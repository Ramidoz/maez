from __future__ import annotations

import re

EXPLICIT_MEMORY_RE = re.compile(
    r"\b(what do you remember|from memory|in your notebook|what's in your notebook)\b",
    re.IGNORECASE,
)


def is_explicit_memory_question(utterance: str) -> bool:
    """Exact shared version of Layer0's explicit-memory request predicate."""
    return bool(EXPLICIT_MEMORY_RE.search(utterance or ""))
