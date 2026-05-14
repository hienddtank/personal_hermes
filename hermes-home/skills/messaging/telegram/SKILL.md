---
name: telegram
description: Interact with Telegram via the bot API for messaging, voice messages, and scheduled task delivery.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
prerequisites: []
env_vars: [TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS]
metadata:
  hermes:
    tags: [telegram, messaging, bot-api]
---

# Telegram Skill for Hermes Agent

## Overview
This skill enables communication with users via Telegram using a bot API. The agent can send and receive messages, handle voice messages (auto-transcribed), and work in group chats.

## Configuration
- **Bot Token**: `8636918388:AAHzKKjdK5o-wJBM7HYCcViUkIcAjyslU9U`
- **Allowed User ID**: `6730547288`
- **Bot Username**: `@Hermes39528u1_Bot`

## Capabilities
- Send and receive text messages
- Handle voice messages (auto-transcribed)
- Work in group chats
- Receive scheduled task results via cronjobs
- Forward important information to users

## Usage
This skill is automatically loaded when needed for Telegram communication. The agent can:
- Respond to user messages
- Initiate conversations
- Execute commands sent via Telegram
- Send scheduled notifications and task results

## Sending Files

### Critical: Sandbox Reset
The Python sandbox (`execute_code`) is fully reset between calls — pip packages do NOT persist. When sending a file via Telegram from Python, **all steps must happen in ONE execute_code call**: import pandas/openpyxl, read the file, build the message, call the Telegram API. Splitting across multiple calls means pandas will be missing on the second call and you'll have to reinstall each time.

### Recommended: Use curl for files on disk
For files already saved on disk (Excel, PDFs, images), prefer `curl` over Python — it avoids the sandbox reset issue entirely:

```bash
curl -s -F document="@/path/to/file.xlsx" \
  "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendDocument?chat_id=6730547288"
```

This works for any file type: `.xlsx`, `.pdf`, `.png`, `.mp3`, etc. Telegram will auto-detect the MIME type. For captions: add `-F caption="your message here"`.

### Inline alternative when tunneling fails
If no tunneling tools are available (ngrok, cloudflared, localtunnel not installed in container), fall back to displaying file contents inline rather than trying to create a download link. The user can also access files directly via their Windows path (e.g. `D:\mkt\python\B2B cleaning 2\ILTM_2026\IG.xlsx`).

## Security
The bot token should be kept secure. Only the specified user ID (6730547288) is allowed to interact with this bot. The token can be used by anyone to control your bot, so store it safely in `~/.hermes/.env`.

## Cronjob Delivery
Telegram can be used as a delivery target for cronjobs:
```bash
deliver=telegram  # or telegram:<chat_id>:<thread_id> for Telegram topics
```

Example: `telegram:-1001234567890:17585`

## Auto-Response Polling
To enable automatic response to new messages (polls every 5 seconds), use this cronjob:
```bash
cronjob action=create prompt="Check for new Telegram messages and respond to them" schedule="*/5 * * * *" deliver=telegram
```

This will spawn a subagent that continuously polls for new messages and responds to them.

## Troubleshooting: Outage Diagnosis

### Symptoms
- Bot appears online (gateway process running) but no user messages received
- No inbound message entries in gateway.log despite active cron jobs
- Gateway restarts with "Polling conflict" or reconnect errors

### Critical Failure Pattern: getUpdates Conflict
Error message: `Conflict: terminated by other getUpdates request; make sure that only one bot instance is running`

This occurs when two processes poll the same bot token simultaneously. The gateway enters a **permanent silent failure state** — it keeps running but never receives new messages again until restarted. Recovery requires:
1. Identifying and stopping the conflicting process (check for duplicate containers, old deployments, or another agent instance)
2. Restarting the gateway

### Diagnostic Steps
1. **Check session files exist**: `ls /hermes-home/sessions/ | grep <date>` — if no sessions on a date but cron jobs ran, Telegram connection was down
2. **Check gateway.log for Telegram errors**: `grep "2026-05-0X" /hermes-home/logs/gateway.log | grep -iE "telegram|polling|conflict|disconnect"`
3. **Verify last successful inbound message timestamp** vs. current time — gap indicates outage duration
4. **Check for duplicate bot instances**: `docker ps | grep -i telegram` or `ps aux | grep bot`

### Prevention & Auto-Recovery
- **Never run two processes** with the same TELEGRAM_BOT_TOKEN
- **Auto-recovery on restart**: The docker entrypoint/docker-compose command runs a pre-start cleanup that calls `setWebhook(url=dummy, drop_pending_updates=true)` followed by `deleteWebhook(drop_pending_updates=true)`. This forces Telegram to kill ALL stale getUpdates sessions and restore clean long-polling mode. See `scripts/telegram-cleanup.sh` for the standalone version.
- Monitor gateway.log for "polling conflict" warnings — treat as urgent (silent failure mode)
- If manual fix needed, run: `curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook -d 'url=https://httpbin.org/status/204&drop_pending_updates=true' && curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook -d 'drop_pending_updates=true'`

## Building Custom AI Chat Bots

### Telegram AI Chat Bridge
To build a custom Telegram bot that bridges users to an AI backend:

1. **Get a Bot Token**: Search `@BotFather` → `/newbot` → follow prompts
2. **Set env vars**: `TELEGRAM_BOT_TOKEN`, optionally `TELEGRAM_ALLOWED_USERS`
3. **Bot features**: Message forwarding, conversation memory, inline keyboards, async processing
4. **Deployment**: Docker, Heroku, Railway, or VPS with systemd

```bash
# Quick start
python simplified_bot.py  # Minimal version
python extended_bot.py     # Full features (inline keyboards, access control)
```

### Configuration
| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Token from @BotFather |
| `HERMES_API_URL` | No | AI API endpoint |
| `HERMES_API_KEY` | No | API auth key |
| `TELEGRAM_ALLOWED_USERS` | No | Comma-separated user IDs |

### Deployment
```bash
docker build -t hermes-telegram-bridge .
docker run -e TELEGRAM_BOT_TOKEN="***" hermes-telegram-bridge
```

See `references/ai-chat-bridge.md` for the complete implementation guide.