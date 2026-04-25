import streamlit as st
import sqlite3
import pandas as pd
import datetime
import folium
from streamlit_folium import st_folium
import requests as _req_geo
import math as _math_geo
import base64 as _b64

st.set_page_config(page_title="Pollygraph", layout="wide", page_icon="assets/parrot_icon.png")

# ── Theme-aware logo helper ───────────────────────────────────────────────────
@st.cache_data
def _logo_b64(path: str) -> str:
    with open(path, "rb") as f:
        return _b64.b64encode(f.read()).decode()

def _theme_logo(width: int = 280):
    dark = _logo_b64("assets/logo_dark_bg.png")
    light = _logo_b64("assets/logo_light_bg.png")
    st.markdown(
        f'<picture>'
        f'<source srcset="data:image/png;base64,{dark}" media="(prefers-color-scheme: dark)">'
        f'<img src="data:image/png;base64,{light}" width="{width}" style="max-width:100%">'
        f'</picture>',
        unsafe_allow_html=True,
    )

# ── Password gate ─────────────────────────────────────────────────────────────
def _check_password():
    correct = st.secrets.get("password", "")
    if not correct:
        return True
    if st.session_state.get("authenticated"):
        return True
    st.markdown(
        '<style>'
        '#_pw-container { max-width: 320px; margin: 0 auto; }'
        '[data-testid="stVerticalBlock"] { align-items: center; }'
        '</style>',
        unsafe_allow_html=True,
    )
    _theme_logo(260)
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        pwd = st.text_input("Enter password to continue", type="password", key="_pw")
        if pwd and pwd == correct:
            st.session_state.authenticated = True
            st.rerun()
        elif pwd:
            st.error("Incorrect password.")
    st.stop()

_check_password()

st.markdown("""
<style>
/* Faint border on all Streamlit text inputs, selects, and textareas for light-mode contrast */
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div {
    border: 1px solid rgba(0, 0, 0, 0.15) !important;
    border-radius: 6px;
}
</style>
""", unsafe_allow_html=True)

DB = "grit_cache.db"

# Ensure all tables exist (idempotent — safe to run every time)
from build_schema import init_db as _init_db
_init_db()

# ── Comparison state ───────────────────────────────────────────────────────────
if "compare_ids" not in st.session_state:
    st.session_state.compare_ids = []


def _compare_has(pid):
    return pid in st.session_state.get("compare_ids", [])


def _compare_add(pid):
    ids = st.session_state.get("compare_ids", [])
    if pid not in ids:
        ids.append(pid)
    st.session_state.compare_ids = ids


def _compare_remove(pid):
    ids = st.session_state.get("compare_ids", [])
    if pid in ids:
        ids.remove(pid)
    st.session_state.compare_ids = ids

ELECTION_DATE_APPROX = True
NEXT_ELECTION = datetime.date(2028, 5, 6)
LAST_ELECTION = datetime.date(2025, 5, 3)

RISK_COLOURS = {
    "High":     "#e94560",
    "Moderate": "#f5a623",
    "Low":      "#27ae60",
}


def query(sql, params=()):
    try:
        with sqlite3.connect(DB, check_same_thread=False) as _conn:
            return pd.read_sql_query(sql, _conn, params=params)
    except Exception:
        return pd.DataFrame()


def days_until(target):
    return (target - datetime.date.today()).days


def postcode_to_state(postcode: str) -> str | None:
    try:
        pc = int(postcode.strip())
    except ValueError:
        return None
    if 200 <= pc <= 299 or 2600 <= pc <= 2618 or 2900 <= pc <= 2920:
        return "Australian Capital Territory"
    if 1000 <= pc <= 1999 or 2000 <= pc <= 2599 or 2619 <= pc <= 2899 or 2921 <= pc <= 2999:
        return "New South Wales"
    if 3000 <= pc <= 3999 or 8000 <= pc <= 8999:
        return "Victoria"
    if 4000 <= pc <= 4999 or 9000 <= pc <= 9999:
        return "Queensland"
    if 5000 <= pc <= 5999:
        return "South Australia"
    if 6000 <= pc <= 6999:
        return "Western Australia"
    if 7000 <= pc <= 7999:
        return "Tasmania"
    if 800 <= pc <= 999:
        return "Northern Territory"
    return None


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = _math_geo.radians(lat2 - lat1)
    dlon = _math_geo.radians(lon2 - lon1)
    a = (_math_geo.sin(dlat / 2) ** 2 +
         _math_geo.cos(_math_geo.radians(lat1)) *
         _math_geo.cos(_math_geo.radians(lat2)) *
         _math_geo.sin(dlon / 2) ** 2)
    return R * 2 * _math_geo.atan2(_math_geo.sqrt(a), _math_geo.sqrt(1 - a))



def risk_badge(risk_text: str) -> str:
    for level, colour in RISK_COLOURS.items():
        if level.lower() in risk_text.lower():
            return f'<span style="background:{colour};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{level} Risk</span>'
    return ""


MARGIN_COLOURS = {
    "Highly Marginal": "#e94560",
    "Marginal":        "#f5a623",
    "Fairly Safe":     "#3498db",
    "Safe":            "#27ae60",
}

PARTY_COLOURS = {
    "ALP": "#e53935",
    "LNP": "#1565c0", "LP": "#1565c0", "NP": "#1565c0",
    "GRN": "#2e7d32",
    "IND": "#8e24aa",
}


