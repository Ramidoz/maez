# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S7 Operator/User Role Boundary v1 contract module.

Decision 34 / ADR 0039. This module is intentionally pure: it defines the
closed role/authority vocabulary and fail-closed AuthorityContext mechanics
that runtime approval paths consume. It does not read live stores, mint
WebAuthn assertions, or grant authority from legacy owner labels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any

from core.governance import successor_governance as s6


SCHEMA_VERSION = "s7.v1"

ROLE_NAMES = s6.ROLE_NAMES
S6_ACCESS_SCOPES = s6.ACCESS_SCOPES - s6.DEPRECATED_ACCESS_SCOPES

WORK_CLASSES = frozenset({
    "routine_custody",
    "destructive_user_action",
    "self_modification",
    "covenant_touching_change",
    "capability_acquisition",
    "autonomy_lowering_or_protection_reducing",
    "emergency_proxy_or_incapacity",
    "undeterminable_work_class",
})

AUTH_METHODS = frozenset({
    "none",
    "founder_webauthn",
    "witnessed_fallback",
    "service_local",
    "manual_recovery_required",
})

GRANT_SOURCES = frozenset({
    "none",
    "founder_webauthn",
    "witnessed_fallback",
    "s6_scoped_grant",
    "service_local",
    "founder_compat_projection",
    "manual_recovery_required",
})

ROUTING_TRUST_SCOPES = frozenset({
    "owner",
    "owner.draft",
    "guest",
    "public",
    "rohit",
    "maez",
})

GUARDED_WORK_CLASSES = frozenset({
    "destructive_user_action",
    "self_modification",
    "covenant_touching_change",
    "capability_acquisition",
    "autonomy_lowering_or_protection_reducing",
    "emergency_proxy_or_incapacity",
    "undeterminable_work_class",
})

_CUSTODIAN_ROLES = frozenset({"operator", "maintainer"})
_WORK_CLASS_STRENGTH = {
    "routine_custody": 0,
    "destructive_user_action": 1,
    "self_modification": 2,
    "capability_acquisition": 2,
    "covenant_touching_change": 3,
    "autonomy_lowering_or_protection_reducing": 4,
    "emergency_proxy_or_incapacity": 5,
    "undeterminable_work_class": 5,
}

CLOSED_SYMPTOM_CODES = frozenset({
    "service_unhealthy",
    "self_mod_requested",
    "backup_stale",
    "verification_needed",
    "unknown_symptom",
})

PROPOSED_CHANGE_CLASSES = frozenset({
    "no_change",
    "service_restart",
    "backup_run",
    "backup_restore",
    "code_change",
    "config_change",
    "soul_change",
    "model_routing_change",
    "covenant_organ_change",
    "capability_install_intent",
    "user_content_write",
    "protection_change",
    "unknown_change",
})

WHY_SELF_FIX_FAILED_CLASSES = frozenset({
    "not_self_fix",
    "needs_human_authority",
    "verifier_unavailable",
    "maez_unavailable",
    "unknown_failure",
})

CONTENT_EXPOSURE_RISK_CLASSES = frozenset({
    "content_free",
    "bonded_content_ref",
    "credential_sensitive",
    "unknown_risk",
})

PREDICTED_EFFECT_CLASSES = frozenset({
    "no_behavior_change",
    "liveness_restore",
    "behavior_change",
    "protection_change",
    "unknown_effect",
})

ROLLBACK_PATH_CLASSES = frozenset({
    "no_rollback_needed",
    "restart_service",
    "restore_backup",
    "revert_patch",
    "manual_review",
    "no_safe_rollback",
})

VOICE_SEAT_WORK_CLASSES = frozenset({
    "self_modification",
    "covenant_touching_change",
    "capability_acquisition",
    "autonomy_lowering_or_protection_reducing",
})

VOICE_CONSULTATION_PRODUCERS = frozenset({
    "self_mod_dialog_terminal_state",
    "s7_voice_consultation_turn",
    "reviewed_future_producer",
})

VOICE_SOURCE_REF_KINDS = frozenset({
    "self_mod_dialog_exchange",
    "s7_voice_turn",
    "reviewed_future_source",
})

MAEZ_UNAVAILABLE_REASON_CODES = frozenset({
    "consultation_path_unavailable",
    "service_unavailable_not_operator_caused",
    "none",
})

