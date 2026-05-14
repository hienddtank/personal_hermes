# Web UI Reference — Dashboard + Open WebUI

## Built-in Web Dashboard (`hermes dashboard`)

Launches on `http://127.0.0.1:9119` by default. Requires `pip install 'hermes-agent[web,pty]'`.

| Flag | Default | Purpose |
|------|---------|---------|
| `--port` | 9119 | Web server port |
| `--host` | 127.0.0.1 | Bind address |
| `--no-open` | — | Skip auto-opening browser |
| `--insecure` | off | Allow non-localhost binding (⚠️ exposes API keys) |
| `--tui` | off | Enable Chat tab via PTY/WebSocket |

### Pages
- **Status** — Version, gateway PID, active sessions (5s refresh)
- **Chat** — Embedded TUI with full slash commands, model picker, tool-call cards. Resume sessions via ▶ button.
- **Config** — Form editor for config.yaml (150+ fields). Save/Reset/Export JSON/Import JSON.
- **API Keys** — .env manager grouped by LLM Providers, Tool Keys, Messaging Platforms, Agent Settings. Redacted previews + delete.
- **Sessions** — FTS5 search, expand messages, color-coded roles, delete via trash icon. Live sessions show pulsing badge.
- **Logs** — agent/errors/gateway logs with live tail (5s poll). Filters: level, component, line count.
- **Analytics** — 7/30/90-day token usage, cost breakdowns, daily charts, per-model tables.
- **Cron** — Create/edit/pause/trigger/delete scheduled jobs. Delivery targets: local/Telegram/Discord/Slack/email.
- **Skills** — Browse/toggle skills by category. Toolsets section shows built-in tools + requirements.

### Security Notes
- No built-in authentication. `--host 0.0.0.0` or `--insecure` exposes everything to LAN.
- Reads/writes `.env` directly — treat dashboard access as full credential access.

### CLI Integration
After updating keys in dashboard, run `/reload` in active CLI session to re-read `.env`.

---

## Open WebUI Integration

External frontend (126k★) connected via Hermes API server port 8642.

### Quick Setup (macOS/Linux)
```bash
cd ~/.hermes/hermes-agent && bash scripts/setup_open_webui.sh
# Launcher created at ~/.local/bin/start-open-webui-hermes.sh
```

### Manual Docker Setup
```yaml
services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    ports: ["3000:8080"]
    environment:
      OPENAI_API_BASE_URL: http://host.docker.internal:8642/v1
      OPENAI_API_KEY: your-secret-key
      ENABLE_OLLAMA_API: "false"  # hides empty Ollama backend
    extra_hosts: ["host.docker.internal:host-gateway"]
    volumes: [open-webui:/app/backend/data]
```

### Key Config Steps
1. Enable API server: `hermes config set API_SERVER_ENABLED true` + set `API_SERVER_KEY`
2. Restart gateway: `hermes gateway restart`
3. Verify: `curl http://127.0.0.1:8642/health` → `{"status": "ok"}`
4. First launch downloads ~150MB embedding models — wait for logs to settle

### Admin UI Config (after first launch)
Profile Avatar → Admin Settings → Connections → OpenAI API → wrench icon → Add connection with URL + key.

⚠️ **Env vars only apply on first launch.** Subsequent changes must be made in Admin UI or by deleting the Docker volume.

### API Modes
- **Chat Completions** (default): `/v1/chat/completions` — recommended, works out of the box
- **Responses** (experimental): `/v1/responses` — server-side state via `previous_response_id`, structured SSE events

### Runtime Notes
- Tools execute on the **API server host** — remote setup = remote tools
- Inline progress streams to UI as markdown (e.g., `` `💻 ls -la` ``)
- Hermes creates an `AIAgent` instance per request with full profile, model, memory, skills

---

## Docs Links
- Dashboard: https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard
- Open WebUI: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/open-webui/
- API Server: https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server/
