# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""PHASE B part 1 tests for pure consolidation-spine units.

Pins docs/superpowers/specs/2026-07-08-consolidation-spine-v0-design.md
B1 only: deterministic citation lock, span skeleton bookkeeping, and
mechanical-v0 selector. No stores, daemon wiring, services, or LLM calls.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DB_DIR = tempfile.mkdtemp(prefix="maez_test_consolidation_b1_")

from core.consolidation import citation_lock, selector, skeleton  # noqa: E402
from core.ledger import migrate, span_reader, writer  # noqa: E402


def tearDownModule():
    import shutil

    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


_SYSTEM_STAMP = {"taint_labels": ["self_generated"], "privacy_access": "public"}
_OWNER_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}
_SEALED_OWNER_STAMP = {
    "taint_labels": ["owner_utterance"],
    "privacy_access": "sealed_adjacent",
}
_TOOL_STAMP = {"taint_labels": ["self_generated"], "privacy_access": "public"}
_TOOL_RESULT_STAMP = {"taint_labels": ["tool_output"], "privacy_access": "public"}
_WEB_TOOL_RESULT_STAMP = {
    "taint_labels": ["tool_output", "internet_derived"],
    "privacy_access": "public",
}
_PEER_STAMP = {"taint_labels": ["third_party"], "privacy_access": "public"}


def _fresh_db(name: str) -> str:
    path = Path(_TEST_DB_DIR) / f"{name}_{os.urandom(4).hex()}.db"
    migrate.run(str(path))
    return str(path)


def _write_seed_rows(
    db_path: str,
    *,
    include_prebirth: bool = False,
    include_sealed: bool = False,
    include_all_taints: bool = False,
) -> dict[str, str]:
    turn_ids: dict[str, str] = {}
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}), \
         patch("core.ledger.writer.time.time") as time_mock:
        time_mock.side_effect = [1000.0 + i for i in range(20)]
        w = writer.LedgerWriter(db_path)
        try:
            if include_prebirth:
                turn_ids["prebirth"] = w.write_turn(
                    "user_message",
                    "before birth",
                    surface="test",
                    **_OWNER_STAMP,
                )
            turn_ids["birth"] = w.write_turn(
                "system_event",
                '{"event":"birth"}',
                birth_anchor=True,
                **_SYSTEM_STAMP,
            )
            turn_ids["owner"] = w.write_turn(
                "user_message",
                "owner row",
                surface="test",
                **_OWNER_STAMP,
            )
            if include_sealed:
                turn_ids["sealed"] = w.write_turn(
                    "user_message",
                    "sealed adjacent row",
                    surface="test",
                    **_SEALED_OWNER_STAMP,
                )
            if include_all_taints:
                turn_ids["tool_call"] = w.write_turn(
                    "tool_call",
                    "run local command",
                    surface="test",
                    action_proposal={"tool": "shell", "cmd": "printf hi"},
                    **_TOOL_STAMP,
                )
                turn_ids["tool_result"] = w.write_turn(
                    "tool_result",
                    "tool said hi",
                    surface="test",
                    parent_turn_id=turn_ids["tool_call"],
                    audit_verdict={"outcome": "ok"},
                    **_WEB_TOOL_RESULT_STAMP,
                )
                turn_ids["peer"] = w.write_turn(
                    "peer_message_in",
                    "peer row",
                    surface="test",
                    **_PEER_STAMP,
                )
        finally:
            w.close()
    return {key: value for key, value in turn_ids.items() if value is not None}


def _write_owner_row(db_path: str, text: str) -> str:
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
        w = writer.LedgerWriter(db_path)
        try:
            turn_id = w.write_turn(
                "user_message",
                text,
                surface="test",
                **_OWNER_STAMP,
            )
        finally:
            w.close()
    assert turn_id is not None
    return turn_id


def _read_all_rows(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM turns ORDER BY chain_position ASC"
            ).fetchall()
        ]
    finally:
        conn.close()


def _row_by_id(rows: list[dict], turn_id: str) -> dict:
    for row in rows:
        if row["turn_id"] == turn_id:
            return row
    raise AssertionError(f"missing row {turn_id}")


