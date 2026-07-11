# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Dormant engine-injected OCR evidence lane for Vision Slice 6."""

from __future__ import annotations

import hashlib
import io
import math
import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from PIL import Image

from core.body.active_window_sensor import (
    ActiveWindowReading,
    RefusalReason as ActiveWindowRefusalReason,
)
from core.vision_contract.frozen_frame import FrameCase, FrozenTransform, derive_transforms
from core.vision_contract.geometry import (
    CropBox,
    WindowGeometry,
    crop_box_key,
    geometry_sha256,
)
from core.vision_contract.screen_privacy import screen_privacy_state

SCHEMA_VERSION = "ocr_pixel_transcription.v1"
SOURCE = "ocr"
TRUST = "untrusted_quoted_evidence"
SUPPORT = "ocr_pixel_transcription"
EGRESS_ORIGIN_CLASS = "third_party_private_context"
COORDINATE_SPACE = "display_local_native_device_pixels"
SLICE4_SCHEMA_VERSION = "active_window_geometry.v2"
DEFAULT_CONFIDENCE_FLOOR = 0.90
MAX_ITEMS = 256
MAX_ITEM_CHARS = 512
MAX_TOTAL_CHARS = 16_384
MAX_PNG_BYTES = 16_777_216
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_FRAME_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SLICE4_REASONS = frozenset(ActiveWindowRefusalReason.__args__)
_EXCLUDED_REASONS = frozenset(
    {
        "class_unavailable",
        "sensitive_window",
        "window_schema_invalid",
        "window_unavailable",
    }
)
OCR_REFUSAL_REASONS = frozenset(
    {
        "confidence_floor_invalid",
        "engine_protocol_invalid",
        "engine_unavailable",
        "frame_binding_unavailable",
        "focus_changed",
        "item_limit_exceeded",
        "path_preflight_unavailable",
        "privacy_changed",
        "privacy_unavailable",
        "slice4_unavailable",
        "text_limit_exceeded",
    }
)


@dataclass(frozen=True)
class OwnerBenchAuthorization:
    frame_id: str
    source_sha256: str
    label_sha256: str
    active_native_sha256: str
    mode: Literal["owner_bench"] = "owner_bench"
    _slice3_bound: bool = field(default=False, init=False, repr=False, compare=False)

    @classmethod
    def from_frame_case(
        cls,
        case: FrameCase,
        active_native: FrozenTransform,
    ) -> "OwnerBenchAuthorization":
        """Bind authorization to Slice 3's validated case and exact transform."""
        if (
            not isinstance(case, FrameCase)
            or not case.labels
            or not _is_sha256(case.source_sha256)
            or hashlib.sha256(case.source_bytes).hexdigest() != case.source_sha256
            or not _is_sha256(case.label_sha256)
            or not isinstance(active_native, FrozenTransform)
            or active_native.name != "active_native"
        ):
            raise ValueError("validated Slice 3 frame case required")
        try:
            expected = next(
                transform
                for transform in derive_transforms(case)
                if transform.name == "active_native"
            )
        except Exception:
            raise ValueError("validated Slice 3 frame case required") from None
        if active_native != expected:
            raise ValueError("active-native transform is not bound to frame case")
        authorization = cls(
            frame_id=case.frame_id,
            source_sha256=case.source_sha256,
            label_sha256=case.label_sha256,
            active_native_sha256=active_native.sha256,
        )
        object.__setattr__(authorization, "_slice3_bound", True)
        return authorization


@dataclass(frozen=True)
class RuntimeAuthorization:
    geometry_sha256: str
    path_clearance_sha256: str
    focus_before_sha256: str
    focus_after_sha256: str
    privacy_before_sha256: str
    privacy_after_sha256: str
    mode: Literal["sealed_runtime"] = "sealed_runtime"


Authorization = OwnerBenchAuthorization | RuntimeAuthorization


@dataclass(frozen=True)
class ActiveNativeEnvelope:
    png_bytes: bytes = field(repr=False)
    png_sha256: str
    width: int
    height: int
    geometry: WindowGeometry
    geometry_sha256: str
    authorization: Authorization


@dataclass(frozen=True)
class RawOcrItem:
    text: str = field(repr=False)
    confidence: float
    region: CropBox


