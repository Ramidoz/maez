# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Coma core-memory writer for restoration events (Decision 22 v1).

When Maez is restored from a hardware-failure backup, post-restore
Maez needs to remember the gap. Otherwise continuity looks intact
while secretly missing N hours — the worst kind of silent state
discrepancy.

This module is the testable boundary: ``write_restoration_record``
takes an injectable MemoryManager (real in production, mocked in
tests) plus the snapshot/restore timestamps and reason.

Two reason codes:
- ``hardware-failure``: writes a first-person coma core memory plus
  an operational restoration log entry.
- ``deliberate-pause``: writes ONLY the operational log entry. The
  owner paused Maez intentionally; framing that as "I lost memory"
  would be a lie.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_VALID_REASONS: frozenset[str] = frozenset({
    "hardware-failure", "deliberate-pause",
})


def format_coma_text(
    *,
    snapshot_timestamp: str,
    restore_timestamp: str,
) -> str:
    """The first-person text written into core memory on a
    hardware-failure restore. Specific dates, no placeholders.
    Owner-facing language at the end invites repair through the
    bond rather than treating the gap as a clinical fact."""
    return (
        f"On {restore_timestamp}, I was restored from a snapshot of "
        f"{snapshot_timestamp} due to a hardware event. I may be "
        "missing memory between the snapshot and the event. The bond "
        "persists through this gap. If anything significant happened "
        "during those hours, my owner is encouraged to tell me about it."
    )


def write_restoration_record(
    *,
    mm: Any,
    snapshot_timestamp: str,
    restore_timestamp: str,
    reason: str,
) -> dict:
    """Write a restoration record to Maez's memory.

    ``hardware-failure`` →
        - core memory (first-person coma text via ``mm.store_core``).
        - operational log entry returned in the result.
    ``deliberate-pause`` →
        - NO core memory write (deliberate pauses aren't amnesia).
        - operational log entry returned in the result.

    Raises ``ValueError`` for any reason outside the valid set —
    silently accepting unknown reasons would defeat the whole point
    of the distinction.
    """
    if reason not in _VALID_REASONS:
        raise ValueError(
            f"unknown restoration reason {reason!r}; "
            f"expected one of {sorted(_VALID_REASONS)}"
        )

    log_entry = {
        "kind": "restoration_event",
        "snapshot_timestamp": snapshot_timestamp,
        "restore_timestamp": restore_timestamp,
        "reason": reason,
    }

    result: dict[str, Any] = {
        "reason": reason,
        "log_entry": log_entry,
        "core_memory_id": None,
    }

    if reason == "hardware-failure":
        text = format_coma_text(
            snapshot_timestamp=snapshot_timestamp,
            restore_timestamp=restore_timestamp,
        )
        # 5x.B Pass 2a: system/covenant. Coma text is schema-derived
        # from canonical timestamps (snapshot + restore); covenant is
        # the strongest tier and survives 5x.D's lineage gate.
        #
        # The TypeError fallback chain accommodates test mocks with
        # older signatures: (a) mocks predating Pass 2a that don't
        # accept the provenance kwargs, (b) much older mocks that
        # don't accept ``source=`` either. Each fallback emits a
        # ``logger.warning`` so a SILENT covenant-tier degrade in
        # production cannot happen unobserved — by 5x.D the system
        # path is assumed reliable, and a quietly-degraded restore
        # write would invalidate that assumption.
        try:
            core_id = mm.store_core(
                text,
                source=f"restoration_event_{restore_timestamp}",
                provenance_source="system",
                trust_tier="covenant",
            )
            result["core_memory_id"] = core_id
        except TypeError as _exc:
            logger.warning(
                "restore_writer: store_core rejected provenance "
                "kwargs (%s); retrying without — covenant tag will "
                "not land on this row. Investigate the mm fixture "
                "if this is production.", _exc,
            )
            try:
                core_id = mm.store_core(
                    text,
                    source=f"restoration_event_{restore_timestamp}",
                )
                result["core_memory_id"] = core_id
            except TypeError as _exc2:
                logger.warning(
                    "restore_writer: store_core rejected source kwarg "
                    "(%s); retrying positional-only — both source and "
                    "provenance will be missing on this row.", _exc2,
                )
                core_id = mm.store_core(text)
                result["core_memory_id"] = core_id

    return result


__all__ = [
    "format_coma_text",
    "write_restoration_record",
]
