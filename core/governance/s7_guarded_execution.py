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

_HASH64_RE = re.compile(r"^[0-9a-f]{64}$")


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


@dataclass(frozen=True)
class S7VoiceSourceBundleValidationResult:
    """Result of the S7.3 source-bundle validator that gates artifact minting."""

    status: str
    source_bundle_valid: bool
    mint_eligible: bool
    authority_projection: str
    failure_reason_code: str | None

    def __post_init__(self) -> None:
        if self.status not in VOICE_SOURCE_BUNDLE_VALIDATION_STATUSES:
            raise ValueError(f"unknown S7.3 voice source bundle validation status: {self.status}")
        if self.authority_projection not in VOICE_SOURCE_BUNDLE_AUTHORITY_PROJECTIONS:
            raise ValueError(
                "unknown S7.3 voice source bundle authority projection: "
                f"{self.authority_projection}"
            )
        if self.status == "valid_absent":
            if self.failure_reason_code is not None:
                raise ValueError("valid_absent source-bundle validation must not carry a failure reason")
            if self.source_bundle_valid is not True or self.mint_eligible is not True:
                raise ValueError("valid_absent source-bundle validation must be valid and mint-eligible")
            if self.authority_projection != "valid_absent":
                raise ValueError("valid_absent source-bundle validation must project valid_absent")
        elif self.failure_reason_code is None:
            raise ValueError("failed source-bundle validation must carry a failure reason")


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

    def get_for_source_ref(self, source_ref_hash: str) -> S7VoiceBundleUse | None:
        _validate_hash64(source_ref_hash, field="source_ref_hash")
        with closing(sqlite3.connect(self.db_path)) as conn:
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
    ) -> S7VoiceBundleUse:
        _validate_hash64(source_ref_hash, field="source_ref_hash")
        _validate_hash64(reservation_token_hash, field="reservation_token_hash")
        if not artifact_id:
            raise ValueError("reserve_for_artifact requires artifact_id")
        if not reserved_at:
            raise ValueError("reserve_for_artifact requires reserved_at")

        existing = self.get_for_source_ref(source_ref_hash)
        if existing is None:
            raise ValueError("S7 voice bundle use must exist before reservation")
        if (
            existing.reservation_state != "unreserved"
            or existing.artifact_id is not None
            or existing.reservation_token_hash is not None
            or existing.reserved_at is not None
            or existing.consumed_at is not None
        ):
            raise ValueError("S7 voice bundle use must be unreserved before artifact mint")

        with closing(sqlite3.connect(self.db_path)) as conn:
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
            conn.commit()
        reserved = self.get_for_source_ref(source_ref_hash)
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
        reservation_token_hash = s7.canonical_hash(reservation_token)
        self.voice_bundle_use_store.reserve_for_artifact(
            source_ref_hash=source_ref_hash,
            artifact_id=artifact.artifact_id,
            reservation_token_hash=reservation_token_hash,
            reserved_at=now,
        )
        self.authorization_store.put(artifact)
