# Dead Man's Switch via Codex Forwarder

## Architecture
The Codex Forwarder (`local_forwarder.py` on Windows host, port 8768) provides native Docker access from outside the container. This enables a dead man's switch that survives container crashes.

### Components
1. **Forwarder** — Runs on Windows host at `http://host.docker.internal:8768`. Has `docker.exe` in PATH.
2. **Watchdog Script** — Runs on Windows via Task Scheduler. Pings forwarder `/health` on a schedule.
3. **Recreate Endpoint** — `POST /services/{service}/recreate` with `wait_for_url` and `notify` params.

### Why Host-Level, Not Container-Level?
- Container death = all in-container cron jobs die with it.
- Windows Task Scheduler persists across container crashes.
- Forwarder has native Docker access from host — no need for docker-in-docker.

## Implementation

### Step 1: Install Windows Scheduled Task
```cmd
schtasks /Create /TN HermesWatchdog /TR "powershell -ExecutionPolicy Bypass -File D:\mkt\python\hermes\workspace\scripts\watchdog-scheduler.ps1" /SC HOURLY /RL HIGHEST /F
```

### Step 2: Watchdog Script (Python)
The watchdog script should:
1. `GET http://host.docker.internal:8768/health` — check forwarder is alive
2. If unresponsive after N retries → `POST /services/hermes/recreate` with wait_for_url
3. Log results to a persistent Windows file (not inside container)

### Step 3: Test Manually
```cmd
# Verify forwarder is up
curl http://host.docker.internal:8768/health | FindStr "ok"

# Trigger test watchdog run
schtasks /Run /TN HermesWatchdog

# Manually recreate (for testing)
curl -X POST http://host.docker.internal:8768/services/hermes/recreate ^
  -H "Content-Type: application/json" ^
  -d "{\"wait_for_url\":\"http://127.0.0.1:8642/health\",\"notify\":{\"telegram\":true}}"

# Clean up task
schtasks /Delete /TN HermesWatchdog /F
```

## Pitfalls
- **Don't run watchdog inside Docker** — it dies with the container. Must be Windows-host-level.
- **Forwarder must be running** for recreate to work. If forwarder is also down, this pattern can't recover. Consider a separate process (Windows service) that keeps the forwarder alive.
- **`wait_for_url` timeout**: Default is 180s. Ensure the service can start within this window or increase via compose config.
- **Health endpoint path**: Hermes agent health is at `http://127.0.0.1:8642/health`, NOT inside the container name.
- **Telegram notify**: Requires `telegram_configured` to be true in forwarder health response.

## Service Lifecycle Methods Comparison

| Method | Use Case | Blocks? | Wait for Health? |
|--------|----------|---------|------------------|
| `POST /restart` | Quick restart, no waiting | No (fire-and-forget) | No |
| `POST /recreate` | Production self-healing | Yes (until healthy or timeout) | Yes |
| `POST /start` | Service was stopped | No | No |
| `POST /stop` | Graceful shutdown | No | No |

## Notes
- The recreate endpoint runs `docker compose up -d --force-recreate` on the host.
- The forwarder's `run_keepalive_seconds` (default 15s) determines how often it sends heartbeat updates during recreate.
- Telegram notifications are sent after the recreate completes (success or failure).
