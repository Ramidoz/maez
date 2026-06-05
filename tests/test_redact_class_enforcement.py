from __future__ import annotations

import os
import unittest
from unittest import mock


class RedactEnforcedHelperTests(unittest.TestCase):
    def _helper(self):
        from core.subscription_proxy import server

        return server

    def test_default_is_shadow(self):
        server = self._helper()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_EGRESS_REDACT_SHADOW", None)
            self.assertFalse(server._redact_enforced())

    def test_enforce_opt_in(self):
        server = self._helper()
        with mock.patch.dict(
            os.environ, {"MAEZ_EGRESS_REDACT_SHADOW": "0"}, clear=False
        ):
            self.assertTrue(server._redact_enforced())

    def test_kill_switch_reverts(self):
        server = self._helper()
        with mock.patch.dict(
            os.environ, {"MAEZ_EGRESS_REDACT_SHADOW": "1"}, clear=False
        ):
            self.assertFalse(server._redact_enforced())


if __name__ == "__main__":
    unittest.main()
