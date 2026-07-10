# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Slice 4 dormant GNOME/Wayland active-window sensor (ADR 0009/0029).

Mechanism: one read-only `FocusedWindow.Get` D-Bus call supplies the exact
title/class/window-actor snapshot used by Decision-9 preflight and geometry.
Mutter `DisplayConfig.GetCurrentState` supplies only display identity, logical
bounds, native dimensions, scale, and serial. The system-Python Gio helper is
required because the Maez venv has no PyGObject.

GNOME/Wayland may deny either D-Bus surface, the extension may be absent, and a
display may reconfigure or expose unusable geometry. Each case is a typed
refusal. There is deliberately no X11 or full-desktop fallback. This module
does not read pixels and has no production caller in Slice 4.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Literal

from core.vision_contract.geometry import WindowGeometry
from core.vision_contract.screen_privacy import screen_privacy_state

SCHEMA_VERSION = "active_window_geometry.v2"
COORDINATE_SPACE = "display_local_native_device_pixels"
_SYSTEM_PYTHON = "/usr/bin/python3"
_PROBE_HELPER = Path(__file__).resolve().parents[2] / "scripts" / "active_window_geometry_probe.py"
_PROBE_STATUSES = frozenset(
    {
        "compositor_unreachable",
        "compositor_protocol_invalid",
        "geometry_unavailable",
        "display_unavailable",
        "display_config_changed",
        "unsupported_session",
    }
)
_MAX_DISPLAYS = 16
_MAX_TIMEOUT_SECONDS = 10.0
MAX_WINDOW_ID_CHARS = 256
RefusalReason = Literal[
    "paused",
    "curtain_drawn",
    "compositor_unreachable",
    "compositor_protocol_invalid",
    "unsupported_session",
    "display_config_changed",
    "window_unavailable",
    "class_unavailable",
    "window_schema_invalid",
    "sensitive_window",
    "geometry_unavailable",
    "degenerate_bounds",
    "display_unavailable",
    "cross_display_bounds",
    "off_screen_bounds",
    "scale_unavailable",
]
_REFUSAL_REASONS = frozenset(RefusalReason.__args__)


@dataclass(frozen=True)
class FocusBinding:
    pid: int
    window_id: str = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.pid) is not int or self.pid <= 0:
            raise ValueError("binding pid must be a positive integer")
        if (
            not isinstance(self.window_id, str)
            or not self.window_id.strip()
            or len(self.window_id) > MAX_WINDOW_ID_CHARS
            or any(unicodedata.category(character).startswith("C") for character in self.window_id)
        ):
            raise ValueError("binding window id is required")


@dataclass(frozen=True)
class ActiveWindowReading:
    state: str
    timestamp: datetime
    reason: RefusalReason | Literal[""] = ""
    app_class: str | None = None
    geometry: WindowGeometry | None = None
    binding: FocusBinding | None = field(default=None, repr=False)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported active-window schema")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must include timezone")
        if self.binding is not None and not isinstance(self.binding, FocusBinding):
            raise ValueError("invalid focus binding")
        if self.state == "available":
            if not self.app_class or self.geometry is None or self.reason:
                raise ValueError("available reading requires class and geometry")
        elif self.state in {"excluded", "refused"}:
            if (
                self.app_class is not None
                or self.geometry is not None
                or self.binding is not None
                or not self.reason
            ):
                raise ValueError("refusal must be content-blind and typed")
            if self.reason not in _REFUSAL_REASONS:
                raise ValueError("unknown active-window refusal reason")
        else:
            raise ValueError("invalid active-window state")

    def to_receipt(self) -> dict[str, object]:
        receipt: dict[str, object] = {
            "schema_version": self.schema_version,
            "state": self.state,
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
            "refusal_reason": self.reason or None,
        }
        if self.state == "available":
            receipt["app_class"] = self.app_class
            receipt["geometry"] = self.geometry.to_receipt()
        return receipt


