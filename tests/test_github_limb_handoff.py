# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""GitHub Limb handoff — auth-before-envelope, identity-only pin, loadable secret."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.information_limb import github_limb  # noqa: E402

SENTINEL = "SENTINEL_GITHUB_ACCESS_TOKEN"


class _Headers(dict):
    def get(self, k, default=None):
        return super().get(k, default)


class HandoffAuthTests(unittest.TestCase):
    def setUp(self):
        os.environ[github_limb.GITHUB_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, github_limb.GITHUB_HANDOFF_TOKEN_ENV, None)

    def test_missing_secret_untrusted(self):
        self.assertFalse(github_limb.handoff_trusted(_Headers()))

    def test_wrong_secret_untrusted(self):
        self.assertFalse(github_limb.handoff_trusted(
            _Headers({github_limb.GITHUB_HANDOFF_HEADER: "WRONG"})))

    def test_origin_untrusted_even_with_right_secret(self):
        self.assertFalse(github_limb.handoff_trusted(
            _Headers({github_limb.GITHUB_HANDOFF_HEADER: "GOODSECRET", "Origin": "http://evil"})))

    def test_right_secret_no_origin_trusted(self):
        self.assertTrue(github_limb.handoff_trusted(
            _Headers({github_limb.GITHUB_HANDOFF_HEADER: "GOODSECRET"})))

    def test_auth_before_envelope_body_loader_never_called_on_bad_secret(self):
        limb = github_limb.GithubLimb()
        body_loader = mock.Mock(return_value={"access_token": SENTINEL, "scopes": ["read:user"]})
        result, status = github_limb.handle_handoff(
            headers=_Headers({github_limb.GITHUB_HANDOFF_HEADER: "WRONG"}),
            body_loader=body_loader, limb=limb,
        )
        self.assertEqual(status, 403)
        body_loader.assert_not_called()
        self.assertNotIn(SENTINEL, repr(result))

    def test_valid_handoff_sets_session(self):
        limb = github_limb.GithubLimb()
        with mock.patch.object(github_limb, "fetch_identity", return_value="available"):
            result, status = github_limb.handle_handoff(
                headers=_Headers({github_limb.GITHUB_HANDOFF_HEADER: "GOODSECRET"}),
                body_loader=lambda: {"access_token": SENTINEL, "scopes": ["read:user"]},
                limb=limb,
            )
        self.assertEqual(status, 200)
        self.assertEqual(result["state"], "available")
        self.assertNotIn(SENTINEL, repr(result))


class HandoffSecretLoadableTests(unittest.TestCase):
    def test_github_handoff_token_is_classified_secret(self):
        from core.infra.secrets import is_secret_name
        self.assertTrue(is_secret_name(github_limb.GITHUB_HANDOFF_TOKEN_ENV))

    def test_github_handoff_token_is_allowlisted(self):
        from core.infra.secrets import SECRET_NAMES
        self.assertIn(github_limb.GITHUB_HANDOFF_TOKEN_ENV, SECRET_NAMES)


class IdentityOnlyPinTests(unittest.TestCase):
    def setUp(self):
        os.environ[github_limb.GITHUB_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, github_limb.GITHUB_HANDOFF_TOKEN_ENV, None)

    def _handoff(self, scopes):
        limb = github_limb.GithubLimb()
        with mock.patch.object(github_limb, "fetch_identity", return_value="available"):
            result, status = github_limb.handle_handoff(
                headers=_Headers({github_limb.GITHUB_HANDOFF_HEADER: "GOODSECRET"}),
                body_loader=lambda: {"access_token": "T", "scopes": scopes},
                limb=limb,
            )
        return limb, result, status

    def test_broader_scope_rejected(self):
        limb, result, status = self._handoff(["read:user", "repo"])
        self.assertEqual(status, 400)
        self.assertEqual(result["error"], "non_identity_scope_rejected")
        self.assertEqual(limb.health()["state"], "needs_auth")

    def test_any_non_identity_scope_rejected(self):
        _, _, status = self._handoff(["repo"])
        self.assertEqual(status, 400)

    def test_read_user_accepted(self):
        limb, _, status = self._handoff(["read:user"])
        self.assertEqual(status, 200)
        self.assertEqual(limb.health()["scopes"], ["read:user"])

    def test_empty_scopes_defaults_to_read_user(self):
        _, _, status = self._handoff([])
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
