import os
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


class OwnerPrivateGate(unittest.TestCase):
    def _patch(self, *, claimed, loopback, cookie_user=None, owner=False):
        acc = mock.Mock()
        acc.owner_claimed.return_value = claimed
        acc.get_by_token.return_value = cookie_user
        acc.get_user_record.return_value = (
            ({"web_owner": 1} if owner else {"web_owner": 0}) if cookie_user else None)
        req = mock.Mock(
            remote_addr=("127.0.0.1" if loopback else "203.0.113.7"),
            headers={}, cookies=({"maez_token": "t"} if cookie_user else {}),
            args={})
        return mock.patch.object(W, "accounts", acc), mock.patch.object(W, "request", req)

    def test_unclaimed_loopback_allows(self):
        a, r = self._patch(claimed=False, loopback=True)
        with a, r: self.assertTrue(W._owner_private_auth_ok())

    def test_unclaimed_remote_denies(self):
        a, r = self._patch(claimed=False, loopback=False)
        with a, r: self.assertFalse(W._owner_private_auth_ok())

    def test_claimed_owner_allows(self):
        a, r = self._patch(claimed=True, loopback=False, cookie_user={"uuid": "u"}, owner=True)
        with a, r: self.assertTrue(W._owner_private_auth_ok())

    def test_claimed_nonowner_denies(self):
        a, r = self._patch(claimed=True, loopback=True, cookie_user={"uuid": "u"}, owner=False)
        with a, r: self.assertFalse(W._owner_private_auth_ok())

    def test_no_query_token_bypass_when_claimed(self):
        acc = mock.Mock(owner_claimed=lambda: True, get_by_token=lambda t: None)
        req = mock.Mock(remote_addr="127.0.0.1", headers={}, cookies={},
                        args={"web_token": "x", "test_t": "1"})
        with mock.patch.object(W, "accounts", acc), mock.patch.object(W, "request", req):
            self.assertFalse(W._owner_private_auth_ok())

    def test_debug_auth_delegates_to_gate(self):
        a, r = self._patch(claimed=False, loopback=True)
        with a, r: self.assertTrue(W._debug_auth_ok())


class NoTelegramAtWebEdge(unittest.TestCase):
    def test_only_definition_reference_remains(self):
        # After migration, _is_private_owner_bridge appears ONLY at its def in web_interface.py
        import pathlib
        src = pathlib.Path(W.__file__).read_text()
        hits = [ln for ln in src.splitlines() if "_is_private_owner_bridge" in ln]
        # exactly one: the `def _is_private_owner_bridge(...)` line
        self.assertEqual(len(hits), 1, hits)
        self.assertTrue(hits[0].lstrip().startswith("def _is_private_owner_bridge"))


class DegradedStoreUnreachable(unittest.TestCase):
    def test_loopback_recovers_remote_fails_closed_on_store_error(self):
        broken = mock.Mock()
        broken.owner_claimed.side_effect = RuntimeError("db down")
        for loopback, expected in ((True, True), (False, False)):
            req = mock.Mock(remote_addr=("127.0.0.1" if loopback else "203.0.113.7"),
                            headers={}, cookies={}, args={})
            with mock.patch.object(W, "accounts", broken), mock.patch.object(W, "request", req):
                self.assertEqual(W._owner_private_auth_ok(), expected, f"loopback={loopback}")

    def test_midgate_store_failure_also_fails_safe(self):
        broken = mock.Mock()
        broken.owner_claimed.return_value = True          # passes the first call
        broken.get_by_token.side_effect = RuntimeError("db down mid-gate")
        for loopback, expected in ((True, True), (False, False)):
            req = mock.Mock(remote_addr=("127.0.0.1" if loopback else "203.0.113.7"),
                            headers={}, cookies={"maez_token": "t"}, args={})
            with mock.patch.object(W, "accounts", broken), mock.patch.object(W, "request", req):
                self.assertEqual(W._owner_private_auth_ok(), expected, f"loopback={loopback}")


class NeverLockout(unittest.TestCase):
    def test_remote_stays_locked_out_but_local_recovery_path_exists(self):
        # Owner claimed but the cookie/account can't resolve -> remote denied...
        acc = mock.Mock(owner_claimed=lambda: True, get_by_token=lambda t: None)
        req_remote = mock.Mock(remote_addr="203.0.113.7", headers={}, cookies={}, args={})
        with mock.patch.object(W, "accounts", acc), mock.patch.object(W, "request", req_remote):
            self.assertFalse(W._owner_private_auth_ok())
        # ...and the LOCAL recovery mechanism (the CLI rebind path) structurally exists.
        cli = __import__("scripts.maez_cli", fromlist=["cmd_own_claim"])
        self.assertTrue(hasattr(cli, "cmd_own_claim"))
