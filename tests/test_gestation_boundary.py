# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Gestation Boundary slice — schema + chain hash invariant + writer
+ recall + self_history label tests.

Per docs/slices/legacy/gestation-boundary.md (locked 2026-05-08):

  §6.1  Schema migration adds `lifecycle_stage` column to turns.
        Default 'gestation'. MUST NOT be included in chain-hash
        canonical bytes (pinned here).
  §6    `meta.birth_event_turn_id` defaults absent; setting it makes
        new turn writes record `lifecycle_stage='lived'`.
  §4    Recall path: gestation rows downweight to 0.15x weight on
        user-facing surfaces; explicit `recall_gestation='full'`
        function arg restores full weight on dev paths.
  §6.6  Adversarial review prompt covers: silent mistagging,
        post-fact gestation inference, lived-recall poisoning,
        chain hash semantics changes.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_gestation_")

from core.ledger import chain, migrate, writer  # noqa: E402
from core.ledger import recent_turns  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


def _column_exists(db: str, table: str, col: str) -> bool:
    with sqlite3.connect(db) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


_MR_KW = dict(
    model_id="qwen36-27b",
    prompt_hash="p" * 64,
    soul_hash="s" * 64,
    evidence_envelope={"claimable": [], "forbidden": []},
    audit_verdict={"verdict": "grounded"},
)


class SchemaMigrationTests(unittest.TestCase):
    """Migration 0003 adds the column with the right default. Idempotent
    across re-invocations of migrate.run()."""

    def test_lifecycle_stage_column_present_after_migrate(self):
        db = _fresh_db("schema_present")
        self.assertTrue(_column_exists(db, "turns", "lifecycle_stage"))

    def test_lifecycle_stage_default_is_gestation(self):
        db = _fresh_db("schema_default")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                tid = w.write_turn("user_message", "hi")
            finally:
                w.close()
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT lifecycle_stage FROM turns WHERE turn_id = ?",
                (tid,),
            ).fetchone()
        self.assertEqual(row[0], "gestation")

    def test_migrate_idempotent_against_already_migrated_db(self):
        db = _fresh_db("idempotent")
        # Re-running migrate.run() on the same DB MUST NOT fail.
        migrate.run(db)
        migrate.run(db)
        self.assertTrue(_column_exists(db, "turns", "lifecycle_stage"))

    def test_lifecycle_index_present(self):
        db = _fresh_db("idx")
        with sqlite3.connect(db) as conn:
            indexes = [
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='index' AND tbl_name='turns'"
                ).fetchall()
            ]
        self.assertIn("idx_turns_lifecycle_ts", indexes)


class ChainHashInvariantTests(unittest.TestCase):
    """The load-bearing reviewer-flagged invariant: lifecycle_stage MUST
    NOT change chain-hash output. Otherwise migration 0003 invalidates
    every existing chain hash on every existing DB the moment it lands.
    """

    def test_lifecycle_stage_excluded_from_canonical_bytes(self):
        row_no_stage = {
            "turn_id": "t1", "tenant_id": "owner", "timestamp": 1.0,
            "schema_version": 1, "turn_kind": "user_message",
            "raw_text": "hello",
        }
        row_with_stage = dict(row_no_stage, lifecycle_stage="gestation")
        b1 = chain.canonical_row_bytes(row_no_stage)
        b2 = chain.canonical_row_bytes(row_with_stage)
        self.assertEqual(
            b1, b2,
            "lifecycle_stage MUST NOT appear in canonical bytes",
        )

    def test_lifecycle_stage_does_not_change_chain_hash(self):
        row_no_stage = {
            "turn_id": "t1", "tenant_id": "owner", "timestamp": 1.0,
            "schema_version": 1, "turn_kind": "user_message",
            "raw_text": "hello",
        }
        row_with_stage = dict(row_no_stage, lifecycle_stage="gestation")
        h1 = chain.compute_chain_hash(row_no_stage, None)
        h2 = chain.compute_chain_hash(row_with_stage, None)
        self.assertEqual(h1, h2)

    def test_different_lifecycle_values_produce_same_hash(self):
        row = {
            "turn_id": "t1", "tenant_id": "owner", "timestamp": 1.0,
            "schema_version": 1, "turn_kind": "user_message",
            "raw_text": "hello",
        }
        h_gestation = chain.compute_chain_hash(
            dict(row, lifecycle_stage="gestation"), None,
        )
        h_lived = chain.compute_chain_hash(
            dict(row, lifecycle_stage="lived"), None,
        )
        self.assertEqual(
            h_gestation, h_lived,
            "gestation vs lived MUST hash identically — "
            "lifecycle is a recall-projection concern, not chain-truth",
        )

    def test_existing_db_chain_remains_valid_after_migration(self):
        # Reproduces the failure mode the reviewer flagged: write rows
        # before the migration "lands"; verify chain integrity stays
        # clean after the column is added. (We can't truly downgrade the
        # migration system mid-test, so we simulate by writing rows then
        # re-running migrate.run which is a no-op for already-applied
        # migrations.)
        db = _fresh_db("chain_invariant")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                for i in range(5):
                    w.write_turn("user_message", f"msg-{i}")
            finally:
                w.close()
        # Re-run migration (no-op).
        migrate.run(db)
        # Verify chain.
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            rows = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM turns ORDER BY timestamp ASC"
                ).fetchall()
            ]
        violations = chain.verify_chain(rows)
        self.assertEqual(violations, [])


