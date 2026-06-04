# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""GitHub limb daemon handoff route — standalone Flask client (no daemon import)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from flask import Flask, jsonify, request  # noqa: E402

from core.information_limb import github_limb  # noqa: E402

SENTINEL = "ROUTE_GH_SENTINEL_TOKEN"


def _build_app(limb):
    app = Flask("test")

    @app.route("/internal/limb/github/session", methods=["POST"])
    def session():
        tile, status = github_limb.handle_handoff(
            headers=request.headers,
            body_loader=lambda: request.get_json(silent=True) or {},
            limb=limb,
        )
        return jsonify(tile), status

    return app


class GithubDaemonRouteTests(unittest.TestCase):
    def setUp(self):
        os.environ[github_limb.GITHUB_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, github_limb.GITHUB_HANDOFF_TOKEN_ENV, None)
        self.limb = github_limb.GithubLimb()
        self.client = _build_app(self.limb).test_client()

    def test_bad_secret_403_token_not_processed(self):
        r = self.client.post("/internal/limb/github/session",
                             headers={github_limb.GITHUB_HANDOFF_HEADER: "WRONG"},
                             json={"access_token": SENTINEL, "scopes": ["read:user"]})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.limb.health()["state"], "needs_auth")
        self.assertNotIn(SENTINEL, r.get_data(as_text=True))

    def test_valid_secret_sets_session(self):
        with mock.patch.object(github_limb, "fetch_identity", return_value="available"):
            r = self.client.post("/internal/limb/github/session",
                                 headers={github_limb.GITHUB_HANDOFF_HEADER: "GOODSECRET"},
                                 json={"access_token": SENTINEL, "scopes": ["read:user"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.limb.health()["state"], "available")
        self.assertNotIn(SENTINEL, r.get_data(as_text=True))

    def test_broader_scope_rejected(self):
        with mock.patch.object(github_limb, "fetch_identity", return_value="available"):
            r = self.client.post("/internal/limb/github/session",
                                 headers={github_limb.GITHUB_HANDOFF_HEADER: "GOODSECRET"},
                                 json={"access_token": SENTINEL, "scopes": ["read:user", "repo"]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.limb.health()["state"], "needs_auth")


if __name__ == "__main__":
    unittest.main()
