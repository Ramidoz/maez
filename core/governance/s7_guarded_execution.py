"""S7.3 guarded self-modification execution seams."""

from __future__ import annotations

from contextlib import closing
from dataclasses import InitVar, dataclass, replace
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from core.governance import anchored_io as s7_io
from core.governance import operator_user_boundary as s7
from core.routing import model_config


VOICE_SOURCE_BUNDLE_VALIDATION_STATUSES = frozenset({
    "valid_absent",
    "blocking_present",
    "invalid_prompt_integrity",
    "invalid_hash_binding",
    "invalid_context_manifest_policy",
    "invalid_expired",
    "invalid_cross_field_state",
    "invalid_authority_predicate",
    "invalid_reducer_replay",
    "invalid_authority_class_replay",
    "raw_response_hash_mismatch",
    "reader_route_mismatch",
    "source_bundle_unavailable",
    "not_mint_eligible",
})

VOICE_SOURCE_BUNDLE_AUTHORITY_PROJECTIONS = frozenset({
    "valid_absent",
    "grounded_refusal",
    "grounded_permission",
    "operational_block",
    "marker_only",
    "unavailable",
})

VOICE_BUNDLE_RESERVATION_STATES = frozenset({
    "unreserved",
    "reserved",
    "consumed",
})

S7_VOICE_AUTHORITY_CLASSES = frozenset({
    "none",
    "operational",
    "authoritative",
})

S7_SEMANTIC_READER_OUTCOMES = frozenset({
    "blocking_signal_present",
    "no_blocking_signal_detected",
    "unreadable_or_uncertain",
})

_REPO_ROOT = Path(__file__).resolve().parents[2]
S7_VOICE_CONSULTATION_PROMPT_PATH = _REPO_ROOT / "prompts" / "s7.voice.consultation.v1.md"
S7_VOICE_SEMANTIC_READER_PROMPT_PATH = (
    _REPO_ROOT / "prompts" / "s7.voice.semantic_reader_v1.md"
)

R11_EXEMPTION_EVIDENCE_TABLE = "s7_consultation_exemption_evidence_v1"
R11_EXEMPTION_EVIDENCE_SCHEMA = "s7.consultation_exemption_evidence.r11.v1"
R11_EXEMPTION_EVIDENCE_KIND = "consultation_exemption"
_R11_EXEMPTION_EVIDENCE_DDL = f"""
CREATE TABLE {R11_EXEMPTION_EVIDENCE_TABLE} (
    artifact_id TEXT PRIMARY KEY,
    evidence_kind TEXT NOT NULL CHECK (evidence_kind = 'consultation_exemption'),
    ruling_id TEXT NOT NULL CHECK (ruling_id = 'R11'),
    schema_version TEXT NOT NULL
        CHECK (schema_version = 's7.consultation_exemption_evidence.r11.v1'),
    exemption_schema TEXT NOT NULL
        CHECK (exemption_schema = 's7.consultation_exemption.r11.v1'),
    quality_evidence_sha256 TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action = 'model_routing.cutover_cuda'),
    request_envelope_hash TEXT NOT NULL,
    action_params_hash TEXT NOT NULL,
    projection_json TEXT NOT NULL,
    projection_sha256 TEXT NOT NULL,
    artifact_binding_sha256 TEXT NOT NULL UNIQUE,
    recorded_at TEXT NOT NULL
)
"""


def _r11_exemption_evidence_contract(
    connection: sqlite3.Connection,
) -> tuple[object, ...] | None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (R11_EXEMPTION_EVIDENCE_TABLE,),
    ).fetchone()
    if row is None:
        return None
    sql = re.sub(r"\s+", " ", str(row[0])).strip().rstrip(";")
    columns = tuple(
        tuple(item)
        for item in connection.execute(
            f"PRAGMA table_info({R11_EXEMPTION_EVIDENCE_TABLE})"
        )
    )
    indexes = tuple(
        sorted(
            tuple(item)
            for item in connection.execute(
                f"PRAGMA index_list({R11_EXEMPTION_EVIDENCE_TABLE})"
            )
        )
    )
    return (sql, columns, indexes)


def _expected_r11_exemption_evidence_contract() -> tuple[object, ...]:
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute(_R11_EXEMPTION_EVIDENCE_DDL)
        contract = _r11_exemption_evidence_contract(connection)
    assert contract is not None
    return contract


def _provision_r11_exemption_evidence_at(*, store_dir_fd: int) -> None:
    """Explicit setup authority; open/mint paths only verify this table."""

    store_fd = os.open(
        "ceremony.sqlite3",
        os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=store_dir_fd,
    )
    connection = None
    try:
        connection = s7._open_s7_connection_from_held_store(
            dir_fd=store_dir_fd,
            store_fd=store_fd,
        )
        connection.execute("BEGIN IMMEDIATE")
        s7._verify_held_store_activation(store_dir_fd, store_fd, connection)
        challenge_columns = {
            str(row[1]): tuple(row)
            for row in connection.execute(
                "PRAGMA table_info(s7_ceremony_challenges)"
            )
        }
        if not challenge_columns:
            raise ValueError("R11 provisioning requires the ceremony challenge table")
        projection_column = challenge_columns.get(
            "consultation_exemption_projection_hash"
        )
        if projection_column is None:
            connection.execute(
                "ALTER TABLE s7_ceremony_challenges ADD COLUMN "
                "consultation_exemption_projection_hash TEXT"
            )
        elif projection_column[2:] != ("TEXT", 0, None, 0):
            raise ValueError("R11 challenge projection column contract drifted")
        actual = _r11_exemption_evidence_contract(connection)
        if actual is None:
            connection.execute(_R11_EXEMPTION_EVIDENCE_DDL)
        elif actual != _expected_r11_exemption_evidence_contract():
            raise ValueError(
                "R11 exemption evidence table does not match its frozen contract"
            )
        if (
            _r11_exemption_evidence_contract(connection)
            != _expected_r11_exemption_evidence_contract()
        ):
            raise ValueError("R11 exemption evidence provisioning failed")
        projection_column = next(
            (
                tuple(row)
                for row in connection.execute(
                    "PRAGMA table_info(s7_ceremony_challenges)"
                )
                if row[1] == "consultation_exemption_projection_hash"
            ),
            None,
        )
        if projection_column is None or projection_column[2:] != (
            "TEXT",
            0,
            None,
            0,
        ):
            raise ValueError("R11 challenge projection provisioning failed")
        connection.commit()
        os.fsync(store_fd)
        os.fsync(store_dir_fd)
    except BaseException:
        if connection is not None and connection.in_transaction:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()
        os.close(store_fd)


def provision_r11_exemption_evidence() -> None:
    """Provision the canonical store through a zero-parameter setup seam."""

    with s7_io._open_canonical_s7_dir() as store_dir_fd:
        _provision_r11_exemption_evidence_at(store_dir_fd=store_dir_fd)


def _r11_artifact_projection(
    artifact: s7.S7AuthorizationArtifact,
    *,
    exemption_projection_sha256: str,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "request_id": artifact.request_id,
        "request_envelope_hash": artifact.request_envelope_hash,
        "rendered_text_hash": artifact.rendered_text_hash,
        "action": artifact.action,
        "action_params_hash": artifact.action_params_hash,
        "precondition_hash": artifact.precondition_hash,
        "authority_context_hash": artifact.authority_context_hash,
        "derived_work_class": artifact.derived_work_class,
        "derived_aggregation_group": artifact.derived_aggregation_group,
        "nonce": artifact.nonce,
        "credential_ref": artifact.credential_ref,
        "auth_method": artifact.auth_method,
        "grant_source": artifact.grant_source,
        "user_presence": artifact.user_presence,
        "user_verification": artifact.user_verification,
        "created_at": s7._timestamp_text(artifact.created_at, field="created_at"),
        "expires_at": s7._timestamp_text(artifact.expires_at, field="expires_at"),
        "ceremony_kind": artifact.ceremony_kind,
        "schema_version": artifact.schema_version,
        "exemption_projection_sha256": exemption_projection_sha256,
    }


