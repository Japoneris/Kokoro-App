# Kokoro pipeline yields PyTorch Tensors, not numpy arrays

## Context

The Kokoro `KPipeline` generator yields audio as `torch.Tensor` objects:

```python
for _, _, audio in pipe(text, voice=voice, speed=speed):
    # audio is a torch.Tensor, not np.ndarray
```

## Bug

Code that called numpy methods directly on the tensor failed at runtime:

```python
# AttributeError: 'Tensor' object has no attribute 'astype'
return (audio * 32767).astype(np.int16).tobytes()
```

This was triggered in the streaming endpoint (`/v1/audio/speech/stream`) because
the batch endpoint was using `np.concatenate()` on the list of chunks, which
implicitly converted tensors to numpy arrays — masking the issue there.

## Fix

Convert the tensor to a numpy array before any numpy operations:

```python
import torch

if isinstance(audio, torch.Tensor):
    audio = audio.detach().cpu().numpy()
```

- `.detach()` — removes the tensor from the autograd computation graph
- `.cpu()` — moves it to host memory (safe no-op if already on CPU)
- `.numpy()` — produces a numpy array sharing the same memory buffer

This guard was added to both `_float32_to_pcm16()` (streaming path) and
`_audio_to_wav_bytes()` (batch path) in `src/server.py`.
