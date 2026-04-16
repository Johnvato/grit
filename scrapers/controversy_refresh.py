"""
Periodic deep-refresh of per-politician controversy & integrity assessments.

Unlike the daily ai_analysis pass (which is news-gated and skips politicians
without recent headlines), this script forces a re-assessment for every
politician using all available context: previous assessment, news, Wikipedia
bio, voting record, and Hansard excerpts.

Designed to run every 3 days via GitHub Actions.
"""

import datetime
import json
import sqlite3
import time

from scrapers.ai_analysis import (
    get_client,
    get_gemini_key,
    MODELS,
    SYSTEM_PROMPT,
    _load_media_trust,
    _build_headlines_with_trust,
    _build_voting_context,
    _build_hansard_context,
    HAS_GEMINI,
)

try:
    from google.genai import types as genai_types
except ImportError:
    genai_types = None

_model_idx = 0

REFRESH_PROMPT = """Re-assess the current controversy and integrity profile for {name} ({party}, {chamber}).

PREVIOUS ASSESSMENT (from {last_analyzed}):
- Heat score: {prev_heat}/10
- Positive score: {prev_positive}/10
- Summary: {prev_summary}
- Flagged concerns: {prev_flags}
- Positive notes: {prev_positives}

CURRENT CONTEXT:
{context_block}

Based on all available evidence, provide a FRESH assessment. If circumstances have
changed since the previous assessment, update accordingly. If nothing material has
changed, you may keep scores similar but still provide a current summary.

Return a JSON object with exactly these keys:
- "sentiment": one of "positive", "negative", "mixed", "neutral"
- "heat_score": integer 1-10 — genuine scandal, hypocrisy, or ethical failure (1=none, 10=major scandal). This score should ONLY reflect genuinely negative conduct: corruption, broken promises, misleading the public, conflicts of interest, or personal misconduct. Do NOT penalise politicians for principled dissent, holding the government to account, championing unpopular causes, or attracting controversy by challenging powerful interests — those are signs of integrity, not scandal.
- "positive_score": integer 1-10 — integrity and positive contribution (1=none, 10=exceptional). This should reflect genuine achievements, constructive legislation, accountability efforts, principled stands, community advocacy, and evidence of walking the talk. A politician who attracts media attention by challenging the status quo or holding the powerful to account should score HIGH here, not on heat_score. Cross-reference media claims against the voting record context — if their votes match their rhetoric, that strengthens a positive score. These two scores are INDEPENDENT — a politician can score high on both.
- "summary": 2-3 sentence assessment of their current public standing
- "rhetoric_flags": list of strings — specific concerns, inconsistencies or integrity issues (empty list if none)
- "positive_notes": list of strings — notable achievements or genuine positive mentions (empty list if none)
- "source_quality": one of "high", "mixed", "low" — overall quality of the sources behind this assessment

IMPORTANT: Distinguish between "controversial because corrupt/hypocritical" (high heat_score) and "controversial because they challenge the powerful" (high positive_score)."""


def _load_previous_assessment(conn, politician_id):
    """Load the existing ai_analysis row for context in the refresh prompt."""
    c = conn.cursor()
    c.execute(
        "SELECT sentiment, heat_score, summary, rhetoric_flags, last_analyzed "
        "FROM ai_analysis WHERE politician_id = ?",
        (politician_id,),
    )
    row = c.fetchone()
    if not row:
        return {
            "last_analyzed": "never",
            "prev_heat": 0,
            "prev_positive": 0,
            "prev_summary": "No previous assessment.",
            "prev_flags": "[]",
            "prev_positives": "[]",
        }

    sentiment, heat, summary, flags_raw, last_analyzed = row
    try:
        flags_data = json.loads(flags_raw or "{}")
    except Exception:
        flags_data = {}

    return {
        "last_analyzed": last_analyzed or "unknown",
        "prev_heat": heat or 0,
        "prev_positive": flags_data.get("positive_score", 0),
        "prev_summary": summary or "No summary.",
        "prev_flags": json.dumps(flags_data.get("rhetoric_flags", [])),
        "prev_positives": json.dumps(flags_data.get("positive_notes", [])),
    }


def _load_bio_context(conn, politician_id):
    """Load Wikipedia bio snippet if available."""
    c = conn.cursor()
    c.execute(
        "SELECT bio_text FROM politician_bio WHERE politician_id = ?",
        (politician_id,),
    )
    row = c.fetchone()
    if row and row[0]:
        bio = row[0][:600]
        return f"\nWIKIPEDIA BIO (excerpt):\n{bio}\n"
    return ""


