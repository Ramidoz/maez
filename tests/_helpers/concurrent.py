# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Concurrent-test helper.

Test-only. Imports from ``threading`` and the standard library only —
**no production imports** (`core`, `daemon`, `skills`, `memory`).
A bug in core/ must not be able to break tests via this helper, and
helper changes must never have a runtime effect.

Why this exists: race-condition fixes need deterministic regression
tests. ``run_two_threads`` runs two functions concurrently with a
barrier-synchronized start, captures exceptions from both, and
times out cleanly. ``Interleave`` lets a test force a specific
step-by-step ordering between the two threads — the precondition
for proving "thread A racing thread B at *exactly* this point"
behaves correctly.

Both helpers are intentionally narrow. This is not a concurrency
framework; it's a tool for deterministic two-thread tests.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class ThreadResult:
    """Captured outcome of one thread's execution.

    ok           — True iff the function returned normally.
    return_value — function's return; meaningful only when ok.
    exception    — captured exception (with traceback preserved
                   on the raised instance); meaningful only when
                   not ok.
    """
    return_value: Any = None
    exception: Optional[BaseException] = None

    @property
    def ok(self) -> bool:
        return self.exception is None


def run_two_threads(
    fn_a: Callable[[], Any],
    fn_b: Callable[[], Any],
    *,
    barrier: bool = True,
    timeout: float = 5.0,
) -> tuple[ThreadResult, ThreadResult]:
    """Execute ``fn_a`` and ``fn_b`` concurrently. Return both
    outcomes.

    barrier=True (default) → both threads cross the start line
    within a few ms of each other (synchronized via
    ``threading.Barrier``). Without this, the second-launched
    thread typically starts a few ms after the first; tests that
    care about exact concurrent execution need the barrier.

    barrier=False → threads start in launch order; second starts
    a few ms after first. Useful for tests that just want both
    functions to run without exact start-time synchronization.

    timeout (seconds) → raise ``TimeoutError`` if either thread
    hasn't completed within the window. Never let a hung test hang
    the whole suite.
    """
    result_a = ThreadResult()
    result_b = ThreadResult()

    if barrier:
        start_barrier = threading.Barrier(2)

    def _wrap(fn: Callable[[], Any], result: ThreadResult) -> None:
        try:
            if barrier:
                # Wait for the other thread to be ready before
                # entering the user's function.
                start_barrier.wait(timeout=timeout)
            result.return_value = fn()
        except BaseException as e:  # capture EVERYTHING, even SystemExit
            result.exception = e

    thread_a = threading.Thread(
        target=_wrap, args=(fn_a, result_a),
        name="run_two_threads:A", daemon=True,
    )
    thread_b = threading.Thread(
        target=_wrap, args=(fn_b, result_b),
        name="run_two_threads:B", daemon=True,
    )

    deadline = time.monotonic() + timeout
    thread_a.start()
    thread_b.start()

    for t in (thread_a, thread_b):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"run_two_threads: thread {t.name!r} did not finish "
                f"within {timeout:.2f}s"
            )
        t.join(timeout=remaining)
        if t.is_alive():
            raise TimeoutError(
                f"run_two_threads: thread {t.name!r} still alive "
                f"after {timeout:.2f}s — likely hung; daemon=True "
                f"so it will be cleaned up at process exit"
            )

    return result_a, result_b


class Interleave:
    """Force a specific step-by-step interleaving between two
    threads.

    Construct with ``Interleave(n_steps=N)``; each thread can then
    call ``step(i)`` to signal it has reached step ``i``, or
    ``wait(i, timeout=...)`` to block until the *other* thread
    signals step ``i``. Steps are 0-indexed; ``step(i)`` is
    idempotent; ``wait(i)`` blocks until ``step(i)`` has been
    called at least once.

    Out-of-range step indices raise ``IndexError`` so a typo in
    the test fails loudly instead of hanging on a never-signaled
    step.

    A common pattern:

        events = Interleave(n_steps=4)

        def thread_a():
            events.wait(0)        # gate: B reached its setup
            do_first_thing()
            events.step(1)        # tell B I'm done
            events.wait(2)        # gate: B did its middle
            do_second_thing()
            events.step(3)

        def thread_b():
            events.step(0)        # tell A I'm here
            ...
    """

    def __init__(self, *, n_steps: int) -> None:
        if n_steps <= 0:
            raise ValueError("n_steps must be positive")
        self._events: list[threading.Event] = [
            threading.Event() for _ in range(n_steps)
        ]

    def _check(self, n: int) -> None:
        if not 0 <= n < len(self._events):
            raise IndexError(
                f"step index {n} out of range [0, {len(self._events)})"
            )

    def step(self, n: int) -> None:
        """Signal that step ``n`` has been reached."""
        self._check(n)
        self._events[n].set()

    def wait(self, n: int, *, timeout: float = 5.0) -> None:
        """Block until ``step(n)`` has been called by the other
        thread. Raise ``TimeoutError`` after ``timeout`` seconds —
        never hang indefinitely on a never-signaled step."""
        self._check(n)
        if not self._events[n].wait(timeout=timeout):
            raise TimeoutError(
                f"Interleave.wait({n}) timed out after {timeout:.2f}s "
                f"— the other thread never called step({n})"
            )
