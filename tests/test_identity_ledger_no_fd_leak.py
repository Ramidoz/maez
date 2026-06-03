# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""The identity ledger must not leak SQLite file handles.

Root cause of the recurring `daemon-cycle-stuck` FD-storm wound: the ledger used
`with sqlite3.connect(db) as conn:`, and the sqlite3 connection context manager
only commits/rolls-back — it does NOT close the connection. Each call leaked one
file handle to identity_ledger.db until garbage collection, and under load the
handles outran GC and exhausted the 1024 FD ceiling (the EMFILE storm).

This test calls a ledger method many times WITHOUT forcing gc, and asserts the
open handles to the db stay bounded — i.e. connections are closed promptly, not
left for the collector.
"""

from __future__ import annotations

import glob
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.memory.identity_ledger import IdentityLedger  # noqa: E402


def _open_handles_to(db_path: Path) -> int:
    target = str(db_path)
    n = 0
    for fd in glob.glob(f"/proc/{os.getpid()}/fd/*"):
        try:
            if os.readlink(fd).startswith(target):
                n += 1
        except OSError:
            pass
    return n


class IdentityLedgerFdLeakTests(unittest.TestCase):
    def test_repeated_reads_do_not_leak_file_handles(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "identity_ledger.db"

        ledger = IdentityLedger(db_path=db)
        baseline = _open_handles_to(db)

        for _ in range(30):
            ledger.recent(limit=5)  # NO gc.collect() — a leak would accumulate

        growth = _open_handles_to(db) - baseline
        self.assertLessEqual(
            growth,
            2,
            f"identity ledger leaked {growth} file handles over 30 reads — "
            f"connections are not being closed (sqlite3 CM does not close).",
        )

    def test_repeated_writes_do_not_leak_file_handles(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "identity_ledger.db"

        ledger = IdentityLedger(db_path=db)
        baseline = _open_handles_to(db)

        for i in range(30):
            ledger.record_event(
                event_type="other", reason=f"fd-leak-probe-{i}", evidence={"i": i}
            )

        growth = _open_handles_to(db) - baseline
        self.assertLessEqual(
            growth,
            2,
            f"identity ledger leaked {growth} file handles over 30 writes.",
        )


if __name__ == "__main__":
    unittest.main()