@dataclass(frozen=True)
class OcrEvidenceItem:
    text: str = field(repr=False)
    confidence: float
    region: CropBox
    provenance: Literal["transcribed", "abstained"]
    source: str = SOURCE
    trust: str = TRUST
    support: str = SUPPORT
    egress_origin_class: str = EGRESS_ORIGIN_CLASS
    publishable: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.text, str)
            or not self.text
            or len(self.text) > MAX_ITEM_CHARS
            or _normalize_literal(self.text) != self.text
            or not _valid_unit_interval(self.confidence)
            or not isinstance(self.region, CropBox)
            or self.provenance not in {"transcribed", "abstained"}
        ):
            raise ValueError("invalid OCR evidence item")
        if (
            self.source != SOURCE
            or self.trust != TRUST
            or self.support != SUPPORT
            or self.egress_origin_class != EGRESS_ORIGIN_CLASS
            or self.publishable is not False
        ):
            raise ValueError("OCR evidence provenance is closed")
        if self.provenance == "abstained" and self.text != "[UNREADABLE]":
            raise ValueError("OCR abstention must discard guessed text")
        crop_box_key(self.region)

    @property
    def region_key(self) -> str:
        return crop_box_key(self.region)

    def to_receipt(self) -> dict[str, object]:
        return {
            "provenance": self.provenance,
            "confidence": self.confidence,
            "character_count": len(self.text),
            "sha256": hashlib.sha256(self.text.encode("utf-8")).hexdigest(),
            "region_key": self.region_key,
            "region": {
                "left": self.region.left,
                "top": self.region.top,
                "right": self.region.right,
                "bottom": self.region.bottom,
            },
        }


@dataclass(frozen=True)
class OcrReading:
    state: Literal["available", "refused", "excluded"]
    timestamp: datetime
    reason: str = ""
    items: tuple[OcrEvidenceItem, ...] = field(default=(), repr=False)
    geometry: WindowGeometry | None = field(default=None, repr=False)
    auth_mode: Literal["owner_bench", "sealed_runtime"] | None = None
    active_native_sha256: str | None = None
    source_sha256: str | None = None
    label_sha256: str | None = None
    confidence_floor: float | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or self.timestamp.tzinfo is None:
            raise ValueError("invalid OCR reading envelope")
        hashes = (
            self.active_native_sha256,
            self.source_sha256,
            self.label_sha256,
        )
        if self.state == "available":
            if (
                self.reason
                or not isinstance(self.geometry, WindowGeometry)
                or self.auth_mode != "owner_bench"
                or not _valid_unit_interval(self.confidence_floor)
                or not all(_is_sha256(value) for value in hashes)
                or any(not isinstance(item, OcrEvidenceItem) for item in self.items)
                or len(self.items) > MAX_ITEMS
                or sum(len(item.text) for item in self.items) > MAX_TOTAL_CHARS
                or self.geometry.coordinate_space != COORDINATE_SPACE
            ):
                raise ValueError("available OCR reading requires bound evidence")
            crop = self.geometry.crop_box
            if any(
                item.region.left < crop.left
                or item.region.top < crop.top
                or item.region.right > crop.right
                or item.region.bottom > crop.bottom
                for item in self.items
            ):
                raise ValueError("OCR evidence outside active crop")
        elif self.state in {"refused", "excluded"}:
            if (
                not self.reason
                or self.reason not in OCR_REFUSAL_REASONS | _SLICE4_REASONS
                or self.items
                or self.geometry is not None
                or self.auth_mode is not None
                or self.confidence_floor is not None
                or any(value is not None for value in hashes)
            ):
                raise ValueError("OCR refusal must be content-blind")
            if self.state == "excluded" and self.reason not in _EXCLUDED_REASONS:
                raise ValueError("excluded OCR state requires an exclusion reason")
            if self.state == "refused" and self.reason in _EXCLUDED_REASONS:
                raise ValueError("OCR exclusion reason requires excluded state")
        else:
            raise ValueError("invalid OCR state")

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
        confidence_values = tuple(item.confidence for item in self.items)
        if confidence_values:
            distribution: dict[str, int | float | None] = {
                "count": len(confidence_values),
                "minimum": min(confidence_values),
                "maximum": max(confidence_values),
                "mean": round(sum(confidence_values) / len(confidence_values), 6),
            }
        else:
            distribution = {
                "count": 0,
                "minimum": None,
                "maximum": None,
                "mean": None,
            }
        base.update(
            {
                "support": SUPPORT,
                "auth_mode": self.auth_mode,
                "confidence_floor": self.confidence_floor,
                "slice4_schema_version": SLICE4_SCHEMA_VERSION,
                "geometry_sha256": geometry_sha256(self.geometry),
                "active_native_sha256": self.active_native_sha256,
                "source_sha256": self.source_sha256,
                "label_sha256": self.label_sha256,
                "item_count": len(self.items),
                "transcribed_count": sum(item.provenance == "transcribed" for item in self.items),
                "abstained_count": sum(item.provenance == "abstained" for item in self.items),
                "confidence_distribution": distribution,
                "items": [item.to_receipt() for item in self.items],
            }
        )
        return base


