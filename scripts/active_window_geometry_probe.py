#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Read-only GNOME/Wayland window + display-state probe for Vision Slice 4.

The FocusedWindow extension may be absent or GNOME may reject either D-Bus
call. Those cases emit a bounded typed status. This helper has no X11 fallback,
does not mutate the extension, and emits no diagnostics beyond its one JSON
return packet. The title is an ephemeral preflight input consumed by the parent
process and is never a receipt/log/prompt field.
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

FOCUSED_DEST = "org.gnome.Shell"
FOCUSED_PATH = "/org/gnome/shell/extensions/FocusedWindow"
FOCUSED_INTERFACE = "org.gnome.shell.extensions.FocusedWindow"
DISPLAY_DEST = "org.gnome.Mutter.DisplayConfig"
DISPLAY_PATH = "/org/gnome/Mutter/DisplayConfig"
DISPLAY_INTERFACE = "org.gnome.Mutter.DisplayConfig"


def _call_timeout_ms(total_timeout_ms: int) -> int:
    """Bound three D-Bus reads and leave one quarter for startup/normalization."""
    return max(1, total_timeout_ms // 4)


def _value(value):
    unpack = getattr(value, "unpack", None)
    return unpack() if callable(unpack) else value


def _current_mode(monitors) -> dict[tuple[str, str, str, str], tuple[int, int]]:
    current: dict[tuple[str, str, str, str], tuple[int, int]] = {}
    for specs, modes, _properties in monitors:
        key = tuple(str(part) for part in specs)
        if len(key) != 4:
            continue
        for mode in modes:
            if not isinstance(mode, (list, tuple)) or len(mode) != 7:
                continue
            _mode_id, width, height, _refresh, _preferred_scale, _scales, props = mode
            if bool(_value(props.get("is-current", False))):
                if type(width) is int and type(height) is int and width > 0 and height > 0:
                    current[key] = (width, height)
                break
    return current


def normalize_display_state(resources) -> tuple[int, list[dict[str, object]]]:
    """Normalize Gio-unpacked Mutter state to bounded compositor facts."""
    if not isinstance(resources, (list, tuple)) or len(resources) != 4:
        raise ValueError("display state shape")
    serial, monitors, logical_monitors, properties = resources
    if type(serial) is not int:
        raise ValueError("display serial")
    if not isinstance(properties, dict):
        raise ValueError("display properties")
    layout_mode = _value(properties.get("layout-mode", 1))
    # Mutter layout-mode 1 uses logical compositor coordinates. Physical (2)
    # and unknown modes use a different ruler and must never be scaled as if
    # they were logical.
    if type(layout_mode) is not int or layout_mode != 1:
        raise ValueError("unsupported display layout mode")
    if not isinstance(monitors, (list, tuple)) or not isinstance(logical_monitors, (list, tuple)):
        raise ValueError("display collections")
    current_modes = _current_mode(monitors)
    displays: list[dict[str, object]] = []
    for logical in logical_monitors:
        if not isinstance(logical, (list, tuple)) or len(logical) != 7:
            raise ValueError("logical monitor shape")
        x, y, raw_scale, transform, _primary, specs_list, _props = logical
        if (
            type(x) is not int
            or type(y) is not int
            or type(transform) is not int
            or transform not in range(8)
        ):
            raise ValueError("logical monitor values")
        try:
            scale = Decimal(str(raw_scale))
        except InvalidOperation as exc:
            raise ValueError("logical monitor scale") from exc
        if not scale.is_finite() or scale <= 0:
            raise ValueError("logical monitor scale")
        for specs in specs_list:
            key = tuple(str(part) for part in specs)
            native = current_modes.get(key)
            if len(key) != 4 or native is None:
                raise ValueError("active monitor mode")
            native_width, native_height = native
            if transform % 2:
                native_width, native_height = native_height, native_width
            logical_width = int(
                (Decimal(native_width) / scale).to_integral_value(rounding=ROUND_HALF_UP)
            )
            logical_height = int(
                (Decimal(native_height) / scale).to_integral_value(rounding=ROUND_HALF_UP)
            )
            if logical_width <= 0 or logical_height <= 0:
                raise ValueError("logical monitor bounds")
            displays.append(
                {
                    "display_id": key[0],
                    "x": x,
                    "y": y,
                    "logical_width": logical_width,
                    "logical_height": logical_height,
                    "native_width": native_width,
                    "native_height": native_height,
                    "scale": format(scale, "f"),
                }
            )
    if not displays:
        raise ValueError("no active displays")
    return serial, displays


def probe(timeout_ms: int) -> dict[str, object]:
    if os.environ.get("XDG_SESSION_TYPE", "").strip().lower() != "wayland" and not os.environ.get(
        "WAYLAND_DISPLAY"
    ):
        return {"status": "unsupported_session"}
    try:
        from gi.repository import Gio

        call_timeout_ms = _call_timeout_ms(timeout_ms)
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        display_before = bus.call_sync(
            DISPLAY_DEST,
            DISPLAY_PATH,
            DISPLAY_INTERFACE,
            "GetCurrentState",
            None,
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            call_timeout_ms,
            None,
        )
        serial_before, displays_before = normalize_display_state(display_before.unpack())
        focused_reply = bus.call_sync(
            FOCUSED_DEST,
            FOCUSED_PATH,
            FOCUSED_INTERFACE,
            "Get",
            None,
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            call_timeout_ms,
            None,
        )
        focused_values = focused_reply.unpack()
        if not isinstance(focused_values, (list, tuple)) or len(focused_values) != 1:
            return {"status": "compositor_protocol_invalid"}
        window = json.loads(focused_values[0])
        if not isinstance(window, dict):
            return {"status": "compositor_protocol_invalid"}

        display_after = bus.call_sync(
            DISPLAY_DEST,
            DISPLAY_PATH,
            DISPLAY_INTERFACE,
            "GetCurrentState",
            None,
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            call_timeout_ms,
            None,
        )
        serial_after, displays_after = normalize_display_state(display_after.unpack())
        if serial_before != serial_after or displays_before != displays_after:
            return {"status": "display_config_changed"}
    except (ImportError, OSError):
        return {"status": "compositor_unreachable"}
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {"status": "compositor_protocol_invalid"}
    except Exception:
        return {"status": "compositor_unreachable"}

    bounded_window = {
        "title": window.get("title"),
        "class": window.get("class") or window.get("wm_class"),
        "x": window.get("x"),
        "y": window.get("y"),
        "width": window.get("width"),
        "height": window.get("height"),
        "monitor": window.get("monitor"),
    }
    return {
        "status": "ok",
        "display_config_serial": serial_after,
        "window": bounded_window,
        "displays": displays_after,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        timeout_ms = int(args[0]) if len(args) == 1 else 1000
    except ValueError:
        timeout_ms = 1000
    timeout_ms = min(10_000, max(1, timeout_ms))
    if sys.stdout.isatty():
        result = {"status": "interactive_output_refused"}
    else:
        result = probe(timeout_ms)
    sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
