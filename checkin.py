"""
Fast reply loop. Run every 15 minutes via launchd (installed by setup.sh).

Prospects who reply expect an answer within minutes, not the next morning —
this is what makes appointments actually get booked. It only polls IMAP and
routes replies through the booking agent; it never prospects or cold-emails.
"""

import sys

import replies


def main() -> None:
    try:
        replies.check_replies()
    except Exception as e:
        print(f"[checkin] ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
