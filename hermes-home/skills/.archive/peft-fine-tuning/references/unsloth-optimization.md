# Unsloth — 2-5x Faster LoRA Fine-Tuning with Less VRAM

## What is Unsloth?
Unsloth wraps PEFT's LoRA/QLoRA methods to provide:
- **2-5x faster training** via fused kernel optimizations
- **60% less GPU memory** through optimized memory management
- Full compatibility with PEFT's API — swap in without code changes

## When to Use Unsloth Instead of Raw PEFT

| Scenario | Recommendation |
|----------|---------------|
| Standard LoRA fine-tuning on <24GB GPU | ✅ Unsloth (saves memory) |
| QLoRA 4-bit training | ✅ Unsloth (much less VRAM needed) |
| Custom PEFT methods (IA3, PrefixTuning) | Use raw PEFT |
| Multi-LoRA experiments | Unsloth for speed |
| Production fine-tuning pipeline | Unsloth → then export standard LoRA weights |

## Quick Start Comparison

### Raw PEFT (standard approach):
```python
from peft import LoraConfig, get_peft_model

config = LoraConfig(
    r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05, bias="none"
)
model = get_peft_model(model, config)
```

### Unsloth (drop-in replacement):
```python
from unsloth import FastLanguageModel

# Load model with 4-bit quantization + optimized kernels
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="meta-llama/Llama-2-7b-hf",
    max_seq_length=2048,
    load_in_4bit=True,  # QLoRA mode
)

# Same LoRA config!
FastLanguageModel.prepare_model_for_kbit_training(model)
config = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"])
model = FastLanguageModel.get_peft_model(model, config)
```

## Key Differences

| Feature | Raw PEFT | Unsloth |
|---------|----------|---------|
| Speed | Baseline | 2-5× faster |
| Memory (7B model) | ~14GB VRAM (4-bit) | ~4.5GB VRAM (4-bit) |
| Compatibility | Full PEFT API | Subset (LoRA/QLoRA only) |
| Custom modules | ✅ Any | ❌ Predefined list |
| Export standard LoRA | ✅ Native | ⚠️ Need conversion step |

## Converting Unsloth LoRA → Standard PEFT LoRA

```python
# After training with Unsloth:
model.save_pretrained("unsloth-lora")

# Convert to standard LoRA adapter
from peft import PeftModel
standard_model = PeftModel.from_pretrained(
    base_model, "unsloth-lora", is_trainable=False
)
standard_model.save_pretrained("standard-lora")
```

## Pitfalls

1. **Only supports LoRA/QLoRA**: If you need IA3 or Prefix Tuning, use raw PEFT.
2. **Pretrained model list limited**: Unsloth only works with certain pre-configured models. Check their model list before committing.
3. **Longer sequence lengths**: Unsloth has limits on max_seq_length for some models.
4. **Export conversion needed**: Unsloth LoRA weights aren't directly compatible with PEFT without the conversion step above.

## Resources
- GitHub: https://github.com/unslothai/unsloth