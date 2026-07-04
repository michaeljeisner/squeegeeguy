"""
Smoke tests for the scheduling + outreach core. Run: uv run python test_core.py
Uses a temporary database so it never touches squeegeeguy.db.
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Point db at a temp file BEFORE importing modules
_tmp = tempfile.mkdtemp()
import db
db.DB_PATH = Path(_tmp) / "test.db"
db.init_db()

import appointments
from config import AVAIL, SEND

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f" FAIL {name} {detail}")


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


# ---------------------------------------------------------------- leads / outreach
db.insert_leads([{
    "place_id": "test-1", "name": "Test Diner", "address": "1 Main St, Tucson",
    "phone": "(520) 555-1111", "website": "https://example.test", "rating": 4.5,
    "types": ["restaurant"],
}])
lead = db.get_leads_by_status("new")[0]
check("lead inserted", lead["name"] == "Test Diner")

db.update_lead(lead["id"], status="drafted", email="owner@testdiner.com")
db.insert_outreach(lead["id"], "initial", "Hi", "body-initial")
db.insert_outreach(lead["id"], "followup_1", "F1", "body-f1")
db.insert_outreach(lead["id"], "followup_2", "F2", "body-f2")

pending = db.get_pending_outreach()
check("pending initial visible", len(pending) == 1 and pending[0]["step"] == "initial")

# No followups due before initial is sent
check("no followups before initial sent", db.get_due_followups(SEND.followup_delays_days) == [])

# Mark initial sent 4 days ago -> followup_1 due, followup_2 not yet
db.mark_sent(pending[0]["id"], "<msg-1@test>")
db.update_lead(lead["id"], status="sent")
with db._connect() as conn:
    conn.execute(
        "UPDATE outreach SET sent_at = ? WHERE step='initial'",
        ((datetime.utcnow() - timedelta(days=4)).isoformat(),),
    )
due = db.get_due_followups(SEND.followup_delays_days)
check("followup_1 due after 3d", len(due) == 1 and due[0]["step"] == "followup_1",
      f"got {[d['step'] for d in due]}")
check("threading id carried", due[0]["initial_message_id"] == "<msg-1@test>")

# Send followup_1, backdate initial to 8 days -> followup_2 due
db.mark_sent(due[0]["id"], "<msg-2@test>")
with db._connect() as conn:
    conn.execute(
        "UPDATE outreach SET sent_at = ? WHERE step='initial'",
        ((datetime.utcnow() - timedelta(days=8)).isoformat(),),
    )
due2 = db.get_due_followups(SEND.followup_delays_days)
check("followup_2 due after 7d + f1 sent", len(due2) == 1 and due2[0]["step"] == "followup_2",
      f"got {[d['step'] for d in due2]}")

# Reply cancels pending outreach
cancelled = db.cancel_pending_outreach(lead["id"], "replied")
check("reply cancels pending followups", cancelled == 1)
check("nothing due after cancel", db.get_due_followups(SEND.followup_delays_days) == [])

# ---------------------------------------------------------------- conversations
db.log_conversation(lead["id"], "outbound", "Hi", "body-initial", "<msg-1@test>")
db.log_conversation(lead["id"], "inbound", "Re: Hi", "yes interested!")
convo = db.get_conversation(lead["id"])
check("conversation logged in order", len(convo) == 2 and convo[0]["direction"] == "outbound")
check("last outbound message id", db.get_last_message_id(lead["id"]) == "<msg-1@test>")

# ---------------------------------------------------------------- suppression
db.add_suppression("Owner@TestDiner.com", "test")
check("suppression case-insensitive", db.is_suppressed("owner@testdiner.com"))

# ---------------------------------------------------------------- slots
# Anchor "now" to a Monday 9 AM so results are deterministic
monday = datetime(2026, 7, 6, 9, 0)  # Monday
slots = appointments.get_free_slots(count=6, _now=monday)
check("slots generated", len(slots) == 6, f"got {len(slots)}")
first = datetime.strptime(slots[0]["starts_at"], "%Y-%m-%dT%H:%M")
check("min notice respected", first >= monday + timedelta(hours=AVAIL.min_notice_hours),
      f"first={first}")
check("slots inside working hours",
      all(AVAIL.day_start_hour <= datetime.strptime(s["starts_at"], "%Y-%m-%dT%H:%M").hour < AVAIL.day_end_hour
          for s in slots))
check("no Sunday slots",
      all(datetime.strptime(s["starts_at"], "%Y-%m-%dT%H:%M").weekday() in AVAIL.workdays
          for s in slots))

# Book the first slot, regenerate -> that slot should be gone
s0 = slots[0]
appt_id = db.insert_appointment(lead["id"], s0["starts_at"], s0["ends_at"], service="windows")
check("appointment inserted", appt_id > 0)
slots2 = appointments.get_free_slots(count=6, _now=monday)
check("booked slot excluded", all(s["starts_at"] != s0["starts_at"] for s in slots2))

# Validation
check("conflict rejected", not appointments.is_slot_available(s0["starts_at"], s0["ends_at"]))
future_ok = slots2[0]
check("open slot accepted", appointments.is_slot_available(future_ok["starts_at"], future_ok["ends_at"])
      or datetime.strptime(future_ok["starts_at"], "%Y-%m-%dT%H:%M") < datetime.now())  # only fails if test run near 2026-07-06
check("garbage rejected", not appointments.is_slot_available("not-a-date", "also-no"))
check("sunday rejected", not appointments.is_slot_available("2026-07-12T09:00", "2026-07-12T11:00"))
check("after-hours rejected", not appointments.is_slot_available("2026-07-13T18:00", "2026-07-13T20:00"))

# ICS
ics = appointments.build_ics(s0["starts_at"], s0["ends_at"], "Test Job", location="1 Main St", description="notes")
check("ics has VEVENT", "BEGIN:VEVENT" in ics and "SUMMARY:Test Job" in ics)
check("ics has TZ", "TZID=America/Phoenix" in ics)

# digest queries
booked = db.get_appointments_booked_since(24)
check("digest sees booked job", len(booked) == 1 and booked[0]["lead_name"] == "Test Diner")

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
