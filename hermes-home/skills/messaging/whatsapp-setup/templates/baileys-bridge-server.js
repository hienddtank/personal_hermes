/**
 * Hermes WhatsApp Bridge — Minimal Baileys v6 HTTP Server Template
 * 
 * Drop-in scaffold for a multi-number WhatsApp bridge using @whiskeysockets/baileys.
 * Copy and modify as needed; see SKILL.md for API differences and pitfalls.
 */

import express from 'express';
import { makeWASocket, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import qrcodeTerminal from 'qrcode-terminal';
import path from 'path';
import { fileURLToPath } from 'url';
import qrImagePkg from 'qr-image';
const { toData } = qrImagePkg;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = parseInt(process.env.BRIDGE_PORT || '3010', 10);
const SESSIONS_DIR = process.env.SESSIONS_DIR || path.join(__dirname, 'sessions');

const sockets = new Map();
const connectedNumbers = new Set();
const qrCodeCache = new Map();

// ── Helpers ───────────────────────────────────────────────────────────────
function getAuthState(number) {
  const dir = path.join(SESSIONS_DIR, number.replace(/[@/]/g, '_'));
  if (!require('fs').existsSync(dir)) require('fs').mkdirSync(dir, { recursive: true });
  return useMultiFileAuthState(dir);
}

function createSocket(number) {
  const { state, saveCreds } = getAuthState(number);
  
  const sock = makeWASocket({
    auth: state,
    printQRInTerminal: true,
    browser: ['Hermes Bridge', 'Chrome', '1.2.0'],
    connectTimeoutMs: 30_000,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, qr, lastDisconnect } = update;

    if (qr) qrcodeTerminal.generate(qr, { small: true }, (code) => console.log(code));

    if (qr) {
      try {
        qrCodeCache.set(number, qr);
      } catch {} // qr may not be renderable by qr-image in all environments
    }

    if (connection === 'open') {
      console.log(`[number:${number}] ✓ Connected`);
      connectedNumbers.add(number);
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode ?? 500;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut &&
                              statusCode !== DisconnectReason.restartRequired &&
                              statusCode !== DisconnectReason.timedOut;
      
      console.log(`[number:${number}] Connection closed: ${statusCode}. Reconnect: ${shouldReconnect}`);
      connectedNumbers.delete(number);
      sockets.delete(number);

      if (shouldReconnect) {
        setTimeout(() => createSocket(number), 3000);
      }
    }
  });

  sock.ev.on('messages.upsert', ({ messages }) => {
    for (const msg of messages) {
      if (!msg.message || !msg.key) continue;
      const body = msg.conversation || msg.extendedTextMessage?.text;
      console.log(`[number:${number}] ${msg.key.remoteJid}: ${body}`);
      // Forward to Hermes or process here
    }
  });

  return sock;
}

// ── Express Server ────────────────────────────────────────────────────────
const app = express();
app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ service: 'whatsapp-bridge', port: PORT, online: connectedNumbers.size });
});

app.post('/connect/:number', async (req, res) => {
  const number = req.params.number;
  if (sockets.has(number)) return res.json({ success: true, message: 'Already connected', number });
  sockets.set(number, createSocket(number));
  res.json({ success: true, message: 'Connecting...', number });
});

app.get('/qr/:number', (req, res) => {
  const qr = qrCodeCache.get(req.params.number);
  if (!qr) return res.status(404).json({ error: 'QR not ready' });
  try {
    const img = toData(qr);
    res.json({ qr: `data:image/png;base64,${img.toString('base64')}` });
  } catch (e) {
    res.status(500).json({ error: 'Failed to render QR' });
  }
});

app.get('/numbers', (req, res) => {
  res.json({
    numbers: [...sockets.keys()].map(n => ({
      number: n.replace('@s.whatsapp.net', ''),
      connected: connectedNumbers.has(n),
    })),
  });
});

app.post('/send', async (req, res) => {
  const { number, to, message } = req.body;
  const sock = sockets.get(number);
  if (!sock || !connectedNumbers.has(number)) {
    return res.status(503).json({ error: 'Number not connected' });
  }
  try {
    await sock.sendMessage(to + '@s.whatsapp.net', { text: message });
    res.json({ success: true, to });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`WhatsApp bridge running on port ${PORT}`);
});
