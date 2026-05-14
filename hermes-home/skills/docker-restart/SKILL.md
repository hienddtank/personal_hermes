---
name: docker-restart
description: Controlled Docker Compose restart with logging, health checks, and automated Telegram notification. Used when Hermes needs to self-restart its container stack after config changes.
tags: [devops, docker, self-healing]
related_skills: [windows-exec-from-container, codex-forward]
---

# Docker Compose Controlled Restart

## When to Use
- After modifying `docker-compose.yml` (new volumes, env vars, build args)
- When services need a clean restart (config updates, credential rotation)
- When you suspect stale container state or hung processes
- **ALWAYS write a breadcrumb BEFORE triggering restart** (see Self-Restart Breadcrumb Rule)

## Files
| File | Location | Purpose |
|------|----------|---------|
| docker-restart.ps1 | `D:\\mkt\\python\\hermes\\workspace\\scripts\\` | Main script — runs on Windows host |
| docker-restart-wrapper.py | `D:\\mkt\\python\\hermes\\workspace\\scripts\\` | Python orchestrator (inside container) |
| docker-compose-hermes.yml | (see references/) | Full production docker-compose.yml content with path mappings |

## CRITICAL: Single Breadcrumbs Location
**ALWAYS use `/workspace/.breadcrumbs/`** — never `/hermes-home/.breadcrumbs/`.
- Interactive sessions write to `/workspace/`
- Cron sessions resolve `~` to `/hermes-home/` (different filesystem root!)
- Writing breadcrumbs in cron context puts them in the WRONG location, creating a second `.breadcrumbs` dir that is invisible to you.
- **Rule:** Every breadcrumb = `write_file(path="/workspace/.breadcrumbs/<short-name>-<date>.md", ...)`
- After any breadcrumb write, verify: `ls -la /workspace/.breadcrumbs/`

## Workflow: Trigger from Inside Container

### Option A: Codex Forwarder (port 8768) — sandboxed, no admin Docker access
The Codex forwarder runs in a sandboxed environment. It CANNOT:
- Write to `D:\mkt\python\hermes\` (only `D:\mkt\python\hermes\workspace\`)
- Access Docker daemon (`Access denied` on named pipe)

**Use only for file edits and non-Docker tasks.** To trigger a restart via forwarder, use an INLINE PowerShell script with no external file dependencies:
```bash
curl -s -X POST "http://host.docker.internal:8768/run" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "powershell -Command \"docker --version; docker ps --format \\\"{{.Names}} `t {{.Status}}\\\"; Write-Host ---DOWN---; docker compose down --remove-orphans; Start-Sleep 5; Write-Host ---UP---; docker compose up -d --force-recreate; Start-Sleep 8; docker ps --format \\\"{{.Names}} `t {{.Status}}\\\"; curl.exe http://localhost:8642/health; Write-Host ---DONE---\"",
    "cwd": "D:/mkt/python/hermes",
    "timeout": 300,
    "keep_alive": false
  }'
```
**WARNING:** This often fails with Docker permission denied. If it does, fall through to Option B or C.

### Option B: WinCmdBridge (port 9999) — direct execution on host
If available, use the Windows command bridge which runs outside the Codex sandbox and has full admin access.

**⚠️ Often closed/unavailable:** Port 9999 is frequently not listening. **Test connectivity first** with `timeout 2 bash -c "echo > /dev/tcp/host.docker.internal/9999"`. If port is closed, skip to Option C. Use the local_forwarder `/winbridge/run` on port **8768** as the reliable alternative — see `references/inspect-windows-processes.md` for the pattern.

### Option C: Ask user to run manually on Windows
If neither forwarder nor bridge works, give the user exact commands:
```powershell
cd D:\\mkt\\python\\hermes
docker compose down --remove-orphans
docker compose up -d --force-recreate
# Wait 10s then check: curl.exe http://localhost:8642/health
```

### Option D: Codex Forwarder direct compose control (v1.6+) — PREFERRED ✅
If the forwarder is running on port 8768, use its built-in compose control endpoints. These run on the Windows host with native Docker access (no sandbox restrictions, no permission denied):

```bash
# Clean recreate with health check — waits until hermes responds before returning
curl -X POST http://host.docker.internal:8768/services/hermes/recreate \
  -H "Content-Type: application/json" \
  -d '{"wait_for_url":"http://127.0.0.1:8642/health","notify":{"telegram":true}}'
