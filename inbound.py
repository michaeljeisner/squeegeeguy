"""
Phase 2: Inbound quote-form receiver.

Lightweight HTTP server that accepts POST /quote submissions.
Run standalone:  uv run python inbound.py [--port 8765]

Form fields: name, email, phone, address, service_needed, message
"""

import argparse
import json
import sqlite3
import sys
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import db
import send
from config import DIGEST, BUSINESS


def _insert_inbound_lead(data: dict) -> int:
    place_id = f"inbound-{uuid.uuid4()}"
    with sqlite3.connect(db.DB_PATH) as conn:
        cur = conn.execute(
            """INSERT INTO leads (place_id, name, address, phone, email, status, types)
               VALUES (?, ?, ?, ?, ?, 'inbound', '["inbound"]')""",
            (
                place_id,
                data.get("name", "Unknown"),
                data.get("address", ""),
                data.get("phone", ""),
                data.get("email", ""),
            ),
        )
    return cur.lastrowid


def handle_quote_submission(data: dict) -> None:
    """Process an inbound quote request."""
    name = data.get("name", "there")
    email_addr = data.get("email", "")
    service = data.get("service_needed", "")
    message = data.get("message", "")

    if not email_addr:
        return

    # Insert into DB
    lead_id = _insert_inbound_lead(data)

    # Auto-acknowledgment to the requester — offer real open slots right away
    try:
        import appointments
        slots = appointments.get_free_slots(count=3)
    except Exception:
        slots = []
    slot_lines = "".join(f"  • {s['label']}\n" for s in slots)
    slot_offer = (
        f"\nI have these openings coming up:\n{slot_lines}\n"
        "Just reply with the one that works and I'll lock it in.\n"
        if slots else "\n"
    )

    ack_subject = f"Got your quote request — {BUSINESS.name} will be in touch!"
    ack_body = (
        f"Hi {name},\n\n"
        f"Thanks for reaching out to {BUSINESS.name}! We received your request"
        f"{' for ' + service if service else ''} and will get back to you shortly.\n"
        f"{slot_offer}\n"
        f"You can also reach us at {BUSINESS.phone or 'our website'}.\n\n"
        f"Talk soon,\n{BUSINESS.owner_name}\n{BUSINESS.name}"
    )
    try:
        send.send_email(email_addr, ack_subject, ack_body, add_footer=False)
        db.log_conversation(lead_id, "outbound", ack_subject, ack_body)
    except Exception as e:
        print(f"[inbound] Failed to send ack to {email_addr}: {e}")

    # Alert owner
    if DIGEST.owner_email:
        alert_body = (
            f"New inbound quote request (lead ID {lead_id}):\n\n"
            f"Name:     {name}\n"
            f"Email:    {email_addr}\n"
            f"Phone:    {data.get('phone', '')}\n"
            f"Address:  {data.get('address', '')}\n"
            f"Service:  {service}\n"
            f"Message:  {message}\n"
        )
        try:
            send.send_email(
                DIGEST.owner_email,
                f"[SqueegeeGuy] New quote request from {name}",
                alert_body,
                add_footer=False,
            )
        except Exception as e:
            print(f"[inbound] Failed to send owner alert: {e}")


class QuoteHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        print(f"[inbound] {self.address_string()} {format % args}")

    def _send_response(self, code: int, body: str, content_type: str = "text/plain") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/quote":
            self._send_response(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        content_type = self.headers.get("Content-Type", "")

        if "application/json" in content_type:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                self._send_response(400, "Invalid JSON")
                return
        else:
            # application/x-www-form-urlencoded
            parsed_qs = parse_qs(raw)
            data = {k: v[0] for k, v in parsed_qs.items()}

        try:
            handle_quote_submission(data)
            self._send_response(200, json.dumps({"ok": True}), "application/json")
        except Exception as e:
            print(f"[inbound] Error handling submission: {e}")
            self._send_response(500, "Server error")

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_response(200, "ok")
        else:
            self._send_response(404, "Not found")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), QuoteHandler)
    print(f"[inbound] Listening on http://0.0.0.0:{args.port}/quote")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[inbound] Shutting down")


if __name__ == "__main__":
    main()
