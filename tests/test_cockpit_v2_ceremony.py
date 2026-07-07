import os
import re
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "web" / "cockpit" / "v2"
WEB_INTERFACE = ROOT / "skills" / "web_interface.py"


class CockpitV2CeremonyTests(unittest.TestCase):
    def test_existing_s7_route_fails_when_live_ceremony_not_armed(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import skills.web_interface as wi

        wi.app.config["TESTING"] = True
        with mock.patch(
            "core.governance.operator_user_boundary.live_webauthn_ceremony_enabled",
            return_value=False,
        ):
            response = wi.app.test_client().post(
                "/api/v1/s7/webauthn/register/begin",
                json={
                    "registration_class": "primary",
                    "session_binding": "test-session",
                },
            )

        body = response.get_json()
        response.close()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(body["ok"], False)
        self.assertEqual(body["error"], "s7_ceremony_deferred")
        self.assertEqual(body["surface"], "cockpit")
        self.assertEqual(body["route"], "/api/v1/s7/webauthn/register/begin")

    def test_ceremony_surface_wraps_existing_s7_routes_only(self):
        ui = (V2 / "terminal-ui.jsx").read_text(encoding="utf-8")
        index = (V2 / "index.html").read_text(encoding="utf-8")
        combined = "\n".join((ui, index))

        self.assertIn("function CeremonySurface", ui)
        self.assertIn("S7 ceremony wrapper", ui)
        self.assertIn("navigator.credentials.get", ui)
        self.assertIn("navigator.credentials.create", ui)
        self.assertIn('"/api/v1/s7/webauthn/status"', ui)
        self.assertIn('"/api/v1/s7/webauthn/register/begin"', ui)
        self.assertIn('"/api/v1/s7/webauthn/register/finish"', ui)
        self.assertRegex(ui, r'`/api/v1/s7/cards/\$\{[^}]+}/webauthn/begin`')
        self.assertRegex(ui, r'`/api/v1/s7/cards/\$\{[^}]+}/webauthn/finish`')
        self.assertRegex(ui, r'`/api/v1/s7/cards/\$\{[^}]+}/execute`')
        self.assertIn("CeremonySurface", index)
        self.assertIn("id: 'ceremony'", index)
        self.assertIn("surface === 'ceremony'", index)

        self.assertIn("/api/v2/cockpit/s7/bootstrap-intent", combined)
        self.assertNotIn("/api/v2/cockpit/ceremony", combined)
        self.assertNotIn("/api/v2/cockpit/birth", combined)
        for forbidden in (
            "mintChallenge",
            "createChallenge",
            "verifyAssertion",
            "verifyWebAuthn",
            "S7_INTERNAL_CHANNEL_TOKEN",
            "X-Maez-S7-Internal-Channel",
        ):
            self.assertNotIn(forbidden, combined)

    def test_ceremony_failure_renders_failed_not_pending_success(self):
        ui = (V2 / "terminal-ui.jsx").read_text(encoding="utf-8")

        self.assertIn("function renderCeremonyStepDomText", ui)
        self.assertIn("status: 'failed'", ui)
        self.assertIn("touch-key failed", ui)
        self.assertNotIn("pending success", ui.lower())
        self.assertNotIn("pending-success", ui.lower())

    def test_birth_readiness_renders_blockers_without_birth_action(self):
        ui = (V2 / "terminal-ui.jsx").read_text(encoding="utf-8")
        index = (V2 / "index.html").read_text(encoding="utf-8")

        self.assertNotIn("BIRTH_READINESS_BLOCKERS", ui)
        self.assertNotIn("A7 undecided", ui)
        self.assertIn("birth_readiness", ui)
        self.assertNotIn("begin birth", ui.lower())
        self.assertIn("CeremonySurface", index)

    def test_no_new_route_writes_soul_dream_or_birth_directly(self):
        source = WEB_INTERFACE.read_text(encoding="utf-8")
        route_block = "\n".join(
            line
            for line in source.splitlines()
            if "/api/v2/cockpit" in line or "api_cockpit_v2" in line
        )

        self.assertNotIn("soul", route_block.lower())
        self.assertNotIn("dream", route_block.lower())
        self.assertNotIn("birth", route_block.lower())
        self.assertNotRegex(route_block, re.compile(r"write_(soul|dream|birth)", re.I))


if __name__ == "__main__":
    unittest.main()
