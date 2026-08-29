# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The one sanctioned door to FRONTIER_CONSULT as a SOURCE.

Owner-authorized 2026-08-28 (D1 seam 2).

WHY THIS MODULE EXISTS. ``core.dispatcher.inventory`` can report that a
paid source is present, reachable and AUTHORIZATION_REQUIRED. That is a
*report*, and a report is not a gate: ``core.routing.claude_tier.call``
spends for anyone who imports it, and several builder-side components
legitimately do. Reporting alone would leave authorization advisory —
the availability check saying "not authorized" while the spend site
spent. So the gate lives HERE, at the spend site.

AUTHORITY COMES FROM AN OWNER DECISION, NOT A CALLER STRING. The grant
consumed here is an owner-resolved pending card (see
``core.dispatcher.frontier_grant``). An earlier version accepted an
injectable in-process ledger, which meant a forged object could satisfy
the gate and any importer could mint its own authorization. That seam is
deliberately gone: there is no ``ledger=`` parameter to substitute.

SCOPE — read before widening. This does not gate ``claude_tier``
globally. Builder-side machinery (``core.self_dev``, ``core.eval.judge``)
calls the proxy directly and is out of scope: that is the development
harness spending Rohit's quota, a different authority class from Maez
consulting a source.

FAIL-CLOSED ON SPEND. The grant is consumed before the call, so a call
that errors still burns its authorization. Once the request leaves,
nobody can prove whether the external resource was consumed. A retry
needs a new owner decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.dispatcher import frontier_grant
from core.dispatcher.spec import ExternalSource


@dataclass(frozen=True)
class FrontierReply:
    """A frontier answer that still knows where it came from, and who
    authorized paying for it.

    Provenance is not decoration. Anything Maez reasons over from here
    must stay attributable to an external paid model, never mistakable
    for Maez's own thought.
    """

    text: str
    source: ExternalSource
    model: str
    operation: str
    card_id: str
    owner_user_id: str
    input_tokens: int = 0
    output_tokens: int = 0


def consult(
    *,
    prompt,
    card_id: str,
    operation: str,
    purpose: object,
    model: str | None = None,
    system_prompt=None,
    timeout_s: float | None = None,
    store=None,
) -> FrontierReply:
    """Consult the frontier source under one owner-authorized grant.

    Raises ``frontier_grant.GrantRefused`` — issuing NO call — when the
    card is missing, unapproved, expired, already spent, or bound to a
    different source/operation/purpose/model.
    """
    # Consume FIRST, atomically. Nothing below may run unauthorized.
    grant = frontier_grant.consume(
        card_id=card_id,
        source=ExternalSource.FRONTIER_CONSULT,
        operation=operation,
        purpose=purpose,
        model=model,
        store=store,
    )

    from core.routing import claude_tier

    try:
        reply = claude_tier.call(
            prompt=prompt,
            system_prompt=system_prompt,
            model=grant.model or model or "sonnet",
            caller=operation,
            timeout_s=timeout_s,
        )
    except Exception as e:
        # Settle as failed. NOT a refund: the grant stays spent.
        frontier_grant.settle(
            card_id=card_id, ok=False, detail=str(e)[:200], store=store
        )
        raise

    frontier_grant.settle(card_id=card_id, ok=True, store=store)

    # TierReply's real fields are `reply` and `model_used`. There is no
    # `text`, no `model` and no `adapter` on the wire; an earlier version
    # read all three invented names and its test mirrored the same
    # fiction. Read the real attributes so a rename breaks loudly.
    return FrontierReply(
        text=reply.reply,
        source=ExternalSource.FRONTIER_CONSULT,
        model=reply.model_used,
        operation=operation,
        card_id=grant.card_id,
        owner_user_id=grant.owner_user_id,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
    )
