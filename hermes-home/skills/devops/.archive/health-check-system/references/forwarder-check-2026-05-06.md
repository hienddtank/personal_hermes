# Forwarder Check — Session Notes (2026-05-06)

## Context
Cron job asked to run `~/.hermes/scripts/check-forwarders.sh` to check background servers/ngrok. Script does not exist.

## System State (2026-05-06, 19:42)
- **ngrok**: Not installed
- **cloudflared/localtunnel/frp**: Not installed
- **Listening ports**: 8642 (Hermes gateway), 40501 (WSL DNS)
- **Background process**: `python -m evolution.trainer` (PID 11463, 106% CPU, running since 18:31)

## Discovery Notes
- `ss` and `netstat` not available; used `/proc/net/tcp` instead (state `0A` = LISTEN, ports in hex)
- Cron auto-delivery to Telegram: `send_message` to the same target returns `cron_auto_delivery_duplicate_target`. Final response is auto-delivered.
- `ps aux` was initially flagged as "long-lived server process" by the command runner — had to run without grep filters to avoid the false positive.

## Created
- `scripts/check-forwarders.sh` — reusable forwarder-checking script under this skill
