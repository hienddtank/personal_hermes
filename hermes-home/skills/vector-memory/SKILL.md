---
name: vector-memory
description: Build lightweight two-table embedding systems for agent memory using FastEmbed + FAISS. Semantic search across past conversations, memories, and project state without external services or heavy dependencies. Uses ONNX Runtime (no PyTorch), ~23MB model, 384-dim vectors stored persistently in binary .index files.
---

# Vector Memory Engine

Build lightweight two-table embedding systems for agent memory using FastEmbed + FAISS. Used when you need semantic search across past conversations, saved memories, and current project state without external services or heavy dependencies.

## When to Use
- User wants to store/retrieve knowledge from conversation history via semantic search
- Need persistent vector storage that survives container restarts
- Building RAG for agent memory (personal notes, study materials, past decisions)
- Lightweight alternative to ChromaDB/Pinecone for single-agent setups

## Architecture: Two Approaches

### Simple: Two-Table (mixed content types)

```
┌─────────────────────┐    ┌──────────────────────┐
│  Table 1: Long-Term │    │  Table 2: Short-Term │
│  (All Messages)     │    │  (All Messages)      │
└──────────┬──────────┘    └──────────┬───────────┘
           │                          │
           ▼                          ▼
    ┌──────────┐               ┌──────────┐
    │ FAISS DB │               │ FAISS DB │
    └────┬─────┘               └────┬─────┘
```

### Dynamic: Six-Table (separated by content type) ⭐ RECOMMENDED

Separating content types enables weighted queries — surface user decisions without tool output noise.

```
long_user  long_assistant  long_tool
short_user short_assistant short_tool
```

- **user**: Messages from the user (decisions, preferences, questions, goals)
- **assistant**: My responses + reasoning_content (answers, conclusions, explanations)
- **tool**: Tool outputs (terminal results, web search results, file read content, API responses)
- **long-term** (>7 days): Past sessions, completed work, historical decisions
- **short-term** (≤7 days): Active context, current projects, recent tasks

Query weights: `user` > `assistant` > `tool` by default. Filter by `--type user|assistant|tool|all`.

### When to use which
- **Simple (2-table)**: Quick setup, small datasets (<5K embeddings), no need to distinguish content sources
- **Dynamic (6-table)**: Wanting weighted search by source type, filtering noise from tool outputs, multi-user scenarios

## Steps

1. **Install dependencies**
   ```bash
   pip install fastembed faiss-cpu
   ```

2. **Create embedding model** — use FastEmbed (ONNX-based, no PyTorch):
   ```python
   from fastembed import TextEmbedding
   model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
   ```
   ⚠️ Model name is `sentence-transformers/all-MiniLM-L6-v2`, NOT `Xenova/all-MiniLM-L6-v2` (the latter throws ValueError).

3. **Initialize two FAISS indices** (inner product on normalized vectors = cosine similarity):
   ```python
   import faiss
   DIMENSION = 384
   long_index = faiss.IndexFlatIP(DIMENSION)
   short_index = faiss.IndexFlatIP(DIMENSION)
   ```

4. **Embed and store** — normalize embeddings, add to FAISS:
   ```python
   embedding = model.embed([text])  # list of numpy arrays
   norm = embedding / np.linalg.norm(embedding)
   index.add(norm.reshape(1, -1))
   ```

5. **Persist metadata** separately (FAISS stores vectors but not content):
   ```python
   meta = {"entries": [{"id": hash_id, "content": text[:500], ...}]}
   # Save as JSON alongside .index files
   ```

6. **Query**: embed query → normalize → `index.search(query_vec, k)` → join with metadata for content.

## Storage Layout

```
embedding_engine/
├── engine.py            # Main engine class (add/search/clear)
├── long_term.index      # FAISS binary — 384-dim vectors for past conversations
├── short_term.index     # FAISS binary — 384-dim vectors for current state
├── meta_long.json       # Entry metadata (content, IDs, timestamps)
└── meta_short.json      # Entry metadata
```

## Model Selection Guide

