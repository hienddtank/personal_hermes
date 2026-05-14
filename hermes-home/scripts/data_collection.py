#!/usr/bin/env python3
"""
Data collection script for Hermes Agent - Cron Job Version.

IMPORTANT: This script runs as a standalone cron job (no hermes_tools available).
Since session_search and memory tools are only available inside Hermes Agent sessions,
this script collects what it can from the filesystem.

For full session history extraction, use:
  python3 /root/.hermes/scripts/full_extract_sessions.py
    
Usage:
    python3 data_collection.py              # Regular cron run (last 10 sessions)
    MANUAL_FULL_EXTRACT=1 python3 data_collection.py  # Full extraction mode
"""

import os
import json
import glob
from datetime import datetime, timedelta

# ============================================================
# Configuration
# ============================================================
CHAT_HISTORY_DIR = os.path.expanduser("~/.hermes/chat_history")
WORKSPACE_DIR = os.path.expanduser("~/.hermes/workspace/chat_history")
MEMORY_FILE = os.path.expanduser("~/.hermes/memory.json")
SCRIPT_VERSION = "3.0.0"

def ensure_dirs():
    """Create necessary directories."""
    os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)
    try:
        os.makedirs(WORKSPACE_DIR, exist_ok=True)
    except Exception:
        pass  # Workspace dir may not be writable in sandbox


def get_recent_chat_files(limit=10):
    """
    Find recent chat history JSONL files and extract session data.
    Returns a list of session summary dicts from existing export files.
    """
    sessions_data = []
    seen_ids = set()  # Deduplicate across multiple runs
    
    # Look for today's file first, then yesterday's
    today = datetime.now().strftime('%Y%m%d')
    search_files = [f"{today}.jsonl"]
    
    # Also check last 3 days
    for i in range(1, 4):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
        search_files.append(f"{date}.jsonl")
    
    for filename in search_files:
        filepath = os.path.join(CHAT_HISTORY_DIR, filename)
        if not os.path.exists(filepath):
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        # Include session summaries (with or without version - old exports may lack it)
                        # Exclude our own export markers and memory entries from source files
                        rtype = record.get('type', '')
                        sid = record.get('session_id', '')
                        
                        if rtype == 'session_summary' and sid:
                            # Deduplicate across multiple runs
                            if sid not in seen_ids:
                                seen_ids.add(sid)
                                sessions_data.append(record)
                    except json.JSONDecodeError:
                        continue
                        
            print(f"  Read {len(sessions_data)} records from {filepath}")
        except Exception as e:
            print(f"  Warning: Could not read {filepath}: {e}")
    
    return sessions_data[-limit:]


def get_memory_from_file():
    """Try to load memory entries from a JSON file on disk."""
    memory_data = []
    
    if not os.path.exists(MEMORY_FILE):
        print("  No memory.json found (memory is stored per-session, not as a single file)")
        return memory_data
    
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                for entry in data[-20:]:  # Last 20 entries
                    if isinstance(entry, dict):
                        memory_data.append({
                            "type": "memory",
                            **entry
                        })
        print(f"  Loaded {len(memory_data)} memory entries from disk")
    except Exception as e:
        print(f"  Warning: Could not read memory file: {e}")
    
    return memory_data


def save_sessions(file_path, sessions_data):
    """Save session summaries to the JSONL file (idempotent - reads existing first)."""
    # Read existing session_summaries to avoid duplicating them
    existing_ids = set()
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        sid = record.get('session_id', '')
                        rtype = record.get('type', '')
                        if rtype == 'session_summary' and sid:
                            existing_ids.add(sid)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
    
    # Filter out sessions already in the file
    new_sessions = [s for s in sessions_data if s.get('session_id') not in existing_ids]
    
    with open(file_path, 'a', encoding='utf-8') as f:
        for s in new_sessions:
            record = {
                "type": "session_summary",
                "version": SCRIPT_VERSION,
                "exported_at": datetime.now().isoformat(),
                **s
            }
            # Remove duplicate exported_at if present from source
            if 'exported_at' in s:
                del record['exported_at']
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"  Saved {len(new_sessions)} new session summaries to {file_path} (already had {len(existing_ids)})")


