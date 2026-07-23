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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from types import FrameType
from types import MappingProxyType
from typing import Literal, Never, Protocol

from scripts import cuda_bench_driver as driver
from scripts import cuda_migration as cm


PUBLIC_COMMANDS = (
    "static-preflight",
    "rehearse",
    "vulkan-baseline",
    "cuda-candidate",
    "assemble-stage1",
)
_WATCHED_SIGNALS = frozenset({signal.SIGINT, signal.SIGTERM})
_CLI_RESERVED_OUTCOMES = frozenset({"cleanup_incomplete", "interrupted"})
_pthread_sigmask = signal.pthread_sigmask
_terminal_committed = False
_cleanup_incomplete_committing = False
_linearized_static_success: _StaticSuccessLatch | None = None
_STATIC_READ_BYTE_CAP = 32 * 1024 * 1024 * 1024
_STATIC_COMMAND_TIMEOUT_S = 30
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


class ReadOnlyRunner(Protocol):
    def __call__(
        self, argv: tuple[str, ...], *, timeout_s: int
    ) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True, slots=True)
class _CandidateObservation:
    runtime_sha256: str
    runtime_manifest_sha256: str
    library_hashes: Mapping[str, str]


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
        observation = _CandidateObservation(
            runtime_sha256=server_sha,
            runtime_manifest_sha256=manifest_sha,
            library_hashes=MappingProxyType(libraries),
        )
        _require_static_directory_bound(directory_fd, root)
        return observation
    except OSError:
        raise driver.BenchRefusal("identity_mismatch") from None
    finally:
        os.close(directory_fd)


def _vulkan_library_manifest(root: Path) -> str:
    directory_fd = _open_static_directory(root)
    try:
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
    finally:
        os.close(directory_fd)


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


def _validate_frozen_corpus(*, root: Path) -> str:
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
        return cm.FROZEN_CORPUS_SHA256
    except driver.BenchRefusal as exc:
        if exc.code == "corpus_unavailable":
            raise
        raise driver.BenchRefusal("corpus_unavailable") from None
    except (TypeError, ValueError):
        raise driver.BenchRefusal("corpus_unavailable") from None


def _collect_static_asset_hashes(paths: StaticAssetPaths) -> _AssetObservation:
    unit_sha, _ = _stable_regular_file(paths.unit)
    dropin_sha, _ = _stable_regular_file(paths.dropin)
    runtime_sha, _ = _stable_regular_file(paths.vulkan_root / "llama-server")
    model_sha, model_bytes = _stable_regular_file(paths.model)
    override_sha, _ = _stable_regular_file(paths.cuda_override)
    flag_sha, _ = _stable_regular_file(paths.flag_source)
    vision_sha, _ = _stable_regular_file(paths.vision_unit)
    stub_sha, _ = _stable_regular_file(paths.stub)
    manifest_sha = _vulkan_library_manifest(paths.vulkan_root)
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
    corpus_sha = _validate_frozen_corpus(root=root)
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
    return StaticObservation(static_doc, identity, rollback_preimage)


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
class _StaticSuccessLatch:
    result: TerminalResult
    root: Path
    root_identity: tuple[int, ...]
    receipt_identity: tuple[int, ...]


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


