"""Sealed command and terminal boundary for the private CUDA bench."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import FrameType
from types import MappingProxyType
from typing import Literal, Never, Protocol

from scripts import cuda_bench_assemble as assemble
from scripts import cuda_bench_driver as driver
from scripts import cuda_migration as cm


PUBLIC_COMMANDS = (
    "static-preflight",
    "rehearse",
    "vulkan-baseline",
    "cuda-candidate",
    "assemble-stage1",
)
_TERMINAL_SCHEMA_MATRIX = MappingProxyType(
    {
        "static-preflight": cm.COMMAND_COMPLETION_SCHEMA,
        "rehearse": driver.REHEARSAL_PACKET_SCHEMA,
        "vulkan-baseline": cm.COMMAND_COMPLETION_SCHEMA,
        "cuda-candidate": cm.COMMAND_COMPLETION_SCHEMA,
        "assemble-stage1": driver.ASSEMBLE_RECEIPT_SCHEMA,
    }
)
_ASSEMBLY_RECEIPT_FIELDS = frozenset(
    {
        "timestamp",
        "bench_binding_sha256",
        "bundle_binding_sha256",
        "evaluator_versions",
        "phase",
        "artifact_role",
        "decision",
        "reasons",
        "runtime",
        "backend_witnesses",
        "measurements",
        "phase_evidence",
        "containment",
        "gate_bindings",
    }
)
_ASSEMBLY_GATE_FIELDS = frozenset(
    {
        "control_summary_sha256",
        "candidate_summary_sha256",
        "control_maps_sha256",
        "candidate_maps_sha256",
        "containment_sha256",
        "boot_authorization_sha256",
        "live_authorization_sha256",
        "bench_evidence_sha256",
        "runtime_identity_sha256",
        "cold_boot_maps_sha256",
        "provisional_live_maps_sha256",
    }
)
_ASSEMBLY_RUNTIME_FIELDS = frozenset(
    {
        "tag",
        "commit",
        "version",
        "backend",
        "runtime_sha256",
        "runtime_manifest_sha256",
        "library_manifest_sha256",
        "configuration_sha256",
        "mode",
        "production_override_sha256",
        "backend_environment_sha256",
        "model_sha256",
        "model_bytes",
        "alias",
        "cuda_toolkit",
        "cuda_compiler",
        "cmake_version",
        "driver_version",
        "gpu_identifier",
        "compute_capability",
        "rollback_manifest_sha256",
    }
)
_ASSEMBLY_BACKEND_FIELDS = frozenset(
    {
        "control_maps_sha256",
        "candidate_maps_sha256",
        "control_binding_sha256",
        "candidate_binding_sha256",
        "cold_boot_maps_sha256",
        "cold_boot_binding_sha256",
        "provisional_live_maps_sha256",
        "provisional_live_binding_sha256",
    }
)
_ASSEMBLY_MEASUREMENT_FIELDS = frozenset(
    {
        "sample_n",
        "warmup_count",
        "measured_sample_count",
        "load_cycles",
        "corpus_sha256",
        "order_sha256",
        "seven_turn_max_ms",
        "p95_e2e_ms",
        "median_decode_tps",
        "median_prefill_tps",
        "steady_bar1_percent",
        "topology_sha256",
        "cycles",
        "mtp_drafted_tokens",
        "mtp_accepted_tokens",
        "mtp_rejected_tokens",
        "mtp_initialized",
        "false_absence_count",
        "wrong_answered_ungrounded_count",
        "type_regression_count",
        "recall_posture",
        "quality_failure_count",
        "kernel_counters",
        "crash_count",
        "restart_count",
        "hang_count",
        "timeout_count",
        "unload_leak_mib",
    }
)
_ASSEMBLY_CYCLE_FIELDS = frozenset(
    {
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
        "unload_wait_seconds",
    }
)
_ASSEMBLY_PHASE_EVIDENCE_FIELDS = frozenset(
    {
        "owner_voice_sha256",
        "rollback_sha256",
        "cold_boot_sha256",
        "provisional_live_sha256",
        "boot_authorization_sha256",
        "live_authorization_sha256",
        "provisional_live_output_lengths",
    }
)
_ASSEMBLY_CONTAINMENT_FIELDS = frozenset({"clean", "phase_hashes"})
_ASSEMBLY_CONTAINMENT_PHASES = frozenset(
    {
        "vulkan_baseline:before",
        "vulkan_baseline:after",
        "cuda_candidate:before",
        "cuda_candidate:after",
        "vulkan_rollback:before",
        "vulkan_rollback:after",
    }
)
_WATCHED_SIGNALS = frozenset({signal.SIGINT, signal.SIGTERM})
_CLI_RESERVED_OUTCOMES = frozenset({"cleanup_incomplete", "interrupted"})
_pthread_sigmask = signal.pthread_sigmask
_terminal_committed = False
_cleanup_incomplete_committing = False
_linearized_durable_success: _DurableSuccessLatch | None = None
_STATIC_READ_BYTE_CAP = 32 * 1024 * 1024 * 1024
_STATIC_COMMAND_TIMEOUT_S = 30
REHEARSAL_READINESS_TIMEOUT_S = 1.0
REHEARSAL_REQUEST_TIMEOUT_MS = 1_000
_REHEARSAL_PERSONAS = (
    "crash",
    "healthy",
    "malformed_response",
    "midturn_hang",
    "readiness_timeout",
    "wrong_identity",
)
_REHEARSAL_PROMPTS = (
    "sentinel-alpha",
    "sentinel-bravo",
    "sentinel-charlie",
    "sentinel-delta",
    "sentinel-echo",
    "sentinel-foxtrot",
    "sentinel-golf",
)
FROZEN_BENCH_ARGV_TAIL = (
    "-m",
    cm.FROZEN_MODEL_PATH,
    "--alias",
    cm.FROZEN_ALIAS,
    "--host",
    "127.0.0.1",
    "--port",
    "18080",
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
_FROZEN_BENCH_ARGV_SHA256 = hashlib.sha256(
    json.dumps(
        list(FROZEN_BENCH_ARGV_TAIL),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
).hexdigest()
if _FROZEN_BENCH_ARGV_SHA256 != cm.FROZEN_BENCH_ARGS_SHA256:
    raise RuntimeError("frozen_bench_argv_mismatch")
_PACKAGE_MEMBERS = (
    "scripts/cuda_migration.py",
    "scripts/cuda_bench_driver.py",
    "scripts/cuda_bench_stub.py",
    "scripts/cuda_bench_cli.py",
    "scripts/cuda_bench_assemble.py",
)


@dataclass(frozen=True, slots=True)
class StaticAssetPaths:
    unit: Path
    dropin: Path
    vulkan_root: Path
    candidate_root: Path
    model: Path
    cuda_override: Path
    nvcc: Path
    cmake: Path
    nvidia_smi: Path
    flag_source: Path
    vision_unit: Path
    stub: Path


CANONICAL_STATIC_ASSETS = StaticAssetPaths(
    unit=Path("/home/rohit/.config/systemd/user/llama-server.service"),
    dropin=Path(
        "/home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf"
    ),
    vulkan_root=cm.VULKAN_RELEASE_ROOT,
    candidate_root=cm.CUDA_RELEASE_ROOT,
    model=Path(cm.FROZEN_MODEL_PATH),
    cuda_override=Path(
        "/home/rohit/maez/config/systemd/llama-server-b9596-cuda.override.conf"
    ),
    nvcc=Path("/usr/local/cuda-13.2/bin/nvcc"),
    cmake=Path("/usr/bin/cmake"),
    nvidia_smi=Path("/usr/bin/nvidia-smi"),
    flag_source=driver.SCREEN_FLAG_SOURCE_PATH,
    vision_unit=driver.VISION_UNIT_PATH,
    stub=Path("/home/rohit/maez/scripts/cuda_bench_stub.py"),
)


@dataclass(frozen=True, slots=True)
class StaticObservation:
    static_doc: cm.StaticPreflightDoc
    runtime_identity: cm.RuntimeIdentity
    rollback_preimage: bytes
    vulkan_release_proof: driver.ReleaseDirectoryProof
    cuda_release_proof: driver.ReleaseDirectoryProof


class ReadOnlyRunner(Protocol):
    def __call__(
        self, argv: tuple[str, ...], *, timeout_s: int
    ) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True, slots=True)
class _CandidateObservation:
    runtime_sha256: str
    runtime_manifest_sha256: str
    library_hashes: Mapping[str, str]
    release_proof: driver.ReleaseDirectoryProof


@dataclass(frozen=True, slots=True)
class _HostObservation:
    gpu_uuid: str
    driver_version: str
    gpu_identifier: str
    compute_capability: str
    cuda_compiler: str
    cmake_version: str


@dataclass(frozen=True, slots=True)
class _AssetObservation:
    unit_sha256: str
    dropin_sha256: str
    vulkan_runtime_sha256: str
    vulkan_library_manifest_sha256: str
    model_sha256: str
    model_bytes: int
    override_sha256: str
    flag_source_sha256: str
    vision_unit_sha256: str
    stub_sha256: str
    vulkan_release_proof: driver.ReleaseDirectoryProof


_StaticIdentity = tuple[int, int, int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class _StaticRegularRecord:
    sha256: str
    size: int
    identity: _StaticIdentity


@dataclass(frozen=True, slots=True)
class _StaticSymlinkRecord:
    target: str
    identity: _StaticIdentity


def _static_identity(value: os.stat_result) -> _StaticIdentity:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _named_static_identity_at(directory_fd: int, name: str) -> _StaticIdentity:
    try:
        return _static_identity(
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        )
    except OSError:
        raise driver.BenchRefusal("identity_mismatch") from None


def _stable_regular_file(path: Path) -> tuple[str, int]:
    """Hash one named regular file without following a final symlink."""

    fd: int | None = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        os.set_inheritable(fd, False)
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_nlink < 1
            or before.st_size < 0
            or before.st_size > _STATIC_READ_BYTE_CAP
        ):
            raise driver.BenchRefusal("identity_mismatch")
        digest = hashlib.sha256()
        observed = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > _STATIC_READ_BYTE_CAP:
                raise driver.BenchRefusal("identity_mismatch")
            digest.update(chunk)
        after = os.fstat(fd)
        identity = lambda value: (
            value.st_dev,
            value.st_ino,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )
        named = os.stat(path, follow_symlinks=False)
        if (
            observed != before.st_size
            or identity(before) != identity(after)
            or not stat.S_ISREG(named.st_mode)
            or (after.st_dev, after.st_ino) != (named.st_dev, named.st_ino)
        ):
            raise driver.BenchRefusal("identity_mismatch")
        return digest.hexdigest(), observed
    except driver.BenchRefusal:
        raise
    except (OSError, TypeError, ValueError):
        raise driver.BenchRefusal("identity_mismatch") from None
    finally:
        if fd is not None:
            os.close(fd)


def _stable_regular_record_at(
    directory_fd: int, name: str
) -> _StaticRegularRecord:
    fd: int | None = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        os.set_inheritable(fd, False)
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_nlink < 1
            or before.st_size > _STATIC_READ_BYTE_CAP
        ):
            raise driver.BenchRefusal("identity_mismatch")
        digest = hashlib.sha256()
        observed = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            digest.update(chunk)
        after = os.fstat(fd)
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            observed != before.st_size
            or _static_identity(before) != _static_identity(after)
            or not stat.S_ISREG(named.st_mode)
            or _static_identity(after) != _static_identity(named)
        ):
            raise driver.BenchRefusal("identity_mismatch")
        return _StaticRegularRecord(
            digest.hexdigest(), observed, _static_identity(after)
        )
    except driver.BenchRefusal:
        raise
    except (OSError, TypeError, ValueError):
        raise driver.BenchRefusal("identity_mismatch") from None
    finally:
        if fd is not None:
            os.close(fd)


def _stable_regular_at(directory_fd: int, name: str) -> tuple[str, int]:
    record = _stable_regular_record_at(directory_fd, name)
    return record.sha256, record.size


def _stable_bytes_at(
    directory_fd: int, name: str, *, byte_cap: int
) -> tuple[bytes, str]:
    fd: int | None = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_nlink < 1
            or before.st_size > byte_cap
        ):
            raise driver.BenchRefusal("identity_mismatch")
        payload = bytearray()
        while len(payload) <= byte_cap:
            chunk = os.read(fd, min(1024 * 1024, byte_cap + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        after = os.fstat(fd)
        named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        stable = lambda value: (
            value.st_dev,
            value.st_ino,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )
        if (
            len(payload) != before.st_size
            or len(payload) > byte_cap
            or stable(before) != stable(after)
            or not stat.S_ISREG(named.st_mode)
            or (after.st_dev, after.st_ino) != (named.st_dev, named.st_ino)
        ):
            raise driver.BenchRefusal("identity_mismatch")
        data = bytes(payload)
        return data, hashlib.sha256(data).hexdigest()
    except driver.BenchRefusal:
        raise
    except (OSError, TypeError, ValueError):
        raise driver.BenchRefusal("identity_mismatch") from None
    finally:
        if fd is not None:
            os.close(fd)


def _stable_symlink_record_at(
    directory_fd: int, name: str
) -> _StaticSymlinkRecord:
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISLNK(before.st_mode) or before.st_uid != os.geteuid():
            raise driver.BenchRefusal("identity_mismatch")
        target = os.readlink(name, dir_fd=directory_fd)
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if _static_identity(before) != _static_identity(after):
            raise driver.BenchRefusal("identity_mismatch")
        return _StaticSymlinkRecord(target, _static_identity(after))
    except driver.BenchRefusal:
        raise
    except (OSError, TypeError, ValueError):
        raise driver.BenchRefusal("identity_mismatch") from None


def _stable_symlink_at(directory_fd: int, name: str) -> str:
    return _stable_symlink_record_at(directory_fd, name).target


def _require_static_directory_bound(directory_fd: int, path: Path) -> None:
    try:
        held = os.fstat(directory_fd)
        named = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISDIR(held.st_mode)
            or held.st_uid != os.geteuid()
            or not stat.S_ISDIR(named.st_mode)
            or _static_identity(held) != _static_identity(named)
        ):
            raise driver.BenchRefusal("identity_mismatch")
    except driver.BenchRefusal:
        raise
    except OSError:
        raise driver.BenchRefusal("identity_mismatch") from None


def _open_static_directory(path: Path) -> int:
    fd: int | None = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(fd)
        named = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or not stat.S_ISDIR(named.st_mode)
            or (info.st_dev, info.st_ino) != (named.st_dev, named.st_ino)
        ):
            raise driver.BenchRefusal("identity_mismatch")
        return fd
    except driver.BenchRefusal:
        if fd is not None:
            os.close(fd)
        raise
    except (OSError, TypeError, ValueError):
        if fd is not None:
            os.close(fd)
        raise driver.BenchRefusal("identity_mismatch") from None


_MANIFEST_NAME_RE = re.compile(r"[A-Za-z0-9_.+-]{1,255}\Z", re.ASCII)
_LIBRARY_NAME_RE = re.compile(
    r"lib[A-Za-z0-9_.+-]+\.so(?:\.[0-9]+)*\Z", re.ASCII
)
_GPU_UUID = re.compile(
    r"GPU-[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\Z",
    re.ASCII,
)


def _safe_manifest_text(value: str) -> bool:
    return (
        type(value) is str
        and _MANIFEST_NAME_RE.fullmatch(value) is not None
        and all(ord(char) >= 32 and ord(char) not in range(127, 160) for char in value)
    )


def _revalidate_candidate_after_snapshot(
    directory_fd: int,
    *,
    names: list[str],
    manifest_name: str,
    manifest_bytes: bytes,
    manifest_sha256: str,
    rows: Mapping[str, tuple[str, ...]],
) -> None:
    try:
        if sorted(os.listdir(directory_fd), key=os.fsencode) != sorted(
            names, key=os.fsencode
        ):
            raise driver.BenchRefusal("identity_mismatch")
        observed_manifest, observed_manifest_sha256 = _stable_bytes_at(
            directory_fd,
            manifest_name,
            byte_cap=1024 * 1024,
        )
        if (
            observed_manifest != manifest_bytes
            or observed_manifest_sha256 != manifest_sha256
        ):
            raise driver.BenchRefusal("identity_mismatch")
        for relative, values in rows.items():
            if values[0] == "F":
                actual = _stable_regular_record_at(directory_fd, relative)
                if (actual.sha256, actual.size) != (values[1], int(values[2])):
                    raise driver.BenchRefusal("identity_mismatch")
            else:
                actual_link = _stable_symlink_record_at(directory_fd, relative)
                if (
                    actual_link.target != values[3]
                    or hashlib.sha256(os.fsencode(actual_link.target)).hexdigest()
                    != values[1]
                ):
                    raise driver.BenchRefusal("identity_mismatch")
        if sorted(os.listdir(directory_fd), key=os.fsencode) != sorted(
            names, key=os.fsencode
        ):
            raise driver.BenchRefusal("identity_mismatch")
    except driver.BenchRefusal:
        raise
    except (OSError, TypeError, ValueError):
        raise driver.BenchRefusal("identity_mismatch") from None


def _revalidate_release_proof_after_manifest(
    directory_fd: int,
    proof: driver.ReleaseDirectoryProof,
) -> None:
    """Keep the manifest and full release snapshot one bracketed observation."""

    try:
        driver._verify_release_directory_fd(directory_fd, proof)
    except driver.BenchRefusal:
        raise driver.BenchRefusal("identity_mismatch") from None


def _verify_candidate_runtime_manifest(root: Path) -> _CandidateObservation:
    directory_fd = _open_static_directory(root)
    try:
        names = os.listdir(directory_fd)
        manifest_name = "runtime-manifest.sha256"
        if names.count(manifest_name) != 1:
            raise driver.BenchRefusal("identity_mismatch")
        manifest_bytes, manifest_sha = _stable_bytes_at(
            directory_fd, manifest_name, byte_cap=1024 * 1024
        )
        try:
            manifest_text = manifest_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise driver.BenchRefusal("identity_mismatch") from None
        rows: dict[str, tuple[str, ...]] = {}
        ordered: list[str] = []
        for line in manifest_text.splitlines(keepends=True):
            if not line.endswith("\n") or line.endswith("\r\n"):
                raise driver.BenchRefusal("identity_mismatch")
            values = tuple(line[:-1].split("\t"))
            if not values or values[0] not in {"F", "L"}:
                raise driver.BenchRefusal("identity_mismatch")
            expected_count = 4 if values[0] == "F" else 4
            if len(values) != expected_count:
                raise driver.BenchRefusal("identity_mismatch")
            relative = values[3] if values[0] == "F" else values[2]
            if not _safe_manifest_text(relative) or relative in rows:
                raise driver.BenchRefusal("identity_mismatch")
            if relative == manifest_name:
                raise driver.BenchRefusal("identity_mismatch")
            rows[relative] = values
            ordered.append(relative)
        if (
            not rows
            or ordered != sorted(ordered, key=os.fsencode)
            or set(names) != set(rows) | {manifest_name}
        ):
            raise driver.BenchRefusal("identity_mismatch")

        regular: dict[str, _StaticRegularRecord] = {}
        links: dict[str, _StaticSymlinkRecord] = {}
        for relative, values in rows.items():
            if values[0] == "F":
                _kind, digest, size_text, _name = values
                if (
                    re.fullmatch(r"[0-9a-f]{64}", digest) is None
                    or re.fullmatch(r"(?:0|[1-9][0-9]*)", size_text) is None
                ):
                    raise driver.BenchRefusal("identity_mismatch")
                actual = _stable_regular_record_at(directory_fd, relative)
                if (actual.sha256, actual.size) != (digest, int(size_text)):
                    raise driver.BenchRefusal("identity_mismatch")
                regular[relative] = actual
            else:
                _kind, target_digest, _name, target = values
                if (
                    re.fullmatch(r"[0-9a-f]{64}", target_digest) is None
                    or not _safe_manifest_text(target)
                    or "/" in target
                    or target in {".", ".."}
                ):
                    raise driver.BenchRefusal("identity_mismatch")
                actual_link = _stable_symlink_record_at(directory_fd, relative)
                if (
                    actual_link.target != target
                    or hashlib.sha256(os.fsencode(actual_link.target)).hexdigest()
                    != target_digest
                ):
                    raise driver.BenchRefusal("identity_mismatch")
                links[relative] = actual_link

        for start in links:
            seen: set[str] = set()
            current = start
            for _hop in range(129):
                if current in seen:
                    raise driver.BenchRefusal("identity_mismatch")
                seen.add(current)
                if current in regular:
                    break
                try:
                    current = links[current].target
                except KeyError:
                    raise driver.BenchRefusal("identity_mismatch") from None
            else:
                raise driver.BenchRefusal("identity_mismatch")

        libraries = {
            name: record.sha256
            for name, record in regular.items()
            if _LIBRARY_NAME_RE.fullmatch(name) is not None
        }
        if "libggml-cuda.so" not in libraries or any(
            "vulkan" in name.lower() for name in rows
        ):
            raise driver.BenchRefusal("identity_mismatch")
        try:
            backend_sha = regular["libggml-cuda.so"].sha256
            server_sha = regular["llama-server"].sha256
        except KeyError:
            raise driver.BenchRefusal("identity_mismatch") from None
        if (
            server_sha != cm.FROZEN_CUDA_SERVER_SHA256
            or backend_sha != cm.FROZEN_CUDA_BACKEND_SHA256
            or manifest_sha != cm.FROZEN_CUDA_RUNTIME_MANIFEST_SHA256
        ):
            raise driver.BenchRefusal("identity_mismatch")
        if sorted(os.listdir(directory_fd), key=os.fsencode) != sorted(
            names, key=os.fsencode
        ):
            raise driver.BenchRefusal("identity_mismatch")
        if sorted(os.listdir(directory_fd), key=os.fsencode) != sorted(
            names, key=os.fsencode
        ):
            raise driver.BenchRefusal("identity_mismatch")
        final_manifest, final_manifest_sha = _stable_bytes_at(
            directory_fd, manifest_name, byte_cap=1024 * 1024
        )
        if (
            final_manifest != manifest_bytes
            or final_manifest_sha != manifest_sha
        ):
            raise driver.BenchRefusal("identity_mismatch")
        final_regular: dict[str, _StaticRegularRecord] = {}
        for relative, expected in regular.items():
            observed = _stable_regular_record_at(directory_fd, relative)
            if (observed.sha256, observed.size) != (
                expected.sha256,
                expected.size,
            ):
                raise driver.BenchRefusal("identity_mismatch")
            final_regular[relative] = observed
        final_links: dict[str, _StaticSymlinkRecord] = {}
        for relative, expected in links.items():
            observed = _stable_symlink_record_at(directory_fd, relative)
            if observed.target != expected.target:
                raise driver.BenchRefusal("identity_mismatch")
            final_links[relative] = observed
        manifest_identity = _named_static_identity_at(
            directory_fd, manifest_name
        )
        for relative, expected in final_regular.items():
            if _named_static_identity_at(directory_fd, relative) != (
                expected.identity
            ):
                raise driver.BenchRefusal("identity_mismatch")
        for relative, expected in final_links.items():
            if _named_static_identity_at(directory_fd, relative) != (
                expected.identity
            ):
                raise driver.BenchRefusal("identity_mismatch")
        if _named_static_identity_at(
            directory_fd, manifest_name
        ) != manifest_identity:
            raise driver.BenchRefusal("identity_mismatch")
        if sorted(os.listdir(directory_fd), key=os.fsencode) != sorted(
            names, key=os.fsencode
        ):
            raise driver.BenchRefusal("identity_mismatch")
        release_proof = driver._release_directory_proof(
            directory_fd,
            manifest_sha256=manifest_sha,
        )
        _revalidate_candidate_after_snapshot(
            directory_fd,
            names=names,
            manifest_name=manifest_name,
            manifest_bytes=manifest_bytes,
            manifest_sha256=manifest_sha,
            rows=rows,
        )
        _revalidate_release_proof_after_manifest(directory_fd, release_proof)
        observation = _CandidateObservation(
            runtime_sha256=server_sha,
            runtime_manifest_sha256=manifest_sha,
            library_hashes=MappingProxyType(libraries),
            release_proof=release_proof,
        )
        _require_static_directory_bound(directory_fd, root)
        return observation
    except OSError:
        raise driver.BenchRefusal("identity_mismatch") from None
    finally:
        os.close(directory_fd)


def _vulkan_library_manifest_at(directory_fd: int) -> str:
    rows: list[dict[str, object]] = []
    names = sorted(
        (
            name
            for name in os.listdir(directory_fd)
            if name.startswith("lib") and ".so" in name
        ),
        key=os.fsencode,
    )
    for name in names:
        info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISLNK(info.st_mode):
            rows.append(
                {
                    "path": name,
                    "type": "symlink",
                    "target": _stable_symlink_at(directory_fd, name),
                }
            )
        elif stat.S_ISREG(info.st_mode):
            digest, size = _stable_regular_at(directory_fd, name)
            rows.append(
                {
                    "path": name,
                    "type": "file",
                    "sha256": digest,
                    "bytes": size,
                }
            )
        else:
            raise driver.BenchRefusal("identity_mismatch")
    encoded = json.dumps(
        rows,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    if len(rows) != 39 or digest != cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256:
        raise driver.BenchRefusal("identity_mismatch")
    return digest


def _vulkan_release_observation(
    root: Path,
) -> tuple[str, driver.ReleaseDirectoryProof]:
    directory_fd = _open_static_directory(root)
    try:
        digest = _vulkan_library_manifest_at(directory_fd)
        proof = driver._release_directory_proof(
            directory_fd,
            manifest_sha256=digest,
        )
        if _vulkan_library_manifest_at(directory_fd) != digest:
            raise driver.BenchRefusal("identity_mismatch")
        _revalidate_release_proof_after_manifest(directory_fd, proof)
        return digest, proof
    finally:
        os.close(directory_fd)


def _vulkan_library_manifest(root: Path) -> str:
    digest, _proof = _vulkan_release_observation(root)
    return digest


def _run_read_only(
    argv: tuple[str, ...], *, timeout_s: int
) -> subprocess.CompletedProcess[str]:
    if (
        type(argv) is not tuple
        or not argv
        or any(type(value) is not str or not value for value in argv)
        or not Path(argv[0]).is_absolute()
        or type(timeout_s) is not int
        or not 1 <= timeout_s <= 60
    ):
        raise driver.BenchRefusal("provider_uncertain")
    try:
        return subprocess.run(
            argv,
            env={
                "HOME": "/home/rohit",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
            shell=False,
            timeout=timeout_s,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise driver.BenchRefusal("provider_uncertain") from None


def _runner_stdout(
    runner: ReadOnlyRunner, argv: tuple[str, ...]
) -> str:
    try:
        result = runner(argv, timeout_s=_STATIC_COMMAND_TIMEOUT_S)
    except driver.BenchRefusal:
        raise
    except Exception:
        raise driver.BenchRefusal("provider_uncertain") from None
    if (
        not isinstance(result, subprocess.CompletedProcess)
        or result.returncode != 0
        or type(result.stdout) is not str
        or len(result.stdout.encode("utf-8")) > 64 * 1024
    ):
        raise driver.BenchRefusal("provider_uncertain")
    return result.stdout


def _collect_host_tool_observations(
    *,
    runner: ReadOnlyRunner,
    paths: StaticAssetPaths,
) -> _HostObservation:
    if (
        type(paths) is not StaticAssetPaths
        or any(
            not path.is_absolute()
            for path in (paths.nvidia_smi, paths.nvcc, paths.cmake)
        )
    ):
        raise driver.BenchRefusal("identity_mismatch")
    uuid_output = _runner_stdout(
        runner,
        (
            str(paths.nvidia_smi),
            "--query-gpu=uuid",
            "--format=csv,noheader",
        ),
    )
    uuids = tuple(line.strip() for line in uuid_output.splitlines() if line.strip())
    if len(uuids) != 1 or _GPU_UUID.fullmatch(uuids[0]) is None:
        raise driver.BenchRefusal("gpu_scope_violation")
    gpu_uuid = uuids[0]
    metadata = _runner_stdout(
        runner,
        (
            str(paths.nvidia_smi),
            "-i",
            gpu_uuid,
            "--query-gpu=driver_version,name,compute_cap",
            "--format=csv,noheader,nounits",
        ),
    )
    metadata_rows = tuple(line.strip() for line in metadata.splitlines() if line.strip())
    if len(metadata_rows) != 1:
        raise driver.BenchRefusal("provider_uncertain")
    parts = tuple(value.strip() for value in metadata_rows[0].split(","))
    if len(parts) != 3:
        raise driver.BenchRefusal("provider_uncertain")
    nvcc = _runner_stdout(runner, (str(paths.nvcc), "--version"))
    nvcc_matches = re.findall(
        r"release (13\.2), V(13\.2\.[0-9]{1,3})(?:\s|\Z)", nvcc
    )
    cmake = _runner_stdout(runner, (str(paths.cmake), "--version"))
    cmake_lines = cmake.splitlines()
    if (
        len(nvcc_matches) != 1
        or not cmake_lines
        or cmake_lines[0] != "cmake version 4.2.3"
    ):
        raise driver.BenchRefusal("identity_mismatch")
    toolkit, compiler = nvcc_matches[0]
    del toolkit
    return _HostObservation(
        gpu_uuid=gpu_uuid,
        driver_version=parts[0],
        gpu_identifier=parts[1],
        compute_capability=parts[2],
        cuda_compiler=compiler,
        cmake_version="4.2.3",
    )


def _driver_package_sha256(
    *,
    repo_root: Path | None = None,
    members: tuple[str, ...] = _PACKAGE_MEMBERS,
) -> tuple[str, bytes]:
    repo = Path(__file__).resolve().parents[1] if repo_root is None else repo_root
    rows: list[list[str]] = []
    for relative in members:
        digest, _size = _stable_regular_file(repo / relative)
        rows.append([relative, digest])
    preimage = json.dumps(
        rows,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(preimage).hexdigest(), preimage


def _validate_frozen_corpus(*, root: Path) -> tuple[str, ...]:
    try:
        payload = driver.open_bench_file("corpus.json", root=root)
        if (
            len(payload) != 285
            or hashlib.sha256(payload).hexdigest() != cm.FROZEN_CORPUS_SHA256
        ):
            raise driver.BenchRefusal("corpus_unavailable")
        decoded = json.loads(payload)
        if (
            type(decoded) is not list
            or len(decoded) != cm.FROZEN_SAMPLE_N
            or any(type(item) is not str or not item for item in decoded)
        ):
            raise driver.BenchRefusal("corpus_unavailable")
        return tuple(decoded)
    except driver.BenchRefusal as exc:
        if exc.code == "corpus_unavailable":
            raise
        raise driver.BenchRefusal("corpus_unavailable") from None
    except (TypeError, ValueError):
        raise driver.BenchRefusal("corpus_unavailable") from None


def _load_frozen_prompts(*, root: Path) -> tuple[str, ...]:
    return _validate_frozen_corpus(root=root)


def _read_boot_id() -> str:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="ascii"
        ).strip()
    except (OSError, UnicodeError):
        raise driver.BenchRefusal("provider_uncertain") from None
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
        r"[0-9a-f]{4}-[0-9a-f]{12}",
        value,
    ) is None:
        raise driver.BenchRefusal("provider_uncertain")
    return value


def _require_static_match(
    selected: cm.StaticPreflightDoc,
    fresh: cm.StaticPreflightDoc,
) -> None:
    if (
        type(selected) is not cm.StaticPreflightDoc
        or type(fresh) is not cm.StaticPreflightDoc
        or selected.gpu_uuid != fresh.gpu_uuid
        or selected.driver_package_sha256 != fresh.driver_package_sha256
        or selected.stub_sha256 != fresh.stub_sha256
        or selected.corpus_verified != fresh.corpus_verified
        or dict(selected.checks) != dict(fresh.checks)
    ):
        raise driver.BenchRefusal("identity_mismatch")


def _collect_static_asset_hashes(paths: StaticAssetPaths) -> _AssetObservation:
    unit_sha, _ = _stable_regular_file(paths.unit)
    dropin_sha, _ = _stable_regular_file(paths.dropin)
    runtime_sha, _ = _stable_regular_file(paths.vulkan_root / "llama-server")
    model_sha, model_bytes = _stable_regular_file(paths.model)
    override_sha, _ = _stable_regular_file(paths.cuda_override)
    flag_sha, _ = _stable_regular_file(paths.flag_source)
    vision_sha, _ = _stable_regular_file(paths.vision_unit)
    stub_sha, _ = _stable_regular_file(paths.stub)
    manifest_sha, vulkan_release_proof = _vulkan_release_observation(
        paths.vulkan_root
    )
    if (
        unit_sha != cm.FROZEN_VULKAN_UNIT_SHA256
        or dropin_sha != cm.FROZEN_VULKAN_DROPIN_SHA256
        or runtime_sha != cm.FROZEN_VULKAN_RUNTIME_SHA256
        or model_sha != cm.FROZEN_MODEL_SHA256
        or model_bytes != cm.FROZEN_MODEL_BYTES
        or manifest_sha != cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256
    ):
        raise driver.BenchRefusal("identity_mismatch")
    return _AssetObservation(
        unit_sha256=unit_sha,
        dropin_sha256=dropin_sha,
        vulkan_runtime_sha256=runtime_sha,
        vulkan_library_manifest_sha256=manifest_sha,
        model_sha256=model_sha,
        model_bytes=model_bytes,
        override_sha256=override_sha,
        flag_source_sha256=flag_sha,
        vision_unit_sha256=vision_sha,
        stub_sha256=stub_sha,
        vulkan_release_proof=vulkan_release_proof,
    )


def _build_rollback_preimage(assets: _AssetObservation) -> bytes:
    fields = (
        ("unit_sha256", assets.unit_sha256),
        ("dropin_sha256", assets.dropin_sha256),
        ("runtime_sha256", assets.vulkan_runtime_sha256),
        (
            "library_manifest_sha256",
            assets.vulkan_library_manifest_sha256,
        ),
        ("model_sha256", assets.model_sha256),
        ("model_bytes", assets.model_bytes),
        ("alias", cm.FROZEN_ALIAS),
        (
            "effective_args_sha256",
            cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
        ),
    )
    try:
        preimage = json.dumps(
            [list(row) for row in fields],
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError):
        raise driver.BenchRefusal("identity_mismatch") from None
    if (
        preimage != cm.frozen_rollback_manifest_preimage()
        or len(preimage) != 582
        or hashlib.sha256(preimage).hexdigest()
        != cm.FROZEN_ROLLBACK_MANIFEST_SHA256
    ):
        raise driver.BenchRefusal("identity_mismatch")
    return preimage


def collect_static_observation(
    *,
    root: Path = driver.BENCH_ROOT,
    paths: StaticAssetPaths = CANONICAL_STATIC_ASSETS,
    runner: ReadOnlyRunner = _run_read_only,
    clock: driver.Clock,
) -> StaticObservation:
    _validate_frozen_corpus(root=root)
    corpus_sha = cm.FROZEN_CORPUS_SHA256
    assets = _collect_static_asset_hashes(paths)
    candidate = _verify_candidate_runtime_manifest(paths.candidate_root)
    host = _collect_host_tool_observations(runner=runner, paths=paths)
    rollback_preimage = _build_rollback_preimage(assets)
    package_sha256, _package_preimage = _driver_package_sha256()
    identity = cm.RuntimeIdentity.from_static_evidence(
        tag=cm.FROZEN_TAG,
        commit=cm.FROZEN_COMMIT,
        version=cm.FROZEN_VERSION,
        alias=cm.FROZEN_ALIAS,
        model_sha256=assets.model_sha256,
        model_bytes=assets.model_bytes,
        runtime_sha256=candidate.runtime_sha256,
        library_hashes=candidate.library_hashes,
        effective_args=cm._MODE_ARGS["bench"],
        mode="bench",
        production_override_sha256=assets.override_sha256,
        backend_environment=cm.FROZEN_BACKEND_ENVIRONMENT,
        runtime_manifest_sha256=candidate.runtime_manifest_sha256,
        rollback_manifest_sha256=hashlib.sha256(
            rollback_preimage
        ).hexdigest(),
        cuda_toolkit="13.2",
        cuda_compiler=host.cuda_compiler,
        cmake_version=host.cmake_version,
        driver_version=host.driver_version,
        gpu_identifier=host.gpu_identifier,
        compute_capability=host.compute_capability,
    )
    try:
        timestamp = clock.now_utc()
        static_doc = cm.StaticPreflightDoc(
            gpu_uuid=host.gpu_uuid,
            driver_package_sha256=package_sha256,
            stub_sha256=assets.stub_sha256,
            corpus_verified=corpus_sha == cm.FROZEN_CORPUS_SHA256,
            checks={
                "corpus": corpus_sha,
                "incumbent_unit": assets.unit_sha256,
                "incumbent_dropin": assets.dropin_sha256,
                "incumbent_server": assets.vulkan_runtime_sha256,
                "model": assets.model_sha256,
                "library_manifest": assets.vulkan_library_manifest_sha256,
                "effective_args": cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
                "flag_source": assets.flag_source_sha256,
                "vision_unit": assets.vision_unit_sha256,
                "candidate_manifest": candidate.runtime_manifest_sha256,
                "bench_root_mode": "700",
                "stub_pin": assets.stub_sha256,
            },
            timestamp=timestamp,
        )
    except (TypeError, ValueError):
        raise driver.BenchRefusal("identity_mismatch") from None
    return StaticObservation(
        static_doc,
        identity,
        rollback_preimage,
        assets.vulkan_release_proof,
        candidate.release_proof,
    )


def _collect_rehearsal_identity(
    static_preflight_ref: str,
    *,
    root: Path,
    paths: StaticAssetPaths = CANONICAL_STATIC_ASSETS,
    runner: ReadOnlyRunner = _run_read_only,
) -> tuple[cm.StaticPreflightDoc, cm.RuntimeIdentity]:
    """Collect rehearsal identity without opening corpus or model bytes."""

    try:
        persisted = cm.PersistedDoc(
            driver.open_bench_file(static_preflight_ref, root=root)
        )
        static = persisted.obj
        if type(static) is not cm.StaticPreflightDoc:
            raise ValueError("static_preflight")
        candidate = _verify_candidate_runtime_manifest(paths.candidate_root)
        package_sha256, _package_preimage = _driver_package_sha256()
        host = _collect_host_tool_observations(runner=runner, paths=paths)
        override_sha256, _override_bytes = _stable_regular_file(
            paths.cuda_override
        )
        if (
            static.driver_package_sha256 != package_sha256
            or static.gpu_uuid != host.gpu_uuid
            or static.checks["candidate_manifest"]
            != candidate.runtime_manifest_sha256
            or static.checks["model"] != cm.FROZEN_MODEL_SHA256
        ):
            raise ValueError("rehearsal_identity")
        identity = cm.RuntimeIdentity.from_static_evidence(
            tag=cm.FROZEN_TAG,
            commit=cm.FROZEN_COMMIT,
            version=cm.FROZEN_VERSION,
            alias=cm.FROZEN_ALIAS,
            model_sha256=cm.FROZEN_MODEL_SHA256,
            model_bytes=cm.FROZEN_MODEL_BYTES,
            runtime_sha256=candidate.runtime_sha256,
            library_hashes=candidate.library_hashes,
            effective_args=cm._MODE_ARGS["bench"],
            mode="bench",
            production_override_sha256=override_sha256,
            backend_environment=cm.FROZEN_BACKEND_ENVIRONMENT,
            runtime_manifest_sha256=candidate.runtime_manifest_sha256,
            rollback_manifest_sha256=cm.FROZEN_ROLLBACK_MANIFEST_SHA256,
            cuda_toolkit="13.2",
            cuda_compiler=host.cuda_compiler,
            cmake_version=host.cmake_version,
            driver_version=host.driver_version,
            gpu_identifier=host.gpu_identifier,
            compute_capability=host.compute_capability,
        )
    except driver.BenchRefusal:
        raise
    except (KeyError, TypeError, ValueError):
        raise driver.BenchRefusal("identity_mismatch") from None
    return static, identity


def _static_preflight_fields(doc: cm.StaticPreflightDoc) -> dict[str, object]:
    return {
        "binding_sha256": doc.binding_sha256,
        "gpu_uuid": doc.gpu_uuid,
        "driver_package_sha256": doc.driver_package_sha256,
        "stub_sha256": doc.stub_sha256,
        "corpus_verified": doc.corpus_verified,
        "checks": dict(doc.checks),
        "timestamp": doc.timestamp,
    }


@dataclass(frozen=True, slots=True)
class _DurableSuccessLatch:
    result: TerminalResult
    root: Path
    root_identity: tuple[int, ...]
    receipt_identity: tuple[int, ...]
    semantic_validator: Callable[[], bool] | None = None


def _static_latch_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _durable_success_latch_is_current(latch: _DurableSuccessLatch) -> bool:
    result = latch.result
    if result.artifact_ref is None or result.artifact_sha256 is None:
        return False
    try:
        payload = driver.open_bench_file(result.artifact_ref, root=latch.root)
        root_info = os.stat(latch.root, follow_symlinks=False)
        receipt_info = os.stat(
            latch.root / result.artifact_ref, follow_symlinks=False
        )
    except Exception:
        return False
    filesystem_current = (
        hashlib.sha256(payload).hexdigest() == result.artifact_sha256
        and stat.S_ISDIR(root_info.st_mode)
        and _static_latch_identity(root_info) == latch.root_identity
        and stat.S_ISREG(receipt_info.st_mode)
        and receipt_info.st_uid == os.geteuid()
        and receipt_info.st_nlink == 1
        and stat.S_IMODE(receipt_info.st_mode) == 0o600
        and _static_latch_identity(receipt_info) == latch.receipt_identity
    )
    if not filesystem_current:
        return False
    validator = latch.semantic_validator
    if validator is None:
        return True
    try:
        return validator() is True
    except Exception:
        return False


def _latch_durable_success(
    result: TerminalResult,
    *,
    root: Path,
    semantic_validator: Callable[[], bool] | None = None,
) -> None:
    global _linearized_durable_success
    if not _binding_is_current(result, root=root):
        raise _StaticTerminalPublicationFailure("filesystem_hazard")
    try:
        root_info = os.stat(root, follow_symlinks=False)
        assert result.artifact_ref is not None
        receipt_info = os.stat(root / result.artifact_ref, follow_symlinks=False)
        if (
            not stat.S_ISDIR(root_info.st_mode)
            or not stat.S_ISREG(receipt_info.st_mode)
            or receipt_info.st_uid != os.geteuid()
            or receipt_info.st_nlink != 1
            or stat.S_IMODE(receipt_info.st_mode) != 0o600
        ):
            raise OSError("durable receipt identity")
    except (AssertionError, OSError):
        raise _StaticTerminalPublicationFailure("filesystem_hazard") from None
    if semantic_validator is not None:
        try:
            if semantic_validator() is not True:
                raise _StaticTerminalPublicationFailure(
                    "filesystem_hazard"
                )
        except _StaticTerminalPublicationFailure:
            raise
        except Exception:
            raise _StaticTerminalPublicationFailure(
                "filesystem_hazard"
            ) from None
    _linearized_durable_success = _DurableSuccessLatch(
        result,
        Path(root),
        _static_latch_identity(root_info),
        _static_latch_identity(receipt_info),
        semantic_validator,
    )


def _static_preflight_handler(
    attempt: driver.CommandAttempt,
    *,
    root: Path,
    clock: driver.Clock,
    paths: StaticAssetPaths = CANONICAL_STATIC_ASSETS,
    runner: ReadOnlyRunner = _run_read_only,
) -> TerminalResult:
    observation = collect_static_observation(
        root=root, paths=paths, runner=runner, clock=clock
    )
    preimage_sha = hashlib.sha256(observation.rollback_preimage).hexdigest()
    relative = f"preimages/rollback-manifest-{preimage_sha}.json"
    try:
        driver.publish_or_verify_immutable(
            relative,
            observation.rollback_preimage,
            attempt=attempt,
            root=root,
        )
    except driver.BenchRefusal as exc:
        raise _StaticTerminalPublicationFailure(exc.code) from None
    except Exception:
        raise _StaticTerminalPublicationFailure("filesystem_hazard") from None
    policy = driver.ProductionArtifactPolicy()
    encoded = policy.encode(
        "static_preflight", _static_preflight_fields(observation.static_doc)
    )
    receipt_relative = (
        f"{policy.artifact_dir('static_preflight')}/"
        f"static-preflight-attempt-{attempt.ordinal:03d}.json"
    )
    global _linearized_durable_success
    old_mask: set[int] | None = None
    try:
        old_mask = _pthread_sigmask(signal.SIG_BLOCK, _WATCHED_SIGNALS)
        pending = _snapshot_pending_signal(None)
        if pending is not None:
            raise driver._CommandInterrupted(pending, attempt)
        try:
            driver.write_private_file(receipt_relative, encoded, root=root)
        except Exception:
            raise _StaticTerminalPublicationFailure(
                "filesystem_hazard"
            ) from None
        completion = cm.CommandCompletionDoc(
            command="static-preflight",
            ordinal=attempt.ordinal,
            window_id=None,
            admission_ref=attempt.admission_ref,
            admission_sha256=attempt.admission_sha256,
            artifact_ref=receipt_relative,
            artifact_sha256=hashlib.sha256(encoded).hexdigest(),
            artifact_schema=cm.STATIC_PREFLIGHT_SCHEMA,
            status="completed",
            timestamp=clock.now_utc(),
        )
        completion_encoded = policy.encode(
            "command_completion",
            {
                "binding_sha256": completion.binding_sha256,
                "command": completion.command,
                "ordinal": completion.ordinal,
                "window_id": completion.window_id,
                "admission_ref": completion.admission_ref,
                "admission_sha256": completion.admission_sha256,
                "artifact_ref": completion.artifact_ref,
                "artifact_sha256": completion.artifact_sha256,
                "artifact_schema": completion.artifact_schema,
                "status": completion.status,
                "timestamp": completion.timestamp,
            },
        )
        completed: TerminalResult | None = None

        def latch_completion(
            completion_ref: str,
            completion_sha256: str,
        ) -> None:
            global _linearized_durable_success
            nonlocal completed
            candidate = TerminalResult(
                "ok",
                "static_preflight_ready",
                None,
                completion_ref,
                completion_sha256,
            )
            completed = candidate
            _latch_durable_success(candidate, root=root)

        completion_ref, completion_sha256 = driver.publish_command_artifact(
            attempt,
            "terminal",
            completion_encoded,
            root=root,
            on_committed=latch_completion,
        )
        if (
            completed is None
            or completed.artifact_ref != completion_ref
            or completed.artifact_sha256 != completion_sha256
        ):
            raise _StaticTerminalPublicationFailure("filesystem_hazard")
        _snapshot_pending_signal(None)
        return completed
    finally:
        if old_mask is not None:
            try:
                _pthread_sigmask(signal.SIG_SETMASK, old_mask)
            except driver._CommandInterrupted:
                if _linearized_durable_success is None:
                    raise


class InvocationRefusal(Exception):
    """A non-echoing argparse refusal."""


class _StaticTerminalPublicationFailure(Exception):
    """Static evidence publication failed; bind refusal to durable admission."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _AssemblyTerminalPublicationFailure(Exception):
    """Assembly terminal could not be proven; preserve the admission binding."""


