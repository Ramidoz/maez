# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Temporal Spine v1: UTC instants, owner-local human days.

Decision 29 / ADR 0034. This module is intentionally store-agnostic: it must
not import memory stores or information-limb stores at module load time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import inspect
import os
import threading
from typing import Literal, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.memory import identity as _identity


TemporalInstantFieldName = Literal[
    "event_at",
    "ingested_at",
    "observed_at",
    "received_at",
    "expires_at",
    "deletion_observed_at",
    "change_observed_at",
    "valid_from",
    "valid_to",
]

TemporalDerivedFieldName = Literal["owner_local_date",]

TemporalAnchorKind = Literal[
    "earlier_today",
    "this_morning",
    "yesterday",
    "last_week",
]

HelperUnavailableReason = Literal["temporal_helper_exception",]

TimezoneSource = Literal["identity", "env", "fallback_utc", "invalid_fallback_utc"]

_INSTANT_FIELDS = frozenset(get_args(TemporalInstantFieldName))
_ANCHOR_KINDS = frozenset(get_args(TemporalAnchorKind))
_HELPER_UNAVAILABLE_REASONS = frozenset(get_args(HelperUnavailableReason))


@dataclass(frozen=True)
class TemporalWindow:
    anchor_kind: TemporalAnchorKind
    start: datetime
    end: datetime
    start_utc: datetime
    end_utc: datetime
    timezone_name: str


@dataclass(frozen=True)
class TemporalDiagnostics:
    timezone_source: TimezoneSource
    timezone_name: str
    invalid_field_name_rejected_count: int
    malformed_timestamp_rejected_count: int
    naive_timestamp_assumed_utc_count: int
    unsupported_anchor_rejected_count: int
    helper_unavailable_count: int


_LOCK = threading.RLock()
_COUNTERS = {
    "invalid_field_name_rejected_count": 0,
    "malformed_timestamp_rejected_count": 0,
    "naive_timestamp_assumed_utc_count": 0,
    "unsupported_anchor_rejected_count": 0,
    "helper_unavailable_count": 0,
}
_LAST_TIMEZONE_SOURCE: TimezoneSource = "fallback_utc"
_LAST_TIMEZONE_NAME = "UTC"


def _increment(counter_name: str) -> None:
    with _LOCK:
        _COUNTERS[counter_name] = int(_COUNTERS.get(counter_name, 0)) + 1


def _remember_timezone(source: TimezoneSource, zone_name: str) -> None:
    global _LAST_TIMEZONE_SOURCE, _LAST_TIMEZONE_NAME
    with _LOCK:
        _LAST_TIMEZONE_SOURCE = source
        _LAST_TIMEZONE_NAME = zone_name


def owner_timezone() -> ZoneInfo:
    """Resolve the bonded user's timezone per call.

    Source precedence is MAEZ_OWNER_TIMEZONE, then identity.yaml, then UTC.
    Invalid configured values fail closed to UTC without exposing the raw value.
    """

    raw_env = os.environ.get("MAEZ_OWNER_TIMEZONE")
    if raw_env is not None and raw_env.strip():
        return _zone_or_utc(raw_env.strip(), source="env")
    try:
        raw_identity = _identity.timezone()
    except Exception:
        return _zone_or_utc(None, source="invalid_fallback_utc")
    if not raw_identity or not str(raw_identity).strip():
        return _zone_or_utc(None, source="fallback_utc")
    return _zone_or_utc(str(raw_identity).strip(), source="identity")


def _zone_or_utc(candidate: str | None, *, source: TimezoneSource) -> ZoneInfo:
    if not candidate:
        _remember_timezone("fallback_utc" if source != "invalid_fallback_utc" else source, "UTC")
        return ZoneInfo("UTC")
    try:
        zone = ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        _remember_timezone("invalid_fallback_utc", "UTC")
        return ZoneInfo("UTC")
    _remember_timezone(source, zone.key)
    return zone


def timezone_source() -> str:
    return diagnostics_snapshot().timezone_source


def _validate_field_name(field_name: str) -> None:
    if field_name not in _INSTANT_FIELDS:
        _increment("invalid_field_name_rejected_count")
        raise ValueError("invalid temporal instant field name")


def canonical_utc(value: str | datetime, *, field_name: TemporalInstantFieldName) -> datetime:
    """Return an aware UTC datetime for an accepted temporal instant field."""

    _validate_field_name(str(field_name))
    parsed = _parse_instant(value)
    if parsed.tzinfo is None:
        _increment("naive_timestamp_assumed_utc_count")
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        _validate_existing_local_datetime(parsed)
    return parsed.astimezone(timezone.utc)


def canonical_utc_iso(value: str | datetime, *, field_name: TemporalInstantFieldName) -> str:
    return canonical_utc(value, field_name=field_name).isoformat()


def owner_local_date(value: str | datetime) -> date:
    return canonical_utc(value, field_name="event_at").astimezone(owner_timezone()).date()


