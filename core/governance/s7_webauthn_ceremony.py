# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S7.1 local WebAuthn ceremony service.

Daemon and cockpit routes are facades. This service is the shared producer that
will own challenges, credentials, refusal history, and artifacts as the S7.1
implementation fills in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
import uuid

from core.governance.operator_user_boundary import live_webauthn_ceremony_enabled
from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier


@dataclass(frozen=True)
class S7CeremonyServiceResult:
    body: dict[str, Any]
    status_code: int


StoreFactory = Callable[[], S7WebAuthnBootstrapStore]


def backup_registration_action_params() -> dict[str, Any]:
    return {
        "registration_class": "backup",
        "target": "memory/s7_1_webauthn/founder_credentials",
    }


def disable_credential_action_params(*, credential_ref: str, credential_kind: str) -> dict[str, Any]:
    if credential_kind not in {"primary", "backup"}:
        raise ValueError("S7 disable credential kind must be primary or backup")
    if not credential_ref:
        raise ValueError("S7 disable credential_ref is required")
    return {
        "credential_ref": credential_ref,
        "credential_kind": credential_kind,
        "target": "memory/s7_1_webauthn/founder_credentials",
    }


def build_backup_registration_envelope(
    *,
    request_id: str,
    created_at: str,
    expires_at: str,
    maez_voice_consultation_id: str | None,
):
    from core.governance import operator_user_boundary as s7

    params = backup_registration_action_params()
    return s7.build_work_request_envelope(
        request_id=request_id,
        action="register_backup_webauthn_credential",
        params=params,
        claimed_work_class="founder_credential_management",
        requesting_subsystem="s7_1_webauthn_ceremony",
        closed_symptom_code="self_mod_requested",
        proposed_change_class="protection_change",
        why_self_fix_failed_class="needs_human_authority",
        affected_refs=("file:memory/s7_1_webauthn/founder_credentials",),
        content_exposure_risk="credential_sensitive",
        precondition_hash=s7.canonical_hash(
            {
                "schema_version": "s7.1.register_backup.precondition.v1",
                "registration_class": "backup",
            }
        ),
        created_at=created_at,
        expires_at=expires_at,
        predicted_effect_class="protection_change",
        rollback_path_class="manual_review",
        maez_voice_consultation_id=maez_voice_consultation_id,
    )


def build_disable_credential_envelope(
    *,
    request_id: str,
    credential_ref: str,
    credential_kind: str,
    created_at: str,
    expires_at: str,
    maez_voice_consultation_id: str | None,
):
    from core.governance import operator_user_boundary as s7

    params = disable_credential_action_params(
        credential_ref=credential_ref,
        credential_kind=credential_kind,
    )
    return s7.build_work_request_envelope(
        request_id=request_id,
        action="disable_founder_webauthn_credential",
        params=params,
        claimed_work_class="founder_credential_management",
        requesting_subsystem="s7_1_webauthn_ceremony",
        closed_symptom_code="self_mod_requested",
        proposed_change_class="protection_change",
        why_self_fix_failed_class="needs_human_authority",
        affected_refs=("file:memory/s7_1_webauthn/founder_credentials",),
        content_exposure_risk="credential_sensitive",
        precondition_hash=s7.canonical_hash(
            {
                "schema_version": "s7.1.disable_credential.precondition.v1",
                "credential_ref": credential_ref,
                "credential_kind": credential_kind,
            }
        ),
        created_at=created_at,
        expires_at=expires_at,
        predicted_effect_class="protection_change",
        rollback_path_class="manual_review",
        maez_voice_consultation_id=maez_voice_consultation_id,
    )


