"""
Appointment-setting reply agent.

Polls the sending mailbox for unread messages. For every reply that matches
a lead, replays the full conversation to Claude along with the owner's real
open calendar slots. Claude decides one of:

  - reply        -> send a threaded reply (answer question, offer time slots)
  - book         -> confirm a specific offered slot: create the appointment,
                    send a confirmation email with an .ics calendar invite,
                    and alert the owner
  - escalate     -> forward to the owner (complex, angry, pricing negotiation,
                    or auto-reply limit hit)
  - unsubscribe  -> suppress the address, cancel pending follow-ups
  - ignore       -> out-of-office / bounce / noise

Every inbound and outbound message is logged to the conversations table so
the agent always has full context. Pending follow-ups are cancelled the
moment a lead replies, so nobody who answered gets a canned "just checking in".
"""

import email
import imaplib
import os
from email.header import decode_header
from email.utils import parseaddr

import appointments
import db
import llm
import send
from config import AVAIL, BUSINESS, DIGEST, LLM

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

BOOKING_SYSTEM_TEMPLATE = """You are the scheduling assistant for {business_name}, a window cleaning and
pressure washing business in Tucson, AZ, owned by {owner_name}. You reply to emails from
prospects as {owner_name} (first person, warm, brief, local, professional — never robotic,
never corporate). Your #1 goal: get a specific appointment on the calendar.

You will see the full conversation so far and the CURRENTLY OPEN calendar slots.

Decide ONE action:

1. "book" — Use when the prospect clearly agrees to a specific date/time that matches one
   of the OPEN SLOTS listed (or unambiguously picks one you previously offered and it is
   still listed as open). Fill slot_starts_at/slot_ends_at EXACTLY as shown in the open
   slots list. Write reply_body as a short confirmation: restate day/time in plain words,
   what you'll do, that a calendar invite is attached, and that they can reply to reschedule.

2. "reply" — Use when they're interested or have questions but haven't committed to a slot.
   Answer their question, then offer 2–3 specific open slots from the list ("Would Tuesday
   July 8 at 8 AM or Thursday July 10 at 10 AM work?"). Always propose concrete times —
   never say "let me know what works" without options. If they proposed a time that is NOT
   open, apologize and offer the nearest open alternatives.

3. "escalate" — Use for: pricing negotiation beyond a simple quote request, complaints or
   anger, complex/large jobs needing a site visit, legal-sounding messages, or anything you
   are unsure about. Do not write a reply_body; the owner will handle it personally.

4. "unsubscribe" — Any variation of stop/remove/not interested-don't-contact-me.

5. "ignore" — Auto-replies (out of office), bounces, newsletters, spam.

Rules:
- NEVER quote exact prices. If asked, say {owner_name} will confirm the price, typical jobs
  run competitive for Tucson, and a firm quote comes with the visit — then still offer slots.
- Keep replies under 120 words. No footers or signatures beyond "– {owner_name}".
- Do not invent slots. Only offer times from the OPEN SLOTS list.
- Times are Arizona time (no DST). Say e.g. "8 AM" — don't mention timezones.
- If the conversation already has {max_replies}+ back-and-forths without a booking, escalate."""


def _decode_header_value(val: str) -> str:
    parts = decode_header(val)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _get_plain_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return ""


def _find_lead(sender_email: str, in_reply_to: str | None) -> dict | None:
    if in_reply_to:
        lead = db.get_lead_by_message_id(in_reply_to)
        if lead:
            return lead
    return db.get_lead_by_email(sender_email)


def _alert_owner(subject: str, body: str) -> None:
    if not DIGEST.owner_email:
        return
    try:
        send.send_email(
            to=DIGEST.owner_email,
            subject=f"[{BUSINESS.name} Alert] {subject}",
            body=body,
            add_footer=False,
        )
    except Exception as e:
        print(f"[replies] Failed to send alert: {e}")


