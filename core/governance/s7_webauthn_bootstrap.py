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
from dataclasses import asdict, dataclass
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


from core.infra import paths as _paths

# Path resolution only. Anchors the default store root under paths.home()
# instead of the process CWD (shadow-store prevention). This does NOT change
# S7 arming, any gate, the human-gate invariant, or when/whether the store
# directory is created — the store is still only materialized inside
# S7WebAuthnBootstrapStore on a deliberate ceremony, exactly as before.
DEFAULT_STORE_ROOT = _paths.memory_dir() / "s7_1_webauthn"
# A founder-key enrollment intent is the most sensitive time-box in S7:
# mint it, move to the cockpit, and touch the key within minutes. It must
# not become a day-long open door.
DEFAULT_BOOTSTRAP_TTL_MINUTES = 5
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
    actor_handle_hmac TEXT NOT NULL DEFAULT '',
    role_names_json TEXT NOT NULL DEFAULT '[]',
    public_key TEXT NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    rp_id TEXT NOT NULL DEFAULT 'localhost',
    origin TEXT NOT NULL DEFAULT 'http://localhost:11437',
    credential_kind TEXT NOT NULL,
    backup_credential INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL,
    ceremony_kind TEXT NOT NULL DEFAULT 'founder_local_webauthn',
    label TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    disabled_at TEXT,
    disabled_by_authorization_id TEXT,
    reenabled_by_authorization_id TEXT,
    registration_challenge_id TEXT NOT NULL DEFAULT '',
    attestation_format TEXT,
    aaguid TEXT,
    authenticator_attachment TEXT,
    backup_eligible INTEGER,
    backed_up INTEGER,
    transports_json TEXT NOT NULL DEFAULT '[]',
    library_name TEXT NOT NULL DEFAULT '',
    library_version TEXT NOT NULL DEFAULT '',
    sign_count_mode TEXT NOT NULL DEFAULT 'unknown',
    uv_capable INTEGER,
    uv_required_for_guarded INTEGER NOT NULL DEFAULT 1,
    distinct_device_confidence TEXT NOT NULL DEFAULT 'unknown',
    record_hash TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS s7_ceremony_challenges (
    challenge_id TEXT PRIMARY KEY,
    challenge_kind TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    invalidated_at TEXT,
    challenge_hash TEXT NOT NULL DEFAULT '',
    challenge_b64 TEXT NOT NULL DEFAULT '',
    rp_id TEXT NOT NULL DEFAULT 'localhost',
    origin TEXT NOT NULL DEFAULT 'http://localhost:11437',
    host TEXT NOT NULL DEFAULT 'localhost:11437',
    session_binding_hash TEXT NOT NULL DEFAULT '',
    internal_channel_binding_hash TEXT,
    request_id TEXT,
    uv_required INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT '',
    request_envelope_hash TEXT NOT NULL DEFAULT '',
    rendered_text_hash TEXT NOT NULL DEFAULT '',
    action_params_hash TEXT NOT NULL DEFAULT '',
    precondition_hash TEXT NOT NULL DEFAULT '',
    authority_context_hash TEXT NOT NULL DEFAULT '',
    maez_voice_consultation_hash TEXT,
    derived_aggregation_group TEXT NOT NULL DEFAULT '',
    nonce TEXT NOT NULL DEFAULT '',
    consultation_exemption_projection_hash TEXT,
    covenant_phase2_of TEXT,
    covenant_salt_b64 TEXT
);

