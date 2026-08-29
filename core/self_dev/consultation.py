# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The explicit FRONTIER_CONSULT request from self-development.

Owner-authorized 2026-08-28 (D1 seam 2).

This is where the three semantics meet without collapsing:

  ACTION      self_dev.propose_tests, non-mutating, Lane 0
  SOURCE      FRONTIER_CONSULT, named EXPLICITLY -- generic
              ExternalFanout selection stays reserved, so conversation
              can never wander into a paid consultant
  AUTHORITY   metered_external_resource_use, derived mechanically from
              the request envelope, resolved by a real owner card

The source is asked for availability FIRST, and that ask is
non-consuming: it reads local card state and the proxy's own budget
endpoint, never a completion. Only after it reports
AUTHORIZATION_REQUIRED is a card opened. Nothing here spends.
"""

from __future__ import annotations

from core.dispatcher import frontier_grant
from core.dispatcher.inventory import InventoryRegistry
from core.dispatcher.spec import ExternalSource, SourceAvailability

OPERATION = "self_dev.propose_tests"

#: The consultation model. Named in the card so approval is bounded to
#: the provider actually shown to the owner.
CONSULT_MODEL = "sonnet"


def consultation_purpose(evidence) -> dict:
    """What this consultation is FOR, hashed into the card binding.

    Binding the purpose is what stops an approval for one question from
    funding a different one, so it carries the evidence identity — not
    just the module name.
    """
    return {
        "operation": OPERATION,
        "module": evidence.module,
        "uncovered_functions": sorted(evidence.uncovered_functions),
        "evidence_refs": [r.as_dict() for r in evidence.refs],
    }


def request_frontier_help(*, evidence, reason: str = "", store=None) -> str:
    """Ask the source boundary, then open an owner card if required.

    Returns a human-readable line for cognition. Spends nothing.
    """
    purpose = consultation_purpose(evidence)

    # 1. Ask the SOURCE. Non-consuming by construction.
    inv = InventoryRegistry()
    summary = inv.summarize([ExternalSource.FRONTIER_CONSULT])
    state = summary.source_availability[ExternalSource.FRONTIER_CONSULT]

    if state is not SourceAvailability.RESERVED_UNAVAILABLE:
        # A context-free ask must look reserved; anything else means the
        # generic path widened and this request should not paper over it.
        return (
            f"FRONTIER_CONSULT reported {state.value} on a context-free "
            "availability check, which is not the expected reserved "
            "posture. Refusing to open an authorization card."
        )

    # 2. Open the owner card. The work class must DERIVE from the
    #    envelope; request_authorization refuses if it does not.
    plain = (
        f"Maez is investigating whether {evidence.module} needs another "
        f"test. It found {len(evidence.uncovered_functions)} public "
        f"function(s) with no test calling them "
        f"({', '.join(evidence.uncovered_functions[:4])}). It would like "
        f"one bounded consultation with an external frontier model to "
        f"help shape a candidate test. This spends one Claude "
        f"subscription call and changes nothing in the repository."
    )
    try:
        card = frontier_grant.request_authorization(
            source=ExternalSource.FRONTIER_CONSULT,
            operation=OPERATION,
            purpose=purpose,
            model=CONSULT_MODEL,
            plain_english=plain,
            store=store,
        )
    except frontier_grant.GrantRefused as e:
        return f"FRONTIER_CONSULT authorization could not be requested: {e}"

    return (
        "FRONTIER_CONSULT: AUTHORIZATION_REQUIRED. Opened owner card "
        f"{card.request_id} (work class metered_external_resource_use, "
        f"one call, model {CONSULT_MODEL}). No consultation has happened "
        "and no quota has been spent. Waiting on the owner's decision."
    )
