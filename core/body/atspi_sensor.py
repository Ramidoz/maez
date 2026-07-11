# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Dormant bounded AT-SPI evidence contract for Vision Slice 5.

The live adapter is a fixed system-Python helper because PyGObject is not in
Maez's venv. AT-SPI application literals are third-party, untrusted quoted
evidence. This module has no production caller, prompt, memory, or cognition
path and performs no filesystem writes.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from core.vision_contract.geometry import CropBox, WindowGeometry
from core.vision_contract.screen_privacy import screen_privacy_state

SCHEMA_VERSION = "atspi_accessibility.v1"
AT_SPI_PROJECTION_SCHEMA_VERSION = "atspi_projection.v1"
FIELD_KINDS = frozenset({"name", "text", "value", "document_uri"})
SOURCE = "atspi"
TRUST = "untrusted_quoted_evidence"
SUPPORT = "atspi_state_bounds_only"
EGRESS_ORIGIN_CLASS = "third_party_private_context"
COORDINATE_SPACE = "display_local_native_device_pixels"
SLICE4_SCHEMA_VERSION = "active_window_geometry.v2"

MAX_IDENTITY_ROOTS = 64
MAX_TOP_LEVEL_WINDOWS = 32
MAX_NODES = 256
MAX_FIELDS = 512
MAX_FIELD_CHARS = 512
MAX_TOTAL_CHARS = 16_384
MAX_PACKET_BYTES = 262_144
MAX_TIMEOUT_SECONDS = 10.0

_SYSTEM_PYTHON = "/usr/bin/python3"
_PROBE_HELPER = Path(__file__).resolve().parents[2] / "scripts" / "atspi_window_probe.py"
_OWN_REASONS = frozenset(
    {
        "slice4_unavailable", "atspi_unreachable", "atspi_protocol_invalid",
        "identity_scan_exceeded", "window_binding_unavailable",
        "window_binding_ambiguous", "bounds_unresolvable", "no_visible_nodes",
        "excluded_path", "field_limit_exceeded", "focus_changed",
    }
)
_SLICE4_REASONS = frozenset(
    {
        "paused", "curtain_drawn", "compositor_unreachable",
        "compositor_protocol_invalid", "unsupported_session",
        "display_config_changed", "window_unavailable", "class_unavailable",
        "window_schema_invalid", "sensitive_window", "geometry_unavailable",
        "degenerate_bounds", "display_unavailable", "cross_display_bounds",
        "off_screen_bounds", "scale_unavailable",
    }
)
REFUSAL_REASONS = _OWN_REASONS | _SLICE4_REASONS
EXCLUSION_COUNT_REASONS = frozenset(
    {"not_showing", "not_visible", "out_of_bounds", "bounds_unresolved"}
)
_EXCLUDED_REASONS = frozenset(
    {"excluded_path", "sensitive_window", "class_unavailable", "window_unavailable", "window_schema_invalid"}
)
OWN_REFUSAL_REASONS = _OWN_REASONS
SLICE4_REFUSAL_REASONS = _SLICE4_REASONS
EXCLUDED_REASONS = _EXCLUDED_REASONS


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_literal(value: str) -> str:
    clean = "".join(
        character
        for character in value
        if not (
            unicodedata.category(character) in {"Cc", "Cf"}
            and character not in {"\t", "\n", "\r"}
        )
    )
    return " ".join(clean.split())


def _valid_region(region: CropBox) -> bool:
    return (
        isinstance(region, CropBox)
        and all(type(value) is int for value in (region.left, region.top, region.right, region.bottom))
        and region.left >= 0
        and region.top >= 0
        and region.right > region.left
        and region.bottom > region.top
    )


