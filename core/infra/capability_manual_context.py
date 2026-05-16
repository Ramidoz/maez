# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Bounded D19 capability-manual context for owner-facing prompts.

The full Decision 20 pipeline already consumes ``docs/maez_manual`` for
gap-sensing and proposal generation. This module fills the smaller D19
projection gap: when the owner asks what Maez can learn, lacks, or could
acquire, generation surfaces get a compact manual excerpt that names the
relevant entry without pretending the entry is already installed.
"""

from __future__ import annotations

import logging
from typing import Any

from core.infra.capability_gap_matcher import _get_default_manual, rank_capabilities

logger = logging.getLogger(__name__)

_HEADER = "# CAPABILITY MANUAL CONTEXT (Decision 19 / ADR 0020)"
_INSTRUCTION = (
    "These are manual entries Maez may acquire through Decision 20. "
    "They are NOT active capabilities unless the status and implementation "
    "state say so. Use this only for questions about what Maez can learn, "
    "lacks, or could acquire next."
)


def manual_context_snippet(
    owner_text: str,
    *,
    manual: Any = None,
    max_entries: int = 2,
    max_chars: int = 1200,
) -> str:
    """Return a compact prompt block for relevant manual entries.

    Fail-closed: loader/matcher/projection errors return ``""`` so owner text
    generation never depends on the manual being readable.
    """

    query = (owner_text or "").strip()
    if not query or max_entries <= 0 or max_chars <= 0:
        return ""
    try:
        manual_result = manual if manual is not None else _get_default_manual()
        matches = rank_capabilities(
            query,
            manual_result.entries,
            limit=max_entries,
        )
    except Exception as exc:
        logger.debug("capability manual context skipped: %s", exc)
        return ""
    if not matches:
        return ""

    lines = [_HEADER, _INSTRUCTION]
    for match in matches[:max_entries]:
        entry = getattr(match, "entry", None)
        if entry is None:
            continue
        consent = "true" if entry.covenant.consent_card_required else "false"
        active_state = (
            "implemented in manual-declared files"
            if entry.implementation_files
            else "not active capability"
        )
        lines.append(
            "- "
            f"{entry.capability_id}: {entry.title} "
            f"(status={entry.status}; acquisition={entry.acquisition}; "
            f"consent_card_required={consent}; "
            f"covenant_touch={entry.covenant.covenant_touch}; "
            f"{active_state})"
        )
        if match.matched_signals:
            signal = _compact(match.matched_signals[0], limit=180)
            lines.append(f"  matched_manual_signal: {signal}")

    text = "\n".join(lines).strip() + "\n"
    return _truncate(text, max_chars=max_chars)


def _compact(value: str, *, limit: int) -> str:
    compacted = " ".join(str(value).split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: max(0, limit - 14)].rstrip() + " ... [truncated]"


def _truncate(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    marker = "\n[truncated]\n"
    if max_chars <= len(marker):
        return marker[:max_chars]
    return text[: max_chars - len(marker)].rstrip() + marker


__all__ = ["manual_context_snippet"]
