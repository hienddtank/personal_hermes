param(
    [int]$Port = 8642,
    [string]$HostName = "127.0.0.1",
    [string]$NgrokPath = "",
    [string]$AuthToken = $env:NGROK_AUTHTOKEN,
    [switch]$Background,
    [int]$InspectPort = 4040
)

$ErrorActionPreference = "Stop"

function Find-Ngrok {
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
    $candidates = @()

    if ($NgrokPath) {
        $candidates += $NgrokPath
    }

    $localExe = Join-Path $repoRoot "ngrok.exe"
    if (Test-Path -LiteralPath $localExe) {
        $candidates += $localExe
    }

    $cmd = Get-Command ngrok -ErrorAction SilentlyContinue
    if ($cmd) {
        $candidates += $cmd.Source
    }

    $storePath = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\ngrok.exe"
    if (Test-Path -LiteralPath $storePath) {
        $candidates += $storePath
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        try {
            & $candidate version *> $null
            return $candidate
        } catch {
            Write-Warning "Found ngrok candidate but it is not runnable: $candidate"
        }
    }

    throw "No runnable ngrok.exe was found. The Microsoft Store alias may exist but be unavailable. Open ngrok once from the Start menu, download ngrok.exe into D:\mkt\python\hermes, or pass -NgrokPath C:\path\to\ngrok.exe."
}

function Test-LocalPort {
    param([string]$TargetHost, [int]$TargetPort)

    $result = Test-NetConnection -ComputerName $TargetHost -Port $TargetPort -WarningAction SilentlyContinue
    if (-not $result.TcpTestSucceeded) {
        Write-Warning "Nothing is listening at http://${TargetHost}:$TargetPort yet. Start the Docker service first if this tunnel should be usable now."
    }
}

function Get-NgrokTunnels {
    param([int]$ApiPort)

    try {
        return Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/api/tunnels" -TimeoutSec 2
    } catch {
        return $null
    }
}

$ngrok = Find-Ngrok
$target = "http://${HostName}:$Port"

if ($AuthToken) {
    & $ngrok config add-authtoken $AuthToken | Out-Host
}

Test-LocalPort -TargetHost $HostName -TargetPort $Port

Write-Host "Starting ngrok tunnel for $target"
Write-Host "ngrok local inspection API: http://127.0.0.1:$InspectPort"

if ($Background) {
    $args = @("http", $target, "--log=stdout", "--inspect=true")
    $process = Start-Process -FilePath $ngrok -ArgumentList $args -PassThru -WindowStyle Minimized

    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        $tunnels = Get-NgrokTunnels -ApiPort $InspectPort
        if ($tunnels -and $tunnels.tunnels.Count -gt 0) {
            $publicUrls = $tunnels.tunnels | ForEach-Object { $_.public_url }
            Write-Host "ngrok process id: $($process.Id)"
            Write-Host "Public URL(s):"
            $publicUrls | ForEach-Object { Write-Host "  $_" }
            exit 0
        }
    }

    Write-Host "ngrok process id: $($process.Id)"
    Write-Warning "Tunnel started, but no public URL was available from the local ngrok API yet."
    exit 0
}

& $ngrok http $target --log=stdout --inspect=true
