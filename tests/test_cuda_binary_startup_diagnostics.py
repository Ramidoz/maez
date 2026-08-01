"""Task 1 witnesses for bounded binary-only startup stderr capture."""

from __future__ import annotations

import ast
import ctypes
import fcntl
import hashlib
import inspect
import json
import os
import signal
import stat
import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import fields, replace
from pathlib import Path

import pytest

from scripts import cuda_bench_cli as cli
from scripts import cuda_bench_assemble as assemble
from scripts import cuda_bench_driver as driver


_CAPTURE_THREAD_PREFIX = "cuda-binary-stderr-"
_EXPECTED_CAPTURE_CAP = 65_536


def _wait_for(predicate: Callable[[], bool], *, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


@contextmanager
def _child_subreaper() -> Iterator[None]:
    libc = ctypes.CDLL(None, use_errno=True)
    prior = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(prior), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    try:
        yield
    finally:
        assert libc.prctl(36, prior.value, 0, 0, 0) == 0


class _ObservedJournal:
    def __init__(self, journal: driver.PhaseJournal) -> None:
        self._journal = journal
        self.path = journal.path
        self.bootstrap_cleanup_appended = threading.Event()

    def append(
        self,
        *,
        ts: str,
        transition: str,
        detail: Mapping[str, object],
    ) -> None:
        self._journal.append(ts=ts, transition=transition, detail=detail)
        if transition == "cycle_1_bootstrap_cleanup":
            self.bootstrap_cleanup_appended.set()

    def close(self) -> None:
        self._journal.close()


class _FailingJournal(_ObservedJournal):
    def append(
        self,
        *,
        ts: str,
        transition: str,
        detail: Mapping[str, object],
    ) -> None:
        del ts, detail
        if transition == "cycle_1_bootstrap_cleanup":
            self.bootstrap_cleanup_appended.set()
        raise driver.BenchRefusal("journal_failure")


class _BootstrapFailingJournal(_ObservedJournal):
    def __init__(
        self,
        journal: driver.PhaseJournal,
        *,
        failure: Callable[[], BaseException],
        pending_signum: int | None = None,
    ) -> None:
        super().__init__(journal)
        self._failure = failure
        self._pending_signum = pending_signum
        self._failed = False

    def append(
        self,
        *,
        ts: str,
        transition: str,
        detail: Mapping[str, object],
    ) -> None:
        if transition == "cycle_1_bootstrap_cleanup" and not self._failed:
            self._failed = True
            self.bootstrap_cleanup_appended.set()
            if self._pending_signum is not None:
                signal.raise_signal(self._pending_signum)
            raise self._failure()
        super().append(ts=ts, transition=transition, detail=detail)


def _task2_journal(root: Path) -> _ObservedJournal:
    return _ObservedJournal(
        driver.PhaseJournal(
            "vulkan_baseline",
            journal_dir="journal",
            timestamp="task2",
            root=root,
        )
    )


def _task2_identity_failure_argv(
    *,
    retained_writer: bool,
    observed_path: Path | None = None,
    descendant_pid_path: Path | None = None,
) -> list[str]:
    executable = "/usr/bin/bash"
    if not retained_writer:
        return [
            executable,
            "-c",
            "printf task2-private-stderr >&2; while :; do :; done",
            "task2",
            "--port",
            str(driver.BENCH_PORT),
        ]
    assert observed_path is not None and descendant_pid_path is not None
    script = r"""
(
    trap '' PIPE
    while :; do
        printf x >&2 || {
            printf observed > "$1"
            exec /usr/bin/sleep 300
        }
    done
) &
printf '%s\n' "$!" > "$2"
wait
"""
    return [
        executable,
        "-c",
        script,
        "task2",
        str(observed_path),
        str(descendant_pid_path),
        "--port",
        str(driver.BENCH_PORT),
    ]


def _run_task2_real_phase_failure_through_cli(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    journal_failure: Callable[[], BaseException],
    pending_signum: int | None = None,
    handoff_signum: int | None = None,
    handoff_observed: threading.Event | None = None,
    interrupt_retirement: bool = False,
) -> tuple[int, list[driver._BinarySpawnFailure]]:
    from tests.test_cuda_bench_driver import _b7_harness

    root.chmod(0o700)
    harness = _b7_harness(root, nonce="7" * 64)
    authorization = harness.config.authorization
    launcher = driver.RealServerLauncher(_binary_pin(Path("/usr/bin/bash")))
    carriers: list[driver._BinarySpawnFailure] = []
    real_raise_failure = driver._raise_binary_spawn_failure
    real_finish = driver._finish_binary_stderr_capture
    real_finish_failed_phase = driver._finish_failed_phase
    real_create = driver.RehearsalJournalFactory.create
    real_open = driver.open_bench_file
    real_signal = signal.signal
    real_pthread_sigmask = signal.pthread_sigmask
    retirement_interrupted = False
    cleanup_terminal_raised = threading.Event()
    handoff_signal_sent = False

    def spawn_real_binary(
        _launcher: driver.RehearsalServerLauncher,
        _argv: list[str],
        _env: dict[str, str],
    ) -> driver.OwnedChild:
        return launcher.spawn(
            _task2_identity_failure_argv(retained_writer=False),
            _binary_env(),
        )

    def record_failure(
        exc: BaseException,
        *,
        bootstrap_cleanup: driver._BootstrapCleanupResult,
        stderr_capture: driver._BinaryStderrCapture,
    ) -> None:
        try:
            real_raise_failure(
                exc,
                bootstrap_cleanup=bootstrap_cleanup,
                stderr_capture=stderr_capture,
            )
        except driver._BinarySpawnFailure as failure:
            carriers.append(failure)
            raise

    def failing_journal(
        factory: driver.RehearsalJournalFactory,
        *args: object,
        **kwargs: object,
    ) -> _BootstrapFailingJournal:
        return _BootstrapFailingJournal(
            real_create(factory, *args, **kwargs),  # type: ignore[arg-type]
            failure=journal_failure,
            pending_signum=pending_signum,
        )

    def finish_with_one_interruption(
        capture: driver._BinaryStderrCapture | None,
    ) -> driver._BinaryStderrSnapshot | None:
        nonlocal retirement_interrupted
        if interrupt_retirement and not retirement_interrupted:
            retirement_interrupted = True
            raise KeyboardInterrupt("task2 retirement interrupt")
        return real_finish(capture)

    def observe_cleanup_terminal(*args: object, **kwargs: object) -> Path:
        try:
            return real_finish_failed_phase(*args, **kwargs)  # type: ignore[arg-type]
        except driver._StorageIndependentCleanupIncomplete:
            cleanup_terminal_raised.set()
            raise

    def signal_at_phase_cli_handoff(
        installed_signum: int,
        handler: object,
    ) -> object:
        nonlocal handoff_signal_sent
        if (
            handoff_signum is not None
            and installed_signum == handoff_signum
            and handler is cli._on_command_signal
            and cleanup_terminal_raised.is_set()
            and not handoff_signal_sent
        ):
            handoff_signal_sent = True
            previous_mask = real_pthread_sigmask(
                signal.SIG_BLOCK,
                {handoff_signum},
            )
            previous_handler = real_signal(installed_signum, handler)
            os.kill(os.getpid(), handoff_signum)
            if handoff_observed is not None:
                handoff_observed.set()
            real_pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            return previous_handler
        return real_signal(installed_signum, handler)

    def phase_handler(
        _attempt: driver.CommandAttempt,
        *,
        root: Path,
        clock: driver.Clock,
        args: object,
        authorization: driver.WindowAuthorization,
        _cleanup_incomplete_observer: Callable[[], None] | None = None,
    ) -> cli._TrustedPhaseResult:
        del clock, args
        path = driver.run_phase(
            harness.config,
            harness.providers,
            root=root,
            _cleanup_incomplete_observer=_cleanup_incomplete_observer,
        )
        return cli._phase_artifact_result(
            str(path.relative_to(root)),
            expected_phase=harness.config.phase,
            expected_window_id=authorization.window_id,
            root=root,
        )

    monkeypatch.setattr(driver.RehearsalServerLauncher, "spawn", spawn_real_binary)
    monkeypatch.setattr(driver, "_raise_binary_spawn_failure", record_failure)
    monkeypatch.setattr(
        driver,
        "_capture_target_identity",
        lambda _pid: (_ for _ in ()).throw(OSError("identity unavailable")),
    )
    monkeypatch.setattr(driver.RehearsalJournalFactory, "create", failing_journal)
    monkeypatch.setattr(
        driver,
        "_finish_binary_stderr_capture",
        finish_with_one_interruption,
    )
    monkeypatch.setattr(driver, "_finish_failed_phase", observe_cleanup_terminal)
    monkeypatch.setattr(driver.signal, "signal", signal_at_phase_cli_handoff)
    monkeypatch.setattr(cli, "_phase_handler", phase_handler)
    monkeypatch.setattr(
        driver,
        "parse_window_authorization",
        lambda _payload: authorization,
    )
    monkeypatch.setattr(
        driver,
        "open_bench_file",
        lambda relative, *, root: (
            b"task2-authority"
            if relative == "task2-authority.json"
            else real_open(relative, root=root)
        ),
    )
    handler = cli._ProductionPhaseHandler(
        clock=driver.SystemClock(),
        args=object(),  # type: ignore[arg-type]
        _guard=cli._PRODUCTION_PHASE_HANDLER_GUARD,
    )
    result = cli._run_command(
        "vulkan-baseline",
        handler,
        root=root,
        clock=driver.SystemClock(),
        authority_ref="task2-authority.json",
    )
    return result, carriers


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


def _run_task3_admitted_binary_failure(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    literal: bytes,
    termination: str = "exit",
    spawned_out: list[driver.OwnedChild] | None = None,
) -> Path:
    from tests.test_cuda_bench_driver import _b7_harness, _free_loopback_port

    root.chmod(0o700)
    harness = _b7_harness(root, nonce=hashlib.sha256(literal).hexdigest())
    launcher = driver.RealServerLauncher(_binary_pin(Path("/usr/bin/bash")))
    spawned: list[driver.OwnedChild] = []

    def spawn_real_binary(
        _launcher: driver.RehearsalServerLauncher,
        _argv: list[str],
        _env: dict[str, str],
    ) -> driver.OwnedChild:
        terminal = {
            "exit": "exit 23",
            "signal": "kill -TERM $$",
            "finalizer": "while :; do :; done",
        }[termination]
        escaped_literal = "".join(f"\\{value:03o}" for value in literal)
        child = launcher.spawn(
            [
                "/usr/bin/bash",
                "-c",
                f"printf '{escaped_literal}' >&2; sleep 0.1; {terminal}",
                "task3",
                "--port",
                str(driver.BENCH_PORT),
            ],
            _binary_env(),
        )
        generation = harness.rehearsal_ports.reserve_launch()
        rehearsal_port = _free_loopback_port()
        lease = harness.rehearsal_ports.activate_from_launcher(
            generation,
            rehearsal_port,
        )
        expected_pin = harness.providers.server_launcher.pin
        child = replace(
            child,
            port=rehearsal_port,
            pinned_path=str(expected_pin.pinned_path),
            pinned_sha256=expected_pin.pinned_sha256,
            rehearsal_port_lease=lease,
        )
        spawned.append(child)
        if spawned_out is not None:
            spawned_out.append(child)
        if termination != "finalizer":
            child.popen.wait(timeout=3)
        return child

    monkeypatch.setattr(driver.RehearsalServerLauncher, "spawn", spawn_real_binary)
    path = driver.run_phase(harness.config, harness.providers, root=root)
    assert len(spawned) == 1
    assert spawned[0]._stderr_capture is not None
    assert spawned[0]._stderr_capture.consumed is True
    assert spawned[0]._stderr_capture.thread_alive is False
    assert literal not in repr(spawned[0]).encode()
    return path


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
        matching_child_fds: list[int] = []
        for fd in Path(f"/proc/{popen.pid}/fd").iterdir():
            try:
                target = fd.readlink()
            except FileNotFoundError:
                continue
            if target == Path(f"pipe:[{stderr_pipe_inode}]"):
                matching_child_fds.append(int(fd.name))
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


def test_task1_inflight_read_is_charged_after_finish_marker_is_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr_read, stderr_write = os.pipe2(os.O_CLOEXEC)
    os.set_blocking(stderr_read, False)
    control_read, control_write = os.pipe2(os.O_CLOEXEC)
    capture = driver._BinaryStderrCapture(
        stderr_read,
        control_read,
        control_write,
    )
    real_read = os.read
    real_write = os.write
    read_started = threading.Event()
    release_read = threading.Event()
    finish_marker_sent = threading.Event()
    observation_lock = threading.Lock()
    post_finish_bytes = 0
    finish_marker_at: float | None = None
    post_finish_read_times: list[float] = []
    finish_result: list[object] = []
    finish_errors: list[BaseException] = []

    def synchronized_read(fd: int, byte_count: int) -> bytes:
        nonlocal post_finish_bytes
        if fd == stderr_read and not read_started.is_set():
            read_started.set()
            assert release_read.wait(timeout=2)
        payload = real_read(fd, byte_count)
        observed_at = time.monotonic()
        if fd == stderr_read and finish_marker_sent.is_set():
            with observation_lock:
                post_finish_bytes += len(payload)
                post_finish_read_times.append(observed_at)
        return payload

    def observed_write(fd: int, payload: bytes) -> int:
        nonlocal finish_marker_at
        written = real_write(fd, payload)
        if fd == control_write and payload == driver._BINARY_STDERR_FINISH_BYTE:
            finish_marker_at = time.monotonic()
            finish_marker_sent.set()
        return written

    def produce() -> None:
        try:
            while True:
                real_write(stderr_write, b"x" * 4096)
        except BrokenPipeError:
            pass
        finally:
            os.close(stderr_write)

    def finish() -> None:
        try:
            finish_result.append(driver._finish_binary_stderr_capture(capture))
        except BaseException as exc:
            finish_errors.append(exc)

    monkeypatch.setattr(driver.os, "read", synchronized_read)
    monkeypatch.setattr(driver.os, "write", observed_write)
    capture._start()
    producer = threading.Thread(target=produce, name="test-racing-stderr-producer")
    producer.start()
    assert read_started.wait(timeout=2)
    finisher = threading.Thread(target=finish, name="test-racing-stderr-finisher")
    finisher.start()
    assert finish_marker_sent.wait(timeout=2)
    release_read.set()
    finisher.join(timeout=3)
    producer.join(timeout=3)

    assert not finisher.is_alive()
    assert not producer.is_alive()
    assert finish_errors == []
    assert len(finish_result) == 1
    assert post_finish_bytes <= _EXPECTED_CAPTURE_CAP
    assert finish_marker_at is not None
    assert all(
        observed_at - finish_marker_at <= 1.0
        for observed_at in post_finish_read_times
    )


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


def test_task2_post_popen_identity_failure_carries_fixed_cleanup_and_live_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = Path("/usr/bin/bash")
    launcher = driver.RealServerLauncher(_binary_pin(executable))
    journal = _task2_journal(tmp_path)
    monkeypatch.setattr(
        driver,
        "_capture_target_identity",
        lambda _pid: (_ for _ in ()).throw(OSError("identity unavailable")),
    )

    try:
        with pytest.raises(driver._BinarySpawnFailure) as caught:
            launcher.spawn(
                _task2_identity_failure_argv(retained_writer=False),
                _binary_env(),
            )
        failure = caught.value
        assert failure.code == "spawn_failure"
        assert failure.args == ("spawn_failure",)
        assert str(failure) == "spawn_failure"
        assert repr(failure) == "_BinarySpawnFailure('spawn_failure')"
        assert "task2-private-stderr" not in repr(failure)
        assert failure._bootstrap_cleanup.outcome == "clean"
        assert failure._bootstrap_cleanup.observed_returncode == -signal.SIGKILL
        assert failure._bootstrap_cleanup.exited_before_cleanup_signal is False
        assert failure._stderr_capture.consumed is False

        with pytest.raises(driver.BenchRefusal, match="^spawn_failure$"):
            driver._dispose_binary_spawn_failure(
                failure,
                journal=journal,  # type: ignore[arg-type]
                clock=driver.SystemClock(),
                cycle=1,
                attempt_root=tmp_path,
            )
        assert failure._stderr_capture.consumed is True
        records = [
            json.loads(line)
            for line in journal.path.read_text(encoding="utf-8").splitlines()
        ]
        assert [record["transition"] for record in records[-2:]] == [
            "cycle_1_bootstrap_cleanup",
            "cycle_1_stderr_diagnostic",
        ]
        assert records[-2]["detail"] == {"outcome": "clean"}
        diagnostic_path = tmp_path / "diagnostics/cycle-1-stderr.bin"
        retained = diagnostic_path.read_bytes()
        assert b"task2-private-stderr".startswith(retained)
        assert stat.S_IMODE(diagnostic_path.stat().st_mode) == 0o600
        assert records[-1]["detail"] == {
            "exited_before_finalize": False,
            "retained_byte_count": len(retained),
            "retained_sha256": hashlib.sha256(retained).hexdigest(),
            "terminating_signal": signal.SIGKILL,
            "truncated": False,
        }
    finally:
        journal.close()


def test_task2_retained_descendant_observes_pipe_retirement_only_after_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = Path("/usr/bin/bash")
    launcher = driver.RealServerLauncher(_binary_pin(executable))
    observed_path = tmp_path / "epipe-observed"
    descendant_pid_path = tmp_path / "descendant-pid"
    journal = _task2_journal(tmp_path)
    captured: list[subprocess.Popen[bytes]] = []
    deliberately_signalled_pids: list[int | None] = []
    real_popen = subprocess.Popen
    real_pidfd_signal = signal.pidfd_send_signal
    real_finish_capture = driver._finish_binary_stderr_capture
    descendant_pid: int | None = None
    descendant_pidfd: int | None = None

    def recording_popen(
        *args: object, **kwargs: object
    ) -> subprocess.Popen[bytes]:
        proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
        captured.append(proc)
        return proc

    def fail_after_descendant_started(_pid: int) -> tuple[int, int, str]:
        assert _wait_for(descendant_pid_path.exists)
        raise OSError("identity unavailable")

    def recording_pidfd_signal(
        pidfd: int,
        signum: int,
        siginfo: object = None,
        flags: int = 0,
    ) -> None:
        _state, bound_pid = driver._pidfd_bound_pid(pidfd)
        deliberately_signalled_pids.append(bound_pid)
        real_pidfd_signal(pidfd, signum, siginfo, flags)

    def finish_after_durable_record(capture: object) -> object:
        assert journal.bootstrap_cleanup_appended.is_set()
        return real_finish_capture(capture)  # type: ignore[arg-type]

    monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(driver, "_capture_target_identity", fail_after_descendant_started)
    monkeypatch.setattr(driver.signal, "pidfd_send_signal", recording_pidfd_signal)
    monkeypatch.setattr(
        driver,
        "_finish_binary_stderr_capture",
        finish_after_durable_record,
    )

    with _child_subreaper():
        try:
            with pytest.raises(driver.BenchRefusal, match="^cleanup_incomplete$"):
                driver._spawn_with_interrupt_handoff(
                    launcher,
                    _task2_identity_failure_argv(
                        retained_writer=True,
                        observed_path=observed_path,
                        descendant_pid_path=descendant_pid_path,
                    ),
                    _binary_env(),
                    admit=lambda _child: pytest.fail("identity failure was admitted"),
                    journal=journal,  # type: ignore[arg-type]
                    clock=driver.SystemClock(),
                    cycle=1,
                    attempt_root=tmp_path,
                )

            descendant_pid = int(descendant_pid_path.read_text(encoding="utf-8"))
            descendant_pidfd = os.pidfd_open(descendant_pid)
            assert journal.bootstrap_cleanup_appended.is_set()
            assert _wait_for(observed_path.exists)
            records = [
                json.loads(line)
                for line in journal.path.read_text(encoding="utf-8").splitlines()
            ]
            transitions = [record["transition"] for record in records]
            assert transitions.index("cycle_1_bootstrap_cleanup") < transitions.index(
                "cycle_1_stderr_diagnostic"
            )
            cleanup = next(
                record
                for record in records
                if record["transition"] == "cycle_1_bootstrap_cleanup"
            )
            assert cleanup["detail"] == {"outcome": "cleanup_incomplete"}
            assert len(captured) == 1
            assert deliberately_signalled_pids == [captured[0].pid]
            assert descendant_pid not in deliberately_signalled_pids
        finally:
            if descendant_pidfd is not None:
                try:
                    real_pidfd_signal(descendant_pidfd, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass
                os.close(descendant_pidfd)
            if descendant_pid is not None:
                try:
                    os.waitpid(descendant_pid, 0)
                except ChildProcessError:
                    pass
                assert _wait_for(
                    lambda: not Path(f"/proc/{descendant_pid}").exists()
                )
            for proc in captured:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3)
            journal.close()


def test_task2_capture_retirement_uncertainty_supersedes_original_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = Path("/usr/bin/bash")
    launcher = driver.RealServerLauncher(_binary_pin(executable))
    journal = _task2_journal(tmp_path)
    monkeypatch.setattr(
        driver,
        "_capture_target_identity",
        lambda _pid: (_ for _ in ()).throw(OSError("identity unavailable")),
    )
    original_finish = driver._finish_binary_stderr_capture

    try:
        with pytest.raises(driver._BinarySpawnFailure) as caught:
            launcher.spawn(
                _task2_identity_failure_argv(retained_writer=False),
                _binary_env(),
            )
        failure = caught.value
        monkeypatch.setattr(
            driver,
            "_finish_binary_stderr_capture",
            lambda _capture: (_ for _ in ()).throw(
                driver.BenchRefusal("cleanup_incomplete")
            ),
        )

        with pytest.raises(driver.BenchRefusal) as disposed:
            driver._dispose_binary_spawn_failure(
                failure,
                journal=journal,  # type: ignore[arg-type]
                clock=driver.SystemClock(),
                cycle=1,
                attempt_root=tmp_path,
            )
        assert disposed.value.code == "cleanup_incomplete"
        assert journal.bootstrap_cleanup_appended.is_set()
    finally:
        monkeypatch.setattr(driver, "_finish_binary_stderr_capture", original_finish)
        if "failure" in locals() and not failure._stderr_capture.consumed:
            original_finish(failure._stderr_capture)
        journal.close()


def test_task2_cleanup_observer_failure_cannot_soften_driver_latch() -> None:
    observed = 0

    def failing_observer() -> None:
        nonlocal observed
        observed += 1
        raise KeyboardInterrupt("task2 observer failure")

    lifecycle = driver._PhaseLifecycleState(
        cleanup_incomplete_observer=failing_observer,
    )

    lifecycle.latch_cleanup_incomplete(storage_unavailable=True)
    lifecycle.latch_cleanup_incomplete()

    assert observed == 1
    assert lifecycle.cleanup_incomplete_latched is True
    assert lifecycle.cleanup_storage_unavailable is True


@pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
def test_task2_pending_signal_cannot_override_storage_failed_cleanup_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    signum: int,
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    carriers: list[driver._BinarySpawnFailure] = []
    real_finish = driver._finish_binary_stderr_capture

    try:
        exit_code, carriers = _run_task2_real_phase_failure_through_cli(
            tmp_path,
            monkeypatch,
            journal_failure=lambda: driver.BenchRefusal("journal_failure"),
            pending_signum=signum,
        )
        captured = capfd.readouterr()

        assert exit_code == 4
        assert captured.err == ""
        assert json.loads(captured.out) == {
            "artifact_ref": None,
            "artifact_sha256": None,
            "outcome": "cleanup_incomplete",
            "status": "failed",
            "window_id": "window-b7",
        }
        assert len(carriers) == 1
        assert carriers[0]._stderr_capture.consumed is True
        assert carriers[0]._stderr_capture.thread_alive is False
        assert not list(tmp_path.rglob("vulkan_baseline-*.json"))
        assert not list(tmp_path.rglob("*command-completion*.json"))
    finally:
        for carrier in carriers:
            if not carrier._stderr_capture.consumed:
                real_finish(carrier._stderr_capture)

    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


@pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
def test_task2_pending_signal_at_phase_cli_handoff_cannot_override_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    signum: int,
) -> None:
    handoff_observed = threading.Event()

    exit_code, _carriers = _run_task2_real_phase_failure_through_cli(
        tmp_path,
        monkeypatch,
        journal_failure=lambda: driver.BenchRefusal("journal_failure"),
        handoff_signum=signum,
        handoff_observed=handoff_observed,
    )
    captured = capfd.readouterr()

    assert handoff_observed.is_set()
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "artifact_ref": None,
        "artifact_sha256": None,
        "outcome": "cleanup_incomplete",
        "status": "failed",
        "window_id": "window-b7",
    }
    assert exit_code == 4
    assert not list(tmp_path.rglob("vulkan_baseline-*.json"))
    assert not list(tmp_path.rglob("*command-completion*.json"))


