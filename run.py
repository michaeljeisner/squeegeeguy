import argparse
import random
import sys
import time
from datetime import datetime, timezone

import db
import digest
import draft
import enrich
import prospect
import score
import send
from config import PLACES_API_KEY, SEND, TARGET


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SqueegeeGuy lead-gen pipeline")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline without sending any emails",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_time = time.monotonic()
    log: dict = {
        "started_at": now(),
        "errors": [],
        "prospects_found": 0,
        "enriched": 0,
        "scored": 0,
        "drafted": 0,
        "sent": 0,
        "dry_run": args.dry_run,
    }

    # Optional: Phase 2 — check replies first (replies.py must exist)
    try:
        import replies
        replies.check_replies()
    except ImportError:
        pass
    except Exception as e:
        log["errors"].append(f"replies: {e}")

    # 1. Prospect
    print("[run] Step 1: Prospecting...")
    for category in TARGET.categories:
        try:
            leads = prospect.search_category(category, TARGET.location, PLACES_API_KEY)
            inserted = db.insert_leads(leads)
            log["prospects_found"] += inserted
            print(f"[prospect] {category}: {len(leads)} found, {inserted} new")
        except Exception as e:
            log["errors"].append(f"prospect/{category}: {e}")
            print(f"[prospect] ERROR {category}: {e}", file=sys.stderr)

    print(f"[run] Prospects inserted: {log['prospects_found']}")

    # 2. Enrich
    print("[run] Step 2: Enriching...")
    new_leads = db.get_leads_by_status("new")
    for lead in new_leads:
        try:
            email = enrich.enrich_lead(lead["website"]) if lead["website"] else None
            if email:
                db.update_lead(lead["id"], status="enriched", email=email)
                log["enriched"] += 1
            else:
                db.update_lead(lead["id"], status="no_contact")
        except Exception as e:
            log["errors"].append(f"enrich/{lead['name']}: {e}")
            print(f"[enrich] ERROR {lead['name']}: {e}", file=sys.stderr)

    print(f"[run] Enriched: {log['enriched']}")

    # 3. Score
    print("[run] Step 3: Scoring...")
    enriched_leads = db.get_leads_by_status("enriched")
    for lead in enriched_leads:
        try:
            result = score.score_lead(lead)
            db.update_lead(lead["id"], status="scored", **result.model_dump())
            log["scored"] += 1
        except Exception as e:
            log["errors"].append(f"score/{lead['name']}: {e}")
            print(f"[score] ERROR {lead['name']}: {e}", file=sys.stderr)

    print(f"[run] Scored: {log['scored']}")

    # 4. Draft
    print("[run] Step 4: Drafting...")
    scored_leads = db.get_leads_by_status("scored", min_score=TARGET.min_fit_score)
    for lead in scored_leads:
        try:
            emails = draft.draft_emails(lead)
            db.insert_outreach(lead["id"], "initial", emails.subject, emails.body)
            db.insert_outreach(lead["id"], "followup_1", emails.followup_1_subject, emails.followup_1_body)
            db.insert_outreach(lead["id"], "followup_2", emails.followup_2_subject, emails.followup_2_body)
            db.update_lead(lead["id"], status="drafted")
            log["drafted"] += 1
        except Exception as e:
            log["errors"].append(f"draft/{lead['name']}: {e}")
            print(f"[draft] ERROR {lead['name']}: {e}", file=sys.stderr)

    print(f"[run] Drafted: {log['drafted']}")

    # 5. Send
    if args.dry_run:
        print("[run] Step 5: SKIPPED (dry run)")
        # Log drafts to stdout so the owner can review
        pending = db.get_pending_outreach(limit=5)
        for o in pending:
            send.send_email_dry_run(o["email"], o["subject"], o["body"])
    else:
        print("[run] Step 5: Sending...")
        if not send.can_send_today():
            print(f"[send] Daily warmup limit reached ({send.get_today_limit()}). Skipping sends.")
        else:
            remaining = send.get_today_limit() - db.get_daily_send_count()
            pending = db.get_pending_outreach(limit=remaining)
            for outreach in pending:
                if db.is_suppressed(outreach["email"]):
                    db.mark_failed(outreach["id"], "suppressed")
                    print(f"[send] Suppressed: {outreach['email']}")
                    continue
                try:
                    msg_id = send.send_email(outreach["email"], outreach["subject"], outreach["body"])
                    db.mark_sent(outreach["id"], msg_id)
                    db.update_lead(outreach["lead_id"], status="sent")
                    log["sent"] += 1
                    print(f"[send] Sent to {outreach['email']} (step: {outreach['step']})")
                    delay = random.uniform(*SEND.inter_email_delay_range)
                    time.sleep(delay)
                except Exception as e:
                    db.mark_failed(outreach["id"], str(e))
                    log["errors"].append(f"send/{outreach['email']}: {e}")
                    print(f"[send] ERROR {outreach['email']}: {e}", file=sys.stderr)

    # Optional: Phase 3 — intent signals
    try:
        import listen
        new_signals = listen.check_signals()
        log["new_signals"] = new_signals
    except ImportError:
        pass
    except Exception as e:
        log["errors"].append(f"listen: {e}")

    # 6. Digest
    log["completed_at"] = now()
    log["duration_seconds"] = time.monotonic() - start_time
    db.insert_run_log(log)

    try:
        if args.dry_run:
            print("[run] Digest skipped in dry-run mode (SMTP may not be configured)")
        else:
            digest.send_digest(log)
    except Exception as e:
        print(f"[digest] ERROR: {e}", file=sys.stderr)

    print(f"\n[run] Done in {log['duration_seconds']:.1f}s")
    print(f"      prospects={log['prospects_found']} enriched={log['enriched']} "
          f"scored={log['scored']} drafted={log['drafted']} sent={log['sent']}")
    if log["errors"]:
        print(f"      errors={len(log['errors'])}")
        for err in log["errors"]:
            print(f"        - {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
