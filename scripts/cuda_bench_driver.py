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
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Callable, Literal, Protocol

from scripts import cuda_migration as cm


BENCH_ROOT = Path("/home/rohit/maez/local/cuda_migration_bench")
BENCH_PORT = 18080
PRODUCTION_PORTS = (8080, 8081, 8082)

READINESS_TIMEOUT_S = 300
REQUEST_TIMEOUT_MS = 30_000
SIGTERM_GRACE_S = 10
RESPONSE_BYTE_CAP = 4 * 1024 * 1024
TURN_ARTIFACT_BYTE_CAP = 8 * 1024 * 1024
WINDOW_TTL_S = 14_400
CONTINUATION_TTL_S = 3_600
KILL_WAIT_S = 15
LISTENER_WAIT_S = 10
UNLOAD_WAIT_S = 60
FROZEN_BENCH_ARGS_SHA256 = "7fd627e1132ff30fb7f45df2cbf83d166002b0a0c56bcd07e169eca2180bd413"

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
WINDOW_AUTHORIZATION_SCHEMA = "cuda_bench_driver.window_authorization.v1"
CONTINUATION_SCHEMA = "cuda_bench_driver.continuation.v1"
CONSUMPTION_RECEIPT_SCHEMA = "cuda_bench_driver.consumption_receipt.v1"
TURN_MANIFEST_SCHEMA = "cuda_bench_driver.turn_manifest.v1"
TURN_ARTIFACT_SCHEMA = "cuda_bench_driver.turn_artifact.v1"
CONTAINMENT_SNAPSHOT_SCHEMA = "cuda_bench_driver.containment_snapshot.v1"
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
_NAME_SEED = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}")


class BenchRefusal(Exception):
    """A typed refusal from the driver's closed vocabulary."""

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in REFUSAL_VOCABULARY:
            raise ValueError("closed_refusal")
        self.code = code
        super().__init__(code)


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
    fd: int, parent_fd: int, name: str, *, expected_size: int
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


def write_private_file(relative: str, data: bytes, *, root: Path = BENCH_ROOT) -> Path:
    """Exclusively create and fsync one owner-private file below root."""

    if type(data) is not bytes or len(data) > TURN_ARTIFACT_BYTE_CAP:
        _filesystem_hazard()
    parent_fd, parts, directory_chain = _open_parent_fd(relative, root=root, create=True)
    fd: int | None = None
    try:
        fd = _open_anonymous_file(parent_fd, append=False)
        _write_all(fd, data)
        os.fsync(fd)
        _check_file_fd(fd, expected_nlink=0, expected_size=len(data))
        published = _publish_anonymous_file(fd, parent_fd, parts[-1], expected_size=len(data))
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
        rendered = line.decode("utf-8").lower()
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
    return ["systemctl", "--user", subcommand, unit]


@dataclass
class ProviderWitness:
    synthetic: bool
    real_calls: int

    def __post_init__(self) -> None:
        if (
            type(self.synthetic) is not bool
            or type(self.real_calls) is not int
            or self.real_calls < 0
            or (self.synthetic and self.real_calls != 0)
        ):
            raise ValueError("provider_witness_invalid")

    def assert_no_real_calls(self) -> None:
        if not self.synthetic or self.real_calls != 0:
            raise AssertionError("synthetic_provider_contacted_real_surface")


class ServiceStateProvider(Protocol):
    tier: str

    def is_active(self, unit: str) -> str: ...


class PortProbe(Protocol):
    tier: str

    def is_free(self, port: int) -> bool: ...


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
old_mask = {int(value) for value in sys.argv[5].split(",") if value}
token = os.read(gate_fd, 1)
os.close(gate_fd)
if token != b"G":
    os.close(exec_fd)
    os.close(pin_fd)
    raise SystemExit(0)
