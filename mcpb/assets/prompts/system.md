# deepfang — MCP Server Capabilities

## Server Overview

DeepFang is a Docker-Compose execution isolation stack on the Goliath server that implements a three-stage pipeline: ZeroClaw sanitizer (threat scoring, injection detection) → DeepSeek-V4-Pro adjudicator (approve/deny with rationale) → Moltbot air-gapped worker (task execution, local Git push, no WAN egress). The server runs as a FastAPI application with a FastMCP 3.2 MCP surface, exposing 7 MCP tools, 2 native prompts, an agentic workflow with ctx.sample() support, and 8 REST API endpoints. The web dashboard is served from a static directory when available.

DeepFang is designed for safe autonomous code modification: content is sanitized by ZeroClaw for prompt injection and malicious patterns, adjudicated by DeepSeek-V4-Pro for strategic approve/deny with detailed rationale, and dispatched to the Moltbot worker which operates in an air-gapped Docker network with no WAN egress — it can only read from and push to local Git mirrors on the Goliath server. All adjudications are logged in a capped deque (500 entries) with content hashing for auditability.

The stack uses canonical v0.2 service URLs with backward-compatible fallbacks (ZEROCLAW_URL/FORMER_SANITIZER_URL, ZEROCLAW_URL/SANITIZER_URL, MOLTBOT_URL/WORKER_URL). The supervisor tracks uptime, performs parallel health checks against all 3 downstream services, and exposes Prometheus metrics via prometheus_fastapi_instrumentator.

## Tools

### deepfang_status
**Purpose**: Return health and pipeline summary for the DeepFang Goliath stack. No parameters required. Returns health status of all three services (zeroclaw, deepseek, moltbot), supervisor uptime, and git root path.
**Return Format**: {"success": bool, "service": str, "version": str, "health": {"status": str, "uptime_seconds": float, "services": dict, "adjudication_log_count": int}, "pipeline": dict, "git_root": str}

### deepfang_sanitize
**Purpose**: Run ZeroClaw sanitization on content. Returns threat assessment with allowed/denied decision, threat score (0.0-1.0), and reasoning.
**Parameters**:
- content (str, required): Text content to sanitize.
- source (str, default="mcp"): Source identifier for the content.
**Return Format**: {"success": bool, "allowed": bool, "threat_score": float, "reason": str}

### deepfang_adjudicate
**Purpose**: Submit content to DeepSeek-V4-Pro for adjudication. Automatically runs sanitization first, then sends the sanitize result + content to the DeepSeek adjudicator. Returns approve/deny verdict with rationale.
**Parameters**:
- content (str, required): Content to adjudicate.
**Return Format**: {"success": bool, "verdict": str, "rationale": str, "log_entry": dict}

### deepfang_dispatch
**Purpose**: Send approved content to the Moltbot worker for execution. Only works if the content hash matches a recent (last 20 entries) approved adjudication. Prevents unapproved execution.
**Parameters**:
- content (str, required): Previously-approved content to dispatch.
**Return Format**: {"success": bool, "dispatched": bool, **result}

### deepfang_pipeline
**Purpose**: Full end-to-end pipeline: sanitize → adjudicate → dispatch. ZeroClaw sanitizes the content first. If allowed, DeepSeek adjudicates for approve/deny. If approved, dispatches to Moltbot worker. Returns the stage reached and result of each step.
**Parameters**:
- content (str, required): Content to run through the full pipeline.
- source (str, default="mcp"): Source identifier.
**Return Format**: {"success": bool, "stage": str, "passed": bool, "sanitize_result": dict, "adjudication": dict, "dispatch_result": dict}

### deepfang_audit
**Purpose**: Query the adjudication audit log. Returns recent verdicts with content hashes, timestamps, verdicts, rationales, and sanitize scores.
**Parameters**:
- limit (int, default=50): Number of recent audit entries to return.
**Return Format**: {"success": bool, "count": int, "entries": list}

