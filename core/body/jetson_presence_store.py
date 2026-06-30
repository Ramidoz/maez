# core/body/jetson_presence_store.py
"""In-memory host store for the latest Jetson presence reading + host received_at.

Non-prompting in Slice A: nothing reads `current()` into a prompt. Host time is the
authority for staleness via jetson_presence.effective_state.
"""
from __future__ import annotations

from core.body.jetson_presence import JetsonPresenceReading, effective_state

DEFAULT_STALE_AFTER_SECONDS = 180


class JetsonPresenceStore:
    def __init__(self, *, stale_after: float = DEFAULT_STALE_AFTER_SECONDS) -> None:
        self._stale_after = stale_after
        self._reading: JetsonPresenceReading | None = None
        self._received_at: float | None = None

    def record(self, reading: JetsonPresenceReading, *, received_at: float) -> None:
        self._reading = reading
        self._received_at = received_at

    @property
    def last_received_at(self) -> float | None:
        return self._received_at

    def current(self, *, now: float) -> tuple[str, str]:
        return effective_state(
            self._reading,
            received_at=self._received_at,
            now=now,
            stale_after=self._stale_after,
        )