def _span(
    db_path: str,
    after_chain_position: int = 0,
    *,
    include_anchor: bool = True,
) -> dict:
    result = span_reader.read_span(db_path, after_chain_position=after_chain_position)
    span = {
        "after_chain_position": result.after_chain_position,
        "high_water": result.high_water,
        "rows": result.rows,
    }
    if include_anchor:
        span["anchor_chain_position"] = after_chain_position + 1
    return span


def _citation(row: dict) -> dict:
    return {
        "turn_id": row["turn_id"],
        "chain_position": row["chain_position"],
    }


def _artifact(*, citations, taint_labels, text: str = "digest"):
    return {
        "text": text,
        "row_citations": citations,
        "taint_labels": list(taint_labels),
    }


class CitationLockTests(unittest.TestCase):
    def test_accepts_complete_public_citations_at_span_boundaries(self):
        db = _fresh_db("lock_accepts")
        ids = _write_seed_rows(db)
        rows = _read_all_rows(db)
        birth = _row_by_id(rows, ids["birth"])
        owner = _row_by_id(rows, ids["owner"])

        verdict = citation_lock.validate(
            _artifact(
                citations=[_citation(birth), _citation(owner)],
                taint_labels=["owner_utterance", "self_generated"],
            ),
            _span(db),
            db,
        )

        self.assertTrue(verdict.ok)
        self.assertIsNone(verdict.refusal_code)
        self.assertEqual(verdict.offending_citation_ids, ())

    def test_refuses_missing_citation_row(self):
        db = _fresh_db("lock_missing")
        _write_seed_rows(db)

        verdict = citation_lock.validate(
            _artifact(
                citations=[{"turn_id": "not-in-ledger"}],
                taint_labels=["owner_utterance"],
            ),
            _span(db),
            db,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.refusal_code, "citation_missing_row")
        self.assertEqual(verdict.offending_citation_ids, ("not-in-ledger",))

    def test_refuses_row_outside_declared_span(self):
        db = _fresh_db("lock_outside")
        _write_seed_rows(db)
        locked_span = _span(db)
        outside_id = _write_owner_row(db, "after locked span")
        outside = _row_by_id(_read_all_rows(db), outside_id)

        verdict = citation_lock.validate(
            _artifact(
                citations=[_citation(outside)],
                taint_labels=["owner_utterance"],
            ),
            locked_span,
            db,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.refusal_code, "citation_outside_span")
        self.assertEqual(verdict.offending_citation_ids, (outside["turn_id"],))

    def test_refuses_chain_tamper_in_cited_row_body(self):
        db = _fresh_db("lock_tamper")
        ids = _write_seed_rows(db)
        locked_span = _span(db)
        owner = _row_by_id(_read_all_rows(db), ids["owner"])
        conn = sqlite3.connect(db)
        try:
            conn.execute("DROP TRIGGER turns_no_update")
            conn.execute(
                "UPDATE turns SET raw_text = ? WHERE turn_id = ?",
                ("tampered body", owner["turn_id"]),
            )
            conn.commit()
        finally:
            conn.close()

        verdict = citation_lock.validate(
            _artifact(
                citations=[_citation(owner)],
                taint_labels=["owner_utterance"],
            ),
            locked_span,
            db,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.refusal_code, "citation_chain_invalid")
        self.assertEqual(verdict.offending_citation_ids, (owner["turn_id"],))

    def test_refuses_artifact_that_does_not_inherit_cited_taint_union(self):
        db = _fresh_db("lock_taint")
        ids = _write_seed_rows(db)
        owner = _row_by_id(_read_all_rows(db), ids["owner"])

        verdict = citation_lock.validate(
            _artifact(
                citations=[_citation(owner)],
                taint_labels=["self_generated"],
            ),
            _span(db),
            db,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.refusal_code, "taint_not_inherited")
        self.assertEqual(verdict.offending_citation_ids, (owner["turn_id"],))

    def test_refuses_empty_citations(self):
        db = _fresh_db("lock_empty")
        _write_seed_rows(db)

        verdict = citation_lock.validate(
            _artifact(citations=[], taint_labels=["owner_utterance"]),
            _span(db),
            db,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.refusal_code, "citations_empty")
        self.assertEqual(verdict.offending_citation_ids, ())

    def test_refuses_capped_citation_summary_shapes(self):
        db = _fresh_db("lock_capped")
        ids = _write_seed_rows(db)
        owner = _row_by_id(_read_all_rows(db), ids["owner"])

        for citations in (
            [f"{owner['turn_id']},+3"],
            [{"turn_id": owner["turn_id"], "summary": "+2 more"}],
        ):
            with self.subTest(citations=citations):
                verdict = citation_lock.validate(
                    _artifact(
                        citations=citations,
                        taint_labels=["owner_utterance"],
                    ),
                    _span(db),
                    db,
                )
                self.assertFalse(verdict.ok)
                self.assertEqual(verdict.refusal_code, "citations_capped")

    def test_refuses_sealed_adjacent_row(self):
        db = _fresh_db("lock_sealed")
        ids = _write_seed_rows(db, include_sealed=True)
        sealed = _row_by_id(_read_all_rows(db), ids["sealed"])

        verdict = citation_lock.validate(
            _artifact(
                citations=[_citation(sealed)],
                taint_labels=["owner_utterance"],
            ),
            _span(db),
            db,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.refusal_code, "privacy_sealed_row")
        self.assertEqual(verdict.offending_citation_ids, (sealed["turn_id"],))

    def test_refuses_citation_below_birth_anchor_by_position(self):
        db = _fresh_db("lock_anchor")
        ids = _write_seed_rows(db, include_prebirth=True)
        rows = _read_all_rows(db)
        prebirth = _row_by_id(rows, ids["prebirth"])
        birth = _row_by_id(rows, ids["birth"])
        span = _span(db)
        span["anchor_chain_position"] = birth["chain_position"]

        verdict = citation_lock.validate(
            _artifact(
                citations=[_citation(prebirth)],
                taint_labels=["owner_utterance"],
            ),
            span,
            db,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.refusal_code, "lived_status_unanchored")
        self.assertEqual(verdict.offending_citation_ids, (prebirth["turn_id"],))

    def test_refuses_when_birth_anchor_position_is_not_declared(self):
        db = _fresh_db("lock_anchor_missing")
        ids = _write_seed_rows(db, include_prebirth=True)
        prebirth = _row_by_id(_read_all_rows(db), ids["prebirth"])

        verdict = citation_lock.validate(
            _artifact(
                citations=[_citation(prebirth)],
                taint_labels=["owner_utterance"],
            ),
            _span(db, include_anchor=False),
            db,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.refusal_code, "lived_status_unanchored")
        self.assertEqual(verdict.offending_citation_ids, (prebirth["turn_id"],))

    def test_valid_later_span_accepts_s2_rows_without_genesis_prefix(self):
        db = _fresh_db("lock_later_s2")
        ids = _write_seed_rows(db)
        rows = _read_all_rows(db)
        birth = _row_by_id(rows, ids["birth"])
        owner = _row_by_id(rows, ids["owner"])
        result = span_reader.read_span(
            db,
            after_chain_position=birth["chain_position"],
        )
        later_span = {
            "after_chain_position": result.after_chain_position,
            "high_water": result.high_water,
            "anchor_chain_position": birth["chain_position"],
            "rows": result.rows,
        }

        verdict = citation_lock.validate(
            _artifact(
                citations=[_citation(owner)],
                taint_labels=["owner_utterance"],
            ),
            later_span,
            result,
        )

        self.assertTrue(verdict.ok)

    def test_refuses_oversized_artifact_text(self):
        db = _fresh_db("lock_oversized")
        ids = _write_seed_rows(db)
        owner = _row_by_id(_read_all_rows(db), ids["owner"])

        verdict = citation_lock.validate(
            _artifact(
                text="x" * (citation_lock.MAX_ARTIFACT_TEXT_CHARS + 1),
                citations=[_citation(owner)],
                taint_labels=["owner_utterance"],
            ),
            _span(db),
            db,
        )

        self.assertFalse(verdict.ok)
        self.assertEqual(verdict.refusal_code, "artifact_oversized")
        self.assertEqual(verdict.offending_citation_ids, ())

    def test_taint_superset_property_over_cited_rows(self):
        db = _fresh_db("lock_taint_property")
        ids = _write_seed_rows(db, include_all_taints=True)
        rows = _read_all_rows(db)
        cited = [
            _row_by_id(rows, ids["owner"]),
            _row_by_id(rows, ids["birth"]),
            _row_by_id(rows, ids["tool_result"]),
            _row_by_id(rows, ids["peer"]),
        ]
        citations = [_citation(row) for row in cited]
        required_labels = {
            label
            for row in cited
            for label in json.loads(row["taint_labels_json"])
        }

        ok = citation_lock.validate(
            _artifact(
                citations=citations,
                taint_labels=sorted(required_labels),
            ),
            _span(db),
            db,
        )
        self.assertTrue(ok.ok)

        for missing in sorted(required_labels):
            with self.subTest(missing=missing):
                verdict = citation_lock.validate(
                    _artifact(
                        citations=citations,
                        taint_labels=sorted(required_labels - {missing}),
                    ),
                    _span(db),
                    db,
                )
                self.assertFalse(verdict.ok)
                self.assertEqual(verdict.refusal_code, "taint_not_inherited")


