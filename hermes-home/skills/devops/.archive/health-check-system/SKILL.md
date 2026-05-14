---
name: health-check-system
description: Diagnostic playbook for the Hermes Agent health check cron job (health_push.py) — endpoint probes, Telegram push, breadcrumb monitoring, and known script bugs.
tags: [devops, health-check, cron, diagnostics, telegram]
related_skills: [docker-restart, cron-workflow-design]
---

# Health Check System

Diagnostic playbook for the Hermes Agent health check cron job (`/workspace/scripts/health_push.py`).

## Trigger Conditions
- Running or troubleshooting the health check cron job
- Forwarder (port 8768) or Gateway (port 8642) failures
- Telegram push failures from the health check
- Breadcrumb pending/unverified states

## Health Check Script Overview

The script at `/workspace/scripts/health_push.py` performs:
1. **Breadcrumb scan** — reads `/workspace/.breadcrumbs/*.md` for recent activity
2. **Endpoint probes** — curls Gateway (`:8642/health`) and Forwarder (`:8768/`)
3. **Telegram push** — posts results to Telegram chat `6730547288`
4. **Local log** — saves to `/workspace/.breadcrumbs/health-check-latest.md`

## Known Bugs in the Script (FIX THESE BEFORE TRUSTING OUTPUT)

### Bug 1: Redacted TELEGRAM_TOKEN_ENV (Line 12)
```python
TELEGRAM_TOKEN_ENV = "TELEGR...OKEN"  # WRONG — redacted placeholder
```
Should be:
```python
TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
```
**Impact:** `os.environ.get()` never finds the token because the literal key `"TELEGR...OKEN"` doesn't exist in any environment. Every run prints `[SKIP] No TELEGRAM_BOT_TOKEN found` regardless of whether the real env var is set.

### Bug 2: Broken String Literal (Line 102)
```python
if line.startswith("TELEGRAM_BOT_TOKEN=***   # unclosed quote — syntax error
```
The `.env` fallback path is unreachable due to this syntax error. Even if fixed, the fallback reads `/opt/hermes-agent/.env` which doesn't exist on this system.

### Bug 3: TELEGRAM_BOT_TOKEN Not in Cron Environment
The `TELEGRAM_BOT_TOKEN` env var is not set in the cron execution context. The token may exist in the gateway container's env but doesn't propagate to the cron job's environment.

**Fixes (in order of priority):**
1. Patch line 12: `TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"`
2. Patch line 102: fix the unclosed quote
3. Point the fallback `.env` path to `~/.hermes/.env` or `/hermes-home/.env` instead of `/opt/hermes-agent/.env`
4. Set `TELEGRAM_BOT_TOKEN` in the cron environment (check cron job configuration)

## Cron Auto-Delivery (Telegram)
When the cron job is configured to deliver to a Telegram chat, the system **auto-delivers** the agent's final response. Do NOT use `send_message` to the same target — you'll get `cron_auto_delivery_duplicate_target`. Just put your message content in your final response.

## Forwarder / Tunnel Check

The script `~/.hermes/scripts/check-forwarders.sh` does **not** exist on this system. To check for active forwarders, tunnels, or background servers, use the commands below or the reusable script at `scripts/check-forwarders.sh` (linked under this skill).

### What to check
- **ngrok** — `which ngrok` (not installed on this system as of 2026-05-06)
- **cloudflared / localtunnel / frp** — `which cloudflared localtunnel frp` (none installed)
- **Listening ports** — `cat /proc/net/tcp` (parse state `0A` = LISTEN; ports in hex)
- **Background processes** — `ps aux | grep -E 'server|ngrok|tunnel|forward|flask|uvicorn|gunicorn|node|python.*\.py'`

### Common listening ports
| Port | Service |
|------|---------|
| 8642 | Hermes gateway |
| 8768 | Forwarder (local_forwarder.py / Codex) |
| 40501 (0x9E33) | WSL internal DNS (127.0.0.11) |

### Quick check (one-liner)
```bash
ps aux | grep -v grep | grep -cE 'ngrok|cloudflared|localtunnel|frp'  # 0 = none running
cat /proc/net/tcp | awk '$4=="0A"'                                    # listening sockets
```

## Quick Diagnostic Commands

```bash
# Run the health check
python3 /workspace/scripts/health_push.py

# Check endpoints manually
curl -sf --max-time 5 http://localhost:8642/health
curl -sf --max-time 5 http://localhost:8768/

# Check for TELEGRAM_BOT_TOKEN
env | grep TELEGRAM

# Check breadcrumb state
ls -lt /workspace/.breadcrumbs/*.md

# Check pending breadcrumbs
grep -ril 'pending\|unverified\|restart' /workspace/.breadcrumbs/

# Check script for syntax errors
python3 -c "import py_compile; py_compile.compile('/workspace/scripts/health_push.py', doraise=True)"
```

## Common Failure Modes

| Symptom | Likely Cause | Fix |
|---|---|---|
| Forwarder FAIL | Forwarder container not running or not yet started | `docker ps \| grep forwarder`, wait/restart |
| Gateway FAIL | Gateway crashed or port conflict | Check `gateway.log`, restart gateway |
| Telegram SKIPPED | Script bug #1 (redacted env var name) + missing env var | Patch script line 12, set TELEGRAM_BOT_TOKEN |
| Pending breadcrumbs | Previous restart/crash not verified | Review breadcrumb contents, resolve |

## Log Locations
- Latest health check: `/workspace/.breadcrumbs/health-check-latest.md`
- Breadcrumbs directory: `/workspace/.breadcrumbs/`
- Cron output archive: `/hermes-home/cron/output/`

## Important: Breadcrumb Path Convention
**ALWAYS use `/workspace/.breadcrumbs/`** — never `/hermes-home/.breadcrumbs/`.
- Interactive sessions write to `/workspace/`
- Cron sessions resolve `~` to `/hermes-home/` (different filesystem root!)
- The health check script uses `BREADCRUMB_DIR = Path("/workspace/.breadcrumbs")` which is correct
- If you see TWO `.breadcrumbs` directories, the cron breadcrumb was written to the wrong place
