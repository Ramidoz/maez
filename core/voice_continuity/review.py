"""Candidate review state transitions for S5 v1."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.voice_continuity.schema import (
    _ACCEPTED_STATE_TOKEN,
    BaselinePackage,
    CandidateReviewPackage,
    OwnerOriginMarker,
    fingerprint_hash,
    validate_owner_marker_binding,
    validate_preflight_outcome,
    validate_run_level_owner_verdict,
)

_EXPECTED_CORPUS = "s5.signature.v1"
_EXPECTED_RUBRIC = "s5.rubric.v1"


def review_state_from_preflight(outcome: str) -> str:
    validate_preflight_outcome(outcome)
    return {
        "preflight_passed_needs_owner_review": "pending_owner_review",
        "preflight_failed_needs_operator_decision": "preflight_failed_needs_operator_decision",
        "runner_error_needs_operator_decision": "runner_error_needs_operator_decision",
        "baseline_missing_uncertified": "uncertified_baseline_missing",
        "not_gradable_needs_owner_review": "not_gradable",
    }[outcome]


def create_candidate_review(
    *,
    review_id: str,
    created_at: datetime,
    event_type: str,
    state: str,
    baseline_id: str | None,
    corpus_version: str,
    rubric_version: str,
    candidate_fingerprint: dict[str, Any] | None,
    candidate_endpoint: dict[str, Any],
    preflight_outcome: str,
    identity_event_id: int | None = None,
    continuity_id: str | None = None,
    owner_review: dict[str, Any] | None = None,
    admission: dict[str, Any] | None = None,
) -> CandidateReviewPackage:
    if corpus_version != _EXPECTED_CORPUS or rubric_version != _EXPECTED_RUBRIC:
        preflight_outcome = "preflight_failed_needs_operator_decision"
        state = "preflight_failed_needs_operator_decision"
    if state == "accepted_same_maez" and not owner_review:
        raise ValueError("accepted state requires owner verdict evidence")
    if state != "uncertified_baseline_missing":
        if not baseline_id:
            raise ValueError("baseline_id is required")
        if not candidate_fingerprint:
            raise ValueError("candidate_fingerprint is required")
    fp_hash = fingerprint_hash(candidate_fingerprint) if candidate_fingerprint else None
    return CandidateReviewPackage(
        review_id=str(review_id),
        created_at=created_at,
        event_type=event_type,
        state=state,
        baseline_id=baseline_id,
        corpus_version=corpus_version,
        rubric_version=rubric_version,
        candidate_fingerprint=dict(candidate_fingerprint or {}),
        candidate_fingerprint_hash=fp_hash,
        candidate_endpoint=dict(candidate_endpoint or {}),
        preflight_outcome=preflight_outcome,
        identity_event_id=identity_event_id,
        continuity_id=continuity_id,
        owner_review=owner_review,
        admission=admission,
    )


def apply_owner_verdict(
    review: CandidateReviewPackage,
    verdict: str,
    *,
    operator_origin_marker: dict[str, Any] | OwnerOriginMarker | None = None,
    required_slots_resolved: bool = False,
) -> CandidateReviewPackage:
    if verdict == "":
        return review
    validate_run_level_owner_verdict(verdict)
    marker = OwnerOriginMarker.from_value(operator_origin_marker) if operator_origin_marker else None
    if not marker:
        raise ValueError("owner verdict requires operator origin marker")
    validate_owner_marker_binding(
        marker,
        review_id=review.review_id,
        baseline_id=review.baseline_id,
        review_package_hash=review.review_package_hash,
    )
    if verdict == "accepted_same_maez":
        if review.state != "pending_owner_review":
            raise ValueError("only pending reviews can be accepted")
        if review.preflight_outcome != "preflight_passed_needs_owner_review":
            raise ValueError("acceptance requires preflight pass artifact")
        if not required_slots_resolved:
            raise ValueError("acceptance requires resolved review slots or waiver")
    owner_review = {
        "run_level_verdict": verdict,
        "review_id": review.review_id,
        "baseline_id": review.baseline_id or "",
        "review_package_hash": review.review_package_hash,
        "operator_origin_marker_hash": marker.marker_hash,
        "origin": marker.origin,
    }
    if verdict == "accepted_same_maez":
        return review.with_updates(
            state=verdict,
            owner_review=owner_review,
            _accepted_state_token=_ACCEPTED_STATE_TOKEN,
        )
    return review.with_updates(state=verdict, owner_review=owner_review)


def validate_baseline_for_review(
    baseline: BaselinePackage,
    *,
    review_started_at: datetime,
) -> bool:
    if not isinstance(baseline, BaselinePackage):
        raise ValueError("sealed S5 baseline package is required")
    if baseline.created_at >= review_started_at:
        raise ValueError("baseline must predate candidate review")
    return True


def nontechnical_review_mode_status() -> str:
    return "future_scope"
