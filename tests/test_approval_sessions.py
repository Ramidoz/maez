# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.approval_sessions.

Approval sessions persist a time-limited blanket grant when the user
says "reading is fine" in natural language, so subsequent read-safe
ops auto-execute instead of stacking proposal cards."""
from __future__ import annotations

import time
import unittest

from core import approval_sessions as ap


class ReadSafeClassifier(unittest.TestCase):
    def test_single_read_safe_commands(self):
        for cmd in (
            "systemctl is-active maez",
            "ps aux",
            "df -h",
            "ls /home",
            "cat /etc/hostname",
            "grep foo bar.log",
            "journalctl -u maez",
            "uptime",
            "nvidia-smi",
        ):
            self.assertTrue(ap.is_read_safe_cmd(cmd),
                f"expected read-safe: {cmd!r}")

    def test_compound_read_safe_commands(self):
        """Chains of read-safe commands (&&, ||, ;) should pass."""
        for cmd in (
            "systemctl is-active maez && systemctl is-active llama-server",
            "systemctl is-active maez || systemctl is-active llama-server",
            "ps aux; df -h",
            "uptime && free -h && df -h",
        ):
            self.assertTrue(ap.is_read_safe_cmd(cmd),
                f"expected compound read-safe: {cmd!r}")

    def test_unsafe_commands_rejected(self):
        for cmd in (
            "rm -rf /tmp/x",
            "cat /etc/passwd > /tmp/out",
            "sudo systemctl restart maez",
            "systemctl restart maez",
            "ps aux | grep maez",           # pipe disqualifies
            "systemctl is-active maez && rm -rf /tmp",  # compound-with-unsafe
            "echo hi > /tmp/x",
            "mv /a /b",
            "apt install foo",
            "",
        ):
            self.assertFalse(ap.is_read_safe_cmd(cmd),
                f"expected REJECTED: {cmd!r}")

    def test_none_and_nonstring(self):
        self.assertFalse(ap.is_read_safe_cmd(None))
        self.assertFalse(ap.is_read_safe_cmd(123))
        self.assertFalse(ap.is_read_safe_cmd([]))


class GrantDetection(unittest.TestCase):
    def setUp(self):
        ap._diag_clear_for_test()

    def tearDown(self):
        ap._diag_clear_for_test()

    def test_explicit_reading_is_fine_grants_read_safe(self):
        granted = ap.detect_and_grant(
            "Yes you are handling it perfectly. Reading is absolutely "
            "fine and necessary for you to know about yourself"
        )
        self.assertIn("read_safe", granted)
        self.assertTrue(ap.is_active("read_safe"))

    def test_you_can_read_anything_grants(self):
        granted = ap.detect_and_grant("You can read anything you need")
        self.assertIn("read_safe", granted)

    def test_blanket_phrase_grants(self):
        granted = ap.detect_and_grant("blanket approval to read")
        self.assertIn("read_safe", granted)

    def test_ambiguous_text_does_not_grant(self):
        """Natural language that MENTIONS reading but doesn't grant."""
        for text in (
            "how are you reading this",
            "I don't like reading",
            "can you read this file",
            "yes",
            "",
        ):
            ap._diag_clear_for_test()
            granted = ap.detect_and_grant(text)
            self.assertEqual(granted, [],
                f"unexpected grant from: {text!r}")
            self.assertFalse(ap.is_active("read_safe"))


class SessionLifecycle(unittest.TestCase):
    def setUp(self):
        ap._diag_clear_for_test()

    def tearDown(self):
        ap._diag_clear_for_test()

    def test_grant_and_revoke(self):
        ap.grant("read_safe", duration_seconds=60)
        self.assertTrue(ap.is_active("read_safe"))
        ap.revoke("read_safe")
        self.assertFalse(ap.is_active("read_safe"))

    def test_expired_session_is_not_active(self):
        # Grant with negative duration → immediately expired
        ap.grant("read_safe", duration_seconds=-1)
        self.assertFalse(ap.is_active("read_safe"))

    def test_describe_only_lists_active(self):
        ap.grant("read_safe", duration_seconds=60)
        ap.grant("expired_kind", duration_seconds=-1)
        d = ap.describe()
        self.assertIn("read_safe", d)
        self.assertNotIn("expired_kind", d)
        self.assertGreater(d["read_safe"]["seconds_remaining"], 0)


if __name__ == "__main__":
    unittest.main()
