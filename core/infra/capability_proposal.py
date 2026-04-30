# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability proposal generator (Step 4 of the Decision-19/20 arc).

Turns eligible CapabilityEvaluation objects into structured
proposal artifacts that can later be routed through Maez's existing
PendingCard approval rails. This stage does ONE thing: prepare a
consent-card-ready payload from an eligible evaluation. It does NOT:

  • install or acquire the capability
  • run field search
  • create or open a PendingCard
  • persist proposals to a DB
  • duplicate the existing self_dev concern infrastructure

Step 4 ships when proposals are well-formed; actual card creation
is Step 4b.

Public API:

  generate_proposal(felt_limitation, evaluation,
                    include_deferred=False)
      → CapabilityProposal | None

  generate_proposals(felt_limitation, evaluations,
                     include_deferred=False)
      → list[CapabilityProposal]

Source contract:

  v1 always emits ``source="manual"`` because v1 only knows about
  the manual. When field search lands (Step 5+), upstream
  CapabilityMatch / CapabilityEvaluation will carry their own
  source, and this module will read it instead of hardcoding.
  Until then: ``source="manual"`` literally.

Reason text contract:

  The ``reason`` field of card_action_payload describes the SOURCE
  of the gap, not a fixed string. v1 says "operator-driven gap
  match: '<query>'" because v1 IS operator-driven. When autonomous
  gap-sensing lands (deferred slice), this string updates to
  describe Maez-detected gaps. Maintainer note for future me.

PendingCardStore.create_card kwargs (verified at
core/decision/pending_cards.py:325):

  Required: action, params
  Optional with defaults: reason, plain_english, audit_verdict,
                          audit_request_id, classification,
                          state_fields, channel, chat_id, user_id

  Our payload uses {action, params, reason, plain_english} —
  forward-callable as ``create_card(**proposal.card_action_payload)``.

No persistence in v1: proposals are pure function output, plus
best-effort telemetry only.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.capability_evaluator import CapabilityEvaluation

logger = logging.getLogger(__name__)


_BODY_EXCERPT_MAX_CHARS = 800

# Strip leading markdown headings when extracting the first
# substantive paragraph. Match `# ...`, `## ...`, etc.
_HEADING_RE = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)


# ── dataclass ──────────────────────────────────────────────────────


@dataclass
class CapabilityProposal:
    """One proposal artifact. Pure function output — not persisted.

    ``actionable=True`` only for ``evaluation_decision='eligible'``
    evaluations. ``include_deferred=True`` callers receive
    explanatory artifacts (decision='defer'/'reject') with
    ``actionable=False`` so the cockpit can surface "why didn't
    this fire?" without misleading the owner that a proposal is
    pending.

    ``card_action_payload`` matches PendingCardStore.create_card
    kwargs exactly — Step 4b will call
    ``store.create_card(**proposal.card_action_payload)``.
    """
    proposal_id: str
    created_at: float
    felt_limitation: str

    capability_id: str
    title: str
    source: str  # "manual" in v1; "field-search" reserved for v1.5+

    match_score: float
    matched_signals: list[str]
    matched_terms: list[str]

    evaluation_decision: str  # "eligible" | "defer" | "reject"
    evaluation_reasons: list[dict]  # serialized EvaluationReason

    prerequisites: list[str]
    external_prerequisites: list[str]

    covenant_touch: str
    consent_card_required: bool
    exact_phrase_ratification: bool

    manual_source_path: str | None
    acquisition: str
    body_excerpt: str
    card_plain_english: str
    card_action_payload: dict

    actionable: bool = False
    entry: object | None = None  # CapabilityEntry; loose to avoid cycle


# ── body excerpt extraction ────────────────────────────────────────


