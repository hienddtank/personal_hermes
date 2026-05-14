---
name: Ngrok Forwarding
description: Start and troubleshoot host-side ngrok tunnels for Docker-published Hermes services
version: 1.0
author: Hermes Agent
---

# Ngrok Forwarding Skill

Use this skill when the agent needs to expose a local Hermes service outside the LAN with ngrok.

## Design

The ngrok binary is installed on the Windows host through Microsoft Store:

```powershell
ngrok
```

Do not try to run that Windows binary inside the Linux Docker container. Docker publishes the service ports to Windows, then the host-side `ngrok.exe` tunnels `127.0.0.1:<port>`.

## Common Tunnels

- Hermes API: `127.0.0.1:8642`
- Open WebUI: `127.0.0.1:3000`
- Firecrawl API: `127.0.0.1:3002`
- Codex local forwarder: `127.0.0.1:8768`

## Start Hermes API Tunnel

From `D:\mkt\python\hermes` on the Windows host:

```powershell
powershell -ExecutionPolicy Bypass -File .\devops\ngrok-forwarding\start-ngrok.ps1 -Port 8642 -Background
```

The script prints the public ngrok URL when the local ngrok API reports it.

## Docker Fallback

If the Microsoft Store `ngrok.exe` alias is not runnable, use the optional compose profile:

```powershell
$env:NGROK_AUTHTOKEN = "<token>"
docker compose --profile ngrok up -d ngrok
```

The Docker ngrok inspection API is published at `http://127.0.0.1:39043`.

## Start Other Service Tunnels

```powershell
powershell -ExecutionPolicy Bypass -File .\devops\ngrok-forwarding\start-ngrok.ps1 -Port 3000 -Background
powershell -ExecutionPolicy Bypass -File .\devops\ngrok-forwarding\start-ngrok.ps1 -Port 3002 -Background
powershell -ExecutionPolicy Bypass -File .\devops\ngrok-forwarding\start-ngrok.ps1 -Port 8768 -Background
```

## Auth Token

If ngrok has not been configured yet, set `NGROK_AUTHTOKEN` for the current PowerShell session before starting the tunnel:

```powershell
$env:NGROK_AUTHTOKEN = "<token>"
powershell -ExecutionPolicy Bypass -File .\devops\ngrok-forwarding\start-ngrok.ps1 -Port 8642 -Background
```

The script calls `ngrok config add-authtoken` only when `NGROK_AUTHTOKEN` or `-AuthToken` is supplied.

## Check Status

```powershell
Invoke-RestMethod http://127.0.0.1:4040/api/tunnels
```

Look for `public_url`. Use the `https://...ngrok-free.app` or `https://...ngrok.app` URL externally.

## Stop Tunnels

```powershell
Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process
```

## Troubleshooting

- If the script warns that nothing is listening on the target port, run `docker compose up -d hermes` or start the relevant service first.
- If `ngrok` is not found or says "The file cannot be accessed by the system", the Microsoft Store app execution alias is present but not runnable from this shell. Open ngrok once from the Start menu, download the standalone `ngrok.exe` into `D:\mkt\python\hermes`, or pass a direct path:

```powershell
powershell -ExecutionPolicy Bypass -File .\devops\ngrok-forwarding\start-ngrok.ps1 -Port 8642 -NgrokPath C:\path\to\ngrok.exe -Background
```
- If port `4040` is already used, rerun with another inspection port only after checking the existing ngrok process.
- Do not expose the Codex local forwarder (`8768`) publicly unless you explicitly need it; it can execute local Codex tasks on approved paths.
