# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Source-awareness async refresh — Commit 4 of the 2026-04-23 repair pass.

Invariant guarded here:

    Self-model staleness is detectable by Maez (map_status()),
    refresh runs asynchronously (never blocks a daemon cycle),
    and accessors keep serving the current map during refresh.

Before this commit:
    - memory/source_awareness.json was last built 2026-04-08 and
      claimed total_files=60. The repo now has 516 tracked files.
      Any self-edit / evolution reasoning that used this map was
      operating on a wrong model of the code.
    - There was no cheap staleness check; a full rebuild took
      several seconds of AST parsing across every .py file, too
      slow to do at daemon startup without risking the cycle-retry
      backoff timing.
"""
from __future__ import annotations

import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _fake_map(built_at_iso: str, total_files: int = 60,
              schema_version: str = "1.0") -> dict:
    """Minimal map dict for staleness tests — body is not inspected
    by the functions under test here."""
    return {
        "schema_version": schema_version,
        "built_at": built_at_iso,
        "maez_root": "/tmp/test",
        "total_files": total_files,
        "indexed_files": total_files,
        "parsed_files": total_files,
        "skipped_by_design": 0,
        "parse_errors": 0,
        "files": {},
    }


class MapStatusStaleness(unittest.TestCase):
    """map_status() / is_stale() must flag stale maps cheaply."""

    def _with_map(self, map_dict: dict):
        """Context-manager shim — patches _read_map_raw so tests don't
        have to touch the real on-disk file."""
        from core.memory import source_awareness as sa
        return patch.object(sa, "_read_map_raw", return_value=map_dict)

    def test_missing_map_is_stale(self):
        from core.memory.source_awareness import map_status
        with patch("core.memory.source_awareness._read_map_raw",
                   return_value=None):
            st = map_status()
        self.assertFalse(st["present"])
        self.assertTrue(st["stale"])
        self.assertEqual(st["total_files"], 0)

    def test_fresh_map_is_not_stale(self):
        from core.memory.source_awareness import map_status
        fresh_ts = datetime.now(timezone.utc).isoformat()
        with self._with_map(_fake_map(fresh_ts)):
            st = map_status()
        self.assertTrue(st["present"])
        self.assertFalse(st["stale"])

    def test_old_map_is_stale(self):
        """A map >7 days old must be flagged stale."""
        from core.memory.source_awareness import map_status
        stale_ts = (
            datetime.now(timezone.utc) - timedelta(days=10)
        ).isoformat()
        with self._with_map(_fake_map(stale_ts)):
            st = map_status()
        self.assertTrue(st["stale"])
        self.assertGreater(st["age_days"], 7.0)

    def test_schema_mismatch_is_stale(self):
        """An incompatible schema version must be flagged stale."""
        from core.memory.source_awareness import map_status
        fresh_ts = datetime.now(timezone.utc).isoformat()
        with self._with_map(_fake_map(fresh_ts, schema_version="0.9")):
            st = map_status()
        self.assertTrue(st["stale"])


class AsyncRefreshBehavior(unittest.TestCase):
    """trigger_async_refresh runs off the main thread and doesn't double-fire."""

    def setUp(self):
        # Reset module-level flag so tests don't leak state.
        from core.memory import source_awareness as sa
        with sa._refresh_lock:
            sa._refresh_running = False

    def tearDown(self):
        from core.memory import source_awareness as sa
        with sa._refresh_lock:
            sa._refresh_running = False

    def test_trigger_returns_true_once_then_false(self):
        """First call starts a thread, second call (while running)
        does NOT double-fire — returns False so the caller knows
        a refresh is already in flight."""
        from core.memory import source_awareness as sa

        with patch.object(sa, "refresh_map",
                          side_effect=lambda: time.sleep(0.3) or {
                              "updated": 1, "unchanged": 0, "errors": 0,
                          }):
            started = sa.trigger_async_refresh()
            self.assertTrue(started)
            # Thread is still running — a second call must bail.
            second = sa.trigger_async_refresh()
            self.assertFalse(second)
            # Wait for the thread to finish so tearDown sees a
            # clean state.
            sa._refresh_thread.join(timeout=2.0)
        # After completion, the flag must be cleared.
        self.assertFalse(sa._refresh_running)

    def test_accessor_triggers_refresh_when_stale(self):
        """get_file() must kick off an async refresh if the map is
        stale and no refresh is running. Accessor still returns the
        current map (or None if absent) WITHOUT blocking."""
        from core.memory import source_awareness as sa
        with patch.object(sa, "is_stale", return_value=True), \
             patch.object(sa, "trigger_async_refresh",
                          return_value=True) as m_trig:
            # Using a missing map shortcut so the accessor returns
            # None — we're asserting the trigger hook fires, not
            # the accessor body.
            with patch.object(type(sa.MAP_PATH), "exists",
                              lambda self: False):
                sa.get_file("daemon/maez_daemon.py")
        m_trig.assert_called_once()

    def test_accessor_does_not_trigger_when_fresh(self):
        from core.memory import source_awareness as sa
        with patch.object(sa, "is_stale", return_value=False), \
             patch.object(sa, "trigger_async_refresh",
                          return_value=True) as m_trig:
            with patch.object(type(sa.MAP_PATH), "exists",
                              lambda self: False):
                sa.get_file("daemon/maez_daemon.py")
        m_trig.assert_not_called()


if __name__ == "__main__":
    unittest.main()