def _static_success_latch_is_current(latch: _StaticSuccessLatch) -> bool:
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
    return (
        hashlib.sha256(payload).hexdigest() == result.artifact_sha256
        and stat.S_ISDIR(root_info.st_mode)
        and _static_latch_identity(root_info) == latch.root_identity
        and stat.S_ISREG(receipt_info.st_mode)
        and receipt_info.st_uid == os.geteuid()
        and receipt_info.st_nlink == 1
        and stat.S_IMODE(receipt_info.st_mode) == 0o600
        and _static_latch_identity(receipt_info) == latch.receipt_identity
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
    global _linearized_static_success
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
            global _linearized_static_success
            nonlocal completed
            candidate = TerminalResult(
                "ok",
                "static_preflight_ready",
                None,
                completion_ref,
                completion_sha256,
            )
            if not _binding_is_current(candidate, root=root):
                raise _StaticTerminalPublicationFailure(
                    "filesystem_hazard"
                )
            try:
                root_info = os.stat(root, follow_symlinks=False)
                receipt_info = os.stat(
                    root / completion_ref, follow_symlinks=False
                )
                if (
                    not stat.S_ISDIR(root_info.st_mode)
                    or not stat.S_ISREG(receipt_info.st_mode)
                    or receipt_info.st_uid != os.geteuid()
                    or receipt_info.st_nlink != 1
                    or stat.S_IMODE(receipt_info.st_mode) != 0o600
                ):
                    raise OSError("static receipt identity")
            except OSError:
                raise _StaticTerminalPublicationFailure(
                    "filesystem_hazard"
                ) from None
            completed = candidate
            _linearized_static_success = _StaticSuccessLatch(
                candidate,
                Path(root),
                _static_latch_identity(root_info),
                _static_latch_identity(receipt_info),
            )

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
                if _linearized_static_success is None:
                    raise


class InvocationRefusal(Exception):
    """A non-echoing argparse refusal."""


class _StaticTerminalPublicationFailure(Exception):
    """Static evidence publication failed; bind refusal to durable admission."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


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


class NonEchoingParser(argparse.ArgumentParser):
    def error(self, _message: str) -> Never:
        raise InvocationRefusal


def build_parser() -> NonEchoingParser:
    parser = NonEchoingParser(add_help=False)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in PUBLIC_COMMANDS:
        commands.add_parser(command, add_help=False)
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
    latch = _linearized_static_success
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
                latch_is_current = _static_success_latch_is_current(latch)
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
        or _linearized_static_success is not None
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
    return (
        type(completion) is cm.CommandCompletionDoc
        and persisted.file_sha256 == result.artifact_sha256
        and completion.command == attempt.command
        and completion.ordinal == attempt.ordinal
        and completion.admission_ref == attempt.admission_ref
        and completion.admission_sha256 == attempt.admission_sha256
        and completion.window_id == result.window_id
    )


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
) -> TerminalResult:
    if type(value) is not TerminalResult:
        return _admission_result(attempt, status="failed", outcome="provider_uncertain")
    result = value
    if (
        result.outcome == "invocation_invalid"
        or result.outcome in _CLI_RESERVED_OUTCOMES
        or (
            _is_command_control_ref(result.artifact_ref)
            and not _valid_command_completion_result(
                attempt, result, root=root
            )
        )
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
) -> int:
    global _cleanup_incomplete_committing, _linearized_static_success
    global _terminal_committed
    _terminal_committed = False
    _cleanup_incomplete_committing = False
    _linearized_static_success = None
    old_handlers: dict[signal.Signals, object] = {}
    attempt: driver.CommandAttempt | None = None

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
        try:
            attempt = driver._admit_command(
                command=command,
                window_id=None,
                policy=policy,
                clock=clock,
                root=root,
                _on_latched=latch_admission,
                _on_cleanup_incomplete=suppress_cleanup_interruption,
            )
            value = handler(attempt, root=root)
            terminal = _normalize_handler_result(attempt, value, root=root)
        except driver._CommandInterrupted as interrupted:
            bound = interrupted.attempt if interrupted.attempt is not None else attempt
            terminal = TerminalResult(
                "refused",
                "interrupted",
                None,
                None if bound is None else bound.admission_ref,
                None if bound is None else bound.admission_sha256,
            )
            return _commit_terminal(
                terminal,
                interrupted_signum=interrupted.signum,
                interruption_fallback=terminal,
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
        return _commit_terminal(terminal, interruption_fallback=fallback)
    except driver._CommandInterrupted as interrupted:
        bound = interrupted.attempt if interrupted.attempt is not None else attempt
        terminal = TerminalResult(
            "refused",
            "interrupted",
            None,
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


def main(argv: Sequence[str] | None = None) -> int:
    global _cleanup_incomplete_committing, _linearized_static_success
    global _terminal_committed
    _terminal_committed = False
    _cleanup_incomplete_committing = False
    _linearized_static_success = None
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
        return _run_command(
            command,
            handler,
            root=driver.BENCH_ROOT,
            clock=clock,
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
