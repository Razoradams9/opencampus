#Requires -Version 5.1
<#
  OpenCampus - start everything for local development.

  Double-click "Start OpenCampus.cmd" in the project folder, or run:
      powershell -ExecutionPolicy Bypass -File scripts\start.ps1

  First run: checks tools, creates backend\.env with fresh secrets, starts the
  database, installs dependencies, migrates, and offers to create demo users.
  Later runs: only does what is needed, then starts the API and website in
  their own windows and opens the browser. Safe to run again at any time.
#>

# Native tools (docker, npm, pip) write progress to stderr. Under "Stop",
# Windows PowerShell 5.1 turns that into errors, so check exit codes instead.
$ErrorActionPreference = 'Continue'

$Root       = Split-Path -Parent $PSScriptRoot
$Backend    = Join-Path $Root 'backend'
$Frontend   = Join-Path $Root 'frontend'
$Compose    = Join-Path $Root 'docker-compose.yml'
$EnvFile    = Join-Path $Backend '.env'
$VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'
$SeedFlag   = Join-Path $Backend '.demo-seeded'
$RunFile    = Join-Path $Backend '.run-pids'   # windows opened by this script, for stop.ps1
$AppUrl     = 'http://localhost:5173'

function Step([string]$Text) { Write-Host ''; Write-Host "==> $Text" -ForegroundColor Cyan }
function Info([string]$Text) { Write-Host "    $Text" }
function Good([string]$Text) { Write-Host "    $Text" -ForegroundColor Green }

