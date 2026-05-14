---
name: cron-workflow-design
description: Design and implement recurring maintenance cron jobs for agent self-improvement, auditing, recaps, and monitoring. Covers state tracking, separation of concerns, and deduplication patterns.
created_at: 2026-04-20
last_reviewed: 2026-05-04
updated: Replaced all /root/.hermes/ paths with /hermes-home/. Added canonical pathing table (scripts → /hermes-home/scripts/, breadcrumbs → /workspace/.breadcrumbs/). Updated example cron JSON to use filename-only script field. Added shell script writing guidelines. Fixed config.yaml location reference. Updated diagnostic procedure to use cronjob() API instead of raw JSON.
---

# Cron Workflow Design: Recurring Maintenance Jobs

Design effective cron jobs for recurring agent maintenance tasks (audits, recaps, monitoring).

## Core Principles

1. **Separate heavy from light jobs** — Don't combine unrelated tasks into one cron prompt. A skill audit is lightweight; a weekly recap requires session search + memory review. Separate = better quality output.
2. **Use state files to prevent duplication** — Always create/extend a JSON tracker file so the job knows what it has already done/suggested across runs. Key arrays: `audited`, `flagged`, `generated`, `processed_sessions`.
3. **Single source of truth per domain** — One tracker per domain (e.g., `skill-audit-tracker.json` for skills, `recap-state.json` for sessions). Don't scatter state across files.

## Design Checklist

Before creating a cron job, confirm:

- [ ] Schedule is correct for timezone (`0 9 * * 1-5` = Mon-Fri 9am UTC)
- [ ] State file exists with proper structure (JSON with typed arrays/objects)
- [ ] Prompt includes: state reading → data gathering → analysis → formatting → state update
- [ ] Output is structured for human review with emoji sections and a summary line
- [ ] Job has `deliver: origin` to return results to chat
- [ ] No auto-execution of changes — output suggestions only, user approves

## Common Patterns & Triggers

| Pattern | When to trigger | What it does |
|---|---|---|
| **Audit** | Daily/weekly for each domain | Check installed items against quality checklist, flag issues, suggest improvements |
| **Recap** | Weekly (end of week) | Summarize sessions/findings across a time period, identify open threads |
| **Monitor** | Hourly/daily | Watch external resources (web pages, APIs) for changes |

## State File Template

```json
{
  "audited": {},       // {name: date} — what's been processed
  "flagged_issues": [], // [{item, issue, date}] — problems found
  "suggestions_generated": [] // [names] — suggestions so far (prevent repeats)
}
```

## Prompt Structure (Reusable Template)

1. **Read state file** → know what's been done before
2. **Gather current data** → `skills_list`, `session_search()`, etc.
3. **Evaluate against checklist** → compare against criteria
4. **Generate new-only suggestions** → only for things NOT in generated array
5. **Format output** → structured sections + emoji + summary stats
6. **Update state file** → write back with new entries

## Common Pitfalls

