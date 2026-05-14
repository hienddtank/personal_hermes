#!/usr/bin/env python3
"""
Watchdog script — runs on Windows host, completely outside Docker.
Pings Hermes agent and auto-recovers if dead.

Usage: watchdog.py [ping|check|restart]
"""

import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path


# --- Config ---
HERMES_URL = "http://localhost:8768/health"
DOCKER_CONTAINER_NAME = "hermes-agent"  # adjust if different
LOG_FILE = Path(__file__).parent.parent / "logs" / "watchdog.log"
RESTART_SCRIPT = r"D:\mkt\python\hermes\workspace\scripts\docker-restart.ps1"


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def ping_healthy() -> bool:
    """Check if Hermes is responding."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10", HERMES_URL],
            capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0 and "healthy" in result.stdout.lower()
    except Exception as e:
        log(f"Ping failed: {e}")
        return False


def restart_hermes():
    """Restart Hermes via the existing restart script."""
    log("⚠️ Hermes unresponsive — restarting...")
    try:
        # Try PowerShell script first
        if Path(RESTART_SCRIPT).exists():
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", RESTART_SCRIPT],
                timeout=120
            )
            log("✅ Restart triggered via docker-restart.ps1")
        else:
            # Fallback: docker restart
            subprocess.run(["docker", "restart", DOCKER_CONTAINER_NAME], timeout=30)
            log(f"✅ Restart triggered via docker restart {DOCKER_CONTAINER_NAME}")
    except Exception as e:
        log(f"❌ Restart failed: {e}")


def run_ping(count: int = 1):
    """Send ping count times with 1 min interval (for testing)."""
    for i in range(1, count + 1):
        healthy = ping_healthy()
        status = "✅" if healthy else "❌ DEAD"
        log(f"Ping {i}/{count}: Hermes is {status}")
        if i < count:
            time.sleep(60)


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "check"

    if action == "ping":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        run_ping(count)
    elif action == "check":
        healthy = ping_healthy()
        if healthy:
            log("✅ Hermes is healthy")
        else:
            log("❌ Hermes is unresponsive!")
            restart_hermes()
    elif action == "restart":
        restart_hermes()
    else:
        print(f"Usage: watchdog.py [ping|check|restart]")
        sys.exit(1)


if __name__ == "__main__":
    main()
