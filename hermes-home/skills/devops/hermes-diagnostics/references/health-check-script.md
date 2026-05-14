# Health Check Script — health_push.py

## Locations (TWO copies — keep in sync)
- `/hermes-home/scripts/health_push.py` — canonical copy
- `/workspace/scripts/health_push.py` — workspace copy

## What It Does
1. **Reads breadcrumbs** from `/workspace/.breadcrumbs/*.md` — lists up to 5 most recent, flags items containing `pending`, `unverified`, or `restart`
2. **Checks endpoints** — Gateway (`localhost:8642/health`) and Forwarder (`localhost:8768/`)
3. **Pushes to Telegram** if `TELEGRAM_BOT_TOKEN` env var is set (fallback: `/opt/hermes-agent/.env`)
4. **Saves local log** to `/workspace/.breadcrumbs/health-check-latest.md`

## Current Script State (as of 2026-05-07)
- **Env var name is correct**: `TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"` — properly looks up the right env var
- **Syntax is clean**: Python script passes `ast.parse()` without errors
- **No `curl.exe` references**: The script uses `curl` (Linux binary), not `curl.exe` (Windows)
- **Two copies still exist**: `/hermes-home/scripts/` and `/workspace/scripts/` — keep them in sync

## Real Failure Mode: Missing TELEGRAM_BOT_TOKEN in Runtime Environment

The script correctly looks for `TELEGRAM_BOT_TOKEN` in `os.environ`, then falls back to `/opt/hermes-agent/.env`. However:

| Checkpoint | Result (current) | 
|------------|-------------------|
| `TELEGRAM_BOT_TOKEN` in env | ❌ Not set in cron/terminal context |
| `/opt/hermes-agent/.env` | ❌ File does not exist |
| `~/.hermes/.env` | ❌ File does not exist |
| Gateway env (Docker) | ✅ Token set there, but doesn't propagate to cron |

**The token exists in the gateway's runtime (Docker container env or similar) but is not available to scripts running outside that context.**

## Running the Health Check

```bash
# From workspace (recommended during interactive sessions)
cd /workspace && python scripts/health_push.py

# From hermes-home
python3 /hermes-home/scripts/health_push.py
```

## Interpreting Output

| Output Line | Meaning |
|-------------|---------|
| `✅ Telegram push successful` | Token was found, message delivered |
| `[WARN] Telegram push failed: ...` | Token found but API rejected it (check token/chat_id) |
| `[SKIP] No TELEGRAM_BOT_TOKEN found` | Token not available — set env var or .env file |
| `✅ Local log saved to ...` | `/workspace/.breadcrumbs/health-check-latest.md` written |

## Breadcrumb Analysis Workflow

When the health check reports "Pending breadcrumbs found", investigate with:

```bash
# Find which breadcrumbs contain pending/unverified/restart keywords
grep -ril 'pending\|unverified\|restart' /workspace/.breadcrumbs/

# Read their content
cat /workspace/.breadcrumbs/<filename>.md

# Common patterns:
# - PENDING_RESTART: docker-compose.yml modified, container needs recreation
# - PENDING: self-restart after config change, needs verification
# - Action items listed in each breadcrumb tell you what to verify
```
