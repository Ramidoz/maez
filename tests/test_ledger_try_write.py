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

_OWNER_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}
_MODEL_STAMP = {"taint_labels": ["self_generated"], "privacy_access": "public"}


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
            tid = writer.try_write_turn(db, "user_message", "hello", **_OWNER_STAMP)
        self.assertIsNotNone(tid)
        self.assertIsInstance(tid, str)

    def test_returns_none_when_disabled(self):
        db = _fresh_db("disabled")
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        env["MAEZ_LEDGER_WRITES"] = "0"
        with patch.dict(os.environ, env, clear=True):
            tid = writer.try_write_turn(db, "user_message", "hello", **_OWNER_STAMP)
        self.assertIsNone(tid)

    def test_disabled_shadow_write_does_not_create_db(self):
        """Default-off must mean no production ledger file is touched."""
        db = Path(_TEST_DB_DIR) / f"disabled_missing_{os.urandom(4).hex()}.db"
        self.assertFalse(db.exists())
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        env["MAEZ_LEDGER_WRITES"] = "0"
        with patch.dict(os.environ, env, clear=True):
            tid = writer.try_write_turn(str(db), "user_message", "hello", **_OWNER_STAMP)
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
                tid = writer.try_write_turn(str(db), "user_message", "hello", **_OWNER_STAMP)
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
                    db, "model_reply", "missing required fields", **_MODEL_STAMP
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
            tid = writer.try_write_turn(nonexistent, "user_message", "x", **_OWNER_STAMP)
        # Either init failed or write_turn failed when reading meta —
        # either way, return None and DON'T raise.
        self.assertIsNone(tid)

    def test_returns_none_on_unwritable_db_path(self):
        """An unwritable parent dir for the DB triggers init failure."""
        bad_path = "/nonexistent_dir_that_should_never_exist_xyz/ledger.db"
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = writer.try_write_turn(bad_path, "user_message", "x", **_OWNER_STAMP)
        self.assertIsNone(tid)

    def test_kwargs_passed_through(self):
        """Optional kwargs reach the underlying write_turn."""
        db = _fresh_db("kwargs")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = writer.try_write_turn(
                db, "user_message", "with surface",
                surface="telegram",
                raw_surface="telegram_text",
                **_OWNER_STAMP,
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
            writer.try_write_turn(db, "user_message", "first", **_OWNER_STAMP)
            # If close() didn't run, the SQLite file would still be
            # locked. A fresh writer instance can write a second turn.
            tid2 = writer.try_write_turn(db, "user_message", "second", **_OWNER_STAMP)
        self.assertIsNotNone(tid2)


class DeadLetterTests(unittest.TestCase):
    """A failed ENABLED write must never be silent: the payload is durably
    dead-lettered next to the DB and the failure logs at ERROR. The
    never-raise contract for the reply path is unchanged."""

    def test_failed_enabled_write_is_dead_lettered(self):
        db = _fresh_db("deadletter")
        dead = Path(writer.dead_letter_path(db))
        self.assertFalse(dead.exists())
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertLogs("core.ledger.writer", level="ERROR") as cm:
                # model_reply without model_id → ValueError inside write_turn.
                tid = writer.try_write_turn(
                    db, "model_reply", "a life event that must not vanish",
                    **_MODEL_STAMP,
                )
        self.assertIsNone(tid)
        self.assertTrue(
            dead.exists(),
            "failed enabled write must leave a durable dead-letter record",
        )
        import json
        lines = dead.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["turn_kind"], "model_reply")
        self.assertEqual(record["raw_text"], "a life event that must not vanish")
        self.assertIn("error", record)
        # Replay identity + classification: a deterministic validation
        # refusal must be marked non-replayable, with an idempotency id.
        self.assertEqual(record["category"], "refused")
        self.assertTrue(record["event_id"])
        self.assertTrue(any("shadow ledger write failed" in line
                            for line in cm.output))
        self.assertTrue(any("deadletter" in line for line in cm.output),
                        "ERROR log must name the dead-letter path")

    def test_set_typed_kwargs_do_not_break_dead_letter(self):
        """write_turn accepts set-typed taint_labels; the dead-letter
        serializer must coerce them losslessly, not crash or stringify."""
        db = _fresh_db("deadletter_set")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertLogs("core.ledger.writer", level="ERROR"):
                tid = writer.try_write_turn(
                    db, "model_reply", "set-typed stamp payload",
                    taint_labels={"self_generated", "a_second_label"},
                    privacy_access="public",
                )
        self.assertIsNone(tid)
        import json
        record = json.loads(
            Path(writer.dead_letter_path(db)).read_text().splitlines()[0]
        )
        self.assertEqual(
            record["kwargs"]["taint_labels"],
            ["a_second_label", "self_generated"],
        )

    def test_writer_init_failure_is_dead_lettered(self):
        # A directory as db_path makes sqlite3.connect fail at init.
        dbdir = Path(_TEST_DB_DIR) / f"init_fail_{os.urandom(4).hex()}"
        dbdir.mkdir()
        dead = Path(writer.dead_letter_path(str(dbdir)))
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertLogs("core.ledger.writer", level="ERROR"):
                tid = writer.try_write_turn(
                    str(dbdir), "user_message", "init-failure payload",
                    **_OWNER_STAMP,
                )
        self.assertIsNone(tid)
        self.assertTrue(
            dead.exists(),
            "init failure of an enabled writer must dead-letter the payload",
        )
        import json
        record = json.loads(dead.read_text().splitlines()[0])
        self.assertEqual(record["raw_text"], "init-failure payload")
        # sqlite refusing to open a directory is environmental, not a
        # payload refusal — it must be classified as a replay candidate.
        self.assertEqual(record["category"], "failed")

    def test_unwritable_dead_letter_logs_critical_and_never_raises(self):
        db = _fresh_db("deadletter_blocked")
        # Occupy the dead-letter path with a directory so append fails.
        Path(writer.dead_letter_path(db)).mkdir()
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertLogs("core.ledger.writer", level="CRITICAL") as cm:
                tid = writer.try_write_turn(
                    db, "model_reply", "payload with blocked dead-letter",
                    **_MODEL_STAMP,
                )
        self.assertIsNone(tid)
        self.assertTrue(any("LOST" in line for line in cm.output),
                        "a lost payload must be named as lost, loudly")

    def test_dead_letter_status_is_machine_readable(self):
        db = _fresh_db("deadletter_status")
        self.assertEqual(
            writer.dead_letter_status(db),
            {"files": 0, "rows": 0, "oldest_ts": None, "bytes": 0},
        )
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertLogs("core.ledger.writer", level="ERROR"):
                writer.try_write_turn(
                    db, "model_reply", "health probe payload", **_MODEL_STAMP
                )
        status = writer.dead_letter_status(db)
        self.assertEqual(status["files"], 1)
        self.assertEqual(status["rows"], 1)
        self.assertIsNotNone(status["oldest_ts"])
        self.assertGreater(status["bytes"], 0)

    def test_disabled_write_leaves_no_dead_letter(self):
        db = _fresh_db("deadletter_disabled")
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        env["MAEZ_LEDGER_WRITES"] = "0"
        with patch.dict(os.environ, env, clear=True):
            tid = writer.try_write_turn(
                db, "model_reply", "dormant", **_MODEL_STAMP,
            )
        self.assertIsNone(tid)
        import glob
        self.assertEqual(glob.glob(writer.dead_letter_glob(db)), [],
                         "dormant state must not grow new files")


if __name__ == "__main__":
    unittest.main()
