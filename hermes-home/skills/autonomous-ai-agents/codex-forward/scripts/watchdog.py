#!/usr/bin/env python3
"""
Hermes Container Watchdog — runs on Windows host via Scheduled Task.
Pings the Codex Forwarder; if down, triggers container recreate with health wait.

Usage (Windows):
    python watchdog.py          # Run once as check
    python watchdog.py --recreate  # Force recreate for testing

Run from: C:\Users\<user>\AppData\Roaming\Python\Python3xx\ or any Windows path
NOT inside Docker — must survive container crashes.
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone

FORWARDER_URL = "http://127.0.0.1:8768"
HERMES_HEALTH = "http://127.0.0.1:8642/health"
LOG_FILE = r"D:\mkt\python\hermes\logs\watchdog.log"
RETRY_COUNT = 3
RETRY_DELAY = 5  # seconds between retries

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def ping_forwarder():
    """Check if forwarder is alive. Returns True/False."""
    for i in range(RETRY_COUNT):
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "10", f"{FORWARDER_URL}/health"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("ok", False), data
        except Exception as e:
            log(f"  Retry {i+1}/{RETRY_COUNT} failed: {e}")
            time.sleep(RETRY_DELAY)
    return False, {}

def trigger_recreate():
    """Trigger container recreate with health wait and Telegram notify."""
    payload = json.dumps({
        "wait_for_url": HERMES_HEALTH,
        "notify": {"telegram": True}
    })
    log("Triggering container recreate...")
    result = subprocess.run(
        ["curl", "-s", "--max-time", "300",
         "-X", "POST",
         f"{FORWARDER_URL}/services/hermes/recreate",
         "-H", "Content-Type: application/json",
         "-d", payload],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log("Recreate request sent (forwarder will handle wait/notify)")
        return True
    else:
        log(f"Recreate failed: {result.stdout[:500]}")
        return False

def main():
    log("=" * 60)
    force_recreate = "--recreate" in sys.argv

    if force_recreate:
        log("FORCED RECREATE mode")
        trigger_recreate()
        return

    # Normal check: ping forwarder
    alive, health_data = ping_forwarder()

    if alive:
        log(f"Forwarder healthy — uptime check passed")
        compose_ok = health_data.get("compose", {}).get("discovery_ok", False)
        services = health_data.get("compose", {}).get("service_count", 0)
        log(f"  Compose OK: {compose_ok}, Services: {services}")

        # Optional: also check if Hermes agent itself is reachable
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "5", HERMES_HEALTH],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                agent_ok = data.get("ok", False)
                log(f"  Hermes agent reachable: {agent_ok}")
            else:
                log(f"  Hermes agent not responding at {HERMES_HEALTH} (HTTP {result.returncode})")
        except Exception as e:
            log(f"  Hermes agent health check failed: {e}")
    else:
        log("Forwarder UNREACHABLE — triggering recreate...")
        trigger_recreate()

if __name__ == "__main__":
    main()
