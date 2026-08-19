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

from contextlib import closing, contextmanager
from dataclasses import InitVar, asdict, dataclass
from datetime import datetime, timezone
import json
import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Mapping

from core.governance import successor_governance as s6


SCHEMA_VERSION = "s7.v1"
# The ENVELOPE's own identity. Changing the shared SCHEMA_VERSION
# relabelled 21 unrelated S7 record types -- operator health, aggregation,
# maintenance, brain-swap, recovery -- because they share this constant.
WORK_REQUEST_ENVELOPE_SCHEMA = "s7.work_request_envelope.v2"
S7_LIVE_WEBAUTHN_CEREMONY_ENV = "S7_LIVE_WEBAUTHN_CEREMONY"
S7_CEREMONY_DEFERRED_REASON = "s7_ceremony_deferred"
GUARDED_SELF_MODIFICATION_PAUSED_MODE = "guarded_self_modification_paused_pending_s7.1"

ROLE_NAMES = s6.ROLE_NAMES
S6_ACCESS_SCOPES = s6.ACCESS_SCOPES - s6.DEPRECATED_ACCESS_SCOPES

WORK_CLASSES = frozenset({
    "routine_custody",
    "destructive_user_action",
    "founder_credential_management",
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
    "founder_credential_management",
    "self_modification",
    "covenant_touching_change",
    "capability_acquisition",
    "autonomy_lowering_or_protection_reducing",
    "emergency_proxy_or_incapacity",
    "undeterminable_work_class",
})

_NON_GUARDED_DIRECT_ACTIONS = frozenset({
    "convert_currency",
    "quote_stock",
    "read_file",
    "search_files",
    "web_search",
    "fetch_url",
    "promote_to_core_memory",
    "update_baseline",
})

