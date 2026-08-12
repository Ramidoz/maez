"""CUDA cutover authority minting and presence-bound 2B orchestration.

Import is inert. The zero-parameter production entrypoint remains dormant by
construction until its fixed owner artifacts, recorded consultation, and real
founder WebAuthn presence are all available.
"""

from __future__ import annotations

import datetime
import errno
import fcntl
import hashlib
import json
import os
import secrets
import signal
import sqlite3
import stat as stat_module
import subprocess
from contextlib import closing, contextmanager
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace as dataclass_replace
from pathlib import Path
from types import FunctionType, MappingProxyType, MethodType, ModuleType, SimpleNamespace
from typing import Mapping

from core.governance import anchored_io as s7_io
from core.governance import operator_user_boundary as s7
from core.governance import s7_guarded_execution as guarded
from core.governance import s7_v2_migration as s7_migration
from core.governance import s7_webauthn_bootstrap as s7_bootstrap
from core.governance import s7_webauthn_ceremony as s7_ceremony
from scripts import cuda_bench_assemble as assemble
from scripts import cuda_migration as cm
from scripts import cuda_bench_driver as driver

BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")
RECEIPT_NAME = "command-assemble-stage1-attempt-026-terminal.json"
AUTHORIZATION_NAME = "receipts/cutover-authorization.json"
MARKER_DIR = "markers"
COMPLETION_SELECTION_NAME = "cutover-completion-selection.json"
COMPLETION_SELECTION_SCHEMA = "cuda_cutover.completion_selection.v1"
AUTHORIZATION_STORE_PATH = Path(
    "/home/rohit/maez/memory/s7_1_webauthn/ceremony.sqlite3"
)
RESPONDER_IDENTITY_DISCLAIMER = (
    "Responder identity is NOT established. "
    "The recorded runtime_identity_hash, model_routing_identity_hash, "
    "and model_config_hash do not prove responder identity."
)
_CUTOVER_ACTION_PREIMAGE_KEYS = frozenset(
    {
        "authorization_binding_sha256",
        "authorization_file_sha256",
        "cutover_action",
        "rollback_manifest_sha256",
        "stage_two_receipt_binding_sha256",
        "stage_two_receipt_file_sha256",
        "target_runtime_identity_sha256",
        "window_id",
    }
)

