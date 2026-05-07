# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for slice 1.4 wake-word reader survivability wiring.

The pw-reader primitive in skills/wake_word.py has unit tests in
tests/test_wake_word_pw_reader.py. These tests pin the PRODUCTION
wiring so a future refactor that bypasses the bounded reader
(or removes the cleanup ladder from stop()) fails loudly here
instead of silently regressing the D-state hang fix.

Specifically guarded:
  - select is imported (the polling primitive).
  - _run_pw_reader exists at module scope and is targeted by the
    spawned reader thread (NOT the original inline _reader closure).
  - Module-level _pw_proc and _pw_reader_thread globals exist —
    these let stop() reach the proc + thread directly without
    depending on _audio_loop_inner's finally block running.
  - stop() calls proc.terminate(), reader.join(timeout=...),
    proc.stdout.close(), proc.kill(), and a final reader.join.
  - MAEZ_PW_READER_WATCHDOG_S is parsed via _pw_reader_watchdog_s
    (safe-fallback posture from slice 1.2/1.3) — typo must not
    crash daemon import.

Style mirrors test_t1_9_shutdown_hygiene_2026_05_05.py and
test_dream_worker_wiring_2026_05_07.py — read the source as text
and assert specific substrings.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class WakeWordReaderWiringTests(unittest.TestCase):
    """Pin the slice 1.4 production wiring. If any of these fail, the
    pw-reader D-state fix has regressed."""

    @classmethod
    def setUpClass(cls):
        cls.src = (REPO / "skills" / "wake_word.py").read_text()

    # ── primitive seam ────────────────────────────────────────────────

    def test_select_is_imported(self):
        # The select stdlib module is the polling primitive that lets
        # stop_event interrupt a stuck pipe read.
        self.assertIn(
            "import select", self.src,
            "wake_word must import select (the stop-event-interruptible "
            "polling primitive); without it, the D-state hang vector "
            "remains open",
        )

    def test_run_pw_reader_helper_exists(self):
        self.assertIn(
            "def _run_pw_reader(", self.src,
            "wake_word must expose a module-level _run_pw_reader "
            "helper that the spawned reader thread targets",
        )

    def test_reader_thread_targets_run_pw_reader(self):
        # The spawn site must use the helper as the thread target,
        # NOT the original inline closure shape.
        self.assertIn(
            "target=_run_pw_reader", self.src,
            "the reader thread must target _run_pw_reader, not the "
            "original inline _reader closure (which had no select "
            "polling and would re-introduce the D-state hang)",
        )

    def test_no_inline_reader_closure_remains(self):
        # The original inline closure shape should be gone.
        self.assertNotIn(
            "def _reader():", self.src,
            "the original inline `def _reader():` closure must be "
            "removed; the bounded module-level helper replaces it",
        )

    # ── module-level state for direct cleanup ─────────────────────────

    def test_module_level_pw_proc_global_exists(self):
        self.assertIn(
            "_pw_proc:", self.src,
            "wake_word must declare _pw_proc at module scope so stop() "
            "can reach the pw-record subprocess directly without "
            "depending on _audio_loop_inner's finally block running",
        )

    def test_module_level_pw_reader_thread_global_exists(self):
        self.assertIn(
            "_pw_reader_thread:", self.src,
            "wake_word must declare _pw_reader_thread at module scope "
            "so stop() can bounded-join the reader directly",
        )

    def test_audio_loop_inner_publishes_globals(self):
        # The spawn site must publish the proc + thread to module globals.
        self.assertIn(
            "_pw_proc = proc", self.src,
            "_audio_loop_inner must publish proc to the module-level "
            "_pw_proc global so stop() can reach it",
        )
        self.assertIn(
            "_pw_reader_thread = reader_thread", self.src,
            "_audio_loop_inner must publish the reader thread to "
            "_pw_reader_thread global",
        )

    # ── stop() cleanup ladder ─────────────────────────────────────────

    def test_stop_calls_proc_terminate(self):
        self.assertIn(
            "proc.terminate()", self.src,
            "stop() must call proc.terminate() to send SIGTERM to "
            "pw-record",
        )

    def test_stop_calls_bounded_reader_join(self):
        # Look for reader.join with a timeout argument.
        self.assertIn(
            "reader.join(timeout=", self.src,
            "stop() must bounded-join the reader thread with a "
            "timeout (unbounded join would re-introduce shutdown hang)",
        )

    def test_stop_closes_stdout_in_escalation(self):
        # When terminate doesn't free the read, explicitly close stdout
        # to force pending reads to error out (Critical #3).
        self.assertIn(
            "proc.stdout.close()", self.src,
            "stop() must explicitly close proc.stdout in the "
            "escalation path so a stuck read errors out instead of "
            "hanging on a SIGTERM-resistant proc",
        )

    def test_stop_calls_proc_kill_in_escalation(self):
        self.assertIn(
            "proc.kill()", self.src,
            "stop() must escalate to proc.kill() if proc.terminate() "
            "didn't free the reader within the bounded join window",
        )

    def test_stop_resets_module_state(self):
        # After cleanup, the globals must be cleared so the next start()
        # gets a clean slate.
        self.assertIn(
            "_pw_proc = None", self.src,
            "stop() must reset _pw_proc to None for clean re-start",
        )
        self.assertIn(
            "_pw_reader_thread = None", self.src,
            "stop() must reset _pw_reader_thread to None for clean "
            "re-start",
        )

    # ── safe-fallback env parsing ─────────────────────────────────────

    def test_watchdog_env_uses_safe_fallback_parser(self):
        # Match the slice 1.2/1.3 posture: a typo on a survivability
        # knob must not crash module import.
        self.assertIn(
            "_pw_reader_watchdog_s", self.src,
            "wake_word must use a safe-fallback parser for "
            "MAEZ_PW_READER_WATCHDOG_S (matching the slice 1.2/1.3 "
            "env-parse posture); a bare float() would crash daemon "
            "import on a typo",
        )
        self.assertIn(
            'os.environ.get("MAEZ_PW_READER_WATCHDOG_S")', self.src,
            "the parser must read the MAEZ_PW_READER_WATCHDOG_S env var",
        )


