# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Every live store is backed up, or explicitly and reasonedly skipped.

2026-08-22. `tests/test_backup_manifest_coverage.py` checks that a handful of
named stores are PRESENT in the manifest. That is an allowlist spot-check, and
it cannot detect the failure that actually happened: a new store appearing and
nobody adding it. `memory/proprioception.db` — 104,943 rows, written minutes
before the audit — was in neither the entries nor the skip list, and every
backup reported success.

This test inverts the guard. It walks the live tree and asserts an exhaustive
partition: every SQLite file is covered by an entry, covered by a backed-up
parent directory, or named in `intentionally_skipped` with a reason. A new
store is a test failure until somebody decides which it is.

The decision is cheap. Losing the record is not: `memory/` exists on exactly
one disk, and `.gitignore` keeps it out of the remote.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "scripts" / "backup" / "backup_state_manifest.json"
SQLITE_SUFFIXES = (".db", ".sqlite3", ".sqlite")

# Roots that hold durable state. Scanned recursively.
STATE_ROOTS = ("memory",)

# Sidecars are not independent state; they belong to their main file.
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _covered_sets(manifest: dict) -> tuple[set[Path], list[Path], list[Path]]:
    files, dirs = set(), []
    for entry in manifest["entries"]:
        path = Path(entry["path"])
        (dirs.append(path) if entry.get("type") == "directory" else files.add(path))
    skips = [Path(s["path"]) for s in manifest["intentionally_skipped"]]
    return files, dirs, skips


def _live_stores() -> list[Path]:
    out = []
    for root in STATE_ROOTS:
        base = REPO / root
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.is_symlink():
                continue
            if p.name.endswith(SIDECAR_SUFFIXES):
                continue
            if p.suffix in SQLITE_SUFFIXES:
                out.append(p.relative_to(REPO))
    return out


def _is_covered(rel: Path, files: set[Path], dirs: list[Path],
                skips: list[Path]) -> bool:
    if rel in files:
        return True
    if any(d == rel or d in rel.parents for d in dirs):
        return True
    for s in skips:
        # A trailing-slash skip covers a whole subtree.
        if s == rel or s in rel.parents or str(s).endswith("/") and \
                str(rel).startswith(str(s)):
            return True
    return False


class ExhaustiveBackupCoverage(unittest.TestCase):

    def test_every_live_store_is_covered_or_skipped(self):
        manifest = _load()
        files, dirs, skips = _covered_sets(manifest)
        uncovered = [
            str(rel) for rel in _live_stores()
            if not _is_covered(rel, files, dirs, skips)
        ]
        self.assertEqual(
            uncovered, [],
            "These live stores are in neither the backup entries nor the "
            "intentionally_skipped list, so a backup would silently omit "
            "them and still report success. Add each one to "
            "scripts/backup/backup_state_manifest.json — as an entry if it "
            "is state worth keeping, or as a skip WITH A REASON if it is "
            f"not:\n  " + "\n  ".join(uncovered),
        )

    def test_every_skip_carries_a_reason(self):
        for skip in _load()["intentionally_skipped"]:
            self.assertTrue(
                (skip.get("reason") or "").strip(),
                f"skip entry {skip.get('path')!r} has no reason; a silent "
                "skip is indistinguishable from an oversight",
            )
            self.assertTrue((skip.get("class") or "").strip(),
                            f"skip entry {skip.get('path')!r} has no class")

    def test_no_path_is_both_backed_up_and_skipped(self):
        manifest = _load()
        files, _dirs, skips = _covered_sets(manifest)
        both = sorted(str(p) for p in (files & set(skips)))
        self.assertEqual(both, [], f"contradictory manifest entries: {both}")

    def test_the_stores_the_2026_08_22_audit_found_uncovered_stay_covered(self):
        """Named regression. These four were live and silently omitted."""
        manifest = _load()
        files, dirs, skips = _covered_sets(manifest)
        for name in ("memory/proprioception.db",
                     "memory/conversation_turn_seq.db",
                     "memory/scar_tissue.db",
                     "memory/unseal_receipts.db"):
            self.assertTrue(
                _is_covered(Path(name), files, dirs, skips),
                f"{name} was uncovered on 2026-08-22 and must stay covered",
            )


if __name__ == "__main__":
    unittest.main()
