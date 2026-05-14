#!/bin/bash
# Restart the WhatsApp bridge with health check verification.
# Usage: ./restart-bridge.sh [--port PORT] [--session DIR] [--mode MODE]

PORT="${PORT:-3000}"
SESSION="${1:-}"
MODE="${2:-bot}"

echo "=== Restarting WhatsApp Bridge on port $PORT ==="

# Kill existing bridge
PIDS=$(pgrep -f "whatsapp-bridge/bridge.js" 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "Killing existing bridge processes: $PIDS"
    kill -9 $PIDS 2>/dev/null
    sleep 2
    # Force kill any remaining
    PIDS=$(pgrep -f "whatsapp-bridge/bridge.js" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        kill -9 $PIDS 2>/dev/null
        sleep 1
    fi
    echo "Old bridge killed."
else
    echo "No existing bridge found."
fi

# Start new bridge
cd /opt/hermes-agent/scripts/whatsapp-bridge
if [ -n "$SESSION" ]; then
    node bridge.js --port $PORT --session "$SESSION" --mode "$MODE" &
else
    node bridge.js --port $PORT --mode "$MODE" &
fi

# Wait and verify
echo "Waiting for bridge to start..."
for i in $(seq 1 10); do
    sleep 2
    if curl -s "http://localhost:$PORT/health" | grep -q 'status'; then
        echo "Bridge is running! Health:"
        curl -s "http://localhost:$PORT/health"
        echo ""
        exit 0
    fi
    echo "  Attempt $i/10..."
done

echo "ERROR: Bridge failed to start within 20 seconds."
exit 1
