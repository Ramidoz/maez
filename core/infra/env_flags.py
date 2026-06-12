"""Canonical strict on/off environment-flag parser.

The house-wide footgun is `bool(os.environ.get("X"))`: it treats `"0"` (and any
other non-empty string) as truthy, so a flag set to `"0"` reads ON, and every
model.env "Revert: set 0 or remove" comment is half a lie — only *removal*
reverts. This helper is the single source of truth for what "on" means.

IMPORTANT: this is for genuine on/off FLAGS, not presence checks. A presence
check ("is WAYLAND_DISPLAY / DISPLAY set?") legitimately wants
`bool(os.environ.get(...))` because the value is a path/socket, not 1/0 — do NOT
route those through this helper (it would read `wayland-0` as off). See
`core/infra/body_capabilities.env_present` and the `WAYLAND_DISPLAY` check in
`core/memory/ambient.py`, both deliberately left as presence checks.
"""
from __future__ import annotations

import os

# The one truthy set for the whole house.
TRUTHY = frozenset({"1", "true", "yes", "on"})


def strict_env_flag(name: str) -> bool:
    """Return True iff env var ``name`` is set to one of ``1/true/yes/on``.

    ``"0"``, ``false``, ``no``, ``off``, empty, unset, or any other value → False.
    """
    return (os.environ.get(name, "") or "").strip().lower() in TRUTHY
