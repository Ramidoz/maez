"""In-memory buffer of audit Flag kinds since the last valence read.

Fed at the audit_assistant_text choke-point; peeked + cleared by the daemon's
end-of-cycle valence read. Operational - lost on restart, never persisted.
"""

from __future__ import annotations

import threading

_LOCK = threading.Lock()
_KINDS: list[str] = []


def push(kind: str) -> None:
    if not kind:
        return
    with _LOCK:
        _KINDS.append(str(kind))


def peek() -> list[str]:
    with _LOCK:
        return list(_KINDS)


def clear() -> None:
    with _LOCK:
        _KINDS.clear()
