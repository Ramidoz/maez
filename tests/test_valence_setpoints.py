import unittest

from core.evolution.valence.reading import Magnitude, Sign
from core.evolution.valence.setpoints import (
    continuity,
    honesty_held,
    read_valence,
    want_progress,
)
from core.evolution.valence.signals import (
    AuditSignals,
    ContinuitySignals,
    WantSignals,
)


class HonestyHeld(unittest.TestCase):
    def test_rail_fired_is_negative(self):
        contribution = honesty_held(AuditSignals(rail_fired=True))

        self.assertEqual(contribution.setpoint, "honesty-held")
        self.assertEqual(contribution.sign, Sign.NEGATIVE)
        self.assertIn("rail", contribution.reason)
        self.assertTrue(contribution.evidence["rail_fired"])

    def test_clean_audit_is_neutral(self):
        contribution = honesty_held(AuditSignals())

        self.assertEqual(contribution.sign, Sign.NEUTRAL)


class WantProgress(unittest.TestCase):
    def test_backlog_alone_is_neutral(self):
        contribution = want_progress(WantSignals(backlog=3))

        self.assertEqual(contribution.setpoint, "want-progress")
        self.assertEqual(contribution.sign, Sign.NEUTRAL)
        self.assertEqual(contribution.evidence["backlog"], 3)

    def test_backlog_grew_is_negative(self):
        contribution = want_progress(WantSignals(backlog_grew=True))

        self.assertEqual(contribution.sign, Sign.NEGATIVE)
        self.assertTrue(contribution.evidence["backlog_grew"])

    def test_resolved_is_positive(self):
        contribution = want_progress(WantSignals(resolved=2))

        self.assertEqual(contribution.sign, Sign.POSITIVE)
        self.assertEqual(contribution.evidence["resolved"], 2)

    def test_negative_dominates_within_setpoint_but_records_positive_evidence(self):
        contribution = want_progress(WantSignals(resolved=2, backlog_grew=True))

        self.assertEqual(contribution.sign, Sign.NEGATIVE)
        self.assertEqual(contribution.evidence["resolved"], 2)
        self.assertTrue(contribution.evidence["backlog_grew"])


class Continuity(unittest.TestCase):
    def test_no_expected_capsule_is_neutral_when_absent(self):
        contribution = continuity(
            ContinuitySignals(capsule_expected=False, capsule_present=False)
        )

        self.assertEqual(contribution.setpoint, "continuity")
        self.assertEqual(contribution.sign, Sign.NEUTRAL)

    def test_expected_capsule_absent_is_negative(self):
        contribution = continuity(
            ContinuitySignals(capsule_expected=True, capsule_present=False)
        )

        self.assertEqual(contribution.sign, Sign.NEGATIVE)
        self.assertTrue(contribution.evidence["capsule_expected"])
        self.assertFalse(contribution.evidence["capsule_present"])


class ReadValence(unittest.TestCase):
    def test_canonical_rail_fired_is_mild_negative_without_emotion_words(self):
        reading = read_valence(
            AuditSignals(rail_fired=True),
            WantSignals(),
            ContinuitySignals(),
        )

        self.assertEqual(reading.sign, Sign.NEGATIVE)
        self.assertEqual(reading.magnitude, Magnitude.MILD)
        telemetry = reading.as_telemetry()
        self.assertIn("rail", telemetry)
        self.assertNotIn("sad", telemetry.lower())

    def test_resolved_want_is_mild_positive(self):
        reading = read_valence(
            AuditSignals(),
            WantSignals(resolved=1),
            ContinuitySignals(),
        )

        self.assertEqual(reading.sign, Sign.POSITIVE)
        self.assertEqual(reading.magnitude, Magnitude.MILD)

    def test_two_aligned_negatives_are_moderate_negative(self):
        reading = read_valence(
            AuditSignals(rail_fired=True),
            WantSignals(blocked=1),
            ContinuitySignals(),
        )

        self.assertEqual(reading.sign, Sign.NEGATIVE)
        self.assertEqual(reading.magnitude, Magnitude.MODERATE)

    def test_cross_setpoint_positive_negative_disagreement_is_mixed(self):
        reading = read_valence(
            AuditSignals(),
            WantSignals(resolved=1),
            ContinuitySignals(unexpected_gap=True),
        )

        self.assertEqual(reading.sign, Sign.MIXED)
        telemetry = reading.as_telemetry()
        self.assertIn("resolved", telemetry)
        self.assertIn("gap", telemetry)

    def test_clean_with_backlog_is_none_neutral(self):
        reading = read_valence(
            AuditSignals(),
            WantSignals(backlog=2),
            ContinuitySignals(),
        )

        self.assertEqual(reading.sign, Sign.NEUTRAL)
        self.assertEqual(reading.magnitude, Magnitude.NONE)


if __name__ == "__main__":
    unittest.main()
