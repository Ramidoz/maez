#!/usr/bin/env python3
"""Lean clean-checkout test airlock.

This module's outer stage deliberately imports only the standard library.  A
disposable no-pip interpreter carries a generated checkout-bound path and
import-provenance guard; only the outer stage can certify a completed run.
"""

from __future__ import annotations

import ast
import hashlib
import json
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

_PYTEST_CORE_MODULE_REGISTRATIONS = frozenset(
    (
        "assertion",
        "capture",
        "debugging",
        "doctest",
        "faulthandler",
        "fixtures",
        "helpconfig",
        "junitxml",
        "legacypath",
        "logging",
        "main",
        "mark",
        "monkeypatch",
        "pastebin",
        "python",
        "recwarn",
        "reports",
        "runner",
        "setuponly",
        "setupplan",
        "skipping",
        "subtests",
        "terminal",
        "threadexception",
        "tmpdir",
        "unittest",
        "unraisableexception",
        "warnings",
    )
)
_PYTEST_CORE_TYPE_REGISTRATIONS = {
    ("_pytest.capture", "CaptureManager"): "capturemanager",
    ("_pytest.config", "Config"): "pytestconfig",
    ("_pytest.fixtures", "FixtureManager"): "funcmanage",
    ("_pytest.legacypath", "LegacyTmpdirPlugin"): "legacypath-tmpdir",
    ("_pytest.logging", "LoggingPlugin"): "logging-plugin",
    ("_pytest.main", "Session"): "session",
    ("_pytest.terminal", "TerminalReporter"): "terminalreporter",
}


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
    root_device: int
    root_inode: int
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
    control: bytes = b""
    stderr: bytes = b""


@dataclass(frozen=True)
class InnerControl:
    """Fixed non-certifying facts returned over the private control pipe."""

    status: int
    call_phase_observed: bool


@dataclass(frozen=True)
class InnerResult:
    """Private in-process result returned to the generated runner."""

    status: int
    call_phase_observed: bool


@dataclass(frozen=True)
class OuterResult:
    """Terminal result published only after every outer finalizer completed."""

    status: int
    refusal: str | None
    certificate: Mapping[str, str] | None
    diagnostic: bytes


@dataclass(frozen=True)
class _PluginBinding:
    registration_name: str
    plugin: Any
    module: Any
    module_name: str
    exported_type: type[Any] | None
    origin: Path
    package_locations: tuple[Path, ...]


@dataclass(frozen=True)
class _ItemBinding:
    item: Any
    path: Path
    nodeid: str


@dataclass(frozen=True)
class _ReportBinding:
    report: Any
    call: Any
    item: Any
    phase: str
    failed: bool


@dataclass(frozen=True)
class _EligibilitySnapshot:
    status: int
    call_phase_observed: bool
    failure_observed: bool
    integrity_complete: bool
    item_lifecycles_complete: bool
    certificate_eligible: bool


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
        if process is None or process.returncode is not None:
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
            if process.returncode is not None:
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


