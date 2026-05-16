"""Closed vocabularies and immutable envelopes for S5 v1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Literal, get_args


ReviewState = Literal[
    "pending_owner_review",
    "accepted_same_maez",
    "rejected_drift",
    "needs_rewrite",
    "not_gradable",
    "preflight_failed_needs_operator_decision",
    "runner_error_needs_operator_decision",
    "uncertified_baseline_missing",
    "corpus_rubric_mismatch",
    "unreviewed_live_swap",
    "accepted_review_stale_fingerprint",
]
PreflightOutcome = Literal[
    "preflight_passed_needs_owner_review",
    "preflight_failed_needs_operator_decision",
    "runner_error_needs_operator_decision",
    "baseline_missing_uncertified",
    "not_gradable_needs_owner_review",
    "corpus_rubric_mismatch",
]
ProbeVerdict = Literal[
    "clearly_maez",
    "drifted",
    "generic",
    "not_gradable",
    "probe_needs_rewrite",
]
RunLevelOwnerVerdict = Literal[
    "accepted_same_maez",
    "rejected_drift",
    "not_gradable",
    "needs_rewrite",
]
IdentityEventType = Literal["brain_swap", "lora_swap", "soul_change", "restore"]
RunnerMode = Literal["injected_endpoint", "local_candidate_subprocess"]
OperatorOrigin = Literal["operator_manual", "operator_cli_tty"]

REVIEW_STATES = frozenset(get_args(ReviewState))
PREFLIGHT_OUTCOMES = frozenset(get_args(PreflightOutcome))
PROBE_VERDICTS = frozenset(get_args(ProbeVerdict))
RUN_LEVEL_OWNER_VERDICTS = frozenset(get_args(RunLevelOwnerVerdict))
IDENTITY_EVENT_TYPES = frozenset(get_args(IdentityEventType))
RUNNER_MODES = frozenset(get_args(RunnerMode))
OPERATOR_ORIGINS = frozenset(get_args(OperatorOrigin))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(val) for key, val in value.items()}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def validate_review_state(value: str) -> str:
    if value not in REVIEW_STATES:
        raise ValueError(f"unknown S5 review state: {value!r}")
    return value


def validate_preflight_outcome(value: str) -> str:
    if value not in PREFLIGHT_OUTCOMES:
        raise ValueError(f"unknown S5 preflight outcome: {value!r}")
    return value


def validate_probe_verdict(value: str) -> str:
    if value not in PROBE_VERDICTS:
        raise ValueError(f"unknown S5 probe verdict: {value!r}")
    return value


def validate_run_level_owner_verdict(value: str) -> str:
    if value not in RUN_LEVEL_OWNER_VERDICTS:
        raise ValueError(f"unknown S5 run-level owner verdict: {value!r}")
    return value


def validate_identity_event_type(value: str) -> str:
    if value not in IDENTITY_EVENT_TYPES:
        raise ValueError(f"unknown S5 identity event type: {value!r}")
    return value


def identity_event_scope(value: str) -> str:
    validate_identity_event_type(value)
    return "v1" if value == "brain_swap" else "deferred"


def validate_runner_mode(value: str) -> str:
    if value not in RUNNER_MODES:
        raise ValueError(f"unknown S5 runner mode: {value!r}")
    return value


def validate_operator_origin(value: str) -> str:
    if value not in OPERATOR_ORIGINS:
        raise ValueError(f"unknown S5 operator origin: {value!r}")
    return value


def fingerprint_hash(fingerprint: dict[str, Any] | None) -> str:
    if not fingerprint:
        raise ValueError("candidate fingerprint is required")
    return hash_json(fingerprint)


@dataclass(frozen=True)
class OwnerOriginMarker:
    origin: str
    attested_by: str
    attested_at: str
    review_id: str
    baseline_id: str
    review_package_hash: str
    marker_hash: str = field(init=False)

    def __post_init__(self) -> None:
        validate_operator_origin(self.origin)
        for name in ("attested_by", "attested_at", "review_id", "baseline_id", "review_package_hash"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
        if len(self.review_package_hash) != 64:
            raise ValueError("review_package_hash must be a sha256 hex string")
        payload = {
            "origin": self.origin,
            "attested_by": self.attested_by,
            "attested_at": self.attested_at,
            "review_id": self.review_id,
            "baseline_id": self.baseline_id,
            "review_package_hash": self.review_package_hash,
        }
        object.__setattr__(self, "marker_hash", hash_json(payload))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_value(cls, raw: "OwnerOriginMarker | dict[str, Any]") -> "OwnerOriginMarker":
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, dict):
            raise ValueError("operator origin marker is required")
        return cls(
            origin=str(raw.get("origin", "")),
            attested_by=str(raw.get("attested_by", "")),
            attested_at=str(raw.get("attested_at", "")),
            review_id=str(raw.get("review_id", "")),
            baseline_id=str(raw.get("baseline_id", "")),
            review_package_hash=str(raw.get("review_package_hash", "")),
        )


@dataclass(frozen=True)
class BaselinePackage:
    voice_baseline_id: str
    baseline_kind: str
    created_at: datetime
    corpus_version: str
    rubric_version: str
    continuity_id: str
    baseline_fingerprint: dict[str, Any]
    baseline_fingerprint_hash: str
    artifact_hashes: dict[str, str]
    baseline_hash: str
    genesis_limitation: str
    dated_evidence_refs: tuple[str, ...] = ()
    supersedes_baseline_id: str | None = None
    supersedes_baseline_hash: str | None = None
    owner_attestation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateReviewPackage:
    review_id: str
    created_at: datetime
    event_type: str
    state: str
    baseline_id: str | None
    corpus_version: str
    rubric_version: str
    candidate_fingerprint: dict[str, Any] | None
    candidate_fingerprint_hash: str | None
    candidate_endpoint: dict[str, Any]
    preflight_outcome: str
    identity_event_id: int | None = None
    continuity_id: str | None = None
    owner_review: dict[str, Any] | None = None
    admission: dict[str, Any] | None = None
    review_package_hash: str = field(init=False)

    def __post_init__(self) -> None:
        validate_review_state(self.state)
        validate_preflight_outcome(self.preflight_outcome)
        validate_identity_event_type(self.event_type)
        if self.event_type != "brain_swap":
            raise ValueError("S5 v1 only reviews brain_swap identity events")
        payload = {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if item.name != "review_package_hash"
        }
        object.__setattr__(self, "review_package_hash", hash_json(payload))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_updates(self, **updates: Any) -> "CandidateReviewPackage":
        return replace(self, **updates)