def electorate_card(electorate: str):
    """Show margin classification + interactive map for an electorate."""
    margin_df = query(
        "SELECT * FROM electorate_margins WHERE division = ?", (electorate,)
    )
    places_df = query(
        "SELECT lat, lng, name, suburb FROM polling_places WHERE division = ? AND lat IS NOT NULL",
        (electorate,)
    )

    if margin_df.empty and places_df.empty:
        return

    st.markdown(f"#### Electorate: {electorate}")
    col_margin, col_map = st.columns([1, 2])

    with col_margin:
        if not margin_df.empty:
            m = margin_df.iloc[0]
            mtype  = m["margin_type"]
            colour = MARGIN_COLOURS.get(mtype, "#aaa")
            party  = m["winning_party"]
            p_col  = PARTY_COLOURS.get(party, "#555")

            margin_tip = (
                "The margin is the gap between the winning candidate and 50%. "
                "A larger margin means the seat is safer for the incumbent party."
            )
            mtype_tip = {
                "Highly Marginal": "Under 2% margin — could change hands easily at the next election",
                "Marginal": "2–6% margin — competitive seat that requires active campaigning to hold",
                "Fairly Safe": "6–10% margin — the incumbent party has a solid but not unassailable lead",
                "Safe": "Over 10% margin — very unlikely to change hands without a major swing",
            }.get(mtype, "")
            party_tip = f"The party that won this electorate on a two-party-preferred basis in 2025"
            alp_tip = "ALP's share of the two-party-preferred vote — the final count after preferences are distributed"
            coal_tip = "Coalition's share of the two-party-preferred vote — the final count after preferences are distributed"
            swing_tip = (
                "The change in two-party-preferred vote share compared to the previous election. "
                "Positive means a swing toward the winning party; negative means a swing away."
            )
            votes_tip = "Total formal votes counted in this electorate at the 2025 federal election"

            st.markdown(
                f"""
                <div style="background:#1a1a2e;border-radius:10px;padding:16px;margin-bottom:8px">
                  <div style="color:#aaa;font-size:12px;text-transform:uppercase;letter-spacing:1px">
                    2025 Result
                  </div>
                  <div style="display:flex;align-items:center;gap:10px;margin:8px 0">
                    <span title="{party_tip}" style="background:{p_col};color:#fff;padding:3px 10px;
                                 border-radius:4px;font-weight:700;font-size:14px;cursor:help">{party}</span>
                    <span title="{mtype_tip}" style="background:{colour};color:#fff;padding:3px 10px;
                                 border-radius:4px;font-weight:600;font-size:13px;cursor:help">{mtype}</span>
                  </div>
                  <div title="{margin_tip}" style="color:#fff;font-size:28px;font-weight:700;line-height:1;cursor:help">
                    {m['margin_pct']:.1f}%
                  </div>
                  <div style="color:#aaa;font-size:12px">margin</div>
                  <hr style="border-color:#333;margin:10px 0">
                  <div style="color:#ddd;font-size:13px">
                    <span title="{alp_tip}" style="cursor:help">ALP: {m['alp_pct']:.1f}%</span>
                    &nbsp;|&nbsp;
                    <span title="{coal_tip}" style="cursor:help">Coalition: {m['coalition_pct']:.1f}%</span>
                  </div>
                  <div style="color:#aaa;font-size:12px">
                    <span title="{swing_tip}" style="cursor:help">Swing: {m['swing']:+.1f}%</span>
                    &nbsp;|&nbsp;
                    <span title="{votes_tip}" style="cursor:help">{int(m['total_votes']):,} votes</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_map:
        if not places_df.empty:
            centre_lat = places_df["lat"].mean()
            centre_lng = places_df["lng"].mean()
            party      = margin_df.iloc[0]["winning_party"] if not margin_df.empty else "IND"
            tile_colour = PARTY_COLOURS.get(party, "#555")

            m_map = folium.Map(
                location=[centre_lat, centre_lng],
                zoom_start=10,
                tiles="CartoDB positron",
            )
            for _, p in places_df.iterrows():
                folium.CircleMarker(
                    location=[p["lat"], p["lng"]],
                    radius=5,
                    color=tile_colour,
                    fill=True,
                    fill_color=tile_colour,
                    fill_opacity=0.7,
                    tooltip=f"{p['name']} — {p['suburb']}",
                ).add_to(m_map)

            st_folium(m_map, height=280, width=500, returned_objects=[])
            st.caption(
                f"{len(places_df)} polling places shown. "
                f"[View AEC boundary map →](https://electorate.aec.gov.au/)"
            )


def bipolar_bar(controversy: int, positive: int, compact: bool = False) -> str:
    """
    Bipolar bar centred on a midpoint.
    Red extends LEFT (controversy/heat), green extends RIGHT (positive).
    Both are independent 1-10 scales.
    Empty bar shown when both are zero (no AI data yet).
    """
    height = "7px" if compact else "9px"
    font   = "10px" if compact else "11px"
    c_pct  = max(0, min(100, (controversy or 0) * 10))
    p_pct  = max(0, min(100, (positive  or 0) * 10))
    no_data = controversy == 0 and positive == 0

    # Labels row — only shown when there's data
    if no_data:
        labels = (
            f'<div style="font-size:{font};color:#444;margin-top:2px;font-style:italic">'
            f'no AI data</div>'
        )
    else:
        left_label  = f'<span style="color:#e74c3c">&#8722;&nbsp;{controversy}/10</span>' if controversy else '<span></span>'
        right_label = f'<span style="color:#27ae60">&#43;&nbsp;{positive}/10</span>'       if positive  else '<span></span>'
        labels = (
            f'<div style="display:flex;justify-content:space-between;'
            f'font-size:{font};margin-top:2px">'
            f'{left_label}{right_label}</div>'
        )

    return f"""
<div style="margin:4px 0 1px 0">
  <div style="display:flex;height:{height};border-radius:4px;overflow:hidden;background:#222">
    <!-- left half: red grows rightward from left edge toward centre -->
    <div style="flex:1;display:flex;justify-content:flex-end;background:#222">
      <div style="width:{c_pct}%;height:100%;background:linear-gradient(to left,#e74c3c,#7b1a1a)"></div>
    </div>
    <!-- centre line -->
    <div style="width:2px;background:#444;flex-shrink:0"></div>
    <!-- right half: green grows leftward from right edge toward centre -->
    <div style="flex:1;background:#222">
      <div style="width:{p_pct}%;height:100%;background:linear-gradient(to right,#27ae60,#1a5c36)"></div>
    </div>
  </div>
  {labels}
</div>"""


def heat_badge(score: int) -> str:
    """Legacy single-score badge used in the AI analysis section."""
    HEAT_COLOURS = ["#27ae60","#2ecc71","#f1c40f","#f39c12","#e67e22","#e74c3c","#c0392b","#922b21","#7b241c","#641e16"]
    score = max(1, min(10, score))
    colour = HEAT_COLOURS[score - 1]
    label = ["Very Low","Low","Low-Mod","Moderate","Mod-High","High","High","Very High","Very High","Extreme"][score - 1]
    return f'<span style="background:{colour};color:#fff;padding:2px 10px;border-radius:4px;font-size:12px;font-weight:700">{score}/10 — {label}</span>'


def ai_analysis_section(politician_id: int):
    ai = query("SELECT * FROM ai_analysis WHERE politician_id = ?", (politician_id,))
    if ai.empty:
        return
    a = ai.iloc[0]
    flags_raw = a.get("rhetoric_flags") or "{}"
    try:
        import json
        flags_data = json.loads(flags_raw)
        rhetoric_flags = flags_data.get("rhetoric_flags", [])
        positive_notes = flags_data.get("positive_notes", [])
    except Exception:
        rhetoric_flags, positive_notes = [], []

    pos_score = flags_data.get("positive_score", 0)
    source_quality = flags_data.get("source_quality", "")

    st.markdown("**AI Analysis** *(updated every few days)*")
    st.markdown(
        bipolar_bar(int(a["heat_score"] or 0), pos_score),
        unsafe_allow_html=True,
    )
    cols = st.columns([2, 1])
    with cols[0]:
        st.markdown(a["summary"] or "")
    with cols[1]:
        sq_colours = {"high": "#27ae60", "mixed": "#f39c12", "low": "#e74c3c"}
        sq_label = source_quality.capitalize() if source_quality else ""
        sq_html = (
            f' · Source quality: <span style="color:{sq_colours.get(source_quality, "#888")}'
            f'">{sq_label}</span>'
        ) if sq_label else ""
        st.markdown(
            f'<span style="font-size:12px;color:#888">Sentiment: {a["sentiment"] or "neutral"}'
            f'{sq_html}</span>',
            unsafe_allow_html=True,
        )

    if rhetoric_flags:
        st.markdown("**Flagged concerns:**")
        for flag in rhetoric_flags:
            st.markdown(f"- {flag}")
    if positive_notes:
        st.markdown("**Positive notes:**")
        for note in positive_notes:
            st.markdown(f"- {note}")
    st.caption(f"Last analysed: {a['last_analyzed'] or '—'}")


def news_section(politician_id: int, limit: int = 8):
    news = query('''
        SELECT headline, url, source, published_date
        FROM politician_news
        WHERE politician_id = ?
        ORDER BY published_date DESC, id DESC
        LIMIT ?
    ''', (politician_id, limit))
    if news.empty:
        return
    st.markdown("**Recent news:**")
    for _, row in news.iterrows():
        date = row["published_date"] or ""
        source = row["source"] or ""
        st.markdown(
            f'<div style="margin:4px 0;font-size:13px">'
            f'<a href="{row["url"]}" target="_blank">{row["headline"]}</a>'
            f'<span style="color:#888;font-size:11px"> — {source} {date}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def voting_record_section(politician_id: int, party: str, chamber: str):
    """Rebellions + recent attendance breakdown inside the profile expander."""
    # Career rebellion count from TVFY API (covers all divisions, not just synced ones)
    career_row = query("SELECT rebellions FROM politicians WHERE id = ?", (politician_id,))
    career_total = int(career_row.iloc[0]["rebellions"]) if not career_row.empty else 0

    # ── Rebellions: votes where politician differed from party majority ──────
    rebellions_df = query("""
        SELECT d.date, d.name AS division, v.vote AS my_vote,
               d.house, d.number,
               (SELECT CASE
                    WHEN SUM(CASE WHEN v2.vote='aye' THEN 1 ELSE 0 END) >
                         SUM(CASE WHEN v2.vote='no'  THEN 1 ELSE 0 END)
                    THEN 'aye' ELSE 'no' END
                FROM votes v2
                JOIN politicians p2 ON p2.id = v2.politician_id
                WHERE v2.division_id = v.division_id
                  AND p2.party = ?) AS party_majority
        FROM votes v
        JOIN divisions d ON d.id = v.division_id
        WHERE v.politician_id = ?
        ORDER BY d.date DESC
    """, (party, politician_id))

    if not rebellions_df.empty:
        reb = rebellions_df[rebellions_df["my_vote"] != rebellions_df["party_majority"]]
        recent = rebellions_df.head(30)
        attended_ids = set(
            query("SELECT division_id FROM votes WHERE politician_id = ?", (politician_id,))
            ["division_id"].tolist()
        )
        all_divs = query(
            "SELECT id, date, name AS division FROM divisions WHERE house = ? ORDER BY date DESC LIMIT 50",
            (chamber,)
        )
        missed_df = all_divs[~all_divs["id"].isin(attended_ids)].head(20)

        r_tab, a_tab = st.tabs([
            f"Rebellions ({len(reb)} found locally)",
            f"Attendance log",
        ])

        with r_tab:
            if career_total > 0:
                tvfy_profile = (
                    f"https://theyvoteforyou.org.au/people/"
                    f"{chamber}/{politician_id}"
                )
                st.caption(
                    f"They Vote For You records **{career_total} career rebellion{'s' if career_total != 1 else ''}** total. "
                    f"Only divisions synced to this app ({len(rebellions_df)}) can be shown below — "
                    f"earlier rebellions may not be in our local database. "
                    f"[View full record on TVFY ↗](https://theyvoteforyou.org.au)"
                )
            if reb.empty:
                st.caption("No rebellions found in locally synced divisions.")
            else:
                for _, row in reb.iterrows():
                    try:
                        tvfy_url = (
                            f"https://theyvoteforyou.org.au/divisions"
                            f"/{row['house']}/{row['date']}/{int(row['number'])}"
                        )
                    except (ValueError, TypeError):
                        tvfy_url = "https://theyvoteforyou.org.au/divisions"
                    st.markdown(
                        f'<div style="margin:4px 0;font-size:13px;padding:6px 10px;'
                        f'background:#1a1a2e;border-left:3px solid #e94560;border-radius:4px">'
                        f'<a href="{tvfy_url}" target="_blank" style="color:#e94560;font-weight:600">'
                        f'{row["division"]}</a>'
                        f'<span style="color:#aaa;font-size:11px"> — {row["date"]}</span><br>'
                        f'<span style="color:#ddd;font-size:11px">Voted <b>{row["my_vote"].upper()}</b> '
                        f'(party voted <b>{row["party_majority"].upper()}</b>)</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        with a_tab:
            att_col, miss_col = st.columns(2)
            with att_col:
                st.markdown("**Recently attended**")
                for _, row in recent.iterrows():
                    div_name = (row["division"] or "Division")[:55]
                    try:
                        tvfy_url = (
                            f"https://theyvoteforyou.org.au/divisions"
                            f"/{row['house']}/{row['date']}/{int(row['number'])}"
                        )
                        link = f'<a href="{tvfy_url}" target="_blank">{div_name}</a>'
                    except (ValueError, TypeError):
                        link = div_name
                    st.markdown(
                        f'<div style="font-size:12px;margin:2px 0">'
                        f'{link}<span style="color:#aaa"> {row["date"]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            with miss_col:
                st.markdown("**Recently missed**")
                if missed_df.empty:
                    st.caption("No recent absences found.")
                else:
                    for _, row in missed_df.iterrows():
                        div_name = (row["division"] or "Division")[:55]
                        st.markdown(
                            f'<div style="font-size:12px;margin:2px 0;color:#aaa">'
                            f'{div_name}'
                            f'<span style="color:#666"> {row["date"]}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )


def _clean_bio(wiki_text: str, name: str, party: str, chamber: str,
               electorate: str, state: str) -> str:
    """
    Build a concise, readable bio. Use Wikipedia text if substantive,
    otherwise generate a short intro from structured data.
    """
    role = "Senator" if chamber == "senate" else "MP"
    location = electorate or state or ""

    # Build a structured intro line
    first_name = name.split()[0]
    if role == "Senator":
        intro = f"{name} is a {party} {role} for {state}."
    else:
        intro = f"{name} is a {party} {role} for the Division of {location}."

    if not wiki_text:
        return intro

    # Strip unhelpful generic openers and replace with our cleaner one
    skip_phrases = [
        f"{name} is an Australian politician",
        f"{first_name} is an Australian politician",
        "is an Australian politician.",
        "is a member of the Australian Parliament",
    ]
    cleaned = wiki_text
    for phrase in skip_phrases:
        if phrase.lower() in cleaned[:150].lower():
            # Find the end of the first sentence and keep everything after
            first_dot = cleaned.find(". ", 1)
            if first_dot > 0 and first_dot < 200:
                remaining = cleaned[first_dot + 2:].strip()
                if remaining:
                    cleaned = intro + " " + remaining
                else:
                    cleaned = intro
            else:
                cleaned = intro
            break
    else:
        # Wikipedia text looks substantive — prepend our intro
        if not cleaned.startswith(name):
            cleaned = intro + " " + cleaned

    # Trim to reasonable length
    if len(cleaned) > 600:
        cut = cleaned[:600].rfind(". ")
        if cut > 200:
            cleaned = cleaned[:cut + 1]
        else:
            cleaned = cleaned[:600] + "…"

    return cleaned


def profile_expander(name: str, politician_id: int = None, photo_url: str = None):
    prof = query("SELECT * FROM profiles WHERE name = ?", (name,))
    bio  = query("SELECT * FROM politician_bio WHERE politician_id = ?", (politician_id,)) if politician_id else None
    pol  = query(
        "SELECT party, chamber, electorate, state FROM politicians WHERE id = ?",
        (politician_id,)
    ) if politician_id else None

    has_profile = not prof.empty
    has_bio     = bio is not None and not bio.empty
    has_ai      = politician_id is not None
    has_votes   = pol is not None and not pol.empty

    if not has_profile and not has_bio and not has_ai:
        return

    with st.expander("▶ Profile, News & AI Analysis"):
        if photo_url:
            st.markdown(
                f'<div class="mobile-photo">'
                f'<img src="{photo_url}" width="100" '
                f'style="border-radius:8px;margin-bottom:8px;object-fit:cover">'
                f'</div>',
                unsafe_allow_html=True,
            )
        # ── Bio ────────────────────────────────────────────────────────────────
        p_party    = pol.iloc[0]["party"] if has_votes else ""
        p_chamber  = pol.iloc[0]["chamber"] if has_votes else ""
        p_elect    = pol.iloc[0]["electorate"] if has_votes else ""
        p_state    = pol.iloc[0]["state"] if has_votes else ""
        wiki_text  = bio.iloc[0]["wikipedia_summary"] if has_bio else ""
        wiki_url   = (bio.iloc[0]["wikipedia_url"] if has_bio else "") or ""

        bio_text = _clean_bio(wiki_text, name, p_party, p_chamber, p_elect, p_state)
        if bio_text:
            st.markdown(bio_text)
            if wiki_url:
                st.caption(f"[Read more on Wikipedia →]({wiki_url})")

        # ── Manual profile (from CSV) ────────────────────────────────────────
        if has_profile:
            p = prof.iloc[0]
            if p["employment_history"]:
                st.markdown(f"**Employment background**  \n{p['employment_history']}")
            if p["notes"]:
                st.markdown(f"**Overview**  \n{p['notes']}")

            cols = st.columns(2)
            with cols[0]:
                if p["media_positive"]:
                    st.markdown(f"**Media (+)**  \n{p['media_positive']}")
                if p["integrity_notes"]:
                    st.markdown(f"**Integrity record**  \n{p['integrity_notes']}")
                if p["funding_info"]:
                    st.markdown(f"**Funding**  \n{p['funding_info']}")
            with cols[1]:
                if p["media_negative"]:
                    st.markdown(f"**Media (−)**  \n{p['media_negative']}")
                if p["risk_assessment"]:
                    st.markdown(
                        f"**Risk assessment**  \n"
                        f"{risk_badge(p['risk_assessment'])}  \n"
                        f"{p['risk_assessment']}",
                        unsafe_allow_html=True,
                    )
                if p["funding_risk"]:
                    st.markdown(f"**Funding risk**  \n{p['funding_risk']}")
            if p["media_veracity"]:
                st.markdown(f"**Media veracity**  \n{p['media_veracity']}")
            if p["term_end"]:
                st.markdown(f"**Term / re-election:** {p['term_end']}")
            if p["postal_address"]:
                st.markdown(f"**Electorate office:** {p['postal_address']}")

        # ── Voting record & rebellions ───────────────────────────────────────
        if has_votes:
            st.divider()
            party   = pol.iloc[0]["party"]
            chamber = pol.iloc[0]["chamber"]
            voting_record_section(politician_id, party, chamber)

        # ── AI analysis ──────────────────────────────────────────────────────
        if politician_id:
            st.divider()
            ai_analysis_section(politician_id)
            st.divider()
            news_section(politician_id)


def politician_grid(df, chamber="representatives", tab_key=""):
    days_left = days_until(NEXT_ELECTION)
    cols_per_row = 4
    for i in range(0, len(df), cols_per_row):
        cols = st.columns(cols_per_row, gap="small")
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(df):
                break
            row = df.iloc[idx]
            pid = int(row["id"])
            with col:
                if row.get("photo_url"):
                    st.markdown(
                        f'<div class="desktop-photo" style="text-align:center">'
                        f'<img src="{row["photo_url"]}" width="90" '
                        f'style="border-radius:6px;object-fit:cover">'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                location = row.get("state") or row.get("electorate", "")
                att = row.get("attendance_%", "—")
                reb = int(row["rebellions"])
                reb_label = f"Reb: {reb}*" if reb > 0 else "Reb: 0"
                st.markdown(
                    f'<div style="text-align:center;margin-bottom:4px">'
                    f'<div style="font-size:14px;font-weight:700">{row["name"]}</div>'
                    f'<div style="font-size:11px;color:#888;line-height:1.4;margin-top:2px">'
                    f'{row["party"]}<br>'
                    f'{location}<br>'
                    f'Att: {att} · {reb_label}<br>'
                    f'{days_left:,}d'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
                heat = int(row.get("heat_score") or 0)
                pos  = int(row.get("positive_score") or 0)
                st.markdown(bipolar_bar(heat, pos, compact=True), unsafe_allow_html=True)

                # Compare checkbox
                in_compare = _compare_has(pid)
                if st.checkbox(
                    "Compare" if not in_compare else "In compare",
                    key=f"cmp_{tab_key}_{pid}",
                    value=in_compare,
                ):
                    _compare_add(pid)
                else:
                    _compare_remove(pid)

                profile_expander(row["name"], pid, photo_url=row.get("photo_url"))


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Desktop defaults ──────────────────────────────── */
.desktop-photo { display: block; }
.mobile-photo  { display: none;  }

/* ── Mobile overrides (<640px) ─────────────────────── */
@media screen and (max-width: 640px) {
  /* Photos: hide in grid, show inside expander */
  .desktop-photo { display: none !important; }
  .mobile-photo  { display: block !important; }

  /* 2-column grid */
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 45% !important;
    max-width: 50% !important;
    flex: 1 1 45% !important;
  }

  /* Smaller name text in cards */
  [data-testid="stColumn"] p strong {
    font-size: 13px !important;
    line-height: 1.2 !important;
  }

  /* Smaller caption text */
  [data-testid="stColumn"] small,
  [data-testid="stColumn"] [data-testid="stCaptionContainer"] {
    font-size: 11px !important;
    line-height: 1.3 !important;
  }

  /* Compact expander button */
  [data-testid="stColumn"] [data-testid="stExpander"] summary {
    font-size: 11px !important;
    padding: 5px 8px !important;
    min-height: 0 !important;
  }
  [data-testid="stColumn"] [data-testid="stExpander"] summary p {
    font-size: 11px !important;
    line-height: 1.2 !important;
  }

  /* "no AI data" label — smaller on mobile */
  .no-info-mobile { font-size: 10px !important; }

  /* Tighter column padding */
  [data-testid="stColumn"] > div {
    padding-left: 4px !important;
    padding-right: 4px !important;
  }
}

/* Tighten card padding */
[data-testid="stColumn"] { padding: 4px !important; }
</style>
""", unsafe_allow_html=True)

# ── Header (logo + tagline only) ──────────────────────────────────────────────
_theme_logo(280)
st.markdown("#### Cut through the ~~bull~~parrotshit.")

# state_from_pc used by build_mp_tab for Senate filtering
state_from_pc = None

# ── Promise tracker summary ────────────────────────────────────────────────────
_promise_summary = query("""
    SELECT party, status, COUNT(*) AS n
    FROM promises
    GROUP BY party, status
""")

STATUS_COLOURS = {
    "Delivered":   "#27ae60",
    "In Progress": "#3498db",
    "Not Started": "#555",
    "Broken":      "#e94560",
}
STATUS_ORDER = ["Delivered", "In Progress", "Not Started", "Broken"]

GOVERNMENT_PARTY = "ALP"   # update if government changes
STATUS_ICON = {"Delivered": "Done", "In Progress": "WIP", "Not Started": "Pending", "Broken": "Broken"}

def _promise_list_html(promises_df, is_government: bool = True) -> str:
    """Render promises as native <details> accordion items."""
    html = ""
    for _, p in promises_df.iterrows():
        colour = STATUS_COLOURS.get(p["status"], "#555")
        icon   = STATUS_ICON.get(p["status"], "")

        if is_government:
            badge = (
                f'<span style="background:{colour};color:#fff;'
                f'padding:1px 8px;border-radius:8px;font-size:11px;font-weight:600;'
                f'white-space:nowrap;margin-right:6px">{icon} {p["status"]}</span>'
            )
        else:
            badge = ""
            colour = "#555"

        # Detail body — richer for government, simple for opposition
        body_parts = []
        if is_government:
            if p.get("evidence"):
                body_parts.append(
                    f'<div style="font-size:12px;color:#ccc;margin:6px 0 4px;'
                    f'border-left:2px solid {colour};padding-left:8px">'
                    f'<strong>Progress:</strong> {p["evidence"]}</div>'
                )
            if p.get("scrutiny"):
                body_parts.append(
                    f'<div style="font-size:12px;color:#bbb;margin:4px 0;'
                    f'border-left:2px solid #f5a623;padding-left:8px">'
                    f'<strong>Scrutiny:</strong> {p["scrutiny"]}</div>'
                )
            if p.get("scrutiny_source"):
                body_parts.append(
                    f'<div style="font-size:11px;color:#888;margin:2px 0">'
                    f'Scrutiny source: <em>{p["scrutiny_source"]}</em></div>'
                )
        else:
            if p.get("evidence"):
                body_parts.append(
                    f'<div style="font-size:12px;color:#aaa;margin:4px 0">{p["evidence"]}</div>'
                )

        if p.get("source_url"):
            body_parts.append(
                f'<a href="{p["source_url"]}" target="_blank" '
                f'style="color:#3498db;font-size:11px">Source ↗</a>'
            )

        body = "".join(body_parts)

        html += (
            f'<details style="border-left:3px solid {colour};'
            f'padding:6px 10px;margin:5px 0;'
            f'background:rgba(255,255,255,0.03);border-radius:0 4px 4px 0;cursor:pointer">'
            f'<summary style="list-style:none;font-size:13px;display:flex;'
            f'align-items:flex-start;gap:6px;flex-wrap:wrap">'
            f'{badge}<span>{p["promise"]}</span></summary>'
            f'{body}'
            f'</details>'
        )
    return html

# ── Compare banner (shows when 1+ politicians selected) ───────────────────────
n_compare = len(st.session_state.get("compare_ids", []))
if n_compare > 0:
    banner_col, clear_col = st.columns([5, 1])
    with banner_col:
        if n_compare == 1:
            cid = st.session_state.compare_ids[0]
            cname = query("SELECT name FROM politicians WHERE id=?", (cid,))
            cname_str = cname.iloc[0]["name"] if not cname.empty else str(cid)
            st.info(f"**1 selected:** {cname_str} — select at least one more to compare.")
        else:
            cnames = query(
                f"SELECT name FROM politicians WHERE id IN ({','.join('?'*n_compare)})",
                tuple(st.session_state.get("compare_ids", [])),
            )["name"].tolist()
            st.success(f"**{n_compare} selected for comparison:** {', '.join(cnames)} — see the **Compare** tab.")
    with clear_col:
        if st.button("Clear", key="clear_compare_btn"):
            st.session_state.compare_ids = []
            st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────
