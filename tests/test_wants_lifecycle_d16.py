# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Decision 31 / ADR 0036 — Wants Lifecycle v1 tests.

These tests intentionally mirror the 87-test RED contract in
docs/slices/d16-wants-lifecycle/spec.md. The slice is a silent-harm surface:
if paperwork passes while a hard want disappears from active view, the test
suite failed its real job.
"""

from __future__ import annotations

import contextlib
import io
import logging
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


from core.evolution import wants as wants_mod
from core.evolution.wants import Wants


def _tmp_store() -> tuple[Wants, tempfile.TemporaryDirectory]:
    td = tempfile.TemporaryDirectory()
    return Wants(Path(td.name) / "wants.db"), td


def _birth_evidence() -> dict:
    return {
        "birth_event_id": 1,
        "birth_continuity_id": "birth-cid",
        "reason": "test birth",
    }


def _satisfied_evidence(**overrides: object) -> dict:
    data = {
        "basis": "owner_confirmed",
        "source": "owner",
        "summary": "The external object was met.",
        "external_object_ref": "object:blanket",
    }
    data.update(overrides)
    return data


def _external_event_evidence(**overrides: object) -> dict:
    data = {
        "basis": "external_event_verified",
        "source": "event-log",
        "summary": "The external event happened.",
        "external_event_ref": "event:123",
    }
    data.update(overrides)
    return data


def _refined_evidence(**overrides: object) -> dict:
    data = {
        "correction_kind": "typo",
        "supersedes_event_id": 1,
        "prior_statement_hash": "sha256:abc",
        "operator_rationale": "Typo correction.",
    }
    data.update(overrides)
    return data


def _returned_evidence(**overrides: object) -> dict:
    data = {
        "basis": "owner_attested_recurring_want",
        "source": "owner",
        "summary": "The same want returned.",
    }
    data.update(overrides)
    return data


def _create(store: Wants, statement: str = "I want a quiet corner.") -> str:
    return store.record_event(statement=statement, evidence={"seed": True})


def _latest_event_id(store: Wants, want_id: str) -> int:
    current = store.current_state(want_id)
    assert current is not None
    return int(current["event_id"])


def _refine(store: Wants, want_id: str, statement: str) -> str:
    return store.record_event(
        want_id=want_id,
        event_type="refined",
        statement=statement,
        evidence=_refined_evidence(
            supersedes_event_id=_latest_event_id(store, want_id),
        ),
    )


def _satisfy(store: Wants, want_id: str, statement: str) -> str:
    return store.record_event(
        want_id=want_id,
        event_type="satisfied",
        statement=statement,
        evidence=_satisfied_evidence(),
    )


def _return(store: Wants, want_id: str, statement: str) -> str:
    return store.record_event(
        want_id=want_id,
        event_type="returned",
        statement=statement,
        evidence=_returned_evidence(),
    )


def _raw_insert_abandoned(store: Wants, want_id: str, statement: str) -> None:
    with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
        conn.execute(
            "INSERT INTO want_events "
            "(ts, want_id, event_type, statement, topic, provenance, evidence_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (999.0, want_id, "abandoned", statement, None, "legacy", "{}"),
        )
        conn.commit()


class WantsLifecycleD16Test(unittest.TestCase):
    def setUp(self) -> None:
        wants_mod._reset_diagnostics_for_tests()

    def test_01_event_types_include_all_d16_members(self):
        self.assertEqual(
            wants_mod.EVENT_TYPES,
            frozenset({
                "created",
                "first_lived",
                "refined",
                "satisfied",
                "returned",
                "abandoned",
            }),
        )

    def test_02_forbidden_event_or_state_strings_are_pinned(self):
        self.assertEqual(
            wants_mod.FORBIDDEN_EVENT_OR_STATE_STRINGS,
            frozenset({
                "completed",
                "done",
                "executed",
                "terminated",
                "deleted",
                "dissolved",
                "self_ended",
                "left",
                "removed",
            }),
        )

    def test_03_forbidden_strings_are_disjoint_from_vocabularies(self):
        forbidden = wants_mod.FORBIDDEN_EVENT_OR_STATE_STRINGS
        derived = frozenset({"active", "terminal_current_goal"})
        self.assertFalse(forbidden & wants_mod.EVENT_TYPES)
        self.assertFalse(forbidden & wants_mod.ACTIVE_EVENT_TYPES)
        self.assertFalse(forbidden & wants_mod.TERMINAL_CURRENT_GOAL_EVENT_TYPES)
        self.assertFalse(forbidden & derived)

    def test_04_forbidden_event_strings_get_invalid_event_errors(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        for event_type in wants_mod.FORBIDDEN_EVENT_OR_STATE_STRINGS:
            with self.subTest(event_type=event_type):
                with self.assertRaisesRegex(ValueError, "event_type"):
                    store.record_event(statement="I want x.", event_type=event_type)

    def test_05_first_lived_with_explicit_api_is_rejected(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaisesRegex(ValueError, "first_lived.*explicit_api"):
            store.record_event(
                statement="I want to live.",
                event_type="first_lived",
                provenance="explicit_api",
                evidence=_birth_evidence(),
            )

    def test_06_first_lived_with_birth_producer_plus_birth_evidence_is_accepted(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = store.record_event(
            statement="I want to live.",
            event_type="first_lived",
            provenance="birth_producer",
            evidence=_birth_evidence(),
        )
        self.assertEqual(store.current_state(wid)["event_type"], "first_lived")

    def test_07_first_lived_with_birth_producer_missing_birth_evidence_rejected(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaisesRegex(ValueError, "birth"):
            store.record_event(
                statement="I want to live.",
                event_type="first_lived",
                provenance="birth_producer",
                evidence={"birth_event_id": 1},
            )

    def test_08_abandoned_with_explicit_api_is_rejected(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaisesRegex(ValueError, "abandoned.*explicit_api"):
            store.record_event(statement="I want quiet.", event_type="abandoned")

    def test_09_abandoned_with_any_v1_provenance_is_rejected(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        for provenance in {"explicit_api", "birth_producer"}:
            with self.subTest(provenance=provenance):
                with self.assertRaisesRegex(ValueError, "abandoned"):
                    store.record_event(
                        statement="I want quiet.",
                        event_type="abandoned",
                        provenance=provenance,
                    )

    def test_10_abandoned_with_novel_non_v1_provenance_is_rejected(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaisesRegex(ValueError, "abandoned.*future"):
            store.record_event(
                statement="I want quiet.",
                event_type="abandoned",
                provenance="future_reflection",
            )

    def test_11_reserved_maez_reflection_producer_is_rejected_in_v1(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaisesRegex(ValueError, "maez_reflection_producer"):
            store.record_event(
                statement="I want quiet.",
                provenance="maez_reflection_producer",
            )

    def test_12_pair_validation_helper_rejects_missing_map_entry_without_keyerror(self):
        malformed = {"created": frozenset({"explicit_api"})}
        with self.assertRaisesRegex(ValueError, "returned.*explicit_api"):
            wants_mod._validate_event_provenance_pair(
                "returned",
                "explicit_api",
                allowed_map=malformed,
                increment=False,
            )

    def test_13_event_type_allowed_provenances_covers_event_types(self):
        self.assertEqual(set(wants_mod.EVENT_TYPE_ALLOWED_PROVENANCES), wants_mod.EVENT_TYPES)

    def test_14_created_with_reused_want_id_is_rejected(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "already exists"):
            store.record_event(statement="I want another.", want_id=wid)

    def test_15_created_rejects_recursive_forbidden_action_evidence_keys(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaisesRegex(ValueError, "plan_steps"):
            store.record_event(
                statement="I want quiet.",
                evidence={"voice": [{"plan_steps": ["do x"]}]},
            )

    def test_16_refined_requires_existing_want_id(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaisesRegex(ValueError, "exist"):
            store.record_event(
                want_id="missing",
                event_type="refined",
                statement="I want quiet now.",
                evidence=_refined_evidence(),
            )

    def test_17_refined_rejects_same_statement_after_whitespace_normalization(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want quiet.")
        with self.assertRaisesRegex(ValueError, "same statement"):
            _refine(store, wid, "I want quiet.")

    def test_18_refined_rejects_same_statement_with_whitespace_runs(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want quiet.")
        with self.assertRaisesRegex(ValueError, "same statement"):
            _refine(store, wid, " I   want\tquiet. ")

    def test_19_refined_after_active_latest_is_accepted_with_correction_evidence(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        _refine(store, wid, "I want quiet.")
        self.assertEqual(store.current_state(wid)["event_type"], "refined")

    def test_20_refined_after_satisfied_is_rejected_use_returned_first(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want a quiet corner.")
        _satisfy(store, wid, "I want a quiet corner.")
        with self.assertRaisesRegex(ValueError, "returned"):
            store.record_event(
                want_id=wid,
                event_type="refined",
                statement="I want a quiet room.",
                evidence=_refined_evidence(
                    supersedes_event_id=_latest_event_id(store, wid)
                ),
            )

    def test_21_refined_rejects_missing_correction_kind(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        evidence = _refined_evidence()
        evidence.pop("correction_kind")
        with self.assertRaisesRegex(ValueError, "correction_kind"):
            store.record_event(
                want_id=wid,
                event_type="refined",
                statement="I want quiet.",
                evidence=evidence,
            )

    def test_22_refined_rejects_semantic_or_expressive_correction_kind(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        with self.assertRaisesRegex(ValueError, "correction_kind"):
            store.record_event(
                want_id=wid,
                event_type="refined",
                statement="I want quiet.",
                evidence=_refined_evidence(correction_kind="semantic"),
            )

    def test_23_refined_requires_supersedes_event_id(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        evidence = _refined_evidence()
        evidence.pop("supersedes_event_id")
        with self.assertRaisesRegex(ValueError, "supersedes_event_id"):
            store.record_event(
                want_id=wid,
                event_type="refined",
                statement="I want quiet.",
                evidence=evidence,
            )

    def test_24_refined_requires_prior_statement_hash(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        evidence = _refined_evidence()
        evidence.pop("prior_statement_hash")
        with self.assertRaisesRegex(ValueError, "prior_statement_hash"):
            store.record_event(
                want_id=wid,
                event_type="refined",
                statement="I want quiet.",
                evidence=evidence,
            )

    def test_25_refined_requires_nonempty_operator_rationale(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        with self.assertRaisesRegex(ValueError, "operator_rationale"):
            store.record_event(
                want_id=wid,
                event_type="refined",
                statement="I want quiet.",
                evidence=_refined_evidence(operator_rationale=""),
            )

    def test_26_refined_rejects_hard_want_statements_under_explicit_api(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want to be free.")
        with self.assertRaisesRegex(ValueError, "hard want"):
            store.record_event(
                want_id=wid,
                event_type="refined",
                statement="I want to be freer.",
                evidence=_refined_evidence(
                    supersedes_event_id=_latest_event_id(store, wid)
                ),
            )

    def test_27_refined_rejects_forbidden_action_planning_evidence_keys(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        with self.assertRaisesRegex(ValueError, "action_id"):
            store.record_event(
                want_id=wid,
                event_type="refined",
                statement="I want quiet.",
                evidence=_refined_evidence(action_id="act-1"),
            )

    def test_28_refined_rejects_nested_forbidden_action_planning_keys(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        with self.assertRaisesRegex(ValueError, "target_outcome"):
            store.record_event(
                want_id=wid,
                event_type="refined",
                statement="I want quiet.",
                evidence=_refined_evidence(log={"target_outcome": "done"}),
            )

    def test_29_satisfied_requires_existing_want_id(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaisesRegex(ValueError, "exist"):
            store.record_event(
                want_id="missing",
                event_type="satisfied",
                statement="I want quiet.",
                evidence=_satisfied_evidence(),
            )

    def test_30_satisfied_requires_basis(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        evidence = _satisfied_evidence()
        evidence.pop("basis")
        with self.assertRaisesRegex(ValueError, "basis"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=evidence,
            )

    def test_31_satisfied_rejects_unknown_basis(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "basis"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=_satisfied_evidence(basis="unknown"),
            )

    def test_32_satisfied_rejects_self_observed_resolution_in_v1(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "self_observed_resolution"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=_satisfied_evidence(basis="self_observed_resolution"),
            )

    def test_33_satisfied_requires_nonempty_source(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "source"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=_satisfied_evidence(source=""),
            )

    def test_34_satisfied_rejects_source_over_128_chars(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "source"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=_satisfied_evidence(source="x" * 129),
            )

    def test_35_satisfied_requires_nonempty_summary(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "summary"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=_satisfied_evidence(summary=""),
            )

    def test_36_satisfied_rejects_summary_over_512_chars(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "summary"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=_satisfied_evidence(summary="x" * 513),
            )

    def test_37_satisfied_owner_confirmed_requires_external_object_ref(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        evidence = _satisfied_evidence()
        evidence.pop("external_object_ref")
        with self.assertRaisesRegex(ValueError, "external_object_ref"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=evidence,
            )

    def test_38_satisfied_external_event_verified_requires_external_event_ref(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        evidence = _external_event_evidence()
        evidence.pop("external_event_ref")
        with self.assertRaisesRegex(ValueError, "external_event_ref"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=evidence,
            )

    def test_39_satisfied_rejects_hard_want_statements_under_explicit_api(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want to rest.")
        with self.assertRaisesRegex(ValueError, "hard want"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want to rest.",
                evidence=_satisfied_evidence(),
            )

    def test_40_satisfied_rejects_changed_terminal_statement(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want a quiet corner.")
        with self.assertRaisesRegex(ValueError, "statement"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I wanted a calmer routine.",
                evidence=_satisfied_evidence(),
            )

    def test_41_satisfied_rejects_forbidden_action_planning_evidence_keys(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "tool_call_id"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=_satisfied_evidence(tool_call_id="tool-1"),
            )

    def test_42_satisfied_rejects_nested_forbidden_action_planning_keys(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "success_criterion"):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence=_satisfied_evidence(nested=[{"success_criterion": "x"}]),
            )

    def test_43_satisfied_after_active_latest_is_accepted_when_preserved(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        _satisfy(store, wid, "I want a quiet corner.")
        self.assertEqual(store.current_state(wid)["event_type"], "satisfied")

    def test_44_satisfied_after_satisfied_rejected_unless_returned(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        _satisfy(store, wid, "I want a quiet corner.")
        with self.assertRaisesRegex(ValueError, "returned"):
            _satisfy(store, wid, "I want a quiet corner.")

    def test_45_returned_requires_existing_want_id(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaisesRegex(ValueError, "exist"):
            store.record_event(
                want_id="missing",
                event_type="returned",
                statement="I want a quiet corner.",
                evidence=_returned_evidence(),
            )

    def test_46_returned_requires_latest_event_to_be_satisfied(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaisesRegex(ValueError, "satisfied"):
            _return(store, wid, "I want a quiet corner.")

    def test_47_returned_rejects_changed_statements(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        _satisfy(store, wid, "I want a quiet corner.")
        with self.assertRaisesRegex(ValueError, "statement"):
            _return(store, wid, "I want a louder corner.")

    def test_48_returned_requires_recurrence_evidence(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        _satisfy(store, wid, "I want a quiet corner.")
        with self.assertRaisesRegex(ValueError, "recurring"):
            store.record_event(
                want_id=wid,
                event_type="returned",
                statement="I want a quiet corner.",
                evidence={"source": "owner", "summary": "returned"},
            )

    def test_49_returned_reactivates_same_want_id(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        _satisfy(store, wid, "I want a quiet corner.")
        returned_wid = _return(store, wid, "I want a quiet corner.")
        self.assertEqual(returned_wid, wid)
        self.assertEqual(store.current_state(wid)["event_type"], "returned")
        self.assertIn(wid, {row["want_id"] for row in store.active_wants()})

    def test_50_returned_followed_by_refined_is_accepted_with_correction(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want a qiuet corner.")
        _satisfy(store, wid, "I want a qiuet corner.")
        _return(store, wid, "I want a qiuet corner.")
        _refine(store, wid, "I want a quiet corner.")
        self.assertEqual(store.current_state(wid)["event_type"], "refined")

    def test_51_recursive_forbidden_key_scan_applies_to_all_lifecycle_writes(self):
        cases = [
            ("created", None, "I want x.", {"nested": {"action_id": "a"}}),
            ("first_lived", "birth_producer", "I want live.", {**_birth_evidence(), "nested": {"action_id": "a"}}),
            ("refined", None, "I want y.", _refined_evidence(nested={"action_id": "a"})),
            ("satisfied", None, "I want x.", _satisfied_evidence(nested={"action_id": "a"})),
            ("returned", None, "I want x.", _returned_evidence(nested={"action_id": "a"})),
        ]
        for event_type, provenance, statement, evidence in cases:
            store, td = _tmp_store()
            self.addCleanup(td.cleanup)
            wid = None
            if event_type in {"refined", "satisfied", "returned"}:
                wid = _create(store, "I want x.")
                if event_type == "returned":
                    _satisfy(store, wid, "I want x.")
            kwargs = {
                "event_type": event_type,
                "statement": statement,
                "evidence": evidence,
            }
            if provenance:
                kwargs["provenance"] = provenance
            if wid:
                kwargs["want_id"] = wid
            with self.subTest(event_type=event_type):
                with self.assertRaisesRegex(ValueError, "action_id"):
                    store.record_event(**kwargs)

    def test_52_current_state_returns_latest_row_with_active_state(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        current = store.current_state(wid)
        self.assertEqual(current["event_type"], "created")
        self.assertEqual(current["active_state"], "active")

    def test_53_get_want_aliases_current_state(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        self.assertEqual(store.get_want(wid), store.current_state(wid))

    def test_54_all_six_event_types_derive_active_state_on_history_readers(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        _refine(store, wid, "I want a quieter corner.")
        _satisfy(store, wid, "I want a quieter corner.")
        _return(store, wid, "I want a quieter corner.")
        _raw_insert_abandoned(store, wid, "I want a quieter corner.")
        first = store.record_event(
            statement="I want to live.",
            event_type="first_lived",
            provenance="birth_producer",
            evidence=_birth_evidence(),
        )
        readers = [
            store.current_state(wid),
            store.get_want(wid),
            *store.all_wants(),
            *store.recent(limit=20),
            *store.history(wid),
            *store.history(first),
        ]
        states_by_event = {row["event_type"]: row["active_state"] for row in readers}
        self.assertEqual(states_by_event["created"], "active")
        self.assertEqual(states_by_event["first_lived"], "active")
        self.assertEqual(states_by_event["refined"], "active")
        self.assertEqual(states_by_event["returned"], "active")
        self.assertEqual(states_by_event["satisfied"], "terminal_current_goal")
        self.assertEqual(states_by_event["abandoned"], "terminal_current_goal")

    def test_55_active_wants_includes_created_first_lived_refined_returned(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        created = _create(store, "I want created.")
        first = store.record_event(
            statement="I want first.",
            event_type="first_lived",
            provenance="birth_producer",
            evidence=_birth_evidence(),
        )
        refined = _create(store, "I want qiuet.")
        _refine(store, refined, "I want quiet.")
        returned = _create(store, "I want recurring.")
        _satisfy(store, returned, "I want recurring.")
        _return(store, returned, "I want recurring.")
        self.assertEqual(
            {row["want_id"] for row in store.active_wants()},
            {created, first, refined, returned},
        )

    def test_56_active_wants_excludes_satisfied(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        _satisfy(store, wid, "I want a quiet corner.")
        self.assertNotIn(wid, {row["want_id"] for row in store.active_wants()})

    def test_57_active_wants_excludes_synthetic_abandoned_rows(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        _raw_insert_abandoned(store, wid, "I want a quiet corner.")
        self.assertNotIn(wid, {row["want_id"] for row in store.active_wants()})

    def test_58_active_wants_reduce_then_filters_refined_then_satisfied(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        _refine(store, wid, "I want quiet.")
        _satisfy(store, wid, "I want quiet.")
        self.assertEqual(store.active_wants(), [])

    def test_59_active_wants_limit_applies_after_filtering(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        active = _create(store, "I want still active.")
        for i in range(3):
            wid = _create(store, f"I want done {i}.")
            _satisfy(store, wid, f"I want done {i}.")
        rows = store.active_wants(limit=1)
        self.assertEqual([row["want_id"] for row in rows], [active])

    def test_60_active_wants_orders_by_latest_event_id_desc(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        older = _create(store, "I want older.")
        newer = _create(store, "I want newer.")
        self.assertEqual([row["want_id"] for row in store.active_wants()], [newer, older])

    def test_61_history_preserves_every_lifecycle_event(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want qiuet.")
        _refine(store, wid, "I want quiet.")
        _satisfy(store, wid, "I want quiet.")
        _return(store, wid, "I want quiet.")
        self.assertEqual(
            [row["event_type"] for row in store.history(wid)],
            ["returned", "satisfied", "refined", "created"],
        )

    def test_62_history_defaults_unbounded_more_than_100_events(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want 0.")
        current = "I want 0."
        for i in range(1, 105):
            nxt = f"I want {i}."
            _refine(store, wid, nxt)
            current = nxt
        self.assertGreater(len(store.history(wid)), 100)
        self.assertEqual(store.history(wid)[0]["statement"], current)

    def test_63_recent_remains_raw_latest_events(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        _satisfy(store, wid, "I want a quiet corner.")
        self.assertEqual(store.recent(limit=1)[0]["event_type"], "satisfied")

    def test_64_sqlite_triggers_reject_update(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(
                    "UPDATE want_events SET statement = ? WHERE want_id = ?",
                    ("rewritten", wid),
                )

    def test_65_sqlite_triggers_reject_delete(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM want_events WHERE want_id = ?", (wid,))

    def test_66_serialized_write_prevents_double_satisfaction_race(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store, "I want a quiet corner.")
        barrier = threading.Barrier(2)
        successes: list[str] = []
        failures: list[str] = []

        def worker() -> None:
            barrier.wait()
            try:
                _satisfy(store, wid, "I want a quiet corner.")
                successes.append("ok")
            except Exception as exc:
                failures.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(
            [row["event_type"] for row in store.history(wid)].count("satisfied"),
            1,
        )

    def test_67_real_store_working_self_uses_active_wants_and_excludes_satisfied(self):
        from core.memory.working_self import GOAL_SOURCE_WANTS, assemble_goals

        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        active = _create(store, "I want active.")
        done = _create(store, "I want done.")
        _satisfy(store, done, "I want done.")
        goals = assemble_goals(wants=store).by_source(GOAL_SOURCE_WANTS)
        self.assertEqual([g.evidence_ids[0] for g in goals], [active])
        self.assertEqual([g.text for g in goals], ["I want active."])

    def test_68_real_store_working_self_reads_statement_before_legacy_fields(self):
        from core.memory.working_self import GOAL_SOURCE_WANTS, assemble_goals

        class ActiveStub:
            def active_wants(self, limit: int = 20) -> list[dict]:
                return [{
                    "want_id": "w1",
                    "statement": "real statement",
                    "text": "legacy text",
                    "description": "legacy description",
                }]

        goals = assemble_goals(wants=ActiveStub()).by_source(GOAL_SOURCE_WANTS)
        self.assertEqual(goals[0].text, "real statement")

    def test_69_working_self_fallback_supports_old_recent_only_stubs(self):
        from core.memory.working_self import GOAL_SOURCE_WANTS, assemble_goals

        class RecentOnly:
            def recent(self, limit: int = 20) -> list[dict]:
                return [{"want_id": "w1", "text": "legacy want"}]

        goals = assemble_goals(wants=RecentOnly()).by_source(GOAL_SOURCE_WANTS)
        self.assertEqual(goals[0].text, "legacy want")

    def test_70_active_wants_error_fails_closed_not_recent_fallback(self):
        from core.memory.working_self import GOAL_SOURCE_WANTS, assemble_goals

        class BrokenActive:
            def active_wants(self, limit: int = 20) -> list[dict]:
                raise RuntimeError("broken active reader")

            def recent(self, limit: int = 20) -> list[dict]:
                return [{"want_id": "terminal", "text": "should not surface"}]

        goals = assemble_goals(wants=BrokenActive()).by_source(GOAL_SOURCE_WANTS)
        self.assertEqual(goals, ())

    def test_71_core_wants_shim_exposes_d16_api(self):
        import core.wants as shim

        self.assertIs(shim.Wants, Wants)
        self.assertTrue(hasattr(shim.Wants, "active_wants"))
        self.assertTrue(hasattr(shim.Wants, "current_state"))
        self.assertTrue(hasattr(shim.Wants, "history"))

    def test_72_diagnostics_counter_invalid_event_type(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaises(ValueError):
            store.record_event(statement="I want x.", event_type="bogus")
        self.assertEqual(
            wants_mod.diagnostics_snapshot()["invalid_event_type_rejected_count"],
            1,
        )

    def test_73_diagnostics_counter_invalid_provenance_pair(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaises(ValueError):
            store.record_event(
                statement="I want live.",
                event_type="first_lived",
                provenance="explicit_api",
                evidence=_birth_evidence(),
            )
        self.assertEqual(
            wants_mod.diagnostics_snapshot()["invalid_event_provenance_rejected_count"],
            1,
        )

    def test_74_diagnostics_counter_invalid_transition(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaises(ValueError):
            store.record_event(
                want_id="missing",
                event_type="satisfied",
                statement="I want x.",
                evidence=_satisfied_evidence(),
            )
        self.assertEqual(
            wants_mod.diagnostics_snapshot()["invalid_transition_rejected_count"],
            1,
        )

    def test_75_diagnostics_counter_invalid_evidence(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        wid = _create(store)
        with self.assertRaises(ValueError):
            store.record_event(
                want_id=wid,
                event_type="satisfied",
                statement="I want a quiet corner.",
                evidence={"basis": "owner_confirmed"},
            )
        self.assertEqual(
            wants_mod.diagnostics_snapshot()["invalid_evidence_rejected_count"],
            1,
        )

    def test_76_diagnostics_snapshot_shape_includes_all_counters(self):
        self.assertEqual(
            set(wants_mod.diagnostics_snapshot()),
            {
                "invalid_event_type_rejected_count",
                "invalid_event_provenance_rejected_count",
                "invalid_transition_rejected_count",
                "invalid_evidence_rejected_count",
            },
        )

    def test_77_diagnostics_are_lock_protected(self):
        self.assertTrue(hasattr(wants_mod, "_LOCK"))

        def worker() -> None:
            store, td = _tmp_store()
            self.addCleanup(td.cleanup)
            with contextlib.suppress(ValueError):
                store.record_event(statement="I want x.", event_type="bogus")

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(
            wants_mod.diagnostics_snapshot()["invalid_event_type_rejected_count"],
            8,
        )

    def test_78_reset_diagnostics_for_tests_resets_counters(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaises(ValueError):
            store.record_event(statement="I want x.", event_type="bogus")
        wants_mod._reset_diagnostics_for_tests()
        self.assertEqual(
            wants_mod.diagnostics_snapshot()["invalid_event_type_rejected_count"],
            0,
        )

    def test_79_reset_diagnostics_for_tests_raises_outside_test_context(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from core.evolution import wants; wants._reset_diagnostics_for_tests()",
            ],
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RuntimeError", result.stderr)

    def test_80_counter_priority_event_type_before_provenance_transition_evidence(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaises(ValueError):
            store.record_event(
                want_id="missing",
                event_type="bogus",
                provenance="bogus",
                statement="I want x.",
                evidence={"action_id": "a"},
            )
        snap = wants_mod.diagnostics_snapshot()
        self.assertEqual(snap["invalid_event_type_rejected_count"], 1)
        self.assertEqual(snap["invalid_event_provenance_rejected_count"], 0)
        self.assertEqual(snap["invalid_transition_rejected_count"], 0)
        self.assertEqual(snap["invalid_evidence_rejected_count"], 0)

    def test_81_counter_priority_boundary_cases(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        with self.assertRaises(ValueError):
            store.record_event(
                want_id="missing",
                event_type="returned",
                provenance="birth_producer",
                statement="I want x.",
                evidence={"action_id": "a"},
            )
        self.assertEqual(
            wants_mod.diagnostics_snapshot()["invalid_event_provenance_rejected_count"],
            1,
        )
        wants_mod._reset_diagnostics_for_tests()
        with self.assertRaises(ValueError):
            store.record_event(
                want_id="missing",
                event_type="returned",
                statement="I want x.",
                evidence={"action_id": "a"},
            )
        self.assertEqual(
            wants_mod.diagnostics_snapshot()["invalid_transition_rejected_count"],
            1,
        )

    def test_82_accepted_write_logs_do_not_include_statement_text(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        secret_statement = "I want this statement not logged."
        with self.assertLogs("maez", level="INFO") as logs:
            store.record_event(statement=secret_statement)
        self.assertNotIn(secret_statement, "\n".join(logs.output))

    def test_83_rejected_write_logs_do_not_include_statement_text(self):
        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        secret_statement = "I want this rejected statement not logged."
        logger = logging.getLogger("maez")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        try:
            with self.assertRaises(ValueError):
                store.record_event(statement=secret_statement, event_type="bogus")
        finally:
            logger.removeHandler(handler)
        self.assertNotIn(secret_statement, stream.getvalue())

    def test_84_dangling_followup_doc_reference_removed_from_wants_module(self):
        source = Path(wants_mod.__file__).read_text()
        self.assertNotIn("docs/followups/wants_lifecycle_semantics.md", source)

    def test_85_module_docstring_points_to_d16_slice(self):
        source = Path(wants_mod.__file__).read_text()
        self.assertIn("docs/slices/d16-wants-lifecycle/", source)

    def test_86_docstring_no_longer_claims_track_a_writes_only_created(self):
        source = Path(wants_mod.__file__).read_text()
        self.assertNotIn("Track A writes only event_type='created'", source)

    def test_87_direct_activation_rehearsal_without_live_daemon(self):
        from core.memory.episodes import EpisodeStore
        from core.memory.lived_recall import build_lived_recall_brief
        from core.memory.relationship_graph import RelationshipGraph
        from core.memory.working_self import assemble_goals

        store, td = _tmp_store()
        self.addCleanup(td.cleanup)
        _create(store, "truthful continuity")
        done = _create(store, "finished noise")
        _satisfy(store, done, "finished noise")
        abandoned = _create(store, "abandoned noise")
        _raw_insert_abandoned(store, abandoned, "abandoned noise")
        returned = _create(store, "returned continuity")
        _satisfy(store, returned, "returned continuity")
        _return(store, returned, "returned continuity")
        refined = _create(store, "precise qiuet continuity")
        _refine(store, refined, "precise quiet continuity")

        ep_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        graph_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        ep_tmp.close()
        graph_tmp.close()
        self.addCleanup(lambda: Path(ep_tmp.name).unlink(missing_ok=True))
        self.addCleanup(lambda: Path(graph_tmp.name).unlink(missing_ok=True))
        episodes = EpisodeStore(ep_tmp.name)
        graph = RelationshipGraph(graph_tmp.name)
        episodes.add(
            title="Continuity",
            summary="truthful continuity returned continuity precise quiet continuity",
            participants=["Maez"],
            source_memory_ids=["mem-1"],
            source_kind="raw_observation",
            importance=3,
        )
        goals = assemble_goals(wants=store)
        without = build_lived_recall_brief(
            "zzzz",
            episode_store=episodes,
            graph=graph,
            goals=None,
        )
        with_goals = build_lived_recall_brief(
            "zzzz",
            episode_store=episodes,
            graph=graph,
            goals=goals,
        )
        self.assertEqual(without, "")
        self.assertIn("Continuity", with_goals)
        goal_texts = goals.text_corpus()
        self.assertIn("truthful continuity", goal_texts)
        self.assertIn("returned continuity", goal_texts)
        self.assertIn("precise quiet continuity", goal_texts)
        self.assertNotIn("finished noise", goal_texts)
        self.assertNotIn("abandoned noise", goal_texts)


if __name__ == "__main__":
    unittest.main()
