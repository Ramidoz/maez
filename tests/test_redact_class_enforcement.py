from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest import mock

_PRIV = "secret-pii-9a2b@example.test"
_PUB_SYS = "PUBLIC-SYSTEM-MARKER"
_PUB_USER = "PUBLIC-USER-MARKER"


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


def _decision(sanitized_segments, decision="redact"):
    return SimpleNamespace(decision=decision, sanitized_segments=list(sanitized_segments))


class SanitizedForwardTests(unittest.TestCase):
    def test_mixed_system_and_user_split_preserved(self):
        from core.subscription_proxy import server

        part_counts = [("system", 2), ("user", 2)]
        sanitized = [
            f"{_PUB_SYS} ",
            "[REDACTED_EMAIL]",
            f"{_PUB_USER} ",
            "[REDACTED_EMAIL]",
        ]
        fwd_system, fwd_prompt = server._sanitized_forward_payload(
            _decision(sanitized),
            part_counts,
            system_prompt=f"{_PUB_SYS} {_PRIV}",
            prompt=f"{_PUB_USER} {_PRIV}",
        )

        self.assertIn(_PUB_SYS, fwd_system)
        self.assertIn(_PUB_USER, fwd_prompt)
        self.assertNotIn(_PUB_USER, fwd_system)
        self.assertNotIn(_PUB_SYS, fwd_prompt)
        self.assertNotIn(_PRIV, fwd_system)
        self.assertNotIn(_PRIV, fwd_prompt)

    def test_count_mismatch_fails_closed(self):
        from core.subscription_proxy import server

        result = server._sanitized_forward_payload(
            _decision(["a", "b"]),
            [("system", 1), ("user", 2)],
            system_prompt="s",
            prompt="p",
        )
        self.assertIsNone(result)

    def test_legacy_path_sanitizes_prompt_keeps_system(self):
        from core.subscription_proxy import server

        fwd_system, fwd_prompt = server._sanitized_forward_payload(
            _decision(["[REDACTED_EMAIL] tail"]),
            [("legacy_prompt", 1)],
            system_prompt="orig-system",
            prompt=f"{_PRIV} tail",
        )
        self.assertEqual(fwd_system, "orig-system")
        self.assertNotIn(_PRIV, fwd_prompt)


if __name__ == "__main__":
    unittest.main()