For ~250-character chunks: **`sentence-transformers/all-MiniLM-L6-v2`** — fastest (~15ms), excellent negative filtering, 384-dim.

See `references/fastembed-models.md` for full comparison table.

### Why MiniLM for short text
- Contrastive-trained: pushes similar things together, dissimilar apart
- Near-zero scores (~0.10) for irrelevant matches — exceptional at rejecting non-matches
- 512 token max truncation — sufficient for most message content
- ~23MB model size + ONNX runtime = minimal overhead
- Benchmarked: outperforms larger models on small-chunk retrieval tasks

## Pitfalls

### Dependencies not pre-installed
The container does NOT ship with required packages. After container rebuild or first run, install:
```bash
pip install numpy faiss-cpu fastembed pymupdf
```
Missing any of these causes immediate crash: `numpy` (engine.py), `faiss-cpu` (FAISS), `fastembed` (embedding model), `pymupdf`/`fitz` (PDF ingestion via `import fitz`).

### Corrupt meta_long.json recovery
The meta JSON file can get truncated (incomplete last entry), causing `JSONDecodeError: Expecting ',' delimiter`. This happens when a write is interrupted mid-entry. Recovery: run the brace-balanced parser that skips corrupted entries — see `references/meta-recovery.md` for the full procedure. Quick inline fix:

```python
import json, re
with open('meta_long.json') as f: raw = f.read()
# ... (brace-balanced parser — see references/meta-recovery.md)
```

The typical symptom: engine.py line 67 `json.load(f)` throws, pipeline fails at `EmbeddingEngine()` init.

- **Empty table crash**: Calling `index.search()` on a FAISS index with 0 vectors throws `AssertionError: k > 0`. Always check `index.ntotal == 0` before searching — skip empty tables gracefully.
- **Schema migration corrupts indexes**: When changing architecture (e.g., 2-table → 6-table), OLD `.index` and `meta_*.json` files cause FAISS read errors (`read error ... != ...`). Delete all existing `.index` + `meta_*.json` files before building new tables.
- **Tool output contamination**: Tool outputs (terminal, web_search, file reads) contain system prompts, code snippets, raw data dumps, and query result text that dominate top search results. A vague query like "how do I fix errors" returns Python tracebacks instead of actual advice. **Mitigation**: filter tool chunks that start with system prompt patterns ("You are Hermes Agent"), strip code blocks before embedding, or lower tool table weight in scoring. See `references/query-performance.md`.
- FastEmbed model names differ from HuggingFace IDs — always check with `TextEmbedding.list_supported_models()`. Model name is `sentence-transformers/all-MiniLM-L6-v2`, NOT `Xenova/all-MiniLM-L6-v2`.
- FAISS `IndexFlatIP` requires normalized vectors for cosine similarity (l2 norm = 1)
- Each session's data is hashed by content MD5 to prevent duplicates
- Metadata must be saved separately — FAISS only stores raw vectors, not the original text
- For large datasets (>10K vectors), switch from `IndexFlatIP` to `IndexIVFFlat` for faster search
- **Ingest ALL content types** (user, assistant reasoning + response, tool outputs) — user wants full conversation indexing, not just summaries
- **Analyze session files BEFORE planning ingestion** — JSONL structure varies (session_meta first line optional), request_dump JSONs are HTTP logs to skip
- See `references/session-ingestion.md` for Hermes Agent-specific session file formats and ingestion patterns.
- See `references/meta-recovery.md` for recovering corrupted meta JSON files from interrupted writes.

## Debugging Pitfalls: query.py / CLI

### `global model` scoping error
In Python, `global model` must come at the **top** of the function body, BEFORE any reference to `model`. If you write `if model is None: global model`, Python throws `SyntaxError: name 'model' is referenced before declaration`. Fix: declare `global model` first, then check and initialize.

### Regex escaping in clean_content
Using `re.sub()` with complex escape sequences (JSON backslash escapes like `\\\"`) causes regex parse errors (`bad escape (end of pattern)`). For simple string replacements, use `.replace()` — no regex involved, no escaping gymnastics. Replace `'\\\\\"', '"'` patterns with `text.replace('\\\\"', '"')`.