(tab_currentgov, tab_yourreps, tab_reps, tab_senate, tab_indep, tab_divs, tab_bills, tab_votes,
 tab_compare, tab_promises, tab_revolving, tab_media, tab_ai_explainer) = st.tabs([
    "Current Gov", "Your Reps", "House of Reps", "Senate", "Independents", "Votes",
    "Dodgy Deals", "Look Up", "Compare", "Promises", "Revolving Door", "Media",
    "How AI Works",
])

days_left = days_until(NEXT_ELECTION)
mandate_pct = round(100 * (1 - days_left / (NEXT_ELECTION - LAST_ELECTION).days), 1)


def build_mp_tab(chamber: str):
    parties = query(
        "SELECT DISTINCT party FROM politicians WHERE chamber=? ORDER BY party",
        (chamber,)
    )["party"].tolist()

    filter_col, sort_col = st.columns([2, 2])
    with filter_col:
        selected_party = st.selectbox("Filter by party", ["All"] + parties, key=f"party_{chamber}")
    with sort_col:
        sort_by = st.selectbox(
            "Sort by",
            ["Heat Score ↓", "Name (A–Z)", "Rebellions ↓", "Rebellions ↑", "Attendance ↓", "Attendance ↑"],
            key=f"sort_{chamber}",
        )

    upd_col1, upd_col2, upd_col3 = st.columns(3)
    with upd_col1:
        only_news = st.checkbox("Has recent news", key=f"news_{chamber}")
    with upd_col2:
        only_ai = st.checkbox("Has AI analysis", key=f"ai_{chamber}")
    with upd_col3:
        only_controversial = st.checkbox(
            "Controversial",
            key=f"controversial_{chamber}",
            help="Both positive and controversy scores exceed 15% — bar extends meaningfully in both directions.",
        )

    mps = query("""
        SELECT p.id, p.name, p.party, p.electorate, p.state, p.photo_url,
               p.votes_attended, p.votes_possible, p.rebellions,
               CASE WHEN n.politician_id IS NOT NULL THEN 1 ELSE 0 END AS has_news,
               CASE WHEN a.politician_id IS NOT NULL THEN 1 ELSE 0 END AS has_ai,
               COALESCE(a.heat_score, 0) AS heat_score,
               COALESCE(a.rhetoric_flags, '{}') AS flags_json
        FROM politicians p
        LEFT JOIN (
            SELECT DISTINCT politician_id FROM politician_news
            WHERE published_date >= date('now', '-14 days')
        ) n ON n.politician_id = p.id
        LEFT JOIN ai_analysis a ON a.politician_id = p.id
        WHERE p.chamber = ?
          AND (? = 'All' OR p.party = ?)
    """, (chamber, selected_party, selected_party))

    import json as _json
    mps["positive_score"] = mps["flags_json"].apply(
        lambda x: _json.loads(x).get("positive_score", 0) if x and x != "{}" else 0
    )

    if mps.empty:
        st.info("No data yet. Run: python sync_data.py")
        return

    if only_news:
        mps = mps[mps["has_news"] == 1]
    if only_ai:
        mps = mps[mps["has_ai"] == 1]
    if only_controversial:
        # Both sides of the bar must exceed 15% (score > 1.5 → integer threshold ≥ 2)
        mps = mps[(mps["heat_score"] >= 2) & (mps["positive_score"] >= 2)]

    if mps.empty:
        st.info("No politicians match the current filters.")
        return

    mps["attendance_num"] = mps.apply(
        lambda r: 100 * r["votes_attended"] / r["votes_possible"]
        if r["votes_possible"] > 0 else 0,
        axis=1,
    )
    mps["attendance_%"] = mps["attendance_num"].apply(
        lambda v: f"{v:.0f}%" if v > 0 else "—"
    )

    sort_map = {
        "Name (A–Z)":     ("name", True),
        "Rebellions ↓":   ("rebellions", False),
        "Rebellions ↑":   ("rebellions", True),
        "Attendance ↓":   ("attendance_num", False),
        "Attendance ↑":   ("attendance_num", True),
        "Heat Score ↓":   ("heat_score", False),
    }
    sort_col_name, sort_asc = sort_map[sort_by]
    mps = mps.sort_values(sort_col_name, ascending=sort_asc)

    if state_from_pc and chamber == "senate":
        mps = mps[mps["state"] == state_from_pc]

    politician_grid(mps, chamber, tab_key=chamber)
    st.caption(
        f"{len(mps)} shown. "
        "\\* Rebellion count is a career total from They Vote For You and may exceed "
        "what's visible in locally synced divisions."
    )


# ── House of Reps ─────────────────────────────────────────────────────────────
# ── Your Reps ──────────────────────────────────────────────────────────────────
with tab_yourreps:
    st.subheader("Your Reps")
    st.caption(
        "Enter your postcode to find every politician who represents you, "
        "from your local MP to your state senators. "
        "These are the people you can actually write to."
    )

    address_electorate = None

    col_pc, col_addr = st.columns([1, 3])

    with col_pc:
        st.markdown("**Postcode**")
        postcode_input = st.text_input(
            "Postcode",
            max_chars=4,
            placeholder="e.g. 3006",
            key="yourreps_postcode",
            label_visibility="collapsed",
        )

    with col_addr:
        st.markdown("**Street address** *(more precise)*")
        address_input = st.text_input(
            "Street address",
            placeholder="e.g. 123 Collins Street, Melbourne VIC",
            key="yourreps_address",
            label_visibility="collapsed",
        )
        st.caption(
            "Uses OpenStreetMap to find your nearest polling place. Your address is not stored. "
            "Confirm at [electorate.aec.gov.au](https://electorate.aec.gov.au/)."
        )

    if address_input and len(address_input.strip()) > 5:
        @st.cache_data(ttl=3600, show_spinner=False)
        def _geocode_address(address: str):
            try:
                resp = _req_geo.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": f"{address}, Australia",
                        "format": "json",
                        "limit": 1,
                        "countrycodes": "au",
                    },
                    headers={"User-Agent": "Pollygraph-AusPolitics/1.0"},
                    timeout=10,
                )
                results = resp.json()
                if results:
                    return float(results[0]["lat"]), float(results[0]["lon"])
            except Exception:
                pass
            return None, None

        with st.spinner("Looking up your address…"):
            addr_lat, addr_lon = _geocode_address(address_input.strip())

        if addr_lat is not None:
            postcode_input = ""
            places = query(
                "SELECT division, lat, lng, name, suburb FROM polling_places "
                "WHERE lat IS NOT NULL"
            )
            if not places.empty:
                places["dist_km"] = places.apply(
                    lambda r: _haversine(addr_lat, addr_lon, r["lat"], r["lng"]),
                    axis=1,
                )
                nearest = places.sort_values("dist_km").iloc[0]
                address_electorate = nearest["division"]
                dist_km = nearest["dist_km"]

                state_from_addr = query(
                    "SELECT state FROM polling_places WHERE division = ? LIMIT 1",
                    (address_electorate,)
                )
                addr_state = (
                    state_from_addr.iloc[0]["state"]
                    if not state_from_addr.empty else None
                )

                st.success(
                    f"Your nearest polling place is **{nearest['name']}** "
                    f"({nearest['suburb']}, {dist_km:.1f} km away) "
                    f"→ electorate of **{address_electorate}**"
                )
                if dist_km > 10:
                    st.warning(
                        "The nearest polling place is quite far from the address you entered. "
                        "The result may not be accurate — please confirm at "
                        "[electorate.aec.gov.au](https://electorate.aec.gov.au/)."
                    )
                st.markdown(
                    '<a href="https://electorate.aec.gov.au/" target="_blank" style="'
                    'display:inline-block;padding:8px 16px;background:#e94560;color:#fff;'
                    'border-radius:6px;font-size:13px;font-weight:600;text-decoration:none;'
                    'margin:4px 0 12px 0">Confirm your electorate at AEC ↗</a>',
                    unsafe_allow_html=True,
                )
        elif address_input.strip():
            st.error(
                "Could not find that address. Try including your suburb and state, "
                "e.g. \"123 Collins Street, Melbourne VIC\". Or use the postcode option."
            )

    st.markdown("""
**Three levels of government represent you:**

| Level | Who represents you | What they control |
|-------|-------------------|-------------------|
| **Federal** | 1 House of Reps MP (your electorate) + ~12 Senators (your state) | Defence, immigration, taxation, Medicare, foreign affairs, telecommunications |
| **State / Territory** | 1 state MP (your state electorate) + state upper house members | Health, education, police, transport, planning, environment |
| **Local Council** | Councillors + Mayor (your ward / municipality) | Roads, rubbish, local planning, parks, libraries, community services |

Most political attention focuses on federal politics, but state and local decisions often have
a more direct impact on daily life — your hospital wait times, your children's school funding,
your roads, and your planning approvals are all state or local responsibilities.
""")

    st.divider()

    # Determine state — from postcode or from address geocode
    _yr_state = None
    _yr_electorates = []

    if address_electorate:
        _yr_electorates = [address_electorate]
        _yr_state = addr_state if 'addr_state' in dir() else None
        if not _yr_state:
            _s = query(
                "SELECT state FROM polling_places WHERE division = ? LIMIT 1",
                (address_electorate,)
            )
            _yr_state = _s.iloc[0]["state"] if not _s.empty else None
    elif postcode_input:
        _yr_state = postcode_to_state(postcode_input)
        if _yr_state:
            _yr_electorates = query(
                "SELECT electorate FROM postcode_electorates WHERE postcode = ?",
                (postcode_input.strip(),)
            )["electorate"].tolist()

    if _yr_state:
        if postcode_input and not address_electorate:
            st.success(f"**{postcode_input}** → {_yr_state}")

        # ── Federal: House of Reps ─────────────────────────────────────────
        st.markdown("### Federal — House of Representatives")
        st.caption(
            "Your local federal MP represents your electorate in the lower house. "
            "They vote on national legislation and should be your first point of contact "
            "for federal issues like Centrelink, Medicare, immigration, and taxation."
        )

        if _yr_electorates:
            placeholders = ",".join("?" * len(_yr_electorates))
            local_reps = query(f"""
                SELECT p.id, p.name, p.party, p.electorate, p.state, p.photo_url,
                       p.votes_attended, p.votes_possible, p.rebellions,
                       COALESCE(a.heat_score, 0) AS heat_score,
                       COALESCE(a.rhetoric_flags, '{{}}') AS flags_json
                FROM politicians p
                LEFT JOIN ai_analysis a ON a.politician_id = p.id
                WHERE p.chamber='representatives'
                  AND p.electorate IN ({placeholders})
                ORDER BY p.name
            """, tuple(_yr_electorates))

            if not local_reps.empty:
                import json as _json_yr
                local_reps["positive_score"] = local_reps["flags_json"].apply(
                    lambda x: _json_yr.loads(x).get("positive_score", 0) if x and x != "{}" else 0
                )
                local_reps["attendance_%"] = local_reps.apply(
                    lambda r: f"{100 * r['votes_attended'] / r['votes_possible']:.0f}%"
                    if r["votes_possible"] > 0 else "—", axis=1
                )
                st.markdown(
                    f"**Your electorate{'s' if len(_yr_electorates) > 1 else ''}:** "
                    + ", ".join(f"**{e}**" for e in sorted(_yr_electorates))
                )
                if len(_yr_electorates) > 1 and not address_electorate:
                    st.caption(
                        "Your postcode spans multiple electorates. For a precise match, "
                        "switch to **Street address** lookup above, or confirm at "
                        "[electorate.aec.gov.au](https://electorate.aec.gov.au/)."
                    )
                politician_grid(local_reps, tab_key="yourreps_fed")

            for elec in sorted(_yr_electorates):
                electorate_card(elec)
        else:
            st.info(
                f"No federal electorate mapping found. "
                "[Search the AEC electorate finder](https://electorate.aec.gov.au/)"
            )

        st.divider()

        # ── Federal: Senate ────────────────────────────────────────────────
        st.markdown("### Federal — Senate")
        st.caption(
            f"Senators represent your entire state or territory ({_yr_state}). "
            "Each state has 12 senators; each territory has 2. They review and amend "
            "legislation passed by the House of Reps — the crossbench often holds the "
            "balance of power here."
        )
        senators_df = query("""
            SELECT p.id, p.name, p.party, p.electorate, p.state, p.photo_url,
                   p.votes_attended, p.votes_possible, p.rebellions,
                   COALESCE(a.heat_score, 0) AS heat_score,
                   COALESCE(a.rhetoric_flags, '{}') AS flags_json
            FROM politicians p
            LEFT JOIN ai_analysis a ON a.politician_id = p.id
            WHERE p.chamber='senate' AND p.state=?
            ORDER BY p.name
        """, (_yr_state,))

        if not senators_df.empty:
            import json as _json_yr2
            senators_df["positive_score"] = senators_df["flags_json"].apply(
                lambda x: _json_yr2.loads(x).get("positive_score", 0) if x and x != "{}" else 0
            )
            senators_df["attendance_%"] = senators_df.apply(
                lambda r: f"{100 * r['votes_attended'] / r['votes_possible']:.0f}%"
                if r["votes_possible"] > 0 else "—", axis=1
            )
            politician_grid(senators_df, chamber="senate", tab_key="yourreps_sen")
        else:
            st.info(f"No senators found for {_yr_state}.")

        st.divider()

        # ── State government ───────────────────────────────────────────────
        STATE_PARL_URLS = {
            "New South Wales": "https://www.parliament.nsw.gov.au/members",
            "Victoria": "",
            "Queensland": "https://www.parliament.qld.gov.au/Members/Current-Members",
            "South Australia": "https://www.parliament.sa.gov.au/Members",
            "Western Australia": "https://www.parliament.wa.gov.au/parliament/memblist.nsf",
            "Tasmania": "",
            "Australian Capital Territory": "http://web.archive.org/web/20251115031821/https://www.parliament.act.gov.au/members",
            "Northern Territory": "",
        }
        st.markdown("### State / Territory Government")
        st.caption(
            f"Your state or territory government ({_yr_state}) runs hospitals, "
            "schools, police, roads, public transport, and housing policy. State elections "
            "are held separately from federal elections. Your state electorate may differ "
            "from your federal electorate."
        )
        parl_url = STATE_PARL_URLS.get(_yr_state, "")
        st.markdown(
            f"Pollygraph currently tracks federal politicians only. "
            f"Find your state representatives here:"
        )
        if parl_url:
            st.markdown(f"[{_yr_state} Parliament — Find your member]({parl_url})")
        else:
            st.markdown("[Search your state parliament's website]")

        st.divider()

        # ── Local council ──────────────────────────────────────────────────
        st.markdown("### Local Council")
        st.caption(
            "Your local council manages roads, rubbish collection, parks, libraries, "
            "local planning decisions, and community services. Councillors are elected "
            "in local government elections held on different cycles to state and federal."
        )
        st.markdown(
            "Find your local council and councillors using the links below:"
        )

        LOCAL_GOV_URLS = {
            "New South Wales": ("", "NSW — Find my council"),
            "Victoria": ("", "VIC — Find your council"),
            "Queensland": ("", "QLD — Local government directory"),
            "South Australia": ("", "SA — Council directory"),
            "Western Australia": ("", "WA — LG directory"),
            "Tasmania": ("https://www.dpac.tas.gov.au/divisions/local_government", "TAS — Local government"),
            "Australian Capital Territory": ("", "ACT — No separate local councils (ACT government handles local services)"),
            "Northern Territory": ("", "NT — Local government"),
        }
        lg = LOCAL_GOV_URLS.get(_yr_state)
        if lg:
            if "No separate" in lg[1]:
                st.info(lg[1])
            else:
                st.markdown(f"[{lg[1]}]({lg[0]})")
        else:
            st.markdown("Search your state's local government website.")

    elif postcode_input:
        st.warning("Postcode not recognised. Check and try again.")


