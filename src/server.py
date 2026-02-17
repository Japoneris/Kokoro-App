"""Kokoro TTS micro-server exposing a single OpenAI-compatible speech synthesis endpoint."""
import io
import wave
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="Kokoro TTS Server")

# Cache KPipeline instances by lang_code to avoid reloading between requests
_pipelines: dict = {}


def _get_pipeline(lang_code: str):
    if lang_code not in _pipelines:
        from kokoro import KPipeline
        _pipelines[lang_code] = KPipeline(lang_code=lang_code)
    return _pipelines[lang_code]


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    if audio.ndim > 1:
        audio = audio.squeeze()
    if audio.dtype in (np.float32, np.float64):
        audio = np.clip(audio, -1.0, 1.0)
        audio = (audio * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buffer.getvalue()


class SpeechRequest(BaseModel):
    input: str
    voice: str = "af_heart"
    speed: float = 1.0
    response_format: str = "wav"
    language: Optional[str] = None  # override lang_code; None = auto-detect from voice prefix


@app.post("/v1/audio/speech")
async def create_speech(request: SpeechRequest):
    """Generate speech from text using Kokoro.

    Language resolution order:
      1. Explicit `language` field if provided (e.g. "f" to use a French phoneme model)
      2. Auto-detected from the voice prefix (e.g. "af_heart" → "a" = en-US)

    Lang codes: a=en-US, b=en-GB, e=es, f=fr, h=hi, i=en-IN, j=ja, p=pt-BR, z=zh
    """
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty")

    lang_code = request.language if request.language else (request.voice[0] if request.voice else "a")

    try:
        pipe = _get_pipeline(lang_code)
        chunks = []
        for _, _, audio in pipe(request.input, voice=request.voice, speed=request.speed):
            chunks.append(audio)
        audio = np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)
        audio_bytes = _audio_to_wav_bytes(audio, sample_rate=24000)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=speech.wav"},
    )