CREATE TABLE IF NOT EXISTS s7_refusal_history (
    record_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    request_envelope_hash TEXT NOT NULL,
    derived_work_class TEXT NOT NULL,
    derived_aggregation_group TEXT NOT NULL,
    affected_refs_json TEXT NOT NULL,
    proposed_change_class TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    requester_ref TEXT NOT NULL,
    denial_reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    dialog_id TEXT,
    outcome TEXT NOT NULL DEFAULT 'refused'
);
"""


@dataclass(frozen=True)
class CreatedBootstrapIntent:
    intent_id: str
    raw_token: str
    purpose: str
    expires_at: str
    audit_ref: str


@dataclass(frozen=True)
class FounderWebAuthnCredentialRecord:
    """S7.1 extension of the sealed S7 WebAuthn credential record."""

    credential_ref: str
    actor_handle_hmac: str
    role_names: tuple[str, ...]
    public_key: str
    sign_count: int
    rp_id: str
    origin: str
    created_at: str
    backup_credential: bool
    enabled: bool
    ceremony_kind: str
    credential_kind: str
    label: str
    last_used_at: str | None
    disabled_at: str | None
    disabled_by_authorization_id: str | None
    reenabled_by_authorization_id: str | None
    registration_challenge_id: str
    attestation_format: str | None
    aaguid: str | None
    authenticator_attachment: str | None
    backup_eligible: bool | None
    backed_up: bool | None
    transports: tuple[str, ...]
    library_name: str
    library_version: str
    sign_count_mode: str
    uv_capable: bool | None
    uv_required_for_guarded: bool
    distinct_device_confidence: str
    record_hash: str

    @classmethod
    def build(cls, **kwargs: Any) -> "FounderWebAuthnCredentialRecord":
        payload = dict(kwargs)
        payload.setdefault("ceremony_kind", "founder_local_webauthn")
        payload.setdefault("last_used_at", None)
        payload.setdefault("disabled_at", None)
        payload.setdefault("disabled_by_authorization_id", None)
        payload.setdefault("reenabled_by_authorization_id", None)
        payload["record_hash"] = ""
        record = cls(**payload)
        return cls(**{**asdict(record), "record_hash": _credential_record_hash(record)})

    def __post_init__(self) -> None:
        if not self.credential_ref:
            raise ValueError("s7_credential_ref_required")
        if not self.actor_handle_hmac.startswith("hmac:s7:") or len(
            self.actor_handle_hmac.rsplit(":", 1)[-1]
        ) != 64:
            raise ValueError("s7_actor_handle_hmac_required")
        if "bonded_user" not in self.role_names:
            raise ValueError("s7_founder_credential_requires_bonded_user_role")
        if not self.public_key:
            raise ValueError("s7_public_key_required")
        if not isinstance(self.sign_count, int) or self.sign_count < 0:
            raise ValueError("s7_sign_count_invalid")
        if self.rp_id != "localhost" or self.origin != "http://localhost:11437":
            raise ValueError("s7_origin_binding_invalid")
        _parse_time(self.created_at)
        for value in (self.last_used_at, self.disabled_at):
            if value is not None:
                _parse_time(value)
        if self.backup_credential is not True and self.backup_credential is not False:
            raise ValueError("s7_backup_credential_bool_required")
        if self.enabled is not True and self.enabled is not False:
            raise ValueError("s7_enabled_bool_required")
        if self.ceremony_kind != "founder_local_webauthn":
            raise ValueError("s7_ceremony_kind_invalid")
        if self.credential_kind not in {"primary", "backup"}:
            raise ValueError("s7_credential_kind_invalid")
        if self.backup_credential != (self.credential_kind == "backup"):
            raise ValueError("s7_backup_credential_kind_mismatch")
        if not self.label:
            raise ValueError("s7_credential_label_required")
        if not self.registration_challenge_id:
            raise ValueError("s7_registration_challenge_id_required")
        if self.sign_count_mode not in {"advancing", "constant_zero", "unknown"}:
            raise ValueError("s7_sign_count_mode_invalid")
        if self.uv_required_for_guarded is not True and self.uv_required_for_guarded is not False:
            raise ValueError("s7_uv_required_bool_required")
        if self.distinct_device_confidence not in {
            "confirmed_distinct",
            "same_device_override",
            "unknown",
        }:
            raise ValueError("s7_distinct_device_confidence_invalid")


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
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO s7_ceremony_metadata(key, value) VALUES (?, ?)",
                ("bootstrap_hmac_key", secrets.token_hex(32)),
            )
            self._migrate_credential_columns(conn)
            conn.commit()
        os.chmod(self.db_path, 0o600)

    def _migrate_credential_columns(self, conn: sqlite3.Connection) -> None:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(s7_founder_webauthn_credentials)")
        }
        desired = {
            "actor_handle_hmac": "TEXT NOT NULL DEFAULT ''",
            "role_names_json": "TEXT NOT NULL DEFAULT '[]'",
            "sign_count": "INTEGER NOT NULL DEFAULT 0",
            "rp_id": "TEXT NOT NULL DEFAULT 'localhost'",
            "origin": "TEXT NOT NULL DEFAULT 'http://localhost:11437'",
            "backup_credential": "INTEGER NOT NULL DEFAULT 0",
            "ceremony_kind": "TEXT NOT NULL DEFAULT 'founder_local_webauthn'",
            "label": "TEXT NOT NULL DEFAULT ''",
            "last_used_at": "TEXT",
            "disabled_at": "TEXT",
            "disabled_by_authorization_id": "TEXT",
            "reenabled_by_authorization_id": "TEXT",
            "registration_challenge_id": "TEXT NOT NULL DEFAULT ''",
            "attestation_format": "TEXT",
            "aaguid": "TEXT",
            "authenticator_attachment": "TEXT",
            "backup_eligible": "INTEGER",
            "backed_up": "INTEGER",
            "transports_json": "TEXT NOT NULL DEFAULT '[]'",
            "library_name": "TEXT NOT NULL DEFAULT ''",
            "library_version": "TEXT NOT NULL DEFAULT ''",
            "sign_count_mode": "TEXT NOT NULL DEFAULT 'unknown'",
            "uv_capable": "INTEGER",
            "uv_required_for_guarded": "INTEGER NOT NULL DEFAULT 1",
            "distinct_device_confidence": "TEXT NOT NULL DEFAULT 'unknown'",
            "record_hash": "TEXT NOT NULL DEFAULT ''",
        }
        for column, ddl in desired.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE s7_founder_webauthn_credentials ADD COLUMN {column} {ddl}")
        challenge_existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(s7_ceremony_challenges)")
        }
        challenge_desired = {
            "challenge_hash": "TEXT NOT NULL DEFAULT ''",
            "challenge_b64": "TEXT NOT NULL DEFAULT ''",
            "rp_id": "TEXT NOT NULL DEFAULT 'localhost'",
            "origin": "TEXT NOT NULL DEFAULT 'http://localhost:11437'",
            "host": "TEXT NOT NULL DEFAULT 'localhost:11437'",
            "session_binding_hash": "TEXT NOT NULL DEFAULT ''",
            "internal_channel_binding_hash": "TEXT",
            "request_id": "TEXT",
            "uv_required": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "request_envelope_hash": "TEXT NOT NULL DEFAULT ''",
            "rendered_text_hash": "TEXT NOT NULL DEFAULT ''",
            "action_params_hash": "TEXT NOT NULL DEFAULT ''",
            "precondition_hash": "TEXT NOT NULL DEFAULT ''",
            "authority_context_hash": "TEXT NOT NULL DEFAULT ''",
            "maez_voice_consultation_hash": "TEXT",
            "derived_aggregation_group": "TEXT NOT NULL DEFAULT ''",
            "nonce": "TEXT NOT NULL DEFAULT ''",
            "covenant_phase2_of": "TEXT",
            "covenant_salt_b64": "TEXT",
        }
        for column, ddl in challenge_desired.items():
            if column not in challenge_existing:
                conn.execute(f"ALTER TABLE s7_ceremony_challenges ADD COLUMN {column} {ddl}")
        history_existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(s7_refusal_history)")
        }
        if "outcome" not in history_existing:
            conn.execute(
                "ALTER TABLE s7_refusal_history "
                "ADD COLUMN outcome TEXT NOT NULL DEFAULT 'refused'"
            )

    def _ensure_audit_file(self) -> None:
        self.audit_path.touch(exist_ok=True)
        os.chmod(self.audit_path, 0o600)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn  # sqlite-raw-ok: pass-or-create handle; callers track owns_conn and close in finally

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
        sign_count: int = 0,
        attestation_format: str | None = None,
        aaguid: str | None = None,
        authenticator_attachment: str | None = None,
        backup_eligible: bool | None = None,
        backed_up: bool | None = None,
        transports: tuple[str, ...] = (),
        library_name: str = "bootstrap-placeholder",
        library_version: str = "0",
        sign_count_mode: str = "unknown",
        uv_capable: bool | None = None,
    ) -> dict[str, Any]:
        with closing(self._conn()) as conn:
            token_hash = self._hash_token(raw_token, conn)
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
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
                if cur.rowcount != 1:
                    conn.execute("ROLLBACK")
                    return {"ok": False, "error": "s7_bootstrap_invalid"}
                record = FounderWebAuthnCredentialRecord.build(
                    credential_ref=credential_ref,
                    actor_handle_hmac="hmac:s7:founder:" + ("0" * 64),
                    role_names=("bonded_user",),
                    public_key=public_key,
                    sign_count=sign_count,
                    rp_id="localhost",
                    origin="http://localhost:11437",
                    created_at=now,
                    backup_credential=False,
                    enabled=True,
                    credential_kind="primary",
                    label="Primary founder key",
                    registration_challenge_id=f"bootstrap:{intent_id}",
                    attestation_format=attestation_format,
                    aaguid=aaguid,
                    authenticator_attachment=authenticator_attachment,
                    backup_eligible=backup_eligible,
                    backed_up=backed_up,
                    transports=transports,
                    library_name=library_name,
                    library_version=library_version,
                    sign_count_mode=sign_count_mode,
                    uv_capable=uv_capable,
                    uv_required_for_guarded=True,
                    distinct_device_confidence="unknown",
                )
                conn.execute(
                    """
                    INSERT INTO s7_founder_webauthn_credentials(
                        credential_ref, actor_handle_hmac, role_names_json,
                        public_key, sign_count, rp_id, origin, credential_kind,
                        backup_credential, enabled, ceremony_kind, label, created_at,
                        last_used_at, disabled_at, disabled_by_authorization_id,
                        reenabled_by_authorization_id, registration_challenge_id,
                        attestation_format, aaguid, authenticator_attachment,
                        backup_eligible, backed_up, transports_json, library_name,
                        library_version, sign_count_mode, uv_capable,
                        uv_required_for_guarded, distinct_device_confidence, record_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _credential_row_values(record),
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

    def bootstrap_intent_valid(
        self,
        *,
        intent_id: str,
        raw_token: str,
        now: str,
    ) -> bool:
        now_text = _parse_time(now).isoformat()
        with closing(self._conn()) as conn:
            token_hash = self._hash_token(raw_token, conn)
            row = conn.execute(
                """
                SELECT 1 FROM s7_bootstrap_intents
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
                LIMIT 1
                """,
                (intent_id, token_hash, now_text),
            ).fetchone()
        return row is not None

    def store_credential(self, record: FounderWebAuthnCredentialRecord) -> None:
        record = _with_current_record_hash(record)
        with closing(self._conn()) as conn:
            exists = conn.execute(
                "SELECT 1 FROM s7_founder_webauthn_credentials WHERE credential_ref = ?",
                (record.credential_ref,),
            ).fetchone()
            if exists is not None:
                raise ValueError("s7_credential_duplicate")
            conn.execute(
                """
                INSERT INTO s7_founder_webauthn_credentials(
                    credential_ref, actor_handle_hmac, role_names_json,
                    public_key, sign_count, rp_id, origin, credential_kind,
                    backup_credential, enabled, ceremony_kind, label, created_at,
                    last_used_at, disabled_at, disabled_by_authorization_id,
                    reenabled_by_authorization_id, registration_challenge_id,
                    attestation_format, aaguid, authenticator_attachment,
                    backup_eligible, backed_up, transports_json, library_name,
                    library_version, sign_count_mode, uv_capable,
                    uv_required_for_guarded, distinct_device_confidence, record_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _credential_row_values(record),
            )

    def get_credential(self, credential_ref: str) -> FounderWebAuthnCredentialRecord | None:
        if not self.db_path.exists():
            return None
        with closing(self._conn()) as conn:
            row = conn.execute(
                """
                SELECT credential_ref, actor_handle_hmac, role_names_json,
                       public_key, sign_count, rp_id, origin, credential_kind,
                       backup_credential, enabled, ceremony_kind, label, created_at,
                       last_used_at, disabled_at, disabled_by_authorization_id,
                       reenabled_by_authorization_id, registration_challenge_id,
                       attestation_format, aaguid, authenticator_attachment,
                       backup_eligible, backed_up, transports_json, library_name,
                       library_version, sign_count_mode, uv_capable,
                       uv_required_for_guarded, distinct_device_confidence, record_hash
                FROM s7_founder_webauthn_credentials
                WHERE credential_ref = ?
                """,
                (credential_ref,),
            ).fetchone()
        if row is None:
            return None
        record = _credential_record_from_row(row)
        if record.record_hash != _credential_record_hash(record):
            raise RuntimeError("s7_record_hash_mismatch")
        return record

    def list_credentials(self) -> tuple[FounderWebAuthnCredentialRecord, ...]:
        if not self.db_path.exists():
            return ()
        with closing(self._conn()) as conn:
            rows = conn.execute(
                """
                SELECT credential_ref
                FROM s7_founder_webauthn_credentials
                ORDER BY credential_ref
                """
            ).fetchall()
        return tuple(
            record
            for ref in rows
            for record in (self.get_credential(str(ref["credential_ref"])),)
            if record is not None
        )

    def exclude_credentials_for_backup_registration(self) -> tuple[str, ...]:
        return tuple(
            record.credential_ref
            for record in self.list_credentials()
            if record.enabled
        )

    def allow_credentials_for_authorization(self) -> tuple[str, ...]:
        return tuple(
            record.credential_ref
            for record in self.list_credentials()
            if record.enabled and "bonded_user" in record.role_names
        )

    def credential_can_authorize(self, credential_ref: str) -> bool:
        record = self.get_credential(credential_ref)
        return bool(record and record.enabled and "bonded_user" in record.role_names)

    def advance_sign_count(
        self,
        credential_ref: str,
        *,
        new_sign_count: int,
        now: str,
    ) -> dict[str, Any]:
        _parse_time(now)
        record = self.get_credential(credential_ref)
        if record is None or not record.enabled:
            return {"ok": False, "error": "s7_credential_disabled"}
        if new_sign_count > record.sign_count:
            sign_count_mode = "advancing"
        elif new_sign_count == 0 and record.sign_count == 0:
            sign_count_mode = "constant_zero"
        else:
            return {"ok": False, "error": "s7_clone_suspected"}
        with closing(self._conn()) as conn:
            cur = conn.execute(
                """
                UPDATE s7_founder_webauthn_credentials
                SET sign_count = ?,
                    sign_count_mode = ?,
                    last_used_at = ?,
                    record_hash = ''
                WHERE credential_ref = ?
                  AND enabled = 1
                """,
                (new_sign_count, sign_count_mode, now, credential_ref),
            )
            if cur.rowcount != 1:
                return {"ok": False, "error": "s7_credential_disabled"}
        updated = self.get_credential_without_hash_check(credential_ref)
        if updated is None:
            return {"ok": False, "error": "s7_credential_disabled"}
        self._update_record_hash(_with_current_record_hash(updated))
        return {
            "ok": True,
            "credential_ref": credential_ref,
            "sign_count": new_sign_count,
            "sign_count_mode": sign_count_mode,
        }

    def disable_credential(
        self,
        credential_ref: str,
        *,
        authorization_id: str,
        now: str,
    ) -> dict[str, Any]:
        _parse_time(now)
        if not credential_ref:
            return {"ok": False, "error": "s7_credential_setup_incomplete"}
        if not authorization_id:
            return {"ok": False, "error": "s7_authorization_required"}
        with closing(self._conn()) as conn:
            cur = conn.execute(
                """
                UPDATE s7_founder_webauthn_credentials
                SET enabled = 0,
                    disabled_at = ?,
                    disabled_by_authorization_id = ?,
                    record_hash = ''
                WHERE credential_ref = ?
                  AND enabled = 1
                """,
                (now, authorization_id, credential_ref),
            )
            if cur.rowcount != 1:
                return {"ok": False, "error": "s7_credential_setup_incomplete"}
        record = self.get_credential_without_hash_check(credential_ref)
        if record is None:
            return {"ok": False, "error": "s7_credential_setup_incomplete"}
        self._update_record_hash(_with_current_record_hash(record))
        self._audit(
            "credential_disabled",
            {
                "credential_ref": credential_ref,
                "authorization_id": authorization_id,
                "disabled_at": now,
            },
        )
        return {"ok": True, "credential_ref": credential_ref}

    def reenable_credential(
        self,
        credential_ref: str,
        *,
        authorization_id: str,
        now: str,
    ) -> dict[str, Any]:
        _parse_time(now)
        enabled = tuple(
            record
            for record in self.list_credentials()
            if record.enabled and record.credential_ref != credential_ref and "bonded_user" in record.role_names
        )
        if not enabled:
            return {"ok": False, "error": "s7_credential_setup_incomplete"}
        with closing(self._conn()) as conn:
            cur = conn.execute(
                """
                UPDATE s7_founder_webauthn_credentials
                SET enabled = 1,
                    disabled_at = NULL,
                    reenabled_by_authorization_id = ?,
                    record_hash = ''
                WHERE credential_ref = ?
                  AND enabled = 0
                """,
                (authorization_id, credential_ref),
            )
            if cur.rowcount != 1:
                return {"ok": False, "error": "s7_credential_setup_incomplete"}
        record = self.get_credential_without_hash_check(credential_ref)
        if record is None:
            return {"ok": False, "error": "s7_credential_setup_incomplete"}
        self._update_record_hash(_with_current_record_hash(record))
        return {"ok": True, "credential_ref": credential_ref}

    def credential_recovery_state(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return _manual_recovery_state("registry_missing")
        try:
            records = self.list_credentials()
        except (sqlite3.Error, RuntimeError, ValueError):
            return _manual_recovery_state("registry_invalid")
        active = tuple(record for record in records if record.enabled and "bonded_user" in record.role_names)
        primary = tuple(record for record in active if record.credential_kind == "primary")
        backup = tuple(record for record in active if record.credential_kind == "backup")
        if not active:
            with closing(self._conn()) as conn:
                bootstrap_closed_at = self._bootstrap_closed_at(conn)
            ever_primary = any(record.credential_kind == "primary" for record in records)
            ever_backup = any(record.credential_kind == "backup" for record in records)
            if not records and bootstrap_closed_at is None:
                return _manual_recovery_state("first_setup_not_started")
            if bootstrap_closed_at is not None and ever_primary and ever_backup:
                return _manual_recovery_state("both_keys_lost")
            return _manual_recovery_state("no_enabled_founder_credential")
        confidence = _aggregate_distinct_device_confidence(backup)
        if not primary or not backup or confidence != "confirmed_distinct":
            return {
                "mode": "degraded",
                "manual_recovery_required": False,
                "manual_recovery_cause": None,
                "active_credential_count": len(active),
                "primary_credential_state": "enabled" if primary else "missing",
                "backup_credential_state": "enabled" if backup else "missing",
                "distinct_device_confidence": confidence,
            }
        return {
            "mode": "ready",
            "manual_recovery_required": False,
            "manual_recovery_cause": None,
            "active_credential_count": len(active),
            "primary_credential_state": "enabled",
            "backup_credential_state": "enabled",
            "distinct_device_confidence": "confirmed_distinct",
        }

    def create_challenge(self, *, challenge_id: str, challenge_kind: str, expires_at: str) -> None:
        _parse_time(expires_at)
        with closing(self._conn()) as conn:
            conn.execute(
                """
                INSERT INTO s7_ceremony_challenges(
                    challenge_id, challenge_kind, expires_at, consumed_at, invalidated_at
                ) VALUES (?, ?, ?, NULL, NULL)
                """,
                (challenge_id, challenge_kind, expires_at),
            )

    def create_registration_challenge(
        self,
        *,
        challenge_kind: str,
        session_binding: str,
        now: str,
        expires_at: str,
        internal_channel_binding: str | None = None,
    ) -> dict[str, Any]:
        _parse_time(now)
        _parse_time(expires_at)
        if challenge_kind not in {"register_primary", "register_backup"}:
            raise ValueError("s7_challenge_kind_invalid")
        challenge_id = f"s7reg_{uuid.uuid4().hex}"
        challenge_b64 = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
        session_binding_hash = _fingerprint(session_binding)
        internal_channel_binding_hash = (
            _fingerprint(internal_channel_binding) if internal_channel_binding else None
        )
        challenge_hash = _fingerprint(
            "|".join(
                (
                    challenge_id,
                    challenge_kind,
                    challenge_b64,
                    "localhost",
                    "http://localhost:11437",
                    "localhost:11437",
                    session_binding_hash,
                    internal_channel_binding_hash or "",
                    now,
                    expires_at,
                )
            )
        )
        with closing(self._conn()) as conn:
            conn.execute(
                """
                INSERT INTO s7_ceremony_challenges(
                    challenge_id, challenge_kind, expires_at, consumed_at, invalidated_at,
                    challenge_hash, challenge_b64, rp_id, origin, host, session_binding_hash,
                    internal_channel_binding_hash, request_id, uv_required, created_at
                ) VALUES (?, ?, ?, NULL, NULL, ?, ?, 'localhost', 'http://localhost:11437',
                          'localhost:11437', ?, ?, NULL, 0, ?)
                """,
                (
                    challenge_id,
                    challenge_kind,
                    expires_at,
                    challenge_hash,
                    challenge_b64,
                    session_binding_hash,
                    internal_channel_binding_hash,
                    now,
                ),
            )
        return {
            "challenge_id": challenge_id,
            "challenge_kind": challenge_kind,
            "challenge_hash": challenge_hash,
            "challenge_b64": challenge_b64,
            "rp_id": "localhost",
            "origin": "http://localhost:11437",
            "host": "localhost:11437",
            "session_binding_hash": session_binding_hash,
            "expires_at": expires_at,
        }

    def create_authorization_challenge(
        self,
        *,
        rendered_statement: Any,
        precondition_hash: str,
        session_binding: str,
        internal_channel_binding: str,
        now: str,
        expires_at: str,
        uv_required: bool,
        consultation_exemption_projection_hash: str | None = None,
        covenant_phase2_of: str | None = None,
    ) -> dict[str, Any]:
        _parse_time(now)
        _parse_time(expires_at)
        _validate_hash64_text(precondition_hash, field="precondition_hash")
        if covenant_phase2_of is not None:
            # The phase-2 stamp: binds this challenge to the sealed phase-1
            # row it confirms. Null for every non-covenant ceremony, so the
            # column is inert on all existing paths.
            _validate_hash64_text(covenant_phase2_of, field="covenant_phase2_of")
        if consultation_exemption_projection_hash is not None:
            _validate_hash64_text(
                consultation_exemption_projection_hash,
                field="consultation_exemption_projection_hash",
            )
        if (
            rendered_statement.maez_voice_consultation_hash is not None
            and consultation_exemption_projection_hash is not None
        ):
            raise ValueError(
                "authorization challenge carries both voice and R11 evidence"
            )
        challenge_id = f"s7auth_{uuid.uuid4().hex}"
        challenge_b64 = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
        session_binding_hash = _fingerprint(session_binding)
        internal_channel_binding_hash = _fingerprint(internal_channel_binding)
        d12_parts = (
            str(rendered_statement.request_id),
            str(rendered_statement.request_envelope_hash),
            str(rendered_statement.rendered_text_hash),
            str(rendered_statement.action_params_hash),
            precondition_hash,
            str(rendered_statement.authority_context_hash),
            str(rendered_statement.maez_voice_consultation_hash or ""),
            str(consultation_exemption_projection_hash or ""),
            str(covenant_phase2_of or ""),
            str(rendered_statement.derived_aggregation_group),
            str(rendered_statement.nonce),
        )
        challenge_hash = _fingerprint(
            "|".join(
                (
                    challenge_id,
                    "authorize_guarded_request",
                    challenge_b64,
                    "localhost",
                    "http://localhost:11437",
                    "localhost:11437",
                    session_binding_hash,
                    internal_channel_binding_hash,
                    *d12_parts,
                    now,
                    expires_at,
                )
            )
        )
        with closing(self._conn()) as conn:
            conn.execute(
                """
                INSERT INTO s7_ceremony_challenges(
                    challenge_id, challenge_kind, expires_at, consumed_at, invalidated_at,
                    challenge_hash, challenge_b64, rp_id, origin, host, session_binding_hash,
                    internal_channel_binding_hash, request_id, uv_required, created_at,
                    request_envelope_hash, rendered_text_hash, action_params_hash,
                    precondition_hash, authority_context_hash, maez_voice_consultation_hash,
                    consultation_exemption_projection_hash,
                    derived_aggregation_group, nonce, covenant_phase2_of
                ) VALUES (?, 'authorize_guarded_request', ?, NULL, NULL, ?, ?,
                          'localhost', 'http://localhost:11437', 'localhost:11437',
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    challenge_id,
                    expires_at,
                    challenge_hash,
                    challenge_b64,
                    session_binding_hash,
                    internal_channel_binding_hash,
                    rendered_statement.request_id,
                    1 if uv_required else 0,
                    now,
                    rendered_statement.request_envelope_hash,
                    rendered_statement.rendered_text_hash,
                    rendered_statement.action_params_hash,
                    precondition_hash,
                    rendered_statement.authority_context_hash,
                    rendered_statement.maez_voice_consultation_hash,
                    consultation_exemption_projection_hash,
                    rendered_statement.derived_aggregation_group,
                    rendered_statement.nonce,
                    covenant_phase2_of,
                ),
            )
        return {
            "challenge_id": challenge_id,
            "challenge_kind": "authorize_guarded_request",
            "challenge_hash": challenge_hash,
            "challenge_b64": challenge_b64,
            "rp_id": "localhost",
            "origin": "http://localhost:11437",
            "host": "localhost:11437",
            "request_id": rendered_statement.request_id,
            "request_envelope_hash": rendered_statement.request_envelope_hash,
            "rendered_text_hash": rendered_statement.rendered_text_hash,
            "action_params_hash": rendered_statement.action_params_hash,
            "precondition_hash": precondition_hash,
            "authority_context_hash": rendered_statement.authority_context_hash,
            "maez_voice_consultation_hash": rendered_statement.maez_voice_consultation_hash,
            "consultation_exemption_projection_hash": (
                consultation_exemption_projection_hash
            ),
            "derived_aggregation_group": rendered_statement.derived_aggregation_group,
            "nonce": rendered_statement.nonce,
            "session_binding_hash": session_binding_hash,
            "internal_channel_binding_hash": internal_channel_binding_hash,
            "uv_required": uv_required,
            "expires_at": expires_at,
        }

    def create_covenant_first_challenge(
        self,
        *,
        rendered_statement: Any,
        precondition_hash: str,
        session_binding: str,
        internal_channel_binding: str,
        now: str,
        expires_at: str,
    ) -> dict[str, Any]:
        """Phase 1 of the covenant ceremony: a challenge bound to the same
        D12 statement fields as an authorize challenge, under its own kind.
        Its finish writes ONLY a sealed phase row -- no authority."""
        _parse_time(now)
        _parse_time(expires_at)
        _validate_hash64_text(precondition_hash, field="precondition_hash")
        challenge_id = f"s7cov1_{uuid.uuid4().hex}"
        # RULING C: the owner must not tap on a false picture. The challenge
        # bytes ARE a commitment to the approved notice and the rendered
        # statement, so the authenticator's signature covers both. Finish
        # recomputes this before verification. (The 2b Construction-4 device,
        # applied to this new challenge kind.)
        from core.governance.s7_covenant_ceremony import COVENANT_PHASE1_NOTICE

        covenant_salt = secrets.token_bytes(32)
        commitment = hashlib.sha256(
            covenant_salt
            + hashlib.sha256(COVENANT_PHASE1_NOTICE.encode("utf-8")).digest()
            + bytes.fromhex(str(rendered_statement.rendered_text_hash))
        ).digest()
        challenge_b64 = base64.urlsafe_b64encode(commitment).decode("ascii").rstrip("=")
        covenant_salt_b64 = base64.urlsafe_b64encode(covenant_salt).decode("ascii").rstrip("=")
        session_binding_hash = _fingerprint(session_binding)
        internal_channel_binding_hash = _fingerprint(internal_channel_binding)
        challenge_hash = _fingerprint(
            "|".join((
                challenge_id, "covenant_first_confirmation", challenge_b64,
                "localhost", "http://localhost:11437", "localhost:11437",
                session_binding_hash, internal_channel_binding_hash,
                str(rendered_statement.request_id),
                str(rendered_statement.request_envelope_hash),
                str(rendered_statement.rendered_text_hash),
                str(rendered_statement.action_params_hash),
                precondition_hash,
                str(rendered_statement.authority_context_hash),
                str(rendered_statement.derived_aggregation_group),
                str(rendered_statement.nonce),
                now, expires_at,
            ))
        )
        with closing(self._conn()) as conn:
            conn.execute(
                """
                INSERT INTO s7_ceremony_challenges(
                    challenge_id, challenge_kind, expires_at, consumed_at, invalidated_at,
                    challenge_hash, challenge_b64, rp_id, origin, host, session_binding_hash,
                    internal_channel_binding_hash, request_id, uv_required, created_at,
                    request_envelope_hash, rendered_text_hash, action_params_hash,
                    precondition_hash, authority_context_hash,
                    derived_aggregation_group, nonce, covenant_salt_b64
                ) VALUES (?, 'covenant_first_confirmation', ?, NULL, NULL, ?, ?,
                          'localhost', 'http://localhost:11437', 'localhost:11437',
                          ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    challenge_id, expires_at, challenge_hash, challenge_b64,
                    session_binding_hash, internal_channel_binding_hash,
                    rendered_statement.request_id, now,
                    rendered_statement.request_envelope_hash,
                    rendered_statement.rendered_text_hash,
                    rendered_statement.action_params_hash,
                    precondition_hash,
                    rendered_statement.authority_context_hash,
                    rendered_statement.derived_aggregation_group,
                    rendered_statement.nonce,
                    covenant_salt_b64,
                ),
            )
        return {
            "challenge_id": challenge_id,
            "challenge_kind": "covenant_first_confirmation",
            "challenge_hash": challenge_hash,
            "challenge_b64": challenge_b64,
            "expires_at": expires_at,
        }

    def covenant_first_challenge_for_finish(
        self,
        *,
        challenge_id: str,
        session_binding: str,
        internal_channel_binding: str,
        now: str,
    ) -> dict[str, Any] | None:
        now_text = _parse_time(now).isoformat()
        session_binding_hash = _fingerprint(session_binding)
        internal_channel_binding_hash = _fingerprint(internal_channel_binding)
        with closing(self._conn()) as conn:
            row = conn.execute(
                """
                SELECT challenge_id, challenge_kind, challenge_hash, rp_id, origin, host,
                       challenge_b64, session_binding_hash, internal_channel_binding_hash,
                       expires_at, consumed_at, invalidated_at, request_id,
                       request_envelope_hash, rendered_text_hash, action_params_hash,
                       precondition_hash, authority_context_hash,
                       maez_voice_consultation_hash,
                       consultation_exemption_projection_hash,
                       derived_aggregation_group,
                       nonce, uv_required, created_at, covenant_salt_b64
                FROM s7_ceremony_challenges
                WHERE challenge_id = ?
                  AND challenge_kind = 'covenant_first_confirmation'
                  AND session_binding_hash = ?
                  AND internal_channel_binding_hash = ?
                  AND consumed_at IS NULL
                  AND invalidated_at IS NULL
                  AND expires_at > ?
                """,
                (challenge_id, session_binding_hash, internal_channel_binding_hash, now_text),
            ).fetchone()
        return None if row is None else dict(row)

    def authorization_challenge_for_finish(
        self,
        *,
        challenge_id: str,
        session_binding: str,
        internal_channel_binding: str,
        now: str,
    ) -> dict[str, Any] | None:
        now_text = _parse_time(now).isoformat()
        session_binding_hash = _fingerprint(session_binding)
        internal_channel_binding_hash = _fingerprint(internal_channel_binding)
        with closing(self._conn()) as conn:
            row = conn.execute(
                """
                SELECT challenge_id, challenge_kind, challenge_hash, rp_id, origin, host,
                       challenge_b64, session_binding_hash, internal_channel_binding_hash,
                       expires_at, consumed_at, invalidated_at, request_id,
                       request_envelope_hash, rendered_text_hash, action_params_hash,
                       precondition_hash, authority_context_hash,
                       maez_voice_consultation_hash,
                       consultation_exemption_projection_hash,
                       derived_aggregation_group,
                       nonce, uv_required, covenant_phase2_of, created_at
                FROM s7_ceremony_challenges
                WHERE challenge_id = ?
                  AND challenge_kind = 'authorize_guarded_request'
                  AND session_binding_hash = ?
                  AND internal_channel_binding_hash = ?
                  AND consumed_at IS NULL
                  AND invalidated_at IS NULL
                  AND expires_at > ?
                """,
                (challenge_id, session_binding_hash, internal_channel_binding_hash, now_text),
            ).fetchone()
        return None if row is None else dict(row)

    def consumed_authorization_challenge_for_artifact(
        self,
        *,
        challenge_id: str,
        session_binding: str,
        internal_channel_binding: str,
        now: str,
    ) -> dict[str, Any] | None:
        now_text = _parse_time(now).isoformat()
        session_binding_hash = _fingerprint(session_binding)
        internal_channel_binding_hash = _fingerprint(internal_channel_binding)
        with closing(self._conn()) as conn:
            row = conn.execute(
                """
                SELECT challenge_id, challenge_kind, challenge_hash, rp_id, origin, host,
                       challenge_b64, session_binding_hash, internal_channel_binding_hash,
                       expires_at, consumed_at, invalidated_at, request_id,
                       request_envelope_hash, rendered_text_hash, action_params_hash,
                       precondition_hash, authority_context_hash,
                       maez_voice_consultation_hash,
                       consultation_exemption_projection_hash,
                       derived_aggregation_group,
                       nonce, uv_required, covenant_phase2_of, created_at
                FROM s7_ceremony_challenges
                WHERE challenge_id = ?
                  AND challenge_kind = 'authorize_guarded_request'
                  AND session_binding_hash = ?
                  AND internal_channel_binding_hash = ?
                  AND consumed_at IS NOT NULL
                  AND invalidated_at IS NULL
                  AND expires_at > ?
                """,
                (challenge_id, session_binding_hash, internal_channel_binding_hash, now_text),
            ).fetchone()
        return None if row is None else dict(row)

    def registration_challenge_for_finish(
        self,
        *,
        challenge_id: str,
        session_binding: str,
        now: str,
    ) -> dict[str, Any] | None:
        now_text = _parse_time(now).isoformat()
        session_binding_hash = _fingerprint(session_binding)
        with closing(self._conn()) as conn:
            row = conn.execute(
                """
                SELECT challenge_id, challenge_kind, challenge_hash, rp_id, origin, host,
                       challenge_b64, session_binding_hash, expires_at, consumed_at,
                       invalidated_at
                FROM s7_ceremony_challenges
                WHERE challenge_id = ?
                  AND session_binding_hash = ?
                  AND consumed_at IS NULL
                  AND invalidated_at IS NULL
                  AND expires_at > ?
                """,
                (challenge_id, session_binding_hash, now_text),
            ).fetchone()
        return None if row is None else dict(row)

    def registration_challenge_status(
        self,
        *,
        challenge_id: str,
        session_binding: str,
        now: str,
    ) -> str:
        now_text = _parse_time(now).isoformat()
        session_binding_hash = _fingerprint(session_binding)
        with closing(self._conn()) as conn:
            row = conn.execute(
                """
                SELECT session_binding_hash, expires_at, consumed_at, invalidated_at
                FROM s7_ceremony_challenges
                WHERE challenge_id = ?
                """,
                (challenge_id,),
            ).fetchone()
        if row is None:
            return "missing"
        if row["consumed_at"] is not None or row["invalidated_at"] is not None:
            return "replayed"
        if row["expires_at"] <= now_text:
            return "expired"
        if row["session_binding_hash"] != session_binding_hash:
            return "session_mismatch"
        return "active"

    def consume_challenge(
        self,
        challenge_id: str,
        *,
        now: str,
        connection: "sqlite3.Connection | None" = None,
    ) -> bool:
        now_text = _parse_time(now).isoformat()

        def _consume(conn) -> bool:
            cur = conn.execute(
                """
                UPDATE s7_ceremony_challenges
                SET consumed_at = ?
                WHERE challenge_id = ?
                  AND consumed_at IS NULL
                  AND invalidated_at IS NULL
                  AND expires_at > ?
                """,
                (now_text, challenge_id, now_text),
            )
            return cur.rowcount == 1

        if connection is not None:
            # Caller owns the transaction: consumption becomes atomic with
            # whatever ceremony write shares it (covenant phase rows).
            return _consume(connection)
        with closing(self._conn()) as conn:
            return _consume(conn)

    def challenge_is_active(self, challenge_id: str, *, now: str) -> bool:
        with closing(self._conn()) as conn:
            row = conn.execute(
                """
                SELECT 1 FROM s7_ceremony_challenges
                WHERE challenge_id = ?
                  AND consumed_at IS NULL
                  AND invalidated_at IS NULL
                  AND expires_at > ?
                """,
                (challenge_id, now),
            ).fetchone()
        return row is not None

    def record_refusal_history(
        self,
        *,
        envelope: Any,
        rendered_text_hash: str,
        requester_ref: str,
        denial_reason: str,
        created_at: str,
        dialog_id: str | None = None,
    ) -> str:
        from core.governance import operator_user_boundary as s7

        _validate_hash64_text(rendered_text_hash, field="rendered_text_hash")
        if not requester_ref:
            raise ValueError("s7_refusal_requester_ref_required")
        if not denial_reason:
            raise ValueError("s7_refusal_denial_reason_required")
        _parse_time(created_at)
        record = s7.build_request_history_record(
            envelope=envelope,
            outcome="refused",
            created_at=created_at,
            dialog_id=dialog_id,
        )
        record_id = f"s7ref_{uuid.uuid4().hex}"
        with closing(self._conn()) as conn:
            conn.execute(
                """
                INSERT INTO s7_refusal_history(
                    record_id, request_id, request_envelope_hash, derived_work_class,
                    derived_aggregation_group, affected_refs_json, proposed_change_class,
                    rendered_text_hash, requester_ref, denial_reason, created_at, dialog_id, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    record.request_id,
                    record.request_envelope_hash,
                    record.derived_work_class,
                    record.derived_aggregation_group,
                    json.dumps(list(record.affected_refs), separators=(",", ":")),
                    record.proposed_change_class,
                    rendered_text_hash,
                    requester_ref,
                    denial_reason,
                    record.created_at,
                    record.dialog_id,
                    "refused",
                ),
            )
        return record_id

    def record_authorization_history(
        self,
        *,
        envelope: Any,
        rendered_text_hash: str,
        requester_ref: str,
        created_at: str,
        dialog_id: str | None = None,
    ) -> str:
        from core.governance import operator_user_boundary as s7

        _validate_hash64_text(rendered_text_hash, field="rendered_text_hash")
        if not requester_ref:
            raise ValueError("s7_refusal_requester_ref_required")
        _parse_time(created_at)
        record = s7.build_request_history_record(
            envelope=envelope,
            outcome="authorized",
            created_at=created_at,
            dialog_id=dialog_id,
        )
        record_id = f"s7authhist_{uuid.uuid4().hex}"
        with closing(self._conn()) as conn:
            conn.execute(
                """
                INSERT INTO s7_refusal_history(
                    record_id, request_id, request_envelope_hash, derived_work_class,
                    derived_aggregation_group, affected_refs_json, proposed_change_class,
                    rendered_text_hash, requester_ref, denial_reason, created_at, dialog_id, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    record.request_id,
                    record.request_envelope_hash,
                    record.derived_work_class,
                    record.derived_aggregation_group,
                    json.dumps(list(record.affected_refs), separators=(",", ":")),
                    record.proposed_change_class,
                    rendered_text_hash,
                    requester_ref,
                    "authorized",
                    record.created_at,
                    record.dialog_id,
                    "authorized",
                ),
            )
        return record_id

    def refusal_history_for_envelope(
        self,
        envelope: Any,
        *,
        now: str | None = None,
        window_seconds: int = 900,
    ) -> tuple[Any, ...]:
        from core.governance import operator_user_boundary as s7

        group = getattr(envelope, "derived_aggregation_group", "")
        cutoff = None
        if now is not None:
            cutoff = _parse_time(now) - timedelta(seconds=window_seconds)
        with closing(self._conn()) as conn:
            rows = conn.execute(
                """
                SELECT request_id, request_envelope_hash, derived_work_class,
                       derived_aggregation_group, affected_refs_json,
                       proposed_change_class, created_at, dialog_id, outcome
                FROM s7_refusal_history
                WHERE derived_aggregation_group = ?
                ORDER BY created_at, record_id
                """,
                (group,),
            ).fetchall()
        if cutoff is not None:
            rows = [
                row
                for row in rows
                if _parse_time(row["created_at"]) > cutoff
            ]
        return tuple(
            s7.S7RequestHistoryRecord(
                request_id=row["request_id"],
                request_envelope_hash=row["request_envelope_hash"],
                derived_work_class=row["derived_work_class"],
                derived_aggregation_group=row["derived_aggregation_group"],
                affected_refs=tuple(json.loads(row["affected_refs_json"])),
                proposed_change_class=row["proposed_change_class"],
                outcome=row["outcome"],
                created_at=row["created_at"],
                dialog_id=row["dialog_id"],
            )
            for row in rows
        )

    def set_bootstrap_closed_at(self, value: str) -> None:
        _parse_time(value)
        with closing(self._conn()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO s7_ceremony_metadata(key, value) VALUES (?, ?)",
                ("bootstrap_closed_at", value),
            )

    def mark_restored(self, *, now: str) -> None:
        _parse_time(now)
        with closing(self._conn()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    UPDATE s7_bootstrap_intents
                    SET revoked_at = ?
                    WHERE consumed_at IS NULL
                      AND revoked_at IS NULL
                    """,
                    (now,),
                )
                conn.execute(
                    """
                    UPDATE s7_ceremony_challenges
                    SET invalidated_at = ?
                    WHERE consumed_at IS NULL
                      AND invalidated_at IS NULL
                    """,
                    (now,),
                )
                conn.execute("COMMIT")
            except sqlite3.Error:
                conn.execute("ROLLBACK")
                raise
        self._audit("ceremony_store_restored", {"restored_at": now})

    def get_credential_without_hash_check(
        self,
        credential_ref: str,
    ) -> FounderWebAuthnCredentialRecord | None:
        with closing(self._conn()) as conn:
            row = conn.execute(
                """
                SELECT credential_ref, actor_handle_hmac, role_names_json,
                       public_key, sign_count, rp_id, origin, credential_kind,
                       backup_credential, enabled, ceremony_kind, label, created_at,
                       last_used_at, disabled_at, disabled_by_authorization_id,
                       reenabled_by_authorization_id, registration_challenge_id,
                       attestation_format, aaguid, authenticator_attachment,
                       backup_eligible, backed_up, transports_json, library_name,
                       library_version, sign_count_mode, uv_capable,
                       uv_required_for_guarded, distinct_device_confidence, record_hash
                FROM s7_founder_webauthn_credentials
                WHERE credential_ref = ?
                """,
                (credential_ref,),
            ).fetchone()
        return None if row is None else _credential_record_from_row(row)

    def _update_record_hash(self, record: FounderWebAuthnCredentialRecord) -> None:
        with closing(self._conn()) as conn:
            conn.execute(
                """
                UPDATE s7_founder_webauthn_credentials
                SET record_hash = ?
                WHERE credential_ref = ?
                """,
                (record.record_hash, record.credential_ref),
            )

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


def _validate_hash64_text(value: str, *, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError(f"{field} must be 64 lowercase hex chars")


def _parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _add_minutes(value: str, minutes: int) -> str:
    dt = _parse_time(value)
    return (dt + timedelta(minutes=minutes)).isoformat()


def _stored_bool(value: bool | int | None) -> int | None:
    if value is None:
        return None
    if value is True or value == 1:
        return 1
    if value is False or value == 0:
        return 0
    raise ValueError("s7_stored_bool_invalid")


def _loaded_bool(value: Any, *, nullable: bool = False) -> bool | None:
    if value is None and nullable:
        return None
    if value == 1:
        return True
    if value == 0:
        return False
    raise ValueError("s7_stored_bool_invalid")


def _credential_hash_payload(record: FounderWebAuthnCredentialRecord) -> dict[str, Any]:
    payload = asdict(record)
    payload["record_hash"] = ""
    payload["role_names"] = list(record.role_names)
    payload["transports"] = list(record.transports)
    return payload


def _credential_record_hash(record: FounderWebAuthnCredentialRecord) -> str:
    encoded = json.dumps(
        _credential_hash_payload(record),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _with_current_record_hash(
    record: FounderWebAuthnCredentialRecord,
) -> FounderWebAuthnCredentialRecord:
    return FounderWebAuthnCredentialRecord(**{**asdict(record), "record_hash": _credential_record_hash(record)})


def _credential_row_values(record: FounderWebAuthnCredentialRecord) -> tuple[Any, ...]:
    return (
        record.credential_ref,
        record.actor_handle_hmac,
        json.dumps(list(record.role_names), separators=(",", ":")),
        record.public_key,
        record.sign_count,
        record.rp_id,
        record.origin,
        record.credential_kind,
        _stored_bool(record.backup_credential),
        _stored_bool(record.enabled),
        record.ceremony_kind,
        record.label,
        record.created_at,
        record.last_used_at,
        record.disabled_at,
        record.disabled_by_authorization_id,
        record.reenabled_by_authorization_id,
        record.registration_challenge_id,
        record.attestation_format,
        record.aaguid,
        record.authenticator_attachment,
        _stored_bool(record.backup_eligible),
        _stored_bool(record.backed_up),
        json.dumps(list(record.transports), separators=(",", ":")),
        record.library_name,
        record.library_version,
        record.sign_count_mode,
        _stored_bool(record.uv_capable),
        _stored_bool(record.uv_required_for_guarded),
        record.distinct_device_confidence,
        record.record_hash,
    )


def _credential_record_from_row(row: sqlite3.Row) -> FounderWebAuthnCredentialRecord:
    return FounderWebAuthnCredentialRecord(
        credential_ref=row["credential_ref"],
        actor_handle_hmac=row["actor_handle_hmac"],
        role_names=tuple(json.loads(row["role_names_json"])),
        public_key=row["public_key"],
        sign_count=int(row["sign_count"]),
        rp_id=row["rp_id"],
        origin=row["origin"],
        credential_kind=row["credential_kind"],
        backup_credential=bool(_loaded_bool(row["backup_credential"])),
        enabled=bool(_loaded_bool(row["enabled"])),
        ceremony_kind=row["ceremony_kind"],
        label=row["label"],
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
        disabled_at=row["disabled_at"],
        disabled_by_authorization_id=row["disabled_by_authorization_id"],
        reenabled_by_authorization_id=row["reenabled_by_authorization_id"],
        registration_challenge_id=row["registration_challenge_id"],
        attestation_format=row["attestation_format"],
        aaguid=row["aaguid"],
        authenticator_attachment=row["authenticator_attachment"],
        backup_eligible=_loaded_bool(row["backup_eligible"], nullable=True),
        backed_up=_loaded_bool(row["backed_up"], nullable=True),
        transports=tuple(json.loads(row["transports_json"])),
        library_name=row["library_name"],
        library_version=row["library_version"],
        sign_count_mode=row["sign_count_mode"],
        uv_capable=_loaded_bool(row["uv_capable"], nullable=True),
        uv_required_for_guarded=bool(_loaded_bool(row["uv_required_for_guarded"])),
        distinct_device_confidence=row["distinct_device_confidence"],
        record_hash=row["record_hash"],
    )


def _aggregate_distinct_device_confidence(
    backups: tuple[FounderWebAuthnCredentialRecord, ...],
) -> str:
    if not backups:
        return "missing"
    values = {record.distinct_device_confidence for record in backups}
    if "same_device_override" in values:
        return "same_device_override"
    if "unknown" in values:
        return "unknown"
    return "confirmed_distinct"


def _manual_recovery_state(cause: str) -> dict[str, Any]:
    return {
        "mode": "manual_recovery_required",
        "manual_recovery_required": True,
        "manual_recovery_cause": cause,
        "active_credential_count": 0,
        "primary_credential_state": "missing",
        "backup_credential_state": "missing",
        "distinct_device_confidence": "missing",
    }


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create S7.1 WebAuthn bootstrap intent")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--purpose", required=True, choices=("register_primary",))
    create.add_argument("--ttl-minutes", type=int, default=5)
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
        print(f"Intent id: {intent.intent_id}")
        print(f"Token: {intent.raw_token}")
        print(f"Expires at: {intent.expires_at}")
        return 0
    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
