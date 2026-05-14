---
name: whatsapp-setup
description: WhatsApp integration for Hermes Agent — setup, configuration, bridge operations (single-number built-in + multi-number external), QR pairing, message sending/receiving, Baileys v6/v7 pitfalls, and session management.
version: 2.0.0
author: Hermes Agent
tags: [whatsapp, messaging, platform, setup, bridge, baileys]
---

# WhatsApp Integration for Hermes Agent

## When to Use
- User wants Hermes to read/send WhatsApp messages
- Setting up WhatsApp as a new communication channel
- Multi-number WhatsApp support (business lines, personal numbers)
- Diagnosing why WhatsApp contacts don't appear in `send_message(action='list')`
- Bridge troubleshooting, session conflicts, Baileys version issues

## Two Setup Paths

### Path A: Built-in Bridge (port 3000) — DEFAULT ✅
Hermes Agent ships with a production-ready WhatsApp bridge at `/opt/hermes-agent/scripts/whatsapp-bridge/bridge.js`. This is the primary path — it handles QR pairing, message sending, media, and auto-reconnect.

**Verify it's running:** `curl -s http://localhost:3000/health` → `{"status":"connected",...}`

**Single-number mode — drop-in replacement:**
```bash
node bridge.js --port 3000 --session /hermes-home/whatsapp/session --mode bot
```

**Steps to setup if not already running:**
1. Ensure `whatsapp:` section in `~/.hermes/config.yaml`
2. `.env` has `WHATSAPP_ALLOWED_USERS=<phone1>, <phone2>`
3. Gateway auto-starts the bridge — check: `pgrep -f whatsapp-bridge/bridge.js`
4. First connect via gateway (gateway handles QR pairing through Hermes CLI)
5. Verify: `curl -s http://localhost:3000/health`

### Path B: Multi-Number External Bridge (`/workspace/whatsapp-bridge/server.js`)
Use ONLY when you need **multiple simultaneous WhatsApp accounts** on different phone numbers with independent sessions and webhook delivery.

```bash
node bridge.js --port 3000 --sessions-dir /hermes-home/whatsapp \
  --numbers 84912382221,84987654321 --mode bot
```

**Steps:**
1. Use `/workspace/whatsapp-bridge/` — ready-to-deploy multi-number Baileys HTTP bridge
2. Each number gets an isolated auth session on disk (`sessions/<number>/`)
3. Add to `docker-compose.yml` with bind-mount for sessions dir:
   ```yaml
   whatsapp-bridge:
     build: ./whatsapp-bridge
     ports: ["3010:3010"]
     volumes: ["D:/mkt/python/hermes/whatsapp-sessions:/app/sessions"]
     environment:
       HERMES_WEBHOOK_URL: http://hermes:8642/v1/whatsapp-webhook
       BRIDGE_PORT: 3010
   ```
4. Pair numbers via `docker exec whatsapp-bridge node pair-all.js 84912382221`
5. API docs: see `references/multi-number-api.md`

**Decision rule:** Path A for 1–2 numbers (single account). Path B only for true multi-account setups.

## Bridge Endpoints (Built-in / Multi-Number)

The bridge exposes REST endpoints compatible with `gateway/platforms/whatsapp.py`. The Python gateway polls `/messages` (GET, clears queue) and sends via `/send` (POST).

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| GET | `/health` | — | Status, queueLength, uptime, numbers array |
| GET | `/messages` | — | Returns and clears ALL message queues from ALL numbers |
| POST | `/send` | `{chatId, message, replyTo?, number?}` | Send text message |
| POST | `/edit` | `{chatId, messageId, message, number?}` | Edit sent message |
| POST | `/send-media` | `{chatId, filePath, mediaType?, caption?, fileName?, number?}` | Send image/video/audio/document |
| POST | `/typing` | `{chatId, number?}` | Typing indicator (composing) |
| GET | `/chat/:id` | — | Chat info (name, type, participants) |
| POST | `/connect/:number` | — | Start connection for a number (multi-number mode) |
| POST | `/disconnect/:number` | — | Disconnect and clear number state |
| POST | `/pairing-code/:number` | — | Get pairing code for phone login |
| GET | `/numbers` | — | List connected numbers with status |
| GET | `/qr/:number` | — | Get QR image as data URI (base64) |
| GET | `/contacts/:number` | — | List contacts for a number |

