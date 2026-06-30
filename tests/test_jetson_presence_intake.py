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


from core.body.jetson_presence_store import JetsonPresenceStore


class IntakeEndpointTests(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as web
        self.web = web
        self.web._JETSON_PRESENCE_STORE = JetsonPresenceStore()  # isolate store per test
        self.client = web.app.test_client()

    def _valid_body(self):
        return {
            "owner_present": "present", "confidence": "high",
            "sensor_state": "available", "ts": "2026-06-29T19:00:00+00:00",
            "schema_version": "jetson_presence.v0",
        }

    def test_flag_off_404_mutates_nothing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(self.web, "_jetson_write_presence_receipt") as receipt:
                resp = self.client.post("/api/v1/presence/jetson/intake", json=self._valid_body())
                self.assertEqual(resp.status_code, 404)
                receipt.assert_not_called()
                self.assertEqual(self.web._JETSON_PRESENCE_STORE.current(now=0.0), ("unknown", "unavailable"))

    def test_bad_token_401_mutates_nothing(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(self.web, "_jetson_write_presence_receipt") as receipt:
                resp = self.client.post("/api/v1/presence/jetson/intake",
                                        json=self._valid_body(),
                                        headers={"X-Maez-Jetson-Token": "wrong"})
                self.assertEqual(resp.status_code, 401)
                receipt.assert_not_called()
                self.assertEqual(self.web._JETSON_PRESENCE_STORE.current(now=0.0), ("unknown", "unavailable"))

    def test_valid_intake_stores_and_receipts(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(self.web, "_jetson_write_presence_receipt") as receipt:
                resp = self.client.post("/api/v1/presence/jetson/intake",
                                        json=self._valid_body(),
                                        headers={"X-Maez-Jetson-Token": "secret"})
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.get_json()["ok"])
                receipt.assert_called_once()
                # stored state is fresh present
                owner, sensor = self.web._JETSON_PRESENCE_STORE.current(now=resp.get_json()["received_at"] + 1)
                self.assertEqual(owner, "present")

    def test_malformed_body_is_400(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            resp = self.client.post("/api/v1/presence/jetson/intake",
                                    json={"owner_present": "maybe"},
                                    headers={"X-Maez-Jetson-Token": "secret"})
            self.assertEqual(resp.status_code, 400)

    def test_intake_does_not_touch_fresh_moment_receipts(self):
        """Covenant: presence intake must NEVER write to the private-thought surface."""
        import core.cognition.fresh_moment_receipts as fmr
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(fmr, "FreshMomentReceipts") as fake_store:
                resp = self.client.post("/api/v1/presence/jetson/intake",
                                        json=self._valid_body(),
                                        headers={"X-Maez-Jetson-Token": "secret"})
                self.assertEqual(resp.status_code, 200)
                fake_store.assert_not_called()  # the private-thought db is never instantiated


class FreshnessWitnessTests(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as web
        self.web = web
        self.web._JETSON_PRESENCE_STORE = JetsonPresenceStore()  # isolate store per test
        self.client = web.app.test_client()

    def test_silence_after_present_becomes_stale_not_absent(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            body = {"owner_present": "present", "confidence": "high",
                    "sensor_state": "available", "ts": "2026-06-29T19:00:00+00:00",
                    "schema_version": "jetson_presence.v0"}
            resp = self.client.post("/api/v1/presence/jetson/intake", json=body,
                                    headers={"X-Maez-Jetson-Token": "secret"})
            received_at = resp.get_json()["received_at"]
            # Fresh read: present
            self.assertEqual(self.web._JETSON_PRESENCE_STORE.current(now=received_at + 1)[0], "present")
            # Silence past the window: stale/unknown, NEVER absent
            owner, sensor = self.web._JETSON_PRESENCE_STORE.current(now=received_at + 10_000)
            self.assertEqual((owner, sensor), ("unknown", "stale"))
            self.assertNotEqual(owner, "absent")


if __name__ == "__main__":
    unittest.main()
