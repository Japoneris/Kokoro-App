"""Batch TTS page — generate the full audio before playback."""
import streamlit as st
import requests

from pages._config import (
    SERVER_URL, OUTPUT_DIR,
    render_voice_sidebar, default_filename,
)

voice_id, speed, language_override, language = render_voice_sidebar(st)

with st.sidebar:
    st.divider()
    st.header("Output file")
    filename_input = st.text_input(
        "Filename (without extension)",
        placeholder=default_filename(language, voice_id),
    )
    st.text_input("Folder", value=str(OUTPUT_DIR), disabled=True)

# ── Main area ──────────────────────────────────────────────────────────────────

st.title("Kokoro TTS — Batch")

text = st.text_area(
    "Text to speak",
    placeholder="Enter the text you want to convert to speech…",
    height=300,
)

if st.button("Generate Speech", type="primary", use_container_width=True):
    if not text.strip():
        st.warning("Please enter some text first.")
    else:
        with st.spinner("Generating speech…"):
            try:
                payload: dict = {"input": text, "voice": voice_id, "speed": speed}
                if language_override:
                    payload["language"] = language_override
                response = requests.post(
                    f"{SERVER_URL}/v1/audio/speech",
                    json=payload,
                    timeout=120,
                )
                if response.status_code == 200:
                    st.session_state["audio_bytes"] = response.content
                    st.session_state["audio_filename"] = (
                        filename_input.strip() or default_filename(language, voice_id)
                    )
                    st.audio(response.content, format="audio/wav")
                    st.success(f"Done — voice: **{voice_id}**, speed: **{speed}x**")
                else:
                    detail = response.json().get("detail", "Unknown error")
                    st.error(f"Server error {response.status_code}: {detail}")
            except requests.exceptions.ConnectionError:
                st.error(
                    f"Cannot connect to the server at `{SERVER_URL}`.  \n"
                    "Make sure it is running:  \n"
                    "```\npython run_server.py\n```"
                )
            except requests.exceptions.Timeout:
                st.error("Request timed out. The text may be too long; try a shorter excerpt.")

if "audio_bytes" in st.session_state:
    fname = st.session_state["audio_filename"]
    col_dl, col_save = st.columns(2)

    with col_dl:
        st.download_button(
            label="Download WAV",
            data=st.session_state["audio_bytes"],
            file_name=f"{fname}.wav",
            mime="audio/wav",
            use_container_width=True,
        )

    with col_save:
        if st.button("Save to outputs/", use_container_width=True):
            OUTPUT_DIR.mkdir(exist_ok=True)
            out_path = OUTPUT_DIR / f"{fname}.wav"
            out_path.write_bytes(st.session_state["audio_bytes"])
            st.success(f"Saved to `{out_path}`")