def test_task2_journal_keyboard_interrupt_cannot_bypass_capture_retirement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    carriers: list[driver._BinarySpawnFailure] = []
    real_finish = driver._finish_binary_stderr_capture

    try:
        exit_code, carriers = _run_task2_real_phase_failure_through_cli(
            tmp_path,
            monkeypatch,
            journal_failure=lambda: KeyboardInterrupt("task2 journal interrupt"),
        )
        captured = capfd.readouterr()

        assert exit_code == 4
        assert captured.err == ""
        assert json.loads(captured.out) == {
            "artifact_ref": None,
            "artifact_sha256": None,
            "outcome": "cleanup_incomplete",
            "status": "failed",
            "window_id": "window-b7",
        }
        assert len(carriers) == 1
        assert carriers[0]._stderr_capture.consumed is True
        assert carriers[0]._stderr_capture.thread_alive is False
        assert not list(tmp_path.rglob("vulkan_baseline-*.json"))
        assert not list(tmp_path.rglob("*command-completion*.json"))
    finally:
        for carrier in carriers:
            if not carrier._stderr_capture.consumed:
                real_finish(carrier._stderr_capture)

    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


def test_task2_retirement_keyboard_interrupt_still_retires_capture_boundedly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    carriers: list[driver._BinarySpawnFailure] = []
    real_finish = driver._finish_binary_stderr_capture

    try:
        exit_code, carriers = _run_task2_real_phase_failure_through_cli(
            tmp_path,
            monkeypatch,
            journal_failure=lambda: driver.BenchRefusal("journal_failure"),
            interrupt_retirement=True,
        )
        captured = capfd.readouterr()

        assert exit_code == 4
        assert captured.err == ""
        assert json.loads(captured.out) == {
            "artifact_ref": None,
            "artifact_sha256": None,
            "outcome": "cleanup_incomplete",
            "status": "failed",
            "window_id": "window-b7",
        }
        assert len(carriers) == 1
        assert carriers[0]._stderr_capture.consumed is True
        assert carriers[0]._stderr_capture.thread_alive is False
        assert not list(tmp_path.rglob("vulkan_baseline-*.json"))
        assert not list(tmp_path.rglob("*command-completion*.json"))
    finally:
        for carrier in carriers:
            if not carrier._stderr_capture.consumed:
                real_finish(carrier._stderr_capture)

    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


