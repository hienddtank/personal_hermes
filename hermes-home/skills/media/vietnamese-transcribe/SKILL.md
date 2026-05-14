---
name: vietnamese-transcribe
description: Transcribe Vietnamese audio files to text using faster-whisper (CPU-friendly, no PyTorch needed).
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
---

# Vietnamese Audio Transcription (faster-whisper)

Transcribe Vietnamese audio files (MP3, M4A, WAV, etc.) to text using faster-whisper — lightweight, CPU-friendly alternative to OpenAI's whisper.

## When to use
- User asks for Vietnamese transcription/transliteration of audio
- Meeting recordings need text output
- Any "ghi âm → văn bản" or "transcribe Vietnamese" request

## Prerequisites (one-time setup)

```bash
pip install faster-whisper
```

No PyTorch needed — uses CTranslate2 runtime (~400MB total install).

## HuggingFace Token (persistent login)

Run once to persist the HF token for gated model access (pyannote, whisperX):

```bash
huggingface-cli login --token "hf_your_token_here"
```

This saves the token to `/root/.cache/huggingface/token` — no `HF_TOKEN` env var needed. Both pyannote.audio and huggingface_hub auto-detect it from the cache. After logging in, scripts do NOT need `token=` parameter or env vars passed explicitly.

## Diarization + Whisper (meeting transcription)

For multi-speaker meetings with true speaker identification, use `vi-meet.py`:

```bash
python3 /workspace/vi-meet.py "/host/d/path/meeting.m4a" -o output.txt --model medium
# For best accuracy: --model large-v3
# Adjust merge gap for overlapping speech: --gap 0.2 (tighter) or --gap 0.8 (looser)
```

Output format:
```
--- A ---
  [   0.4s -    2.4s] (2.1s) Rồi bây giờ là bình thường

--- B ---
  [   1.0s -    3.8s] (2.8s) Bây giờ là mình phải làm cái nhau như thế này xong rồi
```

This uses pyannote diarization (VAD + speaker clustering) + faster-whisper transcription. Detects overlapping speech and assigns speaker labels (A, B, C...). Requires HF token via persistent login (see above). Model cached at `~/.cache/huggingface/hub/models--pyannote--speaker-diarization-community-1` after first run — subsequent runs are fast.

## Usage

### Transcription script (reusable)
Located at `/hermes-home/skills/media/vietnamese-transcribe/scripts/vi-transcribe.py` — also copied to `/workspace/vi-transcribe.py`.

Full CLI with `--timestamps`, `--batch`, `--output`, `--model` options.

### Quick commands

```bash
# Single file → stdout
python3 /workspace/vi-transcribe.py <audio_file>

# Save to file
python3 /workspace/vi-transcribe.py <audio_file> -o transcript.txt

# With timestamps [HH:MM:SS]
python3 /workspace/vi-transcribe.py <audio_file> --timestamps

# Larger model for important recordings
python3 /workspace/vi-transcribe.py <audio_file> --model large-v3
```

### Supported models
| Model    | RAM   | Accuracy  | Best for                    |
|----------|-------|-----------|-----------------------------|
| base     | ~1GB  | Low       | Quick demos, test           |
| small    | ~2GB  | Medium    | Fast processing             |
| medium   | ~5GB  | Good      | Default — balance of speed/quality |
| large-v3 | ~10GB | Best      | Important meeting recordings |

## Related Files

- `scripts/vi-meet.py` — Full meeting transcription with pyannote diarization + faster-whisper (speaker A/B labels)
- `scripts/vi-transcribe.py` — Basic single-speaker transcription with batch mode support
- `references/diarization-workflow.md` — Decision guide: when to use which approach, model quality comparison, environment notes
- `references/single-pass-optimization.md` — Single-pass optimization technique: why transcribing full audio once is 5-10x faster than per-segment calls (includes benchmarks and overlap assignment algorithm)

### File paths on this system
**Windows drives are mounted at `/host/`, NOT `/mnt/`:**
- `D:\path\file.mp3` → `/host/d/path/file.mp3`
- `E:\path\file.m4a` → `/host/e/path/file.m4a`

Common workspace path: `/host/d/mkt/python/hermes/workspace/transcribe/`

## Multi-Speaker Meetings (Diarization)

For recordings with multiple speakers, choose the right approach:

| Scenario | Tool | Needs HF token? |
|----------|------|-----------------|
| Single speaker | `vi-transcribe.py` | No |
| Clear turns (no overlap) | `vi-transcribe.py --timestamps` | No |
| Overlapping speech / arguing | `vi-meet.py` (pyannote) | Yes (persistent login) |
| Quick draft, no diarization | `vi-transcribe.py` + manual labels | No |

### vi-meet.py parameters
- `--model` — whisper model size: `medium` (faster) or `large-v3` (more accurate). All models use int8 compression @ 4 CPU threads.
- `--gap` — max gap (seconds) to merge same-speaker segments separated by silence. Default 0.4s. Use tighter gaps for fast back-and-forth dialogue.
- `--output -o` — save to file instead of printing.
- `--timestamps` — format timestamps as HH:MM:SS instead of seconds.
- `--no-diarize` — skip pyannote diarization entirely. Outputs raw transcript only (~57s for 34s audio vs ~87s full pipeline). Speaker labels (A/B) not available.