CUTOVER_REFUSALS = frozenset(
    {
        "authorization_boot_mismatch",
        "authorization_consumed",
        "authorization_expired",
        "authorization_expired_pre_begin",
        "authorization_expired_pre_link",
        "authorization_missing",
        "authorization_noncanonical",
        "authorization_owner_mismatch",
        "authorization_predicate",
        "authorization_wrong_type",
        "burn_content_invalid",
        "burn_receipt_unencodable",
        "burn_unrecorded_fsync",
        "burn_unrecorded_identity",
        "burn_unstaged",
        "burn_unstaged_fsync",
        "burn_unstaged_link",
        "burn_write_incomplete",
        "chronology_violation",
        "clock_regression",
        "clock_regression_pre_begin",
        "command_admission_invalid",
        "command_artifact_mismatch",
        "command_chain_mismatch",
        "command_completion_invalid",
        "completion_locator_unavailable",
        "consumer_internal_executor",
        "consumer_internal_post_pre_begin",
        "consumer_internal_pre",
        "edge_state_unreadable",
        "executor_contract",
        "executor_failed",
        "join_mismatch",
        "legacy_cutover_consumer_retired",
        "marker_dir_absent",
        "marker_dir_predicate",
        "mint_roundtrip_failed",
        "owner_presence_unattested",
        "parent_receipt_malformed",
        "parent_receipt_noncanonical",
        "parent_receipt_not_bench_passed",
        "parent_receipt_unreadable",
        "permit_unreconstructible",
        "permit_unverified",
        "preparation_failed",
        "preparation_unavailable",
        "presence_action_unauthorized",
        "presence_assertion_invalid",
        "presence_binding_mismatch",
        "presence_consumption_failed",
        "presence_credential_unscoped",
        "presence_grant_unprojectable",
        "presence_mint_failed",
        "presence_no_usable_credential",
        "presence_not_verified",
        "presence_record_invalid",
        "presence_store_corrupt",
        "presence_store_identity_mismatch",
        "presence_store_journal_posture",
        "presence_store_predicate",
        "presence_store_schema_drift",
        "presence_store_table_missing",
        "presence_store_unavailable",
        "publication_uncertain",
        "receipt_missing",
        "receipt_noncanonical",
        "receipt_predicate",
        "receipt_wrong_type",
        "recovery_copies_mismatch",
        "root_mode",
        "root_moved",
        "root_moved_post_publication",
        "root_not_directory",
        "root_ownership",
        "root_walk_failed",
        "stage2_input_missing",
        "stage2_input_predicate",
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


@dataclass(frozen=True, slots=True)
class CutoverOperationSpec:
    """One independently enumerated mutation in the closed executor program."""

    name: str
    affected_refs: tuple[str, ...]


_CUTOVER_OPERATION_SPECS = (
    CutoverOperationSpec(
        "stage_recovery_copies", ("backup:cuda_cutover_recovery",)
    ),
    CutoverOperationSpec(
        "install_cuda_override",
        (
            "file:/home/rohit/.config/systemd/user/"
            "llama-server.service.d/zz-b9596-cuda.conf",
        ),
    ),
    CutoverOperationSpec("daemon_reload", ("systemd_manager:user",)),
    CutoverOperationSpec(
        "restart_llama_server", ("service:llama-server.service",)
    ),
    CutoverOperationSpec(
        "restart_llama_judge", ("service:llama-judge.service",)
    ),
    CutoverOperationSpec("host_reboot", ("host:local",)),
)
CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS: Mapping[
    str, tuple[str, ...]
] = MappingProxyType(
    {spec.name: spec.affected_refs for spec in _CUTOVER_OPERATION_SPECS}
)
if tuple(CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS) != cm.CUTOVER_ACTION_SET:
    raise RuntimeError("cutover executor operations drifted from authorization")
if dict(CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS) != dict(
    cm.CUTOVER_OPERATION_AFFECTED_REFS
):
    raise RuntimeError("cutover executor affected refs drifted from authorization")
CUTOVER_EXECUTOR_AFFECTED_REFS = tuple(
    sorted(
        {
            ref
            for spec in _CUTOVER_OPERATION_SPECS
            for ref in spec.affected_refs
        }
    )
)


@dataclass(frozen=True, slots=True)
class ValidatedCutoverSelection:
    """The independently reconstructed stage-2 permit selected by the owner."""

    completion_locator: str
    completion: cm.CommandCompletionDoc
    admission: cm.CommandAdmissionPreimage
    receipt_ref: str
    receipt: cm.AssembleReceiptDoc
    receipt_bytes: bytes
    regenerated_receipt_bytes: bytes
    receipt_file_sha256: str
    authorization: cm.CutoverAuthorizationDoc
    authorization_file_sha256: str
    bundle: cm.BenchEvidenceBundle
    precondition_hash: str
    operation_affected_refs: Mapping[str, tuple[str, ...]]
    affected_refs: tuple[str, ...]


def _cutover_action_preimage(
    selected: object,
) -> Mapping[str, str]:
    """Return the frozen selected-cutover action preimage.

    The S7 ceremony nonce is deliberately absent: it identifies one
    ceremony attempt.  The cutover authorization (including its own nonce)
    is bound by its canonical file and document-binding hashes.
    """

    authorization = selected.authorization
    receipt = selected.receipt
    runtime_identity_doc = selected.bundle.runtime_identity_doc
    preimage = {
        "authorization_binding_sha256": authorization.binding_sha256,
        "authorization_file_sha256": selected.authorization_file_sha256,
        "cutover_action": cm.CUTOVER_ACTION,
        "rollback_manifest_sha256": authorization.rollback_manifest_sha256,
        "stage_two_receipt_binding_sha256": receipt.binding_sha256,
        "stage_two_receipt_file_sha256": selected.receipt_file_sha256,
        "target_runtime_identity_sha256": runtime_identity_doc.file_sha256,
        "window_id": authorization.window_id,
    }
    for key, value in preimage.items():
        if type(value) is not str or not value:
            raise CutoverRefusal("presence_binding_mismatch")
        if key.endswith("sha256"):
            try:
                s7._validate_hash64(value, field=key)
            except ValueError as exc:
                raise CutoverRefusal("presence_binding_mismatch") from exc
    return MappingProxyType(preimage)


def _fresh_s7_attempt_nonce() -> str:
    """A fresh artifact nonce for one ceremony attempt, never the cutover nonce."""

    return secrets.token_hex(32)


def _require_cutover_grant_binding(
    *,
    grant: s7.S7ExecutionGrant,
    selected: object,
    action_params: Mapping[str, str],
) -> None:
    """Apply v34 refusal 29h to the selected authorization preimage."""

    if (
        type(grant) is not s7.S7ExecutionGrant
        or grant.action != cm.CUTOVER_ACTION
        or grant.action_params_hash
        != s7.canonical_hash(dict(action_params))
        or grant.precondition_hash != selected.precondition_hash
        or grant.request_id != selected.authorization.window_id
    ):
        raise CutoverRefusal("presence_binding_mismatch")


def _read_selected_private_file(
    *,
    root: Path,
    expected_uid: int,
    relative: str,
    refusal: str,
    predicate_refusal: str | None = None,
) -> bytes:
    root_fd = -1
    parent_fd = -1
    leaf_fd = -1
    owned_parent = False
    try:
        root_fd = s7._open_directory_by_components(root)
        root_stat = os.fstat(root_fd)
        if (
            not stat_module.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != expected_uid
            or stat_module.S_IMODE(root_stat.st_mode) != 0o700
        ):
            raise PermissionError("selected-file root is not owner-private")
        parent_fd, leaf, owned_parent = s7_io._anchored_leaf(root_fd, relative)
        leaf_fd = os.open(
            leaf,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
        before = os.fstat(leaf_fd)
        payload = s7_io._verify_and_read(
            leaf_fd,
            before,
            relative,
            expected_uid,
        )
        after = os.fstat(leaf_fd)
        named = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        if (
            len(payload) != before.st_size
            or not _same_file_identity(after, named)
            or any(
                getattr(after, field) != getattr(named, field)
                for field in ("st_size", "st_mtime_ns", "st_ctime_ns")
            )
        ):
            raise OSError("selected file name no longer identifies held bytes")
        return payload
    except FileNotFoundError as exc:
        raise CutoverRefusal(refusal) from exc
    except (OSError, TypeError, ValueError) as exc:
        raise CutoverRefusal(predicate_refusal or refusal) from exc
    finally:
        if leaf_fd >= 0:
            os.close(leaf_fd)
        if owned_parent and parent_fd >= 0:
            os.close(parent_fd)
        if root_fd >= 0:
            os.close(root_fd)


def _require_selected_input_predicate(
    *, root: Path, expected_uid: int, relative: str
) -> None:
    """Classify fixed stage-2 input absence separately from predicates."""

    root_fd = -1
    parent_fd = -1
    leaf_fd = -1
    owned_parent = False
    try:
        root_fd = s7._open_directory_by_components(root)
        parent_fd, leaf, owned_parent = s7_io._anchored_leaf(root_fd, relative)
        try:
            leaf_fd = os.open(
                leaf,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
        except FileNotFoundError as exc:
            raise CutoverRefusal("stage2_input_missing") from exc
        held = os.fstat(leaf_fd)
        named = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat_module.S_ISREG(held.st_mode)
            or held.st_uid != expected_uid
            or stat_module.S_IMODE(held.st_mode) != 0o600
            or held.st_nlink != 1
            or not _same_file_identity(held, named)
        ):
            raise CutoverRefusal("stage2_input_predicate")
    except CutoverRefusal:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise CutoverRefusal("stage2_input_predicate") from exc
    finally:
        if leaf_fd >= 0:
            os.close(leaf_fd)
        if owned_parent and parent_fd >= 0:
            os.close(parent_fd)
        if root_fd >= 0:
            os.close(root_fd)


def _reconstruct_selected_cutover_at(
    *,
    root: Path,
    expected_uid: int,
    completion_locator: str,
    now: str,
    boot_id: str,
) -> ValidatedCutoverSelection:
    """Rebuild and re-evaluate the one completion selected by the owner."""

    try:
        completion_locator = cm._validate_private_ref(completion_locator)
    except (TypeError, ValueError) as exc:
        raise CutoverRefusal("command_completion_invalid") from exc
    completion_bytes = _read_selected_private_file(
        root=root,
        expected_uid=expected_uid,
        relative=completion_locator,
        refusal="command_completion_invalid",
    )
    try:
        completion_doc = cm._canonical_persisted_role(
            cm.PersistedDoc(completion_bytes),
            cm.CommandCompletionDoc,
        )
        completion = completion_doc.obj
    except (TypeError, ValueError) as exc:
        raise CutoverRefusal("command_completion_invalid") from exc
    if completion.command != "assemble-stage2":
        raise CutoverRefusal("command_completion_invalid")

    admission_bytes = _read_selected_private_file(
        root=root,
        expected_uid=expected_uid,
        relative=completion.admission_ref,
        refusal="command_admission_invalid",
    )
    receipt_bytes = _read_selected_private_file(
        root=root,
        expected_uid=expected_uid,
        relative=completion.artifact_ref,
        refusal="receipt_missing",
        predicate_refusal="receipt_predicate",
    )
    try:
        admission = cm.CommandAdmissionPreimage(
            selected_ref=completion.admission_ref,
            wrapper_bytes=admission_bytes,
        )
    except (TypeError, ValueError) as exc:
        raise CutoverRefusal("command_admission_invalid") from exc
    try:
        persisted_receipt = cm.PersistedDoc(receipt_bytes)
    except ValueError as exc:
        refusal = (
            "receipt_noncanonical"
            if str(exc) == "noncanonical_wrapper"
            else "receipt_wrong_type"
        )
        raise CutoverRefusal(refusal) from exc
    try:
        receipt_doc = cm._canonical_persisted_role(
            persisted_receipt,
            cm.AssembleReceiptDoc,
        )
        receipt = receipt_doc.obj
    except (TypeError, ValueError) as exc:
        raise CutoverRefusal("receipt_wrong_type") from exc

    receipt_file_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    if completion.artifact_sha256 != receipt_file_sha256:
        raise CutoverRefusal("command_artifact_mismatch")
    try:
        driver._load_verified_completion_pair(
            admission_ref=completion.admission_ref,
            completion_ref=completion_locator,
            artifact_ref=completion.artifact_ref,
            artifact_bytes=receipt_bytes,
            expected_command="assemble-stage2",
            expected_window_id=completion.window_id,
            expected_type=cm.AssembleReceiptDoc,
            root=root,
        )
    except (driver.BenchRefusal, TypeError, ValueError) as exc:
        raise CutoverRefusal("command_chain_mismatch") from exc

    authorization_bytes = _read_selected_private_file(
        root=root,
        expected_uid=expected_uid,
        relative=assemble.STAGE2_INPUTS.authorization,
        refusal="authorization_missing",
        predicate_refusal="authorization_predicate",
    )
    try:
        persisted_authorization = cm.PersistedDoc(authorization_bytes)
    except ValueError as exc:
        refusal = (
            "authorization_noncanonical"
            if str(exc) == "noncanonical_wrapper"
            else "authorization_wrong_type"
        )
        raise CutoverRefusal(refusal) from exc
    if type(persisted_authorization.obj) is not cm.CutoverAuthorizationDoc:
        raise CutoverRefusal("authorization_wrong_type")

    for field in assemble.fields(assemble.Stage2InputPaths):
        if field.name == "authorization":
            continue
        _require_selected_input_predicate(
            root=root,
            expected_uid=expected_uid,
            relative=getattr(assemble.STAGE2_INPUTS, field.name),
        )

    try:
        bundle = assemble.build_stage2_bundle(
            assemble.STAGE2_INPUTS,
            root=root,
            timestamp=receipt.timestamp,
        )
        verdict = cm.evaluate_promotion_bundle(bundle)
        regenerated = driver.ProductionArtifactPolicy().encode(
            "receipt",
            {
                **cm.build_receipt(
                    bundle,
                    verdict,
                    timestamp=bundle.timestamp,
                ),
                "binding_sha256": bundle.binding_sha256,
            },
        )
    except Exception as exc:
        raise CutoverRefusal("permit_unreconstructible") from exc
    if regenerated != receipt_bytes:
        raise CutoverRefusal("permit_unverified")
    if receipt.decision != "provisional_cuda_boot":
        raise CutoverRefusal("permit_unverified")

    authorization_doc = bundle.cutover_authorization
    if not isinstance(authorization_doc, cm.PersistedDoc) or type(
        authorization_doc.obj
    ) is not cm.CutoverAuthorizationDoc:
        raise CutoverRefusal("authorization_wrong_type")
    authorization = authorization_doc.obj
    authorization_file_sha256 = authorization_doc.file_sha256
    if (
        completion.window_id != authorization.window_id
        or receipt.cutover_window_id != authorization.window_id
        or bundle.boot_authorization.artifact_sha256
        != authorization_file_sha256
        or bundle.boot_authorization.parent_sha256
        != authorization.parent_bench_evidence_sha256
        or bundle.boot_authorization.timestamp != receipt.timestamp
        or receipt.binding_sha256 != bundle.binding_sha256
    ):
        raise CutoverRefusal("join_mismatch")
    if authorization.owner != "rohit":
        raise CutoverRefusal("authorization_owner_mismatch")
    if authorization.boot_id != boot_id:
        raise CutoverRefusal("authorization_boot_mismatch")
    try:
        if cm._compare_utc_z(now, authorization.expires_at) >= 0:
            raise CutoverRefusal("authorization_expired")
        chronology = (
            authorization.issued_at,
            admission.timestamp,
            receipt.timestamp,
            completion.timestamp,
            now,
            authorization.expires_at,
        )
        if any(
            cm._compare_utc_z(left, right) > 0
            for left, right in zip(chronology, chronology[1:], strict=False)
        ):
            raise CutoverRefusal("chronology_violation")
    except ValueError as exc:
        raise CutoverRefusal("chronology_violation") from exc

    precondition_hash = s7.canonical_hash(
        {
            "authorization_binding_sha256": authorization.binding_sha256,
            "authorization_file_sha256": authorization_file_sha256,
            "bench_evidence_sha256": receipt.bench_binding_sha256,
            "rollback_manifest_sha256": authorization.rollback_manifest_sha256,
            "stage_two_receipt_binding_sha256": receipt.binding_sha256,
            "stage_two_receipt_file_sha256": receipt_file_sha256,
            "target_runtime_identity_sha256": (
                bundle.runtime_identity_doc.file_sha256
            ),
            "window_id": authorization.window_id,
        }
    )
    return ValidatedCutoverSelection(
        completion_locator=completion_locator,
        completion=completion,
        admission=admission,
        receipt_ref=completion.artifact_ref,
        receipt=receipt,
        receipt_bytes=receipt_bytes,
        regenerated_receipt_bytes=regenerated,
        receipt_file_sha256=receipt_file_sha256,
        authorization=authorization,
        authorization_file_sha256=authorization_file_sha256,
        bundle=bundle,
        precondition_hash=precondition_hash,
        operation_affected_refs=CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS,
        affected_refs=CUTOVER_EXECUTOR_AFFECTED_REFS,
    )


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
        "_db_name",
        "_expected_uid",
        "_initial_identity",
        "_parent_chain",
        "_parent_fd",
        "consumption_connection",
        "inspection_connection",
    )

    def __init__(
        self,
        *,
        parent_chain: PinnedDirectoryChain,
        db_fd: int,
        db_name: str,
        expected_uid: int,
        initial_identity: tuple[int, int, int, int, int],
        inspection_connection: sqlite3.Connection,
        consumption_connection: sqlite3.Connection,
    ) -> None:
        self._parent_chain = parent_chain
        self._parent_fd = parent_chain.final_fd
        self._db_fd = db_fd
        self._db_name = db_name
        self._expected_uid = expected_uid
        self._initial_identity = initial_identity
        self.inspection_connection = inspection_connection
        self.consumption_connection = consumption_connection
        self._closed = False

    def require_current_named_identity(self) -> None:
        """Require the canonical name to still identify the verified inode."""

        if self._closed:
            raise CutoverRefusal("presence_store_identity_mismatch")
        try:
            s7._require_verified_held_connection(self.consumption_connection)
            if not self._parent_chain.revalidate():
                raise CutoverRefusal("presence_store_identity_mismatch")
            held = os.fstat(self._db_fd)
            named = os.stat(
                self._db_name,
                dir_fd=self._parent_fd,
                follow_symlinks=False,
            )
        except (OSError, ValueError) as exc:
            raise CutoverRefusal("presence_store_identity_mismatch") from exc
        identity = (
            held.st_dev,
            held.st_ino,
            held.st_mode,
            held.st_uid,
            held.st_nlink,
        )
        if (
            identity != self._initial_identity
            or not _same_file_identity(held, named)
            or not stat_module.S_ISREG(held.st_mode)
            or held.st_uid != self._expected_uid
            or stat_module.S_IMODE(held.st_mode) != 0o600
            or held.st_nlink != 1
        ):
            raise CutoverRefusal("presence_store_identity_mismatch")

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
                    self._parent_chain.close()


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
    parent_chain: PinnedDirectoryChain | None = None
    try:
        parent_chain = _pin_absolute_directory_chain(path.parent)
        parent_fd = parent_chain.final_fd
    except (OSError, ValueError) as exc:
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
            consumption = s7._open_s7_connection_from_held_store(
                dir_fd=parent_fd,
                store_fd=db_fd,
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
            parent_chain=parent_chain,
            db_fd=db_fd,
            db_name=path.name,
            expected_uid=expected_uid,
            initial_identity=(
                held.st_dev,
                held.st_ino,
                held.st_mode,
                held.st_uid,
                held.st_nlink,
            ),
            inspection_connection=inspection,
            consumption_connection=consumption,
        )
        parent_chain = None
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
        if parent_chain is not None:
            parent_chain.close()


class _HeldS7AuthorizationStore(s7.S7AuthorizationStore):
    """S7 mutating facade whose every transaction stays on one held inode."""

    def __init__(
        self,
        *,
        opened: ExistingAuthorizationStore,
        db_path: Path,
    ) -> None:
        self.db_path = Path(db_path)
        self._vended: set[int] = set()
        self._opened = opened

    @contextmanager
    def anchored_transaction(self):
        self._opened.require_current_named_identity()
        connection = s7._open_s7_connection_from_held_store(
            dir_fd=self._opened._parent_fd,
            store_fd=self._opened._db_fd,
        )
        connection.execute("BEGIN IMMEDIATE")
        s7._verify_held_store_activation(
            self._opened._parent_fd,
            self._opened._db_fd,
            connection,
        )
        vended_token = s7._S7VendedAnchoredConnectionToken()
        connection._s7_vended_token = vended_token
        self._vended.add(id(connection))
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            self._vended.discard(id(connection))
            vended_token.active = False
            connection._s7_vended_token = None
            connection.close()


class ExistingS7CeremonyStore(s7_bootstrap.S7WebAuthnBootstrapStore):
    """Ceremony adapter that opens an existing store and never initializes it."""

    def __init__(
        self,
        db_path: Path,
        *,
        expected_uid: int,
        opened: ExistingAuthorizationStore,
    ) -> None:
        self.root = Path(db_path).parent
        self.db_path = Path(db_path)
        self.audit_path = self.root / "ceremony.audit.jsonl"
        self._expected_uid = expected_uid
        self._opened = opened

    def close(self) -> None:
        return None

    def get_credential(
        self,
        credential_ref: str,
    ) -> s7_bootstrap.FounderWebAuthnCredentialRecord | None:
        """Read only through the held store; never Path.exists short-circuit."""

        record = super().get_credential_without_hash_check(credential_ref)
        if record is None:
            return None
        if record.record_hash != s7_bootstrap._credential_record_hash(record):
            raise RuntimeError("s7_record_hash_mismatch")
        return record

    def list_credentials(
        self,
    ) -> tuple[s7_bootstrap.FounderWebAuthnCredentialRecord, ...]:
        """Enumerate the verified held inode or surface its identity loss."""

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
            for row in rows
            for record in (self.get_credential(str(row["credential_ref"])),)
            if record is not None
        )

    def credential_recovery_state(self) -> dict[str, object]:
        """Base recovery policy without its pathname-presence shortcut."""

        records = self.list_credentials()
        active = tuple(
            record
            for record in records
            if record.enabled and "bonded_user" in record.role_names
        )
        primary = tuple(
            record for record in active if record.credential_kind == "primary"
        )
        backup = tuple(
            record for record in active if record.credential_kind == "backup"
        )
        if not active:
            with closing(self._conn()) as conn:
                bootstrap_closed_at = self._bootstrap_closed_at(conn)
            ever_primary = any(
                record.credential_kind == "primary" for record in records
            )
            ever_backup = any(
                record.credential_kind == "backup" for record in records
            )
            if not records and bootstrap_closed_at is None:
                return s7_bootstrap._manual_recovery_state(
                    "first_setup_not_started"
                )
            if bootstrap_closed_at is not None and ever_primary and ever_backup:
                return s7_bootstrap._manual_recovery_state("both_keys_lost")
            return s7_bootstrap._manual_recovery_state(
                "no_enabled_founder_credential"
            )
        confidence = s7_bootstrap._aggregate_distinct_device_confidence(backup)
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

    def _conn(self) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
        try:
            self._opened.require_current_named_identity()
            connection = s7._open_s7_connection_from_held_store(
                dir_fd=self._opened._parent_fd,
                store_fd=self._opened._db_fd,
            )
            connection.isolation_level = None
            connection.row_factory = sqlite3.Row
            opened = connection
            connection = None
            return opened
        except CutoverRefusal:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise CutoverRefusal("presence_store_unavailable") from exc
        finally:
            if connection is not None:
                connection.close()

    def _audit(self, event: str, payload: dict[str, object]) -> str:
        """Append only to the pre-existing private audit inode."""

        audit_ref = f"s7_1_bootstrap_audit:{secrets.token_hex(16)}"
        record = json.dumps(
            {"audit_ref": audit_ref, "event": event, **payload},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8") + b"\n"
        parent_fd = -1
        audit_fd = -1
        try:
            parent_fd = s7._open_directory_by_components(self.audit_path.parent)
            audit_fd = os.open(
                self.audit_path.name,
                os.O_WRONLY
                | os.O_APPEND
                | os.O_NOFOLLOW
                | os.O_NONBLOCK
                | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            held = os.fstat(audit_fd)
            named = os.stat(
                self.audit_path.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
            if (
                not stat_module.S_ISREG(held.st_mode)
                or held.st_uid != self._expected_uid
                or stat_module.S_IMODE(held.st_mode) != 0o600
                or held.st_nlink != 1
                or not _same_file_identity(held, named)
            ):
                raise CutoverRefusal("presence_store_predicate")
            view = memoryview(record)
            while view:
                written = os.write(audit_fd, view)
                if written <= 0:
                    raise OSError("short audit write")
                view = view[written:]
            os.fsync(audit_fd)
            return audit_ref
        except CutoverRefusal:
            raise
        except OSError as exc:
            raise CutoverRefusal("presence_store_unavailable") from exc
        finally:
            if audit_fd >= 0:
                os.close(audit_fd)
            if parent_fd >= 0:
                os.close(parent_fd)


class CutoverConsultationAsk:
    """One direct base-model voice turn, with honest non-identity metadata."""

    capability_kind = "bonded_runtime_voice"

    def __init__(
        self,
        *,
        envelope: s7.WorkRequestEnvelope,
        authority_context: s7.AuthorityContext,
        action_params: Mapping[str, str] | None = None,
    ) -> None:
        envelope_hash = s7.work_request_envelope_hash(envelope)
        self.request_id = envelope.request_id
        self.request_envelope_hash = envelope_hash
        self.action = envelope.action
        params_snapshot = dict(action_params or cm.CUTOVER_ACTION_PARAMS)
        self.action_params_hash = s7.canonical_hash(params_snapshot)
        self.precondition_hash = envelope.precondition_hash
        self.authority_context_hash = s7.authority_context_hash(
            authority_context
        )
        # These are the existing source-bundle labels. They are carried for
        # exact joins only; the durable disclaimer explicitly denies that
        # they establish which responder produced the bytes.
        self.runtime_identity_hash = s7.canonical_hash(
            {
                "bonded_runtime": "current",
                "request_envelope_hash": envelope_hash,
            }
        )
        self.model_routing_identity_hash = s7.canonical_hash(
            {
                "model_route": "normal",
                "request_envelope_hash": envelope_hash,
            }
        )
        self.model_config_hash = s7.canonical_hash(
            {
                "model_config": "reviewed_s7_voice_v1",
                "request_envelope_hash": envelope_hash,
            }
        )
        self.runtime_source_ref = (
            "base-model-route:core.routing.llm_client.chat"
        )

    def __call__(self, question: str) -> bytes:
        from core.routing import llm_client, model_config

        response = llm_client.chat(
            model=model_config.PRIMARY_MODEL,
            messages=[{"role": "user", "content": question}],
            stream=False,
            think=False,
            options={"temperature": 0, "top_p": 1},
        )
        content = response.message.content
        if type(content) is not str or not content:
            raise CutoverRefusal("consultation_unavailable")
        return content.encode("utf-8")


def _cutover_voice_bundle(
    *,
    envelope: s7.WorkRequestEnvelope,
    rendered: s7.RenderedRequestStatement,
    authority_context: s7.AuthorityContext,
    result: CutoverConsultationResult,
) -> tuple[
    guarded.S7VoiceConsultationBundle,
    guarded.S7VoiceSourceBundleHashBinding,
]:
    """Build the exact R8/R9 v2 bundle; no semantic reader exists here."""

    consultation = result.consultation
    receipt = result.response_capture_receipt
    if (
        result.outcome != "asked_and_answered"
        or type(consultation) is not s7.MaezVoiceConsultation
        or type(receipt) is not guarded.S7ResponseCaptureReceipt
        or result.raw_response_ref is None
        or result.raw_response_sha256 is None
    ):
        raise CutoverRefusal("bundle_unreservable")
    binding = guarded.derive_s7_voice_source_bundle_hash_binding(
        rendered_statement=rendered,
        envelope=envelope,
        maez_voice_consultation=consultation,
        authority_context=authority_context,
        precondition_hash=envelope.precondition_hash,
    )
    bundle = guarded.S7VoiceConsultationBundle(
        source_ref_hash=consultation.source_ref_hash,
        request_id=envelope.request_id,
        consultation_id=consultation.consultation_id,
        request_envelope_hash=binding.request_envelope_hash,
        rendered_text_hash=binding.rendered_text_hash,
        action_params_hash=binding.action_params_hash,
        precondition_hash=binding.precondition_hash,
        authority_context_hash=binding.authority_context_hash,
        maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
        rendered_prompt_ref=f"cutover-rendered:{envelope.request_id}",
        rendered_prompt_hash=binding.rendered_prompt_hash,
        mutation_preview_hash=binding.mutation_preview_hash,
        rollback_plan_ref=binding.rollback_plan_ref,
        context_manifest_ref=f"cutover-context:{envelope.request_id}",
        context_manifest_hash=binding.context_manifest_hash,
        runtime_identity_hash=binding.runtime_identity_hash,
        model_routing_identity_hash=binding.model_routing_identity_hash,
        model_config_hash=binding.model_config_hash,
        raw_response_ref=result.raw_response_ref,
        raw_response_hash=result.raw_response_sha256,
        semantic_reader_attempt_hash=None,
        expires_at=envelope.expires_at,
        authority_class="none",
        has_grounded_semantic_blocking_signal=False,
        source_bundle_hash=None,
        response_capture_receipt=receipt,
        action=cm.CUTOVER_ACTION,
    )
    bundle = dataclass_replace(
        bundle,
        source_bundle_hash=guarded.s7_voice_consultation_bundle_hash(bundle),
    )
    return bundle, binding


def _persist_and_validate_cutover_voice_bundle(
    *,
    authorization_store: s7.S7AuthorizationStore,
    bundle: guarded.S7VoiceConsultationBundle,
    binding: guarded.S7VoiceSourceBundleHashBinding,
    now: str,
) -> guarded.S7VoiceSourceBundleValidationResultV2:
    """Persist bundle + unreserved use together, then reread and validate."""

    bundle_use = guarded.S7VoiceBundleUse.new_unreserved(
        request_id=bundle.request_id,
        source_ref_hash=bundle.source_ref_hash,
        consultation_id=bundle.consultation_id,
        used_at=now,
    )
    try:
        with authorization_store.anchored_transaction() as conn:
            guarded.put_voice_source_bundle_v2(bundle=bundle, conn=conn)
            conn.execute(
                """
                INSERT INTO s7_voice_bundle_uses (
                    source_ref_hash, request_id, artifact_id, consultation_id,
                    bundle_use_hash, reservation_token_hash,
                    reservation_state, reserved_at, consumed_at, used_at
                ) VALUES (?, ?, NULL, ?, ?, NULL, 'unreserved', NULL, NULL, ?)
                """,
                (
                    bundle_use.source_ref_hash,
                    bundle_use.request_id,
                    bundle_use.consultation_id,
                    bundle_use.bundle_use_hash,
                    bundle_use.used_at,
                ),
            )
        with authorization_store.anchored_transaction() as conn:
            persisted, version = guarded.read_voice_source_bundle(
                source_ref_hash=bundle.source_ref_hash,
                conn=conn,
            )
            validation = guarded.validate_voice_source_bundle(
                bundle=persisted,
                version=version,
                purpose="execution",
                expected_binding=binding,
            )
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise CutoverRefusal("bundle_unreservable") from exc
    if (
        validation.status != "valid_absent"
        or validation.source_bundle_valid is not True
        or validation.mint_eligible is not True
        or validation.authority_projection != "valid_absent"
        or validation.failure_reason_code is not None
    ):
        raise CutoverRefusal("bundle_unreservable")
    return validation


def _existing_voice_bundle_use_store(
    db_path: Path,
) -> guarded.S7VoiceBundleUseStore:
    """Construct the connection-using facade without its schema initializer."""

    store = guarded.S7VoiceBundleUseStore.__new__(
        guarded.S7VoiceBundleUseStore
    )
    store.db_path = Path(db_path)
    return store


@dataclass(frozen=True, slots=True)
class PinnedFile:
    """An already-opened regular file and the identity verified at prepare."""

    label: str
    fd: int
    identity: tuple[int, int, int, int, int]
    sha256: str

    @property
    def source_fd(self) -> int:
        """Descriptor spelling used by recovery-copy commands."""

        return self.fd


@dataclass(frozen=True, slots=True)
class PinnedDirectory:
    """An already-opened directory used through its descriptor after burn."""

    label: str
    fd: int
    identity: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class PinnedDirectoryLink:
    """One held child joined to its name in a held parent directory."""

    parent_fd: int | None
    name: str
    child_fd: int
    identity: tuple[int, int, int, int, int]


class PinnedDirectoryChain:
    """Every component of the fixed bench-root/markers chain, already open."""

    __slots__ = ("_closed", "links")

    def __init__(self, links: tuple[PinnedDirectoryLink, ...]) -> None:
        if not links:
            raise ValueError("pinned directory chain cannot be empty")
        self.links = links
        self._closed = False

    @property
    def final_fd(self) -> int:
        return self.links[-1].child_fd

    def revalidate(self) -> bool:
        if self._closed:
            return False
        try:
            for link in self.links:
                held = os.fstat(link.child_fd)
                if _directory_link_identity(held) != link.identity:
                    return False
                if link.parent_fd is not None:
                    named = os.stat(
                        link.name,
                        dir_fd=link.parent_fd,
                        follow_symlinks=False,
                    )
                    if _directory_link_identity(named) != link.identity:
                        return False
        except OSError:
            return False
        return True

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for fd in sorted(
            {link.child_fd for link in self.links}, reverse=True
        ):
            try:
                os.close(fd)
            except OSError:
                pass


def _directory_link_identity(
    stat: os.stat_result,
) -> tuple[int, int, int, int, int]:
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_mode,
        stat.st_uid,
        stat.st_nlink,
    )


def _pin_absolute_directory_chain(directory: Path) -> PinnedDirectoryChain:
    """Hold and rejoin every component of one canonical absolute directory."""

    resolved = Path(directory)
    if not resolved.is_absolute():
        raise ValueError("directory chain must be absolute")
    links: list[PinnedDirectoryLink] = []
    current_fd = -1
    try:
        current_fd = os.open(
            "/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        root_stat = os.fstat(current_fd)
        links.append(
            PinnedDirectoryLink(
                parent_fd=None,
                name="/",
                child_fd=current_fd,
                identity=_directory_link_identity(root_stat),
            )
        )
        for component in resolved.parts[1:]:
            if component in {"", ".", ".."} or "\x00" in component:
                raise ValueError("invalid directory-chain component")
            child_fd = os.open(
                component,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                dir_fd=current_fd,
            )
            child_stat = os.fstat(child_fd)
            links.append(
                PinnedDirectoryLink(
                    parent_fd=current_fd,
                    name=component,
                    child_fd=child_fd,
                    identity=_directory_link_identity(child_stat),
                )
            )
            current_fd = child_fd
        chain = PinnedDirectoryChain(tuple(links))
        if not chain.revalidate():
            chain.close()
            raise OSError(errno.ESTALE, "directory chain moved while opening")
        links.clear()
        current_fd = -1
        return chain
    finally:
        if links:
            for fd in sorted(
                {link.child_fd for link in links}, reverse=True
            ):
                try:
                    os.close(fd)
                except OSError:
                    pass
        elif current_fd >= 0:
            os.close(current_fd)


def _pin_cutover_marker_chain(
    *, root: Path, expected_uid: int
) -> PinnedDirectoryChain:
    """Pin the fixed absolute root and pre-existing marker directory."""

    resolved = Path(root)
    if not resolved.is_absolute():
        raise CutoverRefusal("root_walk_failed")
    links: list[PinnedDirectoryLink] = []
    current_fd = -1
    try:
        current_fd = os.open(
            "/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        root_stat = os.fstat(current_fd)
        links.append(
            PinnedDirectoryLink(
                parent_fd=None,
                name="/",
                child_fd=current_fd,
                identity=_directory_link_identity(root_stat),
            )
        )
        for component in resolved.parts[1:]:
            if component in {"", ".", ".."} or "\x00" in component:
                raise CutoverRefusal("root_walk_failed")
            child_fd = os.open(
                component,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                dir_fd=current_fd,
            )
            child_stat = os.fstat(child_fd)
            if not stat_module.S_ISDIR(child_stat.st_mode):
                os.close(child_fd)
                raise CutoverRefusal("root_not_directory")
            links.append(
                PinnedDirectoryLink(
                    parent_fd=current_fd,
                    name=component,
                    child_fd=child_fd,
                    identity=_directory_link_identity(child_stat),
                )
            )
            current_fd = child_fd
        final_root = os.fstat(current_fd)
        if final_root.st_uid != expected_uid:
            raise CutoverRefusal("root_ownership")
        if stat_module.S_IMODE(final_root.st_mode) != 0o700:
            raise CutoverRefusal("root_mode")
        try:
            marker_fd = os.open(
                MARKER_DIR,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                dir_fd=current_fd,
            )
        except FileNotFoundError as exc:
            raise CutoverRefusal("marker_dir_absent") from exc
        except (NotADirectoryError, PermissionError) as exc:
            raise CutoverRefusal("marker_dir_predicate") from exc
        marker_stat = os.fstat(marker_fd)
        if (
            not stat_module.S_ISDIR(marker_stat.st_mode)
            or marker_stat.st_uid != expected_uid
            or stat_module.S_IMODE(marker_stat.st_mode) != 0o700
        ):
            os.close(marker_fd)
            raise CutoverRefusal("marker_dir_predicate")
        links.append(
            PinnedDirectoryLink(
                parent_fd=current_fd,
                name=MARKER_DIR,
                child_fd=marker_fd,
                identity=_directory_link_identity(marker_stat),
            )
        )
        chain = PinnedDirectoryChain(tuple(links))
        if not chain.revalidate():
            chain.close()
            raise CutoverRefusal("root_moved")
        links.clear()
        current_fd = -1
        return chain
    except CutoverRefusal:
        raise
    except NotADirectoryError as exc:
        raise CutoverRefusal("root_not_directory") from exc
    except OSError as exc:
        raise CutoverRefusal("root_walk_failed") from exc
    finally:
        if links:
            for fd in sorted(
                {link.child_fd for link in links}, reverse=True
            ):
                try:
                    os.close(fd)
                except OSError:
                    pass
        elif current_fd >= 0:
            os.close(current_fd)


@dataclass(frozen=True, slots=True)
class ResolvedUnitIdentity:
    """A unit name joined to its already-opened fragment file."""

    unit_name: str
    fragment: PinnedFile


@dataclass(frozen=True, slots=True)
class PreparedCommand:
    """One exact argv plus the executable descriptor it will use."""

    executable_fd: int
    argv: tuple[str, ...]
    child_fd_map: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedOperation:
    """One authorized mutation and all commands precomputed for it."""

    name: str
    affected_refs: tuple[str, ...]
    commands: tuple[PreparedCommand, ...]


@dataclass(frozen=True, slots=True)
class CutoverExecutionResult:
    """Content-light return if every precomputed command returned zero."""

    outcome: str
    completed_operations: tuple[str, ...]


def _cutover_consumption_receipt_bytes(
    receipt: cm.CutoverConsumptionReceipt,
) -> bytes:
    fields = {
        name: getattr(receipt, name)
        for name in receipt.__dataclass_fields__
        if name != "schema_version"
    }
    payload = cm._canonical_wrapper_bytes(
        {
            "schema": receipt.schema_version,
            "binding_sha256": receipt.binding_sha256,
            "fields": fields,
        }
    )
    rebuilt = cm.PersistedDoc(payload).obj
    if type(rebuilt) is not cm.CutoverConsumptionReceipt or rebuilt != receipt:
        raise CutoverRefusal("burn_receipt_unencodable")
    return payload


class BurnPublication:
    """A fully staged receipt plus the one exact grant use at the burn edge."""

    __slots__ = (
        "_closed",
        "_eligible",
        "_published",
        "action_params",
        "authorization",
        "clock",
        "grant",
        "marker_chain",
        "marker_name",
        "payload",
        "receipt",
        "staged_fd",
        "staged_read_fd",
    )

    def __init__(
        self,
        *,
        authorization: cm.CutoverAuthorizationDoc,
        receipt: cm.CutoverConsumptionReceipt,
        payload: bytes,
        staged_fd: int,
        staged_read_fd: int,
        marker_chain: PinnedDirectoryChain,
        grant: s7.S7ExecutionGrant,
        action_params: Mapping[str, str],
        clock: Callable[[], str],
    ) -> None:
        self.authorization = authorization
        self.receipt = receipt
        self.payload = payload
        self.staged_fd = staged_fd
        self.staged_read_fd = staged_read_fd
        self.marker_chain = marker_chain
        self.marker_name = authorization.nonce
        self.grant = grant
        self.action_params = MappingProxyType(dict(action_params))
        self.clock = clock
        self._published = False
        self._eligible = False
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            os.close(self.staged_fd)
        except OSError:
            pass
        try:
            os.close(self.staged_read_fd)
        except OSError:
            pass
        self.marker_chain.close()

    def _edge_time(self, *, after_publication: bool) -> str:
        try:
            value = self.clock()
            s7._timestamp_text(value, field="cutover edge time")
            decided_cmp = cm._compare_utc_z(self.receipt.consumed_at, value)
            expiry_cmp = cm._compare_utc_z(value, self.authorization.expires_at)
        except (OSError, TypeError, ValueError) as exc:
            raise CutoverRefusal(
                "consumer_internal_post_pre_begin"
                if after_publication
                else "edge_state_unreadable"
            ) from exc
        if decided_cmp > 0:
            raise CutoverRefusal(
                "clock_regression_pre_begin"
                if after_publication
                else "clock_regression"
            )
        if expiry_cmp >= 0:
            raise CutoverRefusal(
                "authorization_expired_pre_begin"
                if after_publication
                else "authorization_expired_pre_link"
            )
        return value

    def _published_identity_valid(self) -> bool:
        try:
            staged = os.fstat(self.staged_fd)
            named = os.stat(
                self.marker_name,
                dir_fd=self.marker_chain.final_fd,
                follow_symlinks=False,
            )
            if (
                not stat_module.S_ISREG(named.st_mode)
                or named.st_uid != os.getuid()
                or stat_module.S_IMODE(named.st_mode) != 0o600
                or named.st_nlink != 1
                or named.st_dev != staged.st_dev
                or named.st_ino != staged.st_ino
                or named.st_size != len(self.payload)
                or staged.st_size != len(self.payload)
                or os.pread(self.staged_read_fd, len(self.payload) + 1, 0)
                != self.payload
            ):
                return False
            rebuilt = cm.PersistedDoc(self.payload).obj
            return (
                type(rebuilt) is cm.CutoverConsumptionReceipt
                and rebuilt == self.receipt
            )
        except (OSError, TypeError, ValueError):
            return False

    def publish_and_validate_burn(self) -> None:
        """Apply the action grant, atomically publish, durably revalidate."""

        if self._closed or self._published:
            raise CutoverRefusal("authorization_consumed")
        if not self.marker_chain.revalidate():
            raise CutoverRefusal("root_moved")
        self._edge_time(after_publication=False)
        action_params = dict(self.action_params)

        blocked_signals = signal.valid_signals() - {
            signal.SIGKILL,
            signal.SIGSTOP,
        }
        try:
            previous_mask = signal.pthread_sigmask(
                signal.SIG_BLOCK,
                blocked_signals,
            )
        except BaseException as exc:
            raise CutoverRefusal("consumer_internal_pre") from exc
        link_error: OSError | None = None
        publication_state = "not_published"
        try:
            if not s7.consume_execution_grant_for_action(
                self.grant,
                action=cm.CUTOVER_ACTION,
                params=action_params,
            ):
                raise CutoverRefusal("presence_action_unauthorized")
            try:
                os.link(
                    f"/proc/self/fd/{self.staged_fd}",
                    self.marker_name,
                    dst_dir_fd=self.marker_chain.final_fd,
                    follow_symlinks=True,
                )
                publication_state = "published"
            except OSError as exc:
                link_error = exc
                if exc.errno == errno.EEXIST:
                    publication_state = "published"
                else:
                    try:
                        os.stat(
                            self.marker_name,
                            dir_fd=self.marker_chain.final_fd,
                            follow_symlinks=False,
                        )
                    except FileNotFoundError:
                        publication_state = (
                            "not_published"
                            if self.marker_chain.revalidate()
                            else "uncertain"
                        )
                    except OSError:
                        publication_state = "uncertain"
                    else:
                        publication_state = "published"
            self._published = publication_state != "not_published"
        finally:
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            except BaseException as exc:
                self._published = publication_state != "not_published"
                if publication_state == "uncertain":
                    raise CutoverRefusal("publication_uncertain") from exc
                raise CutoverRefusal(
                    "consumer_internal_post_pre_begin"
                    if self._published
                    else "consumer_internal_pre"
                ) from exc

        if publication_state == "uncertain":
            raise CutoverRefusal("publication_uncertain")
        if publication_state == "not_published":
            raise CutoverRefusal("burn_unstaged_link") from link_error
        if link_error is not None:
            if link_error.errno == errno.EEXIST:
                raise CutoverRefusal("authorization_consumed") from link_error
            raise CutoverRefusal("burn_unrecorded_identity") from link_error
        try:
            os.fsync(self.marker_chain.final_fd)
        except OSError as exc:
            raise CutoverRefusal("burn_unrecorded_fsync") from exc
        if not self._published_identity_valid():
            raise CutoverRefusal("burn_unrecorded_identity")
        if not self.marker_chain.revalidate():
            raise CutoverRefusal("root_moved_post_publication")
        self._edge_time(after_publication=True)
        self._eligible = True

    @property
    def eligible(self) -> bool:
        return self._eligible and self._published and not self._closed


def _stage_burn_publication(
    *,
    root: Path,
    expected_uid: int,
    authorization: cm.CutoverAuthorizationDoc,
    receipt: cm.CutoverConsumptionReceipt,
    grant: s7.S7ExecutionGrant,
    action_params: Mapping[str, str],
    clock: Callable[[], str],
) -> BurnPublication:
    """Fully realize and fsync anonymous receipt bytes before action use."""

    try:
        payload = _cutover_consumption_receipt_bytes(receipt)
    except CutoverRefusal:
        raise
    except Exception as exc:
        raise CutoverRefusal("burn_receipt_unencodable") from exc
    marker_chain = _pin_cutover_marker_chain(
        root=root,
        expected_uid=expected_uid,
    )
    staged_fd = -1
    staged_read_fd = -1
    try:
        try:
            staged_fd = driver._open_anonymous_file(
                marker_chain.final_fd,
                append=False,
            )
        except Exception as exc:
            raise CutoverRefusal("burn_unstaged") from exc
        view = memoryview(payload)
        try:
            while view:
                written = os.write(staged_fd, view)
                if written <= 0:
                    raise OSError("short write")
                view = view[written:]
        except OSError as exc:
            raise CutoverRefusal("burn_write_incomplete") from exc
        try:
            staged_read_fd = os.open(
                f"/proc/self/fd/{staged_fd}", os.O_RDONLY | os.O_CLOEXEC
            )
            held = os.fstat(staged_fd)
            held_read = os.fstat(staged_read_fd)
            if (
                held.st_nlink != 0
                or held.st_size != len(payload)
                or held_read.st_dev != held.st_dev
                or held_read.st_ino != held.st_ino
                or os.pread(staged_read_fd, len(payload) + 1, 0) != payload
                or cm.PersistedDoc(payload).obj != receipt
            ):
                raise CutoverRefusal("burn_content_invalid")
        except CutoverRefusal:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise CutoverRefusal("burn_content_invalid") from exc
        try:
            os.fsync(staged_fd)
        except OSError as exc:
            raise CutoverRefusal("burn_unstaged_fsync") from exc
        publication = BurnPublication(
            authorization=authorization,
            receipt=receipt,
            payload=payload,
            staged_fd=staged_fd,
            staged_read_fd=staged_read_fd,
            marker_chain=marker_chain,
            grant=grant,
            action_params=action_params,
            clock=clock,
        )
        staged_fd = -1
        staged_read_fd = -1
        marker_chain = None
        return publication
    finally:
        if staged_fd >= 0:
            os.close(staged_fd)
        if staged_read_fd >= 0:
            os.close(staged_read_fd)
        if marker_chain is not None:
            marker_chain.close()


class PreparedCutover:
    """Two-phase executor capability containing only already-pinned state."""

    __slots__ = (
        "_begun",
        "_burn_publication",
        "_burn_publish",
        "_burn_publish_unbound",
        "_closed",
        "_environment",
        "_execution_result_type",
        "_posix_spawn",
        "_waitpid",
        "directories",
        "executables",
        "installation_artifacts",
        "operations",
        "recovery_artifacts",
        "unit_identities",
    )

    def __init__(
        self,
        *,
        operations: tuple[PreparedOperation, ...],
        recovery_artifacts: tuple[PinnedFile, ...],
        installation_artifacts: tuple[PinnedFile, ...],
        unit_identities: tuple[ResolvedUnitIdentity, ...],
        directories: tuple[PinnedDirectory, ...],
        executables: tuple[PinnedFile, ...],
        environment: tuple[tuple[str, str], ...],
        posix_spawn: Callable[..., int],
        waitpid: Callable[[int, int], tuple[int, int]],
        burn_publication: BurnPublication | None = None,
        execution_result_type: type[CutoverExecutionResult] = CutoverExecutionResult,
        burn_publish_unbound: Callable[[BurnPublication], None] = (
            BurnPublication.publish_and_validate_burn
        ),
    ) -> None:
        if tuple(operation.name for operation in operations) != (
            cm.CUTOVER_ACTION_SET
        ):
            raise ValueError("prepared cutover operation sequence is not exact")
        if {
            operation.name: operation.affected_refs for operation in operations
        } != dict(CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS):
            raise ValueError("prepared cutover affected refs are not exact")
        self.operations = operations
        self.recovery_artifacts = recovery_artifacts
        self.installation_artifacts = installation_artifacts
        self.unit_identities = unit_identities
        self.directories = directories
        self.executables = executables
        self._environment = environment
        self._posix_spawn = posix_spawn
        self._waitpid = waitpid
        self._execution_result_type = execution_result_type
        self._burn_publication = burn_publication
        self._burn_publish_unbound = burn_publish_unbound
        self._burn_publish = (
            None
            if burn_publication is None
            else MethodType(burn_publish_unbound, burn_publication)
        )
        self._begun = False
        self._closed = False

    def __enter__(self) -> PreparedCutover:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._burn_publication is not None:
            self._burn_publication.close()
        fds = {
            pinned.fd
            for pinned in (
                *self.recovery_artifacts,
                *self.installation_artifacts,
                *(identity.fragment for identity in self.unit_identities),
                *self.executables,
            )
        } | {directory.fd for directory in self.directories}
        for fd in sorted(fds, reverse=True):
            try:
                os.close(fd)
            except OSError:
                pass

    def publish_and_validate_burn(self) -> None:
        """Publish only through the staged capability attached by production."""

        if self._burn_publication is None or self._burn_publish is None:
            raise CutoverRefusal("burn_content_invalid")
        try:
            self._burn_publish()
        except CutoverRefusal:
            self.close()
            raise
        except BaseException as exc:
            published = self._burn_publication._published
            self.close()
            raise CutoverRefusal(
                "consumer_internal_post_pre_begin"
                if published
                else "consumer_internal_pre"
            ) from exc

    def _attach_burn_publication(self, publication: BurnPublication) -> None:
        if (
            self._closed
            or self._burn_publication is not None
            or type(publication) is not BurnPublication
        ):
            raise CutoverRefusal("consumer_internal_pre")
        self._burn_publication = publication
        self._burn_publish = MethodType(
            self._burn_publish_unbound,
            publication,
        )

    def begin(self) -> CutoverExecutionResult:
        """Run the precomputed program exactly once from held capabilities."""

        if (
            self._begun
            or self._closed
            or self._burn_publication is None
            or not self._burn_publication.eligible
        ):
            raise CutoverRefusal("executor_contract")
        self._begun = True
        completed: list[str] = []
        environment = dict(self._environment)
        try:
            for operation in self.operations:
                for command in operation.commands:
                    file_actions = tuple(
                        (os.POSIX_SPAWN_DUP2, source_fd, child_fd)
                        for source_fd, child_fd in command.child_fd_map
                    )
                    pid = self._posix_spawn(
                        f"/proc/self/fd/{command.executable_fd}",
                        command.argv,
                        environment,
                        file_actions=file_actions,
                    )
                    _pid, status = self._waitpid(pid, 0)
                    if os.waitstatus_to_exitcode(status) != 0:
                        raise CutoverRefusal("executor_failed")
                completed.append(operation.name)
            result = self._execution_result_type(
                outcome="cutover_commands_completed",
                completed_operations=tuple(completed),
            )
            if type(result) is not self._execution_result_type:
                raise CutoverRefusal("executor_contract")
        except CutoverRefusal:
            raise
        except BaseException as exc:
            raise CutoverRefusal("consumer_internal_executor") from exc
        finally:
            self.close()
        return result


def _file_identity(stat: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_mode,
        stat.st_uid,
        stat.st_nlink,
    )


def _sealed_file_snapshot(*, label: str, payload: bytes) -> PinnedFile:
    """Copy exact prepared bytes into a write/grow/shrink sealed memfd."""

    fd = os.memfd_create(
        f"cuda-cutover-{label}",
        flags=os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("sealed snapshot write made no progress")
            view = view[written:]
        os.fsync(fd)
        if os.pread(fd, len(payload) + 1, 0) != payload:
            raise OSError("sealed snapshot readback mismatch")
        seals = (
            fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_SEAL
        )
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
        if fcntl.fcntl(fd, fcntl.F_GET_SEALS) != seals:
            raise OSError("sealed snapshot did not acquire the exact seals")
        held = os.fstat(fd)
        snapshot = PinnedFile(
            label=label,
            fd=fd,
            identity=_file_identity(held),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        fd = -1
        return snapshot
    finally:
        if fd >= 0:
            os.close(fd)


def _directory_identity(stat: os.stat_result) -> tuple[int, int, int, int]:
    return (stat.st_dev, stat.st_ino, stat.st_mode, stat.st_uid)


def _pin_regular_file(
    path: Path,
    *,
    label: str,
    expected_uid: int | None,
    executable: bool = False,
) -> PinnedFile:
    selected_path = path.resolve(strict=True) if executable else path
    fd = -1
    try:
        fd = os.open(selected_path, os.O_RDONLY | os.O_NOFOLLOW)
        held = os.fstat(fd)
        if (
            not stat_module.S_ISREG(held.st_mode)
            or held.st_nlink < 1
            or (expected_uid is not None and held.st_uid != expected_uid)
            or (held.st_mode & 0o022) != 0
            or (executable and (held.st_mode & 0o111) == 0)
        ):
            raise PermissionError(f"{label} is not a pinned private file")
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        offset = 0
        while True:
            chunk = os.pread(fd, 1024 * 1024, offset)
            if not chunk:
                break
            digest.update(chunk)
            chunks.append(chunk)
            offset += len(chunk)
        after = os.fstat(fd)
        named = os.stat(selected_path, follow_symlinks=False)
        if _file_identity(named) != _file_identity(held) or any(
            getattr(held, field) != getattr(after, field)
            for field in ("st_size", "st_mtime_ns", "st_ctime_ns")
        ):
            raise OSError(f"{label} changed while it was pinned")
        if expected_uid is not None:
            snapshot = _sealed_file_snapshot(
                label=label,
                payload=b"".join(chunks),
            )
            os.close(fd)
            fd = -1
            return snapshot
        os.set_inheritable(fd, False)
        pinned = PinnedFile(
            label=label,
            fd=fd,
            identity=_file_identity(held),
            sha256=digest.hexdigest(),
        )
        fd = -1
        return pinned
    finally:
        if fd >= 0:
            os.close(fd)


def _pin_directory(
    path: Path, *, label: str, expected_uid: int
) -> PinnedDirectory:
    fd = -1
    try:
        fd = s7._open_directory_by_components(path)
        held = os.fstat(fd)
        if (
            not stat_module.S_ISDIR(held.st_mode)
            or held.st_uid != expected_uid
            or (held.st_mode & 0o022) != 0
        ):
            raise PermissionError(f"{label} is not an owner-private directory")
        os.set_inheritable(fd, False)
        pinned = PinnedDirectory(
            label=label,
            fd=fd,
            identity=_directory_identity(held),
        )
        fd = -1
        return pinned
    finally:
        if fd >= 0:
            os.close(fd)


def _prepare_cutover_resources_at(
    *,
    recovery_sources: tuple[tuple[Path, str], ...],
    recovery_directory: Path,
    override_source: Path,
    override_directory: Path,
    unit_fragments: Mapping[str, Path],
    install_executable: Path,
    systemctl_executable: Path,
    expected_uid: int,
    burn_publish_unbound: Callable[[BurnPublication], None] = (
        BurnPublication.publish_and_validate_burn
    ),
) -> PreparedCutover:
    """Testable preparation core; every input is fully resolved before return."""

    if tuple(leaf for _path, leaf in recovery_sources) != (
        "llama-server.service",
        "mtp.conf",
    ) or tuple(unit_fragments) != (
        "llama-server.service",
        "llama-judge.service",
    ):
        raise CutoverRefusal("consumer_internal_pre")
    pinned: list[PinnedFile] = []
    directories: list[PinnedDirectory] = []
    try:
        recovery_artifacts = tuple(
            _pin_regular_file(
                path,
                label=f"recovery-source:{leaf}",
                expected_uid=expected_uid,
            )
            for path, leaf in recovery_sources
        )
        pinned.extend(recovery_artifacts)
        override = _pin_regular_file(
            override_source,
            label="cuda-override-source",
            expected_uid=expected_uid,
        )
        pinned.append(override)
        unit_identities = tuple(
            ResolvedUnitIdentity(
                unit_name=unit_name,
                fragment=_pin_regular_file(
                    fragment_path,
                    label=f"unit-fragment:{unit_name}",
                    expected_uid=expected_uid,
                ),
            )
            for unit_name, fragment_path in unit_fragments.items()
        )
        pinned.extend(identity.fragment for identity in unit_identities)
        recovery_dir = _pin_directory(
            recovery_directory,
            label="cutover-recovery-directory",
            expected_uid=expected_uid,
        )
        override_dir = _pin_directory(
            override_directory,
            label="systemd-user-override-directory",
            expected_uid=expected_uid,
        )
        directories.extend((recovery_dir, override_dir))
        install = _pin_regular_file(
            install_executable,
            label="install-executable",
            expected_uid=None,
            executable=True,
        )
        systemctl = _pin_regular_file(
            systemctl_executable,
            label="systemctl-executable",
            expected_uid=None,
            executable=True,
        )
        pinned.extend((install, systemctl))

        source_fds = {
            artifact.fd
            for artifact in (
                *recovery_artifacts,
                override,
                *(identity.fragment for identity in unit_identities),
                install,
                systemctl,
            )
        } | {recovery_dir.fd, override_dir.fd}
        # posix_spawn applies DUP2 actions in order. A fixed destination can
        # therefore overwrite a later source when the parent already holds
        # that number. Allocate every child-visible descriptor strictly above
        # the complete prepared source set before rendering argv.
        child_fd_base = max(source_fds, default=2) + 16
        recovery_source_child_fds = (
            child_fd_base,
            child_fd_base + 1,
        )
        recovery_dir_child_fd = child_fd_base + 2
        override_source_child_fd = child_fd_base + 3
        override_dir_child_fd = child_fd_base + 4

        recovery_commands = tuple(
            PreparedCommand(
                executable_fd=install.fd,
                argv=(
                    "install",
                    "-m",
                    "0600",
                    f"/proc/self/fd/{recovery_source_child_fds[index]}",
                    f"/proc/self/fd/{recovery_dir_child_fd}/{leaf}",
                ),
                child_fd_map=(
                    (artifact.source_fd, recovery_source_child_fds[index]),
                    (recovery_dir.fd, recovery_dir_child_fd),
                ),
            )
            for index, (artifact, (_path, leaf)) in enumerate(
                zip(
                    recovery_artifacts,
                    recovery_sources,
                    strict=True,
                )
            )
        )
        operations = (
            PreparedOperation(
                name="stage_recovery_copies",
                affected_refs=CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS[
                    "stage_recovery_copies"
                ],
                commands=recovery_commands,
            ),
            PreparedOperation(
                name="install_cuda_override",
                affected_refs=CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS[
                    "install_cuda_override"
                ],
                commands=(
                    PreparedCommand(
                        executable_fd=install.fd,
                        argv=(
                            "install",
                            "-m",
                            "0600",
                            f"/proc/self/fd/{override_source_child_fd}",
                            f"/proc/self/fd/{override_dir_child_fd}/"
                            "zz-b9596-cuda.conf",
                        ),
                        child_fd_map=(
                            (override.fd, override_source_child_fd),
                            (override_dir.fd, override_dir_child_fd),
                        ),
                    ),
                ),
            ),
            PreparedOperation(
                name="daemon_reload",
                affected_refs=CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS[
                    "daemon_reload"
                ],
                commands=(
                    PreparedCommand(
                        executable_fd=systemctl.fd,
                        argv=("systemctl", "--user", "daemon-reload"),
                    ),
                ),
            ),
            PreparedOperation(
                name="restart_llama_server",
                affected_refs=CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS[
                    "restart_llama_server"
                ],
                commands=(
                    PreparedCommand(
                        executable_fd=systemctl.fd,
                        argv=(
                            "systemctl",
                            "--user",
                            "restart",
                            "llama-server.service",
                        ),
                    ),
                ),
            ),
            PreparedOperation(
                name="restart_llama_judge",
                affected_refs=CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS[
                    "restart_llama_judge"
                ],
                commands=(
                    PreparedCommand(
                        executable_fd=systemctl.fd,
                        argv=(
                            "systemctl",
                            "--user",
                            "restart",
                            "llama-judge.service",
                        ),
                    ),
                ),
            ),
            PreparedOperation(
                name="host_reboot",
                affected_refs=CUTOVER_EXECUTOR_OPERATION_AFFECTED_REFS[
                    "host_reboot"
                ],
                commands=(
                    PreparedCommand(
                        executable_fd=systemctl.fd,
                        argv=("systemctl", "reboot"),
                    ),
                ),
            ),
        )
        environment = tuple(
            (name, os.environ[name])
            for name in (
                "DBUS_SESSION_BUS_ADDRESS",
                "HOME",
                "LANG",
                "LC_ALL",
                "PATH",
                "XDG_RUNTIME_DIR",
            )
            if name in os.environ
        )
        prepared = PreparedCutover(
            operations=operations,
            recovery_artifacts=recovery_artifacts,
            installation_artifacts=(override,),
            unit_identities=unit_identities,
            directories=tuple(directories),
            executables=(install, systemctl),
            environment=environment,
            posix_spawn=os.posix_spawn,
            waitpid=os.waitpid,
            burn_publish_unbound=burn_publish_unbound,
        )
        pinned.clear()
        directories.clear()
        return prepared
    except CutoverRefusal:
        raise
    except Exception as exc:
        raise CutoverRefusal("consumer_internal_pre") from exc
    finally:
        for resource in pinned:
            try:
                os.close(resource.fd)
            except OSError:
                pass
        for resource in directories:
            try:
                os.close(resource.fd)
            except OSError:
                pass


def _resolve_user_unit_fragments(
    unit_names: tuple[str, ...],
) -> Mapping[str, Path]:
    """Resolve exact loaded unit fragments before the burn boundary."""

    systemctl = Path("/usr/bin/systemctl").resolve(strict=True)
    resolved: dict[str, Path] = {}
    for unit_name in unit_names:
        values: dict[str, str] = {}
        for property_name in ("Id", "LoadState", "FragmentPath"):
            completed = subprocess.run(
                (
                    str(systemctl),
                    "--user",
                    "show",
                    unit_name,
                    f"--property={property_name}",
                    "--value",
                ),
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            values[property_name] = completed.stdout.strip()
        if (
            values["Id"] != unit_name
            or values["LoadState"] != "loaded"
            or not values["FragmentPath"].startswith("/")
        ):
            raise CutoverRefusal("consumer_internal_pre")
        resolved[unit_name] = Path(values["FragmentPath"])
    return MappingProxyType(resolved)


def _bind_selected_cutover_preparer(
    *,
    reconstruct: Callable[..., ValidatedCutoverSelection],
    resolve_units: Callable[[tuple[str, ...]], Mapping[str, Path]],
    prepare_resources: Callable[..., PreparedCutover],
    authorize_and_stage: Callable[..., PreparedCutover],
    now_z: Callable[[], str],
    burn_publish_unbound: Callable[[BurnPublication], None],
):
    """Close the production preparer over its tracked top-level graph."""

    fixed_root = Path(BENCH_ROOT)
    fixed_expected_uid = os.getuid()
    boot_id_path = Path("/proc/sys/kernel/random/boot_id")
    recovery_sources = (
        (
            Path("/home/rohit/.config/systemd/user/llama-server.service"),
            "llama-server.service",
        ),
        (
            Path(
                "/home/rohit/.config/systemd/user/"
                "llama-server.service.d/mtp.conf"
            ),
            "mtp.conf",
        ),
    )
    recovery_directory = fixed_root / "recovery"
    override_source = Path(
        "/home/rohit/maez/config/systemd/"
        "llama-server-b9596-cuda.override.conf"
    )
    override_directory = Path(
        "/home/rohit/.config/systemd/user/llama-server.service.d"
    )
    install_executable = Path("/usr/bin/install")
    systemctl_executable = Path("/usr/bin/systemctl")
    unit_names = ("llama-server.service", "llama-judge.service")
    frozen_unit_hash = cm.FROZEN_VULKAN_UNIT_SHA256
    frozen_dropin_hash = cm.FROZEN_VULKAN_DROPIN_SHA256

    def _prepare_selected_cutover(completion_locator: str) -> PreparedCutover:
        prepared: PreparedCutover | None = None
        try:
            try:
                boot_id = boot_id_path.read_text().strip()
            except OSError as exc:
                raise CutoverRefusal("edge_state_unreadable") from exc
            selected = reconstruct(
                root=fixed_root,
                expected_uid=fixed_expected_uid,
                completion_locator=completion_locator,
                now=now_z(),
                boot_id=boot_id,
            )
            unit_fragments = resolve_units(unit_names)
            prepared = prepare_resources(
                recovery_sources=recovery_sources,
                recovery_directory=recovery_directory,
                override_source=override_source,
                override_directory=override_directory,
                unit_fragments=unit_fragments,
                install_executable=install_executable,
                systemctl_executable=systemctl_executable,
                expected_uid=fixed_expected_uid,
                burn_publish_unbound=burn_publish_unbound,
            )
            expected_override_hash = getattr(
                selected.bundle.runtime_identity,
                "production_override_sha256",
                None,
            )
            if not (
                prepared.recovery_artifacts[0].sha256 == frozen_unit_hash
                and prepared.recovery_artifacts[1].sha256 == frozen_dropin_hash
                and len(prepared.installation_artifacts) == 1
                and prepared.installation_artifacts[0].label
                == "cuda-override-source"
                and prepared.installation_artifacts[0].sha256
                == expected_override_hash
            ):
                raise CutoverRefusal("consumer_internal_pre")
            return authorize_and_stage(selected=selected, prepared=prepared)
        except CutoverRefusal:
            if prepared is not None:
                prepared.close()
            raise
        except BaseException as exc:
            if prepared is not None:
                prepared.close()
            raise CutoverRefusal("consumer_internal_pre") from exc

    return _prepare_selected_cutover


def _read_completion_locator_at(root: Path, expected_uid: int) -> str:
    """Read the canonical owner selection below a caller-supplied test root."""

    root_fd = -1
    selected_fd = -1
    try:
        root_fd = s7._open_directory_by_components(Path(root))
        root_stat = os.fstat(root_fd)
        if (
            not stat_module.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != expected_uid
            or stat_module.S_IMODE(root_stat.st_mode) != 0o700
        ):
            raise PermissionError("selection root is not owner-private")
        selected_fd = os.open(
            COMPLETION_SELECTION_NAME,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=root_fd,
        )
        before = os.fstat(selected_fd)
        raw = s7_io._verify_and_read(
            selected_fd,
            before,
            COMPLETION_SELECTION_NAME,
            expected_uid,
        )
        named = os.stat(
            COMPLETION_SELECTION_NAME,
            dir_fd=root_fd,
            follow_symlinks=False,
        )
        if not _same_file_identity(before, named) or any(
            getattr(before, field) != getattr(named, field)
            for field in ("st_size", "st_mtime_ns", "st_ctime_ns")
        ):
            raise OSError("selection name no longer identifies held file")

        wrapper = json.loads(raw)
        if (
            type(wrapper) is not dict
            or set(wrapper) != {"fields", "schema"}
            or wrapper.get("schema") != COMPLETION_SELECTION_SCHEMA
            or type(wrapper.get("fields")) is not dict
            or set(wrapper["fields"]) != {"completion_locator"}
        ):
            raise ValueError("completion selection is malformed")
        locator = cm._validate_private_ref(
            wrapper["fields"].get("completion_locator")
        )
        driver._relative_parts(locator)
        if raw != cm._canonical_wrapper_bytes(wrapper):
            raise ValueError("completion selection is noncanonical")
        return locator
    except CutoverRefusal:
        raise
    except (
        OSError,
        TypeError,
        ValueError,
        RecursionError,
        driver.BenchRefusal,
    ) as exc:
        raise CutoverRefusal("completion_locator_unavailable") from exc
    finally:
        if selected_fd >= 0:
            os.close(selected_fd)
        if root_fd >= 0:
            os.close(root_fd)


def _bind_owner_completion_locator_reader():
    """Bind the production reader to one root without an injection surface."""

    fixed_root = Path(BENCH_ROOT)
    fixed_expected_uid = os.getuid()
    read_completion_locator_at = _read_completion_locator_at

    def _read_owner_completion_locator() -> str:
        """Read the one fixed owner-selected completion locator."""

        return read_completion_locator_at(fixed_root, fixed_expected_uid)

    return _read_owner_completion_locator


_read_owner_completion_locator = _bind_owner_completion_locator_reader()
del _bind_owner_completion_locator_reader


def _bind_cutover_entrypoint(
    *,
    prepare_selected_cutover: Callable[[str], PreparedCutover],
    prepared_type: type[PreparedCutover],
    publish_unbound: Callable[[PreparedCutover], None],
    begin_unbound: Callable[[PreparedCutover], CutoverExecutionResult],
    execution_result_type: type[CutoverExecutionResult],
    refusal_type: type[CutoverRefusal],
):
    """Close execution over tracked implementations, never provider globals."""

    read_owner_completion_locator = _read_owner_completion_locator
    method_type = MethodType

    def execute_cutover() -> object:
        """Read owner selection, prepare, burn, then call the pre-bound executor."""

        completion_locator = read_owner_completion_locator()
        prepared = prepare_selected_cutover(completion_locator)
        if type(prepared) is not prepared_type:
            raise refusal_type("preparation_failed")
        if prepared._execution_result_type is not execution_result_type:
            raise refusal_type("preparation_failed")
        begin = method_type(begin_unbound, prepared)
        publish_and_validate_burn = method_type(publish_unbound, prepared)
        publish_and_validate_burn()
        return begin()

    return execute_cutover


def _now_z() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _ensure_private_consultation_subdir(root: Path, name: str) -> None:
    root_fd = s7._open_directory_by_components(root)
    try:
        held = os.fstat(root_fd)
        if (
            held.st_uid != os.getuid()
            or stat_module.S_IMODE(held.st_mode) != 0o700
        ):
            raise PermissionError("consultation receipt root is not owner-private")
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
    model_routing_identity_hash: str,
    model_config_hash: str,
    runtime_source_ref: str,
    action_params: Mapping[str, str] | None = None,
) -> str:
    affected = "\n".join(f"- {ref}" for ref in envelope.affected_refs) or "- none"
    params_text = json.dumps(
        dict(action_params or cm.CUTOVER_ACTION_PARAMS),
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
            f"Model routing identity hash: {model_routing_identity_hash}",
            f"Model config hash: {model_config_hash}",
            f"Runtime source ref: {runtime_source_ref}",
            "Affected refs:",
            affected,
            "What do you want the owner to understand about this exact proposed "
            "change before deciding whether to tap?",
        )
    )


def _is_canonical_cutover_envelope(
    envelope: s7.WorkRequestEnvelope,
    *,
    action_params: Mapping[str, str] | None = None,
) -> bool:
    try:
        params_snapshot = dict(action_params or cm.CUTOVER_ACTION_PARAMS)
        if action_params is not None and params_snapshot != cm.CUTOVER_ACTION_PARAMS:
            if (
                set(params_snapshot) != _CUTOVER_ACTION_PREIMAGE_KEYS
                or params_snapshot.get("cutover_action") != cm.CUTOVER_ACTION
                or params_snapshot.get("window_id") != envelope.request_id
            ):
                return False
            for key in _CUTOVER_ACTION_PREIMAGE_KEYS:
                if key.endswith("sha256"):
                    s7._validate_hash64(params_snapshot[key], field=key)
        expected = s7.build_work_request_envelope(
            request_id=envelope.request_id,
            action=cm.CUTOVER_ACTION,
            params=params_snapshot,
            claimed_work_class="self_modification",
            requesting_subsystem="cuda_cutover",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="model_routing_change",
            why_self_fix_failed_class="not_self_fix",
            affected_refs=CUTOVER_EXECUTOR_AFFECTED_REFS,
            content_exposure_risk="content_free",
            precondition_hash=envelope.precondition_hash,
            created_at=envelope.created_at,
            expires_at=envelope.expires_at,
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            maez_voice_consultation_id=envelope.maez_voice_consultation_id or "",
            free_text_ref_hash=None,
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
    action_params: Mapping[str, str] | None = None,
) -> CutoverConsultationResult:
    """Ask once, preserve exact bytes, and record no machine interpretation."""

    if not isinstance(envelope, s7.WorkRequestEnvelope):
        raise ValueError("cutover consultation requires WorkRequestEnvelope")
    if not isinstance(attempt, ConsultationAttempt):
        raise ValueError("cutover consultation requires ConsultationAttempt")
    s7._timestamp_text(now, field="now")

    request_envelope_hash = s7.canonical_hash(asdict(envelope))
    action_params_snapshot = dict(action_params or cm.CUTOVER_ACTION_PARAMS)
    action_params_hash = s7.canonical_hash(action_params_snapshot)
    authority_context_hash = _ask_text_attr(ask, "authority_context_hash")
    runtime_identity_hash = _ask_text_attr(ask, "runtime_identity_hash")
    model_routing_identity_hash = _ask_text_attr(
        ask, "model_routing_identity_hash"
    )
    model_config_hash = _ask_text_attr(ask, "model_config_hash")
    runtime_source_ref = _ask_text_attr(ask, "runtime_source_ref")
    question = _cutover_consultation_question(
        envelope=envelope,
        request_envelope_hash=request_envelope_hash,
        action_params_hash=action_params_hash,
        authority_context_hash=authority_context_hash or "unavailable",
        runtime_identity_hash=runtime_identity_hash or "unavailable",
        model_routing_identity_hash=(
            model_routing_identity_hash or "unavailable"
        ),
        model_config_hash=model_config_hash or "unavailable",
        runtime_source_ref=runtime_source_ref or "unavailable",
        action_params=action_params_snapshot,
    )
    rendered_text_hash = s7.rendered_text_hash(question)
    base_fields: dict[str, object] = {
        "action": envelope.action,
        "action_params_hash": action_params_hash,
        "action_params": action_params_snapshot,
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
        "responder_identity_disclaimer": RESPONDER_IDENTITY_DISCLAIMER,
        "responder_identity_established": False,
        "model_config_hash": model_config_hash,
        "model_routing_identity_hash": model_routing_identity_hash,
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
        _is_canonical_cutover_envelope(
            envelope,
            action_params=action_params_snapshot,
        )
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
        if model_routing_identity_hash is None:
            raise ValueError("model_routing_identity_hash unavailable")
        s7._validate_hash64(
            model_routing_identity_hash,
            field="model_routing_identity_hash",
        )
        if model_config_hash is None:
            raise ValueError("model_config_hash unavailable")
        s7._validate_hash64(model_config_hash, field="model_config_hash")
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
            "model_config_hash": model_config_hash,
            "model_routing_identity_hash": model_routing_identity_hash,
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
    action_params_hash = bundle.action_params_hash
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
    action_params = terminal_fields.get("action_params")
    if (
        type(action_params) is not dict
        or action_params != start_fields.get("action_params")
        or action_params.get("cutover_action") != cm.CUTOVER_ACTION
        or any(type(key) is not str or type(value) is not str for key, value in action_params.items())
        or s7.canonical_hash(action_params) != action_params_hash
        or not _is_canonical_cutover_envelope(
            envelope,
            action_params=action_params,
        )
    ):
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
    model_routing_identity_hash = bundle.model_routing_identity_hash
    model_config_hash = bundle.model_config_hash
    runtime_source_ref = terminal_fields.get("runtime_source_ref")
    if (
        type(authority_context_hash) is not str
        or type(runtime_identity_hash) is not str
        or type(model_routing_identity_hash) is not str
        or type(model_config_hash) is not str
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
        model_routing_identity_hash=model_routing_identity_hash or "unavailable",
        model_config_hash=model_config_hash or "unavailable",
        runtime_source_ref=runtime_source_ref,
        action_params=action_params,
    )
    rendered_text_hash = s7.rendered_text_hash(question)
    base_fields: dict[str, object] = {
        "action": cm.CUTOVER_ACTION,
        "action_params": action_params,
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
        "responder_identity_disclaimer": RESPONDER_IDENTITY_DISCLAIMER,
        "responder_identity_established": False,
        "model_config_hash": model_config_hash,
        "model_routing_identity_hash": model_routing_identity_hash,
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
            "model_config_hash": model_config_hash,
            "model_routing_identity_hash": model_routing_identity_hash,
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


def _authority_context_for_cutover_credential(
    *,
    credential: s7_bootstrap.FounderWebAuthnCredentialRecord,
    now: str,
    expires_at: str,
) -> s7.AuthorityContext:
    if (
        credential.enabled is not True
        or "bonded_user" not in credential.role_names
    ):
        raise CutoverRefusal("presence_credential_unscoped")
    return s7.AuthorityContext(
        actor_id="founder",
        actor_handle_hmac=credential.actor_handle_hmac,
        role_names=tuple(credential.role_names),
        grant_source="founder_webauthn",
        allowed_scopes=("operator_health",),
        auth_method="founder_webauthn",
        surface="cockpit",
        credential_ref=credential.credential_ref,
        created_at=now,
        expires_at=expires_at,
        verified=True,
        verification_reason="founder_local_webauthn_challenge_pending",
    )


def _select_cutover_credential(
    credentials: tuple[s7_bootstrap.FounderWebAuthnCredentialRecord, ...],
) -> s7_bootstrap.FounderWebAuthnCredentialRecord:
    usable = tuple(
        record
        for record in credentials
        if record.enabled and "bonded_user" in record.role_names
    )
    if not usable:
        raise CutoverRefusal("presence_no_usable_credential")
    if len(usable) == 1:
        return usable[0]
    print(
        json.dumps(
            {
                "cutover_credential_selection_required": [
                    {
                        "credential_kind": record.credential_kind,
                        "credential_ref": record.credential_ref,
                        "label": record.label,
                    }
                    for record in usable
                ]
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        selected = input("credential_ref> ")
    except (EOFError, KeyboardInterrupt) as exc:
        raise CutoverRefusal("owner_presence_unattested") from exc
    matches = tuple(
        record for record in usable if record.credential_ref == selected
    )
    if len(matches) != 1:
        raise CutoverRefusal("presence_credential_unscoped")
    return matches[0]


def _read_owner_webauthn_finish(
    *,
    selected_credential_ref: str,
    challenge_id: str,
    response_sha256: str,
) -> dict[str, object]:
    """Read the actual browser-produced assertion after owner review."""

    try:
        raw = input("webauthn_finish_json> ")
        request = json.loads(raw)
    except (EOFError, KeyboardInterrupt, json.JSONDecodeError) as exc:
        raise CutoverRefusal("owner_presence_unattested") from exc
    if (
        type(request) is not dict
        or request.get("challenge_id") != challenge_id
        or request.get("credential_ref") != selected_credential_ref
        or request.get("maez_voice_raw_response_hash") != response_sha256
        or type(request.get("authentication_response")) is not dict
    ):
        raise CutoverRefusal("owner_presence_unattested")
    return request


def _print_owner_cutover_gate(
    *,
    result: CutoverConsultationResult,
    rendered: s7.RenderedRequestStatement,
    begin_body: Mapping[str, object],
) -> None:
    """Surface exact recorded bytes and signed material before any tap."""

    if (
        result.owner_visible_response is None
        or result.raw_response_sha256 is None
    ):
        raise CutoverRefusal("consultation_unavailable")
    print(
        json.dumps(
            {
                "maez_response_exact": result.owner_visible_response,
                "maez_response_sha256": result.raw_response_sha256,
                "public_key_options": begin_body.get("public_key_options"),
                "rendered_authorization": rendered.rendered_text,
                "responder_identity_disclaimer": (
                    RESPONDER_IDENTITY_DISCLAIMER
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )


def _map_presence_finish_refusal(
    result: s7_ceremony.S7CeremonyServiceResult,
) -> CutoverRefusal:
    error = str(result.body.get("error") or "")
    if error in {"s7_credential_disabled", "s7_credential_setup_incomplete"}:
        return CutoverRefusal("presence_credential_unscoped")
    if error in {
        "s7_guarded_source_bundle_required",
        "s7_guarded_state_store_required",
    }:
        return CutoverRefusal("presence_mint_failed")
    return CutoverRefusal("presence_assertion_invalid")


def _classify_failed_cutover_consumption(
    *,
    connection: sqlite3.Connection,
    artifact_id: str,
    selected: object,
    action_params: Mapping[str, str],
    now: str,
) -> CutoverRefusal:
    """Preserve A7 facts observable after an atomic consume returned none."""

    try:
        row = connection.execute(
            """
            SELECT request_id, action_params_hash, precondition_hash, action,
                   user_presence, user_verification, consumed_at, expires_at
            FROM s7_authorization_artifacts_v2
            WHERE artifact_id = ?
            """,
            (artifact_id,),
        ).fetchone()
    except sqlite3.Error:
        return CutoverRefusal("presence_consumption_failed")
    if row is None:
        return CutoverRefusal("presence_assertion_invalid")
    if row[4] != 1 or row[5] != 1:
        return CutoverRefusal("presence_not_verified")
    if (
        row[0] != selected.authorization.window_id
        or row[1] != s7.canonical_hash(dict(action_params))
        or row[2] != selected.precondition_hash
        or row[3] != cm.CUTOVER_ACTION
    ):
        return CutoverRefusal("presence_binding_mismatch")
    try:
        if row[6] is not None or cm._compare_utc_z(now, row[7]) >= 0:
            return CutoverRefusal("presence_assertion_invalid")
    except (TypeError, ValueError):
        return CutoverRefusal("presence_assertion_invalid")
    return CutoverRefusal("presence_consumption_failed")


def _authorize_and_stage_selected_cutover(
    *,
    selected: ValidatedCutoverSelection,
    prepared: PreparedCutover,
) -> PreparedCutover:
    """Real R8/R9 consultation, founder ceremony, committed consume, stage."""

    db_path = Path(AUTHORIZATION_STORE_PATH)
    expected_uid = os.getuid()
    ceremony_store: ExistingS7CeremonyStore | None = None
    with open_existing_authorization_store(
        db_path=db_path,
        expected_uid=expected_uid,
    ) as opened:
        action_params = _cutover_action_preimage(selected)
        ceremony_store = ExistingS7CeremonyStore(
            db_path,
            expected_uid=expected_uid,
            opened=opened,
        )
        try:
            try:
                credential = _select_cutover_credential(
                    ceremony_store.list_credentials()
                )
            except CutoverRefusal:
                raise
            except RuntimeError as exc:
                raise CutoverRefusal("presence_record_invalid") from exc

            consultation_now = _now_z()
            authority_context = _authority_context_for_cutover_credential(
                credential=credential,
                now=consultation_now,
                expires_at=selected.authorization.expires_at,
            )
            attempt = ConsultationAttempt.fresh(
                request_id=selected.authorization.window_id,
                receipt_root=BENCH_ROOT,
            )
            envelope = s7.build_work_request_envelope(
                request_id=selected.authorization.window_id,
                action=cm.CUTOVER_ACTION,
                params=dict(action_params),
                claimed_work_class="self_modification",
                requesting_subsystem="cuda_cutover",
                closed_symptom_code="self_mod_requested",
                proposed_change_class="model_routing_change",
                why_self_fix_failed_class="not_self_fix",
                affected_refs=selected.affected_refs,
                content_exposure_risk="content_free",
                precondition_hash=selected.precondition_hash,
                created_at=selected.authorization.issued_at,
                expires_at=selected.authorization.expires_at,
                predicted_effect_class="behavior_change",
                rollback_path_class="revert_patch",
                maez_voice_consultation_id=attempt.consultation_id,
                free_text_ref_hash=None,
            )
            ask = CutoverConsultationAsk(
                envelope=envelope,
                authority_context=authority_context,
                action_params=action_params,
            )
            consultation_result = produce_cutover_consultation(
                envelope=envelope,
                attempt=attempt,
                ask=ask,
                now=consultation_now,
                action_params=action_params,
            )
            if consultation_result.outcome != "asked_and_answered":
                raise CutoverRefusal(
                    consultation_result.failure_reason_code
                    or "consultation_unavailable"
                )
            consultation = consultation_result.consultation
            if type(consultation) is not s7.MaezVoiceConsultation:
                raise CutoverRefusal("consultation_unavailable")
            rendered_at = _now_z()
            rendered = s7.render_request_statement(
                envelope=envelope,
                surface="cockpit",
                origin="http://localhost:11437",
                action_params_hash=s7.canonical_hash(dict(action_params)),
                authority_context=authority_context,
                maez_voice_consultation=consultation,
                nonce=_fresh_s7_attempt_nonce(),
                expires_at=selected.authorization.expires_at,
                rendered_at=rendered_at,
            )
            bundle, binding = _cutover_voice_bundle(
                envelope=envelope,
                rendered=rendered,
                authority_context=authority_context,
                result=consultation_result,
            )
            authorization_store = _HeldS7AuthorizationStore(
                opened=opened,
                db_path=db_path,
            )
            validation = _persist_and_validate_cutover_voice_bundle(
                authorization_store=authorization_store,
                bundle=bundle,
                binding=binding,
                now=rendered_at,
            )
            voice_use_store = _existing_voice_bundle_use_store(db_path)
            guarded_store = guarded.S7GuardedStateStore(
                authorization_store=authorization_store,
                voice_bundle_use_store=voice_use_store,
            )
            reservation_token = secrets.token_hex(32)
            session_binding = "cutover-session-" + secrets.token_hex(32)
            internal_channel_binding = (
                "cutover-internal-" + secrets.token_hex(32)
            )
            service = s7_ceremony.S7LocalWebAuthnCeremonyService(
                verifier=s7_ceremony.S7ProductionWebAuthnVerifier(),
                store_factory=lambda: ceremony_store,
            )
            recovery = ceremony_store.credential_recovery_state()
            begin_result = service.authorize_begin(
                now=rendered_at,
                rendered_statement=rendered,
                precondition_hash=selected.precondition_hash,
                session_binding=session_binding,
                internal_channel_binding=internal_channel_binding,
                allow_degraded_primary_only=(
                    recovery.get("primary_credential_state") == "enabled"
                    and recovery.get("backup_credential_state") != "enabled"
                ),
                allow_degraded_backup_only=(
                    recovery.get("primary_credential_state") == "missing"
                    and recovery.get("backup_credential_state") == "enabled"
                ),
            )
            if begin_result.status_code != 200:
                raise _map_presence_finish_refusal(begin_result)
            allow_credentials = begin_result.body.get("allow_credentials")
            challenge_id = begin_result.body.get("challenge_id")
            if (
                type(allow_credentials) not in {tuple, list}
                or credential.credential_ref not in allow_credentials
                or type(challenge_id) is not str
                or not challenge_id
            ):
                raise CutoverRefusal("presence_credential_unscoped")
            _print_owner_cutover_gate(
                result=consultation_result,
                rendered=rendered,
                begin_body=begin_result.body,
            )
            assert consultation_result.raw_response_sha256 is not None
            finish_request = _read_owner_webauthn_finish(
                selected_credential_ref=credential.credential_ref,
                challenge_id=challenge_id,
                response_sha256=consultation_result.raw_response_sha256,
            )
            opened.require_current_named_identity()
            finish_now = _now_z()
            finish_result = service.authorize_finish(
                now=finish_now,
                envelope=envelope,
                rendered_statement=rendered,
                precondition_hash=selected.precondition_hash,
                maez_voice_consultation=consultation,
                session_binding=session_binding,
                internal_channel_binding=internal_channel_binding,
                request_json=finish_request,
                guarded_store=guarded_store,
                source_bundle_validation=validation,
                source_bundle_binding=binding,
                source_ref_hash=bundle.source_ref_hash,
                reservation_token=reservation_token,
                cutover_consultation_result=consultation_result,
            )
            if finish_result.status_code != 200:
                raise _map_presence_finish_refusal(finish_result)
            artifact_id = finish_result.body.get("artifact_id")
            if type(artifact_id) is not str or not artifact_id:
                raise CutoverRefusal("presence_mint_failed")

            consume_now = _now_z()
            opened.require_current_named_identity()
            try:
                try:
                    grant, callback_result, committed_row = (
                        s7.consume_for_execution_with_committed_row(
                            opened.consumption_connection,
                            artifact_id,
                            rendered=rendered,
                            action_params_hash=rendered.action_params_hash,
                            authority_context=authority_context,
                            precondition_hash=selected.precondition_hash,
                            derived_work_class="self_modification",
                            derived_aggregation_group=(
                                rendered.derived_aggregation_group
                            ),
                            now=consume_now,
                        )
                    )
                finally:
                    opened.require_current_named_identity()
            except CutoverRefusal:
                raise
            except (sqlite3.Error, ValueError) as exc:
                raise CutoverRefusal("presence_consumption_failed") from exc
            if (
                type(grant) is not s7.S7ExecutionGrant
                or callback_result is not None
                or type(committed_row) is not s7.CommittedGrantRow
            ):
                raise _classify_failed_cutover_consumption(
                    connection=opened.consumption_connection,
                    artifact_id=artifact_id,
                    selected=selected,
                    action_params=action_params,
                    now=consume_now,
                )
            if not s7.committed_grant_row_proves_founder_self_modification(
                committed_row,
                grant,
            ):
                raise CutoverRefusal("presence_grant_unprojectable")
            _require_cutover_grant_binding(
                grant=grant,
                selected=selected,
                action_params=action_params,
            )
            try:
                projection = cm.s7_execution_grant_projection_bytes(grant)
                presence_evidence_sha256 = hashlib.sha256(
                    projection
                ).hexdigest()
                receipt = cm.CutoverConsumptionReceipt(
                    authorization_file_sha256=(
                        selected.authorization_file_sha256
                    ),
                    authorization_binding_sha256=(
                        selected.authorization.binding_sha256
                    ),
                    nonce=selected.authorization.nonce,
                    window_id=selected.authorization.window_id,
                    boot_id=selected.authorization.boot_id,
                    stage_two_receipt_file_sha256=(
                        selected.receipt_file_sha256
                    ),
                    stage_two_receipt_binding_sha256=(
                        selected.receipt.binding_sha256
                    ),
                    presence_mode="founder_webauthn",
                    presence_evidence_sha256=presence_evidence_sha256,
                    consumed_at=consume_now,
                )
            except (TypeError, ValueError) as exc:
                raise CutoverRefusal("burn_receipt_unencodable") from exc
            publication = _stage_burn_publication(
                root=BENCH_ROOT,
                expected_uid=expected_uid,
                authorization=selected.authorization,
                receipt=receipt,
                grant=grant,
                action_params=action_params,
                clock=_now_z,
            )
            try:
                prepared._attach_burn_publication(publication)
            except BaseException:
                publication.close()
                raise
            return prepared
        finally:
            ceremony_store.close()


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


def _freeze_cutover_function_graph(
    *roots: Callable[..., object],
) -> tuple[Callable[..., object], ...]:
    """Clone the recursively referenced local function graph once at import.

    Each clone receives its own globals snapshot and shallow immutable module
    facades. Reassigning tracked module attributes later therefore cannot
    redirect a nested production edge.
    """

    module_globals = globals()
    discovered: dict[int, FunctionType] = {}
    pending = [root for root in roots if isinstance(root, FunctionType)]
    while pending:
        function = pending.pop()
        if id(function) in discovered:
            continue
        discovered[id(function)] = function
        for name in function.__code__.co_names:
            dependency = module_globals.get(name)
            if (
                isinstance(dependency, FunctionType)
                and dependency.__module__ == __name__
                and id(dependency) not in discovered
            ):
                pending.append(dependency)

    frozen_globals: dict[str, object] = {}
    for name, value in module_globals.items():
        if isinstance(value, ModuleType):
            frozen_globals[name] = SimpleNamespace(**vars(value))
        else:
            frozen_globals[name] = value

    clones: dict[int, FunctionType] = {}
    for identity, function in discovered.items():
        clone = FunctionType(
            function.__code__,
            frozen_globals,
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
        clone.__kwdefaults__ = function.__kwdefaults__
        clone.__annotations__ = dict(function.__annotations__)
        clone.__qualname__ = function.__qualname__
        clones[identity] = clone
    for identity, function in discovered.items():
        frozen_globals[function.__name__] = clones[identity]
    return tuple(clones[id(root)] for root in roots)


(
    _frozen_reconstruct_selected_cutover,
    _frozen_resolve_user_unit_fragments,
    _frozen_prepare_cutover_resources,
    _frozen_authorize_and_stage_selected_cutover,
    _frozen_burn_publish,
    _frozen_prepared_publish,
    _frozen_prepared_begin,
) = _freeze_cutover_function_graph(
    _reconstruct_selected_cutover_at,
    _resolve_user_unit_fragments,
    _prepare_cutover_resources_at,
    _authorize_and_stage_selected_cutover,
    BurnPublication.publish_and_validate_burn,
    PreparedCutover.publish_and_validate_burn,
    PreparedCutover.begin,
)
_prepare_selected_cutover = _bind_selected_cutover_preparer(
    reconstruct=_frozen_reconstruct_selected_cutover,
    resolve_units=_frozen_resolve_user_unit_fragments,
    prepare_resources=_frozen_prepare_cutover_resources,
    authorize_and_stage=_frozen_authorize_and_stage_selected_cutover,
    now_z=_now_z,
    burn_publish_unbound=_frozen_burn_publish,
)
execute_cutover = _bind_cutover_entrypoint(
    prepare_selected_cutover=_prepare_selected_cutover,
    prepared_type=PreparedCutover,
    publish_unbound=_frozen_prepared_publish,
    begin_unbound=_frozen_prepared_begin,
    execution_result_type=CutoverExecutionResult,
    refusal_type=CutoverRefusal,
)
del _prepare_selected_cutover
del _authorize_and_stage_selected_cutover
del _freeze_cutover_function_graph
del _frozen_reconstruct_selected_cutover
del _frozen_resolve_user_unit_fragments
del _frozen_prepare_cutover_resources
del _frozen_authorize_and_stage_selected_cutover
del _frozen_burn_publish
del _frozen_prepared_publish
del _frozen_prepared_begin
del _bind_selected_cutover_preparer
del _bind_cutover_entrypoint


def main() -> None:
    result = execute_cutover()
    print(
        json.dumps(
            {
                "completed_operations": list(result.completed_operations),
                "outcome": result.outcome,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
