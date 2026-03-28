"""
Gemini-powered nightly analysis — reads accumulated news and generates
a heat score, sentiment rating, and rhetoric vs reality flags per politician.
Uses Google Gemini Flash (free tier: 1,500 req/day).
"""
import datetime
import sqlite3
import json
import os

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


SYSTEM_PROMPT = (
    "You are an independent political integrity analyst for GRIT — "
    "an Australian political truth engine. You are factual, non-partisan, and evidence-based. "
    "Respond ONLY with valid JSON — no markdown, no explanation outside the JSON."
)

USER_PROMPT = """Analyse the following recent news headlines about {name} ({party}, {chamber}):

{headlines}

Provide a JSON object with exactly these keys:
- "sentiment": one of "positive", "negative", "mixed", "neutral"
- "heat_score": integer 1-10 (1=no scrutiny, 10=major controversy/scandal)
- "summary": 2-3 sentence assessment of their current public standing
- "rhetoric_flags": list of strings — specific concerns, inconsistencies or integrity issues in the headlines (empty list if none)
- "positive_notes": list of strings — notable achievements or positive mentions (empty list if none)"""


def get_gemini_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    try:
        import tomllib
        with open(".streamlit/secrets.toml", "rb") as f:
            secrets = tomllib.load(f)
        return secrets.get("api_keys", {}).get("GEMINI_API_KEY", "")
    except Exception:
        return None


def get_model():
    if not HAS_GEMINI:
        return None
    key = get_gemini_key()
    if not key or key.startswith("your-"):
        return None
    genai.configure(api_key=key)
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
        generation_config={"temperature": 0.2, "max_output_tokens": 600},
    )


def analyse_politician(
    conn: sqlite3.Connection,
    politician_id: int,
    name: str,
    party: str,
    chamber: str,
    force: bool = False,
) -> bool:
    model = get_model()
    if not model:
        return False

    c = conn.cursor()
    today = datetime.date.today().isoformat()

    if not force:
        c.execute("SELECT last_analyzed FROM ai_analysis WHERE politician_id = ?", (politician_id,))
        row = c.fetchone()
        if row and row[0] == today:
            return False

    c.execute('''
        SELECT headline, source, published_date FROM politician_news
        WHERE politician_id = ?
          AND published_date >= ?
        ORDER BY published_date DESC
        LIMIT 15
    ''', (politician_id, (datetime.date.today() - datetime.timedelta(days=14)).isoformat()))
    articles = c.fetchall()

    if not articles:
        return False

    headlines = "\n".join(
        f"- [{row[2]}] {row[0]} ({row[1]})" for row in articles
    )

    try:
        response = model.generate_content(
            USER_PROMPT.format(
                name=name, party=party, chamber=chamber, headlines=headlines
            )
        )
        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        c.execute('''
            INSERT OR REPLACE INTO ai_analysis
                (politician_id, sentiment, heat_score, summary, rhetoric_flags, last_analyzed)
            VALUES (?,?,?,?,?,?)
        ''', (
            politician_id,
            data.get("sentiment", "neutral"),
            int(data.get("heat_score", 1)),
            data.get("summary", ""),
            json.dumps({
                "rhetoric_flags": data.get("rhetoric_flags", []),
                "positive_notes": data.get("positive_notes", []),
            }),
            today,
        ))
        conn.commit()
        return True

    except Exception as e:
        print(f"    Analysis failed for {name}: {e}")
        return False


def sync_all_analyses(db_path: str = "grit_cache.db"):
    model = get_model()
    if not model:
        print("  Gemini key not configured — skipping AI analysis.")
        print("  Add GEMINI_API_KEY to .streamlit/secrets.toml")
        print("  Get a free key at: https://aistudio.google.com/app/apikey")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, name, party, chamber FROM politicians ORDER BY name")
    politicians = c.fetchall()
    print(f"  Running Gemini analysis for {len(politicians)} politicians...")

    done = skipped = 0
    for pid, name, party, chamber in politicians:
        result = analyse_politician(conn, pid, name, party or "", chamber or "")
        if result:
            done += 1
        else:
            skipped += 1

    conn.close()
    print(f"  Analysis complete — {done} analysed, {skipped} skipped.")