class StopCleanupLadderBehavioralTests(unittest.TestCase):
    """Behavioral test of wake_word.stop() escalation ladder.

    Source-level guards confirm the strings exist; this test confirms
    the order of operations actually runs when the reader thread
    persists past terminate(). This is the production cleanup path
    for the 2026-05-07 D-state incident — worth a behavioral test.
    """

    def setUp(self):
        # Snapshot module state so we can restore it.
        from skills import wake_word as ww
        self.ww = ww
        self._snap = (
            ww._thread,
            ww._stop_event,
            ww._pw_proc,
            ww._pw_reader_thread,
        )

    def tearDown(self):
        ww = self.ww
        ww._thread, ww._stop_event, ww._pw_proc, ww._pw_reader_thread = (
            self._snap
        )

    def test_stop_escalation_runs_when_reader_persists_past_terminate(self):
        """When reader stays alive after proc.terminate(), stop() must
        escalate: close stdout → kill → final join. Verify call order
        and that stdout.close() runs BEFORE proc.kill()."""
        from unittest.mock import MagicMock, call
        ww = self.ww

        proc = MagicMock()
        # Reader stays alive for first is_alive check (after terminate)
        # then dies after proc.kill() — observed by alternating Trues
        # then False. Mock counts: terminate→is_alive(True)→close→kill→
        # is_alive(False).
        # We simulate "still alive after terminate join" by returning
        # True for the FIRST is_alive check, False after.
        reader = MagicMock()
        reader.is_alive = MagicMock(side_effect=[True, True, False])
        reader.join = MagicMock()

        # Audio loop thread mock (so the final _thread.join doesn't
        # do anything interesting).
        audio_loop = MagicMock()
        audio_loop.join = MagicMock()

        # Wire module state.
        ww._pw_proc = proc
        ww._pw_reader_thread = reader
        ww._stop_event = MagicMock()
        ww._thread = audio_loop

        # Call stop and verify escalation order.
        ww.stop()

        # Assertions:
        # 1. terminate called.
        proc.terminate.assert_called_once()
        # 2. First reader.join used a 2.0s timeout.
        first_join = reader.join.call_args_list[0]
        self.assertEqual(first_join, call(timeout=2.0))
        # 3. Because is_alive returned True after first join,
        #    escalation ran: stdout.close() and kill() both called.
        proc.stdout.close.assert_called_once()
        proc.kill.assert_called_once()
        # 4. stdout.close() was called BEFORE proc.kill() (Critical #3:
        #    closing stdout forces pending read to error out, so kill
        #    has a higher chance of completing the cleanup).
        # Use mock_calls on the parent which preserves insertion order
        # across all child attributes/methods.
        method_names = [c[0] for c in proc.mock_calls]
        self.assertIn("stdout.close", method_names)
        self.assertIn("kill", method_names)
        self.assertLess(
            method_names.index("stdout.close"),
            method_names.index("kill"),
            f"stdout.close() must precede kill() in escalation; "
            f"observed call order: {method_names}",
        )
        # 5. Second join also bounded.
        self.assertEqual(reader.join.call_count, 2)
        second_join = reader.join.call_args_list[1]
        self.assertEqual(second_join, call(timeout=2.0))
        # 6. Module state reset so a future start() is clean.
        self.assertIsNone(ww._pw_proc)
        self.assertIsNone(ww._pw_reader_thread)

    def test_stop_skips_escalation_when_reader_exits_on_terminate(self):
        """If reader exits cleanly after proc.terminate(), the
        escalation path (stdout.close + kill) must NOT run. Avoids
        unnecessary SIGKILLs on graceful shutdowns."""
        from unittest.mock import MagicMock
        ww = self.ww

        proc = MagicMock()
        reader = MagicMock()
        # Reader is alive at the initial check, but exits during the
        # first join — is_alive() returns False after.
        reader.is_alive = MagicMock(side_effect=[True, False])
        reader.join = MagicMock()

        ww._pw_proc = proc
        ww._pw_reader_thread = reader
        ww._stop_event = MagicMock()
        ww._thread = MagicMock()

        ww.stop()

        proc.terminate.assert_called_once()
        reader.join.assert_called_once()
        # Escalation must NOT have run.
        proc.stdout.close.assert_not_called()
        proc.kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
