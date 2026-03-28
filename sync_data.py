import sqlite3
import datetime
import os
import time
import requests

from scrapers.news import sync_all_news
from scrapers.wikipedia import sync_all_bios
from scrapers.ai_analysis import sync_all_analyses

TVFY_BASE = "https://theyvoteforyou.org.au/api/v1"


def get_api_key():
    key = os.environ.get("TVFY_API_KEY")
    if key:
        return key
    try:
        import tomllib
        with open(".streamlit/secrets.toml", "rb") as f:
            secrets = tomllib.load(f)
        return secrets["api_keys"]["THEYVOTEFORYOU_API_KEY"]
    except Exception:
        raise RuntimeError(
            "No TVFY API key found. Set TVFY_API_KEY env var or add to .streamlit/secrets.toml"
        )


def tvfy_get(endpoint, params=None, retries=3):
    api_key = get_api_key()
    url = f"{TVFY_BASE}/{endpoint}"
    p = {"key": api_key}
    if params:
        p.update(params)
    for attempt in range(retries):
        try:
            r = requests.get(url, params=p, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def sync_politicians(conn):
    cursor = conn.cursor()
    today = datetime.date.today().isoformat()

    print("  Fetching people from They Vote For You...")
    people = tvfy_get("people.json")

    reps = [p for p in people if p.get("latest_member", {}).get("house") == "representatives"]
    senators = [p for p in people if p.get("latest_member", {}).get("house") == "senate"]
    print(f"  Found {len(reps)} representatives, {len(senators)} senators.")

    for person in reps + senators:
        m = person.get("latest_member", {})
        name_obj = m.get("name", {})
        full_name = f"{name_obj.get('first', '')} {name_obj.get('last', '')}".strip()
        house = m.get("house", "")
        electorate = m.get("electorate", "")
        # For senators, electorate field IS the state name
        state = electorate if house == "senate" else _electorate_to_state(electorate)
        photo_url = f"https://www.openaustralia.org.au/images/mpsL/{person['id']}.jpg"
        cursor.execute('''
            INSERT OR REPLACE INTO politicians
                (id, name, party, electorate, state, chamber, photo_url, last_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            person["id"],
            full_name,
            m.get("party", ""),
            electorate,
            state,
            house,
            photo_url,
            today,
        ))

    conn.commit()
    print(f"  Synced {len(reps) + len(senators)} politicians.")


# Approximate state from electorate name for House of Reps members
_STATE_ELECTORATES = {
    "New South Wales": ["nsw", "new south wales"],
    "Victoria": ["vic", "victoria"],
    "Queensland": ["qld", "queensland"],
    "Western Australia": ["wa", "western australia"],
    "South Australia": ["sa", "south australia"],
    "Tasmania": ["tas", "tasmania"],
    "Australian Capital Territory": ["act", "australian capital territory"],
    "Northern Territory": ["nt", "northern territory"],
}

def _electorate_to_state(electorate: str) -> str:
    """Best-effort state from electorate name — not perfect but useful."""
    el = electorate.lower()
    for state, keywords in _STATE_ELECTORATES.items():
        if any(k in el for k in keywords):
            return state
    return ""


def sync_politician_detail(conn):
    """Pull rebellion/attendance stats for all politicians."""
    cursor = conn.cursor()
    today = datetime.date.today().isoformat()

    cursor.execute("SELECT id FROM politicians")
    ids = [row[0] for row in cursor.fetchall()]
    print(f"  Fetching detail for {len(ids)} politicians...")

    for tvfy_id in ids:
        try:
            detail = tvfy_get(f"people/{tvfy_id}.json")
            cursor.execute('''
                UPDATE politicians
                SET rebellions = ?,
                    votes_attended = ?,
                    votes_possible = ?,
                    last_synced = ?
                WHERE id = ?
            ''', (
                detail.get("rebellions", 0),
                detail.get("votes_attended", 0),
                detail.get("votes_possible", 0),
                today,
                tvfy_id,
            ))
            time.sleep(0.1)
        except Exception as e:
            print(f"    Warning: could not fetch detail for id {tvfy_id}: {e}")

    conn.commit()
    print("  Politician detail sync done.")


def sync_divisions(conn, days_back=30):
    """Pull divisions (votes) for both chambers."""
    cursor = conn.cursor()
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=days_back)).isoformat()
    end = today.isoformat()

    all_divisions = []
    for house in ("representatives", "senate"):
        print(f"  Fetching {house} divisions from {start} to {end}...")
        divs = tvfy_get("divisions.json", {
            "house": house,
            "start_date": start,
            "end_date": end,
        })
        all_divisions.extend(divs)
    divisions = all_divisions
    print(f"  Found {len(divisions)} divisions total.")

    for div in divisions:
        cursor.execute('''
            INSERT OR REPLACE INTO divisions
                (id, house, name, date, number, clock_time,
                 aye_votes, no_votes, possible_turnout, rebellions, last_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            div["id"],
            div.get("house", ""),
            div.get("name", ""),
            div.get("date", ""),
            div.get("number", 0),
            div.get("clock_time"),
            div.get("aye_votes", 0),
            div.get("no_votes", 0),
            div.get("possible_turnout", 0),
            div.get("rebellions", 0),
            end,
        ))

    conn.commit()

    sync_division_detail(conn, [d["id"] for d in divisions])


def sync_division_detail(conn, division_ids):
    """Pull full vote breakdown for each division."""
    cursor = conn.cursor()
    today = datetime.date.today().isoformat()

    print(f"  Fetching vote detail for {len(division_ids)} divisions...")
    for div_id in division_ids:
        try:
            detail = tvfy_get(f"divisions/{div_id}.json")

            # Update summary
            cursor.execute('''
                UPDATE divisions SET summary = ?, last_synced = ? WHERE id = ?
            ''', (detail.get("summary", ""), today, div_id))

            # Individual votes
            for v in detail.get("votes", []):
                member = v.get("member", {})
                pid = member.get("person", {}).get("id")   # person.id matches politicians table
                vote_val = v.get("vote", "")
                if pid:
                    cursor.execute('''
                        INSERT OR REPLACE INTO votes (division_id, politician_id, vote)
                        VALUES (?, ?, ?)
                    ''', (div_id, pid, vote_val))

            # Linked bills
            for bill in detail.get("bills", []):
                bill_id = str(bill.get("id", ""))
                if bill_id:
                    cursor.execute('''
                        INSERT OR IGNORE INTO bills (id, title, url)
                        VALUES (?, ?, ?)
                    ''', (bill_id, bill.get("title", ""), bill.get("url", "")))
                    cursor.execute('''
                        INSERT OR IGNORE INTO division_bills (division_id, bill_id)
                        VALUES (?, ?)
                    ''', (div_id, bill_id))

            time.sleep(0.1)
        except Exception as e:
            print(f"    Warning: could not fetch detail for division {div_id}: {e}")

    conn.commit()
    print("  Division detail sync done.")


def sync_daily_data():
    print(f"Starting sync — {datetime.datetime.now().isoformat()}")
    conn = sqlite3.connect("grit_cache.db")

    try:
        sync_politicians(conn)
        sync_politician_detail(conn)
        sync_divisions(conn, days_back=30)
    finally:
        conn.close()

    print("Scraping news...")
    sync_all_news(days_back=7)

    print("Fetching Wikipedia bios...")
    sync_all_bios()

    print("Running AI analysis...")
    sync_all_analyses()

    print("Sync complete.")


if __name__ == "__main__":
    sync_daily_data()