def test_task2_failed_journal_still_retires_retained_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    executable = Path("/usr/bin/bash")
    launcher = driver.RealServerLauncher(_binary_pin(executable))
    observed_path = tmp_path / "journal-failure-epipe"
    descendant_pid_path = tmp_path / "journal-failure-descendant"
    journal = _FailingJournal(_task2_journal(tmp_path)._journal)
    captured: list[subprocess.Popen[bytes]] = []
    carriers: list[driver._BinarySpawnFailure] = []
    real_popen = subprocess.Popen
    real_raise_failure = driver._raise_binary_spawn_failure
    real_finish_capture = driver._finish_binary_stderr_capture
    real_pidfd_signal = signal.pidfd_send_signal
    descendant_pid: int | None = None
    descendant_pidfd: int | None = None

    def recording_popen(
        *args: object, **kwargs: object
    ) -> subprocess.Popen[bytes]:
        proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
        captured.append(proc)
        return proc

    def fail_after_descendant_started(_pid: int) -> tuple[int, int, str]:
        assert _wait_for(descendant_pid_path.exists)
        raise OSError("identity unavailable")

    def record_failure(
        exc: BaseException,
        *,
        bootstrap_cleanup: driver._BootstrapCleanupResult,
        stderr_capture: driver._BinaryStderrCapture,
    ) -> None:
        try:
            real_raise_failure(
                exc,
                bootstrap_cleanup=bootstrap_cleanup,
                stderr_capture=stderr_capture,
            )
        except driver._BinarySpawnFailure as failure:
            carriers.append(failure)
            raise

    monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(driver, "_capture_target_identity", fail_after_descendant_started)
    monkeypatch.setattr(driver, "_raise_binary_spawn_failure", record_failure)

    with _child_subreaper():
        try:
            with pytest.raises(driver.BenchRefusal) as caught:
                driver._spawn_with_interrupt_handoff(
                    launcher,
                    _task2_identity_failure_argv(
                        retained_writer=True,
                        observed_path=observed_path,
                        descendant_pid_path=descendant_pid_path,
                    ),
                    _binary_env(),
                    admit=lambda _child: pytest.fail("identity failure was admitted"),
                    journal=journal,  # type: ignore[arg-type]
                    clock=driver.SystemClock(),
                    cycle=1,
                    attempt_root=tmp_path,
                )
            assert caught.value.code == "cleanup_incomplete"
            assert journal.bootstrap_cleanup_appended.is_set()
            assert len(carriers) == 1
            assert carriers[0]._stderr_capture.consumed is True
            assert not carriers[0]._stderr_capture.thread_alive
            assert _wait_for(observed_path.exists)
            assert journal.path.read_bytes() == b""

        finally:
            if carriers and not carriers[0]._stderr_capture.consumed:
                real_finish_capture(carriers[0]._stderr_capture)
            if descendant_pid_path.exists():
                descendant_pid = int(
                    descendant_pid_path.read_text(encoding="utf-8")
                )
                try:
                    descendant_pidfd = os.pidfd_open(descendant_pid)
                except ProcessLookupError:
                    descendant_pidfd = None
            if descendant_pidfd is not None:
                try:
                    real_pidfd_signal(descendant_pidfd, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass
                os.close(descendant_pidfd)
            if descendant_pid is not None:
                try:
                    os.waitpid(descendant_pid, 0)
                except ChildProcessError:
                    pass
                assert _wait_for(
                    lambda: not Path(f"/proc/{descendant_pid}").exists()
                )
            for proc in captured:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3)
            journal.close()

    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


