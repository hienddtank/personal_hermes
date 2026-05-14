#!/usr/bin/env bash
# ============================================================
# Heartbeat Check — System Health & Cleanup Report
# Runs daily via cron (4AM & Noon)
# ============================================================

set -euo pipefail

echo "=== HEARTBEAT CHECK — $(date '+%Y-%m-%d %H:%M') ==="
echo ""

# 1. Disk Usage
echo "--- DISK USAGE ---"
df -h / /home 2>/dev/null | grep -v tmpfs || df -h / | tail -n +2
echo ""

# 2. Memory
echo "--- MEMORY ---"
free -h 2>/dev/null || echo "free command not available"
echo ""

# 3. Running Docker containers
echo "--- DOCKER CONTAINERS ---"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | head -20 || echo "Docker not running or not accessible"
echo ""

# 4. Active network listeners (ports)
echo "--- LISTENING PORTS ---"
ss -tlnp 2>/dev/null | head -20 || netstat -tlnp 2>/dev/null | head -20 || echo "Cannot list ports"
echo ""

# 5. Cron jobs overview
echo "--- ACTIVE CRON JOBS ---"
cron_jobs_path="$HOME/.hermes/cron/jobs"
if [ -d "$cron_jobs_path" ]; then
    local_count=$(find "$cron_jobs_path" -maxdepth 1 -name "*.json" 2>/dev/null | wc -l)
    echo "Scheduled cron jobs: $local_count"
else
    echo "Cron jobs directory not found at $cron_jobs_path"
fi
echo ""

# 6. Chat history size
echo "--- CHAT HISTORY ---"
chat_dir="$HOME/.hermes/chat_history"
if [ -d "$chat_dir" ]; then
    count=$(find "$chat_dir" -name "*.json" 2>/dev/null | wc -l)
    total=$(du -sh "$chat_dir" 2>/dev/null | cut -f1)
    echo "Session files: $count, Total size: $total"
else
    echo "Chat history directory not found at $chat_dir"
fi
echo ""

# 7. Workspace usage
echo "--- WORKSPACE ---"
ws_dir="$HOME/.hermes/workspace"
if [ -d "$ws_dir" ]; then
    ws_size=$(du -sh "$ws_dir" 2>/dev/null | cut -f1)
    echo "Workspace: $ws_size"
else
    echo "Workspace directory not found"
fi

echo ""
echo "=== END HEARTBEAT ==="