The `number` field is optional in single-number mode. In multi-number mode, it's required for send/edit/send-media operations.

### Message Format (what gateway/whatsapp.py expects)
```json
{
  "chatId": "84912382221@s.whatsapp.net",
  "senderId": "84912382221@s.whatsapp.net",
  "body": "Hello world",
  "isGroup": false,
  "messageId": "ABC123...",
  "hasMedia": false,
  "mediaType": null,
  "mediaUrls": []
}
```

Supported media types: `image/jpeg`, `video/mp4`, `audio/ogg;ptt`, `application/pdf`, `image/webp` (sticker), `application/vnd.apple.maps` (location).

## Session Directory Layout

### Single-number mode
```
~/.hermes/whatsapp/session/   # or /hermes-home/whatsapp/session/
  Creds.json
  PreKey-*.json
  SenderKey-*.json
  bridge.pid
```

### Multi-number mode
```
/hermes-home/whatsapp/
  ├── 84912382221_session/      # auth state for each number
  │   ├── creds.json
  │   ├── pre-key-*.json
  │   └── ...
  ├── 84987654321_session/
  │   └── ...
```

## Sending Messages

Use `send_message` tool with target format:
```python
send_message(
    target='whatsapp:Contact Name (dm)',  # from send_message(action='list') output
    text='message content'
)
```

Bare `target='whatsapp'` sends to home channel. Always verify targets via `send_message(action='list')` before sending.

## Installation / First-Time Setup

1. Copy `server.js` as `bridge.js` to `/opt/hermes-agent/scripts/whatsapp-bridge/`
2. Install deps: `cd /opt/hermes-agent/scripts/whatsapp-bridge && npm install qr-image --silent`
3. Kill old bridge: `kill $(pgrep -f 'whatsapp-bridge/bridge')`
4. Start new bridge with same args the gateway expects
5. Verify: `curl -s http://localhost:3000/health`

### Restart Script
See `scripts/restart-bridge.sh` — safe restart with health check verification.

## Critical Pitfalls

### Baileys v7 shutdown crash — `sock.destroy()` no longer exists
In Baileys v7 the socket object lost `.destroy()`. The SIGTERM handler that calls `sock.destroy().catch(...)` crashes with `TypeError: sock.destroy is not a function`, killing the process on every graceful shutdown signal.

**Fix:** use `sock.close()` instead, with a fallback check:
```js
// In SIGTERM/SIGINT handlers:
if (typeof sock.close === 'function') sock.close();
else if (typeof sock.destroy === 'function') sock.destroy().catch(() => {});
```

### Baileys import hangs silently
When running the bridge, `@whiskeysockets/baileys` module load is synchronous but does NOT produce console.log output during import. The process appears to hang for 3–5 seconds on startup — this is normal. **Do not kill it prematurely.** Verify via `curl -s http://localhost:3000/health` instead of relying on logs.

### File in-place replacement doesn't work
If you replace `bridge.js` on disk while the old process is running, Linux keeps the OLD binary in memory. You MUST kill the existing bridge (`kill $(pgrep -f 'whatsapp-bridge/bridge')`) before restarting.

### Stale session 401 silent failure pattern
When WhatsApp invalidates old credentials (device limit reached, manual logout on another device, server-side expiry), the bridge connects to WA servers but gets `Connection Failure 401` immediately — **no QR code, no pairing flow**. The bridge stays in a dead loop.

**Remediation procedure:**
1. Delete stale session: `rm -rf /hermes-home/whatsapp/session/<number>_session/`
2. Clear any tmp dirs: `rm -rf /hermes-home/whatsapp/session/tmp_*_<number>/`
3. Kill bridge process: `kill $(pgrep -f 'whatsapp-bridge/bridge')`
4. Wait 5 seconds for gateway to detect and auto-restart with clean state
5. Verify health: `curl -s http://localhost:3000/health`
6. If still disconnected, initiate pairing: `curl -s -X POST http://localhost:3000/pairing-code/<number>`