def test_task2_every_production_launcher_call_uses_disposal_helper() -> None:
    module = ast.parse(inspect.getsource(driver))
    launcher_calls: list[tuple[str, str]] = []
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "spawn"
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "launcher"
            ):
                launcher_calls.append((node.name, ast.unparse(child)))
    assert launcher_calls == [
        ("_spawn_with_interrupt_handoff", "launcher.spawn(argv, env)")
    ]
    helper_source = inspect.getsource(driver._spawn_with_interrupt_handoff)
    assert "except _BinarySpawnFailure as failure:" in helper_source
    assert "_dispose_binary_spawn_failure(" in helper_source


@pytest.mark.parametrize(
    ("persona", "expected_status", "first_status_races_alive"),
    (
        ("false", {"exit_code": 1}, False),
        ("false_binding_race", {"exit_code": 1}, True),
        ("signal", {"terminating_signal": signal.SIGTERM}, False),
    ),
)
def test_task3_real_elf_pre_admission_natural_status_is_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    persona: str,
    expected_status: dict[str, int],
    first_status_races_alive: bool,
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    literal = (
        b""
        if persona.startswith("false")
        else b"task3-pre-admission-raw-819ca2"
    )
    executable = Path(
        "/usr/bin/false" if persona.startswith("false") else "/usr/bin/bash"
    )
    _assert_dynamic_elf(executable)
    launcher = driver.RealServerLauncher(_binary_pin(executable))
    escaped_literal = "".join(f"\\{value:03o}" for value in literal)
    argv = (
        [str(executable), "--port", str(driver.BENCH_PORT)]
        if persona.startswith("false")
        else [
            str(executable),
            "-c",
            f"printf '{escaped_literal}' >&2; kill -TERM $$",
            "task3",
            "--port",
            str(driver.BENCH_PORT),
        ]
    )
    expected_returncode = (
        1 if persona.startswith("false") else -signal.SIGTERM
    )
    journal = _task2_journal(tmp_path)
    spawned: list[subprocess.Popen[bytes]] = []
    real_popen = subprocess.Popen
    real_pidfd_status = driver._pidfd_status
    real_pidfd_send_signal = signal.pidfd_send_signal
    status_checks = 0
    sent_signals: list[int] = []

    def recording_popen(
        *args: object, **kwargs: object
    ) -> subprocess.Popen[bytes]:
        proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
        spawned.append(proc)
        return proc

    def fail_identity_after_natural_exit(pid: int) -> tuple[int, int, str]:
        assert len(spawned) == 1
        assert spawned[0].pid == pid
        assert _wait_for(lambda: spawned[0].poll() is not None)
        assert spawned[0].returncode == expected_returncode
        raise OSError("identity unavailable after natural exit")

    def race_status_before_binding(pidfd: int) -> str:
        nonlocal status_checks
        status_checks += 1
        if first_status_races_alive and status_checks == 1:
            assert real_pidfd_status(pidfd) == "gone"
            return "alive"
        return real_pidfd_status(pidfd)

    def record_pidfd_signal(
        pidfd: int,
        signum: int,
        siginfo: object = None,
        flags: int = 0,
    ) -> None:
        sent_signals.append(signum)
        real_pidfd_send_signal(pidfd, signum, siginfo, flags)

    monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(driver, "_pidfd_status", race_status_before_binding)
    monkeypatch.setattr(driver.signal, "pidfd_send_signal", record_pidfd_signal)
    monkeypatch.setattr(
        driver,
        "_capture_target_identity",
        fail_identity_after_natural_exit,
    )

    try:
        with pytest.raises(driver.BenchRefusal) as caught:
            driver._spawn_with_interrupt_handoff(
                launcher,
                argv,
                _binary_env(),
                admit=lambda _child: pytest.fail("dead target was admitted"),
                journal=journal,  # type: ignore[arg-type]
                clock=driver.SystemClock(),
                cycle=1,
                attempt_root=tmp_path,
            )
        captured = capfd.readouterr()
        records = [
            json.loads(line)
            for line in journal.path.read_text(encoding="utf-8").splitlines()
        ]
        transitions = [record["transition"] for record in records]
        metadata = next(
            record["detail"]
            for record in records
            if record["transition"] == "cycle_1_stderr_diagnostic"
        )
        diagnostic_path = tmp_path / "diagnostics/cycle-1-stderr.bin"
        retained = diagnostic_path.read_bytes()

        assert transitions[-2:] == [
            "cycle_1_bootstrap_cleanup",
            "cycle_1_stderr_diagnostic",
        ]
        assert "cycle_1_finalize" not in transitions
        assert records[-2]["detail"] == {"outcome": "clean"}
        if literal:
            assert retained == literal
        else:
            assert retained
        assert stat.S_IMODE(diagnostic_path.stat().st_mode) == 0o600
        assert metadata == {
            "exited_before_finalize": True,
            "retained_byte_count": len(retained),
            "retained_sha256": hashlib.sha256(retained).hexdigest(),
            "truncated": False,
            **expected_status,
        }
        assert sent_signals == []
        assert caught.value.code == "spawn_failure"
        assert captured.out == ""
        assert captured.err == ""
        assert all(
            retained not in path.read_bytes()
            for path in tmp_path.rglob("*")
            if retained and path.is_file() and path != diagnostic_path
        )
        assert retained.decode(errors="surrogateescape") not in repr(records)
        assert not list(tmp_path.rglob("*command-completion*.json"))
        assert not list(tmp_path.rglob("*completed*.json"))
        assert len(spawned) == 1
        assert spawned[0].returncode == expected_returncode
        assert not Path(f"/proc/{spawned[0].pid}").exists()
    finally:
        journal.close()

    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


