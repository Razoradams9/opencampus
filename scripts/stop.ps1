#Requires -Version 5.1
<#
  OpenCampus - stop the local API, website and database.
  Double-click "Stop OpenCampus.cmd", or run:
      powershell -ExecutionPolicy Bypass -File scripts\stop.ps1
  Your data is kept; the next start picks up where you left off.
#>

$ErrorActionPreference = 'Continue'
$Root    = Split-Path -Parent $PSScriptRoot
$Compose = Join-Path $Root 'docker-compose.yml'
$EnvFile = Join-Path $Root 'backend\.env'
$RunFile = Join-Path $Root 'backend\.run-pids'

Write-Host ''
Write-Host '  OpenCampus - stopping' -ForegroundColor White

# 1. The windows start.ps1 opened, with everything running inside them
#    (/T also ends child processes: uvicorn's reloader and worker, npm's node).
if (Test-Path -LiteralPath $RunFile) {
    foreach ($line in Get-Content -LiteralPath $RunFile) {
        $id = $line.Trim()
        if ($id -match '^\d+$' -and (Get-Process -Id $id -ErrorAction SilentlyContinue)) {
            & taskkill /PID $id /T /F *> $null
            Write-Host "    Closed OpenCampus window (process $id)"
        }
    }
    Remove-Item -LiteralPath $RunFile -Force -ErrorAction SilentlyContinue
}

# 2. Fallback: anything still listening on the OpenCampus ports.
foreach ($port in @(8000, 5173)) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        & taskkill /PID $listener.OwningProcess /T /F *> $null
        Write-Host "    Stopped the process on port $port"
    }
}

# 3. The database container (data is kept in its Docker volume).
if ((Get-Command docker -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath $EnvFile)) {
    & docker compose -f $Compose --env-file $EnvFile stop
    if ($LASTEXITCODE -eq 0) { Write-Host '    Database stopped (data kept)' -ForegroundColor Green }
}

Write-Host ''
Write-Host '  OpenCampus is stopped.' -ForegroundColor Green
Start-Sleep -Seconds 3
