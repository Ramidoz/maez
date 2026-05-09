# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice 4a — inert recall projection architecture.

The load-bearing invariant: projection is a conversation/read-model
surface, not audit evidence. Slice 4a may make projection inspectable,
but it must not alter live recall, evidence envelopes, or judge input.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_recall_projection_")
_REPO = Path(__file__).resolve().parent.parent
_RECALL_PROJECTION_SYMBOLS = frozenset({
    "ProjectionCandidate",
    "ProjectionPolicy",
    "ProjectionReport",
    "ProjectionSourceRef",
    "ProjectedMemoryItem",
    "DEFAULT_POLICY",
    "REPETITION_WITH_CONTINUITY_POLICY",
    "project_candidates",
    "project_self_history",
    "projection_observation_records",
    "recall_projection",
    "write_projection_observation",
})
_RECALL_ACTIVATION_SYMBOLS = frozenset({
    "ActivationDecision",
    "decide_activation",
    "recall_activation",
})


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


def _find_recall_projection_symbol_hits(
    paths: list[Path],
    *,
    allowed_paths: set[str],
) -> set[str]:
    hits: set[str] = set()
    for path in paths:
        rel = (
            str(path.relative_to(_REPO).as_posix())
            if path.is_relative_to(_REPO)
            else str(path)
        )
        if rel in allowed_paths:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "core.memory.recall_projection":
                    for alias in node.names:
                        if alias.name in _RECALL_PROJECTION_SYMBOLS:
                            hits.add(f"{rel}:{alias.name}")
                if module == "core.memory.recall_activation":
                    for alias in node.names:
                        if alias.name in _RECALL_ACTIVATION_SYMBOLS:
                            hits.add(f"{rel}:{alias.name}")
                if module == "core.memory":
                    for alias in node.names:
                        if alias.name in {"recall_projection", "recall_activation"}:
                            hits.add(f"{rel}:{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "core.memory.recall_projection":
                        hits.add(f"{rel}:recall_projection")
                    if alias.name == "core.memory.recall_activation":
                        hits.add(f"{rel}:recall_activation")
            elif isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "import_module"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "importlib"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "core.memory.recall_projection"
                ):
                    hits.add(f"{rel}:importlib.import_module")
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "import_module"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "importlib"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "core.memory.recall_activation"
                ):
                    hits.add(f"{rel}:importlib.import_module")
    return hits


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

    def test_projection_rules_doc_has_candidate_adapter_contract_and_sunset(self):
        path = _REPO / "docs" / "governance" / "MEMORY_PROJECTION_RULES.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("Projection Candidate Adapter Contract", text)
        self.assertIn("Allowed inputs", text)
        self.assertIn("Required candidate fields", text)
        self.assertIn("Forbidden inputs", text)
        self.assertIn("heuristic-derived continuity keys", text)
        self.assertIn("daemon-cycle-only", text)
        self.assertIn("Sunset Commitments", text)
        self.assertIn("2028-05-08", text)
        self.assertIn("outgrown this thread but it keeps surfacing", text)
        self.assertIn("4c observation remains under", text)
        self.assertIn("observation output is not prompt context", text)


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


