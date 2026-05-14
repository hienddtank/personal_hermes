---
name: vector-databases
description: Vector databases for RAG, semantic search, and similarity retrieval. Covers Chroma (local/open-source), FAISS (billion-scale C++), Pinecone (managed SaaS), and Qdrant (Rust, production). Use for embedding storage, nearest-neighbor search, metadata filtering, and retrieval pipelines.
category: mlops
---

# Vector Databases — RAG & Semantic Search

## Decision Tree

```
Need vector search?
├── Prototyping / local dev / notebooks
│   └── Chroma (embedded, zero config)
├── Pure similarity search, no metadata
│   └── FAISS (C++, billion-scale, GPU)
├── Managed, auto-scaling, zero ops
│   └── Pinecone (serverless SaaS)
└── Self-hosted production, rich filtering
    └── Qdrant (Rust, distributed, payload filters)
```

## Quick Comparison

| Feature | Chroma | FAISS | Pinecone | Qdrant |
|---------|--------|-------|----------|--------|
| **Type** | Embedded DB | C++ Library | Managed SaaS | Self-hosted / Cloud |
| **Install** | `pip install chromadb` | `pip install faiss-cpu` | `pip install pinecone-client` | `pip install qdrant-client` + Docker |
| **Metadata filtering** | ✅ | ❌ | ✅ | ✅ (rich) |
| **GPU** | ❌ | ✅ | ✅ (managed) | ❌ |
| **Scale** | <10M vectors | Billions | Billions | Millions |
| **Persistence** | File-based | `.index` files | Cloud | Disk / Cloud |
| **LangChain** | ✅ | ✅ | ✅ | ✅ |
| **LlamaIndex** | ✅ | ✅ | ✅ | ✅ |
| **Cost** | Free | Free | Free tier + paid | Free / Cloud |
| **Best for** | Local dev, RAG prototyping | Batch processing, research | Production RAG, serverless | Production, self-hosted, filtering |

## Common Patterns (All Products Share)

### Embedding Pipeline
```
Text → Embedding Model → Vector (e.g., 384/768/1536 dims) → Store in Vector DB
Query → Same Embedding Model → Query Vector → ANN Search → Top-K Results
```

### Popular Embedding Models
| Model | Dimensions | Notes |
|-------|-----------|-------|
| `all-MiniLM-L6-v2` | 384 | Fast, lightweight (sentence-transformers) |
| `text-embedding-3-small` | 1536 | OpenAI, good quality |
| `text-embedding-3-large` | 3072 | OpenAI, best quality |
| `bge-small-en-v1.5` | 384 | BGE, strong multilingual |
| `nomic-embed-text` | 768 | Open source, good performance |

### Typical RAG Setup (pattern applies to all)
1. Split documents into chunks (200-1000 tokens)
2. Embed each chunk with consistent model
3. Store vectors + metadata (source, page, timestamp)
4. Query: embed question → search → return top-K with metadata
5. Pass retrieved context to LLM

### Distance Metrics
| Metric | Use Case |
|--------|----------|
| Cosine | Text embeddings (most common) |
| L2 / Euclidean | Spatial data, raw features |
| Inner Product | Normalized vectors = cosine, recommendations |

## Product Quick-Starts

### Chroma — Local & Embedded
```python
import chromadb
client = chromadb.Client()  # or PersistentClient(path="...")
col = client.create_collection("docs")
col.add(documents=["text"], metadatas=[{"source": "a"}], ids=["1"])
results = col.query(query_texts=["query"], n_results=3)
```
See `references/chroma.md` for full API (embedding functions, LangChain/LlamaIndex, server mode).

### FAISS — Billion-Scale C++
```python
import faiss, numpy as np
d = 384  # dimensions
index = faiss.IndexFlatL2(d)  # or IndexHNSWFlat, IndexIVFFlat
index.add(vectors)  # numpy array (N, d)
distances, indices = index.search(query, k=5)
faiss.write_index(index, "large.index")  # persistence
```
Index types: `Flat` (exact), `IVF` (fast, needs training), `HNSW` (fastest, high recall), `PQ` (memory-efficient).
See `references/faiss.md` for index types, GPU, and LangChain integration.

### Pinecone — Managed Serverless
```python
from pinecone import Pinecone, ServerlessSpec
pc = Pinecone(api_key="...")
pc.create_index(name="idx", dimension=1536, metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1"))
index = pc.Index("idx")
index.upsert(vectors=[{"id": "1", "values": [...], "metadata": {...}}])
results = index.query(vector=[...], top_k=5, include_metadata=True)
```
See `references/pinecone.md` for namespaces, hybrid search (dense+sparse), and pricing.

### Qdrant — Rust, Production, Filtering
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
client = QdrantClient(host="localhost", port=6333)
client.create_collection("docs", vectors_config=VectorParams(size=384, distance=Distance.COSINE))
client.upsert("docs", points=[PointStruct(id=1, vector=[...], payload={...})])
results = client.search("docs", query_vector=[...], limit=10)
```
See `references/qdrant.md` for payload filtering, quantization, multi-vector, and production tuning.

## Best Practices (Universal)

1. **Batch operations** — Insert/search in batches for throughput
2. **Add metadata** — Enable filtering and traceability
3. **Consistent embedding model** — Use same model for indexing and querying
4. **Choose right dimensions** — Match your embedding model's output
5. **Monitor collection size** — Scale or shard as needed
6. **Test recall** — Compare ANN results vs brute force on sample data
7. **Payload indexing** — Index frequently-filtered fields (Qdrant)
8. **Quantize** — Enable for large collections to save memory

## Resources
- Chroma: https://docs.trychroma.com (⭐24k+)
- FAISS: https://github.com/facebookresearch/faiss (⭐31k+)
- Pinecone: https://docs.pinecone.io
- Qdrant: https://qdrant.tech/documentation/ (⭐22k+)
