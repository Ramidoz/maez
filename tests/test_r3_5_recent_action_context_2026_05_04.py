# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for R3.5 — cycle narration consults preceding
card outcomes.

The 2026-05-04 symphony audit (S4 BLOCKER F7, top-10 #8) found
that Cycle 35 narrated "system idle, holding quiet" 12 seconds
after the 14:39 wmctrl card failed three tools. The cycle's
perception path read system metrics + ambient context but did NOT
read pending_cards.execution_output for the immediately-preceding
card. R3 makes the action engine record failures honestly going
forward; R3.5 makes the cycle's narration consult those records
before claiming idle.

Contract enforced by these tests:
- core/decision/recent_action_context.recent_failures(window_seconds)
  returns a formatted prompt block listing cards that failed
  within the window OR whose execution_output matches a soft-
  failure pattern (so legacy `execution_success=1` lying rows
  pre-R3-deploy are also surfaced).
- Empty string when no failures in window.
- Block is concise (< 500 chars typical) so it fits the cycle
  prompt budget.
- Soft-failure detection re-runs against execution_output so
  legacy rows with execution_success=1 but failure markers in
  stdout are correctly classified as failures.
- daemon._reason() injects the block when non-empty (source-pin
  + behavioural for the assemble path).
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


_PENDING_CARDS_SCHEMA = """
CREATE TABLE pending_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT,
    created_at REAL,
    updated_at REAL,
    status TEXT,
    action TEXT,
    params_json TEXT,
    reason TEXT,
    executed_at REAL,
    execution_success INTEGER,
    execution_output TEXT,
    execution_error TEXT,
    plain_english TEXT
)
"""


def _make_test_db(rows: list[dict]) -> Path:
    """Create a throwaway pending_cards.db with given rows."""
    fd, path = tempfile.mkstemp(suffix=".db")
    Path(path).unlink()  # sqlite3 will create it
    db = sqlite3.connect(path)
    db.execute(_PENDING_CARDS_SCHEMA)
    for r in rows:
        db.execute(
            "INSERT INTO pending_cards "
            "(request_id, created_at, updated_at, status, action, "
            " params_json, reason, executed_at, execution_success, "
            " execution_output, execution_error, plain_english) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r.get("request_id", "rid"),
                r.get("created_at", time.time()),
                r.get("updated_at", time.time()),
                r.get("status", "done"),
                r.get("action", "run_shell"),
                r.get("params_json", "{}"),
                r.get("reason", "test"),
                r.get("executed_at"),
                r.get("execution_success"),
                r.get("execution_output"),
                r.get("execution_error"),
                r.get("plain_english", ""),
            ),
        )
    db.commit()
    db.close()
    return Path(path)


class R3_5_RecentFailuresShape(unittest.TestCase):
    """REGRESSION GUARD: recent_failures() returns a string block
    for cycle prompt consumption with documented shape."""

    def test_empty_db_returns_empty_string(self):
        from core.decision import recent_action_context as rac
        db_path = _make_test_db([])
        try:
            result = rac.recent_failures(
                window_seconds=120.0, _db_path_override=db_path,
            )
            self.assertEqual(result, "")
        finally:
            db_path.unlink()

    def test_recent_failed_card_appears_in_block(self):
        """A card with execution_success=0 inside the window must
        show up in the formatted block."""
        from core.decision import recent_action_context as rac
        now = time.time()
        db_path = _make_test_db([{
            "request_id": "rid_failed",
            "executed_at": now - 30.0,
            "execution_success": 0,
            "execution_output": "permission denied",
            "execution_error": "Permission denied",
            "params_json": '{"cmd": "cat /var/log/private"}',
            "plain_english": "Read private log",
        }])
        try:
            result = rac.recent_failures(
                window_seconds=120.0, _db_path_override=db_path,
            )
            # Block truncates request_id to first 8 chars in the
            # rendered line — production IDs are hex hashes where 8
            # chars is enough for cross-reference.
            self.assertIn("rid_fail", result)
            self.assertIn("FAILED", result)
            self.assertNotEqual(result, "")
        finally:
            db_path.unlink()

    def test_old_failure_outside_window_is_excluded(self):
        from core.decision import recent_action_context as rac
        now = time.time()
        db_path = _make_test_db([{
            "request_id": "rid_old",
            "executed_at": now - 600.0,  # 10 min ago
            "execution_success": 0,
            "execution_output": "old error",
        }])
        try:
            result = rac.recent_failures(
                window_seconds=120.0, _db_path_override=db_path,
            )
            self.assertEqual(result, "")
        finally:
            db_path.unlink()


