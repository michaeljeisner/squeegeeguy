import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "squeegeeguy.db"

DDL = """
CREATE TABLE IF NOT EXISTS leads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id      TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    address       TEXT,
    phone         TEXT,
    website       TEXT,
    email         TEXT,
    rating        REAL,
    types         TEXT,
    status        TEXT NOT NULL DEFAULT 'new',
    fit_score     INTEGER,
    service_pitch TEXT,
    recurring_potential TEXT,
    personalization_hook TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outreach (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id    INTEGER NOT NULL REFERENCES leads(id),
    step       TEXT NOT NULL,
    subject    TEXT NOT NULL,
    body       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    sent_at    TEXT,
    message_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(lead_id, step)
);

CREATE TABLE IF NOT EXISTS suppression (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT UNIQUE NOT NULL,
    reason     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    prospects_found INTEGER DEFAULT 0,
    enriched        INTEGER DEFAULT 0,
    scored          INTEGER DEFAULT 0,
    drafted         INTEGER DEFAULT 0,
    sent            INTEGER DEFAULT 0,
    errors          TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT NOT NULL,
    url        TEXT UNIQUE NOT NULL,
    title      TEXT,
    snippet    TEXT,
    found_at   TEXT NOT NULL DEFAULT (datetime('now')),
    notified   INTEGER NOT NULL DEFAULT 0
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(DDL)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_leads(leads: list[dict]) -> int:
    inserted = 0
    with _connect() as conn:
        for lead in leads:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO leads
                       (place_id, name, address, phone, website, rating, types)
                       VALUES (:place_id, :name, :address, :phone, :website, :rating, :types)""",
                    {
                        "place_id": lead["place_id"],
                        "name": lead["name"],
                        "address": lead.get("address"),
                        "phone": lead.get("phone"),
                        "website": lead.get("website"),
                        "rating": lead.get("rating"),
                        "types": json.dumps(lead.get("types", [])),
                    },
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except Exception:
                pass
    return inserted


def get_leads_by_status(status: str, *, min_score: int = 0, limit: int = 200) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM leads
               WHERE status = ?
                 AND (fit_score IS NULL OR fit_score >= ?)
               ORDER BY fit_score DESC NULLS LAST
               LIMIT ?""",
            (status, min_score, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def update_lead(lead_id: int, **fields) -> None:
    fields["updated_at"] = _now()
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = lead_id
    with _connect() as conn:
        conn.execute(f"UPDATE leads SET {sets} WHERE id = :id", fields)


def insert_outreach(lead_id: int, step: str, subject: str, body: str) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO outreach (lead_id, step, subject, body)
               VALUES (?, ?, ?, ?)""",
            (lead_id, step, subject, body),
        )


def get_pending_outreach(limit: int = 50) -> list[dict]:
    """Return pending initial outreach rows joined with lead email."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT o.id, o.lead_id, o.step, o.subject, o.body,
                      l.email, l.name
               FROM outreach o
               JOIN leads l ON l.id = o.lead_id
               WHERE o.status = 'pending'
                 AND o.step = 'initial'
                 AND l.email IS NOT NULL
               ORDER BY o.created_at
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_pending_followups(limit: int = 50) -> list[dict]:
    """Return pending follow-up rows where delay has elapsed and lead hasn't replied."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT o.id, o.lead_id, o.step, o.subject, o.body,
                      l.email, l.name
               FROM outreach o
               JOIN leads l ON l.id = o.lead_id
               WHERE o.status = 'pending'
                 AND o.step IN ('followup_1', 'followup_2')
                 AND l.status = 'sent'
                 AND l.email IS NOT NULL
               ORDER BY o.created_at
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_sent(outreach_id: int, message_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            """UPDATE outreach SET status = 'sent', sent_at = ?, message_id = ?
               WHERE id = ?""",
            (_now(), message_id, outreach_id),
        )


def mark_failed(outreach_id: int, error: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE outreach SET status = 'failed' WHERE id = ?",
            (outreach_id,),
        )


def is_suppressed(email: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM suppression WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
    return row is not None


def add_suppression(email: str, reason: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO suppression (email, reason) VALUES (?, ?)",
            (email, reason),
        )


def insert_run_log(log: dict) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO run_log
               (started_at, completed_at, prospects_found, enriched, scored, drafted, sent, errors)
               VALUES (:started_at, :completed_at, :prospects_found, :enriched,
                       :scored, :drafted, :sent, :errors)""",
            {
                "started_at": log.get("started_at", _now()),
                "completed_at": log.get("completed_at"),
                "prospects_found": log.get("prospects_found", 0),
                "enriched": log.get("enriched", 0),
                "scored": log.get("scored", 0),
                "drafted": log.get("drafted", 0),
                "sent": log.get("sent", 0),
                "errors": json.dumps(log.get("errors", [])),
            },
        )


def get_daily_send_count() -> int:
    with _connect() as conn:
        row = conn.execute(
            """SELECT COUNT(*) FROM outreach
               WHERE status = 'sent'
                 AND date(sent_at) = date('now')"""
        ).fetchone()
    return row[0] if row else 0


def get_warmup_day() -> int:
    """Days since the first-ever sent email (0 if none)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT MIN(sent_at) FROM outreach WHERE status = 'sent'"
        ).fetchone()
    if not row or not row[0]:
        return 0
    first = datetime.fromisoformat(row[0])
    delta = datetime.now(timezone.utc) - first.replace(tzinfo=timezone.utc)
    return max(0, delta.days)


init_db()
