#!/usr/bin/env bash
# check-forwarders.sh — Check for active forwarding tunnels and background servers
# Usage: bash check-forwarders.sh [--json]
# Output: Human-readable summary (or JSON with --json flag)

set -euo pipefail

NGROK_FOUND=false
CLOUDFLARED_FOUND=false
OTHER_TUNNELS=()
LISTENING_PORTS=()
BACKGROUND_SERVICES=()

# --- Check forwarding tools ---
command -v ngrok &>/dev/null && NGROK_FOUND=true
command -v cloudflared &>/dev/null && CLOUDFLARED_FOUND=true
for t in localtunnel frp serveo; do
  command -v "$t" &>/dev/null && OTHER_TUNNELS+=("$t")
done

# --- Check listening ports (state 0A = LISTEN) ---
while IFS= read -r line; do
  local_hex=$(echo "$line" | awk '{print $2}')
  port_hex=$(echo "$local_hex" | rev | cut -d: -f1 | rev)
  port_dec=$((16#${port_hex}))
  LISTENING_PORTS+=("$port_dec")
done < <(cat /proc/net/tcp 2>/dev/null | awk '$4=="0A" {print $0}')

# --- Check background services ---
while IFS= read -r proc; do
  [[ -n "$proc" ]] && BACKGROUND_SERVICES+=("$proc")
done < <(ps aux | grep -E '(ngrok|cloudflared|localtunnel|frp|server|uvicorn|gunicorn|node|streamlit)' | grep -v grep || true)

# --- Output ---
if [[ "${1:-}" == "--json" ]]; then
  echo '{
    "ngrok_installed": '"$NGROK_FOUND"',
    "cloudflared_installed": '"$CLOUDFLARED_FOUND"',
    "other_tunnel_tools": '"$(printf '%s,' "${OTHER_TUNNELS[@]+"${OTHER_TUNNELS[@]}"}" | sed 's/,$//')"',
    "listening_ports": '"$(printf '%s,' "${LISTENING_PORTS[@]+"${LISTENING_PORTS[@]}"}" | sed 's/,$//')"',
    "background_services_count": '"${#BACKGROUND_SERVICES[@]}"'
  }'
else
  echo "=== Forwarder Check ==="
  echo "ngrok:         $([ "$NGROK_FOUND" = true ] && echo '✅ installed' || echo '❌ not installed')"
  echo "cloudflared:   $([ "$CLOUDFLARED_FOUND" = true ] && echo '✅ installed' || echo '❌ not installed')"
  [[ ${#OTHER_TUNNELS[@]} -gt 0 ]] && echo "other tools:   ${OTHER_TUNNELS[*]}" || echo "other tools:   none"

  echo ""
  echo "=== Listening Ports ==="
  if [[ ${#LISTENING_PORTS[@]} -eq 0 ]]; then
    echo "  (none)"
  else
    for p in "${LISTENING_PORTS[@]}"; do
      echo "  :$p"
    done
  fi

  echo ""
  echo "=== Background Services ==="
  if [[ ${#BACKGROUND_SERVICES[@]} -eq 0 ]]; then
    echo "  (none)"
  else
    printf '%s\n' "${BACKGROUND_SERVICES[@]}" | head -20
    [[ ${#BACKGROUND_SERVICES[@]} -gt 20 ]] && echo "  ... and $(( ${#BACKGROUND_SERVICES[@]} - 20 )) more"
  fi

  echo ""
  if ! $NGROK_FOUND && ! $CLOUDFLARED_FOUND && [[ ${#BACKGROUND_SERVICES[@]} -eq 0 ]]; then
    echo "🟢 All clear — no forwarders or tunnels active."
  else
    echo "⚠️  Forwarders or services detected — review above."
  fi
fi
