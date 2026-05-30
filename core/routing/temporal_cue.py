# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Absolute-date recall cue detection — single source of truth.

Lightweight on purpose: memory_manager, brain_loop, focused_cognition, and the
daemon all need to agree on calendar-address detection without importing each
other. ``_absolute_date_window`` is the low-level parser; ``absolute_recall_cue``
is the behavior-driving resolver.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.time.temporal_spine import owner_timezone


@dataclass(frozen=True)
class AbsoluteRecallWindow:
    """Owner-local absolute-date recall window expressed as UTC bounds.

    ``confidence`` is intentionally a growth seam for richer address weighing;
    v1 keeps the deterministic resolver small and auditable.
    """

    start_utc: datetime
    end_utc: datetime
    method: str
    confidence: str
    label: str


@dataclass(frozen=True)
class AbsoluteRecallCue:
    window: AbsoluteRecallWindow | None
    is_address: bool
    override_continuity: bool
    reason: str


_NIGHTLY_FWD_TOL_DAYS = 2

_MONTH_NAMES: dict[str, int] = {}
for _i in range(1, 13):
    _MONTH_NAMES[calendar.month_name[_i].lower()] = _i
    _MONTH_NAMES[calendar.month_abbr[_i].lower()] = _i

_MONTH_ALT = "|".join(re.escape(name) for name in _MONTH_NAMES)

_RECALL_INTENT = re.compile(
    r"\b(what (did|were|was)|what happened|what about|remind me what|did we|"
    r"we (were|did|discuss|discussed|talked|covered|noted)|working on)\b"
)
_FUTURE_OR_IMPERATIVE = re.compile(
    r"\b(will|i'?ll|shall|should|gonna|going to|let'?s|lets|need to|"
    r"remind me to|schedule|plan to|pick|choose)\b"
)
_INCIDENTAL_QTY = re.compile(rf"\b\d{{1,2}}\s+(?:{_MONTH_ALT})\s+[a-z]{{2,}}")


def _owner_local_to_utc(d: datetime) -> datetime:
    return d.astimezone(timezone.utc)


def _day_bounds_local(year: int, month: int, day: int, tz) -> tuple[datetime, datetime]:
    start = datetime(year, month, day, 0, 0, 0, tzinfo=tz)
    end = datetime(year, month, day, 23, 59, 59, tzinfo=tz)
    return start, end


def _most_recent_year_for(month: int, day: int, now_local: datetime) -> int:
    candidate = now_local.year
    try:
        if datetime(candidate, month, day, tzinfo=now_local.tzinfo) > now_local:
            candidate -= 1
    except ValueError:
        pass
    return candidate


def _exact_window(
    year: int,
    month: int,
    day: int,
    tz,
    symmetric: bool,
) -> AbsoluteRecallWindow | None:
    try:
        start_local, end_local = _day_bounds_local(year, month, day, tz)
    except ValueError:
        return None
    if symmetric:
        start_local = start_local - timedelta(days=_NIGHTLY_FWD_TOL_DAYS)
    end_local = end_local + timedelta(days=_NIGHTLY_FWD_TOL_DAYS)
    return AbsoluteRecallWindow(
        start_utc=_owner_local_to_utc(start_local),
        end_utc=_owner_local_to_utc(end_local),
        method="exact_date",
        confidence="high",
        label=(
            f"matched by exact date "
            f"({calendar.month_name[month]} {day}, {year} / "
            f"{year:04d}-{month:02d}-{day:02d})"
        ),
    )


def _month_window(
    year: int,
    month: int,
    tz,
    part: str | None = None,
) -> AbsoluteRecallWindow:
    last_day = calendar.monthrange(year, month)[1]
    if part in ("start", "beginning", "early"):
        day_start, day_end = 1, min(10, last_day)
    elif part in ("mid", "middle"):
        day_start, day_end = 11, min(20, last_day)
    elif part in ("end", "late"):
        day_start, day_end = 21, last_day
    else:
        day_start, day_end = 1, last_day
    start_local, _ = _day_bounds_local(year, month, day_start, tz)
    _, end_local = _day_bounds_local(year, month, day_end, tz)
    end_local = end_local + timedelta(days=_NIGHTLY_FWD_TOL_DAYS)
    return AbsoluteRecallWindow(
        start_utc=_owner_local_to_utc(start_local),
        end_utc=_owner_local_to_utc(end_local),
        method="month_window",
        confidence="medium",
        label=f"matched by month window ({calendar.month_name[month]} {year})",
    )


