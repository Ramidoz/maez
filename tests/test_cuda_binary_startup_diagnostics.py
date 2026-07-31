"""Task 1 witnesses for bounded binary-only startup stderr capture."""

from __future__ import annotations

import fcntl
import hashlib
import os
import signal
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from scripts import cuda_bench_driver as driver


_CAPTURE_THREAD_PREFIX = "cuda-binary-stderr-"
_EXPECTED_CAPTURE_CAP = 65_536


def _binary_pin(path: Path) -> driver.SpawnPin:
    return driver.SpawnPin(
        kind="binary",
        pinned_path=path,
        pinned_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        required_argv_prefix=(str(path),),
    )


def _binary_env() -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", "/home/rohit"),
        "PATH": "/usr/bin:/bin",
    }


def _capture_threads() -> set[int]:
    return {
        thread.ident
        for thread in threading.enumerate()
        if thread.name.startswith(_CAPTURE_THREAD_PREFIX)
        and thread.ident is not None
    }


def _open_fd_identities() -> set[tuple[int, int]]:
    identities: set[tuple[int, int]] = set()
    for name in os.listdir("/proc/self/fd"):
        try:
            info = os.stat(f"/proc/self/fd/{name}")
        except FileNotFoundError:
            continue
        identities.add((info.st_dev, info.st_ino))
    return identities


def _socket_fd_inodes() -> set[int]:
    inodes: set[int] = set()
    for name in os.listdir("/proc/self/fd"):
        try:
            target = os.readlink(f"/proc/self/fd/{name}")
        except FileNotFoundError:
            continue
        if target.startswith("socket:[") and target.endswith("]"):
            inodes.add(int(target[8:-1]))
    return inodes


def _assert_dynamic_elf(path: Path) -> None:
    assert path.is_absolute()
    payload = path.read_bytes()
    assert payload.startswith(b"\x7fELF")
    assert b"ld-linux" in payload or b"ld-musl" in payload


@contextmanager
def _guarded_binary(
    argv: list[str],
) -> Iterator[
    tuple[
        subprocess.Popen[bytes],
        int,
        int,
        int,
        set[signal.Signals],
        object,
    ]
]:
    executable = Path(argv[0])
    _assert_dynamic_elf(executable)
    sealed = driver._sealed_executable_snapshot(_binary_pin(executable))
    result: tuple[object, ...] | None = None
    mask_restored = False
    try:
        result = driver._guarded_popen(
            argv,
            env=_binary_env(),
            capture_stdout=False,
            pinned_fd=sealed.fd,
            pin_kind="binary",
        )
        popen, pidfd, gate_write, exec_read, old_mask, capture = result
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        mask_restored = True
        yield (
            popen,
            pidfd,
            gate_write,
            exec_read,
            old_mask,
            capture,
        )
    finally:
        os.close(sealed.fd)
        if result is not None:
            popen, pidfd, gate_write, exec_read, old_mask, capture = result
            if not mask_restored:
                signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            if popen.poll() is None:
                try:
                    os.close(gate_write)
                except OSError:
                    pass
                try:
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass
            try:
                popen.wait(timeout=3)
            except subprocess.TimeoutExpired:
                popen.kill()
                popen.wait(timeout=3)
            for fd in (gate_write, exec_read, pidfd):
                try:
                    os.close(fd)
                except OSError:
                    pass
            if not capture.consumed:
                driver._finish_binary_stderr_capture(capture)


def _run_real_binary(argv: list[str]) -> tuple[int, object]:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    with _guarded_binary(argv) as (
        popen,
        _pidfd,
        gate_write,
        exec_read,
        _old_mask,
        capture,
    ):
        pid = popen.pid
        driver._release_guard(gate_write, exec_read)
        returncode = popen.wait(timeout=10)
        diagnostic = driver._finish_binary_stderr_capture(capture)
        assert diagnostic is not None
    assert not Path(f"/proc/{pid}").exists()
    assert driver._pgid_members(pid) == []
    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets
    return returncode, diagnostic