class ProjectionCandidateAdapterTests(unittest.TestCase):
    def test_projection_candidate_adapter_accepts_lived_recall_candidate_shape(self):
        from core.memory import recall_projection as rp
        candidates = [
            rp.ProjectionCandidate(
                candidate_id="episode:alpha",
                candidate_kind="lived_episode",
                text="Rohit protected the audit boundary.",
                source_ids=("turn-a",),
                continuity_key="audit-boundary",
                continuity_key_basis="source_metadata",
                timestamp=1_700_000_000,
                lifecycle_stage="gestation",
                trust_scope="owner_private",
            ),
            rp.ProjectionCandidate(
                candidate_id="episode:beta",
                candidate_kind="lived_episode",
                text="The audit boundary returned later.",
                source_ids=("turn-b",),
                continuity_key="audit-boundary",
                continuity_key_basis="source_metadata",
                timestamp=1_700_086_400,
                lifecycle_stage="gestation",
                trust_scope="owner_private",
            ),
        ]
        report = rp.project_candidates(
            candidates,
            policy=rp.REPETITION_WITH_CONTINUITY_POLICY,
        )
        self.assertEqual(
            [item.turn_id for item in report.items],
            ["episode:alpha", "episode:beta"],
        )
        self.assertEqual(
            [item.projection_effect for item in report.items],
            ["strengthened", "strengthened"],
        )
        self.assertEqual(report.audit_boundary, "not_audit_evidence")

    def test_projection_candidate_adapter_rejects_missing_required_receipts(self):
        from core.memory import recall_projection as rp
        candidate = rp.ProjectionCandidate(
            candidate_id="episode:missing-source",
            candidate_kind="lived_episode",
            text="A source-free candidate is not observable truth.",
            source_ids=(),
            continuity_key="source-free",
            continuity_key_basis="source_metadata",
            timestamp=1_700_000_000,
            lifecycle_stage="gestation",
            trust_scope="owner_private",
        )
        with self.assertRaisesRegex(ValueError, "source_ids"):
            rp.project_candidates([candidate])

    def test_projection_candidate_adapter_refuses_heuristic_continuity_key(self):
        from core.memory import recall_projection as rp
        candidate = rp.ProjectionCandidate(
            candidate_id="episode:heuristic",
            candidate_kind="lived_episode",
            text="A guessed continuity key must not enter covenant salience.",
            source_ids=("turn-a",),
            continuity_key="guessed-key",
            continuity_key_basis="heuristic",
            timestamp=1_700_000_000,
            lifecycle_stage="gestation",
            trust_scope="owner_private",
        )
        with self.assertRaisesRegex(ValueError, "continuity_key_basis"):
            rp.project_candidates([candidate])

    def test_projection_candidate_adapter_refuses_daemon_cycle_only_candidate(self):
        from core.memory import recall_projection as rp
        candidate = rp.ProjectionCandidate(
            candidate_id="daemon:loop",
            candidate_kind="daemon_cycle",
            text="The daemon echoed itself.",
            source_ids=("daemon-turn",),
            continuity_key="internal-loop",
            continuity_key_basis="source_metadata",
            timestamp=1_700_000_000,
            lifecycle_stage="gestation",
            trust_scope="owner_private",
        )
        with self.assertRaisesRegex(ValueError, "daemon_cycle"):
            rp.project_candidates([candidate])

    def test_projection_candidate_adapter_does_not_strengthen_duplicate_receipts(self):
        from core.memory import recall_projection as rp
        candidates = [
            rp.ProjectionCandidate(
                candidate_id="episode:alpha",
                candidate_kind="lived_episode",
                text="Same receipt, first candidate.",
                source_ids=("turn-same",),
                continuity_key="same-source",
                continuity_key_basis="source_metadata",
                timestamp=1_700_000_000,
                lifecycle_stage="gestation",
                trust_scope="owner_private",
            ),
            rp.ProjectionCandidate(
                candidate_id="episode:beta",
                candidate_kind="lived_episode",
                text="Same receipt, second candidate.",
                source_ids=("turn-same",),
                continuity_key="same-source",
                continuity_key_basis="source_metadata",
                timestamp=1_700_086_400,
                lifecycle_stage="gestation",
                trust_scope="owner_private",
            ),
        ]
        report = rp.project_candidates(
            candidates,
            policy=rp.REPETITION_WITH_CONTINUITY_POLICY,
        )
        self.assertEqual(
            [item.projection_effect for item in report.items],
            ["identity", "identity"],
        )
        self.assertEqual(
            report.items[0].rule_inputs["independent_source_count"], 1,
        )

    def test_projection_candidate_adapter_refuses_public_or_guest_candidates(self):
        from core.memory import recall_projection as rp
        candidate = rp.ProjectionCandidate(
            candidate_id="episode:public",
            candidate_kind="lived_episode",
            text="Public or guest candidates cannot shape bonded salience.",
            source_ids=("turn-a",),
            continuity_key="public-context",
            continuity_key_basis="source_metadata",
            timestamp=1_700_000_000,
            lifecycle_stage="gestation",
            trust_scope="guest_public",
        )
        with self.assertRaisesRegex(ValueError, "trust_scope"):
            rp.project_candidates([candidate])


