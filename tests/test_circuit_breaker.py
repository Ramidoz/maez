"""Tests for core.health.circuit_breaker.CircuitBreaker.

Implementation contract (to be built at core/health/circuit_breaker.py):

    class CircuitBreaker:
        def __init__(self, *, name: str,
                     failure_threshold: int = 5,
                     window_s: float = 60.0,
                     cooldown_s: float = 30.0,
                     clock: Callable[[], float] = time.monotonic):
            ...
        def call(self, fn, *args, **kwargs): ...
        @property
        def state(self) -> str: ...  # 'closed' | 'open' | 'half_open'

    class CircuitOpen(Exception): ...

States:
- CLOSED: pass through; record failures with timestamps from `clock()`.
  When count of failures within last `window_s` seconds >= failure_threshold,
  transition to OPEN with cooldown_until = clock() + cooldown_s.
- OPEN: raise CircuitOpen immediately without invoking fn.
  When clock() >= cooldown_until, the next call enters HALF_OPEN.
- HALF_OPEN: invoke fn ONCE. Success -> CLOSED + clear history.
  Failure -> OPEN with new cooldown (counts as one failure).
  Concurrent calls during HALF_OPEN: only the first proceeds; rest see CircuitOpen
  until the probe completes.

The breaker MUST use the injected `clock` for all time decisions (so tests can
deterministically advance time without real sleeps), and MUST be thread-safe.
"""
from __future__ import annotations

import threading
import unittest
from unittest.mock import Mock

from core.health.circuit_breaker import CircuitBreaker, CircuitOpen


class FakeClock:
    """Deterministic monotonic clock for tests."""

    def __init__(self, start: float = 1000.0):
        self._t = start
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self._t

    def advance(self, delta: float) -> None:
        with self._lock:
            self._t += delta


def _boom(*_a, **_kw):
    raise RuntimeError("boom")


class TestClosedPassThrough(unittest.TestCase):
    def test_closed_passes_through(self):
        clock = FakeClock()
        cb = CircuitBreaker(name="cb1", failure_threshold=3, window_s=60.0,
                            cooldown_s=30.0, clock=clock)
        result = cb.call(lambda x, y: x + y, 2, 3)
        self.assertEqual(result, 5)
        self.assertEqual(cb.state, "closed")


class TestFailureCounting(unittest.TestCase):
    def test_failure_below_threshold_stays_closed(self):
        clock = FakeClock()
        threshold = 3
        cb = CircuitBreaker(name="cb", failure_threshold=threshold,
                            window_s=60.0, cooldown_s=30.0, clock=clock)
        # threshold-1 failures: stays closed
        for _ in range(threshold - 1):
            with self.assertRaises(RuntimeError):
                cb.call(_boom)
            self.assertEqual(cb.state, "closed")
        # threshold-th failure: flips to open
        with self.assertRaises(RuntimeError):
            cb.call(_boom)
        self.assertEqual(cb.state, "open")

    def test_failures_outside_window_dont_count(self):
        clock = FakeClock()
        threshold = 3
        window = 10.0
        cb = CircuitBreaker(name="cb", failure_threshold=threshold,
                            window_s=window, cooldown_s=30.0, clock=clock)
        # Spread failures > window_s apart so none coexist in the same window.
        for _ in range(threshold + 2):
            with self.assertRaises(RuntimeError):
                cb.call(_boom)
            clock.advance(window + 1.0)
        # Still closed: no `threshold` failures fall within any single window.
        self.assertEqual(cb.state, "closed")


class TestOpenShortCircuits(unittest.TestCase):
    def test_open_raises_without_invoking_fn(self):
        clock = FakeClock()
        cb = CircuitBreaker(name="cb", failure_threshold=2, window_s=60.0,
                            cooldown_s=30.0, clock=clock)
        # Trip the breaker.
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                cb.call(_boom)
        self.assertEqual(cb.state, "open")

        spy = Mock(return_value="never")
        with self.assertRaises(CircuitOpen):
            cb.call(spy, 1, 2, kw=3)
        self.assertEqual(spy.call_count, 0)


