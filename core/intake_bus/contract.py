# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""The Intake Bus contract — the shared types a limb and the doorway exchange.

The bus owns the covenant moment (tier, taint, posture, idempotency); the limb
brings a sealed, labeled package. These types carry no behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable

from memory.memory_manager import ProvenanceSource


class PromotionPosture(Enum):
    ADMIT_TO_BODY = "admit_to_body"
    STAGE_ONLY = "stage_only"
    # future (NOT in v0): QUARANTINE_PROPOSAL — lands as a contestable reflection proposal


@dataclass(frozen=True)
class IntakeFact:
    """A staged, minimized fact a limb hands the doorway."""

    source_kind: str
    source_ref: str
    content: str
    provenance_source: ProvenanceSource
    egress_origin_class: str
    promotion_posture: PromotionPosture
    fetch_batch_id: str
    metadata: Mapping[str, str] = field(default_factory=dict)


@runtime_checkable
class StoreAdapter(Protocol):
    """The two hooks a limb implements so the bus drives idempotency."""

    def oldest_pending(self) -> "IntakeFact | None": ...

    def mark_admitted(self, source_ref: str, *, body_memory_id: str) -> None: ...


@dataclass(frozen=True)
class IntakeOutcome:
    """Content-free BY CONSTRUCTION — status / source_ref / reason code only."""

    status: str
    source_ref: str | None
    reason: str | None = None
