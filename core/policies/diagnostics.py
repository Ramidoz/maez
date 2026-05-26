from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from core import paths


DIAGNOSTIC_SCHEMA_VERSION = "drive-driven-curiosity-diagnostic-v1"


class CuriosityDiagnosticEventType(Enum):
    OBJECT_CREATED = "object_created"
    OBJECT_DECAYED = "object_decayed"
    OBJECT_RESOLVED = "object_resolved"
    OBJECT_FIXATION_RELEASED = "object_fixation_released"
    OBJECT_RELEASED_AS_LET_GO = "object_released_as_let_go"
    LANE_DECISION = "lane_decision"
    SIGNAL_GATE_DECISION = "signal_gate_decision"
    REFLECTION_AUDIT = "reflection_audit"
    EXTRACTION_GATE_BLOCK = "extraction_gate_block"
    TEMPERAMENT_WRITE = "temperament_write"
    TEMPERAMENT_WRITE_CLAMPED = "temperament_write_clamped"
    SATURATION_SAMPLE = "saturation_sample"
    QUERY_SANITIZATION = "query_sanitization"
    PREFERENCE_RECORDED = "preference_recorded"
    SUPPRESSION_EVENT = "suppression_event"
    CROSS_BOND_ACCESS_REFUSED = "cross_bond_access_refused"
    SUBJECT_BOUNDARY_REFUSED = "subject_boundary_refused"
    SUBJECT_KIND_REFUSED = "subject_kind_refused"
    MASTER_KEY_INITIALIZED = "master_key_initialized"
    MASTER_KEY_ROTATION = "master_key_rotation"


_EVENT_ALIASES = {
    event.value.upper(): event
    for event in CuriosityDiagnosticEventType
}

_ROW_KEYS: tuple[str, ...] = (
    "schema_version",
    "event_type",
    "occurred_utc",
    "bond_digest",
    "requested_bond_digest",
    "query_bond_digest",
    "object_id_digest",
    "subject_ref_digest",
    "seed_text_digest",
    "preference_id_digest",
    "matched_pattern_digest",
    "suppression_kind",
    "reason",
    "refusal_kind",
    "surface",
    "decision",
    "signal_quality",
    "owner_state",
    "preference_class",
    "expressed_by",
    "weight",
    "outreach_dispatch_id",
    "audit_id",
    "parameter",
    "proposed_delta",
    "delta_applied",
    "first_observation_suppressed",
    "raw_seed_text",
    "seed_text",
)


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    if not salt:
        salt = b"\x00" * hashlib.sha256().digest_size
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int = 32) -> bytes:
    blocks: list[bytes] = []
    previous = b""
    counter = 1
    while sum(len(block) for block in blocks) < length:
        previous = hmac.new(
            prk,
            previous + info + bytes([counter]),
            hashlib.sha256,
        ).digest()
        blocks.append(previous)
        counter += 1
    return b"".join(blocks)[:length]


def derive_bond_hmac_key(master_key: bytes, bond_id: str) -> bytes:
    info = f"drive-driven-curiosity-bond-hmac:{bond_id}".encode("utf-8")
    prk = _hkdf_extract(salt=b"", ikm=master_key)
    return _hkdf_expand(prk, info, length=32)


