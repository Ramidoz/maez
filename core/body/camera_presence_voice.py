"""Deterministic Camera Presence v1.1 direct-answer guard.

Decision 24 / ADR 0029 allows camera presence to surface only as
content-free body state. This module grants the narrow v1.1 chat surface:
direct owner questions about the camera sensor receive exact state text, never
identity, room content, duration narrative, or surveillance voice.
"""

from __future__ import annotations

import re
from typing import Pattern

from core.body.camera_presence_state import CameraPresenceState


_QUESTION_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\b(is|was)\s+the\s+(camera|eye)\s+(on|open|enabled|active)\b", re.I),
    re.compile(r"\b(camera|camera presence)\s+(on|open|enabled|active|running)\b", re.I),
    re.compile(r"\bare\s+you\s+(watching|looking at|seeing)\s+me\b", re.I),
    re.compile(r"\bcan\s+you\s+see\s+me\b", re.I),
    re.compile(r"\bdo\s+you\s+have\s+a\s+fresh\s+camera\s+(presence\s+)?reading\b", re.I),
)

_READING_QUESTION_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bfresh\s+camera\s+(presence\s+)?reading\b", re.I),
    re.compile(r"\bcan\s+you\s+see\s+me\b", re.I),
)

_FORBIDDEN_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bwelcome back\b", re.I),
    re.compile(r"\bi noticed you\b", re.I),
    re.compile(r"\byou have been\b", re.I),
    re.compile(r"\bi (saw|see|can see) you\b", re.I),
    re.compile(r"\bsomeone is at your desk\b", re.I),
    re.compile(r"\bi (am|have been|was) watching\b", re.I),
    re.compile(r"\bwatching over you\b", re.I),
    re.compile(r"\bquiet (here|room)\b", re.I),
    re.compile(r"\byou look\b", re.I),
    re.compile(r"\bposture\b", re.I),
    re.compile(r"\b(rohit|someone else|sarah) is\b", re.I),
    re.compile(r"\bthinking about how quiet\b", re.I),
)


def is_camera_presence_question(text: str) -> bool:
    """Return True for direct owner questions about the camera sensor state."""

    raw = (text or "").strip()
    if not raw:
        return False
    return any(pattern.search(raw) for pattern in _QUESTION_PATTERNS)


def _is_reading_question(text: str) -> bool:
    return any(pattern.search(text or "") for pattern in _READING_QUESTION_PATTERNS)


def presence_voice_guard(text: str, *, state: CameraPresenceState) -> str:
    """Reject camera answer text that drifts into forbidden voice classes."""

    answer = (text or "").strip()
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(answer):
            raise ValueError("camera presence answer violates voice guard")
    if state.enabled and re.search(r"\bi do not have a camera\b", answer, re.I):
        raise ValueError("camera presence answer denies active observation mode")
    return answer


def answer_camera_presence_question(text: str, state: CameraPresenceState) -> str | None:
    """Return an exact approved answer for a direct camera-state question."""

    if not is_camera_presence_question(text):
        return None

    fresh_state = state.with_freshness()
    if fresh_state.mode != "expired_disabled" and (
        state.sensor_state == "unavailable" or state.presence_state == "sensor_unavailable"
    ):
        current = state
    else:
        current = fresh_state
    if current.mode == "expired_disabled":
        answer = "The camera presence observation window has expired."
    elif current.sensor_state == "unavailable" or current.presence_state == "sensor_unavailable":
        answer = "Camera presence is unavailable right now."
    elif current.mode != "observe":
        answer = "The camera presence sensor is off."
    elif _is_reading_question(text) and current.presence_state == "unknown":
        answer = "I do not have a fresh camera presence reading."
    elif current.sensor_state in {"unknown", "stale"} and _is_reading_question(text):
        answer = "I do not have a fresh camera presence reading."
    else:
        answer = f"Camera presence observation is on until {current.enabled_until}."
    return presence_voice_guard(answer, state=current)