def save_memory(file_path, memory_data):
    """Append memory entries to the JSONL file (idempotent - reads existing first)."""
    # Read existing memory entries to avoid duplicating them
    existing_keys = set()
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        key = record.get('key', '')
                        rtype = record.get('type', '')
                        if rtype == 'memory_entry' and key:
                            existing_keys.add(key)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
    
    # Filter out entries already in the file
    new_entries = [m for m in memory_data if str(m.get('key', '')) not in existing_keys]
    
    with open(file_path, 'a', encoding='utf-8') as f:
        for m in new_entries:
            record = {
                "type": "memory_entry",
                "version": SCRIPT_VERSION,
                "exported_at": datetime.now().isoformat(),
                **m
            }
            if 'exported_at' in m:
                del record['exported_at']
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"  Saved {len(new_entries)} new memory entries to {file_path} (already had {len(existing_keys)})")


def create_archive(sessions_data, workspace_dir):
    """Create a comprehensive archive of all session data."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_path = os.path.join(workspace_dir, f"{timestamp}_full_archive.jsonl")
    
    with open(archive_path, 'w', encoding='utf-8') as f:
        for s in sessions_data:
            record = {
                "type": "session_full",
                "version": SCRIPT_VERSION,
                "exported_at": datetime.now().isoformat(),
                **s
            }
            if 'exported_at' in s:
                del record['exported_at']
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"  Created full archive: {archive_path}")
    return archive_path


def main():
    """Main data collection routine."""
    print(f"=== Data Collection Script v{SCRIPT_VERSION} ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Check for full extraction mode
    full_extraction = os.environ.get("MANUAL_FULL_EXTRACT") == "1" or \
                      os.environ.get("MANUAL_FULL_EXTRACT")
    if full_extraction:
        print("=== FULL EXTRACTION MODE ===")
    
    ensure_dirs()
    
    # NOTE: In cron job context, hermes_tools is not available.
    # Session data can only be collected from previously exported files on disk.
    # For first-run or empty state, the script writes a marker and exits gracefully.
    
    print("\nCollecting session history...")
    sessions_data = get_recent_chat_files(limit=50 if full_extraction else 10)
    
    # If no data found from files, check if this is a fresh install
    if not sessions_data:
        all_jsonl_files = sorted(glob.glob(os.path.join(CHAT_HISTORY_DIR, "*.jsonl")))
        if not all_jsonl_files or (len(all_jsonl_files) == 1 and 
                                   datetime.now().strftime('%Y%m%d.jsonl') in all_jsonl_files):
            print("  No prior session data found on disk.")
            print("  This is expected for a fresh cron run. Session history")
            print("  will accumulate as previous exports write to chat_history/.")
        
        # Write a marker so we know the export ran successfully
        today = datetime.now().strftime('%Y%m%d')
        file_path = os.path.join(CHAT_HISTORY_DIR, f"{today}.jsonl")
        with open(file_path, 'a', encoding='utf-8') as f:
            record = {
                "type": "export_marker",
                "version": SCRIPT_VERSION,
                "timestamp": datetime.now().isoformat(),
                "note": "Cron export ran but no prior session data was available on disk. Use full_extract_sessions.py for initial backup."
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(f"  Export marker saved to: {file_path}")
        
        # Return success (0) - this is normal operation, not a failure
        return 0
    
    print(f"\nFound {len(sessions_data)} sessions on disk")
    
    # Fetch memory entries (if available as file)
    print("\nChecking for memory data...")
    memory_data = get_memory_from_file()
    
    # Save to today's file
    today = datetime.now().strftime('%Y%m%d')
    today_file = os.path.join(CHAT_HISTORY_DIR, f"{today}.jsonl")
    
    print(f"\nSaving to: {today_file}")
    save_sessions(today_file, sessions_data)
    if memory_data:
        save_memory(today_file, memory_data)
    
    # If full extraction, create additional archives
    if full_extraction and sessions_data:
        print("\nCreating full archives...")
        archive_path = create_archive(sessions_data, WORKSPACE_DIR)
        
        ws_archive = os.path.join(WORKSPACE_DIR, f"{today}_workspace_archive.jsonl")
        with open(ws_archive, 'w', encoding='utf-8') as f:
            for s in sessions_data:
                record = {
                    "type": "session_full",
                    "version": SCRIPT_VERSION,
                    "exported_at": datetime.now().isoformat(),
                    **s
                }
                if 'exported_at' in s:
                    del record['exported_at']
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(f"  Created workspace archive: {ws_archive}")
    
    # Summary
    total_records = len(sessions_data) + len(memory_data)
    print(f"\n=== Collection Complete ===")
    print(f"  Sessions collected from disk: {len(sessions_data)}")
    print(f"  Memory entries: {len(memory_data)}")
    print(f"  Total records exported: {total_records}")
    print(f"  Output file: {today_file}")
    
    return 0


if __name__ == "__main__":
    exit(main() or 0)
