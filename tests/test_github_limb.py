# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""GitHub Limb v0 unit tests — device flow, identity read, in-memory state."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.information_limb import github_limb  # noqa: E402


class DeviceCodeTests(unittest.TestCase):
    def _resp(self, status=200, payload=None):
        r = mock.Mock()
        r.status_code = status
        r.json.return_value = payload or {
            "device_code": "DC", "user_code": "ABCD-1234",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900, "interval": 5,
        }
        return r

    def test_request_device_code_posts_scope_and_parses(self):
        with mock.patch.object(github_limb.requests, "post", return_value=self._resp()) as post:
            grant = github_limb.request_device_code(client_id="CID")
        _, kwargs = post.call_args
        self.assertEqual(kwargs["data"]["client_id"], "CID")
        self.assertEqual(kwargs["data"]["scope"], "read:user")   # identity-only
        self.assertEqual(grant.user_code, "ABCD-1234")
        self.assertEqual(grant.device_code, "DC")
        self.assertEqual(grant.interval, 5)

    def test_request_device_code_raises_on_non_200(self):
        with mock.patch.object(github_limb.requests, "post", return_value=self._resp(status=422)):
            with self.assertRaises(github_limb.GithubAuthError):
                github_limb.request_device_code(client_id="CID")


class PollForTokenTests(unittest.TestCase):
    def _grant(self):
        return github_limb.DeviceCodeGrant(
            device_code="DC", user_code="U", verification_uri="V", interval=1, expires_in=100)

    def _resp(self, payload):
        r = mock.Mock()
        r.content = b"x"
        r.json.return_value = payload
        return r

    def test_pending_then_success(self):
        seq = [self._resp({"error": "authorization_pending"}),
               self._resp({"access_token": "TOK", "scope": "read:user", "token_type": "bearer"})]
        clock = {"t": 0.0}
        with mock.patch.object(github_limb.requests, "post", side_effect=seq):
            session = github_limb.poll_for_token(
                client_id="CID", grant=self._grant(),
                sleep=lambda s: None, now=lambda: clock.__setitem__("t", clock["t"] + 1) or clock["t"],
            )
        self.assertEqual(session.access_token, "TOK")
        self.assertEqual(session.scopes, ["read:user"])

    def test_slow_down_is_handled(self):
        seq = [self._resp({"error": "slow_down", "interval": 7}),
               self._resp({"access_token": "TOK", "scope": "read:user"})]
        clock = {"t": 0.0}
        with mock.patch.object(github_limb.requests, "post", side_effect=seq):
            session = github_limb.poll_for_token(
                client_id="CID", grant=self._grant(),
                sleep=lambda s: None, now=lambda: clock.__setitem__("t", clock["t"] + 1) or clock["t"])
        self.assertEqual(session.access_token, "TOK")

    def test_access_denied_raises(self):
        with mock.patch.object(github_limb.requests, "post",
                               return_value=self._resp({"error": "access_denied"})):
            with self.assertRaises(github_limb.GithubAuthError):
                github_limb.poll_for_token(client_id="CID", grant=self._grant(),
                                           sleep=lambda s: None, now=lambda: 0.0)

    def test_expiry_raises(self):
        # first now() sets the deadline (=0+expires_in); the next now() jumps
        # past it so the while loop never executes → expired.
        calls = {"n": 0}

        def fake_now():
            calls["n"] += 1
            return 0.0 if calls["n"] == 1 else 1e9

        with mock.patch.object(github_limb.requests, "post"):
            with self.assertRaises(github_limb.GithubAuthError):
                github_limb.poll_for_token(client_id="CID", grant=self._grant(),
                                           sleep=lambda s: None, now=fake_now)


class FetchIdentityTests(unittest.TestCase):
    def _session(self):
        now = 1000.0
        return github_limb.GithubSession("TOK", ["read:user"], now, now + 3600)

    def _patch_get(self, status):
        r = mock.Mock()
        r.status_code = status
        r.json.return_value = {"login": "rohit_secret_login", "id": 7}
        return mock.patch.object(github_limb.requests, "get", return_value=r)

    def test_200_available_no_identity_returned(self):
        with self._patch_get(200):
            state = github_limb.fetch_identity(self._session())
        self.assertEqual(state, "available")
        self.assertNotIn("rohit_secret_login", str(state))

    def test_status_mapping(self):
        for status, expected in {401: "auth_error", 403: "revoked", 429: "rate_limited"}.items():
            with self._patch_get(status):
                self.assertEqual(github_limb.fetch_identity(self._session()), expected)

    def test_network_error_unreachable(self):
        with mock.patch.object(github_limb.requests, "get",
                               side_effect=github_limb.requests.RequestException("x")):
            self.assertEqual(github_limb.fetch_identity(self._session()), "unreachable")


class GithubLimbStateTests(unittest.TestCase):
    def test_fresh_is_needs_auth_content_free(self):
        h = github_limb.GithubLimb().health()
        self.assertEqual(h["state"], "needs_auth")
        self.assertEqual(set(h.keys()), {"state", "last_success_at", "scopes", "expires_in_bucket"})

    def test_set_session_available_no_token_in_health(self):
        limb = github_limb.GithubLimb()
        now = 2000.0
        limb.set_session(github_limb.GithubSession("SECRET_TOK", ["read:user"], now, now + 3600))
        limb.mark_state("available", now=now)
        h = limb.health(now=now)
        self.assertEqual(h["state"], "available")
        self.assertEqual(h["scopes"], ["read:user"])
        self.assertNotIn("SECRET_TOK", repr(h))

    def test_expired_is_needs_auth(self):
        limb = github_limb.GithubLimb()
        now = 3000.0
        limb.set_session(github_limb.GithubSession("T", ["read:user"], now, now + 10))
        self.assertEqual(limb.health(now=now + 999)["state"], "needs_auth")

    def test_clear_returns_needs_auth(self):
        limb = github_limb.GithubLimb()
        now = 4000.0
        limb.set_session(github_limb.GithubSession("T", ["read:user"], now, now + 3600))
        limb.clear_session()
        self.assertEqual(limb.health(now=now)["state"], "needs_auth")


if __name__ == "__main__":
    unittest.main()