@dataclass(frozen=True, slots=True)
class TerminalResult:
    status: Literal["ok", "refused", "failed"]
    outcome: str
    window_id: str | None
    artifact_ref: str | None
    artifact_sha256: str | None

    def __post_init__(self) -> None:
        if self.status not in {"ok", "refused", "failed"}:
            raise ValueError("terminal_status")
        if type(self.outcome) is not str or re.fullmatch(
            r"[a-z][a-z0-9_]{0,63}", self.outcome
        ) is None:
            raise ValueError("terminal_outcome")
        if (self.artifact_ref is None) != (self.artifact_sha256 is None):
            raise ValueError("terminal_artifact_pair")
        if self.window_id is not None and re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}", self.window_id
        ) is None:
            raise ValueError("terminal_window_id")
        if self.artifact_ref is not None:
            parts = self.artifact_ref.split("/")
            if os.path.isabs(self.artifact_ref) or any(
                part in {"", ".", ".."} for part in parts
            ):
                raise ValueError("terminal_artifact_pair")
            if re.fullmatch(r"[0-9a-f]{64}", self.artifact_sha256 or "") is None:
                raise ValueError("terminal_artifact_pair")


_TRUSTED_PHASE_GUARD = object()


@dataclass(frozen=True, slots=True, init=False)
class _TrustedPhaseResult:
    terminal: TerminalResult

    def __init__(
        self,
        terminal: TerminalResult,
        *,
        _guard: object,
    ) -> None:
        if _guard is not _TRUSTED_PHASE_GUARD or type(terminal) is not TerminalResult:
            raise ValueError("trusted_phase_result")
        object.__setattr__(self, "terminal", terminal)

    @property
    def status(self) -> str:
        return self.terminal.status

    @property
    def outcome(self) -> str:
        return self.terminal.outcome

    @property
    def artifact_ref(self) -> str | None:
        return self.terminal.artifact_ref


