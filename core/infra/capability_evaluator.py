# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability evaluator (Step 3 of the Decision-19/20 pipeline arc).

Answers ONE question: **"Can Maez responsibly consider this candidate
now?"** — eligible / defer / reject. Does NOT answer "should we
install it" — that belongs to Step 4 (proposal generation + consent
cards).

The evaluator consumes ``CapabilityMatch`` from the gap matcher,
resolves prerequisites against the manual, checks status and
covenant impact, and (if the entry declares hardware requirements)
applies them against ``core.self_knowledge``.

Source-of-truth contract:

  The evaluator uses ``match.entry`` as the source of truth for
  the capability's state. The caller is responsible for producing
  matches from the current manual; stale matches produce stale
  evaluations. Long-running processes that hold matches across
  manual reloads (cockpit, future agent scratchpads) need to
  re-match before re-evaluating if the manual changed.

Hardware dict contract:

  ``hardware: dict | None``. Evaluator reads ONLY these keys:
    - ``vram_available_mb``     int | None — current free VRAM
    - ``vram_total_mb``         int | None — total VRAM (informational)
    - ``current_context_window``int | None — context the loaded brain offers
  Other keys are ignored. Wrong-key dicts behave as if the
  recognized keys were absent (None) — defer rather than crash.

  ``min_vram_mb`` in a manual entry's front-matter is **FREE VRAM
  required at acquisition time**, not total. Capabilities that
  don't load a new model (RLM-style overlays) should declare 0
  or omit the field.

