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
) -> dict:
    return {
        "turn_id": turn_id,
        "timestamp": 123.0,
        "kind": "model_reply",
        "utterance_summary": text,
        "lifecycle_stage": lifecycle_stage,
    }


class MemoryProjectionRulesDocTests(unittest.TestCase):
    def test_memory_projection_rules_doc_has_schema_version_and_adr_0024_anchor(self):
        path = _REPO / "docs" / "governance" / "MEMORY_PROJECTION_RULES.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("projection_rules_schema_version: 1", text)
        self.assertIn("ADR 0024", text)
        self.assertIn("Decision 23", text)
        self.assertIn("conversation projection != audit evidence", text)
        self.assertIn("append_only_never_delete", text)


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
        self.assertEqual(report.schema_version, 1)
        self.assertEqual(report.policy.projection_policy_id,
                         "maez-memory-projection-v1")
        self.assertEqual(report.policy.projection_policy_version, "1.0.0")
        self.assertEqual(report.policy.rule_id, "identity.v1")
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
        policy = rp.ProjectionPolicy(projection_rules_schema_version=2)
        with self.assertRaisesRegex(ValueError, "schema version"):
            rp.project_self_history([_self_history_entry()], policy=policy)


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
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["policy"]["rule_id"], "identity.v1")
        self.assertEqual(data["items"][0]["turn_id"], "t1")
        self.assertEqual(data["items"][0]["projected_text"], "raw")
        self.assertEqual(data["items"][0]["projection_effect"], "identity")
        self.assertEqual(data["omitted_count"], 0)


if __name__ == "__main__":
    unittest.main()