def test_task1_binary_pipe_ownership_blocking_and_blast_radius(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = Path("/usr/bin/bash")
    real_popen = subprocess.Popen
    real_set_blocking = os.set_blocking
    popen_stderr_fd: int | None = None
    stderr_pipe_inode: int | None = None
    pass_fds: tuple[int, ...] = ()
    nonblocking_calls: list[tuple[int, bool]] = []

    def recording_set_blocking(fd: int, blocking: bool) -> None:
        nonblocking_calls.append((fd, blocking))
        real_set_blocking(fd, blocking)

    def recording_popen(
        *args: object, **kwargs: object
    ) -> subprocess.Popen[bytes]:
        nonlocal popen_stderr_fd, stderr_pipe_inode, pass_fds
        supplied_stderr = kwargs.get("stderr")
        assert type(supplied_stderr) is int
        popen_stderr_fd = supplied_stderr
        stderr_pipe_inode = os.fstat(supplied_stderr).st_ino
        pass_fds = tuple(kwargs.get("pass_fds", ()))
        return real_popen(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(driver.os, "set_blocking", recording_set_blocking)
    monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)

    with _guarded_binary([str(executable), "-c", "sleep 0.2"]) as (
        popen,
        _pidfd,
        gate_write,
        exec_read,
        _old_mask,
        capture,
    ):
        assert popen.stderr is None
        assert popen_stderr_fd is not None
        assert stderr_pipe_inode is not None
        assert popen_stderr_fd not in pass_fds
        with pytest.raises(OSError):
            os.fstat(popen_stderr_fd)

        assert len(nonblocking_calls) == 1
        read_fd, blocking = nonblocking_calls[0]
        assert blocking is False
        assert fcntl.fcntl(read_fd, fcntl.F_GETFL) & os.O_NONBLOCK

        fd2_flags_line = next(
            line
            for line in Path(f"/proc/{popen.pid}/fdinfo/2").read_text().splitlines()
            if line.startswith("flags:")
        )
        assert int(fd2_flags_line.split()[1], 8) & os.O_NONBLOCK == 0
        matching_child_fds = [
            int(fd.name)
            for fd in Path(f"/proc/{popen.pid}/fd").iterdir()
            if fd.readlink() == Path(f"pipe:[{stderr_pipe_inode}]")
        ]
        assert matching_child_fds == [2]

        unrelated = real_popen(
            [
                "/usr/bin/bash",
                "-c",
                'for fd in /proc/self/fd/*; do readlink "$fd" 2>/dev/null; done',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        unrelated_fds, _ = unrelated.communicate(timeout=3)
        assert f"pipe:[{stderr_pipe_inode}]".encode() not in unrelated_fds

        driver._release_guard(gate_write, exec_read)
        assert popen.wait(timeout=3) == 0
        diagnostic = driver._finish_binary_stderr_capture(capture)
        assert diagnostic.retained == b""


@pytest.mark.parametrize(
    ("argv", "expected_returncode", "expected_prefix", "truncated"),
    (
        (["/usr/bin/true"], 0, b"", False),
        (["/usr/bin/false"], 1, None, False),
        (["/usr/bin/bash", "-c", "kill -TERM $$"], -signal.SIGTERM, b"", False),
        (
            ["/usr/bin/bash", "-c", "head -c 131072 /dev/zero >&2"],
            0,
            b"\0" * _EXPECTED_CAPTURE_CAP,
            True,
        ),
    ),
    ids=("real_elf_clean", "real_elf_nonzero", "real_elf_signal", "real_elf_flood"),
)
def test_task1_real_elf_outcomes_are_bounded_and_residue_free(
    argv: list[str],
    expected_returncode: int,
    expected_prefix: bytes | None,
    truncated: bool,
) -> None:
    returncode, diagnostic = _run_real_binary(argv)
    assert returncode == expected_returncode
    if expected_prefix is not None:
        assert diagnostic.retained == expected_prefix
    assert diagnostic.retained_byte_count == len(diagnostic.retained)
    assert diagnostic.retained_byte_count <= _EXPECTED_CAPTURE_CAP
    assert diagnostic.retained_sha256 == hashlib.sha256(diagnostic.retained).hexdigest()
    assert diagnostic.truncated is truncated
    if diagnostic.retained:
        assert diagnostic.retained not in repr(diagnostic).encode()


def test_task1_finish_has_one_second_deadline_without_eof() -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    capture, writer = driver._start_binary_stderr_capture()
    started = time.monotonic()
    try:
        diagnostic = driver._finish_binary_stderr_capture(capture)
        elapsed = time.monotonic() - started
        assert 0.8 <= elapsed < 2.0
        assert diagnostic.retained == b""
        assert diagnostic.post_finish_byte_count == 0
        assert not capture.thread_alive
        with pytest.raises(BrokenPipeError):
            os.write(writer, b"after-finish")
    finally:
        os.close(writer)
    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds


def test_task1_finish_caps_continuously_readable_post_finish_bytes() -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    capture, writer = driver._start_binary_stderr_capture()
    stop = threading.Event()

    def flood() -> None:
        block = b"x" * 4096
        try:
            while not stop.is_set():
                os.write(writer, block)
        except BrokenPipeError:
            pass
        finally:
            os.close(writer)

    producer = threading.Thread(target=flood, name="test-stderr-flood")
    producer.start()
    try:
        deadline = time.monotonic() + 2
        while not capture.truncated and time.monotonic() < deadline:
            time.sleep(0.01)
        assert capture.truncated
        diagnostic = driver._finish_binary_stderr_capture(capture)
    finally:
        stop.set()
        producer.join(timeout=2)
    assert not producer.is_alive()
    assert diagnostic.retained_byte_count == _EXPECTED_CAPTURE_CAP
    assert diagnostic.truncated
    assert 0 <= diagnostic.post_finish_byte_count <= 65_536
    assert not capture.thread_alive
    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds


def test_task1_capture_payload_is_excluded_from_repr_and_equality() -> None:
    first = driver._BinaryStderrSnapshot(
        retained=b"private-a",
        retained_sha256=hashlib.sha256(b"private-a").hexdigest(),
        retained_byte_count=9,
        truncated=False,
        post_finish_byte_count=0,
    )
    second = driver._BinaryStderrSnapshot(
        retained=b"private-b",
        retained_sha256=first.retained_sha256,
        retained_byte_count=first.retained_byte_count,
        truncated=first.truncated,
        post_finish_byte_count=first.post_finish_byte_count,
    )
    assert first == second
    assert "private-a" not in repr(first)
    assert "private-b" not in repr(second)
