# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S7 Operator/User Role Boundary v1 contract module.

Decision 34 / ADR 0039. This module is intentionally pure: it defines the
closed role/authority vocabulary and fail-closed AuthorityContext mechanics
that runtime approval paths consume. Its D20 helpers read only closed
content-free projections from named mixed stores; they do not expose raw rows,
mint WebAuthn assertions, or grant authority from legacy owner labels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import re
import sqlite3
from pathlib import Path
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

MAINTENANCE_RECORD_CLASSES = frozenset({
    "self_remaking_history",
})

MAINTENANCE_CORPORA = frozenset({
    "ordinary_recall",
    "m1_lived_episode",
    "trf",
    "s5_voice_continuity",
    "self_remaking_history",
})

BIOGRAPHY_CORPORA = frozenset({
    "ordinary_recall",
    "m1_lived_episode",
    "trf",
    "s5_voice_continuity",
})

SELF_REMAKING_SOURCE_REF_KINDS = frozenset({
    "self_mod_dialog",
    "s7_maintenance_ceremony",
})

OPERATOR_HEALTH_MODES = frozenset({
    "ready",
    "degraded",
    "manual_recovery_required",
    "track_b_confidentiality_not_ready",
    "operator_unavailable_recovery_not_implemented",
    "unavailable",
})

OPERATOR_SERVICE_MODES = frozenset({
    "running",
    "degraded",
    "stopped",
    "unavailable",
})

OPERATOR_FRESHNESS_CLASSES = frozenset({
    "fresh",
    "stale",
    "unavailable",
    "manual_recovery_required",
})

OPERATOR_RED_GATE_MODES = frozenset({
    "track_b_confidentiality_not_ready",
    "operator_unavailable_recovery_not_implemented",
    "backup_restore_confidentiality_not_ready",
    "manual_recovery_required",
})

OPERATOR_QUEUE_COUNT_KEYS = frozenset({
    "total",
    "open",
    "blocked",
    "expired",
})

CREDENTIAL_RECOVERY_MODES = frozenset({
    "ready",
    "degraded",
    "manual_recovery_required",
})

MIXED_STORE_KINDS = frozenset({
    "actions_log",
    "covenant_log",
    "audit_log_db",
    "pending_cards_db",
    "self_mod_dialogs_db",
    "decision22_backup_artifact",
})

MIXED_STORE_PROJECTION_MODES = frozenset({
    "content_free_counts",
    "unavailable",
})

MIXED_STORE_CONTENT_AUTHORITIES = frozenset({
    "not_granted",
})

_EXPECTED_COVENANT_LOG_SUFFIX = ("logs", "covenant.log")
_EXPECTED_AUDIT_LOG_DB_SUFFIX = ("memory", "audit_log.db")
_EXPECTED_LAST_BACKUP_SUFFIX = ("logs", "last_backup.json")
_EXPECTED_SERVICE_MAINTENANCE_AUDIT_SUFFIX = ("logs", "service_maintenance_audit.jsonl")
_WITNESSED_FALLBACK_ID_RE = re.compile(r"^s7fallback_[0-9a-f]{32,64}$")

BACKUP_OPERATIONS = frozenset({
    "backup_run",
    "backup_verify",
    "backup_rotate",
    "backup_restore",
})

_ROUTINE_BACKUP_OPERATIONS = frozenset({
    "backup_run",
    "backup_verify",
    "backup_rotate",
})

BACKUP_STATUS_MODES = frozenset({
    "success",
    "failure",
    "unknown",
    "unavailable",
})

BACKUP_RESTORE_MODES = frozenset({
    "track_a_guarded",
    "track_b_blocked_confidentiality_not_ready",
    "track_b_confidentiality_ready",
})

BACKUP_RESTORE_CONFIDENTIALITY_MODES = frozenset({
    "ready",
    "backup_restore_confidentiality_not_ready",
})

DEPLOYMENT_TRACKS = frozenset({
    "track_a",
    "track_b",
})

SERVICE_MAINTENANCE_VERBS = frozenset({
    "service_status",
    "service_start",
    "service_restart",
    "health_probe",
    "bounded_log_tail",
    "disk_resource_check",
    "backup_status",
})

_SERVICE_MAINTENANCE_SERVICE_VERBS = frozenset({
    "service_status",
    "service_start",
    "service_restart",
    "bounded_log_tail",
})

REVIEWED_MAEZ_SERVICES = frozenset({
    "maez.service",
    "maez-web.service",
    "maez-watchdog.service",
    "maez-subscription-proxy.service",
    "llama-server.service",
})

SERVICE_MAINTENANCE_RESULT_MODES = frozenset({
    "allowed",
    "blocked",
    "executed",
    "failed",
    "unavailable",
})

MAX_SERVICE_MAINTENANCE_LOG_LINES = 200
_SERVICE_MAINTENANCE_REQUEST_ID_RE = re.compile(r"^s7maint_[0-9a-f]{32,64}$")

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
FOUNDER_WEBAUTHN_RP_ID = "localhost"
FOUNDER_WEBAUTHN_ORIGIN = "http://localhost:11437"
FOUNDER_WEBAUTHN_HOST = "localhost:11437"

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


def validate_maintenance_record_class(record_class: str) -> str:
    return _validate_closed_value(
        record_class,
        MAINTENANCE_RECORD_CLASSES,
        "maintenance_record_class",
    )


def validate_maintenance_corpus(corpus: str) -> str:
    return _validate_closed_value(corpus, MAINTENANCE_CORPORA, "maintenance corpus")


def validate_operator_health_mode(mode: str) -> str:
    return _validate_closed_value(mode, OPERATOR_HEALTH_MODES, "operator health mode")


def validate_operator_service_mode(mode: str) -> str:
    return _validate_closed_value(mode, OPERATOR_SERVICE_MODES, "operator service mode")


def validate_operator_freshness_class(freshness_class: str) -> str:
    return _validate_closed_value(
        freshness_class,
        OPERATOR_FRESHNESS_CLASSES,
        "operator freshness class",
    )


def validate_operator_red_gate_mode(mode: str) -> str:
    return _validate_closed_value(mode, OPERATOR_RED_GATE_MODES, "operator red-gate mode")


def validate_operator_queue_count_key(key: str) -> str:
    return _validate_closed_value(key, OPERATOR_QUEUE_COUNT_KEYS, "operator queue count key")


def validate_credential_recovery_mode(mode: str) -> str:
    return _validate_closed_value(mode, CREDENTIAL_RECOVERY_MODES, "credential recovery mode")


def validate_mixed_store_kind(kind: str) -> str:
    return _validate_closed_value(kind, MIXED_STORE_KINDS, "mixed store kind")


def validate_mixed_store_projection_mode(mode: str) -> str:
    return _validate_closed_value(
        mode,
        MIXED_STORE_PROJECTION_MODES,
        "mixed store projection mode",
    )


def validate_mixed_store_content_authority(authority: str) -> str:
    return _validate_closed_value(
        authority,
        MIXED_STORE_CONTENT_AUTHORITIES,
        "mixed store content authority",
    )


def validate_backup_operation(operation: str) -> str:
    return _validate_closed_value(operation, BACKUP_OPERATIONS, "backup operation")


def validate_backup_status_mode(mode: str) -> str:
    return _validate_closed_value(mode, BACKUP_STATUS_MODES, "backup status mode")


def validate_backup_restore_mode(mode: str) -> str:
    return _validate_closed_value(mode, BACKUP_RESTORE_MODES, "backup restore mode")


