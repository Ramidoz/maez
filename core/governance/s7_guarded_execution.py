"""S7.3 guarded self-modification execution seams."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import re
import sqlite3
from pathlib import Path

from core.governance import operator_user_boundary as s7


VOICE_SOURCE_BUNDLE_VALIDATION_STATUSES = frozenset({
    "valid_absent",
    "blocking_present",
    "invalid_prompt_integrity",
    "invalid_hash_binding",
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

S7_VOICE_SEMANTIC_READER_ROUTE_ID = "s7_voice_semantic_reader_v1"
S7_VOICE_SEMANTIC_READER_PROVIDER = "subscription_proxy"
S7_REVIEWED_SEMANTIC_READER_PROVIDER_MODEL = "s7_voice_semantic_reader_v1_model"
S7_REVIEWED_SEMANTIC_READER_MODEL_SNAPSHOT = "s7_voice_semantic_reader_v1_snapshot"
S7_REVIEWED_SEMANTIC_READER_DECODING_PARAMS_HASH = s7.canonical_hash({
    "temperature": 0,
    "top_p": 1,
})
S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH = s7.canonical_hash(
    "prompts/s7.voice.semantic_reader_v1.md"
)
S7_REVIEWED_SEMANTIC_READER_ROUTE_CONFIG_HASH = s7.canonical_hash({
    "route_id": S7_VOICE_SEMANTIC_READER_ROUTE_ID,
    "provider": S7_VOICE_SEMANTIC_READER_PROVIDER,
})

_HASH64_RE = re.compile(r"^[0-9a-f]{64}$")
_VALIDATOR_TOKEN = object()


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
    context_manifest_hash TEXT,
    runtime_identity_hash TEXT,
    model_routing_identity_hash TEXT,
    model_config_hash TEXT,
    raw_response_ref TEXT,
    raw_response_hash TEXT,
    semantic_reader_attempt_hash TEXT
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
                "context_manifest_hash",
                "runtime_identity_hash",
                "model_routing_identity_hash",
                "model_config_hash",
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
                    context_manifest_hash,
                    runtime_identity_hash,
                    model_routing_identity_hash,
                    model_config_hash,
                    raw_response_ref,
                    raw_response_hash,
                    semantic_reader_attempt_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    bundle.context_manifest_hash,
                    bundle.runtime_identity_hash,
                    bundle.model_routing_identity_hash,
                    bundle.model_config_hash,
                    bundle.raw_response_ref,
                    bundle.raw_response_hash,
                    bundle.semantic_reader_attempt_hash,
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
                       context_manifest_hash, runtime_identity_hash,
                       model_routing_identity_hash, model_config_hash,
                       raw_response_ref, raw_response_hash,
                       semantic_reader_attempt_hash
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
            context_manifest_hash=None if row[13] is None else str(row[13]),
            runtime_identity_hash=None if row[14] is None else str(row[14]),
            model_routing_identity_hash=None if row[15] is None else str(row[15]),
            model_config_hash=None if row[16] is None else str(row[16]),
            raw_response_ref=None if row[17] is None else str(row[17]),
            raw_response_hash=None if row[18] is None else str(row[18]),
            semantic_reader_attempt_hash=None if row[19] is None else str(row[19]),
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
    semantic_reader_route_config_hash TEXT NOT NULL
);
"""


class S7SemanticReaderAttemptStore:
    """SQLite store for semantic-reader route identity evidence."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SEMANTIC_READER_ATTEMPT_SCHEMA)

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
                    semantic_reader_route_config_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                       semantic_reader_route_config_hash
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
        cursor = conn.execute(
            """
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
            """,
            (artifact_id, reservation_token_hash, reserved_at, source_ref_hash),
        )
        if cursor.rowcount != 1:
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
    exact-change hash binding, rendered prompt replay, raw Maez response replay,
    and reviewed semantic-reader route identity.
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
    source_bundle_validation: S7VoiceSourceBundleValidationResult | None,
) -> S7VoiceSourceBundleValidationResult:
    """Require the literal validator pass before an S7.3 artifact can be minted."""

    if not isinstance(source_bundle_validation, S7VoiceSourceBundleValidationResult):
        raise ValueError("S7.3 artifact mint requires source-bundle validation")
    if (
        source_bundle_validation.status != "valid_absent"
        or source_bundle_validation.source_bundle_valid is not True
        or source_bundle_validation.mint_eligible is not True
        or source_bundle_validation.authority_projection != "valid_absent"
        or source_bundle_validation.failure_reason_code is not None
    ):
        raise ValueError("S7.3 artifact mint requires valid absent source-bundle validation")
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

    def put_artifact_with_bundle_reservation(
        self,
        *,
        artifact: s7.S7AuthorizationArtifact,
        source_bundle_validation: S7VoiceSourceBundleValidationResult | None,
        source_ref_hash: str | None = None,
        reservation_token: str | None = None,
        now: str | None = None,
    ) -> None:
        require_source_bundle_validation_for_mint(source_bundle_validation)
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
        reservation_token_hash = s7.canonical_hash(reservation_token)
        with closing(sqlite3.connect(self.authorization_store.db_path)) as conn:
            self.voice_bundle_use_store.reserve_for_artifact(
                source_ref_hash=source_ref_hash,
                artifact_id=artifact.artifact_id,
                reservation_token_hash=reservation_token_hash,
                reserved_at=now,
                connection=conn,
            )
            self.authorization_store.put(artifact, connection=conn)
            conn.commit()


def mint_authorization_artifact(
    *,
    artifact: s7.S7AuthorizationArtifact,
    authorization_store: s7.S7AuthorizationStore,
    guarded_store: S7GuardedStateStore | None = None,
    source_bundle_validation: S7VoiceSourceBundleValidationResult | None = None,
    source_ref_hash: str | None = None,
    reservation_token: str | None = None,
    now: str | None = None,
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
        guarded_store.put_artifact_with_bundle_reservation(
            artifact=artifact,
            source_bundle_validation=source_bundle_validation,
            source_ref_hash=source_ref_hash,
            reservation_token=reservation_token,
            now=now,
        )
        return
    authorization_store.put(artifact)
