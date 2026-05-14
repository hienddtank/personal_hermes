# Daily Embedding Orchestrator Pattern

Run the embedding pipeline once per day (cron) to incrementally ingest new sessions and PDFs.

## Key Design Decisions

### Incremental processing — never re-embed everything
Track last successful run in `~/.hermes/system/last_embed_run.json`. Only process:
- **Sessions older than 2 hours** from current time (`SESSION_CUTOFF_HOURS = 2`) — skip active/current sessions that are still being written to
- **New PDFs** via idempotent dedup (content hash + source_path)

### Last-run tracking
```python
SYSTEM_DIR = Path(os.path.expanduser("~/.hermes/system"))
LAST_RUN_FILE = SYSTEM_DIR / "last_embed_run.json"
# Contains: {"timestamp": "...", "last_success": "..."}
```

### Cron schedule (Hanoi time, UTC+7)
- `0 23 * * *` = 6 AM Hanoi daily
- Deliver to `origin` (runs in current session context)
- Command: `cd /workspace/embedding_engine && python3 daily_embed.py`

## Pipeline Steps

1. **Embed new sessions** — scan `~/.hermes/system/sessions/`, load each session's JSON, extract assistant/user messages, call `engine.add_long_term()` with metadata (`entry_type`, `session_id`, `source_path`, `timestamp`)
2. **Ingest new PDFs** — scan configured dirs (`~/.hermes/pdf`, `/workspace/pdf`), call `ingest_pdfs()` which handles classification + chunking
3. **Save last-run timestamp**

## CLI Flags

- `--pdf-only`: Skip session processing, only ingest PDFs
- `--sessions-only`: Skip PDF ingestion, only process sessions
- Useful for debugging individual stages

## File Layout

```
/workspace/embedding_engine/
├── daily_embed.py        # Orchestrator (this file)
├── engine.py             # FAISS embedding engine
├── ingest_pdfs.py        # PDF ingestion logic
└── search_docs.py        # Standalone doc query module
```

## Pitfalls

- **Active session corruption**: Don't embed sessions currently being written to. Always apply the 2-hour cutoff to skip in-progress sessions.
- **Missing directories**: `~/.hermes/pdf` may not exist yet — handle gracefully with `os.path.isdir()` check before scanning.
- **Duplicate ingestion**: The document table uses content hash + source_path for dedup, but long-term table doesn't have a built-in dedup against the doc table. If you ingest both sessions AND PDFs, they might overlap semantically (which is fine — different tables serve different purposes).
- **Missing dependencies**: The container does NOT ship with required packages. After rebuild, run `pip install numpy faiss-cpu fastembed pymupdf` before the pipeline. Missing `numpy` crashes at engine.py import, missing `pymupdf` crashes at PDF ingestion step.
- **Corrupt meta JSON**: If the pipeline is killed mid-write, `meta_long.json` can be truncated. The `EmbeddingEngine()` constructor crashes with `JSONDecodeError`. Run the recovery procedure from `references/meta-recovery.md`.
- **6-table vs 3-table mismatch**: `ingest_with_checkpoints.py` writes to 6 separate FAISS tables (long/short × user/assistant/tool), but `engine.py`'s `stats()` only reports 3 tables (long_term, short_term, doc_table). The session ingestion count (e.g., "782 chunks") lives in the 6-table system. To get full stats, query all `.index` files individually via `faiss.read_index(f).ntotal`.
