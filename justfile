name := "deepfang"
desc := "Docker-Compose execution isolation stack"
ver := "0.2.0"

# Display the SOTA Industrial Dashboard
default:
    @powershell -NoLogo -Command " \
        $lines = Get-Content '{{justfile()}}'; \
        Write-Host ' [{{name}}] {{desc}} v{{ver}}' -ForegroundColor White -BackgroundColor Cyan; \
        Write-Host '' ; \
        $currentCategory = ''; \
        foreach ($line in $lines) { \
            if ($line -match '^# ── ([^─]+) ─') { \
                $currentCategory = $matches[1].Trim(); \
                Write-Host \"`n  $currentCategory\" -ForegroundColor Cyan; \
                Write-Host '  ' + ('─' * 45) -ForegroundColor Gray; \
            } elseif ($line -match '^# ([^─].+)') { \
                $desc = $matches[1].Trim(); \
                $idx = [array]::IndexOf($lines, $line); \
                if ($idx -lt $lines.Count - 1) { \
                    $nextLine = $lines[$idx + 1]; \
                    if ($nextLine -match '^([a-z0-9-]+)(\*)?:') { \
                        $recipe = $matches[1]; \
                        $pad = ' ' * [math]::Max(2, (18 - $recipe.Length)); \
                        Write-Host \"    $recipe\" -ForegroundColor White -NoNewline; \
                        Write-Host \"$pad$desc\" -ForegroundColor Gray; \
                    } \
                } \
            } \
        } \
        Write-Host ''"

# ── Build ─

# Sync Python dependencies
build:
    uv sync

# Build the React dashboard
build-dashboard:
    cd dashboard && npm install && npm run build

# ── Test ─

# Run test suite
test:
    uv run pytest tests/ -v

# ── Lint ─

# Run ruff (Python) + biome (dashboard) lint + format check
check:
    uv run ruff format . --check
    uv run ruff check .
    cd dashboard && npx @biomejs/biome check .

# Auto-fix lint issues (ruff Python + biome dashboard)
fix:
    uv run ruff format .
    uv run ruff check --fix .
    cd dashboard && npx @biomejs/biome check --apply .

# ── Docker ─

# Kill stalled Docker engine (gentle first, escalate to triple kill)
docker-kill:
    Write-Host "[1/3] Terminating docker-desktop WSL distro..." -ForegroundColor Cyan
    wsl --terminate docker-desktop 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Host "  OK - distro terminated" -ForegroundColor Green }
    Start-Sleep 2
    $alive = docker info --format "{{.ServerVersion}}" 2>$null
    if ($alive) { Write-Host "  Docker engine recovered." -ForegroundColor Green; exit 0 }
    Write-Host "[2/3] Full WSL shutdown..." -ForegroundColor Cyan
    wsl --shutdown
    Start-Sleep 3
    $alive = docker info --format "{{.ServerVersion}}" 2>$null
    if ($alive) { Write-Host "  Docker engine recovered." -ForegroundColor Green; exit 0 }
    Write-Host "[3/3] Triple kill (Docker Desktop + backend + vmmem)..." -ForegroundColor Cyan
    taskkill /f /im "Docker Desktop.exe" 2>$null
    taskkill /f /im "com.docker.backend.exe" 2>$null
    taskkill /f /im "vmmem" 2>$null
    taskkill /f /im "vmmemWSL" 2>$null
    Write-Host "Docker processes killed. Restart Docker Desktop manually." -ForegroundColor Yellow

# Start the full stack
up:
    docker compose up -d

# Stop the full stack
down:
    docker compose down

# View logs
logs:
    docker compose logs -f

# Rebuild and restart containers
rebuild:
    docker compose up -d --build

# ── DeepFang ──────────────────────────────────────────────────────────────

# Show supervisor health
supervisor:
    curl -s http://127.0.0.1:10956/health | python -c "import sys,json; d=json.load(sys.stdin); print(f'S supervisor: {d.get(\"status\",\"?\")}')"

# Check adjudication log
adjudicate:
    cd '{{justfile_directory()}}'; \
    uv run python -c "import httpx,asyncio,json; print(asyncio.run(httpx.AsyncClient().get('http://127.0.0.1:10956/adjudication')).text[:2000])"

# Show recent workers
workers:
    cd '{{justfile_directory()}}'; \
    docker ps --format "table {{.Names}}\t{{.Status}}" 2>$null || echo "docker not available"

# ── Housekeeping ─

# Remove all bak files from v0.1 salvage
clean-bak:
    Remove-Item -Path README_*.bak, docker-compose_*.yml.bak, start_*.ps1.bak, .env_*.example.bak, docs\ARCHITECTURE_*.md.bak -Force

# Full clean: bak files + pycache + build artifacts
clean:
    Remove-Item -Path README_*.bak, docker-compose_*.yml.bak, start_*.ps1.bak, .env_*.example.bak, docs\ARCHITECTURE_*.md.bak -Force
    Remove-Item -Recurse -Force src\deepfang\__pycache__, dashboard\dist, .pytest_cache, .ruff_cache -ErrorAction SilentlyContinue
