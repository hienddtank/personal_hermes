@echo off
cd /d F:\AI\llama.cpp

:: ---- Qwen3.6 language model ----
set "MODEL=F:\AI\Lmstudio\unsloth\Qwen3.6-27B-GGUF\Qwen3.6-27B-Q4_K_M.gguf"
set "MMPROJ=F:\AI\Lmstudio\unsloth\Qwen3.6-27B-GGUF\mmproj-F32.gguf"

build\bin\Release\llama-server.exe ^
  -m "%MODEL%" ^
  --mmproj "%MMPROJ%" ^
  --no-mmproj-offload ^
  --host 192.168.1.146 ^
  --port 1235 ^
  --device CUDA0,CUDA1 ^
  --split-mode layer ^
  --main-gpu 0 ^
  --n-gpu-layers 999 ^
  --tensor-split 16,12 ^
  --ctx-size 131072 ^
  --parallel 1 ^
  --batch-size 8192 ^
  --ubatch-size 512 ^
  --cache-type-k q8_0 ^
  --cache-type-v q8_0 ^
  --flash-attn on ^
  --temp 1.0 ^
  --top-p 0.95 ^
  --top-k 20 ^
  --spec-type ngram-mod ^
  --spec-ngram-size-n 24 ^
  --draft-min 48 ^
  --draft-max 64 ^
  --presence-penalty 1.5 ^
  --jinja ^
  --chat-template-kwargs "{\"preserve_thinking\": true}"

pause