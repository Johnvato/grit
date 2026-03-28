import sqlite3


def init_db():
    conn = sqlite3.connect("grit_cache.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS politicians (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            party       TEXT,
            electorate  TEXT,
            chamber     TEXT,
            rebellions  INTEGER DEFAULT 0,
            votes_attended INTEGER DEFAULT 0,
            votes_possible INTEGER DEFAULT 0,
            last_synced TEXT
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

    conn.commit()
    conn.close()
    print("Database schema initialised.")


if __name__ == "__main__":
    init_db()