@dataclass(frozen=True)
class S7LocalWebAuthnCeremonyService:
    """Core S7.1 ceremony service behind daemon and cockpit routes."""

    verifier: Any
    store_factory: StoreFactory

    def register_begin(
        self,
        *,
        now: str,
        request_json: dict[str, Any] | None,
        s7_execution_authorization: object | None = None,
    ) -> S7CeremonyServiceResult:
        dependency = self.verifier.dependency_state()
        if dependency.get("ok") is not True:
            return S7CeremonyServiceResult(body=dependency, status_code=503)
        store = self.store_factory()
        try:
            request = _require_mapping(request_json)
        except ValueError:
            request = {}
        registration_class = request.get("registration_class", "primary")
        if registration_class not in {"primary", "backup"}:
            return _schema_invalid("registration_class")
        if registration_class == "backup":
            if not store.has_enabled_primary():
                return S7CeremonyServiceResult(
                    body={"ok": False, "error": "s7_credential_setup_incomplete"},
                    status_code=409,
                )
            grant = _consume_backup_registration_authorization(
                s7_execution_authorization=s7_execution_authorization,
            )
            if grant is None:
                return S7CeremonyServiceResult(
                    body={
                        "ok": False,
                        "error": "s7_authorization_required",
                        "registration_class": "backup",
                    },
                    status_code=403,
                )
            try:
                session_binding = _require_text(request, "session_binding")
            except ValueError as exc:
                return _schema_invalid(str(exc))
            challenge = store.create_registration_challenge(
                challenge_kind="register_backup",
                session_binding=session_binding,
                now=now,
                expires_at=_add_minutes(now, 10),
            )
            exclude_credentials = store.exclude_credentials_for_backup_registration()
            return S7CeremonyServiceResult(
                body={
                    "ok": True,
                    "registration_class": "backup",
                    **challenge,
                    "exclude_credentials": exclude_credentials,
                    "public_key_options": {
                        "rp": {"id": "localhost", "name": "Maez local founder ceremony"},
                        "user": {
                            "id": "Zm91bmRlci1iYWNrdXA",
                            "name": "founder-backup",
                            "displayName": "Founder backup",
                        },
                        "challenge": challenge["challenge_b64"],
                        "pubKeyCredParams": _public_key_credential_params(),
                        "timeout": 600000,
                        "attestation": "direct",
                        "excludeCredentials": [
                            _credential_descriptor(store, credential_ref)
                            for credential_ref in exclude_credentials
                        ],
                        "authenticatorSelection": {
                            "residentKey": "preferred",
                            "userVerification": "required",
                        },
                    },
                },
                status_code=200,
            )
        readiness = store.first_registration_readiness(now=now)
        if readiness.get("ok") is not True:
            status = 401 if readiness.get("error") == "s7_bootstrap_required" else 410
            return S7CeremonyServiceResult(body=readiness, status_code=status)
        try:
            intent_id = _require_text(request, "bootstrap_intent_id")
            raw_token = _require_text(request, "bootstrap_token")
            session_binding = _require_text(request, "session_binding")
        except ValueError as exc:
            return _schema_invalid(str(exc))
        if not store.bootstrap_intent_valid(
            intent_id=intent_id,
            raw_token=raw_token,
            now=now,
        ):
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_bootstrap_invalid"},
                status_code=401,
            )
        challenge = store.create_registration_challenge(
            challenge_kind="register_primary",
            session_binding=session_binding,
            now=now,
            expires_at=_add_minutes(now, 10),
        )
        return S7CeremonyServiceResult(
            body={
                "ok": True,
                **challenge,
                "public_key_options": {
                    "rp": {"id": "localhost", "name": "Maez local founder ceremony"},
                    "user": {
                        "id": "Zm91bmRlcg",
                        "name": "founder",
                        "displayName": "Founder",
                    },
                    "challenge": challenge["challenge_b64"],
                    "pubKeyCredParams": _public_key_credential_params(),
                    "timeout": 600000,
                    "attestation": "direct",
                    "authenticatorSelection": {
                        "residentKey": "discouraged",
                        "userVerification": "required",
                    },
                },
            },
            status_code=200,
        )

    def register_finish(
        self,
        *,
        now: str,
        request_json: dict[str, Any] | None,
    ) -> S7CeremonyServiceResult:
        dependency = self.verifier.dependency_state()
        if dependency.get("ok") is not True:
            return S7CeremonyServiceResult(body=dependency, status_code=503)
        store = self.store_factory()
        try:
            request = _require_mapping(request_json)
            registration_class = request.get("registration_class", "primary")
            if registration_class not in {"primary", "backup"}:
                raise ValueError("registration_class")
            challenge_id = _require_text(request, "challenge_id")
            session_binding = _require_text(request, "session_binding")
            registration_response = request["registration_response"]
            if not isinstance(registration_response, dict):
                raise ValueError("registration_response")
            intent_id = _require_text(request, "bootstrap_intent_id") if registration_class == "primary" else ""
            raw_token = _require_text(request, "bootstrap_token") if registration_class == "primary" else ""
        except (KeyError, ValueError) as exc:
            return _schema_invalid(str(exc))

        challenge = store.registration_challenge_for_finish(
            challenge_id=challenge_id,
            session_binding=session_binding,
            now=now,
        )
        if challenge is None:
            status = store.registration_challenge_status(
                challenge_id=challenge_id,
                session_binding=session_binding,
                now=now,
            )
            status_code = 410 if status in {"expired", "replayed"} else 400
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_challenge_replayed", "challenge_state": status},
                status_code=status_code,
            )
        if registration_class == "primary" and not store.bootstrap_intent_valid(
            intent_id=intent_id,
            raw_token=raw_token,
            now=now,
        ):
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_bootstrap_invalid"},
                status_code=401,
            )
        expected_kind = "register_primary" if registration_class == "primary" else "register_backup"
        if challenge.get("challenge_kind") != expected_kind:
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_challenge_kind_mismatch"},
                status_code=400,
            )

        verified = self.verifier.verify_registration_response(
            registration_response=registration_response,
            challenge=challenge,
            expected_origin="http://localhost:11437",
            expected_rp_id="localhost",
            require_user_verification=True,
        )
        if verified.get("ok") is not True:
            return S7CeremonyServiceResult(body=verified, status_code=400)

        if not store.consume_challenge(challenge_id, now=now):
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_challenge_replayed", "challenge_state": "replayed"},
                status_code=410,
            )
        if registration_class == "backup":
            from core.governance.s7_webauthn_bootstrap import FounderWebAuthnCredentialRecord

            record = FounderWebAuthnCredentialRecord.build(
                credential_ref=str(verified["credential_ref"]),
                actor_handle_hmac="hmac:s7:founder:" + ("0" * 64),
                role_names=("bonded_user",),
                public_key=str(verified["public_key"]),
                sign_count=int(verified.get("sign_count", 0)),
                rp_id="localhost",
                origin="http://localhost:11437",
                created_at=now,
                backup_credential=True,
                enabled=True,
                credential_kind="backup",
                label="backup key",
                registration_challenge_id=challenge_id,
                attestation_format=_optional_text(verified.get("attestation_format")),
                aaguid=_optional_text(verified.get("aaguid")),
                authenticator_attachment=_optional_text(verified.get("authenticator_attachment")),
                backup_eligible=_optional_bool(verified.get("backup_eligible")),
                backed_up=_optional_bool(verified.get("backed_up")),
                transports=tuple(str(value) for value in verified.get("transports", ())),
                library_name=str(verified.get("library_name", dependency.get("library_name", ""))),
                library_version=str(verified.get("library_version", dependency.get("library_version", ""))),
                sign_count_mode=str(verified.get("sign_count_mode", "unknown")),
                uv_capable=_optional_bool(verified.get("uv_capable")),
                uv_required_for_guarded=True,
                distinct_device_confidence=_backup_distinct_device_confidence(
                    store=store,
                    verified=verified,
                ),
            )
            try:
                store.store_credential(record)
            except ValueError as exc:
                return S7CeremonyServiceResult(
                    body={"ok": False, "error": str(exc)},
                    status_code=409,
                )
            return S7CeremonyServiceResult(
                body={
                    "ok": True,
                    "credential_ref": record.credential_ref,
                    "registration_class": "backup",
                },
                status_code=200,
            )
        result = store.consume_for_first_primary(
            intent_id=intent_id,
            raw_token=raw_token,
            credential_ref=str(verified["credential_ref"]),
            public_key=str(verified["public_key"]),
            now=now,
            sign_count=int(verified.get("sign_count", 0)),
            attestation_format=_optional_text(verified.get("attestation_format")),
            aaguid=_optional_text(verified.get("aaguid")),
            authenticator_attachment=_optional_text(verified.get("authenticator_attachment")),
            backup_eligible=_optional_bool(verified.get("backup_eligible")),
            backed_up=_optional_bool(verified.get("backed_up")),
            transports=tuple(str(value) for value in verified.get("transports", ())),
            library_name=str(verified.get("library_name", dependency.get("library_name", ""))),
            library_version=str(verified.get("library_version", dependency.get("library_version", ""))),
            sign_count_mode=str(verified.get("sign_count_mode", "unknown")),
            uv_capable=_optional_bool(verified.get("uv_capable")),
        )
        if result.get("ok") is not True:
            return S7CeremonyServiceResult(body=result, status_code=409)
        return S7CeremonyServiceResult(
            body={
                "ok": True,
                "credential_ref": result["credential_ref"],
                "registration_class": "primary",
                "bootstrap_closed": True,
            },
            status_code=200,
        )

    def authorize_begin(
        self,
        *,
        now: str,
        rendered_statement: Any,
        precondition_hash: str,
        session_binding: str,
        internal_channel_binding: str,
        allow_degraded_primary_only: bool = False,
        allow_degraded_backup_only: bool = False,
        consultation_exemption: Any | None = None,
        durable_cutover_selection: Any | None = None,
    ) -> S7CeremonyServiceResult:
        dependency = self.verifier.dependency_state()
        if dependency.get("ok") is not True:
            return S7CeremonyServiceResult(body=dependency, status_code=503)
        try:
            exemption_projection_hash = _r11_challenge_projection_hash(
                rendered_statement=rendered_statement,
                precondition_hash=precondition_hash,
                consultation_exemption=consultation_exemption,
                durable_cutover_selection=durable_cutover_selection,
            )
        except ValueError as exc:
            error = str(exc)
            if error not in {
                "s7_signed_statement_contradicts_exemption",
                "s7_consultation_exemption_invalid",
            }:
                error = "s7_consultation_exemption_invalid"
            return S7CeremonyServiceResult(
                body={"ok": False, "error": error},
                status_code=409,
            )
        store = self.store_factory()
        recovery = store.credential_recovery_state()
        if recovery.get("mode") != "ready":
            primary_only_allowed = (
                allow_degraded_primary_only is True
                and recovery.get("primary_credential_state") == "enabled"
            )
            backup_only_allowed = (
                allow_degraded_backup_only is True
                and recovery.get("primary_credential_state") == "missing"
                and recovery.get("backup_credential_state") == "enabled"
            )
            if not primary_only_allowed and not backup_only_allowed:
                return S7CeremonyServiceResult(
                    body={
                        "ok": False,
                        "error": "s7_credential_setup_incomplete",
                        "ceremony_mode": recovery.get("mode"),
                        "primary_credential_state": recovery.get("primary_credential_state"),
                        "backup_credential_state": recovery.get("backup_credential_state"),
                        "distinct_device_confidence": recovery.get("distinct_device_confidence"),
                    },
                    status_code=409,
                )
        challenge = store.create_authorization_challenge(
            rendered_statement=rendered_statement,
            precondition_hash=precondition_hash,
            session_binding=session_binding,
            internal_channel_binding=internal_channel_binding,
            now=now,
            expires_at=_add_minutes(now, 5),
            uv_required=True,
            consultation_exemption_projection_hash=exemption_projection_hash,
        )
        allow_credentials = store.allow_credentials_for_authorization()
        if allow_degraded_primary_only is True:
            allow_credentials = tuple(
                record.credential_ref
                for record in store.list_credentials()
                if record.enabled
                and record.credential_kind == "primary"
                and "bonded_user" in record.role_names
            )
        elif allow_degraded_backup_only is True:
            allow_credentials = tuple(
                record.credential_ref
                for record in store.list_credentials()
                if record.enabled
                and record.credential_kind == "backup"
                and "bonded_user" in record.role_names
            )
        return S7CeremonyServiceResult(
            body={
                "ok": True,
                **challenge,
                "allow_credentials": allow_credentials,
                "public_key_options": {
                    "rpId": "localhost",
                    "challenge": challenge["challenge_b64"],
                    "timeout": 300000,
                    "userVerification": "required",
                    "allowCredentials": [
                        _credential_descriptor(store, credential_ref)
                        for credential_ref in allow_credentials
                    ],
                },
            },
            status_code=200,
        )

    def authorize_finish(
        self,
        *,
        now: str,
        envelope: Any,
        rendered_statement: Any,
        precondition_hash: str,
        maez_voice_consultation: Any,
        session_binding: str,
        internal_channel_binding: str,
        request_json: dict[str, Any] | None,
        guarded_store: Any | None = None,
        source_bundle_validation: Any | None = None,
        source_bundle_binding: Any | None = None,
        source_ref_hash: str | None = None,
        reservation_token: str | None = None,
        consultation_exemption: Any | None = None,
        durable_cutover_selection: Any | None = None,
    ) -> S7CeremonyServiceResult:
        dependency = self.verifier.dependency_state()
        if dependency.get("ok") is not True:
            return S7CeremonyServiceResult(body=dependency, status_code=503)
        store = self.store_factory()
        try:
            request = _require_mapping(request_json)
            challenge_id = _require_text(request, "challenge_id")
            claimed_credential_ref = _require_text(request, "credential_ref")
            authentication_response = request["authentication_response"]
            if not isinstance(authentication_response, dict):
                raise ValueError("authentication_response")
        except (KeyError, ValueError) as exc:
            return _schema_invalid(str(exc))

        challenge = store.authorization_challenge_for_finish(
            challenge_id=challenge_id,
            session_binding=session_binding,
            internal_channel_binding=internal_channel_binding,
            now=now,
        )
        if challenge is None:
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_challenge_replayed"},
                status_code=410,
            )
        if not _challenge_matches_rendered_d12(
            challenge=challenge,
            rendered_statement=rendered_statement,
            precondition_hash=precondition_hash,
        ):
            return _d12_binding_mismatch()
        try:
            presented_exemption_projection_hash = _r11_challenge_projection_hash(
                rendered_statement=rendered_statement,
                precondition_hash=precondition_hash,
                consultation_exemption=consultation_exemption,
                durable_cutover_selection=durable_cutover_selection,
            )
        except ValueError as exc:
            error = str(exc)
            if error == "s7_signed_statement_contradicts_exemption":
                return S7CeremonyServiceResult(
                    body={"ok": False, "error": error},
                    status_code=409,
                )
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_consultation_exemption_invalid"},
                status_code=409,
            )
        if (
            challenge.get("consultation_exemption_projection_hash")
            != presented_exemption_projection_hash
        ):
            return S7CeremonyServiceResult(
                body={
                    "ok": False,
                    "error": "s7_consultation_exemption_challenge_mismatch",
                },
                status_code=409,
            )
        from core.governance import operator_user_boundary as s7

        voice_seat_work = (
            getattr(envelope, "derived_work_class", None)
            in s7.VOICE_SEAT_WORK_CLASSES
        )
        fresh_source_bundle_validation = None
        if voice_seat_work and consultation_exemption is not None:
            # R11: the exemption is the OTHER lawful evidence shape. It never
            # relaxes the bundle requirement -- it replaces it, and the two
            # are mutually exclusive so nothing can say "both".
            from core.governance.s7_consultation_exemption import (
                born_by_any_signal,
                consultation_exemption_admits,
            )

            if (
                source_bundle_validation is not None
                or source_bundle_binding is not None
                or source_ref_hash is not None
                or reservation_token is not None
                or maez_voice_consultation is not None
            ):
                return S7CeremonyServiceResult(
                    body={
                        "ok": False,
                        "error": "s7_exemption_and_consultation_both_present",
                    },
                    status_code=409,
                )
            # THE OWNER MUST NOT TAP ON A FALSE PICTURE. Without this the
            # exemption admits beside a statement that says "Maez consulted:
            # yes" -- the signed text and the authority would disagree, and
            # the human reads the text. The rendered statement must itself
            # carry the absence, with no consultation hash and no objection.
            if (
                getattr(rendered_statement, "maez_consulted_state", None)
                != s7.MAEZ_CONSULTED_NOT_PERFORMED_R11
                or rendered_statement.maez_voice_consultation_hash is not None
                or getattr(rendered_statement, "maez_objection_state", None) != "none"
            ):
                return S7CeremonyServiceResult(
                    body={
                        "ok": False,
                        "error": "s7_signed_statement_contradicts_exemption",
                    },
                    status_code=409,
                )
            if not consultation_exemption_admits(
                envelope=envelope,
                exemption=consultation_exemption,
                durable_cutover_selection=durable_cutover_selection,
                ledger_writes_enabled=born_by_any_signal(),
            ):
                return S7CeremonyServiceResult(
                    body={"ok": False, "error": "s7_consultation_exemption_invalid"},
                    status_code=409,
                )
            # The bundle branch requires an EXACT guarded store bound to this
            # ceremony's database. The exemption branch checked neither, so a
            # fake or different-database store could satisfy finish: the
            # challenge and credential consumed in one database while the
            # artifact was written to another, or to nothing at all.
            #
            # The inner store is isinstance, not exact type. Exact typing here
            # refused the cutover's _HeldS7AuthorizationStore -- a subclass
            # whose every transaction stays on the ceremony's HELD inode,
            # strictly stricter than the plain store -- and the owner's first
            # real assertion died at presence_mint_failed (2026-08-13; the two
            # hardening passes had never run together, and this gate landed
            # with no test naming its error). The guarantee is unchanged:
            # structural fakes are not instances, and a store addressing any
            # other database still refuses on db_path below. A subclass can
            # only come from code already holding the real class, which is the
            # same in-process authority that could construct the exact type.
            from core.governance import s7_guarded_execution as guarded

            exempt_store = getattr(guarded_store, "authorization_store", None)
            if (
                type(guarded_store) is not guarded.S7GuardedStateStore
                or not isinstance(exempt_store, s7.S7AuthorizationStore)
                or exempt_store.db_path != store.db_path
            ):
                return S7CeremonyServiceResult(
                    body={"ok": False, "error": "s7_guarded_state_store_required"},
                    status_code=409,
                )
            authorization_store = exempt_store
        elif voice_seat_work:
            from core.governance import s7_guarded_execution as guarded

            source_bundle_ok = (
                type(guarded_store) is guarded.S7GuardedStateStore
                and type(source_bundle_validation)
                is guarded.S7VoiceSourceBundleValidationResultV2
                and getattr(source_bundle_validation, "_token_verified", False) is True
                and source_bundle_validation.schema_version
                == guarded.S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA
                and source_bundle_validation.action == rendered_statement.action
                and (
                    (
                        source_bundle_validation.status == "valid_absent"
                        and source_bundle_validation.source_bundle_valid is True
                        and source_bundle_validation.mint_eligible is True
                        and source_bundle_validation.authority_projection == "valid_absent"
                        and source_bundle_validation.failure_reason_code is None
                    )
                    or (
                        source_bundle_validation.status == "blocking_present"
                        and source_bundle_validation.source_bundle_valid is True
                        and source_bundle_validation.mint_eligible is False
                        and source_bundle_validation.authority_projection
                        == "grounded_refusal"
                        and source_bundle_validation.failure_reason_code is None
                    )
                )
            )
            if source_bundle_ok is True:
                fresh_source_bundle_validation = (
                    _revalidate_finish_voice_source_bundle(
                        envelope=envelope,
                        consultation=maez_voice_consultation,
                        guarded_store=guarded_store,
                        source_bundle_binding=source_bundle_binding,
                        source_ref_hash=source_ref_hash,
                        source_bundle_validation=source_bundle_validation,
                        now=now,
                    )
                )
                source_bundle_ok = (
                    type(fresh_source_bundle_validation)
                    is guarded.S7VoiceSourceBundleValidationResultV2
                    and fresh_source_bundle_validation == source_bundle_validation
                )
            if source_bundle_ok is not True:
                return S7CeremonyServiceResult(
                    body={
                        "ok": False,
                        "error": "s7_guarded_source_bundle_required",
                        "detail": "S7.3 voice-seat work requires validator-produced source-bundle evidence",
                    },
                    status_code=409,
                )
            authorization_store = guarded_store.authorization_store
            if (
                type(authorization_store) is not s7.S7AuthorizationStore
                or authorization_store.db_path != store.db_path
            ):
                return S7CeremonyServiceResult(
                    body={
                        "ok": False,
                        "error": "s7_guarded_state_store_required",
                    },
                    status_code=409,
                )
        else:
            authorization_store = s7.S7AuthorizationStore(store.db_path)
        voice = authorization_voice_seat_recheck(
            envelope=envelope,
            maez_voice_consultation=maez_voice_consultation,
            refusal_history_store=store,
            rendered_text_hash=rendered_statement.rendered_text_hash,
            requester_ref="founder-local-browser",
            now=now,
            guarded_store=guarded_store,
            source_bundle_binding=source_bundle_binding,
            source_ref_hash=source_ref_hash,
            source_bundle_validation=source_bundle_validation,
            consultation_exemption=consultation_exemption,
            durable_cutover_selection=durable_cutover_selection,
        )
        if voice.status_code != 200:
            return voice
        aggregation = authorization_aggregation_recheck(
            envelope=envelope,
            history=store.refusal_history_for_envelope(envelope, now=now),
        )
        if aggregation.status_code != 200:
            return aggregation
        credential = store.get_credential(claimed_credential_ref)
        if credential is None or not credential.enabled or "bonded_user" not in credential.role_names:
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_credential_disabled"},
                status_code=409,
            )
        verifier_method = getattr(self.verifier, "verify_authentication_response", None)
        if verifier_method is None:
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_authentication_invalid"},
                status_code=400,
            )
        verified = verifier_method(
            authentication_response=authentication_response,
            challenge=challenge,
            expected_origin="http://localhost:11437",
            expected_rp_id="localhost",
            credential_public_key=credential.public_key,
            current_sign_count=credential.sign_count,
            require_user_verification=bool(challenge["uv_required"]),
        )
        if verified.get("ok") is not True:
            return S7CeremonyServiceResult(body=verified, status_code=400)
        if verified.get("user_presence") is not True:
            return S7CeremonyServiceResult(
                body={
                    "ok": False,
                    "error": "s7_authentication_invalid",
                    "detail": "user_presence_required",
                },
                status_code=400,
            )
        if bool(challenge["uv_required"]) and verified.get("user_verification") is not True:
            return S7CeremonyServiceResult(
                body={
                    "ok": False,
                    "error": "s7_authentication_invalid",
                    "detail": "user_verification_required",
                },
                status_code=400,
            )
        credential_ref = str(verified["credential_ref"])
        if credential_ref != claimed_credential_ref:
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_authentication_invalid", "detail": "credential_mismatch"},
                status_code=400,
            )
        if not store.credential_can_authorize(credential_ref):
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_credential_disabled"},
                status_code=409,
            )
        sign_count = store.advance_sign_count(
            credential_ref,
            new_sign_count=int(verified.get("sign_count", credential.sign_count)),
            now=now,
        )
        if sign_count.get("ok") is not True:
            return S7CeremonyServiceResult(body=sign_count, status_code=409)
        if not store.consume_challenge(challenge_id, now=now):
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_challenge_replayed"},
                status_code=410,
            )

        artifact_id = f"s7authz_{uuid.uuid4().hex}"
        artifact = s7.S7AuthorizationArtifact(
            artifact_id=artifact_id,
            request_id=rendered_statement.request_id,
            request_envelope_hash=rendered_statement.request_envelope_hash,
            rendered_text_hash=rendered_statement.rendered_text_hash,
            action=rendered_statement.action,
            action_params_hash=rendered_statement.action_params_hash,
            precondition_hash=precondition_hash,
            authority_context_hash=rendered_statement.authority_context_hash,
            derived_work_class=rendered_statement.derived_work_class,
            derived_aggregation_group=rendered_statement.derived_aggregation_group,
            nonce=rendered_statement.nonce,
            credential_ref=credential_ref,
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=bool(verified.get("user_presence", True)),
            user_verification=bool(verified.get("user_verification", False)),
            created_at=now,
            expires_at=str(challenge["expires_at"]),
            consumed_at=None,
        )
        from core.governance.s7_guarded_execution import mint_authorization_artifact

        try:
            mint_authorization_artifact(
                artifact=artifact,
                authorization_store=authorization_store,
                guarded_store=guarded_store,
                source_bundle_validation=fresh_source_bundle_validation,
                source_ref_hash=source_ref_hash,
                reservation_token=reservation_token,
                now=now,
                consultation_exemption=consultation_exemption,
                durable_cutover_selection=durable_cutover_selection,
            )
        except ValueError as exc:
            if artifact.derived_work_class in s7.VOICE_SEAT_WORK_CLASSES:
                error = (
                    "s7_guarded_state_store_required"
                    if guarded_store is None
                    else "s7_guarded_source_bundle_required"
                )
                return S7CeremonyServiceResult(
                    body={
                        "ok": False,
                        "error": error,
                        "detail": str(exc),
                    },
                    status_code=409,
                )
            raise
        authorization_record_id = store.record_authorization_history(
            envelope=envelope,
            rendered_text_hash=rendered_statement.rendered_text_hash,
            requester_ref="founder-local-browser",
            created_at=now,
        )
        return S7CeremonyServiceResult(
            body={
                "ok": True,
                "artifact_id": artifact_id,
                "request_id": rendered_statement.request_id,
                "credential_ref": credential_ref,
                "grant_source": "founder_webauthn",
                "authorization_record_id": authorization_record_id,
            },
            status_code=200,
        )

    def status(self, *, now: str) -> S7CeremonyServiceResult:
        dependency = self.verifier.dependency_state()
        dependency_state = "available" if dependency.get("ok") is True else "missing"
        dependency_version = dependency.get("library_version")
        store = self.store_factory()
        recovery = store.credential_recovery_state()
        try:
            bootstrap_state = store.bootstrap_state(now=now)
        except Exception:
            bootstrap_state = "unavailable"
        mode = str(recovery["mode"])
        body = {
            "ok": True,
            "ceremony_mode": mode,
            "live_flag_enabled": live_webauthn_ceremony_enabled(),
            "verifier_dependency_state": dependency_state,
            "verifier_dependency_version": dependency_version,
            "bootstrap_state": bootstrap_state,
            "primary_credential_state": recovery["primary_credential_state"],
            "backup_credential_state": recovery["backup_credential_state"],
            "active_credential_count": recovery["active_credential_count"],
            "manual_recovery_required": recovery["manual_recovery_required"],
            "manual_recovery_cause": recovery["manual_recovery_cause"],
            "single_active_credential_warning": recovery["active_credential_count"] == 1,
            "distinct_device_confidence": recovery["distinct_device_confidence"],
            "uv_policy_state": "pending",
            "clone_detection_state": "pending",
            "witnessed_social_recovery_state": "deferred_l9",
            "internal_channel_state": "configured",
            "last_registration_class": None,
            "last_authorization_class": None,
            "last_error_code": None if dependency.get("ok") is True else dependency.get("error"),
        }
        return S7CeremonyServiceResult(body=body, status_code=200)


