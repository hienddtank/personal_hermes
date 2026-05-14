# Case Study: May 2-3 Telegram Outage (2026)

## Timeline

**Last successful interaction**: April 29, ~11:40 UTC — Telegram network errors occurred but recovered.

**Outage begins**: May 1, ~14:56 UTC
```
2026-05-01 14:56:11,714 WARNING gateway.platforms.telegram: [Telegram] Telegram polling conflict (1/3), will retry in 10s. Error: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
2026-05-01 14:56:35,645 WARNING gateway.platforms.telegram_network: [Telegram] Fallback IP 149.154.167.220 failed
2026-05-01 14:56:35,654 WARNING gateway.platforms.telegram: [Telegram] Telegram polling retry failed: Timed out
```

**Outage duration**: ~80 hours (May 1 14:56 → May 4 01:20 UTC) — no inbound messages received.

**Recovery**: Gateway restarted at May 4, 01:20 UTC via SIGTERM shutdown signal. New instance started accepting messages.

## Investigation Steps

### Step 1: Session Search
Session search returned only cron jobs on May 2-3 — no user sessions. Confirmed Telegram connection was down.

### Step 2: Verify Session Files
```bash
ls /hermes-home/sessions/ | grep "2026050[23]"
# Result: Only cron sessions, zero normal (user-initiated) sessions on May 2-3
```

### Step 3: Gateway Log Analysis
```bash
grep "2026-05-0[23]" /hermes-home/logs/gateway.log
# Result: Zero entries — gateway log had a gap from April 29 14:56 to May 4 01:19
```

**Explanation**: The gateway process was still running (receiving SIGTERM on May 4) but the Telegram long-polling connection had failed silently. No new messages were being received, so no log entries were generated for ~80 hours.

### Step 4: Root Cause
The "getUpdates conflict" error on May 1 caused the Telegram polling to fail permanently. The gateway continued running its internal loops (cron jobs still executed) but the Telegram platform handler was disconnected with no automatic recovery mechanism for this specific error type.

## Lessons Learned

1. **Silent failures are dangerous** — A process can appear healthy (running, cron jobs executing) while a critical subsystem is down
2. **getUpdates conflict = permanent disconnect** in practice. Unlike temporary network errors that auto-reconnect, this specific error requires manual intervention
3. **Gateway log gaps indicate no I/O activity** — if gateway.log has a gap between events, the process either crashed or was idle (no messages, no errors logged)
4. **Dual-instance detection** is critical — always verify only one bot instance polls the same token before starting/restarting