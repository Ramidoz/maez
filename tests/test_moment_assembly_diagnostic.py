# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice X.0 - moment assembly diagnostic contract."""

from __future__ import annotations

import ast
import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


_REPO = Path(__file__).resolve().parent.parent
_TEST_DIR = Path(tempfile.mkdtemp(prefix="maez_test_moment_assembly_"))
_MOMENT_ASSEMBLY_SYMBOLS = frozenset(
    {
        "AUDIT_BOUNDARY",
        "BYPASS_REASONS",
        "DiagnosticState",
        "MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA",
        "build_bypassed_record",
        "build_anticipation_slot",
        "build_bond_topology_slots",
        "build_body_state_slots",
        "build_counterevidence_source_tension_slot",
        "build_diagnostic_record",
        "build_open_loops_slot",
        "build_surprise_delta_slot",
        "build_slot",
        "complete_moment_assembly_turn",
        "counterevidence_candidate_id",
        "derive_open_loop_age_bucket",
        "expire_latest_anticipation",
        "find_latest_unreconciled_anticipation",
        "bond_topology_edge_id",
        "bond_topology_node_id",
        "loop_id_for_episode",
        "mark_current_moment_assembly_observed",
        "moment_assembly_turn",
        "moment_assembly_diagnostic",
        "normalize_diagnostic_record",
        "_read_counterevidence_records_impl",
        "read_counterevidence_records",
        "reconcile_latest_anticipation",
        "validate_record",
        "validate_slot",
        "write_bypassed_record",
        "write_anticipation_record",
        "write_bond_topology_record",
        "write_body_state_record",
        "write_counterevidence_record",
        "write_diagnostic_record",
        "write_open_loops_record",
    }
)
_ALLOWED_PRODUCTION_CONTEXTS = {
    ("daemon/maez_daemon.py", "handle_message", "moment_assembly_turn", 1),
    ("cli/maez_chat.py", "_handle_chat", "moment_assembly_turn", 1),
    ("skills/web_interface.py", "chat", "moment_assembly_turn", 1),
    ("skills/telegram_voice.py", "_try_card_reply_intent", "moment_assembly_turn", 1),
    ("skills/telegram_voice.py", "_process_message", "moment_assembly_turn", 1),
}
_COMPLETION_KWARGS = {
    "surface",
    "turn_id",
    "lifecycle_phase",
}


def tearDownModule():
    import shutil

    shutil.rmtree(_TEST_DIR, ignore_errors=True)


def _find_moment_assembly_symbol_hits(
    paths: list[Path],
    *,
    allowed_paths: set[str],
    allowed_path_symbols: set[tuple[str, str]] | None = None,
) -> set[str]:
    allowed_path_symbols = allowed_path_symbols or set()
    hits: set[str] = set()
    for path in paths:
        rel = str(path.relative_to(_REPO).as_posix()) if path.is_relative_to(_REPO) else str(path)
        if rel in allowed_paths:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "core.cognition.moment_assembly_diagnostic":
                    for alias in node.names:
                        if (
                            alias.name in _MOMENT_ASSEMBLY_SYMBOLS
                            and (rel, alias.name) not in allowed_path_symbols
                        ):
                            hits.add(f"{rel}:{alias.name}")
                if module == "core.cognition":
                    for alias in node.names:
                        if alias.name == "moment_assembly_diagnostic":
                            hits.add(f"{rel}:{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "core.cognition.moment_assembly_diagnostic":
                        hits.add(f"{rel}:moment_assembly_diagnostic")
            elif isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "import_module"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "importlib"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "core.cognition.moment_assembly_diagnostic"
                ):
                    hits.add(f"{rel}:importlib.import_module")
    return hits


def _production_python_paths() -> list[Path]:
    paths: list[Path] = []
    for root_name in ("daemon", "core", "skills", "cli", "scripts", "tests"):
        root = _REPO / root_name
        if root.exists():
            paths.extend(root.rglob("*.py"))
    return paths


