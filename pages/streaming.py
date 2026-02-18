"""Streaming TTS page — audio chunks arrive progressively from the server."""
import time

import pandas as pd
import requests
import streamlit as st

from pages._config import SERVER_URL, render_voice_sidebar

_WAV_HEADER_SIZE = 44  # bytes in a standard WAV header

voice_id, speed, language_override, _ = render_voice_sidebar(st)

# ── Main area ──────────────────────────────────────────────────────────────────

st.title("Kokoro TTS — Streaming")
st.caption(
    "Text is sent in one request; the server streams back audio as each "
    "paragraph/sentence is synthesised."
)

text = st.text_area(
    "Text to speak",
    placeholder="Enter the text you want to convert to speech…",
    height=300,
)

if st.button("Generate (streaming)", type="primary", use_container_width=True):
    if not text.strip():
        st.warning("Please enter some text first.")
    else:
        payload: dict = {"input": text, "voice": voice_id, "speed": speed}
        if language_override:
            payload["language"] = language_override

        # ── Live display placeholders ──────────────────────────────────────────
        col_chunks, col_size = st.columns(2)
        ph_chunks = col_chunks.empty()   # metric: chunk count
        ph_size   = col_size.empty()     # metric: KB received
        ph_chart  = st.empty()           # line chart growing over time
        ph_status = st.empty()

        try:
            with requests.post(
                f"{SERVER_URL}/v1/audio/speech/stream",
                json=payload,
                stream=True,
                timeout=300,
            ) as response:
                if response.status_code != 200:
                    detail = response.json().get("detail", "Unknown error")
                    st.error(f"Server error {response.status_code}: {detail}")
                else:
                    audio_buffer = bytearray()
                    http_chunks  = 0
                    bytes_received = 0
                    timeline: list[dict] = []  # [{elapsed, kb}]
                    start = time.monotonic()

                    for raw in response.iter_content(chunk_size=4096):
                        if not raw:
                            continue

                        audio_buffer.extend(raw)
                        bytes_received += len(raw)

                        # Skip the WAV header — only count PCM audio chunks.
                        if bytes_received > _WAV_HEADER_SIZE:
                            http_chunks += 1
                            elapsed = round(time.monotonic() - start, 2)
                            kb = round(bytes_received / 1024, 1)
                            timeline.append({"Elapsed (s)": elapsed, "KB received": kb})

                        ph_chunks.metric("Chunks received", http_chunks)
                        ph_size.metric("Data received", f"{bytes_received / 1024:.1f} KB")

                        if len(timeline) >= 2:
                            ph_chart.line_chart(
                                pd.DataFrame(timeline),
                                x="Elapsed (s)",
                                y="KB received",
                            )

                    ph_status.success(
                        f"Done — {http_chunks} chunks, "
                        f"{len(audio_buffer) / 1024:.1f} KB total, "
                        f"{round(time.monotonic() - start, 1)} s"
                    )
                    st.audio(bytes(audio_buffer), format="audio/wav")

        except requests.exceptions.ConnectionError:
            st.error(
                f"Cannot connect to the server at `{SERVER_URL}`.  \n"
                "Make sure it is running:  \n"
                "```\npython run_server.py\n```"
            )
        except requests.exceptions.Timeout:
            st.error("Request timed out.")