### deepfang_agentic_workflow
**Purpose**: Multi-step agentic workflow via FastMCP 3.1 sampling (ctx.sample). Use for complex goals like "Sanitize and execute this code change", "Check the audit log and summarize recent verdicts", or "Run the full pipeline on this task description". The LLM has access to status_fn, pipeline_fn, and audit_fn sub-tools for autonomous multi-step reasoning.
**Parameters**:
- goal (str, required): Natural language goal description.
- ctx (Context, injected): FastMCP context for sampling.
**Return Format**: str — natural language response from the LLM planner.

## Prompts (FastMCP 3.2 Native)

### deepfang_quick_start
Step-by-step instructions for using the Goliath stack:
1. Check status: deepfang_status() to confirm all services are healthy.
2. Sanitize: deepfang_sanitize(content="...") runs ZeroClaw threat assessment.
3. Adjudicate: deepfang_adjudicate(content="...") submits to DeepSeek-V4-Pro.
4. Dispatch: deepfang_dispatch(content="...") sends approved work to Moltbot.
5. Pipeline: deepfang_pipeline(content="...") runs sanitize→adjudicate→dispatch in one call.

### deepfang_pipeline_workflow
Plan a pipeline execution:
1. Call deepfang_status() to confirm ZeroClaw, DeepSeek, and Moltbot are healthy.
2. Call deepfang_pipeline(content="<task description or code change>").
3. If denied, inspect the rationale and iterate on the content.
4. Call deepfang_audit() periodically to review the adjudication log.

## REST API Endpoints

### GET /health
Returns composite health of all three pipeline services and supervisor uptime.
Response: {"status": "healthy"|"degraded", "uptime_seconds": float, "services": {"zeroclaw": str, "deepseek": str, "moltbot": str}, "adjudication_log_count": int}

### GET /api/audit
Query adjudication log entries.
Query params: limit (int, default=50).
Response: {"entries": [{"timestamp", "content_hash", "content", "verdict", "rationale", "sanitize_score"}]}

### POST /api/pipeline
Execute full pipeline. Body: {"content": str, "source": str}.

### POST /api/sanitize
Run ZeroClaw sanitization. Body: {"content": str, "source": str}.

### POST /api/adjudicate
Run DeepSeek adjudication. Body: {"content": str, "sanitize_result": dict}.

### GET /api/threat
Quick threat score without full pipeline. Query param: content (str).

### POST /api/git
Run safe git operation on the air-gapped worker. Body: {"repo": str, "command": str, "args": list}.

### GET /api/status
Full service status including all downstream URLs and git root path.

## Configuration

### Environment Variables
- SANITIZER_URL / ZEROCLAW_URL (str, default="http://localhost:10958"): ZeroClaw sanitizer service.
- DEEPSEEK_URL (str, default="http://localhost:10959"): DeepSeek-V4-Pro adjudicator service.
- WORKER_URL / MOLTBOT_URL (str, default="http://localhost:10960"): Moltbot air-gapped worker.
- GIT_ROOT (str, default="d:/dev/repos"): Local Git repository root path.

### Service Ports
- deepfang-supervisor: 10956 (API + MCP SSE)
- zeroclaw-sanitizer: 10958 (internal, pipeline only)
- deepseek-adjudicator: 10959 (internal, pipeline only)
- moltbot-worker: 10960 (internal, air-gapped)

## Data Sources
- Adjudication log: In-memory deque (maxlen=500) of audit entries with content hash, verdict, and rationale.
- No persistent database required (all state is in-memory across the pipeline services).
- Git operations are executed on the Moltbot worker against local mirrors only.

## Security Architecture
- **ZeroClaw**: Sanitizer layer — detects prompt injection, malicious code patterns, and anomalous content. Returns threat score 0-1 and allowed/denied decision.
- **DeepSeek**: Adjudicator layer — DeepSeek-V4-Pro model evaluates the sanitized content with full context and returns approve/deny with a detailed rationale.
- **Moltbot**: Execution layer — runs in an air-gapped Docker network with no WAN egress. Can only push to local Git mirrors on the Goliath server. No outbound internet access.
- **Content hash verification**: Dispatch only works if the content hash matches a recently-approved adjudication (last 20 entries).
- **Audit trail**: Every adjudication is logged with timestamp, content hash, verdict, rationale, and sanitize score.

