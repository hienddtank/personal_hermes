# Async Micro-Batched TTS (NimbleEdge Pattern)

## When to Use This Pattern
- GPU environment available with large document batches (>4500 chunks)
- Need significantly faster throughput than serial KPipeline calls (~0.15 text/sec)
- Voice preset: typically `af_heart` for English female voice

## Key Concept
Don't use `KPipeline.__call__` in a loop (processes one text at a time). Instead, use `forward_with_tokens()` directly via micro-batching to process 16 texts in a single GPU/CPU forward pass. Asyncio collects requests for ~20ms, then fires up to 16 at once.

## Expected Performance
- Serial KPipeline: ~0.15 texts/sec (13s per text)
- Async batched: 2-8+ texts/sec depending on hardware (16x speedup potential)
- Total for 4512 chunks serial: ~750 min (~12.5 hours) → with batching under 3 hours

## Critical API Gotchas

1. **KPipeline returns `(grapheme, phoneme_str, torch.Tensor)`** — third element is audio as torch.Tensor, NOT sample rate
2. **No `phonemize()` function exists** in kokoro package — use `pipeline.g2p(text)` via spaCy internally
3. **Reference sound for voice**: Load with `pipeline.load_voice("af_heart")` which returns a torch tensor. Must be unsqueezed and repeated: `ref_s.unsqueeze(0).repeat(batch_size, 1).float()`
4. **forward_with_tokens signature**: `(input_ids, ref_s, speed)` — second arg is REFERENCE SOUND TENSOR (voice embedding), NOT sample rate! #1 source of bugs
5. **NumPy 2.0 compatibility**: Use `.max()` method instead of `np.max(x, axis=...)`
6. **Audio must be numpy array** — Kokoro returns `torch.Tensor`. Convert: `audio.cpu().numpy()` before soundfile.write()
7. **KPipeline doesn't expose batch_size=16 knob** in public API. True batching requires direct `forward_with_tokens()` calls with padded input tensors.

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| TypeError: integer required in soundfile.write() | Passing Kokoro's phoneme string as sample rate | Always use SAMPLE_RATE=24000; ignore `sr` from KPipeline |
| Workers crash silently with NumPy error | `np.max()` API changed in NumPy 2.0 | Use `.max()` method: `float(np.abs(audio).max())` |
| ImportError: cannot import 'phonemize' | phonemize() doesn't exist in kokoro package | Don't import it — use KPipeline's internal g2p |
| Audio is silent/0 samples | ref_s not passed correctly to forward_with_tokens | Must be shape [B, 192] tensor repeated for batch size |
