import streamlit as st
import sqlite3
import pandas as pd
import datetime

st.set_page_config(page_title="Project GRIT", layout="wide")

DB = "grit_cache.db"

# Approximate next federal election — update to exact date once announced
ELECTION_DATE_APPROX = True
NEXT_ELECTION = datetime.date(2028, 5, 6)   # ~first Sat in May 2028
LAST_ELECTION = datetime.date(2025, 5, 3)


@st.cache_resource
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)


conn = get_conn()


def query(sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


def days_until(target: datetime.date) -> int:
    return (target - datetime.date.today()).days


def election_countdown_html() -> str:
    days = days_until(NEXT_ELECTION)
    years, rem = divmod(days, 365)
    months = rem // 30
    label = "≈ Next Federal Election" if ELECTION_DATE_APPROX else "Next Federal Election"
    approx = " (approximate)" if ELECTION_DATE_APPROX else f" — {NEXT_ELECTION.strftime('%-d %B %Y')}"
    return f"""
    <div style="background:linear-gradient(90deg,#1a1a2e,#16213e);
                border-radius:12px;padding:20px 28px;margin-bottom:24px;
                display:flex;align-items:center;justify-content:space-between;
                flex-wrap:wrap;gap:12px;">
      <div>
        <div style="color:#aaa;font-size:13px;letter-spacing:1px;text-transform:uppercase">
          {label}
        </div>
        <div style="color:#e94560;font-size:36px;font-weight:700;line-height:1.1">
          {days:,} days
        </div>
        <div style="color:#aaa;font-size:13px">
          {years}y {months}m remaining{approx}
        </div>
      </div>
      <div style="text-align:right">
        <div style="color:#aaa;font-size:13px">Last election</div>
        <div style="color:#fff;font-size:16px;font-weight:600">
          {LAST_ELECTION.strftime('%-d %B %Y')}
        </div>
        <div style="color:#aaa;font-size:12px">48th Parliament</div>
      </div>
    </div>
    """


# Responsive grid: 4 cols on desktop → 2 on mobile
st.markdown("""
<style>
@media (max-width: 768px) {
  [data-testid="stColumn"] {
    width: calc(50% - 1rem) !important;
    flex: 1 1 calc(50% - 1rem) !important;
    min-width: calc(50% - 1rem) !important;
  }
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Project GRIT: Truth Engine")
st.caption("Tracking Australian MPs — rhetoric vs. reality.")
st.markdown(election_countdown_html(), unsafe_allow_html=True)

days_left = days_until(NEXT_ELECTION)
mp_mandate_pct = round(
    100 * (1 - days_left / (NEXT_ELECTION - LAST_ELECTION).days), 1
)
st.progress(mp_mandate_pct / 100, text=f"Mandate elapsed: {mp_mandate_pct}%")

st.divider()

tab_mps, tab_divisions, tab_votes = st.tabs(["MPs", "Recent Divisions", "Vote Explorer"])

# ── MPs tab ───────────────────────────────────────────────────────────────────
with tab_mps:
    st.subheader("House of Representatives")

    parties = query("SELECT DISTINCT party FROM politicians ORDER BY party")["party"].tolist()
    selected_party = st.selectbox("Filter by party", ["All"] + parties)

    if selected_party == "All":
        mps = query("""
            SELECT id, name, party, electorate, photo_url,
                   votes_attended, votes_possible, rebellions
            FROM politicians ORDER BY name
        """)
    else:
        mps = query("""
            SELECT id, name, party, electorate, photo_url,
                   votes_attended, votes_possible, rebellions
            FROM politicians WHERE party = ? ORDER BY name
        """, (selected_party,))

    if mps.empty:
        st.info("No data yet. Run: python sync_data.py")
    else:
        mps["attendance_%"] = mps.apply(
            lambda r: f"{100 * r['votes_attended'] / r['votes_possible']:.0f}%"
            if r["votes_possible"] > 0 else "—",
            axis=1,
        )

        cols_per_row = 4
        for i in range(0, len(mps), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(mps):
                    break
                row = mps.iloc[idx]
                with col:
                    if row["photo_url"]:
                        st.image(row["photo_url"], width=110)
                    st.markdown(f"**{row['name']}**")
                    st.caption(
                        f"{row['party']}  \n"
                        f"{row['electorate']}  \n"
                        f"Attendance: {row['attendance_%']}  \n"
                        f"Rebellions: {int(row['rebellions'])}  \n"
                        f"⏳ {days_left:,} days to election"
                    )

        st.caption(f"{len(mps)} members shown.")

# ── Divisions tab ─────────────────────────────────────────────────────────────
with tab_divisions:
    st.subheader("Recent Divisions (Votes)")

    divs = query("""
        SELECT d.id, d.date, d.name, d.aye_votes, d.no_votes,
               d.rebellions, d.summary
        FROM divisions d
        ORDER BY d.date DESC, d.number DESC
        LIMIT 100
    """)

    if divs.empty:
        st.info("No division data yet. Run: python sync_data.py")
    else:
        event = st.dataframe(
            divs[["date", "name", "aye_votes", "no_votes", "rebellions"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        selected_rows = event.selection.rows if event.selection else []
        if selected_rows:
            row = divs.iloc[selected_rows[0]]
        else:
            row = divs.iloc[0]

        st.markdown("---")
        st.subheader(row["name"])
        st.caption(f"Date: {row['date']}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Aye", int(row["aye_votes"]))
        col2.metric("No", int(row["no_votes"]))
        col3.metric("Rebellions", int(row["rebellions"]))

        # Linked bills
        bills = query("""
            SELECT b.id, b.title, b.url
            FROM bills b
            JOIN division_bills db ON db.bill_id = b.id
            WHERE db.division_id = ?
        """, (int(row["id"]),))

        if not bills.empty:
            st.markdown("**Linked legislation:**")
            for _, bill in bills.iterrows():
                if bill["url"]:
                    st.markdown(f"- [{bill['title'] or bill['id']}]({bill['url']})")
                else:
                    st.markdown(f"- {bill['title'] or bill['id']}")

        if row["summary"]:
            st.markdown("**Summary:**")
            st.markdown(row["summary"])

# ── Vote Explorer tab ─────────────────────────────────────────────────────────
with tab_votes:
    st.subheader("How did each MP vote?")

    mp_names = query("SELECT name FROM politicians ORDER BY name")["name"].tolist()
    if not mp_names:
        st.info("No data yet. Run: python sync_data.py")
    else:
        selected_mp = st.selectbox("Select an MP", mp_names)

        mp_row = query(
            "SELECT id, photo_url, party, electorate, rebellions, votes_attended, votes_possible "
            "FROM politicians WHERE name = ?", (selected_mp,)
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
                st.caption(f"{r['party']} — {r['electorate']}")
                attendance = (
                    f"{100 * r['votes_attended'] / r['votes_possible']:.0f}%"
                    if r["votes_possible"] > 0 else "—"
                )
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Attendance", attendance)
                m2.metric("Rebellions", int(r["rebellions"]))
                m3.metric("Days to election", f"{days_left:,}")
                m4.metric("Mandate elapsed", f"{mp_mandate_pct}%")

            mp_votes = query("""
                SELECT d.date, d.name AS division, v.vote
                FROM votes v
                JOIN divisions d ON d.id = v.division_id
                WHERE v.politician_id = ?
                ORDER BY d.date DESC
            """, (mp_id,))

            if mp_votes.empty:
                st.info("No vote records for this MP yet.")
            else:
                aye = (mp_votes["vote"] == "aye").sum()
                no  = (mp_votes["vote"] == "no").sum()
                c1, c2 = st.columns(2)
                c1.metric("Aye votes", aye)
                c2.metric("No votes", no)
                st.dataframe(mp_votes, use_container_width=True, hide_index=True)
