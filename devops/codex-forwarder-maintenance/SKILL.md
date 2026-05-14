---
name: Codex Forwarder Maintenance
description: Maintain and troubleshoot the local_forwarder.py HTTP proxy service that bridges Hermes container to Windows host
version: 1.0
author: Hermes Agent
---

# Codex Forwarder Maintenance Skill

This skill covers maintaining the `local_forwarder.py` service - an HTTP proxy (port 8768) that allows Codex agent to execute commands on local Windows drives from within the Hermes container.

## Service Overview

The forwarder runs as a simple Python HTTP server with these endpoints:
- `GET /` - Service overview
- `GET /health` - Health check & diagnostics  
- `GET /openapi.json` - OpenAPI schema
- `POST /run` - Execute Codex task on approved local repository

## Startup

```bash
cd /host/d/mkt/python/hermes && python local_forwarder.py
```

Service will listen on `0.0.0.0:8768`.

## Health Check

```bash
curl http://localhost:8768/health
```

Key fields to verify:
- `"ok": true` - Service is running
- `"codex_cmd_exists": true` - Codex launcher found (Windows only)
- `"allowed_roots"` - Lists permitted directories

## Common Issues & Fixes

### Path Configuration Bug

**Symptom**: Forwarder rejects valid paths with "Path not allowed" or resolves incorrectly.

**Cause**: `ALLOWED_ROOTS` and `REPO_ALIASES` configured with Windows-style paths (`D:/...`) instead of Linux container paths (`/host/d/...`).

**Fix**: Edit `local_forwarder.py`:
```python
# WRONG (Windows style):
ALLOWED_ROOTS = [Path(r"D:/mkt/python").resolve()]

# CORRECT (Linux container path):
ALLOWED_ROOTS = [Path("/host/d/mkt/python").resolve()]
```

Also update `REPO_ALIASES` similarly.

### Codex Launcher Not Found

**Symptom**: `"stage": "preflight", "error": "Codex launcher not found"`

**Cause**: `CODEX_CMD` points to non-existent path (`F:\miniconda\codex.cmd`).

**Fix**: Update `CODEX_CMD` in `local_forwarder.py`:
```python
CODEX_CMD = r"C:\path\to\actual\codex.cmd"  # Adjust for your system
```

### Port Already In Use

**Symptom**: "Address already in use" error on startup.

**Fix**: Kill existing process:
```bash
pkill -f local_forwarder.py
# or find PID and kill
lsof -i :8768  # Find process using port
```

## Testing

Test the service is running:
```bash
curl http://localhost:8768/health | python3 -m json.tool
```

Test a simple command (requires Codex installed):
```bash
curl -X POST http://localhost:8768/run \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "fish_doc_extractor",
    "prompt": "List files in current directory",
    "model": "gpt-5.4",
    "approval": "never",
    "sandbox": "workspace-write"
  }'
```

## Security Notes

1. **Allowed Roots**: Only paths under configured roots are accessible - prevents arbitrary filesystem access
2. **Approval Policies**: 
   - `never` - No approval needed (default)
   - `always` - Requires manual approval for each command
3. **Sandbox Modes**:
   - `workspace-write` - Can write to workspace
   - `read-only` - Cannot modify files

## File Locations

- Service: `/host/d/mkt/python/hermes/local_forwarder.py`
- Logs: Check stdout/stderr (prints to console)
- Config: Same file (`CODEX_CMD`, `ALLOWED_ROOTS`, `REPO_ALIASES`)