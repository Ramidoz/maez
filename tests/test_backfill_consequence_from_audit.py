# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for scripts/backfill_consequence_from_audit.py.

The decision_pipeline producer fix (commit 8694b14) only catches
NEW approve-and-failed events. Historical audit_log.db rows
(95 of them, mostly an `apt install openrgb` fixation episode)
never landed in consequence_memory and so are invisible to the
planner's "LEARNED FROM PAST MISTAKES" prompt block.

This is a one-shot migration script that:
  - reads `outcome='approved_and_failed'` rows from audit_log.db
  - writes them to consequence_memory's events table as
    `class='tool_failure'`, preserving the original outcome_ts
  - is idempotent: re-runs scan extra_json for an audit_id marker
    and skip already-backfilled rows
  - dry-runs by default; --commit gates real writes
  - logs every action to logs/backfill_approved_and_failed_<date>.txt

Test design follows scripts/memory_curation/curate_2026_04_24.py's
pattern: hermetic temp DBs via env-var redirection, no shared
state with the live store.
"""
from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _make_audit_db(path: Path, rows: list[dict]) -> None:
    """Build a minimal audit_log.db with the columns the backfill
    script reads. Schema mirrors core/decision/audit_log.py."""
    con = sqlite3.connect(path)
    con.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            ts REAL,
            action TEXT,
            params_json TEXT,
            intent_category TEXT,
            lane TEXT,
            decision TEXT,
            confidence REAL,
            reasoning TEXT,
            concerns_json TEXT,
            mitigations_json TEXT,
            summary TEXT,
            injection_buckets TEXT,
            injection_severity TEXT,
            judge_raw TEXT,
            parse_error TEXT,
            latency_ms INTEGER,
            nonce TEXT,
            policy_rule_id TEXT,
            outcome TEXT,
            outcome_ts REAL,
            outcome_notes TEXT,
            memory_phase TEXT,
            session_id TEXT
        )
        """
    )
    for r in rows:
        con.execute(
            "INSERT INTO audit_log (request_id, ts, action, params_json, "
            "outcome, outcome_ts, outcome_notes) VALUES (?,?,?,?,?,?,?)",
            (
                r["request_id"], r.get("ts", 1.0), r.get("action", "run_shell"),
                r.get("params_json", "{}"), r["outcome"],
                r.get("outcome_ts"), r.get("outcome_notes", ""),
            ),
        )
    con.commit()
    con.close()


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.audit_db = tmp / "audit_log.db"
        self.cm_db = tmp / "consequence_memory.db"
        self.log_path = tmp / "backfill.txt"
        self._env = mock.patch.dict(os.environ, {
            "MAEZ_CONSEQUENCE_MEMORY_DB": str(self.cm_db),
        })
        self._env.start()
        # reload consequence_memory so its DB_PATH picks up the env var
        from core import consequence_memory as cm
        importlib.reload(cm)
        self.cm = cm

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def _import_backfill(self):
        # Import after env is set; reload to be safe.
        if "scripts.backfill_consequence_from_audit" in sys.modules:
            del sys.modules["scripts.backfill_consequence_from_audit"]
        import scripts.backfill_consequence_from_audit as bf
        return bf


