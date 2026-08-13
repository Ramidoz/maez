#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Rehearse the v1->v2 migration on a COPY of the real ceremony store.

The migration has only ever run against synthetic fixtures. The owner's
store -- holding two enabled founder credentials -- would be its first real
subject, and "the tests pass" is not "the live path works": that gap has
already cost this project twice. This makes the live run a REPEAT of
something already observed rather than a first attempt.

It copies the live store byte-for-byte into a scratch directory, migrates
the COPY, and reports what actually happened to it. The live store is only
ever READ.

    python3 -m scripts.s7_migration_rehearsal [--keep]

Exit status 0 if the rehearsed migration produced a store the ceremony
would accept, 1 otherwise. `--keep` leaves the rehearsed copy on disk for
inspection instead of deleting it.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIVE_STORE = REPO / "memory" / "s7_1_webauthn" / "ceremony.sqlite3"

V2_AUTH_TABLE = "s7_authorization_artifacts_v2"
V1_AUTH_TABLE = "s7_authorization_artifacts"
CREDENTIALS_TABLE = "s7_founder_webauthn_credentials"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(path: Path) -> dict[str, object]:
    """Facts we require the migration to preserve, read read-only."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        counts = {}
        for table in (V1_AUTH_TABLE, CREDENTIALS_TABLE):
            if table in tables:
                counts[table] = conn.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
        creds = []
        if CREDENTIALS_TABLE in tables:
            creds = sorted(
                conn.execute(
                    f"SELECT credential_ref, enabled, role_names_json, record_hash "
                    f"FROM {CREDENTIALS_TABLE}"
                )
            )
        return {"tables": tables, "counts": counts, "credentials": creds}
    finally:
        conn.close()


def rehearse(scratch: Path) -> list[tuple[str, bool, str]]:
    """Migrate a copy and report. Returns (name, passed, detail) rows."""
    results: list[tuple[str, bool, str]] = []

    live_before = _digest(LIVE_STORE)
    before = _snapshot(LIVE_STORE)

    # The migration resolves its store by NAME inside the directory, so the
    # copy has to keep it. Copy, never move: the source is only read.
    from core.governance import s7_v2_migration as migration

    copy_path = scratch / migration.STORE_NAME
    shutil.copyfile(LIVE_STORE, copy_path)
    copy_path.chmod(0o600)
    results.append(
        ("copy is byte-identical", _digest(copy_path) == live_before, live_before[:16])
    )

    dir_fd = os.open(scratch, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        migration._migrate_authorization_store_to_v2_at(store_dir_fd=dir_fd)
        results.append(("migration ran", True, "no exception"))
    except Exception as exc:
        results.append(("migration ran", False, f"{type(exc).__name__}: {exc}"))
        return results
    finally:
        os.close(dir_fd)

    after = _snapshot(copy_path)

    results.append(
        (
            "v2 plane created",
            V2_AUTH_TABLE in after["tables"],
            f"{V2_AUTH_TABLE} "
            + ("present" if V2_AUTH_TABLE in after["tables"] else "ABSENT"),
        )
    )
    receipt = scratch / migration.RECEIPT_NAME
    results.append(
        ("migration receipt written", receipt.exists(), migration.RECEIPT_NAME)
    )
    results.append(
        (
            "credentials preserved exactly",
            after["credentials"] == before["credentials"],
            f"{len(before['credentials'])} before, {len(after['credentials'])} after",
        )
    )
    v1_before = before["counts"].get(V1_AUTH_TABLE)
    v1_after = after["counts"].get(V1_AUTH_TABLE)
    results.append(
        (
            "v1 rows untouched",
            v1_before == v1_after,
            f"{v1_before} before, {v1_after} after",
        )
    )
    # Canon: v1 rows are deliberately NOT copied forward, because doing so
    # would manufacture v2 evidence for authorizations that never had it.
    v2_rows = None
    conn = sqlite3.connect(f"file:{copy_path}?mode=ro", uri=True)
    try:
        if V2_AUTH_TABLE in after["tables"]:
            v2_rows = conn.execute(f"SELECT COUNT(*) FROM {V2_AUTH_TABLE}").fetchone()[
                0
            ]
    finally:
        conn.close()
    results.append(
        (
            "v2 plane starts EMPTY",
            v2_rows == 0,
            f"{v2_rows} rows -- v1 evidence must not be manufactured forward",
        )
    )

    results.append(
        (
            "LIVE STORE UNTOUCHED",
            _digest(LIVE_STORE) == live_before,
            "hash identical before and after the rehearsal",
        )
    )
    return results


def main() -> int:
    keep = "--keep" in sys.argv
    if not LIVE_STORE.exists():
        print(f"live store absent: {LIVE_STORE}")
        return 1
    scratch = Path(tempfile.mkdtemp(prefix="s7-migration-rehearsal-"))
    try:
        results = rehearse(scratch)
        width = max(len(name) for name, _, _ in results)
        for name, passed, detail in results:
            print(f"  [{'PASS' if passed else 'FAIL'}] {name.ljust(width)}  {detail}")
        ok = all(passed for _, passed, _ in results)
        print()
        print(
            "REHEARSAL CLEAN: migrating the live store would repeat this."
            if ok
            else "REHEARSAL FAILED: do NOT migrate the live store."
        )
        if keep:
            print(f"rehearsed copy kept at: {scratch}")
        return 0 if ok else 1
    finally:
        if not keep:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
