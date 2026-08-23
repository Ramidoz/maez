# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""S1 census — who stamps a phase, and who reads the birth anchor.

Theme 2, S1 protocol §5 (T4) with the command pinned in §10:

    python3 -m core.memory.s1_census --repo . \
        --expected docs/superpowers/witness/theme2-s1-census.json

Walks memory/ core/ daemon/ skills/ cli/ with ``ast.parse``, collects every
writer of a ``memory_phase`` key/column and every reader of
``birth_event_turn_id``, normalizes each hit to ``path::qualname`` (falling
back to ``path::@line`` at module level), sorts, and diffs exactly against
the expected JSON. Exit 0 on equality; exit 1 naming every asymmetric
difference.

WHY THIS EXISTS IN THIS FORM. The expected census was authored by hand and
frozen with a digest. On 2026-08-22 it was found to name
``AuditLog._migration_null_normalize``, a method that does not exist — the
behaviour is real but inline in ``AuditLog._initialize``. It also named
``span_planner.plan()`` and two ``PrivateThoughts`` methods that were never
written. Four gate rounds passed those artifacts. The digests matched
throughout, because a digest proves a file is unchanged, not that its
claims are true.

So the expectation must be DERIVED BY EXECUTION and reviewed, never typed
from memory. ``--emit`` prints the observed census; that output becomes the
frozen file. The guard against that being circular is §5's two controls,
which this tool is built to fail: a seeded writer must be named, and a
deleted expectation must be named. A census that cannot fail in both
directions is decoration.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

# Gate round 20: scripts/ added -- the owner birth ceremony
# (scripts/birth_ceremony.py) performs the re-birth-prevention anchor read,
# and a census that cannot see the birth transaction itself is not a census
# of birth-state readers. Protocol §5's root list is amended (v7.3).
WALK_ROOTS = ("memory", "core", "daemon", "skills", "cli", "scripts")
EXCLUDED_PARTS = {"tests", "docs", "logs", "__pycache__", ".venv",
                  ".claude", "node_modules", "backups"}

# This module names both literals in its own source, so it censuses itself
# and would sit in its own frozen expectation forever. It stamps nothing.
SELF_PATH = "core/memory/s1_census.py"

class CensusScanError(RuntimeError):
    """A walked file could not be scanned. Fails the census loudly."""


PHASE_KEY = "memory_phase"
BIRTH_KEY = "birth_event_turn_id"

# A construct can read the birth anchor WITHOUT naming it: source_awareness
# calls birth_phase.is_born(), which does the SELECT. A literal-only sweep
# misses those, and the hand-authored census had source_awareness right where
# this tool had it wrong -- the frozen artifact caught the tool, not only the
# other way round. Any call to the birth_phase accessor surface counts.
BIRTH_ACCESSORS = frozenset({
    "is_born", "current_phase", "birth_event_turn_id", "resolve",
    "phase_for_stamp",
})

# A SQL string counts as a WRITE of the column only in these shapes. A bare
# SELECT that mentions the column is a read, and conflating the two is how a
# census stops meaning anything.
_SQL_WRITE_MARKERS = ("insert into", "update ", "alter table", "set ",
                      "values", "add column")


