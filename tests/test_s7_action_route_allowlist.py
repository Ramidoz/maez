"""S7 v2 action binding — the route allowlist, mechanically checked.

The design's RED contract says every site in the inventory is structurally
pinned by role, that adding an unpinned site in any role fails, and that
"the count comes from the table, never from prose -- three different
hand-counts in one document is what produced this rule."

So this module treats the markdown table in the ratified design as the
single authority and derives everything else from it:

* the tracked call targets and definition targets come FROM the table, so
  the scanner cannot be tuned independently of the thing it checks;
* the comparison is a MULTISET, so a second call to the same target in the
  same function cannot hide behind the first;
* the prose "Counts, derived mechanically" line is checked AGAINST the
  table rather than trusted, which is the drift the rule exists to catch.

The pinned table can only see roads it already lists, so this file also
carries the repo-wide DISCOVERY guard: a sweep of every production file
for tracked call targets, including the shapes a file-scoped scan misses
-- module-level calls, aliased imports and getattr-by-string. Narrowing
that sweep is then a deliberate reviewable act rather than an omission.
"""

from __future__ import annotations

import ast
import collections
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "docs/superpowers/specs/2026-08-07-s7-action-binding-design.md"

_ROW_RE = re.compile(
    r"^\|\s*`?([^`|]+?)`?\s*\|\s*`?([^`|]+?)`?\s*\|\s*([a-z_]+)\s*\|"
    r"\s*([^|]+?)\s*\|\s*(\d+)\s*\|$"
)
_ANCHOR = "single authority allowlist is below"
_COUNTS_PREFIX = "**Counts, derived mechanically"


def _table_rows() -> list[tuple[str, str, str, str, str]]:
    lines = DESIGN.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if _ANCHOR in line)
    rows = []
    for line in lines[start:]:
        if line.startswith(_COUNTS_PREFIX):
            break
        matched = _ROW_RE.match(line)
        if matched:
            rows.append(matched.groups())
    return rows


def _prose_counts() -> tuple[dict[str, int], int]:
    """The sentence under the AUTHORITY table. Checked, never trusted.

    Anchored after the authority marker on purpose: the document still
    contains the superseded v9 counts line, and taking the first match
    silently pins the retired allowlist -- the exact failure the design
    warns about ("a superseded allowlist that is still readable is one
    somebody will pin").
    """
    lines = DESIGN.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if _ANCHOR in line)
    line = next(
        candidate
        for candidate in lines[start:]
        if candidate.startswith(_COUNTS_PREFIX)
    )
    pairs = dict(
        (role, int(count))
        for role, count in re.findall(r"([a-z_]+) (\d+)", line.split(":", 1)[1])
    )
    total = pairs.pop("total")
    return pairs, total


def _scan_with_lines(
    path: str, *, call_targets: set[str], def_targets: set[tuple[str, str]]
):
    """As _scan, but carrying the line each site sits on.

    Line-level identity is part of the contract: without it a site can move
    to a different line -- or two sites can swap -- while the multiset stays
    identical.
    """
    tree = ast.parse((REPO / path).read_text())
    found: list[tuple[str, str, str, int]] = []

    def walk(node, fnstack: list[str], clsstack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, fnstack, clsstack + [child.name])
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = (
                    f"{clsstack[-1]}.{child.name}" if clsstack else child.name
                )
                for candidate in (qualified, child.name):
                    if (path, candidate) in def_targets:
                        found.append((path, candidate, "definition", child.lineno))
                        break
                walk(child, fnstack + [child.name], clsstack)
                continue
            if isinstance(child, ast.Call) and fnstack:
                dotted = ast.unparse(child.func)
                bare = (
                    child.func.attr
                    if isinstance(child.func, ast.Attribute)
                    else getattr(child.func, "id", None)
                )
                for target in (dotted, bare):
                    if target in call_targets:
                        found.append(
                            (path, fnstack[-1], f"call:{target}", child.lineno)
                        )
                        break
            walk(child, fnstack, clsstack)

    walk(tree, [], [])
    return found


