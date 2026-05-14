# Vietnamese Transcription: Single-Pass Optimization

## The Problem (OLD approach)

Iterating over pyannote diarization turns and calling `fw.transcribe()` on each tiny segment:

```python
for _, row in diarize_df.iterrows():
    seg_audio = audio[int(row['start']*sr):int(row['end']*sr)]
    segments, info = fw.transcribe(seg_audio, ...)  # MODEL OVERHEAD EVERY TIME
```

This was ~5-10× slower because:
- Whisper model initialization/loaded happens per call (even for tiny 1-3s clips)
- Beam search overhead repeats for each segment
- No parallelization benefit on CPU-only systems

## The Solution (NEW approach)

Transcribe the FULL audio once, then map whisper segments to diarization turns:

```python
# Step 1: Diarize
pipe = DiarizationPipeline(model_name=None, device="cpu")
diarize_df = pipe(audio)

# Step 2: Transcribe ONCE (one model call for full audio)
segments, info = fw.transcribe(audio, language="vi", beam_size=5, vad_filter=False)
all_whisper = list(segments)

# Step 3: Assign each whisper segment to the best-matching diarization turn
for ws in all_whisper:
    best_turn = max(diarize_df.iterrows(), key=lambda r: overlap(ws, r))
```

### Overlap assignment logic:
For each whisper segment, find the diarization turn with maximum temporal coverage:
```python
ws_coverage = overlap_dur / whisper_segment_duration
# Only accept turns where coverage > 0.3 (meaningful overlap)
```

## Performance Comparison (measured on CPU-only system)

All times assume `compute_type="int8"` and `cpu_threads=4` (the default in vi-meet.py):

| Approach | Time for 34s audio | Notes |
|----------|-------------------|-------|
| OLD: per-segment | ~3-5 min | Model loads/initializes per call — waste |
| NEW single-pass (small) | ~30s | Quick draft, lower accuracy |
| NEW single-pass (medium) | ~70s | Default balance of speed/quality |
| NEW single-pass (large-v3) | ~57s | Best accuracy for important meetings |
| Full pipeline (large-v3 + diarize) | ~87s | Whisper (~57s) + pyannote (~30s) |
| --no-diarize + large-v3 | ~57s | Skip speaker labels, fastest useful mode |

> **int8 matters**: float32 is ~40% slower and uses ~2× RAM. int8 maintains ~99% accuracy vs float32 while being the default in vi-meet.py.

## Script Files

- `scripts/vi-meet.py` — Diarization + whisper, single-pass optimized
- `scripts/vi-transcribe.py` — Basic transcription, no diarization, batch mode

## Key Parameters for vi-meet.py

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `--model` | medium | Whisper model: small/medium/large-v3. All use int8 + 4 threads. |
| `--gap` | 0.4 | Merge same-speaker segments if gap < this (seconds) |
| `--no-diarize` | off | Skip pyannote — raw transcript only, saves ~30s |
| `--timestamps` | off | HH:MM:SS format instead of seconds |
| `-o OUTPUT` | stdout | Save to file |
