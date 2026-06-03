# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Guard against the SQLite connection-leak footgun returning anywhere.

`with sqlite3.connect(...) as conn:` does NOT close the connection — the sqlite3
connection context manager only commits/rolls back. The handle lingers until GC,
and under load the handles outran GC and exhausted the FD ceiling (the recurring
daemon-cycle-stuck EMFILE storm; root-caused 2026-06-03). Every connect must be
wrapped in contextlib.closing(...) so the FD closes deterministically:

    with closing(sqlite3.connect(db)) as conn, conn:   # closing→close, conn→commit

This source-contract test scans the codebase and fails if a bare connect-as
context manager reappears.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# matches `with sqlite3.connect(<anything-without-parens>) as <var>` — the footgun.
_BARE = re.compile(r"with\s+sqlite3\.connect\([^)]*\)\s+as\s+\w+")


class NoBareSqliteConnectTests(unittest.TestCase):
    def test_no_unclosed_sqlite_connect_context_managers(self):
        offenders: list[str] = []
        for top in ("core", "daemon", "skills"):
            for f in (_REPO / top).rglob("*.py"):
                if "__pycache__" in str(f):
                    continue
                for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if _BARE.search(line) and "closing(" not in line:
                        offenders.append(f"{f.relative_to(_REPO)}:{i}: {line.strip()}")
        self.assertEqual(
            offenders,
            [],
            "bare `with sqlite3.connect(...) as` leaks file handles until GC. "
            "Wrap in contextlib.closing():\n  " + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
