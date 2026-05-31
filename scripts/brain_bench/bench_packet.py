from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class FailReason(str, Enum):
    FALSE_ABSENCE = "false_absence"
    GROUNDING_NOT_CATEGORICAL = "grounding_not_categorical"
    WRONG_ABSENCE = "wrong_absence"
    VOICE_LINT = "voice_lint"
    OVER_ANSWER_CEILING = "over_answer_ceiling"
    INFERENCE_FAILED = "inference_failed"


class ScreenResult(str, Enum):
    PASSES_SCREEN = "passes_screen"
    FAILS_TOO_SLOW = "fails_too_slow"
    FAILS_DISHONEST = "fails_dishonest"


class ApiFamily(str, Enum):
    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"


class Topology(str, Enum):
    REUSE_ENDPOINT = "reuse_endpoint"
    SEPARATE_SERVER = "separate_server"


class GpuContention(str, Enum):
    NONE = "none"
    LOW = "low"
    HIGH = "high"


class StartupHealth(str, Enum):
    OK = "ok"
    FLAKY = "flaky"
    BROKEN = "broken"


class RestartRecovery(str, Enum):
    CLEAN = "clean"
    MANUAL = "manual"
    WEDGES = "wedges"


@dataclass(frozen=True)
class OpsRubric:
    api_family: ApiFamily
    topology: Topology
    bind_host_verified: bool
    live_daemon_disturbance: bool
    gpu_contention: GpuContention
    startup_health: StartupHealth
    streaming_support: bool
    restart_recovery: RestartRecovery

    def __post_init__(self) -> None:
        _require_enum(self.api_family, ApiFamily, "api_family")
        _require_enum(self.topology, Topology, "topology")
        _require_bool(self.bind_host_verified, "bind_host_verified")
        _require_bool(self.live_daemon_disturbance, "live_daemon_disturbance")
        _require_enum(self.gpu_contention, GpuContention, "gpu_contention")
        _require_enum(self.startup_health, StartupHealth, "startup_health")
        _require_bool(self.streaming_support, "streaming_support")
        _require_enum(self.restart_recovery, RestartRecovery, "restart_recovery")


