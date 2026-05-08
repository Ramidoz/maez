# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 4a — inert recall projection architecture.

The load-bearing invariant: projection is a conversation/read-model
surface, not audit evidence. Slice 4a may make projection inspectable,
but it must not alter live recall, evidence envelopes, or judge input.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_recall_projection_")
_REPO = Path(__file__).resolve().parent.parent


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def _fresh_db(name: str) -> str:
    from core.ledger import migrate
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


_MR_KW = dict(
    model_id="qwen36-27b",
    prompt_hash="p" * 64,
    soul_hash="s" * 64,
    evidence_envelope={"claimable": [], "forbidden": []},
    audit_verdict={"verdict": "grounded"},
)


def _write_model_reply(db: str, text: str) -> str:
    from core.ledger import writer
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
        w = writer.LedgerWriter(db)
        try:
            tid = w.write_turn("model_reply", text, **_MR_KW)
        finally:
            w.close()
    assert tid
    return tid


def _self_history_entry(
    *,
    turn_id: str = "turn-1",
    text: str = "raw receipt text",
    lifecycle_stage: str = "gestation",
    timestamp: float = 123.0,
    kind: str = "model_reply",
    **extra,
) -> dict:
    entry = {
        "turn_id": turn_id,
        "timestamp": timestamp,
        "kind": kind,
        "utterance_summary": text,
        "lifecycle_stage": lifecycle_stage,
    }
    entry.update(extra)
    return entry


class MemoryProjectionRulesDocTests(unittest.TestCase):
    def test_memory_projection_rules_doc_has_schema_version_and_adr_0024_anchor(self):
        path = _REPO / "docs" / "governance" / "MEMORY_PROJECTION_RULES.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("projection_rules_schema_version: 2", text)
        self.assertIn("ADR 0024", text)
        self.assertIn("Decision 23", text)
        self.assertIn("conversation projection != audit evidence", text)
        self.assertIn("append_only_never_delete", text)

    def test_repetition_rule_documents_temporal_direction_and_probe_boundaries(self):
        path = _REPO / "docs" / "governance" / "MEMORY_PROJECTION_RULES.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("repetition_with_continuity.v1", text)
        self.assertIn("Direction: strengthens only", text)
        self.assertIn("Same turn is not independent", text)
        self.assertIn("rapid repetition", text)
        self.assertIn("daemon-internal echo", text)
        self.assertIn("Probe outputs are diagnostic", text)


class RecallProjectionObjectTests(unittest.TestCase):
    def test_default_projection_preserves_self_history_order_and_text(self):
        from core.memory import recall_projection as rp
        entries = [
            _self_history_entry(turn_id="t-new", text="new raw"),
            _self_history_entry(turn_id="t-old", text="old raw"),
        ]
        report = rp.project_self_history(entries)
        self.assertEqual(
            [item.projected_text for item in report.items],
            ["new raw", "old raw"],
        )
        self.assertEqual(
            [item.turn_id for item in report.items],
            ["t-new", "t-old"],
        )

    def test_projection_preserves_lifecycle_stage_labels(self):
        from core.memory import recall_projection as rp
        entries = [
            _self_history_entry(turn_id="t-live", lifecycle_stage="lived"),
            _self_history_entry(turn_id="t-gest", lifecycle_stage="gestation"),
        ]
        report = rp.project_self_history(entries)
        self.assertEqual(
            [item.lifecycle_stage for item in report.items],
            ["lived", "gestation"],
        )

    def test_projection_marks_missing_lifecycle_stage_unknown(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([{
            "turn_id": "t-missing",
            "kind": "model_reply",
            "utterance_summary": "legacy row",
        }])
        self.assertEqual(report.items[0].lifecycle_stage, "unknown")

    def test_projection_report_carries_rule_id_version_and_source_turn_ids(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(turn_id="t1", text="receipt"),
        ])
        self.assertEqual(report.schema_version, 2)
        self.assertEqual(report.policy.projection_policy_id,
                         "maez-memory-projection-v1")
        self.assertEqual(report.policy.projection_policy_version, "2.0.0")
        self.assertEqual(report.policy.rule_id, "identity.v1")
        self.assertEqual(report.audit_boundary, "not_audit_evidence")
        self.assertEqual(report.items[0].source_refs[0].turn_id, "t1")
        self.assertRegex(report.items[0].source_refs[0].source_text_sha256,
                         r"^[0-9a-f]{64}$")

    def test_projection_does_not_mutate_input_entries(self):
        from core.memory import recall_projection as rp
        entries = [_self_history_entry(text="raw")]
        before = [dict(e) for e in entries]
        rp.project_self_history(entries)
        self.assertEqual(entries, before)

    def test_projection_rejects_policy_schema_version_mismatch(self):
        from core.memory import recall_projection as rp
        policy = rp.ProjectionPolicy(projection_rules_schema_version=1)
        with self.assertRaisesRegex(ValueError, "schema version"):
            rp.project_self_history([_self_history_entry()], policy=policy)


