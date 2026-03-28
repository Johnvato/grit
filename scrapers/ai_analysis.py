"""
OpenAI-powered nightly analysis — reads accumulated news + profile data
and generates a heat score, sentiment, and rhetoric vs reality flags.
"""
import datetime
import sqlite3
import json
import os

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


SYSTEM_PROMPT = """You are an independent political integrity analyst for GRIT — 
an Australian political truth engine. You are factual, non-partisan, and evidence-based.
Your job is to assess an Australian politician's current media standing based solely 
on the news headlines provided. You are NOT influenced by political affiliation.

Respond ONLY with valid JSON — no markdown, no explanation outside the JSON."""

USER_PROMPT = """Analyse the following recent news headlines about {name} ({party}, {chamber}):

{headlines}

Provide a JSON object with exactly these keys:
- "sentiment": one of "positive", "negative", "mixed", "neutral"
- "heat_score": integer 1-10 (1=no scrutiny, 10=major controversy/scandal)  
- "summary": 2-3 sentence assessment of their current public standing
- "rhetoric_flags": list of strings, each a specific concern, inconsistency, or integrity issue 
  found in the headlines (empty list if none)
- "positive_notes": list of strings, each a notable achievement or positive mention (empty list if none)"""


def get_openai_client():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        try:
            import tomllib
            with open(".streamlit/secrets.toml", "rb") as f:
                secrets = tomllib.load(f)
            key = secrets.get("api_keys", {}).get("OPENAI_API_KEY", "")
        except Exception:
            pass
    if not key or not HAS_OPENAI:
        return None
    return OpenAI(api_key=key)


def analyse_politician(
    conn: sqlite3.Connection,
    politician_id: int,
    name: str,
    party: str,
    chamber: str,
    force: bool = False,
) -> bool:
    client = get_openai_client()
    if not client:
        return False

    c = conn.cursor()
    today = datetime.date.today().isoformat()

    # Skip if analysed within 24h (unless forced)
    if not force:
        c.execute("SELECT last_analyzed FROM ai_analysis WHERE politician_id = ?", (politician_id,))
        row = c.fetchone()
        if row and row[0] == today:
            return False

    # Get recent news headlines
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
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT.format(
                    name=name, party=party, chamber=chamber, headlines=headlines
                )},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
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
                "rhetoric_flags":  data.get("rhetoric_flags", []),
                "positive_notes":  data.get("positive_notes", []),
            }),
            today,
        ))
        conn.commit()
        return True

    except Exception as e:
        print(f"    AI analysis failed for {name}: {e}")
        return False


def sync_all_analyses(db_path: str = "grit_cache.db"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, name, party, chamber FROM politicians ORDER BY name")
    politicians = c.fetchall()
    print(f"  Running AI analysis for {len(politicians)} politicians...")

    done = 0
    skipped = 0
    for pid, name, party, chamber in politicians:
        result = analyse_politician(conn, pid, name, party or "", chamber or "")
        if result:
            done += 1
        else:
            skipped += 1

    conn.close()
    print(f"  AI analysis complete — {done} analysed, {skipped} skipped (no news / already done today).")
