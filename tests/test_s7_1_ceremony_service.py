"""S7.1 core WebAuthn ceremony service tests."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import sqlite3


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


class _InvalidRegistrationVerifier(_AvailableVerifier):
    def verify_registration_response(self, **_kwargs):
        return {"ok": False, "error": "s7_registration_invalid"}


class _ValidRegistrationVerifier(_AvailableVerifier):
    def verify_registration_response(self, **kwargs):
        if "challenge_b64" not in kwargs["challenge"]:
            return {"ok": False, "error": "s7_challenge_raw_missing"}
        return {
            "ok": True,
            "credential_ref": "cred-primary",
            "public_key": "public-key",
            "sign_count": 0,
            "attestation_format": "none",
            "aaguid": None,
            "authenticator_attachment": "cross-platform",
            "backup_eligible": False,
            "backed_up": False,
            "transports": ("usb",),
            "uv_capable": True,
        }


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

    def _store_with_bootstrap(self, tmp: str):
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        store = S7WebAuthnBootstrapStore(Path(tmp) / "s7_1_webauthn")
        intent = store.create_bootstrap_intent(
            purpose="register_primary",
            ttl_minutes=10,
            now=NOW,
            effective_uid=Path(tmp).stat().st_uid,
            is_interactive=True,
            tty_path="/dev/pts/test",
            token_bytes=b"t" * 32,
        )
        return store, intent

    def test_055_register_begin_creates_one_time_registration_challenge(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_AvailableVerifier(),
                store_factory=lambda: store,
            )

            result = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )

            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.body["challenge_kind"], "register_primary")
            self.assertEqual(result.body["rp_id"], "localhost")
            self.assertEqual(result.body["origin"], "http://localhost:11437")
            self.assertTrue(store.challenge_is_active(result.body["challenge_id"], now=NOW))

    def test_056_expired_registration_challenge_blocks_finish(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )

            result = service.register_finish(
                now="2026-05-18T11:11:00+00:00",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "expired"},
                },
            )

            self.assertEqual(result.status_code, 410)
            self.assertEqual(result.body["error"], "s7_challenge_replayed")
            self.assertFalse(store.has_enabled_primary())

    def test_057_register_finish_requires_same_session_binding_as_begin(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )

            result = service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-b",
                    "registration_response": {"clientDataJSON": "wrong-session"},
                },
            )

            self.assertEqual(result.status_code, 400)
            self.assertEqual(result.body["error"], "s7_challenge_replayed")
            self.assertFalse(store.has_enabled_primary())

    def test_058_invalid_registration_response_fails_closed_without_credential(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_InvalidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )

            result = service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "invalid"},
                },
            )

            self.assertEqual(result.status_code, 400)
            self.assertEqual(result.body["error"], "s7_registration_invalid")
            self.assertFalse(store.has_enabled_primary())

    def test_valid_primary_registration_consumes_challenge_and_bootstrap(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )

            result = service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "valid"},
                },
            )

            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.body["credential_ref"], "cred-primary")
            self.assertTrue(store.has_enabled_primary())
            self.assertFalse(store.challenge_is_active(begin.body["challenge_id"], now=NOW))
            self.assertEqual(store.bootstrap_state(now=NOW), "closed")
            record = store.get_credential("cred-primary")
            assert record is not None
            self.assertEqual(record.attestation_format, "none")
            self.assertEqual(record.authenticator_attachment, "cross-platform")
            self.assertEqual(record.transports, ("usb",))
            self.assertEqual(record.library_name, "webauthn")
            self.assertEqual(record.library_version, "2.7.1")
            self.assertIs(record.uv_capable, True)

    def test_register_finish_cannot_consume_challenge_twice(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )
            request = {
                "challenge_id": begin.body["challenge_id"],
                "bootstrap_intent_id": intent.intent_id,
                "bootstrap_token": intent.raw_token,
                "session_binding": "session-a",
                "registration_response": {"clientDataJSON": "valid"},
            }

            first = service.register_finish(now=NOW, request_json=request)
            second = service.register_finish(now=NOW, request_json=request)

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 410)
            self.assertEqual(second.body["error"], "s7_challenge_replayed")
            with closing(sqlite3.connect(store.db_path)) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM s7_founder_webauthn_credentials"
                ).fetchone()[0]
            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
