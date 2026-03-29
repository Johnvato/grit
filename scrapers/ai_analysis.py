"""
Gemini-powered nightly analysis — reads accumulated news and generates
a heat score, sentiment rating, and rhetoric vs reality flags per politician.
Uses Google Gemini Flash (free tier: 1,500 req/day).

Enriched with:
- Source trust scores and political leaning from media_profiles
- Voting record context (attendance, rebellions) from They Vote For You
- Source diversity warnings when one ownership group dominates coverage
- Hansard excerpts (what they actually said in parliament)
"""
import datetime
import sqlite3
import json
import os
import re
import time
from collections import Counter

try:
    from google import genai
    from google.genai import types as genai_types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


SYSTEM_PROMPT = (
    "You are an independent political integrity analyst for Pollygraph — "
    "an Australian political truth engine. You are factual, non-partisan, and evidence-based. "
    "Respond ONLY with valid JSON — no markdown, no explanation outside the JSON."
)

USER_PROMPT = """Analyse the following recent news headlines about {name} ({party}, {chamber}).

Each headline includes a source trust rating (1-10, where 10 = most trustworthy) and the
source's political leaning. Weight your assessment toward higher-trust sources. A claim
repeated only by low-trust or highly partisan outlets should carry less weight than one
confirmed by high-trust or evidence-based outlets.

HEADLINES:
{headlines}
{source_diversity_warning}
VOTING RECORD CONTEXT:
{voting_context}
{hansard_context}
Provide a JSON object with exactly these keys:
- "sentiment": one of "positive", "negative", "mixed", "neutral"
- "heat_score": integer 1-10 — genuine scandal, hypocrisy, or ethical failure (1=none, 10=major scandal). This score should ONLY reflect genuinely negative conduct: corruption, broken promises, misleading the public, conflicts of interest, or personal misconduct. Do NOT penalise politicians for principled dissent, holding the government to account, championing unpopular causes, or attracting controversy by challenging powerful interests — those are signs of integrity, not scandal. Weight claims from high-trust sources more heavily.
- "positive_score": integer 1-10 — integrity and positive contribution (1=none, 10=exceptional). This should reflect genuine achievements, constructive legislation, accountability efforts, principled stands, community advocacy, and evidence of walking the talk. A politician who attracts media attention by challenging the status quo or holding the powerful to account should score HIGH here, not on heat_score. Cross-reference media claims against the voting record context above — if their votes match their rhetoric, that strengthens a positive score. These two scores are INDEPENDENT — a politician can score high on both.
- "summary": 2-3 sentence assessment of their current public standing
- "rhetoric_flags": list of strings — specific concerns, inconsistencies or integrity issues (empty list if none). If the voting record contradicts media claims, flag this.
- "positive_notes": list of strings — notable achievements or genuine positive mentions (empty list if none)
- "source_quality": one of "high", "mixed", "low" — overall quality of the sources behind this assessment

IMPORTANT: Distinguish between "controversial because corrupt/hypocritical" (high heat_score) and "controversial because they challenge the powerful" (high positive_score). A politician who opposes a bill on principle or demands transparency is demonstrating integrity, not generating scandal."""


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


# Cycle through models — each has its own free-tier daily quota
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]
_model_idx = 0


def get_client():
    if not HAS_GEMINI:
        return None
    key = get_gemini_key()
    if not key or key.startswith("your-"):
        return None
    return genai.Client(api_key=key)


def _load_media_trust(conn: sqlite3.Connection) -> dict:
    """Build a lookup from source name → {trust_score, leaning, parent_company}."""
    c = conn.cursor()
    c.execute("SELECT source_name, trust_score, political_leaning, parent_company FROM media_profiles")
    trust_map = {}
    for name, trust, leaning, parent in c.fetchall():
        trust_map[name.lower()] = {
            "trust": trust or 5,
            "leaning": leaning or "Unknown",
            "parent": parent or "Unknown",
        }
    return trust_map


def _match_source_trust(source_name: str, trust_map: dict) -> dict:
    """Fuzzy-match a news source name against media_profiles."""
    key = source_name.lower().strip()
    if key in trust_map:
        return trust_map[key]
    for profile_key, profile in trust_map.items():
        if profile_key in key or key in profile_key:
            return profile
    return {"trust": 5, "leaning": "Unknown", "parent": "Unknown"}


def _build_headlines_with_trust(articles: list, trust_map: dict) -> tuple[str, str]:
    """Format headlines with trust metadata and produce source diversity warning."""
    lines = []
    parent_counts = Counter()
    for headline, source, pub_date in articles:
        info = _match_source_trust(source, trust_map)
        lines.append(
            f"- [{pub_date}] [Trust: {info['trust']}/10, {info['leaning']}] "
            f"{headline} ({source})"
        )
        parent_counts[info["parent"]] += 1

    total = len(articles)
    diversity_warning = ""
    if total >= 3:
        for parent, count in parent_counts.most_common(1):
            pct = count / total * 100
            if pct >= 60 and parent != "Unknown":
                diversity_warning = (
                    f"\nSOURCE DIVERSITY WARNING: {pct:.0f}% of headlines ({count}/{total}) "
                    f"come from {parent}-owned outlets. Weight this concentration accordingly "
                    f"— a claim amplified by a single ownership group is less reliable than "
                    f"one confirmed across independent sources.\n"
                )

    return "\n".join(lines), diversity_warning


