import unittest
from pathlib import Path


UI = Path("web/cockpit/v2/terminal-ui.jsx")


class CockpitV2S7EnrollFrontendTests(unittest.TestCase):
    def test_ceremony_primary_button_mints_bootstrap_intent_before_register_begin(self):
        ui = UI.read_text(encoding="utf-8")
        one_click = ui[
            ui.index("const registerPrimaryWithCockpitMint")
            : ui.index("const registerPrimaryWithManualBootstrap")
        ]

        self.assertIn('"/api/v2/cockpit/s7/bootstrap-intent"', ui)
        self.assertIn("registerPrimaryWithCockpitMint", ui)
        self.assertIn('"/api/v2/cockpit/s7/bootstrap-intent"', one_click)
        self.assertIn("await registerPrimaryWithBootstrap", one_click)
        self.assertLess(one_click.index('"/api/v2/cockpit/s7/bootstrap-intent"'), one_click.index("await registerPrimaryWithBootstrap"))
        self.assertIn("intent_id: minted.intent_id", one_click)
        self.assertIn("bootstrap_token: minted.bootstrap_token", one_click)
        self.assertIn("bootstrap_intent_id: intentId", ui)
        self.assertIn("bootstrap_token: token", ui)
        self.assertIn("Register founder key", ui)

    def test_manual_bootstrap_fields_remain_as_advanced_fallback(self):
        ui = UI.read_text(encoding="utf-8")

        self.assertIn("bootstrapIntentId", ui)
        self.assertIn("bootstrapToken", ui)
        self.assertIn("advanced manual fallback", ui)
        self.assertIn("registerPrimaryWithManualBootstrap", ui)

    def test_backup_button_authorizes_with_primary_before_register_begin(self):
        ui = UI.read_text(encoding="utf-8")
        backup_flow = ui[
            ui.index("const registerBackupWithPrimaryAuthorization")
            : ui.index("const executeCard")
        ]

        self.assertIn("Register backup key", ui)
        self.assertIn('"/api/v1/s7/webauthn/register/backup-card"', backup_flow)
        self.assertIn("await authorizeS7Request", backup_flow)
        self.assertIn('registration_class: "backup"', backup_flow)
        self.assertIn("s7_authorization_artifact_id: authorization.finish.artifact_id", backup_flow)
        self.assertIn("backup_authorization_request_id: card.request_id", backup_flow)
        self.assertLess(
            backup_flow.index("await authorizeS7Request"),
            backup_flow.index('"/api/v1/s7/webauthn/register/begin"'),
        )

    def test_webauthn_registration_payload_includes_reported_transports(self):
        ui = UI.read_text(encoding="utf-8")
        encoder = ui[
            ui.index("function ceremonyEncodeCredentialResponse")
            : ui.index("function ceremonyNormalizeCreationOptions")
        ]

        self.assertIn("getTransports", encoder)
        self.assertIn("body.transports", encoder)
        self.assertIn("Array.isArray", encoder)

    def test_backup_authorize_errors_surface_browser_error_details_and_labels(self):
        ui = UI.read_text(encoding="utf-8")
        backup_flow = ui[
            ui.index("const registerBackupWithPrimaryAuthorization")
            : ui.index("const executeCard")
        ]

        self.assertIn("describeCeremonyError", ui)
        self.assertIn("err?.name", ui)
        self.assertIn("err?.message", ui)
        self.assertIn("Touch your PRIMARY founder key (+PIN)", backup_flow)
        self.assertIn("Now register your backup (phone/Face ID)", backup_flow)


if __name__ == "__main__":
    unittest.main()