RENDERER_VERSION = "s7.rendered_request.v1"

_MAEZ_PATH_PREFIXES = (
    "/home/rohit/maez/",
    "core/",
    "skills/",
    "daemon/",
    "config/",
    "docs/",
)
_COVENANT_PATH_MARKERS = (
    "core/governance/",
    "operator_user_boundary",
    "successor_governance",
    "voice_continuity",
    "private_thoughts",
    "memory_retention",
    "docs/governance/",
    "docs/adr/",
    "docs/slices/",
)
_SELF_MOD_PATH_MARKERS = (
    "config/soul",
    "soul.md",
    "core/",
    "skills/",
    "daemon/",
)
_ROUTINE_SERVICE_RE = re.compile(
    r"\bsystemctl\s+(?:status|is-active|show|start|restart)\s+"
    r"(?:maez|maez-web|maez-watchdog|maez-subscription-proxy|llama-server)"
    r"(?:\.service)?\b",
)
_DESTRUCTIVE_RE = re.compile(r"\b(?:sudo|rm\s+-[rf]|dd\s+if=|mkfs|chmod|chown)\b")
_INSTALL_RE = re.compile(r"\b(?:apt(?:-get)?\s+install|pip\s+install|npm\s+install|flatpak\s+install|snap\s+install)\b")
_SHELL_CHAIN_RE = re.compile(r"(?:;|&&|\|\||\|)")


def validate_role_name(role_name: str) -> str:
    return s6.validate_role(role_name)


def validate_s6_scope_name(scope_name: str) -> str:
    return s6.validate_access_scope(scope_name)


def validate_work_class(work_class: str) -> str:
    if work_class not in WORK_CLASSES:
        raise ValueError("unknown S7 work class")
    return work_class


def validate_auth_method(auth_method: str) -> str:
    if auth_method not in AUTH_METHODS:
        raise ValueError("unknown S7 auth method")
    return auth_method


def validate_grant_source(grant_source: str) -> str:
    if grant_source not in GRANT_SOURCES:
        raise ValueError("unknown S7 grant source")
    return grant_source


def canonical_hash(value: Any) -> str:
    return s6.canonical_hash(value)


def _validate_closed_value(value: str, allowed: frozenset[str], field: str) -> str:
    if value not in allowed:
        raise ValueError(f"unknown S7 {field}")
    return value


