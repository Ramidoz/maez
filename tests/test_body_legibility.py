import os
import unittest
from unittest import mock


class AffordanceTests(unittest.TestCase):
    def test_web_sense_affordance_is_state_aware(self):
        from core.cognition.capability_card import _affordance

        self.assertEqual(
            _affordance("web sense", "healthy"),
            "can retrieve current external information",
        )
        self.assertNotIn("can retrieve", _affordance("web sense", "degraded") or "")
        self.assertNotIn("can retrieve", _affordance("web sense", "unknown") or "")
        self.assertIsNotNone(_affordance("web sense", "degraded"))

    def test_affordance_is_generic_no_examples(self):
        from core.cognition.capability_card import _affordance

        text = (_affordance("web sense", "healthy") or "").lower()
        for banned in ("weather", "stock", "news", "sports", "forecast"):
            self.assertNotIn(banned, text)

    def test_unknown_sense_has_no_affordance(self):
        from core.cognition.capability_card import _affordance

        self.assertIsNone(_affordance("felt time", "attached"))

    def test_flag_helper_strict(self):
        from core.cognition.capability_card import body_legibility_enabled

        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "1"}):
            self.assertTrue(body_legibility_enabled())
        with mock.patch.dict(os.environ, {"MAEZ_BODY_LEGIBILITY": "0"}):
            self.assertFalse(body_legibility_enabled())


if __name__ == "__main__":
    unittest.main()