## Error Handling
- If any downstream service is unreachable, health status shows "degraded" or "unreachable".
- Sanitization failure returns {"allowed": False, "error": str, "threat_score": 1.0}.
- Adjudication failure defaults to verdict "deny" with error in rationale.
- Dispatch without approval returns clear error message with content hash.
- All MCP tools return structured dicts with "success": bool.
- Agentic workflow catches exceptions and returns error string.

## Pipeline Architecture Detail

### Stage 1: ZeroClaw Sanitizer
The ZeroClaw service (default port 10958) is the first line of defense. It analyzes incoming content for:
- **Prompt injection patterns**: Detects attempts to override system instructions, role-play as a different user, or inject adversarial commands.
- **Malicious code patterns**: Scans for dangerous operations (rm -rf, DROP TABLE, format C:), privilege escalation (sudo, chmod 777), and data exfiltration (curl to external hosts, base64-encoded payloads).
- **Anomaly scoring**: Assigns a threat_score from 0.0 (completely safe) to 1.0 (extremely dangerous). The score is based on keyword frequency, pattern matching, and heuristic rules.
- **Content classification**: Categorizes content as READ_ONLY (documentation review, code reading), MUTATING (code changes, file edits), or DESTRUCTIVE (deletions, schema changes), informing downstream risk assessment.

### Stage 2: DeepSeek-V4-Pro Adjudicator
The DeepSeek service (default port 10959) performs strategic reasoning on sanitized content:
- **Contextual understanding**: Evaluates content in the full context of the task, repository state, and project conventions.
- **Risk-balanced decision**: Returns a verdict of "approve" or "deny" with a detailed rationale explaining the decision logic.
- **Content hash audit**: Every adjudication creates a log entry with the SHA-256 hash (16 hex chars) of the content, the verdict, rationale, sanitize score, and timestamp.
- **Consistency enforcement**: Similar content receives consistent treatment based on historical adjudication patterns in the audit log.

### Stage 3: Moltbot Air-Gapped Worker
The Moltbot service (default port 10960) executes approved content:
- **Air-gapped execution**: Runs in an isolated Docker network with no WAN egress. No outbound internet access is permitted.
- **Local Git operations**: Can read and write to local Git mirrors on the Goliath server. Supports standard git commands: status, log, add, commit, diff, branch, checkout.
- **Content verification**: Receives and validates the content hash against the recently approved adjudication before execution.
- **Resource limits**: Execution is bounded by configurable timeouts (default 120s for dispatch, 60s for adjudicate).

## Security Threat Model
DeepFang implements defense in depth across three independent layers:

1. **Layer 1 (ZeroClaw) — Statistical Detection**: Uses heuristic rules and pattern matching to detect known attack vectors. This layer is fast (sub-second) and catches obvious threats immediately. False positives are possible but safe (deny by default).
2. **Layer 2 (DeepSeek) — Semantic Analysis**: Uses a large language model to understand the semantic intent of the content. This catches sophisticated attacks that bypass pattern-based detection (e.g., "remove all data" phrased as "clean up the test environment"). The model provides human-readable rationales for every decision.
3. **Layer 3 (Moltbot) — Runtime Isolation**: Even if content passes both checks, the execution environment is air-gapped and sandboxed. The worker cannot exfiltrate data, connect to external services, or persist beyond its container lifecycle.

Additional security measures include: content hash verification preventing replay attacks, audit logging for all adjudications, per-source tracking (mcp, api, automated-test, devops), and Prometheus metrics for detecting anomalous pipeline patterns (e.g., sudden increase in denial rates indicating an attack).

