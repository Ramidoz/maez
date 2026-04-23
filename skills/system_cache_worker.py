# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
skills/system_cache_worker.py — 11b backfill, staging-only.

Async background worker that periodically calls core.perception.snapshot()
and writes the result into the perception cache under source name 'system_state'.

This is the second perception worker (after skills/screen_cache_worker.py)
and follows the same contract:
  • Daemon thread, never crashes the loop on error.
  • If snapshot() raises or exceeds the wall-clock timeout, writes
    cache.set_error() — last good value preserved.
  • Lazy-imports core.perception so this module costs nothing if unused.
  • Injectable snapshot_fn for tests.
  • Not registered with maez.service. Not imported by daemon/maez_daemon.py.

Future fast-lane integration will start this worker once at daemon boot,
alongside the screen worker and any future workers.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

from core.perception_cache import PerceptionCache, get_cache

logger = logging.getLogger(__name__)


# Cadence + freshness for system_state — much faster than screen because
# psutil.snapshot is local and cheap (~50ms typical).
DEFAULT_INTERVAL_S      = 2.0
DEFAULT_SNAPSHOT_TIMEOUT = 5.0
DEFAULT_FRESH_MS        = 4_000   # ≤4s old → FRESH
DEFAULT_STALE_MS        = 30_000  # >4s and ≤30s → STALE

SOURCE_NAME = 'system_state'


class SystemCacheWorker:
    """
    Background worker that refreshes system_state in the perception cache.
    Same contract as ScreenCacheWorker — see that module for the rationale.
    """

    def __init__(
        self,
        cache: Optional[PerceptionCache] = None,
        interval_s: float = DEFAULT_INTERVAL_S,
        snapshot_timeout_s: float = DEFAULT_SNAPSHOT_TIMEOUT,
        fresh_ms: int = DEFAULT_FRESH_MS,
        stale_ms: int = DEFAULT_STALE_MS,
        snapshot_fn: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.cache = cache or get_cache()
        self.interval_s = interval_s
        self.snapshot_timeout_s = snapshot_timeout_s
        self._snapshot_fn = snapshot_fn
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.cache.register(SOURCE_NAME, fresh_ms=fresh_ms, stale_ms=stale_ms)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name='system-cache-worker',
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "SystemCacheWorker started (interval=%.1fs, timeout=%.1fs)",
            self.interval_s, self.snapshot_timeout_s,
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
        result_holder: dict[str, Any] = {'value': None, 'error': None}

        def _call() -> None:
            try:
                fn = self._snapshot_fn or _default_snapshot
                result_holder['value'] = fn()
            except Exception as e:                          # pragma: no cover
                result_holder['error'] = f"snapshot raised: {e!r}"

        t = threading.Thread(target=_call, name='system-snapshot-call', daemon=True)
        t.start()
        t.join(timeout=self.snapshot_timeout_s)

        elapsed_ms = int((time.time() - start) * 1000)

        if t.is_alive():
            self.cache.set_error(
                SOURCE_NAME,
                f"snapshot timed out after {self.snapshot_timeout_s:.1f}s "
                f"(wall={elapsed_ms}ms)",
            )
            logger.warning("SystemCacheWorker: snapshot timed out")
            return

        if result_holder['error'] is not None:
            self.cache.set_error(SOURCE_NAME, result_holder['error'])
            logger.warning("SystemCacheWorker: %s", result_holder['error'])
            return

        value = result_holder['value']
        if value is None:
            self.cache.set_error(SOURCE_NAME, "snapshot returned None")
            return

        self.cache.set_value(SOURCE_NAME, value)


def _default_snapshot():
    """Lazy import so this module is free of perception deps unless run."""
    from core.perception import snapshot
    return snapshot()