# ── Current Government ─────────────────────────────────────────────────────────
def build_current_gov_tab():
    # ── Feature cards + value prop ────────────────────────────────────────────
    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:12px">'

        '<div style="flex:1;min-width:260px;border-left:4px solid #e94560;'
        'border:1px solid rgba(128,128,128,0.2);border-left:4px solid #e94560;'
        'border-radius:0 8px 8px 0;padding:14px 16px">'
        '<div style="font-size:15px;font-weight:700;margin-bottom:4px">'
        'Call out the <s>bull</s>parrotshit</div>'
        '<div style="font-size:13px;line-height:1.5;opacity:0.8">'
        'Pollygraph tracks what pollies say, how the media spins it, '
        'and compares it all to how they actually vote on the stuff '
        'that impacts you.</div></div>'

        '<div style="flex:1;min-width:260px;border-left:4px solid #27ae60;'
        'border:1px solid rgba(128,128,128,0.2);border-left:4px solid #27ae60;'
        'border-radius:0 8px 8px 0;padding:14px 16px">'
        '<div style="font-size:15px;font-weight:700;margin-bottom:4px">'
        'Clean up the <s>bull</s>parrotshit</div>'
        '<div style="font-size:13px;line-height:1.5;opacity:0.8">'
        'Pollies work for you, find your federal and state '
        'representatives by entering your postcode, then write them a letter '
        'calling them out on their parrotshit. It works and we have templates.</div></div>'

        '</div>'

        '<div style="font-size:14px;font-style:italic;line-height:1.6;opacity:0.6;'
        'margin-bottom:8px">'
        'Pollygraph gives you the actual votes, the actual quotes, and the actual track record, '
        'so you can walk into any conversation armed with facts, not vibes.</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Mandate countdown ─────────────────────────────────────────────────────
    days_left = days_until(NEXT_ELECTION)
    approx_label = "≈ " if ELECTION_DATE_APPROX else ""
    mandate_pct = round(100 * (1 - days_left / (NEXT_ELECTION - LAST_ELECTION).days), 1)

    if days_left <= 100:
        countdown_label = f"{days_left} days"
    else:
        years  = days_left // 365
        months = (days_left % 365) // 30
        parts  = []
        if years:
            parts.append(f"{years}yr{'s' if years != 1 else ''}")
        if months:
            parts.append(f"{months}mo")
        countdown_label = " ".join(parts) or f"{days_left}d"

    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.markdown(
            f'<div style="font-size:13px;color:#888;margin-bottom:2px">Last election</div>'
            f'<div style="font-size:20px;font-weight:700">{LAST_ELECTION.strftime("%-d %b %Y")}</div>',
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            f'<div style="font-size:13px;color:#888;margin-bottom:2px">{approx_label}Next federal election</div>'
            f'<div style="font-size:20px;font-weight:700">{countdown_label} away</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div style="font-size:13px;margin-bottom:4px">'
        f'<strong>{mandate_pct}%</strong> of this term gone. Clock\'s ticking.</div>',
        unsafe_allow_html=True,
    )
    st.progress(mandate_pct / 100)
    st.caption(
        "Australian governments serve up to 3 years from election day. "
        "At 100%, an election must be called."
    )

    st.divider()

    # ── Current government mandates ───────────────────────────────────────────
    st.markdown("#### Are they keeping their promises?")
    st.caption(
        "What the government promised versus what they've actually done. "
        "Full detail for all parties in the Promises tab."
    )

    if not _promise_summary.empty:
        _all_promises = query("SELECT * FROM promises ORDER BY category, promise")
        _gov_data = _promise_summary[_promise_summary["party"] == GOVERNMENT_PARTY]
        _gov_counts = {r["status"]: r["n"] for _, r in _gov_data.iterrows()}
        _gov_total = sum(_gov_counts.values())

        if _gov_total:
            _bar_html = '<div style="display:flex;height:12px;border-radius:6px;overflow:hidden;margin:6px 0">'
            for _s in STATUS_ORDER:
                _n = _gov_counts.get(_s, 0)
                if _n:
                    _pct = round(100 * _n / _gov_total)
                    _bar_html += f'<div style="width:{_pct}%;background:{STATUS_COLOURS[_s]}"></div>'
            _bar_html += "</div>"

            _leg_parts = " &nbsp;·&nbsp; ".join(
                f'<span style="color:{STATUS_COLOURS[_s]};font-size:12px">'
                f'{_s}: {_gov_counts[_s]}</span>'
                for _s in STATUS_ORDER if _gov_counts.get(_s, 0)
            )
            st.markdown(
                f'<div style="font-size:13px;font-weight:600;margin-bottom:2px">'
                f'{GOVERNMENT_PARTY} — Government in power</div>'
                f'{_bar_html}'
                f'<div style="margin:4px 0 2px">{_leg_parts}</div>',
                unsafe_allow_html=True,
            )

            with st.expander(f"See all {_gov_total} {GOVERNMENT_PARTY} promises"):
                _gov_promises = _all_promises[_all_promises["party"] == GOVERNMENT_PARTY]
                for _cat in sorted(_gov_promises["category"].unique()):
                    st.markdown(f"**{_cat}**")
                    _cat_df = _gov_promises[_gov_promises["category"] == _cat]
                    st.markdown(_promise_list_html(_cat_df), unsafe_allow_html=True)

    # ── Controversies and influences ──────────────────────────────────────────
    st.markdown("#### Controversies & influences shaping this term")

    _controversies = [
        {
            "title": "AUKUS & defence spending",
            "detail": (
                "The $368 billion AUKUS nuclear submarine deal remains the single largest defence "
                "commitment in Australian history. Critics question cost blowouts, the 2030s delivery "
                "timeline, and whether conventional alternatives would better serve Australia's "
                "strategic needs. The deal has bipartisan support but faces crossbench scrutiny."
            ),
            "colour": "#e94560",
            "sources": [
                ("ABC News — what is AUKUS?", "https://www.abc.net.au/news/2023-03-14/what-is-aukus-submarine-deal-details-announced/102091510"),
                ("ABC News — inside the $8b Perth sub base", "https://www.abc.net.au/news/2025-09-12/inside-the-aukus-plan-to-station-american-subs-near-perth/105763818"),
                ("BBC — AUKUS deal explained", "https://www.bbc.com/news/articles/cgr589k5yleo"),
            ],
        },
        {
            "title": "Cost of living & housing",
            "detail": (
                "Rising rents, mortgage stress, and grocery prices have defined voter sentiment. "
                "The government's response — including energy bill relief, rental assistance, and "
                "the Housing Australia Future Fund — has been criticised as insufficient by "
                "housing advocates and too interventionist by the opposition."
            ),
            "colour": "#f5a623",
            "sources": [
                ("ABC News — housing crisis explained", "https://www.abc.net.au/news/2023-09-14/housing-crisis-australia-explained/102846108"),
            ],
        },
        {
            "title": "Energy transition",
            "detail": (
                "The government's 82% renewables by 2030 target is the centrepiece of its climate "
                "policy. Progress has been uneven — grid reliability concerns, planning delays for "
                "transmission lines, and opposition to offshore wind in some coastal communities "
                "have slowed rollout. The Coalition has countered with a nuclear energy proposal."
            ),
            "colour": "#2980b9",
            "sources": [
                ("ABC News — renewables pass 50% milestone", "https://www.abc.net.au/news/2026-01-29/australia-hits-power-demand-record-as-renewables-pass-50pc/106280246"),
                ("ABC News — emissions progress to 2030", "https://abc.net.au/news/2025-11-29/record-drop-in-australias-emissions/106074296"),
                ("AEMO — Draft 2026 Integrated System Plan", "https://aemo.com.au/energy-systems/major-publications/integrated-system-plan-isp/2026-integrated-system-plan-isp"),
            ],
        },
        {
            "title": "Political donations & lobbying",
            "detail": (
                "Despite promises of transparency, donation disclosure thresholds remain among the "
                "highest in the OECD ($16,900 federally). Both major parties continue to receive "
                "significant funding from mining, property, and gambling industries. The revolving "
                "door between politics and lobbying (see Revolving Door tab) remains largely unregulated."
            ),
            "colour": "#8e24aa",
            "sources": [
                ("ABC News — political donations explained", "https://www.abc.net.au/news/2022-02-01/political-donations-explained-who-gives-what/100793498"),
                ("Transparency International — integrity pack 2025", "https://transparency.org.au/integrity-pack/"),
                ("Transparency International — a better kind of politics", "https://transparency.org.au/better-politics/"),
            ],
        },
        {
            "title": "Immigration & population",
            "detail": (
                "Record net migration levels (over 500,000 in 2023) have fuelled debate about "
                "infrastructure, housing supply, and wage growth. The government has since tightened "
                "visa settings, but population pressures — particularly in Sydney and Melbourne — "
                "remain a political flashpoint."
            ),
            "colour": "#e67e22",
            "sources": [
                ("ABC News — record migration explained", "https://www.abc.net.au/news/2023-12-15/net-overseas-migration-record-high-explained/103233616"),
                ("ABC News — migration 'surge' talk overblown", "https://www.abc.net.au/news/2025-03-30/migration-already-falling-despite-election-debate-over-surge/105111118"),
                ("Lowy Institute — immigration attitudes", "https://www.lowyinstitute.org/publications/lowy-institute-poll-2024"),
            ],
        },
        {
            "title": "Natural resources royalties",
            "detail": (
                "Australia is the world's largest exporter of iron ore, lithium, and LNG, yet "
                "mining royalties are set by state governments and vary wildly — often at rates "
                "well below international benchmarks. The federal government collects no resource "
                "rent tax after the Minerals Resource Rent Tax was repealed in 2014 under pressure "
                "from the mining lobby. Norway's sovereign wealth fund (built on oil royalties) "
                "is worth over $1.7 trillion; Australia has no equivalent. Critics argue that "
                "Australians are giving away their non-renewable inheritance while mining companies "
                "report record profits and pay effective tax rates far below the headline 30%."
            ),
            "colour": "#d4ac0d",
            "sources": [
                ("ABC News — Qld coal royalties under spotlight", "https://www.abc.net.au/news/2025-09-28/qld-coal-mine-royalties-regime-questioned-after-job-cuts/105818488"),
            ],
        },
        {
            "title": "Media ownership concentration",
            "detail": (
                "Australia has one of the most concentrated media landscapes in the democratic world. "
                "News Corp and Nine Entertainment control the majority of print and television, "
                "raising questions about editorial independence and political influence. "
                "See the Media tab for ownership details and trust ratings."
            ),
            "colour": "#27ae60",
            "sources": [
                ("ABC News — who owns Australia's media", "https://www.abc.net.au/news/2021-03-03/who-owns-australian-media/13196164"),
                ("The Conversation — media concentration risks", "https://theconversation.com/australian-media-concentration-is-among-the-worst-in-the-world-107599"),
            ],
        },
    ]

    for c in _controversies:
        with st.expander(c["title"]):
            source_links = " &nbsp;".join(
                f'<a href="{url}" target="_blank" style="display:inline-block;'
                f'font-size:11px;color:#fff;background:{c["colour"]};padding:3px 10px;'
                f'border-radius:12px;text-decoration:none;margin:2px 2px 2px 0;'
                f'opacity:.85">{label}</a>'
                for label, url in c.get("sources", [])
            )
            st.markdown(
                f'<div style="border-left:3px solid {c["colour"]};padding:6px 12px;'
                f'font-size:13px">{c["detail"]}</div>'
                f'<div style="margin-top:8px">{source_links}</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Election result summary ───────────────────────────────────────────────
    _em = query("""
        SELECT winning_party,
               COUNT(*) AS seats,
               ROUND(AVG(margin_pct), 1) AS avg_margin,
               ROUND(AVG(swing), 1) AS avg_swing
        FROM electorate_margins
        GROUP BY winning_party
        ORDER BY seats DESC
    """)

    _party_seats = query("""
        SELECT party, chamber, COUNT(*) AS n
        FROM politicians
        WHERE party NOT IN ('SPK', 'PRES', 'DPRES', 'CWM')
        GROUP BY party, chamber
    """)

    total_seats = 151
    alp_seats = int(_em[_em["winning_party"] == "ALP"]["seats"].sum()) if not _em.empty else 0
    coalition_seats = int(_em[_em["winning_party"].isin(["LP", "LNP", "NP"])]["seats"].sum()) if not _em.empty else 0
    others_seats = total_seats - alp_seats - coalition_seats
    majority_line = (total_seats // 2) + 1
    alp_majority = alp_seats - majority_line
    alp_pct = round(100 * alp_seats / total_seats)
    coal_pct = round(100 * coalition_seats / total_seats)

    st.markdown("**2025 Federal Election** · 3 May · ALP re-elected")
    st.markdown(
        f"**ALP {alp_seats}** · Coalition {coalition_seats} · "
        f"Others {others_seats} · Majority {majority_line} · "
        f"**ALP {'+'if alp_majority>=0 else ''}{alp_majority}**"
    )
    st.progress(alp_seats / total_seats)
    st.caption(
        f"Government: ALP (Albanese). Opposition: Coalition (Ley). "
        f"{alp_seats} of {total_seats} seats — majority by {alp_majority}."
    )

    st.divider()

    # ── Where other parties failed ────────────────────────────────────────────
    st.markdown("#### 2025 election results")

    if not _em.empty:
        for party_code, party_name, colour in [
            ("LP", "Liberal Party", "#1565c0"),
            ("LNP", "Liberal National Party", "#1565c0"),
            ("NP", "National Party", "#1b5e20"),
        ]:
            pdata = _em[_em["winning_party"] == party_code]
            if pdata.empty:
                continue
            p_seats = int(pdata["seats"].sum())
            p_margin = float(pdata["avg_margin"].iloc[0])
            p_swing = float(pdata["avg_swing"].iloc[0])

            st.markdown(
                f'<div style="border-left:4px solid {colour};padding:8px 14px;'
                f'margin:6px 0;border-radius:0 6px 6px 0">'
                f'<div style="font-size:14px;font-weight:700">{party_name}</div>'
                f'<div style="font-size:13px;color:#aaa;margin-top:4px">'
                f'{p_seats} seat{"s" if p_seats != 1 else ""} held '
                f'&nbsp;·&nbsp; Average margin: {p_margin}% '
                f'&nbsp;·&nbsp; Average swing: {p_swing:+.1f}%'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("""
The **Coalition** (Liberal, LNP, and Nationals) entered the 2025 election under Peter Dutton
after losing government in 2022. Key factors in their result:

- **Teal losses held** — The independent candidates who won traditionally safe Liberal seats in 2022
  (Kooyong, Goldstein, North Sydney, Wentworth, and others) largely held those seats, denying the
  Liberals a path back to their pre-2022 position.
- **Climate and integrity** — Voters in affluent urban seats continued to punish the Coalition for
  its stance on climate policy and its opposition to a federal integrity commission during the
  Morrison years.
- **Regional squeeze** — The Nationals faced pressure from independents and minor parties in
  regional seats, particularly on issues like water management, health services, and renewables.
- **Senate fragmentation** — Minor parties and independents continued to win Senate seats at
  Coalition expense, further limiting their ability to block legislation.
""")


with tab_currentgov:
    try:
        build_current_gov_tab()
    except Exception as _cg_err:
        st.error(f"Error loading Current Government tab: {_cg_err}")


# ── House of Reps ─────────────────────────────────────────────────────────────
with tab_reps:
    st.subheader("House of Reps")
    st.caption(
        "151 MPs. The party with the most seats runs the country. "
        "We track how every one of them votes, how often they show up, "
        "and how often they break ranks. Search by name or postcode."
    )
    search = st.text_input(
        "Search by name, electorate or postcode", key="reps_search",
        placeholder="e.g. Melbourne, Albanese, or 3006"
    )
    if search:
        is_postcode = search.strip().isdigit() and len(search.strip()) == 4

        if is_postcode:
            electorates = query(
                "SELECT electorate FROM postcode_electorates WHERE postcode = ?",
                (search.strip(),)
            )["electorate"].tolist()

            if electorates:
                placeholders = ",".join("?" * len(electorates))
                reps_df = query(f"""
                    SELECT p.id, p.name, p.party, p.electorate, p.state, p.photo_url,
                           p.votes_attended, p.votes_possible, p.rebellions,
                           COALESCE(a.heat_score, 0) AS heat_score,
                           COALESCE(a.rhetoric_flags, '{{}}') AS flags_json
                    FROM politicians p
                    LEFT JOIN ai_analysis a ON a.politician_id = p.id
                    WHERE p.chamber='representatives'
                      AND p.electorate IN ({placeholders})
                    ORDER BY p.name
                """, tuple(electorates))
                import json as _json
                reps_df["positive_score"] = reps_df["flags_json"].apply(
                    lambda x: _json.loads(x).get("positive_score", 0) if x and x != "{}" else 0
                )
                st.info(
                    f"Postcode **{search.strip()}** falls in: "
                    + ", ".join(f"**{e}**" for e in sorted(electorates))
                )
            else:
                reps_df = pd.DataFrame()
                st.warning(f"No electorate found for postcode {search.strip()}.")
        else:
            reps_df = query("""
                SELECT p.id, p.name, p.party, p.electorate, p.state, p.photo_url,
                       p.votes_attended, p.votes_possible, p.rebellions,
                       COALESCE(a.heat_score, 0) AS heat_score,
                       COALESCE(a.rhetoric_flags, '{}') AS flags_json
                FROM politicians p
                LEFT JOIN ai_analysis a ON a.politician_id = p.id
                WHERE p.chamber='representatives'
                  AND (LOWER(p.name) LIKE ? OR LOWER(p.electorate) LIKE ?)
                ORDER BY p.name
            """, (f"%{search.lower()}%", f"%{search.lower()}%"))
            import json as _json
            reps_df["positive_score"] = reps_df["flags_json"].apply(
                lambda x: _json.loads(x).get("positive_score", 0) if x and x != "{}" else 0
            )

        if not reps_df.empty:
            reps_df["attendance_%"] = reps_df.apply(
                lambda r: f"{100 * r['votes_attended'] / r['votes_possible']:.0f}%"
                if r["votes_possible"] > 0 else "—", axis=1)
            politician_grid(reps_df, tab_key="reps_search")
            st.caption(f"{len(reps_df)} shown.")

        if is_postcode and electorates:
            st.divider()
            for elec in sorted(electorates):
                electorate_card(elec)
    else:
        build_mp_tab("representatives")

# ── Senate ────────────────────────────────────────────────────────────────────
with tab_senate:
    st.subheader("Senate")
    st.caption(
        "76 senators. They review and vote on every law the House of Reps passes. "
        "Minor parties and independents often hold the balance of power here, "
        "which means this is where the real deals get done."
    )
    build_mp_tab("senate")

# ── Independents ───────────────────────────────────────────────────────────────
CROSSBENCH_PARTIES = [
    "Independent",
    "Centre Alliance",
    "Jacqui Lambie Network",
    "Katter's Australian Party",
    "Pauline Hanson's One Nation Party",
    "United Australia Party",
    "Australia's Voice",
]

with tab_indep:
    st.subheader("Independents & Crossbench")

    st.caption(
        "Politicians who don't answer to a party boss. Independents vote on their own judgement. "
        "The crossbench is where they sit, and when the government needs extra votes, "
        "these are the people they have to negotiate with."
    )

    col_ind, col_cross = st.columns(2)
    with col_ind:
        st.markdown(
            '<div style="border-left:4px solid #27ae60;padding:10px 14px;'
            'border-radius:0 6px 6px 0;margin-bottom:8px">'
            '<div style="font-size:15px;font-weight:700;margin-bottom:6px">'
            'An Independent — the "who"</div>'
            '<div style="font-size:13px">'
            'A politician who is <strong>not a member of any political party</strong>. '
            'They run on their own platform, answer only to their electorate, and vote '
            'according to their own judgement. They have no party leader, no party whip, '
            'and no party platform to follow — they are a "party of one".'
            '</div></div>',
            unsafe_allow_html=True,
        )
    with col_cross:
        st.markdown(
            '<div style="border-left:4px solid #2980b9;padding:10px 14px;'
            'border-radius:0 6px 6px 0;margin-bottom:8px">'
            '<div style="font-size:15px;font-weight:700;margin-bottom:6px">'
            'A Crossbencher — the "where"</div>'
            '<div style="font-size:13px">'
            'Any MP or senator who is <strong>neither part of the government nor the '
            'official opposition</strong>. This includes independents <em>and</em> members '
            'of minor parties (Greens, One Nation, Jacqui Lambie Network, etc.). They sit '
            'on the curved "cross benches" between the government and opposition sides of '
            'the chamber.'
            '</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(128,128,128,0.2);'
        'border-radius:8px;padding:12px 16px;margin:8px 0 16px">'
        '<div style="font-size:14px;font-weight:700;margin-bottom:6px">'
        'The key distinction</div>'
        '<div style="font-size:13px">'
        '<strong>All independents are crossbenchers</strong> — because they are not in the '
        'government or opposition.<br>'
        '<strong>Not all crossbenchers are independents</strong> — because some belong to '
        'minor parties like the Greens.'
        '</div>'
        '<div style="font-size:12px;color:#888;margin-top:8px">'
        'The term "crossbench" is usually used when talking about <em>voting power</em>. '
        'When the government needs extra votes to pass a law, it must "go to the crossbench" '
        'to negotiate — regardless of whether those crossbenchers are independents or minor '
        'party members. In that moment, they all hold the balance of power.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # Comparison table
    st.markdown(
        '<table style="width:100%;font-size:13px;border-collapse:collapse;margin-bottom:16px">'
        '<tr style="border-bottom:2px solid rgba(128,128,128,0.3);text-align:left">'
        '<th style="padding:6px 10px"></th>'
        '<th style="padding:6px 10px;color:#27ae60">Independent</th>'
        '<th style="padding:6px 10px;color:#2980b9">Crossbencher</th></tr>'
        '<tr style="border-bottom:1px solid rgba(128,128,128,0.15)">'
        '<td style="padding:6px 10px;font-weight:600">Party member?</td>'
        '<td style="padding:6px 10px">No — always solo</td>'
        '<td style="padding:6px 10px">Sometimes (may belong to a minor party)</td></tr>'
        '<tr style="border-bottom:1px solid rgba(128,128,128,0.15)">'
        '<td style="padding:6px 10px;font-weight:600">Who do they answer to?</td>'
        '<td style="padding:6px 10px">Only their voters</td>'
        '<td style="padding:6px 10px">Their voters (and their party, if they have one)</td></tr>'
        '<tr style="border-bottom:1px solid rgba(128,128,128,0.15)">'
        '<td style="padding:6px 10px;font-weight:600">Where do they sit?</td>'
        '<td style="padding:6px 10px">On the cross benches</td>'
        '<td style="padding:6px 10px">On the cross benches</td></tr>'
        '<tr>'
        '<td style="padding:6px 10px;font-weight:600">Example</td>'
        '<td style="padding:6px 10px">David Pocock (Ind)</td>'
        '<td style="padding:6px 10px">A Greens senator <em>or</em> David Pocock</td></tr>'
        '</table>',
        unsafe_allow_html=True,
    )

    st.divider()

    with st.expander("Why independents matter — and why voting for them is not a wasted vote"):
        st.markdown("""
Australia's preferential voting system means a vote for an independent is never wasted.
If your first-choice candidate is eliminated, your vote flows to your next preference —
so you can vote with your conscience knowing your vote still counts toward the final result.

Independents and crossbenchers play an outsized role in Australian democracy. When neither
major party holds a clear majority, crossbench MPs and senators become kingmakers —
they negotiate directly with the government on legislation, extracting concessions
for their communities or policy priorities that the major parties would otherwise ignore.

In the Senate, minor party and independent senators routinely hold the balance of power.
No government since 2004 has controlled the Senate outright, meaning every piece of legislation
must be negotiated through the crossbench. This gives individual senators — sometimes
representing fewer than 100,000 voters — direct influence over national policy.

In the House of Representatives, the 2022 and 2025 elections saw a historic wave of
"teal" independents win traditionally safe Liberal seats, particularly on platforms of
climate action, integrity, and gender equality. These MPs have shifted the centre of
political debate and forced both major parties to respond to issues they had previously
sidelined.

**Key advantages of independent representation:**

- **No party whip** — independents vote on the merits of each bill, not on party orders.
  Their voting record is a genuine reflection of their judgement.
- **Constituency focus** — without party machinery to fall back on, independents succeed
  or fail based on how well they serve their electorate.
- **Accountability** — they cannot hide behind party talking points. Every vote,
  every absence, every position is personally theirs.
- **Balance of power** — even a single crossbench vote can defeat or pass legislation,
  giving disproportionate influence to independent MPs.
""")

    st.divider()

    # ── Crossbench MPs and Senators ────────────────────────────────────────────
    import json as _json_indep

    placeholders_indep = ",".join("?" * len(CROSSBENCH_PARTIES))
    indep_df = query(f"""
        SELECT p.id, p.name, p.party, p.electorate, p.state, p.photo_url,
               p.chamber, p.votes_attended, p.votes_possible, p.rebellions,
               COALESCE(a.heat_score, 0) AS heat_score,
               COALESCE(a.rhetoric_flags, '{{}}') AS flags_json
        FROM politicians p
        LEFT JOIN ai_analysis a ON a.politician_id = p.id
        WHERE p.party IN ({placeholders_indep})
        ORDER BY p.chamber, p.name
    """, tuple(CROSSBENCH_PARTIES))

    indep_df["positive_score"] = indep_df["flags_json"].apply(
        lambda x: _json_indep.loads(x).get("positive_score", 0) if x and x != "{}" else 0
    )
    indep_df["attendance_num"] = indep_df.apply(
        lambda r: 100 * r["votes_attended"] / r["votes_possible"]
        if r["votes_possible"] > 0 else 0, axis=1
    )
    indep_df["attendance_%"] = indep_df["attendance_num"].apply(
        lambda v: f"{v:.0f}%" if v > 0 else "—"
    )

    reps_indep = indep_df[indep_df["chamber"] == "representatives"]
    sen_indep  = indep_df[indep_df["chamber"] == "senate"]

    if not reps_indep.empty:
        st.subheader(f"House of Reps — {len(reps_indep)} crossbench members")
        politician_grid(reps_indep, chamber="representatives", tab_key="indep_reps")

    if not sen_indep.empty:
        st.subheader(f"Senate — {len(sen_indep)} crossbench senators")
        politician_grid(sen_indep, chamber="senate", tab_key="indep_sen")

    if indep_df.empty:
        st.info("No independents or crossbench members found in the current data.")

    st.divider()
    st.caption(
        f"{len(indep_df)} crossbench politicians shown across both chambers. "
        "Includes independents and minor party members outside the ALP, "
        "Liberal Party, National Party, LNP, and Greens."
    )

# ── Divisions ─────────────────────────────────────────────────────────────────
with tab_divs:
    st.subheader("How they voted")
    st.caption(
        "When Parliament votes on a law, every MP has to stand up and be counted. "
        "They call it a 'division'. Pick one below to see who voted yes, "
        "who voted no, and who didn't bother showing up."
    )

    house_filter = st.radio(
        "Chamber", ["All", "Representatives", "Senate"], horizontal=True
    )
    house_map = {"All": None, "Representatives": "representatives", "Senate": "senate"}
    hf = house_map[house_filter]

    if hf:
        divs = query("""
            SELECT id, date, house, name, number, aye_votes, no_votes, rebellions, summary
            FROM divisions WHERE house=?
            ORDER BY date DESC, number DESC LIMIT 100
        """, (hf,))
    else:
        divs = query("""
            SELECT id, date, house, name, number, aye_votes, no_votes, rebellions, summary
            FROM divisions ORDER BY date DESC, number DESC LIMIT 100
        """)

    if divs.empty:
        st.info("No division data yet.")
    else:
        div_options = {
            f"{r['date']} — {r['name'][:70]}": i
            for i, r in divs.iterrows()
        }
        selected_label = st.selectbox(
            "Select a division to inspect",
            list(div_options.keys()),
            key="div_select",
        )
        st.dataframe(
            divs[["date", "house", "name", "aye_votes", "no_votes", "rebellions"]],
            width="stretch",
            hide_index=True,
        )
        row = divs.loc[div_options[selected_label]]

        st.divider()

        tvfy_url = (
            f"https://theyvoteforyou.org.au/divisions"
            f"/{row['house']}/{row['date']}/{int(row['number'])}"
        )

        title_col, link_col = st.columns([4, 1])
        with title_col:
            st.subheader(row["name"])
            st.caption(f"{row['house'].title()} — {row['date']}")
        with link_col:
            st.markdown(
                f'<a href="{tvfy_url}" target="_blank" style="'
                f'display:inline-block;margin-top:18px;padding:6px 14px;'
                f'background:#e94560;color:#fff;border-radius:6px;'
                f'font-size:13px;font-weight:600;text-decoration:none">'
                f'View source ↗</a>',
                unsafe_allow_html=True,
            )

        c1, c2, c3 = st.columns(3)
        c1.metric("Aye", int(row["aye_votes"]))
        c2.metric("No", int(row["no_votes"]))
        c3.metric("Rebellions", int(row["rebellions"]))

        bills = query("""
            SELECT b.title, b.url FROM bills b
            JOIN division_bills db ON db.bill_id = b.id
            WHERE db.division_id = ?
        """, (int(row["id"]),))

        if not bills.empty:
            st.markdown("**Linked legislation:**")
            for _, bill in bills.iterrows():
                if bill["url"]:
                    st.markdown(f"- [{bill['title'] or 'Bill'}]({bill['url']})")
                else:
                    st.markdown(f"- {bill['title']}")

        if row["summary"]:
            st.markdown("**Summary** *(from Hansard via They Vote For You):*")
            st.markdown(row["summary"])
            st.caption(f"[Full division record on They Vote For You →]({tvfy_url})")

# ── Vote Explorer ─────────────────────────────────────────────────────────────
with tab_votes:
    st.subheader("Look up any pollie")
    st.caption(
        "Pick a politician. See every vote they've cast. "
        "Check whether what they say matches what they do."
    )

    mp_names = query("SELECT name FROM politicians ORDER BY name")["name"].tolist()
    if not mp_names:
        st.info("No data yet.")
    else:
        selected_mp = st.selectbox(
            "Select a politician", mp_names, index=None,
            placeholder="Search or choose a politician…",
        )

        # ── Spotlight: cycle through newsworthy politicians until one is picked ──
        if selected_mp is None:
            import time as _time_ve

            spotlight_df = query("""
                SELECT p.id, p.name, p.photo_url, p.party, p.chamber,
                       p.electorate, p.state, p.votes_attended, p.votes_possible,
                       p.rebellions,
                       n.headline, n.source, n.published_date
                FROM politicians p
                JOIN politician_news n ON n.politician_id = p.id
                WHERE n.published_date >= date('now', '-14 days')
                GROUP BY p.id
                ORDER BY MAX(n.published_date) DESC
                LIMIT 12
            """)

            if not spotlight_df.empty:
                cycle_idx = int(_time_ve.time() // 5) % len(spotlight_df)
                sp = spotlight_df.iloc[cycle_idx]

                st.markdown(
                    '<div style="margin:8px 0 4px 0;font-size:12px;color:#888;'
                    'text-transform:uppercase;letter-spacing:1px">'
                    '&#9679; Recently in the news</div>',
                    unsafe_allow_html=True,
                )

                ph_col, info_col = st.columns([1, 3])
                with ph_col:
                    if sp["photo_url"]:
                        st.image(sp["photo_url"], width=120)
                with info_col:
                    st.markdown(f"### {sp['name']}")
                    chamber_label = "Senator" if sp["chamber"] == "senate" else "MP"
                    location = sp["state"] or sp["electorate"]
                    st.caption(f"{chamber_label} — {sp['party']} — {location}")
                    attendance = (
                        f"{100 * sp['votes_attended'] / sp['votes_possible']:.0f}%"
                        if sp["votes_possible"] > 0 else "—"
                    )
                    _dl = days_until(NEXT_ELECTION)
                    _mp = round(100 * (1 - _dl / (NEXT_ELECTION - LAST_ELECTION).days), 1)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Attendance", attendance)
                    m2.metric("Rebellions", int(sp["rebellions"]))
                    m3.metric("Days to election", f"{_dl:,}")
                    m4.metric("Mandate elapsed", f"{_mp}%")

                st.markdown(
                    f'<div style="background:#1a1a2e;border-radius:8px;padding:12px;'
                    f'margin:8px 0;font-size:13px">'
                    f'<span style="color:#888">Latest headline:</span> '
                    f'<span style="color:#ddd">{sp["headline"]}</span>'
                    f'<span style="color:#666;font-size:11px"> — {sp["source"]} '
                    f'{sp["published_date"]}</span></div>',
                    unsafe_allow_html=True,
                )

                st.caption(
                    f"Showing {cycle_idx + 1} of {len(spotlight_df)} · "
                    f"Select a name above to explore their voting record · "
                    f"Refresh to see another spotlight"
                )

        else:
            mp_row = query(
                "SELECT id, photo_url, party, electorate, state, chamber, "
                "rebellions, votes_attended, votes_possible FROM politicians WHERE name=?",
                (selected_mp,)
            )
            if not mp_row.empty:
                r = mp_row.iloc[0]
                mp_id = int(r["id"])

                ph_col, info_col = st.columns([1, 3])
                with ph_col:
                    if r["photo_url"]:
                        st.image(r["photo_url"], width=120)
                with info_col:
                    st.markdown(f"### {selected_mp}")
                    chamber_label = "Senator" if r["chamber"] == "senate" else "MP"
                    location = r["state"] or r["electorate"]
                    st.caption(f"{chamber_label} — {r['party']} — {location}")
                    attendance = (
                        f"{100 * r['votes_attended'] / r['votes_possible']:.0f}%"
                        if r["votes_possible"] > 0 else "—"
                    )
                    _dl = days_until(NEXT_ELECTION)
                    _mp = round(100 * (1 - _dl / (NEXT_ELECTION - LAST_ELECTION).days), 1)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Attendance", attendance)
                    m2.metric("Rebellions", int(r["rebellions"]))
                    m3.metric("Days to election", f"{_dl:,}")
                    m4.metric("Mandate elapsed", f"{_mp}%")

                profile_expander(selected_mp, mp_id, photo_url=r.get("photo_url"))

                mp_votes = query("""
                    SELECT d.id AS div_id, d.date, d.name AS division, d.house,
                           d.number, d.aye_votes, d.no_votes, d.rebellions,
                           d.summary, v.vote
                    FROM votes v JOIN divisions d ON d.id = v.division_id
                    WHERE v.politician_id = ? ORDER BY d.date DESC
                """, (mp_id,))

                if mp_votes.empty:
                    st.info("No vote records yet.")
                else:
                    aye_total = (mp_votes["vote"] == "aye").sum()
                    no_total  = (mp_votes["vote"] == "no").sum()
                    c1, c2 = st.columns(2)
                    c1.metric("Aye", aye_total)
                    c2.metric("No", no_total)

                    ve_filter = st.radio(
                        "Filter votes", ["All", "Aye only", "No only"],
                        horizontal=True, key="ve_vote_filter",
                    )
                    filtered = mp_votes
                    if ve_filter == "Aye only":
                        filtered = mp_votes[mp_votes["vote"] == "aye"]
                    elif ve_filter == "No only":
                        filtered = mp_votes[mp_votes["vote"] == "no"]

                    for idx, row in filtered.iterrows():
                        vote_colour = "#27ae60" if row["vote"] == "aye" else "#e74c3c"
                        vote_label = row["vote"].upper()
                        div_title = (row["division"] or "Division")[:80]

                        with st.expander(
                            f"{'🟢' if row['vote'] == 'aye' else '🔴'} "
                            f"{row['date']} — {div_title}"
                        ):
                            st.markdown(
                                f'<div style="margin-bottom:8px">'
                                f'<span style="background:{vote_colour};color:#fff;'
                                f'padding:3px 10px;border-radius:4px;font-size:12px;'
                                f'font-weight:700">{selected_mp} voted {vote_label}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                            mc1, mc2, mc3 = st.columns(3)
                            mc1.metric("Total Aye", int(row["aye_votes"]))
                            mc2.metric("Total No", int(row["no_votes"]))
                            mc3.metric("Rebellions", int(row["rebellions"]))

                            try:
                                tvfy_div_url = (
                                    f"https://theyvoteforyou.org.au/divisions"
                                    f"/{row['house']}/{row['date']}/{int(row['number'])}"
                                )
                            except (ValueError, TypeError):
                                tvfy_div_url = "https://theyvoteforyou.org.au/divisions"
                            st.markdown(
                                f'<a href="{tvfy_div_url}" target="_blank" style="'
                                f'font-size:12px;color:#e94560">View on They Vote For You ↗</a>',
                                unsafe_allow_html=True,
                            )

                            div_bills = query("""
                                SELECT b.title, b.url FROM bills b
                                JOIN division_bills db ON db.bill_id = b.id
                                WHERE db.division_id = ?
                            """, (int(row["div_id"]),))
                            if not div_bills.empty:
                                st.markdown("**Linked legislation:**")
                                for _, bill in div_bills.iterrows():
                                    if bill["url"]:
                                        st.markdown(f"- [{bill['title'] or 'Bill'}]({bill['url']})")
                                    else:
                                        st.markdown(f"- {bill['title'] or 'Bill'}")

                            summary_text = row.get("summary") or ""
                            if summary_text:
                                if len(summary_text) > 600:
                                    short = summary_text[:600].rsplit(". ", 1)[0] + "."
                                    st.markdown("**Division summary:**")
                                    st.markdown(short)
                                    with st.expander("Read full debate text"):
                                        st.markdown(summary_text)
                                else:
                                    st.markdown("**Division summary:**")
                                    st.markdown(summary_text)

                            all_votes = query("""
                                SELECT p.name, p.party, v2.vote
                                FROM votes v2
                                JOIN politicians p ON p.id = v2.politician_id
                                WHERE v2.division_id = ?
                                ORDER BY v2.vote, p.party, p.name
                            """, (int(row["div_id"]),))

                            if not all_votes.empty:
                                aye_df = all_votes[all_votes["vote"] == "aye"]
                                no_df  = all_votes[all_votes["vote"] == "no"]

                                aye_col, no_col = st.columns(2)
                                with aye_col:
                                    st.markdown(f"**Aye ({len(aye_df)})**")
                                    if not aye_df.empty:
                                        by_party = aye_df.groupby("party")["name"].apply(list)
                                        for party, names in sorted(by_party.items()):
                                            st.markdown(
                                                f'<div style="font-size:12px;margin:2px 0">'
                                                f'<strong>{party}</strong> ({len(names)}): '
                                                f'{", ".join(names[:10])}'
                                                f'{"…" if len(names) > 10 else ""}'
                                                f'</div>',
                                                unsafe_allow_html=True,
                                            )
                                with no_col:
                                    st.markdown(f"**No ({len(no_df)})**")
                                    if not no_df.empty:
                                        by_party = no_df.groupby("party")["name"].apply(list)
                                        for party, names in sorted(by_party.items()):
                                            st.markdown(
                                                f'<div style="font-size:12px;margin:2px 0">'
                                                f'<strong>{party}</strong> ({len(names)}): '
                                                f'{", ".join(names[:10])}'
                                                f'{"…" if len(names) > 10 else ""}'
                                                f'</div>',
                                                unsafe_allow_html=True,
                                            )

# ── Compare ───────────────────────────────────────────────────────────────────
def build_compare_tab():
    import json as _json

    st.caption(
        "Pick two or more politicians from any tab using the Compare checkbox, "
        "then come here to see them side by side. "
        "Attendance, voting record, scandals, the lot."
    )

    cids = list(st.session_state.get("compare_ids", []))

    if not cids:
        st.info(
            "No politicians selected yet.  \n"
            "Use the **Compare** checkbox on any card in the "
            "House of Reps or Senate tabs to add them here."
        )
        return

    if len(cids) == 1:
        cid = cids[0]
        cname = query("SELECT name FROM politicians WHERE id=?", (cid,))
        st.info(
            f"Only **{cname.iloc[0]['name']}** selected — pick at least one more to compare."
        )

    placeholders = ",".join("?" * len(cids))
    df = query(f"""
        SELECT
            p.id, p.name, p.party, p.electorate, p.state, p.chamber,
            p.photo_url,
            p.votes_attended, p.votes_possible,
            p.rebellions,
            COALESCE(a.heat_score, 0)      AS heat_score,
            COALESCE(a.rhetoric_flags, '{{}}') AS flags_json,
            b.wikipedia_summary,
            n.headline AS latest_news,
            n.url      AS news_url,
            n.published_date AS news_date
        FROM politicians p
        LEFT JOIN ai_analysis a ON a.politician_id = p.id
        LEFT JOIN politician_bio b ON b.politician_id = p.id
        LEFT JOIN (
            SELECT politician_id, headline, url, published_date,
                   ROW_NUMBER() OVER (PARTITION BY politician_id ORDER BY published_date DESC) AS rn
            FROM politician_news
        ) n ON n.politician_id = p.id AND n.rn = 1
        WHERE p.id IN ({placeholders})
        ORDER BY p.name
    """, tuple(cids))

    if df.empty:
        st.warning("Could not load comparison data.")
        return

    df["positive_score"] = df["flags_json"].apply(
        lambda x: _json.loads(x).get("positive_score", 0) if x and x != "{}" else 0
    )
    df["attendance_pct"] = df.apply(
        lambda r: round(100 * r["votes_attended"] / r["votes_possible"])
        if r["votes_possible"] > 0 else None, axis=1
    )
    df["attendance_str"] = df["attendance_pct"].apply(
        lambda v: f"{v}%" if v is not None else "—"
    )

    # ── Summary metrics table ──────────────────────────────────────────────────
    st.subheader("At a glance")

    summary_rows = []
    for _, r in df.iterrows():
        chamber_label = "Senator" if r["chamber"] == "senate" else "MP"
        summary_rows.append({
            "Name":        r["name"],
            "Role":        chamber_label,
            "Party":       r["party"],
            "Electorate":  r["electorate"] or r["state"] or "—",
            "Attendance":  r["attendance_str"],
            "Rebellions":  int(r["rebellions"]),
            "Heat (1-10)": int(r["heat_score"]),
            "Positive (1-10)": int(r["positive_score"]),
        })
    st.dataframe(
        pd.DataFrame(summary_rows).set_index("Name"),
        width="stretch",
    )

    # ── Side-by-side detail cards ──────────────────────────────────────────────
    st.subheader("Detailed comparison")
    cols = st.columns(len(df))
    for col, (_, row) in zip(cols, df.iterrows()):
        with col:
            # Photo
            if row.get("photo_url"):
                st.image(row["photo_url"], width=90)

            # Identity
            chamber_label = "Senator" if row["chamber"] == "senate" else "MP"
            location = row["electorate"] or row["state"] or "—"
            st.markdown(f"### {row['name']}")
            st.caption(f"{chamber_label} · {row['party']} · {location}")

            st.divider()

            # Attendance bar
            att = row["attendance_pct"]
            att_colour = (
                "#27ae60" if att and att >= 80
                else "#f5a623" if att and att >= 60
                else "#e94560"
            )
            att_str = row["attendance_str"]
            st.markdown(
                f'<div style="margin:4px 0 2px;font-size:12px;color:#aaa">Attendance</div>'
                f'<div style="font-size:22px;font-weight:700;color:{att_colour}">{att_str}</div>',
                unsafe_allow_html=True,
            )

            # Rebellions
            reb = int(row["rebellions"])
            reb_colour = "#e94560" if reb >= 5 else "#f5a623" if reb >= 1 else "#27ae60"
            st.markdown(
                f'<div style="margin:8px 0 2px;font-size:12px;color:#aaa">Rebellions</div>'
                f'<div style="font-size:22px;font-weight:700;color:{reb_colour}">{reb}</div>',
                unsafe_allow_html=True,
            )

            st.divider()

            # Bipolar heat bar
            st.markdown(
                '<div style="font-size:12px;color:#aaa;margin-bottom:4px">AI Score</div>',
                unsafe_allow_html=True,
            )
            heat = int(row["heat_score"])
            pos  = int(row["positive_score"])
            st.markdown(bipolar_bar(heat, pos), unsafe_allow_html=True)
            if heat > 0 or pos > 0:
                st.markdown(
                    f'<div style="font-size:11px;color:#888">'
                    f'Controversy: {heat}/10 &nbsp; Positive: {pos}/10</div>',
                    unsafe_allow_html=True,
                )

            # Background
            if row.get("wikipedia_summary"):
                st.divider()
                st.markdown(
                    '<div style="font-size:12px;color:#aaa;margin-bottom:4px">Background</div>',
                    unsafe_allow_html=True,
                )
                summary = row["wikipedia_summary"]
                st.caption(summary[:350] + ("…" if len(summary) > 350 else ""))

            # Latest news
            if row.get("latest_news"):
                st.divider()
                st.markdown(
                    '<div style="font-size:12px;color:#aaa;margin-bottom:4px">Latest news</div>',
                    unsafe_allow_html=True,
                )
                headline = row["latest_news"][:100]
                date_str = (row.get("news_date") or "")[:10]
                if row.get("news_url"):
                    st.markdown(f"[{headline}]({row['news_url']})")
                else:
                    st.caption(headline)
                if date_str:
                    st.caption(date_str)

            # Remove from compare
            st.divider()
            if st.button(
                f"Remove",
                key=f"rm_cmp_{int(row['id'])}",
                help=f"Remove {row['name']} from comparison",
            ):
                _compare_remove(int(row["id"]))
                st.rerun()


with tab_compare:
    build_compare_tab()

# ── Promises tab ───────────────────────────────────────────────────────────────
def build_promises_tab():
    st.caption(
        "What they promised before the election versus what they've actually done since. "
        "Tap any promise to see the evidence."
    )

    all_promises = query("SELECT * FROM promises ORDER BY party, category, promise")
    if all_promises.empty:
        st.info("No promise data yet. Run: python3 seed_promises.py")
        return

    # ── Filters ────────────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns(3)
    with f1:
        parties = ["All"] + sorted(all_promises["party"].unique().tolist())
        sel_party = st.selectbox("Party", parties, key="prom_party")
    with f2:
        cats = ["All"] + sorted(all_promises["category"].unique().tolist())
        sel_cat = st.selectbox("Category", cats, key="prom_cat")
    with f3:
        statuses = ["All"] + STATUS_ORDER
        sel_status = st.selectbox("Status", statuses, key="prom_status")

    df = all_promises.copy()
    if sel_party != "All":
        df = df[df["party"] == sel_party]
    if sel_cat != "All":
        df = df[df["category"] == sel_cat]
    if sel_status != "All":
        df = df[df["status"] == sel_status]

    st.caption(f"{len(df)} promise{'s' if len(df) != 1 else ''} shown.")

    # ── Per-party summary (full tab) ───────────────────────────────────────────
    summary = query("""
        SELECT party, status, COUNT(*) AS n FROM promises GROUP BY party, status
    """)
    if not summary.empty and sel_party == "All" and sel_status == "All":
        st.subheader("Summary by party")
        summary_cols = st.columns(len(summary["party"].unique()))
        for col, party in zip(summary_cols, sorted(summary["party"].unique())):
            pdata = summary[summary["party"] == party]
            counts = {r["status"]: r["n"] for _, r in pdata.iterrows()}
            total = sum(counts.values())
            with col:
                st.markdown(f"**{party}**")
                for s in STATUS_ORDER:
                    n = counts.get(s, 0)
                    if n:
                        icon = ""
                        bar_w = round(100 * n / total)
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0">'
                            f'<div style="width:{max(bar_w,4)}%;height:8px;'
                            f'background:{STATUS_COLOURS[s]};border-radius:4px;'
                            f'min-width:4px"></div>'
                            f'<span style="font-size:12px;color:#ccc">{icon} {s}: {n}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

    st.divider()

    # ── Promise cards (grouped by category) ────────────────────────────────────
    for category in sorted(df["category"].unique()):
        cat_df = df[df["category"] == category]
        st.markdown(f"#### {category}")

        # Government promises get the rich template; opposition gets the clean one
        for party in cat_df["party"].unique():
            party_cat_df = cat_df[cat_df["party"] == party]
            is_gov = party == GOVERNMENT_PARTY
            if len(cat_df["party"].unique()) > 1:
                st.caption(party)
            st.markdown(
                _promise_list_html(party_cat_df, is_government=is_gov),
                unsafe_allow_html=True,
            )


with tab_promises:
    build_promises_tab()

# ── Fine Print (Controversial Bills) ──────────────────────────────────────────
IMPACT_COLOURS = {
    "Electoral Reform": "#8e24aa",
    "Mining / Energy":  "#e67e22",
    "Digital / Privacy": "#2980b9",
}

def build_fine_print_tab():
    st.subheader("Dodgy deals")
    st.caption(
        "Laws that got passed because the right people made the right donations. "
        "We break down what each bill says it does versus what it actually does, "
        "who lobbied for it, and who got screwed."
    )

    st.markdown("""
**How lobbying shapes legislation in Australia**

The path from industry interest to law is well-established and largely legal:

1. **Access** — Lobbyists meet with ministers, advisers, and departmental officials to
   present their position. Australia's federal lobbyist register is public, but
   'in-house' lobbyists (employed directly by corporations) are exempt from registration.
   A 2023 Grattan Institute study found that ministers held more meetings with industry
   representatives than with community groups by a ratio of 4:1.

2. **Drafting influence** — Industry groups submit detailed legislative amendments during
   consultation periods. These submissions are often adopted wholesale. FOI requests have
   revealed cases where bill text was drafted by industry lawyers and submitted through
   ministerial offices with minimal modification.

3. **Revolving door** — Former ministers and senior advisers become lobbyists, carrying
   their political networks and inside knowledge into the private sector (see the
   Revolving Door tab). This creates an informal channel of influence that operates
   outside the formal lobbying register.

4. **Political donations** — Companies and industry associations donate to both major
   parties simultaneously, ensuring access regardless of who governs. Donation disclosure
   thresholds in Australia ($16,900 at federal level) are among the highest in the OECD,
   meaning many donations are never publicly disclosed.

5. **Committee capture** — Parliamentary committees that scrutinise legislation often
   receive the majority of their submissions from the industries being regulated.
   Resource constraints mean committee secretariats may rely heavily on industry-provided
   technical analysis.

None of this is illegal. That is precisely the point — the influence operates within
the system, making it harder to identify and challenge.
""")

    st.divider()

    bills = query("SELECT * FROM controversial_bills ORDER BY year DESC, title")
    if bills.empty:
        st.info("No bills data yet. Run: python3 seed_controversial_bills.py")
        return

    # ── Category filter ────────────────────────────────────────────────────────
    categories = ["All"] + sorted(bills["category"].unique().tolist())
    sel_cat = st.selectbox("Filter by category", categories, key="fp_cat")
    if sel_cat != "All":
        bills = bills[bills["category"] == sel_cat]

    st.caption(f"{len(bills)} bill{'s' if len(bills) != 1 else ''} shown.")
    st.divider()

    for _, b in bills.iterrows():
        colour = IMPACT_COLOURS.get(b["category"], "#666")

        # Title bar
        year_label = f" ({b['year']})" if b.get("year") else ""
        status_label = b.get("status") or ""
        st.markdown(
            f'<div style="border-left:4px solid {colour};padding:10px 14px;'
            f'margin:8px 0 4px;background:rgba(255,255,255,0.03);'
            f'border-radius:0 6px 6px 0">'
            f'<div style="font-size:16px;font-weight:700">'
            f'{b["short_name"] or b["title"]}{year_label}</div>'
            f'<div style="font-size:12px;color:#000;margin-top:2px">'
            f'{b["title"]}</div>'
            f'<span style="display:inline-block;margin-top:4px;font-size:11px;'
            f'background:{colour};color:#fff;padding:1px 8px;border-radius:8px">'
            f'{b["category"]} — {status_label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # What it says vs what it does
        col_says, col_does = st.columns(2)
        with col_says:
            st.markdown("**What it says it does**")
            st.markdown(
                f'<div style="font-size:13px;color:#000;border-left:3px solid #27ae60;'
                f'padding:6px 10px;margin:4px 0">{b["official_purpose"]}</div>',
                unsafe_allow_html=True,
            )
        with col_does:
            st.markdown("**What it actually does**")
            st.markdown(
                f'<div style="font-size:13px;color:#000;border-left:3px solid #e94560;'
                f'padding:6px 10px;margin:4px 0">{b["hidden_impact"]}</div>',
                unsafe_allow_html=True,
            )

        # Details accordion
        with st.expander("Full analysis"):
            if b.get("key_provisions"):
                st.markdown("**Key provisions**")
                for prov in b["key_provisions"].split(". "):
                    prov = prov.strip().rstrip(".")
                    if prov:
                        st.markdown(f"- {prov}")

            if b.get("who_benefits"):
                st.markdown("**Who benefits**")
                st.markdown(
                    f'<div style="font-size:13px;color:#000;border-left:3px solid #27ae60;'
                    f'padding:6px 10px;margin:4px 0">{b["who_benefits"]}</div>',
                    unsafe_allow_html=True,
                )

            if b.get("who_loses"):
                st.markdown("**Who loses**")
                st.markdown(
                    f'<div style="font-size:13px;color:#000;border-left:3px solid #e94560;'
                    f'padding:6px 10px;margin:4px 0">{b["who_loses"]}</div>',
                    unsafe_allow_html=True,
                )

            if b.get("criticism"):
                st.divider()
                st.markdown("**Independent criticism**")
                st.markdown(
                    f'<div style="font-size:13px;color:#000;padding:4px 0">{b["criticism"]}</div>',
                    unsafe_allow_html=True,
                )
                if b.get("criticism_urls"):
                    _crit_links = []
                    for _pair in b["criticism_urls"].split("||"):
                        _pair = _pair.strip()
                        if "|" in _pair:
                            _lbl, _url = _pair.split("|", 1)
                            _crit_links.append(
                                f'<a href="{_url}" target="_blank" style="display:inline-block;'
                                f'font-size:11px;color:#fff;background:#8e24aa;padding:3px 10px;'
                                f'border-radius:12px;text-decoration:none;margin:2px 2px 2px 0;'
                                f'opacity:.85">{_lbl}</a>'
                            )
                    if _crit_links:
                        st.markdown(" &nbsp;".join(_crit_links), unsafe_allow_html=True)
                elif b.get("criticism_source"):
                    st.caption(f"Sources: {b['criticism_source']}")

            if b.get("defence"):
                st.divider()
                st.markdown("**Government defence**")
                st.markdown(
                    f'<div style="font-size:13px;color:#000;font-style:italic;padding:4px 0">'
                    f'{b["defence"]}</div>',
                    unsafe_allow_html=True,
                )

            if b.get("source_url"):
                st.markdown(
                    f'[View legislation source]({b["source_url"]})',
                )

        st.divider()


with tab_bills:
    build_fine_print_tab()

# ── Revolving Door ─────────────────────────────────────────────────────────────
SECTOR_COLOURS = {
    "Defence / Consulting":        "#e94560",
    "Defence / Aerospace":         "#e94560",
    "Mining / Oil & Gas":          "#e67e22",
    "Mining / Resources":          "#e67e22",
    "Mining / Coal":               "#e67e22",
    "Foreign Investment / Infrastructure": "#8e24aa",
    "Foreign Aid / Development":   "#8e24aa",
    "Telecommunications / Energy": "#8e24aa",
    "Finance / International Trade": "#3498db",
    "Banking / Finance":           "#3498db",
    "Media / Finance":             "#3498db",
    "Consulting / Insurance":      "#3498db",
}

def build_revolving_door_tab():
    st.subheader("Revolving Door")
    st.caption(
        "Politicians who left office and walked straight into jobs in the industries "
        "they used to regulate. Australia has no mandatory cooling-off period. "
        "Most other democracies do."
    )

    cases = query("SELECT * FROM revolving_door ORDER BY left_office_year DESC, name")
    if cases.empty:
        st.info("No data yet. Run: python3 seed_revolving_door.py")
        return

    # ── Filters ────────────────────────────────────────────────────────────────
    f1, f2 = st.columns(2)
    with f1:
        parties = ["All"] + sorted(cases["party"].unique().tolist())
        sel_party = st.selectbox("Party", parties, key="rd_party")
    with f2:
        sectors = ["All"] + sorted(cases["sector"].unique().tolist())
        sel_sector = st.selectbox("Sector", sectors, key="rd_sector")

    if sel_party != "All":
        cases = cases[cases["party"] == sel_party]
    if sel_sector != "All":
        cases = cases[cases["sector"] == sel_sector]

    st.caption(f"{len(cases)} case{'s' if len(cases) != 1 else ''} shown.")

    # ── Stats summary ──────────────────────────────────────────────────────────
    if not cases.empty:
        avg_cool = cases["cooling_off_months"].mean()
        min_cool = cases["cooling_off_months"].min()
        max_cool = cases["cooling_off_months"].max()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cases", len(cases))
        m2.metric("Avg cooling-off", f"{avg_cool:.0f} months")
        m3.metric("Shortest", f"{min_cool} months")
        m4.metric("Longest", f"{max_cool} months")

    st.divider()

    # ── Case cards ─────────────────────────────────────────────────────────────
    for _, r in cases.iterrows():
        colour = SECTOR_COLOURS.get(r["sector"], "#666")
        cool = r["cooling_off_months"]
        if cool <= 3:
            cool_colour = "#e94560"
            cool_label = f"{cool} months — near-immediate"
        elif cool <= 6:
            cool_colour = "#f5a623"
            cool_label = f"{cool} months"
        elif cool <= 12:
            cool_colour = "#3498db"
            cool_label = f"{cool} months"
        else:
            cool_colour = "#27ae60"
            cool_label = f"{cool} months"

        # Header card
        st.markdown(
            f'<div style="border-left:4px solid {colour};padding:12px 16px;'
            f'margin:8px 0 4px;background:rgba(255,255,255,0.03);'
            f'border-radius:0 6px 6px 0">'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:flex-start;flex-wrap:wrap;gap:8px">'
            f'<div>'
            f'<div style="font-size:18px;font-weight:700">{r["name"]}</div>'
            f'<div style="font-size:12px;color:#888;margin-top:2px">'
            f'{r["party"]} — Left office {r["left_office_year"]}</div>'
            f'</div>'
            f'<div style="text-align:right">'
            f'<span style="display:inline-block;font-size:11px;background:{colour};'
            f'color:#fff;padding:2px 10px;border-radius:8px">{r["sector"]}</span>'
            f'<div style="font-size:11px;color:{cool_colour};margin-top:4px">'
            f'Cooling-off: {cool_label}</div>'
            f'</div></div>'
            # Flow diagram
            f'<div style="margin:12px 0 4px;display:flex;align-items:center;'
            f'gap:8px;flex-wrap:wrap">'
            f'<div style="background:#1a3a4a;padding:6px 12px;border-radius:6px;'
            f'font-size:12px;color:#3498db;max-width:45%">'
            f'<strong>Public office:</strong><br>{r["last_office"]}</div>'
            f'<div style="color:#888;font-size:18px">&rarr;</div>'
            f'<div style="background:#3a1a1a;padding:6px 12px;border-radius:6px;'
            f'font-size:12px;color:#e94560;max-width:45%">'
            f'<strong>{r["post_office_role"]}:</strong><br>{r["employer"]}</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Full details"):
            st.markdown("**Conflict of interest**")
            st.markdown(r["conflict_summary"])

            if r.get("portfolio_overlap"):
                st.markdown("**Portfolio overlap**")
                st.markdown(
                    f'<div style="font-size:13px;border-left:3px solid {colour};'
                    f'padding:6px 10px;margin:4px 0;color:#ccc">'
                    f'{r["portfolio_overlap"]}</div>',
                    unsafe_allow_html=True,
                )

            if r.get("source_url"):
                st.markdown(f"[Read more]({r['source_url']})")

        st.divider()

    # ── Context section ────────────────────────────────────────────────────────
    st.markdown("""
**Australia's lack of cooling-off rules**

Australia is one of the few advanced democracies with no mandatory cooling-off period
for ministers moving to the private sector. The Ministerial Standards require ministers
to not lobby government for 18 months — but there is no enforcement mechanism, no penalty
for breach, and the standard does not prevent taking a private-sector role immediately.

| Country | Cooling-off period | Enforcement |
|---------|-------------------|-------------|
| Australia | None (18-month lobbying guideline, unenforced) | None |
| United Kingdom | 2 years (ACOBA reviews) | Advisory, public reporting |
| Canada | 2 years (Conflict of Interest Act) | Legally binding |
| United States | 1–2 years (depending on role) | Legally binding |
| France | 3 years | Legally binding |

The Centre for Public Integrity has recommended a 2-year legally enforceable cooling-off
period for all ministers and senior advisers, with criminal penalties for breach.
""")


with tab_revolving:
    build_revolving_door_tab()

# ── Media tab ──────────────────────────────────────────────────────────────────
TRUST_COLOURS = {
    1: "#641e16", 2: "#922b21", 3: "#e94560", 4: "#e67e22",
    5: "#f5a623", 6: "#f1c40f", 7: "#3498db", 8: "#27ae60",
    9: "#1a7a45", 10: "#145a32",
}
LEANING_COLOURS = {
    "far-right":       "#922b21",
    "right":           "#e94560",
    "centre-right":    "#e67e22",
    "centre":          "#3498db",
    "centre-left":     "#27ae60",
    "left":            "#1a7a45",
}

def _leaning_colour(leaning_text: str) -> str:
    lt = (leaning_text or "").lower()
    for key, colour in LEANING_COLOURS.items():
        if key in lt:
            return colour
    return "#888"


def build_media_tab():
    st.subheader("Media")
    st.caption(
        "Who owns the news you read, how they're funded, and where their political interests lie. "
        "Three companies control most of what Australians see and hear."
    )

    # ── Trust methodology ──────────────────────────────────────────────────────
    with st.expander("How we evaluate trustworthiness"):
        st.markdown("""
**Trust score (1–10)** is assessed across four dimensions:

| Dimension | What it measures |
|-----------|-----------------|
| **Editorial independence** | Is the outlet free from owner interference? Does the owner have commercial or political interests that could influence coverage? |
| **Transparency** | Does the outlet clearly disclose ownership, funding, and corrections? Are conflicts of interest declared? |
| **Accuracy track record** | History of ACMA rulings, Press Council adjudications, retractions, and fact-check performance. |
| **Source diversity** | Does reporting draw on multiple perspectives, or does it consistently platform one side? |

**Political leaning** is assessed by comparing editorial positions, story selection, framing,
and endorsed candidates over multiple election cycles. It is not a measure of quality —
a centre-right outlet can be highly trustworthy, and a centre-left outlet can be unreliable.

**Key principle:** Ownership matters more than stated values. A media outlet's coverage
will, over time, reflect the commercial and political interests of whoever controls it.
""")

    # ── Most frequent sources ──────────────────────────────────────────────────
    st.subheader("Sources in our data")

    view_mode = st.radio(
        "Sort by", ["Most frequently cited", "Most recently cited"],
        horizontal=True, key="media_sort",
    )

    if view_mode == "Most frequently cited":
        source_stats = query("""
            SELECT source, COUNT(*) AS citations, MAX(published_date) AS latest
            FROM politician_news
            WHERE source NOT LIKE '%wikipedia%'
              AND source NOT LIKE '%facebook%'
            GROUP BY source
            ORDER BY citations DESC
            LIMIT 30
        """)
    else:
        source_stats = query("""
            SELECT source, COUNT(*) AS citations, MAX(published_date) AS latest
            FROM politician_news
            WHERE source NOT LIKE '%wikipedia%'
              AND source NOT LIKE '%facebook%'
            GROUP BY source
            ORDER BY latest DESC
            LIMIT 30
        """)

    media_profiles = query("SELECT * FROM media_profiles")
    profile_map = {}
    if not media_profiles.empty:
        for _, mp in media_profiles.iterrows():
            profile_map[mp["source_name"].lower()] = mp

    if source_stats.empty:
        st.info("No news sources found. Run the news scraper first.")
        return

    for _, row in source_stats.iterrows():
        source = row["source"]
        citations = int(row["citations"])
        latest = (row["latest"] or "")[:10]

        profile = profile_map.get(source.lower())

        if profile is not None:
            trust = int(profile["trust_score"] or 5)
            trust_colour = TRUST_COLOURS.get(trust, "#888")
            leaning = profile["political_leaning"] or "Unknown"
            leaning_col = _leaning_colour(leaning)
            owner = profile["owner"] or "Unknown"

            # Header with badges
            st.markdown(
                f'<div style="border-left:4px solid {trust_colour};padding:10px 14px;'
                f'margin:8px 0 4px;background:rgba(255,255,255,0.03);'
                f'border-radius:0 6px 6px 0">'
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:flex-start;flex-wrap:wrap;gap:8px">'
                f'<div>'
                f'<div style="font-size:16px;font-weight:700">{source}</div>'
                f'<div style="font-size:12px;color:#888;margin-top:2px">'
                f'Owned by: {owner}</div>'
                f'</div>'
                f'<div style="display:flex;gap:6px;flex-wrap:wrap">'
                f'<span style="font-size:11px;background:{trust_colour};color:#fff;'
                f'padding:2px 10px;border-radius:8px">Trust: {trust}/10</span>'
                f'<span style="font-size:11px;background:{leaning_col};color:#fff;'
                f'padding:2px 10px;border-radius:8px">{leaning}</span>'
                f'</div></div>'
                f'<div style="font-size:12px;color:#888;margin-top:6px">'
                f'Cited {citations} time{"s" if citations != 1 else ""} '
                f'— last: {latest} '
                f'— Funding: {profile["funding_model"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            with st.expander("Ownership, funding & political interests"):
                if profile.get("ownership_notes"):
                    st.markdown("**Ownership**")
                    st.markdown(profile["ownership_notes"])

                if profile.get("political_interests"):
                    st.markdown("**Political interests**")
                    st.markdown(
                        f'<div style="font-size:13px;border-left:3px solid {leaning_col};'
                        f'padding:6px 10px;margin:4px 0;color:#ccc">'
                        f'{profile["political_interests"]}</div>',
                        unsafe_allow_html=True,
                    )

                if profile.get("trust_method"):
                    st.markdown("**Trust assessment**")
                    st.caption(profile["trust_method"])

                if profile.get("source_url"):
                    st.markdown(f"[Visit site]({profile['source_url']})")

        else:
            # No profile — basic listing
            st.markdown(
                f'<div style="border-left:4px solid #444;padding:8px 14px;'
                f'margin:6px 0;background:rgba(255,255,255,0.02);'
                f'border-radius:0 6px 6px 0">'
                f'<div style="font-size:14px;font-weight:600">{source}</div>'
                f'<div style="font-size:12px;color:#888">'
                f'Cited {citations} time{"s" if citations != 1 else ""} '
                f'— last: {latest} — No profile available</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()

    # ── Ownership concentration map ────────────────────────────────────────────
    st.subheader("Who owns what")
    st.caption(
        "Australian media is among the most concentrated in the democratic world. "
        "Three entities control the vast majority of what Australians read, watch, and hear."
    )

    owners = {}
    for _, mp in media_profiles.iterrows():
        parent = mp["parent_company"] or "Unknown"
        owners.setdefault(parent, []).append(mp)

    for parent, outlets in sorted(owners.items(), key=lambda x: -len(x[1])):
        owner_name = outlets[0]["owner"] or "Unknown"
        st.markdown(
            f'<div style="font-size:15px;font-weight:700;margin-top:12px">'
            f'{parent}</div>'
            f'<div style="font-size:12px;color:#888;margin-bottom:6px">'
            f'Controlled by: {owner_name} — {len(outlets)} outlet{"s" if len(outlets) != 1 else ""}</div>',
            unsafe_allow_html=True,
        )
        for o in outlets:
            trust = int(o["trust_score"] or 5)
            leaning = o["political_leaning"] or "Unknown"
            st.markdown(
                f'<div style="font-size:13px;margin:2px 0 2px 16px;color:#ccc">'
                f'{o["source_name"]} '
                f'<span style="color:{TRUST_COLOURS.get(trust, "#888")};font-size:11px">'
                f'Trust: {trust}/10</span> '
                f'<span style="color:{_leaning_colour(leaning)};font-size:11px">'
                f'{leaning}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown("""
**Why this matters:**
When one company owns 65% of newspaper circulation (News Corp), the owner's political
preferences become systemic bias — not because individual journalists are biased,
but because editorial hiring, story selection, and framing decisions flow from the top.
A healthy democracy requires media pluralism: diverse ownership, diverse funding models,
and transparent editorial governance.
""")


with tab_media:
    build_media_tab()


# ── How AI Works ──────────────────────────────────────────────────────────────

def build_ai_explainer_tab():
    import json as _json_ex

    st.subheader("How the AI works")

    st.caption(
        "Every night, an AI reads the latest news about every politician in parliament "
        "and scores them on scandal and integrity. Here's exactly how it works, "
        "what the scores mean, and where it can get things wrong."
    )

    st.divider()

    # ── Section 1: The process ────────────────────────────────────────────────
    st.markdown("### The nightly analysis process")
    st.markdown("""
Every night, Pollygraph runs an automated pipeline:

1. **Collect news** — up to 15 recent headlines per politician are gathered from the previous
   14 days of media coverage, sourced from Google News.
2. **Send to AI** — the headlines are sent to Google Gemini (a large language model) along with
   the politician's name, party, and chamber. The AI is instructed to act as a non-partisan
   political integrity analyst.
3. **Structured output** — the AI returns a JSON object containing six fields: a sentiment
   rating, a heat score, a positive score, a summary, a list of flagged concerns, and a list
   of positive notes.
4. **Store and display** — the results are saved to the database and displayed on politician
   profiles, comparison views, and list pages across Pollygraph.

The AI has no memory between runs. Each nightly analysis starts fresh from that day's headlines,
so scores can change as the news cycle moves on.
""")

    st.divider()

    # ── Section 2: The integrity bar ──────────────────────────────────────────
    st.markdown("### The integrity bar")
    st.markdown("""
The bar you see on every politician's profile has two sides that work independently:
""")

    col_demo_l, col_demo_r = st.columns(2)
    with col_demo_l:
        st.markdown(
            bipolar_bar(7, 2),
            unsafe_allow_html=True,
        )
        st.caption("High scandal, low integrity contribution")
    with col_demo_r:
        st.markdown(
            bipolar_bar(1, 8),
            unsafe_allow_html=True,
        )
        st.caption("Low scandal, high integrity contribution")

    st.markdown("""
- **Red bar (left side) — Heat Score (1–10):** measures genuine scandal, hypocrisy, or
  ethical failure. A score of 1 means the politician has virtually no negative coverage.
  A score of 10 means they are at the centre of a major scandal. This score only rises for
  genuinely bad conduct — corruption, broken promises, conflicts of interest, or misleading
  the public. It does **not** penalise politicians for being outspoken, challenging the
  government, or championing unpopular causes. Those are signs of integrity, not scandal.

- **Green bar (right side) — Positive Score (1–10):** measures integrity and positive
  contribution. A score of 1 means little notable positive activity. A score of 10 means
  exceptional achievement — constructive legislation, accountability efforts, principled
  stands, or evidence of walking the talk. A politician who attracts media attention by
  challenging powerful interests or demanding transparency should score high here.

These two scores are completely independent. A politician can score high on both (scandal-prone
but also doing good work), low on both (quiet backbencher), or any combination.
""")

    st.markdown("##### What each score range means")
    score_col1, score_col2 = st.columns(2)
    with score_col1:
        st.markdown("""
**Heat Score (red, left)**
| Range | Meaning |
|-------|---------|
| 1–2 | Minimal scrutiny, no controversy |
| 3–4 | Some critical coverage, minor issues |
| 5–6 | Significant negative attention |
| 7–8 | Serious scandal or sustained criticism |
| 9–10 | Major scandal, potential legal/ethical crisis |
""")
    with score_col2:
        st.markdown("""
**Positive Score (green, right)**
| Range | Meaning |
|-------|---------|
| 1–2 | Little notable positive coverage |
| 3–4 | Some constructive activity or advocacy |
| 5–6 | Strong positive contributions noted |
| 7–8 | Significant achievements or principled stands |
| 9–10 | Exceptional integrity or landmark contribution |
""")

    st.divider()

    # ── Section 3: Live examples ──────────────────────────────────────────────
    st.markdown("### Live examples from the database")
    st.markdown("""
Below are real examples drawn from the current Pollygraph database. These illustrate how the AI
distinguishes between different types of political coverage.
""")

    # Example: high heat
    high_heat = query("""
        SELECT p.name, p.party, a.heat_score, a.sentiment, a.summary,
               a.rhetoric_flags,
               COALESCE(json_extract(a.rhetoric_flags, '$.positive_score'), 0) AS positive_score
        FROM politicians p
        JOIN ai_analysis a ON a.politician_id = p.id
        WHERE a.heat_score >= 6
        ORDER BY a.heat_score DESC
        LIMIT 1
    """)

    # Example: high positive
    high_pos = query("""
        SELECT p.name, p.party, a.heat_score, a.sentiment, a.summary,
               a.rhetoric_flags,
               COALESCE(json_extract(a.rhetoric_flags, '$.positive_score'), 0) AS positive_score
        FROM politicians p
        JOIN ai_analysis a ON a.politician_id = p.id
        WHERE COALESCE(json_extract(a.rhetoric_flags, '$.positive_score'), 0) >= 5
              AND a.heat_score <= 2
        ORDER BY json_extract(a.rhetoric_flags, '$.positive_score') DESC
        LIMIT 1
    """)

    # Example: quiet / neutral
    neutral_ex = query("""
        SELECT p.name, p.party, a.heat_score, a.sentiment, a.summary,
               a.rhetoric_flags,
               COALESCE(json_extract(a.rhetoric_flags, '$.positive_score'), 0) AS positive_score
        FROM politicians p
        JOIN ai_analysis a ON a.politician_id = p.id
        WHERE a.heat_score <= 2
              AND COALESCE(json_extract(a.rhetoric_flags, '$.positive_score'), 0) <= 2
              AND a.summary IS NOT NULL AND a.summary != ''
        LIMIT 1
    """)

    examples = [
        ("High heat — genuine scandal or sustained criticism", high_heat, "#e74c3c"),
        ("High positive — integrity and constructive contribution", high_pos, "#27ae60"),
        ("Neutral — routine coverage, no strong signals", neutral_ex, "#888"),
    ]

    for title, df, colour in examples:
        if df.empty:
            continue
        row = df.iloc[0]
        heat = int(row.get("heat_score") or 0)
        pos  = int(row.get("positive_score") or 0)

        flags_raw = row.get("rhetoric_flags") or "{}"
        try:
            flags_data = _json_ex.loads(flags_raw)
            rhetoric_flags = flags_data.get("rhetoric_flags", [])
            positive_notes = flags_data.get("positive_notes", [])
        except Exception:
            rhetoric_flags, positive_notes = [], []

        st.markdown(
            f'<div style="border-left:4px solid {colour};padding-left:12px;margin:16px 0 8px 0">'
            f'<strong>{title}</strong></div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{row['name']}** ({row['party']})")
        st.markdown(bipolar_bar(heat, pos), unsafe_allow_html=True)
        st.markdown(f"*{row['summary']}*")
        st.caption(f"Sentiment: {row['sentiment']}")
        if rhetoric_flags:
            st.markdown("**Flagged concerns:**")
            for f in rhetoric_flags:
                st.markdown(f"- {f}")
        if positive_notes:
            st.markdown("**Positive notes:**")
            for n in positive_notes:
                st.markdown(f"- {n}")

    st.divider()

    # ── Section 4: Sentiment ──────────────────────────────────────────────────
    st.markdown("### Sentiment")
    st.markdown("""
Each politician also receives an overall **sentiment** label based on the tone of their recent
coverage. This is a single word — not a score — that gives a quick read on how the media is
currently framing them.

| Sentiment | What it means |
|-----------|---------------|
| **Positive** | Coverage is predominantly favourable — achievements, praise, good news |
| **Negative** | Coverage is predominantly critical — scandal, failure, backlash |
| **Mixed** | A blend of positive and negative — competing narratives |
| **Neutral** | Routine or procedural coverage — no strong positive or negative framing |

Sentiment is independent of the heat and positive scores. A politician can have "mixed" sentiment
with a high positive score (media is split, but the AI sees genuine achievements) or "negative"
sentiment with a low heat score (critical coverage that doesn't rise to the level of scandal).
""")

    st.divider()

    # ── Section 5: Flagged concerns & positive notes ──────────────────────────
    st.markdown("### Flagged concerns & positive notes")
    st.markdown("""
Beneath the integrity bar on each profile, you may see two lists:

- **Flagged concerns** (shown in red context) — specific issues the AI identified in the
  headlines: potential hypocrisy, rhetoric that contradicts voting records, misleading framing,
  conflicts of interest, or unexplained absences. These are not accusations — they are patterns
  the AI noticed in media coverage that warrant attention.

- **Positive notes** (shown in green context) — genuine achievements, constructive policy work,
  principled stands, or community advocacy that the AI identified. These balance the picture
  and ensure the analysis is not purely negative.

Both lists are drawn directly from headlines. The AI does not investigate or verify claims —
it surfaces what the media is reporting and highlights patterns. It is a starting point for
your own research, not a final verdict.
""")

    st.divider()

    # ── Section 6: Limitations ────────────────────────────────────────────────
    st.markdown("### Limitations and transparency")
    st.markdown("""
No AI system is perfect. Here is what you should know about the limitations of Pollygraph's analysis:

- **Headlines only** — the AI reads headlines and source names, not full articles. This means
  it can be influenced by sensationalist or misleading headlines, just as any reader would be.
- **14-day window** — only the most recent two weeks of coverage are analysed. Long-running
  issues that have dropped out of the news cycle will not appear.
- **No memory** — each nightly run is independent. The AI does not remember previous analyses,
  so a politician's score can shift dramatically when the news cycle changes.
- **Media bias** — if headlines about a politician come predominantly from outlets with a
  particular political leaning, the AI's assessment will reflect that skew. Pollygraph's Media tab
  provides context on media ownership and bias to help you account for this.
- **Not a verdict** — the AI is a tool for surfacing patterns, not a judge. It can make
  mistakes, misinterpret sarcasm, or miss context that a human reader would catch. Always
  cross-reference with primary sources.
- **Model and cost** — Pollygraph uses Google Gemini Flash (free tier) to keep the project
  accessible and free. This model is capable but not infallible.
""")

    # ── Stats footer ──────────────────────────────────────────────────────────
    stats = query("""
        SELECT COUNT(*) as total,
               ROUND(AVG(heat_score), 1) as avg_heat,
               ROUND(AVG(COALESCE(json_extract(rhetoric_flags, '$.positive_score'), 0)), 1)
                   as avg_positive
        FROM ai_analysis
    """)
    if not stats.empty:
        s = stats.iloc[0]
        st.divider()
        st.caption(
            f"Database snapshot: {int(s['total'])} politicians analysed · "
            f"Average heat score: {s['avg_heat']}/10 · "
            f"Average positive score: {s['avg_positive']}/10"
        )


with tab_ai_explainer:
    build_ai_explainer_tab()
