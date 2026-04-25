# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Perception-delta signature for fixation-prevention — 2026-04-25.

The daemon's reasoning loop runs every 30s. The cognition_quality
module already detects fixation and the soul note instructs the
model to suppress repeats, but observed behavior is that the model
still generates fixation thoughts ("AWCC files still uncommitted,
since they haven't changed I'll leave them" repeated across many
cycles). The model verbally complies with the directive but cannot
avoid talking about what perception keeps pressing in front of it.

This module's job: gate the LLM call itself. If the cycle's
perception signature equals the last cycle that produced a stored
thought, AND a minimum-thought floor hasn't been reached, skip the
LLM and mark HEARTBEAT_OK.

Signature axes are chosen by what *actually* drives fixation in the
2026-04-25 incident logs: disk%, git dirty count, presence,
top-3 process names. CPU/RAM/GPU are deliberately excluded — they
jitter cycle-to-cycle on idle systems, so including them means the
gate almost never fires on the very cycles that need it. The LLM
sees CPU/RAM/GPU regardless via the perception block; the gate
just decides whether to run the LLM at all.
"""
from __future__ import annotations

from typing import Iterable


# Long-idle floor: force a thought every N cycles even on identical
# perception so the cognition_quality analyzer's 20-cycle window
# always has fresh data. 10 cycles = 5 minutes at 30s/cycle.
DEFAULT_MIN_THOUGHT_FLOOR = 10

# How many recent stored thoughts must share a value before a field
# counts as stale and gets stripped from the cycle prompt (Patch A).
# 3 is tight enough that real changes resurface quickly, loose enough
# that a single anomaly doesn't lock a real field out of view.
DEFAULT_STALE_THRESHOLD = 3


def extract_axes(
    snap: dict,
    *,
    presence_state: str | None = None,
    git_dirty_count: int = 0,
) -> dict:
    """The fixation-relevant axes of one cycle's perception. Two
    cycles with identical axes are functionally equivalent for
    fixation purposes — the model would see the same static inputs
    and fixate on the same stable observations. Volatile axes
    (CPU/RAM/GPU) are intentionally excluded; they jitter
    cycle-to-cycle on idle and would prevent the gate from ever
    firing on the very cycles that need it."""
    procs = snap.get("top_processes_cpu") or []
    return {
        "disk": int(round(float(snap.get("disk", {}).get("/", {}).get("percent") or 0))),
        "presence": presence_state or "unknown",
        "git": int(git_dirty_count),
        "procs": tuple(sorted(p.get("name", "") for p in procs[:3] if p.get("name"))),
    }


def signature_from_axes(axes: dict) -> str:
    """Compact string form of an axes dict — what the gate compares."""
    procs_str = ",".join(axes.get("procs") or ())
    return (
        f"disk={axes.get('disk', 0)}"
        f"|presence={axes.get('presence', 'unknown')}"
        f"|git={axes.get('git', 0)}"
        f"|procs={procs_str}"
    )


def compute_signature(
    snap: dict,
    *,
    presence_state: str | None = None,
    git_dirty_count: int = 0,
) -> str:
    """Convenience wrapper: extract axes from snap, then signature."""
    return signature_from_axes(extract_axes(
        snap,
        presence_state=presence_state,
        git_dirty_count=git_dirty_count,
    ))


def redact_stale_perception_block(text: str, stale: set[str]) -> str:
    """Patch A redactor: strip stale fields from a `format_snapshot()`
    output before it goes into the cycle prompt.

    Handles only the fields that LIVE in `format_snapshot`'s output:
      - "Disk /..." lines  (when "disk" in stale)
      - "Top processes (CPU):" / "(MEM):" sections  (when "procs" in stale)

    Other axes ("presence", "git") aren't in this block — caller
    handles them by gating the separate append for those blocks in
    `_reason()`.

    Returns text unchanged when `stale` is empty.
    """
    if not stale:
        return text
    keep: list[str] = []
    in_procs_section = False
    for line in text.split("\n"):
        # End the procs section when we hit a non-indented non-blank line.
        if in_procs_section and not line.startswith("  ") and line.strip() != "":
            in_procs_section = False
        # Procs-section header → enter section, skip header.
        if "procs" in stale and line.startswith("Top processes"):
            in_procs_section = True
            continue
        if in_procs_section:
            continue
        if "disk" in stale and line.startswith("Disk "):
            continue
        keep.append(line)
    return "\n".join(keep)


def stale_fields(
    history: Iterable[dict],
    current: dict,
    *,
    threshold: int = DEFAULT_STALE_THRESHOLD,
) -> set[str]:
    """Patch A: which axes have been stable across recent thoughts?

    A field is "stale" when the last `threshold` stored thoughts AND
    the current cycle all carry the same value for it. Stale fields
    get stripped from the prompt — the model can't fixate on what it
    can't see.

    Args:
        history: most recent stored-thought axes dicts (oldest to
            newest is fine; we only check value equality, not order).
        current: this cycle's axes dict.
        threshold: how many history entries must agree. <threshold
            entries available → returns empty set (not enough signal
            to claim staleness yet).

    Returns:
        Set of axis names ({"disk", "presence", "git", "procs"} ⊆).
    """
    history_list = list(history)
    if len(history_list) < threshold:
        return set()
    stale: set[str] = set()
    for axis, value in current.items():
        recent = history_list[-threshold:]
        if all(h.get(axis) == value for h in recent):
            stale.add(axis)
    return stale


def should_skip_reasoning(
    *,
    current_signature: str,
    last_thought_signature: str | None,
    cycles_since_last_thought: int,
    min_thought_floor: int = DEFAULT_MIN_THOUGHT_FLOOR,
) -> bool:
    """True iff this cycle should skip the LLM call.

    Skips when: prior thought exists, current signature matches it,
    and the floor hasn't been reached. Otherwise runs the cycle.
    """
    if last_thought_signature is None:
        return False
    if current_signature != last_thought_signature:
        return False
    if cycles_since_last_thought >= min_thought_floor:
        return False
    return True
