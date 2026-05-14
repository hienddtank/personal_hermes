---
name: RL Project Scaffolding
trigger: always
description: Scaffold and govern RL projects — environment design, data pipelines, progress tracking, and workflow enforcement.
---

# RL Project Scaffolding

Bootstraps a reinforcement learning project with governance, environment design, data pipeline, and workflow enforcement.

## When to Use
- User asks to build an RL environment, RL trading system, or any RL project
- Need to establish project structure with proper splits, constraints, and progress tracking
- Starting a new ML project that needs structured experimentation

## Steps

### 1. Define Governance (AGENT.md)
Create `AGENT.md` with:
- **Goal**: Single sentence. What's the profit/success metric?
- **Data**: Source file, row count, date range, columns
- **Chronological Splits**: Train/Val/OOD with row indices and date ranges. OOD touched ONCE at end.
- **Scope Constraints**: Workspace boundary, runtime platform, no files outside project folder
- **Hardware Constraints**: VRAM cap, max runtime, GPU-only or CPU fallback
- **Workflow Cycle**: READ → WRITE → SWITCH → CHANGE → TEST → VERIFY
- **File Switching Rules**: Which file to read/write/switch based on current task

### 2. Design Environment (env/env.md + env/*.py)
Create environment spec then implementation:

**env.md** must include:
- State space: observation dimensions, feature groups, normalization
- Action space: discrete or continuous, action meanings
- Reward function: pure P&L or shaped, transaction costs
- Episode: data slice, termination conditions
- Trading mechanics: spread, slippage, leverage, capital, position sizing
- Window/lookback: warm-up period, historical context
- Design decisions with rationale
- Explicit "NOT in scope" section

**Environment code** (Gymnasium-compatible):
```python
class MyEnv(gym.Env):
    def __init__(self, csv_path, mode="train"): ...
    def _get_obs(self) -> np.ndarray: ...  # clipped to [-5, 5]
    def _execute_trade(self, action): ...
    def reset(self, seed=None, options=None): ...
    def step(self, action): ...
    def render(self): ...
```

### 3. Data Pipeline (scripts/prep_data.py)
Convert raw data → npz/Arrow format with pre-computed indicators:
- Parse CSV → numpy arrays
- Compute indicators (SMA, EMA, RSI, MACD, ATR, BB, etc.)
- Split chronologically → `data/{train,val,ood}.npz` (or .arrow)
- Verify round-trip (load back, check rows/columns)

### 4. Progress Tracking (PROGRESS/)
Every experiment gets a dated `PROGRESS/YYYY-MM-DD_<topic>.md`:
- What was tested, what changed, results (numbers), what to try next
- Dead ends after 3 iterations get `DEAD_END_<topic>.md`
- Check PROGRESS/ BEFORE starting any investigation

### 5. Systematic Testing (NOT just smoke tests)
Before training, write comprehensive tests for BOTH environment and model:

**Environment tests** (`env/test_env.py` — 60+ tests):
- Mode loading (train/val/ood), data shapes
- Observation space: shape, dtype, clipping, no NaN/Inf
- Step mechanics: hold, long, short, flips, re-opens
- Spread/slippage costs applied correctly
- Episode completion, reset, reproducibility with seeds
- All indicator columns: no NaN/Inf, correct length, value ranges (e.g., RSI in [0,100])

**Model tests** (`test_model.py` — 50+ tests):
- Construction, param count, layer types
- Forward pass: single obs, various batch sizes
- Output properties: no NaN/Inf, valid probabilities
- Action sampling (training) and argmax (inference) modes
- Gradient flow: all params get gradients, no NaN
- Optimizer step: params change after updates
- Save/load round-trip
- VRAM measurement, determinism with seeds
- Flexibility: different feat_dim, n_actions, hidden_dim

Run tests BEFORE any training. Zero failures required.

### 6. Smoke Test
Before moving to model:
- Environment: random actions for 100-200 steps, verify no crashes, no NaN
- Data: load Arrow files, verify shapes and values
- Log results in PROGRESS/

### 7. Evolution Strategies (when using CMA-ES / distribution-guided neuroevolution)
For projects using evolution instead of gradient-based RL (PPO, A2C), follow these patterns:

