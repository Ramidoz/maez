"""Anchored private-file I/O — the S7 publication primitive.

Governance code must not import from the bench-tooling tree, so the shared
primitive lives here rather than in `scripts/cuda_bench_driver.py`.

Publication is anchored, not a file write:

    O_TMPFILE -> write ALL -> fsync file -> exclusive link -> fsync parent

O_TMPFILE has no name, so a partially written receipt is never visible to
a reader. The link is exclusive, so two concurrent publishers cannot both
believe they won -- the loser gets FileExistsError and must verify the
winner rather than replace it. The parent fsync is what makes the
directory entry itself durable; without it a crash can lose a receipt
whose bytes were safely on disk.

Reading is equally anchored. Every open is O_NOFOLLOW so a symlink cannot
redirect the read, O_NONBLOCK so a FIFO cannot hang it, and identity comes
from `os.fstat` on the HELD DESCRIPTOR rather than `os.stat` on a name
that can be replaced between the check and the open. The descriptor is
stat'd again after reading and the two compared, because a file swapped
mid-read would otherwise be returned as if it were the one that was
validated.

ACTIVATION takes no argument at all. `read_migration_receipt()` walks the
one canonical path itself; there is no parameter through which a caller
could aim activation at a receipt beside a different store.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat as stat_module
from pathlib import Path, PurePosixPath

__all__ = [
    "read_migration_receipt",
    "read_private_file",
    "write_private_file",
]

# A receipt is a small content-light document. The cap bounds the read so a
# hostile file cannot exhaust memory before any validation runs.
MAX_PRIVATE_FILE_BYTES = 8192

STORE_NAME = "ceremony.sqlite3"
RECEIPT_NAME = "s7_migration_receipt.json"
PRIVATE_FILE_MODE = 0o600


@contextlib.contextmanager
def _open_directory(path: str | os.PathLike[str]):
    """Walk and hold a directory without following any path component."""

    text = os.fspath(path)
    if not os.path.isabs(text):
        raise ValueError("anchored private-file root must be absolute")
    parts = [part for part in Path(text).parts[1:] if part not in ("", ".")]
    if any(part == ".." or "\x00" in part for part in parts):
        raise ValueError("anchored private-file root is unsafe")
    fd = os.open(
        "/",
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        for component in parts:
            next_fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=fd,
            )
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


def _verify_and_read(fd: int, before, relative: str, expected_uid: int) -> bytes:
    """Verify an already-open descriptor and read it.

    Takes the descriptor AND its first stat, rather than opening and
    stat'ing itself, so the caller's own `os.fstat` is the FIRST stat of
    the file. Order matters to more than style: the stat-stability check
    compares a before and an after, and an extra stat ahead of them makes
    both sides land on the same side of any change.
    """
    if not stat_module.S_ISREG(before.st_mode):
        raise OSError(f"{relative} is not a regular file")
    if before.st_uid != expected_uid:
        raise PermissionError(f"{relative} is not owned by uid {expected_uid}")
    mode = stat_module.S_IMODE(before.st_mode)
    if mode != PRIVATE_FILE_MODE:
        # Not merely "no group or other bits": 0400 and 0000 satisfy
        # that too and are not what the writer produces. Any other mode
        # means something else has touched the file.
        raise PermissionError(f"{relative} has mode {oct(mode)}, expected 0o600")
    if before.st_nlink != 1:
        # A second name is a second way to replace the bytes after they
        # have been checked.
        raise OSError(f"{relative} has {before.st_nlink} links, expected 1")
    if before.st_size > MAX_PRIVATE_FILE_BYTES:
        raise ValueError(
            f"{relative} is {before.st_size} bytes, over the "
            f"{MAX_PRIVATE_FILE_BYTES} cap"
        )

    chunks: list[bytes] = []
    remaining = before.st_size
    while remaining > 0:
        chunk = os.read(fd, remaining)
        if not chunk:
            # EOF before the declared size: the file changed under the
            # reader. Returning the short bytes would be silent
            # corruption.
            raise OSError(f"{relative} ended before its declared size")
        chunks.append(chunk)
        remaining -= len(chunk)

    after = os.fstat(fd)
    for field in (
        "st_dev",
        "st_ino",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    ):
        if getattr(before, field) != getattr(after, field):
            raise OSError(f"{relative} changed while it was being read")

    return b"".join(chunks)


def _anchored_leaf(dir_fd: int, relative: str):
    """Walk `relative` component by component beneath `dir_fd`.

    Returns (parent_fd, leaf_name, owned) where `owned` says whether the
    caller must close parent_fd.

    The anchor was decorative before this: `os.open(absolute, dir_fd=...)`
    IGNORES the descriptor entirely, and `../sibling.json` walked straight
    out of the root. Both were reproduced writing and reading outside the
    supplied root. Intermediate components are opened O_NOFOLLOW too, so a
    symlinked DIRECTORY in the middle cannot redirect the tail.
    """
    if os.path.isabs(relative):
        raise ValueError("anchored path must be relative, not absolute")

    parts = [p for p in PurePosixPath(relative).parts if p not in (".",)]
    if not parts:
        raise ValueError("anchored path is empty")
    if any(p == ".." for p in parts):
        raise ValueError("anchored path may not traverse upwards")

    parent_fd, owned = dir_fd, False
    try:
        for component in parts[:-1]:
            nxt = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            if owned:
                os.close(parent_fd)
            parent_fd, owned = nxt, True
    except Exception:
        if owned:
            os.close(parent_fd)
        raise
    return parent_fd, parts[-1], owned


def read_private_file(
    relative: str, *, root: str | os.PathLike[str], expected_uid: int
) -> bytes:
    """Read a private file under `root`, anchored and verified.

    The root itself is opened O_NOFOLLOW so a symlinked directory cannot
    redirect the read, and O_NONBLOCK so nothing here can block on a
    non-regular file. Identity comes from `os.fstat` on the held
    descriptor; `os.stat` on a pathname would be a TOCTOU, since the name
    can be replaced between the check and the open.
    """
    with _open_directory(root) as dir_fd:
        parent_fd, leaf, owned = _anchored_leaf(dir_fd, relative)
        try:
            fd = os.open(
                leaf,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            try:
                before = os.fstat(fd)
                payload = _verify_and_read(fd, before, relative, expected_uid)
                after = os.fstat(fd)
                named = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
                for field in (
                    "st_dev",
                    "st_ino",
                    "st_mode",
                    "st_uid",
                    "st_nlink",
                    "st_size",
                    "st_mtime_ns",
                    "st_ctime_ns",
                ):
                    if getattr(after, field) != getattr(named, field):
                        raise OSError(
                            f"{relative} name no longer identifies held file"
                        )
                if len(payload) != before.st_size == after.st_size:
                    raise OSError(f"{relative} read length does not match held file")
                return payload
            finally:
                os.close(fd)
        finally:
            if owned:
                os.close(parent_fd)


def _write_private_file_at(
    dir_fd: int, relative: str, data: bytes, *, on_link=None
) -> None:
    """Publish beneath an ALREADY-HELD directory descriptor.

    `write_private_file` takes a root PATH, which it re-walks. If the
    directory has been moved or replaced since the caller opened it, the
    bytes land beside a different store -- reproduced: migration returned
    success while the receipt was written into a newly created foreign
    directory and the migrated directory had none. When the caller already
    holds the directory, the descriptor is the anchor.
    """
    parent_fd, leaf, owned = _anchored_leaf(dir_fd, relative)
    fd = os.open(".", os.O_TMPFILE | os.O_RDWR, PRIVATE_FILE_MODE, dir_fd=parent_fd)
    try:
        written = 0
        while written < len(data):
            sent = os.write(fd, data[written:])
            if sent <= 0:
                raise OSError("anchored write made no progress")
            written += sent
        os.fsync(fd)
        if on_link is not None:
            on_link()
        os.link(
            f"/proc/self/fd/{fd}", leaf, dst_dir_fd=parent_fd, follow_symlinks=True
        )
        os.fsync(parent_fd)
    finally:
        os.close(fd)
        if owned:
            os.close(parent_fd)


def write_private_file(
    relative: str,
    data: bytes,
    *,
    root: str | os.PathLike[str],
    on_link=None,
) -> Path:
    """Publish `data` as `relative` under `root`, atomically and privately.

    `on_link` fires immediately before the link. It exists so the
    exclusive-create race is observable: a competitor publishing in that
    window must make this link FAIL rather than silently win.
    """
    with _open_directory(root) as dir_fd:
        parent_fd, leaf, owned = _anchored_leaf(dir_fd, relative)
        fd = os.open(".", os.O_TMPFILE | os.O_RDWR, PRIVATE_FILE_MODE, dir_fd=parent_fd)
        try:
            # os.write may accept fewer bytes than offered; writing once and
            # assuming completion truncates the file silently.
            written = 0
            while written < len(data):
                sent = os.write(fd, data[written:])
                if sent <= 0:
                    # No progress. Looping on this spins forever --
                    # reproduced, it ran past a one-second timeout.
                    raise OSError("anchored write made no progress")
                written += sent

            os.fsync(fd)

            if on_link is not None:
                on_link()

            # Exclusive: os.link refuses an existing destination, so the
            # loser of a race cannot replace the winner.
            os.link(
                f"/proc/self/fd/{fd}",
                leaf,
                dst_dir_fd=parent_fd,
                follow_symlinks=True,
            )
            # The entry is not durable until the directory HOLDING it is
            # synced -- and for a nested leaf that is `parent_fd`, not the
            # root. Syncing only the root left the bytes safe while the
            # name could still vanish after a crash.
            os.fsync(parent_fd)
        finally:
            os.close(fd)
            if owned:
                os.close(parent_fd)

    return Path(root) / relative


def _canonical_s7_dir() -> Path:
    from core.governance.s7_webauthn_bootstrap import DEFAULT_STORE_ROOT

    return Path(DEFAULT_STORE_ROOT)


@contextlib.contextmanager
def _open_canonical_s7_dir():
    """Walk the frozen canonical path, component by component, O_NOFOLLOW.

    No caller supplies any part of this path.
    """
    target = _canonical_s7_dir()
    parts = target.parts
    fd = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in parts[1:]:
            nxt = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=fd,
            )
            os.close(fd)
            fd = nxt
        yield fd
    finally:
        os.close(fd)


def _read_migration_receipt(*, store_dir_fd: int) -> bytes:
    """PRIVATE — descriptor injection, for private-copy tests only.

    Production callsite allowlist of exactly one: `read_migration_receipt`.
    Any other production caller could aim activation at a chosen directory.
    """
    # BOTH leaves, beneath the ONE held directory. Reading only the
    # receipt binds nothing: a receipt describing a different store would
    # activate this one. The store's identity comes from THIS fd's
    # st_dev/st_ino, never from a re-resolved pathname, which would
    # reintroduce the race the anchoring exists to remove.
    store_fd = os.open(
        STORE_NAME,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
        dir_fd=store_dir_fd,
    )
    try:
        store_stat = os.fstat(store_fd)
    finally:
        os.close(store_fd)

    fd = os.open(
        RECEIPT_NAME,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
        dir_fd=store_dir_fd,
    )
    try:
        raw = _verify_and_read(fd, os.fstat(fd), RECEIPT_NAME, os.getuid())
    finally:
        os.close(fd)

    try:
        document = json.loads(raw)
    except ValueError as exc:
        raise ValueError("migration receipt is not valid JSON") from exc

    # Valid JSON is not a valid receipt. `null`, `[]`, `1` and `"x"` all
    # parse and then crash at .get(); a crash is not a refusal, and a
    # caller catching refusals would not catch it.
    if not isinstance(document, dict):
        raise ValueError("migration receipt is not a JSON object")

    if (
        document.get("store_dev") != store_stat.st_dev
        or document.get("store_ino") != store_stat.st_ino
    ):
        raise ValueError(
            "migration receipt does not describe the store beside it"
        )
    return raw


def read_migration_receipt() -> bytes:
    """ACTIVATION — takes nothing.

    A generic reader with a directory argument would let a caller point
    activation at a receipt beside a different store.
    """
    with _open_canonical_s7_dir() as store_dir_fd:
        return _read_migration_receipt(store_dir_fd=store_dir_fd)
