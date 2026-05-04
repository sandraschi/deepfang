"""DeepFang MCP 3.1 server — tools, prompts, agentic workflow."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Context

logger = logging.getLogger("deepfang.mcp")

_mcp: Any = None
_supervisor: Any = None


def create_mcp_server() -> Any:
    global _mcp, _supervisor
    from fastmcp import FastMCP

    from .main import get_supervisor

    _supervisor = get_supervisor()
    _mcp = FastMCP("DeepFang Supervisor")

    _mcp.tool()(deepfang_status)
    _mcp.tool()(deepfang_sanitize)
    _mcp.tool()(deepfang_adjudicate)
    _mcp.tool()(deepfang_dispatch)
    _mcp.tool()(deepfang_pipeline)
    _mcp.tool()(deepfang_audit)
    _mcp.tool()(deepfang_agentic_workflow)
    _mcp.prompt()(deepfang_quick_start)
    _mcp.prompt()(deepfang_pipeline_workflow)

    logger.info("DeepFang MCP tools and prompts registered.")
    return _mcp


async def deepfang_status() -> dict[str, Any]:
    """Return health and pipeline summary for the DeepFang Goliath stack."""
    if _supervisor is None:
        return {"success": False, "error": "Supervisor not initialized."}
    try:
        health = await _supervisor.health()
        return {
            "success": True,
            "service": "deepfang-supervisor",
            "version": "0.1.0",
            "health": health,
            "pipeline": {
                "zeroclaw": _supervisor.zeroclaw_url,
                "deepseek": _supervisor.deepseek_url,
                "moltbot": _supervisor.moltbot_url,
            },
            "git_root": _supervisor.git_root,
        }
    except Exception as e:
        logger.exception("deepfang_status failed")
        return {"success": False, "error": str(e)}


async def deepfang_sanitize(content: str, source: str = "mcp") -> dict[str, Any]:
    """Run ZeroClaw sanitization on content. Returns threat assessment."""
    if _supervisor is None:
        return {"success": False, "error": "Supervisor not initialized."}
    result = await _supervisor.sanitize(content, source)
    return {"success": True, **result}


async def deepfang_adjudicate(content: str) -> dict[str, Any]:
    """Submit content to DeepSeek-V4-Pro for adjudication (approve/deny with rationale)."""
    if _supervisor is None:
        return {"success": False, "error": "Supervisor not initialized."}
    sanitize_result = await _supervisor.sanitize(content, "adjudicate_direct")
    result = await _supervisor.adjudicate(content, sanitize_result)
    return {"success": True, **result}


async def deepfang_dispatch(content: str) -> dict[str, Any]:
    """Send approved content to worker. Only works if recently adjudicated as approved."""
    if _supervisor is None:
        return {"success": False, "error": "Supervisor not initialized."}
    import hashlib
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    recent = _supervisor.get_audit_log(limit=20)
    approved = any(
        e.get("content_hash") == content_hash and e.get("verdict") == "approve"
        for e in recent
    )
    if not approved:
        return {
            "success": False,
            "error": (
                f"No recent approval found for content hash {content_hash}. "
                "Run deepfang_pipeline or deepfang_adjudicate first."
            ),
        }
    result = await _supervisor.dispatch(content, "approve")
    return {"success": result.get("success", False), **result}


async def deepfang_pipeline(content: str, source: str = "mcp") -> dict[str, Any]:
    """
    Full pipeline: sanitize → adjudicate → dispatch.
    ZeroClaw sanitizes → DeepSeek adjudicates → Moltbot executes (if approved).
    Use this for end-to-end trusted task execution.
    """
    if _supervisor is None:
        return {"success": False, "error": "Supervisor not initialized."}
    result = await _supervisor.pipeline(content, source)
    return {"success": result.get("passed", False), **result}


async def deepfang_audit(limit: int = 50) -> dict[str, Any]:
    """Query the adjudication audit log."""
    if _supervisor is None:
        return {"success": False, "error": "Supervisor not initialized."}
    entries = _supervisor.get_audit_log(limit)
    return {"success": True, "count": len(entries), "entries": entries}


async def deepfang_agentic_workflow(goal: str, ctx: Context) -> str:
    """
    Multi-step workflow via FastMCP 3.1 sampling.
    Use for: "Sanitize and execute this code change", "Check the audit log and summarize recent verdicts",
    "Run the full pipeline on this task description".
    """
    if _supervisor is None:
        return "Error: Supervisor not initialized."

    async def status_fn() -> str:
        out = await deepfang_status()
        return str(out)

    async def pipeline_fn(content: str) -> str:
        out = await deepfang_pipeline(content)
        return str(out)

    async def audit_fn(limit: int = 20) -> str:
        out = await deepfang_audit(limit)
        return str(out.get("entries", out))

    system_prompt = (
        "You are a DeepFang pipeline operator on the Goliath stack. You have sub-tools: "
        "status_fn() for health check; pipeline_fn(content) for the full sanitize→adjudicate→dispatch pipeline; "
        "audit_fn(limit) to query the adjudication log. "
        "Plan and execute steps to achieve the user's goal, then summarize."
    )
    try:
        result = await ctx.sample(
            messages=goal,
            system_prompt=system_prompt,
            tools=[status_fn, pipeline_fn, audit_fn],
            temperature=0.2,
            max_tokens=1024,
        )
        return result.text or "No response from planner."
    except Exception as e:
        logger.exception("deepfang_agentic_workflow failed")
        return f"Agentic workflow failed: {e}"


def deepfang_quick_start() -> str:
    """Get step-by-step instructions to use the DeepFang Goliath stack."""
    return """You are setting up the DeepFang Goliath isolation stack.

1. Check status: deepfang_status() to confirm all services are healthy.
2. Sanitize: deepfang_sanitize(content="...") runs ZeroClaw threat assessment first.
3. Adjudicate: deepfang_adjudicate(content="...") submits to DeepSeek-V4-Pro for approve/deny.
4. Dispatch: deepfang_dispatch(content="...") sends approved work to Moltbot worker.
5. Pipeline: deepfang_pipeline(content="...") runs the full sanitize→adjudicate→dispatch in one call.

The worker has no WAN egress and can only push to local Git mirrors on Goliath.
All adjudications are logged — use deepfang_audit() to review verdicts.
For multi-step goals, use deepfang_agentic_workflow(goal="...")."""


def deepfang_pipeline_workflow() -> str:
    """Plan a DeepFang pipeline execution: sanitize → adjudicate → dispatch."""
    return """Plan a DeepFang pipeline execution:

1. Call deepfang_status() to confirm ZeroClaw, DeepSeek, and Moltbot are all healthy.
2. Call deepfang_pipeline(content="<task description or code change>") — this runs:
   a. ZeroClaw sanitization (threat scoring, injection detection)
   b. DeepSeek-V4-Pro adjudication (approve/deny with rationale)
   c. Moltbot worker dispatch (only if approved, writes to local Git mirrors)
3. If denied, inspect the rationale in the response and iterate on the content.
4. Call deepfang_audit() periodically to review the adjudication log for patterns.
5. The Moltbot worker runs in an air-gapped Docker network with no WAN egress."""
