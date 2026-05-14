/* Hermes Web UI — Chat Client. Streams from Hermes API via /api/chat proxy. */
const API = "/api";
let conversation = [];
let isStreaming = false;

const messagesEl = document.getElementById("messages");
const promptEl = document.getElementById("prompt");
const sendBtn = document.getElementById("send");

async function sendMessage(text) {
  if (!text.trim() || isStreaming) return;
  appendMessage("user", text);
  conversation.push({ role: "user", content: text });
  promptEl.value = "";
  promptEl.style.height = "auto";

  isStreaming = true;
  sendBtn.disabled = true;

  // TODO: POST /api/chat with streaming, parse SSE, render tool calls
  isStreaming = false;
  sendBtn.disabled = false;
}

function appendMessage(role, content) {
  const bubble = document.createElement("div");
  bubble.className = `message ${role}`;
  bubble.innerHTML = `<strong>${role === "user" ? "You" : "Hermes"}</strong><br>${escapeHtml(content)}`;
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(t) { const d = document.createElement("div"); d.textContent = t; return d.innerHTML; }

promptEl.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(promptEl.value); }
});
sendBtn.addEventListener("click", () => sendMessage(promptEl.value));
promptEl.addEventListener("input", () => { promptEl.style.height = "auto"; promptEl.style.height = Math.min(promptEl.scrollHeight, 160) + "px"; });
