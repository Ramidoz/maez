"""Baseline sealing for S5 voice continuity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.voice_continuity.schema import (
    BaselinePackage,
    fingerprint_hash,
    hash_json,
    sha256_text,
)


def _require_text(value: object, name: str) -> str:
    text = str(value or "")
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _artifact_hashes(artifact_texts: dict[str, Any]) -> dict[str, str]:
    if not isinstance(artifact_texts, dict):
        raise ValueError("artifact_texts must be a mapping")
    return {f"{key}_sha256": sha256_text(str(value)) for key, value in sorted(artifact_texts.items())}


def seal_baseline(
    *,
    voice_baseline_id: str,
    baseline_kind: str,
    created_at: datetime,
    corpus_version: str,
    rubric_version: str,
    continuity_id: str,
    baseline_fingerprint: dict[str, Any],
    artifact_texts: dict[str, Any],
    owner_attestation: dict[str, Any],
    genesis_limitation: str = "",
    dated_evidence_refs: list[str] | tuple[str, ...] | None = None,
    supersedes_baseline_id: str | None = None,
    supersedes_baseline_hash: str | None = None,
) -> BaselinePackage:
    _require_text(voice_baseline_id, "voice_baseline_id")
    _require_text(corpus_version, "corpus_version")
    _require_text(rubric_version, "rubric_version")
    _require_text(continuity_id, "continuity_id")
    if baseline_kind not in {"genesis", "ordinary"}:
        raise ValueError("baseline_kind must be genesis or ordinary")
    if not isinstance(created_at, datetime):
        raise ValueError("created_at must be datetime")
    if baseline_kind == "ordinary":
        if not supersedes_baseline_id or not supersedes_baseline_hash:
            raise ValueError("ordinary rebaseline requires supersedes id and hash")
        if len(str(supersedes_baseline_hash)) != 64:
            raise ValueError("supersedes hash must be sha256")
    evidence_refs = tuple(str(item) for item in (dated_evidence_refs or ()))
    if baseline_kind == "genesis" and not evidence_refs:
        genesis_limitation = "pre_s5_drift_not_detectable"
    fp_hash = fingerprint_hash(baseline_fingerprint)
    hashes = _artifact_hashes(artifact_texts)
    payload = {
        "voice_baseline_id": voice_baseline_id,
        "baseline_kind": baseline_kind,
        "created_at": created_at,
        "corpus_version": corpus_version,
        "rubric_version": rubric_version,
        "continuity_id": continuity_id,
        "baseline_fingerprint_hash": fp_hash,
        "artifact_hashes": hashes,
        "genesis_limitation": genesis_limitation,
        "dated_evidence_refs": evidence_refs,
        "supersedes_baseline_id": supersedes_baseline_id,
        "supersedes_baseline_hash": supersedes_baseline_hash,
        "owner_attestation_hash": hash_json(owner_attestation or {}),
    }
    return BaselinePackage(
        voice_baseline_id=voice_baseline_id,
        baseline_kind=baseline_kind,
        created_at=created_at,
        corpus_version=corpus_version,
        rubric_version=rubric_version,
        continuity_id=continuity_id,
        baseline_fingerprint=dict(baseline_fingerprint),
        baseline_fingerprint_hash=fp_hash,
        artifact_hashes=hashes,
        baseline_hash=hash_json(payload),
        genesis_limitation=genesis_limitation,
        dated_evidence_refs=evidence_refs,
        supersedes_baseline_id=supersedes_baseline_id,
        supersedes_baseline_hash=supersedes_baseline_hash,
        owner_attestation=dict(owner_attestation or {}),
    )
