#!/usr/bin/env python3
"""
Full Session Extraction Script - Cron-Safe Version

IMPORTANT: In cron/standalone environments, hermes_tools is NOT available.
This script handles both contexts:
- Inside agent session: uses direct tool calls for full data extraction
- Outside agent session (cron): reads from exported JSONL files on disk as fallback

Usage:
  python3 ~/.hermes/scripts/full_extract_sessions.py      # Run directly
  MANUAL_FULL_EXTRACT=1 python3 ~/.hermes/scripts/...     # Full extraction mode
"""

import os
from datetime import datetime, timedelta
import json

# Use expanduser for cross-platform compatibility
chat_history_dir = os.path.expanduser("~/.hermes/chat_history")
workspace_path = os.path.expanduser("~/.hermes/workspace/chat_history")
SCRIPT_VERSION = "3.0.0"

os.makedirs(chat_history_dir, exist_ok=True)
os.makedirs(workspace_path, exist_ok=True)

# Check if full extraction is requested
full_extraction = os.environ.get("MANUAL_FULL_EXTRACT", "").lower() in ("1", "true", "yes")
if full_extraction:
    print("=== FULL EXTRACTION MODE ===")


def try_direct_tool_call():
    """Attempt to fetch session data directly from Hermes Agent tools.
    
    This only works when running inside an active agent session.
    In cron/standalone environments, this will fail gracefully.
    """
    sessions_data = []
    memory_data = []

    # Try direct tool call for sessions
    try:
        from hermes_tools import session_search as ss_tool
        result = ss_tool()
        
        if isinstance(result, dict) and 'sessions' in result:
            limit = len(result['sessions']) if full_extraction else 50
            all_sessions = result['sessions'][:limit]
            
            for s in all_sessions:
                sessions_data.append({
                    "session_id": s.get('id', 'unknown'),
                    "title": s.get('title', 'No title') or '',
                    "timestamp": s.get('timestamp', '') or '',
                    "summary": (s.get('preview', '') or '')[:500]
                })
            print(f"  ✓ Fetched {len(sessions_data)} sessions via direct tool call")
        else:
            print(f"  ⚠ Unexpected session_search format: {type(result)}")
    except ImportError:
        # hermes_tools not available - this is expected in cron environments
        pass
    except Exception as e:
        print(f"  ✗ Error fetching sessions via tool: {e}")

    # Try direct tool call for memory entries
    try:
        from hermes_tools import memory as mem_tool
        
        if hasattr(mem_tool, 'list_keys'):
            mem_keys = mem_tool.list_keys() or []
            for k in mem_keys:
                val = mem_tool.get(k) if hasattr(mem_tool, 'get') else None
                if val is not None:
                    memory_data.append({
                        "type": "memory",
                        "key": str(k),
                        "value": str(val)[:2000]
                    })
            print(f"  ✓ Fetched {len(memory_data)} memory entries via direct tool call")
    except ImportError:
        pass
    except Exception as e:
        print(f"  ✗ Error fetching memory: {e}")

    return sessions_data, memory_data


def read_exported_files():
    """Read session data from previously exported JSONL files on disk.
    
    This is the fallback method when direct tool calls aren't available
    (i.e., in cron jobs or standalone Python environments).
    """
    sessions_data = []
    seen_ids = set()

    # Search back 3 days for existing exports
    today = datetime.now().date()
    search_dates = [today - timedelta(days=i) for i in range(4)]
    
    for date_obj in search_dates:
        filename = f"{date_obj.strftime('%Y%m%d')}.jsonl"
        filepath = os.path.join(chat_history_dir, filename)
        
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
                        
                        # Skip our own export markers and duplicate exports
                        rtype = record.get('type', '')
                        ver = record.get('version', '')
                        sid = record.get('session_id', '')
                        
                        if rtype == 'export_marker':
                            continue
                        
                        if rtype in ('session_summary', 'session_full') and ver:
                            # Avoid duplicate sessions from re-exports
                            session_key = f"{sid}:{record.get('timestamp', '')}"
                            if session_key not in seen_ids:
                                seen_ids.add(session_key)
                                record['version'] = SCRIPT_VERSION
                                record['exported_at'] = datetime.now().isoformat()
                                
                                # Only include session data, not memory entries
                                if rtype == 'session_full':
                                    sessions_data.append(record)
                    except json.JSONDecodeError:
                        continue
                        
            print(f"  ✓ Read from {filepath}")
        except Exception as e:
            print(f"  ⚠ Could not read {filepath}: {e}")

    return sessions_data


def main():
    """Main extraction routine."""
    print(f"\n=== Full Extraction Script v{SCRIPT_VERSION} ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Attempt direct tool calls first (only works in agent session context)
    print("\n1. Attempting direct tool access...")
    sessions_data, memory_data = try_direct_tool_call()
    
    has_tools = bool(sessions_data or memory_data)
    
    if not has_tools:
        # Fallback: read from exported JSONL files on disk
        print("\n2. No tools available (cron/standalone mode). Reading exported files...")
        sessions_data = read_exported_files()
        
        if not sessions_data and not memory_data:
            print("\n  ℹ No session data found on disk either.")
            print("  ℹ This is expected for fresh installations or before any exports run.")
    
    # Write to today's file
    today = datetime.now().strftime('%Y%m%d')
    file_path = os.path.join(chat_history_dir, f"{today}.jsonl")
    
    with open(file_path, 'a', encoding='utf-8') as f:
        for s in sessions_data:
            record = {
                "type": "session_full" if full_extraction else "session_summary",
                "version": SCRIPT_VERSION,
                **s
            }
            # Clean up empty values
            record = {k: v for k, v in record.items() 
                     if not (isinstance(v, str) and not v.strip())}
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        for m in memory_data:
            record = {"type": "memory_entry", "version": SCRIPT_VERSION, **m}
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    total = len(sessions_data) + len(memory_data)
    
    if total == 0:
        # Write a marker so we know this export ran successfully
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                "type": "export_marker",
                "version": SCRIPT_VERSION,
                "timestamp": datetime.now().isoformat(),
                "note": "Export ran but no data available in this environment"
            }, ensure_ascii=False) + '\n')
    
    # Create full archive if requested and we have data
    if full_extraction and sessions_data:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Workspace archive with timestamp
        ws_archive_path = os.path.join(workspace_path, f"{timestamp}_full.jsonl")
        with open(ws_archive_path, 'w', encoding='utf-8') as f:
            for s in sessions_data:
                record = {"type": "session_full", "version": SCRIPT_VERSION, **s}
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        print(f"\n  ✓ Workspace archive: {ws_archive_path}")

    # Summary
    print(f"\n=== EXTRACTION COMPLETE ===")
    print(f"Sessions found: {len(sessions_data)}")
    print(f"Memory entries found: {len(memory_data)}")
    if has_tools:
        print("  (via direct Hermes Agent tool calls)")
    else:
        print("  (from exported JSONL files on disk or empty - no prior exports)")
    print(f"Output file: {file_path}")

    return 0


if __name__ == "__main__":
    main()
