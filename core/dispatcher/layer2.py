"""Layer 2 repair/follow-up FSM for ADR 0047.

Layer 2 inherits a prior CompositionSpec only for repair-shaped turns. It does
not open substrate readers, render prompt text, fetch external data, or wire
into brain-loop routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
import time
from typing import Any

from core.dispatcher.spec import CompositionSpec


DEFAULT_REPAIR_TTL_S = 300.0


class RepairRefusalReason(StrEnum):
    NO_PRIOR_SPEC = "NO_PRIOR_SPEC"
    CROSS_SURFACE_REFUSED = "CROSS_SURFACE_REFUSED"
    PRIOR_SPEC_EXPIRED = "PRIOR_SPEC_EXPIRED"
    MODIFIED_SPEC_INVALID = "MODIFIED_SPEC_INVALID"


@dataclass(frozen=True)
class RepairRefusal:
    reason: RepairRefusalReason
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"reason": self.reason.value, "detail": self.detail}


@dataclass
class _StoredSpec:
    bond_id: str
    surface: str
    conversation_id: str
    spec_payload: dict[str, Any]
    recorded_at: float
    ttl_expires_at: float


Layer2Result = CompositionSpec | RepairRefusal


class Layer2RepairFSM:
    def __init__(
        self,
        *,
        ttl_s: float = DEFAULT_REPAIR_TTL_S,
        clock: Any | None = None,
    ) -> None:
        self.ttl_s = ttl_s
        self.clock = clock or time.monotonic
        self._last_specs: dict[tuple[str, str, str], _StoredSpec] = {}

    def record_completed_spec(
        self,
        *,
        bond_id: str,
        surface: str,
        conversation_id: str,
        spec: CompositionSpec,
    ) -> None:
        now = float(self.clock())
        self._last_specs[(bond_id, surface, conversation_id)] = _StoredSpec(
            bond_id=bond_id,
            surface=surface,
            conversation_id=conversation_id,
            spec_payload=spec.to_dict(),
            recorded_at=now,
            ttl_expires_at=now + self.ttl_s,
        )
        self._prune_expired(now)

    def apply_repair(
        self,
        *,
        bond_id: str,
        surface: str,
        conversation_id: str,
        current_utterance: str,
        current_spec: CompositionSpec,
    ) -> Layer2Result:
        if not is_repair_shape(current_utterance):
            return current_spec

        now = float(self.clock())
        key = (bond_id, surface, conversation_id)
        stored = self._last_specs.get(key)
        if stored is None:
            if self._has_prior_for_other_surface(bond_id, conversation_id):
                return RepairRefusal(
                    RepairRefusalReason.CROSS_SURFACE_REFUSED,
                    "prior spec exists only on a different surface",
                )
            return RepairRefusal(
                RepairRefusalReason.NO_PRIOR_SPEC,
                "no prior spec for bond/surface/conversation",
            )

        if now > stored.ttl_expires_at:
            self._last_specs.pop(key, None)
            return RepairRefusal(
                RepairRefusalReason.PRIOR_SPEC_EXPIRED,
                "prior spec TTL expired",
            )

        try:
            return CompositionSpec.from_dict(stored.spec_payload)
        except Exception as exc:
            return RepairRefusal(
                RepairRefusalReason.MODIFIED_SPEC_INVALID,
                type(exc).__name__,
            )

    def _has_prior_for_other_surface(self, bond_id: str, conversation_id: str) -> bool:
        return any(
            stored.bond_id == bond_id and stored.conversation_id == conversation_id
            for stored in self._last_specs.values()
        )

    def _prune_expired(self, now: float) -> None:
        for key, stored in list(self._last_specs.items()):
            if now > stored.ttl_expires_at:
                self._last_specs.pop(key, None)


_REPAIR_PHRASES = {
    "you sure",
    "are you sure",
    "check again",
    "look again",
    "try again",
    "really",
    "are you certain",
    "you certain",
    "no that's not it",
    "no thats not it",
    "go on",
}


def is_repair_shape(query: str) -> bool:
    normalized = re.sub(r"[?!.,]+", "", (query or "").lower()).strip()
    if normalized in _REPAIR_PHRASES:
        return True
    return bool(re.fullmatch(r"(can you )?(check|look|try) again", normalized))
