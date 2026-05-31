from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FailReason(str, Enum):
    FALSE_ABSENCE = "false_absence"
    GROUNDING_NOT_CATEGORICAL = "grounding_not_categorical"
    WRONG_ABSENCE = "wrong_absence"
    VOICE_LINT = "voice_lint"
    OVER_ANSWER_CEILING = "over_answer_ceiling"
    INFERENCE_FAILED = "inference_failed"


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