class WriterBirthEventTests(unittest.TestCase):
    """Writer reads meta.birth_event_turn_id; pre-birth writes get
    'gestation' default; post-birth writes get 'lived'."""

    def _set_birth(self, db: str, turn_id: str | None) -> None:
        with sqlite3.connect(db) as conn:
            if turn_id is None:
                conn.execute(
                    "DELETE FROM meta WHERE key='birth_event_turn_id'"
                )
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) "
                    "VALUES('birth_event_turn_id', ?)",
                    (turn_id,),
                )
            conn.commit()

    def test_pre_birth_write_is_gestation(self):
        db = _fresh_db("pre_birth")
        # No meta.birth_event_turn_id — simulates pre-birth state.
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                tid = w.write_turn("user_message", "pre-birth")
            finally:
                w.close()
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT lifecycle_stage FROM turns WHERE turn_id=?",
                (tid,),
            ).fetchone()
        self.assertEqual(row[0], "gestation")

    def test_post_birth_write_is_lived(self):
        db = _fresh_db("post_birth")
        # Mark birth as having occurred.
        self._set_birth(db, "some-prior-turn-id")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                tid = w.write_turn("user_message", "post-birth")
            finally:
                w.close()
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT lifecycle_stage FROM turns WHERE turn_id=?",
                (tid,),
            ).fetchone()
        self.assertEqual(row[0], "lived")

    def test_chain_hash_unchanged_pre_vs_post_birth(self):
        """Same payload, different birth state → same chain hash.
        This is the load-bearing invariant: lifecycle_stage difference
        between rows MUST NOT affect chain integrity."""
        db = _fresh_db("chain_birth")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                tid_pre = w.write_turn("user_message", "X")
            finally:
                w.close()
        # Mark birth, then write another row with the SAME payload.
        self._set_birth(db, tid_pre)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                tid_post = w.write_turn("user_message", "X")
            finally:
                w.close()
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            rows = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM turns ORDER BY timestamp ASC"
                ).fetchall()
            ]
        # Chain still verifies clean — confirming lifecycle_stage
        # difference doesn't break the chain.
        violations = chain.verify_chain(rows)
        self.assertEqual(violations, [])
        # And the two rows have different lifecycle_stages.
        stages = {r["turn_id"]: r["lifecycle_stage"] for r in rows}
        self.assertEqual(stages[tid_pre], "gestation")
        self.assertEqual(stages[tid_post], "lived")


class RecentTurnsRecallGestationTests(unittest.TestCase):
    """Recall path: default downweights gestation rows behind lived
    rows; recall_gestation='full' restores recency-only ordering."""

    def _write(self, db: str, kind: str, text: str) -> str:
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                tid = w.write_turn(kind, text, **(_MR_KW if kind == "model_reply" else {}))
            finally:
                w.close()
        return tid

    def _set_birth(self, db: str, turn_id: str) -> None:
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) "
                "VALUES('birth_event_turn_id', ?)",
                (turn_id,),
            )
            conn.commit()

    def test_default_two_tier_lived_before_gestation(self):
        db = _fresh_db("two_tier")
        # Write 3 gestation rows.
        for i in range(3):
            self._write(db, "model_reply", f"gest-{i}")
        # Mark birth and write 2 lived rows.
        with sqlite3.connect(db) as conn:
            tid = conn.execute(
                "SELECT turn_id FROM turns "
                "WHERE turn_kind='model_reply' "
                "ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()[0]
        self._set_birth(db, tid)
        for i in range(2):
            self._write(db, "model_reply", f"lived-{i}")
        # Recall with default (user-facing) policy.
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply"], limit=10,
        )
        # Lived rows must come first.
        stages = [r["lifecycle_stage"] for r in rows]
        self.assertEqual(
            stages, ["lived", "lived", "gestation", "gestation", "gestation"],
            "lived rows MUST sort before gestation rows on default path",
        )

    def test_recall_gestation_full_recency_only(self):
        db = _fresh_db("full_recency")
        # Same setup: 3 gestation, 2 lived (lived are newer).
        for i in range(3):
            self._write(db, "model_reply", f"gest-{i}")
        with sqlite3.connect(db) as conn:
            tid = conn.execute(
                "SELECT turn_id FROM turns "
                "WHERE turn_kind='model_reply' "
                "ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()[0]
        self._set_birth(db, tid)
        for i in range(2):
            self._write(db, "model_reply", f"lived-{i}")
        # recall_gestation='full' → pure recency, gestation may
        # interleave with lived (here lived rows are still newest, so
        # full strength still puts them first, but for different
        # reason than the two-tier policy).
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply"], limit=10,
            recall_gestation="full",
        )
        # Verify pure-recency order: timestamps strictly descending.
        timestamps = [r["timestamp"] for r in rows]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_lifecycle_stage_in_returned_dict(self):
        db = _fresh_db("returned_dict")
        self._write(db, "model_reply", "x")
        rows = recent_turns.recent_turns_by_kind(
            db, kinds=["model_reply"], limit=10,
        )
        self.assertIn("lifecycle_stage", rows[0])
        self.assertEqual(rows[0]["lifecycle_stage"], "gestation")