function Fail([string]$Text) {
    Write-Host ''
    Write-Host "PROBLEM: $Text" -ForegroundColor Red
    Write-Host ''
    Read-Host 'Press Enter to close'
    exit 1
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-Port([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $attempt = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $attempt.AsyncWaitHandle.WaitOne(300)) { return $false }
        $client.EndConnect($attempt)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-Port([int]$Port, [int]$Seconds) {
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (Test-Port $Port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-Hash([string[]]$Paths) {
    $text = ($Paths | ForEach-Object { (Get-FileHash -Algorithm SHA256 -LiteralPath $_).Hash }) -join ''
    return $text
}

function Read-EnvFile([string]$Path) {
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { $values[$Matches[1]] = $Matches[2].Trim() }
    }
    return $values
}

# Start a command in its own PowerShell window. -EncodedCommand avoids every
# quoting problem with paths that contain spaces.
function Start-Window([string]$Title, [string]$Command) {
    $script = "`$host.UI.RawUI.WindowTitle = '$Title'; $Command"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    $process = Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -EncodedCommand $encoded" -PassThru
    # Remember the window so stop.ps1 can end it together with its child processes.
    Add-Content -LiteralPath $RunFile -Value $process.Id -Encoding Ascii
}

function Quote([string]$Text) { return "'" + ($Text -replace "'", "''") + "'" }

Write-Host ''
Write-Host '  OpenCampus - local start' -ForegroundColor White
Write-Host '  ------------------------'

# ---------------------------------------------------------------- 1. Tools
Step 'Checking tools'

$Python = $null
foreach ($candidate in @('python', 'py')) {
    if (Test-Command $candidate) {
        $version = & $candidate -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version) {
            if ([version]$version -ge [version]'3.11') { $Python = $candidate; break }
        }
    }
}
if (-not $Python) {
    Fail "Python 3.11 or newer was not found. Install it with:  winget install -e --id Python.Python.3.13  then close this window and try again."
}
Good "Python $version"

if (-not (Test-Command 'node')) {
    Fail "Node.js was not found. Install it with:  winget install -e --id OpenJS.NodeJS.LTS  then try again."
}
$nodeVersion = (& node -v).TrimStart('v')
if ([version]$nodeVersion -lt [version]'20.19') { Fail "Node.js $nodeVersion is too old (need 20.19 or newer)." }
Good "Node.js $nodeVersion"

if (-not (Test-Command 'docker')) {
    Fail "Docker was not found. Install Docker Desktop:  winget install -e --id Docker.DockerDesktop"
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $dockerDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (Test-Path -LiteralPath $dockerDesktop) {
        Info 'Starting Docker Desktop (this can take a minute)...'
        Start-Process -FilePath $dockerDesktop | Out-Null
        for ($i = 0; $i -lt 90; $i++) {
            Start-Sleep -Seconds 2
            & docker info *> $null
            if ($LASTEXITCODE -eq 0) { break }
        }
    }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { Fail 'Docker is installed but not running. Open Docker Desktop, wait until it says "running", then try again.' }
}
Good 'Docker is running'

# ---------------------------------------------------------------- 2. Configuration
Step 'Configuration'
if (-not (Test-Path -LiteralPath $EnvFile)) {
    $secrets = & $Python -c "import secrets; print(' '.join(secrets.token_urlsafe(32) for _ in range(5)))"
    if ($LASTEXITCODE -ne 0) { Fail 'Could not generate secrets with Python.' }
    $su, $owner, $app, $jwt, $rl = $secrets.Trim().Split(' ')
    $port = 15432  # 5432 is often reserved on Windows
    $lines = @(
        '# Generated by scripts\start.ps1 - local development only. Never commit this file.',
        'OPENCAMPUS_ENV=development',
        "OPENCAMPUS_DB_PORT=$port",
        "OPENCAMPUS_DB_SUPERUSER_PASSWORD=$su",
        "OPENCAMPUS_DB_OWNER_PASSWORD=$owner",
        "OPENCAMPUS_DB_APP_PASSWORD=$app",
        "OPENCAMPUS_DATABASE_URL=postgresql+psycopg://opencampus_app:$app@127.0.0.1:$port/opencampus",
        "OPENCAMPUS_MIGRATION_DATABASE_URL=postgresql+psycopg://opencampus_owner:$owner@127.0.0.1:$port/opencampus",
        "OPENCAMPUS_TEST_DATABASE_URL=postgresql+psycopg://opencampus_app:$app@127.0.0.1:$port/opencampus_test",
        "OPENCAMPUS_TEST_MIGRATION_DATABASE_URL=postgresql+psycopg://opencampus_owner:$owner@127.0.0.1:$port/opencampus_test",
        "OPENCAMPUS_JWT_SECRET=$jwt",
        "OPENCAMPUS_RATE_LIMIT_SECRET=$rl",
        'OPENCAMPUS_COOKIE_SECURE=false',
        "OPENCAMPUS_FRONTEND_URL=$AppUrl"
    )
    Set-Content -LiteralPath $EnvFile -Value $lines -Encoding Ascii
    Good 'Created backend\.env with new random secrets'
} else {
    $existing = Read-EnvFile $EnvFile
    if (-not $existing.ContainsKey('OPENCAMPUS_RATE_LIMIT_SECRET')) {
        $rl = (& $Python -c "import secrets; print(secrets.token_urlsafe(48))").Trim()
        Add-Content -LiteralPath $EnvFile -Value "OPENCAMPUS_RATE_LIMIT_SECRET=$rl" -Encoding Ascii
        Good 'Added the missing rate-limit secret to backend\.env'
    } else {
        Good 'Using existing backend\.env'
    }
}
$envValues = Read-EnvFile $EnvFile
$dbPort = if ($envValues.ContainsKey('OPENCAMPUS_DB_PORT')) { $envValues['OPENCAMPUS_DB_PORT'] } else { '5432' }

# ---------------------------------------------------------------- 3. Database
Step "Database (PostgreSQL in Docker, port $dbPort)"
& docker compose -f $Compose --env-file $EnvFile up -d
if ($LASTEXITCODE -ne 0) {
    Fail "Could not start the database. If the message mentions the port, set a different OPENCAMPUS_DB_PORT in backend\.env and update the four database URLs to match."
}
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    & docker compose -f $Compose --env-file $EnvFile exec -T postgres pg_isready -U postgres *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { Fail 'The database did not become ready. Check Docker Desktop for errors.' }
Good 'Database is up'

# ---------------------------------------------------------------- 4. Backend
Step 'Backend (Python)'
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Info 'Creating virtual environment...'
    & $Python -m venv (Join-Path $Backend '.venv')
    if ($LASTEXITCODE -ne 0) { Fail 'Could not create the Python virtual environment.' }
}
$reqHash = Get-Hash @((Join-Path $Backend 'requirements.txt'), (Join-Path $Backend 'requirements-dev.txt'))
$reqStamp = Join-Path $Backend '.venv\.requirements-hash'
if (-not (Test-Path -LiteralPath $reqStamp) -or (Get-Content -LiteralPath $reqStamp -Raw).Trim() -ne $reqHash) {
    Info 'Installing Python packages (first time takes a few minutes)...'
    & $VenvPython -m pip install --disable-pip-version-check -q -r (Join-Path $Backend 'requirements-dev.txt')
    if ($LASTEXITCODE -ne 0) { Fail 'Installing Python packages failed. See the messages above.' }
    Set-Content -LiteralPath $reqStamp -Value $reqHash -Encoding Ascii
}
Good 'Python packages are up to date'

Push-Location $Backend
$migrated = $false
for ($i = 0; $i -lt 10; $i++) {
    # Right after first creation Postgres restarts once; retry briefly.
    & $VenvPython -m alembic upgrade head
    if ($LASTEXITCODE -eq 0) { $migrated = $true; break }
    Start-Sleep -Seconds 3
}
Pop-Location
if (-not $migrated) { Fail 'Database migration failed. See the messages above.' }
Good 'Database schema is up to date'

# ---------------------------------------------------------------- 5. Frontend
Step 'Frontend (Node.js)'
$lockHash = Get-Hash @((Join-Path $Frontend 'package-lock.json'))
$lockStamp = Join-Path $Frontend 'node_modules\.package-lock-hash'
if (-not (Test-Path -LiteralPath $lockStamp) -or (Get-Content -LiteralPath $lockStamp -Raw).Trim() -ne $lockHash) {
    Info 'Installing website packages...'
    Push-Location $Frontend
    & npm install --no-audit --no-fund
    $npmExit = $LASTEXITCODE
    Pop-Location
    if ($npmExit -ne 0) { Fail 'Installing website packages failed. See the messages above.' }
    Set-Content -LiteralPath $lockStamp -Value $lockHash -Encoding Ascii
}
Good 'Website packages are up to date'

# ---------------------------------------------------------------- 6. Demo accounts (first run only)
if (-not (Test-Path -LiteralPath $SeedFlag)) {
    Step 'Demo accounts'
    Info 'OpenCampus can create fictional demo colleges and students so you can sign in.'
    $answer = Read-Host '    Create them now? (answer n if you already did this before) [Y/n]'
    if ($answer -eq '' -or $answer -match '^(y|yes)$') {
        Info 'Choose one password (12+ characters) for all demo accounts. Typing is hidden.'
        Push-Location $Backend
        & $VenvPython -m app.cli seed-demo
        $seedExit = $LASTEXITCODE
        Pop-Location
        if ($seedExit -eq 0) {
            Set-Content -LiteralPath $SeedFlag -Value 'seeded' -Encoding Ascii
        } else {
            Write-Host '    Demo accounts were not created; you can still register in the app.' -ForegroundColor Yellow
        }
    } else {
        Set-Content -LiteralPath $SeedFlag -Value 'skipped' -Encoding Ascii
        Info 'Skipped. You can create an account on the sign-in page instead.'
    }
}

# ---------------------------------------------------------------- 7. Run
Step 'Starting OpenCampus'
if (Test-Port 8000) {
    Info 'API is already running on port 8000.'
} else {
    # All local browser traffic arrives from 127.0.0.1 through the dev proxy,
    # so the login limit is relaxed for this local window only.
    $api = "Set-Location -LiteralPath $(Quote $Backend); `$env:OPENCAMPUS_RATE_LIMIT_LOGIN_IP = '30/60,300/3600'; " +
           "& $(Quote $VenvPython) -m uvicorn app.main:app --reload --port 8000 --no-proxy-headers"
    Start-Window 'OpenCampus API - close this window to stop it' $api
}
if (Test-Port 5173) {
    Info 'Website is already running on port 5173.'
} else {
    Start-Window 'OpenCampus website - close this window to stop it' "Set-Location -LiteralPath $(Quote $Frontend); npm run dev"
}

if (-not (Wait-Port 8000 60)) { Fail 'The API did not start. Look at the "OpenCampus API" window for the error.' }
if (-not (Wait-Port 5173 60)) { Fail 'The website did not start. Look at the "OpenCampus website" window for the error.' }
Start-Process $AppUrl | Out-Null

Write-Host ''
Write-Host "  OpenCampus is running at $AppUrl" -ForegroundColor Green
Write-Host '  To stop it: double-click "Stop OpenCampus.cmd" (or close the two OpenCampus windows).'
Write-Host '  Reset emails in development:  backend\.dev-mail\  (or: cd backend; .\.venv\Scripts\python.exe -m app.cli dev-mail)'
Write-Host ''
Read-Host 'Press Enter to close this window (OpenCampus keeps running)'