def default_s7_webauthn_ceremony_service(
    *,
    store_factory: StoreFactory,
) -> S7LocalWebAuthnCeremonyService:
    return S7LocalWebAuthnCeremonyService(
        verifier=S7ProductionWebAuthnVerifier(),
        store_factory=store_factory,
    )


def authorization_voice_seat_recheck(
    *,
    envelope: Any,
    maez_voice_consultation: Any,
    refusal_history_store: Any | None = None,
    rendered_text_hash: str | None = None,
    requester_ref: str | None = None,
    now: str | None = None,
    guarded_store: Any | None = None,
    source_bundle_binding: Any | None = None,
    source_ref_hash: str | None = None,
    source_bundle_validation: Any | None = None,
    consultation_exemption: Any | None = None,
    durable_cutover_selection: Any | None = None,
) -> S7CeremonyServiceResult:
    """Finish-time S7.1 voice-seat gate before artifact minting."""

    from core.governance.operator_user_boundary import (
        VOICE_SEAT_WORK_CLASSES,
        voice_consultation_satisfies_request,
    )

    if getattr(envelope, "derived_work_class", None) not in VOICE_SEAT_WORK_CLASSES:
        return S7CeremonyServiceResult(
            body={"ok": True, "maez_objection_state": "none"},
            status_code=200,
        )
    # R11: a TYPED absence of consultation, scoped to one action, expiring at
    # birth. Checked before any consultation logic because under R11 there is
    # no consultation object at all -- constructing one would assert an ask
    # that never happened. An exemption that is present but does not admit
    # BLOCKS here; it must never fall through to the consultation path, where
    # a different rule could rescue it.
    if consultation_exemption is not None:
        from core.governance.s7_consultation_exemption import (
            R11_RULING_ID,
            born_by_any_signal,
            consultation_exemption_admits,
        )

        if (
            maez_voice_consultation is not None
            or source_bundle_binding is not None
            or source_ref_hash is not None
            or source_bundle_validation is not None
        ):
            return _voice_seat_block(
                "not_determined",
                reason="exemption_and_consultation_both_present",
                envelope=envelope,
                refusal_history_store=refusal_history_store,
                rendered_text_hash=rendered_text_hash,
                requester_ref=requester_ref,
                now=now,
            )

        if consultation_exemption_admits(
            envelope=envelope,
            exemption=consultation_exemption,
            durable_cutover_selection=durable_cutover_selection,
            ledger_writes_enabled=born_by_any_signal(),
        ):
            return S7CeremonyServiceResult(
                body={
                    "ok": True,
                    # NOT an objection state. R11 records that nothing was
                    # asked; "absent" and "not_determined" both describe an
                    # ask that happened, and must stay unreachable from here.
                    "consultation_performed": False,
                    "consultation_exemption_ruling": R11_RULING_ID,
                },
                status_code=200,
            )
        return _voice_seat_block(
            "not_determined",
            reason="consultation_exemption_invalid",
            envelope=envelope,
            refusal_history_store=refusal_history_store,
            rendered_text_hash=rendered_text_hash,
            requester_ref=requester_ref,
            now=now,
        )
    if getattr(envelope, "action", None) == "model_routing.cutover_cuda":
        # R11 removed consultation as an authority shape for this ONE action.
        # Stop before both the retired cutover path and the generic bundle path:
        # otherwise an alternate caller could still authorize the cutover with
        # voice evidence that the canonical ceremony no longer produces.
        return _voice_seat_block(
            "not_determined",
            reason="r11_consultation_exemption_required",
            envelope=envelope,
            refusal_history_store=refusal_history_store,
            rendered_text_hash=rendered_text_hash,
            requester_ref=requester_ref,
            now=now,
        )
    if not voice_consultation_satisfies_request(envelope, maez_voice_consultation):
        return _voice_seat_block(
            "not_determined",
            reason="missing_or_mismatched_voice_fact",
            envelope=envelope,
            refusal_history_store=refusal_history_store,
            rendered_text_hash=rendered_text_hash,
            requester_ref=requester_ref,
            now=now,
        )
    state = str(getattr(maez_voice_consultation, "maez_objection_state", "not_determined"))
    unavailable_reason = getattr(maez_voice_consultation, "unavailable_reason_code", None)
    if state != "absent":
        return _voice_seat_block(
            state,
            reason="maez_voice_not_clear",
            envelope=envelope,
            refusal_history_store=refusal_history_store,
            rendered_text_hash=rendered_text_hash,
            requester_ref=requester_ref,
            now=now,
        )
    if unavailable_reason not in {None, "none"}:
        return _voice_seat_block(
            "not_determined",
            reason=str(unavailable_reason),
            envelope=envelope,
            refusal_history_store=refusal_history_store,
            rendered_text_hash=rendered_text_hash,
            requester_ref=requester_ref,
            now=now,
        )
    if getattr(maez_voice_consultation, "maez_withdrew_request", False) is True:
        return _voice_seat_block(
            "present",
            reason="maez_withdrew_request",
            envelope=envelope,
            refusal_history_store=refusal_history_store,
            rendered_text_hash=rendered_text_hash,
            requester_ref=requester_ref,
            now=now,
        )
    if _generic_voice_evidence_revalidated_at_gate(
        envelope=envelope,
        consultation=maez_voice_consultation,
        guarded_store=guarded_store,
        source_bundle_binding=source_bundle_binding,
        source_ref_hash=source_ref_hash,
        source_bundle_validation=source_bundle_validation,
        now=now,
    ) is None:
        return _voice_seat_block(
            "absent",
            reason="missing_or_invalid_voice_evidence",
            envelope=envelope,
            refusal_history_store=refusal_history_store,
            rendered_text_hash=rendered_text_hash,
            requester_ref=requester_ref,
            now=now,
        )
    return S7CeremonyServiceResult(
        body={
            "ok": True,
            "maez_objection_state": "absent",
            "maez_voice_consultation_id": maez_voice_consultation.consultation_id,
        },
        status_code=200,
    )


