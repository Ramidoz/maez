"""Content-free candidate fingerprint helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.voice_continuity.schema import hash_json, sha256_text


def compute_candidate_fingerprint(
    *,
    model: str,
    model_path: str | None = None,
    soul_hash: str | None = None,
    lora_hash: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not model:
        raise ValueError("model is required")
    payload: dict[str, Any] = {
        "base_model": model,
        "lora_hash": lora_hash,
        "soul_hash": soul_hash,
    }
    if model_path:
        payload["model_path_hash"] = sha256_text(str(Path(model_path)))
    if extra:
        payload["extra_hash"] = hash_json(extra)
    return payload
