import sqlite3
import csv
import io
import requests


def init_db():
    conn = sqlite3.connect("grit_cache.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS politicians (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            party       TEXT,
            electorate  TEXT,
            state       TEXT,
            chamber     TEXT,
            photo_url   TEXT,
            rebellions  INTEGER DEFAULT 0,
            votes_attended INTEGER DEFAULT 0,
            votes_possible INTEGER DEFAULT 0,
            last_synced TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            name                TEXT PRIMARY KEY,
            position_label      TEXT,
            political_spectrum  TEXT,
            notes               TEXT,
            employment_history  TEXT,
            media_positive      TEXT,
            media_negative      TEXT,
            integrity_notes     TEXT,
            media_veracity      TEXT,
            risk_assessment     TEXT,
            funding_info        TEXT,
            funding_transparency TEXT,
            funding_risk        TEXT,
            active_since        TEXT,
            term_end            TEXT,
            postal_address      TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS divisions (
            id              INTEGER PRIMARY KEY,
            house           TEXT,
            name            TEXT,
            date            TEXT,
            number          INTEGER,
            clock_time      TEXT,
            aye_votes       INTEGER,
            no_votes        INTEGER,
            possible_turnout INTEGER,
            rebellions      INTEGER,
            summary         TEXT,
            last_synced     TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            division_id     INTEGER,
            politician_id   INTEGER,
            vote            TEXT,
            PRIMARY KEY (division_id, politician_id),
            FOREIGN KEY (division_id)   REFERENCES divisions(id),
            FOREIGN KEY (politician_id) REFERENCES politicians(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id      TEXT PRIMARY KEY,
            title   TEXT,
            url     TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS division_bills (
            division_id INTEGER,
            bill_id     TEXT,
            PRIMARY KEY (division_id, bill_id),
            FOREIGN KEY (division_id) REFERENCES divisions(id),
            FOREIGN KEY (bill_id)     REFERENCES bills(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media (
            url     TEXT PRIMARY KEY,
            mp_id   INTEGER,
            text    TEXT,
            FOREIGN KEY (mp_id) REFERENCES politicians(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS postcode_electorates (
            postcode    TEXT,
            electorate  TEXT,
            PRIMARY KEY (postcode, electorate)
        )
    ''')

    # Safe migrations for existing DBs
    existing_cols = [r[1] for r in cursor.execute("PRAGMA table_info(politicians)").fetchall()]
    for col, defn in [
        ("photo_url", "TEXT"),
        ("state",     "TEXT"),
    ]:
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE politicians ADD COLUMN {col} {defn}")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS polling_places (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            division    TEXT,
            state       TEXT,
            name        TEXT,
            suburb      TEXT,
            postcode    TEXT,
            lat         REAL,
            lng         REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS electorate_margins (
            division        TEXT PRIMARY KEY,
            state           TEXT,
            winning_party   TEXT,
            alp_pct         REAL,
            coalition_pct   REAL,
            margin_pct      REAL,
            margin_type     TEXT,
            swing           REAL,
            total_votes     INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS politician_news (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            politician_id   INTEGER,
            headline        TEXT,
            url             TEXT UNIQUE,
            source          TEXT,
            published_date  TEXT,
            summary         TEXT,
            fetched_at      TEXT,
            FOREIGN KEY (politician_id) REFERENCES politicians(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS politician_bio (
            politician_id       INTEGER PRIMARY KEY,
            wikipedia_summary   TEXT,
            wikipedia_url       TEXT,
            offices_held        TEXT,
            last_updated        TEXT,
            FOREIGN KEY (politician_id) REFERENCES politicians(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_analysis (
            politician_id   INTEGER PRIMARY KEY,
            sentiment       TEXT,
            heat_score      INTEGER,
            summary         TEXT,
            rhetoric_flags  TEXT,
            last_analyzed   TEXT,
            FOREIGN KEY (politician_id) REFERENCES politicians(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promises (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            party           TEXT    NOT NULL,
            category        TEXT    NOT NULL,
            promise         TEXT    NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'Not Started',
            evidence        TEXT,
            scrutiny        TEXT,
            scrutiny_source TEXT,
            source_url      TEXT,
            added_date      TEXT,
            updated_date    TEXT
        )
    ''')

    # Safe migration for existing DBs
    _prom_cols = [r[1] for r in cursor.execute("PRAGMA table_info(promises)").fetchall()]
    for _col, _defn in [("scrutiny", "TEXT"), ("scrutiny_source", "TEXT")]:
        if _col not in _prom_cols:
            cursor.execute(f"ALTER TABLE promises ADD COLUMN {_col} {_defn}")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS controversial_bills (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT    NOT NULL,
            short_name      TEXT,
            category        TEXT    NOT NULL,
            year            INTEGER,
            status          TEXT,
            official_purpose TEXT,
            hidden_impact   TEXT,
            who_benefits    TEXT,
            who_loses       TEXT,
            key_provisions  TEXT,
            criticism       TEXT,
            criticism_source TEXT,
            defence         TEXT,
            source_url      TEXT,
            added_date      TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS revolving_door (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT    NOT NULL,
            party               TEXT,
            last_office         TEXT,
            left_office_year    INTEGER,
            post_office_role    TEXT,
            employer            TEXT,
            sector              TEXT,
            conflict_summary    TEXT,
            portfolio_overlap   TEXT,
            cooling_off_months  INTEGER,
            source_url          TEXT,
            added_date          TEXT
        )
    ''')

    cursor.execute('''
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
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media_profiles (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name         TEXT    NOT NULL UNIQUE,
            owner               TEXT,
            parent_company      TEXT,
            funding_model       TEXT,
            political_leaning   TEXT,
            trust_score         INTEGER,
            trust_method        TEXT,
            ownership_notes     TEXT,
            political_interests TEXT,
            source_url          TEXT,
            added_date          TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("Database schema initialised.")
    sync_aec_data()


AEC_POLLING_URL = "https://results.aec.gov.au/31496/Website/Downloads/GeneralPollingPlacesDownload-31496.csv"
AEC_TPP_URL     = "https://results.aec.gov.au/31496/Website/Downloads/HouseTppByDivisionDownload-31496.csv"


def margin_type(pct: float) -> str:
    if pct < 2:   return "Highly Marginal"
    if pct < 6:   return "Marginal"
    if pct < 10:  return "Fairly Safe"
    return "Safe"


def sync_aec_data():
    """Download AEC polling places + TPP results and populate reference tables."""
    conn = sqlite3.connect("grit_cache.db")
    c = conn.cursor()

    # ── Polling places (postcode→electorate + coordinates) ─────────────────
    try:
        print("Syncing AEC polling places...")
        r = requests.get(AEC_POLLING_URL, timeout=30)
        r.raise_for_status()
        rows = list(csv.DictReader(r.text.splitlines()[1:]))

        c.execute("DELETE FROM polling_places")
        postcode_map = {}
        for row in rows:
            pc  = row.get("PremisesPostCode", "").strip()
            div = row.get("DivisionNm", "").strip()
            lat = row.get("Latitude", "").strip()
            lng = row.get("Longitude", "").strip()
            if not (lat and lng and div):
                continue
            try:
                c.execute('''
                    INSERT INTO polling_places (division, state, name, suburb, postcode, lat, lng)
                    VALUES (?,?,?,?,?,?,?)
                ''', (
                    div,
                    row.get("State", "").strip(),
                    row.get("PollingPlaceNm", "").strip(),
                    row.get("PremisesSuburb", "").strip(),
                    pc,
                    float(lat), float(lng),
                ))
                if pc and div:
                    postcode_map.setdefault(pc, set()).add(div)
            except (ValueError, Exception):
                continue

        for pc, divs in postcode_map.items():
            for div in divs:
                c.execute("INSERT OR IGNORE INTO postcode_electorates VALUES (?,?)", (pc, div))

        conn.commit()
        print(f"  {len(rows)} polling places loaded, {sum(len(v) for v in postcode_map.values())} postcode mappings.")
    except Exception as e:
        print(f"  Warning: polling places sync failed: {e}")

    # ── TPP margins ────────────────────────────────────────────────────────
    try:
        print("Syncing AEC election margins...")
        r = requests.get(AEC_TPP_URL, timeout=30)
        r.raise_for_status()
        rows = list(csv.DictReader(r.text.splitlines()[1:]))

        c.execute("DELETE FROM electorate_margins")
        for row in rows:
            alp_pct  = float(row.get("Australian Labor Party Percentage", 0) or 0)
            coal_pct = float(row.get("Liberal/National Coalition Percentage", 0) or 0)
            winner   = row.get("PartyAb", "").strip()
            win_pct  = max(alp_pct, coal_pct)
            margin   = round(win_pct - 50, 2)
            c.execute('''
                INSERT OR REPLACE INTO electorate_margins
                    (division, state, winning_party, alp_pct, coalition_pct,
                     margin_pct, margin_type, swing, total_votes)
                VALUES (?,?,?,?,?,?,?,?,?)
            ''', (
                row.get("DivisionNm", "").strip(),
                row.get("StateAb", "").strip(),
                winner,
                alp_pct, coal_pct, margin,
                margin_type(margin),
                float(row.get("Swing", 0) or 0),
                int(row.get("TotalVotes", 0) or 0),
            ))
        conn.commit()
        print(f"  {len(rows)} electorate margins loaded.")
    except Exception as e:
        print(f"  Warning: margins sync failed: {e}")

    conn.close()


if __name__ == "__main__":
    init_db()
