# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The one sanctioned door to FRONTIER_CONSULT as a SOURCE.

Owner-authorized 2026-08-28 (D1 seam 2).

WHY THIS MODULE EXISTS. ``core.dispatcher.inventory`` can now report that
a paid source is present, reachable, and AUTHORIZATION_REQUIRED. That is
a *report*. A report is not a gate: ``core.routing.claude_tier.call``
will spend a paid call for anyone who imports it, and several builder-
side components legitimately do. Reporting alone would leave the grant
advisory — the availability check would say "not authorized" while the
spend site happily spent.

So the gate lives HERE, at the spend site, and this is the ONLY function
through which Maez consults a frontier source. It consumes the bounded
grant BEFORE the proxy is contacted; without a live grant it raises and
no call is issued.

SCOPE — read this before widening it. This does not gate
``claude_tier.call`` globally. Builder-side machinery (``core.self_dev``,
``core.eval.judge``) calls the proxy directly and is out of scope: that
is the development harness spending Rohit's quota, not Maez consulting a
source. Gating those would break them and would confuse two different
semantics. What this guarantees is narrower and honest: *the source
path* cannot spend without a grant.

FAIL-CLOSED ON SPEND. The grant is consumed before the call, so a call
that errors still burns its authorization. That is deliberate — the
alternative (refund on failure) lets a failing loop retry without bound.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.dispatcher.spec import ExternalSource


@dataclass(frozen=True)
class FrontierReply:
    """A frontier answer that still knows where it came from.

    Provenance is not decoration. Anything Maez reasons over from here
    must remain attributable to an external paid model, never mistakable
    for Maez's own thought.
    """

    text: str
    source: ExternalSource
    model: str
    caller: str
    operation: str
    grant_id: str
    input_tokens: int = 0
    output_tokens: int = 0


def consult(
    *,
    prompt,
    caller: str,
    operation: str,
    model: str = "sonnet",
    system_prompt=None,
    timeout_s: float | None = None,
    ledger=None,
) -> FrontierReply:
    """Consult the frontier source under one bounded grant.

    Raises PermissionError -- issuing NO call -- when no live grant
    matches (source, caller, operation).
    """
    if ledger is None:
        # Resolved at call time, not import time, so the active ledger
        # is always the one in force now.
        from core.dispatcher import paid_source_grant

        ledger = paid_source_grant.GRANTS

    # Consume FIRST. Nothing below this line may run unauthorized.
    grant = ledger.consume(
        source=ExternalSource.FRONTIER_CONSULT,
        caller=caller,
        operation=operation,
    )

    from core.routing import claude_tier

    reply = claude_tier.call(
        prompt=prompt,
        system_prompt=system_prompt,
        model=grant.model or model,
        caller=caller,
        timeout_s=timeout_s,
    )

    # TierReply's real fields are `reply` and `model_used` -- there is
    # no `text`, no `model`, and no `adapter` anywhere in the response.
    # An earlier version of this function read all three invented names
    # and its test mirrored the same fiction, so the provenance pin
    # validated an invention rather than the wire shape. Read the real
    # attributes directly so a rename breaks loudly instead of silently
    # producing blank provenance.
    return FrontierReply(
        text=reply.reply,
        source=ExternalSource.FRONTIER_CONSULT,
        model=reply.model_used,
        caller=caller,
        operation=operation,
        grant_id=grant.grant_id,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
    )
