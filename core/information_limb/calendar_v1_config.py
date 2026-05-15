"""Calendar v1 process-start mode resolution.

Decision 28 / ADR 0033 requires Calendar to default to absent, with the old
raw Calendar path available only as an explicit developer test mode. Runtime
fallback to legacy Calendar is forbidden.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping


CALENDAR_MODE_ENV = "MAEZ_CALENDAR_MODE"
LEGACY_TEST_GATE_ENV = "MAEZ_CALENDAR_ALLOW_LEGACY_TEST_MODE"


class CalendarMode(str, Enum):
    DISABLED = "disabled"
    V1 = "v1"
    LEGACY_DEV_ONLY = "legacy_dev_only"


def resolve_calendar_mode(env: Mapping[str, str]) -> CalendarMode:
    """Resolve Calendar mode once at process start."""

    raw = (env.get(CALENDAR_MODE_ENV) or CalendarMode.DISABLED.value).strip().lower()
    if raw in {"", CalendarMode.DISABLED.value}:
        return CalendarMode.DISABLED
    if raw == CalendarMode.V1.value:
        return CalendarMode.V1
    if raw == CalendarMode.LEGACY_DEV_ONLY.value:
        if env.get(LEGACY_TEST_GATE_ENV) == "1":
            return CalendarMode.LEGACY_DEV_ONLY
        raise ValueError(f"{CALENDAR_MODE_ENV}=legacy_dev_only requires {LEGACY_TEST_GATE_ENV}=1")
    raise ValueError(
        f"unsupported {CALENDAR_MODE_ENV}={raw!r}; expected disabled, v1, or legacy_dev_only"
    )
