# Self-Modify Loop Debugging

## The Self-Modify Loop Pattern
Codex proposes code changes → script runs ES training → results recorded as keep/discard/crash → loop continues.

**Key files:** `STOCK_RL/.self_modify_loop/results_stock_rl.tsv` (results table), `.self_modify_loop/run_logs/` (per-run logs), `.self_modify_loop/last_run.md` (latest run summary).

## Diagnosing Crashes: The Flattener Mismatch

### Most Common Failure: `KeyError` in flattener.offsets
```
KeyError: 'actor_residual.0.bias'
  File "trainer.py", line 280, in _stack_actor_params
    lo, hi = flattener.offsets[key]
```

**Root cause:** Codex added a new `nn.Linear`, `nn.Parameter`, or submodule to the model class that wasn't registered as a proper `nn.Module` child. The flattener iterates `.parameters()` to build its offset map — new parameters must appear there.

**Fix:** Ensure any new layer is an actual `nn.Module` submodule:
```python
# BROKEN — raw tensor won't be discovered
self.my_param = torch.zeros(10)

# FIXED — proper parameter registered with the module
self.my_layer = nn.Linear(in_features, out_features)  # auto-discovered
# OR
self.my_param = nn.Parameter(torch.zeros(10))
```

### Other Crash Patterns
| Symptom | Likely Cause |
|---------|-------------|
| `KeyError` on a parameter name | Flattener mismatch (new param not registered as submodule) |
| `CUDA out of memory` | New layer adds too many params for 2GB VRAM cap |
| Shape mismatch errors (`mat1 and mat2`) | Parameter dimension changed, breaking trainer's flat→unflat roundtrip |
| NaN fitness from gen 0 | Initialization broke — loss is exploding immediately |

## Analyzing Results: Keep vs Discard Decision Heuristics

### Typical outcome distribution (observed in practice)
- **~30% keep** — genuine improvements to model/fitness/trainer
- **~50% discard** — underperformed relative to best kept, or noisy results
- **~10% crash** — architecture broke the flattener or OOM'd
- **~10% rejected** — tried to modify protected files (env.py, reward.py)

### What tends to work (from 30 runs observed)
1. **Small gated residuals on model heads** (+59% improvement over baseline)
2. **Hall-of-fame archive** in trainer (+46%)
3. **Rank-weighted parent selection + immigrants** (+27%)
4. **Stagnation-triggered adaptive mutation** (+1%)

### What tends to fail
1. **Complex model heads** (dueling, attention pooling) — too many new params → flattener/OOM crashes
2. **Deep trainer modifications** (species clustering) — breaks assumptions in fitness evaluation
3. **Per-layer mutation scales** — touches protected `fitness.py` files

## Decision Flow for Debugging a Crash

```
1. Read run log: F:/AI/self_modify_baseline/STOCK_RL/.self_modify_loop/run_logs/<run_id>.log
2. Find first ERROR/CRASH line
3. If KeyError on parameter → flattener issue (see above)
4. If CUDA OOM → too many params for VRAM cap
5. If shape mismatch → trainer can't unflat the genome
6. If NaN loss → bad initialization, try smaller init scale
7. Check if Codex modified any protected files → reject automatically
```

## Preventing Future Crashes

### Guardrails for Codex prompts
- Explicitly list allowed code paths vs protected paths
- Require that new layers use `nn.Linear/nn.Conv2d/nn.Parameter` (not raw tensors)
- Ask Codex to confirm parameter names match expected shapes
- Cap max added parameters in proposals

### Self-check before running
```python
# Quick validation script to run before training:
from model import ActorCriticNet
import torch

model = ActorCriticNet()  # or whatever the config dictates
params = list(model.named_parameters())
expected_names = {"old_name_1", "old_name_2"}  # known good set
actual_names = {n for n, _ in params}
new_params = actual_names - expected_names
if new_params:
    print(f"WARNING: New parameters detected: {new_params}")
```
