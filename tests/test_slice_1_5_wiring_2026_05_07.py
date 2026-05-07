# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for slice 1.5 production wiring.

The behavioral tests in test_telegram_adapter_sweep.py and
test_platform_base_session_sweep.py call sweep methods directly with
explicit `now=` injection. They verify the sweepers ARE correct.

These tests verify the sweepers are actually WIRED into production —
that TelegramAdapter.connect() spawns the base-class session sweep,
and that disconnect() / stop() cancels it. Without this guard, the
slice could ship with passing behavioral tests and a silent
production regression where the sweep never actually runs in the
deployed daemon.

Style mirrors test_dream_worker_wiring_2026_05_07.py and
test_wake_word_wiring_2026_05_07.py.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class Slice15WiringTests(unittest.TestCase):
    """Pin the slice 1.5 production wiring."""

    @classmethod
    def setUpClass(cls):
        cls.tg_src = (
            REPO / "skills" / "surface" / "telegram_adapter.py"
        ).read_text()
        cls.pb_src = (
            REPO / "skills" / "surface" / "platform_base.py"
        ).read_text()

    # ── telegram adapter sweep is constructed at init ──────────────────

    def test_telegram_init_creates_batch_last_touched(self):
        self.assertIn(
            "self._batch_last_touched", self.tg_src,
            "TelegramAdapter must own a _batch_last_touched dict to "
            "track per-key timestamps for sweep eviction",
        )

    def test_telegram_init_creates_sweep_task(self):
        # Either asyncio.create_task or asyncio.ensure_future — agent's
        # impl uses create_task with a running-loop probe. Either form
        # should result in self._batch_sweep_task being assigned.
        self.assertIn(
            "self._batch_sweep_task", self.tg_src,
            "TelegramAdapter must own a _batch_sweep_task attribute",
        )

    # ── env vars use safe-fallback parser ──────────────────────────────

    def test_telegram_env_safe_fallback(self):
        self.assertIn(
            "MAEZ_TELEGRAM_SWEEP_INTERVAL_S", self.tg_src,
            "telegram adapter must read the sweep interval env var",
        )
        self.assertIn(
            "MAEZ_TELEGRAM_BATCH_TTL_S", self.tg_src,
            "telegram adapter must read the batch TTL env var",
        )

    def test_platform_base_env_safe_fallback(self):
        self.assertIn(
            "MAEZ_SESSION_SWEEP_INTERVAL_S", self.pb_src,
            "platform_base must read the session sweep interval env var",
        )
        self.assertIn(
            "MAEZ_SESSION_TTL_S", self.pb_src,
            "platform_base must read the session TTL env var",
        )

    # ── PRODUCTION WIRING: connect() spawns base sweep ─────────────────

    def test_telegram_connect_calls_super_start(self):
        """The slice's whole point: in production, connect() must spawn
        the BasePlatformAdapter session-sweep. Behavioral tests pass
        without this because they call start() directly. This guard
        catches a silent production regression.
        """
        self.assertIn(
            "await super().start()", self.tg_src,
            "TelegramAdapter.connect() must call await super().start() "
            "so the BasePlatformAdapter session-sweep task is actually "
            "spawned in production. Without this, the slice's idle "
            "session eviction never runs on a real daemon.",
        )

    def test_telegram_stop_calls_super_stop(self):
        """Symmetric to test_telegram_connect_calls_super_start. The
        stop() method must propagate to the base class so
        _session_sweep_task is cancelled in lockstep with
        _batch_sweep_task during shutdown.
        """
        self.assertIn(
            "await super().stop()", self.tg_src,
            "TelegramAdapter.stop() must call await super().stop() so "
            "the BasePlatformAdapter session-sweep task is cancelled "
            "during shutdown. Without this, the orphaned sweep task "
            "would race teardown.",
        )

    # ── disconnect chains to stop ──────────────────────────────────────

    def test_telegram_disconnect_calls_self_stop(self):
        # Both the sweep cancel and super().stop() chain depend on
        # disconnect() routing through self.stop() first.
        self.assertIn(
            "await self.stop()", self.tg_src,
            "TelegramAdapter.disconnect() must call await self.stop() "
            "as its first step so the slice 1.5 sweep teardown chain "
            "fires before the existing batch-task cleanup",
        )

    # ── platform_base lifecycle methods exist ──────────────────────────

    def test_platform_base_has_start_method(self):
        self.assertIn(
            "async def start(", self.pb_src,
            "BasePlatformAdapter must expose async def start() that "
            "spawns _session_sweep_task",
        )

    def test_platform_base_has_stop_method(self):
        self.assertIn(
            "async def stop(", self.pb_src,
            "BasePlatformAdapter must expose async def stop() that "
            "cancels _session_sweep_task",
        )

    def test_platform_base_has_sweep_method(self):
        self.assertIn(
            "_sweep_idle_sessions", self.pb_src,
            "BasePlatformAdapter must expose _sweep_idle_sessions",
        )

    # ── eviction criteria correctness ──────────────────────────────────

    def test_session_sweep_checks_event_set(self):
        """CRITICAL #1 from adversarial review: a wedged-but-stale
        session must NOT be evicted just because the timestamp is
        old. The interrupt event being set is one of three required
        gates. Production code must check it.
        """
        self.assertIn(
            ".is_set()", self.pb_src,
            "session sweep must check event.is_set() before evicting "
            "(see adversarial review CRITICAL #1)",
        )

    def test_session_sweep_checks_background_tasks(self):
        """CRITICAL #1 from adversarial review: a session with a live
        background task must NOT be evicted. Production code must
        check `_background_tasks` membership for the session_key.
        """
        self.assertIn(
            "_background_tasks", self.pb_src,
            "session sweep must check _background_tasks for live "
            "tasks before evicting (see adversarial review CRITICAL #1)",
        )

    def test_session_sweep_uses_session_key_correlation(self):
        """CRITICAL #4 from adversarial review: tasks must be tagged
        with session_key so the sweep can correlate task → session.
        Look for the setattr / direct-attr-set pattern.
        """
        # Either `task.session_key = ` or `setattr(task, "session_key"`
        self.assertTrue(
            'task.session_key' in self.pb_src
            or 'setattr(task, "session_key"' in self.pb_src
            or "setattr(task, 'session_key'" in self.pb_src,
            "platform_base must tag spawned tasks with session_key "
            "for sweep correlation (see adversarial review CRITICAL #4). "
            "Expected `task.session_key = ...` or "
            "`setattr(task, 'session_key', ...)` somewhere in the file.",
        )


if __name__ == "__main__":
    unittest.main()
