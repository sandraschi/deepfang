"""DeepFang Worker — replaces fictional OpenClaw/Moltbot container.

Exposes:
  POST /execute  → {success, output, error, exit_code, duration_ms}
  POST /git      → {success, output, error, exit_code, duration_ms} — safe git ops
  GET  /health   → {status, workspace, git_root, allowed_commands}

Two content modes (auto-detected):
  - Command mode: content is shell commands → execute directly after allowlist check
  - Task mode:    content is natural language → call Ollama to generate commands, then execute

Safety:
  - Allowlist enforced: first token of each line checked against allowed_commands
  - WAN isolation enforced at Docker network layer (internal: true) — not in software
  - Subprocess timeout from config (default 300s)
  - Output capped at max_output_mb (default 50MB)
  - All executions logged with content hash, commands, exit code, duration

Config: WORKER_CONFIG  env var (default /app/config/worker.yaml)
        WORKER_OLLAMA_URL env var (optional, enables task mode)
        WORKER_OLLAMA_MODEL env var (default qwen2.5:14b)
"""

from __future__ import annotations

import asyncio
import collections
import hashlib
import logging
import os
import re
import shlex
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("deepfang.worker")

CONFIG_PATH = os.getenv("WORKER_CONFIG", "/app/config/worker.yaml")
OLLAMA_URL = os.getenv("WORKER_OLLAMA_URL", "")
OLLAMA_MODEL = os.getenv("WORKER_OLLAMA_MODEL", "qwen2.5:14b")

# ── Config loader ──────────────────────────────────────────────────────────────

_config: dict[str, Any] = {}


def load_config(path: str = CONFIG_PATH) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        logger.warning("Worker config not found at %s — using built-in defaults", path)
        return _default_config()
    with p.open() as f:
        data = yaml.safe_load(f)
    logger.info("Worker config loaded from %s", path)
    return data


def _default_config() -> dict[str, Any]:
    return {
        "git_root": "/repos",
        "workspace": "/workspace",
        "max_runtime_seconds": 300,
        "max_output_mb": 50,
        "allowed_commands": ["git", "python", "node", "npm", "uv", "cargo", "go", "pwsh"],
    }


def get_config() -> dict[str, Any]:
    global _config
    if not _config:
        _config = load_config()
    return _config


# ── Allowlist enforcement ──────────────────────────────────────────────────────

# Tokens that are shell plumbing, not commands — skip allowlist check for these
_SHELL_OPERATORS = {"&&", "||", ";", "|", ">", ">>", "<", "2>&1", "&"}


def extract_commands(content: str) -> list[str]:
    """Extract the first token (command name) from each non-empty, non-comment line."""
    commands = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            tokens = shlex.split(line)
        except ValueError:
            tokens = line.split()
        if not tokens:
            continue
        # Skip shell operators as standalone lines
        cmd = tokens[0]
        if cmd not in _SHELL_OPERATORS:
            # Strip path prefixes: /usr/bin/git → git
            cmd = Path(cmd).name
            commands.append(cmd)
    return commands


def check_allowlist(content: str, allowed: list[str]) -> tuple[bool, str | None]:
    """Returns (ok, offending_command_or_None)."""
    allowed_set = set(allowed)
    for cmd in extract_commands(content):
        if cmd not in allowed_set:
            return False, cmd
    return True, None


# ── Command mode detection ─────────────────────────────────────────────────────

_COMMAND_INDICATORS = re.compile(
    r"^(git|python|node|npm|uv|cargo|go|pwsh|mkdir|cd|echo|cat|ls|Get-|Set-|New-|Copy-|Move-|Remove-|Write-)",
    re.MULTILINE | re.IGNORECASE,
)

_SHEBANG = re.compile(r"^#!")


def is_command_mode(content: str) -> bool:
    """Heuristic: does this look like shell commands vs natural language?"""
    first_line = content.strip().splitlines()[0] if content.strip() else ""
    if _SHEBANG.match(first_line):
        return True
    # If >50% of non-empty lines start with a known command token, it's command mode
    lines = [ln.strip() for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return False
    matches = sum(1 for ln in lines if _COMMAND_INDICATORS.match(ln))
    return (matches / len(lines)) >= 0.5


# ── Ollama task → commands ─────────────────────────────────────────────────────

_http_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=60.0)
    return _http_client


