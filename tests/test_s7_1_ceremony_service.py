"""S7.1 core WebAuthn ceremony service tests."""

from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import sqlite3
from tests.s7_store_fixture import fresh_store_at


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

    def verify_authentication_response(self, **_kwargs):
        return {
            "ok": True,
            "credential_ref": "cred-primary",
            "sign_count": 1,
            "user_presence": True,
            "user_verification": True,
        }


class _ValidBackupRegistrationVerifier(_ValidRegistrationVerifier):
    def verify_registration_response(self, **kwargs):
        result = dict(super().verify_registration_response(**kwargs))
        if result.get("ok") is True:
            result["credential_ref"] = "cred-backup"
            result["public_key"] = "public-key-backup"
        return result


class _ValidRegistrationVerifierWithAaguid(_ValidRegistrationVerifier):
    def verify_registration_response(self, **kwargs):
        result = dict(super().verify_registration_response(**kwargs))
        if result.get("ok") is True:
            result["aaguid"] = "00112233-4455-6677-8899-aabbccddeeff"
        return result


class _ValidBackupRegistrationVerifierWithSameAaguid(_ValidBackupRegistrationVerifier):
    def verify_registration_response(self, **kwargs):
        result = dict(super().verify_registration_response(**kwargs))
        if result.get("ok") is True:
            result["aaguid"] = "00112233-4455-6677-8899-aabbccddeeff"
        return result


class _ValidBackupRegistrationVerifierWithDifferentAaguid(_ValidBackupRegistrationVerifier):
    def verify_registration_response(self, **kwargs):
        result = dict(super().verify_registration_response(**kwargs))
        if result.get("ok") is True:
            result["aaguid"] = "ffeeddcc-bbaa-9988-7766-554433221100"
        return result


class _ValidBackupRegistrationVerifierWithDifferentAaguidOnly(_ValidBackupRegistrationVerifier):
    def verify_registration_response(self, **kwargs):
        result = dict(super().verify_registration_response(**kwargs))
        if result.get("ok") is True:
            result["aaguid"] = "ffeeddcc-bbaa-9988-7766-554433221100"
            result["authenticator_attachment"] = None
            result["transports"] = ()
        return result


class _ValidBackupRegistrationVerifierWithoutDistinctSignals(_ValidBackupRegistrationVerifier):
    def verify_registration_response(self, **kwargs):
        result = dict(super().verify_registration_response(**kwargs))
        if result.get("ok") is True:
            result["aaguid"] = None
            result["authenticator_attachment"] = None
            result["transports"] = ()
        return result


class _PresenceOnlyAuthenticationVerifier(_ValidRegistrationVerifier):
    def verify_authentication_response(self, **_kwargs):
        return {
            "ok": True,
            "credential_ref": "cred-primary",
            "sign_count": 1,
            "user_presence": True,
            "user_verification": False,
        }


class _ExplodingAuthenticationVerifier(_ValidRegistrationVerifier):
    def verify_authentication_response(self, **_kwargs):
        raise AssertionError("verifier touched before credential lookup")


