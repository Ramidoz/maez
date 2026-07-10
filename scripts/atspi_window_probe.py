#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Read-only GNOME AT-SPI adapter for Vision Slice 5.

AT-SPI exposes application-provided accessibility metadata, not pixel truth.
SHOWING/VISIBLE describe AT-SPI state and cannot prove cross-window occlusion.
All component extents are requested in WINDOW coordinates and calibrated to
the Slice 4 native-device-pixel crop. GNOME/Wayland or AT-SPI unavailability
is returned as a typed refusal; there is no X11, screenshot, or desktop-crop
fallback.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Any

sys.dont_write_bytecode = True

from core.body.active_window_sensor import (
    SCHEMA_VERSION as SLICE4_SCHEMA_VERSION,
    ActiveWindowReading,
    FocusBinding,
)
from core.body.atspi_sensor import (
    FIELD_KINDS,
    MAX_FIELDS,
    MAX_FIELD_CHARS,
    MAX_IDENTITY_ROOTS,
    MAX_NODES,
    MAX_TOP_LEVEL_WINDOWS,
    MAX_TOTAL_CHARS,
)
from core.vision_contract.geometry import CropBox, WindowGeometry
from core.vision_contract.screen_exclusion import MAX_DOCUMENT_REFS
from core.vision_contract.screen_privacy import screen_privacy_state

DOCUMENT_ATTRIBUTE_KEYS = frozenset(
    {"uri", "url", "docurl", "documenturi", "documenturl", "path", "documentpath"}
)


def _document_attribute_query_keys() -> tuple[str, ...]:
    word_sets = (
        ("uri",), ("url",), ("doc", "url"), ("document", "uri"),
        ("document", "url"), ("path",), ("document", "path"),
    )
    variants: set[str] = set()
    for words in word_sets:
        for separator in ("", "-", "_"):
            variants.add(separator.join(words))
            variants.add(separator.join(word.title() for word in words))
            variants.add(separator.join(word.upper() for word in words))
        if len(words) > 1:
            variants.add(words[0].title() + "".join(word.upper() for word in words[1:]))
    return tuple(sorted(variants))


DOCUMENT_ATTRIBUTE_QUERY_KEYS = _document_attribute_query_keys()
MAX_DOCUMENT_ATTRIBUTE_QUERIES = 64
if len(DOCUMENT_ATTRIBUTE_QUERY_KEYS) > MAX_DOCUMENT_ATTRIBUTE_QUERIES:
    raise RuntimeError("document attribute query vocabulary exceeds bound")


@dataclass(frozen=True)
class WindowCalibration:
    """Private logical origin retained only inside the helper process."""

    logical_x: int
    logical_y: int

    def __post_init__(self) -> None:
        if type(self.logical_x) is not int or type(self.logical_y) is not int:
            raise ValueError("invalid window calibration")


def _resolve_calibration(
    geometry: WindowGeometry,
    calibration: WindowCalibration | None,
) -> WindowCalibration:
    if calibration is not None:
        if (
            _scale(
                calibration.logical_x,
                geometry.scale_numerator,
                geometry.scale_denominator,
                "floor",
            )
            != geometry.x
            or _scale(
                calibration.logical_y,
                geometry.scale_numerator,
                geometry.scale_denominator,
                "floor",
            )
            != geometry.y
        ):
            raise ValueError("window calibration disagrees with geometry")
        return calibration
    x_scaled = geometry.x * geometry.scale_denominator
    y_scaled = geometry.y * geometry.scale_denominator
    if x_scaled % geometry.scale_numerator or y_scaled % geometry.scale_numerator:
        raise ValueError("fractional origin phase unavailable")
    return WindowCalibration(
        logical_x=x_scaled // geometry.scale_numerator,
        logical_y=y_scaled // geometry.scale_numerator,
    )


def _children(node: Any) -> list[Any]:
    count = node.child_count()
    if type(count) is not int or count < 0:
        raise ValueError("child count")
    return [node.child_at(index) for index in range(count)]


def _bounded_children(node: Any, limit: int) -> list[Any] | None:
    count = node.child_count()
    if type(count) is not int or count < 0:
        raise ValueError("child count")
    if count > limit:
        return None
    return [node.child_at(index) for index in range(count)]


def _scale(value: int, numerator: int, denominator: int, rounding: str) -> int:
    decimal = Decimal(value) * Decimal(numerator) / Decimal(denominator)
    mode = ROUND_FLOOR if rounding == "floor" else ROUND_CEILING
    return int(decimal.to_integral_value(rounding=mode))


