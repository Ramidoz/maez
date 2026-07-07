# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Birth dormancy gate checks.

The checks are intentionally read-only. Missing stores and empty stores are
green because they contain no authored rows; unknown provenance classes are red.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import sqlite3

from core.governance.operator_user_boundary import live_webauthn_ceremony_enabled


@dataclass(frozen=True)
class DormancyCheck:
    ok: bool
    detail: str


_ALLOW_EXACT = frozenset(
    {
        "",
        "explicit_api",
        "smoke",
        "window_reseed",
        "manual",
        "reasoning_residue",
        "crisis_signal_held",
        # Owner ruling 2026-07-07: self_wondering = sealed Maez-to-Maez
        # interiority (lean_idle_heartbeat), permitted per the A7 boundary
        # ("sealing Maez away from its own mind would be the wrong kind of
        # privacy"). Writes no soul/wants/identity; the durable-selfhood
        # pens stay red-lined by clause (b) and the wants/wonderings checks.
        "self_wondering",
    }
)
_STORE_QUERIES = (
    ("wants", "wants.db", "want_events", "provenance"),
    ("wonderings", "wonderings.db", "wonderings", "source"),
    ("private_thoughts", "private_thoughts.db", "private_thoughts", "provenance"),
)


def _allowed_class(value: str) -> bool:
    if value in _ALLOW_EXACT:
        return True
    return (
        value.startswith("self_test")
        or value.startswith("cockpit_observation")
        or value.startswith("want:")
    )


def _counts_for_store(db_path: Path, *, table: str, column: str) -> dict[str, int]:
    if not db_path.exists():
        return {}
    uri = f"file:{db_path}?mode=ro"
    # contextlib.closing: a bare `with sqlite3.connect(...)` manages the
    # transaction but does NOT close the connection — it leaked one fd per
    # store per call, exhausting the daemon's fd limit under cockpit
    # readiness polling (2026-07-07). closing() actually releases the fd.
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        try:
            rows = conn.execute(
                f"SELECT COALESCE({column}, ''), COUNT(*) FROM {table} GROUP BY {column}"
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return {}
            raise
    return {str(row[0] or ""): int(row[1]) for row in rows}


def clause_a(*, memory_dir: Path) -> DormancyCheck:
    unknown: dict[str, int] = {}
    unreadable: list[str] = []
    for store_name, filename, table, column in _STORE_QUERIES:
        try:
            counts = _counts_for_store(memory_dir / filename, table=table, column=column)
        except Exception as exc:
            unreadable.append(f"{store_name}:{exc.__class__.__name__}")
            continue
        for provenance, count in counts.items():
            if not _allowed_class(provenance):
                unknown[provenance] = unknown.get(provenance, 0) + count
    if unreadable:
        return DormancyCheck(False, "clause_a unreadable stores: " + ", ".join(unreadable))
    if unknown:
        parts = ", ".join(f"{name}={count}" for name, count in sorted(unknown.items()))
        return DormancyCheck(False, "clause_a unknown provenance classes: " + parts)
    return DormancyCheck(True, "clause_a green: no authored provenance classes found")


def clause_b(*, env: Mapping[str, str] | None = None) -> DormancyCheck:
    armed = live_webauthn_ceremony_enabled(env=env)
    if armed:
        return DormancyCheck(False, "clause_b red: S7 execution authority armed")
    return DormancyCheck(True, "clause_b green: S7 execution authority not armed")


def two_clause(*, memory_dir: Path, env: Mapping[str, str] | None = None) -> DormancyCheck:
    a = clause_a(memory_dir=memory_dir)
    b = clause_b(env=env)
    return DormancyCheck(a.ok and b.ok, f"{a.detail}; {b.detail}")