def _row(
    position: int,
    timestamp: float,
    *,
    turn_kind: str = "user_message",
    surface: str = "telegram",
    action_proposal=None,
    audit_verdict=None,
    raw_text: str = "",
) -> dict:
    return {
        "turn_id": f"turn-{position}",
        "chain_position": position,
        "timestamp": timestamp,
        "turn_kind": turn_kind,
        "surface": surface,
        "action_proposal_json": (
            json.dumps(action_proposal, sort_keys=True) if action_proposal is not None else None
        ),
        "audit_verdict_json": (
            json.dumps(audit_verdict, sort_keys=True) if audit_verdict is not None else None
        ),
        "raw_text": raw_text,
    }


class SkeletonTests(unittest.TestCase):
    def test_counts_synthetic_three_day_span_without_interpretive_scores(self):
        day = 24 * 60 * 60
        base = 1_700_000_000.0
        rows = [
            _row(1, base, surface="telegram"),
            _row(
                2,
                base + 60,
                turn_kind="tool_call",
                surface="telegram",
                action_proposal={"tool": "shell", "cmd": "ls"},
            ),
            _row(
                3,
                base + 120,
                turn_kind="tool_result",
                surface="telegram",
                audit_verdict={"outcome": "ok"},
            ),
            _row(
                4,
                base + day + 60,
                turn_kind="tool_result",
                surface="daemon",
                audit_verdict={"outcome": "error"},
                raw_text="error one",
            ),
            _row(
                5,
                base + day + 120,
                turn_kind="tool_result",
                surface="daemon",
                audit_verdict={"outcome": "error"},
                raw_text="error two",
            ),
            _row(6, base + 2 * day + 60, surface="web"),
        ]

        got = skeleton.build(rows)

        self.assertEqual(got.row_count, 6)
        self.assertEqual(got.turn_kind_counts["user_message"], 2)
        self.assertEqual(got.turn_kind_counts["tool_result"], 3)
        self.assertEqual(got.tool_proposal_count, 1)
        self.assertEqual(got.tool_outcome_counts, {"error": 2, "ok": 1})
        self.assertEqual(got.surface_counts, {"daemon": 2, "telegram": 3, "web": 1})
        self.assertEqual(sum(got.hour_counts.values()), 6)
        self.assertEqual(
            [
                (
                    boundary.before_chain_position,
                    boundary.after_chain_position,
                )
                for boundary in got.session_boundaries
            ],
            [(3, 4), (5, 6)],
        )
        self.assertEqual(len(got.error_clusters), 1)
        self.assertEqual(got.error_clusters[0].start_chain_position, 4)
        self.assertEqual(got.error_clusters[0].end_chain_position, 5)
        self.assertFalse(any("score" in field for field in got.__dataclass_fields__))


