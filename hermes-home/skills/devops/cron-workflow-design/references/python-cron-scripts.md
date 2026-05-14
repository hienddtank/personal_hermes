# Python Cron Scripts — Guidelines for Hermes Agent

Cron scripts in Python must follow specific constraints because they run as standalone subprocesses without the Hermes agent runtime.

## Constraints

1. **No `hermes_tools` imports** — Only stdlib: `json`, `os`, `datetime`, `pathlib`, `subprocess`, `sys`
2. **No inline curl in cron prompts** — The cron job's `prompt` field blocks curl-like patterns (threat detection). Write logic into a `.py` script, reference via `script` field.
3. **`curl` (not `curl.exe`)** — The container runs on Linux (WSL) and has `/usr/bin/curl`. `curl.exe` does NOT exist in the container and will fail with `[Errno 2] No such file or directory`. Always use `subprocess.run(["curl", ...])`.
4. **TELEGRAM_BOT_TOKEN** may not be in env vars when running as standalone script. Read from `.env` file as fallback:
   ```python
   token = os.environ.get("TELEGRAM_BOT_TOKEN")
   if not token:
       env_file = Path("/opt/hermes-agent/.env")
       for line in env_file.read_text().splitlines():
           if line.startswith("TELEGRAM_BOT_TOKEN="):
               token = line.split("=", 1)[1].strip()
               break
   ```

## Template: Telegram Push Script

```python
#!/usr/bin/env python3
"""[Brief description of what this script does.]"""
import json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

CHAT_ID = "6730547288"  # User's Telegram chat ID

# PATH CONVENTION (since 2026-05-04):
# - This script MUST live at: /hermes-home/scripts/<name>.py
# - Breadcrumbs/state go to: /workspace/.breadcrumbs/
# - Never use ~ or relative paths in cron context

def get_bot_token():
    """Get bot token from env or .env fallback."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        env_file = Path("/opt/hermes-agent/.env")
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break
    return token

def push_telegram(token, message):
    """Send HTML-formatted message via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"})
    result = subprocess.run(
        ["curl.exe", "-sf", "--max-time", "10", "-X", "POST",
         "-H", "Content-Type: application/json",
         "-d", data, url],
        capture_output=True, text=True, timeout=15
    )
    return result.returncode == 0

def main():
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # --- Gather data here (stdlib-only) ---
    status_line = "Gathering health data..."
    
    # --- Build message ---
    msg = f"🔍 <b>Health Check</b>\n{timestamp}\n\n{status_line}"
    
    # --- Push to Telegram ---
    token = get_bot_token()
    if token:
        ok = push_telegram(token, msg)
        print("✅ Pushed" if ok else "❌ Push failed")
    else:
        print("[SKIP] No bot token — Telegram not sent")
    
    # --- Save local state ---
    log_dir = Path("/workspace/.breadcrumbs/")  # Breadcrumbs go to /workspace/, NOT /hermes-home/
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "health-check-latest.md").write_text(
        f"# Health Check\n* {timestamp}\n{msg}\n"
    )

if __name__ == "__main__":
    main()
```

## Testing Checklist

1. `python3 /hermes-home/scripts/<scriptname>.py` — runs without errors in interactive session
2. Verify the script is at `/hermes-home/scripts/<scriptname>.py` (cron will find it here)
3. Check that `/workspace/.breadcrumbs/health-check-latest.md` was created with correct content
4. Verify Telegram message arrives (if token available)
5. Then create cron job referencing it:
   ```json
   {
     "script": "<scriptname>.py",
     "prompt": "Run the script at /hermes-home/scripts/<scriptname>.py and report results.",
     "schedule": "every 4h",
     "deliver": "origin"
   }
   ```

## Common Gotchas

- `grep '---'` fails because `---` starts with dash (interpreted as option). Use `grep -- '---'` or `subprocess.run(["grep", "--", "---", ...])`.
- `curl.exe` must be used, not internal curl function. The system aliases `curl` to an internal tool that conflicts with the Windows subsystem command.
- Always use absolute paths (`/workspace/.breadcrumbs/`, `/workspace/scripts/`) — relative or `~` paths resolve differently in cron context.