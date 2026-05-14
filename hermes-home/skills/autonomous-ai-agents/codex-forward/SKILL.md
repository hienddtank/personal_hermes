---
name: codex-forward
description: Use the local_forwarder.py HTTP service on port 8768 to delegate work to Codex CLI outside the Hermes container. Use when the user explicitly asks to use codex forward, or when Hermes needs Codex to work on allowed host-mounted repositories through POST /run or POST /run-async with progress polling.
---

# Codex Forwarder Skill

## Purpose
Use the `local_forwarder.py` HTTP service to launch `codex exec` on the host-accessible filesystem from inside Hermes. The forwarder is not a generic shell command API; it runs a fresh Codex CLI task for each `POST /run` or `POST /run-async` request.

## Critical Deployment Requirement
**The forwarder MUST run on the Windows host, NOT inside the Docker container.**
- Inside the container: `codex_cmd_exists` is always `false` because `F:\\miniconda\\codex.cmd` cannot resolve in Linux.
- The container only mounts D: → `/host/d/`; F: drive is never accessible.
- If you start `local_forwarder.py` from inside the container, the HTTP server listens but no Codex tasks can execute.
- Start it on Windows directly (e.g., `python local_forwarder.py` in a CMD/PowerShell window) or as a Windows service/scheduled task.
- Verify with `GET /health` — `codex_cmd_exists` must be `true` before attempting any `/run` calls.

