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

The broad discovery scan is a separate concern and is not this file's job.
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

    def test_the_row_count_is_sixty_nine(self, table) -> None:
        assert len(table) == 69

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
        assert total == 69

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
        assert sum(scanned.values()) == len(table) == 69

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
