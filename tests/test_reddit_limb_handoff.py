# tests/test_reddit_limb_handoff.py
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.information_limb import reddit_limb  # noqa: E402

SENTINEL = "SENTINEL_ACCESS_TOKEN_DO_NOT_LEAK"


class _Headers(dict):
    def get(self, k, default=None):
        return super().get(k, default)


class HandoffAuthTests(unittest.TestCase):
    def setUp(self):
        os.environ[reddit_limb.REDDIT_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, reddit_limb.REDDIT_HANDOFF_TOKEN_ENV, None)

    def test_missing_secret_is_untrusted(self):
        self.assertFalse(reddit_limb.handoff_trusted(_Headers()))

    def test_wrong_secret_is_untrusted(self):
        self.assertFalse(reddit_limb.handoff_trusted(
            _Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "WRONG"})))

    def test_origin_header_is_untrusted_even_with_right_secret(self):
        self.assertFalse(reddit_limb.handoff_trusted(
            _Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET", "Origin": "http://evil"})))

    def test_right_secret_no_origin_is_trusted(self):
        self.assertTrue(reddit_limb.handoff_trusted(
            _Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"})))

    def test_auth_before_envelope_body_loader_never_called_on_bad_secret(self):
        """THE load-bearing test: a bad secret returns 403 and the body
        (which carries the live token) is NEVER read."""
        limb = reddit_limb.RedditLimb()
        body_loader = mock.Mock(return_value={"access_token": SENTINEL,
                                              "scopes": ["identity"], "expires_in": 3600})
        result, status = reddit_limb.handle_handoff(
            headers=_Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "WRONG"}),
            body_loader=body_loader, limb=limb,
        )
        self.assertEqual(status, 403)
        body_loader.assert_not_called()                  # envelope never opened
        self.assertNotIn(SENTINEL, repr(result))         # token nowhere in response

    def test_valid_handoff_sets_session_and_fetches(self):
        limb = reddit_limb.RedditLimb()
        body_loader = mock.Mock(return_value={"access_token": SENTINEL,
                                              "scopes": ["identity"], "expires_in": 3600})
        with mock.patch.object(reddit_limb, "fetch_identity", return_value="available"):
            result, status = reddit_limb.handle_handoff(
                headers=_Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"}),
                body_loader=body_loader, limb=limb,
            )
        self.assertEqual(status, 200)
        body_loader.assert_called_once()
        self.assertEqual(result["state"], "available")
        self.assertNotIn(SENTINEL, repr(result))         # token never echoed back


class HandoffSecretLoadableTests(unittest.TestCase):
    """Codex review blocker 1: the handoff secret must survive Maez's credential
    path. MAEZ_REDDIT_HANDOFF_TOKEN matches the 'TOKEN' marker (treated as a
    secret), so it is scrubbed from config/.env and purged from env unless it is
    in the SECRET_NAMES allowlist that the daemon loads as `optional`."""

    def test_handoff_token_is_a_classified_secret(self):
        from core.infra.secrets import is_secret_name
        self.assertTrue(is_secret_name(reddit_limb.REDDIT_HANDOFF_TOKEN_ENV))

    def test_handoff_token_is_allowlisted_so_it_loads(self):
        from core.infra.secrets import SECRET_NAMES
        self.assertIn(reddit_limb.REDDIT_HANDOFF_TOKEN_ENV, SECRET_NAMES)


class IdentityOnlyPinTests(unittest.TestCase):
    """Codex review blocker 2: identity-only must be enforced at the handoff
    trust boundary, not only in the authorize URL."""

    def setUp(self):
        os.environ[reddit_limb.REDDIT_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, reddit_limb.REDDIT_HANDOFF_TOKEN_ENV, None)

    def _handoff(self, scopes):
        limb = reddit_limb.RedditLimb()
        with mock.patch.object(reddit_limb, "fetch_identity", return_value="available"):
            result, status = reddit_limb.handle_handoff(
                headers=_Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"}),
                body_loader=lambda: {"access_token": "T", "scopes": scopes, "expires_in": 3600},
                limb=limb,
            )
        return limb, result, status

    def test_non_identity_scope_rejected(self):
        limb, result, status = self._handoff(["identity", "history", "read"])
        self.assertEqual(status, 400)
        self.assertEqual(result["error"], "non_identity_scope_rejected")
        self.assertEqual(limb.health()["state"], "needs_auth")   # session NOT set

    def test_any_non_identity_scope_rejected(self):
        _, _, status = self._handoff(["history"])
        self.assertEqual(status, 400)

    def test_identity_only_accepted(self):
        limb, _, status = self._handoff(["identity"])
        self.assertEqual(status, 200)
        self.assertEqual(limb.health()["scopes"], ["identity"])

    def test_empty_scopes_rejected(self):
        # fail closed: a blank scope label is NOT identity proof
        limb, _, status = self._handoff([])
        self.assertEqual(status, 400)
        self.assertEqual(limb.health()["state"], "needs_auth")

    def test_missing_scopes_field_rejected(self):
        limb = reddit_limb.RedditLimb()
        with mock.patch.object(reddit_limb, "fetch_identity", return_value="available"):
            _, status = reddit_limb.handle_handoff(
                headers=_Headers({reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"}),
                body_loader=lambda: {"access_token": "T"},   # no 'scopes' key
                limb=limb,
            )
        self.assertEqual(status, 400)
        self.assertEqual(limb.health()["state"], "needs_auth")


if __name__ == "__main__":
    unittest.main()
