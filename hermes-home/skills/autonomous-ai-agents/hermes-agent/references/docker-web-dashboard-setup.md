# Web Dashboard — Docker Setup Notes

## Installing in Docker/git-editable environments (2026-05-14)

The hermes-agent skill's Quick Start shows `pip install 'hermes-agent[web,pty]'` which works for PyPI installs but **fails** when Hermes is installed as an editable package from git (the default Docker build).

### Method 1: Full `[web]` extra (recommended)
```bash
# Inside the container where Hermes lives at /opt/hermes-agent
source /opt/venv/bin/activate
cd /opt/hermes-agent
uv pip install -e ".[web]"
```

This resolves from pyproject.toml which declares:
```toml
web = ["fastapi>=0.104.0,<1", "uvicorn[standard]>=0.24.0,<1"]
```

### Method 2: Individual packages (if `[web]` extra unavailable)
If the editable install doesn't recognize the `[web]` extra or you just need the dependencies quickly:
```bash
# The /opt/venv environment does NOT have a pip binary — use uv pip instead
uv pip install fastapi uvicorn

# Verify
python3 -c "import fastapi; import uvicorn; print('OK')"
```

**Important:** `pip` command is **not present** in `/opt/venv/bin/`. Use either `uv pip install` or `python -m pip` (which may also fail if pip module isn't installed). `uv` is the reliable package manager in this environment.

### Docker-compose port mapping (NOT in default)
The standard docker-compose.yml only exposes `8642` (API server). Dashboard runs on `9119` by default — add it:
```yaml
ports:
  - "8642:8642"
  - "9119:9119"   # <-- add this
```

### Binding to external address
Dashboard refuses `--host 0.0.0.0` by default:
```
Refusing to bind to 0.0.0.0 — the dashboard exposes API keys and config without robust authentication.
Use --insecure to override (NOT recommended on untrusted networks).
```

Start with: `hermes dashboard --host 0.0.0.0 --port 9119 --no-open`
Add `--insecure` if binding externally (safe on single-host Docker Desktop setups).

### Verification
```bash
python3 -c "import fastapi; print('fastapi', fastapi.__version__)"
hermes dashboard --help
```

### Troubleshooting: "Web UI dependencies not installed"
If you see `Import error: No module named 'fastapi'`:
1. Check if installed: `python3 -c "import fastapi"` — if it fails, install with `uv pip install fastapi uvicorn`
2. Reinstall the editable package to update metadata: `cd /opt/hermes-agent && uv pip install -e .`
3. Note: `hermes dashboard` needs to be called with full path `/opt/venv/bin/hermes dashboard` if PATH isn't set