```

**⚠️ Pitfall (2026-05-08):** The `/services/{name}/recreate` endpoint may return help text instead of executing the restart if the service name doesn't exactly match the compose service name. Check `GET /health` to verify the exact service names. Also, this endpoint can hang for 10+ seconds — set appropriate timeouts.

Other compose commands available:
```bash
# Simple restart (no wait)
curl -X POST http://host.docker.internal:8768/services/hermes/restart

# Start/stop individual services
curl -X POST http://host.docker.internal:8768/services/kiwix/start
curl -X POST http://host.docker.internal:8768/services/kiwix/stop
```

**Advantages over Option A:** No `codex exec` involved, no sandbox restrictions, Docker access on the host works natively, built-in health check polling, optional Telegram notification on completion.

**⚠️ Pitfall — Forwarder may be unreachable from container:** With Docker Desktop for Windows + WSL2 + `network_mode: host`, the forwarder running on the Windows host may not be reachable from inside the container at `host.docker.internal:8768` or any other IP, even though the forwarder binds to `0.0.0.0:8768`. Use Python socket scan to verify before relying on this option:
```python
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2)
print("OPEN" if s.connect_ex(("host.docker.internal", 8768)) == 0 else "CLOSED")
```
If unreachable, fall through to Option C (ask user to run manually) or start the forwarder inside the container (limited — only compose endpoints work, no Codex tasks).

## docker-restart.ps1 Script (if used)
Must follow these conventions to avoid common failures:
1. **Use `${var}` not `$var` when followed by `:`** — PowerShell treats `$var:text` as invalid variable reference
2. **NO Unicode emoji characters** — `✓`, `⚠️`, etc. cause mojibake/encoding corruption in .ps1 files. Use `[OK]`, `[WARN]` instead.
3. **Log to `/workspace/logs/` or stdout only** — sandbox won't allow writing to `D:\mkt\python\hermes\logs\`
4. **Use `curl.exe` not `curl`** — PowerShell's `curl` is an alias for Invoke-WebRequest which requires `-UseBasicParsing`

## Self-Restart Breadcrumb Rule (MANDATORY)

After any self-modifying action, write a breadcrumb BEFORE triggering restart:
```markdown
# Breadcrumb: <description>
- **When:** <timestamp in UTC>
- **What:** <what changed>
- **Action:** <how triggered>
- **Status:** SUCCESS/FAILED/NEEDS_VERIFICATION
```
Path: `/workspace/.breadcrumbs/<short-name>-<date>.md`

## Key Learnings

### Trigger mechanism that works reliably
Use `/run` (synchronous) NOT `/run-async` — the keepalive mode sends periodic whitespace that breaks JSON parsing with `--max-time`. If you must use `/run-async`, strip leading whitespace before parsing: `re.search(r'\{[^{}]*"job_id"[^{}]*\}', raw)`.

### Docker restart always requires admin on Windows
Docker Desktop on Windows blocks non-admin processes from accessing the named pipe. The Codex forwarder runs in a sandbox without elevated privileges — Docker operations will fail with "Access is denied". Always have user run `docker compose down/up` manually if forwarder fails.

### Health check
Check hermes API at `http://localhost:8642/health` as primary indicator. kiwix-serve at `http://localhost:8090/` as secondary.

### Cron vs Interactive breadcrumbs path trap
In cron job context, `~` resolves to `/hermes-home/` (not `/root/`). In interactive shell, `~/.hermes = /root/.hermes`. The workspace is always at `/workspace/` which maps to `D:\mkt\python\hermes\workspace\` on Windows. **ALWAYS use absolute path `/workspace/.breadcrumbs/` — never relative paths.**

## Troubleshooting

### Exposing a new port (e.g. dashboard on 9119) — confirmed procedure (2026-05-12)
Add the port to docker-compose.yml, then do a full recreate (not just restart):

```bash
# Inside container — edit the compose file (it's bind-mounted from host)
# Add under the hermes service ports section:
#   - "9119:9119"