def validate_backup_restore_confidentiality_mode(mode: str) -> str:
    return _validate_closed_value(
        mode,
        BACKUP_RESTORE_CONFIDENTIALITY_MODES,
        "backup restore confidentiality mode",
    )


def validate_deployment_track(track: str) -> str:
    return _validate_closed_value(track, DEPLOYMENT_TRACKS, "deployment track")


def validate_service_maintenance_verb(verb: str) -> str:
    return _validate_closed_value(
        verb,
        SERVICE_MAINTENANCE_VERBS,
        "service maintenance verb",
    )


def validate_reviewed_maez_service(service_name: str) -> str:
    return _validate_closed_value(
        service_name,
        REVIEWED_MAEZ_SERVICES,
        "reviewed Maez service",
    )


def validate_service_maintenance_result_mode(mode: str) -> str:
    return _validate_closed_value(
        mode,
        SERVICE_MAINTENANCE_RESULT_MODES,
        "service maintenance result mode",
    )


def validate_service_maintenance_request_id(request_id: str) -> str:
    if not isinstance(request_id, str) or not _SERVICE_MAINTENANCE_REQUEST_ID_RE.fullmatch(request_id):
        raise ValueError("service maintenance request_id must be opaque")
    return request_id


def _validate_hash64(value: str, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{field} must be a 64-character hash")
    try:
        int(value, 16)
    except ValueError:
        raise ValueError(f"{field} must be a 64-character hash") from None
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
    if not isinstance(value, str):
        raise ValueError("S7 timestamp must be a string")
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid S7 timestamp") from exc
    if dt.tzinfo is None:
        raise ValueError("S7 timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _timestamp_text(value: str, *, field: str) -> str:
    dt = _canonical_timestamp(value)
    if dt is None:
        raise ValueError(f"{field} is required")
    return dt.isoformat()


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


def _authority_context_active_for_artifact(ctx: object, *, now: str) -> bool:
    if not isinstance(ctx, AuthorityContext):
        return False
    try:
        validate_grant_source(ctx.grant_source)
        validate_auth_method(ctx.auth_method)
    except ValueError:
        return False
    if ctx.verified is not True:
        return False
    if not ctx.actor_id or not ctx.role_names:
        return False
    if not ctx.allowed_scopes:
        return False
    if not ctx.surface or not ctx.credential_ref:
        return False
    if not ctx.created_at:
        return False
    if ctx.grant_source in {"none", "manual_recovery_required"}:
        return False
    if ctx.auth_method == "none":
        return False
    if not _valid_actor_handle(ctx.actor_handle_hmac):
        return False
    if not ctx.expires_at:
        return False
    return _context_active(ctx, now=now)


def authority_context_active_for_artifact(ctx: object, *, now: str) -> bool:
    """Public fail-closed AuthorityContext validity check for S7 artifact gates."""
    return _authority_context_active_for_artifact(ctx, now=now)


def _authority_context_roles_allow_work(ctx: AuthorityContext, work_class: str) -> bool:
    roles = frozenset(ctx.role_names)
    if work_class == "routine_custody":
        return bool(roles & _CUSTODIAN_ROLES)
    if work_class in {
        "destructive_user_action",
        "self_modification",
        "covenant_touching_change",
        "capability_acquisition",
        "autonomy_lowering_or_protection_reducing",
    }:
        return "bonded_user" in roles
    return False


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

    if action in BACKUP_OPERATIONS:
        return classify_backup_operation(action)
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
class SelfRemakingHistoryRecord:
    record_id: str
    schema_version: str
    maintenance_record_class: str
    source_ref_kind: str
    source_ref_hash: str
    role_names: tuple[str, ...]
    authority_context_hash: str
    work_request_envelope_hash: str
    created_at: str

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("S7 self-remaking record_id is required")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid S7 schema_version")
        validate_maintenance_record_class(self.maintenance_record_class)
        _validate_closed_value(
            self.source_ref_kind,
            SELF_REMAKING_SOURCE_REF_KINDS,
            "self_remaking source_ref_kind",
        )
        _validate_hash64(self.source_ref_hash, field="source_ref_hash")
        if not self.role_names:
            raise ValueError("S7 self-remaking history requires role_names")
        for role_name in self.role_names:
            validate_role_name(role_name)
        _validate_hash64(self.authority_context_hash, field="authority_context_hash")
        _validate_hash64(self.work_request_envelope_hash, field="work_request_envelope_hash")
        _timestamp_text(self.created_at, field="created_at")


def maintenance_record_admissible_to_corpus(
    maintenance_record_class: str,
    target_corpus: str,
) -> bool:
    """Return whether a maintenance record may enter a target corpus by default."""
    validate_maintenance_record_class(maintenance_record_class)
    validate_maintenance_corpus(target_corpus)
    if target_corpus in BIOGRAPHY_CORPORA:
        return False
    return (
        maintenance_record_class == "self_remaking_history"
        and target_corpus == "self_remaking_history"
    )


def build_self_remaking_history_record(
    *,
    record_id: str,
    source_ref_kind: str,
    source_ref_hash: str,
    role_names: tuple[str, ...],
    authority_context_hash: str,
    work_request_envelope_hash: str,
    created_at: str,
) -> SelfRemakingHistoryRecord:
    return SelfRemakingHistoryRecord(
        record_id=record_id,
        schema_version=SCHEMA_VERSION,
        maintenance_record_class="self_remaking_history",
        source_ref_kind=source_ref_kind,
        source_ref_hash=source_ref_hash,
        role_names=tuple(role_names),
        authority_context_hash=authority_context_hash,
        work_request_envelope_hash=work_request_envelope_hash,
        created_at=created_at,
    )


def _non_negative_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def build_operator_health_projection(
    *,
    mode: str,
    service_mode: str,
    uptime_class: str,
    backup_freshness_class: str,
    queue_counts: dict[str, int],
    red_gate_modes: tuple[str, ...],
    manual_recovery_required: bool,
    track_b_confidentiality_mode: str,
    data_freshness_class: str,
    extra_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build the closed, content-free S7 operator-health projection."""
    if extra_fields:
        raise ValueError("operator health projection is closed; extra fields are forbidden")
    validate_operator_health_mode(mode)
    validate_operator_service_mode(service_mode)
    validate_operator_freshness_class(uptime_class)
    validate_operator_freshness_class(backup_freshness_class)
    validate_operator_health_mode(track_b_confidentiality_mode)
    validate_operator_freshness_class(data_freshness_class)
    if manual_recovery_required is not True and manual_recovery_required is not False:
        raise ValueError("manual_recovery_required must be bool")
    safe_counts = {
        validate_operator_queue_count_key(str(key)): _non_negative_int(
            value,
            field=f"queue_counts.{key}",
        )
        for key, value in dict(queue_counts or {}).items()
    }
    safe_red_gates = tuple(sorted(validate_operator_red_gate_mode(mode) for mode in red_gate_modes))
    if mode == "ready" and (
        safe_red_gates
        or manual_recovery_required is True
        or track_b_confidentiality_mode != "ready"
        or service_mode != "running"
        or uptime_class != "fresh"
        or backup_freshness_class != "fresh"
        or data_freshness_class != "fresh"
    ):
        raise ValueError("operator health ready mode requires fresh running inputs")
    return {
        "schema_version": SCHEMA_VERSION,
        "route": "/operator/health",
        "mode": mode,
        "service_mode": service_mode,
        "uptime_class": uptime_class,
        "backup_freshness_class": backup_freshness_class,
        "queue_counts": safe_counts,
        "pending_guarded_request_count": safe_counts.get("open", 0),
        "blocked_request_count": safe_counts.get("blocked", 0),
        "expired_request_count": safe_counts.get("expired", 0),
        "red_gate_modes": safe_red_gates,
        "manual_recovery_required": manual_recovery_required,
        "track_b_confidentiality_mode": track_b_confidentiality_mode,
        "data_freshness_class": data_freshness_class,
    }


def build_operator_unavailable_recovery_projection(
    *,
    deployment_track: str,
    bonded_user_is_operator: bool,
) -> dict[str, object]:
    """Project D16 readiness without naming people or granting authority."""
    validate_deployment_track(deployment_track)
    if bonded_user_is_operator is not True and bonded_user_is_operator is not False:
        raise ValueError("bonded_user_is_operator must be bool")
    separated = bonded_user_is_operator is not True
    blocked = separated or deployment_track == "track_b"
    mode = "operator_unavailable_recovery_not_implemented" if blocked else "ready"
    red_gates = ("operator_unavailable_recovery_not_implemented",) if blocked else ()
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": validate_operator_health_mode(mode),
        "deployment_track": deployment_track,
        "bonded_user_operator_separated": separated,
        "track_b_activation_blocker": blocked,
        "operator_recovery_ceremony_ready": False,
        "red_gate_modes": tuple(validate_operator_red_gate_mode(gate) for gate in red_gates),
        "content_authority": validate_mixed_store_content_authority("not_granted"),
    }


def build_track_b_confidentiality_projection(
    *,
    deployment_track: str,
    non_bonded_operator: bool,
    storage_hardening_review_ref_hash: str | None = None,
) -> dict[str, object]:
    """Project whether Track-B role separation has reviewed storage hardening."""
    validate_deployment_track(deployment_track)
    if non_bonded_operator is not True and non_bonded_operator is not False:
        raise ValueError("non_bonded_operator must be bool")
    if storage_hardening_review_ref_hash:
        _validate_hash64(storage_hardening_review_ref_hash, field="storage_hardening_review_ref_hash")
    ref_present = False
    mode = "track_b_confidentiality_not_ready"
    blocker = mode != "ready" and (deployment_track == "track_b" or non_bonded_operator)
    warning_modes = () if mode == "ready" or blocker else ("track_b_confidentiality_not_ready",)
    red_gates = ("track_b_confidentiality_not_ready",) if blocker else ()
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": validate_operator_health_mode(mode),
        "deployment_track": deployment_track,
        "non_bonded_operator": non_bonded_operator,
        "storage_hardening_ref_present": ref_present,
        "track_b_activation_blocker": blocker,
        "warning_modes": warning_modes,
        "red_gate_modes": tuple(validate_operator_red_gate_mode(gate) for gate in red_gates),
        "content_authority": validate_mixed_store_content_authority("not_granted"),
    }


def build_backup_restore_confidentiality_projection(
    *,
    deployment_track: str,
    non_bonded_operator: bool,
    restore_staging_review_ref_hash: str | None = None,
) -> dict[str, object]:
    """Project whether backup restore has reviewed confidentiality-safe staging."""
    validate_deployment_track(deployment_track)
    if non_bonded_operator is not True and non_bonded_operator is not False:
        raise ValueError("non_bonded_operator must be bool")
    if restore_staging_review_ref_hash:
        _validate_hash64(restore_staging_review_ref_hash, field="restore_staging_review_ref_hash")
    ref_present = False
    mode = "backup_restore_confidentiality_not_ready"
    blocker = deployment_track == "track_b" or non_bonded_operator
    warning_modes = () if blocker else ("backup_restore_confidentiality_not_ready",)
    red_gates = ("backup_restore_confidentiality_not_ready",) if blocker else ()
    track_b_confidentiality_mode = "track_b_confidentiality_not_ready" if blocker else "ready"
    restore_work_class = (
        "undeterminable_work_class"
        if blocker
        else classify_backup_operation(
            "backup_restore",
            deployment_track=deployment_track,
            track_b_confidentiality_mode=track_b_confidentiality_mode,
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": validate_backup_restore_confidentiality_mode(mode),
        "deployment_track": deployment_track,
        "non_bonded_operator": non_bonded_operator,
        "restore_staging_ref_present": ref_present,
        "backup_restore_activation_blocker": blocker,
        "restore_work_class": restore_work_class,
        "warning_modes": warning_modes,
        "red_gate_modes": tuple(validate_operator_red_gate_mode(gate) for gate in red_gates),
        "content_authority": validate_mixed_store_content_authority("not_granted"),
    }


def _build_mixed_store_projection(
    *,
    store_kind: str,
    mode: str,
    row_count: int,
    content_authority: str = "not_granted",
) -> dict[str, object]:
    """Build a closed content-free projection over a mixed content store."""
    return {
        "schema_version": SCHEMA_VERSION,
        "store_kind": validate_mixed_store_kind(store_kind),
        "mode": validate_mixed_store_projection_mode(mode),
        "row_count": _non_negative_int(row_count, field="row_count"),
        "raw_rows_visible_by_default": False,
        "content_authority": validate_mixed_store_content_authority(content_authority),
    }


def _path_has_suffix(path: Path, suffix: tuple[str, ...]) -> bool:
    return len(path.parts) >= len(suffix) and path.parts[-len(suffix):] == suffix


def build_covenant_log_projection(log_path: str | Path) -> dict[str, object]:
    """Return content-free counts for logs/covenant.log.

    D20 treats covenant log lines as bonded-content by default. This reader
    intentionally counts rows without returning the row text, path, command
    parameters, refusal rationale, or timestamps.
    """
    path = Path(log_path)
    if not _path_has_suffix(path, _EXPECTED_COVENANT_LOG_SUFFIX):
        return _build_mixed_store_projection(
            store_kind="covenant_log",
            mode="unavailable",
            row_count=0,
        )
    if not path.is_file():
        return _build_mixed_store_projection(
            store_kind="covenant_log",
            mode="unavailable",
            row_count=0,
        )
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            row_count = sum(1 for _line in handle)
    except OSError:
        return _build_mixed_store_projection(
            store_kind="covenant_log",
            mode="unavailable",
            row_count=0,
        )
    return _build_mixed_store_projection(
        store_kind="covenant_log",
        mode="content_free_counts",
        row_count=row_count,
    )


def build_audit_log_projection(db_path: str | Path) -> dict[str, object]:
    """Return content-free counts for memory/audit_log.db.

    The audit table carries params, reasoning, command outputs, and direct-edit
    context, so S7 exposes only aggregate count unless a future reviewed
    projection proves a narrower field content-free.
    """
    path = Path(db_path)
    if not _path_has_suffix(path, _EXPECTED_AUDIT_LOG_DB_SUFFIX):
        return _build_mixed_store_projection(
            store_kind="audit_log_db",
            mode="unavailable",
            row_count=0,
        )
    if not path.is_file():
        return _build_mixed_store_projection(
            store_kind="audit_log_db",
            mode="unavailable",
            row_count=0,
        )
    try:
        with sqlite3.connect(path) as conn:
            exists = conn.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = 'audit_log'
                """
            ).fetchone()
            if not exists:
                return _build_mixed_store_projection(
                    store_kind="audit_log_db",
                    mode="unavailable",
                    row_count=0,
                )
            row_count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    except sqlite3.Error:
        return _build_mixed_store_projection(
            store_kind="audit_log_db",
            mode="unavailable",
            row_count=0,
        )
    return _build_mixed_store_projection(
        store_kind="audit_log_db",
        mode="content_free_counts",
        row_count=int(row_count),
    )


def classify_backup_operation(
    operation: str,
    *,
    deployment_track: str = "track_a",
    track_b_confidentiality_mode: str = "track_b_confidentiality_not_ready",
) -> str:
    """Map a Decision-22 backup operation into the S7 work-class lattice."""
    validate_backup_operation(operation)
    validate_deployment_track(deployment_track)
    validate_operator_health_mode(track_b_confidentiality_mode)
    if operation in _ROUTINE_BACKUP_OPERATIONS:
        return "routine_custody"
    if deployment_track == "track_b" and track_b_confidentiality_mode != "ready":
        return "undeterminable_work_class"
    return "destructive_user_action"


def _backup_restore_mode(track_b_confidentiality_mode: str) -> str:
    validate_operator_health_mode(track_b_confidentiality_mode)
    if track_b_confidentiality_mode == "ready":
        return "track_b_confidentiality_ready"
    return "track_b_blocked_confidentiality_not_ready"


def build_backup_status_projection(
    status_path: str | Path,
    *,
    backup_freshness_class: str,
    track_b_confidentiality_mode: str = "track_b_confidentiality_not_ready",
) -> dict[str, object]:
    """Return a content-free Decision-22 backup status projection.

    The source file carries snapshot paths, timestamps, byte counts, commits,
    and error details. S7 exposes only a closed status mode and freshness class.
    """
    validate_operator_freshness_class(backup_freshness_class)
    restore_mode = _backup_restore_mode(track_b_confidentiality_mode)
    mode = "unavailable"
    path = Path(status_path)
    if _path_has_suffix(path, _EXPECTED_LAST_BACKUP_SUFFIX) and path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            candidate = str(payload.get("status") or "unknown")
            mode = candidate if candidate in BACKUP_STATUS_MODES else "unknown"
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            mode = "unavailable"
    return {
        "schema_version": SCHEMA_VERSION,
        "store_kind": validate_mixed_store_kind("decision22_backup_artifact"),
        "mode": validate_backup_status_mode(mode),
        "backup_freshness_class": backup_freshness_class,
        "raw_backup_contents_visible_by_default": False,
        "restore_work_class": classify_backup_operation(
            "backup_restore",
            deployment_track="track_a",
            track_b_confidentiality_mode=track_b_confidentiality_mode,
        ),
        "track_b_restore_mode": validate_backup_restore_mode(restore_mode),
        "content_authority": validate_mixed_store_content_authority("not_granted"),
    }


@dataclass(frozen=True)
class ServiceMaintenanceRequest:
    request_id: str
    schema_version: str
    verb: str
    service_name: str | None
    created_at: str
    log_line_limit: int

    def __post_init__(self) -> None:
        validate_service_maintenance_request_id(self.request_id)
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unknown service maintenance schema_version")
        validate_service_maintenance_verb(self.verb)
        _timestamp_text(self.created_at, field="created_at")
        _non_negative_int(self.log_line_limit, field="log_line_limit")
        if self.verb in _SERVICE_MAINTENANCE_SERVICE_VERBS and not self.service_name:
            raise ValueError("service maintenance verb requires reviewed service")
        if self.service_name is not None:
            validate_reviewed_maez_service(self.service_name)
        if self.verb == "bounded_log_tail":
            if self.log_line_limit < 1 or self.log_line_limit > MAX_SERVICE_MAINTENANCE_LOG_LINES:
                raise ValueError("bounded_log_tail requires line limit within reviewed cap")
        elif self.log_line_limit != 0:
            raise ValueError("log_line_limit is only valid for bounded_log_tail")


def build_service_maintenance_request(
    *,
    request_id: str,
    verb: str,
    service_name: str | None,
    created_at: str,
    log_line_limit: int = 0,
) -> ServiceMaintenanceRequest:
    return ServiceMaintenanceRequest(
        request_id=request_id,
        schema_version=SCHEMA_VERSION,
        verb=verb,
        service_name=service_name,
        created_at=created_at,
        log_line_limit=log_line_limit,
    )


def build_service_maintenance_audit_record(
    *,
    request: ServiceMaintenanceRequest,
    result_mode: str,
    created_at: str,
    raw_output: str | None = None,
    command: str | None = None,
) -> dict[str, object]:
    """Build the daemon-down helper's content-free audit spool record."""
    if not isinstance(request, ServiceMaintenanceRequest):
        raise ValueError("service maintenance audit requires reviewed request")
    validate_service_maintenance_result_mode(result_mode)
    created_at = _timestamp_text(created_at, field="created_at")
    if raw_output is not None or command is not None:
        raise ValueError("service maintenance audit records cannot carry raw output or commands")
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request.request_id,
        "verb": request.verb,
        "service_name": request.service_name or "none",
        "result_mode": result_mode,
        "created_at": created_at,
        "log_line_limit": request.log_line_limit,
        "content_authority": validate_mixed_store_content_authority("not_granted"),
    }


def append_service_maintenance_audit_spool(
    spool_path: str | Path,
    record: dict[str, object],
    *,
    repo_root: str | Path | None = None,
) -> None:
    """Append a content-free daemon-down maintenance audit record as JSONL."""
    path = Path(spool_path)
    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    expected_path = root / "logs" / "service_maintenance_audit.jsonl"
    if path.resolve() != expected_path:
        raise ValueError("service maintenance audit spool must be under the trusted repo root")
    expected_keys = {
        "schema_version",
        "request_id",
        "verb",
        "service_name",
        "result_mode",
        "created_at",
        "log_line_limit",
        "content_authority",
    }
    if set(record) != expected_keys:
        raise ValueError("service maintenance audit record is not closed-shape")
    if record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unknown service maintenance audit schema_version")
    validate_service_maintenance_request_id(str(record["request_id"]))
    verb = validate_service_maintenance_verb(str(record["verb"]))
    service_name = str(record["service_name"])
    if service_name != "none":
        validate_reviewed_maez_service(service_name)
    validate_service_maintenance_result_mode(str(record["result_mode"]))
    _timestamp_text(str(record["created_at"]), field="created_at")
    log_line_limit = _non_negative_int(record["log_line_limit"], field="log_line_limit")
    if verb == "bounded_log_tail":
        if log_line_limit < 1 or log_line_limit > MAX_SERVICE_MAINTENANCE_LOG_LINES:
            raise ValueError("bounded_log_tail audit record exceeds reviewed line cap")
    elif log_line_limit != 0:
        raise ValueError("log_line_limit is only valid for bounded_log_tail")
    validate_mixed_store_content_authority(str(record["content_authority"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


@dataclass(frozen=True)
class S7AuthorizationArtifact:
    artifact_id: str
    request_id: str
    request_envelope_hash: str
    rendered_text_hash: str
    action_params_hash: str
    precondition_hash: str
    authority_context_hash: str
    derived_work_class: str
    derived_aggregation_group: str
    nonce: str
    credential_ref: str
    auth_method: str
    grant_source: str
    user_presence: bool
    user_verification: bool
    created_at: str
    expires_at: str
    consumed_at: str | None

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("S7 artifact_id is required")
        if not self.request_id:
            raise ValueError("S7 artifact request_id is required")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        _validate_hash64(self.rendered_text_hash, field="rendered_text_hash")
        _validate_hash64(self.action_params_hash, field="action_params_hash")
        _validate_hash64(self.precondition_hash, field="precondition_hash")
        _validate_hash64(self.authority_context_hash, field="authority_context_hash")
        validate_work_class(self.derived_work_class)
        if not self.derived_aggregation_group:
            raise ValueError("S7 artifact derived_aggregation_group is required")
        if not self.nonce:
            raise ValueError("S7 artifact nonce is required")
        if not self.credential_ref:
            raise ValueError("S7 artifact credential_ref is required")
        validate_auth_method(self.auth_method)
        validate_grant_source(self.grant_source)
        if self.user_presence is not True and self.user_presence is not False:
            raise ValueError("S7 artifact user_presence must be bool")
        if self.user_verification is not True and self.user_verification is not False:
            raise ValueError("S7 artifact user_verification must be bool")
        _canonical_timestamp(self.created_at)
        if not self.expires_at:
            raise ValueError("S7 artifact expires_at is required")
        _canonical_timestamp(self.expires_at)
        if self.consumed_at is not None:
            if not self.consumed_at:
                raise ValueError("S7 artifact consumed_at must be a timestamp or None")
            _canonical_timestamp(self.consumed_at)


def authorization_artifact_matches(
    artifact: S7AuthorizationArtifact,
    *,
    rendered: RenderedRequestStatement,
    action_params_hash: str,
    authority_context_hash: str,
    precondition_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    now: str,
    superseded_request_ids: set[str] | None = None,
) -> bool:
    if superseded_request_ids and rendered.request_id in superseded_request_ids:
        return False
    if artifact.consumed_at is not None:
        return False
    now_dt = _canonical_timestamp(now)
    expires_dt = _canonical_timestamp(artifact.expires_at)
    if now_dt is None or expires_dt is None or expires_dt <= now_dt:
        return False
    expected = {
        "request_id": rendered.request_id,
        "request_envelope_hash": rendered.request_envelope_hash,
        "rendered_text_hash": rendered.rendered_text_hash,
        "action_params_hash": action_params_hash,
        "precondition_hash": precondition_hash,
        "authority_context_hash": authority_context_hash,
        "derived_work_class": derived_work_class,
        "derived_aggregation_group": derived_aggregation_group,
        "nonce": rendered.nonce,
    }
    for field, value in expected.items():
        if getattr(artifact, field) != value:
            return False
    return True


_AUTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS s7_authorization_artifacts (
    artifact_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    request_envelope_hash TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    action_params_hash TEXT NOT NULL,
    precondition_hash TEXT NOT NULL,
    authority_context_hash TEXT NOT NULL,
    derived_work_class TEXT NOT NULL,
    derived_aggregation_group TEXT NOT NULL,
    nonce TEXT NOT NULL UNIQUE,
    credential_ref TEXT NOT NULL,
    auth_method TEXT NOT NULL,
    grant_source TEXT NOT NULL,
    user_presence INTEGER NOT NULL,
    user_verification INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    consumed_by_request_id TEXT
);
"""


class S7AuthorizationStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_AUTH_SCHEMA)

    def put(self, artifact: S7AuthorizationArtifact) -> None:
        created_at = _timestamp_text(artifact.created_at, field="created_at")
        expires_at = _timestamp_text(artifact.expires_at, field="expires_at")
        consumed_at = (
            _timestamp_text(artifact.consumed_at, field="consumed_at")
            if artifact.consumed_at is not None
            else None
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO s7_authorization_artifacts (
                    artifact_id, request_id, request_envelope_hash,
                    rendered_text_hash, action_params_hash, precondition_hash,
                    authority_context_hash, derived_work_class,
                    derived_aggregation_group, nonce, credential_ref, auth_method,
                    grant_source, user_presence, user_verification, created_at,
                    expires_at, consumed_at, consumed_by_request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    artifact.artifact_id,
                    artifact.request_id,
                    artifact.request_envelope_hash,
                    artifact.rendered_text_hash,
                    artifact.action_params_hash,
                    artifact.precondition_hash,
                    artifact.authority_context_hash,
                    artifact.derived_work_class,
                    artifact.derived_aggregation_group,
                    artifact.nonce,
                    artifact.credential_ref,
                    artifact.auth_method,
                    artifact.grant_source,
                    1 if artifact.user_presence else 0,
                    1 if artifact.user_verification else 0,
                    created_at,
                    expires_at,
                    consumed_at,
                ),
            )

    def consume(self, artifact_id: str, *, request_id: str, now: str) -> bool:
        del artifact_id, request_id, now
        raise RuntimeError("S7 authorization consumption requires consume_verified")

    def consume_verified(
        self,
        artifact_id: str,
        *,
        rendered: RenderedRequestStatement,
        action_params_hash: str,
        authority_context: AuthorityContext,
        precondition_hash: str,
        derived_work_class: str,
        derived_aggregation_group: str,
        now: str,
        superseded_request_ids: set[str] | None = None,
    ) -> bool:
        if superseded_request_ids and rendered.request_id in superseded_request_ids:
            return False
        _validate_hash64(action_params_hash, field="action_params_hash")
        _validate_hash64(precondition_hash, field="precondition_hash")
        validate_work_class(derived_work_class)
        if not derived_aggregation_group:
            return False
        if not _authority_context_active_for_artifact(authority_context, now=now):
            return False
        if not _authority_context_roles_allow_work(authority_context, derived_work_class):
            return False
        auth_hash = authority_context_hash(authority_context)
        if rendered.authority_context_hash != auth_hash:
            return False
        now_text = _timestamp_text(now, field="now")
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE s7_authorization_artifacts
                SET consumed_at = ?,
                    consumed_by_request_id = ?
                WHERE artifact_id = ?
                  AND request_id = ?
                  AND request_envelope_hash = ?
                  AND rendered_text_hash = ?
                  AND action_params_hash = ?
                  AND precondition_hash = ?
                  AND authority_context_hash = ?
                  AND derived_work_class = ?
                  AND derived_aggregation_group = ?
                  AND nonce = ?
                  AND auth_method = ?
                  AND grant_source = ?
                  AND user_presence = 1
                  AND (? = 0 OR user_verification = 1)
                  AND consumed_at IS NULL
                  AND expires_at > ?
                """,
                (
                    now_text,
                    rendered.request_id,
                    artifact_id,
                    rendered.request_id,
                    rendered.request_envelope_hash,
                    rendered.rendered_text_hash,
                    action_params_hash,
                    precondition_hash,
                    auth_hash,
                    derived_work_class,
                    derived_aggregation_group,
                    rendered.nonce,
                    authority_context.auth_method,
                    authority_context.grant_source,
                    1 if _webauthn_requires_user_verification(derived_work_class) else 0,
                    now_text,
                ),
            )
            return cur.rowcount == 1


@dataclass(frozen=True)
class S7ExecutionAuthorization:
    """Exact authorization bundle consumed at the execution edge."""

    store: S7AuthorizationStore
    artifact_id: str
    rendered: RenderedRequestStatement
    action_params_hash: str
    authority_context: AuthorityContext
    precondition_hash: str
    derived_work_class: str
    derived_aggregation_group: str
    now: str

    def __post_init__(self) -> None:
        if not isinstance(self.store, S7AuthorizationStore):
            raise ValueError("S7 execution authorization requires an authorization store")
        if not self.artifact_id:
            raise ValueError("S7 execution authorization requires artifact_id")
        _validate_hash64(self.action_params_hash, field="action_params_hash")
        _validate_hash64(self.precondition_hash, field="precondition_hash")
        validate_work_class(self.derived_work_class)
        if not self.derived_aggregation_group:
            raise ValueError("S7 execution authorization requires derived_aggregation_group")
        _timestamp_text(self.now, field="now")


@dataclass(frozen=True)
class WebAuthnCredentialRecord:
    credential_ref: str
    actor_handle_hmac: str
    role_names: tuple[str, ...]
    public_key: str
    sign_count: int
    rp_id: str
    origin: str
    created_at: str
    backup_credential: bool
    enabled: bool

    def __post_init__(self) -> None:
        if not self.credential_ref:
            raise ValueError("S7 WebAuthn credential_ref is required")
        if not _valid_actor_handle(self.actor_handle_hmac):
            raise ValueError("S7 WebAuthn actor_handle_hmac must be purpose-scoped keyed HMAC")
        for role_name in self.role_names:
            validate_role_name(role_name)
        if not self.public_key:
            raise ValueError("S7 WebAuthn public_key is required")
        if not isinstance(self.sign_count, int) or self.sign_count < 0:
            raise ValueError("S7 WebAuthn sign_count must be a non-negative integer")
        if not self.rp_id:
            raise ValueError("S7 WebAuthn rp_id is required")
        if not self.origin:
            raise ValueError("S7 WebAuthn origin is required")
        _canonical_timestamp(self.created_at)
        if self.backup_credential is not True and self.backup_credential is not False:
            raise ValueError("S7 WebAuthn backup_credential must be bool")
        if self.enabled is not True and self.enabled is not False:
            raise ValueError("S7 WebAuthn enabled must be bool")


@dataclass(frozen=True)
class CredentialRecoveryState:
    mode: str
    active_credential_count: int
    primary_credential_count: int
    backup_credential_count: int
    manual_recovery_required: bool
    witnessed_fallback_available: bool = False
    schema_version: str = SCHEMA_VERSION
    content_authority: str = "not_granted"

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("S7 credential recovery state schema_version mismatch")
        validate_credential_recovery_mode(self.mode)
        _non_negative_int(self.active_credential_count, field="active_credential_count")
        _non_negative_int(self.primary_credential_count, field="primary_credential_count")
        _non_negative_int(self.backup_credential_count, field="backup_credential_count")
        if self.manual_recovery_required is not True and self.manual_recovery_required is not False:
            raise ValueError("S7 manual_recovery_required must be bool")
        if self.witnessed_fallback_available is not True and self.witnessed_fallback_available is not False:
            raise ValueError("S7 witnessed_fallback_available must be bool")
        validate_mixed_store_content_authority(self.content_authority)
        if self.active_credential_count != self.primary_credential_count + self.backup_credential_count:
            raise ValueError("S7 credential recovery counts must add up")
        if self.mode == "manual_recovery_required" and self.manual_recovery_required is not True:
            raise ValueError("S7 manual recovery mode requires manual_recovery_required=True")
        if self.active_credential_count == 0 and self.manual_recovery_required is not True:
            raise ValueError("S7 no-credential state must require manual recovery")
        if self.active_credential_count == 0 and self.mode != "manual_recovery_required":
            raise ValueError("S7 no-credential state must use manual_recovery_required mode")
        if self.active_credential_count > 0 and self.manual_recovery_required is True:
            raise ValueError("S7 active credential state cannot require manual recovery")
        if self.mode == "ready" and (self.primary_credential_count == 0 or self.backup_credential_count == 0):
            raise ValueError("S7 ready credential state requires primary and backup credentials")
        if self.mode == "degraded" and (
            self.active_credential_count == 0
            or (self.primary_credential_count > 0 and self.backup_credential_count > 0)
        ):
            raise ValueError("S7 degraded credential state requires partial active credential coverage")


@dataclass(frozen=True)
class WitnessedFallbackRecord:
    fallback_id: str
    bonded_user_actor_handle_hmac: str
    witness_actor_handle_hmac: str
    witness_role_names: tuple[str, ...]
    new_credential_ref: str
    ceremony_ref_hash: str
    created_at: str
    auth_method: str = "witnessed_fallback"
    grant_source: str = "witnessed_fallback"
    witness_read_authority: bool = False
    witness_allowed_scopes: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("S7 witnessed fallback schema_version mismatch")
        if not _WITNESSED_FALLBACK_ID_RE.fullmatch(self.fallback_id):
            raise ValueError("S7 witnessed fallback id must be opaque")
        if not _valid_actor_handle(self.bonded_user_actor_handle_hmac):
            raise ValueError("S7 witnessed fallback bonded_user handle must be purpose-scoped HMAC")
        if not _valid_actor_handle(self.witness_actor_handle_hmac):
            raise ValueError("S7 witnessed fallback witness handle must be purpose-scoped HMAC")
        if self.bonded_user_actor_handle_hmac == self.witness_actor_handle_hmac:
            raise ValueError("S7 witnessed fallback witness cannot substitute for bonded_user")
        if "witness" not in self.witness_role_names:
            raise ValueError("S7 witnessed fallback requires witness role")
        if "bonded_user" in self.witness_role_names:
            raise ValueError("S7 witnessed fallback witness cannot claim bonded_user role")
        for role_name in self.witness_role_names:
            validate_role_name(role_name)
        if not self.new_credential_ref or any(
            marker in self.new_credential_ref for marker in ("/", "\\", " ", "\n", "\t", "@")
        ):
            raise ValueError("S7 witnessed fallback new_credential_ref must be an opaque reference")
        _validate_hash64(self.ceremony_ref_hash, field="ceremony_ref_hash")
        _timestamp_text(self.created_at, field="created_at")
        if self.auth_method != "witnessed_fallback":
            raise ValueError("S7 witnessed fallback auth_method mismatch")
        if self.grant_source != "witnessed_fallback":
            raise ValueError("S7 witnessed fallback grant_source mismatch")
        if self.witness_read_authority is not False:
            raise ValueError("S7 witnessed fallback cannot grant witness read authority")
        if self.witness_allowed_scopes:
            raise ValueError("S7 witnessed fallback cannot grant witness scopes")


@dataclass(frozen=True)
class WebAuthnChallenge:
    challenge_id: str
    request_id: str
    request_envelope_hash: str
    rendered_text_hash: str
    action_params_hash: str
    precondition_hash: str
    authority_context_hash: str
    nonce: str
    work_class: str
    rp_id: str
    origin: str
    host: str
    created_at: str
    expires_at: str

    def __post_init__(self) -> None:
        if not self.challenge_id:
            raise ValueError("S7 WebAuthn challenge_id is required")
        if not self.request_id:
            raise ValueError("S7 WebAuthn challenge request_id is required")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        _validate_hash64(self.rendered_text_hash, field="rendered_text_hash")
        _validate_hash64(self.action_params_hash, field="action_params_hash")
        _validate_hash64(self.precondition_hash, field="precondition_hash")
        _validate_hash64(self.authority_context_hash, field="authority_context_hash")
        if not self.nonce:
            raise ValueError("S7 WebAuthn nonce is required")
        validate_work_class(self.work_class)
        _validate_founder_webauthn_origin(self.rp_id, self.origin, self.host)
        _canonical_timestamp(self.created_at)
        if not self.expires_at:
            raise ValueError("S7 WebAuthn challenge expires_at is required")
        _canonical_timestamp(self.expires_at)


@dataclass(frozen=True)
class WebAuthnAssertion:
    credential_ref: str
    challenge_id: str
    challenge_hash: str
    rp_id: str
    origin: str
    host: str
    user_presence: bool
    user_verification: bool
    sign_count: int
    source: str

    def __post_init__(self) -> None:
        if not self.credential_ref:
            raise ValueError("S7 WebAuthn assertion credential_ref is required")
        if not self.challenge_id:
            raise ValueError("S7 WebAuthn assertion challenge_id is required")
        _validate_hash64(self.challenge_hash, field="challenge_hash")
        if self.user_presence is not True and self.user_presence is not False:
            raise ValueError("S7 WebAuthn assertion user_presence must be bool")
        if self.user_verification is not True and self.user_verification is not False:
            raise ValueError("S7 WebAuthn assertion user_verification must be bool")
        if not isinstance(self.sign_count, int) or self.sign_count < 0:
            raise ValueError("S7 WebAuthn assertion sign_count must be a non-negative integer")
        if not self.source:
            raise ValueError("S7 WebAuthn assertion source is required")


@dataclass(frozen=True)
class WebAuthnVerificationResult:
    verified: bool
    blocked: bool
    credential_ref: str | None
    actor_handle_hmac: str | None
    role_names: tuple[str, ...]
    auth_method: str
    grant_source: str
    user_presence: bool
    user_verification: bool
    sign_count: int | None
    reason_code: str
    created_at: str

    def __post_init__(self) -> None:
        if self.verified is not True and self.verified is not False:
            raise ValueError("S7 WebAuthn result verified must be bool")
        if self.blocked is not True and self.blocked is not False:
            raise ValueError("S7 WebAuthn result blocked must be bool")
        validate_auth_method(self.auth_method)
        validate_grant_source(self.grant_source)
        for role_name in self.role_names:
            validate_role_name(role_name)
        _canonical_timestamp(self.created_at)


class FakeWebAuthnVerifier:
    """Deterministic verifier seam for S7 CI tests; not a production verifier."""

    def __init__(
        self,
        *,
        available: bool = True,
        authenticator_supports_user_verification: bool = True,
    ) -> None:
        self.available = available
        self.authenticator_supports_user_verification = authenticator_supports_user_verification

    def assertion_for(
        self,
        record: WebAuthnCredentialRecord,
        challenge: WebAuthnChallenge,
        *,
        user_presence: bool,
        user_verification: bool,
        sign_count: int | None = None,
        source: str = "browser_webauthn",
    ) -> WebAuthnAssertion:
        return WebAuthnAssertion(
            credential_ref=record.credential_ref,
            challenge_id=challenge.challenge_id,
            challenge_hash=webauthn_challenge_hash(challenge),
            rp_id=challenge.rp_id,
            origin=challenge.origin,
            host=challenge.host,
            user_presence=user_presence,
            user_verification=user_verification,
            sign_count=record.sign_count + 1 if sign_count is None else sign_count,
            source=source,
        )

    def verify(
        self,
        *,
        record: WebAuthnCredentialRecord,
        challenge: WebAuthnChallenge,
        assertion: WebAuthnAssertion,
        require_user_verification: bool,
        now: str,
    ) -> WebAuthnVerificationResult:
        if not self.available:
            return _webauthn_failure("verifier_unavailable", now=now, blocked=True)
        if assertion.source != "browser_webauthn":
            return _webauthn_failure("browser_webauthn_required", now=now)
        if not record.enabled:
            return _webauthn_failure("credential_disabled", now=now)
        if assertion.credential_ref != record.credential_ref:
            return _webauthn_failure("credential_mismatch", now=now)
        if assertion.challenge_id != challenge.challenge_id:
            return _webauthn_failure("challenge_mismatch", now=now)
        if assertion.challenge_hash != webauthn_challenge_hash(challenge):
            return _webauthn_failure("challenge_hash_mismatch", now=now)
        if assertion.rp_id != challenge.rp_id or assertion.rp_id != record.rp_id:
            return _webauthn_failure("rp_id_mismatch", now=now)
        if assertion.origin != challenge.origin or assertion.origin != record.origin:
            return _webauthn_failure("origin_mismatch", now=now)
        if assertion.host != challenge.host or assertion.host != FOUNDER_WEBAUTHN_HOST:
            return _webauthn_failure("host_mismatch", now=now)
        if assertion.sign_count <= record.sign_count:
            return _webauthn_failure("sign_count_not_advanced", now=now)
        if assertion.user_presence is not True:
            return _webauthn_failure("user_presence_required", now=now)
        if (
            require_user_verification
            and self.authenticator_supports_user_verification
            and assertion.user_verification is not True
        ):
            return _webauthn_failure("user_verification_required", now=now)
        return WebAuthnVerificationResult(
            verified=True,
            blocked=False,
            credential_ref=record.credential_ref,
            actor_handle_hmac=record.actor_handle_hmac,
            role_names=record.role_names,
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            user_presence=assertion.user_presence,
            user_verification=assertion.user_verification,
            sign_count=assertion.sign_count,
            reason_code="verified",
            created_at=now,
        )


def webauthn_challenge_hash(challenge: WebAuthnChallenge) -> str:
    return s6.canonical_hash(asdict(challenge))


_WEBAUTHN_CHALLENGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS s7_webauthn_challenges (
    challenge_id TEXT PRIMARY KEY,
    challenge_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT
);
"""


class WebAuthnChallengeStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_WEBAUTHN_CHALLENGE_SCHEMA)

    def put(self, challenge: WebAuthnChallenge) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO s7_webauthn_challenges (
                    challenge_id, challenge_hash, expires_at, consumed_at
                ) VALUES (?, ?, ?, NULL)
                """,
                (
                    challenge.challenge_id,
                    webauthn_challenge_hash(challenge),
                    _timestamp_text(challenge.expires_at, field="expires_at"),
                ),
            )

    def consume(self, challenge: WebAuthnChallenge, *, now: str) -> bool:
        now_text = _timestamp_text(now, field="now")
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE s7_webauthn_challenges
                SET consumed_at = ?
                WHERE challenge_id = ?
                  AND challenge_hash = ?
                  AND consumed_at IS NULL
                  AND expires_at > ?
                """,
                (
                    now_text,
                    challenge.challenge_id,
                    webauthn_challenge_hash(challenge),
                    now_text,
                ),
            )
            return cur.rowcount == 1


_WEBAUTHN_CREDENTIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS s7_webauthn_credentials (
    credential_ref TEXT PRIMARY KEY,
    actor_handle_hmac TEXT NOT NULL,
    role_names_json TEXT NOT NULL,
    public_key TEXT NOT NULL,
    sign_count INTEGER NOT NULL,
    rp_id TEXT NOT NULL,
    origin TEXT NOT NULL,
    created_at TEXT NOT NULL,
    backup_credential INTEGER NOT NULL,
    enabled INTEGER NOT NULL
);
"""


def _credential_record_from_row(row: tuple[Any, ...]) -> WebAuthnCredentialRecord:
    return WebAuthnCredentialRecord(
        credential_ref=row[0],
        actor_handle_hmac=row[1],
        role_names=tuple(json.loads(row[2])),
        public_key=row[3],
        sign_count=int(row[4]),
        rp_id=row[5],
        origin=row[6],
        created_at=row[7],
        backup_credential=bool(row[8]),
        enabled=bool(row[9]),
    )


class WebAuthnCredentialRegistry:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_WEBAUTHN_CREDENTIAL_SCHEMA)

    def put(self, record: WebAuthnCredentialRecord) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO s7_webauthn_credentials (
                    credential_ref, actor_handle_hmac, role_names_json,
                    public_key, sign_count, rp_id, origin, created_at,
                    backup_credential, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.credential_ref,
                    record.actor_handle_hmac,
                    json.dumps(list(record.role_names), separators=(",", ":")),
                    record.public_key,
                    record.sign_count,
                    record.rp_id,
                    record.origin,
                    _timestamp_text(record.created_at, field="created_at"),
                    1 if record.backup_credential else 0,
                    1 if record.enabled else 0,
                ),
            )

    def get(self, credential_ref: str) -> WebAuthnCredentialRecord | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT credential_ref, actor_handle_hmac, role_names_json,
                       public_key, sign_count, rp_id, origin, created_at,
                       backup_credential, enabled
                FROM s7_webauthn_credentials
                WHERE credential_ref = ?
                """,
                (credential_ref,),
            ).fetchone()
        if row is None:
            return None
        return _credential_record_from_row(row)

    def all_records(self) -> tuple[WebAuthnCredentialRecord, ...]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT credential_ref, actor_handle_hmac, role_names_json,
                       public_key, sign_count, rp_id, origin, created_at,
                       backup_credential, enabled
                FROM s7_webauthn_credentials
                ORDER BY credential_ref
                """,
            ).fetchall()
        return tuple(_credential_record_from_row(row) for row in rows)

    def active_records(self) -> tuple[WebAuthnCredentialRecord, ...]:
        return tuple(record for record in self.all_records() if record.enabled)

    def disable_credential(self, credential_ref: str, *, disabled_at: str) -> bool:
        if not credential_ref:
            return False
        _timestamp_text(disabled_at, field="disabled_at")
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE s7_webauthn_credentials
                SET enabled = 0
                WHERE credential_ref = ?
                  AND enabled = 1
                """,
                (credential_ref,),
            )
            return cur.rowcount == 1

    def advance_sign_count(self, credential_ref: str, *, new_sign_count: int) -> bool:
        if not isinstance(new_sign_count, int) or new_sign_count < 0:
            return False
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE s7_webauthn_credentials
                SET sign_count = ?
                WHERE credential_ref = ?
                  AND sign_count < ?
                """,
                (new_sign_count, credential_ref, new_sign_count),
            )
            return cur.rowcount == 1


