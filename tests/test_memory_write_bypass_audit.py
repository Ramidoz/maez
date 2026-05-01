# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5x.D.C — static-audit guard against direct writes to Maez's
lived Chroma collections.

The 5x arc installed a provenance contract on every memory write
that goes through ``MemoryManager.store``, ``store_telegram``, or
``store_core``:

  - 5x.A: ProvenanceSource / TrustTier schema
  - 5x.B: tagged hot-path + external/system call sites
  - 5x.C: surfacing of trust_tier="untrusted" in recall
  - 5x.D.A: promotion gate + ancestor lineage
  - 5x.D.B1: explicit raw-promotion wiring
  - 5x.E: daily consolidation lineage / filtering

ALL of those run inside the public ``MemoryManager.store_*``
methods. Any production code that calls ``<mm>.raw.add(...)``,
``<mm>.daily.add(...)``, or ``<mm>.core.add(...)`` directly bypasses
the entire arc — provenance is silently dropped, the gate doesn't
fire, the consolidation filter is irrelevant.

This static audit fails CI if any production file (outside the
narrow allowlist below) writes directly to a lived Chroma
collection. It is the seatbelt that keeps a future agent — or a
careless refactor — from re-opening the laundering surface 5x just
spent eight commits closing.

Scope: ``add`` and ``upsert`` against a ``.raw./.daily./.core.``
attribute. The pattern is intentionally narrow so it does NOT
false-positive on the public-user separate Chroma stores
(``user_conversations`` / ``user_profiles``) which legitimately use
``self.profiles.upsert`` / ``self.conversations.upsert`` — those
don't write to lived memory.

