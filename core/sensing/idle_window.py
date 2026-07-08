"""Read-only idle-window inputs shared by Dream and consolidation."""

from __future__ import annotations

import time
from datetime import datetime, timezone


def camera_idle_state(camera_state: object | None, *, now: float) -> str:
    if camera_state is None:
        return "unknown"
    try:
        now_dt = datetime.fromtimestamp(float(now), tz=timezone.utc)
        with_freshness = getattr(camera_state, "with_freshness", None)
        if callable(with_freshness):
            camera_state = with_freshness(now=now_dt)
    except Exception:
        pass
    sensor_state = str(
        getattr(camera_state, "sensor_state", "unknown") or "unknown"
    ).lower()
    presence_state = str(
        getattr(camera_state, "presence_state", "unknown") or "unknown"
    ).lower()
    if presence_state == "present" and sensor_state == "available":
        return "present_fresh"
    if presence_state == "absent":
        return "absent"
    if sensor_state in {"disabled", "stale", "unavailable"}:
        return "unavailable"
    return "unknown"


def idle_window_inputs(daemon: object, *, now: float | None = None) -> dict[str, object]:
    current = time.time() if now is None else float(now)
    last_interaction = getattr(daemon, "_last_owner_interaction_ts", None)
    try:
        no_interaction_secs = max(0.0, current - float(last_interaction))
        activity_known = True
    except (TypeError, ValueError):
        no_interaction_secs = 0.0
        activity_known = False
    try:
        active_until_future = (
            float(getattr(daemon, "_rohit_active_until", 0.0) or 0.0) > current
        )
    except (TypeError, ValueError):
        active_until_future = False
    camera_state = (
        getattr(daemon, "_last_presence_snap", None)
        or getattr(daemon, "_camera_presence_state", None)
    )
    return {
        "no_interaction_secs": no_interaction_secs,
        "camera": camera_idle_state(camera_state, now=current),
        "active_until_future": active_until_future,
        "activity_known": activity_known,
    }
