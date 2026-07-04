import os
from pathlib import Path
from unittest import mock
import unittest


os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "web" / "cockpit"


class CockpitV2RouteGateTests(unittest.TestCase):
    def _client(self):
        import skills.web_interface as wi

        wi.app.config["TESTING"] = True
        return wi, wi.app.test_client()

    def test_flag_off_serves_current_cockpit_index_byte_for_byte(self):
        _wi, client = self._client()
        expected = (COCKPIT / "index.html").read_bytes()

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "0"}, clear=False):
            response = client.get("/cockpit")

        body = response.get_data()
        response.close()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body, expected)
        self.assertNotIn(b"cockpit-v2-operability-shell", body)

    def test_flag_on_serves_v2_shell_reusing_existing_track_a_design(self):
        _wi, client = self._client()

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False):
            response = client.get("/cockpit")

        body = response.get_data(as_text=True)
        response.close()
        self.assertEqual(response.status_code, 200)
        self.assertIn("cockpit-v2-operability-shell", body)
        self.assertIn("Maez Cockpit", body)
        self.assertIn("observation surface \u00b7 Track A", body)
        self.assertIn('/cockpit/v2/sim.jsx', body)
        self.assertIn('/cockpit/v2/terminal-ui.jsx', body)
        self.assertNotIn('src="/cockpit/sim.jsx"', body)

    def test_v2_assets_are_served_from_v2_subtree_as_javascript(self):
        _wi, client = self._client()

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False):
            response = client.get("/cockpit/v2/terminal-ui.jsx")

        body = response.get_data(as_text=True)
        response.close()
        self.assertEqual(response.status_code, 200)
        self.assertIn("window.TerminalUI", body)
        self.assertIn("application/javascript", response.headers.get("Content-Type", ""))

    def test_existing_s7_manual_proof_page_is_untouched_when_v2_flag_on(self):
        _wi, client = self._client()

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False):
            response = client.get("/cockpit/s7-webauthn-proof")

        body = response.get_data(as_text=True)
        response.close()
        self.assertEqual(response.status_code, 200)
        self.assertIn("S7.1 Manual Physical-Key Proof", body)
        self.assertIn("navigator.credentials.create", body)
        self.assertNotIn("cockpit-v2-operability-shell", body)


if __name__ == "__main__":
    unittest.main()