def temporal_window(anchor_kind: TemporalAnchorKind, reference_time: datetime) -> TemporalWindow:
    if anchor_kind not in _ANCHOR_KINDS:
        _increment("unsupported_anchor_rejected_count")
        raise ValueError("unsupported temporal anchor kind")

    zone = owner_timezone()
    ref = _reference_as_owner_local(reference_time, zone)
    start_today = datetime.combine(ref.date(), time.min, tzinfo=zone)
    if anchor_kind == "earlier_today":
        start, end = start_today, ref
    elif anchor_kind == "this_morning":
        start = start_today
        end = datetime.combine(ref.date(), time(12, 0), tzinfo=zone)
    elif anchor_kind == "yesterday":
        end = start_today
        start = end - timedelta(days=1)
    elif anchor_kind == "last_week":
        this_monday = start_today - timedelta(days=start_today.weekday())
        start = this_monday - timedelta(days=7)
        end = this_monday
    else:  # pragma: no cover - closed Literal above, kept defensive.
        _increment("unsupported_anchor_rejected_count")
        raise ValueError("unsupported temporal anchor kind")

    return TemporalWindow(
        anchor_kind=anchor_kind,
        start=start,
        end=end,
        start_utc=start.astimezone(timezone.utc),
        end_utc=end.astimezone(timezone.utc),
        timezone_name=zone.key,
    )


def half_open_contains(value: str | datetime, *, start: datetime, end: datetime) -> bool:
    start_utc = _aware_bound_to_utc(start, name="start")
    end_utc = _aware_bound_to_utc(end, name="end")
    instant = canonical_utc(value, field_name="event_at")
    return start_utc <= instant < end_utc


def record_helper_unavailable(reason: HelperUnavailableReason) -> None:
    if reason not in _HELPER_UNAVAILABLE_REASONS:
        return
    _increment("helper_unavailable_count")


def diagnostics_snapshot() -> TemporalDiagnostics:
    with _LOCK:
        return TemporalDiagnostics(
            timezone_source=_LAST_TIMEZONE_SOURCE,
            timezone_name=_LAST_TIMEZONE_NAME,
            invalid_field_name_rejected_count=int(_COUNTERS["invalid_field_name_rejected_count"]),
            malformed_timestamp_rejected_count=int(_COUNTERS["malformed_timestamp_rejected_count"]),
            naive_timestamp_assumed_utc_count=int(_COUNTERS["naive_timestamp_assumed_utc_count"]),
            unsupported_anchor_rejected_count=int(_COUNTERS["unsupported_anchor_rejected_count"]),
            helper_unavailable_count=int(_COUNTERS["helper_unavailable_count"]),
        )


def temporal_spine_health() -> dict:
    owner_timezone()
    snap = diagnostics_snapshot()
    return {
        "timezone_source": snap.timezone_source,
        "timezone_name": snap.timezone_name,
        "invalid_field_name_rejected_count": snap.invalid_field_name_rejected_count,
        "malformed_timestamp_rejected_count": snap.malformed_timestamp_rejected_count,
        "naive_timestamp_assumed_utc_count": snap.naive_timestamp_assumed_utc_count,
        "unsupported_anchor_rejected_count": snap.unsupported_anchor_rejected_count,
        "helper_unavailable_count": snap.helper_unavailable_count,
    }


def _reset_diagnostics_for_tests() -> None:
    if not _called_from_tests():
        raise RuntimeError("_reset_diagnostics_for_tests is only callable from tests")
    global _LAST_TIMEZONE_SOURCE, _LAST_TIMEZONE_NAME
    with _LOCK:
        for key in _COUNTERS:
            _COUNTERS[key] = 0
        _LAST_TIMEZONE_SOURCE = "fallback_utc"
        _LAST_TIMEZONE_NAME = "UTC"


def _called_from_tests() -> bool:
    for frame in inspect.stack()[1:]:
        normalized = frame.filename.replace("\\", "/")
        if "/tests/" in normalized or normalized.endswith("/tests"):
            return True
    return False


def _parse_instant(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        _increment("malformed_timestamp_rejected_count")
        raise ValueError("malformed temporal instant")
    raw = value.strip()
    if "T" not in raw and " " not in raw:
        _increment("malformed_timestamp_rejected_count")
        raise ValueError("bare dates are not temporal instants")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        _increment("malformed_timestamp_rejected_count")
        raise ValueError("malformed temporal instant") from exc


def _reference_as_owner_local(reference_time: datetime, zone: ZoneInfo) -> datetime:
    if reference_time.tzinfo is None:
        candidate = reference_time.replace(tzinfo=zone)
    else:
        candidate = reference_time.astimezone(zone)
        if getattr(reference_time.tzinfo, "key", None) == zone.key:
            candidate = reference_time
    _validate_existing_local_datetime(candidate, owner_zone=zone)
    return candidate


def _aware_bound_to_utc(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} bound must be timezone-aware")
    return value.astimezone(timezone.utc)


def _validate_existing_local_datetime(
    value: datetime,
    *,
    owner_zone: ZoneInfo | None = None,
) -> None:
    zone_key = getattr(value.tzinfo, "key", None)
    if zone_key is None:
        return
    zone = owner_zone or ZoneInfo(zone_key)
    if zone_key != zone.key:
        return
    roundtrip = value.astimezone(timezone.utc).astimezone(zone)
    if roundtrip.replace(tzinfo=None) != value.replace(tzinfo=None) or getattr(
        roundtrip, "fold", 0
    ) != getattr(value, "fold", 0):
        _increment("malformed_timestamp_rejected_count")
        raise ValueError("nonexistent owner-local datetime")


__all__ = [
    "HelperUnavailableReason",
    "TemporalAnchorKind",
    "TemporalDerivedFieldName",
    "TemporalDiagnostics",
    "TemporalInstantFieldName",
    "TemporalWindow",
    "canonical_utc",
    "canonical_utc_iso",
    "diagnostics_snapshot",
    "half_open_contains",
    "owner_local_date",
    "owner_timezone",
    "record_helper_unavailable",
    "temporal_spine_health",
    "temporal_window",
    "timezone_source",
    "_reset_diagnostics_for_tests",
]
