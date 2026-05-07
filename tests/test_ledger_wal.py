# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""WAL-mode invariants for core.ledger.

Locks in LEDGER_ENVELOPE_SCHEMA.md §1 principle 7 ("WAL mode.
Concurrent reads (cockpit) while daemon writes."):

  - After migrate.run() runs, PRAGMA journal_mode reports 'wal'.
  - WAL persists across connection lifetimes: closing every handle
    and reopening still reports 'wal' (WAL is a per-DB persistent
    setting, not per-connection — verifying this catches a writer
    that sets journal_mode on a transient connection only).
  - A reader connection opened concurrently with a writer's open
    transaction is NOT blocked from reading committed state.
  - A reader sees the writer's row only AFTER commit, never during.

The concurrency tests use two sqlite3 connections in the same
process (no threads). SQLite's WAL semantics are connection-scoped,
not thread-scoped, so this is the simpler and less timing-fragile
shape. No sleep-and-hope: every observation is bracketed by an
explicit BEGIN/COMMIT on the writer.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_wal_")

# Intentional hard import. core.ledger.migrate does not yet exist;
# this import will raise ImportError until the migration slice
# lands. That failure is the spec.
from core.ledger import migrate  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db_path(name: str) -> Path:
    p = Path(_TEST_DB_DIR) / name
    if p.exists():
        p.unlink()
    for suffix in ("-wal", "-shm", "-journal"):
        side = p.with_name(p.name + suffix)
        if side.exists():
            side.unlink()
    return p


def _journal_mode(conn: sqlite3.Connection) -> str:
    return conn.execute("PRAGMA journal_mode").fetchone()[0].lower()


class WALModeTests(unittest.TestCase):
    """The migration sets WAL on init and it persists."""

    def test_journal_mode_is_wal_after_migrate(self):
        db_path = _fresh_db_path("wal_mode.db")
        migrate.run(str(db_path))
        conn = sqlite3.connect(db_path)
        try:
            self.assertEqual(_journal_mode(conn), "wal")
        finally:
            conn.close()

    def test_wal_persists_across_fresh_connections(self):
        """WAL is a persistent property of the DB file. After closing
        every connection and reopening, journal_mode should still be
        WAL — proving migrate.run() set it on the file, not on a
        transient handle."""
        db_path = _fresh_db_path("wal_persist.db")
        migrate.run(str(db_path))

        conn = sqlite3.connect(db_path)
        try:
            mode = _journal_mode(conn)
        finally:
            conn.close()
        self.assertEqual(
            mode, "wal",
            "WAL mode must persist on the DB file after migrate.run() exits",
        )


class WALConcurrencyTests(unittest.TestCase):
    """Two connections, one writer in an open tx, one reader."""

    def setUp(self):
        self.db_path = _fresh_db_path("wal_concurrency.db")
        migrate.run(str(self.db_path))
        self.writer = sqlite3.connect(self.db_path, isolation_level=None)
        self.reader = sqlite3.connect(self.db_path, isolation_level=None)

    def tearDown(self):
        self.writer.close()
        self.reader.close()

    def _genesis_hash(self) -> str:
        row = self.reader.execute(
            "SELECT value FROM meta WHERE key='genesis_hash'"
        ).fetchone()
        return row[0]

    def _insert_test_turn(self, conn: sqlite3.Connection, turn_id: str) -> None:
        """Insert a minimal system_event row that links to the genesis
        hash. We use the genesis_hash as prev_chain_hash and a dummy
        chain_hash; this test is about WAL visibility, not chain
        verification."""
        conn.execute(
            "INSERT INTO turns ("
            " turn_id, tenant_id, timestamp, schema_version, turn_kind,"
            " surface, raw_text, prev_chain_hash, chain_hash"
            ") VALUES (?, 'owner', 0.0, 1, 'system_event',"
            " 'system', ?, ?, ?)",
            (turn_id, f"test-{turn_id}", self._genesis_hash(),
             "0" * 64),
        )

    def test_reader_not_blocked_by_open_writer_tx(self):
        """While the writer holds an open transaction, the reader must
        still be able to query committed state (the genesis row)."""
        self.writer.execute("BEGIN IMMEDIATE")
        try:
            self._insert_test_turn(self.writer, "writer-open-tx")
            row = self.reader.execute(
                "SELECT COUNT(*) FROM turns WHERE prev_chain_hash IS NULL"
            ).fetchone()
            self.assertEqual(
                row[0], 1,
                "reader could not see committed genesis row while "
                "writer held an open transaction — WAL likely off",
            )
        finally:
            self.writer.execute("ROLLBACK")

    def test_reader_does_not_see_uncommitted_writes(self):
        """The reader observes the writer's row only after commit."""
        target_id = "vis-test"

        n_before = self.reader.execute(
            "SELECT COUNT(*) FROM turns WHERE turn_id = ?", (target_id,)
        ).fetchone()[0]
        self.assertEqual(n_before, 0)

        self.writer.execute("BEGIN IMMEDIATE")
        self._insert_test_turn(self.writer, target_id)

        n_during = self.reader.execute(
            "SELECT COUNT(*) FROM turns WHERE turn_id = ?", (target_id,)
        ).fetchone()[0]
        self.assertEqual(
            n_during, 0,
            "reader saw uncommitted write — WAL isolation broken",
        )

        self.writer.execute("COMMIT")

        n_after = self.reader.execute(
            "SELECT COUNT(*) FROM turns WHERE turn_id = ?", (target_id,)
        ).fetchone()[0]
        self.assertEqual(
            n_after, 1,
            "reader did not see committed write after writer COMMIT",
        )


if __name__ == "__main__":
    unittest.main()
