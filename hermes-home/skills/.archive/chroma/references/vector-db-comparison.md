# Vector Database Selection Guide

When you need a vector database, use this decision tree to choose the right tool:

## Quick Decision Tree

| Need | Recommended Tool |
|------|------------------|
| Local development, prototyping, self-hosted | **Chroma** |
| Production RAG with managed infrastructure | **Pinecone** |
| Pure similarity search at billion-scale | **FAISS** |
| Metadata filtering + vector search (self-hosted) | Qdrant / Weaviate |

## When to use each

### Chroma — Best for: Local dev, prototyping, simple RAG
- Open-source, Apache 2.0
- Simple 4-function API (create, add, query, delete)
- Built-in sentence-transformer embeddings
- Persistent storage on disk
- Metadata filtering supported
- **Limitation**: Not designed for multi-user production

### Pinecone — Best for: Production RAG, managed infrastructure
- Fully managed SaaS, auto-scaling
- p95 latency <100ms with SLA
- Hybrid search (dense + sparse vectors)
- Namespaces for multi-tenant isolation
- Metadata filtering
- **Limitation**: Vendor lock-in, costs scale with usage

### FAISS — Best for: Pure speed, GPU acceleration, offline analysis
- Facebook AI, handles billions of vectors
- Multiple index types: Flat (exact), IVF (approximate), HNSW (best quality/speed), PQ (memory efficient)
- GPU acceleration (10-100× faster than CPU)
- **Limitation**: No metadata support, no built-in embeddings

### Comparison Summary

| Feature | Chroma | Pinecone | FAISS |
|---------|--------|----------|-------|
| Self-hosted | ✅ | ❌ | ✅ |
| Metadata filtering | ✅ | ✅ | ❌ |
| GPU acceleration | ❌ | ❌ | ✅ |
| Embedding generation | ✅ (built-in) | ❌ | ❌ |
| Multi-tenant namespaces | ❌ | ✅ | ❌ |
| Open source | ✅ Apache 2.0 | ❌ | ✅ MIT |
| Scale target | <1M vectors | Billions | Billions |
| Production-ready | Limited | Yes | Yes (with work) |

## Migration patterns

### Chroma → Pinecone (scaling up)
```python
# Chroma (source)
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("my_docs")

# Get all documents
results = collection.get(include=["documents", "metadatas", "embeddings"])

# → Pinecone (destination)
from pinecone import Pinecone, ServerlessSpec
pc = Pinecone(api_key="your-key")
index = pc.Index("my-index")
vectors = [{"id": id_, "values": emb, "metadata": meta}
           for id_, emb, meta in zip(results["ids"], results["embeddings"], results["metadatas"])]
index.upsert(vectors=vectors)
```

### FAISS → Chroma (adding metadata)
```python
# FAISS (source)
import faiss
index = faiss.read_index("large.index")
faiss_vectors = index.reconstruct(0, index.ntotal)

# → Chroma (destination)
import chromadb
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.create_collection("from_faiss")
docs = [f"Document {i}" for i in range(index.ntotal)]
collection.add(documents=docs, ids=[f"vec_{i}" for i in range(index.ntotal)])
```

## Resources
- Chroma: https://github.com/chroma-core/chroma (24K+ stars)
- Pinecone: https://www.pinecone.io
- FAISS: https://github.com/facebookresearch/faiss (31K+ stars)
