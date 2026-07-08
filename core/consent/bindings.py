"""Owner-surface binding registry for conversational consent."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping


DEFAULT_BINDING_DB_PATH: Path | None = None
DEFAULT_BINDING_RECEIPT_LOG: Path | None = None


def _default_binding_db_path() -> Path:
    global DEFAULT_BINDING_DB_PATH
    if DEFAULT_BINDING_DB_PATH is None:
        from core.infra import paths

        DEFAULT_BINDING_DB_PATH = (
            paths.memory_dir() / "consent" / "owner_surface_bindings.sqlite3"
        )
    return DEFAULT_BINDING_DB_PATH


def _default_binding_receipt_log() -> Path:
    global DEFAULT_BINDING_RECEIPT_LOG
    if DEFAULT_BINDING_RECEIPT_LOG is None:
        from core.infra import paths

        DEFAULT_BINDING_RECEIPT_LOG = (
            paths.logs_dir() / "consent_binding_receipts.jsonl"
        )
    return DEFAULT_BINDING_RECEIPT_LOG


@dataclass(frozen=True)
class ConsentBindingPaths:
    db_path: Path
    receipt_log: Path

    @classmethod
    def defaults(cls) -> "ConsentBindingPaths":
        return cls(
            db_path=_default_binding_db_path(),
            receipt_log=_default_binding_receipt_log(),
        )


@dataclass(frozen=True)
class BindingRecord:
    binding_id: str
    surface_kind: str
    surface_identity: str
    status: str
    enrolled_at: str
    enrolled_via: str
    revoked_at: str | None = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS owner_surface_bindings (
    binding_id TEXT PRIMARY KEY,
    surface_kind TEXT NOT NULL,
    surface_identity TEXT NOT NULL,
    status TEXT NOT NULL,
    enrolled_at TEXT NOT NULL,
    enrolled_via TEXT NOT NULL,
    revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_owner_surface_bindings_lookup
ON owner_surface_bindings(surface_kind, surface_identity, status);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _append_receipt(path: Path, receipt: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(receipt), sort_keys=True, separators=(",", ":")))
        f.write("\n")


def telegram_surface_identity(user_id: object, chat_id: object) -> str:
    return f"{str(user_id).strip()}:{str(chat_id).strip()}"


def _row_to_binding(row: sqlite3.Row) -> BindingRecord:
    return BindingRecord(
        binding_id=str(row["binding_id"]),
        surface_kind=str(row["surface_kind"]),
        surface_identity=str(row["surface_identity"]),
        status=str(row["status"]),
        enrolled_at=str(row["enrolled_at"]),
        enrolled_via=str(row["enrolled_via"]),
        revoked_at=row["revoked_at"],
    )


class BindingRegistry:
    def __init__(self, paths: ConsentBindingPaths | None = None):
        self.paths = paths or ConsentBindingPaths.defaults()
        self.paths.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.paths.db_path)) as conn, conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.paths.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def enroll(
        self,
        surface_kind: str,
        surface_identity: str,
        *,
        enrolled_via: str,
    ) -> BindingRecord:
        surface_kind = str(surface_kind).strip()
        surface_identity = str(surface_identity).strip()
        existing = self.active_binding_for(surface_kind, surface_identity)
        if existing is not None:
            return existing

        binding_id = f"bind_{secrets.token_hex(12)}"
        now = _now_iso()
        with closing(self._conn()) as conn, conn:
            conn.execute(
                """
                INSERT INTO owner_surface_bindings (
                    binding_id, surface_kind, surface_identity, status,
                    enrolled_at, enrolled_via, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    binding_id,
                    surface_kind,
                    surface_identity,
                    "active",
                    now,
                    enrolled_via,
                ),
            )
        record = self.get(binding_id)
        if record is None:
            raise RuntimeError(f"binding disappeared after enroll: {binding_id}")
        _append_receipt(
            self.paths.receipt_log,
            {
                "event": "enrolled",
                "binding_id": record.binding_id,
                "surface_kind": record.surface_kind,
                "surface_identity": record.surface_identity,
                "status": record.status,
                "enrolled_at": record.enrolled_at,
                "enrolled_via": record.enrolled_via,
                "at": now,
            },
        )
        return record

    def revoke(self, binding_id: str) -> BindingRecord:
        now = _now_iso()
        with closing(self._conn()) as conn, conn:
            row = conn.execute(
                "SELECT * FROM owner_surface_bindings WHERE binding_id = ?",
                (binding_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"binding not found: {binding_id}")
            if row["status"] != "revoked":
                conn.execute(
                    """
                    UPDATE owner_surface_bindings
                    SET status = 'revoked', revoked_at = ?
                    WHERE binding_id = ?
                    """,
                    (now, binding_id),
                )
        record = self.get(binding_id)
        if record is None:
            raise RuntimeError(f"binding disappeared after revoke: {binding_id}")
        if record.revoked_at == now:
            _append_receipt(
                self.paths.receipt_log,
                {
                    "event": "revoked",
                    "binding_id": record.binding_id,
                    "surface_kind": record.surface_kind,
                    "surface_identity": record.surface_identity,
                    "status": record.status,
                    "revoked_at": record.revoked_at,
                    "at": now,
                },
            )
        return record

    def get(self, binding_id: str) -> BindingRecord | None:
        with closing(self._conn()) as conn:
            row = conn.execute(
                "SELECT * FROM owner_surface_bindings WHERE binding_id = ?",
                (binding_id,),
            ).fetchone()
        return _row_to_binding(row) if row else None

    def active_binding_for(
        self,
        surface_kind: str,
        surface_identity: str,
    ) -> BindingRecord | None:
        with closing(self._conn()) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM owner_surface_bindings
                WHERE surface_kind = ?
                  AND surface_identity = ?
                  AND status = 'active'
                ORDER BY enrolled_at DESC
                LIMIT 1
                """,
                (str(surface_kind).strip(), str(surface_identity).strip()),
            ).fetchone()
        return _row_to_binding(row) if row else None

    def list_bindings(self) -> list[BindingRecord]:
        with closing(self._conn()) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM owner_surface_bindings
                ORDER BY enrolled_at ASC
                """
            ).fetchall()
        return [_row_to_binding(row) for row in rows]

    def migrate_telegram_env_binding(self) -> BindingRecord | None:
        user_id = (os.environ.get("MAEZ_TELEGRAM_USER_ID") or "").strip()
        chat_id = (
            os.environ.get("MAEZ_TELEGRAM_CHAT_ID")
            or os.environ.get("MAEZ_TELEGRAM_OWNER_CHAT_ID")
            or os.environ.get("TELEGRAM_CHAT_ID")
            or ""
        ).strip()
        if not user_id or not chat_id:
            return None
        return self.enroll(
            "telegram",
            telegram_surface_identity(user_id, chat_id),
            enrolled_via="migration_env",
        )

