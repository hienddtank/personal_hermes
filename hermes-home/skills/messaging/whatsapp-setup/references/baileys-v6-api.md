# Baileys v6 API Cheat Sheet

## Key Exports (v6.7.x — what actually gets installed)
```js
import { makeWASocket, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
```

| Export | Purpose |
|--------|---------|
| `makeWASocket(opts)` | Create a WhatsApp WebSocket connection |
| `useMultiFileAuthState(dir)` | Persist auth state to files on disk |
| `DisconnectReason` | Enum of disconnect reasons (see below) |
| `Browsers` | Pre-built browser user-agent strings |

## Disconnect Reason Codes
```js
DisconnectReason.loggedOut       // User logged out from phone — no reconnect
DisconnectReason.restartRequired // App needs restart — try reconnecting
DisconnectReason.timedOut        // Connection timed out — safe to retry
// Everything else: attempt reconnect (transient network issues)
```

## Socket Methods for Lifecycle
| Method | Usage | Notes |
|--------|-------|-------|
| `sock.destroy()` | Immediate teardown | Use for shutdown or force-closing |
| `sock.logout()` | Graceful disconnect | Sends logout request to WA servers |
| `sock.end()` | Closes connection | Lower-level than destroy |

## ⚠️ Critical Pitfalls

### `useMultiFileAuthState` IS async — MUST await
`useMultiFileAuthState(dir)` returns a Promise, NOT the state object directly. You MUST await it:
```js
// ❌ WRONG — returns Promise, destructuring 'creds' fails
const authState = useMultiFileAuthState(dir);
sock = makeWASocket({ auth: authState.state });

// ✅ CORRECT
const authState = await useMultiFileAuthState(dir);
sock = makeWASocket({ auth: authState.state });
```
This is the #1 cause of "Cannot destructure property 'creds' of 'authState'" errors.

## Connection Config Options
```js
{
  auth: state.state,              // from useMultiFileAuthState
  printQRInTerminal: true,        // set false in headless
  browser: ['Hermes Bridge', 'Chrome', '1.2.0'], // custom UA
  connectTimeoutMs: 30_000,       // connection timeout
  keepAliveIntervalMs: 15_000,    // heartbeat interval
}
```

## Message Sending
```js
// Text
await sock.sendMessage(jid, { text: 'Hello!' });

// Image
await sock.sendMessage(jid, { 
  image: fs.readFileSync('/path/to/img.jpg'),
  caption: 'Optional caption'
});

// With options (ephemeral, reactions, etc.)
await sock.sendMessage(jid, { text: 'msg' }, { quoted: message });
```

## ESM / CJS Import Pitfalls
| Package | ❌ Wrong (ESM named) | ✅ Correct |
|---------|---------------------|-----------|
| qr-image | `import { toData } from 'qr-image'` | `import pkg from 'qr-image'; const { toData } = pkg;` |
| qrcode-terminal | Same issue | `import qrcodeTerminal from 'qrcode-terminal'` |

## Common Status Codes (Baileys v6)
| Code | Meaning | Reconnect? |
|------|---------|-----------|
| 401 | Invalid credentials / logged out | No |
| 428 | Too many connections (same number) | Yes, after disconnecting old one |
| 436 | Retry needed (transient) | Yes |
| 449 | Rate limited | Wait and retry |