### Gateway restart race condition
The Hermes gateway auto-restarts the bridge every ~5 minutes on connection timeout (attempt counter /20). **Always wipe stale session files BEFORE triggering a restart**, otherwise the gateway immediately restarts with the same dead credentials and repeats the 401 cycle. The correct order is: delete session → kill process → wait for gateway auto-start → verify health.

### Port conflict from stray node processes
If multiple bridge instances or leftover node processes are running, port EADDRINUSE errors occur on startup. Before starting a new bridge: `kill $(pgrep -f 'whatsapp-bridge/bridge')` and wait until the port is free (`curl http://localhost:3000/health` returns 404 or times out).

### Empty Session — Bridge Running but Disconnected
Bridge health returns `{"status":"disconnected","numbers":[]}` even though the process is alive. Root cause: session directory has no valid credentials (wiped, never paired, or stale Creds.json).

**Diagnosis:**
1. `curl -s http://localhost:3000/health` → status disconnected, numbers empty
2. `ls /hermes-home/whatsapp/session/` → only `bridge.pid`, no creds.json or pre-key files
3. Bridge log shows `Number mode — waiting for POST /connect/<number>`

**Remediation:** Trigger re-pairing:
```bash
curl -s -X POST http://localhost:3000/pairing-code/<phone_number>
# or
curl -s -X POST http://localhost:3000/connect/<phone_number>
```

### Headless QR pairing
QR code scanning requires a physical device — this is impossible inside the Docker container. Use `POST /pairing-code/:number` only if you already have a connected session and want to add another number (Baileys v7 supports phone-number pairing). For initial setup, scan the QR shown in the bridge's startup log on the host machine.

### Terminal Hang on Startup (Headless Environments)
Baileys can hang during startup when it tries to detect the terminal for QR display:
- In Docker exec / headless containers: add `TERM=dumb` env var, OR disable QR with `printQRInTerminal: false`
- For HTTP-served QR codes: still set `printQRInTerminal: true` but serve via HTTP `/qr/:number` endpoint so users get the code as base64 data URI

## Baileys Version Reference

### v6 vs v7 API Differences
- **v6 (npm @whiskeysockets/baileys → 6.7.x):** Uses `sock.destroy()` for shutdown, `DisconnectReason` enum
- **v7:** `sock.destroy()` removed → use `sock.close()`, no `createLegacyDevice()` — just `makeWASocket()` directly

### v6 Critical Pitfalls
- `useMultiFileAuthState(dir)` IS async — MUST await it:
  ```js
  // ❌ WRONG — returns Promise
  const authState = useMultiFileAuthState(dir);
  sock = makeWASocket({ auth: authState.state });

  // ✅ CORRECT
  const authState = await useMultiFileAuthState(dir);
  sock = makeWASocket({ auth: authState.state });
  ```

### ESM / CJS Interop Gotchas
When `"type": "module"` is set in package.json:
- CommonJS packages like `qr-image` must use **default import**: `import pkg from 'qr-image'; const { toData } = pkg;`
  ❌ `import { toData } from 'qr-image'` → throws "Named export not found"
- All Baileys exports work fine with ESM named imports

### Common Status Codes
| Code | Meaning | Action |
|------|---------|--------|
| 401 | Invalid credentials / logged out | Clear session, re-pair |
| 408 | Device removed / timed out | Auto-reconnect or clear creds |
| 428 | Too many connections | Disconnect old one, retry |
| 436 | Retry needed (transient) | Reconnect |
| 449 | Rate limited | Wait and retry |
| 515 | New protocol | Update Baileys version |

## Configuration Pitfalls
- **Empty whatsapp config block:** `whatsapp: {}` in config.yaml means no driver is active — must be populated by `hermes gateway setup whatsapp`
- **WhatsApp not showing in targets:** Gateway isn't running or WhatsApp driver failed to connect. Check: `tail -f ~/.hermes/logs/gateway.log | grep -i whatsapp`
- **Memory limit blocking session pooling:** When adding memory entries, check current usage first — replacing/shortening existing entries may be needed
- **Backslash escaping bug in memory tool:** Windows path entries with backslashes can cause `old_text` parameter parsing failures

## Related
- See `hermes-agent` skill for gateway setup commands (`hermes gateway setup`)
- See `telegram` skill for parallel multi-platform messaging patterns
