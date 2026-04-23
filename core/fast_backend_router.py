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
                                       fallback is permitted (still subject
                                       to env gate).
    external_guests_local_only       — Public/guest scopes. Local always.
                                       Cloud requests are downgraded to local.
                                       If local is unavailable, the request
                                       fails — never silently routed to cloud.
    default                          — Anything not in the table.
                                       Local-first with cloud fallback only
                                       when local is unavailable AND cloud
                                       is env-enabled.

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
from core.fast_backend_cloud import CloudBackend

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

# Map trust_scope -> rule. Add scopes here as the system grows.
# Keep this table small and explicit; surprises here cause cloud leaks.
SCOPE_RULE_TABLE: dict[str, str] = {
    'rohit':         RULE_MAEZ_LOCAL_ONLY,
    'maez':          RULE_MAEZ_LOCAL_ONLY,
    'rohit.draft':   RULE_MAEZ_CLOUD_ALLOWED_FOR_DRAFTING,
    'guest':         RULE_EXTERNAL_GUESTS_LOCAL_ONLY,
    'public':        RULE_EXTERNAL_GUESTS_LOCAL_ONLY,
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

    def to_dict(self) -> dict:
        return {
            'trust_scope':      self.trust_scope,
            'rule_fired':       self.rule_fired,
            'requested_policy': self.requested_policy,
            'effective_policy': self.effective_policy,
            'allow_cloud':      self.allow_cloud,
            'downgraded':       self.downgraded,
            'reasons':          list(self.reasons),
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
    backend: object        # duck-typed; either LocalGemmaBackend or CloudBackend
    name: str
    reason: str            # human-readable explanation of the choice
    # Session 11g — populated only when the cloud branch ran the redactor.
    # None means the redactor did not run (e.g. local backend was selected).
    redaction_telemetry: dict = None  # type: ignore[assignment]


def _local() -> LocalGemmaBackend:
    return LocalGemmaBackend()


def _cloud() -> CloudBackend:
    return CloudBackend()


def lookup_rule(trust_scope: str) -> str:
    """Return the rule name for this scope. Falls back to RULE_DEFAULT."""
    return SCOPE_RULE_TABLE.get(trust_scope, RULE_DEFAULT)


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
            decision.reasons.append(
                'maez_local_only: cloud request downgraded to local'
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
        decision.allow_cloud = True
        decision.reasons.append(
            'maez_cloud_allowed_for_drafting: cloud permitted (still subject to env gate)'
        )
        # Honor whatever was requested; auto stays auto, local stays local,
        # cloud stays cloud.
        return decision

    if rule == RULE_EXTERNAL_GUESTS_LOCAL_ONLY:
        decision.allow_cloud = False
        if requested_policy == POLICY_CLOUD:
            decision.effective_policy = POLICY_LOCAL
            decision.downgraded = True
            decision.reasons.append(
                'external_guests_local_only: cloud request downgraded to local '
                '(guests never reach cloud)'
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

    # RULE_DEFAULT — historical 11d behavior
    decision.allow_cloud = True
    decision.reasons.append('default: local-first; cloud fallback if local unavailable and env-enabled')
    return decision


def select_backend(decision: PolicyDecision) -> BackendSelection:
    """STAGE 2 — given a policy decision, pick the actual backend by availability.
    Never raises. Returns a BackendSelection (backend may be None on failure)."""
    local = _local()
    cloud = _cloud()

    eff = decision.effective_policy

    if eff == POLICY_LOCAL:
        if local.is_available():
            return BackendSelection(
                backend=local, name=local.name,
                reason=f'effective=local; local available [{decision.rule_fired}]',
            )
        return BackendSelection(
            backend=None, name='none',
            reason=f'effective=local; local unavailable [{decision.rule_fired}]',
        )

    if eff == POLICY_CLOUD:
        if not decision.allow_cloud:
            # Defense-in-depth: should not happen because decide_policy
            # would have downgraded; refuse explicitly anyway.
            return BackendSelection(
                backend=None, name='none',
                reason=(
                    f'effective=cloud but policy disallows cloud [{decision.rule_fired}]'
                ),
            )
        if cloud.is_available():
            return BackendSelection(
                backend=cloud, name=cloud.name,
                reason=f'effective=cloud; cloud enabled [{decision.rule_fired}]',
            )
        return BackendSelection(
            backend=None, name='none',
            reason=(
                f'effective=cloud; cloud disabled or unconfigured '
                f'(set MAEZ_CLOUD_BACKEND_ENABLED=1 and provide an API key) '
                f'[{decision.rule_fired}]'
            ),
        )

    # eff == auto — local-first, cloud only if policy + env both allow
    if local.is_available():
        return BackendSelection(
            backend=local, name=local.name,
            reason=f'effective=auto; local available (preferred) [{decision.rule_fired}]',
        )
    if decision.allow_cloud and cloud.is_available():
        return BackendSelection(
            backend=cloud, name=cloud.name,
            reason=f'effective=auto; local unavailable, cloud fallback [{decision.rule_fired}]',
        )
    return BackendSelection(
        backend=None, name='none',
        reason=(
            f'effective=auto; no backend available '
            f'(local down{"; cloud disallowed by policy" if not decision.allow_cloud else "; cloud also unavailable"}) '
            f'[{decision.rule_fired}]'
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

    # ── Session 11g: cloud redaction guard ──
    # If the selected backend is the cloud backend, run the prompt through
    # core.cloud_redactor.redact_for_cloud and substitute the redacted text.
    # The local backend path is intentionally untouched — perception is
    # already local-only and redaction would just add latency for no gain.
    prompt_for_backend = prompt
    if isinstance(sel.backend, CloudBackend):
        from core.cloud_redactor import redact_for_cloud
        red = redact_for_cloud(prompt)
        prompt_for_backend = red.text
        sel.redaction_telemetry = red.to_telemetry()
        if red.changed:
            logger.info(
                'cloud_redactor: %d redactions applied (pii=%s internal=%s) '
                'before sending to %s',
                red.total_redactions(),
                red.pii_counts, red.internal_counts, sel.name,
            )
        else:
            logger.info('cloud_redactor: no redactions needed for %s', sel.name)

    result = sel.backend.generate(
        prompt_for_backend,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout_s=timeout_s,
    )
    return result, sel, decision
