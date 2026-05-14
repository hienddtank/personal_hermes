# Inspect Windows Processes from Container

## Use Case
Check what's running on the Windows host (Python processes, GPU usage, hanging scripts) without user intervention. Essential for knowing if long-running experiments are still active.

## Method: Local Forwarder + WinBridge Script File

The `local_forwarder.py` (port 8768) accepts PowerShell scripts via `POST /winbridge/run`. It requires a **file path**, not inline code.

### Step 1: Write PowerShell script to allowed directory
```python
write_file(path="/host/d/mkt/python/hermes/workspace/check_ps.ps1", content='
# Get all python processes with command lines
$procs = Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {
    $cmdLine = try { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine } catch { "<denied>" }
    [PSCustomObject]@{ Name=$_.Name; Id=$_.Id; CPU=[math]::Round($_.CPU,1); MemMB=[math]::Round($_.WorkingSet64/1MB,1); CmdLine=$cmdLine }
}
if ($procs) { $procs | Format-Table -AutoSize } else { "No python processes" }
')
```

### Step 2: Call via forwarder
```bash
curl -s -X POST http://host.docker.internal:8768/winbridge/run \
  -H "Content-Type: application/json" \
  -d '{"script": "D:/mkt/python/hermes/workspace/check_ps.ps1", "timeout": 30}'
```

### Step 3: Parse output
The response has `stdout` (success) and `stderr`. Parse the table from stdout. Look for:
- PID of experiment loop controller (e.g., `smo3_codex_loop.py`)
- PID of child training process (e.g., `-m evolution.trainer`)

### Kill command (if needed)
```bash
curl -s -X POST http://host.docker.internal:8768/winbridge/run \
  -H "Content-Type: application/json" \
  -d '{"script": "Stop-Process -Id 108,1684 -Force; Write-Host \"Killed PIDs 108 and 1684\"", "timeout": 15}'
```

## Notes
- `Write-Object` is NOT a valid PowerShell cmdlet (use `Write-Host` or just output the string directly)
- The forwarder runs under the same Windows user account as the local_forwarder process
- Script files must be in allowed roots: `D:/mkt/python/hermes/workspace/` or `D:/mkt/python/hermes/workspace/scripts/`
