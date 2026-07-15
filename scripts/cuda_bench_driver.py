"""Inert CUDA A/B bench-driver core: contracts and private file I/O only.

This slice has no CLI, provider, subprocess, socket, service, or model contact.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path


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
