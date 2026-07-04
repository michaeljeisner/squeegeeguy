"""
Appointment scheduling: free-slot generation, booking, and ICS calendar files.

All times are naive local datetimes in America/Phoenix (Tucson — no DST),
stored as ISO strings 'YYYY-MM-DDTHH:MM'.
"""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import db
from config import AVAIL, BUSINESS

TZ = ZoneInfo(AVAIL.timezone)
FMT = "%Y-%m-%dT%H:%M"


def now_local() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def _overlaps(start: datetime, end: datetime, busy: list[tuple[datetime, datetime]]) -> bool:
    return any(start < b_end and end > b_start for b_start, b_end in busy)


def get_free_slots(count: int = 6, *, _now: datetime | None = None) -> list[dict]:
    """
    Return up to `count` open appointment slots as dicts:
      {"starts_at": "2026-07-06T08:00", "ends_at": "...", "label": "Monday, July 6 at 8:00 AM"}
    Respects workdays, working hours, min notice, existing confirmed appointments.
    """
    current = _now or now_local()
    earliest = current + timedelta(hours=AVAIL.min_notice_hours)

    busy = [
        (datetime.strptime(s[:16], FMT), datetime.strptime(e[:16], FMT))
        for s, e in db.get_busy_slots()
    ]

    slots: list[dict] = []
    day = earliest.date()
    end_date = current.date() + timedelta(days=AVAIL.max_days_out)

    while day <= end_date and len(slots) < count:
        if day.weekday() in AVAIL.workdays:
            slot_start = datetime.combine(day, datetime.min.time()).replace(hour=AVAIL.day_start_hour)
            day_end = datetime.combine(day, datetime.min.time()).replace(hour=AVAIL.day_end_hour)
            while slot_start + timedelta(minutes=AVAIL.slot_minutes) <= day_end and len(slots) < count:
                slot_end = slot_start + timedelta(minutes=AVAIL.slot_minutes)
                if slot_start >= earliest and not _overlaps(slot_start, slot_end, busy):
                    slots.append({
                        "starts_at": slot_start.strftime(FMT),
                        "ends_at": slot_end.strftime(FMT),
                        "label": format_slot(slot_start),
                    })
                slot_start = slot_end
        day += timedelta(days=1)

    return slots


def format_slot(dt: datetime) -> str:
    hour = dt.strftime("%I:%M %p").lstrip("0")
    return f"{dt.strftime('%A, %B')} {dt.day} at {hour}"


def is_slot_available(starts_at: str, ends_at: str) -> bool:
    """Validate a proposed booking: inside working hours, notice ok, no conflicts."""
    try:
        start = datetime.strptime(starts_at[:16], FMT)
        end = datetime.strptime(ends_at[:16], FMT)
    except ValueError:
        return False
    if end <= start:
        return False
    if start.weekday() not in AVAIL.workdays:
        return False
    if start.hour < AVAIL.day_start_hour or end.hour > AVAIL.day_end_hour or (
        end.hour == AVAIL.day_end_hour and (end.minute or end.second)
    ):
        return False
    if start < now_local() + timedelta(hours=AVAIL.min_notice_hours):
        return False
    busy = [
        (datetime.strptime(s[:16], FMT), datetime.strptime(e[:16], FMT))
        for s, e in db.get_busy_slots()
    ]
    return not _overlaps(start, end, busy)


def book_appointment(lead_id: int, starts_at: str, ends_at: str,
                     service: str = "", location: str = "", notes: str = "") -> int | None:
    """Book if the slot is valid and free. Returns appointment id, or None if not available."""
    if not is_slot_available(starts_at, ends_at):
        return None
    return db.insert_appointment(lead_id, starts_at[:16], ends_at[:16],
                                 service=service, location=location, notes=notes)


def build_ics(starts_at: str, ends_at: str, summary: str,
              location: str = "", description: str = "") -> str:
    """Minimal RFC 5545 VCALENDAR the prospect (and owner) can add to any calendar."""
    start = datetime.strptime(starts_at[:16], FMT)
    end = datetime.strptime(ends_at[:16], FMT)
    stamp = datetime.now(TZ).strftime("%Y%m%dT%H%M%S")

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

    return "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{BUSINESS.name}//LeadGen//EN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@{BUSINESS.sending_domain or 'squeegeeguy.com'}",
        f"DTSTAMP;TZID={AVAIL.timezone}:{stamp}",
        f"DTSTART;TZID={AVAIL.timezone}:{start.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND;TZID={AVAIL.timezone}:{end.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{esc(summary)}",
        f"LOCATION:{esc(location)}" if location else "",
        f"DESCRIPTION:{esc(description)}" if description else "",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]).replace("\r\n\r\n", "\r\n")


if __name__ == "__main__":
    print("Next open slots:")
    for s in get_free_slots():
        print(f"  {s['label']}  ({s['starts_at']} – {s['ends_at']})")
