# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
core/fast_backend_router.py — Session 11d + 11e, staging-only.

Selects which backend to use for a given fast reply call.

Two-stage decision:

  STAGE 1 — POLICY DECISION (Session 11e)
    Per-trust-scope policy table determines what backends a given caller
    is even ALLOWED to use, regardless of what they asked for. This is
    the gate that keeps "external_guests_local_only" from ever touching
    cloud, even if cloud is env-enabled and the request says backend=cloud.

  STAGE 2 — BACKEND SELECTION (Session 11d)
    Within the policy-allowed set, pick the actual backend by availability.
    Local-first by contract.

Public surface:
    decide_policy(trust_scope, requested_policy)  -> PolicyDecision
    select_backend(decision)                       -> BackendSelection
    generate(prompt, trust_scope, requested_policy, ...) -> (BackendResult, BackendSelection, PolicyDecision)

Policy rules (declarative table; easy to extend):
    maez_local_only                  — the owner's primary scope. Local always.
                                       Cloud requests are downgraded to local.
    maez_cloud_allowed_for_drafting  — the owner's drafting scope where cloud
                                       used to be permitted. As of the
                                       fast-backend cloud retirement slice,
                                       fast-lane cloud requests are downgraded
                                       to local here too.
    external_guests_local_only       — Public/guest scopes. Local always.
                                       Cloud requests are downgraded to local.
                                       If local is unavailable, the request
                                       fails — never silently routed to cloud.
    default                          — Anything not in the table.
                                       Local-only. Cloud fallback is retired.

Local-first principles preserved:
  • memory authority local
  • trust local
  • action authority local
  • identity local

A single boolean — `allow_cloud` — distills the policy outcome for the
backend selector. If allow_cloud is False, the cloud backend is invisible
to selection regardless of env vars.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.fast_backend_local import LocalGemmaBackend, BackendResult

logger = logging.getLogger(__name__)


POLICY_LOCAL = 'local'
POLICY_CLOUD = 'cloud'
POLICY_AUTO  = 'auto'

VALID_POLICIES = (POLICY_LOCAL, POLICY_CLOUD, POLICY_AUTO)


# ── policy table (Session 11e) ────────────────────────────────────────
RULE_MAEZ_LOCAL_ONLY                 = 'maez_local_only'
RULE_MAEZ_CLOUD_ALLOWED_FOR_DRAFTING = 'maez_cloud_allowed_for_drafting'
RULE_EXTERNAL_GUESTS_LOCAL_ONLY      = 'external_guests_local_only'
RULE_DEFAULT                         = 'default'
RETIREMENT_REASON_FAST_LANE_CLOUD = 'fast_lane_cloud_retired'

# Map trust_scope -> rule. Add scopes here as the system grows.
# Keep this table small and explicit; surprises here cause cloud leaks.
#
# Canonical scope names are role-based ("owner", "owner.draft", "guest",
# "public"). The owner's configured user_id (from identity.yaml) also
# resolves to the owner rules via the runtime lookup in `lookup_rule`.
# Legacy scope labels ("rohit", "maez") remain keyed for backwards
# compatibility with the author's existing callers; these will be
# removed once downstream code is migrated.
SCOPE_RULE_TABLE: dict[str, str] = {
    # Canonical role names
    'owner':         RULE_MAEZ_LOCAL_ONLY,
    'owner.draft':   RULE_MAEZ_CLOUD_ALLOWED_FOR_DRAFTING,
    'guest':         RULE_EXTERNAL_GUESTS_LOCAL_ONLY,
    'public':        RULE_EXTERNAL_GUESTS_LOCAL_ONLY,
    # Legacy author-install aliases — kept to avoid breaking the live
    # daemon during the migration window. Safe to remove in v0.2.
    'rohit':         RULE_MAEZ_LOCAL_ONLY,
    'rohit.draft':   RULE_MAEZ_CLOUD_ALLOWED_FOR_DRAFTING,
    'maez':          RULE_MAEZ_LOCAL_ONLY,
}


@dataclass
class PolicyDecision:
    trust_scope:        str       # the scope that was looked up
    rule_fired:         str       # one of RULE_*
    requested_policy:   str       # what the caller asked for
    effective_policy:   str       # what the router will actually use
    allow_cloud:        bool      # gate for the selector
    downgraded:         bool      # True if requested != effective (cloud→local)
    reasons:            list[str] = field(default_factory=list)
    retirement_reason_code: str = ""

    def to_dict(self) -> dict:
        return {
            'trust_scope':      self.trust_scope,
            'rule_fired':       self.rule_fired,
            'requested_policy': self.requested_policy,
            'effective_policy': self.effective_policy,
            'allow_cloud':      self.allow_cloud,
            'downgraded':       self.downgraded,
            'reasons':          list(self.reasons),
            'retirement_reason_code': self.retirement_reason_code,
        }

    def explain(self) -> str:
        """One-line human summary suitable for CLI / logs."""
        line = (
            f"rule={self.rule_fired} requested={self.requested_policy} "
            f"effective={self.effective_policy} allow_cloud={self.allow_cloud}"
        )
        if self.downgraded:
            line += " (downgraded)"
        return line