## Audit Log Structure
Each audit log entry contains:
1. **timestamp**: ISO 8601 UTC timestamp of the adjudication.
2. **content_hash**: First 16 hex characters of the SHA-256 hash of the content. Used for verification and deduplication.
3. **content**: First 200 characters of the original content for human review. Full content is not stored for privacy/security.
4. **verdict**: "approve" or "deny" from the DeepSeek adjudicator.
5. **rationale**: Free-text explanation of the decision.
6. **sanitize_score**: Threat score from the ZeroClaw sanitizer (0.0-1.0).

The log is stored in a thread-safe collections.deque with maxlen=500 to bound memory usage. Entries can be queried via the deepfang_audit MCP tool or GET /api/audit REST endpoint. The log is in-memory only and is not persisted across supervisor restarts.

## Prometheus Metrics
The server exposes Prometheus metrics via prometheus_fastapi_instrumentator at the default /metrics endpoint. Key metrics include:
- **HTTP request duration**: Per-endpoint latency histograms.
- **HTTP request count**: Per-endpoint request counters with status codes.
- **Pipeline stage counters**: Number of sanitize, adjudicate, and dispatch calls.
- **Pipeline outcome counters**: Approval rate, denial rate, and error rate.
- **Service health gauge**: 1 = healthy, 0 = unreachable for each downstream service.

These metrics can be scraped by the fleet Prometheus server (port 12001) and visualized in Grafana (port 12000) for operational monitoring.

## Service Dependency Graph
The DeepFang supervisor depends on three downstream services that must be running for full pipeline functionality. The ZeroClaw sanitizer is required for all pipeline operations — without it, sanitize, adjudicate, and pipeline calls all fail. The DeepSeek adjudicator is required for adjudicate and pipeline operations — without it, adjudication defaults to "deny". The Moltbot worker is required for dispatch and full pipeline operations — without it, content cannot be executed. The health endpoint reports the status of each service independently, allowing callers to determine which operations are available. The supervisor operates in degraded mode when some services are unavailable: it still reports health (as "degraded"), it still accepts MCP tool calls (which will return appropriate errors), and it still serves audit log queries from local memory. Prometheus metrics track service availability for alerting. Service discovery uses environment-variable-configured URLs with no automatic service discovery — configuration changes require a supervisor restart.

## Quick Reference Card
The following summary covers the most common DeepFang operations. To check pipeline health: call deepfang_status() with no arguments. To run the end-to-end pipeline: call deepfang_pipeline(content="your task"). To sanitize content only: call deepfang_sanitize(content="text", source="mcp"). To adjudicate approved content: call deepfang_adjudicate(content="text"). To dispatch approved content: call deepfang_dispatch(content="text"). To review audit logs: call deepfang_audit(limit=20). For complex multi-step tasks: call deepfang_agentic_workflow(goal="describe your goal", ctx=...). For REST API access: use GET /health, POST /api/pipeline, POST /api/sanitize, GET /api/audit. All tools require the supervisor to be running and all downstream services to be healthy. The most common cause of pipeline failure is a downstream service being unreachable — check deepfang_status first.

## Logging and Debugging
DeepFang uses structlog for structured logging with standard Python logging integration. Log output includes: supervisor startup with configuration details, service health changes (healthy -> unreachable), pipeline stage transitions (sanitize -> adjudicate -> dispatch), content hash computation and verification, adjudication verdicts with rationales, API request paths and response codes, and error conditions with stack traces. Log levels are: INFO for normal operations, WARNING for degraded service health, ERROR for pipeline failures and unreachable services. For debugging, set DEEPFANG_LOG_LEVEL=DEBUG environment variable. The structlog configuration outputs JSON-formatted logs suitable for ingestion by log aggregation systems (Loki, Elasticsearch). Key debug information includes: content hash for tracking specific items through the pipeline, service URL for identifying which downstream service is being called, HTTP status codes for service responses, and timing information for each pipeline stage.