@dataclass(frozen=True)
class AccessibilityFact:
    kind: str
    value: str = field(repr=False)
    region: CropBox
    source: str = SOURCE
    trust: str = TRUST
    support: str = SUPPORT
    egress_origin_class: str = EGRESS_ORIGIN_CLASS
    publishable: bool = False

    def __post_init__(self) -> None:
        if self.kind not in FIELD_KINDS:
            raise ValueError("unsupported accessibility field kind")
        if not isinstance(self.value, str):
            raise ValueError("accessibility literal must be text")
        normalized = _normalize_literal(self.value)
        if not normalized or len(normalized) > MAX_FIELD_CHARS:
            raise ValueError("accessibility literal outside bounds")
        if not _valid_region(self.region):
            raise ValueError("invalid accessibility region")
        if (
            self.source != SOURCE
            or self.trust != TRUST
            or self.support != SUPPORT
            or self.egress_origin_class != EGRESS_ORIGIN_CLASS
            or self.publishable is not False
        ):
            raise ValueError("accessibility provenance is closed")
        object.__setattr__(self, "value", normalized)

    @property
    def region_key(self) -> str:
        raw = f"{self.kind}:{self.region.left}:{self.region.top}:{self.region.right}:{self.region.bottom}"
        return _sha256(raw.encode("utf-8"))[:24]

    def to_receipt(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "character_count": len(self.value),
            "sha256": _sha256(self.value.encode("utf-8")),
            "region_key": self.region_key,
            "region": {
                "left": self.region.left,
                "top": self.region.top,
                "right": self.region.right,
                "bottom": self.region.bottom,
            },
        }


