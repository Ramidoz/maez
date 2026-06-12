import os
import unittest

import core.cognition.grounding_shadow as gs


class GroundingShadowFlagStrictTest(unittest.TestCase):
    """Regression for the bare `if not os.environ.get(...)` footgun: the gate
    must read '0' as DISABLED and must not start the singleton."""

    def setUp(self):
        self._saved = os.environ.get("MAEZ_GROUNDING_SHADOW_ENABLED")
        gs._SHADOW_SINGLETON = None

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MAEZ_GROUNDING_SHADOW_ENABLED", None)
        else:
            os.environ["MAEZ_GROUNDING_SHADOW_ENABLED"] = self._saved
        gs._SHADOW_SINGLETON = None

    def test_zero_disables_and_does_not_start_singleton(self):
        os.environ["MAEZ_GROUNDING_SHADOW_ENABLED"] = "0"
        self.assertIsNone(gs._get_shadow())          # was truthy under the footgun
        self.assertIsNone(gs._SHADOW_SINGLETON)      # singleton never constructed

    def test_unset_disables(self):
        os.environ.pop("MAEZ_GROUNDING_SHADOW_ENABLED", None)
        self.assertIsNone(gs._get_shadow())

    def test_false_word_disables(self):
        os.environ["MAEZ_GROUNDING_SHADOW_ENABLED"] = "false"
        self.assertIsNone(gs._get_shadow())
