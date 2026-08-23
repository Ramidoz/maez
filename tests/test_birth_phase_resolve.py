# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""T1 — the resolution table, latch-independent cells (S1 protocol §2, §9, §10).

Scope is set by §12.13 as ruled: the latch-dependent branches are blocked
until the production writer topology is decided, so this covers the cells
that classify from the LEDGER alone — 1, 3, 5, 7, 9, 11, 15 — plus the
dormancy property that T5's discriminator rests on.

The contract, pinned in §9 and not mine to move:

    core.memory.birth_phase.resolve() -> PhaseResult(phase, reason)
    phase  in {'gestation','lived','unknown'}
    reason in the frozen twelve

And the property the whole slice exists to make true: with
MAEZ_S1_PHASE_TRUTH unset, the pre-S1 surface must behave EXACTLY as it did
before — `current_phase()` answers 'gestation' for every unreadable or
half-built ledger, which is the defect S1 fixes and the behaviour flags-off
must preserve.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MIGRATIONS = REPO / "core" / "ledger" / "migrations"


def _fixture(kind: str, root: Path) -> Path:
    """Build one T1 fixture. Names follow the protocol's F-* vocabulary."""
    db = root / f"{kind}.db"
    if kind == "F-A":                      # absent: never created
        return db
    if kind == "F-E":                      # 0-byte
        db.write_bytes(b"")
        return db
    if kind == "F-P":                      # partial: 0001..0002 only
        conn = sqlite3.connect(db)
        for name in ("0001_init.sql", "0002_triggers.sql"):
            conn.executescript((MIGRATIONS / name).read_text())
        conn.commit(); conn.close()
        return db
    # everything below starts from a full migration
    full = root / "_full.db"
    if not full.exists():
        sys.path.insert(0, str(REPO))
        from core.ledger.migrate import run
        run(str(full))
    if kind == "F-G":
        shutil.copy2(full, db)
        return db
    if kind == "F-D1":                     # turns table dropped
        shutil.copy2(full, db)
        c = sqlite3.connect(db)
        c.executescript("PRAGMA foreign_keys=OFF; DROP TABLE turns;")
        c.close()
        return db
    if kind == "F-D2":                     # bytes corrupted
        shutil.copy2(full, db)
        with open(db, "r+b") as fh:
            fh.seek(4096); fh.write(b"\xff" * 16)
        return db
    if kind == "F-X":                      # anchor pointer to no such turn
        shutil.copy2(full, db)
        c = sqlite3.connect(db)
        c.execute("INSERT OR REPLACE INTO meta (key, value) VALUES "
                  "('birth_event_turn_id', 'no-such-turn')")
        c.commit(); c.close()
        return db
    raise ValueError(kind)


def _resolve(db: Path, *, enabled: bool):
    """Run resolve() in a FRESH process — §0 requires no cached state."""
    env = dict(os.environ)
    env["MAEZ_LEDGER_DB_PATH"] = str(db)
    env.pop("MAEZ_S1_PHASE_TRUTH", None)
    if enabled:
        env["MAEZ_S1_PHASE_TRUTH"] = "1"
    r = subprocess.run(
        [sys.executable, "-c",
         "from core.memory.birth_phase import resolve; "
         "r = resolve(); print(r.phase, r.reason)"],
        capture_output=True, text=True, cwd=str(REPO), env=env)
    if r.returncode != 0:
        return ("ERROR", r.stderr.strip().splitlines()[-1] if r.stderr else "?")
    return tuple(r.stdout.strip().split())


def _legacy_phase(db: Path):
    env = dict(os.environ)
    env["MAEZ_LEDGER_DB_PATH"] = str(db)
    env.pop("MAEZ_S1_PHASE_TRUTH", None)
    r = subprocess.run(
        [sys.executable, "-c",
         "from core.memory.birth_phase import current_phase; print(current_phase())"],
        capture_output=True, text=True, cwd=str(REPO), env=env)
    return r.stdout.strip()


class T1LatchIndependentCells(unittest.TestCase):
    """§10's pinned (phase, reason) for every cell that needs no latch."""

    CELLS = [
        ("1",  "F-A",  ("gestation", "absent")),
        ("3",  "F-E",  ("gestation", "uninitialized_empty")),
        ("5",  "F-P",  ("unknown",   "structural")),
        ("7",  "F-D1", ("unknown",   "structural")),
        ("9",  "F-D2", ("unknown",   "corrupt")),
        ("11", "F-G",  ("gestation", "meta_absent")),
        ("15", "F-X",  ("unknown",   "join_failed")),
    ]

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="t1_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_every_latch_independent_cell(self):
        failures = []
        for cell, kind, want in self.CELLS:
            db = _fixture(kind, self.root)
            got = _resolve(db, enabled=True)
            if got != want:
                failures.append(f"cell {cell} ({kind}): want {want}, got {got}")
        self.assertEqual(failures, [], "\n" + "\n".join(failures))


class Dormancy(unittest.TestCase):
    """The property T5's discriminator measures.

    Flags off, the pre-S1 surface must be unchanged: current_phase() says
    'gestation' for absent, empty, partial and corrupt ledgers alike. That is
    the A6 defect S1 exists to fix, and preserving it while dormant is what
    makes the guard's presence detectable.
    """

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="t1d_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_flags_off_preserves_legacy_gestation_everywhere(self):
        for kind in ("F-A", "F-E", "F-P", "F-D2", "F-G"):
            db = _fixture(kind, self.root)
            self.assertEqual(
                _legacy_phase(db), "gestation",
                f"{kind}: flags-off behaviour changed; T5's baseline and its "
                f"discriminator both depend on this staying 'gestation'")

    def test_the_guard_flips_the_partial_fixture(self):
        """The discriminator itself: same fixture, flag on, different answer."""
        db = _fixture("F-P", self.root)
        self.assertEqual(_legacy_phase(db), "gestation")
        self.assertEqual(_resolve(db, enabled=True), ("unknown", "structural"),
                         "with the flag ON the partial ledger must stop "
                         "claiming gestation — this is the whole slice")

    def test_resolve_is_dormant_when_the_flag_is_unset(self):
        db = _fixture("F-P", self.root)
        phase, _reason = _resolve(db, enabled=False)
        self.assertEqual(phase, "gestation",
                         "dormant resolve() must answer as the pre-S1 code "
                         "did, not as S1 will")


class PinnedShape(unittest.TestCase):

    def test_reason_vocabulary_is_exactly_the_frozen_twelve(self):
        sys.path.insert(0, str(REPO))
        from core.memory.birth_phase import REASONS
        self.assertEqual(sorted(REASONS), sorted([
            "absent", "uninitialized_empty", "structural", "corrupt",
            "meta_absent", "joined", "join_failed", "latch_conflict",
            "latch_torn", "latch_foreign", "rewind", "io_error"]))

    def test_phase_result_is_a_two_field_namedtuple(self):
        sys.path.insert(0, str(REPO))
        from core.memory.birth_phase import PhaseResult
        r = PhaseResult("gestation", "absent")
        self.assertEqual((r.phase, r.reason), ("gestation", "absent"))
        self.assertEqual(len(r), 2)

    def test_latch_dependent_paths_are_fail_closed_not_missing(self):
        """§12.13 blocks the latch. A stub that silently returns something
        plausible would be worse than one that refuses."""
        sys.path.insert(0, str(REPO))
        from core.memory import birth_phase
        self.assertTrue(hasattr(birth_phase, "LATCH_BLOCKED_REASON"),
                        "the blocked seam must be named, not absent")


if __name__ == "__main__":
    unittest.main()