**Project structure** (adds `evo/` directory):
```
PROJECT/
├── evo/
│   ├── __init__.py
│   ├── trainer.py      # EvolutionTrainer: population, distribution, checkpoints
│   ├── fitness.py      # evaluate(), evaluate_batch() — NaN detection + penalty
│   └── flattener.py    # Flatten/unflatten state_dict ↔ 1D numpy vector
├── models/
│   └── checkpoints/    # Periodic saves: ckpt_gen{N}.npy + ckpt_gen{N}_meta.npz
└── models/log.txt      # Training log (append mode)
```

**Critical: σ must match weight scale**
- σ (distribution width) MUST be proportional to your model's weight initialization scale
- For orthogonal init with gain=0.01: σ_init ≈ 0.01–0.02, σ_max ≈ 0.5
- σ_init = 0.5 with tiny weights → NaN cascade through BatchNorm layers → entire population dead
- Clamp σ per-generation: `σ ← clip(σ, σ_min, σ_max)` where σ_min decays (e.g., ×0.98)
- Clip sampled weights to tight bounds like [-1, 1], not [-5, 5]

**Population initialization**:
- Start around base weights (orthogonal init), not from zero
- Add small noise (e.g., ×0.01) to create initial diversity
- Bootstrap distribution μ from population mean (not zeros) — critical for BatchNorm scale params

**Checkpointing for long runs** (10,000+ generations):
- Save every 100 gens: best weights (.npy) + full state (.npz with μ, σ, history)
- Enables resume from last checkpoint without re-deriving distribution
- Save log to file (append mode), monitor with `tail -f`

**NaN handling in fitness evaluation**:
- Wrap model forward pass in try/except for NaN/Inf logits
- Return hard penalty (e.g., -1000) for dead models
- Clean up: `del model, env; torch.cuda.empty_cache(); gc.collect()` after each evaluation

See `references/evolution-strategies.md` for detailed hyperparameter tuning guide.

## Project Structure
```
PROJECT/
├── AGENT.md              # Source of truth
├── PROGRESS/             # Findings, experiments, dead ends
├── data/                 # Processed splits (.npz or .arrow)
├── env/                  # RL environment — gym-compatible, NO PyTorch
│   ├── __init__.py
│   ├── trading_env.py    # Env: obs, actions, steps, rewards
│   └── test_env.py       # 60+ systematic tests
├── model.py              # Neural net architecture — algorithm-agnostic
│                         # Policy π + Value V (PyTorch nn.Module)
├── algo.py               # Training algorithm — uses env + model
│                         # (ppo.py, a2c.py, or evo/trainer.py)
├── test_model.py         # 50+ model tests
├── models/               # Trained models + checkpoints
├── scripts/              # prep_data.py, backtest.py, analysis
└── notebooks/            # Exploration
```

## Three-Layer Architecture

Separate concerns into three clean layers:

| Layer | File | Responsibility | Imports |
|-------|------|---------------|---------|
| **Environment** | `env/trading_env.py` | Market mechanics, obs, rewards | numpy, gym only |
| **Model** | `model.py` | Neural net (policy π, value V) | torch.nn only |
| **Algorithm** | `algo.py` | Training loop — uses env + model | env, model, torch |

- **model.py** is algorithm-agnostic: same network serves PPO, A2C, or evolution
- **env/** is isolated: gym interface, no PyTorch imports
- This separation enables swapping algorithms without touching env or model

## Pitfalls
- **OOD leakage**: Never train or tune on OOD data. Val is for tuning, OOD is the exam.
- **Feature duplication**: Watch for duplicate features in observation space
- **Indicator warmup**: Ensure enough lookback for longest indicator (SMA50 needs 50 candles min)
- **Arrow vs CSV**: Arrow is 10-100x faster for training loops. Always convert upfront.
- **VRAM overflow**: Cap model size early. 2GB VRAM = tiny networks (64-128 hidden units max).
- **Reward scaling**: Unscaled rewards cause NaN gradients. Clip or normalize.
- **Typo columns**: Catch column name typos early (assert column count after Arrow write)

## Verification
1. `python3 scripts/prep_data.py` → 3 Arrow files, round-trip verified
2. `from env import MyEnv; env.reset()` → observation shape correct, no crashes
3. 200 random steps → PnL computed, no NaN, trades counted
4. PROGRESS/ has at least one file documenting findings
