# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for the writer.try_write_turn shadow-write helper.

Daemon callers use this helper so a ledger failure cannot break the
user-facing reply path. Every plausible failure mode must result in
a logged warning and a None return, NEVER an exception propagating
to the caller.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_try_write_")

from core.ledger import migrate, writer  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


class TryWriteTurnTests(unittest.TestCase):
    """try_write_turn always returns None or a turn_id, never raises."""

    def test_writes_when_enabled(self):
        db = _fresh_db("enabled")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = writer.try_write_turn(db, "user_message", "hello")
        self.assertIsNotNone(tid)
        self.assertIsInstance(tid, str)

    def test_returns_none_when_disabled(self):
        db = _fresh_db("disabled")
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        env["MAEZ_LEDGER_WRITES"] = "0"
        with patch.dict(os.environ, env, clear=True):
            tid = writer.try_write_turn(db, "user_message", "hello")
        self.assertIsNone(tid)

    def test_disabled_shadow_write_does_not_create_db(self):
        """Default-off must mean no production ledger file is touched."""
        db = Path(_TEST_DB_DIR) / f"disabled_missing_{os.urandom(4).hex()}.db"
        self.assertFalse(db.exists())
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        env["MAEZ_LEDGER_WRITES"] = "0"
        with patch.dict(os.environ, env, clear=True):
            tid = writer.try_write_turn(str(db), "user_message", "hello")
        self.assertIsNone(tid)
        self.assertFalse(
            db.exists(),
            "disabled try_write_turn must return before sqlite3.connect",
        )

    def test_unrecognized_shadow_write_flag_does_not_create_db(self):
        """Garbage flag values warn and stay dormant without creating DB."""
        db = Path(_TEST_DB_DIR) / f"garbage_flag_{os.urandom(4).hex()}.db"
        self.assertFalse(db.exists())
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "yes"}):
            # De-fork: the unrecognized-flag warning now comes from the shared
            # core.ledger.writes_flag helper, not the writer logger.
            with self.assertLogs("core.ledger.writes_flag", level="WARNING") as cm:
                tid = writer.try_write_turn(str(db), "user_message", "hello")
        self.assertIsNone(tid)
        self.assertFalse(db.exists())
        self.assertTrue(any("MAEZ_LEDGER_WRITES" in line for line in cm.output))

    def test_returns_none_on_validation_error(self):
        """A payload violating the per-kind contract must be swallowed,
        not raised. Production daemon must keep responding even when
        the caller passes a bad payload to the ledger."""
        db = _fresh_db("invalid")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertLogs("core.ledger.writer", level="WARNING") as cm:
                # model_reply requires model_id; passing it without
                # model_id triggers ValueError inside write_turn,
                # which try_write_turn must swallow.
                tid = writer.try_write_turn(
                    db, "model_reply", "missing required fields",
                )
        self.assertIsNone(tid)
        self.assertTrue(any("shadow ledger write failed" in line
                            for line in cm.output),
            f"expected shadow-write warning; got {cm.output!r}")

    def test_returns_none_on_missing_db(self):
        """Nonexistent DB path: writer init may fail (FK pragma on a
        new file is OK, but SELECT on missing meta won't be). Helper
        must swallow."""
        nonexistent = str(Path(_TEST_DB_DIR) / "definitely_not_there.db")
        # First let writer create the file via sqlite3.connect (it
        # will), but reads of meta will fail because no migrate ran.
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = writer.try_write_turn(nonexistent, "user_message", "x")
        # Either init failed or write_turn failed when reading meta —
        # either way, return None and DON'T raise.
        self.assertIsNone(tid)

    def test_returns_none_on_unwritable_db_path(self):
        """An unwritable parent dir for the DB triggers init failure."""
        bad_path = "/nonexistent_dir_that_should_never_exist_xyz/ledger.db"
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = writer.try_write_turn(bad_path, "user_message", "x")
        self.assertIsNone(tid)

    def test_kwargs_passed_through(self):
        """Optional kwargs reach the underlying write_turn."""
        db = _fresh_db("kwargs")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = writer.try_write_turn(
                db, "user_message", "with surface",
                surface="telegram",
                raw_surface="telegram_text",
            )
        self.assertIsNotNone(tid)
        # Verify surface landed.
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT surface, raw_surface FROM turns WHERE turn_id = ?",
                (tid,),
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("telegram", "telegram_text"))

    def test_writer_closed_on_success(self):
        """Helper must close the writer even on success."""
        db = _fresh_db("close_success")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            writer.try_write_turn(db, "user_message", "first")
            # If close() didn't run, the SQLite file would still be
            # locked. A fresh writer instance can write a second turn.
            tid2 = writer.try_write_turn(db, "user_message", "second")
        self.assertIsNotNone(tid2)


if __name__ == "__main__":
    unittest.main()
