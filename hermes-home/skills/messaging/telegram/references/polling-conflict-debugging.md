# Telegram Polling Conflict — Debugging & Recovery

## Problem
Bot appears online but no user messages received. Gateway.log shows:
```
[Telegram] Telegram polling conflict (1/3), will retry in 10s. Error: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
[Telegram] Fallback IP 149.154.167.220 failed
[Telegram] Telegram polling retry failed: Timed out
```

After this, **zero inbound messages** until manual intervention. The gateway stays running but enters a permanent silent failure state.

## Root Cause
Telegram Bot API allows only ONE active `getUpdates` session per bot token. When a second connection appears (stale process, duplicate container, mid-restart overlap), Telegram kills the older session and notifies it with a "conflict" error. If recovery fails (network issues, insufficient retries), the gateway gives up permanently.

## Investigation Procedure

### 1. Check for sessions on the missing dates
```bash
ls /hermes-home/sessions/ | grep "2026050[23]"  # date pattern
```
- Only cron sessions → Telegram was down during that window
- No sessions at all → system was not running

### 2. Check gateway.log for the last Telegram activity
```bash
grep "2026-05-0X" /hermes-home/logs/gateway.log | grep -iE "telegram|polling|conflict|disconnect|inbound"
```
- Last inbound message timestamp vs current time = outage duration
- "Polling conflict" error = exact failure point

### 3. Check agent.log for related errors
```bash
grep "2026-05-0X" /hermes-home/logs/agent.log | grep -iE "timeout|error|fail"
```

### 4. Verify no duplicate bot instances
```bash
# Docker host:
docker ps | grep -i hermes
ps aux | grep -E "bot|telegram|getUpdates"
```

## Recovery

### Automatic (on container restart)
The docker-compose command runs this before `hermes gateway run`:
```bash
curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook \
  -d 'url=https://httpbin.org/status/204&drop_pending_updates=true' && \
sleep 1 && \
curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook \
  -d 'drop_pending_updates=true'
```

### Manual (standalone)
Run `~/.hermes/scripts/telegram-cleanup.sh` or the curl one-liner above. Then restart the gateway:
```bash
docker compose restart gateway
```

## Why setWebhook then deleteWebhook?
1. `setWebhook(url=dummy, drop_pending_updates=true)` → Telegram kills ALL active getUpdates sessions and clears pending messages
2. `deleteWebhook(drop_pending_updates=true)` → removes the webhook, leaving no connection active
3. After both steps, Telegram has zero state — fresh long-polling starts without conflict

The dummy URL (`https://httpbin.org/status/204`) is harmless; it's never actually used to receive messages.

## Prevention
- Single process per bot token (docker-compose `restart: unless-stopped` handles most cases)
- Pre-start cleanup on every container start (now in docker-compose.yml + entrypoint.sh)
- Monitor gateway.log for "polling conflict" warnings — they indicate an emerging problem
