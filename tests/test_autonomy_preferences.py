from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from core.policies.autonomy_policy import AutonomyPolicy, register_policy_for_tests
from core.policies.autonomy_preferences import (
    AutonomyPreference,
    AutonomyPreferences,
    PreferenceClass,
    PreferenceExpressedBy,
    composed_policy,
    preferences_for_bond_and_class,
    tier_weight,
)


class AutonomyPreferenceStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "autonomy_preferences.db"
        self.store = AutonomyPreferences(self.db_path)
        register_policy_for_tests(
            AutonomyPolicy(
                bond_id="bond-a",
                external_knowledge_daily_call_cap=120,
                owner_interrupting_daily_max_count=10,
                capability_acquisition_proposal_rate_per_day=6,
            )
        )
        register_policy_for_tests(
            AutonomyPolicy(
                bond_id="bond-b",
                external_knowledge_daily_call_cap=90,
                owner_interrupting_daily_max_count=8,
                capability_acquisition_proposal_rate_per_day=4,
            )
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _pref(
        self,
        *,
        preference_id: str = "pref-1",
        bond_id: str = "bond-a",
        recorded_utc: datetime | None = None,
        preference_class: PreferenceClass = PreferenceClass.LANE_CEILING,
        pattern_digest: str = "hmac-sha256:" + "a" * 64,
        weight: float = 1.0,
        expressed_by: PreferenceExpressedBy = PreferenceExpressedBy.OWNER_EXPLICIT,
        relevance_decay_half_life_days: float = 90.0,
        notes_digest: str | None = None,
        target_field: str = "owner_interrupting_daily_max_count",
        encoded_modifier: float = 8.0,
    ) -> AutonomyPreference:
        return AutonomyPreference(
            preference_id=preference_id,
            bond_id=bond_id,
            recorded_utc=recorded_utc or datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
            preference_class=preference_class,
            pattern_digest=pattern_digest,
            weight=weight,
            expressed_by=expressed_by,
            relevance_decay_half_life_days=relevance_decay_half_life_days,
            notes_digest=notes_digest,
            target_field=target_field,
            encoded_modifier=encoded_modifier,
        )

    def test_append_round_trips_without_supersession_column(self):
        pref = self._pref(notes_digest="hmac-sha256:" + "b" * 64)

        self.store.append(pref)
        rows = self.store.preferences_for_bond_and_class("bond-a", PreferenceClass.LANE_CEILING)

        self.assertEqual(rows, [pref])
        with closing(sqlite3.connect(self.db_path)) as con:
            columns = {
                row[1]
                for row in con.execute("PRAGMA table_info(autonomy_preferences)").fetchall()
            }
        self.assertIn("bond_id", columns)
        self.assertIn("encoded_modifier", columns)
        self.assertNotIn("superseded_by", columns)

    def test_bond_id_is_mandatory(self):
        with self.assertRaisesRegex(ValueError, "bond_id is required"):
            self.store.append(self._pref(bond_id=""))

    def test_preferences_for_bond_and_class_refuses_cross_bond_composition(self):
        self.store.append(self._pref(preference_id="a", bond_id="bond-a", encoded_modifier=7))
        self.store.append(self._pref(preference_id="b", bond_id="bond-b", encoded_modifier=2))

        rows = self.store.preferences_for_bond_and_class("bond-a", PreferenceClass.LANE_CEILING)

        self.assertEqual([row.preference_id for row in rows], ["a"])
        self.assertEqual([row.bond_id for row in rows], ["bond-a"])

    def test_append_only_rejects_duplicate_preference_id(self):
        pref = self._pref()

        self.store.append(pref)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.append(replace(pref, weight=0.2))

        rows = self.store.preferences_for_bond_and_class("bond-a", PreferenceClass.LANE_CEILING)
        self.assertEqual(rows, [pref])

    def test_tier_weight_matches_closed_vocabulary(self):
        self.assertEqual(tier_weight(PreferenceExpressedBy.OWNER_EXPLICIT), 1.0)
        self.assertEqual(tier_weight(PreferenceExpressedBy.OWNER_EXPLICIT_REVISION), 1.2)
        self.assertEqual(tier_weight(PreferenceExpressedBy.OWNER_OBSERVED), 0.4)
        self.assertEqual(tier_weight(PreferenceExpressedBy.SYSTEM_DEFAULT), 0.1)

    def test_composed_policy_returns_base_when_no_relevant_preferences(self):
        policy = composed_policy(
            "bond-a",
            PreferenceClass.LANE_CEILING,
            now_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
            store=self.store,
        )

        self.assertEqual(policy, AutonomyPolicy.for_bond("bond-a"))

    def test_composed_policy_uses_decay_and_tier_weight(self):
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        self.store.append(
            self._pref(
                preference_id="fresh-explicit",
                recorded_utc=now,
                expressed_by=PreferenceExpressedBy.OWNER_EXPLICIT,
                relevance_decay_half_life_days=90,
                encoded_modifier=8,
            )
        )
        self.store.append(
            self._pref(
                preference_id="half-life-observed",
                recorded_utc=now - timedelta(days=30),
                expressed_by=PreferenceExpressedBy.OWNER_OBSERVED,
                relevance_decay_half_life_days=30,
                encoded_modifier=2,
            )
        )

        policy = composed_policy(
            "bond-a",
            PreferenceClass.LANE_CEILING,
            now_utc=now,
            store=self.store,
        )

        self.assertEqual(policy.owner_interrupting_daily_max_count, 7)

    def test_composed_policy_old_preferences_fade_but_do_not_disappear(self):
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        self.store.append(
            self._pref(
                preference_id="fresh",
                recorded_utc=now,
                relevance_decay_half_life_days=30,
                encoded_modifier=10,
            )
        )
        self.store.append(
            self._pref(
                preference_id="very-old",
                recorded_utc=now - timedelta(days=300),
                relevance_decay_half_life_days=30,
                encoded_modifier=0,
            )
        )

        policy = composed_policy(
            "bond-a",
            PreferenceClass.LANE_CEILING,
            now_utc=now,
            store=self.store,
        )

        self.assertEqual(policy.owner_interrupting_daily_max_count, 10)

    def test_composed_policy_clamps_observed_pressure_to_charter_floor(self):
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        self.store.append(
            self._pref(
                preference_id="observed-below-floor",
                bond_id="firstborn",
                recorded_utc=now,
                expressed_by=PreferenceExpressedBy.OWNER_OBSERVED,
                target_field="owner_interrupting_daily_max_count",
                encoded_modifier=1,
            )
        )

        policy = composed_policy(
            "firstborn",
            PreferenceClass.LANE_CEILING,
            now_utc=now,
            store=self.store,
        )

        self.assertEqual(policy.owner_interrupting_daily_max_count, 3)

    def test_unrelated_explicit_preference_does_not_unlock_observed_floor_reduction(self):
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        self.store.append(
            self._pref(
                preference_id="observed-below-floor",
                bond_id="firstborn",
                recorded_utc=now,
                expressed_by=PreferenceExpressedBy.OWNER_OBSERVED,
                target_field="owner_interrupting_daily_max_count",
                encoded_modifier=1,
            )
        )
        self.store.append(
            self._pref(
                preference_id="explicit-unrelated",
                bond_id="firstborn",
                recorded_utc=now,
                preference_class=PreferenceClass.LANE_CEILING,
                expressed_by=PreferenceExpressedBy.OWNER_EXPLICIT,
                target_field="external_knowledge_daily_call_cap",
                encoded_modifier=150,
            )
        )

        policy = composed_policy(
            "firstborn",
            PreferenceClass.LANE_CEILING,
            now_utc=now,
            store=self.store,
        )

        self.assertEqual(policy.owner_interrupting_daily_max_count, 3)
        self.assertEqual(policy.external_knowledge_daily_call_cap, 150)

    def test_observed_preference_cannot_expand_above_firstborn_declaration(self):
        now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
        self.store.append(
            self._pref(
                preference_id="observed-above-declaration",
                bond_id="firstborn",
                recorded_utc=now,
                expressed_by=PreferenceExpressedBy.OWNER_OBSERVED,
                target_field="owner_interrupting_daily_max_count",
                encoded_modifier=99,
            )
        )

        policy = composed_policy(
            "firstborn",
            PreferenceClass.LANE_CEILING,
            now_utc=now,
            store=self.store,
        )

        self.assertEqual(policy.owner_interrupting_daily_max_count, 10)

    def test_invalid_modifier_field_is_refused_before_storage(self):
        with self.assertRaisesRegex(ValueError, "unsupported autonomy policy field"):
            self.store.append(
                self._pref(
                    preference_id="bad-field",
                    target_field="not_a_policy_field",
                )
            )

    def test_digest_fields_must_be_hmac_sha256_digests(self):
        with self.assertRaisesRegex(ValueError, "pattern_digest must be hmac-sha256"):
            self.store.append(
                self._pref(
                    preference_id="raw-pattern",
                    pattern_digest="Rohit said stop interrupting",
                )
            )

        with self.assertRaisesRegex(ValueError, "notes_digest must be hmac-sha256"):
            self.store.append(
                self._pref(
                    preference_id="raw-notes",
                    pattern_digest="hmac-sha256:" + "c" * 64,
                    notes_digest="raw notes about a private reply",
                )
            )

    def test_recorded_utc_must_be_timezone_aware_utc(self):
        with self.assertRaisesRegex(ValueError, "recorded_utc must be timezone-aware UTC"):
            self.store.append(
                self._pref(
                    preference_id="naive-time",
                    recorded_utc=datetime(2026, 5, 26, 12, 0),
                )
            )

        with self.assertRaisesRegex(ValueError, "recorded_utc must be timezone-aware UTC"):
            self.store.append(
                self._pref(
                    preference_id="offset-time",
                    recorded_utc=datetime(
                        2026,
                        5,
                        26,
                        7,
                        0,
                        tzinfo=timezone(timedelta(hours=-5)),
                    ),
                )
            )

    def test_preference_class_can_only_modify_its_allowed_policy_fields(self):
        with self.assertRaisesRegex(ValueError, "cannot modify"):
            self.store.append(
                self._pref(
                    preference_id="quiet-period-cost-cap",
                    preference_class=PreferenceClass.QUIET_PERIOD,
                    target_field="external_knowledge_cost_cap_cents",
                )
            )

    def test_quiet_hours_tuple_modifier_is_not_part_of_numeric_v1(self):
        with self.assertRaisesRegex(ValueError, "unsupported autonomy policy field"):
            self.store.append(
                self._pref(
                    preference_id="quiet-hours-tuple",
                    preference_class=PreferenceClass.QUIET_PERIOD,
                    target_field="owner_interrupting_quiet_hours",
                    encoded_modifier=23,
                )
            )

    def test_module_level_preferences_default_to_memory_db(self):
        self.store.append(self._pref(preference_id="default-store"))

        rows = preferences_for_bond_and_class(
            "bond-a",
            PreferenceClass.LANE_CEILING,
            store=self.store,
        )

        self.assertEqual([row.preference_id for row in rows], ["default-store"])


if __name__ == "__main__":
    unittest.main()
