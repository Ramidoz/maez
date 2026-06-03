# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Cognition liveness must be true and recoverable.

Regression target: the daemon can answer /health while the reasoning-loop
thread has died. The top-line health status must derive from the loop heartbeat,
and the recovery path must restart the whole process rather than resurrecting a
possibly half-mutated thread.
"""

from __future__ import annotations

import os
import re
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent


def _daemon_stub(**overrides):
    import daemon.maez_daemon as md

    daemon = md.MaezDaemon.__new__(md.MaezDaemon)
    daemon.running = True
    daemon.boot_time = "2026-06-03T00:00:00+00:00"
    daemon.cycle_count = 12
    daemon.last_cycle_time = "2026-06-03T00:00:00+00:00"
    daemon._cycle_stage = "deferred_actions"
    daemon._cycle_stage_started_at = "2026-06-03T00:00:00+00:00"
    daemon._cycle_failure_stage = ""
    daemon._cycle_failure_count = 0
    daemon._cycle_failure_threshold = 3
    daemon._last_cycle_exception_summary = {}
    daemon._last_fd_forensics = {}
    daemon._reasoning_loop_thread = SimpleNamespace(is_alive=lambda: True)
    daemon.watchdog_state = "observing"
    daemon._watchdog_operator_resume_required = False
    daemon._watchdog_halted_at = None
    daemon._watchdog_halt_summary = {}
    daemon._liveness_exit_requested = False
    daemon._shutdown_started = threading.Event()
    daemon.stop = lambda signum=None, frame=None: None
    for key, value in overrides.items():
        setattr(daemon, key, value)
    return daemon


class HeartbeatTruthTests(unittest.TestCase):
    def test_health_status_alive_for_fresh_reasoning_loop(self):
        import daemon.maez_daemon as md

        daemon = _daemon_stub(
            last_cycle_time="2026-06-03T00:09:55+00:00",
            _cycle_stage_started_at="2026-06-03T00:09:55+00:00",
        )

        with mock.patch.object(md.time, "time", return_value=datetime(2026, 6, 3, 0, 10, tzinfo=timezone.utc).timestamp()):
            heartbeat = md.MaezDaemon._cycle_heartbeat_health(daemon)

        self.assertFalse(heartbeat["cycle_stalled"])
        self.assertEqual(md.MaezDaemon._health_status_from_reasoning_loop(daemon, heartbeat), "alive")

    def test_health_status_stalled_for_stale_reasoning_loop(self):
        import daemon.maez_daemon as md

        daemon = _daemon_stub(
            last_cycle_time="2026-06-03T00:00:00+00:00",
            _cycle_stage_started_at="2026-06-03T00:00:00+00:00",
        )

        with mock.patch.object(md.time, "time", return_value=datetime(2026, 6, 3, 0, 11, tzinfo=timezone.utc).timestamp()):
            heartbeat = md.MaezDaemon._cycle_heartbeat_health(daemon)

        self.assertTrue(heartbeat["cycle_stalled"])
        self.assertGreaterEqual(heartbeat["stalled_after_seconds"], 300)
        self.assertEqual(md.MaezDaemon._health_status_from_reasoning_loop(daemon, heartbeat), "stalled")

    def test_health_status_stalled_when_reasoning_thread_is_dead_even_with_fresh_heartbeat(self):
        import daemon.maez_daemon as md

        daemon = _daemon_stub(
            last_cycle_time="2026-06-03T00:09:55+00:00",
            _cycle_stage_started_at="2026-06-03T00:09:55+00:00",
            _reasoning_loop_thread=SimpleNamespace(is_alive=lambda: False),
        )

        with mock.patch.object(md.time, "time", return_value=datetime(2026, 6, 3, 0, 10, tzinfo=timezone.utc).timestamp()):
            heartbeat = md.MaezDaemon._cycle_heartbeat_health(daemon)

        self.assertLess(heartbeat["cycle_age_seconds"], heartbeat["stalled_after_seconds"])
        self.assertTrue(heartbeat["cycle_stalled"])
        self.assertFalse(heartbeat["thread_alive"])
        self.assertEqual(md.MaezDaemon._health_status_from_reasoning_loop(daemon, heartbeat), "stalled")

    def test_health_status_safe_standby_beats_alive(self):
        import daemon.maez_daemon as md

        daemon = _daemon_stub(watchdog_state="safe_standby")

        self.assertEqual(
            md.MaezDaemon._health_status_from_reasoning_loop(
                daemon,
                {"cycle_stalled": False},
            ),
            "safe_standby",
        )


class CycleExceptionContractTests(unittest.TestCase):
    def test_transient_emfile_records_failure_and_keeps_loop_running(self):
        import daemon.maez_daemon as md

        daemon = _daemon_stub()

        with mock.patch("daemon.maez_daemon.fd_forensics_snapshot", return_value={"state": "captured", "fd_count": 1024}):
            should_stop = md.MaezDaemon._handle_cycle_exception(
                daemon,
                OSError(24, "Too many open files"),
            )

        self.assertFalse(should_stop)
        self.assertTrue(daemon.running)
        self.assertEqual(daemon._cycle_stage, "cycle_error_recovered")
        self.assertEqual(daemon._cycle_failure_stage, "deferred_actions")
        self.assertEqual(daemon._cycle_failure_count, 1)
        self.assertEqual(daemon._last_cycle_exception_summary["stage"], "deferred_actions")
        self.assertEqual(daemon._last_cycle_exception_summary["error_class"], "OSError")
        self.assertEqual(daemon._last_fd_forensics["fd_count"], 1024)

    def test_repeated_same_stage_failure_enters_safe_standby(self):
        import daemon.maez_daemon as md

        daemon = _daemon_stub(_cycle_failure_threshold=2)

        first = md.MaezDaemon._handle_cycle_exception(daemon, RuntimeError("db locked"))
        self.assertFalse(first)
        daemon._cycle_stage = "deferred_actions"

        second = md.MaezDaemon._handle_cycle_exception(daemon, RuntimeError("db locked"))

        self.assertTrue(second)
        self.assertFalse(daemon.running)
        self.assertEqual(daemon.watchdog_state, "safe_standby")
        self.assertTrue(daemon._watchdog_operator_resume_required)
        self.assertEqual(daemon._watchdog_halt_summary["halt_detector"], "cycle_exception_circuit_breaker")
        self.assertEqual(daemon._watchdog_halt_summary["observed_metrics"]["stage"], "deferred_actions")

    def test_completed_cycle_resets_failure_count_so_failures_are_consecutive(self):
        import daemon.maez_daemon as md

        daemon = _daemon_stub(_cycle_failure_threshold=2)

        first = md.MaezDaemon._handle_cycle_exception(daemon, RuntimeError("db locked"))
        self.assertFalse(first)
        md.MaezDaemon._reset_cycle_failure_counter(daemon)
        daemon._cycle_stage = "deferred_actions"

        second = md.MaezDaemon._handle_cycle_exception(daemon, RuntimeError("db locked"))

        self.assertFalse(second)
        self.assertTrue(daemon.running)
        self.assertEqual(daemon._cycle_failure_count, 1)


class RecoveryTripTests(unittest.TestCase):
    def test_liveness_trip_attempts_graceful_stop_then_nonzero_exit(self):
        import daemon.maez_daemon as md

        events = []
        daemon = _daemon_stub()
        daemon.stop = lambda signum=None, frame=None: events.append(("stop", signum))

        md.MaezDaemon._trip_process_for_liveness_failure(
            daemon,
            reason="reasoning_loop_stalled",
            exit_fn=lambda code: events.append(("exit", code)),
        )

        self.assertEqual(events, [("stop", None), ("exit", 75)])
        self.assertTrue(daemon._liveness_exit_requested)


class LiveWiringTests(unittest.TestCase):
    def test_supervised_loop_reenters_after_transient_stage_exception(self):
        import daemon.maez_daemon as md

        daemon = _daemon_stub()
        calls = []

        def _fake_loop():
            calls.append("loop")
            if len(calls) == 1:
                raise OSError(24, "Too many open files")
            daemon.running = False

        daemon._loop = _fake_loop

        with mock.patch("daemon.maez_daemon.fd_forensics_snapshot", return_value={"state": "captured"}):
            md.MaezDaemon._run_reasoning_loop_supervised(daemon)

        self.assertEqual(calls, ["loop", "loop"])
        self.assertEqual(daemon._cycle_failure_count, 1)
        self.assertEqual(daemon._cycle_stage, "cycle_error_recovered")

    def test_start_uses_supervised_loop_and_sentinel(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text(encoding="utf-8")
        start = src.index("def start(self):")
        stop = src.index("def _start_surface_v2", start)
        block = src[start:stop]

        self.assertIn("target=self._run_reasoning_loop_supervised", block)
        self.assertIn("self._reasoning_loop_thread = loop_thread", block)
        self.assertIn("self._start_cognition_liveness_sentinel()", block)

    def test_health_route_status_is_not_literal_alive(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text(encoding="utf-8")
        start = src.index("def _run_health_server(self):")
        stop_match = re.search(r"^    def \w+\(", src[start + 1 :], re.MULTILINE)
        stop = start + 1 + stop_match.start() if stop_match else len(src)
        block = src[start:stop]

        self.assertIn('"status": self._health_status_from_reasoning_loop(_reasoning_loop)', block)
        self.assertNotIn('"status": "alive"', block)

    def test_loop_resets_failure_counter_after_completed_cycle_before_sleep(self):
        src = (_REPO / "daemon" / "maez_daemon.py").read_text(encoding="utf-8")
        start = src.index("def _loop(self):")
        stop = src.index("def start(self):", start)
        block = src[start:stop]

        reset_at = block.index("self._reset_cycle_failure_counter()")
        sleep_at = block.index('self._mark_cycle_stage("cycle_sleep")')
        self.assertLess(reset_at, sleep_at)


class FdForensicsTests(unittest.TestCase):
    def test_fd_forensics_snapshot_is_content_free(self):
        from core.health.fd_forensics import fd_forensics_snapshot

        snapshot = fd_forensics_snapshot(pid=os.getpid())

        self.assertIn(snapshot["state"], {"captured", "unavailable"})
        self.assertIn("fd_count", snapshot)
        self.assertIn("by_type", snapshot)
        self.assertIn("thread_count", snapshot)
        self.assertNotIn("targets", snapshot)
        encoded = repr(snapshot)
        self.assertNotIn("/home/rohit", encoded)
        self.assertNotIn("maez.log", encoded)


if __name__ == "__main__":
    unittest.main()
