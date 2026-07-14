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
import statistics
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
# Compact JSON array of the common 27-token A/B argv tail after executable.
FROZEN_BENCH_ARGS_SHA256 = (
    "7fd627e1132ff30fb7f45df2cbf83d166002b0a0c56bcd07e169eca2180bd413"
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
_UTC_Z_RE = re.compile(
    r"(?P<whole>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]+))?Z\Z"
)
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
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise ValueError("invalid_sha256")
    return value


def _json_number_serializable(value: float | int) -> bool:
    try:
        json.dumps(value, allow_nan=False)
    except (OverflowError, TypeError, ValueError):
        return False
    return True


def _finitely_float_representable(value: float | int) -> bool:
    try:
        converted = float(value)
    except (OverflowError, TypeError, ValueError):
        return False
    return math.isfinite(converted)


def _validate_nonnegative_int(name: str, value: int) -> None:
    if (
        type(value) is not int
        or value < 0
        or not _json_number_serializable(value)
    ):
        raise ValueError(f"invalid_{name}")


def _validate_nonnegative_number(name: str, value: float | int) -> None:
    if type(value) not in (float, int):
        raise ValueError(f"invalid_{name}")
    if (
        value < 0
        or not _json_number_serializable(value)
        or not _finitely_float_representable(value)
    ):
        raise ValueError(f"invalid_{name}")


def _validate_positive_number(value: float | int) -> None:
    if type(value) not in (float, int):
        raise ValueError("positive_measurement")
    if (
        value <= 0
        or not _json_number_serializable(value)
        or not _finitely_float_representable(value)
    ):
        raise ValueError("positive_measurement")


def _require_bool(name: str, value: bool) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"invalid_{name}")


def _validate_utc_z_timestamp(timestamp: str) -> None:
    if not isinstance(timestamp, str) or _UTC_Z_RE.fullmatch(timestamp) is None:
        raise ValueError("invalid_timestamp")
    _validate_timestamp(timestamp)


def _authorization_ttl_matches(issued_at: str, expires_at: str, ttl_s: int) -> bool:
    issued_match = _UTC_Z_RE.fullmatch(issued_at)
    expires_match = _UTC_Z_RE.fullmatch(expires_at)
    if issued_match is None or expires_match is None:
        raise ValueError("invalid_timestamp")
    issued_whole = datetime.fromisoformat(issued_match.group("whole") + "+00:00")
    expires_whole = datetime.fromisoformat(expires_match.group("whole") + "+00:00")
    issued_fraction = (issued_match.group("fraction") or "").rstrip("0")
    expires_fraction = (expires_match.group("fraction") or "").rstrip("0")
    whole_delta = expires_whole - issued_whole
    whole_seconds = whole_delta.days * 86_400 + whole_delta.seconds
    return whole_seconds == ttl_s and issued_fraction == expires_fraction


def _compare_utc_z(left: str, right: str) -> int:
    """Compare canonical UTC timestamps without truncating fractional seconds."""

    _validate_utc_z_timestamp(left)
    _validate_utc_z_timestamp(right)
    left_match = _UTC_Z_RE.fullmatch(left)
    right_match = _UTC_Z_RE.fullmatch(right)
    if left_match is None or right_match is None:  # guarded above; keeps typing honest
        raise ValueError("invalid_timestamp")
    left_whole = datetime.fromisoformat(left_match.group("whole") + "+00:00")
    right_whole = datetime.fromisoformat(right_match.group("whole") + "+00:00")
    if left_whole != right_whole:
        return -1 if left_whole < right_whole else 1
    left_fraction = left_match.group("fraction") or ""
    right_fraction = right_match.group("fraction") or ""
    width = max(len(left_fraction), len(right_fraction), 1)
    left_digits = left_fraction.ljust(width, "0")
    right_digits = right_fraction.ljust(width, "0")
    if left_digits == right_digits:
        return 0
    return -1 if left_digits < right_digits else 1


def _containment_brackets_exact(
    containment: ContainmentWitness,
    phase: str,
    timestamp: str,
) -> bool:
    phase_snapshots = {
        item.boundary: item
        for item in containment.snapshots
        if item.phase == phase
    }
    return (
        set(phase_snapshots) == {"before", "after"}
        and _compare_utc_z(phase_snapshots["before"].timestamp, timestamp) < 0
        and _compare_utc_z(timestamp, phase_snapshots["after"].timestamp) < 0
    )


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


_BACKEND_PHASES: Mapping[str, tuple[Backend, Path]] = MappingProxyType(
    {
        "vulkan_baseline": ("vulkan", VULKAN_RELEASE_ROOT),
        "cuda_candidate": ("cuda", CUDA_RELEASE_ROOT),
        "vulkan_rollback": ("vulkan", VULKAN_RELEASE_ROOT),
        "cold_boot": ("cuda", CUDA_RELEASE_ROOT),
        "provisional_live": ("cuda", CUDA_RELEASE_ROOT),
    }
)


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
        if type(self.schema_version) is not str or self.schema_version != SCHEMA_VERSION:
            raise ValueError("schema_version_mismatch")
        _validate_sha256(self.maps_sha256)
        _validate_sha256(self.release_root_sha256)
        _validate_timestamp(self.timestamp)
        if type(self.phase) is not str or self.phase not in _BACKEND_PHASES:
            raise ValueError("backend_witness_invariant")
        backend, release_root = _BACKEND_PHASES[self.phase]
        if (
            type(self.backend) is not str
            or self.backend != backend
            or self.release_root_sha256 != _packet_hash(str(release_root))
        ):
            raise ValueError("backend_witness_invariant")

    @classmethod
    def from_proc_maps(cls, maps_text: str, *, phase: str, timestamp: str) -> RuntimeBackendWitness:
        if type(phase) is not str or phase not in _BACKEND_PHASES:
            raise ValueError("backend_witness_phase")
        if type(maps_text) is not str:
            raise ValueError("backend_unproven")
        _validate_timestamp(timestamp)
        backend_paths = re.findall(r"/\S*libggml-(?:cuda|vulkan)\.so(?:\.[0-9]+)*", maps_text)
        backend = parse_backend_maps("\n".join(backend_paths))
        expected_backend, release_root = _BACKEND_PHASES[phase]
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


CYCLE_BACKEND_WITNESS_SCHEMA = "cuda_migration.cycle_backend_witness.v1"
QUALITY_EVIDENCE_SCHEMA = "cuda_migration.quality_evidence.v1"
OWNER_VOICE_REVIEW_SCHEMA = "cuda_migration.owner_voice_review.v1"
CONSUMPTION_RECEIPT_SCHEMA = "cuda_bench_driver.consumption_receipt.v1"
WINDOW_AUTHORIZATION_SCHEMA = "cuda_bench_driver.window_authorization.v1"
CONTINUATION_SCHEMA = "cuda_bench_driver.continuation.v1"
STATIC_PREFLIGHT_SCHEMA = "cuda_bench_driver.static_preflight.v1"
CONTAINMENT_SNAPSHOT_SCHEMA = "cuda_bench_driver.containment_snapshot.v1"
RUNTIME_IDENTITY_SCHEMA = "cuda_bench_driver.runtime_identity.v1"
COLD_BOOT_WITNESS_SCHEMA = "cuda_migration.cold_boot_witness.v1"
PROVISIONAL_LIVE_WITNESS_SCHEMA = "cuda_migration.provisional_live_witness.v1"
AUTHORIZATION_WITNESS_SCHEMA = "cuda_migration.authorization_witness.v1"
BACKEND_MAP_WITNESS_SCHEMA = "cuda_migration.backend_map_witness.v1"
TURN_MANIFEST_SCHEMA = "cuda_bench_driver.turn_manifest.v1"
PHASE_PACKET_SCHEMA = "cuda_bench_driver.phase_packet.v1"
ROLLBACK_EVIDENCE_BUNDLE_SCHEMA = "cuda_migration.rollback_evidence_bundle.v1"
BENCH_EVIDENCE_BUNDLE_SCHEMA = "cuda_migration.bench_evidence_bundle.v1"

_NONCE_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOW_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_GPU_UUID_RE = re.compile(
    r"^GPU-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
WINDOW_TTL_S = 14_400
CONTINUATION_TTL_S = 3_600

_TURN_OUTCOMES = frozenset(
    {"completed", "http_timeout", "crash", "hang", "malformed_response"}
)
_PHASE_PACKET_OUTCOMES = frozenset(
    {
        "completed",
        "tier_mismatch",
        "preflight_service_active",
        "preflight_port_open",
        "preflight_gpu_occupied",
        "preflight_bench_port_busy",
        "identity_mismatch",
        "corpus_unavailable",
        "gpu_scope_violation",
        "authorization_missing",
        "authorization_malformed",
        "authorization_not_yet_valid",
        "authorization_expired",
        "authorization_boot_mismatch",
        "authorization_scope_mismatch",
        "authorization_consumed",
        "continuation_missing",
        "continuation_parent_mismatch",
        "containment_violation",
        "readiness_timeout",
        "alias_mismatch",
        "backend_unproven",
        "http_timeout",
        "crash",
        "hang",
        "malformed_response",
        "response_too_large",
        "mtp_unproven",
        "topology_drift",
        "kernel_unmatched",
        "unload_incomplete",
        "filesystem_hazard",
        "pid_reuse_detected",
        "rehearsal_artifact_rejected",
        "provider_uncertain",
        "spawn_failure",
        "journal_failure",
        "interrupted",
        "cleanup_incomplete",
        "assembly_refused",
        "unscorable",
    }
)


@dataclass(frozen=True, slots=True)
class TurnManifestEntry:
    cycle: int
    ordinal: int
    warmup: bool
    artifact_sha256: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.cycle, bool)
            or not isinstance(self.cycle, int)
            or self.cycle not in {1, 2, 3}
            or isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal not in range(8)
            or not isinstance(self.warmup, bool)
        ):
            raise ValueError("manifest_shape")
        _validate_sha256(self.artifact_sha256)


@dataclass(frozen=True, slots=True)
class TurnManifest:
    phase: str
    entries: tuple[TurnManifestEntry, ...]
    schema_version: str = field(default=TURN_MANIFEST_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.phase, str) or self.phase not in {
            "vulkan_baseline",
            "cuda_candidate",
        }:
            raise ValueError("closed_phase")
        if not isinstance(self.entries, tuple) or len(self.entries) != 24:
            raise ValueError("manifest_shape")
        expected = tuple(
            (cycle, ordinal, ordinal == 0)
            for cycle in (1, 2, 3)
            for ordinal in range(8)
        )
        if any(not isinstance(entry, TurnManifestEntry) for entry in self.entries):
            raise ValueError("manifest_shape")
        observed = tuple(
            (entry.cycle, entry.ordinal, entry.warmup) for entry in self.entries
        )
        if observed != expected:
            raise ValueError("manifest_shape")

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "phase": self.phase,
                "entries": [
                    [
                        entry.cycle,
                        entry.ordinal,
                        entry.warmup,
                        entry.artifact_sha256,
                    ]
                    for entry in self.entries
                ],
            }
        )


@dataclass(frozen=True, slots=True)
class TurnRecord:
    cycle: int
    ordinal: int
    warmup: bool
    artifact_sha256: str
    outcome: str
    e2e_ms: float
    ttft_ms: float
    prompt_per_second: float
    predicted_per_second: float
    draft_n: int | None
    draft_n_accepted: int | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.cycle, bool)
            or not isinstance(self.cycle, int)
            or self.cycle not in {1, 2, 3}
            or isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal not in range(8)
            or not isinstance(self.warmup, bool)
            or self.warmup != (self.ordinal == 0)
        ):
            raise ValueError("turn_record_shape")
        _validate_sha256(self.artifact_sha256)
        if not isinstance(self.outcome, str) or self.outcome not in _TURN_OUTCOMES:
            raise ValueError("turn_outcome_closed")
        for value in (
            self.e2e_ms,
            self.ttft_ms,
            self.prompt_per_second,
            self.predicted_per_second,
        ):
            if not isinstance(value, float) or not math.isfinite(value) or value < 0:
                raise ValueError("turn_measurement")
        if self.warmup:
            if self.draft_n is not None or self.draft_n_accepted is not None:
                raise ValueError("mtp_unproven")
        elif (
            isinstance(self.draft_n, bool)
            or not isinstance(self.draft_n, int)
            or isinstance(self.draft_n_accepted, bool)
            or not isinstance(self.draft_n_accepted, int)
            or self.draft_n < 0
            or self.draft_n_accepted < 0
            or self.draft_n_accepted > self.draft_n
            or not _json_number_serializable(self.draft_n)
            or not _json_number_serializable(self.draft_n_accepted)
        ):
            raise ValueError("mtp_unproven")

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "cycle": self.cycle,
                "ordinal": self.ordinal,
                "warmup": self.warmup,
                "artifact_sha256": self.artifact_sha256,
                "outcome": self.outcome,
                "e2e_ms": self.e2e_ms,
                "ttft_ms": self.ttft_ms,
                "prompt_per_second": self.prompt_per_second,
                "predicted_per_second": self.predicted_per_second,
                "draft_n": self.draft_n,
                "draft_n_accepted": self.draft_n_accepted,
            }
        )


@dataclass(frozen=True, slots=True)
class CycleBackendWitness:
    witness: RuntimeBackendWitness
    cycle: int
    load_started: str
    unload_proven: str
    schema_version: str = field(default=CYCLE_BACKEND_WITNESS_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.cycle, bool)
            or not isinstance(self.cycle, int)
            or self.cycle not in {1, 2, 3}
        ):
            raise ValueError("bench_identity_mismatch")
        if not isinstance(self.witness, RuntimeBackendWitness):
            raise ValueError("backend_witness_invariant")
        _validate_utc_z_timestamp(self.load_started)
        _validate_utc_z_timestamp(self.unload_proven)
        if not (
            _compare_utc_z(self.load_started, self.witness.timestamp) < 0
            and _compare_utc_z(self.witness.timestamp, self.unload_proven) < 0
        ):
            raise ValueError("witness_outside_interval")

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "cycle": self.cycle,
                "load_started": self.load_started,
                "unload_proven": self.unload_proven,
                "witness_binding_sha256": self.witness.binding_sha256,
            }
        )