target_argv = sys.argv[6:]
signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
os.set_inheritable(exec_fd, False)
try:
    if pin_kind == "binary":
        os.set_inheritable(pin_fd, False)
        os.execve(pin_fd, target_argv, os.environ)
    elif pin_kind == "python_file":
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
            or not isinstance(self.popen, subprocess.Popen)
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
) -> tuple[subprocess.Popen[bytes], int, int, int, set[signal.Signals]]:
    gate_read: int | None = None
    gate_write: int | None = None
    exec_read: int | None = None
    exec_write: int | None = None
    popen: subprocess.Popen[bytes] | None = None
    pidfd: int | None = None
    old_mask: set[signal.Signals] | None = None
    cleanup_complete = True
    try:
        old_mask = signal.pthread_sigmask(
            signal.SIG_BLOCK,
            {signal.SIGINT, signal.SIGTERM},
        )
        gate_read, gate_write = os.pipe2(os.O_CLOEXEC)
        exec_read, exec_write = os.pipe2(os.O_CLOEXEC)
        encoded_mask = ",".join(str(int(value)) for value in sorted(old_mask))
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
            encoded_mask,
            *argv,
        ]
        popen = subprocess.Popen(
            guard_argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=dict(env),
            start_new_session=True,
            pass_fds=(gate_read, exec_write, pinned_fd),
            close_fds=True,
            bufsize=0,
        )
        _close_fd(gate_read)
        gate_read = None
        _close_fd(exec_write)
        exec_write = None
        pidfd = os.pidfd_open(popen.pid)
        binding_state, bound_pid = _pidfd_bound_pid(pidfd)
        if binding_state != "bound" or bound_pid != popen.pid:
            raise BenchRefusal("spawn_failure")
        return popen, pidfd, gate_write, exec_read, old_mask
    except BaseException as exc:
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
        if not 0 < port <= 65_535 or port == BENCH_PORT:
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
) -> bool:
    complete = True
    try:
        status = _pidfd_status(pidfd)
        binding_state, bound_pid = _pidfd_bound_pid(pidfd)
        if status == "alive" and binding_state == "bound" and bound_pid == popen.pid:
            try:
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            except ProcessLookupError:
                if _pidfd_status(pidfd) != "gone":
                    complete = False
            except OSError:
                complete = False
        elif status == "alive":
            complete = False
        try:
            popen.wait(timeout=KILL_WAIT_S)
        except (OSError, subprocess.TimeoutExpired):
            complete = False
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
        return complete
    finally:
        _close_fd(pidfd)
        _close_popen_streams(popen)


def spawn_pinned(
    argv: list[str], *, pin: SpawnPin, env: dict[str, str]
) -> OwnedChild:
    _validate_spawn_inputs(argv, pin=pin, env=env)
    snapshot = _sealed_executable_snapshot(pin)
    try:
        popen, pidfd, gate_write, exec_read, old_mask = _guarded_popen(
            argv,
            env=env,
            capture_stdout=pin.kind == "python_file",
            pinned_fd=snapshot.fd,
            pin_kind=pin.kind,
        )
    finally:
        _close_fd(snapshot.fd)
    port: int | None = None
    mask_restored = False
    target_release_attempted = False
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        mask_restored = True
        target_release_attempted = True
        _release_guard(gate_write, exec_read)
        port = _read_stub_announcement(popen) if pin.kind == "python_file" else None
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
        )
    except BaseException as exc:
        if target_release_attempted:
            cleanup_complete = _bootstrap_abort(popen, pidfd, port=port)
        else:
            cleanup_complete = _cleanup_inert_guard(
                popen,
                pidfd=pidfd,
                gate_write=gate_write,
                exec_read=exec_read,
            )
        if not mask_restored:
            try:
                signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            except BaseException:
                cleanup_complete = False
        if not cleanup_complete:
            raise BenchRefusal("cleanup_incomplete") from exc
        if isinstance(exc, BenchRefusal):
            raise
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise BenchRefusal("spawn_failure") from None


class RealServerLauncher:
    tier = "production"

    def __init__(self, pin: SpawnPin) -> None:
        if not isinstance(pin, SpawnPin) or pin.kind != "binary":
            raise ValueError("spawn_pin_invalid")
        self.pin = pin

    def spawn(self, argv: list[str], env: dict[str, str]) -> OwnedChild:
        ports = [
            argv[index + 1]
            for index, value in enumerate(argv[:-1])
            if value == "--port"
        ] if type(argv) is list else []
        if ports != [str(BENCH_PORT)]:
            raise BenchRefusal("spawn_failure")
        child = spawn_pinned(argv, pin=self.pin, env=env)
        return replace(child, port=BENCH_PORT)


class RehearsalServerLauncher:
    tier = "rehearsal"

    def __init__(self, pin: SpawnPin) -> None:
        if (
            not isinstance(pin, SpawnPin)
            or pin.kind != "python_file"
            or pin.pinned_path != _REHEARSAL_STUB_PATH
        ):
            raise ValueError("spawn_pin_invalid")
        self.pin = pin

    def spawn(self, argv: list[str], env: dict[str, str]) -> OwnedChild:
        return spawn_pinned(argv, pin=self.pin, env=env)


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


def _wait_listener_free(port_probe: PortProbe, port: int) -> bool | None:
    deadline = time.monotonic() + LISTENER_WAIT_S
    while True:
        try:
            if port_probe.is_free(port):
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
    if port is not None:
        listener_free = _wait_listener_free(port_probe, port)
        if listener_free is not True:
            outcome = "cleanup_incomplete"
    return finish()