def _guard_source(
    layout: AirlockLayout,
    inventory: GitInventory,
    *,
    disposable_purelib: Path,
    violation_dir: Path,
    guard_path: Path | None = None,
    runner_path: Path | None = None,
) -> str:
    """Render the origin-bound runtime provenance guard."""

    checkout = layout.checkout.resolve()
    shared_purelib = layout.shared_purelib.resolve()
    disposable_purelib = disposable_purelib.resolve()
    guard_path = (guard_path or violation_dir.parent / "guard.py").resolve()
    runner_path = (runner_path or violation_dir.parent / "inner_runner.py").resolve()
    tracked: list[str] = []
    tracked_dirs: set[str] = {os.fspath(checkout)}
    for relative in inventory.tracked_python_files:
        if relative.is_absolute() or ".." in relative.parts:
            raise AirlockRefusal("airlock_child_setup_failed")
        absolute = checkout / relative
        tracked.append(os.fspath(absolute))
        for parent in absolute.parents:
            try:
                parent.relative_to(checkout)
            except ValueError:
                break
            tracked_dirs.add(os.fspath(parent))
    registered = tuple(
        sorted(
            {
                os.fspath(path.resolve())
                for path in inventory.registered_worktrees
                if path.resolve() != checkout
            }
        )
    )
    base_prefix = Path(sys.base_prefix).resolve()
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    stdlib_roots = tuple(
        sorted(
            {
                os.fspath((base_prefix / "lib" / version).resolve()),
                os.fspath((base_prefix / "lib" / f"{version.replace('.', '')}.zip").resolve()),
                os.fspath((base_prefix / "lib" / version / "lib-dynload").resolve()),
            }
        )
    )
    header = (
        '"""Generated exact-origin airlock guard."""\n'
        f"_CHECKOUT = {os.fspath(checkout)!r}\n"
        f"_SHARED_PURELIB = {os.fspath(shared_purelib)!r}\n"
        f"_DISPOSABLE_PURELIB = {os.fspath(disposable_purelib)!r}\n"
        f"_VIOLATION_DIR = {os.fspath(violation_dir.resolve())!r}\n"
        f"_GUARD_PATH = {os.fspath(guard_path)!r}\n"
        f"_RUNNER_PATH = {os.fspath(runner_path)!r}\n"
        f"_TRACKED_FILES = frozenset({tuple(sorted(tracked))!r})\n"
        f"_TRACKED_DIRS = frozenset({tuple(sorted(tracked_dirs))!r})\n"
        f"_MAEZ_ROOTS = frozenset({tuple(sorted(inventory.maez_roots))!r})\n"
        f"_OTHER_WORKTREES = {registered!r}\n"
        f"_STDLIB_ROOTS = {stdlib_roots!r}\n"
    )
    body = r'''
import os as _os
import sys as _sys

_sys.dont_write_bytecode = True
AIRLOCK_LOAD_COUNT = globals().get("AIRLOCK_LOAD_COUNT", 0) + 1
_MAX_MARKER_ORDINAL = 99_999_999
_SELF = _sys.modules.get(__name__)
_MAIN = _sys.modules.get("__main__")
_ADMITTED_MAIN_ENTRY = None


class AirlockGuardViolation(RuntimeError):
    pass


def _inside(path, root):
    try:
        return _os.path.commonpath((path, root)) == root
    except (OSError, ValueError, TypeError):
        return False


def _canonical(raw):
    if not isinstance(raw, (str, bytes, _os.PathLike)):
        _violate("airlock_path_provenance_violation")
    try:
        return _os.path.realpath(_os.fspath(raw))
    except (OSError, TypeError, ValueError):
        _violate("airlock_path_provenance_violation")


def _has_nested_git(path):
    cursor = path if _os.path.isdir(path) else _os.path.dirname(path)
    while _inside(cursor, _CHECKOUT) and cursor != _CHECKOUT:
        if _os.path.lexists(_os.path.join(cursor, ".git")):
            return True
        parent = _os.path.dirname(cursor)
        if parent == cursor:
            break
        cursor = parent
    return False


def _record_marker(token):
    flags = _os.O_WRONLY | _os.O_CREAT | _os.O_EXCL
    if hasattr(_os, "O_CLOEXEC"):
        flags |= _os.O_CLOEXEC
    if hasattr(_os, "O_NOFOLLOW"):
        flags |= _os.O_NOFOLLOW
    try:
        ordinals = range(1, _MAX_MARKER_ORDINAL + 1)
    except BaseException:
        _os._exit(86)
    for ordinal in ordinals:
        descriptor = None
        try:
            descriptor = _os.open(
                _os.path.join(_VIOLATION_DIR, f"{ordinal:08d}"), flags, 0o600
            )
        except FileExistsError:
            continue
        except BaseException:
            _os._exit(86)
        try:
            _os.fchmod(descriptor, 0o600)
            payload = f"{token}\n".encode("ascii")
            if _os.write(descriptor, payload) != len(payload):
                raise OSError("short marker write")
            info = _os.fstat(descriptor)
            if (
                (info.st_mode & 0o170000) != 0o100000
                or info.st_nlink != 1
                or (info.st_mode & 0o777) != 0o600
            ):
                raise OSError("invalid marker")
            _os.close(descriptor)
            descriptor = None
        except BaseException:
            if descriptor is not None:
                try:
                    _os.close(descriptor)
                except BaseException:
                    pass
            _os._exit(86)
        return
    _os._exit(86)


def _violate(token):
    _record_marker(token)
    raise AirlockGuardViolation(token)


def _admit_path(raw):
    path = _canonical(raw)
    if path == _DISPOSABLE_PURELIB:
        return 1, path
    if path == _CHECKOUT or path in _TRACKED_DIRS:
        if _has_nested_git(path):
            _violate("airlock_path_provenance_violation")
        if any(path == root or _inside(path, root) for root in _OTHER_WORKTREES):
            _violate("airlock_path_provenance_violation")
        return 2, path
    if path == _SHARED_PURELIB:
        return 3, path
    if path in _STDLIB_ROOTS:
        return 0, path
    _violate("airlock_path_provenance_violation")


def _path_class(raw):
    return _admit_path(raw)[0]


def _canonical_path_sequence(values):
    admitted = []
    seen = set()
    for raw in values:
        path_class, path = _admit_path(raw)
        if path not in seen:
            admitted.append((path_class, path))
            seen.add(path)
    admitted.sort(key=lambda item: item[0])
    return [path for _path_class_value, path in admitted]


def _normalize_initial_path():
    values = []
    for raw in tuple(_sys.path):
        if raw == "":
            cwd = _canonical(_os.getcwd())
            if cwd != _CHECKOUT and cwd not in _TRACKED_DIRS:
                continue
            raw = cwd
        values.append(raw)
    return _canonical_path_sequence(values)


def _expected_startup_path0():
    if not _sys.argv:
        return None
    argv0 = _sys.argv[0]
    if _sys.flags.safe_path:
        return None
    if argv0 == "-m":
        candidate = _os.getcwd()
    elif not argv0 or argv0 in ("-c", "-"):
        return None
    else:
        candidate = _os.path.dirname(_os.path.abspath(argv0))
    try:
        return _os.path.realpath(candidate)
    except (OSError, TypeError, ValueError):
        _violate("airlock_path_provenance_violation")


_STARTUP_PATH0_PENDING = False
_FROZEN_STARTUP_PATH = None
_FROZEN_STARTUP_PATH_OBJECT = None
_PRE_STARTUP_BASELINE_AUDIT_PENDING = True


class _ValidatingPath(list):
    def _replace(self, candidate):
        if self is _FROZEN_STARTUP_PATH_OBJECT:
            if tuple(self) != _FROZEN_STARTUP_PATH:
                _violate("airlock_path_provenance_violation")
            _violate("airlock_path_provenance_violation")
        canonical = _canonical_path_sequence(candidate)
        list.__setitem__(self, slice(None), canonical)

    def append(self, value):
        candidate = list(self)
        candidate.append(value)
        self._replace(candidate)

    def insert(self, index, value):
        if self is _FROZEN_STARTUP_PATH_OBJECT:
            if _sys.path is not self:
                _violate("airlock_path_provenance_violation")
            if tuple(self) != _FROZEN_STARTUP_PATH:
                _violate("airlock_path_provenance_violation")
            _path_class_value, inserted = _admit_path(value)
            if (
                type(index) is int
                and index == 0
                and isinstance(value, str)
                and value == _CHECKOUT
                and inserted == _CHECKOUT
            ):
                try:
                    marker_names = _os.listdir(_VIOLATION_DIR)
                except OSError:
                    _violate("airlock_path_provenance_violation")
                if not marker_names:
                    return
                _violate("airlock_path_provenance_violation")
        candidate = list(self)
        candidate.insert(index, value)
        self._replace(candidate)

    def extend(self, values):
        candidate = list(self)
        candidate.extend(values)
        self._replace(candidate)

    def __setitem__(self, key, value):
        candidate = list(self)
        candidate[key] = value
        self._replace(candidate)

    def __iadd__(self, values):
        candidate = list(self)
        candidate += list(values)
        self._replace(candidate)
        return self

    def reverse(self):
        self._replace(self)

    def sort(self, *args, **kwargs):
        self._replace(self)


_BASELINE_PATH = tuple(_normalize_initial_path())
_sys.path = _ValidatingPath(_BASELINE_PATH)
_EXPECTED_STARTUP_PATH0 = _expected_startup_path0()
_STARTUP_PATH_AUDIT_REQUIRED = bool(
    _sys.argv
    and (_sys.argv[0] == "-m" or _sys.argv[0] not in ("", "-", "-c"))
)
_STARTUP_PATH0_PENDING = _STARTUP_PATH_AUDIT_REQUIRED


import site as _site


_ORIGINAL_ADDSITEDIR = _site.addsitedir


def _guarded_addsitedir(sitedir, *args, **kwargs):
    path = _canonical(sitedir)
    if path != _DISPOSABLE_PURELIB:
        _violate("airlock_path_provenance_violation")
    return _ORIGINAL_ADDSITEDIR(path, *args, **kwargs)


_site.addsitedir = _guarded_addsitedir


def _expected_files(fullname):
    candidates = []
    for base in _TRACKED_DIRS:
        stem = _os.path.join(base, *fullname.split("."))
        candidates.extend((stem + ".py", _os.path.join(stem, "__init__.py")))
    return frozenset(candidate for candidate in candidates if candidate in _TRACKED_FILES)


def _expected_directories(fullname):
    return frozenset(
        candidate
        for base in _TRACKED_DIRS
        for candidate in (_os.path.join(base, *fullname.split(".")),)
        if candidate in _TRACKED_DIRS
    )


def _active_alias_exists(fullname):
    active_bases = tuple(
        path
        for path in _sys.path
        if isinstance(path, str) and (path == _CHECKOUT or path in _TRACKED_DIRS)
    )
    for base in active_bases:
        stem = _os.path.join(base, *fullname.split("."))
        if stem + ".py" in _TRACKED_FILES:
            return True
        if _os.path.join(stem, "__init__.py") in _TRACKED_FILES:
            return True
        if stem in _TRACKED_DIRS:
            return True
    return False


def _module_plane_values(module=None, spec=None):
    values = []

    def append_locations(locations):
        try:
            values.extend(tuple(locations))
        except TypeError:
            _violate("airlock_import_provenance_violation")

    if module is not None:
        file_value = getattr(module, "__file__", None)
        if file_value is not None:
            values.append(file_value)
    if spec is not None:
        origin = getattr(spec, "origin", None)
        if origin is not None:
            values.append(origin)
        locations = getattr(spec, "submodule_search_locations", None)
        if locations is not None:
            append_locations(locations)
    if module is not None:
        locations = getattr(module, "__path__", None)
        if locations is not None:
            append_locations(locations)
    return tuple(values)


def _is_stdlib_origin(value):
    if value in {"built-in", "frozen"}:
        return True
    if not isinstance(value, str) or not _os.path.isabs(value):
        return False
    resolved = _os.path.realpath(value)
    return any(resolved == root or _inside(resolved, root) for root in _STDLIB_ROOTS)


def _module_is_owned(name, module=None, spec=None):
    values = _module_plane_values(module=module, spec=spec)
    for value in values:
        if (
            isinstance(value, str)
            and value not in {"built-in", "frozen"}
            and _os.path.isabs(value)
        ):
            lexical = _os.path.abspath(value)
            if lexical in _TRACKED_FILES or _inside(lexical, _CHECKOUT):
                return True
    if values and all(_is_stdlib_origin(value) for value in values):
        return False
    if name.split(".", 1)[0] in _MAEZ_ROOTS:
        return True
    if _active_alias_exists(name):
        return True
    return False


def _is_internal_airlock_module(name, module):
    if (
        name == "_maez_worktree_airlock_guard"
        and module is _SELF
        and getattr(module, "__file__", None) == _GUARD_PATH
        and getattr(module, "__spec__", None) is None
    ):
        return True
    if (
        name == "__main__"
        and module is _MAIN
        and _ADMITTED_MAIN_ENTRY is not None
        and getattr(module, "__file__", None) == _ADMITTED_MAIN_ENTRY[1]
        and getattr(module, "__spec__", None) is None
    ):
        return True
    return (
        name == "__main__"
        and module is _MAIN
        and getattr(module, "__file__", None) == _RUNNER_PATH
        and getattr(module, "__spec__", None) is None
    )


def _validate_concrete(fullname, raw):
    refusal = (
        "airlock_collection_escape"
        if isinstance(raw, str) and _os.path.basename(raw) == "conftest.py"
        else "airlock_import_provenance_violation"
    )
    if not isinstance(raw, str) or raw in {"built-in", "frozen"}:
        _violate(refusal)
    lexical = _os.path.abspath(raw)
    resolved = _canonical(raw)
    if lexical != resolved or _has_nested_git(lexical):
        _violate(refusal)
    try:
        info = _os.lstat(lexical)
    except OSError:
        _violate(refusal)
    if (info.st_mode & 0o170000) != 0o100000:
        _violate(refusal)
    if any(resolved == root or _inside(resolved, root) for root in _OTHER_WORKTREES):
        _violate(refusal)
    expected = _expected_files(fullname)
    if lexical not in _TRACKED_FILES or lexical not in expected:
        _violate(refusal)
    return lexical


def _validate_locations(fullname, values):
    try:
        locations = tuple(values)
    except TypeError:
        _violate("airlock_import_provenance_violation")
    expected = _expected_directories(fullname)
    if not locations:
        _violate("airlock_import_provenance_violation")
    for raw in locations:
        if not isinstance(raw, str):
            _violate("airlock_import_provenance_violation")
        lexical = _os.path.abspath(raw)
        resolved = _canonical(raw)
        if (
            lexical != resolved
            or lexical not in expected
            or lexical not in _TRACKED_DIRS
            or _has_nested_git(lexical)
            or not _os.path.isdir(lexical)
        ):
            _violate("airlock_import_provenance_violation")
    return frozenset(_os.path.abspath(raw) for raw in locations)


def _validate_planes(
    fullname,
    file_value,
    spec_origin,
    module_path,
    search_locations,
    *,
    spec_only=False,
):
    if not spec_only:
        has_concrete = file_value is not None or spec_origin is not None
        if (file_value is None) != (spec_origin is None):
            _violate("airlock_import_provenance_violation")
        if has_concrete:
            if (module_path is None) != (search_locations is None):
                _violate("airlock_import_provenance_violation")
        elif module_path is None or search_locations is None:
            _violate("airlock_import_provenance_violation")
    concrete = []
    if file_value is not None:
        concrete.append(_validate_concrete(fullname, file_value))
    if spec_origin is not None:
        concrete.append(_validate_concrete(fullname, spec_origin))
    if concrete and len(set(concrete)) != 1:
        _violate("airlock_import_provenance_violation")
    location_sets = []
    if module_path is not None:
        location_sets.append(_validate_locations(fullname, module_path))
    if search_locations is not None:
        location_sets.append(_validate_locations(fullname, search_locations))
    if location_sets and len(set(location_sets)) != 1:
        _violate("airlock_import_provenance_violation")
    if not concrete and not location_sets:
        _violate("airlock_import_provenance_violation")
    if concrete:
        concrete_path = concrete[0]
        is_package = _os.path.basename(concrete_path) == "__init__.py"
        if not is_package and location_sets:
            _violate("airlock_import_provenance_violation")
        if is_package:
            expected_locations = frozenset((_os.path.dirname(concrete_path),))
            required_count = 1 if spec_only else 2
            if (
                len(location_sets) != required_count
                or any(locations != expected_locations for locations in location_sets)
            ):
                _violate("airlock_import_provenance_violation")


def _validate_direct_entry(raw):
    if not isinstance(raw, str):
        _violate("airlock_import_provenance_violation")
    lexical = _os.path.abspath(raw)
    resolved = _canonical(raw)
    if (
        lexical != resolved
        or _has_nested_git(lexical)
        or any(
            resolved == root or _inside(resolved, root) for root in _OTHER_WORKTREES
        )
    ):
        _violate("airlock_import_provenance_violation")
    try:
        info = _os.lstat(lexical)
    except OSError:
        _violate("airlock_import_provenance_violation")
    if (info.st_mode & 0o170000) != 0o100000:
        _violate("airlock_import_provenance_violation")
    if lexical != _RUNNER_PATH and lexical not in _TRACKED_FILES:
        _violate("airlock_import_provenance_violation")
    return lexical, resolved


def _validate_startup_entry():
    if not _sys.argv or _sys.argv[0] in {"", "-", "-c", "-m"}:
        return None
    return _validate_direct_entry(_sys.argv[0])


def _revalidate_run_file_event(args):
    if (
        not isinstance(args, tuple)
        or len(args) != 1
        or _ADMITTED_MAIN_ENTRY is None
        or not _sys.argv
    ):
        _violate("airlock_import_provenance_violation")
    event_entry = _validate_direct_entry(args[0])
    argv_entry = _validate_direct_entry(_sys.argv[0])
    if event_entry != _ADMITTED_MAIN_ENTRY or argv_entry != _ADMITTED_MAIN_ENTRY:
        _violate("airlock_import_provenance_violation")


def validate_spec(fullname, spec):
    origin = getattr(spec, "origin", None)
    conftest = (
        isinstance(fullname, str)
        and fullname.rsplit(".", 1)[-1] == "conftest"
    ) or (
        isinstance(origin, str) and _os.path.basename(origin) == "conftest.py"
    )
    if not conftest and not _module_is_owned(fullname, spec=spec):
        return spec
    _validate_planes(
        fullname,
        None,
        origin,
        None,
        getattr(spec, "submodule_search_locations", None),
        spec_only=True,
    )
    return spec


def audit_loaded_modules():
    for name, module in tuple(_sys.modules.items()):
        if module is None:
            continue
        if _is_internal_airlock_module(name, module):
            continue
        spec = getattr(module, "__spec__", None)
        validation_name = name
        if name == "__main__" and module is _MAIN and spec is not None:
            spec_name = getattr(spec, "name", None)
            if isinstance(spec_name, str) and spec_name:
                validation_name = spec_name
        if not _module_is_owned(validation_name, module=module, spec=spec):
            continue
        _validate_planes(
            validation_name,
            getattr(module, "__file__", None),
            getattr(spec, "origin", None) if spec is not None else None,
            getattr(module, "__path__", None),
            getattr(spec, "submodule_search_locations", None) if spec is not None else None,
        )


class _DelegatingDispatcher:
    def __init__(self):
        self._active_names = set()

    def find_spec(self, fullname, path=None, target=None):
        _audit_paths()
        if fullname == "site":
            _violate("airlock_import_provenance_violation")
        if fullname in self._active_names:
            _violate("airlock_import_provenance_violation")
        self._active_names.add(fullname)
        try:
            for finder in tuple(_sys.meta_path):
                if finder is self:
                    continue
                method = getattr(finder, "find_spec", None)
                if method is None:
                    continue
                spec = method(fullname, path, target)
                if spec is not None:
                    return validate_spec(fullname, spec)
            return None
        finally:
            self._active_names.discard(fullname)


DISPATCHER = _DelegatingDispatcher()


class _GuardedMetaPath(list):
    def __init__(self, values=()):
        list.__init__(self)
        self._replace(values)

    def _replace(self, candidate):
        followers = [finder for finder in candidate if finder is not DISPATCHER]
        list.__setitem__(self, slice(None), [DISPATCHER, *followers])

    def append(self, value):
        candidate = list(self)
        candidate.append(value)
        self._replace(candidate)

    def insert(self, index, value):
        candidate = list(self)
        candidate.insert(index, value)
        self._replace(candidate)

    def extend(self, values):
        candidate = list(self)
        candidate.extend(values)
        self._replace(candidate)

    def __setitem__(self, key, value):
        candidate = list(self)
        candidate[key] = value
        self._replace(candidate)

    def __delitem__(self, key):
        candidate = list(self)
        del candidate[key]
        self._replace(candidate)

    def __iadd__(self, values):
        candidate = list(self)
        candidate += list(values)
        self._replace(candidate)
        return self

    def __imul__(self, count):
        candidate = list(self)
        candidate *= count
        self._replace(candidate)
        return self

    def pop(self, index=-1):
        candidate = list(self)
        value = candidate.pop(index)
        self._replace(candidate)
        return value

    def remove(self, value):
        candidate = list(self)
        candidate.remove(value)
        self._replace(candidate)

    def clear(self):
        self._replace(())

    def reverse(self):
        candidate = list(self)
        candidate.reverse()
        self._replace(candidate)

    def sort(self, *args, **kwargs):
        candidate = list(self)
        candidate.sort(*args, **kwargs)
        self._replace(candidate)


def restore_dispatcher_front():
    followers = [finder for finder in _sys.meta_path if finder is not DISPATCHER]
    if isinstance(_sys.meta_path, _GuardedMetaPath):
        _sys.meta_path._replace(followers)
    else:
        _sys.meta_path = _GuardedMetaPath(followers)


def _startup_path_projection_valid(observed):
    if _EXPECTED_STARTUP_PATH0 is None:
        canonical = tuple(_canonical_path_sequence(observed))
        return observed == _BASELINE_PATH and observed == canonical
    if (
        not observed
        or observed[0] != _EXPECTED_STARTUP_PATH0
        or observed[1:] != _BASELINE_PATH
        or tuple(_canonical_path_sequence(observed[1:])) != _BASELINE_PATH
    ):
        return False
    if _ADMITTED_MAIN_ENTRY is not None and _ADMITTED_MAIN_ENTRY[0] == _RUNNER_PATH:
        path0 = _os.path.dirname(_RUNNER_PATH)
        if _canonical(path0) != path0 or not _os.path.isdir(path0):
            _violate("airlock_path_provenance_violation")
    else:
        _path_class_value, path0 = _admit_path(observed[0])
    return observed[0] == path0


def _audit_paths():
    global _PRE_STARTUP_BASELINE_AUDIT_PENDING
    global _STARTUP_PATH0_PENDING
    global _FROZEN_STARTUP_PATH, _FROZEN_STARTUP_PATH_OBJECT
    path_object = _sys.path
    if _PRE_STARTUP_BASELINE_AUDIT_PENDING:
        if not isinstance(path_object, _ValidatingPath):
            _violate("airlock_path_provenance_violation")
        observed = tuple(path_object)
        canonical = tuple(_canonical_path_sequence(observed))
        if observed == _BASELINE_PATH and observed == canonical:
            return
        _violate("airlock_path_provenance_violation")
    if _FROZEN_STARTUP_PATH is not None:
        if (
            path_object is _FROZEN_STARTUP_PATH_OBJECT
            and tuple(path_object) == _FROZEN_STARTUP_PATH
            and _startup_path_projection_valid(_FROZEN_STARTUP_PATH)
        ):
            return
        _violate("airlock_path_provenance_violation")
    if _STARTUP_PATH0_PENDING:
        _STARTUP_PATH0_PENDING = False
        if not isinstance(path_object, _ValidatingPath):
            _violate("airlock_path_provenance_violation")
        observed = tuple(path_object)
        if _startup_path_projection_valid(observed):
            _FROZEN_STARTUP_PATH = observed
            _FROZEN_STARTUP_PATH_OBJECT = path_object
            return
        _violate("airlock_path_provenance_violation")
    if not isinstance(path_object, _ValidatingPath):
        _violate("airlock_path_provenance_violation")
    observed = tuple(path_object)
    canonical = tuple(_canonical_path_sequence(observed))
    if _STARTUP_PATH_AUDIT_REQUIRED:
        _violate("airlock_path_provenance_violation")
    if observed == canonical and set(_BASELINE_PATH).issubset(observed):
        return
    _violate("airlock_path_provenance_violation")


def audit_before_pytest():
    restore_dispatcher_front()
    _audit_paths()
    audit_loaded_modules()


def _normalize_command_path0():
    normalized = _normalize_initial_path()
    if isinstance(_sys.path, _ValidatingPath):
        list.__setitem__(_sys.path, slice(None), normalized)
    else:
        _sys.path = _ValidatingPath(normalized)


_RUN_COMMAND_PATH_PENDING = bool(_sys.argv and _sys.argv[0] == "-c")


def _run_command_audit_hook(event, _args):
    global _PRE_STARTUP_BASELINE_AUDIT_PENDING, _RUN_COMMAND_PATH_PENDING
    if event != "cpython.run_command":
        return
    _PRE_STARTUP_BASELINE_AUDIT_PENDING = False
    if _RUN_COMMAND_PATH_PENDING:
        _RUN_COMMAND_PATH_PENDING = False
        _normalize_command_path0()
        _sys.dont_write_bytecode = True
    audit_before_pytest()


def _startup_phase_audit_hook(event, _args):
    global _PRE_STARTUP_BASELINE_AUDIT_PENDING
    if event not in ("cpython.run_module", "cpython.run_file"):
        return
    _PRE_STARTUP_BASELINE_AUDIT_PENDING = False
    if event == "cpython.run_file":
        _revalidate_run_file_event(_args)


_ADMITTED_MAIN_ENTRY = _validate_startup_entry()
restore_dispatcher_front()
audit_before_pytest()
AUDIT_HOOK_INSTALL_COUNT = globals().get("AUDIT_HOOK_INSTALL_COUNT", 0) + 1
_sys.addaudithook(_run_command_audit_hook)
_sys.addaudithook(_startup_phase_audit_hook)
AIRLOCK_READY = True
'''
    return header + body


