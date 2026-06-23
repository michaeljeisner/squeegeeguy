"""
Phase 3: Intent signal monitoring.

Sources:
- Craigslist RSS (legal, ToS-sanctioned)
- Reddit (optional, gated on REDDIT_CLIENT_ID env var)
- Nextdoor / Facebook: manual check links in daily digest

Add to run.py pipeline AFTER sends and BEFORE digest.
"""

import os
import sqlite3
from datetime import datetime, timezone

import db
import send
from config import DIGEST, TARGET

CRAIGSLIST_KEYWORDS = [
    "window cleaning",
    "pressure washing",
    "power washing",
    "window washer",
]

# Craigslist categories to monitor
# lbg=labor gigs, dmg=domestic gigs, sss=services for sale
CRAIGSLIST_CATEGORIES = ["lbg", "dmg", "sss"]

CRAIGSLIST_BASE = "https://tucson.craigslist.org/search/{category}?format=rss&query={keyword}"


def _check_craigslist() -> list[dict]:
    """Fetch Craigslist RSS feeds for intent keywords. Returns new signals."""
    try:
        import feedparser
    except ImportError:
        print("[listen] feedparser not installed — install with: uv pip install feedparser")
        return []

    new_signals: list[dict] = []
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row

    for category in CRAIGSLIST_CATEGORIES:
        for keyword in CRAIGSLIST_KEYWORDS:
            url = CRAIGSLIST_BASE.format(category=category, keyword=keyword.replace(" ", "+"))
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    entry_url = entry.get("link", "")
                    title = entry.get("title", "")
                    snippet = entry.get("summary", "")[:500]

                    # Skip if already seen
                    existing = conn.execute(
                        "SELECT 1 FROM signals WHERE url = ?", (entry_url,)
                    ).fetchone()
                    if existing:
                        continue

                    conn.execute(
                        """INSERT OR IGNORE INTO signals (source, url, title, snippet)
                           VALUES (?, ?, ?, ?)""",
                        ("craigslist", entry_url, title, snippet),
                    )
                    conn.commit()
                    new_signals.append({
                        "source": "craigslist",
                        "url": entry_url,
                        "title": title,
                        "snippet": snippet,
                    })
            except Exception as e:
                print(f"[listen] Craigslist error ({category}/{keyword}): {e}")

    conn.close()
    return new_signals


def _check_reddit() -> list[dict]:
    """Check Reddit if credentials are configured."""
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    if not client_id:
        return []

    try:
        import praw
    except ImportError:
        print("[listen] praw not installed — install with: uv pip install praw")
        return []

    new_signals: list[dict] = []
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
            user_agent=os.getenv("REDDIT_USER_AGENT", "squeegeeguy-leadgen/1.0"),
        )

        subreddits = ["Tucson", "TucsonList"]
        keywords = CRAIGSLIST_KEYWORDS

        for sub_name in subreddits:
            subreddit = reddit.subreddit(sub_name)
            for keyword in keywords:
                for post in subreddit.search(keyword, time_filter="day", limit=25):
                    post_url = f"https://reddit.com{post.permalink}"
                    existing = conn.execute(
                        "SELECT 1 FROM signals WHERE url = ?", (post_url,)
                    ).fetchone()
                    if existing:
                        continue

                    conn.execute(
                        """INSERT OR IGNORE INTO signals (source, url, title, snippet)
                           VALUES (?, ?, ?, ?)""",
                        ("reddit", post_url, post.title, post.selftext[:500]),
                    )
                    conn.commit()
                    new_signals.append({
                        "source": "reddit",
                        "url": post_url,
                        "title": post.title,
                    })
    except Exception as e:
        print(f"[listen] Reddit error: {e}")

    conn.close()
    return new_signals


def _alert_urgent(signals: list[dict]) -> None:
    """Send owner alert for signals that look like active service requests."""
    if not DIGEST.owner_email or not signals:
        return

    body_lines = ["New intent signals found — someone may be actively looking:\n"]
    for s in signals:
        body_lines.append(f"[{s['source']}] {s['title']}")
        body_lines.append(f"  {s['url']}\n")

    try:
        send.send_email(
            to=DIGEST.owner_email,
            subject=f"[SqueegeeGuy] {len(signals)} new intent signal(s) found",
            body="\n".join(body_lines),
            add_footer=False,
        )
    except Exception as e:
        print(f"[listen] Alert send failed: {e}")


def check_signals() -> list[dict]:
    """Run all signal checks. Returns list of new signal dicts for the digest."""
    new_signals: list[dict] = []
    new_signals.extend(_check_craigslist())
    new_signals.extend(_check_reddit())

    if new_signals:
        print(f"[listen] Found {len(new_signals)} new signal(s)")
        _alert_urgent(new_signals)
    else:
        print("[listen] No new signals")

    return new_signals


if __name__ == "__main__":
    signals = check_signals()
    for s in signals:
        print(f"  [{s['source']}] {s['title']}")
        print(f"    {s['url']}")
