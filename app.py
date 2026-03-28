import streamlit as st
import sqlite3
import pandas as pd

st.set_page_config(page_title="Project GRIT", layout="wide")
st.title("Project GRIT: Truth Engine")
st.caption("Tracking Australian MPs — rhetoric vs. reality.")

DB = "grit_cache.db"


@st.cache_resource
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)


conn = get_conn()


def query(sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


tab_mps, tab_divisions, tab_votes = st.tabs(["MPs", "Recent Divisions", "Vote Explorer"])

# ── MPs tab ──────────────────────────────────────────────────────────────────
with tab_mps:
    st.subheader("House of Representatives")

    parties = query("SELECT DISTINCT party FROM politicians ORDER BY party")["party"].tolist()
    selected_party = st.selectbox("Filter by party", ["All"] + parties)

    if selected_party == "All":
        mps = query("""
            SELECT id, name, party, electorate, photo_url,
                   votes_attended, votes_possible, rebellions
            FROM politicians
            ORDER BY name
        """)
    else:
        mps = query("""
            SELECT id, name, party, electorate, photo_url,
                   votes_attended, votes_possible, rebellions
            FROM politicians
            WHERE party = ?
            ORDER BY name
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
                        col.image(row["photo_url"], width=120)
                    col.markdown(f"**{row['name']}**")
                    col.caption(
                        f"{row['party']}  \n"
                        f"{row['electorate']}  \n"
                        f"Attendance: {row['attendance_%']}  \n"
                        f"Rebellions: {int(row['rebellions'])}"
                    )

        st.caption(f"{len(mps)} members shown.")

# ── Divisions tab ─────────────────────────────────────────────────────────────
with tab_divisions:
    st.subheader("Recent Divisions (Votes)")

    divs = query("""
        SELECT date, name, aye_votes, no_votes, rebellions, summary
        FROM divisions
        ORDER BY date DESC, number DESC
        LIMIT 100
    """)

    if divs.empty:
        st.info("No division data yet. Run: python sync_data.py")
    else:
        st.dataframe(
            divs[["date", "name", "aye_votes", "no_votes", "rebellions"]],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.subheader("Division detail")
        selected_div = st.selectbox(
            "Select a division to see summary",
            divs["name"].tolist(),
        )
        row = divs[divs["name"] == selected_div].iloc[0]
        col1, col2, col3 = st.columns(3)
        col1.metric("Aye", row["aye_votes"])
        col2.metric("No", row["no_votes"])
        col3.metric("Rebellions", row["rebellions"])
        if row["summary"]:
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
            "SELECT id, photo_url, party, electorate FROM politicians WHERE name = ?", (selected_mp,)
        )
        if not mp_row.empty:
            mp_id = int(mp_row.iloc[0]["id"])
            ph_col, info_col = st.columns([1, 3])
            with ph_col:
                if mp_row.iloc[0]["photo_url"]:
                    st.image(mp_row.iloc[0]["photo_url"], width=120)
            with info_col:
                st.markdown(f"**{selected_mp}**")
                st.caption(f"{mp_row.iloc[0]['party']} — {mp_row.iloc[0]['electorate']}")
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
