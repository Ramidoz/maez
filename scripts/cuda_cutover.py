"""Cutover authority tooling — Act 1 minting and execution-edge consumption.

Tracked and tested (unlike the retired local minter). Nothing here mutates
a service: minting writes one authorization document; consumption burns its
nonce atomically. Every mutating ceremony command remains owner-typed.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import secrets
import sqlite3
import stat as stat_module
from abc import ABC, abstractmethod
from pathlib import Path

from core.governance import operator_user_boundary as s7
from core.governance import s7_v2_migration as s7_migration
from core.governance import s7_webauthn_bootstrap as s7_bootstrap
from scripts import cuda_migration as cm
from scripts import cuda_bench_driver as driver

BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")
RECEIPT_NAME = "command-assemble-stage1-attempt-026-terminal.json"
AUTHORIZATION_NAME = "receipts/cutover-authorization.json"
MARKER_DIR = "markers"

CUTOVER_REFUSALS = frozenset(
    {
        "authorization_boot_mismatch",
        "authorization_consumed",
        "authorization_expired",
        "authorization_missing",
        "authorization_wrong_type",
        "burn_content_invalid",
        "mint_roundtrip_failed",
        "parent_receipt_malformed",
        "parent_receipt_noncanonical",
        "parent_receipt_not_bench_passed",
        "parent_receipt_unreadable",
        "preparation_failed",
        "preparation_unavailable",
        "legacy_cutover_consumer_retired",
        "presence_no_usable_credential",
        "presence_store_corrupt",
        "presence_store_identity_mismatch",
        "presence_store_journal_posture",
        "presence_store_predicate",
        "presence_store_schema_drift",
        "presence_store_table_missing",
        "presence_store_unavailable",
        "recovery_copies_mismatch",
    }
)


class CutoverRefusal(Exception):
    """Typed refusal; the message is the closed reason code."""


class ExistingAuthorizationStore:
    """Held descriptor plus read-only and read-write SQLite connections.

    Opening is eager so an absent path refuses at the function call, not
    later at context entry. Construction performs no schema initialization
    or migration.
    """

    __slots__ = (
        "_closed",
        "_db_fd",
        "_parent_fd",
        "consumption_connection",
        "inspection_connection",
    )

    def __init__(
        self,
        *,
        parent_fd: int,
        db_fd: int,
        inspection_connection: sqlite3.Connection,
        consumption_connection: sqlite3.Connection,
    ) -> None:
        self._parent_fd = parent_fd
        self._db_fd = db_fd
        self.inspection_connection = inspection_connection
        self.consumption_connection = consumption_connection
        self._closed = False

    def __enter__(self) -> ExistingAuthorizationStore:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.consumption_connection.close()
        finally:
            try:
                self.inspection_connection.close()
            finally:
                try:
                    os.close(self._db_fd)
                finally:
                    os.close(self._parent_fd)


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return all(
        getattr(left, field) == getattr(right, field)
        for field in (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_nlink",
        )
    )


def _sqlite_table_contract(
    conn: sqlite3.Connection, table: str
) -> tuple[tuple[object, ...], tuple[tuple[object, ...], ...]]:
    columns = tuple(conn.execute(f"PRAGMA table_info({table})"))
    indexes: list[tuple[object, ...]] = []
    for _seq, name, unique, origin, partial in conn.execute(
        f"PRAGMA index_list({table})"
    ):
        index_columns = tuple(
            row[2] for row in conn.execute(f"PRAGMA index_info({name})")
        )
        indexes.append((name, unique, origin, partial, index_columns))
    return columns, tuple(sorted(indexes, key=lambda item: str(item[0])))


def _expected_authorization_store_contracts():
    with sqlite3.connect(":memory:") as reference:
        reference.executescript(s7_migration._V2_AUTH_DDL)
        reference.executescript(s7_bootstrap._SCHEMA)
        return {
            table: _sqlite_table_contract(reference, table)
            for table in (
                "s7_authorization_artifacts_v2",
                "s7_founder_webauthn_credentials",
            )
        }


def open_existing_authorization_store(
    *, db_path: Path, expected_uid: int
) -> ExistingAuthorizationStore:
    """Open an existing private SQLite store without creation or migration."""

    path = Path(db_path)
    try:
        parent_fd = s7._open_directory_by_components(path.parent)
    except OSError as exc:
        raise CutoverRefusal("presence_store_unavailable") from exc

    db_fd: int | None = None
    inspection: sqlite3.Connection | None = None
    consumption: sqlite3.Connection | None = None
    try:
        try:
            db_fd = os.open(
                path.name,
                os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise CutoverRefusal("presence_store_unavailable") from exc

        held = os.fstat(db_fd)
        if (
            not stat_module.S_ISREG(held.st_mode)
            or held.st_uid != expected_uid
            or stat_module.S_IMODE(held.st_mode) != 0o600
            or held.st_nlink != 1
        ):
            raise CutoverRefusal("presence_store_predicate")

        header = os.pread(db_fd, 100, 0)
        if len(header) != 100 or not header.startswith(b"SQLite format 3\x00"):
            raise CutoverRefusal("presence_store_corrupt")
        if header[18:20] != b"\x01\x01":
            raise CutoverRefusal("presence_store_journal_posture")
        for suffix in ("-journal", "-wal", "-shm"):
            try:
                os.stat(
                    f"{path.name}{suffix}",
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise CutoverRefusal(
                    "presence_store_journal_posture"
                ) from exc
            raise CutoverRefusal("presence_store_journal_posture")

        try:
            inspection = sqlite3.connect(
                f"file:/proc/self/fd/{db_fd}?mode=ro", uri=True
            )
            inspection.execute("PRAGMA schema_version").fetchone()
        except sqlite3.Error as exc:
            raise CutoverRefusal("presence_store_corrupt") from exc

        journal_mode = inspection.execute("PRAGMA journal_mode").fetchone()
        if journal_mode != ("delete",):
            raise CutoverRefusal("presence_store_journal_posture")
        integrity = tuple(inspection.execute("PRAGMA integrity_check"))
        if integrity != (("ok",),):
            raise CutoverRefusal("presence_store_corrupt")
        expected_contracts = _expected_authorization_store_contracts()
        present_tables = {
            row[0]
            for row in inspection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not set(expected_contracts).issubset(present_tables):
            raise CutoverRefusal("presence_store_table_missing")
        actual_contracts = {
            table: _sqlite_table_contract(inspection, table)
            for table in expected_contracts
        }
        if actual_contracts != expected_contracts:
            raise CutoverRefusal("presence_store_schema_drift")

        try:
            consumption = sqlite3.connect(
                f"file:/proc/self/fd/{db_fd}?mode=rw", uri=True
            )
        except sqlite3.Error as exc:
            raise CutoverRefusal("presence_store_corrupt") from exc

        try:
            named = os.stat(
                path.name, dir_fd=parent_fd, follow_symlinks=False
            )
        except OSError as exc:
            raise CutoverRefusal("presence_store_identity_mismatch") from exc
        if not _same_file_identity(held, named):
            raise CutoverRefusal("presence_store_identity_mismatch")

        opened = ExistingAuthorizationStore(
            parent_fd=parent_fd,
            db_fd=db_fd,
            inspection_connection=inspection,
            consumption_connection=consumption,
        )
        parent_fd = -1
        db_fd = None
        inspection = None
        consumption = None
        return opened
    finally:
        if consumption is not None:
            consumption.close()
        if inspection is not None:
            inspection.close()
        if db_fd is not None:
            os.close(db_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


class PreparedCutover(ABC):
    """A capability whose implementation already holds its pinned resources."""

    @abstractmethod
    def begin(self) -> object:
        """Start the precomputed operation sequence without new resolution."""


class _CutoverPreparer(ABC):
    @abstractmethod
    def prepare(self) -> PreparedCutover:
        """Validate and pin every resource needed by ``begin``."""


class _BurnPublication(ABC):
    @abstractmethod
    def publish_and_validate(self) -> None:
        """Publish the staged burn and complete all post-link validation."""


_CUTOVER_PREPARER: _CutoverPreparer | None = None
_BURN_PUBLICATION: _BurnPublication | None = None


def prepare_cutover() -> PreparedCutover:
    """Return only a nominally typed, already-pinned executor capability."""

    preparer = _CUTOVER_PREPARER
    if preparer is None:
        raise CutoverRefusal("preparation_unavailable")
    prepared = preparer.prepare()
    if not isinstance(prepared, PreparedCutover):
        raise CutoverRefusal("preparation_failed")
    return prepared


def publish_and_validate_burn() -> None:
    """Closed and dormant until the real burn publisher is hard-bound."""

    publication = _BURN_PUBLICATION
    if publication is None:
        raise CutoverRefusal("burn_content_invalid")
    result = publication.publish_and_validate()
    if result is not None:
        raise CutoverRefusal("burn_content_invalid")


def execute_cutover() -> object:
    """Compose prepared execution and burn with a closed adjacency boundary."""

    prepared = prepare_cutover()
    begin = prepared.begin
    publish_and_validate_burn()
    return begin()


def _now_z() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _verified_bench_parent(root: Path) -> tuple[str, str]:
    """Fully verify the bench_passed receipt; return (evidence, artifact) hashes."""

    receipt_path = root / RECEIPT_NAME
    try:
        raw = receipt_path.read_bytes()
    except OSError as exc:
        raise CutoverRefusal("parent_receipt_unreadable") from exc
    try:
        wrapper = json.loads(raw)
    except ValueError as exc:
        raise CutoverRefusal("parent_receipt_malformed") from exc
    if (
        type(wrapper) is not dict
        or set(wrapper) != {"schema", "binding_sha256", "fields"}
        or wrapper["schema"] != driver.ASSEMBLE_RECEIPT_SCHEMA
        or type(wrapper["fields"]) is not dict
    ):
        raise CutoverRefusal("parent_receipt_malformed")
    if cm._canonical_wrapper_bytes(wrapper) != raw:
        raise CutoverRefusal("parent_receipt_noncanonical")
    fields = wrapper["fields"]
    bench = fields.get("bench_binding_sha256")
    bundle = fields.get("bundle_binding_sha256")
    if (
        fields.get("decision") != "bench_passed"
        or fields.get("reasons") != []
        or type(bench) is not str
        or cm._SHA256_RE.fullmatch(bench) is None
        or type(bundle) is not str
        or cm._SHA256_RE.fullmatch(bundle) is None
        or wrapper.get("binding_sha256") != bundle
    ):
        raise CutoverRefusal("parent_receipt_not_bench_passed")
    return bench, hashlib.sha256(raw).hexdigest()


def _anchored_exclusive_write(root: Path, relative: str, payload: bytes) -> Path:
    """O_NOFOLLOW/O_EXCL creation at 0600 inside the bench root."""

    target = root / relative
    parent_fd = os.open(
        target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    try:
        fd = os.open(
            target.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)
    return target


def mint_cutover_authorization(
    *,
    root: Path = BENCH_ROOT,
    owner: str = "rohit",
) -> cm.CutoverAuthorizationDoc:
    """Act 1: mint the enforceable cutover authorization (owner-run)."""

    bench_evidence, _artifact = _verified_bench_parent(root)
    # Precondition: the staged recovery copies must match the frozen
    # incumbent identity before the authorization binds the complete
    # rollback manifest (unit + dropin + runtime + library manifest +
    # model sha/bytes + alias + effective args).
    recovery_unit = hashlib.sha256(
        (root / "recovery" / "llama-server.service").read_bytes()
    ).hexdigest()
    recovery_dropin = hashlib.sha256(
        (root / "recovery" / "mtp.conf").read_bytes()
    ).hexdigest()
    if (
        recovery_unit != cm.FROZEN_VULKAN_UNIT_SHA256
        or recovery_dropin != cm.FROZEN_VULKAN_DROPIN_SHA256
    ):
        raise CutoverRefusal("recovery_copies_mismatch")
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    doc = cm.CutoverAuthorizationDoc(
        window_id=now.strftime("cutover-%Y%m%d-%H%M"),
        actions=cm.CUTOVER_ACTION_SET,
        boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        nonce=secrets.token_hex(32),
        issued_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at=(
            now + datetime.timedelta(seconds=cm.CUTOVER_TTL_S)
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        owner=owner,
        parent_bench_evidence_sha256=bench_evidence,
        rollback_manifest_sha256=cm.FROZEN_ROLLBACK_MANIFEST_SHA256,
    )
    wrapper = {
        "schema": cm.CUTOVER_AUTHORIZATION_SCHEMA,
        "binding_sha256": doc.binding_sha256,
        "fields": {
            "window_id": doc.window_id,
            "actions": list(doc.actions),
            "boot_id": doc.boot_id,
            "nonce": doc.nonce,
            "issued_at": doc.issued_at,
            "expires_at": doc.expires_at,
            "owner": doc.owner,
            "parent_bench_evidence_sha256": doc.parent_bench_evidence_sha256,
            "rollback_manifest_sha256": doc.rollback_manifest_sha256,
        },
    }
    payload = cm._canonical_wrapper_bytes(wrapper)
    path = _anchored_exclusive_write(root, AUTHORIZATION_NAME, payload)
    rebuilt = cm.PersistedDoc(path.read_bytes()).obj
    if (
        type(rebuilt) is not cm.CutoverAuthorizationDoc
        or rebuilt.binding_sha256 != doc.binding_sha256
    ):
        raise CutoverRefusal("mint_roundtrip_failed")
    return doc


def consume_cutover_authorization(
    *,
    root: Path = BENCH_ROOT,
    now_utc: str | None = None,
) -> cm.CutoverAuthorizationDoc:
    """Retired v1 burn path; presence-bound v2 is the only future route."""

    raise CutoverRefusal("legacy_cutover_consumer_retired")


def main() -> None:
    doc = mint_cutover_authorization()
    print(f"wrote      {BENCH_ROOT / AUTHORIZATION_NAME}")
    print(f"window_id  {doc.window_id}")
    print(f"valid      {doc.issued_at} -> {doc.expires_at}  (4h)")
    print(f"boot_id    {doc.boot_id}")
    print(f"parent     bench evidence {doc.parent_bench_evidence_sha256[:24]}…")
    print(f"actions    {', '.join(doc.actions)}")
    print("single-use: consumed atomically at the execution edge.")


if __name__ == "__main__":
    main()
