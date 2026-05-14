# Multi-Speaker Transcription — Workflow & Lessons

## The Problem with "Who spoke when?"

Basic whisper (even large-v3) has **no speaker diarization**. It transcribes the entire audio as one stream. When multiple people talk:

1. **Turns with pauses** → works well if speakers take turns
2. **Overlapping speech** → garbled, words from both speakers merge into nonsense
3. **No way to label "Person A said X"** without external diarization

## Pipeline Options (Cheapest to Most Powerful)

### Option 1: Single File (`vi-transcribe.py`)
- **What**: Transcribe entire audio as one stream
- **When**: Solo speaker, clear audio
- **Pros**: Fastest, simplest
- **Cons**: No speaker identification at all

### Option 2: Energy-Based Turn Split (`vi-transcribe-diary.py`)
- **What**: Detect speech/silence energy boundaries → split into segments → transcribe each
- **When**: Meetings where speakers alternate with clear pauses between turns
- **Pros**: No downloads needed (just ffmpeg + faster-whisper), works on CPU
- **Cons**: 
  - Labels turns sequentially (Turn 1, Turn 2...) — NOT true speaker IDs
  - Can't handle overlapping speech at all
  - Very short turns (<0.8s) are skipped
  
**Real example from session:**
Recording: `New Recording 9 - arguing.m4a` (33.7s, two people talking over each other)
- Energy threshold 0.015 detected only 6 regions because speech was continuous
- Even when it found gaps, the overlap meant "Turn 2" and "Turn 3" were fragments of simultaneous speech
- **Conclusion**: For arguing/overlapping audio, energy-based split is useless

### Option 3: Pyannote Diarization (Requires HF Token)
- **What**: Deep learning model that clusters voice features to identify unique speakers
- **When**: Any multi-speaker recording where speaker ID matters
- **Pros**: True speaker identification (Speaker_00, Speaker_01, etc.)
- **Cons**: 
  - Requires `pip install pyannote.audio` (~2GB + downloads)
  - Requires HuggingFace token (`export HF_TOKEN=...`)
  - First model download takes time
  - CPU inference is slow for long recordings

### Option 4: whisperX (All-in-One)
- **What**: whisper + forced alignment + pyannote diarization in one package
- **When**: You want best quality and have GPU
- **Cons**: Heavy dependencies, timed out during install on this system

## Decision Matrix

| Scenario | Recommended Approach |
|----------|---------------------|
| Solo speaker recording | `vi-transcribe.py` (single file) |
| Meeting with clear pauses between speakers | `vi-transcribe-diary.py` (energy-based) |
| Heavy overlap / fast back-and-forth | Need pyannote/whisperX, or accept garbled output |
| Need actual speaker IDs (not just turn order) | Pyannote + HF token required |

## Vietnamese Quality Notes

From live testing with `New Recording 8.m4a` (29.2s, single speaker):

**medium model errors:**
- "văn bản" → "văn bạng" (systematic phoneme swap)
- "Tây Ban Nha" → "Tây Đăng Nha"
- "tiếng Pháp" → "tiếng Phát"
- "tiếng Hàn" → "tiếng Hà"

**large-v3 fixes all of these** — the improvement is dramatic. For important recordings, always use large-v3 despite slower CPU inference.

## Environment Notes

- **Windows paths**: Always convert to `/host/d/`, `/host/e/`, etc. NOT `/mnt/d/`
- **ffmpeg**: Required for audio decoding (already installed)
- **faster-whisper**: Uses CTranslate2, works on CPU without PyTorch
- **Model cache**: `~/.cache/huggingface/hub/` — subsequent runs load instantly
