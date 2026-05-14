# WebSocket Tunnel Debugging Patterns

## Symptoms
- Client shows "connecting... disconnected" cycling
- Works locally but fails through tunnel
- FastAPI/Uvicorn service responds to HTTP but not WebSocket upgrades

## Root Causes (ordered by likelihood)

### 1. Missing `websockets` package
FastAPI + Uvicorn requires the `websockets` package for WebSocket protocol handling:
```bash
pip install "uvicorn[standard]" websockets
python -c "import websockets; print(websockets.__version__)"
```

### 2. Tunnel idle timeout
- ngrok free tier: ~60 seconds
- cloudflared: ~5 minutes
- Implement heartbeat ping/pong pattern:
  ```python
  # Server (FastAPI WebSocket):
  if msg.get("type") == "ping":
      await ws.send_text(json.dumps({"type": "pong", "ts": msg["ts"]}))

  # Client: ping every 25 seconds, reconnect with exponential backoff
  ```

### 3. Wrong protocol scheme
- HTTPS pages → use `wss://` (WebSocket Secure)
- HTTP pages → use `ws://`
- Mismatch causes browser to block connection

### 4. pyngrok vs subprocess tunnels
Prefer `pyngrok` SDK for programmatic tunnel management:
```python
# Good: Programmatic
from pyngrok import ngrok
tunnel = ngrok.connect(8765, "http")

# Avoid: Subprocess calls (may not handle WS upgrades properly)
import subprocess
subprocess.run(["ngrok", "http", "8765"])
```

## Diagnostic Order
1. Test WebSocket connection locally (`ws://localhost:PORT`)
2. Verify ngrok tunnel is running (`ngrok tunnel list`)
3. Check server logs for WebSocket upgrade handling
4. Test through tunnel URL directly in browser