class SelectorTests(unittest.TestCase):
    @staticmethod
    def _depth_allocation(result: selector.SelectionResult) -> tuple[tuple[str, str], ...]:
        return tuple(
            (episode.episode_key, episode.selection_depth)
            for episode in result.episodes
        )

    def test_selector_is_deterministic_and_respects_coverage_row_cap(self):
        rows = [
            _row(1, 1000.0),
            _row(2, 1060.0),
            _row(3, 4000.0, audit_verdict={"outcome": "ok"}),
            _row(4, 4060.0, audit_verdict={"outcome": "error"}, raw_text="error"),
            _row(5, 4120.0),
            _row(6, 4180.0),
            _row(7, 8000.0, audit_verdict={"outcome": "ok"}),
            _row(8, 8060.0),
            _row(9, 8120.0),
        ]

        first = selector.select(rows, deep_row_cap=6)
        second = selector.select(rows, deep_row_cap=6)

        self.assertEqual(first, second)
        self.assertEqual(first.selection_mode, "mechanical_v0")
        self.assertEqual(len(first.episodes), 3)
        self.assertEqual(first.coverage_order_episode_keys, ("cp1-cp2", "cp3-cp6", "cp7-cp9"))
        self.assertEqual(first.deep_row_budget, 6)
        self.assertEqual(
            self._depth_allocation(first),
            (
                ("cp1-cp2", "deep"),
                ("cp3-cp6", "deep"),
                ("cp7-cp9", "shallow"),
            ),
        )

    def test_selector_domain_swap_keeps_identical_depth_allocation(self):
        base = 1_700_000_000.0
        rows_tool_second = [
            _row(1, base),
            _row(2, base + 60),
            _row(3, base + 4000, turn_kind="tool_result", audit_verdict={"outcome": "error"}),
            _row(4, base + 4060, turn_kind="tool_result", audit_verdict={"outcome": "ok"}),
            _row(5, base + 8000),
            _row(6, base + 8060),
            _row(7, base + 12000),
            _row(8, base + 12060),
        ]
        rows_tool_fourth = [
            _row(1, base),
            _row(2, base + 60),
            _row(3, base + 4000),
            _row(4, base + 4060),
            _row(5, base + 8000),
            _row(6, base + 8060),
            _row(7, base + 12000, turn_kind="tool_result", audit_verdict={"outcome": "error"}),
            _row(8, base + 12060, turn_kind="tool_result", audit_verdict={"outcome": "ok"}),
        ]

        second_tool = selector.select(rows_tool_second)
        fourth_tool = selector.select(rows_tool_fourth)

        self.assertEqual(
            self._depth_allocation(second_tool),
            self._depth_allocation(fourth_tool),
        )

    def test_selector_rotation_changes_coverage_start_without_content_signals(self):
        base = 1_700_000_000.0
        rows = [
            _row(1, base),
            _row(2, base + 60),
            _row(3, base + 4000),
            _row(4, base + 4060),
            _row(5, base + 8000),
            _row(6, base + 8060),
            _row(7, base + 12000),
            _row(8, base + 12060),
        ]

        first_window = selector.select(rows, deep_row_cap=4, rotation_offset=0)
        second_window = selector.select(rows, deep_row_cap=4, rotation_offset=2)

        self.assertEqual(
            self._depth_allocation(first_window),
            (
                ("cp1-cp2", "deep"),
                ("cp3-cp4", "deep"),
                ("cp5-cp6", "shallow"),
                ("cp7-cp8", "shallow"),
            ),
        )
        self.assertEqual(
            self._depth_allocation(second_window),
            (
                ("cp1-cp2", "shallow"),
                ("cp3-cp4", "shallow"),
                ("cp5-cp6", "deep"),
                ("cp7-cp8", "deep"),
            ),
        )

    def test_selector_source_has_no_content_ranking_signals(self):
        source = Path(selector.__file__).read_text(encoding="utf-8")

        self.assertNotIn("_rank_key", source)
        self.assertNotIn("tool_outcome_density", source)
        self.assertNotIn("error_cluster_present", source)

    def test_selector_handles_single_row_span(self):
        got = selector.select([_row(1, 1000.0)], deep_row_cap=1)

        self.assertEqual(got.selection_mode, "mechanical_v0")
        self.assertEqual(len(got.episodes), 1)
        self.assertEqual(got.episodes[0].episode_key, "cp1-cp1")
        self.assertEqual(got.episodes[0].selection_depth, "deep")

    def test_selector_handles_ten_thousand_row_span_as_one_episode(self):
        rows = [_row(i, 1000.0 + i) for i in range(1, 10_001)]

        got = selector.select(rows, deep_row_cap=1)

        self.assertEqual(len(got.episodes), 1)
        self.assertEqual(got.episodes[0].row_count, 10_000)
        self.assertEqual(got.episodes[0].selection_depth, "deep")
        self.assertEqual(got.coverage_order_episode_keys, ("cp1-cp10000",))


if __name__ == "__main__":
    unittest.main()