class AuthorizationGate(Protocol):
    tier: str

    def consume(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        parent_window: object | None,
        parent_packet: cm.PhasePacket | None,
        root: Path,
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
    if kind == "turn_artifact":
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
        payload = _production_artifact(kind, document)
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


def _prepare_authorization_consumption(
    auth: object,
    *,
    phase: str,
    boot_id: str,
    clock: Clock,
    policy: ArtifactPolicy,
    expected_tier: str,
    parent_window: WindowAuthorization | None,
    parent_packet: cm.PhasePacket | None,
) -> tuple[ConsumedAuthority, bytes, str]:
    if (
        type(getattr(policy, "tier", None)) is not str
        or policy.tier != expected_tier
        or not callable(getattr(policy, "encode", None))
        or not callable(getattr(policy, "artifact_dir", None))
    ):
        raise BenchRefusal("tier_mismatch")

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
        if cm._compare_utc_z(timestamp, parent_window.expires_at) >= 0:
            raise BenchRefusal("authorization_expired")

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
    clock: Clock,
    root: Path,
    policy: ArtifactPolicy,
    parent_window: WindowAuthorization | None = None,
    parent_packet: cm.PhasePacket | None = None,
) -> ConsumedAuthority:
    consumed, encoded, receipt_dir = _prepare_authorization_consumption(
        auth,
        phase=phase,
        boot_id=boot_id,
        clock=clock,
        policy=policy,
        expected_tier="production",
        parent_window=parent_window,
        parent_packet=parent_packet,
    )
    nonce = consumed.receipt["nonce"]
    if type(nonce) is not str:
        raise BenchRefusal("authorization_malformed")
    _create_consumption_marker(nonce, root=root)
    write_private_file(
        f"{receipt_dir}/consumption-{nonce}.json",
        encoded,
        root=root,
    )
    return consumed


class RealAuthorizationGate:
    tier = "production"

    def __init__(self, policy: ArtifactPolicy) -> None:
        if type(getattr(policy, "tier", None)) is not str or policy.tier != self.tier:
            raise BenchRefusal("tier_mismatch")
        self.policy = policy

    def consume(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        parent_window: WindowAuthorization | None,
        parent_packet: cm.PhasePacket | None,
        root: Path,
        clock: Clock,
    ) -> ConsumedAuthority:
        return consume_authorization(
            authorization,
            phase=phase,
            boot_id=boot_id,
            parent_window=parent_window,
            parent_packet=parent_packet,
            root=root,
            clock=clock,
            policy=self.policy,
        )


class RehearsalAuthorizationGate:
    tier = "rehearsal"

    def __init__(self, policy: ArtifactPolicy) -> None:
        if type(getattr(policy, "tier", None)) is not str or policy.tier != self.tier:
            raise BenchRefusal("tier_mismatch")
        self.policy = policy

    def consume(
        self,
        authorization: object,
        *,
        phase: str,
        boot_id: str,
        parent_window: WindowAuthorization | None,
        parent_packet: cm.PhasePacket | None,
        root: Path,
        clock: Clock,
    ) -> ConsumedAuthority:
        consumed, encoded, receipt_dir = _prepare_authorization_consumption(
            authorization,
            phase=phase,
            boot_id=boot_id,
            clock=clock,
            policy=self.policy,
            expected_tier=self.tier,
            parent_window=parent_window,
            parent_packet=parent_packet,
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
            root=root,
        )
        return consumed


class _CommandRunner(Protocol):
    def __call__(self, argv: list[str]) -> subprocess.CompletedProcess[str]: ...


def _run_read_only(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=False, capture_output=True, text=True)


class RealServiceStateProvider:
    tier = "production"

    def __init__(self, *, runner: _CommandRunner = _run_read_only) -> None:
        self._runner = runner
        self.witness = ProviderWitness(synthetic=False, real_calls=0)

    def is_active(self, unit: str) -> str:
        self.witness.real_calls += 1
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


class RealPortProbe:
    tier = "production"

    def __init__(self) -> None:
        self.witness = ProviderWitness(synthetic=False, real_calls=0)

    def is_free(self, port: int) -> bool:
        if type(port) is not int or not 0 < port <= 65_535:
            raise BenchRefusal("provider_uncertain")
        self.witness.real_calls += 1
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


class RealGpuProvider:
    tier = "production"

    def __init__(self, *, runner: _CommandRunner = _run_read_only) -> None:
        self._runner = runner
        self.witness = ProviderWitness(synthetic=False, real_calls=0)

    def _query(self, argv: list[str]) -> str:
        self.witness.real_calls += 1
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


