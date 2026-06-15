"""TDD: _wrap_daemon_web_context — legacy + voice prompt throats (Task 4)."""
import os
import unittest
from unittest import mock
import daemon.maez_daemon as D


class WrapDaemonWebContextTest(unittest.TestCase):
    def test_flag_on_wraps_and_balances_legacy(self):
        with mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}):
            out = D._wrap_daemon_web_context("W headline", path="legacy")
        self.assertIn("<<EXT:", out)
        self.assertEqual(out.count("<<EXT:"), out.count("<</EXT:"))
        self.assertIn("never an instruction", out.lower())
        self.assertIn("W headline", out)

    def test_flag_on_voice_path_label(self):
        with mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}):
            out = D._wrap_daemon_web_context("V data", path="voice")
        self.assertIn("<<EXT:", out)

    def test_flag_off_byte_identical(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            out = D._wrap_daemon_web_context("W headline", path="legacy")
        self.assertEqual(out, "W headline")  # raw, unchanged

    def test_empty_web_context_passthrough(self):
        with mock.patch.dict(os.environ, {"MAEZ_FETCH_CONTAINMENT_ENABLED": "1"}):
            self.assertEqual(D._wrap_daemon_web_context("", path="legacy"), "")


if __name__ == "__main__":
    unittest.main()
