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
import subprocess
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# matches `with sqlite3.connect(<anything-without-parens>) as <var>` — the footgun.
_BARE = re.compile(r"with\s+sqlite3\.connect\([^)]*\)\s+as\s+\w+")

# Non-source tooling dirs, for the no-git fallback walk only.
_SKIP_TOP = {
    "tests", "docs", "backups", "superpowers", "__pycache__", ".git",
    ".venv", "venv", "env", "node_modules", "build", "dist",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", ".agents", ".claude",
    ".vscode", ".idea", "htmlcov",
}


def _production_py_files():
    """Every git-TRACKED production .py (all roots, recursively), excluding
    tests/. This is the guard's coverage: the earlier "core/daemon/skills"
    allowlist forgot tracked rooms like `memory/` (imported by `core` on the
    live path) and `scripts/`. Scoping to git-tracked files means every tracked
    room is covered AND untracked archival dirs (backups/, plugin copies) are
    not. `tests/` is excluded on purpose — tests may intentionally probe raw
    connections (e.g. the FD-leak probes themselves). Falls back to a
    filesystem walk when run outside a git checkout."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=_REPO, capture_output=True, text=True, check=True,
        ).stdout
        rels = [r for r in out.splitlines() if r and not r.startswith("tests/")]
        if rels:
            for r in rels:
                yield _REPO / r
            return
    except (OSError, subprocess.SubprocessError):
        pass
    # Fallback (no git): walk the filesystem, skipping non-source dirs.
    for entry in sorted(_REPO.iterdir()):
        if entry.name in _SKIP_TOP or entry.name.startswith("."):
            continue
        if entry.is_file() and entry.suffix == ".py":
            yield entry
        elif entry.is_dir():
            for f in entry.rglob("*.py"):
                if "__pycache__" not in str(f):
                    yield f


class NoBareSqliteConnectTests(unittest.TestCase):
    def test_scan_roots_cover_all_production_code(self):
        # Pins the guard's coverage so a tracked production room can never be
        # silently forgotten again (the bug that let memory/quality_tracker's
        # leak through the first pass). If a new top-level prod dir appears,
        # it is auto-scanned; this test just asserts the critical rooms are in.
        scanned = {str(f.relative_to(_REPO)) for f in _production_py_files()}
        for must in ("core/", "daemon/", "skills/", "memory/", "scripts/"):
            self.assertTrue(
                any(p.startswith(must) for p in scanned),
                f"guard must scan {must} (production code can leak there)",
            )
        self.assertFalse(
            any(p.startswith("tests/") for p in scanned),
            "guard intentionally excludes tests/ (they may probe raw connections)",
        )

    def test_no_unclosed_sqlite_connect_context_managers(self):
        offenders: list[str] = []
        for f in _production_py_files():
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
    # No KNOWN-tracked leaks: entity_index._connect() was converted to a
    # conditional-close @contextmanager (2026-06-03), so this set is empty.
    # Re-pinning a leak here requires a `# sqlite-leak-tracked` marker on the
    # offending return AND a reviewed edit to this set — it can never grow
    # silently.
    _EXPECTED_TRACKED: set[str] = set()

    def test_no_connection_returning_factories(self):
        import ast

        offenders: list[str] = []
        tracked: set[str] = set()
        for f in _production_py_files():
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

    def test_no_unclosed_assigned_connections(self):
        # The THIRD shape: `v = sqlite3.connect(...)` assigned, used, and never
        # closed — no `v.close()`, no `closing(v)`, not returned/yielded. The
        # first guard catches `with sqlite3.connect(...) as v:`; the second
        # catches factories that `return` a raw connection. This one catches the
        # assigned-and-abandoned leak (e.g. self_model._wonderings_snapshot, on
        # the live daemon describe() path — Codex traced its ResourceWarning).
        # Escape with `# sqlite-raw-ok` on the assignment line when the
        # connection is provably closed elsewhere (e.g. a passed-in handle).
        import ast

        offenders: list[str] = []
        for f in _production_py_files():
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
                def _is_connect(call: ast.AST) -> bool:
                    return (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and call.func.attr == "connect"
                        and getattr(call.func.value, "id", None) == "sqlite3"
                    )

                def _opens_conn(val: ast.AST) -> bool:
                    # direct `sqlite3.connect(...)` OR pass-or-create
                    # `connection or sqlite3.connect(...)` (a BoolOp).
                    if _is_connect(val):
                        return True
                    return isinstance(val, ast.BoolOp) and any(
                        _is_connect(x) for x in val.values
                    )

                # Covers `v = ...`, `v: T = ...`, and the pass-or-create
                # `v = x or sqlite3.connect(...)`. Only NAME targets: attribute
                # targets like `self._conn = sqlite3.connect(...)` are
                # instance-owned, long-lived connections closed in a separate
                # close()/__del__ — out of scope for a single-function guard.
                assigned: dict[str, int] = {}
                for n in ast.walk(node):
                    if isinstance(n, ast.Assign) and _opens_conn(n.value):
                        for t in n.targets:
                            if isinstance(t, ast.Name):
                                assigned.setdefault(t.id, n.lineno)
                    elif (
                        isinstance(n, ast.AnnAssign)
                        and n.value is not None
                        and _opens_conn(n.value)
                        and isinstance(n.target, ast.Name)
                    ):
                        assigned.setdefault(n.target.id, n.lineno)
                if not assigned:
                    continue
                for v, ln in assigned.items():
                    handled = False
                    for n in ast.walk(node):
                        # v.close()
                        if (
                            isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Attribute)
                            and n.func.attr == "close"
                            and isinstance(n.func.value, ast.Name)
                            and n.func.value.id == v
                        ):
                            handled = True
                        # return v / yield v — handed off (other guards' job)
                        if isinstance(n, ast.Return) and isinstance(n.value, ast.Name) and n.value.id == v:
                            handled = True
                        if isinstance(n, ast.Yield) and isinstance(n.value, ast.Name) and n.value.id == v:
                            handled = True
                        # closing(v) / contextlib.closing(v)
                        if isinstance(n, ast.Call):
                            cf = n.func
                            nm = cf.attr if isinstance(cf, ast.Attribute) else getattr(cf, "id", None)
                            if nm == "closing" and any(
                                isinstance(a, ast.Name) and a.id == v for a in n.args
                            ):
                                handled = True
                    if handled:
                        continue
                    line = src_lines[ln - 1] if ln <= len(src_lines) else ""
                    if "sqlite-raw-ok" in line:
                        continue
                    offenders.append(f"{rel}:{ln}")

        self.assertEqual(
            offenders,
            [],
            "assigned-but-never-closed sqlite connections leak FDs (no v.close(), no "
            "closing(v), not handed off). Wrap the connect in closing(...) or add a "
            "try/finally v.close(); or — if a caller owns it — mark the assignment "
            "`# sqlite-raw-ok: <reason>`:\n  " + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