def _generic_voice_evidence_revalidated_at_gate(
    *,
    envelope: Any,
    consultation: Any,
    guarded_store: Any | None,
    source_bundle_binding: Any | None,
    source_ref_hash: str | None,
    source_bundle_validation: Any | None,
    now: str | None,
) -> Any | None:
    """Reopen generic response/reader evidence before accepting `absent`."""

    from core.governance import operator_user_boundary as s7
    from core.governance import s7_guarded_execution as guarded

    if (
        type(envelope) is not s7.WorkRequestEnvelope
        or type(consultation) is not s7.MaezVoiceConsultation
        or type(guarded_store) is not guarded.S7GuardedStateStore
        or type(source_bundle_binding) is not guarded.S7VoiceSourceBundleHashBinding
        or type(source_ref_hash) is not str
        or type(now) is not str
        or source_ref_hash != consultation.source_ref_hash
        or source_bundle_binding.request_id != envelope.request_id
        or source_bundle_binding.consultation_id != consultation.consultation_id
        or source_bundle_binding.source_ref_hash != source_ref_hash
        or source_bundle_binding.precondition_hash != envelope.precondition_hash
        or source_bundle_binding.maez_voice_consultation_hash
        != s7.maez_voice_consultation_hash(consultation)
    ):
        return None
    db_path = guarded_store.authorization_store.db_path
    bundle_store = guarded.S7VoiceConsultationBundleStore(db_path)
    bundle_use_store = guarded.S7VoiceBundleUseStore(db_path)
    attempt_store = guarded.S7SemanticReaderAttemptStore(db_path)
    with guarded_store.authorization_store.anchored_transaction() as conn:
        try:
            bundle, version = guarded.read_voice_source_bundle(
                source_ref_hash=source_ref_hash,
                conn=conn,
            )
        except guarded.S7VoiceSourceBundleEvidenceInvalid:
            return None
        validation = guarded.validate_voice_source_bundle(
            bundle=bundle,
            version=version,
            purpose="execution",
            expected_binding=source_bundle_binding,
        )
        validation_complete = (
            validation.status == "valid_absent"
            and validation.source_bundle_valid is True
            and validation.mint_eligible is True
            and validation.authority_projection == "valid_absent"
            and validation.failure_reason_code is None
        ) or (
            validation.status == "blocking_present"
            and validation.source_bundle_valid is True
            and validation.mint_eligible is False
            and validation.authority_projection == "grounded_refusal"
            and validation.failure_reason_code is None
        )
        if (
            version != guarded.S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA
            or bundle.action != envelope.action
            or not validation_complete
            or validation.action != envelope.action
            or (
                source_bundle_validation is not None
                and validation != source_bundle_validation
            )
            or not guarded._bundle_fresh(bundle, now=now)
            or not guarded._consultation_bundle_cross_fields_valid(
                consultation=consultation,
                bundle=bundle,
            )
            or not guarded._context_manifest_policy_valid(
                bundle=bundle,
                bundle_store=bundle_store,
                expected_binding=source_bundle_binding,
                connection=conn,
            )
        ):
            return None
        bundle_use = bundle_use_store.get_for_source_ref(
            source_ref_hash,
            connection=conn,
        )
        if (
            bundle_use is None
            or bundle_use.reservation_state != "unreserved"
            or bundle_use.artifact_id is not None
            or bundle_use.reservation_token_hash is not None
            or bundle_use.reserved_at is not None
            or bundle_use.consumed_at is not None
        ):
            return None
        if bundle.rendered_prompt_ref is None or bundle.rendered_prompt_hash is None:
            return None
        rendered_prompt = bundle_store.read_rendered_prompt(
            bundle.rendered_prompt_ref,
            connection=conn,
        )
        if (
            rendered_prompt is None
            or s7.canonical_hash(rendered_prompt) != bundle.rendered_prompt_hash
        ):
            return None
        if bundle.raw_response_ref is None or bundle.raw_response_hash is None:
            return None
        raw_response = bundle_store.read_raw_response(
            bundle.raw_response_ref,
            connection=conn,
        )
        if (
            raw_response is None
            or s7.canonical_hash(raw_response) != bundle.raw_response_hash
        ):
            return None
        if bundle.semantic_reader_attempt_hash is None:
            return None
        attempt = attempt_store.get(
            bundle.semantic_reader_attempt_hash,
            connection=conn,
        )
        if (
            attempt is None
            or attempt.semantic_reader_route_identity_hash
            not in guarded.REVIEWED_SEMANTIC_READER_ROUTE_IDENTITIES
        ):
            return None
        effective_reader_outcome = guarded._effective_reader_outcome_replays(
            raw_response=raw_response,
            attempt=attempt,
        )
        if (
            not guarded._replayed_reducer_fields_match(
                consultation=consultation,
                effective_reader_outcome=effective_reader_outcome,
            )
            or not guarded._replayed_authority_fields_match(
                bundle=bundle,
                effective_reader_outcome=effective_reader_outcome,
            )
            or not guarded._authority_predicate_valid(
                consultation=consultation,
                bundle=bundle,
            )
        ):
            return None
        return validation


