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

# Run ruff lint + format check
check:
    uv run ruff format . --check
    uv run ruff check .

# Auto-fix lint issues
fix:
    uv run ruff format .
    uv run ruff check --fix .

# ── Docker ─

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

# ── Housekeeping ─

# Remove all bak files from v0.1 salvage
clean-bak:
    Remove-Item -Path README_*.bak, docker-compose_*.yml.bak, start_*.ps1.bak, .env_*.example.bak, docs\ARCHITECTURE_*.md.bak -Force

# Full clean: bak files + pycache + build artifacts
clean:
    Remove-Item -Path README_*.bak, docker-compose_*.yml.bak, start_*.ps1.bak, .env_*.example.bak, docs\ARCHITECTURE_*.md.bak -Force
    Remove-Item -Recurse -Force src\deepfang\__pycache__, dashboard\dist, .pytest_cache, .ruff_cache -ErrorAction SilentlyContinue
