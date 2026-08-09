"""S7 v2 migration — the ordered, locked, single-transaction procedure.

The design freezes a 16-step order and a 5-row classification matrix. Both
are implemented here literally, in that order, because the order IS the
contract: the lock is taken FIRST so nothing can mutate between
classification and commit, and the fsync and receipt publication happen
OUTSIDE the lock, which is exactly why the receipt rather than the commit
is the linearization point.

What this module deliberately does NOT do:

* create anything on open -- that is `initialise_authorization_store`,
  and ordinary opening is verification-only;
* backfill a single row -- copying v1 rows forward would manufacture v2
  authority for records that never carried an action;
* repair anything. A store that matches neither the source nor the target
  identity is indeterminate and is refused, never completed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from core.governance import anchored_io
from core.governance.s7_schema_identity import (
    S7_SOURCE_FINGERPRINT_AUTH,
    S7_SOURCE_FINGERPRINT_VOICE,
    S7_TARGET_FINGERPRINT_AUTH,
    S7_TARGET_FINGERPRINT_VOICE,
)

STORE_NAME = "ceremony.sqlite3"
RECEIPT_NAME = "s7_migration_receipt.json"
RECEIPT_SCHEMA = "s7.migration_receipt.v1"

V1_AUTH = "s7_authorization_artifacts"
V2_AUTH = "s7_authorization_artifacts_v2"
V1_VOICE = "s7_voice_consultation_bundles"
V2_VOICE = "s7_voice_source_bundles_v2"

AUTH_PLANE = (V1_AUTH, V2_AUTH)
VOICE_PLANE = (V1_VOICE, V2_VOICE)


# --- frozen DDL, literal ------------------------------------------------

_V2_AUTH_DDL = f"""
CREATE TABLE IF NOT EXISTS {V2_AUTH} (
    artifact_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    request_envelope_hash TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    action_params_hash TEXT NOT NULL,
    precondition_hash TEXT NOT NULL,
    authority_context_hash TEXT NOT NULL,
    derived_work_class TEXT NOT NULL,
    derived_aggregation_group TEXT NOT NULL,
    nonce TEXT NOT NULL UNIQUE,
    credential_ref TEXT NOT NULL,
    auth_method TEXT NOT NULL,
    grant_source TEXT NOT NULL,
    user_presence INTEGER NOT NULL,
    user_verification INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    consumed_by_request_id TEXT,
    ceremony_kind TEXT NOT NULL DEFAULT 'founder_local_webauthn',
    action TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT 's7.authorization_artifact.v2'
);
CREATE UNIQUE INDEX IF NOT EXISTS s7_v2_nonce
    ON {V2_AUTH}(nonce);
"""

_V1_VOICE_DDL = f"""
CREATE TABLE IF NOT EXISTS {V1_VOICE} (
    source_ref_hash TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    consultation_id TEXT NOT NULL,
    request_envelope_hash TEXT,
    rendered_text_hash TEXT,
    action_params_hash TEXT,
    precondition_hash TEXT,
    authority_context_hash TEXT,
    maez_voice_consultation_hash TEXT,
    rendered_prompt_ref TEXT,
    rendered_prompt_hash TEXT,
    mutation_preview_hash TEXT,
    rollback_plan_ref TEXT,
    context_manifest_ref TEXT,
    context_manifest_hash TEXT,
    runtime_identity_hash TEXT,
    model_routing_identity_hash TEXT,
    model_config_hash TEXT,
    raw_response_ref TEXT,
    raw_response_hash TEXT,
    semantic_reader_attempt_hash TEXT,
    expires_at TEXT,
    authority_class TEXT,
    has_grounded_semantic_blocking_signal INTEGER,
    source_bundle_hash TEXT
)
"""

_V2_VOICE_DDL = f"""
CREATE TABLE IF NOT EXISTS {V2_VOICE} (
    source_ref_hash TEXT PRIMARY KEY,
    request_id TEXT NOT NULL, consultation_id TEXT NOT NULL,
    request_envelope_hash TEXT, rendered_text_hash TEXT,
    action_params_hash TEXT, precondition_hash TEXT,
    authority_context_hash TEXT, maez_voice_consultation_hash TEXT,
    rendered_prompt_ref TEXT, rendered_prompt_hash TEXT,
    mutation_preview_hash TEXT, rollback_plan_ref TEXT,
    context_manifest_ref TEXT, context_manifest_hash TEXT,
    runtime_identity_hash TEXT, model_routing_identity_hash TEXT,
    model_config_hash TEXT, raw_response_ref TEXT, raw_response_hash TEXT,
    semantic_reader_attempt_hash TEXT, expires_at TEXT,
    authority_class TEXT, has_grounded_semantic_blocking_signal INTEGER,
    source_bundle_hash TEXT,
    action TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT 's7.voice_source_bundle.v2'
);
CREATE UNIQUE INDEX IF NOT EXISTS s7_vb_v2_src
    ON {V2_VOICE}(source_ref_hash);