def _revalidate_finish_voice_source_bundle(
    *,
    envelope: Any,
    consultation: Any,
    guarded_store: Any,
    source_bundle_binding: Any | None,
    source_ref_hash: str | None,
    source_bundle_validation: Any,
    now: str,
) -> Any | None:
    """Reopen the authoritative v2 row before any authenticator side effect."""

    return _generic_voice_evidence_revalidated_at_gate(
        envelope=envelope,
        consultation=consultation,
        guarded_store=guarded_store,
        source_bundle_binding=source_bundle_binding,
        source_ref_hash=source_ref_hash,
        source_bundle_validation=source_bundle_validation,
        now=now,
    )


def authorization_aggregation_recheck(
    *,
    envelope: Any,
    history: tuple[Any, ...],
) -> S7CeremonyServiceResult:
    """D23 aggregation gate before artifact minting."""

    from core.governance.operator_user_boundary import assess_aggregation_risk

    assessment = assess_aggregation_risk(
        current_envelope=envelope,
        history=history,
    )
    body = {
        "ok": assessment.decision in {"allow", "warn"},
        "decision": assessment.decision,
        "signals": assessment.signals,
        "derived_aggregation_group": assessment.derived_aggregation_group,
        "same_group_request_count": assessment.same_group_request_count,
        "repeated_refusal_count": assessment.repeated_refusal_count,
    }
    if assessment.decision in {"allow", "warn"}:
        return S7CeremonyServiceResult(body=body, status_code=200)
    return S7CeremonyServiceResult(
        body={**body, "error": "s7_aggregation_block"},
        status_code=409,
    )


