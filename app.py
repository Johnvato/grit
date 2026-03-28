import streamlit as st
import sqlite3
import pandas as pd
import datetime

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


@st.cache_resource
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)


conn = get_conn()


def query(sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


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


def profile_expander(name: str):
    prof = query("SELECT * FROM profiles WHERE name = ?", (name,))
    if prof.empty:
        return
    p = prof.iloc[0]

    with st.expander("Profile & Risk Assessment"):
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
                    st.image(row["photo_url"], width=90)
                st.markdown(f"**{row['name']}**")
                location = row.get("state") or row.get("electorate", "")
                st.caption(
                    f"{row['party']}  \n"
                    f"{location}  \n"
                    f"Attendance: {row.get('attendance_%', '—')}  \n"
                    f"Rebellions: {int(row['rebellions'])}  \n"
                    f"⏳ {days_left:,}d"
                )
                profile_expander(row["name"])


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Mobile: 2-column grid */
@media screen and (max-width: 640px) {
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
    selected_party = st.selectbox("Filter by party", ["All"] + parties, key=f"party_{chamber}")

    if selected_party == "All":
        mps = query("""
            SELECT id, name, party, electorate, state, photo_url,
                   votes_attended, votes_possible, rebellions
            FROM politicians WHERE chamber=? ORDER BY name
        """, (chamber,))
    else:
        mps = query("""
            SELECT id, name, party, electorate, state, photo_url,
                   votes_attended, votes_possible, rebellions
            FROM politicians WHERE chamber=? AND party=? ORDER BY name
        """, (chamber, selected_party))

    if mps.empty:
        st.info("No data yet. Run: python sync_data.py")
        return

    mps["attendance_%"] = mps.apply(
        lambda r: f"{100 * r['votes_attended'] / r['votes_possible']:.0f}%"
        if r["votes_possible"] > 0 else "—",
        axis=1,
    )
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
                    SELECT id, name, party, electorate, state, photo_url,
                           votes_attended, votes_possible, rebellions
                    FROM politicians
                    WHERE chamber='representatives'
                      AND electorate IN ({placeholders})
                    ORDER BY name
                """, tuple(electorates))
                st.info(
                    f"Postcode **{search.strip()}** falls in: "
                    + ", ".join(f"**{e}**" for e in sorted(electorates))
                )
            else:
                reps_df = pd.DataFrame()
                st.warning(f"No electorate found for postcode {search.strip()}.")
        else:
            reps_df = query("""
                SELECT id, name, party, electorate, state, photo_url,
                       votes_attended, votes_possible, rebellions
                FROM politicians
                WHERE chamber='representatives'
                  AND (LOWER(name) LIKE ? OR LOWER(electorate) LIKE ?)
                ORDER BY name
            """, (f"%{search.lower()}%", f"%{search.lower()}%"))

        if not reps_df.empty:
            reps_df["attendance_%"] = reps_df.apply(
                lambda r: f"{100 * r['votes_attended'] / r['votes_possible']:.0f}%"
                if r["votes_possible"] > 0 else "—", axis=1)
            politician_grid(reps_df)
            st.caption(f"{len(reps_df)} shown.")
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
            SELECT id, date, house, name, aye_votes, no_votes, rebellions, summary
            FROM divisions WHERE house=?
            ORDER BY date DESC, number DESC LIMIT 100
        """, (hf,))
    else:
        divs = query("""
            SELECT id, date, house, name, aye_votes, no_votes, rebellions, summary
            FROM divisions ORDER BY date DESC, number DESC LIMIT 100
        """)

    if divs.empty:
        st.info("No division data yet.")
    else:
        event = st.dataframe(
            divs[["date", "house", "name", "aye_votes", "no_votes", "rebellions"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        selected_rows = event.selection.rows if event.selection else []
        row = divs.iloc[selected_rows[0]] if selected_rows else divs.iloc[0]

        st.divider()
        st.subheader(row["name"])
        st.caption(f"{row['house'].title()} — {row['date']}")

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
            st.markdown("**Summary:**")
            st.markdown(row["summary"])

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

            profile_expander(selected_mp)

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