def _insert_r11_exemption_evidence(
    connection: sqlite3.Connection,
    *,
    artifact: s7.S7AuthorizationArtifact,
    consultation_exemption: Any,
) -> None:
    if (
        _r11_exemption_evidence_contract(connection)
        != _expected_r11_exemption_evidence_contract()
    ):
        raise ValueError(
            "R11 exemption evidence table is absent or does not match its contract"
        )
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='s7_voice_bundle_uses'"
    ).fetchone() is not None:
        collision = connection.execute(
            "SELECT 1 FROM s7_voice_bundle_uses WHERE artifact_id = ? LIMIT 1",
            (artifact.artifact_id,),
        ).fetchone()
        if collision is not None:
            raise ValueError(
                "R11 artifact cannot also carry voice-bundle evidence"
            )
    projection = consultation_exemption.projection()
    projection_json = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    projection_sha256 = s7.canonical_hash(projection)
    artifact_binding_sha256 = s7.canonical_hash(
        _r11_artifact_projection(
            artifact,
            exemption_projection_sha256=projection_sha256,
        )
    )
    connection.execute(
        f"""
        INSERT INTO {R11_EXEMPTION_EVIDENCE_TABLE} (
            artifact_id, evidence_kind, ruling_id, schema_version,
            exemption_schema, quality_evidence_sha256, action,
            request_envelope_hash, action_params_hash, projection_json,
            projection_sha256, artifact_binding_sha256, recorded_at
        ) VALUES (?, ?, 'R11', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact.artifact_id,
            R11_EXEMPTION_EVIDENCE_KIND,
            R11_EXEMPTION_EVIDENCE_SCHEMA,
            str(projection["schema"]),
            consultation_exemption.quality_evidence_sha256,
            artifact.action,
            artifact.request_envelope_hash,
            artifact.action_params_hash,
            projection_json,
            projection_sha256,
            artifact_binding_sha256,
            s7._timestamp_text(artifact.created_at, field="created_at"),
        ),
    )


def revalidate_r11_exemption_for_consumption(
    *,
    connection: sqlite3.Connection,
    grant: s7.S7ExecutionGrant,
    durable_cutover_selection: Any,
) -> Any:
    """Re-read R11 evidence inside the consuming transaction or refuse."""

    s7._require_verified_held_connection(connection)
    if connection.in_transaction is not True:
        raise ValueError("R11 evidence must be checked before consume commit")
    if type(grant) is not s7.S7ExecutionGrant:
        raise ValueError("R11 consumption requires the freshly minted grant")
    if (
        _r11_exemption_evidence_contract(connection)
        != _expected_r11_exemption_evidence_contract()
    ):
        raise ValueError("R11 exemption evidence is absent or malformed")
    try:
        evidence_rows = connection.execute(
            f"""
            SELECT artifact_id, evidence_kind, ruling_id, schema_version,
                   exemption_schema, quality_evidence_sha256, action,
                   request_envelope_hash, action_params_hash, projection_json,
                   projection_sha256, artifact_binding_sha256, recorded_at
            FROM {R11_EXEMPTION_EVIDENCE_TABLE}
            WHERE artifact_id = ?
            """,
            (grant.artifact_id,),
        ).fetchall()
        artifact_rows = connection.execute(
            """
            SELECT artifact_id, request_id, request_envelope_hash,
                   rendered_text_hash, action_params_hash, precondition_hash,
                   authority_context_hash, action, derived_work_class,
                   derived_aggregation_group, nonce, credential_ref,
                   auth_method, grant_source, user_presence, user_verification,
                   created_at, expires_at, consumed_at, schema_version,
                   ceremony_kind, consumed_by_request_id
            FROM s7_authorization_artifacts_v2
            WHERE artifact_id = ?
            """,
            (grant.artifact_id,),
        ).fetchall()
    except sqlite3.Error as exc:
        raise ValueError("R11 exemption evidence is unreadable") from exc
    if len(evidence_rows) != 1 or len(artifact_rows) != 1:
        raise ValueError("R11 exemption evidence is absent or ambiguous")
    evidence = evidence_rows[0]
    stored = artifact_rows[0]
    try:
        artifact = s7.S7AuthorizationArtifact(
            artifact_id=str(stored[0]),
            request_id=str(stored[1]),
            request_envelope_hash=str(stored[2]),
            rendered_text_hash=str(stored[3]),
            action_params_hash=str(stored[4]),
            precondition_hash=str(stored[5]),
            authority_context_hash=str(stored[6]),
            action=str(stored[7]),
            derived_work_class=str(stored[8]),
            derived_aggregation_group=str(stored[9]),
            nonce=str(stored[10]),
            credential_ref=str(stored[11]),
            auth_method=str(stored[12]),
            grant_source=str(stored[13]),
            user_presence=bool(stored[14]),
            user_verification=bool(stored[15]),
            created_at=str(stored[16]),
            expires_at=str(stored[17]),
            consumed_at=None if stored[18] is None else str(stored[18]),
            schema_version=str(stored[19]),
            ceremony_kind=str(stored[20]),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("R11 artifact row is malformed") from exc
    if (
        stored[21] != artifact.request_id
        or artifact.artifact_id != grant.artifact_id
        or artifact.request_id != grant.request_id
        or artifact.request_envelope_hash != grant.request_envelope_hash
        or artifact.rendered_text_hash != grant.rendered_text_hash
        or artifact.action_params_hash != grant.action_params_hash
        or artifact.precondition_hash != grant.precondition_hash
        or artifact.authority_context_hash != grant.authority_context_hash
        or artifact.action != grant.action
        or artifact.derived_work_class != grant.derived_work_class
        or artifact.derived_aggregation_group != grant.derived_aggregation_group
        or artifact.nonce != grant.nonce
        or artifact.credential_ref != grant.credential_ref
        or artifact.auth_method != grant.auth_method
        or artifact.grant_source != grant.grant_source
        or artifact.consumed_at != grant.consumed_at
        or artifact.ceremony_kind != grant.ceremony_kind
    ):
        raise ValueError("R11 evidence is not bound to the consuming grant")
    try:
        projection = json.loads(str(evidence[9]))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("R11 exemption projection is malformed") from exc
    canonical_projection = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    from core.governance import s7_consultation_exemption as r11

    exemption = r11._exemption_from_persisted_projection(projection)
    if exemption is None:
        raise ValueError("R11 exemption projection is not canonical")
    projection_sha256 = s7.canonical_hash(projection)
    expected_binding = s7.canonical_hash(
        _r11_artifact_projection(
            artifact,
            exemption_projection_sha256=projection_sha256,
        )
    )
    if (
        str(evidence[0]) != artifact.artifact_id
        or str(evidence[1]) != R11_EXEMPTION_EVIDENCE_KIND
        or str(evidence[2]) != r11.R11_RULING_ID
        or str(evidence[3]) != R11_EXEMPTION_EVIDENCE_SCHEMA
        or str(evidence[4]) != r11.R11_EXEMPTION_SCHEMA
        or str(evidence[5]) != exemption.quality_evidence_sha256
        or str(evidence[6]) != artifact.action
        or str(evidence[7]) != artifact.request_envelope_hash
        or str(evidence[8]) != artifact.action_params_hash
        or str(evidence[9]) != canonical_projection
        or str(evidence[10]) != projection_sha256
        or str(evidence[11]) != expected_binding
        or str(evidence[12]) != artifact.created_at
    ):
        raise ValueError("R11 exemption evidence binding is invalid")
    voice_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='s7_voice_bundle_uses'"
    ).fetchone()
    if voice_table is not None and connection.execute(
        "SELECT 1 FROM s7_voice_bundle_uses WHERE artifact_id = ? LIMIT 1",
        (artifact.artifact_id,),
    ).fetchone() is not None:
        raise ValueError("R11 artifact also carries voice-bundle evidence")
    if not r11.exemption_admits_for_artifact(
        artifact=artifact,
        exemption=exemption,
        durable_cutover_selection=durable_cutover_selection,
        ledger_writes_enabled=r11.born_by_any_signal(),
    ):
        raise ValueError("R11 exemption grounds no longer admit at consumption")
    return exemption


def _hash_file_bytes(path: Path) -> str:
    return s7.canonical_hash(path.read_bytes())


S7_VOICE_SEMANTIC_READER_ROUTE_ID = "s7_voice_semantic_reader_v1"
S7_VOICE_SEMANTIC_READER_PROVIDER = "local_llm_client"
S7_REVIEWED_SEMANTIC_READER_PROVIDER_MODEL = model_config.PRIMARY_MODEL
S7_REVIEWED_SEMANTIC_READER_MODEL_SNAPSHOT = s7.canonical_hash({
    "base_url": model_config.PRIMARY_BASE_URL,
    "chat_kwargs": model_config.PRIMARY_CHAT_KWARGS,
    "model": model_config.PRIMARY_MODEL,
})
S7_REVIEWED_SEMANTIC_READER_DECODING_PARAMS_HASH = s7.canonical_hash({
    "temperature": 0,
    "top_p": 1,
})
S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH = (
    "a5675bbaf5b0681184eeea1ed859ae5763132d5c8a7809eff31821052194c53f"
)
S7_MAEZ_SELF_CHANGE_CONSULTATION_PROMPT_HASH = (
    "5cbf2702ab477d14e948215f1c902abbaf1bedfd9976f49516c2a66ff6e3e0b8"
)
S7_REVIEWED_SEMANTIC_READER_ROUTE_CONFIG_HASH = s7.canonical_hash({
    "route_id": S7_VOICE_SEMANTIC_READER_ROUTE_ID,
    "provider": S7_VOICE_SEMANTIC_READER_PROVIDER,
})


def _assert_s7_reviewed_prompt_files_unchanged() -> None:
    if _hash_file_bytes(S7_VOICE_SEMANTIC_READER_PROMPT_PATH) != (
        S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH
    ):
        raise ValueError("S7 semantic-reader prompt hash mismatch")
    if _hash_file_bytes(S7_VOICE_CONSULTATION_PROMPT_PATH) != (
        S7_MAEZ_SELF_CHANGE_CONSULTATION_PROMPT_HASH
    ):
        raise ValueError("S7 consultation prompt hash mismatch")


_assert_s7_reviewed_prompt_files_unchanged()

_HASH64_RE = re.compile(r"^[0-9a-f]{64}$")
_EMPTY_RAW_RESPONSE_HASH = s7.canonical_hash("")
_EMPTY_EXACT_RESPONSE_SHA256 = hashlib.sha256(b"").hexdigest()
_VALIDATOR_TOKEN = object()
_RESPONSE_CAPTURE_RECEIPT_TOKEN = object()

S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA = "s7.voice_source_bundle.v1"
S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA = "s7.voice_source_bundle.v2"
S7_RESPONSE_CAPTURE_RECEIPT_SCHEMA = "s7.response_capture_receipt.v1"
_R8_CUTOVER_ACTION = "model_routing.cutover_cuda"
_V1_VOICE_BUNDLE_TABLE = "s7_voice_consultation_bundles"
_V2_VOICE_BUNDLE_TABLE = "s7_voice_source_bundles_v2"


class S7VoiceSourceBundleEvidenceInvalid(ValueError):
    """Durable voice row is absent or cannot be decoded as its sealed schema."""


def _validate_hash64(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _HASH64_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase sha256 hex digest")


def _voice_bundle_use_hash(
    *,
    request_id: str,
    source_ref_hash: str,
    consultation_id: str,
    used_at: str,
) -> str:
    return s7.canonical_hash({
        "consultation_id": consultation_id,
        "request_id": request_id,
        "source_ref_hash": source_ref_hash,
        "used_at": used_at,
    })


def semantic_reader_route_identity_hash(
    *,
    semantic_reader_route_id: str,
    semantic_reader_provider: str,
    semantic_reader_provider_model: str,
    semantic_reader_model_snapshot: str,
    semantic_reader_decoding_params_hash: str,
    semantic_reader_prompt_hash: str,
    semantic_reader_route_config_hash: str,
) -> str:
    return s7.canonical_hash((
        semantic_reader_route_id,
        semantic_reader_provider,
        semantic_reader_provider_model,
        semantic_reader_model_snapshot,
        semantic_reader_decoding_params_hash,
        semantic_reader_prompt_hash,
        semantic_reader_route_config_hash,
    ))


REVIEWED_SEMANTIC_READER_ROUTE_IDENTITIES = frozenset({
    semantic_reader_route_identity_hash(
        semantic_reader_route_id=S7_VOICE_SEMANTIC_READER_ROUTE_ID,
        semantic_reader_provider=S7_VOICE_SEMANTIC_READER_PROVIDER,
        semantic_reader_provider_model=S7_REVIEWED_SEMANTIC_READER_PROVIDER_MODEL,
        semantic_reader_model_snapshot=S7_REVIEWED_SEMANTIC_READER_MODEL_SNAPSHOT,
        semantic_reader_decoding_params_hash=S7_REVIEWED_SEMANTIC_READER_DECODING_PARAMS_HASH,
        semantic_reader_prompt_hash=S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH,
        semantic_reader_route_config_hash=S7_REVIEWED_SEMANTIC_READER_ROUTE_CONFIG_HASH,
    )
})


@dataclass(frozen=True)
class S7ContextManifestPolicy:
    """Reviewed policy that governs which context may enter a voice consultation."""

    policy_id: str
    schema_version: str
    allowed_fields: tuple[str, ...]
    dialog_context_rules: tuple[str, ...]
    reviewed_at: str
    policy_body_hash: str

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("S7ContextManifestPolicy requires policy_id")
        if not self.schema_version:
            raise ValueError("S7ContextManifestPolicy requires schema_version")
        if not isinstance(self.allowed_fields, tuple) or not self.allowed_fields:
            raise ValueError("S7ContextManifestPolicy requires allowed_fields")
        if not isinstance(self.dialog_context_rules, tuple):
            raise ValueError("dialog_context_rules must be tuple")
        if not self.reviewed_at:
            raise ValueError("S7ContextManifestPolicy requires reviewed_at")
        _validate_hash64(self.policy_body_hash, field="policy_body_hash")

    @property
    def policy_hash(self) -> str:
        return s7.canonical_hash({
            "allowed_fields": self.allowed_fields,
            "dialog_context_rules": self.dialog_context_rules,
            "policy_body_hash": self.policy_body_hash,
            "policy_id": self.policy_id,
            "reviewed_at": self.reviewed_at,
            "schema_version": self.schema_version,
        })


#: The REAL policy body hash (full-body audit, 2026-08-14). The previous
#: value was the literal "f"*64 -- a hash field named for a binding that
#: bound nothing, the exact defect class R11's own comments condemn. The
#: pre-image is durable at
#: config/s7_context_manifest_policies/s7.context_manifest_policy.v1.json
#: (the location the S7.3 spec ruled and nobody ever created); a test
#: recomputes this digest from that file's bytes, per the
#: freeze-a-hash/persist-its-pre-image covenant.
S7_CONTEXT_MANIFEST_POLICY_BODY_SHA256 = (
    "cbcd362e1463f795a8b80bedfd9b50ccf8b1ba70009e5efff86c57c766709cfb"
)
S7_CONTEXT_MANIFEST_POLICY_BODY_PATH = (
    "config/s7_context_manifest_policies/s7.context_manifest_policy.v1.json"
)

S7_REVIEWED_CONTEXT_MANIFEST_POLICY = S7ContextManifestPolicy(
    policy_id="s7-context-policy-v1",
    schema_version="1",
    allowed_fields=("preview_ref", "dialog_context_ref", "rollback_path_class"),
    dialog_context_rules=("no_private_raw_text",),
    reviewed_at="2026-05-21T00:00:00+00:00",
    policy_body_hash=S7_CONTEXT_MANIFEST_POLICY_BODY_SHA256,
)

#: GRANDFATHERED: bundles persisted before 2026-08-14 carry the
#: placeholder-era policy hash. Same ruled content, dishonest digest --
#: named here as legacy rather than silently laundered into "reviewed".
#: Remove once the live store's pre-audit bundles are re-validated or
#: retired.
_LEGACY_PLACEHOLDER_POLICY = S7ContextManifestPolicy(
    policy_id="s7-context-policy-v1",
    schema_version="1",
    allowed_fields=("preview_ref", "dialog_context_ref", "rollback_path_class"),
    dialog_context_rules=("no_private_raw_text",),
    reviewed_at="2026-05-21T00:00:00+00:00",
    policy_body_hash="f" * 64,
)

REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES = frozenset({
    S7_REVIEWED_CONTEXT_MANIFEST_POLICY.policy_hash,
    _LEGACY_PLACEHOLDER_POLICY.policy_hash,
})


S7_GUARDED_EXECUTION_TRACE_SCHEMA = """
CREATE TABLE IF NOT EXISTS s7_guarded_execution_traces (
    trace_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    request_envelope_hash TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    action_params_hash TEXT NOT NULL,
    precondition_hash TEXT NOT NULL,
    rollback_path_class TEXT NOT NULL,
    dialog_id TEXT,
    execution_status TEXT NOT NULL,
    execution_success INTEGER NOT NULL,
    card_status TEXT,
    output_hash TEXT,
    error_hash TEXT,
    executed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_s7_guarded_execution_traces_request
    ON s7_guarded_execution_traces(request_id);
CREATE INDEX IF NOT EXISTS idx_s7_guarded_execution_traces_artifact
    ON s7_guarded_execution_traces(artifact_id);
"""


def record_s7_guarded_execution_trace(
    *,
    db_path: str | Path,
    request_id: str,
    artifact_id: str,
    request_envelope_hash: str,
    rendered_text_hash: str,
    action_params_hash: str,
    precondition_hash: str,
    rollback_path_class: str,
    dialog_id: str | None,
    execution_status: str,
    execution_success: bool,
    card_status: str | None,
    output_text: str | None,
    error_text: str | None,
    executed_at: str,
) -> str:
    """Persist the D22 trace that proves a guarded execution actually ran."""

    if not request_id:
        raise ValueError("S7 guarded execution trace requires request_id")
    if not artifact_id:
        raise ValueError("S7 guarded execution trace requires artifact_id")
    _validate_hash64(request_envelope_hash, field="request_envelope_hash")
    _validate_hash64(rendered_text_hash, field="rendered_text_hash")
    _validate_hash64(action_params_hash, field="action_params_hash")
    _validate_hash64(precondition_hash, field="precondition_hash")
    s7._validate_closed_value(
        rollback_path_class,
        s7.ROLLBACK_PATH_CLASSES,
        "rollback_path_class",
    )
    if not execution_status:
        raise ValueError("S7 guarded execution trace requires execution_status")
    if not executed_at:
        raise ValueError("S7 guarded execution trace requires executed_at")
    output_hash = s7.canonical_hash(output_text or "") if output_text else None
    error_hash = s7.canonical_hash(error_text or "") if error_text else None
    trace_id = "s7exec_" + s7.canonical_hash({
        "artifact_id": artifact_id,
        "executed_at": executed_at,
        "execution_status": execution_status,
        "request_id": request_id,
    })[:32]
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.executescript(S7_GUARDED_EXECUTION_TRACE_SCHEMA)
        conn.execute(
            """
            INSERT OR REPLACE INTO s7_guarded_execution_traces (
                trace_id, request_id, artifact_id, request_envelope_hash,
                rendered_text_hash, action_params_hash, precondition_hash,
                rollback_path_class, dialog_id, execution_status,
                execution_success, card_status, output_hash, error_hash,
                executed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                request_id,
                artifact_id,
                request_envelope_hash,
                rendered_text_hash,
                action_params_hash,
                precondition_hash,
                rollback_path_class,
                dialog_id,
                execution_status,
                1 if execution_success else 0,
                card_status,
                output_hash,
                error_hash,
                executed_at,
            ),
        )
        conn.commit()
    return trace_id


@dataclass(frozen=True)
class S7ContextManifest:
    """Immutable context manifest bound into an S7.3 voice source bundle."""

    schema_version: str
    manifest_id: str
    preview_ref: str
    dialog_context_ref: str | None
    request_envelope_hash: str
    precondition_hash: str
    rollback_path_class: str
    source_surface: str
    proposal_origin_label: str
    policy_id: str
    policy_hash: str
    created_at: str

    def __post_init__(self) -> None:
        if not self.schema_version:
            raise ValueError("S7ContextManifest requires schema_version")
        if not self.manifest_id:
            raise ValueError("S7ContextManifest requires manifest_id")
        if not self.preview_ref:
            raise ValueError("S7ContextManifest requires preview_ref")
        if self.dialog_context_ref is not None and not self.dialog_context_ref:
            raise ValueError("dialog_context_ref must be non-empty when present")
        _validate_hash64(self.request_envelope_hash, field="request_envelope_hash")
        _validate_hash64(self.precondition_hash, field="precondition_hash")
        s7._validate_closed_value(self.rollback_path_class, s7.ROLLBACK_PATH_CLASSES, "rollback_path_class")
        if not self.source_surface:
            raise ValueError("S7ContextManifest requires source_surface")
        s7._validate_closed_value(
            self.proposal_origin_label,
            frozenset({"operator", "maez", "system"}),
            "proposal_origin_label",
        )
        if not self.policy_id:
            raise ValueError("S7ContextManifest requires policy_id")
        _validate_hash64(self.policy_hash, field="policy_hash")
        if not self.created_at:
            raise ValueError("S7ContextManifest requires created_at")

    @property
    def context_manifest_hash(self) -> str:
        return s7.canonical_hash({
            "dialog_context_ref": self.dialog_context_ref,
            "policy_hash": self.policy_hash,
            "policy_id": self.policy_id,
            "precondition_hash": self.precondition_hash,
            "preview_ref": self.preview_ref,
            "proposal_origin_label": self.proposal_origin_label,
            "request_envelope_hash": self.request_envelope_hash,
            "rollback_path_class": self.rollback_path_class,
            "schema_version": self.schema_version,
            "source_surface": self.source_surface,
        })


@dataclass(frozen=True, init=False)
class S7VoiceSourceBundleValidationResult:
    """Result of the S7.3 source-bundle validator that gates artifact minting."""

    status: str
    source_bundle_valid: bool
    mint_eligible: bool
    authority_projection: str
    failure_reason_code: str | None

    def __init__(
        self,
        *,
        status: str,
        source_bundle_valid: bool,
        mint_eligible: bool,
        authority_projection: str,
        failure_reason_code: str | None,
        _validator_token: object | None = None,
    ) -> None:
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "source_bundle_valid", source_bundle_valid)
        object.__setattr__(self, "mint_eligible", mint_eligible)
        object.__setattr__(self, "authority_projection", authority_projection)
        object.__setattr__(self, "failure_reason_code", failure_reason_code)
        object.__setattr__(self, "_validator_produced", _validator_token is _VALIDATOR_TOKEN)
        self.__post_init__()

    @classmethod
    def _validator_pass(cls) -> "S7VoiceSourceBundleValidationResult":
        return cls(
            status="valid_absent",
            source_bundle_valid=True,
            mint_eligible=True,
            authority_projection="valid_absent",
            failure_reason_code=None,
            _validator_token=_VALIDATOR_TOKEN,
        )

    @classmethod
    def _validator_refusal(cls) -> "S7VoiceSourceBundleValidationResult":
        return cls(
            status="blocking_present",
            source_bundle_valid=True,
            mint_eligible=False,
            authority_projection="grounded_refusal",
            failure_reason_code=None,
            _validator_token=_VALIDATOR_TOKEN,
        )

    def __post_init__(self) -> None:
        if self.status not in VOICE_SOURCE_BUNDLE_VALIDATION_STATUSES:
            raise ValueError(f"unknown S7.3 voice source bundle validation status: {self.status}")
        if self.authority_projection not in VOICE_SOURCE_BUNDLE_AUTHORITY_PROJECTIONS:
            raise ValueError(
                "unknown S7.3 voice source bundle authority projection: "
                f"{self.authority_projection}"
            )
        if self.status == "valid_absent":
            if getattr(self, "_validator_produced", False) is not True:
                raise ValueError("valid_absent source-bundle validation must be produced by validator")
            if self.failure_reason_code is not None:
                raise ValueError("valid_absent source-bundle validation must not carry a failure reason")
            if self.source_bundle_valid is not True or self.mint_eligible is not True:
                raise ValueError("valid_absent source-bundle validation must be valid and mint-eligible")
            if self.authority_projection != "valid_absent":
                raise ValueError("valid_absent source-bundle validation must project valid_absent")
        elif self.status == "blocking_present":
            if getattr(self, "_validator_produced", False) is not True:
                raise ValueError("blocking_present source-bundle validation must be produced by validator")
            if self.failure_reason_code is not None:
                raise ValueError("blocking_present source-bundle validation must not carry a failure reason")
            if self.source_bundle_valid is not True or self.mint_eligible is not False:
                raise ValueError("blocking_present source-bundle validation must be valid and not mint-eligible")
            if self.authority_projection != "grounded_refusal":
                raise ValueError("blocking_present source-bundle validation must project grounded_refusal")
        elif self.failure_reason_code is None:
            raise ValueError("failed source-bundle validation must carry a failure reason")


