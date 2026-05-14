# Evaluation Patterns for Evolution Strategy

## Sequential Evaluation (Default)

Evaluate one model at a time, clean up GPU memory between each:

```python
def evaluate_batch_sequential(population, flattener, device, steps):
    pop_size = population.shape[0]
    fitnesses = np.zeros(pop_size, dtype=np.float32)
    
    for i in range(pop_size):
        model = load_model(population[i], flattener, device)
        fitnesses[i] = run_episode(model, env, steps)
        del model
        torch.cuda.empty_cache()
        gc.collect()
    
    return fitnesses
```

**Pros**: VRAM stays at ~9MB regardless of population size
**Cons**: Linear time in population size. 512 models × 5000 steps = very slow.

## Chunked Parallel Evaluation (Recommended for pop > 64)

Process N models simultaneously using batched observations. Tested with pop=512, chunk=128:
- VRAM: ~20MB peak (first chunk) — models share GPU memory efficiently
- Speedup: **35%** (115s → 74s/gen with pop=512, steps=5000)

```python
def evaluate_batch_chunked(population, flattener, device, steps, chunk_size=128):
    pop_size = population.shape[0]
    fitnesses = np.zeros(pop_size, dtype=np.float32)
    
    for offset in range(0, pop_size, chunk_size):
        end = min(offset + chunk_size, pop_size)
        chunk_n = end - offset
        
        # Load all models in this chunk
        models = [load_model(population[offset + i], flattener, device) 
                  for i in range(chunk_n)]
        
        # Create all envs in this chunk
        envs = [create_env(start_offset=starts[offset + i]) for _ in range(chunk_n)]
        
        # Step all envs together
        alive = [True] * chunk_n
        for _ in range(steps):
            obs_batch, alive_idx = [], []
            for j in range(chunk_n):
                if alive[j]:
                    obs = envs[j]._get_obs()
                    if np.isfinite(obs).all():
                        obs_batch.append(obs)
                        alive_idx.append(j)
            
            if not alive_idx:
                break
            
            obs_tensor = torch.tensor(obs_batch, dtype=torch.float32, device=device)
            
            with torch.inference_mode():
                for idx, j in enumerate(alive_idx):
                    action = models[j].get_action(obs_tensor[idx:idx+1], training=False)
                    envs[j].step(int(action.item()))
                    if envs[j].done or envs[j].truncated:
                        alive[j] = False
            
            if all(not a for a in alive):
                break
        
        # Collect fitnesses
        for j in range(chunk_n):
            fitnesses[offset + j] = envs[j].pnl
        
        # Cleanup chunk
        del models, envs
        torch.cuda.empty_cache()
        gc.collect()
    
    return fitnesses
```

**Key points**:
- Use chunk_size=128 when you have 2GB+ free VRAM
- Each model uses ~9MB, so 128 × 9MB ≈ 1.2GB (but actual peak is ~20MB due to shared memory)
- Models are evaluated one forward pass at a time per step, but env overhead is amortized
- Always use `common_start=True` for fair comparison within a generation

## WSL2 VRAM Zombie Quirk

On WSL2, killed Python processes can leave zombie VRAM that doesn't free until Docker restart:
```bash
# Check for zombie processes
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv -i 1
# If empty but VRAM shows used, it's stale

# Fix: reduce chunk_size to fit available memory, or restart Docker
```

## Common Start Pattern

For fair comparison, all models in a generation should evaluate on the same data slice:

```python
# Sample ONE start offset for the entire generation
start = rng.randint(WARMUP, data_len - steps)
starts = np.full(pop_size, start)  # all models use same start
```

This ensures selection pressure is on policy quality, not lucky market windows.

## Performance Cliff: Environments Staying Alive

When your environment's `done` condition depends on events that evolved models learn to avoid, gen 0-2 will be fast but gen 3+ can slow dramatically.

### Observed Behavior (2026-05-06, forex trading env)

| Gen | Env Lifespan | Time/Gen | Notes |
|-----|-------------|----------|-------|
| 0-2 | <100 steps | ~90s | Random models trigger stop-loss/take-profit |
| 3+ | All 5000 steps | ~67min | Evolved models keep positions open |

This is a **50x slowdown** — at 67min/gen, 50,000 gens would take ~230 days.

### Diagnosis

Add per-100-steps progress logging in your stepping loop:

```python
for step_i in range(steps):
    # ... your stepping logic ...
    if step_i % 100 == 0 and step_i > 0:
        alive_count = sum(alive)
        print(f"  step {step_i}/{steps} alive={alive_count}/{chunk_n}", flush=True)
```

If you see `alive=N/N` persisting through all steps, your envs are surviving the full budget.

### Fixes (pick one or combine)

1. **Hard episode length limit**: Add `max_steps` to env — force `done=True` after N steps
2. **Reduce steps per model**: From 5000 → 1000 (5x faster)
3. **Max trade duration**: Most trading envs have `max_bars=100` but models open new trades continuously
4. **Increase chunk size**: Fewer env creations total, but more VRAM per chunk
5. **Reduce population**: Smaller pop = fewer total models × steps

### GC Placement

Move `gc.collect()` from per-chunk to single call at end of evaluation:

```python
# BAD — GC per chunk adds compounding overhead
for offset in range(0, pop_size, chunk_size):
    # ... evaluate chunk ...
    gc.collect()  # ← slow, especially later gens

# GOOD — single GC at end
for offset in range(0, pop_size, chunk_size):
    # ... evaluate chunk ...
    torch.cuda.empty_cache()

gc.collect()  # ← once, after all chunks
```

- pop=512, steps=5000, sequential: ~115s/gen — episodes end early (done/trunc before 5000 steps)
- pop=512, steps=5000, chunked(128): ~74s/gen — 35% speedup
- Environment warmup period may consume significant steps
- Mean fitness near 0 with small losses suggests models barely trade — may need reward structure adjustment
