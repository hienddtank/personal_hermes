---
name: kokoro-tts-batching
category: media
description: Convert text to audio using Kokoro TTS with shared-model architecture for batch processing. Addresses per-chunk model reload overhead and NumPy 2.0 incompatibilities.
---

# Kokoro TTS Batching for Batch Processing

Use when converting large amounts of text (PDFs, books) to speech using the Kokoro TTS engine on CPU hardware, where per-chunk model loading creates unacceptable slowdowns.

## Prerequisites

```bash
pip install kokoro torch --extra-index-url https://download.pytorch.org/whl/cpu
# CPU-only PyTorch build (~530MB). CUDA explicitly avoided for compatibility.
```

## Core Architecture: Shared KModel Pattern

**Critical insight:** `KPipeline` loads a new model instance on every `__call__` unless you pass your own. This causes ~12s overhead per chunk (model + voice loading) vs actual inference (~3s).

### WRONG — Per-chunk reload (slow):
```python
from kokoro import KPipeline
pipeline = KPipeline(lang_code="a")  # Model loaded fresh each call!

for text in texts:
    for g, p, audio_obj in pipeline(text, voice="af_heart"):
        ...  # ~15s per chunk total
```

### RIGHT — Shared model + pre-loaded voice (fastest):
**CRITICAL:** If you pass `voice=` on every `.call()` it triggers `self.load_voice(voice)` internally each time (~2-3s overhead). Instead, pass voice in the constructor:

```python
from kokoro import KModel, KPipeline

model = KModel(
    repo_id="hexgrad/Kokoro-82M", 
    disable_complex=True,
).to("cpu").eval()  # Load ONCE

# Pass BOTH model AND voice in constructor — avoids per-call load_voice() overhead!
pipeline = KPipeline(lang_code="a", model=model)  
ref_s = pipeline.load_voice("af_heart")  # Load voice ONCE

for text in texts:
    for g, p, audio_obj in pipeline(text):  # No voice= needed — already bound
        ...  # ~3-5s per chunk (G2P + inference only)
```

### Worker-level sharing (8 parallel processes):
Each worker process gets its OWN `KModel` instance — you cannot share across Python processes. Distribute chunks via JSON files:
```python
# Main process distributes chunks to workers
for i in range(N_WORKERS):
    chunk_file = f"/tmp/kokero_worker_{i}_chunks.json"
    write_json(chunk_file, distribute_chunks(all_chunks, i, N_WORKERS))
    
# Worker script: each loads its own KModel once, processes all assigned chunks
```

## How Kokoro's Pipeline Actually Works

The `KPipeline.__call__()` method yields `(grapheme_str, phoneme_str, tokens)` where `tokens` is a `KPipeline.Result` object with `.output.audio` (a `torch.Tensor`). The bottleneck is **spaCy G2P** — each text goes through full spaCy NLP pipeline (tokenization + POS tagging → lexicon lookup) which takes ~10-20s per text on CPU. This is sequential and cannot be batched.

## Common Bugs (NumPy 2.0 + Kokoro Incompatibilities)

### Bug 1: np.max() fails with NumPy 2.0 API
```python
# BROKEN — raises TypeError on NumPy ≥2.0
peak = np.max(np.abs(audio))

# FIXED — use array .max() method instead
peak = float(np.abs(audio).max())
```

### Bug 2: Audio is torch.Tensor, not numpy
```python
# BROKEN — soundfile.write expects numpy array
sf.write(path, audio, sr)  # TypeError (sr is actually phonemes string!)

# FIXED — convert tensor to numpy first
if isinstance(audio, torch.Tensor):
    audio = audio.cpu().numpy()
peak = float(np.abs(audio).max())
```

### Bug 3: Pipeline yields wrong tuple unpacking
The pipeline yields `(grapheme_str, phoneme_string, tokens)` NOT `(g, p, audio)`. The third element is a `KPipeline.Result` object with `.output.audio` attribute. If you do `for g, p, sr in pipeline(...)` the variable `sr` is actually the **phonemes string**, not sample rate!