class WriteShape(_Base):
    def test_dry_run_writes_nothing(self):
        _make_audit_db(self.audit_db, [
            {"request_id": "req-1", "outcome": "approved_and_failed",
             "outcome_ts": 1700000100.0,
             "params_json": '{"cmd": "apt install openrgb"}',
             "outcome_notes": "exit=100; Unable to locate package openrgb"},
        ])
        bf = self._import_backfill()
        n = bf.run(audit_db=self.audit_db, log_path=self.log_path,
                   commit=False)
        self.assertEqual(n, 1, "should report 1 candidate")
        # No rows written
        rows = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(len(rows), 0)

    def test_commit_writes_one_per_failed_row(self):
        _make_audit_db(self.audit_db, [
            {"request_id": "req-1", "outcome": "approved_and_failed",
             "outcome_ts": 1700000100.0,
             "params_json": '{"cmd": "apt install openrgb"}',
             "outcome_notes": "exit=100; Unable to locate package openrgb"},
            {"request_id": "req-2", "outcome": "approved_and_ran",
             "outcome_ts": 1700000200.0,
             "params_json": '{"cmd": "ls /tmp"}',
             "outcome_notes": ""},
            {"request_id": "req-3", "outcome": "approved_and_failed",
             "outcome_ts": 1700000300.0,
             "params_json": '{"cmd": "git push origin main"}',
             "outcome_notes": "Permission denied (publickey)"},
        ])
        bf = self._import_backfill()
        n = bf.run(audit_db=self.audit_db, log_path=self.log_path,
                   commit=True)
        self.assertEqual(n, 2, "only the two failed rows backfill")
        rows = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(len(rows), 2)

    def test_event_shape_matches_decision_pipeline_producer(self):
        """Backfill rows must be retrievable by the same machinery
        that surfaces live producer rows — context contains action +
        cmd, outcome holds the error, tags include action + first
        token of cmd. Mirrors the _on_approve fix in commit 8694b14."""
        _make_audit_db(self.audit_db, [
            {"request_id": "req-rgb", "outcome": "approved_and_failed",
             "outcome_ts": 1700000100.0,
             "params_json": '{"cmd": "sudo apt install openrgb"}',
             "outcome_notes": "exit=100; Unable to locate package openrgb"},
        ])
        bf = self._import_backfill()
        bf.run(audit_db=self.audit_db, log_path=self.log_path, commit=True)
        rows = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertIn("run_shell", r.context)
        self.assertIn("openrgb", r.context)
        self.assertIn("Unable to locate", r.outcome)
        self.assertIn("run_shell", r.tags)
        self.assertIn("sudo", r.tags)

    def test_preserves_original_outcome_ts(self):
        original = 1700000100.0
        _make_audit_db(self.audit_db, [
            {"request_id": "req-ts", "outcome": "approved_and_failed",
             "outcome_ts": original,
             "params_json": '{"cmd": "ls"}',
             "outcome_notes": "exit=1"},
        ])
        bf = self._import_backfill()
        bf.run(audit_db=self.audit_db, log_path=self.log_path, commit=True)
        rows = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(len(rows), 1)
        # ts must equal original outcome_ts (NOT time.time()) — direct
        # SQLite insert is required because record_event() stamps
        # time.time() on every write.
        self.assertEqual(rows[0].ts, original)

    def test_extra_carries_audit_request_id_and_backfill_flag(self):
        _make_audit_db(self.audit_db, [
            {"request_id": "req-id-marker",
             "outcome": "approved_and_failed",
             "outcome_ts": 1700000100.0,
             "params_json": '{"cmd": "ls"}',
             "outcome_notes": "exit=1"},
        ])
        bf = self._import_backfill()
        bf.run(audit_db=self.audit_db, log_path=self.log_path, commit=True)
        rows = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(rows[0].extra.get("request_id"), "req-id-marker")
        self.assertTrue(rows[0].extra.get("backfill"))


class Idempotency(_Base):
    def test_second_run_writes_zero_new_rows(self):
        _make_audit_db(self.audit_db, [
            {"request_id": "req-a", "outcome": "approved_and_failed",
             "outcome_ts": 1700000100.0,
             "params_json": '{"cmd": "ls"}', "outcome_notes": "exit=1"},
            {"request_id": "req-b", "outcome": "approved_and_failed",
             "outcome_ts": 1700000200.0,
             "params_json": '{"cmd": "pwd"}', "outcome_notes": "exit=1"},
        ])
        bf = self._import_backfill()
        n1 = bf.run(audit_db=self.audit_db, log_path=self.log_path,
                    commit=True)
        n2 = bf.run(audit_db=self.audit_db, log_path=self.log_path,
                    commit=True)
        self.assertEqual(n1, 2)
        self.assertEqual(n2, 0, "re-run must not duplicate rows")
        rows = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(len(rows), 2)


class EdgeCases(_Base):
    def test_empty_audit_log_does_not_crash(self):
        _make_audit_db(self.audit_db, [])
        bf = self._import_backfill()
        n = bf.run(audit_db=self.audit_db, log_path=self.log_path,
                   commit=True)
        self.assertEqual(n, 0)
        self.assertEqual(self.cm.recent(), [])

    def test_missing_outcome_ts_falls_back_to_ts(self):
        """Some old rows may have NULL outcome_ts. Don't drop them;
        fall back to the request ts."""
        _make_audit_db(self.audit_db, [
            {"request_id": "req-null-outcome-ts",
             "outcome": "approved_and_failed",
             "ts": 1699999000.0, "outcome_ts": None,
             "params_json": '{"cmd": "ls"}', "outcome_notes": "exit=1"},
        ])
        bf = self._import_backfill()
        bf.run(audit_db=self.audit_db, log_path=self.log_path, commit=True)
        rows = self.cm.recent(kind=self.cm.CLASS_TOOL_FAILURE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].ts, 1699999000.0)

    def test_log_file_written_in_both_modes(self):
        _make_audit_db(self.audit_db, [
            {"request_id": "r1", "outcome": "approved_and_failed",
             "outcome_ts": 1700000100.0,
             "params_json": '{"cmd": "ls"}', "outcome_notes": "exit=1"},
        ])
        bf = self._import_backfill()
        bf.run(audit_db=self.audit_db, log_path=self.log_path, commit=False)
        self.assertTrue(self.log_path.exists())
        text = self.log_path.read_text()
        self.assertIn("DRYRUN", text)


if __name__ == "__main__":
    unittest.main()
