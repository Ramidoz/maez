"""Shared fresh-store fixture, routed through the initialization seam.

Once ordinary `S7AuthorizationStore(...)` opening correctly REFUSES an
absent database, every suite that built a fresh store by constructing one
would fail during setup -- before reaching the RED it was written to
prove. So intentional fresh stores go through the initializer here, and
opening is only ever opening.

This helper deliberately does NOT fall back to the constructor. A fallback
would keep the old suites green while the prerequisite went unbuilt, which
is the failure mode the prerequisite exists to remove.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7

STORE_NAME = "ceremony.sqlite3"


def initialise(tmp: Path) -> Path:
    """Create a store the way bootstrap/setup does. Never the constructor."""
    if not hasattr(s7, "initialise_authorization_store"):
        pytest.fail(
            "initialise_authorization_store does not exist yet: fresh stores "
            "cannot be created without the constructor's creation authority, "
            "which is the prerequisite under construction"
        )
    path = tmp / STORE_NAME
    s7.initialise_authorization_store(path)
    return path


def fresh_store(tmp: Path):
    """An initialized store, then OPENED -- the two authorities separated."""
    return s7.S7AuthorizationStore(initialise(tmp))
