# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Neutral frozen geometry values shared by vision evaluation and sensors.

`CropBox(left, top, right, bottom)` and its right/bottom-exclusive edge
semantics are the stable Slice 3 -> Slice 6 interface for schema v1. A future
coordinate-space change requires a new schema rather than reinterpretation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CropBox:
    """Right/bottom-exclusive rectangle in the declared source pixel space."""

    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class WindowGeometry:
    """Validated display-local native-pixel active-window geometry."""

    x: int
    y: int
    width: int
    height: int
    display_id: str
    display_width: int
    display_height: int
    scale_numerator: int
    scale_denominator: int
    display_config_serial: int
    coordinate_space: str

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("invalid window geometry")
        if self.x + self.width > self.display_width:
            raise ValueError("window exceeds display width")
        if self.y + self.height > self.display_height:
            raise ValueError("window exceeds display height")
        if not self.display_id:
            raise ValueError("display_id is required")
        if self.scale_numerator <= 0 or self.scale_denominator <= 0:
            raise ValueError("scale must be positive")
        if self.display_config_serial < 0:
            raise ValueError("display_config_serial must be non-negative")

    @property
    def crop_box(self) -> CropBox:
        return CropBox(
            left=self.x,
            top=self.y,
            right=self.x + self.width,
            bottom=self.y + self.height,
        )

    def to_receipt(self) -> dict[str, object]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "display_id": self.display_id,
            "display_width": self.display_width,
            "display_height": self.display_height,
            "scale_factor": {
                "numerator": self.scale_numerator,
                "denominator": self.scale_denominator,
            },
            "display_config_serial": self.display_config_serial,
            "coordinate_space": self.coordinate_space,
        }
