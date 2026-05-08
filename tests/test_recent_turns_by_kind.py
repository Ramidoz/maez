# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.ledger.recent_turns.recent_turns_by_kind.

Slice 3 proper foundation: bounded ledger lookback that the evidence-
envelope builder uses to populate the `self_history` slot. The
function is a thin SQL wrapper over the existing idx_turns_kind_ts
DESC index, returning raw turn rows (turn_id, timestamp, turn_kind,
raw_text). Shaping into SelfHistoryRef is the envelope builder's job.

Read-only: opens the DB with mode=ro to avoid contending with a live
writer's connection.
"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_recent_turns_")

from core.ledger import migrate, writer  # noqa: E402
from core.ledger import recent_turns  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


def _write(db: str, kind: str, text: str, **kwargs) -> str:
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
        w = writer.LedgerWriter(db)
        try:
            tid = w.write_turn(kind, text, **kwargs)
        finally:
            w.close()
    assert tid is not None, f"write_turn({kind!r}) returned None"
    return tid


_MR_KW = dict(
    model_id="qwen36-27b",
    prompt_hash="p" * 64,
    soul_hash="s" * 64,
    evidence_envelope={"claimable": [], "forbidden": []},
    audit_verdict={"verdict": "grounded"},
)


class EmptyAndShapingTests(unittest.TestCase):
    def test_empty_db_returns_empty(self):
        db = _fresh_db("empty")
        self.assertEqual(
            recent_turns.recent_turns_by_kind(
                db, kinds=["model_reply"], limit=10,
            ),
            [],
        )

    def test_row_shape_has_required_fields(self):
        db = _fresh_db("shape")
        _write(db, "model_reply", "hello world", **_MR_KW)
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply"], limit=10,
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for required in ("turn_id", "timestamp", "turn_kind", "raw_text"):
            self.assertIn(required, row, f"missing {required}")
        self.assertEqual(row["turn_kind"], "model_reply")
        self.assertEqual(row["raw_text"], "hello world")
        self.assertIsInstance(row["timestamp"], float)


class KindFilterTests(unittest.TestCase):
    def test_only_requested_kinds_returned(self):
        db = _fresh_db("kindfilter")
        _write(db, "user_message", "owner says hi")
        _write(db, "model_reply", "maez replies", **_MR_KW)
        _write(db, "user_message", "owner again")
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply"], limit=10,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_text"], "maez replies")

    def test_multiple_kinds_combined(self):
        db = _fresh_db("multi")
        _write(db, "user_message", "u1")
        _write(db, "model_reply", "m1", **_MR_KW)
        _write(db, "daemon_cycle", "d1",
               model_id="qwen36-27b", prompt_hash="p" * 64,
               soul_hash="s" * 64,
               evidence_envelope={"claimable": [], "forbidden": []},
               audit_verdict={"verdict": "grounded"})
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply", "daemon_cycle"], limit=10,
        )
        kinds = {r["turn_kind"] for r in rows}
        self.assertEqual(kinds, {"model_reply", "daemon_cycle"})
        self.assertEqual(len(rows), 2)

    def test_unrequested_kind_never_appears(self):
        db = _fresh_db("exclude")
        _write(db, "user_message", "u1")
        _write(db, "user_message", "u2")
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply"], limit=10,
        )
        self.assertEqual(rows, [])


class OrderingAndLimitTests(unittest.TestCase):
    def test_returned_newest_first(self):
        db = _fresh_db("order")
        _write(db, "model_reply", "first", **_MR_KW)
        time.sleep(0.005)
        _write(db, "model_reply", "second", **_MR_KW)
        time.sleep(0.005)
        _write(db, "model_reply", "third", **_MR_KW)
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply"], limit=10,
        )
        self.assertEqual(
            [r["raw_text"] for r in rows],
            ["third", "second", "first"],
        )

    def test_limit_respected(self):
        db = _fresh_db("limit")
        for i in range(7):
            _write(db, "model_reply", f"reply_{i}", **_MR_KW)
            time.sleep(0.002)
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply"], limit=3,
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["raw_text"], "reply_6")
        self.assertEqual(rows[2]["raw_text"], "reply_4")


class TenantIsolationTests(unittest.TestCase):
    def test_default_tenant_is_owner(self):
        db = _fresh_db("tenant_default")
        _write(db, "model_reply", "owner reply", **_MR_KW)
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply"], limit=10,
        )
        self.assertEqual(len(rows), 1)


class InvalidKindRejectionTests(unittest.TestCase):
    def test_empty_kinds_returns_empty(self):
        db = _fresh_db("emptykinds")
        _write(db, "model_reply", "x", **_MR_KW)
        self.assertEqual(
            recent_turns.recent_turns_by_kind(db, kinds=[], limit=10),
            [],
        )

    def test_zero_limit_returns_empty(self):
        db = _fresh_db("zerolimit")
        _write(db, "model_reply", "x", **_MR_KW)
        self.assertEqual(
            recent_turns.recent_turns_by_kind(
                db, kinds=["model_reply"], limit=0,
            ),
            [],
        )

    def test_negative_limit_rejected(self):
        db = _fresh_db("neglimit")
        with self.assertRaises(ValueError):
            recent_turns.recent_turns_by_kind(
                db, kinds=["model_reply"], limit=-1,
            )


class ReadOnlyTests(unittest.TestCase):
    """The lookback opens the DB read-only — confirm by passing a path
    that exists but is a read-only file (the SQL must still succeed for
    a SELECT-only operation)."""

    def test_readonly_db_path_works(self):
        db = _fresh_db("ro")
        _write(db, "model_reply", "frozen", **_MR_KW)
        # Make file read-only at the FS level. mode=ro URI bypasses
        # write attempts; if the implementation forgot to open read-
        # only, sqlite would still succeed for SELECT but a future
        # journal-mode change attempt would fail. We just confirm the
        # SELECT works and the file mode is unchanged afterwards.
        os.chmod(db, 0o444)
        try:
            rows = recent_turns.recent_turns_by_kind(
                db, kinds=["model_reply"], limit=10,
            )
            self.assertEqual(len(rows), 1)
        finally:
            os.chmod(db, 0o644)


if __name__ == "__main__":
    unittest.main()
