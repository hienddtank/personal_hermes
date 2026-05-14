---
name: pdf-to-audio-kokoro
category: media
description: Convert PDFs to MP3 using Kokoro TTS engine (MOS 4.2). Covers setup, paragraph-by-paragraph chunking, batch processing with shared models, async micro-batching, NumPy 2.0 fixes, and GPU/CPU optimization patterns. ~15x faster than edge-tts.
version: 3.0.0
tags: [tts, audio, voice, kokoro, pdf-to-speech, mp3, speech-synthesis]
---

# PDF-to-Audio with Kokoro TTS

Convert PDFs to spoken-word MP3 using Kokoro open-source TTS engine (MOS 4.2 vs edge-tts ~3.6). **~15x faster** than edge-tts (~1 hour vs ~15 hours for full documents). Uses paragraph-based chunking for long docs, sentence-based for short ones.

## Chunking Strategy

### Paragraph-by-paragraph (Recommended)
- Process ONE paragraph per Kokoro call (~500-1200 chars typical)
- Highest quality with natural prosody and proper pauses at sentence boundaries
- Spider_web.pdf: ~1289 chunks, ~7,500 total characters
- **DO NOT group paragraphs** — produces robotic/mushy audio

### Sentence-based (Short docs < 30 pages where speed > quality)
- ~200-400 chars per sentence, max ~3 sentences per call is a compromise
- Acceptable for medium-length texts

## Installation

```bash
# Step 1: Install PyTorch CPU-only wheels FIRST
pip install --no-cache-dir "torch>=2.0" torchvision torchaudio \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Step 2: Install kokoro + dependencies (~400MB total, ~3-4 min)
pip install kokoro soundfile PyPDF2

# CRITICAL: Use --extra-index-url, NOT --index-url (replaces PyPI entirely)
```

## Quick Test

```python
from kokoro import KPipeline
import soundfile as sf

pipe = KPipeline(lang_code="a", device="cpu")  # 'a' = American English
for gs, ps, audio in pipe("Hello! This is a test of Kokoro TTS.", voice="af_heart"):
    sf.write("/tmp/kokero_test.wav", audio.cpu().numpy(), 24000)

# Convert to MP3: ffmpeg -i /tmp/kokero_test.wav -b:a 192k /tmp/kokero_test.mp3 -y
```

## Voices (American English, lang_code="a")

| Voice ID | Style |
|----------|-------|
| `af_heart` | Warm, friendly female — best default |
| `af_bubble` | Bright, bubbly female |
| `af_kore` | Conversational female |
| `af_nicole` | Professional, clear female |
| `am_adam` | Deep male voice |
| `am_michael` | Male voice |

## Pipeline (CPU Only — Shared Model Pattern)

**Critical bottleneck:** spaCy G2P processing takes 15-80 seconds per chunk on CPU, NOT the audio synthesis. Each paragraph call costs ~20-40s total. Full PDF (~1200 paragraphs): **7-15 hours single-threaded**. Parallel workers do NOT help — G2P is sequential; multi-worker causes OOM.

### Correct Shared Model API (tested 2026-04)

```python
from kokoro import KModel, KPipeline
import fitz  # PyMuPDF for text extraction
import numpy as np
import soundfile as sf

# Load model ONCE — shared across all chunks (CRITICAL for speed)
model = KModel().to("cpu")
pipeline = KPipeline(lang_code="a", model=model)

# Extract paragraphs using PyMuPDF blocks
doc = fitz.open(pdf_path)
paragraphs = []
for page in doc:
    for block in page.get_text("blocks"):
        text = block[4].strip()  # Index 4 = text content
        if len(text) > 50 and any(c.isalpha() for c in text):
            paragraphs.append(text)

# Process ONE paragraph per call
all_audio_parts = []
for para_text in paragraphs:
    for result in pipeline(para_text, voice="af_heart"):
        audio = result.audio.numpy().astype(np.float32) if hasattr(result, 'audio') else None
        if audio is not None:
            all_audio_parts.append(audio)

# Concatenate and save (Kokoro uses 24kHz sample rate)
final_audio = np.concatenate(all_audio_parts)
sf.write(output_path, final_audio, 24000)
```

### Key API Points
- **No `set_vox` or `load_voice()` needed** — pass `voice=` to pipeline calls
- **Pipeline constructor**: `KPipeline(lang_code='a', model=model)` — do NOT pass `device="cpu"` (inferred)
- **Audio output**: Access via `result.audio` attribute (torch.Tensor). Call `.numpy()` before soundfile.write()
- **Sample rate is 24000 Hz** for Kokoro

### load_voice() Return Value Variability
```python
voice_result = pipeline.load_voice(VOICE)
if isinstance(voice_result, tuple):
    _, vox_model = voice_result if len(voice_result) == 2 else (voice_result[0], voice_result[-1])
else:
    vox_model = voice_result
```

## NumPy 2.0 Compatibility

`np.max()` fails on certain array types in NumPy 2.0+. Use method syntax:
```python
# BROKEN: np.max() fails on some arrays
max_val = np.max(some_array)
# FIXED: Method syntax works reliably  
max_val = float(np.abs(audio).max())
```

## Audio Quality Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Stops/pauses at PDF line breaks | Kokoro treats `\n` as pause marker | `text = re.sub(r'\s+', ' ', text).strip()` before TTS |
| Janky voice transitions between chunks | New KPipeline per chunk (voice state resets) | Create KPipeline ONCE, pass shared pipe to all chunks |
| Pops/cracks at chunk boundaries | Chunks end abruptly with no gap | 100ms silence padding via ffmpeg between chunks |
| Robotic/mushy audio quality | Using paragraph-grouping approach (7500+ chars) | Switch to one-paragraph-per-chunk |

