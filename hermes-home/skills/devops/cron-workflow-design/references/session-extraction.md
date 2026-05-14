# Session Extraction Pattern (Cron)

## Problem
`data_collection.py` runs standalone (no hermes_tools available), so it only reads previously-exported JSONL files. If no prior exports exist, it writes markers and exits with 0 — never actually collecting session data.

## Root Cause
The script at `/hermes-home/scripts/data_collection.py` depends on `full_extract_sessions.py` having run first (which uses hermes_tools to query sessions). But `full_extract_sessions.py` also needs hermes_tools, which aren't available in a standalone Python context — it must run inside a Hermes Agent session.

The chicken-and-egg cycle: the script reads JSONL files looking for records with `type == "session_summary"`. But the script itself only ever wrote `export_marker` records (when it found nothing). So every subsequent run also finds nothing — fresh installs never bootstrap themselves.

### Symptom: repeated "Read 0 records from" lines
```
Read 0 records from 20260507.jsonl
Read 0 records from 20260506.jsonl
Read 0 records from 20260505.jsonl
Export marker saved to: 20260507.jsonl
```
The files exist on disk (`cat` shows content) but contain only `export_marker` entries, not `session_summary` entries. This is the key diagnostic.

## Solution
When running as a cron job with agent tool access:

1. Call `session_search()` (no args or with a broad query) in your main conversation to discover sessions.
2. Write session_summary records to `~/.hermes/chat_history/YYYYMMDD.jsonl` using a python script or heredoc call.
3. Subsequent cron runs of `data_collection.py` will then correctly find and accumulate sessions.

### IMPORTANT: `session_search()` Return Format
**The tool returns `{"results": [...]}`, NOT `{"sessions": [...]}`.** Each result item has keys like `session_id`, `when`, `source`, `model`, `summary`, and `preview`. Do NOT look for `result.get('sessions')` — that returns `None`.

```python
# WRONG — returns None:
result.get('sessions', [])

# RIGHT:
result.get('results', [])
```

This differs from the `full_extract_sessions.py` script which uses the internal `hermes_tools.session_search()` Python API.

### Complete bootstrap procedure (in-session)

```python
import json, os
from datetime import datetime

# 1. Discover sessions via the tool
#    Just call session_search() as a tool (no code) and collect results

# 2. Organize sessions by date into a dict
sessions_by_date = {
    "20260507": [
        {
            "session_id": "session_id_here",
            "started_at": "2026-05-07T13:10:22Z",
            "source": "telegram",  # or "cron", "api_server"
            "model": "model-name",
            "title": "Short descriptive title",
            "preview": "Brief summary of what happened (keep under 500 chars)"
        }
    ]
}

# 3. Write to each date's JSONL file, preserving existing markers
CHAT_HISTORY_DIR = os.path.expanduser("~/.hermes/chat_history")

for date_str, sessions in sessions_by_date.items():
    filepath = os.path.join(CHAT_HISTORY_DIR, f"{date_str}.jsonl")
    
    # Read existing markers (export_marker, etc.) to preserve them
    existing_markers = []
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r.get('type') == 'export_marker':
                        existing_markers.append(r)
    
    # Rewrite: markers first, then session_summary records
    with open(filepath, 'w') as f:
        for marker in existing_markers:
            f.write(json.dumps(marker) + '\n')
        for s in sessions:
            record = {
                "type": "session_summary",
                "exported_at": datetime.now().isoformat(),
                "session_id": s["session_id"],
                "id": s["session_id"],
                "started_at": s.get("started_at", ""),
                "source": s.get("source", ""),
                "model": s.get("model", ""),
                "title": s.get("title", ""),
                "preview": s.get("preview", "")
            }
            f.write(json.dumps(record) + '\n')
```

### Key pitfalls
- **`execute_code` sandbox does NOT have session_search** — you must call the session_search tool directly in your conversation, or use `terminal` to run stdlib code that reads/writes JSONL files.
- **The file path for cron scripts** is `/hermes-home/scripts/`, not `/root/.hermes/scripts/` — check your cron config if paths fail.
- **Script path resolution in cron jobs:** The cron system requires just the **filename** (relative) in the `script` field. It resolves against `~/.hermes/scripts/`. If you get "Blocked: script path resolves outside the scripts directory (/hermes-home/scripts)", fix by setting `script` to just `data_collection.py`.
- **Deduplicate by session_id** when appending — the data_collection script has its own dedup logic that checks `session_id` and avoids writing duplicates. But if you're manually bootstrapping, ensure you don't write the same session_id twice.
- **Preserve existing markers** — don't overwrite the file. The JSONL may contain `export_marker` records from previous cron runs that serve as a run log. Read them first, then append/write session_summary records.
- **`session_search()` only returns recent sessions by default** — use a keyword query to reach further back. Without a query, it returns ~3 most recent. With a broad query like "cron or health or gateway or telegram", it returns more.
- **The data_collection.py script counts session_summary records from ALL files, not just today's** — it looks at today's + last 3 days. After bootstrapping, those files will be read and deduplicated against whatever is already in today's file.

## Verification

```bash
# Verify session_summary records exist
cat ~/.hermes/chat_history/$(date +%Y%m%d).jsonl | python3 -c "
import sys, json
lines = [json.loads(l) for l in sys.stdin if l.strip()]
summaries = [l for l in lines if l.get('type') == 'session_summary']
print(f'{len(summaries)} session summaries, {len(lines) - len(summaries)} non-summary records')
for s in summaries:
    print(f'  - {s.get(\"session_id\",\"?\")[:50]}')
"

# Run the data collection script to confirm it picks up sessions
python3 /hermes-home/scripts/data_collection.py

# Expected output includes:
#   Read N records from ...jsonl
#   Found N sessions on disk
#   Saved N new session summaries to ...jsonl
```
