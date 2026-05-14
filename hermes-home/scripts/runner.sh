#!/bin/bash
# Runner: Start email hunter during inactive hours, stop at 7am GMT+7
# User inactive: 10pm-7am GMT+7 = 3pm-0am UTC
# Run from 15:00 UTC to 23:59 UTC, kill at 0:00+ UTC

CURRENT_UTC_HOUR=$(date -u +%H)

# Kill zone: 0am-14pm UTC (7am-7pm GMT+7) → user is awake
if [ "$CURRENT_UTC_HOUR" -ge 0 ] && [ "$CURRENT_UTC_HOUR" -lt 15 ]; then
    pkill -f batch_email_hunter 2>/dev/null
    echo "🛑 Stopped (GMT+7 hour: $(( CURRENT_UTC_HOUR + 7 ))). Resumes at 3pm UTC."
    exit 0
fi

# Run zone: 3pm-11pm UTC (10pm-6am GMT+7) → user is sleeping
if pgrep -f batch_email_hunter > /dev/null 2>&1; then
    echo "✓ Already running"
    exit 0
fi

cd /host/d/mkt/python/hermes/workspace/fish_profs
nohup python3 batch_email_hunter.py >> email_hunt.log 2>&1 &
echo "▶ Started (PID: $!)"
