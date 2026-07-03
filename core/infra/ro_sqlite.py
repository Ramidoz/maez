"""Read-only SQLite helpers for inspection surfaces.

These helpers are intentionally tiny: a missing DB is data absence, not a
reason to create an empty file just to report on it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote


def _ro_connect(path: str | Path) -> sqlite3.Connection | None:
    db_path = Path(path)
    if not db_path.exists():
        return None
    uri_path = quote(str(db_path.resolve()), safe="/")
    con = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con
