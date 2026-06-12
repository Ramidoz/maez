import os
import unittest

from core.cognition.capability_card import voice_boundary_enabled


class VoiceBoundaryFlagTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("MAEZ_VOICE_BOUNDARY_ENABLED")
        os.environ.pop("MAEZ_VOICE_BOUNDARY_ENABLED", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MAEZ_VOICE_BOUNDARY_ENABLED", None)
        else:
            os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = self._saved

    def test_unset_is_off(self):
        self.assertFalse(voice_boundary_enabled())

    def test_zero_is_off_not_truthy(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "0"
        self.assertFalse(voice_boundary_enabled())

    def test_false_no_off_are_off(self):
        for val in ("false", "no", "off", "", "  "):
            os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = val
            self.assertFalse(voice_boundary_enabled(), val)

    def test_truthy_set_enables(self):
        for val in ("1", "true", "yes", "on", "ON", " True "):
            os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = val
            self.assertTrue(voice_boundary_enabled(), val)
