"""Operator-only, content-free S5 health projection."""

from __future__ import annotations

from typing import Any


HEALTH_MODES = frozenset(
    {
        "disabled",
        "ready",
        "pending_review",
        "preflight_failed",
        "accepted",
        "uncertified",
        "unavailable",
    }
)


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


def _mode_for_state(state: str) -> str:
    if state == "accepted_same_maez":
        return "accepted"
    if state == "uncertified_baseline_missing":
        return "uncertified"
    if state in {"preflight_failed_needs_operator_decision", "rejected_drift"}:
        return "preflight_failed"
    if state == "runner_error_needs_operator_decision":
        return "unavailable"
    if state in {"pending_owner_review", "needs_rewrite", "not_gradable", "unreviewed_live_swap"}:
        return "pending_review"
    return "ready"


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
    accepted_review_id = None
    if current_fingerprint_hash:
        live_state = project_live_swap_status(
            current_fingerprint_hash=current_fingerprint_hash,
            accepted_reviews=accepted_reviews,
            rejected_reviews=rejected_reviews,
        )
        latest_review_state = live_state
        if live_state == "accepted_same_maez":
            for row in accepted_reviews or []:
                if row.get("candidate_fingerprint_hash") == current_fingerprint_hash:
                    accepted_review_id = row.get("review_id")
                    break
        mode = _mode_for_state(live_state)
    else:
        latest_review_state = latest_review_state or "none"
        mode = _mode_for_state(latest_review_state)
    if mode not in HEALTH_MODES:
        mode = "unavailable"
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


def voice_continuity_health(identity_ledger: Any | None = None) -> dict[str, Any]:
    try:
        from core.identity_ledger import IdentityLedger
        from core.voice_continuity.schema import fingerprint_hash

        ledger = identity_ledger or IdentityLedger()
        latest = ledger.latest() or {}
        fingerprint = latest.get("fingerprint") or {}
        return project_voice_continuity_health(
            current_fingerprint_hash=fingerprint_hash(fingerprint) if fingerprint else None,
            latest_identity_event_type=latest.get("event_type"),
            latest_identity_event_id=latest.get("event_id"),
        )
    except Exception as exc:
        return project_voice_continuity_health(
            latest_review_state="runner_error_needs_operator_decision",
            last_error_class=exc.__class__.__name__,
        )
