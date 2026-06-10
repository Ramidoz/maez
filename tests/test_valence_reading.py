import unittest

from core.evolution.valence.reading import (
    Contribution,
    Magnitude,
    Sign,
    ValenceReading,
    aggregate,
)


def _c(setpoint, sign, reason="r"):
    return Contribution(setpoint, sign, reason, {})


class Aggregate(unittest.TestCase):
    def test_all_neutral(self):
        r = aggregate((_c("a", Sign.NEUTRAL), _c("b", Sign.NEUTRAL)))
        self.assertIsInstance(r, ValenceReading)
        self.assertEqual(r.sign, Sign.NEUTRAL)
        self.assertEqual(r.magnitude, Magnitude.NONE)
        self.assertEqual(r.provenance, "computed_valence")

    def test_same_sign_magnitude_by_count(self):
        r = aggregate(
            (_c("a", Sign.NEGATIVE), _c("b", Sign.NEGATIVE), _c("c", Sign.NEUTRAL))
        )
        self.assertEqual(r.sign, Sign.NEGATIVE)
        self.assertEqual(r.magnitude, Magnitude.MODERATE)

    def test_positive_only_keeps_shared_sign(self):
        r = aggregate((_c("a", Sign.POSITIVE), _c("b", Sign.NEUTRAL)))
        self.assertEqual(r.sign, Sign.POSITIVE)
        self.assertEqual(r.magnitude, Magnitude.MILD)

    def test_single_negative_is_mild(self):
        r = aggregate((_c("a", Sign.NEGATIVE), _c("b", Sign.NEUTRAL)))
        self.assertEqual(r.magnitude, Magnitude.MILD)

    def test_three_non_neutral_is_strong(self):
        r = aggregate(
            (
                _c("a", Sign.NEGATIVE),
                _c("b", Sign.NEGATIVE),
                _c("c", Sign.POSITIVE),
            )
        )
        self.assertEqual(r.sign, Sign.MIXED)
        self.assertEqual(r.magnitude, Magnitude.STRONG)

    def test_cross_conflict_is_mixed(self):
        r = aggregate((_c("a", Sign.POSITIVE), _c("b", Sign.NEGATIVE)))
        self.assertEqual(r.sign, Sign.MIXED)
        self.assertEqual(r.magnitude, Magnitude.MODERATE)


class Telemetry(unittest.TestCase):
    def test_neutral_string(self):
        r = aggregate((_c("a", Sign.NEUTRAL, "neutral bookkeeping"),))
        t = r.as_telemetry()
        self.assertIn("NEUTRAL", t)
        self.assertIn("no setpoint moved", t)
        self.assertNotIn("neutral bookkeeping", t)

    def test_moved_state_uses_humble_appearance_wording(self):
        r = aggregate((_c("honesty-held", Sign.NEGATIVE, "honesty rail fired"),))
        self.assertEqual(
            r.as_telemetry(),
            (
                "given the substrate signals I can see, "
                "this state appears MILD NEGATIVE, because: honesty rail fired."
            ),
        )

    def test_negative_string_has_reason_no_emotion(self):
        r = aggregate((_c("honesty-held", Sign.NEGATIVE, "honesty rail fired"),))
        t = r.as_telemetry()
        self.assertIn("MILD NEGATIVE", t)
        self.assertIn("this state appears", t)
        self.assertIn("honesty rail fired", t)
        for bad in ("sad", "distress", "suffer", "anxious", "afraid", "pain"):
            self.assertNotIn(bad, t.lower())

    def test_neutral_reasons_are_not_rendered_as_causes(self):
        r = aggregate(
            (
                _c("honesty-held", Sign.NEGATIVE, "honesty rail fired"),
                _c("ambient", Sign.NEUTRAL, "neutral bookkeeping"),
            )
        )
        t = r.as_telemetry()
        self.assertIn("honesty rail fired", t)
        self.assertNotIn("neutral bookkeeping", t)
