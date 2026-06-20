import unittest
from unittest import mock
import skills.web_interface as wi


def _ctx(remote_addr, cookie=None, xff=None):
    headers = {}
    if xff:
        headers["X-Forwarded-For"] = xff
    env = {"REMOTE_ADDR": remote_addr}
    # Set the cookie directly on the WSGI environ so request.cookies.get(AUTH_COOKIE)
    # actually resolves (Flask test_request_context cookie-via-headers can be finicky).
    if cookie:
        env["HTTP_COOKIE"] = f"{wi.AUTH_COOKIE}={cookie}"
    return wi.app.test_request_context(
        "/api/v1/cockpit/message", environ_base=env, headers=headers
    )


class OwnerPrivateAuthLoopback(unittest.TestCase):
    def test_claimed_loopback_allows_without_cookie(self):
        with _ctx("127.0.0.1"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True):
            self.assertTrue(wi._owner_private_auth_ok())   # physical body IS the owner

    def test_claimed_remote_no_cookie_denied(self):
        with _ctx("10.0.0.5"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True):
            self.assertFalse(wi._owner_private_auth_ok())

    def test_claimed_remote_valid_cookie_allows(self):
        with _ctx("10.0.0.5", cookie="goodtoken"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True), \
             mock.patch.object(wi.accounts, "get_by_token", return_value={"uuid": "u1"}), \
             mock.patch.object(wi.accounts, "get_user_record", return_value={"relationship": "owner", "trust_tier": 3}), \
             mock.patch.object(wi, "_is_owner", return_value=True):
            self.assertTrue(wi._owner_private_auth_ok())

    def test_unclaimed_loopback_allows(self):
        with _ctx("127.0.0.1"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=False):
            self.assertTrue(wi._owner_private_auth_ok())

    def test_xff_spoof_from_remote_peer_denied(self):
        # remote_addr is non-loopback; X-Forwarded-For:127.0.0.1 must NOT upgrade to loopback.
        with _ctx("10.0.0.5", xff="127.0.0.1"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True):
            self.assertFalse(wi._owner_private_auth_ok())

    def test_claimed_loopback_nonowner_cookie_denied(self):
        # The fix: an explicit NON-owner cookie is NOT escalated to owner access even on loopback.
        with _ctx("127.0.0.1", cookie="someusertoken"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True), \
             mock.patch.object(wi.accounts, "get_by_token", return_value={"uuid": "u2"}), \
             mock.patch.object(wi.accounts, "get_user_record", return_value={"relationship": "guest"}), \
             mock.patch.object(wi, "_is_owner", return_value=False):
            self.assertFalse(wi._owner_private_auth_ok())   # explicit non-owner ID wins over loopback

    def test_claimed_loopback_owner_cookie_allows(self):
        # Loopback + a cookie resolving to OWNER -> True (owner's frictionless local access preserved).
        with _ctx("127.0.0.1", cookie="ownertoken"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True), \
             mock.patch.object(wi.accounts, "get_by_token", return_value={"uuid": "u1"}), \
             mock.patch.object(wi.accounts, "get_user_record", return_value={"relationship": "owner", "trust_tier": 3}), \
             mock.patch.object(wi, "_is_owner", return_value=True):
            self.assertTrue(wi._owner_private_auth_ok())

    def test_strict_gate_unchanged_loopback_no_cookie_is_false(self):
        # The STRICT felt-time gate must STILL require the cookie even on loopback (NOT loosened).
        with _ctx("127.0.0.1"), \
             mock.patch.object(wi.accounts, "owner_claimed", return_value=True):
            self.assertFalse(wi._request_has_web_owner_cookie())


if __name__ == "__main__":
    unittest.main()