"""

# Unconditional by construction: a WHEN clause here would be a trigger
# that can decline to fire.
_V1_AUTH_FREEZE = f"""
CREATE TRIGGER s7_v1_frozen_insert BEFORE INSERT ON {V1_AUTH}
BEGIN SELECT RAISE(ABORT, 's7_v1_frozen'); END;
CREATE TRIGGER s7_v1_frozen_update BEFORE UPDATE ON {V1_AUTH}
BEGIN SELECT RAISE(ABORT, 's7_v1_frozen'); END;
CREATE TRIGGER s7_v1_frozen_delete BEFORE DELETE ON {V1_AUTH}
BEGIN SELECT RAISE(ABORT, 's7_v1_frozen'); END;
"""

_V1_VOICE_FREEZE = f"""
CREATE TRIGGER s7_vb_v1_frozen_insert BEFORE INSERT ON {V1_VOICE}
BEGIN SELECT RAISE(ABORT, 's7_vb_v1_frozen'); END;
CREATE TRIGGER s7_vb_v1_frozen_update BEFORE UPDATE ON {V1_VOICE}
BEGIN SELECT RAISE(ABORT, 's7_vb_v1_frozen'); END;
CREATE TRIGGER s7_vb_v1_frozen_delete BEFORE DELETE ON {V1_VOICE}
BEGIN SELECT RAISE(ABORT, 's7_vb_v1_frozen'); END;
"""

# Conditional BY DESIGN -- they fire only on collision -- and the
# condition reads the v1 table, so `WHEN 0` could not impersonate one.
_V2_EXCLUSION = f"""
CREATE TRIGGER s7_v2_no_v1_nonce BEFORE INSERT ON {V2_AUTH}
WHEN EXISTS (SELECT 1 FROM {V1_AUTH} WHERE nonce = NEW.nonce)
BEGIN SELECT RAISE(ABORT, 's7_cross_version_nonce'); END;
CREATE TRIGGER s7_v2_no_v1_artifact BEFORE INSERT ON {V2_AUTH}
WHEN EXISTS (SELECT 1 FROM {V1_AUTH} WHERE artifact_id = NEW.artifact_id)
BEGIN SELECT RAISE(ABORT, 's7_cross_version_artifact'); END;
CREATE TRIGGER s7_vb_v2_no_v1 BEFORE INSERT ON {V2_VOICE}
WHEN EXISTS (SELECT 1 FROM {V1_VOICE}
             WHERE source_ref_hash = NEW.source_ref_hash)
BEGIN SELECT RAISE(ABORT, 's7_cross_version_bundle'); END;
"""


class S7MigrationRefused(ValueError):
    """A refusal, not a crash. Never repaired into a success."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def schema_fingerprint(conn: sqlite3.Connection, table_names) -> str:
    """The FROZEN recipe: normalized sqlite_master.sql over tables, indexes
    AND triggers, explicitly sorted rather than raw row order.

    It hashes SQL TEXT, so expression indexes, partial predicates and every
    trigger body participate by construction. v5's fingerprint enumerated
    PRAGMA fields and did not cover triggers at all -- a DROP TRIGGER left
    it identical, so the wall could be removed and the receipt still
    validate.
    """

    def canon(sql):
        return None if sql is None else re.sub(r"\s+", " ", sql).strip().rstrip(";")

    rows = []
    for name in sorted(table_names):
        for kind, obj, tbl, sql in conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE tbl_name=? ORDER BY type,name",
            (name,),
        ):
            rows.append([kind, obj, tbl, canon(sql)])
    payload = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _run(conn: sqlite3.Connection, script: str) -> None:
    """Execute a DDL script statement by statement.

    NOT executescript: it COMMITS any pending transaction before running,
    which would silently break the single BEGIN IMMEDIATE the whole
    procedure depends on -- a fault halfway through would leave a
    half-migrated store rather than rolling back whole.
    """
    for statement in _split_sql(script):
        conn.execute(statement)


