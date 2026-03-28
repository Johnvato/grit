import streamlit as st
import sqlite3
import pandas as pd
import datetime
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Project GRIT", layout="wide")

DB = "grit_cache.db"

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
    Bipolar bar: red extends LEFT (controversy), green extends RIGHT (positive).
    Both are independent 1-10 scales. Zero on both = 'not enough information'.
    """
    if controversy == 0 and positive == 0:
        return (
            '<div style="font-size:11px;color:#666;font-style:italic;margin:4px 0">'
            'Not enough information</div>'
        )
    c_pct = max(0, min(100, controversy * 10))
    p_pct = max(0, min(100, positive * 10))
    height = "6px" if compact else "8px"
    font   = "10px" if compact else "11px"
    return f"""
<div style="margin:5px 0 2px 0">
  <div style="display:flex;align-items:center;gap:0;height:{height};border-radius:4px;overflow:hidden;background:#1e1e2e">
    <div style="flex:1;display:flex;justify-content:flex-end">
      <div style="width:{c_pct}%;height:100%;background:linear-gradient(to left,#e74c3c,#922b21)"></div>
    </div>
    <div style="width:2px;height:140%;background:#444;flex-shrink:0"></div>
    <div style="flex:1">
      <div style="width:{p_pct}%;height:100%;background:linear-gradient(to right,#27ae60,#1a7a45)"></div>
    </div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:{font};color:#888;margin-top:2px">
    <span style="color:#e74c3c">{'⚠ ' + str(controversy) + '/10' if controversy else ''}</span>
    <span style="color:#27ae60">{'✓ ' + str(positive) + '/10' if positive else ''}</span>
  </div>
</div>"""


def heat_badge(score: int) -> str:
    """Legacy single-score badge used in the AI analysis section."""
    HEAT_COLOURS = ["#27ae60","#2ecc71","#f1c40f","#f39c12","#e67e22","#e74c3c","#c0392b","#922b21","#7b241c","#641e16"]
    score = max(1, min(10, score))
    colour = HEAT_COLOURS[score - 1]
    label = ["Very Low","Low","Low-Mod","Moderate","Mod-High","High","High","Very High","Very High","Extreme"][score - 1]
    return f'<span style="background:{colour};color:#fff;padding:2px 10px;border-radius:4px;font-size:12px;font-weight:700">🌡 {score}/10 — {label}</span>'


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
        st.markdown("**⚠️ Flagged concerns:**")
        for flag in rhetoric_flags:
            st.markdown(f"- {flag}")
    if positive_notes:
        st.markdown("**✅ Positive notes:**")
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
            f"⚡ Rebellions ({len(reb)})",
            f"📅 Attendance log",
        ])

        with r_tab:
            if reb.empty:
                st.caption("No rebellions detected in synced divisions.")
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
                st.markdown("**✅ Recently attended**")
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
                st.markdown("**❌ Recently missed**")
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

    with st.expander("Profile, News & AI Analysis"):
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


def politician_grid(df, chamber="representatives"):
    days_left = days_until(NEXT_ELECTION)
    cols_per_row = 4
    for i in range(0, len(df), cols_per_row):
        cols = st.columns(cols_per_row, gap="small")
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(df):
                break
            row = df.iloc[idx]
            with col:
                if row.get("photo_url"):
                    # Wrapped in a div hidden on mobile via CSS
                    st.markdown(
                        f'<div class="desktop-photo">'
                        f'<img src="{row["photo_url"]}" width="90" '
                        f'style="border-radius:6px;object-fit:cover">'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(f"**{row['name']}**")
                location = row.get("state") or row.get("electorate", "")
                st.caption(
                    f"{row['party']}  \n"
                    f"{location}  \n"
                    f"Attendance: {row.get('attendance_%', '—')}  \n"
                    f"Rebellions: {int(row['rebellions'])}  \n"
                    f"⏳ {days_left:,}d"
                )
                heat = int(row.get("heat_score") or 0)
                pos  = int(row.get("positive_score") or 0)
                st.markdown(bipolar_bar(heat, pos, compact=True), unsafe_allow_html=True)
                profile_expander(row["name"], int(row["id"]), photo_url=row.get("photo_url"))


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Desktop: show grid photo, hide expander photo */
.desktop-photo { display: block; }
.mobile-photo  { display: none;  }

/* Mobile: hide grid photo, show expander photo, 2-column grid */
@media screen and (max-width: 640px) {
  .desktop-photo { display: none !important; }
  .mobile-photo  { display: block !important; }

  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 45% !important;
    max-width: 50% !important;
    flex: 1 1 45% !important;
  }
}
/* Tighten card padding */
[data-testid="stColumn"] { padding: 4px !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Project GRIT: Truth Engine")
st.caption("Tracking Australian politicians — rhetoric vs. reality.")

days_left = days_until(NEXT_ELECTION)
approx_label = "≈ " if ELECTION_DATE_APPROX else ""
mandate_pct = round(100 * (1 - days_left / (NEXT_ELECTION - LAST_ELECTION).days), 1)

col_a, col_b = st.columns([3, 1])
with col_a:
    st.markdown(
        f"### {approx_label}Next Federal Election: **{days_left:,} days** away",
    )
    st.progress(mandate_pct / 100, text=f"Mandate elapsed: {mandate_pct}%")
with col_b:
    st.metric("Last election", LAST_ELECTION.strftime("%-d %b %Y"))

# ── Postcode filter ───────────────────────────────────────────────────────────
st.divider()
with st.expander("🔍 Find your local representatives by postcode", expanded=False):
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

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_reps, tab_senate, tab_divs, tab_votes = st.tabs([
    "House of Reps", "Senate", "Divisions", "Vote Explorer"
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

    upd_col1, upd_col2 = st.columns(2)
    with upd_col1:
        only_news = st.checkbox("📰 Has recent news", key=f"news_{chamber}")
    with upd_col2:
        only_ai = st.checkbox("🤖 Has AI analysis", key=f"ai_{chamber}")

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

    politician_grid(mps, chamber)
    st.caption(f"{len(mps)} shown.")


# ── House of Reps ─────────────────────────────────────────────────────────────
with tab_reps:
    st.subheader("House of Representatives")
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
            politician_grid(reps_df)
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
    build_mp_tab("senate")

# ── Divisions ─────────────────────────────────────────────────────────────────
with tab_divs:
    st.subheader("Recent Divisions")

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
