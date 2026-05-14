---
name: hermes-diagnostics
description: Systematic troubleshooting for Hermes Agent operational issues — diagnose outages, connection failures, session gaps, and platform delivery problems. Covers gateway logs, session verification, cron job analysis, and Telegram/API failure modes.
version: 1.0.0
category: devops
tags: [diagnostics, troubleshooting, gateway, sessions, outage]
---

## Health Check System (health_push.py)

Diagnostic playbook for the Hermes Agent health check cron job.

### Script Locations (TWO copies — keep in sync)
- `/hermes-home/scripts/health_push.py` — canonical copy (hermes-home managed)
- `/workspace/scripts/health_push.py` — workspace copy (may be independently modified)

**Pitfall**: Always check which copy the cron job is actually invoking. Cron jobs have historically referenced wrong paths (e.g., `/hermes-home/scripts/health-push.sh` — a non-existent shell script name instead of the actual Python script).

### What the Script Does
1. **Breadcrumb scan** — reads `/workspace/.breadcrumbs/*.md` for recent activity
2. **Endpoint probes** — curls Gateway (`:8642/health`) and Forwarder (`:8768/`)
3. **Telegram push** — posts results to configured chat
4. **Local log** — saves to `/workspace/.breadcrumbs/health-check-latest.md`

### Common Failure Modes (Not Script Bugs)

**Note on prior "bug" reports**: Earlier versions of this skill described syntax errors and redacted env var names in `health_push.py`. As of the current script, those are **not present** — the env var name at line 12 (`TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"`) is correct, and line 102's string is properly terminated. The `TELEGR...OKEN` display came from read_file's token-redaction logic, not the actual file. The real blockers are environment-level, not script-level.