def _build_voting_context(conn: sqlite3.Connection, politician_id: int,
                          party: str) -> str:
    """Build voting record summary for the AI to cross-reference."""
    c = conn.cursor()
    c.execute(
        "SELECT votes_attended, votes_possible, rebellions FROM politicians WHERE id = ?",
        (politician_id,)
    )
    row = c.fetchone()
    if not row:
        return "No voting record available."

    attended, possible, rebellions = row
    attendance_pct = (
        f"{100 * attended / possible:.0f}%" if possible and possible > 0 else "unknown"
    )

    # Recent rebellions with division names
    c.execute("""
        SELECT d.name, d.date, v.vote
        FROM votes v
        JOIN divisions d ON d.id = v.division_id
        JOIN (
            SELECT v2.division_id,
                   CASE WHEN SUM(CASE WHEN v2.vote='aye' THEN 1 ELSE 0 END) >
                             SUM(CASE WHEN v2.vote='no'  THEN 1 ELSE 0 END)
                   THEN 'aye' ELSE 'no' END AS party_majority
            FROM votes v2
            JOIN politicians p2 ON p2.id = v2.politician_id
            WHERE p2.party = ?
            GROUP BY v2.division_id
        ) pm ON pm.division_id = v.division_id AND v.vote != pm.party_majority
        WHERE v.politician_id = ?
        ORDER BY d.date DESC
        LIMIT 5
    """, (party, politician_id))
    recent_rebellions = c.fetchall()

    lines = [
        f"Attendance: {attendance_pct} ({attended}/{possible} votes)",
        f"Career rebellions against party: {rebellions}",
    ]
    if recent_rebellions:
        lines.append("Recent rebellions (voted against own party):")
        for div_name, div_date, vote in recent_rebellions:
            lines.append(f"  - {div_date}: {div_name} (voted {vote})")
    else:
        lines.append("No recent rebellions found in synced divisions.")

    return "\n".join(lines)


def _build_hansard_context(conn: sqlite3.Connection, politician_id: int) -> str:
    """Include recent Hansard excerpts if available."""
    c = conn.cursor()
    c.execute("""
        SELECT date, context, quote FROM hansard_mentions
        WHERE politician_id = ?
        ORDER BY date DESC
        LIMIT 5
    """, (politician_id,))
    rows = c.fetchall()
    if not rows:
        return ""
    lines = ["\nRECENT PARLIAMENTARY STATEMENTS (Hansard):"]
    for date, context, quote in rows:
        lines.append(f"- [{date}] {context}: \"{quote}\"")
    lines.append(
        "Use these statements to cross-reference against media claims. "
        "If their words in parliament contradict their media positioning, flag it."
    )
    return "\n".join(lines)


def analyse_politician(
    conn: sqlite3.Connection,
    politician_id: int,
    name: str,
    party: str,
    chamber: str,
    force: bool = False,
) -> bool:
    client = get_client()
    if not client:
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

    # Enrich headlines with source trust data
    trust_map = _load_media_trust(conn)
    headlines, source_diversity_warning = _build_headlines_with_trust(articles, trust_map)
    voting_context = _build_voting_context(conn, politician_id, party)

    # Hansard context (gracefully skip if table doesn't exist yet)
    try:
        hansard_context = _build_hansard_context(conn, politician_id)
    except Exception:
        hansard_context = ""

    prompt_content = USER_PROMPT.format(
        name=name, party=party, chamber=chamber,
        headlines=headlines,
        source_diversity_warning=source_diversity_warning,
        voting_context=voting_context,
        hansard_context=hansard_context,
    )

    global _model_idx
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
                "positive_score":  int(data.get("positive_score", 0)),
                "source_quality":  data.get("source_quality", "mixed"),
            }),
            today,
        ))
        conn.commit()
        return True

    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            _model_idx += 1
            if _model_idx % len(MODELS) == 0:
                print(f"    All models exhausted for today — stopping.")
                return False
            next_model = MODELS[_model_idx % len(MODELS)]
            print(f"    Quota hit — switching to {next_model}")
            try:
                response = client.models.generate_content(
                    model=next_model,
                    contents=prompt_content,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT, temperature=0.2, max_output_tokens=2048,
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
                    "INSERT OR REPLACE INTO ai_analysis (politician_id, sentiment, heat_score, summary, rhetoric_flags, last_analyzed) VALUES (?,?,?,?,?,?)",
                    (politician_id, data.get("sentiment", "neutral"), int(data.get("heat_score", 1)),
                     data.get("summary", ""), json.dumps({
                         "rhetoric_flags": data.get("rhetoric_flags", []),
                         "positive_notes": data.get("positive_notes", []),
                         "positive_score": int(data.get("positive_score", 0)),
                         "source_quality": data.get("source_quality", "mixed"),
                     }), today)
                )
                conn.commit()
                return True
            except Exception as e2:
                print(f"    Analysis failed for {name} (retry): {e2}")
                return False
        print(f"    Analysis failed for {name}: {e}")
        return False


def sync_all_analyses(db_path: str = "grit_cache.db", force: bool = False):
    client = get_client()
    if not client:
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
        result = analyse_politician(conn, pid, name, party or "", chamber or "", force=force)
        if result:
            done += 1
        else:
            skipped += 1

    conn.close()
    print(f"  Analysis complete — {done} analysed, {skipped} skipped.")
