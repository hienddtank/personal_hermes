---
name: robust-batch-processing
description: "Build fault-tolerant batch processing pipelines with checkpointing, resumability, and timeout protection for long-running data operations."
version: 1.0.0
author: Hermes Agent
tags: [batch-processing, checkpointing, resumption, fault-tolerance, pipelines]
category: data-science
---

# Robust Batch Processing with Checkpoints

Build long-running batch processing scripts that survive interruptions via automatic checkpoint persistence, breadcrumb logging, and resumable execution.

## When to Use This Pattern

- Any batch operation expected to run >60 seconds (file processing, embedding generation, data transformation)
- User explicitly asks for "checkpoints" or "timeout system"
- Processing many files where partial progress should be preserved
- Operations that could be interrupted by timeouts or manual cancellation

## Core Design Pattern

A robust batch processor has three components:

1. **Checkpoint file** — JSON state tracking which items are done, total counts, timestamps
2. **Breadcrumb log** — Timestamped text log of every processing step (append-only)
3. **Batch loop** — Processes items in chunks, saves checkpoint after each batch

## Standard Implementation Template

```python
"""robust_batch_processor.py - Generic batch processing with checkpoints."""

import os, sys, json, time, hashlib, argparse
from datetime import datetime
from pathlib import Path

# ── Configuration (override per use case) ──
OUTPUT_DIR = "/path/to/output"
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "checkpoint.json")
BREADCRUMB_LOG = os.path.join(OUTPUT_DIR, "breadcrumbs.log")
ITEMS_DIR = "/path/to/input"  # Directory of files/items to process
DEFAULT_BATCH_SIZE = 50

# ── Breadcrumb logging (append-only, timestamped) ──
def log_breadcrumb(message):
    """Write timestamped breadcrumb to log file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}\n"
    with open(BREADCRUMB_LOG, "a") as f:
        f.write(line)
    print(f"\r[BC] {message}", end="", flush=True)

# ── Checkpoint class (handles persistence and resume logic) ──
class CheckpointManager:
    def __init__(self, checkpoint_file=CHECKPOINT_FILE):
        self.checkpoint = self._load()
    
    def _load(self):
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file) as f:
                data = json.load(f)
            log_breadcrumb(f"Resumed from checkpoint: {data.get('processed_items', 0)} items already done")
            return data
        return {
            "processed_items": [],
            "total_work_units": 0,
            "last_updated": None,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    
    def save(self):
        self.checkpoint["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.checkpoint_file, "w") as f:
            json.dump(self.checkpoint, f, indent=2)
    
    def is_done(self, item_id):
        return item_id in self.checkpoint["processed_items"]
    
    def mark_done(self, item_id, work_units_added=1):
        self.checkpoint["processed_items"].append(item_id)
        self.checkpoint["total_work_units"] += work_units_added

# ── Processing function (override for your use case) ──
def process_item(item_path, checkpoint):
    """Process a single item. Returns number of work units added."""
    # YOUR PROCESSING LOGIC HERE
    return 1

# ── Main batch loop ──
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-new", action="store_true")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=-1, help="Max items to process (-1 = all)")
    args = parser.parse_args()
    
    # Load checkpoint
    cp = CheckpointManager()
    if args.start_new:
        cp.checkpoint["processed_items"] = []
        cp.checkpoint["total_work_units"] = 0
    
    # Get items to process
    items = sorted([f for f in os.listdir(ITEMS_DIR) if f.endswith(".jsonl")])
    if args.limit > 0:
        items = items[-args.limit:]
    
    remaining = [i for i in items if not cp.is_done(i)]
    log_breadcrumb(f"Starting: {len(remaining)} items remaining (total available: {len(items)})")
    
    # Batch loop
    total_added = 0
    for batch_start in range(0, len(remaining), args.batch_size):
        batch = remaining[batch_start:batch_start + args.batch_size]
        log_breadcrumb(f"\nBATCH START: {len(batch)} items ({batch_start+1}-{min(batch_start+len(batch), len(remaining))}/{len(remaining)})")
        
        for item in batch:
            item_path = os.path.join(ITEMS_DIR, item)
            added = process_item(item_path, cp)
            total_added += added
        
        # Save after each batch
        cp.save()
        log_breadcrumb(f"\nBATCH DONE: +{len(batch)} items (total processed: {cp.checkpoint['processed_items']})")
    
    print(f"\n{'='*60}\nDONE. Total: {len(cp.checkpoint['processed_items'])} items, {total_added} work units added")

if __name__ == "__main__":
    main()
```

