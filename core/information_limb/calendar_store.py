"""Calendar v1 noncanonical staging store.

Decision 28 / ADR 0033 keeps Calendar provider data outside Maez's body until
reviewed flows admit derived facts. This store is therefore deliberately small:
minimized provider facts, content-free sidecars, schema guards, and aggregate
telemetry only.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from core.information_limb.calendar_v1 import build_calendar_health


CALENDAR_STORE_SCHEMA_VERSION = "1"
SOURCE_KIND = "calendar.event"

_REQUIRED_TABLES = (
    "calendar_provider_mirror",
    "calendar_read_model",
    "calendar_sync_state",
    "calendar_tombstone_sidecar",
    "calendar_audit_events",
    "calendar_policy_versions",
)

_FORBIDDEN_FACT_KEYS = {
    "description",
    "body",
    "attendee",
    "attendees",
    "attendee_email",
    "attendee_name",
    "organizer",
    "organizer_email",
    "organizer_name",
    "creator",
    "creator_email",
    "creator_name",
    "conference",
    "conference_url",
    "conference_urls",
    "entry_point",
    "entry_points",
    "attachment",
    "attachments",
    "attachment_url",
    "attachment_urls",
    "extended_properties",
    "raw_title",
    "raw_location",
    "title",
    "location",
    "source_id",
    "external_event_id",
    "source_revision",
}

_ALLOWED_SAFE_TOKENS = {
    "[calendar event]",
    "[redacted calendar detail]",
    "[sensitive calendar detail]",
    "[redacted third-party calendar detail]",
}


class CalendarStoreError(RuntimeError):
    """Raised when Calendar v1 staging storage would violate its contract."""


class CalendarStore:
    """SQLite-backed pre-body staging store for Calendar v1."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS calendar_provider_mirror (
                    source_instance_id TEXT NOT NULL,
                    external_event_id_hash TEXT NOT NULL,
                    source_revision_hash TEXT NOT NULL,
                    provider_updated_at TEXT NOT NULL,
                    facts_json TEXT NOT NULL,
                    record_state TEXT NOT NULL DEFAULT 'active',
                    calendar_store_schema_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (source_instance_id, external_event_id_hash)
                );

                CREATE TABLE IF NOT EXISTS calendar_read_model (
                    read_model_id TEXT PRIMARY KEY,
                    source_instance_id TEXT NOT NULL,
                    external_event_id_hash TEXT NOT NULL,
                    safe_summary_token TEXT NOT NULL,
                    starts_at TEXT,
                    ends_at TEXT,
                    calendar_store_schema_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS calendar_sync_state (
                    source_instance_id TEXT PRIMARY KEY,
                    query_shape_hash TEXT NOT NULL,
                    sync_token_ref TEXT,
                    page_checkpoint TEXT,
                    last_success_at TEXT,
                    last_attempt_at TEXT,
                    connector_state TEXT NOT NULL,
                    error_class TEXT NOT NULL DEFAULT '',
                    max_prompt_context_staleness_seconds INTEGER NOT NULL DEFAULT 0,
                    calendar_store_schema_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS calendar_tombstone_sidecar (
                    source_instance_id TEXT NOT NULL,
                    external_event_id_hash TEXT NOT NULL,
                    source_revision_hash TEXT NOT NULL,
                    source_deleted_at TEXT NOT NULL,
                    deletion_observed_at TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_handle_telemetry TEXT NOT NULL,
                    record_state TEXT NOT NULL,
                    calendar_store_schema_version TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (source_instance_id, external_event_id_hash)
                );

                CREATE TABLE IF NOT EXISTS calendar_audit_events (
                    audit_event_id TEXT PRIMARY KEY,
                    event_class TEXT NOT NULL,
                    source_instance_id TEXT,
                    external_event_id_hash TEXT,
                    source_revision_hash TEXT,
                    connector_state TEXT,
                    error_class TEXT NOT NULL DEFAULT '',
                    calendar_store_schema_version TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS calendar_policy_versions (
                    policy_name TEXT PRIMARY KEY,
                    policy_version TEXT NOT NULL,
                    calendar_store_schema_version TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                INSERT INTO calendar_policy_versions (
                    policy_name,
                    policy_version,
                    calendar_store_schema_version
                )
                VALUES (?, ?, ?)
                ON CONFLICT(policy_name) DO NOTHING
                """,
                ("calendar_store", CALENDAR_STORE_SCHEMA_VERSION, CALENDAR_STORE_SCHEMA_VERSION),
            )
        self.validate_schema()

    def validate_schema(self) -> None:
        with self._connection() as conn:
            existing = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            missing = set(_REQUIRED_TABLES) - existing
            if missing:
                raise CalendarStoreError(f"calendar store schema missing tables: {sorted(missing)}")

            for table in _REQUIRED_TABLES:
                columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                if "calendar_store_schema_version" not in columns:
                    raise CalendarStoreError(
                        f"calendar store schema missing version column: {table}"
                    )
                mismatch = conn.execute(
                    f"""
                    SELECT 1
                    FROM {table}
                    WHERE calendar_store_schema_version != ?
                    LIMIT 1
                    """,
                    (CALENDAR_STORE_SCHEMA_VERSION,),
                ).fetchone()
                if mismatch is not None:
                    raise CalendarStoreError(f"calendar store schema mismatch in {table}")

    def upsert_provider_mirror(
        self,
        *,
        source_instance_id: str,
        external_event_id_hash: str,
        source_revision_hash: str,
        provider_updated_at: str,
        facts: dict[str, Any],
    ) -> None:
        self.validate_schema()
        _validate_minimized_facts(facts)
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO calendar_provider_mirror (
                    source_instance_id,
                    external_event_id_hash,
                    source_revision_hash,
                    provider_updated_at,
                    facts_json,
                    record_state,
                    calendar_store_schema_version
                )
                VALUES (?, ?, ?, ?, ?, 'active', ?)
                ON CONFLICT(source_instance_id, external_event_id_hash)
                DO UPDATE SET
                    source_revision_hash=excluded.source_revision_hash,
                    provider_updated_at=excluded.provider_updated_at,
                    facts_json=excluded.facts_json,
                    record_state='active',
                    calendar_store_schema_version=excluded.calendar_store_schema_version,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    source_instance_id,
                    external_event_id_hash,
                    source_revision_hash,
                    provider_updated_at,
                    json.dumps(facts, sort_keys=True, separators=(",", ":")),
                    CALENDAR_STORE_SCHEMA_VERSION,
                ),
            )

    def tombstone_provider_record(
        self,
        *,
        source_instance_id: str,
        external_event_id_hash: str,
        source_revision_hash: str,
        source_deleted_at: str,
        deletion_observed_at: str,
    ) -> None:
        self.validate_schema()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO calendar_tombstone_sidecar (
                    source_instance_id,
                    external_event_id_hash,
                    source_revision_hash,
                    source_deleted_at,
                    deletion_observed_at,
                    source_kind,
                    source_handle_telemetry,
                    record_state,
                    calendar_store_schema_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'tombstoned', ?)
                ON CONFLICT(source_instance_id, external_event_id_hash)
                DO UPDATE SET
                    source_revision_hash=excluded.source_revision_hash,
                    source_deleted_at=excluded.source_deleted_at,
                    deletion_observed_at=excluded.deletion_observed_at,
                    record_state='tombstoned',
                    calendar_store_schema_version=excluded.calendar_store_schema_version
                """,
                (
                    source_instance_id,
                    external_event_id_hash,
                    source_revision_hash,
                    source_deleted_at,
                    deletion_observed_at,
                    SOURCE_KIND,
                    source_instance_id,
                    CALENDAR_STORE_SCHEMA_VERSION,
                ),
            )

    def delete_provider_mirror(
        self, *, source_instance_id: str, external_event_id_hash: str
    ) -> None:
        self.validate_schema()
        with self._connection() as conn:
            tombstone = conn.execute(
                """
                SELECT 1
                FROM calendar_tombstone_sidecar
                WHERE source_instance_id=? AND external_event_id_hash=?
                LIMIT 1
                """,
                (source_instance_id, external_event_id_hash),
            ).fetchone()
            if tombstone is None:
                raise CalendarStoreError("provider mirror delete requires durable tombstone")
            conn.execute(
                """
                DELETE FROM calendar_provider_mirror
                WHERE source_instance_id=? AND external_event_id_hash=?
                """,
                (source_instance_id, external_event_id_hash),
            )

    def health_snapshot(self, *, mode: str, auth_ready: bool = False) -> dict:
        self.validate_schema()
        with self._connection() as conn:
            event_count = conn.execute(
                "SELECT COUNT(*) FROM calendar_provider_mirror WHERE record_state='active'"
            ).fetchone()[0]
            read_model_count = conn.execute("SELECT COUNT(*) FROM calendar_read_model").fetchone()[
                0
            ]
        return build_calendar_health(
            mode=mode,
            auth_ready=auth_ready,
            event_count=event_count,
            read_model_count=read_model_count,
        )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=2.0)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _validate_minimized_facts(facts: dict[str, Any]) -> None:
    for key, value in _walk_items(facts):
        if key.lower() in _FORBIDDEN_FACT_KEYS:
            raise CalendarStoreError(f"forbidden Calendar fact field: {key}")
        if key.lower() in {"safe_title_token", "safe_location_token"}:
            if not isinstance(value, str) or value not in _ALLOWED_SAFE_TOKENS:
                raise CalendarStoreError(f"Calendar safe token is not approved: {key}")


def _walk_items(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key), child
            yield from _walk_items(child)
    elif isinstance(value, list | tuple):
        for child in value:
            yield from _walk_items(child)
