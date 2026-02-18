"""Multi-page Streamlit app for Kokoro TTS."""
import streamlit as st

st.set_page_config(page_title="Kokoro TTS", page_icon="🔊", layout="centered")

pg = st.navigation([
    st.Page("pages/batch.py", title="Batch", icon="🗂️"),
    st.Page("pages/streaming.py", title="Streaming", icon="📡"),
])
pg.run()