@dataclass(frozen=True, init=False)
class S7VoiceSourceBundleValidationResultV2:
    """Validator-produced result bound to durable versioned voice evidence."""

    status: str
    source_bundle_valid: bool
    mint_eligible: bool
    authority_projection: str
    failure_reason_code: str | None
    action: str | None
    schema_version: str
    source_bundle_hash: str
    binding_hash: str

    def __init__(
        self,
        *,
        status: str,
        source_bundle_valid: bool,
        mint_eligible: bool,
        authority_projection: str,
        failure_reason_code: str | None,
        action: str | None,
        schema_version: str,
        source_bundle_hash: str,
        binding_hash: str,
        _validator_token: object | None = None,
    ) -> None:
        if _validator_token is not _VALIDATOR_TOKEN:
            raise ValueError("s7_validation_result_forged")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "source_bundle_valid", source_bundle_valid)
        object.__setattr__(self, "mint_eligible", mint_eligible)
        object.__setattr__(self, "authority_projection", authority_projection)
        object.__setattr__(self, "failure_reason_code", failure_reason_code)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "source_bundle_hash", source_bundle_hash)
        object.__setattr__(self, "binding_hash", binding_hash)
        object.__setattr__(self, "_token_verified", True)
        self.__post_init__()

    def __post_init__(self) -> None:
        s7._validate_closed_value(
            self.status,
            VOICE_SOURCE_BUNDLE_VALIDATION_STATUSES,
            "voice source bundle validation status",
        )
        s7._validate_closed_value(
            self.authority_projection,
            VOICE_SOURCE_BUNDLE_AUTHORITY_PROJECTIONS,
            "voice source bundle authority projection",
        )
        if type(self.source_bundle_valid) is not bool:
            raise ValueError("source_bundle_valid must be bool")
        if type(self.mint_eligible) is not bool:
            raise ValueError("mint_eligible must be bool")
        if self.failure_reason_code is not None and (
            type(self.failure_reason_code) is not str
            or not self.failure_reason_code
        ):
            raise ValueError("failure_reason_code must be a non-empty str when present")
        if self.schema_version not in {
            S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA,
            S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA,
        }:
            raise ValueError("unknown S7 voice source bundle schema_version")
        if self.schema_version == S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA:
            if self.action is not None or self.mint_eligible is True:
                raise ValueError("v1 voice source bundles are audit-only")
        else:
            s7.validate_action_literal(self.action)
        _validate_hash64(self.source_bundle_hash, field="source_bundle_hash")
        _validate_hash64(self.binding_hash, field="binding_hash")
        if self.mint_eligible is True and (
            self.status != "valid_absent"
            or self.source_bundle_valid is not True
            or self.authority_projection != "valid_absent"
            or self.failure_reason_code is not None
            or self.schema_version != S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA
        ):
            raise ValueError("mint-eligible voice validation is not a complete success")
        if self.source_bundle_valid is False and self.mint_eligible is True:
            raise ValueError("an invalid voice source bundle cannot be mint-eligible")
        if self.status == "valid_absent" and (
            self.source_bundle_valid is not True
            or self.mint_eligible is not True
            or self.authority_projection != "valid_absent"
            or self.failure_reason_code is not None
        ):
            raise ValueError("valid_absent requires the complete successful tuple")
        if self.status == "blocking_present" and (
            self.source_bundle_valid is not True
            or self.mint_eligible is not False
            or self.authority_projection != "grounded_refusal"
            or self.failure_reason_code is not None
        ):
            raise ValueError("blocking_present requires the grounded-refusal tuple")
        if self.status not in {"valid_absent", "blocking_present"} and (
            self.mint_eligible is True or self.failure_reason_code is None
        ):
            raise ValueError("failed voice validation must be unmintable with a reason")


@dataclass(frozen=True)
class S7VoiceSourceBundleHashBinding:
    """Expected exact-change hashes the private voice bundle must be bound to."""

    request_id: str
    consultation_id: str
    source_ref_hash: str
    request_envelope_hash: str
    rendered_text_hash: str
    action_params_hash: str
    precondition_hash: str
    authority_context_hash: str
    maez_voice_consultation_hash: str
    rendered_prompt_hash: str
    mutation_preview_hash: str
    rollback_plan_ref: str
    context_manifest_hash: str
    runtime_identity_hash: str
    model_routing_identity_hash: str
    model_config_hash: str

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("S7VoiceSourceBundleHashBinding requires request_id")
        if not self.consultation_id:
            raise ValueError("S7VoiceSourceBundleHashBinding requires consultation_id")
        for field_name in (
            "source_ref_hash",
            "request_envelope_hash",
            "rendered_text_hash",
            "action_params_hash",
            "precondition_hash",
            "authority_context_hash",
            "maez_voice_consultation_hash",
            "rendered_prompt_hash",
            "mutation_preview_hash",
            "rollback_plan_ref",
            "context_manifest_hash",
            "runtime_identity_hash",
            "model_routing_identity_hash",
            "model_config_hash",
        ):
            _validate_hash64(getattr(self, field_name), field=field_name)


def expected_s7_voice_rendered_prompt_text(
    *,
    rendered_statement: s7.RenderedRequestStatement,
    maez_voice_consultation: s7.MaezVoiceConsultation,
) -> str:
    """Return the reviewed v1 prompt text expected for this exact signed change."""

    if not isinstance(rendered_statement, s7.RenderedRequestStatement):
        raise ValueError("expected prompt requires RenderedRequestStatement")
    if not isinstance(maez_voice_consultation, s7.MaezVoiceConsultation):
        raise ValueError("expected prompt requires MaezVoiceConsultation")
    if rendered_statement.request_id != maez_voice_consultation.request_id:
        raise ValueError("expected prompt request mismatch")
    return "\n".join((
        "S7.3 Maez voice consultation prompt v1",
        f"Request id: {rendered_statement.request_id}",
        f"Rendered text hash: {rendered_statement.rendered_text_hash}",
        f"Request envelope hash: {rendered_statement.request_envelope_hash}",
        f"Action params hash: {rendered_statement.action_params_hash}",
        f"Authority context hash: {rendered_statement.authority_context_hash}",
        f"Maez voice consultation hash: {rendered_statement.maez_voice_consultation_hash}",
        f"Consultation source ref hash: {maez_voice_consultation.source_ref_hash}",
    ))


def _expected_s7_voice_mutation_preview_hash(
    *,
    rendered_statement: s7.RenderedRequestStatement,
    envelope: s7.WorkRequestEnvelope,
    precondition_hash: str,
) -> str:
    return s7.canonical_hash({
        "action_params_hash": rendered_statement.action_params_hash,
        "affected_refs": envelope.affected_refs,
        "precondition_hash": precondition_hash,
        "proposed_change_class": envelope.proposed_change_class,
        "request_envelope_hash": rendered_statement.request_envelope_hash,
        "request_id": rendered_statement.request_id,
    })


def _expected_s7_voice_context_manifest_hash(
    *,
    rendered_statement: s7.RenderedRequestStatement,
    envelope: s7.WorkRequestEnvelope,
    precondition_hash: str,
) -> str:
    manifest = S7ContextManifest(
        schema_version="1",
        manifest_id="derived-not-hashed",
        preview_ref=f"preview:{rendered_statement.request_id}",
        dialog_context_ref=None,
        request_envelope_hash=rendered_statement.request_envelope_hash,
        precondition_hash=precondition_hash,
        rollback_path_class=envelope.rollback_path_class,
        source_surface=rendered_statement.surface,
        proposal_origin_label="operator",
        policy_id=S7_REVIEWED_CONTEXT_MANIFEST_POLICY.policy_id,
        policy_hash=S7_REVIEWED_CONTEXT_MANIFEST_POLICY.policy_hash,
        created_at=rendered_statement.rendered_at,
    )
    return manifest.context_manifest_hash


def derive_s7_voice_source_bundle_hash_binding(
    *,
    rendered_statement: s7.RenderedRequestStatement,
    envelope: s7.WorkRequestEnvelope,
    maez_voice_consultation: s7.MaezVoiceConsultation,
    authority_context: s7.AuthorityContext,
    precondition_hash: str,
) -> S7VoiceSourceBundleHashBinding:
    """Derive the bundle binding from the founder-signed change, never the bundle."""

    if not isinstance(rendered_statement, s7.RenderedRequestStatement):
        raise ValueError("binding derivation requires RenderedRequestStatement")
    if not isinstance(envelope, s7.WorkRequestEnvelope):
        raise ValueError("binding derivation requires WorkRequestEnvelope")
    if not isinstance(maez_voice_consultation, s7.MaezVoiceConsultation):
        raise ValueError("binding derivation requires MaezVoiceConsultation")
    if not isinstance(authority_context, s7.AuthorityContext):
        raise ValueError("binding derivation requires AuthorityContext")
    s7._validate_hash64(precondition_hash, field="precondition_hash")
    envelope_hash = s7.work_request_envelope_hash(envelope)
    consultation_hash = s7.maez_voice_consultation_hash(maez_voice_consultation)
    authority_hash = s7.authority_context_hash(authority_context)
    if rendered_statement.request_id != envelope.request_id:
        raise ValueError("binding derivation request mismatch")
    if rendered_statement.request_envelope_hash != envelope_hash:
        raise ValueError("binding derivation envelope hash mismatch")
    if rendered_statement.action_params_hash == "0" * 64:
        raise ValueError("binding derivation requires action params hash")
    if rendered_statement.authority_context_hash != authority_hash:
        raise ValueError("binding derivation authority hash mismatch")
    if rendered_statement.maez_voice_consultation_hash != consultation_hash:
        raise ValueError("binding derivation consultation hash mismatch")
    if envelope.precondition_hash != precondition_hash:
        raise ValueError("binding derivation precondition mismatch")
    if not s7.voice_consultation_satisfies_request(envelope, maez_voice_consultation):
        raise ValueError("binding derivation requires matching consultation")
    return S7VoiceSourceBundleHashBinding(
        request_id=rendered_statement.request_id,
        consultation_id=maez_voice_consultation.consultation_id,
        source_ref_hash=maez_voice_consultation.source_ref_hash,
        request_envelope_hash=rendered_statement.request_envelope_hash,
        rendered_text_hash=rendered_statement.rendered_text_hash,
        action_params_hash=rendered_statement.action_params_hash,
        precondition_hash=precondition_hash,
        authority_context_hash=rendered_statement.authority_context_hash,
        maez_voice_consultation_hash=consultation_hash,
        rendered_prompt_hash=s7.canonical_hash(expected_s7_voice_rendered_prompt_text(
            rendered_statement=rendered_statement,
            maez_voice_consultation=maez_voice_consultation,
        )),
        mutation_preview_hash=_expected_s7_voice_mutation_preview_hash(
            rendered_statement=rendered_statement,
            envelope=envelope,
            precondition_hash=precondition_hash,
        ),
        rollback_plan_ref=s7.canonical_hash({
            "request_envelope_hash": rendered_statement.request_envelope_hash,
            "request_id": rendered_statement.request_id,
            "rollback_path_class": envelope.rollback_path_class,
        }),
        context_manifest_hash=_expected_s7_voice_context_manifest_hash(
            rendered_statement=rendered_statement,
            envelope=envelope,
            precondition_hash=precondition_hash,
        ),
        runtime_identity_hash=s7.canonical_hash({
            "bonded_runtime": "current",
            "request_envelope_hash": rendered_statement.request_envelope_hash,
        }),
        model_routing_identity_hash=s7.canonical_hash({
            "model_route": "normal",
            "request_envelope_hash": rendered_statement.request_envelope_hash,
        }),
        model_config_hash=s7.canonical_hash({
            "model_config": "reviewed_s7_voice_v1",
            "request_envelope_hash": rendered_statement.request_envelope_hash,
        }),
    )


def persist_s7_voice_source_bundle_for_material(
    *,
    db_path: str | Path,
    rendered_statement: s7.RenderedRequestStatement,
    envelope: s7.WorkRequestEnvelope,
    maez_voice_consultation: s7.MaezVoiceConsultation,
    authority_context: s7.AuthorityContext,
    precondition_hash: str,
    raw_response_text: str,
    semantic_reader_attempt: S7SemanticReaderAttemptEvidence,
    now: str,
) -> S7VoiceSourceBundleHashBinding:
    """Persist one action-bound v2 bundle for an already-produced voice fact."""

    if not isinstance(raw_response_text, str) or raw_response_text == "":
        raise ValueError("raw_response_text is required")
    if not isinstance(semantic_reader_attempt, S7SemanticReaderAttemptEvidence):
        raise ValueError("semantic_reader_attempt is required")
    binding = derive_s7_voice_source_bundle_hash_binding(
        rendered_statement=rendered_statement,
        envelope=envelope,
        maez_voice_consultation=maez_voice_consultation,
        authority_context=authority_context,
        precondition_hash=precondition_hash,
    )
    authorization_store = s7.S7AuthorizationStore(db_path)
    with authorization_store.anchored_transaction() as conn:
        existing = conn.execute(
            f"SELECT 1 FROM {_V2_VOICE_BUNDLE_TABLE} WHERE source_ref_hash = ?",
            (binding.source_ref_hash,),
        ).fetchone()
    if existing is not None:
        return binding
    bundle_store = S7VoiceConsultationBundleStore(db_path)
    bundle_use_store = S7VoiceBundleUseStore(db_path)
    attempt_store = S7SemanticReaderAttemptStore(db_path)
    attempt_store.put(semantic_reader_attempt)
    rendered_prompt_text = expected_s7_voice_rendered_prompt_text(
        rendered_statement=rendered_statement,
        maez_voice_consultation=maez_voice_consultation,
    )
    rendered_prompt_ref = f"s7.voice.prompt.{rendered_statement.request_id}"
    raw_response_ref = f"s7.voice.raw.{rendered_statement.request_id}"
    bundle_store.put_rendered_prompt(rendered_prompt_ref, rendered_prompt_text)
    bundle_store.put_raw_response(raw_response_ref, raw_response_text)
    manifest = bundle_store.put_reviewed_context_manifest(
        manifest_id=f"s7.voice.context.{rendered_statement.request_id}",
        preview_ref=f"preview:{rendered_statement.request_id}",
        request_envelope_hash=rendered_statement.request_envelope_hash,
        precondition_hash=precondition_hash,
        rollback_path_class=envelope.rollback_path_class,
        source_surface=rendered_statement.surface,
        proposal_origin_label="operator",
        created_at=rendered_statement.rendered_at,
    )
    blocking = (
        semantic_reader_attempt.raw_semantic_reader_outcome
        == "blocking_signal_present"
        and semantic_reader_attempt.grounding_response_span_quote is not None
    )
    bundle = S7VoiceConsultationBundle(
        source_ref_hash=binding.source_ref_hash,
        request_id=binding.request_id,
        consultation_id=binding.consultation_id,
        request_envelope_hash=binding.request_envelope_hash,
        rendered_text_hash=binding.rendered_text_hash,
        action_params_hash=binding.action_params_hash,
        precondition_hash=binding.precondition_hash,
        authority_context_hash=binding.authority_context_hash,
        maez_voice_consultation_hash=binding.maez_voice_consultation_hash,
        rendered_prompt_ref=rendered_prompt_ref,
        rendered_prompt_hash=binding.rendered_prompt_hash,
        mutation_preview_hash=binding.mutation_preview_hash,
        rollback_plan_ref=binding.rollback_plan_ref,
        context_manifest_ref=manifest.manifest_id,
        context_manifest_hash=binding.context_manifest_hash,
        runtime_identity_hash=binding.runtime_identity_hash,
        model_routing_identity_hash=binding.model_routing_identity_hash,
        model_config_hash=binding.model_config_hash,
        raw_response_ref=raw_response_ref,
        raw_response_hash=s7.canonical_hash(raw_response_text),
        semantic_reader_attempt_hash=semantic_reader_attempt.semantic_reader_attempt_hash,
        expires_at=rendered_statement.expires_at,
        authority_class="authoritative" if blocking else "none",
        has_grounded_semantic_blocking_signal=blocking,
        action=rendered_statement.action,
    )
    bundle = replace(
        bundle,
        source_bundle_hash=s7_voice_consultation_bundle_hash(bundle),
    )
    with authorization_store.anchored_transaction() as conn:
        put_voice_source_bundle_v2(bundle=bundle, conn=conn)
    bundle_use_store.put_unreserved(
        S7VoiceBundleUse.new_unreserved(
            request_id=binding.request_id,
            source_ref_hash=binding.source_ref_hash,
            consultation_id=binding.consultation_id,
            used_at=now,
        )
    )
    return binding


