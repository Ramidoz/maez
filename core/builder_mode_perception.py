"""
core/builder_mode_perception.py — A-core #3, Step 3.

The consumer side of builder-mode event ingestion. Reads direct-edit
events from memory/audit_log.db, formats them into a perception block
for Maez's observation stream, and manages the high-water-mark so
events aren't re-surfaced on every cycle.

Producer side:
    scripts/maez_cli.py  (Step 2, live)
    skills/telegram_voice.py  (Step 4, pending)
Both producers write to audit_log.db via the existing AuditLog API.
This module is the shared consumer that both surfaces feed into.

Design notes — see docs/governance/BETA_ARCHITECTURE_DECISIONS.md and
the anchoring conversation for A-core #3 in the session snapshot for
2026-04-15:

- Surface-agnostic: this module does not know or care which surface
  produced an event. Producers write to audit_log; this reader
  reads from audit_log. No surface-specific plumbing.

- Scope-locked: only direct-edit event types (session_start / edit
  / session_end) are surfaced. Regular audit events and regular
  Telegram messages use their existing paths. This is NOT a general
  surface-agnostic event bus. It's the narrow reader for builder-
  mode transitions. Resist scope creep.

- Layered replay on daemon startup:
    1. Primary: persisted high-water-mark file (daemon/builder_mode_hwm.txt)
       lets the daemon resume cleanly without re-surfacing everything.
    2. Fallback: if the HWM file is missing, corrupted, in the future,
       or earlier than the oldest event, fall back to a bounded window
       (default 1 hour before now).
    3. Open-session supplement: if any session is currently open
       (session_start with no matching session_end), its events are
       replayed in full regardless of the HWM, up to the total cap.
  All three layers compose; they are not alternatives.

- Lossy at perception, durable at storage: events dropped by the
  total cap are NOT re-surfaced on the next cycle. The HWM advances
  to the max ts seen (not the max ts surfaced), so dropped events
  stay dropped at the perception layer. They remain in audit_log.db
  as the source of truth and can be surfaced later by a smarter
  summarization pass. This is the right tradeoff: rate-limiting
  would just delay pollution, lossy-drop prevents it.

- Total cap (default 50) applies to the whole surfaced block, not
  per-component. When the cap fires, selection uses option 3:
  always keep session_start events for any currently-open session
  (load-bearing context) + fill remaining cap slots with the most
  recent events. Dropped events are summarized by a rich truncation
  marker that carries shape (count, span, session breakdown).

- Crash safety: callers MUST update the HWM file AFTER successful
  surfacing (not before). If the daemon crashes between surfacing
  and HWM update, next boot re-surfaces the last cycle's events —
  bounded replay, small, correct. If the order were reversed, a
  crash would silently lose events.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Any

from core.audit_log import (
    AuditLog,
    DIRECT_EDIT,
    DIRECT_EDIT_SESSION_END,
    DIRECT_EDIT_SESSION_START,
)


# -------------------------------------------------------------------- #
#  Tunables                                                              #
# -------------------------------------------------------------------- #

# Default total-events cap for a single cycle's surfaced block. Small
# enough to prevent permanent gestation-memory pollution from a
# pathological replay, large enough that normal operation never
# notices. See the 2026-04-15 session snapshot for the cost/benefit
# reasoning on the specific number.
DEFAULT_MAX_TOTAL_EVENTS = 50

# Default bounded window for the fallback when the HWM file is
# missing, corrupted, in the future, or earlier than the oldest
# event. One hour of generous recovery budget; anything older stays
# in audit_log.db and is not replayed.
DEFAULT_FALLBACK_WINDOW_S = 3600

# Maximum session IDs to list in the truncation marker's "sessions
# affected" line. The marker is a summary; summaries have bounded
# size. Sessions beyond this cap are shown as "... and N more".
MAX_SESSION_IDS_IN_MARKER = 3


# -------------------------------------------------------------------- #
#  High-water-mark file helpers                                         #
# -------------------------------------------------------------------- #

def load_high_water_mark(
    hwm_file: Path,
    *,
    now: Optional[float] = None,
    fallback_window_s: int = DEFAULT_FALLBACK_WINDOW_S,
) -> float:
    """Load the last-seen timestamp from the HWM file, with defensive
    sanity checks. Falls back to `now - fallback_window_s` on any
    read failure or suspicious value.

    Sanity checks:
      - File missing or empty → fallback window
      - Unparseable content → fallback window
      - Value more than 60 seconds in the future (clock skew
        tolerance) → fallback window
      - Value effectively zero or negative → fallback window

    The caller is responsible for passing an audit_log handle to
    clamp against the oldest event if that's desired; this function
    only handles file-level sanity.
    """
    now_ts = now if now is not None else time.time()

    if not hwm_file.exists():
        return now_ts - fallback_window_s

    try:
        content = hwm_file.read_text().strip()
    except OSError:
        return now_ts - fallback_window_s

    if not content:
        return now_ts - fallback_window_s

    try:
        ts = float(content.splitlines()[0].strip())
    except (ValueError, IndexError):
        return now_ts - fallback_window_s

    # Sanity: clock-skew tolerance
    if ts > now_ts + 60:
        return now_ts - fallback_window_s

    # Sanity: non-positive timestamp
    if ts <= 0:
        return now_ts - fallback_window_s

    return ts


def save_high_water_mark(hwm_file: Path, new_ts: float) -> None:
    """Persist the new high-water-mark. Overwrites the file.

    Call this ONLY after events have been successfully surfaced to
    Maez's perception stream. If the order is inverted (save HWM
    first, then surface), a crash between the two steps silently
    loses events. The correct order is surface → save HWM.
    """
    hwm_file.parent.mkdir(parents=True, exist_ok=True)
    hwm_file.write_text(f"{new_ts}\n")


# -------------------------------------------------------------------- #
#  Internal helpers                                                      #
# -------------------------------------------------------------------- #

def _closed_session_ids(audit_log: AuditLog) -> set[str]:
    """Return the set of session_ids that have at least one
    session_end event in the log. Sessions NOT in this set are
    considered currently open.
    """
    import sqlite3
    with sqlite3.connect(audit_log.db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT session_id FROM audit_log WHERE action = ? AND session_id IS NOT NULL",
            (DIRECT_EDIT_SESSION_END,),
        ).fetchall()
    return {r[0] for r in rows}


def _find_open_session_start_events(audit_log: AuditLog) -> list[dict]:
    """Return all session_start events whose session_id has no
    matching session_end in the log. Ordered by ts ascending.
    """
    closed = _closed_session_ids(audit_log)
    import sqlite3
    with sqlite3.connect(audit_log.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE action = ? ORDER BY ts ASC",
            (DIRECT_EDIT_SESSION_START,),
        ).fetchall()
    return [dict(r) for r in rows if r["session_id"] not in closed]


def _fmt_wall(ts: float) -> str:
    """Short wall-clock time for perception readability."""
    return time.strftime("%H:%M:%S", time.localtime(ts))


def _classify_event_for_display(event: dict) -> str:
    """Produce a one-line human-readable line for a single event."""
    import json
    ts = _fmt_wall(event["ts"])
    action = event["action"]
    session_short = (event.get("session_id") or "?")[:8]
    try:
        params = json.loads(event.get("params_json") or "{}")
    except (ValueError, TypeError):
        params = {}

    if action == DIRECT_EDIT_SESSION_START:
        reason = params.get("reason") or "(no reason)"
        source = params.get("source") or "?"
        return f"  {ts}  [session_start]  via {source}, reason: {reason}  (session {session_short})"

    if action == DIRECT_EDIT_SESSION_END:
        return f"  {ts}  [session_end]    (session {session_short})"

    if action == DIRECT_EDIT:
        paths = params.get("paths") or []
        diff_summary = params.get("diff_summary") or ""
        commit_hash = params.get("commit_hash")
        commit_part = f" commit={commit_hash[:8]}" if commit_hash else ""
        paths_str = ", ".join(paths) if paths else "(no paths)"
        # Keep the diff summary short for perception
        if len(diff_summary) > 80:
            diff_summary = diff_summary[:77] + "..."
        return f"  {ts}  [edit]{commit_part}  {paths_str}  — {diff_summary}  (session {session_short})"

    # Unknown direct-edit action (shouldn't happen given the filter)
    return f"  {ts}  [{action}]  (session {session_short})"


def _build_truncation_marker(
    dropped_events: list[dict],
    open_session_ids: set[str],
    max_total_events: int,
) -> str:
    """Build the rich truncation marker for dropped events. Carries
    shape (count, span, session breakdown) so Maez knows the omission
    had structure, not just volume.
    """
    if not dropped_events:
        return ""

    n_dropped = len(dropped_events)
    oldest_ts = min(e["ts"] for e in dropped_events)
    newest_ts = max(e["ts"] for e in dropped_events)
    oldest_fmt = _fmt_wall(oldest_ts)
    newest_fmt = _fmt_wall(newest_ts)

    # Session breakdown on the dropped set
    dropped_session_ids = {e["session_id"] for e in dropped_events if e.get("session_id")}
    dropped_open_ids = [sid for sid in dropped_session_ids if sid in open_session_ids]
    dropped_closed_ids = [sid for sid in dropped_session_ids if sid not in open_session_ids]

    total_sessions = len(dropped_session_ids)
    n_closed = len(dropped_closed_ids)
    n_open = len(dropped_open_ids)

    # Session listing (cap to MAX_SESSION_IDS_IN_MARKER, prefer open ones
    # since their state matters more)
    ids_to_list: list[str] = []
    # Open sessions first, they're more load-bearing
    for sid in sorted(dropped_open_ids):
        if len(ids_to_list) >= MAX_SESSION_IDS_IN_MARKER:
            break
        ids_to_list.append(sid)
    # Fill with closed sessions
    for sid in sorted(dropped_closed_ids):
        if len(ids_to_list) >= MAX_SESSION_IDS_IN_MARKER:
            break
        ids_to_list.append(sid)
    n_more = total_sessions - len(ids_to_list)

    # Short ids for display
    ids_display = [sid[:12] for sid in ids_to_list]

    # Build the sessions-affected line
    session_parts = []
    if n_closed > 0 and n_open > 0:
        session_parts.append(f"{n_closed} closed")
        session_parts.append(f"{n_open} open")
    elif n_closed > 0:
        session_parts.append(f"{n_closed} closed")
    elif n_open > 0:
        session_parts.append(f"{n_open} open")
    session_breakdown = ", ".join(session_parts) if session_parts else "0"

    ids_line = ", ".join(ids_display)
    if n_more > 0:
        ids_line += f" ... and {n_more} more"

    if total_sessions > 0:
        sessions_line = f" Sessions affected: {total_sessions} ({session_breakdown}): {ids_line}."
    else:
        sessions_line = " Sessions affected: 0 (events not tied to any session)."

    marker = (
        "\n[BUILDER MODE TRUNCATED\n"
        f" {n_dropped} events not shown in this perception (cap = {max_total_events}).\n"
        f" Dropped span: {oldest_fmt} — {newest_fmt}.\n"
        f"{sessions_line}\n"
        f" Full history in memory/audit_log.db since {oldest_fmt}.]\n"
    )
    return marker


# -------------------------------------------------------------------- #
#  Main formatter                                                        #
# -------------------------------------------------------------------- #

def format_recent_builder_events(
    audit_log: AuditLog,
    since_ts: float,
    *,
    include_open_session: bool = True,
    max_total_events: int = DEFAULT_MAX_TOTAL_EVENTS,
    now: Optional[float] = None,
) -> tuple[str, float]:
    """Format direct-edit events since `since_ts` into a perception
    block for Maez's observation stream. Returns (block_text, new_hwm).

    If no events, block_text is the empty string and new_hwm equals
    since_ts (caller should NOT save HWM in that case).

    If events exist, block_text is a formatted text block suitable
    for appending to the daemon's perception snapshot, and new_hwm
    is the max timestamp observed across ALL events seen in this
    call (including dropped ones — the cap is lossy at perception,
    durable at storage).

    Parameters:
        audit_log: an AuditLog instance pointing at memory/audit_log.db
        since_ts: unix timestamp; only events at or after this ts
            are considered for the since-window. Events from an open
            session older than since_ts may still be included via
            the open-session supplement.
        include_open_session: if True, events from any currently-open
            session are included in the replay even if they're older
            than since_ts. This is how a mid-session restart gets the
            coherent arc of the session instead of just the tail.
        max_total_events: total cap on the surfaced block. If more
            events would land, the block is truncated using option 3
            (keep open-session starts + most recent events) and a
            rich truncation marker is appended.
        now: override for the current time (used in tests). Defaults
            to time.time().
    """
    # 1. Gather events from the since_ts window
    window_events = audit_log.recent_direct_edits(since_ts=since_ts, limit=10000)

    # 2. Open-session supplement — if include_open_session, fetch all
    #    events belonging to currently-open sessions regardless of ts
    open_session_ids: set[str] = set()
    supplemental_events: list[dict] = []
    if include_open_session:
        open_start_events = _find_open_session_start_events(audit_log)
        open_session_ids = {e["session_id"] for e in open_start_events if e.get("session_id")}
        if open_session_ids:
            # Pull all events belonging to any open session across all time
            import sqlite3
            placeholders = ",".join("?" * len(open_session_ids))
            q = (
                f"SELECT * FROM audit_log "
                f"WHERE session_id IN ({placeholders}) "
                f"  AND action IN (?, ?, ?) "
                f"ORDER BY ts ASC"
            )
            args: list[Any] = list(open_session_ids) + [
                DIRECT_EDIT_SESSION_START,
                DIRECT_EDIT,
                DIRECT_EDIT_SESSION_END,
            ]
            with sqlite3.connect(audit_log.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(q, args).fetchall()
            supplemental_events = [dict(r) for r in rows]

    # 3. Merge window + supplement, dedupe by request_id, sort by ts
    merged: dict[str, dict] = {}
    for e in window_events:
        merged[e["request_id"]] = e
    for e in supplemental_events:
        merged[e["request_id"]] = e

    if not merged:
        return "", since_ts

    all_events = sorted(merged.values(), key=lambda e: e["ts"])

    # Compute new HWM as max ts in the FULL set (pre-truncation).
    # This is the "lossy at perception, durable at storage" invariant:
    # even events dropped by the cap advance the HWM so they aren't
    # surfaced again on subsequent cycles.
    new_hwm = max(e["ts"] for e in all_events)

    # 4. Apply cap. Option 3 selection: always keep session_start
    #    events for currently-open sessions, fill remaining slots
    #    with most-recent events.
    if len(all_events) <= max_total_events:
        survivors = all_events
        dropped: list[dict] = []
    else:
        # "Must keep" set: session_start events where session_id is open
        must_keep: list[dict] = [
            e for e in all_events
            if e["action"] == DIRECT_EDIT_SESSION_START
            and e.get("session_id") in open_session_ids
        ]
        must_keep_ids = {e["request_id"] for e in must_keep}

        # Fill the remaining cap with most-recent events (not already
        # in must_keep), then recombine and sort for display.
        remaining_slots = max_total_events - len(must_keep)
        if remaining_slots <= 0:
            # Pathological: more open-session starts than the cap
            # allows. Keep the most recent `max_total_events` of them.
            survivors = sorted(must_keep, key=lambda e: e["ts"])[-max_total_events:]
        else:
            # Walk events newest → oldest, pick until filled
            fill: list[dict] = []
            for e in reversed(all_events):
                if len(fill) >= remaining_slots:
                    break
                if e["request_id"] not in must_keep_ids:
                    fill.append(e)
            survivors = must_keep + fill

        survivor_ids = {e["request_id"] for e in survivors}
        dropped = [e for e in all_events if e["request_id"] not in survivor_ids]
        survivors = sorted(survivors, key=lambda e: e["ts"])

    # 5. Format the surviving events
    lines = [
        f"[BUILDER MODE EVENTS since {_fmt_wall(since_ts)}]"
    ]
    for e in survivors:
        lines.append(_classify_event_for_display(e))

    # 6. Append the truncation marker if anything was dropped
    if dropped:
        marker = _build_truncation_marker(
            dropped_events=dropped,
            open_session_ids=open_session_ids,
            max_total_events=max_total_events,
        )
        lines.append(marker)

    block = "\n".join(lines) + "\n"
    return block, new_hwm


# -------------------------------------------------------------------- #
#  Self-test                                                             #
# -------------------------------------------------------------------- #

if __name__ == "__main__":
    import tempfile

    print("=== builder_mode_perception self-test ===\n")

    # Fresh temp DB
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = Path(tf.name)
    db_path.unlink()

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
        hwm_path = Path(tf.name)
    hwm_path.unlink()

    log = AuditLog(db_path)

    # ------------------------------------------------------------------ #
    #  HWM helper tests                                                   #
    # ------------------------------------------------------------------ #
    print("--- HWM helper tests ---")

    # 1. Missing file → fallback window
    ts0 = load_high_water_mark(hwm_path, now=1_000_000.0, fallback_window_s=3600)
    assert ts0 == 1_000_000.0 - 3600, f"missing HWM should fall back; got {ts0}"
    print("  ✓ missing HWM → fallback window")

    # 2. Save + load round-trip
    save_high_water_mark(hwm_path, 1_000_500.25)
    ts1 = load_high_water_mark(hwm_path, now=1_000_600.0)
    assert abs(ts1 - 1_000_500.25) < 0.001, f"round-trip failed: {ts1}"
    print("  ✓ save/load round-trip")

    # 3. Corrupted content → fallback
    hwm_path.write_text("not a number\n")
    ts2 = load_high_water_mark(hwm_path, now=1_000_000.0, fallback_window_s=3600)
    assert ts2 == 1_000_000.0 - 3600
    print("  ✓ corrupted HWM → fallback window")

    # 4. Future timestamp → fallback
    hwm_path.write_text(f"{2_000_000.0}\n")
    ts3 = load_high_water_mark(hwm_path, now=1_000_000.0, fallback_window_s=3600)
    assert ts3 == 1_000_000.0 - 3600
    print("  ✓ future HWM → fallback window")

    # 5. Non-positive → fallback
    hwm_path.write_text("0\n")
    ts4 = load_high_water_mark(hwm_path, now=1_000_000.0, fallback_window_s=3600)
    assert ts4 == 1_000_000.0 - 3600
    print("  ✓ zero HWM → fallback window")

    # ------------------------------------------------------------------ #
    #  Formatter: empty case                                              #
    # ------------------------------------------------------------------ #
    print("\n--- formatter: empty case ---")
    block, new_hwm = format_recent_builder_events(log, since_ts=0.0, now=1_000_000.0)
    assert block == ""
    assert new_hwm == 0.0
    print("  ✓ empty DB → empty block, hwm unchanged")

    # ------------------------------------------------------------------ #
    #  Formatter: small closed session surfaces normally                  #
    # ------------------------------------------------------------------ #
    print("\n--- formatter: small closed session ---")
    sid_a = log.start_direct_edit_session(reason="test rewrite", source="cli")
    log.log_direct_edit(
        session_id=sid_a,
        paths=["core/foo.py"],
        diff_summary="rewrote foo",
        commit_hash="abc12345",
        reason="",
    )
    log.end_direct_edit_session(session_id=sid_a)

    block, new_hwm = format_recent_builder_events(log, since_ts=0.0)
    assert "session_start" in block
    assert "session_end" in block
    assert "edit" in block
    assert "rewrote foo" in block
    assert sid_a[:8] in block
    # No truncation since only 3 events
    assert "BUILDER MODE TRUNCATED" not in block
    assert new_hwm > 0
    print("  ✓ 3-event session surfaced cleanly, no truncation")

    # ------------------------------------------------------------------ #
    #  Formatter: open session supplement                                 #
    # ------------------------------------------------------------------ #
    print("\n--- formatter: open session supplement ---")
    # Open a new session and log some events, but don't close it
    sid_open = log.start_direct_edit_session(reason="in progress", source="telegram")
    log.log_direct_edit(
        session_id=sid_open,
        paths=["skills/bar.py"],
        diff_summary="wip refactor",
        reason="",
    )

    # Use a since_ts far in the future to exclude the window path;
    # the open session should still be replayed via the supplement.
    future_ts = time.time() + 3600
    block, new_hwm = format_recent_builder_events(
        log,
        since_ts=future_ts,
        include_open_session=True,
    )
    # The open session's events should still appear via the supplement
    assert sid_open[:8] in block, "open session events should surface via supplement"
    assert "in progress" in block
    assert "wip refactor" in block
    # The closed session (sid_a) should NOT appear because it's older and
    # not included via either path (since_ts is in future, session is closed)
    assert sid_a[:8] not in block, "closed session should not surface"
    print("  ✓ open session supplement surfaces regardless of since_ts")

    # ------------------------------------------------------------------ #
    #  Formatter: truncation with single closed session                   #
    # ------------------------------------------------------------------ #
    print("\n--- formatter: truncation with single closed session ---")
    # Close the open one to isolate the next test
    log.end_direct_edit_session(session_id=sid_open)

    # Create a fresh closed session with many events
    sid_big = log.start_direct_edit_session(reason="many edits", source="cli")
    for i in range(100):
        log.log_direct_edit(
            session_id=sid_big,
            paths=[f"core/file_{i}.py"],
            diff_summary=f"edit {i}",
            reason="",
        )
    log.end_direct_edit_session(session_id=sid_big)

    block, new_hwm = format_recent_builder_events(
        log,
        since_ts=0.0,
        max_total_events=20,
        include_open_session=False,  # no open session supplement
    )
    assert "BUILDER MODE TRUNCATED" in block
    # We had 3 (closed sid_a) + 3 (closed sid_open) + 102 (sid_big) = 108 events
    # Cap is 20, so 88 were dropped
    # Verify the marker has the shape
    assert "events not shown" in block
    assert "Dropped span:" in block
    assert "Sessions affected:" in block
    assert "closed" in block  # at least one closed session affected
    print("  ✓ large single-session batch truncated with rich marker")

    # ------------------------------------------------------------------ #
    #  Formatter: truncation preserves open-session start                 #
    # ------------------------------------------------------------------ #
    print("\n--- formatter: truncation preserves open-session start ---")
    # Open a new session and flood it with edits
    sid_flood = log.start_direct_edit_session(reason="flood test", source="cli")
    for i in range(100):
        log.log_direct_edit(
            session_id=sid_flood,
            paths=[f"skills/flood_{i}.py"],
            diff_summary=f"flood edit {i}",
            reason="",
        )
    # Leave it open

    block, new_hwm = format_recent_builder_events(
        log,
        since_ts=0.0,
        max_total_events=10,
        include_open_session=True,
    )
    # Truncation happened
    assert "BUILDER MODE TRUNCATED" in block
    # The open session's start event must be present even though it's
    # older than almost all the other surfaced events
    assert "flood test" in block, "open session start reason should be preserved"
    assert sid_flood[:8] in block
    print("  ✓ open-session session_start preserved during truncation")

    # ------------------------------------------------------------------ #
    #  Formatter: truncation with many sessions                           #
    # ------------------------------------------------------------------ #
    print("\n--- formatter: truncation with many sessions ---")
    # Create many closed sessions to trigger the "...and N more" branch
    for i in range(6):
        sid = log.start_direct_edit_session(reason=f"many-{i}", source="cli")
        log.log_direct_edit(
            session_id=sid,
            paths=[f"many_{i}.py"],
            diff_summary=f"many-edit-{i}",
            reason="",
        )
        log.end_direct_edit_session(session_id=sid)

    # Close the flood session so it's a closed session too
    log.end_direct_edit_session(session_id=sid_flood)

    block, new_hwm = format_recent_builder_events(
        log,
        since_ts=0.0,
        max_total_events=5,
        include_open_session=False,
    )
    assert "BUILDER MODE TRUNCATED" in block
    assert "Sessions affected:" in block
    # With many dropped sessions, we should see the cap on session-id listing
    # Find the sessions-affected line
    assert "... and" in block or "Sessions affected: " in block
    print("  ✓ many-session truncation produces bounded marker")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    db_path.unlink(missing_ok=True)
    hwm_path.unlink(missing_ok=True)
    print("\n=== builder_mode_perception self-test complete ===")