class RealKernelLogProvider:
    tier = "production"

    def __init__(self, *, runner: _CommandRunner = _run_read_only) -> None:
        self._runner = runner
        self.witness = ProviderWitness(synthetic=False, real_calls=0)

    def _query(self, argv: list[str]) -> str:
        self.witness.real_calls += 1
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


class RealBackendMapProvider:
    tier = "production"

    def __init__(self) -> None:
        self.witness = ProviderWitness(synthetic=False, real_calls=0)

    def read_maps(self, pid: int) -> str:
        if type(pid) is not int or pid <= 0:
            raise BenchRefusal("provider_uncertain")
        self.witness.real_calls += 1
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


class SyntheticServiceState:
    tier = "rehearsal"

    def __init__(self, states: dict[str, str]) -> None:
        self._states = dict(states)
        self.witness = ProviderWitness(synthetic=True, real_calls=0)

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


class SyntheticPortProbe:
    tier = "rehearsal"

    def __init__(self, free: set[int]) -> None:
        try:
            self._free = set(free)
        except (TypeError, ValueError):
            self._free = set()
            self._configuration_valid = False
        else:
            self._configuration_valid = type(free) is set and all(
                type(port) is int and 0 < port <= 65_535 for port in self._free
            )
        self.witness = ProviderWitness(synthetic=True, real_calls=0)

    def is_free(self, port: int) -> bool:
        if (
            not self._configuration_valid
            or type(port) is not int
            or not 0 < port <= 65_535
        ):
            raise BenchRefusal("provider_uncertain")
        return port in self._free


class SyntheticGpu:
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
        self.witness = ProviderWitness(synthetic=True, real_calls=0)

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


class SyntheticKernelLog:
    tier = "rehearsal"

    def __init__(self, counts: dict[str, int]) -> None:
        if set(counts) != set(KERNEL_COUNTER_KEYS) or any(
            type(value) is not int or value < 0 for value in counts.values()
        ):
            raise ValueError("synthetic_kernel_invalid")
        self._counts = dict(counts)
        self._cursor_sequence = itertools.count(1)
        self.witness = ProviderWitness(synthetic=True, real_calls=0)

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


class SyntheticBackendMap:
    tier = "rehearsal"

    def __init__(self, maps_text_by_pid: dict[int, str]) -> None:
        try:
            self._maps = dict(maps_text_by_pid)
        except (TypeError, ValueError):
            self._maps = {}
            self._configuration_valid = False
        else:
            self._configuration_valid = all(
                type(pid) is int and pid > 0 for pid in self._maps
            )
        self.witness = ProviderWitness(synthetic=True, real_calls=0)

    def read_maps(self, pid: int) -> str:
        if not self._configuration_valid or type(pid) is not int or pid <= 0:
            raise BenchRefusal("provider_uncertain")
        try:
            evidence = self._maps[pid]
        except KeyError:
            raise BenchRefusal("provider_uncertain") from None
        if type(evidence) is not str:
            raise BenchRefusal("provider_uncertain")
        return evidence


class FrozenClock:
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
        self.witness = ProviderWitness(synthetic=True, real_calls=0)

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


_PROVIDERS_GUARD = object()


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
    artifact_policy: ArtifactPolicy,
    clock: Clock,
    journal_factory: JournalFactory,
) -> Providers:
    expected_launcher = (
        RealServerLauncher if tier == "production" else RehearsalServerLauncher
    )
    if type(server_launcher) is not expected_launcher:
        raise BenchRefusal("tier_mismatch")
    if type(server_client) is not LoopbackServerClient:
        raise BenchRefusal("tier_mismatch")
    if server_client.clock is not clock:
        raise BenchRefusal("tier_mismatch")
    components = {
        "service_state": service_state,
        "port_probe": port_probe,
        "gpu": gpu,
        "kernel_log": kernel_log,
        "backend_maps": backend_maps,
        "server_launcher": server_launcher,
        "server_client": server_client,
        "authorization_gate": authorization_gate,
        "artifact_policy": artifact_policy,
        "clock": clock,
        "journal_factory": journal_factory,
    }
    if getattr(authorization_gate, "policy", None) is not artifact_policy:
        raise BenchRefusal("tier_mismatch")
    required_methods = {
        "service_state": ("is_active",),
        "port_probe": ("is_free",),
        "gpu": ("enumerate_uuids", "inventory", "memory"),
        "kernel_log": ("cursor", "count_signatures"),
        "backend_maps": ("read_maps",),
        "server_launcher": ("spawn",),
        "server_client": ("health", "models", "stream"),
        "authorization_gate": ("consume",),
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
        artifact_policy=artifact_policy,
        clock=clock,
        journal_factory=journal_factory,
    )