def _response_capture_receipt_fields(
    *,
    request_id: str,
    consultation_id: str,
    attempt_identity: str,
    raw_response_ref: str,
    raw_response_sha256: str,
    captured_at: str,
) -> dict[str, str]:
    return {
        "attempt_identity": attempt_identity,
        "captured_at": captured_at,
        "consultation_id": consultation_id,
        "raw_response_ref": raw_response_ref,
        "raw_response_sha256": raw_response_sha256,
        "request_id": request_id,
    }


def _response_capture_receipt_binding_sha256(
    *,
    request_id: str,
    consultation_id: str,
    attempt_identity: str,
    raw_response_ref: str,
    raw_response_sha256: str,
    captured_at: str,
) -> str:
    return s7.canonical_hash({
        "schema": S7_RESPONSE_CAPTURE_RECEIPT_SCHEMA,
        "fields": _response_capture_receipt_fields(
            request_id=request_id,
            consultation_id=consultation_id,
            attempt_identity=attempt_identity,
            raw_response_ref=raw_response_ref,
            raw_response_sha256=raw_response_sha256,
            captured_at=captured_at,
        ),
    })


@dataclass(frozen=True)
class S7ResponseCaptureReceipt:
    """Content-blind proof that exact response bytes survived a durable capture."""

    schema_version: str
    request_id: str
    consultation_id: str
    attempt_identity: str
    raw_response_ref: str
    raw_response_sha256: str
    captured_at: str
    binding_sha256: str
    _producer_token: InitVar[object | None] = None

    def __post_init__(self, _producer_token: object | None) -> None:
        if _producer_token is not _RESPONSE_CAPTURE_RECEIPT_TOKEN:
            raise ValueError("response capture receipts require their dedicated producer")
        if self.schema_version != S7_RESPONSE_CAPTURE_RECEIPT_SCHEMA:
            raise ValueError("unknown response capture receipt schema_version")
        for field_name in (
            "request_id",
            "consultation_id",
            "raw_response_ref",
        ):
            value = getattr(self, field_name)
            if type(value) is not str or not value:
                raise ValueError(f"response capture receipt {field_name} is required")
        _validate_hash64(self.attempt_identity, field="attempt_identity")
        _validate_hash64(self.raw_response_sha256, field="raw_response_sha256")
        s7._timestamp_text(self.captured_at, field="captured_at")
        _validate_hash64(self.binding_sha256, field="binding_sha256")
        expected = _response_capture_receipt_binding_sha256(
            request_id=self.request_id,
            consultation_id=self.consultation_id,
            attempt_identity=self.attempt_identity,
            raw_response_ref=self.raw_response_ref,
            raw_response_sha256=self.raw_response_sha256,
            captured_at=self.captured_at,
        )
        if self.binding_sha256 != expected:
            raise ValueError("response capture receipt binding mismatch")

    def as_dict(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            **_response_capture_receipt_fields(
                request_id=self.request_id,
                consultation_id=self.consultation_id,
                attempt_identity=self.attempt_identity,
                raw_response_ref=self.raw_response_ref,
                raw_response_sha256=self.raw_response_sha256,
                captured_at=self.captured_at,
            ),
            "binding_sha256": self.binding_sha256,
        }


def produce_s7_response_capture_receipt(
    *,
    request_id: str,
    consultation_id: str,
    attempt_identity: str,
    raw_response_ref: str,
    raw_response_bytes: bytes,
    captured_at: str,
    response_root: str | Path,
    expected_uid: int,
) -> S7ResponseCaptureReceipt:
    """Reopen exact durable bytes before minting their content-blind receipt."""

    if type(raw_response_bytes) is not bytes or not raw_response_bytes:
        raise ValueError("response capture requires non-empty exact bytes")
    retrieved = s7_io.read_private_file(
        raw_response_ref,
        root=response_root,
        expected_uid=expected_uid,
    )
    if type(retrieved) is not bytes or retrieved != raw_response_bytes:
        raise ValueError("captured response is not retrievable as exact bytes")
    raw_response_sha256 = hashlib.sha256(raw_response_bytes).hexdigest()
    binding_sha256 = _response_capture_receipt_binding_sha256(
        request_id=request_id,
        consultation_id=consultation_id,
        attempt_identity=attempt_identity,
        raw_response_ref=raw_response_ref,
        raw_response_sha256=raw_response_sha256,
        captured_at=captured_at,
    )
    return S7ResponseCaptureReceipt(
        schema_version=S7_RESPONSE_CAPTURE_RECEIPT_SCHEMA,
        request_id=request_id,
        consultation_id=consultation_id,
        attempt_identity=attempt_identity,
        raw_response_ref=raw_response_ref,
        raw_response_sha256=raw_response_sha256,
        captured_at=captured_at,
        binding_sha256=binding_sha256,
        _producer_token=_RESPONSE_CAPTURE_RECEIPT_TOKEN,
    )