## Usage Pattern

```bash
# Initial run — processes all items
python3 robust_batch_processor.py --batch-size 50

# Resume after interruption (skips already-processed items)
python3 robust_batch_processor.py --batch-size 50

# Process only last N items
python3 robust_batch_processor.py --limit 10

# Start completely over (clear checkpoint)
python3 robust_batch_processor.py --start-new --limit 5
```

## Checking Progress Without Re-running

```bash
# Checkpoint state (JSON)
cat checkpoint.json | python3 -m json.tool

# Breadcrumb log (human-readable progress trail)
tail -20 breadcrumbs.log

# Quick count of processed items
grep -c "BATCH DONE" breadcrumbs.log
```

## Key Design Decisions

1. **Checkpoint saves AFTER each batch** — not after every item (too many writes). Balance between durability and performance.
2. **Breadcrumb log is append-only** — never overwritten, always safe to read while processing runs.
3. **Item ID must be unique and stable** — typically filename or hash. Don't use mutable identifiers.
4. **Batch size 50 is default sweet spot** — large enough for efficiency, small enough that losing a batch isn't catastrophic.
5. **Process function should be idempotent-safe** — if called twice on same item, shouldn't duplicate work or corrupt data.

## Pitfalls

1. **Don't skip checkpoint saves** — if the process crashes between batches, you lose only one batch's worth of work.
2. **Don't log to stdout only** — terminal output is lost after crash. Always write to file.
3. **Don't store large state in checkpoint** — it's read entirely into memory on resume. Keep it lean (IDs and counts).
4. **Don't assume items are sorted correctly** — always `sorted()` your file list to get consistent ordering across runs.

## Variations

- **Database ingestion**: Replace `ITEMS_DIR` with DB connection, use primary keys as item IDs
- **Web scraping**: Item ID = URL hash, checkpoint tracks URLs already scraped
- **Model training**: Checkpoint saves model weights + optimizer state (heavier but more durable)
- **File conversion**: Use checksums or modification times as resume criteria instead of simple done-list
- **API enrichment with cron scheduling**: See `references/cron-scheduled-enrichment.md` for timezone-aware runner scripts that auto-start during inactive hours, auto-stop during work hours, and restart on failure via cron jobs.

## Cron-Scheduled Batch Processing

For long-running enrichment jobs that should run during inactive hours:

```bash
#!/bin/bash
# runner.sh — timezone-aware batch processor runner
# Run via cron every 30m to ensure process stays alive

CURRENT_UTC_HOUR=$(date -u +%H)
# Example: 10pm GMT+7 = 3pm UTC (start), 7am GMT+7 = midnight UTC (stop)

if [ "$CURRENT_UTC_HOUR" -ge 0 ] && [ "$CURRENT_UTC_HOUR" -lt 15 ]; then
    pkill -f batch_processor 2>/dev/null  # Kill if user is awake
    exit 0
fi

# User is sleeping → ensure process is running
pgrep -f batch_processor > /dev/null || {
    cd /path/to/project && nohup python3 batch_processor.py >> processor.log 2>&1 &
}
```

**Setup**: Two cron jobs:
1. **Runner** (every 30m): Checks timezone, starts/kills process
2. **Progress reporter** (every 6h): Sends status notification to user

**CSV checkpointing** (for tabular data): Save CSV after each row — simpler than JSON checkpoints:
```python
# After processing each row:
row['result'] = result
rows[i] = row
save_csv(rows)  # Overwrite entire file — atomic enough for single-writer
```

## Related Skills

- `jupyter-live-kernel` — for interactive exploration before committing to batch processing
- `data-science/read-xlsx` — for reading spreadsheet input data
- `docker-restart` — for restarting services after data pipeline completion
- `evolution-strategy-training` — for ML model evolution checkpointing (mu/sigma distribution state + weights)

## See Also

- `references/openalex-api-patterns.md` — OpenAlex API quirks, pagination, rate limiting, email enrichment patterns