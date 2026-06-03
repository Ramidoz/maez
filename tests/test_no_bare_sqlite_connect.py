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

    # The "hose shape": a factory that RETURNS a raw connection. Callers
    # consume it as `with f() as c:` — which commits but never closes —
    # leaking one FD per call (Codex empirically: 30 over 30 uses). The
    # fix is to make the factory a @contextmanager that yields and closes.
    #
    # A raw-connection return is allowed ONLY when the return line carries
    # an explicit, reviewed marker:
    #   `# sqlite-raw-ok: <why the caller provably owns + closes it>`
    # used where the @contextmanager shape would break a load-bearing
    # contract (e.g. an Optional None-on-failure factory the caller closes
    # itself, or a pass-or-create handle with owns_conn/finally close).
    #
    # A KNOWN-but-not-yet-fixed leak is tracked separately and PINNED via
    #   `# sqlite-leak-tracked: <follow-up doc>`
    # plus an entry in _EXPECTED_TRACKED below — so a real leak can neither
    # be added nor silently disappear without a reviewed edit to both.
    _EXPECTED_TRACKED = {
        # entity_index._connect() is used as a chained read-handle across
        # ~50 sites (core + scripts + tests); converting it to a context
        # manager is its own slice. See:
        # docs/superpowers/parked/2026-06-03-entity-index-connect-lifecycle-slice.md
        "core/memory/entity_index.py",
    }

    def test_no_connection_returning_factories(self):
        import ast

        offenders: list[str] = []
        tracked: set[str] = set()
        for top in ("core", "daemon", "skills"):
            for f in (_REPO / top).rglob("*.py"):
                if "__pycache__" in str(f):
                    continue
                src = f.read_text(encoding="utf-8")
                src_lines = src.splitlines()
                try:
                    tree = ast.parse(src)
                except SyntaxError:
                    continue
                rel = str(f.relative_to(_REPO))
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    decos = {
                        getattr(d, "id", getattr(d, "attr", None))
                        for d in node.decorator_list
                    }
                    if "contextmanager" in decos:
                        continue
                    # names bound to a sqlite3.connect(...) result in this fn
                    conn_vars: set[str] = set()
                    for n in ast.walk(node):
                        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
                            fn = n.value.func
                            if (
                                isinstance(fn, ast.Attribute)
                                and fn.attr == "connect"
                                and getattr(fn.value, "id", None) == "sqlite3"
                            ):
                                conn_vars.update(
                                    t.id for t in n.targets if isinstance(t, ast.Name)
                                )
                    for n in ast.walk(node):
                        if not (isinstance(n, ast.Return) and n.value is not None):
                            continue
                        v = n.value
                        is_raw = (isinstance(v, ast.Name) and v.id in conn_vars) or (
                            isinstance(v, ast.Call)
                            and isinstance(v.func, ast.Attribute)
                            and v.func.attr == "connect"
                            and getattr(v.func.value, "id", None) == "sqlite3"
                        )
                        if not is_raw:
                            continue
                        line = src_lines[n.lineno - 1] if n.lineno <= len(src_lines) else ""
                        if "sqlite-raw-ok" in line:
                            continue
                        if "sqlite-leak-tracked" in line:
                            tracked.add(rel)
                            continue
                        offenders.append(f"{rel}:{n.lineno}")

        self.assertEqual(
            offenders,
            [],
            "connection-returning factories leak FDs (callers `with f() as c:` "
            "commit but never close). Convert to @contextmanager, or — only if the "
            "caller provably owns the lifecycle — mark the return "
            "`# sqlite-raw-ok: <reason>`:\n  " + "\n  ".join(offenders),
        )
        self.assertEqual(
            tracked,
            self._EXPECTED_TRACKED,
            "the set of KNOWN-tracked sqlite leak factories changed. It is PINNED so "
            "a leak can neither be added nor silently dropped. If you fixed one, "
            "remove BOTH its `# sqlite-leak-tracked` marker and its _EXPECTED_TRACKED "
            f"entry. Got {sorted(tracked)}, expected {sorted(self._EXPECTED_TRACKED)}.",
        )


if __name__ == "__main__":
    unittest.main()