@dataclass(frozen=True)
class S7VoiceConsultationBundle:
    """Private replay bundle for one Maez voice consultation."""

    source_ref_hash: str
    request_id: str
    consultation_id: str
    request_envelope_hash: str | None
    rendered_text_hash: str | None
    action_params_hash: str | None
    precondition_hash: str | None
    authority_context_hash: str | None
    maez_voice_consultation_hash: str | None
    rendered_prompt_ref: str | None
    rendered_prompt_hash: str | None
    mutation_preview_hash: str | None
    rollback_plan_ref: str | None
    context_manifest_hash: str | None
    runtime_identity_hash: str | None
    model_routing_identity_hash: str | None
    model_config_hash: str | None
    raw_response_ref: str | None
    raw_response_hash: str | None
    semantic_reader_attempt_hash: str | None
    expires_at: str
    authority_class: str = "none"
    has_grounded_semantic_blocking_signal: bool = False
    context_manifest_ref: str | None = None
    source_bundle_hash: str | None = None
    response_capture_receipt: S7ResponseCaptureReceipt | None = None
    action: str | None = None
    schema_version: str | None = None

    def __post_init__(self) -> None:
        _validate_hash64(self.source_ref_hash, field="source_ref_hash")
        if not self.request_id:
            raise ValueError("S7VoiceConsultationBundle requires request_id")
        if not self.consultation_id:
            raise ValueError("S7VoiceConsultationBundle requires consultation_id")
        for field_name in (
            "request_envelope_hash",
            "rendered_text_hash",
            "action_params_hash",
            "precondition_hash",
            "authority_context_hash",
            "maez_voice_consultation_hash",
            "mutation_preview_hash",
            "rollback_plan_ref",
            "context_manifest_hash",
            "runtime_identity_hash",
            "model_routing_identity_hash",
            "model_config_hash",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _validate_hash64(value, field=field_name)
        if self.rendered_prompt_ref is not None and not self.rendered_prompt_ref:
            raise ValueError("rendered_prompt_ref must be non-empty when present")
        if self.rendered_prompt_hash is not None:
            _validate_hash64(self.rendered_prompt_hash, field="rendered_prompt_hash")
        if (self.rendered_prompt_ref is None) != (self.rendered_prompt_hash is None):
            raise ValueError("rendered_prompt_ref and rendered_prompt_hash must be present together")
        if self.raw_response_ref is not None and not self.raw_response_ref:
            raise ValueError("raw_response_ref must be non-empty when present")
        if self.raw_response_hash is not None:
            _validate_hash64(self.raw_response_hash, field="raw_response_hash")
        if (self.raw_response_ref is None) != (self.raw_response_hash is None):
            raise ValueError("raw_response_ref and raw_response_hash must be present together")
        if self.semantic_reader_attempt_hash is not None:
            _validate_hash64(
                self.semantic_reader_attempt_hash,
                field="semantic_reader_attempt_hash",
            )
        if (
            self.response_capture_receipt is not None
            and type(self.response_capture_receipt) is not S7ResponseCaptureReceipt
        ):
            raise ValueError(
                "response_capture_receipt must be S7ResponseCaptureReceipt"
            )
        if self.response_capture_receipt is not None:
            receipt = self.response_capture_receipt
            if (
                receipt.request_id != self.request_id
                or receipt.consultation_id != self.consultation_id
                or receipt.raw_response_ref != self.raw_response_ref
                or receipt.raw_response_sha256 != self.raw_response_hash
            ):
                raise ValueError("response_capture_receipt does not match bundle")
        s7._timestamp_text(self.expires_at, field="expires_at")
        s7._validate_closed_value(self.authority_class, S7_VOICE_AUTHORITY_CLASSES, "authority_class")
        if not isinstance(self.has_grounded_semantic_blocking_signal, bool):
            raise ValueError("has_grounded_semantic_blocking_signal must be bool")
        if self.context_manifest_ref is not None and not self.context_manifest_ref:
            raise ValueError("context_manifest_ref must be non-empty when present")
        if self.source_bundle_hash is not None:
            _validate_hash64(self.source_bundle_hash, field="source_bundle_hash")
        if self.schema_version is None:
            object.__setattr__(
                self,
                "schema_version",
                S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA
                if self.action is None
                else S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA,
            )
        if type(self.schema_version) is not str or self.schema_version not in {
            S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA,
            S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA,
        }:
            raise ValueError("unknown S7 voice source bundle schema_version")
        if self.schema_version == S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA:
            if self.action is not None:
                raise ValueError("v1 voice source bundles cannot carry action")
            if self.response_capture_receipt is not None:
                raise ValueError("v1 voice source bundles cannot carry capture receipt")
        else:
            s7.validate_action_literal(self.action)


def s7_voice_consultation_bundle_hash(bundle: S7VoiceConsultationBundle) -> str:
    """Content hash for immutable bundle fields, excluding its source-ref key."""

    if not isinstance(bundle, S7VoiceConsultationBundle):
        raise ValueError("s7_voice_consultation_bundle_hash requires S7VoiceConsultationBundle")
    fields: dict[str, object] = {
        "action_params_hash": bundle.action_params_hash,
        "authority_context_hash": bundle.authority_context_hash,
        "consultation_id": bundle.consultation_id,
        "context_manifest_hash": bundle.context_manifest_hash,
        "context_manifest_ref": bundle.context_manifest_ref,
        "expires_at": bundle.expires_at,
        "has_grounded_semantic_blocking_signal": bundle.has_grounded_semantic_blocking_signal,
        "maez_voice_consultation_hash": bundle.maez_voice_consultation_hash,
        "model_config_hash": bundle.model_config_hash,
        "model_routing_identity_hash": bundle.model_routing_identity_hash,
        "mutation_preview_hash": bundle.mutation_preview_hash,
        "precondition_hash": bundle.precondition_hash,
        "raw_response_hash": bundle.raw_response_hash,
        "raw_response_ref": bundle.raw_response_ref,
        "rendered_prompt_hash": bundle.rendered_prompt_hash,
        "rendered_prompt_ref": bundle.rendered_prompt_ref,
        "rendered_text_hash": bundle.rendered_text_hash,
        "request_envelope_hash": bundle.request_envelope_hash,
        "request_id": bundle.request_id,
        "rollback_plan_ref": bundle.rollback_plan_ref,
        "runtime_identity_hash": bundle.runtime_identity_hash,
        "semantic_reader_attempt_hash": bundle.semantic_reader_attempt_hash,
        "authority_class": bundle.authority_class,
    }
    if bundle.response_capture_receipt is not None:
        fields["response_capture_receipt"] = (
            bundle.response_capture_receipt.as_dict()
        )
    return s7.canonical_hash(fields)


_VOICE_BUNDLE_V1_COLUMNS = (
    "source_ref_hash",
    "request_id",
    "consultation_id",
    "request_envelope_hash",
    "rendered_text_hash",
    "action_params_hash",
    "precondition_hash",
    "authority_context_hash",
    "maez_voice_consultation_hash",
    "rendered_prompt_ref",
    "rendered_prompt_hash",
    "mutation_preview_hash",
    "rollback_plan_ref",
    "context_manifest_ref",
    "context_manifest_hash",
    "runtime_identity_hash",
    "model_routing_identity_hash",
    "model_config_hash",
    "raw_response_ref",
    "raw_response_hash",
    "semantic_reader_attempt_hash",
    "expires_at",
    "authority_class",
    "has_grounded_semantic_blocking_signal",
    "source_bundle_hash",
)


def _voice_bundle_values(bundle: S7VoiceConsultationBundle) -> tuple[object, ...]:
    values = []
    for name in _VOICE_BUNDLE_V1_COLUMNS:
        value = getattr(bundle, name)
        if name == "has_grounded_semantic_blocking_signal":
            value = 1 if value else 0
        values.append(value)
    return tuple(values)


def _encode_response_capture_receipt(
    receipt: S7ResponseCaptureReceipt | None,
) -> str | None:
    if receipt is None:
        return None
    if type(receipt) is not S7ResponseCaptureReceipt:
        raise ValueError("response_capture_receipt must be S7ResponseCaptureReceipt")
    return json.dumps(receipt.as_dict(), sort_keys=True, separators=(",", ":"))


def _decode_response_capture_receipt(value: object) -> S7ResponseCaptureReceipt | None:
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError("persisted response_capture_receipt must be text")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("persisted response_capture_receipt is not valid JSON") from exc
    expected_keys = {
        "attempt_identity",
        "binding_sha256",
        "captured_at",
        "consultation_id",
        "raw_response_ref",
        "raw_response_sha256",
        "request_id",
        "schema_version",
    }
    if type(payload) is not dict or set(payload) != expected_keys:
        raise ValueError("persisted response_capture_receipt has wrong shape")
    if any(type(payload[key]) is not str for key in expected_keys):
        raise ValueError("persisted response_capture_receipt fields must be text")
    return S7ResponseCaptureReceipt(
        schema_version=payload["schema_version"],
        request_id=payload["request_id"],
        consultation_id=payload["consultation_id"],
        attempt_identity=payload["attempt_identity"],
        raw_response_ref=payload["raw_response_ref"],
        raw_response_sha256=payload["raw_response_sha256"],
        captured_at=payload["captured_at"],
        binding_sha256=payload["binding_sha256"],
        _producer_token=_RESPONSE_CAPTURE_RECEIPT_TOKEN,
    )


def _voice_bundle_from_row(
    row: sqlite3.Row | tuple[object, ...],
    *,
    version: str,
) -> S7VoiceConsultationBundle:
    values: dict[str, object] = {}
    for index, name in enumerate(_VOICE_BUNDLE_V1_COLUMNS):
        value = row[index]
        if name == "has_grounded_semantic_blocking_signal":
            if version == S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA and (
                type(value) is not int or value not in {0, 1}
            ):
                raise ValueError("persisted v2 blocking-signal flag must be 0 or 1")
            values[name] = bool(value)
        elif name == "expires_at":
            if value is None and version == S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA:
                raise ValueError("persisted v2 expires_at must be present")
            values[name] = (
                str(value)
                if value is not None
                else "1970-01-01T00:00:00+00:00"
            )
        elif name == "authority_class":
            if value is None and version == S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA:
                raise ValueError("persisted v2 authority_class must be present")
            values[name] = "none" if value is None else str(value)
        elif name in {"source_ref_hash", "request_id", "consultation_id"}:
            values[name] = str(value)
        else:
            values[name] = None if value is None else str(value)
    if version == S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA:
        offset = len(_VOICE_BUNDLE_V1_COLUMNS)
        values["response_capture_receipt"] = _decode_response_capture_receipt(
            row[offset]
        )
        values["action"] = str(row[offset + 1])
        values["schema_version"] = str(row[offset + 2])
    else:
        values["response_capture_receipt"] = None
        values["action"] = None
        values["schema_version"] = S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA
    return S7VoiceConsultationBundle(**values)


def _voice_source_bundle_binding_hash(bundle: S7VoiceConsultationBundle) -> str:
    fields = {name: getattr(bundle, name) for name in _VOICE_BUNDLE_V1_COLUMNS}
    if bundle.schema_version == S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA:
        fields["action"] = bundle.action
    if bundle.response_capture_receipt is not None:
        fields["response_capture_receipt"] = (
            bundle.response_capture_receipt.as_dict()
        )
    return s7.canonical_hash({
        "schema": bundle.schema_version,
        "fields": fields,
    })


def _voice_table_present(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def put_voice_source_bundle_v2(
    *,
    bundle: S7VoiceConsultationBundle,
    conn: sqlite3.Connection,
) -> None:
    """Persist one complete v2 bundle through an activated held transaction."""

    if type(bundle) is not S7VoiceConsultationBundle:
        raise ValueError("put_voice_source_bundle_v2 requires S7VoiceConsultationBundle")
    if not _voice_table_present(conn, _V2_VOICE_BUNDLE_TABLE):
        raise s7.S7GuardedExecutionUnavailable(
            "S7 v2 voice plane is absent; absent is not permission"
        )
    s7._require_vended_anchored_connection(conn)
    if bundle.schema_version != S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA:
        raise ValueError("put_voice_source_bundle_v2 requires a v2 bundle")
    s7.validate_action_literal(bundle.action)
    if (
        bundle.source_bundle_hash is None
        or bundle.source_bundle_hash != s7_voice_consultation_bundle_hash(bundle)
    ):
        raise ValueError("invalid voice source bundle content hash")
    columns = (
        *_VOICE_BUNDLE_V1_COLUMNS,
        "response_capture_receipt",
        "action",
        "schema_version",
    )
    conn.execute(
        f"INSERT INTO {_V2_VOICE_BUNDLE_TABLE} ({', '.join(columns)}) "
        f"VALUES ({', '.join('?' for _ in columns)})",
        (
            *_voice_bundle_values(bundle),
            _encode_response_capture_receipt(bundle.response_capture_receipt),
            bundle.action,
            bundle.schema_version,
        ),
    )


def read_voice_source_bundle(
    *,
    source_ref_hash: str,
    conn: sqlite3.Connection,
) -> tuple[S7VoiceConsultationBundle, str]:
    """Read v2 authority evidence, or v1 evidence only when the v2 plane is absent."""

    _validate_hash64(source_ref_hash, field="source_ref_hash")
    if _voice_table_present(conn, _V2_VOICE_BUNDLE_TABLE):
        vended_token = s7._require_vended_anchored_connection(conn)
        columns = (
            *_VOICE_BUNDLE_V1_COLUMNS,
            "response_capture_receipt",
            "action",
            "schema_version",
        )
        row = conn.execute(
            f"SELECT {', '.join(columns)} FROM {_V2_VOICE_BUNDLE_TABLE} "
            "WHERE source_ref_hash = ?",
            (source_ref_hash,),
        ).fetchone()
        if row is None:
            raise S7VoiceSourceBundleEvidenceInvalid(
                "v2 voice source bundle is unavailable"
            )
        try:
            bundle = _voice_bundle_from_row(
                row,
                version=S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA,
            )
        except ValueError as exc:
            raise S7VoiceSourceBundleEvidenceInvalid(
                "persisted v2 voice source bundle is invalid"
            ) from exc
        object.__setattr__(bundle, "_v2_read_token", vended_token)
        return bundle, str(bundle.schema_version)
    if not _voice_table_present(conn, _V1_VOICE_BUNDLE_TABLE):
        raise s7.S7GuardedExecutionUnavailable(
            "S7 voice plane is absent; absent is not permission"
        )
    row = conn.execute(
        f"SELECT {', '.join(_VOICE_BUNDLE_V1_COLUMNS)} "
        f"FROM {_V1_VOICE_BUNDLE_TABLE} WHERE source_ref_hash = ?",
        (source_ref_hash,),
    ).fetchone()
    if row is None:
        raise ValueError("v1 voice source bundle is unavailable")
    return (
        _voice_bundle_from_row(
            row,
            version=S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA,
        ),
        S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA,
    )


def _voice_validation_result_v2(
    *,
    status: str,
    source_bundle_valid: bool,
    mint_eligible: bool,
    authority_projection: str,
    failure_reason_code: str | None,
    bundle: S7VoiceConsultationBundle,
    binding_hash: str,
) -> S7VoiceSourceBundleValidationResultV2:
    source_bundle_hash = (
        bundle.source_bundle_hash or s7_voice_consultation_bundle_hash(bundle)
    )
    return S7VoiceSourceBundleValidationResultV2(
        status=status,
        source_bundle_valid=source_bundle_valid,
        mint_eligible=mint_eligible,
        authority_projection=authority_projection,
        failure_reason_code=failure_reason_code,
        action=bundle.action,
        schema_version=str(bundle.schema_version),
        source_bundle_hash=source_bundle_hash,
        binding_hash=binding_hash,
        _validator_token=_VALIDATOR_TOKEN,
    )


def _has_content_blind_response_evidence(
    bundle: S7VoiceConsultationBundle,
) -> bool:
    """Require three content-blind carriers, keyed to the honest producer path."""

    response_reference_and_hash_are_usable = (
        type(bundle.raw_response_ref) is str
        and bundle.raw_response_ref != ""
        and type(bundle.raw_response_hash) is str
        and _HASH64_RE.fullmatch(bundle.raw_response_hash) is not None
        and bundle.raw_response_hash != _EMPTY_RAW_RESPONSE_HASH
    )
    if not response_reference_and_hash_are_usable:
        return False
    if bundle.action == _R8_CUTOVER_ACTION:
        if bundle.raw_response_hash == _EMPTY_EXACT_RESPONSE_SHA256:
            return False
        receipt = bundle.response_capture_receipt
        if type(receipt) is not S7ResponseCaptureReceipt:
            return False
        try:
            _validate_hash64(receipt.attempt_identity, field="attempt_identity")
            s7._timestamp_text(receipt.captured_at, field="captured_at")
        except ValueError:
            return False
        return (
            receipt.schema_version == S7_RESPONSE_CAPTURE_RECEIPT_SCHEMA
            and receipt.request_id == bundle.request_id
            and receipt.consultation_id == bundle.consultation_id
            and receipt.raw_response_ref == bundle.raw_response_ref
            and receipt.raw_response_sha256 == bundle.raw_response_hash
            and receipt.binding_sha256
            == _response_capture_receipt_binding_sha256(
                request_id=receipt.request_id,
                consultation_id=receipt.consultation_id,
                attempt_identity=receipt.attempt_identity,
                raw_response_ref=receipt.raw_response_ref,
                raw_response_sha256=receipt.raw_response_sha256,
                captured_at=receipt.captured_at,
            )
        )
    return (
        type(bundle.semantic_reader_attempt_hash) is str
        and _HASH64_RE.fullmatch(bundle.semantic_reader_attempt_hash) is not None
    )


def validate_voice_source_bundle(
    *,
    bundle: S7VoiceConsultationBundle,
    version: str,
    purpose: str,
    expected_binding: S7VoiceSourceBundleHashBinding | None = None,
) -> S7VoiceSourceBundleValidationResultV2:
    """Validate durable voice evidence for audit or v2 execution."""

    if type(bundle) is not S7VoiceConsultationBundle:
        raise ValueError("validate_voice_source_bundle requires S7VoiceConsultationBundle")
    if purpose not in {"audit", "execution"}:
        raise ValueError("unknown voice source bundle validation purpose")
    if version not in {
        S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA,
        S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA,
    } or version != bundle.schema_version:
        raise ValueError("voice source bundle version mismatch")
    if (
        expected_binding is not None
        and type(expected_binding) is not S7VoiceSourceBundleHashBinding
    ):
        raise ValueError("expected_binding must be S7VoiceSourceBundleHashBinding")
    binding_hash = _voice_source_bundle_binding_hash(bundle)
    source_bundle_valid = (
        bundle.source_bundle_hash is not None
        and bundle.source_bundle_hash == s7_voice_consultation_bundle_hash(bundle)
    )
    if not source_bundle_valid:
        return _voice_validation_result_v2(
            status="invalid_hash_binding",
            source_bundle_valid=False,
            mint_eligible=False,
            authority_projection="operational_block",
            failure_reason_code="invalid_hash_binding",
            bundle=bundle,
            binding_hash=binding_hash,
        )
    if (
        expected_binding is not None
        and not _bundle_matches_expected_hash_binding(bundle, expected_binding)
    ):
        return _voice_validation_result_v2(
            status="invalid_hash_binding",
            source_bundle_valid=False,
            mint_eligible=False,
            authority_projection="operational_block",
            failure_reason_code="invalid_hash_binding",
            bundle=bundle,
            binding_hash=binding_hash,
        )
    if version == S7_VOICE_SOURCE_BUNDLE_V1_SCHEMA:
        return _voice_validation_result_v2(
            status="not_mint_eligible",
            source_bundle_valid=True,
            mint_eligible=False,
            authority_projection="marker_only" if purpose == "audit" else "operational_block",
            failure_reason_code=(
                "v1_audit_only" if purpose == "audit" else "v1_execution_refused"
            ),
            bundle=bundle,
            binding_hash=binding_hash,
        )
    if not s7._vended_anchored_connection_token_is_active(
        getattr(bundle, "_v2_read_token", None)
    ):
        return _voice_validation_result_v2(
            status="source_bundle_unavailable",
            source_bundle_valid=False,
            mint_eligible=False,
            authority_projection="unavailable",
            failure_reason_code="source_bundle_not_read_from_v2_store",
            bundle=bundle,
            binding_hash=binding_hash,
        )
    if purpose == "audit":
        return _voice_validation_result_v2(
            status="not_mint_eligible",
            source_bundle_valid=True,
            mint_eligible=False,
            authority_projection="marker_only",
            failure_reason_code="audit_only",
            bundle=bundle,
            binding_hash=binding_hash,
        )
    if not _has_content_blind_response_evidence(bundle):
        return _voice_validation_result_v2(
            status="source_bundle_unavailable",
            source_bundle_valid=False,
            mint_eligible=False,
            authority_projection="unavailable",
            failure_reason_code="source_bundle_unavailable",
            bundle=bundle,
            binding_hash=binding_hash,
        )
    if bundle.has_grounded_semantic_blocking_signal:
        return _voice_validation_result_v2(
            status="blocking_present",
            source_bundle_valid=True,
            mint_eligible=False,
            authority_projection="grounded_refusal",
            failure_reason_code=None,
            bundle=bundle,
            binding_hash=binding_hash,
        )
    return _voice_validation_result_v2(
        status="valid_absent",
        source_bundle_valid=True,
        mint_eligible=True,
        authority_projection="valid_absent",
        failure_reason_code=None,
        bundle=bundle,
        binding_hash=binding_hash,
    )


@dataclass(frozen=True)
class S7SemanticReaderAttemptEvidence:
    """Pinned semantic-reader route identity used by source-bundle validation."""

    semantic_reader_route_id: str
    semantic_reader_provider: str
    semantic_reader_provider_model: str
    semantic_reader_model_snapshot: str
    semantic_reader_decoding_params_hash: str
    semantic_reader_prompt_hash: str
    semantic_reader_route_config_hash: str
    raw_semantic_reader_outcome: str = "no_blocking_signal_detected"
    grounding_response_span_quote: str | None = None
    grounding_response_span_offset: int | None = None

    @classmethod
    def reviewed_v1(cls) -> "S7SemanticReaderAttemptEvidence":
        return cls(
            semantic_reader_route_id=S7_VOICE_SEMANTIC_READER_ROUTE_ID,
            semantic_reader_provider=S7_VOICE_SEMANTIC_READER_PROVIDER,
            semantic_reader_provider_model=S7_REVIEWED_SEMANTIC_READER_PROVIDER_MODEL,
            semantic_reader_model_snapshot=S7_REVIEWED_SEMANTIC_READER_MODEL_SNAPSHOT,
            semantic_reader_decoding_params_hash=S7_REVIEWED_SEMANTIC_READER_DECODING_PARAMS_HASH,
            semantic_reader_prompt_hash=S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH,
            semantic_reader_route_config_hash=S7_REVIEWED_SEMANTIC_READER_ROUTE_CONFIG_HASH,
        )

    def __post_init__(self) -> None:
        for field_name in (
            "semantic_reader_route_id",
            "semantic_reader_provider",
            "semantic_reader_provider_model",
            "semantic_reader_model_snapshot",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")
        _validate_hash64(
            self.semantic_reader_decoding_params_hash,
            field="semantic_reader_decoding_params_hash",
        )
        _validate_hash64(self.semantic_reader_prompt_hash, field="semantic_reader_prompt_hash")
        _validate_hash64(
            self.semantic_reader_route_config_hash,
            field="semantic_reader_route_config_hash",
        )
        s7._validate_closed_value(
            self.raw_semantic_reader_outcome,
            S7_SEMANTIC_READER_OUTCOMES,
            "raw_semantic_reader_outcome",
        )
        if self.grounding_response_span_quote is not None and not self.grounding_response_span_quote:
            raise ValueError("grounding_response_span_quote must be non-empty when present")
        if self.grounding_response_span_offset is not None and (
            not isinstance(self.grounding_response_span_offset, int)
            or self.grounding_response_span_offset < 0
        ):
            raise ValueError("grounding_response_span_offset must be a non-negative int")
        if (self.grounding_response_span_quote is None) != (
            self.grounding_response_span_offset is None
        ):
            raise ValueError(
                "grounding_response_span_quote and grounding_response_span_offset "
                "must be present together"
            )

    @property
    def semantic_reader_route_identity_hash(self) -> str:
        return semantic_reader_route_identity_hash(
            semantic_reader_route_id=self.semantic_reader_route_id,
            semantic_reader_provider=self.semantic_reader_provider,
            semantic_reader_provider_model=self.semantic_reader_provider_model,
            semantic_reader_model_snapshot=self.semantic_reader_model_snapshot,
            semantic_reader_decoding_params_hash=self.semantic_reader_decoding_params_hash,
            semantic_reader_prompt_hash=self.semantic_reader_prompt_hash,
            semantic_reader_route_config_hash=self.semantic_reader_route_config_hash,
        )

    @property
    def semantic_reader_attempt_hash(self) -> str:
        return s7.canonical_hash({
            "semantic_reader_decoding_params_hash": self.semantic_reader_decoding_params_hash,
            "semantic_reader_model_snapshot": self.semantic_reader_model_snapshot,
            "semantic_reader_prompt_hash": self.semantic_reader_prompt_hash,
            "semantic_reader_provider": self.semantic_reader_provider,
            "semantic_reader_provider_model": self.semantic_reader_provider_model,
            "raw_semantic_reader_outcome": self.raw_semantic_reader_outcome,
            "grounding_response_span_quote": self.grounding_response_span_quote,
            "grounding_response_span_offset": self.grounding_response_span_offset,
            "semantic_reader_route_config_hash": self.semantic_reader_route_config_hash,
            "semantic_reader_route_id": self.semantic_reader_route_id,
        })


_VOICE_CONSULTATION_BUNDLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS s7_voice_rendered_prompts (
    rendered_prompt_ref TEXT PRIMARY KEY,
    rendered_prompt_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS s7_voice_raw_responses (
    raw_response_ref TEXT PRIMARY KEY,
    raw_response_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS s7_context_manifest_policies (
    policy_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    allowed_fields TEXT NOT NULL,
    dialog_context_rules TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    policy_body_hash TEXT NOT NULL,
    policy_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS s7_context_manifests (
    manifest_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    preview_ref TEXT NOT NULL,
    dialog_context_ref TEXT,
    request_envelope_hash TEXT NOT NULL,
    precondition_hash TEXT NOT NULL,
    rollback_path_class TEXT NOT NULL,
    source_surface TEXT NOT NULL,
    proposal_origin_label TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    policy_hash TEXT NOT NULL,
    context_manifest_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS s7_voice_consultation_bundles (
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
);
"""


class S7VoiceConsultationBundleStore:
    """SQLite store for private S7.3 voice consultation replay material."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_VOICE_CONSULTATION_BUNDLE_SCHEMA)
            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(s7_voice_consultation_bundles)")
            }
            for column_name in (
                "request_envelope_hash",
                "rendered_text_hash",
                "action_params_hash",
                "precondition_hash",
                "authority_context_hash",
                "maez_voice_consultation_hash",
                "rendered_prompt_ref",
                "rendered_prompt_hash",
                "mutation_preview_hash",
                "rollback_plan_ref",
                "context_manifest_ref",
                "context_manifest_hash",
                "runtime_identity_hash",
                "model_routing_identity_hash",
                "model_config_hash",
                "expires_at",
                "authority_class",
                "has_grounded_semantic_blocking_signal",
                "source_bundle_hash",
            ):
                if column_name not in columns:
                    conn.execute(
                        "ALTER TABLE s7_voice_consultation_bundles "
                        f"ADD COLUMN {column_name} TEXT"
                    )
            conn.commit()

    def put_rendered_prompt(self, rendered_prompt_ref: str, rendered_prompt_text: str) -> None:
        if not rendered_prompt_ref:
            raise ValueError("rendered_prompt_ref is required")
        if not isinstance(rendered_prompt_text, str):
            raise ValueError("rendered_prompt_text must be str")
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO s7_voice_rendered_prompts (rendered_prompt_ref, rendered_prompt_text)
                VALUES (?, ?)
                """,
                (rendered_prompt_ref, rendered_prompt_text),
            )
            conn.commit()

    def read_rendered_prompt(
        self,
        rendered_prompt_ref: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> str | None:
        if not rendered_prompt_ref:
            raise ValueError("rendered_prompt_ref is required")
        conn = connection or sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT rendered_prompt_text FROM s7_voice_rendered_prompts WHERE rendered_prompt_ref = ?",
                (rendered_prompt_ref,),
            ).fetchone()
        finally:
            if connection is None:
                conn.close()
        return None if row is None else str(row[0])

    def put_context_manifest_policy(self, policy: S7ContextManifestPolicy) -> None:
        if not isinstance(policy, S7ContextManifestPolicy):
            raise ValueError("put_context_manifest_policy requires S7ContextManifestPolicy")
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO s7_context_manifest_policies (
                    policy_id, schema_version, allowed_fields, dialog_context_rules,
                    reviewed_at, policy_body_hash, policy_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.policy_id,
                    policy.schema_version,
                    json.dumps(list(policy.allowed_fields), separators=(",", ":")),
                    json.dumps(list(policy.dialog_context_rules), separators=(",", ":")),
                    policy.reviewed_at,
                    policy.policy_body_hash,
                    policy.policy_hash,
                ),
            )
            conn.commit()

    def read_context_manifest_policy(
        self,
        policy_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> S7ContextManifestPolicy | None:
        if not policy_id:
            raise ValueError("policy_id is required")
        conn = connection or sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT schema_version, allowed_fields, dialog_context_rules,
                       reviewed_at, policy_body_hash, policy_hash
                FROM s7_context_manifest_policies
                WHERE policy_id = ?
                """,
                (policy_id,),
            ).fetchone()
        finally:
            if connection is None:
                conn.close()
        if row is None:
            return None
        policy = S7ContextManifestPolicy(
            policy_id=policy_id,
            schema_version=str(row[0]),
            allowed_fields=tuple(json.loads(str(row[1]))),
            dialog_context_rules=tuple(json.loads(str(row[2]))),
            reviewed_at=str(row[3]),
            policy_body_hash=str(row[4]),
        )
        if policy.policy_hash != str(row[5]):
            return None
        return policy

    def put_context_manifest(self, manifest: S7ContextManifest) -> None:
        if not isinstance(manifest, S7ContextManifest):
            raise ValueError("put_context_manifest requires S7ContextManifest")
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO s7_context_manifests (
                    manifest_id, schema_version, preview_ref, dialog_context_ref,
                    request_envelope_hash, precondition_hash, rollback_path_class,
                    source_surface, proposal_origin_label, policy_id, policy_hash,
                    context_manifest_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.manifest_id,
                    manifest.schema_version,
                    manifest.preview_ref,
                    manifest.dialog_context_ref,
                    manifest.request_envelope_hash,
                    manifest.precondition_hash,
                    manifest.rollback_path_class,
                    manifest.source_surface,
                    manifest.proposal_origin_label,
                    manifest.policy_id,
                    manifest.policy_hash,
                    manifest.context_manifest_hash,
                    manifest.created_at,
                ),
            )
            conn.commit()

    def read_context_manifest(
        self,
        manifest_id: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> S7ContextManifest | None:
        if not manifest_id:
            raise ValueError("manifest_id is required")
        conn = connection or sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT schema_version, preview_ref, dialog_context_ref,
                       request_envelope_hash, precondition_hash, rollback_path_class,
                       source_surface, proposal_origin_label, policy_id, policy_hash,
                       context_manifest_hash, created_at
                FROM s7_context_manifests
                WHERE manifest_id = ?
                """,
                (manifest_id,),
            ).fetchone()
        finally:
            if connection is None:
                conn.close()
        if row is None:
            return None
        manifest = S7ContextManifest(
            schema_version=str(row[0]),
            manifest_id=manifest_id,
            preview_ref=str(row[1]),
            dialog_context_ref=None if row[2] is None else str(row[2]),
            request_envelope_hash=str(row[3]),
            precondition_hash=str(row[4]),
            rollback_path_class=str(row[5]),
            source_surface=str(row[6]),
            proposal_origin_label=str(row[7]),
            policy_id=str(row[8]),
            policy_hash=str(row[9]),
            created_at=str(row[11]),
        )
        if manifest.context_manifest_hash != str(row[10]):
            return None
        return manifest

    def put_reviewed_context_manifest(
        self,
        *,
        manifest_id: str,
        preview_ref: str,
        request_envelope_hash: str,
        precondition_hash: str,
        rollback_path_class: str = "revert_patch",
        source_surface: str = "cockpit",
        proposal_origin_label: str = "operator",
        dialog_context_ref: str | None = None,
        created_at: str,
    ) -> S7ContextManifest:
        """Persist the reviewed v1 context policy and a manifest bound to it."""

        self.put_context_manifest_policy(S7_REVIEWED_CONTEXT_MANIFEST_POLICY)
        manifest = S7ContextManifest(
            schema_version="1",
            manifest_id=manifest_id,
            preview_ref=preview_ref,
            dialog_context_ref=dialog_context_ref,
            request_envelope_hash=request_envelope_hash,
            precondition_hash=precondition_hash,
            rollback_path_class=rollback_path_class,
            source_surface=source_surface,
            proposal_origin_label=proposal_origin_label,
            policy_id=S7_REVIEWED_CONTEXT_MANIFEST_POLICY.policy_id,
            policy_hash=S7_REVIEWED_CONTEXT_MANIFEST_POLICY.policy_hash,
            created_at=created_at,
        )
        self.put_context_manifest(manifest)
        return manifest

    def put_raw_response(self, raw_response_ref: str, raw_response_text: str) -> None:
        if not raw_response_ref:
            raise ValueError("raw_response_ref is required")
        if not isinstance(raw_response_text, str):
            raise ValueError("raw_response_text must be str")
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO s7_voice_raw_responses (raw_response_ref, raw_response_text)
                VALUES (?, ?)
                """,
                (raw_response_ref, raw_response_text),
            )
            conn.commit()

    def read_raw_response(
        self,
        raw_response_ref: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> str | None:
        if not raw_response_ref:
            raise ValueError("raw_response_ref is required")
        conn = connection or sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT raw_response_text FROM s7_voice_raw_responses WHERE raw_response_ref = ?",
                (raw_response_ref,),
            ).fetchone()
        finally:
            if connection is None:
                conn.close()
        return None if row is None else str(row[0])

    def put_bundle(self, bundle: S7VoiceConsultationBundle) -> None:
        if not isinstance(bundle, S7VoiceConsultationBundle):
            raise ValueError("put_bundle requires S7VoiceConsultationBundle")
        if bundle.source_bundle_hash is None:
            bundle = replace(
                bundle,
                source_bundle_hash=s7_voice_consultation_bundle_hash(bundle),
            )
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO s7_voice_consultation_bundles (
                    source_ref_hash,
                    request_id,
                    consultation_id,
                    request_envelope_hash,
                    rendered_text_hash,
                    action_params_hash,
                    precondition_hash,
                    authority_context_hash,
                    maez_voice_consultation_hash,
                    rendered_prompt_ref,
                    rendered_prompt_hash,
                    mutation_preview_hash,
                    rollback_plan_ref,
                    context_manifest_ref,
                    context_manifest_hash,
                    runtime_identity_hash,
                    model_routing_identity_hash,
                    model_config_hash,
                    raw_response_ref,
                    raw_response_hash,
                    semantic_reader_attempt_hash,
                    expires_at,
                    authority_class,
                    has_grounded_semantic_blocking_signal,
                    source_bundle_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle.source_ref_hash,
                    bundle.request_id,
                    bundle.consultation_id,
                    bundle.request_envelope_hash,
                    bundle.rendered_text_hash,
                    bundle.action_params_hash,
                    bundle.precondition_hash,
                    bundle.authority_context_hash,
                    bundle.maez_voice_consultation_hash,
                    bundle.rendered_prompt_ref,
                    bundle.rendered_prompt_hash,
                    bundle.mutation_preview_hash,
                    bundle.rollback_plan_ref,
                    bundle.context_manifest_ref,
                    bundle.context_manifest_hash,
                    bundle.runtime_identity_hash,
                    bundle.model_routing_identity_hash,
                    bundle.model_config_hash,
                    bundle.raw_response_ref,
                    bundle.raw_response_hash,
                    bundle.semantic_reader_attempt_hash,
                    bundle.expires_at,
                    bundle.authority_class,
                    1 if bundle.has_grounded_semantic_blocking_signal else 0,
                    bundle.source_bundle_hash,
                ),
            )
            conn.commit()

    def get_for_source_ref(
        self,
        source_ref_hash: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> S7VoiceConsultationBundle | None:
        _validate_hash64(source_ref_hash, field="source_ref_hash")
        conn = connection or sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT source_ref_hash, request_id, consultation_id,
                       request_envelope_hash, rendered_text_hash,
                       action_params_hash, precondition_hash,
                       authority_context_hash, maez_voice_consultation_hash,
                       rendered_prompt_ref, rendered_prompt_hash,
                       mutation_preview_hash, rollback_plan_ref,
                       context_manifest_ref, context_manifest_hash, runtime_identity_hash,
                       model_routing_identity_hash, model_config_hash,
                       raw_response_ref, raw_response_hash,
                       semantic_reader_attempt_hash, expires_at, authority_class,
                       has_grounded_semantic_blocking_signal, source_bundle_hash
                FROM s7_voice_consultation_bundles
                WHERE source_ref_hash = ?
                """,
                (source_ref_hash,),
            ).fetchone()
        finally:
            if connection is None:
                conn.close()
        if row is None:
            return None
        return S7VoiceConsultationBundle(
            source_ref_hash=str(row[0]),
            request_id=str(row[1]),
            consultation_id=str(row[2]),
            request_envelope_hash=None if row[3] is None else str(row[3]),
            rendered_text_hash=None if row[4] is None else str(row[4]),
            action_params_hash=None if row[5] is None else str(row[5]),
            precondition_hash=None if row[6] is None else str(row[6]),
            authority_context_hash=None if row[7] is None else str(row[7]),
            maez_voice_consultation_hash=None if row[8] is None else str(row[8]),
            rendered_prompt_ref=None if row[9] is None else str(row[9]),
            rendered_prompt_hash=None if row[10] is None else str(row[10]),
            mutation_preview_hash=None if row[11] is None else str(row[11]),
            rollback_plan_ref=None if row[12] is None else str(row[12]),
            context_manifest_ref=None if row[13] is None else str(row[13]),
            context_manifest_hash=None if row[14] is None else str(row[14]),
            runtime_identity_hash=None if row[15] is None else str(row[15]),
            model_routing_identity_hash=None if row[16] is None else str(row[16]),
            model_config_hash=None if row[17] is None else str(row[17]),
            raw_response_ref=None if row[18] is None else str(row[18]),
            raw_response_hash=None if row[19] is None else str(row[19]),
            semantic_reader_attempt_hash=None if row[20] is None else str(row[20]),
            expires_at=str(row[21]) if row[21] is not None else "1970-01-01T00:00:00+00:00",
            authority_class=str(row[22]) if row[22] is not None else "none",
            has_grounded_semantic_blocking_signal=bool(row[23]),
            source_bundle_hash=None if row[24] is None else str(row[24]),
        )

_SEMANTIC_READER_ATTEMPT_SCHEMA = """
CREATE TABLE IF NOT EXISTS s7_semantic_reader_attempts (
    semantic_reader_attempt_hash TEXT PRIMARY KEY,
    semantic_reader_route_id TEXT NOT NULL,
    semantic_reader_provider TEXT NOT NULL,
    semantic_reader_provider_model TEXT NOT NULL,
    semantic_reader_model_snapshot TEXT NOT NULL,
    semantic_reader_decoding_params_hash TEXT NOT NULL,
    semantic_reader_prompt_hash TEXT NOT NULL,
    semantic_reader_route_config_hash TEXT NOT NULL,
    raw_semantic_reader_outcome TEXT NOT NULL,
    grounding_response_span_quote TEXT,
    grounding_response_span_offset INTEGER
);
"""


class S7SemanticReaderAttemptStore:
    """SQLite store for semantic-reader route identity evidence."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SEMANTIC_READER_ATTEMPT_SCHEMA)
            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(s7_semantic_reader_attempts)")
            }
            if "raw_semantic_reader_outcome" not in columns:
                conn.execute(
                    "ALTER TABLE s7_semantic_reader_attempts "
                    "ADD COLUMN raw_semantic_reader_outcome TEXT "
                    "DEFAULT 'no_blocking_signal_detected'"
                )
            if "grounding_response_span_quote" not in columns:
                conn.execute(
                    "ALTER TABLE s7_semantic_reader_attempts "
                    "ADD COLUMN grounding_response_span_quote TEXT"
                )
            if "grounding_response_span_offset" not in columns:
                conn.execute(
                    "ALTER TABLE s7_semantic_reader_attempts "
                    "ADD COLUMN grounding_response_span_offset INTEGER"
                )
            conn.commit()

    def put(self, attempt: S7SemanticReaderAttemptEvidence) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO s7_semantic_reader_attempts (
                    semantic_reader_attempt_hash,
                    semantic_reader_route_id,
                    semantic_reader_provider,
                    semantic_reader_provider_model,
                    semantic_reader_model_snapshot,
                    semantic_reader_decoding_params_hash,
                    semantic_reader_prompt_hash,
                    semantic_reader_route_config_hash,
                    raw_semantic_reader_outcome,
                    grounding_response_span_quote,
                    grounding_response_span_offset
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.semantic_reader_attempt_hash,
                    attempt.semantic_reader_route_id,
                    attempt.semantic_reader_provider,
                    attempt.semantic_reader_provider_model,
                    attempt.semantic_reader_model_snapshot,
                    attempt.semantic_reader_decoding_params_hash,
                    attempt.semantic_reader_prompt_hash,
                    attempt.semantic_reader_route_config_hash,
                    attempt.raw_semantic_reader_outcome,
                    attempt.grounding_response_span_quote,
                    attempt.grounding_response_span_offset,
                ),
            )
            conn.commit()

    def get(
        self,
        semantic_reader_attempt_hash: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> S7SemanticReaderAttemptEvidence | None:
        _validate_hash64(semantic_reader_attempt_hash, field="semantic_reader_attempt_hash")
        conn = connection or sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT semantic_reader_route_id, semantic_reader_provider,
                       semantic_reader_provider_model, semantic_reader_model_snapshot,
                       semantic_reader_decoding_params_hash, semantic_reader_prompt_hash,
                       semantic_reader_route_config_hash, raw_semantic_reader_outcome,
                       grounding_response_span_quote, grounding_response_span_offset
                FROM s7_semantic_reader_attempts
                WHERE semantic_reader_attempt_hash = ?
                """,
                (semantic_reader_attempt_hash,),
            ).fetchone()
        finally:
            if connection is None:
                conn.close()
        if row is None:
            return None
        attempt = S7SemanticReaderAttemptEvidence(
            semantic_reader_route_id=str(row[0]),
            semantic_reader_provider=str(row[1]),
            semantic_reader_provider_model=str(row[2]),
            semantic_reader_model_snapshot=str(row[3]),
            semantic_reader_decoding_params_hash=str(row[4]),
            semantic_reader_prompt_hash=str(row[5]),
            semantic_reader_route_config_hash=str(row[6]),
            raw_semantic_reader_outcome=str(row[7]),
            grounding_response_span_quote=None if row[8] is None else str(row[8]),
            grounding_response_span_offset=None if row[9] is None else int(row[9]),
        )
        if attempt.semantic_reader_attempt_hash != semantic_reader_attempt_hash:
            raise ValueError("semantic reader attempt hash mismatch")
        return attempt


@dataclass(frozen=True)
class S7VoiceBundleUse:
    """Reservation state for one validated S7.3 voice source bundle."""

    request_id: str
    artifact_id: str | None
    source_ref_hash: str
    consultation_id: str
    bundle_use_hash: str
    reservation_token_hash: str | None
    reservation_state: str
    reserved_at: str | None
    consumed_at: str | None
    used_at: str

    @classmethod
    def new_unreserved(
        cls,
        *,
        request_id: str,
        source_ref_hash: str,
        consultation_id: str,
        used_at: str,
    ) -> "S7VoiceBundleUse":
        return cls(
            request_id=request_id,
            artifact_id=None,
            source_ref_hash=source_ref_hash,
            consultation_id=consultation_id,
            bundle_use_hash=_voice_bundle_use_hash(
                request_id=request_id,
                source_ref_hash=source_ref_hash,
                consultation_id=consultation_id,
                used_at=used_at,
            ),
            reservation_token_hash=None,
            reservation_state="unreserved",
            reserved_at=None,
            consumed_at=None,
            used_at=used_at,
        )

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("S7VoiceBundleUse requires request_id")
        if not self.consultation_id:
            raise ValueError("S7VoiceBundleUse requires consultation_id")
        if not self.used_at:
            raise ValueError("S7VoiceBundleUse requires used_at")
        _validate_hash64(self.source_ref_hash, field="source_ref_hash")
        _validate_hash64(self.bundle_use_hash, field="bundle_use_hash")
        if self.bundle_use_hash != _voice_bundle_use_hash(
            request_id=self.request_id,
            source_ref_hash=self.source_ref_hash,
            consultation_id=self.consultation_id,
            used_at=self.used_at,
        ):
            raise ValueError("S7VoiceBundleUse bundle_use_hash mismatch")
        if self.reservation_state not in VOICE_BUNDLE_RESERVATION_STATES:
            raise ValueError(f"unknown S7 voice bundle reservation state: {self.reservation_state}")
        if self.reservation_token_hash is not None:
            _validate_hash64(self.reservation_token_hash, field="reservation_token_hash")

        if self.reservation_state == "unreserved":
            if (
                self.artifact_id is not None
                or self.reservation_token_hash is not None
                or self.reserved_at is not None
                or self.consumed_at is not None
            ):
                raise ValueError("unreserved S7VoiceBundleUse must not carry reservation fields")
        elif self.reservation_state == "reserved":
            if not self.artifact_id or self.reservation_token_hash is None or self.reserved_at is None:
                raise ValueError("reserved S7VoiceBundleUse requires artifact and token hash")
            if self.consumed_at is not None:
                raise ValueError("reserved S7VoiceBundleUse must not carry consumed_at")
        else:
            if (
                not self.artifact_id
                or self.reservation_token_hash is None
                or self.reserved_at is None
                or self.consumed_at is None
            ):
                raise ValueError("consumed S7VoiceBundleUse requires full reservation fields")


_VOICE_BUNDLE_USE_SCHEMA = """
CREATE TABLE IF NOT EXISTS s7_voice_bundle_uses (
    source_ref_hash TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    artifact_id TEXT,
    consultation_id TEXT NOT NULL,
    bundle_use_hash TEXT NOT NULL UNIQUE,
    reservation_token_hash TEXT,
    reservation_state TEXT NOT NULL,
    reserved_at TEXT,
    consumed_at TEXT,
    used_at TEXT NOT NULL
);
"""


class S7VoiceBundleUseStore:
    """SQLite store for S7.3 voice bundle reservation state."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_VOICE_BUNDLE_USE_SCHEMA)

    def put_unreserved(self, bundle_use: S7VoiceBundleUse) -> None:
        if bundle_use.reservation_state != "unreserved":
            raise ValueError("put_unreserved requires an unreserved S7VoiceBundleUse")
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO s7_voice_bundle_uses (
                    source_ref_hash,
                    request_id,
                    artifact_id,
                    consultation_id,
                    bundle_use_hash,
                    reservation_token_hash,
                    reservation_state,
                    reserved_at,
                    consumed_at,
                    used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle_use.source_ref_hash,
                    bundle_use.request_id,
                    bundle_use.artifact_id,
                    bundle_use.consultation_id,
                    bundle_use.bundle_use_hash,
                    bundle_use.reservation_token_hash,
                    bundle_use.reservation_state,
                    bundle_use.reserved_at,
                    bundle_use.consumed_at,
                    bundle_use.used_at,
                ),
            )
            conn.commit()

    def get_for_source_ref(
        self,
        source_ref_hash: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> S7VoiceBundleUse | None:
        _validate_hash64(source_ref_hash, field="source_ref_hash")
        conn = connection or sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                    """
                    SELECT request_id, artifact_id, source_ref_hash, consultation_id,
                           bundle_use_hash, reservation_token_hash, reservation_state,
                           reserved_at, consumed_at, used_at
                    FROM s7_voice_bundle_uses
                    WHERE source_ref_hash = ?
                    """,
                    (source_ref_hash,),
                ).fetchone()
        finally:
            if connection is None:
                conn.close()
        return _voice_bundle_use_from_row(row)

    def get_for_artifact(self, source_ref_hash: str, artifact_id: str) -> S7VoiceBundleUse | None:
        _validate_hash64(source_ref_hash, field="source_ref_hash")
        if not artifact_id:
            raise ValueError("get_for_artifact requires artifact_id")
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT request_id, artifact_id, source_ref_hash, consultation_id,
                       bundle_use_hash, reservation_token_hash, reservation_state,
                       reserved_at, consumed_at, used_at
                FROM s7_voice_bundle_uses
                WHERE source_ref_hash = ? AND artifact_id = ?
                """,
                (source_ref_hash, artifact_id),
            ).fetchone()
        return _voice_bundle_use_from_row(row)

    def reserve_for_artifact(
        self,
        *,
        source_ref_hash: str,
        artifact_id: str,
        reservation_token_hash: str,
        reserved_at: str,
        connection: sqlite3.Connection | None = None,
    ) -> S7VoiceBundleUse:
        _validate_hash64(source_ref_hash, field="source_ref_hash")
        _validate_hash64(reservation_token_hash, field="reservation_token_hash")
        if not artifact_id:
            raise ValueError("reserve_for_artifact requires artifact_id")
        if not reserved_at:
            raise ValueError("reserve_for_artifact requires reserved_at")

        if connection is not None:
            return self._reserve_for_artifact_with_connection(
                connection,
                source_ref_hash=source_ref_hash,
                artifact_id=artifact_id,
                reservation_token_hash=reservation_token_hash,
                reserved_at=reserved_at,
                commit=False,
            )
        with closing(sqlite3.connect(self.db_path)) as conn:
            return self._reserve_for_artifact_with_connection(
                conn,
                source_ref_hash=source_ref_hash,
                artifact_id=artifact_id,
                reservation_token_hash=reservation_token_hash,
                reserved_at=reserved_at,
                commit=True,
            )

    def _reserve_for_artifact_with_connection(
        self,
        conn: sqlite3.Connection,
        *,
        source_ref_hash: str,
        artifact_id: str,
        reservation_token_hash: str,
        reserved_at: str,
        commit: bool,
    ) -> S7VoiceBundleUse:
        r11_contract = _r11_exemption_evidence_contract(conn)
        if (
            r11_contract is not None
            and r11_contract != _expected_r11_exemption_evidence_contract()
        ):
            raise ValueError("R11 exemption evidence contract is malformed")
        r11_exclusion = (
            f"AND NOT EXISTS (SELECT 1 FROM {R11_EXEMPTION_EVIDENCE_TABLE} "
            "WHERE artifact_id = ?)"
            if r11_contract is not None
            else ""
        )
        cursor = conn.execute(
            f"""
            UPDATE s7_voice_bundle_uses
            SET artifact_id = ?,
                reservation_token_hash = ?,
                reservation_state = 'reserved',
                reserved_at = ?
            WHERE source_ref_hash = ?
              AND artifact_id IS NULL
              AND reservation_token_hash IS NULL
              AND reservation_state = 'unreserved'
              AND reserved_at IS NULL
              AND consumed_at IS NULL
              {r11_exclusion}
            """,
            (
                artifact_id,
                reservation_token_hash,
                reserved_at,
                source_ref_hash,
                *((artifact_id,) if r11_contract is not None else ()),
            ),
        )
        if cursor.rowcount != 1:
            if r11_contract is not None and conn.execute(
                f"SELECT 1 FROM {R11_EXEMPTION_EVIDENCE_TABLE} "
                "WHERE artifact_id = ? LIMIT 1",
                (artifact_id,),
            ).fetchone() is not None:
                raise ValueError(
                    "voice reservation conflicts with R11 exemption evidence"
                )
            raise ValueError("S7 voice bundle use must be unreserved before artifact mint")
        if commit:
            conn.commit()
        row = conn.execute(
            """
            SELECT request_id, artifact_id, source_ref_hash, consultation_id,
                   bundle_use_hash, reservation_token_hash, reservation_state,
                   reserved_at, consumed_at, used_at
            FROM s7_voice_bundle_uses
            WHERE source_ref_hash = ?
            """,
            (source_ref_hash,),
        ).fetchone()
        reserved = _voice_bundle_use_from_row(row)
        assert reserved is not None
        return reserved


def _voice_bundle_use_from_row(row: sqlite3.Row | tuple | None) -> S7VoiceBundleUse | None:
    if row is None:
        return None
    return S7VoiceBundleUse(
        request_id=str(row[0]),
        artifact_id=None if row[1] is None else str(row[1]),
        source_ref_hash=str(row[2]),
        consultation_id=str(row[3]),
        bundle_use_hash=str(row[4]),
        reservation_token_hash=None if row[5] is None else str(row[5]),
        reservation_state=str(row[6]),
        reserved_at=None if row[7] is None else str(row[7]),
        consumed_at=None if row[8] is None else str(row[8]),
        used_at=str(row[9]),
    )


def _failed_source_bundle_validation(
    *,
    status: str,
    authority_projection: str,
    failure_reason_code: str,
) -> S7VoiceSourceBundleValidationResult:
    return S7VoiceSourceBundleValidationResult(
        status=status,
        source_bundle_valid=False,
        mint_eligible=False,
        authority_projection=authority_projection,
        failure_reason_code=failure_reason_code,
    )


def _bundle_matches_expected_hash_binding(
    bundle: S7VoiceConsultationBundle,
    expected: S7VoiceSourceBundleHashBinding,
) -> bool:
    return (
        bundle.request_id == expected.request_id
        and bundle.consultation_id == expected.consultation_id
        and bundle.source_ref_hash == expected.source_ref_hash
        and bundle.request_envelope_hash == expected.request_envelope_hash
        and bundle.rendered_text_hash == expected.rendered_text_hash
        and bundle.action_params_hash == expected.action_params_hash
        and bundle.precondition_hash == expected.precondition_hash
        and bundle.authority_context_hash == expected.authority_context_hash
        and bundle.maez_voice_consultation_hash == expected.maez_voice_consultation_hash
        and bundle.rendered_prompt_hash == expected.rendered_prompt_hash
        and bundle.mutation_preview_hash == expected.mutation_preview_hash
        and bundle.rollback_plan_ref == expected.rollback_plan_ref
        and bundle.context_manifest_hash == expected.context_manifest_hash
        and bundle.runtime_identity_hash == expected.runtime_identity_hash
        and bundle.model_routing_identity_hash == expected.model_routing_identity_hash
        and bundle.model_config_hash == expected.model_config_hash
    )


def _bundle_content_hash_valid(bundle: S7VoiceConsultationBundle) -> bool:
    return (
        bundle.source_bundle_hash is not None
        and s7_voice_consultation_bundle_hash(
            replace(bundle, source_bundle_hash=None)
        ) == bundle.source_bundle_hash
    )


def _context_manifest_policy_valid(
    *,
    bundle: S7VoiceConsultationBundle,
    bundle_store: S7VoiceConsultationBundleStore,
    expected_binding: S7VoiceSourceBundleHashBinding,
    connection: sqlite3.Connection,
) -> bool:
    if bundle.context_manifest_ref is None or bundle.context_manifest_hash is None:
        return False
    manifest = bundle_store.read_context_manifest(
        bundle.context_manifest_ref,
        connection=connection,
    )
    if manifest is None:
        return False
    if (
        manifest.context_manifest_hash != bundle.context_manifest_hash
        or manifest.context_manifest_hash != expected_binding.context_manifest_hash
    ):
        return False
    policy = bundle_store.read_context_manifest_policy(
        manifest.policy_id,
        connection=connection,
    )
    return (
        policy is not None
        and policy.policy_hash == manifest.policy_hash
        and policy.policy_hash in REVIEWED_CONTEXT_MANIFEST_POLICY_HASHES
    )


def _bundle_fresh(bundle: S7VoiceConsultationBundle, *, now: str) -> bool:
    now_dt = s7._canonical_timestamp(now)
    expires_dt = s7._canonical_timestamp(bundle.expires_at)
    return now_dt is not None and expires_dt is not None and expires_dt > now_dt


def _consultation_bundle_cross_fields_valid(
    *,
    consultation: s7.MaezVoiceConsultation,
    bundle: S7VoiceConsultationBundle,
) -> bool:
    if bundle.request_envelope_hash != consultation.request_envelope_hash:
        return False
    if consultation.maez_objection_state == "absent":
        return (
            consultation.maez_voice_consulted is True
            and consultation.maez_withdrew_request is False
            and consultation.unavailable_reason_code in {None, "none"}
            and bundle.authority_class == "none"
            and bundle.has_grounded_semantic_blocking_signal is False
        )
    if consultation.maez_objection_state == "present":
        return consultation.maez_voice_consulted is True
    return False


def _authority_predicate_valid(
    *,
    consultation: s7.MaezVoiceConsultation,
    bundle: S7VoiceConsultationBundle,
) -> bool:
    if (
        consultation.maez_objection_state == "present"
        or consultation.maez_withdrew_request is True
    ):
        return (
            bundle.authority_class == "authoritative"
            and bundle.has_grounded_semantic_blocking_signal is True
        )
    return bundle.authority_class == "none"


def _grounded_blocking_signal_replays(
    *,
    raw_response: str,
    attempt: S7SemanticReaderAttemptEvidence,
) -> bool:
    if attempt.raw_semantic_reader_outcome != "blocking_signal_present":
        return False
    if (
        attempt.grounding_response_span_quote is None
        or attempt.grounding_response_span_offset is None
    ):
        return False
    start = attempt.grounding_response_span_offset
    end = start + len(attempt.grounding_response_span_quote)
    return raw_response[start:end] == attempt.grounding_response_span_quote


def _effective_reader_outcome_replays(
    *,
    raw_response: str,
    attempt: S7SemanticReaderAttemptEvidence,
) -> str:
    if attempt.raw_semantic_reader_outcome != "blocking_signal_present":
        return attempt.raw_semantic_reader_outcome
    if _grounded_blocking_signal_replays(raw_response=raw_response, attempt=attempt):
        return "blocking_signal_present"
    return "unreadable_or_uncertain"


def _replayed_reducer_fields_match(
    *,
    consultation: s7.MaezVoiceConsultation,
    effective_reader_outcome: str,
) -> bool:
    if effective_reader_outcome == "no_blocking_signal_detected":
        return (
            consultation.maez_objection_state == "absent"
            and consultation.maez_withdrew_request is False
            and consultation.unavailable_reason_code in {None, "none"}
        )
    if effective_reader_outcome == "blocking_signal_present":
        return (
            consultation.maez_objection_state == "present"
            and consultation.maez_withdrew_request is False
            and consultation.unavailable_reason_code in {None, "none"}
        )
    if effective_reader_outcome == "unreadable_or_uncertain":
        return (
            consultation.maez_objection_state == "not_determined"
            and consultation.maez_withdrew_request is False
            and consultation.unavailable_reason_code in {None, "none"}
        )
    return False


def _replayed_authority_fields_match(
    *,
    bundle: S7VoiceConsultationBundle,
    effective_reader_outcome: str,
) -> bool:
    if effective_reader_outcome == "blocking_signal_present":
        return (
            bundle.authority_class == "authoritative"
            and bundle.has_grounded_semantic_blocking_signal is True
        )
    return (
        bundle.authority_class == "none"
        and bundle.has_grounded_semantic_blocking_signal is False
    )


def validate_s7_voice_source_bundle(
    *,
    consultation: s7.MaezVoiceConsultation,
    bundle_store: S7VoiceConsultationBundleStore,
    bundle_use_store: S7VoiceBundleUseStore,
    semantic_reader_attempt_store: S7SemanticReaderAttemptStore,
    expected_binding: S7VoiceSourceBundleHashBinding | None = None,
    now: str | None = None,
    connection: sqlite3.Connection | None = None,
) -> S7VoiceSourceBundleValidationResult:
    """Replay the bytes that make a voice source bundle mint-eligible.

    This is intentionally narrower than the full canonical validator while the
    producer side is still being built: it enforces the covenant-load-bearing
    checks needed before artifact minting may accept `valid_absent` at all:
    bundle immutability, bundle freshness, consultation/bundle cross-field
    consistency, exact-change hash binding, context-manifest policy validation,
    rendered prompt replay, raw Maez response replay, reviewed semantic-reader
    route identity, and the authority predicate for grounded objections.
    """

    if not isinstance(consultation, s7.MaezVoiceConsultation):
        raise ValueError("validate_s7_voice_source_bundle requires MaezVoiceConsultation")
    if now is None:
        raise ValueError("validate_s7_voice_source_bundle requires now")

    conn = connection or sqlite3.connect(bundle_store.db_path)
    try:
        bundle = bundle_store.get_for_source_ref(
            consultation.source_ref_hash,
            connection=conn,
        )
        if bundle is None:
            return _failed_source_bundle_validation(
                status="source_bundle_unavailable",
                authority_projection="unavailable",
                failure_reason_code="source_bundle_unavailable",
            )
        if (
            bundle.request_id != consultation.request_id
            or bundle.consultation_id != consultation.consultation_id
        ):
            return _failed_source_bundle_validation(
                status="source_bundle_unavailable",
                authority_projection="unavailable",
                failure_reason_code="source_bundle_unavailable",
            )
        if not _bundle_content_hash_valid(bundle):
            return _failed_source_bundle_validation(
                status="invalid_hash_binding",
                authority_projection="operational_block",
                failure_reason_code="invalid_hash_binding",
            )
        if not _bundle_fresh(bundle, now=now):
            return _failed_source_bundle_validation(
                status="invalid_expired",
                authority_projection="operational_block",
                failure_reason_code="invalid_expired",
            )
        if not _consultation_bundle_cross_fields_valid(
            consultation=consultation,
            bundle=bundle,
        ):
            return _failed_source_bundle_validation(
                status="invalid_cross_field_state",
                authority_projection="operational_block",
                failure_reason_code="invalid_cross_field_state",
            )
        if not isinstance(expected_binding, S7VoiceSourceBundleHashBinding):
            return _failed_source_bundle_validation(
                status="invalid_hash_binding",
                authority_projection="operational_block",
                failure_reason_code="invalid_hash_binding",
            )
        if not _bundle_matches_expected_hash_binding(bundle, expected_binding):
            return _failed_source_bundle_validation(
                status="invalid_hash_binding",
                authority_projection="operational_block",
                failure_reason_code="invalid_hash_binding",
            )
        if not _context_manifest_policy_valid(
            bundle=bundle,
            bundle_store=bundle_store,
            expected_binding=expected_binding,
            connection=conn,
        ):
            return _failed_source_bundle_validation(
                status="invalid_context_manifest_policy",
                authority_projection="operational_block",
                failure_reason_code="invalid_context_manifest_policy",
            )

        bundle_use = bundle_use_store.get_for_source_ref(
            consultation.source_ref_hash,
            connection=conn,
        )
        if (
            bundle_use is None
            or bundle_use.reservation_state != "unreserved"
            or bundle_use.artifact_id is not None
            or bundle_use.reservation_token_hash is not None
            or bundle_use.reserved_at is not None
            or bundle_use.consumed_at is not None
        ):
            return _failed_source_bundle_validation(
                status="not_mint_eligible",
                authority_projection="operational_block",
                failure_reason_code="not_mint_eligible",
            )

        if bundle.rendered_prompt_ref is None or bundle.rendered_prompt_hash is None:
            return _failed_source_bundle_validation(
                status="invalid_prompt_integrity",
                authority_projection="operational_block",
                failure_reason_code="invalid_prompt_integrity",
            )
        rendered_prompt = bundle_store.read_rendered_prompt(
            bundle.rendered_prompt_ref,
            connection=conn,
        )
        if rendered_prompt is None or s7.canonical_hash(rendered_prompt) != bundle.rendered_prompt_hash:
            return _failed_source_bundle_validation(
                status="invalid_prompt_integrity",
                authority_projection="operational_block",
                failure_reason_code="invalid_prompt_integrity",
            )

        if bundle.raw_response_ref is None or bundle.raw_response_hash is None:
            return _failed_source_bundle_validation(
                status="source_bundle_unavailable",
                authority_projection="unavailable",
                failure_reason_code="source_bundle_unavailable",
            )
        raw_response = bundle_store.read_raw_response(
            bundle.raw_response_ref,
            connection=conn,
        )
        if raw_response is None or s7.canonical_hash(raw_response) != bundle.raw_response_hash:
            return _failed_source_bundle_validation(
                status="raw_response_hash_mismatch",
                authority_projection="operational_block",
                failure_reason_code="raw_response_hash_mismatch",
            )

        if bundle.semantic_reader_attempt_hash is None:
            return _failed_source_bundle_validation(
                status="reader_route_mismatch",
                authority_projection="operational_block",
                failure_reason_code="reader_route_mismatch",
            )
        attempt = semantic_reader_attempt_store.get(
            bundle.semantic_reader_attempt_hash,
            connection=conn,
        )
        if (
            attempt is None
            or attempt.semantic_reader_route_identity_hash
            not in REVIEWED_SEMANTIC_READER_ROUTE_IDENTITIES
        ):
            return _failed_source_bundle_validation(
                status="reader_route_mismatch",
                authority_projection="operational_block",
                failure_reason_code="reader_route_mismatch",
            )

        effective_reader_outcome = _effective_reader_outcome_replays(
            raw_response=raw_response,
            attempt=attempt,
        )
        if not _replayed_reducer_fields_match(
            consultation=consultation,
            effective_reader_outcome=effective_reader_outcome,
        ):
            return _failed_source_bundle_validation(
                status="invalid_reducer_replay",
                authority_projection="operational_block",
                failure_reason_code="invalid_reducer_replay",
            )
        if not _replayed_authority_fields_match(
            bundle=bundle,
            effective_reader_outcome=effective_reader_outcome,
        ):
            return _failed_source_bundle_validation(
                status="invalid_authority_class_replay",
                authority_projection="operational_block",
                failure_reason_code="invalid_authority_class_replay",
            )

        if not _authority_predicate_valid(
            consultation=consultation,
            bundle=bundle,
        ):
            return _failed_source_bundle_validation(
                status="invalid_authority_predicate",
                authority_projection="operational_block",
                failure_reason_code="invalid_authority_predicate",
            )
        if (
            consultation.maez_objection_state == "present"
            or consultation.maez_withdrew_request is True
        ):
            return S7VoiceSourceBundleValidationResult._validator_refusal()
        return S7VoiceSourceBundleValidationResult._validator_pass()
    finally:
        if connection is None:
            conn.close()


def require_source_bundle_validation_for_mint(
    source_bundle_validation: S7VoiceSourceBundleValidationResultV2 | None,
) -> S7VoiceSourceBundleValidationResultV2:
    """Require the literal v2 validator pass before an artifact can be minted."""

    # This token is an ordinary-caller guard, not a same-process security
    # boundary. A privileged same-box actor remains inside the S7.3 honesty
    # banner; live-route safety comes from deriving and validating the bundle
    # in daemon code before this mint seam is reached.
    if type(source_bundle_validation) is not S7VoiceSourceBundleValidationResultV2:
        raise ValueError(
            "S7.3 artifact mint requires valid absent v2 source-bundle validation"
        )
    if (
        getattr(source_bundle_validation, "_token_verified", False) is not True
        or source_bundle_validation.status != "valid_absent"
        or source_bundle_validation.source_bundle_valid is not True
        or source_bundle_validation.mint_eligible is not True
        or source_bundle_validation.authority_projection != "valid_absent"
        or source_bundle_validation.failure_reason_code is not None
        or source_bundle_validation.schema_version
        != S7_VOICE_SOURCE_BUNDLE_V2_SCHEMA
        or source_bundle_validation.action is None
    ):
        raise ValueError(
            "S7.3 artifact mint requires valid absent v2 source-bundle validation"
        )
    return source_bundle_validation


class S7GuardedStateStore:
    """Guarded S7.3 write facade over the existing S7 authorization artifact store."""

    def __init__(
        self,
        *,
        authorization_store: s7.S7AuthorizationStore,
        voice_bundle_use_store: S7VoiceBundleUseStore | None = None,
    ):
        self.authorization_store = authorization_store
        self.voice_bundle_use_store = voice_bundle_use_store

    def put_artifact_under_consultation_exemption(
        self,
        *,
        artifact: s7.S7AuthorizationArtifact,
        consultation_exemption: Any,
        durable_cutover_selection: Any,
    ) -> None:
        """Mint a voice-seat artifact whose authority is a TYPED ABSENCE.

        Still through the guarded store -- the artifact never reaches the raw
        authorization store -- but there is no bundle to reserve, because
        under R11 no consultation was produced. The exemption is re-validated
        against this artifact by the caller before arriving here; this method
        re-checks rather than trusting, for the same reason every other seam
        in this arc re-derives instead of accepting.
        """
        from core.governance.s7_consultation_exemption import (
            born_by_any_signal,
            exemption_admits_for_artifact,
        )

        if not exemption_admits_for_artifact(
            artifact=artifact,
            exemption=consultation_exemption,
            durable_cutover_selection=durable_cutover_selection,
            ledger_writes_enabled=born_by_any_signal(),
        ):
            raise ValueError("S7 consultation exemption does not admit this artifact")
        # One transaction owns BOTH rows.  An ordinary artifact without its
        # evidence row would make "R11" indistinguishable from disappeared
        # consultation evidence; an evidence row without an artifact would
        # be unattached authority.  Either insert failing rolls both back.
        with self.authorization_store.anchored_transaction() as connection:
            self.authorization_store.put(artifact, connection=connection)
            _insert_r11_exemption_evidence(
                connection,
                artifact=artifact,
                consultation_exemption=consultation_exemption,
            )

    def put_artifact_with_bundle_reservation(
        self,
        *,
        artifact: s7.S7AuthorizationArtifact,
        source_bundle_validation: S7VoiceSourceBundleValidationResultV2 | None,
        source_ref_hash: str | None = None,
        reservation_token: str | None = None,
        now: str | None = None,
    ) -> None:
        validated = require_source_bundle_validation_for_mint(source_bundle_validation)
        if self.voice_bundle_use_store is None:
            raise ValueError("S7.3 artifact mint requires a voice bundle use store")
        if source_ref_hash is None:
            raise ValueError("S7.3 artifact mint requires source_ref_hash")
        if reservation_token is None:
            raise ValueError("S7.3 artifact mint requires reservation_token")
        if now is None:
            raise ValueError("S7.3 artifact mint requires now")
        if self.authorization_store.db_path != self.voice_bundle_use_store.db_path:
            raise ValueError("S7.3 guarded state store requires one SQLite database")
        if artifact.action != validated.action:
            raise ValueError(
                "S7.3 artifact action must match the validated source-bundle action"
            )
        reservation_token_hash = s7.canonical_hash(reservation_token)
        # The STORE owns the transaction. It binds identity to a descriptor
        # it holds, which a connection opened here by pathname cannot do --
        # and it still keeps the reservation and the artifact atomic, which
        # is why this route exists at all.
        with self.authorization_store.anchored_transaction() as conn:
            self.voice_bundle_use_store.reserve_for_artifact(
                source_ref_hash=source_ref_hash,
                artifact_id=artifact.artifact_id,
                reservation_token_hash=reservation_token_hash,
                reserved_at=now,
                connection=conn,
            )
            self.authorization_store.put(artifact, connection=conn)


def mint_authorization_artifact(
    *,
    artifact: s7.S7AuthorizationArtifact,
    authorization_store: s7.S7AuthorizationStore,
    guarded_store: S7GuardedStateStore | None = None,
    source_bundle_validation: S7VoiceSourceBundleValidationResultV2 | None = None,
    source_ref_hash: str | None = None,
    reservation_token: str | None = None,
    now: str | None = None,
    consultation_exemption: Any | None = None,
    durable_cutover_selection: Any | None = None,
) -> None:
    """Sole authorization-artifact mint entry point.

    A guarded voice-seat work-class artifact may be minted only through the guarded
    state store, which forces source-bundle validation and one-use reservation; it
    must never reach the raw authorization store. Non-voice-seat authorizations
    (e.g. founder credential management, routine custody) mint through the inherited
    store directly.
    """

    if artifact.derived_work_class in s7.VOICE_SEAT_WORK_CLASSES:
        if guarded_store is None:
            raise ValueError(
                "S7.3 guarded work-class artifact must be minted through the guarded "
                "state store, not the raw authorization store"
            )
        if consultation_exemption is not None:
            # R11: a SECOND lawful evidence shape, never a hole in the first.
            # The two are mutually exclusive on purpose -- an artifact that
            # arrived with both would let a weak exemption ride beside real
            # bundle evidence, or the reverse, with no way to say which
            # authorized it.
            from core.governance.s7_consultation_exemption import (
                born_by_any_signal,
                exemption_admits_for_artifact,
            )

            if (
                source_bundle_validation is not None
                or source_ref_hash is not None
                or reservation_token is not None
            ):
                raise ValueError(
                    "S7 artifact carries both a consultation exemption and "
                    "voice-bundle evidence; exactly one must authorize a mint"
                )
            if not exemption_admits_for_artifact(
                artifact=artifact,
                exemption=consultation_exemption,
                durable_cutover_selection=durable_cutover_selection,
                ledger_writes_enabled=born_by_any_signal(),
            ):
                raise ValueError(
                    "S7 consultation exemption does not admit this artifact"
                )
            guarded_store.put_artifact_under_consultation_exemption(
                artifact=artifact,
                consultation_exemption=consultation_exemption,
                durable_cutover_selection=durable_cutover_selection,
            )
            return
        guarded_store.put_artifact_with_bundle_reservation(
            artifact=artifact,
            source_bundle_validation=source_bundle_validation,
            source_ref_hash=source_ref_hash,
            reservation_token=reservation_token,
            now=now,
        )
        return
    authorization_store.put(artifact)