def read_compositor_snapshot(timeout: float = 1.0) -> dict[str, object]:
    """Run the fixed read-only Gio helper and return its bounded JSON packet."""
    if (
        type(timeout) not in {int, float}
        or not math.isfinite(timeout)
        or timeout <= 0
        or timeout > _MAX_TIMEOUT_SECONDS
    ):
        return {"status": "compositor_unreachable"}
    timeout_ms = max(1, int(timeout * 1000))
    try:
        completed = subprocess.run(
            [_SYSTEM_PYTHON, os.fspath(_PROBE_HELPER), str(timeout_ms)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return {"status": "compositor_unreachable"}
    if completed.returncode != 0:
        return {"status": "compositor_unreachable"}
    raw = (completed.stdout or "").strip()
    if not raw or len(raw) > 262_144:
        return {"status": "compositor_protocol_invalid"}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {"status": "compositor_protocol_invalid"}
    if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
        return {"status": "compositor_protocol_invalid"}
    return payload


def _reading(
    *,
    state: str,
    timestamp: datetime,
    reason: RefusalReason | Literal[""] = "",
    app_class: str | None = None,
    geometry: WindowGeometry | None = None,
    binding: FocusBinding | None = None,
) -> ActiveWindowReading:
    return ActiveWindowReading(
        state=state,
        timestamp=timestamp.astimezone(timezone.utc),
        reason=reason,
        app_class=app_class,
        geometry=geometry,
        binding=binding,
    )


def _refusal(
    timestamp: datetime,
    reason: RefusalReason,
    *,
    excluded: bool = False,
) -> ActiveWindowReading:
    return _reading(
        state="excluded" if excluded else "refused",
        timestamp=timestamp,
        reason=reason,
    )


def _exact_ints(source: Mapping[str, object], names: tuple[str, ...]) -> tuple[int, ...] | None:
    values = tuple(source.get(name) for name in names)
    if any(type(value) is not int for value in values):
        return None
    return values  # type: ignore[return-value]


def _overlaps(window: tuple[int, int, int, int], display: tuple[int, int, int, int]) -> bool:
    wx, wy, ww, wh = window
    dx, dy, dw, dh = display
    return wx < dx + dw and wx + ww > dx and wy < dy + dh and wy + wh > dy


def _contains(window: tuple[int, int, int, int], display: tuple[int, int, int, int]) -> bool:
    wx, wy, ww, wh = window
    dx, dy, dw, dh = display
    return wx >= dx and wy >= dy and wx + ww <= dx + dw and wy + wh <= dy + dh


def _scale_fraction(value: object) -> tuple[Decimal, Fraction] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        decimal = Decimal(value)
    except InvalidOperation:
        return None
    if not decimal.is_finite() or decimal <= 0:
        return None
    return decimal, Fraction(decimal)


def sample_active_window(
    *,
    now: datetime | None = None,
    probe_fn: Callable[[float], Mapping[str, object]] = read_compositor_snapshot,
    privacy_fn: Callable[[], str | None] | None = None,
    timeout: float = 1.0,
) -> ActiveWindowReading:
    """Sample one bounded window snapshot; never capture or publish a title."""
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    privacy_check = privacy_fn or screen_privacy_state
    privacy = privacy_check()
    if privacy in {"paused", "curtain_drawn"}:
        return _refusal(timestamp, privacy)

    try:
        payload = probe_fn(timeout)
    except Exception:
        return _refusal(timestamp, "compositor_unreachable")
    privacy = privacy_check()
    if privacy in {"paused", "curtain_drawn"}:
        return _refusal(timestamp, privacy)
    if not isinstance(payload, Mapping):
        return _refusal(timestamp, "compositor_protocol_invalid")
    status = payload.get("status")
    if status != "ok":
        reason = (
            status
            if isinstance(status, str) and status in _PROBE_STATUSES
            else "compositor_protocol_invalid"
        )
        return _refusal(timestamp, reason)

    window = payload.get("window")
    if not isinstance(window, Mapping):
        return _refusal(timestamp, "window_unavailable", excluded=True)

    # The existing screen preflight remains the sole Decision-9 authority.
    # Passing this exact snapshot closes the old read-preflight-read TOCTOU.
    from skills.screen_perception import active_window_preflight_reason

    exclusion_reason = active_window_preflight_reason(window)
    if exclusion_reason is not None:
        return _refusal(timestamp, exclusion_reason, excluded=True)

    app_class = window.get("class")
    assert isinstance(app_class, str)  # guaranteed by the preflight authority
    window_rect = _exact_ints(window, ("x", "y", "width", "height"))
    if window_rect is None:
        return _refusal(timestamp, "geometry_unavailable")
    wx, wy, ww, wh = window_rect
    if ww <= 0 or wh <= 0:
        return _refusal(timestamp, "degenerate_bounds")

    serial = payload.get("display_config_serial")
    displays = payload.get("displays")
    if (
        type(serial) is not int
        or serial < 0
        or not isinstance(displays, list)
        or not displays
        or len(displays) > _MAX_DISPLAYS
    ):
        return _refusal(timestamp, "display_unavailable")

    normalized: list[tuple[Mapping[str, object], tuple[int, int, int, int]]] = []
    for display in displays:
        if not isinstance(display, Mapping):
            return _refusal(timestamp, "display_unavailable")
        logical = _exact_ints(display, ("x", "y", "logical_width", "logical_height"))
        if logical is None or logical[2] <= 0 or logical[3] <= 0:
            return _refusal(timestamp, "display_unavailable")
        normalized.append((display, logical))

    overlapping = [item for item in normalized if _overlaps(window_rect, item[1])]
    if len(overlapping) > 1:
        return _refusal(timestamp, "cross_display_bounds")
    containing = [item for item in normalized if _contains(window_rect, item[1])]
    if len(containing) != 1:
        return _refusal(timestamp, "off_screen_bounds")
    display, (dx, dy, logical_width, logical_height) = containing[0]

    display_id = display.get("display_id")
    native = _exact_ints(display, ("native_width", "native_height"))
    scale_values = _scale_fraction(display.get("scale"))
    if not isinstance(display_id, str) or not display_id.strip() or native is None:
        return _refusal(timestamp, "display_unavailable")
    native_width, native_height = native
    if native_width <= 0 or native_height <= 0 or scale_values is None:
        return _refusal(timestamp, "scale_unavailable")
    scale, fraction = scale_values
    if (Decimal(logical_width) * scale).to_integral_value(
        rounding=ROUND_CEILING
    ) != native_width or (Decimal(logical_height) * scale).to_integral_value(
        rounding=ROUND_CEILING
    ) != native_height:
        return _refusal(timestamp, "scale_unavailable")

    local_left = Decimal(wx - dx) * scale
    local_top = Decimal(wy - dy) * scale
    local_right = Decimal(wx - dx + ww) * scale
    local_bottom = Decimal(wy - dy + wh) * scale
    left = int(local_left.to_integral_value(rounding=ROUND_FLOOR))
    top = int(local_top.to_integral_value(rounding=ROUND_FLOOR))
    right = int(local_right.to_integral_value(rounding=ROUND_CEILING))
    bottom = int(local_bottom.to_integral_value(rounding=ROUND_CEILING))
    if left < 0 or top < 0 or right <= left or bottom <= top:
        return _refusal(timestamp, "degenerate_bounds")
    if right > native_width or bottom > native_height:
        return _refusal(timestamp, "off_screen_bounds")

    geometry = WindowGeometry(
        x=left,
        y=top,
        width=right - left,
        height=bottom - top,
        display_id=display_id.strip(),
        display_width=native_width,
        display_height=native_height,
        scale_numerator=fraction.numerator,
        scale_denominator=fraction.denominator,
        display_config_serial=serial,
        coordinate_space=COORDINATE_SPACE,
    )
    privacy = privacy_check()
    if privacy in {"paused", "curtain_drawn"}:
        return _refusal(timestamp, privacy)
    binding = None
    raw_pid = window.get("pid")
    raw_window_id = window.get("id")
    if type(raw_pid) is int and isinstance(raw_window_id, str):
        try:
            binding = FocusBinding(pid=raw_pid, window_id=raw_window_id)
        except ValueError:
            binding = None
    return _reading(
        state="available",
        timestamp=timestamp,
        app_class=app_class.strip(),
        geometry=geometry,
        binding=binding,
    )
