#!/usr/bin/env python3
"""Pre-start cleanup: kill stale Telegram getUpdates connections and reset state.
Called from docker-compose command before 'hermes gateway run'."""

import os, sys, json, time, urllib.request, urllib.error

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
BASE = f"https://api.telegram.org/bot{TOKEN}"

def api(method, params=None):
    url = f"{BASE}/{method}"
    payload = json.dumps({k:v for k,v in (params or {}).items() if v is not None}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  API error {e.code}: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Request error: {e}", file=sys.stderr)
        return None

def main():
    if not TOKEN:
        return
    print(f"[cleanup] Starting at {time.strftime('%H:%M:%S')}", flush=True)
    api("setWebhook", {"url": "https://httpbin.org/status/204", "drop_pending_updates": True})
    time.sleep(1)
    api("deleteWebhook", {"drop_pending_updates": True})
    print("[cleanup] Done.", flush=True)

if __name__ == "__main__":
    main()
