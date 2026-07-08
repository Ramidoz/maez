# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Concurrency tests for core.ledger.writer.

Pins:
  - Single-instance lock serialization preserves chain integrity
    under concurrent writes from multiple threads.
  - close() releases resources; subsequent writes raise.
  - close() releases the file lock for a fresh instance on the same
    path.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_ledger_writer_atom_")

from core.ledger import migrate, chain  # noqa: E402
from core.ledger import writer  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db_path(name: str) -> str:
    p = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(p))
    return str(p)


def _meta(db_path: str, key: str) -> str | None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _all_turns(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM turns ORDER BY rowid ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


_USER_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}


class ConcurrencyTests(unittest.TestCase):
    """Single-instance lock serialization preserves chain integrity."""

    def setUp(self):
        self._env_patch = mock.patch.dict(
            os.environ, {"MAEZ_LEDGER_WRITES": "1", "MAEZ_TEST_MODE": "1"}
        )
        self._env_patch.start()
        self.db_path = _fresh_db_path(self._testMethodName)
        self.w = writer.LedgerWriter(self.db_path)

    def tearDown(self):
        try:
            self.w.close()
        except Exception:
            pass
        self._env_patch.stop()

    def _spawn_writers(self, n_threads: int, writes_per_thread: int,
                       post_write_sleep: float = 0.0) -> list[Exception]:
        barrier = threading.Barrier(n_threads)
        errors: list[Exception] = []
        errors_lock = threading.Lock()

        def task(tid: int):
            try:
                barrier.wait(timeout=5.0)
                for i in range(writes_per_thread):
                    self.w.write_turn("user_message", f"t{tid}-i{i}", **_USER_STAMP)
                    if post_write_sleep:
                        time.sleep(post_write_sleep)
            except Exception as e:
                with errors_lock:
                    errors.append(e)

        threads = [threading.Thread(target=task, args=(t,))
                   for t in range(n_threads)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=30.0)
            self.assertFalse(th.is_alive(), "writer thread hung")
        return errors

    def test_two_threads_one_writer_chain_integrity(self):
        errors = self._spawn_writers(n_threads=2, writes_per_thread=10)
        self.assertEqual(errors, [], f"unexpected errors: {errors!r}")
        rows = _all_turns(self.db_path)
        self.assertEqual(len(rows), 1 + 20)  # genesis + 20
        violations = chain.verify_chain(rows)
        self.assertEqual(violations, [], f"chain violations: {violations!r}")
        head = _meta(self.db_path, "last_chain_hash")
        self.assertEqual(head, rows[-1]["chain_hash"])

    def test_two_thread_race_with_scheduling_delay(self):
        """Small post-write delay widens interleaving. With proper Lock,
        chain still verifies clean. Without it, threads would compute
        identical prev_chain_hash and produce a fork."""
        errors = self._spawn_writers(
            n_threads=2, writes_per_thread=10, post_write_sleep=0.001,
        )
        self.assertEqual(errors, [], f"unexpected errors: {errors!r}")
        rows = _all_turns(self.db_path)
        violations = chain.verify_chain(rows)
        self.assertEqual(violations, [],
            f"chain corrupted under contention: {violations!r}")


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self._env_patch = mock.patch.dict(
            os.environ, {"MAEZ_LEDGER_WRITES": "1", "MAEZ_TEST_MODE": "1"}
        )
        self._env_patch.start()
        self.db_path = _fresh_db_path("cleanup")

    def tearDown(self):
        self._env_patch.stop()

    def test_close_makes_subsequent_writes_raise(self):
        w = writer.LedgerWriter(self.db_path)
        w.write_turn("user_message", "pre-close", **_USER_STAMP)
        w.close()
        with self.assertRaises(
            (sqlite3.ProgrammingError, sqlite3.Error, RuntimeError, ValueError)
        ):
            w.write_turn("user_message", "post-close", **_USER_STAMP)

    def test_close_releases_for_new_instance(self):
        w1 = writer.LedgerWriter(self.db_path)
        w1.write_turn("user_message", "first", **_USER_STAMP)
        w1.close()
        w2 = writer.LedgerWriter(self.db_path)
        try:
            tid = w2.write_turn("user_message", "second", **_USER_STAMP)
            self.assertIsNotNone(tid)
        finally:
            w2.close()


if __name__ == "__main__":
    unittest.main()