def _scan(path: str, *, call_targets: set[str], def_targets: set[tuple[str, str]]):
    """Every tracked site in one file, attributed to its innermost function.

    Nested functions matter: attributing a call to the outer def would let a
    site move into a closure and silently change identity.
    """
    tree = ast.parse((REPO / path).read_text())
    found: list[tuple[str, str, str]] = []

    def walk(node, fnstack: list[str], clsstack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, fnstack, clsstack + [child.name])
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = (
                    f"{clsstack[-1]}.{child.name}" if clsstack else child.name
                )
                for candidate in (qualified, child.name):
                    if (path, candidate) in def_targets:
                        found.append((path, candidate, "definition"))
                        break
                walk(child, fnstack + [child.name], clsstack)
                continue
            if isinstance(child, ast.Call) and fnstack:
                # The table names some targets by receiver (authorization_store
                # .put) because the bare attribute (put) is ambiguous. Match
                # either form, most-qualified first.
                dotted = ast.unparse(child.func)
                bare = (
                    child.func.attr
                    if isinstance(child.func, ast.Attribute)
                    else getattr(child.func, "id", None)
                )
                for target in (dotted, bare):
                    if target in call_targets:
                        found.append((path, fnstack[-1], f"call:{target}"))
                        break
            walk(child, fnstack, clsstack)

    walk(tree, [], [])
    return found


@pytest.fixture(scope="module")
def table():
    rows = _table_rows()
    assert rows, "the authority table did not parse; every check below would be vacuous"
    return rows


@pytest.fixture(scope="module")
def scanned(table):
    call_targets = {r[3][5:] for r in table if r[3].startswith("call:")}
    def_targets = {(r[0], r[1]) for r in table if r[3] == "definition"}
    counted: collections.Counter = collections.Counter()
    for path in sorted({r[0] for r in table}):
        for site in _scan(path, call_targets=call_targets, def_targets=def_targets):
            counted[site] += 1
    return counted


class TestTheTableIsInternallyConsistent:
    """One table, one count."""

    def test_the_row_count_is_seventy_four(self, table) -> None:
        assert len(table) == 74

    def test_the_prose_counts_agree_with_the_table(self, table) -> None:
        """v4's headings totalled 30 while its rows totalled something else.
        The table wins; this test exists to catch the prose drifting."""
        from_table = collections.Counter(row[2] for row in table)
        per_role, total = _prose_counts()
        assert dict(from_table) == per_role
        assert total == len(table)

    def test_the_superseded_counts_line_is_not_what_we_pinned(self) -> None:
        """The retired v9 line is still in the document and says something
        different. If a future edit removes the authority line, the anchored
        lookup must not silently fall back onto the old one."""
        lines = DESIGN.read_text().splitlines()
        all_counts = [i for i, line in enumerate(lines)
                      if line.startswith(_COUNTS_PREFIX)]
        anchor = next(i for i, line in enumerate(lines) if _ANCHOR in line)
        assert len(all_counts) > 1, "expected a superseded counts line to exist"
        assert any(i < anchor for i in all_counts), "no pre-anchor line to confuse"
        _per_role, total = _prose_counts()
        assert total == 74

    def test_the_role_counts_sum_to_the_row_count(self, table) -> None:
        from_table = collections.Counter(row[2] for row in table)
        assert sum(from_table.values()) == len(table)

    def test_every_row_names_a_file_that_exists(self, table) -> None:
        for row in table:
            assert (REPO / row[0]).is_file(), row[0]

    def test_the_syntactic_roles_are_a_closed_vocabulary(self, table) -> None:
        kinds = {row[3].split(":", 1)[0] for row in table}
        assert kinds == {"call", "definition"}


