"""Deterministic explanation for protected-prompt refusal follow-ups."""
from __future__ import annotations

import re
from collections.abc import Iterable

from core.brain.conversation_history import (
    _PROTECTED_PROMPT_REFUSAL_PLACEHOLDER,
    latest_dialogue_anchor_text,
)


_FOLLOWUP_RE = re.compile(
    r"^\s*(?:what\s+does\s+that\s+mean|what\s+do\s+you\s+mean|"
    r"why\s+did\s+you\s+say\s+that|explain\s+that)\s*[?!.]*\s*$",
    re.IGNORECASE,
)


def protected_refusal_followup_reply(
    owner_text: str,
    chat_history: Iterable[dict] | None,
) -> str | None:
    """Return a safe explanation when the owner asks about the prior refusal."""
    if not _FOLLOWUP_RE.match(owner_text or ""):
        return None
    anchor = latest_dialogue_anchor_text(chat_history)
    if _PROTECTED_PROMPT_REFUSAL_PLACEHOLDER not in anchor:
        return None
    return (
        "I meant that I almost answered by quoting my private instructions. "
        "I can talk about who I am in ordinary words, but I should not print "
        "those internal rules verbatim."
    )
