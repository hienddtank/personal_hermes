---
name: kokoro-async-batch-tts
category: media
description: Convert PDFs to audio using Kokoro TTS engine with async micro-batching (NimbleEdge pattern). Batches 16 texts into single forward_with_tokens() call for max throughput.
tags: []
related_skills: [pdf-to-audio-edge-tts]
---

# Kokoro Async Micro-Batched TTS for PDF-to-Audio Conversion

Use this skill when converting large PDFs to audio using the Kokoro TTS engine with batch processing for maximum throughput. The key insight: don't use `KPipeline.__call__` in a loop (processes one text at a time). Instead, use `forward_with_tokens()` directly via NimbleEdge-style micro-batching to process 16 texts in a single GPU/CPU forward pass.

## When to Use
- Converting large PDFs/text documents to audio with Kokoro TTS engine
- Need significantly faster throughput than serial KPipeline calls (~0.15 text/sec)
- User has specified Kokoro engine (not edge-tts or other engines)
- Voice preset: typically `af_heart` for English female voice

## Prerequisites

```bash
pip install torch --extra-index-url https://download.pytorch.org/whl/cpu  # CPU-only, ~530MB
pip install kokoro soundfile numpy
# ffmpeg must be available in PATH for MP3 encoding
```

## Steps

### 1. Check Existing Conversion Progress

```bash
# Count completed segments per worker (serial or parallel)
for i in $(seq 0 7); do count=$(ls /tmp/kokero_seg_w${i}_*.wav 2>/dev/null | wc -l); echo "Worker $i: $count"; done
ps aux | grep kokero_worker | grep -v grep | wc -l

# Or check log
tail -20 /tmp/kokoro_parallel_v2.log
```

### 2. Prepare Chunk File (split into worker assignments)

Split extracted sentences from PDF into per-worker JSON files:

```python
import json

chunks = [(i, chunk_text) for i, chunk_text in enumerate(all_chunks)]
worker_id = 0
chunk_file = f"/tmp/kokero_worker_{worker_id}_chunks.json"
with open(chunk_file, 'w') as f:
    json.dump(chunks[:N], f)  # N chunks per worker (~564 for 8 workers / 4512 total)
```

### 3. Launch Async Batch Worker (KEY STEP - NOT serial loop!)

```bash
python3 /tmp/kokoro_async_batch_worker.py <worker_id> <chunks.json> &
# or run all N workers in parallel:
for i in $(seq 0 $((N_WORKERS-1))); do python3 /tmp/kokoro_async_batch_worker.py $i /tmp/kokero_worker_${i}_chunks.json & done
```

The worker uses `asyncio` + micro-batching: collects requests for ~20ms, then fires up to 16 at once via `forward_with_tokens()`.

### 4. Monitor Progress

```bash
# Count segments per worker
for i in $(seq 0 7); do echo "W$i: $(ls /tmp/kokoro_async_w${i}_*.wav 2>/dev/null | wc -l)"; done

# Check log for throughput stats
tail -5 /tmp/kokoro_worker_${i}.log
```

### 5. Merge Segments When Complete

Use `ffmpeg` to concatenate all WAV segments into final MP3:

```bash
cat /tmp/kokoro_async_w*_*.wav > combined.wav
ffmpeg -i combined.wav -codec:a libmp3lame -qscale:a 2 output.mp3
rm /tmp/kokoro_async_w*_*.wav combined.wav
```

## Critical API Gotchas (from debugging!)

1. **KPipeline returns `(grapheme, phoneme_str, torch.Tensor)`** — the third element is audio as a torch.Tensor, NOT sample rate. There IS no separate `sr` variable in Kokoro's output tuple. Common error: passing `sr` to soundfile.write() causes TypeError because it's a string (the grapheme/phonetic transcription).

2. **No `phonemize()` function exists** in kokoro package — use `pipeline.g2p(text)` via spacy internally (for English). The KPipeline handles G2P; you just get phoneme strings back from the generator.

3. **Reference sound for voice**: Load with `pipeline.load_voice("af_heart")` which returns a torch tensor. Must be unsqueezed and repeated for batch: `ref_s.unsqueeze(0).repeat(batch_size, 1).float()`

4. **forward_with_tokens signature**: `(input_ids, ref_s, speed)` — second arg is the REFERENCE SOUND TENSOR (voice embedding), NOT sample rate! This is the #1 source of bugs.

5. **NumPy 2.0 compatibility**: Use `.max()` method instead of `np.max(x, axis=...)`. E.g., `float(np.abs(audio).max())` not `np.max(np.abs(audio))`. Old code using `np.max` with keyword args will crash.

6. **Audio must be numpy array** — Kokoro returns `torch.Tensor`. Convert: `audio.cpu().numpy()` before passing to soundfile.

7. **KPipeline doesn't expose batch_size=16 knob** in its public API. True batching requires direct `forward_with_tokens()` calls with padded input tensors. The NimbleEdge pattern is the recommended approach.

## Expected Performance

- Serial KPipeline: ~0.15 texts/sec (13s per text) — very slow
- Async batched: 2-8+ texts/sec depending on hardware (16x speedup potential)
- Total for 4512 chunks at serial rate: ~750 min (~12.5 hours) → with batching should be under 3 hours

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| `TypeError: an integer is required` in soundfile.write() | Passing Kokoro's phoneme string as sample rate instead of int(24000) | Always use hardcoded SAMPLE_RATE=24000; ignore the `sr` from KPipeline |
| Workers crash silently with NumPy error | `np.max()` API changed in NumPy 2.0 | Use `.max()` method: `float(np.abs(audio).max())` |
| `ImportError: cannot import name 'phonemize'` | phonemize() doesn't exist in kokoro package | Don't try to import it — use KPipeline's internal g2p instead |
| Audio is silent/0 samples | ref_s not passed correctly to forward_with_tokens | Must be shape [B, 192] tensor repeated for batch size |
| Model fails to download from HuggingFace | Unauthenticated API rate limit | Set HF_TOKEN env var or wait between model loads |

## When NOT to Use This Skill

- Simple text files (< 50 sentences) — use `text_to_speech` tool directly
- Need Vietnamese audio (Kokoro is English-focused; edge-tts supports more languages)
- User wants a short passage (< 1 minute) — too much overhead for tiny inputs
