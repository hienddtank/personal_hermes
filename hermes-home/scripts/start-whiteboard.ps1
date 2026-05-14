# Start the local whiteboard server on Windows host
Set-Location "D:\mkt\python\local_white_board"
Write-Host "Starting whiteboard server..." -ForegroundColor Green

# Check if already running
$existing = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existing) {
    Write-Host "Port 8765 already in use (PID: $($existing.OwningProcess)). Checking if it's us..." -ForegroundColor Yellow
} else {
    # Start the server as a background process
    $job = Start-Process python -ArgumentList "local_whiteboard_app.py" -NoNewWindow -PassThru
    Write-Host "Whiteboard started! PID: $($job.Id)" -ForegroundColor Green
    Write-Host "Access at: http://localhost:8765/b/meeeeee" -ForegroundColor Cyan
    
    # Wait a moment and verify it's listening
    Start-Sleep -Seconds 3
    $check = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($check) {
        Write-Host "Confirmed: Port 8765 is now listening!" -ForegroundColor Green
    } else {
        Write-Host "Warning: Server may still be starting up..." -ForegroundColor Yellow
    }
}