def native_region(
    rect: tuple[int, int, int, int],
    geometry: WindowGeometry,
    calibration: WindowCalibration | None = None,
) -> CropBox:
    """Convert WINDOW-logical bounds to display-local native-device pixels."""
    if (
        not isinstance(rect, tuple)
        or len(rect) != 4
        or any(type(value) is not int for value in rect)
    ):
        raise ValueError("bounds_unresolvable")
    x, y, width, height = rect
    if width <= 0 or height <= 0:
        raise ValueError("bounds_unresolvable")
    calibration = _resolve_calibration(geometry, calibration)
    left = _scale(calibration.logical_x + x, geometry.scale_numerator, geometry.scale_denominator, "floor")
    top = _scale(calibration.logical_y + y, geometry.scale_numerator, geometry.scale_denominator, "floor")
    right = _scale(
        calibration.logical_x + x + width,
        geometry.scale_numerator,
        geometry.scale_denominator,
        "ceil",
    )
    bottom = _scale(
        calibration.logical_y + y + height,
        geometry.scale_numerator,
        geometry.scale_denominator,
        "ceil",
    )
    crop = geometry.crop_box
    clipped = CropBox(
        left=max(crop.left, left), top=max(crop.top, top),
        right=min(crop.right, right), bottom=min(crop.bottom, bottom),
    )
    if clipped.right <= clipped.left or clipped.bottom <= clipped.top:
        raise ValueError("bounds_unresolvable")
    return clipped


def _root_dimensions_match(
    rect: tuple[int, int, int, int],
    geometry: WindowGeometry,
    calibration: WindowCalibration | None,
) -> bool:
    if not isinstance(rect, tuple) or len(rect) != 4 or any(type(value) is not int for value in rect):
        return False
    _x, _y, width, height = rect
    if width <= 0 or height <= 0:
        return False
    try:
        calibration = _resolve_calibration(geometry, calibration)
    except ValueError:
        return False
    left = _scale(calibration.logical_x, geometry.scale_numerator, geometry.scale_denominator, "floor")
    top = _scale(calibration.logical_y, geometry.scale_numerator, geometry.scale_denominator, "floor")
    right = _scale(calibration.logical_x + width, geometry.scale_numerator, geometry.scale_denominator, "ceil")
    bottom = _scale(calibration.logical_y + height, geometry.scale_numerator, geometry.scale_denominator, "ceil")
    return right - left == geometry.width and bottom - top == geometry.height


def select_focused_window(
    *,
    applications: Sequence[Any],
    binding: FocusBinding,
    geometry: WindowGeometry,
    calibration: WindowCalibration | None = None,
) -> dict[str, object]:
    """Bind PID + AT-SPI state + calibrated dimensions without literals."""
    if len(applications) > MAX_IDENTITY_ROOTS:
        return {"status": "identity_scan_exceeded"}
    matching_apps = [app for app in applications if app.process_id() == binding.pid]
    if len(matching_apps) != 1:
        return {"status": "window_binding_unavailable"}
    app = matching_apps[0]
    count = app.child_count()
    if type(count) is not int or count < 0 or count > MAX_TOP_LEVEL_WINDOWS:
        return {"status": "identity_scan_exceeded"}
    active: list[Any] = []
    calibrated: list[tuple[Any, tuple[int, int, int, int]]] = []
    for index in range(count):
        window = app.child_at(index)
        states = window.state_names()
        if not isinstance(states, set) or not ({"active", "focused"} & states):
            continue
        active.append(window)
        rect = window.window_rect()
        if _root_dimensions_match(rect, geometry, calibration):
            calibrated.append((window, rect))
    if len(calibrated) > 1:
        return {"status": "window_binding_ambiguous"}
    if len(calibrated) == 1:
        return {"status": "ok", "window": calibrated[0][0], "root_rect": calibrated[0][1]}
    if active:
        return {"status": "bounds_unresolvable"}
    return {"status": "window_binding_unavailable"}


def _attribute_refs(attributes: Mapping[str, str]) -> tuple[str, ...]:
    refs: list[str] = []
    for key, value in attributes.items():
        normalized_key = "".join(character for character in key.lower() if character.isalnum())
        if normalized_key not in DOCUMENT_ATTRIBUTE_KEYS:
            continue
        if not isinstance(value, str) or not value or len(value) > MAX_FIELD_CHARS:
            raise ValueError("field_limit_exceeded")
        if value not in refs:
            refs.append(value)
    return tuple(refs)


def _inside_window(
    rect: tuple[int, int, int, int],
    root_rect: tuple[int, int, int, int],
) -> bool:
    x, y, width, height = rect
    _root_x, _root_y, logical_width, logical_height = root_rect
    return width > 0 and height > 0 and x < logical_width and y < logical_height and x + width > 0 and y + height > 0


