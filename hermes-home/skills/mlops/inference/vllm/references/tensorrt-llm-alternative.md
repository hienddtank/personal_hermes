# TensorRT-LLM — When vLLM Isn't Enough

## What is TensorRT-LLM?
NVIDIA's optimized inference engine for maximum throughput and lowest latency on NVIDIA GPUs. It pre-compiles models into optimized execution graphs using CUDA kernels, FlashAttention, and tensor core optimizations.

## Decision Matrix: vLLM vs TensorRT-LLM

| Factor | vLLM | TensorRT-LLM |
|--------|------|-------------|
| **Setup complexity** | Simple (pip + serve) | Complex (CUDA/TensorRT build) |
| **Model support** | Broad (any HF model) | Good (100+ pre-built) |
| **Throughput** | Very good (24x transformers) | Best-in-class (100x transformers) |
| **Latency** | Low (PagedAttention) | Lowest (pre-compiled kernels) |
| **Hardware** | NVIDIA + AMD + Intel | NVIDIA only (A100/H100/GB200) |
| **Quantization** | AWQ, GPTQ, FP8 (runtime) | FP8, INT4, FP4 (compile-time) |
| **Multi-GPU** | Tensor parallelism | TP + PP + Expert parallelism |
| **In-flight batching** | Continuous batching | In-flight dynamic batching |
| **Speculative decode** | Built-in | Built-in |
| **LoRA serving** | Via LoRA adapter plugin | Native LoRA serving |
| **Use case** | General production serving | Maximum performance, NVIDIA-only |

## When to Choose TensorRT-LLM Over vLLM

1. **You need maximum throughput**: 24,000+ tokens/sec on H100 for Llama 3-8B
2. **NVIDIA hardware only** (A100/H100/GB200) — no AMD support
3. **FP8/INT4/FP4 quantization** at compile time for maximum speedup
4. **Multi-node scaling** with pipeline parallelism
5. **Your model is in the supported list** (check NVIDIA's compatibility list)

## Migration from vLLM to TensorRT-LLM

If you're already running vLLM and need more performance:

```python
# vLLM style (simpler)
from vllm import LLM, SamplingParams
llm = LLM(model="meta-llama/Llama-3-8B")

# TensorRT-LLM style (pre-compilation required)
# 1. Build engine (one-time, GPU-specific):
# trtllm-build --model meta-llama/Meta-Llama-3-8B \
#   --output_dir ./engines/llama3-8b/tp4/kvcache_dtype_fp16

# 2. Load compiled engine:
from tensorrt_llm import LLM
llm = LLM(model="./engines/llama3-8b")
```

**Key differences:**
- TensorRT-LLM requires **compile-time optimization** per GPU architecture
- vLLM is **runtime-compiled** (works on any GPU out of the box)
- TensorRT-LLM's first inference is slower (compilation overhead)
- After compilation, TensorRT-LLM delivers ~2-3x more throughput than vLLM

## Resources
- NVIDIA TensorRT-LLM: https://github.com/NVIDIA/TensorRT-LLM