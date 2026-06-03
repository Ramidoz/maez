import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from flask import Flask, request, jsonify  # noqa: E402
from core.information_limb import reddit_limb  # noqa: E402

SENTINEL = "ROUTE_SENTINEL_TOKEN"


def _build_app(limb):
    app = Flask("test")

    @app.route("/internal/limb/reddit/session", methods=["POST"])
    def session():
        tile, status = reddit_limb.handle_handoff(
            headers=request.headers,
            body_loader=lambda: request.get_json(silent=True) or {},
            limb=limb,
        )
        return jsonify(tile), status

    return app


class RedditDaemonRouteTests(unittest.TestCase):
    def setUp(self):
        os.environ[reddit_limb.REDDIT_HANDOFF_TOKEN_ENV] = "GOODSECRET"
        self.addCleanup(os.environ.pop, reddit_limb.REDDIT_HANDOFF_TOKEN_ENV, None)
        self.limb = reddit_limb.RedditLimb()
        self.client = _build_app(self.limb).test_client()

    def test_bad_secret_403_token_not_processed(self):
        r = self.client.post("/internal/limb/reddit/session",
                             headers={reddit_limb.REDDIT_HANDOFF_HEADER: "WRONG"},
                             json={"access_token": SENTINEL, "scopes": ["identity"]})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.limb.health()["state"], "needs_auth")  # session never set
        self.assertNotIn(SENTINEL, r.get_data(as_text=True))

    def test_valid_secret_sets_session(self):
        with mock.patch.object(reddit_limb, "fetch_identity", return_value="available"):
            r = self.client.post("/internal/limb/reddit/session",
                                 headers={reddit_limb.REDDIT_HANDOFF_HEADER: "GOODSECRET"},
                                 json={"access_token": SENTINEL, "scopes": ["identity"],
                                       "expires_in": 3600})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.limb.health()["state"], "available")
        self.assertNotIn(SENTINEL, r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