class R3_5_LegacyLyingRowsClassified(unittest.TestCase):
    """REGRESSION GUARD: legacy rows with execution_success=1 but
    failure markers in stdout (the wmctrl 14:39 row 105 shape from
    pre-R3 deploy) must be classified as failures via the soft-
    failure detector. Otherwise the cycle reads them as success
    and continues to narrate 'idle' when reality contradicts."""

    def test_legacy_wmctrl_row_classified_as_failure(self):
        """The exact stdout from the 14:39 row 105 — with
        execution_success=1 but unambiguous failure markers in
        stdout — must show up in recent_failures()."""
        from core.decision import recent_action_context as rac
        now = time.time()
        db_path = _make_test_db([{
            "request_id": "b7008d6c_legacy",
            "executed_at": now - 30.0,
            "execution_success": 1,  # the LIE
            "execution_output": (
                "bash: line 1: wmctrl: command not found\n"
                "wmctrl not found\n"
                "Error: Can't open display: (null)\n"
                "Failed creating new xdo instance"
            ),
            "params_json": '{"cmd": "wmctrl -l && xdotool ..."}',
            "plain_english": "Check Firefox tabs",
        }])
        try:
            result = rac.recent_failures(
                window_seconds=120.0, _db_path_override=db_path,
            )
            self.assertIn(
                "b7008d6c", result,
                "legacy lying row (execution_success=1 but failure "
                "markers in stdout) must be classified as failure "
                "via soft-failure detector re-run; request_id is "
                "rendered truncated to 8 chars in the block",
            )
            self.assertIn(
                "FAILED", result,
                "the block must label the entry as FAILED",
            )
            # The kind for wmctrl class should be one of the soft-
            # failure kinds, not exit_nonzero (since we passed
            # execution_success=1).
            self.assertIn(
                "binary_not_found",
                result,
            )
        finally:
            db_path.unlink()

    def test_clean_success_row_excluded(self):
        """A genuinely successful card (success=1, clean stdout)
        must NOT appear in recent_failures."""
        from core.decision import recent_action_context as rac
        now = time.time()
        db_path = _make_test_db([{
            "request_id": "rid_clean",
            "executed_at": now - 30.0,
            "execution_success": 1,
            "execution_output": "Hello, World!",
        }])
        try:
            result = rac.recent_failures(
                window_seconds=120.0, _db_path_override=db_path,
            )
            self.assertEqual(
                result, "",
                "clean successful card must not appear in failures",
            )
        finally:
            db_path.unlink()


class R3_5_BlockShape(unittest.TestCase):
    """REGRESSION GUARD: the formatted block must include enough
    context that the cycle's reasoning can frame the failure
    accurately, but stay compact for the cycle prompt budget."""

    def test_block_contains_section_header(self):
        from core.decision import recent_action_context as rac
        now = time.time()
        db_path = _make_test_db([{
            "request_id": "rid",
            "executed_at": now - 30.0,
            "execution_success": 0,
            "execution_output": "Permission denied",
        }])
        try:
            result = rac.recent_failures(
                window_seconds=120.0, _db_path_override=db_path,
            )
            self.assertTrue(
                result.startswith("[")
                or "RECENT" in result.upper()
                or "FAILED" in result.upper(),
                f"block should be self-identifying; got {result[:120]!r}",
            )
        finally:
            db_path.unlink()

    def test_block_size_bounded(self):
        """Even with many recent failures, the block must stay
        bounded so the cycle prompt doesn't blow up."""
        from core.decision import recent_action_context as rac
        now = time.time()
        rows = [{
            "request_id": f"rid_{i}",
            "executed_at": now - i,
            "execution_success": 0,
            "execution_output": "Permission denied " * 50,
        } for i in range(20)]
        db_path = _make_test_db(rows)
        try:
            result = rac.recent_failures(
                window_seconds=120.0, _db_path_override=db_path,
            )
            self.assertLess(
                len(result), 2000,
                "recent_failures block must stay bounded — even with "
                "many failures, the cycle prompt has a finite budget",
            )
        finally:
            db_path.unlink()


class R3_5_DaemonWiring(unittest.TestCase):
    """REGRESSION GUARD: daemon/maez_daemon.py:_reason() must call
    recent_failures() and inject the block into the cycle prompt
    when non-empty."""

    def test_daemon_imports_recent_action_context(self):
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        self.assertIn(
            "recent_action_context",
            src,
            "daemon/maez_daemon.py must reference "
            "recent_action_context — without this wire, cycle "
            "narration cannot consult preceding card outcomes",
        )

    def test_daemon_calls_recent_failures(self):
        path = REPO / "daemon" / "maez_daemon.py"
        src = path.read_text()
        self.assertIn(
            "recent_failures",
            src,
            "daemon/maez_daemon.py must call recent_failures() to "
            "pull the recent-action context block into the cycle "
            "prompt",
        )


if __name__ == "__main__":
    unittest.main()
