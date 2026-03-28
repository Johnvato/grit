import sqlite3
import datetime


def sync_daily_data():
    conn = sqlite3.connect("grit_cache.db")
    cursor = conn.cursor()

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # Simulating an API pull of a new politician record
    cursor.execute(
        "INSERT OR REPLACE INTO politicians (ID, name) VALUES (?, ?)",
        ("75", f"Anthony Albanese (Updated {today})")
    )

    conn.commit()
    conn.close()
    print(f"Data synced for {today}.")


if __name__ == "__main__":
    sync_daily_data()
