# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
ambient_format.py — render ambient_context() as a compact text block for prompts.

Kept small on purpose: every token added to every turn costs money/latency on
the external route and compute on the local route. Inject only what actually
changes a good response into a better-grounded one.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from core.ambient import ambient_context

_CACHE: dict[str, Any] = {"text": None, "ts": 0.0}
_CACHE_TTL_SEC = 60.0  # refresh at most once per minute across all chat turns


def _one_line(s: Any) -> str:
    """Flatten whitespace in string values so multi-line addresses display cleanly."""
    if not isinstance(s, str):
        return str(s)
    return " ".join(s.split())


def _humanize_signal_time(
    signal_ts: str,
    reference_iso: str | None,
) -> str:
    """Render an ISO signal timestamp as a relative phrase against
    the ambient block's own ``now`` reference.

    Two-tier strategy:
      • Sub-day deltas (the common case for live signals — focus
        changed 30 min ago, arrived home 4 hours ago) get
        minute/hour granularity here in this helper.
      • Day+ deltas delegate to Step-5c's ``relative_time_phrase``
        for consistency with the lived-recall surface, with
        per-surface phrasing swap so "before question" reads as
        "before now" in the ambient context.

    Falls back to truncated ISO when inputs are unparseable or the
    reference is missing — better to surface a literal timestamp
    than fabricate a relative phrase. Silence on malformed input
    is honest.
    """
    if not signal_ts or not isinstance(signal_ts, str):
        return ""
    try:
        from datetime import timezone

        ev = datetime.fromisoformat(signal_ts.replace("Z", "+00:00"))
        if reference_iso:
            ref = datetime.fromisoformat(
                reference_iso.replace("Z", "+00:00"),
            )
        else:
            return f"{signal_ts[:16]}Z"
        if ev.tzinfo is None:
            ev = ev.replace(tzinfo=timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        delta_s = (ev - ref).total_seconds()
        abs_s = abs(delta_s)
        direction_past = delta_s <= 0
        # Sub-day path: ambient signals typically arrive within
        # the last hour or two; minute/hour granularity is what
        # the model can act on.
        if abs_s < 86400.0:
            if abs_s < 60.0:
                phrase = "just now"
                return phrase if direction_past else "in seconds"
            if abs_s < 3600.0:
                minutes = max(1, int(round(abs_s / 60.0)))
                unit = "minute" if minutes == 1 else "minutes"
                return f"{minutes} {unit} before now" if direction_past else f"in {minutes} {unit}"
            hours = abs_s / 3600.0
            if hours < 1.5:
                return "about 1 hour before now" if direction_past else "in about 1 hour"
            hours_int = int(round(hours))
            return (
                f"about {hours_int} hours before now"
                if direction_past
                else f"in about {hours_int} hours"
            )
        # Day+ path delegates to the lived-recall surface's helper
        # so multi-day signals share phrasing across the brief.
        from core.memory.temporal_arithmetic import (
            relative_time_phrase,
        )

        return (
            relative_time_phrase(ev, ref)
            .replace(
                "before question",
                "before now",
            )
            .replace(
                "after question",
                "from now",
            )
            .replace(
                "same day as question",
                "today",
            )
        )
    except (TypeError, ValueError, ImportError):
        return f"{signal_ts[:16]}Z"


def _format(ctx: dict[str, Any]) -> str:
    lines: list[str] = []
    # Today's date + resolved absolute paths — concrete facts the model
    # would otherwise hallucinate. Keep these short.
    try:
        from core import paths

        today_iso = datetime.now().strftime("%Y-%m-%d (%A)")
        lines.append(f"Today: {today_iso}")
        lines.append(f"Your notes file: {paths.maez_notes_path()}")
    except Exception:
        pass
    w = ctx.get("weather") or {}
    if w.get("temp_c") is not None:
        src = ctx.get("coords_source") or (w.get("coords") or {}).get("source") or "unknown"
        tz = w.get("timezone", "")
        # local time in the user's current timezone
        local_time = "?"
        try:
            import zoneinfo

            if tz:
                local_time = datetime.now(zoneinfo.ZoneInfo(tz)).strftime("%a %I:%M %p %Z")
        except Exception:
            pass
        lines.append(
            f"Weather at the owner's location: {w['temp_c']}°C, {w.get('conditions', '?')}"
            f" (coords from {src}; local time {local_time})"
        )
    elif "weather" in ctx:
        try:
            from core.cognition.capability_card import body_legibility_enabled

            if body_legibility_enabled():
                src = ctx.get("coords_source")
                src_suffix = f"; coords from {src}" if src else ""
                lines.append(
                    "Weather at the owner's location: unavailable "
                    f"(weather sense temporarily down{src_suffix})"
                )
        except Exception:
            pass

    win = ctx.get("active_window") or {}
    if win.get("class"):
        lines.append(f"Active desktop window: {win['class']}")

    sigs = ctx.get("signals_latest") or {}
    # Only surface the most relevant recent signals — not everything, not old.
    shown: list[str] = []
    for kind in (
        "focus_mode",
        "location",
        "mood_check",
        "intention",
        "arrive_home",
        "leave_home",
        "arrive_work",
        "leave_work",
        "workout",
        "sleep",
        "reflection",
        "manual_note",
    ):
        entry = sigs.get(kind)
        if not entry:
            continue
        data = entry.get("data") or {}
        ts = entry.get("timestamp", "")
        # summarize data in one line
        if kind == "focus_mode":
            mode = data.get("mode")
            if not isinstance(mode, str) or not mode.strip():
                continue  # malformed — skip instead of polluting prompt
            s = f"focus_mode: {mode}={data.get('active')}"
        elif kind == "location":
            place = _one_line(data.get("place") or f"{data.get('lat')},{data.get('lon')}")
            s = f"location: {place}"
        elif kind == "mood_check":
            s = f"mood: {data.get('rating')}/5 {_one_line(data.get('note') or '')}".strip()
        elif kind == "intention":
            s = f"intention ({data.get('when')}): {_one_line(data.get('text', ''))}"
        elif kind in ("arrive_home", "leave_home", "arrive_work", "leave_work"):
            s = kind
        elif kind == "workout":
            s = f"workout: {data.get('type')} {data.get('duration_min')}min"
        elif kind == "sleep":
            s = f"sleep: {data.get('duration_hours')}h"
        elif kind == "reflection":
            s = f"reflection: {_one_line(data.get('text', ''))[:80]}"
        elif kind == "manual_note":
            s = f"note: {_one_line(data.get('text', ''))[:80]}"
        else:
            continue
        # Step 5s: render the timestamp as relative time (e.g.
        # "about 4 hours before now") instead of a truncated ISO
        # string. Reuses Step-5c's relative_time_phrase against
        # the ambient block's own ``now`` reference, so the model
        # gets something it can act on directly. Falls back to the
        # truncated ISO when parsing fails — silence on malformed
        # timestamps is honest.
        when_str = _humanize_signal_time(ts, ctx.get("now"))
        shown.append(f"  • {s}  ({when_str})")
    if shown:
        lines.append("Recent iPhone signals:")
        lines.extend(shown)

    if not lines:
        return ""
    return "AMBIENT CONTEXT (snapshot; may be stale):\n" + "\n".join(lines)


def ambient_prompt_block() -> str:
    """Cached formatted ambient string. Refreshes at most once per TTL window."""
    now = time.time()
    if _CACHE["text"] is not None and (now - _CACHE["ts"]) < _CACHE_TTL_SEC:
        return _CACHE["text"]
    try:
        ctx = ambient_context()
        text = _format(ctx)
    except Exception:
        text = ""
    _CACHE["text"] = text
    _CACHE["ts"] = now
    return text