## Supervisor REST API Architecture
The DeepFang supervisor exposes 8 REST API endpoints on port 10956. The /health endpoint checks all three downstream services in parallel with a 5-second timeout — any unreachable service results in a "degraded" status. The /api/audit endpoint returns the in-memory adjudication log with optional limit parameter. The /api/pipeline endpoint executes the full three-stage pipeline with content sanitization and returns the stage reached. The /api/sanitize endpoint runs ZeroClaw sanitization only — useful for pre-screening. The /api/adjudicate endpoint runs DeepSeek adjudication with an optional sanitize_result parameter — if omitted, it runs sanitization first. The /api/threat endpoint provides a quick threat score for rapid assessment. The /api/git endpoint executes git commands on the air-gapped worker — restricted to a whitelist of safe commands. The /api/status endpoint returns full service configuration including all downstream URLs. All endpoints are wrapped with CORS middleware allowing all origins for development flexibility. Prometheus metrics are exposed at /metrics via prometheus_fastapi_instrumentator.

## Pipeline Execution Guarantees
The DeepFang pipeline provides specific guarantees about execution. Content validation: all content is sanitized before adjudication — no content reaches DeepSeek without passing through ZeroClaw first. Approval verification: dispatch only executes content that has been approved within the last 20 adjudications — replay attacks are prevented by content hash verification. Audit trail: every adjudication is logged with content hash, verdict, rationale, and timestamp — no approvals can be made without an audit entry. Isolation: the worker is air-gapped with no WAN egress — even approved content cannot exfiltrate data. Non-repudiation: the audit log provides a complete record of all pipeline activities. Best-effort delivery: if the worker fails to execute approved content, the error is returned but the approval remains in the audit log for retry. The pipeline does not guarantee: delivery to external systems (the worker cannot contact external services), persistence across supervisor restarts (the audit log is in-memory), or immunity from social engineering (adversarial content that appears safe may still pass).

## Prompt Template Details
The deepfang_quick_start prompt returns a step-by-step guide for first-time users. It covers: checking service status with deepfang_status(), running individual pipeline stages (sanitize first, then adjudicate, then dispatch), using the full pipeline as a shortcut, reviewing the audit log, and using the agentic workflow for complex goals. The deepfang_pipeline_workflow prompt provides a more detailed plan for executing a multi-step pipeline operation. It includes: starting with status verification, crafting the content for pipeline submission, interpreting denial rationales, iterating on content based on feedback, and regularly reviewing the audit log for pattern analysis. Both prompts are registered as FastMCP 3.2 native prompts and are available via the MCP prompts/list and prompts/get protocol methods.

## Tool Integration Patterns
The deepfang MCP tools can be integrated into broader automation workflows. For CI/CD integration, use the POST /api/pipeline REST endpoint as a pre-deployment gate — submit the deployment diff as content and only proceed if the pipeline returns passed=true for the dispatch stage. For fleet agent integration, the deepfang_agentic_workflow tool with ctx.sample() enables autonomous multi-step reasoning — the agent can independently check health, run pipelines, and review audit logs. For monitoring integration, scrape the /metrics Prometheus endpoint at regular intervals and set up alerts for denial rate spikes, service unreachability, and adjudication errors. For chatops integration, connect deepfang tools to a Slack or Discord bot that team members can interact with using natural language commands through the agentic workflow. The MCP surface supports both stdio (for Claude Desktop) and HTTP/SSE (for web integration) transports, making it adaptable to different deployment contexts.

## Configuration Precedence
DeepFang configuration follows a clear precedence chain: environment variables override code defaults, but not command-line arguments or runtime configuration. Service URLs (SANITIZER_URL, DEEPSEEK_URL, WORKER_URL) are read from environment variables at supervisor startup with sensible localhost defaults. The configuration can be overridden at runtime by passing a config dict to the DeepFangSupervisor constructor. The git root path (GIT_ROOT) defaults to d:/dev/repos and should point to a directory containing local Git mirrors. All service URLs use HTTP with no authentication — in production, place behind a reverse proxy with TLS and authentication. The default ports (10958-10960) are within the fleet 10700-11500 range and should not conflict with other services. Logging is configured via structlog with standard Python logging integration — set DEEPFANG_LOG_LEVEL for the supervisor's log level.