def build_credential_recovery_state(
    *,
    registry: WebAuthnCredentialRegistry | None = None,
    records: tuple[WebAuthnCredentialRecord, ...] | None = None,
    witnessed_fallback_available: bool = False,
) -> CredentialRecoveryState:
    if registry is not None and records is not None:
        raise ValueError("S7 credential recovery state accepts registry or records, not both")
    source_records = registry.active_records() if registry is not None else tuple(records or ())
    active_records = tuple(
        record for record in source_records if record.enabled and "bonded_user" in record.role_names
    )
    primary_count = sum(1 for record in active_records if not record.backup_credential)
    backup_count = sum(1 for record in active_records if record.backup_credential)
    active_count = primary_count + backup_count
    if active_count == 0:
        mode = "manual_recovery_required"
    elif primary_count == 0 or backup_count == 0:
        mode = "degraded"
    else:
        mode = "ready"
    return CredentialRecoveryState(
        mode=mode,
        active_credential_count=active_count,
        primary_credential_count=primary_count,
        backup_credential_count=backup_count,
        manual_recovery_required=active_count == 0,
        witnessed_fallback_available=witnessed_fallback_available,
    )


def build_witnessed_fallback_record(
    *,
    fallback_id: str,
    bonded_user_actor_handle_hmac: str,
    witness_actor_handle_hmac: str,
    witness_role_names: tuple[str, ...],
    new_credential_ref: str,
    ceremony_ref_hash: str,
    created_at: str,
    witness_read_authority: bool = False,
    witness_allowed_scopes: tuple[str, ...] = (),
) -> WitnessedFallbackRecord:
    return WitnessedFallbackRecord(
        fallback_id=fallback_id,
        bonded_user_actor_handle_hmac=bonded_user_actor_handle_hmac,
        witness_actor_handle_hmac=witness_actor_handle_hmac,
        witness_role_names=tuple(witness_role_names),
        new_credential_ref=new_credential_ref,
        ceremony_ref_hash=ceremony_ref_hash,
        created_at=created_at,
        witness_read_authority=witness_read_authority,
        witness_allowed_scopes=tuple(witness_allowed_scopes),
    )