async def task_to_commands(task: str, git_root: str) -> tuple[str, str]:
    """Call Ollama to convert a natural language task to shell commands.
    Returns (commands_str, model_used). Raises RuntimeError if Ollama unavailable."""
    if not OLLAMA_URL:
        raise RuntimeError(
            "Task mode requires WORKER_OLLAMA_URL to be set. "
            "Either set the env var or send shell commands directly."
        )

    cfg = get_config()
    allowed = cfg.get("allowed_commands", [])
    workspace = cfg.get("workspace", "/workspace")

    system = (
        f"You are a shell command generator running on an air-gapped Linux container. "
        f"You have NO internet access. You can only use these commands: {', '.join(allowed)}. "
        f"Git repos are at {git_root}. Your working directory is {workspace}. "
        f"Output ONLY the shell commands to execute the task, one per line. "
        f"No explanations, no markdown, no backticks. Just the commands."
    )
    prompt = f"Task: {task}\n\nGenerate the shell commands:"

    resp = await get_client().post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "system": system, "stream": False},
        timeout=45.0,
    )
    resp.raise_for_status()
    data = resp.json()
    commands = data.get("response", "").strip()
    return commands, OLLAMA_MODEL


# ── Subprocess execution ───────────────────────────────────────────────────────

async def run_commands(content: str, git_root: str) -> dict[str, Any]:
    """Execute shell commands in a subprocess. Returns execution result."""
    cfg = get_config()
    workspace = cfg.get("workspace", "/workspace")
    timeout = cfg.get("max_runtime_seconds", 300)
    max_bytes = int(cfg.get("max_output_mb", 50) * 1024 * 1024)

    # Ensure workspace exists
    Path(workspace).mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_shell(
            content,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=workspace,
            env={
                **os.environ,
                "GIT_ROOT": git_root,
                "HOME": workspace,
                # Prevent git from prompting for credentials (would hang)
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "echo",
            },
        )

        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=float(timeout))
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "success": False,
                "output": "",
                "error": f"Execution timed out after {timeout}s",
                "exit_code": -1,
                "duration_ms": round((time.monotonic() - start) * 1000),
            }

        output = stdout[:max_bytes].decode("utf-8", errors="replace")
        truncated = len(stdout) > max_bytes
        if truncated:
            output += f"\n[OUTPUT TRUNCATED at {cfg.get('max_output_mb', 50)}MB]"

        duration_ms = round((time.monotonic() - start) * 1000)
        success = proc.returncode == 0

        return {
            "success": success,
            "output": output,
            "error": None if success else f"Process exited with code {proc.returncode}",
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "truncated": truncated,
        }

    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Subprocess error: {e}",
            "exit_code": -1,
            "duration_ms": round((time.monotonic() - start) * 1000),
        }


# ── Execution log ──────────────────────────────────────────────────────────────

_exec_log: collections.deque = collections.deque(maxlen=200)


def log_execution(content_hash: str, mode: str, commands: str, result: dict, source: str):
    _exec_log.append({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "content_hash": content_hash,
        "mode": mode,
        "source": source,
        "exit_code": result.get("exit_code"),
        "success": result.get("success"),
        "duration_ms": result.get("duration_ms"),
        "commands_preview": commands[:200],
    })


# ── Core execute ───────────────────────────────────────────────────────────────

async def execute(content: str, git_root: str, source: str = "unknown") -> dict[str, Any]:
    cfg = get_config()
    allowed = cfg.get("allowed_commands", [])
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    # Detect mode
    if is_command_mode(content):
        mode = "command"
        commands = content
    else:
        # Task mode — needs Ollama
        mode = "task"
        if not OLLAMA_URL:
            return {
                "success": False,
                "output": "",
                "error": (
                    "Content looks like a natural language task but WORKER_OLLAMA_URL is not set. "
                    "Send shell commands directly, or set WORKER_OLLAMA_URL to enable task mode."
                ),
                "exit_code": -1,
                "duration_ms": 0,
                "content_hash": content_hash,
                "mode": mode,
            }
        try:
            commands, model = await task_to_commands(content, git_root)
            logger.info("Task mode: generated %d lines via %s", len(commands.splitlines()), model)
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Task→commands generation failed: {e}",
                "exit_code": -1,
                "duration_ms": 0,
                "content_hash": content_hash,
                "mode": mode,
            }

    # Allowlist check
    ok, offender = check_allowlist(commands, allowed)
    if not ok:
        logger.warning("BLOCKED content_hash=%s command=%s", content_hash, offender)
        return {
            "success": False,
            "output": "",
            "error": f"Command not in allowlist: '{offender}'. Allowed: {', '.join(allowed)}",
            "exit_code": -1,
            "duration_ms": 0,
            "content_hash": content_hash,
            "mode": mode,
            "blocked_command": offender,
        }

    # Execute
    logger.info("EXECUTE content_hash=%s mode=%s source=%s", content_hash, mode, source)
    result = await run_commands(commands, git_root)
    log_execution(content_hash, mode, commands, result, source)

    logger.info(
        "DONE content_hash=%s exit_code=%s duration_ms=%s",
        content_hash, result.get("exit_code"), result.get("duration_ms"),
    )
    return {**result, "content_hash": content_hash, "mode": mode}


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="DeepFang Worker", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    global _config
    _config = load_config()
    logger.info(
        "Worker ready — git_root=%s workspace=%s allowed=%s ollama=%s",
        _config.get("git_root"), _config.get("workspace"),
        _config.get("allowed_commands"), OLLAMA_URL or "disabled",
    )