def _origin_loader_line(guard: Path) -> str:
    """Return the one executable line permitted in the controlled path file."""

    module_name = "_maez_worktree_airlock_guard"
    path = os.fspath(guard)
    loader = (
        f"_n={module_name!r}\n"
        f"_p={path!r}\n"
        "_o=sys.modules.get('os')\n"
        "if _o is None: raise SystemExit(86)\n"
        "_m=sys.modules.get(_n)\n"
        "if _m is not None:\n"
        " if getattr(_m,'__file__',None)!=_p or getattr(_m,'AIRLOCK_READY',False) is not True: _o._exit(86)\n"
        "else:\n"
        " try:\n"
        "  _m=type(sys)(_n)\n"
        "  _m.__file__=_p\n"
        "  sys.modules[_n]=_m\n"
        "  _raw=builtins.open(_p,'rb').read()\n"
        "  builtins.exec(builtins.compile(_raw,_p,'exec'),_m.__dict__)\n"
        "  if getattr(_m,'__file__',None)!=_p or getattr(_m,'AIRLOCK_READY',False) is not True: _o._exit(86)\n"
        " except BaseException:\n"
        "  _o._exit(86)\n"
    )
    return f"import builtins,sys;builtins.exec({loader!r})\n"


class _AirlockPytestPlugin:
    """Observe pytest provenance and call phases without certifying them."""

    def __init__(self, *, guard: Any, checkout: Path, shared_purelib: Path) -> None:
        self._guard = guard
        self._checkout = checkout.resolve()
        self._shared_purelib = shared_purelib.resolve()
        self.__call_phase_observed = False
        self.__failure_observed = False
        self.__provenance_validated_first = False
        self.__final_audit_complete = False
        self.__rewrite_hook: Any | None = None
        self.__manager: Any | None = None
        self.__self_registration_name: str | None = None
        self.__final_cleanup_registered = False
        self.__registrations_sealed = False
        self.__plugin_bindings: dict[str, _PluginBinding] = {}
        self.__item_bindings: dict[int, _ItemBinding] = {}
        self.__item_phase_state: dict[int, str] = {}
        self.__pending_report_by_item: dict[int, _ReportBinding] = {}
        self.__report_bindings: dict[int, _ReportBinding] = {}
        self.__consumed_reports: set[int] = set()
        self.__collect_report_bindings: dict[int, tuple[Any, bool]] = {}
        self.__consumed_collect_reports: set[int] = set()

    @property
    def call_phase_observed(self) -> bool:
        return self.__call_phase_observed

    @property
    def failure_observed(self) -> bool:
        return self.__failure_observed

    @staticmethod
    def _inside(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    def _refuse(self, token: str) -> None:
        self._guard._violate(token)

    def _canonical_file(self, value: Any) -> Path:
        if not isinstance(value, str) or not os.path.isabs(value):
            self._refuse("airlock_import_provenance_violation")
        try:
            return Path(value).resolve(strict=True)
        except OSError:
            self._refuse("airlock_import_provenance_violation")
            raise AssertionError("unreachable")

    def _canonical_locations(self, values: Any) -> tuple[Path, ...] | None:
        if values is None:
            return None
        try:
            raw_values = tuple(values)
        except TypeError:
            self._refuse("airlock_import_provenance_violation")
            raise AssertionError("unreachable")
        return tuple(self._canonical_file(value) for value in raw_values)

    def _derive_plugin_binding(
        self, plugin: Any, registration_name: str
    ) -> _PluginBinding:
        exported_type: type[Any] | None
        if isinstance(plugin, type(sys)):
            module = plugin
            exported_type = None
            module_name = getattr(module, "__name__", None)
            if not isinstance(module_name, str) or sys.modules.get(module_name) is not module:
                self._refuse("airlock_import_provenance_violation")
        else:
            exported_type = plugin if isinstance(plugin, type) else type(plugin)
            module_name = getattr(exported_type, "__module__", None)
            if not isinstance(module_name, str):
                self._refuse("airlock_import_provenance_violation")
            module = sys.modules.get(module_name)
            if (
                not isinstance(module, type(sys))
                or getattr(module, exported_type.__name__, None) is not exported_type
            ):
                self._refuse("airlock_import_provenance_violation")
        spec = getattr(module, "__spec__", None)
        if spec is None or getattr(spec, "name", None) != module_name:
            self._refuse("airlock_import_provenance_violation")
        origin = self._canonical_file(getattr(module, "__file__", None))
        if self._canonical_file(getattr(spec, "origin", None)) != origin:
            self._refuse("airlock_import_provenance_violation")
        if getattr(module, "__loader__", None) is not getattr(spec, "loader", None):
            self._refuse("airlock_import_provenance_violation")
        if getattr(module, "__package__", None) != getattr(spec, "parent", None):
            self._refuse("airlock_import_provenance_violation")
        module_locations = self._canonical_locations(getattr(module, "__path__", None))
        spec_locations = self._canonical_locations(
            getattr(spec, "submodule_search_locations", None)
        )
        if module_locations != spec_locations:
            self._refuse("airlock_import_provenance_violation")
        locations = module_locations or ()
        if locations and any(location != origin.parent for location in locations):
            self._refuse("airlock_import_provenance_violation")
        return _PluginBinding(
            registration_name=registration_name,
            plugin=plugin,
            module=module,
            module_name=module_name,
            exported_type=exported_type,
            origin=origin,
            package_locations=locations,
        )

    def _binding_is_allowed(self, binding: _PluginBinding) -> bool:
        origin = binding.origin
        if origin.name == "conftest.py":
            tracked = frozenset(getattr(self._guard, "_TRACKED_FILES", ()))
            if not self._inside(origin, self._checkout) or os.fspath(origin) not in tracked:
                self._refuse("airlock_collection_escape")
            return (
                binding.exported_type is None
                and binding.plugin is binding.module
                and binding.registration_name == os.fspath(origin)
            )
        if (
            binding.module_name == "anyio.pytest_plugin"
            and binding.exported_type is None
            and binding.registration_name == "anyio.pytest_plugin"
            and self._inside(origin, self._shared_purelib)
        ):
            return True
        if not self._inside(origin, self._shared_purelib):
            return False
        if binding.exported_type is None:
            expected_module = f"_pytest.{binding.registration_name}"
            return (
                binding.registration_name in _PYTEST_CORE_MODULE_REGISTRATIONS
                and binding.module_name == expected_module
            )
        type_key = (
            binding.module_name,
            binding.exported_type.__name__,
        )
        expected_registration = _PYTEST_CORE_TYPE_REGISTRATIONS.get(type_key)
        if expected_registration is not None:
            return binding.registration_name == expected_registration
        if type_key == ("_pytest.config", "PytestPluginManager"):
            return binding.registration_name == str(id(binding.plugin))
        return False

    def _revalidate_plugins(self) -> None:
        for name, binding in tuple(self.__plugin_bindings.items()):
            observed = self._derive_plugin_binding(binding.plugin, name)
            if (
                observed.plugin is not binding.plugin
                or observed.module is not binding.module
                or observed.module_name != binding.module_name
                or observed.exported_type is not binding.exported_type
                or observed.origin != binding.origin
                or observed.package_locations != binding.package_locations
                or not self._binding_is_allowed(observed)
            ):
                self._refuse("airlock_import_provenance_violation")
        if not self.__registrations_sealed:
            return
        manager = self.__manager
        if manager is None or not hasattr(manager, "list_name_plugin"):
            self._refuse("airlock_import_provenance_violation")
        live = {
            name: plugin
            for name, plugin in manager.list_name_plugin()
            if plugin is not None
        }
        if (
            self.__self_registration_name is None
            or live.get(self.__self_registration_name) is not self
        ):
            self._refuse("airlock_import_provenance_violation")
        expected_names = set(self.__plugin_bindings) | {self.__self_registration_name}
        if set(live) != expected_names:
            self._refuse("airlock_import_provenance_violation")
        for name, binding in self.__plugin_bindings.items():
            if live.get(name) is not binding.plugin:
                self._refuse("airlock_import_provenance_violation")

    def _rewrite_indexes(self) -> tuple[list[int], list[int]]:
        hook = self.__rewrite_hook
        rewrite_indexes = [
            index
            for index, finder in enumerate(sys.meta_path)
            if finder is hook
        ]
        dispatcher_indexes = [
            index
            for index, finder in enumerate(sys.meta_path)
            if finder is self._guard.DISPATCHER
        ]
        return rewrite_indexes, dispatcher_indexes

    def _bind_rewrite_hook(self, manager: Any) -> None:
        hook = getattr(manager, "rewrite_hook", None)
        module = sys.modules.get("_pytest.assertion.rewrite")
        expected_type = (
            getattr(module, "AssertionRewritingHook", None)
            if module is not None
            else None
        )
        if hook is None or expected_type is None or type(hook) is not expected_type:
            self._refuse("airlock_import_provenance_violation")
        self.__rewrite_hook = hook
        self._audit_rewrite_hook()

    def _audit_rewrite_hook(self) -> None:
        if self.__rewrite_hook is None:
            return
        rewrite_indexes, dispatcher_indexes = self._rewrite_indexes()
        if (
            len(rewrite_indexes) != 1
            or len(dispatcher_indexes) != 1
            or dispatcher_indexes[0] != 0
            or dispatcher_indexes[0] >= rewrite_indexes[0]
        ):
            self._refuse("airlock_import_provenance_violation")

    def _audit(self) -> None:
        self._audit_rewrite_hook()
        self._guard.audit_before_pytest()
        self._audit_rewrite_hook()
        self._revalidate_plugins()

    def _observe_item(self, item: Any) -> _ItemBinding:
        try:
            path = Path(os.fspath(getattr(item, "path", None))).resolve(strict=True)
        except (OSError, TypeError, ValueError):
            self._refuse("airlock_collection_escape")
            raise AssertionError("unreachable")
        nodeid = getattr(item, "nodeid", None)
        if not isinstance(nodeid, str) or not nodeid or not self._inside(
            path, self._checkout
        ):
            self._refuse("airlock_collection_escape")
        return _ItemBinding(item=item, path=path, nodeid=nodeid)

    def _bind_items(self, items: Sequence[Any]) -> None:
        bindings = tuple(self._observe_item(item) for item in items)
        self.__item_bindings = {id(binding.item): binding for binding in bindings}
        self.__item_phase_state = {
            id(binding.item): "setup" for binding in bindings
        }

    def _audit_item(self, item: Any) -> None:
        binding = self.__item_bindings.get(id(item))
        observed = self._observe_item(item)
        if (
            binding is None
            or observed.item is not binding.item
            or observed.path != binding.path
            or observed.nodeid != binding.nodeid
        ):
            self._refuse("airlock_collection_escape")

    def _audit_items(self) -> None:
        for binding in tuple(self.__item_bindings.values()):
            self._audit_item(binding.item)

    def _pytest_type(self, module_name: str, type_name: str) -> type[Any]:
        module = sys.modules.get(module_name)
        expected = getattr(module, type_name, None) if module is not None else None
        if not isinstance(expected, type):
            self._refuse("airlock_import_provenance_violation")
        return expected

    def _audit_report_state(self) -> None:
        if self.__pending_report_by_item or not set(
            self.__report_bindings
        ).issubset(self.__consumed_reports):
            self._refuse("airlock_import_provenance_violation")

    def _item_lifecycles_complete(self) -> bool:
        return bool(self.__item_phase_state) and all(
            state == "complete" for state in self.__item_phase_state.values()
        )

    def _phase_is_expected(self, item_id: int, phase: str) -> bool:
        state = self.__item_phase_state.get(item_id)
        return (
            (state == "setup" and phase == "setup")
            or (state == "call_or_teardown" and phase in {"call", "teardown"})
            or (state == "teardown" and phase == "teardown")
        )

    def _advance_phase(self, item_id: int, phase: str) -> None:
        next_state = {
            "setup": "call_or_teardown",
            "call": "teardown",
            "teardown": "complete",
        }[phase]
        self.__item_phase_state[item_id] = next_state

    def _report_control_types(self) -> tuple[type[Any], type[Any]]:
        outcomes = sys.modules.get("_pytest.outcomes")
        skip = getattr(outcomes, "skip", None) if outcomes is not None else None
        xfail = getattr(outcomes, "xfail", None) if outcomes is not None else None
        skip_type = getattr(skip, "Exception", None)
        xfail_type = getattr(xfail, "Exception", None)
        if not isinstance(skip_type, type) or not isinstance(xfail_type, type):
            self._refuse("airlock_import_provenance_violation")
        return skip_type, xfail_type

    def _raw_report_kind(self, excinfo: Any) -> str:
        if excinfo is None:
            return "passed"
        skip_type, xfail_type = self._report_control_types()
        value = getattr(excinfo, "value", None)
        if isinstance(value, skip_type):
            return "skipped"
        if isinstance(value, xfail_type):
            return "xfailed"
        if isinstance(value, BaseExceptionGroup):
            try:
                _matched, remainder = value.split(skip_type)
            except (TypeError, ValueError):
                self._refuse("airlock_import_provenance_violation")
            if remainder is None:
                return "skipped"
        return "failed"

    def _validated_unittest_excinfo(
        self,
        item: Any,
        before: Any,
        unittest_excinfo: tuple[Any, ...] | None,
        after: Any,
    ) -> Any:
        if after is before:
            return after
        unittest = sys.modules.get("unittest")
        skip_test = getattr(unittest, "SkipTest", None) if unittest is not None else None
        skip_type, _xfail_type = self._report_control_types()
        function_type = self._pytest_type("_pytest.python", "Function")
        if (
            type(item) is function_type
            and unittest_excinfo is None
            and isinstance(skip_test, type)
            and isinstance(getattr(before, "value", None), skip_test)
            and isinstance(getattr(after, "value", None), skip_type)
            and str(getattr(after, "value", None))
            == str(getattr(before, "value", None))
        ):
            return after
        unittest_module = sys.modules.get("_pytest.unittest")
        item_type = (
            getattr(unittest_module, "TestCaseFunction", None)
            if unittest_module is not None
            else None
        )
        if (
            not isinstance(item_type, type)
            or type(item) is not item_type
            or not unittest_excinfo
            or tuple(getattr(item, "_excinfo", ())) != unittest_excinfo[1:]
        ):
            self._refuse("airlock_import_provenance_violation")
        injected = unittest_excinfo[0]
        if after is injected:
            return after
        if (
            not isinstance(skip_test, type)
            or not isinstance(getattr(injected, "value", None), skip_test)
            or not isinstance(getattr(after, "value", None), skip_type)
            or str(getattr(after, "value", None)) != str(getattr(injected, "value", None))
        ):
            self._refuse("airlock_import_provenance_violation")
        return after

    def _xfail_state(self, item: Any) -> Any:
        skipping = sys.modules.get("_pytest.skipping")
        key = getattr(skipping, "xfailed_key", None) if skipping is not None else None
        stash = getattr(item, "stash", None)
        get = getattr(stash, "get", None)
        if key is None or not callable(get):
            return None
        try:
            return get(key, None)
        except (KeyError, TypeError):
            self._refuse("airlock_import_provenance_violation")

    def _validated_report_failure(
        self, item: Any, phase: str, excinfo: Any, report: Any
    ) -> bool:
        outcome = getattr(report, "outcome", None)
        if (
            outcome not in {"passed", "failed", "skipped"}
            or (getattr(report, "failed", False) is True) != (outcome == "failed")
            or (getattr(report, "passed", False) is True) != (outcome == "passed")
            or (getattr(report, "skipped", False) is True) != (outcome == "skipped")
            or (outcome == "passed" and getattr(report, "longrepr", None) is not None)
            or (outcome != "passed" and getattr(report, "longrepr", None) is None)
        ):
            self._refuse("airlock_import_provenance_violation")
        raw_kind = self._raw_report_kind(excinfo)
        xfail_state = self._xfail_state(item)
        has_wasxfail = hasattr(report, "wasxfail")
        if has_wasxfail:
            reason = getattr(report, "wasxfail", None)
            if not isinstance(reason, str):
                self._refuse("airlock_import_provenance_violation")
            if raw_kind == "xfailed":
                message = getattr(getattr(excinfo, "value", None), "msg", None)
                if outcome != "skipped" or reason != message:
                    self._refuse("airlock_import_provenance_violation")
                return False
            expected_reason = getattr(xfail_state, "reason", None)
            expected_strict = getattr(xfail_state, "strict", None)
            if (
                not isinstance(expected_reason, str)
                or reason != expected_reason
                or raw_kind not in {"passed", "failed"}
                or (raw_kind == "passed" and outcome != "passed")
                or (raw_kind == "passed" and expected_strict is not False)
                or (raw_kind == "failed" and outcome != "skipped")
            ):
                self._refuse("airlock_import_provenance_violation")
            return False
        if raw_kind == "xfailed":
            self._refuse("airlock_import_provenance_violation")
        if raw_kind == "passed" and outcome == "failed":
            reason = getattr(xfail_state, "reason", None)
            if (
                phase != "call"
                or getattr(xfail_state, "strict", None) is not True
                or not isinstance(reason, str)
                or getattr(report, "longrepr", None) != f"[XPASS(strict)] {reason}"
            ):
                self._refuse("airlock_import_provenance_violation")
            return True
        expected_outcome = {
            "passed": "passed",
            "skipped": "skipped",
            "failed": "failed",
        }[raw_kind]
        if outcome != expected_outcome:
            self._refuse("airlock_import_provenance_violation")
        return outcome == "failed"

    def pytest_plugin_registered(
        self, plugin: Any, plugin_name: str, manager: Any
    ) -> None:
        if self.__manager is None:
            self.__manager = manager
        elif manager is not self.__manager:
            self._refuse("airlock_import_provenance_violation")
        if not isinstance(plugin_name, str) or not plugin_name:
            self._refuse("airlock_import_provenance_violation")
        if plugin is self:
            self.__self_registration_name = plugin_name
            return
        binding = self._derive_plugin_binding(plugin, plugin_name)
        if not self._binding_is_allowed(binding):
            if plugin_name.endswith("conftest.py"):
                self._refuse("airlock_collection_escape")
            self._refuse("airlock_import_provenance_violation")
        existing = self.__plugin_bindings.get(plugin_name)
        if existing is not None and existing.plugin is not plugin:
            self._refuse("airlock_import_provenance_violation")
        self.__plugin_bindings[plugin_name] = binding
        if self.__registrations_sealed:
            self._audit()

    def pytest_load_initial_conftests(
        self, early_config: Any, parser: Any, args: Any
    ) -> Any:
        del parser, args
        if getattr(early_config, "pluginmanager", None) is not self.__manager:
            self._refuse("airlock_import_provenance_violation")
        self._bind_rewrite_hook(self.__manager)
        add_cleanup = getattr(early_config, "add_cleanup", None)
        if not callable(add_cleanup) or self.__final_cleanup_registered:
            self._refuse("airlock_import_provenance_violation")
        add_cleanup(self._final_pre_rewrite_cleanup_audit)
        self.__final_cleanup_registered = True
        self.__provenance_validated_first = True
        self.__registrations_sealed = True
        self._audit()
        result = yield
        self._audit()
        return result

    def pytest_configure(self, config: Any) -> None:
        if getattr(config, "pluginmanager", None) is not self.__manager:
            self._refuse("airlock_import_provenance_violation")
        self._audit()

    def pytest_collection_modifyitems(
        self, session: Any, config: Any, items: Sequence[Any]
    ) -> Any:
        del session, config
        self._audit()
        result = yield
        self._audit()
        self._bind_items(items)
        return result

    def pytest_runtest_setup(self, item: Any) -> Any:
        self._audit()
        self._audit_item(item)
        result = yield
        self._audit()
        self._audit_item(item)
        return result

    def pytest_runtest_call(self, item: Any) -> Any:
        self._audit()
        self._audit_item(item)
        result = yield
        self._audit()
        self._audit_item(item)
        return result

    def pytest_runtest_teardown(self, item: Any) -> Any:
        self._audit()
        self._audit_item(item)
        result = yield
        self._audit()
        self._audit_item(item)
        return result

    def pytest_runtest_makereport(self, item: Any, call: Any) -> Any:
        self._audit()
        self._audit_item(item)
        call_type = self._pytest_type("_pytest.runner", "CallInfo")
        if type(call) is not call_type:
            self._refuse("airlock_import_provenance_violation")
        phase = getattr(call, "when", None)
        excinfo_before = getattr(call, "excinfo", None)
        unittest_excinfo = getattr(item, "_excinfo", None)
        if isinstance(unittest_excinfo, list):
            unittest_excinfo = tuple(unittest_excinfo)
        else:
            unittest_excinfo = None
        call_timing = (
            getattr(call, "duration", None),
            getattr(call, "start", None),
            getattr(call, "stop", None),
        )
        report = yield
        report_type = self._pytest_type("_pytest.reports", "TestReport")
        excinfo = self._validated_unittest_excinfo(
            item,
            excinfo_before,
            unittest_excinfo,
            getattr(call, "excinfo", None),
        )
        if (
            type(call) is not call_type
            or type(report) is not report_type
            or getattr(call, "when", None) != phase
            or (
                getattr(call, "duration", None),
                getattr(call, "start", None),
                getattr(call, "stop", None),
            )
            != call_timing
        ):
            self._refuse("airlock_import_provenance_violation")
        failed = self._validated_report_failure(item, phase, excinfo, report)
        item_id = id(item)
        binding = self.__item_bindings.get(item_id)
        if (
            binding is None
            or phase not in {"setup", "call", "teardown"}
            or getattr(report, "when", None) != phase
            or getattr(report, "nodeid", None) != binding.nodeid
            or not self._phase_is_expected(item_id, phase)
            or item_id in self.__pending_report_by_item
            or id(report) in self.__report_bindings
        ):
            self._refuse("airlock_import_provenance_violation")
        report_binding = _ReportBinding(
            report=report,
            call=call,
            item=item,
            phase=phase,
            failed=failed,
        )
        self.__report_bindings[id(report)] = report_binding
        self.__pending_report_by_item[item_id] = report_binding
        self._audit_item(item)
        return report

    def pytest_runtest_logreport(self, report: Any) -> None:
        report_id = id(report)
        matched = self.__report_bindings.get(report_id)
        if matched is None or matched.report is not report:
            subtests_module = sys.modules.get("_pytest.subtests")
            subtest_type = (
                getattr(subtests_module, "SubtestReport", None)
                if subtests_module is not None
                else None
            )
            if not isinstance(subtest_type, type) or type(report) is not subtest_type:
                return
            if report_id in self.__consumed_reports:
                return
            candidates = tuple(
                binding
                for binding in self.__pending_report_by_item.values()
                if binding.phase == "call"
                and getattr(report, "when", None) == "call"
                and getattr(report, "nodeid", None)
                == getattr(binding.report, "nodeid", None)
                and getattr(report, "outcome", None)
                == getattr(binding.report, "outcome", None)
                and getattr(report, "location", None)
                == getattr(binding.report, "location", None)
                and (getattr(report, "failed", False) is True) == binding.failed
            )
            if len(candidates) != 1:
                self._refuse("airlock_import_provenance_violation")
            matched = candidates[0]
            item_id = id(matched.item)
            if self.__pending_report_by_item.get(item_id) is not matched:
                self._refuse("airlock_import_provenance_violation")
            del self.__pending_report_by_item[item_id]
            self.__consumed_reports.update((id(matched.report), report_id))
            self._audit_item(matched.item)
            if matched.failed:
                self.__failure_observed = True
            return
        if report_id in self.__consumed_reports:
            return
        item_id = id(matched.item)
        if self.__pending_report_by_item.get(item_id) is not matched:
            self._refuse("airlock_import_provenance_violation")
        del self.__pending_report_by_item[item_id]
        self.__consumed_reports.add(report_id)
        self._advance_phase(item_id, matched.phase)
        self._audit_item(matched.item)
        if matched.phase == "call":
            self.__call_phase_observed = True
        if matched.failed:
            self.__failure_observed = True

    def pytest_make_collect_report(self, collector: Any) -> Any:
        del collector
        report = yield
        report_type = self._pytest_type("_pytest.reports", "CollectReport")
        if type(report) is not report_type or id(report) in self.__collect_report_bindings:
            self._refuse("airlock_import_provenance_violation")
        self.__collect_report_bindings[id(report)] = (
            report,
            getattr(report, "failed", False) is True,
        )
        return report

    def pytest_collectreport(self, report: Any) -> None:
        report_id = id(report)
        matched = self.__collect_report_bindings.get(report_id)
        if matched is None or matched[0] is not report:
            self._refuse("airlock_import_provenance_violation")
        if report_id in self.__consumed_collect_reports:
            self._refuse("airlock_import_provenance_violation")
        self.__consumed_collect_reports.add(report_id)
        if matched[1] is True:
            self.__failure_observed = True

    def pytest_sessionfinish(self, session: Any, exitstatus: Any) -> Any:
        del exitstatus
        self._audit()
        result = yield
        self._audit()
        self._audit_items()
        self._audit_report_state()
        if self.__failure_observed and getattr(session, "exitstatus", None) == 0:
            session.exitstatus = 1
        return result

    def pytest_unconfigure(self, config: Any) -> Any:
        if getattr(config, "pluginmanager", None) is not self.__manager:
            self._refuse("airlock_import_provenance_violation")
        self._audit()
        result = yield
        self._audit()
        self._audit_items()
        self._audit_report_state()
        return result

    def _final_pre_rewrite_cleanup_audit(self) -> None:
        self._audit()
        self._audit_items()
        self._audit_report_state()
        self.__final_audit_complete = True

    def final_snapshot(self, status: int) -> _EligibilitySnapshot:
        normalized = _normalize_pytest_status(status)
        if normalized == 0 and self.__failure_observed:
            normalized = 1
        integrity_complete = (
            self.__provenance_validated_first and self.__final_audit_complete
        )
        item_lifecycles_complete = self._item_lifecycles_complete()
        eligible = (
            normalized == 0
            and self.__call_phase_observed
            and not self.__failure_observed
            and item_lifecycles_complete
            and integrity_complete
        )
        return _EligibilitySnapshot(
            status=normalized,
            call_phase_observed=self.__call_phase_observed,
            failure_observed=self.__failure_observed,
            integrity_complete=integrity_complete,
            item_lifecycles_complete=item_lifecycles_complete,
            certificate_eligible=eligible,
        )


def _normalize_pytest_status(status: int) -> int:
    if isinstance(status, bool) or not isinstance(status, int) or status not in range(7):
        raise AirlockRefusal("airlock_child_setup_failed")
    return status


def _install_pytest_hook_markers(pytest: Any) -> None:
    wrappers = {
        "pytest_load_initial_conftests": {"wrapper": True, "tryfirst": True},
        "pytest_collection_modifyitems": {"wrapper": True, "tryfirst": True},
        "pytest_runtest_setup": {"wrapper": True, "tryfirst": True},
        "pytest_runtest_call": {"wrapper": True, "tryfirst": True},
        "pytest_runtest_teardown": {"wrapper": True, "tryfirst": True},
        "pytest_runtest_makereport": {"wrapper": True, "tryfirst": True},
        "pytest_make_collect_report": {"wrapper": True, "trylast": True},
        "pytest_sessionfinish": {"wrapper": True, "tryfirst": True},
        "pytest_unconfigure": {"wrapper": True, "tryfirst": True},
    }
    for name, options in wrappers.items():
        pytest.hookimpl(**options)(getattr(_AirlockPytestPlugin, name))


def _inner_main(pytest_arguments: Sequence[str]) -> InnerResult:
    """Run pytest behind the guard; terminal publication is deliberately absent."""

    try:
        guard = sys.modules["_maez_worktree_airlock_guard"]
        guard.audit_before_pytest()
        import pytest

        guard.restore_dispatcher_front()
        guard.audit_before_pytest()
        _install_pytest_hook_markers(pytest)
        plugin = _AirlockPytestPlugin(
            guard=guard,
            checkout=Path(guard._CHECKOUT),
            shared_purelib=Path(guard._SHARED_PURELIB),
        )
        raw_status = pytest.main(list(pytest_arguments), plugins=[plugin])
        status = _normalize_pytest_status(raw_status)
        snapshot = plugin.final_snapshot(status)
        if not snapshot.integrity_complete or (
            snapshot.status == 0
            and snapshot.call_phase_observed
            and not snapshot.certificate_eligible
        ):
            guard._violate("airlock_import_provenance_violation")
        return InnerResult(
            status=snapshot.status,
            call_phase_observed=snapshot.call_phase_observed,
        )
    except BaseException:
        return InnerResult(
            status=AIRLOCK_STATUS,
            call_phase_observed=False,
        )


def _runner_source(diagnostic: Path) -> str:
    """Generate a fixed-control, deliberately non-certifying inner runner."""

    return (
        "import os,stat,sys,traceback\n"
        "def _run_airlock_inner():\n"
        " try:\n"
        f"  diagnostic=os.open({os.fspath(diagnostic)!r},os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\n"
        "  os.fchmod(diagnostic,0o600)\n"
        "  diagnostic_info=os.fstat(diagnostic)\n"
        " except BaseException:\n"
        "  os._exit(86)\n"
        " if (not stat.S_ISREG(diagnostic_info.st_mode) or diagnostic_info.st_nlink!=1 or stat.S_IMODE(diagnostic_info.st_mode)!=0o600):\n"
        "  os._exit(86)\n"
        " control=os.dup(1)\n"
        " os.dup2(diagnostic,1);os.dup2(diagnostic,2);os.close(diagnostic)\n"
        " os.write(control,b'airlock_inner_noncertifying\\n')\n"
        " status=86;call_phase_observed=False\n"
        " try:\n"
        "  guard=sys.modules['_maez_worktree_airlock_guard']\n"
        "  guard.audit_before_pytest()\n"
        "  if len(sys.argv)<2 or sys.argv[1]!='--': raise RuntimeError('invalid runner argv')\n"
        "  from scripts.dev import worktree_test_airlock as airlock\n"
        "  result=airlock._inner_main(tuple(sys.argv[2:]))\n"
        "  status=result.status;call_phase_observed=result.call_phase_observed\n"
        " except BaseException:\n"
        "  traceback.print_exc()\n"
        " completion=(f'airlock_inner_complete:{status}:call_phase_observed={int(call_phase_observed)}\\n').encode('ascii')\n"
        " os.write(control,completion)\n"
        " os.close(control)\n"
        " return status\n"
        "raise SystemExit(_run_airlock_inner())\n"
    )


def _authored_environment(prepared_root: Path, python: Path) -> dict[str, str]:
    return {
        "HOME": os.fspath(prepared_root),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": f"{python.parent}:/usr/bin:/bin",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


_PYTEST_FLAG_TOKENS = frozenset(
    ("-q", "--collect-only", "--collectonly", "--co", "--setup-only", "--setup-plan")
)
_PYTEST_DIAGNOSTIC_TOKENS = frozenset(
    ("--collect-only", "--collectonly", "--co", "--setup-only", "--setup-plan")
)


def _selector_is_inside_checkout(token: str, checkout: Path) -> bool:
    path_token = token.split("::", 1)[0]
    if not path_token or token.startswith("@"):
        return False
    path = Path(path_token)
    if path.is_absolute() or ".." in path.parts:
        return False
    try:
        resolved_checkout = checkout.resolve(strict=True)
        resolved = (resolved_checkout / path).resolve(strict=True)
        resolved.relative_to(resolved_checkout)
    except (OSError, ValueError):
        return False
    return True


def _parse_pytest_invocation(
    argv: Sequence[str],
    checkout: Path,
    *,
    environment: Mapping[str, str],
) -> tuple[str, ...]:
    """Validate the intentionally tiny caller-controlled pytest surface."""

    try:
        if any(
            not isinstance(token, str)
            or token.encode("utf-8").decode("utf-8") != token
            for token in argv
        ):
            raise UnicodeError
    except UnicodeError:
        raise AirlockRefusal("airlock_pytest_arguments_invalid") from None
    if "PYTEST_ADDOPTS" in environment or "PYTEST_PLUGINS" in environment:
        raise AirlockRefusal("airlock_pytest_arguments_invalid")
    if len(argv) < 3 or tuple(argv[:2]) != ("pytest", "--"):
        raise AirlockRefusal("airlock_pytest_arguments_invalid")
    caller = tuple(argv[2:])
    selector_seen = False
    index = 0
    while index < len(caller):
        token = caller[index]
        if token in _PYTEST_FLAG_TOKENS:
            index += 1
            continue
        if token == "-k":
            if (
                index + 1 >= len(caller)
                or not caller[index + 1]
                or caller[index + 1].startswith(("-", "@"))
            ):
                raise AirlockRefusal("airlock_pytest_arguments_invalid")
            index += 2
            continue
        if token.startswith("-") or token.startswith("@"):
            raise AirlockRefusal("airlock_pytest_arguments_invalid")
        if not _selector_is_inside_checkout(token, checkout):
            raise AirlockRefusal("airlock_pytest_arguments_invalid")
        selector_seen = True
        index += 1
    if not selector_seen:
        raise AirlockRefusal("airlock_pytest_arguments_invalid")
    return caller


def _effective_pytest_arguments(
    prepared: PreparedAirlock,
    checkout: Path,
    caller_args: Sequence[str],
) -> tuple[str, ...]:
    return (
        "-c",
        os.fspath(prepared.pytest_config),
        "--rootdir",
        os.fspath(checkout),
        "--confcutdir",
        os.fspath(checkout),
        "-p",
        "no:cacheprovider",
        "-p",
        "anyio.pytest_plugin",
        *caller_args,
    )


def _hash_effective_pytest_arguments(arguments: Sequence[str]) -> str:
    payload = json.dumps(
        tuple(arguments), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _prepare_disposable(
    layout: AirlockLayout,
    inventory: GitInventory,
    *,
    root_parent: Path = Path("/tmp"),
    caller_args: Sequence[str] = (),
) -> PreparedAirlock:
    """Build the one-run interpreter without touching the dependency venv."""

    try:
        root = Path(
            tempfile.mkdtemp(prefix=f"maez-airlock-{os.getpid()}-", dir=root_parent)
        )
        root.chmod(0o700)
        root_info = root.stat(follow_symlinks=False)
        if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid():
            raise AirlockRefusal("airlock_child_setup_failed")
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
        _private_write(
            guard,
            _guard_source(
                layout,
                inventory,
                disposable_purelib=purelib,
                violation_dir=violation_dir,
                guard_path=guard,
                runner_path=runner,
            ),
        )
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
            root_device=root_info.st_dev,
            root_inode=root_info.st_ino,
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
        # Constructing the vector here proves the temporary config exists before
        # any child can consume its path.  The value is recomputed by outer when
        # it binds the certificate, rather than stored as mutable authority.
        _effective_pytest_arguments(prepared, layout.checkout, caller_args)
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


def _prepared_root_is_owned(prepared: PreparedAirlock) -> bool:
    try:
        observed = prepared.root.stat(follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISDIR(observed.st_mode)
        and observed.st_uid == os.getuid()
        and observed.st_dev == prepared.root_device
        and observed.st_ino == prepared.root_inode
    )


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
            _state, observed_group = _parse_proc_stat(stat_reader(entry / "stat"))
            if observed_group == process_group:
                members.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, UnicodeError, ValueError):
            raise AirlockRefusal("airlock_cleanup_incomplete") from None
    return tuple(sorted(members))


def _group_is_quiescent(
    process_group: int,
    *,
    group_reader: Callable[[int], tuple[int, ...]],
    sleeper: Callable[[float], Any],
) -> bool:
    if group_reader(process_group):
        return False
    sleeper(0.05)
    return not group_reader(process_group)


def _clear_owned_group(
    process_group: int,
    *,
    group_reader: Callable[[int], tuple[int, ...]] = _group_members,
    signaler: Callable[[int, int], Any] = os.killpg,
    sleeper: Callable[[float], Any] = time.sleep,
) -> bool:
    for sig, delay in ((signal.SIGTERM, 0.2), (signal.SIGKILL, 0.2)):
        try:
            if _group_is_quiescent(
                process_group, group_reader=group_reader, sleeper=sleeper
            ):
                return True
        except AirlockRefusal:
            return False
        try:
            signaler(process_group, sig)
        except ProcessLookupError:
            continue
        except OSError:
            return False
        sleeper(delay)
    try:
        return _group_is_quiescent(
            process_group, group_reader=group_reader, sleeper=sleeper
        )
    except AirlockRefusal:
        return False


def _reaped_group_is_quiescent(
    process_group: int,
    *,
    group_reader: Callable[[int], tuple[int, ...]] = _group_members,
    sleeper: Callable[[float], Any] = time.sleep,
) -> bool:
    """Observe a reaped leader's old numeric group without signalling it."""

    try:
        return _group_is_quiescent(
            process_group, group_reader=group_reader, sleeper=sleeper
        )
    except AirlockRefusal:
        return False


def _clear_interrupted_owned_group(process: subprocess.Popen[bytes]) -> bool:
    """Bound an interrupted child group while its original leader is known."""

    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            if _group_is_quiescent(
                process.pid, group_reader=_group_members, sleeper=time.sleep
            ):
                return True
        except AirlockRefusal:
            return False
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            continue
        except OSError:
            return False
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            continue
        return _reaped_group_is_quiescent(
            process.pid, group_reader=_group_members
        )
    return _reaped_group_is_quiescent(process.pid, group_reader=_group_members)


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
    group_empty: bool | None = None

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
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
            )
        except OSError:
            return OwnedRun(status=AIRLOCK_STATUS + 1, group_empty=True)
        scope.attach(process)
        if forward_signal is not None:
            time.sleep(0.1)
            scope.inject_for_test(forward_signal)
        interrupt_deadline: float | None = None
        while process.poll() is None:
            if scope.interrupted:
                if interrupt_deadline is None:
                    interrupt_deadline = time.monotonic() + 0.25
                elif time.monotonic() >= interrupt_deadline:
                    group_empty = _clear_interrupted_owned_group(process)
                    break
            time.sleep(0.01)
        try:
            status = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            status = AIRLOCK_STATUS + 1
            group_empty = False
        if group_empty is None:
            group_empty = _reaped_group_is_quiescent(process.pid)
        try:
            control, child_stderr = process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            control, child_stderr = b"", b""
            group_empty = False
        if len(control) > 4096 or len(child_stderr) > 4096:
            return OwnedRun(
                status=AIRLOCK_STATUS + 1,
                group_empty=group_empty,
            )
        return OwnedRun(
            status=status,
            group_empty=group_empty,
            control=control,
            stderr=child_stderr,
        )
    finally:
        if process is not None and process.returncode is None:
            if process.poll() is None:
                _clear_owned_group(process.pid)
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
        if process is not None:
            scope.detach(process)
        if owns_scope:
            restore_complete = scope.restore()
        if (
            not restore_complete
            and process is not None
            and process.returncode is None
        ):
            _clear_owned_group(process.pid)


def _parse_inner_control(payload: bytes, child_status: int) -> InnerControl:
    if len(payload) > 4096:
        raise AirlockRefusal("airlock_child_setup_failed")
    try:
        text = payload.decode("ascii")
    except UnicodeError:
        raise AirlockRefusal("airlock_child_setup_failed") from None
    matched = re.fullmatch(
        r"airlock_inner_noncertifying\n"
        r"airlock_inner_complete:([0-6]):call_phase_observed=([01])\n",
        text,
    )
    if matched is None:
        raise AirlockRefusal("airlock_child_setup_failed")
    status = _normalize_pytest_status(int(matched.group(1)))
    if status != child_status:
        raise AirlockRefusal("airlock_child_setup_failed")
    call_phase_observed = matched.group(2) == "1"
    return InnerControl(
        status=status,
        call_phase_observed=call_phase_observed,
    )


_DIAGNOSTIC_LIMIT = 1_048_576
_DIAGNOSTIC_TRUNCATION_MARKER = b"\nMAEZ_AIRLOCK_DIAGNOSTIC_TRUNCATED\n"


def _read_private_diagnostic(
    path: Path, *, limit: int = _DIAGNOSTIC_LIMIT
) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise AirlockRefusal("airlock_child_setup_failed")
            payload = bytearray()
            while len(payload) <= limit:
                block = os.read(
                    descriptor,
                    min(131_072, limit + 1 - len(payload)),
                )
                if not block:
                    break
                payload.extend(block)
        finally:
            os.close(descriptor)
    except AirlockRefusal:
        raise
    except OSError:
        raise AirlockRefusal("airlock_child_setup_failed") from None
    truncated = info.st_size > limit or len(payload) > limit
    bounded = bytes(payload[:limit])
    return (
        bounded + _DIAGNOSTIC_TRUNCATION_MARKER
        if truncated
        else bounded
    )


def _sha256_file(path: Path) -> str:
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(131072):
                hasher.update(block)
    except OSError:
        raise AirlockRefusal("airlock_child_setup_failed") from None
    return hasher.hexdigest()


def _hash_pth_projection(entries: Sequence[PthEntry]) -> str:
    projection = tuple(
        {
            "name": entry.name,
            "is_regular": entry.is_regular,
            "mode": entry.mode,
            "size": entry.size,
            "sha256": entry.sha256,
        }
        for entry in entries
    )
    payload = json.dumps(
        projection, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _build_certificate(
    *,
    inventory: GitInventory,
    interpreter: Path,
    shared_pth: Sequence[PthEntry],
    effective_pytest_args: Sequence[str],
) -> dict[str, str]:
    return {
        "schema": "worktree_test_airlock.certificate.v1",
        "isolation": "inherited_interpreter_contract",
        "git_head": inventory.head,
        "interpreter_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "interpreter_sha256": _sha256_file(interpreter),
        "shared_pth_sha256": _hash_pth_projection(shared_pth),
        "pytest_args_sha256": _hash_effective_pytest_arguments(
            effective_pytest_args
        ),
    }


def _write_certificate(
    payload: Mapping[str, str], *, stream: Any = sys.stdout
) -> None:
    rendered = json.dumps(
        dict(payload), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    print(f"MAEZ_AIRLOCK_CERTIFIED {rendered}", file=stream)


def _read_marker_state(violation_dir: Path) -> tuple[str, ...]:
    guard_tokens = frozenset(
        (
            "airlock_path_provenance_violation",
            "airlock_import_provenance_violation",
            "airlock_collection_escape",
        )
    )
    markers: list[tuple[int, str]] = []
    try:
        entries = sorted(violation_dir.iterdir(), key=lambda path: path.name)
        for path in entries:
            matched = re.fullmatch(r"([0-9]{8})", path.name)
            if matched is None:
                raise AirlockRefusal("airlock_child_setup_failed")
            ordinal = int(matched.group(1))
            if ordinal < 1:
                raise AirlockRefusal("airlock_child_setup_failed")
            flags = os.O_RDONLY
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(path, flags)
            try:
                info = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_nlink != 1
                    or stat.S_IMODE(info.st_mode) != 0o600
                ):
                    raise AirlockRefusal("airlock_child_setup_failed")
                payload = os.read(descriptor, 512)
                if os.read(descriptor, 1):
                    raise AirlockRefusal("airlock_child_setup_failed")
            finally:
                os.close(descriptor)
            try:
                token = payload.decode("ascii").removesuffix("\n")
            except UnicodeError:
                raise AirlockRefusal("airlock_child_setup_failed") from None
            if payload != f"{token}\n".encode("ascii") or token not in guard_tokens:
                raise AirlockRefusal("airlock_child_setup_failed")
            markers.append((ordinal, token))
    except AirlockRefusal:
        raise
    except (OSError, UnicodeError, ValueError):
        raise AirlockRefusal("airlock_child_setup_failed") from None
    if [ordinal for ordinal, _token in markers] != list(range(1, len(markers) + 1)):
        raise AirlockRefusal("airlock_child_setup_failed")
    return tuple(token for _ordinal, token in markers)


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


_PROC_SCAN_MAX_PROCESSES = 16_384
_PROC_SCAN_MAX_BYTES = 131_072
_PYTHON_EXECUTABLE_NAME = re.compile(rb"python(?:\d+(?:\.\d+)*)?")


def _read_bounded_proc_bytes(path: Path, limit: int) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        payload = bytearray()
        while len(payload) <= limit:
            block = os.read(descriptor, min(65_536, limit + 1 - len(payload)))
            if not block:
                break
            payload.extend(block)
    finally:
        os.close(descriptor)
    if len(payload) > limit:
        raise OSError("process metadata exceeds the bounded scan")
    return bytes(payload)


def _field_references_prepared_root(field: bytes, root: bytes) -> bool:
    offset = 0
    while (index := field.find(root, offset)) >= 0:
        boundary = index + len(root)
        if boundary == len(field) or field[boundary : boundary + 1] == b"/":
            return True
        offset = index + 1
    return False


def _pythonish_executable(raw: bytes) -> bool:
    name = raw.rstrip(b"/").rsplit(b"/", 1)[-1]
    return _PYTHON_EXECUTABLE_NAME.fullmatch(name) is not None


def _same_uid_process_still_exists(process: Path) -> bool:
    try:
        info = process.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()


def _scan_prepared_root_processes(
    prepared_root: Path,
    *,
    proc_root: Path = Path("/proc"),
    byte_reader: Callable[[Path, int], bytes] = _read_bounded_proc_bytes,
) -> bool:
    """Return true only when one bounded same-UID scan finds no descendant.

    The scan is deliberately content-light: process bytes are compared in
    memory and never returned or persisted.  An unreadable environment matters
    only after argv0 or ``/proc/<pid>/exe`` establishes a Python candidate.
    """

    root = os.fsencode(os.fspath(prepared_root.absolute()))
    entries: list[Path] = []
    try:
        for entry in proc_root.iterdir():
            if not entry.name.isdigit():
                continue
            entries.append(entry)
            if len(entries) > _PROC_SCAN_MAX_PROCESSES:
                return False
    except OSError:
        return False
    entries.sort(key=lambda entry: int(entry.name))

    for process in entries:
        try:
            info = process.stat(follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError:
            return False
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            continue

        executable_python = False
        try:
            executable_python = _pythonish_executable(
                os.fsencode(os.readlink(process / "exe"))
            )
        except FileNotFoundError:
            if not _same_uid_process_still_exists(process):
                continue
        except OSError:
            # argv0 can still prove relevance below.  A non-Python candidate
            # with an unreadable executable does not poison the host-wide scan.
            pass

        try:
            command = byte_reader(process / "cmdline", _PROC_SCAN_MAX_BYTES)
        except FileNotFoundError:
            if executable_python and _same_uid_process_still_exists(process):
                return False
            continue
        except OSError:
            if executable_python:
                return False
            continue
        arguments = tuple(value for value in command.split(b"\0") if value)
        if any(_field_references_prepared_root(value, root) for value in arguments):
            return False

        argv_python = bool(arguments) and _pythonish_executable(arguments[0])
        if not (argv_python or executable_python):
            continue
        try:
            environment = byte_reader(
                process / "environ", _PROC_SCAN_MAX_BYTES
            )
        except FileNotFoundError:
            if _same_uid_process_still_exists(process):
                return False
            continue
        except OSError:
            return False
        variables = tuple(value for value in environment.split(b"\0") if value)
        if any(_field_references_prepared_root(value, root) for value in variables):
            return False
    return True


def _prepared_root_processes_absent(
    prepared_root: Path,
    *,
    scanner: Callable[[Path], bool] = _scan_prepared_root_processes,
    sleeper: Callable[[float], Any] = time.sleep,
) -> bool:
    """Require two clean same-UID scans separated by the frozen 50 ms gap."""

    first_clean = scanner(prepared_root)
    sleeper(0.05)
    second_clean = scanner(prepared_root)
    return first_clean and second_clean


def _execute_outer(
    layout: AirlockLayout,
    inventory: GitInventory,
    *,
    caller_args: Sequence[str] = (),
    root_parent: Path = Path("/tmp"),
) -> OuterResult:
    """Run pytest and return terminal facts only after every finalizer closes."""

    tokens: list[str] = []
    prepared: PreparedAirlock | None = None
    before: tuple[PthEntry, ...] | None = None
    cleanup_complete = True
    shared_environment_changed = False
    signals = _OuterSignalScope()
    signals_installed = False
    pytest_status = AIRLOCK_STATUS
    call_phase_observed = False
    diagnostic = b""
    candidate_certificate: Mapping[str, str] | None = None
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
                    caller_args=caller_args,
                )
                effective_arguments = _effective_pytest_arguments(
                    prepared, layout.checkout, caller_args
                )
                candidate_certificate = _build_certificate(
                    inventory=inventory,
                    interpreter=prepared.python,
                    shared_pth=before or (),
                    effective_pytest_args=effective_arguments,
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
                            "--",
                            *effective_arguments,
                        ],
                        cwd=layout.checkout,
                        environment=prepared.environment,
                        signal_scope=signals,
                    )
                    cleanup_complete = result.group_empty
                    if cleanup_complete and not _prepared_root_processes_absent(
                        prepared.root
                    ):
                        cleanup_complete = False
                    try:
                        control = _parse_inner_control(result.control, result.status)
                    except AirlockRefusal:
                        tokens.append("airlock_child_setup_failed")
                    else:
                        pytest_status = control.status
                        call_phase_observed = control.call_phase_observed
                    if result.stderr:
                        tokens.append("airlock_child_setup_failed")
                    try:
                        diagnostic = _read_private_diagnostic(prepared.diagnostic)
                    except AirlockRefusal as refusal:
                        tokens.append(refusal.token)
                try:
                    marker_tokens = _read_marker_state(prepared.violation_dir)
                except AirlockRefusal:
                    raise
                if marker_tokens:
                    tokens.extend(marker_tokens)
        except AirlockRefusal as refusal:
            tokens.append(refusal.token)
        except (OSError, subprocess.SubprocessError):
            tokens.append("airlock_child_setup_failed")
    finally:
        if prepared is not None:
            try:
                if type(prepared) is PreparedAirlock and not _prepared_root_is_owned(
                    prepared
                ):
                    raise AirlockRefusal("airlock_cleanup_incomplete")
                _remove_disposable(prepared.root)
            except AirlockRefusal:
                cleanup_complete = False
            if prepared.root.exists():
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
    refusal = _select_refusal(
        tokens,
        shared_environment_changed=shared_environment_changed,
        cleanup_complete=cleanup_complete,
    )
    if refusal is not None:
        return OuterResult(
            status=AIRLOCK_STATUS,
            refusal=refusal,
            certificate=None,
            diagnostic=diagnostic,
        )
    certificate = (
        candidate_certificate
        if (
            pytest_status == 0
            and call_phase_observed
            and not any(
                token in _PYTEST_DIAGNOSTIC_TOKENS for token in caller_args
            )
        )
        else None
    )
    return OuterResult(
        status=pytest_status,
        refusal=None,
        certificate=certificate,
        diagnostic=diagnostic,
    )


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
    if sys.argv[0] != os.fspath(Path(__file__).resolve()):
        raise AirlockRefusal("airlock_invocation_invalid")
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


def _replay_diagnostic(payload: bytes) -> None:
    if not payload:
        return
    buffer = getattr(sys.stderr, "buffer", None)
    if buffer is not None:
        buffer.write(payload)
        buffer.flush()
        return
    sys.stderr.write(payload.decode("utf-8", errors="replace"))
    sys.stderr.flush()


def _publish_terminal(result: OuterResult) -> int:
    _replay_diagnostic(result.diagnostic)
    if result.refusal is not None:
        print(result.refusal, file=sys.stderr)
    elif result.certificate is not None:
        _write_certificate(result.certificate)
    return result.status


def main(argv: Sequence[str] | None = None) -> int:
    """Run the sole certifying outer airlock boundary."""

    arguments = tuple(sys.argv[1:] if argv is None else argv)
    try:
        layout = _validate_outer_invocation()
        caller_args = _parse_pytest_invocation(
            arguments, layout.checkout, environment=os.environ
        )
        inventory = _run_preflight(layout)
        return _publish_terminal(
            _execute_outer(
                layout,
                inventory,
                caller_args=caller_args,
            )
        )
    except AirlockRefusal as refusal:
        print(refusal.token, file=sys.stderr)
        return AIRLOCK_STATUS


if __name__ == "__main__":
    raise SystemExit(main())
