---
name: evolution-strategy-training
description: "Evolution strategy (ES) hyperparameter tuning, distribution-guided optimization, and checkpoint patterns for long-running evolution runs."
version: 1.0.0
author: Hermes Agent
tags: [evolution-strategy, NEAT, distribution-guided, hyperparameters, checkpointing, sigma-scaling]
---

# Evolution Strategy Training

Distribution-guided evolution for ML model weight optimization — evolving neural network parameters without gradients using population-based search with Gaussian distributions.

## When to Use

- Training RL policies where gradient-based methods are unstable
- Optimizing model architectures or hyperparameters
- When you need checkpoint-safe long runs (thousands of generations)
- User asks about evolution, NEAT, or population-based training

## Critical: σ Scaling to Weight Distribution

**This is the #1 failure mode.** If σ is too large relative to weight scale, nearly all sampled models produce NaN and get penalized.

**Rule**: `sigma_min_init` should match the standard deviation of your base weights, not be arbitrary.

```python
# BAD: σ=0.5 for weights with gain=0.01 (50x too large → 90% NaN)
sigma_min_init = 0.5  # most models die

# GOOD: σ=0.02 matches weight scale
sigma_min_init = 0.02  # models survive and learn
```

**Typical σ bounds**:
- gain=0.01 orthogonal: σ_min=0.02, σ_max=0.5, σ_floor=0.001
- gain=0.1: σ_min=0.1, σ_max=1.0, σ_floor=0.01
- He init (gain≈1): σ_min=0.5, σ_max=3.0, σ_floor=0.01

See `references/sigma-scaling-notes.md` for derivation.

## Checkpoint Pattern for Long Runs

For runs of 10,000+ generations, save state periodically. Must save:

1. **Best weights** (`.npy`) — recover best model
2. **Distribution state** (`.npz`) — recover evolution state (mu, sigma, history)

```python
# In trainer run loop, every N generations:
if gen % checkpoint_interval == 0:
    np.save(ckpt_dir / f"ckpt_gen{gen}.npy", best_weights)
    np.savez(ckpt_dir / f"ckpt_gen{gen}_meta.npz",
             best_fitness=best_fitness,
             sigma_min=sigma_min,
             mu=mu, sigma=sigma,  # distribution state
             elapsed=elapsed, gen=gen)
```

**Checkpoint interval**: 100 generations for runs >10,000 gens. Adjust based on gen time.

## Evaluation: Sequential vs Chunked Parallel

**Sequential** (default): Evaluate one model at a time, clean up GPU memory.
- VRAM: ~9MB regardless of population size
- Time: linear in population size
- Best for: VRAM-constrained setups (2GB cap), debugging

**Chunked parallel**: Process N models simultaneously, clean up between chunks.
- VRAM: chunk_size × ~9MB (128 models ≈ 1.2GB)
- Measured speedup: **35% faster** (115s → 74s/gen with pop=512, chunk=128)
- Use chunk_size=128 when you have 2GB+ free VRAM
- See `references/evaluation-patterns.md` for full implementation

**WSL2 VRAM zombie quirk**: Killed Python processes on WSL2 can leave "zombie" VRAM that doesn't free until Docker restart. Check with `nvidia-smi --query-compute-apps=pid,used_memory --format=csv -i <gpu>`. If no apps listed but VRAM shows used, it's stale. Free with Docker restart or reduce chunk size to fit available memory.

## Population Size Guidance

- 32: Quick experiments, 10-30s per gen
- 512: Production training, 60-300s per gen
- 2048+: Massive search, hours per gen

## Distribution EMA Smoothing

Smooth the candidate distribution with EMA to avoid overfitting to one generation's winners:

```python
beta = 1.0 - ema_alpha  # e.g., 0.7
mu = beta * mu + ema_alpha * mu_candidate
sigma = beta * sigma + ema_alpha * sigma_candidate
sigma = np.clip(sigma, sigma_min, sigma_max)
sigma_min = max(sigma_min * sigma_decay, sigma_floor)
```

Typical values: `ema_alpha=0.3`, `sigma_decay=0.98`

## Pitfalls

1. **σ too large → NaN epidemic**: 90%+ of population gets -1000 penalty. Fix by matching σ to weight scale.
2. **Not saving distribution state**: Can recover best model but can't resume evolution from checkpoint. Always save mu/sigma.
3. **Weight clipping too wide**: `np.clip(pop, -5, 5)` is meaningless if weights should be ±0.01. Tighten clip to ±1.0 or less.
4. **Random seed not fixed**: Different starts = non-reproducible results. Always set `np.random.RandomState(seed)`.
5. **Environment data loading per evaluation**: If each evaluation recreates the environment from disk, 512 models × 5000 steps becomes I/O bound. Preload data once.
6. **Envs staying alive full budget → performance cliff**: If your env's `done` condition depends on events models learn to avoid (e.g., stop-loss hits), gen 0-2 will be fast (~90s) but gen 3+ can slow 50x (~67min/gen). Add hard `max_steps` limit, per-100-steps progress logging, and move `gc.collect()` from per-chunk to single call at end. See `references/evaluation-patterns.md` section "Performance Cliff".

## Running Long Evolution in Background

```bash
# Launch with unbuffered output to log file
cd /path/to/project
python3 -u -m evolution.trainer >> models/log.txt 2>&1 &

# Monitor progress
tail -5 models/log.txt

# Check checkpoint directory
ls -lh models/checkpoints/
```

## Advanced: Autonomous Self-Modify Loop

For unsupervised code optimization, the self-modify-loop pattern uses Codex/AI agents in a closed loop to propose and test code changes to `trainer.py`, `model.py`, etc. The agent proposes → implements → runs ES training → evaluates → keeps only improvements. See `self-modify-loop` for the full architecture.

## Related Skills

- `robust-batch-processing` — general checkpoint patterns
- `jupyter-live-kernel` — interactive exploration before committing to long runs
- `self-modify-loop` — AI agent proposes code changes, runs ES training, keeps only improvements (autonomous optimization)

## Support Files

- `references/sigma-scaling-notes.md` — Derivation of σ scaling rules
- `references/evaluation-patterns.md` — Sequential vs chunked eval, performance cliff mitigation
- `references/self-modify-loop-debugging.md` — Diagnosing Codex-proposed code change crashes (flattener mismatches, crash taxonomy, decision flow)
