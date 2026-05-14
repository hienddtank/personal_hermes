# GRPO — Detailed Guide (Advanced)

## When to Use GRPO Specifically

Group Relative Policy Optimization (GRPO) from the DeepSeek R1 paper is a memory-efficient RL method that:
- **Generates multiple completions** per prompt and compares them within each group
- **No separate reward model needed** — uses heuristic rules as rewards
- **More sample-efficient than PPO** — learns from within-group comparisons

## Detailed Reward Function Design

### Rule-Based Rewards (No Training Needed)

```python
# 1. Format compliance
def format_reward(completions, **kwargs):
    import re
    pattern = r'<think>.*?</think>\s*<answer>.*?</answer>'
    return [1.0 if re.search(pattern, c[0]['content'], re.DOTALL) else 0.0
            for c in completions]

# 2. Correctness (math/coding)
def correctness_reward(prompts, completions, answer=None, **kwargs):
    responses = [c[0]['content'] for c in completions]
    # Extract final answer from each response
    extracted = [extract_answer(r) for r in responses]
    return [2.0 if a == gt else 0.0 for a, gt in zip(extracted, answer)]

# 3. Incremental partial credit
def incremental_format_reward(completions, **kwargs):
    responses = [c[0]['content'] for c in completions]
    rewards = []
    for r in responses:
        score = 0.0
        if '<think>' in r: score += 0.25
        if '</think>' in r: score += 0.25
        if '<answer>' in r: score += 0.25
        if '</answer>' in r: score += 0.25
        rewards.append(score)
    return rewards

# Combine rewards (weights matter!)
all_rewards = [
    lambda c, **kw: format_reward(c, **kw),         # Weight: 1.0
    lambda p, c, a, **kw: correctness_reward(p, c, a, **kw),  # Weight: 2.0
    lambda c, **kw: incremental_format_reward(c, **kw),         # Weight: 0.5
]

# Configure trainer with weighted rewards
from trl import GRPOConfig, GRPOTrainer

trainer = GRPOTrainer(
    model=model,
    reward_funcs=[f * w for f, w in zip(all_rewards, [1.0, 2.0, 0.5])],
    args=training_args,
    train_dataset=dataset
)
```

### Understanding GRPO Training Dynamics

**Expected Loss Pattern:** Loss starts near 0 and INCREASES during training — this is correct! The loss measures KL divergence from the initial policy. Monitor reward metrics instead.

**Healthy Training Progression:**
| Step | Reward | Reward Std | KL Divergence |
|------|--------|------------|---------------|
| 100  | 0.5    | 0.3        | 0.02          |
| 200  | 0.8    | 0.25       | 0.05          |
| 300  | 1.2    | 0.2        | 0.08          |

**Warning Signs:**
- Reward std → 0 (model collapsing to single response)
- KL exploding (> 0.5) (diverging too much, reduce LR)
- Reward stuck (reward functions too harsh or model capacity issue)

### Multi-Stage Training for Complex Tasks

```python
# Stage 1: Format compliance only
trainer1 = GRPOTrainer(model=model, reward_funcs=[format_reward], ...)
trainer1.train()

# Stage 2: Add correctness
trainer2 = GRPOTrainer(model=model, reward_funcs=[format_reward, correctness_reward], ...)
trainer2.train()
```

### Key Hyperparameters

| Parameter | Impact | Recommended Range |
|-----------|--------|-------------------|
| `num_generations` | Group size for comparison | 8-16 (higher = better signal) |
| `learning_rate` | Convergence speed/stability | 5e-6 (safe), 1e-5 (faster) |
| `max_completion_length` | Output verbosity | Match task (256-512 typical) |
| `gradient_accumulation_steps` | Effective batch size | Increase if GPU memory limited |

### Unsloth Integration for Faster GRPO

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="google/gemma-3-1b-it",
    max_seq_length=1024,
    load_in_4bit=True,
    fast_inference=True
)

model = FastLanguageModel.get_peft_model(
    model, r=32, target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]
)

trainer = GRPOTrainer(model=model, reward_funcs=all_rewards, ...)
```