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

    win = ctx.get("active_window") or {}
    if win.get("title"):
        lines.append(f"Active desktop window: {win['title']} ({win.get('class', '?')})")

    sigs = ctx.get("signals_latest") or {}
    # Only surface the most relevant recent signals — not everything, not old.
    shown: list[str] = []
    for kind in ("focus_mode", "location", "mood_check", "intention",
                 "arrive_home", "leave_home", "arrive_work", "leave_work",
                 "workout", "calendar", "sleep", "reflection", "manual_note"):
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
        elif kind == "calendar":
            s = f"calendar: {_one_line(data.get('title', ''))} at {data.get('start')}"
        elif kind == "sleep":
            s = f"sleep: {data.get('duration_hours')}h"
        elif kind == "reflection":
            s = f"reflection: {_one_line(data.get('text', ''))[:80]}"
        elif kind == "manual_note":
            s = f"note: {_one_line(data.get('text', ''))[:80]}"
        else:
            continue
        shown.append(f"  • {s}  ({ts[:16]}Z)")
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
