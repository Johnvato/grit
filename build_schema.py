import sqlite3


def init_db():
    conn = sqlite3.connect("grit_cache.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS politicians (
            ID   TEXT PRIMARY KEY,
            name TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            Bill_No TEXT PRIMARY KEY,
            title   TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media (
            URL   TEXT PRIMARY KEY,
            MP_ID TEXT,
            text  TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("Database built.")


if __name__ == "__main__":
    init_db()
