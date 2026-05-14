"""checkpoint_batch_processor.py — Drop-in batch processor with checkpointing.

Usage:
  python3 checkpoint_batch_processor.py --last-n 10 --batch-size 20
  python3 checkpoint_batch_processor.py --start-new --batch-size 50
  python3 checkpoint_batch_processor.py --resume-only

Requires: Override process_item() for your use case.
"""

import os, sys, json, time, argparse
from datetime import datetime
from pathlib import Path

# ── Configuration (override these) ──
OUTPUT_DIR = "/host/d/mkt/python/hermes/workspace/embedding_engine"
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "checkpoint.json")
BREADCRUMB_LOG = os.path.join(OUTPUT_DIR, "breadcrumbs.log")
ITEMS_DIR = None  # Override: directory to scan for items
DEFAULT_BATCH_SIZE = 50

def log_breadcrumb(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    with open(BREADCRUMB_LOG, "a") as f:
        f.write(line)
    print(f"\r[BC] {msg}", end="", flush=True)

class CheckpointManager:
    def __init__(self, cp_file=CHECKPOINT_FILE):
        self.cp = self._load()
    
    def _load(self):
        if os.path.exists(cp_file):
            with open(cp_file) as f:
                return json.load(f)
        return {"done": [], "total_work": 0, "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_updated": None}
    
    def save(self):
        self.cp["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(cp_file, "w") as f:
            json.dump(self.cp, f, indent=2)
    
    def is_done(self, item_id): return item_id in self.cp["done"]
    def mark_done(self, item_id, work=1):
        self.cp["done"].append(item_id)
        self.cp["total_work"] += work

# ── OVERRIDE THIS FUNCTION ──
def process_item(item_path, checkpoint):
    """Process one item. Returns number of work units (chunks/records/etc)."""
    # YOUR LOGIC HERE
    return 1

# ── MAIN ──
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-new", action="store_true")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--last-n", type=int, default=-1)
    parser.add_argument("--resume-only", action="store_true")
    args = parser.parse_args()
    
    cp = CheckpointManager()
    if args.start_new:
        cp.cp["done"] = []
        cp.cp["total_work"] = 0
    
    if ITEMS_DIR is None or not os.path.isdir(ITEMS_DIR):
        print(f"ERROR: Set ITEMS_DIR to your input directory (was: {ITEMS_DIR})")
        sys.exit(1)
    
    all_items = sorted([f for f in os.listdir(ITEMS_DIR) if os.path.isfile(os.path.join(ITEMS_DIR, f))])
    if args.last_n > 0:
        all_items = all_items[-args.last_n:]
    
    remaining = [i for i in all_items if not cp.is_done(i)]
    log_breadcrumb(f"Items: {len(all_items)} total, {cp.cp['total_work']} work done, {len(remaining)} remaining")
    
    total_work = 0
    batch_num = 0
    for start in range(0, len(remaining), args.batch_size):
        batch = remaining[start:start + args.batch_size]
        batch_num += 1
        log_breadcrumb(f"BATCH {batch_num}: {len(batch)} items")
        
        for item in batch:
            path = os.path.join(ITEMS_DIR, item)
            work = process_item(path, cp)
            total_work += work
        
        cp.save()
        log_breadcrumb(f"Batch {batch_num} done: +{len(batch)} items (total: {cp.cp['total_work']})")
    
    print(f"\n{'='*60}\nDONE. Items: {len(cp.cp['done'])}, Work: {cp.cp['total_work']}")

if __name__ == "__main__":
    main()
