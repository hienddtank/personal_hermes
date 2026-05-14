# Hermes Agent Session Ingestion for Embedding Engine

Hermes Agent stores conversation history in `/hermes-home/sessions/`. Understanding the file format is critical before ingesting.

## File Inventory

| Format | Count | Purpose | Action |
|--------|-------|---------|--------|
| `*.jsonl` | ~177 | Actual conversations — one JSON object per line | **Ingest** |
| `request_dump_*.json` | ~629 | HTTP request logs (full API call bodies + headers) | **Skip** — duplicates JSONL content plus metadata noise |
| `sessions.json` | 1 | Index mapping session keys to metadata | Use for date/cutoff classification, not content |

## JSONL Structure

Each line is a JSON object. Line 1 varies:

```jsonc
// Line 1 (optional): session metadata — tools list only, skip for embedding
{"role": "session_meta", "tools": [...]}

// Subsequent lines: conversation messages
{"role": "user", "content": "...", "timestamp": "..."}
{"role": "assistant", "content": "...", "reasoning": "...", "tool_calls": [...], "timestamp": "..."}
{"role": "tool", "content": "...", "tool_call_id": "...", "timestamp": "..."}
```

### Role Types
- **user**: Direct messages from the user. Extract `content` only.
- **assistant**: My responses. Has optional fields: `reasoning`, `reasoning_content`, `tool_calls`. Combine `reasoning_content` (if exists) + `content`.
- **tool**: Tool outputs (`terminal`, `web_search`, `read_file`, etc.). Extract `content` only.
- **session_meta**: Tools list for the session. Skip — no semantic value for search.

### Key Fields per Role
```python
# User
text = msg["content"]

# Assistant (prefer reasoning for decision context)
text = msg.get("reasoning_content", msg.get("reasoning", "") + " " + msg.get("content", ""))

# Tool — CRITICAL: filter system prompt contamination
if role == "tool":
    content = msg["content"]
    if "You are Hermes Agent" in content[:200]:
        return None  # System prompt inside tool output — skip
    text = f"[TOOL_OUTPUT] {content}"
```

## Ingestion Strategy

1. **Classify by date**: Parse filename `YYYYMMDD_HHMMSS_*.jsonl` or use `sessions.json` metadata
2. **Split tables**: >7 days → long-term, ≤7 days → short-term
3. **Chunk per message**: ~250 chars with 50 char overlap, OR 500 chars with 100 overlap. Chunk size does not significantly affect query performance — both produce similar scores (0.18–0.49 vague, 0.60+ concrete). Larger chunks are more storage-efficient.
4. **Separate by role type**: user→user table, assistant→assistant table, tool→tool table
5. **Skip session_meta first line** and `request_dump_*.json` files

## Example Ingestion (per session)

```python
from pathlib import Path

def ingest_session(filepath: Path):
    lines = filepath.read_text().strip().split("\n")
    
    long_user, long_assist, long_tool = [], [], []
    short_user, short_assist, short_tool = [], [], []
    
    for line in lines:
        msg = json.loads(line)
        role = msg.get("role", "")
        
        if role == "session_meta":
            continue  # skip tools list
        
        # Extract text based on role
        if role == "user":
            text = msg["content"]
        elif role == "assistant":
            text = msg.get("reasoning_content", "") + " " + msg["content"].strip()
        elif role == "tool":
            text = msg["content"]
        else:
            continue
        
        # Classify by date (parse from filename)
        table = "long" if is_older_than_7_days(filepath) else "short"
        
        chunks = chunk_text(text, 250, 50)
        for chunk in chunks:
            if role == "user":
                globals()[f"{table}_user"].append(chunk)
            elif role == "assistant":
                globals()[f"{table}_assist"].append(chunk)
            elif role == "tool":
                globals()[f"{table}_tool"].append(chunk)
    
    return long_user, long_assist, long_tool, short_user, short_assist, short_tool
```

## Common Pitfalls

- **Request dumps are NOT conversations**: `request_dump_*.json` contains HTTP headers, auth tokens, full API request bodies. They duplicate JSONL content with added noise (system prompts, retry info). Skip them.
- **session_meta is not a message**: The first line often contains a tools list — it has no semantic value for search. Skip it.
- **Assistant reasoning vs content**: Always prefer `reasoning_content` when available — it captures the assistant's thought process which is more valuable for understanding decisions than the final response text.
- **Tool output can be large**: Terminal outputs, web search results, and file reads can span hundreds of characters. Chunk them aggressively (250 chars) to avoid embedding long irrelevant logs.
- **Schema migration corrupts indexes**: When changing table architecture (e.g., 2-table → 6-table), old `.index` + `meta_*.json` files cause FAISS read errors (`read error ... != ...`). Delete ALL existing index/metadata files before building new tables with a different schema.
