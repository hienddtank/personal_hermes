# Evolution Strategies for Neuroevolution

Distribution-guided evolution (CMA-ES style) for training RL policies without gradients.

## Session: STOCK_RL USD/JPY Evolution (2026-05-06)

### σ (Distribution Width) — Most Critical Hyperparameter

**Rule: σ must match weight initialization scale.**

| Model Weight Scale | σ_init | σ_max | σ_floor | σ_decay |
|---|---|---|---|---|
| orthogonal gain=0.01 | 0.02 | 0.5 | 0.001 | 0.98 |
| orthogonal gain=1.0 (default) | 0.5 | 3.0 | 0.01 | 0.98 |

**What happened with wrong σ**:
- Started with σ_init=0.5, σ_max=3.0, weight_clip=[-5, 5]
- Model uses orthogonal init gain=0.01 (weights ~0.01)
- σ=0.5 samples weights ±0.5, which is 50× the model's design scale
- Through BatchNorm + tanh + multiple layers → NaN cascade
- Result: 90%+ of population scored -1000 (NaN penalty), mean fitness -939
- After fix (σ_init=0.02, σ_max=0.5, clip=[-1,1]): mean fitness -10 to -15, models surviving

### Distribution EMA Smoothing
```python
# Per-generation update:
mu_candidate = elite_set.mean(axis=0)   # top-8 mean
sigma_candidate = elite_set.std(axis=0) # top-8 std

beta = 1.0 - ema_alpha  # 0.7
mu = beta * mu + ema_alpha * mu_candidate
sigma = beta * sigma + ema_alpha * sigma_candidate
sigma = clip(sigma, sigma_min, sigma_max)
sigma_min = max(sigma_min * sigma_decay, sigma_floor)
```

### Population Initialization
```python
model = ActorCriticNet()  # orthogonal init gain=0.01
base = flattener.flatten(model.state_dict())
noise = rng.randn(pop_size, dim) * 0.01
population = base[None, :] + noise

# Bootstrap distribution from population (NOT zeros)
mu = population.mean(axis=0)  # critical for BatchNorm scale weights ~1.0
sigma = clip(population.std(axis=0), sigma_min, sigma_max)
```

### Checkpoint Pattern for Long Runs
```python
# Every 100 generations (or on final gen):
np.save(f"ckpt_gen{gen}.npy", best_weights)
np.savez(f"ckpt_gen{gen}_meta.npz",
    history_gen=history["gen"],
    history_best=history["best"],
    mu=mu, sigma=sigma, sigma_min=sigma_min,
    best_fitness=best_fitness, gen=gen, elapsed=elapsed)
```

### NaN Detection in Fitness
```python
def evaluate(weights, flattener, device, steps=200):
    model = ActorCriticNet().to(device)
    state_dict = flattener.unflatten(weights)
    state_dict = {k: v.to(device) for k, v in state_dict.items()}
    model.load_state_dict(state_dict)
    model.eval()

    env = ForexEnv(mode="train")
    for _ in range(steps):
        obs = torch.tensor(env._get_obs(), device=device).unsqueeze(0)
        with torch.no_grad():
            try:
                action, _, _ = model.get_action(obs, training=False)
            except ValueError:  # NaN in logits
                return -1000.0  # penalty

        if torch.isnan(action).any():
            return -1000.0
        env.step(action.item())

    # Cleanup
    del model, env
    torch.cuda.empty_cache()
    gc.collect()
    return float(env.pnl)
```

### Background Process Monitoring
```bash
# Launch with unbuffered output to file:
python3 -u -m evolution.trainer >> models/log.txt 2>&1

# Monitor:
tail -f models/log.txt
```

### Timing
- With 200 steps: ~20s per generation (32 models)
- With 2,000 steps: ~270s for gen 0, ~8-25s for subsequent gens (data reuse)
- 50,000 gens at ~20s each ≈ 28 days total

### VRAM
- Peak: 9 MB (tiny models, no gradients)
- Watchdog threshold: 1800 MB (auto-kill via os._exit(1))