def _split_sql(script: str) -> list[str]:
    """Split on statement boundaries, keeping TRIGGER bodies intact.

    A trigger contains internal semicolons between BEGIN and END, so a
    naive split on ';' would tear it into fragments.
    """
    statements, buffer, depth = [], [], 0
    for chunk in script.split(";"):
        buffer.append(chunk)
        upper = chunk.upper()
        depth += len(re.findall(r"\bBEGIN\b", upper))
        depth -= len(re.findall(r"\bEND\b", upper))
        if depth <= 0:
            statement = ";".join(buffer).strip()
            buffer, depth = [], 0
            if statement:
                statements.append(statement)
    tail = ";".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _count(conn: sqlite3.Connection, name: str) -> int:
    if not _table_exists(conn, name):
        return 0
    return conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]


RECEIPT_FIELDS = (
    "activation_path",
    "completed_at",
    "from_fingerprint_auth",
    "from_fingerprint_bundle",
    "row_count_v1_auth",
    "row_count_v1_bundle",
    "row_count_v2_auth_at_migration",
    "row_count_v2_bundle_at_migration",
    "started_at",
    "store_dev",
    "store_ino",
    "to_fingerprint_auth",
    "to_fingerprint_bundle",
)
ACTIVATION_PATHS = frozenset({"fresh_migration", "committed_recovery"})


def _validate_receipt(receipt: dict, conn: sqlite3.Connection) -> None:
    """"Present and valid" is not "a JSON object exists".

    A document carrying only store_dev and store_ino was accepted as
    complete. Every frozen field, the fingerprints it vouches for, the
    migration-time zero counts and the closed activation path are checked
    here, or the receipt asserts nothing it can be held to.
    """
    if tuple(sorted(receipt)) != RECEIPT_FIELDS:
        raise S7MigrationRefused("receipt does not carry exactly its frozen fields")
    if receipt["activation_path"] not in ACTIVATION_PATHS:
        raise S7MigrationRefused("receipt activation_path is not a closed value")
    if receipt["from_fingerprint_auth"] != S7_SOURCE_FINGERPRINT_AUTH:
        raise S7MigrationRefused("receipt source auth fingerprint mismatch")
    if receipt["from_fingerprint_bundle"] != S7_SOURCE_FINGERPRINT_VOICE:
        raise S7MigrationRefused("receipt source voice fingerprint mismatch")
    if receipt["to_fingerprint_auth"] != S7_TARGET_FINGERPRINT_AUTH:
        raise S7MigrationRefused("receipt target auth fingerprint mismatch")
    if receipt["to_fingerprint_bundle"] != S7_TARGET_FINGERPRINT_VOICE:
        raise S7MigrationRefused("receipt target voice fingerprint mismatch")
    if receipt["row_count_v2_auth_at_migration"] != 0:
        raise S7MigrationRefused("receipt claims a non-zero v2 auth count")
    if receipt["row_count_v2_bundle_at_migration"] != 0:
        raise S7MigrationRefused("receipt claims a non-zero v2 bundle count")
    # Step 4a: the v1 counts the receipt CLAIMS must be the counts present.
    # A receipt claiming 999 rows describes a different store.
    if receipt["row_count_v1_auth"] != _count(conn, V1_AUTH):
        raise S7MigrationRefused("receipt v1 auth count does not match the store")
    if receipt["row_count_v1_bundle"] != _count(conn, V1_VOICE):
        raise S7MigrationRefused("receipt v1 bundle count does not match the store")
    # The schema the receipt vouches for must still be the schema present.
    if schema_fingerprint(conn, AUTH_PLANE) != S7_TARGET_FINGERPRINT_AUTH:
        raise S7MigrationRefused("auth plane no longer matches the receipt")
    if schema_fingerprint(conn, VOICE_PLANE) != S7_TARGET_FINGERPRINT_VOICE:
        raise S7MigrationRefused("voice plane no longer matches the receipt")