## Parallel Worker Architecture

```python
# Distribute ~4500 sentence chunks across 8 workers (564 each)
N_WORKERS = 8
chunk_file_template = "/tmp/kokero_worker_{i}_chunks.json"

for i in range(N_WORKERS):
    proc = subprocess.Popen(
        ["python3", "kokoro_worker.py", str(i), 
         f"/tmp/kokero_worker_{i}_chunks.json", "af_heart"],
        stdout=open(f"/tmp/kokoro_w{i}.log", "w"), stderr=subprocess.STDOUT
    )

# Workers write segments: /tmp/kokoro_seg_w{id}_{chunk_idx:05d}.wav
# After all workers complete, merge WAVs into final MP3 with ffmpeg
```

## Performance Baselines (CPU-only)

| Approach | Chunks/min | Notes |
|----------|-----------|-------|
| Per-chunk KPipeline() instantiation | ~4 c/h (~0.07/s) | Model loads every time (~12s overhead) |
| Shared model + single pipeline | ~30-60 c/h (~0.5-1/s) | spaCy G2P is the hard limit per text |
| True batched forward_with_tokens | TBD | Would require bypassing KPipeline API entirely |

## Voice Presets
- `af_heart` — English female, warm/natural (recommended default)
- `af_bubble` — English female, bouncy/playful  
- `bf_emma` — English female, professional
- `am_adam` — English male
- Test multiple voices for quality comparison

## Merging Segments to Final MP3

After all workers complete:
```bash
# Collect all segment files sorted by worker then chunk index
cat <(ls /tmp/kokoro_seg_w0_*.wav) \
    <(ls /tmp/kokoro_seg_w1_*.wav) ... > /tmp/all_segments.txt

# Concatenate with ffmpeg
ffmpeg -f concat -safe 0 -i /tmp/segment_list.txt -c copy output.mp3
```

Or use a Python merge script that reads all WAV files in order and concatenates them.

## Operational Pitfalls & Monitoring

### Silent Worker Crash Loops (CRITICAL)
Workers can run for HOURS at 100% CPU producing ZERO segments. This happens when:
- All chunks hit the same error (e.g., NumPy incompatibility, voice loading failure)
- The worker catches/ignores exceptions and silently retries each chunk

**Always verify progress within 60 seconds of launch:**
```bash
# Check if ANY segments were created — if zero after 1 minute, something is wrong
ls /tmp/kokoro_seg_w*_*.wav | wc -l
# If this returns 0, kill workers immediately and debug before waiting hours

# Per-worker progress check
for i in $(seq 0 7); do echo "Worker $i: $(ls /tmp/kokero_seg_w${i}_*.wav 2>/dev/null | wc -l) segments"; done

# CPU usage per worker (should be moderate, not all cores maxed with zero output)
ps aux | grep kokero_worker
```

**If workers are stuck with zero progress:** `pkill -9 -f kokero_worker.py` then fix the error before restarting.

### spaCy G2P Is The Hard Limit
Even with shared model + voice, each text still requires ~15-20s of sequential spaCy processing (NLP tokenization + lexicon lookup). This CANNOT be batched — it's a CPU-bound per-text requirement. Parallel workers give you N× throughput but each worker is still limited to ~3 chunks/min on typical hardware.

For 4500 chunks with 8 workers: expect **~12-20 hours total** (each worker processes ~564 chunks at ~3 min/chunk).

## When to Use This Skill
- Converting PDFs/text to audio with Kokoro (CPU-only, edge-tts quality complaints)
- Large batch processing (>100 text segments) 
- Situations where edge-tts produces unnatural/robotic audio (lower MOS score ~3.6 vs Kokoro's ~4.2)

## When NOT to Use This Skill
- Short passages (< 5 minutes of audio) — use `text_to_speech` tool directly
- GPU/CUDA environment available — different optimization strategy needed
- User wants real-time streaming output (Kokoro batch approach is offline-only)
