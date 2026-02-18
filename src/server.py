"""Kokoro TTS micro-server exposing a single OpenAI-compatible speech synthesis endpoint."""
import asyncio
import io
import struct
import threading
import wave
from typing import AsyncGenerator, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Kokoro TTS Server")

# Cache KPipeline instances by lang_code to avoid reloading between requests
_pipelines: dict = {}


def _get_pipeline(lang_code: str):
    if lang_code not in _pipelines:
        from kokoro import KPipeline
        _pipelines[lang_code] = KPipeline(lang_code=lang_code)
    return _pipelines[lang_code]


def _audio_to_wav_bytes(audio, sample_rate: int) -> bytes:
    import torch
    if isinstance(audio, torch.Tensor):
        audio = audio.detach().cpu().numpy()
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


_SAMPLE_RATE = 24000


def _wav_streaming_header(sample_rate: int = _SAMPLE_RATE, channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """WAV header with size=0xFFFFFFFF for open-ended streaming.

    Most players (ffmpeg, VLC, browser MediaSource) accept this as a valid
    streaming WAV and start decoding as soon as the first PCM bytes arrive.
    """
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    # 0xFFFFFFFF signals an unknown/streaming length (RFC-standard trick).
    # Both the RIFF chunk size and the data sub-chunk size are set to the max
    # value; adding 36 to data_size would overflow the uint32 field.
    header = struct.pack("<4sI4s", b"RIFF", 0xFFFFFFFF, b"WAVE")
    header += struct.pack(
        "<4sIHHIIHH",
        b"fmt ", 16, 1, channels, sample_rate, byte_rate, block_align, bits_per_sample,
    )
    header += struct.pack("<4sI", b"data", 0xFFFFFFFF)
    return header


def _float32_to_pcm16(audio) -> bytes:
    import torch
    if isinstance(audio, torch.Tensor):
        audio = audio.detach().cpu().numpy()
    if audio.ndim > 1:
        audio = audio.squeeze()
    audio = np.clip(audio, -1.0, 1.0)
    return (audio * 32767).astype(np.int16).tobytes()


async def _kokoro_stream(pipe, text: str, voice: str, speed: float) -> AsyncGenerator[bytes, None]:
    """Async generator: yields WAV header then PCM chunks as Kokoro produces them.

    Kokoro's pipeline is synchronous and CPU-bound, so it runs in a background
    thread. Chunks are handed back to the async world via asyncio.Queue so the
    event loop is never blocked.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _run_pipeline() -> None:
        try:
            for _, _, audio in pipe(text, voice=voice, speed=speed, split_pattern=r"\n+"):
                asyncio.run_coroutine_threadsafe(queue.put(audio), loop)
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(queue.put(exc), loop)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel

    thread = threading.Thread(target=_run_pipeline, daemon=True)
    thread.start()

    yield _wav_streaming_header()

    while True:
        item = await queue.get()
        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        yield _float32_to_pcm16(item)

    thread.join()


@app.post("/v1/audio/speech/stream")
async def stream_speech(request: SpeechRequest):
    """Stream speech audio as it is generated, chunk by chunk.

    Returns a streaming WAV (header + raw PCM). The first bytes arrive as soon
    as Kokoro finishes the first sentence/paragraph, not after the full text.

    Useful for long texts or latency-sensitive applications — the client can
    start playback while the server is still synthesising the remainder.
    """
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty")

    lang_code = request.language if request.language else (request.voice[0] if request.voice else "a")

    try:
        pipe = _get_pipeline(lang_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        _kokoro_stream(pipe, request.input, request.voice, request.speed),
        media_type="audio/wav",
    )


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