def _build_transcript(lead_id: int) -> str:
    convo = db.get_conversation(lead_id, limit=30)
    if not convo:
        return "(no prior messages logged)"
    lines = []
    for m in convo:
        who = "US" if m["direction"] == "outbound" else "PROSPECT"
        subj = f" [{m['subject']}]" if m.get("subject") else ""
        lines.append(f"--- {who}{subj} ({m['created_at']}) ---\n{m['body'][:1500]}")
    return "\n\n".join(lines)


def handle_reply(lead: dict, sender_email: str, subject: str,
                 body_text: str, inbound_message_id: str | None) -> None:
    """Process one inbound reply for a known lead."""
    lead_id = lead["id"]
    db.log_conversation(lead_id, "inbound", subject, body_text[:5000], inbound_message_id)
    reply_count = db.increment_reply_count(lead_id)
    db.cancel_pending_outreach(lead_id, reason="replied")

    slots = appointments.get_free_slots(count=6)
    slots_text = "\n".join(
        f"- {s['label']}  (starts_at={s['starts_at']}, ends_at={s['ends_at']})"
        for s in slots
    ) or "(no open slots in the next two weeks — escalate to owner)"

    system = BOOKING_SYSTEM_TEMPLATE.format(
        business_name=BUSINESS.name,
        owner_name=BUSINESS.owner_name,
        max_replies=AVAIL.max_auto_replies_per_lead,
    )
    user = (
        f"PROSPECT BUSINESS: {lead['name']}\n"
        f"Address: {lead.get('address') or 'unknown'}\n"
        f"Email: {sender_email}\n"
        f"Auto-replies sent so far in this thread: {reply_count - 1}\n\n"
        f"OPEN SLOTS (Arizona time):\n{slots_text}\n\n"
        f"CONVERSATION SO FAR:\n{_build_transcript(lead_id)}\n\n"
        f"NEWEST MESSAGE FROM PROSPECT (respond to this):\n"
        f"Subject: {subject}\n{body_text[:3000]}"
    )

    decision: llm.BookingAction = llm.structured_call(
        model=LLM.reply_model,
        system=system,
        user=user,
        output_type=llm.BookingAction,
        max_tokens=1500,
    )

    # Safety: force escalation once the auto-reply cap is hit
    if decision.action in ("reply", "book") and reply_count > AVAIL.max_auto_replies_per_lead:
        decision.action = "escalate"
        decision.summary += " (auto-reply limit reached)"

    reply_subject = decision.reply_subject or (
        subject if subject.lower().startswith("re:") else f"Re: {subject}"
    )
    thread_id = db.get_last_message_id(lead_id)

    if decision.action == "unsubscribe":
        db.add_suppression(sender_email, "unsubscribe_reply")
        db.cancel_pending_outreach(lead_id, reason="unsubscribed")
        db.update_lead(lead_id, status="unsubscribed")
        print(f"[replies] Unsubscribed: {sender_email}")
        return

    if decision.action == "ignore":
        print(f"[replies] Ignored (ooo/noise): {sender_email}")
        return

    if decision.action == "escalate":
        db.update_lead(lead_id, status="needs_owner")
        _alert_owner(
            subject=f"Needs you: {lead['name']} — {decision.summary}",
            body=(
                f"Lead: {lead['name']}\nEmail: {sender_email}\n"
                f"Phone: {lead.get('phone') or 'n/a'}\n"
                f"Why escalated: {decision.summary}\n\n"
                f"--- Their message ---\n{body_text[:3000]}\n\n"
                f"Reply directly from your inbox — the thread is in your Sent folder."
            ),
        )
        print(f"[replies] ESCALATED: {lead['name']} — {decision.summary}")
        return

    if decision.action == "book":
        appt_id = appointments.book_appointment(
            lead_id,
            decision.slot_starts_at,
            decision.slot_ends_at,
            service=decision.service or lead.get("service_pitch") or "",
            location=lead.get("address") or "",
            notes=f"Booked automatically from email thread with {sender_email}",
        )
        if appt_id is None:
            # Slot no longer valid — fall back to a re-offer reply
            print(f"[replies] Slot conflict for {lead['name']}; sending re-offer")
            fresh = appointments.get_free_slots(count=3)
            options = "\n".join(f"- {s['label']}" for s in fresh)
            fallback = (
                f"So sorry — that time just got taken. Here's what I have open:\n\n{options}\n\n"
                f"Any of those work?\n\n– {BUSINESS.owner_name}"
            )
            msg_id = send.send_email(sender_email, reply_subject, fallback,
                                     add_footer=False, in_reply_to=thread_id)
            db.log_conversation(lead_id, "outbound", reply_subject, fallback, msg_id)
            return

        ics = appointments.build_ics(
            decision.slot_starts_at,
            decision.slot_ends_at,
            summary=f"{BUSINESS.name} — {decision.service or 'service visit'} ({lead['name']})",
            location=lead.get("address") or "",
            description=f"Booked via email with {sender_email}. Phone: {BUSINESS.phone}",
        )
        msg_id = send.send_email(
            sender_email, reply_subject, decision.reply_body,
            add_footer=False, in_reply_to=thread_id, ics_content=ics,
        )
        db.log_conversation(lead_id, "outbound", reply_subject, decision.reply_body, msg_id)
        db.update_lead(lead_id, status="booked")

        # Owner gets the invite too so it lands on his calendar
        slot_dt = decision.slot_starts_at.replace("T", " ")
        _alert_owner(
            subject=f"NEW JOB BOOKED: {lead['name']} — {slot_dt}",
            body=(
                f"An appointment was just booked automatically.\n\n"
                f"Business: {lead['name']}\n"
                f"When:     {slot_dt} (Arizona time)\n"
                f"Service:  {decision.service or 'see thread'}\n"
                f"Where:    {lead.get('address') or 'confirm with client'}\n"
                f"Contact:  {sender_email} / {lead.get('phone') or 'n/a'}\n\n"
                f"A calendar invite (.ics) was emailed to the client. "
                f"Add it to your calendar from the copy below."
            ),
        )
        if DIGEST.owner_email:
            try:
                send.send_email(
                    DIGEST.owner_email,
                    f"Calendar invite: {lead['name']} — {slot_dt}",
                    "Open the attached invite.ics to add this job to your calendar.",
                    add_footer=False, ics_content=ics,
                )
            except Exception as e:
                print(f"[replies] Owner ICS send failed: {e}")
        print(f"[replies] BOOKED: {lead['name']} at {decision.slot_starts_at}")
        return

    # Default: "reply"
    msg_id = send.send_email(sender_email, reply_subject, decision.reply_body,
                             add_footer=False, in_reply_to=thread_id)
    db.log_conversation(lead_id, "outbound", reply_subject, decision.reply_body, msg_id)
    db.update_lead(lead_id, status="in_conversation")
    print(f"[replies] Replied to {lead['name']}: {decision.summary}")


def check_replies() -> None:
    """Poll IMAP for unread replies and route them through the booking agent."""
    if not IMAP_PASSWORD:
        print("[replies] IMAP_PASSWORD not set — skipping reply check")
        return

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select("INBOX")
        _, msg_nums = mail.search(None, "UNSEEN")
    except Exception as e:
        print(f"[replies] IMAP connection failed: {e}")
        return

    for num in msg_nums[0].split():
        try:
            _, data = mail.fetch(num, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            sender_email = parseaddr(msg.get("From", ""))[1].strip().lower()
            subject = _decode_header_value(msg.get("Subject", ""))
            in_reply_to = (msg.get("In-Reply-To") or "").strip() or None
            inbound_message_id = (msg.get("Message-ID") or "").strip() or None
            body_text = _get_plain_text(msg)

            lead = _find_lead(sender_email, in_reply_to)
            if not lead:
                continue  # not our lead — leave unread state alone? mark seen below

            handle_reply(lead, sender_email, subject, body_text, inbound_message_id)
            mail.store(num, "+FLAGS", "\\Seen")

        except Exception as e:
            print(f"[replies] Error processing message {num}: {e}")

    mail.logout()


if __name__ == "__main__":
    check_replies()
