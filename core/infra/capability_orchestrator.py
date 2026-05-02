# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""D20 capability-acquisition orchestrator — fires-on-felt-gap.

The 4-agent audit on 2026-05-02 confirmed every stage-2..4 module
of the capability-acquisition pipeline (ADR-0021) is shipped and
unit-tested but no runtime caller wires them together. This module
is that wire — given a felt-limitation string, walk it through:

    Stage 2  match_gap            core/infra/capability_gap_matcher
    Stage 3  evaluate_matches     core/infra/capability_evaluator
    Stage 4  generate_proposals   core/infra/capability_proposal
    Stage 4b create pending card  core/decision/pending_cards

…and return a single OrchestrationResult carrying every stage's
output. Stage 5 (queue → planner → activation) already has its
own runtime path through action_engine._do_capability_acquire
once the operator approves the card.

Stage 1 (autonomous gap-sensing from chat / memory / failures)
is deliberately out of scope here. The first version takes a
caller-provided felt-limitation string. A later slice can add
producers that detect gaps from chat surface, audit failures, or
memory-consolidation anomalies and feed them into this orchestrator.

Why dependency-injection (pending_card_store, hardware) over
module-globals: tests need hermetic temp DBs and pinned hardware
snapshots; production callers pass the live store and let
hardware default-resolve via core.self_knowledge.

Failure mode: never raises on bad input. Empty / unmatched / no-
proposals cases all return a populated OrchestrationResult with
the relevant fields empty so callers can log + display each
stage's outcome uniformly.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from core.infra.capability_evaluator import evaluate_matches
from core.infra.capability_gap_matcher import match_gap
from core.infra.capability_proposal import generate_proposals

logger = logging.getLogger("maez.capability_orchestrator")


@dataclass
class OrchestrationResult:
    """Output of one orchestration pass — one felt-limitation in,
    every stage's output out. Callers log this for telemetry,
    display it on the operator surface, or feed it back into a
    diagnostic.

    cards_created: list of PendingCard.request_id strings, one
        per eligible proposal that produced a card.
    cards_skipped: list of (capability_id, reason) tuples for
        proposals that did NOT produce a card — typically because
        the proposal's decision is 'defer' or 'reject', or because
        consent_card_required is False on the manual entry.
    stage_errors: list of (stage_name, error_str) tuples populated
        when an upstream pipeline call raised. Lets the caller
        distinguish "no matches" from "matcher crashed" without
        breaking the never-raise contract.
    """
    felt_limitation: str
    matches: list = field(default_factory=list)
    evaluations: list = field(default_factory=list)
    proposals: list = field(default_factory=list)
    cards_created: list[str] = field(default_factory=list)
    cards_skipped: list[tuple[str, str]] = field(default_factory=list)
    stage_errors: list[tuple[str, str]] = field(default_factory=list)


def orchestrate_from_felt_limitation(
    felt_limitation: str,
    *,
    pending_card_store: Any = None,
    manual: Any = None,
    hardware: Optional[dict] = None,
    include_deferred: bool = False,
    chat_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 5,
    source: str = "capability_orchestrator",
) -> OrchestrationResult:
    """Walk one felt-limitation through stages 2 → 3 → 4 → 4b.

    Args:
        felt_limitation: a natural-language string describing what
            Maez can't currently do. From an operator command in
            v1; later slices may auto-detect from chat/audit.
        pending_card_store: when present, eligible proposals
            produce real cards via store.create_card(). When None,
            proposals are returned without card creation
            (dry-run / diagnostic mode).
        manual: optional pre-loaded ManualLoadResult; when None,
            the matcher loads the default at docs/maez_manual/.
        hardware: optional hardware snapshot dict; when None, the
            evaluator probes via core.self_knowledge.summarize().
            Pin in tests so vram numbers don't depend on the
            test machine.
        include_deferred: pass through to generate_proposals — by
            default deferred/rejected proposals are skipped; this
            flag returns non-actionable proposals for diagnostic
            purposes (no cards are created for them either way).
        chat_id, user_id: forwarded to create_card so the card is
            properly attributed to the surface that requested it.
        limit: cap on matches considered (default 5, matching the
            matcher's own default).
        source: synthetic chat_id used when ``chat_id`` is None.
            PendingCardStore.create_card supersedes prior
            open/deferred cards in the same chat_id; without a
            synthetic source, two back-to-back operator runs would
            stack two open cards for the same capability. Default
            "capability_orchestrator" gives operator-CLI runs a
            stable supersession bucket.
    """
    result = OrchestrationResult(felt_limitation=felt_limitation)

    if not felt_limitation or not felt_limitation.strip():
        return result

    try:
        result.matches = match_gap(
            felt_limitation, manual=manual, limit=limit,
        )
    except Exception as e:
        logger.warning(
            "capability_orchestrator: match_gap failed on %r: %s",
            felt_limitation, e,
        )
        result.stage_errors.append(("match_gap", str(e)))
        return result

    if not result.matches:
        return result

    try:
        result.evaluations = evaluate_matches(
            result.matches, manual=manual, hardware=hardware,
        )
    except Exception as e:
        logger.warning(
            "capability_orchestrator: evaluate_matches failed: %s", e,
        )
        result.stage_errors.append(("evaluate_matches", str(e)))
        return result

    try:
        result.proposals = generate_proposals(
            felt_limitation, result.evaluations,
            include_deferred=include_deferred,
        )
    except Exception as e:
        logger.warning(
            "capability_orchestrator: generate_proposals failed: %s", e,
        )
        result.stage_errors.append(("generate_proposals", str(e)))
        return result

    if pending_card_store is None:
        return result

    # Pin a synthetic chat_id so successive operator runs supersede
    # rather than stack — see kwarg docstring above for rationale.
    effective_chat_id = chat_id if chat_id is not None else source

    for p in result.proposals:
        # `actionable` is the proposal module's authoritative gate —
        # True only for evaluation_decision='eligible'. Don't second-
        # guess it here; the proposal generator already encodes the
        # eligible/defer/reject policy.
        if not p.actionable:
            result.cards_skipped.append(
                (p.capability_id,
                 f"non-actionable (decision={p.evaluation_decision})"),
            )
            continue
        if not p.consent_card_required:
            result.cards_skipped.append(
                (p.capability_id, "consent_card_required=False"),
            )
            continue
        try:
            card = pending_card_store.create_card(
                **p.card_action_payload,
                chat_id=effective_chat_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(
                "capability_orchestrator: create_card failed for "
                "capability_id=%s: %s",
                p.capability_id, e,
            )
            result.cards_skipped.append(
                (p.capability_id, f"create_card_error: {e}"),
            )
            result.stage_errors.append(("create_card", str(e)))
            continue
        # CardRecord exposes request_id via attribute; PendingCardStore
        # may evolve to return a dict in the future, so handle both.
        rid = getattr(card, "request_id", None)
        if rid is None and isinstance(card, dict):
            rid = card.get("request_id")
        if rid:
            result.cards_created.append(rid)

    return result
