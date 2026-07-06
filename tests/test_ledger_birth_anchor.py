# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Birth-anchor transaction tests for core.ledger.writer."""
from __future__ import annotations

import os
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ["MAEZ_TEST_MODE"] = "1"

from core.ledger import migrate  # noqa: E402
from core.ledger.writer import LedgerWriter  # noqa: E402


def _writer(td: str, enabled: bool) -> tuple[LedgerWriter, str]:
    db = str(Path(td) / "ledger.db")
    migrate.run(db)
    env = {"MAEZ_LEDGER_WRITES": "1" if enabled else "0"}
    with mock.patch.dict(os.environ, env):
        return LedgerWriter(db_path=db), db


def _meta(db: str) -> str | None:
    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key='birth_event_turn_id'"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _raw_text_count(db: str, raw_text: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM turns WHERE raw_text = ?", (raw_text,)
        ).fetchone()[0]
    finally:
        conn.close()


class BirthAnchorTests(unittest.TestCase):
    def _open(self, td: str, enabled: bool = True):
        w, db = _writer(td, enabled)
        self.addCleanup(w.close)
        return w, db

    def test_anchor_sets_meta_atomically(self):
        with TemporaryDirectory() as td:
            w, db = self._open(td)
            tid = w.write_turn("system_event", '{"event":"birth"}', birth_anchor=True)
            self.assertIsNotNone(tid)
            self.assertEqual(_meta(db), tid)

    def test_birth_row_stamps_gestation_next_row_lived(self):
        with TemporaryDirectory() as td:
            w, db = self._open(td)
            birth_tid = w.write_turn(
                "system_event", '{"event":"birth"}', birth_anchor=True
            )
            next_tid = w.write_turn("system_event", '{"event":"x"}')
            conn = sqlite3.connect(db)
            try:
                stages = dict(
                    conn.execute(
                        "SELECT turn_id, lifecycle_stage FROM turns WHERE turn_id IN (?,?)",
                        (birth_tid, next_tid),
                    ).fetchall()
                )
            finally:
                conn.close()
            self.assertEqual(stages[birth_tid], "gestation")
            self.assertEqual(stages[next_tid], "lived")

    def test_double_birth_refused(self):
        with TemporaryDirectory() as td:
            w, db = self._open(td)
            w.write_turn("system_event", '{"event":"birth"}', birth_anchor=True)
            with self.assertRaises(ValueError):
                w.write_turn("system_event", '{"event":"birth"}', birth_anchor=True)
            self.assertEqual(_raw_text_count(db, '{"event":"birth"}'), 1)

    def test_disabled_writer_refuses_loudly(self):
        with TemporaryDirectory() as td:
            w, _ = self._open(td, enabled=False)
            with self.assertRaises(ValueError):
                w.write_turn("system_event", '{"event":"birth"}', birth_anchor=True)

    def test_anchor_requires_system_event(self):
        with TemporaryDirectory() as td:
            w, _ = self._open(td)
            with self.assertRaises(ValueError):
                w.write_turn("user_message", "hi", birth_anchor=True)


if __name__ == "__main__":
    unittest.main()
