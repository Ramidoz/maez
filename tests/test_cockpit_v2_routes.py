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

    def test_v2_state_route_is_flagged_owner_private_and_serves_memory_room(self):
        wi, client = self._client()
        payload = {
            "kind": "cockpit_v2_state",
            "memory_room": {
                "kind": "cockpit_v2_memory_room",
                "a7_interiority": {"content_policy": "sealed"},
            },
        }

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "0"}, clear=False):
            off = client.get("/api/v2/cockpit/state")
        self.assertEqual(off.status_code, 404)
        off.close()

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False), \
            mock.patch.object(wi, "_owner_private_auth_ok", return_value=False):
            unauth = client.get("/api/v2/cockpit/state")
        self.assertEqual(unauth.status_code, 401)
        unauth.close()

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False), \
            mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
            mock.patch("core.cockpit.state.build_state", return_value=payload):
            ok = client.get("/api/v2/cockpit/state")

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["memory_room"]["a7_interiority"]["content_policy"], "sealed")
        ok.close()

    def test_v2_memory_room_route_uses_narrow_memory_payload(self):
        wi, client = self._client()
        payload = {
            "kind": "cockpit_v2_memory_room",
            "a7_interiority": {"content_policy": "sealed"},
        }

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False), \
            mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
            mock.patch("core.cockpit.memory_room.build_memory_room", return_value=payload) as build:
            ok = client.get("/api/v2/cockpit/memory-room")

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["kind"], "cockpit_v2_memory_room")
        self.assertEqual(ok.get_json()["a7_interiority"]["content_policy"], "sealed")
        build.assert_called_once_with()
        ok.close()

    def test_v2_receipts_room_route_uses_narrow_receipts_payload(self):
        wi, client = self._client()
        payload = {
            "kind": "cockpit_v2_receipts_room",
            "fabrication_events": {
                "label": "fabrication event receipts",
                "receipt_count": 0,
            },
        }

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "0"}, clear=False):
            off = client.get("/api/v2/cockpit/receipts-room")
        self.assertEqual(off.status_code, 404)
        off.close()

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False), \
            mock.patch.object(wi, "_owner_private_auth_ok", return_value=False):
            unauth = client.get("/api/v2/cockpit/receipts-room")
        self.assertEqual(unauth.status_code, 401)
        unauth.close()

        with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False), \
            mock.patch.object(wi, "_owner_private_auth_ok", return_value=True), \
            mock.patch("core.cockpit.receipts_room.build_receipts_room", return_value=payload) as build:
            ok = client.get("/api/v2/cockpit/receipts-room")

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["kind"], "cockpit_v2_receipts_room")
        self.assertEqual(ok.get_json()["fabrication_events"]["label"], "fabrication event receipts")
        build.assert_called_once_with()
        ok.close()


if __name__ == "__main__":
    unittest.main()
