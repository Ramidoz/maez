# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice X.0 - moment assembly diagnostic contract."""

from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path


_REPO = Path(__file__).resolve().parent.parent
_TEST_DIR = Path(tempfile.mkdtemp(prefix="maez_test_moment_assembly_"))
_MOMENT_ASSEMBLY_SYMBOLS = frozenset(
    {
        "AUDIT_BOUNDARY",
        "BYPASS_REASONS",
        "DiagnosticState",
        "MOMENT_ASSEMBLY_DIAGNOSTIC_SCHEMA",
        "build_bypassed_record",
        "build_diagnostic_record",
        "build_slot",
        "complete_moment_assembly_turn",
        "moment_assembly_diagnostic",
        "validate_record",
        "validate_slot",
        "write_bypassed_record",
        "write_diagnostic_record",
    }
)
_ALLOWED_PRODUCTION_COMPLETION_CALLS = {
    ("daemon/maez_daemon.py", "complete_moment_assembly_turn"),
    ("cli/maez_chat.py", "complete_moment_assembly_turn"),
    ("skills/web_interface.py", "complete_moment_assembly_turn"),
    ("skills/telegram_voice.py", "complete_moment_assembly_turn"),
}
_COMPLETION_KWARGS = {
    "surface",
    "turn_id",
    "diagnostic_observed",
    "bypass_reason",
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

    def test_moment_assembly_diagnostic_has_only_path_symbol_allowlisted_callers(self):
        allowed = {
            "core/cognition/moment_assembly_diagnostic.py",
            "scripts/moment_assembly_probe.py",
            "tests/test_moment_assembly_diagnostic.py",
        }
        hits = _find_moment_assembly_symbol_hits(
            _production_python_paths(),
            allowed_paths=allowed,
            allowed_path_symbols=_ALLOWED_PRODUCTION_COMPLETION_CALLS,
        )
        self.assertEqual(hits, set())

    def test_allowlisted_completion_callers_are_present_and_use_same_kwargs(self):
        for rel, symbol in sorted(_ALLOWED_PRODUCTION_COMPLETION_CALLS):
            path = _REPO / rel
            calls = _completion_call_nodes(path)
            self.assertGreaterEqual(
                len(calls),
                1,
                f"{rel} must call {symbol}",
            )
            for call in calls:
                self.assertEqual(
                    {kw.arg for kw in call.keywords},
                    _COMPLETION_KWARGS,
                    f"{rel} must use the locked completion kwarg shape",
                )

    def test_web_completion_hook_is_owner_bridge_gated(self):
        src = (_REPO / "skills" / "web_interface.py").read_text(encoding="utf-8")
        call_idx = src.find("complete_moment_assembly_turn(")
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
        self.assertNotIn("complete_moment_assembly_turn", src)

    def test_telegram_recovery_synthesis_path_is_covered(self):
        src = (_REPO / "skills" / "telegram_voice.py").read_text(encoding="utf-8")
        recovery_idx = src.find("_synthesize_recovery_reply(")
        self.assertGreater(recovery_idx, 0, "recovery synthesis path must exist")
        hook_idx = src.find("complete_moment_assembly_turn(", recovery_idx)
        self.assertGreater(
            hook_idx,
            recovery_idx,
            "telegram recovery synthesis path must close with completion hook",
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
        self.assertIn("complete_moment_assembly_turn", text)
        self.assertIn("bypass_reason", text)
        self.assertIn("source_id_synthetic", text)
        self.assertIn("X.0.3", text)

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


if __name__ == "__main__":
    unittest.main()
