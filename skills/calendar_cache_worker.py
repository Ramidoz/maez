# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
skills/calendar_cache_worker.py — legacy Calendar cache worker, dev-test-only.

Async background worker that periodically calls
skills.calendar_perception.observe() and writes the result into the
perception cache under source name 'calendar'. Same contract as the
screen and system workers — see core/perception_cache.py for the model.

Decision 28:
  • Default fail-closed unless MAEZ_CALENDAR_ALLOW_LEGACY_TEST_MODE=1
  • Not allowed to feed prompts, memory, alerts, or fast-lane envelopes

Legacy behavior when explicitly dev-gated:
  • Daemon thread, never crashes the loop on error
  • Soft error on snapshot.success=False (preserves last good value)
  • Hard timeout via inner thread join
  • Lazy import of skills.calendar_perception so this module is free
    of google-api-python-client deps unless actually run
  • Not registered with maez.service. Not imported by daemon/maez_daemon.py.

Calendar refresh is intentionally slow — Google's API rate limits and
the underlying calendar_perception module already caches for 5 minutes
internally — so we use a 60s worker tick which means real Google calls
happen at the slower of (worker tick, internal cache).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Optional

from core.perception_cache import PerceptionCache, get_cache

logger = logging.getLogger(__name__)


# Calendar cadence + freshness — slower than screen/system because the
# data itself changes on a meeting timescale, not a perception timescale.
DEFAULT_INTERVAL_S = 60.0
DEFAULT_OBSERVE_TIMEOUT_S = 25.0
DEFAULT_FRESH_MS = 120_000  # ≤2min old → FRESH
DEFAULT_STALE_MS = 600_000  # >2min and ≤10min → STALE

SOURCE_NAME = "calendar"
LEGACY_CALENDAR_CACHE_GATE_ENV = "MAEZ_CALENDAR_ALLOW_LEGACY_TEST_MODE"


def _legacy_calendar_cache_allowed() -> bool:
    return os.environ.get(LEGACY_CALENDAR_CACHE_GATE_ENV) == "1"


class CalendarCacheWorker:
    """Background worker that refreshes calendar in the perception cache."""

    def __init__(
        self,
        cache: Optional[PerceptionCache] = None,
        interval_s: float = DEFAULT_INTERVAL_S,
        observe_timeout_s: float = DEFAULT_OBSERVE_TIMEOUT_S,
        fresh_ms: int = DEFAULT_FRESH_MS,
        stale_ms: int = DEFAULT_STALE_MS,
        observe_fn: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.cache = cache or get_cache()
        self.interval_s = interval_s
        self.observe_timeout_s = observe_timeout_s
        self._observe_fn = observe_fn
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.cache.register(SOURCE_NAME, fresh_ms=fresh_ms, stale_ms=stale_ms)

    def start(self) -> None:
        if not _legacy_calendar_cache_allowed():
            self.cache.set_error(
                SOURCE_NAME,
                "legacy calendar cache disabled by Decision 28",
            )
            logger.warning(
                "CalendarCacheWorker blocked; set %s=1 only for legacy dev tests",
                LEGACY_CALENDAR_CACHE_GATE_ENV,
            )
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="calendar-cache-worker",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "CalendarCacheWorker started (interval=%.1fs, timeout=%.1fs)",
            self.interval_s,
            self.observe_timeout_s,
        )

    def stop(self, join_timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            self._tick()
            slept = 0.0
            while slept < self.interval_s and not self._stop.is_set():
                step = min(0.25, self.interval_s - slept)
                time.sleep(step)
                slept += step

    def _tick(self) -> None:
        start = time.time()
        result_holder: dict[str, Any] = {"value": None, "error": None}

        def _call() -> None:
            try:
                fn = self._observe_fn or _default_observe
                result_holder["value"] = fn()
            except Exception as e:  # pragma: no cover
                result_holder["error"] = f"observe raised: {e!r}"

        t = threading.Thread(target=_call, name="calendar-observe-call", daemon=True)
        t.start()
        t.join(timeout=self.observe_timeout_s)

        elapsed_ms = int((time.time() - start) * 1000)

        if t.is_alive():
            self.cache.set_error(
                SOURCE_NAME,
                f"observe timed out after {self.observe_timeout_s:.1f}s (wall={elapsed_ms}ms)",
            )
            logger.warning("CalendarCacheWorker: observe timed out")
            return

        if result_holder["error"] is not None:
            self.cache.set_error(SOURCE_NAME, result_holder["error"])
            logger.warning("CalendarCacheWorker: %s", result_holder["error"])
            return

        value = result_holder["value"]
        if value is None:
            self.cache.set_error(SOURCE_NAME, "observe returned None")
            return

        # CalendarSnapshot has .success / .error
        success = getattr(value, "success", None)
        if success is False:
            err = getattr(value, "error", "<no error message>")
            self.cache.set_error(SOURCE_NAME, f"observe success=False: {err}")
            return

        self.cache.set_value(SOURCE_NAME, value)


def _default_observe():
    """Lazy import so this module costs nothing if unused."""
    if not _legacy_calendar_cache_allowed():
        raise RuntimeError("legacy calendar observe disabled by Decision 28")
    from skills.calendar_perception import observe

    return observe()
