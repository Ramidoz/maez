#!/usr/bin/env python3
"""Create the S7 authorization store. The sole creation command.

Opening an S7AuthorizationStore is verification-only, so exactly one route
may build the store, and this is it. The callsite allowlist pins that to
`scripts/s7_initialise_store.py::main` -- fully qualified, so the call may
not move into a class or a closure here either.

Creation happens ONLY when main() runs. Nothing at module level touches
the store, because importing this file must not be an act of authority.
"""

from __future__ import annotations

from core.governance.operator_user_boundary import initialise_authorization_store
from core.governance.s7_webauthn_bootstrap import DEFAULT_STORE_ROOT


def main() -> int:
    initialise_authorization_store(DEFAULT_STORE_ROOT / "ceremony.sqlite3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
