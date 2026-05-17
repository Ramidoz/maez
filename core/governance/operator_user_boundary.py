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

from dataclasses import dataclass
from datetime import datetime, timezone

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
    if not _context_active(ctx, now=now):
        return False

    roles = frozenset(ctx.role_names)
    if work_class == "routine_custody":
        return bool(roles & _CUSTODIAN_ROLES)

    # Guarded work requires the later exact-request authorization artifact
    # path. A role-bearing context alone must not become the ceremony.
    return False
