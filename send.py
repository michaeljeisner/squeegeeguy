import smtplib
import sys
import uuid
from email.message import EmailMessage
from email.utils import make_msgid, formatdate

import db
from config import SEND, BUSINESS, DIGEST

FOOTER_TEMPLATE = """
—
{from_name} | {business_name}
{physical_address}
Reply STOP to unsubscribe"""


def _build_footer() -> str:
    return FOOTER_TEMPLATE.format(
        from_name=SEND.from_name,
        business_name=BUSINESS.name,
        physical_address=BUSINESS.physical_address or "(address on file)",
    )


def get_today_limit() -> int:
    warmup_day = db.get_warmup_day()
    warmup_week = (warmup_day // 7) + 1
    max_limit = max(SEND.warmup_schedule.values()) if SEND.warmup_schedule else 50
    return SEND.warmup_schedule.get(warmup_week, max_limit)


def can_send_today() -> bool:
    return db.get_daily_send_count() < get_today_limit()


def send_email(to: str, subject: str, body: str, add_footer: bool = True) -> str:
    """
    Send one email. Returns the Message-ID string.
    CAN-SPAM compliant: physical address, unsubscribe instruction, List-Unsubscribe header.
    Opens a fresh SMTP connection per call.
    """
    if add_footer:
        full_body = body + "\n" + _build_footer()
    else:
        full_body = body

    msg = EmailMessage()
    msg["From"] = f"{SEND.from_name} <{SEND.from_email}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg_id = make_msgid(domain=BUSINESS.sending_domain or "squeegeeguy.com")
    msg["Message-ID"] = msg_id
    msg["List-Unsubscribe"] = f"<mailto:{SEND.from_email}?subject=unsubscribe>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(full_body)

    with smtplib.SMTP(SEND.smtp_host, SEND.smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(SEND.smtp_user, SEND.smtp_password)
        smtp.send_message(msg)

    return msg_id


def send_email_dry_run(to: str, subject: str, body: str, add_footer: bool = True) -> str:
    """Log the email without actually sending. Returns a fake Message-ID."""
    if add_footer:
        full_body = body + "\n" + _build_footer()
    else:
        full_body = body

    fake_id = f"dry-run-{uuid.uuid4()}"
    print(f"\n--- DRY RUN EMAIL ---")
    print(f"To: {to}")
    print(f"Subject: {subject}")
    print(f"Message-ID: {fake_id}")
    print(f"Body:\n{full_body}")
    print(f"--- END DRY RUN EMAIL ---\n")
    return fake_id


if __name__ == "__main__":
    # Send a test email to the owner
    if not SEND.smtp_password:
        print("SMTP_PASSWORD not set in .env — cannot send test email")
        sys.exit(1)
    owner = DIGEST.owner_email or SEND.smtp_user
    msg_id = send_email(
        to=owner,
        subject="SqueegeeGuy Lead-Gen: SMTP test",
        body="This is a test email from the SqueegeeGuy lead-gen system. If you received this, SMTP is working.",
    )
    print(f"Test email sent to {owner}. Message-ID: {msg_id}")