def _first_substantive_paragraph(body: str) -> str:
    """Return the first non-blank paragraph after stripping
    markdown headings, capped at ``_BODY_EXCERPT_MAX_CHARS``."""
    if not body:
        return ""
    # Drop heading lines so they don't count as the "first
    # paragraph."
    stripped = _HEADING_RE.sub("", body)
    # Split on blank-line boundaries.
    paragraphs = [p.strip() for p in stripped.split("\n\n")]
    for para in paragraphs:
        if para and not para.startswith("#"):
            # Collapse internal whitespace for tidier excerpt.
            collapsed = re.sub(r"\s+", " ", para).strip()
            if len(collapsed) > _BODY_EXCERPT_MAX_CHARS:
                return collapsed[:_BODY_EXCERPT_MAX_CHARS - 1].rstrip() + "…"
            return collapsed
    return ""


# ── card text composition ─────────────────────────────────────────


def _compose_card_plain_english(
    *,
    felt_limitation: str,
    title: str,
    body_excerpt: str,
    covenant_touch: str,
    decision: str,
) -> str:
    """Owner-facing explanation. Load-bearing social contract:
    must frame as PROPOSAL, not as already-installed capability."""
    lead = (
        f"This is a proposal to acquire **{title}** — it is "
        "**not yet installed**, and nothing happens unless you "
        "approve via the consent card."
    )
    why = (
        f"\n\nWhy this came up: you said *\"{felt_limitation}\"*, "
        "and this manual entry's gap signals matched."
    )
    if body_excerpt:
        why += f"\n\nWhat it does: {body_excerpt}"
    impact = ""
    if covenant_touch == "high":
        impact = (
            "\n\nThis capability has **high** covenant impact; "
            "approval will require explicit ratification."
        )
    elif covenant_touch == "medium":
        impact = (
            "\n\nThis capability has medium covenant impact; "
            "the consent card will document what will change."
        )
    closer = (
        "\n\nIf you don't want this, no action is needed — the "
        "proposal expires without approval."
    )
    if decision != "eligible":
        closer = (
            f"\n\nNote: this evaluation came back as **{decision}** "
            "(not eligible for direct acquisition). This artifact is "
            "explanatory, not actionable."
        )
    return lead + why + impact + closer


def _compose_card_action_payload(
    *,
    felt_limitation: str,
    capability_id: str,
    source: str,
    manual_source_path: str | None,
    acquisition: str,
    plain_english: str,
) -> dict:
    """Build the create_card-compatible payload. Keys must match
    PendingCardStore.create_card kwargs exactly so a future Step 4b
    can invoke create_card(**payload)."""
    return {
        "action": "capability.acquire",
        "params": {
            "capability_id": capability_id,
            "source": source,
            "manual_source_path": manual_source_path or "",
            "acquisition": acquisition,
        },
        "reason": (
            f"operator-driven gap match: {felt_limitation!r}"
        ),
        "plain_english": plain_english,
    }


# ── core generator ─────────────────────────────────────────────────


