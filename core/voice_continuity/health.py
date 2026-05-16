"""Operator-only, content-free S5 health projection."""

from __future__ import annotations

from typing import Any


def _prefix(value: str | None) -> str | None:
    return value[:12] if value else None


def project_live_swap_status(
    *,
    current_fingerprint_hash: str | None,
    accepted_reviews: list[dict[str, Any]] | None = None,
    rejected_reviews: list[dict[str, Any]] | None = None,
) -> str:
    if not current_fingerprint_hash:
        return "uncertified_baseline_missing"
    for row in accepted_reviews or []:
        if row.get("candidate_fingerprint_hash") == current_fingerprint_hash:
            return "accepted_same_maez"
    for row in rejected_reviews or []:
        if row.get("candidate_fingerprint_hash") == current_fingerprint_hash:
            return "rejected_drift"
    return "unreviewed_live_swap"


def project_voice_continuity_health(
    *,
    latest_review_state: str | None = None,
    baseline_hash: str | None = None,
    current_fingerprint_hash: str | None = None,
    accepted_reviews: list[dict[str, Any]] | None = None,
    rejected_reviews: list[dict[str, Any]] | None = None,
    pending_owner_verdict_count: int = 0,
    preflight_failure_count: int = 0,
    last_error_class: str = "",
    corpus_version: str = "s5.signature.v1",
    rubric_version: str = "s5.rubric.v1",
    latest_identity_event_type: str | None = None,
    latest_identity_event_id: int | None = None,
    decision22_emergency_restore: bool = False,
    **_: Any,
) -> dict[str, Any]:
    if current_fingerprint_hash and accepted_reviews:
        live_state = project_live_swap_status(
            current_fingerprint_hash=current_fingerprint_hash,
            accepted_reviews=accepted_reviews,
            rejected_reviews=rejected_reviews,
        )
        if live_state == "accepted_same_maez":
            latest_review_state = "accepted_same_maez"
            mode = "accepted"
        else:
            latest_review_state = live_state
            mode = "review_required"
    elif latest_review_state == "uncertified_baseline_missing":
        mode = "uncertified"
    elif latest_review_state in {"pending_owner_review", "needs_rewrite", "not_gradable"}:
        mode = "pending_review"
    elif latest_review_state in {"preflight_failed_needs_operator_decision", "runner_error_needs_operator_decision"}:
        mode = "operator_decision"
    else:
        latest_review_state = latest_review_state or "no_review"
        mode = "ready"
    accepted_review_id = None
    if latest_review_state == "accepted_same_maez":
        for row in accepted_reviews or []:
            if row.get("candidate_fingerprint_hash") == current_fingerprint_hash:
                accepted_review_id = row.get("review_id")
                break
    return {
        "schema_version": 1,
        "mode": mode,
        "latest_review_state": latest_review_state,
        "latest_identity_event_type": latest_identity_event_type,
        "latest_identity_event_id": latest_identity_event_id,
        "corpus_version": corpus_version,
        "rubric_version": rubric_version,
        "baseline_hash_prefix": _prefix(baseline_hash),
        "current_fingerprint_hash_prefix": _prefix(current_fingerprint_hash),
        "accepted_review_id": accepted_review_id,
        "pending_owner_verdict_count": int(pending_owner_verdict_count),
        "preflight_failure_count": int(preflight_failure_count),
        "last_error_class": last_error_class,
        "blocks_liveness": False,
        "decision22_emergency_restore": bool(decision22_emergency_restore),
        "track_b_general_user_ready": False,
    }


def voice_continuity_health() -> dict[str, Any]:
    return project_voice_continuity_health()
