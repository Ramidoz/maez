"""Offline Calendar v1 connector policy.

No OAuth and no Google client live here. This module is the deterministic
boundary a future connector must pass through before provider events can reach
Calendar's noncanonical staging store.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any


DEFAULT_GOOGLE_SCOPE = "https://www.googleapis.com/auth/calendar.events.owned.readonly"
FALLBACK_GOOGLE_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"
FORBIDDEN_BROAD_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

_SAFE_CALENDAR_EVENT = "[calendar event]"
_REDACTED_CALENDAR_DETAIL = "[redacted calendar detail]"
_SENSITIVE_CALENDAR_DETAIL = "[sensitive calendar detail]"
_THIRD_PARTY_CALENDAR_DETAIL = "[redacted third-party calendar detail]"

_BODY_ADJACENT_RE = re.compile(
    r"\b("
    r"doctor|medical|therapy|therapist|psychiat|clinic|hospital|lawyer|legal|court|"
    r"divorce|religion|church|mosque|temple|politic|sexual|address|home address"
    r")\b",
    re.IGNORECASE,
)
_THIRD_PARTY_RE = re.compile(
    r"\b(with|for|about|re:)\s+[A-Z][A-Za-z]{2,}\b|"
    r"\b[A-Z][a-z]+\s+(home|address|divorce|therapy|lawyer)\b"
)


class CalendarPolicyError(ValueError):
    """Raised when Calendar connector configuration violates Decision 28."""


@dataclass(frozen=True)
class CalendarSelection:
    calendar_id: str = "primary"
    owned: bool = True
    horizon_days_forward: int = 14


@dataclass(frozen=True)
class CalendarPolicyResult:
    accepted: bool
    reason: str
    facts: dict[str, Any] = field(default_factory=dict)
    external_event_id_hash: str = ""
    source_revision_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "facts": dict(self.facts),
            "external_event_id_hash": self.external_event_id_hash,
            "source_revision_hash": self.source_revision_hash,
        }


def validate_requested_scope(scope: str, *, allow_fallback: bool = False) -> str:
    """Return the approved scope or reject broad Calendar access."""

    if scope == FORBIDDEN_BROAD_SCOPE:
        raise CalendarPolicyError("calendar.readonly is forbidden in Calendar v1")
    if scope == FALLBACK_GOOGLE_SCOPE and not allow_fallback:
        raise CalendarPolicyError("fallback Calendar scope requires explicit escalation")
    if scope not in {DEFAULT_GOOGLE_SCOPE, FALLBACK_GOOGLE_SCOPE}:
        raise CalendarPolicyError(f"unsupported Calendar scope: {scope!r}")
    return scope


def normalize_provider_event(
    event: dict[str, Any],
    *,
    selection: CalendarSelection,
    now: datetime,
) -> CalendarPolicyResult:
    """Minimize one Google Calendar event into content-free/redacted facts."""

    external_event_id = _require_string(event.get("id"), "id")
    source_revision = _require_string(event.get("updated"), "updated")
    external_event_id_hash = _hash_handle(selection.calendar_id, external_event_id)
    source_revision_hash = _hash_handle(selection.calendar_id, source_revision)

    if selection.calendar_id != "primary":
        return _reject("non_primary_calendar", external_event_id_hash, source_revision_hash)
    if not selection.owned or not _provider_owner_evidence(event):
        return _reject("non_owned_event", external_event_id_hash, source_revision_hash)

    start_at = _parse_event_start(event.get("start") or {})
    end_at = _parse_event_end(event.get("end") or {}, fallback_start=start_at)
    if start_at is None:
        return _reject("missing_start", external_event_id_hash, source_revision_hash)

    now_utc = _as_utc(now)
    horizon_end = now_utc + timedelta(days=selection.horizon_days_forward)
    event_end = end_at or start_at
    if event_end < now_utc:
        return _reject("before_forward_window", external_event_id_hash, source_revision_hash)
    if start_at > horizon_end:
        return _reject("outside_forward_window", external_event_id_hash, source_revision_hash)

    facts = {
        "safe_title_token": _safe_token(event.get("summary")),
        "safe_location_token": _safe_token(event.get("location")),
        "attendee_count": len(event.get("attendees") or []),
        "provider_status": _safe_status(event.get("status")),
    }
    return CalendarPolicyResult(
        accepted=True,
        reason="accepted",
        facts=facts,
        external_event_id_hash=external_event_id_hash,
        source_revision_hash=source_revision_hash,
    )


def attendee_audit_handle(
    *,
    attendee_identity: str,
    source_instance_id: str,
    external_event_id: str,
    purpose: str,
    hmac_key: str,
) -> str:
    """Return an event-lineage-scoped handle, not a people-profile key."""

    if not isinstance(purpose, str) or not purpose.strip():
        raise CalendarPolicyError("attendee HMAC purpose is required")
    if not isinstance(hmac_key, str) or len(hmac_key) < 8:
        raise CalendarPolicyError("attendee hmac key is missing or too short")
    material = "|".join(
        (
            purpose.strip().lower(),
            source_instance_id.strip().lower(),
            external_event_id.strip(),
            attendee_identity.strip().lower(),
        )
    )
    digest = hmac.new(hmac_key.encode("utf-8"), material.encode("utf-8"), hashlib.sha256)
    return "attendee_hmac:" + digest.hexdigest()


def _reject(
    reason: str, external_event_id_hash: str, source_revision_hash: str
) -> CalendarPolicyResult:
    return CalendarPolicyResult(
        accepted=False,
        reason=reason,
        external_event_id_hash=external_event_id_hash,
        source_revision_hash=source_revision_hash,
    )


def _safe_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return _SAFE_CALENDAR_EVENT
    third_party = bool(_THIRD_PARTY_RE.search(text))
    sensitive = bool(_BODY_ADJACENT_RE.search(text))
    if third_party:
        return _THIRD_PARTY_CALENDAR_DETAIL
    if sensitive:
        return _SENSITIVE_CALENDAR_DETAIL
    return _SAFE_CALENDAR_EVENT


def _safe_status(value: Any) -> str:
    raw = str(value or "confirmed").strip().lower()
    if raw in {"confirmed", "tentative", "cancelled"}:
        return raw
    return "unknown"


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalendarPolicyError(f"provider event missing {name}")
    return value.strip()


def _hash_handle(source_instance_id: str, value: str) -> str:
    payload = f"calendar.v1|{source_instance_id}|{value}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _parse_event_start(start: dict[str, Any]) -> datetime | None:
    if not isinstance(start, dict):
        return None
    if isinstance(start.get("dateTime"), str):
        return _parse_datetime(start["dateTime"])
    if isinstance(start.get("date"), str):
        parsed = date.fromisoformat(start["date"])
        return datetime.combine(parsed, time.min, tzinfo=timezone.utc)
    return None


def _parse_event_end(end: dict[str, Any], *, fallback_start: datetime | None) -> datetime | None:
    if not isinstance(end, dict):
        return fallback_start
    if isinstance(end.get("dateTime"), str):
        return _parse_datetime(end["dateTime"])
    if isinstance(end.get("date"), str):
        parsed = date.fromisoformat(end["date"])
        return datetime.combine(parsed, time.min, tzinfo=timezone.utc)
    return fallback_start


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _provider_owner_evidence(event: dict[str, Any]) -> bool:
    organizer = event.get("organizer") or {}
    creator = event.get("creator") or {}
    return bool(
        isinstance(organizer, dict)
        and organizer.get("self") is True
        or isinstance(creator, dict)
        and creator.get("self") is True
    )
