# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Cold recall activation substrate.

Slice 4c.5c defines the narrow decision socket future activation may
use. It intentionally does not activate projection in production.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from core.memory.recall_activation_config import (
    LOGGER_NAME as _CONFIG_LOGGER_NAME,
    projection_activation_enabled,
)
from core.memory.recall_projection import ProjectionCandidate


ACTIVATION_DECISION_SCHEMA_VERSION = 1
LOGGER_NAME = _CONFIG_LOGGER_NAME
ALLOWED_ORDERING_BUMPS = frozenset({-1, 0, 1})
LOG_SHAPES = frozenset({"disabled", "declined", "decided"})


@dataclass(frozen=True)
class ActivationDecision:
    """Narrow projection activation output.

    The recall hint is intentionally the existing
    ``ProjectionCandidate.continuity_key`` vocabulary, not a free-form
    prose marker.
    """

    candidate_id: str
    ordering_bump: int
    recall_continuity_hint: str

    def __post_init__(self) -> None:
        if type(self.candidate_id) is not str:
            raise TypeError("candidate_id must be str")
        if not self.candidate_id:
            raise ValueError("candidate_id must be non-empty")
        if type(self.ordering_bump) is not int:
            raise TypeError("ordering_bump must be int")
        if self.ordering_bump not in ALLOWED_ORDERING_BUMPS:
            raise ValueError("ordering_bump must be one of -1, 0, 1")
        if type(self.recall_continuity_hint) is not str:
            raise TypeError("recall_continuity_hint must be str")
        if not self.recall_continuity_hint:
            raise ValueError("recall_continuity_hint must be non-empty")


def decide_activation(
    candidates: Iterable[ProjectionCandidate],
) -> Optional[ActivationDecision]:
    """Return no activation decision until the later activation slice.

    ``candidates`` is typed now so future activation cannot invent a
    richer candidate shape. Slice 4c.5c keeps the socket cold even if an
    operator sets the env var early.
    """

    _ = candidates
    if not projection_activation_enabled():
        return None
    return None
