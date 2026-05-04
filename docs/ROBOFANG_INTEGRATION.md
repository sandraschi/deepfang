# RoboFang Integration

DeepFang is wired into RoboFang's security pipeline as a pre-execution screen for high-risk tool calls.

---

## How It Works

RoboFang's `OrchestrationClient.execute_tool()` calls `security.validate_action()` before executing any tool. DeepFang adds a pre-screen at the top of that method for tools matching high-risk prefixes.

```
robofang.execute_tool("mcp_windows-operations_run_powershell", content="...")
    → security.validate_action()
        → DeepFang pre-screen (new in v0.2.0)
            → deepfang_sanitize  (regex, <5ms)
            → if threat_score > 0.3: deepfang_adjudicate  (DeepSeek, ~2s)
            → if denied: return False immediately
        → DefenseClaw.validate_action()  (existing sandbox, unchanged)
    → tool execution
```

---

## Which Tools Are Pre-Screened

High-risk prefixes defined in `src/robofang/core/security.py`:

| Prefix | Why |
|--------|-----|
| `mcp_windows-operations_*` | Shell execution, registry writes, process control |
| `mcp_docker_*` | Container lifecycle, image pulls, network changes |
| `skill_run_shell` | Direct shell passthrough hands |
| `skill_execute` | Generic execution skills |
| `skill_mutate` | Config/file mutation skills |

To add more prefixes, edit `HIGH_RISK_PREFIXES` in `src/robofang/core/security.py`.

---

## Failure Behaviour

| Scenario | Result |
|----------|--------|
| DeepFang stack not running | High-risk tools **blocked** until stack starts |
| Sanitizer returns `allowed: false` | Tool blocked, logged |
| Adjudicator returns `deny` | Tool blocked, logged |
| Threat score ≤ 0.3 | Passes to DefenseClaw without adjudication call |
| DeepFang connector not active | Tool blocked, warning logged |

The fail-closed behaviour is intentional. If you need to execute a high-risk tool without DeepFang running, you have two options:

1. Start the DeepFang stack: `.\start.ps1` in `D:\Dev\repos\deepfang`
2. Temporarily remove the tool prefix from `HIGH_RISK_PREFIXES` (not recommended for production use)

---

## Relation to DefenseClaw and Bastio

DeepFang, DefenseClaw, and Bastio serve different roles in RoboFang's security stack:

| Layer | Tool | What it does |
|-------|------|-------------|
| Input | **Bastio** | Scans incoming prompts for injection vectors before LLM reasoning |
| Execution pre-screen | **DeepFang** | Sanitizes + adjudicates task content before high-risk tool calls |
| Execution sandbox | **DefenseClaw** | Validates proposed actions against policy before execution |
| Network isolation | **DeepFang worker** | Hard network isolation for tasks that actually execute |

They are complementary, not redundant. Bastio fires on the user's input prompt. DeepFang fires on the generated task content. DefenseClaw fires on the tool call parameters.

---

## Viewing the Audit Log

After DeepFang has been running, query the adjudication log from any MCP client:

```
deepfang_audit(limit=50)
```

Or via REST:

```powershell
Invoke-RestMethod http://localhost:10956/api/audit?limit=50
```

Each entry contains:
- `timestamp` — ISO 8601 UTC
- `content_hash` — sha256[:16] of the task content
- `content` — first 200 chars of the task
- `verdict` — `approve` or `deny`
- `rationale` — DeepSeek's explanation
- `sanitize_score` — L1 threat score (0.0–1.0)

---

## Configuration in federation_map.json

```json
"deepfang": {
    "enabled": true,
    "mcp_backend": "http://localhost:10956",
    "description": "DeepFang execution isolation — sanitize → adjudicate → dispatch pipeline",
    "tools": ["deepfang_pipeline", "deepfang_sanitize", "deepfang_adjudicate", "deepfang_audit", "deepfang_status"]
}
```

Set `"enabled": false` to disable the connector without removing the configuration.