@dataclass(frozen=True, slots=True)
class QualityEvidence:
    evaluator_version: str
    control_manifest_sha256: str
    candidate_manifest_sha256: str
    false_absence_count: int
    wrong_answered_ungrounded_count: int
    type_regression_count: int
    recall_posture: str
    quality_failure_count: int
    covered_turn_count: int
    timestamp: str
    schema_version: str = field(default=QUALITY_EVIDENCE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.evaluator_version, str) or not self.evaluator_version:
            raise ValueError("quality_evaluator_version")
        _validate_sha256(self.control_manifest_sha256)
        _validate_sha256(self.candidate_manifest_sha256)
        for name in (
            "false_absence_count",
            "wrong_answered_ungrounded_count",
            "type_regression_count",
            "quality_failure_count",
        ):
            _validate_nonnegative_int(name, getattr(self, name))
        if not isinstance(self.recall_posture, str) or self.recall_posture not in {
            "pass",
            "fail",
        }:
            raise ValueError("bench_identity_mismatch")
        if (
            isinstance(self.covered_turn_count, bool)
            or not isinstance(self.covered_turn_count, int)
            or self.covered_turn_count != FROZEN_MEASURED_SAMPLE_COUNT
        ):
            raise ValueError("quality_coverage")
        _validate_utc_z_timestamp(self.timestamp)

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "evaluator_version": self.evaluator_version,
                "control_manifest_sha256": self.control_manifest_sha256,
                "candidate_manifest_sha256": self.candidate_manifest_sha256,
                "false_absence_count": self.false_absence_count,
                "wrong_answered_ungrounded_count": self.wrong_answered_ungrounded_count,
                "type_regression_count": self.type_regression_count,
                "recall_posture": self.recall_posture,
                "quality_failure_count": self.quality_failure_count,
                "covered_turn_count": self.covered_turn_count,
                "timestamp": self.timestamp,
            }
        )


@dataclass(frozen=True, slots=True)
class OwnerVoiceReview:
    producer: str
    status: EvidenceStatus
    evaluator_version: str
    control_manifest_sha256: str
    candidate_manifest_sha256: str
    artifact_sha256: str
    timestamp: str
    schema_version: str = field(default=OWNER_VOICE_REVIEW_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.producer, str) or self.producer != "owner_human":
            raise ValueError("owner_voice_producer")
        if not isinstance(self.status, str) or self.status not in ("pass", "fail"):
            raise ValueError("phase_evidence")
        if not isinstance(self.evaluator_version, str) or not self.evaluator_version:
            raise ValueError("owner_voice_evaluator_version")
        _validate_sha256(self.control_manifest_sha256)
        _validate_sha256(self.candidate_manifest_sha256)
        _validate_sha256(self.artifact_sha256)
        _validate_utc_z_timestamp(self.timestamp)

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "producer": self.producer,
                "status": self.status,
                "evaluator_version": self.evaluator_version,
                "control_manifest_sha256": self.control_manifest_sha256,
                "candidate_manifest_sha256": self.candidate_manifest_sha256,
                "artifact_sha256": self.artifact_sha256,
                "timestamp": self.timestamp,
            }
        )


@dataclass(frozen=True, slots=True)
class ConsumptionReceipt:
    nonce: str
    phase: str
    boot_id: str
    timestamp: str
    schema_version: str = field(default=CONSUMPTION_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.nonce, str) or _NONCE_RE.fullmatch(self.nonce) is None:
            raise ValueError("nonce_syntax")
        if not isinstance(self.phase, str) or self.phase not in (
            "vulkan_baseline",
            "cuda_candidate",
        ):
            raise ValueError("closed_phase")
        if not isinstance(self.boot_id, str) or not self.boot_id:
            raise ValueError("boot_id_required")
        _validate_utc_z_timestamp(self.timestamp)

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "nonce": self.nonce,
                "phase": self.phase,
                "boot_id": self.boot_id,
                "timestamp": self.timestamp,
            }
        )


def _validate_authorization_fields(doc: object, ttl_s: int) -> None:
    window_id = getattr(doc, "window_id", None)
    phases = getattr(doc, "phases", None)
    boot_id = getattr(doc, "boot_id", None)
    nonce = getattr(doc, "nonce", None)
    owner = getattr(doc, "owner", None)
    if not isinstance(window_id, str) or _WINDOW_ID_RE.fullmatch(window_id) is None:
        raise ValueError("window_id_syntax")
    if not isinstance(phases, tuple):
        raise ValueError("immutable_sequence_required")
    if not phases or any(
        not isinstance(phase, str)
        or phase not in ("vulkan_baseline", "cuda_candidate")
        for phase in phases
    ):
        raise ValueError("closed_phase")
    if not isinstance(boot_id, str) or not boot_id:
        raise ValueError("boot_id_required")
    if not isinstance(nonce, str) or _NONCE_RE.fullmatch(nonce) is None:
        raise ValueError("nonce_syntax")
    issued_at = getattr(doc, "issued_at", None)
    expires_at = getattr(doc, "expires_at", None)
    _validate_utc_z_timestamp(issued_at)
    _validate_utc_z_timestamp(expires_at)
    if not _authorization_ttl_matches(issued_at, expires_at, ttl_s):
        raise ValueError("authorization_ttl")
    if not isinstance(owner, str) or not owner:
        raise ValueError("authorization_owner")


@dataclass(frozen=True, slots=True)
class WindowAuthorizationDoc:
    window_id: str
    phases: tuple[str, ...]
    boot_id: str
    nonce: str
    issued_at: str
    expires_at: str
    owner: str
    schema_version: str = field(default=WINDOW_AUTHORIZATION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        _validate_authorization_fields(self, WINDOW_TTL_S)

    @property
    def preimage_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "window_id": self.window_id,
                "phases": list(self.phases),
                "boot_id": self.boot_id,
                "nonce": self.nonce,
                "issued_at": self.issued_at,
                "expires_at": self.expires_at,
                "owner": self.owner,
            }
        )


@dataclass(frozen=True, slots=True)
class ContinuationDoc:
    window_id: str
    phases: tuple[str, ...]
    boot_id: str
    nonce: str
    issued_at: str
    expires_at: str
    owner: str
    parent_vulkan_packet_sha256: str
    schema_version: str = field(default=CONTINUATION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        _validate_authorization_fields(self, CONTINUATION_TTL_S)
        _validate_sha256(self.parent_vulkan_packet_sha256)

    @property
    def preimage_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "window_id": self.window_id,
                "phases": list(self.phases),
                "boot_id": self.boot_id,
                "nonce": self.nonce,
                "issued_at": self.issued_at,
                "expires_at": self.expires_at,
                "owner": self.owner,
                "parent_vulkan_packet_sha256": self.parent_vulkan_packet_sha256,
            }
        )


_STATIC_CHECK_EXPECTATIONS = MappingProxyType(
    {
        "corpus": FROZEN_CORPUS_SHA256,
        "incumbent_unit": FROZEN_VULKAN_UNIT_SHA256,
        "incumbent_dropin": FROZEN_VULKAN_DROPIN_SHA256,
        "incumbent_server": FROZEN_VULKAN_RUNTIME_SHA256,
        "model": FROZEN_MODEL_SHA256,
        "library_manifest": FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
        "effective_args": FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
    }
)
_STATIC_DYNAMIC_SHA_CHECKS = ("flag_source", "vision_unit", "candidate_manifest")
_STATIC_CHECK_NAMES = frozenset(_STATIC_CHECK_EXPECTATIONS) | frozenset(
    (*_STATIC_DYNAMIC_SHA_CHECKS, "bench_root_mode", "stub_pin")
)


@dataclass(frozen=True, slots=True)
class StaticPreflightDoc:
    gpu_uuid: str
    driver_package_sha256: str
    stub_sha256: str
    corpus_verified: bool
    checks: Mapping[str, str]
    timestamp: str
    schema_version: str = field(default=STATIC_PREFLIGHT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.checks, Mapping):
            raise ValueError("static_preflight_invalid")
        checks = dict(self.checks)
        if set(checks) != _STATIC_CHECK_NAMES or self.corpus_verified is not True:
            raise ValueError("static_preflight_invalid")
        if any(checks[name] != expected for name, expected in _STATIC_CHECK_EXPECTATIONS.items()):
            raise ValueError("static_preflight_invalid")
        if not isinstance(self.gpu_uuid, str) or _GPU_UUID_RE.fullmatch(self.gpu_uuid) is None:
            raise ValueError("static_preflight_invalid")
        if checks["bench_root_mode"] != "700" or checks["stub_pin"] != self.stub_sha256:
            raise ValueError("static_preflight_invalid")
        try:
            for name in _STATIC_DYNAMIC_SHA_CHECKS:
                _validate_sha256(checks[name])
            _validate_sha256(self.driver_package_sha256)
            _validate_sha256(self.stub_sha256)
        except ValueError as exc:
            raise ValueError("static_preflight_invalid") from exc
        _validate_utc_z_timestamp(self.timestamp)
        object.__setattr__(self, "checks", MappingProxyType(checks))

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "gpu_uuid": self.gpu_uuid,
                "driver_package_sha256": self.driver_package_sha256,
                "stub_sha256": self.stub_sha256,
                "corpus_verified": self.corpus_verified,
                "checks": dict(sorted(self.checks.items())),
                "timestamp": self.timestamp,
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
        if type(self.schema_version) is not str or self.schema_version != SCHEMA_VERSION:
            raise ValueError("schema_version_mismatch")
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
            type(self.schema_version) is not str
            or self.schema_version != SCHEMA_VERSION
            or type(self.kernel_counters) is not KernelCounters
            or type(self.health_state) is not str
        ):
            raise ValueError("rollback_evidence_type")
        for digest in (
            self.unit_sha256,
            self.dropin_sha256,
            self.runtime_sha256,
            self.model_sha256,
            self.shared_library_manifest_sha256,
            self.effective_args_sha256,
        ):
            _validate_sha256(digest)
        if (
            self.unit_sha256 != FROZEN_VULKAN_UNIT_SHA256
            or self.dropin_sha256 != FROZEN_VULKAN_DROPIN_SHA256
            or self.runtime_sha256 != FROZEN_VULKAN_RUNTIME_SHA256
            or self.model_sha256 != FROZEN_MODEL_SHA256
            or type(self.alias) is not str
            or self.alias != FROZEN_ALIAS
            or self.shared_library_manifest_sha256 != FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256
            or self.effective_args_sha256 != FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256
        ):
            raise ValueError("rollback_identity_mismatch")
        self.kernel_counters.__post_init__()
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
        if _compare_utc_z(self.started_at, self.ended_at) >= 0:
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
        if len(self.load_intervals) != 2 or {item.component for item in self.load_intervals} != {
            "primary",
            "judge",
        }:
            raise ValueError("cold_boot_topology")
        first, second = self.load_intervals
        if _compare_utc_z(first.started_at, second.started_at) > 0:
            first, second = second, first
        if _compare_utc_z(first.ended_at, second.started_at) >= 0:
            raise ValueError("overlapping_load_intervals")
        if any(
            _compare_utc_z(item.ended_at, self.timestamp) >= 0
            for item in self.load_intervals
        ):
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
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal not in range(1, 8)
        ):
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
    vram_before_mib: int
    vram_after_load_mib: int
    vram_after_inference_mib: int
    vram_after_unload_mib: int
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.cycle, bool)
            or not isinstance(self.cycle, int)
            or self.cycle not in {1, 2, 3}
        ):
            raise ValueError("bench_identity_mismatch")
        _validate_sha256(self.topology_sha256)
        for name in (
            "bar1_before_percent",
            "bar1_after_load_percent",
            "bar1_after_inference_percent",
            "bar1_after_unload_percent",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (float, int)):
                raise ValueError("positive_measurement")
            if value < 0 or value > 100 or not math.isfinite(value):
                raise ValueError("positive_measurement")
        for name in (
            "vram_before_mib",
            "vram_after_load_mib",
            "vram_after_inference_mib",
            "vram_after_unload_mib",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                or not _json_number_serializable(value)
            ):
                raise ValueError("vram_integer_mib")

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


def recompute_phase_statistics(records: tuple[TurnRecord, ...]) -> dict[str, object]:
    """Recompute every turn-derived phase aggregate from its typed rows."""

    expected_order = tuple(
        (cycle, ordinal, ordinal == 0)
        for cycle in (1, 2, 3)
        for ordinal in range(8)
    )
    if (
        not isinstance(records, tuple)
        or len(records) != 24
        or any(not isinstance(record, TurnRecord) for record in records)
        or tuple((record.cycle, record.ordinal, record.warmup) for record in records)
        != expected_order
    ):
        raise ValueError("turn_record_join")
    measured = tuple(record for record in records if not record.warmup)
    if len(measured) != FROZEN_MEASURED_SAMPLE_COUNT:
        raise ValueError("turn_record_join")
    for cycle in (1, 2, 3):
        if len(tuple(record for record in measured if record.cycle == cycle)) != 7:
            raise ValueError("turn_record_join")

    e2e = sorted(record.e2e_ms for record in measured)
    p95_index = math.ceil(0.95 * len(e2e)) - 1
    cycle_mtp = tuple(
        (
            sum(
                record.draft_n
                for record in measured
                if record.cycle == cycle and record.draft_n is not None
            ),
            sum(
                record.draft_n_accepted
                for record in measured
                if record.cycle == cycle and record.draft_n_accepted is not None
            ),
        )
        for cycle in (1, 2, 3)
    )
    drafted = sum(item[0] for item in cycle_mtp)
    accepted = sum(item[1] for item in cycle_mtp)
    return {
        "seven_turn_max_ms": max(e2e),
        "p95_e2e_ms": e2e[p95_index],
        "median_decode_tps": statistics.median(
            record.predicted_per_second for record in measured
        ),
        "median_prefill_tps": statistics.median(
            record.prompt_per_second for record in measured
        ),
        "mtp_drafted_tokens": drafted,
        "mtp_accepted_tokens": accepted,
        "mtp_rejected_tokens": drafted - accepted,
        "mtp_initialized": drafted > 0,
        "crash_count": sum(record.outcome == "crash" for record in records),
        "restart_count": 0,
        "hang_count": sum(record.outcome == "hang" for record in records),
        "timeout_count": sum(record.outcome == "http_timeout" for record in records),
    }


