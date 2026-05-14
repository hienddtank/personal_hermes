# Investigation from 2026-05-04 — May 2-3 Telegram Outage

## Timeline
- **Apr 29 ~11:40** — Last successful inbound message via Telegram (`"i gave you the wrong email list..."`)
- **Apr 29 ~10:56–11:40** — Multiple temporary "Server disconnected without sending a response" errors, all recovered within seconds
- **May 01 ~14:56** — `Conflict: terminated by other getUpdates request` error. Fallback IP failed. Polling retry timed out. No recovery.
- **May 02–03** — Zero inbound messages. Only cron jobs executed. Gateway.log had no Telegram entries.
- **May 04 01:19** — SIGTERM shutdown of gateway process (first restart since the conflict)
- **May 04 01:43** — Gateway restarted, polling conflict resolved via manual intervention

## What Was Found in Logs
- `/hermes-home/logs/gateway.log`: Conflict at May 1 14:56, no subsequent Telegram activity until restart on May 4
- `/hermes-home/logs/agent.log`: Only session summarization timeout errors (from cron jobs), no Telegram-related entries during the outage window
- `/hermes-home/logs/errors.log`: Same timeout errors, no additional failures
- Session files in `/hermes-home/sessions/`: 34 cron sessions on May 2, 40+ on May 3 — all `cron_` prefixed. Zero non-cron (user-initiated) sessions on either date

## Key Discovery
The gateway's Telegram retry logic had only 3 attempts before giving up. The conflict error triggered a reconnect attempt that failed due to a fallback IP timeout, and the gateway never retried after that. This meant the outage persisted for ~2.5 days without any recovery.

## Fix Applied
Added pre-start cleanup (setWebhook → deleteWebhook) to docker-compose.yml command and entrypoint.sh. Also increased diagnostic visibility by adding structured investigation steps in the telegram skill.
