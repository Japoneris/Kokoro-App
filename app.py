"""Streamlit app for Kokoro text-to-speech."""
import re
from pathlib import Path

import requests
import streamlit as st

import os

OUTPUT_DIR = Path("outputs")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")

# Voice catalogue keyed by display language name.
# Voice ID format: <lang><gender>_<name>  (e.g. af_heart = American Female heart)
VOICES: dict[str, dict] = {
    "American English": {
        "lang_code": "a",
        "voices": {
            "Female": [
                "af_alloy", "af_aoede", "af_bella", "af_heart",
                "af_jessica", "af_kore", "af_nicole", "af_nova",
                "af_river", "af_sarah", "af_sky",
            ],
            "Male": [
                "am_adam", "am_echo", "am_eric", "am_fenrir",
                "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa",
            ],
        },
    },
    "British English": {
        "lang_code": "b",
        "voices": {
            "Female": ["bf_alice", "bf_emma", "bf_isabella", "bf_lily"],
            "Male": ["bm_daniel", "bm_fable", "bm_george", "bm_lewis"],
        },
    },
    "Spanish": {
        "lang_code": "e",
        "voices": {
            "Female": ["ef_dora"],
            "Male": ["em_alex", "em_santa"],
        },
    },
    "French": {
        "lang_code": "f",
        "voices": {
            "Female": ["ff_siwis"],
        },
    },
    "Hindi": {
        "lang_code": "h",
        "voices": {
            "Female": ["hf_alpha", "hf_beta"],
            "Male": ["hm_omega", "hm_psi"],
        },
    },
    "Indian English": {
        "lang_code": "i",
        "voices": {
            "Female": ["if_sara"],
            "Male": ["im_nicola"],
        },
    },
    "Japanese": {
        "lang_code": "j",
        "voices": {
            "Female": ["jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro"],
            "Male": ["jm_kumo"],
        },
    },
    "Portuguese": {
        "lang_code": "p",
        "voices": {
            "Female": ["pf_dora"],
            "Male": ["pm_alex", "pm_santa"],
        },
    },
    "Chinese (Mandarin)": {
        "lang_code": "z",
        "voices": {
            "Female": ["zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi"],
            "Male": ["zm_yunjian", "zm_yunxi", "zm_yunxia", "zm_yunyang"],
        },
    },
}

LANG_CODES: dict[str, str] = {
    "American English (a)": "a",
    "British English (b)": "b",
    "Spanish (e)": "e",
    "French (f)": "f",
    "Hindi (h)": "h",
    "Indian English (i)": "i",
    "Japanese (j)": "j",
    "Portuguese (p)": "p",
    "Chinese Mandarin (z)": "z",
}


def build_voice_options(lang_name: str, genders: list[str]) -> dict[str, str]:
    """Return {display_name: voice_id} for the given language, filtered by gender.

    The display name is just the bare name after the prefix (e.g. 'af_heart' → 'heart').
    """
    options: dict[str, str] = {}
    for gender, voice_ids in VOICES[lang_name]["voices"].items():
        if gender in genders:
            for vid in voice_ids:
                g = "f" if gender == "Female" else "m"
                name = f"({g}) {vid.split('_', 1)[1]}"  # strip 'af_', 'bm_', etc.
                options[name] = vid
    return options


def next_index() -> int:
    """Return the next sequential index based on existing files in OUTPUT_DIR."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    existing = list(OUTPUT_DIR.glob("*.wav"))
    if not existing:
        return 1
    indices = []
    for f in existing:
        m = re.match(r"^(\d+)", f.stem)
        if m:
            indices.append(int(m.group(1)))
    return max(indices, default=0) + 1


def default_filename(language: str, voice_id: str) -> str:
    idx = next_index()
    lang_slug = language.lower().replace(" ", "-").replace("(", "").replace(")", "")
    return f"{idx:03d}-{lang_slug}-{voice_id}"


st.set_page_config(page_title="Kokoro TTS", page_icon="🔊", layout="centered")

# ── Sidebar — all configuration ───────────────────────────────────────────────

with st.sidebar:
    st.header("Voice")

    language = st.selectbox("Language", list(VOICES.keys()))
    genders = st.multiselect("Gender", ["Female", "Male"], default=["Female", "Male"])
    voice_map = build_voice_options(language, genders or ["Female", "Male"])
    voice_display = st.selectbox("Voice", list(voice_map.keys()))
    voice_id = voice_map[voice_display] if voice_display else "af_heart"

    st.divider()
    st.header("Phoneme language")

    custom_lang = st.toggle("Override", value=False,
                            help="By default the phoneme model is chosen from the voice prefix. "
                                 "Enable to force a different language (e.g. French phonemes with an American voice).")
    if custom_lang:
        lang_label = st.selectbox(
            "Phoneme language",
            list(LANG_CODES.keys()),
            index=list(LANG_CODES.keys()).index(
                next(k for k, v in LANG_CODES.items() if v == voice_id[0])
            ),
        )
        language_override = LANG_CODES[lang_label]
    else:
        language_override = None

    st.divider()
    st.header("Generation")

    speed = st.slider("Speed", min_value=0.5, max_value=2.0, value=1.0, step=0.1)

    st.divider()
    st.header("Output file")

    filename_input = st.text_input(
        "Filename (without extension)",
        placeholder=default_filename(language, voice_id),
    )
    st.text_input("Folder", value=str(OUTPUT_DIR), disabled=True)


# ── Main area ─────────────────────────────────────────────────────────────────

st.title("Kokoro Text-to-Speech")

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
