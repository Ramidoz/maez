# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Regression: the dormancy gate must not leak file descriptors.

A bare ``with sqlite3.connect(...)`` manages the transaction but does NOT
close the connection. Under cockpit birth-readiness polling this leaked one
fd per store per call and exhausted the daemon's fd limit (2026-07-07),
which manifested as the daemon being unable to open its own S7 database
(``OSError: [Errno 24] Too many open files``). The fix wraps the connect in
``contextlib.closing``; this test proves fds stay flat across many calls.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.governance import dormancy_gate as DG


def _fd_count() -> int:
    return len(os.listdir(f"/proc/{os.getpid()}/fd"))


class DormancyGateNoFdLeakTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        for name, table, column in (
            ("wants.db", "want_events", "provenance"),
            ("wonderings.db", "wonderings", "source"),
            ("private_thoughts.db", "private_thoughts", "provenance"),
        ):
            con = sqlite3.connect(self.dir / name)
            con.execute(f"CREATE TABLE {table}({column} TEXT)")
            con.execute(f"INSERT INTO {table} VALUES('explicit_api')")
            con.commit()
            con.close()

    def test_repeated_two_clause_does_not_leak_fds(self) -> None:
        # warm up (import/first-call fixed costs) then measure steady state
        for _ in range(5):
            DG.two_clause(memory_dir=self.dir)
        before = _fd_count()
        for _ in range(200):
            DG.two_clause(memory_dir=self.dir)
        after = _fd_count()
        self.assertLessEqual(
            after - before,
            2,
            f"dormancy gate leaked fds: {before} -> {after} over 200 calls",
        )


if __name__ == "__main__":
    unittest.main()
