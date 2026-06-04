"""GitHub v1 noncanonical staging store.

GitHub provider data stays outside Maez's body until the single reviewed
repo-count admission writes an observed, taint-railed memory row. This store
therefore persists only minimized staging facts and content-free telemetry.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from core.information_limb.github_connector_policy import (
    GithubPolicyError,
    assert_fact_minimized,
)


GITHUB_STORE_SCHEMA_VERSION = "2"
SOURCE_KIND = "github.repo_count"

_EXPECTED_COLUMNS = {
    "github_provider_mirror": {
        "ingest_record_id",
        "fetch_batch_id",
        "repo_count",
        "count_field",
        "count_hash",
        "record_state",
        "promotion_state",
        "body_memory_id",
        "github_store_schema_version",
        "updated_at",
    },
    "github_policy_versions": {
        "policy_name",
        "policy_version",
        "github_store_schema_version",
        "updated_at",
    },
}


class GithubStoreError(RuntimeError):
    """Raised when GitHub v1 staging storage would violate its contract."""


class GithubStore:
    """SQLite-backed pre-body staging store for GitHub v1."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS github_provider_mirror (
                    ingest_record_id TEXT PRIMARY KEY,
                    fetch_batch_id TEXT NOT NULL,
                    repo_count INTEGER NOT NULL,
                    count_field TEXT NOT NULL,
                    count_hash TEXT NOT NULL,
                    record_state TEXT NOT NULL DEFAULT 'active',
                    promotion_state TEXT NOT NULL DEFAULT 'pending',
                    body_memory_id TEXT,
                    github_store_schema_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS github_policy_versions (
                    policy_name TEXT PRIMARY KEY,
                    policy_version TEXT NOT NULL,
                    github_store_schema_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                INSERT INTO github_policy_versions (
                    policy_name,
                    policy_version,
                    github_store_schema_version
                )
                VALUES (?, ?, ?)
                ON CONFLICT(policy_name) DO NOTHING
                """,
                ("github_store", GITHUB_STORE_SCHEMA_VERSION, GITHUB_STORE_SCHEMA_VERSION),
            )
            self._migrate_schema(conn)
            conn.execute(
                """
                INSERT INTO github_policy_versions (
                    policy_name,
                    policy_version,
                    github_store_schema_version
                )
                VALUES (?, ?, ?)
                ON CONFLICT(policy_name) DO UPDATE SET
                    policy_version=excluded.policy_version,
                    github_store_schema_version=excluded.github_store_schema_version,
                    updated_at=CURRENT_TIMESTAMP
                """,
                ("github_store", GITHUB_STORE_SCHEMA_VERSION, GITHUB_STORE_SCHEMA_VERSION),
            )
        self.validate_schema()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(github_provider_mirror)")
        }
        if "promotion_state" not in columns:
            conn.execute(
                """
                ALTER TABLE github_provider_mirror
                ADD COLUMN promotion_state TEXT NOT NULL DEFAULT 'pending'
                """
            )
        if "body_memory_id" not in columns:
            conn.execute(
                """
                ALTER TABLE github_provider_mirror
                ADD COLUMN body_memory_id TEXT
                """
            )
        conn.execute(
            """
            UPDATE github_provider_mirror
            SET github_store_schema_version=?
            WHERE github_store_schema_version != ?
            """,
            (GITHUB_STORE_SCHEMA_VERSION, GITHUB_STORE_SCHEMA_VERSION),
        )
        conn.execute(
            """
            UPDATE github_policy_versions
            SET github_store_schema_version=?
            WHERE github_store_schema_version != ?
            """,
            (GITHUB_STORE_SCHEMA_VERSION, GITHUB_STORE_SCHEMA_VERSION),
        )

    def validate_schema(self) -> None:
        with self._connection() as conn:
            existing = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            missing = set(_EXPECTED_COLUMNS) - existing
            if missing:
                raise GithubStoreError(f"github store schema missing tables: {sorted(missing)}")

            for table, expected_columns in _EXPECTED_COLUMNS.items():
                columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                if columns != expected_columns:
                    raise GithubStoreError(f"github store schema incompatible: {table}")
                mismatch = conn.execute(
                    f"""
                    SELECT 1
                    FROM {table}
                    WHERE github_store_schema_version != ?
                    LIMIT 1
                    """,
                    (GITHUB_STORE_SCHEMA_VERSION,),
                ).fetchone()
                if mismatch is not None:
                    raise GithubStoreError(f"github store schema mismatch in {table}")

    def stage_repo_count(
        self,
        *,
        ingest_record_id: str,
        fetch_batch_id: str,
        repo_count: int,
        count_field: str,
    ) -> dict[str, str]:
        self.validate_schema()
        try:
            assert_fact_minimized({"repo_count": repo_count, "count_field": count_field})
        except GithubPolicyError as exc:
            raise GithubStoreError(str(exc)) from exc

        count_hash = _count_hash(repo_count=repo_count, count_field=count_field)
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO github_provider_mirror (
                    ingest_record_id,
                    fetch_batch_id,
                    repo_count,
                    count_field,
                    count_hash,
                    record_state,
                    promotion_state,
                    github_store_schema_version
                )
                VALUES (?, ?, ?, ?, ?, 'active', 'pending', ?)
                ON CONFLICT(ingest_record_id)
                DO UPDATE SET
                    fetch_batch_id=excluded.fetch_batch_id,
                    repo_count=excluded.repo_count,
                    count_field=excluded.count_field,
                    count_hash=excluded.count_hash,
                    record_state='active',
                    github_store_schema_version=excluded.github_store_schema_version,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    ingest_record_id,
                    fetch_batch_id,
                    repo_count,
                    count_field,
                    count_hash,
                    GITHUB_STORE_SCHEMA_VERSION,
                ),
            )
        return {
            "ingest_record_id": ingest_record_id,
            "fetch_batch_id": fetch_batch_id,
            "record_state": "active",
            "count_hash": count_hash,
        }

    def promotion_state(self, ingest_record_id: str) -> str:
        self.validate_schema()
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT promotion_state
                FROM github_provider_mirror
                WHERE ingest_record_id=?
                """,
                (ingest_record_id,),
            ).fetchone()
        return str(row[0]) if row is not None else "absent"

    def mark_admitted(self, ingest_record_id: str, *, body_memory_id: str) -> None:
        self.validate_schema()
        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE github_provider_mirror
                SET promotion_state='admitted',
                    body_memory_id=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE ingest_record_id=?
                """,
                (body_memory_id, ingest_record_id),
            )
            if cursor.rowcount != 1:
                raise GithubStoreError(
                    f"github ingest record absent: {ingest_record_id}"
                )

    def admitted_body_memory_id(self, ingest_record_id: str) -> str | None:
        self.validate_schema()
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT body_memory_id
                FROM github_provider_mirror
                WHERE ingest_record_id=?
                """,
                (ingest_record_id,),
            ).fetchone()
        return str(row[0]) if row is not None and row[0] is not None else None

    def health(self) -> dict[str, int | str]:
        self.validate_schema()
        with self._connection() as conn:
            staged_records = conn.execute(
                "SELECT COUNT(*) FROM github_provider_mirror WHERE record_state='active'"
            ).fetchone()[0]
        return {
            "source_kind": SOURCE_KIND,
            "store_state": "available",
            "staged_records": int(staged_records),
            "schema_version": GITHUB_STORE_SCHEMA_VERSION,
        }

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=2.0)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _count_hash(*, repo_count: int, count_field: str) -> str:
    payload = f"github.v1|{count_field}|{repo_count}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
