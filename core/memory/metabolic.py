"""Metabolic memory: the durability vote and glance buffer.

The vote has exactly two voter classes: deterministic events (the world did
something) and Maez's own substrate-salience signals (Maez raised its hand).
"Idle" is never a verdict: it means neither voter voted. The LLM is not a voter
because asking the model what to keep would make its priors the gatekeeper.

The event-trigger set is scaffolding. As Maez's salience machinery matures, its
own vote should carry more of this decision instead of tuning this list forever.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CycleEvents:
    alert_sent: bool = False
    error_event: bool = False
    owner_interaction: bool = False
    action_taken: bool = False
    first_of_kind: bool = False
    covenant_event: bool = False
    salience_marked: bool = False


_EVENT_REASONS = (
    ("alert_sent", "alert"),
    ("error_event", "error"),
    ("owner_interaction", "owner_interaction"),
    ("action_taken", "action"),
    ("first_of_kind", "novel_event"),
    ("covenant_event", "covenant"),
)


def evaluate_durability(events: CycleEvents) -> tuple[bool, str | None]:
    """Return whether a cycle thought should become durable, with its reason."""
    for field, reason in _EVENT_REASONS:
        if getattr(events, field):
            return True, reason
    if events.salience_marked:
        return True, "salience_rescue"
    return False, None


class GlanceBuffer:
    """RAM-only ring for untriggered cycle thoughts.

    It feeds the current moment, keeps a short rescue window, decays, never
    touches disk, and does not survive restart.
    """

    def __init__(self, maxlen: int = 240, ttl_s: float = 4 * 3600):
        self._d: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._ttl = float(ttl_s)
        self._lock = threading.Lock()

    def append(
        self,
        *,
        text: str,
        cycle: int,
        ts: float,
        meta: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self._d.append(
                {"text": text, "cycle": cycle, "ts": ts, "meta": meta or {}}
            )

    def _prune(self) -> None:
        cutoff = time.time() - self._ttl
        while self._d and self._d[0]["ts"] < cutoff:
            self._d.popleft()

    def recent(self, n: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            self._prune()
            items = list(self._d)
        return items if n is None else items[-n:]

    def take_by_cycle(self, cycle: int) -> dict[str, Any] | None:
        with self._lock:
            self._prune()
            for i, glance in enumerate(self._d):
                if glance["cycle"] == cycle:
                    del self._d[i]
                    return glance
        return None
