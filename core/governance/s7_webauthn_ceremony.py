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

from core.governance.operator_user_boundary import live_webauthn_ceremony_enabled
from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore
from core.governance.s7_webauthn_verifier import S7ProductionWebAuthnVerifier


@dataclass(frozen=True)
class S7CeremonyServiceResult:
    body: dict[str, Any]
    status_code: int


StoreFactory = Callable[[], S7WebAuthnBootstrapStore]


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
            return S7CeremonyServiceResult(
                body={
                    "ok": False,
                    "error": "s7_authorization_required",
                    "registration_class": "backup",
                    "message": (
                        "Backup registration requires a live founder authorization "
                        "artifact; S7.1 has not wired that producer yet."
                    ),
                },
                status_code=403,
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
                    "user": {"name": "founder", "displayName": "Founder"},
                    "challenge": challenge["challenge_b64"],
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
            challenge_id = _require_text(request, "challenge_id")
            intent_id = _require_text(request, "bootstrap_intent_id")
            raw_token = _require_text(request, "bootstrap_token")
            session_binding = _require_text(request, "session_binding")
            registration_response = request["registration_response"]
            if not isinstance(registration_response, dict):
                raise ValueError("registration_response")
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
        if not store.bootstrap_intent_valid(
            intent_id=intent_id,
            raw_token=raw_token,
            now=now,
        ):
            return S7CeremonyServiceResult(
                body={"ok": False, "error": "s7_bootstrap_invalid"},
                status_code=401,
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
    return S7CeremonyServiceResult(
        body={
            "ok": True,
            "maez_objection_state": "absent",
            "maez_voice_consultation_id": maez_voice_consultation.consultation_id,
        },
        status_code=200,
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


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _add_minutes(value: str, minutes: int) -> str:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(minutes=minutes)).isoformat()
