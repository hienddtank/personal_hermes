# Set up Windows Scheduled Task for Hermes Watchdog
# Run this ONCE to register the task. Then it runs independently on Windows host.

$taskName = "HermesWatchdog"
$actionPath = r"D:\mkt\python\hermes\workspace\scripts\watchdog.bat"
$actionArgs = "/c python watchdog.py check"

# Create the bat wrapper (Windows path)
$batContent = @"
cd /d D:\mkt\python\hermes\workspace
call venv\Scripts\activate.bat 2>$null
python scripts/watchdog.py %1
"@

[System.IO.File]::WriteAllText($actionPath, $batContent, [System.Text.Encoding]::ASCII)

# Register the task — runs every hour
schtasks /Create /TN $taskName /TR "cmd /c $actionArgs check" /SC HOURLY /RL HIGHEST /F 2>&1 | Write-Host

Write-Host "✅ Scheduled task '$taskName' created."
Write-Host "   Runs every hour on Windows host (outside Docker)."
Write-Host ""
Write-Host "To test immediately:"
Write-Host "   schtasks /Run /TN $taskName"
Write-Host ""
Write-Host "To remove:"
Write-Host "   schtasks /Delete /TN $taskName /F"
