from __future__ import annotations

import json
import unittest
from unittest import mock


def _urlopen_response(body: bytes, status: int = 200):
    class _Response:
        headers = {"Content-Type": "application/json"}

        def __init__(self):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return body

    return _Response()


class S7EnrollmentAssetBoundaryTest(unittest.TestCase):
    def setUp(self):
        from skills.web_interface import app

        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_browser_assets_never_expose_channel_token(self):
        token = "boundary-test-channel-secret"

        def fake_urlopen(req, timeout=None):
            body = json.dumps({"ok": True, "credential_count": 0}).encode("utf-8")
            return _urlopen_response(body)

        with mock.patch.dict("os.environ", {"S7_INTERNAL_CHANNEL_TOKEN": token}, clear=False), \
             mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            surfaces = [
                self.client.get("/cockpit/s7-webauthn-proof").get_data(as_text=True),
                self.client.get("/api/v1/s7/webauthn/status").get_data(as_text=True),
            ]

        for body in surfaces:
            self.assertNotIn(token, body)
            self.assertNotIn("S7_INTERNAL_CHANNEL_TOKEN", body)
            self.assertNotIn("X-Maez-S7-Internal-Channel", body)
            self.assertNotRegex(
                body,
                r"(localStorage|sessionStorage)\.[A-Za-z]*[Ii]tem\([^)]*[Cc]hannel",
            )

    def test_page_renders_owner_readiness_without_secret_names(self):
        text = self.client.get("/cockpit/s7-webauthn-proof").get_data(as_text=True)

        self.assertIn("Open this page from http://localhost:11437", text)
        self.assertIn("maez-web proxy has its local channel token", text)
        self.assertIn("Mint a fresh bootstrap intent", text)
        self.assertNotIn("S7_INTERNAL_CHANNEL_TOKEN", text)
        self.assertNotIn("X-Maez-S7-Internal-Channel", text)

    def test_page_maps_s7_error_codes_to_human_receipts(self):
        text = self.client.get("/cockpit/s7-webauthn-proof").get_data(as_text=True)

        expected_receipts = {
            "s7_internal_channel_untrusted": "maez-web proxy is missing its local channel token",
            "s7_ceremony_deferred": "The live WebAuthn ceremony flag is off",
            "s7_bootstrap_required": "Mint a fresh bootstrap intent",
            "s7_bootstrap_invalid": "The bootstrap intent or token is invalid or expired",
            "s7_challenge_replayed": "The browser challenge expired or was already used",
            "s7_webauthn_dependency_missing": "The WebAuthn verifier dependency is unavailable",
        }
        for error_code, receipt in expected_receipts.items():
            self.assertIn(error_code, text)
            self.assertIn(receipt, text)
