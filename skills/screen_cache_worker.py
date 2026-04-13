"""
skills/screen_cache_worker.py — staging-only async screen cache worker (Session 11a).

A background thread that periodically calls skills.screen_perception.observe()
and writes the result into the perception cache. The reasoning loop should
NEVER call observe() in its hot path; it reads from the cache instead.

This worker is staging-only:
  • Not started by daemon/maez_daemon.py
  • Not registered in maez.service
  • Started only by scripts/run_screen_cache_worker.py or by the benchmark

Future fast-lane integration will start this worker once at daemon boot,
alongside future workers (system_state, calendar, github, etc.).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

from core.perception_cache import PerceptionCache, get_cache

logger = logging.getLogger(__name__)


# Default cadence + freshness thresholds for the screen source.
# Tuned conservatively for Session 11a — real values can be tightened later.
DEFAULT_INTERVAL_S       = 8.0    # how often the worker tries to refresh
DEFAULT_OBSERVE_TIMEOUT  = 30.0   # hard cap on a single observe() call
DEFAULT_FRESH_MS         = 15_000 # ≤15s old → FRESH
DEFAULT_STALE_MS         = 60_000 # >15s and ≤60s → STALE

SOURCE_NAME = 'screen'


class ScreenCacheWorker:
    """
    Background screen cache worker.

    Lifecycle:
        worker = ScreenCacheWorker(cache)
        worker.start()                # spawns daemon thread
        ...
        worker.stop()                 # signals + joins (with timeout)

    Behavior contract:
      • Never raises out of its loop.
      • If observe() returns success, writes the value via cache.set_value().
      • If observe() returns failure OR exceeds the wall-clock timeout, writes
        cache.set_error() — which preserves the previous good value.
      • Each loop iteration is bounded so a hung observe() can't stall stop().
    """

    def __init__(
        self,
        cache: Optional[PerceptionCache] = None,
        interval_s: float = DEFAULT_INTERVAL_S,
        observe_timeout_s: float = DEFAULT_OBSERVE_TIMEOUT,
        fresh_ms: int = DEFAULT_FRESH_MS,
        stale_ms: int = DEFAULT_STALE_MS,
        observe_fn: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.cache = cache or get_cache()
        self.interval_s = interval_s
        self.observe_timeout_s = observe_timeout_s
        # observe_fn is injectable so the benchmark can substitute a slow stub
        # without monkey-patching the live screen_perception module.
        self._observe_fn = observe_fn
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self.cache.register(SOURCE_NAME, fresh_ms=fresh_ms, stale_ms=stale_ms)

    # ── lifecycle ────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name='screen-cache-worker',
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "ScreenCacheWorker started (interval=%.1fs, timeout=%.1fs)",
            self.interval_s, self.observe_timeout_s,
        )

    def stop(self, join_timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
            self._thread = None

    # ── loop ─────────────────────────────────────────────────────
    def _run(self) -> None:
        while not self._stop.is_set():
            self._tick()
            # Sleep in small chunks so stop() responds quickly
            slept = 0.0
            while slept < self.interval_s and not self._stop.is_set():
                step = min(0.25, self.interval_s - slept)
                time.sleep(step)
                slept += step

    def _tick(self) -> None:
        """One refresh attempt. Bounded by observe_timeout_s via a worker thread."""
        start = time.time()
        result_holder: dict[str, Any] = {'value': None, 'error': None}

        def _call() -> None:
            try:
                fn = self._observe_fn or _default_observe
                result_holder['value'] = fn()
            except Exception as e:                          # pragma: no cover
                result_holder['error'] = f"observe raised: {e!r}"

        t = threading.Thread(target=_call, name='screen-observe-call', daemon=True)
        t.start()
        t.join(timeout=self.observe_timeout_s)

        elapsed_ms = int((time.time() - start) * 1000)

        if t.is_alive():
            # Underlying call hung past the timeout. We cannot kill it (Python
            # threads aren't cancellable), but we can stop waiting and record
            # an error. The hung thread will eventually finish or die with the
            # process. The cache keeps its last good value.
            self.cache.set_error(
                SOURCE_NAME,
                f"observe timed out after {self.observe_timeout_s:.1f}s "
                f"(wall={elapsed_ms}ms)",
            )
            logger.warning("ScreenCacheWorker: observe timed out")
            return

        if result_holder['error'] is not None:
            self.cache.set_error(SOURCE_NAME, result_holder['error'])
            logger.warning("ScreenCacheWorker: %s", result_holder['error'])
            return

        value = result_holder['value']

        # observe() returns a ScreenObservation dataclass with .success/.error.
        # Treat success=False as a soft error (preserve last good value).
        if value is None:
            self.cache.set_error(SOURCE_NAME, "observe returned None")
            return

        success = getattr(value, 'success', None)
        if success is False:
            err = getattr(value, 'error', '<no error message>')
            self.cache.set_error(SOURCE_NAME, f"observe success=False: {err}")
            return

        # Success path
        self.cache.set_value(SOURCE_NAME, value)


def _default_observe():
    """Lazy import so the cache module doesn't pull in screen_perception
    (which imports requests + PIL etc.) unless the worker is actually run."""
    from skills.screen_perception import observe
    return observe()