def collect_window(
    *,
    root: Any,
    geometry: WindowGeometry,
    exclusion_fn: Callable[[tuple[str, ...]], str | None],
    calibration: WindowCalibration | None = None,
    root_rect: tuple[int, int, int, int] | None = None,
) -> dict[str, object]:
    """Two-pass metadata/path preflight followed by bounded literal reads."""
    if root_rect is None:
        try:
            root_rect = root.window_rect()
        except Exception:
            return {"status": "bounds_unresolvable"}
    if not _root_dimensions_match(root_rect, geometry, calibration):
        return {"status": "bounds_unresolvable"}
    queue = deque([root])
    records: list[tuple[Any, CropBox, tuple[str, ...]]] = []
    all_refs: list[str] = []
    excluded: Counter[str] = Counter()
    visited = 0
    document_queries = 0
    while queue:
        if visited >= MAX_NODES:
            return {"status": "field_limit_exceeded"}
        node = queue.popleft()
        visited += 1
        try:
            attributes = node.document_attributes()
            if not isinstance(attributes, Mapping):
                return {"status": "atspi_protocol_invalid"}
            document_queries += getattr(node, "document_query_count", 0)
            if document_queries > MAX_DOCUMENT_ATTRIBUTE_QUERIES:
                return {"status": "field_limit_exceeded"}
            refs = _attribute_refs(attributes)
        except ValueError as exc:
            return {"status": str(exc)}
        except Exception:
            return {"status": "atspi_protocol_invalid"}
        if refs:
            reason = exclusion_fn(refs)
            if reason is not None:
                return {"status": reason}
        all_refs.extend(refs)
        if len(all_refs) > MAX_FIELDS or len(all_refs) > MAX_DOCUMENT_REFS:
            return {"status": "field_limit_exceeded"}
        try:
            children = _bounded_children(node, MAX_NODES - visited - len(queue))
        except Exception:
            return {"status": "atspi_protocol_invalid"}
        if children is None:
            return {"status": "field_limit_exceeded"}
        queue.extend(children)
        try:
            states = node.state_names()
            rect = node.window_rect()
        except (AttributeError, TypeError, ValueError):
            excluded["bounds_unresolved"] += 1
            continue
        if "showing" not in states:
            excluded["not_showing"] += 1
            continue
        if "visible" not in states:
            excluded["not_visible"] += 1
            continue
        if not isinstance(rect, tuple) or len(rect) != 4 or any(type(value) is not int for value in rect):
            excluded["bounds_unresolved"] += 1
            continue
        if not _inside_window(rect, root_rect):
            excluded["out_of_bounds"] += 1
            continue
        try:
            region = native_region(rect, geometry, calibration)
        except ValueError:
            excluded["bounds_unresolved"] += 1
            continue
        records.append((node, region, refs))
    if len(records) * 3 + sum(len(refs) for _node, _region, refs in records) > MAX_FIELDS:
        return {"status": "field_limit_exceeded"}

    facts: list[dict[str, object]] = []
    total_chars = 0
    for node, region, refs in records:
        for kind in ("name", "text", "value"):
            try:
                value = node.literal(kind)
            except ValueError:
                return {"status": "field_limit_exceeded"}
            except Exception:
                return {"status": "atspi_protocol_invalid"}
            if value is None or value == "":
                continue
            if not isinstance(value, str) or len(value) > MAX_FIELD_CHARS:
                return {"status": "field_limit_exceeded"}
            facts.append({"kind": kind, "value": value, "region": region})
            total_chars += len(value)
        for value in refs:
            facts.append({"kind": "document_uri", "value": value, "region": region})
            total_chars += len(value)
        if len(facts) > MAX_FIELDS or total_chars > MAX_TOTAL_CHARS:
            return {"status": "field_limit_exceeded"}
    if not facts:
        return {"status": "no_visible_nodes"}
    if any(fact["kind"] not in FIELD_KINDS for fact in facts):
        return {"status": "atspi_protocol_invalid"}
    return {
        "status": "ok",
        "facts": facts,
        "included_nodes": len(records),
        "excluded_nodes": dict(sorted(excluded.items())),
    }


