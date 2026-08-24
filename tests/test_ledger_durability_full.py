# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Council ruling Q2 (2026-08-24, 4 seats): synchronous=FULL for every
enabled non-rehearsal canonical writer, unconditionally, no mode switch
at birth.

The invariant: acknowledgment durability must never exceed commit
durability. Today's acknowledgment IS write_turn's returned turn_id
(used immediately as parent_turn_id / felt-state), so the commit behind
it must survive power loss, not merely process death. Rehearsal
sidecar writers are explicitly disposable and may keep NORMAL.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_durability_")

from core.ledger import migrate, writer  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


def _sync_mode(w: writer.LedgerWriter) -> int:
    return w._conn.execute("PRAGMA synchronous").fetchone()[0]


class DurabilityPragmaTests(unittest.TestCase):
    def test_enabled_writer_runs_synchronous_full(self):
        db = _fresh_db("full")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                self.assertEqual(
                    _sync_mode(w), 2,
                    "canonical writer must be synchronous=FULL: the ack "
                    "(returned turn_id) must never outlive its commit",
                )
            finally:
                w.close()

    def test_disabled_writer_also_full(self):
        # No mode switch anywhere on the canonical path: a disabled
        # writer never writes, but if the pragma differed by flag state
        # we would have rebuilt the phase-conditional the council refused.
        db = _fresh_db("full_disabled")
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        with patch.dict(os.environ, env, clear=True):
            w = writer.LedgerWriter(db)
            try:
                self.assertEqual(_sync_mode(w), 2)
            finally:
                w.close()

    def test_rehearsal_writer_keeps_normal(self):
        # Rehearsal sidecars are explicitly disposable (council carve-out).
        root = Path(_TEST_DB_DIR) / "rehearsal_root"
        run_dir = root / "x6_testrun"
        run_dir.mkdir(parents=True)
        db = str(run_dir / "ledger.db")
        migrate.run(db)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db, rehearsal_mode=True, rehearsal_root=root)
            try:
                self.assertEqual(_sync_mode(w), 1)
            finally:
                w.close()


if __name__ == "__main__":
    unittest.main()
