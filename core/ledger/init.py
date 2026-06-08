# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Explicit, witnessed ledger initialization. Run:

    python -m core.ledger.init [path]   (default: memory/ledger.db)

Runs migrate.run (idempotent), verifies the result is a real ledger, and prints
a CONTENT-FREE status line. NEVER auto-run from the daemon — initialization is a
deliberate owner act.
"""

from __future__ import annotations

import sqlite3
import sys

from core.ledger import migrate

_DEFAULT_PATH = "memory/ledger.db"


def _head_prefix(db_path: str) -> str:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key='last_chain_hash'"
        ).fetchone()
        return row[0][:8] if row and row[0] else "?"
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = args[0] if args else _DEFAULT_PATH
    migrate.run(path)
    if not migrate.ledger_is_initialized(path):
        print(f"ledger init FAILED to verify: {path}", file=sys.stderr)
        return 1
    print(
        f"ledger initialized: {path} | meta=ok turns=ok genesis=ok "
        f"schema_version=1 head={_head_prefix(path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
