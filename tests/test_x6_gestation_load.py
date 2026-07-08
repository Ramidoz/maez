# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Slice X.6 - gestation load and moment-arc readability rehearsal."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent
_TEST_DIR = Path(tempfile.mkdtemp(prefix="maez_test_x6_"))


def tearDownModule():
    import shutil

    shutil.rmtree(_TEST_DIR, ignore_errors=True)


def _fresh_db(name: str) -> Path:
    from core.ledger import migrate

    path = _TEST_DIR / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return path


def _count_stage(db_path: Path, stage: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM turns WHERE lifecycle_stage = ?",
                (stage,),
            ).fetchone()[0]
        )


def _count_turns(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0])


def _chain_head(db_path: Path) -> str | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM meta WHERE key='last_chain_hash'"
        ).fetchone()
    return str(row[0]) if row else None


class RehearsalLedgerIsolationTests(unittest.TestCase):
    def test_rehearsal_writer_rejects_non_sidecar_path_at_construction_time(self):
        db = _fresh_db("production_like")
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from core.ledger.writer import LedgerWriter; "
                    f"LedgerWriter({str(db)!r}, rehearsal_mode=True)"
                ),
            ],
            cwd=_REPO,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(probe.returncode, 0)
        self.assertIn("rehearsal ledger writers must use", probe.stderr + probe.stdout)

    def test_production_writer_rejects_rehearsal_lifecycle_stage_at_write_time(self):
        from core.ledger import writer

        db = _fresh_db("production_refusal")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(str(db))
            try:
                with self.assertRaisesRegex(ValueError, "rehearsal"):
                    w.write_turn(
                        "user_message",
                        "synthetic rehearsal row",
                        lifecycle_stage="rehearsal",
                        taint_labels=["self_generated"],
                        privacy_access="public",
                    )
            finally:
                w.close()

        self.assertEqual(_count_stage(db, "rehearsal"), 0)

    def test_rehearsal_writer_requires_explicit_rehearsal_lifecycle_stage(self):
        from core.ledger import writer

        rehearsal_root = _TEST_DIR / "logs" / "rehearsal"
        db = rehearsal_root / "x6_missing_stage" / "ledger.db"
        db.parent.mkdir(parents=True)
        from core.ledger import migrate

        migrate.run(str(db))
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(
                str(db),
                rehearsal_mode=True,
                rehearsal_root=rehearsal_root,
            )
            try:
                with self.assertRaisesRegex(ValueError, "requires lifecycle_stage"):
                    w.write_turn(
                        "user_message",
                        "missing stage",
                        taint_labels=["self_generated"],
                        privacy_access="public",
                    )
            finally:
                w.close()

    def test_runner_rejects_non_x6_run_id_before_creating_sidecar_db(self):
        from scripts.x6_gestation_load import run_synthetic_load

        rehearsal_root = _TEST_DIR / "logs" / "rehearsal"

        with self.assertRaisesRegex(ValueError, "run_id"):
            run_synthetic_load(
                run_id="not_x6",
                turn_count=1,
                rehearsal_root=rehearsal_root,
                production_ledger_path=_fresh_db("production_bad_run_id"),
            )

        self.assertFalse((rehearsal_root / "not_x6" / "ledger.db").exists())

    def test_synthetic_load_writes_only_sidecar_rehearsal_rows(self):
        from scripts.x6_gestation_load import run_synthetic_load

        production_db = _fresh_db("production_clean")
        before_count = _count_turns(production_db)
        before_head = _chain_head(production_db)
        rehearsal_root = _TEST_DIR / "logs" / "rehearsal"

        report = run_synthetic_load(
            run_id="x6_test_sidecar",
            turn_count=6,
            rehearsal_root=rehearsal_root,
            production_ledger_path=production_db,
        )

        sidecar_db = Path(report["ledger_path"])
        self.assertEqual(sidecar_db, rehearsal_root / "x6_test_sidecar" / "ledger.db")
        self.assertEqual(_count_stage(sidecar_db, "rehearsal"), 6)
        self.assertEqual(_count_stage(production_db, "rehearsal"), 0)
        self.assertEqual(_count_turns(production_db), before_count)
        self.assertEqual(_chain_head(production_db), before_head)
        self.assertEqual(report["corpus_kind"], "rehearsal")
        self.assertIs(report["not_lived_history"], True)
        self.assertLess(report["total_bytes"], 50 * 1024 * 1024)

        metrics = [
            json.loads(line)
            for line in Path(report["metrics_path"]).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(metrics)
        for metric in metrics:
            self.assertEqual(metric["audit_boundary"], "not_audit_evidence")
            self.assertEqual(metric["corpus_kind"], "rehearsal")
            self.assertIs(metric["not_lived_history"], True)
            self.assertIn("slice_memo_sha256", metric)
            self.assertIn("expires_at", metric)


class X6ReadabilityAndInvariantTests(unittest.TestCase):
    def test_cross_organ_invariants_are_stable_before_and_after_load(self):
        from scripts.x6_gestation_load import collect_cross_organ_invariants, run_synthetic_load

        before = collect_cross_organ_invariants()
        run_synthetic_load(
            run_id="x6_test_invariants",
            turn_count=4,
            rehearsal_root=_TEST_DIR / "logs" / "rehearsal",
            production_ledger_path=_fresh_db("production_invariants"),
        )
        after = collect_cross_organ_invariants()

        self.assertEqual(before, after)
        self.assertTrue(before["audit_boundary_uniform"])
        self.assertTrue(before["hash_prefixes_unique"])
        self.assertTrue(before["write_only_tests_present"])
        self.assertTrue(before["basis_versions_monotonic"])

    def test_expected_fire_distinguishes_honest_absence_from_broken_silence(self):
        from scripts.x6_gestation_load import ExpectedFireFailure, assert_expected_fire

        panel_row = {
            "turn_id": "turn-1",
            "organ_states": {
                "anticipation": "not_observed",
                "open_loops": "emitted_value",
            },
        }

        assert_expected_fire(panel_row, {"anticipation": False, "open_loops": True})
        with self.assertRaisesRegex(ExpectedFireFailure, "anticipation"):
            assert_expected_fire(panel_row, {"anticipation": True, "open_loops": True})

    def test_panel_watermark_visible_and_slot_states_not_interpolated(self):
        from scripts.x6_gestation_load import render_readability_panel

        out_path = _TEST_DIR / "panel.txt"
        panel = render_readability_panel(
            rows=[
                {
                    "turn_id": "turn-1",
                    "audit_boundary": "not_audit_evidence",
                    "corpus_kind": "replay",
                    "not_lived_history": False,
                    "expires_at": "2026-08-07T00:00:00Z",
                    "slice_memo_sha256": "a" * 64,
                    "thesis_doc_sha256": "b" * 64,
                    "organ_states": {
                        "anticipation": "not_observed",
                        "open_loops": "emitted_null",
                        "bond_topology": "not_observed",
                        "body_state": "not_observed",
                        "counterevidence": "not_observed",
                    },
                }
            ],
            output_path=out_path,
            turn_id_start="turn-1",
            turn_id_end="turn-1",
        )

        text = out_path.read_text(encoding="utf-8")
        self.assertIn("audit_boundary: not_audit_evidence", text)
        self.assertIn("anticipation=not_observed", text)
        self.assertIn("open_loops=emitted_null", text)
        self.assertIn("expires_at: 2026-08-07T00:00:00Z", text)
        self.assertIn("slice_memo_sha256:", text)
        self.assertIn("thesis_doc_sha256:", text)
        self.assertNotIn("anticipation=emitted_null", text)
        self.assertEqual(panel["corpus_kind"], "replay")
        self.assertIs(panel["not_lived_history"], False)

        with self.assertRaisesRegex(ValueError, "missing organ state"):
            render_readability_panel(
                rows=[
                    {
                        "turn_id": "turn-2",
                        "audit_boundary": "not_audit_evidence",
                        "corpus_kind": "replay",
                        "not_lived_history": False,
                        "expires_at": "2026-08-07T00:00:00Z",
                        "slice_memo_sha256": "a" * 64,
                        "thesis_doc_sha256": "b" * 64,
                        "organ_states": {"anticipation": "not_observed"},
                    }
                ],
                output_path=_TEST_DIR / "bad_panel.txt",
                turn_id_start="turn-2",
                turn_id_end="turn-2",
            )

    def test_shape_cardinality_counts_distinct_panel_shapes(self):
        from scripts.x6_gestation_load import diagnostic_shape_cardinality

        count = diagnostic_shape_cardinality(
            [
                {"organ_states": {"anticipation": "emitted_value", "open_loops": "emitted_value"}},
                {"organ_states": {"anticipation": "emitted_value", "open_loops": "emitted_value"}},
                {"organ_states": {"anticipation": "not_observed", "open_loops": "emitted_value"}},
            ]
        )

        self.assertEqual(count, 2)

    def test_replay_readability_accepts_explicit_turn_id_range(self):
        from core.ledger import writer
        from scripts.x6_gestation_load import run_replay_readability

        db = _fresh_db("replay_range")
        turn_ids: list[str] = []
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = writer.LedgerWriter(str(db))
            try:
                for index in range(6):
                    turn_ids.append(
                        w.write_turn(
                            "user_message",
                            f"turn-{index}",
                            surface="x6_rehearsal",
                            taint_labels=["self_generated"],
                            privacy_access="public",
                        ) or ""
                    )
            finally:
                w.close()

        report = run_replay_readability(
            run_id="x6_test_replay_range",
            rehearsal_root=_TEST_DIR / "logs" / "rehearsal",
            ledger_path=db,
            turn_id_start=turn_ids[1],
            turn_id_end=turn_ids[4],
        )

        self.assertEqual(report["turn_id_start"], turn_ids[1])
        self.assertEqual(report["turn_id_end"], turn_ids[4])
        self.assertEqual(report["turn_count"], 4)

    def test_x6_helpers_are_not_imported_by_production_paths(self):
        import ast

        roots = ["core", "daemon", "skills", "cli"]
        hits: list[str] = []
        for root_name in roots:
            for path in (_REPO / root_name).rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                rel = path.relative_to(_REPO).as_posix()
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module == "scripts.x6_gestation_load":
                        hits.append(rel)
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name == "scripts.x6_gestation_load":
                                hits.append(rel)

        self.assertEqual(hits, [])

    def test_x6_slice_memo_and_rules_pin_rehearsal_contract(self):
        memo = (
            _REPO / "docs" / "slices" / "organs" / "x6-gestation-load-and-readability.md"
        ).read_text(encoding="utf-8")
        rules = (
            _REPO / "docs" / "governance" / "MOMENT_ASSEMBLY_DIAGNOSTIC_RULES.md"
        ).read_text(encoding="utf-8")

        for text in (memo, rules):
            self.assertIn("Rehearsal Corpora", text)
            self.assertIn("audit_boundary: not_audit_evidence", text)
            self.assertIn("expires_at", text)
            self.assertIn("not_lived_history", text)
            self.assertIn("No rehearsal turn is written to turns", text)
        self.assertIn("Switchboard Visibility", memo)
        self.assertIn("ledger-stability", memo)
        self.assertIn("diagnostic-pressure", memo)
        self.assertIn("readability-panel", memo)
        self.assertIn("By 2026-09-03 a rehearsal harness was re-pointed", rules)
        self.assertIn("By 2028-02-19 a rehearsal_origin flag was stripped", rules)