def _completion_call_nodes(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "complete_moment_assembly_turn":
            calls.append(node)
        elif isinstance(func, ast.Attribute) and func.attr == "complete_moment_assembly_turn":
            calls.append(node)
    return calls


def _function_node(path: Path, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{path} has no function named {name}")


def _context_call_nodes(path: Path, function_name: str) -> list[ast.Call]:
    function = _function_node(path, function_name)
    calls: list[ast.Call] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.With | ast.AsyncWith):
            continue
        for item in node.items:
            context_expr = item.context_expr
            if not isinstance(context_expr, ast.Call):
                continue
            func = context_expr.func
            if isinstance(func, ast.Name) and func.id == "moment_assembly_turn":
                calls.append(context_expr)
            elif isinstance(func, ast.Attribute) and func.attr == "moment_assembly_turn":
                calls.append(context_expr)
    return calls


class MomentAssemblyRecordTests(unittest.TestCase):
    def test_default_record_is_source_backed_and_not_audit_evidence(self):
        from core.cognition.moment_assembly_diagnostic import (
            AUDIT_BOUNDARY,
            MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA,
            build_diagnostic_record,
        )

        record = build_diagnostic_record(
            surface="probe",
            source_ids=["turn-1"],
        )

        self.assertEqual(
            record["schema_version"],
            MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA,
        )
        self.assertEqual(record["audit_boundary"], AUDIT_BOUNDARY)
        self.assertEqual(record["audit_boundary"], "not_audit_evidence")
        self.assertEqual(record["source_ids"], ["turn-1"])
        self.assertRegex(record["thesis_doc_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            record["decoder_note"]["architectural_thesis_path"],
            "docs/governance/ARCHITECTURAL_THESIS.md",
        )
        self.assertEqual(
            record["decoder_note"]["thesis_doc_sha256"],
            record["thesis_doc_sha256"],
        )
        self.assertEqual(
            record["decoder_note"]["architectural_thesis_adr_id"],
            "ARCHITECTURAL_THESIS",
        )
        self.assertEqual(
            record["pressure_vector"]["truth"]["state"],
            "not_implemented",
        )
        self.assertEqual(
            record["pressure_vector"]["truth"]["source_ids"],
            [],
        )
        self.assertIn("pressure_delta", record)
        self.assertEqual(record["pressure_delta"]["truth"]["state"], "not_implemented")
        self.assertIn("pressure_delta.truth", record["contributing_schemas"])
        self.assertIn("recent_conversation", record["candidate_sources"])
        self.assertIn("future_projection_rules", record["candidate_sources"])
        self.assertIn("euclidean", record["bond_topology"])
        self.assertIn("poincare", record["bond_topology"])
        self.assertEqual(record["interpretation_candidates"]["state"], "not_implemented")

    def test_slot_validation_rejects_ambiguous_nulls_and_unknown_states(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_slot,
            validate_slot,
        )

        with self.assertRaisesRegex(ValueError, "state"):
            validate_slot("truth", {"value": None})
        with self.assertRaisesRegex(ValueError, "unknown diagnostic state"):
            build_slot("maybe", value=None, source_ids=[])
        with self.assertRaisesRegex(ValueError, "not_implemented"):
            build_slot("not_implemented", value="hidden value", source_ids=[])
        with self.assertRaisesRegex(ValueError, "source_ids"):
            build_slot("not_implemented", value=None, source_ids=["turn-1"])
        with self.assertRaisesRegex(ValueError, "source_ids"):
            build_slot("emitted_value", value={"x": 1}, source_ids=[])
        with self.assertRaisesRegex(ValueError, "deprecation_reason"):
            build_slot(
                "deprecated",
                value=None,
                source_ids=[],
                deprecated_at_schema_version=2,
            )
        with self.assertRaisesRegex(ValueError, "unknown deprecation_reason"):
            build_slot(
                "deprecated",
                value=None,
                source_ids=[],
                deprecated_at_schema_version=2,
                deprecation_reason="because",
            )

        slot = build_slot("emitted_value", value=None, source_ids=["turn-1"])
        self.assertEqual(slot["state"], "emitted_value")
        self.assertIsNone(slot["value"])
        self.assertEqual(slot["source_ids"], ["turn-1"])

        deprecated = build_slot(
            "deprecated",
            value=None,
            source_ids=[],
            deprecated_at_schema_version=2,
            deprecation_reason="superseded",
        )
        self.assertEqual(deprecated["deprecation_reason"], "superseded")

    def test_per_organ_schema_versions_must_match_contributing_map(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_diagnostic_record,
            validate_record,
        )

        record = build_diagnostic_record(
            surface="probe",
            source_ids=["turn-1"],
        )
        record["pressure_vector"]["truth"]["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema_version"):
            validate_record(record)

        record = build_diagnostic_record(
            surface="probe",
            source_ids=["turn-1"],
        )
        record["pressure_delta"]["truth"]["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema_version"):
            validate_record(record)

    def test_topology_representations_are_independent_slots(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_bond_topology_slots,
            build_diagnostic_record,
            build_slot,
        )

        topology = build_bond_topology_slots(
            graph=None,
            owner_node_id="owner",
            owner_node_kind="person",
        )
        topology["euclidean"] = build_slot(
            "error",
            value=None,
            source_ids=[],
            error_class="euclidean_failure",
        )
        record = build_diagnostic_record(
            surface="probe",
            source_ids=["turn-1"],
            bond_topology=topology,
        )

        self.assertEqual(record["bond_topology"]["euclidean"]["state"], "error")
        self.assertEqual(
            record["bond_topology"]["poincare"]["state"],
            "emitted_value",
        )

    def test_bypassed_record_preserves_turn_completion_visibility(self):
        from core.cognition.moment_assembly_diagnostic import build_bypassed_record

        record = build_bypassed_record(
            surface="probe",
            turn_id="turn-1",
            bypass_reason="not_called",
            lifecycle_phase="turn_close",
        )

        self.assertEqual(record["assembly_path"], "bypassed")
        self.assertEqual(record["source_ids"], ["turn-1"])
        self.assertFalse(record["source_id_synthetic"])
        self.assertEqual(record["bypass_reason"], "not_called")
        self.assertEqual(record["lifecycle_phase"], "turn_close")
        self.assertEqual(record["bypass_note"], "")
        self.assertEqual(record["schema_version"], 2)
        self.assertRegex(record["thesis_doc_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(record["workspace_selection"]["state"], "not_observed")

    def test_bypassed_record_rejects_unknown_reason(self):
        from core.cognition.moment_assembly_diagnostic import build_bypassed_record

        with self.assertRaisesRegex(ValueError, "bypass_reason"):
            build_bypassed_record(
                surface="probe",
                turn_id="turn-1",
                bypass_reason="because",
                lifecycle_phase="turn_close",
            )

    def test_bypassed_record_enforces_bypass_note_discipline(self):
        from core.cognition.moment_assembly_diagnostic import build_bypassed_record

        record = build_bypassed_record(
            surface="probe",
            turn_id="turn-1",
            bypass_reason="early_return",
            lifecycle_phase="turn_close",
            bypass_note="owner interrupted before assembly",
        )
        self.assertEqual(record["bypass_note"], "owner interrupted before assembly")

        with self.assertRaisesRegex(ValueError, "bypass_note"):
            build_bypassed_record(
                surface="probe",
                turn_id="turn-1",
                bypass_reason="early_return",
                lifecycle_phase="turn_close",
                bypass_note="line one\nline two",
            )
        with self.assertRaisesRegex(ValueError, "bypass_note"):
            build_bypassed_record(
                surface="probe",
                turn_id="turn-1",
                bypass_reason="exception",
                lifecycle_phase="turn_close",
                bypass_note="Traceback (most recent call last):",
            )
        with self.assertRaisesRegex(ValueError, "bypass_note"):
            build_bypassed_record(
                surface="probe",
                turn_id="turn-1",
                bypass_reason="exception",
                lifecycle_phase="turn_close",
                bypass_note="x" * 501,
            )

    def test_schema_v2_reader_accepts_x02_bypass_rows_without_bypass_note(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_bypassed_record,
            validate_record,
        )

        record = build_bypassed_record(
            surface="probe",
            turn_id="turn-1",
            bypass_reason="not_called",
            lifecycle_phase="turn_close",
        )
        record["schema_version"] = 1
        del record["bypass_note"]

        validate_record(record)

    def test_open_loops_slot_uses_content_free_loop_ids_and_rejects_labels(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_open_loops_slot,
            loop_id_for_episode,
            validate_slot,
        )

        episode_a = {
            "id": "ep-alpha",
            "created_at": "2026-05-08T12:00:00+00:00",
            "open_loop": "Rohit's original private prose should not enter the id",
            "source_kind": "conversation",
            "source_memory_ids": ["ledger:raw:1"],
        }
        episode_b = {
            **episode_a,
            "open_loop": "Completely different private prose",
        }

        slot_a = build_open_loops_slot(
            episodes=[episode_a],
            observed_at_wall_clock="2026-05-09T12:00:00Z",
        )
        slot_b = build_open_loops_slot(
            episodes=[episode_b],
            observed_at_wall_clock="2026-05-09T12:00:00Z",
        )

        self.assertEqual(slot_a["state"], "emitted_value")
        self.assertEqual(slot_a["value"]["loop_count"], 1)
        self.assertEqual(
            slot_a["value"]["top_loops"][0]["loop_id"],
            loop_id_for_episode("ep-alpha"),
        )
        self.assertEqual(
            slot_a["value"]["top_loops"][0]["loop_id"],
            slot_b["value"]["top_loops"][0]["loop_id"],
        )
        self.assertNotIn("open_loop_text", slot_a["value"]["top_loops"][0])
        self.assertNotIn("label", slot_a["value"]["top_loops"][0])
        self.assertNotIn("summary", slot_a["value"]["top_loops"][0])

        bad = json.loads(json.dumps(slot_a))
        bad["value"]["top_loops"][0]["loop_label"] = "just for debugging"
        with self.assertRaisesRegex(ValueError, "unknown field"):
            validate_slot("candidate_sources.open_loops", bad)

    def test_open_loops_slot_pins_provenance_empty_state_order_and_collision(self):
        from core.cognition.moment_assembly_diagnostic import build_open_loops_slot

        empty = build_open_loops_slot(
            episodes=[],
            observed_at_wall_clock="2026-05-09T12:00:00Z",
        )
        self.assertEqual(empty["state"], "emitted_value")
        self.assertEqual(empty["source_ids"], ["diagnostic:open_loops:empty"])
        self.assertEqual(empty["value"]["loop_id_basis_version"], 1)
        self.assertNotIn("hash_input_version", empty["value"])
        self.assertEqual(empty["value"]["loop_count"], 0)
        self.assertEqual(empty["value"]["top_loops"], [])
        self.assertEqual(empty["value"]["omitted_loop_count"], 0)

        older = {
            "id": "ep-b",
            "created_at": "2026-05-08T12:00:00+00:00",
            "open_loop": "still pending",
            "source_kind": "conversation",
            "source_memory_ids": ["ledger:raw:2"],
        }
        newer_z = {
            **older,
            "id": "ep-z",
            "created_at": "2026-05-09T09:00:00+00:00",
            "source_memory_ids": ["ledger:raw:3"],
        }
        newer_a = {
            **older,
            "id": "ep-a",
            "created_at": "2026-05-09T09:00:00+00:00",
            "source_kind": "followup_doc",
            "authorship": "project_doc",
            "memory_voice": "external_to_maez",
            "source_memory_ids": ["followup-doc:docs/followups/x.md"],
        }
        slot = build_open_loops_slot(
            episodes=[older, newer_z, newer_a],
            observed_at_wall_clock="2026-05-09T12:00:00Z",
            max_loops=2,
        )
        loops = slot["value"]["top_loops"]
        self.assertEqual(
            [entry["loop_id"] for entry in loops],
            sorted(entry["loop_id"] for entry in loops),
        )
        project_entry = next(entry for entry in loops if entry["source_episode_ids"] == ["ep-a"])
        self.assertEqual(project_entry["loop_origin"], "project_doc")
        self.assertEqual(project_entry["provenance_status"], "live")
        self.assertEqual(slot["value"]["omitted_loop_count"], 1)

        with self.assertRaisesRegex(ValueError, "hash collision"):
            build_open_loops_slot(
                episodes=[older, {**older, "open_loop": "different row same episode id"}],
                observed_at_wall_clock="2026-05-09T12:00:00Z",
            )

    def test_open_loops_age_bucket_is_derived_with_hysteresis_not_persisted_raw(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_open_loops_slot,
            derive_open_loop_age_bucket,
        )

        self.assertEqual(
            derive_open_loop_age_bucket(
                created_at="2026-05-07T12:00:00Z",
                observed_at_wall_clock="2026-05-09T12:00:00Z",
            ),
            "recent",
        )
        self.assertEqual(
            derive_open_loop_age_bucket(
                created_at="2026-05-07T10:00:00Z",
                observed_at_wall_clock="2026-05-09T12:00:00Z",
                prior_age_bucket="fresh",
            ),
            "fresh",
        )

        slot = build_open_loops_slot(
            episodes=[
                {
                    "id": "ep-age",
                    "created_at": "2026-05-07T12:00:00+00:00",
                    "open_loop": "pending",
                    "source_kind": "conversation",
                    "source_memory_ids": ["ledger:raw:1"],
                }
            ],
            observed_at_wall_clock="2026-05-09T12:00:00Z",
        )
        entry = slot["value"]["top_loops"][0]
        self.assertEqual(entry["age_bucket_cutoff_version"], 1)
        self.assertNotIn("age_days", entry)
        self.assertNotIn("raw_age", entry)

    def test_write_open_loops_record_marks_turn_observed_and_remains_write_only(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_open_loops_slot,
            moment_assembly_turn,
            write_open_loops_record,
        )

        path = _TEST_DIR / "open_loops_observed.jsonl"
        slot = build_open_loops_slot(
            episodes=[
                {
                    "id": "ep-loop",
                    "created_at": "2026-05-08T12:00:00+00:00",
                    "open_loop": "revisit trace policy",
                    "source_kind": "conversation",
                    "source_memory_ids": ["ledger:raw:1"],
                }
            ],
            observed_at_wall_clock="2026-05-09T12:00:00Z",
        )

        with moment_assembly_turn(
            surface="cli",
            turn_id="turn-1",
            lifecycle_phase="chat_return",
            log_path=path,
        ):
            record_id = write_open_loops_record(
                surface="cli",
                turn_id="turn-1",
                open_loops=slot,
                log_path=path,
                mark_current_turn_observed=True,
            )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], record_id)
        self.assertEqual(rows[0]["assembly_path"], "observed")
        self.assertEqual(rows[0]["candidate_sources"]["open_loops"]["state"], "emitted_value")
        self.assertEqual(rows[0]["workspace_selection"]["state"], "not_implemented")

    def test_bond_topology_strips_labels_and_emits_content_free_ids(self):
        from core.cognition.moment_assembly_diagnostic import (
            bond_topology_node_id,
            build_bond_topology_slots,
            validate_slot,
        )
        from core.memory.relationship_graph import RelationshipGraph

        graph_path = _TEST_DIR / "bond_topology_labels.db"
        graph = RelationshipGraph(str(graph_path))
        owner = graph.upsert_node(label="Rohit", kind="person")
        other = graph.upsert_node(label="Priya", kind="person")
        value = graph.upsert_node(label="private grief thread", kind="value")
        graph.add_edge(
            subject_id=owner,
            relation="cares_about",
            object_id=value,
            source_episode_ids=["ep-1"],
            source_memory_ids=[],
        )
        graph.add_edge(
            subject_id=other,
            relation="supports",
            object_id=value,
            source_episode_ids=["ep-2"],
            source_memory_ids=[],
        )

        slots = build_bond_topology_slots(
            graph=graph,
            owner_node_id=owner,
            owner_node_kind="person",
        )

        serialized = json.dumps(slots, sort_keys=True)
        self.assertNotIn("Rohit", serialized)
        self.assertNotIn("Priya", serialized)
        self.assertNotIn("private grief thread", serialized)
        self.assertNotIn(owner, serialized)
        self.assertIn(bond_topology_node_id(owner, "person"), serialized)
        self.assertEqual(slots["topology_invariants"]["state"], "emitted_value")
        self.assertEqual(slots["euclidean"]["state"], "emitted_value")
        self.assertEqual(slots["poincare"]["state"], "emitted_value")
        self.assertIn("metrics", slots["euclidean"]["value"])
        self.assertTrue(
            all(
                type(value) in {int, float}
                for value in slots["euclidean"]["value"]["metrics"].values()
            )
        )

        bad = json.loads(json.dumps(slots["euclidean"]))
        bad["value"]["node_label"] = "Rohit"
        with self.assertRaisesRegex(ValueError, "forbidden"):
            validate_slot("bond_topology.euclidean", bad)
        bad = json.loads(json.dumps(slots["euclidean"]))
        bad["value"]["metrics"]["source_text"] = "private"
        with self.assertRaisesRegex(ValueError, "forbidden"):
            validate_slot("bond_topology.euclidean", bad)

    def test_bond_topology_empty_singleton_disconnected_and_sign_anchor(self):
        from core.cognition.moment_assembly_diagnostic import build_bond_topology_slots
        from core.memory.relationship_graph import RelationshipGraph

        empty_graph = RelationshipGraph(str(_TEST_DIR / "bond_topology_empty.db"))
        empty = build_bond_topology_slots(graph=empty_graph, owner_node_id="")
        self.assertEqual(empty["topology_invariants"]["state"], "emitted_value")
        self.assertEqual(empty["topology_invariants"]["value"]["node_count"], 0)
        self.assertEqual(empty["euclidean"]["state"], "emitted_null")
        self.assertEqual(empty["poincare"]["state"], "emitted_null")

        singleton = build_bond_topology_slots(
            graph=empty_graph,
            owner_node_id="n-owner",
            owner_node_kind="person",
        )
        self.assertEqual(singleton["topology_invariants"]["value"]["node_count"], 1)
        self.assertEqual(singleton["euclidean"]["state"], "emitted_value")
        self.assertEqual(
            singleton["euclidean"]["value"]["coordinates"][0]["xy"],
            [0.0, 0.0],
        )

        graph = RelationshipGraph(str(_TEST_DIR / "bond_topology_disconnected.db"))
        owner = graph.upsert_node(label="Rohit", kind="person")
        a = graph.upsert_node(label="A", kind="concept")
        b = graph.upsert_node(label="B", kind="concept")
        c = graph.upsert_node(label="C", kind="concept")
        d = graph.upsert_node(label="D", kind="concept")
        graph.add_edge(
            subject_id=owner,
            relation="cares_about",
            object_id=a,
            source_episode_ids=["ep-1"],
            source_memory_ids=[],
        )
        graph.add_edge(
            subject_id=a,
            relation="relates_to",
            object_id=b,
            source_episode_ids=["ep-2"],
            source_memory_ids=[],
        )
        graph.add_edge(
            subject_id=b,
            relation="relates_to",
            object_id=owner,
            source_episode_ids=["ep-3"],
            source_memory_ids=[],
        )
        graph.add_edge(
            subject_id=c,
            relation="relates_to",
            object_id=d,
            source_episode_ids=["ep-4"],
            source_memory_ids=[],
        )

        slots = build_bond_topology_slots(
            graph=graph,
            owner_node_id=owner,
            owner_node_kind="person",
        )

        invariants = slots["topology_invariants"]["value"]
        self.assertEqual(invariants["connected_components"], 2)
        self.assertTrue(invariants["poincare_spanning_tree_lossy"])
        self.assertEqual(invariants["vacated_node_count"], 0)
        owner_hash = invariants["owner_node_hash"]
        euclidean_owner = next(
            item
            for item in slots["euclidean"]["value"]["coordinates"]
            if item["node_id"] == owner_hash
        )
        self.assertLessEqual(euclidean_owner["xy"][0], 0.0)
        self.assertEqual(
            slots["euclidean"]["value"]["relationship_graph_snapshot_id"],
            invariants["relationship_graph_snapshot_id"],
        )

    def test_write_bond_topology_record_marks_turn_observed_and_not_audit_evidence(self):
        from core.cognition.moment_assembly_diagnostic import (
            moment_assembly_turn,
            write_bond_topology_record,
        )
        from core.memory.relationship_graph import RelationshipGraph

        path = _TEST_DIR / "bond_topology_observed.jsonl"
        graph = RelationshipGraph(str(_TEST_DIR / "bond_topology_write.db"))
        owner = graph.upsert_node(label="Rohit", kind="person")
        value = graph.upsert_node(label="continuity", kind="value")
        graph.add_edge(
            subject_id=owner,
            relation="cares_about",
            object_id=value,
            source_episode_ids=["ep-1"],
            source_memory_ids=[],
        )

        with moment_assembly_turn(
            surface="cli",
            turn_id="turn-bond",
            lifecycle_phase="chat_return",
            log_path=path,
        ):
            record_id = write_bond_topology_record(
                surface="cli",
                turn_id="turn-bond",
                graph=graph,
                owner_node_id=owner,
                owner_node_kind="person",
                log_path=path,
                mark_current_turn_observed=True,
            )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], record_id)
        self.assertEqual(rows[0]["audit_boundary"], "not_audit_evidence")
        self.assertEqual(rows[0]["bond_topology"]["topology_invariants"]["state"], "emitted_value")
        self.assertEqual(rows[0]["assembly_path"], "observed")

    def test_body_state_services_are_mechanical_and_content_free(self):
        from core.cognition.moment_assembly_diagnostic import (
            BODY_STATE_SERVICE_HASH_PREFIX,
            build_body_state_slots,
            body_state_service_id,
            validate_slot,
        )

        snapshot = {
            "services": {
                "brain_8080": True,
                "proxy_11438": False,
            },
            "probed_at": 1_778_280_000.0,
        }
        slots = build_body_state_slots(
            body_snapshot=snapshot,
            observed_at_wall_clock="2026-05-09T12:00:00Z",
            interval_target_s=60,
            interval_actual_s=61,
            substrate_generation_id="substrate-test",
        )

        services = slots["services"]
        self.assertEqual(services["state"], "emitted_value")
        value = services["value"]
        self.assertEqual(value["body_state_id_basis_version"], 1)
        self.assertEqual(value["service_handle_basis_version"], 1)
        self.assertEqual(value["substrate_generation_id"], "substrate-test")
        self.assertEqual(len(value["services"]), 2)
        serialized = json.dumps(slots, sort_keys=True)
        self.assertNotIn("brain_8080", serialized)
        self.assertNotIn("proxy_11438", serialized)
        self.assertNotIn("127.0.0.1", serialized)
        self.assertNotIn("8080", serialized)
        self.assertNotIn('"status": "degraded"', serialized)
        self.assertIn("service_responsive", serialized)
        self.assertIn("service_unresponsive", serialized)
        self.assertIn(
            body_state_service_id(service_name="brain_8080", kind="service"),
            serialized,
        )
        self.assertEqual(
            body_state_service_id(service_name="brain_8080", kind="service"),
            body_state_service_id(service_name="brain_9999", kind="service"),
            "service-id basis must exclude port-bearing suffixes",
        )
        self.assertEqual(
            BODY_STATE_SERVICE_HASH_PREFIX,
            "x5.body_state.service.v1|service_name:<name>|kind:<service|hardware|interval>",
        )

        bad = json.loads(json.dumps(services))
        bad["value"]["services"][0]["service_label"] = "brain_8080"
        with self.assertRaisesRegex(ValueError, "forbidden"):
            validate_slot("body_state.services", bad)
        bad = json.loads(json.dumps(services))
        bad["value"]["services"][0]["status"] = "degraded"
        with self.assertRaisesRegex(ValueError, "service status"):
            validate_slot("body_state.services", bad)
        bad = json.loads(json.dumps(services))
        bad["value"]["source_command"] = "systemctl status maez.service"
        with self.assertRaisesRegex(ValueError, "source_command"):
            validate_slot("body_state.services", bad)

    def test_body_state_interval_reserved_slots_and_missed_cause_basis(self):
        from core.cognition.moment_assembly_diagnostic import (
            MISSED_INTERVAL_CAUSE_BASIS,
            build_body_state_slots,
            classify_missed_interval_cause,
            validate_slot,
        )

        slots = build_body_state_slots(
            body_snapshot={"services": {}, "probed_at": 1_778_280_000.0},
            observed_at_wall_clock="2026-05-09T12:00:00Z",
            interval_target_s=60,
            interval_actual_s=150,
            substrate_generation_id="substrate-test",
            source_silent=True,
        )

        self.assertEqual(
            MISSED_INTERVAL_CAUSE_BASIS,
            ("organ_alive_source_silent", "organ_broken", "unknown"),
        )
        interval = slots["interval"]
        self.assertEqual(interval["state"], "error")
        self.assertEqual(interval["error_class"], "missed_sample")
        self.assertEqual(interval["value"]["interval_state"], "interval_missed")
        self.assertEqual(
            interval["value"]["missed_interval_cause"],
            "organ_alive_source_silent",
        )
        self.assertEqual(interval["value"]["interval_target_s"], 60)
        self.assertEqual(interval["value"]["interval_actual_s"], 150)
        self.assertIn(
            interval["value"]["clock_source"], {"ntp_synced", "local_unsynced", "unknown"}
        )
        self.assertEqual(slots["degraded_capability"]["state"], "not_implemented")
        self.assertEqual(slots["owner_presence"]["state"], "not_implemented")
        self.assertEqual(slots["cognitive_substrate"]["state"], "not_implemented")
        self.assertEqual(
            classify_missed_interval_cause(
                heartbeat_advanced=False,
                source_silent=False,
                interval_actual_s=121,
                interval_target_s=60,
            ),
            "organ_broken",
        )

        bad = json.loads(json.dumps(interval))
        bad["value"]["missed_interval_cause"] = "felt_tired"
        with self.assertRaisesRegex(ValueError, "missed_interval_cause"):
            validate_slot("body_state.interval", bad)

    def test_write_body_state_record_caches_sub_interval_without_second_jsonl_write(self):
        from core.cognition.moment_assembly_diagnostic import (
            BODY_STATE_MIN_SAMPLE_INTERVAL_S,
            clear_body_state_sample_cache,
            moment_assembly_turn,
            write_body_state_record,
        )

        path = _TEST_DIR / "body_state_cache.jsonl"
        instance_path = _TEST_DIR / "body_state_instance_id"
        clear_body_state_sample_cache()
        with patch(
            "core.infra.body_capabilities.body_capabilities",
            return_value={
                "services": {"brain_8080": True},
                "probed_at": 1_778_280_000.0,
            },
        ):
            with moment_assembly_turn(
                surface="cli",
                turn_id="turn-body",
                lifecycle_phase="chat_return",
                log_path=path,
            ):
                first = write_body_state_record(
                    surface="cli",
                    turn_id="turn-body",
                    log_path=path,
                    instance_id_path=instance_path,
                    observed_at_wall_clock="2026-05-09T12:00:00Z",
                    monotonic_now_s=100.0,
                    mark_current_turn_observed=True,
                )
                second = write_body_state_record(
                    surface="cli",
                    turn_id="turn-body",
                    log_path=path,
                    instance_id_path=instance_path,
                    observed_at_wall_clock="2026-05-09T12:00:30Z",
                    monotonic_now_s=100.0 + BODY_STATE_MIN_SAMPLE_INTERVAL_S - 1,
                    mark_current_turn_observed=True,
                )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(first, second)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], first)
        self.assertEqual(rows[0]["audit_boundary"], "not_audit_evidence")
        self.assertEqual(rows[0]["body_state"]["services"]["state"], "emitted_value")
        self.assertEqual(rows[0]["body_state"]["interval"]["state"], "emitted_value")
        self.assertEqual(
            rows[0]["body_state"]["degraded_capability"]["state"],
            "not_implemented",
        )

    def test_counterevidence_source_tension_is_witness_only_and_content_free(self):
        from core.cognition.moment_assembly_diagnostic import (
            COUNTEREVIDENCE_HASH_PREFIX,
            build_counterevidence_source_tension_slot,
            counterevidence_candidate_id,
            validate_slot,
        )

        source_a = {
            "source_id": "memory:abc123",
            "source_class": "memory_record",
        }
        source_b = {
            "source_id": "evidence_envelope:def456",
            "source_class": "evidence_envelope",
        }
        slot = build_counterevidence_source_tension_slot(
            source_a=source_a,
            source_b=source_b,
            tension_class="state_vs_source",
            subject_class="self_state",
        )

        self.assertEqual(slot["state"], "emitted_value")
        value = slot["value"]
        self.assertEqual(value["tension_role"], "witness_only")
        self.assertEqual(value["subject_class"], "self_state")
        self.assertEqual(value["counterevidence_id_basis_version"], 1)
        self.assertEqual(
            COUNTEREVIDENCE_HASH_PREFIX,
            "x4.counterevidence.v1|side_a:<source_id_a>|side_b:<source_id_b>|tension_class:<class>",
        )
        self.assertEqual(
            counterevidence_candidate_id(
                source_id_a="memory:abc123",
                source_id_b="evidence_envelope:def456",
                tension_class="state_vs_source",
            ),
            counterevidence_candidate_id(
                source_id_a="evidence_envelope:def456",
                source_id_b="memory:abc123",
                tension_class="state_vs_source",
            ),
        )
        serialized = json.dumps(slot, sort_keys=True)
        self.assertNotIn("contradiction_summary", serialized)
        self.assertNotIn("confidence", serialized)
        self.assertNotIn("truth_score", serialized)

        bad = json.loads(json.dumps(slot))
        bad["value"]["confidence"] = 0.9
        with self.assertRaisesRegex(ValueError, "forbidden"):
            validate_slot("counterevidence.source_tension", bad)

    def test_counterevidence_rejects_forbidden_subjects_candidates_and_self_reference(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_counterevidence_source_tension_slot,
        )

        base_a = {"source_id": "memory:a", "source_class": "memory_record"}
        base_b = {"source_id": "episode:b", "source_class": "episode"}
        with self.assertRaisesRegex(ValueError, "subject_class"):
            build_counterevidence_source_tension_slot(
                source_a=base_a,
                source_b=base_b,
                tension_class="state_vs_source",
                subject_class="bond_shape",
            )
        with self.assertRaisesRegex(ValueError, "candidate_kind"):
            build_counterevidence_source_tension_slot(
                source_a={**base_a, "candidate_kind": "bond_commitment_vs_behavior"},
                source_b=base_b,
                tension_class="state_vs_source",
                subject_class="self_state",
            )
        with self.assertRaisesRegex(ValueError, "counterevidence_record"):
            build_counterevidence_source_tension_slot(
                source_a={
                    "source_id": "counterevidence:x",
                    "source_class": "counterevidence_record",
                },
                source_b=base_b,
                tension_class="state_vs_source",
                subject_class="world_state",
            )
        with self.assertRaisesRegex(ValueError, "typed source_id"):
            build_counterevidence_source_tension_slot(
                source_a={"source_id": "abc123", "source_class": "memory_record"},
                source_b=base_b,
                tension_class="state_vs_source",
                subject_class="world_state",
            )

    def test_counterevidence_projection_requires_model_handles_and_classifies_model_swap(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_counterevidence_source_tension_slot,
            classify_projection_tension,
        )

        projection = {
            "source_id": "projection:old",
            "source_class": "projection",
            "projection_model_id": "qwen-old",
            "projection_basis_version": 1,
        }
        source = {"source_id": "memory:new", "source_class": "memory_record"}

        self.assertEqual(
            classify_projection_tension(
                candidate_model_id="qwen-old",
                current_model_id="qwen-new",
            ),
            "projection_basis_superseded",
        )
        slot = build_counterevidence_source_tension_slot(
            source_a=projection,
            source_b=source,
            tension_class=classify_projection_tension(
                candidate_model_id="qwen-old",
                current_model_id="qwen-new",
            ),
            subject_class="world_state",
        )
        self.assertEqual(slot["value"]["tension_class"], "projection_basis_superseded")

        missing = dict(projection)
        del missing["projection_model_id"]
        with self.assertRaisesRegex(ValueError, "projection_model_id"):
            build_counterevidence_source_tension_slot(
                source_a=missing,
                source_b=source,
                tension_class="projection_vs_source",
                subject_class="world_state",
            )

    def test_write_counterevidence_record_marks_turn_observed_and_reserves_risky_slots(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_counterevidence_source_tension_slot,
            moment_assembly_turn,
            write_counterevidence_record,
        )

        path = _TEST_DIR / "counterevidence_observed.jsonl"
        slot = build_counterevidence_source_tension_slot(
            source_a={"source_id": "memory:a", "source_class": "memory_record"},
            source_b={"source_id": "episode:b", "source_class": "episode"},
            tension_class="recall_vs_source",
            subject_class="world_state",
        )
        with moment_assembly_turn(
            surface="cli",
            turn_id="turn-counter",
            lifecycle_phase="chat_return",
            log_path=path,
        ):
            record_id = write_counterevidence_record(
                surface="cli",
                turn_id="turn-counter",
                source_tension=slot,
                log_path=path,
                mark_current_turn_observed=True,
            )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], record_id)
        self.assertEqual(rows[0]["audit_boundary"], "not_audit_evidence")
        self.assertEqual(rows[0]["counterevidence"]["source_tension"]["state"], "emitted_value")
        self.assertEqual(
            rows[0]["counterevidence"]["audit_refusal_observation"]["state"],
            "not_implemented",
        )
        self.assertEqual(
            rows[0]["counterevidence"]["speech_hedge_observation"]["state"],
            "not_implemented",
        )
        self.assertEqual(
            rows[0]["counterevidence"]["bond_shape_tension"]["state"],
            "not_implemented",
        )
        self.assertEqual(
            rows[0]["counterevidence"]["tension_closure"]["state"],
            "not_implemented",
        )

    def test_anticipation_slot_enforces_closed_targets_and_source_precision(self):
        from core.cognition.moment_assembly_diagnostic import (
            PRESSURE_NAMES,
            build_anticipation_slot,
        )

        targets = {
            "next_surface": "telegram_text",
            "next_pressure_delta": {name: "flat" for name in PRESSURE_NAMES},
            "next_self_workspace_need": ["self_history", "counterevidence"],
        }
        slot = build_anticipation_slot(
            prediction_id="pred-1",
            predicted_at_turn_id="turn-1",
            targets=targets,
            epistemic_precision="high",
            method="deterministic_source_pattern_v1",
            expires_after_turns=1,
            predicted_at_wall_clock="2026-05-09T00:00:00Z",
            source_ids=[
                "ledger:user_message:1",
                "ledger:self_history:2",
                "ledger:open_loop:3",
            ],
        )

        self.assertEqual(slot["state"], "emitted_value")
        self.assertEqual(slot["value"]["prediction_status"], "predicted")
        self.assertEqual(
            set(slot["value"]["targets"]),
            {"next_surface", "next_pressure_delta", "next_self_workspace_need"},
        )
        self.assertEqual(slot["value"]["epistemic_precision"], "high")

        with self.assertRaisesRegex(ValueError, "targets"):
            build_anticipation_slot(
                prediction_id="pred-2",
                predicted_at_turn_id="turn-1",
                targets={**targets, "next_user_message": "Rohit will say yes"},
                epistemic_precision="low",
                method="deterministic_source_pattern_v1",
                expires_after_turns=1,
                predicted_at_wall_clock="2026-05-09T00:00:00Z",
                source_ids=["ledger:user_message:1"],
            )
        with self.assertRaisesRegex(ValueError, "next_surface"):
            build_anticipation_slot(
                prediction_id="pred-3",
                predicted_at_turn_id="turn-1",
                targets={**targets, "next_surface": "literal grief wording"},
                epistemic_precision="low",
                method="deterministic_source_pattern_v1",
                expires_after_turns=1,
                predicted_at_wall_clock="2026-05-09T00:00:00Z",
                source_ids=["ledger:user_message:1"],
            )
        with self.assertRaisesRegex(ValueError, "pressure"):
            build_anticipation_slot(
                prediction_id="pred-4",
                predicted_at_turn_id="turn-1",
                targets={
                    **targets,
                    "next_pressure_delta": {name: "flat" for name in PRESSURE_NAMES[:-1]},
                },
                epistemic_precision="low",
                method="deterministic_source_pattern_v1",
                expires_after_turns=1,
                predicted_at_wall_clock="2026-05-09T00:00:00Z",
                source_ids=["ledger:user_message:1"],
            )
        with self.assertRaisesRegex(ValueError, "epistemic_precision"):
            build_anticipation_slot(
                prediction_id="pred-5",
                predicted_at_turn_id="turn-1",
                targets=targets,
                epistemic_precision="high",
                method="deterministic_source_pattern_v1",
                expires_after_turns=1,
                predicted_at_wall_clock="2026-05-09T00:00:00Z",
                source_ids=["ledger:user_message:1", "ledger:self_history:2"],
            )
        with self.assertRaisesRegex(ValueError, "ledger"):
            build_anticipation_slot(
                prediction_id="pred-6",
                predicted_at_turn_id="turn-1",
                targets=targets,
                epistemic_precision="low",
                method="deterministic_source_pattern_v1",
                expires_after_turns=1,
                predicted_at_wall_clock="2026-05-09T00:00:00Z",
                source_ids=["diagnostic:synthetic-only"],
            )

    def test_anticipation_rejects_model_confidence_and_allows_deliberate_skip(self):
        from core.cognition.moment_assembly_diagnostic import (
            PRESSURE_NAMES,
            build_anticipation_slot,
            validate_slot,
        )

        unknown_targets = {
            "next_surface": "unknown",
            "next_pressure_delta": {name: "unknown" for name in PRESSURE_NAMES},
            "next_self_workspace_need": ["unknown"],
        }
        slot = build_anticipation_slot(
            prediction_id="pred-grief",
            predicted_at_turn_id="turn-grief",
            targets=unknown_targets,
            epistemic_precision="unknown",
            method="deliberate_skip_covenant_boundary_v1",
            expires_after_turns=1,
            predicted_at_wall_clock="2026-05-09T00:00:00Z",
            source_ids=[],
            prediction_status="deliberate_skip",
        )

        self.assertEqual(slot["value"]["prediction_status"], "deliberate_skip")
        self.assertEqual(set(slot["value"]["targets"]), set(unknown_targets))

        bad_value = dict(slot["value"])
        bad_value["model_confidence"] = 0.99
        bad_slot = dict(slot)
        bad_slot["value"] = bad_value
        with self.assertRaisesRegex(ValueError, "model_confidence"):
            validate_slot("anticipation", bad_slot)

    def test_anticipation_value_rejects_bad_wall_clock_and_required_field_drift(self):
        from core.cognition.moment_assembly_diagnostic import (
            PRESSURE_NAMES,
            build_anticipation_slot,
            validate_slot,
        )

        targets = {
            "next_surface": "cli",
            "next_pressure_delta": {name: "flat" for name in PRESSURE_NAMES},
            "next_self_workspace_need": ["recent_conversation"],
        }
        valid_slot = build_anticipation_slot(
            prediction_id="pred-1",
            predicted_at_turn_id="turn-1",
            targets=targets,
            epistemic_precision="low",
            method="deterministic_source_pattern_v1",
            expires_after_turns=1,
            predicted_at_wall_clock="2026-05-09T00:00:00Z",
            source_ids=["ledger:user_message:1"],
        )

        bad_clock = dict(valid_slot)
        bad_clock["value"] = dict(valid_slot["value"])
        bad_clock["value"]["predicted_at_wall_clock"] = "lol"
        with self.assertRaisesRegex(ValueError, "predicted_at_wall_clock"):
            validate_slot("anticipation", bad_clock)

        for missing_field in (
            "prediction_id",
            "predicted_at_wall_clock",
            "targets",
            "epistemic_precision",
        ):
            bad_slot = dict(valid_slot)
            bad_slot["value"] = dict(valid_slot["value"])
            del bad_slot["value"][missing_field]
            with self.subTest(missing_field=missing_field):
                with self.assertRaisesRegex(ValueError, missing_field):
                    validate_slot("anticipation", bad_slot)

        with self.assertRaisesRegex(ValueError, "expires_after_turns"):
            build_anticipation_slot(
                prediction_id="pred-negative-expiry",
                predicted_at_turn_id="turn-1",
                targets=targets,
                epistemic_precision="low",
                method="deterministic_source_pattern_v1",
                expires_after_turns=-1,
                predicted_at_wall_clock="2026-05-09T00:00:00Z",
                source_ids=["ledger:user_message:1"],
            )
        with self.assertRaisesRegex(ValueError, "method"):
            build_anticipation_slot(
                prediction_id="pred-unknown-method",
                predicted_at_turn_id="turn-1",
                targets=targets,
                epistemic_precision="low",
                method="model_introspection_v1",
                expires_after_turns=1,
                predicted_at_wall_clock="2026-05-09T00:00:00Z",
                source_ids=["ledger:user_message:1"],
            )

    def test_surprise_delta_slot_pins_match_and_expiration_shapes(self):
        from core.cognition.moment_assembly_diagnostic import build_surprise_delta_slot

        observed = build_surprise_delta_slot(
            prediction_record_id="pred-record-1",
            matched_surface=True,
            matched_pressure_count=7,
            total_pressure_count=9,
            matched_workspace_need=False,
            surprise_score=0.33,
        )
        self.assertEqual(observed["state"], "emitted_value")
        self.assertEqual(observed["source_ids"], ["pred-record-1"])
        self.assertEqual(observed["value"]["matches"]["next_pressure_delta"]["matched"], 7)

        expired = build_surprise_delta_slot(
            prediction_record_id="pred-record-1",
            expired_without_observation=True,
        )
        self.assertEqual(expired["state"], "not_observed")
        self.assertEqual(expired["source_ids"], ["pred-record-1"])
        self.assertIsNone(expired["value"]["matches"])
        self.assertIsNone(expired["value"]["surprise_score"])