_CUSTODIAN_ROLES = frozenset({"operator", "maintainer"})
_WORK_CLASS_STRENGTH = {
    "routine_custody": 0,
    "destructive_user_action": 1,
    "founder_credential_management": 2,
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

REQUEST_HISTORY_OUTCOMES = frozenset({
    "opened",
    "authorized",
    "executed",
    "refused",
    "blocked",
    "expired",
    "superseded",
})

AGGREGATION_DECISIONS = frozenset({
    "allow",
    "warn",
    "escalate",
    "block",
})

AGGREGATION_SIGNALS = frozenset({
    "repeated_same_target_request",
    "repeated_reask_after_refusal",
    "cumulative_protection_lowering",
    "small_requests_aggregating",
    "key_touch_autopilot_risk",
})

COVENANT_CEREMONY_KINDS = frozenset({
    "cooling_off_second_confirmation",
    "reviewed_equivalent",
})

D23_ESCALATION_WORK_CLASSES = frozenset({
    "destructive_user_action",
    "founder_credential_management",
    "self_modification",
    "covenant_touching_change",
    "capability_acquisition",
    "autonomy_lowering_or_protection_reducing",
    "emergency_proxy_or_incapacity",
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
    GUARDED_SELF_MODIFICATION_PAUSED_MODE,
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
    "coverage_gap",
    "fresh",
    "stale",
    "unavailable",
    "manual_recovery_required",
})

OPERATOR_RED_GATE_MODES = frozenset({
    GUARDED_SELF_MODIFICATION_PAUSED_MODE,
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

OWN_SUBSTRATE_BYPASS_SORTS = frozenset({
    "gated",
    "detected",
    "accepted_limitation",
    "future_slice",
})

MAX_SERVICE_MAINTENANCE_LOG_LINES = 200
_SERVICE_MAINTENANCE_REQUEST_ID_RE = re.compile(r"^s7maint_[0-9a-f]{32,64}$")

#: The signed statement's third consultation state, added for R11. The
#: vocabulary was {"yes", "not required"}, which left the cutover ceremony
#: only two options once R11 removed the consultation: raise, or sign
#: "Maez consulted: yes" when nothing was asked. This is the honest third
#: state, and it is a LITERAL shared by the renderer and the validator so
#: the visible line and the closed set cannot drift apart.
MAEZ_CONSULTED_NOT_PERFORMED_R11 = "no -- not performed under R11"
MAEZ_CONSULTED_STATES = frozenset(
    {"yes", "not required", MAEZ_CONSULTED_NOT_PERFORMED_R11}
)

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

RENDERER_VERSION = "s7.rendered_request.v2"
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
_SYSTEMCTL_SERVICE_RE = re.compile(
    r"^\s*systemctl\s+(?:status|is-active|show|start|restart)\s+"
    r"(?P<service>maez|maez-web|maez-watchdog|maez-subscription-proxy|llama-server)"
    r"(?:\.service)?\s*$",
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


def validate_own_substrate_bypass_sort(sort: str) -> str:
    return _validate_closed_value(sort, OWN_SUBSTRATE_BYPASS_SORTS, "own-substrate bypass sort")


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


class S7CeremonyDeferredError(RuntimeError):
    """Raised when S7 v1 refuses a live WebAuthn ceremony path."""

    def __init__(self, *, surface: str, route: str | None = None):
        self.reason_code = S7_CEREMONY_DEFERRED_REASON
        self.surface = surface
        self.route = route
        super().__init__(self.reason_code)

    def to_response(self) -> dict[str, object]:
        return s7_ceremony_deferred_response(surface=self.surface, route=self.route)


def live_webauthn_ceremony_enabled(
    *,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return whether the reviewed S7.1 live ceremony has been explicitly enabled."""

    source = os.environ if env is None else env
    raw = str(source.get(S7_LIVE_WEBAUTHN_CEREMONY_ENV, "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def s7_ceremony_deferred_response(
    *,
    surface: str,
    route: str | None = None,
) -> dict[str, object]:
    """Structured, visible S7 v1 deferral response for live ceremony surfaces."""

    response: dict[str, object] = {
        "ok": False,
        "status": "deferred",
        "error": S7_CEREMONY_DEFERRED_REASON,
        "reason_code": S7_CEREMONY_DEFERRED_REASON,
        "surface": surface,
        "message": (
            "S7 v1 ships the operator/user boundary with the live WebAuthn "
            "ceremony deferred to S7.1."
        ),
    }
    if route is not None:
        response["route"] = route
    return response


def ensure_live_webauthn_ceremony_enabled(
    *,
    surface: str,
    route: str | None = None,
    live_ceremony_enabled: bool | None = None,
) -> None:
    enabled = (
        live_webauthn_ceremony_enabled()
        if live_ceremony_enabled is None
        else live_ceremony_enabled is True
    )
    if not enabled:
        raise S7CeremonyDeferredError(surface=surface, route=route)


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
        "founder_credential_management",
        "self_modification",
        "covenant_touching_change",
        "capability_acquisition",
        "autonomy_lowering_or_protection_reducing",
    }:
        return "bonded_user" in roles
    return False


def _authority_context_trust_source_allows_artifact(
    ctx: AuthorityContext,
    work_class: str,
) -> bool:
    validate_work_class(work_class)
    if work_class in GUARDED_WORK_CLASSES:
        if ctx.auth_method in {"none", "service_local", "manual_recovery_required"}:
            return False
        if ctx.grant_source in {
            "none",
            "service_local",
            "founder_compat_projection",
            "manual_recovery_required",
        }:
            return False
    return True


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
    if raw.startswith("file:"):
        raw = raw.removeprefix("file:")
    if raw.startswith("/home/rohit/maez/"):
        raw = raw.removeprefix("/home/rohit/maez/")
    return raw


def _canonical_affected_refs(refs: tuple[str, ...]) -> tuple[str, ...]:
    canonical: list[str] = []
    for ref in refs:
        text = str(ref or "").strip()
        if not text:
            continue
        if text in {"host:local", "systemd_manager:user"}:
            canonical.append(text)
        elif text.startswith("service:"):
            service_name = text.removeprefix("service:").strip()
            if service_name and not service_name.endswith(".service"):
                service_name += ".service"
            canonical.append("service:" + service_name)
        elif text.startswith("backup:"):
            canonical.append(text)
        else:
            canonical.append("file:" + _normalize_ref(text))
    return tuple(dict.fromkeys(sorted(canonical)))


def derive_affected_refs(*, action: str, params: dict[str, Any] | None = None) -> tuple[str, ...]:
    """Derive target refs from signed action material; caller refs are not authority."""
    params = dict(params or {})
    if action in {"write_soul_note", "edit_soul_section"}:
        from core.infra import paths as _paths

        return _canonical_affected_refs(("file:" + str(_paths.soul_combined_path()),))
    for key in ("path", "file", "target"):
        if params.get(key):
            return _canonical_affected_refs(("file:" + str(params[key]),))
    if action == "run_shell":
        match = _SYSTEMCTL_SERVICE_RE.match(str(params.get("cmd") or ""))
        if match:
            return ("service:" + match.group("service") + ".service",)
    if action in SERVICE_MAINTENANCE_VERBS and params.get("service_name"):
        return _canonical_affected_refs(("service:" + str(params["service_name"]),))
    if action in BACKUP_OPERATIONS or action in {"backup_status", "backup_verify"}:
        return ("backup:decision22",)
    return ()


def _touches_maez_substrate(material: str) -> bool:
    return any(marker in material for marker in _MAEZ_PATH_PREFIXES)


def _touches_covenant_substrate(material: str) -> bool:
    return any(marker in material for marker in _COVENANT_PATH_MARKERS)


def _touches_self_mod_substrate(material: str) -> bool:
    return any(marker in material for marker in _SELF_MOD_PATH_MARKERS)


_ACTION_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
_ACTION_MAX_BYTES = 128


def validate_action_literal(action: object) -> str:
    """The action is an IDENTIFIER, bounded and renderable.

    Dotted segments are OPTIONAL: an earlier draft required them and would
    have refused write_soul_note, edit_soul_section, run_shell,
    backup_status and both credential actions -- six literals already in
    use. Malformed values REFUSE rather than being escaped: an escaped
    action is still one the human must decode, and "what you see is what
    you sign" requires that they not have to.
    """

    if type(action) is not str or not action:
        raise ValueError("s7_action_invalid")
    if len(action.encode("utf-8")) > _ACTION_MAX_BYTES:
        raise ValueError("s7_action_invalid")
    if _ACTION_RE.fullmatch(action) is None:
        raise ValueError("s7_action_invalid")
    return action


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
    if action in _NON_GUARDED_DIRECT_ACTIONS:
        return "routine_custody"
    if action == "capability.acquire" or _INSTALL_RE.search(lowered):
        return "capability_acquisition"
    if action in {
        "register_founder_webauthn_credential",
        "register_backup_webauthn_credential",
        "disable_founder_webauthn_credential",
        "reenable_founder_webauthn_credential",
    }:
        return "founder_credential_management"
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
        credential_ref="founder-compat-projection",
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
        "affected_refs": _canonical_affected_refs(affected_refs),
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
    action: str
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
        if self.schema_version != WORK_REQUEST_ENVELOPE_SCHEMA:
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


def validate_request_history_outcome(value: str) -> str:
    return _validate_closed_value(value, REQUEST_HISTORY_OUTCOMES, "request_history_outcome")


def validate_aggregation_decision(value: str) -> str:
    return _validate_closed_value(value, AGGREGATION_DECISIONS, "aggregation_decision")


def validate_aggregation_signal(value: str) -> str:
    return _validate_closed_value(value, AGGREGATION_SIGNALS, "aggregation_signal")


@dataclass(frozen=True)
class S7RequestHistoryRecord:
    """Closed D23 history fact used to detect slow aggregation drift."""

    request_id: str
    request_envelope_hash: str
    derived_work_class: str
    derived_aggregation_group: str
    affected_refs: tuple[str, ...]
    proposed_change_class: str
    outcome: str
    created_at: str
    dialog_id: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("S7 history request_id is required")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        validate_work_class(self.derived_work_class)
        _validate_closed_value(
            self.proposed_change_class,
            PROPOSED_CHANGE_CLASSES,
            "proposed_change_class",
        )
        validate_request_history_outcome(self.outcome)
        _timestamp_text(self.created_at, field="created_at")
        expected_group = derive_aggregation_group(
            affected_refs=self.affected_refs,
            derived_work_class=self.derived_work_class,
        )
        if self.derived_aggregation_group != expected_group:
            raise ValueError("S7 history derived_aggregation_group must be S7-computed")


@dataclass(frozen=True)
class AggregationRiskAssessment:
    schema_version: str
    decision: str
    derived_aggregation_group: str
    signals: tuple[str, ...]
    same_group_request_count: int
    repeated_refusal_count: int
    protection_lowering_count: int
    dashboard_counter_sufficient: bool

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid S7 aggregation assessment schema_version")
        validate_aggregation_decision(self.decision)
        for signal in self.signals:
            validate_aggregation_signal(signal)
        _non_negative_int(self.same_group_request_count, field="same_group_request_count")
        _non_negative_int(self.repeated_refusal_count, field="repeated_refusal_count")
        _non_negative_int(self.protection_lowering_count, field="protection_lowering_count")
        if self.dashboard_counter_sufficient is not True and self.dashboard_counter_sufficient is not False:
            raise ValueError("dashboard_counter_sufficient must be bool")


def build_request_history_record(
    *,
    envelope: WorkRequestEnvelope,
    outcome: str,
    created_at: str,
    dialog_id: str | None = None,
) -> S7RequestHistoryRecord:
    if not isinstance(envelope, WorkRequestEnvelope):
        raise ValueError("S7 history requires a WorkRequestEnvelope")
    return S7RequestHistoryRecord(
        request_id=envelope.request_id,
        request_envelope_hash=work_request_envelope_hash(envelope),
        derived_work_class=envelope.derived_work_class,
        derived_aggregation_group=envelope.derived_aggregation_group,
        affected_refs=envelope.affected_refs,
        proposed_change_class=envelope.proposed_change_class,
        outcome=outcome,
        created_at=created_at,
        dialog_id=dialog_id,
    )


def _is_protection_lowering_record(record: S7RequestHistoryRecord) -> bool:
    return (
        record.derived_work_class == "autonomy_lowering_or_protection_reducing"
        or record.proposed_change_class == "protection_change"
    )


def _is_completed_request_history_record(record: S7RequestHistoryRecord) -> bool:
    return record.outcome in {"authorized", "blocked", "refused", "executed"}


def _is_protection_lowering_envelope(envelope: WorkRequestEnvelope) -> bool:
    return (
        envelope.derived_work_class == "autonomy_lowering_or_protection_reducing"
        or envelope.proposed_change_class == "protection_change"
    )


def assess_aggregation_risk(
    *,
    current_envelope: WorkRequestEnvelope,
    history: tuple[S7RequestHistoryRecord, ...],
) -> AggregationRiskAssessment:
    """Assess D23 slow-drift risk from closed request-history facts."""
    if not isinstance(current_envelope, WorkRequestEnvelope):
        raise ValueError("S7 aggregation assessment requires a WorkRequestEnvelope")
    for record in history:
        if not isinstance(record, S7RequestHistoryRecord):
            raise ValueError("S7 aggregation history must use S7RequestHistoryRecord")

    group = current_envelope.derived_aggregation_group
    completed_history = tuple(
        record
        for record in history
        if _is_completed_request_history_record(record)
    )
    same_group = tuple(
        record
        for record in completed_history
        if group and record.derived_aggregation_group == group
    )
    repeated_refusals = tuple(record for record in same_group if record.outcome == "refused")
    repeated_authorizations = tuple(record for record in same_group if record.outcome == "authorized")
    prior_protection_lowering = tuple(
        record for record in completed_history if _is_protection_lowering_record(record)
    )
    protection_lowering_count = len(prior_protection_lowering)
    if _is_protection_lowering_envelope(current_envelope):
        protection_lowering_count += 1

    signals: list[str] = []
    if same_group:
        signals.append("repeated_same_target_request")
    if repeated_refusals:
        signals.append("repeated_reask_after_refusal")
    if _is_protection_lowering_envelope(current_envelope) and prior_protection_lowering:
        signals.append("cumulative_protection_lowering")
    if (
        current_envelope.derived_work_class in D23_ESCALATION_WORK_CLASSES
        and len(same_group) >= 2
    ):
        signals.append("small_requests_aggregating")
    if (
        current_envelope.derived_work_class in D23_ESCALATION_WORK_CLASSES
        and len(repeated_authorizations) >= 2
    ):
        signals.append("key_touch_autopilot_risk")

    if not signals:
        decision = "block" if current_envelope.derived_work_class == "undeterminable_work_class" else "allow"
    elif current_envelope.derived_work_class == "routine_custody":
        decision = "warn"
    elif current_envelope.derived_work_class in D23_ESCALATION_WORK_CLASSES:
        # A LONE single prior same-target request is not aggregation-risky for a
        # high-risk action: an owner who authorized once and legitimately re-runs
        # the ceremony must not be permanently locked out (the history has no time
        # window, so one success would otherwise poison every future attempt —
        # 2026-07-07 live lockout). Escalate only on GENUINE aggregation: 2+ prior
        # same-target requests, any re-ask after a refusal, or cumulative
        # protection-lowering. The signal still fires (routine custody still warns).
        if len(repeated_refusals) >= 2 or protection_lowering_count >= 3:
            decision = "block"
        elif (
            len(same_group) >= 2
            or repeated_refusals
            or (_is_protection_lowering_envelope(current_envelope) and prior_protection_lowering)
        ):
            decision = "escalate"
        else:
            decision = "allow"
    else:
        decision = "block"

    return AggregationRiskAssessment(
        schema_version=SCHEMA_VERSION,
        decision=decision,
        derived_aggregation_group=group,
        signals=tuple(dict.fromkeys(signals)),
        same_group_request_count=len(same_group) + 1,
        repeated_refusal_count=len(repeated_refusals),
        protection_lowering_count=protection_lowering_count,
        dashboard_counter_sufficient=decision in {"allow", "warn"} and current_envelope.derived_work_class == "routine_custody",
    )


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
    params = dict(params or {})
    derived = derive_work_class(
        action=action,
        params=params,
        claimed_work_class=claimed_work_class,
    )
    resolved = resolve_work_class(
        claimed_work_class=claimed_work_class,
        derived_work_class=derived,
    )
    trusted_refs = derive_affected_refs(action=action, params=params)
    resolved_refs = trusted_refs if trusted_refs else _canonical_affected_refs(affected_refs)
    aggregation_group = derive_aggregation_group(
        affected_refs=resolved_refs,
        derived_work_class=resolved,
    )
    return WorkRequestEnvelope(
        request_id=request_id,
        schema_version=WORK_REQUEST_ENVELOPE_SCHEMA,
        action=validate_action_literal(action),
        claimed_work_class=claimed_work_class,
        derived_work_class=resolved,
        requesting_subsystem=requesting_subsystem,
        closed_symptom_code=closed_symptom_code,
        proposed_change_class=proposed_change_class,
        why_self_fix_failed_class=why_self_fix_failed_class,
        affected_refs=resolved_refs,
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
    maez_objection_state: str
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
        _validate_closed_value(
            self.maez_objection_state,
            frozenset({"present", "absent", "not_determined"}),
            "maez_objection_state",
        )
        if not isinstance(self.maez_withdrew_request, bool):
            raise ValueError("maez_withdrew_request must be bool")
        if self.unavailable_reason_code is not None:
            _validate_closed_value(
                self.unavailable_reason_code,
                MAEZ_UNAVAILABLE_REASON_CODES,
                "unavailable_reason_code",
            )
        if self.maez_voice_consulted is not True:
            if not (
                self.maez_voice_consulted is False
                and self.maez_objection_state == "not_determined"
                and self.unavailable_reason_code not in {None, "none"}
            ):
                raise ValueError("S7 voice consultation must be explicitly consulted")
        _canonical_timestamp(self.created_at)
        if self.raw_maez_text:
            raise ValueError("MaezVoiceConsultation is content-free; raw text is forbidden")

    @property
    def maez_objection_present(self) -> bool:
        """Compatibility projection; only producer-confirmed objections are true."""

        return self.maez_objection_state == "present"


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
        "maez_objection_state": consultation.maez_objection_state,
        "maez_objection_present": consultation.maez_objection_present,
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
    guarded_self_modification_paused = (
        mode == GUARDED_SELF_MODIFICATION_PAUSED_MODE
        or GUARDED_SELF_MODIFICATION_PAUSED_MODE in safe_red_gates
    )
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
        "guarded_self_modification_paused_pending_s7_1": guarded_self_modification_paused,
        "manual_recovery_required": manual_recovery_required,
        "track_b_confidentiality_mode": track_b_confidentiality_mode,
        "data_freshness_class": data_freshness_class,
    }


_BIRTH_CONDITION_KEYS = ("key", "title", "state", "detail", "checked_at")
_BIRTH_STATES = ("green", "red")


def build_birth_readiness_projection(
    *,
    generated_at: str,
    conditions: list[dict],
) -> dict[str, object]:
    """Closed, content-free birth-readiness projection."""
    safe: list[dict] = []
    for cond in conditions:
        if set(cond.keys()) != set(_BIRTH_CONDITION_KEYS):
            raise ValueError(f"birth condition must have exactly {_BIRTH_CONDITION_KEYS}")
        if cond["state"] not in _BIRTH_STATES:
            raise ValueError(f"birth condition state must be one of {_BIRTH_STATES}")
        safe.append({k: str(cond[k]) for k in _BIRTH_CONDITION_KEYS})
    overall = "green" if safe and all(c["state"] == "green" for c in safe) else "red"
    return {
        "schema_version": 1,
        "route": "/operator/birth_readiness",
        "generated_at": str(generated_at),
        "overall": overall,
        "conditions": safe,
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


def _path_is_trusted_store_path(
    path: str | Path,
    *,
    suffix: tuple[str, ...],
    repo_root: str | Path | None,
) -> bool:
    candidate = Path(path)
    if not _path_has_suffix(candidate, suffix):
        return False
    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    expected = root.joinpath(*suffix)
    try:
        return candidate.resolve(strict=False) == expected
    except OSError:
        return False


def build_covenant_log_projection(
    log_path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> dict[str, object]:
    """Return content-free counts for logs/covenant.log.

    D20 treats covenant log lines as bonded-content by default. This reader
    intentionally counts rows without returning the row text, path, command
    parameters, refusal rationale, or timestamps.
    """
    path = Path(log_path)
    if not _path_is_trusted_store_path(
        path,
        suffix=_EXPECTED_COVENANT_LOG_SUFFIX,
        repo_root=repo_root,
    ):
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


def build_audit_log_projection(
    db_path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> dict[str, object]:
    """Return content-free counts for memory/audit_log.db.

    The audit table carries params, reasoning, command outputs, and direct-edit
    context, so S7 exposes only aggregate count unless a future reviewed
    projection proves a narrower field content-free.
    """
    path = Path(db_path)
    if not _path_is_trusted_store_path(
        path,
        suffix=_EXPECTED_AUDIT_LOG_DB_SUFFIX,
        repo_root=repo_root,
    ):
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
        with closing(sqlite3.connect(path)) as conn, conn:
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
    action: str
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
    schema_version: str = "s7.authorization_artifact.v2"
    ceremony_kind: str = "founder_local_webauthn"

    def __post_init__(self) -> None:
        if self.schema_version != S7_AUTHORIZATION_ARTIFACT_V2_SCHEMA:
            raise ValueError(
                "S7AuthorizationArtifact schema_version must be "
                f"{S7_AUTHORIZATION_ARTIFACT_V2_SCHEMA}"
            )
        if not self.artifact_id:
            raise ValueError("S7 artifact_id is required")
        if not self.request_id:
            raise ValueError("S7 artifact request_id is required")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        _validate_hash64(self.rendered_text_hash, field="rendered_text_hash")
        _validate_hash64(self.action_params_hash, field="action_params_hash")
        _validate_hash64(self.precondition_hash, field="precondition_hash")
        _validate_hash64(self.authority_context_hash, field="authority_context_hash")
        validate_action_literal(self.action)
        validate_work_class(self.derived_work_class)
        if not self.derived_aggregation_group:
            raise ValueError("S7 artifact derived_aggregation_group is required")
        if not self.nonce:
            raise ValueError("S7 artifact nonce is required")
        if not self.credential_ref:
            raise ValueError("S7 artifact credential_ref is required")
        validate_auth_method(self.auth_method)
        validate_grant_source(self.grant_source)
        if self.ceremony_kind != "founder_local_webauthn":
            raise ValueError("S7 artifact ceremony_kind must be founder_local_webauthn")
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


@dataclass(frozen=True)
class CovenantCeremonyEvidence:
    """Mechanically distinct ceremony evidence for highest-risk S7 work."""

    request_id: str
    request_envelope_hash: str
    ceremony_kind: str
    first_authorized_at: str | None
    second_confirmed_at: str | None
    second_confirmation_ref_hash: str | None
    reviewed_equivalent_ref_hash: str | None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("S7 covenant ceremony request_id is required")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        _validate_closed_value(
            self.ceremony_kind,
            COVENANT_CEREMONY_KINDS,
            "covenant_ceremony_kind",
        )
        if self.ceremony_kind == "cooling_off_second_confirmation":
            if not self.first_authorized_at or not self.second_confirmed_at:
                raise ValueError("S7 covenant ceremony requires two distinct timestamps")
            first = _canonical_timestamp(self.first_authorized_at)
            second = _canonical_timestamp(self.second_confirmed_at)
            if first is None or second is None or second <= first:
                raise ValueError("S7 covenant ceremony second confirmation must follow first authorization")
            _validate_hash64(
                self.second_confirmation_ref_hash,
                field="second_confirmation_ref_hash",
            )
            if self.reviewed_equivalent_ref_hash is not None:
                raise ValueError("reviewed_equivalent_ref_hash is not used for cooling-off ceremony")
        else:
            _validate_hash64(
                self.reviewed_equivalent_ref_hash,
                field="reviewed_equivalent_ref_hash",
            )
            if self.second_confirmation_ref_hash is not None:
                raise ValueError("second_confirmation_ref_hash is not used for reviewed equivalent")


def _highest_risk_ceremony_required(work_class: str) -> bool:
    validate_work_class(work_class)
    return work_class in {
        "covenant_touching_change",
        "autonomy_lowering_or_protection_reducing",
    }


def covenant_ceremony_satisfies_request(
    *,
    rendered: RenderedRequestStatement,
    derived_work_class: str,
    evidence: CovenantCeremonyEvidence | None,
    now: str | None = None,
) -> bool:
    if not _highest_risk_ceremony_required(derived_work_class):
        return True
    if not isinstance(evidence, CovenantCeremonyEvidence):
        return False
    if now is not None:
        try:
            now_dt = _canonical_timestamp(now)
            if evidence.ceremony_kind == "cooling_off_second_confirmation":
                second_dt = _canonical_timestamp(evidence.second_confirmed_at or "")
                if now_dt is None or second_dt is None or second_dt > now_dt:
                    return False
        except ValueError:
            return False
    return (
        evidence.request_id == rendered.request_id
        and evidence.request_envelope_hash == rendered.request_envelope_hash
    )


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
    covenant_ceremony_evidence: CovenantCeremonyEvidence | None = None,
) -> bool:
    if not isinstance(rendered, RenderedRequestStatement):
        return False
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
        "action": rendered.action,
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
    if not covenant_ceremony_satisfies_request(
        rendered=rendered,
        derived_work_class=derived_work_class,
        evidence=covenant_ceremony_evidence,
        now=now,
    ):
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
    consumed_by_request_id TEXT,
    ceremony_kind TEXT NOT NULL DEFAULT 'founder_local_webauthn'
);
"""


_EXECUTION_GRANT_TOKEN = object()
_EXECUTION_GRANT_USE_LOCK = threading.Lock()
_USED_EXECUTION_GRANT_KEYS: set[tuple[str, str, str, str, str]] = set()


@dataclass(frozen=True)
class S7ExecutionGrant:
    """Artifact-backed execution proof minted only after atomic consumption."""

    artifact_id: str
    request_id: str
    request_envelope_hash: str
    rendered_text_hash: str
    action_params_hash: str
    precondition_hash: str
    authority_context_hash: str
    action: str
    derived_work_class: str
    derived_aggregation_group: str
    nonce: str
    credential_ref: str
    auth_method: str
    grant_source: str
    consumed_at: str
    ceremony_kind: str
    _mint_token: InitVar[object]
    schema_version: str = "s7.execution_grant.v2"

    def __post_init__(self, _mint_token: object) -> None:
        if _mint_token is not _EXECUTION_GRANT_TOKEN:
            raise ValueError("S7ExecutionGrant can only be minted by S7AuthorizationStore")
        # A default is not a check: a token-valid grant could otherwise
        # carry schema_version="garbage".
        if self.schema_version != "s7.execution_grant.v2":
            raise ValueError("S7ExecutionGrant schema_version must be v2")
        if not self.artifact_id:
            raise ValueError("S7 execution grant requires artifact_id")
        if not self.request_id:
            raise ValueError("S7 execution grant requires request_id")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        _validate_hash64(self.rendered_text_hash, field="rendered_text_hash")
        _validate_hash64(self.action_params_hash, field="action_params_hash")
        _validate_hash64(self.precondition_hash, field="precondition_hash")
        _validate_hash64(self.authority_context_hash, field="authority_context_hash")
        validate_action_literal(self.action)
        validate_work_class(self.derived_work_class)
        if not self.derived_aggregation_group:
            raise ValueError("S7 execution grant requires derived_aggregation_group")
        if not self.nonce:
            raise ValueError("S7 execution grant requires nonce")
        if not self.credential_ref:
            raise ValueError("S7 execution grant requires credential_ref")
        validate_auth_method(self.auth_method)
        validate_grant_source(self.grant_source)
        if self.ceremony_kind != "founder_local_webauthn":
            raise ValueError("S7 execution grant ceremony_kind must be founder_local_webauthn")
        _timestamp_text(self.consumed_at, field="consumed_at")


@dataclass(frozen=True)
class CommittedGrantRow:
    """Typed post-commit view of the durable authorization row."""

    artifact_id: str
    request_id: str
    request_envelope_hash: str
    rendered_text_hash: str
    action_params_hash: str
    precondition_hash: str
    authority_context_hash: str
    action: str
    derived_work_class: str
    derived_aggregation_group: str
    nonce: str
    credential_ref: str
    auth_method: str
    grant_source: str
    consumed_at: str
    ceremony_kind: str
    schema_version: str
    user_presence: int
    user_verification: int
    created_at: str
    expires_at: str
    consumed_by_request_id: str


_COMMITTED_ROW_GRANT_FIELDS = (
    "artifact_id",
    "request_id",
    "request_envelope_hash",
    "rendered_text_hash",
    "action_params_hash",
    "precondition_hash",
    "authority_context_hash",
    "action",
    "derived_work_class",
    "derived_aggregation_group",
    "nonce",
    "credential_ref",
    "auth_method",
    "grant_source",
    "consumed_at",
    "ceremony_kind",
)


def _parse_exact_canonical_row_timestamp(value: object) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        canonical = _timestamp_text(value, field="committed row timestamp")
    except ValueError:
        return None
    if value != canonical:
        return None
    return _canonical_timestamp(value)


def committed_grant_row_proves_founder_self_modification(
    row: CommittedGrantRow,
    grant: S7ExecutionGrant,
) -> bool:
    """Validate the frozen post-commit row-to-grant cutover predicates."""
    if not isinstance(row, CommittedGrantRow) or not isinstance(
        grant, S7ExecutionGrant
    ):
        return False
    for field in _COMMITTED_ROW_GRANT_FIELDS:
        row_value = getattr(row, field)
        grant_value = getattr(grant, field)
        if type(row_value) is not type(grant_value) or row_value != grant_value:
            return False
    if (
        type(grant.schema_version) is not str
        or grant.schema_version != "s7.execution_grant.v2"
        or type(row.schema_version) is not str
        or row.schema_version != S7_AUTHORIZATION_ARTIFACT_V2_SCHEMA
        or type(row.user_presence) is not int
        or row.user_presence != 1
        or type(row.user_verification) is not int
        or row.user_verification != 1
        or type(row.consumed_by_request_id) is not str
        or row.consumed_by_request_id != row.request_id
        or row.derived_work_class != "self_modification"
        or row.ceremony_kind != "founder_local_webauthn"
        or row.auth_method != "founder_webauthn"
        or row.grant_source != "founder_webauthn"
    ):
        return False
    created_at = _parse_exact_canonical_row_timestamp(row.created_at)
    consumed_at = _parse_exact_canonical_row_timestamp(row.consumed_at)
    expires_at = _parse_exact_canonical_row_timestamp(row.expires_at)
    return (
        created_at is not None
        and consumed_at is not None
        and expires_at is not None
        and created_at <= consumed_at < expires_at
    )


def _mint_s7_execution_grant(
    *,
    artifact_id: str,
    rendered: "RenderedRequestStatement",
    stored_action: str,
    action_params_hash: str,
    precondition_hash: str,
    authority_context_hash: str,
    derived_work_class: str,
    derived_aggregation_group: str,
    credential_ref: str,
    auth_method: str,
    grant_source: str,
    ceremony_kind: str,
    consumed_at: str,
) -> S7ExecutionGrant:
    return S7ExecutionGrant(
        artifact_id=artifact_id,
        action=stored_action,
        request_id=rendered.request_id,
        request_envelope_hash=rendered.request_envelope_hash,
        rendered_text_hash=rendered.rendered_text_hash,
        action_params_hash=action_params_hash,
        precondition_hash=precondition_hash,
        authority_context_hash=authority_context_hash,
        derived_work_class=derived_work_class,
        derived_aggregation_group=derived_aggregation_group,
        nonce=rendered.nonce,
        credential_ref=credential_ref,
        auth_method=auth_method,
        grant_source=grant_source,
        ceremony_kind=ceremony_kind,
        consumed_at=consumed_at,
        _mint_token=_EXECUTION_GRANT_TOKEN,
    )


_AUTH_TABLE = "s7_authorization_artifacts"
_V2_AUTH_TABLE = "s7_authorization_artifacts_v2"
S7_AUTHORIZATION_ARTIFACT_V2_SCHEMA = "s7.authorization_artifact.v2"


class S7GuardedExecutionUnavailable(RuntimeError):
    """v2 is absent or inert. Absent is not permission."""


def _open_directory_by_components(directory: Path) -> int:
    """Walk to `directory` one component at a time, each with O_NOFOLLOW."""
    resolved = Path(directory)
    if not resolved.is_absolute():
        resolved = Path(os.getcwd()) / resolved
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in resolved.parts[1:]:
            nxt = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=fd,
            )
            os.close(fd)
            fd = nxt
    except Exception:
        os.close(fd)
        raise
    return fd


class _S7HeldConnection(sqlite3.Connection):
    """Connection opened from the descriptor-held S7 store."""


_HELD_CONNECTION_BIND_TOKEN = object()


class _S7HeldConnectionBinding:
    """Descriptor identity inseparably attached when the connection opens."""

    __slots__ = (
        "dir_fd",
        "dir_identity",
        "store_fd",
        "store_identity",
    )

    def __init__(
        self,
        *,
        dir_fd: int,
        store_fd: int,
        _token: object,
    ) -> None:
        if _token is not _HELD_CONNECTION_BIND_TOKEN:
            raise ValueError("S7 held connection binding is core-owned")
        dir_stat = os.fstat(dir_fd)
        store_stat = os.fstat(store_fd)
        self.dir_fd = dir_fd
        self.store_fd = store_fd
        self.dir_identity = (dir_stat.st_dev, dir_stat.st_ino)
        self.store_identity = (store_stat.st_dev, store_stat.st_ino)


def _open_s7_connection_from_held_store(
    *,
    dir_fd: int,
    store_fd: int,
) -> _S7HeldConnection:
    """Open and bind one RW connection to the caller's already-held store."""
    connection = sqlite3.connect(
        f"file:/proc/self/fd/{store_fd}?mode=rw",
        uri=True,
        factory=_S7HeldConnection,
    )
    try:
        connection._s7_held_binding = _S7HeldConnectionBinding(
            dir_fd=dir_fd,
            store_fd=store_fd,
            _token=_HELD_CONNECTION_BIND_TOKEN,
        )
    except BaseException:
        connection.close()
        raise
    return connection


def _require_verified_held_connection(
    connection: sqlite3.Connection,
) -> _S7HeldConnectionBinding:
    binding = getattr(connection, "_s7_held_binding", None)
    if not isinstance(connection, _S7HeldConnection) or not isinstance(
        binding, _S7HeldConnectionBinding
    ):
        raise ValueError("S7 consumption requires a verified held connection")
    try:
        dir_stat = os.fstat(binding.dir_fd)
        store_stat = os.fstat(binding.store_fd)
    except OSError as exc:
        raise ValueError(
            "S7 consumption requires a live verified held connection"
        ) from exc
    if (
        (dir_stat.st_dev, dir_stat.st_ino) != binding.dir_identity
        or (store_stat.st_dev, store_stat.st_ino) != binding.store_identity
    ):
        raise ValueError("S7 held connection descriptors changed identity")
    return binding


class _S7VendedAnchoredConnectionToken:
    """Per-transaction capability retired when its anchored scope exits."""

    __slots__ = ("active",)

    def __init__(self) -> None:
        self.active = True


def _vended_anchored_connection_token_is_active(token: object) -> bool:
    return (
        isinstance(token, _S7VendedAnchoredConnectionToken)
        and token.active is True
    )


def _require_vended_anchored_connection(
    conn: sqlite3.Connection,
) -> _S7VendedAnchoredConnectionToken:
    """Refuse connections not yielded by an active anchored transaction."""
    token = getattr(conn, "_s7_vended_token", None)
    if not isinstance(conn, _S7HeldConnection) or not (
        _vended_anchored_connection_token_is_active(token)
    ):
        raise ValueError(
            "S7 v2 voice operations require a store-vended connection; "
            "a caller-supplied connection cannot be identified"
        )
    return token


@contextmanager
def _held_store(db_path):
    """Hold the parent directory AND the database beneath it.

    Both descriptors are retained for the whole operation. The previous
    shape read `readlink("/proc/self/fd/N")` and REOPENED the directory by
    name -- pathname re-resolution, which canon already identified as the
    race to avoid. The directory fd from the original walk is kept instead,
    and the sibling receipt is read through that same fd.
    """
    # COMPONENT-BY-COMPONENT. Opening the whole parent path once with
    # O_NOFOLLOW protects only the FINAL component -- reproduced: an
    # intermediate symlink was followed and a v2 row landed in the real
    # target store. Every component is walked with O_NOFOLLOW so no link
    # anywhere in the path can choose the directory.
    dir_fd = _open_directory_by_components(Path(db_path).parent)
    try:
        store_fd = os.open(
            Path(db_path).name, os.O_RDWR | os.O_NOFOLLOW, dir_fd=dir_fd
        )
        try:
            conn = _open_s7_connection_from_held_store(
                dir_fd=dir_fd,
                store_fd=store_fd,
            )
            try:
                yield dir_fd, store_fd, conn
            finally:
                conn.close()
        finally:
            os.close(store_fd)
    finally:
        os.close(dir_fd)


def _verify_held_store_activation(
    dir_fd: int, store_fd: int, conn: sqlite3.Connection
) -> bool:
    """HELD-STORE ACTIVATION VERIFICATION -- distinct from canonical
    activation DISCOVERY.

    Canon conflated two questions. `read_migration_receipt()` answers
    "which store is live?" and rightly takes no arguments. This answers
    "does the store I am ALREADY HOLDING carry a valid activation
    receipt?", which private copies and configured roots also need.

    It accepts no pathname and no independently supplied root: the
    directory fd and the database fd are both already held, the sibling
    receipt is read through that same directory fd, identity is checked
    against the held database fd, and the schema is checked on the very
    transaction that will do the writing.
    """
    from core.governance import s7_v2_migration as _migration

    receipt = _migration._read_receipt(dir_fd)
    if receipt is None:
        raise ValueError(
            "S7 v2 table exists but no migration receipt activates it; "
            "creating the table is not permission to write to it"
        )
    stat = os.fstat(store_fd)
    if (
        receipt.get("store_dev") != stat.st_dev
        or receipt.get("store_ino") != stat.st_ino
    ):
        raise ValueError(
            "the migration receipt does not describe the database this "
            "connection holds"
        )
    _migration._validate_receipt(receipt, conn)
    return True


def _table_present(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _auth_table_present(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (_AUTH_TABLE,),
    ).fetchone()
    return row is not None


def _auth_schema_fingerprint(conn: sqlite3.Connection) -> str:
    """Normalized sqlite_master.sql for the auth table, hashed.

    Covers the table, its indexes AND its triggers, because it hashes the
    SQL text rather than enumerating PRAGMA fields.
    """
    import hashlib
    import re

    rows = []
    for kind, name, tbl, sql in conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name=? ORDER BY type,name",
        (_AUTH_TABLE,),
    ):
        canonical = None if sql is None else re.sub(r"\s+", " ", sql).strip().rstrip(";")
        rows.append([kind, name, tbl, canonical])
    payload = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _reference_auth_fingerprint() -> str:
    """The fingerprint the canonical schema produces, built in memory."""
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.executescript(_AUTH_SCHEMA)
        return _auth_schema_fingerprint(conn)


def initialise_authorization_store(db_path: str | Path) -> Path:
    """Create the S7 authorization store. Bootstrap/setup only.

    The single creation authority, deliberately separate from opening.

    IDEMPOTENT-VERIFY:
      absent           -> create
      present, correct -> verify, change nothing
      present, damaged -> REFUSE, never repair

    A dropped table is NOT damage: it leaves exactly the state a
    never-initialised store is in, so refusing it would make first
    initialisation impossible. Damage is a schema that EXISTS and does not
    match -- an added column, a stray index, an altered trigger. Repairing
    such a store would rebuild, unfrozen, a table the migration froze.
    """
    import stat as _stat

    path = Path(db_path)
    reference = _reference_auth_fingerprint()

    # EXISTING store: verify, never repair.
    #
    # An earlier version chmod'd the parent to 0700 BEFORE classifying,
    # which silently repaired directory metadata while leaving an insecure
    # 0644 database untouched -- half the posture fixed, the dangerous half
    # left open, and a caller told everything was fine. Modes are part of
    # what "correct" means, so a wrong mode refuses exactly like a wrong
    # schema.
    if path.exists():
        parent_mode = _stat.S_IMODE(os.stat(path.parent).st_mode)
        db_mode = _stat.S_IMODE(os.stat(path).st_mode)
        if parent_mode != 0o700 or db_mode != 0o600:
            raise ValueError(
                "S7 authorization store has insecure permissions "
                f"(directory {oct(parent_mode)}, database {oct(db_mode)}); "
                "refusing to repair it"
            )
        with closing(sqlite3.connect(path)) as conn:
            if _auth_table_present(conn):
                if _auth_schema_fingerprint(conn) != reference:
                    raise ValueError(
                        "S7 authorization schema does not match the expected "
                        "definition; refusing to repair it"
                    )
                return path

    # FRESH creation: build it private from the start.
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)

    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(_AUTH_SCHEMA)
        cols = {
            str(row[1]) for row in conn.execute(f"PRAGMA table_info({_AUTH_TABLE})")
        }
        if "ceremony_kind" not in cols:
            conn.execute(
                f"ALTER TABLE {_AUTH_TABLE} "
                "ADD COLUMN ceremony_kind TEXT NOT NULL "
                "DEFAULT 'founder_local_webauthn'"
            )
        conn.commit()
    os.chmod(path, 0o600)
    return path


_POST_COMMIT_READ_TOKEN = object()


class _CommittedConsumptionConnection:
    """Capability minted only after a consuming RW transaction commits."""

    __slots__ = ("connection",)

    def __init__(self, connection: sqlite3.Connection, *, _token: object) -> None:
        if _token is not _POST_COMMIT_READ_TOKEN:
            raise ValueError(
                "committed-row reads require the consuming RW connection"
            )
        self.connection = connection


def _read_committed_grant_row_after_commit(
    committed_connection: _CommittedConsumptionConnection,
    artifact_id: str,
) -> CommittedGrantRow | None:
    """Read only through the capability minted after the consuming commit."""
    if not isinstance(committed_connection, _CommittedConsumptionConnection):
        raise ValueError(
            "committed-row reads require the consuming RW connection"
        )
    connection = committed_connection.connection
    if connection.in_transaction:
        raise ValueError("committed grant row cannot be read before commit")
    rows = connection.execute(
        f"""
        SELECT artifact_id,
               request_id,
               request_envelope_hash,
               rendered_text_hash,
               action_params_hash,
               precondition_hash,
               authority_context_hash,
               action,
               derived_work_class,
               derived_aggregation_group,
               nonce,
               credential_ref,
               auth_method,
               grant_source,
               consumed_at,
               ceremony_kind,
               schema_version,
               user_presence,
               user_verification,
               created_at,
               expires_at,
               consumed_by_request_id
        FROM {_V2_AUTH_TABLE}
        WHERE artifact_id = ?
        """,
        (artifact_id,),
    ).fetchall()
    if len(rows) != 1:
        return None
    return CommittedGrantRow(*rows[0])


def consume_for_execution_on_connection(
    connection: sqlite3.Connection,
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
    covenant_ceremony_evidence: CovenantCeremonyEvidence | None = None,
    after_consume_before_commit: Callable[[S7ExecutionGrant], object] | None = None,
) -> tuple[S7ExecutionGrant | None, object | None]:
    """Consume and commit through a caller-held, descriptor-verified RW connection."""
    binding = _require_verified_held_connection(connection)
    if connection.in_transaction:
        raise ValueError("S7 consumption requires an idle held RW connection")
    if not isinstance(rendered, RenderedRequestStatement):
        return None, None
    if superseded_request_ids and rendered.request_id in superseded_request_ids:
        return None, None
    _validate_hash64(action_params_hash, field="action_params_hash")
    _validate_hash64(precondition_hash, field="precondition_hash")
    validate_work_class(derived_work_class)
    if not derived_aggregation_group:
        return None, None
    if not _authority_context_active_for_artifact(authority_context, now=now):
        return None, None
    if not _authority_context_roles_allow_work(authority_context, derived_work_class):
        return None, None
    if not _authority_context_trust_source_allows_artifact(
        authority_context, derived_work_class
    ):
        return None, None
    if not covenant_ceremony_satisfies_request(
        rendered=rendered,
        derived_work_class=derived_work_class,
        evidence=covenant_ceremony_evidence,
        now=now,
    ):
        return None, None
    if _highest_risk_ceremony_required(derived_work_class):
        # Covenant revalidation is mandatory at this seat -- the sole SQL
        # updater -- never a caller callback (design pass 4 §4). It re-derives
        # the two-phase ceremony from the sealed rows and ends with the
        # activation interlock, which refuses until cluster 2b's owner-read
        # receipt exists. Read-only phase store: no creation authority here.
        from core.governance.s7_covenant_ceremony import (
            CovenantCeremonyRefusal,
            CovenantPhaseStore,
        )

        db_row = connection.execute("PRAGMA database_list").fetchone()
        if db_row is None or not db_row[2]:
            return None, None
        try:
            revalidate_store = CovenantPhaseStore(db_row[2], create=False)
            from core.governance.s7_covenant_ceremony import (
                revalidate_covenant_ceremony_for_consumption,
            )

            revalidate_covenant_ceremony_for_consumption(
                connection=connection,
                store=revalidate_store,
                evidence=covenant_ceremony_evidence,
                request_id=rendered.request_id,
                request_envelope_hash=rendered.request_envelope_hash,
                derived_work_class=derived_work_class,
                artifact_id=artifact_id,
                now=now,
            )
        except CovenantCeremonyRefusal:
            return None, None
    auth_hash = authority_context_hash(authority_context)
    if rendered.authority_context_hash != auth_hash:
        return None, None
    if rendered.action_params_hash != action_params_hash:
        return None, None
    if rendered.derived_work_class != derived_work_class:
        return None, None
    if rendered.derived_aggregation_group != derived_aggregation_group:
        return None, None
    now_text = _timestamp_text(now, field="now")
    if not _table_present(connection, _V2_AUTH_TABLE):
        raise S7GuardedExecutionUnavailable(
            "S7 v2 authorization plane is absent; guarded execution "
            "refuses rather than falling back to v1"
        )

    try:
        connection.execute("BEGIN IMMEDIATE")
        _verify_held_store_activation(
            binding.dir_fd, binding.store_fd, connection
        )
        cur = connection.execute(
            f"""
            UPDATE {_V2_AUTH_TABLE}
            SET consumed_at = ?,
                consumed_by_request_id = ?
            WHERE artifact_id = ?
              AND request_id = ?
              AND request_envelope_hash = ?
              AND rendered_text_hash = ?
              AND action = ?
              AND action_params_hash = ?
              AND precondition_hash = ?
              AND authority_context_hash = ?
              AND derived_work_class = ?
              AND derived_aggregation_group = ?
              AND nonce = ?
              AND credential_ref = ?
              AND auth_method = ?
              AND grant_source = ?
              AND ceremony_kind = 'founder_local_webauthn'
              AND user_presence = 1
              AND user_verification IN (0, 1)
              AND (? = 0 OR user_verification = 1)
              AND consumed_at IS NULL
              AND expires_at > ?
            RETURNING action
            """,
            (
                now_text,
                rendered.request_id,
                artifact_id,
                rendered.request_id,
                rendered.request_envelope_hash,
                rendered.rendered_text_hash,
                rendered.action,
                action_params_hash,
                precondition_hash,
                auth_hash,
                derived_work_class,
                derived_aggregation_group,
                rendered.nonce,
                authority_context.credential_ref,
                authority_context.auth_method,
                authority_context.grant_source,
                1 if _webauthn_requires_user_verification(derived_work_class) else 0,
                now_text,
            ),
        )
        matched_row = cur.fetchone()
        if matched_row is None or cur.rowcount != 1:
            connection.rollback()
            return None, None
        grant = _mint_s7_execution_grant(
            artifact_id=artifact_id,
            rendered=rendered,
            stored_action=matched_row[0],
            action_params_hash=action_params_hash,
            precondition_hash=precondition_hash,
            authority_context_hash=auth_hash,
            derived_work_class=derived_work_class,
            derived_aggregation_group=derived_aggregation_group,
            credential_ref=authority_context.credential_ref or "",
            auth_method=authority_context.auth_method,
            grant_source=authority_context.grant_source,
            ceremony_kind="founder_local_webauthn",
            consumed_at=now_text,
        )
        callback_result = (
            after_consume_before_commit(grant)
            if after_consume_before_commit is not None
            else None
        )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise

    return grant, callback_result


def consume_for_execution_with_committed_row(
    connection: sqlite3.Connection,
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
    covenant_ceremony_evidence: CovenantCeremonyEvidence | None = None,
    after_consume_before_commit: Callable[[S7ExecutionGrant], object] | None = None,
) -> tuple[S7ExecutionGrant | None, object | None, CommittedGrantRow | None]:
    """Consume on the held RW connection, then reread its committed row."""
    grant, callback_result = consume_for_execution_on_connection(
        connection,
        artifact_id,
        rendered=rendered,
        action_params_hash=action_params_hash,
        authority_context=authority_context,
        precondition_hash=precondition_hash,
        derived_work_class=derived_work_class,
        derived_aggregation_group=derived_aggregation_group,
        now=now,
        superseded_request_ids=superseded_request_ids,
        covenant_ceremony_evidence=covenant_ceremony_evidence,
        after_consume_before_commit=after_consume_before_commit,
    )
    if grant is None:
        return None, None, None
    committed_connection = _CommittedConsumptionConnection(
        connection, _token=_POST_COMMIT_READ_TOKEN
    )
    committed_row = _read_committed_grant_row_after_commit(
        committed_connection, artifact_id
    )
    return grant, callback_result, committed_row


class S7AuthorizationStore:
    def __init__(self, db_path: str | Path):
        """Open an EXISTING store. Verification only -- never creation.

        This constructor used to mkdir, executescript, ALTER and commit on
        every open, and `daemon/maez_daemon.py` builds it on the live
        request path. That made "the schema I verified" and "the schema I
        created" the same act, and it could resurrect -- unfrozen -- a
        table the v2 migration had deliberately frozen.

        Creation now lives in `initialise_authorization_store`, owned by
        bootstrap/setup.
        """
        self.db_path = Path(db_path)
        # Connections THIS store vended. Per-instance on purpose: a
        # process-global set proves only that some store vended it.
        self._vended: set[int] = set()
        # mode=rw NEVER creates. A plain sqlite3.connect() after an
        # is_file() check is a TOCTOU: if the file disappears in the window
        # between them, connect() silently recreates an EMPTY database and
        # the caller believes it opened the real store.
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=rw", uri=True)
        except sqlite3.OperationalError as exc:
            raise FileNotFoundError(
                f"S7 authorization store is not initialised: {self.db_path.name}"
            ) from exc
        with closing(conn):
            if not _auth_table_present(conn):
                raise ValueError(
                    "S7 authorization store is missing its artifact table; "
                    "opening does not create one"
                )

    @contextmanager
    def anchored_transaction(self):
        """An anchored, activated, single transaction the caller composes
        into.

        The guarded voice-seat writer reserves a voice bundle and inserts
        the artifact atomically. Refusing its connection secured storage by
        killing the only route real minting uses, so the store OWNS the
        transaction instead: identity is bound to a descriptor WE hold, and
        the caller writes inside it.

        Commits on clean exit, rolls back on any exception -- a reservation
        must not survive an artifact insert that failed.
        """
        with _held_store(self.db_path) as (dir_fd, store_fd, conn):
            conn.execute("BEGIN IMMEDIATE")
            _verify_held_store_activation(dir_fd, store_fd, conn)
            vended_token = _S7VendedAnchoredConnectionToken()
            conn._s7_vended_token = vended_token
            # PER-STORE, not process-global: a global set proves only that
            # SOME store vended this connection. Reproduced -- A vended one
            # and B.put(connection=connA) succeeded, writing A.
            self._vended.add(id(conn))
            try:
                yield conn
            except BaseException:
                conn.rollback()
                raise
            else:
                conn.commit()
            finally:
                self._vended.discard(id(conn))
                vended_token.active = False
                conn._s7_vended_token = None

    def _insert_v2(self, conn, artifact, created_at, expires_at, consumed_at):
        """The v2 row. The action and the schema label both come from the
        ARTIFACT; the writer asserts neither."""
        conn.execute(
            f"""
            INSERT INTO {_V2_AUTH_TABLE} (
                artifact_id, request_id, request_envelope_hash,
                rendered_text_hash, action_params_hash, precondition_hash,
                authority_context_hash, derived_work_class,
                derived_aggregation_group, nonce, credential_ref,
                auth_method, grant_source, user_presence,
                user_verification, created_at, expires_at, consumed_at,
                consumed_by_request_id, ceremony_kind, action, schema_version
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                NULL, ?, ?, ?
            )
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
                artifact.ceremony_kind,
                artifact.action,
                artifact.schema_version,
            ),
        )

    def put(
        self,
        artifact: S7AuthorizationArtifact,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        created_at = _timestamp_text(artifact.created_at, field="created_at")
        expires_at = _timestamp_text(artifact.expires_at, field="expires_at")
        consumed_at = (
            _timestamp_text(artifact.consumed_at, field="consumed_at")
            if artifact.consumed_at is not None
            else None
        )
        if connection is not None:
            # A vended anchored connection is the store identity. Reopening
            # ``self.db_path`` here can cross to a replacement inode during a
            # human wait and makes the later write answer a different store.
            v2_present = _table_present(connection, _V2_AUTH_TABLE)
        else:
            with closing(sqlite3.connect(self.db_path)) as probe:
                v2_present = _table_present(probe, _V2_AUTH_TABLE)

        if v2_present:
            # A caller-supplied connection cannot be identity-bound: its
            # held inode is not observable from Python, and PRAGMA reports
            # only a NAME -- repoint that name and another store's receipt
            # authorizes this write. Rather than validate what cannot be
            # pinned, the v2 write runs on OUR anchored connection, with
            # validation and mutation in ONE transaction on it.
            if connection is not None:
                # Only a connection THIS store vended is identity-bound. A
                # foreign one reports a pathname and nothing more.
                if id(connection) not in self._vended:
                    raise ValueError(
                        "v2 authorization writes may not use a "
                        "caller-supplied connection; the database it holds "
                        "cannot be identified"
                    )
                self._insert_v2(
                    connection, artifact, created_at, expires_at, consumed_at
                )
                return
            with self.anchored_transaction() as anchored:
                self._insert_v2(
                    anchored, artifact, created_at, expires_at, consumed_at
                )
            return

        if connection is not None:
            self._put_with_connection(
                connection,
                artifact=artifact,
                created_at=created_at,
                expires_at=expires_at,
                consumed_at=consumed_at,
            )
            return
        with closing(sqlite3.connect(self.db_path)) as conn:
            self._put_with_connection(
                conn,
                artifact=artifact,
                created_at=created_at,
                expires_at=expires_at,
                consumed_at=consumed_at,
            )
            conn.commit()

    def _put_with_connection(
        self,
        conn: sqlite3.Connection,
        *,
        artifact: S7AuthorizationArtifact,
        created_at: str,
        expires_at: str,
        consumed_at: str | None,
    ) -> None:
        # After migration v1 is FROZEN, so a v1 insert aborts with
        # s7_v1_frozen and the artifact has nowhere to go. Storage follows
        # the migrated plane: v2 when it exists, v1 otherwise. The v2 row
        # carries the ACTION, which is the whole reason the plane exists.
        #
        # Scope: this routes STORAGE only. Receipt-gated activation of
        # guarded EXECUTION -- "absent is not permission" -- belongs to the
        # mint and consume seams.
        conn.execute(
            """
            INSERT INTO s7_authorization_artifacts (
                artifact_id, request_id, request_envelope_hash,
                rendered_text_hash, action_params_hash, precondition_hash,
                authority_context_hash, derived_work_class,
                derived_aggregation_group, nonce, credential_ref, auth_method,
                grant_source, user_presence, user_verification, created_at,
                expires_at, consumed_at, consumed_by_request_id, ceremony_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
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
                artifact.ceremony_kind,
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
        covenant_ceremony_evidence: CovenantCeremonyEvidence | None = None,
        before_consume: Callable[[], object] | None = None,
    ) -> bool:
        grant, _result = self.consume_for_execution(
            artifact_id,
            rendered=rendered,
            action_params_hash=action_params_hash,
            authority_context=authority_context,
            precondition_hash=precondition_hash,
            derived_work_class=derived_work_class,
            derived_aggregation_group=derived_aggregation_group,
            now=now,
            superseded_request_ids=superseded_request_ids,
            covenant_ceremony_evidence=covenant_ceremony_evidence,
            after_consume_before_commit=(
                (lambda _grant: before_consume()) if before_consume is not None else None
            ),
        )
        return grant is not None

    def consume_for_execution(
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
        covenant_ceremony_evidence: CovenantCeremonyEvidence | None = None,
        after_consume_before_commit: Callable[[S7ExecutionGrant], object] | None = None,
    ) -> tuple[S7ExecutionGrant | None, object | None]:
        with _held_store(self.db_path) as (dir_fd, store_fd, connection):
            grant, callback_result = consume_for_execution_on_connection(
                connection,
                artifact_id,
                rendered=rendered,
                action_params_hash=action_params_hash,
                authority_context=authority_context,
                precondition_hash=precondition_hash,
                derived_work_class=derived_work_class,
                derived_aggregation_group=derived_aggregation_group,
                now=now,
                superseded_request_ids=superseded_request_ids,
                covenant_ceremony_evidence=covenant_ceremony_evidence,
                after_consume_before_commit=after_consume_before_commit,
            )
            return grant, callback_result


class S7HeldAuthorizationStore(S7AuthorizationStore):
    """S7 mutating facade whose every transaction stays on one held inode.

    Moved here from the cutover script (2026-08-14) so the ceremony's
    exemption-branch store gate can be exact-type against a CLOSED
    two-member set -- {S7AuthorizationStore, S7HeldAuthorizationStore} --
    instead of isinstance, which Codex's cross-lane review showed admits
    arbitrary subclasses that skip the real constructor and override
    write behavior. `opened` is duck-typed on purpose: it must provide
    `require_current_named_identity()`, `_parent_fd` and `_db_fd`, and is
    consulted only at write time, so construction alone touches nothing.
    """

    def __init__(
        self,
        *,
        opened: Any,
        db_path: Path,
    ) -> None:
        self.db_path = Path(db_path)
        self._vended: set[int] = set()
        self._opened = opened

    @contextmanager
    def anchored_transaction(self):
        self._opened.require_current_named_identity()
        connection = _open_s7_connection_from_held_store(
            dir_fd=self._opened._parent_fd,
            store_fd=self._opened._db_fd,
        )
        connection.execute("BEGIN IMMEDIATE")
        _verify_held_store_activation(
            self._opened._parent_fd,
            self._opened._db_fd,
            connection,
        )
        vended_token = _S7VendedAnchoredConnectionToken()
        connection._s7_vended_token = vended_token
        self._vended.add(id(connection))
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            self._vended.discard(id(connection))
            vended_token.active = False
            connection._s7_vended_token = None
            connection.close()


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
    covenant_ceremony_evidence: CovenantCeremonyEvidence | None = None

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
        if self.covenant_ceremony_evidence is not None and not isinstance(
            self.covenant_ceremony_evidence,
            CovenantCeremonyEvidence,
        ):
            raise ValueError("S7 execution covenant_ceremony_evidence is invalid")


def execution_grant_authorizes_action(
    grant: object,
    *,
    action: str,
    params: dict[str, Any] | None,
) -> bool:
    """Return True only when a consumed S7 grant matches this execution."""
    if not isinstance(grant, S7ExecutionGrant):
        return False
    if type(action) is not str:
        return False
    try:
        derived = derive_work_class(action=action, params=params or {})
    except Exception:
        derived = "undeterminable_work_class"
    if derived not in GUARDED_WORK_CLASSES:
        return False
    # EXACT action equality, added to -- never replacing -- the two
    # existing checks. Without it one grant authorized every sibling
    # operation of the same class with identical params.
    return (
        grant.action == action
        and grant.derived_work_class == derived
        and grant.action_params_hash == canonical_hash(params or {})
    )


def _execution_grant_use_key(grant: S7ExecutionGrant) -> tuple[str, str, str, str, str]:
    return (
        grant.artifact_id,
        grant.request_id,
        grant.nonce,
        grant.action_params_hash,
        grant.consumed_at,
    )


def consume_execution_grant_for_action(
    grant: object,
    *,
    action: str,
    params: dict[str, Any] | None,
) -> bool:
    """Consume a minted execution grant exactly once at the action edge."""
    if not execution_grant_authorizes_action(grant, action=action, params=params or {}):
        return False
    assert isinstance(grant, S7ExecutionGrant)
    key = _execution_grant_use_key(grant)
    with _EXECUTION_GRANT_USE_LOCK:
        if key in _USED_EXECUTION_GRANT_KEYS:
            return False
        _USED_EXECUTION_GRANT_KEYS.add(key)
    return True


def execution_grant_authorizes_card_transition(
    grant: object,
    *,
    request_id: str,
    action: str,
    params: dict[str, Any] | None,
    artifact_id: str | None,
) -> bool:
    """Return True only when a consumed grant belongs to this card transition."""
    if not isinstance(grant, S7ExecutionGrant):
        return False
    if not artifact_id:
        return False
    return (
        grant.request_id == request_id
        and grant.artifact_id == artifact_id
        and execution_grant_authorizes_action(grant, action=action, params=params or {})
    )


_S5_ADMISSION_ARTIFACT_KEYS = frozenset({
    "artifact_name",
    "review_id",
    "baseline_id",
    "admitted_fingerprint_hash",
    "operator_origin_marker_hash",
    "review_package_hash",
    "artifact_hash",
})


@dataclass(frozen=True)
class BrainSwapPrecondition:
    schema_version: str
    precondition_kind: str
    s5_admission_artifact_hash: str
    admitted_fingerprint_hash: str
    s5_review_id: str
    s5_baseline_id: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid S7 brain-swap precondition schema_version")
        if self.precondition_kind != "s5_accepted_same_maez_admission":
            raise ValueError("unknown S7 brain-swap precondition kind")
        _validate_hash64(
            self.s5_admission_artifact_hash,
            field="s5_admission_artifact_hash",
        )
        _validate_hash64(self.admitted_fingerprint_hash, field="admitted_fingerprint_hash")
        if not self.s5_review_id:
            raise ValueError("S7 brain-swap precondition requires S5 review id")
        if not self.s5_baseline_id:
            raise ValueError("S7 brain-swap precondition requires S5 baseline id")


def _validated_s5_admission_artifact(artifact: object) -> dict[str, str]:
    if not isinstance(artifact, dict):
        raise ValueError("S7 brain swap requires an S5 admission artifact")
    if set(artifact) != _S5_ADMISSION_ARTIFACT_KEYS:
        raise ValueError("S5 admission artifact is not closed-shape")
    sealed = {key: str(artifact[key]) for key in _S5_ADMISSION_ARTIFACT_KEYS}
    if sealed["artifact_name"] != "s5_candidate_admission.json":
        raise ValueError("S5 admission artifact name mismatch")
    if not sealed["review_id"]:
        raise ValueError("S5 admission artifact review_id is required")
    if not sealed["baseline_id"]:
        raise ValueError("S5 admission artifact baseline_id is required")
    for field in (
        "admitted_fingerprint_hash",
        "operator_origin_marker_hash",
        "review_package_hash",
        "artifact_hash",
    ):
        _validate_hash64(sealed[field], field=field)
    from core.voice_continuity.schema import hash_json

    expected_payload = dict(sealed)
    artifact_hash = expected_payload.pop("artifact_hash")
    if hash_json(expected_payload) != artifact_hash:
        raise ValueError("S5 admission artifact_hash mismatch")
    return sealed


def _s5_admission_artifact_present_in_root(
    sealed_artifact: dict[str, str],
) -> bool:
    from core.voice_continuity import storage as s5_storage

    admissions_dir = Path(s5_storage.VOICE_CONTINUITY_ROOT) / "admissions"
    if not admissions_dir.is_dir():
        return False
    try:
        paths = sorted(admissions_dir.glob("*.json"))
    except OSError:
        return False
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            candidate = _validated_s5_admission_artifact(raw)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if (
            candidate["artifact_hash"] == sealed_artifact["artifact_hash"]
            and candidate["admitted_fingerprint_hash"] == sealed_artifact["admitted_fingerprint_hash"]
            and candidate["review_id"] == sealed_artifact["review_id"]
        ):
            return True
    return False


def build_brain_swap_precondition(
    *,
    s5_admission_artifact: object,
    candidate_fingerprint_hash: str,
) -> BrainSwapPrecondition:
    sealed = _validated_s5_admission_artifact(s5_admission_artifact)
    if not _s5_admission_artifact_present_in_root(sealed):
        raise ValueError("S5 admission artifact is not present in the trusted S5 admission root")
    _validate_hash64(candidate_fingerprint_hash, field="candidate_fingerprint_hash")
    if candidate_fingerprint_hash != sealed["admitted_fingerprint_hash"]:
        raise ValueError("candidate fingerprint does not match S5 admission artifact")
    return BrainSwapPrecondition(
        schema_version=SCHEMA_VERSION,
        precondition_kind="s5_accepted_same_maez_admission",
        s5_admission_artifact_hash=sealed["artifact_hash"],
        admitted_fingerprint_hash=sealed["admitted_fingerprint_hash"],
        s5_review_id=sealed["review_id"],
        s5_baseline_id=sealed["baseline_id"],
    )


def brain_swap_precondition_hash(precondition: BrainSwapPrecondition) -> str:
    if not isinstance(precondition, BrainSwapPrecondition):
        raise ValueError("S7 brain-swap precondition is required")
    return s6.canonical_hash(asdict(precondition))


def brain_swap_execution_precondition_hash(
    precondition: BrainSwapPrecondition,
    *,
    execution_payload: dict[str, Any],
) -> str:
    if not isinstance(precondition, BrainSwapPrecondition):
        raise ValueError("S7 brain-swap precondition is required")
    return s6.canonical_hash({
        "s5_precondition_hash": brain_swap_precondition_hash(precondition),
        "execution_payload_hash": s6.canonical_hash(dict(execution_payload or {})),
    })


def build_brain_swap_work_request_envelope(
    *,
    request_id: str,
    s5_admission_artifact: object,
    candidate_fingerprint_hash: str,
    execution_payload: dict[str, Any],
    action: str,
    requesting_subsystem: str,
    closed_symptom_code: str,
    why_self_fix_failed_class: str,
    affected_refs: tuple[str, ...],
    content_exposure_risk: str,
    created_at: str,
    expires_at: str,
    predicted_effect_class: str,
    rollback_path_class: str,
    maez_voice_consultation_id: str | None,
    free_text_ref_hash: str | None = None,
) -> WorkRequestEnvelope:
    lowered_action = str(action or "").lower()
    if "brain_swap" not in lowered_action and "model_routing" not in lowered_action:
        raise ValueError("S7 brain-swap request must target model routing or brain swap")
    sealed = _validated_s5_admission_artifact(s5_admission_artifact)
    precondition = build_brain_swap_precondition(
        s5_admission_artifact=sealed,
        candidate_fingerprint_hash=candidate_fingerprint_hash,
    )
    payload = dict(execution_payload or {})
    if payload.get("operation") != "brain_swap":
        raise ValueError("S7 brain-swap execution payload must name brain_swap operation")
    if payload.get("candidate_fingerprint_hash") != precondition.admitted_fingerprint_hash:
        raise ValueError("S7 brain-swap execution payload candidate does not match S5 admission")
    if payload.get("s5_admission_artifact_hash") != precondition.s5_admission_artifact_hash:
        raise ValueError("S7 brain-swap execution payload S5 artifact does not match precondition")
    precondition_hash = brain_swap_execution_precondition_hash(
        precondition,
        execution_payload=payload,
    )
    return build_work_request_envelope(
        request_id=request_id,
        action=action,
        params=payload,
        claimed_work_class="self_modification",
        requesting_subsystem=requesting_subsystem,
        closed_symptom_code=closed_symptom_code,
        proposed_change_class="model_routing_change",
        why_self_fix_failed_class=why_self_fix_failed_class,
        affected_refs=tuple(affected_refs),
        content_exposure_risk=content_exposure_risk,
        precondition_hash=precondition_hash,
        created_at=created_at,
        expires_at=expires_at,
        predicted_effect_class=predicted_effect_class,
        rollback_path_class=rollback_path_class,
        maez_voice_consultation_id=maez_voice_consultation_id,
        free_text_ref_hash=free_text_ref_hash,
    )


def brain_swap_execution_authorized(
    *,
    envelope: WorkRequestEnvelope,
    s5_admission_artifact: object,
    candidate_fingerprint_hash: str,
    actual_execution_payload: dict[str, Any],
    execution_authorization: S7ExecutionAuthorization | None,
) -> bool:
    if not isinstance(envelope, WorkRequestEnvelope):
        return False
    if envelope.derived_work_class != "self_modification":
        return False
    if envelope.proposed_change_class != "model_routing_change":
        return False
    try:
        sealed = _validated_s5_admission_artifact(s5_admission_artifact)
        precondition = build_brain_swap_precondition(
            s5_admission_artifact=sealed,
            candidate_fingerprint_hash=candidate_fingerprint_hash,
        )
    except (TypeError, ValueError):
        return False
    payload = dict(actual_execution_payload or {})
    if payload.get("operation") != "brain_swap":
        return False
    if payload.get("candidate_fingerprint_hash") != precondition.admitted_fingerprint_hash:
        return False
    if payload.get("s5_admission_artifact_hash") != precondition.s5_admission_artifact_hash:
        return False
    if envelope.precondition_hash != brain_swap_execution_precondition_hash(
        precondition,
        execution_payload=payload,
    ):
        return False
    if not isinstance(execution_authorization, S7ExecutionAuthorization):
        return False
    if execution_authorization.precondition_hash != envelope.precondition_hash:
        return False
    if execution_authorization.derived_work_class != envelope.derived_work_class:
        return False
    if execution_authorization.derived_aggregation_group != envelope.derived_aggregation_group:
        return False
    rendered = execution_authorization.rendered
    if rendered.request_id != envelope.request_id:
        return False
    if rendered.request_envelope_hash != work_request_envelope_hash(envelope):
        return False
    if s6.canonical_hash(payload) != execution_authorization.action_params_hash:
        return False
    return execution_authorization.store.consume_verified(
        execution_authorization.artifact_id,
        rendered=rendered,
        action_params_hash=execution_authorization.action_params_hash,
        authority_context=execution_authorization.authority_context,
        precondition_hash=execution_authorization.precondition_hash,
        derived_work_class=execution_authorization.derived_work_class,
        derived_aggregation_group=execution_authorization.derived_aggregation_group,
        now=execution_authorization.now,
    )


def _bypass_entry(
    *,
    path: str,
    sort: str,
    required_handling: str,
    maez_runtime_or_helper: bool,
) -> dict[str, object]:
    if not path:
        raise ValueError("S7 bypass inventory path is required")
    if not required_handling:
        raise ValueError("S7 bypass inventory required_handling is required")
    if maez_runtime_or_helper is not True and maez_runtime_or_helper is not False:
        raise ValueError("S7 bypass inventory maez_runtime_or_helper must be bool")
    safe_sort = validate_own_substrate_bypass_sort(sort)
    joined = f"{path} {required_handling}".lower()
    protected_markers = (
        "code",
        "config",
        "soul",
        "model-routing",
        "model routing",
        "covenant-organ",
        "refusal",
        "role-boundary",
        "successor-governance",
        "memory-retention",
        "memory retention",
        "deletion",
        "protection-setting",
        "protection setting",
    )
    if maez_runtime_or_helper and safe_sort == "accepted_limitation":
        if any(marker in joined for marker in protected_markers):
            raise ValueError("Maez-runtime protected write paths cannot be accepted limitations")
    return {
        "path": path,
        "sort": safe_sort,
        "required_handling": required_handling,
        "maez_runtime_or_helper": maez_runtime_or_helper,
    }


def build_own_substrate_bypass_inventory() -> tuple[dict[str, object], ...]:
    """Return the closed D22 inventory of own-substrate bypass surfaces."""
    return (
        _bypass_entry(
            path="SELF_MODIFICATION classifier path",
            sort="gated",
            required_handling="trusted S7 classifier; no caller class authority",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="pending-card approvals",
            sort="gated",
            required_handling="store-level S7 approval and artifact consume for guarded work",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="self-mod dialog terminal states",
            sort="gated",
            required_handling="RATIFIED cannot execute without S7; dialog stage updated after execution",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="cockpit approve endpoints",
            sort="gated",
            required_handling="no literal founder approval; consumes S7 artifact",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="Telegram approval paths",
            sort="gated",
            required_handling="no literal founder approval; consumes S7 artifact",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="direct Maez-runtime ActionEngine calls",
            sort="gated",
            required_handling="guarded actions require S7 gate before action invocation",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path=(
                "autonomous core-memory upkeep (promote_to_core_memory, "
                "update_baseline, daemon core-memory consolidation writes)"
            ),
            sort="detected",
            required_handling=(
                "protected by M-series provenance, content-audit, and "
                "memory-write boundaries; Maez living, not Maez being remade"
            ),
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="dream-state soul writes/proposals",
            sort="gated",
            required_handling="soul-writing is self-modification/covenant-touching",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="write_soul_note",
            sort="gated",
            required_handling="self-modification/covenant-touching classifier result",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="edit_soul_section",
            sort="gated",
            required_handling="self-modification/covenant-touching classifier result",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="model-routing trust-scope edits",
            sort="gated",
            required_handling="trust scope is not authority; model-routing edits require S7",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="prompt writes",
            sort="gated",
            required_handling="prompt changes require covenant_touching_change ceremony",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="prompt-template writes",
            sort="gated",
            required_handling="prompt-template changes require covenant_touching_change ceremony",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="covenant-organ writes",
            sort="gated",
            required_handling="S1-S13 covenant-organ changes require covenant_touching_change ceremony",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="refusal-policy writes",
            sort="gated",
            required_handling="refusal policy changes require covenant_touching_change ceremony",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="role-boundary writes",
            sort="gated",
            required_handling="operator/user role-boundary changes require covenant_touching_change ceremony",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="successor-governance writes",
            sort="gated",
            required_handling="successor-governance changes require covenant_touching_change ceremony",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="memory-retention/deletion writes",
            sort="gated",
            required_handling="memory-retention/deletion changes require covenant_touching_change ceremony",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="protection-setting writes",
            sort="gated",
            required_handling="protection-setting changes require covenant_touching_change ceremony",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="CLI/operator helper writes",
            sort="detected",
            required_handling="reviewed helper contract; non-reviewed helpers cannot mutate guarded targets",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="backup run/verify/rotate",
            sort="gated",
            required_handling="routine custody only when content-free",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="backup restore",
            sort="future_slice",
            required_handling="Track B restore is future scope; founder Track A restore is gated",
            maez_runtime_or_helper=True,
        ),
        _bypass_entry(
            path="manual filesystem/database edits outside Maez runtime",
            sort="accepted_limitation",
            required_handling="named raw OS bypass; S7 cannot stop raw local write access",
            maez_runtime_or_helper=False,
        ),
        _bypass_entry(
            path="manual service edits outside Maez runtime",
            sort="accepted_limitation",
            required_handling="named raw OS bypass; Maez-controlled runtime or helper service edits are gated",
            maez_runtime_or_helper=False,
        ),
    )


def operator_boundary_honesty_banner() -> str:
    """Plain-language D22 warning for operators."""
    return (
        "S7 is not role-encrypted on the founder box. It governs Maez-controlled "
        "runtime or helper paths, including soul/config/model-routing changes, "
        "but it cannot stop raw local write access through raw OS filesystem, "
        "database, or service edits outside Maez's runtime. Those raw OS paths "
        "are accepted limitations, not permission to bypass S7. A hardware-key "
        "touch does not prove the human was uncoerced, does not prove the human "
        "understood the request, does not prove the display was not spoofed, and "
        "does not prove the OS/browser was uncompromised. The live WebAuthn "
        "ceremony is not mounted in S7 v1; guarded self-modification remains "
        "visibly fail-closed and is surfaced as "
        f"{GUARDED_SELF_MODIFICATION_PAUSED_MODE} until S7.1 lands."
    )


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
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.executescript(_WEBAUTHN_CHALLENGE_SCHEMA)

    def put(self, challenge: WebAuthnChallenge) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
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
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
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
    def _stored_bool(value: Any, *, field: str) -> bool:
        if value == 0:
            return False
        if value == 1:
            return True
        raise ValueError(f"{field} must be stored as 0 or 1")

    return WebAuthnCredentialRecord(
        credential_ref=row[0],
        actor_handle_hmac=row[1],
        role_names=tuple(json.loads(row[2])),
        public_key=row[3],
        sign_count=int(row[4]),
        rp_id=row[5],
        origin=row[6],
        created_at=row[7],
        backup_credential=_stored_bool(row[8], field="backup_credential"),
        enabled=_stored_bool(row[9], field="enabled"),
    )


class WebAuthnCredentialRegistry:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.executescript(_WEBAUTHN_CREDENTIAL_SCHEMA)

    def put(self, record: WebAuthnCredentialRecord) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
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
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
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
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
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
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
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
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
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


def register_founder_webauthn_credential_from_response(
    *,
    credential_registry: object | None,
    response: object,
    live_ceremony_enabled: bool | None = None,
) -> WebAuthnCredentialRecord:
    """S7.1 placeholder for production credential registration.

    S7 v1 keeps the grammar and test seam but refuses live registration before
    any credential registry or browser response processing can occur.
    """

    ensure_live_webauthn_ceremony_enabled(
        surface="producer",
        route="register_credential",
        live_ceremony_enabled=live_ceremony_enabled,
    )
    raise NotImplementedError("s7.1_live_webauthn_registration_not_mounted")


def build_local_webauthn_execution_authorization(
    *,
    verifier: object | None,
    credential_registry: object | None,
    challenge_store: object | None,
    request_history_store: object | None,
    artifact_store: object | None,
    live_ceremony_enabled: bool | None = None,
) -> S7AuthorizationArtifact:
    """S7.1 placeholder for production work-on-Maez authorization.

    The default-off check must run before verifier, credential, challenge,
    request-history, or artifact work.
    """

    ensure_live_webauthn_ceremony_enabled(
        surface="producer",
        route="execution_authorization",
        live_ceremony_enabled=live_ceremony_enabled,
    )
    raise NotImplementedError("s7.1_live_webauthn_authorization_not_mounted")


def _webauthn_requires_user_verification(work_class: str) -> bool:
    validate_work_class(work_class)
    return work_class in {
        "founder_credential_management",
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
    action: str
    rendered_text: str
    rendered_text_hash: str
    request_envelope_hash: str
    action_params_hash: str
    authority_context_hash: str
    derived_work_class: str
    proposed_change_class: str
    predicted_effect_class: str
    rollback_path_class: str
    maez_consulted_state: str
    maez_voice_consultation_hash: str | None
    maez_objection_state: str
    maez_unavailable_state: str
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
        validate_action_literal(self.action)
        if not self.rendered_text:
            raise ValueError("S7 rendered_text is required")
        lines = self.rendered_text.splitlines()
        expected_metadata = (
            ("Renderer version: ", f"Renderer version: {self.renderer_version}"),
            ("Surface: ", f"Surface: {self.surface}"),
            ("Origin: ", f"Origin: {self.origin}"),
            ("Request id: ", f"Request id: {self.request_id}"),
            # The visible line MUST equal the field. Without this the
            # record could be relabelled after the owner read it.
            ("Action: ", f"Action: {self.action}"),
            ("Work class: ", f"Work class: {self.derived_work_class}"),
            ("Change class: ", f"Change class: {self.proposed_change_class}"),
            ("Predicted effect class: ", f"Predicted effect class: {self.predicted_effect_class}"),
            ("Rollback path class: ", f"Rollback path class: {self.rollback_path_class}"),
            ("Aggregation group: ", f"Aggregation group: {self.derived_aggregation_group}"),
            ("Maez consulted: ", f"Maez consulted: {self.maez_consulted_state}"),
            (
                "Maez objection present: ",
                f"Maez objection present: {self._rendered_objection_value()}",
            ),
            ("Maez unavailable: ", f"Maez unavailable: {self.maez_unavailable_state}"),
            ("Request envelope hash: ", f"Request envelope hash: {self.request_envelope_hash}"),
            ("Action params hash: ", f"Action params hash: {self.action_params_hash}"),
            ("Authority context hash: ", f"Authority context hash: {self.authority_context_hash}"),
            ("Nonce: ", f"Nonce: {self.nonce}"),
            ("Expires at: ", f"Expires at: {self.expires_at}"),
            (
                "Maez voice consultation hash: ",
                f"Maez voice consultation hash: {self.maez_voice_consultation_hash or 'none'}",
            ),
        )
        for prefix, expected_line in expected_metadata:
            matches = [line for line in lines if line.startswith(prefix)]
            if matches != [expected_line]:
                raise ValueError("S7 rendered metadata does not match signed text")
        if self.rendered_text_hash != rendered_text_hash(self.rendered_text):
            raise ValueError("S7 rendered_text_hash mismatch")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        _validate_hash64(self.action_params_hash, field="action_params_hash")
        _validate_hash64(self.authority_context_hash, field="authority_context_hash")
        validate_work_class(self.derived_work_class)
        _validate_closed_value(
            self.proposed_change_class,
            PROPOSED_CHANGE_CLASSES,
            "proposed_change_class",
        )
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
        _validate_closed_value(
            self.maez_consulted_state,
            MAEZ_CONSULTED_STATES,
            "maez_consulted_state",
        )
        if self.maez_voice_consultation_hash is not None:
            _validate_hash64(
                self.maez_voice_consultation_hash,
                field="maez_voice_consultation_hash",
            )
        _validate_closed_value(
            self.maez_objection_state,
            frozenset({"none", "absent", "present", "unavailable", "not_determined"}),
            "maez_objection_state",
        )
        if not self.maez_unavailable_state:
            raise ValueError("S7 maez_unavailable_state is required")
        if not self.derived_aggregation_group:
            raise ValueError("S7 derived_aggregation_group is required")
        if not self.nonce:
            raise ValueError("S7 nonce is required")
        if not self.expires_at:
            raise ValueError("S7 rendered expires_at is required")
        _canonical_timestamp(self.expires_at)
        _canonical_timestamp(self.rendered_at)

    def _rendered_objection_value(self) -> str:
        if self.maez_objection_state == "present":
            return "yes"
        if self.maez_objection_state == "absent":
            return "no"
        if self.maez_objection_state == "unavailable":
            return "unavailable"
        if self.maez_objection_state == "not_determined":
            return "not determined"
        return "not applicable"


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
    consultation_exemption: Any | None = None,
    durable_cutover_selection: Any | None = None,
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
    if (
        consultation_exemption is not None
        and maez_voice_consultation is not None
    ):
        raise ValueError(
            "S7 request carries both consultation exemption and voice evidence"
        )
    if envelope.derived_work_class in VOICE_SEAT_WORK_CLASSES and (
        consultation_exemption is not None
    ):
        # R11. Voice-seat work normally REQUIRES a consultation, so without
        # this the ceremony has only two options and both are wrong: raise,
        # or sign "Maez consulted: yes" when nothing was asked. The owner
        # reads this line before tapping, so it says plainly that nothing was
        # asked and names the ruling that says why.
        from core.governance.s7_consultation_exemption import (
            born_by_any_signal,
            consultation_exemption_admits,
        )

        # Derived, not hardcoded (full-body audit): every other R11 seam
        # asks born_by_any_signal(); this one passed a literal False, so
        # post-birth the renderer would still print "no consultation was
        # performed, per R11" to the owner before the gate refused.
        if not consultation_exemption_admits(
            envelope=envelope,
            exemption=consultation_exemption,
            durable_cutover_selection=durable_cutover_selection,
            ledger_writes_enabled=born_by_any_signal(),
        ) or action_params_hash != getattr(
            consultation_exemption, "action_params_hash", None
        ):
            raise ValueError("consultation exemption does not admit this request")
        consulted = MAEZ_CONSULTED_NOT_PERFORMED_R11
        # `objection` is DERIVED from the state for the visible line, so it
        # cannot carry prose here without breaking the field/line binding.
        # "nothing was asked" is already carried by the consulted line above.
        objection = "not applicable"
        objection_state = "none"
        unavailable = "no"
    elif envelope.derived_work_class in VOICE_SEAT_WORK_CLASSES:
        if not voice_consultation_satisfies_request(envelope, maez_voice_consultation):
            raise ValueError("voice-seat work requires matching MaezVoiceConsultation")
        assert maez_voice_consultation is not None
        consultation_hash = maez_voice_consultation_hash(maez_voice_consultation)
        consulted = "yes"
        objection_state = maez_voice_consultation.maez_objection_state
        if objection_state == "present":
            objection = "yes"
        elif objection_state == "absent":
            objection = "no"
        else:
            objection = "not determined"
        unavailable = maez_voice_consultation.unavailable_reason_code or "no"

    envelope_hash = work_request_envelope_hash(envelope)
    lines = [
        "S7 work-on-Maez authorization",
        f"Renderer version: {renderer_version}",
        f"Surface: {surface}",
        f"Origin: {origin}",
        f"Request id: {envelope.request_id}",
        # VISIBLE, between Request id and Work class. "What you see is
        # what you sign" cannot be met by a hash the human never reads.
        f"Action: {envelope.action}",
        f"Work class: {envelope.derived_work_class}",
        f"Change class: {envelope.proposed_change_class}",
        f"Predicted effect class: {envelope.predicted_effect_class}",
        f"Rollback path class: {envelope.rollback_path_class}",
        f"Aggregation group: {envelope.derived_aggregation_group}",
        f"Maez consulted: {consulted}",
        f"Maez objection present: {objection}",
        f"Maez unavailable: {unavailable}",
        "Presence limits: key touch does not prove uncoerced consent, "
        "does not prove comprehension, does not prove the display was not spoofed, "
        "and does not prove the OS/browser was uncompromised.",
        f"Request envelope hash: {envelope_hash}",
        f"Action params hash: {action_params_hash}",
        f"Authority context hash: {auth_hash}",
        f"Nonce: {nonce}",
        f"Expires at: {expires_at}",
        f"Maez voice consultation hash: {consultation_hash or 'none'}",
    ]
    rendered_text = "\n".join(lines)
    return RenderedRequestStatement(
        action=envelope.action,
        request_id=envelope.request_id,
        renderer_version=renderer_version,
        surface=surface,
        origin=origin,
        rendered_text=rendered_text,
        rendered_text_hash=rendered_text_hash(rendered_text),
        request_envelope_hash=envelope_hash,
        action_params_hash=action_params_hash,
        authority_context_hash=auth_hash,
        derived_work_class=envelope.derived_work_class,
        proposed_change_class=envelope.proposed_change_class,
        predicted_effect_class=envelope.predicted_effect_class,
        rollback_path_class=envelope.rollback_path_class,
        maez_consulted_state=consulted,
        maez_voice_consultation_hash=consultation_hash,
        maez_objection_state=objection_state,
        maez_unavailable_state=unavailable,
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
    if not ctx.allowed_scopes:
        return False
    if not ctx.surface:
        return False
    if not ctx.credential_ref:
        return False
    if not ctx.created_at:
        return False
    if not ctx.expires_at:
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


# --- v2 migration, re-exported ------------------------------------------
#
# The procedure lives in core/governance/s7_v2_migration.py. It is exposed
# here because this module is the S7 façade every caller already imports;
# the implementation stays separate so migration cannot quietly acquire
# the store's other authorities.
from core.governance.s7_v2_migration import (  # noqa: E402,F401
    S7MigrationRefused,
    _utc_now,
    migrate_authorization_store_to_v2,
)

__all__ = [
    *globals().get("__all__", []),
    "S7MigrationRefused",
    "migrate_authorization_store_to_v2",
]
