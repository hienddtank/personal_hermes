#!/usr/bin/env python3
"""Check email hunter progress. Run as cron script."""
import csv
import os
import subprocess
from pathlib import Path

CSV = Path("/host/d/mkt/python/hermes/workspace/fish_profs/korea_materials_professors.csv")
LOG = Path("/host/d/mkt/python/hermes/workspace/fish_profs/email_hunt.log")

def main():
    # Check if script is running
    result = subprocess.run(['pgrep', '-f', 'batch_email_hunter'], capture_output=True, text=True)
    running = bool(result.stdout.strip())
    
    # Count emails
    with open(CSV, 'r') as f:
        rows = list(csv.DictReader(f))
    
    total = len(rows)
    with_emails = sum(1 for r in rows if r.get('email') and '@' in r['email'])
    without = total - with_emails
    
    # Count recent finds from log
    recent = 0
    if LOG.exists():
        with open(LOG, 'r') as f:
            recent = f.read().count('✓')
    
    status = "🟢 RUNNING" if running else "🔴 STOPPED"
    pct = (with_emails / total * 100) if total else 0
    
    lines = [
        f"📧 Korea Professors — Email Hunt",
        f"",
        f"{status}",
        f"Progress: {with_emails}/{total} ({pct:.1f}%)",
        f"Remaining: {without}",
        f"Found this session: {recent}",
        f"",
        f"Script: {'active' if running else 'idle (cron will restart)'}",
    ]
    
    if not running:
        lines.append("")
        lines.append("💡 Tip: Run manually with:")
        lines.append("`cd fish_profs && python3 batch_email_hunter.py`")
    
    print("\n".join(lines))

if __name__ == "__main__":
    main()