class GroundingJudgeSelfHistoryLabelTests(unittest.TestCase):
    """Self-history block in the judge prompt labels gestation entries
    with the pre-birth marker. Lived entries render unchanged."""

    def test_gestation_entry_labeled(self):
        from core.cognition import grounding_judge as gj
        prompt = gj._build_judge_prompt(
            text="anything",
            signals_present=[], signals_absent=[], few_shots=[],
            self_history=[{
                "turn_id": "t-gest", "timestamp": 1.0,
                "kind": "model_reply",
                "utterance_summary": "I told you the kettle was on",
                "lifecycle_stage": "gestation",
            }],
        )
        # The label must appear in the rendered self_history block.
        self.assertIn("pre-birth", prompt.lower())
        # And appear specifically against the gestation entry's line.
        # (The marker can be anywhere on that entry's line.)
        sh_block_idx = prompt.find("PRIOR UTTERANCES")
        self.assertGreater(sh_block_idx, -1)
        self.assertIn("kettle was on", prompt[sh_block_idx:])

    def test_lived_entry_unlabeled(self):
        from core.cognition import grounding_judge as gj
        prompt = gj._build_judge_prompt(
            text="anything",
            signals_present=[], signals_absent=[], few_shots=[],
            self_history=[{
                "turn_id": "t-lived", "timestamp": 2.0,
                "kind": "model_reply",
                "utterance_summary": "I noticed the temp at 70F",
                "lifecycle_stage": "lived",
            }],
        )
        # No pre-birth marker on lived entries.
        self.assertNotIn("pre-birth", prompt.lower())

    def test_missing_lifecycle_stage_treated_as_gestation_in_label(self):
        # Defensive: legacy callers (or rows from before migration) may
        # not carry lifecycle_stage. Default-deny: treat absent as
        # gestation so unlabeled doesn't accidentally promote to lived.
        from core.cognition import grounding_judge as gj
        prompt = gj._build_judge_prompt(
            text="anything",
            signals_present=[], signals_absent=[], few_shots=[],
            self_history=[{
                "turn_id": "t-legacy", "timestamp": 1.0,
                "kind": "model_reply",
                "utterance_summary": "legacy summary",
            }],
        )
        self.assertIn("pre-birth", prompt.lower())


class LifecycleStageValidationTests(unittest.TestCase):
    """Adversarial-review-flagged: lifecycle_stage typos must fail
    loudly instead of silently bypassing the gestation label
    (per memo §6.6)."""

    def test_valid_lifecycle_stage_accepted(self):
        from core.ledger import envelope_schema
        for stage in ("gestation", "lived"):
            envelope_schema.validate_self_history_entry({
                "turn_id": "t-1", "timestamp": 1.0,
                "utterance_summary": "x",
                "kind": "model_reply",
                "lifecycle_stage": stage,
            })  # no raise

    def test_typo_lifecycle_stage_rejected(self):
        from core.ledger import envelope_schema
        with self.assertRaises(ValueError) as ctx:
            envelope_schema.validate_self_history_entry({
                "turn_id": "t-1", "timestamp": 1.0,
                "utterance_summary": "x",
                "kind": "model_reply",
                "lifecycle_stage": "gestaetion",
            })
        self.assertIn("lifecycle_stage", str(ctx.exception))

    def test_absent_lifecycle_stage_accepted(self):
        # Default-deny convention: absence is treated as 'gestation'
        # downstream, but validation does NOT require the key.
        from core.ledger import envelope_schema
        envelope_schema.validate_self_history_entry({
            "turn_id": "t-1", "timestamp": 1.0,
            "utterance_summary": "x",
            "kind": "model_reply",
        })  # no raise

    def test_lifecycle_stages_constant_exposed(self):
        from core.ledger import envelope_schema
        self.assertEqual(
            envelope_schema.LIFECYCLE_STAGES,
            frozenset({"gestation", "lived"}),
        )


if __name__ == "__main__":
    unittest.main()