Decision rules (v1):

  • ``status == 'deprecated'``                        → reject
  • internal prereq missing from manual               → defer + blocker
  • internal prereq present but ``status='deprecated'`` → defer + warning
    (transitive deprecation: don't build on a sunset capability)
  • external prereq                                   → info only
  • ``conflicts_with`` non-empty                       → info only
    (skipped pending activation registry; one info reason emitted)
  • ``covenant_touch == 'high'``                       → defer + warning
  • ``consent_card_required``                          → info only
    (proposal stage handles consent flow)
  • ``min_vram_mb`` declared, ``vram_available_mb`` is None → defer
  • ``min_vram_mb`` declared, available < required     → reject
  • ``min_vram_mb`` declared, available ≥ required     → info pass
  • ``min_context_window`` declared, current is None   → defer
  • ``min_context_window`` declared, current < required → reject
  • ``min_context_window`` declared, current ≥ required → info pass
  • No hardware requirement declared                   → info reason

Telemetry: best-effort append to ``logs/capability_evaluator.jsonl``
per evaluation. Write failures are swallowed; evaluation never
fails because the log is unwritable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from core.capability_gap_matcher import CapabilityMatch
    from core.capability_manual import CapabilityEntry, ManualLoadResult

logger = logging.getLogger(__name__)


# ── dataclasses ────────────────────────────────────────────────────


@dataclass
class EvaluationReason:
    """One structured reason from the evaluator. ``severity``
    controls how it factors into the decision; ``info`` is
    informational, ``warning`` flags caveats, ``blocker`` shifts
    the decision off ``eligible``.
    """
    code: str
    severity: Literal["info", "warning", "blocker"]
    message: str
    evidence: dict = field(default_factory=dict)


@dataclass
class CapabilityEvaluation:
    """Structured result of evaluating one match. Step 4 (proposal
    generation) reads ``reasons`` to compose the consent card text
    and ``decision`` to gate whether to propose at all."""
    capability_id: str
    title: str
    match_score: float
    decision: Literal["eligible", "defer", "reject"]
    reasons: list[EvaluationReason]
    missing_prerequisites: list[str]
    external_prerequisites: list[str]
    covenant_touch: str
    consent_card_required: bool
    exact_phrase_ratification: bool
    hardware_snapshot: dict
    entry: object | None  # CapabilityEntry; loose to avoid cycle


# ── reason builders ────────────────────────────────────────────────


def _info(code: str, message: str, **evidence) -> EvaluationReason:
    return EvaluationReason(
        code=code, severity="info", message=message, evidence=evidence,
    )


def _warning(code: str, message: str, **evidence) -> EvaluationReason:
    return EvaluationReason(
        code=code, severity="warning", message=message, evidence=evidence,
    )


def _blocker(code: str, message: str, **evidence) -> EvaluationReason:
    return EvaluationReason(
        code=code, severity="blocker", message=message, evidence=evidence,
    )


# ── core evaluation ────────────────────────────────────────────────


def _evaluate_entry(
    entry: CapabilityEntry,
    *,
    match_score: float,
    manual: ManualLoadResult,
    hardware: dict,
) -> CapabilityEvaluation:
    """Evaluate one entry against manual + hardware context.

    Internal helper — public callers use ``evaluate_match`` /
    ``evaluate_matches``. Pure function on its inputs (no
    self_knowledge call here; caller resolves the snapshot).
    """
    reasons: list[EvaluationReason] = []
    missing_prereqs: list[str] = []

    # 1. Status reject (deprecated entries are not eligible).
    if entry.status == "deprecated":
        reasons.append(_blocker(
            "status_deprecated",
            f"capability {entry.capability_id!r} is deprecated; "
            "rejection is structural",
            status=entry.status,
        ))

    # 2. Prerequisites — internal must exist; transitive
    # deprecation must propagate.
    for prereq_id in entry.prerequisites:
        prereq_entry = manual.find_by_id(prereq_id)
        if prereq_entry is None:
            missing_prereqs.append(prereq_id)
            reasons.append(_blocker(
                "missing_internal_prerequisite",
                f"prerequisite {prereq_id!r} is not in the manual; "
                "either add it as a manual entry or move it to "
                "external_prerequisites if it lives in code",
                prerequisite=prereq_id,
            ))
        elif prereq_entry.status == "deprecated":
            # Transitive deprecation — don't build on sunset.
            reasons.append(_warning(
                "prerequisite_deprecated",
                f"prerequisite {prereq_id!r} is deprecated; "
                "this capability cannot be eligible while it depends "
                "on a sunset capability",
                prerequisite=prereq_id,
            ))

    # 3. External prerequisites — informational only.
    if entry.external_prerequisites:
        reasons.append(_info(
            "external_prerequisites_declared",
            f"capability declares {len(entry.external_prerequisites)} "
            "external (shipped-in-code) prerequisite(s)",
            external_prerequisites=list(entry.external_prerequisites),
        ))

    # 4. Conflicts_with — skipped in v1 (no activation registry).
    if entry.conflicts_with:
        reasons.append(_info(
            "conflicts_check_skipped_no_activation_registry",
            "conflicts_with cannot be meaningfully checked yet — "
            "an activation registry doesn't exist. The declared "
            "conflicts are recorded for the proposal stage to "
            "surface to the owner",
            conflicts_with=list(entry.conflicts_with),
        ))

    # 5. Covenant high touch defers (still a meaningful candidate,
    # but the proposal needs elevated consent).
    if entry.covenant.covenant_touch == "high":
        reasons.append(_warning(
            "covenant_touch_high",
            "this capability has high covenant impact; the proposal "
            "stage will need elevated consent (exact-phrase "
            "ratification or a covenant review)",
            covenant_touch=entry.covenant.covenant_touch,
        ))

    # 6. Consent card required is informational — proposal handles.
    if entry.covenant.consent_card_required:
        reasons.append(_info(
            "consent_card_required",
            "acquisition requires owner approval via consent card "
            "(handled by the proposal stage)",
        ))

    # 7. Hardware checks. Read only the documented keys; treat
    # absent / wrong-key as None.
    min_vram = entry.raw_front_matter.get("min_vram_mb")
    min_ctx = entry.raw_front_matter.get("min_context_window")
    has_hardware_req = (
        isinstance(min_vram, int) and min_vram > 0
    ) or (
        isinstance(min_ctx, int) and min_ctx > 0
    )

    avail_vram = hardware.get("vram_available_mb")
    cur_ctx = hardware.get("current_context_window")

    if isinstance(min_vram, int) and min_vram > 0:
        if avail_vram is None:
            reasons.append(_blocker(
                "vram_unknown",
                f"capability requires {min_vram} MB free VRAM; "
                "available VRAM could not be probed (defer rather "
                "than guess)",
                min_vram_mb=min_vram,
            ))
        elif avail_vram < min_vram:
            reasons.append(_blocker(
                "vram_insufficient",
                f"capability requires {min_vram} MB free VRAM; only "
                f"{avail_vram} MB available",
                min_vram_mb=min_vram,
                available_mb=avail_vram,
            ))
        else:
            reasons.append(_info(
                "vram_sufficient",
                f"available VRAM {avail_vram} MB ≥ required {min_vram} MB",
                min_vram_mb=min_vram,
                available_mb=avail_vram,
            ))

    if isinstance(min_ctx, int) and min_ctx > 0:
        if cur_ctx is None:
            reasons.append(_blocker(
                "context_window_unknown",
                f"capability requires context window of {min_ctx} "
                "tokens; current context window could not be probed",
                min_context_window=min_ctx,
            ))
        elif cur_ctx < min_ctx:
            reasons.append(_blocker(
                "context_window_insufficient",
                f"capability requires context window of {min_ctx} "
                f"tokens; current is {cur_ctx}",
                min_context_window=min_ctx,
                current_context_window=cur_ctx,
            ))
        else:
            reasons.append(_info(
                "context_window_sufficient",
                f"current context window {cur_ctx} ≥ required {min_ctx}",
                min_context_window=min_ctx,
                current_context_window=cur_ctx,
            ))

    if not has_hardware_req:
        reasons.append(_info(
            "no_hardware_requirement_declared",
            "manual entry declares no min_vram_mb or "
            "min_context_window; hardware fit cannot be checked",
        ))

    # 8. Decision: derive from the structural state above.
    decision: Literal["eligible", "defer", "reject"]
    if entry.status == "deprecated":
        decision = "reject"
    elif any(r.code == "vram_insufficient" or
             r.code == "context_window_insufficient"
             for r in reasons):
        decision = "reject"
    elif any(r.code in (
        "missing_internal_prerequisite",
        "prerequisite_deprecated",
        "vram_unknown",
        "context_window_unknown",
        "covenant_touch_high",
    ) for r in reasons):
        decision = "defer"
    else:
        decision = "eligible"

    return CapabilityEvaluation(
        capability_id=entry.capability_id,
        title=entry.title,
        match_score=match_score,
        decision=decision,
        reasons=reasons,
        missing_prerequisites=missing_prereqs,
        external_prerequisites=list(entry.external_prerequisites),
        covenant_touch=entry.covenant.covenant_touch,
        consent_card_required=entry.covenant.consent_card_required,
        exact_phrase_ratification=entry.covenant.exact_phrase_ratification,
        hardware_snapshot=dict(hardware),
        entry=entry,
    )


# ── public API ─────────────────────────────────────────────────────


def evaluate_match(
    match: CapabilityMatch,
    manual: ManualLoadResult | None = None,
    hardware: dict | None = None,
) -> CapabilityEvaluation:
    """Evaluate one ``CapabilityMatch``. ``manual=None`` triggers a
    lazy-cached load of the default manual. ``hardware=None``
    triggers ``core.self_knowledge.summarize()`` once."""
    if manual is None:
        from core.capability_gap_matcher import _get_default_manual
        manual = _get_default_manual()
    if hardware is None:
        from core import self_knowledge
        hardware = self_knowledge.summarize()
    if match.entry is None:
        # Defensive: a match without an attached entry can't be
        # evaluated — return a degenerate reject rather than crash.
        return CapabilityEvaluation(
            capability_id=match.capability_id,
            title=match.title,
            match_score=match.score,
            decision="reject",
            reasons=[_blocker(
                "match_entry_missing",
                "CapabilityMatch.entry is None; cannot evaluate "
                "without the underlying manual entry",
            )],
            missing_prerequisites=[],
            external_prerequisites=[],
            covenant_touch="",
            consent_card_required=False,
            exact_phrase_ratification=False,
            hardware_snapshot=dict(hardware),
            entry=None,
        )
    evaluation = _evaluate_entry(
        match.entry, match_score=match.score,
        manual=manual, hardware=hardware,
    )
    _record_telemetry(evaluation)
    return evaluation


def evaluate_matches(
    matches: list[CapabilityMatch],
    manual: ManualLoadResult | None = None,
    hardware: dict | None = None,
) -> list[CapabilityEvaluation]:
    """Evaluate a list of matches. Resolves ``hardware`` and
    ``manual`` ONCE up front (not per-match) so a 5-match batch
    doesn't trigger 5 nvidia-smi probes."""
    if not matches:
        return []
    if manual is None:
        from core.capability_gap_matcher import _get_default_manual
        manual = _get_default_manual()
    if hardware is None:
        from core import self_knowledge
        hardware = self_knowledge.summarize()
    out: list[CapabilityEvaluation] = []
    for match in matches:
        out.append(evaluate_match(
            match, manual=manual, hardware=hardware,
        ))
    return out


# ── telemetry (best-effort) ───────────────────────────────────────


def _telemetry_path() -> Path:
    try:
        from core import paths as _paths
        return _paths.logs_dir() / "capability_evaluator.jsonl"
    except Exception:  # pragma: no cover — defensive fallback
        return Path("logs/capability_evaluator.jsonl")


def _record_telemetry(evaluation: CapabilityEvaluation) -> None:
    """Best-effort telemetry. ANY failure here is swallowed —
    evaluation must never fail because the log file is unwritable."""
    try:
        blocker_codes = sorted({
            r.code for r in evaluation.reasons if r.severity == "blocker"
        })
        warning_codes = sorted({
            r.code for r in evaluation.reasons if r.severity == "warning"
        })
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "capability_id": evaluation.capability_id,
            "decision": evaluation.decision,
            "match_score": evaluation.match_score,
            "blocker_codes": blocker_codes,
            "warning_codes": warning_codes,
        }
        _append_telemetry(payload)
    except Exception as e:
        logger.debug(
            "capability_evaluator telemetry suppressed: %s", e,
        )


def _append_telemetry(payload: dict) -> None:
    """Append one JSON line. Patched in tests to simulate failure."""
    log_path = _telemetry_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


__all__ = [
    "CapabilityEvaluation",
    "EvaluationReason",
    "evaluate_match",
    "evaluate_matches",
]