class TestCooldownAndHalfOpen(unittest.TestCase):
    def _trip(self, cb, n):
        for _ in range(n):
            with self.assertRaises(RuntimeError):
                cb.call(_boom)

    def test_cooldown_elapses_to_half_open(self):
        clock = FakeClock()
        cb = CircuitBreaker(name="cb", failure_threshold=2, window_s=60.0,
                            cooldown_s=30.0, clock=clock)
        self._trip(cb, 2)
        self.assertEqual(cb.state, "open")

        # Before cooldown elapses: still open, fn not invoked.
        clock.advance(29.0)
        spy = Mock(return_value="ok")
        with self.assertRaises(CircuitOpen):
            cb.call(spy)
        self.assertEqual(spy.call_count, 0)

        # After cooldown: half-open allows a probe.
        clock.advance(2.0)  # total 31s past trip
        result = cb.call(lambda: "probed")
        self.assertEqual(result, "probed")

    def test_half_open_success_closes_circuit(self):
        clock = FakeClock()
        cb = CircuitBreaker(name="cb", failure_threshold=2, window_s=60.0,
                            cooldown_s=30.0, clock=clock)
        self._trip(cb, 2)
        clock.advance(31.0)
        # Probe succeeds: circuit closes, history clears.
        self.assertEqual(cb.call(lambda: 42), 42)
        self.assertEqual(cb.state, "closed")
        # History was cleared: a single new failure should not reopen.
        with self.assertRaises(RuntimeError):
            cb.call(_boom)
        self.assertEqual(cb.state, "closed")

    def test_half_open_failure_reopens_with_new_cooldown(self):
        clock = FakeClock()
        cb = CircuitBreaker(name="cb", failure_threshold=2, window_s=60.0,
                            cooldown_s=30.0, clock=clock)
        self._trip(cb, 2)
        clock.advance(31.0)
        # Probe fails: back to open with a fresh cooldown.
        with self.assertRaises(RuntimeError):
            cb.call(_boom)
        self.assertEqual(cb.state, "open")

        # Subsequent calls before the new cooldown raise CircuitOpen.
        clock.advance(5.0)
        spy = Mock()
        with self.assertRaises(CircuitOpen):
            cb.call(spy)
        self.assertEqual(spy.call_count, 0)
        self.assertEqual(cb.state, "open")

        # And after the new cooldown expires we can probe again.
        clock.advance(30.0)
        self.assertEqual(cb.call(lambda: "ok"), "ok")
        self.assertEqual(cb.state, "closed")


