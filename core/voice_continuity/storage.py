"""Storage-boundary helpers for S5 artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


VOICE_CONTINUITY_ROOT = Path("memory") / "voice_continuity"
_TEXT_KEYS = {"prompt_text", "reply_text", "transcript", "candidate_reply", "baseline_reply"}


def validate_git_visible_artifact(artifact: dict[str, Any]) -> bool:
    encoded_keys = set(artifact)
    if encoded_keys & _TEXT_KEYS:
        raise ValueError("git-visible S5 artifacts may carry hashes only")
    return True