### Choosing the right approach
- Clean meetings with clear speaker turns → just use basic `vi-transcribe.py` with timestamps
- Heavy overlap / arguing / fast back-and-forth → `vi-meet.py` (pyannote diarization)
- Solo speaker meeting → just use `vi-transcribe.py`


### Model Quality Comparison (Vietnamese)

| Issue | medium | large-v3 | Fixed? |
|-------|--------|----------|--------|
| văn bạng | ❌ | văn bản | ✓ |
| Tây Đăng Nha | ❌ | Tây Ban Nha | ✓ |
| tiếng Phát | ❌ | tiếng Pháp | ✓ |
| tiếng Hà | ❌ | tiếng Hàn | ✓ |
| Proper nouns (names, places) | garbled | better but still imperfect | partial |

**Recommendation**: Use `--model large-v3` for all important meeting recordings. The medium model has systematic phoneme confusions in Vietnamese (bạng→bản, Phát→Pháp). On this CPU-only system, large-v3 is slow but worth it for accuracy.

### PhoWhisper (Vietnamese-Specific Model) — Alternative Approach

PhoWhisper (`vinai/PhoWhisper-medium`) is a Whisper model fine-tuned on 844 hours of Vietnamese speech. Uses `transformers` pipeline (NOT compatible with faster-whisper).

```bash
# Install transformers deps
pip install transformers accelerate soundfile torch --index-url https://download.pytorch.org/whl/cpu

# Use the PhoWhisper transcriber
python3 /workspace/vi-transcribe-phonowhisper.py <audio_file> --model medium -o output.txt
```

**PhoWhisper vs Whisper-medium comparison:**

| Aspect | faster-whisper medium | PhoWhisper medium |
|--------|----------------------|--------------------|
| Speed (34s audio, CPU) | ~10-20s | ~23s/segment |
| Common VN words | "thi thoảng" → "thi thoại" ✗ | "thỉnh thoảng" ✓ |
| Proper nouns | Error-prone but preserves content | Drops content entirely |
| RAM | ~5GB | ~8GB |

**Verdict**: PhoWhisper is ~2× slower on CPU with marginal quality gains. Only use when you specifically need better Vietnamese word accuracy and have GPU. On CPU, stick with `faster-whisper large-v3`. See `references/phonowhisper-comparison.md` for full analysis.

## Pitfalls & Performance

  ### CPU benchmarks (measured on this system — no GPU, large-v3 int8 @ 4 threads)
For ~34s Vietnamese audio:
- **small**: ~30s total — quick drafts, low accuracy
- **medium**: ~70s total — default balance of speed/quality
- **large-v3 (int8)**: ~57s whisper + ~30s diarization = **~87s** full pipeline. Best for important meetings.
- **--no-diarize + large-v3**: **~57s** total — skip pyannote, raw transcript only

> These are SINGLE-PASS times (full audio transcribed once). Per-segment calls were 5-10× slower due to model initialization cost per call.

### int8 optimization
All scripts default to `compute_type="int8"` with `cpu_threads=4` — this is the sweet spot for whisper on this hardware. int8 halves memory vs float32 and maintains ~99% accuracy while cutting RAM usage from ~10GB to ~5GB for large-v3.

### Model downloads on first run:
faster-whisper models download from HuggingFace (~1GB for medium, ~3GB for large-v3). Subsequent runs load instantly from `~/.cache/huggingface/hub/`. Pyannote diarization model also caches after first download.

### Single-pass vs per-segment optimization:
The correct approach for di+erentiated meetings is:
1. Run pyannote diarization → get speaker-labeled segments with timestamps
2. Transcribe the FULL audio ONCE with whisper (one model call)
3. Assign each whisper segment to the closest diarization turn based on temporal overlap

Do NOT iterate over diarization turns and call `fw.transcribe()` per turn — this wastes the entire model initialization cost on every tiny 1-3s clip. See `references/single-pass-optimization.md` for details.
- **Accuracy issues**: Vietnamese proper nouns, names, and technical terms may be misrecognized. `large-v3` helps significantly over medium.
- **M4A/MP3 support**: ffmpeg must be installed (it is on this system). faster-whisper handles all common formats via av/ffmpeg backend.
- **Overlapping speech**: Energy-based turn segmentation can't separate overlapping speech — when two people talk simultaneously, energy gaps are absent. Use `vi-meet.py` (pyannote diarization) for real speaker identification across overlapping turns.
- **HF token caching**: After `huggingface-cli login`, the token is saved to `/root/.cache/huggingface/token`. Scripts auto-detect it — no need to pass `token=` parameter or set `HF_TOKEN` env var. The pyannote diarization model (`pyannote/speaker-diarization-community-1`) requires a valid HF token for gated access; the cached login handles this transparently.
