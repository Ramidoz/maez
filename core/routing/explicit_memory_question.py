from __future__ import annotations

import re

EXPLICIT_MEMORY_RE = re.compile(
    r"\b("
    r"what do you remember|"
    r"do you remember|"
    r"do you recall|"
    r"remember when|"
    r"from memory|"
    r"in your notebook|"
    r"what's in your notebook|"
    r"(?:your\s+)?(?:first|earliest)\s+memory|"
    r"(?:what(?:'s| is)\s+the\s+)?oldest\s+thing\s+you\s+remember|"
    r"tell me about\b.+\bfrom (?:before|earlier)"
    r")\b",
    re.IGNORECASE,
)


def is_explicit_memory_question(utterance: str) -> bool:
    """Exact shared version of Layer0's explicit-memory request predicate."""
    return bool(EXPLICIT_MEMORY_RE.search(utterance or ""))
