"""Small command parsers for proposal-related slash commands."""
from __future__ import annotations

import re


_SHOW_RE = re.compile(r"^/show(?:@\w+)?\s+#?(\d+)\s*$", re.IGNORECASE)


def parse_show_id(text: str) -> int | None:
    """Return the proposal id from ``/show <id>``, or ``None``."""
    match = _SHOW_RE.match((text or "").strip())
    if not match:
        return None
    return int(match.group(1))
