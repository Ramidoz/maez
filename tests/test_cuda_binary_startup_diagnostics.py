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
import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import pytest

from scripts import cuda_bench_cli as cli
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
    real_create = driver.RehearsalJournalFactory.create
    real_open = driver.open_bench_file
    retirement_interrupted = False

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
        cleanup_complete: bool,
        stderr_capture: driver._BinaryStderrCapture,
    ) -> None:
        try:
            real_raise_failure(
                exc,
                cleanup_complete=cleanup_complete,
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

    def phase_handler(
        _attempt: driver.CommandAttempt,
        *,
        root: Path,
        clock: driver.Clock,
        args: object,
        authorization: driver.WindowAuthorization,
    ) -> cli._TrustedPhaseResult:
        del clock, args
        path = driver.run_phase(harness.config, harness.providers, root=root)
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
        assert failure._stderr_capture.consumed is False

        with pytest.raises(driver.BenchRefusal, match="^spawn_failure$"):
            driver._dispose_binary_spawn_failure(
                failure,
                journal=journal,  # type: ignore[arg-type]
                clock=driver.SystemClock(),
                cycle=1,
            )
        assert failure._stderr_capture.consumed is True
        records = [
            json.loads(line)
            for line in journal.path.read_text(encoding="utf-8").splitlines()
        ]
        assert records[-1]["transition"] == "cycle_1_bootstrap_cleanup"
        assert records[-1]["detail"] == {"outcome": "clean"}
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
                )

            descendant_pid = int(descendant_pid_path.read_text(encoding="utf-8"))
            descendant_pidfd = os.pidfd_open(descendant_pid)
            assert journal.bootstrap_cleanup_appended.is_set()
            assert _wait_for(observed_path.exists)
            records = [
                json.loads(line)
                for line in journal.path.read_text(encoding="utf-8").splitlines()
            ]
            assert records[-1]["transition"] == "cycle_1_bootstrap_cleanup"
            assert records[-1]["detail"] == {"outcome": "cleanup_incomplete"}
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
            )
        assert disposed.value.code == "cleanup_incomplete"
        assert journal.bootstrap_cleanup_appended.is_set()
    finally:
        monkeypatch.setattr(driver, "_finish_binary_stderr_capture", original_finish)
        if "failure" in locals() and not failure._stderr_capture.consumed:
            original_finish(failure._stderr_capture)
        journal.close()


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
        cleanup_complete: bool,
        stderr_capture: driver._BinaryStderrCapture,
    ) -> None:
        try:
            real_raise_failure(
                exc,
                cleanup_complete=cleanup_complete,
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