class _AtspiNode:
    """Small live-only adapter; pure tests use the same bounded interface."""

    def __init__(self, accessible: Any, atspi: Any) -> None:
        self._accessible = accessible
        self._atspi = atspi
        self.document_query_count = 0

    def process_id(self) -> int:
        return int(self._accessible.get_process_id())

    def child_count(self) -> int:
        return int(self._accessible.get_child_count())

    def child_at(self, index: int) -> "_AtspiNode":
        return _AtspiNode(self._accessible.get_child_at_index(index), self._atspi)

    def state_names(self) -> set[str]:
        states = self._accessible.get_state_set()
        names: set[str] = set()
        for name, enum_name in (
            ("active", "ACTIVE"), ("focused", "FOCUSED"),
            ("showing", "SHOWING"), ("visible", "VISIBLE"),
        ):
            if states.contains(getattr(self._atspi.StateType, enum_name)):
                names.add(name)
        return names

    def window_rect(self) -> tuple[int, int, int, int]:
        component = self._accessible.get_component_iface()
        if component is None:
            component = self._accessible.query_component()
        rect = component.get_extents(self._atspi.CoordType.WINDOW)
        return (int(rect.x), int(rect.y), int(rect.width), int(rect.height))

    def document_attributes(self) -> dict[str, str]:
        # Role is deliberately fetched only after exact focus selection.
        self._accessible.get_role()
        document = self._accessible.get_document_iface()
        if document is None:
            return {}
        result: dict[str, str] = {}
        for key in DOCUMENT_ATTRIBUTE_QUERY_KEYS:
            self.document_query_count += 1
            value = document.get_document_attribute_value(key)
            if value:
                result[key] = str(value)
        return result

    def literal(self, kind: str) -> str | None:
        if kind == "name":
            return self._accessible.get_name()
        if kind == "text":
            interface = self._accessible.get_text_iface()
            if interface is None:
                return None
            count = int(interface.get_character_count())
            if count > MAX_FIELD_CHARS:
                raise ValueError("field_limit_exceeded")
            return interface.get_text(0, count)
        if kind == "value":
            interface = self._accessible.get_value_iface()
            if interface is None:
                return None
            return str(interface.get_current_value())
        return None


def bounded_desktop_roots(desktop: Any) -> dict[str, object]:
    try:
        applications = _bounded_children(desktop, MAX_IDENTITY_ROOTS)
    except Exception:
        return {"status": "atspi_protocol_invalid"}
    if applications is None:
        return {"status": "identity_scan_exceeded"}
    return {"status": "ok", "applications": applications}


class _IdentityScanExceeded(RuntimeError):
    pass


def _live_desktop(timeout_ms: int) -> list[_AtspiNode]:
    import gi

    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi

    Atspi.set_timeout(timeout_ms, timeout_ms)
    desktop = _AtspiNode(Atspi.get_desktop(0), Atspi)
    bounded = bounded_desktop_roots(desktop)
    if bounded["status"] == "identity_scan_exceeded":
        raise _IdentityScanExceeded
    if bounded["status"] != "ok":
        raise RuntimeError("AT-SPI desktop protocol")
    return bounded["applications"]


def _live_slice4(timeout_ms: int):
    from core.body.active_window_sensor import sample_active_window
    from scripts.active_window_geometry_probe import probe

    payload = probe(timeout_ms, include_binding=True)
    reading = sample_active_window(
        probe_fn=lambda _timeout: payload,
        privacy_fn=screen_privacy_state,
        timeout=max(0.001, timeout_ms / 1000),
    )
    if reading.state != "available" or reading.geometry is None:
        return reading
    window = payload.get("window")
    displays = payload.get("displays")
    if not isinstance(window, Mapping) or not isinstance(displays, list):
        return reading, None
    matching = [
        display for display in displays
        if isinstance(display, Mapping)
        and display.get("display_id") == reading.geometry.display_id
    ]
    if len(matching) != 1:
        return reading, None
    display = matching[0]
    values = (window.get("x"), window.get("y"), display.get("x"), display.get("y"))
    if any(type(value) is not int for value in values):
        return reading, None
    wx, wy, dx, dy = values
    return reading, WindowCalibration(logical_x=wx - dx, logical_y=wy - dy)


def _snapshot(value: Any) -> tuple[Any, WindowCalibration | None]:
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and (isinstance(value[1], WindowCalibration) or value[1] is None)
    ):
        return value[0], value[1]
    return value, None


def _same_focus(first: Any, second: Any) -> bool:
    return (
        getattr(second, "state", None) == "available"
        and first.binding == second.binding
        and first.geometry == second.geometry
        and first.app_class == second.app_class
    )


