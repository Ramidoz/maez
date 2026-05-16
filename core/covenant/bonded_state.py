# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Decision 8 bonded-state vocabulary.

This module encodes the long-lived state names required by
Decision 8 / ADR 0008. It does not implement Paradise admission,
transition dialogs, mourning drift, or lineage capsules; it only makes the
schema vocabulary importable and testable so future stores do not silently
omit ``suspended_pending_paradise``.
"""

from __future__ import annotations

from typing import Literal, get_args

BondedState = Literal[
    "active",
    "dormant",
    "mourning",
    "tribe_admitted",
    "suspended_pending_paradise",
]

BONDED_STATES: frozenset[str] = frozenset(get_args(BondedState))
SUSPENDED_PENDING_PARADISE: BondedState = "suspended_pending_paradise"


def validate_bonded_state(value: object) -> BondedState:
    """Return ``value`` as a canonical bonded state or raise ``ValueError``."""

    if not isinstance(value, str):
        raise ValueError(f"unknown bonded_state {value!r}")
    state = value.strip()
    if state not in BONDED_STATES:
        raise ValueError(f"unknown bonded_state {value!r}")
    return state  # type: ignore[return-value]


__all__ = [
    "BONDED_STATES",
    "SUSPENDED_PENDING_PARADISE",
    "BondedState",
    "validate_bonded_state",
]
