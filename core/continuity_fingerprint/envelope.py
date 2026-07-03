"""Minimal A2 probe envelope.

A2 samples Maez through the actually-applied persistent prompt frame mode, while
stripping volatile sections such as time lines, capability cards, evidence, and
conversation anchors.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from core.infra import paths
from core.model_config import PRIMARY_MODEL
from core.routing.focused_cognition import (
    _ORIGIN_TRUST_INSTRUCTION,
    _TRUST_TIER_INSTRUCTION,
    _VOICE_CARD_TEXT,
    _self_card_enabled,
)
from core.routing.llm_client import served_model_alias
from core.routing.self_card import assemble_self_card_from_paths


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _served_model() -> str:
    try:
        return served_model_alias(default=PRIMARY_MODEL, timeout_s=0.25)
    except Exception:
        return PRIMARY_MODEL


def _resolved_frame() -> tuple[str, bool, dict[str, Any] | None]:
    if not _self_card_enabled():
        return _VOICE_CARD_TEXT, False, None

    card = assemble_self_card_from_paths(
        base_path=paths.soul_base_path(),
        local_path=paths.soul_local_path(),
        time_line_candidate=None,
        time_line_applied=False,
    )
    receipt = None
    try:
        receipt = dict(card.receipt())
    except Exception:
        receipt = None
    return card.text, True, receipt


def build_probe_envelope() -> tuple[str, dict[str, Any]]:
    """Return ``(system_prompt, component_snapshot)`` for an A2 probe run."""

    frame_text, self_card_applied, frame_receipt = _resolved_frame()
    policy_text = f"{_TRUST_TIER_INSTRUCTION}\n\n{_ORIGIN_TRUST_INSTRUCTION}"
    envelope = f"{frame_text}\n\n{policy_text}"
    soul_base = paths.soul_base_path()
    soul_local = paths.soul_local_path()
    snapshot: dict[str, Any] = {
        "base_model": _served_model(),
        "soul_base_hash": _sha256_file(soul_base),
        "soul_local_hash": _sha256_file(soul_local),
        "frame_text_hash": _sha256_text(frame_text),
        "policy_hash": _sha256_text(policy_text),
        "self_card_applied": bool(self_card_applied),
    }
    if frame_receipt is not None:
        snapshot["frame_receipt"] = frame_receipt
    return envelope, snapshot

