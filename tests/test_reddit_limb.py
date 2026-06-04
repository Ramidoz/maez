# tests/test_reddit_limb.py
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse, parse_qs

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.information_limb import reddit_limb  # noqa: E402


class BuildAuthorizeUrlTests(unittest.TestCase):
    def test_authorize_url_has_required_readonly_params(self):
        url = reddit_limb.build_authorize_url(
            client_id="CID",
            redirect_uri="http://localhost:65010/reddit/callback",
            state="STATE123",
        )
        parsed = urlparse(url)
        q = parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.reddit.com")
        self.assertEqual(parsed.path, "/api/v1/authorize")
        self.assertEqual(q["client_id"], ["CID"])
        self.assertEqual(q["response_type"], ["code"])
        self.assertEqual(q["state"], ["STATE123"])
        self.assertEqual(q["redirect_uri"], ["http://localhost:65010/reddit/callback"])
        self.assertEqual(q["duration"], ["temporary"])   # v0: no refresh token
        self.assertEqual(q["scope"], ["identity"])        # v0: identity-only

    def test_no_secret_in_authorize_url(self):
        url = reddit_limb.build_authorize_url(
            client_id="CID", redirect_uri="http://localhost:65010/reddit/callback", state="S",
        )
        self.assertNotIn("secret", url.lower())


class ExchangeCodeTests(unittest.TestCase):
    def _fake_response(self, status=200, payload=None):
        resp = mock.Mock()
        resp.status_code = status
        resp.json.return_value = payload or {
            "access_token": "TOK", "token_type": "bearer",
            "expires_in": 3600, "scope": "identity",
        }
        return resp

    def test_exchange_uses_basic_auth_empty_password_and_grant(self):
        with mock.patch.object(reddit_limb.requests, "post") as post:
            post.return_value = self._fake_response()
            session = reddit_limb.exchange_code_for_token(
                client_id="CID", code="CODE",
                redirect_uri="http://localhost:65010/reddit/callback",
            )
        # installed app: HTTP Basic with client_id and EMPTY password
        _, kwargs = post.call_args
        self.assertEqual(kwargs["auth"], ("CID", ""))
        self.assertEqual(kwargs["data"]["grant_type"], "authorization_code")
        self.assertEqual(kwargs["data"]["code"], "CODE")
        self.assertIn("User-Agent", kwargs["headers"])
        self.assertEqual(session.access_token, "TOK")
        self.assertEqual(session.scopes, ["identity"])
        self.assertGreater(session.expires_at, session.obtained_at)

    def test_exchange_raises_on_non_200(self):
        with mock.patch.object(reddit_limb.requests, "post") as post:
            post.return_value = self._fake_response(status=401, payload={"error": "x"})
            with self.assertRaises(reddit_limb.RedditAuthError):
                reddit_limb.exchange_code_for_token(
                    client_id="CID", code="BAD",
                    redirect_uri="http://localhost:65010/reddit/callback",
                )

    def test_exchange_raises_on_missing_or_broader_scope(self):
        # fail closed: a token response with no scope, or a broader scope, is
        # not identity proof
        for payload in ({"access_token": "T", "expires_in": 3600},                       # no scope
                        {"access_token": "T", "scope": "identity history", "expires_in": 3600}):
            with mock.patch.object(reddit_limb.requests, "post") as post:
                post.return_value = self._fake_response(payload=payload)
                with self.assertRaises(reddit_limb.RedditAuthError):
                    reddit_limb.exchange_code_for_token(
                        client_id="CID", code="C",
                        redirect_uri="http://localhost:65010/reddit/callback",
                    )


class FetchIdentityTests(unittest.TestCase):
    def _session(self):
        now = 1000.0
        return reddit_limb.RedditSession(
            access_token="TOK", scopes=["identity"], obtained_at=now, expires_at=now + 3600
        )

    def _patch_get(self, status):
        resp = mock.Mock()
        resp.status_code = status
        resp.json.return_value = {"name": "rohit_secret_username", "id": "abc"}
        return mock.patch.object(reddit_limb.requests, "get", return_value=resp)

    def test_200_maps_to_available_and_returns_no_identity(self):
        with self._patch_get(200):
            state = reddit_limb.fetch_identity(self._session())
        self.assertEqual(state, "available")
        # fetch_identity returns ONLY a state string — never identity fields
        self.assertNotIn("rohit_secret_username", str(state))

    def test_status_to_state_mapping(self):
        cases = {401: "auth_error", 403: "revoked", 429: "rate_limited"}
        for status, expected in cases.items():
            with self._patch_get(status):
                self.assertEqual(reddit_limb.fetch_identity(self._session()), expected)

    def test_network_error_maps_to_unreachable(self):
        with mock.patch.object(reddit_limb.requests, "get",
                               side_effect=reddit_limb.requests.RequestException("boom")):
            self.assertEqual(reddit_limb.fetch_identity(self._session()), "unreachable")


class RedditLimbStateTests(unittest.TestCase):
    def test_fresh_limb_is_needs_auth_and_content_free(self):
        limb = reddit_limb.RedditLimb()
        h = limb.health()
        self.assertEqual(h["state"], "needs_auth")
        self.assertIsNone(h["last_success_at"])
        # content-free: keys are a fixed allowlist, no token/identity fields
        self.assertEqual(set(h.keys()), {"state", "last_success_at", "scopes", "expires_in_bucket"})

    def test_set_session_then_available_records_no_token(self):
        limb = reddit_limb.RedditLimb()
        now = 2000.0
        limb.set_session(reddit_limb.RedditSession("SECRET_TOK", ["identity"], now, now + 3600))
        limb.mark_state("available", now=now)
        h = limb.health(now=now)
        self.assertEqual(h["state"], "available")
        self.assertIsNotNone(h["last_success_at"])
        self.assertEqual(h["scopes"], ["identity"])
        # the token must never appear anywhere in the health output
        self.assertNotIn("SECRET_TOK", repr(h))

    def test_expired_session_reports_needs_auth(self):
        limb = reddit_limb.RedditLimb()
        now = 3000.0
        limb.set_session(reddit_limb.RedditSession("T", ["identity"], now, now + 10))
        self.assertEqual(limb.health(now=now + 999)["state"], "needs_auth")

    def test_clear_session_returns_to_needs_auth(self):
        limb = reddit_limb.RedditLimb()
        now = 4000.0
        limb.set_session(reddit_limb.RedditSession("T", ["identity"], now, now + 3600))
        limb.clear_session()
        self.assertEqual(limb.health(now=now)["state"], "needs_auth")


if __name__ == "__main__":
    unittest.main()
