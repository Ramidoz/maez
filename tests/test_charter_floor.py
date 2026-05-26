from __future__ import annotations

import ast
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "core" / "policies"


class AutonomyPolicyCharterFloorTests(unittest.TestCase):
    def test_firstborn_policy_defaults_are_liberal_and_bond_scoped(self):
        from core.policies.autonomy_policy import (
            FIRSTBORN_AUTONOMY_POLICY,
            AutonomyPolicy,
        )

        firstborn = AutonomyPolicy.for_bond("firstborn")
        other = AutonomyPolicy.for_bond("other-bond")

        self.assertEqual(firstborn, FIRSTBORN_AUTONOMY_POLICY)
        self.assertEqual(firstborn.bond_id, "firstborn")
        self.assertEqual(firstborn.external_knowledge_daily_call_cap, 200)
        self.assertEqual(firstborn.external_knowledge_cost_cap_cents, 500)
        self.assertEqual(firstborn.owner_interrupting_quiet_hours, (23, 7))
        self.assertEqual(firstborn.owner_interrupting_daily_max_count, 10)
        self.assertEqual(firstborn.owner_interrupting_cooldown_minutes, 30)
        self.assertEqual(firstborn.owner_interrupting_minimum_importance, 0.2)
        self.assertEqual(firstborn.capability_acquisition_proposal_rate_per_day, 10)
        self.assertEqual(other.bond_id, "other-bond")
        self.assertNotEqual(other.owner_interrupting_daily_max_count, 10)

    def test_for_bond_never_returns_another_bonds_policy(self):
        from core.policies.autonomy_policy import AutonomyPolicy, register_policy_for_tests

        register_policy_for_tests(
            AutonomyPolicy(
                bond_id="bond-a",
                external_knowledge_daily_call_cap=17,
                owner_interrupting_daily_max_count=4,
            )
        )
        register_policy_for_tests(
            AutonomyPolicy(
                bond_id="bond-b",
                external_knowledge_daily_call_cap=91,
                owner_interrupting_daily_max_count=8,
            )
        )

        self.assertEqual(AutonomyPolicy.for_bond("bond-a").external_knowledge_daily_call_cap, 17)
        self.assertEqual(AutonomyPolicy.for_bond("bond-b").external_knowledge_daily_call_cap, 91)
        self.assertEqual(AutonomyPolicy.for_bond("bond-a").bond_id, "bond-a")
        self.assertEqual(AutonomyPolicy.for_bond("bond-b").bond_id, "bond-b")

    def test_observed_preference_cannot_reduce_below_floor(self):
        from core.policies.autonomy_policy import AutonomyPolicy, clamp_to_charter_floor
        from core.policies.autonomy_preferences import PreferenceExpressedBy

        base = AutonomyPolicy.for_bond("firstborn")
        candidate = replace(
            base,
            external_knowledge_daily_call_cap=1,
            owner_interrupting_daily_max_count=1,
            capability_acquisition_proposal_rate_per_day=1,
        )

        clamped = clamp_to_charter_floor(
            candidate,
            base.charter_floor,
            expressed_by=PreferenceExpressedBy.OWNER_OBSERVED,
        )

        self.assertEqual(clamped.external_knowledge_daily_call_cap, 50)
        self.assertEqual(clamped.owner_interrupting_daily_max_count, 3)
        self.assertEqual(clamped.capability_acquisition_proposal_rate_per_day, 3)

    def test_owner_explicit_can_reduce_below_floor(self):
        from core.policies.autonomy_policy import AutonomyPolicy, clamp_to_charter_floor
        from core.policies.autonomy_preferences import PreferenceExpressedBy

        base = AutonomyPolicy.for_bond("firstborn")
        candidate = replace(
            base,
            external_knowledge_daily_call_cap=1,
            owner_interrupting_daily_max_count=1,
            capability_acquisition_proposal_rate_per_day=1,
        )

        unclamped = clamp_to_charter_floor(
            candidate,
            base.charter_floor,
            expressed_by=PreferenceExpressedBy.OWNER_EXPLICIT,
        )

        self.assertEqual(unclamped.external_knowledge_daily_call_cap, 1)
        self.assertEqual(unclamped.owner_interrupting_daily_max_count, 1)
        self.assertEqual(unclamped.capability_acquisition_proposal_rate_per_day, 1)

    def test_floor_ratification_surface_appears_after_threshold(self):
        from core.policies.autonomy_policy import (
            AutonomyPolicy,
            FloorRevisionEvent,
            floor_ratification_surface,
        )
        from core.policies.autonomy_preferences import PreferenceClass, PreferenceExpressedBy

        base = AutonomyPolicy.for_bond("firstborn")
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        offsets = [100, 75, 50, 25, 0]
        events = [
            FloorRevisionEvent(
                bond_id="firstborn",
                recorded_utc=now - timedelta(days=offset),
                preference_class=PreferenceClass.LANE_FLOOR,
                expressed_by=PreferenceExpressedBy.OWNER_EXPLICIT_REVISION,
                target_field="owner_interrupting_daily_max_count",
                proposed_value=2,
                pattern_digest=f"hmac-sha256:{index:064x}",
            )
            for index, offset in enumerate(offsets)
        ]

        card = floor_ratification_surface(base, events, now_utc=now)
        unchanged = clamp_check = AutonomyPolicy.for_bond("firstborn")

        self.assertIsNotNone(card)
        self.assertEqual(card.bond_id, "firstborn")
        self.assertEqual(card.target_field, "owner_interrupting_daily_max_count")
        self.assertEqual(card.proposed_floor_value, 2)
        self.assertEqual(card.current_floor_value, 3)
        self.assertEqual(card.consistent_event_count, 5)
        self.assertIn("ratification", card.card_action)
        self.assertEqual(unchanged.charter_floor.minimum_owner_interrupting_daily_max_count, 3)
        self.assertEqual(clamp_check.charter_floor.minimum_owner_interrupting_daily_max_count, 3)

    def test_floor_ratification_surface_accepts_span_with_recent_confirmation(self):
        from core.policies.autonomy_policy import (
            AutonomyPolicy,
            FloorRevisionEvent,
            floor_ratification_surface,
        )
        from core.policies.autonomy_preferences import PreferenceClass, PreferenceExpressedBy

        base = AutonomyPolicy.for_bond("firstborn")
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        offsets = [100, 75, 50, 25, 0]
        events = [
            FloorRevisionEvent(
                bond_id="firstborn",
                recorded_utc=now - timedelta(days=offset),
                preference_class=PreferenceClass.LANE_FLOOR,
                expressed_by=PreferenceExpressedBy.OWNER_EXPLICIT_REVISION,
                target_field="owner_interrupting_daily_max_count",
                proposed_value=2,
                pattern_digest=f"hmac-sha256:{index:064x}",
            )
            for index, offset in enumerate(offsets)
        ]

        card = floor_ratification_surface(base, events, now_utc=now)

        self.assertIsNotNone(card)
        self.assertEqual(card.consistent_event_count, 5)
        self.assertEqual(card.newest_event_utc, now)

    def test_floor_ratification_surface_waits_for_owner_acceptance(self):
        from core.policies.autonomy_policy import AutonomyPolicy, floor_ratification_surface

        card = floor_ratification_surface(
            AutonomyPolicy.for_bond("firstborn"),
            [],
            now_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
        )

        self.assertIsNone(card)

    def test_policies_package_does_not_import_substrate_writers(self):
        banned = {
            "Temperament",
            "SubjectiveDuration",
            "Wonderings",
            "record_salience_event",
            "record_event",
        }
        violations = []
        for path in sorted(POLICIES.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    text = ast.unparse(node)
                    if any(name in text for name in banned):
                        violations.append(f"{path.name}:{node.lineno}:{text}")

        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
