import sqlite3
from datetime import date

import db
import send
from config import DIGEST, TARGET


def _top_prospects(limit: int = 5) -> list[dict]:
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT name, fit_score, service_pitch, recurring_potential, personalization_hook
           FROM leads
           WHERE fit_score >= 80
           ORDER BY fit_score DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _sent_today() -> list[dict]:
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT l.email, o.subject
           FROM outreach o
           JOIN leads l ON l.id = o.lead_id
           WHERE o.status = 'sent'
             AND date(o.sent_at) = date('now')
           ORDER BY o.sent_at""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_digest_body(run_stats: dict) -> str:
    today = date.today().isoformat()
    dry = run_stats.get("dry_run", False)
    dry_note = "  *** DRY RUN — no emails sent ***\n" if dry else ""

    prospects_found = run_stats.get("prospects_found", 0)
    enriched = run_stats.get("enriched", 0)
    scored = run_stats.get("scored", 0)
    drafted = run_stats.get("drafted", 0)
    sent = run_stats.get("sent", 0)
    duration = run_stats.get("duration_seconds", 0)
    errors = run_stats.get("errors", [])

    top = _top_prospects()
    sent_today = _sent_today()
    booked = db.get_appointments_booked_since(hours=24)
    upcoming = db.get_upcoming_appointments()

    lines = []

    if booked:
        lines.append("🎉 NEW JOBS BOOKED (last 24h)")
        for a in booked:
            when = a["starts_at"].replace("T", " ")
            lines.append(f"  • {when} — {a['lead_name']} ({a.get('service') or 'service visit'})")
            lines.append(f"    {a.get('location') or 'location TBD'} | {a.get('lead_email') or ''} {a.get('lead_phone') or ''}")
        lines.append("")

    if upcoming:
        lines.append("UPCOMING APPOINTMENTS")
        for a in upcoming[:10]:
            when = a["starts_at"].replace("T", " ")
            lines.append(f"  • {when} — {a['lead_name']} ({a.get('service') or 'service visit'})")
        lines.append("")

    lines += [
        f"TODAY'S RUN{' (DRY)' if dry else ''}",
        dry_note,
        f"  New prospects found:    {prospects_found}",
        f"  Enriched (email found): {enriched}",
        f"  Scored above {TARGET.min_fit_score}:         {scored}",
        f"  Emails drafted:         {drafted}",
        f"  Emails sent:            {sent}",
        "",
    ]

    if top:
        lines.append(f"TOP PROSPECTS (score >= 80)")
        for i, p in enumerate(top, 1):
            lines.append(
                f"  {i}. [{p['fit_score']}] {p['name']} — pitch: {p['service_pitch']}, recurring: {p['recurring_potential']}"
            )
            if p.get("personalization_hook"):
                lines.append(f'     Hook: "{p["personalization_hook"]}"')
        lines.append("")

    if sent_today:
        lines.append("EMAILS SENT TODAY")
        for i, s in enumerate(sent_today, 1):
            lines.append(f'  {i}. To: {s["email"]} — Subject: "{s["subject"]}"')
        lines.append("")

    new_signals = run_stats.get("new_signals", [])
    if new_signals:
        lines.append("NEW INTENT SIGNALS")
        for sig in new_signals[:10]:
            lines.append(f"  [{sig.get('source', '?')}] {sig.get('title', 'No title')}")
            lines.append(f"    {sig.get('url', '')}")
        lines.append("")
        lines.append("Manual check links:")
        lines.append("  Nextdoor: https://nextdoor.com/search/?query=window+cleaning")
        lines.append("  Facebook: https://www.facebook.com/search/posts/?q=window+cleaning+tucson")
        lines.append("")

    if errors:
        lines.append("ERRORS")
        for err in errors:
            lines.append(f"  - {err}")
        lines.append("")

    lines.append(f"Pipeline completed in {duration:.1f}s.")
    return "\n".join(lines)


def send_digest(run_stats: dict) -> None:
    if not DIGEST.owner_email:
        print("[digest] OWNER_EMAIL not set — skipping digest")
        return

    today = date.today().isoformat()
    dry = run_stats.get("dry_run", False)
    subject = f"SqueegeeGuy Daily Digest {'(DRY RUN) ' if dry else ''}— {today}"
    body = build_digest_body(run_stats)

    # Digest is internal — skip compliance footer
    send.send_email(DIGEST.owner_email, subject, body, add_footer=False)
    print(f"[digest] Sent to {DIGEST.owner_email}")