@dataclass
class BackendSelection:
    backend: object        # duck-typed; LocalGemmaBackend or None after retirement
    name: str
    reason: str            # human-readable explanation of the choice
    # Session 11g — populated only when the cloud branch ran the redactor.
    # None means the redactor did not run (e.g. local backend was selected).
    redaction_telemetry: dict = None  # type: ignore[assignment]
    # 10-B1 — distinguish "policy forbade this backend" from "service
    # was unavailable" when backend is None. The router previously
    # reported both as the same opaque failure; a guest requesting
    # cloud under external_guests_local_only was indistinguishable
    # from a transient local outage in the logs.
    policy_denied: bool = False
    retirement_reason_code: str = ""


def _local() -> LocalGemmaBackend:
    return LocalGemmaBackend()


def _cloud() -> object:
    # Compatibility shim for older regression guards. Selection no longer calls
    # this factory after fast-backend cloud retirement.
    from core.fast_backend_cloud import CloudBackend
    return CloudBackend()


def lookup_rule(trust_scope: str) -> str:
    """Return the rule name for this scope. Falls back to RULE_DEFAULT.

    A trust_scope that matches the owner's configured user_id (from
    core.identity) resolves to the owner's rules even if it isn't
    spelled verbatim in SCOPE_RULE_TABLE. Same for `<owner_id>.draft`.
    """
    if trust_scope in SCOPE_RULE_TABLE:
        return SCOPE_RULE_TABLE[trust_scope]
    try:
        from core.identity import user_profile_id
        owner_id = user_profile_id()
    except Exception:
        owner_id = None
    if owner_id:
        if trust_scope == owner_id:
            return RULE_MAEZ_LOCAL_ONLY
        if trust_scope == f"{owner_id}.draft":
            return RULE_MAEZ_CLOUD_ALLOWED_FOR_DRAFTING
    return RULE_DEFAULT


def decide_policy(trust_scope: str, requested_policy: str = POLICY_AUTO) -> PolicyDecision:
    """STAGE 1 — apply the policy table to the request.

    Returns a PolicyDecision describing what the router will *actually* do,
    along with why. Never raises.
    """
    if requested_policy not in VALID_POLICIES:
        # Treat unknown policies as 'auto' but flag it
        original = requested_policy
        requested_policy = POLICY_AUTO
        reasons = [f'unknown requested policy {original!r} normalized to auto']
    else:
        reasons = []

    rule = lookup_rule(trust_scope)
    decision = PolicyDecision(
        trust_scope=trust_scope,
        rule_fired=rule,
        requested_policy=requested_policy,
        effective_policy=requested_policy,
        allow_cloud=False,
        downgraded=False,
        reasons=reasons,
    )

    if rule == RULE_MAEZ_LOCAL_ONLY:
        decision.allow_cloud = False
        if requested_policy == POLICY_CLOUD:
            decision.effective_policy = POLICY_LOCAL
            decision.downgraded = True
            decision.retirement_reason_code = RETIREMENT_REASON_FAST_LANE_CLOUD
            decision.reasons.append(
                'maez_local_only: cloud request downgraded to local '
                f'({RETIREMENT_REASON_FAST_LANE_CLOUD})'
            )
        elif requested_policy == POLICY_AUTO:
            decision.effective_policy = POLICY_LOCAL
            decision.reasons.append(
                'maez_local_only: auto narrowed to local (no cloud fallback)'
            )
        else:
            decision.reasons.append('maez_local_only: local request honored')
        return decision

    if rule == RULE_MAEZ_CLOUD_ALLOWED_FOR_DRAFTING:
        decision.allow_cloud = False
        decision.reasons.append(
            'maez_cloud_allowed_for_drafting: fast-lane cloud retired '
            f'({RETIREMENT_REASON_FAST_LANE_CLOUD})'
        )
        if requested_policy == POLICY_CLOUD:
            decision.effective_policy = POLICY_LOCAL
            decision.downgraded = True
            decision.retirement_reason_code = RETIREMENT_REASON_FAST_LANE_CLOUD
            decision.reasons.append(
                'cloud request downgraded to local after fast-backend cloud retirement'
            )
        elif requested_policy == POLICY_AUTO:
            decision.effective_policy = POLICY_AUTO
            decision.reasons.append(
                'auto remains local-first with no cloud fallback after retirement'
            )
        else:
            decision.effective_policy = POLICY_LOCAL
            decision.reasons.append('local request honored')
        return decision

    if rule == RULE_EXTERNAL_GUESTS_LOCAL_ONLY:
        decision.allow_cloud = False
        if requested_policy == POLICY_CLOUD:
            decision.effective_policy = POLICY_LOCAL
            decision.downgraded = True
            decision.retirement_reason_code = RETIREMENT_REASON_FAST_LANE_CLOUD
            decision.reasons.append(
                'external_guests_local_only: cloud request downgraded to local '
                f'(guests never reach cloud; {RETIREMENT_REASON_FAST_LANE_CLOUD})'
            )
        elif requested_policy == POLICY_AUTO:
            decision.effective_policy = POLICY_LOCAL
            decision.reasons.append(
                'external_guests_local_only: auto narrowed to local'
            )
        else:
            decision.reasons.append(
                'external_guests_local_only: local request honored'
            )
        return decision

    # RULE_DEFAULT — local-only after fast-backend cloud retirement.
    decision.allow_cloud = False
    decision.reasons.append(
        f'default: fast-lane cloud retired ({RETIREMENT_REASON_FAST_LANE_CLOUD})'
    )
    if requested_policy == POLICY_CLOUD:
        decision.effective_policy = POLICY_LOCAL
        decision.downgraded = True
        decision.retirement_reason_code = RETIREMENT_REASON_FAST_LANE_CLOUD
        decision.reasons.append('cloud request downgraded to local')
    elif requested_policy == POLICY_AUTO:
        decision.effective_policy = POLICY_AUTO
        decision.reasons.append('auto remains local-first with no cloud fallback')
    else:
        decision.effective_policy = POLICY_LOCAL
        decision.reasons.append('local request honored')
    return decision


