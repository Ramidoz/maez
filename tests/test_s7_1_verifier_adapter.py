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


if __name__ == "__main__":
    unittest.main()
