# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""BoundedSingletonWorker — at most one daemon thread at a time.

Skip-when-busy fire-and-forget, NOT a queue. NOT a pool. Concurrent
submits while a worker is in flight are REFUSED, not deferred.

Designed for daemon-survivability work where the caller's own cadence
gate decides when to *attempt* a task; this primitive only enforces
"don't pile up threads if the previous one didn't finish." The
canonical use case (slice 1.3) is the dream-cycle worker, where the
cadence gate (DREAM_COOLDOWN_S) is supposed to prevent re-spawn but
fails when a cycle takes longer than the cooldown — leaking threads.

Per-process state. Restart resets to fresh.

Not for: per-message executors that need queueing semantics, voice
gap detectors that want N>1 concurrency, or long-lived reader threads
that need different lifecycle management.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger("core.health.bounded_worker")

__all__ = ["BoundedSingletonWorker"]


class BoundedSingletonWorker:
    """Spawns at most one daemon thread at a time.

    Thread-safety contract: ``submit`` is serialized by an internal
    lock. Two concurrent ``submit`` calls when no worker is in flight
    have deterministic outcomes — exactly one wins and spawns; the rest
    return False.

    Shutdown contract: ``shutdown`` (close + wait) marks the worker
    closed; subsequent ``submit`` calls return False even if no thread
    is currently running. Use ``shutdown`` for daemon stop() flow to
    prevent stale callers from spawning a thread after the process
    has decided to exit (which would risk half-written DB rows from
    background tasks racing the exit). ``join`` is wait-only and
    leaves the worker reusable for within-flow synchronization.

    ``in_flight`` is observational and inherently racy with concurrent
    ``submit`` / thread completion. For test synchronization, use
    ``join(timeout=...)`` rather than polling ``in_flight``.
    """

    def __init__(
        self,
        *,
        name: str,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.name = name
        self._log = log or logger
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._shutdown = False

    # ── public API ────────────────────────────────────────────────────

    def submit(self, target: Callable[[], None]) -> bool:
        """Spawn a daemon thread to run ``target()``.

        Returns ``True`` if a thread was spawned, ``False`` if a
        previous worker is still alive OR the worker has been shut
        down (post-``join``). When False, ``target`` is NOT invoked.

        Exceptions raised by ``target`` are caught and logged at
        WARNING on the worker's logger; they do not propagate to the
        caller (which has already returned True). ``BaseException``
        is intentionally NOT caught — process-control exceptions
        (KeyboardInterrupt, SystemExit) bubble up to Python's default
        ``threading.excepthook`` rather than being silenced inside a
        background thread.
        """
        with self._lock:
            if self._shutdown:
                return False
            if self._thread is not None and self._thread.is_alive():
                return False
            t = threading.Thread(
                target=self._wrap(target),
                name=f"{self.name}-{id(self):x}",
                daemon=True,
            )
            self._thread = t
            t.start()
        return True

    def in_flight(self) -> bool:
        """True if a thread is currently running.

        Inherently racy with concurrent submits/completion. Tests
        should use ``join(timeout=...)`` to synchronize, not poll
        this method.
        """
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def join(self, timeout: Optional[float] = None) -> bool:
        """Wait for the in-flight thread to finish. Does NOT mark the
        worker closed — subsequent ``submit`` calls remain accepted.

        Use ``shutdown`` instead when you want close-and-wait semantics
        (e.g. daemon stop()).

        Returns ``True`` if no thread was in flight or it completed
        within ``timeout``. Returns ``False`` if the timeout elapsed
        and the thread is still alive. Idempotent.
        """
        with self._lock:
            t = self._thread
        if t is None or not t.is_alive():
            return True
        t.join(timeout=timeout)
        return not t.is_alive()

    def shutdown(self, timeout: Optional[float] = None) -> bool:
        """Mark the worker closed and wait for the in-flight thread.

        After ``shutdown`` returns, subsequent ``submit`` calls return
        ``False`` regardless of whether a thread was in flight. This
        prevents a stale caller from spawning a new thread after the
        daemon has decided to stop — a hazard for tasks that write to
        durable state (e.g. dream cycles writing to memory.db on the
        way out).

        Returns ``True`` if shutdown completed cleanly (no thread, or
        thread finished within ``timeout``). Returns ``False`` if the
        timeout elapsed and the thread is still alive (caller may
        choose to log/proceed; the daemon will exit and the daemon
        thread dies with the process).

        Idempotent — safe to call multiple times.
        """
        # Mark shutdown under lock so concurrent submits see it before
        # we release the lock to wait on the thread.
        with self._lock:
            self._shutdown = True
            t = self._thread
        if t is None or not t.is_alive():
            return True
        t.join(timeout=timeout)
        return not t.is_alive()

    # ── internals ─────────────────────────────────────────────────────

    def _wrap(self, target: Callable[[], None]) -> Callable[[], None]:
        """Wrap target with WARNING-on-Exception handling. Process-
        control exceptions (BaseException subclasses) propagate to
        Python's default thread-exception hook."""
        log = self._log
        worker_name = self.name

        def _runner() -> None:
            try:
                target()
            except Exception as exc:  # noqa: BLE001 — per-thread guard
                log.warning(
                    "bounded worker %r: target raised %s: %s",
                    worker_name,
                    type(exc).__name__,
                    exc,
                )
        return _runner

    # ── repr ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        with self._lock:
            alive = self._thread is not None and self._thread.is_alive()
            shutdown = self._shutdown
        return (
            f"BoundedSingletonWorker(name={self.name!r}, "
            f"in_flight={alive}, shutdown={shutdown})"
        )
