# Embedding Engine — Venv Dependency Setup

The embedding engine at `/workspace/embedding_engine/` runs via the venv Python at `/opt/venv/bin/python3`. System `pip3` installs packages to `/usr/local/lib/` which is **NOT** visible from the venv.

## Root Cause

```
python3 → /opt/venv/bin/python3  (Python 3.11 in a virtual env)
pip3    → /usr/local/bin/pip3     (system pip, installs to /usr/local/lib/)
```

These are separate Python environments. Packages installed via system pip are invisible to the venv's Python interpreter.

## Fix (first-run or after sandbox reset)

```bash
# Step 1: Ensure pip exists in venv (may already be present)
/opt/venv/bin/python3 -m ensurepip 2>/dev/null || true

# Step 2: Install required packages into the venv
/opt/venv/bin/python3 -m pip install numpy faiss-cpu fastembed PyMuPDF
```

## Required Dependencies

| Package | Used by | Purpose |
|---------|---------|---------|
| `numpy` | engine.py | Array operations, cosine similarity |
| `faiss-cpu` | engine.py | FAISS vector index (HNSW) |
| `fastembed` | engine.py | Embedding model inference (`BAAI/bge-small-en-v1.5`, 384-dim) |
| `PyMuPDF` | ingest_pdfs.py | PDF text extraction |

## Verification

```bash
/opt/venv/bin/python3 -c "import numpy, faiss, fastembed, fitz; print('all good')"
```