def _consume_backup_registration_authorization(
    *,
    s7_execution_authorization: object | None,
) -> object | None:
    from core.governance import operator_user_boundary as s7

    if not isinstance(s7_execution_authorization, s7.S7ExecutionAuthorization):
        return None
    rendered = s7_execution_authorization.rendered
    action_matches = rendered.action == "register_backup_webauthn_credential"
    if not action_matches:
        return None
    action_params_hash = s7.canonical_hash(backup_registration_action_params())
    if s7_execution_authorization.action_params_hash != action_params_hash:
        return None
    if s7_execution_authorization.derived_work_class != "founder_credential_management":
        return None
    grant, _result = s7_execution_authorization.store.consume_for_execution(
        s7_execution_authorization.artifact_id,
        rendered=s7_execution_authorization.rendered,
        action_params_hash=action_params_hash,
        authority_context=s7_execution_authorization.authority_context,
        precondition_hash=s7_execution_authorization.precondition_hash,
        derived_work_class=s7_execution_authorization.derived_work_class,
        derived_aggregation_group=s7_execution_authorization.derived_aggregation_group,
        now=s7_execution_authorization.now,
        covenant_ceremony_evidence=s7_execution_authorization.covenant_ceremony_evidence,
    )
    return grant if isinstance(grant, s7.S7ExecutionGrant) else None