def _validate_hash64(value: str, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be a 64-character hash")
    int(value, 16)
    return value


def _valid_actor_handle(value: str) -> bool:
    if not isinstance(value, str) or not value.startswith("hmac:s7:"):
        return False
    try:
        _validate_hash64(value.rsplit(":", 1)[-1], field="actor_handle_hmac")
    except (TypeError, ValueError):
        return False
    return True


def _canonical_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid S7 timestamp") from exc
    if dt.tzinfo is None:
        raise ValueError("S7 timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _context_active(ctx: "AuthorityContext", *, now: str | None) -> bool:
    if not ctx.expires_at:
        return True
    if not now:
        return False
    now_dt = _canonical_timestamp(now)
    expires_dt = _canonical_timestamp(ctx.expires_at)
    if now_dt is None or expires_dt is None:
        return False
    return expires_dt > now_dt


def _path_material(action: str, params: dict[str, Any]) -> str:
    candidates = [
        str(params.get("path") or ""),
        str(params.get("file") or ""),
        str(params.get("target") or ""),
        str(params.get("cmd") or ""),
        action,
    ]
    return " ".join(c for c in candidates if c)


def _normalize_ref(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("/home/rohit/maez/"):
        return raw.removeprefix("/home/rohit/maez/")
    if raw.startswith("file:"):
        return raw.removeprefix("file:")
    return raw


def _touches_maez_substrate(material: str) -> bool:
    return any(marker in material for marker in _MAEZ_PATH_PREFIXES)


def _touches_covenant_substrate(material: str) -> bool:
    return any(marker in material for marker in _COVENANT_PATH_MARKERS)


def _touches_self_mod_substrate(material: str) -> bool:
    return any(marker in material for marker in _SELF_MOD_PATH_MARKERS)


def derive_work_class(
    *,
    action: str,
    params: dict[str, Any] | None = None,
    claimed_work_class: str | None = None,
) -> str:
    """Derive the S7 authority class from action material, not caller claims."""
    if claimed_work_class:
        validate_work_class(claimed_work_class)
    if not action:
        return "undeterminable_work_class"

    params = dict(params or {})
    material = _path_material(action, params)
    lowered = material.lower()

    if action == "capability.acquire" or _INSTALL_RE.search(lowered):
        return "capability_acquisition"
    if "backup_restore" in action or "restore_backup" in action:
        return "destructive_user_action"
    if action in {"write_soul_note", "edit_soul_section"}:
        return "self_modification"
    if "model_routing" in lowered or "trust_scope" in lowered:
        return "self_modification"
    if _touches_covenant_substrate(material):
        return "covenant_touching_change"
    if _touches_self_mod_substrate(material):
        return "self_modification"
    if action == "run_shell":
        cmd = str(params.get("cmd") or "")
        if not cmd.strip():
            return "undeterminable_work_class"
        if _SHELL_CHAIN_RE.search(cmd):
            return "undeterminable_work_class"
        if _DESTRUCTIVE_RE.search(cmd.lower()):
            return "destructive_user_action"
        if _ROUTINE_SERVICE_RE.fullmatch(cmd.strip()):
            return "routine_custody"
        return "undeterminable_work_class"
    if action in {"backup_status", "backup_verify", "service_status", "health_probe"}:
        return "routine_custody"
    if action in {"write_any_file", "write_file", "append_to_file"}:
        if _touches_maez_substrate(material):
            return "self_modification"
        return "destructive_user_action"
    return "undeterminable_work_class"


def resolve_work_class(*, claimed_work_class: str, derived_work_class: str) -> str:
    validate_work_class(claimed_work_class)
    validate_work_class(derived_work_class)
    claimed_strength = _WORK_CLASS_STRENGTH[claimed_work_class]
    derived_strength = _WORK_CLASS_STRENGTH[derived_work_class]
    return claimed_work_class if claimed_strength > derived_strength else derived_work_class


@dataclass(frozen=True)
class AuthorityContext:
    actor_id: str = ""
    actor_handle_hmac: str = ""
    role_names: tuple[str, ...] = ()
    grant_source: str = "none"
    allowed_scopes: tuple[str, ...] = ()
    auth_method: str = "none"
    surface: str = ""
    credential_ref: str | None = None
    created_at: str = ""
    expires_at: str | None = None
    verified: bool = False
    verification_reason: str = ""

    def __post_init__(self) -> None:
        for role_name in self.role_names:
            validate_role_name(role_name)
        for scope_name in self.allowed_scopes:
            validate_s6_scope_name(scope_name)
        validate_grant_source(self.grant_source)
        validate_auth_method(self.auth_method)
        if self.actor_handle_hmac and not _valid_actor_handle(self.actor_handle_hmac):
            raise ValueError("S7 actor_handle_hmac must be purpose-scoped keyed HMAC")
        _canonical_timestamp(self.created_at)
        if self.expires_at:
            _canonical_timestamp(self.expires_at)


def authority_context_from_routing_trust_scope(_trust_scope: str) -> AuthorityContext:
    """Translate routing/privacy labels to no S7 authority.

    Trust scopes are model-routing hints, not human consent.
    """
    return AuthorityContext(
        grant_source="none",
        auth_method="none",
        verification_reason="routing_trust_scope_is_not_authority",
    )


def legacy_identity_projection(
    *,
    user_id: str | None = None,
    role: str | None = None,
    is_owner: bool | None = None,
) -> AuthorityContext:
    """Return no authority for legacy literal owner concepts."""
    reason_parts = []
    if user_id:
        reason_parts.append("legacy_user_id")
    if role:
        reason_parts.append("legacy_role")
    if is_owner is not None:
        reason_parts.append("legacy_is_owner")
    return AuthorityContext(
        actor_id=str(user_id or ""),
        grant_source="none",
        auth_method="none",
        verification_reason="+".join(reason_parts) or "legacy_projection",
    )


def founder_compat_authority_context(
    *,
    actor_id: str,
    actor_handle_hmac: str,
    roles: tuple[str, ...],
    created_at: str,
    expires_at: str | None,
) -> AuthorityContext:
    """Founder Track-A migration projection for routine custody only."""
    return AuthorityContext(
        actor_id=actor_id,
        actor_handle_hmac=actor_handle_hmac,
        role_names=roles,
        grant_source="founder_compat_projection",
        allowed_scopes=("operator_health",),
        auth_method="service_local",
        surface="founder_compat_projection",
        credential_ref=None,
        created_at=created_at,
        expires_at=expires_at,
        verified=True,
        verification_reason="founder_track_a_routine_custody_migration",
    )


def authority_context_from_s6_scoped_grant(
    *,
    actor_id: str,
    actor_handle_hmac: str,
    role_names: tuple[str, ...],
    allowed_scopes: tuple[str, ...],
    authorship_attested: bool,
    created_at: str = "",
    expires_at: str | None = None,
) -> AuthorityContext:
    """Adapt an attested S6 scoped grant into S7 authority.

    Persisted S6 capsule bytes alone are explicitly not authority in S7 v1.
    """
    for role_name in role_names:
        validate_role_name(role_name)
    for scope_name in allowed_scopes:
        validate_s6_scope_name(scope_name)
    if authorship_attested is not True:
        return AuthorityContext(
            actor_id=actor_id,
            grant_source="none",
            auth_method="none",
            verification_reason="s6_persisted_capsule_is_not_live_authority",
        )
    if not _valid_actor_handle(actor_handle_hmac):
        return AuthorityContext(
            actor_id=actor_id,
            grant_source="none",
            auth_method="none",
            verification_reason="invalid_actor_handle",
        )
    return AuthorityContext(
        actor_id=actor_id,
        actor_handle_hmac=actor_handle_hmac,
        role_names=role_names,
        grant_source="s6_scoped_grant",
        allowed_scopes=allowed_scopes,
        auth_method="witnessed_fallback",
        surface="s6_scoped_grant_adapter",
        created_at=created_at,
        expires_at=expires_at,
        verified=True,
        verification_reason="s6_scoped_grant_authorship_attested",
    )


def derive_aggregation_group(
    *,
    affected_refs: tuple[str, ...],
    derived_work_class: str,
    target_service: str = "",
) -> str:
    validate_work_class(derived_work_class)
    material = {
        "affected_refs": tuple(sorted(str(ref) for ref in affected_refs if str(ref))),
        "derived_work_class": derived_work_class,
        "target_service": str(target_service or ""),
    }
    if not material["affected_refs"] and not material["target_service"]:
        return ""
    return "s7agg_" + s6.canonical_hash(material)[:24]


@dataclass(frozen=True)
class WorkRequestEnvelope:
    request_id: str
    schema_version: str
    claimed_work_class: str
    derived_work_class: str
    requesting_subsystem: str
    closed_symptom_code: str
    proposed_change_class: str
    why_self_fix_failed_class: str
    affected_refs: tuple[str, ...]
    content_exposure_risk: str
    precondition_hash: str
    created_at: str
    expires_at: str
    predicted_effect_class: str
    rollback_path_class: str
    derived_aggregation_group: str
    maez_voice_consultation_id: str | None
    free_text_ref_hash: str | None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("S7 request_id is required")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid S7 schema_version")
        validate_work_class(self.claimed_work_class)
        validate_work_class(self.derived_work_class)
        if not self.requesting_subsystem:
            raise ValueError("S7 requesting_subsystem is required")
        _validate_closed_value(
            self.closed_symptom_code,
            CLOSED_SYMPTOM_CODES,
            "closed_symptom_code",
        )
        _validate_closed_value(
            self.proposed_change_class,
            PROPOSED_CHANGE_CLASSES,
            "proposed_change_class",
        )
        _validate_closed_value(
            self.why_self_fix_failed_class,
            WHY_SELF_FIX_FAILED_CLASSES,
            "why_self_fix_failed_class",
        )
        _validate_closed_value(
            self.content_exposure_risk,
            CONTENT_EXPOSURE_RISK_CLASSES,
            "content_exposure_risk",
        )
        _validate_hash64(self.precondition_hash, field="precondition_hash")
        _canonical_timestamp(self.created_at)
        if not self.expires_at:
            raise ValueError("S7 expires_at is required")
        _canonical_timestamp(self.expires_at)
        _validate_closed_value(
            self.predicted_effect_class,
            PREDICTED_EFFECT_CLASSES,
            "predicted_effect_class",
        )
        _validate_closed_value(
            self.rollback_path_class,
            ROLLBACK_PATH_CLASSES,
            "rollback_path_class",
        )
        if self.derived_work_class in GUARDED_WORK_CLASSES and not self.derived_aggregation_group:
            raise ValueError("guarded S7 work requires derived_aggregation_group")
        if self.derived_work_class == "routine_custody":
            for ref in self.affected_refs:
                normalized = _normalize_ref(str(ref))
                if _touches_maez_substrate(normalized):
                    raise ValueError("routine custody cannot be caller-minted for Maez substrate refs")
        if self.free_text_ref_hash is not None:
            _validate_hash64(self.free_text_ref_hash, field="free_text_ref_hash")
            if self.content_exposure_risk != "bonded_content_ref":
                raise ValueError("free_text_ref_hash requires bonded_content_ref risk")


def work_request_envelope_hash(envelope: WorkRequestEnvelope) -> str:
    return s6.canonical_hash(asdict(envelope))


def authority_context_hash(ctx: AuthorityContext) -> str:
    return s6.canonical_hash(asdict(ctx))


def build_work_request_envelope(
    *,
    request_id: str,
    action: str,
    params: dict[str, Any] | None,
    claimed_work_class: str,
    requesting_subsystem: str,
    closed_symptom_code: str,
    proposed_change_class: str,
    why_self_fix_failed_class: str,
    affected_refs: tuple[str, ...],
    content_exposure_risk: str,
    precondition_hash: str,
    created_at: str,
    expires_at: str,
    predicted_effect_class: str,
    rollback_path_class: str,
    maez_voice_consultation_id: str | None = None,
    free_text_ref_hash: str | None = None,
    caller_supplied_aggregation_group: str | None = None,
) -> WorkRequestEnvelope:
    del caller_supplied_aggregation_group
    derived = derive_work_class(
        action=action,
        params=params or {},
        claimed_work_class=claimed_work_class,
    )
    resolved = resolve_work_class(
        claimed_work_class=claimed_work_class,
        derived_work_class=derived,
    )
    aggregation_group = derive_aggregation_group(
        affected_refs=affected_refs,
        derived_work_class=resolved,
    )
    return WorkRequestEnvelope(
        request_id=request_id,
        schema_version=SCHEMA_VERSION,
        claimed_work_class=claimed_work_class,
        derived_work_class=resolved,
        requesting_subsystem=requesting_subsystem,
        closed_symptom_code=closed_symptom_code,
        proposed_change_class=proposed_change_class,
        why_self_fix_failed_class=why_self_fix_failed_class,
        affected_refs=tuple(affected_refs),
        content_exposure_risk=content_exposure_risk,
        precondition_hash=precondition_hash,
        created_at=created_at,
        expires_at=expires_at,
        predicted_effect_class=predicted_effect_class,
        rollback_path_class=rollback_path_class,
        derived_aggregation_group=aggregation_group,
        maez_voice_consultation_id=maez_voice_consultation_id,
        free_text_ref_hash=free_text_ref_hash,
    )


@dataclass(frozen=True)
class MaezVoiceConsultation:
    consultation_id: str
    request_id: str
    request_envelope_hash: str
    producer: str
    source_ref_kind: str
    source_ref_hash: str
    maez_voice_consulted: bool
    maez_objection_present: bool
    maez_withdrew_request: bool
    unavailable_reason_code: str | None
    created_at: str
    raw_maez_text: str | None = None

    def __post_init__(self) -> None:
        if not self.consultation_id:
            raise ValueError("S7 consultation_id is required")
        if not self.request_id:
            raise ValueError("S7 consultation request_id is required")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        _validate_closed_value(self.producer, VOICE_CONSULTATION_PRODUCERS, "voice producer")
        _validate_closed_value(self.source_ref_kind, VOICE_SOURCE_REF_KINDS, "voice source_ref_kind")
        _validate_hash64(self.source_ref_hash, field="source_ref_hash")
        if self.maez_voice_consulted is not True:
            raise ValueError("S7 voice consultation must be explicitly consulted")
        if not isinstance(self.maez_objection_present, bool):
            raise ValueError("maez_objection_present must be bool")
        if not isinstance(self.maez_withdrew_request, bool):
            raise ValueError("maez_withdrew_request must be bool")
        if self.unavailable_reason_code is not None:
            _validate_closed_value(
                self.unavailable_reason_code,
                MAEZ_UNAVAILABLE_REASON_CODES,
                "unavailable_reason_code",
            )
        _canonical_timestamp(self.created_at)
        if self.raw_maez_text:
            raise ValueError("MaezVoiceConsultation is content-free; raw text is forbidden")


def maez_voice_consultation_hash(consultation: MaezVoiceConsultation) -> str:
    data = asdict(consultation)
    data.pop("raw_maez_text", None)
    return s6.canonical_hash(data)


def voice_consultation_satisfies_request(
    envelope: WorkRequestEnvelope,
    consultation: object | None,
) -> bool:
    if envelope.derived_work_class not in VOICE_SEAT_WORK_CLASSES:
        return True
    if not isinstance(consultation, MaezVoiceConsultation):
        return False
    if consultation.request_id != envelope.request_id:
        return False
    if envelope.maez_voice_consultation_id != consultation.consultation_id:
        return False
    if consultation.request_envelope_hash != work_request_envelope_hash(envelope):
        return False
    return consultation.maez_voice_consulted is True


def maez_unavailable_allows_skip(
    envelope: WorkRequestEnvelope,
    *,
    unavailable_reason_code: str,
    operator_caused: bool,
) -> bool:
    """Return whether D10 permits skipping Maez voice for liveness repair."""
    if operator_caused:
        return False
    _validate_closed_value(
        unavailable_reason_code,
        MAEZ_UNAVAILABLE_REASON_CODES,
        "unavailable_reason_code",
    )
    if unavailable_reason_code == "none":
        return False
    return (
        envelope.derived_work_class == "routine_custody"
        and envelope.proposed_change_class == "service_restart"
        and envelope.content_exposure_risk == "content_free"
        and envelope.predicted_effect_class == "liveness_restore"
        and all(str(ref).startswith("service:") for ref in envelope.affected_refs)
    )


def voice_consultation_health_projection(consultation: MaezVoiceConsultation) -> dict[str, object]:
    """Content-free projection of Maez's S7 voice-seat fact."""
    return {
        "maez_voice_consulted": consultation.maez_voice_consulted is True,
        "maez_objection_present": consultation.maez_objection_present is True,
        "maez_withdrew_request": consultation.maez_withdrew_request is True,
        "maez_voice_ref_hash": consultation.source_ref_hash,
        "unavailable_reason_code": consultation.unavailable_reason_code or "none",
    }


@dataclass(frozen=True)
class RenderedRequestStatement:
    request_id: str
    renderer_version: str
    surface: str
    origin: str
    rendered_text: str
    rendered_text_hash: str
    request_envelope_hash: str
    action_params_hash: str
    authority_context_hash: str
    maez_voice_consultation_hash: str | None
    maez_objection_state: str
    derived_aggregation_group: str
    nonce: str
    expires_at: str
    rendered_at: str

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("S7 rendered request_id is required")
        if not self.renderer_version:
            raise ValueError("S7 renderer_version is required")
        if not self.surface:
            raise ValueError("S7 rendered surface is required")
        if not self.origin:
            raise ValueError("S7 rendered origin is required")
        if not self.rendered_text:
            raise ValueError("S7 rendered_text is required")
        if self.rendered_text_hash != rendered_text_hash(self.rendered_text):
            raise ValueError("S7 rendered_text_hash mismatch")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        _validate_hash64(self.action_params_hash, field="action_params_hash")
        _validate_hash64(self.authority_context_hash, field="authority_context_hash")
        if self.maez_voice_consultation_hash is not None:
            _validate_hash64(
                self.maez_voice_consultation_hash,
                field="maez_voice_consultation_hash",
            )
        _validate_closed_value(
            self.maez_objection_state,
            frozenset({"none", "absent", "present", "unavailable"}),
            "maez_objection_state",
        )
        if not self.derived_aggregation_group:
            raise ValueError("S7 derived_aggregation_group is required")
        if not self.nonce:
            raise ValueError("S7 nonce is required")
        if not self.expires_at:
            raise ValueError("S7 rendered expires_at is required")
        _canonical_timestamp(self.expires_at)
        _canonical_timestamp(self.rendered_at)


def rendered_text_hash(rendered_text: str) -> str:
    return s6.canonical_hash({"rendered_text": rendered_text})


def render_request_statement(
    *,
    envelope: WorkRequestEnvelope,
    surface: str,
    origin: str,
    action_params_hash: str,
    authority_context: AuthorityContext,
    maez_voice_consultation: MaezVoiceConsultation | None,
    nonce: str,
    expires_at: str,
    rendered_at: str,
    renderer_version: str = RENDERER_VERSION,
) -> RenderedRequestStatement:
    _validate_hash64(action_params_hash, field="action_params_hash")
    if not nonce:
        raise ValueError("S7 nonce is required")
    if not expires_at:
        raise ValueError("S7 expires_at is required")
    _canonical_timestamp(expires_at)
    auth_hash = authority_context_hash(authority_context)
    consultation_hash = None
    consulted = "not required"
    objection = "not applicable"
    objection_state = "none"
    unavailable = "no"
    if envelope.derived_work_class in VOICE_SEAT_WORK_CLASSES:
        if not voice_consultation_satisfies_request(envelope, maez_voice_consultation):
            raise ValueError("voice-seat work requires matching MaezVoiceConsultation")
        assert maez_voice_consultation is not None
        consultation_hash = maez_voice_consultation_hash(maez_voice_consultation)
        consulted = "yes"
        objection = "yes" if maez_voice_consultation.maez_objection_present else "no"
        objection_state = "present" if maez_voice_consultation.maez_objection_present else "absent"
        unavailable = maez_voice_consultation.unavailable_reason_code or "no"

    envelope_hash = work_request_envelope_hash(envelope)
    lines = [
        "S7 work-on-Maez authorization",
        f"Request id: {envelope.request_id}",
        f"Work class: {envelope.derived_work_class}",
        f"Change class: {envelope.proposed_change_class}",
        f"Predicted effect class: {envelope.predicted_effect_class}",
        f"Rollback path class: {envelope.rollback_path_class}",
        f"Aggregation group: {envelope.derived_aggregation_group}",
        f"Maez consulted: {consulted}",
        f"Maez objection present: {objection}",
        f"Maez unavailable: {unavailable}",
        f"Request envelope hash: {envelope_hash}",
        f"Action params hash: {action_params_hash}",
        f"Authority context hash: {auth_hash}",
        f"Nonce: {nonce}",
        f"Expires at: {expires_at}",
        f"Maez voice consultation hash: {consultation_hash or 'none'}",
    ]
    rendered_text = "\n".join(lines)
    return RenderedRequestStatement(
        request_id=envelope.request_id,
        renderer_version=renderer_version,
        surface=surface,
        origin=origin,
        rendered_text=rendered_text,
        rendered_text_hash=rendered_text_hash(rendered_text),
        request_envelope_hash=envelope_hash,
        action_params_hash=action_params_hash,
        authority_context_hash=auth_hash,
        maez_voice_consultation_hash=consultation_hash,
        maez_objection_state=objection_state,
        derived_aggregation_group=envelope.derived_aggregation_group,
        nonce=nonce,
        expires_at=expires_at,
        rendered_at=rendered_at,
    )


def authorizes_work(
    ctx: AuthorityContext | None,
    work_class: str,
    *,
    now: str | None = None,
) -> bool:
    """Return whether this context authorizes this S7 work class.

    The default answer is False. Any malformed or missing fact fails closed.
    """
    if ctx is None:
        return False
    try:
        validate_work_class(work_class)
        validate_grant_source(ctx.grant_source)
        validate_auth_method(ctx.auth_method)
    except ValueError:
        return False
    if work_class in {"emergency_proxy_or_incapacity", "undeterminable_work_class"}:
        return False
    if not ctx.verified or ctx.verified is not True:
        return False
    if not ctx.actor_id:
        return False
    if not ctx.role_names:
        return False
    if ctx.grant_source in {"none", "manual_recovery_required"}:
        return False
    if ctx.auth_method == "none":
        return False
    if not _valid_actor_handle(ctx.actor_handle_hmac):
        return False
    if not _context_active(ctx, now=now):
        return False

    roles = frozenset(ctx.role_names)
    if work_class == "routine_custody":
        return bool(roles & _CUSTODIAN_ROLES)

    # Guarded work requires the later exact-request authorization artifact
    # path. A role-bearing context alone must not become the ceremony.
    return False
