"""
Google News RSS scraper — fetches recent articles for each politician.
"""
import datetime
import time
import sqlite3
from urllib.parse import quote_plus
from email.utils import parsedate_to_datetime

import feedparser


def fetch_news_for_politician(
    conn: sqlite3.Connection,
    politician_id: int,
    name: str,
    days_back: int = 7,
    max_articles: int = 10,
) -> int:
    cutoff = (datetime.date.today() - datetime.timedelta(days=days_back)).isoformat()
    fetched_at = datetime.datetime.utcnow().isoformat()

    query = quote_plus(f'"{name}" australia parliament OR politician OR senate OR minister')
    url = (
        f"https://news.google.com/rss/search"
        f"?q={query}&hl=en-AU&gl=AU&ceid=AU:en"
    )

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"    RSS parse error for {name}: {e}")
        return 0

    c = conn.cursor()
    count = 0
    for entry in feed.entries[:max_articles]:
        headline = entry.get("title", "").strip()
        link     = entry.get("link", "").strip()
        summary  = entry.get("summary", "").strip()
        source   = ""
        if hasattr(entry, "source") and entry.source:
            source = entry.source.get("title", "")

        pub_date = ""
        if hasattr(entry, "published") and entry.published:
            try:
                pub_date = parsedate_to_datetime(entry.published).date().isoformat()
            except Exception:
                pass

        if pub_date and pub_date < cutoff:
            continue
        if not headline or not link:
            continue

        try:
            c.execute('''
                INSERT OR IGNORE INTO politician_news
                    (politician_id, headline, url, source, published_date, summary, fetched_at)
                VALUES (?,?,?,?,?,?,?)
            ''', (politician_id, headline, link, source, pub_date, summary, fetched_at))
            if c.rowcount:
                count += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    return count


def sync_all_news(db_path: str = "grit_cache.db", days_back: int = 7):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, name FROM politicians ORDER BY name")
    politicians = c.fetchall()
    print(f"  Scraping news for {len(politicians)} politicians...")

    total = 0
    for i, (pid, name) in enumerate(politicians):
        n = fetch_news_for_politician(conn, pid, name, days_back=days_back)
        total += n
        if (i + 1) % 25 == 0:
            print(f"    {i+1}/{len(politicians)} done...")
        time.sleep(0.3)

    conn.close()
    print(f"  News sync complete — {total} new articles stored.")
