---
name: Chat History Extraction
description: Automatically extract and archive chat session data from Hermes Agent memory for fine-tuning purposes. Provides hourly auto-save and manual full extraction capabilities.
category: devops
---

# Chat History Extraction Skill

Automatically extract and archive chat session data from Hermes Agent memory for fine-tuning purposes.

## Purpose

This skill provides tools to:
1. **Agent-session export** - Use `session_search`/`memory` tools during active sessions
2. **Cron-based collection** - Standalone scripts that read exported JSONL files on disk
3. **Data export** - Export to JSONL format suitable for fine-tuning pipelines

## ⚠️ Critical: Tool Availability

The `hermes_tools` Python module is **NOT importable in standalone scripts**. The tools (`session_search`, `memory`) are only available as Hermes Agent tool calls inside active sessions. This means:

- **Inside agent sessions**: Call tools directly via the agent interface
- **In cron jobs / standalone Python**: Use filesystem-based collection (reads JSONL files written by previous exports) or accept empty results gracefully

## Setup

### Step 1: Install both scripts

Run this as a one-time setup in your terminal:

```bash
# data_collection.py - reads exported JSONL files from disk (for cron jobs)
curl -sLO https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/data_collection.py 2>/dev/null || true

# If you have the scripts locally, just copy them:
cp ~/.hermes/scripts/data_collection.py /tmp/verify-works.py  # sanity check
python3 /root/.hermes/scripts/data_collection.py
```

If curl isn't available, use `skill_view` to get the script content and write it manually.

### Step 2: Set up cronjobs

**Hourly data collection (reads from disk):**
```bash
(crontab -l 2>/dev/null; echo "0 * * * * cd ~ && python3 ~/.hermes/scripts/data_collection.py >> /tmp/chat_history_export.log 2>&1") | crontab -
```

**Full extraction on demand (can be run from agent session or manually):**
```bash
# Run inside an active Hermes Agent session:
# Use the `session_search` tool directly, then write to JSONL files

# Or run standalone with full extraction mode:
MANUAL_FULL_EXTRACT=1 python3 ~/.hermes/scripts/full_extract_sessions.py
```

## Architecture

The system uses a **two-layer approach**:

```
Agent Session                    Cron Job / Standalone
──────────────                   ──────────────────
session_search() tool    →       reads exported JSONL files
memory.tool calls        →       reads memory from disk (if available)
Writes to                  on disk:
  ~/.hermes/chat_history/     ✓ YYYYMMDD.jsonl (appended daily)
                              ✓ full archives in workspace dir
```

### How data flows:

1. **During agent sessions**: The agent calls `session_search()` and writes results to `~/.hermes/chat_history/YYYYMMDD.jsonl`
2. **In cron jobs**: `data_collection.py` reads those JSONL files from disk, deduplicates by version marker, and appends fresh records
3. **Full extraction**: `full_extract_sessions.py` attempts direct tool calls (when run inside agent context) or reads from disk as fallback

## Files Created

- `~/.hermes/chat_history/YYYYMMDD.jsonl` - Daily export files
- `~/.hermes/workspace/chat_history/TIMESTAMP_full_archive.jsonl` - Full extraction archives  
- `~/.hermes/scripts/data_collection.py` - Standalone cron script (reads from disk)
- `~/.hermes/scripts/full_extract_sessions.py` - Agent-context full extractor

## Data Format

**Session Entry:**
```json
{
  "type": "session_summary" | "session_full",
  "version": "3.0.0",
  "exported_at": "...",
  "session_id": "...",
  "title": "...",
  "timestamp": "...",
  "summary": "..."
}
```

**Memory Entry:**
```json
{
  "type": "memory_entry",
  "version": "3.0.0",
  "key": "...",
  "value": "..."
}
```

**Export Marker (when no prior data exists):**
```json
{"type": "export_marker", "version": "3.0.0", "timestamp": "..."}
```

## Usage

### Inside Agent Session (full tool access)
Use `session_search()` to get all sessions, then export:
1. Call the `session_search` tool  
2. Iterate results and write to JSONL file using Python code

### Cron Job / Standalone (disk-based only)
```bash
python3 ~/.hermes/scripts/data_collection.py           # Normal mode
MANUAL_FULL_EXTRACT=1 python3 ~/.hermes/scripts/data_collection.py  # Full mode
```

### Load for Fine-tuning
```python
import json
from pathlib import Path

history_dir = Path.home() / ".hermes" / "chat_history"
all_records = []
for f in sorted(history_dir.glob("*.jsonl")):
    with open(f) as fh:
        for line in fh:
            if line.strip():
                all_records.append(json.loads(line))

# Filter for actual session data only
sessions = [r for r in all_records 
            if r.get('type') == 'session_full' and 'version' in r]
print(f"Found {len(sessions)} sessions")
```

## Troubleshooting

### Cron job fails with "No module named 'hermes_tools'" or "Cannot import session_search"
**Diagnosis**: `hermes_tools` **is installed** (via `hermes-agent==0.7.0`) but is an **RPC stub**, not a full tools library. It only exposes: `terminal`, `read_file`, `write_file`, `search_files`, `web_search`, `web_extract`, `patch`, `json_parse`, `shell_quote`, `retry`. Built-in tools like `session_search()` and `memory` are internal agent handlers, NOT available in standalone Python scripts.

