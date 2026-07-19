#!/usr/bin/env python3
"""Lean clean-checkout test airlock.

This module's outer stage deliberately imports only the standard library.  The
disposable no-pip interpreter is now built on the immutable invocation,
checkout, and child-shape preflight. Runtime import provenance remains a subsequent task.
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import sysconfig
import tempfile
import time
import venv
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SHARED_VENV = Path("/home/rohit/maez/.venv")
SHARED_PYTHON = SHARED_VENV / "bin" / "python"
HOST_GIT = Path("/usr/bin/git")
AIRLOCK_STATUS = 86


class AirlockRefusal(RuntimeError):
    """A content-light, typed refusal from the airlock boundary."""

    def __init__(self, token: str) -> None:
        super().__init__(token)
        self.token = token


@dataclass(frozen=True)
class AirlockLayout:
    shared_python: Path
    shared_purelib: Path
    checkout: Path


@dataclass(frozen=True)
class GitInventory:
    head: str
    tracked_files: tuple[Path, ...]
    tracked_python_files: tuple[Path, ...]
    maez_roots: tuple[str, ...]
    registered_worktrees: tuple[Path, ...]


@dataclass(frozen=True)
class ChildShapeViolation:
    source: str
    line: int
    kind: str
    excerpt: str


@dataclass(frozen=True)
class PthEntry:
    """One content-light member of the canonical shared ``.pth`` projection."""

    name: str
    is_regular: bool
    mode: int
    size: int
    sha256: str | None


@dataclass(frozen=True)
class PreparedAirlock:
    """Owner-only, one-run interpreter state beneath a disposable root."""

    root: Path
    venv: Path
    python: Path
    purelib: Path
    controlled_pth: Path
    guard: Path
    pytest_config: Path
    runner: Path
    violation_dir: Path
    diagnostic: Path
    environment: Mapping[str, str]


@dataclass(frozen=True)
class OwnedRun:
    """Content-light terminal facts for one owned process group."""

    status: int
    group_empty: bool


class _OuterSignalScope:
    """Own SIGINT/SIGTERM from pre-setup through the final integrity check."""

    def __init__(self) -> None:
        self.received: list[int] = []
        self._process: subprocess.Popen[bytes] | None = None
        self._previous: dict[int, Any] = {}

    @property
    def interrupted(self) -> bool:
        return bool(self.received)

    def _handle(self, signum: int, _frame: Any) -> None:
        self.received.append(signum)
        process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass

    def install(self) -> None:
        try:
            for signum in (signal.SIGINT, signal.SIGTERM):
                self._previous[signum] = signal.getsignal(signum)
                signal.signal(signum, self._handle)
        except (OSError, ValueError):
            self.restore()
            raise AirlockRefusal("airlock_child_setup_failed") from None

    def attach(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process
        for signum in tuple(self.received):
            if process.poll() is not None:
                break
            try:
                os.killpg(process.pid, signum)
            except ProcessLookupError:
                break

    def detach(self, process: subprocess.Popen[bytes]) -> None:
        if self._process is process:
            self._process = None

    def inject_for_test(self, signum: int) -> None:
        self._handle(signum, None)

    def restore(self) -> bool:
        complete = True
        for signum, previous in reversed(tuple(self._previous.items())):
            try:
                signal.signal(signum, previous)
            except (OSError, ValueError):
                complete = False
        self._previous.clear()
        self._process = None
        return complete


def _git_environment() -> dict[str, str]:
    """Return an authored environment with no caller-controlled search path."""

    return {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": "/nonexistent",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }


def _snapshot_pth(purelib: Path) -> tuple[PthEntry, ...]:
    """Read a canonical ``.pth`` projection without following a file symlink."""

    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        directory_fd = os.open(purelib, flags)
    except OSError:
        raise AirlockRefusal("airlock_shared_environment_changed") from None
    entries: list[PthEntry] = []
    try:
        try:
            names = sorted(name for name in os.listdir(directory_fd) if name.endswith(".pth"))
        except OSError:
            raise AirlockRefusal("airlock_shared_environment_changed") from None
        for name in names:
            try:
                before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError:
                raise AirlockRefusal("airlock_shared_environment_changed") from None
            regular = stat.S_ISREG(before.st_mode)
            digest: str | None = None
            if regular:
                file_flags = os.O_RDONLY
                if hasattr(os, "O_CLOEXEC"):
                    file_flags |= os.O_CLOEXEC
                if hasattr(os, "O_NOFOLLOW"):
                    file_flags |= os.O_NOFOLLOW
                try:
                    descriptor = os.open(name, file_flags, dir_fd=directory_fd)
                    try:
                        opened = os.fstat(descriptor)
                        hasher = hashlib.sha256()
                        while block := os.read(descriptor, 131072):
                            hasher.update(block)
                        after = os.fstat(descriptor)
                    finally:
                        os.close(descriptor)
                except OSError:
                    raise AirlockRefusal("airlock_shared_environment_changed") from None
                identity_before = (
                    before.st_dev,
                    before.st_ino,
                    before.st_mode,
                    before.st_size,
                )
                identity_opened = (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_mode,
                    opened.st_size,
                )
                identity_after = (
                    after.st_dev,
                    after.st_ino,
                    after.st_mode,
                    after.st_size,
                )
                if identity_before != identity_opened or identity_opened != identity_after:
                    raise AirlockRefusal("airlock_shared_environment_changed")
                digest = hasher.hexdigest()
            entries.append(
                PthEntry(
                    name=name,
                    is_regular=regular,
                    mode=stat.S_IMODE(before.st_mode),
                    size=before.st_size,
                    sha256=digest,
                )
            )
    finally:
        os.close(directory_fd)
    return tuple(entries)


def _private_write(path: Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        payload = content.encode("utf-8")
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
        raise AirlockRefusal("airlock_child_setup_failed")


def _create_disposable_venv(root: Path, base_python: Path) -> None:
    """Create a no-pip venv using the already-authorized base interpreter."""

    if Path(base_python).resolve() != Path(sys.executable).resolve():
        raise AirlockRefusal("airlock_invocation_invalid")
    try:
        venv.EnvBuilder(
            with_pip=False,
            system_site_packages=False,
            symlinks=False,
        ).create(root)
    except (OSError, subprocess.SubprocessError):
        raise AirlockRefusal("airlock_child_setup_failed") from None


def _query_venv_purelib(python: Path) -> Path:
    """Ask the created interpreter for its real versioned purelib."""

    try:
        result = subprocess.run(
            [
                os.fspath(python),
                "-I",
                "-S",
                "-B",
                "-c",
                "import sysconfig;print(sysconfig.get_path('purelib'))",
            ],
            cwd=python.parent.parent,
            env={
                "HOME": "/nonexistent",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise AirlockRefusal("airlock_child_setup_failed") from None
    if result.returncode != 0:
        raise AirlockRefusal("airlock_child_setup_failed")
    candidate = Path(result.stdout.strip()).resolve()
    try:
        candidate.relative_to(python.parent.parent.resolve())
    except ValueError:
        raise AirlockRefusal("airlock_child_setup_failed") from None
    if not candidate.is_dir():
        raise AirlockRefusal("airlock_child_setup_failed")
    return candidate


def _guard_source() -> str:
    return (
        '"""Generated exact-origin airlock guard."""\n'
        "AIRLOCK_LOAD_COUNT = globals().get('AIRLOCK_LOAD_COUNT', 0) + 1\n"
        "AIRLOCK_READY = True\n"
    )


def _origin_loader_line(guard: Path) -> str:
    """Return the one executable line permitted in the controlled path file."""

    module_name = "_maez_worktree_airlock_guard"
    path = os.fspath(guard)
    loader = (
        f"_n={module_name!r}\n"
        f"_p={path!r}\n"
        "_m=sys.modules.get(_n)\n"
        "if _m is not None:\n"
        " if getattr(_m,'__file__',None)!=_p or getattr(_m,'AIRLOCK_READY',False) is not True: os._exit(86)\n"
        "else:\n"
        " try:\n"
        "  _m=type(sys)(_n)\n"
        "  _m.__file__=_p\n"
        "  sys.modules[_n]=_m\n"
        "  _raw=builtins.open(_p,'rb').read()\n"
        "  builtins.exec(builtins.compile(_raw,_p,'exec'),_m.__dict__)\n"
        "  if getattr(_m,'__file__',None)!=_p or getattr(_m,'AIRLOCK_READY',False) is not True: os._exit(86)\n"
        " except BaseException:\n"
        "  os._exit(86)\n"
    )
    return f"import builtins,sys,os;builtins.exec({loader!r})\n"


def _runner_source(diagnostic: Path) -> str:
    """Generate a deliberately non-certifying Task-2 inner runner."""

    return (
        "import os,stat,sys\n"
        "try:\n"
        f" diagnostic=os.open({os.fspath(diagnostic)!r},os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\n"
        " os.fchmod(diagnostic,0o600)\n"
        " diagnostic_info=os.fstat(diagnostic)\n"
        "except BaseException:\n"
        " os._exit(86)\n"
        "if (not stat.S_ISREG(diagnostic_info.st_mode) or diagnostic_info.st_nlink!=1 or stat.S_IMODE(diagnostic_info.st_mode)!=0o600):\n"
        " os._exit(86)\n"
        "control=os.dup(1)\n"
        "os.dup2(diagnostic,1);os.dup2(diagnostic,2);os.close(diagnostic)\n"
        "os.write(control,b'airlock_inner_noncertifying\\n')\n"
        "status=86\n"
        "try:\n"
        " import pytest\n"
        "except BaseException:\n"
        " pass\n"
        "os.write(control,b'airlock_inner_complete:86\\n')\n"
        "os.close(control)\n"
        "raise SystemExit(status)\n"
    )


def _authored_environment(prepared_root: Path, python: Path) -> dict[str, str]:
    return {
        "HOME": os.fspath(prepared_root),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": f"{python.parent}:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _prepare_disposable(
    layout: AirlockLayout,
    inventory: GitInventory,
    *,
    root_parent: Path = Path("/tmp"),
) -> PreparedAirlock:
    """Build the one-run interpreter without touching the dependency venv."""

    del inventory  # Task 3 embeds the complete tracked-origin policy.
    try:
        root = Path(tempfile.mkdtemp(prefix="maez-airlock-", dir=root_parent))
        root.chmod(0o700)
        disposable_venv = root / "venv"
        _create_disposable_venv(disposable_venv, layout.shared_python)
        python = disposable_venv / "bin" / "python"
        purelib = _query_venv_purelib(python)
        violation_dir = root / "violations"
        violation_dir.mkdir(mode=0o700)
        guard = root / "guard.py"
        pytest_config = root / "pytest.ini"
        runner = root / "inner_runner.py"
        diagnostic = root / "inner-diagnostic.log"
        controlled_pth = purelib / "maez-worktree-airlock.pth"
        _private_write(guard, _guard_source())
        _private_write(pytest_config, "")
        _private_write(runner, _runner_source(diagnostic))
        _private_write(
            controlled_pth,
            f"{layout.checkout.resolve()}\n"
            f"{layout.shared_purelib.resolve()}\n"
            f"{_origin_loader_line(guard)}",
        )
        prepared = PreparedAirlock(
            root=root,
            venv=disposable_venv,
            python=python,
            purelib=purelib,
            controlled_pth=controlled_pth,
            guard=guard,
            pytest_config=pytest_config,
            runner=runner,
            violation_dir=violation_dir,
            diagnostic=diagnostic,
            environment={},
        )
        return PreparedAirlock(
            **{
                **prepared.__dict__,
                "environment": _authored_environment(root, python),
            }
        )
    except AirlockRefusal:
        if "root" in locals():
            _cleanup_failed_setup(root)
        raise
    except (OSError, UnicodeError, subprocess.SubprocessError):
        if "root" in locals():
            _cleanup_failed_setup(root)
        raise AirlockRefusal("airlock_child_setup_failed") from None


def _remove_disposable(root: Path) -> None:
    try:
        shutil.rmtree(root)
    except OSError:
        raise AirlockRefusal("airlock_cleanup_incomplete") from None


def _cleanup_failed_setup(root: Path) -> None:
    try:
        shutil.rmtree(root)
    except OSError:
        raise AirlockRefusal("airlock_cleanup_incomplete") from None


def _parse_proc_stat(payload: str) -> tuple[str, int]:
    """Return state and pgrp from proc stat after its final comm delimiter."""

    open_index = payload.find("(")
    close_index = payload.rfind(")")
    if open_index <= 0 or close_index <= open_index:
        raise ValueError("invalid proc stat")
    fields = payload[close_index + 1 :].split()
    if len(fields) < 3 or len(fields[0]) != 1:
        raise ValueError("invalid proc stat")
    return fields[0], int(fields[2])


def _parse_proc_stat_pgrp(payload: str) -> int:
    return _parse_proc_stat(payload)[1]


def _read_proc_stat(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _group_members(
    process_group: int,
    *,
    proc_root: Path = Path("/proc"),
    stat_reader: Callable[[Path], str] = _read_proc_stat,
) -> tuple[int, ...]:
    members: list[int] = []
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        raise AirlockRefusal("airlock_cleanup_incomplete") from None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            state, observed_group = _parse_proc_stat(stat_reader(entry / "stat"))
            if state != "Z" and observed_group == process_group:
                members.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, UnicodeError, ValueError):
            raise AirlockRefusal("airlock_cleanup_incomplete") from None
    return tuple(sorted(members))


def _clear_owned_group(
    process_group: int,
    *,
    group_reader: Callable[[int], tuple[int, ...]] = _group_members,
    signaler: Callable[[int, int], Any] = os.killpg,
    sleeper: Callable[[float], Any] = time.sleep,
) -> bool:
    for sig, delay in ((signal.SIGTERM, 0.2), (signal.SIGKILL, 0.2)):
        try:
            members = group_reader(process_group)
        except AirlockRefusal:
            return False
        if not members:
            return True
        try:
            signaler(process_group, sig)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        sleeper(delay)
    try:
        return not group_reader(process_group)
    except AirlockRefusal:
        return False


def _run_owned_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    forward_signal: int | None = None,
    signal_scope: _OuterSignalScope | None = None,
) -> OwnedRun:
    process: subprocess.Popen[bytes] | None = None
    owns_scope = signal_scope is None
    scope = signal_scope or _OuterSignalScope()
    restore_complete = True

    try:
        if owns_scope:
            try:
                scope.install()
            except AirlockRefusal:
                return OwnedRun(status=AIRLOCK_STATUS + 1, group_empty=True)
        try:
            process = subprocess.Popen(
                list(argv),
                cwd=cwd,
                env=dict(environment),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                start_new_session=True,
            )
        except OSError:
            return OwnedRun(status=AIRLOCK_STATUS + 1, group_empty=True)
        scope.attach(process)
        if forward_signal is not None:
            time.sleep(0.1)
            scope.inject_for_test(forward_signal)
        try:
            status = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            status = AIRLOCK_STATUS + 1
        group_empty = _clear_owned_group(process.pid)
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            group_empty = False
        return OwnedRun(status=status, group_empty=group_empty)
    finally:
        if process is not None and process.poll() is None:
            _clear_owned_group(process.pid)
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        if process is not None:
            scope.detach(process)
        if owns_scope:
            restore_complete = scope.restore()
        if not restore_complete and process is not None:
            _clear_owned_group(process.pid)


def _read_marker_state(violation_dir: Path) -> tuple[str, ...]:
    try:
        return tuple(sorted(path.name for path in violation_dir.iterdir()))
    except OSError:
        raise AirlockRefusal("airlock_child_setup_failed") from None


_REFUSAL_VOCABULARY = (
    "airlock_invocation_invalid",
    "airlock_checkout_mismatch",
    "airlock_environment_forbidden",
    "airlock_dependency_unavailable",
    "airlock_path_provenance_violation",
    "airlock_import_provenance_violation",
    "airlock_collection_escape",
    "airlock_pytest_arguments_invalid",
    "airlock_child_setup_failed",
    "airlock_shared_environment_changed",
    "airlock_cleanup_incomplete",
)


def _select_refusal(
    tokens: Sequence[str],
    *,
    shared_environment_changed: bool,
    cleanup_complete: bool,
) -> str | None:
    """Select terminal evidence independently of exception timing."""

    if shared_environment_changed:
        return "airlock_shared_environment_changed"
    if not cleanup_complete:
        return "airlock_cleanup_incomplete"
    present = frozenset(tokens)
    return next((token for token in _REFUSAL_VOCABULARY if token in present), None)


def _execute_outer(
    layout: AirlockLayout,
    inventory: GitInventory,
    *,
    root_parent: Path = Path("/tmp"),
) -> str:
    """Run Task 2's non-certifying child and close every finalizer in order."""

    tokens: list[str] = []
    prepared: PreparedAirlock | None = None
    before: tuple[PthEntry, ...] | None = None
    cleanup_complete = True
    shared_environment_changed = False
    signals = _OuterSignalScope()
    signals_installed = False
    try:
        try:
            signals.install()
            signals_installed = True
        except AirlockRefusal as refusal:
            tokens.append(refusal.token)
        try:
            before = _snapshot_pth(layout.shared_purelib)
            if not signals_installed or signals.interrupted:
                tokens.append("airlock_child_setup_failed")
            else:
                prepared = _prepare_disposable(
                    layout,
                    inventory,
                    root_parent=root_parent,
                )
                if signals.interrupted:
                    tokens.append("airlock_child_setup_failed")
                else:
                    result = _run_owned_command(
                        [
                            os.fspath(prepared.python),
                            "-I",
                            "-B",
                            os.fspath(prepared.runner),
                        ],
                        cwd=layout.checkout,
                        environment=prepared.environment,
                        signal_scope=signals,
                    )
                    cleanup_complete = result.group_empty
                    if result.status == AIRLOCK_STATUS:
                        tokens.append("airlock_dependency_unavailable")
                    else:
                        tokens.append("airlock_child_setup_failed")
                if _read_marker_state(prepared.violation_dir):
                    tokens.append("airlock_import_provenance_violation")
        except AirlockRefusal as refusal:
            tokens.append(refusal.token)
        except (OSError, subprocess.SubprocessError):
            tokens.append("airlock_child_setup_failed")
    finally:
        if prepared is not None:
            try:
                _remove_disposable(prepared.root)
            except AirlockRefusal:
                cleanup_complete = False
        try:
            after = _snapshot_pth(layout.shared_purelib)
        except AirlockRefusal:
            shared_environment_changed = True
        else:
            shared_environment_changed = before is None or after != before
        if signals_installed and not signals.restore():
            cleanup_complete = False
        if signals.interrupted:
            tokens.append("airlock_child_setup_failed")
    return _select_refusal(
        tokens,
        shared_environment_changed=shared_environment_changed,
        cleanup_complete=cleanup_complete,
    ) or "airlock_child_setup_failed"


