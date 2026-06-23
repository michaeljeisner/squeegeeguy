"""
Phase 2: IMAP reply handler.

Polls the sending mailbox for unread messages, classifies each with Claude,
and routes actions: mark interested, suppress unsubscribes, alert owner on urgent replies.

Enable follow-up sends by importing and calling check_replies() at the start of run.py.
"""

import email
import imaplib
import os
import sqlite3
from email.header import decode_header

import db
import llm
import send
from config import LLM, DIGEST, SEND, BUSINESS

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

CLASSIFY_SYSTEM = """You are classifying email replies to a cold outreach campaign for SqueegeeGuy,
a window cleaning and pressure washing business in Tucson, AZ.

Categories:
- interested: They want a quote or more info.
- not_interested: They declined or said no.
- unsubscribe: They asked to be removed (any variation of "stop", "unsubscribe", "remove me", etc.).
- out_of_office: Auto-reply indicating they are away.
- question: They asked a question (not yet committed either way).
- other: Anything else.

Mark urgent=true if the reply needs the owner's immediate attention (interested, question, angry)."""


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


def _find_lead_by_reply(conn: sqlite3.Connection, sender: str, in_reply_to: str | None) -> dict | None:
    """Match reply to a lead via message_id or sender email."""
    if in_reply_to:
        row = conn.execute(
            """SELECT l.* FROM leads l
               JOIN outreach o ON o.lead_id = l.id
               WHERE o.message_id = ?""",
            (in_reply_to,),
        ).fetchone()
        if row:
            return dict(row)
    # Fallback: match by sender email
    row = conn.execute(
        "SELECT * FROM leads WHERE email = ? COLLATE NOCASE",
        (sender,),
    ).fetchone()
    return dict(row) if row else None


def _alert_owner(subject: str, body: str) -> None:
    if not DIGEST.owner_email:
        return
    try:
        send.send_email(
            to=DIGEST.owner_email,
            subject=f"[SqueegeeGuy Alert] {subject}",
            body=body,
            add_footer=False,
        )
    except Exception as e:
        print(f"[replies] Failed to send alert: {e}")


def check_replies() -> None:
    """Poll IMAP for unread replies and route them."""
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

    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row

    for num in msg_nums[0].split():
        try:
            _, data = mail.fetch(num, "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            sender = msg.get("From", "")
            # Extract bare email address
            if "<" in sender:
                sender_email = sender.split("<")[1].rstrip(">").strip().lower()
            else:
                sender_email = sender.strip().lower()

            subject = _decode_header_value(msg.get("Subject", ""))
            in_reply_to = msg.get("In-Reply-To", "").strip()
            body_text = _get_plain_text(msg)

            lead = _find_lead_by_reply(conn, sender_email, in_reply_to)
            if not lead:
                # Not our lead — skip
                continue

            # Classify
            classification = llm.structured_call(
                model=LLM.reply_model,
                system=CLASSIFY_SYSTEM,
                user=f"From: {sender_email}\nSubject: {subject}\n\n{body_text[:2000]}",
                output_type=llm.ReplyClassification,
            )

            lead_id = lead["id"]

            if classification.category == "unsubscribe":
                db.add_suppression(sender_email, "unsubscribe_reply")
                db.update_lead(lead_id, status="unsubscribed")
                print(f"[replies] Unsubscribed: {sender_email}")

            elif classification.category in ("interested", "question"):
                db.update_lead(lead_id, status="replied")
                _alert_owner(
                    subject=f"Reply from {lead['name']}: {classification.summary}",
                    body=(
                        f"Lead: {lead['name']}\n"
                        f"Email: {sender_email}\n"
                        f"Category: {classification.category}\n"
                        f"Summary: {classification.summary}\n\n"
                        f"--- Original reply ---\n{body_text[:3000]}"
                    ),
                )
                print(f"[replies] {classification.category.upper()}: {lead['name']} ({sender_email})")

            elif classification.category == "not_interested":
                db.update_lead(lead_id, status="replied")
                print(f"[replies] Not interested: {lead['name']}")

            elif classification.category == "out_of_office":
                print(f"[replies] OOO from {lead['name']} — no action")

            else:
                if classification.urgent:
                    _alert_owner(
                        subject=f"Reply from {lead['name']} (review needed)",
                        body=f"Category: {classification.category}\n\n{body_text[:3000]}",
                    )

            # Mark as read
            mail.store(num, "+FLAGS", "\\Seen")

        except Exception as e:
            print(f"[replies] Error processing message {num}: {e}")

    conn.close()
    mail.logout()
