# Hermes Web UI — Minimal Chat Frontend

A thin browser-based chat frontend that connects to the Hermes Agent API server, showing tool calls and streaming responses. Supports file upload to workspace.

## Architecture
- `static/index.html` — Single-page chat UI (vanilla JS, no build step)
- `server.py` — Ultra-thin FastAPI server: serves static files, proxies `/api/chat` → Hermes API at `:8642/v1/chat/completions`, handles file uploads to `/workspace`
- Runs on port **9120**

## Quick Start
```bash
cd <this-dir>
pip install -r requirements.txt
python server.py
# Open http://localhost:9120
```

## Features to Implement (follow TODOs in files)
- [ ] Chat UI with streaming SSE responses
- [ ] Tool call visualization (collapsible cards for each tool use)
- [ ] File upload → saves to workspace, returns path
- [ ] Conversation history (client-side localStorage or server-side)
- [ ] Copy-to-clipboard on messages
