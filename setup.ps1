# DeepFang setup — idempotent. Run from repo root.
$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

# 1. .env from example if missing
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "[1/4] Creating .env from .env.example ..." -ForegroundColor Cyan
        Copy-Item ".env.example" ".env"
        Write-Host "  Edit .env and set DEEPSEEK_API_KEY before starting." -ForegroundColor Yellow
    } else {
        Write-Host "[1/4] No .env.example; skipping .env." -ForegroundColor DarkGray
    }
} else {
    Write-Host "[1/4] .env exists." -ForegroundColor DarkGray
}

# 2. Python venv
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[2/4] Creating .venv (uv sync) ..." -ForegroundColor Cyan
    uv sync --quiet
    if (-not $?) { throw "uv sync failed" }
} else {
    Write-Host "[2/4] .venv exists." -ForegroundColor DarkGray
}

# 3. Dashboard (Vite)
$DashDir = Join-Path $RepoRoot "dashboard"
if (Test-Path (Join-Path $DashDir "package.json")) {
    Write-Host "[3/4] Installing and building dashboard ..." -ForegroundColor Cyan
    Set-Location $DashDir
    npm install --silent
    if (-not $?) { Set-Location $RepoRoot; throw "npm install failed" }
    npm run build
    if (-not $?) { Set-Location $RepoRoot; throw "npm run build failed" }
    Set-Location $RepoRoot
} else {
    Write-Host "[3/4] Dashboard not found; skipping." -ForegroundColor DarkGray
}

# 4. Configs directory
if (-not (Test-Path "configs\zeroclaw")) {
    Write-Host "[4/4] Creating config stubs ..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path "configs\zeroclaw" -Force | Out-Null
    New-Item -ItemType Directory -Path "configs\moltbot" -Force | Out-Null
} else {
    Write-Host "[4/4] Config directories exist." -ForegroundColor DarkGray
}

Write-Host "Setup done. Run .\start.ps1 to start the stack." -ForegroundColor Green