def hmac_digest_for_bond(*, master_key: bytes, bond_id: str, value: object) -> str:
    key = derive_bond_hmac_key(master_key, str(bond_id))
    digest = hmac.new(key, str(value).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def ensure_master_key(
    *,
    master_key_path: Path | str | None = None,
    diagnostic_log_path: Path | str | None = None,
) -> bytes:
    key_path = Path(master_key_path) if master_key_path is not None else paths.drive_curiosity_master_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return _read_master_key_when_ready(key_path)

    key = os.urandom(32)
    try:
        fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return _read_master_key_when_ready(key_path)
    with os.fdopen(fd, "wb") as handle:
        handle.write(key)
    try:
        key_path.chmod(0o600)
    except OSError:
        pass

    log_path = (
        Path(diagnostic_log_path)
        if diagnostic_log_path is not None
        else paths.drive_curiosity_diagnostics_log()
    )
    _append_jsonl(
        log_path,
        _uniform_row(
            event_type=CuriosityDiagnosticEventType.MASTER_KEY_INITIALIZED,
            occurred_utc=datetime.now(tz=UTC),
            master_key=None,
            bond_id=None,
            payload={"surface": "drive_curiosity_master_key"},
        ),
    )
    return key


def _read_master_key_when_ready(key_path: Path, *, attempts: int = 100) -> bytes:
    for _ in range(max(1, attempts)):
        try:
            key = key_path.read_bytes()
        except FileNotFoundError:
            key = b""
        if len(key) == 32:
            return key
        time.sleep(0.001)
    raise ValueError("drive curiosity master key must be exactly 32 bytes")


class DriveCuriosityDiagnosticSink:
    accepts_raw_diagnostic_fields = True

    def __init__(
        self,
        *,
        log_path: Path | str | None = None,
        master_key_path: Path | str | None = None,
    ):
        self.log_path = Path(log_path) if log_path is not None else paths.drive_curiosity_diagnostics_log()
        self.master_key_path = (
            Path(master_key_path)
            if master_key_path is not None
            else paths.drive_curiosity_master_key()
        )
        self._lock = threading.RLock()

    def __call__(self, event: Mapping[str, Any]) -> None:
        event_type = event.get("event_type")
        if event_type is None:
            raise ValueError("diagnostic event_type is required")
        payload = dict(event)
        payload.pop("event_type", None)
        bond_id = payload.pop("bond_id", None)
        occurred = payload.pop("occurred_utc", None)
        self.emit(
            event_type=event_type,
            bond_id=None if bond_id is None else str(bond_id),
            occurred_utc=occurred,
            **payload,
        )

    def emit(
        self,
        *,
        event_type: CuriosityDiagnosticEventType | str,
        bond_id: str | None = None,
        occurred_utc: datetime | None = None,
        **payload: Any,
    ) -> None:
        event = _coerce_event_type(event_type)
        occurred = _coerce_utc(occurred_utc or datetime.now(tz=UTC))
        with self._lock:
            master_key = ensure_master_key(
                master_key_path=self.master_key_path,
                diagnostic_log_path=self.log_path,
            )
            row = _uniform_row(
                event_type=event,
                occurred_utc=occurred,
                master_key=master_key,
                bond_id=bond_id,
                payload=payload,
            )
            _append_jsonl(self.log_path, row)


def emit_diagnostic_best_effort(
    diagnostic_sink,
    event: Mapping[str, Any],
    *,
    logger=None,
) -> bool:
    try:
        diagnostic_sink(event)
        return True
    except Exception as exc:
        if logger is not None:
            logger.warning(
                "drive curiosity diagnostic stream write failed: %s",
                exc,
            )
        return False


def _uniform_row(
    *,
    event_type: CuriosityDiagnosticEventType,
    occurred_utc: datetime,
    master_key: bytes | None,
    bond_id: str | None,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    row = {key: None for key in _ROW_KEYS}
    row["schema_version"] = DIAGNOSTIC_SCHEMA_VERSION
    row["event_type"] = event_type.value
    row["occurred_utc"] = _coerce_utc(occurred_utc).isoformat()

    if master_key is not None and bond_id:
        row["bond_digest"] = hmac_digest_for_bond(
            master_key=master_key,
            bond_id=bond_id,
            value=bond_id,
        )

    digest_fields = {
        "object_id": "object_id_digest",
        "subject_ref": "subject_ref_digest",
        "seed_text": "seed_text_digest",
        "raw_seed_text": "seed_text_digest",
        "preference_id": "preference_id_digest",
        "matched_pattern": "matched_pattern_digest",
    }
    if master_key is not None:
        digest_bond = bond_id or str(payload.get("bond_id") or "_diagnostic")
        for source_key, row_key in digest_fields.items():
            value = payload.get(source_key)
            if value not in (None, ""):
                row[row_key] = hmac_digest_for_bond(
                    master_key=master_key,
                    bond_id=digest_bond,
                    value=value,
                )

        for source_key, row_key in (
            ("requested_bond_id", "requested_bond_digest"),
            ("query_bond_id", "query_bond_digest"),
        ):
            value = payload.get(source_key)
            if value not in (None, ""):
                row[row_key] = hmac_digest_for_bond(
                    master_key=master_key,
                    bond_id=str(value),
                    value=value,
                )

    passthrough = {
        "suppression_kind",
        "reason",
        "refusal_kind",
        "surface",
        "decision",
        "signal_quality",
        "owner_state",
        "preference_class",
        "expressed_by",
        "weight",
        "outreach_dispatch_id",
        "audit_id",
        "parameter",
        "proposed_delta",
        "delta_applied",
        "first_observation_suppressed",
    }
    for key in passthrough:
        if key in payload:
            row[key] = payload[key]

    return row


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _coerce_event_type(value: CuriosityDiagnosticEventType | str) -> CuriosityDiagnosticEventType:
    if isinstance(value, CuriosityDiagnosticEventType):
        return value
    raw = str(value)
    try:
        return CuriosityDiagnosticEventType(raw)
    except ValueError:
        alias = _EVENT_ALIASES.get(raw.upper())
        if alias is not None:
            return alias
        raise ValueError(f"unsupported curiosity diagnostic event_type: {raw!r}") from None


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(None):
        raise ValueError("diagnostic timestamp must be timezone-aware UTC")
    return value.astimezone(UTC)
