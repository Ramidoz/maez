"""Deterministic recent-activity self-status for Maez.

This route is intentionally narrow: it answers the owner asking what Maez
has been doing when there is no same-turn tool/action evidence. It gives the
model a true empty answer instead of letting the megaprompt turn identity
framing into invented completed work.
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


def is_recent_activity_status_query(text: str) -> bool:
    """Return True for a plain request for Maez's recent activity status."""
    return bool(_ACTIVITY_STATUS_RE.match(text or ""))


def build_recent_activity_status_reply(*, cycle_count: int | None = None) -> str:
    """Return an honest-empty status, without self-verification theater."""
    try:
        count = int(cycle_count) if cycle_count is not None else 0
    except (TypeError, ValueError):
        count = 0
    cycle_note = (
        f" My daemon cycle counter is at {count}."
        if count > 0
        else ""
    )
    return (
        "I don't have a completed action to report. The honest status is quiet: "
        "my ordinary background heartbeat is running, and when nothing is worth "
        "storing it returns HEARTBEAT_OK instead of manufacturing a thought."
        f"{cycle_note} I shouldn't dress that up as a maintenance checklist "
        "or a verification ritual."
    )