class TestTheAllowlistMatchesTheCode:
    """The whole point: no unpinned site, in any role."""

    def test_no_pinned_site_has_disappeared(self, table, scanned) -> None:
        expected = collections.Counter((r[0], r[1], r[3]) for r in table)
        missing = expected - scanned
        assert not missing, f"pinned sites absent from the code: {sorted(missing)}"

    def test_no_unpinned_site_exists(self, table, scanned) -> None:
        expected = collections.Counter((r[0], r[1], r[3]) for r in table)
        extra = scanned - expected
        assert not extra, f"unpinned sites present in the code: {sorted(extra)}"

    def test_the_totals_match_exactly(self, table, scanned) -> None:
        assert sum(scanned.values()) == len(table) == 74

    def test_multiplicity_is_carried_not_collapsed(self, table, scanned) -> None:
        """A second call to the same target in the same function must be
        counted, or it hides behind the first. The table contains exactly
        one such pair; if it ever contains none this test must be rewritten
        rather than quietly passing on an empty set."""
        expected = collections.Counter((r[0], r[1], r[3]) for r in table)
        repeated = {key: n for key, n in expected.items() if n > 1}
        assert repeated, "no multiplicity in the table; this check is vacuous"
        for key, n in repeated.items():
            assert scanned[key] == n, (key, scanned[key], n)


class TestLineLevelIdentity:
    """The table records a line per site; without checking it, a site can
    move -- or two sites can swap -- while the multiset stays identical."""

    def test_identity_ignoring_lines_is_already_exact(self, table, scanned) -> None:
        """CONTROL. If this failed, a line mismatch below could mean a road
        moved rather than a line moving under a stationary road."""
        expected = collections.Counter((r[0], r[1], r[3]) for r in table)
        assert expected == scanned

    def test_every_row_sits_on_the_line_it_claims(self, table) -> None:
        """RED, with a precise cause.

        The roads are unchanged -- the control above proves that -- but this
        slice has been editing core/governance/operator_user_boundary.py, so
        the ratified table's line numbers for that file are stale. The table
        is generator-derived, and the fix is to regenerate it once that file
        stops moving, NOT to relax this check: dropping line identity lets a
        site move, or two sites swap, while the multiset stays identical.
        """
        call_targets = {r[3][5:] for r in table if r[3].startswith("call:")}
        def_targets = {(r[0], r[1]) for r in table if r[3] == "definition"}
        found = set()
        for path in sorted({r[0] for r in table}):
            found.update(
                _scan_with_lines(
                    path, call_targets=call_targets, def_targets=def_targets
                )
            )
        expected = {(r[0], r[1], r[3], int(r[4])) for r in table}
        drifted = sorted({row[0] for row in (expected - found) | (found - expected)})
        assert expected == found, (
            f"table line numbers are stale for: {drifted}. "
            f"{len(expected - found)} of {len(expected)} rows. "
            "Regenerate the table; do not relax this check."
        )


_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "tests",
        "docs",
        "logs",
    }
)


def _production_files() -> list[str]:
    """Every production .py, walked in-process.

    Deliberately NOT `git ls-files`: spawning a subprocess from a test
    recreates the airlock spawn-debt that already blocks two tests from
    certifying. A walk also sees UNTRACKED files, which is the right
    behaviour for a discovery guard -- a new road is a new road whether or
    not it has been committed yet.
    """
    import os

    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for name in filenames:
            if name.endswith(".py"):
                found.append(str(Path(dirpath, name).relative_to(REPO)))
    return sorted(found)