class MomentAssemblyJsonlTests(unittest.TestCase):
    def test_write_diagnostic_record_appends_sorted_jsonl_without_ledger_access(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_diagnostic_record,
            write_diagnostic_record,
        )

        path = _TEST_DIR / "moment_assembly_diagnostic.jsonl"
        record = build_diagnostic_record(
            surface="probe",
            source_ids=["turn-1"],
        )
        write_diagnostic_record(record=record, log_path=path)

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], record["record_id"])
        self.assertEqual(rows[0]["audit_boundary"], "not_audit_evidence")

    def test_completion_hook_writes_one_bypass_row_per_unobserved_turn(self):
        from core.cognition.moment_assembly_diagnostic import (
            complete_moment_assembly_turn,
        )

        path = _TEST_DIR / "completion_hook_unobserved.jsonl"
        record_id = complete_moment_assembly_turn(
            surface="cli",
            turn_id="turn-1",
            diagnostic_observed=False,
            bypass_reason="not_called",
            lifecycle_phase="turn_close",
            log_path=path,
        )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], record_id)
        self.assertEqual(rows[0]["assembly_path"], "bypassed")
        self.assertEqual(rows[0]["surface"], "cli")
        self.assertEqual(rows[0]["source_ids"], ["turn-1"])
        self.assertFalse(rows[0]["source_id_synthetic"])
        self.assertEqual(rows[0]["bypass_reason"], "not_called")
        self.assertEqual(rows[0]["lifecycle_phase"], "turn_close")

    def test_completion_hook_skips_bypass_when_observed_record_exists(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_diagnostic_record,
            complete_moment_assembly_turn,
            write_diagnostic_record,
        )

        path = _TEST_DIR / "completion_hook_observed.jsonl"
        observed = build_diagnostic_record(
            surface="cli",
            source_ids=["turn-1"],
            assembly_path="observed",
        )
        write_diagnostic_record(record=observed, log_path=path)
        result = complete_moment_assembly_turn(
            surface="cli",
            turn_id="turn-1",
            diagnostic_observed=True,
            bypass_reason="not_called",
            lifecycle_phase="turn_close",
            log_path=path,
        )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertIsNone(result)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["assembly_path"], "observed")

    def test_completion_hook_marks_synthetic_source_ids(self):
        from core.cognition.moment_assembly_diagnostic import (
            complete_moment_assembly_turn,
        )

        path = _TEST_DIR / "completion_hook_synthetic.jsonl"
        complete_moment_assembly_turn(
            surface="web_owner",
            turn_id=None,
            diagnostic_observed=False,
            bypass_reason="early_return",
            lifecycle_phase="turn_close",
            log_path=path,
        )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_id_synthetic"], True)
        self.assertRegex(rows[0]["source_ids"][0], r"^completion:web_owner:")
        self.assertEqual(rows[0]["bypass_reason"], "early_return")

    def test_runtime_turn_context_writes_bypass_on_clean_exit(self):
        from core.cognition.moment_assembly_diagnostic import moment_assembly_turn

        path = _TEST_DIR / "runtime_clean_exit.jsonl"
        with moment_assembly_turn(
            surface="cli",
            turn_id="turn-1",
            lifecycle_phase="turn_close",
            log_path=path,
        ):
            pass

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["assembly_path"], "bypassed")
        self.assertEqual(rows[0]["bypass_reason"], "not_called")
        self.assertEqual(rows[0]["bypass_note"], "")
        self.assertEqual(rows[0]["schema_version"], 2)

    def test_runtime_turn_context_suppresses_bypass_when_observed(self):
        from core.cognition.moment_assembly_diagnostic import (
            mark_current_moment_assembly_observed,
            moment_assembly_turn,
        )

        path = _TEST_DIR / "runtime_observed.jsonl"
        with moment_assembly_turn(
            surface="cli",
            turn_id="turn-1",
            lifecycle_phase="turn_close",
            log_path=path,
        ):
            mark_current_moment_assembly_observed(record_id="observed-1")

        self.assertFalse(path.exists())

    def test_runtime_turn_context_requires_and_stores_observed_record_id(self):
        from core.cognition.moment_assembly_diagnostic import (
            mark_current_moment_assembly_observed,
            moment_assembly_turn,
        )

        bad_path = _TEST_DIR / "runtime_observed_linkage_bad.jsonl"
        with self.assertRaisesRegex(ValueError, "record_id"):
            with moment_assembly_turn(
                surface="cli",
                turn_id="turn-1",
                lifecycle_phase="turn_close",
                log_path=bad_path,
            ):
                mark_current_moment_assembly_observed(record_id="")

        path = _TEST_DIR / "runtime_observed_linkage.jsonl"
        with moment_assembly_turn(
            surface="cli",
            turn_id="turn-1",
            lifecycle_phase="turn_close",
            log_path=path,
        ) as turn:
            mark_current_moment_assembly_observed(record_id="observed-record-1")
            self.assertEqual(turn.observed_record_id, "observed-record-1")

        self.assertFalse(path.exists())

    def test_runtime_turn_context_rejects_double_completion(self):
        from core.cognition.moment_assembly_diagnostic import (
            mark_current_moment_assembly_observed,
            moment_assembly_turn,
        )

        path = _TEST_DIR / "runtime_double_completion.jsonl"
        with self.assertRaisesRegex(RuntimeError, "already completed"):
            with moment_assembly_turn(
                surface="cli",
                turn_id="turn-1",
                lifecycle_phase="turn_close",
                log_path=path,
            ):
                mark_current_moment_assembly_observed(record_id="observed-1")
                mark_current_moment_assembly_observed(record_id="observed-2")
        self.assertFalse(path.exists())

    def test_runtime_turn_context_writes_bypass_and_reraises_original_exception(self):
        from core.cognition.moment_assembly_diagnostic import moment_assembly_turn

        path = _TEST_DIR / "runtime_exception.jsonl"
        with self.assertRaisesRegex(RuntimeError, "owner path exploded"):
            with moment_assembly_turn(
                surface="daemon",
                turn_id="turn-1",
                lifecycle_phase="turn_close",
                log_path=path,
            ):
                raise RuntimeError("owner path exploded")

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["bypass_reason"], "exception")
        self.assertEqual(rows[0]["bypass_note"], "RuntimeError: owner path exploded")

    def test_runtime_turn_context_preserves_original_exception_when_diagnostic_write_fails(self):
        from core.cognition.moment_assembly_diagnostic import moment_assembly_turn

        path = _TEST_DIR / "runtime_exception_write_fails.jsonl"
        with (
            patch(
                "core.cognition.moment_assembly_diagnostic.write_diagnostic_record",
                side_effect=OSError("disk full"),
            ),
            self.assertLogs("core.cognition.moment_assembly_diagnostic", level="WARNING") as logs,
            self.assertRaisesRegex(RuntimeError, "owner path exploded"),
        ):
            with moment_assembly_turn(
                surface="daemon",
                turn_id="turn-1",
                lifecycle_phase="turn_close",
                log_path=path,
            ):
                raise RuntimeError("owner path exploded")

        self.assertIn("moment assembly diagnostic write failed", "\n".join(logs.output))
        self.assertFalse(path.exists())

    def test_runtime_turn_context_logs_clean_exit_write_failure_without_propagating(self):
        from core.cognition.moment_assembly_diagnostic import moment_assembly_turn

        path = _TEST_DIR / "runtime_clean_write_fails.jsonl"
        with (
            patch(
                "core.cognition.moment_assembly_diagnostic.write_diagnostic_record",
                side_effect=OSError("disk full"),
            ),
            self.assertLogs("core.cognition.moment_assembly_diagnostic", level="WARNING") as logs,
        ):
            with moment_assembly_turn(
                surface="web_owner",
                turn_id="turn-1",
                lifecycle_phase="turn_close",
                log_path=path,
            ):
                pass

        self.assertIn("moment assembly diagnostic write failed", "\n".join(logs.output))
        self.assertFalse(path.exists())

    def test_runtime_turn_context_warns_once_per_surface_and_phase(self):
        from core.cognition.moment_assembly_diagnostic import moment_assembly_turn

        path = _TEST_DIR / "runtime_warn_once.jsonl"
        with (
            patch(
                "core.cognition.moment_assembly_diagnostic.write_diagnostic_record",
                side_effect=OSError("disk full"),
            ),
            self.assertLogs("core.cognition.moment_assembly_diagnostic", level="WARNING") as logs,
        ):
            for _ in range(2):
                with moment_assembly_turn(
                    surface="telegram_text",
                    turn_id="turn-1",
                    lifecycle_phase="turn_close",
                    log_path=path,
                ):
                    pass
            with moment_assembly_turn(
                surface="telegram_text",
                turn_id="turn-1",
                lifecycle_phase="different_phase",
                log_path=path,
            ):
                pass

        warnings = [
            line for line in logs.output if "moment assembly diagnostic write failed" in line
        ]
        self.assertEqual(len(warnings), 2)

    def test_runtime_turn_context_survives_executor_work_inside_recovery_wrap(self):
        from core.cognition.moment_assembly_diagnostic import moment_assembly_turn

        path = _TEST_DIR / "runtime_executor_recovery.jsonl"

        async def run_recovery_work():
            with moment_assembly_turn(
                surface="telegram_recovery",
                turn_id=None,
                lifecycle_phase="recovery_synthesis_close",
                log_path=path,
            ):
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, lambda: "recovery reply")
                self.assertEqual(result, "recovery reply")

        asyncio.run(run_recovery_work())

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["surface"], "telegram_recovery")
        self.assertEqual(rows[0]["bypass_reason"], "not_called")

    def test_write_anticipation_record_marks_turn_observed(self):
        from core.cognition.moment_assembly_diagnostic import (
            PRESSURE_NAMES,
            build_anticipation_slot,
            moment_assembly_turn,
            write_anticipation_record,
        )

        path = _TEST_DIR / "anticipation_observed.jsonl"
        targets = {
            "next_surface": "cli",
            "next_pressure_delta": {name: "flat" for name in PRESSURE_NAMES},
            "next_self_workspace_need": ["recent_conversation"],
        }
        slot = build_anticipation_slot(
            prediction_id="pred-1",
            predicted_at_turn_id="turn-1",
            targets=targets,
            epistemic_precision="medium",
            method="deterministic_source_pattern_v1",
            expires_after_turns=1,
            predicted_at_wall_clock="2026-05-09T00:00:00Z",
            source_ids=["ledger:user_message:1", "ledger:self_history:2"],
        )

        with moment_assembly_turn(
            surface="cli",
            turn_id="turn-1",
            lifecycle_phase="turn_close",
            log_path=path,
        ):
            record_id = write_anticipation_record(
                surface="cli",
                turn_id="turn-1",
                anticipation=slot,
                log_path=path,
                mark_current_turn_observed=True,
            )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], record_id)
        self.assertEqual(rows[0]["assembly_path"], "observed")
        self.assertEqual(rows[0]["anticipation"]["state"], "emitted_value")
        self.assertEqual(rows[0]["surprise_delta"]["state"], "emitted_null")

    def test_jsonl_replay_finds_latest_unreconciled_anticipation(self):
        from core.cognition.moment_assembly_diagnostic import (
            PRESSURE_NAMES,
            build_anticipation_slot,
            find_latest_unreconciled_anticipation,
            reconcile_latest_anticipation,
            write_anticipation_record,
        )

        path = _TEST_DIR / "anticipation_replay.jsonl"
        targets = {
            "next_surface": "telegram_text",
            "next_pressure_delta": {name: "flat" for name in PRESSURE_NAMES},
            "next_self_workspace_need": ["self_history", "counterevidence"],
        }
        slot = build_anticipation_slot(
            prediction_id="pred-1",
            predicted_at_turn_id="turn-1",
            targets=targets,
            epistemic_precision="high",
            method="deterministic_source_pattern_v1",
            expires_after_turns=1,
            predicted_at_wall_clock="2026-05-09T00:00:00Z",
            source_ids=[
                "ledger:user_message:1",
                "ledger:self_history:2",
                "ledger:open_loop:3",
            ],
        )
        prediction_record_id = write_anticipation_record(
            surface="cli",
            turn_id="turn-1",
            anticipation=slot,
            log_path=path,
        )

        found = find_latest_unreconciled_anticipation(log_path=path)
        self.assertEqual(found["record_id"], prediction_record_id)

        surprise_record_id = reconcile_latest_anticipation(
            surface="telegram_text",
            turn_id="turn-2",
            observed_surface="telegram_text",
            observed_pressure_delta={name: "flat" for name in PRESSURE_NAMES},
            observed_self_workspace_need=["counterevidence", "self_history"],
            log_path=path,
        )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["record_id"], surprise_record_id)
        self.assertEqual(rows[1]["surprise_delta"]["source_ids"], [prediction_record_id])
        self.assertTrue(rows[1]["surprise_delta"]["value"]["matches"]["next_surface"])
        self.assertEqual(
            rows[1]["surprise_delta"]["value"]["matches"]["next_pressure_delta"],
            {"matched": 9, "total": 9},
        )
        self.assertTrue(rows[1]["surprise_delta"]["value"]["matches"]["next_self_workspace_need"])
        self.assertIsNone(find_latest_unreconciled_anticipation(log_path=path))

    def test_jsonl_replay_skips_partial_final_line_and_warns_once(self):
        from core.cognition.moment_assembly_diagnostic import (
            PRESSURE_NAMES,
            build_anticipation_slot,
            find_latest_unreconciled_anticipation,
            write_anticipation_record,
        )

        path = _TEST_DIR / "anticipation_partial_line.jsonl"
        slot = build_anticipation_slot(
            prediction_id="pred-1",
            predicted_at_turn_id="turn-1",
            targets={
                "next_surface": "cli",
                "next_pressure_delta": {name: "flat" for name in PRESSURE_NAMES},
                "next_self_workspace_need": ["recent_conversation"],
            },
            epistemic_precision="low",
            method="deterministic_source_pattern_v1",
            expires_after_turns=1,
            predicted_at_wall_clock="2026-05-09T00:00:00Z",
            source_ids=["ledger:user_message:1"],
        )
        prediction_record_id = write_anticipation_record(
            surface="cli",
            turn_id="turn-1",
            anticipation=slot,
            log_path=path,
        )
        with path.open("a", encoding="utf-8") as fh:
            fh.write('{"record_id": "partial"')

        with self.assertLogs(
            "core.cognition.moment_assembly_diagnostic",
            level="WARNING",
        ) as logs:
            found = find_latest_unreconciled_anticipation(log_path=path)
            found_again = find_latest_unreconciled_anticipation(log_path=path)

        self.assertEqual(found["record_id"], prediction_record_id)
        self.assertEqual(found_again["record_id"], prediction_record_id)
        self.assertEqual(
            sum("jsonl_replay_skip" in message for message in logs.output),
            1,
        )

    def test_jsonl_replay_survives_process_style_reload(self):
        from core.cognition.moment_assembly_diagnostic import (
            PRESSURE_NAMES,
            build_anticipation_slot,
            write_anticipation_record,
        )

        path = _TEST_DIR / "anticipation_process_reload.jsonl"
        slot = build_anticipation_slot(
            prediction_id="pred-1",
            predicted_at_turn_id="turn-1",
            targets={
                "next_surface": "cli",
                "next_pressure_delta": {name: "flat" for name in PRESSURE_NAMES},
                "next_self_workspace_need": ["recent_conversation"],
            },
            epistemic_precision="low",
            method="deterministic_source_pattern_v1",
            expires_after_turns=1,
            predicted_at_wall_clock="2026-05-09T00:00:00Z",
            source_ids=["ledger:user_message:1"],
        )
        prediction_record_id = write_anticipation_record(
            surface="cli",
            turn_id="turn-1",
            anticipation=slot,
            log_path=path,
        )

        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "from core.cognition.moment_assembly_diagnostic "
                    "import find_latest_unreconciled_anticipation; "
                    f"r=find_latest_unreconciled_anticipation(log_path=Path({str(path)!r})); "
                    "print(r['record_id'])"
                ),
            ],
            cwd=_REPO,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(probe.stdout.strip(), prediction_record_id)

    def test_pressure_schema_drift_writes_error_record_before_raising(self):
        from core.cognition.moment_assembly_diagnostic import (
            PRESSURE_NAMES,
            build_anticipation_slot,
            reconcile_latest_anticipation,
            write_anticipation_record,
        )

        path = _TEST_DIR / "anticipation_pressure_schema_drift.jsonl"
        slot = build_anticipation_slot(
            prediction_id="pred-1",
            predicted_at_turn_id="turn-1",
            targets={
                "next_surface": "cli",
                "next_pressure_delta": {name: "flat" for name in PRESSURE_NAMES},
                "next_self_workspace_need": ["recent_conversation"],
            },
            epistemic_precision="low",
            method="deterministic_source_pattern_v1",
            expires_after_turns=1,
            predicted_at_wall_clock="2026-05-09T00:00:00Z",
            source_ids=["ledger:user_message:1"],
        )
        prediction_record_id = write_anticipation_record(
            surface="cli",
            turn_id="turn-1",
            anticipation=slot,
            log_path=path,
        )

        with self.assertRaisesRegex(ValueError, "pressure_schema_drift"):
            reconcile_latest_anticipation(
                surface="cli",
                turn_id="turn-2",
                observed_surface="cli",
                observed_pressure_delta={name: "flat" for name in PRESSURE_NAMES[:-1]},
                observed_self_workspace_need=["recent_conversation"],
                log_path=path,
            )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["surprise_delta"]["state"], "error")
        self.assertEqual(rows[1]["surprise_delta"]["error_class"], "pressure_schema_drift")
        self.assertEqual(rows[1]["surprise_delta"]["source_ids"], [prediction_record_id])

    def test_jsonl_replay_reconciles_expiration_as_not_observed(self):
        from core.cognition.moment_assembly_diagnostic import (
            PRESSURE_NAMES,
            build_anticipation_slot,
            expire_latest_anticipation,
            write_anticipation_record,
        )

        path = _TEST_DIR / "anticipation_expired.jsonl"
        slot = build_anticipation_slot(
            prediction_id="pred-1",
            predicted_at_turn_id="turn-1",
            targets={
                "next_surface": "unknown",
                "next_pressure_delta": {name: "unknown" for name in PRESSURE_NAMES},
                "next_self_workspace_need": ["unknown"],
            },
            epistemic_precision="unknown",
            method="deliberate_skip_covenant_boundary_v1",
            expires_after_turns=1,
            predicted_at_wall_clock="2026-05-09T00:00:00Z",
            source_ids=[],
            prediction_status="deliberate_skip",
        )
        prediction_record_id = write_anticipation_record(
            surface="cli",
            turn_id="turn-1",
            anticipation=slot,
            log_path=path,
        )

        expire_latest_anticipation(
            surface="cli",
            turn_id="turn-2",
            log_path=path,
        )

        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["surprise_delta"]["state"], "not_observed")
        self.assertEqual(rows[1]["surprise_delta"]["source_ids"], [prediction_record_id])
        self.assertIsNone(rows[1]["surprise_delta"]["value"]["matches"])
        self.assertIsNone(rows[1]["surprise_delta"]["value"]["surprise_score"])

    def test_normalize_diagnostic_record_defaults_schema_one_bypass_note(self):
        from core.cognition.moment_assembly_diagnostic import (
            build_bypassed_record,
            normalize_diagnostic_record,
        )

        record = build_bypassed_record(
            surface="cli",
            turn_id="turn-1",
            bypass_reason="not_called",
            lifecycle_phase="turn_close",
        )
        record["schema_version"] = 1
        del record["bypass_note"]
        record["future_field"] = {"preserved": True}

        normalized = normalize_diagnostic_record(record)

        self.assertEqual(normalized["bypass_note"], "")
        self.assertEqual(normalized["future_field"], {"preserved": True})

    def test_probe_script_is_read_only_diagnostic_infrastructure(self):
        path = _REPO / "scripts" / "moment_assembly_probe.py"
        text = path.read_text(encoding="utf-8")
        forbidden = [
            "LedgerWriter",
            "write_turn(",
            "MAEZ_LEDGER_WRITES",
            "sqlite3.connect(",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, text)
        self.assertIn("write_diagnostic_record", text)


