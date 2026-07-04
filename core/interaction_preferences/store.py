from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.infra import paths

PREFERENCE_CLASSES = frozenset({"question_cadence"})
STATUSES = frozenset({"active", "retracted", "superseded"})


@dataclass(frozen=True)
class InteractionPreference:
    preference_id: str
    created_at: str
    updated_at: str
    status: str
    preference_class: str
    owner_statement: str
    source_ref: str
    surface: str
    statement_sha256: str
    supersedes_preference_id: str | None = None
    superseded_by_preference_id: str | None = None
    retraction_reason: str | None = None
    revision_statement: str | None = None


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _row_to_preference(row: sqlite3.Row) -> InteractionPreference:
    return InteractionPreference(
        preference_id=str(row["preference_id"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        status=str(row["status"]),
        preference_class=str(row["preference_class"]),
        owner_statement=str(row["owner_statement"]),
        source_ref=str(row["source_ref"]),
        surface=str(row["surface"]),
        statement_sha256=str(row["statement_sha256"]),
        supersedes_preference_id=row["supersedes_preference_id"],
        superseded_by_preference_id=row["superseded_by_preference_id"],
        retraction_reason=row["retraction_reason"],
        revision_statement=row["revision_statement"],
    )


def _connect_readonly(db_path: Path | str) -> sqlite3.Connection:
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con  # sqlite-raw-ok: read helpers wrap in closing() and never expose the connection


def _table_exists(con: sqlite3.Connection) -> bool:
    row = con.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'interaction_preferences'
        """
    ).fetchone()
    return row is not None


def list_all_readonly(db_path: Path | str) -> list[InteractionPreference]:
    path = Path(db_path)
    if not path.exists():
        return []
    try:
        with closing(_connect_readonly(path)) as con:
            if not _table_exists(con):
                return []
            rows = con.execute(
                """
                SELECT * FROM interaction_preferences
                ORDER BY created_at ASC, preference_id ASC
                """
            ).fetchall()
    except sqlite3.DatabaseError:
        return []
    return [_row_to_preference(row) for row in rows]


def get_readonly(
    db_path: Path | str,
    preference_id: str,
) -> InteractionPreference | None:
    path = Path(db_path)
    if not path.exists():
        return None
    try:
        with closing(_connect_readonly(path)) as con:
            if not _table_exists(con):
                return None
            row = con.execute(
                """
                SELECT * FROM interaction_preferences
                WHERE preference_id = ?
                """,
                (_require_text(preference_id, "preference_id"),),
            ).fetchone()
    except sqlite3.DatabaseError:
        return None
    return _row_to_preference(row) if row is not None else None


def _require_text(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _validate_preference_class(preference_class: str) -> str:
    value = _require_text(preference_class, "preference_class")
    if value not in PREFERENCE_CLASSES:
        raise ValueError(f"unsupported preference_class: {value!r}")
    return value


class InteractionPreferencesStore:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else paths.interaction_preferences_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))  # sqlite-raw-ok: private factory; callers wrap in closing() and own commit scope
        con.row_factory = sqlite3.Row
        return con  # sqlite-raw-ok: store methods wrap in closing() and own commit scope

    def _init_schema(self) -> None:
        with closing(self._connect()) as con, con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS interaction_preferences (
                    preference_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('active', 'retracted', 'superseded')),
                    preference_class TEXT NOT NULL CHECK (preference_class IN ('question_cadence')),
                    owner_statement TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    statement_sha256 TEXT NOT NULL,
                    supersedes_preference_id TEXT,
                    superseded_by_preference_id TEXT,
                    retraction_reason TEXT,
                    revision_statement TEXT
                )
                """
            )
            con.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_interaction_preferences_status_class
                ON interaction_preferences (status, preference_class)
                """
            )
            con.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_interaction_preferences_statement_class
                ON interaction_preferences (statement_sha256, preference_class)
                """
            )

    def record_capture(
        self,
        *,
        preference_id: str,
        preference_class: str,
        owner_statement: str,
        source_ref: str,
        surface: str,
        statement_sha256: str,
        created_at: str | None = None,
    ) -> InteractionPreference:
        created = created_at or _now_utc()
        pref = InteractionPreference(
            preference_id=_require_text(preference_id, "preference_id"),
            created_at=created,
            updated_at=created,
            status="active",
            preference_class=_validate_preference_class(preference_class),
            owner_statement=_require_text(owner_statement, "owner_statement"),
            source_ref=_require_text(source_ref, "source_ref"),
            surface=_require_text(surface, "surface"),
            statement_sha256=_require_text(statement_sha256, "statement_sha256"),
        )
        with closing(self._connect()) as con, con:
            con.execute(
                """
                INSERT INTO interaction_preferences (
                    preference_id, created_at, updated_at, status,
                    preference_class, owner_statement, source_ref, surface,
                    statement_sha256, supersedes_preference_id,
                    superseded_by_preference_id, retraction_reason,
                    revision_statement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pref.preference_id,
                    pref.created_at,
                    pref.updated_at,
                    pref.status,
                    pref.preference_class,
                    pref.owner_statement,
                    pref.source_ref,
                    pref.surface,
                    pref.statement_sha256,
                    pref.supersedes_preference_id,
                    pref.superseded_by_preference_id,
                    pref.retraction_reason,
                    pref.revision_statement,
                ),
            )
        return pref

    def record_retraction(
        self,
        *,
        preference_id: str,
        preference_class: str,
        owner_statement: str,
        source_ref: str,
        surface: str,
        statement_sha256: str,
        supersedes_preference_id: str,
        retraction_reason: str,
        created_at: str | None = None,
    ) -> InteractionPreference:
        created = created_at or _now_utc()
        supersedes = _require_text(supersedes_preference_id, "supersedes_preference_id")
        pref = InteractionPreference(
            preference_id=_require_text(preference_id, "preference_id"),
            created_at=created,
            updated_at=created,
            status="retracted",
            preference_class=_validate_preference_class(preference_class),
            owner_statement=_require_text(owner_statement, "owner_statement"),
            source_ref=_require_text(source_ref, "source_ref"),
            surface=_require_text(surface, "surface"),
            statement_sha256=_require_text(statement_sha256, "statement_sha256"),
            supersedes_preference_id=supersedes,
            retraction_reason=_require_text(retraction_reason, "retraction_reason"),
        )
        with closing(self._connect()) as con, con:
            con.execute(
                """
                UPDATE interaction_preferences
                SET status = 'retracted',
                    updated_at = ?,
                    superseded_by_preference_id = ?
                WHERE preference_id = ?
                """,
                (created, pref.preference_id, supersedes),
            )
            con.execute(
                """
                INSERT INTO interaction_preferences (
                    preference_id, created_at, updated_at, status,
                    preference_class, owner_statement, source_ref, surface,
                    statement_sha256, supersedes_preference_id,
                    superseded_by_preference_id, retraction_reason,
                    revision_statement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pref.preference_id,
                    pref.created_at,
                    pref.updated_at,
                    pref.status,
                    pref.preference_class,
                    pref.owner_statement,
                    pref.source_ref,
                    pref.surface,
                    pref.statement_sha256,
                    pref.supersedes_preference_id,
                    pref.superseded_by_preference_id,
                    pref.retraction_reason,
                    pref.revision_statement,
                ),
            )
        return pref

    def get(self, preference_id: str) -> InteractionPreference | None:
        with closing(self._connect()) as con:
            row = con.execute(
                """
                SELECT * FROM interaction_preferences
                WHERE preference_id = ?
                """,
                (_require_text(preference_id, "preference_id"),),
            ).fetchone()
        return _row_to_preference(row) if row is not None else None

    def active_preferences(
        self, preference_class: str | None = None
    ) -> list[InteractionPreference]:
        where = "WHERE status = 'active'"
        params: tuple[str, ...] = ()
        if preference_class is not None:
            where += " AND preference_class = ?"
            params = (_validate_preference_class(preference_class),)
        with closing(self._connect()) as con:
            rows = con.execute(
                f"""
                SELECT * FROM interaction_preferences
                {where}
                ORDER BY created_at ASC, preference_id ASC
                """,
                params,
            ).fetchall()
        return [_row_to_preference(row) for row in rows]

    def list_all(self) -> list[InteractionPreference]:
        with closing(self._connect()) as con:
            rows = con.execute(
                """
                SELECT * FROM interaction_preferences
                ORDER BY created_at ASC, preference_id ASC
                """
            ).fetchall()
        return [_row_to_preference(row) for row in rows]
