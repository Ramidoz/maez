"""Inert CUDA A/B bench-driver core: private I/O and provider seams.

Import and provider construction perform no query, subprocess, socket, service,
or model contact. Real providers remain read-only and run only when invoked.
"""

from __future__ import annotations

import errno
import copy
import fcntl
import hashlib
import http.client
import itertools
import json
import math
import os
import re
import secrets
import select
import signal
import socket
import stat
import statistics
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Literal, NoReturn, Protocol

from scripts import cuda_migration as cm


BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")
BENCH_PORT = 18080
PRODUCTION_PORTS = (8080, 8081, 8082)
SCREEN_FLAG_SOURCE_PATH = Path("/home/rohit/.config/maez/model.env")
VISION_UNIT_PATH = Path(
    "/home/rohit/.config/systemd/user/llama-vision.service"
)
VISION_UNIT = "llama-vision.service"
MAEZ_UNIT = "maez.service"

READINESS_TIMEOUT_S = 300
REQUEST_TIMEOUT_MS = 30_000
SIGTERM_GRACE_S = 10
RESPONSE_BYTE_CAP = 4 * 1024 * 1024
TURN_ARTIFACT_BYTE_CAP = 8 * 1024 * 1024
BINARY_STDERR_DIAGNOSTIC_CAP = 65_536
WINDOW_TTL_S = 14_400
CONTINUATION_TTL_S = 3_600
KILL_WAIT_S = 15
LISTENER_WAIT_S = 10
UNLOAD_WAIT_S = 60
FROZEN_BENCH_ARGS_SHA256 = "7fd627e1132ff30fb7f45df2cbf83d166002b0a0c56bcd07e169eca2180bd413"
_SANITIZED_BENCH_PATH = (
    "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
)
_PHASE_BENCH_ENVIRONMENTS = MappingProxyType(
    {
        "vulkan_baseline": MappingProxyType(
            {
                "HOME": "/home/rohit",
                "PATH": _SANITIZED_BENCH_PATH,
                "LD_LIBRARY_PATH": str(cm.VULKAN_RELEASE_ROOT),
                "GGML_VK_VISIBLE_DEVICES": "0",
                "CUDA_VISIBLE_DEVICES": "",
            }
        ),
        "cuda_candidate": MappingProxyType(
            {
                "HOME": "/home/rohit",
                "PATH": _SANITIZED_BENCH_PATH,
                "CUDA_VISIBLE_DEVICES": "0",
                "GGML_VK_VISIBLE_DEVICES": "",
                "LD_LIBRARY_PATH": (
                    f"{cm.CUDA_RELEASE_ROOT}:{cm.CUDA_TOOLKIT_LIBRARY_ROOT}"
                ),
            }
        ),
    }
)

# Linux UAPI constants from <linux/memfd.h>.  Python 3.14 exposes the base
# memfd flags but not these two execution-policy flags on this host.
MFD_NOEXEC_SEAL = 0x0008
MFD_EXEC = 0x0010
_EXECUTABLE_MEMFD_FLAGS = os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING | MFD_EXEC
_REQUIRED_MEMFD_SEALS = (
    fcntl.F_SEAL_WRITE
    | fcntl.F_SEAL_GROW
    | fcntl.F_SEAL_SHRINK
    | fcntl.F_SEAL_SEAL
)

STATIC_PREFLIGHT_SCHEMA = "cuda_bench_driver.static_preflight.v1"
PHASE_PACKET_SCHEMA = "cuda_bench_driver.phase_packet.v2"
REFUSAL_SCHEMA = "cuda_bench_driver.refusal.v1"
COMMAND_ADMISSION_SCHEMA = "cuda_bench_driver.command_admission.v1"
COMMAND_COMPLETION_SCHEMA = "cuda_bench_driver.command_completion.v1"
WINDOW_AUTHORIZATION_SCHEMA = "cuda_bench_driver.window_authorization.v1"
CONTINUATION_SCHEMA = "cuda_bench_driver.continuation.v1"
CONSUMPTION_RECEIPT_SCHEMA = "cuda_bench_driver.consumption_receipt.v1"
TURN_MANIFEST_SCHEMA = "cuda_bench_driver.turn_manifest.v1"
TURN_ARTIFACT_SCHEMA = "cuda_bench_driver.turn_artifact.v1"
CONTAINMENT_SNAPSHOT_SCHEMA = "cuda_bench_driver.containment_snapshot.v2"
RUNTIME_IDENTITY_SCHEMA = "cuda_bench_driver.runtime_identity.v1"
ASSEMBLE_RECEIPT_SCHEMA = "cuda_bench_assemble.receipt.v1"
REHEARSAL_PACKET_SCHEMA = "cuda_bench_rehearsal.packet.v1"

REFUSAL_VOCABULARY: frozenset[str] = frozenset(
    {
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
_JOURNAL_SEQUENCE = itertools.count()
_AUTHORIZATION_RECEIPT_SEQUENCE = itertools.count()
_BINARY_STDERR_THREAD_SEQUENCE = itertools.count()
_NAME_SEED = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}")

_BINARY_STDERR_FINISH_BYTE = b"F"
_BINARY_STDERR_POST_FINISH_CAP = 65_536
_BINARY_STDERR_POST_FINISH_TIMEOUT_S = 1.0
_BINARY_STDERR_JOIN_TIMEOUT_S = 2.0


class BenchRefusal(Exception):
    """A typed refusal from the driver's closed vocabulary."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in REFUSAL_VOCABULARY:
            raise ValueError("closed_refusal")
        self.code = code
        super().__init__(code)


class _StorageIndependentCleanupIncomplete(BenchRefusal):
    """Trusted terminal cleanup when durable failure storage is unavailable."""

    def __init__(self) -> None:
        super().__init__("cleanup_incomplete")


class _CleanupIncompleteLatch(Protocol):
    def __call__(self, *, storage_unavailable: bool = False) -> None: ...


@dataclass(frozen=True, slots=True)
class _BootstrapCleanupResult:
    outcome: Literal["clean", "cleanup_incomplete"]
    observed_returncode: int | None
    exited_before_cleanup_signal: bool

    def __post_init__(self) -> None:
        if (
            self.outcome not in {"clean", "cleanup_incomplete"}
            or (
                self.observed_returncode is not None
                and type(self.observed_returncode) is not int
            )
            or type(self.exited_before_cleanup_signal) is not bool
            or (
                self.observed_returncode is None
                and self.exited_before_cleanup_signal
            )
        ):
            raise ValueError("bootstrap_cleanup_result_invalid")


def _filesystem_hazard() -> None:
    raise BenchRefusal("filesystem_hazard")


def _relative_parts(relative: str) -> tuple[str, ...]:
    if type(relative) is not str or not relative or os.path.isabs(relative):
        _filesystem_hazard()
    parts = tuple(relative.split(os.sep))
    if any(part in {"", ".", ".."} or "\0" in part for part in parts):
        _filesystem_hazard()
    return parts


def _check_directory_fd(fd: int) -> os.stat_result:
    try:
        info = os.fstat(fd)
    except OSError:
        _filesystem_hazard()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        _filesystem_hazard()
    return info


def _check_file_fd(
    fd: int,
    *,
    byte_cap: int = TURN_ARTIFACT_BYTE_CAP,
    expected_nlink: int = 1,
    expected_size: int | None = None,
) -> os.stat_result:
    try:
        info = os.fstat(fd)
    except OSError:
        _filesystem_hazard()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_nlink != expected_nlink
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_size > byte_cap
        or (expected_size is not None and info.st_size != expected_size)
    ):
        _filesystem_hazard()
    return info


def _open_root_fd(root: Path) -> int:
    try:
        root = Path(root)
        if not root.is_absolute():
            _filesystem_hazard()
        fd = os.open(os.fspath(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except (OSError, TypeError, ValueError):
        _filesystem_hazard()
    try:
        _check_directory_fd(fd)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _open_existing_directory(parent_fd: int, name: str) -> int:
    try:
        child_fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except OSError:
        _filesystem_hazard()
    try:
        _check_directory_fd(child_fd)
    except BaseException:
        os.close(child_fd)
        raise
    return child_fd


def _open_parent_fd(
    relative: str, *, root: Path, create: bool
) -> tuple[int, tuple[str, ...], tuple[tuple[int, int], ...]]:
    parts = _relative_parts(relative)
    directory_fd = _open_root_fd(root)
    root_info = _check_directory_fd(directory_fd)
    chain = [(root_info.st_dev, root_info.st_ino)]
    try:
        for part in parts[:-1]:
            try:
                next_fd = _open_existing_directory(directory_fd, part)
            except BenchRefusal:
                if not create:
                    raise
                try:
                    os.mkdir(part, mode=0o700, dir_fd=directory_fd)
                except FileExistsError:
                    pass
                except OSError:
                    _filesystem_hazard()
                next_fd = _open_existing_directory(directory_fd, part)
            next_info = _check_directory_fd(next_fd)
            chain.append((next_info.st_dev, next_info.st_ino))
            os.close(directory_fd)
            directory_fd = next_fd
        return directory_fd, parts, tuple(chain)
    except BaseException:
        os.close(directory_fd)
        raise


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write")
        view = view[written:]


def _open_anonymous_file(parent_fd: int, *, append: bool) -> int:
    flags = os.O_WRONLY | os.O_TMPFILE | os.O_NOFOLLOW
    if append:
        flags |= os.O_APPEND
    fd: int | None = None
    try:
        fd = os.open(".", flags, 0o600, dir_fd=parent_fd)
        os.set_inheritable(fd, False)
        os.fchmod(fd, 0o600)
        _check_file_fd(fd, expected_nlink=0, expected_size=0)
        return fd
    except BaseException as exc:
        if fd is not None:
            os.close(fd)
        if isinstance(exc, OSError):
            _filesystem_hazard()
        raise


def _publish_anonymous_file(
    fd: int,
    parent_fd: int,
    name: str,
    *,
    expected_size: int,
) -> os.stat_result:
    _check_file_fd(fd, expected_nlink=0, expected_size=expected_size)
    _check_directory_fd(parent_fd)
    try:
        os.link(
            f"/proc/self/fd/{fd}",
            name,
            dst_dir_fd=parent_fd,
            follow_symlinks=True,
        )
    except OSError:
        _filesystem_hazard()
    _check_directory_fd(parent_fd)
    _check_file_fd(fd, expected_nlink=1, expected_size=expected_size)
    try:
        os.fsync(parent_fd)
    except OSError:
        _filesystem_hazard()
    _check_directory_fd(parent_fd)
    return _check_file_fd(fd, expected_nlink=1, expected_size=expected_size)


def _stable_file_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _verify_path_binding(
    relative: str,
    *,
    root: Path,
    expected_chain: tuple[tuple[int, int], ...],
    expected_file: os.stat_result,
) -> None:
    """Bind a locator to its private inode chain at verification time.

    A returned Path is a locator, not a retained capability: a later same-UID
    namespace mutation can invalidate it, so every later read must re-enter
    through ``open_bench_file`` and perform this verification again.
    """

    parent_fd, parts, current_chain = _open_parent_fd(relative, root=root, create=False)
    fd: int | None = None
    try:
        if current_chain != expected_chain:
            _filesystem_hazard()
        try:
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError:
            _filesystem_hazard()
        current_file = _check_file_fd(fd, expected_size=expected_file.st_size)
        if _stable_file_identity(current_file) != _stable_file_identity(expected_file):
            _filesystem_hazard()
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent_fd)


def open_bench_file(relative: str, *, root: Path = BENCH_ROOT) -> bytes:
    """Read one owner-private file through a trusted-anchor descriptor walk."""

    parent_fd, parts, directory_chain = _open_parent_fd(relative, root=root, create=False)
    try:
        try:
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        except OSError:
            _filesystem_hazard()
    finally:
        os.close(parent_fd)
    try:
        initial = _check_file_fd(fd)
        chunks: list[bytes] = []
        remaining = TURN_ARTIFACT_BYTE_CAP + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > TURN_ARTIFACT_BYTE_CAP:
            _filesystem_hazard()
        final = _check_file_fd(fd)
        if len(payload) != initial.st_size or _stable_file_identity(
            initial
        ) != _stable_file_identity(final):
            _filesystem_hazard()
        _verify_path_binding(
            relative,
            root=root,
            expected_chain=directory_chain,
            expected_file=final,
        )
        return payload
    except OSError:
        _filesystem_hazard()
    finally:
        os.close(fd)


def write_private_file(
    relative: str,
    data: bytes,
    *,
    root: Path = BENCH_ROOT,
    on_link: Callable[[Path], None] | None = None,
) -> Path:
    """Exclusively create and fsync one owner-private file below root."""

    if type(data) is not bytes or len(data) > TURN_ARTIFACT_BYTE_CAP:
        _filesystem_hazard()
    parent_fd, parts, directory_chain = _open_parent_fd(relative, root=root, create=True)
    final_path = Path(root).joinpath(*parts)
    fd: int | None = None
    try:
        fd = _open_anonymous_file(parent_fd, append=False)
        _write_all(fd, data)
        os.fsync(fd)
        _check_file_fd(fd, expected_nlink=0, expected_size=len(data))
        published = _publish_anonymous_file(
            fd,
            parent_fd,
            parts[-1],
            expected_size=len(data),
        )
        _verify_path_binding(
            relative,
            root=root,
            expected_chain=directory_chain,
            expected_file=published,
        )
        if on_link is not None:
            on_link(final_path)
    except BaseException as exc:
        if isinstance(exc, OSError):
            _filesystem_hazard()
        raise
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent_fd)
    return final_path


def _create_consumption_marker(nonce: str, *, root: Path) -> Path:
    """Publish the nonce's anchored atomic-link linearization point."""

    relative = f"markers/{nonce}"
    parent_fd, parts, directory_chain = _open_parent_fd(relative, root=root, create=True)
    fd: int | None = None
    try:
        fd = _open_anonymous_file(parent_fd, append=False)
        os.fsync(fd)
        _check_file_fd(fd, expected_nlink=0, expected_size=0)
        _check_directory_fd(parent_fd)
        try:
            os.link(
                f"/proc/self/fd/{fd}",
                parts[-1],
                dst_dir_fd=parent_fd,
                follow_symlinks=True,
            )
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                _filesystem_hazard()
            os.close(fd)
            fd = None
            try:
                fd = os.open(
                    parts[-1],
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=parent_fd,
                )
            except OSError:
                _filesystem_hazard()
            os.set_inheritable(fd, False)
            existing = _check_file_fd(fd, expected_size=0)
            _check_directory_fd(parent_fd)
            _verify_path_binding(
                relative,
                root=root,
                expected_chain=directory_chain,
                expected_file=existing,
            )
            raise BenchRefusal("authorization_consumed") from None
        _check_directory_fd(parent_fd)
        os.fsync(parent_fd)
        _check_directory_fd(parent_fd)
        published = _check_file_fd(fd, expected_size=0)
        _verify_path_binding(
            relative,
            root=root,
            expected_chain=directory_chain,
            expected_file=published,
        )
    except BaseException as exc:
        if isinstance(exc, OSError):
            _filesystem_hazard()
        raise
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent_fd)
    return Path(root).joinpath(*parts)