### ⚠️ Networking Limitation: Forwarder May Be Unreachable from Container
Even when the forwarder is running on the Windows host (confirmed running, `HOST = "0.0.0.0"`, `PORT = 8768`), it may **not be reachable** from inside the Docker container. This is a known issue with Docker Desktop for Windows + WSL2 backend + `network_mode: host`:
- `host.docker.internal:8768` → Connection refused
- `192.168.1.x:8768` → Connection refused
- `localhost:8768` → Connection refused
- However, the Hermes gateway **inside** the container IS reachable at the same hostnames on port 8642 (the gateway's API port).

**Root cause:** With `network_mode: host` on WSL2 Docker Desktop, the container shares the WSL2 VM's network stack, not the Windows host's LAN stack. A Python process running directly on the Windows host listens on the Windows host's network interfaces — which are on a different virtual network than the WSL2 VM. Traffic cannot route between them.

**How to detect this:**
```python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
result = s.connect_ex(("host.docker.internal", 8768))
print("OPEN" if result == 0 else "CLOSED")
```
Or scan a range:
```python
for host in ["host.docker.internal", "192.168.1.146", "localhost"]:
    for port in [8768, 8769, 8767, 8642]:
        s = socket.socket(); s.settimeout(1.5)
        if s.connect_ex((host, port)) == 0: print(f"OPEN {host}:{port}")
        s.close()
```

**Workaround — Run forwarder inside container (limited functionality):**
If the forwarder is unreachable but you still need its HTTP endpoints (health checks, compose control, file access), you can start it inside the container:
```bash
python /host/d/mkt/python/hermes/local_forwarder.py
```
This binds to `0.0.0.0:8768` inside the container and IS reachable at `localhost:8768`. However, Codex CLI tasks will NOT work (codex_cmd_exists = false, CODEX_CMD = `F:\miniconda\codex.cmd` won't resolve). Only use this for:
- Compose service control (start/stop/restart containers)
- Health checks and diagnostics
- File operations under allowed roots

**Workaround — Use Hermes gateway API directly on port 8642:**
The Hermes gateway listens on port 8642 (accessible at `host.docker.internal:8642`, `192.168.1.x:8642`, etc.). It has a `/health` endpoint but no compose control — check this endpoint first to confirm the container itself is healthy.

## Service Contract
Default base URLs:

- `http://host.docker.internal:8768`
- `http://127.0.0.1:8768`
- `http://localhost:8768`

**Important**: Always call `GET /health` first when checking reachability or diagnosing failures. If route discovery fails, call `GET /help` — unknown GET/POST routes return the `/help` guide with HTTP 200, `ok: false`, and `request.original_status: 404/405` so agents can recover.

Routes:

- `GET /` - same guide as `/help`
- `GET /help` - human and agent-readable usage guide (includes common mistakes)
- `GET /health` - health and diagnostics (richer than before — includes compose config diagnostics, async output limit, keepalive config)
- `GET /jobs` - list recent background Codex jobs
- `GET /jobs/{job_id}` - poll background job progress and final output
- `GET /services` - discover compose services **+ live runtime info** (container state, ports). Returns `include_runtime=True` by default.
- `GET /services/{service}` - service details by compose service name or container_name **+ live runtime info**. Use to check if a service is up/down before controlling it.
- `GET /openapi.json` - OpenAPI schema (v1.6.0)
- `POST /run` - run `codex exec`, keep the HTTP connection alive, return final JSON
- `POST /run-async` - start `codex exec`, return `job_id` immediately for polling
- `POST /services/{service}/start` - start one compose service container
- `POST /services/{service}/stop` - stop one compose service container
- `POST /services/{service}/restart` - restart one compose service container
- `POST /services/start` - start a compose service from JSON body `{"service":"name"}`
- `POST /services/stop` - stop a compose service from JSON body `{"service":"name"}`
- `POST /services/restart` - restart a compose service from JSON body `{"service":"name"}`

## Self-Restart & Dead Man's Switch Pattern
Hermes Agent can restart its own container via the forwarder's direct compose control (no Codex CLI needed):

### Basic restart (simple, no waiting)
```bash
curl -X POST http://host.docker.internal:8768/services/hermes/restart
```

Or with JSON body:
```bash
curl -X POST http://host.docker.internal:8768/services/restart \
  -H "Content-Type: application/json" \
  -d '{"service":"hermes"}'
```

### Preferred: clean recreate with wait + notification (self-healing)
The `recreate` endpoint is the **recommended method for self-restart and dead man's switch** because it waits for the service to be healthy before returning, enabling reliable failure detection:

```bash
curl -X POST http://host.docker.internal:8768/services/hermes/recreate \
  -H "Content-Type: application/json" \
  -d '{"wait_for_url":"http://127.0.0.1:8642/health","notify":{"telegram":true}}'
```

Key fields:
- `wait_for_url`: URL the forwarder polls after recreate to confirm service is healthy. The forwarder blocks until this returns HTTP 200 or timeout expires.
- `notify.telegram`: Send Telegram notification on success/failure (requires telegram_configured in health).
- This runs on the **Windows host** — the forwarder has native Docker access via docker.exe.

### Dead Man's Switch Architecture
For a production-grade dead man's switch that survives container crashes:

1. The watchdog script must run **on Windows host**, NOT inside Docker (container death = any in-container cron dies with it).
2. The forwarder (`http://host.docker.internal:8768`) runs on Windows — its `/health` endpoint is the heartbeat target.
3. If the host-level watchdog detects the forwarder is down → call `POST /services/hermes/recreate` to restart.
4. If the forwarder is up but Hermes agent is down → still call `recreate` since the forwarder has Docker access.

**Why POST /run keeps the response active with whitespace heartbeats until the final JSON result is ready.** Use this for simple one-off restarts when you need immediate confirmation.

## POST /run Payload
Required:
- `prompt`: string task for Codex

Location (provide `repo` or `cwd`; `repo` wins if both present):
- `repo`: optional alias. Common aliases: `fish_doc_extractor`, `fish_store_front`, `hermes_workspace`
- `cwd`: optional path under an allowed root when no alias fits

Optional execution settings:
- `model`: default `gpt-5.4`
- `approval`: default `never`
- `sandbox`: default `workspace-write`
- `timeout`: default `1800` seconds
- `add_dirs`: list of extra allowed directories
- `skip_git_repo_check`: default `true`
- `keep_alive`: default `true` for POST /run — sends leading JSON whitespace heartbeats until final result
- `keep_alive_seconds`: default `15` — heartbeat interval

## Runtime Info (GET /services and GET /services/{service})
Since v1.6, service endpoints return live runtime data by default:
- Container status (running/paused/exited)
- Port mappings
- Uptime info
- Use this to verify a service is actually up before sending start/stop/restart commands

## Health Diagnostics
Key fields in health response:
- `async_jobs.output_limit_chars` — output cap per job stream (26MB / 26,214,400 chars)
- `async_jobs.poll_after_seconds` — recommended polling delay (2s)
- `compose.config_returncode` — docker compose config validation result
- `compose.config_stderr_preview` — first 1000 chars of compose config stderr
- `run_keepalive.headers` — `["X-Forwarder-Keepalive", "X-Forwarder-Job-Id", "X-Forwarder-Status-Url"]`

## Common Mistakes (from docs module)
- Use POST /run for tasks; GET /run only returns this guide.
- Use POST /run-async for long tasks so callers can poll progress instead of waiting on one HTTP request.
- POST /run sends whitespace keepalives before the final JSON; JSON parsers should ignore this leading whitespace.
- Send a JSON body with Content-Type: application/json.
- Include either repo or cwd when calling POST /run.
- Do not send command/args; this service delegates natural-language prompts to Codex CLI.
- Service names come from docker compose config and can change when the compose file changes.
- If compose service discovery fails, check docker daemon state and the compose file path in /health.
- Treat stage=empty_output as no usable answer, even though the Codex process exited 0.
- Keep cwd and add_dirs under the allowed roots listed above.
- Use /health first when checking whether the forwarder is reachable.

Unknown `GET` or `POST` routes return the `/help` guide with HTTP `200`, `ok: false`, and `request.original_status: 404` so agents can recover and choose a valid route.

## Workflow
1. Call `GET /health` first when checking reachability or diagnosing failures.
2. For **complex/multi-step tasks**: write a `codex.md` file with structured instructions, then call `POST /run` telling Codex to read and execute it (see "File-Based Instructions" section).
3. For **simple single-shot queries**: pass instructions directly in the `prompt` string.
4. Use `POST /run` when the caller wants the final result in the same HTTP response. It sends JSON-safe whitespace heartbeats until the final JSON object is ready.
5. Use `POST /run-async` when the caller has a hard total timeout or prefers polling.
6. For async jobs, poll `GET /jobs/{job_id}` every `poll_after_seconds` until `done: true`.
7. Read the JSON response fields `ok`, `stage`, `done`, `running`, `progress_message`, `empty_output`, `output_state`, `stdout_tail`, `stderr_tail`, `stdout`, `stderr`, `returncode`, `cmd`, `hints`, and `request_log`.

## Progress Polling
Blocking progress on `POST /run`:

- The response body may begin with blank lines/newlines while Codex runs.
- This is intentional JSON whitespace; parse the full response as JSON after the connection closes.
- Response headers include `X-Forwarder-Job-Id` and `X-Forwarder-Status-Url` when available.
- If the caller still times out, switch to `POST /run-async` and poll `GET /jobs/{job_id}`.

Start a long task:

```bash
curl -X POST http://host.docker.internal:8768/run-async \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "hermes_workspace",
    "prompt": "Inspect this repository and summarize the available files.",
    "model": "gpt-5.4",
    "approval": "never",
    "sandbox": "workspace-write"
  }'
```

The response includes:

- `job_id`: use this in `/jobs/{job_id}`.
- `status_url`: relative polling path.
- `poll_after_seconds`: recommended polling delay.
- `progress_message`: human-readable running status.

Poll status:

```bash
curl http://host.docker.internal:8768/jobs/job_REPLACE_ME
```

While running, expect `done: false`, `running: true`, elapsed time, and live `stdout_tail`/`stderr_tail` when Codex has emitted output. When finished, expect `done: true`, `returncode`, `stdout`, and `stderr`.

If `stdout_tail` and `stderr_tail` are empty while the job is still running, keep polling. If the final response has `stage: empty_output` or `empty_output: true`, Codex exited but produced no usable answer.

List recent jobs:

```bash
curl http://host.docker.internal:8768/jobs
```

## POST /run Payload
`POST /run` and `POST /run-async` accept the same JSON fields.

Required:

- `prompt`: string task for Codex.

Location, provide `repo` or `cwd`; if both are present, `repo` wins:

- `repo`: optional alias. Current aliases include `fish_doc_extractor`, `fish_store_front`, and `hermes_workspace`.
- `cwd`: optional path under an allowed root when no alias fits.

Optional execution settings:

- `model`: default `gpt-5.4`
- `approval`: default `never`
- `sandbox`: default `workspace-write`
- `timeout`: default `1800` seconds
- `add_dirs`: list of extra allowed directories
- `skip_git_repo_check`: default `true`
- `keep_alive`: default `true` for `POST /run`; sends leading JSON whitespace until the final JSON result
- `keep_alive_seconds`: default `15`; heartbeat interval for blocking `POST /run`

Example:

```bash
curl -X POST http://host.docker.internal:8768/run \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "hermes_workspace",
    "prompt": "Inspect this repository and summarize the available files.",
    "model": "gpt-5.4",
    "approval": "never",
    "sandbox": "workspace-write"
  }'
```

## Path Rules
The forwarder only accepts paths under its configured `ALLOWED_ROOTS`. Call `/health` to see the exact resolved paths for the running service.

When the forwarder runs on Windows, `/host/d/...` is normalized to `D:\...`. When it runs inside a Linux container, `/host/d/...` stays as the mounted path. Do not guess; prefer repo aliases or check `/health`.

Use repo aliases when possible. If a raw path is needed, call `/health` or `/help` first and read `allowed_roots` and `repo_aliases`.

Current common aliases include `fish_doc_extractor`, `fish_store_front`, and `hermes_workspace`.

Codex Forward is not a raw file-read API. For deterministic file contents from paths that Hermes can already access, prefer direct shell/file tools; use Codex Forward when delegating a task to Codex CLI.

## Failure Handling
- If route discovery fails, call `/help`; unknown routes should also return the help body.
- If `ok` is false, inspect `stage`, `error`, `hints`, `stderr_preview`, and `cmd`.
- For async jobs, keep polling while `done` is false. Use `progress_message`, `elapsed_seconds`, `stdout_tail`, and `stderr_tail` as working progress.
- For blocking `POST /run`, ignore leading blank lines before the final JSON result. They are keepalive whitespace, not output.
- If `stage` is `empty_output`, do not treat the blank `stdout` as file content and do not keep retrying random payload shapes. Inspect `request_log.body`, confirm that the request used `prompt` plus `repo` or `cwd`, then retry once with a more explicit prompt that asks Codex to print or summarize the result.
- If `stage` is `preflight` and the error says the Codex launcher was not found, `CODEX_CMD` in `local_forwarder.py` is wrong or Codex CLI is unavailable.
- If validation rejects `cwd` or `add_dirs`, use an allowed root or a listed repo alias.
- If Codex exits non-zero, the forwarder still returns HTTP `200`; treat `ok: false` and `stage: codex_exit_nonzero` as the failure signal.
- If the request times out, retry with a narrower prompt or a larger `timeout`.
- If `GET /health` on port 8768 returns `Connection refused` but the user insists the forwarder is running: the forwarder is likely unreachable due to Docker Desktop WSL2 networking (see "Networking Limitation" above). Use a Python socket scan across `host.docker.internal`, `192.168.1.x`, and `localhost` to confirm. Fall back to starting the forwarder inside the container (limited functionality) or ask the user to run restart commands manually on Windows.

## Output Size & Truncation
- Async jobs: output capped at **8,388,608 chars (8MB)** per stream (stdout + stderr).
- When the limit is hit, the forwarder keeps the **last 8MB** and drops everything from the beginning.
- Check `stdout_truncated_chars` and `stderr_truncated_chars` in the response to see if data was dropped.
- Normal tasks (repos, file listings, summaries) rarely approach this limit. If a task produces massive output (e.g., scanning 10k+ files), split into smaller requests.
- The `output_limit_chars` value is visible via `GET /health` under `async_jobs.output_limit_chars`.

## Important Usage Note
Always use this skill when the user explicitly says "use codex forward" or asks to run work through the Codex forwarder. Delegate through `POST /run-async` for long work or `POST /run` for short work instead of performing the requested host-side Codex task directly.

## File-Based Instructions (Preferred Pattern)

Instead of embedding instructions directly in the `prompt` string, **write a `codex.md` file on disk first**, then call `POST /run` telling Codex to read and execute it. This avoids all multi-line truncation issues because the file lives on disk — no JSON string escaping needed.

### When to use
- **File-based (`codex.md`)**: Multi-step tasks, complex instructions, code generation, file creation/deletion, or anything with structured steps.
- **Inline prompt**: Simple single-shot queries (e.g., "summarize the X function in Y.py", "list all Python files").

### Workflow (file-based)
1. Use `write_file` to create `codex.md` at a path under an allowed root (e.g., `/host/d/mkt/python/hermes/workspace/codex.md`).
2. Structure the file with clear sections: Objective, Steps, Output Requirements, Notes.
3. Call `POST /run` (or `/run-async`) with a minimal prompt instructing Codex to read the file:

```bash
curl -X POST http://host.docker.internal:8768/run \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "hermes_workspace",
    "prompt": "Read the file codex.md in the workspace root. Execute every instruction in that file exactly. Do not deviate from it.",
    "model": "gpt-5.4",
    "approval": "never",
    "sandbox": "workspace-write",
    "timeout": 600
  }'
```

### `codex.md` template
```markdown
# Codex Task: [Brief Title]

## Objective
[What you want accomplished]

## Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Output Requirements
- [Expected deliverables]

## Notes
- [Constraints, read-only rules, paths to avoid, etc.]
```

### Why this works better than inline prompts
| Problem | Inline prompt | File-based (`codex.md`) |
|---------|--------------|------------------------|
| Multi-line truncation | Frequent (gpt-5.4 drops newlines) | None — file read from disk |
| Escaping JSON special chars | Required (`\"`, `\\n`, etc.) | None — plain Markdown |
| Iterating instructions | Re-edit entire curl payload | Just edit the .md file |
| Versionable / reviewable | No (buried in API call) | Yes (standalone file) |
| Task can outlive conversation | No (prompt is ephemeral) | Yes (file persists on disk) |

### Example: Full request
```bash
# Step 1: Write instructions to disk
# write_file to /host/d/mkt/python/hermes/workspace/codex.md

# Step 2: Tell Codex to execute it
curl -X POST http://host.docker.internal:8768/run \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "hermes_workspace",
    "prompt": "Read the file codex.md in the workspace root (D:\\mkt\\python\\hermes\\workspace\\codex.md). Execute every instruction in that file exactly. Do not deviate from it.",
    "model": "gpt-5.4",
    "approval": "never",
    "sandbox": "workspace-write",
    "timeout": 600
  }'
```

### Cross-repo tasks
If the task affects a repo outside the default working directory, include the full absolute path in both:
- The `cwd` field of the POST body (must be under an allowed root)
- The prompt text referencing `codex.md` location

## Support Files
- `references/dead-mans-switch.md` — Architecture and implementation guide for a dead man's switch using the forwarder's Docker API to survive container crashes.
- `references/multi-line-prompt-truncation.md` — Why multi-line content in /run-async prompts gets truncated, with workarounds (shell echo, Python one-liner).
- `scripts/watchdog.py` — Reusable Windows-host watchdog script template (pings forwarder, triggers recreate on failure). Copy to your Windows path before use.

## See Also

- `references/docs-update-recipe.md` — Codex documentation update workflow (structure.md + README.md automation)
