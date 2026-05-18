"""S7.1 WebAuthn verifier adapter tests."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path
from unittest.mock import patch


class S71VerifierAdapterTests(unittest.TestCase):
    def test_018_missing_s7_webauthn_extra_returns_typed_dependency_error(self):
        from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier

        def missing_import(_name: str):
            raise ModuleNotFoundError("No module named 'webauthn'")

        verifier = S7ProductionWebAuthnVerifier(import_module=missing_import)

        self.assertEqual(
            verifier.dependency_state(),
            {
                "ok": False,
                "error": "s7_webauthn_dependency_missing",
                "library_name": "webauthn",
                "library_version": None,
            },
        )

    def test_052_production_verifier_does_not_import_s7_fake_verifier(self):
        source = Path("core/governance/s7_webauthn_verifier.py").read_text(encoding="utf-8")

        self.assertNotIn("FakeWebAuthnVerifier", source)
        self.assertNotIn("operator_user_boundary", source)

    def test_053_virtual_authenticator_harness_refuses_live_maez_store(self):
        from core.governance.s7_webauthn_verifier import S7VirtualAuthenticatorHarness

        with self.assertRaisesRegex(ValueError, "s7_virtual_authenticator_requires_isolated_store"):
            S7VirtualAuthenticatorHarness(store_root=Path("memory/s7_1_webauthn"))

    def test_053a_virtual_authenticator_harness_requires_explicit_test_origin(self):
        from core.governance.s7_webauthn_verifier import S7VirtualAuthenticatorHarness

        with self.assertRaisesRegex(ValueError, "s7_virtual_authenticator_requires_test_origin"):
            S7VirtualAuthenticatorHarness(store_root=Path("build/s7_1_virtual_authenticator"))

    def test_053b_virtual_authenticator_harness_rejects_production_origin_and_rp(self):
        from core.governance.s7_webauthn_verifier import S7VirtualAuthenticatorHarness

        with self.assertRaisesRegex(
            ValueError,
            "s7_virtual_authenticator_must_not_target_production_cockpit",
        ):
            S7VirtualAuthenticatorHarness(
                store_root=Path("build/s7_1_virtual_authenticator"),
                origin="http://localhost:11437",
                rp_id="localhost",
                remote_debugging_enabled=True,
            )

    def test_054_virtual_authenticator_harness_requires_test_automation_channel(self):
        from core.governance.s7_webauthn_verifier import S7VirtualAuthenticatorHarness

        with self.assertRaisesRegex(
            ValueError,
            "s7_virtual_authenticator_requires_test_automation_channel",
        ):
            S7VirtualAuthenticatorHarness(
                store_root=Path("build/s7_1_virtual_authenticator"),
                origin="http://127.0.0.1:11438",
                rp_id="127.0.0.1",
            )

    def test_054a_virtual_authenticator_harness_accepts_isolated_test_service(self):
        from core.governance.s7_webauthn_verifier import S7VirtualAuthenticatorHarness

        harness = S7VirtualAuthenticatorHarness(
            store_root=Path("build/s7_1_virtual_authenticator"),
            origin="http://127.0.0.1:11438",
            rp_id="127.0.0.1",
            remote_debugging_enabled=True,
        )

        self.assertEqual(harness.origin, "http://127.0.0.1:11438")
        self.assertEqual(harness.rp_id, "127.0.0.1")
        self.assertTrue(harness.remote_debugging_enabled)

    def test_054b_production_cockpit_sources_expose_no_remote_debugging_channel(self):
        production_sources = (
            Path("skills/web_interface.py"),
            Path("daemon/maez_daemon.py"),
        )

        for path in production_sources:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("--remote-debugging-port", source, path.as_posix())
            self.assertNotIn("remote_debugging_enabled=True", source, path.as_posix())
            self.assertNotIn("virtual-authenticator", source, path.as_posix())

    def test_adapter_reports_installed_webauthn_version_without_importing_fake(self):
        from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier

        class WebAuthnModule:
            pass

        def fake_import(name: str):
            if name != "webauthn":
                raise AssertionError(name)
            return WebAuthnModule()

        with patch.object(importlib.metadata, "version", return_value="2.7.1"):
            verifier = S7ProductionWebAuthnVerifier(import_module=fake_import)

        self.assertEqual(
            verifier.dependency_state(),
            {
                "ok": True,
                "library_name": "webauthn",
                "library_version": "2.7.1",
            },
        )

    def test_058_production_registration_verifier_fails_closed_on_invalid_response(self):
        from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier

        class WebAuthnModule:
            @staticmethod
            def verify_registration_response(**_kwargs):
                raise ValueError("bad webauthn response")

        verifier = S7ProductionWebAuthnVerifier(import_module=lambda _name: WebAuthnModule)

        result = verifier.verify_registration_response(
            registration_response={"clientDataJSON": "not-real"},
            challenge={"challenge_b64": "Y2hhbGxlbmdl"},
            expected_origin="http://localhost:11437",
            expected_rp_id="localhost",
            require_user_verification=True,
        )

        self.assertEqual(result["ok"], False)
        self.assertEqual(result["error"], "s7_registration_invalid")

    def test_060_062_registration_verifier_returns_attestation_and_uv_metadata(self):
        from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier

        class Value:
            def __init__(self, value: str):
                self.value = value

        class Verified:
            credential_id = b"credential-id"
            credential_public_key = b"public-key"
            sign_count = 7
            aaguid = "00000000-0000-0000-0000-000000000000"
            fmt = Value("none")
            credential_device_type = Value("single_device")
            credential_backed_up = False
            user_verified = True

        class WebAuthnModule:
            @staticmethod
            def verify_registration_response(**kwargs):
                self.assertEqual(kwargs["expected_challenge"], b"challenge")
                self.assertEqual(kwargs["expected_rp_id"], "localhost")
                self.assertEqual(kwargs["expected_origin"], "http://localhost:11437")
                self.assertIs(kwargs["require_user_verification"], True)
                return Verified()

        with patch.object(importlib.metadata, "version", return_value="2.7.1"):
            verifier = S7ProductionWebAuthnVerifier(import_module=lambda _name: WebAuthnModule)
            result = verifier.verify_registration_response(
                registration_response={"clientDataJSON": "valid"},
                challenge={"challenge_b64": "Y2hhbGxlbmdl"},
                expected_origin="http://localhost:11437",
                expected_rp_id="localhost",
                require_user_verification=True,
            )

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["credential_ref"], "Y3JlZGVudGlhbC1pZA")
        self.assertEqual(result["public_key"], "cHVibGljLWtleQ")
        self.assertEqual(result["attestation_format"], "none")
        self.assertEqual(result["aaguid"], "00000000-0000-0000-0000-000000000000")
        self.assertEqual(result["backup_eligible"], False)
        self.assertEqual(result["backed_up"], False)
        self.assertEqual(result["library_name"], "webauthn")
        self.assertEqual(result["library_version"], "2.7.1")
        self.assertEqual(result["uv_capable"], True)

    def test_072_production_authentication_verifier_fails_closed_on_invalid_assertion(self):
        from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier

        class WebAuthnModule:
            @staticmethod
            def verify_authentication_response(**_kwargs):
                raise ValueError("bad assertion")

        verifier = S7ProductionWebAuthnVerifier(import_module=lambda _name: WebAuthnModule)

        result = verifier.verify_authentication_response(
            authentication_response={"clientDataJSON": "not-real"},
            challenge={"challenge_b64": "Y2hhbGxlbmdl"},
            credential_public_key="cHVibGljLWtleQ",
            current_sign_count=7,
            expected_origin="http://localhost:11437",
            expected_rp_id="localhost",
            require_user_verification=True,
        )

        self.assertEqual(result["ok"], False)
        self.assertEqual(result["error"], "s7_authentication_invalid")

    def test_authentication_verifier_returns_uv_and_sign_count_metadata(self):
        from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier

        class Verified:
            credential_id = b"credential-id"
            new_sign_count = 8
            user_verified = True

        class WebAuthnModule:
            @staticmethod
            def verify_authentication_response(**kwargs):
                self.assertEqual(kwargs["expected_challenge"], b"challenge")
                self.assertEqual(kwargs["expected_rp_id"], "localhost")
                self.assertEqual(kwargs["expected_origin"], "http://localhost:11437")
                self.assertEqual(kwargs["credential_public_key"], b"public-key")
                self.assertEqual(kwargs["credential_current_sign_count"], 7)
                self.assertIs(kwargs["require_user_verification"], True)
                return Verified()

        with patch.object(importlib.metadata, "version", return_value="2.7.1"):
            verifier = S7ProductionWebAuthnVerifier(import_module=lambda _name: WebAuthnModule)
            result = verifier.verify_authentication_response(
                authentication_response={"clientDataJSON": "valid"},
                challenge={"challenge_b64": "Y2hhbGxlbmdl"},
                credential_public_key="cHVibGljLWtleQ",
                current_sign_count=7,
                expected_origin="http://localhost:11437",
                expected_rp_id="localhost",
                require_user_verification=True,
            )

        self.assertEqual(result["ok"], True)
        self.assertEqual(result["credential_ref"], "Y3JlZGVudGlhbC1pZA")
        self.assertEqual(result["sign_count"], 8)
        self.assertTrue(result["user_presence"])
        self.assertTrue(result["user_verification"])


if __name__ == "__main__":
    unittest.main()
