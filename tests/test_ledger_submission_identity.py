# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Admission-protocol slice: schema-level submission identity.

Council groupthink finding (2026-08-23/24, both rounds): one owner is
necessary and nowhere near sufficient — exactly-once needs a STABLE
identity minted before the first attempt and ENFORCED by the schema.
Migration 0006 adds ``turns.submission_id`` (UNIQUE where present) and
``turns.submitted_at`` (when the event lived, as opposed to
``timestamp`` = when it committed; ledger order is honestly commit
order, lived-time is provenance).

Idempotent commit-by-identity: re-submitting the same submission_id
with the same payload bytes returns the EXISTING turn_id and writes
nothing — that is what makes crash-window redrive safe. The same id
with DIFFERENT bytes is refused: an identity collision is never
silently resolved.

Both columns are excluded from chain-hash canonical bytes (same
treatment as lifecycle_stage): identity is for dedupe, the chain is for
integrity, and pre-0006 chains must stay valid.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_submission_id_")

from core.ledger import chain, migrate, writer  # noqa: E402

_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


def _row(db: str, turn_id: str) -> sqlite3.Row:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
        ).fetchone()
    finally:
        conn.close()


def _turn_count(db: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    finally:
        conn.close()


class SubmissionIdentityTests(unittest.TestCase):
    def _writer(self, db: str) -> writer.LedgerWriter:
        return writer.LedgerWriter(db)

    def test_submission_identity_is_recorded(self):
        db = _fresh_db("record")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = self._writer(db)
            try:
                tid = w.write_turn(
                    "user_message", "identified turn",
                    submission_id="sub-0001",
                    submitted_at=1000.5,
                    **_STAMP,
                )
            finally:
                w.close()
        row = _row(db, tid)
        self.assertEqual(row["submission_id"], "sub-0001")
        self.assertEqual(row["submitted_at"], 1000.5)

    def test_redrive_same_bytes_is_idempotent(self):
        db = _fresh_db("redrive")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = self._writer(db)
            try:
                first = w.write_turn(
                    "user_message", "the same life event",
                    submission_id="sub-0002", **_STAMP,
                )
                before = _turn_count(db)
                again = w.write_turn(
                    "user_message", "the same life event",
                    submission_id="sub-0002", **_STAMP,
                )
            finally:
                w.close()
        self.assertEqual(
            again, first,
            "redrive with identical identity+bytes must return the "
            "existing turn_id — that is what makes crash recovery safe",
        )
        self.assertEqual(_turn_count(db), before, "and write nothing")

    def test_identity_collision_with_different_bytes_is_refused(self):
        db = _fresh_db("collision")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = self._writer(db)
            try:
                w.write_turn(
                    "user_message", "original bytes",
                    submission_id="sub-0003", **_STAMP,
                )
                before = _turn_count(db)
                with self.assertRaises(ValueError):
                    w.write_turn(
                        "user_message", "DIFFERENT bytes",
                        submission_id="sub-0003", **_STAMP,
                    )
            finally:
                w.close()
        self.assertEqual(_turn_count(db), before,
                         "a refused collision must leave zero rows behind")

    def test_rows_without_identity_still_write(self):
        # Identity is optional at the writer layer (legacy callers, the
        # marker, system events); UNIQUE applies only where present.
        db = _fresh_db("optional")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = self._writer(db)
            try:
                t1 = w.write_turn("user_message", "no id one", **_STAMP)
                t2 = w.write_turn("user_message", "no id two", **_STAMP)
            finally:
                w.close()
        self.assertIsNotNone(t1)
        self.assertIsNotNone(t2)

    def test_identity_excluded_from_chain_hash(self):
        self.assertIn("submission_id", chain._CHAIN_HASH_EXCLUDE)
        self.assertIn("submitted_at", chain._CHAIN_HASH_EXCLUDE)
        # And the whole mixed chain (identified + unidentified rows)
        # must verify.
        db = _fresh_db("chainmix")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = self._writer(db)
            try:
                w.write_turn("user_message", "plain", **_STAMP)
                w.write_turn(
                    "user_message", "identified",
                    submission_id="sub-0004", submitted_at=5.0, **_STAMP,
                )
            finally:
                w.close()
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM turns ORDER BY chain_position"
            ).fetchall()]
        finally:
            conn.close()
        self.assertEqual(
            chain.verify_chain(rows), [],
            "mixed identified/unidentified chain must verify clean",
        )


class OwnerWritePersistsIdentityTests(unittest.TestCase):
    """Replay prerequisite (Grok seat, 2026-08-24): owner_write_turn mints
    an attempt_id BEFORE the attempt and puts it in the dead-letter
    record — but never persisted it on the committed row. That gap is
    what makes 'did this dead letter actually commit?' answerable only by
    byte archaeology. Persisting the same identity makes it an exact
    lookup, and makes owner writes idempotent under redrive."""

    def setUp(self):
        from core.ledger import owner as ledger_owner

        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)

    def test_owner_write_persists_a_submission_identity(self):
        import sqlite3

        from core.ledger import owner as ledger_owner

        db = _fresh_db("owner_identity")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            tid = ledger_owner.owner_write_turn(
                db, "user_message", "owner speech",
                surface="telegram_text",
                taint_labels=["owner_utterance"],
                privacy_access="public",
            )
        self.assertIsNotNone(tid)
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            sid = conn.execute(
                "SELECT submission_id FROM turns WHERE turn_id = ?", (tid,)
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertTrue(
            sid, "an owner-committed row must carry the attempt identity "
                 "so a dead-letter record can be resolved exactly",
        )

    def test_explicit_submission_id_is_not_overridden(self):
        """The spool drainer passes its own identity — the owner path must
        never clobber it."""
        import sqlite3

        from core.ledger import owner as ledger_owner

        db = _fresh_db("owner_identity_explicit")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            tid = ledger_owner.owner_write_turn(
                db, "user_message", "from the spool",
                surface="web_owner",
                submission_id="spool-minted-identity",
                taint_labels=["owner_utterance"],
                privacy_access="public",
            )
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            sid = conn.execute(
                "SELECT submission_id FROM turns WHERE turn_id = ?", (tid,)
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(sid, "spool-minted-identity")


if __name__ == "__main__":
    unittest.main()
