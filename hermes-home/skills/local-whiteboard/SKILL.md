---
name: local-whiteboard
description: Interact with Hien's LAN collaborative whiteboard (FastAPI on port 8765). Upload/download files, sync text, paste images via WebSocket. Runs INSIDE the Linux container using system Python. Use whenever the user wants to push content to or pull content from their local whiteboard.
tags: [whiteboard, local, LAN, collaboration, file-upload, websocket]
---

# Local Whiteboard App

A self-hosted LAN collaborative whiteboard built with FastAPI + WebSockets. Runs on **port 8765** inside this Linux container. Supports text sync, pasted images (real-time), and file uploads across multiple board keys.

## Location & Setup

- **Source**: `/host/d/mkt/python/local_white_board/`
- **Binary**: `local_whiteboard_app.py` (self-contained, embedded HTML)
- **Dependencies**: fastapi, uvicorn, websockets, python-multipart (installed via system pip to `/usr/local/lib/python3.11/site-packages`)
- **Python**: `/usr/local/bin/python3.11` (system Python with all deps)
- **Run**: See "Starting the Server" below

## Starting the Server

```bash
# Start in background
/usr/local/bin/python3.11 /host/d/mkt/python/local_white_board/local_whiteboard_app.py > /tmp/wb.log 2>&1 &

# Verify it's up
curl -s --max-time 3 http://127.0.0.1:8765/ | head -c 50

# Check process
pgrep -f local_whiteboard_app && echo "RUNNING" || echo "STOPPED"
```

**URL inside container:** `http://127.0.0.1:8765`  
**URL from outside (LAN):** `http://<host-ip>:8765` or via ngrok/tunnel

## Board Keys & Access Control

```python
REQUIRE_KEYS = False  # Any key creates a new board on disk
ALLOWED_KEYS = {
    "meeeee": {"label": "admin"},
    "hai":    {"label": "user1"},
}
```

Any string key works. Each key gets its own folder under `whiteboard_instances/<safe_key>/`.

## Quick Reference — Endpoints

**REST (use `?key=<key>` query param):**
| Method | Path | What |
|---|---|---|
| POST | `/upload?key=***` | Upload file (multipart/form-data, field="file") |
| GET | `/download?key=***` | Download board text as plain text |
| GET | `/download.json?key=***` | Export full board state as JSON |
| GET | `/img/{image_id}?key=***` | View served image (inline) |
| GET | `/file/{file_id}?key=***` | Download stored file (attachment) |

**WebSocket (real-time):**
```
ws://127.0.0.1:8765/ws?key=***
```

**UI:**
| Path | What |
|---|---|
| `GET /admin` | Control panel (local-only, opens in browser) |
| `GET /b/<key>` | Board view (HTML editor for the given key) |
| `GET /whiteboard.html` | Generic whiteboard UI |
| `GET /` | Root page / redirects to /admin |

## File Upload (REST — verified working)

Use when uploading arbitrary files (PDFs, images, docs, etc.):

```bash
curl -X POST "http://127.0.0.1:8765/upload?key=meeeeeee" \
  -F "file=@/path/to/file.pdf;type=application/pdf"
# → {"ok": true, "entry": {"id": "...", "name": "file.pdf", "mime": "application/pdf", "size": 12345, ...}}
```

Or with Python `requests`:
```python
import requests
with open("/path/to/file.pdf", "rb") as f:
    resp = requests.post("http://127.0.0.1:8765/upload?key=meeeeeee", files={"file": ("filename.pdf", f, "application/pdf")})
```

Limits: 500 MB per file, 500 files per board, ~5 TB total per key.

## Downloading Content

```bash
# Text only
curl "http://127.0.0.1:8765/download?key=meeeeeee"

# Full board JSON (text + images[] + files[])
curl "http://127.0.0.1:8765/download.json?key=meeeeeee" | python3 -m json.tool
```

## WebSocket API — Verified Working

Connect via `ws://127.0.0.1:8765/ws?key=<key>`.

### Client → Server Messages (verified)

| Type | Fields | What |
|---|---|---|
| `text_update` | `{"type": "text_update", "text": "..."}` | Update board text (server auto-increments rev) |
| `paste_image` | `{"type": "paste_image", "data_url": "data:image/png;base64,...", "rev": N}` | Paste inline image (base64 data URL) |
| `delete_image` | `{"type": "delete_image", "id": "<image_id>"}` | Remove a pasted image |
| `delete_file` | `{"type": "delete_file", "id": "<file_id>"}` | Remove an uploaded file |
| `ping` | `{"type": "ping"}` | Keepalive (server replies with `pong`) |

**CRITICAL:** Image paste type is `"paste_image"` NOT `"image_paste"`. The server silently skips unknown message types.

### Server → Client Messages

| Type | When |
|---|---|
| `init` | On connect — includes key, rev, text, images[], files[], plus counts/bytes |
| `text_broadcast` | After any `text_update` — sends the new text + rev to all clients |
| `image_added` | After any `paste_image` — sends image metadata + counts |
| `image_deleted` | After any `delete_image` — confirms deletion |
| `file_added` | After any REST upload — broadcast to connected WebSocket clients |
| `file_deleted` | After any `delete_file` — confirms deletion |
| `info` | Error/warning message (e.g., "Text too large", "Image limit reached") |
| `pong` | Response to `ping` |

Limits: images ≤ 25 MB each, 120 max per board, 300 MB total; text ≤ 200 MB.

### Minimal WebSocket Example (Python)

