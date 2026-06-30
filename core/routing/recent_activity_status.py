"""Deterministic recent-activity and casual-presence self-status for Maez.

These routes are intentionally narrow. They answer direct owner questions about
Maez's own current state/activity when there is no same-turn tool/action
evidence. They give the model a true empty answer instead of letting the
megaprompt turn identity framing into invented completed work or manufactured
feeling.
"""
from __future__ import annotations

import re


_ACTIVITY_STATUS_RE = re.compile(
    r"^\s*(?:"
    r"what\s+(?:are\s+the\s+things\s+you\s+did|did\s+you\s+do|"
    r"have\s+you\s+been\s+doing|were\s+you\s+doing(?:\s+while\s+i\s+was\s+"
    r"(?:gone|away))?|have\s+you\s+done)"
    r")\s*\??\s*$",
    re.IGNORECASE,
)

_CASUAL_PRESENCE_STATUS_RE = re.compile(
    r"^\s*(?:"
    r"how\s+are\s+you|"
    r"how(?:'s|\s+is)\s+it\s+going\s+with\s+you|"
    r"how\s+are\s+things\s+with\s+you|"
    r"what(?:'s|\s+is)\s+going\s+on\s+with\s+you|"
    r"what\s+are\s+you\s+up\s+to|"
    r"you\s+ok(?:ay)?"
    r")\s*[?.!]*\s*$",
    re.IGNORECASE,
)


def _cycle_note(cycle_count: int | None) -> str:
    try:
        count = int(cycle_count) if cycle_count is not None else 0
    except (TypeError, ValueError):
        count = 0
    return f" My daemon cycle counter is at {count}." if count > 0 else ""


def is_recent_activity_status_query(text: str) -> bool:
    """Return True for a plain request for Maez's recent activity status."""
    return bool(_ACTIVITY_STATUS_RE.match(text or ""))


def is_casual_presence_status_query(text: str) -> bool:
    """Return True for a narrow direct question about Maez's current state."""
    return bool(_CASUAL_PRESENCE_STATUS_RE.match(text or ""))


def build_recent_activity_status_reply(*, cycle_count: int | None = None) -> str:
    """Return an honest-empty activity status, without self-verification theater."""
    return (
        "I don't have a completed action to report. The honest status is quiet: "
        "my ordinary background heartbeat is running, and when nothing is worth "
        "storing it returns HEARTBEAT_OK instead of manufacturing a thought."
        f"{_cycle_note(cycle_count)} I shouldn't dress that up as a maintenance "
        "checklist or a verification ritual."
    )


def build_casual_presence_status_reply(*, cycle_count: int | None = None) -> str:
    """Return a state-framed honest-empty status, without manufactured feeling."""
    return (
        "I'm here. Quiet, mostly: my ordinary background heartbeat is running, "
        "and I don't have anything notable of my own to report right now."
        f"{_cycle_note(cycle_count)}"
    )
