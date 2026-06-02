# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the Tier-2 daemon-runtime cluster from
the 2026-05-04 15-agent code audit.

Six items, all narrow runtime-hygiene fixes:

T2.1 — PID-file false-positive on SIGKILL
  Audit: a stale PID file from a SIGKILLed parent makes the daemon
  appear to be running. _write_pid must liveness-check (os.kill 0)
  any existing PID, log a WARNING for the dead process, and overwrite.

T2.2 — paths.ensure_dirs() silent OSError swallow
  Audit: directory-creation failures pass under `except OSError: pass`,
  so callers see opaque "file not found" errors elsewhere. Must log
  WARNING with the path + the exception so the failure is visible.

T2.3 — capability-integration plan poller race on list_open() →
       per-row upsert(). Two pollers (or duplicate threads) can both
       observe the same queue_id without a plan and both insert.
       The window is closed by claiming the row in a single
       BEGIN IMMEDIATE transaction (only one poller wins).

T2.4 — same-file follow-up: list_open() → upsert() wasted work.
       Same fix shape; the regression guard is one concurrency test.

T2.5 — superseded by Camera Presence v1: camera arrival/departure state
       must not drive dream-idle timing at all.

T2.6 — capability-planning loop silent 1-hour wait on exception.
       Must (a) log the exception type+message at WARNING and
       (b) back off bounded (60s → 120s → 240s → 1h cap) instead
       of always waiting 3600s before retry.
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── T2.1 — PID-file liveness check ───────────────────────────────────


class T2_1_PidFileLivenessCheck(unittest.TestCase):
    """REGRESSION GUARDS for T2.1: a stale PID file from a SIGKILLed
    daemon must not block the next start. The daemon must liveness-
    check the existing PID via os.kill(pid, 0) and overwrite when
    the prior process is gone, logging at WARNING."""

    def test_source_pin_write_pid_calls_os_kill_signal_zero(self):
        """Source-pin: _write_pid must reference os.kill(..., 0) so
        a future refactor that drops the liveness check is caught
        here rather than silently regressing."""
        src = (REPO / "daemon" / "maez_daemon.py").read_text()
        # Find the _write_pid function and check its body region.
        idx = src.find("def _write_pid(")
        self.assertGreater(idx, -1, "_write_pid must exist")
        # Take the next ~2000 chars as the function body region.
        region = src[idx:idx + 2000]
        self.assertIn(
            "os.kill(",
            region,
            "T2.1 regression: _write_pid no longer liveness-checks "
            "the prior PID via os.kill",
        )
        self.assertIn(
            ", 0)",
            region,
            "T2.1 regression: _write_pid no longer uses signal 0 "
            "(liveness check) — it must, to avoid killing live PIDs",
        )

    def test_stale_pid_overwrite_logs_warning(self):
        """Behaviour: write a stale PID (one guaranteed dead), call
        the liveness-check helper, and confirm WARNING is logged
        and the file is overwritten with the live PID."""
        from daemon import maez_daemon as md

        # Use a temp PID file so we don't disturb a running daemon.
        with tempfile.TemporaryDirectory() as tmp:
            stale_pid_path = Path(tmp) / "maez.pid"
            # PID 1 is init; we use a guaranteed-dead PID instead.
            # On Linux, /proc lookup confirms; for the test we
            # synthesize a dead PID by spawning + reaping a child.
            import subprocess
            proc = subprocess.Popen(["true"])
            proc.wait()
            dead_pid = proc.pid
            stale_pid_path.write_text(str(dead_pid))

            with mock.patch.object(md, "PID_FILE", stale_pid_path):
                with self.assertLogs("maez", level="WARNING") as cm:
                    inst = md.MaezDaemon.__new__(md.MaezDaemon)
                    inst._write_pid()

            self.assertTrue(
                any("stale" in m.lower() or "dead" in m.lower()
                    for m in cm.output),
                f"WARNING must mention stale/dead pid; got {cm.output}",
            )
            # File must now contain our live PID (the test process).
            self.assertEqual(
                stale_pid_path.read_text().strip(),
                str(os.getpid()),
            )


# ── T2.2 — paths.ensure_dirs OSError visibility ──────────────────────


class T2_2_EnsureDirsLogsFailure(unittest.TestCase):
    """REGRESSION GUARDS for T2.2: ensure_dirs() must log a WARNING
    on directory-creation failure rather than swallowing the OSError.
    """

    def test_source_pin_ensure_dirs_logs_on_failure(self):
        src = (REPO / "core" / "infra" / "paths.py").read_text()
        idx = src.find("def ensure_dirs(")
        self.assertGreater(idx, -1)
        region = src[idx:idx + 2000]
        # Must reference a logger and warning-level call inside
        # the except OSError branch.
        self.assertIn(
            "logger",
            region,
            "T2.2 regression: ensure_dirs no longer references a logger",
        )
        self.assertIn(
            "warning",
            region,
            "T2.2 regression: ensure_dirs no longer logs at warning "
            "level on OSError",
        )

    def test_runtime_warning_logged_on_mkdir_failure(self):
        # Force ensure_dirs to re-run by clearing the cache.
        from core.infra import paths as P
        P._ENSURED = False
        # Patch one of the dir helpers to point at an unwritable
        # location so mkdir(parents=True, exist_ok=True) raises.
        bad = Path("/proc/1/sentinel-cannot-create-here")
        with mock.patch.object(P, "snapshots_dir", lambda: bad):
            with self.assertLogs("maez", level="WARNING") as cm:
                try:
                    P.ensure_dirs()
                except OSError:
                    # Either re-raise or swallow-with-log is acceptable
                    # per audit; but the WARNING must fire either way.
                    pass
        self.assertTrue(
            any("ensure_dirs" in m or "snapshots" in m
                or "/proc" in m for m in cm.output),
            f"WARNING must surface the failed path; got {cm.output}",
        )
        # Reset so other tests don't inherit a partially-ensured state.
        P._ENSURED = False


