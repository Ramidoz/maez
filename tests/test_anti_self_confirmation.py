from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from core.policies.autonomy_preferences import (
    DeliveredOutreachSample,
    PreferenceExpressedBy,
    SuppressionEvent,
    SuppressionKind,
    owner_observed_preference_from_response_window,
)


class AntiSelfConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 5, 26, 20, 0, tzinfo=UTC)
        self.pattern_digest = "hmac-sha256:" + "e" * 64

    def _sample(
        self,
        index: int,
        *,
        bond_id: str = "bond-a",
        owner_response: str = "declined_without_teaching",
    ) -> DeliveredOutreachSample:
        return DeliveredOutreachSample(
            bond_id=bond_id,
            delivered_utc=self.now + timedelta(minutes=index * 40),
            owner_response=owner_response,
        )

    def test_suppression_events_excluded_for_all_three_kinds(self):
        samples = [
            self._sample(0, owner_response="declined_without_teaching"),
            self._sample(1, owner_response="declined_without_teaching"),
            self._sample(2, owner_response="declined_without_teaching"),
            *[self._sample(index, owner_response="acknowledged") for index in range(3, 8)],
        ]
        suppression_events = [
            SuppressionEvent(
                bond_id="bond-a",
                occurred_utc=samples[0].delivered_utc,
                suppression_kind=SuppressionKind.SIGNAL_GATED,
            ),
            SuppressionEvent(
                bond_id="bond-a",
                occurred_utc=samples[1].delivered_utc,
                suppression_kind=SuppressionKind.REFLECTION_DEFERRED,
            ),
            SuppressionEvent(
                bond_id="bond-a",
                occurred_utc=samples[2].delivered_utc,
                suppression_kind=SuppressionKind.EXTRACTION_BLOCKED,
            ),
        ]

        preference = owner_observed_preference_from_response_window(
            bond_id="bond-a",
            samples=samples,
            suppression_events=suppression_events,
            preference_id="observed-1",
            pattern_digest=self.pattern_digest,
            target_field="owner_interrupting_minimum_importance",
            encoded_modifier=0.9,
            recorded_utc=self.now,
        )

        self.assertIsNotNone(preference)
        assert preference is not None
        self.assertEqual(preference.expressed_by, PreferenceExpressedBy.OWNER_OBSERVED)
        self.assertEqual(preference.weight, 0.3)

    def test_single_suppressed_outreach_cannot_produce_preference(self):
        samples = [self._sample(0)]
        suppression_events = [
            SuppressionEvent(
                bond_id="bond-a",
                occurred_utc=samples[0].delivered_utc,
                suppression_kind=SuppressionKind.EXTRACTION_BLOCKED,
            )
        ]

        preference = owner_observed_preference_from_response_window(
            bond_id="bond-a",
            samples=samples,
            suppression_events=suppression_events,
            preference_id="observed-2",
            pattern_digest=self.pattern_digest,
            target_field="owner_interrupting_minimum_importance",
            encoded_modifier=0.9,
            recorded_utc=self.now,
        )

        self.assertIsNone(preference)

    def test_minimum_sample_size_uses_delivered_unsuppressed_same_bond_only(self):
        samples = [self._sample(index) for index in range(4)]
        samples.append(self._sample(5, bond_id="bond-b"))

        preference = owner_observed_preference_from_response_window(
            bond_id="bond-a",
            samples=samples,
            suppression_events=[],
            preference_id="observed-3",
            pattern_digest=self.pattern_digest,
            target_field="owner_interrupting_minimum_importance",
            encoded_modifier=0.9,
            recorded_utc=self.now,
        )

        self.assertIsNone(preference)

    def test_suppression_kind_is_closed_vocabulary(self):
        with self.assertRaisesRegex(ValueError, "suppression_kind must be SuppressionKind"):
            owner_observed_preference_from_response_window(
                bond_id="bond-a",
                samples=[self._sample(index) for index in range(5)],
                suppression_events=[
                    SuppressionEvent(
                        bond_id="bond-a",
                        occurred_utc=self.now,
                        suppression_kind="EXTRACTION_BLOCKED",  # type: ignore[arg-type]
                    )
                ],
                preference_id="observed-4",
                pattern_digest=self.pattern_digest,
                target_field="owner_interrupting_minimum_importance",
                encoded_modifier=0.9,
                recorded_utc=self.now,
            )

    def test_owner_response_is_closed_vocabulary(self):
        sample = DeliveredOutreachSample(
            bond_id="bond-a",
            delivered_utc=self.now,
            owner_response="later_maybe",
        )

        with self.assertRaisesRegex(ValueError, "unsupported owner_response"):
            owner_observed_preference_from_response_window(
                bond_id="bond-a",
                samples=[sample, *[self._sample(index + 1) for index in range(4)]],
                suppression_events=[],
                preference_id="observed-5",
                pattern_digest=self.pattern_digest,
                target_field="owner_interrupting_minimum_importance",
                encoded_modifier=0.9,
                recorded_utc=self.now,
            )

    def test_owner_response_is_validated_before_sample_size(self):
        sample = DeliveredOutreachSample(
            bond_id="bond-a",
            delivered_utc=self.now,
            owner_response="later_maybe",
        )

        with self.assertRaisesRegex(ValueError, "unsupported owner_response"):
            owner_observed_preference_from_response_window(
                bond_id="bond-a",
                samples=[sample],
                suppression_events=[],
                preference_id="observed-6",
                pattern_digest=self.pattern_digest,
                target_field="owner_interrupting_minimum_importance",
                encoded_modifier=0.9,
                recorded_utc=self.now,
            )


if __name__ == "__main__":
    unittest.main()
