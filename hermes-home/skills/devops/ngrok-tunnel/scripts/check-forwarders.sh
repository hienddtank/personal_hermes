#!/bin/bash
# check-forwarders.sh - Check for background servers and ngrok forwarding ports
# Usage: bash ~/.hermes/scripts/check-forwarders.sh
# Designed for cron jobs — outputs status report to stdout

echo "=== Forwarder Check: $(date) ==="
echo ""

# 1. Check for ngrok tunnels
echo "--- Ngrok Status ---"
NGROK_STATUS=$(pgrep -a ngrok 2>/dev/null || echo "ngrok: NOT RUNNING")
if [ $? -ne 0 ]; then
    NGROK_STATUS="ngrok: no process found"
fi

# Check for ngrok API (local forwarding port)
NGROK_API_URL="http://localhost:4040/api/tunnels"
NGROK_TUNNELS=""
if curl -s --max-time 3 "$NGROK_API_URL" > /dev/null 2>&1; then
    NGROK_TUNNELS=$(curl -s "$NGROK_API_URL" 2>/dev/null | grep -oP '"public_url":\s*"\K[^"]+' || echo "none detected")
else
    NGROK_TUNNELS="ngrok API not accessible (port 4040)"
fi

echo "Process: $NGROK_STATUS"
echo "Tunnels: $NGROK_TUNNELS"
echo ""

# 2. Check for tmux/screen sessions with long-running processes
echo "--- Session Managers ---"
SCREEN_SESSIONS=$(screen -ls 2>/dev/null | grep -c "Detached\|Attached" 2>/dev/null || echo "0")
TMUX_SESSIONS=$(tmux list-sessions 2>/dev/null | wc -l)

echo "Screen sessions: $SCREEN_SESSIONS"
echo "Tmux sessions: $TMUX_SESSIONS"
echo ""

# 3. Check for long-running server processes
echo "--- Potential Server Processes ---"
SERVER_PROCS=$(ps aux | grep -E '(python.*server|node.*server|npm start|yarn dev|bun run|uvicorn|gunicorn|rails|next dev|webpack-dev)' | grep -v grep || echo "none detected")
echo "$SERVER_PROCS"

# 4. Quick port scan via /proc/net/tcp (works in containers without ss/netstat)
echo ""
echo "--- Listening Ports (via /proc/net/tcp) ---"
awk '{split($2,a,":"); printf "%s\n", strtonum("0x"a[2])}' /proc/net/tcp 2>/dev/null | sort -un | head -20 || echo "Cannot parse /proc/net/tcp"
