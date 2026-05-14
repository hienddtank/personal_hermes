FROM python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:${PATH}" \
    NVIDIA_LIB_DIRS="/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib:/usr/local/lib/python3.11/site-packages/nvidia/cufft/lib:/usr/local/lib/python3.11/site-packages/nvidia/curand/lib:/usr/local/lib/python3.11/site-packages/nvidia/cusolver/lib:/usr/local/lib/python3.11/site-packages/nvidia/cusparse/lib:/usr/local/lib/python3.11/site-packages/nvidia/nccl/lib:/usr/local/lib/python3.11/site-packages/nvidia/nvjitlink/lib:/usr/local/lib/python3.11/site-packages/nvidia/cuda_nvrtc/lib:/usr/local/lib/python3.11/site-packages/nvidia/cufile/lib:/usr/local/lib/python3.11/site-packages/nvidia/cuda_cupti/lib:/usr/local/lib/python3.11/site-packages/nvidia/cusparselt/lib:/usr/local/lib/python3.11/site-packages/nvidia/nvtx/lib" \
    LD_LIBRARY_PATH="${NVIDIA_LIB_DIRS}:/usr/local/cuda/compat/lib:/usr/local/cuda/compat/lib_real:/usr/local/cuda/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    curl \
    ffmpeg \
    git \
    ripgrep \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Install NVIDIA CUDA runtime for proper lib symlinks
RUN curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/cuda-keyring_1.1-1_all.deb \
    -o /tmp/cuda-keyring.deb \
    && dpkg -i /tmp/cuda-keyring.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends cuda-runtime-12-8 \
    && rm -f /tmp/cuda-keyring.deb \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

RUN git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /opt/hermes-agent \
    && cd /opt/hermes-agent \
    && uv venv /opt/venv --python 3.11 \
    && . /opt/venv/bin/activate \
    && uv pip install -e ".[cli,pty,cron,messaging]"

WORKDIR /workspace
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
