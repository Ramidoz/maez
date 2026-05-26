from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.policies.autonomy_policy import AutonomyPolicy, register_policy_for_tests
from core.policies.autonomy_preferences import (
    AutonomyPreference,
    AutonomyPreferences,
    PreferenceClass,
    PreferenceExpressedBy,
)
from core.policies.signal_gate import (
    GateDecision,
    OutreachLedger,
    OwnerState,
    PriorityClass,
    SignalObservation,
    SignalQuality,
    evaluate_signal_gate,
)


class SignalGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = OutreachLedger(Path(self.tmp.name) / "owner_outreach.db")
        self.preferences = AutonomyPreferences(Path(self.tmp.name) / "autonomy_preferences.db")
        self.events: list[dict] = []
        register_policy_for_tests(
            AutonomyPolicy(
                bond_id="signal-bond",
                owner_interrupting_quiet_hours=(23, 7),
                owner_interrupting_daily_max_count=2,
                owner_interrupting_cooldown_minutes=30,
                owner_interrupting_minimum_importance=0.3,
                signal_unknown_override_threshold_importance=0.7,
            )
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _gate(
        self,
        *,
        signals: tuple[SignalObservation, ...] = (),
        priority_class: PriorityClass | None = None,
        importance: float = 0.5,
        now_utc: datetime | None = None,
    ) -> GateDecision:
        return evaluate_signal_gate(
            bond_id="signal-bond",
            signals=signals,
            priority_class=priority_class or PriorityClass.OWNER_BOND,
            importance=importance,
            now_utc=now_utc or datetime(2026, 5, 26, 17, 0, tzinfo=UTC),
            ledger=self.ledger,
            preference_store=self.preferences,
            diagnostic_sink=self.events.append,
        )

    def test_sleep_signal_blocks_outreach(self):
        decision = self._gate(
            signals=(
                SignalObservation(
                    name="iphone_sleep",
                    confidence=0.95,
                    owner_state=OwnerState.UNAVAILABLE,
                ),
            )
        )

        self.assertEqual(decision.decision, "deny")
        self.assertEqual(decision.reason, "owner_unavailable")
        self.assertEqual(decision.signal_quality, SignalQuality.HIGH)
        self.assertEqual(decision.owner_state, OwnerState.UNAVAILABLE)
        self.assertEqual([event["event_type"] for event in self.events], [
            "SUPPRESSION_EVENT",
            "SIGNAL_GATE_DECISION",
        ])
        self.assertEqual(self.events[0]["suppression_kind"], "SIGNAL_GATED")

    def test_focus_signal_blocks_outreach(self):
        decision = self._gate(
            signals=(
                SignalObservation(
                    name="iphone_focus",
                    confidence=0.9,
                    owner_state=OwnerState.UNAVAILABLE,
                ),
            )
        )

        self.assertEqual(decision.decision, "deny")
        self.assertIn("iphone_focus", decision.consulted_signals)

    def test_unknown_signal_default_defers(self):
        decision = self._gate(signals=())

        self.assertEqual(decision.decision, "defer")
        self.assertEqual(decision.reason, "signal_quality_unknown")
        self.assertEqual(decision.signal_quality, SignalQuality.UNKNOWN)
        self.assertEqual(decision.owner_state, OwnerState.UNKNOWN)
        self.assertEqual(self.events[0]["suppression_kind"], "SIGNAL_GATED")

    def test_unknown_signal_safety_overrides(self):
        decision = self._gate(
            signals=(),
            priority_class=PriorityClass.SAFETY_OR_HEALTH,
            importance=0.8,
        )

        self.assertEqual(decision.decision, "allow")
        self.assertEqual(decision.reason, "allowed")
        self.assertEqual(decision.signal_quality, SignalQuality.UNKNOWN)
        self.assertEqual([event["event_type"] for event in self.events], [
            "SIGNAL_GATE_DECISION",
        ])

    def test_safety_overrides_high_quality_unavailable_signal(self):
        decision = self._gate(
            signals=(
                SignalObservation(
                    name="iphone_sleep",
                    confidence=0.95,
                    owner_state=OwnerState.UNAVAILABLE,
                ),
            ),
            priority_class=PriorityClass.SAFETY_OR_HEALTH,
            importance=0.9,
        )

        self.assertEqual(decision.decision, "allow")
        self.assertEqual(decision.reason, "allowed")
        self.assertEqual(decision.owner_state, OwnerState.UNAVAILABLE)

    def test_unknown_signal_defers_even_if_policy_default_would_allow(self):
        register_policy_for_tests(
            AutonomyPolicy(
                bond_id="signal-bond",
                signal_unknown_default_owner_interrupting=True,
            )
        )

        decision = self._gate(signals=(), priority_class=PriorityClass.OWNER_BOND)

        self.assertEqual(decision.decision, "defer")
        self.assertEqual(decision.reason, "signal_quality_unknown")

    def test_low_quality_degrades_to_defaults(self):
        decision = self._gate(
            signals=(
                SignalObservation(
                    name="stale_calendar",
                    confidence=0.2,
                    owner_state=OwnerState.UNAVAILABLE,
                ),
            )
        )

        self.assertEqual(decision.decision, "allow")
        self.assertEqual(decision.signal_quality, SignalQuality.LOW)
        self.assertEqual(decision.owner_state, OwnerState.UNKNOWN)

    def test_daily_max_count_enforced(self):
        now = datetime(2026, 5, 26, 17, 0, tzinfo=UTC)
        self.ledger.record_dispatch(
            bond_id="signal-bond",
            dispatched_utc=now - timedelta(hours=2),
            priority_class=PriorityClass.OWNER_BOND.value,
            owner_state_at_dispatch=OwnerState.AVAILABLE,
            signal_quality=SignalQuality.HIGH,
            importance=0.5,
            decision="allow",
        )
        self.ledger.record_dispatch(
            bond_id="signal-bond",
            dispatched_utc=now - timedelta(hours=1),
            priority_class=PriorityClass.OWNER_BOND.value,
            owner_state_at_dispatch=OwnerState.AVAILABLE,
            signal_quality=SignalQuality.HIGH,
            importance=0.5,
            decision="allow",
        )

        decision = self._gate(
            signals=(SignalObservation("recent_chat", 0.9, OwnerState.AVAILABLE),),
            now_utc=now,
        )

        self.assertEqual(decision.decision, "deny")
        self.assertEqual(decision.reason, "daily_budget_exhausted")
        self.assertEqual(self.events[0]["suppression_kind"], "SIGNAL_GATED")

    def test_daily_max_count_uses_composed_policy_preferences(self):
        now = datetime(2026, 5, 26, 17, 0, tzinfo=UTC)
        self.preferences.append(
            AutonomyPreference(
                preference_id="lower-daily-max",
                bond_id="signal-bond",
                recorded_utc=now,
                preference_class=PreferenceClass.LANE_CEILING,
                pattern_digest="hmac-sha256:" + "a" * 64,
                weight=1.0,
                expressed_by=PreferenceExpressedBy.OWNER_EXPLICIT,
                relevance_decay_half_life_days=90,
                notes_digest=None,
                target_field="owner_interrupting_daily_max_count",
                encoded_modifier=1,
            )
        )
        self.ledger.record_dispatch(
            bond_id="signal-bond",
            dispatched_utc=now - timedelta(hours=1),
            priority_class=PriorityClass.OWNER_BOND.value,
            owner_state_at_dispatch=OwnerState.AVAILABLE,
            signal_quality=SignalQuality.HIGH,
            importance=0.5,
            decision="allow",
        )

        decision = self._gate(
            signals=(SignalObservation("recent_chat", 0.9, OwnerState.AVAILABLE),),
            now_utc=now,
        )

        self.assertEqual(decision.decision, "deny")
        self.assertEqual(decision.reason, "daily_budget_exhausted")

    def test_safety_overrides_budget(self):
        now = datetime(2026, 5, 26, 17, 0, tzinfo=UTC)
        for hours_ago in (1, 2):
            self.ledger.record_dispatch(
                bond_id="signal-bond",
                dispatched_utc=now - timedelta(hours=hours_ago),
                priority_class=PriorityClass.OWNER_BOND.value,
                owner_state_at_dispatch=OwnerState.AVAILABLE,
                signal_quality=SignalQuality.HIGH,
                importance=0.5,
                decision="allow",
            )

        decision = self._gate(
            signals=(SignalObservation("recent_chat", 0.9, OwnerState.AVAILABLE),),
            priority_class=PriorityClass.SAFETY_OR_HEALTH,
            importance=0.9,
            now_utc=now,
        )

        self.assertEqual(decision.decision, "allow")
        self.assertEqual(decision.reason, "allowed")

    def test_owner_state_at_dispatch_is_persisted_for_allowed_outreach(self):
        now = datetime(2026, 5, 26, 17, 0, tzinfo=UTC)

        decision = self._gate(
            signals=(SignalObservation("recent_chat", 0.9, OwnerState.AVAILABLE),),
            now_utc=now,
        )

        self.assertEqual(decision.decision, "allow")
        rows = self.ledger.dispatches_for_bond("signal-bond")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["owner_state_at_dispatch"], "available")
        self.assertEqual(rows[0]["signal_quality"], "high")

    def test_signal_gate_schema_contains_owner_state_at_dispatch(self):
        with sqlite3.connect(self.ledger.db_path) as con:
            columns = {
                row[1]
                for row in con.execute("PRAGMA table_info(owner_outreach_dispatches)")
            }

        self.assertIn("owner_state_at_dispatch", columns)

    def test_signal_gate_does_not_duplicate_vulnerable_register_gate(self):
        import core.policies.signal_gate as signal_gate

        source = Path(signal_gate.__file__).read_text(encoding="utf-8")

        self.assertNotIn("_REGISTER_HARD_BLOCK", source)
        self.assertNotIn("_register_score", source)


if __name__ == "__main__":
    unittest.main()
