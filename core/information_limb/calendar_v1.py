"""Calendar v1 content-free runtime surface.

This module intentionally does not talk to Google. The first implementation
step is the safe shell: default-disabled state, content-free health, and a
place for the future S2-bounded connector to report non-content telemetry.
"""

from __future__ import annotations

from typing import Literal, TypedDict


CalendarConnectorState = Literal[
    "disabled",
    "auth_unavailable",
    "ready",
    "stale",
    "provider_rate_limited",
    "provider_backend_error",
    "source_unavailable",
]


class CalendarHealth(TypedDict):
    mode: str
    source_kind: str
    connector_state: str
    event_count: int
    read_model_count: int
    newest_age_bucket: str
    oldest_age_bucket: str
    error_class: str


def build_calendar_health(
    *,
    mode: str,
    auth_ready: bool = False,
    connector_state_override: CalendarConnectorState | None = None,
    event_count: int = 0,
    read_model_count: int = 0,
    newest_age_bucket: str = "none",
    oldest_age_bucket: str = "none",
    error_class: str = "",
) -> CalendarHealth:
    """Build Decision-28-compliant aggregate health telemetry."""

    if connector_state_override is not None:
        connector_state = connector_state_override
        error = error_class
    elif mode == "disabled":
        connector_state: CalendarConnectorState = "disabled"
        error = ""
    elif mode == "v1" and not auth_ready:
        connector_state = "auth_unavailable"
        error = error_class or "auth_access_expired"
    else:
        connector_state = "ready"
        error = error_class

    return {
        "mode": mode,
        "source_kind": "calendar.event",
        "connector_state": connector_state,
        "event_count": int(event_count),
        "read_model_count": int(read_model_count),
        "newest_age_bucket": newest_age_bucket,
        "oldest_age_bucket": oldest_age_bucket,
        "error_class": error,
    }