class NonEchoingParser(argparse.ArgumentParser):
    def error(self, _message: str) -> Never:
        raise InvocationRefusal


def _relative_ref(value: str) -> str:
    if (
        type(value) is not str
        or not value
        or os.path.isabs(value)
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise argparse.ArgumentTypeError("relative_ref")
    return value


def build_parser() -> NonEchoingParser:
    parser = NonEchoingParser(add_help=False)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in PUBLIC_COMMANDS:
        command_parser = commands.add_parser(command, add_help=False)
        if command == "rehearse":
            command_parser.add_argument(
                "--static-preflight",
                type=_relative_ref,
                required=True,
            )
            command_parser.add_argument(
                "--persona",
                choices=_REHEARSAL_PERSONAS,
                required=True,
            )
        elif command == "vulkan-baseline":
            for name in (
                "window-authorization",
                "static-preflight",
                "static-admission",
                "static-completion",
            ):
                command_parser.add_argument(
                    f"--{name}", type=_relative_ref, required=True
                )
        elif command == "cuda-candidate":
            for name in (
                "continuation",
                "parent-window",
                "parent-packet",
                "parent-admission",
                "parent-completion",
                "static-preflight",
                "static-admission",
                "static-completion",
            ):
                command_parser.add_argument(
                    f"--{name}", type=_relative_ref, required=True
                )
        elif command == "assemble-stage1":
            for field in fields(assemble.Stage1ArtifactPaths):
                command_parser.add_argument(
                    f"--{field.name.replace('_', '-')}",
                    dest=field.name,
                    type=_relative_ref,
                    required=True,
                )
    return parser


def _terminal_bytes(result: TerminalResult) -> bytes:
    return (
        json.dumps(asdict(result), sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _write_stdout(data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(1, view)
        if written <= 0:
            raise OSError("terminal_write")
        view = view[written:]


def _snapshot_pending_signal(explicit: int | None) -> int | None:
    pending = set(signal.sigpending()).intersection(_WATCHED_SIGNALS)
    if explicit in _WATCHED_SIGNALS:
        pending.add(signal.Signals(explicit))
    selected = signal.SIGTERM if signal.SIGTERM in pending else None
    if selected is None and signal.SIGINT in pending:
        selected = signal.SIGINT
    while True:
        current = set(signal.sigpending()).intersection(_WATCHED_SIGNALS)
        if not current:
            break
        signal.sigwait(current)
    return None if selected is None else int(selected)


def _exit_status(result: TerminalResult, signum: int | None = None) -> int:
    if signum is not None:
        return 128 + signum
    if result.outcome == "invocation_invalid":
        return 2
    if result.status == "ok":
        return 0
    if result.status == "refused":
        return 3
    return 4


def _commit_terminal(
    result: TerminalResult,
    *,
    interrupted_signum: int | None = None,
    interruption_fallback: TerminalResult | None = None,
) -> int:
    global _terminal_committed
    _terminal_committed = False
    latch = _linearized_durable_success
    linearized: TerminalResult | None = None
    preblock_signals: set[int] = set()
    if interrupted_signum in _WATCHED_SIGNALS:
        preblock_signals.add(int(interrupted_signum))
    old_mask: set[int] | None = None
    try:
        while True:
            try:
                old_mask = signal.pthread_sigmask(
                    signal.SIG_BLOCK, _WATCHED_SIGNALS
                )
                break
            except driver._CommandInterrupted as interrupted:
                preblock_signals.add(interrupted.signum)
        explicit = None
        if signal.SIGTERM in preblock_signals:
            explicit = int(signal.SIGTERM)
        elif signal.SIGINT in preblock_signals:
            explicit = int(signal.SIGINT)
        selected = _snapshot_pending_signal(explicit)
        latch_is_current = False
        if latch is not None:
            try:
                latch_is_current = _durable_success_latch_is_current(latch)
            except Exception:
                latch_is_current = False
        if latch_is_current:
            linearized = latch.result
            result = linearized
            interruption_fallback = None
            selected = None
        elif latch is not None:
            binding = interruption_fallback
            result = TerminalResult(
                "failed",
                "provider_uncertain",
                None if binding is None else binding.window_id,
                None if binding is None else binding.artifact_ref,
                None if binding is None else binding.artifact_sha256,
            )
            interruption_fallback = None
            selected = None
    except Exception:
        _terminal_committed = True
        if old_mask is not None:
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            except Exception:
                pass
        return 4
    cleanup_dominates = (
        _cleanup_incomplete_committing or result.outcome == "cleanup_incomplete"
    )
    if cleanup_dominates:
        selected = None
    committed_result = result
    if selected is not None:
        binding = result if interruption_fallback is None else interruption_fallback
        committed_result = TerminalResult(
            "refused",
            "interrupted",
            binding.window_id,
            binding.artifact_ref,
            binding.artifact_sha256,
        )
    code = _exit_status(committed_result, selected)
    try:
        _write_stdout(_terminal_bytes(committed_result))
    except Exception:
        code = 4
    _terminal_committed = True
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
    except driver._CommandInterrupted:
        pass
    except Exception:
        pass
    return code


def _on_command_signal(signum: int, _frame: FrameType | None) -> None:
    if (
        _terminal_committed
        or _cleanup_incomplete_committing
        or _linearized_durable_success is not None
    ):
        return
    raise driver._CommandInterrupted(signum)


def _install_command_signal_scope() -> dict[signal.Signals, object]:
    previous: dict[signal.Signals, object] = {}
    for signum in _WATCHED_SIGNALS:
        previous[signum] = signal.signal(signum, _on_command_signal)
    return previous


def _enter_command_signal_scope() -> tuple[dict[signal.Signals, object], set[int]]:
    """Install both handlers while neither watched signal can be delivered."""

    old_mask = _pthread_sigmask(signal.SIG_BLOCK, _WATCHED_SIGNALS)
    previous: dict[signal.Signals, object] = {}
    try:
        previous = _install_command_signal_scope()
    except BaseException:
        _restore_command_signal_scope(previous)
        _pthread_sigmask(signal.SIG_SETMASK, old_mask)
        raise
    return previous, old_mask


def _restore_command_signal_scope(
    previous: dict[signal.Signals, object], *, restore_mask: bool = True
) -> None:
    try:
        old_mask = _pthread_sigmask(signal.SIG_BLOCK, _WATCHED_SIGNALS)
    except Exception:
        return
    try:
        for signum, handler in previous.items():
            try:
                signal.signal(signum, handler)
            except Exception:
                continue
        if _terminal_committed:
            try:
                _snapshot_pending_signal(None)
            except Exception:
                pass
    finally:
        if restore_mask:
            try:
                _pthread_sigmask(signal.SIG_SETMASK, old_mask)
            except Exception:
                pass


def _admission_result(
    attempt: driver.CommandAttempt,
    *,
    status: Literal["refused", "failed"],
    outcome: str,
) -> TerminalResult:
    return TerminalResult(
        status,
        outcome,
        None,
        attempt.admission_ref,
        attempt.admission_sha256,
    )


def _cleanup_incomplete_result(
    attempt: driver.CommandAttempt | None,
) -> TerminalResult:
    global _cleanup_incomplete_committing
    _cleanup_incomplete_committing = True
    if attempt is None:
        return TerminalResult("failed", "cleanup_incomplete", None, None, None)
    return _admission_result(
        attempt, status="failed", outcome="cleanup_incomplete"
    )


def _expected_terminal_ref(attempt: driver.CommandAttempt) -> str:
    name = driver._command_name(attempt.command, attempt.ordinal, "terminal")
    return driver._command_ref(attempt.namespace, name)


def _binding_is_current(result: TerminalResult, *, root: Path) -> bool:
    if result.artifact_ref is None or result.artifact_sha256 is None:
        return False
    try:
        payload = driver.open_bench_file(result.artifact_ref, root=root)
    except Exception:
        return False
    return hashlib.sha256(payload).hexdigest() == result.artifact_sha256


def _binding_matches_tier(
    attempt: driver.CommandAttempt, result: TerminalResult
) -> bool:
    if result.artifact_ref is None:
        return False
    is_rehearsal = result.artifact_ref.startswith("rehearsal/")
    return is_rehearsal == (attempt.namespace == "rehearsal")


def _is_command_control_ref(relative: str | None) -> bool:
    if relative is None:
        return False
    name = relative.rsplit("/", 1)[-1]
    return driver._COMMAND_ARTIFACT_NAME_RE.fullmatch(name) is not None


def _valid_command_completion_result(
    attempt: driver.CommandAttempt,
    result: TerminalResult,
    *,
    root: Path,
) -> bool:
    if (
        result.status != "ok"
        or result.artifact_ref != _expected_terminal_ref(attempt)
        or result.artifact_sha256 is None
    ):
        return False
    try:
        persisted = cm.PersistedDoc(
            driver.open_bench_file(result.artifact_ref, root=root)
        )
    except Exception:
        return False
    completion = persisted.obj
    if not (
        type(completion) is cm.CommandCompletionDoc
        and persisted.file_sha256 == result.artifact_sha256
        and completion.command == attempt.command
        and completion.ordinal == attempt.ordinal
        and completion.admission_ref == attempt.admission_ref
        and completion.admission_sha256 == attempt.admission_sha256
        and completion.window_id == result.window_id
    ):
        return False
    if attempt.command == "static-preflight":
        return True
    expected_type: type[object] = cm.PhasePacket
    try:
        artifact_bytes = driver.open_bench_file(
            completion.artifact_ref, root=root
        )
        _admission, _completion, artifact = (
            driver._load_verified_completion_pair(
                admission_ref=attempt.admission_ref,
                completion_ref=result.artifact_ref,
                artifact_ref=completion.artifact_ref,
                artifact_bytes=artifact_bytes,
                expected_command=attempt.command,
                expected_window_id=result.window_id,
                expected_type=expected_type,
                root=root,
            )
        )
    except Exception:
        return False
    packet = artifact.obj
    return (
        type(packet) is cm.PhasePacket
        and packet.phase == completion.decoded_phase
        and packet.window_id == result.window_id
        and packet.outcome == "completed"
        and packet.order_sha256 == cm.FROZEN_ORDER_SHA256
    )


def _sha256_value(value: object) -> bool:
    return (
        type(value) is str
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    )


def _sha256_or_none(value: object) -> bool:
    return value is None or _sha256_value(value)


def _utc_timestamp_value(value: object, *, allow_none: bool = False) -> bool:
    if value is None:
        return allow_none
    if type(value) is not str or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.utcoffset() == timedelta(0)


def _read_canonical_terminal_wrapper(
    result: TerminalResult,
    *,
    root: Path,
) -> dict[str, object] | None:
    if result.artifact_ref is None or result.artifact_sha256 is None:
        return None
    try:
        payload = driver.open_bench_file(result.artifact_ref, root=root)
        wrapper = json.loads(payload)
        if (
            type(wrapper) is not dict
            or payload != driver._canonical_json(wrapper)
            or hashlib.sha256(payload).hexdigest() != result.artifact_sha256
        ):
            return None
        return wrapper
    except Exception:
        return None


def _valid_rehearsal_result(
    attempt: driver.CommandAttempt,
    result: TerminalResult,
    *,
    root: Path,
) -> bool:
    if result.artifact_ref is None:
        return result.status != "ok"
    wrapper = _read_canonical_terminal_wrapper(result, root=root)
    if (
        wrapper is None
        or set(wrapper) != {"rehearsal_schema", "tier", "payload"}
        or wrapper["rehearsal_schema"] != driver.REHEARSAL_PACKET_SCHEMA
        or wrapper["tier"] != "rehearsal"
        or type(wrapper["payload"]) is not dict
    ):
        return False
    packet = wrapper["payload"]
    if (
        set(packet) != {"kind", "binding_sha256", "fields"}
        or packet.get("kind") not in {"packet", "refusal"}
        or type(packet.get("fields")) is not dict
        or packet["fields"].get("outcome") != result.outcome
    ):
        return False
    if result.status == "ok":
        return (
            packet["kind"] == "packet"
            and result.outcome == "completed"
            and _sha256_value(packet["binding_sha256"])
        )
    if result.artifact_ref == _expected_terminal_ref(attempt):
        return (
            packet["kind"] == "refusal"
            and packet["binding_sha256"] is None
            and set(packet["fields"]) == {"outcome"}
        )
    return (
        result.status in {"refused", "failed"}
        and _sha256_or_none(packet["binding_sha256"])
    )


def _valid_production_refusal_result(
    attempt: driver.CommandAttempt,
    result: TerminalResult,
    *,
    root: Path,
) -> bool:
    if result.artifact_ref is None:
        return result.status != "ok"
    wrapper = _read_canonical_terminal_wrapper(result, root=root)
    if (
        wrapper is None
        or set(wrapper) != {"schema", "binding_sha256", "fields"}
        or type(wrapper["fields"]) is not dict
    ):
        return False
    fields_value = wrapper["fields"]
    if result.artifact_ref == _expected_terminal_ref(attempt):
        return (
            wrapper["schema"] == driver.REFUSAL_SCHEMA
            and wrapper["binding_sha256"] is None
            and set(fields_value) == {"outcome"}
            and fields_value["outcome"] == result.outcome
        )
    expected_phase = {
        "vulkan-baseline": "vulkan_baseline",
        "cuda-candidate": "cuda_candidate",
    }.get(attempt.command)
    if expected_phase is None:
        return False
    spawned = fields_value.get("spawned")
    expected_schema = (
        driver.PHASE_PACKET_SCHEMA
        if spawned is True
        else driver.REFUSAL_SCHEMA
    )
    return (
        type(spawned) is bool
        and wrapper["schema"] == expected_schema
        and wrapper["binding_sha256"]
        == hashlib.sha256(driver._canonical_json(fields_value)).hexdigest()
        and fields_value.get("phase") == expected_phase
        and fields_value.get("window_id") == result.window_id
        and type(fields_value.get("boot_id")) is str
        and bool(fields_value["boot_id"])
        and fields_value.get("outcome") == result.outcome
        and _utc_timestamp_value(fields_value.get("timestamp"))
        and result.status == ("failed" if spawned else "refused")
    )


def _valid_assembly_success_fields(
    receipt: dict[str, object],
    *,
    binding: str,
    outcome: str,
) -> bool:
    if (
        set(receipt) != _ASSEMBLY_RECEIPT_FIELDS
        or not _utc_timestamp_value(receipt.get("timestamp"))
        or receipt.get("phase") != "cuda_candidate"
        or receipt.get("artifact_role")
        != "producer_evidence_not_verdict"
        or receipt.get("decision") != outcome
        or type(receipt.get("reasons")) is not list
        or any(
            type(item) is not str or item not in cm._REASONS
            for item in receipt["reasons"]
        )
        or (outcome == "bench_passed" and receipt["reasons"] != [])
        or (outcome == "keep_vulkan" and not receipt["reasons"])
        or receipt.get("bundle_binding_sha256") != binding
        or not _sha256_value(receipt.get("bench_binding_sha256"))
    ):
        return False
    evaluator_versions = receipt.get("evaluator_versions")
    runtime = receipt.get("runtime")
    backend = receipt.get("backend_witnesses")
    measurements = receipt.get("measurements")
    phase_evidence = receipt.get("phase_evidence")
    containment = receipt.get("containment")
    gate = receipt.get("gate_bindings")
    if not (
        type(evaluator_versions) is dict
        and set(evaluator_versions) == {"quality", "owner_voice"}
        and all(
            type(value) is str and bool(value)
            for value in evaluator_versions.values()
        )
        and type(runtime) is dict
        and set(runtime) == _ASSEMBLY_RUNTIME_FIELDS
        and type(backend) is dict
        and set(backend) == _ASSEMBLY_BACKEND_FIELDS
        and type(measurements) is dict
        and set(measurements) == _ASSEMBLY_MEASUREMENT_FIELDS
        and type(phase_evidence) is dict
        and set(phase_evidence) == _ASSEMBLY_PHASE_EVIDENCE_FIELDS
        and type(containment) is dict
        and set(containment) == _ASSEMBLY_CONTAINMENT_FIELDS
        and type(gate) is dict
        and set(gate) == _ASSEMBLY_GATE_FIELDS
        and all(_sha256_value(value) for value in gate.values())
        and gate["bench_evidence_sha256"]
        == receipt["bench_binding_sha256"]
    ):
        return False
    runtime_hashes = {
        key for key in _ASSEMBLY_RUNTIME_FIELDS if key.endswith("_sha256")
    }
    required_backend_fields = {
        "control_maps_sha256",
        "candidate_maps_sha256",
        "control_binding_sha256",
        "candidate_binding_sha256",
    }
    absent_backend_fields = _ASSEMBLY_BACKEND_FIELDS - required_backend_fields
    if (
        any(not _sha256_value(runtime[key]) for key in runtime_hashes)
        or runtime.get("tag") != cm.FROZEN_TAG
        or runtime.get("commit") != cm.FROZEN_COMMIT
        or runtime.get("version") != cm.FROZEN_VERSION
        or type(runtime.get("version")) is not int
        or runtime.get("backend") != "cuda"
        or runtime.get("mode") != "bench"
        or runtime.get("model_sha256") != cm.FROZEN_MODEL_SHA256
        or runtime.get("model_bytes") != cm.FROZEN_MODEL_BYTES
        or type(runtime.get("model_bytes")) is not int
        or runtime.get("alias") != cm.FROZEN_ALIAS
        or runtime.get("cuda_toolkit") != "13.2"
        or type(runtime.get("cuda_compiler")) is not str
        or re.fullmatch(r"13\.2\.\d{1,3}", runtime["cuda_compiler"])
        is None
        or type(runtime.get("cmake_version")) is not str
        or re.fullmatch(
            r"(?:3\.\d{1,2}\.\d{1,3}|4\.\d{1,2}\.\d{1,3})",
            runtime["cmake_version"],
        )
        is None
        or type(runtime.get("driver_version")) is not str
        or re.fullmatch(
            r"\d{3}\.\d{1,3}\.\d{1,3}",
            runtime["driver_version"],
        )
        is None
        or tuple(int(part) for part in runtime["driver_version"].split("."))
        < (590, 44)
        or type(runtime.get("gpu_identifier")) is not str
        or re.fullmatch(
            r"NVIDIA (?:GeForce )?RTX 4090",
            runtime["gpu_identifier"],
        )
        is None
        or runtime.get("compute_capability") != "8.9"
        or runtime.get("rollback_manifest_sha256")
        != cm.FROZEN_ROLLBACK_MANIFEST_SHA256
        or any(
            type(runtime[key]) is not str or not runtime[key]
            for key in _ASSEMBLY_RUNTIME_FIELDS
            - runtime_hashes
            - {"model_bytes", "version"}
        )
        or any(
            not _sha256_value(backend[key])
            for key in required_backend_fields
        )
        or any(backend[key] is not None for key in absent_backend_fields)
        or backend["control_binding_sha256"]
        != gate["control_maps_sha256"]
        or backend["candidate_binding_sha256"]
        != gate["candidate_maps_sha256"]
        or gate["runtime_identity_sha256"]
        != hashlib.sha256(
            json.dumps(
                runtime,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    ):
        return False
    measurement_hashes = {"corpus_sha256", "order_sha256", "topology_sha256"}
    integer_measurements = {
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
    }
    numeric_measurements = {
        "seven_turn_max_ms",
        "p95_e2e_ms",
        "median_decode_tps",
        "median_prefill_tps",
        "steady_bar1_percent",
        "unload_leak_mib",
    }
    kernel = measurements.get("kernel_counters")
    cycles = measurements.get("cycles")
    if (
        any(not _sha256_value(measurements[key]) for key in measurement_hashes)
        or measurements.get("sample_n") != cm.FROZEN_SAMPLE_N
        or measurements.get("warmup_count") != cm.FROZEN_WARMUP_COUNT
        or measurements.get("measured_sample_count")
        != cm.FROZEN_MEASURED_SAMPLE_COUNT
        or measurements.get("load_cycles") != cm.FROZEN_LOAD_CYCLES
        or measurements.get("corpus_sha256") != cm.FROZEN_CORPUS_SHA256
        or measurements.get("order_sha256") != cm.FROZEN_ORDER_SHA256
        or any(
            type(measurements[key]) is not int
            or isinstance(measurements[key], bool)
            or measurements[key] < 0
            for key in integer_measurements
        )
        or any(
            type(measurements[key]) not in {int, float}
            or isinstance(measurements[key], bool)
            or measurements[key] < 0
            for key in numeric_measurements
        )
        or type(measurements.get("mtp_initialized")) is not bool
        or measurements.get("recall_posture") not in {"pass", "fail"}
        or type(kernel) is not dict
        or set(kernel) != set(driver.KERNEL_COUNTER_KEYS)
        or any(
            type(value) is not int
            or isinstance(value, bool)
            or value < 0
            for value in kernel.values()
        )
        or type(cycles) is not list
        or len(cycles) != measurements["load_cycles"]
        or any(type(cycle) is not dict for cycle in cycles)
    ):
        return False
    cycle_bar_fields = {
        "bar1_before_percent",
        "bar1_after_load_percent",
        "bar1_after_inference_percent",
        "bar1_after_unload_percent",
    }
    cycle_vram_fields = {
        "vram_before_mib",
        "vram_after_load_mib",
        "vram_after_inference_mib",
        "vram_after_unload_mib",
    }
    if (
        any(type(cycle.get("cycle")) is not int for cycle in cycles)
        or tuple(cycle.get("cycle") for cycle in cycles)
        != tuple(range(1, measurements["load_cycles"] + 1))
        or any(set(cycle) != _ASSEMBLY_CYCLE_FIELDS for cycle in cycles)
        or any(
            not _sha256_value(cycle.get("topology_sha256"))
            or cycle["topology_sha256"] != measurements["topology_sha256"]
            or any(
                type(cycle.get(field)) not in {int, float}
                or isinstance(cycle[field], bool)
                or not 0 <= cycle[field] <= 100
                for field in cycle_bar_fields
            )
            or any(
                type(cycle.get(field)) is not int
                or isinstance(cycle[field], bool)
                or cycle[field] < 0
                for field in cycle_vram_fields
            )
            or type(cycle.get("unload_wait_seconds")) not in {int, float}
            or isinstance(cycle["unload_wait_seconds"], bool)
            or cycle["unload_wait_seconds"] < 0
            for cycle in cycles
        )
    ):
        return False
    phase_hashes = containment.get("phase_hashes")
    if not (
        type(containment.get("clean")) is bool
        and type(phase_hashes) is dict
        and set(phase_hashes) == _ASSEMBLY_CONTAINMENT_PHASES
        and all(_sha256_value(value) for value in phase_hashes.values())
        and _sha256_value(phase_evidence.get("owner_voice_sha256"))
        and _sha256_value(phase_evidence.get("rollback_sha256"))
        and _sha256_value(
            phase_evidence.get("boot_authorization_sha256")
        )
        and _sha256_value(
            phase_evidence.get("live_authorization_sha256")
        )
        and phase_evidence.get("cold_boot_sha256") is None
        and phase_evidence.get("provisional_live_sha256") is None
        and phase_evidence.get("provisional_live_output_lengths") == []
        and phase_evidence["boot_authorization_sha256"]
        == gate["boot_authorization_sha256"]
        and phase_evidence["live_authorization_sha256"]
        == gate["live_authorization_sha256"]
        and gate["containment_sha256"]
        == hashlib.sha256(
            json.dumps(
                phase_hashes,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    ):
        return False
    return True


def _valid_assembly_receipt_result(
    attempt: driver.CommandAttempt,
    result: TerminalResult,
    *,
    root: Path,
) -> bool:
    if (
        result.window_id is not None
        or result.artifact_ref != _expected_terminal_ref(attempt)
        or result.artifact_sha256 is None
    ):
        return False
    try:
        wrapper = _read_canonical_terminal_wrapper(result, root=root)
        if (
            wrapper is None
            or set(wrapper) != {"schema", "binding_sha256", "fields"}
            or wrapper["schema"] != driver.ASSEMBLE_RECEIPT_SCHEMA
            or type(wrapper["fields"]) is not dict
        ):
            return False
        receipt = wrapper["fields"]
        binding = wrapper["binding_sha256"]
        if result.status == "ok":
            return (
                result.outcome in {"bench_passed", "keep_vulkan"}
                and _sha256_value(binding)
                and _valid_assembly_success_fields(
                    receipt,
                    binding=binding,
                    outcome=result.outcome,
                )
            )
        return (
            result.status in {"refused", "failed"}
            and result.outcome
            == (
                "assembly_refused"
                if result.status == "refused"
                else "provider_uncertain"
            )
            and binding is None
            and set(receipt) == {"outcome", "timestamp"}
            and receipt["outcome"] == result.outcome
            and _utc_timestamp_value(
                receipt["timestamp"],
                allow_none=result.status == "failed",
            )
        )
    except Exception:
        return False


def _valid_terminal_result(
    attempt: driver.CommandAttempt,
    result: TerminalResult,
    *,
    root: Path,
) -> bool:
    expected_schema = _TERMINAL_SCHEMA_MATRIX.get(attempt.command)
    if expected_schema is None:
        return False
    if expected_schema == driver.ASSEMBLE_RECEIPT_SCHEMA:
        return _valid_assembly_receipt_result(attempt, result, root=root)
    if expected_schema == cm.COMMAND_COMPLETION_SCHEMA:
        return (
            _valid_command_completion_result(attempt, result, root=root)
            if result.status == "ok"
            else _valid_production_refusal_result(
                attempt,
                result,
                root=root,
            )
        )
    if expected_schema == driver.REHEARSAL_PACKET_SCHEMA:
        return _valid_rehearsal_result(attempt, result, root=root)
    return False


def _publish_terminal_result(
    attempt: driver.CommandAttempt,
    result: TerminalResult,
    *,
    root: Path,
) -> TerminalResult:
    policy: driver.ArtifactPolicy
    if attempt.namespace == "rehearsal":
        policy = driver.RehearsalArtifactPolicy()
    else:
        policy = driver.ProductionArtifactPolicy()
    encoded = policy.encode("refusal", {"outcome": result.outcome})
    relative, digest = driver.publish_command_artifact(
        attempt, "terminal", encoded, root=root
    )
    return TerminalResult(
        result.status,
        result.outcome,
        result.window_id,
        relative,
        digest,
    )


def _normalize_handler_result(
    attempt: driver.CommandAttempt,
    value: object,
    *,
    root: Path,
    trust_phase_results: bool = False,
) -> TerminalResult:
    trusted_phase = type(value) is _TrustedPhaseResult and trust_phase_results
    if trusted_phase:
        result = value.terminal
    elif type(value) is TerminalResult:
        result = value
    else:
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")
    if (
        result.outcome == "invocation_invalid"
        or (
            result.outcome in _CLI_RESERVED_OUTCOMES
            and not trusted_phase
        )
        or not _valid_terminal_result(attempt, result, root=root)
    ):
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")
    if result.status == "ok":
        if (
            result.artifact_ref == attempt.admission_ref
            or not _binding_matches_tier(attempt, result)
            or not _binding_is_current(result, root=root)
        ):
            return _admission_result(
                attempt, status="failed", outcome="provider_uncertain"
            )
        return result
    if result.artifact_ref is None:
        try:
            return _publish_terminal_result(attempt, result, root=root)
        except driver.BenchRefusal as exc:
            if exc.code == "cleanup_incomplete":
                return _cleanup_incomplete_result(attempt)
            return _admission_result(
                attempt, status="failed", outcome="provider_uncertain"
            )
        except Exception:
            return _admission_result(
                attempt, status="failed", outcome="provider_uncertain"
            )
    if (
        not _binding_matches_tier(attempt, result)
        or not _binding_is_current(result, root=root)
    ):
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")
    return result


def _exception_result(
    attempt: driver.CommandAttempt,
    *,
    root: Path,
    status: Literal["refused", "failed"],
    outcome: str,
) -> TerminalResult:
    provisional = TerminalResult(status, outcome, None, None, None)
    try:
        return _publish_terminal_result(attempt, provisional, root=root)
    except driver.BenchRefusal as exc:
        if exc.code == "cleanup_incomplete":
            return _cleanup_incomplete_result(attempt)
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")
    except Exception:
        if _cleanup_incomplete_committing:
            return _cleanup_incomplete_result(attempt)
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")


def _run_command(
    command: str,
    handler: Callable[..., object],
    *,
    root: Path,
    clock: driver.Clock,
    authority_ref: str | None = None,
) -> int:
    global _cleanup_incomplete_committing, _linearized_durable_success
    global _terminal_committed
    _terminal_committed = False
    _cleanup_incomplete_committing = False
    _linearized_durable_success = None
    old_handlers: dict[signal.Signals, object] = {}
    attempt: driver.CommandAttempt | None = None
    authorization: driver.WindowAuthorization | driver.Continuation | None = None
    window_id: str | None = None

    def latch_admission(value: driver.CommandAttempt) -> None:
        nonlocal attempt
        attempt = value

    def suppress_cleanup_interruption() -> None:
        global _cleanup_incomplete_committing
        _cleanup_incomplete_committing = True

    try:
        try:
            old_handlers, old_mask = _enter_command_signal_scope()
            _pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except driver._CommandInterrupted as interrupted:
            terminal = TerminalResult(
                "refused", "interrupted", None, None, None
            )
            return _commit_terminal(
                terminal,
                interrupted_signum=interrupted.signum,
                interruption_fallback=terminal,
            )
        except Exception:
            terminal = TerminalResult(
                "failed", "provider_uncertain", None, None, None
            )
            return _commit_terminal(terminal)
        try:
            policy: driver.ArtifactPolicy
            if command == "rehearse":
                policy = driver.RehearsalArtifactPolicy()
            else:
                policy = driver.ProductionArtifactPolicy()
        except Exception:
            terminal = TerminalResult(
                "failed", "provider_uncertain", None, None, None
            )
            return _commit_terminal(terminal)
        if command in {"vulkan-baseline", "cuda-candidate"}:
            try:
                if authority_ref is None:
                    raise driver.BenchRefusal("invocation_invalid")
                authority_bytes = driver.open_bench_file(authority_ref, root=root)
                authorization = (
                    driver.parse_window_authorization(authority_bytes)
                    if command == "vulkan-baseline"
                    else driver.parse_continuation(authority_bytes)
                )
                window_id = authorization.window_id
                if not window_id:
                    raise driver.BenchRefusal("authorization_window_mismatch")
            except driver.BenchRefusal as exc:
                terminal = TerminalResult("refused", exc.code, None, None, None)
                return _commit_terminal(terminal)
            except (TypeError, ValueError):
                terminal = TerminalResult(
                    "refused", "authorization_malformed", None, None, None
                )
                return _commit_terminal(terminal)
        try:
            attempt = driver._admit_command(
                command=command,
                window_id=window_id,
                policy=policy,
                clock=clock,
                root=root,
                _on_latched=latch_admission,
                _on_cleanup_incomplete=suppress_cleanup_interruption,
            )
            if type(handler) is _ProductionPhaseHandler:
                if authorization is None:
                    raise driver.BenchRefusal("authorization_malformed")
                value = handler(
                    attempt,
                    root=root,
                    authorization=authorization,
                    _cleanup_incomplete_observer=suppress_cleanup_interruption,
                )
            else:
                value = (
                    handler(attempt, root=root, authorization=authorization)
                    if authorization is not None
                    else handler(attempt, root=root)
                )
            terminal = (
                _normalize_handler_result(
                    attempt,
                    value,
                    root=root,
                    trust_phase_results=True,
                )
                if type(handler) is _ProductionPhaseHandler
                else _normalize_handler_result(attempt, value, root=root)
            )
        except driver._CommandInterrupted as interrupted:
            bound = interrupted.attempt if interrupted.attempt is not None else attempt
            terminal = TerminalResult(
                "refused",
                "interrupted",
                window_id,
                None if bound is None else bound.admission_ref,
                None if bound is None else bound.admission_sha256,
            )
            return _commit_terminal(
                terminal,
                interrupted_signum=interrupted.signum,
                interruption_fallback=terminal,
            )
        except driver._StorageIndependentCleanupIncomplete:
            terminal = (
                _cleanup_incomplete_result(None)
                if type(handler) is _ProductionPhaseHandler
                else (
                    TerminalResult(
                        "failed", "provider_uncertain", None, None, None
                    )
                    if attempt is None
                    else _admission_result(
                        attempt,
                        status="failed",
                        outcome="provider_uncertain",
                    )
                )
            )
        except _AssemblyTerminalPublicationFailure:
            terminal = (
                TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
                if attempt is None
                else _admission_result(
                    attempt,
                    status="failed",
                    outcome="provider_uncertain",
                )
            )
        except _StaticTerminalPublicationFailure as exc:
            if attempt is None:
                terminal = TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
            else:
                terminal = _admission_result(
                    attempt, status="refused", outcome=exc.code
                )
        except driver.BenchRefusal as exc:
            if exc.code == "cleanup_incomplete":
                _cleanup_incomplete_committing = True
                terminal = _cleanup_incomplete_result(attempt)
            if exc.code == "interrupted":
                terminal = (
                    TerminalResult(
                        "failed", "provider_uncertain", None, None, None
                    )
                    if attempt is None
                    else _admission_result(
                        attempt,
                        status="failed",
                        outcome="provider_uncertain",
                    )
                )
            elif exc.code == "cleanup_incomplete":
                pass
            elif attempt is None:
                status: Literal["refused", "failed"] = (
                    "failed" if exc.code == "cleanup_incomplete" else "refused"
                )
                terminal = TerminalResult(status, exc.code, None, None, None)
            else:
                terminal = _exception_result(
                    attempt,
                    root=root,
                    status=(
                        "failed" if exc.code == "cleanup_incomplete" else "refused"
                    ),
                    outcome=exc.code,
                )
        except Exception:
            if _cleanup_incomplete_committing:
                terminal = _cleanup_incomplete_result(attempt)
            elif attempt is None:
                terminal = TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
            else:
                terminal = _exception_result(
                    attempt,
                    root=root,
                    status="failed",
                    outcome="provider_uncertain",
                )
        fallback = (
            None
            if attempt is None
            else _admission_result(
                attempt, status="refused", outcome="interrupted"
            )
        )
        if attempt is not None and window_id is not None and terminal.window_id is None:
            terminal = TerminalResult(
                terminal.status,
                terminal.outcome,
                window_id,
                terminal.artifact_ref,
                terminal.artifact_sha256,
            )
        if (
            fallback is not None
            and window_id is not None
            and fallback.window_id is None
        ):
            fallback = TerminalResult(
                fallback.status,
                fallback.outcome,
                window_id,
                fallback.artifact_ref,
                fallback.artifact_sha256,
            )
        return _commit_terminal(terminal, interruption_fallback=fallback)
    except driver._CommandInterrupted as interrupted:
        bound = interrupted.attempt if interrupted.attempt is not None else attempt
        terminal = TerminalResult(
            "refused",
            "interrupted",
            window_id,
            None if bound is None else bound.admission_ref,
            None if bound is None else bound.admission_sha256,
        )
        return _commit_terminal(
            terminal,
            interrupted_signum=interrupted.signum,
            interruption_fallback=terminal,
        )
    finally:
        _restore_command_signal_scope(old_handlers)
        _cleanup_incomplete_committing = False


def _unimplemented_handler(
    _attempt: driver.CommandAttempt, *, root: Path
) -> TerminalResult:
    del root
    return TerminalResult("refused", "assembly_refused", None, None, None)


def _publish_assembly_receipt(
    attempt: driver.CommandAttempt,
    *,
    document: dict[str, object],
    status: Literal["ok", "refused", "failed"],
    outcome: str,
    root: Path,
) -> TerminalResult:
    committed: TerminalResult | None = None

    def latch_receipt(relative: str, digest: str) -> None:
        nonlocal committed
        candidate = TerminalResult(
            status,
            outcome,
            None,
            relative,
            digest,
        )
        try:
            _latch_durable_success(
                candidate,
                root=root,
                semantic_validator=lambda: _valid_assembly_receipt_result(
                    attempt,
                    candidate,
                    root=root,
                ),
            )
        except driver.BenchRefusal as exc:
            if exc.code == "cleanup_incomplete":
                raise
            raise _AssemblyTerminalPublicationFailure from None
        except Exception:
            raise _AssemblyTerminalPublicationFailure from None
        committed = candidate

    try:
        encoded = driver.ProductionArtifactPolicy().encode(
            "receipt",
            document,
        )
        relative, digest = driver.publish_command_artifact(
            attempt,
            "terminal",
            encoded,
            root=root,
            on_committed=latch_receipt,
        )
    except driver._CommandInterrupted:
        raise
    except driver.BenchRefusal as exc:
        if exc.code == "cleanup_incomplete":
            raise
        raise _AssemblyTerminalPublicationFailure from None
    except _AssemblyTerminalPublicationFailure:
        raise
    except Exception:
        raise _AssemblyTerminalPublicationFailure from None
    if (
        committed is None
        or committed.artifact_ref != relative
        or committed.artifact_sha256 != digest
    ):
        raise _AssemblyTerminalPublicationFailure
    return committed


def _assembly_handler(
    attempt: driver.CommandAttempt,
    *,
    root: Path,
    clock: driver.Clock,
    args: argparse.Namespace,
) -> TerminalResult:
    timestamp: str | None = None
    try:
        timestamp = clock.now_utc()
        paths = assemble.Stage1ArtifactPaths(
            **{
                field.name: getattr(args, field.name)
                for field in fields(assemble.Stage1ArtifactPaths)
            }
        )
        evaluation = assemble.assemble_stage1(
            paths,
            root=root,
            timestamp=timestamp,
        )
        if (
            type(evaluation) is not assemble.Stage1Evaluation
            or evaluation.verdict.decision
            not in {"bench_passed", "keep_vulkan"}
            or evaluation.receipt.get("decision")
            != evaluation.verdict.decision
            or evaluation.receipt.get("bench_binding_sha256")
            != evaluation.bundle.bench_binding_sha256
            or evaluation.receipt.get("bundle_binding_sha256")
            != evaluation.bundle.binding_sha256
        ):
            raise ValueError("assembly_evaluation")
    except driver.BenchRefusal as exc:
        if exc.code != "assembly_refused":
            return _publish_assembly_receipt(
                attempt,
                document={
                    "binding_sha256": None,
                    "outcome": "provider_uncertain",
                    "timestamp": timestamp,
                },
                status="failed",
                outcome="provider_uncertain",
                root=root,
            )
        return _publish_assembly_receipt(
            attempt,
            document={
                "binding_sha256": None,
                "outcome": "assembly_refused",
                "timestamp": timestamp,
            },
            status="refused",
            outcome="assembly_refused",
            root=root,
        )
    except Exception:
        return _publish_assembly_receipt(
            attempt,
            document={
                "binding_sha256": None,
                "outcome": "provider_uncertain",
                "timestamp": timestamp,
            },
            status="failed",
            outcome="provider_uncertain",
            root=root,
        )
    receipt = dict(evaluation.receipt)
    receipt["binding_sha256"] = evaluation.bundle.binding_sha256
    return _publish_assembly_receipt(
        attempt,
        document=receipt,
        status="ok",
        outcome=evaluation.verdict.decision,
        root=root,
    )


def _rehearsal_providers(
    static: cm.StaticPreflightDoc,
    *,
    clock: driver.RehearsalClock,
) -> driver.Providers:
    registry = driver.RehearsalPortRegistry()
    port_probe = driver.SyntheticPortProbe(
        {driver.BENCH_PORT, *driver.PRODUCTION_PORTS},
        rehearsal_ports=registry,
    )
    policy = driver.RehearsalArtifactPolicy()
    memories = [
        value
        for _cycle in range(3)
        for value in (
            (1.0, 100),
            (2.0, 200),
            (3.0, 250),
            (1.0, 100),
        )
    ]
    memories.extend(((1.0, 100), (1.0, 100), (1.0, 100)))
    pin = driver.SpawnPin(
        kind="python_file",
        pinned_path=driver._REHEARSAL_STUB_PATH,
        pinned_sha256=static.stub_sha256,
        required_argv_prefix=(
            sys.executable,
            "-B",
            "-I",
            str(driver._REHEARSAL_STUB_PATH),
        ),
    )
    return driver.rehearsal_tier(
        service_state=driver.SyntheticServiceState(
            {
                "llama-server.service": "inactive",
                "llama-judge.service": "inactive",
                driver.VISION_UNIT: "inactive",
            }
        ),
        port_probe=port_probe,
        gpu=driver.SyntheticGpu(
            [static.gpu_uuid],
            [[] for _index in range(16)],
            memories,
        ),
        kernel_log=driver.SyntheticKernelLog(
            dict.fromkeys(driver.KERNEL_COUNTER_KEYS, 0)
        ),
        backend_maps=driver.SyntheticBackendMap(
            {},
            default_maps_text=str(
                cm.VULKAN_RELEASE_ROOT / "libggml-vulkan.so"
            ),
        ),
        server_launcher=driver.RehearsalServerLauncher(
            pin,
            rehearsal_ports=registry,
        ),
        server_client=driver.LoopbackServerClient.rehearsal(
            clock,
            request_timeout_ms=REHEARSAL_REQUEST_TIMEOUT_MS,
        ),
        authorization_gate=driver.RehearsalAuthorizationGate(policy),
        containment=driver.SyntheticContainmentProvider(
            clock=clock,
            port_probe=port_probe,
            flag_source_sha256=static.checks["flag_source"],
            vision_unit_sha256=static.checks["vision_unit"],
        ),
        artifact_policy=policy,
        clock=clock,
        journal_factory=driver.RehearsalJournalFactory(),
    )


def _rehearsal_handler(
    attempt: driver.CommandAttempt,
    *,
    root: Path,
    clock: driver.RehearsalClock,
    static_preflight_ref: str,
    persona: str,
) -> TerminalResult:
    static, identity = _collect_rehearsal_identity(
        static_preflight_ref,
        root=root,
    )
    providers = _rehearsal_providers(static, clock=clock)
    now = datetime.fromisoformat(
        clock.now_utc().replace("Z", "+00:00")
    ).astimezone(UTC)
    issued = now - timedelta(minutes=1)
    expires = issued + timedelta(seconds=driver.WINDOW_TTL_S)
    window_id = f"rehearsal-{attempt.ordinal:03d}"
    boot_id = "rehearsal-boot"
    authorization = driver.WindowAuthorization(
        window_id=window_id,
        phases=("vulkan_baseline",),
        boot_id=boot_id,
        nonce=hashlib.sha256(
            f"{attempt.admission_sha256}:{persona}".encode()
        ).hexdigest(),
        issued_at=issued.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        expires_at=expires.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        owner="rehearsal",
    )
    identity_fields = driver._runtime_identity_fields(identity)
    identity_fields["effective_args"] = tuple(identity.effective_args)
    argv = [
        sys.executable,
        "-B",
        "-I",
        str(driver._REHEARSAL_STUB_PATH),
        "--persona",
        persona,
        "--alias",
        cm.FROZEN_ALIAS,
    ]
    config = driver.PhaseConfig(
        phase="vulkan_baseline",
        argv=argv,
        env={
            "HOME": "/home/rohit",
            "PATH": "/usr/bin:/bin",
            "PYTHONUNBUFFERED": "1",
        },
        alias=cm.FROZEN_ALIAS,
        prompts=_REHEARSAL_PROMPTS,
        authorization=authorization,
        parent_window=None,
        parent_packet_path=None,
        bench_identity_fields=dict(identity_fields),
        runtime_identity_fields=dict(identity_fields),
        static_preflight_path=static_preflight_ref,
        gpu_uuid=static.gpu_uuid,
        boot_id=boot_id,
        window_id=window_id,
        expected_port=None,
        readiness_timeout_s=REHEARSAL_READINESS_TIMEOUT_S,
    )
    phase_path = driver.run_phase(config, providers, root=root)
    try:
        phase_ref = str(phase_path.relative_to(root))
        phase_bytes = driver.open_bench_file(phase_ref, root=root)
        wrapper = json.loads(phase_bytes)
        payload = wrapper["payload"]
        fields = payload["fields"]
        if (
            set(wrapper) != {"rehearsal_schema", "tier", "payload"}
            or wrapper["rehearsal_schema"]
            != driver.REHEARSAL_PACKET_SCHEMA
            or wrapper["tier"] != "rehearsal"
            or type(payload) is not dict
            or type(fields) is not dict
            or type(fields.get("outcome")) is not str
        ):
            raise ValueError("rehearsal_document")
        outcome = fields["outcome"]
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ):
        raise driver.BenchRefusal("provider_uncertain") from None
    return TerminalResult(
        "ok" if outcome == "completed" else "refused",
        outcome,
        None,
        phase_ref,
        hashlib.sha256(phase_bytes).hexdigest(),
    )


def _production_providers(
    phase: Literal["vulkan_baseline", "cuda_candidate"],
    identity: cm.RuntimeIdentity,
    release_proof: driver.ReleaseDirectoryProof,
) -> driver.Providers:
    if (
        phase not in {"vulkan_baseline", "cuda_candidate"}
        or type(identity) is not cm.RuntimeIdentity
        or type(release_proof) is not driver.ReleaseDirectoryProof
    ):
        raise driver.BenchRefusal("identity_mismatch")
    runtime = (
        cm.VULKAN_RELEASE_ROOT
        if phase == "vulkan_baseline"
        else cm.CUDA_RELEASE_ROOT
    ) / "llama-server"
    runtime_sha256 = (
        cm.FROZEN_VULKAN_RUNTIME_SHA256
        if phase == "vulkan_baseline"
        else identity.runtime_sha256
    )
    clock = driver.SystemClock()
    port_probe = driver.RealPortProbe()
    policy = driver.ProductionArtifactPolicy()
    return driver.production_tier(
        service_state=driver.RealServiceStateProvider(),
        port_probe=port_probe,
        gpu=driver.RealGpuProvider(),
        kernel_log=driver.RealKernelLogProvider(),
        backend_maps=driver.RealBackendMapProvider(),
        server_launcher=driver.RealServerLauncher(
            driver.SpawnPin(
                kind="binary",
                pinned_path=runtime,
                pinned_sha256=runtime_sha256,
                required_argv_prefix=(str(runtime),),
            ),
            release_proof,
        ),
        server_client=driver.LoopbackServerClient.production(clock),
        authorization_gate=driver.RealAuthorizationGate(policy),
        containment=driver.RealContainmentProvider(
            clock=clock, port_probe=port_probe
        ),
        artifact_policy=policy,
        clock=clock,
        journal_factory=driver.ProductionJournalFactory(),
    )


def _identity_fields(identity: cm.RuntimeIdentity) -> dict[str, object]:
    fields = driver._runtime_identity_fields(identity)
    fields["effective_args"] = tuple(identity.effective_args)
    return fields


def _vulkan_config(
    args: argparse.Namespace,
    observation: StaticObservation,
) -> driver.PhaseConfig:
    root = args._root
    authorization = args._authorization
    if (
        not isinstance(root, Path)
        or type(authorization) is not driver.WindowAuthorization
        or type(observation) is not StaticObservation
        or type(observation.runtime_identity) is not cm.RuntimeIdentity
    ):
        raise driver.BenchRefusal("identity_mismatch")
    identity_fields = _identity_fields(observation.runtime_identity)
    runtime = cm.VULKAN_RELEASE_ROOT / "llama-server"
    return driver.PhaseConfig(
        phase="vulkan_baseline",
        argv=[str(runtime), *FROZEN_BENCH_ARGV_TAIL],
        env=dict(driver._PHASE_BENCH_ENVIRONMENTS["vulkan_baseline"]),
        alias=cm.FROZEN_ALIAS,
        prompts=_load_frozen_prompts(root=root),
        authorization=authorization,
        parent_window=None,
        parent_packet_path=None,
        bench_identity_fields=dict(identity_fields),
        runtime_identity_fields=dict(identity_fields),
        static_preflight_path=args.static_preflight,
        static_admission_path=args.static_admission,
        static_completion_path=args.static_completion,
        gpu_uuid=observation.static_doc.gpu_uuid,
        boot_id=_read_boot_id(),
        window_id=authorization.window_id,
        expected_port=driver.BENCH_PORT,
        readiness_timeout_s=driver.READINESS_TIMEOUT_S,
    )


def _cuda_config(
    args: argparse.Namespace,
    observation: StaticObservation,
) -> driver.PhaseConfig:
    root = args._root
    continuation = args._authorization
    if (
        not isinstance(root, Path)
        or type(continuation) is not driver.Continuation
        or type(observation) is not StaticObservation
        or type(observation.runtime_identity) is not cm.RuntimeIdentity
    ):
        raise driver.BenchRefusal("identity_mismatch")
    try:
        parent_window = driver.parse_window_authorization(
            driver.open_bench_file(args.parent_window, root=root)
        )
    except driver.BenchRefusal:
        raise
    except (TypeError, ValueError):
        raise driver.BenchRefusal("continuation_parent_mismatch") from None
    identity_fields = _identity_fields(observation.runtime_identity)
    runtime = cm.CUDA_RELEASE_ROOT / "llama-server"
    return driver.PhaseConfig(
        phase="cuda_candidate",
        argv=[str(runtime), *FROZEN_BENCH_ARGV_TAIL],
        env=dict(driver._PHASE_BENCH_ENVIRONMENTS["cuda_candidate"]),
        alias=cm.FROZEN_ALIAS,
        prompts=_load_frozen_prompts(root=root),
        authorization=continuation,
        parent_window=parent_window,
        parent_packet_path=args.parent_packet,
        parent_admission_path=args.parent_admission,
        parent_completion_path=args.parent_completion,
        bench_identity_fields=dict(identity_fields),
        runtime_identity_fields=dict(identity_fields),
        static_preflight_path=args.static_preflight,
        static_admission_path=args.static_admission,
        static_completion_path=args.static_completion,
        gpu_uuid=observation.static_doc.gpu_uuid,
        boot_id=_read_boot_id(),
        window_id=continuation.window_id,
        expected_port=driver.BENCH_PORT,
        readiness_timeout_s=driver.READINESS_TIMEOUT_S,
    )


def _phase_artifact_result(
    phase_ref: str,
    *,
    expected_phase: str,
    expected_window_id: str,
    root: Path,
) -> _TrustedPhaseResult:
    try:
        payload = driver.open_bench_file(phase_ref, root=root)
        wrapper = json.loads(
            payload,
            object_pairs_hook=driver._json_object_without_duplicates,
            parse_constant=driver._reject_json_constant,
        )
        if type(wrapper) is not dict or set(wrapper) != {
            "schema",
            "binding_sha256",
            "fields",
        }:
            raise ValueError("reduced_wrapper")
        fields = wrapper["fields"]
        if type(fields) is not dict:
            raise ValueError("reduced_fields")
        spawned = fields.get("spawned")
        expected_schema = (
            driver.PHASE_PACKET_SCHEMA
            if spawned is True
            else driver.REFUSAL_SCHEMA
        )
        outcome = fields.get("outcome")
        timestamp = fields.get("timestamp")
        if (
            type(spawned) is not bool
            or wrapper["schema"] != expected_schema
            or wrapper["binding_sha256"]
            != hashlib.sha256(driver._canonical_json(fields)).hexdigest()
            or fields.get("phase") != expected_phase
            or fields.get("window_id") != expected_window_id
            or type(fields.get("boot_id")) is not str
            or not fields["boot_id"]
            or type(outcome) is not str
            or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", outcome) is None
            or type(timestamp) is not str
            or not timestamp.endswith("Z")
            or datetime.fromisoformat(timestamp.replace("Z", "+00:00")).tzinfo
            is None
        ):
            raise ValueError("reduced_binding")
        try:
            cm.decode_persisted_packet(payload)
        except ValueError:
            pass
        else:
            raise ValueError("reduced_decoded_complete")
        return _TrustedPhaseResult(
            TerminalResult(
                "failed" if spawned else "refused",
                outcome,
                expected_window_id,
                phase_ref,
                hashlib.sha256(payload).hexdigest(),
            ),
            _guard=_TRUSTED_PHASE_GUARD,
        )
    except driver.BenchRefusal:
        raise
    except (KeyError, OSError, TypeError, ValueError):
        raise driver.BenchRefusal("provider_uncertain") from None


def _completion_fields(completion: cm.CommandCompletionDoc) -> dict[str, object]:
    return {
        "binding_sha256": completion.binding_sha256,
        "command": completion.command,
        "ordinal": completion.ordinal,
        "window_id": completion.window_id,
        "admission_ref": completion.admission_ref,
        "admission_sha256": completion.admission_sha256,
        "artifact_ref": completion.artifact_ref,
        "artifact_sha256": completion.artifact_sha256,
        "artifact_schema": completion.artifact_schema,
        "status": completion.status,
        "timestamp": completion.timestamp,
    }


def _phase_completion_is_current(
    attempt: driver.CommandAttempt,
    result: TerminalResult,
    *,
    phase_ref: str,
    phase_identity: tuple[int, ...],
    root: Path,
) -> bool:
    try:
        before = os.stat(root / phase_ref, follow_symlinks=False)
    except OSError:
        return False
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.geteuid()
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != 0o600
        or _static_latch_identity(before) != phase_identity
        or not _valid_command_completion_result(attempt, result, root=root)
    ):
        return False
    try:
        after = os.stat(root / phase_ref, follow_symlinks=False)
    except OSError:
        return False
    return _static_latch_identity(after) == phase_identity


def _publish_phase_completion(
    attempt: driver.CommandAttempt,
    *,
    phase_ref: str,
    expected_phase: Literal["vulkan_baseline", "cuda_candidate"],
    expected_window_id: str,
    root: Path,
    clock: driver.Clock,
) -> TerminalResult:
    try:
        phase_bytes = driver.open_bench_file(phase_ref, root=root)
        packet = cm.decode_persisted_packet(phase_bytes)
    except driver.BenchRefusal:
        raise
    except (TypeError, ValueError):
        raise driver.BenchRefusal("provider_uncertain") from None
    if (
        packet.phase != expected_phase
        or packet.window_id != expected_window_id
        or packet.outcome != "completed"
        or packet.order_sha256 != cm.FROZEN_ORDER_SHA256
    ):
        raise driver.BenchRefusal("provider_uncertain")
    try:
        phase_info = os.stat(root / phase_ref, follow_symlinks=False)
        if (
            not stat.S_ISREG(phase_info.st_mode)
            or phase_info.st_uid != os.geteuid()
            or phase_info.st_nlink != 1
            or stat.S_IMODE(phase_info.st_mode) != 0o600
        ):
            raise OSError("phase packet identity")
        phase_identity = _static_latch_identity(phase_info)
    except OSError:
        raise driver.BenchRefusal("filesystem_hazard") from None
    completion = cm.CommandCompletionDoc(
        command=attempt.command,
        ordinal=attempt.ordinal,
        window_id=expected_window_id,
        admission_ref=attempt.admission_ref,
        admission_sha256=attempt.admission_sha256,
        artifact_ref=phase_ref,
        artifact_sha256=hashlib.sha256(phase_bytes).hexdigest(),
        artifact_schema=cm.PHASE_PACKET_SCHEMA,
        status="completed",
        timestamp=clock.now_utc(),
    )
    encoded = driver.ProductionArtifactPolicy().encode(
        "command_completion", _completion_fields(completion)
    )
    completed: TerminalResult | None = None

    def latch_completion(completion_ref: str, completion_sha256: str) -> None:
        nonlocal completed
        candidate = TerminalResult(
            "ok",
            "completed",
            expected_window_id,
            completion_ref,
            completion_sha256,
        )
        _latch_durable_success(
            candidate,
            root=root,
            semantic_validator=lambda: _valid_command_completion_result(
                attempt, candidate, root=root
            )
            and _phase_completion_is_current(
                attempt,
                candidate,
                phase_ref=phase_ref,
                phase_identity=phase_identity,
                root=root,
            ),
        )
        completed = candidate

    completion_ref, completion_sha256 = driver.publish_command_artifact(
        attempt,
        "terminal",
        encoded,
        root=root,
        on_committed=latch_completion,
    )
    if (
        completed is None
        or completed.artifact_ref != completion_ref
        or completed.artifact_sha256 != completion_sha256
    ):
        raise driver.BenchRefusal("filesystem_hazard")
    return completed


def _phase_handler(
    attempt: driver.CommandAttempt,
    *,
    root: Path,
    clock: driver.Clock,
    args: argparse.Namespace,
    authorization: driver.WindowAuthorization | driver.Continuation,
    _cleanup_incomplete_observer: Callable[[], None] | None = None,
) -> TerminalResult | _TrustedPhaseResult:
    observation = collect_static_observation(root=root, clock=clock)
    try:
        selected = cm.PersistedDoc(
            driver.open_bench_file(args.static_preflight, root=root)
        ).obj
    except driver.BenchRefusal:
        raise
    except (TypeError, ValueError):
        raise driver.BenchRefusal("identity_mismatch") from None
    if type(selected) is not cm.StaticPreflightDoc:
        raise driver.BenchRefusal("identity_mismatch")
    _require_static_match(selected, observation.static_doc)
    preimage_sha256 = hashlib.sha256(observation.rollback_preimage).hexdigest()
    driver.verify_existing_immutable(
        f"preimages/rollback-manifest-{preimage_sha256}.json",
        observation.rollback_preimage,
        attempt=attempt,
        root=root,
    )
    args._root = root
    args._authorization = authorization
    config = (
        _vulkan_config(args, observation)
        if args.command == "vulkan-baseline"
        else _cuda_config(args, observation)
    )
    if config.window_id != authorization.window_id:
        raise driver.BenchRefusal("authorization_window_mismatch")
    release_proof = (
        observation.vulkan_release_proof
        if config.phase == "vulkan_baseline"
        else observation.cuda_release_proof
    )
    providers = _production_providers(
        config.phase,
        observation.runtime_identity,
        release_proof,
    )
    phase_path = driver.run_phase(
        config,
        providers,
        root=root,
        _cleanup_incomplete_observer=_cleanup_incomplete_observer,
    )
    try:
        phase_ref = str(phase_path.relative_to(root))
    except ValueError:
        raise driver.BenchRefusal("provider_uncertain") from None
    try:
        packet = cm.decode_persisted_packet(
            driver.open_bench_file(phase_ref, root=root)
        )
    except driver.BenchRefusal:
        raise
    except (TypeError, ValueError):
        return _phase_artifact_result(
            phase_ref,
            expected_phase=config.phase,
            expected_window_id=config.window_id,
            root=root,
        )
    if (
        packet.phase != config.phase
        or packet.window_id != config.window_id
        or packet.outcome != "completed"
        or packet.order_sha256 != cm.FROZEN_ORDER_SHA256
    ):
        raise driver.BenchRefusal("provider_uncertain")
    return _publish_phase_completion(
        attempt,
        phase_ref=phase_ref,
        expected_phase=config.phase,
        expected_window_id=config.window_id,
        root=root,
        clock=clock,
    )


_PRODUCTION_PHASE_HANDLER_GUARD = object()


@dataclass(frozen=True, slots=True, init=False)
class _ProductionPhaseHandler:
    clock: driver.Clock
    args: argparse.Namespace

    def __init__(
        self,
        *,
        clock: driver.Clock,
        args: argparse.Namespace,
        _guard: object,
    ) -> None:
        if _guard is not _PRODUCTION_PHASE_HANDLER_GUARD:
            raise ValueError("production_phase_handler")
        object.__setattr__(self, "clock", clock)
        object.__setattr__(self, "args", args)

    def __call__(
        self,
        attempt: driver.CommandAttempt,
        *,
        root: Path,
        authorization: driver.WindowAuthorization | driver.Continuation,
        _cleanup_incomplete_observer: Callable[[], None],
    ) -> TerminalResult | _TrustedPhaseResult:
        return _phase_handler(
            attempt,
            root=root,
            clock=self.clock,
            args=self.args,
            authorization=authorization,
            _cleanup_incomplete_observer=_cleanup_incomplete_observer,
        )


def main(argv: Sequence[str] | None = None) -> int:
    global _cleanup_incomplete_committing, _linearized_durable_success
    global _terminal_committed
    _terminal_committed = False
    _cleanup_incomplete_committing = False
    _linearized_durable_success = None
    old_handlers: dict[signal.Signals, object] = {}
    try:
        try:
            old_handlers, old_mask = _enter_command_signal_scope()
            _pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except driver._CommandInterrupted as interrupted:
            return _commit_terminal(
                TerminalResult("refused", "interrupted", None, None, None),
                interrupted_signum=interrupted.signum,
            )
        except Exception:
            return _commit_terminal(
                TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
            )
        try:
            parsed = build_parser().parse_args(argv)
        except InvocationRefusal:
            return _commit_terminal(
                TerminalResult("refused", "invocation_invalid", None, None, None)
            )
        except driver._CommandInterrupted as interrupted:
            return _commit_terminal(
                TerminalResult("refused", "interrupted", None, None, None),
                interrupted_signum=interrupted.signum,
            )
        except Exception:
            return _commit_terminal(
                TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
            )
        command = parsed.command
        try:
            clock: driver.Clock = (
                driver.RehearsalClock()
                if command == "rehearse"
                else driver.SystemClock()
            )
        except Exception:
            return _commit_terminal(
                TerminalResult(
                    "failed", "provider_uncertain", None, None, None
                )
            )
        handler: Callable[..., object] = _unimplemented_handler
        if command == "static-preflight":
            def static_handler(
                attempt: driver.CommandAttempt, *, root: Path
            ) -> TerminalResult:
                return _static_preflight_handler(
                    attempt, root=root, clock=clock
                )

            handler = static_handler
        elif command == "rehearse":
            if type(clock) is not driver.RehearsalClock:
                return _commit_terminal(
                    TerminalResult(
                        "failed", "provider_uncertain", None, None, None
                    )
                )

            def rehearsal_handler(
                attempt: driver.CommandAttempt, *, root: Path
            ) -> TerminalResult:
                return _rehearsal_handler(
                    attempt,
                    root=root,
                    clock=clock,
                    static_preflight_ref=parsed.static_preflight,
                    persona=parsed.persona,
                )

            handler = rehearsal_handler
        elif command in {"vulkan-baseline", "cuda-candidate"}:
            handler = _ProductionPhaseHandler(
                clock=clock,
                args=parsed,
                _guard=_PRODUCTION_PHASE_HANDLER_GUARD,
            )
        elif command == "assemble-stage1":
            def assembly_handler(
                attempt: driver.CommandAttempt, *, root: Path
            ) -> TerminalResult:
                return _assembly_handler(
                    attempt,
                    root=root,
                    clock=clock,
                    args=parsed,
                )

            handler = assembly_handler
        return _run_command(
            command,
            handler,
            root=driver.BENCH_ROOT,
            clock=clock,
            authority_ref=(
                parsed.window_authorization
                if command == "vulkan-baseline"
                else (
                    parsed.continuation
                    if command == "cuda-candidate"
                    else None
                )
            ),
        )
    except driver._CommandInterrupted as interrupted:
        return _commit_terminal(
            TerminalResult("refused", "interrupted", None, None, None),
            interrupted_signum=interrupted.signum,
        )
    finally:
        _restore_command_signal_scope(
            old_handlers, restore_mask=not _terminal_committed
        )
        _cleanup_incomplete_committing = False


if __name__ == "__main__":
    raise SystemExit(main())
