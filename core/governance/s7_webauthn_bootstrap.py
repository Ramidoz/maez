# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S7.1 first-credential bootstrap store and CLI.

This module owns the authority root before any founder WebAuthn credential
exists. It deliberately does not prove that the local shell user is Rohit; it
only makes cockpit HTTP access and originless daemon calls insufficient to
create the first credential.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
from typing import Any
import uuid


DEFAULT_STORE_ROOT = Path("memory/s7_1_webauthn")
MAX_BOOTSTRAP_TTL_MINUTES = 10
MIN_BOOTSTRAP_TOKEN_BYTES = 16


_SCHEMA = """
CREATE TABLE IF NOT EXISTS s7_ceremony_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS s7_bootstrap_intents (
    intent_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL,
    purpose TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    revoked_at TEXT,
    issuer_uid INTEGER NOT NULL,
    store_owner_uid INTEGER NOT NULL,
    repo_path TEXT NOT NULL,
    issuer_tty_fingerprint TEXT NOT NULL,
    audit_ref TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS s7_founder_webauthn_credentials (
    credential_ref TEXT PRIMARY KEY,
    public_key TEXT NOT NULL,
    credential_kind TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class CreatedBootstrapIntent:
    intent_id: str
    raw_token: str
    purpose: str
    expires_at: str
    audit_ref: str


class S7WebAuthnBootstrapStore:
    """SQLite-backed S7.1 first-credential bootstrap store."""

    def __init__(self, root: Path | str = DEFAULT_STORE_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.db_path = self.root / "ceremony.sqlite3"
        self.audit_path = self.root / "ceremony.audit.jsonl"
        self._init_db()
        self._ensure_audit_file()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO s7_ceremony_metadata(key, value) VALUES (?, ?)",
                ("bootstrap_hmac_key", secrets.token_hex(32)),
            )
        os.chmod(self.db_path, 0o600)

    def _ensure_audit_file(self) -> None:
        self.audit_path.touch(exist_ok=True)
        os.chmod(self.audit_path, 0o600)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _hmac_key(self, conn: sqlite3.Connection) -> bytes:
        row = conn.execute(
            "SELECT value FROM s7_ceremony_metadata WHERE key = ?",
            ("bootstrap_hmac_key",),
        ).fetchone()
        if row is None:
            raise RuntimeError("s7_bootstrap_hmac_key_missing")
        return bytes.fromhex(row["value"])

    def _hash_token(self, raw_token: str, conn: sqlite3.Connection) -> str:
        digest = hmac.new(
            self._hmac_key(conn),
            raw_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"hmac:s7.1:bootstrap:{digest}"

    def _audit(self, event: str, payload: dict[str, Any]) -> str:
        audit_ref = f"s7_1_bootstrap_audit:{uuid.uuid4().hex}"
        row = {"audit_ref": audit_ref, "event": event, **payload}
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        return audit_ref

    def first_registration_readiness(self, *, now: str) -> dict[str, Any]:
        state = self.bootstrap_state(now=now)
        if state == "absent":
            return {
                "ok": False,
                "error": "s7_bootstrap_required",
                "bootstrap_state": "absent",
            }
        if state == "issued":
            return {"ok": True, "bootstrap_state": "issued"}
        return {"ok": False, "error": "s7_bootstrap_invalid", "bootstrap_state": state}

    def bootstrap_state(self, *, now: str) -> str:
        with closing(self._conn()) as conn:
            if self._bootstrap_closed_at(conn) is not None or self.has_enabled_primary(conn=conn):
                return "closed"
            active = self._active_intent_count(conn, now=now)
            if active:
                return "issued"
            expired = conn.execute(
                """
                SELECT 1 FROM s7_bootstrap_intents
                WHERE consumed_at IS NULL
                  AND revoked_at IS NULL
                  AND expires_at <= ?
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if expired is not None:
                return "expired"
            consumed = conn.execute(
                "SELECT 1 FROM s7_bootstrap_intents WHERE consumed_at IS NOT NULL LIMIT 1"
            ).fetchone()
            if consumed is not None:
                return "consumed"
            return "absent"

    def create_bootstrap_intent(
        self,
        *,
        purpose: str,
        ttl_minutes: int,
        now: str,
        effective_uid: int | None = None,
        is_interactive: bool | None = None,
        tty_path: str | None = None,
        token_bytes: bytes | None = None,
    ) -> CreatedBootstrapIntent:
        if purpose != "register_primary":
            raise ValueError("s7_bootstrap_bad_purpose")
        if ttl_minutes > MAX_BOOTSTRAP_TTL_MINUTES:
            raise ValueError("s7_bootstrap_ttl_too_long")
        if ttl_minutes <= 0:
            raise ValueError("s7_bootstrap_ttl_invalid")
        if is_interactive is None:
            is_interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if not is_interactive:
            raise RuntimeError("s7_bootstrap_non_interactive")
        effective_uid = os.geteuid() if effective_uid is None else effective_uid
        store_owner_uid = self.root.stat().st_uid
        if effective_uid != store_owner_uid:
            raise RuntimeError("s7_bootstrap_uid_mismatch")
        if not tty_path:
            tty_path = os.ttyname(sys.stdin.fileno()) if sys.stdin.isatty() else "unknown-tty"
        token_bytes = token_bytes if token_bytes is not None else secrets.token_bytes(32)
        if len(token_bytes) < MIN_BOOTSTRAP_TOKEN_BYTES:
            raise ValueError("s7_bootstrap_entropy_too_low")
        raw_token = base64.urlsafe_b64encode(token_bytes).decode("ascii").rstrip("=")
        intent_id = f"s7_bootstrap_{uuid.uuid4().hex}"
        issued_at = now
        expires_at = _add_minutes(now, ttl_minutes)
        tty_fingerprint = _fingerprint(tty_path)
        repo_path = str(Path.cwd().resolve())

        with closing(self._conn()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if self._bootstrap_closed_at(conn) is not None or self.has_enabled_primary(conn=conn):
                    raise RuntimeError("s7_bootstrap_closed")
                if self._active_intent_count(conn, now=now):
                    raise RuntimeError("s7_bootstrap_active_intent_exists")
                token_hash = self._hash_token(raw_token, conn)
                audit_ref = self._audit(
                    "bootstrap_intent_created",
                    {
                        "intent_id": intent_id,
                        "purpose": purpose,
                        "issued_at": issued_at,
                        "expires_at": expires_at,
                        "issuer_uid": effective_uid,
                    },
                )
                conn.execute(
                    """
                    INSERT INTO s7_bootstrap_intents(
                        intent_id, token_hash, purpose, issued_at, expires_at,
                        consumed_at, revoked_at, issuer_uid, store_owner_uid,
                        repo_path, issuer_tty_fingerprint, audit_ref
                    ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
                    """,
                    (
                        intent_id,
                        token_hash,
                        purpose,
                        issued_at,
                        expires_at,
                        effective_uid,
                        store_owner_uid,
                        repo_path,
                        tty_fingerprint,
                        audit_ref,
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return CreatedBootstrapIntent(
            intent_id=intent_id,
            raw_token=raw_token,
            purpose=purpose,
            expires_at=expires_at,
            audit_ref=audit_ref,
        )

    def revoke_bootstrap_intent(self, intent_id: str, *, now: str, effective_uid: int) -> None:
        store_owner_uid = self.root.stat().st_uid
        if effective_uid != store_owner_uid:
            raise RuntimeError("s7_bootstrap_uid_mismatch")
        with closing(self._conn()) as conn:
            conn.execute(
                """
                UPDATE s7_bootstrap_intents
                SET revoked_at = ?
                WHERE intent_id = ?
                  AND consumed_at IS NULL
                  AND revoked_at IS NULL
                """,
                (now, intent_id),
            )
        self._audit("bootstrap_intent_revoked", {"intent_id": intent_id, "revoked_at": now})

    def consume_for_first_primary(
        self,
        *,
        intent_id: str,
        raw_token: str,
        credential_ref: str,
        public_key: str,
        now: str,
    ) -> dict[str, Any]:
        with closing(self._conn()) as conn:
            token_hash = self._hash_token(raw_token, conn)
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    UPDATE s7_bootstrap_intents
                    SET consumed_at = ?
                    WHERE intent_id = ?
                      AND purpose = 'register_primary'
                      AND token_hash = ?
                      AND consumed_at IS NULL
                      AND revoked_at IS NULL
                      AND expires_at > ?
                      AND NOT EXISTS (
                          SELECT 1 FROM s7_founder_webauthn_credentials
                          WHERE credential_kind = 'primary' AND enabled = 1
                      )
                    """,
                    (now, intent_id, token_hash, now),
                )
                if conn.total_changes < 1:
                    conn.execute("ROLLBACK")
                    return {"ok": False, "error": "s7_bootstrap_invalid"}
                conn.execute(
                    """
                    INSERT INTO s7_founder_webauthn_credentials(
                        credential_ref, public_key, credential_kind, enabled, created_at
                    ) VALUES (?, ?, 'primary', 1, ?)
                    """,
                    (credential_ref, public_key, now),
                )
                conn.execute(
                    """
                    UPDATE s7_bootstrap_intents
                    SET revoked_at = ?
                    WHERE intent_id != ?
                      AND consumed_at IS NULL
                      AND revoked_at IS NULL
                    """,
                    (now, intent_id),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO s7_ceremony_metadata(key, value) VALUES (?, ?)",
                    ("bootstrap_closed_at", now),
                )
                conn.execute("COMMIT")
            except sqlite3.Error:
                conn.execute("ROLLBACK")
                raise
        self._audit(
            "first_primary_registered",
            {"intent_id": intent_id, "credential_ref": credential_ref, "created_at": now},
        )
        return {"ok": True, "credential_ref": credential_ref}

    def has_enabled_primary(self, *, conn: sqlite3.Connection | None = None) -> bool:
        owns_conn = conn is None
        conn = self._conn() if conn is None else conn
        try:
            row = conn.execute(
                """
                SELECT 1 FROM s7_founder_webauthn_credentials
                WHERE credential_kind = 'primary' AND enabled = 1
                LIMIT 1
                """
            ).fetchone()
            return row is not None
        finally:
            if owns_conn:
                conn.close()

    def _active_intent_count(self, conn: sqlite3.Connection, *, now: str) -> int:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM s7_bootstrap_intents
            WHERE consumed_at IS NULL
              AND revoked_at IS NULL
              AND expires_at > ?
            """,
            (now,),
        ).fetchone()
        return int(row[0])

    def _bootstrap_closed_at(self, conn: sqlite3.Connection) -> str | None:
        row = conn.execute(
            "SELECT value FROM s7_ceremony_metadata WHERE key = ?",
            ("bootstrap_closed_at",),
        ).fetchone()
        return None if row is None else str(row["value"])


def _fingerprint(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _add_minutes(value: str, minutes: int) -> str:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(minutes=minutes)).isoformat()


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create S7.1 WebAuthn bootstrap intent")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--purpose", required=True, choices=("register_primary",))
    create.add_argument("--ttl-minutes", type=int, default=10)
    create.add_argument("--store-root", default=str(DEFAULT_STORE_ROOT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)
    if args.command == "create":
        now = datetime.now(timezone.utc).isoformat()
        store = S7WebAuthnBootstrapStore(args.store_root)
        intent = store.create_bootstrap_intent(
            purpose=args.purpose,
            ttl_minutes=args.ttl_minutes,
            now=now,
        )
        print("S7.1 first-credential bootstrap token")
        print("Warning: this is a bearer secret visible to the terminal under S7 L1.")
        print(intent.raw_token)
        print(f"Expires at: {intent.expires_at}")
        return 0
    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