## Alternative Batching Patterns

For parallel processing, see:
- **[Shared Model Architecture](references/parallel-batching.md)** — Multi-worker architecture with JSON chunk distribution, progress monitoring, silent crash detection
- **[Async Micro-Batching (NimbleEdge)](references/async-microbatching.md)** — Batch 16 texts via `forward_with_tokens()` for 2-8x throughput on GPU

## When to Use This Skill
- User complains edge-tts sounds bad / robotic / unsatisfactory quality  
- Need faster TTS conversion (Kokoro is ~60x faster per chunk than edge-tts API)
- No GPU available but need good-quality speech synthesis
- PDF-to-audio conversion with better naturalness than JennyNeural

## When NOT to Use This Skill
- User wants celebrity voice cloning (use ElevenLabs or Fish Speech instead)
- Need multi-language support beyond English
- Short passages (< 5 minutes of audio) — use `text_to_speech` tool directly
- GPU environment available with large document — consider async micro-batching

## Performance Reality Check (CPU)

| Metric | Previous Claim | Actual (CPU) |
|--------|---------------|--------------|
| Per-chunk time | ~3s (paragraph) | **20-80s** (G2P dominated) |
| Full PDF runtime | ~3 minutes | **7–15 hours single-threaded** |
| Parallel workers | Faster throughput | **No benefit, causes OOM crashes** |

For faster conversion: consider cloud APIs (ElevenLabs/OpenAI) or GPU-accelerated inference.

## Resources
- Script: `scripts/pdf_to_audio_kokoro.py`
- Kokoro docs: https://huggingface.co/hexgrad/Kokoro-82M

---

## FFmpeg Silence Removal (Critical Gotchas)

### ⚠️ Threshold Uses RAW SAMPLES, Not dB
FFmpeg's `silenceremove` silently ignores the `-dB` suffix, parsing it as 0 (exact silence only), causing total audio loss.

**Always use raw sample values:**
| dB | Raw (16-bit) |
|----|-------------|
| -48dB | ~5 |
| -24dB | ~92 |
| -12dB | ~369 |
| -6dB | ~737 |

### Detecting Silence First
```bash
# Check average/max volume
ffmpeg -i input.mp3 -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
# Find silence periods
ffmpeg -i input.mp3 -af silencedetect=noise=-1dB:d=0.5 -f null - 2>&1 | grep -E "silence_start|silence_end"
```

### Simple Start/End Trim
```bash
# Skip first N seconds (stream copy — instant)
ffmpeg -y -ss 400 -i input.mp3 -c:a copy output.mp3
```

### silenceremove (internal gaps)
```bash
ffmpeg -y -i input.mp3 \
  -af "silenceremove=start_periods=1:start_duration=0.8:start_threshold=5:detection=rms" \
  -c:a libmp3lame -b:a 64k output.mp3
```

### Chunk Merging Pattern
```bash
ls -1 /path/to/chunks_*.mp3 | sort > concat_list.txt
sed "s|^|file '|; s|$|'|" concat_list.txt > concat_protocol.txt
ffmpeg -y -f concat -safe 0 -i concat_protocol.txt -c:a copy output.mp3
```

### Common Pitfalls
1. **`-dB` suffix silently parses as 0** — removes ALL audio
2. **-ss AFTER -i is slow** — put -ss BEFORE -i for fast seeking
3. **Low-volume TTS (~-20dB mean)** — use silencedetect + segment extraction instead
4. **MP3 concat with different codecs** — requires re-encoding to common format

---

## Edge-TTS Troubleshooting (Legacy Backend)

### Check Conversion Progress
```bash
# Check running TTS process
ps aux | grep -E "edge.tts|pdf_to_audio|python.*tts"
# Count output chunks
find /tmp -name "*_chunk_*.mp3" 2>/dev/null | wc -l
```

### Massive Output File Diagnosis
```bash
# Check file metadata
ffprobe -v quiet -show_entries format=size,duration,bit_rate -of default=noprint_wrappers=1 output.mp3
# Sample audio at timestamps
ffmpeg -y -i output.mp3 -af volumedetect -f null - 2>&1 | grep max_volume
```
Common causes: O(n²) concatenation bugs, loop appending to wrong variable, excessive padding between 247+ chunks.

### Voice Contamination Bug
**Symptom:** Output sounds like a different language. Multiple edge-tts scripts ran in same session using `/tmp/edge_*.mp3` filenames, test voice got concatenated into production output.

**Fix:** Re-extract PDF text and re-run with isolated temp dir, explicit voice parameter, and per-chunk validation (file size > 100 bytes).

### Robust Edge-TTS Script Pattern (see `references/edge-tts-troubleshooting.md`)
- ALWAYS use explicit `VOICE = "en-US-JennyNeural"`
- Never use `/tmp/` for production chunks — use isolated dir
- Validate each chunk before concatenation
- Remove non-ASCII text from PDF extractions before TTS

---

## Backend Comparison

| Feature | Kokoro | edge-tts |
|---------|--------|----------|
| Quality (MOS) | 4.2 | ~3.6 |
| Speed (CPU) | 20-80s/chunk (G2P bottleneck) | ~3s/chunk |
| Full PDF (1200 paras) | 7-15 hours single-threaded | ~15 hours API rate-limited |
| GPU support | Yes (async micro-batching) | No (cloud API) |
| Languages | English (en-a, en-b) | Many (Azure voices) |
| Cost | Free (local) | Free (cloud API) |
