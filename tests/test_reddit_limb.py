# tests/test_reddit_limb.py
import sys
import unittest
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