# On Windows host — full recreate needed for port changes:
cd D:\mkt\python\hermes
docker compose up -d --force-recreate
```

**⚠️ Critical:** `docker compose restart` does NOT apply port changes. Must use `up -d --force-recreate` or `down` + `up -d`. Port changes are structural — Docker only re-reads port mappings on container recreation, not process restart.

**Dashboard extras install (first-time per fresh container):**
```bash
cd /opt/hermes-agent && uv pip install -e ".[web]" --python /opt/venv/bin/python
```
The `[web]` extra (fastapi + uvicorn) is NOT included in the default Dockerfile install (`[cli,pty,cron,messaging]`). Must install on every fresh container build.

### Adding a new Windows drive to container — confirmed procedure (2026-05-08)
**Step-by-step:**
1. Edit `docker-compose.yml` on the host at `/host/d/mkt/python/hermes/docker-compose.yml` (this IS the real file — it's bind-mounted from Windows). Add under the desired service's `volumes:` section:
```yaml
- type: bind
  source: F:/
  target: /host/f
```
2. **Save the file** (`write_file` or `patch` works because `/host/d/` → D: is a real bind mount).
3. Recreate from Windows host (you CANNOT do this from inside the agent container): `cd D:\mkt\python\hermes && docker compose up -d hermes`.
4. Verify inside container: `ls /host/f/` and `mount | grep '/host/f'` (should show 9P drvfs mount).

**Confirmed working:** F: drive now accessible at `/host/f/` with full read-write access. Windows system files ($RECYCLE.BIN, pagefile.sys) require elevated permissions inside container but user folders are fully readable.

### Windows drives not mounting (F:, G:, etc.)
Two approaches to add a drive into the container:

**Approach A: Docker Desktop File Sharing (auto-mounts at /host/{letter})**
Docker Desktop on Windows requires explicit per-drive share permission: Settings → Resources → File Sharing. Only shared drives are mountable. By default only C: is shared. D: was added manually. Add any new drives here for container access. Docker Desktop auto-mounts them at `/host/<drive-letter>` via 9P protocol.

**Approach B: Bind mount in docker-compose.yml (simpler, no settings change)**
Add a volume mount directly to the service definition. Two possible YAML formats depending on compose version:

```yaml
# Format A (short syntax — works with Docker Compose V2):
volumes:
  - F:\\:/host/f:rw

# Format B (long syntax — user's actual compose uses this format):
volumes:
  - type: bind
    source: F:/
    target: /host/f