@app.on_event("shutdown")
async def shutdown():
    global _http_client
    if _http_client:
        await _http_client.aclose()


@app.get("/health")
async def health():
    cfg = get_config()
    return {
        "status": "healthy",
        "git_root": cfg.get("git_root"),
        "workspace": cfg.get("workspace"),
        "allowed_commands": cfg.get("allowed_commands"),
        "task_mode_enabled": bool(OLLAMA_URL),
        "ollama_model": OLLAMA_MODEL if OLLAMA_URL else None,
        "exec_log_count": len(_exec_log),
    }


@app.post("/execute")
async def execute_endpoint(body: dict):
    content = body.get("content", "")
    git_root = body.get("git_root", get_config().get("git_root", "/repos"))
    source = body.get("source", "unknown")

    if not content:
        return {"success": False, "error": "Empty content", "exit_code": -1, "duration_ms": 0}

    return await execute(content, git_root, source)


@app.post("/git")
async def git_op(body: dict):
    """Run a safe git operation in an allowed repo directory.

    Body: {repo: str, command: str, args: list[str] | None, source: str | None}
    - repo: subdirectory under git_root (e.g. "deepfang", "mcp-central-docs")
    - command: git subcommand (e.g. "status", "log", "diff", "push")
    - args: additional arguments to git

    Blocked commands: anything outside allowlist, or repo paths escaping git_root.
    """
    repo = body.get("repo", "")
    command = body.get("command", "")
    args = body.get("args", []) or []
    source = body.get("source", "gitops")
    cfg = get_config()
    git_root = cfg.get("git_root", "/repos")
    allowed = cfg.get("allowed_commands", [])

    if "git" not in allowed:
        return {"success": False, "error": "git is not in the allowlist", "exit_code": -1, "duration_ms": 0}

    if not repo:
        return {"success": False, "error": "Missing 'repo'", "exit_code": -1, "duration_ms": 0}
    if not command:
        return {"success": False, "error": "Missing 'command'", "exit_code": -1, "duration_ms": 0}

    # Prevent path traversal
    repo_path = Path(git_root) / repo
    try:
        repo_path = repo_path.resolve()
    except Exception:
        return {"success": False, "error": f"Invalid repo path: {repo}", "exit_code": -1, "duration_ms": 0}

    git_root_resolved = Path(git_root).resolve()
    if not str(repo_path).startswith(str(git_root_resolved)):
        return {"success": False, "error": f"Repo path escapes git_root: {repo}", "exit_code": -1, "duration_ms": 0}

    if not repo_path.is_dir():
        return {"success": False, "error": f"Repo directory not found: {repo_path}", "exit_code": -1, "duration_ms": 0}

    # Block dangerous git commands
    dangerous = {"push --force", "reset --hard", "clean -fd", "gc", "filter-branch", "update-ref", "rebase --exec"}
    full_cmd = f"git {command} {' '.join(str(a) for a in args)}"
    if any(d in full_cmd for d in dangerous):
        return {
            "success": False,
            "error": f"Dangerous git command blocked: {full_cmd}",
            "exit_code": -1,
            "duration_ms": 0,
        }

    # Build and execute
    cmd_parts = ["git", command] + [str(a) for a in args]
    content_hash = hashlib.sha256(full_cmd.encode()).hexdigest()[:16]
    start = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(repo_path),
            env={
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "echo",
            },
        )
        timeout = cfg.get("max_runtime_seconds", 120)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=float(timeout))
        except TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "success": False,
                "output": "",
                "error": f"Git operation timed out after {timeout}s",
                "exit_code": -1,
                "duration_ms": round((time.monotonic() - start) * 1000),
                "content_hash": content_hash,
            }

        output = stdout.decode("utf-8", errors="replace")
        error_output = stderr.decode("utf-8", errors="replace")
        duration_ms = round((time.monotonic() - start) * 1000)
        success = proc.returncode == 0

        result = {
            "success": success,
            "output": output,
            "error": error_output if error_output else None,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "content_hash": content_hash,
        }
        log_execution(content_hash, "git", full_cmd, result, source)
        return result

    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Git subprocess error: {e}",
            "exit_code": -1,
            "duration_ms": round((time.monotonic() - start) * 1000),
            "content_hash": content_hash,
        }


@app.get("/log")
async def exec_log(limit: int = 50):
    entries = list(_exec_log)
    return {"count": len(entries), "entries": entries[-limit:]}
