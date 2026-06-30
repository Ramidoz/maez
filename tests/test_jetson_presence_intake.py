# tests/test_jetson_presence_intake.py
import os
import unittest
from unittest import mock

# Import the web module at top-level (real env) BEFORE any mock.patch.dict(clear=True).
# skills.web_interface runs load_secrets_for_process() at import, which purges secret-named
# env vars (including MAEZ_JETSON_DEVICE_TOKEN, matched by the "TOKEN" marker). If the very
# first import happened lazily inside a cleared-env block, that purge would strip the test's
# own token. Front-loading the import makes the purge run once against the real environment.
import skills.web_interface  # noqa: E402,F401


class DeviceAuthTests(unittest.TestCase):
    def _auth(self, headers: dict):
        import skills.web_interface as web
        fake_req = mock.Mock()
        fake_req.headers = headers
        with mock.patch.object(web, "request", fake_req):
            return web._jetson_device_auth_ok()

    def test_correct_token_ok(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_DEVICE_TOKEN": "secret-abc"}, clear=True):
            self.assertTrue(self._auth({"X-Maez-Jetson-Token": "secret-abc"}))

    def test_wrong_token_rejected(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_DEVICE_TOKEN": "secret-abc"}, clear=True):
            self.assertFalse(self._auth({"X-Maez-Jetson-Token": "nope"}))

    def test_missing_header_rejected(self):
        with mock.patch.dict(os.environ, {"MAEZ_JETSON_DEVICE_TOKEN": "secret-abc"}, clear=True):
            self.assertFalse(self._auth({}))

    def test_no_token_configured_fails_closed(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(self._auth({"X-Maez-Jetson-Token": "anything"}))


if __name__ == "__main__":
    unittest.main()
