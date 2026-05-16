"""Managed candidate admission artifacts for S5."""

from __future__ import annotations

from typing import Any

from core.voice_continuity.schema import CandidateReviewPackage, hash_json


def emit_admission_artifact(
    review: CandidateReviewPackage,
    *,
    candidate_fingerprint_hash: str,
) -> dict[str, Any]:
    if review.state != "accepted_same_maez":
        raise ValueError("managed admission requires accepted_same_maez review")
    if not review.candidate_fingerprint_hash or candidate_fingerprint_hash != review.candidate_fingerprint_hash:
        raise ValueError("candidate fingerprint does not match accepted review")
    artifact = {
        "artifact_name": "s5_candidate_admission.json",
        "review_id": review.review_id,
        "baseline_id": review.baseline_id,
        "admitted_fingerprint_hash": candidate_fingerprint_hash,
        "review_package_hash": review.review_package_hash,
    }
    artifact["artifact_hash"] = hash_json(artifact)
    return artifact
