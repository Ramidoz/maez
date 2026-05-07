# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 3.0b (2026-05-07): self_history provenance + envelope slot.

Pins:
  1. PROVENANCE_VALUES contains the seven §2 enum values, including
     the new ``self_history`` value.
  2. validate_envelope accepts a well-shaped ``self_history`` slot,
     accepts an absent or empty slot (optional), and rejects malformed
     entries (bad type, missing turn_id, oversize summary, bad kind).
  3. The ledger writer threads envelope validation: a model_reply or
     daemon_cycle with a malformed self_history entry is rejected
     before SQL runs; a well-shaped or absent slot is accepted.
  4. The grounding judge prompt builder serializes self_history when
     present and omits the block when absent/empty.
  5. self_claim_audit.accepts_provenance recognizes self_history.
  6. Source-level wiring guard: schema doc enum + envelope sections
     mention the new vocabulary.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_self_history_")

from core.ledger import envelope_schema  # noqa: E402
from core.ledger import migrate as ledger_migrate  # noqa: E402
from core.ledger import writer as writer_mod  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


_REPO = Path(__file__).resolve().parents[1]


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    ledger_migrate.run(str(path))
    return str(path)


def _good_self_history_entry(**override) -> dict:
    base = {
        "turn_id": "11111111-1111-4111-8111-111111111111",
        "timestamp": 1715000000.0,
        "utterance_summary": "weather check, said 72F clear",
        "kind": "model_reply",
    }
    base.update(override)
    return base


def _model_reply_kwargs(envelope: dict | None) -> dict:
    return {
        "surface": "test",
        "model_id": "qwen36-27b",
        "prompt_hash": "p" * 64,
        "soul_hash": "s" * 64,
        "evidence_envelope": envelope,
        "audit_verdict": {"verdict": "grounded"},
    }


# ── enum vocabulary ────────────────────────────────────────────────────

class ProvenanceEnumTests(unittest.TestCase):

    def test_enum_includes_self_history(self):
        self.assertIn("self_history", envelope_schema.PROVENANCE_VALUES)

    def test_enum_keeps_six_legacy_values(self):
        for v in (
            "owner-said", "tool-verified", "observed",
            "recalled", "inferred", "synthesized",
        ):
            with self.subTest(value=v):
                self.assertIn(v, envelope_schema.PROVENANCE_VALUES)

    def test_enum_is_exactly_seven_values(self):
        self.assertEqual(len(envelope_schema.PROVENANCE_VALUES), 7)

    def test_validate_provenance_accepts_self_history(self):
        envelope_schema.validate_provenance("self_history")  # no raise

    def test_validate_provenance_rejects_unknown(self):
        with self.assertRaises(ValueError):
            envelope_schema.validate_provenance("hallucinated")


# ── self_history entry validation ──────────────────────────────────────

class SelfHistoryEntryTests(unittest.TestCase):

    def test_well_shaped_entry_accepted(self):
        envelope_schema.validate_self_history_entry(_good_self_history_entry())

    def test_entry_must_be_dict(self):
        with self.assertRaises(ValueError):
            envelope_schema.validate_self_history_entry(["not", "a", "dict"])

    def test_missing_turn_id_rejected(self):
        e = _good_self_history_entry()
        e.pop("turn_id")
        with self.assertRaises(ValueError) as ctx:
            envelope_schema.validate_self_history_entry(e)
        self.assertIn("turn_id", str(ctx.exception))

    def test_oversize_summary_rejected(self):
        e = _good_self_history_entry(utterance_summary="x" * 201)
        with self.assertRaises(ValueError) as ctx:
            envelope_schema.validate_self_history_entry(e)
        self.assertIn("200", str(ctx.exception))

    def test_summary_at_bound_accepted(self):
        e = _good_self_history_entry(utterance_summary="x" * 200)
        envelope_schema.validate_self_history_entry(e)  # no raise

    def test_bad_kind_rejected(self):
        e = _good_self_history_entry(kind="user_message")
        with self.assertRaises(ValueError) as ctx:
            envelope_schema.validate_self_history_entry(e)
        self.assertIn("kind", str(ctx.exception))

    def test_non_numeric_timestamp_rejected(self):
        e = _good_self_history_entry(timestamp="now")
        with self.assertRaises(ValueError):
            envelope_schema.validate_self_history_entry(e)


# ── envelope-level validation ──────────────────────────────────────────

class EnvelopeValidationTests(unittest.TestCase):

    def test_none_envelope_accepted(self):
        envelope_schema.validate_envelope(None)  # no raise

    def test_empty_envelope_accepted(self):
        envelope_schema.validate_envelope({})  # no raise

    def test_missing_self_history_slot_accepted(self):
        envelope_schema.validate_envelope({"claimable": []})

    def test_empty_self_history_slot_accepted(self):
        envelope_schema.validate_envelope({"self_history": []})

    def test_well_shaped_self_history_accepted(self):
        env = {"self_history": [_good_self_history_entry()]}
        envelope_schema.validate_envelope(env)

    def test_self_history_must_be_list(self):
        with self.assertRaises(ValueError):
            envelope_schema.validate_envelope({"self_history": "nope"})

    def test_envelope_propagates_index_in_error(self):
        env = {"self_history": [
            _good_self_history_entry(),
            _good_self_history_entry(turn_id=""),
        ]}
        with self.assertRaises(ValueError) as ctx:
            envelope_schema.validate_envelope(env)
        self.assertIn("self_history[1]", str(ctx.exception))

    def test_unknown_keys_pass_through(self):
        # Forward-compat: a future slot we don't know about must not
        # break old writers. (Permissive on unknown keys per spec.)
        envelope_schema.validate_envelope({
            "future_slot_we_havent_built": {"any": "shape"},
            "self_history": [_good_self_history_entry()],
        })


