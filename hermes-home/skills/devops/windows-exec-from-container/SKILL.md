---
name: windows-exec-from-container
description: Execute Windows commands/applications from inside the Hermes Docker container via HTTP bridge to the host PC. Used when the user needs to run Windows EXEs, PowerShell scripts, or cmd.exe commands that aren't accessible inside the container.
---

# Run Windows Apps/Commands From Container

## Problem
The Hermes agent runs inside a Linux Docker container. Windows executables (`.exe`) and Windows-specific tools cannot run directly here. Files from `D:/` are mounted at `/host/d/` but as read/write data — not executable in the Linux environment.

## Environment Facts
- **Container → Host**: Reachable via `host.docker.internal` (resolves to 192.168.65.254)
- **Container ↛ Docker daemon**: No `docker` command inside container (no socket, no PATH). Cannot self-restart. Use Codex Forwarder, WinBridge, or manual host execution.
- **Drive mounts (9P protocol)**: Windows drives are served by Docker Desktop's 9P server via `trans=fd` — the runtime opens file descriptors at container creation, NOT via /etc/fstab or Docker compose volumes. Currently mounted:
  - `D:\` → `/host/d/`, `/workspace/`, `/hermes-home/`
  - `E:\` → `/host/e/`
  - `/mnt/` is **empty** (not drvfs auto-mount — this is a Docker container, not raw WSL)
- **To add a new Windows drive** (e.g. F:): Add a bind mount to `docker-compose.yml` — see **Method 3: Adding a New Windows Drive** below
- **Container tools**: Wine 8.0, Xvfb (display :99), fluxbox WM, curl, Python 3.11
- **No Docker socket** mounted inside container
- **Wine prefix**: `/root/.wine` with `C:\\tools\\link_to_tools\\` → `/host/d/tools/`

## Method Selection Guide
- **Use Wine (in-container)**: Batch processing, CLI tools, headless automation, no display needed, quick execution
- **Use HTTP Bridge (host)**: Full Windows environment access, GUI apps needing real display, native Windows tools, conda environments
- **Add drive via docker-compose (persistent)**: Make a new Windows drive permanently available at `/host/<letter>/` — see Method 3

## Method 3: Adding a New Windows Drive via docker-compose.yml

**When to use**: A Windows drive (F:, G:, H:, etc.) is not visible inside the container. D: and E: are auto-mounted by Docker Desktop's 9P server, but additional drives require explicit configuration.

### Steps

1. **Edit `/opt/hermes-agent/docker-compose.yml`** — add a bind mount for the new drive to both `gateway` and `dashboard` services:
   ```yaml
   volumes:
     - ~/.hermes:/opt/data
     - F:\:/host/f:rw    # <-- add this line
   ```

2. **Restart the container** from the Windows host:
   ```powershell
   cd D:\mkt\python\hermes
   docker compose down --remove-orphans
   docker compose up -d --force-recreate
   ```

3. **Verify** inside the container:
   ```bash
   ls /host/f/
   ```

### Path Format Notes
- Use `F:\` (backslash) — Docker Desktop on Windows resolves this as the host's F: drive
- Mount point inside container: `/host/f/` (lowercase drive letter)
- Use `:rw` to ensure read-write access
- **Must restart the container** for the change to take effect (no hot-reload)

### Troubleshooting
- **Docker permission denied on restart**: The Codex forwarder sandbox can't run Docker commands. Run the restart manually on the Windows host, or use WinBridge (port 9999).
- **Drive still not visible after restart**: Verify the drive exists on Windows (`if exist F:\ echo EXISTS`). Docker Desktop won't mount a non-existent drive.
- **Already added via Docker Desktop File Sharing?**: Docker Desktop → Settings → Resources → File Sharing → add `F:\`. Then restart container. But the docker-compose bind mount (above) is more explicit and doesn't depend on Docker Desktop UI settings.

---

## Method 1: Wine (In-Container)

Wine is installed and running. No host service required.

### Prerequisites Check
```bash
# Verify Wine + Xvfb are ready
wine --version  # Should show wine-8.0
ps aux | grep -E "(Xvfb|fluxbox)" | grep -v grep
ls /root/.wine/drive_c/tools/link_to_tools/
```

### Run a .exe file
```bash
# Direct Wine execution (display :99, no visible window)
wine /root/.wine/drive_c/tools/link_to_tools/<name>.exe

# With arguments
wine cmd /c 'C:\tools\link_to_tools\script.bat arg1 arg2'

