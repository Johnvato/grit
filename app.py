import streamlit as st
import sqlite3

st.set_page_config(page_title="Project GRIT", layout="centered")
st.title("Project GRIT: Truth Engine")

conn = sqlite3.connect("grit_cache.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM politicians WHERE ID = '75'")
result = cursor.fetchone()
conn.close()

if result:
    st.metric(label="Current MP Data", value=result[0])
else:
    st.error("No data found. Run: python3 sync_data.py")
