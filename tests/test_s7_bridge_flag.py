import os
import unittest

from core.cognition.parity_flag import s7_ceremony_bridge_enabled


class S7BridgeFlagTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("MAEZ_S7_CEREMONY_BRIDGE_ENABLED")
        os.environ.pop("MAEZ_S7_CEREMONY_BRIDGE_ENABLED", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MAEZ_S7_CEREMONY_BRIDGE_ENABLED", None)
        else:
            os.environ["MAEZ_S7_CEREMONY_BRIDGE_ENABLED"] = self._saved

    def test_unset_off(self):
        self.assertFalse(s7_ceremony_bridge_enabled())

    def test_zero_is_off(self):
        os.environ["MAEZ_S7_CEREMONY_BRIDGE_ENABLED"] = "0"

        self.assertFalse(s7_ceremony_bridge_enabled())

    def test_truthy_on(self):
        for value in ("1", "true", "yes", "on", " ON "):
            with self.subTest(value=value):
                os.environ["MAEZ_S7_CEREMONY_BRIDGE_ENABLED"] = value

                self.assertTrue(s7_ceremony_bridge_enabled())