def select_backend(decision: PolicyDecision) -> BackendSelection:
    """STAGE 2 — given a policy decision, pick the actual backend by availability.
    Never raises. Returns a BackendSelection (backend may be None on failure)."""
    local = _local()

    eff = decision.effective_policy

    if eff == POLICY_LOCAL:
        if local.is_available():
            return BackendSelection(
                backend=local, name=local.name,
                reason=f'effective=local; local available [{decision.rule_fired}]',
            )
        # T1.6: when the policy enforces LOCAL-only and local is
        # unavailable, callers MUST be able to distinguish "policy
        # forbids cloud" from "transient unavailability". Without
        # policy_denied=True, the fast-reply retry path silently
        # promoted the call to cloud (skills/fast_reply_prototype.py
        # downgrade), bypassing the policy gate. Cloud fallback in
        # the LOCAL-only case is a privacy-violation in the
        # maez_local_only scope. policy_denied makes the refusal
        # explicit so retry logic can respect it.
        return BackendSelection(
            backend=None, name='none',
            reason=f'effective=local; local unavailable [{decision.rule_fired}]',
            policy_denied=True,
            retirement_reason_code=decision.retirement_reason_code,
        )

    if eff == POLICY_CLOUD:
        logger.warning(
            "fast_backend_router: cloud effective policy reached after "
            "retirement; refusing (rule_fired=%s)",
            decision.rule_fired,
        )
        return BackendSelection(
            backend=None, name='none',
            reason=(
                f'effective=cloud; fast-lane cloud retired '
                f'({RETIREMENT_REASON_FAST_LANE_CLOUD}) '
                f'[{decision.rule_fired}]'
            ),
            policy_denied=True,
            retirement_reason_code=RETIREMENT_REASON_FAST_LANE_CLOUD,
        )

    # eff == auto — local-first, no cloud fallback after retirement.
    if local.is_available():
        return BackendSelection(
            backend=local, name=local.name,
            reason=f'effective=auto; local available (preferred) [{decision.rule_fired}]',
        )
    _policy_denied = (not decision.allow_cloud) and not local.is_available()
    return BackendSelection(
        backend=None, name='none',
        reason=(
            f'effective=auto; no backend available '
            f'(local down; cloud retired by policy) '
            f'[{decision.rule_fired}]'
        ),
        policy_denied=_policy_denied,
        retirement_reason_code=(
            RETIREMENT_REASON_FAST_LANE_CLOUD if _policy_denied else ""
        ),
    )


def generate(
    prompt: str,
    policy: str = POLICY_AUTO,
    trust_scope: str = 'rohit',
    max_tokens: int = 256,
    temperature: float = 0.4,
    timeout_s: float = 30.0,
) -> tuple[BackendResult, BackendSelection, PolicyDecision]:
    """Route to the policy-selected backend and run a single generation.

    Returns (result, selection, decision) so callers can show:
      • which backend ran
      • why that backend was picked (selection.reason)
      • what policy rule fired and how it shaped the request (decision)

    Never raises. The 11d two-tuple form is preserved by ignoring the
    third element at the call site (Python tuple unpacking).
    """
    decision = decide_policy(trust_scope, policy)
    sel = select_backend(decision)

    if sel.backend is None:
        return (
            BackendResult(
                success=False, text='', backend_name='none',
                model_call_ms=0,
                error=f'no backend available: {sel.reason}',
            ),
            sel,
            decision,
        )

    logger.info(
        "fast_backend_router: selected %s (%s) policy=%s",
        sel.name, sel.reason, decision.explain(),
    )

    prompt_for_backend = prompt
    result = sel.backend.generate(
        prompt_for_backend,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout_s=timeout_s,
    )
    return result, sel, decision
