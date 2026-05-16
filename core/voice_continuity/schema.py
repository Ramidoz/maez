"""Closed vocabularies and immutable envelopes for S5 v1."""

from __future__ import annotations

from dataclasses import InitVar, asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
import hashlib
import inspect
import json
from typing import Any, Literal, get_args


ReviewState = Literal[
    "pending_owner_review",
    "accepted_same_maez",
    "rejected_drift",
    "closed_reverted",
    "superseded",
    "needs_rewrite",
    "not_gradable",
    "preflight_failed_needs_operator_decision",
    "runner_error_needs_operator_decision",
    "uncertified_baseline_missing",
    "unreviewed_live_swap",
]
PreflightOutcome = Literal[
    "preflight_passed_needs_owner_review",
    "preflight_failed_needs_operator_decision",
    "runner_error_needs_operator_decision",
    "baseline_missing_uncertified",
    "not_gradable_needs_owner_review",
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
_ACCEPTED_STATE_TOKEN = object()
_GENESIS_LIMITATION = "pre_s5_drift_not_detectable"
S5_V1_LIMITATIONS = frozenset(
    {
        "genesis_pre_s5_drift_not_detectable",
        "grandmother_technical_owner_review_deferred",
        "manual_model_env_bypass_detected_not_prevented",
    }
)


def utc_now_iso() -> str:
    return _canonical_utc_iso(datetime.now(timezone.utc))


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


def _canonical_utc(value: str | datetime) -> datetime:
    from core.time.temporal_spine import canonical_utc

    return canonical_utc(value, field_name="observed_at")


def _canonical_utc_iso(value: str | datetime) -> str:
    from core.time.temporal_spine import canonical_utc_iso

    return canonical_utc_iso(value, field_name="observed_at")


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


def validate_owner_marker_binding(
    marker: OwnerOriginMarker,
    *,
    review_id: str,
    baseline_id: str | None,
    review_package_hash: str,
) -> None:
    if marker.review_id != review_id:
        raise ValueError("operator-origin marker review_id does not match review")
    if marker.baseline_id != (baseline_id or ""):
        raise ValueError("operator-origin marker baseline_id does not match review")
    if marker.review_package_hash != review_package_hash:
        raise ValueError("operator-origin marker review_package_hash does not match review")


def fingerprint_hash(fingerprint: dict[str, Any] | None) -> str:
    if not fingerprint:
        raise ValueError("candidate fingerprint is required")
    return hash_json(fingerprint)


def _validate_acceptance_owner_review(
    owner_review: dict[str, Any] | None,
    *,
    review_id: str,
    baseline_id: str | None,
) -> None:
    if not isinstance(owner_review, dict):
        raise ValueError("accepted_same_maez requires owner verdict evidence")
    if owner_review.get("run_level_verdict") != "accepted_same_maez":
        raise ValueError("accepted_same_maez requires accepted owner verdict")
    marker_hash = str(owner_review.get("operator_origin_marker_hash") or "")
    if len(marker_hash) != 64:
        raise ValueError("accepted_same_maez requires operator-origin marker hash")
    validate_operator_origin(str(owner_review.get("origin") or ""))
    if owner_review.get("review_id") != review_id:
        raise ValueError("accepted_same_maez owner evidence review_id mismatch")
    if owner_review.get("baseline_id") != (baseline_id or ""):
        raise ValueError("accepted_same_maez owner evidence baseline_id mismatch")
    review_package_hash = str(owner_review.get("review_package_hash") or "")
    if len(review_package_hash) != 64:
        raise ValueError("accepted_same_maez owner evidence review_package_hash is required")


def _validate_baseline_owner_attestation(owner_attestation: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(owner_attestation, dict):
        raise ValueError("baseline owner_attestation is required")
    verdict = str(owner_attestation.get("verdict") or "")
    if verdict != "baseline_accepted":
        raise ValueError("baseline owner_attestation requires baseline_accepted verdict")
    origin = validate_operator_origin(str(owner_attestation.get("origin") or ""))
    attested_by = str(owner_attestation.get("attested_by") or "")
    attested_at = str(owner_attestation.get("attested_at") or "")
    if not attested_by:
        raise ValueError("baseline owner_attestation attested_by is required")
    if not attested_at:
        raise ValueError("baseline owner_attestation attested_at is required")
    sealed = dict(owner_attestation)
    sealed["origin"] = origin
    sealed["attested_at"] = _canonical_utc_iso(attested_at)
    return sealed


def _called_from_apply_owner_verdict() -> bool:
    for frame in inspect.stack()[2:8]:
        if (
            frame.function == "apply_owner_verdict"
            and frame.frame.f_globals.get("__name__") == "core.voice_continuity.review"
        ):
            return True
    return False


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
        object.__setattr__(self, "attested_at", _canonical_utc_iso(self.attested_at))
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

    def __post_init__(self) -> None:
        if not self.voice_baseline_id:
            raise ValueError("voice_baseline_id is required")
        if self.baseline_kind not in {"genesis", "ordinary"}:
            raise ValueError("baseline_kind must be genesis or ordinary")
        object.__setattr__(self, "created_at", _canonical_utc(self.created_at))
        evidence_refs = tuple(str(item) for item in self.dated_evidence_refs)
        object.__setattr__(self, "dated_evidence_refs", evidence_refs)
        if self.baseline_kind == "genesis" and not evidence_refs and self.genesis_limitation != _GENESIS_LIMITATION:
            raise ValueError("evidence-less genesis baseline must name pre-S5 drift limitation")
        if self.baseline_kind == "ordinary":
            if not self.supersedes_baseline_id or not self.supersedes_baseline_hash:
                raise ValueError("ordinary rebaseline requires supersedes id and hash")
            if len(str(self.supersedes_baseline_hash)) != 64:
                raise ValueError("supersedes hash must be sha256")
        object.__setattr__(
            self,
            "owner_attestation",
            _validate_baseline_owner_attestation(self.owner_attestation),
        )

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
    _accepted_state_token: InitVar[object | None] = None

    def __post_init__(self, _accepted_state_token: object | None) -> None:
        validate_review_state(self.state)
        validate_preflight_outcome(self.preflight_outcome)
        validate_identity_event_type(self.event_type)
        if self.event_type != "brain_swap":
            raise ValueError("S5 v1 only reviews brain_swap identity events")
        object.__setattr__(self, "created_at", _canonical_utc(self.created_at))
        if self.state == "accepted_same_maez":
            if _accepted_state_token is not _ACCEPTED_STATE_TOKEN or not _called_from_apply_owner_verdict():
                raise ValueError("accepted_same_maez must be produced by apply_owner_verdict")
            _validate_acceptance_owner_review(
                self.owner_review,
                review_id=self.review_id,
                baseline_id=self.baseline_id,
            )
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