def _timestamp(now: datetime | None) -> datetime:
    value = now or datetime.now(timezone.utc)
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _refusal(
    reason: str,
    timestamp: datetime,
    *,
    excluded: bool = False,
) -> OcrReading:
    return OcrReading(
        state="excluded" if excluded else "refused",
        timestamp=timestamp,
        reason=reason,
    )


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _validate_envelope(
    envelope: object,
    upstream_geometry: WindowGeometry,
) -> Literal["owner_bench", "sealed_runtime"] | None:
    if not isinstance(envelope, ActiveNativeEnvelope):
        return None
    if (
        not isinstance(envelope.png_bytes, bytes)
        or not envelope.png_bytes
        or len(envelope.png_bytes) > MAX_PNG_BYTES
        or type(envelope.width) is not int
        or type(envelope.height) is not int
        or envelope.width <= 0
        or envelope.height <= 0
        or not isinstance(envelope.geometry, WindowGeometry)
        or envelope.geometry != upstream_geometry
        or envelope.geometry.coordinate_space != COORDINATE_SPACE
        or envelope.width != envelope.geometry.width
        or envelope.height != envelope.geometry.height
    ):
        return None
    png_digest = hashlib.sha256(envelope.png_bytes).hexdigest()
    canonical_geometry_digest = geometry_sha256(envelope.geometry)
    if envelope.png_sha256 != png_digest or envelope.geometry_sha256 != canonical_geometry_digest:
        return None
    try:
        with Image.open(io.BytesIO(envelope.png_bytes)) as image:
            if image.format != "PNG":
                return None
            image.load()
            if image.size != (envelope.width, envelope.height):
                return None
    except Exception:
        return None
    authorization = envelope.authorization
    if isinstance(authorization, OwnerBenchAuthorization):
        if (
            authorization.mode != "owner_bench"
            or authorization._slice3_bound is not True
            or not isinstance(authorization.frame_id, str)
            or _SAFE_FRAME_ID_RE.fullmatch(authorization.frame_id) is None
            or not all(
                _is_sha256(value)
                for value in (
                    authorization.source_sha256,
                    authorization.label_sha256,
                    authorization.active_native_sha256,
                )
            )
            or authorization.active_native_sha256 != png_digest
        ):
            return None
        return "owner_bench"
    if isinstance(authorization, RuntimeAuthorization):
        if (
            authorization.mode != "sealed_runtime"
            or authorization.geometry_sha256 != canonical_geometry_digest
            or not all(
                _is_sha256(value)
                for value in (
                    authorization.path_clearance_sha256,
                    authorization.focus_before_sha256,
                    authorization.focus_after_sha256,
                    authorization.privacy_before_sha256,
                    authorization.privacy_after_sha256,
                )
            )
        ):
            return None
        return "sealed_runtime"
    return None


def _valid_unit_interval(value: object) -> bool:
    return (
        type(value) in {int, float} and math.isfinite(float(value)) and 0.0 <= float(value) <= 1.0
    )


def _normalize_literal(value: str) -> str:
    clean = "".join(
        character
        for character in value
        if not (
            unicodedata.category(character) in {"Cc", "Cf"} and character not in {"\t", "\n", "\r"}
        )
    )
    return " ".join(clean.split())


def _valid_local_region(region: object, *, width: int, height: int) -> bool:
    return (
        isinstance(region, CropBox)
        and all(
            type(value) is int for value in (region.left, region.top, region.right, region.bottom)
        )
        and region.left >= 0
        and region.top >= 0
        and region.right > region.left
        and region.bottom > region.top
        and region.right <= width
        and region.bottom <= height
    )


def _privacy_reason(value: object) -> str | None:
    if value is None:
        return None
    if value in {"paused", "curtain_drawn"}:
        return str(value)
    return "privacy_unavailable"


