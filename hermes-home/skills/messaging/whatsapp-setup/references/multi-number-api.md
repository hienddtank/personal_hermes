# Multi-Number WhatsApp Bridge API (`/workspace/whatsapp-bridge/server.js`)

Use this ONLY when you need multiple simultaneous WhatsApp accounts. Single-number setups should use Path A (built-in bridge on port 3000).

**Base URL:** `http://localhost:3010` or `http://host.docker.internal:3010`
**Default port:** 3010 (configurable via `BRIDGE_PORT` env var)

## Endpoints

### Connect a Number (Start Session + QR Pairing)
```
POST /connect/:number
```
- `:number` — phone number digits only, e.g. `84912382221`
- Creates independent auth session at `sessions/<number>/`
- Returns immediately; QR is cached and available via `/qr/`
- **Response:** `{ success: true, message: "Connecting...", number: "84912382221" }`

### Get QR Code (Base64 Data URI)
```
GET /qr/:number
```
- Returns QR code for the connected session as a PNG data URI
- **Response:** `{ qr: "data:image/png;base64,iVBORw0KGgo..." }`
- The bridge prints QR to terminal AND caches it here simultaneously

### Request Pairing Code (SMS Alternative)
```
POST /pairing-code/:number
```
- Use this instead of QR code pairing — sends a 6-character code via SMS
- Returns the pairing code in the response
- **Response:** `{ success: true, code: "ABCD-EF", message: "..." }`

### Disconnect a Number
```
POST /disconnect/:number
```
- Logs out and removes session data for this number
- **Response:** `{ success: true, message: "Disconnected 84912382221" }`

### Send a Message
```
POST /send
Body: { "number": "84912382221", "to": "8491xxxxxxx", "message": "Hello", "type": "text", "media": null, "extra": {} }
```
- `number` — the WhatsApp account to send FROM (must be connected)
- `to` — recipient phone number (digits only; will be normalized with `@s.whatsapp.net`)
- `message` — text content
- `type` — `"text"` or `"media"`
- `media` — optional, for media messages: `{ type: "image", path: "/host/path" }`
- `extra` — additional Baileys options (quoted, reaction, etc.)
- Messages queued automatically if the socket is not yet connected
- **Response:** `{ success: true, sent: true, number: "84912382221", to: "8491xxxxxxx" }`

### List Numbers and Status
```
GET /numbers
```
- **Response:**
  ```json
  {
    "numbers": [
      { "number": "84912382221", "connected": true, "state": "open" },
      { "number": "84374584688", "connected": false, "state": "disconnected" }
    ],
    "total": 2,
    "online": 1
  }
  ```

### Health Check
```
GET /health
```
- **Response:** `{ "service": "whatsapp-bridge", "port": 3010, "numbers": [...] }`

### List Contacts (Per Number)
```
GET /contacts/:number
```
- Lists contacts stored in this number's session
- **Response:** `{ "number": "84912382221", "total": 42, "contacts": [...] }`

## Session Storage

Sessions are stored on disk at `<SESSIONS_DIR>/<number>/` (default: `sessions/<number>/`).

Each session directory contains Baileys auth files (`Creds.json`, `PreKey`, `SenderKey`, etc.) that survive container restarts.

**Important:** If a user re-pairs a number, delete the session dir first:
```bash
rm -rf sessions/84912382221/*
POST /connect/84912382221  # will generate fresh QR
```

## Architecture Notes

- **Per-number isolation:** Each number has its own `makeWASocket` instance with independent auth state. No session collision.
- **Auto-reconnect:** On transient disconnects (network, timeout), the bridge auto-reconnects after 3 seconds.
- **Logged out / auth error:** If disconnected due to `loggedOut`, `restartRequired`, or `timedOut`, does NOT auto-reconnect — user must re-pair.
- **Message queuing:** Messages sent via `/send` before a socket is connected are queued and sent once connection opens.
- **Webhook delivery:** Incoming messages are forwarded to `HERMES_WEBHOOK_URL` (configurable env var). Falls back to console log if no webhook configured.
- **ESM compatibility:** Uses Node 22 ESM (`"type": "module"` in package.json). QR-image is CJS — import as default: `import pkg from 'qr-image'; const { toData } = pkg;`

## Docker Deployment

```yaml
whatsapp-bridge:
  build: ./whatsapp-bridge
  container_name: whatsapp-bridge
  ports:
    - "3010:3010"
  volumes:
    - D:/mkt/python/hermes/whatsapp-sessions:/app/sessions
  environment:
    HERMES_WEBHOOK_URL: http://hermes:8642/v1/whatsapp-webhook
    BRIDGE_PORT: 3010
```

Sessions bind-mounted to host path survive container rebuilds. No QR re-pairing needed after `docker compose up -d --build`.

## Comparison vs Built-in Bridge (Port 3000)

| Feature | Built-in (port 3000) | Multi-Number (port 3010) |
|---------|---------------------|--------------------------|
| Numbers supported | 1 | Unlimited |
| Message delivery | Poll (`/messages`) | Webhook push |
| QR serving | Terminal only | HTTP endpoint + terminal |
| Session persistence | `~/.hermes/whatsapp/session/` | Bind-mounted volume |
| Auto-reconnect | Yes | Yes |
| Message queuing | No | Yes (queue while connecting) |
| Pairing code SMS | No | Yes (`/pairing-code/:number`) |
| Best for | Single personal/business account | Multiple accounts, automated workflows |