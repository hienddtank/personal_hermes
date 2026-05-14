#!/bin/bash
# Pre-start cleanup: kill stale Telegram getUpdates connections.
# Usage: run BEFORE starting the Telegram gateway process.
# Works with both long-polling and webhook modes.

set -euo pipefail
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
if [ -z "$TOKEN" ]; then
  echo "[cleanup] TELEGRAM_BOT_TOKEN not set — skipping." >&2
  exit 0
fi

BASE="https://api.telegram.org/bot$TOKEN"

echo "[cleanup] Starting at $(date +%H:%M:%S)" >&2

# Step 1: setWebhook with dummy URL + drop_pending_updates
# This forcibly terminates ALL active long-polling (getUpdates) sessions.
curl -sf "$BASE/setWebhook" \
  -d "url=https://httpbin.org/status/204" \
  -d "drop_pending_updates=true" >/dev/null 2>&1 || true

sleep 1

# Step 2: deleteWebhook — restores long-polling mode (no webhook)
curl -sf "$BASE/deleteWebhook" \
  -d "drop_pending_updates=true" >/dev/null 2>&1 || true

echo "[cleanup] Done." >&2