# ── writer-level integration ───────────────────────────────────────────

class WriterEnvelopeTests(unittest.TestCase):

    def setUp(self):
        self.db_path = _fresh_db("writer_env")

    def test_model_reply_with_self_history_succeeds(self):
        env = {"claimable": [],
               "self_history": [_good_self_history_entry()]}
        kw = _model_reply_kwargs(env)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                tid = w.write_turn("model_reply", "ok", **kw)
            finally:
                w.close()
        self.assertIsNotNone(tid)

    def test_model_reply_without_self_history_succeeds(self):
        env = {"claimable": []}
        kw = _model_reply_kwargs(env)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                tid = w.write_turn("model_reply", "ok", **kw)
            finally:
                w.close()
        self.assertIsNotNone(tid)

    def test_model_reply_with_malformed_self_history_rejected(self):
        env = {"claimable": [],
               "self_history": [_good_self_history_entry(turn_id="")]}
        kw = _model_reply_kwargs(env)
        before = sqlite3.connect(self.db_path).execute(
            "SELECT COUNT(*) FROM turns").fetchone()[0]
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                with self.assertRaises(ValueError) as ctx:
                    w.write_turn("model_reply", "ok", **kw)
            finally:
                w.close()
        self.assertIn("self_history", str(ctx.exception))
        # No row written.
        after = sqlite3.connect(self.db_path).execute(
            "SELECT COUNT(*) FROM turns").fetchone()[0]
        self.assertEqual(before, after)

    def test_daemon_cycle_with_oversize_summary_rejected(self):
        bad_entry = _good_self_history_entry(utterance_summary="x" * 5000)
        env = {"claimable": [], "self_history": [bad_entry]}
        kw = _model_reply_kwargs(env)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer_mod.LedgerWriter(self.db_path)
            try:
                with self.assertRaises(ValueError):
                    w.write_turn("daemon_cycle", "thinking", **kw)
            finally:
                w.close()


# ── grounding judge prompt builder ─────────────────────────────────────

class GroundingJudgePromptTests(unittest.TestCase):

    def test_prompt_omits_self_history_block_when_empty(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="ok", signals_present=[], signals_absent=[],
            few_shots=[], self_history=None,
        )
        self.assertNotIn("PRIOR UTTERANCES", prompt)

    def test_prompt_omits_self_history_block_when_list_empty(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="ok", signals_present=[], signals_absent=[],
            few_shots=[], self_history=[],
        )
        self.assertNotIn("PRIOR UTTERANCES", prompt)

    def test_prompt_serializes_self_history_when_present(self):
        from core.grounding_judge import _build_judge_prompt
        sh = [_good_self_history_entry(
            turn_id="abcd1234-1234-4abc-8abc-123412341234",
            utterance_summary="weather is 72F clear",
        )]
        prompt = _build_judge_prompt(
            text="I told you the weather earlier.",
            signals_present=[], signals_absent=[],
            few_shots=[], self_history=sh,
        )
        self.assertIn("PRIOR UTTERANCES", prompt)
        self.assertIn("abcd1234-1234-4abc-8abc-123412341234", prompt)
        self.assertIn("weather is 72F clear", prompt)

    def test_prompt_includes_self_history_rule_text(self):
        # The instruction paragraph must be present so the judge knows
        # how to treat self_history claims regardless of slot population.
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="x", signals_present=[], signals_absent=[],
            few_shots=[], self_history=None,
        )
        self.assertIn("SELF-HISTORY RULE", prompt)


# ── self_claim_audit awareness ─────────────────────────────────────────

class SelfClaimAuditAcceptsProvenanceTests(unittest.TestCase):

    def test_self_history_accepted(self):
        from core.safety import self_claim_audit
        self.assertTrue(self_claim_audit.accepts_provenance("self_history"))

    def test_legacy_value_still_accepted(self):
        from core.safety import self_claim_audit
        self.assertTrue(self_claim_audit.accepts_provenance("owner-said"))

    def test_unknown_label_rejected(self):
        from core.safety import self_claim_audit
        self.assertFalse(self_claim_audit.accepts_provenance("hallucinated"))


# ── source-level wiring guard ──────────────────────────────────────────

class SchemaDocWiringTests(unittest.TestCase):
    """If the schema doc loses the self_history vocabulary the rest of
    this slice's diff is a fiction. Cheap source-grep guard."""

    def test_schema_doc_enum_section_mentions_self_history(self):
        doc = (_REPO / "docs" / "LEDGER_ENVELOPE_SCHEMA.md").read_text()
        # §2 enum table row.
        self.assertIn("`self_history`", doc)
        self.assertIn("Seven classes", doc)

    def test_schema_doc_envelope_section_has_self_history_slot(self):
        doc = (_REPO / "docs" / "LEDGER_ENVELOPE_SCHEMA.md").read_text()
        self.assertIn("SelfHistoryRef", doc)
        self.assertIn("self_history: list[SelfHistoryRef]", doc)

    def test_schema_doc_marked_ratified(self):
        doc = (_REPO / "docs" / "LEDGER_ENVELOPE_SCHEMA.md").read_text()
        self.assertIn("Ratified 2026-05-06", doc)
        self.assertNotIn("NOT ratified", doc)


if __name__ == "__main__":
    unittest.main()
