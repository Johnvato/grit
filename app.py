import streamlit as st
import sqlite3
import pandas as pd
import datetime
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Polygraph", layout="wide")

DB = "grit_cache.db"

# ── Comparison state ───────────────────────────────────────────────────────────
if "compare_ids" not in st.session_state:
    st.session_state.compare_ids = set()

ELECTION_DATE_APPROX = True
NEXT_ELECTION = datetime.date(2028, 5, 6)
LAST_ELECTION = datetime.date(2025, 5, 3)

RISK_COLOURS = {
    "High":     "#e94560",
    "Moderate": "#f5a623",
    "Low":      "#27ae60",
}


def query(sql, params=()):
    with sqlite3.connect(DB, check_same_thread=False) as _conn:
        return pd.read_sql_query(sql, _conn, params=params)


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

            st.markdown(
                f"""
                <div style="background:#1a1a2e;border-radius:10px;padding:16px;margin-bottom:8px">
                  <div style="color:#aaa;font-size:12px;text-transform:uppercase;letter-spacing:1px">
                    2025 Result
                  </div>
                  <div style="display:flex;align-items:center;gap:10px;margin:8px 0">
                    <span style="background:{p_col};color:#fff;padding:3px 10px;
                                 border-radius:4px;font-weight:700;font-size:14px">{party}</span>
                    <span style="background:{colour};color:#fff;padding:3px 10px;
                                 border-radius:4px;font-weight:600;font-size:13px">{mtype}</span>
                  </div>
                  <div style="color:#fff;font-size:28px;font-weight:700;line-height:1">
                    {m['margin_pct']:.1f}%
                  </div>
                  <div style="color:#aaa;font-size:12px">margin</div>
                  <hr style="border-color:#333;margin:10px 0">
                  <div style="color:#ddd;font-size:13px">
                    ALP: {m['alp_pct']:.1f}% &nbsp;|&nbsp; Coalition: {m['coalition_pct']:.1f}%
                  </div>
                  <div style="color:#aaa;font-size:12px">
                    Swing: {m['swing']:+.1f}% &nbsp;|&nbsp; {int(m['total_votes']):,} votes
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

            st_folium(m_map, height=280, use_container_width=True)
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

    st.markdown("**AI Analysis** *(updated nightly)*")
    st.markdown(
        bipolar_bar(int(a["heat_score"] or 0), pos_score),
        unsafe_allow_html=True,
    )
    cols = st.columns([2, 1])
    with cols[0]:
        st.markdown(a["summary"] or "")
    with cols[1]:
        st.caption(f"Sentiment: {a['sentiment'] or 'neutral'}")

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


def profile_expander(name: str, politician_id: int = None, photo_url: str = None):
    prof = query("SELECT * FROM profiles WHERE name = ?", (name,))
    bio  = query("SELECT * FROM politician_bio WHERE politician_id = ?", (politician_id,)) if politician_id else None
    pol  = query("SELECT party, chamber FROM politicians WHERE id = ?", (politician_id,)) if politician_id else None

    has_profile = not prof.empty
    has_bio     = bio is not None and not bio.empty
    has_ai      = politician_id is not None
    has_votes   = pol is not None and not pol.empty

    if not has_profile and not has_bio and not has_ai:
        return

    with st.expander("▶ Profile, News & AI Analysis"):
        # Photo shown on mobile (hidden on desktop via .desktop-photo CSS)
        if photo_url:
            st.markdown(
                f'<div class="mobile-photo">'
                f'<img src="{photo_url}" width="100" '
                f'style="border-radius:8px;margin-bottom:8px;object-fit:cover">'
                f'</div>',
                unsafe_allow_html=True,
            )
        # ── Wikipedia bio ────────────────────────────────────────────────────
        if has_bio and bio.iloc[0]["wikipedia_summary"]:
            b = bio.iloc[0]
            st.markdown("**Background:**")
            st.markdown(b["wikipedia_summary"][:600] + ("…" if len(b["wikipedia_summary"]) > 600 else ""))
            if b["wikipedia_url"]:
                st.caption(f"[Read more on Wikipedia →]({b['wikipedia_url']})")

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
                        f'<div class="desktop-photo">'
                        f'<img src="{row["photo_url"]}" width="90" '
                        f'style="border-radius:6px;object-fit:cover">'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(f"**{row['name']}**")
                location = row.get("state") or row.get("electorate", "")
                att = row.get("attendance_%", "—")
                reb = int(row["rebellions"])
                reb_label = f"Reb: {reb}*" if reb > 0 else "Reb: 0"
                st.markdown(
                    f'<div style="font-size:11px;color:#888;line-height:1.4;margin-bottom:4px">'
                    f'{row["party"]}<br>'
                    f'{location}<br>'
                    f'Att: {att} · {reb_label}<br>'
                    f'{days_left:,}d'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                heat = int(row.get("heat_score") or 0)
                pos  = int(row.get("positive_score") or 0)
                st.markdown(bipolar_bar(heat, pos, compact=True), unsafe_allow_html=True)

                # Compare checkbox
                in_compare = pid in st.session_state.compare_ids
                if st.checkbox(
                    "Compare" if not in_compare else "In compare",
                    key=f"cmp_{tab_key}_{pid}",
                    value=in_compare,
                ):
                    st.session_state.compare_ids.add(pid)
                else:
                    st.session_state.compare_ids.discard(pid)

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

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Polygraph")
st.caption("Reality vs rhetoric in Australian politics.")

days_left = days_until(NEXT_ELECTION)
approx_label = "≈ " if ELECTION_DATE_APPROX else ""
mandate_pct = round(100 * (1 - days_left / (NEXT_ELECTION - LAST_ELECTION).days), 1)

# Countdown label: years & months normally, days-only in the final 100 days
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
    f'Mandate elapsed: <strong>{mandate_pct}%</strong></div>',
    unsafe_allow_html=True,
)
st.progress(mandate_pct / 100)
st.caption(
    "Australian governments serve up to 3 years from election day. "
    "This bar shows how much of the current term has passed — at 100% an election must be called."
)

# ── Postcode filter ───────────────────────────────────────────────────────────
st.divider()
with st.expander("Find your local representatives by postcode", expanded=False):
    postcode_input = st.text_input("Enter your postcode", max_chars=4, placeholder="e.g. 3006")
    state_from_pc = None
    if postcode_input:
        state_from_pc = postcode_to_state(postcode_input)
        if state_from_pc:
            st.success(f"**{postcode_input}** → {state_from_pc}")
            senators_for_state = query(
                "SELECT name, party, electorate FROM politicians WHERE chamber='senate' AND state=? ORDER BY name",
                (state_from_pc,)
            )
            if not senators_for_state.empty:
                st.markdown(f"**Your senators ({state_from_pc}):**")
                for _, s in senators_for_state.iterrows():
                    st.markdown(f"- {s['name']} *(_{s['party']}_)*")

            electorates_for_pc = query(
                "SELECT electorate FROM postcode_electorates WHERE postcode = ?",
                (postcode_input.strip(),)
            )["electorate"].tolist()
            if electorates_for_pc:
                st.markdown(f"**Your electorate(s):** {', '.join(f'**{e}**' for e in sorted(electorates_for_pc))}")
                placeholders = ",".join("?" * len(electorates_for_pc))
                local_reps = query(f"""
                    SELECT name, party, electorate FROM politicians
                    WHERE chamber='representatives' AND electorate IN ({placeholders})
                    ORDER BY name
                """, tuple(electorates_for_pc))
                if not local_reps.empty:
                    st.markdown("**Your House of Reps MP(s):**")
                    for _, rep in local_reps.iterrows():
                        st.markdown(f"- {rep['name']} *(_{rep['party']}_, {rep['electorate']})*")
                st.divider()
                for elec in sorted(electorates_for_pc):
                    electorate_card(elec)
            else:
                st.markdown(
                    "**Find your House of Reps MP:**  \n"
                    "[Search AEC electorate finder →](https://electorate.aec.gov.au/)"
                )
        else:
            st.warning("Postcode not recognised. Check and try again.")

st.divider()

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

if not _promise_summary.empty:
    _all_promises = query("SELECT * FROM promises ORDER BY category, promise")
    st.subheader("2025 Election Promises")

    # ── Government party: full delivery bar + expandable list ─────────────────
    _gov_data    = _promise_summary[_promise_summary["party"] == GOVERNMENT_PARTY]
    _gov_counts  = {r["status"]: r["n"] for _, r in _gov_data.iterrows()}
    _gov_total   = sum(_gov_counts.values())
    _gov_delivered = _gov_counts.get("Delivered", 0)

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
            f'<div style="margin:4px 0 8px">{_leg_parts}</div>'
            f'<div style="font-size:12px;color:#aaa">{_gov_delivered}/{_gov_total} promises delivered</div>',
            unsafe_allow_html=True,
        )

        with st.expander(f"See all {_gov_total} {GOVERNMENT_PARTY} promises"):
            _gov_promises = _all_promises[_all_promises["party"] == GOVERNMENT_PARTY]
            for _cat in sorted(_gov_promises["category"].unique()):
                st.markdown(f"**{_cat}**")
                _cat_df = _gov_promises[_gov_promises["category"] == _cat]
                st.markdown(_promise_list_html(_cat_df), unsafe_allow_html=True)

    st.divider()

    # ── Opposition parties: compact platform expanders (no delivery bar) ───────
    _opp_parties = [p for p in sorted(_promise_summary["party"].unique()) if p != GOVERNMENT_PARTY]
    if _opp_parties:
        st.markdown(
            '<div style="font-size:13px;color:#aaa;margin-bottom:6px">'
            '**Opposition platforms** — what they promised if elected in 2025</div>',
            unsafe_allow_html=True,
        )
        _opp_cols = st.columns(len(_opp_parties))
        for _col, _party in zip(_opp_cols, _opp_parties):
            _pdata  = _promise_summary[_promise_summary["party"] == _party]
            _counts = {r["status"]: r["n"] for _, r in _pdata.iterrows()}
            _total  = sum(_counts.values())
            with _col:
                with st.expander(f"{_party} — {_total} promises"):
                    _party_promises = _all_promises[_all_promises["party"] == _party]
                    for _cat in sorted(_party_promises["category"].unique()):
                        st.markdown(f"**{_cat}**")
                        _cat_df = _party_promises[_party_promises["category"] == _cat]
                        st.markdown(_promise_list_html(_cat_df, is_government=False), unsafe_allow_html=True)

st.divider()

# ── Compare banner (shows when 1+ politicians selected) ───────────────────────
n_compare = len(st.session_state.compare_ids)
if n_compare > 0:
    banner_col, clear_col = st.columns([5, 1])
    with banner_col:
        if n_compare == 1:
            cid = next(iter(st.session_state.compare_ids))
            cname = query("SELECT name FROM politicians WHERE id=?", (cid,))
            cname_str = cname.iloc[0]["name"] if not cname.empty else str(cid)
            st.info(f"**1 selected:** {cname_str} — select at least one more to compare.")
        else:
            cnames = query(
                f"SELECT name FROM politicians WHERE id IN ({','.join('?'*n_compare)})",
                tuple(st.session_state.compare_ids),
            )["name"].tolist()
            st.success(f"**{n_compare} selected for comparison:** {', '.join(cnames)} — see the **Compare** tab.")
    with clear_col:
        if st.button("Clear", key="clear_compare_btn"):
            st.session_state.compare_ids = set()
            st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────
(tab_reps, tab_senate, tab_indep, tab_divs, tab_votes,
 tab_compare, tab_promises, tab_bills, tab_revolving) = st.tabs([
    "House of Reps", "Senate", "Independents", "Divisions", "Vote Explorer",
    "Compare", "Promises", "False Promises", "Revolving Door",
])


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
            ["Name (A–Z)", "Rebellions ↓", "Rebellions ↑", "Attendance ↓", "Attendance ↑", "Heat Score ↓"],
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
with tab_reps:
    st.subheader("House of Representatives")
    st.caption(
        "The House of Representatives is the lower house of the Australian Parliament, "
        "with 151 members each representing an electorate. Government is formed by the party "
        "that holds a majority here. Members vote on legislation, and their attendance and "
        "rebellion records reveal how closely they follow their party's line."
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
        "The Senate is the upper house, with 76 senators representing states and territories. "
        "It acts as a house of review — scrutinising and amending legislation passed by the House of Reps. "
        "Minor parties and independents often hold the balance of power here, making Senate voting records "
        "particularly revealing of political alliances and deal-making."
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

    st.markdown("""
**Why independents matter — and why voting for them is not a wasted vote.**

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
    st.subheader("Recent Divisions")
    st.caption(
        "A 'division' is a formal vote in Parliament where members are counted for or against. "
        "Divisions decide whether bills become law, whether motions pass, and how public money is spent. "
        "This tab shows recent divisions from both chambers — select one to see how each member voted "
        "and which bills were at stake."
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
            use_container_width=True,
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
    st.subheader("How did each politician vote?")
    st.caption(
        "Look up any MP or senator to see their complete voting record across all synced divisions. "
        "This view makes it easy to see whether a politician's votes match their public statements — "
        "the core of what Polygraph tracks. Filter by aye/no votes to spot patterns, rebellions, "
        "and absences."
    )

    mp_names = query("SELECT name FROM politicians ORDER BY name")["name"].tolist()
    if not mp_names:
        st.info("No data yet.")
    else:
        selected_mp = st.selectbox("Select a politician", mp_names)
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
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Attendance", attendance)
                m2.metric("Rebellions", int(r["rebellions"]))
                m3.metric("Days to election", f"{days_left:,}")
                m4.metric("Mandate elapsed", f"{mandate_pct}%")

            profile_expander(selected_mp, mp_id, photo_url=r.get("photo_url"))

            mp_votes = query("""
                SELECT d.date, d.name AS division, d.house, v.vote
                FROM votes v JOIN divisions d ON d.id = v.division_id
                WHERE v.politician_id = ? ORDER BY d.date DESC
            """, (mp_id,))

            if mp_votes.empty:
                st.info("No vote records yet.")
            else:
                aye = (mp_votes["vote"] == "aye").sum()
                no  = (mp_votes["vote"] == "no").sum()
                c1, c2 = st.columns(2)
                c1.metric("Aye", aye)
                c2.metric("No", no)
                st.dataframe(mp_votes, use_container_width=True, hide_index=True)

# ── Compare ───────────────────────────────────────────────────────────────────
def build_compare_tab():
    import json as _json

    st.caption(
        "Compare politicians side by side — like a product comparison table for democracy. "
        "Select any combination of MPs and senators using the Compare checkbox on their cards, "
        "then view attendance, rebellions, AI sentiment scores, background, and latest news "
        "in parallel columns to spot differences at a glance."
    )

    cids = list(st.session_state.compare_ids)

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
        use_container_width=True,
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
                st.session_state.compare_ids.discard(int(row["id"]))
                st.rerun()


with tab_compare:
    build_compare_tab()

# ── Promises tab ───────────────────────────────────────────────────────────────
def build_promises_tab():
    st.caption(
        "Election promises are the commitments parties make to win your vote. "
        "This tracker holds them accountable — showing which promises the government has delivered, "
        "which are in progress, and which remain unfulfilled. Opposition platforms are included "
        "to show what was offered as an alternative. Tap any promise for evidence and independent scrutiny."
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
    st.subheader("False Promises")
    st.caption(
        "Legislation often sounds reasonable on the surface — but the detail can tell a "
        "different story. This section highlights bills and policies where the stated purpose "
        "masks provisions that disproportionately benefit one group at the expense of another. "
        "Each entry breaks down: what the bill claims to do, what it actually does, "
        "who benefits, who loses, and what independent critics have said."
    )

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
            f'<div style="font-size:12px;color:#888;margin-top:2px">'
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
                f'<div style="font-size:13px;color:#ccc;border-left:3px solid #27ae60;'
                f'padding:6px 10px;margin:4px 0">{b["official_purpose"]}</div>',
                unsafe_allow_html=True,
            )
        with col_does:
            st.markdown("**What it actually does**")
            st.markdown(
                f'<div style="font-size:13px;color:#ccc;border-left:3px solid #e94560;'
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
                    f'<div style="font-size:13px;color:#27ae60;border-left:3px solid #27ae60;'
                    f'padding:6px 10px;margin:4px 0">{b["who_benefits"]}</div>',
                    unsafe_allow_html=True,
                )

            if b.get("who_loses"):
                st.markdown("**Who loses**")
                st.markdown(
                    f'<div style="font-size:13px;color:#e94560;border-left:3px solid #e94560;'
                    f'padding:6px 10px;margin:4px 0">{b["who_loses"]}</div>',
                    unsafe_allow_html=True,
                )

            if b.get("criticism"):
                st.divider()
                st.markdown("**Independent criticism**")
                st.markdown(
                    f'<div style="font-size:13px;color:#ccc;padding:4px 0">{b["criticism"]}</div>',
                    unsafe_allow_html=True,
                )
                if b.get("criticism_source"):
                    st.caption(f"Sources: {b['criticism_source']}")

            if b.get("defence"):
                st.divider()
                st.markdown("**Government defence**")
                st.markdown(
                    f'<div style="font-size:13px;color:#aaa;font-style:italic;padding:4px 0">'
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
    st.subheader("The Revolving Door")
    st.caption(
        "When politicians leave office and immediately take jobs in industries they regulated, "
        "it raises a fundamental question: were their decisions in office influenced by the "
        "prospect of future employment? Australia has no mandatory cooling-off period for "
        "federal ministers — unlike the UK (2 years), Canada (2 years), or the US (1–2 years). "
        "This tab documents cases where the post-politics career path suggests the door between "
        "government and industry swings both ways."
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
