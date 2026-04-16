"""
Periodic deep-refresh of per-politician controversy & integrity assessments.

Unlike the daily ai_analysis pass (which is news-gated and skips politicians
without recent headlines), this script forces a re-assessment using all
available context: previous assessment, news, Wikipedia bio, voting record,
and Hansard excerpts.

Quota strategy (free tier = 20 RPD per model):
  - Round-robins across 4 models (~80 total RPD).
  - Processes politicians in staleness order (oldest last_analyzed first),
    so the queue naturally advances across runs.
  - Stops gracefully when all models are exhausted; the next day's run
    picks up where this one left off.
  - Retries on 429 with backoff before marking a model as spent.
"""

import datetime
import json
import sqlite3
import time

from scrapers.ai_analysis import (
    get_client,
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

REFRESH_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-2.5-flash",
]
REQUESTS_PER_MODEL = 18  # leave 2 buffer per model's 20 RPD
MAX_503_STRIKES = 3       # retire a model after this many consecutive 503s
MAX_RETRIES = 2
BASE_BACKOFF = 16

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
        "SELECT wikipedia_summary FROM politician_bio WHERE politician_id = ?",
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

    sections.append(f"\nVOTING RECORD:\n{_build_voting_context(conn, politician_id, party)}")

    try:
        hansard = _build_hansard_context(conn, politician_id)
        if hansard:
            sections.append(hansard)
    except Exception:
        pass

    sections.append(_load_bio_context(conn, politician_id))

    return "\n".join(sections)


class ModelPool:
    """Round-robin across models, retiring each after REQUESTS_PER_MODEL uses
    or after MAX_503_STRIKES consecutive 503 errors."""

    def __init__(self):
        self._counts = {m: 0 for m in REFRESH_MODELS}
        self._503_strikes = {m: 0 for m in REFRESH_MODELS}
        self._exhausted = set()
        self._idx = 0

    @property
    def all_exhausted(self):
        return len(self._exhausted) == len(REFRESH_MODELS)

    def current(self):
        available = [m for m in REFRESH_MODELS if m not in self._exhausted]
        if not available:
            return None
        return available[self._idx % len(available)]

    def record_success(self, model):
        self._counts[model] += 1
        self._503_strikes[model] = 0
        if self._counts[model] >= REQUESTS_PER_MODEL:
            self._exhausted.add(model)
            print(f"    Model {model} reached {REQUESTS_PER_MODEL} requests — rotating out")
        self._idx += 1

    def mark_exhausted(self, model):
        self._exhausted.add(model)
        print(f"    Model {model} quota exhausted by API — rotating out")

    def record_503(self, model):
        self._503_strikes[model] += 1
        if self._503_strikes[model] >= MAX_503_STRIKES:
            self._exhausted.add(model)
            print(f"    Model {model} unavailable ({MAX_503_STRIKES} consecutive 503s) — rotating out")
            return True
        return False


def _call_gemini(client, model, prompt_content):
    """Call Gemini with retry on 429.  Returns (response, failure) where
    failure is None on success or (kind, detail) with kind in
    'quota' | '503' | 'error'."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt_content,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.2,
                    max_output_tokens=2048,
                ),
            )
            return response, None
        except Exception as e:
            err = str(e)
            is_quota = "429" in err or "RESOURCE_EXHAUSTED" in err
            is_503 = "503" in err or "UNAVAILABLE" in err
            if is_quota and attempt < MAX_RETRIES - 1:
                wait = BASE_BACKOFF * (2 ** attempt)
                print(f"    Rate limited on {model} — waiting {wait}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            if is_503:
                return None, ("503", err)
            return None, ("quota" if is_quota else "error", err)
    return None, ("quota", "max retries")


def refresh_politician(conn, client, pool, politician_id, name, party, chamber, trust_map):
    """Run a forced Gemini re-assessment for a single politician."""
    model = pool.current()
    if not model:
        return False

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

    response, failure = _call_gemini(client, model, prompt_content)

    if failure:
        kind, detail = failure
        if kind == "quota":
            pool.mark_exhausted(model)
        elif kind == "503":
            pool.record_503(model)
        else:
            print(f"    Refresh failed for {name}: {detail[:120]}")
            return False

        next_model = pool.current()
        if not next_model:
            print(f"    All models exhausted — stopping run.")
            return False
        print(f"    Retrying {name} on {next_model}")
        response, failure = _call_gemini(client, next_model, prompt_content)
        if failure:
            if failure[0] == "503":
                pool.record_503(next_model)
            print(f"    Refresh failed for {name}: {failure[1][:120]}")
            return False
        model = next_model

    try:
        raw = response.text.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]
        data = json.loads(raw)
    except Exception as e:
        print(f"    Parse failed for {name}: {e}")
        return False

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

    pool.record_success(model)
    time.sleep(5)
    return True


def refresh_all(db_path="grit_cache.db"):
    """Process politicians in staleness order until quota runs out."""
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
    c.execute("""
        SELECT p.id, p.name, p.party, p.chamber
        FROM politicians p
        LEFT JOIN ai_analysis a ON a.politician_id = p.id
        ORDER BY a.last_analyzed ASC NULLS FIRST, p.name
    """)
    politicians = c.fetchall()

    pool = ModelPool()
    budget = REQUESTS_PER_MODEL * len(REFRESH_MODELS)

    print(f"  {len(politicians)} politicians, processing up to ~{budget} (stalest first)")
    print(f"  Models: {', '.join(REFRESH_MODELS)}")

    done = failed = 0
    for pid, name, party, chamber in politicians:
        if pool.all_exhausted:
            remaining = len(politicians) - done - failed
            print(f"  All models exhausted — {remaining} politicians deferred to next run.")
            break

        result = refresh_politician(
            conn, client, pool, pid, name, party or "", chamber or "", trust_map
        )
        if result:
            done += 1
            print(f"    [{done}] {name} — refreshed")
        else:
            failed += 1
            if pool.all_exhausted:
                remaining = len(politicians) - done - failed
                print(f"  All models exhausted — {remaining} politicians deferred to next run.")
                break

    conn.close()
    print(f"  Refresh complete — {done} refreshed, {failed} failed/skipped.")
    if done > 0:
        days_to_full_cycle = max(1, len(politicians) // done)
        print(f"  At this rate, full cycle takes ~{days_to_full_cycle} days.")


if __name__ == "__main__":
    refresh_all()
