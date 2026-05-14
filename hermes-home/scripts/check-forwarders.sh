#!/bin/bash
# Check for ngrok tunnels and background forwarded services

echo "=== NGROK STATUS ==="
NGROK_PID=$(pgrep -f ngrok 2>/dev/null)
if [ -n "$NGROK_PID" ]; then
    echo "ngrok is RUNNING (PID: $NGROK_PID)"
    ps aux | grep -E '[n]grok' | head -5
else
    echo "ngrok is NOT running"
fi

echo ""
echo "=== LISTENING PORTS ==="
ss -tlnp 2>/dev/null | head -20 || netstat -tlnp 2>/dev/null | head -20

echo ""
echo "=== COMMON FORWARDING SERVICES ==="
for svc in ngrok cloudflared tunnel; do
    PID=$(pgrep -f "$svc" 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "$svc: RUNNING (PID: $PID)"
        ps aux | grep -E "[${svc:0:1}]$svc" | head -3
    else
        echo "$svc: NOT running"
    fi
done

echo ""
echo "=== BACKGROUND PROCESSES ==="
ps aux --sort=-%cpu | head -10
