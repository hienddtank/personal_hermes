@echo off
REM Hermes Watchdog Setup — paste this into Windows CMD (one line)
REM Creates scheduled task that runs watchdog.py every hour, completely outside Docker

SET WORKSPACE=D:\mkt\python\hermes\workspace
SET SCRIPT=%WORKSPACE%\scripts\watchdog.bat
SET LOG=%WORKSPACE%\logs\watchdog.log

REM Create bat wrapper
echo @echo off > "%SCRIPT%"
echo cd /d "%%WORKSPACE%%" >> "%SCRIPT%"
echo if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat >> "%SCRIPT%"
echo python scripts/watchdog.py %%1 ^>^> "%LOG%%2" 2^^>^^&1 >> "%SCRIPT%"

REM Create scheduled task — runs hourly, completely outside Docker
schtasks /Create /TN HermesWatchdog /TR "cmd /c %SCRIPT% check" /SC HOURLY /RL HIGHEST /F
if errorlevel 1 (
    echo Failed to create scheduled task
) else (
    echo [OK] Scheduled task 'HermesWatchdog' created — runs hourly on Windows host
    echo        Test it now: schtasks /Run /TN HermesWatchdog
    echo        Remove it:   schtasks /Delete /TN HermesWatchdog /F
)
