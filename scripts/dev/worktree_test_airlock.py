#!/usr/bin/env python3
"""Lean clean-checkout test airlock.

This module's outer stage deliberately imports only the standard library.  The
disposable no-pip interpreter now carries a generated, checkout-bound path and
import-provenance guard. Certification remains a subsequent task.
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
        return _os.path.realpath(_os.path.abspath(_os.fspath(raw)))
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
            _violate("airlock_path_provenance_violation")
        canonical = _canonical_path_sequence(candidate)
        list.__setitem__(self, slice(None), canonical)

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
    if not isinstance(raw, str) or raw in {"built-in", "frozen"}:
        _violate("airlock_import_provenance_violation")
    lexical = _os.path.abspath(raw)
    resolved = _canonical(raw)
    if lexical != resolved or _has_nested_git(lexical):
        _violate("airlock_import_provenance_violation")
    try:
        info = _os.lstat(lexical)
    except OSError:
        _violate("airlock_import_provenance_violation")
    if (info.st_mode & 0o170000) != 0o100000:
        _violate("airlock_import_provenance_violation")
    if any(resolved == root or _inside(resolved, root) for root in _OTHER_WORKTREES):
        _violate("airlock_import_provenance_violation")
    expected = _expected_files(fullname)
    if lexical not in _TRACKED_FILES or lexical not in expected:
        _violate("airlock_import_provenance_violation")
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
    if not _module_is_owned(fullname, spec=spec):
        return spec
    _validate_planes(
        fullname,
        None,
        getattr(spec, "origin", None),
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
        " guard=sys.modules['_maez_worktree_airlock_guard']\n"
        " guard.audit_before_pytest()\n"
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
    guard_tokens = frozenset(
        (
            "airlock_path_provenance_violation",
            "airlock_import_provenance_violation",
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
                try:
                    marker_tokens = _read_marker_state(prepared.violation_dir)
                except AirlockRefusal:
                    tokens = [
                        token
                        for token in tokens
                        if token != "airlock_dependency_unavailable"
                    ]
                    raise
                if marker_tokens:
                    tokens = [
                        token
                        for token in tokens
                        if token != "airlock_dependency_unavailable"
                    ]
                    tokens.extend(marker_tokens)
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
