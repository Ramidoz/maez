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


def bootstrap_shaped(tmp: Path) -> Path:
    """The REAL pre-initialization state: a bootstrap-created ceremony db.

    An empty SQLite file is not it. `S7WebAuthnBootstrapStore` creates five
    tables, and the live store is exactly that plus the authorization
    table. Using an empty file made "pre-initialized" and "damaged" the
    same observable state -- both have zero tables -- so no implementation
    could distinguish them and both REDs were impossible.
    """
    from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

    # The bootstrap store takes a DIRECTORY and appends ceremony.sqlite3
    # itself. Passing the filename made it create ceremony.sqlite3/ as a
    # directory with the database nested inside -- so every test built on
    # this fixture was pointed at the wrong object entirely.
    store = S7WebAuthnBootstrapStore(tmp)
    assert store.db_path == tmp / STORE_NAME, store.db_path
    assert store.db_path.is_file(), "bootstrap did not create a database file"
    return store.db_path


def open_only(path: Path):
    """OPEN an existing store. Never initialises.

    Witnesses of open-side behaviour must not call the initializer as part
    of the act under test, or they prove the pair rather than the open.
    """
    return s7.S7AuthorizationStore(path)


def fresh_store_at(path: Path):
    """Initialise AT an explicit path if absent, then open.

    Established suites build stores at their own paths, not under a tmp
    dir. They are intentional fresh-store callers, so they route through
    the initializer too -- otherwise they die in setup the moment opening
    becomes verification-only.
    """
    path = Path(path)
    # NOT `if not path.exists()`. A bootstrap-created database already
    # exists and is exactly the state that still needs the authorization
    # table added, so an existence check skips initialization precisely
    # where it is required. Initialization is IDEMPOTENT-VERIFY, so it is
    # always safe to call.
    if not hasattr(s7, "initialise_authorization_store"):
        pytest.fail(
            "initialise_authorization_store does not exist yet: this suite "
            "creates a fresh store and cannot do so through the constructor "
            "once opening is verification-only"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    s7.initialise_authorization_store(path)
    return s7.S7AuthorizationStore(path)
