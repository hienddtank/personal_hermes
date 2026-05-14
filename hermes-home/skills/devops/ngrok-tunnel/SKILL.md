---
name: ngrok-tunnel
description: Comprehensive guide for exposing local services to external access via ngrok tunnels - setup, authentication, tunnel management, WebSocket debugging, status monitoring, reverse proxy alternatives, and specialized patterns. Covers ngrok CLI, pyngrok SDK, Docker container usage, free-tier limitations (WebSocket drops), and alternative tunneling strategies.
version: 2.0.0
---

# Ngrok Tunneling - Comprehensive Guide

## Overview
Expose local services (servers, whiteboards, Docker containers) to external access via ngrok's secure tunneling service. This umbrella skill covers all aspects of ngrok-based tunneling including setup, WebSocket handling, status monitoring, reverse proxy alternatives, and specialized use cases.

### Files
| File | Purpose |
|------|---------|
| `scripts/check-forwarders.sh` | Reusable script to check active tunnels/servers — copy to `~/.hermes/scripts/` for cron jobs |

## Quick Start

### Install & Authenticate
```bash
pip install pyngrok  # Python SDK
# Or CLI: https://ngrok.com/download
ngrok authtoken YOUR_TOKEN
```

### Create HTTP Tunnel
```python
from pyngrok import ngrok
tunnel = ngrok.connect(8765, "http")
print(f"Public URL: {tunnel.public_url}")
```

### CLI Alternative
```bash
ngrok http 8765
```

## Sections

### [Setup & Authentication](references/setup.md)
- ngrok CLI install and authtoken configuration
- pyngrok SDK setup
- Docker container environment considerations (API endpoint: `http://ngrok:4040`)
- Windows/Mac/Linux installation differences

### [WebSocket Tunnel Debugging](references/websocket-debugging.md)
**Symptoms:** Client shows "connecting... disconnected" cycling; works locally but fails through tunnel.

**Root causes & fixes (ordered by likelihood):**

1. **Missing `websockets` package** (MOST COMMON) - FastAPI/Uvicorn needs it for WS upgrades:
   ```bash
   pip install "uvicorn[standard]" websockets
   python -c "import websockets; print(websockets.__version__)"
   ```

2. **Tunnel idle timeout** (~60s ngrok free, ~5m cloudflared) - implement heartbeat ping/pong:
   ```python
   # Server (FastAPI): handle ping -> pong
   if msg.get("type") == "ping":
       await ws.send_text(json.dumps({"type": "pong", "ts": msg["ts"]}))
   
   # Client: ping every 25s, reconnect with exponential backoff
   ```

3. **Wrong protocol** - use `wss://` for HTTPS pages, `ws://` for HTTP

4. **Subprocess vs pyngrok** - prefer `pyngrok` programmatically; subprocess tunnels may not handle WS upgrades

**Diagnostic order:** Test locally -> test through tunnel -> check server logs -> verify tunnel running.

### [Tunnel Status Monitoring](references/status-monitoring.md)
Check ngrok installation, running tunnels, and config:
```bash
ngrok version
ngrok tunnel list  # or API: curl http://ngrok:4040/api/tunnels
ngrok config view
```

**Forwarder check script**: `scripts/check-forwarders.sh` is a reusable script that checks ngrok tunnels, tmux/screen sessions, server processes, and listening ports. Copy to `~/.hermes/scripts/` for cron jobs:
```bash
mkdir -p ~/.hermes/scripts && cp $(find /hermes-home/skills/devops/ngrok-tunnel -name check-forwarders.sh) ~/.hermes/scripts/check-forwarders.sh
```

### [Reverse Proxy Alternative](references/reverse-proxy.md)
When ngrok is unavailable (corrupted binary, blocked ISP), use HTTP reverse proxy:
- Simple Python HTTP server forwarding to localhost:39043
- SSH dynamic forwarding (`ssh -L 8080:localhost:39043 user@server`)

### [Specialized Patterns](references/specialized.md)
- **Whiteboard app on ngrok**: FastAPI + pyngrok, WebSocket support, default board keys
- **SSH dynamic forwarding** as alternative to ngrok
- **Cloudflare Tunnel** as free alternative when ngrok fails
- **Residential IP limitations**: ISP firewall blocks require tunneling solutions

### [Known Issues & Troubleshooting](references/issues.md)
- ngrok CLI binary corruption (ASCII placeholder, not executable)
- Python SDK import errors (`SessionBuilder` missing attributes)
- Download failures from bin.equinox.io and dl.ngrok.com (frequent 404s)
- GitHub releases API availability varies by region

### [File Serving Patterns](references/file-serving-patterns.md)
- Serve static files via python http.server + ngrok tunnel
- Auto-generated index.html landing page with download links
- Multiple-file directory serving for outputs, reports, and assets

## Pyngrok SDK Lifecycle Pitfall ⚠️
When using `pyngrok` SDK programmatically: **the tunnel dies when the Python process exits** if ngrok was started by that process. The SDK spawns an ngrok subprocess tied to the parent PID. If you need a persistent tunnel (e.g., for file downloads), use the ngrok CLI directly with `ngrok http <port>` in a background process instead.

**Recommended pattern for persistent access:**
```bash
# 1. Start your service on a local port
cd /path/to/files && python3 -m http.server 8000 &>/tmp/http-server.log &

# 2. Start ngrok CLI (not SDK) in background
ngrok http 8000 --log=stdout &

# 3. Get the URL from ngrok's local API or logs
sleep 5 && curl -s http://127.0.0.1:4040/api/tunnels | python3 -m json.tool | grep public_url
```

## Prevention Checklist
- [ ] Always install `uvicorn[standard]` for WebSocket services
- [ ] Implement heartbeat ping every 25s for tunnel-exposed WS
- [ ] Test locally before testing through tunnel
- [ ] Use exponential backoff for reconnection (1s -> 2s -> 4s -> max 30s)
- [ ] Prefer ngrok CLI over pyngrok SDK for persistent tunnels
- [ ] Have reverse proxy or SSH forwarding as fallback

## Resources
- ngrok docs: https://ngrok.com/docs
- pyngrok: https://pyngrok.readthedocs.io
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
