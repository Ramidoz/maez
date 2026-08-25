# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Checkpoint policy — the default IS the policy, and it is WITNESSED.

Eighth council round (2026-08-24, Codex + Grok, both seats independently):
ship NO periodic checkpoint. The proposal that reached the council was
falsified by its own numbers before a seat ruled:

- With no pinning reader the WAL PLATEAUS at SQLite's autocheckpoint
  ceiling (1000 pages x page_size ~= 4.1 MB) and stays flat — measured
  over 20,000 commits. There is no unbounded growth to prevent.
- The only way the WAL grows without bound is a reader that pins the
  snapshot; measured 4.17 MB -> 727 MB over 16,000 commits. A periodic
  TRUNCATE cannot fix that case: it returns busy=1, honestly.
- TRUNCATE is not free under contention: with a write lock genuinely
  held elsewhere it consumed the owner's FULL busy_timeout (5,005 ms)
  and still returned busy. On the owner's serialized connection that is
  a stall of the life-admission rail.

So this module witnesses the CLAIM the policy rests on, rather than
adding machinery to the writer. If the default ever stops bounding the
WAL, this goes RED and the policy is re-opened.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DIR = tempfile.mkdtemp(prefix="maez_test_ckpt_policy_")

from core.ledger import migrate  # noqa: E402
from core.ledger.writer import LedgerWriter, wal_ceiling_bytes  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


def _fresh(name: str) -> str:
    base = Path(_TEST_DIR) / f"{name}_{os.urandom(4).hex()}"
    base.mkdir()
    db = str(base / "ledger.db")
    migrate.run(db)
    return db


_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}


class CheckpointPolicyTests(unittest.TestCase):
    def test_no_periodic_checkpoint_ships(self):
        """Both seats ruled: add no checkpoint behavior. A future slice
        that adds one must change this test deliberately, not by
        accident."""
        # Repo root from THIS file, never a hardcoded path: run from a
        # git worktree, an absolute path reads main's copy and passes
        # while the worktree adds a checkpoint (the recorded
        # worktree-floor confound).
        repo = Path(__file__).resolve().parents[1]
        for rel in ("core/ledger/writer.py", "core/ledger/owner.py",
                    "core/ledger/spool.py", "daemon/maez_daemon.py"):
            src = repo / rel
            self.assertNotIn(
                "wal_checkpoint", src.read_text(),
                f"{rel} must not issue checkpoints: SQLite's automatic "
                f"PASSIVE checkpointing is the policy",
            )

    def test_default_autocheckpoint_is_still_the_documented_one(self):
        db = _fresh("pragma")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = LedgerWriter(db)
            try:
                self.assertEqual(
                    w._conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0],
                    1000,
                    "the policy documents SQLite's 1000-page default; if "
                    "this changes the documented ceiling is wrong",
                )
                self.assertEqual(
                    w._conn.execute("PRAGMA journal_mode").fetchone()[0], "wal"
                )
            finally:
                w.close()

    def test_ceiling_tracks_the_connection_that_actually_checkpoints(self):
        """Third seat, executed: wal_autocheckpoint is a PER-CONNECTION
        setting, not a database property. Reading it from a fresh
        connection always reports the compile-time default — so an owner
        that disabled checkpointing (genuinely unbounded WAL) would still
        be reported as bounded. The old test asserted `== page * 1000`,
        pinning the very constant it was named for."""
        db = _fresh("ceiling")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = LedgerWriter(db)
            try:
                w._conn.execute("PRAGMA wal_autocheckpoint=0")
                self.assertEqual(
                    wal_ceiling_bytes(db, conn=w._conn), 0,
                    "checkpointing disabled on the live connection means "
                    "there IS no ceiling; reporting one is a lie",
                )
                w._conn.execute("PRAGMA wal_autocheckpoint=250")
                page = w._conn.execute("PRAGMA page_size").fetchone()[0]
                self.assertEqual(
                    wal_ceiling_bytes(db, conn=w._conn), page * 250
                )
            finally:
                w.close()

    def test_ceiling_is_unknown_for_an_unborn_or_missing_ledger(self):
        """A 0-byte ledger is not a 4 MB ceiling. The live tree is 0
        bytes today, so this is the value the cockpit actually shows."""
        base = Path(_TEST_DIR) / f"unborn_{os.urandom(4).hex()}"
        base.mkdir()
        empty = base / "ledger.db"
        empty.touch()
        self.assertEqual(wal_ceiling_bytes(str(empty)), 0)
        self.assertEqual(wal_ceiling_bytes(str(base / "absent.db")), 0)

    def test_no_ceiling_for_corrupt_or_non_wal_databases(self):
        """Codex validation, executed: a corrupt file and a
        journal_mode=delete database both answered PRAGMA page_size and
        were handed a plausible 4 MB ceiling for a WAL policy that does
        not apply to them. A fabricated number on a real-state surface
        is worse than no number."""
        base = Path(_TEST_DIR) / f"badshape_{os.urandom(4).hex()}"
        base.mkdir()
        corrupt = base / "corrupt.db"
        corrupt.write_bytes(b"definitely not sqlite" * 40)
        self.assertEqual(wal_ceiling_bytes(str(corrupt)), 0)

        rollback = base / "rollback.db"
        conn = sqlite3.connect(str(rollback))
        try:
            conn.execute("PRAGMA journal_mode=delete")
            conn.execute("CREATE TABLE t(x)")
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(
            wal_ceiling_bytes(str(rollback)), 0,
            "a rollback-journal db has no WAL ceiling to report",
        )

    def test_the_default_actually_bounds_the_wal(self):
        """F_bound, in-process: the claim the whole policy rests on."""
        db = _fresh("bound")
        wal = db + "-wal"
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = LedgerWriter(db)
            try:
                for i in range(2500):
                    w.write_turn("user_message", f"t{i} " + "x" * 200,
                                 surface="probe", **_STAMP)
                size = os.path.getsize(wal)
            finally:
                w.close()
        ceiling = wal_ceiling_bytes(db)
        self.assertLessEqual(
            size, ceiling * 2,
            f"WAL {size} exceeded twice the autocheckpoint ceiling "
            f"{ceiling} with no pinning reader — the default no longer "
            f"bounds the WAL and the checkpoint policy must be re-opened",
        )

    def test_a_pinning_reader_is_what_breaks_the_bound(self):
        """The real hazard, pinned as a fact: this is why the cockpit
        surfaces a WAL excursion instead of the writer truncating."""
        db = _fresh("pinned")
        wal = db + "-wal"
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = LedgerWriter(db)
            try:
                for i in range(500):
                    w.write_turn("user_message", f"warm{i} " + "x" * 200,
                                 surface="probe", **_STAMP)
                baseline = os.path.getsize(wal)
                ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                ro.execute("BEGIN")
                ro.execute("SELECT count(*) FROM turns").fetchone()
                try:
                    for i in range(2500):
                        w.write_turn("user_message", f"pin{i} " + "x" * 200,
                                     surface="probe", **_STAMP)
                    pinned = os.path.getsize(wal)
                finally:
                    ro.execute("COMMIT")
                    ro.close()
            finally:
                w.close()
        self.assertGreater(
            pinned, baseline * 3,
            "a pinned reader must visibly break the bound — if it does "
            "not, the cockpit excursion signal is watching nothing",
        )


if __name__ == "__main__":
    unittest.main()
