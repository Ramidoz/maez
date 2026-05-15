"""Offline Google Calendar request builders for Calendar v1.

These functions construct dictionaries suitable for
``events().list(**request)`` later. They do not import Google libraries, read
credentials, or perform network I/O.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


DEFAULT_HORIZON_DAYS_FORWARD = 14

_FIELDS = (
    "nextPageToken,nextSyncToken,"
    "items(id,updated,status,summary,location,start,end,"
    "attendees(email,responseStatus,self),organizer(self),creator(self))"
)


class CalendarSyncRequestError(ValueError):
    """Raised when Calendar sync request construction would violate v1."""


def build_initial_events_request(
    *,
    calendar_id: str,
    now: datetime,
    horizon_days_forward: int = DEFAULT_HORIZON_DAYS_FORWARD,
) -> dict:
    """Build the bounded initial/full-sync request shape."""

    now_utc = _as_utc(now)
    return {
        "calendarId": _require_non_empty(calendar_id, "calendar id"),
        "singleEvents": True,
        "orderBy": "startTime",
        "showDeleted": True,
        "timeMin": _rfc3339(now_utc),
        "timeMax": _rfc3339(now_utc + timedelta(days=horizon_days_forward)),
        "fields": _FIELDS,
    }


def build_incremental_events_request(*, calendar_id: str, sync_token: str) -> dict:
    """Build an incremental request without query/window filters."""

    return {
        "calendarId": _require_non_empty(calendar_id, "calendar id"),
        "syncToken": _require_non_empty(sync_token, "sync token"),
        "singleEvents": True,
        "showDeleted": True,
        "fields": _FIELDS,
    }


def _require_non_empty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalendarSyncRequestError(f"missing {name}")
    return value.strip()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _rfc3339(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
