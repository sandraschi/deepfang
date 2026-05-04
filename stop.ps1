# DeepFang stop — docker-compose down.
$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

Write-Host "Stopping DeepFang Goliath Stack ..." -ForegroundColor Cyan
docker compose -f docker-compose.yml down
Write-Host "Stack stopped." -ForegroundColor Green
