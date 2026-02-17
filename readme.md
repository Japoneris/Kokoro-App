# Kokoro Speaker

A local text-to-speech app powered by [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), with a Streamlit UI and a lightweight FastAPI server.

![App screenshot](screenshot.png)

---

## Features

- 54 voices across 9 languages (American English, British English, Spanish, French, Hindi, Indian English, Japanese, Portuguese, Chinese Mandarin)
- Voice filtered by language, annotated by gender
- Adjustable speech speed (0.5×–2.0×)
- Phoneme language override — use e.g. French phonemes with an American-accented voice
- Save audio to `outputs/` with auto-indexed filenames or a custom name
- Browser download button (WAV)

---

## Project structure

```
kokoro_speaker/
├── app.py            # Streamlit UI
├── run_server.py     # FastAPI server entry point
├── requirements.txt
└── src/
    └── server.py     # Single POST /v1/audio/speech endpoint
```

---

## Installation

**System dependency** — Kokoro requires `espeak-ng` for phoneme conversion:

```bash
sudo apt install espeak-ng        # Debian / Ubuntu
brew install espeak-ng            # macOS
```

**Python dependencies:**

```bash
pip install -r requirements.txt
```

---

## Usage

Start the two processes in separate terminals:

```bash
# Terminal 1 — TTS server (default: http://localhost:8000)
python run_server.py

# Terminal 2 — Streamlit app (default: http://localhost:8501)
streamlit run app.py
```

Optional server flags:

```bash
python run_server.py --host 0.0.0.0 --port 8000 --reload
```

---

## API

The server exposes a single OpenAI-compatible endpoint:

```
POST /v1/audio/speech
```

**Request body (JSON):**

| Field | Type | Default | Description |
|---|---|---|---|
| `input` | string | — | Text to synthesize |
| `voice` | string | `af_heart` | Voice ID (see list below) |
| `speed` | float | `1.0` | Speed multiplier (0.5–2.0) |
| `language` | string | `null` | Phoneme language override (`a`, `b`, `e`, …). Auto-detected from voice prefix if omitted. |
| `response_format` | string | `wav` | Output format (currently `wav`) |

**Response:** raw WAV audio bytes (`audio/wav`).

**Example:**

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
     -H "Content-Type: application/json" \
     -d '{"input": "Hello world", "voice": "af_heart", "speed": 1.0}' \
     --output speech.wav
```

---

## Voice list

Language codes: `a`=en-US · `b`=en-GB · `e`=es · `f`=fr · `h`=hi · `i`=en-IN · `j`=ja · `p`=pt-BR · `z`=zh

| Language | Female voices | Male voices |
|---|---|---|
| American English | af_alloy, af_aoede, af_bella, af_heart, af_jessica, af_kore, af_nicole, af_nova, af_river, af_sarah, af_sky | am_adam, am_echo, am_eric, am_fenrir, am_liam, am_michael, am_onyx, am_puck, am_santa |
| British English | bf_alice, bf_emma, bf_isabella, bf_lily | bm_daniel, bm_fable, bm_george, bm_lewis |
| Spanish | ef_dora | em_alex, em_santa |
| French | ff_siwis | — |
| Hindi | hf_alpha, hf_beta | hm_omega, hm_psi |
| Indian English | if_sara | im_nicola |
| Japanese | jf_alpha, jf_gongitsune, jf_nezumi, jf_tebukuro | jm_kumo |
| Portuguese | pf_dora | pm_alex, pm_santa |
| Chinese (Mandarin) | zf_xiaobei, zf_xiaoni, zf_xiaoxiao, zf_xiaoyi | zm_yunjian, zm_yunxi, zm_yunxia, zm_yunyang |

---

## Output files

Generated audio is saved to the `outputs/` folder. If no filename is specified, files are named automatically:

```
outputs/001-american-english-af_heart.wav
outputs/002-french-ff_siwis.wav
```

The index is derived from the highest existing file index in `outputs/`, so files never overwrite each other.

---

## Model

- **Kokoro-82M** — [HuggingFace](https://huggingface.co/hexgrad/Kokoro-82M) · [GitHub](https://github.com/hexgrad/kokoro)
- Lightweight 82M-parameter TTS model with high-quality output
- Runs on CPU and GPU