def _classify(conn: sqlite3.Connection, receipt: dict | None) -> str:
    """Step 2a, INSIDE the lock.

    v13 classified before BEGIN IMMEDIATE, which restored the very TOCTOU
    that moving source verification inside the lock had just removed.
    """
    auth = schema_fingerprint(conn, AUTH_PLANE)
    voice = schema_fingerprint(conn, VOICE_PLANE)

    if receipt is not None:
        return "complete"
    if auth == S7_SOURCE_FINGERPRINT_AUTH and voice == S7_SOURCE_FINGERPRINT_VOICE:
        return "not_started"
    if auth == S7_TARGET_FINGERPRINT_AUTH and voice == S7_TARGET_FINGERPRINT_VOICE:
        if _count(conn, V2_AUTH) == 0 and _count(conn, V2_VOICE) == 0:
            return "committed_not_published"
        return "indeterminate"
    return "indeterminate"


def _read_receipt(store_dir_fd: int) -> dict | None:
    try:
        raw = anchored_io._read_migration_receipt(store_dir_fd=store_dir_fd)
    except FileNotFoundError:
        # The ONLY posture that means "no receipt". Swallowing every
        # OSError let a 0644 receipt read as absent: the store migrated,
        # the invalid receipt stayed, and the call returned success.
        return None
    except (OSError, ValueError) as exc:
        raise S7MigrationRefused(f"existing receipt is unusable: {exc}") from exc

    document = json.loads(raw)
    # Canonical BYTES, not merely equivalent JSON. Pretty-printed content
    # parses the same and is not what was published; two readers could
    # disagree about what the receipt says.
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":")
    ).encode()
    if raw != canonical:
        raise S7MigrationRefused("receipt bytes are not canonical")
    return document