def _build_context_block(conn, politician_id, party, trust_map):
    """Assemble all available context for the refresh prompt."""
    sections = []

    # Recent news (last 30 days for the refresh — wider window than daily)
    c = conn.cursor()
    cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    c.execute(
        "SELECT headline, source, published_date FROM politician_news "
        "WHERE politician_id = ? AND published_date >= ? "
        "ORDER BY published_date DESC LIMIT 20",
        (politician_id, cutoff),
    )
    articles = c.fetchall()
    if articles:
        headlines, diversity_warn = _build_headlines_with_trust(articles, trust_map)
        sections.append(f"RECENT HEADLINES (last 30 days):\n{headlines}")
        if diversity_warn:
            sections.append(diversity_warn)
    else:
        sections.append("RECENT HEADLINES: None in the last 30 days.")

    # Voting record
    sections.append(f"\nVOTING RECORD:\n{_build_voting_context(conn, politician_id, party)}")

    # Hansard
    try:
        hansard = _build_hansard_context(conn, politician_id)
        if hansard:
            sections.append(hansard)
    except Exception:
        pass

    # Wikipedia bio
    sections.append(_load_bio_context(conn, politician_id))

    return "\n".join(sections)


def refresh_politician(conn, client, politician_id, name, party, chamber, trust_map):
    """Run a forced Gemini re-assessment for a single politician."""
    global _model_idx

    prev = _load_previous_assessment(conn, politician_id)
    context_block = _build_context_block(conn, politician_id, party, trust_map)

    prompt_content = REFRESH_PROMPT.format(
        name=name,
        party=party,
        chamber=chamber,
        context_block=context_block,
        **prev,
    )

    today = datetime.date.today().isoformat()

    try:
        response = client.models.generate_content(
            model=MODELS[_model_idx % len(MODELS)],
            contents=prompt_content,
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                max_output_tokens=2048,
            ),
        )
        raw = response.text.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]
        data = json.loads(raw)
        time.sleep(13)

        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO ai_analysis "
            "(politician_id, sentiment, heat_score, summary, rhetoric_flags, last_analyzed) "
            "VALUES (?,?,?,?,?,?)",
            (
                politician_id,
                data.get("sentiment", "neutral"),
                int(data.get("heat_score", 1)),
                data.get("summary", ""),
                json.dumps({
                    "rhetoric_flags": data.get("rhetoric_flags", []),
                    "positive_notes": data.get("positive_notes", []),
                    "positive_score": int(data.get("positive_score", 0)),
                    "source_quality": data.get("source_quality", "mixed"),
                }),
                today,
            ),
        )
        conn.commit()
        return True

    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            _model_idx += 1
            if _model_idx % len(MODELS) == 0:
                print(f"    All models exhausted — stopping.")
                return False
            next_model = MODELS[_model_idx % len(MODELS)]
            print(f"    Quota hit — switching to {next_model}")
            try:
                response = client.models.generate_content(
                    model=next_model,
                    contents=prompt_content,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        max_output_tokens=2048,
                    ),
                )
                raw = response.text.strip()
                start, end = raw.find("{"), raw.rfind("}") + 1
                if start != -1 and end > start:
                    raw = raw[start:end]
                data = json.loads(raw)
                time.sleep(13)
                c = conn.cursor()
                c.execute(
                    "INSERT OR REPLACE INTO ai_analysis "
                    "(politician_id, sentiment, heat_score, summary, rhetoric_flags, last_analyzed) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        politician_id,
                        data.get("sentiment", "neutral"),
                        int(data.get("heat_score", 1)),
                        data.get("summary", ""),
                        json.dumps({
                            "rhetoric_flags": data.get("rhetoric_flags", []),
                            "positive_notes": data.get("positive_notes", []),
                            "positive_score": int(data.get("positive_score", 0)),
                            "source_quality": data.get("source_quality", "mixed"),
                        }),
                        today,
                    ),
                )
                conn.commit()
                return True
            except Exception as e2:
                print(f"    Refresh failed for {name} (retry): {e2}")
                return False
        print(f"    Refresh failed for {name}: {e}")
        return False


def refresh_all(db_path="grit_cache.db"):
    """Force a full controversy re-assessment for every politician."""
    if not HAS_GEMINI:
        print("  google-genai not installed — skipping controversy refresh.")
        return

    client = get_client()
    if not client:
        print("  Gemini key not configured — skipping controversy refresh.")
        print("  Add GEMINI_API_KEY to environment or .streamlit/secrets.toml")
        return

    conn = sqlite3.connect(db_path)
    trust_map = _load_media_trust(conn)

    c = conn.cursor()
    c.execute("SELECT id, name, party, chamber FROM politicians ORDER BY name")
    politicians = c.fetchall()
    print(f"  Controversy refresh for {len(politicians)} politicians...")

    done = failed = 0
    for pid, name, party, chamber in politicians:
        result = refresh_politician(
            conn, client, pid, name, party or "", chamber or "", trust_map
        )
        if result:
            done += 1
            print(f"    [{done}] {name} — refreshed")
        else:
            failed += 1

    conn.close()
    print(f"  Refresh complete — {done} refreshed, {failed} skipped/failed.")


if __name__ == "__main__":
    refresh_all()
