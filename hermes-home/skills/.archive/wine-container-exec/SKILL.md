---
name: wine-container-exec
description: Run Windows .exe files inside the Linux container using Wine + Xvfb virtual display with screenshot capture.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [wine, windows-execution, gui-testing, xvfb, docker]
---

# Wine Container Execution — Run Windows .exe files inside the container

Run Windows executables directly from my Linux container using Wine + Xvfb virtual display.

## Prerequisites (already installed)
- Wine 8.0
- Xvfb (virtual framebuffer)
- fluxbox (window manager)
- imagemagick (`import` for screenshots)

## Setup (if Wine not already configured)
```bash
# Install dependencies
apt-get install -y wine xvfb fluxbox x11-utils imagemagick

# Initialize Wine prefix
WINEPREFIX=/root/.wine WINEDEBUG=-all wineboot --init

# Create mount point for D:/ Windows files
mkdir -p /root/.wine/drive_c/tools/link_to_tools
```

## Start Xvfb session (each container session)
```bash
Xvfb :99 -screen 0 1920x1080x24 -ac &
sleep 1
fluxbox &>/dev/null &
sleep 1
export DISPLAY=:99
```

## Run a Windows .exe from my container
```bash
wine "/path/to/windows/app.exe" [args...]

# Examples:
wine "/host/d/mkt/python/hermes/workspace/LocalWhiteboard.exe"
wine "/host/d/mkt/python/B2C_MSC/dist/SimpleQRGenerator.exe" --args ...
wine '/root/.wine/drive_c/tools/link_to_tools/AnyDesk.exe'
```

## Capture GUI app output (screenshots)
```bash
import -window root -display :99 /tmp/screenshot.png
```

## Troubleshooting

**Broken symlinks (self-referencing):**
- If `/host/d/tools/file.exe → /host/d/tools/file.exe`, the file is corrupted on Windows
- Fix: Copy the real .exe binary to D:/tools/ on Windows
- In Wine: `cp -L /host/d/tools/file.exe /root/.wine/drive_c/tools/link_to_tools/` (use -L to follow symlinks)

**GUI apps hang/crash:**
- Needs Xvfb + fluxbox window manager (not just Xvfb alone)
- Some apps (ChromeDriver, complex GUI) may need additional Wine dependencies (winbind for NTLM, etc.)
- Run with timeout: `timeout 10 wine /path/to/app.exe args`

**CLI tools that produce no output:**
- May still be running — check with: `ps aux | grep -i appname | grep -v grep`
- Wine apps in Xvfb are invisible but functional

## Available .exe files (as of last check)
| File | Size | Notes |
|------|------|-------|
| SimpleQRGenerator.exe | 31 MB | QR code generator |
| LocalWhiteboard.exe | 16 MB | GUI app (runs in :99) |
| chromedriver.exe | 20 MB | Needs winbind package |