Out of scope (not audited here):
  - ``.update(`` / ``.modify(`` / ``.delete(`` — these mutate or
    remove existing rows rather than introducing new memory; the
    legitimate uses (``tag_integrity``, ``migrate_wings``) live
    inside ``MemoryManager`` and a future audit slice can extend
    coverage if needed.
  - Direct ``chromadb.PersistentClient(<some-path>)`` usage —
    distinguishing lived-memory paths from isolated harness paths
    requires path resolution that's not reliably static-decidable.
    Belongs in a separate slice if needed.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Match `<obj>.raw.add(`, `<obj>.daily.add(`, `<obj>.core.add(`, and
# their `upsert` variants. Receiver `<obj>` is implicitly anything
# matching r'\.' before the collection attr. The strict attr names
# (raw / daily / core) keep this off the public-user Chroma stores
# whose collections are accessed via `.profiles` / `.conversations`.
_BYPASS_PATTERNS = (
    (re.compile(r"\.raw\.(?:add|upsert)\("),    "raw"),
    (re.compile(r"\.daily\.(?:add|upsert)\("),  "daily"),
    (re.compile(r"\.core\.(?:add|upsert)\("),   "core"),
)

# Production paths approved to write directly to Maez lived Chroma
# collections. Every entry MUST have a recorded reason in this file
# (NOT just a code comment) so future agents reading this allowlist
# understand why each escape hatch is safe.
#
# Adding a new entry to this allowlist requires:
#   1. A clear case for why the write must NOT go through the
#      MemoryManager.store_* chokepoints (e.g. isolated test harness).
#   2. A defense against the path becoming a production-data write
#      surface (e.g. explicit BASE_DB monkeypatch, separate Chroma DB,
#      etc.).
#   3. The reason recorded here, with the date and slice it landed in.
_ALLOWLIST: dict[str, str] = {
    # 5x.A onward: the chokepoint itself. Every store_* method here
    # runs the provenance schema before calling self.<collection>.add.
    "memory/memory_manager.py":
        "MemoryManager internals — chokepoint where the provenance "
        "schema, promotion gate, and consolidation filter all run.",

    # 5x.B Pass 2a verification (b8a5db4): isolated benchmark harness.
    # IsolatedMemoryHarness monkeypatches memory.memory_manager.BASE_DB
    # to a tmpdir before MemoryManager instantiation, so writes never
    # touch production lived memory. Re-verified during 5x.D.C audit.
    "core/eval/longmemeval.py":
        "Benchmark-only writes wrapped in IsolatedMemoryHarness which "
        "monkeypatches BASE_DB to tmpdir; never touches production.",
}

# Directories whose .py files are scanned. Production-only paths;
# `tests/` is allowlisted broadly because test fixtures legitimately
# reference these patterns (in docstrings or fake-collection method
# names) and adding finer rules to allow that would just create
# regex churn without security value — the threat is production
# code laundering writes around the gate, not test code.
_PRODUCTION_DIRS = (
    "core",
    "skills",
    "daemon",
    "scripts",
    "cli",
    "hardware",
    "training",
    "memory",
)


def _iter_production_files():
    """Yield every .py file under the production directories above,
    excluding the allowlist."""
    for d in _PRODUCTION_DIRS:
        root = _REPO_ROOT / d
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            rel = path.relative_to(_REPO_ROOT).as_posix()
            if rel in _ALLOWLIST:
                continue
            yield path, rel


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return a list of ``(line_number, collection_name, line_text)``
    matches for any bypass pattern in ``path``."""
    matches: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return matches
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern, collection in _BYPASS_PATTERNS:
            if pattern.search(line):
                matches.append((lineno, collection, line.strip()))
                break
    return matches


class MemoryWriteBypassAuditTests(unittest.TestCase):
    def test_no_production_file_writes_directly_to_lived_chroma(self):
        """The provenance contract is enforced inside
        MemoryManager.store, store_telegram, store_core. Any
        production file that writes directly to a lived Chroma
        collection (raw / daily / core) bypasses the entire 5x arc:
        the schema (5x.A), tagging (5x.B), surfacing (5x.C), gate
        (5x.D.A/D.B1), and consolidation filter (5x.E) all become
        irrelevant. This test is the seatbelt."""
        bypasses: list[str] = []
        for path, rel in _iter_production_files():
            for lineno, collection, line in _scan_file(path):
                bypasses.append(
                    f"  {rel}:{lineno}  ({collection}.add/upsert)\n"
                    f"    {line}"
                )
        if bypasses:
            allowlist_lines = "\n".join(
                f"  - {p}: {reason}"
                for p, reason in _ALLOWLIST.items()
            )
            self.fail(
                "5x.D.C bypass guard tripped: a production file is "
                "writing directly to a lived Chroma collection "
                "(raw/daily/core), bypassing the MemoryManager "
                "provenance chokepoint. Use MemoryManager.store(...), "
                "store_telegram(...), or store_core(...) so the 5x "
                "schema, gates, and filters apply. If this write is "
                "genuinely safe (e.g. isolated benchmark store), add "
                "the file to _ALLOWLIST in this test with a recorded "
                "reason and the slice/date it landed in.\n\n"
                "Bypass(es) found:\n"
                + "\n".join(bypasses)
                + f"\n\nCurrent allowlist:\n{allowlist_lines}"
            )

    def test_allowlist_entries_actually_exist(self):
        """The allowlist is only useful if its paths still resolve.
        A renamed-or-deleted allowlist entry creates a phantom
        permission — guard by asserting every entry resolves to a
        real file."""
        for rel in _ALLOWLIST:
            self.assertTrue(
                (_REPO_ROOT / rel).exists(),
                f"_ALLOWLIST entry refers to a non-existent file: "
                f"{rel}. Either restore the file or remove the entry.",
            )

    def test_longmemeval_still_uses_isolated_memory_harness(self):
        """Bound to the longmemeval allowlist entry: re-verify the
        BASE_DB monkeypatch is still in place. If a future refactor
        of longmemeval drops IsolatedMemoryHarness, the allowlist
        entry's safety claim no longer holds and the file must be
        either re-allowlisted with a new reason or removed."""
        path = _REPO_ROOT / "core" / "eval" / "longmemeval.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn(
            "IsolatedMemoryHarness", text,
            "core/eval/longmemeval.py is allowlisted on the basis "
            "that IsolatedMemoryHarness monkeypatches BASE_DB to a "
            "tmpdir so writes never touch production. That class "
            "name is no longer present — the allowlist's safety "
            "claim is broken. Either restore the harness or remove "
            "the longmemeval entry from _ALLOWLIST.",
        )
        self.assertIn(
            "BASE_DB", text,
            "core/eval/longmemeval.py no longer references BASE_DB; "
            "the monkeypatch defense underlying its allowlist entry "
            "may be gone.",
        )


if __name__ == "__main__":
    unittest.main()