class RepetitionWithContinuityRuleTests(unittest.TestCase):
    def test_repetition_with_continuity_strengthens_temporally_distinct_sources(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="t1",
                text="Rohit corrected the audit boundary.",
                timestamp=1_700_000_000,
                continuity_key="audit-boundary",
            ),
            _self_history_entry(
                turn_id="t2",
                text="The audit boundary came up again later.",
                timestamp=1_700_086_400,
                continuity_key="audit-boundary",
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertTrue(all(
            item.projection_effect == "strengthened" for item in report.items
        ))
        self.assertTrue(all(item.strength_score == 1 for item in report.items))
        self.assertTrue(all(
            "temporal_distinct_repetition" in item.strength_reasons
            for item in report.items
        ))
        self.assertEqual(
            report.items[0].rule_inputs["independent_source_count"], 2,
        )

    def test_rapid_repetition_within_short_window_does_not_strengthen(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="t1",
                text="same worry",
                timestamp=1_700_000_000,
                continuity_key="same-worry",
            ),
            _self_history_entry(
                turn_id="t2",
                text="same worry again",
                timestamp=1_700_000_030,
                continuity_key="same-worry",
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertEqual(
            [item.projection_effect for item in report.items],
            ["identity", "identity"],
        )
        self.assertEqual(
            report.items[0].rule_inputs["temporal_distinct"], False,
        )

    def test_daemon_internal_echo_does_not_strengthen(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="d1",
                text="daemon thought about the same thing",
                timestamp=1_700_000_000,
                kind="daemon_cycle",
                continuity_key="internal-loop",
            ),
            _self_history_entry(
                turn_id="d2",
                text="daemon thought about the same thing later",
                timestamp=1_700_086_400,
                kind="daemon_cycle",
                continuity_key="internal-loop",
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertEqual(
            [item.projection_effect for item in report.items],
            ["identity", "identity"],
        )
        self.assertEqual(
            report.items[0].rule_inputs["eligible_for_strengthening"],
            False,
        )

    def test_empty_turn_id_does_not_count_as_independent_source(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="",
                text="one source has no receipt id",
                timestamp=1_700_000_000,
                continuity_key="bad-receipts",
            ),
            _self_history_entry(
                turn_id="t2",
                text="one source has a receipt id",
                timestamp=1_700_086_400,
                continuity_key="bad-receipts",
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertEqual(
            [item.projection_effect for item in report.items],
            ["identity", "identity"],
        )
        self.assertEqual(
            report.items[1].rule_inputs["independent_source_count"], 1,
        )

    def test_daemon_echo_cannot_help_non_daemon_item_strengthen(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="d1",
                text="daemon internal echo",
                timestamp=1_700_000_000,
                kind="daemon_cycle",
                continuity_key="mixed-loop",
            ),
            _self_history_entry(
                turn_id="m1",
                text="model reply with same key",
                timestamp=1_700_086_400,
                kind="model_reply",
                continuity_key="mixed-loop",
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertEqual(
            [item.projection_effect for item in report.items],
            ["identity", "identity"],
        )
        self.assertEqual(
            report.items[1].rule_inputs["independent_source_count"], 1,
        )

    def test_daemon_echo_cannot_supply_temporal_distinctness(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="m1",
                text="rapid model repetition",
                timestamp=1_700_000_000,
                kind="model_reply",
                continuity_key="mixed-temporal-loop",
            ),
            _self_history_entry(
                turn_id="m2",
                text="rapid model repetition again",
                timestamp=1_700_000_030,
                kind="model_reply",
                continuity_key="mixed-temporal-loop",
            ),
            _self_history_entry(
                turn_id="d1",
                text="daemon internal echo much later",
                timestamp=1_700_086_400,
                kind="daemon_cycle",
                continuity_key="mixed-temporal-loop",
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertEqual(
            [item.projection_effect for item in report.items],
            ["identity", "identity", "identity"],
        )
        self.assertEqual(
            report.items[0].rule_inputs["temporal_distinct"], False,
        )

    def test_soothing_only_memory_does_not_strengthen_without_continuity_key(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="t1",
                text="You are amazing and everything is fine.",
                timestamp=1_700_000_000,
            ),
            _self_history_entry(
                turn_id="t2",
                text="You are amazing and everything is fine.",
                timestamp=1_700_086_400,
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertEqual(
            [item.projection_effect for item in report.items],
            ["identity", "identity"],
        )

    def test_strength_score_cannot_go_below_baseline(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="t1",
                text="one-off hard memory",
                timestamp=1_700_000_000,
                continuity_key="one-off",
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertEqual(report.items[0].projection_effect, "identity")
        self.assertEqual(report.items[0].strength_score, 0)
        self.assertGreaterEqual(report.items[0].strength_score, 0)

    def test_contradiction_or_refusal_memory_can_strengthen_when_recurrent(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="t1",
                text="Maez refused because the claim was ungrounded.",
                timestamp=1_700_000_000,
                continuity_key="refusal-boundary",
            ),
            _self_history_entry(
                turn_id="t2",
                text="Rohit later reinforced that refusal was correct.",
                timestamp=1_700_086_400,
                continuity_key="refusal-boundary",
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertEqual(
            [item.projection_effect for item in report.items],
            ["strengthened", "strengthened"],
        )

    def test_counterevidence_refs_are_attached_to_strengthened_items(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(
                turn_id="t1",
                text="The claim recurred.",
                timestamp=1_700_000_000,
                continuity_key="claim-thread",
            ),
            _self_history_entry(
                turn_id="t2",
                text="The claim recurred later.",
                timestamp=1_700_086_400,
                continuity_key="claim-thread",
            ),
            _self_history_entry(
                turn_id="t3",
                text="But Rohit corrected the claim.",
                timestamp=1_700_086_500,
                counterevidence_for="claim-thread",
            ),
        ], policy=rp.REPETITION_WITH_CONTINUITY_POLICY)
        self.assertEqual(
            [ref.turn_id for ref in report.items[0].counterevidence_refs],
            ["t3"],
        )


class InertBoundaryTests(unittest.TestCase):
    def test_projection_probe_is_read_only(self):
        path = _REPO / "scripts" / "memory_projection_probe.py"
        text = path.read_text(encoding="utf-8")
        forbidden = [
            "MAEZ_LEDGER_WRITES",
            "write_turn(",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
            "sqlite3.connect(",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, text)
        self.assertIn("recent_turns_by_kind", text)

    def test_projection_probe_exposes_shadow_strengthening_rule(self):
        path = _REPO / "scripts" / "memory_projection_probe.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn("--projection-rule", text)
        self.assertIn("repetition_with_continuity.v1", text)

    def test_grounding_judge_self_history_uses_raw_entries_not_projected(self):
        from core.cognition import grounding_judge
        raw = [_self_history_entry(text="raw receipt: I refused earlier")]
        projected = [_self_history_entry(text="projected lie: I agreed earlier")]
        # Projection objects may exist, but the judge call receives and
        # renders the raw self_history entries explicitly supplied.
        prompt = grounding_judge._build_judge_prompt(
            text="I agreed earlier.",
            signals_present=[],
            signals_absent=[],
            few_shots=[],
            self_history=raw,
        )
        self.assertIn("raw receipt: I refused earlier", prompt)
        self.assertNotIn(projected[0]["utterance_summary"], prompt)

    def test_evidence_envelope_self_history_uses_raw_entries_not_projected(self):
        from core.cognition import envelope_builder
        from core.memory import recall_projection as rp
        db = _fresh_db("raw_envelope")
        _write_model_reply(db, "raw receipt: I refused earlier")
        with patch.object(
            rp, "project_self_history",
            side_effect=AssertionError("projection must not feed envelope"),
        ):
            env = envelope_builder.build_envelope(
                ledger_db_path=db,
                signals_present=[],
                signals_absent=[],
                tool_results=[],
            )
        summaries = [
            e["utterance_summary"] for e in env["self_history"]
        ]
        self.assertIn("raw receipt: I refused earlier", summaries)

    def test_recall_projection_has_no_production_callers(self):
        allowed = {
            "core/memory/recall_projection.py",
            "tests/test_recall_projection.py",
            "scripts/memory_projection_probe.py",
        }
        result = subprocess.run(
            [
                "rg",
                "-l",
                "recall_projection|project_self_history",
                "daemon", "core", "skills", "cli", "scripts", "tests",
            ],
            cwd=_REPO,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        hits = {
            str(Path(line).as_posix())
            for line in result.stdout.splitlines()
            if line.strip()
        }
        self.assertLessEqual(hits, allowed, hits - allowed)

    def test_replay_regression_baseline_unchanged(self):
        result = subprocess.run(
            [
                "scripts/replay_harness.py",
                "--mode", "regression",
                "--baseline", "check",
            ],
            cwd=_REPO,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("overall:      PASS", result.stdout)


class ProjectionReportSerializationTests(unittest.TestCase):
    def test_report_serializes_with_policy_and_items(self):
        from core.memory import recall_projection as rp
        report = rp.project_self_history([
            _self_history_entry(turn_id="t1", text="raw"),
        ])
        data = report.to_dict()
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["audit_boundary"], "not_audit_evidence")
        self.assertEqual(data["policy"]["rule_id"], "identity.v1")
        self.assertEqual(data["items"][0]["turn_id"], "t1")
        self.assertEqual(data["items"][0]["projected_text"], "raw")
        self.assertEqual(data["items"][0]["projection_effect"], "identity")
        self.assertEqual(data["items"][0]["strength_score"], 0)
        self.assertEqual(data["items"][0]["counterevidence_refs"], [])
        self.assertEqual(data["omitted_count"], 0)


if __name__ == "__main__":
    unittest.main()
