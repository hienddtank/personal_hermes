---
name: vision-models
description: Vision AI models — image understanding, segmentation, generation, and multimodal vision-language. Covers CLIP (embeddings/classification), LLaVA (vision chat), SAM (segmentation), and Stable Diffusion (image generation). Use for image search, visual QA, object masking, or text-to-image workflows.
category: mlops
---

# Vision AI Models

## Decision Tree

```
Working with images?
├── Need image-text embeddings or zero-shot classification
│   └── CLIP — contrastive image-text model
├── Need conversational image analysis / visual QA
│   └── LLaVA — vision-language chatbot
├── Need to segment/mask objects in images
│   └── SAM (Segment Anything) — zero-shot segmentation
└── Need to generate images from text
    └── Stable Diffusion — text-to-image generation
```

## Quick Comparison

| Model | Task | Input | Output | Stars | License |
|-------|------|-------|--------|-------|---------|
| **CLIP** | Embeddings, classification | Image + text | Similarity scores | 25k+ | MIT |
| **LLaVA** | Visual QA, chat | Image + text prompt | Natural language | 23k+ | Apache 2.0 |
| **SAM** | Segmentation | Image + points/boxes | Binary masks | 47k+ | Apache 2.0 |
| **SD** | Image generation | Text prompt | Generated images | 8k+ (diffusers) | Various |

## When to Combine Models

- **CLIP + Vector DB**: Semantic image search
- **SAM + CLIP**: Text-prompted segmentation (GroundingDINO bridge)
- **LLaVA + SAM**: "Describe what this masked region contains"
- **SD + CLIP**: Image quality filtering / similarity search

## Quick Starts

### CLIP — Image-Text Embeddings
```python
import clip
import torch
from PIL import Image

model, preprocess = clip.load("ViT-B/32")
image = preprocess(Image.open("photo.jpg")).unsqueeze(0)
text = clip.tokenize(["a dog", "a cat", "a bird"])

with torch.no_grad():
    logits_per_image, _ = model(image, text)
    probs = logits_per_image.softmax(dim=-1).cpu().numpy()

for label, prob in zip(["dog", "cat", "bird"], probs[0]):
    print(f"{label}: {prob:.2%}")
```

### LLaVA — Vision-Language Chat
```python
from llava.model.builder import load_pretrained_model
from llava.mm_utils import get_model_name_from_path, process_images
from llava.constants import DEFAULT_IMAGE_TOKEN
from llava.conversation import conv_templates
from PIL import Image
import torch

tokenizer, model, image_processor, context_len = load_pretrained_model(
    model_path="liuhaotian/llava-v1.5-7b", model_base=None,
    model_name=get_model_name_from_path("liuhaotian/llava-v1.5-7b")
)

image = Image.open("image.jpg")
image_tensor = process_images([image], image_processor, model.config)
image_tensor = image_tensor.to(model.device, dtype=torch.float16)

conv = conv_templates["llava_v1"].copy()
conv.append_message(conv.roles[0], DEFAULT_IMAGE_TOKEN + "\nWhat is in this image?")
conv.append_message(conv.roles[1], None)
prompt = conv.get_prompt()
# ... generate response
```

### SAM — Zero-Shot Segmentation
```python
import numpy as np
from segment_anything import sam_model_registry, SamPredictor

sam = sam_model_registry["vit_h"](checkpoint="sam_vit_h_4b8939.pth")
sam.to(device="cuda")
predictor = SamPredictor(sam)

image = cv2.cvtColor(cv2.imread("image.jpg"), cv2.COLOR_BGR2RGB)
predictor.set_image(image)

input_point = np.array([[500, 375]])
input_label = np.array([1])  # 1=foreground, 0=background
masks, scores, _ = predictor.predict(
    point_coords=input_point, point_labels=input_label, multimask_output=True
)
best_mask = masks[np.argmax(scores)]
```

### Stable Diffusion — Text-to-Image
```python
from diffusers import DiffusionPipeline
import torch

pipe = DiffusionPipeline.from_pretrained(
    "stable-diffusion-v1-5/stable-diffusion-v1-5", torch_dtype=torch.float16
).to("cuda")

image = pipe(
    "A serene mountain landscape at sunset, highly detailed",
    num_inference_steps=50, guidance_scale=7.5
).images[0]
image.save("output.png")
```

## Common Workflows

### Image Search Pipeline (CLIP + Vector DB)
1. Encode all images with CLIP → embeddings
2. Store embeddings in Chroma/FAISS/Qdrant
3. Search with text query → encode query → nearest neighbors

### Interactive Annotation (SAM)
1. Load image into predictor (compute embeddings once)
2. User clicks points → segment object
3. Refine with additional points or box prompts
4. Export masks as PNGs or COCO RLE

### Visual QA Bot (LLaVA)
1. Load model + image processor
2. Accept image + question
3. Generate natural language response
4. Maintain conversation history for multi-turn

### Image Generation Pipeline (SD)
1. Load pipeline (SD/SDXL/Flux)
2. Apply optional ControlNet/LoRA
3. Generate with prompt + parameters
4. Optional: upscale, refine, batch

## GPU Requirements

| Model | Min VRAM | Recommended |
|-------|----------|-------------|
| CLIP (ViT-B/32) | 1 GB | 2 GB |
| CLIP (ViT-L/14) | 2 GB | 4 GB |
| LLaVA 7B | 4 GB (4-bit) | 14 GB |
| LLaVA 34B | 18 GB (4-bit) | 70 GB |
| SAM (ViT-B) | 2 GB | 4 GB |
| SAM (ViT-H) | 4 GB | 8 GB |
| SD 1.5 | 4 GB | 8 GB |
| SDXL | 8 GB | 16 GB |

## Best Practices
1. **Cache embeddings** — CLIP/SAM image encodings are expensive; compute once
2. **Use appropriate model size** — Start small, scale up for quality
3. **Batch processing** — Process multiple images/texts together
4. **GPU memory** — Enable CPU offloading, attention slicing, xFormers
5. **Normalize embeddings** — Required for cosine similarity (CLIP)
6. **Use fp16** — Half precision saves memory with minimal quality loss

## Resources
- CLIP: https://github.com/openai/CLIP (⭐25k+)
- LLaVA: https://github.com/haotian-liu/LLaVA (⭐23k+)
- SAM: https://github.com/facebookresearch/segment-anything (⭐47k+)
- Stable Diffusion: https://github.com/huggingface/diffusers
