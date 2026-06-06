"""Desktop Awareness v0: content-free desktop body sensor.

Mirrors camera_presence_state.py: hold only content-free state: the active app
class, never the window title, never screenshots, never durable history. Which
room of the house, not what paper on the desk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping

from core.infra import body_capabilities

PERCEPTION_ENV = "MAEZ_DESKTOP_PERCEPTION"
SCHEMA_VERSION = "desktop_presence.v1"

VALID_SENSOR_STATES = frozenset({"disabled", "available", "unavailable"})
VALID_REASONS = frozenset(
    {"", "tools_missing", "wayland", "session_unreachable", "no_active_window"}
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DesktopPresenceState:
    sensor_state: str = "disabled"
    app_class: str | None = None
    reason: str = ""
    sampled_at: datetime | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.sensor_state not in VALID_SENSOR_STATES:
            raise ValueError(f"invalid sensor_state: {self.sensor_state!r}")
        if self.reason not in VALID_REASONS:
            raise ValueError(f"invalid reason: {self.reason!r}")
        if self.app_class is not None and self.sensor_state != "available":
            raise ValueError("app_class may only be set when sensor_state == 'available'")
        if self.sampled_at is not None and self.sampled_at.tzinfo is None:
            raise ValueError("sampled_at must include timezone")

    def to_health(self, *, now: datetime | None = None) -> dict[str, object]:
        current = (now or _utc_now()).astimezone(timezone.utc)
        age_seconds = None
        if self.sampled_at is not None:
            sampled = self.sampled_at.astimezone(timezone.utc)
            age_seconds = int((current - sampled).total_seconds())
        return {
            "schema_version": self.schema_version,
            "sensor_state": self.sensor_state,
            "app_class": self.app_class,
            "reason": self.reason,
            "age_seconds": age_seconds,
        }


def _desktop_availability() -> tuple[str, str]:
    """Return (sensor_state, reason) for honest desktop reachability."""
    if not body_capabilities.has_binary("xdotool"):
        return "unavailable", "tools_missing"
    if not os.environ.get("DISPLAY"):
        return "unavailable", "wayland"
    if not body_capabilities.desktop_session_reachable():
        return "unavailable", "session_unreachable"
    return "available", ""


def sample_desktop_presence(
    env: Mapping[str, str],
    *,
    now: datetime | None = None,
    availability_fn: Callable[[], tuple[str, str]] = _desktop_availability,
    active_window_fn: Callable[[], dict | None] | None = None,
) -> DesktopPresenceState:
    """Sample the desktop sense.

    Returns a fresh state each call. Blind beats stale: an unavailable sample
    never carries a previous app class.
    """
    mode = (env.get(PERCEPTION_ENV) or "0").strip()
    if mode in {"", "0"}:
        return DesktopPresenceState(sensor_state="disabled")

    sampled = (now or _utc_now()).astimezone(timezone.utc)
    state, reason = availability_fn()
    if state == "unavailable":
        return DesktopPresenceState(
            sensor_state="unavailable",
            reason=reason,
            sampled_at=sampled,
        )

    win_fn = active_window_fn
    if win_fn is None:
        from core.memory.ambient import active_window as win_fn

    window = win_fn()
    app_class = (window or {}).get("class") if window else None
    if not app_class:
        return DesktopPresenceState(
            sensor_state="unavailable",
            reason="no_active_window",
            sampled_at=sampled,
        )
    return DesktopPresenceState(
        sensor_state="available",
        app_class=str(app_class),
        sampled_at=sampled,
    )