@dataclass(frozen=True)
class AccessibilityReading:
    state: Literal["available", "refused", "excluded"]
    timestamp: datetime
    reason: str = ""
    facts: tuple[AccessibilityFact, ...] = field(default=(), repr=False)
    geometry: WindowGeometry | None = field(default=None, repr=False)
    included_nodes: int = 0
    excluded_nodes: tuple[tuple[str, int], ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.timestamp.tzinfo is None:
            raise ValueError("invalid accessibility reading envelope")
        if self.state == "available":
            if (
                self.reason
                or not self.facts
                or not isinstance(self.geometry, WindowGeometry)
                or any(not isinstance(fact, AccessibilityFact) for fact in self.facts)
            ):
                raise ValueError("available accessibility reading requires evidence")
            if len(self.facts) > MAX_FIELDS or sum(len(fact.value) for fact in self.facts) > MAX_TOTAL_CHARS:
                raise ValueError("accessibility evidence outside bounds")
            if type(self.included_nodes) is not int or self.included_nodes <= 0:
                raise ValueError("included-node count required")
            if self.included_nodes > MAX_NODES or any(
                not isinstance(item, tuple)
                or len(item) != 2
                or item[0] not in EXCLUSION_COUNT_REASONS
                or type(item[1]) is not int
                or item[1] <= 0
                for item in self.excluded_nodes
            ):
                raise ValueError("excluded-node counts outside vocabulary")
            if self.included_nodes + sum(count for _reason, count in self.excluded_nodes) > MAX_NODES:
                raise ValueError("node counts exceed traversal bound")
            crop = self.geometry.crop_box
            if self.geometry.coordinate_space != COORDINATE_SPACE or any(
                fact.region.left < crop.left
                or fact.region.top < crop.top
                or fact.region.right > crop.right
                or fact.region.bottom > crop.bottom
                for fact in self.facts
            ):
                raise ValueError("fact region outside active-window geometry")
        elif self.state in {"refused", "excluded"}:
            if (
                self.reason not in REFUSAL_REASONS
                or self.facts
                or self.geometry is not None
                or self.included_nodes
                or self.excluded_nodes
            ):
                raise ValueError("refusal must be typed and content-blind")
            if self.state == "excluded" and self.reason not in _EXCLUDED_REASONS:
                raise ValueError("excluded state requires an exclusion reason")
            if self.state == "refused" and self.reason in _EXCLUDED_REASONS:
                raise ValueError("exclusion reason requires excluded state")
        else:
            raise ValueError("invalid accessibility state")

    @classmethod
    def available(
        cls,
        *,
        facts: tuple[AccessibilityFact, ...],
        geometry: WindowGeometry,
        included_nodes: int,
        excluded_nodes: Mapping[str, int],
        now: datetime,
    ) -> "AccessibilityReading":
        return cls(
            state="available",
            timestamp=now,
            facts=facts,
            geometry=geometry,
            included_nodes=included_nodes,
            excluded_nodes=tuple(sorted(excluded_nodes.items())),
        )

    @classmethod
    def refused(
        cls,
        reason: str,
        now: datetime,
        *,
        excluded: bool = False,
    ) -> "AccessibilityReading":
        return cls(state="excluded" if excluded else "refused", timestamp=now, reason=reason)

    def to_receipt(self) -> dict[str, object]:
        base: dict[str, object] = {
            "schema_version": self.schema_version,
            "state": self.state,
            "timestamp": self.timestamp.astimezone(timezone.utc).isoformat(),
            "refusal_reason": self.reason or None,
        }
        if self.state != "available":
            return base
        assert self.geometry is not None
        geometry_bytes = json.dumps(
            self.geometry.to_receipt(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        base.update(
            {
                "support": SUPPORT,
                "occlusion_checked": False,
                "slice4_schema_version": SLICE4_SCHEMA_VERSION,
                "geometry_sha256": _sha256(geometry_bytes),
                "included_nodes": self.included_nodes,
                "excluded_nodes": dict(self.excluded_nodes),
                "facts": [fact.to_receipt() for fact in self.facts],
            }
        )
        return base


def accessibility_projection_sha256(reading: AccessibilityReading) -> str:
    """Return the canonical content projection for one available reading."""
    if not isinstance(reading, AccessibilityReading) or reading.state != "available":
        raise ValueError("available accessibility reading required")
    facts = sorted(
        (
            fact.kind,
            len(fact.value),
            _sha256(fact.value.encode("utf-8")),
            fact.region.left,
            fact.region.top,
            fact.region.right,
            fact.region.bottom,
        )
        for fact in reading.facts
    )
    payload = {
        "projection_schema_version": AT_SPI_PROJECTION_SCHEMA_VERSION,
        "sensor_schema_version": reading.schema_version,
        "support": SUPPORT,
        "occlusion_checked": False,
        "included_nodes": reading.included_nodes,
        "excluded_nodes": sorted(reading.excluded_nodes),
        "facts": facts,
    }
    return _sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _timestamp(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def read_atspi_packet(timeout: float = 2.0) -> Mapping[str, object]:
    """Invoke the fixed helper and decode one bounded content packet."""
    if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout <= 0 or timeout > MAX_TIMEOUT_SECONDS:
        return {"status": "atspi_unreachable"}
    try:
        completed = subprocess.run(
            [
                _SYSTEM_PYTHON,
                "-B",
                os.fspath(_PROBE_HELPER),
                str(max(1, int(timeout * 1000))),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return {"status": "atspi_unreachable"}
    raw = (completed.stdout or "").strip()
    if completed.returncode != 0 or not raw or len(raw.encode("utf-8")) > MAX_PACKET_BYTES:
        return {"status": "atspi_protocol_invalid"}
    try:
        packet = json.loads(raw)
    except (TypeError, ValueError):
        return {"status": "atspi_protocol_invalid"}
    return packet if isinstance(packet, Mapping) else {"status": "atspi_protocol_invalid"}


def _exact_int(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key)
    if type(value) is not int:
        raise ValueError("integer field")
    return value


def _geometry_from_receipt(value: object) -> WindowGeometry:
    if not isinstance(value, Mapping):
        raise ValueError("geometry")
    scale = value.get("scale_factor")
    if not isinstance(scale, Mapping):
        raise ValueError("scale")
    display_id = value.get("display_id")
    coordinate_space = value.get("coordinate_space")
    if not isinstance(display_id, str) or not isinstance(coordinate_space, str):
        raise ValueError("geometry strings")
    return WindowGeometry(
        x=_exact_int(value, "x"),
        y=_exact_int(value, "y"),
        width=_exact_int(value, "width"),
        height=_exact_int(value, "height"),
        display_id=display_id,
        display_width=_exact_int(value, "display_width"),
        display_height=_exact_int(value, "display_height"),
        scale_numerator=_exact_int(scale, "numerator"),
        scale_denominator=_exact_int(scale, "denominator"),
        display_config_serial=_exact_int(value, "display_config_serial"),
        coordinate_space=coordinate_space,
    )


def _fact_from_packet(value: object) -> AccessibilityFact:
    if not isinstance(value, Mapping):
        raise ValueError("fact")
    kind = value.get("kind")
    literal = value.get("value")
    region = value.get("region")
    if not isinstance(kind, str) or not isinstance(literal, str) or not isinstance(region, Mapping):
        raise ValueError("fact shape")
    return AccessibilityFact(
        kind=kind,
        value=literal,
        region=CropBox(
            left=_exact_int(region, "left"),
            top=_exact_int(region, "top"),
            right=_exact_int(region, "right"),
            bottom=_exact_int(region, "bottom"),
        ),
    )


def sample_accessibility(
    *,
    now: datetime | None = None,
    packet_fn=read_atspi_packet,
    privacy_fn=screen_privacy_state,
    timeout: float = 2.0,
) -> AccessibilityReading:
    """Validate one helper packet into a frozen, dormant accessibility reading."""
    timestamp = _timestamp(now)
    privacy = privacy_fn()
    if privacy in {"paused", "curtain_drawn"}:
        return AccessibilityReading.refused(privacy, timestamp)
    try:
        packet = packet_fn(timeout)
    except Exception:
        return AccessibilityReading.refused("atspi_unreachable", timestamp)
    privacy = privacy_fn()
    if privacy in {"paused", "curtain_drawn"}:
        return AccessibilityReading.refused(privacy, timestamp)
    if not isinstance(packet, Mapping):
        return AccessibilityReading.refused("atspi_protocol_invalid", timestamp)
    status = packet.get("status")
    if status != "ok":
        state = packet.get("state")
        valid = isinstance(status, str) and status in REFUSAL_REASONS
        if status in _OWN_REASONS:
            valid = valid and state is None
            excluded = status == "excluded_path"
        elif status in _SLICE4_REASONS:
            expected_state = "excluded" if status in _EXCLUDED_REASONS else "refused"
            valid = valid and state == expected_state
            excluded = expected_state == "excluded"
        else:
            valid = False
            excluded = False
        if not valid:
            status = "atspi_protocol_invalid"
            excluded = False
        try:
            return AccessibilityReading.refused(status, timestamp, excluded=excluded)
        except ValueError:
            return AccessibilityReading.refused("atspi_protocol_invalid", timestamp)
    try:
        if packet.get("slice4_schema_version") != SLICE4_SCHEMA_VERSION:
            raise ValueError("slice4 schema")
        raw_facts = packet.get("facts")
        if not isinstance(raw_facts, list) or not raw_facts or len(raw_facts) > MAX_FIELDS:
            raise ValueError("facts")
        facts = tuple(_fact_from_packet(item) for item in raw_facts)
        geometry = _geometry_from_receipt(packet.get("geometry"))
        included_nodes = packet.get("included_nodes")
        excluded_nodes = packet.get("excluded_nodes")
        if type(included_nodes) is not int or included_nodes <= 0 or included_nodes > MAX_NODES:
            raise ValueError("included nodes")
        if not isinstance(excluded_nodes, Mapping) or any(
            not isinstance(key, str) or type(count) is not int or count < 0
            for key, count in excluded_nodes.items()
        ):
            raise ValueError("excluded nodes")
        reading = AccessibilityReading.available(
            facts=facts,
            geometry=geometry,
            included_nodes=included_nodes,
            excluded_nodes=excluded_nodes,
            now=timestamp,
        )
    except (TypeError, ValueError):
        return AccessibilityReading.refused("atspi_protocol_invalid", timestamp)
    privacy = privacy_fn()
    if privacy in {"paused", "curtain_drawn"}:
        return AccessibilityReading.refused(privacy, timestamp)
    return reading
