import os
import unittest
from unittest import mock
from core.cognition import fetch_screen_flags as F


class FetchScreenFlagsTest(unittest.TestCase):
    def test_containment_strict_on(self):
        for v in ("1", "true", "yes", "on", "ON", "True"):
            with mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": v}):
                self.assertTrue(F.fetch_containment_enabled())

    def test_containment_strict_off(self):
        for v in ("0", "false", "no", "off", "", "wat"):
            with mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": v}):
                self.assertFalse(F.fetch_containment_enabled())

    def test_containment_unset_off(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(F.fetch_containment_enabled())

    def test_shadow_strict_on(self):
        with mock.patch.dict(os.environ, {"MAEZ_FETCH_INJECTION_SHADOW": "1"}):
            self.assertTrue(F.fetch_injection_shadow_enabled())

    def test_shadow_default_off(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(F.fetch_injection_shadow_enabled())