def _run_git(
    checkout: Path,
    arguments: Sequence[str],
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> str:
    """Run host Git directly; never consult caller PATH or a shell."""

    try:
        result = runner(
            [os.fspath(HOST_GIT), "-C", os.fspath(checkout), *arguments],
            cwd=checkout,
            env=_git_environment(),
            shell=False,
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise AirlockRefusal("airlock_checkout_mismatch") from None
    if result.returncode != 0 or not isinstance(result.stdout, str):
        raise AirlockRefusal("airlock_checkout_mismatch")
    return result.stdout


def _has_symlink_component(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if current.is_symlink():
            return True
    return False


def _resolve_checkout(launcher: Path, cwd: Path) -> Path:
    """Bind authority to the real launcher and the current Git toplevel."""

    launcher = Path(launcher).absolute()
    cwd = Path(cwd).resolve()
    if _has_symlink_component(launcher) or not launcher.is_file():
        raise AirlockRefusal("airlock_checkout_mismatch")
    if launcher.parts[-3:] != ("scripts", "dev", "worktree_test_airlock.py"):
        raise AirlockRefusal("airlock_checkout_mismatch")

    checkout = launcher.parent.parent.parent.resolve()
    launcher_top = Path(
        _run_git(checkout, ("rev-parse", "--show-toplevel")).strip()
    ).resolve()
    cwd_top = Path(
        _run_git(cwd, ("rev-parse", "--show-toplevel")).strip()
    ).resolve()
    if launcher_top != checkout or cwd_top != checkout:
        raise AirlockRefusal("airlock_checkout_mismatch")

    # A checkout nested below another repository can look lexically local while
    # delegating authority to different Git metadata.  Refuse that shape.
    if any((ancestor / ".git").exists() for ancestor in checkout.parents):
        raise AirlockRefusal("airlock_checkout_mismatch")
    return checkout


def _discover_inventory(checkout: Path) -> GitInventory:
    """Derive the entire tracked-code policy from one audited Git checkout."""

    head = _run_git(checkout, ("rev-parse", "HEAD")).strip()
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise AirlockRefusal("airlock_checkout_mismatch")

    tracked_output = _run_git(checkout, ("ls-files", "-z"))
    tracked_files = tuple(
        sorted(
            (Path(item) for item in tracked_output.split("\0") if item),
            key=lambda path: path.as_posix(),
        )
    )
    tracked = tuple(path for path in tracked_files if path.suffix == ".py")
    roots: set[str] = set()
    for path in tracked:
        roots.add(path.stem if len(path.parts) == 1 else path.parts[0])

    worktree_output = _run_git(checkout, ("worktree", "list", "--porcelain"))
    worktrees = tuple(
        sorted(
            (
                Path(line.removeprefix("worktree ")).resolve()
                for line in worktree_output.splitlines()
                if line.startswith("worktree ")
            ),
            key=lambda path: path.as_posix(),
        )
    )
    if checkout not in worktrees:
        raise AirlockRefusal("airlock_checkout_mismatch")
    return GitInventory(
        head=head,
        tracked_files=tracked_files,
        tracked_python_files=tracked,
        maez_roots=tuple(sorted(roots)),
        registered_worktrees=worktrees,
    )


def _tripwire_source_paths(tracked_files: Sequence[Path]) -> tuple[Path, ...]:
    """Select the frozen, enumerable source set without following targets."""

    selected: set[Path] = set()
    exact = {
        PurePosixPath("scripts/dev/worktree_test_airlock.py"),
        PurePosixPath("scripts/smoke_meaningful_salience_seam_migration.sh"),
        PurePosixPath("tests/test_ledger_activation_v0.py"),
        PurePosixPath("tests/test_subjective_duration_meaningful_salience_seam.py"),
    }
    for raw_path in tracked_files:
        path = PurePosixPath(raw_path.as_posix())
        if path in exact:
            selected.add(Path(path.as_posix()))
            continue
        if len(path.parts) == 2 and path.parts[0] == "tests":
            if path.name.startswith("test_cuda_") and path.suffix == ".py":
                selected.add(Path(path.as_posix()))
        if len(path.parts) == 2 and path.parts[0] == "scripts":
            if path.name.startswith("cuda_") and path.suffix == ".py":
                selected.add(Path(path.as_posix()))
    return tuple(sorted(selected, key=lambda path: path.as_posix()))


_SHARED_INTERPRETER = re.compile(
    r"^/home/rohit/maez/\.venv/bin/python(?:\d+(?:\.\d+)*)?$"
)
_PYTHON_COMMAND = re.compile(r"^python(?:\d+(?:\.\d+)*)?$")


def _subprocess_symbols(tree: ast.AST) -> tuple[set[str], set[str]]:
    module_names: set[str] = set()
    callable_names: set[str] = set()
    child_calls = {"Popen", "run", "call", "check_call", "check_output"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    module_names.add(alias.asname or "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name in child_calls:
                    callable_names.add(alias.asname or alias.name)
    return module_names, callable_names


def _is_subprocess_call(
    node: ast.Call,
    *,
    module_names: set[str],
    callable_names: set[str],
) -> bool:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id in callable_names
    return (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and function.value.id in module_names
        and function.attr in {"Popen", "run", "call", "check_call", "check_output"}
    )


def _constant_string_bindings(tree: ast.AST) -> dict[str, str]:
    bindings: dict[str, str] = {}
    ambiguous: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            if (
                target.id in bindings
                or not isinstance(value, ast.Constant)
                or not isinstance(value.value, str)
            ):
                ambiguous.add(target.id)
                bindings.pop(target.id, None)
            elif target.id not in ambiguous:
                bindings[target.id] = value.value
    return bindings


def _sequence_projection(
    node: ast.List | ast.Tuple, bindings: Mapping[str, str]
) -> tuple[str | None, ...]:
    command: list[str | None] = []
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            command.append(element.value)
            continue
        if isinstance(element, ast.Name) and element.id in bindings:
            command.append(bindings[element.id])
            continue
        command.append(None)
    return tuple(command)


def _local_command_bindings(
    tree: ast.AST, string_bindings: Mapping[str, str]
) -> dict[str, tuple[str | None, ...]]:
    bindings: dict[str, tuple[str | None, ...]] = {}
    ambiguous: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            if (
                target.id in bindings
                or not isinstance(value, (ast.List, ast.Tuple))
            ):
                ambiguous.add(target.id)
                bindings.pop(target.id, None)
            elif target.id not in ambiguous:
                bindings[target.id] = _sequence_projection(value, string_bindings)
    return bindings


def _command_projection(
    node: ast.Call,
    string_bindings: Mapping[str, str],
    command_bindings: Mapping[str, tuple[str | None, ...]],
) -> tuple[str | None, ...]:
    if not node.args:
        return ()
    argument = node.args[0]
    if isinstance(argument, (ast.List, ast.Tuple)):
        return _sequence_projection(argument, string_bindings)
    if isinstance(argument, ast.Name):
        return command_bindings.get(argument.id, ())
    return ()


def _canonical_outer_command(
    command: Sequence[str | None], *, audited_launcher: Path | None
) -> bool:
    if (
        audited_launcher is None
        or not audited_launcher.is_absolute()
        or len(command) < 7
        or command[0] != os.fspath(SHARED_PYTHON)
    ):
        return False
    try:
        launcher_index = command.index("-B") + 1
    except ValueError:
        return False
    return (
        tuple(command[1:launcher_index]) == ("-I", "-S", "-B")
        and command[launcher_index] == os.fspath(audited_launcher)
        and tuple(command[launcher_index + 1 : launcher_index + 3])
        == ("pytest", "--")
    )


def _code_imports_maez(code: str, maez_roots: frozenset[str]) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        names: tuple[str, ...] = ()
        if isinstance(node, ast.Import):
            names = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names = (node.module,)
        if any(name.split(".", 1)[0] in maez_roots for name in names):
            return True
    return False


def _tracked_script_token(
    token: str,
    *,
    tracked_files: frozenset[PurePosixPath],
    audited_checkout: PurePosixPath | None,
) -> bool:
    if not token.endswith(".py"):
        return False
    path = PurePosixPath(token)
    if path.is_absolute():
        if audited_checkout is None:
            return False
        try:
            path = path.relative_to(audited_checkout)
        except ValueError:
            return False
    if not path.parts or any(component in {"", ".", ".."} for component in path.parts):
        return False
    return path in tracked_files


def _is_project_no_site_command(
    command: Sequence[str | None],
    *,
    maez_roots: frozenset[str],
    tracked_files: frozenset[PurePosixPath],
    audited_checkout: PurePosixPath | None,
) -> bool:
    if (
        not command
        or not isinstance(command[0], str)
        or _PYTHON_COMMAND.fullmatch(Path(command[0]).name) is None
    ):
        return False
    if "-S" not in command:
        return False
    if "-m" in command:
        index = command.index("-m")
        if index + 1 < len(command) and isinstance(command[index + 1], str):
            module = command[index + 1]
            if module.split(".", 1)[0] in maez_roots:
                return True
    if "-c" in command:
        index = command.index("-c")
        if (
            index + 1 < len(command)
            and isinstance(command[index + 1], str)
            and _code_imports_maez(command[index + 1], maez_roots)
        ):
            return True
    return any(
        isinstance(token, str)
        and
        _tracked_script_token(
            token,
            tracked_files=tracked_files,
            audited_checkout=audited_checkout,
        )
        for token in command
    )


def _environment_interpreters(node: ast.Call) -> tuple[str, ...]:
    values: list[str] = []
    for keyword in node.keywords:
        if keyword.arg != "env" or not isinstance(keyword.value, ast.Dict):
            continue
        for key, value in zip(keyword.value.keys, keyword.value.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and "PYTHON" in key.value.upper()
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                values.append(value.value)
    return tuple(values)


def _scan_python_child_shapes(
    source_name: str,
    source: str,
    *,
    maez_roots: frozenset[str],
    tracked_files: frozenset[PurePosixPath],
    audited_launcher: Path | None,
) -> list[ChildShapeViolation]:
    try:
        tree = ast.parse(source, filename=source_name)
    except SyntaxError:
        return []
    lines = source.splitlines()
    string_bindings = _constant_string_bindings(tree)
    command_bindings = _local_command_bindings(tree, string_bindings)
    module_names, callable_names = _subprocess_symbols(tree)
    violations: list[ChildShapeViolation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_subprocess_call(
            node,
            module_names=module_names,
            callable_names=callable_names,
        ):
            continue
        command = _command_projection(node, string_bindings, command_bindings)
        if _canonical_outer_command(command, audited_launcher=audited_launcher):
            continue
        excerpt = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        if (
            command
            and isinstance(command[0], str)
            and _SHARED_INTERPRETER.fullmatch(command[0])
        ):
            violations.append(
                ChildShapeViolation(
                    source=source_name,
                    line=node.lineno,
                    kind="absolute_shared_venv_interpreter",
                    excerpt=excerpt,
                )
            )
        for value in _environment_interpreters(node):
            if _SHARED_INTERPRETER.fullmatch(value):
                violations.append(
                    ChildShapeViolation(
                        source=source_name,
                        line=node.lineno,
                        kind="absolute_shared_venv_interpreter",
                        excerpt=excerpt,
                    )
                )
        audited_checkout = (
            PurePosixPath(audited_launcher.parent.parent.parent.as_posix())
            if audited_launcher is not None
            else None
        )
        if _is_project_no_site_command(
            command,
            maez_roots=maez_roots,
            tracked_files=tracked_files,
            audited_checkout=audited_checkout,
        ):
            violations.append(
                ChildShapeViolation(
                    source=source_name,
                    line=node.lineno,
                    kind="project_import_with_no_site",
                    excerpt=excerpt,
                )
            )
    return violations


def _scan_shell_child_shapes(
    source_name: str,
    source: str,
    *,
    maez_roots: frozenset[str],
    tracked_files: frozenset[PurePosixPath],
    audited_launcher: Path | None,
) -> list[ChildShapeViolation]:
    violations: list[ChildShapeViolation] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        try:
            tokens = shlex.split(line, comments=True, posix=True)
        except ValueError:
            tokens = []
        assignment_match = any(
            "=" in token
            and "PYTHON" in token.split("=", 1)[0].upper()
            and _SHARED_INTERPRETER.fullmatch(token.split("=", 1)[1]) is not None
            for token in tokens
        )
        command_index = 0
        while command_index < len(tokens) and "=" in tokens[command_index]:
            command_index += 1
        if command_index < len(tokens) and tokens[command_index] == "exec":
            command_index += 1
        command = tuple(tokens[command_index:])
        canonical_outer = _canonical_outer_command(
            command, audited_launcher=audited_launcher
        )
        direct_match = bool(
            not canonical_outer
            and command
            and _SHARED_INTERPRETER.fullmatch(command[0])
        )
        if assignment_match or direct_match:
            violations.append(
                ChildShapeViolation(
                    source=source_name,
                    line=line_number,
                    kind="absolute_shared_venv_interpreter",
                    excerpt=line.strip(),
                )
            )
        audited_checkout = (
            PurePosixPath(audited_launcher.parent.parent.parent.as_posix())
            if audited_launcher is not None
            else None
        )
        if not canonical_outer and _is_project_no_site_command(
            command,
            maez_roots=maez_roots,
            tracked_files=tracked_files,
            audited_checkout=audited_checkout,
        ):
            violations.append(
                ChildShapeViolation(
                    source=source_name,
                    line=line_number,
                    kind="project_import_with_no_site",
                    excerpt=line.strip(),
                )
            )
    return violations


def _scan_forbidden_child_shapes(
    sources: Mapping[str, str],
    *,
    maez_roots: Sequence[str] = (),
    tracked_files: Sequence[Path] = (),
    audited_launcher: Path | None = None,
) -> tuple[ChildShapeViolation, ...]:
    """Scan only caller-supplied frozen sources for the two ruled-out shapes."""

    violations: list[ChildShapeViolation] = []
    roots = frozenset(maez_roots)
    tracked = frozenset(PurePosixPath(path.as_posix()) for path in tracked_files)
    for source_name in sorted(sources):
        source = sources[source_name]
        if source_name.endswith(".py"):
            violations.extend(
                _scan_python_child_shapes(
                    source_name,
                    source,
                    maez_roots=roots,
                    tracked_files=tracked,
                    audited_launcher=audited_launcher,
                )
            )
        elif source_name.endswith(".sh"):
            violations.extend(
                _scan_shell_child_shapes(
                    source_name,
                    source,
                    maez_roots=roots,
                    tracked_files=tracked,
                    audited_launcher=audited_launcher,
                )
            )
    return tuple(
        sorted(violations, key=lambda item: (item.source, item.line, item.kind))
    )


def _validate_outer_invocation() -> AirlockLayout:
    flags = sys.flags
    if (
        Path(sys.executable) != SHARED_PYTHON
        or flags.isolated != 1
        or flags.no_site != 1
        or flags.dont_write_bytecode != 1
        or flags.safe_path is not True
        or flags.no_user_site != 1
    ):
        raise AirlockRefusal("airlock_invocation_invalid")
    if Path(sys.prefix) != SHARED_VENV:
        raise AirlockRefusal("airlock_invocation_invalid")
    purelib = Path(sysconfig.get_path("purelib")).resolve()
    try:
        purelib.relative_to(SHARED_VENV)
    except ValueError as exc:
        raise AirlockRefusal("airlock_invocation_invalid") from exc

    checkout = _resolve_checkout(Path(__file__), Path.cwd())
    return AirlockLayout(
        shared_python=SHARED_PYTHON,
        shared_purelib=purelib,
        checkout=checkout,
    )


def _run_preflight(layout: AirlockLayout) -> GitInventory:
    inventory = _discover_inventory(layout.checkout)
    paths = _tripwire_source_paths(inventory.tracked_files)
    try:
        sources = {
            path.as_posix(): (layout.checkout / path).read_text(encoding="utf-8")
            for path in paths
        }
    except (OSError, UnicodeError):
        raise AirlockRefusal("airlock_environment_forbidden") from None
    if _scan_forbidden_child_shapes(
        sources,
        maez_roots=inventory.maez_roots,
        tracked_files=inventory.tracked_files,
        audited_launcher=layout.checkout / "scripts/dev/worktree_test_airlock.py",
    ):
        raise AirlockRefusal("airlock_environment_forbidden")
    return inventory


def main(argv: Sequence[str] | None = None) -> int:
    """Run the non-certifying Task-2 airlock boundary."""

    del argv
    try:
        layout = _validate_outer_invocation()
        inventory = _run_preflight(layout)
        raise AirlockRefusal(_execute_outer(layout, inventory))
    except AirlockRefusal as refusal:
        print(refusal.token, file=sys.stderr)
        return AIRLOCK_STATUS


if __name__ == "__main__":
    raise SystemExit(main())