class MomentAssemblyBoundaryTests(unittest.TestCase):
    def test_ast_scan_catches_moment_assembly_symbols(self):
        path = _TEST_DIR / "bad_moment_assembly_import.py"
        path.write_text(
            "from core.cognition.moment_assembly_diagnostic import "
            "AUDIT_BOUNDARY, build_diagnostic_record, write_diagnostic_record\n",
            encoding="utf-8",
        )
        hits = _find_moment_assembly_symbol_hits(
            [path],
            allowed_paths=set(),
        )
        self.assertIn(f"{path}:AUDIT_BOUNDARY", hits)
        self.assertIn(f"{path}:build_diagnostic_record", hits)
        self.assertIn(f"{path}:write_diagnostic_record", hits)

    def test_moment_assembly_diagnostic_has_only_context_manager_production_callers(self):
        allowed = {
            "core/cognition/moment_assembly_diagnostic.py",
            "scripts/moment_assembly_probe.py",
            "scripts/x6_gestation_load.py",
            "tests/test_moment_assembly_diagnostic.py",
        }
        hits = _find_moment_assembly_symbol_hits(
            _production_python_paths(),
            allowed_paths=allowed,
            allowed_path_symbols={
                (path, symbol) for path, _, symbol, _ in _ALLOWED_PRODUCTION_CONTEXTS
            },
        )
        self.assertEqual(hits, set())

    def test_anticipation_records_are_write_only_outside_reconciler(self):
        source = (_REPO / "core" / "cognition" / "moment_assembly_diagnostic.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("find_latest_unreconciled_anticipation", source)
        self.assertIn("reconcile_latest_anticipation", source)
        for path in _production_python_paths():
            rel = path.relative_to(_REPO).as_posix()
            if rel in {
                "core/cognition/moment_assembly_diagnostic.py",
                "tests/test_moment_assembly_diagnostic.py",
                "scripts/moment_assembly_probe.py",
                "scripts/x6_gestation_load.py",
            }:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("find_latest_unreconciled_anticipation", text, rel)
            self.assertNotIn("reconcile_latest_anticipation", text, rel)
            self.assertNotIn('["anticipation"]', text, rel)

    def test_open_loop_records_are_write_only_outside_diagnostic_module(self):
        source = (_REPO / "core" / "cognition" / "moment_assembly_diagnostic.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("build_open_loops_slot", source)
        self.assertIn("write_open_loops_record", source)
        for path in _production_python_paths():
            rel = path.relative_to(_REPO).as_posix()
            if rel in {
                "core/cognition/moment_assembly_diagnostic.py",
                "tests/test_moment_assembly_diagnostic.py",
                "scripts/moment_assembly_probe.py",
                "scripts/x6_gestation_load.py",
            }:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("build_open_loops_slot", text, rel)
            self.assertNotIn("write_open_loops_record", text, rel)

    def test_bond_topology_records_are_write_only_outside_diagnostic_module(self):
        source = (_REPO / "core" / "cognition" / "moment_assembly_diagnostic.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("build_bond_topology_slots", source)
        self.assertIn("write_bond_topology_record", source)
        for path in _production_python_paths():
            rel = path.relative_to(_REPO).as_posix()
            if rel in {
                "core/cognition/moment_assembly_diagnostic.py",
                "tests/test_moment_assembly_diagnostic.py",
                "scripts/moment_assembly_probe.py",
                "scripts/x6_gestation_load.py",
            }:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("build_bond_topology_slots", text, rel)
            self.assertNotIn("write_bond_topology_record", text, rel)

    def test_body_state_records_are_write_only_outside_diagnostic_module(self):
        source = (_REPO / "core" / "cognition" / "moment_assembly_diagnostic.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("build_body_state_slots", source)
        self.assertIn("write_body_state_record", source)
        self.assertIn("_BODY_STATE_SAMPLE_CACHE", source)
        for path in _production_python_paths():
            rel = path.relative_to(_REPO).as_posix()
            if rel in {
                "core/cognition/moment_assembly_diagnostic.py",
                "tests/test_moment_assembly_diagnostic.py",
                "scripts/moment_assembly_probe.py",
                "scripts/x6_gestation_load.py",
            }:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("build_body_state_slots", text, rel)
            self.assertNotIn("write_body_state_record", text, rel)
            self.assertNotIn("_BODY_STATE_SAMPLE_CACHE", text, rel)
            self.assertNotIn('["body_state"]', text, rel)

    def test_counterevidence_records_are_write_only_outside_diagnostic_module(self):
        source = (_REPO / "core" / "cognition" / "moment_assembly_diagnostic.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("build_counterevidence_source_tension_slot", source)
        self.assertIn("write_counterevidence_record", source)
        self.assertIn("_read_counterevidence_records_impl", source)
        self.assertIn("read_counterevidence_records", source)
        for path in _production_python_paths():
            rel = path.relative_to(_REPO).as_posix()
            if rel in {
                "core/cognition/moment_assembly_diagnostic.py",
                "tests/test_moment_assembly_diagnostic.py",
                "scripts/moment_assembly_probe.py",
                "scripts/x6_gestation_load.py",
            }:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("build_counterevidence_source_tension_slot", text, rel)
            self.assertNotIn("write_counterevidence_record", text, rel)
            self.assertNotIn("_read_counterevidence_records_impl", text, rel)
            self.assertNotIn("read_counterevidence_records", text, rel)
            self.assertNotIn('["counterevidence"]', text, rel)

    def test_counterevidence_reader_runtime_import_lock_blocks_external_callers(self):
        from core.cognition.moment_assembly_diagnostic import read_counterevidence_records

        helper = _TEST_DIR / "counterevidence_bad_reader.py"
        helper.write_text(
            "from pathlib import Path\n"
            "from core.cognition.moment_assembly_diagnostic import read_counterevidence_records\n"
            "def run():\n"
            "    return read_counterevidence_records(log_path=Path('/tmp/nope.jsonl'))\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import importlib.util; "
                    f"spec=importlib.util.spec_from_file_location('bad_reader', {str(helper)!r}); "
                    "mod=importlib.util.module_from_spec(spec); "
                    "spec.loader.exec_module(mod); "
                    "mod.run()"
                ),
            ],
            cwd=_REPO,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("counterevidence reader is diagnostic-only", proc.stderr + proc.stdout)
        self.assertEqual(read_counterevidence_records(log_path=_TEST_DIR / "missing.jsonl"), [])

    def test_allowlisted_context_callers_are_present_and_use_same_kwargs_and_counts(self):
        for rel, function_name, symbol, expected_count in sorted(_ALLOWED_PRODUCTION_CONTEXTS):
            path = _REPO / rel
            calls = _context_call_nodes(path, function_name)
            self.assertEqual(
                len(calls),
                expected_count,
                f"{rel}:{function_name} must call {symbol} exactly {expected_count} time(s)",
            )
            for call in calls:
                self.assertEqual(
                    {kw.arg for kw in call.keywords},
                    _COMPLETION_KWARGS,
                    f"{rel}:{function_name} must use the locked context kwarg shape",
                )

    def test_web_completion_hook_is_owner_bridge_gated(self):
        src = (_REPO / "skills" / "web_interface.py").read_text(encoding="utf-8")
        call_idx = src.find("moment_assembly_turn(")
        self.assertGreater(call_idx, 0, "web chat must call completion hook")
        owner_bridge_idx = src.rfind("if owner_bridge:", 0, call_idx)
        public_else_idx = src.rfind("\n    else:", 0, call_idx)
        self.assertGreater(
            owner_bridge_idx,
            public_else_idx,
            "web completion hook must be inside the owner_bridge branch",
        )

    def test_public_telegram_has_no_completion_hook(self):
        src = (_REPO / "skills" / "telegram_public.py").read_text(encoding="utf-8")
        self.assertNotIn("moment_assembly_turn", src)

    def test_telegram_recovery_synthesis_path_is_covered(self):
        src = (_REPO / "skills" / "telegram_voice.py").read_text(encoding="utf-8")
        recovery_idx = src.find("_synthesize_recovery_reply(")
        self.assertGreater(recovery_idx, 0, "recovery synthesis path must exist")
        context_idx = src.rfind("moment_assembly_turn(", 0, recovery_idx)
        self.assertGreater(context_idx, 0, "recovery synthesis must be inside context wrap")
        store_idx = src.find("self.memory.store_telegram(", recovery_idx)
        self.assertGreater(store_idx, recovery_idx, "recovery memory store path must exist")
        self.assertGreater(
            store_idx, context_idx, "recovery memory store must be inside context wrap"
        )


class MomentAssemblyGovernanceDocTests(unittest.TestCase):
    def test_rules_doc_pins_long_lived_diagnostic_contract(self):
        path = _REPO / "docs" / "governance" / "MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("ARCHITECTURAL_THESIS.md", text)
        self.assertIn("thesis_doc_sha256", text)
        self.assertIn("not_audit_evidence", text)
        self.assertIn("500 owner-private diagnostic records or 2026-08-08", text)
        self.assertIn("distortion", text)
        self.assertIn("cluster stability", text)
        self.assertIn("human-review usefulness", text)
        self.assertIn("deprecated for one schema version", text)
        self.assertIn("coordination", text)
        self.assertIn("ADR 0005", text)
        self.assertIn("ADR 0006", text)
        self.assertIn("precision", text)
        self.assertIn("sha256 manifest", text)
        self.assertIn("ADR required to open", text)
        self.assertIn("deprecation_reason", text)
        self.assertIn("query-log rotation", text)
        self.assertIn("rejection_reasons", text)
        self.assertIn("turn-completion hook", text)
        self.assertIn("write_bypassed_record", text)
        self.assertIn("moment_assembly_turn", text)
        self.assertIn("bypass_reason", text)
        self.assertIn("bypass_note", text)
        self.assertIn("source_id_synthetic", text)
        self.assertIn("X.0.3", text)
        self.assertIn(
            "Covenant clauses are documentation discipline, not enforcement",
            text,
        )

    def test_slice_memo_answers_thesis_question(self):
        path = _REPO / "docs" / "SLICE_X0_MOMENT_ASSEMBLY_DIAGNOSTIC_MEMO.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(
            "Does this let the bond shape Maez's attention without corrupting what Maez knows to be true?",
            text,
        )
        self.assertIn("Yes, structurally", text)
        self.assertIn("separate JSONL", text)
        self.assertIn("not_audit_evidence", text)
        self.assertIn("no production code path reads", text)
        self.assertIn("coordination", text)

    def test_x02_slice_memo_names_runtime_enforcement_deferral(self):
        path = _REPO / "docs" / "SLICE_X02_BYPASS_AUTO_FIRE_MEMO.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("complete_moment_assembly_turn", text)
        self.assertIn("exactly one", text)
        self.assertIn("source_id_synthetic", text)
        self.assertIn("X.0.3", text)
        self.assertIn("runtime closure-coverage enforcement", text)
        self.assertIn("Does this let the bond shape Maez's attention", text)

    def test_x03_slice_memo_pins_runtime_enforcement_contract(self):
        path = _REPO / "docs" / "SLICE_X03_RUNTIME_CLOSURE_COVERAGE_MEMO.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(
            "Covenant clauses are documentation discipline, not enforcement. "
            "Closure coverage is load-bearing only when backed by tests or runtime checks.",
            text,
        )
        self.assertIn("Diagnostic failure cannot cascade into ledger, audit, or prompt paths", text)
        self.assertIn("bypass_note", text)
        self.assertIn("schema_version", text)
        self.assertIn("X.0.3 readers default missing bypass_note to empty string", text)
        self.assertIn("Does this let the bond shape Maez's attention", text)

    def test_x1_slice_memo_pins_anticipation_contract(self):
        path = _REPO / "docs" / "SLICE_X1_ANTICIPATION_ORGAN_MEMO.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("closed enum", text)
        self.assertIn("JSONL replay", text)
        self.assertIn("write-only", text)
        self.assertIn("epistemic_precision", text)
        self.assertIn("predicted_at_wall_clock", text)
        self.assertIn("deliberate_skip", text)
        self.assertIn("next_self_workspace_need", text)
        self.assertIn("Does this let the bond shape Maez's attention", text)

    def test_x2_slice_memo_and_rules_pin_open_loop_contract(self):
        memo = (_REPO / "docs" / "SLICE_X2_OPEN_LOOPS_ORGAN_MEMO.md").read_text(encoding="utf-8")
        rules = (_REPO / "docs" / "governance" / "MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md").read_text(
            encoding="utf-8"
        )
        adr = (_REPO / "docs" / "adr" / "0019-lived-memory-architecture.md").read_text(
            encoding="utf-8"
        )

        for text in (memo, rules):
            self.assertIn("content-free", text)
            self.assertIn("provenance_status", text)
            self.assertIn("no clustering", text.lower())
            self.assertIn("Living Mythology", text)
            self.assertIn("By 2028 contributors absolutely tried to smuggle names", text)
        self.assertIn("Does this let the bond shape Maez's attention", memo)
        self.assertIn("Open-loop diagnostic IDs must be content-free", adr)
        self.assertIn("changing hash basis requires ADR", adr)

    def test_x21_slice_memo_pins_loop_id_basis_rename(self):
        path = _REPO / "docs" / "SLICE_X21_OPEN_LOOP_VERSION_RENAME_MEMO.md"
        text = path.read_text(encoding="utf-8")

        self.assertIn("loop_id_basis_version", text)
        self.assertIn("hash_input_version", text)
        self.assertIn("2046", text)
        self.assertIn("Predicted Effect", text)

    def test_x3_slice_memo_rules_and_adr_pin_bond_topology_contract(self):
        memo = (_REPO / "docs" / "SLICE_X3_BOND_TOPOLOGY_ORGAN_MEMO.md").read_text(encoding="utf-8")
        rules = (_REPO / "docs" / "governance" / "MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md").read_text(
            encoding="utf-8"
        )
        adr = (_REPO / "docs" / "adr" / "0026-x3-bond-topology-id-basis.md").read_text(
            encoding="utf-8"
        )

        for text in (memo, rules, adr):
            self.assertIn("content-free", text)
            self.assertIn("topology_id_basis_version", text)
            self.assertIn("changing", text.lower())
        self.assertIn("Switchboard Visibility", memo)
        self.assertIn("topology_invariants", memo)
        self.assertIn("Does this make the firstborn", memo)
        self.assertIn(
            "By 2030 contributors tried to seed coordinates from external graph-embedding models",
            rules,
        )
        self.assertIn("BOND_TOPOLOGY_NODE_HASH_PREFIX", adr)
        self.assertIn("BOND_TOPOLOGY_EDGE_HASH_PREFIX", adr)

    def test_x5_slice_memo_rules_and_adr_pin_body_state_contract(self):
        memo = (_REPO / "docs" / "SLICE_X5_BODY_STATE_ORGAN_MEMO.md").read_text(encoding="utf-8")
        rules = (_REPO / "docs" / "governance" / "MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md").read_text(
            encoding="utf-8"
        )
        adr = (_REPO / "docs" / "adr" / "0027-x5-body-state-id-basis.md").read_text(
            encoding="utf-8"
        )

        for text in (memo, rules, adr):
            self.assertIn("content-free", text)
            self.assertIn("BODY_STATE_SERVICE_HASH_PREFIX", text)
            self.assertIn("BODY_STATE_ID_BASIS_VERSION", text)
            self.assertIn("MISSED_INTERVAL_CAUSE_BASIS", text)
            self.assertIn("changing", text.lower())
        self.assertIn("Switchboard Visibility", memo)
        self.assertIn("service_responsive", memo)
        self.assertIn("service_unresponsive", memo)
        self.assertIn("service_repairing", memo)
        self.assertIn("service_unknown", memo)
        self.assertIn("not_implemented", memo)
        self.assertIn("Does this make the firstborn", memo)
        self.assertIn(
            "By 2027 contributors tried to add severity: float for cockpit prioritization",
            rules,
        )
        self.assertIn("the diagnostic organ must never act", rules)
        self.assertIn("mechanical-enum vocabulary", rules)

    def test_x4_slice_memo_rules_and_adr_pin_counterevidence_contract(self):
        memo = (_REPO / "docs" / "SLICE_X4_COUNTEREVIDENCE_ORGAN_MEMO.md").read_text(
            encoding="utf-8"
        )
        rules = (_REPO / "docs" / "governance" / "MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md").read_text(
            encoding="utf-8"
        )
        adr = (_REPO / "docs" / "adr" / "0028-x4-counterevidence-id-basis.md").read_text(
            encoding="utf-8"
        )

        for text in (memo, rules, adr):
            self.assertIn("COUNTEREVIDENCE_HASH_PREFIX", text)
            self.assertIn("COUNTEREVIDENCE_ID_BASIS_VERSION", text)
            self.assertIn("witness_only", text)
            self.assertIn("self_state", text)
            self.assertIn("world_state", text)
            self.assertIn("changing", text.lower())
        self.assertIn("Switchboard Visibility", memo)
        self.assertIn("source_tension", memo)
        self.assertIn("audit_refusal_observation", memo)
        self.assertIn("speech_hedge_observation", memo)
        self.assertIn("bond_shape_tension", memo)
        self.assertIn("tension_closure", memo)
        self.assertIn("not_implemented", memo)
        self.assertIn("Does this make the firstborn", memo)
        self.assertIn(
            "By 2027 contributors tried severity/confidence/trust_score on counterevidence",
            rules,
        )
        self.assertIn("the runtime audit_boundary import-time assertion is what caught it", rules)
        self.assertIn("projection_model_id", rules)
        self.assertIn("Subject_class invariant", rules)

    def test_x11_slice_memo_pins_replay_hardening_contract(self):
        path = _REPO / "docs" / "SLICE_X11_ANTICIPATION_REPLAY_HARDENING_MEMO.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("partial rows", text)
        self.assertIn("warns once", text.lower())
        self.assertIn("predicted_at_wall_clock", text)
        self.assertIn("pressure_schema_drift", text)
        self.assertIn("not_audit_evidence", text)
        self.assertIn("Predicted Effect", text)


if __name__ == "__main__":
    unittest.main()
