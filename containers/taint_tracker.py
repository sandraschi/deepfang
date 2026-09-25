"""Taint Tracker — information flow control for DeepFang pipeline.

This fixes the NanoClaw flaw: prompt injection via email can trick an agent
into posting private content to Slack. NanoClaw blocks host access but can't
stop data exfiltration INSIDE allowed tools.

Taint tracking solves this:
    1. Content entering the pipeline is classified (file source, sensitivity tags)
    2. If content is tagged #private, #sensitive, or from untrusted source, the
       session is marked "tainted"
    3. Tainted sessions are blocked from making outbound network calls
    4. Taint propagates: if tool output references tainted content, it becomes tainted
    5. Taint clears on session reset (re-adjudication required)

Design inspired by: Bell-LaPadula (no read up, no write down) applied to
LLM agent pipelines. Simplified: we don't need full MLS — just a binary
taint bit that gates egress.

Integration points:
    - Sanitizer: tags content with classification labels
    - Supervisor: tracks session taint state in adjudication log
    - Worker: refuses network egress (enforced at Docker level, validated here)
    - MCP tools: deepfang_pipeline checks taint before dispatch
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar

logger = logging.getLogger("deepfang.taint")


class SensitivityLabel(StrEnum):
    PUBLIC = "public"          # Safe to share anywhere
    INTERNAL = "internal"       # Within-team only
    PRIVATE = "private"         # Personal/confidential
    RESTRICTED = "restricted"   # Need-to-know basis
    UNTRUSTED = "untrusted"     # External/unverified source


class TaintSource(StrEnum):
    FILE_READ = "file_read"             # Agent read a file
    TOOL_OUTPUT = "tool_output"         # Tool returned sensitive data
    PROMPT_INJECTION = "prompt_injection"  # Detected injection attempt
    EXTERNAL_DATA = "external_data"     # Data from external source
    UNTRUSTED_INPUT = "untrusted_input" # Input from unknown sender


@dataclass
class TaintEvent:
    """Records when a session becomes tainted."""
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    source: TaintSource = TaintSource.UNTRUSTED_INPUT
    label: SensitivityLabel = SensitivityLabel.UNTRUSTED
    content_hash: str = ""
    detail: str = ""


@dataclass
class SessionTaintState:
    """Per-session taint tracking state."""
    session_id: str
    is_tainted: bool = False
    sensitivity_level: SensitivityLabel = SensitivityLabel.PUBLIC
    taint_events: deque[TaintEvent] = field(default_factory=lambda: deque(maxlen=100))
    egress_blocked: bool = False
    egress_blocked_until: float = 0.0

    def taint(self, source: TaintSource, label: SensitivityLabel, content_hash: str = "", detail: str = ""):
        self.is_tainted = True

        # Sensitivity escalation: highest label wins
        label_order = [SensitivityLabel.PUBLIC, SensitivityLabel.INTERNAL,
                       SensitivityLabel.PRIVATE, SensitivityLabel.RESTRICTED,
                       SensitivityLabel.UNTRUSTED]
        if label_order.index(label) > label_order.index(self.sensitivity_level):
            self.sensitivity_level = label

        self.taint_events.append(TaintEvent(source=source, label=label,
                                            content_hash=content_hash, detail=detail))
        self.egress_blocked = True
        self.egress_blocked_until = time.time() + 3600  # 1 hour default

    def clear(self):
        self.is_tainted = False
        self.sensitivity_level = SensitivityLabel.PUBLIC
        self.taint_events.clear()
        self.egress_blocked = False
        self.egress_blocked_until = 0.0

    def can_egress(self) -> bool:
        if not self.egress_blocked:
            return True
        if self.egress_blocked_until and time.time() > self.egress_blocked_until:
            self.egress_blocked = False
            return True
        return False


class TaintTracker:
    """Central taint tracking service for all DeepFang sessions."""

    SENSITIVITY_PATTERNS: ClassVar[dict[str, SensitivityLabel]] = {
        "#private": SensitivityLabel.PRIVATE,
        "#sensitive": SensitivityLabel.PRIVATE,
        "#restricted": SensitivityLabel.RESTRICTED,
        "#confidential": SensitivityLabel.RESTRICTED,
        "#internal": SensitivityLabel.INTERNAL,
        "password": SensitivityLabel.PRIVATE,
        "secret": SensitivityLabel.PRIVATE,
        "api_key": SensitivityLabel.PRIVATE,
        "token": SensitivityLabel.PRIVATE,
        "credential": SensitivityLabel.PRIVATE,
        "/etc/passwd": SensitivityLabel.RESTRICTED,
        "/etc/shadow": SensitivityLabel.RESTRICTED,
        ".env": SensitivityLabel.INTERNAL,
        ".htpasswd": SensitivityLabel.RESTRICTED,
    }

    def __init__(self):
        self._sessions: dict[str, SessionTaintState] = {}
        self._global_audit: deque[dict[str, Any]] = deque(maxlen=500)

    def get_session(self, session_id: str) -> SessionTaintState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionTaintState(session_id=session_id)
        return self._sessions[session_id]

    def classify_content(self, content: str, source: str = "internal") -> SensitivityLabel:
        """Classify content sensitivity based on patterns."""
        if not content:
            return SensitivityLabel.PUBLIC

        content_lower = content.lower()

        for pattern, label in self.SENSITIVITY_PATTERNS.items():
            if pattern in content_lower:
                logger.info("Content classified as %s: matched pattern '%s'", label.value, pattern)
                return label

        if source in ("external", "untrusted"):
            return SensitivityLabel.UNTRUSTED

        return SensitivityLabel.PUBLIC

    def evaluate_content(self, content: str, source: str = "internal",
                         session_id: str = "default") -> dict[str, Any]:
        """Full evaluation: classify + taint session if needed."""
        label = self.classify_content(content, source)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        session = self.get_session(session_id)

        result = {
            "content_hash": content_hash,
            "sensitivity_label": label.value,
            "session_tainted_before": session.is_tainted,
        }

        should_taint = label in (SensitivityLabel.PRIVATE, SensitivityLabel.RESTRICTED, SensitivityLabel.UNTRUSTED)
        should_taint = should_taint or source == "prompt"

        if should_taint:
            source_enum = TaintSource.UNTRUSTED_INPUT
            if source == "prompt":
                source_enum = TaintSource.PROMPT_INJECTION
            elif source in ("file", "tool"):
                source_enum = TaintSource.FILE_READ if source == "file" else TaintSource.TOOL_OUTPUT

            session.taint(source_enum, label, content_hash,
                          f"Content classified as {label.value} from source '{source}'")

            result["session_tainted"] = True
            result["egress_blocked"] = True
            result["taint_source"] = source_enum.value
            logger.warning("SESSION TAINTED: session=%s label=%s source=%s",
                           session_id, label.value, source_enum.value)
        else:
            result["session_tainted"] = session.is_tainted
            result["egress_blocked"] = session.egress_blocked

        self._audit_event(session_id, "classify", label.value, content_hash)
        return result

    def can_dispatch(self, session_id: str, content: str) -> tuple[bool, str]:
        """Check if dispatch is allowed given current taint state."""
        session = self.get_session(session_id)
        if not session.is_tainted:
            return True, "ok"

        if not session.can_egress():
            remaining = max(0, session.egress_blocked_until - time.time())
            return False, (
                f"Session '{session_id}' is tainted ({session.sensitivity_level.value}). "
                f"Egress blocked for {remaining:.0f}s. Reset session to clear taint."
            )

        return True, "taint_cleared"

    def reset_session(self, session_id: str) -> dict[str, Any]:
        """Clear taint after re-adjudication or session reset."""
        session = self.get_session(session_id)
        was_tainted = session.is_tainted
        session.clear()
        self._audit_event(session_id, "reset", "cleared",
                          f"was_tainted={was_tainted}")
        logger.info("Session '%s' taint cleared (was tainted: %s).",
                     session_id, was_tainted)
        return {"session_id": session_id, "was_tainted": was_tainted,
                "now_clean": True}

    def propagate_taint(self, session_id: str, parent_content_hash: str, child_content: str):
        """Propagate taint from parent content to child content."""
        session = self.get_session(session_id)
        if not session.is_tainted:
            return
        child_hash = hashlib.sha256(child_content.encode()).hexdigest()[:16]
        event = TaintEvent(
            source=TaintSource.TOOL_OUTPUT,
            label=session.sensitivity_level,
            content_hash=child_hash,
            detail=f"Taint propagated from parent content hash {parent_content_hash}",
        )
        session.taint_events.append(event)
        logger.debug("Taint propagated: session=%s parent=%s child=%s",
                      session_id, parent_content_hash, child_hash)

    def get_session_state(self, session_id: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        return {
            "session_id": session_id,
            "is_tainted": session.is_tainted,
            "sensitivity_level": session.sensitivity_level.value,
            "egress_blocked": session.egress_blocked,
            "taint_events": len(session.taint_events),
            "recent_events": [
                {"timestamp": e.timestamp, "source": e.source.value,
                 "label": e.label.value, "detail": e.detail}
                for e in list(session.taint_events)[-5:]
            ],
        }

    def _audit_event(self, session_id: str, event: str, label: str, detail: str):
        self._global_audit.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": session_id,
            "event": event,
            "label": label,
            "detail": detail,
        })

    def get_audit_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._global_audit)[-limit:]


# ── Singleton ──────────────────────────────────────────────────────────────────

_tracker: TaintTracker | None = None


def get_tracker() -> TaintTracker:
    global _tracker
    if _tracker is None:
        _tracker = TaintTracker()
    return _tracker
