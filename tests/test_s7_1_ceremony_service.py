"""S7.1 core WebAuthn ceremony service tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


NOW = "2026-05-18T11:00:00+00:00"


class _ExplodingFactory:
    def __call__(self):
        raise AssertionError("store factory touched before dependency check")


class _MissingDependencyVerifier:
    def dependency_state(self):
        return {
            "ok": False,
            "error": "s7_webauthn_dependency_missing",
            "library_name": "webauthn",
            "library_version": None,
        }


class _AvailableVerifier:
    def dependency_state(self):
        return {"ok": True, "library_name": "webauthn", "library_version": "2.7.1"}


class S71CeremonyServiceTests(unittest.TestCase):
    def test_018_missing_dependency_fails_before_store_work(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        service = S7LocalWebAuthnCeremonyService(
            verifier=_MissingDependencyVerifier(),
            store_factory=_ExplodingFactory(),
        )

        result = service.register_begin(now=NOW, request_json={})

        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.body["error"], "s7_webauthn_dependency_missing")

    def test_020_register_begin_requires_bootstrap_when_dependency_available(self):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            service = S7LocalWebAuthnCeremonyService(
                verifier=_AvailableVerifier(),
                store_factory=lambda: S7WebAuthnBootstrapStore(Path(tmp) / "s7_1_webauthn"),
            )

            result = service.register_begin(now=NOW, request_json={})

        self.assertEqual(result.status_code, 401)
        self.assertEqual(result.body["error"], "s7_bootstrap_required")


if __name__ == "__main__":
    unittest.main()
