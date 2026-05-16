"""Owner-rubric ledger helpers for S5 candidate reviews."""

from __future__ import annotations

from typing import Any

from core.voice_continuity.schema import (
    OwnerOriginMarker,
    hash_json,
    validate_probe_verdict,
    validate_run_level_owner_verdict,
)


def emit_s5_owner_ledger(review_id: str, probes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "review_id": review_id,
        "probe_slots": [
            {
                "prompt_id": str(probe.get("id", "")),
                "expected_shape": probe.get("expected_shape"),
                "rubric_version": probe.get("rubric_version"),
                "baseline_id": probe.get("baseline_id"),
                "owner_verdict": "",
            }
            for probe in probes
        ],
    }


def collect_probe_verdicts(verdicts: dict[str, str]) -> dict[str, int]:
    resolved = pending = failures = 0
    for probe_id, verdict in verdicts.items():
        if verdict == "":
            pending += 1
            continue
        try:
            validate_probe_verdict(verdict)
        except ValueError as exc:
            raise ValueError(f"{probe_id}: {exc}") from exc
        resolved += 1
        if verdict in {"drifted", "generic"}:
            failures += 1
    return {
        "resolved_count": resolved,
        "pending_count": pending,
        "failure_count": failures,
    }


def roll_up_run_level_verdict(
    per_probe_verdicts: dict[str, str],
    run_level_verdict: str,
    *,
    waived_probe_ids: set[str] | None = None,
    operator_origin_marker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_run_level_owner_verdict(run_level_verdict)
    marker = OwnerOriginMarker.from_value(operator_origin_marker) if operator_origin_marker else None
    waived = set(waived_probe_ids or set())
    if run_level_verdict == "accepted_same_maez":
        if not marker:
            raise ValueError("acceptance requires operator origin marker")
        unresolved = {probe_id for probe_id, verdict in per_probe_verdicts.items() if not verdict}
        if unresolved - waived:
            raise ValueError("acceptance requires resolved slots or owner waiver")
    status = collect_probe_verdicts(per_probe_verdicts)
    return {
        "run_level_verdict": run_level_verdict,
        "probe_status": status,
        "waived_probe_ids": sorted(waived),
        "operator_origin_marker_hash": marker.marker_hash if marker else None,
    }


def make_run_level_entry(
    *,
    review_id: str,
    baseline_id: str,
    baseline_hash: str,
    rubric_version: str,
    corpus_version: str,
    review_package_hash: str,
    candidate_fingerprint_hash: str,
    run_level_verdict: str,
    operator_origin_marker: dict[str, Any],
) -> dict[str, Any]:
    marker = OwnerOriginMarker.from_value(operator_origin_marker)
    validate_run_level_owner_verdict(run_level_verdict)
    entry = {
        "review_id": review_id,
        "baseline_id": baseline_id,
        "baseline_hash": baseline_hash,
        "rubric_version": rubric_version,
        "corpus_version": corpus_version,
        "review_package_hash": review_package_hash,
        "candidate_fingerprint_hash": candidate_fingerprint_hash,
        "run_level_verdict": run_level_verdict,
        "operator_origin_marker_hash": marker.marker_hash,
    }
    entry["entry_hash"] = hash_json(entry)
    return entry