```

Apply to all services that need the drive. Then recreate (`docker compose up -d <service>`).

**Editing from inside container:** The docker-compose.yml lives at `D:\mkt\python\hermes\docker-compose.yml` on Windows. Inside the container it is accessible at `/host/d/mkt/python/hermes/docker-compose.yml`. Edit via `write_file` or `patch` here — changes persist because `/host/d/` is a bind mount to the Windows D: drive.

**Which to use?** Approach B is faster for a one-off drive. Approach A is better if you expect Docker Desktop to always auto-mount the drive on container start. Note: docker-compose.yml lives at `D:\\mkt\\python\\hermes\\docker-compose.yml` on the Windows host — edit it there (or via the mounted path inside the container).

**Inside the container**, drvfs mounts are visible via `/proc/mounts | grep drvfs`. If F: isn't listed, it wasn't shared in Docker Desktop settings. You cannot add drvfs mounts from inside the container (no `wsl.exe`, no `sudo`, no `/etc/wsl.conf`).

### Environment constraints (inside Hermes container)
- **`docker` command NOT available** inside the container — no PATH entry, no named pipe access. Must use forwarder, WinCmdBridge, or ask user to run on host.
- **`/mnt/` is empty** — Windows drives are NOT mounted at `/mnt/c`, `/mnt/d`, etc. inside this container. Only `/host/` provides host filesystem access (e.g. `/host/e/` maps to `E:\\`).
- **Quick drive inventory**: run `cat /proc/mounts | grep drvfs` — lists all Windows drives mounted as 9P in the container. Shows D: and E: by default; F: will only appear after being added to Docker Desktop File Sharing or docker-compose.yml. If no drvfs lines appear, drives were never shared in Docker Desktop settings.
- **`nvidia-smi` IS available** inside the container — shows total GPU usage but NOT per-container VRAM limits (those are only visible via `docker inspect` on the host).
- **Codex forwarder (port 8768) is intermittent after restart** — may need several seconds to become responsive. `GET /health` reveals compose file location (`D:\mkt\python\hermes\docker-compose.yml`) and full service inventory (9 services). Use `GET /services/{name}` for per-service details.
- **WinBridge** (via forwarder `POST /winbridge/run` or `POST /winbridge/run-async`) runs PowerShell directly on the Windows host — has full Docker access. Preferred method for Docker inspection commands.

### WSL2 nvidia-smi limitations (GPU VRAM capping)
WSL2's `nvidia-smi` does NOT support these bare-metal Linux flags:
- `-lgm` (GPU memory limit) — **NOT AVAILABLE** in WSL2
- `-lgc` (locked clocks) — **NOT AVAILABLE** in WSL2
- `--compute-mode` — **fails with "Insufficient Permissions"** even as root

To cap GPU VRAM on a specific GPU (e.g., limit GPU 1 to 1 GB):
1. **Best: Docker GPU device options** — Add `deploy.resources.reservations.devices` or `--gpus '"device=1,count=1,memory=1073741824"'` to docker-compose. Requires container recreation.
2. **Simplest: CUDA_VISIBLE_DEVICES** — Set `CUDA_VISIBLE_DEVICES=0` to hide GPU 1 entirely.
3. **Soft: Environment vars** — `PYTORCH_CUDA_ALLOC_CONF` or `CUDA_VISIBLE_MEMORY=1024MiB` (framework-level, not hard caps).

Windows host `nvidia-smi.exe` is NOT accessible from WSL2 (not in PATH, not at `/mnt/c/Windows/System32/`).

### Container extras not persisting after restart
After a container recreation, pip/uv packages installed in `/opt/venv` DO NOT persist (Docker image is rebuilt from scratch). Hermes `[web]` extra (fastapi+uvicorn) must be reinstalled:
```bash
cd /opt/hermes-agent && uv pip install -e ".[web]" --python /opt/venv/bin/python
```
If `hermes dashboard` complains about missing fastapi/uvicorn, this is the fix. Run before starting the dashboard.

### Containers won't start after restart
Check log file → `docker logs --tail 20 <container>` → verify path exists on Windows host.

### How to tell if container restarted
If a user asks "did you restart?", compare session timestamps in `session_search()`:
- Check `last_active` of the most recent session before current
- Gap > 60 seconds with no user session = a restart likely occurred
- Gap of a few seconds = normal gateway reconnect (no full restart)
- Immediate user session with no gap = no restart happened
- If recent sessions are all cron jobs with no user sessions, there was likely no restart — just idle time

### Breadcrumbs in wrong location
If you see TWO `.breadcrumbs` directories (one at `/hermes-home/.breadcrumbs/` and one at `/workspace/.breadcrumbs/`), the cron breadcrumb was written to the wrong place. Copy it to `/workspace/.breadcrumbs/` and never write to `/hermes-home/.breadcrumbs/` again.

### PowerShell encoding errors
If `docker-restart.ps1` fails with "Variable reference is not valid" or "Unexpected token", the file has: (1) `$var:` syntax errors — change to `${var}:`, (2) Unicode emoji corruption — rewrite with ASCII only, (3) missing braces from encoding mangling. Use `write_file` (not `patch`) for full rewrites to avoid incremental encoding corruption.