class TestConcurrency(unittest.TestCase):
    def test_concurrent_half_open_only_one_probes(self):
        clock = FakeClock()
        cb = CircuitBreaker(name="cb", failure_threshold=2, window_s=60.0,
                            cooldown_s=30.0, clock=clock)
        # Trip then expire cooldown -> half-open.
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                cb.call(_boom)
        clock.advance(31.0)

        gate = threading.Event()
        proceed = threading.Event()
        call_count = {"n": 0}
        count_lock = threading.Lock()

        def slow_probe():
            with count_lock:
                call_count["n"] += 1
            gate.set()
            # Wait so the second thread has time to attempt and be rejected.
            proceed.wait(timeout=1.0)
            return "probed"

        results = {}
        errors = {}

        def worker(tag):
            try:
                results[tag] = cb.call(slow_probe)
            except CircuitOpen as e:
                errors[tag] = e
            except Exception as e:  # pragma: no cover - defensive
                errors[tag] = e

        t1 = threading.Thread(target=worker, args=("a",))
        t1.start()
        # Wait until the first thread is inside slow_probe.
        self.assertTrue(gate.wait(timeout=1.0), "first probe never started")

        t2 = threading.Thread(target=worker, args=("b",))
        t2.start()
        t2.join(timeout=1.0)

        # Second thread must have been short-circuited.
        self.assertIn("b", errors)
        self.assertIsInstance(errors["b"], CircuitOpen)

        proceed.set()
        t1.join(timeout=1.0)

        self.assertEqual(call_count["n"], 1)
        self.assertEqual(results.get("a"), "probed")

    def test_thread_safe_failure_counting(self):
        clock = FakeClock()
        N = 50
        # Threshold larger than N so we don't trip mid-test; we only check
        # that all N failures were observed by the breaker (no lost updates).
        cb = CircuitBreaker(name="cb", failure_threshold=N + 1,
                            window_s=600.0, cooldown_s=30.0, clock=clock)

        start = threading.Event()

        def worker():
            start.wait()
            try:
                cb.call(_boom)
            except RuntimeError:
                pass

        threads = [threading.Thread(target=worker) for _ in range(N)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join(timeout=2.0)

        # One more failure should now exceed the threshold and open the breaker.
        # If any of the N concurrent failures were lost, the breaker would
        # remain closed.
        self.assertEqual(cb.state, "closed")
        with self.assertRaises(RuntimeError):
            cb.call(_boom)
        self.assertEqual(cb.state, "open")


class TestStateProperty(unittest.TestCase):
    def test_state_property_is_consistent(self):
        clock = FakeClock()
        cb = CircuitBreaker(name="cb", failure_threshold=2, window_s=60.0,
                            cooldown_s=30.0, clock=clock)
        valid = {"closed", "open", "half_open"}

        self.assertIn(cb.state, valid)

        # After failures.
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                cb.call(_boom)
        self.assertIn(cb.state, valid)

        # After cooldown.
        clock.advance(31.0)
        self.assertIn(cb.state, valid)

        # After successful probe.
        cb.call(lambda: None)
        self.assertIn(cb.state, valid)


class TestRepr(unittest.TestCase):
    def test_breaker_name_is_in_repr_or_str(self):
        cb = CircuitBreaker(name="db_writer", failure_threshold=2,
                            window_s=60.0, cooldown_s=30.0,
                            clock=FakeClock())
        self.assertTrue(
            "db_writer" in repr(cb) or "db_writer" in str(cb),
            f"name not visible: repr={repr(cb)!r} str={str(cb)!r}",
        )


class TestShouldCountFailure(unittest.TestCase):
    """Caller can mark certain exceptions as 'don't count toward threshold'.

    Why: some failures are caller-side bugs (malformed prompt template,
    bad response shape) that would deterministically open the circuit
    forever even though the backend is healthy. The caller knows which
    exceptions are transport-class vs. caller-class; the breaker does
    not.
    """

    def test_predicate_excludes_failure_from_count(self):
        clock = FakeClock()
        cb = CircuitBreaker(name="cb", failure_threshold=2, window_s=60.0,
                            cooldown_s=30.0, clock=clock)

        class BenignError(Exception):
            pass

        # Predicate returns False for BenignError → not counted.
        not_counted = lambda e: not isinstance(e, BenignError)

        def benign():
            raise BenignError("not transport-class")

        for _ in range(5):
            with self.assertRaises(BenignError):
                cb.call(benign, should_count_failure=not_counted)

        # Five 'benign' raises in window did NOT trip the breaker.
        self.assertEqual(cb.state, "closed")

        # Real transport failures still count.
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                cb.call(_boom)
        self.assertEqual(cb.state, "open")

    def test_half_open_not_counted_failure_closes_circuit(self):
        """In HALF_OPEN, a not-counted failure means transport recovered
        (we got past the network and got a response, even if body was
        wrong). The breaker should treat that as probe-success and CLOSE,
        otherwise it would stay HALF_OPEN forever — throttling concurrent
        callers via the probe lock even though transport is healthy.

        Reproduces a bug missed by the slice 1.2 review: bad_response
        during HALF_OPEN left the breaker stuck.
        """
        clock = FakeClock()
        cb = CircuitBreaker(name="cb", failure_threshold=2, window_s=60.0,
                            cooldown_s=30.0, clock=clock)

        class BenignError(Exception):
            pass

        not_counted = lambda e: not isinstance(e, BenignError)

        # Trip the breaker with real (counted) failures.
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                cb.call(_boom)
        self.assertEqual(cb.state, "open")

        # Cooldown elapses → HALF_OPEN admission for next call.
        clock.advance(31.0)

        # Probe gets a not-counted failure (e.g. bad_response).
        # The original exception must propagate to the caller.
        with self.assertRaises(BenignError):
            cb.call(
                lambda: (_ for _ in ()).throw(BenignError("malformed body")),
                should_count_failure=not_counted,
            )

        # Breaker must be CLOSED — transport is fine, we got past the network.
        self.assertEqual(
            cb.state, "closed",
            "HALF_OPEN + not-counted failure means transport recovered; "
            "breaker must close (was stuck in half_open before fix)",
        )

        # And subsequent calls are NOT throttled by the probe lock —
        # two threads calling concurrently both proceed.
        proceed = threading.Event()

        def slow_ok():
            proceed.wait(timeout=1.0)
            return "ok"

        results = {}
        def worker(tag):
            results[tag] = cb.call(slow_ok)

        t1 = threading.Thread(target=worker, args=("a",))
        t2 = threading.Thread(target=worker, args=("b",))
        t1.start(); t2.start()
        proceed.set()
        t1.join(timeout=1.0); t2.join(timeout=1.0)

        self.assertEqual(results.get("a"), "ok")
        self.assertEqual(results.get("b"), "ok")


if __name__ == "__main__":
    unittest.main()
