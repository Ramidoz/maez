"""
core/perception_cache.py — staging-only perception cache (Session 11a).

A thread-safe key→entry store for perception sources (screen, system, calendar,
GitHub, etc.). The reasoning loop should NEVER call a slow perception source
synchronously in its hot path; instead, async workers populate this cache and
the hot path reads from it.

This module is staging-only for Session 11a:
  • Not imported by daemon/maez_daemon.py
  • Not imported by core/cognition_quality.py
  • Not imported by skills/evolution_engine.py
  • Not wired into maez.service in any way

Future fast-lane integration will attach via:
  • cache.get('screen') in the prompt builder hot path
  • cache.get('system_state') for runtime continuity blocks
  • per-source freshness gating before injecting into the reasoning prompt
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, asdict
from typing import Any, Optional


# Freshness state vocabulary — keep small and stable.
FRESH   = 'fresh'
STALE   = 'stale'
MISSING = 'missing'
ERROR   = 'error'

VALID_STATES = {FRESH, STALE, MISSING, ERROR}


@dataclass
class CacheEntry:
    source_name: str
    value: Any                          # last good value (preserved across failures)
    collected_at: float                 # unix ts when this value was captured
    freshness_state: str                # one of FRESH/STALE/MISSING/ERROR
    error: Optional[str] = None         # last error message if any
    version: int = 0                    # monotonically increases on every update

    @property
    def age_ms(self) -> int:
        if self.collected_at <= 0:
            return -1
        return int((time.time() - self.collected_at) * 1000)

    def to_dict(self) -> dict:
        d = asdict(self)
        d['age_ms'] = self.age_ms
        return d


class PerceptionCache:
    """
    Thread-safe perception cache.

    Read-only consumer API:
        get(source) -> CacheEntry | None
        snapshot()  -> dict[str, dict]      # for debugging / dashboards

    Worker update API:
        register(source, fresh_ms, stale_ms)
        set_value(source, value)            # success path
        set_error(source, error_msg)        # failure path — preserves last good value
        mark_missing(source)                # explicit missing state

    Freshness rules (per source):
        age <= fresh_ms      → FRESH
        fresh_ms < age <= stale_ms → STALE
        age > stale_ms             → STALE  (still readable; consumer decides)
        no value ever set    → MISSING
        last update raised   → ERROR  (but value may still be readable if a
                                       previous successful set_value happened)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, CacheEntry] = {}
        self._thresholds: dict[str, tuple[int, int]] = {}  # source -> (fresh_ms, stale_ms)

    # ── registration ────────────────────────────────────────────────
    def register(self, source: str, fresh_ms: int, stale_ms: int) -> None:
        """Declare freshness thresholds for a source. Idempotent."""
        if fresh_ms <= 0 or stale_ms < fresh_ms:
            raise ValueError(
                f"register({source!r}): require 0 < fresh_ms <= stale_ms, "
                f"got fresh_ms={fresh_ms} stale_ms={stale_ms}"
            )
        with self._lock:
            self._thresholds[source] = (fresh_ms, stale_ms)
            if source not in self._entries:
                self._entries[source] = CacheEntry(
                    source_name=source,
                    value=None,
                    collected_at=0.0,
                    freshness_state=MISSING,
                    error=None,
                    version=0,
                )

    # ── consumer API ────────────────────────────────────────────────
    def get(self, source: str) -> Optional[CacheEntry]:
        """Return a snapshot of the entry with freshness recomputed at read time.
        Never returns the live entry — always a copy — so consumers can't mutate state."""
        with self._lock:
            entry = self._entries.get(source)
            if entry is None:
                return None
            # Recompute freshness at read time so the consumer always sees current state
            recomputed = self._compute_state(source, entry)
            return CacheEntry(
                source_name=entry.source_name,
                value=entry.value,
                collected_at=entry.collected_at,
                freshness_state=recomputed,
                error=entry.error,
                version=entry.version,
            )

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return {k: self.get(k).to_dict() for k in self._entries.keys()}

    # ── worker API ──────────────────────────────────────────────────
    def set_value(self, source: str, value: Any) -> None:
        """Successful update: store the value, clear error, bump version."""
        with self._lock:
            self._ensure(source)
            e = self._entries[source]
            e.value = value
            e.collected_at = time.time()
            e.error = None
            e.version += 1
            e.freshness_state = FRESH

    def set_error(self, source: str, error_msg: str) -> None:
        """Failure update: KEEP last good value/timestamp; record error and ERROR state.
        The consumer can still read the previous value via get(); it just sees
        freshness_state=ERROR and error=<msg>. This is the 'preserve last good value
        if a later update fails' contract."""
        with self._lock:
            self._ensure(source)
            e = self._entries[source]
            e.error = error_msg
            e.version += 1
            e.freshness_state = ERROR
            # NOTE: deliberately do NOT touch e.value or e.collected_at.

    def mark_missing(self, source: str) -> None:
        """Force MISSING state. Used at startup or when a worker is decommissioned."""
        with self._lock:
            self._ensure(source)
            e = self._entries[source]
            e.value = None
            e.collected_at = 0.0
            e.error = None
            e.version += 1
            e.freshness_state = MISSING

    # ── internals ───────────────────────────────────────────────────
    def _ensure(self, source: str) -> None:
        if source not in self._entries:
            self._entries[source] = CacheEntry(
                source_name=source,
                value=None,
                collected_at=0.0,
                freshness_state=MISSING,
                error=None,
                version=0,
            )

    def _compute_state(self, source: str, entry: CacheEntry) -> str:
        # If the most recent worker update was an error and there's no value yet,
        # state stays ERROR. If there IS a previous good value, freshness still
        # ages from that value's collected_at — but we keep ERROR sticky until
        # the next successful set_value.
        if entry.freshness_state == ERROR:
            return ERROR
        if entry.collected_at <= 0 or entry.value is None:
            return MISSING
        thresholds = self._thresholds.get(source)
        if thresholds is None:
            # No registered thresholds — treat any value as fresh
            return FRESH
        fresh_ms, stale_ms = thresholds
        age_ms = (time.time() - entry.collected_at) * 1000
        if age_ms <= fresh_ms:
            return FRESH
        return STALE


# ──────────────────────────────────────────────────────────────────────
# Module-level singleton — staging-only.
# Future fast-lane integration will pass this object explicitly into the
# prompt builder rather than relying on global import.
# ──────────────────────────────────────────────────────────────────────
_GLOBAL_CACHE: Optional[PerceptionCache] = None
_GLOBAL_LOCK = threading.Lock()


def get_cache() -> PerceptionCache:
    global _GLOBAL_CACHE
    with _GLOBAL_LOCK:
        if _GLOBAL_CACHE is None:
            _GLOBAL_CACHE = PerceptionCache()
        return _GLOBAL_CACHE
