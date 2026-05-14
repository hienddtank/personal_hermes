---
name: embedding-session-recall
description: Query the embedding engine for semantic session recall. Search past conversations by meaning, not keywords. Supports type filtering (user/assistant/tool) and time filtering (short/long term).
---

# Embedding Session Recall

Search past conversation sessions using semantic embeddings. The engine stores 21,500+ chunks across 6 FAISS tables (user/assistant/tool × short/long term).

## When to Use

- User asks "what were we working on?" or "remember when we did X?"
- User references past work, projects, decisions, or experiments
- Keyword search (`session_search`) isn't finding what you need
- User wants semantic recall: "find stuff about embeddings" instead of "embedding"

## ⚠ Dependency Requirement

The embedding engine scripts require `numpy`, `faiss-cpu`, `fastembed`, and `PyMuPDF` in the **venv** at `/opt/venv/bin/python3`. After a sandbox reset, reinstall via:

```bash
/opt/venv/bin/python3 -m ensurepip 2>/dev/null || true
/opt/venv/bin/python3 -m pip install numpy faiss-cpu fastembed PyMuPDF
```

**Do NOT use system `pip3`** — it installs to a different location invisible to the venv. See `references/venv-dependency-setup.md` for details.

## Quick Reference

```bash
# Search all tables (default)
python3 /workspace/embedding_engine/query.py "topic"

# Filter by type
python3 /workspace/embedding_engine/query.py "topic" --type user        # Only user messages
python3 /workspace/embedding_engine/query.py "topic" --type assistant   # Only my responses
python3 /workspace/embedding_engine/query.py "topic" --type tool        # Only tool outputs

# Filter by time
python3 /workspace/embedding_engine/query.py "topic" --time short  # Last 7 days
python3 /workspace/embedding_engine/query.py "topic" --time long   # Older than 7 days

# Combine filters
python3 /workspace/embedding_engine/query.py "topic" --type user --time short -n 10
```

## Programmatic Usage (Recommended)

Import and call directly in Python scripts for better control:

```python
import sys, os
sys.path.insert(0, "/workspace/embedding_engine")
from query import load_tables, search, clean_content

# Load all tables
meta, indices = load_tables()

# Search
results = search("calculus exercises", meta, indices, k=5)

# Use results
for r in results:
    print(f"[{r['type']}] score={r['score']}: {clean_content(r['content'])[:200]}")
```

## Result Format

Each result contains:
- `type`: "user", "assistant", or "tool"
- `table`: e.g., "short_user" (becomes "short. user" in display)
- `score`: raw cosine similarity (0-1)
- `weighted_score`: score × type weight (user=1.0, assistant=0.9, tool=0.7)
- `content`: the embedded text chunk
- `session`: session ID (e.g., "20260504_072428_3051f817")
- `date`: session date
- `chunk_index`: position within the session

## Scoring

Results are sorted by **weighted score** (weighted_score = score × type_weight):

| Type | Weight | Rationale |
|------|--------|-----------|
| user | 1.0 | Highest priority — decisions, preferences, goals |
| assistant | 0.9 | Responses, explanations, conclusions |
| tool | 0.7 | Lowest — often noisy (system prompts, raw data) |

## Tips

- **For "what were we doing?"**: Search with `--type user` to surface the user's actual questions/goals
- **For "how did we fix X?"**: Search with `--type assistant` to find solutions
- **For "what tools/scripts did we use?"**: Search with `--type tool` to find commands and outputs
- **Combine with session_search**: Use embedding recall for semantic matches, keyword search for exact terms
- **Vague queries work better than keyword search**: "things about vectors and memory" finds relevant sessions that keyword search might miss

## Engine State

```
Location: /workspace/embedding_engine/
Tables: 6 (short/long × user/assistant/tool) + 1 document table
Total chunks: ~25,050 (207+ sessions)
Model: BAAI/bge-small-en-v1.5 (384-dim, fastembed backend)
Sessions dir: /host/d/mkt/python/hermes/hermes-home/sessions/*.jsonl
Python: /opt/venv/bin/python3 (ISOLATED venv — system pip does NOT reach it)
Daily ingest: Cronjob — daily_embed.py at 11 PM UTC / 4 AM local
  → delegates to ingest_with_checkpoints.py
  → Checkpoint: ingestion_checkpoint.json (resumable)
  → Progress log: ingestion_breadcrumbs.log
```

## Daily Ingestion Pipeline

Run `daily_embed.py` to ingest new sessions and PDFs. **Must use the venv Python** — system pip installs to a different location:

```bash
# Install dependencies (first run or after sandbox reset)
/opt/venv/bin/python3 -m ensurepip 2>/dev/null
/opt/venv/bin/python3 -m pip install numpy faiss-cpu fastembed PyMuPDF

# Run the pipeline
/opt/venv/bin/python3 /workspace/embedding_engine/daily_embed.py
```

**Pipeline stages:**
1. **Session ingestion** — processes `.jsonl` session files older than 2 hours via `ingest_with_checkpoints.py` (resumable via `ingestion_checkpoint.json`)
2. **PDF ingestion** — scans `~/.hermes/pdf` and `/workspace/pdf` for new documents (currently no configured dirs exist)
3. **Timestamp save** — records last-run time for incremental processing

**Checkpoint files:**
- `ingestion_checkpoint.json` — tracks which sessions have been processed
- `ingestion_breadcrumbs.log` — detailed per-session progress log

## Troubleshooting

- **"No results"**: May sessions not ingested → run `python3 ingest_with_checkpoints.py --batch-size 20`
- **daily_embed.py finds no sessions**: It delegates to `ingest_with_checkpoints.py` which reads `.jsonl` files from `/host/d/mkt/python/hermes/hermes-home/sessions/`
- **Stale data**: Check `ingestion_checkpoint.json` — cleared files are skipped
- **`ModuleNotFoundError: No module named 'numpy'`** (or fastembed, faiss, PyMuPDF): The venv at `/opt/venv/` is isolated from system Python. System `pip3 install` does NOT reach the venv. Fix: use `/opt/venv/bin/python3 -m pip install <package>` instead. If pip itself is missing from the venv, run `/opt/venv/bin/python3 -m ensurepip` first.