def test_task3_uncertain_bootstrap_natural_exit_has_no_cleanup_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    executable = Path("/usr/bin/bash")
    _assert_dynamic_elf(executable)
    ready_path = tmp_path / "uncertain-ready"
    release_path = tmp_path / "uncertain-release"
    script = (
        'printf ready > "$1"; '
        'while [ ! -e "$2" ]; do :; done; '
        "exit 37"
    )
    journal = _task2_journal(tmp_path)
    spawned: list[subprocess.Popen[bytes]] = []
    sent_signals: list[int] = []
    real_popen = subprocess.Popen
    real_pidfd_send_signal = signal.pidfd_send_signal
    status_checks = 0

    def recording_popen(
        *args: object, **kwargs: object
    ) -> subprocess.Popen[bytes]:
        proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
        spawned.append(proc)
        return proc

    def fail_identity_while_target_alive(pid: int) -> tuple[int, int, str]:
        assert len(spawned) == 1
        assert spawned[0].pid == pid
        assert _wait_for(ready_path.exists)
        assert spawned[0].poll() is None
        raise OSError("identity status unavailable while target lives")

    def uncertain_then_release(_pidfd: int) -> str:
        nonlocal status_checks
        status_checks += 1
        assert status_checks == 1
        release_path.write_text("release", encoding="utf-8")
        return "uncertain"

    def record_pidfd_signal(
        pidfd: int,
        signum: int,
        siginfo: object = None,
        flags: int = 0,
    ) -> None:
        sent_signals.append(signum)
        real_pidfd_send_signal(pidfd, signum, siginfo, flags)

    monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(
        driver,
        "_capture_target_identity",
        fail_identity_while_target_alive,
    )
    monkeypatch.setattr(driver, "_pidfd_status", uncertain_then_release)
    monkeypatch.setattr(driver.signal, "pidfd_send_signal", record_pidfd_signal)

    try:
        with pytest.raises(driver._BinarySpawnFailure) as caught:
            driver.spawn_pinned(
                [
                    str(executable),
                    "-c",
                    script,
                    "task3",
                    str(ready_path),
                    str(release_path),
                ],
                pin=_binary_pin(executable),
                env=_binary_env(),
                admitted_port=driver.BENCH_PORT,
            )
        failure = caught.value
        with pytest.raises(driver.BenchRefusal) as disposed:
            driver._dispose_binary_spawn_failure(
                failure,
                journal=journal,  # type: ignore[arg-type]
                clock=driver.SystemClock(),
                cycle=1,
                attempt_root=tmp_path,
            )
        records = [
            json.loads(line)
            for line in journal.path.read_text(encoding="utf-8").splitlines()
        ]
        metadata = next(
            record["detail"]
            for record in records
            if record["transition"] == "cycle_1_stderr_diagnostic"
        )
        diagnostic_path = tmp_path / "diagnostics/cycle-1-stderr.bin"

        assert sent_signals == []
        assert failure._bootstrap_cleanup.outcome == "cleanup_incomplete"
        assert failure._bootstrap_cleanup.observed_returncode == 37
        assert failure._bootstrap_cleanup.exited_before_cleanup_signal is True
        assert disposed.value.code == "cleanup_incomplete"
        assert records[-2]["detail"] == {"outcome": "cleanup_incomplete"}
        assert metadata == {
            "exit_code": 37,
            "exited_before_finalize": True,
            "retained_byte_count": 0,
            "retained_sha256": hashlib.sha256(b"").hexdigest(),
            "truncated": False,
        }
        assert diagnostic_path.read_bytes() == b""
        assert stat.S_IMODE(diagnostic_path.stat().st_mode) == 0o600
        assert not list(tmp_path.rglob("*command-completion*.json"))
        assert len(spawned) == 1
        assert spawned[0].returncode == 37
        assert not Path(f"/proc/{spawned[0].pid}").exists()
    finally:
        if (
            "failure" in locals()
            and not failure._stderr_capture.consumed
        ):
            driver._finish_binary_stderr_capture(failure._stderr_capture)
        for proc in spawned:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)
        journal.close()

    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


