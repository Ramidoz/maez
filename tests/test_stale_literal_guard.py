# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Stale-literal guard — Commit 7b of the 2026-04-23 audit repair pass.

Invariant: no live runtime Python file under core/ skills/ daemon/ cli/
carries a bare string literal of a stale model name or a retired
service name as a live fallback. Specifically bans:

  - "gemma-4-26b"
  - "gemma4:26b"
  - "llama-server-vision"    (and "llama-server-vision.service")

Exemptions:

  1. Comments (lines starting with `#` after stripping leading
     whitespace, or lines whose only non-comment content precedes a
     `#` marker that introduces the literal). Documentation in code
     comments is allowed.
  2. Legacy / retired / disabled-feature contexts: a literal on a
     runtime-code line is allowed IF the same line OR a comment in
     a 3-line-above window contains one of: `legacy`, `retired`,
     `disabled feature`, `LEGACY-LABEL`. This is what lets
     core/actions/action_engine.py and core/infra/capability_
     registry.py keep their defensive guards without the test
     false-positiving on them.
  3. Explicit file allowlist — modules intentionally retained under
     this commit's scope but deliberately not yet cleaned:
       - core/routing/fast_backend_local.py (Ollama-gemma backend,
         retire-or-retune decision deferred)
       - scripts/judge_bench/test_set.json (fabrication corpus;
         stale strings are the test fixtures)
  4. Test fixtures under tests/ are ignored entirely — those files
     legitimately hold historical strings to exercise regression
     detectors.
  5. Docs / config / markdown outside runtime Python are ignored.
     Separate concerns; a sweep of those can be its own pass.

If this test starts failing on a new file, the right fix is almost
always: either (a) replace the literal with a read from
core.routing.model_config, or (b) add a nearby comment marking the
entry as a legacy covenant guard with the word "legacy" or
"retired." Do NOT just add the file to the allowlist — that
smuggles the regression back.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

STALE_LITERALS = (
    "gemma-4-26b",
    "gemma4:26b",
    "llama-server-vision",
    "llama-server-vision.service",
)

# Files where stale literals are deliberately retained.
# Path is relative to repo root, Unix separators.
FILE_ALLOWLIST = frozenset({
    "core/routing/fast_backend_local.py",
    "core/routing/llm_client.py",    # historical comments + __main__ test fixture
})

# Dir prefixes skipped entirely (separate from the allowlist above).
DIR_SKIP_PREFIXES = (
    "tests/",        # test fixtures allowed to hold historical strings
)

# Words that, if present on the same line or within the preamble,
# exempt an otherwise-offending literal. Case-insensitive match.
LEGACY_MARKERS = (
    "legacy",
    "retired",
    "disabled feature",
    "operationally disabled",  # matches capability_registry phrasing
    "deliberately off",
)

# How many non-blank lines to look BACK when checking for a legacy
# marker in a comment preamble. Widened from 3 → 6 so comments that
# live a few lines above a dict literal (e.g. module-level docstrings
# preceding `_DISABLED_FEATURES = {"llama-server-vision": ...}`) still
# exempt the literal on that dict key line.
PREAMBLE_LOOKBACK = 6


def _iter_runtime_python_files() -> list[Path]:
    roots = ("core", "skills", "daemon", "cli")
    files: list[Path] = []
    for r in roots:
        root = _REPO / r
        if not root.exists():
            continue
        files.extend(root.rglob("*.py"))
    return files


def _is_inside_main_block(lines: list[str], i: int) -> bool:
    """Return True if lines[i] is inside an `if __name__ == "__main__":`
    block. Test code embedded in module __main__ sections
    legitimately uses historical model literals as fixtures — the
    identity-ledger brain-swap detector is the reference case.

    Simple shape: if any line ABOVE lines[i] is exactly
    `if __name__ == "__main__":` at column 0, AND lines[i] has
    non-zero leading whitespace, treat as inside __main__.
    `if __name__ == "__main__":` is Python convention for "the
    rest of the module is CLI / self-test scaffolding" and is
    almost always the final top-level construct.
    """
    import re as _re
    if not lines[i].startswith(" ") and not lines[i].startswith("\t"):
        return False
    guard_re = _re.compile(
        r'^if __name__\s*==\s*["\']__main__["\']\s*:'
    )
    for j in range(i):
        if guard_re.match(lines[j]):
            return True
    return False


def _is_exempt_line(lines: list[str], i: int) -> bool:
    """Return True if the literal on lines[i] should be exempt.

    Exempt conditions:
      - The line is a comment (starts with '#' after strip).
      - The line is inside a triple-quoted docstring (cheap heuristic:
        check whether prior non-blank line ended inside a `\"\"\"`).
      - The line's end-of-line comment mentions a legacy marker.
      - Any of the previous PREAMBLE_LOOKBACK non-blank lines is a
        comment OR string-literal that mentions a legacy marker
        (covers comments immediately above dict literals as well as
        docstrings of the enclosing construct).
      - The line is inside an `if __name__ == "__main__":` block —
        test fixtures embedded in module __main__ sections.
    """
    line = lines[i]
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return True
    # End-of-line comment legacy marker on same line.
    if "#" in line:
        tail = line[line.index("#"):].lower()
        if any(m in tail for m in LEGACY_MARKERS):
            return True
    # Preamble check (comments OR string content mentioning a marker).
    look = 0
    j = i - 1
    while j >= 0 and look < PREAMBLE_LOOKBACK:
        prev = lines[j].strip()
        if not prev:
            j -= 1
            continue
        look += 1
        if any(m in prev.lower() for m in LEGACY_MARKERS):
            return True
        j -= 1
    # Docstring heuristic: if the line is inside a triple-quoted
    # block, treat as exempt. Walk backwards counting unclosed
    # triple-quote markers.
    joined = "".join(lines[:i + 1])
    if joined.count('"""') % 2 == 1 or joined.count("'''") % 2 == 1:
        return True
    # __main__ test-fixture exemption.
    if _is_inside_main_block(lines, i):
        return True
    return False


class StaleLiteralGuard(unittest.TestCase):
    """Fail fast on any new stale-model / retired-service literal
    landing in runtime code without a legacy/retired comment
    nearby."""

    def test_no_bare_stale_literals_in_runtime_python(self):
        offenders: list[str] = []
        for fpath in _iter_runtime_python_files():
            rel = fpath.relative_to(_REPO).as_posix()
            if rel in FILE_ALLOWLIST:
                continue
            if any(rel.startswith(p) for p in DIR_SKIP_PREFIXES):
                continue
            try:
                content = fpath.read_text()
            except Exception:
                continue
            # Quick short-circuit: does the file contain any stale
            # literal at all?
            if not any(lit in content for lit in STALE_LITERALS):
                continue
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if not any(lit in line for lit in STALE_LITERALS):
                    continue
                # Identify which literal(s) hit this line for the
                # error message.
                hits = [lit for lit in STALE_LITERALS if lit in line]
                if _is_exempt_line(lines, i):
                    continue
                offenders.append(
                    f"{rel}:{i + 1}: {line.rstrip()}  "
                    f"(stale literal(s): {', '.join(hits)})"
                )
        self.assertFalse(
            offenders,
            "Stale model/service literal on a live runtime line "
            "without a nearby 'legacy' / 'retired' / 'disabled "
            "feature' marker. Either replace with a read from "
            "core.routing.model_config, or tag the line as a "
            "legacy covenant guard:\n\n" + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
