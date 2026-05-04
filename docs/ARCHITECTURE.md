# Architecture

DeepFang is a Docker Compose stack with a three-stage execution pipeline. This document covers the data flow, network topology, service responsibilities, and design rationale.

---

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Clients (any combination)                                    │
│  Claude Desktop  ·  RoboFang  ·  openclaude-mcp  ·  REST API │
└───────────────────────────┬──────────────────────────────────┘
                            │ MCP SSE / REST
                            ▼
              ┌─────────────────────────┐
              │       Supervisor        │
              │   FastMCP 3.2 + FastAPI │
              │   :10956 (MCP + API)    │
              │   :10957 (dashboard)    │
              │                         │
              │  The only service that  │
              │  spans all 3 networks.  │
              │  Trusted broker.        │
              └──────┬────────┬────────┘
                     │        │
          ┌──────────▼─┐  ┌───▼──────────┐
          │  Sanitizer  │  │ DeepSeek     │
          │  :10958     │  │ Bridge       │
          │             │  │ :10959       │
          │  Regex +    │  │              │
          │  threat     │  │  LLM adjudi- │
          │  scoring    │  │  cation via  │
          │  <5ms       │  │  DeepSeek    │
          │             │  │  cloud API   │
          └─────────────┘  └─────────────┘
                     │
                     ▼
          ┌──────────────────┐
          │     Worker        │
          │     :10960        │
          │                   │
          │  Air-gapped       │
          │  internal: true   │
          │  No WAN egress    │
          │                   │
          │  Writes to        │
          │  /repos           │
          └──────────────────┘
```

---

## Data Flow

1. Client sends task content to Supervisor via `POST /api/pipeline` or `deepfang_pipeline` MCP tool
2. Supervisor calls **Sanitizer** `POST /sanitize` — regex evaluation, returns `{allowed, threat_score, reason}`
3. If `allowed: false` → pipeline stops, error returned to client
4. If `threat_score > 0.8` → Supervisor calls **DeepSeek Bridge** `POST /adjudicate` directly (auto-deny path skipped)
5. Supervisor calls **DeepSeek Bridge** `POST /adjudicate` — LLM evaluates intent, returns `{verdict, rationale}`
6. If `verdict != "approve"` → pipeline stops, rationale returned to client
7. Supervisor calls **Worker** `POST /execute` — runs the task in an air-gapped subprocess
8. Worker result (output, exit_code, duration) returned through Supervisor to client
9. All adjudication decisions logged to in-memory audit deque (maxlen=500)

---

## Networks

Docker Compose creates four networks. Each service is assigned to only the networks it legitimately needs.

```
deepfang-sanitize (internal: true)
  ├── supervisor
  └── sanitizer

deepfang-adjudicate (bridge, WAN access)
  ├── supervisor
  └── deepseek-bridge        ← needs WAN for DeepSeek API calls

deepfang-worker (internal: true)   ← the critical air-gap
  ├── supervisor
  └── worker                 ← NO WAN. Cannot reach internet.

deepfang-internal (bridge, no external exposure)
  ├── prometheus
  ├── loki
  ├── promtail
  └── grafana
```

The **Supervisor is the only service on more than one network**. This is the trust boundary. The Supervisor is trusted; everything it talks to is isolated from everything else.

`internal: true` is not a software policy — it is a Docker network flag that creates a network with no default gateway. The worker kernel has no route to the internet.

---

## Services

### Supervisor (`src/deepfang/`)

FastAPI application + FastMCP 3.2 server, co-hosted on port 10956.

Responsibilities:
- Receives tasks from clients
- Orchestrates the sanitize → adjudicate → dispatch sequence
- Maintains the adjudication log (in-memory deque, maxlen=500)
- Exposes 7 MCP tools and 5 REST endpoints
- Serves the built React dashboard as static files from `dashboard/dist/`
- Exposes Prometheus metrics via `prometheus-fastapi-instrumentator`

The MCP server is mounted at `/sse` using FastMCP 3.2's `http_app()` — it shares the FastAPI process rather than running standalone.

### Sanitizer (`containers/sanitizer.py`)

~220 lines of Python/FastAPI. Stateless — reads `configs/sanitizer/rules.yaml` on startup.

Two-pass evaluation:
1. **Regex pass** — rules evaluated in order. First `deny` match is an immediate hard block. `allow` matches reduce the threat score.
2. **Threat scoring** — independent of rules, scores based on weighted pattern presence (network egress, credential access, code injection, etc.). Allows partially cancel dangerous signals.
3. **Optional LLM pass** — if `SANITIZER_LLM_URL` is set, calls Ollama for content in the ambiguous range (0.3–0.7). Blended 60% regex / 40% LLM. Not a gating control — if Ollama is down, the regex score is used.

Returns `{allowed, threat_score, reason, matched_rule, content_hash, elapsed_ms}`.

### DeepSeek Bridge (`containers/deepseek_bridge.py`)

~120 lines. Proxies to the DeepSeek cloud API with a hardcoded system prompt instructing the model to act as an adjudicator for air-gapped worker tasks.

Pre-filter: if `sanitize_result.threat_score > 0.8`, returns `deny` without calling the API. This saves API cost for obvious threats.

All failures (timeout, malformed JSON, missing key) return `deny`. The bridge is fail-closed.

### Worker (`containers/worker.py`)

~280 lines. Runs inside a Docker container with no internet access.

Content mode detection: if >50% of non-empty lines start with a known command token, content is treated as shell commands (command mode). Otherwise it's a natural language task (task mode — requires `WORKER_OLLAMA_URL`).

Allowlist enforcement: first token of each command line checked against `configs/worker/worker.yaml` before any subprocess is spawned. Non-allowlisted commands are rejected immediately.

Subprocess execution: `asyncio.create_subprocess_shell` with configurable timeout (default 300s) and output cap (default 50MB). `GIT_TERMINAL_PROMPT=0` prevents git from hanging waiting for credentials.

Execution log: last 200 executions in a deque, accessible via `GET /log`.

---

## Observability

Prometheus scrapes the Supervisor's `/metrics` endpoint (auto-exposed by `prometheus-fastapi-instrumentator`). Loki/Promtail collect container logs. Grafana at :10963 has a provisioned dashboard with:

- Pipeline request rates (sanitize/adjudicate/dispatch)
- Request latency p95 per endpoint
- Service health (UP/DOWN for all 4 pipeline services)
- HTTP 5xx error rate

---

## Port Reference

| Port | Container | Service |
|------|-----------|---------|
| 10956 | supervisor | FastMCP SSE + FastAPI REST |
| 10957 | supervisor | React dashboard (static files) |
| 10958 | sanitizer | Sanitizer shim |
| 10959 | deepseek-bridge | DeepSeek adjudicator proxy |
| 10960 | worker | Air-gapped executor |
| 10961 | prometheus | Metrics (internal :9090 → host :10961) |
| 10962 | loki | Log aggregation (internal :3100 → host :10962) |
| 10963 | grafana | Observability UI (internal :3000 → host :10963) |
