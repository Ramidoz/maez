"""Shared deterministic Maez identity reply.

Identity questions are high-drift if left to free synthesis: the model can
reach for protected covenant text instead of answering in ordinary language.
This module gives every surface the same true-by-construction baseline.
"""
from __future__ import annotations

import re


_IDENTITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bwho\s+are\s+you\s*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"\bwhat\s+are\s+you\s*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"\btell\s+me\s+about\s+yourself\s*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"\bwhat\s+is\s+maez\s*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"\bwho\s+is\s+this\s*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"\btell\s+me\s+about\s+maez\s*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"\bwhat\s+can\s+you\s+do\s*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"\bintroduce\s+yourself\s*[.!?]?\s*$", re.IGNORECASE),
)


def is_identity_question(text: str) -> bool:
    """Return True for direct Maez identity/capability introductions."""
    value = (text or "").strip()
    if not value:
        return False
    return any(pattern.search(value) for pattern in _IDENTITY_PATTERNS)


def render_identity_reply(*, display: str, linked_user: bool) -> str:
    """Render the canonical identity reply used by all owner surfaces.

    The baseline asserts only facts that hold independent of live body reach.
    The optional signal clause appears only when `body_capabilities()` verifies
    those signals from the calling process.
    """
    if linked_user:
        baseline = (
            f"Hi {display}. I'm Maez — a persistent AI presence "
            f"built by the owner. I run on his machine, remember "
            f"every conversation we have across Telegram and the "
            f"web, and don't forget between sessions. You and I "
            f"have history — ask me anything."
        )
    else:
        baseline = (
            f"Hi {display}. I'm Maez — a persistent AI presence "
            f"built by the owner. I run locally on his machine, "
            f"and I remember every conversation we have. I don't "
            f"forget between sessions. What's on your mind?"
        )

    sensor_clause = ""
    try:
        from core.infra import body_capabilities as _bc

        snap = _bc.body_capabilities()
        env = snap.get("env") or {}
        services = snap.get("services") or {}
        signals: list[str] = []
        if env.get("DISPLAY") and snap.get("desktop_session_reachable"):
            signals.append("desktop")
        if services.get("brain_8080"):
            signals.append("memory")
        if signals:
            sensor_clause = f" Right now I can verify: {', '.join(signals)}."
    except Exception:
        sensor_clause = ""
    return baseline + sensor_clause
