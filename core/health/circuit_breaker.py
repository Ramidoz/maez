# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""In-memory failure-counting circuit breaker.

Exists to stop wasted connect attempts to a wedged backend. The audit-gate
fail-open contract is preserved: callers still see the same exception
shape they did before; only the *source* of the failure (and its cost)
changes during sustained outages.

Defaults (failure_threshold=3, window_s=300, cooldown_s=30) were tuned
against the May 2026 grounding-judge outage signature where the daemon
called the judge ~1× per cycle (~30s) and saw 2,086 'Connection refused'
events on a single day. A 60s window with 5 failures couldn't trip under
that call rate.

Per-process state. Restart resets to CLOSED; this is intentional —
persistence would mask config errors and make deploys feel buggy.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable

logger = logging.getLogger("core.health.circuit_breaker")

__all__ = ["CircuitBreaker", "CircuitOpen"]

_VALID_STATES = frozenset({"closed", "open", "half_open"})


class CircuitOpen(Exception):
    """Raised by ``CircuitBreaker.call`` when the circuit is OPEN, or
    when HALF_OPEN and another thread is already probing."""


class CircuitBreaker:
    """Three-state breaker: CLOSED → OPEN (after N failures in window) →
    HALF_OPEN (after cooldown) → CLOSED on probe success.

    Thread-safe. The HALF_OPEN single-probe admission is non-blocking:
    concurrent callers get ``CircuitOpen`` immediately rather than queuing
    behind the probe (otherwise the breaker would defeat its own purpose
    when the probe is slow). The probe is wrapped in try/finally so a
    crashing probe always restores breaker state.
    """

    def __init__(
        self,
        *,
        name: str,
        failure_threshold: int = 3,
        window_s: float = 300.0,
        cooldown_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
        log: logging.Logger | None = None,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if window_s <= 0:
            raise ValueError("window_s must be > 0")
        if cooldown_s <= 0:
            raise ValueError("cooldown_s must be > 0")
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_s = float(window_s)
        self.cooldown_s = float(cooldown_s)
        self._clock = clock
        # Caller-injectable logger so state-transition WARNINGs land on
        # the caller's logger hierarchy (matters for test assertLogs and
        # operator log filters that key off module name).
        self._log = log or logger

        self._lock = threading.Lock()
        # Probe lock is acquired non-blocking by HALF_OPEN admission.
        self._probe_lock = threading.Lock()

        self._failures: deque[float] = deque()
        self._state: str = "closed"
        self._opened_at: float | None = None  # when we last entered OPEN

    # ── public API ────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        """Current state, computed lazily under the lock so cooldown
        elapsing is reflected even without an intervening call."""
        with self._lock:
            return self._compute_state_locked()

    def call(
        self,
        fn: Callable[..., Any],
        *args: Any,
        should_count_failure: Callable[[Exception], bool] = lambda e: True,
        **kwargs: Any,
    ) -> Any:
        """Run ``fn(*args, **kwargs)`` under the breaker.

        ``should_count_failure``: predicate over a raised exception.
        Return ``True`` to count it toward the failure threshold,
        ``False`` to let it surface without affecting breaker state.
        Default counts every exception.

        Catches ``Exception``, not ``BaseException``: process-control
        exceptions (KeyboardInterrupt, SystemExit, GeneratorExit) bypass
        breaker accounting and propagate without releasing the probe
        lock. That's intentional — those are not transport failures.
        If the probe is interrupted by KeyboardInterrupt, the probe
        lock stays held until process exit, which is the correct
        posture for a process that's about to die anyway.
        """
        admission = self._admit()
        if admission == "reject":
            raise CircuitOpen(f"{self.name}: circuit open")
        # admission is 'closed' (normal) or 'probe' (HALF_OPEN single-probe).

        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            if should_count_failure(exc):
                self._record_failure(admission)
            elif admission == "probe":
                # Not-counted failure during HALF_OPEN means we got past
                # the network and got a response — even though the body
                # was wrong, transport recovered. Treat as probe-success
                # for breaker-state purposes (close + clear history),
                # then propagate the original exception. Otherwise the
                # breaker would stay HALF_OPEN forever, throttling all
                # concurrent callers via the probe lock even though the
                # backend is reachable.
                self._record_success(admission)
            raise
        else:
            self._record_success(admission)
            return result

    # ── admission and state ───────────────────────────────────────────

    def _admit(self) -> str:
        """Decide whether the next call goes through.

        Returns:
            'closed' — call should proceed (CLOSED state).
            'probe'  — call should proceed as the single HALF_OPEN probe.
            'reject' — caller should raise ``CircuitOpen``.
        """
        with self._lock:
            state = self._compute_state_locked()
            if state == "closed":
                return "closed"
            if state == "open":
                return "reject"
            # state == "half_open"
            # Try to grab the probe slot non-blockingly. If another
            # thread is already probing, reject this caller.
            if self._probe_lock.acquire(blocking=False):
                return "probe"
            return "reject"

    def _compute_state_locked(self) -> str:
        """Resolve current state. Caller must hold ``self._lock``."""
        if self._state == "open":
            assert self._opened_at is not None
            if self._clock() - self._opened_at >= self.cooldown_s:
                # Cooldown elapsed — eligible for half-open. Don't acquire
                # the probe lock here; that's the admission step's job so
                # only an actual call can take the probe slot.
                self._state = "half_open"
        return self._state

    # ── outcomes ──────────────────────────────────────────────────────

    def _record_failure(self, admission: str) -> None:
        with self._lock:
            now = self._clock()
            self._failures.append(now)
            self._evict_old_failures_locked(now)

            if admission == "probe":
                # Probe failed: back to OPEN with a fresh cooldown.
                self._open_locked(now)
                self._release_probe_lock()
                return

            # Normal CLOSED-path failure. Trip if threshold reached.
            if len(self._failures) >= self.failure_threshold:
                self._open_locked(now)

    def _record_success(self, admission: str) -> None:
        if admission != "probe":
            # Successes in CLOSED don't change state. We don't decrement
            # the failure window here — old failures age out via the
            # window.
            return
        # HALF_OPEN probe succeeded: close the circuit and clear history.
        with self._lock:
            self._state = "closed"
            self._opened_at = None
            self._failures.clear()
            self._release_probe_lock()
            self._log.warning(
                "circuit breaker %r: probe success → CLOSED", self.name,
            )

    # ── helpers ───────────────────────────────────────────────────────

    def _evict_old_failures_locked(self, now: float) -> None:
        cutoff = now - self.window_s
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

    def _open_locked(self, now: float) -> None:
        was_closed = self._state != "open"
        self._state = "open"
        self._opened_at = now
        if was_closed:
            self._log.warning(
                "circuit breaker %r: OPEN (failures=%d, window=%.0fs, "
                "cooldown=%.0fs)",
                self.name, len(self._failures),
                self.window_s, self.cooldown_s,
            )

    def _release_probe_lock(self) -> None:
        # Best-effort release; holding it on a code path that didn't
        # acquire it would be a logic error worth surfacing, so don't
        # swallow.
        try:
            self._probe_lock.release()
        except RuntimeError:
            # Already released — defensive against double-release if
            # called from both success and failure paths.
            pass

    # ── repr ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, "
            f"state={self._state}, "
            f"threshold={self.failure_threshold}, "
            f"window_s={self.window_s}, "
            f"cooldown_s={self.cooldown_s})"
        )
