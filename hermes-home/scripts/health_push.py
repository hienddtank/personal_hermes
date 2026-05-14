#!/usr/bin/env python3
"""Unified health check: breadcrumbs + endpoint checks → Telegram push."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BREADCRUMB_DIR = Path("/workspace/.breadcrumbs")
CHAT_ID = "6730547288"
TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"

# --- Step 1: Read breadcrumbs ---
breadcrumb_entries = []
if BREADCRUMB_DIR.exists():
    for f in sorted(BREADCRUMB_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        breadcrumb_entries.append({
            "name": f.name,
            "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        })

if not breadcrumb_entries:
    bc_summary = "none"
else:
    lines = []
    for entry in breadcrumb_entries[:5]:
        lines.append(f"  • {entry['name']} ({entry['mtime']})")
    bc_summary = "\n".join(lines)

# Check for pending/unverified breadcrumbs
has_pending = False
for f in BREADCRUMB_DIR.glob("*.md"):
    try:
        content = f.read_text().lower()
        if any(w in content for w in ["pending", "unverified", "restart"]):
            has_pending = True
            break
    except Exception:
        pass

# --- Step 2: Health endpoints ---
def check_endpoint(name, url):
    try:
        result = subprocess.run(
            ["curl", "-sf", "--max-time", "5", url],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return "OK", result.stdout.strip()
    except Exception as e:
        return "FAIL", str(e)
    return "FAIL", "no response"

gw_status, gw_body = check_endpoint("Gateway", "http://localhost:8642/health")
fd_status, fd_body = check_endpoint("Forwarder", "http://localhost:8768/")

# --- Step 3: Build message ---
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
alert = ""
if gw_status == "FAIL" or fd_status == "FAIL":
    alert += "\n\n⚠️ <b>Action needed</b> — endpoint(s) failed above."
if has_pending:
    alert += "\n⚠️ <b>Pending breadcrumbs</b> found — verify restart status."

msg = (
    f"🔍 <b>Hermes Health Check</b>\n"
    f"━━━━━━━━━━━━━━━━━━━\n\n"
    f"<b>📋 Breadcrumbs:</b>\n{bc_summary}\n\n"
    f"<b>🌐 Gateway:</b> {gw_status} ({gw_body})\n"
    f"<b>📡 Forwarder:</b> {fd_status} ({fd_body})\n\n"
    f"⏰ {timestamp}"
) + alert

# --- Step 4: Push to Telegram ---
token = os.environ.get(TELEGRAM_TOKEN_ENV, "")
if token:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
        }).encode()
        req = subprocess.run(
           ["curl", "-sf", "--max-time", "10", "-X", "POST",
             "-H", "Content-Type: application/json",
             "-d", data.decode(), url],
        capture_output=True, text=True, timeout=15
        )
        if req.returncode == 0:
            print("✅ Telegram push successful")
        else:
            print(f"[WARN] Telegram push failed: {req.stderr}")
    except Exception as e:
        print(f"[ERROR] Telegram push exception: {e}")
else:
    # Fallback: read from docker-compose env if available
    env_file = Path("/opt/hermes-agent/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip()
                break

if token and TELEGRAM_TOKEN_ENV not in os.environ:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
        }).encode()
        req = subprocess.run(
            ["curl", "-sf", "--max-time", "10", "-X", "POST",
             "-H", "Content-Type: application/json",
             "-d", data.decode(), url],
            capture_output=True, text=True, timeout=15
        )
        if req.returncode == 0:
            print("✅ Telegram push successful (via .env)")
        else:
            print(f"[WARN] Telegram push failed: {req.stderr}")
    except Exception as e:
        print(f"[ERROR] Telegram push exception: {e}")
elif not token:
    print("[SKIP] No TELEGRAM_BOT_TOKEN found — no Telegram message sent")

# --- Step 5: Save local log ---
BREADCRUMB_DIR.mkdir(parents=True, exist_ok=True)
log_path = BREADCRUMB_DIR / "health-check-latest.md"
log_content = (
    f"# Health Check Log\n\n"
    f"* Last checked: {timestamp}\n"
    f"* Gateway: {gw_status} | Forwarder: {fd_status}\n"
    f"* Breadcrumbs found: {len(breadcrumb_entries)}\n"
    f"* Pending items: {'yes' if has_pending else 'no'}\n\n"
    f"```{msg}```\n"
)
log_path.write_text(log_content)
print(f"✅ Local log saved to {log_path}")
