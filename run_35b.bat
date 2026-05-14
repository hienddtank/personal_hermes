@echo off
cd /d F:\AI\llama.cpp

set "MODEL=F:\AI\Lmstudio\unsloth\Qwen3.6-35B-A3B-GGUF\Qwen3.6-35B-A3B-UD-IQ4_XS.gguf"
set "MMPROJ=F:\AI\Lmstudio\unsloth\Qwen3.6-35B-A3B-GGUF\mmproj-F32.gguf"

build\bin\Release\llama-server.exe ^
  -m "%MODEL%" ^
  --mmproj "%MMPROJ%" ^
  --host 192.168.1.146 ^
  --port 1235 ^
  --device CUDA0,CUDA1 ^
  --split-mode layer ^
  --main-gpu 0 ^
  --n-gpu-layers 999 ^
  --tensor-split 20,12 ^
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
  --presence-penalty 1.5 ^
  --jinja ^
  --chat-template-kwargs "{\"preserve_thinking\": true}"

pause