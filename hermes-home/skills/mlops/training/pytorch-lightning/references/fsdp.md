# PyTorch FSDP (Fully Sharded Data Parallel) — When You Need More Than Lightning's Built-in

## When to Use Raw FSDP Instead of Lightning's Trainer

- **Memory-bound models** where you need fine-grained control over parameter sharding
- **Custom forward passes** that don't fit cleanly into LightningModules
- **Mixed precision + CPU offloading** tuned for specific hardware configs
- **FSDP2** (experimental) features not yet available in Lightning

## Quick Start with Raw PyTorch

```python
import torch
from torch.distributed.fsdp import FullyShardedDataParallel as FSDP
from torch.distributed.fsdp import MixedPrecision, ShardingStrategy
from torch.distributed.fsdp.wrap import size_based_auto_wrap_policy

# Wrap model with FSDP
auto_wrap_policy = size_based_auto_wrap_policy(min_num_params=100_000_000)
model = FSDP(model, auto_wrap_policy=auto_wrap_policy)
```

## Key Patterns

### Mixed Precision Configuration

```python
mixed_precision = MixedPrecision(
    param_dtype=torch.float32,   # Parameters in FP32 for accuracy
    reduce_dtype=torch.float16,  # Gradients in FP16 for memory savings
    buffer_dtype=torch.float16   # Buffers in FP16
)

model = FSDP(model, mixed_precision=mixed_precision)
```

### CPU Offloading (for extremely large models)

```python
from torch.distributed.fsdp import CPUOffload

# Offloads parameters/gradients to CPU when not actively computing
model = FSDP(
    model,
    cpu_offload=CPUOffload(offload_params=True)
)
```

### Sharding Strategies Comparison

| Strategy | Parameter Shard | Gradient Shard | Activation | Use Case |
|----------|----------------|----------------|------------|----------|
| FULL_SHARD (ZeRO-3) | ✅ | ✅ | Local | Single GPU too small for full model |
| SHARD_GRAD_OP | ❌ | ✅ | Local | Most memory savings, fastest communication |
| NO_SHARD | ❌ | ❌ | Local | Debugging, profiling |
| HYBRID_SHARD | Partial | ✅ | Local | Multi-node with large GPU count |

### Custom Auto-Wrap Policies

```python
from torch.distributed.fsdp.wrap import transformer_auto_wrap_policy

# Wrap specific layer types
auto_wrap_policy = transformer_auto_wrap_policy(
    transformers_to_wrap={SomeTransformerLayer}
)

# Or wrap by size threshold
auto_wrap_policy = size_based_auto_wrap_policy(min_num_params=50_000_000)

model = FSDP(model, auto_wrap_policy=auto_wrap_policy)
```

### Activation Checkpointing (Memory Optimization)

```python
from torch.distributed.checkpoint import save_state_dict

# Save/restore state with sharded parameters
state_dict = model.state_dict()
save_state_dict(state_dict, checkpoint_path)

# Load and reconstruct sharded model
model = FSDP(model, auto_wrap_policy=auto_wrap_policy)
load_state_dict(model, checkpoint_path)
```

## Migration: PyTorch Lightning → Raw FSDP

If you're already using PyTorch Lightning with `strategy='fsdp'`, the main differences are:

**Lightning handles:**
- Process group initialization (`init_process_group`)
- DataLoader sharding (`DistributedSampler`)
- State dict saving/loading across ranks
- Mixed precision integration
- Checkpointing to a single path

**Raw FSDP gives you:**
- Fine-grained control over which layers get wrapped
- Custom forward passes that Lightning can't support
- Experimental FSDP2 features (FSDP2 wraps individual layers automatically)
- Direct access to sharding strategy internals

## Common Pitfalls

1. **Forgetting to wrap child modules**: If you have nested `nn.Module` objects, they need their own `FSDP` wrapping via `auto_wrap_policy` or manual wrapping.

2. **Grad norm clipping with FSDP**: Use `model.clip_grad_norm_()` instead of `torch.nn.utils.clip_grad_norm_()`:
```python
# Correct for FSDP
model.clip_grad_norm_(max_norm=1.0)
```

3. **Loss scaling in FP16**: Manual loss scaling is needed with raw PyTorch:
```python
loss = model(data).float()  # Convert back to FP32 for stability
loss.backward()
optimizer.step()
optimizer.zero_grad()
```

4. **State dict naming**: FSDP changes parameter names in state_dict. Use `model.state_dict()` directly or save/load with FSDP-specific helpers.

## References
- PyTorch FSDP Docs: https://pytorch.org/docs/stable/fsdp.html
- FSD2 (Experimental): https://pytorch.org/docs/master/fsdp2.html
- Lightning's FSDP integration: Use `strategy='fsdp'` in L.Trainer for simple cases