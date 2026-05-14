# File Serving via ngrok Tunnel

## Pattern: python http.server + ngrok CLI for Static Files

Use this when you need the user to download files from the container (MP4, GIF, PNG, reports) via a public URL.

### Step 1: Start HTTP server on a port
```bash
cd /workspace/outputs && python3 -m http.server 8000 &>/tmp/http-server.log &
echo "Server PID: $!"
```

### Step 2: Configure ngrok auth (if not already done)
```bash
export NGROK_AUTHTOKEN="YOUR_TOKEN"
ngrok config add-authtoken "$NGROK_AUTHTOKEN"
# Token persists in ~/.config/ngrok/ngrok.yml after first use
```

### Step 3: Start ngrok CLI tunnel (not SDK!)
```bash
# IMPORTANT: use ngrok CLI, NOT pyngrok SDK.
# pyngrok tunnels die when the Python process exits.
export NGROK_AUTHTOKEN="YOUR_TOKEN"
ngrok http 8000 --log=stdout &

sleep 5  # wait for tunnel to establish
```

### Step 4: Get the public URL
```bash
# From local ngrok API (port 4040)
curl -s http://127.0.0.1:4040/api/tunnels | python3 -m json.tool | grep public_url
# Output: "public_url": "https://XXXX-XX-XX-XX.ngrok-free.app"

# Or from logs
cat /tmp/ngrok.log | grep "url=" | tail -1
```

### Step 5: Verify access
```bash
curl -s -o /dev/null -w "%{http_code}" "https://XXXX-XX-XX-XX.ngrok-free.app/"
# Should return 200
```

## Auto-Generate index.html Landing Page

Create a clean landing page so the user can browse and download multiple files:

```python
files_info = [
    ("slur-axis-walk.mp4", "125 KB"),
    ("slur-axis-walk.gif", "animated GIF"),
    ("slur-axis-summary.png", "static plot"),
]

html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Hermes Outputs</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #333; padding: 40px; }
        h1 { font-size: 24px; margin-bottom: 8px; }
        .subtitle { color: #666; margin-bottom: 30px; font-size: 14px; }
        .file-list { list-style: none; max-width: 600px; }
        .file-list li { background: white; border-radius: 8px; padding: 16px 20px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); display: flex; align-items: center; justify-content: space-between; }
        .file-name { font-weight: 600; font-size: 15px; }
        .file-size { color: #888; font-size: 13px; margin-left: 10px; }
        .download-btn { background: #2563eb; color: white; border: none; padding: 8px 18px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600; }
    </style>
</head>
<body>
    <h1>Hermes Outputs</h1>
    <p class="subtitle">Generated Apr 30, 2026</p>
    <ul class="file-list">
"""
for name, size in files_info:
    html += f'        <li><span><span class="file-name">{name}</span><span class="file-size">{size}</span></span><a href="{name}" class="download-btn">Download</a></li>\n'
html += """    </ul>
</body>
</html>"""

with open("index.html", "w") as f:
    f.write(html)
```

## Tunnel Management

### Check if tunnel is alive
```bash
curl -s http://127.0.0.1:4040/api/tunnels | python3 -m json.tool
# Look for your tunnel with state "online"
```

### Kill all ngrok processes
```bash
pkill -f ngrok
```

### Kill specific Python HTTP server
```bash
pkill -f "http.server 8000"
```

## Common Pitfalls

1. **pyngrok SDK tunnels die on process exit** — always use `ngrok http` CLI for persistent access
2. **Height must be divisible by 2 for libx264** — use `scale=WIDTH:-1:flags=lanczos,split[s0][s1];[s0]scale=W:H_PADDED[pad]` to fix odd heights
3. **ngrok free tier randomizes URL each session** — don't hardcode URLs; always query the API for current URL
4. **http.server directory listing** — python -m http.server serves the current directory with clickable files by default
