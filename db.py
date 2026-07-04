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
    reply_count   INTEGER NOT NULL DEFAULT 0,
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
    error      TEXT,
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

-- Full back-and-forth history with each lead (both directions).
-- The booking agent replays this to Claude so replies have full context.
CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id    INTEGER NOT NULL REFERENCES leads(id),
    direction  TEXT NOT NULL,               -- 'outbound' | 'inbound'
    subject    TEXT,
    body       TEXT NOT NULL,
    message_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_conversations_lead ON conversations(lead_id);

-- Booked (or proposed) appointments. This is what the owner wakes up to.
CREATE TABLE IF NOT EXISTS appointments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id      INTEGER NOT NULL REFERENCES leads(id),
    starts_at    TEXT NOT NULL,             -- ISO local time (America/Phoenix)
    ends_at      TEXT NOT NULL,
    service      TEXT,
    location     TEXT,
    notes        TEXT,
    status       TEXT NOT NULL DEFAULT 'confirmed',  -- 'confirmed' | 'cancelled' | 'completed'
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_appointments_start ON appointments(starts_at);
"""

# Columns added after initial release — applied to existing DBs on init.
MIGRATIONS = [
    ("leads", "reply_count", "INTEGER NOT NULL DEFAULT 0"),
    ("outreach", "error", "TEXT"),
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(DDL)
        for table, column, decl in MIGRATIONS:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- leads

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


def get_lead(lead_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(row) if row else None


def get_lead_by_email(email: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM leads WHERE email = ? COLLATE NOCASE", (email,)
        ).fetchone()
    return dict(row) if row else None


def get_lead_by_message_id(message_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """SELECT l.* FROM leads l
               JOIN outreach o ON o.lead_id = l.id
               WHERE o.message_id = ?""",
            (message_id,),
        ).fetchone()
    return dict(row) if row else None


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


def increment_reply_count(lead_id: int) -> int:
    with _connect() as conn:
        conn.execute(
            "UPDATE leads SET reply_count = reply_count + 1, updated_at = ? WHERE id = ?",
            (_now(), lead_id),
        )
        row = conn.execute("SELECT reply_count FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------- outreach

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


def get_due_followups(delays_days: tuple[int, ...], limit: int = 50) -> list[dict]:
    """
    Return pending follow-ups whose delay (measured from the INITIAL send)
    has elapsed and whose lead is still in 'sent' status (i.e. never replied).
    followup_2 is only due after followup_1 was actually sent.
    """
    delay_1 = delays_days[0] if len(delays_days) > 0 else 3
    delay_2 = delays_days[1] if len(delays_days) > 1 else 7
    with _connect() as conn:
        rows = conn.execute(
            """SELECT o.id, o.lead_id, o.step, o.subject, o.body,
                      l.email, l.name,
                      init.sent_at AS initial_sent_at,
                      init.message_id AS initial_message_id
               FROM outreach o
               JOIN leads l    ON l.id = o.lead_id
               JOIN outreach init
                    ON init.lead_id = o.lead_id
                   AND init.step = 'initial'
                   AND init.status = 'sent'
               LEFT JOIN outreach f1
                    ON f1.lead_id = o.lead_id
                   AND f1.step = 'followup_1'
               WHERE o.status = 'pending'
                 AND l.status = 'sent'
                 AND l.email IS NOT NULL
                 AND (
                       (o.step = 'followup_1'
                        AND julianday('now') - julianday(init.sent_at) >= ?)
                    OR (o.step = 'followup_2'
                        AND f1.status = 'sent'
                        AND julianday('now') - julianday(init.sent_at) >= ?)
                 )
               ORDER BY o.created_at
               LIMIT ?""",
            (delay_1, delay_2, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def cancel_pending_outreach(lead_id: int, reason: str = "replied") -> int:
    """Cancel all not-yet-sent outreach for a lead (called when they reply/unsubscribe)."""
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE outreach SET status = 'cancelled', error = ?
               WHERE lead_id = ? AND status = 'pending'""",
            (reason, lead_id),
        )
    return cur.rowcount


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
            "UPDATE outreach SET status = 'failed', error = ? WHERE id = ?",
            (error[:500], outreach_id),
        )


def get_last_message_id(lead_id: int) -> str | None:
    """Most recent outbound message-id for threading follow-ups/replies."""
    with _connect() as conn:
        row = conn.execute(
            """SELECT message_id FROM conversations
               WHERE lead_id = ? AND direction = 'outbound' AND message_id IS NOT NULL
               ORDER BY id DESC LIMIT 1""",
            (lead_id,),
        ).fetchone()
        if row and row[0]:
            return row[0]
        row = conn.execute(
            """SELECT message_id FROM outreach
               WHERE lead_id = ? AND status = 'sent' AND message_id IS NOT NULL
               ORDER BY sent_at DESC LIMIT 1""",
            (lead_id,),
        ).fetchone()
    return row[0] if row and row[0] else None


# ---------------------------------------------------------------- suppression

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


# ---------------------------------------------------------------- conversations

def log_conversation(lead_id: int, direction: str, subject: str | None,
                     body: str, message_id: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO conversations (lead_id, direction, subject, body, message_id)
               VALUES (?, ?, ?, ?, ?)""",
            (lead_id, direction, subject, body, message_id),
        )


def get_conversation(lead_id: int, limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT direction, subject, body, created_at
               FROM conversations WHERE lead_id = ?
               ORDER BY id ASC LIMIT ?""",
            (lead_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- appointments

def insert_appointment(lead_id: int, starts_at: str, ends_at: str,
                       service: str = "", location: str = "", notes: str = "") -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO appointments (lead_id, starts_at, ends_at, service, location, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (lead_id, starts_at, ends_at, service, location, notes),
        )
    return cur.lastrowid or 0


def get_upcoming_appointments() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.*, l.name AS lead_name, l.email AS lead_email, l.phone AS lead_phone
               FROM appointments a
               JOIN leads l ON l.id = a.lead_id
               WHERE a.status = 'confirmed'
                 AND a.starts_at >= datetime('now', 'localtime')
               ORDER BY a.starts_at""",
        ).fetchall()
    return [dict(r) for r in rows]


def get_busy_slots() -> list[tuple[str, str]]:
    """(starts_at, ends_at) for all confirmed future appointments."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT starts_at, ends_at FROM appointments
               WHERE status = 'confirmed'
                 AND ends_at >= datetime('now', 'localtime')""",
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


def get_appointments_booked_since(hours: int = 24) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.*, l.name AS lead_name, l.email AS lead_email, l.phone AS lead_phone
               FROM appointments a
               JOIN leads l ON l.id = a.lead_id
               WHERE a.created_at >= datetime('now', ?)
               ORDER BY a.starts_at""",
            (f"-{hours} hours",),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- run log / limits

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
