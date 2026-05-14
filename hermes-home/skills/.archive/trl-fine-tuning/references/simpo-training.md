# SimPO — Simple Preference Optimization (Reference-Free DPO)

## What is SimPO?
Simple Preference Optimization (SimPO) outperforms DPO without needing a reference model. Key advantages:
- **No reference model** — simpler setup, faster training
- **Better performance** (+6.4 points on AlpacaEval 2.0 vs DPO)
- **More efficient** — fewer parameters to manage

## Quick Start

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from simpo import SimPOConfig, SimPOTrainer  # or via TRL if supported

config = SimPOConfig(
    output_dir="./simpo-model",
    beta=2.0,              # Reward scaling (higher = stronger signal)
    gamma_beta_ratio=0.5,   # Target margin between chosen/rejected
    learning_rate=5e-7,     # Critical: 3e-7 to 1e-6
    num_train_epochs=1,
)

trainer = SimPOTrainer(
    model=model,
    args=config,
    train_dataset=preference_dataset,  # chosen/rejected pairs
    processing_class=tokenizer
)
trainer.train()
```

## Key Hyperparameters

| Parameter | Impact | Recommended Range |
|-----------|--------|-------------------|
| `beta` | Reward scaling strength | 2.0-10.0 (higher = stronger signal) |
| `gamma_beta_ratio` | Target margin | 0.5-0.7 |
| `learning_rate` | Convergence speed | 3e-7 to 5e-7 (lower than DPO) |
| `loss_type` | Optimization objective | sigmoid or hinge |
| `sft_weight` | SFT regularization | 0.0-0.1 (prevent capability loss) |

## SimPO vs DPO Comparison

| Aspect | DPO | SimPO |
|--------|-----|-------|
| Reference model | Required | Not needed |
| Setup complexity | Moderate | Simple |
| Performance | Good | Better (+6.4 AlpacaEval) |
| Memory usage | Higher (stores reference) | Lower |
| Tuning knobs | beta only | beta, gamma_beta_ratio |

## When to Use SimPO

- Have preference data (chosen/rejected pairs)
- Want simpler setup than DPO/PPO
- Need maximum performance from limited compute
- Training on single-node GPU

## Troubleshooting

**Loss divergence**: Reduce LR (3e-7) and beta (1.0)
**Capability loss**: Add SFT regularization (sft_weight=0.1)
**Poor separation**: Increase beta (5.0) and margin (gamma_beta_ratio=0.8)

## Resources
- Paper: arXiv:2405.14734 (NeurIPS 2024)
- GitHub: https://github.com/princeton-nlp/SimPO