# ── T2.3 / T2.4 — capability_integration_plans poll_and_plan race ───


class T2_3_PollAndPlanConcurrentRace(unittest.TestCase):
    """REGRESSION GUARDS for T2.3 + T2.4: two concurrent poll_and_plan
    invocations on the same store must not double-process a queue_id.
    Idempotency at the upsert layer prevents duplicate rows, but the
    audit asks for a transactional claim so the second worker's
    plan_next() call (which is the expensive part) is skipped."""

    def _fake_queue(self, rows):
        class FakeQ:
            def list_open(self_inner):
                return list(rows)
        return FakeQ()

    def test_concurrent_pollers_do_not_double_call_plan_next(self):
        from core.infra import capability_integration_plans as cip
        with tempfile.TemporaryDirectory() as tmp:
            store = cip.IntegrationPlanStore(
                db_path=Path(tmp) / "plans.db",
            )
            row = {"id": "acq-test1", "status": "queued"}
            queue = self._fake_queue([row])

            call_counter = {"n": 0}
            call_lock = threading.Lock()

            class _Plan:
                capability_id = "cap-x"
                needs_field_search = False

                def __init__(self):
                    self.__dict__["capability_id"] = "cap-x"
                    self.__dict__["needs_field_search"] = False

            def slow_plan_next(_q, *, queue_id, manual_root=None):
                # Simulate a slow planner so concurrent pollers
                # interleave inside the list_open → upsert window.
                with call_lock:
                    call_counter["n"] += 1
                import time as _t
                _t.sleep(0.05)
                return _Plan()

            with mock.patch.object(cip, "plan_next", slow_plan_next):
                results = []

                def runner():
                    try:
                        out = cip.poll_and_plan(
                            queue=queue, plans=store,
                        )
                        results.append(out)
                    except Exception as e:  # pragma: no cover
                        results.append(e)

                t1 = threading.Thread(target=runner)
                t2 = threading.Thread(target=runner)
                t1.start(); t2.start()
                t1.join(); t2.join()

            # Exactly one planner call for the single queue row.
            # Without the BEGIN IMMEDIATE claim both threads call
            # plan_next() because both observed
            # get_by_queue_id is None.
            self.assertEqual(
                call_counter["n"], 1,
                f"plan_next must be called once per queue_id "
                f"under concurrency; got {call_counter['n']}",
            )
            # And exactly one row in the store.
            rows = store.list_all()
            self.assertEqual(len(rows), 1)


# ── T2.5 — camera presence no longer drives arrival state ────────────


class T2_5_DepartureClearedOnArrival(unittest.TestCase):
    """REGRESSION GUARDS for T2.5 after Camera Presence v1.

    The old daemon path used camera arrival/departure transitions as behavioral
    state. The sleep-consolidation wiring keeps that removed: dream scheduling
    goes through an explicit activity-primary idle helper, not arrival/leave
    state or prompt/signature context.
    """

    def test_camera_presence_does_not_drive_dream_arrival_state(self):
        src = (REPO / "daemon" / "maez_daemon.py").read_text()
        loop_idx = src.find("def _loop(")
        self.assertGreater(loop_idx, -1)
        next_def = src.find("\n    def ", loop_idx + 20)
        loop_body = src[loop_idx : next_def if next_def != -1 else len(src)]
        self.assertNotIn("just_arrived", loop_body)
        self.assertNotIn("just_left", loop_body)
        self.assertNotIn("_last_departure_time", loop_body)
        self.assertNotIn("self.dream.is_idle(None, 0.0)", loop_body)
        self.assertIn("_dream_idle_gate_open(self, now=_now)", loop_body)


# ── T2.6 — capability-planning loop bounded backoff + exception log ─


class T2_6_PlanningLoopBackoffOnException(unittest.TestCase):
    """REGRESSION GUARDS for T2.6: on exception, the capability-
    planning loop must (a) log the exception class+message at
    WARNING and (b) use bounded exponential backoff (60→120→240,
    capped at 3600) instead of always sleeping 3600s."""

    def test_source_pin_loop_uses_backoff_and_logs_exc_class(self):
        src = (REPO / "daemon" / "maez_daemon.py").read_text()
        idx = src.find("def _capability_planning_loop(")
        self.assertGreater(idx, -1)
        region = src[idx:idx + 4000]
        # Backoff sentinel: the seed (60) and the doubling pattern
        # must both be visible in the loop body.
        self.assertIn(
            "60.0",
            region,
            "T2.6 regression: bounded backoff seed (60s) missing",
        )
        # Exception class must be logged — %r or type(e).__name__
        # or e.__class__.__name__.
        self.assertTrue(
            ("type(" in region and "__name__" in region)
            or "%r" in region
            or "exc_info=True" in region,
            "T2.6 regression: exception class is no longer logged "
            "in the planning-loop except branch",
        )
        # And we must STILL have a 3600s cap, not just an unbounded
        # doubling.
        self.assertIn(
            "3600",
            region,
            "T2.6 regression: 1-hour cap on backoff missing",
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    unittest.main()