**Failure 1: TELEGRAM_BOT_TOKEN Not in Runtime Environment**
The script requires `TELEGRAM_BOT_TOKEN` set in the environment. Common causes of missing token:
- Cron jobs run with a minimal environment — token present in gateway container doesn't propagate
- No `.env` file exists at `/opt/hermes-agent/.env` (script's fallback path)
- No `.env` file exists at `~/.hermes/.env` (Hermes config convention per AGENTS.md)
- Gateway may get the token via Docker compose env or systemd, but the cron job process doesn't inherit it

**Fix**: Either (a) set `TELEGRAM_BOT_TOKEN` in the cron job's environment directly, (b) create `~/.hermes/.env` with the token (and patch the script to read from there instead of `/opt/hermes-agent/.env`), or (c) source the env from wherever the gateway gets it.

**Failure 2: Forwarder (port 8768) Not Running**
The Codex/local_forwarder service at `http://localhost:8768/` is often not running. This is expected when no Codex tasks are active. Not critical unless the cron job needs it.

**Failure 3: Pending Breadcrumbs Accumulating**
Breadcrumbs with `PENDING` or `PENDING_RESTART` status will be flagged by the health check but won't auto-resolve. These require manual review and resolution.

### Breadcrumb Path Convention
**ALWAYS use `/workspace/.breadcrumbs/`** — never `/hermes-home/.breadcrumbs/`. Cron sessions resolve `~` to `/hermes-home/` (different root!). Interactive sessions write to `/workspace/`.

### Quick Diagnostic Commands

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

### Common Failure Modes

| Symptom | Likely Cause | Fix |
|---|---|---|
| Forwarder FAIL | Forwarder container not running | `docker ps \| grep forwarder`, wait/restart |
| Gateway FAIL | Gateway crashed or port conflict | Check `gateway.log`, restart gateway |
| Telegram SKIPPED | Missing TELEGRAM_BOT_TOKEN in runtime environment | Set env var or create .env file with token |
| Pending breadcrumbs | Previous restart/crash not verified | Review breadcrumb contents, resolve |

---

## Support Files

See `references/outage-case-studies.md` for detailed investigation transcripts from past outages.
- User reports they couldn't reach the bot via Telegram/other platform
- Session search returns unexpected gaps (no user sessions on dates where activity was expected)
- Gateway appears running but no inbound messages being processed
- Cron jobs executing but responses not delivered
- System health verification after restart or config change

## Core Diagnostic Path (Step-by-Step)

### 1. Verify Session Activity for the Relevant Period
```bash
# List sessions by date range
ls /hermes-home/sessions/ | grep <date-pattern> | head -20

# Count non-cron vs cron sessions
ls /hermes-home/sessions/ | grep "<date>" | grep -v "cron_"   # user-initiated?
ls /hermes-home/sessions/ | grep "<date>" | grep "cron_"      # scheduled only?

# Check the session tracker for summary stats
python3 -c "import json; d=json.load(open('/root/.hermes/sessions/tracker.json')); print(json.dumps(d['summary'], indent=2))"
```

**Key insight**: Session files are in `/hermes-home/sessions/` (NOT `/root/.hermes/sessions/`). The latter is a WSL mount alias — the actual persistent location is `/hermes-home/`.

### 2. Check Gateway Logs for Platform-Specific Errors
```bash
# All entries for specific date
grep "2026-05-0X" /hermes-home/logs/gateway.log | head -50

# Look for Telegram-specific issues
grep "2026-05-0X" /hermes-home/logs/gateway.log | grep -iE "telegram|polling|conflict|disconnect|error|fail"

# Look for API/model timeout issues
grep "2026-05-0X" /hermes-home/logs/gateway.log | grep -iE "timeout|request.*fail|timed out"

# Check last successful inbound message timestamp
grep "inbound message:" /hermes-home/logs/gateway.log | tail -20
```

**Gateway restart detection**: `grep "Starting Hermes Gateway\|Press Ctrl+C to stop" /hermes-home/logs/gateway.log` — shows all restart timestamps. Large gaps between restarts mean the process was running continuously (check for silent failures during those gaps).

### 3. Check Agent Log for Model/Processing Issues
```bash
grep "2026-05-0X" /hermes-home/logs/agent.log | grep -iE "error|fail|timeout|warning"
```

**Key failure pattern**: `Session summarization failed after 3 attempts: Request timed out` — indicates the model API (qwen3.6-27b or similar) was unreachable, causing cron jobs to complete without summaries and potentially blocking response delivery.

### 4. Check Error Logs
```bash
grep "2026-05-0X" /hermes-home/logs/errors.log | head -30
```

### 5. Correlate Findings
Build a timeline:
- Last known good inbound message timestamp
- First error/gap timestamp
- Gateway restart timestamps (if any)
- Model API timeout windows
- Cron job success/failure during the gap

## Common Failure Patterns

### Pattern A: Telegram getUpdates Conflict
```
ERROR: "Conflict: terminated by other getUpdates request; make sure that only one bot instance is running"
```
**Effect**: Silent failure — gateway keeps running but receives zero new messages. Can persist for days until manual restart.
**Fix**: Stop conflicting process, restart gateway. Prevent by ensuring single-instance per bot token.

### Pattern B: Model API Timeout Cascade
```
WARNING: "Session summarization failed after 3 attempts: Request timed out"
```
**Effect**: Cron jobs run but can't generate summaries or responses. Gateway continues accepting connections but processing fails.
**Fix**: Check model endpoint reachability (`curl http://<api-server>:1235/v1/health`). May require API server restart or network fix.

### Pattern C: Session Storage Discrepancy
Sessions tracked in tracker.json (at `/root/.hermes/sessions/tracker.json`) but files missing from that directory because actual sessions live at `/hermes-home/sessions/`. Tracker metadata may show sessions exist while disk appears empty.

## Diagnostic Checklist for Outages
- [ ] Sessions exist for the reported period? (`ls /hermes-home/sessions/ | grep <date>`)
- [ ] Gateway was running during outage? (check restart timestamps)
- [ ] Inbound messages logged before/after outage window?
- [ ] Platform-specific errors in gateway.log? (Telegram conflict, webhook failures)
- [ ] Model API reachable during outage? (agent.log timeouts)
- [ ] Cron jobs executing but responses blocked? (summarization failures)
- [ ] Conflicting processes running? (duplicate bot instances)

## WSL-Specific Pitfalls

### `curl.exe` vs `curl` in Scripts
Scripts that hardcode `curl.exe` will **silently fail** in the WSL Linux environment because `.exe` is a Windows binary. The Linux `curl` command has no `.exe` extension.

**Symptom**: Endpoint checks or HTTP calls in scripts return `[Errno 2] No such file or directory: 'curl.exe'`.

**Fix**: Replace `curl.exe` with `curl` in any script running inside the WSL container. Common locations:
- `/hermes-home/scripts/health_push.py` — health check cron job
- Any custom scripts invoking HTTP from the container

**Detection**: `grep -r 'curl\.exe' /hermes-home/scripts/` — should return nothing.

## Support Files
See `references/outage-case-studies.md` for detailed investigation transcripts from past outages.
See `references/health-check-script.md` for health_push.py documentation and troubleshooting.