```python
import asyncio, json, websockets

async def push_text():
    async with websockets.connect("ws://127.0.0.1:8765/ws?key=meeeeeee") as ws:
        init = json.loads(await ws.recv())  # init message
        rev = init["rev"]
        
        # Send text (rev optional, server auto-increments)
        await ws.send(json.dumps({"type": "text_update", "text": "# Hello\nThis is my whiteboard."}))
        
        # Receive broadcast (goes to all clients including sender)
        resp = json.loads(await ws.recv())  # {type: "text_broadcast", rev: N, text: "..."}
        print(f"Updated to rev={resp['rev']}")

asyncio.run(push_text())
```

### Image Paste Example (verified)

```python
import asyncio, json, websockets, base64, io, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

async def paste_image():
    async with websockets.connect("ws://127.0.0.1:8765/ws?key=meeeeeee") as ws:
        init = json.loads(await ws.recv())
        rev = init["rev"] + 1
        
        # Create image → base64 data URL
        fig, ax = plt.subplots(figsize=(4,2), dpi=100)
        ax.text(0.5, 0.5, 'Test Image', ha='center', va='center')
        buf = io.BytesIO()
        fig.savefig(buf, format='png', facecolor='#f5f5f5')
        plt.close()
        
        data_url = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
        await ws.send(json.dumps({"type": "paste_image", "data_url": data_url, "rev": rev}))
        
        # Server broadcasts image_added back
        resp = json.loads(await ws.recv())  # {type: "image_added", ...}
        print(f"Image added: {resp}")

asyncio.run(paste_image())
```

## Board Data Location

Board data stored on disk at:
```
/host/d/mkt/python/local_white_board/whiteboard_instances/<safe_key>/
  state.json          # Board state (text, rev, images list, files list)
  assets/images/      # Pasted images (from WS paste_image)
  assets/files/       # Uploaded files (from REST POST /upload)
```

Safe key = original key with non-alphanumeric chars (except `-_.`) replaced by `_`.

## Common Workflows

### Push a file to the whiteboard:
1. Write file to container filesystem (or download from URL)
2. `curl -X POST "http://127.0.0.1:8765/upload?key=<key>" -F "file=@/path/to/file"`
3. File appears in board state and served at `/file/{id}?key=<key>`

### Push text via WebSocket:
1. Connect to `ws://127.0.0.1:8765/ws?key=<key>`
2. Receive init state (includes current rev)
3. Send `{"type": "text_update", "text": "..."}` — server auto-increments rev
4. Close connection after sending

### Push an inline image via WebSocket:
1. Connect to `ws://127.0.0.1:8765/ws?key=<key>`
2. Receive init state, increment rev by 1
3. Send `{"type": "paste_image", "data_url": "data:image/png;base64,...", "rev": N}`
4. Server responds with `image_added` broadcast to all connected clients

### Pull all board content:
1. GET `/download.json?key=<key>` — returns text + images[] + files[] arrays
2. Download individual files via `/file/{id}?key=<key>`
3. Images served at `/img/{id}?key=<key>` (inline)

## Exposing Outside LAN (ngrok)

The whiteboard runs inside the container on port 8765. To share it externally:

### Check existing tunnel

```bash
# Check if ngrok is already running a tunnel to port 8765
curl -s http://127.0.0.1:4040/api/tunnels | python3 -m json.tool 2>/dev/null | grep -i "8765\|public_url" || echo "No ngrok tunnel on port 8765"
```

### Start a new tunnel (ngrok CLI)

```bash
# Kill old tunnel if exists, start fresh:
pgrep -f "ngrok http 8765" | xargs kill 2>/dev/null; sleep 1
ngrok http 8765 --log=stdout &
sleep 3

# Get the public URL:
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])")
echo "Share this link: ${NGROK_URL}/b/meeeeeee"
```

### Or use pyngrok SDK (from Python)

```python
from pyngrok import ngrok
tunnel = ngrok.connect(8765, 'http')
print(f"Public URL: {tunnel.public_url}")
# Share link: {tunnel.public_url}/b/meeeeeee
# Kill: ngrok.disconnect()
```

### Cloudflare Tunnel (alternative)

```bash
cloudflared tunnel --url http://localhost:8765
```

### Important for WebSocket over ngrok

- **Free tier idle timeout ~60s** — clients must implement heartbeat ping/pong (already built into the whiteboard server)
- Clients using WS must reconnect periodically with exponential backoff (1s → 2s → 4s → max 30s)
- Use `wss://` URLs when ngrok serves HTTPS, `ws://` for HTTP

### Share Link Format

Once you have a public URL (e.g., `https://abc123.ngrok-free.app`), share these links:

| Purpose | URL |
|---|---|
| **Board view** (collaborative editing) | `{public_url}/b/meeeeeee` |
| **Control panel** (local only) | `{public_url}/admin` |
| **Download text** | `{public_url}/download?key=meeeeeee` |
| **Full state JSON** | `{public_url}/download.json?key=meeeeeee` |
| **View uploaded file** | `{public_url}/file/{file_id}?key=meeeeeee` |
| **View pasted image** (inline) | `{public_url}/img/{image_id}?key=meeeeeee` |

## Troubleshooting

- **Port 8765 not open**: Server not running. Start with the command above.
- **Inside container**: Use `http://127.0.0.1:8765` (NOT host.docker.internal).
- **From outside LAN**: Use actual host IP or set up a tunnel (ngrok, etc.).
- **Board not found**: Data lives in `whiteboard_instances/<key>/`. New board auto-created on first access.
- **Image paste returns nothing / timeout**: Make sure type is `"paste_image"` NOT `"image_paste"`. The server silently skips unknown message types.
- **File upload gets 409**: File limit reached for this key (500 files or ~5TB). Delete some first via `delete_file` WS message or manually removing from disk.