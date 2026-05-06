# Changelog

All notable changes to DeepFang are documented here.

---

## [0.2.1] — 2026-05-04

Day-to-day usability additions: gitops worker mode, scriptlet executor, threat check tool, resource limits.

### Added

**Worker gitops mode:**
- `POST /git` on worker — safe git operations in air-gapped environment. Path traversal protection, dangerous command blocking (push --force, reset --hard, etc.), per-repo directory enforcement under git_root.
- `POST /api/git` on supervisor — proxied endpoint for running git ops through the pipeline.
- `supervisor.git_op()` method on the supervisor class.

**Dashboard:**
- "Threat Check" page — instant threat score via `GET /api/threat`. Score gauge (0-100), severity badge, reason detail. No pipeline needed.
- "Scriptlets" page — paste and run scripts through the full pipeline. Preset buttons (git status, git log, system info). Shows worker output with exit code and duration.

**Infrastructure:**
- Worker `deploy.resources.limits`: 2 CPUs, 2GB memory in docker-compose.yml.

### Changed

- `containers/worker.py` — Added POST /git endpoint for safe git operations.
- `src/deepfang/main.py` — Added GET /api/threat and POST /api/git endpoints. Added git_op() method to supervisor.
- `dashboard/src/App.tsx` — Added ThreatCheckPage and ScriptletsPage components. Updated nav with both new pages.
- `docker-compose.yml` — Added deploy.resources.limits to worker service.

---

### Added

**Containers (custom replacements for fictional images):**
- `containers/sanitizer.py` — Sanitizer shim (~220 lines). Regex rule engine reading `configs/sanitizer/rules.yaml`, threat scoring (0.0–1.0), optional Ollama LLM pass for ambiguous scores. Exposes `POST /sanitize`, `GET /health`, `GET /rules`. Non-root uid 65533.
- `containers/Dockerfile.sanitizer` — Python 3.12-slim, 4 deps, port 10958.
- `containers/worker.py` — Air-gapped executor (~280 lines). Auto-detects command vs task mode. Allowlist enforcement against `configs/worker/worker.yaml`. Async subprocess with timeout + output cap. `GIT_TERMINAL_PROMPT=0` prevents hanging. Execution log (deque 200). Non-root uid 65532.
- `containers/Dockerfile.worker` — Python 3.12-slim + git + Node LTS + uv, port 10960.

**Config:**
- `configs/sanitizer/rules.yaml` — 11 rules: 6 hard denies + 5 safe allows. Renamed from `configs/zeroclaw/`.
- `configs/worker/worker.yaml` — Expanded allowlist (17 commands). Renamed from `configs/moltbot/`.
- `configs/grafana-dashboard-provider.yml` — Grafana file-based dashboard provisioning.
- `configs/dashboards/deepfang.json` — Provisioned Grafana dashboard: stat panels (rates + errors), timeseries (request rates + p95 latency), service health row.

**Tests:**
- `tests/test_sanitizer.py` — 15 tests: unit (threat scoring) + integration (endpoint behaviour, field presence, elapsed_ms).
- `tests/test_worker.py` — 20 tests: mode detection, allowlist, endpoint behaviour, task-mode-without-Ollama error path, log endpoint.

**Integration:**
- `D:\Dev\repos\robofang\configs\federation_map.json` — deepfang connector entry added (enabled, port 10956).
- `D:\Dev\repos\robofang\src\robofang\core\plugins.py` — deepfang registered in static connector registry.
- `D:\Dev\repos\robofang\src\robofang\core\security.py` — `validate_action()` now pre-screens high-risk tool prefixes through `deepfang_sanitize` → `deepfang_adjudicate`. Fail-closed.
- `D:\Dev\repos\robofang\docs\integrations\deepfang.md` — integration doc.

**Docs:**
- `docs/SALVAGE_PLAN.md` — Full analysis: what v0.1 got wrong (fictional ZeroClaw/Moltbot containers), what was salvaged, implementation plan. Status updated to reflect completion.
- `docs/ARCHITECTURE.md` — Updated with correct container descriptions, port map, network topology.
- `CHANGELOG.md` — This file.

### Changed

- `docker-compose.yml` — Complete rewrite. `zeroclaw` → `sanitizer` (local build), `moltbot` → `worker` (local build). Ports updated to 10956–10963. Old fictional images removed.
- `.env.example` — Added `SANITIZER_LLM_URL`, `WORKER_OLLAMA_URL`, `WORKER_OLLAMA_MODEL`. Removed stale port vars.
- `start.ps1` — Full rewrite. `Require-Command` for docker + node (naked-PC compliant). Auto-copies `.env.example`. Zombie kill on all 8 ports. Dashboard build if `dist/` absent. Readiness poll. Opens browser.
- `src/deepfang/main.py` — `content_hash` (sha256[:16]) added to every adjudication log entry. FastMCP 3.2 SSE mount fixed (`http_app()` replaces deprecated `sse_app()`). Version bumped to 0.2.0. Env vars updated (`SANITIZER_URL`, `WORKER_URL`; old names kept as fallbacks).
- `src/deepfang/mcp_server.py` — `deepfang_dispatch` bypass fixed: now requires matching `content_hash` + `verdict=approve` in recent audit log before dispatching.
- `containers/Dockerfile.grafana` — Now copies `grafana-dashboard-provider.yml` and `configs/dashboards/` for auto-provisioning.

### Removed

- `ghcr.io/zeroclaw-labs/zeroclaw:v0.7.4` — Fictional image reference (ZeroClaw is a personal assistant gateway, not a sanitizer; tag v0.7.4 never existed).
- `ghcr.io/openclaw/openclaw:latest` — Fictional image reference (OpenClaw = Moltbot = ClawdBot; a personal assistant, not an execution worker).
- `configs/zeroclaw/` — Renamed to `configs/sanitizer/`.
- `configs/moltbot/` — Renamed to `configs/worker/`.
- `zeroclaw_data` Docker volume — Sanitizer shim is stateless.

---

## [0.1.0] — 2026-05-04 (generated, not functional)

Initial scaffold generated by DeepSeek V4 Pro. Architecture and pipeline design sound. Two of three container references were fictional — assigned to real projects that don't expose the expected APIs:

- `zeroclaw` mapped to ZeroClaw (Rust personal assistant gateway, ~17k stars) — exposes no `/sanitize` endpoint; tag `v0.7.4` does not exist.
- `moltbot` mapped to OpenClaw/Moltbot/ClawdBot (Node.js personal assistant, ~368k stars, three names from one trademark dispute) — exposes no `/execute` endpoint.

Genuine components from v0.1.0 retained in v0.2.0: supervisor pipeline logic, DeepSeek bridge, dashboard, docker-compose network topology, MCP tools, audit log, Prometheus instrumentation.
