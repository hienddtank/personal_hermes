---
name: gpu-cloud-providers
description: GPU cloud providers for ML training and inference — serverless (Modal) and dedicated instances (Lambda Labs). Use for on-demand GPU access, model deployment, batch processing, and distributed training.
---

# GPU Cloud Providers

GPU cloud platforms for ML workloads — serverless and dedicated instances.

## Provider Selection Guide

- **Serverless (auto-scaling)**: Modal — pay-per-second, Python-native, auto-scaling to 0
- **Dedicated instances (SSH)**: Lambda Labs — simple pricing, no egress fees, 1-Click Clusters
- **Multi-cloud orchestration**: SkyPilot
- **Cheapest spot instances**: RunPod, Vast.ai

## Modal — Serverless GPU Platform

Serverless GPUs with auto-scaling, Python-native deployment, sub-second cold starts.

### When to use Modal
- Auto-scaling ML APIs
- Pay-per-second GPU pricing (no idle costs)
- Batch processing with automatic scaling
- Scheduled/cron workloads
- Quick prototyping without infrastructure management

### Quick start

```bash
pip install modal
modal setup  # Auth via browser
```

```python
import modal

app = modal.App("my-app")
image = modal.Image.debian_slim().pip_install("torch", "transformers")

@app.cls(gpu="A10G", image=image)
class Model:
    @modal.enter()
    def load(self):
        self.model = load_my_model()  # Load once at container start

    @modal.method()
    def predict(self, x: str) -> str:
        return self.model(x)

@app.local_entrypoint()
def main():
    print(Model().predict.remote("Hello"))
```

### GPUs

| GPU | VRAM | Best For |
|-----|------|----------|
| T4 | 16GB | Budget inference |
| L4 | 24GB | Ada Lovelace arch |
| A10G | 24GB | Training/inference |
| L40S | 48GB | Best cost/perf |
| A100 | 40/80GB | Large models |
| H100 | 80GB | Fastest, FP8 |

### GPU specification patterns

```python
@app.function(gpu="A100")                    # Single GPU
@app.function(gpu="H100:4")                  # Multiple GPUs
@app.function(gpu=["H100", "A100", "L40S"])  # Fallbacks
@app.function(gpu="any")                     # Any available
```

### Key features
- **Container images**: Python-native, layer caching
- **Persistent volumes**: Model caching across runs
- **Web endpoints**: `@modal.fastapi_endpoint()`, `@modal.asgi_app()`
- **Dynamic batching**: `@modal.batched(max_batch_size=32, wait_ms=100)`
- **Secrets**: `modal secret create name KEY=value`
- **Scheduling**: `modal.Cron("0 0 * * *")`, `modal.Period(hours=1)`

### Performance tips
- Use `container_idle_timeout=300` to keep warm
- `@modal.enter()` for one-time model loading
- `allow_concurrent_inputs=10` for parallel requests

## Lambda Labs — Dedicated GPU Instances

Dedicated GPU instances with SSH access, persistent filesystems, and 1-Click Clusters.

### When to use Lambda Labs
- Long training jobs (hours to days)
- Full SSH access needed
- Simple pricing, no egress fees
- Persistent storage across sessions
- Multi-node clusters (16-512 GPUs)

### Quick start

```bash
# 1. Create account at https://lambda.ai
# 2. Add SSH key and API key
# 3. Launch instance via console or API

# Connect via SSH
ssh ubuntu@<INSTANCE-IP>

# Verify GPU and PyTorch
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

### GPUs

| GPU | VRAM | Price/GPU/hr |
|-----|------|-------------|
| B200 | 180 GB | $4.99 |
| H100 SXM | 80 GB | $2.99-3.29 |
| H100 PCIe | 80 GB | $2.49 |
| GH200 | 96 GB | $1.49 |
| A100 80GB | 80 GB | $1.79 |
| A100 40GB | 40 GB | $1.29 |
| A10 | 24 GB | $0.75 |
| A6000 | 48 GB | $0.80 |
| V100 | 16 GB | $0.55 |

### Lambda Stack (pre-installed)
- Ubuntu 22.04 LTS, NVIDIA drivers, CUDA 12.x
- PyTorch, TensorFlow, JAX
- NCCL, cuDNN, JupyterLab

### Persistent storage

```bash
# Filesystem mount point (persists across instances)
/lambda/nfs/<FILESYSTEM_NAME>/
  ├── datasets/
  ├── checkpoints/
  └── models/

# Local SSD (faster, ephemeral)
/home/ubuntu/working/
```

### Python API

```bash
pip install lambda-cloud-client
```

```python
import lambda_cloud_client
from lambda_cloud_client.models import LaunchInstanceRequest

config = lambda_cloud_client.Configuration(
    host="https://cloud.lambdalabs.com/api/v1",
    access_token=os.environ["LAMBDA_API_KEY"]
)

with lambda_cloud_client.ApiClient(config) as client:
    api = lambda_cloud_client.DefaultApi(client)

    # Launch instance
    request = LaunchInstanceRequest(
        region_name="us-west-1",
        instance_type_name="gpu_1x_h100_sxm5",
        ssh_key_names=["my-key"],
    )
    response = api.launch_instance(request)

    # List instances
    for inst in api.list_instances().data:
        print(f"{inst.name}: {inst.ip} ({inst.status})")
```

### 1-Click Clusters (16-512 GPUs)
- NVIDIA H100 or B200 with InfiniBand
- Slurm-based scheduling
- GPUDirect RDMA at 3200 Gb/s

```bash
srun --nodes=4 --ntasks-per-node=8 --gpus-per-node=8 \
  torchrun --nnodes=4 --nproc_per_node=8 train.py
```

### SSH tunneling

```bash
# Forward Jupyter + TensorBoard
ssh -L 8888:localhost:8888 -L 6006:localhost:6006 ubuntu@<IP>
```

## Common Workflows

### Workflow 1: Fine-tune LLM on Lambda Labs

```bash
# Launch 8x H100 with filesystem
ssh ubuntu@<IP>
pip install transformers accelerate peft

# Download model to persistent storage
python -c "from transformers import AutoModelForCausalLM; \
  AutoModelForCausalLM.from_pretrained('meta-llama/Llama-2-7b-hf').save_pretrained('/lambda/nfs/storage/models/llama')"

# Fine-tune
accelerate launch --num_processes 8 train.py \
  --model_path /lambda/nfs/storage/models/llama \
  --checkpoint_dir /lambda/nfs/storage/checkpoints
```

### Workflow 2: Deploy ML API on Modal

```python
import modal

app = modal.App("ml-api")

@app.function(gpu="L40S")
@modal.fastapi_endpoint(method="POST")
def predict(data: dict) -> dict:
    return {"result": model.predict(data["input"])}

# Deploy: modal deploy api.py
```

## Resources

- **Modal**: https://modal.com/docs
- **Lambda Labs**: https://cloud.lambda.ai
