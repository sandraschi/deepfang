<#
.SYNOPSIS
    Start DeepFang Goliath execution isolation stack.
    Naked-PC compliant: auto-installs docker and node via winget if missing.
#>

Set-StrictMode -Version Latest

function Require-Command {
    param([string]$Cmd, [string]$WingetId = "")
    if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) {
        if ($WingetId) {
            Write-Host "  Installing $Cmd via winget..." -ForegroundColor Yellow
            winget install --id $WingetId -e --accept-source-agreements --accept-package-agreements
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
            if (-not (Get-Command $Cmd -ErrorAction SilentlyContinue)) {
                Write-Error "$Cmd still not found after install. Restart your terminal and retry."
                exit 1
            }
        } else {
            Write-Error "$Cmd not found and no winget ID provided. Install manually."
            exit 1
        }
    }
}

$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

Write-Host ""
Write-Host "=== DeepFang v0.2.0 - Goliath Execution Isolation Stack ===" -ForegroundColor Cyan
Write-Host ""

# Prerequisites
Write-Host "[prereq] Checking dependencies..." -ForegroundColor DarkGray
Require-Command "docker"  "Docker.DockerDesktop"
Require-Command "node"    "OpenJS.NodeJS.LTS"
Write-Host "[prereq] OK" -ForegroundColor Green

# .env check
if (-not (Test-Path ".env")) {
    Write-Warning ".env not found - copying from .env.example"
    Copy-Item ".env.example" ".env"
    Write-Warning "Edit .env and set DEEPSEEK_API_KEY before the adjudicator will work."
}

$envContent = Get-Content ".env" -Raw -ErrorAction SilentlyContinue
if ($envContent -match "DEEPSEEK_API_KEY=sk-xxxx") {
    Write-Warning "DEEPSEEK_API_KEY is still the placeholder. Adjudication will return deny for all requests."
}

# Kill zombies on our ports (best-effort, may fail on some Windows SKUs)
try {
    $Ports = @(10956, 10957, 10958, 10959, 10960, 10961, 10962, 10963)
    foreach ($Port in $Ports) {
        $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        if ($conn) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-Host "[warn] Port cleanup skipped (Get-NetTCPConnection not available)" -ForegroundColor DarkGray
}

# Build dashboard if needed
$DashDist = Join-Path $RepoRoot "dashboard\dist\index.html"
if (-not (Test-Path $DashDist)) {
    Write-Host "[dashboard] Building React dashboard..." -ForegroundColor Cyan
    Push-Location (Join-Path $RepoRoot "dashboard")
    cmd /c "npm ci --silent"
    cmd /c "npm run build"
    Pop-Location
    Write-Host "[dashboard] Build complete." -ForegroundColor Green
}

# Start observability stack
Write-Host "[1/3] Starting observability stack (Prometheus, Loki, Grafana)..." -ForegroundColor Cyan
docker compose up -d prometheus loki promtail grafana
if ($LASTEXITCODE -ne 0) { Write-Error "Observability stack failed."; exit 1 }

# Start pipeline
Write-Host "[2/3] Building and starting pipeline (sanitizer, deepseek-bridge, worker, supervisor)..." -ForegroundColor Cyan
docker compose up -d --build sanitizer deepseek-bridge worker supervisor
if ($LASTEXITCODE -ne 0) { Write-Error "Pipeline failed to start."; exit 1 }

# Wait for supervisor health
Write-Host "[3/3] Waiting for supervisor readiness..." -ForegroundColor Cyan
$Timeout = 60
$Elapsed = 0
$Ready = $false
while ($Elapsed -lt $Timeout) {
    try {
        $resp = Invoke-WebRequest "http://localhost:10956/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $Ready = $true; break }
    } catch {}
    Start-Sleep 2
    $Elapsed += 2
}

if (-not $Ready) {
    Write-Warning "Supervisor did not become healthy within ${Timeout}s. Check logs:"
    Write-Host "  docker compose logs supervisor" -ForegroundColor DarkGray
} else {
    Write-Host "[3/3] Supervisor healthy." -ForegroundColor Green
}

# Summary
Write-Host ""
Write-Host "DeepFang stack is running:" -ForegroundColor Green
Write-Host "  MCP + API:       http://localhost:10956/mcp"  -ForegroundColor White
Write-Host "  Dashboard:       http://localhost:10957"       -ForegroundColor White
Write-Host "  Sanitizer:       http://localhost:10958/health" -ForegroundColor White
Write-Host "  DeepSeek Bridge: http://localhost:10959/health" -ForegroundColor White
Write-Host "  Worker:          http://localhost:10960/health" -ForegroundColor White
Write-Host "  Grafana:         http://localhost:10963"        -ForegroundColor White
Write-Host ""
Write-Host "Stop: docker compose down" -ForegroundColor DarkGray
Write-Host ""

Start-Process "http://localhost:10957"
