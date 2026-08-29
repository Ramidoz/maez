# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""`self_dev.propose_tests` — bounded self-development evidence gathering.

Owner-authorized 2026-08-28 (D1 seam 2).

WHAT THIS IS. A NON-MUTATING action. It reads real repository material,
ranks where behavioural coverage is genuinely thin, and hands that
evidence back to cognition. It writes nothing, applies nothing, and
proposes no patch.

WHY THE SUBSTRATE RANKS AND MAEZ DECIDES. The builder must not do the
investigating and hand Maez a conclusion. So the ranking here is
MECHANICAL — public functions that no test calls by name — and it is
deliberately not a judgement about which test is worth writing. Maez
reads the real source and the real test references and decides that.
A candidate list is evidence; it is not an answer.

WHY EVIDENCE REFS EXIST. Anything Maez later reasons about must be
traceable to the exact bytes inspected, so every excerpt carries its
path, line span and sha256. Without that, a candidate test could not be
checked against what was actually read.

LANE. Lane 0: this action mutates nothing. It is NOT Lane 2 merely
because a later consultation may spend quota — cost lives at the SOURCE
boundary, not in an action lane. It is deliberately NOT added to
_READ_ONLY_ACTIONS either: it can lead to paid egress, and that S7
invocation-gate list means something narrower.
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Bounded by construction — never dump the repository into cognition.
MAX_CANDIDATES = 6
MAX_SOURCE_CHARS = 6000
MAX_TEST_EXCERPTS = 3
MAX_EXCERPT_CHARS = 1200

#: Where self-development may look. Narrow on purpose.
SEARCH_ROOTS = ("core/cognition", "core/infra", "core/routing")


@dataclass(frozen=True)
class EvidenceRef:
    """One inspected artefact, traceable to the exact bytes read."""

    path: str
    start_line: int
    end_line: int
    sha256: str
    kind: str  # "module_source" | "test_reference" | "coverage_scan"

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "lines": f"{self.start_line}-{self.end_line}",
            "sha256": self.sha256,
            "kind": self.kind,
        }


@dataclass
class TestGapEvidence:
    """Real material for reasoning about a missing test. Not a verdict."""

    module: str
    module_source: str
    public_functions: list
    uncovered_functions: list
    existing_test_files: list
    test_excerpts: list = field(default_factory=list)
    candidates_considered: list = field(default_factory=list)
    refs: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "module": self.module,
            "public_functions": self.public_functions,
            "uncovered_functions": self.uncovered_functions,
            "existing_test_files": self.existing_test_files,
            "candidates_considered": self.candidates_considered,
            "evidence_refs": [r.as_dict() for r in self.refs],
        }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _public_functions(source: str) -> list:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [
        n.name for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not n.name.startswith("_")
    ]


def _test_corpus(repo: Path) -> tuple:
    blob, files = "", []
    for p in sorted((repo / "tests").glob("test_*.py")):
        try:
            blob += p.read_text(encoding="utf-8")
            files.append(str(p.relative_to(repo)))
        except OSError:
            continue
    return blob, files


def _called_by_name(blob: str, name: str) -> bool:
    """A name is covered only if a test CALLS it.

    Substring matching would count a name appearing inside an unrelated
    string literal as coverage — which is exactly how this module looked
    covered when nothing exercised it.
    """
    return bool(re.search(rf"\b{re.escape(name)}\s*\(", blob))


def rank_thin_coverage(repo: Path, test_blob: str) -> list:
    """Mechanical ranking. NOT a judgement about what is worth testing."""
    rows = []
    for root in SEARCH_ROOTS:
        base = repo / root
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in sorted(filenames):
                if not fn.endswith(".py") or fn == "__init__.py":
                    continue
                rel = str(Path(dirpath, fn).relative_to(repo))
                try:
                    src = (repo / rel).read_text(encoding="utf-8")
                except OSError:
                    continue
                loc = len(src.splitlines())
                if not (40 <= loc <= 320):
                    continue
                funcs = _public_functions(src)
                if len(funcs) < 2:
                    continue
                uncovered = [f for f in funcs if not _called_by_name(test_blob, f)]
                if uncovered:
                    rows.append({
                        "module": rel,
                        "loc": loc,
                        "public_functions": funcs,
                        "uncovered_functions": uncovered,
                    })
    rows.sort(key=lambda r: (-len(r["uncovered_functions"]), r["loc"]))
    return rows[:MAX_CANDIDATES]


def gather(module: str | None = None, *, repo: Path | None = None) -> TestGapEvidence:
    """Collect bounded, traceable evidence about thin test coverage."""
    repo = repo or Path(__file__).resolve().parent.parent.parent
    test_blob, test_files = _test_corpus(repo)
    candidates = rank_thin_coverage(repo, test_blob)
    if not candidates:
        raise RuntimeError("no thin-coverage candidate found in the search roots")

    chosen = None
    if module:
        chosen = next((c for c in candidates if c["module"] == module), None)
        if chosen is None:
            raise ValueError(
                f"{module!r} is not among the ranked candidates; "
                "self-development inspects the scanned region only"
            )
    else:
        chosen = candidates[0]

    rel = chosen["module"]
    src = (repo / rel).read_text(encoding="utf-8")
    truncated = src[:MAX_SOURCE_CHARS]
    refs = [EvidenceRef(
        path=rel, start_line=1, end_line=len(truncated.splitlines()),
        sha256=_sha(truncated), kind="module_source",
    )]

    # Real existing-test material, so the candidate can be judged against
    # how this repository actually writes tests.
    excerpts, named_in = [], []
    stem = Path(rel).stem
    for tf in test_files:
        try:
            body = (repo / tf).read_text(encoding="utf-8")
        except OSError:
            continue
        if stem in body or any(f in body for f in chosen["public_functions"]):
            named_in.append(tf)
            if len(excerpts) < MAX_TEST_EXCERPTS:
                head = body[:MAX_EXCERPT_CHARS]
                excerpts.append({"path": tf, "excerpt": head})
                refs.append(EvidenceRef(
                    path=tf, start_line=1, end_line=len(head.splitlines()),
                    sha256=_sha(head), kind="test_reference",
                ))

    refs.append(EvidenceRef(
        path="|".join(SEARCH_ROOTS), start_line=0, end_line=0,
        sha256=_sha(repr(candidates)), kind="coverage_scan",
    ))

    return TestGapEvidence(
        module=rel,
        module_source=truncated,
        public_functions=chosen["public_functions"],
        uncovered_functions=chosen["uncovered_functions"],
        existing_test_files=named_in,
        test_excerpts=excerpts,
        candidates_considered=[
            {"module": c["module"], "uncovered": c["uncovered_functions"]}
            for c in candidates
        ],
        refs=refs,
    )