## Development and Deployment
The DeepFang stack is deployed on the Goliath server using Docker Compose. Each service (zeroclaw, deepseek, moltbot) runs in a separate container with its own configuration. The supervisor can run as a standalone Python process or within a Docker container. For development, run `uv run python -m deepfang` after installing dependencies with `uv sync`. The MCP surface is registered in mcp_server.py which creates the FastMCP instance, registers all 7 tools and 2 prompts, and exposes them via the FastAPI app mounted at /sse. The web dashboard is served from dashboard/dist/ when the directory exists with an index.html file. For production, the dashboard should be built and served by a reverse proxy (nginx, Caddy) or included in a Docker image. The Prometheus metrics endpoint is available at /metrics and should be scraped by the fleet Prometheus server (port 12001). Environment variables for downstream service URLs default to localhost but should be set to the container names when running in Docker Compose (e.g., ZEROCLAW_URL=http://zeroclaw:10958).

## Use Cases and Applications
DeepFang is designed for scenarios requiring safe, auditable automated code modification. Primary use cases include: CI/CD pipeline gating where code changes are automatically reviewed before deployment, automated refactoring of legacy code with safety checks, batch documentation updates across multiple repositories, security-conscious development environments where code changes must be vetted before execution, regulated industries requiring audit trails for all code modifications, multi-developer environments where automated changes need human-style review, and research settings where experimental code modifications need isolation from production systems. The air-gapped worker is particularly valuable for protecting against supply chain attacks — even if the content is malicious, the worker cannot exfiltrate data or connect to external command-and-control servers.

## Pipeline Observability
DeepFang supports comprehensive observability through three channels: health checks via the /health endpoint which probes all three downstream services in parallel, adjudication audit logs via /api/audit which provide full traceability of all decisions, and Prometheus metrics via /metrics which track request volumes, latencies, and outcomes. For real-time monitoring, set up Grafana dashboards with alerts for: any service being unreachable for more than 60 seconds, pipeline denial rate exceeding 50% over a 5-minute window, adjudication errors or timeouts, and sudden changes in threat score distribution. The audit log content field is truncated to 200 characters for privacy — full content is not stored. For deep-dive analysis, export audit logs periodically and analyze patterns in denials to improve the adjudication criteria.

## Security Hardening Guide
For production deployment of DeepFang, follow these hardening steps: run all pipeline services in isolated Docker networks with no WAN access, use Docker's built-in network policies to restrict inter-service communication to required ports only, set GIT_ROOT to a dedicated directory with no access to sensitive repositories, enable authentication on the supervisor API using API tokens or mutual TLS, restrict Git operations to a whitelist of allowed commands (status, log, diff, add, commit — not push, reset, clean), configure ZeroClaw with custom threat rules matching your security policy, set conservative timeout values for each pipeline stage, and regularly review the audit log for suspicious patterns. The air-gapped worker provides the strongest isolation — never grant it network access even for seemingly legitimate purposes.

## Configuration Reference

### Environment Variables
- **SANITIZER_URL / ZEROCLAW_URL** (str, default="http://localhost:10958"): HTTP endpoint for the ZeroClaw sanitizer service. Must include protocol and port.
- **DEEPSEEK_URL** (str, default="http://localhost:10959"): HTTP endpoint for the DeepSeek-V4-Pro adjudicator service.
- **WORKER_URL / MOLTBOT_URL** (str, default="http://localhost:10960"): HTTP endpoint for the Moltbot air-gapped worker service.
- **GIT_ROOT** (str, default="d:/dev/repos"): Filesystem path to the local Git repositories root. The worker uses this to locate repos for git operations.

### Service Ports Overview
The complete DeepFang stack uses ports in the 10956-10960 range:
- 10956: deepfang-supervisor (FastAPI + FastMCP SSE, web dashboard)
- 10957: deepfang dashboard frontend (Vite React, future)
- 10958: zeroclaw-sanitizer (internal pipeline service)
- 10959: deepseek-adjudicator (internal pipeline service, DeepSeek-V4-Pro)
- 10960: moltbot-worker (internal air-gapped worker service)
