"""Single source of truth for Maez's recall-triad launch mode."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

BUNDLE_FLAG = "MAEZ_RECALL_TRIAD_ENABLED"
RAW_RECALL_FLAG_NAMES = (
    "MAEZ_DISPATCHER_ENABLED",
    "MAEZ_FOCUSED_COGNITION_ENABLED",
    "MAEZ_LIVING_RECALL_ENABLED",
)

_TRUTHY = {"1", "true", "yes"}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUTHY


class RecallMode(Enum):
    LEGACY = "legacy"
    TRIAD = "recall_triad"


@dataclass(frozen=True)
class RecallStackConfig:
    mode: RecallMode
    reason: str

    @property
    def triad_on(self) -> bool:
        return self.mode is RecallMode.TRIAD

    @property
    def carrier_available(self) -> bool:
        """Whether the recall carrier is available, not necessarily consulted."""
        return self.triad_on


def resolve_recall_stack(env: Mapping[str, str] | None = None) -> RecallStackConfig:
    """Resolve recall-triad posture from env without caching."""
    env = os.environ if env is None else env
    if _truthy(env.get(BUNDLE_FLAG)):
        return RecallStackConfig(RecallMode.TRIAD, "bundle_enabled")
    raw_set = [name for name in RAW_RECALL_FLAG_NAMES if _truthy(env.get(name))]
    if raw_set:
        return RecallStackConfig(
            RecallMode.LEGACY,
            "legacy_raw_flags_ignored:" + ",".join(raw_set),
        )
    return RecallStackConfig(RecallMode.LEGACY, "off")