def phase_summary_projection(summary: BenchSummary) -> dict[str, object]:
    """Return only the aggregates a completed phase can itself produce."""

    if not isinstance(summary, BenchSummary):
        raise ValueError("projection_not_recomputable")
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
        "crash_count": summary.crash_count,
        "restart_count": summary.restart_count,
        "hang_count": summary.hang_count,
        "timeout_count": summary.timeout_count,
        "unload_leak_mib": float(summary.unload_leak_mib),
        "kernel_counters": summary.kernel_counters.packet(),
    }


def _canonical_projection_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass(frozen=True, slots=True)
class PhasePacket:
    phase: str
    outcome: str
    window_id: str
    boot_id: str
    gpu_uuid: str
    topology_sha256: str
    model_sha256: str
    corpus_sha256: str
    order_sha256: str
    effective_args_sha256: str
    driver_package_sha256: str
    authorization_preimage_sha256: str
    consumption_receipt_sha256: str
    static_preflight_sha256: str
    runtime_identity_sha256: str
    turn_manifest: TurnManifest
    turn_records: tuple[TurnRecord, ...]
    cycle_metrics: tuple[CycleMetrics, CycleMetrics, CycleMetrics]
    cycle_witnesses: tuple[
        CycleBackendWitness,
        CycleBackendWitness,
        CycleBackendWitness,
    ]
    containment_before_sha256: str
    containment_after_sha256: str
    kernel_cursor_before: str
    kernel_cursor_after: str
    kernel_counters: KernelCounters
    summary_projection_json: str
    cycle_one_before_snapshot_at: str
    timestamp: str
    schema_version: str = field(default=PHASE_PACKET_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.phase, str) or self.phase not in {
            "vulkan_baseline",
            "cuda_candidate",
        }:
            raise ValueError("closed_phase")
        if (
            not isinstance(self.outcome, str)
            or self.outcome not in _PHASE_PACKET_OUTCOMES
        ):
            raise ValueError("turn_outcome_closed")
        if not isinstance(self.window_id, str) or _WINDOW_ID_RE.fullmatch(self.window_id) is None:
            raise ValueError("window_id_syntax")
        if not isinstance(self.boot_id, str) or not self.boot_id:
            raise ValueError("boot_id_required")
        if not isinstance(self.gpu_uuid, str) or _GPU_UUID_RE.fullmatch(self.gpu_uuid) is None:
            raise ValueError("gpu_scope_violation")
        for digest in (
            self.topology_sha256,
            self.model_sha256,
            self.corpus_sha256,
            self.order_sha256,
            self.effective_args_sha256,
            self.driver_package_sha256,
            self.authorization_preimage_sha256,
            self.consumption_receipt_sha256,
            self.static_preflight_sha256,
            self.runtime_identity_sha256,
            self.containment_before_sha256,
            self.containment_after_sha256,
        ):
            _validate_sha256(digest)
        _validate_utc_z_timestamp(self.cycle_one_before_snapshot_at)
        _validate_utc_z_timestamp(self.timestamp)

        if not isinstance(self.turn_manifest, TurnManifest) or self.turn_manifest.phase != self.phase:
            raise ValueError("manifest_shape")
        if not isinstance(self.turn_records, tuple) or len(self.turn_records) != 24:
            raise ValueError("turn_record_join")
        manifest_join = tuple(
            (entry.cycle, entry.ordinal, entry.warmup, entry.artifact_sha256)
            for entry in self.turn_manifest.entries
        )
        if any(not isinstance(record, TurnRecord) for record in self.turn_records):
            raise ValueError("turn_record_join")
        record_join = tuple(
            (record.cycle, record.ordinal, record.warmup, record.artifact_sha256)
            for record in self.turn_records
        )
        if record_join != manifest_join:
            raise ValueError("turn_record_join")
        if self.outcome == "completed" and any(
            record.outcome != "completed" for record in self.turn_records
        ):
            raise ValueError("turn_outcome_incomplete")
        if self.outcome in {"crash", "hang", "http_timeout", "malformed_response"} and not any(
            record.outcome == self.outcome for record in self.turn_records
        ):
            raise ValueError("turn_outcome_incomplete")

        if (
            not isinstance(self.cycle_metrics, tuple)
            or len(self.cycle_metrics) != 3
            or any(not isinstance(metric, CycleMetrics) for metric in self.cycle_metrics)
            or tuple(metric.cycle for metric in self.cycle_metrics) != (1, 2, 3)
        ):
            raise ValueError("cycle_metrics_shape")
        if any(metric.topology_sha256 != self.topology_sha256 for metric in self.cycle_metrics):
            raise ValueError("projection_not_recomputable")
        if (
            not isinstance(self.cycle_witnesses, tuple)
            or len(self.cycle_witnesses) != 3
            or any(
                not isinstance(witness, CycleBackendWitness)
                for witness in self.cycle_witnesses
            )
            or tuple(witness.cycle for witness in self.cycle_witnesses) != (1, 2, 3)
        ):
            raise ValueError("bench_identity_mismatch")
        if any(witness.witness.phase != self.phase for witness in self.cycle_witnesses):
            raise ValueError("backend_witness_phase")
        if (
            _compare_utc_z(
                self.cycle_one_before_snapshot_at,
                self.cycle_witnesses[0].load_started,
            )
            >= 0
        ):
            raise ValueError("bench_identity_mismatch")

        if (
            not isinstance(self.kernel_cursor_before, str)
            or not self.kernel_cursor_before
            or not isinstance(self.kernel_cursor_after, str)
            or not self.kernel_cursor_after
            or self.kernel_cursor_before == self.kernel_cursor_after
        ):
            raise ValueError("kernel_window_invalid")
        if not isinstance(self.kernel_counters, KernelCounters):
            raise ValueError("projection_not_recomputable")
        self._validate_projection()

    def _validate_projection(self) -> None:
        if not isinstance(self.summary_projection_json, str):
            raise ValueError("projection_not_recomputable")
        try:
            projection = json.loads(self.summary_projection_json)
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("projection_not_recomputable") from exc
        if not isinstance(projection, Mapping):
            raise ValueError("projection_not_recomputable")
        try:
            projection_is_canonical = (
                _canonical_projection_json(projection) == self.summary_projection_json
            )
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("projection_not_recomputable") from exc
        if not projection_is_canonical:
            raise ValueError("projection_not_recomputable")

        try:
            statistics_packet = recompute_phase_statistics(self.turn_records)
            unload_leak = sum(
                max(0, metric.vram_after_unload_mib - metric.vram_before_mib)
                for metric in self.cycle_metrics
            )
            expected = {
                "phase": self.phase,
                "alias": FROZEN_ALIAS,
                "model_sha256": self.model_sha256,
                "corpus_sha256": self.corpus_sha256,
                "order_sha256": self.order_sha256,
                "sample_n": FROZEN_SAMPLE_N,
                "warmup_count": FROZEN_WARMUP_COUNT,
                "measured_sample_count": FROZEN_MEASURED_SAMPLE_COUNT,
                "load_cycles": FROZEN_LOAD_CYCLES,
                "cycles": [_cycle_packet(metric) for metric in self.cycle_metrics],
                "unload_leak_mib": float(unload_leak),
                "kernel_counters": self.kernel_counters.packet(),
                **statistics_packet,
            }
            matches = (
                _canonical_projection_json(expected) == self.summary_projection_json
            )
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("projection_not_recomputable") from exc
        if not matches:
            raise ValueError("projection_not_recomputable")

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "phase": self.phase,
                "outcome": self.outcome,
                "window_id": self.window_id,
                "boot_id": self.boot_id,
                "gpu_uuid": self.gpu_uuid,
                "topology_sha256": self.topology_sha256,
                "model_sha256": self.model_sha256,
                "corpus_sha256": self.corpus_sha256,
                "order_sha256": self.order_sha256,
                "effective_args_sha256": self.effective_args_sha256,
                "driver_package_sha256": self.driver_package_sha256,
                "authorization_preimage_sha256": self.authorization_preimage_sha256,
                "consumption_receipt_sha256": self.consumption_receipt_sha256,
                "static_preflight_sha256": self.static_preflight_sha256,
                "runtime_identity_sha256": self.runtime_identity_sha256,
                "turn_manifest_sha256": self.turn_manifest.binding_sha256,
                "turn_record_sha256s": [
                    record.binding_sha256 for record in self.turn_records
                ],
                "cycle_metrics": [
                    _cycle_packet(metric) for metric in self.cycle_metrics
                ],
                "cycle_witness_sha256s": [
                    witness.binding_sha256 for witness in self.cycle_witnesses
                ],
                "containment_before_sha256": self.containment_before_sha256,
                "containment_after_sha256": self.containment_after_sha256,
                "kernel_cursor_before": self.kernel_cursor_before,
                "kernel_cursor_after": self.kernel_cursor_after,
                "kernel_counters": self.kernel_counters.packet(),
                "summary_projection_json": self.summary_projection_json,
                "cycle_one_before_snapshot_at": self.cycle_one_before_snapshot_at,
                "timestamp": self.timestamp,
            }
        )


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
        if type(self.schema_version) is not str or self.schema_version != SCHEMA_VERSION:
            raise ValueError("schema_version_mismatch")
        if type(self.phase) is not str or self.phase not in {
            "vulkan_baseline",
            "cuda_candidate",
            "vulkan_rollback",
            "provisional_cuda_boot",
            "cold_boot",
            "provisional_live",
        }:
            raise ValueError("containment_phase")
        if type(self.boundary) is not str or self.boundary not in {"before", "after"}:
            raise ValueError("containment_phase")
        if any(
            type(value) is not str
            for value in (
                self.screen_flag_value,
                self.active_state,
                self.substate,
                self.enabled_state,
            )
        ):
            raise ValueError("containment_state")
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
class RollbackEvidenceBundle:
    witness: RollbackWitness
    maps_witness: RuntimeBackendWitness
    kernel_cursor_before: str
    kernel_cursor_after: str
    kernel_counters: KernelCounters
    containment_before: ContainmentSnapshot
    containment_after: ContainmentSnapshot
    producer: str
    window_id: str
    parent_control_packet_sha256: str
    parent_candidate_packet_sha256: str
    timestamp: str
    schema_version: str = field(default=ROLLBACK_EVIDENCE_BUNDLE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not str
            or self.schema_version != ROLLBACK_EVIDENCE_BUNDLE_SCHEMA
        ):
            raise ValueError("rollback_evidence_type")
        if (
            type(self.witness) is not RollbackWitness
            or type(self.maps_witness) is not RuntimeBackendWitness
            or type(self.kernel_counters) is not KernelCounters
            or type(self.containment_before) is not ContainmentSnapshot
            or type(self.containment_after) is not ContainmentSnapshot
        ):
            raise ValueError("rollback_evidence_type")
        if (
            type(self.kernel_cursor_before) is not str
            or not self.kernel_cursor_before
            or type(self.kernel_cursor_after) is not str
            or not self.kernel_cursor_after
            or self.kernel_cursor_before == self.kernel_cursor_after
        ):
            raise ValueError("kernel_window_invalid")
        if type(self.producer) is not str or self.producer != "owner_human":
            raise ValueError("rollback_producer")
        if (
            type(self.window_id) is not str
            or _WINDOW_ID_RE.fullmatch(self.window_id) is None
        ):
            raise ValueError("window_id_syntax")
        _validate_sha256(self.parent_control_packet_sha256)
        _validate_sha256(self.parent_candidate_packet_sha256)
        _validate_timestamp(self.timestamp)
        try:
            self.witness.__post_init__()
            self.maps_witness.__post_init__()
            self.kernel_counters.__post_init__()
            self.containment_before.__post_init__()
            self.containment_after.__post_init__()
            for binding in (
                self.witness.binding_sha256,
                self.maps_witness.binding_sha256,
                self.containment_before.binding_sha256,
                self.containment_after.binding_sha256,
            ):
                _validate_sha256(binding)
            _packet_hash(self.kernel_counters.packet())
        except (AttributeError, OverflowError, TypeError, ValueError) as exc:
            raise ValueError("rollback_evidence_type") from exc
        if self.maps_witness.phase != "vulkan_rollback":
            raise ValueError("backend_witness_phase")
        if (
            self.containment_before.phase != "vulkan_rollback"
            or self.containment_before.boundary != "before"
            or self.containment_after.phase != "vulkan_rollback"
            or self.containment_after.boundary != "after"
        ):
            raise ValueError("containment_phase")

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "witness_sha256": self.witness.binding_sha256,
                "maps_witness_sha256": self.maps_witness.binding_sha256,
                "kernel_cursor_before": self.kernel_cursor_before,
                "kernel_cursor_after": self.kernel_cursor_after,
                "kernel_counters": self.kernel_counters.packet(),
                "containment_before_sha256": (
                    self.containment_before.binding_sha256
                ),
                "containment_after_sha256": self.containment_after.binding_sha256,
                "producer": self.producer,
                "window_id": self.window_id,
                "parent_control_packet_sha256": (
                    self.parent_control_packet_sha256
                ),
                "parent_candidate_packet_sha256": (
                    self.parent_candidate_packet_sha256
                ),
                "timestamp": self.timestamp,
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
        return (
            _compare_utc_z(
                phase_snapshots["before"].timestamp,
                witness_timestamp,
            )
            < 0
            and _compare_utc_z(
                witness_timestamp,
                phase_snapshots["after"].timestamp,
            )
            < 0
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


def _canonical_wrapper_bytes(wrapper: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            wrapper,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _persisted_fields(fields: object, expected: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(fields, Mapping) or set(fields) != set(expected):
        raise ValueError("persisted_roundtrip")
    return dict(fields)


def _decode_containment_snapshot(fields: object) -> ContainmentSnapshot:
    values = _persisted_fields(
        fields,
        (
            "phase",
            "boundary",
            "timestamp",
            "screen_flag_value",
            "active_state",
            "substate",
            "enabled_state",
            "port_closed",
            "flag_source_sha256",
            "vision_unit_sha256",
            "artifact_sha256",
        ),
    )
    return ContainmentSnapshot(**values)


def _decode_runtime_identity(fields: object) -> RuntimeIdentity:
    values = _persisted_fields(
        fields,
        (
            "tag",
            "commit",
            "version",
            "alias",
            "model_sha256",
            "model_bytes",
            "runtime_sha256",
            "library_hashes",
            "effective_args",
            "mode",
            "production_override_sha256",
            "backend_environment",
            "runtime_manifest_sha256",
            "rollback_manifest_sha256",
            "cuda_toolkit",
            "cuda_compiler",
            "cmake_version",
            "driver_version",
            "gpu_identifier",
            "compute_capability",
            "backend",
        ),
    )
    effective_args = values["effective_args"]
    if not isinstance(effective_args, list):
        raise ValueError("persisted_roundtrip")
    values["effective_args"] = tuple(effective_args)
    for name in ("library_hashes", "backend_environment"):
        if not isinstance(values[name], Mapping):
            raise ValueError("persisted_roundtrip")
        values[name] = MappingProxyType(dict(values[name]))
    return RuntimeIdentity(**values)


def _decode_static_preflight(fields: object) -> StaticPreflightDoc:
    values = _persisted_fields(
        fields,
        (
            "gpu_uuid",
            "driver_package_sha256",
            "stub_sha256",
            "corpus_verified",
            "checks",
            "timestamp",
        ),
    )
    if not isinstance(values["checks"], Mapping):
        raise ValueError("persisted_roundtrip")
    values["checks"] = MappingProxyType(dict(values["checks"]))
    return StaticPreflightDoc(**values)


_KERNEL_COUNTER_FIELDS = (
    "reusemappingdb_map",
    "pmap_cb",
    "mmu_walk_map",
    "nv_err_no_memory",
    "xid",
    "unmatched_nvrm",
)


def _decode_kernel_counters(fields: object) -> KernelCounters:
    return KernelCounters(**_persisted_fields(fields, _KERNEL_COUNTER_FIELDS))


_ROLLBACK_WITNESS_FIELDS = (
    "unit_sha256",
    "dropin_sha256",
    "runtime_sha256",
    "model_sha256",
    "alias",
    "health_state",
    "mtp_initialized",
    "mtp_accepted_tokens",
    "restart_count",
    "kernel_counters",
    "bar1_percent",
    "vram_mib",
    "shared_library_manifest_sha256",
    "effective_args_sha256",
    "containment_artifact_sha256",
    "artifact_sha256",
    "timestamp",
)


def _decode_rollback_witness(fields: object) -> RollbackWitness:
    values = _persisted_fields(fields, _ROLLBACK_WITNESS_FIELDS)
    values["kernel_counters"] = _decode_kernel_counters(values["kernel_counters"])
    return RollbackWitness(**values)


_ROLLBACK_EVIDENCE_BUNDLE_FIELDS = (
    "witness",
    "maps_witness",
    "kernel_cursor_before",
    "kernel_cursor_after",
    "kernel_counters",
    "containment_before",
    "containment_after",
    "producer",
    "window_id",
    "parent_control_packet_sha256",
    "parent_candidate_packet_sha256",
    "timestamp",
)


def _decode_rollback_evidence_bundle(fields: object) -> RollbackEvidenceBundle:
    values = _persisted_fields(fields, _ROLLBACK_EVIDENCE_BUNDLE_FIELDS)
    values["witness"] = _decode_rollback_witness(values["witness"])
    values["maps_witness"] = _decode_backend_map_witness(values["maps_witness"])
    values["kernel_counters"] = _decode_kernel_counters(values["kernel_counters"])
    values["containment_before"] = _decode_containment_snapshot(
        values["containment_before"]
    )
    values["containment_after"] = _decode_containment_snapshot(
        values["containment_after"]
    )
    return RollbackEvidenceBundle(**values)


def _decode_cold_boot_witness(fields: object) -> ColdBootWitness:
    values = _persisted_fields(
        fields,
        (
            "parent_sha256",
            "artifact_sha256",
            "timestamp",
            "topology_sha256",
            "load_intervals",
            "steady_bar1_percent",
            "kernel_counters",
            "restart_count",
            "containment_artifact_sha256",
            "runtime_sha256",
            "runtime_maps_sha256",
            "backend",
            "production_override_sha256",
            "alias",
            "model_sha256",
            "model_bytes",
            "service_health",
            "mtp_initialized",
            "mtp_accepted_tokens",
        ),
    )
    intervals = values["load_intervals"]
    if not isinstance(intervals, list):
        raise ValueError("persisted_roundtrip")
    values["load_intervals"] = tuple(
        LoadInterval(
            **_persisted_fields(item, ("component", "started_at", "ended_at"))
        )
        for item in intervals
    )
    values["kernel_counters"] = _decode_kernel_counters(values["kernel_counters"])
    return ColdBootWitness(**values)


_LIVE_TURN_FIELDS = (
    "ordinal",
    "latency_ms",
    "false_absence_count",
    "wrong_answered_ungrounded_count",
    "type_regression_count",
    "recall_posture",
    "mtp_initialized",
    "mtp_accepted_tokens",
    "output_length",
    "artifact_sha256",
)


def _decode_provisional_live_witness(fields: object) -> ProvisionalLiveWitness:
    values = _persisted_fields(
        fields,
        (
            "parent_sha256",
            "artifact_sha256",
            "timestamp",
            "containment_artifact_sha256",
            "turns",
            "runtime_sha256",
            "runtime_maps_sha256",
            "backend",
            "configuration_sha256",
            "corpus_sha256",
            "order_sha256",
        ),
    )
    turns = values["turns"]
    if not isinstance(turns, list):
        raise ValueError("persisted_roundtrip")
    values["turns"] = tuple(
        LiveTurnWitness(**_persisted_fields(item, _LIVE_TURN_FIELDS)) for item in turns
    )
    return ProvisionalLiveWitness(**values)


def _decode_authorization_witness(fields: object) -> AuthorizationWitness:
    return AuthorizationWitness(
        **_persisted_fields(
            fields,
            ("phase", "status", "artifact_sha256", "parent_sha256", "timestamp"),
        )
    )


def _decode_backend_map_witness(fields: object) -> RuntimeBackendWitness:
    return RuntimeBackendWitness(
        **_persisted_fields(
            fields,
            ("backend", "maps_sha256", "phase", "timestamp", "release_root_sha256"),
        )
    )


_TURN_RECORD_FIELDS = (
    "cycle",
    "ordinal",
    "warmup",
    "artifact_sha256",
    "outcome",
    "e2e_ms",
    "ttft_ms",
    "prompt_per_second",
    "predicted_per_second",
    "draft_n",
    "draft_n_accepted",
)
_CYCLE_METRIC_FIELDS = (
    "cycle",
    "topology_sha256",
    "bar1_before_percent",
    "bar1_after_load_percent",
    "bar1_after_inference_percent",
    "bar1_after_unload_percent",
    "vram_before_mib",
    "vram_after_load_mib",
    "vram_after_inference_mib",
    "vram_after_unload_mib",
)
_PHASE_PACKET_FIELDS = (
    "phase",
    "outcome",
    "window_id",
    "boot_id",
    "gpu_uuid",
    "topology_sha256",
    "model_sha256",
    "corpus_sha256",
    "order_sha256",
    "effective_args_sha256",
    "driver_package_sha256",
    "authorization_preimage_sha256",
    "consumption_receipt_sha256",
    "static_preflight_sha256",
    "runtime_identity_sha256",
    "turn_manifest",
    "turn_records",
    "cycle_metrics",
    "cycle_witnesses",
    "containment_before_sha256",
    "containment_after_sha256",
    "kernel_cursor_before",
    "kernel_cursor_after",
    "kernel_counters",
    "summary_projection_json",
    "cycle_one_before_snapshot_at",
    "timestamp",
)


def _decode_turn_manifest(fields: object) -> TurnManifest:
    values = _persisted_fields(fields, ("phase", "entries"))
    entries = values["entries"]
    if not isinstance(entries, list):
        raise ValueError("persisted_roundtrip")
    rebuilt = []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 4:
            raise ValueError("persisted_roundtrip")
        rebuilt.append(TurnManifestEntry(*entry))
    return TurnManifest(phase=values["phase"], entries=tuple(rebuilt))


def _decode_cycle_backend_witness(fields: object) -> CycleBackendWitness:
    values = _persisted_fields(
        fields,
        ("witness", "cycle", "load_started", "unload_proven"),
    )
    values["witness"] = _decode_backend_map_witness(values["witness"])
    return CycleBackendWitness(**values)


def _decode_phase_packet(fields: object) -> PhasePacket:
    values = _persisted_fields(fields, _PHASE_PACKET_FIELDS)
    values["turn_manifest"] = _decode_turn_manifest(values["turn_manifest"])
    turn_records = values["turn_records"]
    cycle_metrics = values["cycle_metrics"]
    cycle_witnesses = values["cycle_witnesses"]
    if not all(
        isinstance(items, list)
        for items in (turn_records, cycle_metrics, cycle_witnesses)
    ):
        raise ValueError("persisted_roundtrip")
    values["turn_records"] = tuple(
        TurnRecord(**_persisted_fields(record, _TURN_RECORD_FIELDS))
        for record in turn_records
    )
    values["cycle_metrics"] = tuple(
        CycleMetrics(**_persisted_fields(metric, _CYCLE_METRIC_FIELDS))
        for metric in cycle_metrics
    )
    values["cycle_witnesses"] = tuple(
        _decode_cycle_backend_witness(witness) for witness in cycle_witnesses
    )
    values["kernel_counters"] = _decode_kernel_counters(values["kernel_counters"])
    return PhasePacket(**values)


_PERSISTED_REGISTRY: Mapping[str, object] = MappingProxyType(
    {
        CONTAINMENT_SNAPSHOT_SCHEMA: _decode_containment_snapshot,
        RUNTIME_IDENTITY_SCHEMA: _decode_runtime_identity,
        STATIC_PREFLIGHT_SCHEMA: _decode_static_preflight,
        PHASE_PACKET_SCHEMA: _decode_phase_packet,
        COLD_BOOT_WITNESS_SCHEMA: _decode_cold_boot_witness,
        PROVISIONAL_LIVE_WITNESS_SCHEMA: _decode_provisional_live_witness,
        AUTHORIZATION_WITNESS_SCHEMA: _decode_authorization_witness,
        BACKEND_MAP_WITNESS_SCHEMA: _decode_backend_map_witness,
        ROLLBACK_EVIDENCE_BUNDLE_SCHEMA: _decode_rollback_evidence_bundle,
    }
)


@dataclass(frozen=True, slots=True)
class PersistedDoc:
    wrapper_bytes: bytes
    _obj: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.wrapper_bytes, bytes):
            raise ValueError("persisted_wrapper_shape")
        try:
            wrapper = json.loads(self.wrapper_bytes)
        except (OverflowError, UnicodeDecodeError, ValueError) as exc:
            raise ValueError("persisted_wrapper_shape") from exc
        if not isinstance(wrapper, Mapping) or set(wrapper) != {
            "schema",
            "binding_sha256",
            "fields",
        }:
            raise ValueError("persisted_wrapper_shape")
        try:
            wrapper_is_canonical = (
                _canonical_wrapper_bytes(wrapper) == self.wrapper_bytes
            )
        except (OverflowError, TypeError, ValueError) as exc:
            raise ValueError("persisted_wrapper_shape") from exc
        if not wrapper_is_canonical:
            raise ValueError("noncanonical_wrapper")
        schema = wrapper["schema"]
        if not isinstance(schema, str) or schema not in _PERSISTED_REGISTRY:
            raise ValueError("persisted_schema_unknown")
        decoder = _PERSISTED_REGISTRY[schema]
        try:
            obj = decoder(wrapper["fields"])
            _validate_sha256(wrapper["binding_sha256"])
            if obj.binding_sha256 != wrapper["binding_sha256"]:
                raise ValueError("persisted_roundtrip")
        except (AttributeError, KeyError, OverflowError, TypeError, ValueError) as exc:
            raise ValueError("persisted_roundtrip") from exc
        object.__setattr__(self, "_obj", obj)

    @property
    def file_sha256(self) -> str:
        return hashlib.sha256(self.wrapper_bytes).hexdigest()

    @property
    def obj(self) -> object:
        return self._obj


def decode_persisted_packet(data: bytes) -> PhasePacket:
    persisted = PersistedDoc(data)
    if not isinstance(persisted.obj, PhasePacket):
        raise ValueError("persisted_packet_schema")
    return persisted.obj


_BENCH_IDENTITY_STABLE_FIELDS = (
    "tag",
    "commit",
    "version",
    "alias",
    "model_sha256",
    "model_bytes",
    "runtime_sha256",
    "library_hashes",
    "production_override_sha256",
    "backend_environment",
    "runtime_manifest_sha256",
    "rollback_manifest_sha256",
    "cuda_toolkit",
    "cuda_compiler",
    "cmake_version",
    "driver_version",
    "gpu_identifier",
    "compute_capability",
    "backend",
)
_BASE_CONTAINMENT_KEYS = frozenset(
    f"{phase}:{boundary}"
    for phase in ("vulkan_baseline", "cuda_candidate", "vulkan_rollback")
    for boundary in ("before", "after")
)
_AB_CONTAINMENT_DOC_KEYS = frozenset(
    f"{phase}:{boundary}"
    for phase in ("vulkan_baseline", "cuda_candidate")
    for boundary in ("before", "after")
)


def _revalidate_bundle_component(value: object, expected_type: type[object]) -> None:
    if type(value) is not expected_type:
        raise ValueError("bundle_binding")
    post_init = getattr(value, "__post_init__", None)
    if not callable(post_init):
        raise ValueError("bundle_binding")
    post_init()


def _require_exact_fields(
    value: object,
    names: tuple[str, ...],
    allowed_types: tuple[type[object], ...],
) -> None:
    if any(type(getattr(value, name)) not in allowed_types for name in names):
        raise ValueError("bundle_binding")


def _require_exact_string_mapping(value: object) -> None:
    if not isinstance(value, Mapping) or any(
        type(key) is not str or type(item) is not str for key, item in value.items()
    ):
        raise ValueError("bundle_binding")


def _require_exact_schema(value: object, expected: str) -> None:
    if type(getattr(value, "schema_version")) is not str or value.schema_version != expected:
        raise ValueError("bundle_binding")


def _canonical_persisted_role(
    value: object,
    expected_type: type[object],
) -> PersistedDoc:
    if type(value) is not PersistedDoc:
        raise ValueError("bundle_binding")
    canonical = PersistedDoc(value.wrapper_bytes)
    if type(canonical.obj) is not expected_type or type(value.obj) is not expected_type:
        raise ValueError("bundle_binding")
    if (
        canonical.file_sha256 != value.file_sha256
        or canonical.obj != value.obj
        or canonical.obj.binding_sha256 != value.obj.binding_sha256
    ):
        raise ValueError("bundle_binding")
    return canonical


def _normalized_bench_summary_packet(summary: BenchSummary) -> dict[str, object]:
    packet = _bench_packet(summary)
    packet["cold_boot_witness_sha256"] = None
    packet["provisional_live_witness_sha256"] = None
    return packet


@dataclass(frozen=True, slots=True)
class BenchEvidenceBundle:
    window_id: str
    boot_id: str
    gpu_uuid: str
    driver_package_sha256: str
    control_summary: BenchSummary
    candidate_summary: BenchSummary
    control_packet: PhasePacket
    candidate_packet: PhasePacket
    containment: ContainmentWitness
    boot_authorization: AuthorizationWitness
    live_authorization: AuthorizationWitness
    bench_runtime_identity: RuntimeIdentity
    runtime_identity: RuntimeIdentity
    quality: QualityEvidence
    owner_voice: OwnerVoiceReview
    window_authorization: WindowAuthorizationDoc
    continuation: ContinuationDoc
    window_consumption: ConsumptionReceipt
    continuation_consumption: ConsumptionReceipt
    containment_docs: Mapping[str, PersistedDoc]
    bench_identity_doc: PersistedDoc
    runtime_identity_doc: PersistedDoc
    static_preflight: PersistedDoc
    rollback: RollbackEvidenceBundle
    cold_boot_maps: RuntimeBackendWitness | None
    provisional_live_maps: RuntimeBackendWitness | None
    timestamp: str
    schema_version: str = field(default=BENCH_EVIDENCE_BUNDLE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        try:
            self._validate_exact_components()
            docs = self._validate_persisted_documents()
            object.__setattr__(self, "containment_docs", MappingProxyType(docs))
            self._validate_base_joins(docs)
            self._validate_stage_prefix()
            _validate_utc_z_timestamp(self.timestamp)
            _validate_sha256(self.bench_binding_sha256)
            _validate_sha256(self.binding_sha256)
        except Exception as exc:
            raise ValueError("bundle_binding") from exc

    def _validate_exact_components(self) -> None:
        if type(self.schema_version) is not str or self.schema_version != BENCH_EVIDENCE_BUNDLE_SCHEMA:
            raise ValueError("bundle_binding")
        if type(self.window_id) is not str or _WINDOW_ID_RE.fullmatch(self.window_id) is None:
            raise ValueError("bundle_binding")
        if type(self.boot_id) is not str or not self.boot_id:
            raise ValueError("bundle_binding")
        if type(self.gpu_uuid) is not str or _GPU_UUID_RE.fullmatch(self.gpu_uuid) is None:
            raise ValueError("bundle_binding")
        _validate_sha256(self.driver_package_sha256)

        for value, expected in (
            (self.control_summary, BenchSummary),
            (self.candidate_summary, BenchSummary),
            (self.control_packet, PhasePacket),
            (self.candidate_packet, PhasePacket),
            (self.containment, ContainmentWitness),
            (self.boot_authorization, AuthorizationWitness),
            (self.live_authorization, AuthorizationWitness),
            (self.bench_runtime_identity, RuntimeIdentity),
            (self.runtime_identity, RuntimeIdentity),
            (self.quality, QualityEvidence),
            (self.owner_voice, OwnerVoiceReview),
            (self.window_authorization, WindowAuthorizationDoc),
            (self.continuation, ContinuationDoc),
            (self.window_consumption, ConsumptionReceipt),
            (self.continuation_consumption, ConsumptionReceipt),
            (self.rollback, RollbackEvidenceBundle),
        ):
            _revalidate_bundle_component(value, expected)
        for value in (self.cold_boot_maps, self.provisional_live_maps):
            if value is not None:
                _revalidate_bundle_component(value, RuntimeBackendWitness)
        self._validate_exact_builtin_shapes()
        self._validate_schema_versions()

        for summary in (self.control_summary, self.candidate_summary):
            if (
                type(summary.owner_voice_evidence) is not PhaseEvidence
                or type(summary.kernel_counters) is not KernelCounters
                or type(summary.rollback_witness) is not RollbackWitness
                or type(summary.cycles) is not tuple
                or any(type(cycle) is not CycleMetrics for cycle in summary.cycles)
                or (
                    summary.cold_boot_witness is not None
                    and type(summary.cold_boot_witness) is not ColdBootWitness
                )
                or (
                    summary.provisional_live_witness is not None
                    and type(summary.provisional_live_witness) is not ProvisionalLiveWitness
                )
            ):
                raise ValueError("bundle_binding")
            summary.owner_voice_evidence.__post_init__()
            summary.kernel_counters.__post_init__()
            summary.rollback_witness.__post_init__()
            for cycle in summary.cycles:
                cycle.__post_init__()
            if summary.cold_boot_witness is not None:
                summary.cold_boot_witness.__post_init__()
                summary.cold_boot_witness.kernel_counters.__post_init__()
            if summary.provisional_live_witness is not None:
                if type(summary.provisional_live_witness.turns) is not tuple or any(
                    type(turn) is not LiveTurnWitness
                    for turn in summary.provisional_live_witness.turns
                ):
                    raise ValueError("bundle_binding")
                summary.provisional_live_witness.__post_init__()
                for turn in summary.provisional_live_witness.turns:
                    turn.__post_init__()

        for packet in (self.control_packet, self.candidate_packet):
            if (
                type(packet.turn_manifest) is not TurnManifest
                or type(packet.turn_manifest.entries) is not tuple
                or any(
                    type(entry) is not TurnManifestEntry
                    for entry in packet.turn_manifest.entries
                )
                or type(packet.turn_records) is not tuple
                or any(type(record) is not TurnRecord for record in packet.turn_records)
                or type(packet.cycle_metrics) is not tuple
                or any(type(metric) is not CycleMetrics for metric in packet.cycle_metrics)
                or type(packet.cycle_witnesses) is not tuple
                or any(type(item) is not CycleBackendWitness for item in packet.cycle_witnesses)
                or any(
                    type(item.witness) is not RuntimeBackendWitness
                    for item in packet.cycle_witnesses
                )
                or type(packet.kernel_counters) is not KernelCounters
            ):
                raise ValueError("bundle_binding")
            packet.turn_manifest.__post_init__()
            for entry in packet.turn_manifest.entries:
                entry.__post_init__()
            for record in packet.turn_records:
                record.__post_init__()
            for metric in packet.cycle_metrics:
                metric.__post_init__()
            for item in packet.cycle_witnesses:
                item.witness.__post_init__()
                item.__post_init__()
            packet.kernel_counters.__post_init__()

        if type(self.containment.snapshots) is not tuple:
            raise ValueError("bundle_binding")
        for snapshot in self.containment.snapshots:
            _revalidate_bundle_component(snapshot, ContainmentSnapshot)
        rollback = self.rollback
        if (
            type(rollback.witness) is not RollbackWitness
            or type(rollback.maps_witness) is not RuntimeBackendWitness
            or type(rollback.kernel_counters) is not KernelCounters
            or type(rollback.containment_before) is not ContainmentSnapshot
            or type(rollback.containment_after) is not ContainmentSnapshot
        ):
            raise ValueError("bundle_binding")

    def _validate_schema_versions(self) -> None:
        """Pin every schema-bearing object crossing the public bundle boundary."""

        expected: list[tuple[object, str]] = [
            (self, BENCH_EVIDENCE_BUNDLE_SCHEMA),
            (self.quality, QUALITY_EVIDENCE_SCHEMA),
            (self.owner_voice, OWNER_VOICE_REVIEW_SCHEMA),
            (self.window_authorization, WINDOW_AUTHORIZATION_SCHEMA),
            (self.continuation, CONTINUATION_SCHEMA),
            (self.window_consumption, CONSUMPTION_RECEIPT_SCHEMA),
            (self.continuation_consumption, CONSUMPTION_RECEIPT_SCHEMA),
            (self.control_summary, SCHEMA_VERSION),
            (self.candidate_summary, SCHEMA_VERSION),
            (self.control_packet, PHASE_PACKET_SCHEMA),
            (self.candidate_packet, PHASE_PACKET_SCHEMA),
            (self.containment, SCHEMA_VERSION),
            (self.boot_authorization, SCHEMA_VERSION),
            (self.live_authorization, SCHEMA_VERSION),
            (self.bench_runtime_identity, SCHEMA_VERSION),
            (self.runtime_identity, SCHEMA_VERSION),
            (self.rollback, ROLLBACK_EVIDENCE_BUNDLE_SCHEMA),
            (self.rollback.witness, SCHEMA_VERSION),
            (self.rollback.maps_witness, SCHEMA_VERSION),
            (self.rollback.kernel_counters, SCHEMA_VERSION),
            (self.rollback.containment_before, SCHEMA_VERSION),
            (self.rollback.containment_after, SCHEMA_VERSION),
        ]
        for summary in (self.control_summary, self.candidate_summary):
            expected.extend(
                (
                    (summary.owner_voice_evidence, SCHEMA_VERSION),
                    (summary.kernel_counters, SCHEMA_VERSION),
                    (summary.rollback_witness, SCHEMA_VERSION),
                    (summary.rollback_witness.kernel_counters, SCHEMA_VERSION),
                )
            )
            expected.extend((cycle, SCHEMA_VERSION) for cycle in summary.cycles)
            if summary.cold_boot_witness is not None:
                expected.extend(
                    (
                        (summary.cold_boot_witness, SCHEMA_VERSION),
                        (summary.cold_boot_witness.kernel_counters, SCHEMA_VERSION),
                    )
                )
            if summary.provisional_live_witness is not None:
                expected.append((summary.provisional_live_witness, SCHEMA_VERSION))
        for packet in (self.control_packet, self.candidate_packet):
            expected.extend(
                (
                    (packet.turn_manifest, TURN_MANIFEST_SCHEMA),
                    (packet.kernel_counters, SCHEMA_VERSION),
                )
            )
            expected.extend((metric, SCHEMA_VERSION) for metric in packet.cycle_metrics)
            for witness in packet.cycle_witnesses:
                expected.extend(
                    (
                        (witness, CYCLE_BACKEND_WITNESS_SCHEMA),
                        (witness.witness, SCHEMA_VERSION),
                    )
                )
        expected.extend(
            (snapshot, SCHEMA_VERSION) for snapshot in self.containment.snapshots
        )
        for value in (self.cold_boot_maps, self.provisional_live_maps):
            if value is not None:
                expected.append((value, SCHEMA_VERSION))
        expected.extend(
            (
                (
                    _canonical_persisted_role(
                        self.bench_identity_doc, RuntimeIdentity
                    ).obj,
                    SCHEMA_VERSION,
                ),
                (
                    _canonical_persisted_role(
                        self.runtime_identity_doc, RuntimeIdentity
                    ).obj,
                    SCHEMA_VERSION,
                ),
                (
                    _canonical_persisted_role(
                        self.static_preflight, StaticPreflightDoc
                    ).obj,
                    STATIC_PREFLIGHT_SCHEMA,
                ),
            )
        )
        expected.extend(
            (
                _canonical_persisted_role(doc, ContainmentSnapshot).obj,
                SCHEMA_VERSION,
            )
            for doc in self.containment_docs.values()
        )
        for value, schema in expected:
            _require_exact_schema(value, schema)

    def _validate_exact_builtin_shapes(self) -> None:
        _require_exact_fields(
            self.quality,
            (
                "evaluator_version",
                "control_manifest_sha256",
                "candidate_manifest_sha256",
                "recall_posture",
                "timestamp",
                "schema_version",
            ),
            (str,),
        )
        _require_exact_fields(
            self.quality,
            (
                "false_absence_count",
                "wrong_answered_ungrounded_count",
                "type_regression_count",
                "quality_failure_count",
                "covered_turn_count",
            ),
            (int,),
        )
        _require_exact_fields(
            self.owner_voice,
            (
                "producer",
                "status",
                "evaluator_version",
                "control_manifest_sha256",
                "candidate_manifest_sha256",
                "artifact_sha256",
                "timestamp",
                "schema_version",
            ),
            (str,),
        )
        for authorization in (self.boot_authorization, self.live_authorization):
            _require_exact_fields(
                authorization,
                ("phase", "status", "schema_version"),
                (str,),
            )
            for name in ("artifact_sha256", "parent_sha256", "timestamp"):
                if type(getattr(authorization, name)) not in (str, type(None)):
                    raise ValueError("bundle_binding")
        for document in (self.window_authorization, self.continuation):
            _require_exact_fields(
                document,
                (
                    "window_id",
                    "boot_id",
                    "nonce",
                    "issued_at",
                    "expires_at",
                    "owner",
                    "schema_version",
                ),
                (str,),
            )
            if type(document.phases) is not tuple or any(
                type(phase) is not str for phase in document.phases
            ):
                raise ValueError("bundle_binding")
        _require_exact_fields(
            self.continuation, ("parent_vulkan_packet_sha256",), (str,)
        )
        for receipt in (self.window_consumption, self.continuation_consumption):
            _require_exact_fields(
                receipt,
                ("nonce", "phase", "boot_id", "timestamp", "schema_version"),
                (str,),
            )

        for identity in (self.bench_runtime_identity, self.runtime_identity):
            _require_exact_fields(
                identity,
                (
                    "tag",
                    "commit",
                    "alias",
                    "model_sha256",
                    "runtime_sha256",
                    "mode",
                    "production_override_sha256",
                    "runtime_manifest_sha256",
                    "rollback_manifest_sha256",
                    "cuda_toolkit",
                    "cuda_compiler",
                    "cmake_version",
                    "driver_version",
                    "gpu_identifier",
                    "compute_capability",
                    "backend",
                    "schema_version",
                ),
                (str,),
            )
            _require_exact_fields(identity, ("version", "model_bytes"), (int,))
            if type(identity.effective_args) is not tuple or any(
                type(argument) is not str for argument in identity.effective_args
            ):
                raise ValueError("bundle_binding")
            _require_exact_string_mapping(identity.library_hashes)
            _require_exact_string_mapping(identity.backend_environment)

        for packet in (self.control_packet, self.candidate_packet):
            _require_exact_fields(
                packet,
                (
                    "phase",
                    "outcome",
                    "window_id",
                    "boot_id",
                    "gpu_uuid",
                    "topology_sha256",
                    "model_sha256",
                    "corpus_sha256",
                    "order_sha256",
                    "effective_args_sha256",
                    "driver_package_sha256",
                    "authorization_preimage_sha256",
                    "consumption_receipt_sha256",
                    "static_preflight_sha256",
                    "runtime_identity_sha256",
                    "containment_before_sha256",
                    "containment_after_sha256",
                    "kernel_cursor_before",
                    "kernel_cursor_after",
                    "summary_projection_json",
                    "cycle_one_before_snapshot_at",
                    "timestamp",
                    "schema_version",
                ),
                (str,),
            )
            _require_exact_fields(
                packet.turn_manifest, ("phase", "schema_version"), (str,)
            )
            for entry in packet.turn_manifest.entries:
                _require_exact_fields(entry, ("cycle", "ordinal"), (int,))
                _require_exact_fields(entry, ("warmup",), (bool,))
                _require_exact_fields(entry, ("artifact_sha256",), (str,))
            for record in packet.turn_records:
                _require_exact_fields(record, ("cycle", "ordinal"), (int,))
                _require_exact_fields(record, ("warmup",), (bool,))
                _require_exact_fields(
                    record, ("artifact_sha256", "outcome"), (str,)
                )
                _require_exact_fields(
                    record,
                    (
                        "e2e_ms",
                        "ttft_ms",
                        "prompt_per_second",
                        "predicted_per_second",
                    ),
                    (float,),
                )
                for name in ("draft_n", "draft_n_accepted"):
                    if type(getattr(record, name)) not in (int, type(None)):
                        raise ValueError("bundle_binding")
            for metric in packet.cycle_metrics:
                _require_exact_fields(metric, ("cycle",), (int,))
                _require_exact_fields(metric, ("topology_sha256",), (str,))
                _require_exact_fields(
                    metric,
                    (
                        "bar1_before_percent",
                        "bar1_after_load_percent",
                        "bar1_after_inference_percent",
                        "bar1_after_unload_percent",
                    ),
                    (int, float),
                )
                _require_exact_fields(
                    metric,
                    (
                        "vram_before_mib",
                        "vram_after_load_mib",
                        "vram_after_inference_mib",
                        "vram_after_unload_mib",
                    ),
                    (int,),
                )
            for witness in packet.cycle_witnesses:
                _require_exact_fields(witness, ("cycle",), (int,))
                _require_exact_fields(
                    witness,
                    ("load_started", "unload_proven", "schema_version"),
                    (str,),
                )
                _require_exact_fields(
                    witness.witness,
                    (
                        "backend",
                        "maps_sha256",
                        "phase",
                        "timestamp",
                        "release_root_sha256",
                        "schema_version",
                    ),
                    (str,),
                )

        for summary in (self.control_summary, self.candidate_summary):
            _require_exact_fields(
                summary,
                (
                    "phase",
                    "alias",
                    "model_sha256",
                    "corpus_sha256",
                    "order_sha256",
                    "recall_posture",
                    "schema_version",
                ),
                (str,),
            )
            _require_exact_fields(
                summary,
                (
                    "sample_n",
                    "warmup_count",
                    "measured_sample_count",
                    "load_cycles",
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
                ),
                (int,),
            )
            _require_exact_fields(
                summary,
                (
                    "seven_turn_max_ms",
                    "p95_e2e_ms",
                    "median_decode_tps",
                    "median_prefill_tps",
                    "unload_leak_mib",
                ),
                (float,),
            )
            _require_exact_fields(summary, ("mtp_initialized",), (bool,))
            evidence = summary.owner_voice_evidence
            _require_exact_fields(
                evidence,
                ("phase", "status", "schema_version"),
                (str,),
            )
            for name in ("artifact_sha256", "timestamp"):
                if type(getattr(evidence, name)) not in (str, type(None)):
                    raise ValueError("bundle_binding")
            if summary.cold_boot_witness is not None:
                cold = summary.cold_boot_witness
                if type(cold.kernel_counters) is not KernelCounters:
                    raise ValueError("bundle_binding")
                _require_exact_fields(
                    cold,
                    (
                        "parent_sha256",
                        "artifact_sha256",
                        "timestamp",
                        "topology_sha256",
                        "containment_artifact_sha256",
                        "runtime_sha256",
                        "runtime_maps_sha256",
                        "backend",
                        "production_override_sha256",
                        "alias",
                        "model_sha256",
                        "service_health",
                        "schema_version",
                    ),
                    (str,),
                )
                _require_exact_fields(
                    cold,
                    ("model_bytes", "restart_count", "mtp_accepted_tokens"),
                    (int,),
                )
                _require_exact_fields(cold, ("steady_bar1_percent",), (float,))
                _require_exact_fields(cold, ("mtp_initialized",), (bool,))
                if type(cold.load_intervals) is not tuple:
                    raise ValueError("bundle_binding")
                for interval in cold.load_intervals:
                    if type(interval) is not LoadInterval:
                        raise ValueError("bundle_binding")
                    _require_exact_fields(
                        interval, ("component", "started_at", "ended_at"), (str,)
                    )
            if summary.provisional_live_witness is not None:
                live = summary.provisional_live_witness
                _require_exact_fields(
                    live,
                    (
                        "parent_sha256",
                        "artifact_sha256",
                        "timestamp",
                        "containment_artifact_sha256",
                        "runtime_sha256",
                        "runtime_maps_sha256",
                        "backend",
                        "configuration_sha256",
                        "corpus_sha256",
                        "order_sha256",
                        "schema_version",
                    ),
                    (str,),
                )
                if type(live.turns) is not tuple:
                    raise ValueError("bundle_binding")
                for turn in live.turns:
                    if type(turn) is not LiveTurnWitness:
                        raise ValueError("bundle_binding")
                    _require_exact_fields(
                        turn,
                        (
                            "ordinal",
                            "false_absence_count",
                            "wrong_answered_ungrounded_count",
                            "type_regression_count",
                            "mtp_accepted_tokens",
                            "output_length",
                        ),
                        (int,),
                    )
                    _require_exact_fields(turn, ("latency_ms",), (float,))
                    _require_exact_fields(
                        turn, ("recall_posture", "artifact_sha256"), (str,)
                    )
                    _require_exact_fields(turn, ("mtp_initialized",), (bool,))

        kernel_counters = [
            self.control_summary.kernel_counters,
            self.candidate_summary.kernel_counters,
            self.control_summary.rollback_witness.kernel_counters,
            self.candidate_summary.rollback_witness.kernel_counters,
            self.control_packet.kernel_counters,
            self.candidate_packet.kernel_counters,
            self.rollback.witness.kernel_counters,
            self.rollback.kernel_counters,
        ]
        kernel_counters.extend(
            summary.cold_boot_witness.kernel_counters
            for summary in (self.control_summary, self.candidate_summary)
            if summary.cold_boot_witness is not None
        )
        for counters in kernel_counters:
            _require_exact_fields(
                counters,
                _KERNEL_COUNTER_FIELDS,
                (int,),
            )
            _require_exact_fields(counters, ("schema_version",), (str,))

        backend_witnesses = [
            self.rollback.maps_witness,
            *(
                witness.witness
                for packet in (self.control_packet, self.candidate_packet)
                for witness in packet.cycle_witnesses
            ),
        ]
        backend_witnesses.extend(
            value
            for value in (self.cold_boot_maps, self.provisional_live_maps)
            if value is not None
        )
        for witness in backend_witnesses:
            _require_exact_fields(
                witness,
                (
                    "backend",
                    "maps_sha256",
                    "phase",
                    "timestamp",
                    "release_root_sha256",
                    "schema_version",
                ),
                (str,),
            )

        for snapshot in (
            *self.containment.snapshots,
            self.rollback.containment_before,
            self.rollback.containment_after,
        ):
            _require_exact_fields(
                snapshot,
                (
                    "phase",
                    "boundary",
                    "timestamp",
                    "screen_flag_value",
                    "active_state",
                    "substate",
                    "enabled_state",
                    "flag_source_sha256",
                    "vision_unit_sha256",
                    "artifact_sha256",
                    "schema_version",
                ),
                (str,),
            )
            _require_exact_fields(snapshot, ("port_closed",), (bool,))

        for witness in (
            self.control_summary.rollback_witness,
            self.candidate_summary.rollback_witness,
            self.rollback.witness,
        ):
            _require_exact_fields(
                witness,
                (
                    "unit_sha256",
                    "dropin_sha256",
                    "runtime_sha256",
                    "model_sha256",
                    "alias",
                    "health_state",
                    "shared_library_manifest_sha256",
                    "effective_args_sha256",
                    "containment_artifact_sha256",
                    "artifact_sha256",
                    "timestamp",
                    "schema_version",
                ),
                (str,),
            )
            _require_exact_fields(
                witness,
                ("mtp_accepted_tokens", "restart_count"),
                (int,),
            )
            _require_exact_fields(witness, ("mtp_initialized",), (bool,))
            _require_exact_fields(witness, ("bar1_percent", "vram_mib"), (float,))

        _require_exact_fields(
            self.rollback,
            (
                "kernel_cursor_before",
                "kernel_cursor_after",
                "producer",
                "window_id",
                "parent_control_packet_sha256",
                "parent_candidate_packet_sha256",
                "timestamp",
                "schema_version",
            ),
            (str,),
        )
        preflight = _canonical_persisted_role(
            self.static_preflight, StaticPreflightDoc
        ).obj
        _require_exact_fields(
            preflight,
            (
                "gpu_uuid",
                "driver_package_sha256",
                "stub_sha256",
                "timestamp",
                "schema_version",
            ),
            (str,),
        )
        _require_exact_fields(preflight, ("corpus_verified",), (bool,))
        _require_exact_string_mapping(preflight.checks)

    def _validate_persisted_documents(self) -> dict[str, PersistedDoc]:
        if not isinstance(self.containment_docs, Mapping):
            raise ValueError("bundle_binding")
        docs = dict(self.containment_docs)
        if any(type(key) is not str for key in docs) or set(docs) != _AB_CONTAINMENT_DOC_KEYS:
            raise ValueError("bundle_binding")
        for key, doc in tuple(docs.items()):
            canonical = _canonical_persisted_role(doc, ContainmentSnapshot)
            expected_phase, expected_boundary = key.split(":", 1)
            if (
                canonical.obj.phase != expected_phase
                or canonical.obj.boundary != expected_boundary
            ):
                raise ValueError("bundle_binding")
            docs[key] = canonical
        _canonical_persisted_role(self.bench_identity_doc, RuntimeIdentity)
        _canonical_persisted_role(self.runtime_identity_doc, RuntimeIdentity)
        _canonical_persisted_role(self.static_preflight, StaticPreflightDoc)
        return docs

    def _validate_base_joins(self, docs: Mapping[str, PersistedDoc]) -> None:
        control = self.control_packet
        candidate = self.candidate_packet
        if (
            control.phase != "vulkan_baseline"
            or self.control_summary.phase != "vulkan_baseline"
            or candidate.phase != "cuda_candidate"
            or self.candidate_summary.phase != "cuda_candidate"
            or control.outcome != "completed"
            or candidate.outcome != "completed"
        ):
            raise ValueError("bundle_binding")
        for packet in (control, candidate):
            if (
                packet.window_id != self.window_id
                or packet.boot_id != self.boot_id
                or packet.gpu_uuid != self.gpu_uuid
                or packet.driver_package_sha256 != self.driver_package_sha256
            ):
                raise ValueError("bundle_binding")
        if self.rollback.window_id != self.window_id:
            raise ValueError("bundle_binding")

        if (
            control.authorization_preimage_sha256
            != self.window_authorization.preimage_sha256
            or candidate.authorization_preimage_sha256
            != self.continuation.preimage_sha256
            or control.consumption_receipt_sha256
            != self.window_consumption.binding_sha256
            or candidate.consumption_receipt_sha256
            != self.continuation_consumption.binding_sha256
            or self.window_consumption.nonce != self.window_authorization.nonce
            or self.continuation_consumption.nonce != self.continuation.nonce
            or self.window_authorization.nonce == self.continuation.nonce
            or self.continuation.parent_vulkan_packet_sha256 != control.binding_sha256
            or self.window_authorization.window_id != self.window_id
            or self.continuation.window_id != self.window_id
            or self.window_authorization.boot_id != self.boot_id
            or self.continuation.boot_id != self.boot_id
            or "vulkan_baseline" not in self.window_authorization.phases
            or "cuda_candidate" not in self.continuation.phases
            or self.window_authorization.owner != self.continuation.owner
            or self.boot_authorization.phase != "boot_authorization"
            or self.live_authorization.phase != "live_witness_authorization"
            or self.window_consumption.phase != "vulkan_baseline"
            or self.continuation_consumption.phase != "cuda_candidate"
            or self.window_consumption.boot_id != self.boot_id
            or self.continuation_consumption.boot_id != self.boot_id
        ):
            raise ValueError("bundle_binding")
        if not (
            _compare_utc_z(
                self.window_authorization.issued_at,
                self.window_consumption.timestamp,
            )
            <= 0
            and _compare_utc_z(
                self.window_consumption.timestamp,
                self.window_authorization.expires_at,
            )
            < 0
            and _compare_utc_z(
                self.continuation.issued_at,
                self.continuation_consumption.timestamp,
            )
            <= 0
            and _compare_utc_z(
                self.continuation_consumption.timestamp,
                self.continuation.expires_at,
            )
            < 0
            and _compare_utc_z(
                self.continuation_consumption.timestamp,
                self.window_authorization.expires_at,
            )
            < 0
        ):
            raise ValueError("bundle_binding")

        citation_pairs = (
            (control.containment_before_sha256, docs["vulkan_baseline:before"]),
            (control.containment_after_sha256, docs["vulkan_baseline:after"]),
            (candidate.containment_before_sha256, docs["cuda_candidate:before"]),
            (candidate.containment_after_sha256, docs["cuda_candidate:after"]),
        )
        if any(citation != doc.file_sha256 for citation, doc in citation_pairs):
            raise ValueError("bundle_binding")
        phase_objects = {
            key: value for key, value in self.containment.phase_hashes.items()
        }
        if any(
            phase_objects.get(key) != doc.obj.binding_sha256
            for key, doc in docs.items()
        ):
            raise ValueError("bundle_binding")
        if (
            phase_objects.get("vulkan_rollback:before")
            != self.rollback.containment_before.binding_sha256
            or phase_objects.get("vulkan_rollback:after")
            != self.rollback.containment_after.binding_sha256
        ):
            raise ValueError("bundle_binding")

        bench_doc = _canonical_persisted_role(
            self.bench_identity_doc, RuntimeIdentity
        )
        runtime_doc = _canonical_persisted_role(
            self.runtime_identity_doc, RuntimeIdentity
        )
        static_doc = _canonical_persisted_role(
            self.static_preflight, StaticPreflightDoc
        )
        if (
            self.bench_runtime_identity.mode != "bench"
            or control.runtime_identity_sha256 != bench_doc.file_sha256
            or candidate.runtime_identity_sha256 != bench_doc.file_sha256
            or bench_doc.obj.binding_sha256
            != self.bench_runtime_identity.binding_sha256
            or bench_doc.obj != self.bench_runtime_identity
            or runtime_doc.obj.binding_sha256 != self.runtime_identity.binding_sha256
            or runtime_doc.obj != self.runtime_identity
        ):
            raise ValueError("bundle_binding")
        for name in _BENCH_IDENTITY_STABLE_FIELDS:
            left = getattr(self.bench_runtime_identity, name)
            right = getattr(self.runtime_identity, name)
            if isinstance(left, Mapping):
                if dict(left) != dict(right):
                    raise ValueError("bundle_binding")
            elif left != right:
                raise ValueError("bundle_binding")

        preflight = static_doc.obj
        if (
            control.static_preflight_sha256 != static_doc.file_sha256
            or candidate.static_preflight_sha256 != static_doc.file_sha256
            or preflight.gpu_uuid != self.gpu_uuid
            or preflight.driver_package_sha256 != self.driver_package_sha256
            or preflight.checks["corpus"] != control.corpus_sha256
            or preflight.checks["corpus"] != candidate.corpus_sha256
            or preflight.checks["model"] != control.model_sha256
            or preflight.checks["model"] != candidate.model_sha256
            or preflight.checks["candidate_manifest"]
            != self.bench_runtime_identity.runtime_manifest_sha256
            or control.effective_args_sha256 != FROZEN_BENCH_ARGS_SHA256
            or candidate.effective_args_sha256 != FROZEN_BENCH_ARGS_SHA256
        ):
            raise ValueError("bundle_binding")
        if any(
            snapshot.flag_source_sha256 != preflight.checks["flag_source"]
            or snapshot.vision_unit_sha256 != preflight.checks["vision_unit"]
            for snapshot in self.containment.snapshots
        ):
            raise ValueError("bundle_binding")

        self._validate_packet_summary(control, self.control_summary)
        self._validate_packet_summary(candidate, self.candidate_summary)
        if (
            self.quality.control_manifest_sha256
            != control.turn_manifest.binding_sha256
            or self.quality.candidate_manifest_sha256
            != candidate.turn_manifest.binding_sha256
            or self.owner_voice.control_manifest_sha256
            != control.turn_manifest.binding_sha256
            or self.owner_voice.candidate_manifest_sha256
            != candidate.turn_manifest.binding_sha256
        ):
            raise ValueError("bundle_binding")
        for summary in (self.control_summary, self.candidate_summary):
            if any(
                getattr(summary, name) != getattr(self.quality, name)
                for name in (
                    "false_absence_count",
                    "wrong_answered_ungrounded_count",
                    "type_regression_count",
                    "recall_posture",
                    "quality_failure_count",
                )
            ):
                raise ValueError("bundle_binding")
            if (
                summary.owner_voice_evidence.artifact_sha256
                != self.owner_voice.artifact_sha256
                or summary.owner_voice_evidence.status != self.owner_voice.status
                or summary.owner_voice_evidence.timestamp != self.owner_voice.timestamp
            ):
                raise ValueError("bundle_binding")

        if (
            self.rollback.parent_control_packet_sha256 != control.binding_sha256
            or self.rollback.parent_candidate_packet_sha256
            != candidate.binding_sha256
            or self.rollback.witness.binding_sha256
            != self.control_summary.rollback_witness.binding_sha256
            or self.rollback.witness.binding_sha256
            != self.candidate_summary.rollback_witness.binding_sha256
            or self.rollback.kernel_counters != self.rollback.witness.kernel_counters
            or self.rollback.witness.containment_artifact_sha256
            != self.containment.phase_binding("vulkan_rollback")
        ):
            raise ValueError("bundle_binding")
        if not (
            _compare_utc_z(
                self.rollback.containment_before.timestamp,
                self.rollback.maps_witness.timestamp,
            )
            < 0
            and _compare_utc_z(
                self.rollback.maps_witness.timestamp,
                self.rollback.containment_after.timestamp,
            )
            < 0
            and _compare_utc_z(
                self.rollback.containment_before.timestamp,
                self.rollback.witness.timestamp,
            )
            < 0
            and _compare_utc_z(
                self.rollback.witness.timestamp,
                self.rollback.containment_after.timestamp,
            )
            < 0
        ):
            raise ValueError("bundle_binding")
        self._validate_phase_chronology(control, docs)
        self._validate_phase_chronology(candidate, docs)
        if not (
            _compare_utc_z(control.timestamp, self.continuation.issued_at) <= 0
            and _compare_utc_z(
                control.timestamp,
                docs["cuda_candidate:before"].obj.timestamp,
            )
            <= 0
        ):
            raise ValueError("bundle_binding")

    def _validate_packet_summary(
        self,
        packet: PhasePacket,
        summary: BenchSummary,
    ) -> None:
        if packet.summary_projection_json != _canonical_projection_json(
            phase_summary_projection(summary)
        ):
            raise ValueError("bundle_binding")
        statistics_packet = recompute_phase_statistics(packet.turn_records)
        unload_leak = float(
            sum(
                max(0, metric.vram_after_unload_mib - metric.vram_before_mib)
                for metric in packet.cycle_metrics
            )
        )
        if (
            summary.cycles != packet.cycle_metrics
            or summary.unload_leak_mib != unload_leak
            or summary.crash_count != statistics_packet["crash_count"]
            or summary.restart_count != 0
            or summary.hang_count != statistics_packet["hang_count"]
            or summary.timeout_count != statistics_packet["timeout_count"]
            or packet.model_sha256 != summary.model_sha256
            or packet.corpus_sha256 != summary.corpus_sha256
            or packet.order_sha256 != summary.order_sha256
            or any(
                packet.topology_sha256 != cycle.topology_sha256
                for cycle in summary.cycles
            )
            or packet.kernel_counters != summary.kernel_counters
        ):
            raise ValueError("bundle_binding")

    def _validate_phase_chronology(
        self,
        packet: PhasePacket,
        docs: Mapping[str, PersistedDoc],
    ) -> None:
        before = docs[f"{packet.phase}:before"].obj
        after = docs[f"{packet.phase}:after"].obj
        receipt = (
            self.window_consumption
            if packet.phase == "vulkan_baseline"
            else self.continuation_consumption
        )
        intervals = packet.cycle_witnesses
        if not (
            _compare_utc_z(before.timestamp, packet.cycle_one_before_snapshot_at)
            <= 0
            and _compare_utc_z(
                packet.cycle_one_before_snapshot_at, receipt.timestamp
            )
            < 0
            and _compare_utc_z(receipt.timestamp, intervals[0].load_started) < 0
        ):
            raise ValueError("bundle_binding")
        previous_unload: str | None = None
        for interval in intervals:
            if (
                _compare_utc_z(before.timestamp, interval.load_started) > 0
                or _compare_utc_z(interval.load_started, interval.unload_proven) >= 0
                or _compare_utc_z(
                    interval.load_started, interval.witness.timestamp
                )
                >= 0
                or _compare_utc_z(
                    interval.witness.timestamp, interval.unload_proven
                )
                >= 0
                or _compare_utc_z(interval.unload_proven, after.timestamp) > 0
                or (
                    previous_unload is not None
                    and _compare_utc_z(previous_unload, interval.load_started) > 0
                )
            ):
                raise ValueError("bundle_binding")
            previous_unload = interval.unload_proven
        if not (
            _compare_utc_z(intervals[2].unload_proven, after.timestamp) <= 0
            and _compare_utc_z(after.timestamp, packet.timestamp) <= 0
        ):
            raise ValueError("bundle_binding")

    def _validate_stage_prefix(self) -> None:
        snapshots = {
            f"{snapshot.phase}:{snapshot.boundary}" for snapshot in self.containment.snapshots
        }
        cold = self.candidate_summary.cold_boot_witness
        provisional = self.candidate_summary.provisional_live_witness
        if (
            self.control_summary.cold_boot_witness is not None
            or self.control_summary.provisional_live_witness is not None
        ):
            raise ValueError("bundle_binding")

        boot_status = self.boot_authorization.status
        live_status = self.live_authorization.status
        if boot_status == "not_attempted":
            stage = 1
        elif cold is None:
            stage = 2
        elif live_status == "not_attempted":
            stage = 3
        elif provisional is None:
            stage = 4
        else:
            stage = 5

        expected_snapshots = set(_BASE_CONTAINMENT_KEYS)
        if stage >= 3:
            expected_snapshots.update(
                f"{phase}:{boundary}"
                for phase in ("provisional_cuda_boot", "cold_boot")
                for boundary in ("before", "after")
            )
        if stage >= 5:
            expected_snapshots.update(
                f"provisional_live:{boundary}" for boundary in ("before", "after")
            )
        if snapshots != expected_snapshots:
            raise ValueError("bundle_binding")

        if stage == 1:
            if (
                self.runtime_identity.mode != "bench"
                or live_status != "not_attempted"
                or cold is not None
                or provisional is not None
                or self.cold_boot_maps is not None
                or self.provisional_live_maps is not None
            ):
                raise ValueError("bundle_binding")
            return
        if self.runtime_identity.mode != "production" or boot_status not in {"pass", "fail"}:
            raise ValueError("bundle_binding")
        self._validate_boot_authorization()
        if stage == 2:
            if (
                live_status != "not_attempted"
                or cold is not None
                or provisional is not None
                or self.cold_boot_maps is not None
                or self.provisional_live_maps is not None
            ):
                raise ValueError("bundle_binding")
            return
        if boot_status != "pass" or cold is None or self.cold_boot_maps is None:
            raise ValueError("bundle_binding")
        self._validate_cold_stage(cold)
        if stage == 3:
            if (
                live_status != "not_attempted"
                or provisional is not None
                or self.provisional_live_maps is not None
            ):
                raise ValueError("bundle_binding")
            return
        if not cold.passed or live_status not in {"pass", "fail"}:
            raise ValueError("bundle_binding")
        if (
            self.live_authorization.parent_sha256 != cold.binding_sha256
            or _compare_utc_z(cold.timestamp, self.live_authorization.timestamp) >= 0
        ):
            raise ValueError("bundle_binding")
        if stage == 4:
            if provisional is not None or self.provisional_live_maps is not None:
                raise ValueError("bundle_binding")
            return
        if (
            live_status != "pass"
            or provisional is None
            or self.provisional_live_maps is None
        ):
            raise ValueError("bundle_binding")
        self._validate_provisional_stage(provisional)

    def _validate_boot_authorization(self) -> None:
        if self.boot_authorization.parent_sha256 != self.bench_binding_sha256:
            raise ValueError("bundle_binding")
        static_doc = _canonical_persisted_role(
            self.static_preflight, StaticPreflightDoc
        ).obj
        latest = [
            self.control_packet.timestamp,
            self.candidate_packet.timestamp,
            self.quality.timestamp,
            self.owner_voice.timestamp,
            self.rollback.timestamp,
            self.rollback.witness.timestamp,
            self.rollback.maps_witness.timestamp,
            static_doc.timestamp,
            *(snapshot.timestamp for snapshot in self.containment.snapshots if f"{snapshot.phase}:{snapshot.boundary}" in _BASE_CONTAINMENT_KEYS),
        ]
        if any(
            _compare_utc_z(timestamp, self.boot_authorization.timestamp) >= 0
            for timestamp in latest
        ):
            raise ValueError("bundle_binding")

    def _validate_cold_stage(self, cold: ColdBootWitness) -> None:
        maps = self.cold_boot_maps
        if maps is None:
            raise ValueError("bundle_binding")
        if (
            maps.phase != "cold_boot"
            or cold.parent_sha256 != self.boot_authorization.binding_sha256
            or _compare_utc_z(self.boot_authorization.timestamp, cold.timestamp) >= 0
            or cold.containment_artifact_sha256
            != self.containment.phase_binding("cold_boot")
            or cold.runtime_sha256 != self.runtime_identity.runtime_sha256
            or cold.runtime_maps_sha256 != maps.binding_sha256
            or cold.backend != maps.backend
            or cold.production_override_sha256
            != self.runtime_identity.production_override_sha256
            or cold.alias != self.runtime_identity.alias
            or cold.model_sha256 != self.runtime_identity.model_sha256
            or cold.model_bytes != self.runtime_identity.model_bytes
            or not _containment_brackets_exact(
                self.containment, "cold_boot", maps.timestamp
            )
            or not _containment_brackets_exact(
                self.containment, "cold_boot", cold.timestamp
            )
        ):
            raise ValueError("bundle_binding")

    def _validate_provisional_stage(self, live: ProvisionalLiveWitness) -> None:
        maps = self.provisional_live_maps
        if maps is None:
            raise ValueError("bundle_binding")
        if (
            maps.phase != "provisional_live"
            or live.parent_sha256 != self.live_authorization.binding_sha256
            or _compare_utc_z(self.live_authorization.timestamp, live.timestamp) >= 0
            or live.containment_artifact_sha256
            != self.containment.phase_binding("provisional_live")
            or live.runtime_sha256 != self.runtime_identity.runtime_sha256
            or live.runtime_maps_sha256 != maps.binding_sha256
            or live.backend != maps.backend
            or live.configuration_sha256 != self.runtime_identity.configuration_sha256
            or not _containment_brackets_exact(
                self.containment, "provisional_live", maps.timestamp
            )
            or not _containment_brackets_exact(
                self.containment, "provisional_live", live.timestamp
            )
        ):
            raise ValueError("bundle_binding")

    @property
    def bench_binding_sha256(self) -> str:
        base_phase_hashes = {
            key: value
            for key, value in self.containment.phase_hashes.items()
            if key in _BASE_CONTAINMENT_KEYS
        }
        return _packet_hash(
            {
                "schema": self.schema_version,
                "window_id": self.window_id,
                "boot_id": self.boot_id,
                "gpu_uuid": self.gpu_uuid,
                "driver_package_sha256": self.driver_package_sha256,
                "bench_runtime_identity_sha256": (
                    self.bench_runtime_identity.binding_sha256
                ),
                "control_packet_sha256": self.control_packet.binding_sha256,
                "candidate_packet_sha256": self.candidate_packet.binding_sha256,
                "control_summary": _normalized_bench_summary_packet(
                    self.control_summary
                ),
                "candidate_summary": _normalized_bench_summary_packet(
                    self.candidate_summary
                ),
                "containment_phase_hashes": base_phase_hashes,
                "quality_sha256": self.quality.binding_sha256,
                "owner_voice_sha256": self.owner_voice.binding_sha256,
                "window_authorization_preimage_sha256": (
                    self.window_authorization.preimage_sha256
                ),
                "continuation_preimage_sha256": self.continuation.preimage_sha256,
                "window_consumption_sha256": self.window_consumption.binding_sha256,
                "continuation_consumption_sha256": (
                    self.continuation_consumption.binding_sha256
                ),
                "rollback_sha256": self.rollback.binding_sha256,
            }
        )

    @property
    def binding_sha256(self) -> str:
        return _packet_hash(
            {
                "schema": self.schema_version,
                "bench_binding_sha256": self.bench_binding_sha256,
                "window_id": self.window_id,
                "boot_id": self.boot_id,
                "gpu_uuid": self.gpu_uuid,
                "driver_package_sha256": self.driver_package_sha256,
                "control_summary_sha256": self.control_summary.binding_sha256,
                "candidate_summary_sha256": self.candidate_summary.binding_sha256,
                "control_packet_sha256": self.control_packet.binding_sha256,
                "candidate_packet_sha256": self.candidate_packet.binding_sha256,
                "containment_sha256": self.containment.binding_sha256,
                "boot_authorization_sha256": self.boot_authorization.binding_sha256,
                "live_authorization_sha256": self.live_authorization.binding_sha256,
                "bench_runtime_identity_sha256": (
                    self.bench_runtime_identity.binding_sha256
                ),
                "runtime_identity_sha256": self.runtime_identity.binding_sha256,
                "quality_sha256": self.quality.binding_sha256,
                "owner_voice_sha256": self.owner_voice.binding_sha256,
                "window_authorization_preimage_sha256": (
                    self.window_authorization.preimage_sha256
                ),
                "continuation_preimage_sha256": self.continuation.preimage_sha256,
                "window_consumption_sha256": self.window_consumption.binding_sha256,
                "continuation_consumption_sha256": (
                    self.continuation_consumption.binding_sha256
                ),
                "containment_doc_file_sha256s": {
                    key: value.file_sha256
                    for key, value in sorted(self.containment_docs.items())
                },
                "bench_identity_file_sha256": self.bench_identity_doc.file_sha256,
                "runtime_identity_file_sha256": self.runtime_identity_doc.file_sha256,
                "static_preflight_file_sha256": self.static_preflight.file_sha256,
                "rollback_sha256": self.rollback.binding_sha256,
                "cold_boot_maps_sha256": (
                    self.cold_boot_maps.binding_sha256
                    if self.cold_boot_maps is not None
                    else None
                ),
                "provisional_live_maps_sha256": (
                    self.provisional_live_maps.binding_sha256
                    if self.provisional_live_maps is not None
                    else None
                ),
                "timestamp": self.timestamp,
            }
        )


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
        if type(self.schema_version) is not str or self.schema_version != SCHEMA_VERSION:
            raise ValueError("verdict_binding")
        if type(self.decision) is not str or self.decision not in _DECISIONS:
            raise ValueError("closed_decision")
        if type(self.reasons) is not tuple or any(
            type(reason) is not str or reason not in _REASONS for reason in self.reasons
        ):
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
    expected_bench_evidence_sha256: str,
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
    _validate_sha256(expected_bench_evidence_sha256)
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
        bench_evidence_sha256=expected_bench_evidence_sha256,
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


def _evaluate_promotion_gate(
    control: BenchSummary,
    candidate: BenchSummary,
    control_maps: RuntimeBackendWitness,
    candidate_maps: RuntimeBackendWitness,
    containment: ContainmentWitness,
    boot_authorization: AuthorizationWitness,
    live_authorization: AuthorizationWitness,
    runtime_identity: RuntimeIdentity,
    *,
    expected_bench_evidence_sha256: str,
    cold_boot_maps: RuntimeBackendWitness | None = None,
    provisional_live_maps: RuntimeBackendWitness | None = None,
) -> PromotionVerdict:
    """Apply the closed v1.1 gate without performing or authorizing cutover."""

    _validate_sha256(expected_bench_evidence_sha256)
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
        or not _containment_brackets_exact(
            containment,
            "vulkan_rollback",
            candidate.rollback_witness.timestamp,
        )
    ):
        reasons.append("rollback_drill_failed")
    if not _containment_brackets_exact(
        containment, "vulkan_baseline", control_maps.timestamp
    ):
        reasons.append("containment_incomplete")
    if not _containment_brackets_exact(
        containment, "cuda_candidate", candidate_maps.timestamp
    ):
        reasons.append("containment_incomplete")
    if not containment.clean:
        reasons.append("containment_failed")

    if reasons:
        return _make_verdict(
            expected_bench_evidence_sha256,
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
    if boot_authorization.status == "fail":
        return _make_verdict(
            expected_bench_evidence_sha256,
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
                expected_bench_evidence_sha256,
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
            expected_bench_evidence_sha256,
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
    bench_timestamps = [
        control_maps.timestamp,
        candidate_maps.timestamp,
        *(
            item.timestamp
            for item in containment.snapshots
            if item.phase in base_phases
        ),
        candidate.rollback_witness.timestamp,
    ]
    latest_bench_time = bench_timestamps[0]
    for timestamp in bench_timestamps[1:]:
        if _compare_utc_z(timestamp, latest_bench_time) > 0:
            latest_bench_time = timestamp
    if (
        boot_authorization.parent_sha256 != expected_bench_evidence_sha256
        or _compare_utc_z(boot_authorization.timestamp, latest_bench_time) <= 0
    ):
        return _make_verdict(
            expected_bench_evidence_sha256,
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
                expected_bench_evidence_sha256,
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
            expected_bench_evidence_sha256,
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
        or _compare_utc_z(cold.timestamp, boot_authorization.timestamp) <= 0
        or not containment.complete_for({"provisional_cuda_boot", "cold_boot"})
        or cold.containment_artifact_sha256 != containment.phase_binding("cold_boot")
        or not _containment_brackets_exact(containment, "cold_boot", cold.timestamp)
        or not _containment_brackets_exact(
            containment, "cold_boot", cold_boot_maps.timestamp
        )
        or cold.runtime_sha256 != runtime_identity.runtime_sha256
        or cold.runtime_maps_sha256 != cold_boot_maps.binding_sha256
        or cold.backend != cold_boot_maps.backend
        or cold.production_override_sha256 != runtime_identity.production_override_sha256
        or cold.alias != runtime_identity.alias
        or cold.model_sha256 != runtime_identity.model_sha256
        or cold.model_bytes != runtime_identity.model_bytes
    ):
        return _make_verdict(
            expected_bench_evidence_sha256,
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
            expected_bench_evidence_sha256,
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
            expected_bench_evidence_sha256,
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
            expected_bench_evidence_sha256,
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
    if live_authorization.parent_sha256 != cold.binding_sha256 or _compare_utc_z(
        live_authorization.timestamp, cold.timestamp
    ) <= 0:
        return _make_verdict(
            expected_bench_evidence_sha256,
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
                expected_bench_evidence_sha256,
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
            expected_bench_evidence_sha256,
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
        or _compare_utc_z(live.timestamp, live_authorization.timestamp) <= 0
        or not containment.complete_for({"provisional_live"})
        or live.containment_artifact_sha256 != containment.phase_binding("provisional_live")
        or not _containment_brackets_exact(
            containment, "provisional_live", live.timestamp
        )
        or not _containment_brackets_exact(
            containment,
            "provisional_live",
            provisional_live_maps.timestamp,
        )
        or live.runtime_sha256 != runtime_identity.runtime_sha256
        or live.runtime_maps_sha256 != provisional_live_maps.binding_sha256
        or live.backend != provisional_live_maps.backend
        or live.configuration_sha256 != runtime_identity.configuration_sha256
    ):
        return _make_verdict(
            expected_bench_evidence_sha256,
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
            expected_bench_evidence_sha256,
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
        expected_bench_evidence_sha256,
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


def evaluate_promotion_bundle(bundle: BenchEvidenceBundle) -> PromotionVerdict:
    """Evaluate one complete, joined evidence bundle through the closed gate."""

    if type(bundle) is not BenchEvidenceBundle:
        raise ValueError("bundle_binding")
    try:
        BenchEvidenceBundle.__post_init__(bundle)
        selected: list[RuntimeBackendWitness] = []
        for packet in (bundle.control_packet, bundle.candidate_packet):
            cycle_one: list[RuntimeBackendWitness] = []
            for item in packet.cycle_witnesses:
                if type(item) is not CycleBackendWitness:
                    raise ValueError("bundle_binding")
                if type(item.witness) is not RuntimeBackendWitness:
                    raise ValueError("bundle_binding")
                RuntimeBackendWitness.__post_init__(item.witness)
                CycleBackendWitness.__post_init__(item)
                if type(item.cycle) is int and item.cycle == 1:
                    cycle_one.append(item.witness)
            if len(cycle_one) != 1:
                raise ValueError("bundle_binding")
            selected.append(cycle_one[0])
        control_maps, candidate_maps = selected
    except Exception as exc:
        raise ValueError("bundle_binding") from exc
    return _evaluate_promotion_gate(
        bundle.control_summary,
        bundle.candidate_summary,
        control_maps,
        candidate_maps,
        bundle.containment,
        bundle.boot_authorization,
        bundle.live_authorization,
        bundle.runtime_identity,
        expected_bench_evidence_sha256=bundle.bench_binding_sha256,
        cold_boot_maps=bundle.cold_boot_maps,
        provisional_live_maps=bundle.provisional_live_maps,
    )


def _packet_hash(value: object) -> str:
    packet = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packet.encode("utf-8")).hexdigest()


def _timestamp_value(timestamp: str) -> datetime:
    if type(timestamp) is not str:
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


def _promotion_verdict_packet(verdict: PromotionVerdict) -> dict[str, object]:
    return {
        "schema_version": verdict.schema_version,
        "decision": verdict.decision,
        "reasons": list(verdict.reasons),
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
    }


def build_receipt(
    bundle: BenchEvidenceBundle,
    verdict: PromotionVerdict,
    *,
    timestamp: str,
) -> dict[str, object]:
    """Serialize content-light producer evidence, never an admission decision."""

    _validate_timestamp(timestamp)
    expected = evaluate_promotion_bundle(bundle)
    if type(verdict) is not PromotionVerdict:
        raise ValueError("verdict_binding_mismatch")
    try:
        PromotionVerdict.__post_init__(verdict)
    except Exception as exc:
        raise ValueError("verdict_binding_mismatch") from exc
    if _promotion_verdict_packet(expected) != _promotion_verdict_packet(verdict):
        raise ValueError("verdict_binding_mismatch")
    verdict = expected

    identity = bundle.runtime_identity
    candidate = bundle.candidate_summary
    control_maps = next(
        item.witness for item in bundle.control_packet.cycle_witnesses if item.cycle == 1
    )
    candidate_maps = next(
        item.witness
        for item in bundle.candidate_packet.cycle_witnesses
        if item.cycle == 1
    )
    containment = bundle.containment
    boot_authorization = bundle.boot_authorization
    live_authorization = bundle.live_authorization
    cold_boot_maps = bundle.cold_boot_maps
    provisional_live_maps = bundle.provisional_live_maps
    if candidate.alias != identity.alias or candidate.model_sha256 != identity.model_sha256:
        raise ValueError("receipt_identity_mismatch")
    if not receipt_mode_allows(identity, decision=verdict.decision):
        raise ValueError("receipt_mode_mismatch")
    receipt: dict[str, object] = {
        "schema": SCHEMA_VERSION,
        "timestamp": timestamp,
        "bench_binding_sha256": bundle.bench_binding_sha256,
        "bundle_binding_sha256": bundle.binding_sha256,
        "evaluator_versions": {
            "quality": bundle.quality.evaluator_version,
            "owner_voice": bundle.owner_voice.evaluator_version,
        },
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
