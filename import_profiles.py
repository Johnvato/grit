"""
Import manually curated politician profiles from CSV into grit_cache.db.
Run this whenever the CSV is updated:
    python3 import_profiles.py
"""
import csv
import sqlite3
import os

CSV_FILES = [
    "data/profiles_southbank.csv",
]


def import_profiles(db_path="grit_cache.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    total = 0
    for csv_path in CSV_FILES:
        if not os.path.exists(csv_path):
            print(f"  Skipping missing file: {csv_path}")
            continue

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute('''
                    INSERT OR REPLACE INTO profiles (
                        name, position_label, political_spectrum, notes,
                        employment_history, media_positive, media_negative,
                        integrity_notes, media_veracity, risk_assessment,
                        funding_info, funding_transparency, funding_risk,
                        active_since, term_end, postal_address
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row.get("Name", "").strip(),
                    row.get("Position", "").strip(),
                    row.get("Political Spectrum", "").strip(),
                    row.get("Notes", "").strip(),
                    row.get("Employment History Highlights", "").strip(),
                    row.get("Media [+]", "").strip(),
                    row.get("Media [-]", "").strip(),
                    row.get("Integrity Scrutiny & Verified Incidents", "").strip(),
                    row.get("Media Veracity Interrogation", "").strip(),
                    row.get("Risk Assessment (Corruption/Conflict)", "").strip(),
                    row.get("Funding Information", "").strip(),
                    row.get("Funding Transparency", "").strip(),
                    row.get("Funding Risk", "").strip(),
                    row.get("Active Since", "").strip(),
                    row.get("Term End / Re-election", "").strip(),
                    row.get("Postal Address", "").strip(),
                ))
                total += 1

    conn.commit()
    conn.close()
    print(f"Imported {total} politician profiles.")


if __name__ == "__main__":
    import_profiles()