**Verify**: 
```bash
python3 -c "import hermes_tools; print([x for x in dir(hermes_tools) if not x.startswith('_')])"
# Check RPC socket: echo $HERMES_RPC_SOCKET
```

**Fix**: Use the updated `data_collection.py` (v3.0.0+) that reads from JSONL files on disk instead of importing tools. Never use `from hermes_tools import session_search` or `from hermes_tools import memory` in cron/standalone scripts — they will always fail.

### No data in exported files
This is expected if:
- The cron job ran before any agent sessions exported data (it creates a marker)
- The system is newly installed (no prior exports exist yet)
- Run `MANUAL_FULL_EXTRACT=1 python3 ~/.hermes/scripts/full_extract_sessions.py` from an **agent session** for initial backup

### Duplicate entries in JSONL files
The v3.0.0+ script filters by `"version"` field to exclude internal markers and deduplicates when reading existing files. If you have old duplicates, regenerate today's file:
```bash
today=$(date +%Y%m%d)
grep -v '"export_marker"' ~/.hermes/chat_history/$today.jsonl > /tmp/clean.jsonl
mv /tmp/clean.jsonl ~/.hermes/chat_history/$today.jsonl
```

### Script exists but cron still fails (version mismatch)
**Symptom**: The correct `data_collection.py` v3.0.0+ exists on disk, but cron still reports `hermes_tools` import errors.  
**Diagnosis workflow**:
1. Check what the cron job actually executes: inspect crontab or cron job config (`crontab -l`) or use `cronjob action='list'` to see the full command
2. Verify the script on disk works: `python3 /root/.hermes/scripts/data_collection.py` (should exit 0)
3. Look for old scripts being called instead of the new one (wrong path, stale symlink, etc.)

**Common pitfall**: Old export scripts wrote session summaries *without* a `"version"` field. The v3.0.0+ script's original filter required `'version' in record`, silently dropping all legacy entries and producing empty results — which looked like "cron failure" but was actually silent data loss. Fix: accept session summaries regardless of version presence, then add `version` on write.

**Idempotency fix**: The `save_sessions()` function must check what's already in today's file before appending, otherwise each cron run duplicates all previously-exported sessions. Pattern:
```python
# Read existing IDs from target file first
existing_ids = set()
with open(file_path) as f:
    for line in f:
        rec = json.loads(line.strip())
        if rec.get('type') == 'session_summary' and rec.get('session_id'):
            existing_ids.add(rec['session_id'])

# Only write sessions not already present
new_sessions = [s for s in data if s.get('session_id') not in existing_ids]
```

### Cron job runs inline Python instead of calling the script (exit code 2)
**Symptom**: Cron fails with "Script exited with code 2" and stdout showing:
```
Error: Cannot import hermes_tools. Is Hermes installed?
Details: No module named 'hermes_tools'
```

**Root cause**: The cron task was configured with an embedded script (inline Python) instead of calling the proper `data_collection.py`. This happens when using a cronjob toolset with `action='create'` and providing inline code.

**Fix — Option A: Update cron to call the script:**
```bash
# Instead of inline Python, run:
python3 /root/.hermes/scripts/data_collection.py
```

**Fix — Option B: Rewrite inline script to use subprocess:**
If you must keep inline Python (e.g., for custom logic), replace tool imports with filesystem reads:
```python
# WRONG: from hermes_tools import session_search  # Never works in cron
# RIGHT: Read exported JSONL files directly
import json, os
history_dir = os.path.expanduser("~/.hermes/chat_history")
for f in sorted(os.listdir(history_dir)):
    if f.endswith('.jsonl'):
        with open(os.path.join(history_dir, f)) as fh:
            for line in fh:
                rec = json.loads(line)
```

**Fix — Option C: Use `cronjob action='update'` to switch to script-based:**
Update the cron job configuration to use `/root/.hermes/scripts/data_collection.py` as the command instead of inline Python.

### Script file location must be `~/.hermes/scripts/` (not `chat_history/`)
**Critical**: Data collection scripts MUST live in `~/.hermes/scripts/`. Writing them to `~/.hermes/chat_history/` causes:
- Cron jobs that point to the standard path still run old broken versions
- The fix is invisible — cron reports success but exports nothing (reads empty files)

**Verification**: After writing a fixed script, confirm it's in the right place:
```bash
ls -la ~/.hermes/scripts/data_collection.py  # Should exist
python3 ~/.hermes/scripts/data_collection.py  # Should exit 0
# Also verify cron job uses this exact path (not chat_history/)
crontab -l | grep data_collection
```

**If cron still fails after fix**: The cron job may reference a different script path. Update via `cronjob action='update'` with the correct path, or replace `data_collection.py` in place at `~/.hermes/scripts/`.

### Cron jobs filter out their own empty sessions
Data-collection cron runs often appear as "sessions" in session_search results but contain only a 1-line SYSTEM prompt (no actual user interaction). These are noise:
- **Filter pattern**: Skip any session with `message_count <= 2` AND preview starts with `[SYSTEM cron]` or `[SYSTEM: You are running as a scheduled cron job]`
- Apply this filter in the export/load script to avoid polluting fine-tuning data with empty cron sessions.