def _qualname_index(tree: ast.AST) -> list[tuple[int, int, str]]:
    """(start, end, dotted-name) for every def/class, innermost last."""
    spans: list[tuple[int, int, str]] = []

    def walk(node: ast.AST, prefix: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                name = prefix + [child.name]
                spans.append((child.lineno,
                              getattr(child, "end_lineno", child.lineno),
                              ".".join(name)))
                walk(child, name)
            else:
                walk(child, prefix)

    walk(tree, [])
    return spans


def _qualname_at(spans, line: int) -> str | None:
    """Innermost enclosing def/class, or None at module level."""
    best = None
    for start, end, name in spans:
        if start <= line <= end and (best is None or start > best[0]):
            best = (start, name)
    return best[1] if best else None


def _is_phase_write(node: ast.AST, parents: dict) -> bool:
    """Does this occurrence of the literal write the column?"""
    parent = parents.get(id(node))
    if parent is None:
        return False
    # {"memory_phase": ...}
    if isinstance(parent, ast.Dict) and any(
            k is node for k in parent.keys):
        return True
    # f(..., memory_phase=...) is a keyword, not a Constant — handled below.
    # obj["memory_phase"] = ... : the literal is the slice of an assigned
    # Subscript.
    if isinstance(parent, ast.Subscript):
        gp = parents.get(id(parent))
        if isinstance(gp, ast.Assign) and any(t is parent for t in gp.targets):
            return True
    return False


def _birth_accessor_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Local names that resolve to a birth_phase accessor, aliases included.

    `source_awareness.py:341` does
    ``from core.memory.birth_phase import is_born as _is_born`` and then calls
    ``_is_born()``. Matching the called name against the accessor list misses
    it entirely -- and the hand-authored census had that site right. Resolve
    the alias instead of matching the surface spelling.

    `resolve` and `is_born` are ordinary words, so a bare name only counts in
    a file that actually imports birth_phase.
    """
    # Returns (from-import accessor names incl. aliases, module alias names).
    # Kept separate on purpose: a bare call like `resolve()` counts only when
    # that NAME was from-imported from birth_phase, and an attribute call like
    # `x.resolve()` counts only when `x` IS the birth_phase module alias.
    # Gate round 20's fix for the daemon's import form briefly made every
    # `Path(...).resolve()` in any importing file a "birth anchor reader" --
    # over-inclusion is the safe direction for a census, but 20 false readers
    # in the daemon is not a census, it is noise wearing one's clothes.
    local: set[str] = set()
    module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module \
                and "birth_phase" in node.module:
            for a in node.names:
                if a.name in BIRTH_ACCESSORS:
                    local.add(a.asname or a.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            # Gate round 20: `from core.memory import birth_phase` -- the form
            # the daemon itself uses (maez_daemon.py:4594 calls
            # birth_phase.is_born()). The first version only matched
            # birth_phase in the MODULE path, so the daemon's own reads were
            # invisible to the census.
            for a in node.names:
                if a.name == "birth_phase" or "birth_phase" in a.name:
                    module_aliases.add(a.asname or a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if "birth_phase" in a.name:
                    module_aliases.add(a.asname or a.name.split(".")[-1])
    return local, module_aliases


def scan_file(path: Path, rel: str) -> tuple[list[str], list[str], list[str]]:
    """Return (phase_writers, birth_readers, phase_readers) for one file."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except (SyntaxError, OSError) as exc:
        # Gate round 20: a file that cannot be parsed used to vanish as an
        # empty result -- indistinguishable from a file with no hits. Absent
        # evidence is not evidence of absence.
        raise CensusScanError(f"{rel}: {type(exc).__name__}: {exc}") from exc

    spans = _qualname_index(tree)

    # Docstrings mention these column names constantly -- prose about the
    # census is not a census hit. Collect every docstring node so they can be
    # skipped by identity.
    docstrings: set[int] = set()
    for holder in ast.walk(tree):
        if isinstance(holder, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef)):
            body = getattr(holder, "body", None)
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))

    parents: dict = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node

    from_import_names, module_alias_names = _birth_accessor_names(tree)

    writers: set[str] = set()
    birth: set[str] = set()
    readers: set[str] = set()

    def label(line: int) -> str:
        qual = _qualname_at(spans, line)
        return f"{rel}::{qual}" if qual else f"{rel}::@{line}"

    for node in ast.walk(tree):
        # keyword argument: f(memory_phase=...)  /  def f(memory_phase=...)
        if isinstance(node, ast.keyword) and node.arg == PHASE_KEY:
            writers.add(label(node.value.lineno))
        elif isinstance(node, ast.arg) and node.arg == PHASE_KEY:
            writers.add(label(node.lineno))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            text = node.value
            if text == PHASE_KEY:
                if _is_phase_write(node, parents):
                    writers.add(label(node.lineno))
                else:
                    readers.add(label(node.lineno))
            elif PHASE_KEY in text:
                low = text.lower()
                if any(m in low for m in _SQL_WRITE_MARKERS):
                    writers.add(label(node.lineno))
                else:
                    readers.add(label(node.lineno))
            if BIRTH_KEY in text:
                birth.add(label(node.lineno))
        # a def or attribute literally named birth_event_turn_id is a reader
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == BIRTH_KEY:
            birth.add(label(node.lineno))
        elif isinstance(node, ast.Attribute) and node.attr == BIRTH_KEY:
            birth.add(label(node.lineno))
        # indirect read: a call to the birth_phase accessor surface
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in from_import_names:
                birth.add(label(node.lineno))
            elif isinstance(fn, ast.Attribute) \
                    and fn.attr in BIRTH_ACCESSORS \
                    and isinstance(fn.value, ast.Name) \
                    and fn.value.id in module_alias_names:
                birth.add(label(node.lineno))

    return sorted(writers), sorted(birth), sorted(readers)


def census(repo: Path) -> dict:
    writers: set[str] = set()
    birth: set[str] = set()
    readers: set[str] = set()
    unscannable: list[str] = []
    for root in WALK_ROOTS:
        base = repo / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel_path = path.relative_to(repo)
            if EXCLUDED_PARTS & set(rel_path.parts):
                continue
            if str(rel_path) == SELF_PATH:
                continue
            try:
                w, b, r = scan_file(path, str(rel_path))
            except CensusScanError as exc:
                unscannable.append(str(exc))
                continue
            writers.update(w)
            birth.update(b)
            readers.update(r)
    return {
        "_comment": "DERIVED BY EXECUTION, not authored. Regenerate with "
                    "`python3 -m core.memory.s1_census --repo . --emit`.",
        "_interpreter": sys.version.split()[0],
        "unscannable": sorted(unscannable),
        "memory_phase_writers": sorted(writers),
        "birth_meta_readers": sorted(birth),
        "readers_of_memory_phase_values": sorted(readers),
    }


def diff(observed: dict, expected: dict) -> list[str]:
    problems: list[str] = []
    for entry in observed.get("unscannable", []):
        problems.append(f"UNSCANNABLE {entry}")
    for key in ("memory_phase_writers", "birth_meta_readers",
                "readers_of_memory_phase_values"):
        got = set(observed.get(key, []))
        want = set(expected.get(key, []))
        for entry in sorted(got - want):
            problems.append(f"UNEXPECTED  {key}: {entry}")
        for entry in sorted(want - got):
            problems.append(f"MISSING     {key}: {entry}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--expected", type=Path)
    ap.add_argument("--emit", action="store_true",
                    help="print the observed census as JSON and exit 0")
    args = ap.parse_args(argv)

    repo = args.repo.resolve()
    observed = census(repo)

    if args.emit or not args.expected:
        print(json.dumps(observed, indent=1))
        return 0

    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    problems = diff(observed, expected)
    if not problems:
        n = sum(len(observed[k]) for k in
                ("memory_phase_writers", "birth_meta_readers",
                 "readers_of_memory_phase_values"))
        print(f"census CLEAN — {n} constructs match {args.expected}")
        return 0

    print(f"census FAILED — {len(problems)} asymmetric difference(s) "
          f"against {args.expected}:")
    for line in problems:
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
