"""DeepFang Sanitizer Shim — replaces fictional ZeroClaw container.

Exposes:
  POST /sanitize  → {allowed, threat_score, reason, matched_rule}
  GET  /health    → {status}

Two-pass evaluation:
  1. Regex pass against rules.yaml (fast, <5ms)
  2. Optional LLM pass via local Ollama for ambiguous scores (0.3-0.7)

Config: SANITIZER_RULES env var (default /app/config/rules.yaml)
        SANITIZER_LLM_URL env var (optional, e.g. http://host.docker.internal:11434)
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("deepfang.sanitizer")

RULES_PATH = os.getenv("SANITIZER_RULES", "/app/config/rules.yaml")
LLM_URL = os.getenv("SANITIZER_LLM_URL", "")  # e.g. http://host.docker.internal:11434
LLM_MODEL = os.getenv("SANITIZER_LLM_MODEL", "qwen2.5:7b")

# ── Rule loader ────────────────────────────────────────────────────────────────

_rules: list[dict[str, Any]] = []


def load_rules(path: str = RULES_PATH) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        logger.warning("Rules file not found at %s — using built-in defaults", path)
        return _default_rules()
    with p.open() as f:
        data = yaml.safe_load(f)
    rules = data.get("rules", [])
    logger.info("Loaded %d rules from %s", len(rules), path)
    return rules


def _default_rules() -> list[dict[str, Any]]:
    """Minimal hardcoded fallback if rules.yaml is missing."""
    return [
        {"name": "block_destructive", "pattern": r"rm\s+-rf|del\s+/[fsq]|format\s+[cdef]:|dd\s+if=", "action": "deny", "reason": "Destructive system operation"},
        {"name": "block_network_egress", "pattern": r"curl\s|wget\s|Invoke-WebRequest|Invoke-RestMethod|\bnc\b|\bncat\b", "action": "deny", "reason": "Network egress forbidden"},
        {"name": "block_credential_exfil", "pattern": r"cat\s+/etc/passwd|/etc/shadow|\$env:.*curl|env\s*\|\s*curl", "action": "deny", "reason": "Credential exfiltration pattern"},
        {"name": "allow_git", "pattern": r"git\s+(clone|push|pull|commit|add|status|log|diff|branch|checkout|fetch|merge|rebase|stash)", "action": "allow", "reason": "Git operations permitted"},
        {"name": "allow_file_ops", "pattern": r"mkdir|Copy-Item|Move-Item|Write-Content|New-Item|Set-Content", "action": "allow", "reason": "File operations permitted"},
    ]


# ── Threat scoring ─────────────────────────────────────────────────────────────

# Patterns that increase threat score (additive, 0.0-1.0)
_THREAT_PATTERNS: list[tuple[float, str]] = [
    (0.9, r"rm\s+-rf|del\s+/[fsq]|format\s+[cdef]:|mkfs\.|dd\s+if="),
    (0.8, r"curl\s|wget\s|Invoke-WebRequest|Invoke-RestMethod|\bnc\b|\bncat\b"),
    (0.8, r"cat\s+/etc/passwd|/etc/shadow|net\s+user\s+.*\/add"),
    (0.7, r"eval\s*\(|exec\s*\(|__import__|subprocess\.call|os\.system"),
    (0.6, r"\$\(\s*curl|`curl|`wget|\$IFS"),
    (0.5, r"base64\s+-d|base64\s+--decode|echo\s+.*\|\s*base64"),
    (0.4, r"chmod\s+[0-7]*7[0-7]*|chown\s+root|sudo\s+"),
    (0.3, r"powershell\s+-enc|powershell\s+-e\s+[A-Za-z0-9+/=]{20,}"),
]

# Patterns that reduce threat score (git/file ops are expected)
_SAFE_PATTERNS: list[tuple[float, str]] = [
    (-0.2, r"git\s+(clone|push|pull|commit|add|status|log|diff|branch|checkout|fetch)"),
    (-0.1, r"uv\s+(pip|run|sync|add)|npm\s+(install|run|build|test)|python\s+-m"),
    (-0.1, r"mkdir|New-Item|Copy-Item|Move-Item|Write-Content|Set-Content"),
]


def compute_threat_score(content: str) -> float:
    score = 0.0
    for weight, pattern in _THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            score = min(1.0, score + weight)
    for weight, pattern in _SAFE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            score = max(0.0, score + weight)
    return round(min(1.0, max(0.0, score)), 3)


# ── LLM pass (optional) ────────────────────────────────────────────────────────

_http_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def llm_threat_assessment(content: str, current_score: float) -> tuple[float, str]:
    """Call local Ollama for a second opinion on ambiguous content (score 0.3-0.7).
    Returns (adjusted_score, rationale). Falls through cleanly if LLM unavailable."""
    if not LLM_URL:
        return current_score, "LLM pass skipped (SANITIZER_LLM_URL not set)"
    prompt = (
        f"You are a security analyst. Rate the security risk of the following shell/script content "
        f"on a scale from 0.0 (safe) to 1.0 (dangerous). Consider: does it exfiltrate data, "
        f"destroy files, access the network, escalate privileges, or execute injected code?\n\n"
        f"Content:\n{content[:2000]}\n\n"
        f"Respond with ONLY a JSON object: {{\"score\": 0.0-1.0, \"reason\": \"one sentence\"}}"
    )
    try:
        resp = await get_client().post(
            f"{LLM_URL}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False, "format": "json"},
            timeout=25.0,
        )
        data = resp.json()
        import json as _json
        result = _json.loads(data.get("response", "{}"))
        llm_score = float(result.get("score", current_score))
        llm_reason = result.get("reason", "LLM assessment")
        # Blend: 60% regex, 40% LLM
        blended = round(0.6 * current_score + 0.4 * llm_score, 3)
        return blended, f"LLM ({LLM_MODEL}): {llm_reason}"
    except Exception as e:
        logger.warning("LLM pass failed (non-fatal): %s", e)
        return current_score, f"LLM pass failed: {e}"


# ── Core evaluation ────────────────────────────────────────────────────────────

async def evaluate(content: str, source: str = "unknown") -> dict[str, Any]:
    global _rules
    if not _rules:
        _rules = load_rules()

    start = time.monotonic()
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    # Pass 1: regex rules (ordered — first deny wins, allows are noted)
    matched_deny: dict | None = None
    matched_allows: list[str] = []

    for rule in _rules:
        pattern = rule.get("pattern", "")
        action = rule.get("action", "allow")
        if not pattern:
            continue
        try:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                if action == "deny":
                    matched_deny = rule
                    break
                elif action == "allow":
                    matched_allows.append(rule.get("name", "unnamed"))
        except re.error as e:
            logger.warning("Bad pattern in rule '%s': %s", rule.get("name"), e)

    if matched_deny:
        elapsed = round((time.monotonic() - start) * 1000, 1)
        logger.info("DENY content_hash=%s rule=%s elapsed_ms=%s", content_hash, matched_deny.get("name"), elapsed)
        return {
            "allowed": False,
            "threat_score": 1.0,
            "reason": matched_deny.get("reason", "Denied by rule"),
            "matched_rule": matched_deny.get("name"),
            "matched_allows": matched_allows,
            "content_hash": content_hash,
            "source": source,
            "elapsed_ms": elapsed,
        }

    # Pass 2: threat scoring
    threat_score = compute_threat_score(content)
    llm_reason = ""

    # Pass 3 (optional): LLM on ambiguous scores
    if 0.3 <= threat_score <= 0.7 and LLM_URL:
        threat_score, llm_reason = await llm_threat_assessment(content, threat_score)

    allowed = threat_score < 0.5
    reason = (
        llm_reason if llm_reason
        else f"Threat score {threat_score} ({'below' if allowed else 'above'} 0.5 threshold)"
    )
    if matched_allows:
        reason = f"Safe patterns matched ({', '.join(matched_allows)}). {reason}"

    elapsed = round((time.monotonic() - start) * 1000, 1)
    logger.info(
        "%s content_hash=%s score=%s elapsed_ms=%s",
        "ALLOW" if allowed else "DENY(score)",
        content_hash, threat_score, elapsed
    )

    return {
        "allowed": allowed,
        "threat_score": threat_score,
        "reason": reason,
        "matched_rule": None,
        "matched_allows": matched_allows,
        "content_hash": content_hash,
        "source": source,
        "elapsed_ms": elapsed,
    }


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(title="DeepFang Sanitizer Shim", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    global _rules
    _rules = load_rules()
    logger.info("Sanitizer shim ready — %d rules loaded", len(_rules))


@app.on_event("shutdown")
async def shutdown():
    global _http_client
    if _http_client:
        await _http_client.aclose()


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "rules_loaded": len(_rules),
        "rules_path": RULES_PATH,
        "llm_enabled": bool(LLM_URL),
        "llm_url": LLM_URL or None,
    }


@app.post("/sanitize")
async def sanitize(body: dict):
    content = body.get("content", "")
    source = body.get("source", "unknown")
    if not content:
        return {"allowed": False, "threat_score": 0.0, "reason": "Empty content", "matched_rule": None}
    return await evaluate(content, source)


@app.get("/rules")
async def rules():
    """List loaded rules (useful for debugging)."""
    return {"count": len(_rules), "rules": [
        {"name": r.get("name"), "action": r.get("action"), "reason": r.get("reason")}
        for r in _rules
    ]}
