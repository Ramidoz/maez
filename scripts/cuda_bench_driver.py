"""Inert CUDA A/B bench-driver core: private I/O and provider seams.

Import and provider construction perform no query, subprocess, socket, service,
or model contact. Real providers remain read-only and run only when invoked.
"""

from __future__ import annotations

import errno
import copy
import hashlib
import itertools
import json
import math
import os
import re
import secrets
import socket
import stat
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Protocol

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

STATIC_PREFLIGHT_SCHEMA = "cuda_bench_driver.static_preflight.v1"
PHASE_PACKET_SCHEMA = "cuda_bench_driver.phase_packet.v1"
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


def _json_object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate_key")
        document[key] = value
    return document


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
    tier = "production"

    def now_utc(self) -> str:
        return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

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