def test_task3_pre_release_inert_guard_has_no_target_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    executable = Path("/usr/bin/false")
    _assert_dynamic_elf(executable)
    launcher = driver.RealServerLauncher(_binary_pin(executable))
    journal = _task2_journal(tmp_path)
    spawned: list[subprocess.Popen[bytes]] = []
    real_popen = subprocess.Popen
    real_pidfd_bound_pid = driver._pidfd_bound_pid
    binding_checks = 0

    def recording_popen(
        *args: object, **kwargs: object
    ) -> subprocess.Popen[bytes]:
        proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
        spawned.append(proc)
        return proc

    def fail_first_binding(pidfd: int) -> tuple[str, int | None]:
        nonlocal binding_checks
        binding_checks += 1
        if binding_checks == 1:
            return "unavailable", None
        return real_pidfd_bound_pid(pidfd)

    monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
    monkeypatch.setattr(driver, "_pidfd_bound_pid", fail_first_binding)

    try:
        with pytest.raises(driver.BenchRefusal, match="^spawn_failure$"):
            driver._spawn_with_interrupt_handoff(
                launcher,
                [str(executable), "--port", str(driver.BENCH_PORT)],
                _binary_env(),
                admit=lambda _child: pytest.fail("inert guard was admitted"),
                journal=journal,  # type: ignore[arg-type]
                clock=driver.SystemClock(),
                cycle=1,
                attempt_root=tmp_path,
            )
        records = [
            json.loads(line)
            for line in journal.path.read_text(encoding="utf-8").splitlines()
        ]
        metadata = next(
            record["detail"]
            for record in records
            if record["transition"] == "cycle_1_stderr_diagnostic"
        )

        assert metadata == {
            "exited_before_finalize": False,
            "retained_byte_count": 0,
            "retained_sha256": hashlib.sha256(b"").hexdigest(),
            "truncated": False,
        }
        assert len(spawned) == 1
        assert spawned[0].returncode is not None
        assert not Path(f"/proc/{spawned[0].pid}").exists()
    finally:
        journal.close()

    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


