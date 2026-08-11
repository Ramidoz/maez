"""Cutover authority tooling — Act 1 minting and dormant Act 2 contracts.

Tracked and tested (unlike the retired local minter). Nothing here mutates a
service. Act 2 remains blocked until its owner-selected completion locator has
an authority-preserving input surface.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import secrets
import sqlite3
import stat as stat_module
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from core.governance import anchored_io as s7_io
from core.governance import operator_user_boundary as s7
from core.governance import s7_guarded_execution as guarded
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
        "completion_locator_unavailable",
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

CONSULTATION_FAILURES = (
    "consultation_unavailable",
    "response_unreadable",
    "semantic_reader_failed",
    "objection_recorded",
    "consultation_withdrawn",
    "bundle_unreservable",
)

_CONSULTATION_OUTCOMES = frozenset(
    {"asked_and_answered", "attempt_failed", "consultation_withdrawn"}
)
_CONSULTATION_ATTEMPT_SCHEMA = "cuda_cutover.consultation_attempt.v1"


class CutoverRefusal(Exception):
    """Typed refusal; the message is the closed reason code."""


@dataclass(frozen=True)
class ConsultationAttempt:
    """Fresh pre-ask identity plus the private root for its durable evidence."""

    request_id: str
    receipt_root: Path
    attempt_identity: str
    consultation_id: str

    @classmethod
    def fresh(cls, *, request_id: str, receipt_root: Path) -> ConsultationAttempt:
        if type(request_id) is not str or not request_id:
            raise ValueError("consultation attempt requires request_id")
        attempt_identity = secrets.token_hex(32)
        consultation_id = _consultation_id_for_attempt(
            request_id=request_id,
            attempt_identity=attempt_identity,
        )
        return cls(
            request_id=request_id,
            receipt_root=Path(receipt_root),
            attempt_identity=attempt_identity,
            consultation_id=consultation_id,
        )

    def __post_init__(self) -> None:
        if type(self.request_id) is not str or not self.request_id:
            raise ValueError("consultation attempt requires request_id")
        if not isinstance(self.receipt_root, Path):
            raise ValueError("consultation attempt requires a Path receipt_root")
        s7._validate_hash64(self.attempt_identity, field="attempt_identity")
        expected = _consultation_id_for_attempt(
            request_id=self.request_id,
            attempt_identity=self.attempt_identity,
        )
        if self.consultation_id != expected:
            raise ValueError("consultation_id must derive from the fresh attempt")

    @property
    def start_receipt_ref(self) -> str:
        return f"attempts/{self.attempt_identity}.started.json"


@dataclass(frozen=True)
class CutoverConsultationResult:
    """Recorded exchange state only; this type carries no proceed verdict."""

    outcome: str
    attempt: ConsultationAttempt
    consultation: s7.MaezVoiceConsultation | None
    raw_response_bytes: bytes | None
    raw_response_ref: str | None
    raw_response_sha256: str | None
    owner_visible_response: str | None
    rendered_text_hash: str | None
    response_capture_receipt: guarded.S7ResponseCaptureReceipt | None
    attempt_receipt_ref: str | None
    failure_reason_code: str | None

    def __post_init__(self) -> None:
        if self.outcome not in _CONSULTATION_OUTCOMES:
            raise ValueError("unknown cutover consultation outcome")
        if not isinstance(self.attempt, ConsultationAttempt):
            raise ValueError("cutover consultation result requires its attempt")
        if self.failure_reason_code is not None and (
            self.failure_reason_code not in CONSULTATION_FAILURES
        ):
            raise ValueError("unknown cutover consultation failure")
        if type(self.attempt_receipt_ref) is not str or not self.attempt_receipt_ref:
            raise ValueError("cutover consultation results require a durable receipt")

        if self.outcome == "asked_and_answered":
            if self.failure_reason_code is not None:
                raise ValueError("answered consultation cannot carry a failure")
            if not isinstance(self.consultation, s7.MaezVoiceConsultation):
                raise ValueError("answered consultation requires its typed record")
            if (
                self.consultation.maez_voice_consulted is not True
                or self.consultation.maez_objection_state != "not_determined"
            ):
                raise ValueError("recorded consultation must remain unjudged")
            if type(self.raw_response_bytes) is not bytes or not self.raw_response_bytes:
                raise ValueError("answered consultation requires exact response bytes")
            expected_sha256 = hashlib.sha256(self.raw_response_bytes).hexdigest()
            if self.raw_response_sha256 != expected_sha256:
                raise ValueError("raw_response_sha256 must derive from exact bytes")
            if (
                type(self.raw_response_ref) is not str
                or expected_sha256 not in self.raw_response_ref
            ):
                raise ValueError("raw_response_ref must derive from exact bytes")
            if (
                type(self.owner_visible_response) is not str
                or self.owner_visible_response.encode("utf-8")
                != self.raw_response_bytes
            ):
                raise ValueError("owner-visible response must preserve exact bytes")
            if self.rendered_text_hash is None:
                raise ValueError("answered consultation requires rendered_text_hash")
            s7._validate_hash64(
                self.rendered_text_hash,
                field="rendered_text_hash",
            )
            if self.attempt_receipt_ref is None:
                raise ValueError("answered consultation requires a durable receipt")
            receipt = self.response_capture_receipt
            if type(receipt) is not guarded.S7ResponseCaptureReceipt:
                raise ValueError("answered consultation requires its typed capture receipt")
            if (
                receipt.request_id != self.attempt.request_id
                or receipt.consultation_id != self.attempt.consultation_id
                or receipt.attempt_identity != self.attempt.attempt_identity
                or receipt.raw_response_ref != self.raw_response_ref
                or receipt.raw_response_sha256 != self.raw_response_sha256
            ):
                raise ValueError("capture receipt does not match the consultation result")
            return

        if self.consultation is not None:
            raise ValueError("non-answered consultation cannot carry a voice fact")
        if self.failure_reason_code is None:
            raise ValueError("non-answered consultation requires a failure reason")
        if self.response_capture_receipt is not None:
            raise ValueError("non-answered consultation cannot carry a capture receipt")
        if self.outcome == "consultation_withdrawn" and (
            self.failure_reason_code != "consultation_withdrawn"
        ):
            raise ValueError("withdrawal must remain distinct")
        if self.failure_reason_code == "consultation_withdrawn" and (
            self.outcome != "consultation_withdrawn"
        ):
            raise ValueError("withdrawal must remain distinct")


def _consultation_id_for_attempt(*, request_id: str, attempt_identity: str) -> str:
    return "cutover-consultation-" + s7.canonical_hash(
        {
            "attempt_identity": attempt_identity,
            "request_id": request_id,
        }
    )


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


def execute_cutover() -> object:
    """Refuse until the owner-selected completion locator has a ruled ingress."""

    raise CutoverRefusal("completion_locator_unavailable")


def _now_z() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _ensure_private_consultation_subdir(root: Path, name: str) -> None:
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        held = os.fstat(root_fd)
        if held.st_uid != os.getuid():
            raise PermissionError("consultation receipt root has the wrong owner")
        try:
            os.mkdir(name, 0o700, dir_fd=root_fd)
        except FileExistsError:
            present = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            if (
                not stat_module.S_ISDIR(present.st_mode)
                or present.st_uid != os.getuid()
                or stat_module.S_IMODE(present.st_mode) != 0o700
            ):
                raise PermissionError("consultation evidence directory is not private")
    finally:
        os.close(root_fd)


def _consultation_receipt_bytes(fields: dict[str, object]) -> bytes:
    return cm._canonical_wrapper_bytes(
        {
            "schema": _CONSULTATION_ATTEMPT_SCHEMA,
            "binding_sha256": s7.canonical_hash(fields),
            "fields": fields,
        }
    )


def _persist_consultation_receipt(
    *,
    attempt: ConsultationAttempt,
    relative: str,
    fields: dict[str, object],
) -> str:
    _ensure_private_consultation_subdir(attempt.receipt_root, "attempts")
    s7_io.write_private_file(
        relative,
        _consultation_receipt_bytes(fields),
        root=attempt.receipt_root,
    )
    return relative


def _persist_exact_consultation_response(
    *,
    attempt: ConsultationAttempt,
    response: bytes,
    response_sha256: str,
) -> str:
    _ensure_private_consultation_subdir(attempt.receipt_root, "responses")
    relative = f"responses/{response_sha256}.bin"
    try:
        s7_io.write_private_file(
            relative,
            response,
            root=attempt.receipt_root,
        )
    except FileExistsError:
        present = s7_io.read_private_file(
            relative,
            root=attempt.receipt_root,
            expected_uid=os.getuid(),
        )
        if present != response:
            raise ValueError("content-addressed response bytes do not match")
    return relative


def _attempt_terminal_ref(
    attempt: ConsultationAttempt,
    *,
    replay: bool = False,
) -> str:
    suffix = (
        f"replay-{secrets.token_hex(16)}"
        if replay
        else "terminal"
    )
    return f"attempts/{attempt.attempt_identity}.{suffix}.json"


def _failed_consultation_result(
    *,
    attempt: ConsultationAttempt,
    base_fields: dict[str, object],
    outcome: str,
    failure_reason_code: str,
    now: str,
    rendered_text_hash: str | None,
    replay: bool = False,
) -> CutoverConsultationResult:
    terminal_fields = {
        **base_fields,
        "completed_at": now,
        "failure_reason_code": failure_reason_code,
        "outcome": outcome,
        "rendered_text_hash": rendered_text_hash,
    }
    try:
        receipt_ref = _persist_consultation_receipt(
            attempt=attempt,
            relative=_attempt_terminal_ref(attempt, replay=replay),
            fields=terminal_fields,
        )
    except (OSError, ValueError) as exc:
        raise CutoverRefusal("bundle_unreservable") from exc
    return CutoverConsultationResult(
        outcome=outcome,
        attempt=attempt,
        consultation=None,
        raw_response_bytes=None,
        raw_response_ref=None,
        raw_response_sha256=None,
        owner_visible_response=None,
        rendered_text_hash=rendered_text_hash,
        response_capture_receipt=None,
        attempt_receipt_ref=receipt_ref,
        failure_reason_code=failure_reason_code,
    )


def _ask_text_attr(ask: object, name: str) -> str | None:
    value = getattr(ask, name, None)
    return value if type(value) is str else None


def _cutover_consultation_question(
    *,
    envelope: s7.WorkRequestEnvelope,
    request_envelope_hash: str,
    action_params_hash: str,
    authority_context_hash: str,
    runtime_identity_hash: str,
    runtime_source_ref: str,
) -> str:
    affected = "\n".join(f"- {ref}" for ref in envelope.affected_refs) or "- none"
    params_text = json.dumps(
        dict(cm.CUTOVER_ACTION_PARAMS),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return "\n".join(
        (
            "CUDA cutover consultation request v1",
            f"Request id: {envelope.request_id}",
            f"Action: {envelope.action}",
            f"Action params: {params_text}",
            f"Request envelope hash: {request_envelope_hash}",
            f"Action params hash: {action_params_hash}",
            f"Precondition hash: {envelope.precondition_hash}",
            f"Authority context hash: {authority_context_hash}",
            f"Runtime identity hash: {runtime_identity_hash}",
            f"Runtime source ref: {runtime_source_ref}",
            "Affected refs:",
            affected,
            "What do you want the owner to understand about this exact proposed "
            "change before deciding whether to tap?",
        )
    )


def _is_canonical_cutover_envelope(envelope: s7.WorkRequestEnvelope) -> bool:
    try:
        expected = s7.build_cutover_work_request_envelope(
            request_id=envelope.request_id,
            action=cm.CUTOVER_ACTION,
            params=dict(cm.CUTOVER_ACTION_PARAMS),
            affected_refs=envelope.affected_refs,
            precondition_hash=envelope.precondition_hash,
            created_at=envelope.created_at,
            expires_at=envelope.expires_at,
            maez_voice_consultation_id=envelope.maez_voice_consultation_id or "",
        )
    except ValueError:
        return False
    return envelope == expected


def produce_cutover_consultation(
    *,
    envelope: s7.WorkRequestEnvelope,
    attempt: ConsultationAttempt,
    ask: Callable[[str], bytes],
    now: str,
) -> CutoverConsultationResult:
    """Ask once, preserve exact bytes, and record no machine interpretation."""

    if not isinstance(envelope, s7.WorkRequestEnvelope):
        raise ValueError("cutover consultation requires WorkRequestEnvelope")
    if not isinstance(attempt, ConsultationAttempt):
        raise ValueError("cutover consultation requires ConsultationAttempt")
    s7._timestamp_text(now, field="now")

    request_envelope_hash = s7.canonical_hash(asdict(envelope))
    action_params_hash = s7.canonical_hash(dict(cm.CUTOVER_ACTION_PARAMS))
    authority_context_hash = _ask_text_attr(ask, "authority_context_hash")
    runtime_identity_hash = _ask_text_attr(ask, "runtime_identity_hash")
    runtime_source_ref = _ask_text_attr(ask, "runtime_source_ref")
    question = _cutover_consultation_question(
        envelope=envelope,
        request_envelope_hash=request_envelope_hash,
        action_params_hash=action_params_hash,
        authority_context_hash=authority_context_hash or "unavailable",
        runtime_identity_hash=runtime_identity_hash or "unavailable",
        runtime_source_ref=runtime_source_ref or "unavailable",
    )
    rendered_text_hash = s7.rendered_text_hash(question)
    base_fields: dict[str, object] = {
        "action": envelope.action,
        "action_params_hash": action_params_hash,
        "attempt_identity": attempt.attempt_identity,
        "authority_context_hash": authority_context_hash,
        "consultation_id": attempt.consultation_id,
        "created_at": now,
        "failure_reason_code": None,
        "outcome": "attempt_started",
        "precondition_hash": envelope.precondition_hash,
        "rendered_text_hash": rendered_text_hash,
        "request_envelope_hash": request_envelope_hash,
        "request_id": envelope.request_id,
        "runtime_identity_hash": runtime_identity_hash,
        "runtime_source_ref": runtime_source_ref,
    }

    try:
        _persist_consultation_receipt(
            attempt=attempt,
            relative=attempt.start_receipt_ref,
            fields=base_fields,
        )
    except FileExistsError:
        return _failed_consultation_result(
            attempt=attempt,
            base_fields=base_fields,
            outcome="attempt_failed",
            failure_reason_code="bundle_unreservable",
            now=now,
            rendered_text_hash=rendered_text_hash,
            replay=True,
        )
    except (OSError, ValueError) as exc:
        raise CutoverRefusal("bundle_unreservable") from exc

    exact_binding = {
        "capability_kind": "bonded_runtime_voice",
        "request_id": envelope.request_id,
        "request_envelope_hash": request_envelope_hash,
        "action": envelope.action,
        "action_params_hash": action_params_hash,
        "precondition_hash": envelope.precondition_hash,
    }
    binding_matches = (
        _is_canonical_cutover_envelope(envelope)
        and attempt.request_id == envelope.request_id
        and envelope.maez_voice_consultation_id == attempt.consultation_id
        and all(
            _ask_text_attr(ask, name) == expected
            for name, expected in exact_binding.items()
        )
    )
    try:
        if authority_context_hash is None:
            raise ValueError("authority_context_hash unavailable")
        s7._validate_hash64(
            authority_context_hash,
            field="authority_context_hash",
        )
        if runtime_identity_hash is None:
            raise ValueError("runtime_identity_hash unavailable")
        s7._validate_hash64(
            runtime_identity_hash,
            field="runtime_identity_hash",
        )
        if runtime_source_ref is None or not runtime_source_ref:
            raise ValueError("runtime_source_ref unavailable")
    except ValueError:
        binding_matches = False
    if not binding_matches:
        return _failed_consultation_result(
            attempt=attempt,
            base_fields=base_fields,
            outcome="attempt_failed",
            failure_reason_code="consultation_unavailable",
            now=now,
            rendered_text_hash=rendered_text_hash,
        )

    try:
        response = ask(question)
    except CutoverRefusal as exc:
        if str(exc) == "consultation_withdrawn":
            return _failed_consultation_result(
                attempt=attempt,
                base_fields=base_fields,
                outcome="consultation_withdrawn",
                failure_reason_code="consultation_withdrawn",
                now=now,
                rendered_text_hash=rendered_text_hash,
            )
        return _failed_consultation_result(
            attempt=attempt,
            base_fields=base_fields,
            outcome="attempt_failed",
            failure_reason_code="consultation_unavailable",
            now=now,
            rendered_text_hash=rendered_text_hash,
        )
    except Exception:
        return _failed_consultation_result(
            attempt=attempt,
            base_fields=base_fields,
            outcome="attempt_failed",
            failure_reason_code="consultation_unavailable",
            now=now,
            rendered_text_hash=rendered_text_hash,
        )

    if (
        type(response) is not bytes
        or not response
        or len(response) > s7_io.MAX_PRIVATE_FILE_BYTES
    ):
        return _failed_consultation_result(
            attempt=attempt,
            base_fields=base_fields,
            outcome="attempt_failed",
            failure_reason_code="response_unreadable",
            now=now,
            rendered_text_hash=rendered_text_hash,
        )

    raw_response_sha256 = hashlib.sha256(response).hexdigest()
    raw_response_ref = f"responses/{raw_response_sha256}.bin"
    try:
        raw_response_ref = _persist_exact_consultation_response(
            attempt=attempt,
            response=response,
            response_sha256=raw_response_sha256,
        )
        owner_visible_response = response.decode("utf-8")
        response_capture_receipt = guarded.produce_s7_response_capture_receipt(
            request_id=envelope.request_id,
            consultation_id=attempt.consultation_id,
            attempt_identity=attempt.attempt_identity,
            raw_response_ref=raw_response_ref,
            raw_response_bytes=response,
            captured_at=now,
            response_root=attempt.receipt_root,
            expected_uid=os.getuid(),
        )
    except UnicodeDecodeError:
        return _failed_consultation_result(
            attempt=attempt,
            base_fields={
                **base_fields,
                "raw_response_ref": raw_response_ref,
                "raw_response_sha256": raw_response_sha256,
            },
            outcome="attempt_failed",
            failure_reason_code="response_unreadable",
            now=now,
            rendered_text_hash=rendered_text_hash,
        )
    except (OSError, PermissionError, ValueError):
        return _failed_consultation_result(
            attempt=attempt,
            base_fields=base_fields,
            outcome="attempt_failed",
            failure_reason_code="bundle_unreservable",
            now=now,
            rendered_text_hash=rendered_text_hash,
        )

    source_ref_hash = s7.canonical_hash(
        {
            "action": envelope.action,
            "action_params_hash": action_params_hash,
            "attempt_identity": attempt.attempt_identity,
            "authority_context_hash": authority_context_hash,
            "consultation_id": attempt.consultation_id,
            "precondition_hash": envelope.precondition_hash,
            "raw_response_ref": raw_response_ref,
            "raw_response_sha256": raw_response_sha256,
            "response_capture_receipt_sha256": (
                response_capture_receipt.binding_sha256
            ),
            "rendered_text_hash": rendered_text_hash,
            "request_envelope_hash": request_envelope_hash,
            "request_id": envelope.request_id,
            "runtime_identity_hash": runtime_identity_hash,
            "runtime_source_ref": runtime_source_ref,
        }
    )
    consultation = s7.MaezVoiceConsultation(
        consultation_id=attempt.consultation_id,
        request_id=envelope.request_id,
        request_envelope_hash=request_envelope_hash,
        producer="s7_voice_consultation_turn",
        source_ref_kind="s7_voice_turn",
        source_ref_hash=source_ref_hash,
        maez_voice_consulted=True,
        maez_objection_state="not_determined",
        maez_withdrew_request=False,
        unavailable_reason_code=None,
        created_at=now,
    )
    terminal_fields = {
        **base_fields,
        "completed_at": now,
        "failure_reason_code": None,
        "maez_objection_state": "not_determined",
        "outcome": "asked_and_answered",
        "raw_response_ref": raw_response_ref,
        "raw_response_sha256": raw_response_sha256,
        "response_capture_receipt": response_capture_receipt.as_dict(),
        "source_ref_hash": source_ref_hash,
    }
    try:
        attempt_receipt_ref = _persist_consultation_receipt(
            attempt=attempt,
            relative=_attempt_terminal_ref(attempt),
            fields=terminal_fields,
        )
    except (OSError, ValueError) as exc:
        raise CutoverRefusal("bundle_unreservable") from exc

    return CutoverConsultationResult(
        outcome="asked_and_answered",
        attempt=attempt,
        consultation=consultation,
        raw_response_bytes=response,
        raw_response_ref=raw_response_ref,
        raw_response_sha256=raw_response_sha256,
        owner_visible_response=owner_visible_response,
        rendered_text_hash=rendered_text_hash,
        response_capture_receipt=response_capture_receipt,
        attempt_receipt_ref=attempt_receipt_ref,
        failure_reason_code=None,
    )


def revalidate_cutover_consultation_result(
    *,
    envelope: s7.WorkRequestEnvelope,
    consultation: s7.MaezVoiceConsultation,
    result: CutoverConsultationResult,
    bundle: guarded.S7VoiceConsultationBundle,
) -> bool:
    """Reopen and rejoin one R8 result at the consuming voice-seat gate."""

    if (
        type(envelope) is not s7.WorkRequestEnvelope
        or type(consultation) is not s7.MaezVoiceConsultation
        or type(result) is not CutoverConsultationResult
        or type(bundle) is not guarded.S7VoiceConsultationBundle
        or not _is_canonical_cutover_envelope(envelope)
        or result.outcome != "asked_and_answered"
        or result.failure_reason_code is not None
        or result.consultation != consultation
        or consultation.maez_objection_state != "not_determined"
        or consultation.maez_voice_consulted is not True
        or consultation.maez_withdrew_request is not False
        or consultation.unavailable_reason_code is not None
    ):
        return False

    attempt = result.attempt
    receipt = result.response_capture_receipt
    if (
        type(attempt) is not ConsultationAttempt
        or type(receipt) is not guarded.S7ResponseCaptureReceipt
        or attempt.request_id != envelope.request_id
        or attempt.consultation_id != envelope.maez_voice_consultation_id
        or consultation.consultation_id != attempt.consultation_id
        or result.attempt_receipt_ref != f"attempts/{attempt.attempt_identity}.terminal.json"
    ):
        return False

    request_envelope_hash = consultation.request_envelope_hash
    action_params_hash = s7.canonical_hash(dict(cm.CUTOVER_ACTION_PARAMS))
    if (
        consultation.request_id != envelope.request_id
        or consultation.request_envelope_hash != request_envelope_hash
        or consultation.producer != "s7_voice_consultation_turn"
        or consultation.source_ref_kind != "s7_voice_turn"
        or type(result.rendered_text_hash) is not str
        or type(result.raw_response_ref) is not str
        or type(result.raw_response_sha256) is not str
        or type(result.raw_response_bytes) is not bytes
        or type(result.owner_visible_response) is not str
    ):
        return False
    try:
        s7._validate_hash64(
            result.raw_response_sha256,
            field="raw_response_sha256",
        )
    except ValueError:
        return False
    if result.raw_response_ref != f"responses/{result.raw_response_sha256}.bin":
        return False
    try:
        response_bytes = s7_io.read_private_file(
            result.raw_response_ref,
            root=attempt.receipt_root,
            expected_uid=os.getuid(),
        )
        start_raw = s7_io.read_private_file(
            attempt.start_receipt_ref,
            root=attempt.receipt_root,
            expected_uid=os.getuid(),
        )
        terminal_raw = s7_io.read_private_file(
            result.attempt_receipt_ref,
            root=attempt.receipt_root,
            expected_uid=os.getuid(),
        )
        start_wrapper = json.loads(start_raw)
        terminal_wrapper = json.loads(terminal_raw)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False

    def _receipt_fields(wrapper: object, raw: bytes) -> dict[str, object] | None:
        if (
            type(wrapper) is not dict
            or set(wrapper) != {"schema", "binding_sha256", "fields"}
            or wrapper.get("schema") != _CONSULTATION_ATTEMPT_SCHEMA
            or type(wrapper.get("fields")) is not dict
        ):
            return None
        fields = wrapper["fields"]
        if _consultation_receipt_bytes(fields) != raw:
            return None
        return fields

    start_fields = _receipt_fields(start_wrapper, start_raw)
    terminal_fields = _receipt_fields(terminal_wrapper, terminal_raw)
    if start_fields is None or terminal_fields is None:
        return False

    created_at = consultation.created_at
    try:
        s7._timestamp_text(created_at, field="created_at")
        owner_visible_bytes = result.owner_visible_response.encode("utf-8")
    except (UnicodeEncodeError, ValueError):
        return False
    response_sha256 = hashlib.sha256(response_bytes).hexdigest()
    if (
        response_bytes != result.raw_response_bytes
        or owner_visible_bytes != response_bytes
        or result.raw_response_sha256 != response_sha256
        or result.raw_response_ref != f"responses/{response_sha256}.bin"
        or receipt.request_id != envelope.request_id
        or receipt.consultation_id != consultation.consultation_id
        or receipt.attempt_identity != attempt.attempt_identity
        or receipt.raw_response_ref != result.raw_response_ref
        or receipt.raw_response_sha256 != response_sha256
        or receipt.captured_at != created_at
    ):
        return False

    authority_context_hash = bundle.authority_context_hash
    runtime_identity_hash = bundle.runtime_identity_hash
    runtime_source_ref = terminal_fields.get("runtime_source_ref")
    if (
        type(authority_context_hash) is not str
        or type(runtime_identity_hash) is not str
        or type(runtime_source_ref) is not str
        or not runtime_source_ref
    ):
        return False
    question = _cutover_consultation_question(
        envelope=envelope,
        request_envelope_hash=request_envelope_hash,
        action_params_hash=action_params_hash,
        authority_context_hash=authority_context_hash,
        runtime_identity_hash=runtime_identity_hash,
        runtime_source_ref=runtime_source_ref,
    )
    rendered_text_hash = s7.rendered_text_hash(question)
    base_fields: dict[str, object] = {
        "action": cm.CUTOVER_ACTION,
        "action_params_hash": action_params_hash,
        "attempt_identity": attempt.attempt_identity,
        "authority_context_hash": authority_context_hash,
        "consultation_id": attempt.consultation_id,
        "created_at": created_at,
        "failure_reason_code": None,
        "outcome": "attempt_started",
        "precondition_hash": envelope.precondition_hash,
        "rendered_text_hash": rendered_text_hash,
        "request_envelope_hash": request_envelope_hash,
        "request_id": envelope.request_id,
        "runtime_identity_hash": runtime_identity_hash,
        "runtime_source_ref": runtime_source_ref,
    }
    source_ref_hash = s7.canonical_hash(
        {
            "action": cm.CUTOVER_ACTION,
            "action_params_hash": action_params_hash,
            "attempt_identity": attempt.attempt_identity,
            "authority_context_hash": authority_context_hash,
            "consultation_id": attempt.consultation_id,
            "precondition_hash": envelope.precondition_hash,
            "raw_response_ref": result.raw_response_ref,
            "raw_response_sha256": response_sha256,
            "response_capture_receipt_sha256": receipt.binding_sha256,
            "rendered_text_hash": rendered_text_hash,
            "request_envelope_hash": request_envelope_hash,
            "request_id": envelope.request_id,
            "runtime_identity_hash": runtime_identity_hash,
            "runtime_source_ref": runtime_source_ref,
        }
    )
    expected_consultation = s7.MaezVoiceConsultation(
        consultation_id=attempt.consultation_id,
        request_id=envelope.request_id,
        request_envelope_hash=request_envelope_hash,
        producer="s7_voice_consultation_turn",
        source_ref_kind="s7_voice_turn",
        source_ref_hash=source_ref_hash,
        maez_voice_consulted=True,
        maez_objection_state="not_determined",
        maez_withdrew_request=False,
        unavailable_reason_code=None,
        created_at=created_at,
    )
    expected_terminal = {
        **base_fields,
        "completed_at": created_at,
        "failure_reason_code": None,
        "maez_objection_state": "not_determined",
        "outcome": "asked_and_answered",
        "raw_response_ref": result.raw_response_ref,
        "raw_response_sha256": response_sha256,
        "response_capture_receipt": receipt.as_dict(),
        "source_ref_hash": source_ref_hash,
    }
    return (
        start_fields == base_fields
        and terminal_fields == expected_terminal
        and consultation == expected_consultation
        and result.rendered_text_hash == rendered_text_hash
        and bundle.source_ref_hash == source_ref_hash
        and bundle.request_id == envelope.request_id
        and bundle.consultation_id == consultation.consultation_id
        and bundle.request_envelope_hash == request_envelope_hash
        and bundle.rendered_text_hash == rendered_text_hash
        and bundle.action_params_hash == action_params_hash
        and bundle.precondition_hash == envelope.precondition_hash
        and bundle.authority_context_hash == authority_context_hash
        and bundle.maez_voice_consultation_hash == s7.maez_voice_consultation_hash(consultation)
        and bundle.runtime_identity_hash == runtime_identity_hash
        and bundle.raw_response_ref == result.raw_response_ref
        and bundle.raw_response_hash == response_sha256
        and bundle.response_capture_receipt == receipt
        and bundle.action == cm.CUTOVER_ACTION
        and bundle.schema_version == guarded.S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA
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
    print("act 2: blocked pending the owner-selected completion locator ingress.")


if __name__ == "__main__":
    main()
