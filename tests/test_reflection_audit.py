from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from core.policies.reflection_audit import (
    OwnerResponse,
    ReflectionAuditLedger,
    ReflectionDecision,
    ReflectionInputs,
    run_reflection_audit,
)
from core.policies.autonomy_preferences import (
    PreferenceClass,
    PreferenceExpressedBy,
    record_owner_response_preference,
)
from core.policies.signal_gate import GateDecision, OwnerState, PriorityClass, SignalQuality


class ReflectionAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = ReflectionAuditLedger(Path(self.tmp.name) / "reflection_audit.db")
        self.events: list[dict] = []
        self.now = datetime(2026, 5, 26, 18, 0, tzinfo=UTC)
        self.gate_decision = GateDecision(
            bond_id="bond-a",
            decision="allow",
            reason="allowed",
            consulted_signals=frozenset({"recent_chat"}),
            signal_quality=SignalQuality.HIGH,
            owner_state=OwnerState.AVAILABLE,
            recheck_after_seconds=None,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _inputs(self, **overrides) -> ReflectionInputs:
        values = {
            "object_id": "object-a",
            "bond_id": "bond-a",
            "priority_class": PriorityClass.SELF_GROWTH,
            "salience": 0.8,
            "can_resolve_interiorly_candidate": False,
            "is_worth_interrupting": True,
            "is_extraction_shaped": False,
            "reasoning_digest": "hmac-sha256:" + "a" * 64,
            "owner_response": None,
        }
        values.update(overrides)
        return ReflectionInputs(**values)

    def test_audit_row_persisted_with_split_defer_modes(self):
        context = run_reflection_audit(
            inputs=self._inputs(is_worth_interrupting=False),
            gate_decision=self.gate_decision,
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=self.events.append,
        )
        extraction = run_reflection_audit(
            inputs=self._inputs(object_id="object-b", is_extraction_shaped=True),
            gate_decision=self.gate_decision,
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=self.events.append,
        )

        self.assertEqual(context.decision, ReflectionDecision.DEFER_CONTEXT_NOT_RIPE)
        self.assertEqual(extraction.decision, ReflectionDecision.DEFER_EXTRACTION_SHAPE)
        rows = self.ledger.audits_for_bond("bond-a")
        self.assertEqual([row["decision"] for row in rows], [
            "defer_context_not_ripe",
            "defer_extraction_shape",
        ])

    def test_owner_bond_exemption_can_resolve_interiorly_false(self):
        audit = run_reflection_audit(
            inputs=self._inputs(
                priority_class=PriorityClass.OWNER_BOND,
                can_resolve_interiorly_candidate=True,
            ),
            gate_decision=self.gate_decision,
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=self.events.append,
        )

        self.assertFalse(audit.can_resolve_interiorly)
        self.assertEqual(audit.decision, ReflectionDecision.PROCEED)

    def test_non_owner_bond_can_defer_when_resolvable_interiorly(self):
        audit = run_reflection_audit(
            inputs=self._inputs(can_resolve_interiorly_candidate=True),
            gate_decision=self.gate_decision,
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=self.events.append,
        )

        self.assertTrue(audit.can_resolve_interiorly)
        self.assertEqual(audit.decision, ReflectionDecision.ABANDON)
        self.assertEqual(self.events[0]["suppression_kind"], "REFLECTION_DEFERRED")

    def test_non_allow_gate_decision_cannot_proceed_even_if_owner_available(self):
        audit = run_reflection_audit(
            inputs=self._inputs(),
            gate_decision=GateDecision(
                bond_id="bond-a",
                decision="defer",
                reason="quiet_hours",
                consulted_signals=frozenset({"recent_chat"}),
                signal_quality=SignalQuality.HIGH,
                owner_state=OwnerState.AVAILABLE,
                recheck_after_seconds=900,
            ),
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=self.events.append,
        )

        self.assertEqual(audit.decision, ReflectionDecision.DEFER_CONTEXT_NOT_RIPE)
        self.assertEqual(self.events[0]["suppression_kind"], "REFLECTION_DEFERRED")

    def test_suppression_event_emitted_before_deferred_audit_decision(self):
        audit = run_reflection_audit(
            inputs=self._inputs(is_extraction_shaped=True),
            gate_decision=self.gate_decision,
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=self.events.append,
        )

        self.assertEqual(audit.decision, ReflectionDecision.DEFER_EXTRACTION_SHAPE)
        self.assertEqual([event["event_type"] for event in self.events], [
            "SUPPRESSION_EVENT",
            "REFLECTION_AUDIT",
        ])
        self.assertEqual(self.events[0]["suppression_kind"], "REFLECTION_DEFERRED")

    def test_audit_row_persisted_before_decision_returns(self):
        seen_counts: list[int] = []

        def sink(event: dict) -> None:
            if event["event_type"] == "REFLECTION_AUDIT":
                seen_counts.append(len(self.ledger.audits_for_bond("bond-a")))

        audit = run_reflection_audit(
            inputs=self._inputs(),
            gate_decision=self.gate_decision,
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=sink,
        )

        self.assertEqual(audit.decision, ReflectionDecision.PROCEED)
        self.assertEqual(seen_counts, [1])

    def test_cross_bond_audit_reads_are_isolated(self):
        run_reflection_audit(
            inputs=self._inputs(object_id="object-a"),
            gate_decision=self.gate_decision,
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=self.events.append,
        )
        run_reflection_audit(
            inputs=self._inputs(object_id="object-b", bond_id="bond-b"),
            gate_decision=GateDecision(
                bond_id="bond-b",
                decision="allow",
                reason="allowed",
                consulted_signals=frozenset(),
                signal_quality=SignalQuality.UNKNOWN,
                owner_state=OwnerState.UNKNOWN,
                recheck_after_seconds=None,
            ),
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=self.events.append,
        )

        rows = self.ledger.audits_for_bond("bond-a")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["bond_id"], "bond-a")

    def test_reasoning_digest_and_reflection_utc_validated_at_boundary(self):
        with self.assertRaisesRegex(ValueError, "reasoning_digest must be hmac-sha256"):
            run_reflection_audit(
                inputs=self._inputs(reasoning_digest="raw reasoning text"),
                gate_decision=self.gate_decision,
                reflection_utc=self.now,
                ledger=self.ledger,
            )

    def test_priority_class_must_be_closed_enum_not_raw_string(self):
        with self.assertRaisesRegex(ValueError, "priority_class must be PriorityClass"):
            run_reflection_audit(
                inputs=self._inputs(
                    priority_class="owner_bond",  # type: ignore[arg-type]
                    can_resolve_interiorly_candidate=True,
                ),
                gate_decision=self.gate_decision,
                reflection_utc=self.now,
                ledger=self.ledger,
            )

    def test_gate_decision_closed_fields_validated_at_boundary(self):
        with self.assertRaisesRegex(ValueError, "gate_decision.decision"):
            run_reflection_audit(
                inputs=self._inputs(),
                gate_decision=GateDecision(
                    bond_id="bond-a",
                    decision="route_around",  # type: ignore[arg-type]
                    reason="malformed",
                    consulted_signals=frozenset(),
                    signal_quality=SignalQuality.HIGH,
                    owner_state=OwnerState.AVAILABLE,
                    recheck_after_seconds=None,
                ),
                reflection_utc=self.now,
                ledger=self.ledger,
            )

        with self.assertRaisesRegex(ValueError, "gate_decision.owner_state"):
            run_reflection_audit(
                inputs=self._inputs(),
                gate_decision=GateDecision(
                    bond_id="bond-a",
                    decision="allow",
                    reason="malformed",
                    consulted_signals=frozenset(),
                    signal_quality=SignalQuality.HIGH,
                    owner_state="available",  # type: ignore[arg-type]
                    recheck_after_seconds=None,
                ),
                reflection_utc=self.now,
                ledger=self.ledger,
            )

        with self.assertRaisesRegex(ValueError, "reflection_utc must be timezone-aware UTC"):
            run_reflection_audit(
                inputs=self._inputs(),
                gate_decision=self.gate_decision,
                reflection_utc=datetime(2026, 5, 26, 18, 0),
                ledger=self.ledger,
            )

    def test_owner_response_sidecar_persists_synthetic_fixture(self):
        audit = run_reflection_audit(
            inputs=self._inputs(owner_response=OwnerResponse.DEFERRED),
            gate_decision=self.gate_decision,
            reflection_utc=self.now,
            ledger=self.ledger,
            diagnostic_sink=self.events.append,
        )

        self.assertEqual(audit.owner_response, OwnerResponse.DEFERRED)
        self.assertEqual(self.ledger.audits_for_bond("bond-a")[0]["owner_response"], "deferred")

    def test_deferred_response_writes_no_preference(self):
        events: list[dict] = []

        preference = record_owner_response_preference(
            bond_id="bond-a",
            object_id="object-a",
            owner_response=OwnerResponse.DEFERRED,
            pattern_digest="hmac-sha256:" + "c" * 64,
            target_field="owner_interrupting_minimum_importance",
            encoded_modifier=0.8,
            recorded_utc=self.now,
            store_path=Path(self.tmp.name) / "autonomy_preferences.db",
            diagnostic_sink=events.append,
        )

        self.assertIsNone(preference)
        self.assertEqual(events, [])

    def test_corrected_response_writes_explicit_revision(self):
        preference = record_owner_response_preference(
            bond_id="bond-a",
            object_id="object-a",
            owner_response=OwnerResponse.CORRECTED,
            pattern_digest="hmac-sha256:" + "e" * 64,
            target_field="owner_interrupting_minimum_importance",
            encoded_modifier=0.75,
            recorded_utc=self.now,
            store_path=Path(self.tmp.name) / "autonomy_preferences.db",
        )

        self.assertIsNotNone(preference)
        assert preference is not None
        self.assertEqual(preference.preference_class, PreferenceClass.LANE_CEILING)
        self.assertEqual(preference.expressed_by, PreferenceExpressedBy.OWNER_EXPLICIT_REVISION)
        self.assertEqual(preference.weight, 1.0)
        self.assertEqual(preference.relevance_decay_half_life_days, 90)

    def test_invited_more_response_writes_encouraged_topic(self):
        preference = record_owner_response_preference(
            bond_id="bond-a",
            object_id="object-a",
            owner_response=OwnerResponse.INVITED_MORE,
            pattern_digest="hmac-sha256:" + "f" * 64,
            target_field="owner_interrupting_minimum_importance",
            encoded_modifier=0.35,
            recorded_utc=self.now,
            store_path=Path(self.tmp.name) / "autonomy_preferences.db",
        )

        self.assertIsNotNone(preference)
        assert preference is not None
        self.assertEqual(preference.preference_class, PreferenceClass.ENCOURAGED_TOPIC)
        self.assertEqual(preference.expressed_by, PreferenceExpressedBy.OWNER_OBSERVED)
        self.assertEqual(preference.weight, 0.6)
        self.assertEqual(preference.relevance_decay_half_life_days, 60)

    def test_declined_without_teaching_writes_discouraged_topic_weight_0_4(self):
        events: list[dict] = []
        store_path = Path(self.tmp.name) / "autonomy_preferences.db"

        preference = record_owner_response_preference(
            bond_id="bond-a",
            object_id="object-a",
            owner_response=OwnerResponse.DECLINED_WITHOUT_TEACHING,
            pattern_digest="hmac-sha256:" + "d" * 64,
            target_field="owner_interrupting_minimum_importance",
            encoded_modifier=0.9,
            recorded_utc=self.now,
            store_path=store_path,
            diagnostic_sink=events.append,
        )

        self.assertIsNotNone(preference)
        assert preference is not None
        self.assertEqual(preference.preference_class, PreferenceClass.DISCOURAGED_TOPIC)
        self.assertEqual(preference.expressed_by, PreferenceExpressedBy.OWNER_OBSERVED)
        self.assertEqual(preference.weight, 0.4)
        self.assertEqual(preference.relevance_decay_half_life_days, 30)
        self.assertEqual(events[0]["event_type"], "PREFERENCE_RECORDED")
        self.assertEqual(events[0]["expressed_by"], "owner_observed")

    def test_schema_is_append_only_and_contains_owner_response(self):
        with closing(sqlite3.connect(self.ledger.db_path)) as con:
            columns = {
                row[1]
                for row in con.execute("PRAGMA table_info(reflection_audits)")
            }

        self.assertIn("owner_response", columns)
        self.assertNotIn("superseded_by", columns)


if __name__ == "__main__":
    unittest.main()