def _discover_source(path, source, *, bare, dotted):
    """All tracked reachability shapes in ONE source string.

    Split out so the scanner can be attacked directly with synthetic code
    rather than only exercised on a repo that happens to be clean.
    """
    dotted_tails = {t.split(".")[-1] for t in dotted}
    sites, module_level, via_getattr, via_alias = [], [], [], []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return sites, module_level, via_getattr, via_alias

    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        # import aliases: from x import build_work_request_envelope as b
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                if a.asname and a.name.split(".")[-1] in bare:
                    aliases[a.asname] = a.name.split(".")[-1]
        # ASSIGNMENT aliases: b = build_work_request_envelope
        if isinstance(node, ast.Assign):
            value = node.value
            tail = (
                value.attr
                if isinstance(value, ast.Attribute)
                else (value.id if isinstance(value, ast.Name) else None)
            )
            if tail in bare or tail in dotted_tails:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        aliases[target.id] = tail

    def walk(node, fn):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child, child.name)
                continue
            if isinstance(child, ast.ClassDef):
                walk(child, fn)
                continue
            if isinstance(child, ast.Call):
                name = (
                    child.func.attr
                    if isinstance(child.func, ast.Attribute)
                    else getattr(child.func, "id", None)
                )
                if name in aliases:
                    via_alias.append((path, aliases[name], child.lineno))
                    name = aliases[name]
                unparsed = ast.unparse(child.func)
                hit = (
                    unparsed
                    if unparsed in dotted
                    else (name if name in bare else None)
                )
                if hit:
                    sites.append((path, fn or "<module>", hit, child.lineno))
                    if fn is None:
                        module_level.append((path, hit, child.lineno))
                # getattr(store, "put") -- reaches a DOTTED target by its
                # tail, which no call-graph check in this file can see.
                if (
                    name == "getattr"
                    and len(child.args) > 1
                    and isinstance(child.args[1], ast.Constant)
                    and child.args[1].value in (bare | dotted | dotted_tails)
                ):
                    via_getattr.append((path, child.args[1].value, child.lineno))
            walk(child, fn)

    walk(tree, None)
    return sites, module_level, via_getattr, via_alias


def _targets(table):
    call_targets = {r[3][5:] for r in table if r[3].startswith("call:")}
    return (
        {t for t in call_targets if "." not in t},
        {t for t in call_targets if "." in t},
    )


def _discover(table):
    """Repo-wide sweep for tracked call targets, in ANY production file.

    The pinned inventory can only see roads it already lists. This sweep is
    the discovery half.

    Definition names are deliberately NOT swept as call targets. Reducing
    `S7AuthorizationStore.put` to bare `put` matched a terminal-UI buffer
    write and reported a new S7 road that did not exist.
    """
    bare, dotted = _targets(table)
    sites, module_level, via_getattr, via_alias = [], [], [], []
    for path in _production_files():
        try:
            source = (REPO / path).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        s, m, g, a = _discover_source(path, source, bare=bare, dotted=dotted)
        sites += s
        module_level += m
        via_getattr += g
        via_alias += a
    return sites, module_level, via_getattr, via_alias


class TestRepoWideDiscoveryGuard:
    """The pinned table cannot see a NEW road. This can.

    It fires when a tracked target is called anywhere outside the
    allowlist, so narrowing it is a deliberate reviewable act rather than
    an omission nobody notices.
    """

    def test_the_sweep_actually_reaches_the_repo(self, table) -> None:
        """CONTROL: an empty sweep would make every check below vacuous."""
        assert len(_production_files()) > 500
        sites, _m, _g, _a = _discover(table)
        # The sweep looks for CALL targets only; definitions are not call
        # sites. So the floor is the table's call-row count, not its total.
        call_rows = sum(1 for r in table if r[3].startswith("call:"))
        assert call_rows == 56
        assert len(sites) >= call_rows, (len(sites), call_rows)

    def test_no_tracked_call_lives_outside_the_allowlisted_files(
        self, table
    ) -> None:
        listed = {r[0] for r in table}
        sites, _m, _g, _a = _discover(table)
        strangers = sorted({(f, fn, t) for f, fn, t, _ln in sites if f not in listed})
        assert not strangers, f"tracked S7 calls in unpinned files: {strangers}"

    def test_no_tracked_call_happens_at_module_level(self, table) -> None:
        """A module-level call runs at import time, before any authority
        exists, and the file-scoped scanner cannot attribute it."""
        _s, module_level, _g, _a = _discover(table)
        assert not module_level, module_level

    def test_no_tracked_target_is_reached_by_getattr(self, table) -> None:
        """getattr(obj, "consume_for_execution") is invisible to every
        call-graph check in this file."""
        _s, _m, via_getattr, _a = _discover(table)
        assert not via_getattr, via_getattr

    def test_no_tracked_target_is_reached_through_an_alias(self, table) -> None:
        _s, _m, _g, via_alias = _discover(table)
        assert not via_alias, via_alias


