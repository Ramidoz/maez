# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Single serialized ledger owner — the topology the U5 council ruled for.

Three properties, each structural rather than conventional:

1. OWNER LATCH — two concurrently ENABLED LedgerWriters on the same DB
   cannot exist, in or across processes: the second refuses at
   construction (flock on ``<db>.ownerlock``, released atomically with
   process death). The forbidden two-concurrent-WAL-writers state is
   unreachable by configuration, not merely discouraged by rule.
2. OWNER SINGLETON — a process that claims ownership routes every
   enabled write through ONE long-lived writer behind one lock (no
   per-write connection churn; churn maximises the WAL-reset hazard).
   The MAEZ_LEDGER_WRITES flag is re-read per write, so unsetting it
   remains an emergency brake even with a long-lived writer.
3. ROUTING — try_write_turn in the owner process uses the singleton;
   in a non-owner process while another process holds the latch it must
   NOT write the DB: the payload dead-letters (never silent, never a
   second concurrent writer).

Dormancy: with MAEZ_LEDGER_WRITES unset nothing here activates — no
latch file, no singleton, no behavior change.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_single_owner_")

from core.ledger import migrate, writer  # noqa: E402
from core.ledger import owner as ledger_owner  # noqa: E402

_OWNER_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


class OwnerLatchTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()

    def test_second_concurrent_enabled_writer_refuses(self):
        db = _fresh_db("latch")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            first = writer.LedgerWriter(db)
            try:
                with self.assertRaises(RuntimeError) as ctx:
                    writer.LedgerWriter(db)
                self.assertIn("owner", str(ctx.exception).lower())
            finally:
                first.close()

    def test_latch_released_on_close(self):
        db = _fresh_db("latch_release")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            first = writer.LedgerWriter(db)
            first.close()
            second = writer.LedgerWriter(db)  # must not raise
            second.close()

    def test_disabled_writers_take_no_latch(self):
        db = _fresh_db("latch_disabled")
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        with patch.dict(os.environ, env, clear=True):
            a = writer.LedgerWriter(db)
            b = writer.LedgerWriter(db)  # dormant state: both construct
            a.close()
            b.close()
        self.assertFalse(
            Path(db + ".ownerlock").exists(),
            "dormant construction must not grow latch files",
        )


class EagerLatchTests(unittest.TestCase):
    """Council trap #3 (Grok, 2026-08-24): stopping the owner FREES the
    latch — stop is an invitation, not a lease. The owner must therefore
    take the latch EAGERLY at claim time when writes are enabled, closing
    the pre-claim window the falsifier's F2 found during development."""

    def setUp(self):
        ledger_owner._reset_for_tests()

    def tearDown(self):
        ledger_owner._reset_for_tests()

    def test_enabled_claim_takes_the_latch_before_any_write(self):
        db = _fresh_db("eager")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership(db)
            # No write has happened, yet a second enabled writer must
            # already refuse: the pre-claim window is closed.
            with self.assertRaises(RuntimeError):
                writer.LedgerWriter(db)

    def test_disabled_claim_stays_inert(self):
        db = _fresh_db("eager_dormant")
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        with patch.dict(os.environ, env, clear=True):
            ledger_owner.claim_ownership(db)
        self.assertFalse(
            Path(db + ".ownerlock").exists(),
            "dormant claim must not grow latch files",
        )

    def test_pathless_claim_still_works(self):
        # Existing callers (tests) claim without a db_path; behavior is
        # the old lazy shape.
        ledger_owner.claim_ownership()
        self.assertTrue(ledger_owner.this_process_is_owner())


class OwnerSingletonTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()

    def tearDown(self):
        ledger_owner._reset_for_tests()

    def test_owner_writes_reuse_one_writer(self):
        db = _fresh_db("singleton")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            t1 = ledger_owner.owner_write_turn(
                db, "user_message", "first", **_OWNER_STAMP
            )
            t2 = ledger_owner.owner_write_turn(
                db, "user_message", "second", **_OWNER_STAMP
            )
        self.assertIsNotNone(t1)
        self.assertIsNotNone(t2)
        self.assertEqual(
            ledger_owner._writer_constructions_for_tests(), 1,
            "the owner must hold ONE long-lived writer, not churn per write",
        )
        conn = sqlite3.connect(db)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM turns WHERE turn_kind='user_message'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 2)

    def test_flag_off_mid_life_is_an_emergency_brake(self):
        db = _fresh_db("brake")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            self.assertIsNotNone(
                ledger_owner.owner_write_turn(
                    db, "user_message", "while on", **_OWNER_STAMP
                )
            )
        env = {k: v for k, v in os.environ.items() if k != "MAEZ_LEDGER_WRITES"}
        env["MAEZ_LEDGER_WRITES"] = "0"
        with patch.dict(os.environ, env, clear=True):
            self.assertIsNone(
                ledger_owner.owner_write_turn(
                    db, "user_message", "after off", **_OWNER_STAMP
                ),
                "a long-lived owner must re-read the flag per write",
            )

    def test_try_write_turn_routes_to_singleton_in_owner_process(self):
        db = _fresh_db("routing_owner")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            # Prime the singleton (holds the latch long-lived).
            self.assertIsNotNone(
                ledger_owner.owner_write_turn(
                    db, "user_message", "prime", **_OWNER_STAMP
                )
            )
            # try_write_turn must reuse it — a per-call writer would hit
            # the held latch and dead-letter instead of writing.
            tid = writer.try_write_turn(
                db, "user_message", "routed through singleton", **_OWNER_STAMP
            )
        self.assertIsNotNone(tid)
        self.assertEqual(ledger_owner._writer_constructions_for_tests(), 1)


class NonOwnerRoutingTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()

    def tearDown(self):
        ledger_owner._reset_for_tests()

    def test_non_owner_process_dead_letters_instead_of_second_writer(self):
        """Simulate the cross-process shape in-process: another 'process'
        holds the latch (a live enabled writer); this process has NOT
        claimed ownership. try_write_turn must dead-letter, not write."""
        db = _fresh_db("routing_nonowner")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            holder = writer.LedgerWriter(db)  # stands in for the daemon
            try:
                with self.assertLogs("core.ledger.writer", level="ERROR"):
                    tid = writer.try_write_turn(
                        db, "user_message", "must not be lost", **_OWNER_STAMP
                    )
            finally:
                holder.close()
        self.assertIsNone(tid)
        import glob
        import json
        files = glob.glob(writer.dead_letter_glob(db))
        self.assertEqual(len(files), 1)
        record = json.loads(Path(files[0]).read_text().splitlines()[0])
        self.assertEqual(record["raw_text"], "must not be lost")
        self.assertEqual(record["category"], "failed")


if __name__ == "__main__":
    unittest.main()