def _migrate_authorization_store_to_v2_at(*, store_dir_fd: int) -> None:
    """PRIVATE — descriptor injection, for private-copy tests only."""
    # Held OPEN for the whole procedure. Closing it and handing SQLite a
    # pathname loses the anchor: the name can be repointed at another
    # inode and the migration modifies the WRONG database before any
    # refusal. Connecting through the descriptor makes that impossible
    # rather than merely detectable afterwards.
    store_fd = os.open(STORE_NAME, os.O_RDWR | os.O_NOFOLLOW, dir_fd=store_dir_fd)
    try:
        store_stat = os.fstat(store_fd)
    except Exception:
        os.close(store_fd)
        raise

    from core.governance import operator_user_boundary as _facade

    # Through the façade so the clock is INJECTABLE. A wall-clock reading
    # is not enough for the recovery witness: two runs inside the same
    # second are identical, so a recovery that simply REUSED the original
    # stamp would be indistinguishable from one that recorded its own.
    now = getattr(_facade, "_utc_now", _utc_now)

    try:
        existing = _read_receipt(store_dir_fd)
        # SQLite needs a pathname; it cannot take a descriptor. The directory
        # is resolved ONCE from the already-held fd rather than re-walked from
        # a caller-supplied string, so the anchor still decides which directory
        # this is. `/proc/self/fd/N` itself cannot be reopened with O_NOFOLLOW
        # -- it IS a symlink -- so the target is read out of it instead.
        db_path = f"file:/proc/self/fd/{store_fd}?mode=rw"

        def _assert_still_the_held_store() -> None:
            """The pathname must never become the authority.

            SQLite re-walks `db_path`, so between resolving it and opening it
            the name can be pointed at a DIFFERENT inode -- reproduced: the
            migration ran happily against a substituted database and published
            a receipt for the wrong inode while the held one sat untouched.
            The held descriptor's identity is the arbiter, checked either side
            of the work.
            """
            current = os.fstat(store_fd)
            if (current.st_dev, current.st_ino) != (
                store_stat.st_dev,
                store_stat.st_ino,
            ):
                raise S7MigrationRefused(
                    "the store beneath the held descriptor changed identity"
                )

        _assert_still_the_held_store()
        started_at = now()

        with closing(sqlite3.connect(db_path, uri=True)) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")  # 1. LOCK FIRST
            except sqlite3.OperationalError as exc:
                raise S7MigrationRefused(f"store is busy: {exc}") from exc

            try:
                state = _classify(conn, existing)  # 2a. inside the lock

                if state == "indeterminate":
                    raise S7MigrationRefused(
                        "store matches neither the source nor the target identity"
                    )

                # Step 2, on EVERY run. This sat below the complete
                # branch's early return, so a migrated store flipped to
                # WAL was accepted -- and WAL is precisely the mode the
                # fsync ordering was designed against.
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                if str(mode).lower() != "delete":
                    raise S7MigrationRefused(
                        f"journal_mode is {mode}, not delete"
                    )
                synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
                if int(synchronous) != 2:
                    raise S7MigrationRefused("synchronous is not FULL")

                if state == "complete":
                    _validate_receipt(existing, conn)
                    conn.commit()
                    return

                counts = {
                    "row_count_v1_auth": _count(conn, V1_AUTH),
                    "row_count_v1_bundle": _count(conn, V1_VOICE),
                }
                if state == "not_started":
                    from_auth = schema_fingerprint(conn, AUTH_PLANE)
                    from_voice = schema_fingerprint(conn, VOICE_PLANE)
                else:
                    # committed_not_published: the schema is ALREADY migrated,
                    # so reading it here would record the TARGET as the source
                    # and the receipt would claim the migration started where
                    # it ended. The source is the identity classification
                    # already proved this store had.
                    from_auth = S7_SOURCE_FINGERPRINT_AUTH
                    from_voice = S7_SOURCE_FINGERPRINT_VOICE

                if state == "not_started":
                    _run(conn, _V1_VOICE_DDL)      # 5
                    _run(conn, _V1_VOICE_FREEZE)   # 6
                    _run(conn, _V1_AUTH_FREEZE)    # 7
                    _run(conn, _V2_AUTH_DDL)       # 8
                    _run(conn, _V2_VOICE_DDL)      # 8
                    _run(conn, _V2_EXCLUSION)      # 9
                    # 10. copy nothing.

                    # 11-12. the built schema must hash to the COMMITTED
                    # constants -- never to whatever it happens to be.
                    if schema_fingerprint(conn, AUTH_PLANE) != S7_TARGET_FINGERPRINT_AUTH:
                        raise S7MigrationRefused("auth plane target fingerprint mismatch")
                    if schema_fingerprint(conn, VOICE_PLANE) != S7_TARGET_FINGERPRINT_VOICE:
                        raise S7MigrationRefused("voice plane target fingerprint mismatch")

                    # 13. both v2 tables must be empty
                    if _count(conn, V2_AUTH) or _count(conn, V2_VOICE):
                        raise S7MigrationRefused("v2 tables are not empty")

                conn.commit()  # 14. lock RELEASED
            except Exception:
                conn.rollback()
                raise

            to_auth = schema_fingerprint(conn, AUTH_PLANE)
            to_voice = schema_fingerprint(conn, VOICE_PLANE)

        # Either side of the work: what we migrated is what we held.
        _assert_still_the_held_store()

        # 15. fsync the database AND its parent -- outside the lock
        os.fsync(store_fd)
        os.fsync(store_dir_fd)

        # 16. publish the receipt -- THE linearization point
        receipt = {
            "activation_path": (
                "fresh_migration" if state == "not_started" else "committed_recovery"
            ),
            "completed_at": now(),
            "from_fingerprint_auth": from_auth,
            "from_fingerprint_bundle": from_voice,
            "row_count_v1_auth": counts["row_count_v1_auth"],
            "row_count_v1_bundle": counts["row_count_v1_bundle"],
            "row_count_v2_auth_at_migration": 0,
            "row_count_v2_bundle_at_migration": 0,
            "started_at": started_at,
            "store_dev": store_stat.st_dev,
            "store_ino": store_stat.st_ino,
            "to_fingerprint_auth": to_auth,
            "to_fingerprint_bundle": to_voice,
        }
        payload = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        try:
            anchored_io._write_private_file_at(store_dir_fd, RECEIPT_NAME, payload)
        except FileExistsError:
            # A competitor published while we were syncing. Losing is fine;
            # accepting whatever they wrote is not -- a two-field document
            # carrying only the right dev/ino was taken as proof of a
            # completed migration. Re-open and run the SAME validator.
            winner = _read_receipt(store_dir_fd)
            if winner is None:
                raise S7MigrationRefused("lost the publication race to nothing")
            with closing(sqlite3.connect(db_path, uri=True)) as conn:
                _validate_receipt(winner, conn)
    finally:
        os.close(store_fd)


def migrate_authorization_store_to_v2() -> None:
    """PRODUCTION — no path, no root, no descriptor."""
    with anchored_io._open_canonical_s7_dir() as store_dir_fd:
        _migrate_authorization_store_to_v2_at(store_dir_fd=store_dir_fd)


def read_migration_receipt() -> bytes:
    return anchored_io.read_migration_receipt()


def _read_migration_receipt(*, store_dir_fd: int) -> bytes:
    return anchored_io._read_migration_receipt(store_dir_fd=store_dir_fd)


def _migration_receipt_path() -> Path:
    raise NotImplementedError("activation takes no path")
