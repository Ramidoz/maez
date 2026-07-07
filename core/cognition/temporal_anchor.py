from __future__ import annotations

import logging

from core.infra.env_flags import strict_env_flag

logger = logging.getLogger("maez.temporal_anchor")

TEMPORAL_ANCHOR_THRESHOLD_S = 3 * 60 * 60


def temporal_anchor_shadow_enabled() -> bool:
    return strict_env_flag("MAEZ_TEMPORAL_ANCHOR_SHADOW")


def temporal_anchor_enforce_enabled() -> bool:
    return strict_env_flag("MAEZ_TEMPORAL_ANCHOR_ENFORCE")


def elapsed_hours_phrase(elapsed_seconds: float) -> str:
    hours = max(0, int(float(elapsed_seconds) // 3600))
    return f"{hours} hour ago" if hours == 1 else f"{hours} hours ago"


def completed_owner_gap_seconds() -> float | None:
    try:
        from core.evolution.subjective_duration import SubjectiveDuration

        ctx = SubjectiveDuration().completed_gap_rhythm_context()
    except Exception as exc:
        logger.debug("temporal anchor gap unavailable: %s", exc)
        return None
    if not ctx:
        return None
    try:
        return float(ctx.get("rhythm_current_gap_s"))
    except (TypeError, ValueError):
        return None


def anchor_prompt_context(
    text: str,
    *,
    elapsed_seconds: float | None = None,
) -> str:
    shadow = temporal_anchor_shadow_enabled()
    enforce = temporal_anchor_enforce_enabled()
    if not shadow and not enforce:
        return text
    if not text:
        return text
    gap = elapsed_seconds
    if gap is None:
        gap = completed_owner_gap_seconds()
    if gap is None or gap <= TEMPORAL_ANCHOR_THRESHOLD_S:
        return text
    label = f"[previous conversation, {elapsed_hours_phrase(gap)} - not current]"
    if shadow:
        logger.info(
            "temporal_anchor_shadow elapsed_seconds=%s would_anchor=%s",
            int(gap),
            True,
        )
    if not enforce:
        return text
    return f"{label}\n{text}"
