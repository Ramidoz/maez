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


if __name__ == "__main__":
    unittest.main()
