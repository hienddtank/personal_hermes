# Kokoro Parallel Batch Processing (Shared Model Architecture)

## Core Pattern: Shared KModel + Pre-loaded Voice

**Critical insight:** `KPipeline` loads a new model on every `__call__` unless you pass your own. This causes ~12s overhead per chunk vs actual inference (~3s).

### WRONG — Per-chunk reload (slow):
```python
from kokoro import KPipeline
pipeline = KPipeline(lang_code="a")  # Model loaded fresh each call!

for text in texts:
    for g, p, audio_obj in pipeline(text, voice="af_heart"):
        ...  # ~15s per chunk total
```

### RIGHT — Shared model + pre-loaded voice (fastest):
If you pass `voice=` on every `.call()`, Kokoro calls `self.load_voice(voice)` internally (~2-3s overhead). Instead, bind voice in constructor:

```python
from kokoro import KModel, KPipeline

model = KModel(repo_id="hexgrad/Kokoro-82M", disable_complex=True).to("cpu").eval()
pipeline = KPipeline(lang_code="a", model=model)  
ref_s = pipeline.load_voice("af_heart")  # Load voice ONCE
```

## Parallel Worker Architecture

Each worker process gets its OWN `KModel` instance — you cannot share across Python processes. Distribute chunks via JSON files:

```python
# Main process distributes chunks to workers
for i in range(N_WORKERS):
    chunk_file = f"/tmp/kokero_worker_{i}_chunks.json"
    write_json(chunk_file, distribute_chunks(all_chunks, i, N_WORKERS))
    
# Workers write segments: /tmp/kokoro_seg_w{id}_{chunk_idx:05d}.wav
```

## Progress Monitoring (CRITICAL)

Workers can run for HOURS at 100% CPU producing ZERO segments if all chunks hit the same error. **Always verify progress within 60 seconds:**

```bash
# Check if ANY segments were created
ls /tmp/kokoro_seg_w*_*.wav | wc -l
# If returns 0, kill workers immediately and debug before waiting hours

for i in $(seq 0 7); do 
    echo "Worker $i: $(ls /tmp/kokoro_seg_w${i}_*.wav 2>/dev/null | wc -l) segments"
done

ps aux | grep kokero_worker
```

If stuck: `pkill -9 -f kokero_worker.py` then fix before restarting.

## Merging Segments

```bash
cat <(ls /tmp/kokoro_seg_w0_*.wav) \
    <(ls /tmp/kokoro_seg_w1_*.wav) ... > /tmp/all_segments.txt
ffmpeg -f concat -safe 0 -i /tmp/segment_list.txt -c copy output.mp3
```

## Performance Baselines (CPU-only)

| Approach | Chunks/min | Notes |
|----------|-----------|-------|
| Per-chunk KPipeline() instantiation | ~4 c/h (~0.07/s) | Model loads every time (~12s overhead) |
| Shared model + single pipeline | ~30-60 c/h (~0.5-1/s) | spaCy G2P is the hard limit per text |
| True batched forward_with_tokens | TBD | Would require bypassing KPipeline API entirely |
