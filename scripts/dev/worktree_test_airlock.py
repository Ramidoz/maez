#!/usr/bin/env python3
"""Lean clean-checkout test airlock.

This module's outer stage deliberately imports only the standard library.  The
disposable interpreter and runtime import guard land in subsequent tasks; this
first slice establishes the immutable invocation, checkout, and child-shape
preflight that they rely on.
"""

from __future__ import annotations

import ast
import os
import re
import shlex
import subprocess
import sys
import sysconfig
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
    """Validate the immutable outer boundary; later tasks add execution."""

    del argv
    try:
        layout = _validate_outer_invocation()
        _run_preflight(layout)
        raise AirlockRefusal("airlock_dependency_unavailable")
    except AirlockRefusal as refusal:
        print(refusal.token, file=sys.stderr)
        return AIRLOCK_STATUS


if __name__ == "__main__":
    raise SystemExit(main())
