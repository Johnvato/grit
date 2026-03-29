"""
Hansard scraper — fetches recent parliamentary speeches and statements
from the Australian Parliament House (APH) Hansard RSS feeds.

These provide what politicians *actually said* in parliament, which the AI
can cross-reference against media claims to detect rhetoric vs reality gaps.
"""
import datetime
import time
import sqlite3
import re
from urllib.parse import quote_plus
from email.utils import parsedate_to_datetime

import feedparser


HANSARD_RSS_BASE = "https://www.aph.gov.au/Parliamentary_Business/Hansard/Hansard_Display"

FEED_URLS = {
    "representatives": (
        "https://www.aph.gov.au/Parliamentary_Business/Hansard/"
        "Hansreps_Atom.xml"
    ),
    "senate": (
        "https://www.aph.gov.au/Parliamentary_Business/Hansard/"
        "Hansard_Senate_Atom.xml"
    ),
}

SEARCH_RSS = (
    "https://www.aph.gov.au/api/hansard/search.rss"
    "?q={query}&sort=date-desc&limit=10"
)


def _clean_text(html: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 500:
        cut = text[:500].rfind(". ")
        text = text[:cut + 1] if cut > 200 else text[:500] + "…"
    return text


def fetch_hansard_for_politician(
    conn: sqlite3.Connection,
    politician_id: int,
    name: str,
    days_back: int = 14,
    max_entries: int = 5,
) -> int:
    """Search Hansard RSS for mentions of a specific politician."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=days_back)).isoformat()
    fetched_at = datetime.datetime.utcnow().isoformat()

    query = quote_plus(f'"{name}"')
    url = SEARCH_RSS.format(query=query)

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"    Hansard RSS error for {name}: {e}")
        return 0

    c = conn.cursor()
    count = 0
    for entry in feed.entries[:max_entries]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = entry.get("summary", "")
        content = entry.get("content", [{}])
        full_text = content[0].get("value", summary) if content else summary

        pub_date = ""
        for date_field in ("published", "updated"):
            raw_date = getattr(entry, date_field, None)
            if raw_date:
                try:
                    pub_date = parsedate_to_datetime(raw_date).date().isoformat()
                    break
                except Exception:
                    pass

        if pub_date and pub_date < cutoff:
            continue
        if not title:
            continue

        quote = _clean_text(full_text) if full_text else ""
        if not quote:
            continue

        try:
            c.execute('''
                INSERT OR IGNORE INTO hansard_mentions
                    (politician_id, date, context, quote, url, fetched_at)
                VALUES (?,?,?,?,?,?)
            ''', (politician_id, pub_date, title, quote, link, fetched_at))
            if c.rowcount:
                count += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    return count


def sync_all_hansard(db_path: str = "grit_cache.db", days_back: int = 14):
    """Fetch Hansard mentions for all politicians."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS hansard_mentions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            politician_id   INTEGER,
            date            TEXT,
            context         TEXT,
            quote           TEXT,
            url             TEXT UNIQUE,
            fetched_at      TEXT,
            FOREIGN KEY (politician_id) REFERENCES politicians(id)
        )
    """)
    conn.commit()

    c.execute("SELECT id, name FROM politicians ORDER BY name")
    politicians = c.fetchall()
    print(f"  Scraping Hansard for {len(politicians)} politicians...")

    total = 0
    for i, (pid, name) in enumerate(politicians):
        n = fetch_hansard_for_politician(conn, pid, name, days_back=days_back)
        total += n
        if (i + 1) % 25 == 0:
            print(f"    {i+1}/{len(politicians)} done...")
        time.sleep(0.5)

    conn.close()
    print(f"  Hansard sync complete — {total} new mentions stored.")