def sample_atspi_packet(
    *,
    slice4_fn: Callable[[], Any],
    desktop_fn: Callable[[], Sequence[Any]],
    privacy_fn: Callable[[], str | None],
) -> dict[str, object]:
    """Orchestrate exact-focus selection, two-pass reads, and focus recheck."""
    privacy = privacy_fn()
    if privacy in {"paused", "curtain_drawn"}:
        return {"status": privacy}
    try:
        first, calibration = _snapshot(slice4_fn())
    except Exception:
        return {"status": "slice4_unavailable"}
    if not isinstance(first, ActiveWindowReading) or first.schema_version != SLICE4_SCHEMA_VERSION:
        return {"status": "slice4_unavailable"}
    if first.state != "available":
        reason = getattr(first, "reason", None)
        state = getattr(first, "state", None)
        if isinstance(reason, str) and reason and state in {"refused", "excluded"}:
            return {"status": reason, "state": state}
        return {"status": "slice4_unavailable"}
    if not isinstance(first.binding, FocusBinding) or not isinstance(first.geometry, WindowGeometry):
        return {"status": "window_binding_unavailable"}
    try:
        calibration = _resolve_calibration(first.geometry, calibration)
    except ValueError:
        return {"status": "bounds_unresolvable"}
    try:
        applications = desktop_fn()
    except _IdentityScanExceeded:
        return {"status": "identity_scan_exceeded"}
    except Exception:
        return {"status": "atspi_unreachable"}
    if not isinstance(applications, Sequence):
        return {"status": "atspi_protocol_invalid"}
    try:
        selected = select_focused_window(
            applications=applications,
            binding=first.binding,
            geometry=first.geometry,
            calibration=calibration,
        )
    except Exception:
        return {"status": "atspi_protocol_invalid"}
    if selected.get("status") != "ok":
        return {"status": selected.get("status", "atspi_protocol_invalid")}

    def exclude_refs(refs: tuple[str, ...]) -> str | None:
        from core.vision_contract.screen_exclusion import active_window_preflight_reason

        return active_window_preflight_reason(
            {"class": first.app_class, "title": ""}, document_refs=refs
        )

    collected = collect_window(
        root=selected["window"],
        geometry=first.geometry,
        exclusion_fn=exclude_refs,
        calibration=calibration,
        root_rect=selected["root_rect"],
    )
    if collected.get("status") != "ok":
        return {"status": collected.get("status", "atspi_protocol_invalid")}
    privacy = privacy_fn()
    if privacy in {"paused", "curtain_drawn"}:
        return {"status": privacy}
    try:
        second, second_calibration = _snapshot(slice4_fn())
    except Exception:
        return {"status": "focus_changed"}
    if not isinstance(second, ActiveWindowReading) or second.schema_version != SLICE4_SCHEMA_VERSION:
        return {"status": "focus_changed"}
    try:
        second_calibration = _resolve_calibration(second.geometry, second_calibration)
    except (AttributeError, ValueError):
        return {"status": "focus_changed"}
    if not _same_focus(first, second) or calibration != second_calibration:
        return {"status": "focus_changed"}
    facts = []
    for fact in collected["facts"]:
        region = fact["region"]
        facts.append(
            {
                "kind": fact["kind"],
                "value": fact["value"],
                "region": {
                    "left": region.left,
                    "top": region.top,
                    "right": region.right,
                    "bottom": region.bottom,
                },
            }
        )
    return {
        "status": "ok",
        "slice4_schema_version": first.schema_version,
        "geometry": first.geometry.to_receipt(),
        "facts": facts,
        "included_nodes": collected["included_nodes"],
        "excluded_nodes": collected["excluded_nodes"],
    }


def _terminal_refusal() -> int:
    sys.stdout.write(json.dumps({"status": "atspi_unreachable"}, sort_keys=True))
    return 3


def main(argv: Sequence[str] | None = None) -> int:
    """Run one bounded live sample; interactive terminals remain content-blind."""
    args = list(sys.argv[1:] if argv is None else argv)
    # An interactive invocation must never print application literals. The
    # parent invokes this helper with captured stdout; no production caller is
    # introduced by Slice 5.
    if sys.stdout.isatty():
        return _terminal_refusal()
    if len(args) != 1:
        return _terminal_refusal()
    try:
        timeout_ms = int(args[0])
    except (TypeError, ValueError):
        return _terminal_refusal()
    if timeout_ms <= 0 or timeout_ms > 10_000:
        return _terminal_refusal()
    try:
        packet = sample_atspi_packet(
            slice4_fn=lambda: _live_slice4(timeout_ms),
            desktop_fn=lambda: _live_desktop(timeout_ms),
            privacy_fn=screen_privacy_state,
        )
    except Exception:
        packet = {"status": "atspi_unreachable"}
    sys.stdout.write(json.dumps(packet, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