@pytest.mark.parametrize(
    ("termination", "status_detail"),
    (
        ("exit", {"exit_code": 23}),
        ("signal", {"terminating_signal": signal.SIGTERM}),
    ),
)
def test_task3_real_elf_admitted_binary_publishes_after_finalize_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    termination: str,
    status_detail: dict[str, int],
) -> None:
    literal = f"task3-raw-only-{termination}-4b83a1".encode()
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    real_finish = driver._finish_binary_stderr_capture

    def finish_after_finalize_record(
        capture: driver._BinaryStderrCapture | None,
    ) -> driver._BinaryStderrSnapshot | None:
        journal_path = next(tmp_path.rglob("*-journal.jsonl"))
        records = [
            json.loads(line)
            for line in journal_path.read_text(encoding="utf-8").splitlines()
        ]
        assert any(
            record["transition"] == "cycle_1_finalize"
            and set(record["detail"])
            == {
                "outcome",
                "signals_sent",
                "quadruple_reproofs",
                "surviving_pgid_members",
                "listener_free",
                "started_at",
                "finished_at",
            }
            for record in records
        )
        return real_finish(capture)

    monkeypatch.setattr(
        driver,
        "_finish_binary_stderr_capture",
        finish_after_finalize_record,
    )

    packet_path = _run_task3_admitted_binary_failure(
        tmp_path,
        monkeypatch,
        literal=literal,
        termination=termination,
    )
    captured = capfd.readouterr()
    attempt_root = packet_path.parents[2]
    diagnostic_path = attempt_root / "diagnostics/cycle-1-stderr.bin"
    journal_path = next(attempt_root.rglob("*-journal.jsonl"))
    records = [
        json.loads(line)
        for line in journal_path.read_text(encoding="utf-8").splitlines()
    ]
    transitions = [record["transition"] for record in records]
    metadata = next(
        record["detail"]
        for record in records
        if record["transition"] == "cycle_1_stderr_diagnostic"
    )

    assert json.loads(packet_path.read_bytes())["payload"]["fields"]["outcome"] == (
        "crash"
    )
    assert transitions.index("cycle_1_finalize") < transitions.index(
        "cycle_1_stderr_diagnostic"
    )
    assert diagnostic_path.read_bytes() == literal
    diagnostic_info = diagnostic_path.stat()
    assert stat.S_ISREG(diagnostic_info.st_mode)
    assert stat.S_IMODE(diagnostic_info.st_mode) == 0o600
    assert diagnostic_info.st_nlink == 1
    assert metadata == {
        "exited_before_finalize": True,
        "retained_byte_count": len(literal),
        "retained_sha256": hashlib.sha256(literal).hexdigest(),
        "truncated": False,
        **status_detail,
    }
    assert captured.out == ""
    assert captured.err == ""
    assert all(
        literal not in path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file() and path != diagnostic_path
    )
    assert literal.decode() not in repr(metadata)
    assert not list(attempt_root.rglob("*command-completion*.json"))
    assert not list(attempt_root.rglob("*completed*.json"))
    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


