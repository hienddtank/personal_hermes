#!/bin/bash
# ============================================================
# Heartbeat Check — System Health & Cleanup Report
# Runs daily via cron (4AM & Noon)
# Usage: bash heartbeat_check.sh
# ============================================================

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SCRIPT_DIR="$HOME/.hermes/scripts"
SESSIONS_DIR="$HERMES_HOME/sessions"

echo "=== Heartbeat Check — $(date -u '+%Y-%m-%d %H:%M UTC') ==="

# 1. Disk usage (sessions + scripts)
echo ""
echo "--- Disk ---"
du -sh "$SESSIONS_DIR" 2>/dev/null || echo "Sessions dir not found"
du -sh "$SCRIPT_DIR" 2>/dev/null || echo "Scripts dir not found"

# 2. Memory
echo ""
echo "--- Memory ---"
free -h 2>/dev/null || echo "free command unavailable"

# 3. Docker containers (if running)
echo ""
echo "--- Docker ---"
docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || echo "Docker not available"

# 4. Listening ports
echo ""
echo "--- Ports ---"
ss -tlnp 2>/dev/null | grep -E ':(8000|8090|3000|8768)' || echo "No known services detected"

# 5. Active cron jobs
echo ""
echo "--- Cron Jobs ---"
cronjob list 2>/dev/null | head -20 || echo "Cron tool unavailable"

# 6. Session count
echo ""
echo "--- Sessions ---"
if [ -d "$SESSIONS_DIR" ]; then
    find "$SESSIONS_DIR" -name "session_*" -type f 2>/dev/null | wc -l
else
    echo "Sessions directory not found at $SESSIONS_DIR"
fi

# 7. Workspace usage
echo ""
echo "--- Workspace ---"
du -sh /workspace/ 2>/dev/null || echo "Workspace dir not found"

echo ""
echo "=== Heartbeat Complete ==="