### Table argument passing
When refactoring function signatures that load FAISS tables, ensure the calling code passes parameters in the correct format. If a function expects `(meta_store, indices)` as separate dicts, the call site must not wrap them in an extra dict layer (`{tables: {...}}`). The `load_tables()` and `search()` functions are tightly coupled — changes to one require corresponding changes at the call site.

### No sklearn or scipy — use numpy-only PCA and correlation
The FastEmbed container does NOT include sklearn or scipy. For any analysis requiring PCA, correlation, or clustering, implement with raw numpy:

**PCA via eigendecomposition**:
```python
def pca_fit(X, n_components):
    X_centered = X - X.mean(axis=0)
    cov_matrix = np.cov(X_centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    idx = np.argsort(eigenvalues)[::-1][:n_components]
    return X_centered @ eigenvectors[:, idx], eigenvalues[idx]
```

**Pearson correlation (manual)**:
```python
def pearson_r(a, b):
    mean_a, mean_b = np.mean(a), np.mean(b)
    num = np.sum((a - mean_a) * (b - mean_b))
    den = np.sqrt(np.sum((a - mean_a)**2) * np.sum((b - mean_b)**2))
    return num / den if den != 0 else 0.0
```

For axis derivation and semantic direction analysis, see the `embedding-axis-analysis` skill.

## Chunk Size Comparison (Empirical Results)

| Config | Chunks/Session | Avg Score (Vague) | Avg Score (Concrete) | Notes |
|--------|---------------|-------------------|---------------------|-------|
| 250 chars, 50 overlap | ~523 | 0.18–0.49 | 0.60+ | More entries, slightly noisier |
| 500 chars, 100 overlap | ~98 | 0.18–0.49 | 0.60+ | Fewer entries, same quality |

**Finding**: Chunk size makes little difference for query performance. The bottleneck is **content type**, not chunk granularity. Tool outputs dominate regardless of chunk size because they contain system instructions and raw data that match vague queries superficially. Use whichever aligns with your storage/latency tradeoff — larger chunks are more efficient but don't improve search quality.

## Querying an Existing Engine

Once your engine is populated, search it via the CLI:

```bash
cd /workspace/embedding_engine
python3 query.py "your query here"                    # Search all tables
python3 query.py "calculus" --type user               # Only user messages
python3 query.py "error fix" --type tool              # Only tool outputs
python3 query.py "docker restart" --time short        # Only ≤7 day old
python3 query.py "study plan" -n 10                  # Top 10 results
```

**Type weights** (applied automatically): user 1.0, assistant 0.9, tool 0.7 — surfaces decisions over noise.

To call from within a conversation (e.g. as an agent), run via terminal tool:
```
terminal: cd /workspace/embedding_engine && python3 query.py "session recall query" --type user -n 5
```

## Extended Patterns: Document / PDF Ingestion

When you need to embed external documents (PDFs, knowledge base, reference materials) alongside conversation history, add a **third FAISS table** (`documents`). See `references/document-ingestion.md` for the full pattern including paragraph-aware chunking, section detection, auto-classification, and reverse lookup context expansion.

See also:
- `references/fastembed-models.md` — Model comparison table
- `templates/engine-boilerplate.py` — Starter engine code (2-table)
- `references/query-performance.md` — Query patterns and known performance characteristics
- `references/type-filtered-search.md` — Six-table pattern with type filtering and weighted scoring
- `references/document-ingestion.md` — Document/PDF ingestion: chunking, classification, metadata schema
- `templates/ingest_pdfs_template.py` — Starter script for PDF ingestion (paragraph-aware chunking + auto-tagging)
- `references/daily-embed-orchestrator.md` — Daily cron orchestrator pattern for incremental session + PDF ingestion
- **`embedding-axis-analysis`** (separate skill) — Derive semantic axes from embeddings: offensiveness, sentiment, formality, gender debiasing direction
