# Telegram Polling Conflict Cleanup Pattern

## Problem
When Hermes gateway crashes without graceful shutdown, stale `getUpdates` connections persist. On restart, a second polling instance triggers Telegram's single-connection rule: `Conflict: terminated by other getUpdates request`. Gateway fails silently until manually restarted — outage lasts 1-3 days.

## Fix: Pre-start cleanup hook
Force Telegram to terminate all active polls before gateway starts. Run this **before** `hermes gateway run`:

```bash
# Using curl (already in container, no Python needed):
curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook \
  -d 'url=https://httpbin.org/status/204&drop_pending_updates=true' >/dev/null 2>&1
sleep 1
curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook \
  -d 'drop_pending_updates=true' >/dev/null 2>&1
```

**How it works:** `setWebhook` with a dummy URL forces Telegram to kill ALL existing long-polling connections. `deleteWebhook` (with 1s delay) restores long-polling mode. The second call clears the webhook, so the gateway falls back to polling normally.

## Where to place it
- **docker-compose.yml** command field — takes priority over entrypoint, ideal for immediate effect
- **entrypoint.sh** — as a fallback for direct `hermes gateway run` invocations

## docker-compose.yml example
```yaml
gateway:
  environment:
    - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
  command: ["sh", "-c", "if [ -n \"$TELEGRAM_BOT_TOKEN\" ]; then curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook -d 'url=https://httpbin.org/status/204&drop_pending_updates=true' >/dev/null 2>&1 && sleep 1 && curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook -d 'drop_pending_updates=true' >/dev/null 2>&1; fi && exec hermes gateway run"]
```

## Verification
After restart, check logs for clean start: no "Conflict" errors in the first 60 seconds. Monitor inbound messages — they should flow immediately.
