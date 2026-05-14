#!/usr/bin/env python3
"""
Full extraction script for Hermes session history.
Saves current sessions to chat_history directory.
"""

import os
from datetime import datetime
import json
import sys

def main():
    # Paths
    user_home = os.path.expanduser('~')
    chat_history_dir = os.path.join(user_home, '.hermes/chat_history')
    
    # Create directories if they don't exist
    os.makedirs(chat_history_dir, exist_ok=True)
    
    print(f"Saving session history to: {chat_history_dir}")
    
    # Check for full extraction mode
    full_extraction = "MANUAL_FULL_EXTRACT" in os.environ
    
    # Fetch sessions using hermes_tools.session_search
    try:
        from hermes_tools import session_search
        
        all_sessions_result = session_search()
        
        if all_sessions_result and 'sessions' in all_sessions_result:
            sessions_list = all_sessions_result['sessions']
            limit = len(sessions_list) if full_extraction else 10
            
            print(f"Found {len(sessions_list)} total sessions")
            
            for s in sessions_list[:limit]:
                session_id = s.get('id', 'unknown')
                title = s.get('title', 'No title')
                timestamp = s.get('timestamp', '')
                preview = s.get('preview', '')
                
                print(f"  - {session_id}: {title[:100]}...")
            
            # Save to file
            today = datetime.now().strftime('%Y%m%d')
            file_path = os.path.join(chat_history_dir, f"{today}.jsonl")
            
            with open(file_path, 'a') as f:
                for s in sessions_list[:limit]:
                    record = {
                        "type": "session_summary",
                        "id": s.get('id', 'unknown'),
                        "title": s.get('title', 'No title'),
                        "timestamp": s.get('timestamp', ''),
                        "preview": (s.get('preview', '')[:500] if s.get('preview') else '')
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            
            print(f"\n✓ Saved session summaries to: {file_path}")
        else:
            print("Warning: Unexpected response format from session_search")
            return 1
            
    except ImportError as e:
        print(f"Error: Cannot import hermes_tools. Is Hermes installed?")
        print(f"Details: {e}")
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 3
    
    # If full extraction mode, also create a comprehensive archive
    if full_extraction and 'sessions' in locals():
        archive_path = os.path.join(chat_history_dir, f"{today}_full_archive.jsonl")
        
        with open(archive_path, 'w') as f:
            for s in sessions_list:
                record = {
                    "type": "session_full",
                    **s
                }
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        print(f"✓ Full extraction also saved to: {archive_path}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())