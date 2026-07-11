"""Pure evidence contracts for the pinned b9596 Vulkan-to-CUDA migration.

This module validates supplied artifacts and aggregate evidence only.  It does
not discover processes, query services, contact model ports, or mutate runtime
state.  Runtime mapping evidence must be supplied explicitly from a future
owner-authorized offline window; static bundle identity never stands in for it.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, Sequence


SCHEMA_VERSION = "cuda_migration_runtime.v1"
FROZEN_TAG = "b9596"
FROZEN_COMMIT = "18ef86ecec723361362a332a79b4d913fd724d40"
FROZEN_VERSION = 9596
FROZEN_ALIAS = "qwen36-27b-mtp"
FROZEN_MODEL_PATH = "/home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf"
FROZEN_MODEL_SHA256 = "4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095"
FROZEN_MODEL_BYTES = 17_909_097_600
FROZEN_CORPUS_SHA256 = "ba126352982e734ff1e2742aaef329cfcc496371fd53c59d0cf21f4c4a487104"
FROZEN_ORDER_SHA256 = "cc9cd81c3110bc37d6c9bfd30bce0267b6cbfc3ffef7fb9abdc8615e42d10575"
FROZEN_SAMPLE_N = 7
FROZEN_WARMUP_COUNT = 3
FROZEN_MEASURED_SAMPLE_COUNT = 21
FROZEN_LOAD_CYCLES = 3
VULKAN_RELEASE_ROOT = Path("/home/rohit/llama.cpp-release/llama-b9596/llama-b9596")
CUDA_RELEASE_ROOT = Path("/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89")
CUDA_TOOLKIT_LIBRARY_ROOT = Path("/usr/local/cuda-13.2/targets/x86_64-linux/lib")
FROZEN_VULKAN_UNIT_SHA256 = "65dfc9e59267b54f4896d88db682538d2fc9ac20d97a80bbd3c6cdfedcadddaa"
FROZEN_VULKAN_DROPIN_SHA256 = "95f630a0b3a7095d9ca0328184d731077d9b8dcca8dc1eadf93094fa8c529f37"
FROZEN_VULKAN_RUNTIME_SHA256 = "55c6ce2efc8feccd25bfab500c5ac70709152be6ff0c5bb2e0f478991519db69"
# Compact sort-key JSON over the 39 top-level *.so* entries. Regular files
# bind relative path, type, SHA-256 and byte count; symlinks bind path/type/target.
FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256 = (
    "c04ba04862db3b558deecbcc2b8f923a1dc7bce830b74592dd9157b784c86dd2"
)
# Compact JSON array of the effective incumbent mtp.conf argv after executable.
FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256 = (
    "8fa9b789572e4d1d63f5d9e008797b14df5fc10b634b0a3858cd68fe008c583b"
)
FROZEN_BACKEND_ENVIRONMENT = MappingProxyType(
    {
        "CUDA_VISIBLE_DEVICES": "0",
        "GGML_VK_VISIBLE_DEVICES": "",
        "LD_LIBRARY_PATH": f"{CUDA_RELEASE_ROOT}:{CUDA_TOOLKIT_LIBRARY_ROOT}",
    }
)

Backend = Literal["cuda", "vulkan"]
Decision = Literal["keep_vulkan", "bench_passed", "provisional_cuda_boot", "promote_cuda"]
EvidenceStatus = Literal["not_attempted", "pass", "fail"]

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_LIBRARY_RE = re.compile(r"lib[A-Za-z0-9_.+-]+\.so(?:\.[0-9]+)*\Z")
_ALLOWED_ROOTS = (
    Path("/home/rohit/maez"),
    Path("/home/rohit/llama.cpp-release"),
    Path("/home/rohit/.config/systemd/user"),
)
_PHASES = frozenset(
    {
        "static_preflight",
        "vulkan_baseline",
        "cuda_candidate",
        "vulkan_rollback",
        "owner_voice_review",
        "owner_authorization",
        "provisional_cuda_boot",
        "provisional_live",
        "cold_boot",
        "final_decision",
    }
)
_DECISIONS = frozenset({"keep_vulkan", "bench_passed", "provisional_cuda_boot", "promote_cuda"})
_REASONS = frozenset(
    {
        "phase_mismatch",
        "alias_changed",
        "model_changed",
        "seven_turn_sample_count",
        "corpus_hash_mismatch",
        "order_hash_mismatch",
        "seven_turn_latency_limit",
        "p95_regression",
        "decode_throughput_regression",
        "bar1_ceiling",
        "bar1_improvement_insufficient",
        "mapping_assertion_delta",
        "xid_delta",
        "crash_detected",
        "restart_detected",
        "hang_detected",
        "timeout_detected",
        "unload_leak_detected",
        "quality_failure",
        "owner_voice_review_missing",
        "mtp_not_initialized",
        "mtp_acceptance_missing",
        "mtp_counter_mismatch",
        "rollback_drill_failed",
        "containment_failed",
        "owner_authorization_failed",
        "cold_boot_witness_pending",
        "cold_boot_witness_failed",
        "provisional_live_witness_pending",
        "provisional_live_witness_failed",
        "live_authorization_failed",
        "evidence_chain_invalid",
        "containment_incomplete",
        "kernel_counter_delta",
        "runtime_identity_mismatch",
        "backend_witness_mismatch",
        "topology_mismatch",
        "unload_incomplete",
        "false_absence",
        "wrong_answered_ungrounded",
        "type_regression",
        "recall_posture_failed",
    }
)
_CONTENT_MARKERS = (
    "prompt",
    "response",
    "transcript",
    "title",
    "pixel",
    '"memory"',
    "/memory/",
    "/home/rohit/",
    '"environment"',
    '"pid"',
)
_ARGV_PREFIX = (
    "-m",
    FROZEN_MODEL_PATH,
    "--alias",
    FROZEN_ALIAS,
    "--host",
    "127.0.0.1",
    "--port",
)
_ARGV_SUFFIX = (
    "--ctx-size",
    "40960",
    "--parallel",
    "1",
    "--n-gpu-layers",
    "999",
    "-fa",
    "on",
    "--cache-type-k",
    "q4_0",
    "--cache-type-v",
    "q4_0",
    "--spec-type",
    "draft-mtp",
    "--spec-draft-n-max",
    "3",
    "--kv-unified",
    "-fit",
    "off",
)
_MODE_ARGS = {
    "bench": _ARGV_PREFIX + ("18080",) + _ARGV_SUFFIX,
    "production": _ARGV_PREFIX + ("8080",) + _ARGV_SUFFIX,
}
_REQUIRED_HELP_TOKENS = (
    "--alias",
    "--ctx-size",
    "--parallel",
    "--n-gpu-layers",
    "-fa",
    "--cache-type-k",
    "--cache-type-v",
    "--spec-type",
    "draft-mtp",
    "--spec-draft-n-max",
    "--kv-unified",
    "-fit",
)


def _validate_sha256(value: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError("invalid_sha256")
    return value


def _validate_nonnegative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid_{name}")


def _validate_nonnegative_number(name: str, value: float | int) -> None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"invalid_{name}")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid_{name}")


def _validate_positive_number(value: float | int) -> None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("positive_measurement")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("positive_measurement")


def _require_bool(name: str, value: bool) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"invalid_{name}")


def validate_asset_path(path: Path) -> Path:
    """Validate an absolute, normalized path beneath one frozen owner root."""

    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("canonical_asset_path")
    if str(path) != os.path.normpath(str(path)):
        raise ValueError("canonical_asset_path")

    resolved = path.resolve(strict=False)
    if not any(resolved == root or resolved.is_relative_to(root) for root in _ALLOWED_ROOTS):
        raise ValueError("canonical_asset_path")
    return path


def hash_file(path: Path) -> str:
    """Hash one canonical regular file without retaining its content."""

    checked = validate_asset_path(path)
    if not checked.is_file():
        raise ValueError("asset_unavailable")
    digest = hashlib.sha256()
    with checked.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_backend_maps(text: str) -> Backend:
    """Return the sole backend named by supplied bundle/map evidence."""

    if not isinstance(text, str):
        raise ValueError("backend_unproven")
    has_cuda = "libggml-cuda.so" in text
    has_vulkan = "libggml-vulkan.so" in text
    if has_cuda == has_vulkan:
        raise ValueError("backend_unproven")
    return "cuda" if has_cuda else "vulkan"


def _validate_effective_args(args: Sequence[str], mode: str) -> None:
    if mode not in _MODE_ARGS or isinstance(args, (str, bytes)):
        raise ValueError("exact_features_mismatch")
    if tuple(args) != _MODE_ARGS[mode]:
        raise ValueError("exact_features_mismatch")
    validate_asset_path(Path(args[1]))


def validate_exact_features(help_text: str, args: Sequence[str], *, mode: str) -> None:
    """Prove exact b9596 help support and the frozen effective argument packet."""

    if not isinstance(help_text, str) or any(
        token not in help_text for token in _REQUIRED_HELP_TOKENS
    ):
        raise ValueError("exact_features_missing")
    _validate_effective_args(args, mode)


@dataclass(frozen=True, slots=True)
class RuntimeBackendWitness:
    """Content-free result of an explicitly supplied future `/proc/maps` read."""

    backend: Backend
    maps_sha256: str
    phase: str
    timestamp: str
    release_root_sha256: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        _validate_sha256(self.maps_sha256)
        _validate_sha256(self.release_root_sha256)
        _validate_timestamp(self.timestamp)
        expected = {
            "vulkan_baseline": ("vulkan", VULKAN_RELEASE_ROOT),
            "cuda_candidate": ("cuda", CUDA_RELEASE_ROOT),
            "cold_boot": ("cuda", CUDA_RELEASE_ROOT),
            "provisional_live": ("cuda", CUDA_RELEASE_ROOT),
        }
        if self.phase not in expected:
            raise ValueError("backend_witness_invariant")
        backend, release_root = expected[self.phase]
        if self.backend != backend or self.release_root_sha256 != _packet_hash(str(release_root)):
            raise ValueError("backend_witness_invariant")

    @classmethod
    def from_proc_maps(cls, maps_text: str, *, phase: str, timestamp: str) -> RuntimeBackendWitness:
        expected = {
            "vulkan_baseline": ("vulkan", VULKAN_RELEASE_ROOT),
            "cuda_candidate": ("cuda", CUDA_RELEASE_ROOT),
            "cold_boot": ("cuda", CUDA_RELEASE_ROOT),
            "provisional_live": ("cuda", CUDA_RELEASE_ROOT),
        }
        if phase not in expected:
            raise ValueError("backend_witness_phase")
        _validate_timestamp(timestamp)
        backend_paths = re.findall(r"/\S*libggml-(?:cuda|vulkan)\.so(?:\.[0-9]+)*", maps_text)
        backend = parse_backend_maps("\n".join(backend_paths))
        expected_backend, release_root = expected[phase]
        if backend != expected_backend:
            raise ValueError("backend_unproven")
        for path_text in backend_paths:
            path = validate_asset_path(Path(path_text))
            if not path.is_relative_to(release_root):
                raise ValueError("backend_release_root")
        return cls(
            backend=backend,
            maps_sha256=hashlib.sha256(maps_text.encode("utf-8")).hexdigest(),
            phase=phase,
            timestamp=timestamp,
            release_root_sha256=_packet_hash(str(release_root)),
        )

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "backend": self.backend,
                "maps_sha256": self.maps_sha256,
                "phase": self.phase,
                "timestamp": self.timestamp,
                "release_root_sha256": self.release_root_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    """Pinned static bundle identity; it does not claim the backend was loaded."""

    tag: str
    commit: str
    version: int
    alias: str
    model_sha256: str
    model_bytes: int
    runtime_sha256: str
    library_hashes: Mapping[str, str]
    effective_args: tuple[str, ...]
    mode: str
    production_override_sha256: str
    backend_environment: Mapping[str, str]
    runtime_manifest_sha256: str
    rollback_manifest_sha256: str
    cuda_toolkit: str
    cuda_compiler: str
    cmake_version: str
    driver_version: str
    gpu_identifier: str
    compute_capability: str
    backend: Backend
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if (self.tag, self.commit, self.version, self.alias) != (
            FROZEN_TAG,
            FROZEN_COMMIT,
            FROZEN_VERSION,
            FROZEN_ALIAS,
        ):
            raise ValueError("runtime_identity_mismatch")
        if self.model_sha256 != FROZEN_MODEL_SHA256 or self.model_bytes != FROZEN_MODEL_BYTES:
            raise ValueError("model_identity_mismatch")
        for digest in (
            self.model_sha256,
            self.runtime_sha256,
            self.runtime_manifest_sha256,
            self.rollback_manifest_sha256,
            self.production_override_sha256,
        ):
            _validate_sha256(digest)
        if not isinstance(self.effective_args, tuple):
            raise ValueError("immutable_sequence_required")
        _validate_effective_args(self.effective_args, self.mode)
        if not isinstance(self.library_hashes, Mapping):
            raise ValueError("runtime_identity_mismatch")
        hashes = dict(self.library_hashes)
        for name, digest in hashes.items():
            if _LIBRARY_RE.fullmatch(name) is None:
                raise ValueError("invalid_library_name")
            _validate_sha256(digest)
        if parse_backend_maps("\n".join(hashes)) != "cuda" or self.backend != "cuda":
            raise ValueError("backend_unproven")
        if dict(self.backend_environment) != dict(FROZEN_BACKEND_ENVIRONMENT):
            raise ValueError("backend_environment_mismatch")
        bounded_metadata = (
            self.cuda_toolkit == "13.2"
            and re.fullmatch(r"13\.2\.\d{1,3}", self.cuda_compiler) is not None
            and re.fullmatch(r"3\.\d{1,2}\.\d{1,3}", self.cmake_version) is not None
            and re.fullmatch(r"\d{3}\.\d{1,3}\.\d{1,3}", self.driver_version) is not None
            and re.fullmatch(r"NVIDIA (?:GeForce )?RTX 4090", self.gpu_identifier) is not None
            and self.compute_capability == "8.9"
        )
        if not bounded_metadata:
            raise ValueError("runtime_identity_mismatch")
        driver = tuple(int(part) for part in self.driver_version.split("."))
        if driver < (590, 44):
            raise ValueError("runtime_identity_mismatch")
        object.__setattr__(self, "library_hashes", MappingProxyType(hashes))
        object.__setattr__(
            self,
            "backend_environment",
            MappingProxyType(dict(self.backend_environment)),
        )

    @classmethod
    def from_static_evidence(
        cls,
        *,
        tag: str,
        commit: str,
        version: int,
        alias: str,
        model_sha256: str,
        model_bytes: int,
        runtime_sha256: str,
        library_hashes: Mapping[str, str],
        effective_args: Sequence[str],
        mode: str,
        production_override_sha256: str,
        backend_environment: Mapping[str, str],
        runtime_manifest_sha256: str,
        rollback_manifest_sha256: str,
        cuda_toolkit: str,
        cuda_compiler: str,
        cmake_version: str,
        driver_version: str,
        gpu_identifier: str,
        compute_capability: str,
    ) -> RuntimeIdentity:
        if (tag, commit, version, alias) != (
            FROZEN_TAG,
            FROZEN_COMMIT,
            FROZEN_VERSION,
            FROZEN_ALIAS,
        ):
            raise ValueError("runtime_identity_mismatch")
        _validate_nonnegative_int("model_bytes", model_bytes)
        if model_bytes != FROZEN_MODEL_BYTES:
            raise ValueError("model_identity_mismatch")
        if model_sha256 != FROZEN_MODEL_SHA256:
            raise ValueError("model_identity_mismatch")
        hashes = {name: _validate_sha256(digest) for name, digest in library_hashes.items()}
        if any(_LIBRARY_RE.fullmatch(name) is None for name in hashes):
            raise ValueError("invalid_library_name")
        backend = parse_backend_maps("\n".join(hashes))
        if backend != "cuda":
            raise ValueError("backend_unproven")
        _validate_effective_args(effective_args, mode)
        if dict(backend_environment) != dict(FROZEN_BACKEND_ENVIRONMENT):
            raise ValueError("backend_environment_mismatch")
        _validate_sha256(production_override_sha256)
        bounded_metadata = (
            cuda_toolkit == "13.2"
            and re.fullmatch(r"13\.2\.\d{1,3}", cuda_compiler) is not None
            and re.fullmatch(r"3\.\d{1,2}\.\d{1,3}", cmake_version) is not None
            and re.fullmatch(r"\d{3}\.\d{1,3}\.\d{1,3}", driver_version) is not None
            and re.fullmatch(r"NVIDIA (?:GeForce )?RTX 4090", gpu_identifier) is not None
            and compute_capability == "8.9"
        )
        if not bounded_metadata:
            raise ValueError("runtime_identity_mismatch")
        try:
            driver = tuple(int(part) for part in driver_version.split("."))
        except ValueError as exc:
            raise ValueError("runtime_identity_mismatch") from exc
        if driver < (590, 44):
            raise ValueError("runtime_identity_mismatch")
        return cls(
            tag=tag,
            commit=commit,
            version=version,
            alias=alias,
            model_sha256=_validate_sha256(model_sha256),
            model_bytes=model_bytes,
            runtime_sha256=_validate_sha256(runtime_sha256),
            library_hashes=MappingProxyType(hashes),
            effective_args=tuple(effective_args),
            mode=mode,
            production_override_sha256=production_override_sha256,
            backend_environment=MappingProxyType(dict(backend_environment)),
            runtime_manifest_sha256=_validate_sha256(runtime_manifest_sha256),
            rollback_manifest_sha256=_validate_sha256(rollback_manifest_sha256),
            cuda_toolkit=cuda_toolkit,
            cuda_compiler=cuda_compiler,
            cmake_version=cmake_version,
            driver_version=driver_version,
            gpu_identifier=gpu_identifier,
            compute_capability=compute_capability,
            backend=backend,
        )

    @property
    def configuration_sha256(self) -> str:
        return _packet_hash(
            {
                "mode": self.mode,
                "effective_args": list(self.effective_args),
                "production_override_sha256": self.production_override_sha256,
                "backend_environment": dict(self.backend_environment),
            }
        )

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(self.identity_packet)

    @property
    def identity_packet(self) -> dict[str, object]:
        return {
            "tag": self.tag,
            "commit": self.commit,
            "version": self.version,
            "backend": self.backend,
            "runtime_sha256": self.runtime_sha256,
            "runtime_manifest_sha256": self.runtime_manifest_sha256,
            "library_manifest_sha256": _packet_hash(dict(self.library_hashes)),
            "configuration_sha256": self.configuration_sha256,
            "mode": self.mode,
            "production_override_sha256": self.production_override_sha256,
            "backend_environment_sha256": _packet_hash(dict(self.backend_environment)),
            "model_sha256": self.model_sha256,
            "model_bytes": self.model_bytes,
            "alias": self.alias,
            "cuda_toolkit": self.cuda_toolkit,
            "cuda_compiler": self.cuda_compiler,
            "cmake_version": self.cmake_version,
            "driver_version": self.driver_version,
            "gpu_identifier": self.gpu_identifier,
            "compute_capability": self.compute_capability,
            "rollback_manifest_sha256": self.rollback_manifest_sha256,
        }


@dataclass(frozen=True, slots=True)
class PhaseEvidence:
    phase: str
    status: EvidenceStatus
    artifact_sha256: str | None
    timestamp: str | None
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if self.phase not in _PHASES:
            raise ValueError("phase_evidence")
        if self.status not in {"not_attempted", "pass", "fail"}:
            raise ValueError("phase_evidence")
        if self.status == "not_attempted":
            if self.artifact_sha256 is not None or self.timestamp is not None:
                raise ValueError("phase_evidence")
        else:
            if self.artifact_sha256 is None or self.timestamp is None:
                raise ValueError("phase_evidence")
            _validate_sha256(self.artifact_sha256)
            _validate_timestamp(self.timestamp)

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "phase": self.phase,
                "status": self.status,
                "artifact_sha256": self.artifact_sha256,
                "timestamp": self.timestamp,
            }
        )


@dataclass(frozen=True, slots=True)
class KernelCounters:
    reusemappingdb_map: int
    pmap_cb: int
    mmu_walk_map: int
    nv_err_no_memory: int
    xid: int
    unmatched_nvrm: int
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        for name in (
            "reusemappingdb_map",
            "pmap_cb",
            "mmu_walk_map",
            "nv_err_no_memory",
            "xid",
            "unmatched_nvrm",
        ):
            _validate_nonnegative_int(name, getattr(self, name))

    @classmethod
    def zero(cls) -> KernelCounters:
        return cls(0, 0, 0, 0, 0, 0)

    @property
    def clean(self) -> bool:
        return all(
            value == 0
            for value in (
                self.reusemappingdb_map,
                self.pmap_cb,
                self.mmu_walk_map,
                self.nv_err_no_memory,
                self.xid,
                self.unmatched_nvrm,
            )
        )

    def packet(self) -> dict[str, int]:
        return {
            "reusemappingdbMap": self.reusemappingdb_map,
            "pMapCb": self.pmap_cb,
            "mmuWalkMap": self.mmu_walk_map,
            "NV_ERR_NO_MEMORY": self.nv_err_no_memory,
            "Xid": self.xid,
            "unmatched_nvrm": self.unmatched_nvrm,
        }


@dataclass(frozen=True, slots=True)
class AuthorizationWitness:
    phase: str
    status: EvidenceStatus
    artifact_sha256: str | None
    parent_sha256: str | None
    timestamp: str | None
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if self.phase not in {"boot_authorization", "live_witness_authorization"}:
            raise ValueError("authorization_phase")
        if self.status not in {"not_attempted", "pass", "fail"}:
            raise ValueError("authorization_status")
        values = (self.artifact_sha256, self.parent_sha256, self.timestamp)
        if self.status == "not_attempted":
            if any(value is not None for value in values):
                raise ValueError("authorization_parent")
        else:
            if any(value is None for value in values):
                raise ValueError("authorization_parent")
            _validate_sha256(self.artifact_sha256)
            _validate_sha256(self.parent_sha256)
            _validate_timestamp(self.timestamp)

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "phase": self.phase,
                "status": self.status,
                "artifact_sha256": self.artifact_sha256,
                "parent_sha256": self.parent_sha256,
                "timestamp": self.timestamp,
            }
        )


@dataclass(frozen=True, slots=True)
class RollbackWitness:
    unit_sha256: str
    dropin_sha256: str
    runtime_sha256: str
    model_sha256: str
    alias: str
    health_state: str
    mtp_initialized: bool
    mtp_accepted_tokens: int
    restart_count: int
    kernel_counters: KernelCounters
    bar1_percent: float
    vram_mib: float
    shared_library_manifest_sha256: str
    effective_args_sha256: str
    containment_artifact_sha256: str
    artifact_sha256: str
    timestamp: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if (
            self.unit_sha256 != FROZEN_VULKAN_UNIT_SHA256
            or self.dropin_sha256 != FROZEN_VULKAN_DROPIN_SHA256
            or self.runtime_sha256 != FROZEN_VULKAN_RUNTIME_SHA256
            or self.model_sha256 != FROZEN_MODEL_SHA256
            or self.alias != FROZEN_ALIAS
            or self.shared_library_manifest_sha256 != FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256
            or self.effective_args_sha256 != FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256
        ):
            raise ValueError("rollback_identity_mismatch")
        for digest in (self.containment_artifact_sha256, self.artifact_sha256):
            _validate_sha256(digest)
        _validate_timestamp(self.timestamp)
        _require_bool("mtp_initialized", self.mtp_initialized)
        _validate_nonnegative_int("mtp_accepted_tokens", self.mtp_accepted_tokens)
        _validate_nonnegative_int("restart_count", self.restart_count)
        _validate_positive_number(self.bar1_percent)
        _validate_positive_number(self.vram_mib)
        if self.bar1_percent > 100:
            raise ValueError("positive_measurement")

    @property
    def passed(self) -> bool:
        return (
            self.health_state == "healthy"
            and self.mtp_initialized
            and self.mtp_accepted_tokens > 0
            and self.restart_count == 0
            and self.kernel_counters.clean
            and self.bar1_percent < 85.0
        )

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "unit_sha256": self.unit_sha256,
                "dropin_sha256": self.dropin_sha256,
                "runtime_sha256": self.runtime_sha256,
                "model_sha256": self.model_sha256,
                "alias": self.alias,
                "health_state": self.health_state,
                "mtp_initialized": self.mtp_initialized,
                "mtp_accepted_tokens": self.mtp_accepted_tokens,
                "restart_count": self.restart_count,
                "kernel_counters": self.kernel_counters.packet(),
                "bar1_percent": self.bar1_percent,
                "vram_mib": self.vram_mib,
                "shared_library_manifest_sha256": (self.shared_library_manifest_sha256),
                "effective_args_sha256": self.effective_args_sha256,
                "containment_artifact_sha256": self.containment_artifact_sha256,
                "artifact_sha256": self.artifact_sha256,
                "timestamp": self.timestamp,
            }
        )


@dataclass(frozen=True, slots=True)
class LoadInterval:
    component: str
    started_at: str
    ended_at: str

    def __post_init__(self) -> None:
        if self.component not in {"primary", "judge"}:
            raise ValueError("load_interval_component")
        if _timestamp_value(self.started_at) >= _timestamp_value(self.ended_at):
            raise ValueError("overlapping_load_intervals")


@dataclass(frozen=True, slots=True)
class ColdBootWitness:
    parent_sha256: str
    artifact_sha256: str
    timestamp: str
    topology_sha256: str
    load_intervals: tuple[LoadInterval, ...]
    steady_bar1_percent: float
    kernel_counters: KernelCounters
    restart_count: int
    containment_artifact_sha256: str
    runtime_sha256: str
    runtime_maps_sha256: str
    backend: Backend
    production_override_sha256: str
    alias: str
    model_sha256: str
    model_bytes: int
    service_health: str
    mtp_initialized: bool
    mtp_accepted_tokens: int
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.load_intervals, tuple):
            raise ValueError("immutable_sequence_required")
        for digest in (
            self.parent_sha256,
            self.artifact_sha256,
            self.topology_sha256,
            self.containment_artifact_sha256,
            self.runtime_sha256,
            self.runtime_maps_sha256,
            self.production_override_sha256,
            self.model_sha256,
        ):
            _validate_sha256(digest)
        timestamp_value = _timestamp_value(self.timestamp)
        if len(self.load_intervals) != 2 or {item.component for item in self.load_intervals} != {
            "primary",
            "judge",
        }:
            raise ValueError("cold_boot_topology")
        intervals = sorted(self.load_intervals, key=lambda item: _timestamp_value(item.started_at))
        if _timestamp_value(intervals[0].ended_at) >= _timestamp_value(intervals[1].started_at):
            raise ValueError("overlapping_load_intervals")
        if timestamp_value <= max(_timestamp_value(item.ended_at) for item in self.load_intervals):
            raise ValueError("evidence_timestamp_order")
        _validate_positive_number(self.steady_bar1_percent)
        _validate_nonnegative_int("restart_count", self.restart_count)
        _validate_nonnegative_int("mtp_accepted_tokens", self.mtp_accepted_tokens)
        _require_bool("mtp_initialized", self.mtp_initialized)

    @property
    def passed(self) -> bool:
        return (
            self.steady_bar1_percent < 85.0
            and self.kernel_counters.clean
            and self.restart_count == 0
            and self.backend == "cuda"
            and self.alias == FROZEN_ALIAS
            and self.model_sha256 == FROZEN_MODEL_SHA256
            and self.model_bytes == FROZEN_MODEL_BYTES
            and self.service_health == "healthy"
            and self.mtp_initialized
            and self.mtp_accepted_tokens > 0
        )

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "parent_sha256": self.parent_sha256,
                "artifact_sha256": self.artifact_sha256,
                "timestamp": self.timestamp,
                "topology_sha256": self.topology_sha256,
                "load_intervals": [
                    {
                        "component": item.component,
                        "started_at": item.started_at,
                        "ended_at": item.ended_at,
                    }
                    for item in self.load_intervals
                ],
                "steady_bar1_percent": self.steady_bar1_percent,
                "kernel_counters": self.kernel_counters.packet(),
                "restart_count": self.restart_count,
                "containment_artifact_sha256": self.containment_artifact_sha256,
                "runtime_sha256": self.runtime_sha256,
                "runtime_maps_sha256": self.runtime_maps_sha256,
                "backend": self.backend,
                "production_override_sha256": self.production_override_sha256,
                "alias": self.alias,
                "model_sha256": self.model_sha256,
                "model_bytes": self.model_bytes,
                "service_health": self.service_health,
                "mtp_initialized": self.mtp_initialized,
                "mtp_accepted_tokens": self.mtp_accepted_tokens,
            }
        )


@dataclass(frozen=True, slots=True)
class LiveTurnWitness:
    ordinal: int
    latency_ms: float
    false_absence_count: int
    wrong_answered_ungrounded_count: int
    type_regression_count: int
    recall_posture: str
    mtp_initialized: bool
    mtp_accepted_tokens: int
    output_length: int
    artifact_sha256: str

    def __post_init__(self) -> None:
        if self.ordinal not in range(1, 8):
            raise ValueError("live_turn_order")
        _validate_positive_number(self.latency_ms)
        for name in (
            "false_absence_count",
            "wrong_answered_ungrounded_count",
            "type_regression_count",
            "mtp_accepted_tokens",
        ):
            _validate_nonnegative_int(name, getattr(self, name))
        _require_bool("mtp_initialized", self.mtp_initialized)
        if (
            isinstance(self.output_length, bool)
            or not isinstance(self.output_length, int)
            or self.output_length <= 0
        ):
            raise ValueError("positive_output_length")
        if self.recall_posture not in {"pass", "fail"}:
            raise ValueError("live_turn_schema")
        _validate_sha256(self.artifact_sha256)

    @property
    def passed(self) -> bool:
        return (
            self.latency_ms < 12_000
            and self.false_absence_count == 0
            and self.wrong_answered_ungrounded_count == 0
            and self.type_regression_count == 0
            and self.recall_posture == "pass"
            and self.mtp_initialized
            and self.mtp_accepted_tokens > 0
        )

    def packet(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "latency_ms": self.latency_ms,
            "false_absence_count": self.false_absence_count,
            "wrong_answered_ungrounded_count": self.wrong_answered_ungrounded_count,
            "type_regression_count": self.type_regression_count,
            "recall_posture": self.recall_posture,
            "mtp_initialized": self.mtp_initialized,
            "mtp_accepted_tokens": self.mtp_accepted_tokens,
            "output_length": self.output_length,
            "artifact_sha256": self.artifact_sha256,
        }


@dataclass(frozen=True, slots=True)
class ProvisionalLiveWitness:
    parent_sha256: str
    artifact_sha256: str
    timestamp: str
    containment_artifact_sha256: str
    turns: tuple[LiveTurnWitness, ...]
    runtime_sha256: str
    runtime_maps_sha256: str
    backend: Backend
    configuration_sha256: str
    corpus_sha256: str
    order_sha256: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.turns, tuple):
            raise ValueError("immutable_sequence_required")
        for digest in (
            self.parent_sha256,
            self.artifact_sha256,
            self.containment_artifact_sha256,
            self.runtime_sha256,
            self.runtime_maps_sha256,
            self.configuration_sha256,
            self.corpus_sha256,
            self.order_sha256,
        ):
            _validate_sha256(digest)
        _validate_timestamp(self.timestamp)
        if len(self.turns) != 7 or tuple(turn.ordinal for turn in self.turns) != tuple(range(1, 8)):
            raise ValueError("live_turn_order")
        if self.corpus_sha256 != FROZEN_CORPUS_SHA256 or self.order_sha256 != FROZEN_ORDER_SHA256:
            raise ValueError("live_corpus_identity")

    @property
    def passed(self) -> bool:
        return self.backend == "cuda" and all(turn.passed for turn in self.turns)

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "parent_sha256": self.parent_sha256,
                "artifact_sha256": self.artifact_sha256,
                "timestamp": self.timestamp,
                "containment_artifact_sha256": self.containment_artifact_sha256,
                "turns": [turn.packet() for turn in self.turns],
                "runtime_sha256": self.runtime_sha256,
                "runtime_maps_sha256": self.runtime_maps_sha256,
                "backend": self.backend,
                "configuration_sha256": self.configuration_sha256,
                "corpus_sha256": self.corpus_sha256,
                "order_sha256": self.order_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class CycleMetrics:
    cycle: int
    topology_sha256: str
    bar1_before_percent: float
    bar1_after_load_percent: float
    bar1_after_inference_percent: float
    bar1_after_unload_percent: float
    vram_before_mib: float
    vram_after_load_mib: float
    vram_after_inference_mib: float
    vram_after_unload_mib: float
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if self.cycle not in {1, 2, 3}:
            raise ValueError("bench_identity_mismatch")
        _validate_sha256(self.topology_sha256)
        for name in (
            "bar1_before_percent",
            "bar1_after_load_percent",
            "bar1_after_inference_percent",
            "bar1_after_unload_percent",
            "vram_before_mib",
            "vram_after_load_mib",
            "vram_after_inference_mib",
            "vram_after_unload_mib",
        ):
            _validate_positive_number(getattr(self, name))
        for name in (
            "bar1_before_percent",
            "bar1_after_load_percent",
            "bar1_after_inference_percent",
            "bar1_after_unload_percent",
        ):
            if getattr(self, name) > 100:
                raise ValueError("positive_measurement")

    @property
    def unload_complete(self) -> bool:
        return (
            self.bar1_after_unload_percent <= self.bar1_before_percent
            and self.vram_after_unload_mib <= self.vram_before_mib
        )


@dataclass(frozen=True, slots=True)
class BenchSummary:
    phase: str
    alias: str
    model_sha256: str
    corpus_sha256: str
    order_sha256: str
    sample_n: int
    warmup_count: int
    measured_sample_count: int
    load_cycles: int
    seven_turn_max_ms: float
    p95_e2e_ms: float
    median_decode_tps: float
    median_prefill_tps: float
    cycles: tuple[CycleMetrics, ...]
    mtp_drafted_tokens: int
    mtp_accepted_tokens: int
    mtp_rejected_tokens: int
    mtp_initialized: bool
    false_absence_count: int
    wrong_answered_ungrounded_count: int
    type_regression_count: int
    recall_posture: str
    quality_failure_count: int
    owner_voice_evidence: PhaseEvidence
    kernel_counters: KernelCounters
    crash_count: int
    restart_count: int
    hang_count: int
    timeout_count: int
    unload_leak_mib: float
    rollback_witness: RollbackWitness
    cold_boot_witness: ColdBootWitness | None
    provisional_live_witness: ProvisionalLiveWitness | None
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.cycles, tuple):
            raise ValueError("immutable_sequence_required")
        if self.phase not in _PHASES:
            raise ValueError("closed_phase")
        if self.alias != FROZEN_ALIAS or self.model_sha256 != FROZEN_MODEL_SHA256:
            raise ValueError("bench_identity_mismatch")
        if (
            self.corpus_sha256 != FROZEN_CORPUS_SHA256
            or self.order_sha256 != FROZEN_ORDER_SHA256
            or self.sample_n != FROZEN_SAMPLE_N
            or self.warmup_count != FROZEN_WARMUP_COUNT
            or self.measured_sample_count != FROZEN_MEASURED_SAMPLE_COUNT
            or self.load_cycles != FROZEN_LOAD_CYCLES
        ):
            raise ValueError("bench_identity_mismatch")
        if len(self.cycles) != FROZEN_LOAD_CYCLES or tuple(
            cycle.cycle for cycle in self.cycles
        ) != (1, 2, 3):
            raise ValueError("bench_identity_mismatch")
        if len({cycle.topology_sha256 for cycle in self.cycles}) != 1:
            raise ValueError("topology_mismatch")
        for name in (
            "mtp_drafted_tokens",
            "mtp_accepted_tokens",
            "mtp_rejected_tokens",
            "false_absence_count",
            "wrong_answered_ungrounded_count",
            "type_regression_count",
            "quality_failure_count",
            "crash_count",
            "restart_count",
            "hang_count",
            "timeout_count",
        ):
            _validate_nonnegative_int(name, getattr(self, name))
        for name in (
            "seven_turn_max_ms",
            "p95_e2e_ms",
            "median_decode_tps",
            "median_prefill_tps",
        ):
            _validate_positive_number(getattr(self, name))
        _validate_nonnegative_number("unload_leak_mib", self.unload_leak_mib)
        _require_bool("mtp_initialized", self.mtp_initialized)
        if self.recall_posture not in {"pass", "fail"}:
            raise ValueError("bench_identity_mismatch")
        if self.owner_voice_evidence.phase != "owner_voice_review":
            raise ValueError("phase_evidence")

    @property
    def steady_bar1_percent(self) -> float:
        return max(cycle.bar1_after_inference_percent for cycle in self.cycles)

    @property
    def topology_sha256(self) -> str:
        return self.cycles[0].topology_sha256

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(_bench_packet(self))


@dataclass(frozen=True, slots=True)
class ContainmentSnapshot:
    phase: str
    boundary: str
    timestamp: str
    screen_flag_value: str
    active_state: str
    substate: str
    enabled_state: str
    port_closed: bool
    flag_source_sha256: str
    vision_unit_sha256: str
    artifact_sha256: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if self.phase not in {
            "vulkan_baseline",
            "cuda_candidate",
            "vulkan_rollback",
            "provisional_cuda_boot",
            "cold_boot",
            "provisional_live",
        }:
            raise ValueError("containment_phase")
        if self.boundary not in {"before", "after"}:
            raise ValueError("containment_phase")
        _validate_timestamp(self.timestamp)
        for digest in (
            self.flag_source_sha256,
            self.vision_unit_sha256,
            self.artifact_sha256,
        ):
            _validate_sha256(digest)
        _require_bool("port_closed", self.port_closed)

    @property
    def clean(self) -> bool:
        return (
            self.screen_flag_value == "0"
            and self.active_state == "inactive"
            and self.substate == "dead"
            and self.enabled_state == "disabled"
            and self.port_closed
        )

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "phase": self.phase,
                "boundary": self.boundary,
                "timestamp": self.timestamp,
                "screen_flag_value": self.screen_flag_value,
                "active_state": self.active_state,
                "substate": self.substate,
                "enabled_state": self.enabled_state,
                "port_closed": self.port_closed,
                "flag_source_sha256": self.flag_source_sha256,
                "vision_unit_sha256": self.vision_unit_sha256,
                "artifact_sha256": self.artifact_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class ContainmentWitness:
    snapshots: tuple[ContainmentSnapshot, ...]
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.snapshots, tuple):
            raise ValueError("immutable_sequence_required")
        required = {
            ("vulkan_baseline", "before"),
            ("vulkan_baseline", "after"),
            ("cuda_candidate", "before"),
            ("cuda_candidate", "after"),
            ("vulkan_rollback", "before"),
            ("vulkan_rollback", "after"),
        }
        actual = {(item.phase, item.boundary) for item in self.snapshots}
        if len(self.snapshots) != len(actual) or not required.issubset(actual):
            raise ValueError("containment_phase")

    @property
    def clean(self) -> bool:
        return (
            all(item.clean for item in self.snapshots)
            and len({item.flag_source_sha256 for item in self.snapshots}) == 1
            and len({item.vision_unit_sha256 for item in self.snapshots}) == 1
        )

    def complete_for(self, phases: set[str]) -> bool:
        actual = {(item.phase, item.boundary) for item in self.snapshots}
        return all(
            (phase, boundary) in actual for phase in phases for boundary in ("before", "after")
        )

    def brackets(self, phase: str, witness_timestamp: str) -> bool:
        phase_snapshots = {item.boundary: item for item in self.snapshots if item.phase == phase}
        if set(phase_snapshots) != {"before", "after"}:
            return False
        timestamp = _timestamp_value(witness_timestamp)
        return (
            _timestamp_value(phase_snapshots["before"].timestamp)
            < timestamp
            < _timestamp_value(phase_snapshots["after"].timestamp)
        )

    def phase_binding(self, phase: str) -> str:
        packet = {
            key: value for key, value in self.phase_hashes.items() if key.startswith(f"{phase}:")
        }
        if len(packet) != 2:
            raise ValueError("containment_phase")
        return _packet_hash(packet)

    @property
    def phase_hashes(self) -> Mapping[str, str]:
        return MappingProxyType(
            {f"{item.phase}:{item.boundary}": item.binding_sha256 for item in self.snapshots}
        )

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(dict(self.phase_hashes))


@dataclass(frozen=True, slots=True)
class PromotionVerdict:
    decision: Decision
    reasons: tuple[str, ...]
    control_summary_sha256: str
    candidate_summary_sha256: str
    control_maps_sha256: str
    candidate_maps_sha256: str
    containment_sha256: str
    boot_authorization_sha256: str
    live_authorization_sha256: str
    bench_evidence_sha256: str
    runtime_identity_sha256: str
    cold_boot_maps_sha256: str
    provisional_live_maps_sha256: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if self.decision not in _DECISIONS:
            raise ValueError("closed_decision")
        if any(reason not in _REASONS for reason in self.reasons):
            raise ValueError("closed_reason")
        if self.decision == "promote_cuda" and self.reasons:
            raise ValueError("closed_reason")
        for digest in (
            self.control_summary_sha256,
            self.candidate_summary_sha256,
            self.control_maps_sha256,
            self.candidate_maps_sha256,
            self.containment_sha256,
            self.boot_authorization_sha256,
            self.live_authorization_sha256,
            self.bench_evidence_sha256,
            self.runtime_identity_sha256,
            self.cold_boot_maps_sha256,
            self.provisional_live_maps_sha256,
        ):
            _validate_sha256(digest)

    @property
    def evidence_sha256(self) -> str:
        return self.bench_evidence_sha256

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "decision": self.decision,
                "reasons": list(self.reasons),
                "evidence_sha256": self.evidence_sha256,
                "boot_authorization_sha256": self.boot_authorization_sha256,
                "live_authorization_sha256": self.live_authorization_sha256,
                "runtime_identity_sha256": self.runtime_identity_sha256,
                "cold_boot_maps_sha256": self.cold_boot_maps_sha256,
                "provisional_live_maps_sha256": self.provisional_live_maps_sha256,
            }
        )


def _cycle_packet(cycle: CycleMetrics) -> dict[str, object]:
    return {
        "cycle": cycle.cycle,
        "topology_sha256": cycle.topology_sha256,
        "bar1_before_percent": cycle.bar1_before_percent,
        "bar1_after_load_percent": cycle.bar1_after_load_percent,
        "bar1_after_inference_percent": cycle.bar1_after_inference_percent,
        "bar1_after_unload_percent": cycle.bar1_after_unload_percent,
        "vram_before_mib": cycle.vram_before_mib,
        "vram_after_load_mib": cycle.vram_after_load_mib,
        "vram_after_inference_mib": cycle.vram_after_inference_mib,
        "vram_after_unload_mib": cycle.vram_after_unload_mib,
    }


def _bench_packet(summary: BenchSummary) -> dict[str, object]:
    return {
        "phase": summary.phase,
        "alias": summary.alias,
        "model_sha256": summary.model_sha256,
        "corpus_sha256": summary.corpus_sha256,
        "order_sha256": summary.order_sha256,
        "sample_n": summary.sample_n,
        "warmup_count": summary.warmup_count,
        "measured_sample_count": summary.measured_sample_count,
        "load_cycles": summary.load_cycles,
        "seven_turn_max_ms": summary.seven_turn_max_ms,
        "p95_e2e_ms": summary.p95_e2e_ms,
        "median_decode_tps": summary.median_decode_tps,
        "median_prefill_tps": summary.median_prefill_tps,
        "cycles": [_cycle_packet(cycle) for cycle in summary.cycles],
        "mtp_drafted_tokens": summary.mtp_drafted_tokens,
        "mtp_accepted_tokens": summary.mtp_accepted_tokens,
        "mtp_rejected_tokens": summary.mtp_rejected_tokens,
        "mtp_initialized": summary.mtp_initialized,
        "false_absence_count": summary.false_absence_count,
        "wrong_answered_ungrounded_count": summary.wrong_answered_ungrounded_count,
        "type_regression_count": summary.type_regression_count,
        "recall_posture": summary.recall_posture,
        "quality_failure_count": summary.quality_failure_count,
        "owner_voice_evidence_sha256": summary.owner_voice_evidence.binding_sha256,
        "kernel_counters": summary.kernel_counters.packet(),
        "crash_count": summary.crash_count,
        "restart_count": summary.restart_count,
        "hang_count": summary.hang_count,
        "timeout_count": summary.timeout_count,
        "unload_leak_mib": summary.unload_leak_mib,
        "rollback_witness_sha256": summary.rollback_witness.binding_sha256,
        "cold_boot_witness_sha256": (
            summary.cold_boot_witness.binding_sha256
            if summary.cold_boot_witness is not None
            else None
        ),
        "provisional_live_witness_sha256": (
            summary.provisional_live_witness.binding_sha256
            if summary.provisional_live_witness is not None
            else None
        ),
    }


def _bench_evidence_sha256(
    control: BenchSummary,
    candidate: BenchSummary,
    control_maps: RuntimeBackendWitness,
    candidate_maps: RuntimeBackendWitness,
    containment: ContainmentWitness,
) -> str:
    control_packet = _bench_packet(control)
    candidate_packet = _bench_packet(candidate)
    for packet in (control_packet, candidate_packet):
        packet["cold_boot_witness_sha256"] = None
        packet["provisional_live_witness_sha256"] = None
    base_phase_hashes = {
        key: value
        for key, value in containment.phase_hashes.items()
        if key.split(":", 1)[0] in {"vulkan_baseline", "cuda_candidate", "vulkan_rollback"}
    }
    return _packet_hash(
        {
            "control": control_packet,
            "candidate": candidate_packet,
            "control_maps_sha256": control_maps.binding_sha256,
            "candidate_maps_sha256": candidate_maps.binding_sha256,
            "containment_phase_hashes": base_phase_hashes,
        }
    )


def _make_verdict(
    decision: Decision,
    reasons: tuple[str, ...],
    control: BenchSummary,
    candidate: BenchSummary,
    control_maps: RuntimeBackendWitness,
    candidate_maps: RuntimeBackendWitness,
    containment: ContainmentWitness,
    boot_authorization: AuthorizationWitness,
    live_authorization: AuthorizationWitness,
    runtime_identity: RuntimeIdentity,
    cold_boot_maps: RuntimeBackendWitness | None = None,
    provisional_live_maps: RuntimeBackendWitness | None = None,
) -> PromotionVerdict:
    return PromotionVerdict(
        decision=decision,
        reasons=reasons,
        control_summary_sha256=control.binding_sha256,
        candidate_summary_sha256=candidate.binding_sha256,
        control_maps_sha256=control_maps.binding_sha256,
        candidate_maps_sha256=candidate_maps.binding_sha256,
        containment_sha256=containment.binding_sha256,
        boot_authorization_sha256=boot_authorization.binding_sha256,
        live_authorization_sha256=live_authorization.binding_sha256,
        bench_evidence_sha256=_bench_evidence_sha256(
            control, candidate, control_maps, candidate_maps, containment
        ),
        runtime_identity_sha256=runtime_identity.binding_sha256,
        cold_boot_maps_sha256=(
            cold_boot_maps.binding_sha256
            if cold_boot_maps is not None
            else _packet_hash({"phase": "cold_boot", "status": "not_reached"})
        ),
        provisional_live_maps_sha256=(
            provisional_live_maps.binding_sha256
            if provisional_live_maps is not None
            else _packet_hash({"phase": "provisional_live", "status": "not_reached"})
        ),
    )


def evaluate_promotion(
    control: BenchSummary,
    candidate: BenchSummary,
    control_maps: RuntimeBackendWitness,
    candidate_maps: RuntimeBackendWitness,
    containment: ContainmentWitness,
    boot_authorization: AuthorizationWitness,
    live_authorization: AuthorizationWitness,
    runtime_identity: RuntimeIdentity,
    *,
    cold_boot_maps: RuntimeBackendWitness | None = None,
    provisional_live_maps: RuntimeBackendWitness | None = None,
) -> PromotionVerdict:
    """Apply the closed v1.1 gate without performing or authorizing cutover."""

    if boot_authorization.phase != "boot_authorization":
        raise ValueError("authorization_phase")
    if live_authorization.phase != "live_witness_authorization":
        raise ValueError("authorization_phase")
    if control_maps.phase != "vulkan_baseline" or candidate_maps.phase != "cuda_candidate":
        raise ValueError("backend_witness_phase")
    if cold_boot_maps is not None and cold_boot_maps.phase != "cold_boot":
        raise ValueError("backend_witness_phase")
    if provisional_live_maps is not None and provisional_live_maps.phase != "provisional_live":
        raise ValueError("backend_witness_phase")
    reasons: list[str] = []

    if control.phase != "vulkan_baseline" or candidate.phase != "cuda_candidate":
        reasons.append("phase_mismatch")
    expected_mode = "bench" if boot_authorization.status == "not_attempted" else "production"
    if runtime_identity.mode != expected_mode:
        reasons.append("runtime_identity_mismatch")
    if control_maps.backend != "vulkan" or candidate_maps.backend != "cuda":
        reasons.append("backend_witness_mismatch")
    if candidate.alias != control.alias or candidate.alias != FROZEN_ALIAS:
        reasons.append("alias_changed")
    if candidate.model_sha256 != control.model_sha256:
        reasons.append("model_changed")
    if candidate.sample_n != 7:
        reasons.append("seven_turn_sample_count")
    if candidate.corpus_sha256 != control.corpus_sha256:
        reasons.append("corpus_hash_mismatch")
    if candidate.order_sha256 != control.order_sha256:
        reasons.append("order_hash_mismatch")
    if candidate.topology_sha256 != control.topology_sha256:
        reasons.append("topology_mismatch")
    if candidate.seven_turn_max_ms >= 12_000:
        reasons.append("seven_turn_latency_limit")
    if candidate.p95_e2e_ms > control.p95_e2e_ms:
        reasons.append("p95_regression")
    if candidate.median_decode_tps < control.median_decode_tps * 0.97:
        reasons.append("decode_throughput_regression")
    if candidate.steady_bar1_percent >= 85.0:
        reasons.append("bar1_ceiling")
    if candidate.steady_bar1_percent > control.steady_bar1_percent - 2.0:
        reasons.append("bar1_improvement_insufficient")
    if not control.kernel_counters.clean or not candidate.kernel_counters.clean:
        reasons.append("kernel_counter_delta")
    if candidate.crash_count != 0:
        reasons.append("crash_detected")
    if candidate.restart_count != 0:
        reasons.append("restart_detected")
    if candidate.hang_count != 0:
        reasons.append("hang_detected")
    if candidate.timeout_count != 0:
        reasons.append("timeout_detected")
    if candidate.unload_leak_mib != 0:
        reasons.append("unload_leak_detected")
    if any(not cycle.unload_complete for cycle in candidate.cycles):
        reasons.append("unload_incomplete")
    if candidate.quality_failure_count != 0:
        reasons.append("quality_failure")
    if candidate.false_absence_count != 0:
        reasons.append("false_absence")
    if candidate.wrong_answered_ungrounded_count != 0:
        reasons.append("wrong_answered_ungrounded")
    if candidate.type_regression_count != 0:
        reasons.append("type_regression")
    if candidate.recall_posture != "pass":
        reasons.append("recall_posture_failed")
    if candidate.owner_voice_evidence.status != "pass":
        reasons.append("owner_voice_review_missing")
    if not candidate.mtp_initialized:
        reasons.append("mtp_not_initialized")
    if candidate.mtp_accepted_tokens <= 0:
        reasons.append("mtp_acceptance_missing")
    if (
        candidate.mtp_drafted_tokens
        != candidate.mtp_accepted_tokens + candidate.mtp_rejected_tokens
    ):
        reasons.append("mtp_counter_mismatch")
    base_phases = {"vulkan_baseline", "cuda_candidate", "vulkan_rollback"}
    if not containment.complete_for(base_phases):
        reasons.append("containment_incomplete")
    if (
        not candidate.rollback_witness.passed
        or candidate.rollback_witness.containment_artifact_sha256
        != containment.phase_binding("vulkan_rollback")
        or not containment.brackets("vulkan_rollback", candidate.rollback_witness.timestamp)
    ):
        reasons.append("rollback_drill_failed")
    if not containment.brackets("vulkan_baseline", control_maps.timestamp):
        reasons.append("containment_incomplete")
    if not containment.brackets("cuda_candidate", candidate_maps.timestamp):
        reasons.append("containment_incomplete")
    if not containment.clean:
        reasons.append("containment_failed")

    if reasons:
        return _make_verdict(
            "keep_vulkan",
            tuple(reasons),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    bench_evidence_sha = _bench_evidence_sha256(
        control, candidate, control_maps, candidate_maps, containment
    )
    if boot_authorization.status == "fail":
        return _make_verdict(
            "keep_vulkan",
            ("owner_authorization_failed",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    if boot_authorization.status == "not_attempted":
        if (
            candidate.cold_boot_witness is not None
            or candidate.provisional_live_witness is not None
            or cold_boot_maps is not None
            or provisional_live_maps is not None
            or live_authorization.status != "not_attempted"
        ):
            return _make_verdict(
                "keep_vulkan",
                ("evidence_chain_invalid",),
                control,
                candidate,
                control_maps,
                candidate_maps,
                containment,
                boot_authorization,
                live_authorization,
                runtime_identity,
                cold_boot_maps,
                provisional_live_maps,
            )
        return _make_verdict(
            "bench_passed",
            (),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    latest_bench_time = max(
        [_timestamp_value(control_maps.timestamp), _timestamp_value(candidate_maps.timestamp)]
        + [
            _timestamp_value(item.timestamp)
            for item in containment.snapshots
            if item.phase in base_phases
        ]
        + [_timestamp_value(candidate.rollback_witness.timestamp)]
    )
    if (
        boot_authorization.parent_sha256 != bench_evidence_sha
        or _timestamp_value(boot_authorization.timestamp) <= latest_bench_time
    ):
        return _make_verdict(
            "keep_vulkan",
            ("evidence_chain_invalid",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    if candidate.cold_boot_witness is None:
        if cold_boot_maps is not None or provisional_live_maps is not None:
            return _make_verdict(
                "keep_vulkan",
                ("evidence_chain_invalid",),
                control,
                candidate,
                control_maps,
                candidate_maps,
                containment,
                boot_authorization,
                live_authorization,
                runtime_identity,
                cold_boot_maps,
                provisional_live_maps,
            )
        return _make_verdict(
            "provisional_cuda_boot",
            ("cold_boot_witness_pending",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    cold = candidate.cold_boot_witness
    if (
        cold_boot_maps is None
        or cold.parent_sha256 != boot_authorization.binding_sha256
        or _timestamp_value(cold.timestamp) <= _timestamp_value(boot_authorization.timestamp)
        or not containment.complete_for({"provisional_cuda_boot", "cold_boot"})
        or cold.containment_artifact_sha256 != containment.phase_binding("cold_boot")
        or not containment.brackets("cold_boot", cold.timestamp)
        or not containment.brackets("cold_boot", cold_boot_maps.timestamp)
        or cold.runtime_sha256 != runtime_identity.runtime_sha256
        or cold.runtime_maps_sha256 != cold_boot_maps.binding_sha256
        or cold.backend != cold_boot_maps.backend
        or cold.production_override_sha256 != runtime_identity.production_override_sha256
        or cold.alias != runtime_identity.alias
        or cold.model_sha256 != runtime_identity.model_sha256
        or cold.model_bytes != runtime_identity.model_bytes
    ):
        return _make_verdict(
            "keep_vulkan",
            ("evidence_chain_invalid",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    if not cold.passed:
        return _make_verdict(
            "keep_vulkan",
            ("cold_boot_witness_failed",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    if live_authorization.status == "fail":
        return _make_verdict(
            "keep_vulkan",
            ("live_authorization_failed",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    if live_authorization.status == "not_attempted":
        return _make_verdict(
            "provisional_cuda_boot",
            ("provisional_live_witness_pending",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    if live_authorization.parent_sha256 != cold.binding_sha256 or _timestamp_value(
        live_authorization.timestamp
    ) <= _timestamp_value(cold.timestamp):
        return _make_verdict(
            "keep_vulkan",
            ("evidence_chain_invalid",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    live = candidate.provisional_live_witness
    if live is None:
        if provisional_live_maps is not None:
            return _make_verdict(
                "keep_vulkan",
                ("evidence_chain_invalid",),
                control,
                candidate,
                control_maps,
                candidate_maps,
                containment,
                boot_authorization,
                live_authorization,
                runtime_identity,
                cold_boot_maps,
                provisional_live_maps,
            )
        return _make_verdict(
            "provisional_cuda_boot",
            ("provisional_live_witness_pending",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    if (
        provisional_live_maps is None
        or live.parent_sha256 != live_authorization.binding_sha256
        or _timestamp_value(live.timestamp) <= _timestamp_value(live_authorization.timestamp)
        or not containment.complete_for({"provisional_live"})
        or live.containment_artifact_sha256 != containment.phase_binding("provisional_live")
        or not containment.brackets("provisional_live", live.timestamp)
        or not containment.brackets("provisional_live", provisional_live_maps.timestamp)
        or live.runtime_sha256 != runtime_identity.runtime_sha256
        or live.runtime_maps_sha256 != provisional_live_maps.binding_sha256
        or live.backend != provisional_live_maps.backend
        or live.configuration_sha256 != runtime_identity.configuration_sha256
    ):
        return _make_verdict(
            "keep_vulkan",
            ("evidence_chain_invalid",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    if not live.passed:
        return _make_verdict(
            "keep_vulkan",
            ("provisional_live_witness_failed",),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            boot_authorization,
            live_authorization,
            runtime_identity,
            cold_boot_maps,
            provisional_live_maps,
        )
    return _make_verdict(
        "promote_cuda",
        (),
        control,
        candidate,
        control_maps,
        candidate_maps,
        containment,
        boot_authorization,
        live_authorization,
        runtime_identity,
        cold_boot_maps,
        provisional_live_maps,
    )


def _packet_hash(value: object) -> str:
    packet = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packet.encode("utf-8")).hexdigest()


def _timestamp_value(timestamp: str) -> datetime:
    if not isinstance(timestamp, str):
        raise ValueError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("invalid_timestamp")
    return parsed


def _validate_timestamp(timestamp: str) -> None:
    _timestamp_value(timestamp)


def _assert_content_light(receipt: Mapping[str, object]) -> None:
    serialized = json.dumps(receipt, sort_keys=True).lower()
    if any(marker in serialized for marker in _CONTENT_MARKERS):
        raise ValueError("content_marker")


def receipt_mode_allows(identity: RuntimeIdentity, *, decision: str) -> bool:
    if decision not in _DECISIONS:
        raise ValueError("closed_decision")
    if identity.mode == "bench":
        return decision in {"bench_passed", "keep_vulkan"}
    if identity.mode == "production":
        return decision in {"provisional_cuda_boot", "promote_cuda", "keep_vulkan"}
    return False


def build_receipt(
    identity: RuntimeIdentity,
    control: BenchSummary,
    candidate: BenchSummary,
    control_maps: RuntimeBackendWitness,
    candidate_maps: RuntimeBackendWitness,
    containment: ContainmentWitness,
    boot_authorization: AuthorizationWitness,
    live_authorization: AuthorizationWitness,
    verdict: PromotionVerdict,
    *,
    timestamp: str,
    cold_boot_maps: RuntimeBackendWitness | None = None,
    provisional_live_maps: RuntimeBackendWitness | None = None,
) -> dict[str, object]:
    """Serialize content-light producer evidence, never an admission decision."""

    _validate_timestamp(timestamp)
    if candidate.alias != identity.alias or candidate.model_sha256 != identity.model_sha256:
        raise ValueError("receipt_identity_mismatch")
    if not receipt_mode_allows(identity, decision=verdict.decision):
        raise ValueError("receipt_mode_mismatch")
    expected = evaluate_promotion(
        control,
        candidate,
        control_maps,
        candidate_maps,
        containment,
        boot_authorization,
        live_authorization,
        identity,
        cold_boot_maps=cold_boot_maps,
        provisional_live_maps=provisional_live_maps,
    )
    if expected != verdict:
        raise ValueError("verdict_binding_mismatch")
    receipt: dict[str, object] = {
        "schema": SCHEMA_VERSION,
        "timestamp": timestamp,
        "phase": candidate.phase,
        "artifact_role": "producer_evidence_not_verdict",
        "decision": verdict.decision,
        "reasons": list(verdict.reasons),
        "runtime": dict(identity.identity_packet),
        "backend_witnesses": {
            "control_maps_sha256": control_maps.maps_sha256,
            "candidate_maps_sha256": candidate_maps.maps_sha256,
            "control_binding_sha256": control_maps.binding_sha256,
            "candidate_binding_sha256": candidate_maps.binding_sha256,
            "cold_boot_maps_sha256": (
                cold_boot_maps.maps_sha256 if cold_boot_maps is not None else None
            ),
            "cold_boot_binding_sha256": (
                cold_boot_maps.binding_sha256 if cold_boot_maps is not None else None
            ),
            "provisional_live_maps_sha256": (
                provisional_live_maps.maps_sha256 if provisional_live_maps is not None else None
            ),
            "provisional_live_binding_sha256": (
                provisional_live_maps.binding_sha256 if provisional_live_maps is not None else None
            ),
        },
        "measurements": {
            "sample_n": candidate.sample_n,
            "warmup_count": candidate.warmup_count,
            "measured_sample_count": candidate.measured_sample_count,
            "load_cycles": candidate.load_cycles,
            "corpus_sha256": candidate.corpus_sha256,
            "order_sha256": candidate.order_sha256,
            "seven_turn_max_ms": candidate.seven_turn_max_ms,
            "p95_e2e_ms": candidate.p95_e2e_ms,
            "median_decode_tps": candidate.median_decode_tps,
            "median_prefill_tps": candidate.median_prefill_tps,
            "steady_bar1_percent": candidate.steady_bar1_percent,
            "topology_sha256": candidate.topology_sha256,
            "cycles": [_cycle_packet(cycle) for cycle in candidate.cycles],
            "mtp_drafted_tokens": candidate.mtp_drafted_tokens,
            "mtp_accepted_tokens": candidate.mtp_accepted_tokens,
            "mtp_rejected_tokens": candidate.mtp_rejected_tokens,
            "mtp_initialized": candidate.mtp_initialized,
            "false_absence_count": candidate.false_absence_count,
            "wrong_answered_ungrounded_count": (candidate.wrong_answered_ungrounded_count),
            "type_regression_count": candidate.type_regression_count,
            "recall_posture": candidate.recall_posture,
            "quality_failure_count": candidate.quality_failure_count,
            "kernel_counters": candidate.kernel_counters.packet(),
            "crash_count": candidate.crash_count,
            "restart_count": candidate.restart_count,
            "hang_count": candidate.hang_count,
            "timeout_count": candidate.timeout_count,
            "unload_leak_mib": candidate.unload_leak_mib,
        },
        "phase_evidence": {
            "owner_voice_sha256": candidate.owner_voice_evidence.binding_sha256,
            "rollback_sha256": candidate.rollback_witness.binding_sha256,
            "cold_boot_sha256": (
                candidate.cold_boot_witness.binding_sha256
                if candidate.cold_boot_witness is not None
                else None
            ),
            "provisional_live_sha256": (
                candidate.provisional_live_witness.binding_sha256
                if candidate.provisional_live_witness is not None
                else None
            ),
            "boot_authorization_sha256": boot_authorization.binding_sha256,
            "live_authorization_sha256": live_authorization.binding_sha256,
            "provisional_live_output_lengths": (
                [turn.output_length for turn in candidate.provisional_live_witness.turns]
                if candidate.provisional_live_witness is not None
                else []
            ),
        },
        "containment": {
            "clean": containment.clean,
            "phase_hashes": dict(containment.phase_hashes),
        },
        "gate_bindings": {
            "control_summary_sha256": verdict.control_summary_sha256,
            "candidate_summary_sha256": verdict.candidate_summary_sha256,
            "control_maps_sha256": verdict.control_maps_sha256,
            "candidate_maps_sha256": verdict.candidate_maps_sha256,
            "containment_sha256": verdict.containment_sha256,
            "boot_authorization_sha256": verdict.boot_authorization_sha256,
            "live_authorization_sha256": verdict.live_authorization_sha256,
            "bench_evidence_sha256": verdict.bench_evidence_sha256,
            "runtime_identity_sha256": verdict.runtime_identity_sha256,
            "cold_boot_maps_sha256": verdict.cold_boot_maps_sha256,
            "provisional_live_maps_sha256": verdict.provisional_live_maps_sha256,
        },
    }
    _assert_content_light(receipt)
    return receipt
