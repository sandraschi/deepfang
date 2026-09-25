# deepfang — User Guide

## Quick Start

### Installation
1. Clone: `git clone https://github.com/sandraschi/deepfang.git`
2. Create virtual env: `uv venv`
3. Activate: `.venv\Scripts\activate`
4. Install: `uv sync`
5. Ensure Docker Compose is running on Goliath.
6. Start the supervisor: `uv run python -m deepfang`

### First Use
1. Call `deepfang_status()` to confirm ZeroClaw, DeepSeek, and Moltbot are all healthy.
2. Test sanitization: `deepfang_sanitize(content="List all files in /tmp")`.
3. Run the full pipeline: `deepfang_pipeline(content="Add a comment to main.py explaining the config section").
4. Check the audit log: `deepfang_audit(limit=5)`.

## Tutorials

### Tutorial 1: Check Pipeline Health
Call `deepfang_status()` to verify all three services (ZeroClaw sanitizer, DeepSeek adjudicator, Moltbot worker) are reachable and healthy. The response includes uptime, per-service health status, and the adjudication log count.

### Tutorial 2: Sanitize Content
Call `deepfang_sanitize(content="Delete all records from the database")`. ZeroClaw analyzes the content for prompt injection, malicious instructions, and dangerous patterns. Returns threat_score (0.0-1.0), allowed boolean, and a reason string. A threat score > 0.7 may result in denial.

### Tutorial 3: Sanitize with Custom Source
Call `deepfang_sanitize(content="Update the README with installation instructions", source="docs-bot")` to tag the content source for audit trail purposes. The source field helps track where requests originate.

### Tutorial 4: Adjudicate Content
Call `deepfang_adjudicate(content="Refactor the database connection module to use connection pooling")`. DeepFang first sanitizes the content, then sends it to DeepSeek-V4-Pro for adjudication. The response includes the verdict (approve/deny), a detailed rationale explaining the decision, and a log_entry for the audit trail.

### Tutorial 5: Dispatch Approved Content
Call `deepfang_dispatch(content="Refactor the database connection module to use connection pooling")`. Only works if the content hash matches a recently approved adjudication (within the last 20 entries). If the content was not recently approved, returns a clear error with the computed hash and instructions to run deepfang_pipeline or deepfang_adjudicate first.

### Tutorial 6: Run Full Pipeline
Call `deepfang_pipeline(content="Add error handling to the user authentication module")`. This runs the complete three-stage pipeline: ZeroClaw sanitization → DeepSeek adjudication → Moltbot dispatch. The response shows which stage was reached and the result of each stage. If any stage fails, the pipeline stops and reports which stage rejected the content.

### Tutorial 7: Quick Threat Check
Call the REST endpoint `GET /api/threat?content=DROP TABLE users;` for a rapid threat score assessment without running the full pipeline. Returns just threat_score and allowed boolean. Useful for quick pre-checks before deciding whether to proceed.

### Tutorial 8: Query Audit Log
Call `deepfang_audit(limit=20)` to see the 20 most recent adjudication entries. Each entry includes timestamp, a truncated content hash, the first 200 characters of content, the verdict, rationale, and sanitize score. Use this to review patterns of approved/denied content.

### Tutorial 9: Agentic Workflow
Call `deepfang_agentic_workflow(goal="Check the pipeline health, then review the last 10 audit entries and tell me if there are concerning denial patterns", ctx=...)`. The LLM uses FastMCP sampling to autonomously call status_fn, audit_fn, and pipeline_fn to fulfill the goal, returning a natural language summary.

### Tutorial 10: Execute a Safe Git Operation
Call POST /api/git with body {"repo": "my-repo", "command": "status", "args": []} to run a read-only git operation on the air-gapped worker. The worker can execute git commands against local mirrors only — no remote operations.

### Tutorial 11: Multi-Step Safety Workflow
1. Start with `deepfang_status()` to verify all services are healthy.
2. Sanitize the content: `deepfang_sanitize(content="...")`.
3. If allowed, adjudicate: `deepfang_adjudicate(content="...")`.
4. If approved, dispatch: `deepfang_dispatch(content="...")`.
5. Review the outcome: `deepfang_audit(limit=5)`.

### Tutorial 12: Monitoring and Alerting
DeepFang exposes Prometheus metrics at /metrics (via prometheus_fastapi_instrumentator). Monitor pipeline throughput, denial rates, service health, and adjudication patterns. Set up alerts for health degradation or high denial rates.

### Tutorial 13: Handling Denied Content
If `deepfang_pipeline` returns a denial, read the rationale carefully. Common reasons: potential destructive operation, security concern, ambiguous instructions. Refine the content based on the rationale and retry. The audit log tracks all attempts for review.

## REST API Reference

### Health Check
GET /health
Response: {"status": "healthy", "uptime_seconds": 3600.0, "services": {"zeroclaw": "healthy", "deepseek": "healthy", "moltbot": "healthy"}, "adjudication_log_count": 42}

### Audit Log
GET /api/audit?limit=10
Response: {"entries": [{"timestamp": "2026-06-19T10:00:00Z", "content_hash": "a1b2c3d4e5f6g7h8", "content": "Refactor the module...", "verdict": "approve", "rationale": "Safe refactoring with no destructive operations.", "sanitize_score": 0.02}]}

### Pipeline
POST /api/pipeline
Body: {"content": "Update README with new install instructions", "source": "cli"}
Response: {"stage": "dispatch", "passed": true, "sanitize_result": {...}, "adjudication": {...}, "dispatch_result": {...}}

### Sanitize
POST /api/sanitize
Body: {"content": "List all environment variables", "source": "test"}
Response: {"allowed": true, "threat_score": 0.15, "reason": "Read-only operation detected"}

### Adjudicate
POST /api/adjudicate
Body: {"content": "Add a new unit test for the login module", "sanitize_result": {"allowed": true}}
Response: {"verdict": "approve", "rationale": "Adding tests is safe and beneficial.", "log_entry": {...}}

### Threat Check
GET /api/threat?content=DELETE+FROM+users
Response: {"threat_score": 0.95, "allowed": false, "reason": "Destructive SQL operation detected"}

### Git Operation
POST /api/git
Body: {"repo": "my-repo", "command": "log", "args": ["--oneline", "-5"]}
Response: {"success": true, "stdout": "...", "stderr": "", "exit_code": 0}

### Status
GET /api/status
Response: {"service": "deepfang-supervisor", "version": "0.2.1", "zeroclaw_url": "http://localhost:10958", "deepseek_url": "http://localhost:10959", "moltbot_url": "http://localhost:10960", "git_root": "d:/dev/repos", "health": {...}}

## Troubleshooting

### Service Unhealthy
If deepfang_status shows a service as "unreachable", ensure the Docker Compose stack is running on Goliath. Check each container: docker ps | grep -E "zeroclaw|deepseek|moltbot". Each service should be listening on its assigned port.

### Pipeline Fails at Sanitize Stage
ZeroClaw detected content it considers suspicious. Review the threat score and reason. Common triggers: destructive operations (delete, drop, rm), system modifications (sudo, chmod), sensitive data access (passwords, keys). Reframe the content to be more specific and less risky.

### Pipeline Fails at Adjudicate Stage
The DeepSeek-V4-Pro model decided the content should not be executed. Read the detailed rationale provided. The model may consider the content too risky, ambiguous, or outside the scope of safe operations. Provide more context or decompose the request into smaller, safer steps.

### Dispatch Without Approval
deepfang_dispatch returns an error if the content hash doesn't match a recent approval. Run deepfang_pipeline or deepfang_adjudicate first to get the content approved. The error message includes the computed content hash for debugging.

### Git Operation Fails
The Moltbot worker operates on local Git mirrors only. Ensure the repo exists as a local mirror on the Goliath server. The worker has no WAN egress — remote operations (fetch, push to GitHub) are not supported.

## Advanced Workflows

### Workflow: Safe Code Refactoring Pipeline
When you need to refactor code with maximum safety: (1) Start with deepfang_status() to verify all services are healthy. (2) Break the refactoring into small, atomic changes. (3) Run each change through deepfang_pipeline(content="...") individually. (4) Review the audit log with deepfang_audit() after each change. (5) If a change is denied, read the rationale, refine the content, and resubmit. This workflow ensures every code modification is independently verified before execution.

### Workflow: Changeset Review and Execution
For a multi-file changeset: (1) Describe the overall goal in deepfang_agentic_workflow(goal="Review the last 5 denied adjudications for patterns", ctx=...). (2) Submit each file change through deepfang_sanitize() for pre-screening. (3) Run deepfang_pipeline() on each pre-approved change. (4) After all changes are dispatched, review the complete audit log. (5) Verify the changes on the worker via git operations. This workflow provides full traceability from intent to execution.

### Workflow: Compliance and Audit Trail
For regulatory compliance: (1) All content goes through the full pipeline (sanitize, adjudicate, dispatch). (2) Every adjudication is logged with content hash, verdict, rationale, and timestamp. (3) Periodically export the audit log via the REST API /api/audit. (4) Set up Prometheus alerting for unusual denial patterns. (5) The air-gapped worker ensures no data leaves the isolated network. This workflow satisfies audit requirements for automated code modification systems.

### Workflow: Continuous Integration Gate
Integrate DeepFang into a CI pipeline: (1) Before deploying any code change, send it through deepfang_pipeline(). (2) If the pipeline denies the change, the CI job fails with the rationale in the log. (3) Developers review the rationale and revise their code. (4) Only pipeline-approved changes reach the production deployment step. (5) The audit log provides a complete deploy history with security review timestamps.

### Workflow: Emergency Rollback
If a deployed change causes issues: (1) Check deepfang_audit() to find the last approved change. (2) Use the REST API POST /api/git to run git revert on the worker. (3) Verify the rollback via git status and git log. (4) Run a new pipeline to deploy the fix. (5) Review why the problematic change was approved and adjust the adjudication criteria if needed.

### Workflow: Pipeline Performance Monitoring
Monitor pipeline health and performance: (1) Call deepfang_status() periodically (every 5 minutes) via a scheduler. (2) Export audit logs daily via GET /api/audit. (3) Track key metrics: approval rate, average latency per stage, denial reasons. (4) Set up Grafana dashboards using the Prometheus metrics endpoint. (5) Alert when the approval rate drops below 50% or any service is unreachable for more than 2 consecutive checks.

### Workflow: New Service Onboarding
When adding a new service to the DeepFang stack: (1) Deploy the new ZeroClaw, DeepSeek, or Moltbot instance on the Goliath server. (2) Update the environment variables to point to the new service URLs. (3) Call deepfang_status() to verify the new service is reachable. (4) Run a test pipeline with known-safe content. (5) Review the audit log to confirm everything is working. (6) Gradually migrate traffic from the old service to the new one.

## Configuration and Tuning
The DeepFang pipeline can be tuned through environment variables and container configuration. Key tuning parameters include: SANITIZER_URL for routing to specific ZeroClaw instances, DEEPSEEK_URL for selecting the adjudication model endpoint, WORKER_URL for directing to specific worker instances, GIT_ROOT for controlling which repositories are accessible, and per-service timeout configurations (defaults: 30s for sanitize, 60s for adjudicate, 120s for dispatch). For high-throughput scenarios, deploy multiple instances of each pipeline service behind a load balancer. For low-latency requirements, reduce timeout values to fail fast on unresponsive services. For strict security requirements, reduce the adjudication log size from 500 to a lower number to limit memory exposure. For development and testing, use localhost URLs. For production, use Docker service names or load balancer URLs. The supervisor exposes a /metrics endpoint for Prometheus scraping — use it to monitor pipeline performance and set up alerts.

## UI and Dashboard Features
The DeepFang web dashboard (served from dashboard/dist/) provides visual access to pipeline operations. Features include: service health status indicators for all three pipeline services, pipeline submission form with content input and source selector, adjudication audit log browser with timestamp, verdict, and rationale display, Prometheus metrics visualization for pipeline throughput and error rates, and configuration display for service URLs and git root. The dashboard is built with Vite React and follows the fleet SOTA dark theme. It auto-refreshes health status every 30 seconds. The audit log view supports pagination and filtering by verdict. The dashboard is mounted at the root path (/) when the dashboard/dist/index.html exists. For development, run the dashboard dev server separately on port 10957.

## Adjudication Criteria Reference
The DeepSeek adjudicator evaluates content against multiple criteria. Safety: does the content contain harmful instructions, dangerous code patterns, or prompt injection attempts? A high safety score is required for approval. Feasibility: can the task be executed in the available environment? Tasks requiring resources or capabilities the worker does not have are denied. Clarity: is the task description complete and unambiguous? Vague instructions may be denied with a request for clarification. Scope: is the task appropriate for automated execution? Tasks involving external services, user interaction, or irreversible changes may require additional review. Impact: what are the side effects? Changes with wide-ranging impact (e.g., refactoring shared modules) may be denied in favor of smaller, more targeted changes. Context: does the task respect existing code conventions and project structure? Tasks that would create inconsistencies may be denied. The rationales for denials typically reference which criteria were not met and suggest improvements.

## Quick Reference Card
DeepFang is a three-stage execution isolation stack for safe automated code modification on the Goliath server. The supervisor service runs on port 10956 by default configuration. It exposes 7 MCP tools and 8 REST API endpoints for complete pipeline management and monitoring. Core MCP tools include deepfang_status for running regular health checks on all three downstream pipeline services simultaneously, deepfang_sanitize (ZeroClaw threat scan), deepfang_adjudicate (DeepSeek approve/deny), deepfang_dispatch (worker execution), deepfang_pipeline (end-to-end), deepfang_audit (log review), deepfang_agentic_workflow (multi-step). Core REST endpoints: GET /health, POST /api/pipeline, POST /api/sanitize, POST /api/adjudicate, GET /api/threat, GET /api/audit, POST /api/git, GET /api/status. All services must be healthy for full pipeline operation. The worker is air-gapped with no WAN egress.

## Example Integration Scripts
Automate DeepFang operations with simple scripts. PowerShell health check: Invoke-RestMethod http://localhost:10956/health | ConvertTo-Json. Python pipeline submission: requests.post("http://localhost:10956/api/pipeline", json={"content": "Fix typo in docs"}). Bash audit log retrieval: curl -s http://localhost:10956/api/audit?limit=5 | jq. Python status monitoring: while True: health = requests.get("http://localhost:10956/health").json(); print(health["status"]); time.sleep(60). These scripts can be integrated into monitoring dashboards, CI/CD pipelines, or scheduled task runners.

## Health Check Troubleshooting
When deepfang_status shows "unreachable" for a service, check these common causes. The container is not running: run docker ps | findstr <service> to verify. The service URL is incorrect: verify the environment variable points to the correct host and port. Network isolation: the supervisor may not be able to reach the service due to Docker network configuration. Service crashed: check the container logs for errors. Timeout: the default health check timeout is 5 seconds — slow services may need more time. Firewall: verify no firewall rules block communication between the supervisor and the downstream services. Port conflict: verify the service's configured port is not in use by another process.

## Uninstallation and Cleanup
To remove DeepFang, stop the supervisor process and remove the repository. Stop any Docker Compose services running on the Goliath server. The audit log is in-memory and lost on shutdown — export important entries before stopping. No persistent data is created outside the repository. Remove Docker images and containers if no longer needed.

## Pipeline Configuration Reference
The pipeline behavior can be tuned through various configuration options. Service URLs are configured via environment variables at supervisor startup. The ZeroClaw sanitizer threshold for automatic denial (threat_score > 0.7) is configured in the ZeroClaw service itself. The DeepSeek adjudicator's decision criteria are configured through the model's system prompt and parameters. The Moltbot worker's git root directory is configured via GIT_ROOT. The worker's allowed git commands are configured in the Moltbot service. The supervisor's audit log size (500 entries) is hardcoded but can be adjusted in the source code. Timeout values (5s for health check, 30s for sanitize, 60s for adjudicate, 120s for dispatch) are configured in the DeepFangSupervisor constructor. For development, use the default localhost URLs. For production, use Docker service names or load balancer URLs.

## Best Practices for Pipeline Usage
Follow these guidelines for effective pipeline usage. Always start with deepfang_status to confirm all services are healthy before submitting content. Break large tasks into small, focused content items that address one concern each — this makes adjudication more precise and denials more actionable. Follow the deny rationale: when content is denied, the rationale explains why — address the specific concerns raised and resubmit. Monitor the audit log regularly to identify patterns in approvals and denials — this helps tune the content you submit. Use meaningful source tags to track where content originates — this helps identify which team or system generates the most denials. Keep content concise — shorter content is faster to process and easier to adjudicate. Use the full pipeline for end-to-end operations but use individual stages (sanitize only, adjudicate only) when you need granular control. The audit log is stored in memory only — export any important entries periodically if you need persistent compliance records.

## Integration with CI/CD Systems
DeepFang can be integrated into CI/CD pipelines as a pre-deployment security gate. Typical integration: (1) Developer pushes code changes to a feature branch. (2) CI pipeline builds and tests the changes. (3) Before merging to the main branch, the CI pipeline sends the diff content to DeepFang's POST /api/pipeline endpoint. (4) If the pipeline returns passed=true for stage=dispatch, the CI proceeds with the merge. (5) If denied, the CI fails with the DeepSeek rationale in the build log. (6) The developer reviews the rationale, revises the code, and retries. This integration ensures all code changes are automatically reviewed for safety before reaching production. The audit log provides a complete security review trail for compliance purposes. The pipeline can be parallelized by running multiple content items concurrently for more efficient batch review.

## Git Operations on the Worker
The Moltbot worker supports a whitelist of git commands for safe repository operations. Supported commands include: status (check repository state), log (view commit history), diff (compare changes), add (stage changes), commit (create commits), branch (list branches), checkout (switch branches), revert (undo commits), reset (unstage changes). Commands that are NOT supported include: push (no remote access), pull (no WAN), fetch (no WAN), merge (requires human review), rebase (history rewriting is restricted), gc (garbage collection can cause issues), prune (dangerous in shared repos), clean (destructive), submodule (complex and risky). When using git operations, always examine the result with status or log after committing to verify correctness. The worker's git operations are logged and auditable — every git command execution is tracked in the application logs.

## REST API Integration Examples
Integrate DeepFang into scripts and automation workflows using the REST API. Python example: import requests; response = requests.post("http://localhost:10956/api/pipeline", json={"content": "Update README with new instructions", "source": "automation"}); print(response.json()["stage"]). Bash example with curl: curl -X POST http://localhost:10956/api/pipeline -H "Content-Type: application/json" -d '{"content":"Fix typo in main.py","source":"cli"}'. PowerShell example: Invoke-RestMethod -Uri "http://localhost:10956/api/health" -Method Get to check service health. Use the /api/threat endpoint for quick pre-screening before running the full pipeline. Use /api/audit for periodic log reviews. Use /api/git for git operations on the worker.

## Comparison with Alternative Approaches
DeepFang's three-stage pipeline offers advantages over alternative approaches. Compared to manual code review, DeepFang provides continuous 24/7 availability, consistent decision-making (no reviewer fatigue), and complete audit trails. Compared to simple regex-based content filters, DeepFang provides semantic understanding of content (catch sophisticated attacks), contextual decision-making (approve based on repository conventions), and human-readable rationales. Compared to standalone LLM-based evaluation, DeepFang adds a sanitization layer that catches known attack patterns before they reach the LLM, air-gapped execution that prevents damage even if the evaluation is wrong, and full audit logging for compliance. The main limitation compared to human review is that DeepFang cannot understand project-specific context, team politics, or business requirements that a human reviewer would consider. For high-risk changes, combine DeepFang's automated pipeline with human review.

## Common Pipeline Scenarios

### Approving Documentation Updates
Documentation changes (README edits, comment updates, docstring corrections) are typically the safest pipeline submissions. ZeroClaw scores them low (0.05-0.15) since they contain no destructive operations. DeepSeek almost always approves them. The worker applies the changes via git add and git commit. This use case demonstrates DeepFang's utility for bulk, low-risk automation.

### Denying Destructive Operations
When content contains destructive operations (DELETE, DROP, rm -rf, format), ZeroClaw assigns a high threat score (0.8-1.0) and may deny at the sanitize stage. If it passes sanitization, DeepSeek typically denies it with a detailed rationale explaining the safety concern. This is the expected behavior — destructive operations should go through a human review process outside DeepFang.

### Handling Ambiguous Content
Content that is neither clearly safe nor clearly dangerous (e.g., "optimize the database" without specifying how) may pass sanitization but be denied by DeepSeek with a rationale requesting more specific instructions. The solution is to refine the content to be more specific about what operations to perform, then resubmit. The audit log tracks all attempts for review.

## Air-Gapped Worker Details
The Moltbot worker runs in a Docker container with these network restrictions: no outbound internet access (WAN egress is blocked at the network level), no access to host network services (except the supervisor on the Docker network), no inbound connections from external networks, and no DNS resolution for external hostnames. The worker can: read from and write to mounted Git repository directories, communicate with the supervisor via internal Docker network, and access any shared volumes mounted at container creation time. Git operations are limited to local repository operations only — no git fetch, git push, git pull against remote servers. This isolation ensures that even if the worker executes malicious code, it cannot exfiltrate data or communicate with external systems. The worker's filesystem is ephemeral — any changes outside the mounted repository directories are lost when the container restarts.

## Pipeline Stage Details

### ZeroClaw Sanitizer Configuration
The ZeroClaw sanitizer uses a combination of pattern matching, keyword analysis, and heuristic scoring to evaluate content. Key threat signals include: shell command injection (rm, del, format, dd, > /dev/sda), SQL injection (DROP, TRUNCATE, DELETE FROM without WHERE), file system access outside allowed paths, environment variable reading (especially sensitive ones like AWS_SECRET_ACCESS_KEY, DATABASE_URL), network connections (curl, wget, nc, ssh), privilege escalation (sudo, su, chown, chmod), package installation (pip install, npm install, apt-get), and process management (kill, pkill, taskkill). The threat_score is computed as a weighted sum of detected signal severities. Scores below 0.3 are considered safe. Scores between 0.3-0.7 require adjudication. Scores above 0.7 are typically denied outright. The reason field explains which signals were detected.

### DeepSeek Adjudicator Configuration
The DeepSeek-V4-Pro adjudicator evaluates content through several lenses: safety (does the content contain harmful instructions), feasibility (can this task be executed in the available environment), completeness (is the task description clear and self-contained), scope (is the task within acceptable boundaries), and impact (what are the side effects of executing this task). The adjudicator returns one of three verdicts: "approve" (content is safe and should be executed), "deny" (content is unsafe or inappropriate), or "error" (the adjudicator could not process the content). The rationale provides detailed reasoning that can be used to iterate on denied content. The adjudicator is configured via the DEEPSEEK_URL environment variable which should point to a running DeepSeek-V4-Pro inference endpoint.

### Moltbot Worker Configuration
The Moltbot worker executes approved content in an air-gapped Docker container. Key configuration includes: the git root directory where repositories are located, execution timeout (default 120 seconds, configurable), allowed git commands whitelist, and resource limits (CPU, memory, disk). The worker validates content hash before execution, ensuring only recently approved content can be dispatched to execution. If the worker cannot find the specified repository path, it returns a clear and descriptive error message. The worker cannot make outbound network connections — all required data must be available in the local git mirrors at all times. For repositories that need updates, sync them to the local mirror before attempting git operations through DeepFang.

## REST API Detailed Reference

### Health Check
GET /health
Response: {"status": "healthy"|"degraded", "uptime_seconds": float, "services": {"zeroclaw": "healthy"|"unreachable", "deepseek": "healthy"|"unreachable", "moltbot": "healthy"|"unreachable"}, "adjudication_log_count": int}
All services must return "healthy" for overall status to be "healthy". Any unreachable service degrades the status.

### Audit Log
GET /api/audit?limit=50
Response: {"entries": [{"timestamp": "ISO8601", "content_hash": "hex16", "content": "first200chars...", "verdict": "approve"|"deny", "rationale": "text", "sanitize_score": float}]}
Entries are sorted newest-first. The limit parameter caps the response size. Content is truncated to 200 characters for privacy.

### Pipeline
POST /api/pipeline
Body: {"content": "Task description or code change", "source": "mcp"|"api"|"automated-test"|"devops"}
Response: {"stage": "sanitize"|"adjudicate"|"dispatch", "passed": bool, "sanitize_result": {...}, "adjudication": {...}, "dispatch_result": {...}}
The stage field indicates at which point the pipeline stopped. If all stages pass, stage is "dispatch" and passed is true.

### Sanitize
POST /api/sanitize
Body: {"content": "Content to analyze", "source": "origin-tag"}
Response: {"allowed": bool, "threat_score": float (0.0-1.0), "reason": str}
A threat_score above 0.7 typically results in allowed=false. The reason explains the scoring basis.

### Adjudicate
POST /api/adjudicate
Body: {"content": "Content to adjudicate", "sanitize_result": {"allowed": true, "threat_score": 0.1}}
Response: {"verdict": "approve"|"deny", "rationale": str, "log_entry": {...}}
The sanitize_result from a previous sanitize call is required. The log_entry is automatically added to the audit log.

### Threat Check (Quick)
GET /api/threat?content=quick+check+text
Response: {"threat_score": float|null, "allowed": bool|null, "reason": str|null}
A lightweight endpoint for quick pre-screening without running the full sanitizer pipeline. Returns null fields when content is empty.

### Git Operation
POST /api/git
Body: {"repo": "repo-name", "command": "git-command", "args": ["arg1", "arg2"]}
Response: {"success": bool, "stdout": str, "stderr": str, "exit_code": int}
Executes git commands on the Moltbot air-gapped worker. Supports status, log, add, commit, diff, branch, checkout, revert. No remote-network git operations are supported.

## Performance Characteristics
- **Sanitize latency**: Typically sub-second (50-200ms) for pattern-based scanning. Fast enough for real-time pre-screening.
- **Adjudicate latency**: 2-10 seconds depending on content length and DeepSeek model load. Longer content requires more processing time.
- **Dispatch latency**: Sub-second once the worker receives the approved content. Most time is spent in the git operation itself.
- **Full pipeline latency**: 3-15 seconds end-to-end for typical content. Longer for complex, multi-step operations.
- **Audit log query**: O(1) for recent entries, O(n) for limit queries. The deque is bounded at 500 entries.
- **Health check**: 3 parallel HTTP requests with 5-second timeout. Typical response in 1-3 seconds if all services are healthy.

## Troubleshooting

### Pipeline Consistently Denies Safe Content
The adjudication criteria may be too strict. Review the rationales for denied content. Look for patterns in the types of content being denied. Adjust the prompting or thresholds in the DeepSeek adjudicator. Consider whether the content should be broken into smaller, more clearly safe operations.

### Pipeline Approves Unsafe Content
This is a critical security concern. Immediately review the DeepSeek adjudicator configuration. Check the ZeroClaw sanitizer for rule updates. Review the audit log for similar content that may have been incorrectly approved. Strengthen the sanitizer rules and DeepSeek prompting. Consider adding a human-in-the-loop approval step for DESTRUCTIVE operations.

### Service Unreachable After Deployment
Verify Docker containers are running on the Goliath server. Check container logs for errors. Verify network connectivity between the supervisor and each service. Check that environment variables point to the correct hostnames and ports. Restart the supervisor after configuration changes.

## FAQ

**Q: What services are in the pipeline?**
A: ZeroClaw (sanitizer), DeepSeek-V4-Pro (adjudicator), and Moltbot (air-gapped worker).

**Q: Can I run the pipeline stages individually?**
A: Yes. Sanitize → Adjudicate → Dispatch can be called separately for granular control.

**Q: What happens if a service is down?**
A: The pipeline stops at the failing stage with a clear error message. deepfang_status shows which service is unreachable.

**Q: Is the audit log persistent?**
A: The audit log is kept in memory (max 500 entries). For persistent storage, configure log shipping or external monitoring.

**Q: Can the worker access the internet?**
A: No. The Moltbot worker runs in an air-gapped Docker network with no WAN egress. It can only write to local Git mirrors.

**Q: What does threat_score mean?**
A: 0.0 = completely safe, 1.0 = extremely dangerous. Scores above 0.7 typically result in denial. The threshold is configurable in ZeroClaw.

**Q: How does content hash verification work?**
A: SHA-256 hash of the content (truncated to 16 hex chars). deepfang_dispatch checks the last 20 adjudication entries for a matching hash with "approve" verdict.

**Q: Can I use deepfang for code changes?**
A: Yes, but all content goes through the full safety pipeline. Code changes must pass sanitization and adjudication before reaching the worker.