def _backup_distinct_device_confidence(
    *,
    store: Any,
    verified: dict[str, Any],
) -> str:
    """Classify backup distinctness from verifier/registry evidence.

    The code may not assert "confirmed_distinct" as a default. Confirmation
    requires a different credential plus verifier-supplied authenticator evidence
    that differs from the enabled primary. A non-empty backup AAGUID that differs
    from all enabled primary AAGUIDs is sufficient evidence even when browser
    attachment/transport hints are absent. Absent or matching AAGUIDs remain
    honest degraded states.
    """

    credential_ref = str(verified.get("credential_ref") or "")
    backup_aaguid = str(verified.get("aaguid") or "")
    primary_records = tuple(
        record
        for record in store.list_credentials()
        if record.enabled
        and record.credential_kind == "primary"
        and "bonded_user" in record.role_names
    )
    if not primary_records:
        return "unknown"
    if credential_ref and any(record.credential_ref == credential_ref for record in primary_records):
        return "same_device_override"
    if not backup_aaguid:
        return "unknown"
    primary_aaguids = tuple(str(record.aaguid or "") for record in primary_records)
    if any(not aaguid for aaguid in primary_aaguids):
        return "unknown"
    if backup_aaguid in primary_aaguids:
        return "same_device_override"
    # Direct attestation with a different AAGUID is stronger evidence than
    # optional browser attachment/transport hints, which some browsers omit.
    return "confirmed_distinct"


