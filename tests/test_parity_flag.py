from __future__ import annotations

import os
import unittest


class ParityFlagTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_SURFACE_PARITY_ENABLED", None))

    def test_default_off(self):
        from core.cognition.parity_flag import surface_parity_enabled

        self.assertFalse(surface_parity_enabled())

    def test_strict_truthy(self):
        from core.cognition.parity_flag import surface_parity_enabled

        for value in ("1", "true", "yes", "on", "ON", "True"):
            os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = value
            self.assertTrue(surface_parity_enabled(), value)

    def test_zero_is_off_not_on(self):
        from core.cognition.parity_flag import surface_parity_enabled

        for value in ("0", "false", "no", "off", ""):
            os.environ["MAEZ_SURFACE_PARITY_ENABLED"] = value
            self.assertFalse(surface_parity_enabled(), value)