def test_task3_live_admitted_binary_records_finalizer_terminating_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    literal = b"task3-finalizer-signal-31d47c"
    real_finalize = driver.finalize
    returncodes_after_finalize: list[int | None] = []

    def finalize_live_child(
        child: driver.OwnedChild,
        *,
        clock: driver.Clock,
        port_probe: driver.PortProbe,
        port: int | None,
    ) -> driver.FinalizeResult:
        assert child.popen.poll() is None
        result = real_finalize(
            child,
            clock=clock,
            port_probe=port_probe,
            port=port,
        )
        returncodes_after_finalize.append(child.popen.returncode)
        return result

    monkeypatch.setattr(driver, "finalize", finalize_live_child)
    packet_path = _run_task3_admitted_binary_failure(
        tmp_path,
        monkeypatch,
        literal=literal,
        termination="finalizer",
    )
    attempt_root = packet_path.parents[2]
    records = [
        json.loads(line)
        for line in next(attempt_root.rglob("*-journal.jsonl"))
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    finalizer = next(
        record["detail"]
        for record in records
        if record["transition"] == "cycle_1_finalize"
    )
    metadata = next(
        record["detail"]
        for record in records
        if record["transition"] == "cycle_1_stderr_diagnostic"
    )

    assert "SIGTERM" in finalizer["signals_sent"]
    assert returncodes_after_finalize == [-signal.SIGTERM]
    assert metadata == {
        "exited_before_finalize": False,
        "retained_byte_count": len(literal),
        "retained_sha256": hashlib.sha256(literal).hexdigest(),
        "terminating_signal": signal.SIGTERM,
        "truncated": False,
    }
    assert "exit_code" not in metadata


def test_task3_real_elf_publication_failure_has_no_metadata_or_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    literal = b"task3-publication-refused-37c90a"
    real_write = driver.write_private_file

    def fail_diagnostic_write(
        relative: str,
        data: bytes,
        *,
        root: Path = driver.BENCH_ROOT,
        on_link: Callable[[Path], None] | None = None,
    ) -> Path:
        if relative == "diagnostics/cycle-1-stderr.bin":
            raise driver.BenchRefusal("filesystem_hazard")
        return real_write(relative, data, root=root, on_link=on_link)

    monkeypatch.setattr(driver, "write_private_file", fail_diagnostic_write)

    packet_path = _run_task3_admitted_binary_failure(
        tmp_path,
        monkeypatch,
        literal=literal,
    )

    assert json.loads(packet_path.read_bytes())["payload"]["fields"]["outcome"] == (
        "filesystem_hazard"
    )
    assert not list(tmp_path.rglob("cycle-1-stderr.bin"))
    assert not list(tmp_path.rglob("*command-completion*.json"))
    for journal_path in tmp_path.rglob("*-journal.jsonl"):
        assert "stderr_diagnostic" not in journal_path.read_text(encoding="utf-8")
    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


def test_task3_real_elf_capture_cleanup_failure_has_no_file_or_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    literal = b"task3-cleanup-refused-f124b8"
    real_finish = driver._finish_binary_stderr_capture
    failed_once = False

    def finish_then_refuse(
        capture: driver._BinaryStderrCapture | None,
    ) -> driver._BinaryStderrSnapshot | None:
        nonlocal failed_once
        snapshot = real_finish(capture)
        if not failed_once:
            failed_once = True
            raise driver.BenchRefusal("cleanup_incomplete")
        return snapshot

    monkeypatch.setattr(
        driver,
        "_finish_binary_stderr_capture",
        finish_then_refuse,
    )

    packet_path = _run_task3_admitted_binary_failure(
        tmp_path,
        monkeypatch,
        literal=literal,
    )

    assert failed_once is True
    assert json.loads(packet_path.read_bytes())["payload"]["fields"]["outcome"] == (
        "cleanup_incomplete"
    )
    assert not list(tmp_path.rglob("cycle-1-stderr.bin"))
    assert not list(tmp_path.rglob("*command-completion*.json"))
    for journal_path in tmp_path.rglob("*-journal.jsonl"):
        assert "stderr_diagnostic" not in journal_path.read_text(encoding="utf-8")
    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


@pytest.mark.parametrize(
    "snapshot",
    (
        driver._BinaryStderrSnapshot(
            retained=b"x",
            retained_sha256="0" * 64,
            retained_byte_count=1,
            truncated=False,
            post_finish_byte_count=0,
        ),
        driver._BinaryStderrSnapshot(
            retained=b"x",
            retained_sha256=hashlib.sha256(b"x").hexdigest(),
            retained_byte_count=2,
            truncated=False,
            post_finish_byte_count=0,
        ),
        driver._BinaryStderrSnapshot(
            retained=b"x" * (_EXPECTED_CAPTURE_CAP + 1),
            retained_sha256=hashlib.sha256(
                b"x" * (_EXPECTED_CAPTURE_CAP + 1)
            ).hexdigest(),
            retained_byte_count=_EXPECTED_CAPTURE_CAP + 1,
            truncated=True,
            post_finish_byte_count=0,
        ),
    ),
)
def test_task3_metadata_rejects_fabricated_or_unbounded_snapshot(
    snapshot: driver._BinaryStderrSnapshot,
) -> None:
    with pytest.raises(driver.BenchRefusal, match="^cleanup_incomplete$"):
        driver._binary_stderr_metadata(
            snapshot,
            returncode=0,
            exited_before_finalize=True,
        )


def test_task3_real_elf_finalize_journal_interrupt_still_retires_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_fds = _open_fd_identities()
    before_threads = _capture_threads()
    before_sockets = _socket_fd_inodes()
    literal = b"task3-journal-interrupt-b91a72"
    spawned: list[driver.OwnedChild] = []
    real_try_append = driver._try_append_phase_transition
    real_finish = driver._finish_binary_stderr_capture

    def interrupt_finalize_journal(
        journal: driver.PhaseJournal,
        clock: driver.Clock,
        transition: str,
        *,
        detail: Mapping[str, object] | None = None,
    ) -> driver.BenchRefusal | None:
        if transition == "cycle_1_finalize":
            raise KeyboardInterrupt("task3 finalize journal interrupt")
        return real_try_append(journal, clock, transition, detail=detail)

    monkeypatch.setattr(
        driver,
        "_try_append_phase_transition",
        interrupt_finalize_journal,
    )
    consumed_by_driver = False
    packet_path: Path | None = None
    try:
        packet_path = _run_task3_admitted_binary_failure(
            tmp_path,
            monkeypatch,
            literal=literal,
            spawned_out=spawned,
        )
        assert len(spawned) == 1
        capture = spawned[0]._stderr_capture
        assert capture is not None
        consumed_by_driver = capture.consumed and not capture.thread_alive
    finally:
        for child in spawned:
            capture = child._stderr_capture
            if capture is not None and not capture.consumed:
                real_finish(capture)

    assert consumed_by_driver is True
    assert packet_path is not None
    assert json.loads(packet_path.read_bytes())["payload"]["fields"]["outcome"] == (
        "interrupted"
    )
    assert not list(tmp_path.rglob("cycle-1-stderr.bin"))
    for journal_path in tmp_path.rglob("*-journal.jsonl"):
        assert "stderr_diagnostic" not in journal_path.read_text(encoding="utf-8")
    assert _capture_threads() == before_threads
    assert _open_fd_identities() == before_fds
    assert _socket_fd_inodes() == before_sockets


def test_task3_real_elf_terminal_failures_cannot_reach_bundle_or_scorer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_cuda_bench_assemble import _materialize_stage_one
    from tests.test_cuda_bench_driver import _b7_harness

    terminal_payloads: dict[str, bytes] = {}

    refused_root = tmp_path / "refused"
    refused_root.mkdir(mode=0o700)
    refused_harness = _b7_harness(
        refused_root,
        service_active=True,
        nonce="a" * 64,
    )
    refused_path = driver.run_phase(
        refused_harness.config,
        refused_harness.providers,
        root=refused_root,
    )
    terminal_payloads["service_interference"] = refused_path.read_bytes()

    failed_root = tmp_path / "failed"
    failed_root.mkdir(mode=0o700)
    with monkeypatch.context() as local:
        failed_path = _run_task3_admitted_binary_failure(
            failed_root,
            local,
            literal=b"task3-failed-unscoreable-760b31",
        )
    terminal_payloads["crash"] = failed_path.read_bytes()

    cleanup_root = tmp_path / "cleanup"
    cleanup_root.mkdir(mode=0o700)
    real_finish = driver._finish_binary_stderr_capture
    failed_once = False

    def finish_then_refuse(
        capture: driver._BinaryStderrCapture | None,
    ) -> driver._BinaryStderrSnapshot | None:
        nonlocal failed_once
        snapshot = real_finish(capture)
        if not failed_once:
            failed_once = True
            raise driver.BenchRefusal("cleanup_incomplete")
        return snapshot

    with monkeypatch.context() as local:
        local.setattr(
            driver,
            "_finish_binary_stderr_capture",
            finish_then_refuse,
        )
        cleanup_path = _run_task3_admitted_binary_failure(
            cleanup_root,
            local,
            literal=b"task3-cleanup-unscoreable-95d244",
        )
    assert failed_once is True
    terminal_payloads["cleanup_incomplete"] = cleanup_path.read_bytes()

    scorer_calls: list[object] = []
    receipt_calls: list[object] = []

    def forbidden_scorer(bundle: object) -> object:
        scorer_calls.append(bundle)
        raise AssertionError("terminal artifact reached scorer")

    def forbidden_receipt(*args: object, **kwargs: object) -> object:
        receipt_calls.append((args, kwargs))
        raise AssertionError("terminal artifact minted receipt")

    monkeypatch.setattr(driver.cm, "evaluate_promotion_bundle", forbidden_scorer)
    monkeypatch.setattr(driver.cm, "build_receipt", forbidden_receipt)

    for index, (outcome, payload) in enumerate(terminal_payloads.items(), start=1):
        assembler_root = tmp_path / f"assembler-{index}"
        assembler_root.mkdir(mode=0o700)
        paths, _bundle = _materialize_stage_one(assembler_root)
        injected_relative = f"injected/{outcome}.json"
        injected_path = assembler_root / injected_relative
        injected_path.parent.mkdir(mode=0o700)
        injected_path.write_bytes(payload)
        injected_path.chmod(0o600)
        terminal_paths = replace(paths, control_packet=injected_relative)

        with pytest.raises(driver.BenchRefusal, match="^assembly_refused$"):
            assemble.build_stage1_bundle(
                terminal_paths,
                root=assembler_root,
                timestamp="2026-07-13T12:02:10Z",
            )
        with pytest.raises(driver.BenchRefusal, match="^assembly_refused$"):
            assemble.assemble_stage1(
                terminal_paths,
                root=assembler_root,
                timestamp="2026-07-13T12:02:10Z",
            )

    assert scorer_calls == []
    assert receipt_calls == []


def test_task3_diagnostics_are_structurally_absent_from_evidence_and_actions() -> None:
    forbidden = {"diagnostic", "stderr_diagnostic", "stderr_sha256", "stderr_bytes"}
    field_surfaces = (
        driver.FinalizeResult,
        driver.CompletedPhaseEvidence,
        driver.cm.CommandCompletionDoc,
        driver.cm.PhasePacket,
        driver.cm.PersistedDoc,
        driver.cm.BenchEvidenceBundle,
        driver.cm.PromotionVerdict,
        assemble.Stage1ArtifactPaths,
    )
    for surface in field_surfaces:
        names = {field.name.lower() for field in fields(surface)}
        assert all(token not in name for name in names for token in forbidden)

    assert len(fields(assemble.Stage1ArtifactPaths)) == 22
    assert all(
        token not in schema.lower()
        for schema in driver._ARTIFACT_SCHEMAS.values()
        for token in forbidden
    )
    assert all(
        token not in schema.lower()
        for schema in driver.cm._PERSISTED_REGISTRY
        for token in forbidden
    )
    source_surfaces = (
        driver.ArtifactPolicy,
        driver._write_reduced_outcome,
        driver._build_completed_phase_packet,
        driver.cm.evaluate_promotion_bundle,
        driver.cm.build_receipt,
        assemble.build_stage1_bundle,
        assemble.assemble_stage1,
        cli._completion_fields,
        cli._publish_phase_completion,
    )
    for surface in source_surfaces:
        source = inspect.getsource(surface).lower()
        assert all(token not in source for token in forbidden)