class InertBoundaryTests(unittest.TestCase):
    def test_recall_projection_import_scan_catches_new_projection_symbols(self):
        path = Path(_TEST_DB_DIR) / "bad_projection_import.py"
        path.write_text(
            "from core.memory.recall_projection import "
            "ProjectionCandidate, project_candidates\n",
            encoding="utf-8",
        )
        hits = _find_recall_projection_symbol_hits(
            [path],
            allowed_paths=set(),
        )
        self.assertIn(
            f"{path}:ProjectionCandidate",
            hits,
        )
        self.assertIn(
            f"{path}:project_candidates",
            hits,
        )

    def test_recall_projection_import_scan_catches_activation_symbols(self):
        path = Path(_TEST_DB_DIR) / "bad_activation_import.py"
        path.write_text(
            "from core.memory.recall_activation import "
            "ActivationDecision, decide_activation\n",
            encoding="utf-8",
        )
        hits = _find_recall_projection_symbol_hits(
            [path],
            allowed_paths=set(),
        )
        self.assertIn(
            f"{path}:ActivationDecision",
            hits,
        )
        self.assertIn(
            f"{path}:decide_activation",
            hits,
        )

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

    def test_projection_probe_writes_observation_jsonl_not_ledger(self):
        from scripts import memory_projection_probe as probe
        from core.memory import recall_projection as rp
        candidates = [
            rp.ProjectionCandidate(
                candidate_id="episode:alpha",
                candidate_kind="lived_episode",
                text="Rohit protected the audit boundary.",
                source_ids=("turn-a",),
                continuity_key="audit-boundary",
                continuity_key_basis="source_metadata",
                timestamp=1_700_000_000,
                lifecycle_stage="gestation",
                trust_scope="owner_private",
            ),
            rp.ProjectionCandidate(
                candidate_id="episode:beta",
                candidate_kind="lived_episode",
                text="The audit boundary returned later.",
                source_ids=("turn-b",),
                continuity_key="audit-boundary",
                continuity_key_basis="source_metadata",
                timestamp=1_700_086_400,
                lifecycle_stage="gestation",
                trust_scope="owner_private",
            ),
        ]
        report = rp.project_candidates(
            candidates,
            policy=rp.REPETITION_WITH_CONTINUITY_POLICY,
        )
        path = Path(_TEST_DB_DIR) / "projection_observation.jsonl"
        probe.write_projection_observation(
            report=report,
            candidates=candidates,
            log_path=path,
        )
        records = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["schema_version"], 2)
        self.assertEqual(
            records[0]["policy"]["rule_id"],
            "repetition_with_continuity.v1",
        )
        self.assertEqual(records[0]["candidate_count"], 2)
        self.assertEqual(records[0]["projected_count"], 2)
        self.assertEqual(records[0]["candidate_id"], "episode:alpha")
        self.assertEqual(records[0]["candidate_kind"], "lived_episode")
        self.assertEqual(records[0]["trust_scope"], "owner_private")
        self.assertEqual(records[0]["source_ids"], ["turn-a"])
        self.assertEqual(records[0]["continuity_key"], "audit-boundary")
        self.assertEqual(records[0]["would_strengthen"], True)
        self.assertEqual(records[0]["audit_boundary"], "not_audit_evidence")
        self.assertRegex(records[0]["policy_doc_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("independent_source_count", records[0]["rule_inputs"])
        self.assertEqual(records[0]["counterevidence_refs"], [])

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
            "core/memory/recall_activation.py",
            "core/memory/recall_projection.py",
            "tests/test_recall_activation.py",
            "tests/test_recall_projection.py",
            "scripts/memory_projection_probe.py",
        }
        paths: list[Path] = []
        for root_name in ("daemon", "core", "skills", "cli", "scripts", "tests"):
            root = _REPO / root_name
            if root.exists():
                paths.extend(root.rglob("*.py"))
        hits = _find_recall_projection_symbol_hits(
            paths,
            allowed_paths=allowed,
        )
        self.assertEqual(hits, set())

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
