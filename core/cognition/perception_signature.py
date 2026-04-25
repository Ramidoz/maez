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


# Long-idle floor: force a thought every N cycles even on identical
# perception so the cognition_quality analyzer's 20-cycle window
# always has fresh data. 10 cycles = 5 minutes at 30s/cycle.
DEFAULT_MIN_THOUGHT_FLOOR = 10


def compute_signature(
    snap: dict,
    *,
    presence_state: str | None = None,
    git_dirty_count: int = 0,
) -> str:
    """Build a fixation-relevant signature from perception state.

    Two cycles with the same signature are functionally equivalent
    for fixation purposes — the model would see the same static
    inputs and fixate on the same stable observations. Volatile
    axes (CPU/RAM/GPU) are intentionally excluded.
    """
    disk_pct = int(round(float(snap.get("disk", {}).get("/", {}).get("percent") or 0)))
    procs = snap.get("top_processes_cpu") or []
    proc_names = sorted(p.get("name", "") for p in procs[:3] if p.get("name"))
    presence = presence_state or "unknown"
    return (
        f"disk={disk_pct}|presence={presence}|git={git_dirty_count}"
        f"|procs={','.join(proc_names)}"
    )


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