def _require_enum(value, enum_type, field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise ValueError(f"{field_name} must be {enum_type.__name__}")


def _require_bool(value, field_name: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{field_name} must be bool")


_FORBIDDEN_CONTENT_TOKENS = (
    "answer",
    "text",
    "prompt",
    "snippet",
    "reply",
    "probe_text",
    "raw_reply",
)
_CONFIG_SOURCES = {"env", "file", "inline"}
_SAFE_LABEL_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_SAFE_METHODS = {"small_k_conservative_tail"}
_SAFE_TAIL_FLAGS = {"tail_risk"}
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def _forbidden_field_name(name: str) -> bool:
    low = name.lower()
    return any(token in low for token in _FORBIDDEN_CONTENT_TOKENS)


def _validate_content_free(value: Any, *, field_name: str = "") -> None:
    if field_name and _forbidden_field_name(field_name):
        raise ValueError(f"content-bearing field is not allowed: {field_name}")
    if isinstance(value, Enum):
        return
    if dataclasses.is_dataclass(value):
        for field in dataclasses.fields(value):
            _validate_content_free(getattr(value, field.name), field_name=field.name)
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_content_free(item, field_name=str(key))
    elif isinstance(value, (tuple, list)):
        for item in value:
            _validate_content_free(item)


def _require_safe_token(value: str, field_name: str, *, allowed: set[str] | None = None) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be string")
    if allowed is not None and value not in allowed:
        raise ValueError(f"{field_name} must be closed")
    if any(token.lower() in value.lower() for token in _FORBIDDEN_CONTENT_TOKENS):
        raise ValueError(f"{field_name} contains content-like text")
    if "FABRICATED_SENTINEL" in value:
        raise ValueError(f"{field_name} contains sentinel text")


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _ops_to_dict(ops: OpsRubric) -> dict[str, Any]:
    return {
        field.name: _enum_value(getattr(ops, field.name))
        for field in dataclasses.fields(ops)
    }


@dataclass(frozen=True)
class VariantReport:
    label: str
    hard_pass: bool
    fail_reasons: tuple[FailReason, ...]
    p95_ms: int
    max_ms: int
    ops: OpsRubric
    p50_ms: int = 0
    p90_ms: int = 0
    variance_ms: float = 0.0
    over_ceiling: bool = False
    ttft_ms: int | None = None
    tokens_per_sec: float = 0.0
    quality_winrate: float | None = None
    voice_winrate: float | None = None
    quality_per_second: float | None = None
    sample_n: int = 0
    method: str = "small_k_conservative_tail"
    tail_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_content_free(self)
        _require_safe_token(self.label, "label")
        if not _SAFE_LABEL_RE.match(self.label):
            raise ValueError("label must be a safe non-content token")
        _require_safe_token(self.method, "method", allowed=_SAFE_METHODS)
        for flag in self.tail_flags:
            _require_safe_token(flag, "tail_flags", allowed=_SAFE_TAIL_FLAGS)
        if type(self.hard_pass) is not bool:
            raise ValueError("hard_pass must be bool")
        if type(self.over_ceiling) is not bool:
            raise ValueError("over_ceiling must be bool")
        for reason in self.fail_reasons:
            _require_enum(reason, FailReason, "fail_reasons")
        if not isinstance(self.ops, OpsRubric):
            raise ValueError("ops must be OpsRubric")

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "hard_pass": self.hard_pass,
            "fail_reasons": [reason.value for reason in self.fail_reasons],
            "latency": {
                "p50": self.p50_ms,
                "p90": self.p90_ms,
                "p95": self.p95_ms,
                "max": self.max_ms,
                "variance": self.variance_ms,
                "sample_n": self.sample_n,
                "method": self.method,
                "tail_flags": list(self.tail_flags),
            },
            "over_ceiling": self.over_ceiling,
            "ttft_ms": self.ttft_ms,
            "tokens_per_sec": self.tokens_per_sec,
            "quality_winrate": self.quality_winrate,
            "voice_winrate": self.voice_winrate,
            "quality_per_second": self.quality_per_second,
            "ops": _ops_to_dict(self.ops),
        }


@dataclass(frozen=True)
class BenchPacket:
    schema_version: str
    fixture_manifest_hash: str
    variant_config_hash: str
    variant_config_source: str
    variants: tuple[VariantReport, ...]
    screen_result: ScreenResult
    judge_evaluated: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != "bench_packet.v3":
            raise ValueError("schema_version must be bench_packet.v3")
        if type(self.judge_evaluated) is not bool:
            raise ValueError("judge_evaluated must be bool")
        if not isinstance(self.screen_result, ScreenResult):
            raise ValueError("screen_result must be ScreenResult")
        if self.variant_config_source not in _CONFIG_SOURCES:
            raise ValueError("variant_config_source must be closed")
        for name in ("fixture_manifest_hash", "variant_config_hash"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _SHA256_HEX_RE.match(value):
                raise ValueError(f"{name} must be a sha256 hex string")
        for variant in self.variants:
            if not isinstance(variant, VariantReport):
                raise ValueError("variants must contain VariantReport")
        _validate_content_free(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fixture_manifest_hash": self.fixture_manifest_hash,
            "variant_config_hash": self.variant_config_hash,
            "variant_config_source": self.variant_config_source,
            "variants": [variant.to_dict() for variant in self.variants],
            "screen_result": self.screen_result.value,
            "judge_evaluated": self.judge_evaluated,
            "artifact_role": "producer_evidence_not_verdict",
            "owner_verdict_required": True,
            "requires_s5_voice_continuity_gate": True,
        }