def _absolute_date_window(
    query: str,
    now_local: datetime | None = None,
) -> AbsoluteRecallWindow | None:
    """Resolve explicit owner-local date/month phrases to a UTC window."""
    if not query:
        return None
    tz = owner_timezone()
    if now_local is None:
        now_local = datetime.now(tz)
    q = (query or "").lower()
    symmetric = bool(re.search(r"\b(around|about|near|circa)\b", q))

    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", q)
    if iso:
        return _exact_window(
            int(iso.group(1)),
            int(iso.group(2)),
            int(iso.group(3)),
            tz,
            symmetric,
        )

    md = re.search(rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\b", q)
    if md:
        month = _MONTH_NAMES[md.group(1)]
        day = int(md.group(2))
        year = (
            int(md.group(3))
            if md.group(3)
            else _most_recent_year_for(month, day, now_local)
        )
        return _exact_window(year, month, day, tz, symmetric)

    dm = re.search(rf"\b(\d{{1,2}})\s+({_MONTH_ALT})\b", q)
    if dm:
        day = int(dm.group(1))
        month = _MONTH_NAMES[dm.group(2)]
        year = _most_recent_year_for(month, day, now_local)
        return _exact_window(year, month, day, tz, symmetric)

    if re.search(r"\blast month\b", q):
        prior_month = (now_local.replace(day=1) - timedelta(days=1)).replace(day=1)
        return _month_window(prior_month.year, prior_month.month, tz)
    if re.search(r"\bthis month\b", q):
        return _month_window(now_local.year, now_local.month, tz)

    part_match = re.search(
        rf"\b(start|beginning|early|mid|middle|end|late)\s+"
        rf"(?:of\s+)?({_MONTH_ALT})\b(?:\s+(\d{{4}}))?",
        q,
    )
    if part_match:
        month = _MONTH_NAMES[part_match.group(2)]
        year = (
            int(part_match.group(3))
            if part_match.group(3)
            else _most_recent_year_for(month, 15, now_local)
        )
        return _month_window(year, month, tz, part=part_match.group(1))

    in_month = re.search(rf"\bin\s+({_MONTH_ALT})\b(?:\s+(\d{{4}}))?", q)
    if in_month:
        month = _MONTH_NAMES[in_month.group(1)]
        year = (
            int(in_month.group(2))
            if in_month.group(2)
            else _most_recent_year_for(month, 15, now_local)
        )
        return _month_window(year, month, tz)

    explicit_year_month = re.search(rf"\b({_MONTH_ALT})\s+(\d{{4}})\b", q)
    if explicit_year_month:
        return _month_window(
            int(explicit_year_month.group(2)),
            _MONTH_NAMES[explicit_year_month.group(1)],
            tz,
        )
    return None


def absolute_recall_cue(
    question: str,
    now_local: datetime | None = None,
) -> AbsoluteRecallCue:
    """Return the behavior-driving absolute recall cue for a question."""
    q = " " + (question or "").lower().strip() + " "
    window = _absolute_date_window(question, now_local)
    if window is None:
        return AbsoluteRecallCue(None, False, False, "no_date_token")
    if _FUTURE_OR_IMPERATIVE.search(q):
        return AbsoluteRecallCue(window, False, False, "future_or_imperative")
    if _INCIDENTAL_QTY.search(q):
        return AbsoluteRecallCue(window, False, False, "incidental_quantity_phrase")
    if not _RECALL_INTENT.search(q):
        return AbsoluteRecallCue(window, False, False, "no_recall_intent")
    return AbsoluteRecallCue(window, True, True, "address")


def has_absolute_recall_cue(
    question: str,
    now_local: datetime | None = None,
) -> bool:
    """Parser-parity only; behavior keys on ``absolute_recall_cue``."""
    return _absolute_date_window(question, now_local) is not None