class TestTheDiscoveryScannerIsItselfAttacked:
    """A guard that only ever runs against a clean repo proves nothing.

    Each case below is a way to reach a tracked target that the earlier
    file-scoped scanner could not see. They are fed as synthetic source so
    the scanner is tested, not the repo's current cleanliness.
    """

    def _run(self, table, source: str):
        bare, dotted = _targets(table)
        return _discover_source("synthetic.py", source, bare=bare, dotted=dotted)

    def test_a_plain_call_is_seen(self, table) -> None:
        """CONTROL: if this missed, every negative below would be vacuous."""
        sites, _m, _g, _a = self._run(
            table, "def f():\n    build_work_request_envelope()\n"
        )
        assert [s[2] for s in sites] == ["build_work_request_envelope"]

    def test_an_import_alias_is_seen(self, table) -> None:
        sites, _m, _g, via_alias = self._run(
            table,
            "from x import build_work_request_envelope as mk\n"
            "def f():\n    mk()\n",
        )
        assert via_alias, "aliased import reached a tracked target unseen"
        assert [s[2] for s in sites] == ["build_work_request_envelope"]

    def test_an_assignment_alias_is_seen(self, table) -> None:
        """`mk = build_work_request_envelope` then `mk()` -- the shape an
        import-only alias check misses entirely."""
        sites, _m, _g, via_alias = self._run(
            table,
            "mk = build_work_request_envelope\ndef f():\n    mk()\n",
        )
        assert via_alias, "assignment alias reached a tracked target unseen"
        assert [s[2] for s in sites] == ["build_work_request_envelope"]

    def test_getattr_by_string_is_seen(self, table) -> None:
        sites, _m, via_getattr, _a = self._run(
            table, 'def f():\n    getattr(s7, "consume_for_execution")()\n'
        )
        assert via_getattr, "getattr-by-string reached a tracked target unseen"

    def test_getattr_reaching_a_dotted_target_by_its_tail_is_seen(
        self, table
    ) -> None:
        """`getattr(store, "put")` reaches authorization_store.put without
        ever naming it. Matching only the full dotted form misses it."""
        _s, _m, via_getattr, _a = self._run(
            table, 'def f():\n    getattr(store, "put")(artifact)\n'
        )
        assert via_getattr, "getattr reached a dotted target by tail, unseen"

    def test_a_module_level_call_is_seen(self, table) -> None:
        """Runs at import time, before any authority exists."""
        _s, module_level, _g, _a = self._run(
            table, "build_work_request_envelope()\n"
        )
        assert module_level

    def test_an_unrelated_put_is_not_flagged(self, table) -> None:
        """The false positive that reported a terminal-UI buffer write as a
        new S7 road. Dotted targets must stay dotted."""
        sites, _m, _g, _a = self._run(
            table, "def f():\n    self.buf.put(1, 2, 'x')\n"
        )
        assert not sites, sites

    def test_an_unrelated_getattr_is_not_flagged(self, table) -> None:
        _s, _m, via_getattr, _a = self._run(
            table, 'def f():\n    getattr(obj, "render")()\n'
        )
        assert not via_getattr, via_getattr
