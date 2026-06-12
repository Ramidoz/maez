"""Strict flag for Surface Parity Restoration v0."""

from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def surface_parity_enabled() -> bool:
    """Return true only for explicit truthy values.

    This deliberately rejects the house-wide ``bool(os.environ.get(...))``
    footgun where ``"0"`` reads as enabled.
    """

    return (os.environ.get("MAEZ_SURFACE_PARITY_ENABLED", "") or "").strip().lower() in _TRUTHY


def s7_ceremony_bridge_enabled() -> bool:
    """Return true only for explicit truthy values.

    This bridge initiates the ceremony for soul-affecting writes, so ``"0"``
    must mean off rather than truthy-by-presence.
    """

    return (
        os.environ.get("MAEZ_S7_CEREMONY_BRIDGE_ENABLED", "") or ""
    ).strip().lower() in _TRUTHY
