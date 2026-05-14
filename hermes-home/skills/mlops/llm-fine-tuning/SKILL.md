---
name: llm-fine-tuning
description: LLM fine-tuning, pretraining, and distributed training — PEFT/LoRA (parameter-efficient), TRL (RLHF/DPO/GRPO), Accelerate (distributed), TorchTitan (pretraining), and PyTorch Lightning. Use for adapting models to custom datasets, alignment training, multi-GPU scaling, or distributed pretraining.
---

# LLM Fine-Tuning & Training

## Decision Tree

```
Training LLMs?
├── Fine-tuning 7B-70B+ on limited GPU memory
│   └── PEFT/LoRA — parameter-efficient fine-tuning (<1% params)
├── RLHF / DPO / preference alignment
│   └── TRL — reinforcement learning from human feedback
├── Multi-GPU / multi-node distributed training
│   └── Accelerate — simple distributed training API
├── Pretraining from scratch (B-scale+)
│   └── TorchTitan — PyTorch-native distributed pretraining
└── Custom training loops, callbacks, experiment tracking
    └── PyTorch Lightning — high-level trainer framework
```

## Quick Comparison

| Tool | Purpose | Scale | Key Feature |
|------|---------|-------|-------------|
| **PEFT/LoRA** | Parameter-efficient FT | 7B-70B+ | <1% params, 6MB adapters |
| **TRL** | RLHF, DPO, SFT | Any | Preference alignment |
| **Accelerate** | Distributed training | Any | 4 lines for multi-GPU |
| **TorchTitan** | Pretraining | B-scale+ | PyTorch-native, no XLA |
| **Lightning** | Training framework | Any | Callbacks, plugins, flexibility |

## Quick Starts

### PEFT/LoRA — Parameter-Efficient Fine-Tuning
```python
from transformers import AutoModelForCausalLM
from peft import get_peft_model, LoraConfig, TaskType

model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.1-8B", torch_dtype="auto")

lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]
)
model = get_peft_model(model, lora_config)
# trainable: 0.17% (14M params of 8B)
model.save_pretrained("./lora-adapter")  # ~6MB
```

### TRL — Supervised Fine-Tuning (SFT)
```python
from trl import SFTTrainer, SFTConfig
from transformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.1-8B")

trainer = SFTTrainer(
    model=model,
    args=SFTConfig(output_dir="./output", per_device_train_batch_size=4),
    train_dataset=dataset,
)
trainer.train()
```

### TRL — DPO (Direct Preference Optimization)
```python
from trl import DPOTrainer, DPOConfig

trainer = DPOTrainer(
    model=model,
    args=DPOConfig(beta=0.1, output_dir="./dpo-output"),
    train_dataset=preference_dataset,  # {prompt, chosen, rejected}
)
trainer.train()
```

### Accelerate — Multi-GPU Training
```python
from accelerate import Accelerator
accelerator = Accelerator()

model, optimizer, train_dataloader, lr_scheduler = accelerator.prepare(
    model, optimizer, train_dataloader, lr_scheduler
)

for batch in train_dataloader:
    optimizer.zero_grad()
    loss = model(**batch).loss
    accelerator.backward(loss)
    optimizer.step()
    lr_scheduler.step()
```

### TorchTitan — Distributed Pretraining
```bash
# Multi-node pretraining
python -m torch.distributed.run \
    --nproc_per_node=8 \
    --nnodes=4 \
    titain/train.py \
    --config configs/gpt2_medium.yaml
```

## When to Use Each

| Scenario | Recommended Tool |
|----------|-----------------|
| Fine-tune on single GPU, limited memory | PEFT + QLoRA |
| Fine-tune with RLHF/DPO | TRL (SFT → DPO/RL) |
| Multi-GPU training | Accelerate |
| Multi-node pretraining | TorchTitan |
| Custom training loops | Lightning |
| Full pipeline (config → train) | Axolotl |

## Common Workflows

### Full Fine-Tuning Pipeline
1. **PEFT/LoRA** → parameter-efficient adapters
2. **TRL SFT** → supervised fine-tuning
3. **TRL DPO** → preference alignment
4. **vLLM** → deployment

### Multi-Node Pretraining
1. **TorchTitan** → distributed pretraining
2. **Accelerate** → coordinate across nodes
3. **DeepSpeed/FSDP** → ZeRO optimization

## Best Practices
1. **Start with LoRA r=8-16** for fine-tuning
2. **Use QLoRA** for 70B+ on single GPU
3. **SFT before DPO** — align before preference optimize
4. **Gradient checkpointing** — reduces memory 30-50%
5. **fp16/bf16 mixed precision** — faster, less memory
6. **Save adapters separately** — easy to swap/compare

## Resources
- PEFT: https://huggingface.co/docs/peft
- TRL: https://huggingface.co/docs/trl
- Accelerate: https://huggingface.co/docs/accelerate
- TorchTitan: https://github.com/pytorch/torchtitan
- Lightning: https://lightning.ai/docs/pytorch