def _validate_founder_webauthn_origin(rp_id: str, origin: str, host: str) -> None:
    if rp_id != FOUNDER_WEBAUTHN_RP_ID:
        raise ValueError("S7 founder WebAuthn rp_id must be localhost")
    if origin != FOUNDER_WEBAUTHN_ORIGIN:
        raise ValueError("S7 founder WebAuthn origin must be canonical localhost")
    if host != FOUNDER_WEBAUTHN_HOST:
        raise ValueError("S7 founder WebAuthn host must be canonical localhost")


def register_founder_webauthn_credential(
    *,
    credential_ref: str,
    actor_handle_hmac: str,
    role_names: tuple[str, ...],
    public_key: str,
    sign_count: int,
    rp_id: str,
    origin: str,
    host: str,
    created_at: str,
    backup_credential: bool = False,
    enabled: bool = True,
) -> WebAuthnCredentialRecord:
    _validate_founder_webauthn_origin(rp_id, origin, host)
    return WebAuthnCredentialRecord(
        credential_ref=credential_ref,
        actor_handle_hmac=actor_handle_hmac,
        role_names=role_names,
        public_key=public_key,
        sign_count=sign_count,
        rp_id=rp_id,
        origin=origin,
        created_at=created_at,
        backup_credential=backup_credential,
        enabled=enabled,
    )


