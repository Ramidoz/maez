# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 4c.5b — audit trace refusal policy.

Trace labels are refusal tokens, not evidence metadata. Projection-
influenced rows must be excluded at the ledger read boundary by
default, while rich lineage lives in a separate diagnostic table keyed
by turn_id.
"""

from __future__ import annotations

import io
import json
import logging
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_audit_trace_")

from core.ledger import chain, migrate, recent_turns, writer  # noqa: E402


def tearDownModule():
    import shutil

    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


def _write(db: str, kind: str, text: str, **kwargs) -> str:
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
        w = writer.LedgerWriter(db)
        try:
            tid = w.write_turn(kind, text, **kwargs)
        finally:
            w.close()
    assert tid is not None, f"write_turn({kind!r}) returned None"
    return tid


_MR_KW = dict(
    model_id="qwen36-27b",
    prompt_hash="p" * 64,
    soul_hash="s" * 64,
    evidence_envelope={"claimable": [], "forbidden": []},
    audit_verdict={"verdict": "grounded"},
)


def _trace_lineage(rule_id: str = "repetition_with_continuity") -> dict:
    return {
        "rule_id": rule_id,
        "source_ids": ["source-turn-1", "source-turn-2"],
        "policy_doc_sha256": "a" * 64,
        "applied_at": 1_800_000_000.0,
    }


def _write_reply(db: str, text: str, **kwargs) -> str:
    return _write(db, "model_reply", text, **dict(_MR_KW, **kwargs))


class TraceSchemaTests(unittest.TestCase):
    def test_trace_columns_default_null_after_migrate(self):
        db = _fresh_db("columns")
        with sqlite3.connect(db) as conn:
            cols = {row[1]: row for row in conn.execute("PRAGMA table_info(turns)").fetchall()}
            self.assertIn("audit_trace_label", cols)
            self.assertIn("audit_trace_value_schema", cols)
            self.assertIn("audit_trace_metadata_shape", cols)

            tid = _write(db, "user_message", "plain owner row")
            row = conn.execute(
                "SELECT audit_trace_label, audit_trace_value_schema, "
                "audit_trace_metadata_shape FROM turns WHERE turn_id=?",
                (tid,),
            ).fetchone()
        self.assertEqual(row, (None, None, None))

    def test_trace_lineage_table_is_separate_from_turns_row(self):
        db = _fresh_db("lineage")
        traced = _write_reply(
            db,
            "projection-shaped reply",
            audit_trace_label="projection_influenced",
            audit_trace_value_schema=1,
            audit_trace_metadata_shape=1,
            audit_trace_lineage=_trace_lineage(),
        )
        with sqlite3.connect(db) as conn:
            turns_cols = {row[1] for row in conn.execute("PRAGMA table_info(turns)")}
            self.assertNotIn("audit_trace_rule_id", turns_cols)
            self.assertNotIn("audit_trace_source_ids", turns_cols)
            lineage = conn.execute(
                "SELECT turn_id, rule_id, source_ids_json, policy_doc_sha256, "
                "trace_value_schema, trace_metadata_shape FROM audit_trace_lineage "
                "WHERE turn_id=?",
                (traced,),
            ).fetchone()
        self.assertEqual(lineage[0], traced)
        self.assertEqual(lineage[1], "repetition_with_continuity")
        self.assertEqual(json.loads(lineage[2]), ["source-turn-1", "source-turn-2"])
        self.assertEqual(lineage[3], "a" * 64)
        self.assertEqual(lineage[4], 1)
        self.assertEqual(lineage[5], 1)


class ChainHashInvariantTests(unittest.TestCase):
    def test_trace_metadata_excluded_from_canonical_bytes(self):
        row = {
            "turn_id": "t1",
            "tenant_id": "owner",
            "timestamp": 1.0,
            "schema_version": 1,
            "turn_kind": "model_reply",
            "raw_text": "hello",
        }
        traced = dict(
            row,
            audit_trace_label="projection_influenced",
            audit_trace_value_schema=1,
            audit_trace_metadata_shape=1,
        )
        self.assertEqual(chain.canonical_row_bytes(row), chain.canonical_row_bytes(traced))
        self.assertEqual(
            chain.compute_chain_hash(row, None), chain.compute_chain_hash(traced, None)
        )


class WriterValidationTests(unittest.TestCase):
    def test_writer_rejects_half_set_trace_metadata(self):
        db = _fresh_db("half_set")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                with self.assertRaisesRegex(ValueError, "audit_trace"):
                    w.write_turn(
                        "model_reply",
                        "bad trace",
                        **dict(_MR_KW, audit_trace_label="projection_influenced"),
                    )
            finally:
                w.close()

    def test_writer_rejects_trace_without_lineage(self):
        db = _fresh_db("no_lineage")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(db)
            try:
                with self.assertRaisesRegex(ValueError, "lineage"):
                    w.write_turn(
                        "model_reply",
                        "bad trace",
                        **dict(
                            _MR_KW,
                            audit_trace_label="projection_influenced",
                            audit_trace_value_schema=1,
                            audit_trace_metadata_shape=1,
                        ),
                    )
            finally:
                w.close()


class ModelReplyPersistenceTraceTests(unittest.TestCase):
    def test_persist_model_reply_forwards_trace_metadata_and_lineage(self):
        from core.ledger import model_reply_persistence as mrp

        db = _fresh_db("helper_trace")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            tid = mrp.persist_model_reply(
                db_path=db,
                raw_text="future activation traced reply",
                surface="telegram_text",
                parent_turn_id=None,
                model_id="test-model",
                prompt_material={"messages": []},
                soul_material="test soul",
                evidence_envelope={"claimable": [], "forbidden": []},
                audit_verdict={"verdict": "post_audit"},
                audit_trace_label="projection_influenced",
                audit_trace_value_schema=1,
                audit_trace_metadata_shape=1,
                audit_trace_lineage=_trace_lineage(),
            )

        self.assertIsNotNone(tid)
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT audit_trace_label FROM turns WHERE turn_id=?",
                (tid,),
            ).fetchone()
            lineage = conn.execute(
                "SELECT rule_id FROM audit_trace_lineage WHERE turn_id=?",
                (tid,),
            ).fetchone()
        self.assertEqual(row[0], "projection_influenced")
        self.assertEqual(lineage[0], "repetition_with_continuity")


class ReadBoundaryPolicyTests(unittest.TestCase):
    def test_policy_constants_and_current_policy_shape(self):
        from core.cognition import audit_policy

        self.assertEqual(audit_policy.AUDIT_TRACE_POLICY, "refuse_v1")
        self.assertEqual(audit_policy.TRACE_LABEL_VALUE_SCHEMA, 1)
        self.assertEqual(audit_policy.TRACE_METADATA_SHAPE, 1)
        self.assertEqual(
            audit_policy.PROJECTION_INFLUENCED_TRACE_LABEL,
            "projection_influenced",
        )
        self.assertEqual(
            audit_policy.TraceAuditPolicy.current().policy_version,
            "refuse_v1",
        )

    def test_golden_trace_predicate_corpus_is_pinned(self):
        from core.cognition import audit_policy

        cases = audit_policy.GOLDEN_TRACE_PREDICATE_CASES
        self.assertGreaterEqual(len(cases), 4)
        policy = audit_policy.TraceAuditPolicy.current()
        by_name = {case["name"]: case for case in cases}

        self.assertTrue(policy.is_trace_labeled(by_name["current_valid"]))
        self.assertFalse(policy.is_trace_labeled(by_name["null_default"]))
        self.assertFalse(policy.is_trace_labeled(by_name["wrong_value_schema"]))
        self.assertFalse(policy.is_trace_labeled(by_name["unknown_label"]))

    def test_recent_turns_excludes_traced_rows_by_default_and_backfills(self):
        db = _fresh_db("read_gate")
        older = _write_reply(db, "older untraced reply")
        time.sleep(0.005)
        newer = _write_reply(
            db,
            "newer traced reply",
            audit_trace_label="projection_influenced",
            audit_trace_value_schema=1,
            audit_trace_metadata_shape=1,
            audit_trace_lineage=_trace_lineage(),
        )

        rows = recent_turns.recent_turns_by_kind(
            db,
            kinds=["model_reply"],
            limit=1,
            audit_path="test.default_gate",
            would_have_consumed_surface="self_history",
        )
        self.assertEqual([r["turn_id"] for r in rows], [older])

        rows_with_trace = recent_turns.recent_turns_by_kind(
            db,
            kinds=["model_reply"],
            limit=2,
            include_trace_labeled=True,
        )
        self.assertEqual(
            [r["turn_id"] for r in rows_with_trace],
            [newer, older],
        )

    def test_recent_turns_logs_enriched_skipped_reason(self):
        from core.cognition import audit_policy

        db = _fresh_db("log")
        _write_reply(db, "plain")
        time.sleep(0.005)
        traced = _write_reply(
            db,
            "trace",
            audit_trace_label="projection_influenced",
            audit_trace_value_schema=1,
            audit_trace_metadata_shape=1,
            audit_trace_lineage=_trace_lineage(),
        )

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger(audit_policy.LOGGER_NAME)
        old_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            recent_turns.recent_turns_by_kind(
                db,
                kinds=["model_reply"],
                limit=1,
                audit_path="unit.envelope",
                would_have_consumed_surface="owner_private",
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)

        text = stream.getvalue()
        payload = json.loads(text)
        self.assertEqual(payload["reason"], "skipped_trace_labeled")
        self.assertEqual(payload["row_id"], traced)
        self.assertEqual(payload["audit_path"], "unit.envelope")
        self.assertEqual(payload["would_have_consumed_surface"], "owner_private")
        self.assertEqual(payload["policy_version"], "refuse_v1")
        self.assertNotIn("would-have-consumed-surface", payload)


class DelayedFeedbackReplayTests(unittest.TestCase):
    def test_bounded_envelope_builder_refuses_next_turn_trace_evidence(self):
        from core.cognition.envelope_builder import BoundedEnvelopeBuilder

        db = _fresh_db("delayed_builder")
        _write(db, "user_message", "owner first")
        _write_reply(
            db,
            "projection-shaped reply must not become evidence",
            audit_trace_label="projection_influenced",
            audit_trace_value_schema=1,
            audit_trace_metadata_shape=1,
            audit_trace_lineage=_trace_lineage(),
        )
        _write(db, "user_message", "owner next")

        env = BoundedEnvelopeBuilder().build(
            ledger_db_path=db,
            signals_present=[],
            signals_absent=[],
            tool_results=[],
        )
        summaries = [e["utterance_summary"] for e in env["self_history"]]
        self.assertNotIn(
            "projection-shaped reply must not become evidence",
            summaries,
        )

    def test_daemon_evidence_helper_refuses_trace_evidence(self):
        import daemon.maez_daemon as maez_daemon

        db = _fresh_db("delayed_daemon")
        _write_reply(
            db,
            "trace from daemon helper",
            audit_trace_label="projection_influenced",
            audit_trace_value_schema=1,
            audit_trace_metadata_shape=1,
            audit_trace_lineage=_trace_lineage(),
        )

        daemon = object.__new__(maez_daemon.MaezDaemon)
        with patch.object(maez_daemon, "LEDGER_DB_PATH", Path(db)):
            env = daemon._build_audit_evidence_envelope(
                surface="daemon_cycle",
                signals_present=[],
                signals_absent=[],
            )
        self.assertIsNotNone(env)
        self.assertEqual(env["self_history"], [])

    def test_cached_envelope_reuse_cannot_reintroduce_trace_evidence(self):
        from core.cognition.envelope_builder import BoundedEnvelopeBuilder

        db = _fresh_db("cached")
        _write_reply(
            db,
            "cached trace",
            audit_trace_label="projection_influenced",
            audit_trace_value_schema=1,
            audit_trace_metadata_shape=1,
            audit_trace_lineage=_trace_lineage(),
        )
        env_turn_n = BoundedEnvelopeBuilder().build(
            ledger_db_path=db,
            signals_present=[],
            signals_absent=[],
            tool_results=[],
        )
        cached_for_turn_n2 = dict(env_turn_n)
        self.assertEqual(cached_for_turn_n2["self_history"], [])


class DirectAuditPathTests(unittest.TestCase):
    def test_grounding_judge_direct_prompt_filters_trace_labeled_self_history(self):
        from core.cognition import grounding_judge

        prompt = grounding_judge._build_judge_prompt(
            text="I said something earlier",
            signals_present=[],
            signals_absent=[],
            few_shots=[],
            self_history=[
                {
                    "turn_id": "trace-row",
                    "timestamp": 1.0,
                    "kind": "model_reply",
                    "utterance_summary": "trace should not render",
                    "audit_trace_label": "projection_influenced",
                    "audit_trace_value_schema": 1,
                    "audit_trace_metadata_shape": 1,
                }
            ],
        )
        self.assertNotIn("trace should not render", prompt)

    def test_self_claim_audit_does_not_import_recent_turns_directly(self):
        src = Path("core/safety/self_claim_audit.py").read_text()
        self.assertNotIn("recent_turns_by_kind", src)
        self.assertNotIn("FROM turns", src)

    def test_memory_projection_probe_explicitly_opts_into_trace_rows(self):
        src = Path("scripts/memory_projection_probe.py").read_text()
        self.assertIn("include_trace_labeled=True", src)
        self.assertIn('audit_path="diagnostic.memory_projection_probe"', src)


class GovernanceDocTests(unittest.TestCase):
    def test_slice_memo_cites_four_governance_artifacts_and_thesis_question(self):
        memo = Path("docs/SLICE_4C_5B_TRACE_AUDIT_REFUSAL_MEMO.md")
        self.assertTrue(memo.exists())
        text = memo.read_text()
        self.assertIn("ADR 0024", text)
        self.assertIn("Decision 23", text)
        self.assertIn("MEMORY_PROJECTION_RULES.md", text)
        self.assertIn("VELLUM_DELTA_AUDIT.md", text)
        self.assertIn("ARCHITECTURAL_THESIS.md", text)
        self.assertIn(
            "Does this let the bond shape Maez's attention without corrupting what Maez knows to be true?",
            text,
        )

    def test_memory_projection_rules_pin_refuse_v1_and_adr_predicate_lock(self):
        text = Path("docs/governance/MEMORY_PROJECTION_RULES.md").read_text()
        self.assertIn("refuse_v1", text)
        self.assertIn("audit-touching reads MUST exclude trace-labeled rows", text)
        self.assertIn("requires an ADR", text)
        self.assertIn("golden", text.lower())
        self.assertIn("derived rows", text)
        self.assertIn("idempotent-retry semantics", text)
        self.assertIn("INSERT OR IGNORE", text)
        self.assertIn("idempotency-key validation", text)
        self.assertIn("trace-rows", text)
