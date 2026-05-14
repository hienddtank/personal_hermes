---
name: embedding-axis-probing
description: >
  Systematic analysis of embedding spaces to discover interpretable semantic dimensions, 
  cluster related axes, and project text onto discovered concepts. For probing model internals 
  via activation analysis, not training or fine-tuning.
---

# Embedding Axis Probing
Systematic analysis of embedding space to discover interpretable semantic dimensions and project text onto them.

## When to use
- User asks what "meaning" individual embedding dimensions encode
- Need to map out the conceptual axes of a model's embedding space
- Want to compare different wordings by projecting them onto discovered semantic dimensions
- User wants to understand "which directions" in an embedding correspond to real-world concepts

## Prerequisites
- `fastembed` with `all-MiniLM-L6-v2` (or similar) installed
- Access to any sentence-transformers / embedding model

## Step 1: Probe all dimensions
```python
import numpy as np
from fastembed import TextEmbedding

model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Build a diverse vocabulary spanning many semantic categories
vocab = ["happy", "sad", "angry", "big", "small", "freedom", "tyranny", ...]  # 50-200 words

all_embeds = np.array(list(model.embed(vocab))).astype(np.float64)
D = all_embeds.shape[1]  # e.g., 384

# For each dimension, find top-5 and bottom-5 activating words
for d in range(D):
    dim_vals = all_embeds[:, d]
    top5 = np.argsort(dim_vals)[-5:][::-1]
    bot5 = np.argsort(dim_vals)[:5]
```

## Step 2: Cluster dimensions by word overlap
Calculate Jaccard similarity between dimension pairs based on overlapping top-5 words. Group dimensions with similarity ≥ 0.25 into semantic clusters. Dimensions that activate the same words belong to the same conceptual axis.

## Step 3: Interpret clusters
For each cluster, extract the most frequent top/bottom words. Name the axis based on shared theme (e.g., "moral character", "political freedom", "natural vs artificial").

## Step 4: Build directional vectors
For a cluster with `high_words` and `low_words`:
```python
# Get embeddings for all defining words
word_embeds = np.array(list(model.embed(all_words)))
# Compute centroids
high_centroid = mean(embeddings of high_words)
low_centroid = mean(embeddings of low_words)
axis_direction = (high_centroid - low_centroid) / norm(high_centroid - low_centroid)
```

## Step 5: Project new text onto axes
```python
text_embed = np.array(list(model.embed([text])))[0]
text_embed = text_embed / norm(text_embed)
score_on_axis = dot(text_embed, axis_direction)
# Positive → toward high_words, Negative → toward low_words
```

## Visualization
- PCA scatter of all vocabulary words (2D projection) with cluster centroid annotations
- Bar charts for individual text projections onto multiple axes
- Side-by-side comparison tables for alternative wordings

## Pitfalls
- **Small vocabularies produce weak clusters**: Use 50-200+ words spanning diverse categories (emotions, physical properties, politics, morality, nature/artificial, cognitive states)
- **Normalization matters**: Always L2-normalize embeddings before dot-product projection
- **Dimensions are not independent**: Adjacent dimensions often share semantic meaning — clustering helps identify the true underlying axes vs. redundant slices
- **Word list bias**: The discovered axes reflect your vocabulary choices. Missing categories = missing axes
- **fastembed returns generators**: Use `np.array(list(model.embed(texts)))`, NOT `model.embed(texts)[0]`

## Output files
- `embedding-axes-overview.png` — PCA scatter with cluster annotations
- Per-dimension text output for detailed analysis

## Related
- `scripts/embedding-axes-analysis.py` — Full probing implementation
- `references/axis-catalog.md` — Example axis interpretations from prior runs