# Timeout protection
timeout 30 wine '/root/.wine/drive_c/tools/link_to_tools/app.exe' --flag
```

### Path Mapping
| Windows path | Wine path |
|---|---|
| `D:/tools/AnyDesk.exe` | `C:\tools\link_to_tools\AnyDesk.exe` |
| `/host/d/tools/<file>` | `/root/.wine/drive_c/tools/link_to_tools/<file>` |

### Known Issue: Broken Symlinks
`.exe` files in `D:/tools/` may be broken self-referencing symlinks (e.g., `AnyDesk.exe → AnyDesk.exe`).
- **Detect**: `ls -la /host/d/tools/*.exe` — if symlink target equals source path, it's broken
- **Fix**: User must copy the actual `.exe` file to `D:/tools/` on Windows

### Start Xvfb session (each container session)
```bash
Xvfb :99 -screen 0 1920x1080x24 -ac &
sleep 1
fluxbox &>/dev/null &
sleep 1
export DISPLAY=:99
```

### Running GUI Apps
GUI apps launch in virtual display `:99` via Xvfb + fluxbox. They won't be visible externally.

### Capture GUI app output (screenshots)
```bash
import -window root -display :99 /tmp/screenshot.png
```

### CLI tools that produce no output
May still be running — check with: `ps aux | grep -i appname | grep -v grep`. Wine apps in Xvfb are invisible but functional.

### Broken Symlinks — cp -L workaround
If `.exe` files in `D:/tools/` are broken self-referencing symlinks, use `-L` to follow and copy the real binary:
```bash
cp -L /host/d/tools/file.exe /root/.wine/drive_c/tools/link_to_tools/
```

### PyInstaller-Bundled Apps
Electron apps bundled with PyInstaller may contain Python backend code that doesn't execute properly in Wine. Symptoms: no console output, no new network ports open, silent hangs/crashes. Debug: `strings /path/to/app.exe | grep -iE "python|fastapi|http"`

## Method 2: HTTP Bridge (Host PC)

The original approach — runs commands on the actual Windows host via an HTTP service.

### When to Use
- Full Windows environment access (F:/ drive, conda environments)
- GUI apps needing real desktop display
- Native Windows tools not emulatable by Wine

### Quick Start
1. **Start the bridge** on Windows (`D:\mkt\python\hermes\win_cmd_bridge.py`):
   ```powershell
   cd D:\mkt\python\hermes
   python win_cmd_bridge.py 9999
   ```
2. **Run from container**:
   ```bash
   curl -s -X POST http://host.docker.internal:9999/exec \
     -H "Content-Type: application/json" \
     -d '{"cmd": "Get-Process | Select Name, CPU -First 5", "shell": "powershell"}'
   ```

### Files
- Server: `D:\mkt\python\hermes\win_cmd_bridge.py` (port 9999)
- Client: `/host/d/mkt/python/hermes/win_cmd_bridge_client.py` (container)
- Exe wrapper: `/usr/local/bin/runexe` (Wine method, in-container)

## Troubleshooting

```bash
# Check if host is reachable
timeout 2 bash -c "echo > /dev/tcp/host.docker.internal/22" && echo "SSH open" || echo "SSH closed"
timeout 2 bash -c "echo > /dev/tcp/host.docker.internal/5985" && echo "WinRM open" || echo "WinRM closed"

# Check which ports are already in use on the host
for port in 8768 8642 5000 3000 8080; do
    timeout 1 bash -c "echo > /dev/tcp/host.docker.internal/$port" 2>/dev/null && echo "OPEN: $port" || true
done
```

## Step 2: Choose an Execution Method

### Option A: HTTP Bridge Service (Recommended ✅)

**Pros**: Simple, language-agnostic, works through any network.  
**Cons**: Requires starting a service on Windows host.

1. **Create the bridge script** on the host at `D:\mkt\python\hermes\win_exec_bridge.py`
2. **Start it on Windows** (CMD/PowerShell):
   ```cmd
   cd D:\mkt\python\hermes
   python win_exec_bridge.py --port 9999
   ```
3. **Call from container**:
   ```bash
   curl -s -X POST http://host.docker.internal:9999/exec \
     -H "Content-Type: application/json" \
     -d '{
       "cmd": "dir D:\\mkt",
       "shell": "powershell"
     }'
   ```

### Option B: Extend Existing local_forwarder.py

The forwarder already has an HTTP server on port 8768 with routing. Add a `/exec` endpoint to `local_forwarder.py`:

```python
# Add after the existing /run-async handler (around line 1534)
if path == "/exec":
    cmd = data.get("cmd", "")
    shell = data.get("shell", "powershell")  # or "cmd"
    result = subprocess.run(
        ["/usr/bin/pwsh" if shell == "cmd" else "pwsh", "-Command", cmd],
        capture_output=True, text=True, timeout=120, cwd=str(data.get("cwd"))
    )
    self._send_json(200, {
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    })
    return
```

Then restart the forwarder on Windows and call:
```bash
curl -s -X POST http://host.docker.internal:8768/exec \
  -H "Content-Type: application/json" \
  -d '{"cmd": "Get-Process | Select Name, Id", "shell": "powershell"}'
```

### Option C: SSH with Key Auth

Only works if Windows OpenSSH server is already installed and running (port 22 open):
1. Generate key inside container: `ssh-keygen -t ed25519 -f /root/.ssh/win_exec -N ""`
2. Copy public key to Windows: user must add it to `C:\Users\<username>\.ssh\authorized_keys`
3. Connect: `ssh user@host.docker.internal "Get-Process"`

### Option D: PowerShell Remoting / WinRM

Only works if already configured on Windows (ports 5985/5986). Enable with:
```powershell
Enable-PSRemoting -Force
New-NetFirewallRule -DisplayName "WinRM" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5985
```

## Troubleshooting
- **"Connection refused"**: No service listening on that port. Start one first.
- **"Connection timed out"**: Firewall blocking access from container network. Check Windows Defender firewall rules.
- **Path issues**: Use absolute paths with forward slashes or double-backslashes in JSON (e.g., `"D:/mkt/python"`).
- **No ports available**: The existing ports are 8642 and 8768 (both in use by local_forwarder.py). Choose a different port for the bridge.

### When to Use
- Running `.exe` files that don't have Linux equivalents
- PowerShell/WMI commands for Windows system inspection (processes, services, drives)
- Accessing Windows-only tools installed on the host
- **Inspecting running experiments** on the Windows host from inside the container
- Any task requiring the full Windows environment, not just file access

## Quick Reference: Inspect Windows Processes

See `references/inspect-windows-processes.md` for the full pattern.

### One-liner (inline PowerShell via winbridge)
```bash
# Write script + execute in two steps
curl -s -X POST http://host.docker.internal:8768/winbridge/run \
  -H "Content-Type: application/json" \
  -d '{"script": "D:/mkt/python/hermes/workspace/check_ps.ps1", "timeout": 30}'
```

**⚠️ Port preference:** `9999` (win_cmd_bridge) is often closed/unavailable. **Use port `8768` (local_forwarder `/winbridge/run`) as the reliable default.** Write scripts to `D:/mkt/python/hermes/workspace/` then execute via forwarder.

### Key pitfalls
- ❌ **`Write-Object`** is NOT a PowerShell cmdlet — use `Write-Host` or bare output
- ❌ **Inline code does NOT work** with `/winbridge/run` — it expects a file path
- ✅ Scripts must live in allowed roots: `D:/mkt/python/hermes/workspace/` or `D:/mkt/python/hermes/workspace/scripts/`

## Support Files
- `references/inspect-windows-processes.md` — Process inspection from container (write + execute via forwarder, kill commands)

## Wine-Specific Gotchas & Troubleshooting

### Broken Symlinks in Wine
If `.exe` files in `D:/tools/` are broken self-referencing symlinks (`AnyDesk.exe → AnyDesk.exe`), Wine will fail. Check first:
```bash
ls -la /host/d/tools/*.exe | grep '→ .*\.exe'
test -L /host/d/path/exe && [ "$(readlink /host/d/path/exe)" = "/host/d/path/exe" ] && echo "BROKEN"
```

### PyInstaller-Bundled Apps
Electron apps bundled with PyInstaller may contain Python backend code that doesn't execute properly in Wine. Symptoms: no console output, no new network ports open, silent hangs/crashes. Debug by checking for Python references: `strings /path/to/app.exe | grep -iE "python|fastapi|http"`

### Wine Path Mapping
- C: drive = `/root/.wine/drive_c/`
- D:/ mount → accessible under `drive_d/` or via symlink in `C:\tools\link_to_tools\`

### Command-Line Flags
Wine doesn't always pass args correctly. Test with: `wine '/path/to/app.exe' --help 2>&1 | head -10`
