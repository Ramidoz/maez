"""Storage-boundary helpers for S5 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VOICE_CONTINUITY_ROOT = Path("memory") / "voice_continuity"
ADMISSIONS_DIRNAME = "admissions"
REVIEWS_DIRNAME = "reviews"
_TEXT_KEYS = {"prompt_text", "reply_text", "transcript", "candidate_reply", "baseline_reply"}


def validate_git_visible_artifact(artifact: dict[str, Any]) -> bool:
    encoded_keys = set(artifact)
    if encoded_keys & _TEXT_KEYS:
        raise ValueError("git-visible S5 artifacts may carry hashes only")
    return True


def _read_json_artifacts(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    artifacts: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"S5 artifact must be a JSON object: {path}")
        artifacts.append(raw)
    return artifacts


def load_admitted_fingerprint_rows(
    root: str | Path = VOICE_CONTINUITY_ROOT,
) -> list[dict[str, str]]:
    """Return content-free rows proving which candidate fingerprints were admitted."""
    rows: list[dict[str, str]] = []
    for artifact in _read_json_artifacts(Path(root) / ADMISSIONS_DIRNAME):
        if artifact.get("artifact_name") != "s5_candidate_admission.json":
            continue
        fingerprint_hash = str(artifact.get("admitted_fingerprint_hash") or "")
        review_id = str(artifact.get("review_id") or "")
        if not fingerprint_hash or not review_id:
            raise ValueError("admission artifact requires review_id and admitted_fingerprint_hash")
        rows.append({"review_id": review_id, "candidate_fingerprint_hash": fingerprint_hash})
    return rows


def load_rejected_fingerprint_rows(
    root: str | Path = VOICE_CONTINUITY_ROOT,
) -> list[dict[str, str]]:
    """Return content-free rows for reviewed candidate fingerprints rejected as drift."""
    rows: list[dict[str, str]] = []
    for artifact in _read_json_artifacts(Path(root) / REVIEWS_DIRNAME):
        if artifact.get("state") != "rejected_drift":
            continue
        fingerprint_hash = str(artifact.get("candidate_fingerprint_hash") or "")
        review_id = str(artifact.get("review_id") or "")
        if not fingerprint_hash or not review_id:
            raise ValueError("rejected review artifact requires review_id and candidate_fingerprint_hash")
        rows.append({"review_id": review_id, "candidate_fingerprint_hash": fingerprint_hash})
    return rows