def _webauthn_requires_user_verification(work_class: str) -> bool:
    validate_work_class(work_class)
    return work_class in {
        "self_modification",
        "covenant_touching_change",
        "capability_acquisition",
        "autonomy_lowering_or_protection_reducing",
    }


def _webauthn_failure(
    reason_code: str,
    *,
    now: str,
    blocked: bool = False,
) -> WebAuthnVerificationResult:
    return WebAuthnVerificationResult(
        verified=False,
        blocked=blocked,
        credential_ref=None,
        actor_handle_hmac=None,
        role_names=(),
        auth_method="manual_recovery_required" if blocked else "none",
        grant_source="manual_recovery_required" if blocked else "none",
        user_presence=False,
        user_verification=False,
        sign_count=None,
        reason_code=reason_code,
        created_at=now,
    )


def verify_founder_webauthn_assertion(
    *,
    record: WebAuthnCredentialRecord,
    challenge: WebAuthnChallenge,
    assertion: WebAuthnAssertion,
    verifier: FakeWebAuthnVerifier | None,
    challenge_store: WebAuthnChallengeStore | None = None,
    credential_registry: WebAuthnCredentialRegistry | None = None,
    now: str,
) -> WebAuthnVerificationResult:
    now_dt = _canonical_timestamp(now)
    expires_dt = _canonical_timestamp(challenge.expires_at)
    if now_dt is None or expires_dt is None or expires_dt <= now_dt:
        return _webauthn_failure("challenge_expired", now=now, blocked=True)
    if verifier is None:
        return _webauthn_failure("missing_verifier", now=now, blocked=True)
    active_record = record
    if credential_registry is not None:
        loaded = credential_registry.get(record.credential_ref)
        if loaded is None:
            return _webauthn_failure("credential_not_registered", now=now, blocked=True)
        active_record = loaded
    result = verifier.verify(
        record=active_record,
        challenge=challenge,
        assertion=assertion,
        require_user_verification=_webauthn_requires_user_verification(challenge.work_class),
        now=now,
    )
    if not result.verified:
        return result
    if challenge_store is None:
        return _webauthn_failure("missing_challenge_store", now=now, blocked=True)
    if credential_registry is None:
        return _webauthn_failure("missing_credential_registry", now=now, blocked=True)
    if not challenge_store.consume(challenge, now=now):
        return _webauthn_failure("challenge_replayed", now=now)
    if not credential_registry.advance_sign_count(
        active_record.credential_ref,
        new_sign_count=result.sign_count or -1,
    ):
        return _webauthn_failure("sign_count_replayed", now=now)
    return result


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