def sample_ocr(
    *,
    upstream: object,
    envelope: ActiveNativeEnvelope | None,
    engine: Callable[[bytes], Sequence[RawOcrItem]] | None,
    now: datetime | None = None,
    privacy_fn: Callable[[], str | None] = screen_privacy_state,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
) -> OcrReading:
    """Validate one dormant OCR sample without any live acquisition authority."""
    timestamp = _timestamp(now)
    try:
        privacy = privacy_fn()
    except Exception:
        return _refusal("privacy_unavailable", timestamp)
    privacy_reason = _privacy_reason(privacy)
    if privacy_reason is not None:
        return _refusal(privacy_reason, timestamp)
    if not isinstance(upstream, ActiveWindowReading):
        return _refusal("slice4_unavailable", timestamp)
    if upstream.state != "available":
        if upstream.reason not in _SLICE4_REASONS:
            return _refusal("slice4_unavailable", timestamp)
        if (
            upstream.state == "excluded"
            and upstream.reason not in _EXCLUDED_REASONS
            or upstream.state == "refused"
            and upstream.reason in _EXCLUDED_REASONS
        ):
            return _refusal("slice4_unavailable", timestamp)
        return _refusal(
            upstream.reason,
            timestamp,
            excluded=upstream.state == "excluded",
        )
    if not isinstance(upstream.geometry, WindowGeometry):
        return _refusal("slice4_unavailable", timestamp)
    auth_mode = _validate_envelope(envelope, upstream.geometry)
    if auth_mode is None:
        return _refusal("frame_binding_unavailable", timestamp)
    if auth_mode == "sealed_runtime":
        assert isinstance(envelope, ActiveNativeEnvelope)
        authorization = envelope.authorization
        assert isinstance(authorization, RuntimeAuthorization)
        if authorization.focus_before_sha256 != authorization.focus_after_sha256:
            return _refusal("focus_changed", timestamp)
        if authorization.privacy_before_sha256 != authorization.privacy_after_sha256:
            return _refusal("privacy_changed", timestamp)
        return _refusal("path_preflight_unavailable", timestamp)
    if not _valid_unit_interval(confidence_floor):
        return _refusal("confidence_floor_invalid", timestamp)
    if not callable(engine):
        return _refusal("engine_unavailable", timestamp)
    assert isinstance(envelope, ActiveNativeEnvelope)
    try:
        raw_items = engine(envelope.png_bytes)
    except Exception:
        return _refusal("engine_unavailable", timestamp)
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes, bytearray)):
        return _refusal("engine_protocol_invalid", timestamp)
    try:
        declared_count = len(raw_items)
    except Exception:
        return _refusal("engine_protocol_invalid", timestamp)
    if declared_count > MAX_ITEMS:
        return _refusal("item_limit_exceeded", timestamp)

    total_chars = 0
    evidence: list[OcrEvidenceItem] = []
    observed_count = 0
    try:
        for item in raw_items:
            observed_count += 1
            if observed_count > MAX_ITEMS:
                return _refusal("item_limit_exceeded", timestamp)
            if not isinstance(item, RawOcrItem) or not isinstance(item.text, str):
                return _refusal("engine_protocol_invalid", timestamp)
            raw_length = len(item.text)
            total_chars += raw_length
            if raw_length > MAX_ITEM_CHARS or total_chars > MAX_TOTAL_CHARS:
                return _refusal("text_limit_exceeded", timestamp)
            if not _valid_unit_interval(item.confidence) or not _valid_local_region(
                item.region,
                width=envelope.width,
                height=envelope.height,
            ):
                return _refusal("engine_protocol_invalid", timestamp)
            normalized = _normalize_literal(item.text)
            if not normalized:
                return _refusal("engine_protocol_invalid", timestamp)
            confidence = float(item.confidence)
            provenance: Literal["transcribed", "abstained"]
            if confidence < float(confidence_floor):
                normalized = "[UNREADABLE]"
                provenance = "abstained"
            else:
                provenance = "transcribed"
            local = item.region
            evidence.append(
                OcrEvidenceItem(
                    text=normalized,
                    confidence=confidence,
                    region=CropBox(
                        left=envelope.geometry.x + local.left,
                        top=envelope.geometry.y + local.top,
                        right=envelope.geometry.x + local.right,
                        bottom=envelope.geometry.y + local.bottom,
                    ),
                    provenance=provenance,
                )
            )
    except Exception:
        return _refusal("engine_protocol_invalid", timestamp)
    if observed_count != declared_count:
        return _refusal("engine_protocol_invalid", timestamp)
    try:
        privacy = privacy_fn()
    except Exception:
        return _refusal("privacy_unavailable", timestamp)
    privacy_reason = _privacy_reason(privacy)
    if privacy_reason is not None:
        return _refusal(privacy_reason, timestamp)
    authorization = envelope.authorization
    assert isinstance(authorization, OwnerBenchAuthorization)
    return OcrReading(
        state="available",
        timestamp=timestamp,
        items=tuple(evidence),
        geometry=envelope.geometry,
        auth_mode=auth_mode,
        active_native_sha256=envelope.png_sha256,
        source_sha256=authorization.source_sha256,
        label_sha256=authorization.label_sha256,
        confidence_floor=float(confidence_floor),
    )
