"""Tests for core.health.bounded_worker.BoundedSingletonWorker.

These tests are written BEFORE the primitive exists. They are expected
to fail at import-time until BoundedSingletonWorker is implemented at
core/health/bounded_worker.py per the spec.

Stdlib only. Deterministic. <2s total. No time.sleep for cross-thread
synchronization — uses threading.Event and the worker's own join().
"""

from __future__ import annotations

import logging
import threading
import time
import unittest
import unittest.mock
from unittest.mock import Mock

from core.health.bounded_worker import BoundedSingletonWorker


class BoundedSingletonWorkerTests(unittest.TestCase):
    # Test 12 pins on thread name. The implementer must include
    # the worker's `name` in the spawned thread's `.name` attribute.

    def setUp(self):
        # Track events so tearDown can release any blocked workers.
        self._release_events: list[threading.Event] = []
        self._workers: list[BoundedSingletonWorker] = []

    def tearDown(self):
        # Best-effort: release any still-blocked workers and join them
        # so a buggy implementation cannot leak threads across tests.
        for ev in self._release_events:
            ev.set()
        for w in self._workers:
            try:
                w.join(timeout=1.0)
            except Exception:
                pass

    def _make_worker(self, name="test-worker", log=None):
        w = BoundedSingletonWorker(name=name, log=log)
        self._workers.append(w)
        return w

    def _make_release_event(self):
        ev = threading.Event()
        self._release_events.append(ev)
        return ev

    # ------------------------------------------------------------------
    # 1. First submit spawns and returns True
    # ------------------------------------------------------------------
    def test_first_submit_spawns_and_returns_true(self):
        w = self._make_worker()
        done = threading.Event()

        def fn():
            done.set()

        result = w.submit(fn)
        self.assertTrue(result)
        self.assertTrue(done.wait(timeout=1.0), "target was never invoked")
        self.assertTrue(w.join(timeout=1.0))

    # ------------------------------------------------------------------
    # 2. Concurrent submit returns False without invoking target
    # ------------------------------------------------------------------
    def test_concurrent_submit_returns_false_without_invoking_target(self):
        w = self._make_worker()
        started = threading.Event()
        release = self._make_release_event()

        def blocker():
            started.set()
            release.wait(timeout=2.0)

        first = w.submit(blocker)
        self.assertTrue(first)
        self.assertTrue(started.wait(timeout=1.0))

        second_target = Mock()
        try:
            second = w.submit(second_target)
            self.assertFalse(
                second,
                "second submit should be refused while first is in flight",
            )
            self.assertEqual(
                second_target.call_count,
                0,
                "refused submit must NOT invoke the second target",
            )
        finally:
            release.set()

        self.assertTrue(w.join(timeout=1.0))

    # ------------------------------------------------------------------
    # 3. Submit after completion succeeds again
    # ------------------------------------------------------------------
    def test_submit_after_completion_succeeds_again(self):
        w = self._make_worker()
        first_done = threading.Event()
        second_done = threading.Event()

        self.assertTrue(w.submit(first_done.set))
        self.assertTrue(w.join(timeout=1.0))
        self.assertTrue(first_done.is_set())

        self.assertTrue(w.submit(second_done.set))
        self.assertTrue(w.join(timeout=1.0))
        self.assertTrue(second_done.is_set())

    # ------------------------------------------------------------------
    # 4. in_flight() reports correctly
    # ------------------------------------------------------------------
    def test_in_flight_reports_correctly(self):
        w = self._make_worker()
        self.assertFalse(w.in_flight(), "fresh worker should not be in flight")

        started = threading.Event()
        release = self._make_release_event()

        def blocker():
            started.set()
            release.wait(timeout=2.0)

        try:
            self.assertTrue(w.submit(blocker))
            self.assertTrue(started.wait(timeout=1.0))
            self.assertTrue(
                w.in_flight(),
                "in_flight should be True while target is running",
            )
        finally:
            release.set()

        self.assertTrue(w.join(timeout=1.0))
        self.assertFalse(
            w.in_flight(),
            "in_flight should be False after target completes",
        )

    # ------------------------------------------------------------------
    # 5. join() with no thread returns True immediately
    # ------------------------------------------------------------------
    def test_join_with_no_thread_returns_true_immediately(self):
        w = self._make_worker()
        t0 = time.monotonic()
        result = w.join(timeout=0.01)
        elapsed = time.monotonic() - t0
        self.assertTrue(result)
        self.assertLess(
            elapsed,
            0.5,
            "join on idle worker should return effectively immediately",
        )

    # ------------------------------------------------------------------
    # 6. join() returns True when thread completes within timeout
    # ------------------------------------------------------------------
    def test_join_returns_true_when_thread_completes_within_timeout(self):
        w = self._make_worker()

        def quick():
            time.sleep(0.05)

        self.assertTrue(w.submit(quick))
        self.assertTrue(w.join(timeout=1.0))
        self.assertFalse(w.in_flight())

    # ------------------------------------------------------------------
    # 7. join() returns False on timeout
    # ------------------------------------------------------------------
    def test_join_returns_false_on_timeout(self):
        w = self._make_worker()
        started = threading.Event()
        release = self._make_release_event()

        def blocker():
            started.set()
            release.wait(timeout=2.0)

        try:
            self.assertTrue(w.submit(blocker))
            self.assertTrue(started.wait(timeout=1.0))
            self.assertFalse(
                w.join(timeout=0.05),
                "join must return False when the thread is still running",
            )
            self.assertTrue(w.in_flight())
        finally:
            release.set()

        self.assertTrue(w.join(timeout=1.0))

    # ------------------------------------------------------------------
    # 8. Target exception is logged, not propagated
    # ------------------------------------------------------------------
    def test_target_exception_is_logged_not_propagated(self):
        w = self._make_worker(name="exc-worker")

        def boom():
            raise ValueError("kaboom")

        # The worker is expected to log on a logger whose name we don't
        # know a priori. Capture at the root logger to be permissive,
        # then assert at WARNING level.
        with self.assertLogs(level="WARNING") as cm:
            result = w.submit(boom)
            self.assertTrue(
                result,
                "submit returns True because the thread WAS spawned",
            )
            self.assertTrue(w.join(timeout=1.0))

        joined = "\n".join(cm.output)
        self.assertIn("WARNING", joined)
        self.assertFalse(
            w.in_flight(),
            "worker should recover (not stuck in_flight) after exception",
        )

    # ------------------------------------------------------------------
    # 9. Target exception does not block future submits
    # ------------------------------------------------------------------
    def test_target_exception_does_not_block_future_submits(self):
        w = self._make_worker()

        def boom():
            raise RuntimeError("first one fails")

        with self.assertLogs(level="WARNING"):
            self.assertTrue(w.submit(boom))
            self.assertTrue(w.join(timeout=1.0))

        recovered = threading.Event()
        self.assertTrue(w.submit(recovered.set))
        self.assertTrue(w.join(timeout=1.0))
        self.assertTrue(
            recovered.is_set(),
            "second submit after exception must run normally",
        )

    # ------------------------------------------------------------------
    # 10. Thread count bounded under rapid submits
    # ------------------------------------------------------------------
    def test_thread_count_bounded_under_rapid_submits(self):
        w = self._make_worker()
        started = threading.Event()
        release = self._make_release_event()

        def blocker():
            started.set()
            release.wait(timeout=2.0)

        target = Mock(side_effect=blocker)

        try:
            first = w.submit(target)
            self.assertTrue(first)
            self.assertTrue(started.wait(timeout=1.0))

            refused = 0
            for _ in range(50):
                if w.submit(target) is False:
                    refused += 1

            self.assertEqual(
                refused,
                50,
                "all 50 concurrent submits must be refused",
            )
            # Only the first call ever ran; the 50 refused submits must
            # NOT have invoked target.
            self.assertEqual(
                target.call_count,
                1,
                "refused submits must not invoke target; only first call counted",
            )
        finally:
            release.set()

        self.assertTrue(w.join(timeout=1.0))

    # ------------------------------------------------------------------
    # 11. Logger can be injected
    # ------------------------------------------------------------------
    def test_logger_can_be_injected(self):
        custom = logging.getLogger("maez.test.bounded_worker.injected")
        w = self._make_worker(name="injected-worker", log=custom)

        def boom():
            raise ValueError("custom-logger-path")

        with self.assertLogs(custom.name, level="WARNING") as cm:
            self.assertTrue(w.submit(boom))
            self.assertTrue(w.join(timeout=1.0))

        self.assertTrue(
            any("WARNING" in line for line in cm.output),
            "exception must be logged to the injected logger at WARNING",
        )

    # ------------------------------------------------------------------
    # 12. Name appears in spawned thread's .name (pinned)
    # ------------------------------------------------------------------
    def test_name_appears_in_thread_name_or_log(self):
        worker_name = "distinct-pin-name-xyzzy"
        w = self._make_worker(name=worker_name)

        started = threading.Event()
        release = self._make_release_event()
        captured: dict[str, str] = {}

        def blocker():
            captured["thread_name"] = threading.current_thread().name
            started.set()
            release.wait(timeout=2.0)

        try:
            self.assertTrue(w.submit(blocker))
            self.assertTrue(started.wait(timeout=1.0))
            self.assertIn(
                worker_name,
                captured.get("thread_name", ""),
                "spawned thread .name must include the worker's name",
            )
        finally:
            release.set()

        self.assertTrue(w.join(timeout=1.0))

    # ------------------------------------------------------------------
    # 13. shutdown() marks worker closed — subsequent submits refused
    # (Critical #2 from slice 1.3 adversarial review: prevents a stale
    #  caller from spawning a new worker thread AFTER the daemon has
    #  decided to stop. Daemon dream cycles write to DB; a thread
    #  spawned post-shutdown could leave half-written rows.)
    #
    # Distinct from join(): join is wait-only and leaves the worker
    # reusable; shutdown is close+wait and is one-way.
    # ------------------------------------------------------------------
    def test_submit_after_shutdown_returns_false(self):
        w = self._make_worker(name="shutdown-test")

        # First submit succeeds.
        ran_first = threading.Event()
        self.assertTrue(w.submit(lambda: ran_first.set()))
        self.assertTrue(w.shutdown(timeout=1.0))
        self.assertTrue(ran_first.is_set())

        # shutdown() implies "no more work" — subsequent submits must
        # refuse, even if no thread is currently in flight.
        spy = unittest.mock.Mock()
        self.assertFalse(
            w.submit(spy),
            "submit after shutdown() must return False",
        )
        self.assertEqual(
            spy.call_count, 0,
            "submit after shutdown() must NOT invoke target",
        )

    def test_join_does_not_mark_shutdown(self):
        """join() is wait-only — the worker stays reusable. This is
        the behavioral split that lets within-test patterns like
        'submit→join→submit-again' keep working while shutdown()
        provides a one-way close for daemon stop()."""
        w = self._make_worker(name="join-not-shutdown")

        ran_first = threading.Event()
        self.assertTrue(w.submit(lambda: ran_first.set()))
        self.assertTrue(w.join(timeout=1.0))
        self.assertTrue(ran_first.is_set())

        # After join, submit must STILL succeed.
        ran_second = threading.Event()
        self.assertTrue(
            w.submit(lambda: ran_second.set()),
            "submit after join() must succeed (join is wait-only)",
        )
        self.assertTrue(w.join(timeout=1.0))
        self.assertTrue(ran_second.is_set())

        # shutdown closes for real.
        self.assertTrue(w.shutdown(timeout=1.0))
        self.assertFalse(w.submit(Mock()))

    # ------------------------------------------------------------------
    # 14. Concurrent submits at the moment a previous worker finishes
    # are deterministic (Critical #1: internal lock around check-and-spawn)
    # ------------------------------------------------------------------
    def test_concurrent_submits_are_serialized(self):
        """Many threads call submit() simultaneously while no worker is
        in flight. Exactly ONE must win and spawn; the rest must refuse.
        Without an internal lock, two could pass the is_alive() check
        and both spawn — violating the at-most-one contract.
        """
        w = self._make_worker(name="serialized")

        N = 32
        ran = threading.Event()
        release = threading.Event()

        def long_running():
            ran.set()
            release.wait(timeout=2.0)

        results: list[bool] = []
        results_lock = threading.Lock()
        start_gate = threading.Event()

        def attempt():
            start_gate.wait()
            ok = w.submit(long_running)
            with results_lock:
                results.append(ok)

        try:
            threads = [
                threading.Thread(target=attempt) for _ in range(N)
            ]
            for t in threads:
                t.start()
            start_gate.set()
            for t in threads:
                t.join(timeout=2.0)

            # Exactly one True, rest False.
            wins = sum(1 for r in results if r)
            self.assertEqual(
                wins, 1,
                f"exactly one submit must win; got {wins} wins out of {N}",
            )
            # Confirm only one target invocation (the winning submit).
            self.assertTrue(ran.wait(timeout=1.0))
        finally:
            release.set()

        self.assertTrue(w.join(timeout=2.0))


if __name__ == "__main__":
    unittest.main()
