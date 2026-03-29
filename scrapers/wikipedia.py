"""
Wikipedia scraper — pulls biographical summaries for politicians.
"""
import datetime
import time
import sqlite3
import json
import requests

WIKI_SEARCH = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
HEADERS = {"User-Agent": "Pollygraph/1.0 (https://github.com/Johnvato/grit)"}


def search_wikipedia(name: str) -> tuple[str, str] | tuple[None, None]:
    """Return (article_title, page_url) or (None, None)."""
    try:
        r = requests.get(WIKI_SEARCH, params={
            "action": "query",
            "list": "search",
            "srsearch": f"{name} Australian politician",
            "srlimit": 3,
            "format": "json",
        }, headers=HEADERS, timeout=10)
        results = r.json().get("query", {}).get("search", [])
        if not results:
            return None, None
        title = results[0]["title"]
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        return title, url
    except Exception:
        return None, None


def fetch_wikipedia_summary(title: str) -> str:
    """Return the plain-text extract for a Wikipedia article."""
    try:
        r = requests.get(
            WIKI_SUMMARY.format(title=title.replace(" ", "_")),
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            return r.json().get("extract", "")
    except Exception:
        pass
    return ""


def sync_politician_bio(
    conn: sqlite3.Connection,
    politician_id: int,
    name: str,
    offices_json: str = "[]",
) -> bool:
    c = conn.cursor()
    today = datetime.date.today().isoformat()

    # Skip if recently updated (within 7 days)
    c.execute("SELECT last_updated FROM politician_bio WHERE politician_id = ?", (politician_id,))
    row = c.fetchone()
    if row and row[0] and row[0] >= (datetime.date.today() - datetime.timedelta(days=7)).isoformat():
        return False

    title, url = search_wikipedia(name)
    summary = fetch_wikipedia_summary(title) if title else ""

    c.execute('''
        INSERT OR REPLACE INTO politician_bio
            (politician_id, wikipedia_summary, wikipedia_url, offices_held, last_updated)
        VALUES (?,?,?,?,?)
    ''', (politician_id, summary, url or "", offices_json, today))
    conn.commit()
    return bool(summary)


def sync_all_bios(db_path: str = "grit_cache.db"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, name FROM politicians ORDER BY name")
    politicians = c.fetchall()
    print(f"  Fetching Wikipedia bios for {len(politicians)} politicians...")

    found = 0
    for i, (pid, name) in enumerate(politicians):
        updated = sync_politician_bio(conn, pid, name)
        if updated:
            found += 1
        if (i + 1) % 25 == 0:
            print(f"    {i+1}/{len(politicians)} done...")
        time.sleep(0.2)

    conn.close()
    print(f"  Bio sync complete — {found} summaries updated.")
