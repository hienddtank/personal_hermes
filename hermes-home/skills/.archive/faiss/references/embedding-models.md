# Lightweight Embedding Models for Short Text

When using FAISS with short text chunks (~250 chars), model choice matters more than at larger scales. Smaller, contrastive-trained models often outperform larger ones.

## Best Option: FastEmbed + AllMiniLM-L6-V2

**Install:** `pip install fastembed faiss-cpu numpy`

- **Speed:** 14.7ms per 1K tokens (fastest available)
- **Size:** ~23MB model file
- **Dimensions:** 384-dim output
- **Training:** Contrastive learning — pushes similar together, dissimilar apart
- **Negative filtering:** Near-zero scores (~0.10) for irrelevant matches
- **Chunk performance:** Specifically excels on small chunks (<500 chars) because it doesn't need long context windows
- **Under the hood:** ONNX Runtime, no PyTorch needed

```python
from fastembed import TextEmbedding
import faiss
import numpy as np

model = TextEmbedding(model_name="Xenova/all-MiniLM-L6-v2")
docs = ["chunk1", "chunk2", ...]
embeddings = list(model.embed(docs))

# FAISS index (inner product on normalized vectors = cosine)
d = 384
index = faiss.IndexFlatIP(d)
index.add(np.array(embeddings, dtype='float32'))
```

## Alternative: BGE-small-en-v1.5

- **Speed:** ~20% slower than MiniLM (~18ms/token)
- **Size:** ~134MB model file
- **Dimensions:** 384-dim
- **Strengths:** Better semantic understanding, supports "query"/"passage" prefixes natively
- **Use when:** Chunks sometimes exceed 500 chars or deeper semantics needed

## Model Comparison (from benchmark data)

| Model | Dim | Size | Speed | Best For |
|-------|-----|------|-------|----------|
| AllMiniLM-L6-V2 | 384 | 23MB | ~15ms | Short chunks, speed-critical |
| AllMiniLM-L12-V2 | 384 | 78MB | ~20ms | Slightly longer chunks (up to 500 chars) |
| BGE-small-en-v1.5 | 384 | 134MB | ~18ms | General purpose, query/passage prefixes |
| Qwen3-Embedding-0.6B | 1024 | ~1.2GB | ~50ms+ | Large chunks (>3000 words), deep semantics |

## Key Insights

1. **Smaller models often outperform for short text** — they don't waste capacity on context the text doesn't need
2. **Contrastive training > general pretraining** for retrieval — MiniLM was specifically trained on sentence similarity
3. **For ~250 char chunks**, AllMiniLM-L6-V2 gives the best speed/accuracy ratio with minimal memory footprint
4. **Normalize vectors** before FAISS IP index to get cosine similarity