- **Re-flagging the same issues forever** — Always check `flagged_issues` before re-reporting a problem. Add "last flagged" date.
- **Duplicating suggestions across runs** — Maintain `suggestions_generated` array as an exclusion list.
- **Cron running during active work** — Schedule during expected idle hours (early morning user's timezone).
- **Memory tool disabled but still called** — The `memory` tool may be disabled in config. If a cron prompt references it, the job will error out. Always skip memory operations in cron jobs or verify it's enabled first.
- **Memory tool disabled but still called** — The `memory` tool may be disabled in config. If a cron prompt references it, the job will error out. Always skip memory operations in cron jobs or verify it's enabled first.
- **qwen3.6-27b model stuck in tool-call loops** — When given a complex multi-phase LLM-driven prompt (e.g., "do 5 phases of analysis"), the qwen3.6-27b model keeps making tool calls but never produces a final text response. Symptoms: session has 10+ messages, all assistant turns have `content_len: 0` and tool_calls > 0, no final delivery. **Confirmed pattern (2026-05-08):** With ~60+ skills to audit, the model called `skill_view()` on each one sequentially (18 tool responses in 22 messages) but never finished or produced a summary response.

## Resolving qwen3.6-27b Tool-Call Loops (Heartbeat Fix Pattern)

**Problem:** Complex multi-phase LLM prompts cause qwen3.6-27b to loop endlessly through tool calls without producing a final text response. Both 4AM and Noon heartbeat jobs failed with `last_status: "error"` for this reason.

**Symptoms in session files:**
- Session has 10+ messages
- All assistant turns have `content_len: 0` and `tool_calls > 0`
- No final text output delivered
- Cron job marked as `error`

**Resolution procedure:**

1. **Diagnose the loop** — Read the session file (`session_cron_<job_id>_<date>.json`). Check if every assistant message has empty content with tool calls. This confirms the model is stuck.
2. **Simplify the prompt** — Reduce to 2-3 steps max. Remove phases that trigger deep analysis or memory operations.
3. **Offload to a script** — Write the data collection logic into a shell/Python script. The cron job should just run the script and deliver its output.
4. **Verify with manual run** — `cronjob(action='run')` then check the session file for non-zero assistant content length.

**Example transformation:**
```
BEFORE (broken): "Phase 1: Review sessions... Phase 2: Self-reflection... Phase 3: Cron cleanup... Phase 4: Memory maintenance... Phase 5: Report..."
AFTER (fixed):    "Run the health check script at /hermes-home/scripts/health_push.py and report the results."
                  + script field: "health_push.py"
```

**Key rule:** Keep cron prompts for qwen3.6-27b to simple "run this script, deliver the output" — never multi-phase analysis instructions.

## Cron Timeout Configuration: Two Separate Timeouts

Cron jobs have **two independent timeout settings** that both control job execution limits. Both must be configured correctly or jobs will terminate early:

### 1. `gateway_timeout` (config.yaml, agent-level)
- Location: `~/.hermes/hermes-home/config.yaml` → `agent.gateway_timeout`
- Controls how long the **agent session** runs before the gateway kills it
- Change via: edit config.yaml, then restart container/process

### 2. `HERMES_CRON_TIMEOUT` (environment variable, cron-specific)
- Source: [Hermes Agent Cron Troubleshooting docs](https://hermes-agent.nousresearch.com/docs/guides/cron-troubleshooting)
- Controls the **inactivity timeout** for cron jobs specifically
- Default: `600` seconds (10 minutes)
- Configurable via: `HERMES_CRON_TIMEOUT` env var; set to `0` for unlimited
- Timer only fires after sustained inactivity — the agent can run as long as it's actively calling tools

### Configuration procedure:
1. **Set env var in docker-compose.yml** (if running Docker):
   ```yaml
   environment:
     HERMES_CRON_TIMEOUT: "3600"  # seconds, 0 = unlimited
   ```
2. **Update config.yaml** for agent-level timeout:
   ```yaml
   agent:
     gateway_timeout: 3600  # seconds
   ```
   Location: `/hermes-home/hermes-home/config.yaml` (NOT `~/.hermes/`)
3. **Restart the container**: `docker compose restart hermes` (must run on host, not inside container)

### Verification:
- After restarting, check job status via `cronjob(action='list')` and verify no premature timeout errors
- Long-running scripts (data collection, web scraping) need both set; lightweight check scripts may only need `HERMES_CRON_TIMEOUT`

## Environment Constraints: `hermes_tools` Not Available in Cron Scripts

The `hermes_tools` Python module is only available inside the Hermes Agent runtime context, not in standalone Python processes. **Two failure modes exist:**

### Mode 1: Embedded Python in cron prompt
If a cron job's `prompt` field contains Python code that does `from hermes_tools import session_search`, the system may inject and execute it as a standalone subprocess. This crashes with exit code 2:
```
ModuleNotFoundError: No module named 'hermes_tools'
```

**Fix:** Keep cron prompts as plain text instructions only. Never embed Python code in cron prompts.

### Mode 2: Cron `script` field points to hermes_tools-using script
If the `script` parameter in `~/.hermes/cron/jobs.json` references a Python file that imports `hermes_tools`, the same error occurs when the system runs it in isolation.

**Fix:** All cron scripts must use only stdlib (json, os, datetime, glob, etc.) for data collection. If you need session data, read from exported JSONL files on disk (`~/.hermes/chat_history/*.jsonl`).

### Correct pattern for a data-collection cron job:
```json
{
  "name": "Data Collection - Chat History Backup",
  "script": "data_collection.py",
  "prompt": "Report on the data collection results. If the script completed successfully, confirm that session history is up to date.",
  "schedule": "every 24h",
  "deliver": "local"
}
```
The script is located at `/hermes-home/scripts/data_collection.py` and referenced by filename only in the `script` field. The cron system resolves it from `/hermes-home/scripts/`. The prompt is just a lightweight wrapper that reports results.

### Available stdlib-only cron scripts (all in /hermes-home/scripts/):
- `data_collection.py` — primary data collection (stdlib-only, reads JSONL files)
- `full_extract_sessions.py` — full extraction with tool-first fallback
- `heartbeat_check.sh` — bash-based health check

### Writing new cron Python scripts:
1. Never import `hermes_tools`, hermes_tools, or any Hermes-specific module
2. Use only stdlib: json, os, datetime, glob, pathlib, subprocess, sys
3. Read session data from existing `.jsonl` files in `/workspace/` or relevant paths (NOT `~/.hermes/chat_history/`)
4. Write output to `/hermes-home/scripts/` state files or `/workspace/.breadcrumbs/` for breadcrumbs
5. Test with `python3 /hermes-home/scripts/<scriptname>` before deploying to cron
6. The script should return 0 on success (even when no new data found — write an export_marker)

### Writing new cron shell scripts:
1. Use `#!/bin/bash` shebang
2. Use `curl` (not `curl.exe`) — the container has `/usr/bin/curl`. `curl.exe` does NOT exist in the container and will fail with `[Errno 2] No such file or directory`.
3. Handle TELEGRAM_BOT_TOKEN from env or `/opt/hermes-agent/.env` fallback
4. Use absolute paths everywhere — never `~` or relative
5. Test with `bash /hermes-home/scripts/<scriptname>` before deploying to cron

## Skill Audit & Cleanup Safety

During skill audits (delete orphaned skills, clean scripts), always distinguish **two storage models**:

### Registry-Based Skills (safe to delete parent dirs on disk)
- Script content is stored **within the registry itself**, not as separate on-disk files
- Identified by: `skill_view(name)` returns content + linked_files with scripts that may NOT exist on disk
- Safe action: `rm -rf /hermes-home/skills/some-parent/` will NOT break these skills
- Example: `pdf-to-audio-kokoro`, most category-prefixed skills (e.g., `mlops/whisper`)

### Disk-Based Skills (scripts MUST exist on disk)
- Script is a real file on disk referenced by SKILL.md
- Identified by: `skill_view(name, file_path='scripts/xxx.py')` returns 404 or the script doesn't exist at the expected path
- UNSAFE to delete parent directories — will break the skill's scripts
- Example: skills in `/hermes-home/skills/productivity/word-gen/scripts/word_gen.py`

### Audit Procedure
1. **List all skills** → `skills_list(category='')` (full list with 0 limit)
2. **Check on-disk vs registry match**:
   ```bash
   find /hermes-home/skills/ -name "SKILL.md" | sort
   ```
3. **Identify dead skills**: check for skills where linked scripts don't exist:
   ```python
   # Test each skill's scripts
   skill_view(name, file_path='scripts/xxx.py')  # if it fails → script missing
   ```
4. **Delete only confirmed-dead skills** with `skill_manage(action='delete', name='...')` — this removes from registry AND cleans up disk files
5. **NEVER bulk-delete directories via terminal** unless you're certain all contained skills are either unregistered or registry-based (scripts embedded in registry)

## Diagnosing Failed Cron Scripts

When a cron job fails, follow this step-by-step diagnostic procedure:

1. **Check the error output** — Look for `stdout` and error details (exit code 2 + ModuleNotFoundError usually means hermes_tools import failure).
2. **Read the cron config** — Use `cronjob(action='list')` to find which `script` path the job points to. Note: the `last_run_at` field being `null` means the job hasn't run yet (error may be from a prior manual test or different invocation).
3. **List all scripts** — Check `/hermes-home/scripts/` for multiple Python files. There may be old versions alongside new ones.
4. **Read candidate scripts** — Read each script to see which one matches the error output (e.g., "Saving session history to:" prefix points to save_chat_history.py).
5. **Run the suspected script manually** — `python3 /hermes-home/scripts/<scriptname>` to verify it reproduces or passes.
6. **Cross-reference with all scripts** — If the error doesn't match any on-disk script, the error may be from an older cached version or inline code that ran previously.

### Key indicators:
- **"Cannot import hermes_tools"** → Script uses `from hermes_tools import ...` without fallback. Fix: use only stdlib in cron scripts.
- **"No module named 'hermes_tools'"** → Same as above, but from a subprocess execution context.
- **Exit code 0 but no data** → Script ran but found nothing (normal — check for export_markers in JSONL files).
- **Last run is null but error exists** → Error was from a different invocation (manual test or old job config), not the current scheduled run.

## Execution Visibility Limitation: Cron Output Is Invisible During Creation

**Critical pattern:** When you create a cron job and immediately say "run it now" or "do that", calling `cronjob(action='run')` executes the job in a **completely isolated session**. The output goes to the deliver target (e.g., `telegram:-100...`) — **NOT back to your current conversation**. You cannot inspect intermediate results, check logs, or interact with the running cron.

### Correct approach for immediate execution:
1. Create the cron job normally (for future recurring runs)
2. To execute NOW with visible output, **run the task logic directly** in your current session using `execute_code` or `terminal`, not `cronjob(action='run')`
3. Use `cronjob(action='run')` only when you don't need to see the results (e.g., a background status check)

### Why this matters:
- Cron runs are isolated with no context of your current conversation
- You can't use `session_search()`, `web_search()`, or other tools to debug mid-run
- The output is delivered asynchronously — you won't see it until the next turn if at all
- Always verify cron-created files by reading them directly after execution

### When you CAN use cronjob(action='run'):
- The job writes a file that you'll check in a subsequent turn
- You just need the side effect (e.g., "check forwarder status" — it delivers to Telegram anyway)
- You're testing idempotency, not inspecting output

## CRITICAL: Verify Scripts Exist Before Assigning to Cron

**Pattern observed (2026-05-04):** Two cron jobs referenced `heartbeat_check.sh` via the `script` field, but no such file existed on disk. The crons were marked `last_status: "ok"` because they never actually executed — the system silently skipped them without error notification.

**Rule:** After creating a cron with a `script` field, immediately verify:
```bash
ls -la /path/to/that/script.sh  # or .py
```
If it returns nothing, the cron will fail silently on every run. Either create the script or switch to an inline prompt approach.

**Also:** Cron jobs cannot contain curl commands directly in their `prompt` field — this is blocked as a threat pattern (exfil_curl). Always write logic into a script file and reference it.

## CRITICAL: Large Cron Output → File + Attachment Pattern

When a cron job's output will exceed Telegram's 4,096-character message limit (typically >80 lines of process info, full listings, or verbose dumps), **never let the agent paste it inline**. Instead:

1. **Script writes to file** — Use `tee` or redirect in the script:
   ```bash
   OUTPUT_DIR="$HOME/.hermes/logs/cron-name"
   mkdir -p "$OUTPUT_DIR"
   TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
   OUTPUT_FILE="$OUTPUT_DIR/check_${TIMESTAMP}.txt"
   exec > >(tee "$OUTPUT_FILE") 2>&1   # Captures everything to file + stdout
   ```

2. **Cron prompt instructs file delivery** — Tell the agent:
   > "After running, find the latest file in `$OUTPUT_DIR/`, read it, send a brief summary, then attach the full file using MEDIA:<absolute_path>. Do NOT paste raw output."

3. **Old files accumulate** — Add cleanup logic to the cron prompt or a periodic maintenance task:
   ```bash
   # Keep only last 10 runs
   ls -1t "$OUTPUT_DIR"/*.txt | tail -n +11 | xargs rm -f
   ```

### Why this matters
- Telegram inline messages have a hard 4,096 char limit — large outputs get truncated mid-stream
- File attachments deliver the complete output cleanly and are downloadable
- The agent's summary gives at-a-glance status; the file is for deep review

## CRITICAL: Docker Container Networking with `ss` / `netstat`

`ss -tlnp` and `netstat -tlnp` **do not reliably show listening ports inside Docker containers** because the container lacks access to the host's network namespace. The command may return zero results even when services are actively listening.

### Correct approach for port checks inside containers:
- **Use Python socket probing**:
  ```python
  import socket
  def check_port(host, port, timeout=2):
      s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      s.settimeout(timeout)
      result = s.connect_ex((host, port))
      s.close()
      return result == 0
  ```
- **Or use `curl` / `wget`** against known service endpoints
- **Or check from the host side** using `docker exec <container> ss -tlnp` or `nsenter --net=/proc/<pid>/root/ns/net`

### Pattern for a cron port-check script (container-safe):
```python
#!/usr/bin/env python3
"""Port health checker — works inside Docker containers."""
import socket, sys

def check_port(host, port, timeout=2):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        ok = s.connect_ex((host, port)) == 0
        s.close()
        return ok
    except Exception:
        return False

SERVICES = [
    ("127.0.0.1", 8765, "local_white_board"),
    ("127.0.0.1", 8090, "kiwix-serve"),
]

for host, port, name in SERVICES:
    status = "UP" if check_port(host, port) else "DOWN"
    print(f"{name:<25} {host}:{port:>5} → {status}")
```

## CRITICAL: Consolidate Overlapping Crons

**Preference:** User prefers unified, deduplicated cron jobs over multiple fragmented ones doing similar things. If you identify 2+ crons covering overlapping domains (e.g., separate heartbeat + breadcrumb check), propose merging them into a single job rather than maintaining redundancy.

## CRITICAL: Cron vs Interactive File Path Trap

Cron sessions and interactive sessions run with different `~` (home directory) resolution:
- **Interactive shell:** `~` → `/root/` (`~/.hermes` = `/root/.hermes`). User workspace files at `/workspace/` map to Windows D: drive.
- **Cron job context:** `~` → `/hermes-home/` (`~/.hermes` = `/hermes-home/.hermes`)

**Canonical pathing rules (enforced since 2026-05-04):**

| Item | Path | Reason |
|---|---|---|
| **Cron scripts** | `/hermes-home/scripts/<name>` | This is where cron resolves `~` → the script must live here |
| **Breadcrumbs/state** | `/workspace/.breadcrumbs/<name>` | Single authoritative location; user-visible in interactive session |
| **Docker compose** | `/opt/hermes-agent/` (or wherever mounted) | Fixed container mount point |
| **Config files** | `/hermes-home/` prefix | Cron-safe, never use `~` |

**Rule:** Never use `~` or relative paths in cron prompts. Always use absolute paths that resolve correctly in BOTH contexts:
- Scripts: `/hermes-home/scripts/health_push.py` (not `~/scripts/...` or `/workspace/scripts/...`)
- Breadcrumbs: `/workspace/.breadcrumbs/` (NOT `/hermes-home/.breadcrumbs/` — that's a duplicate trap)

**Verify after writing:** `ls -la /hermes-home/scripts/<scriptname>` to confirm the file is where cron expects it.

**Observed failures from wrong paths:**
- `heartbeat_check.sh` referenced in crons but script at different path → silent skip (no error)
- Breadcrumbs written to `/hermes-home/.breadcrumbs/` by cron context → invisible to user at `/workspace/.breadcrumbs/`
- Script saved as `/workspace/scripts/...` for cron → cron can't find it (resolves under `~` = `/hermes-home/`)

## CRITICAL: Canonical Skill Path

**Single source of truth for skills: `/hermes-home/skills/`** (maps to `D:\mkt\python\hermes\hermes-home\skills` on the Windows host).

All skill directories, SKILL.md files, references/, scripts/, and assets/ live here. This is the canonical location — never create or edit skills under `/workspace/skills/`. Disk-based skills created via `skill_manage` automatically go to `/hermes-home/skills/<name>/`.

**Never duplicate:** If you see a skill existing in multiple locations (e.g., both `/workspace/skills/docker-restart/` and `/hermes-home/skills/docker-restart/`), always use the one under `/hermes-home/skills/`. The workspace copy is stale.

## Timezone-Aware Scheduling Pattern

For batch jobs that should only run during user's inactive hours:

```bash
#!/bin/bash
# runner.sh — timezone-aware runner (example: Hanoi GMT+7)
CURRENT_UTC_HOUR=$(date -u +%H)
# 10pm GMT+7 = 3pm UTC (start), 7am GMT+7 = midnight UTC (stop)

# Kill zone: 0am-14pm UTC (7am-7pm GMT+7) → user is awake
if [ "$CURRENT_UTC_HOUR" -ge 0 ] && [ "$CURRENT_UTC_HOUR" -lt 15 ]; then
    pkill -f batch_processor 2>/dev/null
    exit 0
fi

# Run zone: 3pm-11pm UTC (10pm-6am GMT+7) → user is sleeping
pgrep -f batch_processor > /dev/null || {
    cd /path/to/project && nohup python3 batch_processor.py >> log 2>&1 &
}
```

**Setup**: Two cron jobs:
1. **Runner** (every 30m): Checks timezone, starts/kills process
2. **Progress reporter** (every 6h): Sends status notification

**Timezone conversion**: `GMT+N hour = UTC hour + N`. If N is positive, add to UTC. If the result exceeds 24, wrap.

## Sub-Skills & Reference Files

This umbrella skill covers all cron-based maintenance patterns. See reference files for specific implementations:

- **references/session-extraction.md** — Fix pattern for collecting session history when data_collection.py fails (standalone mode without hermes_tools)
- **references/memory-management.md** — Memory trimming and consolidation strategies for Hermes Agent's persistent memory
- **references/weekly-review-cron.md** — Weekly session review cron: scheduling, debugging qwen3.6-27b tool-loop failures, heartbeat pattern
- **references/python-cron-scripts.md** — Guidelines for writing Python-based cron scripts (stdlib-only, curl via subprocess, Telegram API push)
- **references/cron-provider-issues.md** — Provider-specific cron failures (openrouter vs custom), qwen3.6-27b tool-loop diagnosis patterns and detection scripts

## Related Maintenance Skills (Hub-Installed)

- `weekly-session-review` — Pre-built weekly Sunday 6AM cron job pattern for scanning sessions and updating memory
