# tests/test_jetson_presence_intake.py
import os
import subprocess
import sys
import unittest
from unittest import mock

# Import the web module at top-level (real env) BEFORE any mock.patch.dict(clear=True).
# skills.web_interface runs load_secrets_for_process() at import, which purges secret-named
# env vars (including MAEZ_JETSON_DEVICE_TOKEN, matched by the "TOKEN" marker). If the very
# first import happened lazily inside a cleared-env block, that purge would strip the test's
# own token. Front-loading the import makes the purge run once against the real environment.
import skills.web_interface  # noqa: E402,F401


class DeviceAuthTests(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as web

        self.web = web
        self.secret_patch = mock.patch.object(web, "get_secret", return_value=None)
        self.secret_patch.start()
        self.addCleanup(self.secret_patch.stop)

    def _auth(self, headers: dict):
        fake_req = mock.Mock()
        fake_req.headers = headers
        with mock.patch.object(self.web, "request", fake_req):
            return self.web._jetson_device_auth_ok()

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
        self.secret_patch = mock.patch.object(self.web, "get_secret", return_value=None)
        self.secret_patch.start()
        self.addCleanup(self.secret_patch.stop)
        self.client = web.app.test_client()

    def _valid_body(self):
        return {
            "owner_present": "present",
            "confidence": "high",
            "sensor_state": "available",
            "ts": "2026-06-29T19:00:00+00:00",
            "schema_version": "jetson_presence.v0",
        }

    def test_flag_off_404_mutates_nothing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(self.web, "_jetson_write_presence_receipt") as receipt:
                resp = self.client.post("/api/v1/presence/jetson/intake", json=self._valid_body())
                self.assertEqual(resp.status_code, 404)
                receipt.assert_not_called()
                self.assertEqual(
                    self.web._JETSON_PRESENCE_STORE.current(now=0.0), ("unknown", "unavailable")
                )

    def test_bad_token_401_mutates_nothing(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(self.web, "_jetson_write_presence_receipt") as receipt:
                resp = self.client.post(
                    "/api/v1/presence/jetson/intake",
                    json=self._valid_body(),
                    headers={"X-Maez-Jetson-Token": "wrong"},
                )
                self.assertEqual(resp.status_code, 401)
                receipt.assert_not_called()
                self.assertEqual(
                    self.web._JETSON_PRESENCE_STORE.current(now=0.0), ("unknown", "unavailable")
                )

    def test_valid_intake_stores_and_receipts(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(self.web, "_jetson_write_presence_receipt") as receipt:
                resp = self.client.post(
                    "/api/v1/presence/jetson/intake",
                    json=self._valid_body(),
                    headers={"X-Maez-Jetson-Token": "secret"},
                )
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.get_json()["ok"])
                receipt.assert_called_once()
                # stored state is fresh present
                owner, sensor = self.web._JETSON_PRESENCE_STORE.current(
                    now=resp.get_json()["received_at"] + 1
                )
                self.assertEqual(owner, "present")

    def test_malformed_body_is_400(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            resp = self.client.post(
                "/api/v1/presence/jetson/intake",
                json={"owner_present": "maybe"},
                headers={"X-Maez-Jetson-Token": "secret"},
            )
            self.assertEqual(resp.status_code, 400)

    def test_intake_does_not_touch_fresh_moment_receipts(self):
        """Covenant: presence intake must NEVER write to the private-thought surface."""
        import core.cognition.fresh_moment_receipts as fmr

        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(fmr, "FreshMomentReceipts") as fake_store:
                resp = self.client.post(
                    "/api/v1/presence/jetson/intake",
                    json=self._valid_body(),
                    headers={"X-Maez-Jetson-Token": "secret"},
                )
                self.assertEqual(resp.status_code, 200)
                fake_store.assert_not_called()  # the private-thought db is never instantiated


class FreshnessWitnessTests(unittest.TestCase):
    def setUp(self):
        import skills.web_interface as web

        self.web = web
        self.web._JETSON_PRESENCE_STORE = JetsonPresenceStore()  # isolate store per test
        self.secret_patch = mock.patch.object(self.web, "get_secret", return_value=None)
        self.secret_patch.start()
        self.addCleanup(self.secret_patch.stop)
        self.client = web.app.test_client()

    def test_silence_after_present_becomes_stale_not_absent(self):
        env = {"MAEZ_JETSON_PRESENCE_SHADOW": "1", "MAEZ_JETSON_DEVICE_TOKEN": "secret"}
        with mock.patch.dict(os.environ, env, clear=True):
            body = {
                "owner_present": "present",
                "confidence": "high",
                "sensor_state": "available",
                "ts": "2026-06-29T19:00:00+00:00",
                "schema_version": "jetson_presence.v0",
            }
            resp = self.client.post(
                "/api/v1/presence/jetson/intake",
                json=body,
                headers={"X-Maez-Jetson-Token": "secret"},
            )
            received_at = resp.get_json()["received_at"]
            # Fresh read: present
            self.assertEqual(
                self.web._JETSON_PRESENCE_STORE.current(now=received_at + 1)[0], "present"
            )
            # Silence past the window: stale/unknown, NEVER absent
            owner, sensor = self.web._JETSON_PRESENCE_STORE.current(now=received_at + 10_000)
            self.assertEqual((owner, sensor), ("unknown", "stale"))
            self.assertNotEqual(owner, "absent")


class RealSecretsImportRegressionTests(unittest.TestCase):
    """The mock-patched DeviceAuthTests front-load the import before clear=True, so they
    CANNOT catch the device token being purged at import. This drives the REAL import +
    secrets-load path in a fresh subprocess.

    The production loader (non-rollback) reads MAEZ_JETSON_DEVICE_TOKEN from the
    secrets.local.env file, but only if the name is in the optional set (it gates the
    `_parse_env_file` allowed-names filter); names absent from required|optional are
    dropped at parse and then purged from os.environ, so `get_secret` returns None and
    auth fails closed (401). With the name in optional, the token is loaded, survives the
    purge, and `get_secret` returns it -> auth passes (200).

    Hermetic: a temp config dir (MAEZ_CONFIG) holds a stand-in secrets.local.env so the
    import-time load runs against it; no real config/services are touched. This exercises
    the genuine import path (NOT a hand-rolled re-load), so it is sensitive to both the
    optional-set entry and get_secret.
    """

    def test_device_token_survives_real_secrets_import(self):
        import tempfile

        known_token = "jetson-device-token-xyz"
        td = tempfile.mkdtemp(prefix="jetson_secret_")
        with open(os.path.join(td, "secrets.local.env"), "w") as fh:
            fh.write("MAEZ_IPHONE_INGEST_TOKEN=dummy-required-token\n")
            fh.write("MAEZ_JETSON_DEVICE_TOKEN=%s\n" % known_token)
        # The subprocess does NOT re-load secrets — it relies entirely on web_interface's
        # import-time load reading MAEZ_CONFIG/secrets.local.env, then POSTs to the endpoint.
        code = (
            "import skills.web_interface as web\n"
            "from core.body.jetson_presence_store import JetsonPresenceStore\n"
            "web._JETSON_PRESENCE_STORE = JetsonPresenceStore()\n"
            "c = web.app.test_client()\n"
            "body = {'owner_present': 'present', 'confidence': 'high',\n"
            "        'sensor_state': 'available', 'ts': '2026-06-29T19:00:00+00:00',\n"
            "        'schema_version': 'jetson_presence.v0'}\n"
            "r = c.post('/api/v1/presence/jetson/intake', json=body,\n"
            "           headers={'X-Maez-Jetson-Token': %r})\n"
            "print(r.status_code)\n" % known_token
        )
        env = dict(os.environ)  # carry PATH/HOME/PYTHONPATH-style essentials
        env.update(
            {
                "MAEZ_CONFIG": td,  # hermetic stand-in for config/ (holds secrets.local.env)
                "MAEZ_JETSON_PRESENCE_SHADOW": "1",
            }
        )
        # Token must come via the file, not the env, to prove the real load path keeps it.
        env.pop("MAEZ_JETSON_DEVICE_TOKEN", None)
        env.pop("MAEZ_IPHONE_INGEST_TOKEN", None)
        proc = subprocess.run(
            [sys.executable, "-B", "-c", code],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "",
            "200",
            msg=f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
