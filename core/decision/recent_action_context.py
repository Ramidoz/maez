# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""recent_action_context.py — surface preceding card outcomes to the
cycle narration path.

R3.5 from the 2026-05-04 symphony audit. S4 BLOCKER F7 (top-10 #8)
found that Cycle 35 narrated "system idle, holding quiet" 12 seconds
after the 14:39 wmctrl card failed three tools. The cycle's perception
path read system metrics + ambient context but did NOT read
pending_cards.execution_output for the immediately-preceding card.

R3 makes the action engine record failures honestly going forward
(stdout-pattern detection on exit=0). R3.5 makes the cycle narration
consult those records before claiming idle. Specifically, this module
returns a compact prompt-ready block listing recent card failures so
the cycle reasoning can frame its output truthfully.

Public API:
    recent_failures(window_seconds=120.0) -> str

The block format:
    [RECENT-ACTION-OUTCOMES (last 120s)]
    - {executed_at} {request_id[:8]}: FAILED ({kind}) — {marker}
      cmd: {cmd snippet}
    ...

Empty string when no failures in window.

Soft-failure detector re-runs against execution_output so legacy
rows with execution_success=1 but failure markers (the wmctrl 14:39
row 105 shape from pre-R3 deploy) are correctly classified.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.recent_action_context")

# Bound the block size so the cycle prompt budget stays predictable.
_MAX_FAILURES_IN_BLOCK = 6
_MARKER_TRUNCATE_CHARS = 100
_CMD_TRUNCATE_CHARS = 100
_MAX_BLOCK_CHARS = 1800


def _resolve_db_path() -> Path:
    """Resolve the pending_cards.db path via core.paths so this
    module works in dev/tests without env coupling. Mirrors the
    pattern used in core.paths-routed code."""
    try:
        from core import paths as _paths
        return _paths.memory_dir() / "pending_cards.db"
    except Exception:
        return Path(__file__).resolve().parents[2] / "memory" / "pending_cards.db"


def recent_failures(
    window_seconds: float = 120.0,
    *,
    _db_path_override: Optional[Path] = None,
) -> str:
    """Return a prompt-ready block describing recent card failures.

    A card is treated as a failure if EITHER:
      - execution_success == 0, OR
      - execution_success == 1 but execution_output matches a
        soft-failure pattern (catches legacy rows from pre-R3
        deploy when the action engine was returncode-only).

    Empty string if no failures within the window.

    Args:
        window_seconds: how far back to look (default 120s = the
            "this just happened" window for the cycle's perception
            of preceding state).
        _db_path_override: testing hook; production callers leave
            this None.
    """
    db_path = _db_path_override or _resolve_db_path()
    if not db_path.exists():
        return ""

    cutoff_ts = time.time() - max(0.0, window_seconds)

    try:
        db = sqlite3.connect(str(db_path), timeout=2.0)
        cur = db.cursor()
        rows = cur.execute(
            "SELECT request_id, executed_at, execution_success, "
            "       execution_output, execution_error, params_json "
            "FROM pending_cards "
            "WHERE executed_at IS NOT NULL "
            "  AND executed_at >= ? "
            "ORDER BY executed_at DESC "
            "LIMIT 50",
            (cutoff_ts,),
        ).fetchall()
        db.close()
    except sqlite3.Error as e:
        logger.warning(
            "recent_action_context: pending_cards read failed: %s "
            "(returning empty block)", e,
        )
        return ""

    failures: list[dict] = []
    for (rid, executed_at, success, output, err, params_json) in rows:
        kind: Optional[str] = None
        marker: Optional[str] = None
        is_failure = False

        if success == 0:
            is_failure = True
            kind = "exit_nonzero"
            marker = (err or output or "")[:_MARKER_TRUNCATE_CHARS]
        else:
            # Re-run soft-failure detector on stdout/stderr.
            try:
                from core.actions import shell_failure_detector as _sfd
                sig = _sfd.detect_failures_in_output(
                    stdout=output or "", stderr=err or "",
                    returncode=0, cmd="",
                )
                if sig is not None:
                    is_failure = True
                    kind = sig.kind
                    marker = sig.marker
            except Exception as _e:
                logger.debug(
                    "recent_action_context: detector re-run failed "
                    "for %s: %s", rid, _e,
                )

        if not is_failure:
            continue

        # Pull the cmd from params_json for context.
        cmd_snippet = ""
        try:
            if params_json:
                params = json.loads(params_json)
                cmd_snippet = (params.get("cmd") or "")[:_CMD_TRUNCATE_CHARS]
        except (json.JSONDecodeError, AttributeError):
            cmd_snippet = ""

        failures.append({
            "request_id": rid,
            "executed_at": executed_at,
            "kind": kind,
            "marker": marker,
            "cmd": cmd_snippet,
        })
        if len(failures) >= _MAX_FAILURES_IN_BLOCK:
            break

    if not failures:
        return ""

    # Render block.
    lines = [
        f"[RECENT-ACTION-OUTCOMES (last {int(window_seconds)}s)]"
    ]
    for f in failures:
        try:
            ts_label = time.strftime(
                "%H:%M:%S", time.localtime(f["executed_at"])
            )
        except (TypeError, ValueError):
            ts_label = "?"
        rid_short = (f["request_id"] or "")[:8]
        marker = (f["marker"] or "").replace("\n", " ")
        lines.append(
            f"- {ts_label} {rid_short}: FAILED ({f['kind']}) — {marker}"
        )
        if f["cmd"]:
            lines.append(f"  cmd: {f['cmd']}")
    lines.append(
        "GROUNDING: do NOT narrate the system as idle/quiet without "
        "acknowledging these recent failures. They are real outcomes "
        "from your own action engine."
    )

    block = "\n".join(lines)
    if len(block) > _MAX_BLOCK_CHARS:
        block = block[:_MAX_BLOCK_CHARS] + "\n... (truncated)"
    return block