class PhaseJournal:
    """One content-light append-only journal backed by one retained fd."""

    def __init__(
        self,
        phase: str,
        *,
        journal_dir: str,
        timestamp: str,
        root: Path = BENCH_ROOT,
    ) -> None:
        if (
            type(phase) is not str
            or _NAME_SEED.fullmatch(phase) is None
            or type(timestamp) is not str
            or _NAME_SEED.fullmatch(timestamp) is None
        ):
            _filesystem_hazard()
        directory_parts = _relative_parts(journal_dir)
        sequence = next(_JOURNAL_SEQUENCE)
        filename = f"{phase}-{timestamp}-{os.getpid()}-{sequence}-journal.jsonl"
        relative = os.path.join(*directory_parts, filename)
        parent_fd, parts, directory_chain = _open_parent_fd(relative, root=root, create=True)
        self.path = Path(root).joinpath(*parts)
        self._fd: int | None = None
        try:
            self._fd = _open_anonymous_file(parent_fd, append=True)
            os.fsync(self._fd)
            _check_file_fd(self._fd, expected_nlink=0, expected_size=0)
            published = _publish_anonymous_file(self._fd, parent_fd, parts[-1], expected_size=0)
            _verify_path_binding(
                relative,
                root=root,
                expected_chain=directory_chain,
                expected_file=published,
            )
        except BaseException as exc:
            if self._fd is not None:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None
            if isinstance(exc, Exception):
                raise BenchRefusal("journal_failure") from None
            raise
        finally:
            os.close(parent_fd)

    def append(self, *, ts: str, transition: str, detail: Mapping[str, object]) -> None:
        try:
            if (
                type(ts) is not str
                or not 1 <= len(ts) <= 128
                or type(transition) is not str
                or not 1 <= len(transition) <= 128
                or not isinstance(detail, Mapping)
            ):
                raise ValueError("invalid journal shape")
            projected_detail = dict(detail)
            if any(type(key) is not str or not 1 <= len(key) <= 128 for key in projected_detail):
                raise ValueError("invalid journal detail key")
            document = {
                "ts": ts,
                "transition": transition,
                "detail": projected_detail,
            }
            line = (
                json.dumps(
                    document,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
        except Exception:
            raise BenchRefusal("journal_failure") from None
        marker_document = {
            "ts": ts,
            "transition": transition,
            "detail": {
                key: (
                    "<typed-refusal>"
                    if type(value) is str and value in REFUSAL_VOCABULARY
                    else value
                )
                for key, value in projected_detail.items()
            },
        }
        rendered = json.dumps(
            marker_document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).lower()
        if any(marker in rendered for marker in _CONTENT_MARKERS):
            raise ValueError("content_light_violation")
        if self._fd is None:
            raise BenchRefusal("journal_failure")
        try:
            before = _check_file_fd(self._fd)
        except BenchRefusal:
            self._poison()
            raise
        checkpoint = before.st_size
        if checkpoint + len(line) > TURN_ARTIFACT_BYTE_CAP:
            raise BenchRefusal("journal_failure")
        our_bytes = 0
        try:
            view = memoryview(line)
            while view:
                written = os.write(self._fd, view)
                if written <= 0 or written > len(view):
                    raise OSError("short write")
                our_bytes += written
                view = view[written:]
            expected_size = checkpoint + len(line)
            _check_file_fd(self._fd, expected_size=expected_size)
            os.fsync(self._fd)
            _check_file_fd(self._fd, expected_size=expected_size)
        except BaseException as exc:
            if not self._rollback(checkpoint, our_bytes):
                self._poison()
            if isinstance(exc, BenchRefusal):
                raise
            if isinstance(exc, Exception):
                raise BenchRefusal("journal_failure") from None
            raise

    def _rollback(self, checkpoint: int, our_bytes: int) -> bool:
        if self._fd is None:
            return False
        try:
            current = _check_file_fd(self._fd)
            if current.st_size != checkpoint + our_bytes:
                return False
            os.ftruncate(self._fd, checkpoint)
            os.fsync(self._fd)
            _check_file_fd(self._fd, expected_size=checkpoint)
            return True
        except BaseException:
            return False

    def _poison(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            os.close(fd)
        except OSError:
            pass

    def close(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            os.close(fd)
        except OSError:
            raise BenchRefusal("journal_failure") from None

    def __enter__(self) -> PhaseJournal:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


SYSTEMCTL_WHITELIST = frozenset({"show", "is-active"})
_SYSTEMCTL = "systemctl"
KERNEL_SIGNATURES = (
    "reusemappingdbMap",
    "pMapCb",
    "mmuWalkMap",
    "NV_ERR_NO_MEMORY",
    "Xid",
)
KERNEL_COUNTER_KEYS = (*KERNEL_SIGNATURES, "unmatched_nvrm")


def systemctl_command(subcommand: str, unit: str) -> list[str]:
    """Build the sole read-only systemd command shape available to the driver."""

    if subcommand not in SYSTEMCTL_WHITELIST:
        raise ValueError("mutating_systemctl_forbidden")
    if type(unit) is not str or not unit:
        raise ValueError("unit_invalid")
    return [_SYSTEMCTL, "--user", subcommand, unit]


@dataclass(frozen=True, slots=True)
class ProviderWitness:
    synthetic: bool
    real_calls: int
    loopback_kernel_calls: int = 0

    def __post_init__(self) -> None:
        if (
            type(self.synthetic) is not bool
            or type(self.real_calls) is not int
            or self.real_calls < 0
            or type(self.loopback_kernel_calls) is not int
            or self.loopback_kernel_calls < 0
            or (self.synthetic and self.real_calls != 0)
        ):
            raise ValueError("provider_witness_invalid")

    def assert_no_real_calls(self) -> None:
        if not self.synthetic or self.real_calls != 0:
            raise AssertionError("synthetic_provider_contacted_real_surface")

    def canonical_bytes(self) -> bytes:
        return _canonical_json(
            {
                "synthetic": self.synthetic,
                "real_calls": self.real_calls,
                "loopback_kernel_calls": self.loopback_kernel_calls,
            }
        )

    @property
    def binding_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_canonical_bytes(
        cls,
        payload: bytes,
        *,
        expected_binding_sha256: str | None = None,
    ) -> "ProviderWitness":
        try:
            if type(payload) is not bytes or not payload or len(payload) > 256:
                raise ValueError
            document = json.loads(
                payload,
                object_pairs_hook=_json_object_without_duplicates,
                parse_constant=_reject_json_constant,
            )
            if type(document) is not dict or set(document) != {
                "synthetic",
                "real_calls",
                "loopback_kernel_calls",
            }:
                raise ValueError
            witness = cls(
                synthetic=document["synthetic"],
                real_calls=document["real_calls"],
                loopback_kernel_calls=document["loopback_kernel_calls"],
            )
            if witness.canonical_bytes() != payload:
                raise ValueError
        except (KeyError, TypeError, UnicodeError, ValueError):
            raise ValueError("provider_witness_serialization_invalid") from None
        if expected_binding_sha256 is not None:
            if (
                type(expected_binding_sha256) is not str
                or _SHA256_RE.fullmatch(expected_binding_sha256) is None
                or witness.binding_sha256 != expected_binding_sha256
            ):
                raise ValueError("provider_witness_binding_mismatch")
        return witness


class _WitnessedProvider:
    def _init_provider_witness(self, *, synthetic: bool) -> None:
        if type(synthetic) is not bool:
            raise ValueError("provider_witness_invalid")
        self._witness_synthetic = synthetic
        self._witness_real_calls = 0
        self._witness_loopback_kernel_calls = 0

    @property
    def witness(self) -> ProviderWitness:
        return ProviderWitness(
            synthetic=self._witness_synthetic,
            real_calls=self._witness_real_calls,
            loopback_kernel_calls=self._witness_loopback_kernel_calls,
        )

    def _record_real_call(self) -> None:
        self._witness_real_calls += 1

    def _record_loopback_kernel_call(self) -> None:
        self._witness_loopback_kernel_calls += 1


class ServiceStateProvider(Protocol):
    tier: str

    def is_active(self, unit: str) -> str: ...


class PortProbe(Protocol):
    tier: str

    def is_free(
        self,
        port: int,
        *,
        lease: "RehearsalPortLease | None" = None,
    ) -> bool: ...


class GpuProvider(Protocol):
    tier: str

    def enumerate_uuids(self) -> list[str]: ...

    def inventory(self, uuid: str) -> list[tuple[int, str]]: ...

    def memory(self, uuid: str) -> tuple[float, int]: ...


class KernelLogProvider(Protocol):
    tier: str

    def cursor(self) -> str: ...

    def count_signatures(
        self, start_cursor: str, end_cursor: str
    ) -> dict[str, int]: ...


class BackendMapProvider(Protocol):
    tier: str

    def read_maps(self, pid: int) -> str: ...


class Clock(Protocol):
    tier: str

    def now_utc(self) -> str: ...

    def monotonic(self) -> float: ...


class ContainmentProvider(Protocol):
    tier: str
    clock: Clock
    port_probe: PortProbe

    def capture(self, phase: str, boundary: str) -> cm.ContainmentSnapshot: ...


class ServerLauncher(Protocol):
    tier: str

    def spawn(self, argv: list[str], env: dict[str, str]) -> "OwnedChild": ...  # noqa: F821


_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_STUB_ANNOUNCEMENT_RE = re.compile(rb"STUB_LISTENING port=([1-9][0-9]*)\n")
_STUB_ANNOUNCEMENT_CAP = 128
_REHEARSAL_STUB_PATH = Path(__file__).with_name("cuda_bench_stub.py")
_GUARD_GO_BYTE = b"G"
_GUARD_CODE = """\
import os
import signal
import sys

gate_fd = int(sys.argv[1])
exec_fd = int(sys.argv[2])
pin_fd = int(sys.argv[3])
pin_kind = sys.argv[4]
release_directory_fd = int(sys.argv[5])
old_mask = {int(value) for value in sys.argv[6].split(",") if value}
token = os.read(gate_fd, 1)
os.close(gate_fd)
if token != b"G":
    os.close(exec_fd)
    os.close(pin_fd)
    if release_directory_fd >= 0:
        os.close(release_directory_fd)
    raise SystemExit(0)
target_argv = sys.argv[7:]
signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
os.set_inheritable(exec_fd, False)
try:
    if pin_kind == "binary":
        os.set_inheritable(pin_fd, False)
        if release_directory_fd >= 0:
            os.set_inheritable(release_directory_fd, False)
            os.fchdir(release_directory_fd)
        os.execve(pin_fd, target_argv, os.environ)
    elif pin_kind == "python_file":
        if release_directory_fd != -1:
            raise OSError("unexpected release directory")
        os.set_inheritable(pin_fd, True)
        target_argv[3] = f"/proc/self/fd/{pin_fd}"
        os.execve(target_argv[0], target_argv, os.environ)
    else:
        raise OSError("unknown pin kind")
except BaseException:
    try:
        os.write(exec_fd, b"E")
    finally:
        os.close(exec_fd)
    raise SystemExit(127)
"""


@dataclass(frozen=True, slots=True)
class _BinaryStderrSnapshot:
    retained: bytes = field(repr=False, compare=False)
    retained_sha256: str
    retained_byte_count: int
    truncated: bool
    post_finish_byte_count: int = field(repr=False, compare=False)


class _BinaryStderrCapture:
    """Sole-owner drainer for one binary launch's private stderr pipe."""

    def __init__(
        self,
        stderr_read: int,
        control_read: int,
        control_write: int,
    ) -> None:
        self._stderr_read = stderr_read
        self._control_read = control_read
        self._control_write: int | None = control_write
        self._lock = threading.Lock()
        self._finished = threading.Event()
        self._retained = bytearray()
        self._truncated = False
        self._post_finish_byte_count = 0
        self._snapshot: _BinaryStderrSnapshot | None = None
        self._failed = False
        self._stderr_eof = False
        self._finish_requested_at: float | None = None
        self._consumed = False
        self._thread = threading.Thread(
            target=self._drain,
            name=(
                "cuda-binary-stderr-"
                f"{next(_BINARY_STDERR_THREAD_SEQUENCE)}"
            ),
        )

    def __repr__(self) -> str:
        return "_BinaryStderrCapture()"

    @property
    def thread_alive(self) -> bool:
        return self._thread.is_alive()

    @property
    def truncated(self) -> bool:
        with self._lock:
            return self._truncated

    @property
    def consumed(self) -> bool:
        with self._lock:
            return self._consumed

    def _start(self) -> None:
        self._thread.start()

    def _close_before_start(self) -> None:
        for fd in (self._stderr_read, self._control_read, self._control_write):
            _close_fd(fd)
        self._control_write = None

    def _retain(self, payload: bytes) -> None:
        with self._lock:
            available = BINARY_STDERR_DIAGNOSTIC_CAP - len(self._retained)
            if available > 0:
                self._retained.extend(payload[:available])
            if len(payload) > available:
                self._truncated = True

    def _drain_ready_stderr(
        self,
        *,
        finish_deadline: float | None,
        post_finish_remaining: int,
    ) -> tuple[bool, int, bool]:
        cycle_remaining = BINARY_STDERR_DIAGNOSTIC_CAP
        while cycle_remaining > 0:
            with self._lock:
                finish_requested_at = self._finish_requested_at
            active_deadline = finish_deadline
            if finish_requested_at is not None:
                requested_deadline = (
                    finish_requested_at + _BINARY_STDERR_POST_FINISH_TIMEOUT_S
                )
                active_deadline = (
                    requested_deadline
                    if active_deadline is None
                    else min(active_deadline, requested_deadline)
                )
            read_cap = cycle_remaining
            if active_deadline is not None:
                read_cap = min(read_cap, post_finish_remaining)
                if read_cap <= 0 or time.monotonic() >= active_deadline:
                    return False, post_finish_remaining, True
            try:
                payload = os.read(self._stderr_read, read_cap)
            except BlockingIOError:
                return False, post_finish_remaining, False
            if not payload:
                return True, post_finish_remaining, False
            with self._lock:
                finish_requested_at = self._finish_requested_at
            if finish_requested_at is not None:
                requested_deadline = (
                    finish_requested_at + _BINARY_STDERR_POST_FINISH_TIMEOUT_S
                )
                active_deadline = (
                    requested_deadline
                    if active_deadline is None
                    else min(active_deadline, requested_deadline)
                )
            self._retain(payload)
            cycle_remaining -= len(payload)
            if active_deadline is not None:
                post_finish_remaining -= len(payload)
                with self._lock:
                    self._post_finish_byte_count += len(payload)
                if (
                    post_finish_remaining <= 0
                    or time.monotonic() >= active_deadline
                ):
                    return False, post_finish_remaining, True
        return False, post_finish_remaining, False

    def _drain(self) -> None:
        finish_deadline: float | None = None
        post_finish_remaining = _BINARY_STDERR_POST_FINISH_CAP
        stderr_eof = False
        try:
            poller = select.poll()
            poller.register(
                self._stderr_read,
                select.POLLIN | select.POLLHUP | select.POLLERR | select.POLLNVAL,
            )
            poller.register(
                self._control_read,
                select.POLLIN | select.POLLHUP | select.POLLERR | select.POLLNVAL,
            )
            while True:
                with self._lock:
                    finish_requested_at = self._finish_requested_at
                if finish_requested_at is not None:
                    requested_deadline = (
                        finish_requested_at + _BINARY_STDERR_POST_FINISH_TIMEOUT_S
                    )
                    finish_deadline = (
                        requested_deadline
                        if finish_deadline is None
                        else min(finish_deadline, requested_deadline)
                    )
                if finish_deadline is None:
                    timeout_ms = 100
                else:
                    remaining_s = finish_deadline - time.monotonic()
                    if remaining_s <= 0:
                        break
                    timeout_ms = max(1, min(100, int(remaining_s * 1000)))
                events = dict(poller.poll(timeout_ms))
                control_mask = events.get(self._control_read, 0)
                if control_mask:
                    marker = os.read(self._control_read, 1)
                    if marker not in {b"", _BINARY_STDERR_FINISH_BYTE}:
                        raise OSError("invalid diagnostic finish marker")
                    marker_deadline = (
                        time.monotonic() + _BINARY_STDERR_POST_FINISH_TIMEOUT_S
                    )
                    finish_deadline = (
                        marker_deadline
                        if finish_deadline is None
                        else min(finish_deadline, marker_deadline)
                    )
                stderr_mask = events.get(self._stderr_read, 0)
                if stderr_mask:
                    eof, post_finish_remaining, stop = self._drain_ready_stderr(
                        finish_deadline=finish_deadline,
                        post_finish_remaining=post_finish_remaining,
                    )
                    if eof:
                        stderr_eof = True
                        break
                    if stop:
                        break
                if finish_deadline is not None and post_finish_remaining <= 0:
                    break
        except BaseException:
            with self._lock:
                self._failed = True
        finally:
            _close_fd(self._stderr_read)
            _close_fd(self._control_read)
            with self._lock:
                retained = bytes(self._retained)
                self._stderr_eof = stderr_eof
                self._snapshot = _BinaryStderrSnapshot(
                    retained=retained,
                    retained_sha256=hashlib.sha256(retained).hexdigest(),
                    retained_byte_count=len(retained),
                    truncated=self._truncated,
                    post_finish_byte_count=self._post_finish_byte_count,
                )
            self._finished.set()

    def finish(self) -> _BinaryStderrSnapshot:
        with self._lock:
            if self._consumed:
                raise BenchRefusal("cleanup_incomplete")
            self._consumed = True
            control_write = self._control_write
            self._control_write = None
            self._finish_requested_at = time.monotonic()
        write_failed = False
        try:
            if control_write is None:
                write_failed = True
            elif os.write(control_write, _BINARY_STDERR_FINISH_BYTE) != 1:
                write_failed = True
        except OSError:
            write_failed = True
        finally:
            _close_fd(control_write)
        self._thread.join(timeout=_BINARY_STDERR_JOIN_TIMEOUT_S)
        with self._lock:
            snapshot = self._snapshot
            failed = self._failed
            stderr_eof = self._stderr_eof
        if (
            self._thread.is_alive()
            or snapshot is None
            or failed
            or (write_failed and not stderr_eof)
        ):
            raise BenchRefusal("cleanup_incomplete")
        return snapshot

    def retire_after_interruption(self) -> None:
        """Complete or await the already-bounded retirement after interruption."""

        if not self.consumed:
            self.finish()
            return
        self._thread.join(timeout=_BINARY_STDERR_JOIN_TIMEOUT_S)
        if self._thread.is_alive():
            raise BenchRefusal("cleanup_incomplete")


class _BinarySpawnFailure(BenchRefusal):
    """Content-light refusal carrying one still-live binary capture."""

    def __init__(
        self,
        code: str,
        *,
        bootstrap_cleanup: _BootstrapCleanupResult,
        stderr_capture: _BinaryStderrCapture,
    ) -> None:
        if (
            type(bootstrap_cleanup) is not _BootstrapCleanupResult
            or type(stderr_capture) is not _BinaryStderrCapture
            or stderr_capture.consumed
        ):
            raise ValueError("binary_spawn_failure_invalid")
        self._bootstrap_cleanup = bootstrap_cleanup
        self._stderr_capture = stderr_capture
        super().__init__(code)

    def __repr__(self) -> str:
        return f"_BinarySpawnFailure({self.code!r})"


def _start_binary_stderr_capture() -> tuple[_BinaryStderrCapture, int]:
    stderr_read: int | None = None
    stderr_write: int | None = None
    control_read: int | None = None
    control_write: int | None = None
    capture: _BinaryStderrCapture | None = None
    try:
        stderr_read, stderr_write = os.pipe2(os.O_CLOEXEC)
        os.set_blocking(stderr_read, False)
        control_read, control_write = os.pipe2(os.O_CLOEXEC)
        capture = _BinaryStderrCapture(
            stderr_read,
            control_read,
            control_write,
        )
        capture._start()
        return capture, stderr_write
    except BaseException:
        if capture is not None:
            capture._close_before_start()
        else:
            for fd in (stderr_read, control_read, control_write):
                _close_fd(fd)
        _close_fd(stderr_write)
        raise


def _finish_binary_stderr_capture(
    capture: _BinaryStderrCapture | None,
) -> _BinaryStderrSnapshot | None:
    if capture is None:
        return None
    if type(capture) is not _BinaryStderrCapture:
        raise BenchRefusal("cleanup_incomplete")
    return capture.finish()


def _retire_binary_stderr_capture(
    capture: _BinaryStderrCapture | None,
    *,
    on_cleanup_incomplete: _CleanupIncompleteLatch | None = None,
) -> _BinaryStderrSnapshot | None:
    """Consume one capture, making bounded retirement failure authoritative."""

    try:
        return _finish_binary_stderr_capture(capture)
    except BaseException:
        if on_cleanup_incomplete is not None:
            on_cleanup_incomplete()
        if type(capture) is _BinaryStderrCapture:
            try:
                capture.retire_after_interruption()
            except BaseException:
                pass
        raise BenchRefusal("cleanup_incomplete") from None


def _binary_stderr_metadata(
    snapshot: _BinaryStderrSnapshot,
    *,
    returncode: int | None,
    exited_before_finalize: bool,
) -> dict[str, object]:
    if (
        type(snapshot) is not _BinaryStderrSnapshot
        or type(snapshot.retained) is not bytes
        or type(snapshot.retained_sha256) is not str
        or _SHA256_RE.fullmatch(snapshot.retained_sha256) is None
        or snapshot.retained_sha256
        != hashlib.sha256(snapshot.retained).hexdigest()
        or type(snapshot.retained_byte_count) is not int
        or snapshot.retained_byte_count != len(snapshot.retained)
        or not 0 <= snapshot.retained_byte_count <= BINARY_STDERR_DIAGNOSTIC_CAP
        or type(snapshot.truncated) is not bool
        or type(exited_before_finalize) is not bool
        or (returncode is not None and type(returncode) is not int)
    ):
        raise BenchRefusal("cleanup_incomplete")
    detail: dict[str, object] = {
        "retained_sha256": snapshot.retained_sha256,
        "retained_byte_count": snapshot.retained_byte_count,
        "truncated": snapshot.truncated,
        "exited_before_finalize": exited_before_finalize,
    }
    if returncode is not None:
        if returncode < 0:
            detail["terminating_signal"] = -returncode
        else:
            detail["exit_code"] = returncode
    return detail


def _dispose_binary_stderr_diagnostic(
    capture: _BinaryStderrCapture | None,
    *,
    journal: PhaseJournal,
    clock: Clock,
    cycle: int,
    attempt_root: Path,
    returncode: int | None,
    exited_before_finalize: bool,
    on_cleanup_incomplete: _CleanupIncompleteLatch | None = None,
) -> None:
    """Retire, privately publish, then journal one content-light snapshot."""

    if capture is None:
        return
    if type(cycle) is not int or cycle <= 0 or not isinstance(attempt_root, Path):
        raise BenchRefusal("cleanup_incomplete")
    snapshot = _retire_binary_stderr_capture(
        capture,
        on_cleanup_incomplete=on_cleanup_incomplete,
    )
    if snapshot is None:
        raise BenchRefusal("cleanup_incomplete")
    detail = _binary_stderr_metadata(
        snapshot,
        returncode=returncode,
        exited_before_finalize=exited_before_finalize,
    )
    write_private_file(
        f"diagnostics/cycle-{cycle}-stderr.bin",
        snapshot.retained,
        root=attempt_root,
    )
    _append_phase_transition(
        journal,
        clock,
        f"cycle_{cycle}_stderr_diagnostic",
        detail=detail,
    )


def _raise_binary_spawn_failure(
    exc: BaseException,
    *,
    bootstrap_cleanup: _BootstrapCleanupResult,
    stderr_capture: _BinaryStderrCapture,
) -> NoReturn:
    if type(bootstrap_cleanup) is not _BootstrapCleanupResult:
        raise ValueError("bootstrap_cleanup_result_invalid")
    cleanup_complete = bootstrap_cleanup.outcome == "clean"
    code = (
        exc.code
        if cleanup_complete and isinstance(exc, BenchRefusal)
        else "spawn_failure"
        if cleanup_complete
        else "cleanup_incomplete"
    )
    raise _BinarySpawnFailure(
        code,
        bootstrap_cleanup=bootstrap_cleanup,
        stderr_capture=stderr_capture,
    ) from None


@dataclass(frozen=True)
class SpawnPin:
    kind: Literal["binary", "python_file"]
    pinned_path: Path
    pinned_sha256: str
    required_argv_prefix: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            self.kind not in {"binary", "python_file"}
            or not isinstance(self.pinned_path, Path)
            or not self.pinned_path.is_absolute()
            or type(self.pinned_sha256) is not str
            or _SHA256_RE.fullmatch(self.pinned_sha256) is None
            or type(self.required_argv_prefix) is not tuple
            or not self.required_argv_prefix
            or any(type(part) is not str or not part for part in self.required_argv_prefix)
        ):
            raise ValueError("spawn_pin_invalid")
        if self.kind == "binary":
            if self.required_argv_prefix[0] != str(self.pinned_path):
                raise ValueError("spawn_pin_invalid")
        elif self.required_argv_prefix != (
            sys.executable,
            "-B",
            "-I",
            str(self.pinned_path),
        ):
            raise ValueError("spawn_pin_invalid")


@dataclass(frozen=True, slots=True)
class ReleaseDirectoryProof:
    manifest_sha256: str
    directory_dev: int
    directory_ino: int
    snapshot_sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.manifest_sha256) is not str
            or _SHA256_RE.fullmatch(self.manifest_sha256) is None
            or type(self.directory_dev) is not int
            or self.directory_dev < 0
            or type(self.directory_ino) is not int
            or self.directory_ino <= 0
            or type(self.snapshot_sha256) is not str
            or _SHA256_RE.fullmatch(self.snapshot_sha256) is None
        ):
            raise ValueError("release_directory_proof_invalid")


_RELEASE_DIRECTORY_HANDLE_GUARD = object()


@dataclass(frozen=True, init=False, slots=True)
class _LauncherReleaseDirectory:
    """One launcher-owned directory capability bound to one exact pin/proof."""

    fd: int
    pin: SpawnPin
    proof: ReleaseDirectoryProof

    def __init__(
        self,
        fd: int,
        pin: SpawnPin,
        proof: ReleaseDirectoryProof,
        *,
        _guard: object | None = None,
    ) -> None:
        if (
            _guard is not _RELEASE_DIRECTORY_HANDLE_GUARD
            or type(fd) is not int
            or fd < 0
            or type(pin) is not SpawnPin
            or pin.kind != "binary"
            or type(proof) is not ReleaseDirectoryProof
        ):
            raise TypeError("launcher_owned_release_directory_required")
        object.__setattr__(self, "fd", fd)
        object.__setattr__(self, "pin", pin)
        object.__setattr__(self, "proof", proof)


def _release_snapshot_sha256(directory_fd: int) -> str:
    """Hash every top-level file or literal link through one held directory."""

    try:
        directory_before = os.fstat(directory_fd)
        if not stat.S_ISDIR(directory_before.st_mode):
            raise BenchRefusal("spawn_failure")
        names = sorted(os.listdir(directory_fd), key=os.fsencode)
        digest = hashlib.sha256()
        final_records: list[tuple[str, tuple[int, ...], str | None]] = []
        stable = lambda value: (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )
        for name in names:
            name_bytes = os.fsencode(name)
            named_before = os.stat(
                name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if stat.S_ISREG(named_before.st_mode):
                fd = os.open(
                    name,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                try:
                    held_before = os.fstat(fd)
                    if (
                        not stat.S_ISREG(held_before.st_mode)
                        or (held_before.st_dev, held_before.st_ino)
                        != (named_before.st_dev, named_before.st_ino)
                    ):
                        raise BenchRefusal("spawn_failure")
                    digest.update(b"F")
                    digest.update(len(name_bytes).to_bytes(8, "big"))
                    digest.update(name_bytes)
                    digest.update(held_before.st_size.to_bytes(16, "big"))
                    observed = 0
                    while True:
                        chunk = os.read(fd, 1024 * 1024)
                        if not chunk:
                            break
                        observed += len(chunk)
                        digest.update(chunk)
                    held_after = os.fstat(fd)
                    named_after = os.stat(
                        name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                    if (
                        observed != held_before.st_size
                        or stable(held_before) != stable(held_after)
                        or stable(held_after) != stable(named_after)
                    ):
                        raise BenchRefusal("spawn_failure")
                    final_records.append((name, stable(held_after), None))
                finally:
                    os.close(fd)
            elif stat.S_ISLNK(named_before.st_mode):
                target = os.readlink(name, dir_fd=directory_fd)
                named_after = os.stat(
                    name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                if stable(named_before) != stable(named_after):
                    raise BenchRefusal("spawn_failure")
                target_bytes = os.fsencode(target)
                digest.update(b"L")
                digest.update(len(name_bytes).to_bytes(8, "big"))
                digest.update(name_bytes)
                digest.update(len(target_bytes).to_bytes(8, "big"))
                digest.update(target_bytes)
                final_records.append((name, stable(named_after), target))
            else:
                raise BenchRefusal("spawn_failure")
        directory_after = os.fstat(directory_fd)
        if (
            (directory_before.st_dev, directory_before.st_ino)
            != (directory_after.st_dev, directory_after.st_ino)
            or sorted(os.listdir(directory_fd), key=os.fsencode) != names
        ):
            raise BenchRefusal("spawn_failure")
        for name, expected_identity, expected_target in final_records:
            observed = os.stat(
                name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if stable(observed) != expected_identity:
                raise BenchRefusal("spawn_failure")
            if (
                expected_target is not None
                and os.readlink(name, dir_fd=directory_fd) != expected_target
            ):
                raise BenchRefusal("spawn_failure")
        return digest.hexdigest()
    except BenchRefusal:
        raise
    except (OSError, OverflowError, TypeError, ValueError):
        raise BenchRefusal("spawn_failure") from None


def _release_directory_proof(
    directory_fd: int,
    *,
    manifest_sha256: str,
) -> ReleaseDirectoryProof:
    try:
        info = os.fstat(directory_fd)
        snapshot_sha256 = _release_snapshot_sha256(directory_fd)
        return ReleaseDirectoryProof(
            manifest_sha256=manifest_sha256,
            directory_dev=info.st_dev,
            directory_ino=info.st_ino,
            snapshot_sha256=snapshot_sha256,
        )
    except (TypeError, ValueError):
        raise BenchRefusal("spawn_failure") from None


def _open_release_directory(path: Path) -> int:
    """Open one absolute directory without following any path component."""

    if not isinstance(path, Path) or not path.is_absolute():
        raise OSError("release directory path")
    current: int | None = None
    try:
        current = os.open(
            "/",
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
        for component in path.parts[1:]:
            if component in {"", ".", ".."}:
                raise OSError("release directory component")
            opened = os.open(
                component,
                os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=current,
            )
            os.close(current)
            current = opened
        info = os.fstat(current)
        if not stat.S_ISDIR(info.st_mode):
            raise OSError("release directory type")
        result = current
        current = None
        return result
    finally:
        _close_fd(current)


def _verify_release_directory_fd(
    directory_fd: int,
    proof: ReleaseDirectoryProof,
) -> None:
    if type(proof) is not ReleaseDirectoryProof:
        raise BenchRefusal("spawn_failure")
    try:
        info = os.fstat(directory_fd)
        if (
            not stat.S_ISDIR(info.st_mode)
            or (info.st_dev, info.st_ino)
            != (proof.directory_dev, proof.directory_ino)
            or _release_snapshot_sha256(directory_fd)
            != proof.snapshot_sha256
        ):
            raise BenchRefusal("spawn_failure")
    except BenchRefusal:
        raise
    except OSError:
        raise BenchRefusal("spawn_failure") from None


@dataclass(frozen=True, slots=True)
class RehearsalPortLease:
    generation: int
    port: int

    def __post_init__(self) -> None:
        if (
            type(self.generation) is not int
            or self.generation <= 0
            or type(self.port) is not int
            or not 0 < self.port <= 65_535
            or self.port in {*PRODUCTION_PORTS, BENCH_PORT}
        ):
            raise ValueError("rehearsal_port_lease_invalid")


class RehearsalPortRegistry:
    """Hold one process-local reservation/lease with monotonic generations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._generation = 0
        self._reserved_generation: int | None = None
        self._active: RehearsalPortLease | None = None

    @property
    def current(self) -> RehearsalPortLease | None:
        with self._lock:
            return self._active

    def reserve_launch(self) -> int:
        with self._lock:
            if self._reserved_generation is not None or self._active is not None:
                raise BenchRefusal("provider_uncertain")
            self._generation += 1
            self._reserved_generation = self._generation
            return self._generation

    def activate_from_launcher(
        self, generation: int, port: int
    ) -> RehearsalPortLease:
        if type(generation) is not int or generation <= 0:
            raise BenchRefusal("provider_uncertain")
        try:
            lease = RehearsalPortLease(generation, port)
        except (TypeError, ValueError):
            raise BenchRefusal("provider_uncertain") from None
        with self._lock:
            if (
                self._reserved_generation != generation
                or self._active is not None
            ):
                raise BenchRefusal("provider_uncertain")
            self._reserved_generation = None
            self._active = lease
        return lease

    def cancel_launch(self, generation: int) -> None:
        if type(generation) is not int or generation <= 0:
            raise BenchRefusal("provider_uncertain")
        with self._lock:
            if self._reserved_generation == generation:
                self._reserved_generation = None
                return
            if self._active is not None and self._active.generation == generation:
                self._active = None
                return
            raise BenchRefusal("provider_uncertain")

    def snapshot_exact(self, lease: RehearsalPortLease) -> None:
        if type(lease) is not RehearsalPortLease:
            raise BenchRefusal("provider_uncertain")
        with self._lock:
            if self._active is not lease:
                raise BenchRefusal("provider_uncertain")

    def retire_exact(self, lease: RehearsalPortLease) -> None:
        if type(lease) is not RehearsalPortLease:
            raise BenchRefusal("provider_uncertain")
        with self._lock:
            if self._active is not lease:
                raise BenchRefusal("provider_uncertain")
            self._active = None


@dataclass(frozen=True)
class OwnedChild:
    pid: int
    pgid: int
    pidfd: int
    start_time_ticks: int
    pinned_path: str
    pinned_sha256: str
    exe_sha256: str
    port: int | None
    popen: subprocess.Popen[bytes]
    rehearsal_port_lease: RehearsalPortLease | None = None
    _stderr_capture: _BinaryStderrCapture | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if (
            any(
                type(value) is not int or value <= 0
                for value in (self.pid, self.pgid, self.start_time_ticks)
            )
            or type(self.pidfd) is not int
            or self.pidfd < 0
            or type(self.pinned_path) is not str
            or not os.path.isabs(self.pinned_path)
            or self.pinned_path.startswith("/proc/self/fd/")
            or type(self.pinned_sha256) is not str
            or _SHA256_RE.fullmatch(self.pinned_sha256) is None
            or type(self.exe_sha256) is not str
            or _SHA256_RE.fullmatch(self.exe_sha256) is None
            or (
                self.port is not None
                and (type(self.port) is not int or not 0 < self.port <= 65_535)
            )
            or (
                self.rehearsal_port_lease is not None
                and (
                    type(self.rehearsal_port_lease) is not RehearsalPortLease
                    or self.port != self.rehearsal_port_lease.port
                )
            )
            or not isinstance(self.popen, subprocess.Popen)
            or (
                self._stderr_capture is not None
                and type(self._stderr_capture) is not _BinaryStderrCapture
            )
        ):
            raise ValueError("owned_child_invalid")


@dataclass(frozen=True)
class FinalizeResult:
    outcome: Literal["clean", "cleanup_incomplete", "pid_reuse_detected"]
    signals_sent: tuple[str, ...]
    quadruple_reproofs: int
    surviving_pgid_members: tuple[int, ...]
    listener_free: bool | None
    started_at: str
    finished_at: str

    def __post_init__(self) -> None:
        if (
            self.outcome
            not in {"clean", "cleanup_incomplete", "pid_reuse_detected"}
            or type(self.signals_sent) is not tuple
            or any(signal_name not in {"SIGTERM", "SIGKILL"} for signal_name in self.signals_sent)
            or type(self.quadruple_reproofs) is not int
            or self.quadruple_reproofs < 0
            or type(self.surviving_pgid_members) is not tuple
            or any(type(pid) is not int or pid <= 0 for pid in self.surviving_pgid_members)
            or (self.listener_free is not None and type(self.listener_free) is not bool)
            or type(self.started_at) is not str
            or not self.started_at
            or type(self.finished_at) is not str
            or not self.finished_at
        ):
            raise ValueError("finalize_result_invalid")


@dataclass(frozen=True)
class _SealedExecutableSnapshot:
    fd: int
    pinned_path: str
    pinned_sha256: str


def _hash_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        raise BenchRefusal("spawn_failure") from None


def _hash_fd(fd: int) -> str:
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        os.lseek(fd, 0, os.SEEK_SET)
        return digest.hexdigest()
    except OSError:
        raise BenchRefusal("spawn_failure") from None


def _sealed_executable_snapshot(pin: SpawnPin) -> _SealedExecutableSnapshot:
    """Seal, then hash, the one entry executable the guard will use.

    This binds only the entry executable.  Runtime shared-library integrity is
    independently owned by the static runtime-manifest proof.
    """

    source_fd: int | None = None
    snapshot_fd: int | None = None
    try:
        source_fd = os.open(pin.pinned_path, os.O_RDONLY | os.O_CLOEXEC)
        source_before = os.fstat(source_fd)
        if not stat.S_ISREG(source_before.st_mode):
            raise BenchRefusal("spawn_failure")

        snapshot_fd = os.memfd_create(
            "cuda-bench-entry",
            _EXECUTABLE_MEMFD_FLAGS,
        )
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            offset = 0
            while offset < len(chunk):
                written = os.write(snapshot_fd, chunk[offset:])
                if written <= 0:
                    raise OSError("short memfd write")
                offset += written

        source_after = os.fstat(source_fd)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(
            getattr(source_before, name) != getattr(source_after, name)
            for name in stable_fields
        ):
            raise BenchRefusal("spawn_failure")

        fcntl.fcntl(snapshot_fd, fcntl.F_ADD_SEALS, _REQUIRED_MEMFD_SEALS)
        observed_seals = fcntl.fcntl(snapshot_fd, fcntl.F_GET_SEALS)
        if observed_seals & _REQUIRED_MEMFD_SEALS != _REQUIRED_MEMFD_SEALS:
            raise BenchRefusal("spawn_failure")
        snapshot_sha256 = _hash_fd(snapshot_fd)
        if snapshot_sha256 != pin.pinned_sha256:
            raise BenchRefusal("spawn_failure")
        snapshot_stat = os.fstat(snapshot_fd)
        if not snapshot_stat.st_mode & 0o111 or not os.access(
            f"/proc/self/fd/{snapshot_fd}", os.X_OK
        ):
            raise BenchRefusal("spawn_failure")
        result = _SealedExecutableSnapshot(
            fd=snapshot_fd,
            pinned_path=str(pin.pinned_path),
            pinned_sha256=snapshot_sha256,
        )
        snapshot_fd = None
        return result
    except BenchRefusal:
        raise
    except (OSError, ValueError):
        raise BenchRefusal("spawn_failure") from None
    finally:
        for fd in (source_fd, snapshot_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass


def _validate_spawn_inputs(
    argv: list[str], *, pin: SpawnPin, env: dict[str, str]
) -> None:
    if (
        type(argv) is not list
        or not argv
        or any(type(part) is not str or not part or "\0" in part for part in argv)
        or type(env) is not dict
        or any(
            type(key) is not str
            or not key
            or "=" in key
            or "\0" in key
            or type(value) is not str
            or "\0" in value
            for key, value in env.items()
        )
    ):
        raise BenchRefusal("spawn_failure")
    prefix = pin.required_argv_prefix
    if tuple(argv[: len(prefix)]) != prefix:
        raise BenchRefusal("spawn_failure")
    if pin.kind == "binary":
        if argv[0] != str(pin.pinned_path):
            raise BenchRefusal("spawn_failure")
    else:
        expected = (sys.executable, "-B", "-I", str(pin.pinned_path))
        if tuple(argv[:4]) != expected:
            raise BenchRefusal("spawn_failure")
        try:
            if pin.pinned_path.resolve(strict=True) != pin.pinned_path:
                raise BenchRefusal("spawn_failure")
        except OSError:
            raise BenchRefusal("spawn_failure") from None


def _close_popen_streams(popen: subprocess.Popen[bytes]) -> None:
    for stream in (popen.stdin, popen.stdout, popen.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def _pidfd_status(pidfd: int) -> Literal["alive", "gone", "uncertain"]:
    try:
        poller = select.poll()
        poller.register(
            pidfd,
            select.POLLIN | select.POLLHUP | select.POLLERR | select.POLLNVAL,
        )
        events = poller.poll(0)
        if not events:
            return "alive"
        event_mask = events[0][1]
        if event_mask & select.POLLNVAL or event_mask & select.POLLERR:
            return "uncertain"
        if event_mask & select.POLLIN:
            return "gone"
        return "uncertain"
    except (OSError, ValueError):
        return "uncertain"


def _wait_pidfd_gone(pidfd: int, timeout_s: float) -> bool:
    try:
        poller = select.poll()
        poller.register(
            pidfd,
            select.POLLIN | select.POLLHUP | select.POLLERR | select.POLLNVAL,
        )
        events = poller.poll(max(0, int(timeout_s * 1000)))
        return bool(events) and bool(events[0][1] & select.POLLIN)
    except (OSError, ValueError):
        return False


def _pidfd_bound_pid(
    pidfd: int,
) -> tuple[Literal["bound", "gone", "unavailable"], int | None]:
    try:
        rendered = Path(f"/proc/self/fdinfo/{pidfd}").read_text(
            encoding="utf-8", errors="strict"
        )
    except (OSError, UnicodeError):
        return "unavailable", None
    matches = [
        line.split(":", 1)[1].strip()
        for line in rendered.splitlines()
        if line.startswith("Pid:")
    ]
    if len(matches) != 1:
        return "unavailable", None
    try:
        pid = int(matches[0])
    except ValueError:
        return "unavailable", None
    if pid == -1:
        return "gone", None
    if pid <= 0:
        return "unavailable", None
    return "bound", pid


def _close_fd(fd: int | None) -> None:
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass


def _cleanup_inert_guard(
    popen: subprocess.Popen[bytes] | None,
    *,
    pidfd: int | None,
    gate_write: int | None,
    exec_read: int | None,
) -> bool:
    _close_fd(gate_write)
    _close_fd(exec_read)
    if popen is None:
        _close_fd(pidfd)
        return True
    clean = True
    try:
        popen.wait(timeout=KILL_WAIT_S)
    except (subprocess.TimeoutExpired, OSError):
        clean = False
        state, bound_pid = (
            _pidfd_bound_pid(pidfd) if pidfd is not None else ("unavailable", None)
        )
        if state == "bound" and bound_pid == popen.pid:
            try:
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)  # type: ignore[arg-type]
                popen.wait(timeout=KILL_WAIT_S)
                clean = True
            except (OSError, subprocess.TimeoutExpired):
                clean = False
    if popen.poll() is None:
        clean = False
    try:
        if _pgid_members(popen.pid):
            clean = False
    except BenchRefusal:
        clean = False
    _close_fd(pidfd)
    _close_popen_streams(popen)
    return clean


def _guarded_popen(
    argv: list[str],
    *,
    env: dict[str, str],
    capture_stdout: bool,
    pinned_fd: int,
    pin_kind: Literal["binary", "python_file"],
    release_directory_fd: int | None = None,
) -> tuple[
    subprocess.Popen[bytes],
    int,
    int,
    int,
    set[signal.Signals],
    _BinaryStderrCapture | None,
]:
    gate_read: int | None = None
    gate_write: int | None = None
    exec_read: int | None = None
    exec_write: int | None = None
    popen: subprocess.Popen[bytes] | None = None
    pidfd: int | None = None
    old_mask: set[signal.Signals] | None = None
    stderr_write: int | None = None
    stderr_capture: _BinaryStderrCapture | None = None
    cleanup_complete = True
    try:
        old_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGINT, signal.SIGTERM},
        )
        gate_read, gate_write = os.pipe2(os.O_CLOEXEC)
        exec_read, exec_write = os.pipe2(os.O_CLOEXEC)
        if pin_kind == "binary":
            stderr_capture, stderr_write = _start_binary_stderr_capture()
        target_mask = old_mask.difference({signal.SIGINT, signal.SIGTERM})
        encoded_mask = ",".join(str(int(value)) for value in sorted(target_mask))
        if pin_kind == "python_file" and release_directory_fd is not None:
            raise BenchRefusal("spawn_failure")
        guard_argv = [
            sys.executable,
            "-B",
            "-I",
            "-c",
            _GUARD_CODE,
            str(gate_read),
            str(exec_write),
            str(pinned_fd),
            pin_kind,
            str(-1 if release_directory_fd is None else release_directory_fd),
            encoded_mask,
            *argv,
        ]
        passed_fds = (
            (gate_read, exec_write, pinned_fd)
            if release_directory_fd is None
            else (gate_read, exec_write, pinned_fd, release_directory_fd)
        )
        try:
            popen = subprocess.Popen(
                guard_argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
                stderr=(
                    stderr_write
                    if stderr_write is not None
                    else subprocess.DEVNULL
                ),
                env=dict(env),
                start_new_session=True,
                pass_fds=passed_fds,
                close_fds=True,
                bufsize=0,
            )
        finally:
            _close_fd(stderr_write)
            stderr_write = None
        _close_fd(gate_read)
        gate_read = None
        _close_fd(exec_write)
        exec_write = None
        pidfd = os.pidfd_open(popen.pid)
        binding_state, bound_pid = _pidfd_bound_pid(pidfd)
        if binding_state != "bound" or bound_pid != popen.pid:
            raise BenchRefusal("spawn_failure")
        return popen, pidfd, gate_write, exec_read, old_mask, stderr_capture
    except BaseException as exc:
        _close_fd(stderr_write)
        _close_fd(gate_read)
        _close_fd(exec_write)
        cleanup_complete = _cleanup_inert_guard(
            popen,
            pidfd=pidfd,
            gate_write=gate_write,
            exec_read=exec_read,
        )
        if old_mask is not None:
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            except BaseException:
                cleanup_complete = False
        if (
            popen is not None
            and stderr_capture is not None
            and not isinstance(exc, (KeyboardInterrupt, SystemExit))
        ):
            _raise_binary_spawn_failure(
                exc,
                bootstrap_cleanup=_BootstrapCleanupResult(
                    outcome=(
                        "clean" if cleanup_complete else "cleanup_incomplete"
                    ),
                    observed_returncode=None,
                    exited_before_cleanup_signal=False,
                ),
                stderr_capture=stderr_capture,
            )
        try:
            _finish_binary_stderr_capture(stderr_capture)
        except BenchRefusal:
            cleanup_complete = False
        if not cleanup_complete:
            raise BenchRefusal("cleanup_incomplete") from exc
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, BenchRefusal):
            raise
        raise BenchRefusal("spawn_failure") from None


def _release_guard(gate_write: int, exec_read: int) -> None:
    try:
        try:
            if os.write(gate_write, _GUARD_GO_BYTE) != 1:
                raise OSError("short guard write")
        finally:
            os.close(gate_write)
        deadline = time.monotonic() + READINESS_TIMEOUT_S
        while time.monotonic() < deadline:
            ready, _, _ = select.select(
                [exec_read], [], [], min(0.1, deadline - time.monotonic())
            )
            if not ready:
                continue
            marker = os.read(exec_read, 1)
            if marker == b"":
                return
            raise BenchRefusal("spawn_failure")
        raise BenchRefusal("spawn_failure")
    except OSError:
        raise BenchRefusal("spawn_failure") from None
    finally:
        os.close(exec_read)


def _read_stub_announcement(popen: subprocess.Popen[bytes]) -> int:
    if popen.stdout is None:
        raise BenchRefusal("spawn_failure")
    fd = popen.stdout.fileno()
    payload = bytearray()
    deadline = time.monotonic() + READINESS_TIMEOUT_S
    try:
        while b"\n" not in payload and len(payload) <= _STUB_ANNOUNCEMENT_CAP:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BenchRefusal("spawn_failure")
            ready, _, _ = select.select([fd], [], [], min(0.1, remaining))
            if not ready:
                if popen.poll() is not None:
                    raise BenchRefusal("spawn_failure")
                continue
            chunk = os.read(fd, _STUB_ANNOUNCEMENT_CAP + 1 - len(payload))
            if not chunk:
                raise BenchRefusal("spawn_failure")
            payload.extend(chunk)
        match = _STUB_ANNOUNCEMENT_RE.fullmatch(bytes(payload))
        if match is None:
            raise BenchRefusal("spawn_failure")
        port = int(match.group(1))
        if not 0 < port <= 65_535 or port in {*PRODUCTION_PORTS, BENCH_PORT}:
            raise BenchRefusal("spawn_failure")
        return port
    except OSError:
        raise BenchRefusal("spawn_failure") from None


def _parse_proc_stat(rendered: str) -> tuple[int, int, int]:
    try:
        open_paren = rendered.index("(")
        close_paren = rendered.rindex(")")
        pid = int(rendered[:open_paren].strip())
        suffix = rendered[close_paren + 1 :].split()
        pgid = int(suffix[2])
        start_time_ticks = int(suffix[19])
    except (IndexError, TypeError, ValueError):
        raise OSError("malformed proc stat") from None
    if pid <= 0 or pgid < 0 or start_time_ticks <= 0:
        raise OSError("malformed proc stat")
    return pid, pgid, start_time_ticks


def _capture_target_identity(pid: int) -> tuple[int, int, str]:
    if type(pid) is not int or pid <= 0:
        raise OSError("invalid pid")
    rendered = Path(f"/proc/{pid}/stat").read_text(
        encoding="utf-8", errors="surrogateescape"
    )
    observed_pid, pgid, start_time_ticks = _parse_proc_stat(rendered)
    if observed_pid != pid:
        raise OSError("pid mismatch")
    exe_sha256 = hashlib.sha256(Path(f"/proc/{pid}/exe").read_bytes()).hexdigest()
    return pgid, start_time_ticks, exe_sha256


def _bootstrap_abort(
    popen: subprocess.Popen[bytes],
    pidfd: int,
    *,
    port: int | None,
) -> _BootstrapCleanupResult:
    complete = True
    cleanup_signal_sent = False
    try:
        status = _pidfd_status(pidfd)
        binding_state, bound_pid = _pidfd_bound_pid(pidfd)
        target_gone_without_signal = status == "gone" or (
            status == "alive" and binding_state == "gone"
        )
        if (
            status == "alive"
            and binding_state == "bound"
            and bound_pid == popen.pid
        ):
            try:
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                cleanup_signal_sent = True
            except ProcessLookupError:
                if _pidfd_status(pidfd) != "gone":
                    complete = False
            except OSError:
                complete = False
        elif not target_gone_without_signal:
            complete = False
        try:
            popen.wait(timeout=KILL_WAIT_S)
        except (OSError, subprocess.TimeoutExpired):
            complete = False
        exited_before_cleanup_signal = (
            popen.returncode is not None and not cleanup_signal_sent
        )
        try:
            if _pgid_members(popen.pid):
                complete = False
        except BenchRefusal:
            complete = False
        if port is not None:
            try:
                if not RealPortProbe().is_free(port):
                    complete = False
            except BenchRefusal:
                complete = False
        return _BootstrapCleanupResult(
            outcome="clean" if complete else "cleanup_incomplete",
            observed_returncode=popen.returncode,
            exited_before_cleanup_signal=exited_before_cleanup_signal,
        )
    finally:
        _close_fd(pidfd)
        _close_popen_streams(popen)


def spawn_pinned(
    argv: list[str],
    *,
    pin: SpawnPin,
    env: dict[str, str],
    admitted_port: int | None = None,
    _post_identity: Callable[[int], RehearsalPortLease] | None = None,
    _release_directory: _LauncherReleaseDirectory | None = None,
) -> OwnedChild:
    _validate_spawn_inputs(argv, pin=pin, env=env)
    if _post_identity is not None and (
        pin.kind != "python_file" or not callable(_post_identity)
    ):
        raise BenchRefusal("spawn_failure")
    if (
        admitted_port is not None
        and (
            pin.kind != "binary"
            or type(admitted_port) is not int
            or not 0 < admitted_port <= 65_535
        )
    ):
        raise BenchRefusal("spawn_failure")
    if _release_directory is not None and (
        pin.kind != "binary"
        or type(_release_directory) is not _LauncherReleaseDirectory
        or _release_directory.pin is not pin
    ):
        raise BenchRefusal("spawn_failure")
    if pin.kind == "binary" and _release_directory is None:
        raise BenchRefusal("spawn_failure")
    release_directory_fd = (
        None if _release_directory is None else _release_directory.fd
    )
    if _release_directory is not None:
        _verify_release_directory_fd(
            release_directory_fd,
            _release_directory.proof,
        )
    snapshot = _sealed_executable_snapshot(pin)
    try:
        (
            popen,
            pidfd,
            gate_write,
            exec_read,
            old_mask,
            stderr_capture,
        ) = _guarded_popen(
            argv,
            env=env,
            capture_stdout=pin.kind == "python_file",
            pinned_fd=snapshot.fd,
            pin_kind=pin.kind,
            release_directory_fd=release_directory_fd,
        )
    finally:
        _close_fd(snapshot.fd)
    port = admitted_port
    mask_restored = False
    target_release_attempted = False
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        mask_restored = True
        target_release_attempted = True
        _release_guard(gate_write, exec_read)
        if pin.kind == "python_file":
            port = _read_stub_announcement(popen)
        pgid, start_time_ticks, exe_sha256 = _capture_target_identity(popen.pid)
        if pgid != popen.pid:
            raise BenchRefusal("spawn_failure")
        expected_exe_sha256 = (
            _hash_file(Path(sys.executable).resolve())
            if pin.kind == "python_file"
            else pin.pinned_sha256
        )
        if exe_sha256 != expected_exe_sha256:
            raise BenchRefusal("spawn_failure")
        rehearsal_port_lease = None
        if _post_identity is not None:
            if port is None:
                raise BenchRefusal("spawn_failure")
            rehearsal_port_lease = _post_identity(port)
            if (
                type(rehearsal_port_lease) is not RehearsalPortLease
                or rehearsal_port_lease.port != port
            ):
                raise BenchRefusal("spawn_failure")
        return OwnedChild(
            pid=popen.pid,
            pgid=pgid,
            pidfd=pidfd,
            start_time_ticks=start_time_ticks,
            pinned_path=snapshot.pinned_path,
            pinned_sha256=pin.pinned_sha256,
            exe_sha256=exe_sha256,
            port=port,
            popen=popen,
            rehearsal_port_lease=rehearsal_port_lease,
            _stderr_capture=stderr_capture,
        )
    except BaseException as exc:
        if target_release_attempted:
            bootstrap_cleanup = _bootstrap_abort(popen, pidfd, port=port)
        else:
            cleanup_complete = _cleanup_inert_guard(
                popen,
                pidfd=pidfd,
                gate_write=gate_write,
                exec_read=exec_read,
            )
            bootstrap_cleanup = _BootstrapCleanupResult(
                outcome="clean" if cleanup_complete else "cleanup_incomplete",
                observed_returncode=None,
                exited_before_cleanup_signal=False,
            )
        if not mask_restored:
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            except BaseException:
                bootstrap_cleanup = _BootstrapCleanupResult(
                    outcome="cleanup_incomplete",
                    observed_returncode=(
                        bootstrap_cleanup.observed_returncode
                    ),
                    exited_before_cleanup_signal=(
                        bootstrap_cleanup.exited_before_cleanup_signal
                    ),
                )
        cleanup_complete = bootstrap_cleanup.outcome == "clean"
        if (
            stderr_capture is not None
            and not isinstance(exc, (KeyboardInterrupt, SystemExit))
        ):
            _raise_binary_spawn_failure(
                exc,
                bootstrap_cleanup=bootstrap_cleanup,
                stderr_capture=stderr_capture,
            )
        try:
            _finish_binary_stderr_capture(stderr_capture)
        except BenchRefusal:
            cleanup_complete = False
        if not cleanup_complete:
            raise BenchRefusal("cleanup_incomplete") from exc
        if isinstance(exc, BenchRefusal):
            raise
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise BenchRefusal("spawn_failure") from None


@dataclass(frozen=True, slots=True)
class RealServerLauncher:
    pin: SpawnPin
    release_proof: ReleaseDirectoryProof
    tier: str = field(default="production", init=False)

    def __post_init__(self) -> None:
        pin = self.pin
        if (
            not isinstance(pin, SpawnPin)
            or pin.kind != "binary"
            or type(self.release_proof) is not ReleaseDirectoryProof
        ):
            raise ValueError("spawn_pin_invalid")

    def _open_verified_release_directory(self) -> _LauncherReleaseDirectory:
        proof = self.release_proof
        if type(proof) is not ReleaseDirectoryProof:
            raise BenchRefusal("spawn_failure")
        directory_fd: int | None = None
        try:
            directory_fd = _open_release_directory(self.pin.pinned_path.parent)
            _verify_release_directory_fd(directory_fd, proof)
            result = _LauncherReleaseDirectory(
                directory_fd,
                self.pin,
                proof,
                _guard=_RELEASE_DIRECTORY_HANDLE_GUARD,
            )
            directory_fd = None
            return result
        except BenchRefusal:
            raise
        except OSError:
            raise BenchRefusal("spawn_failure") from None
        finally:
            _close_fd(directory_fd)

    def verify_release_directory(self) -> None:
        release_directory = self._open_verified_release_directory()
        os.close(release_directory.fd)

    def spawn(self, argv: list[str], env: dict[str, str]) -> OwnedChild:
        ports = [
            argv[index + 1]
            for index, value in enumerate(argv[:-1])
            if value == "--port"
        ] if type(argv) is list else []
        if ports != [str(BENCH_PORT)]:
            raise BenchRefusal("spawn_failure")
        release_directory = self._open_verified_release_directory()
        try:
            try:
                return spawn_pinned(
                    argv,
                    pin=self.pin,
                    env=env,
                    admitted_port=BENCH_PORT,
                    _release_directory=release_directory,
                )
            except BaseException as original:
                try:
                    _verify_release_directory_fd(
                        release_directory.fd,
                        self.release_proof,
                    )
                except BenchRefusal:
                    if isinstance(original, _BinarySpawnFailure):
                        raise original
                    if isinstance(original, (KeyboardInterrupt, SystemExit)) or (
                        isinstance(original, BenchRefusal)
                        and original.code
                        in {"cleanup_incomplete", "pid_reuse_detected"}
                    ):
                        raise original
                    raise
                raise
        finally:
            os.close(release_directory.fd)


@dataclass(frozen=True, slots=True)
class RehearsalServerLauncher:
    pin: SpawnPin
    rehearsal_ports: RehearsalPortRegistry | None = None
    tier: str = field(default="rehearsal", init=False)

    def __post_init__(self) -> None:
        pin = self.pin
        if (
            not isinstance(pin, SpawnPin)
            or pin.kind != "python_file"
            or pin.pinned_path != _REHEARSAL_STUB_PATH
            or (
                self.rehearsal_ports is not None
                and type(self.rehearsal_ports) is not RehearsalPortRegistry
            )
        ):
            raise ValueError("spawn_pin_invalid")

    def spawn(self, argv: list[str], env: dict[str, str]) -> OwnedChild:
        registry = self.rehearsal_ports
        if registry is None:
            return spawn_pinned(argv, pin=self.pin, env=env)
        generation = registry.reserve_launch()
        try:
            return spawn_pinned(
                argv,
                pin=self.pin,
                env=env,
                _post_identity=lambda port: registry.activate_from_launcher(
                    generation, port
                ),
            )
        except BaseException:
            try:
                registry.cancel_launch(generation)
            except BenchRefusal:
                pass
            raise


def _pgid_members(pgid: int) -> list[int]:
    if type(pgid) is not int or pgid <= 0:
        raise BenchRefusal("cleanup_incomplete")
    members: list[int] = []
    try:
        entries = tuple(os.scandir("/proc"))
    except OSError:
        raise BenchRefusal("cleanup_incomplete") from None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            rendered = Path(entry.path, "stat").read_text(
                encoding="utf-8", errors="surrogateescape"
            )
            pid, observed_pgid, _start = _parse_proc_stat(rendered)
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError:
            raise BenchRefusal("cleanup_incomplete") from None
        if observed_pgid == pgid:
            members.append(pid)
    return sorted(set(members))


def _identity_proof(
    child: OwnedChild,
) -> Literal["match", "mismatch", "unavailable"]:
    try:
        pgid, start_time_ticks, exe_sha256 = _capture_target_identity(child.pid)
    except OSError:
        return "unavailable"
    return "match" if (
        pgid == child.pgid
        and start_time_ticks == child.start_time_ticks
        and exe_sha256 == child.exe_sha256
    ) else "mismatch"


def _identity_matches(child: OwnedChild) -> bool:
    return _identity_proof(child) == "match"


def _signal_authority_proof(
    child: OwnedChild,
) -> Literal["match", "mismatch", "gone", "unavailable"]:
    if child.popen.pid != child.pid:
        return "mismatch"
    pidfd_status = _pidfd_status(child.pidfd)
    binding_state, bound_pid = _pidfd_bound_pid(child.pidfd)
    if pidfd_status == "gone" or binding_state == "gone":
        return "gone"
    if pidfd_status == "uncertain" or binding_state == "unavailable":
        return "unavailable"
    if bound_pid != child.pid:
        return "mismatch"
    return _identity_proof(child)


def _reap_if_gone(child: OwnedChild) -> None:
    if _pidfd_status(child.pidfd) == "gone":
        try:
            child.popen.wait(timeout=0)
        except (subprocess.TimeoutExpired, ChildProcessError):
            pass


def _wait_group_absent(pgid: int, timeout_s: float) -> tuple[int, ...]:
    deadline = time.monotonic() + timeout_s
    while True:
        members = tuple(_pgid_members(pgid))
        if not members:
            return ()
        if time.monotonic() >= deadline:
            return members
        time.sleep(0.01)


def _wait_listener_free(
    port_probe: PortProbe,
    port: int,
    *,
    lease: RehearsalPortLease | None = None,
) -> bool | None:
    deadline = time.monotonic() + LISTENER_WAIT_S
    while True:
        try:
            free = (
                port_probe.is_free(port)
                if lease is None
                else port_probe.is_free(port, lease=lease)
            )
            if free:
                return True
        except BenchRefusal:
            return None
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)


def _best_effort_timestamp(clock: Clock) -> tuple[str, bool]:
    """Read evidence time without allowing the evidence provider to gate cleanup."""

    try:
        rendered = clock.now_utc()
    except BaseException:
        return "timestamp_unavailable", False
    if type(rendered) is not str or not rendered:
        return "timestamp_unavailable", False
    return rendered, True


def finalize(
    child: OwnedChild,
    *,
    clock: Clock,
    port_probe: PortProbe,
    port: int | None,
) -> FinalizeResult:
    started_at, start_time_available = _best_effort_timestamp(clock)
    signals_sent: list[str] = []
    reproofs = 0
    outcome: Literal["clean", "cleanup_incomplete", "pid_reuse_detected"] = (
        "clean" if start_time_available else "cleanup_incomplete"
    )
    listener_free: bool | None = None
    survivors: tuple[int, ...] = ()
    lease = child.rehearsal_port_lease
    effective_port = port
    port_binding_valid = True
    if lease is not None:
        if child.port != lease.port:
            port_binding_valid = False
        elif port is None:
            effective_port = lease.port
        elif port != lease.port:
            port_binding_valid = False
    if not port_binding_valid:
        outcome = "cleanup_incomplete"

    def finish() -> FinalizeResult:
        nonlocal outcome
        try:
            os.close(child.pidfd)
        except OSError:
            pass
        _close_popen_streams(child.popen)
        finished_at, finish_time_available = _best_effort_timestamp(clock)
        if not finish_time_available and outcome == "clean":
            outcome = "cleanup_incomplete"
        return FinalizeResult(
            outcome=outcome,
            signals_sent=tuple(signals_sent),
            quadruple_reproofs=reproofs,
            surviving_pgid_members=survivors,
            listener_free=listener_free,
            started_at=started_at,
            finished_at=finished_at,
        )

    status = _pidfd_status(child.pidfd)
    if status == "uncertain":
        outcome = "cleanup_incomplete"
        try:
            survivors = tuple(_pgid_members(child.pgid))
        except BenchRefusal:
            survivors = ()
        return finish()
    if status == "gone":
        _reap_if_gone(child)
        try:
            survivors = tuple(_pgid_members(child.pgid))
        except BenchRefusal:
            outcome = "cleanup_incomplete"
            return finish()
        if survivors:
            outcome = "cleanup_incomplete"
            return finish()
    else:
        try:
            members = tuple(_pgid_members(child.pgid))
        except BenchRefusal:
            outcome = "cleanup_incomplete"
            return finish()
        unexpected = tuple(pid for pid in members if pid != child.pid)
        if unexpected:
            outcome = "cleanup_incomplete"
            survivors = members
            return finish()
        reproofs += 1
        proof = _signal_authority_proof(child)
        if proof == "mismatch":
            outcome = "pid_reuse_detected"
            survivors = members
            return finish()
        if proof == "unavailable":
            outcome = "cleanup_incomplete"
            survivors = members
            return finish()
        if proof == "match":
            try:
                signal.pidfd_send_signal(child.pidfd, signal.SIGTERM)
                signals_sent.append("SIGTERM")
            except ProcessLookupError:
                pass
            except OSError:
                outcome = "cleanup_incomplete"
                survivors = members
                return finish()
        if not _wait_pidfd_gone(child.pidfd, SIGTERM_GRACE_S):
            try:
                members = tuple(_pgid_members(child.pgid))
            except BenchRefusal:
                outcome = "cleanup_incomplete"
                return finish()
            unexpected = tuple(pid for pid in members if pid != child.pid)
            if unexpected:
                outcome = "cleanup_incomplete"
                survivors = members
                return finish()
            reproofs += 1
            proof = _signal_authority_proof(child)
            if proof == "mismatch":
                outcome = "pid_reuse_detected"
                survivors = members
                return finish()
            if proof == "unavailable":
                outcome = "cleanup_incomplete"
                survivors = members
                return finish()
            if proof == "match":
                try:
                    signal.pidfd_send_signal(child.pidfd, signal.SIGKILL)
                    signals_sent.append("SIGKILL")
                except ProcessLookupError:
                    pass
                except OSError:
                    outcome = "cleanup_incomplete"
                    survivors = members
                    return finish()
                if not _wait_pidfd_gone(child.pidfd, KILL_WAIT_S):
                    outcome = "cleanup_incomplete"
        _reap_if_gone(child)

    try:
        survivors = _wait_group_absent(child.pgid, KILL_WAIT_S)
    except BenchRefusal:
        outcome = "cleanup_incomplete"
        survivors = ()
        return finish()
    if survivors:
        outcome = "cleanup_incomplete"
        return finish()
    if port_binding_valid and effective_port is not None:
        listener_free = _wait_listener_free(
            port_probe,
            effective_port,
            lease=lease,
        )
        if listener_free is not True:
            outcome = "cleanup_incomplete"
    return finish()


@dataclass(frozen=True, slots=True)
class ParentCompletionEvidence:
    packet: cm.PhasePacket
    packet_ref: str
    packet_doc: cm.PersistedDoc
    admission: cm.CommandAdmissionPreimage
    completion_doc: cm.PersistedDoc

    def __post_init__(self) -> None:
        try:
            if (
                type(self.packet_doc) is not cm.PersistedDoc
                or type(self.completion_doc) is not cm.PersistedDoc
                or type(self.admission) is not cm.CommandAdmissionPreimage
            ):
                raise ValueError("parent completion")
            packet_doc = cm.PersistedDoc(self.packet_doc.wrapper_bytes)
            completion_doc = cm.PersistedDoc(
                self.completion_doc.wrapper_bytes
            )
            admission = cm.CommandAdmissionPreimage(
                self.admission.selected_ref,
                self.admission.wrapper_bytes,
            )
            completion = completion_doc.obj
            if (
                type(self.packet) is not cm.PhasePacket
                or type(packet_doc.obj) is not cm.PhasePacket
                or packet_doc.obj != self.packet
                or packet_doc.obj != self.packet_doc.obj
                or completion_doc.obj != self.completion_doc.obj
                or admission != self.admission
                or type(completion) is not cm.CommandCompletionDoc
                or admission.command != "vulkan-baseline"
                or admission.window_id != self.packet.window_id
                or completion.command != "vulkan-baseline"
                or completion.ordinal != admission.ordinal
                or completion.decoded_phase != "vulkan_baseline"
                or completion.window_id != self.packet.window_id
                or completion.admission_ref != admission.selected_ref
                or completion.admission_sha256 != admission.file_sha256
                or completion.artifact_ref != self.packet_ref
                or completion.artifact_sha256 != packet_doc.file_sha256
                or completion.artifact_schema != cm.PHASE_PACKET_SCHEMA
                or cm._compare_utc_z(
                    admission.timestamp,
                    completion.timestamp,
                )
                >= 0
                or cm._compare_utc_z(
                    packet_doc.obj.timestamp,
                    completion.timestamp,
                )
                > 0
            ):
                raise ValueError("parent completion")
        except (AttributeError, TypeError, ValueError) as exc:
            raise BenchRefusal("continuation_parent_mismatch") from exc


class AuthorizationGate(Protocol):
    tier: str

    def validate(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        expected_window_id: str,
        parent_window: object | None,
        parent_packet: cm.PhasePacket | None,
        parent_completion: ParentCompletionEvidence | None = None,
        clock: Clock,
    ) -> None: ...

    def consume(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        expected_window_id: str,
        parent_window: object | None,
        parent_packet: cm.PhasePacket | None,
        parent_completion: ParentCompletionEvidence | None = None,
        authority_root: Path,
        receipt_root: Path,
        clock: Clock,
    ) -> "ConsumedAuthority": ...  # noqa: F821


class ServerClient(Protocol):
    tier: str

    def health(self, port: int) -> bool: ...

    def models(self, port: int) -> list[str]: ...

    def stream(self, port: int, prompt: str) -> "TurnMeasurement": ...  # noqa: F821


@dataclass(frozen=True, slots=True)
class TurnMeasurement:
    """One private in-memory turn measurement with a content-light repr."""

    ttft_ms: float
    e2e_ms: float
    content: str = field(repr=False)
    timings: dict[str, object] = field(repr=False)
    terminal: dict[str, object] = field(repr=False)

    def __repr__(self) -> str:
        return (
            "TurnMeasurement("
            f"ttft_ms={self.ttft_ms!r}, e2e_ms={self.e2e_ms!r}, "
            f"literal_chars={len(self.content)}, "
            f"timing_field_count={len(self.timings)}, "
            f"terminal_field_count={len(self.terminal)})"
        )


def parse_mtp(terminal_timings: dict[str, object]) -> tuple[int, int, int]:
    """Validate the two b9596 per-request MTP counters and derive rejected."""

    if type(terminal_timings) is not dict:
        raise BenchRefusal("malformed_response")
    if "draft_n" not in terminal_timings or "draft_n_accepted" not in terminal_timings:
        raise BenchRefusal("mtp_unproven")
    drafted = terminal_timings["draft_n"]
    accepted = terminal_timings["draft_n_accepted"]
    if (
        type(drafted) is not int
        or type(accepted) is not int
        or drafted < 1
        or accepted < 0
        or accepted > drafted
    ):
        raise BenchRefusal("malformed_response")
    return drafted, accepted, drafted - accepted


def aggregate_mtp(
    cycle_turn_mtp: list[list[tuple[int, int, int]]],
) -> tuple[int, int, int]:
    """Aggregate exactly seven validated request counters across three cycles."""

    if type(cycle_turn_mtp) is not list or len(cycle_turn_mtp) != 3:
        raise ValueError("sample_count")
    drafted_total = 0
    accepted_total = 0
    for cycle in cycle_turn_mtp:
        if type(cycle) is not list or len(cycle) != 7:
            raise ValueError("sample_count")
        for item in cycle:
            if type(item) is not tuple or len(item) != 3:
                raise BenchRefusal("malformed_response")
            drafted, accepted, rejected = item
            if (
                type(drafted) is not int
                or type(accepted) is not int
                or type(rejected) is not int
                or drafted < 1
                or accepted < 0
                or accepted > drafted
                or rejected != drafted - accepted
            ):
                raise BenchRefusal("malformed_response")
            drafted_total += drafted
            accepted_total += accepted
    return drafted_total, accepted_total, drafted_total - accepted_total


def _finite_nonnegative_real(value: object) -> bool:
    if type(value) not in {int, float}:
        return False
    try:
        numeric = float(value)
    except OverflowError:
        return False
    return math.isfinite(numeric) and numeric >= 0


def phase_statistics(turns: list[TurnMeasurement]) -> dict[str, float]:
    """Recompute the frozen latency and throughput statistics for 21 turns."""

    if (
        type(turns) is not list
        or len(turns) != cm.FROZEN_MEASURED_SAMPLE_COUNT
        or any(type(turn) is not TurnMeasurement for turn in turns)
    ):
        raise ValueError("sample_count")
    e2e_values: list[float] = []
    prefill_rates: list[float] = []
    decode_rates: list[float] = []
    for turn in turns:
        if (
            not _finite_nonnegative_real(turn.ttft_ms)
            or not _finite_nonnegative_real(turn.e2e_ms)
            or float(turn.ttft_ms) > float(turn.e2e_ms)
            or type(turn.timings) is not dict
        ):
            raise BenchRefusal("malformed_response")
        prefill = turn.timings.get("prompt_per_second")
        decode = turn.timings.get("predicted_per_second")
        if not _finite_nonnegative_real(prefill) or not _finite_nonnegative_real(decode):
            raise BenchRefusal("malformed_response")
        e2e_values.append(float(turn.e2e_ms))
        prefill_rates.append(float(prefill))
        decode_rates.append(float(decode))
    e2e_values.sort()
    p95_index = math.ceil(0.95 * len(e2e_values)) - 1
    return {
        "seven_turn_max_ms": max(e2e_values),
        "p95_e2e_ms": e2e_values[p95_index],
        "median_decode_tps": float(statistics.median(decode_rates)),
        "median_prefill_tps": float(statistics.median(prefill_rates)),
    }


class _LiteralLoopbackHTTPConnection(http.client.HTTPConnection):
    """HTTP/1.1 connection whose address path cannot invoke name resolution."""

    def connect(self) -> None:
        if self.host != "127.0.0.1" or self._tunnel_host is not None:
            raise OSError("loopback transport invariant")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            if self.source_address:
                sock.bind(self.source_address)
            sock.connect(("127.0.0.1", self.port))
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except BaseException:
            sock.close()
            raise
        self.sock = sock


_ConnectionFactory = Callable[[str, int, float], object]
_CLIENT_GUARD = object()
_READ_CHUNK_BYTES = 64 * 1024


def _monotonic(clock: Clock) -> float:
    try:
        value = clock.monotonic()
    except Exception:
        raise BenchRefusal("provider_uncertain") from None
    if not _finite_nonnegative_real(value):
        raise BenchRefusal("provider_uncertain")
    return float(value)


def _remaining_seconds(clock: Clock, deadline: float) -> float:
    remaining = deadline - _monotonic(clock)
    if remaining <= 0:
        raise BenchRefusal("http_timeout")
    return remaining


def _set_connection_timeout(connection: object, timeout: float) -> None:
    sock = getattr(connection, "sock", None)
    if sock is None or not callable(getattr(sock, "settimeout", None)):
        raise BenchRefusal("malformed_response")
    try:
        sock.settimeout(timeout)
    except (OSError, TypeError, ValueError):
        raise BenchRefusal("malformed_response") from None


def _set_read_timeout(connection: object, response: object, timeout: float) -> None:
    """Set the socket deadline after HTTP/1.0 may detach it from the connection."""

    sock = getattr(connection, "sock", None)
    if sock is None:
        fp = getattr(response, "fp", None)
        raw = getattr(fp, "raw", None)
        sock = getattr(raw, "_sock", None)
    if sock is None or not callable(getattr(sock, "settimeout", None)):
        raise BenchRefusal("malformed_response")
    try:
        sock.settimeout(timeout)
    except (OSError, TypeError, ValueError):
        raise BenchRefusal("malformed_response") from None


def _response_is_closed(response: object) -> bool:
    isclosed = getattr(response, "isclosed", None)
    if not callable(isclosed):
        return False
    try:
        return isclosed() is True
    except (OSError, http.client.HTTPException):
        raise BenchRefusal("malformed_response") from None


def _validate_response_framing(
    response: object,
    *,
    expected_content_type: str,
) -> int | None:
    """Reject ambiguous HTTP framing before consuming any response bytes."""

    getheaders = getattr(response, "getheaders", None)
    if not callable(getheaders):
        raise BenchRefusal("malformed_response")
    try:
        raw_headers = getheaders()
    except (OSError, http.client.HTTPException):
        raise BenchRefusal("malformed_response") from None
    if type(raw_headers) is not list:
        raise BenchRefusal("malformed_response")
    headers: dict[str, list[str]] = {}
    for row in raw_headers:
        if (
            type(row) is not tuple
            or len(row) != 2
            or type(row[0]) is not str
            or type(row[1]) is not str
        ):
            raise BenchRefusal("malformed_response")
        headers.setdefault(row[0].lower(), []).append(row[1])

    content_types = headers.get("content-type", [])
    if len(content_types) != 1:
        raise BenchRefusal("malformed_response")
    observed_content_type = content_types[0].split(";", 1)[0].strip().lower()
    if observed_content_type != expected_content_type:
        raise BenchRefusal("malformed_response")

    content_lengths = headers.get("content-length", [])
    transfer_encodings = headers.get("transfer-encoding", [])
    if (
        len(content_lengths) > 1
        or len(transfer_encodings) > 1
        or (content_lengths and transfer_encodings)
    ):
        raise BenchRefusal("malformed_response")
    if transfer_encodings and transfer_encodings[0].strip().lower() != "chunked":
        raise BenchRefusal("malformed_response")
    if content_lengths:
        rendered_length = content_lengths[0].strip()
        if not rendered_length.isascii() or not rendered_length.isdecimal():
            raise BenchRefusal("malformed_response")
        normalized_length = rendered_length.lstrip("0") or "0"
        rendered_cap = str(RESPONSE_BYTE_CAP)
        if len(normalized_length) > len(rendered_cap) or (
            len(normalized_length) == len(rendered_cap)
            and normalized_length > rendered_cap
        ):
            raise BenchRefusal("response_too_large")
        declared_length = int(normalized_length)
        return declared_length
    elif not transfer_encodings and getattr(response, "will_close", None) is not True:
        raise BenchRefusal("malformed_response")
    return None


def _close_http_resources(*resources: object | None) -> None:
    """Close every resource; ordinary close errors are non-authoritative."""

    pending_base_exception: BaseException | None = None
    for resource in resources:
        close = getattr(resource, "close", None)
        if not callable(close):
            continue
        try:
            close()
        except BaseException as exc:
            if not isinstance(exc, Exception) and pending_base_exception is None:
                pending_base_exception = exc
    if pending_base_exception is not None:
        raise pending_base_exception


def _validate_http_inputs(port: int, timeout_ms: int) -> None:
    if type(port) is not int or not 0 < port <= 65_535:
        raise ValueError("port")
    if type(timeout_ms) is not int or timeout_ms <= 0:
        raise ValueError("request_timeout_ms")


def _open_connection(
    port: int,
    *,
    clock: Clock,
    deadline: float,
    connection_factory: _ConnectionFactory,
) -> object:
    connection: object | None = None
    admitted = False
    try:
        connection = connection_factory(
            "127.0.0.1", port, _remaining_seconds(clock, deadline)
        )
        connect = getattr(connection, "connect", None)
        if not callable(connect):
            raise BenchRefusal("malformed_response")
        connect()
        _set_connection_timeout(connection, _remaining_seconds(clock, deadline))
        admitted = True
        return connection
    except BenchRefusal:
        raise
    except (TimeoutError, socket.timeout):
        raise BenchRefusal("http_timeout") from None
    except (OSError, http.client.HTTPException):
        raise BenchRefusal("malformed_response") from None
    finally:
        if not admitted:
            _close_http_resources(connection)


def _next_sse_event(buffer: bytes) -> tuple[bytes | None, bytes]:
    lf_index = buffer.find(b"\n\n")
    crlf_index = buffer.find(b"\r\n\r\n")
    candidates = [
        (index, separator)
        for index, separator in ((lf_index, b"\n\n"), (crlf_index, b"\r\n\r\n"))
        if index >= 0
    ]
    if not candidates:
        return None, buffer
    index, separator = min(candidates, key=lambda item: item[0])
    return buffer[:index], buffer[index + len(separator) :]


def _sse_payload(event: bytes) -> bytes | None:
    data_lines: list[bytes] = []
    for raw_line in event.replace(b"\r\n", b"\n").split(b"\n"):
        if not raw_line or raw_line.startswith(b":"):
            continue
        if raw_line.startswith(b"data:"):
            data_lines.append(raw_line[5:].lstrip(b" "))
            continue
        raise BenchRefusal("malformed_response")
    if not data_lines:
        return None
    return b"\n".join(data_lines)


def _json_object_without_duplicates(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate_key")
        document[key] = value
    return document


def _finite_json_float(rendered: str) -> float:
    value = float(rendered)
    if not math.isfinite(value):
        raise ValueError("nonfinite")
    return value


def _reject_json_constant(_rendered: str) -> object:
    raise ValueError("nonfinite")


def _decode_protocol_json(payload: bytes | bytearray) -> object:
    """Decode bounded wire JSON without ambiguity or non-finite numbers."""

    try:
        document = json.loads(
            payload,
            object_pairs_hook=_json_object_without_duplicates,
            parse_float=_finite_json_float,
            parse_constant=_reject_json_constant,
        )
        pending = [document]
        while pending:
            value = pending.pop()
            if type(value) is str:
                value.encode("utf-8")
            elif type(value) is dict:
                pending.extend(value.keys())
                pending.extend(value.values())
            elif type(value) is list:
                pending.extend(value)
        return document
    except (
        UnicodeError,
        json.JSONDecodeError,
        RecursionError,
        TypeError,
        ValueError,
    ):
        raise BenchRefusal("malformed_response") from None


def stream_completion(
    port: int,
    prompt: str,
    *,
    clock: Clock,
    request_timeout_ms: int = REQUEST_TIMEOUT_MS,
    connection_factory: _ConnectionFactory = _LiteralLoopbackHTTPConnection,
) -> TurnMeasurement:
    """Measure one native llama.cpp SSE completion against literal loopback."""

    _validate_http_inputs(port, request_timeout_ms)
    if type(prompt) is not str:
        raise ValueError("prompt")
    body = json.dumps(
        {"prompt": prompt, "stream": True},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    deadline = _monotonic(clock) + request_timeout_ms / 1000
    connection: object | None = None
    response: object | None = None
    try:
        connection = _open_connection(
            port,
            clock=clock,
            deadline=deadline,
            connection_factory=connection_factory,
        )
        putrequest = getattr(connection, "putrequest", None)
        putheader = getattr(connection, "putheader", None)
        endheaders = getattr(connection, "endheaders", None)
        getresponse = getattr(connection, "getresponse", None)
        if not all(callable(item) for item in (putrequest, putheader, endheaders, getresponse)):
            raise BenchRefusal("malformed_response")
        _set_connection_timeout(connection, _remaining_seconds(clock, deadline))
        putrequest("POST", "/completion", skip_accept_encoding=True)
        putheader("Accept", "text/event-stream")
        putheader("Content-Length", str(len(body)))
        putheader("Content-Type", "application/json")
        _set_connection_timeout(connection, _remaining_seconds(clock, deadline))
        endheaders(body)
        request_written_at = _monotonic(clock)
        _remaining_seconds(clock, deadline)
        _set_connection_timeout(connection, _remaining_seconds(clock, deadline))
        response = getresponse()
        _remaining_seconds(clock, deadline)
        status = getattr(response, "status", None)
        read1 = getattr(response, "read1", None)
        if status != 200 or not callable(read1):
            raise BenchRefusal("malformed_response")
        declared_body_bytes = _validate_response_framing(
            response,
            expected_content_type="text/event-stream",
        )

        total_bytes = 0
        buffer = b""
        content_parts: list[str] = []
        ttft_at: float | None = None
        terminal_at: float | None = None
        terminal: dict[str, object] | None = None
        timings: dict[str, object] | None = None
        while True:
            _remaining_seconds(clock, deadline)
            if _response_is_closed(response):
                if (
                    buffer
                    or terminal is None
                    or ttft_at is None
                    or (
                        declared_body_bytes is not None
                        and total_bytes != declared_body_bytes
                    )
                ):
                    raise BenchRefusal("malformed_response")
                break
            _set_read_timeout(
                connection,
                response,
                _remaining_seconds(clock, deadline),
            )
            try:
                chunk = read1(min(_READ_CHUNK_BYTES, RESPONSE_BYTE_CAP - total_bytes + 1))
            except (TimeoutError, socket.timeout):
                raise BenchRefusal("http_timeout") from None
            except (OSError, http.client.HTTPException):
                raise BenchRefusal("malformed_response") from None
            arrived_at = _monotonic(clock)
            if arrived_at >= deadline:
                raise BenchRefusal("http_timeout")
            if type(chunk) is not bytes:
                raise BenchRefusal("malformed_response")
            if not chunk:
                if (
                    buffer
                    or terminal is None
                    or ttft_at is None
                    or (
                        declared_body_bytes is not None
                        and total_bytes != declared_body_bytes
                    )
                ):
                    raise BenchRefusal("malformed_response")
                break
            total_bytes += len(chunk)
            if total_bytes > RESPONSE_BYTE_CAP:
                raise BenchRefusal("response_too_large")
            buffer += chunk
            while True:
                event, buffer = _next_sse_event(buffer)
                if event is None:
                    break
                if terminal is not None:
                    raise BenchRefusal("malformed_response")
                payload = _sse_payload(event)
                if payload is None:
                    continue
                if payload == b"[DONE]":
                    raise BenchRefusal("malformed_response")
                document = _decode_protocol_json(payload)
                if type(document) is not dict:
                    raise BenchRefusal("malformed_response")
                value = document.get("content")
                if value is not None and type(value) is not str:
                    raise BenchRefusal("malformed_response")
                stop = document.get("stop")
                if type(stop) is not bool:
                    raise BenchRefusal("malformed_response")
                if stop:
                    if (
                        terminal is not None
                        or value != ""
                        or type(document.get("prompt")) is not str
                    ):
                        raise BenchRefusal("malformed_response")
                    candidate = document.get("timings")
                    if type(candidate) is not dict:
                        raise BenchRefusal("malformed_response")
                    terminal = dict(document)
                    timings = dict(candidate)
                    terminal_at = arrived_at
                    continue
                if terminal is not None:
                    raise BenchRefusal("malformed_response")
                if value:
                    content_parts.append(value)
                    if ttft_at is None:
                        ttft_at = arrived_at
        if terminal is None or timings is None or terminal_at is None or ttft_at is None:
            raise BenchRefusal("malformed_response")
        ttft_ms = (ttft_at - request_written_at) * 1000
        e2e_ms = (terminal_at - request_written_at) * 1000
        if ttft_ms < 0 or e2e_ms < 0 or ttft_ms > e2e_ms:
            raise BenchRefusal("malformed_response")
        return TurnMeasurement(
            ttft_ms=float(ttft_ms),
            e2e_ms=float(e2e_ms),
            content="".join(content_parts),
            timings=timings,
            terminal=terminal,
        )
    except BenchRefusal:
        raise
    except (TimeoutError, socket.timeout):
        raise BenchRefusal("http_timeout") from None
    except (OSError, http.client.HTTPException):
        raise BenchRefusal("malformed_response") from None
    finally:
        _close_http_resources(response, connection)


def _json_get(
    port: int,
    path: str,
    *,
    clock: Clock,
    request_timeout_ms: int,
    health_probe: bool,
) -> object | None:
    """Read one capped loopback JSON response without exposing response bytes."""

    _validate_http_inputs(port, request_timeout_ms)
    if path not in {"/health", "/v1/models"}:
        raise ValueError("path")
    deadline = _monotonic(clock) + request_timeout_ms / 1000
    connection: object | None = None
    response: object | None = None
    try:
        try:
            connection = _open_connection(
                port,
                clock=clock,
                deadline=deadline,
                connection_factory=_LiteralLoopbackHTTPConnection,
            )
        except BenchRefusal as exc:
            if health_probe and exc.code in {"http_timeout", "malformed_response"}:
                return None
            raise
        putrequest = getattr(connection, "putrequest", None)
        putheader = getattr(connection, "putheader", None)
        endheaders = getattr(connection, "endheaders", None)
        getresponse = getattr(connection, "getresponse", None)
        if not all(callable(item) for item in (putrequest, putheader, endheaders, getresponse)):
            raise BenchRefusal("malformed_response")
        _set_connection_timeout(connection, _remaining_seconds(clock, deadline))
        putrequest("GET", path, skip_accept_encoding=True)
        putheader("Accept", "application/json")
        _set_connection_timeout(connection, _remaining_seconds(clock, deadline))
        endheaders()
        _set_connection_timeout(connection, _remaining_seconds(clock, deadline))
        response = getresponse()
        _remaining_seconds(clock, deadline)
        status = getattr(response, "status", None)
        unready = health_probe and status == 503
        if status != 200 and not unready:
            raise BenchRefusal("malformed_response")
        read1 = getattr(response, "read1", None)
        if not callable(read1):
            raise BenchRefusal("malformed_response")
        declared_body_bytes = _validate_response_framing(
            response,
            expected_content_type="application/json",
        )
        body = bytearray()
        while True:
            _remaining_seconds(clock, deadline)
            if _response_is_closed(response):
                if (
                    declared_body_bytes is not None
                    and len(body) != declared_body_bytes
                ):
                    raise BenchRefusal("malformed_response")
                break
            _set_read_timeout(
                connection,
                response,
                _remaining_seconds(clock, deadline),
            )
            chunk = read1(min(_READ_CHUNK_BYTES, RESPONSE_BYTE_CAP - len(body) + 1))
            arrived_at = _monotonic(clock)
            if arrived_at >= deadline:
                raise BenchRefusal("http_timeout")
            if type(chunk) is not bytes:
                raise BenchRefusal("malformed_response")
            if not chunk:
                if (
                    declared_body_bytes is not None
                    and len(body) != declared_body_bytes
                ):
                    raise BenchRefusal("malformed_response")
                break
            body.extend(chunk)
            if len(body) > RESPONSE_BYTE_CAP:
                raise BenchRefusal("response_too_large")
        document = _decode_protocol_json(body)
        _remaining_seconds(clock, deadline)
        if unready:
            if type(document) is not dict or set(document) != {"error"}:
                raise BenchRefusal("malformed_response")
            error = document["error"]
            if (
                type(error) is not dict
                or set(error) != {"code", "message", "type"}
                or type(error["code"]) is not int
                or error["code"] != 503
                or type(error["message"]) is not str
                or error["message"] != "Loading model"
                or type(error["type"]) is not str
                or error["type"] != "unavailable_error"
            ):
                raise BenchRefusal("malformed_response")
            return None
        return document
    except BenchRefusal:
        raise
    except (TimeoutError, socket.timeout):
        if health_probe:
            return None
        raise BenchRefusal("http_timeout") from None
    except OSError:
        if health_probe:
            return None
        raise BenchRefusal("malformed_response") from None
    except http.client.HTTPException:
        raise BenchRefusal("malformed_response") from None
    finally:
        _close_http_resources(response, connection)


def _health_request(
    port: int,
    *,
    clock: Clock,
    request_timeout_ms: int,
) -> bool:
    document = _json_get(
        port,
        "/health",
        clock=clock,
        request_timeout_ms=request_timeout_ms,
        health_probe=True,
    )
    if document is None:
        return False
    if type(document) is not dict or document != {"status": "ok"}:
        raise BenchRefusal("malformed_response")
    return True


def _models_request(
    port: int,
    *,
    clock: Clock,
    request_timeout_ms: int,
) -> list[str]:
    document = _json_get(
        port,
        "/v1/models",
        clock=clock,
        request_timeout_ms=request_timeout_ms,
        health_probe=False,
    )
    if type(document) is not dict or "data" not in document:
        raise BenchRefusal("malformed_response")
    rows = document["data"]
    if type(rows) is not list:
        raise BenchRefusal("malformed_response")
    model_ids: list[str] = []
    for row in rows:
        if type(row) is not dict or type(row.get("id")) is not str or not row["id"]:
            raise BenchRefusal("malformed_response")
        model_ids.append(row["id"])
    return model_ids


@dataclass(frozen=True, slots=True, init=False)
class LoopbackServerClient:
    """Sealed provider client using only the literal-loopback transport."""

    tier: str
    clock: Clock
    host: str
    request_timeout_ms: int

    def __init__(
        self,
        *,
        tier: str,
        clock: Clock,
        host: str,
        request_timeout_ms: int,
        _guard: object | None = None,
    ) -> None:
        if _guard is not _CLIENT_GUARD:
            raise TypeError("sealed_client_factory_required")
        if host != "127.0.0.1":
            raise ValueError("loopback_literal_required")
        if tier not in {"production", "rehearsal"} or getattr(clock, "tier", None) != tier:
            raise ValueError("client_tier")
        expected_clock = SystemClock if tier == "production" else RehearsalClock
        if type(clock) is not expected_clock:
            raise ValueError("transport_clock_required")
        _validate_http_inputs(1, request_timeout_ms)
        object.__setattr__(self, "tier", tier)
        object.__setattr__(self, "clock", clock)
        object.__setattr__(self, "host", host)
        object.__setattr__(self, "request_timeout_ms", request_timeout_ms)

    @classmethod
    def production(
        cls,
        clock: Clock,
        *,
        host: str = "127.0.0.1",
        request_timeout_ms: int = REQUEST_TIMEOUT_MS,
    ) -> "LoopbackServerClient":
        return cls(
            tier="production",
            clock=clock,
            host=host,
            request_timeout_ms=request_timeout_ms,
            _guard=_CLIENT_GUARD,
        )

    @classmethod
    def rehearsal(
        cls,
        clock: Clock,
        *,
        host: str = "127.0.0.1",
        request_timeout_ms: int = REQUEST_TIMEOUT_MS,
    ) -> "LoopbackServerClient":
        return cls(
            tier="rehearsal",
            clock=clock,
            host=host,
            request_timeout_ms=request_timeout_ms,
            _guard=_CLIENT_GUARD,
        )

    def health(self, port: int) -> bool:
        return _health_request(
            port,
            clock=self.clock,
            request_timeout_ms=self.request_timeout_ms,
        )

    def models(self, port: int) -> list[str]:
        return _models_request(
            port,
            clock=self.clock,
            request_timeout_ms=self.request_timeout_ms,
        )

    def stream(self, port: int, prompt: str) -> TurnMeasurement:
        return stream_completion(
            port,
            prompt,
            clock=self.clock,
            request_timeout_ms=self.request_timeout_ms,
        )


class ArtifactPolicy(Protocol):
    tier: str

    def encode(self, kind: str, document: dict[str, object]) -> bytes: ...

    def artifact_dir(self, kind: str) -> str: ...


class JournalFactory(Protocol):
    tier: str

    def create(
        self,
        phase: str,
        *,
        journal_dir: str,
        timestamp: str,
        root: Path,
    ) -> PhaseJournal: ...


@dataclass(frozen=True, init=False)
class ProductionJournalFactory:
    tier: str = "production"

    def create(
        self,
        phase: str,
        *,
        journal_dir: str,
        timestamp: str,
        root: Path,
    ) -> PhaseJournal:
        expected_dir = ProductionArtifactPolicy().artifact_dir("journal")
        if type(journal_dir) is not str or journal_dir != expected_dir:
            raise BenchRefusal("tier_mismatch")
        return PhaseJournal(
            phase,
            journal_dir=journal_dir,
            timestamp=timestamp,
            root=root,
        )


@dataclass(frozen=True, init=False)
class RehearsalJournalFactory:
    tier: str = "rehearsal"

    def create(
        self,
        phase: str,
        *,
        journal_dir: str,
        timestamp: str,
        root: Path,
    ) -> PhaseJournal:
        expected_dir = RehearsalArtifactPolicy().artifact_dir("journal")
        if type(journal_dir) is not str or journal_dir != expected_dir:
            raise BenchRefusal("tier_mismatch")
        return PhaseJournal(
            phase,
            journal_dir=journal_dir,
            timestamp=timestamp,
            root=root,
        )


_ARTIFACT_SCHEMAS = {
    "packet": PHASE_PACKET_SCHEMA,
    "refusal": REFUSAL_SCHEMA,
    "command_admission": COMMAND_ADMISSION_SCHEMA,
    "command_completion": COMMAND_COMPLETION_SCHEMA,
    "receipt": ASSEMBLE_RECEIPT_SCHEMA,
    "consumption_receipt": CONSUMPTION_RECEIPT_SCHEMA,
    "containment_snapshot": CONTAINMENT_SNAPSHOT_SCHEMA,
    "identity_document": RUNTIME_IDENTITY_SCHEMA,
    "turn_artifact": TURN_ARTIFACT_SCHEMA,
    "turn_manifest": TURN_MANIFEST_SCHEMA,
    "static_preflight": STATIC_PREFLIGHT_SCHEMA,
    "window_authorization": WINDOW_AUTHORIZATION_SCHEMA,
    "continuation": CONTINUATION_SCHEMA,
}
_ARTIFACT_DIRECTORIES = {
    "packet": "packets",
    "refusal": "refusals",
    "receipt": "receipts",
    "consumption_receipt": "receipts",
    "containment_snapshot": "containment",
    "identity_document": "identity",
    "turn_artifact": "turns",
    "turn_manifest": "turns",
    "static_preflight": "receipts",
    "command_completion": "",
    "window_authorization": "authorizations",
    "continuation": "authorizations",
    "journal": "journals",
}


def _canonical_json(document: Mapping[str, object]) -> bytes:
    try:
        return (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (RecursionError, TypeError, ValueError):
        raise ValueError("artifact_document_invalid") from None


def _validate_artifact_value(value: object, *, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("artifact_document_invalid")
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("artifact_document_invalid")
        return
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("artifact_document_invalid")
        for nested in value.values():
            _validate_artifact_value(nested, depth=depth + 1)
        return
    if type(value) in {list, tuple}:
        for nested in value:
            _validate_artifact_value(nested, depth=depth + 1)
        return
    raise ValueError("artifact_document_invalid")


def _production_artifact(kind: str, document: Mapping[str, object]) -> dict[str, object]:
    if kind not in _ARTIFACT_SCHEMAS or not isinstance(document, Mapping):
        raise ValueError("artifact_kind_invalid")
    try:
        fields = dict(document)
    except Exception:
        raise ValueError("artifact_document_invalid") from None
    if any(type(key) is not str for key in fields):
        raise ValueError("artifact_document_invalid")
    _validate_artifact_value(fields)
    binding = fields.pop("binding_sha256", None)
    if kind in {"turn_artifact", "command_admission"}:
        binding = None
    elif binding is not None and (
        type(binding) is not str or re.fullmatch(r"[0-9a-f]{64}", binding) is None
    ):
        raise ValueError("artifact_document_invalid")
    fields.pop("schema", None)
    return {
        "schema": _ARTIFACT_SCHEMAS[kind],
        "binding_sha256": binding,
        "fields": fields,
    }


@dataclass(frozen=True, init=False)
class ProductionArtifactPolicy:
    tier: str = "production"

    def encode(self, kind: str, document: dict[str, object]) -> bytes:
        return _canonical_json(_production_artifact(kind, document))

    def artifact_dir(self, kind: str) -> str:
        try:
            return _ARTIFACT_DIRECTORIES[kind]
        except KeyError:
            raise ValueError("artifact_kind_invalid") from None


@dataclass(frozen=True, init=False)
class RehearsalArtifactPolicy:
    tier: str = "rehearsal"

    def encode(self, kind: str, document: dict[str, object]) -> bytes:
        production = _production_artifact(kind, document)
        payload = {
            "kind": kind,
            "binding_sha256": production["binding_sha256"],
            "fields": production["fields"],
        }
        return _canonical_json(
            {
                "rehearsal_schema": REHEARSAL_PACKET_SCHEMA,
                "tier": self.tier,
                "payload": payload,
            }
        )

    def artifact_dir(self, kind: str) -> str:
        try:
            directory = _ARTIFACT_DIRECTORIES[kind]
        except KeyError:
            raise ValueError("artifact_kind_invalid") from None
        return f"rehearsal/{directory}"


def _window_authorization_doc(auth: "WindowAuthorization") -> cm.WindowAuthorizationDoc:
    if (
        type(auth.window_id) is not str
        or type(auth.phases) is not tuple
        or any(type(phase) is not str for phase in auth.phases)
        or type(auth.boot_id) is not str
        or type(auth.nonce) is not str
        or type(auth.issued_at) is not str
        or type(auth.expires_at) is not str
        or type(auth.owner) is not str
    ):
        raise ValueError("authorization_fields_invalid")
    return cm.WindowAuthorizationDoc(
        window_id=auth.window_id,
        phases=auth.phases,
        boot_id=auth.boot_id,
        nonce=auth.nonce,
        issued_at=auth.issued_at,
        expires_at=auth.expires_at,
        owner=auth.owner,
    )


def _continuation_doc(auth: "Continuation") -> cm.ContinuationDoc:
    if (
        type(auth.window_id) is not str
        or type(auth.phases) is not tuple
        or any(type(phase) is not str for phase in auth.phases)
        or type(auth.boot_id) is not str
        or type(auth.nonce) is not str
        or type(auth.issued_at) is not str
        or type(auth.expires_at) is not str
        or type(auth.owner) is not str
        or type(auth.parent_vulkan_packet_sha256) is not str
    ):
        raise ValueError("authorization_fields_invalid")
    return cm.ContinuationDoc(
        window_id=auth.window_id,
        phases=auth.phases,
        boot_id=auth.boot_id,
        nonce=auth.nonce,
        issued_at=auth.issued_at,
        expires_at=auth.expires_at,
        owner=auth.owner,
        parent_vulkan_packet_sha256=auth.parent_vulkan_packet_sha256,
    )


@dataclass(frozen=True, slots=True)
class WindowAuthorization:
    window_id: str
    phases: tuple[str, ...]
    boot_id: str
    nonce: str
    issued_at: str
    expires_at: str
    owner: str

    def __post_init__(self) -> None:
        _window_authorization_doc(self)

    @property
    def preimage_sha256(self) -> str:
        return _window_authorization_doc(self).preimage_sha256


@dataclass(frozen=True, slots=True)
class Continuation:
    window_id: str
    phases: tuple[str, ...]
    boot_id: str
    nonce: str
    issued_at: str
    expires_at: str
    owner: str
    parent_vulkan_packet_sha256: str

    def __post_init__(self) -> None:
        _continuation_doc(self)

    @property
    def preimage_sha256(self) -> str:
        return _continuation_doc(self).preimage_sha256


@dataclass(frozen=True, slots=True)
class ConsumedAuthority:
    preimage_sha256: str
    consumption_receipt_sha256: str
    receipt: dict[str, object]


_WINDOW_AUTHORIZATION_FIELDS = frozenset(
    {"window_id", "phases", "boot_id", "nonce", "issued_at", "expires_at", "owner"}
)
_CONTINUATION_FIELDS = frozenset(
    {*_WINDOW_AUTHORIZATION_FIELDS, "parent_vulkan_packet_sha256"}
)


def _parse_authorization_wrapper(
    data: bytes,
    *,
    schema: str,
    expected_fields: frozenset[str],
) -> tuple[dict[str, object], str]:
    try:
        if type(data) is not bytes:
            raise ValueError("authorization_bytes_required")
        wrapper = json.loads(
            data,
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        if type(wrapper) is not dict or set(wrapper) != {
            "schema",
            "binding_sha256",
            "fields",
        }:
            raise ValueError("authorization_wrapper")
        if type(wrapper["schema"]) is not str or wrapper["schema"] != schema:
            raise ValueError("authorization_schema")
        if type(wrapper["binding_sha256"]) is not str:
            raise ValueError("authorization_binding")
        fields = wrapper["fields"]
        if type(fields) is not dict or set(fields) != expected_fields:
            raise ValueError("authorization_fields")
        phases = fields["phases"]
        if type(phases) is not list or any(type(phase) is not str for phase in phases):
            raise ValueError("authorization_phases")
        return dict(fields), wrapper["binding_sha256"]
    except (RecursionError, TypeError, UnicodeError, ValueError):
        raise BenchRefusal("authorization_malformed") from None


def parse_window_authorization(data: bytes) -> WindowAuthorization:
    fields, binding = _parse_authorization_wrapper(
        data,
        schema=WINDOW_AUTHORIZATION_SCHEMA,
        expected_fields=_WINDOW_AUTHORIZATION_FIELDS,
    )
    try:
        authorization = WindowAuthorization(
            **{**fields, "phases": tuple(fields["phases"])}  # type: ignore[arg-type]
        )
        if binding != authorization.preimage_sha256:
            raise ValueError("authorization_binding")
        return authorization
    except (TypeError, ValueError):
        raise BenchRefusal("authorization_malformed") from None


def parse_continuation(data: bytes) -> Continuation:
    fields, binding = _parse_authorization_wrapper(
        data,
        schema=CONTINUATION_SCHEMA,
        expected_fields=_CONTINUATION_FIELDS,
    )
    try:
        continuation = Continuation(
            **{**fields, "phases": tuple(fields["phases"])}  # type: ignore[arg-type]
        )
        if binding != continuation.preimage_sha256:
            raise ValueError("authorization_binding")
        return continuation
    except (TypeError, ValueError):
        raise BenchRefusal("authorization_malformed") from None


def _validated_clock_timestamp(timestamp: str) -> str:
    try:
        if type(timestamp) is not str:
            raise ValueError("timestamp")
        cm._validate_utc_z_timestamp(timestamp)
        return timestamp
    except (TypeError, ValueError):
        raise BenchRefusal("provider_uncertain") from None


def _validated_authority(
    auth: object,
    *,
    phase: str,
    boot_id: str,
    expected_window_id: str,
    clock: Clock,
    parent_window: WindowAuthorization | None,
    parent_packet: cm.PhasePacket | None,
    parent_completion: ParentCompletionEvidence | None,
) -> tuple[
    WindowAuthorization | Continuation,
    cm.WindowAuthorizationDoc | cm.ContinuationDoc,
    str,
]:
    if phase == "vulkan_baseline":
        if type(auth) is not WindowAuthorization:
            raise BenchRefusal("authorization_scope_mismatch")
        authority = auth
        scorer_authority: cm.WindowAuthorizationDoc | cm.ContinuationDoc = (
            _window_authorization_doc(authority)
        )
    elif phase == "cuda_candidate":
        if type(auth) is not Continuation:
            raise BenchRefusal("authorization_scope_mismatch")
        authority = auth
        scorer_authority = _continuation_doc(authority)
    else:
        raise BenchRefusal("authorization_scope_mismatch")
    if phase not in authority.phases:
        raise BenchRefusal("authorization_scope_mismatch")
    if (
        type(expected_window_id) is not str
        or authority.window_id != expected_window_id
    ):
        raise BenchRefusal("authorization_scope_mismatch")
    if type(boot_id) is not str or authority.boot_id != boot_id:
        raise BenchRefusal("authorization_boot_mismatch")

    timestamp = _validated_clock_timestamp(clock.now_utc())
    if cm._compare_utc_z(timestamp, authority.issued_at) < 0:
        raise BenchRefusal("authorization_not_yet_valid")
    if cm._compare_utc_z(timestamp, authority.expires_at) >= 0:
        raise BenchRefusal("authorization_expired")

    if type(authority) is Continuation:
        if parent_window is None or parent_packet is None:
            raise BenchRefusal("continuation_missing")
        if type(parent_window) is not WindowAuthorization:
            raise BenchRefusal("authorization_scope_mismatch")
        if not isinstance(parent_packet, cm.PhasePacket):
            raise BenchRefusal("continuation_parent_mismatch")
        if parent_packet.phase != "vulkan_baseline" or parent_packet.outcome != "completed":
            raise BenchRefusal("continuation_parent_mismatch")
        try:
            parent_binding = parent_packet.binding_sha256
        except (AttributeError, TypeError, ValueError):
            raise BenchRefusal("continuation_parent_mismatch") from None
        if parent_binding != authority.parent_vulkan_packet_sha256:
            raise BenchRefusal("continuation_parent_mismatch")
        if (
            parent_packet.window_id != authority.window_id
            or parent_packet.boot_id != authority.boot_id
        ):
            raise BenchRefusal("authorization_scope_mismatch")
        if (
            parent_window.owner != authority.owner
            or parent_window.window_id != authority.window_id
            or parent_window.boot_id != authority.boot_id
        ):
            raise BenchRefusal("authorization_scope_mismatch")
        if (
            parent_window.preimage_sha256
            != parent_packet.authorization_preimage_sha256
        ):
            raise BenchRefusal("continuation_parent_mismatch")
        if type(parent_completion) is not ParentCompletionEvidence:
            raise BenchRefusal("continuation_parent_mismatch")
        try:
            verified_parent_completion = ParentCompletionEvidence(
                packet=parent_completion.packet,
                packet_ref=parent_completion.packet_ref,
                packet_doc=parent_completion.packet_doc,
                admission=parent_completion.admission,
                completion_doc=parent_completion.completion_doc,
            )
        except BenchRefusal:
            raise BenchRefusal("continuation_parent_mismatch") from None
        if verified_parent_completion.packet != parent_packet:
            raise BenchRefusal("continuation_parent_mismatch")
        completion = verified_parent_completion.completion_doc.obj
        if (
            type(completion) is not cm.CommandCompletionDoc
            or cm._compare_utc_z(
                completion.timestamp,
                authority.issued_at,
            )
            > 0
            or cm._compare_utc_z(
                completion.timestamp,
                timestamp,
            )
            > 0
        ):
            raise BenchRefusal("continuation_parent_mismatch")
        if cm._compare_utc_z(timestamp, parent_window.expires_at) >= 0:
            raise BenchRefusal("authorization_expired")

    return authority, scorer_authority, timestamp


def validate_authorization(
    auth: object,
    *,
    phase: str,
    boot_id: str,
    expected_window_id: str,
    clock: Clock,
    parent_window: WindowAuthorization | None = None,
    parent_packet: cm.PhasePacket | None = None,
    parent_completion: ParentCompletionEvidence | None = None,
) -> None:
    """Validate the current authority without writing or consuming its nonce."""

    _validated_authority(
        auth,
        phase=phase,
        boot_id=boot_id,
        expected_window_id=expected_window_id,
        clock=clock,
        parent_window=parent_window,
        parent_packet=parent_packet,
        parent_completion=parent_completion,
    )


def _prepare_authorization_consumption(
    auth: object,
    *,
    phase: str,
    boot_id: str,
    expected_window_id: str,
    clock: Clock,
    policy: ArtifactPolicy,
    expected_tier: str,
    parent_window: WindowAuthorization | None,
    parent_packet: cm.PhasePacket | None,
    parent_completion: ParentCompletionEvidence | None,
) -> tuple[ConsumedAuthority, bytes, str]:
    if (
        type(getattr(policy, "tier", None)) is not str
        or policy.tier != expected_tier
        or not callable(getattr(policy, "encode", None))
        or not callable(getattr(policy, "artifact_dir", None))
    ):
        raise BenchRefusal("tier_mismatch")
    authority, scorer_authority, timestamp = _validated_authority(
        auth,
        phase=phase,
        boot_id=boot_id,
        expected_window_id=expected_window_id,
        clock=clock,
        parent_window=parent_window,
        parent_packet=parent_packet,
        parent_completion=parent_completion,
    )

    receipt = cm.ConsumptionReceipt(
        nonce=authority.nonce,
        phase=phase,
        boot_id=boot_id,
        timestamp=timestamp,
    )
    receipt_document: dict[str, object] = {
        "schema": receipt.schema_version,
        "binding_sha256": receipt.binding_sha256,
        "nonce": receipt.nonce,
        "phase": receipt.phase,
        "boot_id": receipt.boot_id,
        "timestamp": receipt.timestamp,
    }
    encoded = policy.encode("consumption_receipt", dict(receipt_document))
    receipt_dir = policy.artifact_dir("consumption_receipt")
    if type(encoded) is not bytes or type(receipt_dir) is not str:
        raise BenchRefusal("tier_mismatch")
    return (
        ConsumedAuthority(
            preimage_sha256=scorer_authority.preimage_sha256,
            consumption_receipt_sha256=receipt.binding_sha256,
            receipt=dict(receipt_document),
        ),
        encoded,
        receipt_dir,
    )


def consume_authorization(
    auth: object,
    *,
    phase: str,
    boot_id: str,
    expected_window_id: str,
    clock: Clock,
    authority_root: Path,
    receipt_root: Path,
    policy: ArtifactPolicy,
    parent_window: WindowAuthorization | None = None,
    parent_packet: cm.PhasePacket | None = None,
    parent_completion: ParentCompletionEvidence | None = None,
) -> ConsumedAuthority:
    consumed, encoded, receipt_dir = _prepare_authorization_consumption(
        auth,
        phase=phase,
        boot_id=boot_id,
        expected_window_id=expected_window_id,
        clock=clock,
        policy=policy,
        expected_tier="production",
        parent_window=parent_window,
        parent_packet=parent_packet,
        parent_completion=parent_completion,
    )
    _require_distinct_roots(authority_root, receipt_root)
    nonce = consumed.receipt["nonce"]
    if type(nonce) is not str:
        raise BenchRefusal("authorization_malformed")
    _validated_authority(
        auth,
        phase=phase,
        boot_id=boot_id,
        expected_window_id=expected_window_id,
        clock=clock,
        parent_window=parent_window,
        parent_packet=parent_packet,
        parent_completion=parent_completion,
    )
    _create_consumption_marker(nonce, root=authority_root)
    write_private_file(
        f"{receipt_dir}/consumption-{nonce}.json",
        encoded,
        root=receipt_root,
    )
    return consumed


@dataclass(frozen=True, slots=True)
class RealAuthorizationGate:
    tier = "production"
    policy: ArtifactPolicy

    def __post_init__(self) -> None:
        policy = self.policy
        if type(getattr(policy, "tier", None)) is not str or policy.tier != self.tier:
            raise BenchRefusal("tier_mismatch")

    def validate(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        expected_window_id: str,
        parent_window: WindowAuthorization | None,
        parent_packet: cm.PhasePacket | None,
        parent_completion: ParentCompletionEvidence | None = None,
        clock: Clock,
    ) -> None:
        validate_authorization(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
            clock=clock,
        )

    def consume(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        expected_window_id: str,
        parent_window: WindowAuthorization | None,
        parent_packet: cm.PhasePacket | None,
        parent_completion: ParentCompletionEvidence | None = None,
        authority_root: Path,
        receipt_root: Path,
        clock: Clock,
    ) -> ConsumedAuthority:
        self.validate(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
            clock=clock,
        )
        return consume_authorization(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
            authority_root=authority_root,
            receipt_root=receipt_root,
            clock=clock,
            policy=self.policy,
        )


@dataclass(frozen=True, slots=True)
class RehearsalAuthorizationGate:
    tier = "rehearsal"
    policy: ArtifactPolicy

    def __post_init__(self) -> None:
        policy = self.policy
        if type(getattr(policy, "tier", None)) is not str or policy.tier != self.tier:
            raise BenchRefusal("tier_mismatch")

    def validate(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        expected_window_id: str,
        parent_window: WindowAuthorization | None,
        parent_packet: cm.PhasePacket | None,
        parent_completion: ParentCompletionEvidence | None = None,
        clock: Clock,
    ) -> None:
        validate_authorization(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
            clock=clock,
        )

    def consume(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        expected_window_id: str,
        parent_window: WindowAuthorization | None,
        parent_packet: cm.PhasePacket | None,
        parent_completion: ParentCompletionEvidence | None = None,
        authority_root: Path,
        receipt_root: Path,
        clock: Clock,
    ) -> ConsumedAuthority:
        self.validate(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
            clock=clock,
        )
        consumed, encoded, receipt_dir = _prepare_authorization_consumption(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            clock=clock,
            policy=self.policy,
            expected_tier=self.tier,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
        )
        _require_distinct_roots(authority_root, receipt_root)
        _validated_authority(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            clock=clock,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
        )
        if tuple(receipt_dir.split("/", 1))[:1] != ("rehearsal",):
            raise BenchRefusal("tier_mismatch")
        nonce = consumed.receipt["nonce"]
        if type(nonce) is not str:
            raise BenchRefusal("authorization_malformed")
        sequence = next(_AUTHORIZATION_RECEIPT_SEQUENCE)
        receipt_id = secrets.token_hex(16)
        write_private_file(
            f"{receipt_dir}/consumption-{nonce}-{sequence:06d}-{receipt_id}.json",
            encoded,
            root=receipt_root,
        )
        return consumed


@dataclass(frozen=True, slots=True)
class _TestOnlySingleUseAuthorizationGate:
    """In-memory anti-replay gate reachable only through the private test tier."""

    policy: ArtifactPolicy
    tier: str = field(default="rehearsal", init=False)
    _consumed: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.policy) is not RehearsalArtifactPolicy:
            raise BenchRefusal("tier_mismatch")

    def validate(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        expected_window_id: str,
        parent_window: WindowAuthorization | None,
        parent_packet: cm.PhasePacket | None,
        parent_completion: ParentCompletionEvidence | None = None,
        clock: Clock,
    ) -> None:
        validate_authorization(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
            clock=clock,
        )

    def consume(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        expected_window_id: str,
        parent_window: WindowAuthorization | None,
        parent_packet: cm.PhasePacket | None,
        parent_completion: ParentCompletionEvidence | None = None,
        authority_root: Path,
        receipt_root: Path,
        clock: Clock,
    ) -> ConsumedAuthority:
        del authority_root, receipt_root
        self.validate(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
            clock=clock,
        )
        expected_type = WindowAuthorization if phase == "vulkan_baseline" else Continuation
        if type(authorization) is not expected_type:
            raise BenchRefusal("authorization_malformed")
        if authorization.nonce in self._consumed:
            raise BenchRefusal("authorization_consumed")
        consumed, _encoded, _receipt_dir = _prepare_authorization_consumption(
            authorization,
            phase=phase,
            boot_id=boot_id,
            expected_window_id=expected_window_id,
            clock=clock,
            policy=self.policy,
            expected_tier=self.tier,
            parent_window=parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
        )
        self._consumed.add(authorization.nonce)
        return consumed


def _require_distinct_roots(authority_root: Path, receipt_root: Path) -> None:
    try:
        authority_path = os.fspath(authority_root)
        receipt_path = os.fspath(receipt_root)
    except TypeError:
        _filesystem_hazard()
    if (
        not os.path.isabs(authority_path)
        or not os.path.isabs(receipt_path)
        or os.path.normpath(authority_path) == os.path.normpath(receipt_path)
    ):
        _filesystem_hazard()

    authority_fd = _open_root_fd(authority_root)
    try:
        try:
            receipt_fd = os.open(
                receipt_path,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
        except FileNotFoundError:
            return
        except (OSError, TypeError, ValueError):
            _filesystem_hazard()
        try:
            _check_directory_fd(receipt_fd)
            authority = os.fstat(authority_fd)
            receipt = os.fstat(receipt_fd)
            if (authority.st_dev, authority.st_ino) == (
                receipt.st_dev,
                receipt.st_ino,
            ):
                _filesystem_hazard()
        finally:
            os.close(receipt_fd)
    finally:
        os.close(authority_fd)


class _CommandRunner(Protocol):
    def __call__(self, argv: list[str]) -> subprocess.CompletedProcess[str]: ...


def _run_read_only(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=False, capture_output=True, text=True)


class RealServiceStateProvider(_WitnessedProvider):
    tier = "production"

    def __init__(self, *, runner: _CommandRunner = _run_read_only) -> None:
        self._runner = runner
        self._init_provider_witness(synthetic=False)

    def is_active(self, unit: str) -> str:
        self._record_real_call()
        try:
            result = self._runner(systemctl_command("is-active", unit))
        except Exception:
            raise BenchRefusal("provider_uncertain") from None
        if result.returncode not in {0, 3} or type(result.stdout) is not str:
            raise BenchRefusal("provider_uncertain")
        state = result.stdout.strip()
        valid_states = {
            0: {"active", "reloading"},
            3: {"inactive", "failed", "activating", "deactivating", "maintenance"},
        }
        if state not in valid_states[result.returncode]:
            raise BenchRefusal("provider_uncertain")
        return state


class RealPortProbe(_WitnessedProvider):
    tier = "production"

    def __init__(self) -> None:
        self._init_provider_witness(synthetic=False)

    def is_free(
        self,
        port: int,
        *,
        lease: RehearsalPortLease | None = None,
    ) -> bool:
        if (
            type(port) is not int
            or not 0 < port <= 65_535
            or lease is not None
        ):
            raise BenchRefusal("provider_uncertain")
        self._record_real_call()
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError:
            raise BenchRefusal("provider_uncertain") from None
        result: bool | None = None
        failure = False
        try:
            try:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(("127.0.0.1", port))
                result = True
            except OSError as exc:
                if exc.errno == errno.EADDRINUSE:
                    result = False
                else:
                    failure = True
        finally:
            try:
                probe.close()
            except OSError:
                failure = True
        if failure or result is None:
            raise BenchRefusal("provider_uncertain")
        return result


def _command_output(
    runner: _CommandRunner, argv: list[str]
) -> str:
    try:
        result = runner(argv)
    except Exception:
        raise BenchRefusal("provider_uncertain") from None
    if result.returncode != 0 or type(result.stdout) is not str:
        raise BenchRefusal("provider_uncertain")
    return result.stdout


def _parse_compute_inventory(text: str) -> set[tuple[int, str]]:
    rows: set[tuple[int, str]] = set()
    for line in text.splitlines():
        if not line.strip():
            continue
        pieces = line.split(",", 1)
        if len(pieces) != 2:
            raise BenchRefusal("provider_uncertain")
        try:
            pid = int(pieces[0].strip())
        except ValueError:
            raise BenchRefusal("provider_uncertain") from None
        name = os.path.basename(pieces[1].strip())
        if pid <= 0 or not name:
            raise BenchRefusal("provider_uncertain")
        rows.add((pid, name))
    return rows


def _parse_pids_inventory(text: str) -> set[tuple[int, str]]:
    if type(text) is not str:
        raise BenchRefusal("provider_uncertain")
    lines = text.splitlines()
    explicit_none_indexes = [
        index
        for index, line in enumerate(lines)
        if re.fullmatch(r"\s*Processes\s*:\s*None\s*", line) is not None
    ]
    envelope_indexes = [
        index for index, line in enumerate(lines) if line.strip() == "Processes"
    ]
    if explicit_none_indexes:
        if len(explicit_none_indexes) != 1 or envelope_indexes:
            raise BenchRefusal("provider_uncertain")
        if any(
            "Process ID" in line
            or re.search(r"^\s*Name\s*:", line) is not None
            or line.strip() == "No running processes found"
            for line in lines
        ):
            raise BenchRefusal("provider_uncertain")
        return set()
    if len(envelope_indexes) != 1:
        raise BenchRefusal("provider_uncertain")
    body = lines[envelope_indexes[0] + 1 :]
    explicit_empty = sum(line.strip() == "No running processes found" for line in body)
    if explicit_empty > 1:
        raise BenchRefusal("provider_uncertain")
    rows: set[tuple[int, str]] = set()
    current_pid: int | None = None
    for line in body:
        pid_match = re.search(r"^\s*Process ID\s*:\s*(\d+)\s*$", line)
        if "Process ID" in line and pid_match is None:
            raise BenchRefusal("provider_uncertain")
        if pid_match:
            if current_pid is not None:
                raise BenchRefusal("provider_uncertain")
            current_pid = int(pid_match.group(1))
            continue
        name_match = re.search(r"^\s*Name\s*:\s*(.+?)\s*$", line)
        if name_match and current_pid is None:
            raise BenchRefusal("provider_uncertain")
        if name_match:
            assert current_pid is not None
            raw_name = name_match.group(1).strip()
            if raw_name == "N/A":
                raise BenchRefusal("provider_uncertain")
            name = os.path.basename(raw_name)
            if current_pid <= 0 or not name:
                raise BenchRefusal("provider_uncertain")
            rows.add((current_pid, name))
            current_pid = None
    if current_pid is not None:
        raise BenchRefusal("provider_uncertain")
    if explicit_empty:
        if rows:
            raise BenchRefusal("provider_uncertain")
        return set()
    if not rows:
        raise BenchRefusal("provider_uncertain")
    return rows


def _valid_gpu_uuid(value: object) -> bool:
    return (
        type(value) is str
        and re.fullmatch(
            r"GPU-[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
            r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}",
            value,
        )
        is not None
    )


def _parse_memory_sections(text: str) -> dict[str, tuple[int, int]]:
    if type(text) is not str:
        raise BenchRefusal("provider_uncertain")
    headings = list(
        re.finditer(
            r"(?m)^[ \t]*([A-Za-z][A-Za-z0-9 ]*?) Memory Usage[ \t]*$", text
        )
    )
    labels = [match.group(1).strip() for match in headings]
    if labels.count("FB") != 1 or labels.count("BAR1") != 1:
        raise BenchRefusal("provider_uncertain")
    parsed: dict[str, tuple[int, int]] = {}
    for index, heading in enumerate(headings):
        label = heading.group(1).strip()
        if label not in {"FB", "BAR1"}:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[heading.end() : end]
        totals = re.findall(r"(?m)^\s*Total\s*:\s*(\d+)\s+MiB\s*$", body)
        used_values = re.findall(r"(?m)^\s*Used\s*:\s*(\d+)\s+MiB\s*$", body)
        if len(totals) != 1 or len(used_values) != 1:
            raise BenchRefusal("provider_uncertain")
        total, used = int(totals[0]), int(used_values[0])
        if total <= 0 or used < 0 or used > total:
            raise BenchRefusal("provider_uncertain")
        parsed[label] = (total, used)
    return parsed


class RealGpuProvider(_WitnessedProvider):
    tier = "production"

    def __init__(self, *, runner: _CommandRunner = _run_read_only) -> None:
        self._runner = runner
        self._init_provider_witness(synthetic=False)

    def _query(self, argv: list[str]) -> str:
        self._record_real_call()
        return _command_output(self._runner, argv)

    def enumerate_uuids(self) -> list[str]:
        output = self._query(
            ["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader"]
        )
        uuids = [line.strip() for line in output.splitlines() if line.strip()]
        if any(not _valid_gpu_uuid(value) for value in uuids):
            raise BenchRefusal("provider_uncertain")
        return uuids

    def inventory(self, uuid: str) -> list[tuple[int, str]]:
        if not _valid_gpu_uuid(uuid):
            raise BenchRefusal("provider_uncertain")
        compute = self._query(
            [
                "nvidia-smi",
                "-i",
                uuid,
                "--query-compute-apps=pid,process_name",
                "--format=csv,noheader",
            ]
        )
        pids = self._query(["nvidia-smi", "-i", uuid, "-q", "-d", "PIDS"])
        return sorted(_parse_compute_inventory(compute) | _parse_pids_inventory(pids))

    def memory(self, uuid: str) -> tuple[float, int]:
        if not _valid_gpu_uuid(uuid):
            raise BenchRefusal("provider_uncertain")
        output = self._query(["nvidia-smi", "-i", uuid, "-q", "-d", "MEMORY"])
        sections = _parse_memory_sections(output)
        _fb_total, vram_mib = sections["FB"]
        total, used = sections["BAR1"]
        percent = (Decimal(used) * 100 / Decimal(total)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        return float(percent), vram_mib


def _parse_cursor(text: str) -> str:
    matches = re.findall(r"^-- cursor:\s*(\S+)\s*$", text, re.MULTILINE)
    if len(matches) != 1:
        raise BenchRefusal("provider_uncertain")
    return matches[0]


class RealKernelLogProvider(_WitnessedProvider):
    tier = "production"

    def __init__(self, *, runner: _CommandRunner = _run_read_only) -> None:
        self._runner = runner
        self._init_provider_witness(synthetic=False)

    def _query(self, argv: list[str]) -> str:
        self._record_real_call()
        return _command_output(self._runner, argv)

    def cursor(self) -> str:
        output = self._query(
            ["journalctl", "-k", "-n", "0", "--show-cursor", "--no-pager"]
        )
        return _parse_cursor(output)

    def count_signatures(
        self, start_cursor: str, end_cursor: str
    ) -> dict[str, int]:
        if type(start_cursor) is not str or type(end_cursor) is not str:
            raise BenchRefusal("provider_uncertain")
        if not start_cursor or not end_cursor:
            raise BenchRefusal("provider_uncertain")
        if start_cursor == end_cursor:
            return dict.fromkeys(KERNEL_COUNTER_KEYS, 0)
        output = self._query(
            [
                "journalctl",
                "-k",
                f"--after-cursor={start_cursor}",
                "--show-cursor",
                "--no-pager",
            ]
        )
        if _parse_cursor(output) != end_cursor:
            raise BenchRefusal("provider_uncertain")
        counts = dict.fromkeys(KERNEL_COUNTER_KEYS, 0)
        for line in output.splitlines():
            matched_count = 0
            for signature in KERNEL_SIGNATURES:
                occurrences = (
                    len(re.findall(r"NVRM:\s+Xid\b", line))
                    if signature == "Xid"
                    else len(
                        re.findall(
                            rf"(?<![A-Za-z0-9_]){re.escape(signature)}"
                            r"(?![A-Za-z0-9_])",
                            line,
                        )
                    )
                )
                counts[signature] += occurrences
                matched_count += occurrences
            if "NVRM" in line and matched_count == 0:
                counts["unmatched_nvrm"] += 1
        return counts


class RealBackendMapProvider(_WitnessedProvider):
    tier = "production"

    def __init__(self) -> None:
        self._init_provider_witness(synthetic=False)

    def read_maps(self, pid: int) -> str:
        if type(pid) is not int or pid <= 0:
            raise BenchRefusal("provider_uncertain")
        self._record_real_call()
        try:
            return Path(f"/proc/{pid}/maps").read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise BenchRefusal("provider_uncertain") from None


class SystemClock:
    __slots__ = ()
    tier = "production"

    def now_utc(self) -> str:
        return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    def monotonic(self) -> float:
        return time.monotonic()


class RehearsalClock:
    """Advancing local clock for full-fidelity stub transport rehearsal."""

    __slots__ = ()
    tier = "rehearsal"

    def now_utc(self) -> str:
        return datetime.now(UTC).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )

    def monotonic(self) -> float:
        return time.monotonic()


_ContainmentCommandReader = Callable[[list[str]], str]
_ContainmentFileReader = Callable[[Path], bytes]
_ContainmentEnvironReader = Callable[[int], bytes]


def _read_containment_command(argv: list[str]) -> str:
    try:
        result = _run_read_only(argv)
    except Exception:
        raise BenchRefusal("provider_uncertain") from None
    if result.returncode != 0 or type(result.stdout) is not str:
        raise BenchRefusal("provider_uncertain")
    return result.stdout


def _read_containment_file(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        raise BenchRefusal("provider_uncertain") from None


def _read_process_environ(pid: int) -> bytes:
    if type(pid) is not int or pid <= 0:
        raise BenchRefusal("provider_uncertain")
    try:
        return Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        raise BenchRefusal("provider_uncertain") from None


def _parse_systemd_show(text: str) -> dict[str, str | int]:
    if type(text) is not str:
        raise BenchRefusal("provider_uncertain")
    expected = {"ActiveState", "SubState", "UnitFileState", "MainPID"}
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in expected:
            if key in values or not value:
                raise BenchRefusal("provider_uncertain")
            values[key] = value
    if set(values) != expected:
        raise BenchRefusal("provider_uncertain")
    rendered_pid = values.pop("MainPID")
    if not rendered_pid.isascii() or not rendered_pid.isdecimal():
        raise BenchRefusal("provider_uncertain")
    pid = int(rendered_pid)
    return {**values, "MainPID": pid}


def _exact_env_assignment(data: bytes, *, nul_separated: bool) -> str:
    if type(data) is not bytes:
        raise BenchRefusal("provider_uncertain")
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise BenchRefusal("provider_uncertain") from None
    lines = text.split("\0" if nul_separated else "\n")
    prefix = "MAEZ_SCREEN_PERCEPTION="
    matches = [line[len(prefix) :] for line in lines if line.startswith(prefix)]
    if len(matches) != 1 or matches[0] not in {"0", "1"}:
        raise BenchRefusal("containment_violation")
    return matches[0]


class RealContainmentProvider(_WitnessedProvider):
    tier = "production"

    def __init__(
        self,
        *,
        clock: Clock,
        port_probe: PortProbe,
        command_reader: _ContainmentCommandReader = _read_containment_command,
        file_reader: _ContainmentFileReader = _read_containment_file,
        environ_reader: _ContainmentEnvironReader = _read_process_environ,
    ) -> None:
        self.clock = clock
        self.port_probe = port_probe
        self._command_reader = command_reader
        self._file_reader = file_reader
        self._environ_reader = environ_reader
        self._init_provider_witness(synthetic=False)

    def _command(self, argv: list[str]) -> str:
        self._record_real_call()
        try:
            value = self._command_reader(argv)
        except BenchRefusal:
            raise
        except Exception:
            raise BenchRefusal("provider_uncertain") from None
        if type(value) is not str:
            raise BenchRefusal("provider_uncertain")
        return value

    def _file(self, path: Path) -> bytes:
        self._record_real_call()
        try:
            value = self._file_reader(path)
        except BenchRefusal:
            raise
        except Exception:
            raise BenchRefusal("provider_uncertain") from None
        if type(value) is not bytes:
            raise BenchRefusal("provider_uncertain")
        return value

    def capture(self, phase: str, boundary: str) -> cm.ContainmentSnapshot:
        flag_bytes = self._file(SCREEN_FLAG_SOURCE_PATH)
        unit_bytes = self._file(VISION_UNIT_PATH)
        flag_value = _exact_env_assignment(flag_bytes, nul_separated=False)
        vision = _parse_systemd_show(
            self._command(systemctl_command("show", VISION_UNIT))
        )
        maez = _parse_systemd_show(
            self._command(systemctl_command("show", MAEZ_UNIT))
        )
        maez_state = maez["ActiveState"]
        process_flag: str | None = None
        if maez_state == "active":
            pid = maez["MainPID"]
            if type(pid) is not int or pid <= 0:
                raise BenchRefusal("provider_uncertain")
            self._record_real_call()
            try:
                environ = self._environ_reader(pid)
            except BenchRefusal:
                raise
            except Exception:
                raise BenchRefusal("provider_uncertain") from None
            process_flag = _exact_env_assignment(environ, nul_separated=True)
            second = _parse_systemd_show(
                self._command(systemctl_command("show", MAEZ_UNIT))
            )
            if second["ActiveState"] != "active" or second["MainPID"] != pid:
                raise BenchRefusal("provider_uncertain")
        elif maez["MainPID"] != 0:
            raise BenchRefusal("provider_uncertain")
        try:
            timestamp = _validated_clock_timestamp(self.clock.now_utc())
            port_closed = self.port_probe.is_free(8082)
        except BenchRefusal:
            raise
        except Exception:
            raise BenchRefusal("provider_uncertain") from None
        if type(port_closed) is not bool:
            raise BenchRefusal("provider_uncertain")
        try:
            snapshot = cm.ContainmentSnapshot(
                phase=phase,
                boundary=boundary,
                timestamp=timestamp,
                screen_flag_value=flag_value,
                active_state=vision["ActiveState"],
                substate=vision["SubState"],
                enabled_state=vision["UnitFileState"],
                maez_active_state=maez_state,
                maez_process_screen_flag_value=process_flag,
                port_closed=port_closed,
                flag_source_sha256=hashlib.sha256(flag_bytes).hexdigest(),
                vision_unit_sha256=hashlib.sha256(unit_bytes).hexdigest(),
            )
        except (TypeError, ValueError):
            raise BenchRefusal("containment_violation") from None
        return snapshot


class SyntheticContainmentProvider(_WitnessedProvider):
    tier = "rehearsal"

    def __init__(
        self,
        *,
        clock: Clock,
        port_probe: PortProbe,
        flag_source_sha256: str,
        vision_unit_sha256: str,
        fail_boundary: str | None = None,
    ) -> None:
        if fail_boundary not in {None, "before", "after"}:
            raise ValueError("synthetic_containment_invalid")
        if _SHA256_RE.fullmatch(flag_source_sha256) is None or _SHA256_RE.fullmatch(
            vision_unit_sha256
        ) is None:
            raise ValueError("synthetic_containment_invalid")
        self.clock = clock
        self.port_probe = port_probe
        self.flag_source_sha256 = flag_source_sha256
        self.vision_unit_sha256 = vision_unit_sha256
        self.fail_boundary = fail_boundary
        self.capture_count = 0
        self._init_provider_witness(synthetic=True)

    def capture(self, phase: str, boundary: str) -> cm.ContainmentSnapshot:
        self.capture_count += 1
        if boundary == self.fail_boundary:
            raise BenchRefusal("containment_violation")
        try:
            port_closed = self.port_probe.is_free(8082)
            timestamp = _validated_clock_timestamp(self.clock.now_utc())
            snapshot = cm.ContainmentSnapshot(
                phase=phase,
                boundary=boundary,
                timestamp=timestamp,
                screen_flag_value="0",
                active_state="inactive",
                substate="dead",
                enabled_state="disabled",
                maez_active_state="inactive",
                maez_process_screen_flag_value=None,
                port_closed=port_closed,
                flag_source_sha256=self.flag_source_sha256,
                vision_unit_sha256=self.vision_unit_sha256,
            )
        except BenchRefusal:
            raise
        except (TypeError, ValueError):
            raise BenchRefusal("provider_uncertain") from None
        return snapshot


class SyntheticServiceState(_WitnessedProvider):
    tier = "rehearsal"

    def __init__(self, states: dict[str, str]) -> None:
        self._states = dict(states)
        self._init_provider_witness(synthetic=True)

    def is_active(self, unit: str) -> str:
        if type(unit) is not str or not unit:
            raise BenchRefusal("provider_uncertain")
        try:
            state = self._states[unit]
        except KeyError:
            raise BenchRefusal("provider_uncertain") from None
        if type(state) is not str or not state:
            raise BenchRefusal("provider_uncertain")
        return state


class SyntheticPortProbe(_WitnessedProvider):
    tier = "rehearsal"

    def __init__(
        self,
        free: set[int],
        *,
        rehearsal_ports: RehearsalPortRegistry | None = None,
    ) -> None:
        try:
            self._free = set(free)
        except (TypeError, ValueError):
            self._free = set()
            self._configuration_valid = False
        else:
            fixed_ports = {*PRODUCTION_PORTS, BENCH_PORT}
            self._configuration_valid = type(free) is set and all(
                type(port) is int and 0 < port <= 65_535 for port in self._free
            ) and self._free <= fixed_ports
        if (
            rehearsal_ports is not None
            and type(rehearsal_ports) is not RehearsalPortRegistry
        ):
            self._configuration_valid = False
        self.rehearsal_ports = rehearsal_ports
        self._init_provider_witness(synthetic=True)

    def is_free(
        self,
        port: int,
        *,
        lease: RehearsalPortLease | None = None,
    ) -> bool:
        if (
            not self._configuration_valid
            or type(port) is not int
            or not 0 < port <= 65_535
        ):
            raise BenchRefusal("provider_uncertain")
        fixed_ports = {*PRODUCTION_PORTS, BENCH_PORT}
        if port in fixed_ports:
            if lease is not None:
                raise BenchRefusal("provider_uncertain")
            return port in self._free
        registry = self.rehearsal_ports
        if (
            type(registry) is not RehearsalPortRegistry
            or type(lease) is not RehearsalPortLease
            or lease.port != port
        ):
            raise BenchRefusal("provider_uncertain")
        registry.snapshot_exact(lease)
        self._record_loopback_kernel_call()
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError:
            raise BenchRefusal("provider_uncertain") from None
        result: bool | None = None
        failure = False
        try:
            try:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(("127.0.0.1", port))
                result = True
            except OSError as exc:
                if exc.errno == errno.EADDRINUSE:
                    result = False
                else:
                    failure = True
        finally:
            try:
                probe.close()
            except OSError:
                failure = True
        if failure or result is None:
            raise BenchRefusal("provider_uncertain")
        if result:
            registry.retire_exact(lease)
        return result


class SyntheticGpu(_WitnessedProvider):
    tier = "rehearsal"

    def __init__(
        self,
        uuids: list[str],
        inventory_by_stage: list[list[tuple[int, str]]] | None,
        memory_by_stage: list[tuple[float, int]] | None,
    ) -> None:
        self._uuids = list(uuids)
        self._inventories = (
            None
            if inventory_by_stage is None
            else tuple(tuple(stage) for stage in copy.deepcopy(inventory_by_stage))
        )
        self._memories = (
            None if memory_by_stage is None else tuple(copy.deepcopy(memory_by_stage))
        )
        self._inventory_index = 0
        self._memory_index = 0
        self._init_provider_witness(synthetic=True)

    def enumerate_uuids(self) -> list[str]:
        if any(not _valid_gpu_uuid(uuid) for uuid in self._uuids):
            raise BenchRefusal("provider_uncertain")
        return list(self._uuids)

    def inventory(self, uuid: str) -> list[tuple[int, str]]:
        if uuid not in self._uuids or self._inventories is None:
            raise BenchRefusal("provider_uncertain")
        if self._inventory_index >= len(self._inventories):
            raise BenchRefusal("provider_uncertain")
        value = self._inventories[self._inventory_index]
        self._inventory_index += 1
        normalized: set[tuple[int, str]] = set()
        for row in value:
            if (
                type(row) is not tuple
                or len(row) != 2
                or type(row[0]) is not int
                or row[0] <= 0
                or type(row[1]) is not str
                or not row[1]
                or not os.path.basename(row[1])
            ):
                raise BenchRefusal("provider_uncertain")
            normalized.add((row[0], os.path.basename(row[1])))
        if len(normalized) != len(value):
            raise BenchRefusal("provider_uncertain")
        return sorted(normalized)

    def memory(self, uuid: str) -> tuple[float, int]:
        if uuid not in self._uuids or self._memories is None:
            raise BenchRefusal("provider_uncertain")
        if self._memory_index >= len(self._memories):
            raise BenchRefusal("provider_uncertain")
        value = self._memories[self._memory_index]
        self._memory_index += 1
        if (
            type(value) is not tuple
            or len(value) != 2
            or type(value[0]) is not float
            or not 0 <= value[0] <= 100
            or type(value[1]) is not int
            or value[1] < 0
        ):
            raise BenchRefusal("provider_uncertain")
        return value


class SyntheticKernelLog(_WitnessedProvider):
    tier = "rehearsal"

    def __init__(self, counts: dict[str, int]) -> None:
        if set(counts) != set(KERNEL_COUNTER_KEYS) or any(
            type(value) is not int or value < 0 for value in counts.values()
        ):
            raise ValueError("synthetic_kernel_invalid")
        self._counts = dict(counts)
        self._cursor_sequence = itertools.count(1)
        self._init_provider_witness(synthetic=True)

    def cursor(self) -> str:
        return f"synthetic-cursor-{next(self._cursor_sequence):06d}"

    def count_signatures(
        self, start_cursor: str, end_cursor: str
    ) -> dict[str, int]:
        if (
            type(start_cursor) is not str
            or not start_cursor
            or type(end_cursor) is not str
            or not end_cursor
        ):
            raise BenchRefusal("provider_uncertain")
        if start_cursor == end_cursor:
            return dict.fromkeys(KERNEL_COUNTER_KEYS, 0)
        return dict(self._counts)


class SyntheticBackendMap(_WitnessedProvider):
    tier = "rehearsal"

    def __init__(
        self,
        maps_text_by_pid: dict[int, str],
        *,
        default_maps_text: str | None = None,
    ) -> None:
        try:
            self._maps = dict(maps_text_by_pid)
        except (TypeError, ValueError):
            self._maps = {}
            self._configuration_valid = False
        else:
            self._configuration_valid = all(
                type(pid) is int and pid > 0 for pid in self._maps
            )
        self._default_maps_text = default_maps_text
        if self._configuration_valid:
            for evidence in (*self._maps.values(), default_maps_text):
                if evidence is None:
                    continue
                if type(evidence) is not str:
                    self._configuration_valid = False
                    break
                try:
                    cm.parse_backend_maps(evidence)
                except ValueError:
                    self._configuration_valid = False
                    break
        self._init_provider_witness(synthetic=True)

    def read_maps(self, pid: int) -> str:
        if not self._configuration_valid or type(pid) is not int or pid <= 0:
            raise BenchRefusal("provider_uncertain")
        evidence = self._maps.get(pid, self._default_maps_text)
        if type(evidence) is not str:
            raise BenchRefusal("provider_uncertain") from None
        try:
            cm.parse_backend_maps(evidence)
        except ValueError:
            raise BenchRefusal("provider_uncertain")
        return evidence


class FrozenClock(_WitnessedProvider):
    tier = "rehearsal"

    def __init__(self, start_ts: str, *, monotonic_start: float = 0.0) -> None:
        if type(start_ts) is not str or not start_ts.endswith("Z"):
            raise ValueError("frozen_clock_invalid")
        try:
            self._instant = datetime.fromisoformat(start_ts[:-1] + "+00:00")
        except ValueError:
            raise ValueError("frozen_clock_invalid") from None
        if self._instant.tzinfo is None:
            raise ValueError("frozen_clock_invalid")
        try:
            monotonic_value = float(monotonic_start)
        except (OverflowError, TypeError, ValueError):
            raise ValueError("frozen_clock_invalid") from None
        if (
            type(monotonic_start) not in {int, float}
            or not math.isfinite(monotonic_value)
            or monotonic_value < 0
        ):
            raise ValueError("frozen_clock_invalid")
        self._monotonic = monotonic_value
        self._init_provider_witness(synthetic=True)

    def now_utc(self) -> str:
        return self._instant.astimezone(UTC).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, seconds: float) -> None:
        try:
            delta = float(seconds)
        except (OverflowError, TypeError, ValueError):
            raise ValueError("frozen_clock_invalid") from None
        if (
            type(seconds) not in {int, float}
            or not math.isfinite(delta)
            or delta < 0
        ):
            raise ValueError("frozen_clock_invalid")
        new_monotonic = self._monotonic + delta
        if not math.isfinite(new_monotonic):
            raise ValueError("frozen_clock_invalid")
        try:
            new_instant = self._instant + timedelta(seconds=delta)
        except (OverflowError, ValueError):
            raise ValueError("frozen_clock_invalid") from None
        self._instant = new_instant
        self._monotonic = new_monotonic


def ambient_topology_hash(
    inventory: list[tuple[int, str]], owned_pids: set[int]
) -> str:
    if type(inventory) is not list or type(owned_pids) is not set or any(
        type(pid) is not int or pid <= 0 for pid in owned_pids
    ):
        raise BenchRefusal("provider_uncertain")
    for row in inventory:
        if (
            type(row) is not tuple
            or len(row) != 2
            or type(row[0]) is not int
            or row[0] <= 0
            or type(row[1]) is not str
            or not row[1]
            or not os.path.basename(row[1])
        ):
            raise BenchRefusal("provider_uncertain")
    projected = sorted(
        {
            (pid, os.path.basename(name))
            for pid, name in inventory
            if pid not in owned_pids
        }
    )
    encoded = json.dumps(
        projected, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


_ATTEMPT_NAME_RE = re.compile(r"attempt-(?P<ordinal>[0-9]{3,})")


class _DiskOrdinalCollision(Exception):
    """A collision raised only by the allocator's claim syscall."""


def _claim_attempt_directory(parent_fd: int, name: str) -> None:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise _DiskOrdinalCollision from None
        raise


def _allocate_disk_ordinal(
    parent_fd: int,
    *,
    name_pattern: re.Pattern[str],
    starting_ordinal: int,
    claim: Callable[[int], None],
) -> int:
    """Claim scan-max-plus-one from one held directory descriptor."""

    if type(starting_ordinal) is not int or starting_ordinal < 0:
        raise ValueError("ordinal_start_invalid")
    try:
        names = os.listdir(parent_fd)
    except OSError:
        _filesystem_hazard()
    numbers = [
        int(match.group("ordinal"))
        for name in names
        if (match := name_pattern.fullmatch(name)) is not None
    ]
    candidate = max(numbers, default=starting_ordinal - 1) + 1
    while True:
        try:
            claim(candidate)
        except _DiskOrdinalCollision:
            candidate += 1
            continue
        return candidate


def _allocate_attempt(
    *,
    window_id: str,
    phase: str,
    policy: ArtifactPolicy,
    root: Path,
) -> Path:
    if (
        type(window_id) is not str
        or _NAME_SEED.fullmatch(window_id) is None
        or phase not in {"vulkan_baseline", "cuda_candidate"}
        or type(getattr(policy, "tier", None)) is not str
        or policy.tier not in {"production", "rehearsal"}
    ):
        raise BenchRefusal("filesystem_hazard")
    prefix = "rehearsal/" if policy.tier == "rehearsal" else ""
    parent_relative = f"{prefix}windows/{window_id}/{phase}"
    parent_fd, _parts, _chain = _open_parent_fd(
        f"{parent_relative}/.attempt-anchor",
        root=root,
        create=True,
    )
    try:
        def claim_phase_attempt(ordinal: int) -> None:
            try:
                _claim_attempt_directory(parent_fd, f"attempt-{ordinal:03d}")
            except FileExistsError as exc:
                if exc.errno == errno.EEXIST:
                    raise _DiskOrdinalCollision from None
                raise

        try:
            candidate = _allocate_disk_ordinal(
                parent_fd,
                name_pattern=_ATTEMPT_NAME_RE,
                starting_ordinal=0,
                claim=claim_phase_attempt,
            )
        except OSError:
            _filesystem_hazard()
        name = f"attempt-{candidate:03d}"
        child_fd = _open_existing_directory(parent_fd, name)
        os.close(child_fd)
        return root / parent_relative / name
    finally:
        os.close(parent_fd)


_COMMAND_NAMES = (
    "static-preflight",
    "rehearse",
    "vulkan-baseline",
    "cuda-candidate",
    "assemble-stage1",
)
_COMMAND_ARTIFACT_NAME_RE = re.compile(
    r"(?:(?P<quarantine>\.command-cleanup-))?"
    r"command-[a-z][a-z0-9-]*-attempt-(?P<ordinal>[0-9]{3,})-"
    r"(?:admission|terminal)\.json"
    r"(?(quarantine)-[0-9a-f]{32}|)"
)
_COMMAND_NAMESPACE_QUARANTINE_RE = re.compile(
    r"\.command-cleanup-rehearsal-[0-9a-f]{32}"
)
_COMMAND_SIGNALS = frozenset({signal.SIGINT, signal.SIGTERM})
_COMMAND_ATTEMPT_GUARD = object()


@dataclass(frozen=True, slots=True, init=False)
class CommandAttempt:
    command: str
    ordinal: int
    admission_ref: str
    admission_sha256: str
    namespace: str
    _root_identity: tuple[int, int]
    _admission_identity: tuple[int, int]

    def __init__(
        self,
        command: str,
        ordinal: int,
        admission_ref: str,
        admission_sha256: str,
        namespace: str,
        root_identity: tuple[int, int],
        admission_identity: tuple[int, int],
        *,
        _guard: object,
    ) -> None:
        if _guard is not _COMMAND_ATTEMPT_GUARD:
            raise ValueError("command_attempt_sealed")
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "admission_ref", admission_ref)
        object.__setattr__(self, "admission_sha256", admission_sha256)
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "_root_identity", root_identity)
        object.__setattr__(self, "_admission_identity", admission_identity)


class _CommandInterrupted(BaseException):
    """Explicit CLI interruption, optionally bound to a latched admission."""

    def __init__(self, signum: int, attempt: CommandAttempt | None = None) -> None:
        if signum not in _COMMAND_SIGNALS:
            raise ValueError("command_signal_invalid")
        self.signum = int(signum)
        self.attempt = attempt
        super().__init__(self.signum)


def _command_name(command: str, ordinal: int, role: str) -> str:
    if (
        command not in _COMMAND_NAMES
        or type(ordinal) is not int
        or ordinal < 1
        or role not in {"admission", "terminal"}
    ):
        raise ValueError("command_artifact_invalid")
    return f"command-{command}-attempt-{ordinal:03d}-{role}.json"


def _command_ref(namespace: str, name: str) -> str:
    if namespace == "":
        return name
    if namespace == "rehearsal":
        return f"rehearsal/{name}"
    raise ValueError("command_namespace_invalid")


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _held_root_is_bound(root_fd: int, root: Path) -> bool:
    try:
        held = _check_directory_fd(root_fd)
        current = os.stat(root, follow_symlinks=False)
    except (BenchRefusal, OSError, TypeError, ValueError):
        return False
    return (
        stat.S_ISDIR(current.st_mode)
        and current.st_uid == os.geteuid()
        and stat.S_IMODE(current.st_mode) == 0o700
        and _same_inode(held, current)
    )


def _held_namespace_is_bound(root_fd: int, parent_fd: int, namespace: str) -> bool:
    if namespace == "":
        try:
            return _same_inode(_check_directory_fd(root_fd), _check_directory_fd(parent_fd))
        except BenchRefusal:
            return False
    try:
        held = _check_directory_fd(parent_fd)
        current = os.stat(namespace, dir_fd=root_fd, follow_symlinks=False)
    except (BenchRefusal, OSError):
        return False
    return stat.S_ISDIR(current.st_mode) and _same_inode(held, current)


def _named_inode_matches(parent_fd: int, name: str, expected: os.stat_result) -> bool:
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        return False
    return stat.S_ISREG(current.st_mode) and _same_inode(current, expected)


def _read_held_file(parent_fd: int, name: str) -> tuple[bytes, os.stat_result]:
    fd: int | None = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        os.set_inheritable(fd, False)
        initial = _check_file_fd(fd)
        chunks: list[bytes] = []
        remaining = TURN_ARTIFACT_BYTE_CAP + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        final = _check_file_fd(fd)
        if (
            len(payload) > TURN_ARTIFACT_BYTE_CAP
            or len(payload) != initial.st_size
            or _stable_file_identity(initial) != _stable_file_identity(final)
        ):
            _filesystem_hazard()
        return payload, final
    except OSError:
        _filesystem_hazard()
    finally:
        if fd is not None:
            os.close(fd)


def _consume_pending_command_signal() -> int | None:
    pending = set(signal.sigpending()).intersection(_COMMAND_SIGNALS)
    if not pending:
        return None
    selected = signal.SIGTERM if signal.SIGTERM in pending else signal.SIGINT
    while True:
        current = set(signal.sigpending()).intersection(_COMMAND_SIGNALS)
        if not current:
            break
        signal.sigwait(current)
    return int(selected)


def _command_signal_checkpoint() -> None:
    signum = _consume_pending_command_signal()
    if signum is not None:
        raise _CommandInterrupted(signum)


def _restore_command_mask_after_cleanup(
    old_mask: set[signal.Signals],
) -> None:
    """Best-effort restoration that cannot replace a cleanup refusal."""

    for _attempt in range(2):
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            return
        except (OSError, ValueError, _CommandInterrupted):
            pass


def _acquire_cleanup_name(
    parent_fd: int,
    name: str,
    expected_identity: tuple[int, int],
    *,
    directory: bool,
) -> str:
    observed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    observed_matches = (
        stat.S_ISDIR(observed.st_mode) if directory else stat.S_ISREG(observed.st_mode)
    ) and (observed.st_dev, observed.st_ino) == expected_identity
    if not observed_matches:
        raise OSError(errno.ESTALE, "cleanup target changed")

    quarantine = f".command-cleanup-{name}-{secrets.token_hex(16)}"
    os.rename(
        name,
        quarantine,
        src_dir_fd=parent_fd,
        dst_dir_fd=parent_fd,
    )
    acquired = os.stat(quarantine, dir_fd=parent_fd, follow_symlinks=False)
    if (
        (stat.S_ISDIR(acquired.st_mode) if directory else stat.S_ISREG(acquired.st_mode))
        and (acquired.st_dev, acquired.st_ino) == expected_identity
    ):
        return quarantine
    raise OSError(errno.ESTALE, "cleanup acquisition changed")


def _command_disk_max_ordinal(root_fd: int) -> int:
    """Return the run-global command ordinal from one locked bench root."""

    directory_fds = [root_fd]
    child_fds: list[int] = []
    try:
        try:
            root_names = os.listdir(root_fd)
        except OSError:
            _filesystem_hazard()
        child_names = sorted(
            name
            for name in root_names
            if name == "rehearsal"
            or _COMMAND_NAMESPACE_QUARANTINE_RE.fullmatch(name) is not None
        )
        for child_name in child_names:
            try:
                child_fd = os.open(
                    child_name,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=root_fd,
                )
            except OSError:
                _filesystem_hazard()
            child_fds.append(child_fd)
            _check_directory_fd(child_fd)
            directory_fds.append(child_fd)
        ordinals = [
            int(match.group("ordinal"))
            for name in root_names
            if (match := _COMMAND_ARTIFACT_NAME_RE.fullmatch(name)) is not None
        ]
        for directory_fd in directory_fds[1:]:
            for name in os.listdir(directory_fd):
                match = _COMMAND_ARTIFACT_NAME_RE.fullmatch(name)
                if match is not None:
                    ordinals.append(int(match.group("ordinal")))
        return max(ordinals, default=0)
    except OSError:
        _filesystem_hazard()
    finally:
        for child_fd in reversed(child_fds):
            os.close(child_fd)


def _restore_populated_namespace(
    root_fd: int,
    namespace: str,
    quarantine: str,
    namespace_identity: tuple[int, int],
) -> None:
    """Restore the creator inode while preserving an empty replacement."""

    replacement_fd: int | None = None
    replacement_quarantine: str | None = None
    try:
        replacement_fd = os.open(
            namespace,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=root_fd,
        )
        replacement = _check_directory_fd(replacement_fd)
        if (replacement.st_dev, replacement.st_ino) == namespace_identity:
            raise OSError(errno.ESTALE, "command namespace restore changed")
        if os.listdir(replacement_fd):
            raise OSError(errno.ENOTEMPTY, "replacement namespace populated")
        replacement_quarantine = _acquire_cleanup_name(
            root_fd,
            namespace,
            (replacement.st_dev, replacement.st_ino),
            directory=True,
        )
        try:
            os.rename(
                quarantine,
                namespace,
                src_dir_fd=root_fd,
                dst_dir_fd=root_fd,
            )
        except BaseException:
            try:
                os.stat(namespace, dir_fd=root_fd, follow_symlinks=False)
            except FileNotFoundError:
                os.rename(
                    replacement_quarantine,
                    namespace,
                    src_dir_fd=root_fd,
                    dst_dir_fd=root_fd,
                )
                os.fsync(root_fd)
            raise
        restored = os.stat(namespace, dir_fd=root_fd, follow_symlinks=False)
        if not stat.S_ISDIR(restored.st_mode) or (
            restored.st_dev,
            restored.st_ino,
        ) != namespace_identity:
            raise OSError(errno.ESTALE, "command namespace restore changed")
        os.fsync(root_fd)
    finally:
        if replacement_fd is not None:
            os.close(replacement_fd)


def _cleanup_command_claim(
    *,
    root_fd: int,
    parent_fd: int,
    namespace: str,
    namespace_created: bool,
    namespace_identity: tuple[int, int] | None,
    linked_name: str | None,
    linked_info: os.stat_result | None,
) -> None:
    lock_held = False
    try:
        fcntl.flock(root_fd, fcntl.LOCK_EX)
        lock_held = True
        if linked_name is not None:
            if linked_info is None:
                raise OSError(errno.ESTALE, "command binding changed")
            if not _named_inode_matches(parent_fd, linked_name, linked_info):
                raise OSError(errno.ESTALE, "command binding changed")
            acquired = _acquire_cleanup_name(
                parent_fd,
                linked_name,
                (linked_info.st_dev, linked_info.st_ino),
                directory=False,
            )
            os.unlink(acquired, dir_fd=parent_fd)
            os.fsync(parent_fd)
        if namespace_created:
            if namespace_identity is None:
                raise OSError(errno.ESTALE, "command namespace changed")
            cleanup_namespace_fd = parent_fd
            close_cleanup_namespace_fd = False
            if parent_fd == root_fd:
                cleanup_namespace_fd = os.open(
                    namespace,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=root_fd,
                )
                close_cleanup_namespace_fd = True
            try:
                if close_cleanup_namespace_fd:
                    opened = _check_directory_fd(cleanup_namespace_fd)
                    if (opened.st_dev, opened.st_ino) != namespace_identity:
                        raise OSError(errno.ESTALE, "command namespace changed")
                if os.listdir(cleanup_namespace_fd):
                    raise OSError(errno.ENOTEMPTY, "command namespace populated")
            finally:
                if close_cleanup_namespace_fd:
                    os.close(cleanup_namespace_fd)
            acquired = _acquire_cleanup_name(
                root_fd,
                namespace,
                namespace_identity,
                directory=True,
            )
            try:
                os.rmdir(acquired, dir_fd=root_fd)
            except OSError as exc:
                if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                    raise
                try:
                    os.stat(namespace, dir_fd=root_fd, follow_symlinks=False)
                except FileNotFoundError:
                    os.rename(
                        acquired,
                        namespace,
                        src_dir_fd=root_fd,
                        dst_dir_fd=root_fd,
                    )
                    restored = os.stat(
                        namespace, dir_fd=root_fd, follow_symlinks=False
                    )
                    if not stat.S_ISDIR(restored.st_mode) or (
                        restored.st_dev,
                        restored.st_ino,
                    ) != namespace_identity:
                        raise OSError(errno.ESTALE, "command namespace restore changed")
                    os.fsync(root_fd)
                else:
                    _restore_populated_namespace(
                        root_fd,
                        namespace,
                        acquired,
                        namespace_identity,
                    )
                raise
            os.fsync(root_fd)
    except (BenchRefusal, OSError):
        raise BenchRefusal("cleanup_incomplete") from None
    finally:
        if lock_held:
            try:
                fcntl.flock(root_fd, fcntl.LOCK_UN)
            except OSError:
                raise BenchRefusal("cleanup_incomplete") from None


def _admit_command(
    command: str,
    window_id: str | None,
    policy: ArtifactPolicy,
    clock: Clock,
    root: Path,
    *,
    _on_latched: Callable[[CommandAttempt], None] | None = None,
    _on_cleanup_incomplete: Callable[[], None] | None = None,
) -> CommandAttempt:
    tier = getattr(policy, "tier", None)
    namespace = "rehearsal" if tier == "rehearsal" else ""
    if (
        command not in _COMMAND_NAMES
        or tier not in {"production", "rehearsal"}
        or (command == "rehearse") != (tier == "rehearsal")
        or (
            window_id is not None
            and (type(window_id) is not str or _NAME_SEED.fullmatch(window_id) is None)
        )
    ):
        raise BenchRefusal("filesystem_hazard")

    old_mask: set[signal.Signals] | None = signal.pthread_sigmask(
        signal.SIG_BLOCK, _COMMAND_SIGNALS
    )
    root_fd: int | None = None
    parent_fd: int | None = None
    namespace_created = False
    namespace_identity: tuple[int, int] | None = None
    linked_name: str | None = None
    linked_info: os.stat_result | None = None
    latched: CommandAttempt | None = None
    linearized = False
    failure: BaseException | None = None
    try:
        root_fd = _open_root_fd(root)
        parent_fd = root_fd

        def claim(ordinal: int) -> None:
            nonlocal latched, linearized, linked_info, linked_name
            name = _command_name(command, ordinal, "admission")
            fields: dict[str, object] = {
                "command": command,
                "ordinal": ordinal,
                "window_id": window_id,
                "status": "admitted",
                "timestamp": _validated_clock_timestamp(clock.now_utc()),
            }
            encoded = policy.encode("command_admission", fields)
            fd: int | None = None
            try:
                fd = _open_anonymous_file(parent_fd, append=False)
                _write_all(fd, encoded)
                os.fsync(fd)
                source = _check_file_fd(
                    fd, expected_nlink=0, expected_size=len(encoded)
                )
                lock_held = False
                try:
                    fcntl.flock(root_fd, fcntl.LOCK_EX)
                    lock_held = True
                    if ordinal <= _command_disk_max_ordinal(root_fd):
                        raise _DiskOrdinalCollision
                    try:
                        os.link(
                            f"/proc/self/fd/{fd}",
                            name,
                            dst_dir_fd=parent_fd,
                            follow_symlinks=True,
                        )
                        linked_name, linked_info = name, source
                    except OSError as exc:
                        if exc.errno == errno.EEXIST:
                            raise _DiskOrdinalCollision from None
                        if _named_inode_matches(parent_fd, name, source):
                            linked_name, linked_info = name, source
                        raise
                    except (KeyboardInterrupt, _CommandInterrupted):
                        if _named_inode_matches(parent_fd, name, source):
                            linked_name, linked_info = name, source
                        raise
                finally:
                    if lock_held:
                        fcntl.flock(root_fd, fcntl.LOCK_UN)
                _command_signal_checkpoint()
                if not _held_root_is_bound(root_fd, root) or not _held_namespace_is_bound(
                    root_fd, parent_fd, namespace
                ):
                    raise BenchRefusal("filesystem_hazard")
                os.fsync(parent_fd)
                _command_signal_checkpoint()
                reopened, reopened_info = _read_held_file(parent_fd, name)
                _command_signal_checkpoint()
                if (
                    reopened != encoded
                    or not _same_inode(source, reopened_info)
                    or not _held_root_is_bound(root_fd, root)
                ):
                    raise BenchRefusal("filesystem_hazard")
                digest = hashlib.sha256(reopened).hexdigest()
                _command_signal_checkpoint()
                final_bytes, final_info = _read_held_file(parent_fd, name)
                final_digest = hashlib.sha256(final_bytes).hexdigest()
                if (
                    final_bytes != encoded
                    or final_digest != digest
                    or not _same_inode(source, final_info)
                    or not _held_root_is_bound(root_fd, root)
                    or not _held_namespace_is_bound(root_fd, parent_fd, namespace)
                    or not _named_inode_matches(parent_fd, name, source)
                ):
                    raise BenchRefusal("filesystem_hazard")
                os.close(fd)
                fd = None
                latched = CommandAttempt(
                    command,
                    ordinal,
                    _command_ref(namespace, name),
                    final_digest,
                    namespace,
                    (
                        _check_directory_fd(root_fd).st_dev,
                        _check_directory_fd(root_fd).st_ino,
                    ),
                    (final_info.st_dev, final_info.st_ino),
                    _guard=_COMMAND_ATTEMPT_GUARD,
                )
                linearized = True
            finally:
                if fd is not None:
                    os.close(fd)

        try:
            if namespace:
                try:
                    parent_fd = os.open(
                        namespace,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=root_fd,
                    )
                except FileNotFoundError:
                    try:
                        os.mkdir(namespace, mode=0o700, dir_fd=root_fd)
                        namespace_created = True
                        created = os.stat(
                            namespace, dir_fd=root_fd, follow_symlinks=False
                        )
                        namespace_identity = (created.st_dev, created.st_ino)
                    except FileExistsError:
                        pass
                    parent_fd = os.open(
                        namespace,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=root_fd,
                    )
                opened_namespace = _check_directory_fd(parent_fd)
                if namespace_created and namespace_identity != (
                    opened_namespace.st_dev,
                    opened_namespace.st_ino,
                ):
                    raise BenchRefusal("filesystem_hazard")
            _allocate_disk_ordinal(
                parent_fd,
                name_pattern=_COMMAND_ARTIFACT_NAME_RE,
                starting_ordinal=1,
                claim=claim,
            )
        except (Exception, KeyboardInterrupt, _CommandInterrupted) as exc:
            failure = exc

        if failure is not None:
            try:
                _cleanup_command_claim(
                    root_fd=root_fd,
                    parent_fd=parent_fd,
                    namespace=namespace,
                    namespace_created=namespace_created,
                    namespace_identity=namespace_identity,
                    linked_name=linked_name,
                    linked_info=linked_info,
                )
            except BenchRefusal as cleanup_exc:
                _consume_pending_command_signal()
                if _on_cleanup_incomplete is not None:
                    _on_cleanup_incomplete()
                _restore_command_mask_after_cleanup(old_mask)
                old_mask = None
                raise cleanup_exc
            pending_signum = _consume_pending_command_signal()
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            except _CommandInterrupted as interrupted:
                raise _CommandInterrupted(interrupted.signum) from None
            old_mask = None
            if isinstance(failure, _CommandInterrupted):
                raise _CommandInterrupted(failure.signum) from None
            if pending_signum is not None:
                raise _CommandInterrupted(pending_signum) from None
            if isinstance(failure, KeyboardInterrupt):
                raise failure
            if isinstance(failure, BenchRefusal):
                raise failure
            raise BenchRefusal("filesystem_hazard") from None

        if latched is None or not linearized:
            raise BenchRefusal("filesystem_hazard")
        if _on_latched is not None:
            _on_latched(latched)
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except _CommandInterrupted as interrupted:
            raise _CommandInterrupted(interrupted.signum, latched) from None
        old_mask = None
        return latched
    finally:
        try:
            if parent_fd is not None and parent_fd != root_fd:
                os.close(parent_fd)
            if root_fd is not None:
                os.close(root_fd)
        finally:
            if old_mask is not None:
                _restore_command_mask_after_cleanup(old_mask)


def publish_command_artifact(
    attempt: CommandAttempt,
    role: str,
    encoded: bytes,
    *,
    root: Path,
    on_committed: Callable[[str, str], None] | None = None,
) -> tuple[str, str]:
    if type(attempt) is not CommandAttempt or role not in {"admission", "terminal"}:
        raise ValueError("command_artifact_invalid")
    if type(encoded) is not bytes or len(encoded) > TURN_ARTIFACT_BYTE_CAP:
        raise ValueError("command_artifact_invalid")
    if on_committed is not None and not callable(on_committed):
        raise ValueError("command_artifact_invalid")
    expected_admission = _command_ref(
        attempt.namespace,
        _command_name(attempt.command, attempt.ordinal, "admission"),
    )
    if attempt.admission_ref != expected_admission:
        raise BenchRefusal("filesystem_hazard")

    old_mask: set[signal.Signals] | None = signal.pthread_sigmask(
        signal.SIG_BLOCK, _COMMAND_SIGNALS
    )
    root_fd: int | None = None
    parent_fd: int | None = None
    linked_name: str | None = None
    linked_info: os.stat_result | None = None
    try:
        root_fd = _open_root_fd(root)
        parent_fd = root_fd
        if attempt.namespace:
            parent_fd = _open_existing_directory(root_fd, attempt.namespace)
        admission_name = _command_name(attempt.command, attempt.ordinal, "admission")
        admission_bytes, _admission_info = _read_held_file(parent_fd, admission_name)
        if hashlib.sha256(admission_bytes).hexdigest() != attempt.admission_sha256:
            raise BenchRefusal("filesystem_hazard")

        name = _command_name(attempt.command, attempt.ordinal, role)
        relative = _command_ref(attempt.namespace, name)
        fd: int | None = None
        source: os.stat_result | None = None
        result: tuple[str, str] | None = None
        failure: BaseException | None = None
        cleanup_failure: BenchRefusal | None = None
        try:
            fd = _open_anonymous_file(parent_fd, append=False)
            _write_all(fd, encoded)
            os.fsync(fd)
            source = _check_file_fd(fd, expected_nlink=0, expected_size=len(encoded))
            os.link(
                f"/proc/self/fd/{fd}",
                name,
                dst_dir_fd=parent_fd,
                follow_symlinks=True,
            )
            linked_name, linked_info = name, source
            _command_signal_checkpoint()
            if not _held_root_is_bound(root_fd, root) or not _held_namespace_is_bound(
                root_fd, parent_fd, attempt.namespace
            ):
                raise BenchRefusal("filesystem_hazard")
            os.fsync(parent_fd)
            _command_signal_checkpoint()
            reopened, reopened_info = _read_held_file(parent_fd, name)
            if reopened != encoded or not _same_inode(source, reopened_info):
                raise BenchRefusal("filesystem_hazard")
            digest = hashlib.sha256(reopened).hexdigest()
            _command_signal_checkpoint()
            if (
                not _held_root_is_bound(root_fd, root)
                or not _held_namespace_is_bound(
                    root_fd, parent_fd, attempt.namespace
                )
                or not _named_inode_matches(parent_fd, name, source)
            ):
                raise BenchRefusal("filesystem_hazard")
            os.close(fd)
            fd = None
            result = (relative, digest)
            if on_committed is not None:
                on_committed(*result)
        except (Exception, KeyboardInterrupt, _CommandInterrupted) as exc:
            failure = exc

        if fd is not None:
            try:
                os.close(fd)
                fd = None
            except (OSError, KeyboardInterrupt, _CommandInterrupted) as exc:
                if failure is None:
                    failure = exc

        if failure is not None:
            if (
                linked_name is None
                and source is not None
                and _named_inode_matches(parent_fd, name, source)
            ):
                linked_name, linked_info = name, source
            if linked_name is not None:
                try:
                    _cleanup_command_claim(
                        root_fd=root_fd,
                        parent_fd=parent_fd,
                        namespace=attempt.namespace,
                        namespace_created=False,
                        namespace_identity=None,
                        linked_name=linked_name,
                        linked_info=linked_info,
                    )
                except BenchRefusal as exc:
                    cleanup_failure = exc

        pending_signum = _consume_pending_command_signal()
        if cleanup_failure is not None:
            _restore_command_mask_after_cleanup(old_mask)
            old_mask = None
            raise cleanup_failure

        restore_signum: int | None = None
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except _CommandInterrupted as exc:
            restore_signum = exc.signum
        old_mask = None

        failure_signum: int | None = None
        if isinstance(failure, _CommandInterrupted):
            failure_signum = failure.signum
        elif isinstance(failure, KeyboardInterrupt):
            failure_signum = int(signal.SIGINT)
        observed_signals = {
            signum
            for signum in (failure_signum, pending_signum, restore_signum)
            if signum is not None
        }
        if int(signal.SIGTERM) in observed_signals:
            raise _CommandInterrupted(int(signal.SIGTERM)) from None
        if int(signal.SIGINT) in observed_signals:
            raise _CommandInterrupted(int(signal.SIGINT)) from None

        if isinstance(failure, BenchRefusal):
            raise failure
        if failure is not None:
            raise failure
        if result is None:
            raise BenchRefusal("filesystem_hazard")
        return result
    except OSError:
        raise BenchRefusal("filesystem_hazard") from None
    finally:
        try:
            if parent_fd is not None and parent_fd != root_fd:
                os.close(parent_fd)
            if root_fd is not None:
                os.close(root_fd)
        finally:
            if old_mask is not None:
                try:
                    signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
                except _CommandInterrupted:
                    pass


_IMMUTABLE_PREIMAGE_RE = re.compile(
    r"preimages/rollback-manifest-[0-9a-f]{64}\.json\Z"
)


@dataclass(slots=True)
class _ImmutableAttemptAuthority:
    root_fd: int
    admission_fd: int
    root: Path
    admission_name: str
    payload: bytes
    admission_identity: tuple[int, ...]

    def reprove(self) -> None:
        try:
            if not _held_root_is_bound(self.root_fd, self.root):
                _filesystem_hazard()
            os.lseek(self.admission_fd, 0, os.SEEK_SET)
            initial = _check_file_fd(
                self.admission_fd, expected_size=len(self.payload)
            )
            chunks: list[bytes] = []
            remaining = len(self.payload) + 1
            while remaining:
                chunk = os.read(
                    self.admission_fd, min(remaining, 1024 * 1024)
                )
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            final = _check_file_fd(
                self.admission_fd, expected_size=len(self.payload)
            )
            named = os.stat(
                self.admission_name,
                dir_fd=self.root_fd,
                follow_symlinks=False,
            )
            if (
                b"".join(chunks) != self.payload
                or _stable_file_identity(initial) != self.admission_identity
                or _stable_file_identity(final) != self.admission_identity
                or not stat.S_ISREG(named.st_mode)
                or named.st_uid != os.geteuid()
                or named.st_nlink != 1
                or stat.S_IMODE(named.st_mode) != 0o600
                or _stable_file_identity(named) != self.admission_identity
            ):
                _filesystem_hazard()
        except OSError:
            _filesystem_hazard()

    def close(self) -> None:
        os.close(self.admission_fd)
        os.close(self.root_fd)


def _open_immutable_attempt_authority(
    attempt: CommandAttempt,
    *,
    root: Path,
    permitted_commands: frozenset[str],
) -> _ImmutableAttemptAuthority:
    """Re-enter through the supplied root; an in-memory attempt is not authority."""

    if (
        type(attempt) is not CommandAttempt
        or attempt.command not in permitted_commands
        or attempt.namespace != ""
    ):
        _filesystem_hazard()
    expected = _command_ref(
        attempt.namespace,
        _command_name(attempt.command, attempt.ordinal, "admission"),
    )
    if attempt.admission_ref != expected:
        _filesystem_hazard()
    root_fd: int | None = None
    admission_fd: int | None = None
    try:
        root_fd = _open_root_fd(root)
        root_info = _check_directory_fd(root_fd)
        if (root_info.st_dev, root_info.st_ino) != attempt._root_identity:
            _filesystem_hazard()
        admission_fd = os.open(
            expected, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_fd
        )
        os.set_inheritable(admission_fd, False)
        initial = _check_file_fd(admission_fd)
        chunks: list[bytes] = []
        remaining = TURN_ARTIFACT_BYTE_CAP + 1
        while remaining:
            chunk = os.read(admission_fd, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        final = _check_file_fd(admission_fd)
        current_admission = os.stat(
            expected, dir_fd=root_fd, follow_symlinks=False
        )
        if hashlib.sha256(payload).hexdigest() != attempt.admission_sha256:
            _filesystem_hazard()
        if (
            len(payload) > TURN_ARTIFACT_BYTE_CAP
            or len(payload) != initial.st_size
            or _stable_file_identity(initial) != _stable_file_identity(final)
            or not stat.S_ISREG(current_admission.st_mode)
            or current_admission.st_uid != os.geteuid()
            or current_admission.st_nlink != 1
            or stat.S_IMODE(current_admission.st_mode) != 0o600
            or _stable_file_identity(final)
            != _stable_file_identity(current_admission)
            or (current_admission.st_dev, current_admission.st_ino)
            != attempt._admission_identity
        ):
            _filesystem_hazard()
        wrapper = json.loads(payload)
        fields = wrapper["fields"]
        if (
            wrapper.get("schema") != COMMAND_ADMISSION_SCHEMA
            or fields.get("command") != attempt.command
            or fields.get("ordinal") != attempt.ordinal
            or fields.get("status") != "admitted"
        ):
            _filesystem_hazard()
        authority = _ImmutableAttemptAuthority(
            root_fd=root_fd,
            admission_fd=admission_fd,
            root=Path(root),
            admission_name=expected,
            payload=payload,
            admission_identity=_stable_file_identity(final),
        )
        root_fd = None
        admission_fd = None
        return authority
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        _filesystem_hazard()
    finally:
        if admission_fd is not None:
            os.close(admission_fd)
        if root_fd is not None:
            os.close(root_fd)


def _immutable_parts(relative: str) -> tuple[str, str]:
    if (
        type(relative) is not str
        or _IMMUTABLE_PREIMAGE_RE.fullmatch(relative) is None
    ):
        _filesystem_hazard()
    directory, name = relative.split("/", 1)
    return directory, name


def _validate_immutable_content_address(relative: str, data: bytes) -> None:
    expected = hashlib.sha256(data).hexdigest()
    if relative != f"preimages/rollback-manifest-{expected}.json":
        _filesystem_hazard()


def _open_preimages_directory(
    *,
    root: Path,
    create: bool,
    expected_root_identity: tuple[int, int],
) -> tuple[int, int]:
    root_fd = _open_root_fd(root)
    root_info = _check_directory_fd(root_fd)
    if (root_info.st_dev, root_info.st_ino) != expected_root_identity:
        os.close(root_fd)
        _filesystem_hazard()
    created_identity: tuple[int, int] | None = None
    parent_fd: int | None = None
    try:
        try:
            parent_fd = os.open(
                "preimages",
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root_fd,
            )
        except FileNotFoundError:
            if not create:
                _filesystem_hazard()
            try:
                os.mkdir("preimages", mode=0o700, dir_fd=root_fd)
                created = os.stat(
                    "preimages", dir_fd=root_fd, follow_symlinks=False
                )
                created_identity = (created.st_dev, created.st_ino)
            except FileExistsError:
                pass
            except OSError:
                _filesystem_hazard()
            try:
                os.fsync(root_fd)
                parent_fd = os.open(
                    "preimages",
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=root_fd,
                )
            except OSError:
                _filesystem_hazard()
        except OSError:
            _filesystem_hazard()
        opened = _check_directory_fd(parent_fd)
        current = os.stat("preimages", dir_fd=root_fd, follow_symlinks=False)
        if (
            not stat.S_ISDIR(current.st_mode)
            or not _same_inode(opened, current)
            or (
                created_identity is not None
                and created_identity != (opened.st_dev, opened.st_ino)
            )
        ):
            _filesystem_hazard()
        assert parent_fd is not None
        return root_fd, parent_fd
    except BaseException:
        if parent_fd is not None:
            os.close(parent_fd)
        os.close(root_fd)
        raise


def _read_exact_immutable(
    parent_fd: int,
    name: str,
    expected: bytes,
) -> os.stat_result:
    fd: int | None = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        initial = _check_file_fd(fd, expected_size=len(expected))
        payload = bytearray()
        while len(payload) <= len(expected):
            chunk = os.read(fd, len(expected) + 1 - len(payload))
            if not chunk:
                break
            payload.extend(chunk)
        if bytes(payload) != expected:
            _filesystem_hazard()
        final = _check_file_fd(fd, expected_size=len(expected))
        if _stable_file_identity(initial) != _stable_file_identity(final):
            _filesystem_hazard()
        os.fsync(fd)
        os.fsync(parent_fd)
        after = _check_file_fd(fd, expected_size=len(expected))
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            _stable_file_identity(final) != _stable_file_identity(after)
            or not _same_inode(after, named)
        ):
            _filesystem_hazard()
        return after
    except OSError:
        _filesystem_hazard()
    finally:
        if fd is not None:
            os.close(fd)


def _preimages_is_bound(root_fd: int, parent_fd: int) -> bool:
    try:
        held = _check_directory_fd(parent_fd)
        named = os.stat("preimages", dir_fd=root_fd, follow_symlinks=False)
    except (BenchRefusal, OSError):
        return False
    return stat.S_ISDIR(named.st_mode) and _same_inode(held, named)


def publish_or_verify_immutable(
    relative: str,
    data: bytes,
    *,
    attempt: CommandAttempt,
    root: Path,
) -> Path:
    """Create once after static admission, or durably verify exact prior bytes."""

    _directory, name = _immutable_parts(relative)
    if type(data) is not bytes or len(data) > TURN_ARTIFACT_BYTE_CAP:
        _filesystem_hazard()
    _validate_immutable_content_address(relative, data)
    authority = _open_immutable_attempt_authority(
        attempt, root=root, permitted_commands=frozenset({"static-preflight"})
    )
    try:
        root_fd, parent_fd = _open_preimages_directory(
            root=root,
            create=True,
            expected_root_identity=attempt._root_identity,
        )
        fd: int | None = None
        try:
            fd = _open_anonymous_file(parent_fd, append=False)
            _write_all(fd, data)
            os.fsync(fd)
            source = _check_file_fd(
                fd, expected_nlink=0, expected_size=len(data)
            )
            try:
                os.link(
                    f"/proc/self/fd/{fd}",
                    name,
                    dst_dir_fd=parent_fd,
                    follow_symlinks=True,
                )
            except FileExistsError:
                os.close(fd)
                fd = None
                _read_exact_immutable(parent_fd, name, data)
                if (
                    not _held_root_is_bound(root_fd, root)
                    or not _preimages_is_bound(root_fd, parent_fd)
                ):
                    _filesystem_hazard()
                authority.reprove()
                return Path(root) / relative
            except OSError:
                _filesystem_hazard()
            _check_file_fd(fd, expected_nlink=1, expected_size=len(data))
            os.fsync(parent_fd)
            published = _check_file_fd(
                fd, expected_nlink=1, expected_size=len(data)
            )
            named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                not _same_inode(source, published)
                or not _same_inode(published, named)
                or not _held_root_is_bound(root_fd, root)
                or not _preimages_is_bound(root_fd, parent_fd)
            ):
                _filesystem_hazard()
            _read_exact_immutable(parent_fd, name, data)
            if (
                not _held_root_is_bound(root_fd, root)
                or not _preimages_is_bound(root_fd, parent_fd)
            ):
                _filesystem_hazard()
            authority.reprove()
            return Path(root) / relative
        except OSError:
            _filesystem_hazard()
        finally:
            if fd is not None:
                os.close(fd)
            os.close(parent_fd)
            os.close(root_fd)
    finally:
        authority.close()


def verify_existing_immutable(
    relative: str,
    data: bytes,
    *,
    attempt: CommandAttempt,
    root: Path,
) -> Path:
    """Phase-only verification; this function never creates or repairs."""

    _directory, name = _immutable_parts(relative)
    if type(data) is not bytes or len(data) > TURN_ARTIFACT_BYTE_CAP:
        _filesystem_hazard()
    _validate_immutable_content_address(relative, data)
    authority = _open_immutable_attempt_authority(
        attempt,
        root=root,
        permitted_commands=frozenset({"vulkan-baseline", "cuda-candidate"}),
    )
    try:
        root_fd, parent_fd = _open_preimages_directory(
            root=root,
            create=False,
            expected_root_identity=attempt._root_identity,
        )
        try:
            _read_exact_immutable(parent_fd, name, data)
            if (
                not _held_root_is_bound(root_fd, root)
                or not _preimages_is_bound(root_fd, parent_fd)
            ):
                _filesystem_hazard()
            authority.reprove()
            return Path(root) / relative
        finally:
            os.close(parent_fd)
            os.close(root_fd)
    finally:
        authority.close()


_PROVIDERS_GUARD = object()
_TEST_TIER_GUARD = object()


@dataclass(frozen=True)
class PhaseConfig:
    phase: str
    argv: list[str]
    env: dict[str, str]
    alias: str
    prompts: tuple[str, ...]
    authorization: WindowAuthorization | Continuation
    parent_window: WindowAuthorization | None
    parent_packet_path: str | None
    bench_identity_fields: dict[str, object]
    runtime_identity_fields: dict[str, object]
    static_preflight_path: str
    gpu_uuid: str
    boot_id: str
    window_id: str
    expected_port: int | None
    static_admission_path: str | None = None
    static_completion_path: str | None = None
    parent_admission_path: str | None = None
    parent_completion_path: str | None = None
    readiness_timeout_s: float = READINESS_TIMEOUT_S

    def __post_init__(self) -> None:
        if (
            self.phase not in {"vulkan_baseline", "cuda_candidate"}
            or type(self.argv) is not list
            or not self.argv
            or any(type(value) is not str or not value for value in self.argv)
            or type(self.env) is not dict
            or any(
                type(key) is not str
                or not key
                or type(value) is not str
                for key, value in self.env.items()
            )
            or type(self.alias) is not str
            or not self.alias
            or type(self.prompts) is not tuple
            or len(self.prompts) != 7
            or any(type(prompt) is not str or not prompt for prompt in self.prompts)
            or type(self.bench_identity_fields) is not dict
            or type(self.runtime_identity_fields) is not dict
            or type(self.static_preflight_path) is not str
            or not self.static_preflight_path
            or type(self.gpu_uuid) is not str
            or not self.gpu_uuid
            or type(self.boot_id) is not str
            or not self.boot_id
            or type(self.window_id) is not str
            or _NAME_SEED.fullmatch(self.window_id) is None
            or (
                self.expected_port is not None
                and (
                    type(self.expected_port) is not int
                    or not 0 < self.expected_port <= 65_535
                )
            )
        ):
            raise ValueError("phase_config_invalid")
        if self.phase == "vulkan_baseline":
            if type(self.authorization) is not WindowAuthorization:
                raise ValueError("phase_config_invalid")
        elif type(self.authorization) is not Continuation:
            raise ValueError("phase_config_invalid")


@dataclass(frozen=True, slots=True)
class ProductionExecutionContract:
    pinned_path: str
    pinned_sha256: str
    effective_args_sha256: str
    argv: tuple[str, ...]
    environment: Mapping[str, str]

    def __post_init__(self) -> None:
        if (
            type(self.pinned_path) is not str
            or not os.path.isabs(self.pinned_path)
            or type(self.pinned_sha256) is not str
            or _SHA256_RE.fullmatch(self.pinned_sha256) is None
            or self.effective_args_sha256 != FROZEN_BENCH_ARGS_SHA256
            or type(self.argv) is not tuple
            or not self.argv
            or any(type(value) is not str or not value for value in self.argv)
            or _effective_args_sha256(list(self.argv))
            != self.effective_args_sha256
            or not isinstance(self.environment, Mapping)
            or any(
                type(key) is not str or type(value) is not str
                for key, value in self.environment.items()
            )
        ):
            raise ValueError("production_execution_contract_invalid")
        object.__setattr__(
            self,
            "environment",
            MappingProxyType(dict(self.environment)),
        )


@dataclass(frozen=True, slots=True)
class CompletedPhaseEvidence:
    """Typed measured preimages consumed by the production packet builder."""

    admitted_pinned_path: str
    admitted_pinned_sha256: str
    topology_sha256: str
    consumed: ConsumedAuthority
    static_preflight_sha256: str
    bench_runtime_identity_sha256: str
    turn_manifest: cm.TurnManifest
    turn_records: tuple[cm.TurnRecord, ...]
    cycle_metrics: tuple[cm.CycleMetrics, cm.CycleMetrics, cm.CycleMetrics]
    cycle_witnesses: tuple[
        cm.CycleBackendWitness,
        cm.CycleBackendWitness,
        cm.CycleBackendWitness,
    ]
    containment_before_sha256: str
    containment_after_sha256: str
    kernel_cursor_before: str
    kernel_cursor_after: str
    kernel_counters: cm.KernelCounters
    cycle_one_before_snapshot_at: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class _PhaseTailEvidence:
    containment_after: cm.ContainmentSnapshot | None
    containment_after_file_sha256: str | None
    kernel_cursor_after: str | None
    kernel_counters: cm.KernelCounters | None
    refusal: BenchRefusal | None


@dataclass(slots=True)
class _PhaseLifecycleState:
    cleanup_incomplete_observer: Callable[[], None] | None = field(
        default=None,
        repr=False,
    )
    interrupted: bool = False
    cleanup_incomplete_latched: bool = False
    cleanup_storage_unavailable: bool = False
    spawned_any: bool = False
    observed_child: OwnedChild | None = None
    current_child: OwnedChild | None = None
    last_finalizer: FinalizeResult | None = None
    active_cycle: int | None = None
    active_memory_before: tuple[float, int] | None = None
    common_topology: str | None = None

    def admit(self, child: OwnedChild) -> None:
        self.current_child = child
        self.observed_child = child
        self.spawned_any = True

    def latch_cleanup_incomplete(self, *, storage_unavailable: bool = False) -> None:
        already_latched = self.cleanup_incomplete_latched
        self.cleanup_incomplete_latched = True
        if storage_unavailable:
            self.cleanup_storage_unavailable = True
        if not already_latched and self.cleanup_incomplete_observer is not None:
            try:
                self.cleanup_incomplete_observer()
            except BaseException:
                pass


@dataclass(slots=True)
class _TerminalCommit:
    path: Path | None = None

    def latch(self, path: Path) -> None:
        if self.path is None:
            self.path = path


@dataclass(frozen=True, slots=True)
class _CompletedCycles:
    manifest_entries: tuple[cm.TurnManifestEntry, ...]
    records: tuple[cm.TurnRecord, ...]
    metrics: tuple[cm.CycleMetrics, cm.CycleMetrics, cm.CycleMetrics]
    witnesses: tuple[
        cm.CycleBackendWitness,
        cm.CycleBackendWitness,
        cm.CycleBackendWitness,
    ]
    topology_groups: tuple[
        tuple[str, str, str, str],
        tuple[str, str, str, str],
        tuple[str, str, str, str],
    ]
    admitted_pin: tuple[str, str]


def _effective_args_sha256(argv: list[str]) -> str:
    if type(argv) is not list or not argv or any(
        type(value) is not str or not value for value in argv
    ):
        raise BenchRefusal("identity_mismatch")
    try:
        encoded = json.dumps(
            argv[1:],
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, TypeError, UnicodeError, ValueError):
        raise BenchRefusal("identity_mismatch") from None
    return hashlib.sha256(encoded).hexdigest()


def _validate_production_execution_contract(
    config: PhaseConfig,
    *,
    launcher: RealServerLauncher,
    static: cm.StaticPreflightDoc,
    runtime_identity: cm.RuntimeIdentity,
) -> ProductionExecutionContract:
    launcher_pin = getattr(launcher, "pin", None)
    if (
        type(config) is not PhaseConfig
        or type(launcher) is not RealServerLauncher
        or type(launcher_pin) is not SpawnPin
        or launcher_pin.kind != "binary"
        or type(static) is not cm.StaticPreflightDoc
        or type(runtime_identity) is not cm.RuntimeIdentity
        or runtime_identity.mode != "bench"
    ):
        raise BenchRefusal("identity_mismatch")
    release_proof = launcher.release_proof
    expected_manifest_sha256 = (
        static.checks["library_manifest"]
        if config.phase == "vulkan_baseline"
        else runtime_identity.runtime_manifest_sha256
    )
    if (
        type(release_proof) is not ReleaseDirectoryProof
        or release_proof.manifest_sha256 != expected_manifest_sha256
    ):
        raise BenchRefusal("spawn_failure")
    expected_path = (
        cm.VULKAN_RELEASE_ROOT / "llama-server"
        if config.phase == "vulkan_baseline"
        else cm.CUDA_RELEASE_ROOT / "llama-server"
    )
    expected_sha256 = (
        static.checks["incumbent_server"]
        if config.phase == "vulkan_baseline"
        else runtime_identity.runtime_sha256
    )
    expected_environment = dict(_PHASE_BENCH_ENVIRONMENTS[config.phase])
    args_sha256 = _effective_args_sha256(config.argv)
    if (
        launcher_pin.pinned_path != expected_path
        or launcher_pin.pinned_sha256 != expected_sha256
        or launcher_pin.required_argv_prefix != (str(expected_path),)
        or config.argv[0] != str(expected_path)
        or tuple(config.argv[1:]) != runtime_identity.effective_args
        or args_sha256 != FROZEN_BENCH_ARGS_SHA256
        or config.env != expected_environment
        or config.expected_port != BENCH_PORT
    ):
        raise BenchRefusal("identity_mismatch")
    if config.phase == "cuda_candidate" and any(
        config.env.get(name) != value
        for name, value in runtime_identity.backend_environment.items()
    ):
        raise BenchRefusal("identity_mismatch")
    try:
        return ProductionExecutionContract(
            pinned_path=str(expected_path),
            pinned_sha256=expected_sha256,
            effective_args_sha256=args_sha256,
            argv=tuple(config.argv),
            environment=expected_environment,
        )
    except (TypeError, ValueError):
        raise BenchRefusal("identity_mismatch") from None


@dataclass(frozen=True, init=False)
class Providers:
    tier: str
    service_state: ServiceStateProvider
    port_probe: PortProbe
    gpu: GpuProvider
    kernel_log: KernelLogProvider
    backend_maps: BackendMapProvider
    server_launcher: ServerLauncher
    server_client: ServerClient
    authorization_gate: AuthorizationGate
    containment: ContainmentProvider
    artifact_policy: ArtifactPolicy
    clock: Clock
    journal_factory: JournalFactory

    def __init__(
        self,
        *,
        tier: str | None = None,
        service_state: ServiceStateProvider,
        port_probe: PortProbe,
        gpu: GpuProvider,
        kernel_log: KernelLogProvider,
        backend_maps: BackendMapProvider,
        server_launcher: ServerLauncher,
        server_client: ServerClient,
        authorization_gate: AuthorizationGate,
        containment: ContainmentProvider,
        artifact_policy: ArtifactPolicy,
        clock: Clock,
        journal_factory: JournalFactory,
        _guard: object | None = None,
    ) -> None:
        if _guard is not _PROVIDERS_GUARD:
            raise TypeError("sealed_provider_factory_required")
        for name, value in locals().copy().items():
            if name not in {"self", "_guard"}:
                object.__setattr__(self, name, value)


def _sealed_tier(
    tier: str,
    *,
    service_state: ServiceStateProvider,
    port_probe: PortProbe,
    gpu: GpuProvider,
    kernel_log: KernelLogProvider,
    backend_maps: BackendMapProvider,
    server_launcher: ServerLauncher,
    server_client: ServerClient,
    authorization_gate: AuthorizationGate,
    containment: ContainmentProvider,
    artifact_policy: ArtifactPolicy,
    clock: Clock,
    journal_factory: JournalFactory,
    _test_guard: object | None = None,
) -> Providers:
    expected_types = (
        {
            "service_state": RealServiceStateProvider,
            "port_probe": RealPortProbe,
            "gpu": RealGpuProvider,
            "kernel_log": RealKernelLogProvider,
            "backend_maps": RealBackendMapProvider,
            "server_launcher": RealServerLauncher,
            "server_client": LoopbackServerClient,
            "authorization_gate": RealAuthorizationGate,
            "containment": RealContainmentProvider,
            "artifact_policy": ProductionArtifactPolicy,
            "clock": SystemClock,
            "journal_factory": ProductionJournalFactory,
        }
        if tier == "production"
        else {
            "service_state": SyntheticServiceState,
            "port_probe": SyntheticPortProbe,
            "gpu": SyntheticGpu,
            "kernel_log": SyntheticKernelLog,
            "backend_maps": SyntheticBackendMap,
            "server_launcher": RehearsalServerLauncher,
            "server_client": LoopbackServerClient,
            "authorization_gate": (
                _TestOnlySingleUseAuthorizationGate
                if _test_guard is _TEST_TIER_GUARD
                else RehearsalAuthorizationGate
            ),
            "containment": SyntheticContainmentProvider,
            "artifact_policy": RehearsalArtifactPolicy,
            "clock": RehearsalClock,
            "journal_factory": RehearsalJournalFactory,
        }
    )
    components = {
        "service_state": service_state,
        "port_probe": port_probe,
        "gpu": gpu,
        "kernel_log": kernel_log,
        "backend_maps": backend_maps,
        "server_launcher": server_launcher,
        "server_client": server_client,
        "authorization_gate": authorization_gate,
        "containment": containment,
        "artifact_policy": artifact_policy,
        "clock": clock,
        "journal_factory": journal_factory,
    }
    if any(type(components[name]) is not expected for name, expected in expected_types.items()):
        raise BenchRefusal("tier_mismatch")
    if server_client.clock is not clock:
        raise BenchRefusal("tier_mismatch")
    if (
        tier == "production"
        and (
            REQUEST_TIMEOUT_MS != 30_000
            or server_client.request_timeout_ms != 30_000
        )
    ):
        raise BenchRefusal("tier_mismatch")
    if getattr(authorization_gate, "policy", None) is not artifact_policy:
        raise BenchRefusal("tier_mismatch")
    if containment.clock is not clock or containment.port_probe is not port_probe:
        raise BenchRefusal("tier_mismatch")
    if tier == "rehearsal":
        launcher_registry = getattr(server_launcher, "rehearsal_ports", None)
        probe_registry = getattr(port_probe, "rehearsal_ports", None)
        if (
            type(launcher_registry) is not RehearsalPortRegistry
            or launcher_registry is not probe_registry
        ):
            raise BenchRefusal("tier_mismatch")
    required_methods = {
        "service_state": ("is_active",),
        "port_probe": ("is_free",),
        "gpu": ("enumerate_uuids", "inventory", "memory"),
        "kernel_log": ("cursor", "count_signatures"),
        "backend_maps": ("read_maps",),
        "server_launcher": ("spawn",),
        "server_client": ("health", "models", "stream"),
        "authorization_gate": ("validate", "consume"),
        "containment": ("capture",),
        "artifact_policy": ("encode", "artifact_dir"),
        "clock": ("now_utc", "monotonic"),
        "journal_factory": ("create",),
    }
    for name, component in components.items():
        component_tier = getattr(component, "tier", None)
        if type(component_tier) is not str or component_tier != tier:
            raise BenchRefusal("tier_mismatch")
        if any(not callable(getattr(component, method, None)) for method in required_methods[name]):
            raise TypeError("provider_protocol_incomplete")
    return Providers(tier=tier, _guard=_PROVIDERS_GUARD, **components)


def _test_rehearsal_tier(**components: object) -> Providers:
    """Seal protocol-complete test components without widening real factories."""

    return _sealed_tier(
        "rehearsal",
        _test_guard=_TEST_TIER_GUARD,
        **components,
    )


def production_tier(
    *,
    service_state: ServiceStateProvider,
    port_probe: PortProbe,
    gpu: GpuProvider,
    kernel_log: KernelLogProvider,
    backend_maps: BackendMapProvider,
    server_launcher: ServerLauncher,
    server_client: ServerClient,
    authorization_gate: AuthorizationGate,
    containment: ContainmentProvider,
    artifact_policy: ArtifactPolicy,
    clock: Clock,
    journal_factory: JournalFactory,
) -> Providers:
    return _sealed_tier(
        "production",
        service_state=service_state,
        port_probe=port_probe,
        gpu=gpu,
        kernel_log=kernel_log,
        backend_maps=backend_maps,
        server_launcher=server_launcher,
        server_client=server_client,
        authorization_gate=authorization_gate,
        containment=containment,
        artifact_policy=artifact_policy,
        clock=clock,
        journal_factory=journal_factory,
    )


def rehearsal_tier(
    *,
    service_state: ServiceStateProvider,
    port_probe: PortProbe,
    gpu: GpuProvider,
    kernel_log: KernelLogProvider,
    backend_maps: BackendMapProvider,
    server_launcher: ServerLauncher,
    server_client: ServerClient,
    authorization_gate: AuthorizationGate,
    containment: ContainmentProvider,
    artifact_policy: ArtifactPolicy,
    clock: Clock,
    journal_factory: JournalFactory,
) -> Providers:
    return _sealed_tier(
        "rehearsal",
        service_state=service_state,
        port_probe=port_probe,
        gpu=gpu,
        kernel_log=kernel_log,
        backend_maps=backend_maps,
        server_launcher=server_launcher,
        server_client=server_client,
        authorization_gate=authorization_gate,
        containment=containment,
        artifact_policy=artifact_policy,
        clock=clock,
        journal_factory=journal_factory,
    )


def _containment_fields(snapshot: cm.ContainmentSnapshot) -> dict[str, object]:
    return {
        "phase": snapshot.phase,
        "boundary": snapshot.boundary,
        "timestamp": snapshot.timestamp,
        "screen_flag_value": snapshot.screen_flag_value,
        "active_state": snapshot.active_state,
        "substate": snapshot.substate,
        "enabled_state": snapshot.enabled_state,
        "port_closed": snapshot.port_closed,
        "flag_source_sha256": snapshot.flag_source_sha256,
        "vision_unit_sha256": snapshot.vision_unit_sha256,
        "maez_active_state": snapshot.maez_active_state,
        "maez_process_screen_flag_value": (
            snapshot.maez_process_screen_flag_value
        ),
    }


def _runtime_identity_fields(identity: cm.RuntimeIdentity) -> dict[str, object]:
    return {
        "tag": identity.tag,
        "commit": identity.commit,
        "version": identity.version,
        "alias": identity.alias,
        "model_sha256": identity.model_sha256,
        "model_bytes": identity.model_bytes,
        "runtime_sha256": identity.runtime_sha256,
        "library_hashes": dict(identity.library_hashes),
        "effective_args": list(identity.effective_args),
        "mode": identity.mode,
        "production_override_sha256": identity.production_override_sha256,
        "backend_environment": dict(identity.backend_environment),
        "runtime_manifest_sha256": identity.runtime_manifest_sha256,
        "rollback_manifest_sha256": identity.rollback_manifest_sha256,
        "cuda_toolkit": identity.cuda_toolkit,
        "cuda_compiler": identity.cuda_compiler,
        "cmake_version": identity.cmake_version,
        "driver_version": identity.driver_version,
        "gpu_identifier": identity.gpu_identifier,
        "compute_capability": identity.compute_capability,
        "backend": identity.backend,
    }


def _turn_record_fields(record: cm.TurnRecord) -> dict[str, object]:
    return {
        name: getattr(record, name)
        for name in (
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
    }


def _cycle_metric_fields(
    metric: cm.CycleMetrics,
    *,
    topology_hashes: tuple[str, str, str, str] | None = None,
) -> dict[str, object]:
    fields = {
        name: getattr(metric, name)
        for name in (
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
    }
    if topology_hashes is not None:
        fields["topology_hashes"] = list(topology_hashes)
    return fields


def _cycle_witness_fields(witness: cm.CycleBackendWitness) -> dict[str, object]:
    return {
        "cycle": witness.cycle,
        "load_started": witness.load_started,
        "unload_proven": witness.unload_proven,
        "witness": {
            "backend": witness.witness.backend,
            "maps_sha256": witness.witness.maps_sha256,
            "phase": witness.witness.phase,
            "timestamp": witness.witness.timestamp,
            "release_root_sha256": witness.witness.release_root_sha256,
        },
    }


def _kernel_counter_fields(counters: cm.KernelCounters) -> dict[str, int]:
    return {
        "reusemappingdb_map": counters.reusemappingdb_map,
        "pmap_cb": counters.pmap_cb,
        "mmu_walk_map": counters.mmu_walk_map,
        "nv_err_no_memory": counters.nv_err_no_memory,
        "xid": counters.xid,
        "unmatched_nvrm": counters.unmatched_nvrm,
    }


def _finalizer_fields(result: FinalizeResult) -> dict[str, object]:
    return {
        "outcome": result.outcome,
        "signals_sent": list(result.signals_sent),
        "quadruple_reproofs": result.quadruple_reproofs,
        "surviving_pgid_members": list(result.surviving_pgid_members),
        "listener_free": result.listener_free,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
    }


def _persist_document(
    *,
    policy: ArtifactPolicy,
    kind: str,
    name: str,
    document: dict[str, object],
    root: Path,
    on_link: Callable[[Path], None] | None = None,
) -> tuple[Path, str]:
    try:
        encoded = policy.encode(kind, document)
        directory = policy.artifact_dir(kind)
    except (TypeError, ValueError):
        raise BenchRefusal("tier_mismatch") from None
    path = write_private_file(
        f"{directory}/{name}",
        encoded,
        root=root,
        on_link=on_link,
    )
    return path, hashlib.sha256(encoded).hexdigest()


def _persist_terminal_document(
    *,
    policy: ArtifactPolicy,
    kind: str,
    name: str,
    document: dict[str, object],
    root: Path,
    terminal: _TerminalCommit,
) -> Path:
    """Latch only after durable publication and anchored identity validation."""

    if terminal.path is not None:
        return terminal.path
    try:
        old_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGINT, signal.SIGTERM},
        )
    except (OSError, ValueError):
        raise BenchRefusal("cleanup_incomplete") from None
    try:
        try:
            path, _file_sha = _persist_document(
                policy=policy,
                kind=kind,
                name=name,
                document=document,
                root=root,
                on_link=terminal.latch,
            )
        except BaseException:
            if terminal.path is not None:
                return terminal.path
            raise
        if terminal.path is None:
            raise BenchRefusal("filesystem_hazard")
        return path
    finally:
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except (OSError, ValueError):
            if terminal.path is None:
                raise BenchRefusal("cleanup_incomplete") from None


def _sample_gpu_stage(
    providers: Providers,
    *,
    gpu_uuid: str,
    owned_pids: set[int],
) -> tuple[str, tuple[float, int]]:
    try:
        inventory = providers.gpu.inventory(gpu_uuid)
        memory = providers.gpu.memory(gpu_uuid)
        topology = ambient_topology_hash(inventory, owned_pids)
    except BenchRefusal:
        raise
    except Exception:
        raise BenchRefusal("provider_uncertain") from None
    return topology, memory


def _kernel_counters(values: dict[str, int]) -> cm.KernelCounters:
    if set(values) != set(KERNEL_COUNTER_KEYS):
        raise BenchRefusal("provider_uncertain")
    try:
        return cm.KernelCounters(
            reusemappingdb_map=values["reusemappingdbMap"],
            pmap_cb=values["pMapCb"],
            mmu_walk_map=values["mmuWalkMap"],
            nv_err_no_memory=values["NV_ERR_NO_MEMORY"],
            xid=values["Xid"],
            unmatched_nvrm=values["unmatched_nvrm"],
        )
    except (TypeError, ValueError):
        raise BenchRefusal("provider_uncertain") from None


def _stage_identities_match(
    bench_identity: cm.RuntimeIdentity,
    runtime_identity: cm.RuntimeIdentity,
) -> bool:
    for name in cm._BENCH_IDENTITY_STABLE_FIELDS:
        bench_value = getattr(bench_identity, name)
        runtime_value = getattr(runtime_identity, name)
        if isinstance(bench_value, Mapping):
            if not isinstance(runtime_value, Mapping) or dict(bench_value) != dict(
                runtime_value
            ):
                return False
        elif bench_value != runtime_value:
            return False
    return True


def _load_verified_completion_pair(
    *,
    admission_ref: str | None,
    completion_ref: str | None,
    artifact_ref: str,
    artifact_bytes: bytes,
    expected_command: str,
    expected_window_id: str | None,
    expected_type: type[object],
    root: Path,
) -> tuple[
    cm.CommandAdmissionPreimage,
    cm.PersistedDoc,
    cm.PersistedDoc,
]:
    if admission_ref is None or completion_ref is None:
        raise BenchRefusal("continuation_parent_mismatch")
    try:
        admission = cm.CommandAdmissionPreimage(
            admission_ref,
            open_bench_file(admission_ref, root=root),
        )
        completion_doc = cm.PersistedDoc(
            open_bench_file(completion_ref, root=root)
        )
        artifact_doc = cm.PersistedDoc(artifact_bytes)
    except (BenchRefusal, TypeError, ValueError):
        raise BenchRefusal("continuation_parent_mismatch") from None
    completion = completion_doc.obj
    if (
        type(completion) is not cm.CommandCompletionDoc
        or type(artifact_doc.obj) is not expected_type
        or admission.command != expected_command
        or completion.command != expected_command
        or completion.ordinal != admission.ordinal
        or completion.window_id != expected_window_id
        or admission.window_id != expected_window_id
        or completion.admission_ref != admission.selected_ref
        or completion.admission_sha256 != admission.file_sha256
        or completion.artifact_ref != artifact_ref
        or completion.artifact_sha256 != artifact_doc.file_sha256
        or completion.artifact_schema
        != (
            cm.STATIC_PREFLIGHT_SCHEMA
            if expected_type is cm.StaticPreflightDoc
            else cm.PHASE_PACKET_SCHEMA
        )
        or cm._compare_utc_z(
            admission.timestamp,
            completion.timestamp,
        )
        >= 0
        or cm._compare_utc_z(
            artifact_doc.obj.timestamp,
            completion.timestamp,
        )
        > 0
    ):
        raise BenchRefusal("continuation_parent_mismatch")
    return admission, completion_doc, artifact_doc


def _load_phase_preimages(
    config: PhaseConfig,
    providers: Providers,
    *,
    root: Path,
    attempt_root: Path,
) -> tuple[
    cm.RuntimeIdentity,
    cm.RuntimeIdentity,
    cm.StaticPreflightDoc,
    cm.PhasePacket | None,
    ParentCompletionEvidence | None,
    str,
    str,
]:
    try:
        static_bytes = open_bench_file(config.static_preflight_path, root=root)
        persisted = cm.PersistedDoc(static_bytes)
        if type(persisted.obj) is not cm.StaticPreflightDoc:
            raise ValueError("static_preflight")
        static = persisted.obj
        bench_identity = cm.RuntimeIdentity(**config.bench_identity_fields)
        runtime_identity = cm.RuntimeIdentity(**config.runtime_identity_fields)
    except BenchRefusal:
        raise
    except (TypeError, ValueError):
        raise BenchRefusal("identity_mismatch") from None
    try:
        canonical_stub_sha256 = _hash_file(_REHEARSAL_STUB_PATH)
    except BenchRefusal:
        raise BenchRefusal("identity_mismatch") from None
    if (
        not _stage_identities_match(bench_identity, runtime_identity)
        or bench_identity.mode != "bench"
        or bench_identity.alias != config.alias
        or runtime_identity.alias != config.alias
        or static.gpu_uuid != config.gpu_uuid
        or static.checks["candidate_manifest"]
        != bench_identity.runtime_manifest_sha256
        or static.stub_sha256 != canonical_stub_sha256
        or (
            providers.tier == "rehearsal"
            and (
                providers.server_launcher.pin.pinned_path  # type: ignore[attr-defined]
                != _REHEARSAL_STUB_PATH
                or providers.server_launcher.pin.pinned_sha256  # type: ignore[attr-defined]
                != static.stub_sha256
            )
        )
    ):
        raise BenchRefusal("identity_mismatch")

    if providers.tier == "production":
        try:
            _load_verified_completion_pair(
                admission_ref=config.static_admission_path,
                completion_ref=config.static_completion_path,
                artifact_ref=config.static_preflight_path,
                artifact_bytes=static_bytes,
                expected_command="static-preflight",
                expected_window_id=None,
                expected_type=cm.StaticPreflightDoc,
                root=root,
            )
        except BenchRefusal:
            raise BenchRefusal("identity_mismatch") from None

    parent_packet: cm.PhasePacket | None = None
    parent_completion: ParentCompletionEvidence | None = None
    parent_bytes: bytes | None = None
    if config.parent_packet_path is not None:
        try:
            parent_bytes = open_bench_file(config.parent_packet_path, root=root)
            parent_packet = cm.decode_persisted_packet(parent_bytes)
        except (BenchRefusal, TypeError, ValueError):
            raise BenchRefusal("continuation_parent_mismatch") from None
    if config.phase == "vulkan_baseline":
        if (
            config.parent_window is not None
            or config.parent_packet_path is not None
            or config.parent_admission_path is not None
            or config.parent_completion_path is not None
        ):
            raise BenchRefusal("continuation_parent_mismatch")
    elif config.parent_window is None or parent_packet is None:
        raise BenchRefusal("continuation_missing")
    elif providers.tier == "production":
        if parent_bytes is None:
            raise BenchRefusal("continuation_parent_mismatch")
        parent_admission, parent_completion_doc, parent_packet_doc = (
            _load_verified_completion_pair(
            admission_ref=config.parent_admission_path,
            completion_ref=config.parent_completion_path,
            artifact_ref=config.parent_packet_path,
            artifact_bytes=parent_bytes,
            expected_command="vulkan-baseline",
            expected_window_id=config.window_id,
            expected_type=cm.PhasePacket,
            root=root,
        )
        )
        if config.parent_packet_path is None:
            raise BenchRefusal("continuation_parent_mismatch")
        parent_completion = ParentCompletionEvidence(
            packet=parent_packet,
            packet_ref=config.parent_packet_path,
            packet_doc=parent_packet_doc,
            admission=parent_admission,
            completion_doc=parent_completion_doc,
        )

    bench_document = {
        "schema": RUNTIME_IDENTITY_SCHEMA,
        "binding_sha256": bench_identity.binding_sha256,
        **_runtime_identity_fields(bench_identity),
    }
    runtime_document = {
        "schema": RUNTIME_IDENTITY_SCHEMA,
        "binding_sha256": runtime_identity.binding_sha256,
        **_runtime_identity_fields(runtime_identity),
    }
    _bench_path, bench_file_sha = _persist_document(
        policy=providers.artifact_policy,
        kind="identity_document",
        name="bench_runtime_identity.json",
        document=bench_document,
        root=attempt_root,
    )
    _runtime_path, _runtime_file_sha = _persist_document(
        policy=providers.artifact_policy,
        kind="identity_document",
        name="runtime_identity.json",
        document=runtime_document,
        root=attempt_root,
    )
    return (
        bench_identity,
        runtime_identity,
        static,
        parent_packet,
        parent_completion,
        hashlib.sha256(static_bytes).hexdigest(),
        bench_file_sha,
    )


def _phase_preflight(
    config: PhaseConfig,
    providers: Providers,
    *,
    parent_packet: cm.PhasePacket | None,
    parent_completion: ParentCompletionEvidence | None,
) -> None:
    try:
        for unit in (
            "llama-server.service",
            "llama-judge.service",
            VISION_UNIT,
        ):
            if providers.service_state.is_active(unit) != "inactive":
                raise BenchRefusal("preflight_service_active")
        for port in PRODUCTION_PORTS:
            if providers.port_probe.is_free(port) is not True:
                raise BenchRefusal("preflight_port_open")
        if providers.port_probe.is_free(BENCH_PORT) is not True:
            raise BenchRefusal("preflight_bench_port_busy")
        uuids = providers.gpu.enumerate_uuids()
        if uuids != [config.gpu_uuid]:
            raise BenchRefusal("gpu_scope_violation")
        inventory = providers.gpu.inventory(config.gpu_uuid)
    except BenchRefusal:
        raise
    except Exception:
        raise BenchRefusal("provider_uncertain") from None
    if any(os.path.basename(name) == "llama-server" for _pid, name in inventory):
        raise BenchRefusal("preflight_gpu_occupied")
    providers.authorization_gate.validate(
        config.authorization,
        phase=config.phase,
        boot_id=config.boot_id,
        expected_window_id=config.window_id,
        parent_window=config.parent_window,
        parent_packet=parent_packet,
        parent_completion=parent_completion,
        clock=providers.clock,
    )


def _persist_containment(
    snapshot: cm.ContainmentSnapshot,
    providers: Providers,
    *,
    attempt_root: Path,
) -> tuple[Path, str]:
    return _persist_document(
        policy=providers.artifact_policy,
        kind="containment_snapshot",
        name=f"containment-{snapshot.boundary}.json",
        document={
            "schema": CONTAINMENT_SNAPSHOT_SCHEMA,
            "binding_sha256": snapshot.binding_sha256,
            **_containment_fields(snapshot),
        },
        root=attempt_root,
    )


def _write_reduced_outcome(
    *,
    config: PhaseConfig,
    providers: Providers,
    attempt_root: Path,
    outcome: str,
    spawned: bool,
    finalizer: FinalizeResult | None,
    observed_child: OwnedChild | None,
    consumed: ConsumedAuthority | None,
    static_preflight_sha256: str | None,
    runtime_identity_sha256: str | None,
    containment_before_sha256: str | None,
    containment_after_sha256: str | None,
    kernel_cursor_before: str | None,
    kernel_cursor_after: str | None,
    kernel_counters: cm.KernelCounters | None,
    terminal: _TerminalCommit,
) -> Path:
    timestamp = _validated_clock_timestamp(providers.clock.now_utc())
    fields: dict[str, object] = {
        "phase": config.phase,
        "window_id": config.window_id,
        "boot_id": config.boot_id,
        "outcome": outcome,
        "spawned": spawned,
        "timestamp": timestamp,
    }
    if observed_child is not None:
        fields.update(
            {
                "observed_port": observed_child.port,
                "observed_pgid": observed_child.pgid,
                "pinned_path": observed_child.pinned_path,
                "pinned_sha256": observed_child.pinned_sha256,
            }
        )
    if finalizer is not None:
        fields["finalizer"] = _finalizer_fields(finalizer)
    if consumed is not None:
        fields["authorization_preimage_sha256"] = consumed.preimage_sha256
        fields["consumption_receipt_sha256"] = (
            consumed.consumption_receipt_sha256
        )
    optional_hashes = {
        "static_preflight_sha256": static_preflight_sha256,
        "runtime_identity_sha256": runtime_identity_sha256,
        "containment_before_sha256": containment_before_sha256,
        "containment_after_sha256": containment_after_sha256,
        "kernel_cursor_before": kernel_cursor_before,
        "kernel_cursor_after": kernel_cursor_after,
    }
    fields.update(
        {name: value for name, value in optional_hashes.items() if value is not None}
    )
    if kernel_counters is not None:
        fields["kernel_counters"] = _kernel_counter_fields(kernel_counters)
    binding = hashlib.sha256(_canonical_json(fields)).hexdigest()
    kind = "packet" if spawned else "refusal"
    path = _persist_terminal_document(
        policy=providers.artifact_policy,
        kind=kind,
        name=f"{config.phase}-{outcome}.json",
        document={"binding_sha256": binding, **fields},
        root=attempt_root,
        terminal=terminal,
    )
    return path


def _write_turn(
    *,
    config: PhaseConfig,
    providers: Providers,
    attempt_root: Path,
    cycle: int,
    ordinal: int,
    prompt: str,
    measurement: TurnMeasurement,
) -> tuple[cm.TurnManifestEntry, cm.TurnRecord]:
    warmup = ordinal == 0
    document = {
        "cycle": cycle,
        "ordinal": ordinal,
        "warmup": warmup,
        "prompt": prompt,
        "content": measurement.content,
        "ttft_ms": measurement.ttft_ms,
        "e2e_ms": measurement.e2e_ms,
        "timings": measurement.timings,
        "terminal": measurement.terminal,
    }
    encoded = providers.artifact_policy.encode("turn_artifact", document)
    directory = providers.artifact_policy.artifact_dir("turn_artifact")
    name = f"cycle-{cycle}-turn-{ordinal}.json"
    write_private_file(f"{directory}/{name}", encoded, root=attempt_root)
    artifact_sha = hashlib.sha256(encoded).hexdigest()
    timings = measurement.timings
    try:
        prompt_rate = float(timings["prompt_per_second"])
        predicted_rate = float(timings["predicted_per_second"])
    except (KeyError, OverflowError, TypeError, ValueError):
        raise BenchRefusal("malformed_response") from None
    if warmup:
        draft_n = None
        accepted = None
    else:
        draft_n, accepted, _rejected = parse_mtp(timings)
    try:
        entry = cm.TurnManifestEntry(cycle, ordinal, warmup, artifact_sha)
        record = cm.TurnRecord(
            cycle=cycle,
            ordinal=ordinal,
            warmup=warmup,
            artifact_sha256=artifact_sha,
            outcome="completed",
            e2e_ms=float(measurement.e2e_ms),
            ttft_ms=float(measurement.ttft_ms),
            prompt_per_second=prompt_rate,
            predicted_per_second=predicted_rate,
            draft_n=draft_n,
            draft_n_accepted=accepted,
        )
    except (TypeError, ValueError):
        raise BenchRefusal("malformed_response") from None
    return entry, record


def _authorization_attempt_window(config: PhaseConfig) -> str:
    authority = config.authorization
    expected_type = (
        WindowAuthorization
        if config.phase == "vulkan_baseline"
        else Continuation
    )
    if (
        type(authority) is not expected_type
        or config.phase not in authority.phases
        or authority.window_id != config.window_id
    ):
        raise BenchRefusal("authorization_scope_mismatch")
    if authority.boot_id != config.boot_id:
        raise BenchRefusal("authorization_boot_mismatch")
    return authority.window_id


def _summary_projection(
    *,
    phase: str,
    model_sha256: str,
    metrics: tuple[cm.CycleMetrics, cm.CycleMetrics, cm.CycleMetrics],
    records: tuple[cm.TurnRecord, ...],
    counters: cm.KernelCounters,
) -> str:
    statistics_packet = cm.recompute_phase_statistics(records)
    unload_leak = sum(
        max(0, metric.vram_after_unload_mib - metric.vram_before_mib)
        for metric in metrics
    )
    projection = {
        "phase": phase,
        "alias": cm.FROZEN_ALIAS,
        "model_sha256": model_sha256,
        "corpus_sha256": cm.FROZEN_CORPUS_SHA256,
        "order_sha256": cm.FROZEN_ORDER_SHA256,
        "sample_n": cm.FROZEN_SAMPLE_N,
        "warmup_count": cm.FROZEN_WARMUP_COUNT,
        "measured_sample_count": cm.FROZEN_MEASURED_SAMPLE_COUNT,
        "load_cycles": cm.FROZEN_LOAD_CYCLES,
        "cycles": [cm._cycle_packet(metric) for metric in metrics],
        "unload_leak_mib": float(unload_leak),
        "kernel_counters": counters.packet(),
        **statistics_packet,
    }
    return cm._canonical_projection_json(projection)


def _phase_packet_fields(packet: cm.PhasePacket) -> dict[str, object]:
    return {
        "phase": packet.phase,
        "outcome": packet.outcome,
        "window_id": packet.window_id,
        "boot_id": packet.boot_id,
        "gpu_uuid": packet.gpu_uuid,
        "topology_sha256": packet.topology_sha256,
        "model_sha256": packet.model_sha256,
        "corpus_sha256": packet.corpus_sha256,
        "order_sha256": packet.order_sha256,
        "effective_args_sha256": packet.effective_args_sha256,
        "driver_package_sha256": packet.driver_package_sha256,
        "pinned_path": packet.pinned_path,
        "pinned_sha256": packet.pinned_sha256,
        "authorization_preimage_sha256": packet.authorization_preimage_sha256,
        "consumption_receipt_sha256": packet.consumption_receipt_sha256,
        "static_preflight_sha256": packet.static_preflight_sha256,
        "runtime_identity_sha256": packet.runtime_identity_sha256,
        "turn_manifest": {
            "phase": packet.turn_manifest.phase,
            "entries": [
                [entry.cycle, entry.ordinal, entry.warmup, entry.artifact_sha256]
                for entry in packet.turn_manifest.entries
            ],
        },
        "turn_records": [
            _turn_record_fields(record) for record in packet.turn_records
        ],
        "cycle_metrics": [
            _cycle_metric_fields(metric) for metric in packet.cycle_metrics
        ],
        "cycle_witnesses": [
            _cycle_witness_fields(witness) for witness in packet.cycle_witnesses
        ],
        "containment_before_sha256": packet.containment_before_sha256,
        "containment_after_sha256": packet.containment_after_sha256,
        "kernel_cursor_before": packet.kernel_cursor_before,
        "kernel_cursor_after": packet.kernel_cursor_after,
        "kernel_counters": _kernel_counter_fields(packet.kernel_counters),
        "summary_projection_json": packet.summary_projection_json,
        "cycle_one_before_snapshot_at": packet.cycle_one_before_snapshot_at,
        "timestamp": packet.timestamp,
    }


def _build_completed_phase_packet(
    *,
    config: PhaseConfig,
    execution_contract: ProductionExecutionContract,
    runtime_identity: cm.RuntimeIdentity,
    static: cm.StaticPreflightDoc,
    evidence: CompletedPhaseEvidence,
) -> cm.PhasePacket:
    """Build one production packet only from admitted execution and typed evidence."""

    if (
        type(config) is not PhaseConfig
        or type(execution_contract) is not ProductionExecutionContract
        or type(runtime_identity) is not cm.RuntimeIdentity
        or type(static) is not cm.StaticPreflightDoc
        or type(evidence) is not CompletedPhaseEvidence
    ):
        raise BenchRefusal("identity_mismatch")
    expected_path = str(
        (
            cm.VULKAN_RELEASE_ROOT
            if config.phase == "vulkan_baseline"
            else cm.CUDA_RELEASE_ROOT
        )
        / "llama-server"
    )
    expected_sha256 = (
        static.checks["incumbent_server"]
        if config.phase == "vulkan_baseline"
        else runtime_identity.runtime_sha256
    )
    if (
        execution_contract.pinned_path != expected_path
        or execution_contract.pinned_sha256 != expected_sha256
        or evidence.admitted_pinned_path != execution_contract.pinned_path
        or evidence.admitted_pinned_sha256 != execution_contract.pinned_sha256
        or execution_contract.effective_args_sha256 != FROZEN_BENCH_ARGS_SHA256
        or config.expected_port != BENCH_PORT
    ):
        raise BenchRefusal("identity_mismatch")
    try:
        return cm.PhasePacket(
            phase=config.phase,
            outcome="completed",
            window_id=config.window_id,
            boot_id=config.boot_id,
            gpu_uuid=config.gpu_uuid,
            topology_sha256=evidence.topology_sha256,
            model_sha256=runtime_identity.model_sha256,
            corpus_sha256=cm.FROZEN_CORPUS_SHA256,
            order_sha256=cm.FROZEN_ORDER_SHA256,
            effective_args_sha256=execution_contract.effective_args_sha256,
            driver_package_sha256=static.driver_package_sha256,
            pinned_path=execution_contract.pinned_path,
            pinned_sha256=execution_contract.pinned_sha256,
            authorization_preimage_sha256=evidence.consumed.preimage_sha256,
            consumption_receipt_sha256=(
                evidence.consumed.consumption_receipt_sha256
            ),
            static_preflight_sha256=evidence.static_preflight_sha256,
            runtime_identity_sha256=evidence.bench_runtime_identity_sha256,
            turn_manifest=evidence.turn_manifest,
            turn_records=evidence.turn_records,
            cycle_metrics=evidence.cycle_metrics,
            cycle_witnesses=evidence.cycle_witnesses,
            containment_before_sha256=evidence.containment_before_sha256,
            containment_after_sha256=evidence.containment_after_sha256,
            kernel_cursor_before=evidence.kernel_cursor_before,
            kernel_cursor_after=evidence.kernel_cursor_after,
            kernel_counters=evidence.kernel_counters,
            summary_projection_json=_summary_projection(
                phase=config.phase,
                model_sha256=runtime_identity.model_sha256,
                metrics=evidence.cycle_metrics,
                records=evidence.turn_records,
                counters=evidence.kernel_counters,
            ),
            cycle_one_before_snapshot_at=evidence.cycle_one_before_snapshot_at,
            timestamp=evidence.timestamp,
        )
    except (TypeError, ValueError):
        raise BenchRefusal("provider_uncertain") from None


def _append_phase_transition(
    journal: PhaseJournal,
    clock: Clock,
    transition: str,
    *,
    detail: Mapping[str, object] | None = None,
) -> None:
    journal.append(
        ts=_validated_clock_timestamp(clock.now_utc()),
        transition=transition,
        detail={} if detail is None else detail,
    )


def _try_append_phase_transition(
    journal: PhaseJournal,
    clock: Clock,
    transition: str,
    *,
    detail: Mapping[str, object] | None = None,
) -> BenchRefusal | None:
    try:
        _append_phase_transition(
            journal,
            clock,
            transition,
            detail=detail,
        )
    except (BenchRefusal, ValueError):
        return BenchRefusal("journal_failure")
    return None


def _dispose_binary_spawn_failure(
    failure: _BinarySpawnFailure,
    *,
    journal: PhaseJournal,
    clock: Clock,
    cycle: int,
    attempt_root: Path,
    on_cleanup_incomplete: _CleanupIncompleteLatch | None = None,
) -> NoReturn:
    """Record fixed process cleanup before retiring one failed capture."""

    if type(failure) is not _BinarySpawnFailure or type(cycle) is not int:
        raise BenchRefusal("cleanup_incomplete")
    if failure.code == "cleanup_incomplete" and on_cleanup_incomplete is not None:
        on_cleanup_incomplete()
    journal_failed = False
    try:
        _append_phase_transition(
            journal,
            clock,
            f"cycle_{cycle}_bootstrap_cleanup",
            detail={"outcome": failure._bootstrap_cleanup.outcome},
        )
    except BaseException:
        journal_failed = True
        if on_cleanup_incomplete is not None:
            on_cleanup_incomplete(storage_unavailable=True)
    if journal_failed:
        _retire_binary_stderr_capture(
            failure._stderr_capture,
            on_cleanup_incomplete=on_cleanup_incomplete,
        )
        raise _StorageIndependentCleanupIncomplete from None
    _dispose_binary_stderr_diagnostic(
        failure._stderr_capture,
        journal=journal,
        clock=clock,
        cycle=cycle,
        attempt_root=attempt_root,
        returncode=failure._bootstrap_cleanup.observed_returncode,
        exited_before_finalize=(
            failure._bootstrap_cleanup.exited_before_cleanup_signal
        ),
        on_cleanup_incomplete=on_cleanup_incomplete,
    )
    raise BenchRefusal(failure.code) from None


def _spawn_with_interrupt_handoff(
    launcher: ServerLauncher,
    argv: list[str],
    env: dict[str, str],
    *,
    admit: Callable[[OwnedChild], None],
    journal: PhaseJournal,
    clock: Clock,
    cycle: int,
    attempt_root: Path,
    on_cleanup_incomplete: _CleanupIncompleteLatch | None = None,
) -> OwnedChild:
    """Block driver interrupts until the caller has recorded child ownership."""

    try:
        old_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGINT, signal.SIGTERM},
        )
    except (OSError, ValueError):
        raise BenchRefusal("spawn_failure") from None
    try:
        try:
            child = launcher.spawn(argv, env)
        except _BinarySpawnFailure as failure:
            _dispose_binary_spawn_failure(
                failure,
                journal=journal,
                clock=clock,
                cycle=cycle,
                attempt_root=attempt_root,
                on_cleanup_incomplete=on_cleanup_incomplete,
            )
        if type(child) is not OwnedChild:
            raise BenchRefusal("spawn_failure")
        admit(child)
    finally:
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        except (OSError, ValueError):
            raise BenchRefusal("cleanup_incomplete") from None
    return child


def _resolved_cycle_failure(
    pending: BaseException | None,
    finalizer: FinalizeResult,
    *,
    child_exited_before_finalize: bool,
    unload_refusal: BenchRefusal | None,
    interrupted: bool,
) -> BenchRefusal | None:
    if finalizer.outcome != "clean":
        return BenchRefusal(finalizer.outcome)
    if interrupted or isinstance(pending, KeyboardInterrupt):
        return BenchRefusal("interrupted")
    if "SIGKILL" in finalizer.signals_sent:
        return BenchRefusal("hang")
    if unload_refusal is not None:
        return unload_refusal
    if pending is None:
        return None
    if isinstance(pending, BenchRefusal):
        if pending.code == "malformed_response" and child_exited_before_finalize:
            return BenchRefusal("crash")
        return pending
    return BenchRefusal("provider_uncertain")


def _wait_for_unload(
    providers: Providers,
    *,
    gpu_uuid: str,
    memory_before: tuple[float, int],
    expected_topology: str,
    listener_free: bool | None,
) -> tuple[str, tuple[float, int]]:
    if listener_free is not True:
        raise BenchRefusal("unload_incomplete")
    deadline = _monotonic(providers.clock) + UNLOAD_WAIT_S
    while True:
        topology, memory = _sample_gpu_stage(
            providers,
            gpu_uuid=gpu_uuid,
            owned_pids=set(),
        )
        if topology != expected_topology:
            raise BenchRefusal("topology_drift")
        if memory[0] <= memory_before[0] and memory[1] <= memory_before[1]:
            return topology, memory
        if _monotonic(providers.clock) >= deadline:
            raise BenchRefusal("unload_incomplete")
        time.sleep(0.01)


def _collect_phase_tail(
    *,
    config: PhaseConfig,
    providers: Providers,
    attempt_root: Path,
    static: cm.StaticPreflightDoc,
    containment_before: cm.ContainmentSnapshot,
    kernel_cursor_before: str,
    journal: PhaseJournal,
) -> _PhaseTailEvidence:
    refusal: BenchRefusal | None = None
    cursor_after: str | None = None
    counters: cm.KernelCounters | None = None
    containment_after: cm.ContainmentSnapshot | None = None
    containment_after_file_sha: str | None = None

    journal_refusal = _try_append_phase_transition(
        journal,
        providers.clock,
        "kernel_delta",
    )
    if journal_refusal is not None:
        refusal = journal_refusal
    try:
        cursor_after = providers.kernel_log.cursor()
        counters = _kernel_counters(
            providers.kernel_log.count_signatures(
                kernel_cursor_before,
                cursor_after,
            )
        )
        if not counters.clean:
            refusal = BenchRefusal("kernel_unmatched")
    except BenchRefusal as error:
        refusal = error
    except Exception:
        refusal = BenchRefusal("provider_uncertain")

    journal_refusal = _try_append_phase_transition(
        journal,
        providers.clock,
        "containment_after",
    )
    if refusal is None and journal_refusal is not None:
        refusal = journal_refusal
    try:
        containment_after = providers.containment.capture(config.phase, "after")
        _after_path, containment_after_file_sha = _persist_containment(
            containment_after,
            providers,
            attempt_root=attempt_root,
        )
        if (
            not containment_after.clean
            or containment_after.flag_source_sha256
            != static.checks["flag_source"]
            or containment_after.vision_unit_sha256
            != static.checks["vision_unit"]
            or containment_after.flag_source_sha256
            != containment_before.flag_source_sha256
            or containment_after.vision_unit_sha256
            != containment_before.vision_unit_sha256
        ):
            refusal = BenchRefusal("containment_violation")
    except BenchRefusal as error:
        if refusal is None or error.code == "containment_violation":
            refusal = error
    except Exception:
        if refusal is None:
            refusal = BenchRefusal("provider_uncertain")
    if providers.tier == "production":
        try:
            launcher = providers.server_launcher
            if type(launcher) is not RealServerLauncher:
                raise BenchRefusal("spawn_failure")
            launcher.verify_release_directory()
        except BenchRefusal as error:
            if refusal is None:
                refusal = error
        except Exception:
            if refusal is None:
                refusal = BenchRefusal("spawn_failure")
    return _PhaseTailEvidence(
        containment_after=containment_after,
        containment_after_file_sha256=containment_after_file_sha,
        kernel_cursor_after=cursor_after,
        kernel_counters=counters,
        refusal=refusal,
    )


def _run_three_cycles(
    *,
    config: PhaseConfig,
    providers: Providers,
    attempt_root: Path,
    journal: PhaseJournal,
    lifecycle: _PhaseLifecycleState,
    admitted_argv: tuple[str, ...],
    admitted_env: Mapping[str, str],
    expected_pin: tuple[str, str],
    before_topology: str,
    before_memory: tuple[float, int],
) -> _CompletedCycles:
    """Run exactly three identical-pin cycles and return measured preimages."""

    manifest_entries: list[cm.TurnManifestEntry] = []
    records: list[cm.TurnRecord] = []
    metrics: list[cm.CycleMetrics] = []
    witnesses: list[cm.CycleBackendWitness] = []
    topology_groups: list[tuple[str, str, str, str]] = []
    common_pin: tuple[str, str] | None = None
    lifecycle.common_topology = before_topology

    for cycle in (1, 2, 3):
        lifecycle.active_cycle = cycle
        _append_phase_transition(
            journal,
            providers.clock,
            f"cycle_{cycle}_before",
        )
        if cycle == 1:
            topology_before, memory_before = before_topology, before_memory
        else:
            topology_before, memory_before = _sample_gpu_stage(
                providers,
                gpu_uuid=config.gpu_uuid,
                owned_pids=set(),
            )
        if topology_before != lifecycle.common_topology:
            raise BenchRefusal("topology_drift")
        lifecycle.active_memory_before = memory_before

        _append_phase_transition(
            journal,
            providers.clock,
            f"cycle_{cycle}_load",
        )
        load_started = _validated_clock_timestamp(providers.clock.now_utc())
        child = _spawn_with_interrupt_handoff(
            providers.server_launcher,
            list(admitted_argv),
            dict(admitted_env),
            admit=lifecycle.admit,
            journal=journal,
            clock=providers.clock,
            cycle=cycle,
            attempt_root=attempt_root,
            on_cleanup_incomplete=lifecycle.latch_cleanup_incomplete,
        )
        if providers.tier == "production":
            if config.expected_port != BENCH_PORT or child.port != BENCH_PORT:
                raise BenchRefusal("identity_mismatch")
        elif (
            config.expected_port is not None
            or child.port is None
            or child.port == BENCH_PORT
        ):
            raise BenchRefusal("identity_mismatch")
        child_pin = (child.pinned_path, child.pinned_sha256)
        if child_pin != expected_pin:
            raise BenchRefusal("identity_mismatch")
        if common_pin is None:
            common_pin = child_pin
        elif child_pin != common_pin:
            raise BenchRefusal("identity_mismatch")

        pending: BaseException | None = None
        topology_after_load = ""
        topology_after_inference = ""
        memory_after_load: tuple[float, int] = (0.0, 0)
        memory_after_inference: tuple[float, int] = (0.0, 0)
        runtime_witness: cm.RuntimeBackendWitness | None = None
        child_exited_before_finalize = False
        try:
            _append_phase_transition(
                journal,
                providers.clock,
                f"cycle_{cycle}_readiness",
            )
            deadline = (
                _monotonic(providers.clock) + config.readiness_timeout_s
            )
            while True:
                if providers.server_client.health(child.port):
                    break
                if child.popen.poll() is not None:
                    raise BenchRefusal("crash")
                if _monotonic(providers.clock) >= deadline:
                    raise BenchRefusal("readiness_timeout")
                time.sleep(0.01)
            _append_phase_transition(
                journal,
                providers.clock,
                f"cycle_{cycle}_alias",
            )
            if providers.server_client.models(child.port) != [config.alias]:
                raise BenchRefusal("alias_mismatch")
            _append_phase_transition(
                journal,
                providers.clock,
                f"cycle_{cycle}_backend_witness",
            )
            witness_at = _validated_clock_timestamp(providers.clock.now_utc())
            try:
                runtime_witness = cm.RuntimeBackendWitness.from_proc_maps(
                    providers.backend_maps.read_maps(child.pid),
                    phase=config.phase,
                    timestamp=witness_at,
                )
            except BenchRefusal:
                raise
            except (TypeError, ValueError):
                raise BenchRefusal("backend_unproven") from None
            _append_phase_transition(
                journal,
                providers.clock,
                f"cycle_{cycle}_after_load",
            )
            topology_after_load, memory_after_load = _sample_gpu_stage(
                providers,
                gpu_uuid=config.gpu_uuid,
                owned_pids={child.pid},
            )
            if topology_after_load != lifecycle.common_topology:
                raise BenchRefusal("topology_drift")

            turn_prompts = (config.prompts[0], *config.prompts)
            for ordinal, prompt in enumerate(turn_prompts):
                _append_phase_transition(
                    journal,
                    providers.clock,
                    (
                        f"cycle_{cycle}_warmup"
                        if ordinal == 0
                        else f"cycle_{cycle}_measured_{ordinal}"
                    ),
                )
                measurement = providers.server_client.stream(child.port, prompt)
                if lifecycle.interrupted:
                    raise BenchRefusal("interrupted")
                entry, record = _write_turn(
                    config=config,
                    providers=providers,
                    attempt_root=attempt_root,
                    cycle=cycle,
                    ordinal=ordinal,
                    prompt=prompt,
                    measurement=measurement,
                )
                manifest_entries.append(entry)
                records.append(record)
            _append_phase_transition(
                journal,
                providers.clock,
                f"cycle_{cycle}_after_inference",
            )
            topology_after_inference, memory_after_inference = _sample_gpu_stage(
                providers,
                gpu_uuid=config.gpu_uuid,
                owned_pids={child.pid},
            )
            if topology_after_inference != lifecycle.common_topology:
                raise BenchRefusal("topology_drift")
        except BaseException as exc:
            pending = exc
        finally:
            child_exited_before_finalize = child.popen.poll() is not None
            lifecycle.last_finalizer = finalize(
                child,
                clock=providers.clock,
                port_probe=providers.port_probe,
                port=child.port,
            )
            observed_returncode = child.popen.returncode

        unload_refusal: BenchRefusal | None = None
        try:
            topology_after_unload, memory_after_unload = _wait_for_unload(
                providers,
                gpu_uuid=config.gpu_uuid,
                memory_before=memory_before,
                expected_topology=lifecycle.common_topology,
                listener_free=lifecycle.last_finalizer.listener_free,
            )
        except BenchRefusal as error:
            unload_refusal = error
            topology_after_unload = lifecycle.common_topology
            memory_after_unload = memory_before
        lifecycle.current_child = None
        try:
            finalize_journal_error = _try_append_phase_transition(
                journal,
                providers.clock,
                f"cycle_{cycle}_finalize",
                detail=_finalizer_fields(lifecycle.last_finalizer),
            )
        except BaseException:
            _retire_binary_stderr_capture(
                child._stderr_capture,
                on_cleanup_incomplete=lifecycle.latch_cleanup_incomplete,
            )
            raise
        if finalize_journal_error is not None:
            _retire_binary_stderr_capture(
                child._stderr_capture,
                on_cleanup_incomplete=lifecycle.latch_cleanup_incomplete,
            )
            raise finalize_journal_error
        _dispose_binary_stderr_diagnostic(
            child._stderr_capture,
            journal=journal,
            clock=providers.clock,
            cycle=cycle,
            attempt_root=attempt_root,
            returncode=observed_returncode,
            exited_before_finalize=child_exited_before_finalize,
            on_cleanup_incomplete=lifecycle.latch_cleanup_incomplete,
        )
        _append_phase_transition(
            journal,
            providers.clock,
            f"cycle_{cycle}_after_unload",
            detail={
                "outcome": (
                    "completed" if unload_refusal is None else unload_refusal.code
                )
            },
        )
        resolved_failure = _resolved_cycle_failure(
            pending,
            lifecycle.last_finalizer,
            child_exited_before_finalize=child_exited_before_finalize,
            unload_refusal=unload_refusal,
            interrupted=lifecycle.interrupted,
        )
        if resolved_failure is not None:
            raise resolved_failure
        if runtime_witness is None:
            raise BenchRefusal("backend_unproven")

        topology_group = (
            topology_before,
            topology_after_load,
            topology_after_inference,
            topology_after_unload,
        )
        if any(value != lifecycle.common_topology for value in topology_group):
            raise BenchRefusal("topology_drift")
        unload_proven = _validated_clock_timestamp(providers.clock.now_utc())
        try:
            metrics.append(
                cm.CycleMetrics(
                    cycle=cycle,
                    topology_sha256=lifecycle.common_topology,
                    bar1_before_percent=memory_before[0],
                    bar1_after_load_percent=memory_after_load[0],
                    bar1_after_inference_percent=memory_after_inference[0],
                    bar1_after_unload_percent=memory_after_unload[0],
                    vram_before_mib=memory_before[1],
                    vram_after_load_mib=memory_after_load[1],
                    vram_after_inference_mib=memory_after_inference[1],
                    vram_after_unload_mib=memory_after_unload[1],
                )
            )
            witnesses.append(
                cm.CycleBackendWitness(
                    witness=runtime_witness,
                    cycle=cycle,
                    load_started=load_started,
                    unload_proven=unload_proven,
                )
            )
        except (TypeError, ValueError):
            raise BenchRefusal("provider_uncertain") from None
        topology_groups.append(topology_group)

    if common_pin is None:
        raise BenchRefusal("identity_mismatch")
    return _CompletedCycles(
        manifest_entries=tuple(manifest_entries),
        records=tuple(records),
        metrics=(metrics[0], metrics[1], metrics[2]),
        witnesses=(witnesses[0], witnesses[1], witnesses[2]),
        topology_groups=(
            topology_groups[0],
            topology_groups[1],
            topology_groups[2],
        ),
        admitted_pin=common_pin,
    )


def _publish_completed_phase(
    *,
    config: PhaseConfig,
    providers: Providers,
    attempt_root: Path,
    journal: PhaseJournal,
    lifecycle: _PhaseLifecycleState,
    execution_contract: ProductionExecutionContract | None,
    runtime_identity: cm.RuntimeIdentity,
    static: cm.StaticPreflightDoc,
    completed_cycles: _CompletedCycles,
    consumed: ConsumedAuthority,
    static_file_sha256: str,
    bench_identity_file_sha256: str,
    containment_before_sha256: str,
    tail: _PhaseTailEvidence,
    kernel_cursor_before: str,
    cycle_one_before_at: str,
    effective_args_sha256: str,
    terminal: _TerminalCommit,
) -> Path:
    """Construct and publish the one terminal completed artifact."""

    if (
        tail.containment_after_file_sha256 is None
        or tail.kernel_cursor_after is None
        or tail.kernel_counters is None
        or lifecycle.common_topology is None
    ):
        raise BenchRefusal("provider_uncertain")
    containment_after_sha = tail.containment_after_file_sha256
    kernel_cursor_after = tail.kernel_cursor_after
    counters = tail.kernel_counters
    common_pin = completed_cycles.admitted_pin
    manifest = cm.TurnManifest(config.phase, completed_cycles.manifest_entries)
    completed_at = _validated_clock_timestamp(providers.clock.now_utc())

    if providers.tier == "production":
        if execution_contract is None:
            raise BenchRefusal("identity_mismatch")
        packet = _build_completed_phase_packet(
            config=config,
            execution_contract=execution_contract,
            runtime_identity=runtime_identity,
            static=static,
            evidence=CompletedPhaseEvidence(
                admitted_pinned_path=common_pin[0],
                admitted_pinned_sha256=common_pin[1],
                topology_sha256=lifecycle.common_topology,
                consumed=consumed,
                static_preflight_sha256=static_file_sha256,
                bench_runtime_identity_sha256=bench_identity_file_sha256,
                turn_manifest=manifest,
                turn_records=completed_cycles.records,
                cycle_metrics=completed_cycles.metrics,
                cycle_witnesses=completed_cycles.witnesses,
                containment_before_sha256=containment_before_sha256,
                containment_after_sha256=containment_after_sha,
                kernel_cursor_before=kernel_cursor_before,
                kernel_cursor_after=kernel_cursor_after,
                kernel_counters=counters,
                cycle_one_before_snapshot_at=cycle_one_before_at,
                timestamp=completed_at,
            ),
        )
        packet_fields = _phase_packet_fields(packet)
        binding = packet.binding_sha256
    else:
        packet_fields = {
            "phase": config.phase,
            "outcome": "completed",
            "window_id": config.window_id,
            "boot_id": config.boot_id,
            "gpu_uuid": config.gpu_uuid,
            "topology_sha256": lifecycle.common_topology,
            "model_sha256": runtime_identity.model_sha256,
            "corpus_sha256": cm.FROZEN_CORPUS_SHA256,
            "order_sha256": cm.FROZEN_ORDER_SHA256,
            "effective_args_sha256": effective_args_sha256,
            "driver_package_sha256": static.driver_package_sha256,
            "pinned_path": common_pin[0],
            "pinned_sha256": common_pin[1],
            "authorization_preimage_sha256": consumed.preimage_sha256,
            "consumption_receipt_sha256": consumed.consumption_receipt_sha256,
            "static_preflight_sha256": static_file_sha256,
            "runtime_identity_sha256": bench_identity_file_sha256,
            "turn_manifest": {
                "phase": config.phase,
                "entries": [
                    [entry.cycle, entry.ordinal, entry.warmup, entry.artifact_sha256]
                    for entry in manifest.entries
                ],
            },
            "turn_records": [
                _turn_record_fields(record) for record in completed_cycles.records
            ],
            "cycle_metrics": [
                _cycle_metric_fields(metric, topology_hashes=topologies)
                for metric, topologies in zip(
                    completed_cycles.metrics,
                    completed_cycles.topology_groups,
                    strict=True,
                )
            ],
            "cycle_witnesses": [
                _cycle_witness_fields(witness)
                for witness in completed_cycles.witnesses
            ],
            "containment_before_sha256": containment_before_sha256,
            "containment_after_sha256": containment_after_sha,
            "kernel_cursor_before": kernel_cursor_before,
            "kernel_cursor_after": kernel_cursor_after,
            "kernel_counters": _kernel_counter_fields(counters),
            "cycle_one_before_snapshot_at": cycle_one_before_at,
            "timestamp": completed_at,
        }
        binding = hashlib.sha256(_canonical_json(packet_fields)).hexdigest()

    _append_phase_transition(journal, providers.clock, "packet_write")
    journal.append(ts=completed_at, transition="completed", detail={})
    journal.close()
    packet_path, _packet_file_sha256 = _persist_document(
        policy=providers.artifact_policy,
        kind="packet",
        name=f"{config.phase}-completed.json",
        document={"binding_sha256": binding, **packet_fields},
        root=attempt_root,
    )
    return packet_path


def _finish_failed_phase(
    trigger: BaseException,
    *,
    config: PhaseConfig,
    providers: Providers,
    attempt_root: Path,
    journal: PhaseJournal,
    lifecycle: _PhaseLifecycleState,
    static: cm.StaticPreflightDoc | None,
    containment_before: cm.ContainmentSnapshot | None,
    kernel_cursor_before: str | None,
    tail_evidence: _PhaseTailEvidence | None,
    consumed: ConsumedAuthority | None,
    static_file_sha256: str | None,
    bench_identity_file_sha256: str | None,
    containment_before_file_sha256: str | None,
    terminal: _TerminalCommit,
) -> Path:
    """Finish owned work, collect the observable tail, and publish one failure."""

    if lifecycle.cleanup_incomplete_latched:
        outcome = "cleanup_incomplete"
    elif lifecycle.interrupted or isinstance(trigger, KeyboardInterrupt):
        outcome = "interrupted"
    elif isinstance(trigger, BenchRefusal):
        outcome = trigger.code
    else:
        outcome = "provider_uncertain"

    if lifecycle.cleanup_storage_unavailable:
        raise _StorageIndependentCleanupIncomplete from None

    if lifecycle.current_child is not None:
        child = lifecycle.current_child
        lifecycle.observed_child = child
        lifecycle.spawned_any = True
        child_exited = child.popen.poll() is not None
        lifecycle.last_finalizer = finalize(
            child,
            clock=providers.clock,
            port_probe=providers.port_probe,
            port=child.port,
        )
        observed_returncode = child.popen.returncode
        if lifecycle.active_cycle is not None:
            unload_refusal: BenchRefusal | None = None
            if (
                lifecycle.active_memory_before is not None
                and lifecycle.common_topology is not None
            ):
                try:
                    _wait_for_unload(
                        providers,
                        gpu_uuid=config.gpu_uuid,
                        memory_before=lifecycle.active_memory_before,
                        expected_topology=lifecycle.common_topology,
                        listener_free=lifecycle.last_finalizer.listener_free,
                    )
                except BenchRefusal as error:
                    unload_refusal = error
            lifecycle.current_child = None
            try:
                journal_error = _try_append_phase_transition(
                    journal,
                    providers.clock,
                    f"cycle_{lifecycle.active_cycle}_finalize",
                    detail=_finalizer_fields(lifecycle.last_finalizer),
                )
            except BaseException:
                _retire_binary_stderr_capture(
                    child._stderr_capture,
                    on_cleanup_incomplete=(
                        lifecycle.latch_cleanup_incomplete
                    ),
                )
                raise
            diagnostic_refusal: BenchRefusal | None = None
            if journal_error is None:
                try:
                    _dispose_binary_stderr_diagnostic(
                        child._stderr_capture,
                        journal=journal,
                        clock=providers.clock,
                        cycle=lifecycle.active_cycle,
                        attempt_root=attempt_root,
                        returncode=observed_returncode,
                        exited_before_finalize=child_exited,
                        on_cleanup_incomplete=(
                            lifecycle.latch_cleanup_incomplete
                        ),
                    )
                except BenchRefusal as error:
                    diagnostic_refusal = error
            else:
                try:
                    _retire_binary_stderr_capture(
                        child._stderr_capture,
                        on_cleanup_incomplete=(
                            lifecycle.latch_cleanup_incomplete
                        ),
                    )
                except BenchRefusal as error:
                    diagnostic_refusal = error
            unload_journal_error = _try_append_phase_transition(
                journal,
                providers.clock,
                f"cycle_{lifecycle.active_cycle}_after_unload",
                detail={
                    "outcome": (
                        "completed" if unload_refusal is None else unload_refusal.code
                    )
                },
            )
            if journal_error is None:
                journal_error = unload_journal_error
            resolved = _resolved_cycle_failure(
                trigger,
                lifecycle.last_finalizer,
                child_exited_before_finalize=child_exited,
                unload_refusal=unload_refusal,
                interrupted=lifecycle.interrupted,
            )
            if resolved is not None:
                outcome = resolved.code
            if diagnostic_refusal is not None and (
                diagnostic_refusal.code == "cleanup_incomplete"
                or outcome not in {"cleanup_incomplete", "pid_reuse_detected"}
            ):
                outcome = diagnostic_refusal.code
            if (
                journal_error is not None
                and outcome not in {"cleanup_incomplete", "pid_reuse_detected"}
            ):
                outcome = journal_error.code
        else:
            lifecycle.current_child = None
    elif (
        lifecycle.last_finalizer is not None
        and lifecycle.last_finalizer.outcome != "clean"
    ):
        outcome = lifecycle.last_finalizer.outcome

    if (
        lifecycle.spawned_any
        and tail_evidence is None
        and static is not None
        and containment_before is not None
        and kernel_cursor_before is not None
    ):
        tail_evidence = _collect_phase_tail(
            config=config,
            providers=providers,
            attempt_root=attempt_root,
            static=static,
            containment_before=containment_before,
            kernel_cursor_before=kernel_cursor_before,
            journal=journal,
        )
        if (
            tail_evidence.refusal is not None
            and outcome not in {"cleanup_incomplete", "pid_reuse_detected"}
            and (
                tail_evidence.refusal.code == "containment_violation"
                or outcome == "provider_uncertain"
            )
        ):
            outcome = tail_evidence.refusal.code

    journal_error = _try_append_phase_transition(
        journal,
        providers.clock,
        "failed_packet_write",
        detail={"outcome": outcome},
    )
    if (
        journal_error is not None
        and outcome not in {"cleanup_incomplete", "pid_reuse_detected"}
    ):
        outcome = journal_error.code
    journal_error = _try_append_phase_transition(
        journal,
        providers.clock,
        "failed",
        detail={"outcome": outcome},
    )
    if (
        journal_error is not None
        and outcome not in {"cleanup_incomplete", "pid_reuse_detected"}
    ):
        outcome = journal_error.code
    try:
        journal.close()
    except (BenchRefusal, OSError, ValueError):
        if outcome not in {"cleanup_incomplete", "pid_reuse_detected"}:
            outcome = "journal_failure"
    path = _write_reduced_outcome(
        config=config,
        providers=providers,
        attempt_root=attempt_root,
        outcome=outcome,
        spawned=lifecycle.spawned_any,
        finalizer=lifecycle.last_finalizer,
        observed_child=(lifecycle.observed_child if lifecycle.spawned_any else None),
        consumed=consumed,
        static_preflight_sha256=static_file_sha256,
        runtime_identity_sha256=bench_identity_file_sha256,
        containment_before_sha256=containment_before_file_sha256,
        containment_after_sha256=(
            None
            if tail_evidence is None
            else tail_evidence.containment_after_file_sha256
        ),
        kernel_cursor_before=kernel_cursor_before,
        kernel_cursor_after=(
            None if tail_evidence is None else tail_evidence.kernel_cursor_after
        ),
        kernel_counters=(
            None if tail_evidence is None else tail_evidence.kernel_counters
        ),
        terminal=terminal,
    )
    return path


def run_phase(
    config: PhaseConfig,
    providers: Providers,
    *,
    root: Path,
    _cleanup_incomplete_observer: Callable[[], None] | None = None,
) -> Path:
    """Run one phase while closing the signal gap before evidence setup."""

    terminal = _TerminalCommit()
    try:
        entry_signal_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGINT, signal.SIGTERM},
        )
    except (OSError, ValueError):
        raise BenchRefusal("cleanup_incomplete") from None
    result: Path | None = None
    pending: BaseException | None = None
    try:
        result = _run_phase_with_blocked_entry(
            config,
            providers,
            root=root,
            entry_signal_mask=entry_signal_mask,
            terminal=terminal,
            cleanup_incomplete_observer=_cleanup_incomplete_observer,
        )
    except BaseException as error:
        pending = error
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, entry_signal_mask)
    except (OSError, ValueError):
        if terminal.path is None:
            pending = BenchRefusal("cleanup_incomplete")
    if terminal.path is not None:
        return terminal.path
    if pending is not None:
        raise pending
    if result is None:
        raise BenchRefusal("provider_uncertain")
    return result