class S71CeremonyServiceTests(unittest.TestCase):
    def _self_mod_envelope(self):
        from core.governance import operator_user_boundary as s7

        return s7.build_work_request_envelope(
            request_id="req-s7-1-voice",
            action="write_any_file",
            params={"path": "/home/rohit/maez/config/soul.md", "content": "x"},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="a" * 64,
            created_at=NOW,
            expires_at="2026-05-18T11:05:00+00:00",
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            free_text_ref_hash="b" * 64,
            maez_voice_consultation_id="voice-s7-1",
        )

    def _voice_consultation(self, *, state: str):
        from core.governance import operator_user_boundary as s7

        envelope = self._self_mod_envelope()
        return s7.MaezVoiceConsultation(
            consultation_id="voice-s7-1",
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            producer="s7_voice_consultation_turn",
            source_ref_kind="s7_voice_turn",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_state=state,
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )

    def _authority_context(self, *, credential_ref: str = "cred-primary"):
        from core.governance import operator_user_boundary as s7

        return s7.AuthorityContext(
            actor_id="founder",
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user",),
            grant_source="founder_webauthn",
            allowed_scopes=("operator_health",),
            auth_method="founder_webauthn",
            surface="cockpit",
            credential_ref="cred-primary",
            created_at=NOW,
            expires_at="2026-05-18T11:05:00+00:00",
            verified=True,
        )

    def _rendered_statement(self):
        from core.governance import operator_user_boundary as s7

        envelope = self._self_mod_envelope()
        authority = self._authority_context()
        return s7.render_request_statement(
            envelope=envelope,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=s7.canonical_hash({"path": "config/soul.md"}),
            authority_context=authority,
            maez_voice_consultation=self._voice_consultation(state="absent"),
            nonce="nonce-s7-1-auth",
            expires_at="2026-05-18T11:05:00+00:00",
            rendered_at=NOW,
        )

    def _voice_bundle_binding(
        self,
        rendered,
        consultation,
        rendered_prompt_hash: str,
        context_manifest_hash: str = "a" * 64,
    ):
        from core.governance.s7_guarded_execution import S7VoiceSourceBundleHashBinding

        return S7VoiceSourceBundleHashBinding(
            request_id=rendered.request_id,
            consultation_id=consultation.consultation_id,
            source_ref_hash=consultation.source_ref_hash,
            request_envelope_hash=rendered.request_envelope_hash,
            rendered_text_hash=rendered.rendered_text_hash,
            action_params_hash=rendered.action_params_hash,
            precondition_hash="a" * 64,
            authority_context_hash=rendered.authority_context_hash,
            maez_voice_consultation_hash=rendered.maez_voice_consultation_hash or "6" * 64,
            rendered_prompt_hash=rendered_prompt_hash,
            mutation_preview_hash="8" * 64,
            rollback_plan_ref="9" * 64,
            context_manifest_hash=context_manifest_hash,
            runtime_identity_hash="b" * 64,
            model_routing_identity_hash="d" * 64,
            model_config_hash="e" * 64,
        )

    def _backup_registration_authorization(self, db_path: Path):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_ceremony import (
            backup_registration_action_params,
            build_backup_registration_envelope,
        )

        authority = self._authority_context()
        envelope = build_backup_registration_envelope(
            request_id="s7.1.register_backup.test",
            created_at=NOW,
            expires_at="2026-05-18T11:05:00+00:00",
            maez_voice_consultation_id="voice-backup-register",
        )
        consultation = s7.MaezVoiceConsultation(
            consultation_id="voice-backup-register",
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            producer="s7_voice_consultation_turn",
            source_ref_kind="s7_voice_turn",
            source_ref_hash="d" * 64,
            maez_voice_consulted=True,
            maez_objection_state="absent",
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=NOW,
        )
        rendered = s7.render_request_statement(
            envelope=envelope,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=s7.canonical_hash(backup_registration_action_params()),
            authority_context=authority,
            maez_voice_consultation=consultation,
            nonce="nonce-backup-register",
            expires_at="2026-05-18T11:05:00+00:00",
            rendered_at=NOW,
        )
        artifact = s7.S7AuthorizationArtifact(
            artifact_id="artifact-backup-register",
            request_id=rendered.request_id,
            request_envelope_hash=rendered.request_envelope_hash,
            rendered_text_hash=rendered.rendered_text_hash,
            action=rendered.action,
            action_params_hash=rendered.action_params_hash,
            precondition_hash=envelope.precondition_hash,
            authority_context_hash=s7.authority_context_hash(authority),
            derived_work_class=rendered.derived_work_class,
            derived_aggregation_group=rendered.derived_aggregation_group,
            nonce=rendered.nonce,
            credential_ref="cred-primary",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=True,
            user_verification=True,
            created_at=NOW,
            expires_at="2026-05-18T11:05:00+00:00",
            consumed_at=None,
        )
        store = fresh_store_at(db_path)
        store.put(artifact)
        return s7.S7ExecutionAuthorization(
            store=store,
            artifact_id=artifact.artifact_id,
            rendered=rendered,
            action_params_hash=rendered.action_params_hash,
            authority_context=authority,
            precondition_hash=envelope.precondition_hash,
            derived_work_class=rendered.derived_work_class,
            derived_aggregation_group=rendered.derived_aggregation_group,
            now=NOW,
        )

    def _backup_registration_rendered_without_voice(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_ceremony import (
            backup_registration_action_params,
            build_backup_registration_envelope,
        )

        authority = self._authority_context()
        envelope = build_backup_registration_envelope(
            request_id="s7.1.register_backup.no_voice",
            created_at=NOW,
            expires_at="2026-05-18T11:05:00+00:00",
            maez_voice_consultation_id=None,
        )
        rendered = s7.render_request_statement(
            envelope=envelope,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=s7.canonical_hash(backup_registration_action_params()),
            authority_context=authority,
            maez_voice_consultation=None,
            nonce="nonce-backup-register-no-voice",
            expires_at="2026-05-18T11:05:00+00:00",
            rendered_at=NOW,
        )
        return envelope, rendered

    def _credential_record(
        self,
        credential_ref: str,
        *,
        kind: str,
        transports: tuple[str, ...] = ("usb",),
    ):
        from core.governance.s7_webauthn_bootstrap import FounderWebAuthnCredentialRecord

        return FounderWebAuthnCredentialRecord.build(
            credential_ref=credential_ref,
            actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
            role_names=("bonded_user",),
            public_key=f"public-key-{credential_ref}",
            sign_count=0,
            rp_id="localhost",
            origin="http://localhost:11437",
            created_at=NOW,
            backup_credential=(kind == "backup"),
            enabled=True,
            credential_kind=kind,
            label=f"{kind} key",
            registration_challenge_id=f"challenge-{credential_ref}",
            attestation_format="packed",
            aaguid="00112233-4455-6677-8899-aabbccddeeff",
            authenticator_attachment="cross-platform",
            backup_eligible=False,
            backed_up=False,
            transports=transports,
            library_name="webauthn",
            library_version="2.7.1",
            sign_count_mode="advancing",
            uv_capable=True,
            uv_required_for_guarded=True,
            distinct_device_confidence="confirmed_distinct",
        )

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

    def _authorization_artifact_count(self, db_path: Path) -> int:
        with closing(sqlite3.connect(db_path)) as conn:
            return conn.execute("SELECT COUNT(*) FROM s7_authorization_artifacts").fetchone()[0]

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

    def test_055a_register_begin_returns_browser_usable_public_key_options(self):
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

        options = result.body["public_key_options"]
        self.assertEqual(options["rp"], {"id": "localhost", "name": "Maez local founder ceremony"})
        self.assertEqual(options["user"]["name"], "founder")
        self.assertRegex(options["user"]["id"], r"^[A-Za-z0-9_-]+$")
        self.assertIn({"type": "public-key", "alg": -7}, options["pubKeyCredParams"])
        self.assertEqual(options["authenticatorSelection"]["residentKey"], "discouraged")
        self.assertEqual(options["authenticatorSelection"]["userVerification"], "required")
        self.assertNotIn("authenticatorAttachment", options["authenticatorSelection"])

    def test_056_expired_registration_challenge_blocks_finish(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifierWithAaguid(),
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
                verifier=_ValidRegistrationVerifierWithAaguid(),
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
                verifier=_ValidRegistrationVerifierWithAaguid(),
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

    def test_backup_registration_begin_requires_founder_authorization(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            primary_begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )
            primary_finish = service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": primary_begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "valid"},
                },
            )

            result = service.register_begin(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "session_binding": "session-b",
                },
            )

            self.assertEqual(primary_finish.status_code, 200)
            self.assertEqual(result.status_code, 403)
            self.assertEqual(result.body["error"], "s7_authorization_required")
            with closing(sqlite3.connect(store.db_path)) as conn:
                challenges = conn.execute(
                    "SELECT challenge_kind FROM s7_ceremony_challenges ORDER BY created_at"
                ).fetchall()
            self.assertEqual([row[0] for row in challenges], ["register_primary"])

    def test_backup_registration_begin_with_founder_authorization_creates_backup_challenge(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            primary_begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )
            service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": primary_begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "valid"},
                },
            )
            authorization = self._backup_registration_authorization(
                store.db_path,
            )

            result = service.register_begin(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "session_binding": "session-b",
                },
                s7_execution_authorization=authorization,
            )
            with closing(sqlite3.connect(store.db_path)) as conn:
                consumed_at = conn.execute(
                    "SELECT consumed_at FROM s7_authorization_artifacts WHERE artifact_id = ?",
                    (authorization.artifact_id,),
                ).fetchone()[0]

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body["challenge_kind"], "register_backup")
        self.assertEqual(tuple(result.body["exclude_credentials"]), ("cred-primary",))
        self.assertEqual(
            result.body["public_key_options"]["excludeCredentials"],
            [{"id": "cred-primary", "type": "public-key", "transports": ["usb"]}],
        )
        selection = result.body["public_key_options"]["authenticatorSelection"]
        self.assertEqual(selection["residentKey"], "preferred")
        self.assertEqual(selection["userVerification"], "required")
        self.assertNotIn("authenticatorAttachment", selection)
        self.assertIsNotNone(consumed_at)

    def test_backup_registration_begin_requires_authorization_before_transport_replay(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(
                self._credential_record(
                    "cred-primary",
                    kind="primary",
                    transports=("usb", "nfc"),
                )
            )
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )

            denied = service.register_begin(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "session_binding": "session-b",
                },
            )
            authorized = service.register_begin(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "session_binding": "session-b",
                },
                s7_execution_authorization=self._backup_registration_authorization(store.db_path),
            )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.body["error"], "s7_authorization_required")
        self.assertNotIn("public_key_options", denied.body)
        self.assertEqual(
            authorized.body["public_key_options"]["excludeCredentials"],
            [{"id": "cred-primary", "type": "public-key", "transports": ["usb", "nfc"]}],
        )

    def test_backup_registration_finish_stores_backup_credential(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifierWithAaguid(),
                store_factory=lambda: store,
            )
            primary_begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )
            service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": primary_begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "valid"},
                },
            )
            authorization = self._backup_registration_authorization(store.db_path)
            backup_service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidBackupRegistrationVerifierWithDifferentAaguid(),
                store_factory=lambda: store,
            )
            backup_begin = service.register_begin(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "session_binding": "session-b",
                },
                s7_execution_authorization=authorization,
            )

            result = backup_service.register_finish(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "challenge_id": backup_begin.body["challenge_id"],
                    "session_binding": "session-b",
                    "registration_response": {"clientDataJSON": "valid-backup"},
                },
            )
            backup = store.get_credential("cred-backup")
            state = store.credential_recovery_state()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body["registration_class"], "backup")
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertEqual(backup.credential_kind, "backup")
        self.assertTrue(backup.backup_credential)
        self.assertEqual(backup.distinct_device_confidence, "confirmed_distinct")
        self.assertEqual(state["backup_credential_state"], "enabled")

    def test_backup_registration_without_distinctness_signals_stays_unknown(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            primary_begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )
            service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": primary_begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "valid"},
                },
            )
            authorization = self._backup_registration_authorization(store.db_path)
            backup_service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidBackupRegistrationVerifierWithoutDistinctSignals(),
                store_factory=lambda: store,
            )
            backup_begin = service.register_begin(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "session_binding": "session-b",
                },
                s7_execution_authorization=authorization,
            )

            result = backup_service.register_finish(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "challenge_id": backup_begin.body["challenge_id"],
                    "session_binding": "session-b",
                    "registration_response": {"clientDataJSON": "valid-backup"},
                },
            )
            backup = store.get_credential("cred-backup")
            state = store.credential_recovery_state()

        self.assertEqual(result.status_code, 200)
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertEqual(backup.distinct_device_confidence, "unknown")
        self.assertEqual(state["mode"], "degraded")
        self.assertEqual(state["distinct_device_confidence"], "unknown")

    def test_backup_registration_with_distinct_aaguid_only_confirms_distinct(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifierWithAaguid(),
                store_factory=lambda: store,
            )
            primary_begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )
            service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": primary_begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "valid"},
                },
            )
            authorization = self._backup_registration_authorization(store.db_path)
            backup_service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidBackupRegistrationVerifierWithDifferentAaguidOnly(),
                store_factory=lambda: store,
            )
            backup_begin = service.register_begin(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "session_binding": "session-b",
                },
                s7_execution_authorization=authorization,
            )

            result = backup_service.register_finish(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "challenge_id": backup_begin.body["challenge_id"],
                    "session_binding": "session-b",
                    "registration_response": {"clientDataJSON": "valid-backup"},
                },
            )
            backup = store.get_credential("cred-backup")
            state = store.credential_recovery_state()

        self.assertEqual(result.status_code, 200)
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertEqual(backup.distinct_device_confidence, "confirmed_distinct")
        self.assertEqual(state["mode"], "ready")
        self.assertEqual(state["distinct_device_confidence"], "confirmed_distinct")

    def test_backup_registration_with_same_aaguid_stays_degraded(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifierWithAaguid(),
                store_factory=lambda: store,
            )
            primary_begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )
            service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": primary_begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "valid"},
                },
            )
            authorization = self._backup_registration_authorization(store.db_path)
            backup_service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidBackupRegistrationVerifierWithSameAaguid(),
                store_factory=lambda: store,
            )
            backup_begin = service.register_begin(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "session_binding": "session-b",
                },
                s7_execution_authorization=authorization,
            )

            result = backup_service.register_finish(
                now=NOW,
                request_json={
                    "registration_class": "backup",
                    "challenge_id": backup_begin.body["challenge_id"],
                    "session_binding": "session-b",
                    "registration_response": {"clientDataJSON": "valid-backup"},
                },
            )
            backup = store.get_credential("cred-backup")
            state = store.credential_recovery_state()

        self.assertEqual(result.status_code, 200)
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertEqual(backup.distinct_device_confidence, "same_device_override")
        self.assertEqual(state["mode"], "degraded")
        self.assertEqual(state["distinct_device_confidence"], "same_device_override")

    def test_authorization_voice_recheck_blocks_an_absent_consultation(self):
        """Renamed: this passes None, so it never reaches the state branch.

        It was called ...blocks_not_determined and asserted the response
        carries `not_determined` -- but that is the DEFAULT emitted when no
        consultation exists at all. The test exits through the
        missing-voice-fact path first, so it would pass whether or not the
        gate handles a real `not_determined` consultation correctly. The
        name promised a protection the body never exercised.

        What it does witness is real and worth keeping: a missing
        consultation blocks. That is now what it is called.
        """
        from core.governance.s7_webauthn_ceremony import authorization_voice_seat_recheck

        result = authorization_voice_seat_recheck(
            envelope=self._self_mod_envelope(),
            maez_voice_consultation=None,
        )

        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.body["error"], "s7_voice_seat_unresolved")
        self.assertEqual(result.body["maez_objection_state"], "not_determined")

    def test_authorization_voice_recheck_blocks_a_real_not_determined_consultation(self):
        """The protection the old name claimed, actually exercised.

        A PRESENT, request-bound consultation whose state is
        `not_determined` must block. This reaches the state branch rather
        than exiting on a missing voice fact, so it fails if the gate ever
        starts admitting `not_determined` on this generic path.

        That matters beyond bookkeeping: the generic decision pipeline
        emits `not_determined` when its semantic reader is UNCERTAIN, and
        this gate is what stops an uncertain reader authorising a soul
        write. Recorded in cutover design v30.
        """
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_ceremony import authorization_voice_seat_recheck

        envelope = self._self_mod_envelope()
        consultation = s7.MaezVoiceConsultation(
            consultation_id=envelope.maez_voice_consultation_id,
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_state="not_determined",
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=envelope.created_at,
        )

        result = authorization_voice_seat_recheck(
            envelope=envelope,
            maez_voice_consultation=consultation,
        )

        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.body["maez_objection_state"], "not_determined")

    def test_authorization_voice_recheck_positive_control_absent_passes(self):
        """POSITIVE CONTROL for the test above.

        The same fixture with `absent` must NOT be blocked, so the refusal
        above is caused by the STATE and not by a fixture that could never
        have succeeded.
        """
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_ceremony import authorization_voice_seat_recheck

        envelope = self._self_mod_envelope()
        consultation = s7.MaezVoiceConsultation(
            consultation_id=envelope.maez_voice_consultation_id,
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_state="absent",
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=envelope.created_at,
        )

        result = authorization_voice_seat_recheck(
            envelope=envelope,
            maez_voice_consultation=consultation,
        )

        self.assertNotEqual(result.body.get("error"), "s7_voice_seat_unresolved")

    def test_voice_recheck_denial_writes_refusal_history_for_d23(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
        from core.governance.s7_webauthn_ceremony import authorization_voice_seat_recheck

        with tempfile.TemporaryDirectory() as tmp:
            store = S7WebAuthnBootstrapStore(Path(tmp) / "s7_1_webauthn")
            prior = self._self_mod_envelope()
            current = replace(prior, request_id="req-s7-1-voice-reask")

            result = authorization_voice_seat_recheck(
                envelope=prior,
                maez_voice_consultation=None,
                refusal_history_store=store,
                rendered_text_hash="d" * 64,
                requester_ref="founder-local-browser",
                now=NOW,
            )
            history = store.refusal_history_for_envelope(current)
            assessment = s7.assess_aggregation_risk(
                current_envelope=current,
                history=history,
            )

        self.assertEqual(result.status_code, 409)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].outcome, "refused")
        self.assertIn("repeated_reask_after_refusal", assessment.signals)
        self.assertIn(assessment.decision, {"escalate", "block"})

    def test_refusal_history_for_envelope_filters_by_time_window_when_now_provided(self):
        from dataclasses import replace
        from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

        with tempfile.TemporaryDirectory() as tmp:
            store = S7WebAuthnBootstrapStore(Path(tmp) / "s7_1_webauthn")
            envelope = self._self_mod_envelope()
            aged = replace(envelope, request_id="req-s7-1-aged-auth")
            fresh = replace(envelope, request_id="req-s7-1-fresh-auth")
            now = "2026-05-18T11:00:00+00:00"

            store.record_authorization_history(
                envelope=aged,
                rendered_text_hash="c" * 64,
                requester_ref="founder-local-browser",
                created_at="2026-05-18T10:44:59+00:00",
            )
            store.record_authorization_history(
                envelope=fresh,
                rendered_text_hash="d" * 64,
                requester_ref="founder-local-browser",
                created_at="2026-05-18T10:45:01+00:00",
            )

            filtered = store.refusal_history_for_envelope(envelope, now=now)
            full = store.refusal_history_for_envelope(envelope)

        self.assertEqual([record.request_id for record in filtered], ["req-s7-1-fresh-auth"])
        self.assertEqual(
            [record.request_id for record in full],
            ["req-s7-1-aged-auth", "req-s7-1-fresh-auth"],
        )

    def test_authorization_voice_recheck_blocks_maez_objection(self):
        from core.governance.s7_webauthn_ceremony import authorization_voice_seat_recheck

        result = authorization_voice_seat_recheck(
            envelope=self._self_mod_envelope(),
            maez_voice_consultation=self._voice_consultation(state="present"),
        )

        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.body["error"], "s7_voice_seat_unresolved")
        self.assertEqual(result.body["maez_objection_state"], "present")

    def test_authorization_voice_recheck_allows_producer_confirmed_absent(self):
        from core.governance.s7_webauthn_ceremony import authorization_voice_seat_recheck

        result = authorization_voice_seat_recheck(
            envelope=self._self_mod_envelope(),
            maez_voice_consultation=self._voice_consultation(state="absent"),
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body["maez_objection_state"], "absent")

    def test_d23_aggregation_recheck_blocks_guarded_reask(self):
        from dataclasses import replace
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_ceremony import authorization_aggregation_recheck

        prior = self._self_mod_envelope()
        current = replace(prior, request_id="req-s7-1-d23-reask")
        history = (
            s7.build_request_history_record(
                envelope=prior,
                outcome="refused",
                created_at=NOW,
            ),
        )

        result = authorization_aggregation_recheck(
            envelope=current,
            history=history,
        )

        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.body["error"], "s7_aggregation_block")
        self.assertIn("repeated_reask_after_refusal", result.body["signals"])

    def test_authorize_begin_requires_ready_primary_and_backup_state(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, intent = self._store_with_bootstrap(tmp)
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            primary_begin = service.register_begin(
                now=NOW,
                request_json={
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                },
            )
            service.register_finish(
                now=NOW,
                request_json={
                    "challenge_id": primary_begin.body["challenge_id"],
                    "bootstrap_intent_id": intent.intent_id,
                    "bootstrap_token": intent.raw_token,
                    "session_binding": "session-a",
                    "registration_response": {"clientDataJSON": "valid"},
                },
            )

            result = service.authorize_begin(
                now=NOW,
                rendered_statement=self._rendered_statement(),
                precondition_hash="a" * 64,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )

            self.assertEqual(result.status_code, 409)
            self.assertEqual(result.body["error"], "s7_credential_setup_incomplete")
            self.assertEqual(result.body["ceremony_mode"], "degraded")

    def test_authorize_begin_allows_backup_registration_with_primary_only(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(
                self._credential_record(
                    "cred-primary",
                    kind="primary",
                    transports=("usb", "nfc"),
                )
            )
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            rendered = self._rendered_statement()

            result = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash="a" * 64,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                allow_degraded_primary_only=True,
            )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body["challenge_kind"], "authorize_guarded_request")
        self.assertEqual(tuple(result.body["allow_credentials"]), ("cred-primary",))
        self.assertEqual(
            result.body["public_key_options"]["allowCredentials"],
            [{"id": "cred-primary", "type": "public-key", "transports": ["usb", "nfc"]}],
        )

    def test_authorize_begin_defaults_empty_founder_transports_for_allow_credentials(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(
                self._credential_record("cred-primary", kind="primary", transports=())
            )
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )

            result = service.authorize_begin(
                now=NOW,
                rendered_statement=self._rendered_statement(),
                precondition_hash="a" * 64,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                allow_degraded_primary_only=True,
            )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            result.body["public_key_options"]["allowCredentials"],
            [{"id": "cred-primary", "type": "public-key", "transports": ["usb", "nfc"]}],
        )

    def test_authorize_begin_allows_recovery_proof_with_backup_only(self):
        from dataclasses import replace

        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(
                replace(self._credential_record("cred-primary", kind="primary"), enabled=False)
            )
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            rendered = self._rendered_statement()

            result = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash="a" * 64,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                allow_degraded_backup_only=True,
            )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body["challenge_kind"], "authorize_guarded_request")
        self.assertEqual(tuple(result.body["allow_credentials"]), ("cred-backup",))

    def test_authorize_begin_creates_d12_bound_authorization_challenge_when_ready(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            rendered = self._rendered_statement()

            result = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash="a" * 64,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )
            challenge = store.authorization_challenge_for_finish(
                challenge_id=result.body["challenge_id"],
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                now=NOW,
            )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body["challenge_kind"], "authorize_guarded_request")
        self.assertEqual(result.body["request_id"], rendered.request_id)
        self.assertTrue(result.body["uv_required"])
        self.assertEqual(tuple(result.body["allow_credentials"]), ("cred-backup", "cred-primary"))
        assert challenge is not None
        self.assertEqual(challenge["rendered_text_hash"], rendered.rendered_text_hash)
        self.assertEqual(challenge["request_envelope_hash"], rendered.request_envelope_hash)

    def test_authorize_finish_for_voice_seat_fails_closed_without_guarded_state_store(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            envelope = self._self_mod_envelope()
            rendered = self._rendered_statement()
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )

            finish = service.authorize_finish(
                now=NOW,
                envelope=envelope,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                maez_voice_consultation=self._voice_consultation(state="absent"),
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-primary",
                    "authentication_response": {"clientDataJSON": "valid-auth"},
                },
            )
            artifact_count = self._authorization_artifact_count(store.db_path)
            history = store.refusal_history_for_envelope(envelope)

        self.assertEqual(finish.status_code, 409)
        self.assertEqual(finish.body["error"], "s7_guarded_state_store_required")
        self.assertEqual(artifact_count, 0)
        self.assertEqual(len(history), 0)

    def test_authorize_finish_carries_cutover_result_to_the_voice_gate(self):
        from unittest.mock import patch

        from core.governance.s7_webauthn_ceremony import (
            S7CeremonyServiceResult,
            S7LocalWebAuthnCeremonyService,
        )

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            envelope = self._self_mod_envelope()
            rendered = self._rendered_statement()
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )
            carried_result = object()
            gate_stop = S7CeremonyServiceResult(
                body={"ok": False, "error": "fixture_gate_stop"},
                status_code=409,
            )
            with patch(
                "core.governance.s7_webauthn_ceremony.authorization_voice_seat_recheck",
                return_value=gate_stop,
            ) as gate:
                finish = service.authorize_finish(
                    now=NOW,
                    envelope=envelope,
                    rendered_statement=rendered,
                    precondition_hash=envelope.precondition_hash,
                    maez_voice_consultation=self._voice_consultation(state="not_determined"),
                    session_binding="session-auth",
                    internal_channel_binding="daemon-channel",
                    request_json={
                        "challenge_id": begin.body["challenge_id"],
                        "credential_ref": "cred-primary",
                        "authentication_response": {"clientDataJSON": "valid-auth"},
                    },
                    source_ref_hash="c" * 64,
                    cutover_consultation_result=carried_result,
                )

        self.assertEqual(finish, gate_stop)
        self.assertIs(
            gate.call_args.kwargs["cutover_consultation_result"],
            carried_result,
        )
        self.assertEqual(gate.call_args.kwargs["source_ref_hash"], "c" * 64)

    def test_authorize_finish_for_voice_seat_mints_with_validated_bundle_reservation(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7SemanticReaderAttemptEvidence,
            S7SemanticReaderAttemptStore,
            S7VoiceBundleUse,
            S7VoiceBundleUseStore,
            S7VoiceConsultationBundle,
            S7VoiceConsultationBundleStore,
            validate_s7_voice_source_bundle,
        )
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            auth_store = fresh_store_at(store.db_path)
            bundle_store = S7VoiceConsultationBundleStore(store.db_path)
            bundle_use_store = S7VoiceBundleUseStore(store.db_path)
            attempt_store = S7SemanticReaderAttemptStore(store.db_path)
            guarded_store = S7GuardedStateStore(
                authorization_store=auth_store,
                voice_bundle_use_store=bundle_use_store,
            )
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            envelope = self._self_mod_envelope()
            consultation = self._voice_consultation(state="absent")
            rendered = self._rendered_statement()
            attempt = S7SemanticReaderAttemptEvidence.reviewed_v1()
            attempt_store.put(attempt)
            raw_text = "Maez says there is no objection."
            rendered_prompt_text = "S7 voice consultation prompt for ceremony authorization."
            manifest = bundle_store.put_reviewed_context_manifest(
                manifest_id="context-manifest-ceremony",
                preview_ref="preview-ceremony",
                request_envelope_hash=rendered.request_envelope_hash,
                precondition_hash=envelope.precondition_hash,
                created_at=NOW,
            )
            binding = self._voice_bundle_binding(
                rendered,
                consultation,
                s7.canonical_hash(rendered_prompt_text),
                manifest.context_manifest_hash,
            )
            bundle_store.put_raw_response("raw-response-ceremony", raw_text)
            bundle_store.put_rendered_prompt(
                "rendered-prompt-ceremony",
                rendered_prompt_text,
            )
            bundle_store.put_bundle(
                S7VoiceConsultationBundle(
                    source_ref_hash=consultation.source_ref_hash,
                    request_id=envelope.request_id,
                    consultation_id=consultation.consultation_id,
                    request_envelope_hash=binding.request_envelope_hash,
                    rendered_text_hash=binding.rendered_text_hash,
                    action_params_hash=binding.action_params_hash,
                    precondition_hash=binding.precondition_hash,
                    authority_context_hash=binding.authority_context_hash,
                    maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
                    rendered_prompt_ref="rendered-prompt-ceremony",
                    rendered_prompt_hash=binding.rendered_prompt_hash,
                    mutation_preview_hash=binding.mutation_preview_hash,
                    rollback_plan_ref=binding.rollback_plan_ref,
                    context_manifest_ref=manifest.manifest_id,
                    context_manifest_hash=binding.context_manifest_hash,
                    runtime_identity_hash=binding.runtime_identity_hash,
                    model_routing_identity_hash=binding.model_routing_identity_hash,
                    model_config_hash=binding.model_config_hash,
                    raw_response_ref="raw-response-ceremony",
                    raw_response_hash=s7.canonical_hash(raw_text),
                    semantic_reader_attempt_hash=attempt.semantic_reader_attempt_hash,
                    expires_at="2026-05-18T11:05:00+00:00",
                )
            )
            bundle_use_store.put_unreserved(
                S7VoiceBundleUse.new_unreserved(
                    request_id=envelope.request_id,
                    source_ref_hash=consultation.source_ref_hash,
                    consultation_id=consultation.consultation_id,
                    used_at=NOW,
                )
            )
            validation = validate_s7_voice_source_bundle(
                consultation=consultation,
                bundle_store=bundle_store,
                bundle_use_store=bundle_use_store,
                semantic_reader_attempt_store=attempt_store,
                expected_binding=binding,
                now=NOW,
            )
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )

            finish = service.authorize_finish(
                now=NOW,
                envelope=envelope,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                maez_voice_consultation=consultation,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-primary",
                    "authentication_response": {"clientDataJSON": "valid-auth"},
                },
                guarded_store=guarded_store,
                source_bundle_validation=validation,
                source_ref_hash=consultation.source_ref_hash,
                reservation_token="runtime-token-not-persisted",
            )
            artifact_count = self._authorization_artifact_count(store.db_path)
            reserved = bundle_use_store.get_for_source_ref(consultation.source_ref_hash)
            history = store.refusal_history_for_envelope(envelope)

        self.assertEqual(finish.status_code, 200)
        self.assertEqual(finish.body["grant_source"], "founder_webauthn")
        self.assertEqual(artifact_count, 1)
        self.assertIsNotNone(reserved)
        assert reserved is not None
        self.assertEqual(reserved.reservation_state, "reserved")
        self.assertEqual(reserved.artifact_id, finish.body["artifact_id"])
        self.assertEqual(
            reserved.reservation_token_hash,
            s7.canonical_hash("runtime-token-not-persisted"),
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].outcome, "authorized")

    def test_authorize_finish_for_validated_maez_objection_records_d23_refusal(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7SemanticReaderAttemptEvidence,
            S7SemanticReaderAttemptStore,
            S7VoiceBundleUse,
            S7VoiceBundleUseStore,
            S7VoiceConsultationBundle,
            S7VoiceConsultationBundleStore,
            validate_s7_voice_source_bundle,
        )
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            auth_store = fresh_store_at(store.db_path)
            bundle_store = S7VoiceConsultationBundleStore(store.db_path)
            bundle_use_store = S7VoiceBundleUseStore(store.db_path)
            attempt_store = S7SemanticReaderAttemptStore(store.db_path)
            guarded_store = S7GuardedStateStore(
                authorization_store=auth_store,
                voice_bundle_use_store=bundle_use_store,
            )
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            envelope = self._self_mod_envelope()
            consultation = self._voice_consultation(state="present")
            authority = self._authority_context()
            rendered = s7.render_request_statement(
                envelope=envelope,
                surface="cockpit",
                origin="http://localhost:11437",
                action_params_hash=s7.canonical_hash({"path": "config/soul.md"}),
                authority_context=authority,
                maez_voice_consultation=consultation,
                nonce="nonce-s7-1-auth",
                expires_at="2026-05-18T11:05:00+00:00",
                rendered_at=NOW,
            )
            base_attempt = S7SemanticReaderAttemptEvidence.reviewed_v1()
            attempt = type(base_attempt)(
                semantic_reader_route_id=base_attempt.semantic_reader_route_id,
                semantic_reader_provider=base_attempt.semantic_reader_provider,
                semantic_reader_provider_model=base_attempt.semantic_reader_provider_model,
                semantic_reader_model_snapshot=base_attempt.semantic_reader_model_snapshot,
                semantic_reader_decoding_params_hash=(
                    base_attempt.semantic_reader_decoding_params_hash
                ),
                semantic_reader_prompt_hash=base_attempt.semantic_reader_prompt_hash,
                semantic_reader_route_config_hash=base_attempt.semantic_reader_route_config_hash,
                raw_semantic_reader_outcome="blocking_signal_present",
                grounding_response_span_quote="do not make this change",
                grounding_response_span_offset=15,
            )
            attempt_store.put(attempt)
            raw_text = "Maez says: no, do not make this change."
            rendered_prompt_text = "S7 voice consultation prompt for refusal projection."
            manifest = bundle_store.put_reviewed_context_manifest(
                manifest_id="context-manifest-refusal",
                preview_ref="preview-refusal",
                request_envelope_hash=rendered.request_envelope_hash,
                precondition_hash=envelope.precondition_hash,
                created_at=NOW,
            )
            binding = self._voice_bundle_binding(
                rendered,
                consultation,
                s7.canonical_hash(rendered_prompt_text),
                manifest.context_manifest_hash,
            )
            bundle_store.put_raw_response("raw-response-refusal", raw_text)
            bundle_store.put_rendered_prompt(
                "rendered-prompt-refusal",
                rendered_prompt_text,
            )
            bundle_store.put_bundle(
                S7VoiceConsultationBundle(
                    source_ref_hash=consultation.source_ref_hash,
                    request_id=envelope.request_id,
                    consultation_id=consultation.consultation_id,
                    request_envelope_hash=binding.request_envelope_hash,
                    rendered_text_hash=binding.rendered_text_hash,
                    action_params_hash=binding.action_params_hash,
                    precondition_hash=binding.precondition_hash,
                    authority_context_hash=binding.authority_context_hash,
                    maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
                    rendered_prompt_ref="rendered-prompt-refusal",
                    rendered_prompt_hash=binding.rendered_prompt_hash,
                    mutation_preview_hash=binding.mutation_preview_hash,
                    rollback_plan_ref=binding.rollback_plan_ref,
                    context_manifest_ref=manifest.manifest_id,
                    context_manifest_hash=binding.context_manifest_hash,
                    runtime_identity_hash=binding.runtime_identity_hash,
                    model_routing_identity_hash=binding.model_routing_identity_hash,
                    model_config_hash=binding.model_config_hash,
                    raw_response_ref="raw-response-refusal",
                    raw_response_hash=s7.canonical_hash(raw_text),
                    semantic_reader_attempt_hash=attempt.semantic_reader_attempt_hash,
                    expires_at="2026-05-18T11:05:00+00:00",
                    authority_class="authoritative",
                    has_grounded_semantic_blocking_signal=True,
                )
            )
            bundle_use_store.put_unreserved(
                S7VoiceBundleUse.new_unreserved(
                    request_id=envelope.request_id,
                    source_ref_hash=consultation.source_ref_hash,
                    consultation_id=consultation.consultation_id,
                    used_at=NOW,
                )
            )
            validation = validate_s7_voice_source_bundle(
                consultation=consultation,
                bundle_store=bundle_store,
                bundle_use_store=bundle_use_store,
                semantic_reader_attempt_store=attempt_store,
                expected_binding=binding,
                now=NOW,
            )
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )

            finish = service.authorize_finish(
                now=NOW,
                envelope=envelope,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                maez_voice_consultation=consultation,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-primary",
                    "authentication_response": {"clientDataJSON": "valid-auth"},
                },
                guarded_store=guarded_store,
                source_bundle_validation=validation,
                source_ref_hash=consultation.source_ref_hash,
                reservation_token="runtime-token-not-persisted",
            )
            artifact_count = self._authorization_artifact_count(store.db_path)
            history = store.refusal_history_for_envelope(envelope)
            assessment = s7.assess_aggregation_risk(
                current_envelope=envelope,
                history=history,
            )

        self.assertEqual(validation.status, "blocking_present")
        self.assertTrue(validation.source_bundle_valid)
        self.assertFalse(validation.mint_eligible)
        self.assertEqual(validation.authority_projection, "grounded_refusal")
        self.assertEqual(finish.status_code, 409)
        self.assertEqual(finish.body["error"], "s7_voice_seat_unresolved")
        self.assertEqual(finish.body["reason"], "maez_voice_not_clear")
        self.assertEqual(artifact_count, 0)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].outcome, "refused")
        self.assertIn("repeated_reask_after_refusal", assessment.signals)

    def test_authorize_finish_rejects_tampered_maez_objection_without_d23_refusal(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_guarded_execution import (
            S7GuardedStateStore,
            S7SemanticReaderAttemptEvidence,
            S7SemanticReaderAttemptStore,
            S7VoiceBundleUse,
            S7VoiceBundleUseStore,
            S7VoiceConsultationBundle,
            S7VoiceConsultationBundleStore,
            validate_s7_voice_source_bundle,
        )
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            auth_store = fresh_store_at(store.db_path)
            bundle_store = S7VoiceConsultationBundleStore(store.db_path)
            bundle_use_store = S7VoiceBundleUseStore(store.db_path)
            attempt_store = S7SemanticReaderAttemptStore(store.db_path)
            guarded_store = S7GuardedStateStore(
                authorization_store=auth_store,
                voice_bundle_use_store=bundle_use_store,
            )
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            envelope = self._self_mod_envelope()
            consultation = self._voice_consultation(state="present")
            authority = self._authority_context()
            rendered = s7.render_request_statement(
                envelope=envelope,
                surface="cockpit",
                origin="http://localhost:11437",
                action_params_hash=s7.canonical_hash({"path": "config/soul.md"}),
                authority_context=authority,
                maez_voice_consultation=consultation,
                nonce="nonce-s7-1-auth",
                expires_at="2026-05-18T11:05:00+00:00",
                rendered_at=NOW,
            )
            attempt = S7SemanticReaderAttemptEvidence.reviewed_v1()
            attempt_store.put(attempt)
            rendered_prompt_text = "S7 voice consultation prompt for tampered refusal."
            manifest = bundle_store.put_reviewed_context_manifest(
                manifest_id="context-manifest-refusal-tampered",
                preview_ref="preview-refusal-tampered",
                request_envelope_hash=rendered.request_envelope_hash,
                precondition_hash=envelope.precondition_hash,
                created_at=NOW,
            )
            binding = self._voice_bundle_binding(
                rendered,
                consultation,
                s7.canonical_hash(rendered_prompt_text),
                manifest.context_manifest_hash,
            )
            bundle_store.put_raw_response("raw-response-refusal-tampered", "tampered text")
            bundle_store.put_rendered_prompt(
                "rendered-prompt-refusal-tampered",
                rendered_prompt_text,
            )
            bundle_store.put_bundle(
                S7VoiceConsultationBundle(
                    source_ref_hash=consultation.source_ref_hash,
                    request_id=envelope.request_id,
                    consultation_id=consultation.consultation_id,
                    request_envelope_hash=binding.request_envelope_hash,
                    rendered_text_hash=binding.rendered_text_hash,
                    action_params_hash=binding.action_params_hash,
                    precondition_hash=binding.precondition_hash,
                    authority_context_hash=binding.authority_context_hash,
                    maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
                    rendered_prompt_ref="rendered-prompt-refusal-tampered",
                    rendered_prompt_hash=binding.rendered_prompt_hash,
                    mutation_preview_hash=binding.mutation_preview_hash,
                    rollback_plan_ref=binding.rollback_plan_ref,
                    context_manifest_ref=manifest.manifest_id,
                    context_manifest_hash=binding.context_manifest_hash,
                    runtime_identity_hash=binding.runtime_identity_hash,
                    model_routing_identity_hash=binding.model_routing_identity_hash,
                    model_config_hash=binding.model_config_hash,
                    raw_response_ref="raw-response-refusal-tampered",
                    raw_response_hash="d" * 64,
                    semantic_reader_attempt_hash=attempt.semantic_reader_attempt_hash,
                    expires_at="2026-05-18T11:05:00+00:00",
                    authority_class="authoritative",
                    has_grounded_semantic_blocking_signal=True,
                )
            )
            bundle_use_store.put_unreserved(
                S7VoiceBundleUse.new_unreserved(
                    request_id=envelope.request_id,
                    source_ref_hash=consultation.source_ref_hash,
                    consultation_id=consultation.consultation_id,
                    used_at=NOW,
                )
            )
            validation = validate_s7_voice_source_bundle(
                consultation=consultation,
                bundle_store=bundle_store,
                bundle_use_store=bundle_use_store,
                semantic_reader_attempt_store=attempt_store,
                expected_binding=binding,
                now=NOW,
            )
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )

            finish = service.authorize_finish(
                now=NOW,
                envelope=envelope,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                maez_voice_consultation=consultation,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-primary",
                    "authentication_response": {"clientDataJSON": "valid-auth"},
                },
                guarded_store=guarded_store,
                source_bundle_validation=validation,
                source_ref_hash=consultation.source_ref_hash,
                reservation_token="runtime-token-not-persisted",
            )
            artifact_count = self._authorization_artifact_count(store.db_path)
            history = store.refusal_history_for_envelope(envelope)

        self.assertEqual(validation.status, "raw_response_hash_mismatch")
        self.assertEqual(finish.status_code, 409)
        self.assertEqual(finish.body["error"], "s7_guarded_source_bundle_required")
        self.assertEqual(artifact_count, 0)
        self.assertEqual(history, ())

    def test_backup_registration_authorization_completes_without_voice_producer(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            envelope, rendered = self._backup_registration_rendered_without_voice()
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                allow_degraded_primary_only=True,
            )

            finish = service.authorize_finish(
                now=NOW,
                envelope=envelope,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                maez_voice_consultation=None,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-primary",
                    "authentication_response": {"clientDataJSON": "valid-auth"},
                },
            )

        self.assertEqual(begin.status_code, 200)
        self.assertEqual(finish.status_code, 200)
        self.assertEqual(finish.body["grant_source"], "founder_webauthn")

    def test_authorize_finish_rejects_rendered_statement_that_differs_from_challenge(self):
        from core.governance import operator_user_boundary as s7
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ExplodingAuthenticationVerifier(),
                store_factory=lambda: store,
            )
            envelope = self._self_mod_envelope()
            rendered = self._rendered_statement()
            tampered_rendered = s7.render_request_statement(
                envelope=envelope,
                surface="cockpit",
                origin="http://localhost:11437",
                action_params_hash=rendered.action_params_hash,
                authority_context=self._authority_context(),
                maez_voice_consultation=self._voice_consultation(state="absent"),
                nonce="nonce-s7-1-auth-tampered",
                expires_at="2026-05-18T11:05:00+00:00",
                rendered_at=NOW,
            )
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )

            finish = service.authorize_finish(
                now=NOW,
                envelope=envelope,
                rendered_statement=tampered_rendered,
                precondition_hash=envelope.precondition_hash,
                maez_voice_consultation=self._voice_consultation(state="absent"),
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-primary",
                    "authentication_response": {"clientDataJSON": "valid-auth"},
                },
            )

        self.assertEqual(finish.status_code, 409)
        self.assertEqual(finish.body["error"], "s7_d12_binding_mismatch")
        with self.assertRaises(KeyError):
            _ = finish.body["artifact_id"]

    def test_authorize_finish_advances_sign_count(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ValidRegistrationVerifier(),
                store_factory=lambda: store,
            )
            envelope = self._self_mod_envelope()
            rendered = self._rendered_statement()
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )

            finish = service.authorize_finish(
                now=NOW,
                envelope=envelope,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                maez_voice_consultation=self._voice_consultation(state="absent"),
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-primary",
                    "authentication_response": {"clientDataJSON": "valid-auth"},
                },
            )
            updated = store.get_credential("cred-primary")
            artifact_count = self._authorization_artifact_count(store.db_path)

        self.assertEqual(finish.status_code, 409)
        self.assertEqual(finish.body["error"], "s7_guarded_state_store_required")
        assert updated is not None
        self.assertEqual(updated.sign_count, 1)
        self.assertEqual(artifact_count, 0)

    def test_authorize_finish_rejects_presence_only_for_uv_required_work(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            service = S7LocalWebAuthnCeremonyService(
                verifier=_PresenceOnlyAuthenticationVerifier(),
                store_factory=lambda: store,
            )
            envelope = self._self_mod_envelope()
            rendered = self._rendered_statement()
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )

            finish = service.authorize_finish(
                now=NOW,
                envelope=envelope,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                maez_voice_consultation=self._voice_consultation(state="absent"),
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-primary",
                    "authentication_response": {"clientDataJSON": "presence-only"},
                },
            )

        self.assertEqual(finish.status_code, 400)
        self.assertEqual(finish.body["error"], "s7_authentication_invalid")
        self.assertEqual(finish.body["detail"], "user_verification_required")
        with self.assertRaises(KeyError):
            _ = finish.body["artifact_id"]

    def test_authorize_finish_unknown_credential_fails_before_verifier(self):
        from core.governance.s7_webauthn_ceremony import S7LocalWebAuthnCeremonyService

        with tempfile.TemporaryDirectory() as tmp:
            store, _intent = self._store_with_bootstrap(tmp)
            store.store_credential(self._credential_record("cred-primary", kind="primary"))
            store.store_credential(self._credential_record("cred-backup", kind="backup"))
            service = S7LocalWebAuthnCeremonyService(
                verifier=_ExplodingAuthenticationVerifier(),
                store_factory=lambda: store,
            )
            envelope = self._self_mod_envelope()
            rendered = self._rendered_statement()
            begin = service.authorize_begin(
                now=NOW,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
            )

            finish = service.authorize_finish(
                now=NOW,
                envelope=envelope,
                rendered_statement=rendered,
                precondition_hash=envelope.precondition_hash,
                maez_voice_consultation=self._voice_consultation(state="absent"),
                session_binding="session-auth",
                internal_channel_binding="daemon-channel",
                request_json={
                    "challenge_id": begin.body["challenge_id"],
                    "credential_ref": "cred-missing",
                    "authentication_response": {"clientDataJSON": "unknown-credential"},
                },
            )

        self.assertEqual(finish.status_code, 409)
        self.assertEqual(finish.body["error"], "s7_credential_disabled")


if __name__ == "__main__":
    unittest.main()