def _make_proposal(
    felt_limitation: str,
    evaluation: CapabilityEvaluation,
) -> CapabilityProposal | None:
    """Build a proposal from one evaluation. Caller decides whether
    to include based on decision + include_deferred flag."""
    entry = evaluation.entry
    if entry is None:
        # No underlying entry → can't build a meaningful proposal.
        return None

    body = getattr(entry, "body", "") or ""
    body_excerpt = _first_substantive_paragraph(body)
    manual_source_path = (
        str(entry.source_path)
        if getattr(entry, "source_path", None) is not None
        else None
    )

    plain = _compose_card_plain_english(
        felt_limitation=felt_limitation,
        title=evaluation.title,
        body_excerpt=body_excerpt,
        covenant_touch=evaluation.covenant_touch,
        decision=evaluation.decision,
    )
    payload = _compose_card_action_payload(
        felt_limitation=felt_limitation,
        capability_id=evaluation.capability_id,
        source="manual",  # v1 hardcode; v1.5+ reads from upstream
        manual_source_path=manual_source_path,
        acquisition=getattr(entry, "acquisition", "self-dev"),
        plain_english=plain,
    )

    proposal_id = "prop-" + secrets.token_hex(8)
    return CapabilityProposal(
        proposal_id=proposal_id,
        created_at=time.time(),
        felt_limitation=felt_limitation,
        capability_id=evaluation.capability_id,
        title=evaluation.title,
        source="manual",
        match_score=evaluation.match_score,
        matched_signals=[],  # not threaded through the evaluator yet
        matched_terms=[],
        evaluation_decision=evaluation.decision,
        evaluation_reasons=[
            {
                "code": r.code,
                "severity": r.severity,
                "message": r.message,
                "evidence": r.evidence,
            }
            for r in evaluation.reasons
        ],
        prerequisites=list(getattr(entry, "prerequisites", [])),
        external_prerequisites=list(evaluation.external_prerequisites),
        covenant_touch=evaluation.covenant_touch,
        consent_card_required=evaluation.consent_card_required,
        exact_phrase_ratification=evaluation.exact_phrase_ratification,
        manual_source_path=manual_source_path,
        acquisition=getattr(entry, "acquisition", "self-dev"),
        body_excerpt=body_excerpt,
        card_plain_english=plain,
        card_action_payload=payload,
        actionable=(evaluation.decision == "eligible"),
        entry=entry,
    )


def generate_proposal(
    felt_limitation: str,
    evaluation: CapabilityEvaluation,
    *,
    include_deferred: bool = False,
) -> CapabilityProposal | None:
    """Generate a proposal from a single evaluation.

    By default only ``decision='eligible'`` evaluations produce a
    proposal. ``include_deferred=True`` returns a non-actionable
    explanatory artifact for defer/reject decisions; the cockpit
    uses this to show "why didn't this fire?" without implying a
    pending action.
    """
    if evaluation.decision != "eligible" and not include_deferred:
        _record_telemetry(felt_limitation, evaluation, proposal_id=None)
        return None
    proposal = _make_proposal(felt_limitation, evaluation)
    _record_telemetry(
        felt_limitation, evaluation,
        proposal_id=(proposal.proposal_id if proposal else None),
    )
    return proposal


def generate_proposals(
    felt_limitation: str,
    evaluations: list[CapabilityEvaluation],
    *,
    include_deferred: bool = False,
) -> list[CapabilityProposal]:
    """Generate proposals for a batch of evaluations. Skips
    deferred/rejected by default; ``include_deferred=True`` returns
    non-actionable artifacts for them too."""
    out: list[CapabilityProposal] = []
    for ev in evaluations:
        p = generate_proposal(
            felt_limitation, ev,
            include_deferred=include_deferred,
        )
        if p is not None:
            out.append(p)
    return out


# ── telemetry (best-effort) ───────────────────────────────────────


def _telemetry_path() -> Path:
    try:
        from core import paths as _paths
        return _paths.logs_dir() / "capability_proposal.jsonl"
    except Exception:  # pragma: no cover
        return Path("logs/capability_proposal.jsonl")


def _record_telemetry(
    felt_limitation: str,
    evaluation: CapabilityEvaluation,
    *,
    proposal_id: str | None,
) -> None:
    """Best-effort telemetry. Failures swallowed — proposal
    generation must never fail because the log is unwritable."""
    try:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": felt_limitation,
            "capability_id": evaluation.capability_id,
            "decision": evaluation.decision,
            "proposal_id": proposal_id,
            "generated": proposal_id is not None,
        }
        _append_telemetry(payload)
    except Exception as e:
        logger.debug(
            "capability_proposal telemetry suppressed: %s", e,
        )


def _append_telemetry(payload: dict) -> None:
    """Append one JSON line. Patched in tests to simulate failure."""
    log_path = _telemetry_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


__all__ = [
    "CapabilityProposal",
    "generate_proposal",
    "generate_proposals",
]