def _run_phase_with_blocked_entry(
    config: PhaseConfig,
    providers: Providers,
    *,
    root: Path,
    entry_signal_mask: set[signal.Signals],
    terminal: _TerminalCommit,
    cleanup_incomplete_observer: Callable[[], None] | None = None,
) -> Path:
    """Execute after the public entry point has blocked driver signals."""

    if type(config) is not PhaseConfig or type(providers) is not Providers:
        raise TypeError("phase_runner_contract")
    if providers.tier != providers.artifact_policy.tier:
        raise BenchRefusal("tier_mismatch")
    timeout = config.readiness_timeout_s
    if (
        type(timeout) not in {int, float}
        or not math.isfinite(timeout)
        or (
            providers.tier == "production"
            and (
                READINESS_TIMEOUT_S != 300
                or timeout != 300
            )
        )
        or (
            providers.tier == "rehearsal"
            and not 0 < timeout <= 5
        )
    ):
        raise BenchRefusal("tier_mismatch")
    authorization_window = _authorization_attempt_window(config)
    attempt_root = _allocate_attempt(
        window_id=authorization_window,
        phase=config.phase,
        policy=providers.artifact_policy,
        root=root,
    )
    started_at = _validated_clock_timestamp(providers.clock.now_utc())
    journal = providers.journal_factory.create(
        config.phase,
        journal_dir=providers.artifact_policy.artifact_dir("journal"),
        timestamp=started_at,
        root=attempt_root,
    )
    lifecycle = _PhaseLifecycleState(
        cleanup_incomplete_observer=cleanup_incomplete_observer,
    )
    static: cm.StaticPreflightDoc | None = None
    containment_before: cm.ContainmentSnapshot | None = None
    kernel_cursor_before: str | None = None
    tail_evidence: _PhaseTailEvidence | None = None
    consumed: ConsumedAuthority | None = None
    static_file_sha: str | None = None
    bench_identity_file_sha: str | None = None
    containment_before_file_sha: str | None = None
    old_handlers: dict[int, object] = {}

    def on_signal(_signum: int, _frame: object) -> None:
        if terminal.path is not None:
            return
        if lifecycle.cleanup_incomplete_latched:
            return
        lifecycle.interrupted = True
        raise BenchRefusal("interrupted")

    def admit_child(child: OwnedChild) -> None:
        lifecycle.admit(child)

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, on_signal)

    def finish_failed(trigger: BaseException) -> Path:
        return _finish_failed_phase(
            trigger,
            config=config,
            providers=providers,
            attempt_root=attempt_root,
            journal=journal,
            lifecycle=lifecycle,
            static=static,
            containment_before=containment_before,
            kernel_cursor_before=kernel_cursor_before,
            tail_evidence=tail_evidence,
            consumed=consumed,
            static_file_sha256=static_file_sha,
            bench_identity_file_sha256=bench_identity_file_sha,
            containment_before_file_sha256=containment_before_file_sha,
            terminal=terminal,
        )

    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, entry_signal_mask)
        journal.append(ts=started_at, transition="phase_preflight", detail={})
        (
            bench_identity,
            runtime_identity,
            static,
            parent_packet,
            parent_completion,
            static_file_sha,
            bench_identity_file_sha,
        ) = _load_phase_preimages(
            config,
            providers,
            root=root,
            attempt_root=attempt_root,
        )
        launcher_pin = getattr(providers.server_launcher, "pin", None)
        if type(launcher_pin) is not SpawnPin:
            raise BenchRefusal("identity_mismatch")
        execution_contract: ProductionExecutionContract | None = None
        if providers.tier == "production":
            execution_contract = _validate_production_execution_contract(
                config,
                launcher=providers.server_launcher,
                static=static,
                runtime_identity=bench_identity,
            )
            admitted_pin = (
                execution_contract.pinned_path,
                execution_contract.pinned_sha256,
            )
            effective_args_sha256 = execution_contract.effective_args_sha256
            admitted_argv = execution_contract.argv
            admitted_env = execution_contract.environment
        else:
            if config.expected_port is not None:
                raise BenchRefusal("identity_mismatch")
            admitted_pin = (
                str(launcher_pin.pinned_path),
                launcher_pin.pinned_sha256,
            )
            admitted_argv = tuple(config.argv)
            admitted_env = MappingProxyType(dict(config.env))
            effective_args_sha256 = _effective_args_sha256(list(admitted_argv))
        _phase_preflight(
            config,
            providers,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
        )

        _append_phase_transition(
            journal,
            providers.clock,
            "containment_before",
        )
        containment_before = providers.containment.capture(config.phase, "before")
        _before_path, containment_before_file_sha = _persist_containment(
            containment_before,
            providers,
            attempt_root=attempt_root,
        )
        if (
            not containment_before.clean
            or containment_before.flag_source_sha256
            != static.checks["flag_source"]
            or containment_before.vision_unit_sha256
            != static.checks["vision_unit"]
        ):
            raise BenchRefusal("containment_violation")
        kernel_cursor_before = providers.kernel_log.cursor()
        before_topology, before_memory = _sample_gpu_stage(
            providers,
            gpu_uuid=config.gpu_uuid,
            owned_pids=set(),
        )
        lifecycle.common_topology = before_topology
        cycle_one_before_at = _validated_clock_timestamp(providers.clock.now_utc())
        _append_phase_transition(
            journal,
            providers.clock,
            "cycle_one_before_snapshot",
        )

        _append_phase_transition(
            journal,
            providers.clock,
            "consume_authorization",
        )
        consumed = providers.authorization_gate.consume(
            config.authorization,
            phase=config.phase,
            boot_id=config.boot_id,
            expected_window_id=config.window_id,
            parent_window=config.parent_window,
            parent_packet=parent_packet,
            parent_completion=parent_completion,
            authority_root=root,
            receipt_root=attempt_root,
            clock=providers.clock,
        )

        completed_cycles = _run_three_cycles(
            config=config,
            providers=providers,
            attempt_root=attempt_root,
            journal=journal,
            lifecycle=lifecycle,
            admitted_argv=admitted_argv,
            admitted_env=admitted_env,
            expected_pin=admitted_pin,
            before_topology=before_topology,
            before_memory=before_memory,
        )

        tail_evidence = _collect_phase_tail(
            config=config,
            providers=providers,
            attempt_root=attempt_root,
            static=static,
            containment_before=containment_before,
            kernel_cursor_before=kernel_cursor_before,
            journal=journal,
        )
        if tail_evidence.refusal is not None:
            raise tail_evidence.refusal
        return _publish_completed_phase(
            config=config,
            providers=providers,
            attempt_root=attempt_root,
            journal=journal,
            lifecycle=lifecycle,
            execution_contract=execution_contract,
            runtime_identity=runtime_identity,
            static=static,
            completed_cycles=completed_cycles,
            consumed=consumed,
            static_file_sha256=static_file_sha,
            bench_identity_file_sha256=bench_identity_file_sha,
            containment_before_sha256=containment_before_file_sha,
            tail=tail_evidence,
            kernel_cursor_before=kernel_cursor_before,
            cycle_one_before_at=cycle_one_before_at,
            effective_args_sha256=effective_args_sha256,
            terminal=terminal,
        )
    except BenchRefusal as refusal:
        return finish_failed(refusal)
    except BaseException as unexpected:
        return finish_failed(unexpected)
    finally:
        cleanup_error: BenchRefusal | None = None
        for signum, previous in old_handlers.items():
            try:
                signal.signal(signum, previous)
            except (OSError, ValueError):
                cleanup_error = BenchRefusal("cleanup_incomplete")
        try:
            journal.close()
        except (BenchRefusal, OSError, ValueError):
            cleanup_error = BenchRefusal("journal_failure")
        if (
            cleanup_error is not None
            and terminal.path is None
            and not lifecycle.cleanup_incomplete_latched
        ):
            raise cleanup_error
