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
        "build_diagnostic_record",
        "build_surprise_delta_slot",
        "build_slot",
        "complete_moment_assembly_turn",
        "expire_latest_anticipation",
        "find_latest_unreconciled_anticipation",
        "mark_current_moment_assembly_observed",
        "moment_assembly_turn",
        "moment_assembly_diagnostic",
        "normalize_diagnostic_record",
        "reconcile_latest_anticipation",
        "validate_record",
        "validate_slot",
        "write_bypassed_record",
        "write_anticipation_record",
        "write_diagnostic_record",
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
            build_diagnostic_record,
            build_slot,
        )

        record = build_diagnostic_record(
            surface="probe",
            source_ids=["turn-1"],
            bond_topology={
                "euclidean": build_slot(
                    "error",
                    value=None,
                    source_ids=[],
                    error_class="euclidean_failure",
                ),
                "poincare": build_slot(
                    "emitted_value",
                    value={"coordinates": [0.1, 0.2]},
                    source_ids=["turn-1"],
                ),
            },
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
            }:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("find_latest_unreconciled_anticipation", text, rel)
            self.assertNotIn("reconcile_latest_anticipation", text, rel)
            self.assertNotIn('["anticipation"]', text, rel)

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
