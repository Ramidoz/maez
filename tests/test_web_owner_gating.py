import os
import sys
import unittest
from unittest import mock

# Inject dummy secrets so skills.web_interface can be imported in test context.
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

from skills import web_interface as W


class LoopbackAndOwner(unittest.TestCase):
    def test_is_owner_reads_web_owner_only(self):
        self.assertTrue(W._is_owner({"web_owner": 1}))
        self.assertFalse(W._is_owner({"web_owner": 0}))
        self.assertFalse(W._is_owner(None))
        # MUST NOT consult telegram-derived fields:
        self.assertFalse(W._is_owner({"web_owner": 0, "private_owner_bridge": True}))

    def test_loopback_true_for_127_v6_and_mapped(self):
        for addr in ("127.0.0.1", "127.0.0.5", "::1", "::ffff:127.0.0.1"):
            with mock.patch.object(W, "request", mock.Mock(remote_addr=addr, headers={})):
                self.assertTrue(W._request_is_loopback(), addr)

    def test_remote_is_not_loopback_and_xff_never_upgrades(self):
        with mock.patch.object(W, "request",
                               mock.Mock(remote_addr="203.0.113.7",
                                         headers={"X-Forwarded-For": "127.0.0.1"})):
            self.assertFalse(W._request_is_loopback())