def _voice_seat_block(
    state: str,
    *,
    reason: str,
    envelope: Any | None = None,
    refusal_history_store: Any | None = None,
    rendered_text_hash: str | None = None,
    requester_ref: str | None = None,
    now: str | None = None,
) -> S7CeremonyServiceResult:
    refusal_record_id = None
    if refusal_history_store is not None:
        if envelope is None or rendered_text_hash is None or requester_ref is None or now is None:
            raise ValueError("s7_refusal_history_context_required")
        refusal_record_id = refusal_history_store.record_refusal_history(
            envelope=envelope,
            rendered_text_hash=rendered_text_hash,
            requester_ref=requester_ref,
            denial_reason=reason,
            created_at=now,
        )
    return S7CeremonyServiceResult(
        body={
            "ok": False,
            "error": "s7_voice_seat_unresolved",
            "maez_objection_state": state,
            "reason": reason,
            "refusal_record_id": refusal_record_id,
        },
        status_code=409,
    )


def _require_mapping(request_json: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(request_json, dict):
        raise ValueError("request_json")
    return request_json


def _require_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(key)
    return value


def _schema_invalid(detail: str) -> S7CeremonyServiceResult:
    return S7CeremonyServiceResult(
        body={"ok": False, "error": "s7_schema_invalid", "detail": detail},
        status_code=400,
    )


def _challenge_matches_rendered_d12(
    *,
    challenge: dict[str, Any],
    rendered_statement: Any,
    precondition_hash: str,
) -> bool:
    expected = {
        "request_id": str(rendered_statement.request_id),
        "request_envelope_hash": str(rendered_statement.request_envelope_hash),
        "rendered_text_hash": str(rendered_statement.rendered_text_hash),
        "action_params_hash": str(rendered_statement.action_params_hash),
        "precondition_hash": str(precondition_hash),
        "authority_context_hash": str(rendered_statement.authority_context_hash),
        "maez_voice_consultation_hash": str(rendered_statement.maez_voice_consultation_hash or ""),
        "derived_aggregation_group": str(rendered_statement.derived_aggregation_group),
        "nonce": str(rendered_statement.nonce),
    }
    for key, value in expected.items():
        actual = "" if challenge.get(key) is None else str(challenge.get(key))
        if actual != value:
            return False
    return True


def _r11_challenge_projection_hash(
    *,
    rendered_statement: Any,
    precondition_hash: str,
    consultation_exemption: Any | None,
    durable_cutover_selection: Any | None,
) -> str | None:
    """Derive the R11 value stored beside the authenticator challenge.

    The browser signs ``challenge_b64``.  The server's durable challenge row
    binds those random bytes to D12's rendered-statement fields and, for R11,
    to the exact typed-absence projection.  Finish re-derives this value from
    the presented exemption before authentication, so an assertion begun for
    one absence cannot authorize another.
    """

    from core.governance import operator_user_boundary as s7

    if consultation_exemption is None:
        if (
            getattr(rendered_statement, "maez_consulted_state", None)
            == s7.MAEZ_CONSULTED_NOT_PERFORMED_R11
        ):
            raise ValueError("s7_consultation_exemption_invalid")
        return None

    from core.governance import s7_consultation_exemption as r11

    derived_action_params_hash = r11._action_params_hash_from_durable_selection(
        durable_cutover_selection
    )
    expected_envelope = r11._envelope_from_durable_selection(
        durable_cutover_selection
    )
    expected_envelope_hash = (
        None
        if expected_envelope is None
        else s7.work_request_envelope_hash(expected_envelope)
    )
    expected_rendered_fields = (
        ("request_id", getattr(expected_envelope, "request_id", None)),
        ("action", getattr(expected_envelope, "action", None)),
        (
            "derived_work_class",
            getattr(expected_envelope, "derived_work_class", None),
        ),
        (
            "proposed_change_class",
            getattr(expected_envelope, "proposed_change_class", None),
        ),
        (
            "predicted_effect_class",
            getattr(expected_envelope, "predicted_effect_class", None),
        ),
        (
            "rollback_path_class",
            getattr(expected_envelope, "rollback_path_class", None),
        ),
        (
            "derived_aggregation_group",
            getattr(expected_envelope, "derived_aggregation_group", None),
        ),
        ("expires_at", getattr(expected_envelope, "expires_at", None)),
    )

    if (
        type(consultation_exemption) is not r11.S7ConsultationExemption
        or getattr(consultation_exemption, "_token_verified", False) is not True
        or consultation_exemption.action != r11.R11_EXEMPT_ACTION
        or consultation_exemption.action
        != getattr(rendered_statement, "action", None)
        or consultation_exemption.request_envelope_hash
        != getattr(rendered_statement, "request_envelope_hash", None)
        or consultation_exemption.request_envelope_hash
        != expected_envelope_hash
        or consultation_exemption.action_params_hash
        != getattr(rendered_statement, "action_params_hash", None)
        or consultation_exemption.action_params_hash
        != derived_action_params_hash
        or precondition_hash != getattr(expected_envelope, "precondition_hash", None)
        or any(
            getattr(rendered_statement, field, None) != expected
            for field, expected in expected_rendered_fields
        )
    ):
        raise ValueError("s7_consultation_exemption_invalid")
    if (
        getattr(rendered_statement, "maez_consulted_state", None)
        != s7.MAEZ_CONSULTED_NOT_PERFORMED_R11
        or rendered_statement.maez_voice_consultation_hash is not None
        or getattr(rendered_statement, "maez_objection_state", None) != "none"
    ):
        raise ValueError("s7_signed_statement_contradicts_exemption")
    return s7.canonical_hash(consultation_exemption.projection())


def _d12_binding_mismatch() -> S7CeremonyServiceResult:
    return S7CeremonyServiceResult(
        body={"ok": False, "error": "s7_d12_binding_mismatch"},
        status_code=409,
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _credential_descriptor(store: Any, credential_ref: str) -> dict[str, Any]:
    credential = store.get_credential(credential_ref)
    transports = tuple(getattr(credential, "transports", ()) or ())
    return {
        "id": credential_ref,
        "type": "public-key",
        "transports": list(transports or ("usb", "nfc")),
    }


def _public_key_credential_params() -> tuple[dict[str, int | str], ...]:
    return (
        {"type": "public-key", "alg": -7},
        {"type": "public-key", "alg": -257},
    )


def _add_minutes(value: str, minutes: int) -> str:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(minutes=minutes)).isoformat()
