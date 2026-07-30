from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import inspect
import itertools
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import sysconfig
import textwrap
import time
import types
import unittest
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
AIRLOCK_SOURCE = REPO / "scripts" / "dev" / "worktree_test_airlock.py"
SHARED_PYTHON = Path("/home/rohit/maez/.venv/bin/python")
SHARED_PURELIB = Path(
    subprocess.run(
        [
            os.fspath(SHARED_PYTHON),
            "-I",
            "-S",
            "-B",
            "-c",
            "import sysconfig;print(sysconfig.get_path('purelib'))",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
).resolve()


def _owned_airlock_roots(outer_pid: int) -> tuple[Path, ...]:
    prefix = f"maez-airlock-{outer_pid}-"
    roots: list[Path] = []
    for candidate in Path("/tmp").glob(f"{prefix}*"):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if (
            candidate.parent == Path("/tmp")
            and candidate.name.startswith(prefix)
            and stat.S_ISDIR(info.st_mode)
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o700
        ):
            roots.append(candidate)
    return tuple(sorted(roots))


def _cleanup_owned_outer_test_run(airlock, outer_pid: int) -> None:
    roots = _owned_airlock_roots(outer_pid)
    runners = frozenset(os.fsencode(root / "inner_runner.py") for root in roots)

    def owned_inner_groups() -> tuple[int, ...]:
        groups: list[int] = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                arguments = (entry / "cmdline").read_bytes().split(b"\0")
                pid = int(entry.name)
                process_group = os.getpgid(pid)
            except (FileNotFoundError, ProcessLookupError):
                continue
            except (OSError, ValueError):
                continue
            if any(runner in arguments for runner in runners) and process_group == pid:
                groups.append(process_group)
        return tuple(sorted(set(groups)))

    for process_group in owned_inner_groups():
        try:
            os.killpg(process_group, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and owned_inner_groups():
        time.sleep(0.01)
    for root in _owned_airlock_roots(outer_pid):
        try:
            airlock._remove_disposable(root)
        except airlock.AirlockRefusal:
            pass


def _airlock():
    spec = importlib.util.spec_from_file_location("_airlock_under_test", AIRLOCK_SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_shared_dependency_purelib_is_bound_to_the_canonical_interpreter():
    observed = Path(
        subprocess.run(
            [
                os.fspath(SHARED_PYTHON),
                "-I",
                "-S",
                "-B",
                "-c",
                "import sysconfig;print(sysconfig.get_path('purelib'))",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    ).resolve()

    assert SHARED_PURELIB == observed


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(
        ["/usr/bin/git", "init", "-q", os.fspath(path)],
        check=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )


def _inventory_for(checkout: Path):
    airlock = _airlock()
    return airlock.GitInventory(
        head="a" * 40,
        tracked_files=(Path("scripts/dev/worktree_test_airlock.py"),),
        tracked_python_files=(Path("scripts/dev/worktree_test_airlock.py"),),
        maez_roots=("scripts",),
        registered_worktrees=(checkout,),
    )


def _synthetic_layout(tmp_path: Path):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    dependency_purelib = tmp_path / "dependency-purelib"
    dependency_purelib.mkdir()
    return airlock.AirlockLayout(
        shared_python=SHARED_PYTHON,
        shared_purelib=dependency_purelib,
        checkout=checkout,
    )


def _task3_prepared(
    tmp_path: Path,
    *,
    extra_files: dict[str, str] | None = None,
    dependency_purelib: Path | None = None,
    caller_args: tuple[str, ...] = (),
):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    dependency_purelib = dependency_purelib or tmp_path / "dependency-purelib"
    checkout.mkdir()
    dependency_purelib.mkdir(exist_ok=True)
    files = {
        "core/__init__.py": "\n",
        "core/good.py": "VALUE = 41\n",
        "core/ns/leaf.py": "VALUE = 42\n",
        "tests/__init__.py": "\n",
    }
    files.update(extra_files or {})
    for relative, content in files.items():
        destination = checkout / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    if dependency_purelib.is_relative_to(tmp_path):
        (dependency_purelib / "dependency_probe.py").write_text(
            "VALUE = 43\n", encoding="utf-8"
        )
    tracked = tuple(sorted((Path(path) for path in files), key=lambda item: item.as_posix()))
    tracked_python = tuple(path for path in tracked if path.suffix == ".py")
    inventory = airlock.GitInventory(
        head="a" * 40,
        tracked_files=tracked,
        tracked_python_files=tracked_python,
        maez_roots=("core", "tests"),
        registered_worktrees=(checkout,),
    )
    layout = airlock.AirlockLayout(
        shared_python=SHARED_PYTHON,
        shared_purelib=dependency_purelib,
        checkout=checkout,
    )
    prepared = airlock._prepare_disposable(
        layout, inventory, root_parent=tmp_path, caller_args=caller_args
    )
    return airlock, layout, inventory, prepared


def _run_guarded(prepared, code: str, *, cwd: Path | None = None):
    return subprocess.run(
        [os.fspath(prepared.python), "-I", "-B", "-c", code],
        cwd=cwd or prepared.root,
        env=prepared.environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _bytecode_inventory(root: Path) -> tuple[tuple[str, str], ...]:
    entries = []
    for path in root.rglob("*"):
        if path.name == "__pycache__" and path.is_dir():
            entries.append(("directory", path.relative_to(root).as_posix()))
        elif path.suffix == ".pyc" and path.is_file():
            entries.append(("file", path.relative_to(root).as_posix()))
    return tuple(sorted(entries))


def _install_pre_startup_mismatch_probe(
    prepared,
    result_path: Path,
    *,
    forbidden_first: Path | None = None,
) -> None:
    first_mutation = (
        "list.__delitem__(sys.path, 0)"
        if forbidden_first is None
        else f"list.__setitem__(sys.path, 0, {os.fspath(forbidden_first)!r})"
    )
    restore_mutation = (
        "list.insert(sys.path, 0, expected)"
        if forbidden_first is None
        else "list.__setitem__(sys.path, 0, expected)"
    )
    probe_source = textwrap.dedent(
        f"""
        import sys

        if not getattr(sys, '_maez_task4_startup_probe_installed', False):
            sys._maez_task4_startup_probe_installed = True

            def _maez_task4_startup_probe(event, _args):
                if event not in ('cpython.run_module', 'cpython.run_file'):
                    return
                guard = sys.modules.get('_maez_worktree_airlock_guard')
                if guard is None:
                    return
                expected = guard._EXPECTED_STARTUP_PATH0
                removed = sys.path[0]
                {first_mutation}
                first_refused = False
                try:
                    guard._audit_paths()
                except RuntimeError:
                    first_refused = True
                {restore_mutation}
                second_refused = False
                try:
                    guard._audit_paths()
                except RuntimeError:
                    second_refused = True
                payload = (
                    (b'1' if removed == expected else b'0')
                    + b':'
                    + (b'1' if first_refused else b'0')
                    + b':'
                    + (b'1' if second_refused else b'0')
                )
                os_module = sys.modules['os']
                descriptor = os_module.open(
                    {os.fspath(result_path)!r},
                    os_module.O_WRONLY | os_module.O_CREAT | os_module.O_TRUNC,
                    0o600,
                )
                try:
                    os_module.write(descriptor, payload)
                finally:
                    os_module.close(descriptor)

            sys.addaudithook(_maez_task4_startup_probe)
        """
    )
    probe_line = f"import builtins;builtins.exec({probe_source!r})\n"
    (prepared.purelib / "zz-maez-task4-startup-probe.pth").write_text(
        probe_line, encoding="utf-8"
    )


def _run_concurrent_marker_writers(
    prepared,
    tokens: tuple[str, ...],
    rendezvous: Path,
) -> list[subprocess.CompletedProcess[str]]:
    release = rendezvous / "release"
    processes: list[subprocess.Popen[str]] = []
    for index, token in enumerate(tokens):
        ready = rendezvous / f"ready-{index}"
        code = textwrap.dedent(
            f"""
            import pathlib
            import sys
            import time

            guard = sys.modules['_maez_worktree_airlock_guard']
            pathlib.Path({os.fspath(ready)!r}).touch()
            release = pathlib.Path({os.fspath(release)!r})
            while not release.exists():
                time.sleep(0.001)
            guard._record_marker({token!r})
            """
        )
        processes.append(
            subprocess.Popen(
                [os.fspath(prepared.python), "-I", "-B", "-c", code],
                cwd=prepared.root,
                env=prepared.environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    deadline = time.monotonic() + 10
    ready_paths = tuple(rendezvous / f"ready-{index}" for index in range(len(tokens)))
    while not all(path.exists() for path in ready_paths):
        if any(process.poll() is not None for process in processes):
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.002)
    release.touch()
    completed: list[subprocess.CompletedProcess[str]] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=10)
        completed.append(
            subprocess.CompletedProcess(
                process.args,
                process.returncode,
                stdout,
                stderr,
            )
        )
    return completed


class WorktreeAirlockImportTests(unittest.TestCase):
    def test_web_interface_does_not_inject_founder_checkout_into_sys_path(self):
        repo = Path(__file__).resolve().parent.parent
        source = repo / "skills" / "web_interface.py"

        self.assertNotIn(
            'sys.path.insert(0, "/home/rohit/maez")',
            source.read_text(encoding="utf-8"),
        )

    def test_skills_do_not_prepend_founder_checkout_to_sys_path(self):
        repo = Path(__file__).resolve().parent.parent
        offenders = []
        for source in (repo / "skills").glob("*.py"):
            text = source.read_text(encoding="utf-8")
            if 'sys.path.insert(0, str(Path("/home/rohit/maez")))' in text:
                offenders.append(source.relative_to(repo).as_posix())

        self.assertEqual([], offenders)

    def test_tests_do_not_prepend_founder_checkout_to_sys_path(self):
        repo = Path(__file__).resolve().parent.parent
        forbidden = (
            'sys.path.insert(0, "/home/rohit/maez")',
            "sys.path.insert(0, '/home/rohit/maez')",
        )
        offenders = []
        for source in (repo / "tests").glob("test_*.py"):
            if source == Path(__file__).resolve():
                continue
            text = source.read_text(encoding="utf-8")
            if any(pattern in text for pattern in forbidden):
                offenders.append(source.relative_to(repo).as_posix())

        self.assertEqual([], offenders)


@pytest.mark.parametrize(
    "flags",
    [
        ("-S", "-B"),
        ("-I", "-B"),
        ("-I", "-S"),
    ],
    ids=("missing-I", "missing-S", "missing-B"),
)
def test_outer_invocation_refuses_each_missing_isolation_flag(flags: tuple[str, ...]):
    result = subprocess.run(
        [
            os.fspath(SHARED_PYTHON),
            *flags,
            os.fspath(AIRLOCK_SOURCE),
            "pytest",
            "--",
            "tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes",
            "-q",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 86
    assert result.stdout == ""
    assert result.stderr.strip() == "airlock_invocation_invalid"


def test_outer_invocation_refuses_relative_launcher_before_checkout_resolution():
    result = subprocess.run(
        [
            os.fspath(SHARED_PYTHON),
            "-I",
            "-S",
            "-B",
            "scripts/dev/worktree_test_airlock.py",
            "pytest",
            "--",
            "tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes",
            "-q",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 86
    assert result.stdout == ""
    assert result.stderr.strip() == "airlock_invocation_invalid"


def test_hostile_environment_cannot_choose_git_or_enter_git_environment(monkeypatch):
    airlock = _airlock()
    observed: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        observed["argv"] = argv
        observed.update(kwargs)
        return types.SimpleNamespace(stdout="tracked.py\0", returncode=0, stderr="")

    monkeypatch.setenv("PATH", "/hostile/bin")
    monkeypatch.setenv("PYTHONPATH", "/foreign/checkout")
    monkeypatch.setenv("PYTHONUSERBASE", "/foreign/user-site")
    airlock._run_git(REPO, ("ls-files", "-z", "--", "*.py"), runner=fake_run)

    assert observed["argv"][0] == "/usr/bin/git"
    assert observed["shell"] is False
    assert observed["cwd"] == REPO
    child_env = observed["env"]
    assert "/hostile/bin" not in child_env.values()
    assert "PYTHONPATH" not in child_env
    assert "PYTHONUSERBASE" not in child_env


def test_git_runner_exception_is_translated_without_leaking_literal():
    airlock = _airlock()

    def exploding_runner(_argv, **_kwargs):
        raise OSError("/secret/foreign/checkout")

    with pytest.raises(airlock.AirlockRefusal) as observed:
        airlock._run_git(REPO, ("rev-parse", "HEAD"), runner=exploding_runner)

    assert str(observed.value) == "airlock_checkout_mismatch"
    assert "/secret/foreign/checkout" not in str(observed.value)


def test_checkout_identity_refuses_foreign_cwd(tmp_path: Path):
    airlock = _airlock()
    foreign = tmp_path / "foreign"
    _init_repo(foreign)

    with pytest.raises(airlock.AirlockRefusal, match="airlock_checkout_mismatch"):
        airlock._resolve_checkout(AIRLOCK_SOURCE, foreign)


def test_checkout_identity_refuses_launcher_symlink(tmp_path: Path):
    airlock = _airlock()
    launcher_link = tmp_path / "worktree_test_airlock.py"
    launcher_link.symlink_to(AIRLOCK_SOURCE)

    with pytest.raises(airlock.AirlockRefusal, match="airlock_checkout_mismatch"):
        airlock._resolve_checkout(launcher_link, REPO)


def test_checkout_identity_refuses_another_registered_worktree():
    airlock = _airlock()
    main_checkout = Path("/home/rohit/maez")

    with pytest.raises(airlock.AirlockRefusal, match="airlock_checkout_mismatch"):
        airlock._resolve_checkout(AIRLOCK_SOURCE, main_checkout)


def test_checkout_identity_refuses_nested_git_authority(tmp_path: Path):
    airlock = _airlock()
    outer = tmp_path / "outer"
    nested = outer / "nested"
    _init_repo(outer)
    _init_repo(nested)
    launcher = nested / "scripts" / "dev" / "worktree_test_airlock.py"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("# nested decoy\n", encoding="utf-8")

    with pytest.raises(airlock.AirlockRefusal, match="airlock_checkout_mismatch"):
        airlock._resolve_checkout(launcher, nested)


def test_retired_floor_inventory_discovers_tracked_inventory_from_absolute_git():
    airlock = _airlock()
    checkout = airlock._resolve_checkout(AIRLOCK_SOURCE, REPO)
    inventory = airlock._discover_inventory(checkout)

    assert checkout == REPO
    assert len(inventory.head) == 40
    assert inventory.tracked_python_files == tuple(
        sorted(inventory.tracked_python_files, key=lambda path: path.as_posix())
    )
    for removed in (
        "scripts/dev/bench_baseline.py",
        "scripts/dev/bench_report_plugin.py",
        "tests/test_bench_baseline.py",
    ):
        assert not (checkout / removed).exists()
    assert (checkout / "scripts/dev/worktree_test_airlock.py").is_file()
    assert {"core", "scripts", "skills", "tests"} <= set(inventory.maez_roots)
    assert REPO in inventory.registered_worktrees
    assert (
        Path("scripts/smoke_meaningful_salience_seam_migration.sh")
        in inventory.tracked_files
    )
    assert Path("scripts/smoke_meaningful_salience_seam_migration.sh") in (
        airlock._tripwire_source_paths(inventory.tracked_files)
    )


def test_inherited_executable_replaces_all_known_shared_venv_child_literals():
    cuda_source = (REPO / "tests" / "test_cuda_bench_driver.py").read_text(
        encoding="utf-8"
    )
    ledger_source = (REPO / "tests" / "test_ledger_activation_v0.py").read_text(
        encoding="utf-8"
    )
    duration_source = (
        REPO / "tests" / "test_subjective_duration_meaningful_salience_seam.py"
    ).read_text(encoding="utf-8")

    forbidden = os.fspath(SHARED_PYTHON)
    assert forbidden not in cuda_source
    assert forbidden not in ledger_source
    assert forbidden not in duration_source
    assert cuda_source.count("sys.executable") >= 2
    assert "sys.executable" in ledger_source
    assert '"PYTHON": sys.executable' in duration_source


def test_child_shape_tripwire_catches_only_the_two_frozen_categories():
    airlock = _airlock()
    sources = {
        "tests/test_cuda_shape.py": textwrap.dedent(
            """
            import subprocess
            subprocess.run(["/home/rohit/maez/.venv/bin/python", "-c", "pass"])
            subprocess.run(["/home/rohit/maez/.venv/bin/python3", "-c", "pass"])
            subprocess.run(["/home/rohit/maez/.venv/bin/python3.12", "-c", "pass"])
            subprocess.run(["python3", "-c", "pass"])
            subprocess.run(["python3", "-S", "-m", "core.example"])
            subprocess.run([
                "/home/rohit/maez/.venv/bin/python3", "-I", "-S", "-B",
                "/audited/scripts/dev/worktree_test_airlock.py", "pytest", "--", "x",
            ])
            """
        ),
        "scripts/cuda_shape.py": textwrap.dedent(
            """
            import subprocess
            subprocess.run([
                "/home/rohit/maez/.venv/bin/python", "-I", "-S", "-B",
                "/audited/scripts/dev/worktree_test_airlock.py", "pytest", "--", "x",
            ])
            """
        ),
    }

    violations = airlock._scan_forbidden_child_shapes(
        sources,
        maez_roots=("core", "scripts", "skills", "daemon"),
        tracked_files=(Path("scripts/dev/worktree_test_airlock.py"),),
        audited_launcher=Path("/audited/scripts/dev/worktree_test_airlock.py"),
    )

    assert [violation.kind for violation in violations].count(
        "absolute_shared_venv_interpreter"
    ) == 4
    assert [violation.kind for violation in violations].count(
        "project_import_with_no_site"
    ) == 2
    assert len(violations) == 6
    assert all(
        not violation.excerpt.startswith('subprocess.run(["python3", "-c"')
        for violation in violations
    )
    assert all("worktree_test_airlock.py" not in violation.excerpt for violation in violations)


def test_child_shape_tripwire_source_set_is_fixed_and_nonrecursive():
    airlock = _airlock()
    tracked = (
        Path("tests/test_cuda_alpha.py"),
        Path("tests/test_cuda_nested/ignored.py"),
        Path("scripts/cuda_alpha.py"),
        Path("scripts/dev/worktree_test_airlock.py"),
        Path("tests/test_ledger_activation_v0.py"),
        Path("tests/test_subjective_duration_meaningful_salience_seam.py"),
        Path("scripts/smoke_meaningful_salience_seam_migration.sh"),
        Path("future/test_other_gate.py"),
    )

    selected = airlock._tripwire_source_paths(tracked)

    assert selected == (
        Path("scripts/cuda_alpha.py"),
        Path("scripts/dev/worktree_test_airlock.py"),
        Path("scripts/smoke_meaningful_salience_seam_migration.sh"),
        Path("tests/test_cuda_alpha.py"),
        Path("tests/test_ledger_activation_v0.py"),
        Path("tests/test_subjective_duration_meaningful_salience_seam.py"),
    )
    assert Path("future/test_other_gate.py") not in selected
    assert Path("tests/test_cuda_nested/ignored.py") not in selected

    inventory = airlock._discover_inventory(REPO)
    current_paths = airlock._tripwire_source_paths(
        (*inventory.tracked_files, Path("scripts/dev/worktree_test_airlock.py"))
    )
    current_sources = {
        path.as_posix(): (REPO / path).read_text(encoding="utf-8")
        for path in current_paths
    }
    assert (
        airlock._scan_forbidden_child_shapes(
            current_sources,
            maez_roots=inventory.maez_roots,
            tracked_files=inventory.tracked_files,
            audited_launcher=AIRLOCK_SOURCE,
        )
        == ()
    )


def test_child_shape_tripwire_handles_local_alias_exports_and_shell_shape():
    airlock = _airlock()
    sources = {
        "tests/test_cuda_alias.py": textwrap.dedent(
            """
            import subprocess
            PYTHON = "/home/rohit/maez/.venv/bin/python"
            subprocess.run([PYTHON, "-c", "pass"])
            subprocess.run(
                ["bash", "child.sh"],
                env={"PYTHON": "/home/rohit/maez/.venv/bin/python3"},
            )
            subprocess.run(["python3", "-S", "/audited/scripts/tool.py"])
            """
        ),
        "scripts/smoke_meaningful_salience_seam_migration.sh": (
            'PYTHON="/home/rohit/maez/.venv/bin/python3.12" "$PYTHON" -c pass\n'
        ),
    }

    violations = airlock._scan_forbidden_child_shapes(
        sources,
        tracked_files=(Path("scripts/tool.py"),),
        audited_launcher=Path("/audited/scripts/dev/worktree_test_airlock.py"),
    )

    assert [item.kind for item in violations].count(
        "absolute_shared_venv_interpreter"
    ) == 3
    assert [item.kind for item in violations].count(
        "project_import_with_no_site"
    ) == 1


def test_child_shape_tripwire_refuses_real_outer_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    airlock = _airlock()
    relative = Path("tests/test_cuda_forbidden_child.py")
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    source.write_text(
        "import subprocess\n"
        'subprocess.run(["/home/rohit/maez/.venv/bin/python", "-c", "pass"])\n',
        encoding="utf-8",
    )
    inventory = airlock.GitInventory(
        head="a" * 40,
        tracked_files=(relative,),
        tracked_python_files=(relative,),
        maez_roots=("tests",),
        registered_worktrees=(tmp_path,),
    )
    monkeypatch.setattr(airlock, "_discover_inventory", lambda _checkout: inventory)
    layout = airlock.AirlockLayout(
        shared_python=SHARED_PYTHON,
        shared_purelib=tmp_path / "purelib",
        checkout=tmp_path,
    )

    with pytest.raises(airlock.AirlockRefusal, match="airlock_environment_forbidden"):
        airlock._run_preflight(layout)


def test_child_shape_tripwire_uses_git_derived_roots_and_tracked_scripts():
    airlock = _airlock()
    sources = {
        "tests/test_cuda_derived_policy.py": textwrap.dedent(
            """
            import subprocess
            subprocess.run(["python3", "-S", "-m", "hardware.foo"])
            subprocess.run(["python3", "-S", "-m", "maez_tool"])
            subprocess.run(["python3", "-S", "/audited/tools/special_check.py"])
            """
        )
    }

    violations = airlock._scan_forbidden_child_shapes(
        sources,
        maez_roots=("hardware", "maez_tool"),
        tracked_files=(Path("tools/special_check.py"),),
        audited_launcher=Path(
            "/audited/scripts/dev/worktree_test_airlock.py"
        ),
    )

    assert [item.kind for item in violations] == [
        "project_import_with_no_site",
        "project_import_with_no_site",
        "project_import_with_no_site",
    ]


def test_child_shape_tripwire_catches_direct_shared_python_shell_command():
    airlock = _airlock()
    violations = airlock._scan_forbidden_child_shapes(
        {
            "scripts/smoke_meaningful_salience_seam_migration.sh": (
                "/home/rohit/maez/.venv/bin/python3.12 -c pass\n"
            )
        }
    )

    assert [item.kind for item in violations] == [
        "absolute_shared_venv_interpreter"
    ]


def test_child_shape_tripwire_rejects_relative_canonical_launcher_lookalike():
    airlock = _airlock()
    source = textwrap.dedent(
        """
        import subprocess
        subprocess.run([
            "/home/rohit/maez/.venv/bin/python", "-I", "-S", "-B",
            "relative/scripts/dev/worktree_test_airlock.py", "pytest", "--", "x",
        ])
        """
    )

    violations = airlock._scan_forbidden_child_shapes(
        {"scripts/cuda_shape.py": source},
        tracked_files=(Path("scripts/dev/worktree_test_airlock.py"),),
        audited_launcher=Path("/audited/scripts/dev/worktree_test_airlock.py"),
    )

    assert [item.kind for item in violations] == [
        "absolute_shared_venv_interpreter"
    ]


def test_child_shape_tripwire_detects_direct_list_with_dynamic_tail():
    airlock = _airlock()
    source = textwrap.dedent(
        """
        import subprocess
        subprocess.run([
            "/home/rohit/maez/.venv/bin/python", "-B", "-c",
            dynamic_code, str(private_root), make_nonce(),
        ])
        """
    )

    violations = airlock._scan_forbidden_child_shapes(
        {"tests/test_cuda_dynamic_child.py": source}
    )

    assert [item.kind for item in violations] == [
        "absolute_shared_venv_interpreter"
    ]


def test_child_shape_tripwire_detects_named_local_command_list():
    airlock = _airlock()
    source = textwrap.dedent(
        """
        import subprocess
        PYTHON = "/home/rohit/maez/.venv/bin/python"
        cmd = [PYTHON, "-B", "-m", "hardware.init", database_path]
        subprocess.run(cmd)
        """
    )

    violations = airlock._scan_forbidden_child_shapes(
        {"tests/test_cuda_named_child.py": source},
        maez_roots=("hardware",),
    )

    assert [item.kind for item in violations] == [
        "absolute_shared_venv_interpreter"
    ]


def test_borrowed_green_control_is_blocked_by_disposable_plain_dependency_path(
    tmp_path: Path,
):
    airlock = _airlock()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "borrowed_only.py").write_text("VALUE = 17\n", encoding="utf-8")
    control = tmp_path / "control"
    airlock._create_disposable_venv(control, SHARED_PYTHON)
    control_purelib = airlock._query_venv_purelib(control / "bin" / "python")
    (control_purelib / "editable.pth").write_text(
        os.fspath(foreign) + "\n", encoding="utf-8"
    )
    control_result = subprocess.run(
        [os.fspath(control / "bin" / "python"), "-B", "-c", "import borrowed_only"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert control_result.returncode == 0

    layout = airlock.AirlockLayout(
        shared_python=SHARED_PYTHON,
        shared_purelib=control_purelib,
        checkout=tmp_path / "checkout",
    )
    layout.checkout.mkdir()
    prepared = airlock._prepare_disposable(
        layout, _inventory_for(layout.checkout), root_parent=tmp_path
    )
    try:
        isolated = subprocess.run(
            [
                os.fspath(prepared.python),
                "-I",
                "-B",
                "-c",
                "import borrowed_only",
            ],
            cwd=tmp_path,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert isolated.returncode != 0
        assert "borrowed_only" not in isolated.stdout
    finally:
        airlock._remove_disposable(prepared.root)


def test_parent_only_control_flags_do_not_inherit_and_editable_pth_reappears(
    tmp_path: Path,
):
    airlock = _airlock()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "shared_editable_probe.py").write_text(
        "VALUE = 19\n", encoding="utf-8"
    )
    control = tmp_path / "parent-only-control"
    airlock._create_disposable_venv(control, SHARED_PYTHON)
    control_python = control / "bin" / "python"
    control_purelib = airlock._query_venv_purelib(control_python)
    (control_purelib / "synthetic-editable.pth").write_text(
        f"{foreign}\n", encoding="utf-8"
    )
    child_code = (
        "import json,shared_editable_probe,sys;"
        "print(json.dumps({"
        "'value':shared_editable_probe.VALUE,"
        "'origin':shared_editable_probe.__file__,"
        "'isolated':sys.flags.isolated,"
        "'no_site':sys.flags.no_site,"
        "'dont_write_bytecode':sys.flags.dont_write_bytecode}))"
    )
    parent_code = textwrap.dedent(
        f"""
        import json
        import subprocess
        import sys

        child = subprocess.run(
            [sys.executable, "-c", {child_code!r}],
            check=False,
            capture_output=True,
            text=True,
        )
        print(json.dumps({{
            "parent_flags": [
                sys.flags.isolated,
                sys.flags.no_site,
                sys.flags.dont_write_bytecode,
            ],
            "child_status": child.returncode,
            "child": json.loads(child.stdout),
        }}))
        """
    )

    result = subprocess.run(
        [os.fspath(control_python), "-I", "-S", "-B", "-c", parent_code],
        cwd=tmp_path,
        env={"HOME": os.fspath(tmp_path), "PATH": "/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["parent_flags"] == [1, 1, 1]
    assert observed["child_status"] == 0
    assert observed["child"]["value"] == 19
    assert Path(observed["child"]["origin"]) == foreign / "shared_editable_probe.py"
    assert observed["child"]["isolated"] == 0
    assert observed["child"]["no_site"] == 0
    assert observed["child"]["dont_write_bytecode"] == 0


def test_inherited_child_tracked_direct_script_entry_executes(tmp_path: Path):
    sentinel = tmp_path / "tracked-script-ran"
    source = f"open({os.fspath(sentinel)!r}, 'w').write('ran')\n"
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"tools/tracked_entry.py": source}
    )
    script = layout.checkout / "tools/tracked_entry.py"
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), os.fspath(script)],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert sentinel.read_text(encoding="utf-8") == "ran"
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_untracked_direct_script_refuses_before_execution(
    tmp_path: Path,
):
    sentinel = tmp_path / "untracked-script-ran"
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"tools/anchor.py": "VALUE = 44\n"}
    )
    script = layout.checkout / "tools/untracked_entry.py"
    script.write_text(
        f"open({os.fspath(sentinel)!r}, 'w').write('ran')\n"
        "__import__('os').unlink(__file__)\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), os.fspath(script)],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, result.stdout + result.stderr
        assert not sentinel.exists()
        assert script.is_file()
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("mutation", ("argv", "symlink-swap"))
def test_inherited_child_run_file_revalidates_entry_before_script_bytes(
    tmp_path: Path,
    mutation: str,
):
    sentinel = tmp_path / f"{mutation}-script-ran"
    source = f"open({os.fspath(sentinel)!r}, 'w').write('ran')\n"
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"tools/revalidated_entry.py": source},
    )
    script = layout.checkout / "tools/revalidated_entry.py"
    foreign = tmp_path / "foreign_entry.py"
    foreign.write_text(source, encoding="utf-8")
    if mutation == "argv":
        probe_line = f"import sys;sys.argv[0]={os.fspath(foreign)!r}\n"
    else:
        probe_line = (
            "import sys;"
            "_o=sys.modules['os'];"
            f"_o.unlink({os.fspath(script)!r});"
            f"_o.symlink({os.fspath(foreign)!r},{os.fspath(script)!r})\n"
        )
    (prepared.purelib / "zz-maez-task4-run-file-swap.pth").write_text(
        probe_line, encoding="utf-8"
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), os.fspath(script)],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, result.stdout + result.stderr
        assert not sentinel.exists()
        marker_tokens = airlock._read_marker_state(prepared.violation_dir)
        assert marker_tokens[0] == "airlock_import_provenance_violation"
        assert set(marker_tokens).issubset(
            {
                "airlock_import_provenance_violation",
                "airlock_path_provenance_violation",
            }
        )
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    ("launcher", "empty_environment"),
    (
        ("sys-executable", False),
        ("python", False),
        ("python3", False),
        ("sys-executable", True),
    ),
    ids=("sys-executable", "python", "python3", "absolute-env-empty"),
)
def test_inherited_child_c_forms_are_guarded_clean_without_bytecode_residue(
    tmp_path: Path,
    launcher: str,
    empty_environment: bool,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    before_artifacts = {
        path.relative_to(layout.checkout)
        for path in layout.checkout.rglob("*")
        if path.name == "__pycache__" or path.suffix == ".pyc"
    }
    executable = (
        os.fspath(prepared.python) if launcher == "sys-executable" else launcher
    )
    code = (
        "import core.good,json,sys;"
        "g=sys.modules['_maez_worktree_airlock_guard'];"
        "print(json.dumps({"
        "'executable':sys.executable,"
        "'guard_ready':g.AIRLOCK_READY,"
        "'module_origin':core.good.__file__,"
        "'path':sys.path,"
        "'dont_write_bytecode':sys.dont_write_bytecode}))"
    )
    try:
        result = subprocess.run(
            [executable, "-c", code],
            cwd=layout.checkout,
            env={} if empty_environment else prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        observed = json.loads(result.stdout)
        assert Path(observed["executable"]).resolve().is_relative_to(
            prepared.venv.resolve()
        )
        assert observed["guard_ready"] is True
        assert Path(observed["module_origin"]) == layout.checkout / "core/good.py"
        assert "" not in observed["path"]
        assert observed["dont_write_bytecode"] is True
        after_artifacts = {
            path.relative_to(layout.checkout)
            for path in layout.checkout.rglob("*")
            if path.name == "__pycache__" or path.suffix == ".pyc"
        }
        assert after_artifacts == before_artifacts
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_absolute_env_empty_preserves_all_bytecode_inventories(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    disposable_probe = prepared.purelib / "disposable_probe.py"
    disposable_probe.write_text("VALUE = 45\n", encoding="utf-8")
    roots = (layout.checkout, prepared.root, layout.shared_purelib)
    before = tuple(_bytecode_inventory(root) for root in roots)
    code = (
        "import core.good,dependency_probe,disposable_probe,json,sys;"
        "g=sys.modules['_maez_worktree_airlock_guard'];"
        "print(json.dumps({"
        "'checkout':core.good.__file__,"
        "'disposable':disposable_probe.__file__,"
        "'dependency':dependency_probe.__file__,"
        "'shared':g._SHARED_PURELIB,"
        "'dont_write_bytecode':sys.dont_write_bytecode}))"
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-c", code],
            cwd=layout.checkout,
            env={},
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        observed = json.loads(result.stdout)
        assert Path(observed["checkout"]) == layout.checkout / "core/good.py"
        assert Path(observed["disposable"]) == disposable_probe
        assert Path(observed["dependency"]) == (
            layout.shared_purelib / "dependency_probe.py"
        )
        assert Path(observed["shared"]) == layout.shared_purelib
        assert observed["dont_write_bytecode"] is True
        assert tuple(_bytecode_inventory(root) for root in roots) == before
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_run_command_audit_hook_is_inert_one_shot_and_consumes_first(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = textwrap.dedent(
        """
        import json
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        assert guard._RUN_COMMAND_PATH_PENDING is False
        events = []
        guard._normalize_command_path0 = lambda: events.append('normalize')
        guard.audit_before_pytest = lambda: events.append('audit')
        sys.audit('airlock.non_run_command')
        inert_events = list(events)
        sys.audit('cpython.run_command', 'repeat')
        repeat_events = list(events)

        class Expected(Exception):
            pass

        def first_work():
            events.append(('pending-during-work', guard._RUN_COMMAND_PATH_PENDING))
            raise Expected

        guard._RUN_COMMAND_PATH_PENDING = True
        guard._normalize_command_path0 = first_work
        try:
            guard._run_command_audit_hook('cpython.run_command', ('direct',))
        except Expected:
            pass
        print(json.dumps({
            'inert': inert_events,
            'repeat': repeat_events,
            'tail': events[-1],
            'pending': guard._RUN_COMMAND_PATH_PENDING,
        }))
        """
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-c", code],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        observed = json.loads(result.stdout)
        assert observed == {
            "inert": [],
            "repeat": ["audit"],
            "tail": ["pending-during-work", False],
            "pending": False,
        }
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_startup_phase_hook_never_normalizes_command_path(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = textwrap.dedent(
        """
        import json
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        events = []
        guard._normalize_command_path0 = lambda: events.append('normalize')
        guard._revalidate_run_file_event = (
            lambda args: events.append(['revalidate', list(args)])
        )

        guard._PRE_STARTUP_BASELINE_AUDIT_PENDING = True
        sys.audit('airlock.unrelated_startup_event')
        unrelated_pending = guard._PRE_STARTUP_BASELINE_AUDIT_PENDING

        sys.audit('cpython.run_module', 'synthetic-module')
        module_pending = guard._PRE_STARTUP_BASELINE_AUDIT_PENDING

        guard._PRE_STARTUP_BASELINE_AUDIT_PENDING = True
        sys.audit('cpython.run_file', 'synthetic-script')
        file_pending = guard._PRE_STARTUP_BASELINE_AUDIT_PENDING

        print(json.dumps({
            'events': events,
            'unrelated_pending': unrelated_pending,
            'module_pending': module_pending,
            'file_pending': file_pending,
        }))
        """
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-c", code],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout) == {
            "events": [["revalidate", ["synthetic-script"]]],
            "unrelated_pending": True,
            "module_pending": False,
            "file_pending": False,
        }
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("mode", ("module", "script"))
def test_inherited_child_non_command_mode_cannot_arm_run_command_normalization(
    tmp_path: Path,
    mode: str,
):
    probe = textwrap.dedent(
        """
        __import__('sys').audit('cpython.run_command', 'synthetic-before-imports')
        import json
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        print(json.dumps({
            'path0': sys.path[0],
            'pending': guard._RUN_COMMAND_PATH_PENDING,
        }))
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={
            "core/run_event_probe.py": probe,
            "tools/run_event_probe.py": probe,
        },
    )
    if mode == "module":
        command = [os.fspath(prepared.python), "-m", "core.run_event_probe"]
        expected = layout.checkout
    else:
        script = layout.checkout / "tools/run_event_probe.py"
        command = [os.fspath(prepared.python), os.fspath(script)]
        expected = script.parent
    try:
        result = subprocess.run(
            command,
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        observed = json.loads(result.stdout)
        assert Path(observed["path0"]) == expected
        assert observed["pending"] is False
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_post_startup_base_list_prefix_mutation_is_sticky(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"plugins/anchor.py": "VALUE = 44\n"}
    )
    code = textwrap.dedent(
        f"""
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        list.insert(sys.path, 0, {os.fspath(layout.checkout / 'plugins')!r})
        caught = False
        try:
            guard.audit_before_pytest()
        except RuntimeError:
            caught = True
        assert caught
        """
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)

        assert result.returncode == 0, result.stdout + result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("mode", ("module", "script"))
def test_inherited_child_first_post_startup_mismatch_refuses_and_cannot_rearm(
    tmp_path: Path,
    mode: str,
):
    result_path = tmp_path / f"{mode}-startup-probe-result"
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"core/startup_probe.py": "\n", "tools/startup_probe.py": "\n"},
    )
    _install_pre_startup_mismatch_probe(prepared, result_path)
    if mode == "module":
        command = [os.fspath(prepared.python), "-m", "core.startup_probe"]
    else:
        command = [
            os.fspath(prepared.python),
            os.fspath(layout.checkout / "tools/startup_probe.py"),
        ]
    try:
        result = subprocess.run(
            command,
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result_path.read_text(encoding="ascii") == "1:1:1", (
            result.stdout + result.stderr
        )
        marker_tokens = airlock._read_marker_state(prepared.violation_dir)
        assert len(marker_tokens) >= 2
        assert set(marker_tokens) == {"airlock_path_provenance_violation"}
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("mode", ("module", "script"))
def test_inherited_child_forbidden_first_startup_mismatch_cannot_rearm(
    tmp_path: Path,
    mode: str,
):
    result_path = tmp_path / f"{mode}-forbidden-startup-probe-result"
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"core/startup_probe.py": "\n", "tools/startup_probe.py": "\n"},
    )
    _install_pre_startup_mismatch_probe(
        prepared,
        result_path,
        forbidden_first=tmp_path / "foreign-startup-path",
    )
    if mode == "module":
        command = [os.fspath(prepared.python), "-m", "core.startup_probe"]
    else:
        command = [
            os.fspath(prepared.python),
            os.fspath(layout.checkout / "tools/startup_probe.py"),
        ]
    try:
        result = subprocess.run(
            command,
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result_path.read_text(encoding="ascii") == "1:1:1", (
            result.stdout + result.stderr
        )
        marker_tokens = airlock._read_marker_state(prepared.violation_dir)
        assert len(marker_tokens) >= 2
        assert set(marker_tokens) == {"airlock_path_provenance_violation"}
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("mode", ("module", "script"))
def test_inherited_child_module_and_script_keep_path_zero_semantics(
    tmp_path: Path,
    mode: str,
):
    probe = textwrap.dedent(
        """
        import core.good
        import json
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        print(json.dumps({
            'path0': sys.path[0],
            'pending': guard._STARTUP_PATH0_PENDING,
            'frozen': guard._FROZEN_STARTUP_PATH == tuple(sys.path),
        }))
        """
    )
    extra_files = {
        "core/path0_probe.py": probe,
        "tools/path0_probe.py": probe,
    }
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files=extra_files
    )
    if mode == "module":
        command = [os.fspath(prepared.python), "-m", "core.path0_probe"]
        expected = layout.checkout
    else:
        script = layout.checkout / "tools/path0_probe.py"
        command = [os.fspath(prepared.python), os.fspath(script)]
        expected = script.parent
    try:
        result = subprocess.run(
            command,
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        observed = json.loads(result.stdout)
        assert Path(observed["path0"]) == expected
        assert observed["pending"] is False
        assert observed["frozen"] is True
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("mode", ("module", "script"))
@pytest.mark.parametrize("mutation", ("wrapper", "reassignment", "direct-list"))
def test_inherited_child_frozen_startup_path_rejects_every_mutation_plane(
    tmp_path: Path,
    mode: str,
    mutation: str,
):
    plugin = tmp_path / "checkout" / "plugins"
    mutations = {
        "wrapper": f"sys.path.append({os.fspath(plugin)!r})",
        "reassignment": "sys.path = guard._ValidatingPath(sys.path)",
        "direct-list": "list.pop(sys.path, 0)",
    }
    probe = textwrap.dedent(
        f"""
        import core.good
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        assert guard._FROZEN_STARTUP_PATH == tuple(sys.path)
        caught = False
        try:
            {mutations[mutation]}
            guard._audit_paths()
        except RuntimeError:
            caught = True
        assert caught
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={
            "core/freeze_probe.py": probe,
            "tools/freeze_probe.py": probe,
            "plugins/anchor.py": "VALUE = 44\n",
        },
    )
    if mode == "module":
        command = [os.fspath(prepared.python), "-m", "core.freeze_probe"]
    else:
        command = [
            os.fspath(prepared.python),
            os.fspath(layout.checkout / "tools/freeze_probe.py"),
        ]
    try:
        result = subprocess.run(
            command,
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_frozen_path_duplicate_is_true_noop_but_new_path_refuses(
    tmp_path: Path,
):
    probe = textwrap.dedent(
        """
        import core.good
        import os
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        original = sys.path
        before = tuple(sys.path)
        sys.path.insert(0, guard._CHECKOUT)
        assert sys.path is original
        assert tuple(sys.path) == before
        assert os.listdir(guard._VIOLATION_DIR) == []
        caught = False
        try:
            sys.path.append(guard._CHECKOUT + '/plugins')
        except RuntimeError:
            caught = True
        assert caught
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={
            "tools/noop_path_probe.py": probe,
            "plugins/anchor.py": "VALUE = 44\n",
        },
    )
    try:
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                os.fspath(layout.checkout / "tools/noop_path_probe.py"),
            ],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_reassigned_away_frozen_path_cannot_absorb_exact_noop(
    tmp_path: Path,
):
    probe = textwrap.dedent(
        """
        import core.good
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        saved = sys.path
        sys.path = []
        caught = False
        try:
            saved.insert(0, guard._CHECKOUT)
        except RuntimeError:
            caught = True
        assert caught
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"tools/reassigned_path_probe.py": probe},
    )
    try:
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                os.fspath(layout.checkout / "tools/reassigned_path_probe.py"),
            ],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    "mutation",
    (
        "sys.path.append(guard._CHECKOUT)",
        "sys.path.extend([guard._CHECKOUT])",
        "sys.path.insert(1, guard._CHECKOUT)",
        "sys.path.insert(False, guard._CHECKOUT)",
        "sys.path.insert(0, guard._SHARED_PURELIB)",
    ),
    ids=(
        "append-checkout",
        "extend-checkout",
        "insert-checkout-other-index",
        "insert-checkout-bool-index",
        "insert-other-duplicate-origin",
    ),
)
def test_inherited_child_rejects_every_duplicate_path_shape_except_exact_noop(
    tmp_path: Path,
    mutation: str,
):
    probe = textwrap.dedent(
        f"""
        import core.good
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        caught = False
        try:
            {mutation}
        except RuntimeError:
            caught = True
        assert caught
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"tools/duplicate_path_shape_probe.py": probe},
    )
    try:
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                os.fspath(layout.checkout / "tools/duplicate_path_shape_probe.py"),
            ],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_exact_path_noop_refuses_after_sticky_violation(
    tmp_path: Path,
):
    probe = textwrap.dedent(
        """
        import core.good
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        first_caught = False
        try:
            sys.path.append(guard._CHECKOUT + '/foreign')
        except RuntimeError:
            first_caught = True
        assert first_caught
        second_caught = False
        try:
            sys.path.insert(0, guard._CHECKOUT)
        except RuntimeError:
            second_caught = True
        assert second_caught
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"tools/sticky_then_noop_probe.py": probe},
    )
    try:
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                os.fspath(layout.checkout / "tools/sticky_then_noop_probe.py"),
            ],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_lexical_duplicate_with_foreign_symlink_refuses(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    foreign = tmp_path / "foreign" / "child"
    foreign.mkdir(parents=True)
    link = layout.checkout / "apparent-duplicate"
    link.symlink_to(foreign, target_is_directory=True)
    lexical_duplicate = os.fspath(link / "..")
    assert os.path.normpath(lexical_duplicate) == os.fspath(layout.checkout)
    code = textwrap.dedent(
        f"""
        import sys

        caught = False
        try:
            sys.path.insert(0, {lexical_duplicate!r})
        except RuntimeError:
            caught = True
        assert caught
        """
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-I", "-B", "-c", code],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_frozen_path_noop_cannot_mask_prior_base_list_corruption(
    tmp_path: Path,
):
    probe = textwrap.dedent(
        """
        import core.good
        import sys

        removed = list.pop(sys.path, 0)
        caught = False
        try:
            sys.path.insert(0, removed)
        except RuntimeError:
            caught = True
        assert caught
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"tools/corrupt_then_restore_probe.py": probe},
    )
    try:
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                os.fspath(
                    layout.checkout / "tools/corrupt_then_restore_probe.py"
                ),
            ],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_frozen_startup_path_revalidates_same_text_target(
    tmp_path: Path,
):
    sentinel = tmp_path / "retargeted-import-ran"
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "retarget_probe.py").write_text(
        f"open({os.fspath(sentinel)!r}, 'w').write('ran')\n",
        encoding="utf-8",
    )
    tools = tmp_path / "checkout" / "tools"
    moved_tools = tmp_path / "checkout" / "tools-original"
    probe = textwrap.dedent(
        f"""
        import core.good
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        os_module = sys.modules['os']
        os_module.rename({os.fspath(tools)!r}, {os.fspath(moved_tools)!r})
        os_module.symlink({os.fspath(foreign)!r}, {os.fspath(tools)!r})
        caught = False
        try:
            guard._audit_paths()
        except RuntimeError:
            caught = True
        if not caught:
            try:
                __import__('retarget_probe')
            except RuntimeError:
                pass
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"tools/frozen_retarget.py": probe},
    )
    script = layout.checkout / "tools/frozen_retarget.py"
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), os.fspath(script)],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_grandchild_retains_disposable_guarded_provenance(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    grandchild_code = (
        "import core.good,json,sys;"
        "g=sys.modules['_maez_worktree_airlock_guard'];"
        "print(json.dumps({"
        "'executable':sys.executable,"
        "'origin':core.good.__file__,"
        "'ready':g.AIRLOCK_READY,"
        "'path':sys.path}))"
    )
    child_code = textwrap.dedent(
        f"""
        import json
        import subprocess
        import sys

        grandchild = subprocess.run(
            ['python3', '-c', {grandchild_code!r}],
            check=False,
            capture_output=True,
            text=True,
        )
        print(json.dumps({{
            'executable': sys.executable,
            'grandchild_status': grandchild.returncode,
            'grandchild': json.loads(grandchild.stdout),
        }}))
        """
    )
    try:
        result = subprocess.run(
            ["python", "-c", child_code],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        observed = json.loads(result.stdout)
        assert Path(observed["executable"]).resolve() == prepared.python.resolve()
        assert observed["grandchild_status"] == 0
        assert Path(observed["grandchild"]["executable"]).resolve().is_relative_to(
            prepared.venv.resolve()
        )
        assert Path(observed["grandchild"]["origin"]) == layout.checkout / "core/good.py"
        assert observed["grandchild"]["ready"] is True
        assert "" not in observed["grandchild"]["path"]
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_grandchild_caught_violation_leaves_sticky_marker(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    grandchild_code = textwrap.dedent(
        """
        import sys
        caught = False
        try:
            sys.path.append('/foreign/grandchild')
        except RuntimeError:
            caught = True
        assert caught
        """
    )
    child_code = textwrap.dedent(
        f"""
        import subprocess
        import sys
        grandchild = subprocess.run([sys.executable, '-c', {grandchild_code!r}])
        assert grandchild.returncode == 0
        """
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-c", child_code],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_absolute_foreign_interpreter_is_outside_without_no_site(
    tmp_path: Path,
):
    airlock, _layout, _inventory, prepared = _task3_prepared(tmp_path)
    probe = (
        "import sys;"
        "print(sys.executable);"
        "print('_maez_worktree_airlock_guard' in sys.modules)"
    )
    try:
        foreign = subprocess.run(
            [
                os.fspath(Path(sys._base_executable).resolve()),
                "-I",
                "-B",
                "-c",
                probe,
            ],
            cwd=tmp_path,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert foreign.returncode == 0, foreign.stderr
        lines = foreign.stdout.splitlines()
        assert Path(lines[0]).resolve() != prepared.python.resolve()
        assert lines[1] == "False"
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_disposable_no_site_project_import_is_outside(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    try:
        no_site = subprocess.run(
            [
                os.fspath(prepared.python),
                "-S",
                "-B",
                "-c",
                "import core.good,sys;print(sys.executable);"
                "print(core.good.__file__);"
                "print('_maez_worktree_airlock_guard' in sys.modules)",
            ],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert no_site.returncode == 0, no_site.stderr
        lines = no_site.stdout.splitlines()
        assert Path(lines[0]).resolve() == prepared.python.resolve()
        assert Path(lines[1]) == layout.checkout / "core/good.py"
        assert lines[2] == "False"
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_bare_empty_environment_interpreters_remain_outside(
    tmp_path: Path,
):
    airlock, _layout, _inventory, prepared = _task3_prepared(tmp_path)
    probe = (
        "import sys;"
        "print(sys.executable);"
        "print('_maez_worktree_airlock_guard' in sys.modules)"
    )
    try:
        for bare in ("python", "python3"):
            resolved = shutil.which(bare, path=os.defpath)
            if resolved is None:
                with pytest.raises(FileNotFoundError):
                    subprocess.run([bare, "-c", "pass"], env={}, check=False)
                continue
            outside = subprocess.run(
                [bare, "-I", "-S", "-B", "-c", probe],
                env={},
                check=False,
                capture_output=True,
                text=True,
            )
            assert outside.returncode == 0, outside.stderr
            lines = outside.stdout.splitlines()
            assert Path(lines[0]).resolve() != prepared.python.resolve()
            assert lines[1] == "False"
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_contract_contains_no_task5_certification_seam(tmp_path: Path):
    airlock = _airlock()
    runner = airlock._runner_source(tmp_path / "diagnostic")
    inner = inspect.getsource(airlock._inner_main)

    assert "MAEZ_AIRLOCK_CERTIFIED" not in runner
    assert "MAEZ_AIRLOCK_CERTIFIED" not in inner
    assert "_write_certificate" not in runner
    assert "_write_certificate" not in inner


def test_inherited_child_design_qualifies_absolute_interpreter_bypass_as_foreign():
    design = (
        REPO
        / "docs/superpowers/specs/2026-07-16-clean-checkout-import-airlock-design.md"
    ).read_text(encoding="utf-8")

    assert "Absolute foreign-interpreter literals" in design
    assert "Absolute interpreter literals and project-import descendants" not in design


def test_inherited_child_task4_plan_authorizes_exact_atomic_four_file_scope():
    plan = (
        REPO / "docs/superpowers/plans/2026-07-17-clean-checkout-import-airlock.md"
    ).read_text(encoding="utf-8")
    task4 = plan.split("## Task 4: Inherited descendant contract", 1)[1].split(
        "## Task 5:", 1
    )[0]
    files = task4.split("- [ ]", 1)[0]
    expected = (
        "docs/superpowers/plans/2026-07-17-clean-checkout-import-airlock.md",
        "docs/superpowers/specs/2026-07-16-clean-checkout-import-airlock-design.md",
        "scripts/dev/worktree_test_airlock.py",
        "tests/test_worktree_airlock_imports.py",
    )

    assert files.count("- Modify:") == len(expected)
    for path in expected:
        assert f"- Modify: `{path}`" in files


def test_inherited_child_direct_script_preexecution_validation_is_documented():
    documents = (
        REPO / "docs/superpowers/plans/2026-07-17-clean-checkout-import-airlock.md",
        REPO
        / "docs/superpowers/specs/2026-07-16-clean-checkout-import-airlock-design.md",
    )

    for document in documents:
        text = document.read_text(encoding="utf-8")
        assert "cpython.run_file" in text
        assert "before CPython opens the file or executes any script" in text
        assert "untracked script" in text
        assert "_RUNNER_PATH" in text


def test_module_description_names_the_landed_certifying_airlock():
    airlock = _airlock()

    assert "disposable no-pip interpreter carries" in airlock.__doc__
    assert "checkout-bound path and\nimport-provenance guard" in airlock.__doc__
    assert "only the outer stage can certify a completed run" in airlock.__doc__
    assert "subsequent task" not in airlock.__doc__


def test_disposable_interpreter_imports_pytest_without_outer_site_or_maez(
    tmp_path: Path,
):
    airlock = _airlock()
    assert "site" not in airlock.__dict__
    assert not any(root in airlock.__dict__ for root in ("core", "skills", "daemon"))
    layout = airlock.AirlockLayout(
        shared_python=SHARED_PYTHON,
        shared_purelib=Path(
            subprocess.run(
                [
                    os.fspath(SHARED_PYTHON),
                    "-I",
                    "-S",
                    "-B",
                    "-c",
                    "import sysconfig;print(sysconfig.get_path('purelib'))",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        ),
        checkout=REPO,
    )
    prepared = airlock._prepare_disposable(
        layout, airlock._discover_inventory(REPO), root_parent=tmp_path
    )
    try:
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                "-I",
                "-B",
                "-c",
                "import json,pytest,sys;print(json.dumps({'pytest': pytest.__version__, 'exe': sys.executable}))",
            ],
            cwd=REPO,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        observed = json.loads(result.stdout)
        assert observed["pytest"]
        assert Path(observed["exe"]) == prepared.python
    finally:
        airlock._remove_disposable(prepared.root)


def test_disposable_layout_is_private_minimal_and_has_no_pip(tmp_path: Path):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    prepared = airlock._prepare_disposable(
        layout, _inventory_for(layout.checkout), root_parent=tmp_path
    )
    try:
        assert stat.S_IMODE(prepared.root.stat().st_mode) == 0o700
        assert prepared.python.is_file()
        assert not (prepared.root / "venv" / "bin" / "pip").exists()
        assert not (prepared.purelib / "pip").exists()
        assert sorted(path.name for path in prepared.purelib.glob("*.pth")) == [
            "maez-worktree-airlock.pth"
        ]
        assert prepared.pytest_config.read_text(encoding="utf-8") == ""
        assert prepared.diagnostic.exists() is False
        for authored in (
            prepared.controlled_pth,
            prepared.guard,
            prepared.pytest_config,
            prepared.runner,
        ):
            info = authored.stat()
            assert stat.S_IMODE(info.st_mode) == 0o600
            assert info.st_nlink == 1
        assert stat.S_IMODE(prepared.violation_dir.stat().st_mode) == 0o700
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("isolated", (True, False), ids=("safe-path", "script-path0"))
def test_disposable_runner_creates_only_one_private_diagnostic(
    tmp_path: Path,
    isolated: bool,
):
    airlock = _airlock()
    layout = airlock.AirlockLayout(
        shared_python=SHARED_PYTHON,
        shared_purelib=Path(
            subprocess.run(
                [
                    os.fspath(SHARED_PYTHON),
                    "-I",
                    "-S",
                    "-B",
                    "-c",
                    "import sysconfig;print(sysconfig.get_path('purelib'))",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        ),
        checkout=REPO,
    )
    prepared = airlock._prepare_disposable(
        layout, airlock._discover_inventory(REPO), root_parent=tmp_path
    )
    try:
        command = [os.fspath(prepared.python)]
        if isolated:
            command.append("-I")
        command.extend(("-B", os.fspath(prepared.runner)))
        result = subprocess.run(
            command,
            cwd=REPO,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 86
        assert result.stdout.splitlines() == [
            "airlock_inner_noncertifying",
            "airlock_inner_complete:86:call_phase_observed=0",
        ]
        info = prepared.diagnostic.stat()
        assert stat.S_ISREG(info.st_mode)
        assert stat.S_IMODE(info.st_mode) == 0o600
        assert info.st_nlink == 1
        assert "MAEZ_AIRLOCK_CERTIFIED" not in prepared.runner.read_text(
            encoding="utf-8"
        )
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_disposable_runner_forces_diagnostic_mode_under_restrictive_umask(
    tmp_path: Path,
):
    airlock = _airlock()
    layout = airlock.AirlockLayout(
        shared_python=SHARED_PYTHON,
        shared_purelib=Path(
            subprocess.run(
                [
                    os.fspath(SHARED_PYTHON),
                    "-I",
                    "-S",
                    "-B",
                    "-c",
                    "import sysconfig;print(sysconfig.get_path('purelib'))",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        ),
        checkout=REPO,
    )
    prepared = airlock._prepare_disposable(
        layout, airlock._discover_inventory(REPO), root_parent=tmp_path
    )
    wrapper = (
        "import builtins,os;"
        "os.umask(0o777);"
        f"p={os.fspath(prepared.runner)!r};"
        "builtins.exec(builtins.compile(builtins.open(p,'rb').read(),p,'exec'))"
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-I", "-B", "-c", wrapper],
            cwd=REPO,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 86
        info = prepared.diagnostic.stat()
        assert stat.S_IMODE(info.st_mode) == 0o600
        assert info.st_nlink == 1
    finally:
        airlock._remove_disposable(prepared.root)


def test_disposable_runner_refuses_before_control_record_when_diagnostic_proof_fails(
    tmp_path: Path,
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    prepared = airlock._prepare_disposable(
        layout, _inventory_for(layout.checkout), root_parent=tmp_path
    )
    wrapper = (
        "import builtins,os,types;"
        "os.fstat=lambda _fd:types.SimpleNamespace(st_mode=0,st_nlink=2);"
        f"p={os.fspath(prepared.runner)!r};"
        "builtins.exec(builtins.compile(builtins.open(p,'rb').read(),p,'exec'))"
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-I", "-B", "-c", wrapper],
            cwd=tmp_path,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 86
        assert result.stdout == ""
        source = prepared.runner.read_text(encoding="utf-8")
        assert "os.fchmod" in source
        assert "os.fstat" in source
        assert "stat.S_ISREG" in source
        assert "st_nlink" in source
    finally:
        airlock._remove_disposable(prepared.root)


def test_controlled_pth_exact_origin_is_idempotent_across_reprocessing(
    tmp_path: Path,
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    prepared = airlock._prepare_disposable(
        layout, _inventory_for(layout.checkout), root_parent=tmp_path
    )
    executable_line = next(
        line
        for line in prepared.controlled_pth.read_text(encoding="utf-8").splitlines()
        if line.startswith("import ")
    )
    code = (
        "import builtins,json,sys;"
        f"line={executable_line!r};"
        "builtins.exec(line);builtins.exec(line);"
        "m=sys.modules['_maez_worktree_airlock_guard'];"
        "print(json.dumps([m.__file__,m.AIRLOCK_READY,m.AIRLOCK_LOAD_COUNT,"
        "m.AUDIT_HOOK_INSTALL_COUNT]))"
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-I", "-B", "-c", code],
            cwd=tmp_path,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == [os.fspath(prepared.guard), True, 1, 1]
    finally:
        airlock._remove_disposable(prepared.root)


def test_addsitedir_shared_purelib_refuses_before_editable_pth_executes(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    sentinel = tmp_path / "editable-pth-ran"
    (layout.shared_purelib / "editable.pth").write_text(
        f"import pathlib;pathlib.Path({os.fspath(sentinel)!r}).touch()\n",
        encoding="utf-8",
    )
    code = (
        "import site;"
        "caught=False;"
        "\ntry:\n"
        f" site.addsitedir({os.fspath(layout.shared_purelib)!r})\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("resolution", ("reload", "delete-reimport"))
def test_later_site_resolution_cannot_restore_raw_addsitedir_before_pth_executes(
    tmp_path: Path, resolution: str
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    sentinel = tmp_path / "reloaded-site-editable-pth-ran"
    (layout.shared_purelib / "editable.pth").write_text(
        f"import pathlib;pathlib.Path({os.fspath(sentinel)!r}).touch()\n",
        encoding="utf-8",
    )
    resolve = {
        "reload": "importlib.reload(site)",
        "delete-reimport": "sys.modules.pop('site');site=importlib.import_module('site')",
    }[resolution]
    code = (
        "import importlib,site,sys;"
        "caught=False;"
        f"\ntry:\n {resolve}\n"
        "except RuntimeError:\n caught=True\n"
        f"if not caught:\n site.addsitedir({os.fspath(layout.shared_purelib)!r})\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_cached_site_import_keeps_guarded_addsitedir_callable(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = (
        "import site,sys;g=sys.modules['_maez_worktree_airlock_guard'];"
        "assert site.addsitedir is g._guarded_addsitedir;g.audit_before_pytest()"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_module_plane_accepts_only_tracked_checkout_and_dependency_roots(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = (
        "import core.good,core.ns,dependency_probe,sys;"
        "g=sys.modules['_maez_worktree_airlock_guard'];"
        "g.audit_loaded_modules();"
        "assert core.good.VALUE==41;"
        "assert dependency_probe.VALUE==43;"
        f"assert core.good.__file__=={os.fspath(layout.checkout / 'core/good.py')!r};"
        f"assert dependency_probe.__file__=={os.fspath(layout.shared_purelib / 'dependency_probe.py')!r}"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_module_plane_accepts_tracked_module_from_allowed_tracked_subdirectory(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"plugins/anchor.py": "VALUE = 44\n"}
    )
    code = (
        "import sys;"
        f"sys.path.append({os.fspath(layout.checkout / 'plugins')!r});"
        "import anchor;assert anchor.VALUE==44;"
        "g=sys.modules['_maez_worktree_airlock_guard'];g.audit_loaded_modules()"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_module_plane_guard_normalizes_paths_before_new_import_resolution(
    tmp_path: Path,
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    source = airlock._guard_source(
        layout,
        _inventory_for(layout.checkout),
        disposable_purelib=tmp_path / "disposable-purelib",
        violation_dir=tmp_path / "violations",
    )

    path_install = source.index("_sys.path = _ValidatingPath")
    site_import = source.index("import site as _site")
    assert path_install < site_import
    assert "import importlib.abc" not in source


def test_module_plane_guard_makes_every_startup_import_after_path_normalization(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    tracker_line = (
        "import builtins,sys;"
        "builtins._airlock_import_events=[];"
        "builtins._AirlockImportTracker=type('_AirlockImportTracker',(),{"
        "'find_spec':lambda self,fullname,path=None,target=None:"
        "(builtins._airlock_import_events.append((fullname,type(sys.path).__name__)) and None)});"
        "sys.meta_path.insert(0,builtins._AirlockImportTracker())\n"
    )
    (prepared.purelib / "000-airlock-import-tracker.pth").write_text(
        tracker_line, encoding="utf-8"
    )
    code = (
        "import builtins,json;events=builtins._airlock_import_events;"
        "assert events;"
        "assert all(path_type=='_ValidatingPath' for _name,path_type in events),events;"
        "print(json.dumps(events))"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)
    finally:
        airlock._remove_disposable(prepared.root)


def test_foreign_module_from_exact_dependency_purelib_is_refused(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    dirty = layout.shared_purelib / "core/dirty.py"
    dirty.parent.mkdir()
    dirty.write_text("VALUE = 99\n", encoding="utf-8")
    code = (
        "import importlib.machinery,sys,types;"
        "import dependency_probe;assert dependency_probe.VALUE==43;"
        "m=types.ModuleType('core.dirty');"
        f"m.__file__={os.fspath(dirty)!r};"
        f"m.__spec__=importlib.machinery.ModuleSpec('core.dirty',loader=None,origin={os.fspath(dirty)!r});"
        "sys.modules['core.dirty']=m;"
        "g=sys.modules['_maez_worktree_airlock_guard'];caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


def test_foreign_module_untracked_top_level_under_allowed_checkout_dir_refuses(
    tmp_path: Path,
):
    sentinel = tmp_path / "untracked-loader-ran"
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"plugins/anchor.py": "\n"}
    )
    rogue = layout.checkout / "plugins/untracked_rogue.py"
    rogue.write_text(
        f"from pathlib import Path;Path({os.fspath(sentinel)!r}).touch()\n",
        encoding="utf-8",
    )
    code = (
        "import sys;"
        f"sys.path.append({os.fspath(rogue.parent)!r});caught=False;"
        "\ntry:\n import untracked_rogue\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    "foreign_module_shape",
    (
        "file",
        "spec-origin",
        "namespace-path",
        "search-locations",
        "mixed-namespace",
        "retained-origin",
    ),
)
def test_foreign_module_plane_is_sticky_after_local_catch(
    tmp_path: Path, foreign_module_shape: str
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    bad_file = foreign / "bad.py"
    bad_file.write_text("VALUE = 99\n", encoding="utf-8")
    namespace = layout.checkout / "core/ns"
    module_name, setup = {
        "file": (
            "core.good",
            "m.__file__=bad;"
            "m.__spec__=importlib.machinery.ModuleSpec(name,loader=None,origin=good)",
        ),
        "spec-origin": (
            "core.good",
            "m.__file__=good;"
            "m.__spec__=importlib.machinery.ModuleSpec(name,loader=None,origin=bad)",
        ),
        "namespace-path": (
            "core.ns",
            "m.__file__=None;"
            "m.__path__=[foreign];"
            "m.__spec__=importlib.machinery.ModuleSpec(name,loader=None,origin=None,is_package=True);"
            "m.__spec__.submodule_search_locations=[namespace]",
        ),
        "search-locations": (
            "core.ns",
            "m.__file__=None;"
            "m.__path__=[namespace];"
            "m.__spec__=importlib.machinery.ModuleSpec(name,loader=None,origin=None,is_package=True);"
            "m.__spec__.submodule_search_locations=[foreign]",
        ),
        "mixed-namespace": (
            "core.ns",
            "m.__file__=None;"
            "m.__path__=[namespace,foreign];"
            "m.__spec__=importlib.machinery.ModuleSpec(name,loader=None,origin=None,is_package=True);"
            "m.__spec__.submodule_search_locations=[namespace,foreign]",
        ),
        "retained-origin": (
            "core.good",
            "m.__file__=bad;"
            "m.__spec__=importlib.machinery.ModuleSpec(name,loader=None,origin=bad);"
            "sys.path[:]=[p for p in sys.path if p!=foreign]",
        ),
    }[foreign_module_shape]
    code = (
        "import importlib.machinery,sys,types;"
        f"bad={os.fspath(bad_file)!r};good={os.fspath(layout.checkout / 'core/good.py')!r};"
        f"namespace={os.fspath(namespace)!r};foreign={os.fspath(foreign)!r};"
        f"name={module_name!r};m=types.ModuleType(name);"
        f"{setup};sys.modules[name]=m;"
        "g=sys.modules['_maez_worktree_airlock_guard'];caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("mismatched_plane", ("file", "spec-origin"))
def test_module_plane_rejects_tracked_but_wrong_corresponding_file(
    tmp_path: Path, mismatched_plane: str
):
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"core/alpha.py": "\n", "core/beta.py": "\n"},
    )
    alpha = layout.checkout / "core/alpha.py"
    beta = layout.checkout / "core/beta.py"
    if mismatched_plane == "file":
        file_value, origin_value = beta, alpha
    else:
        file_value, origin_value = alpha, beta
    code = (
        "import importlib.machinery,sys,types;"
        "m=types.ModuleType('core.alpha');"
        f"m.__file__={os.fspath(file_value)!r};"
        f"m.__spec__=importlib.machinery.ModuleSpec('core.alpha',loader=None,origin={os.fspath(origin_value)!r});"
        "sys.modules['core.alpha']=m;"
        "g=sys.modules['_maez_worktree_airlock_guard'];caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


def test_module_plane_handles_top_level_module_package_collision_exactly(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"cli.py": "\n", "cli/__init__.py": "\n"},
    )
    code = (
        "import importlib.machinery,sys,types;"
        "g=sys.modules['_maez_worktree_airlock_guard'];"
        f"module_path={os.fspath(layout.checkout / 'cli.py')!r};"
        f"package_path={os.fspath(layout.checkout / 'cli/__init__.py')!r};"
        "m=types.ModuleType('cli');m.__file__=module_path;"
        "m.__spec__=importlib.machinery.ModuleSpec('cli',loader=None,origin=module_path);"
        "sys.modules['cli']=m;g.audit_loaded_modules();"
        "m.__file__=package_path;"
        "m.__spec__=importlib.machinery.ModuleSpec('cli',loader=None,origin=package_path,is_package=True);"
        f"m.__path__=[{os.fspath(layout.checkout / 'cli')!r}];"
        f"m.__spec__.submodule_search_locations=[{os.fspath(layout.checkout / 'cli')!r}];"
        "g.audit_loaded_modules()"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    "plane_shape",
    ("module-with-package-locations", "package-missing-locations", "package-wrong-dir"),
)
def test_module_plane_rejects_cross_kind_and_incomplete_package_shapes(
    tmp_path: Path, plane_shape: str
):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={
            "cli.py": "\n",
            "cli/__init__.py": "\n",
            "plugins/cli/__init__.py": "\n",
        },
    )
    module_path = layout.checkout / "cli.py"
    package_path = layout.checkout / "cli/__init__.py"
    package_dir = layout.checkout / "cli"
    wrong_package_dir = layout.checkout / "plugins/cli"
    setup = {
        "module-with-package-locations": (
            f"concrete={os.fspath(module_path)!r};"
            f"locations=[{os.fspath(package_dir)!r}]"
        ),
        "package-missing-locations": (
            f"concrete={os.fspath(package_path)!r};locations=None"
        ),
        "package-wrong-dir": (
            f"concrete={os.fspath(package_path)!r};"
            f"locations=[{os.fspath(wrong_package_dir)!r}]"
        ),
    }[plane_shape]
    code = (
        "import importlib.machinery,sys,types;"
        f"{setup};m=types.ModuleType('cli');m.__file__=concrete;"
        "m.__spec__=importlib.machinery.ModuleSpec('cli',loader=None,origin=concrete);"
        "m.__path__=locations;"
        "m.__spec__.submodule_search_locations=locations;"
        "sys.modules['cli']=m;g=sys.modules['_maez_worktree_airlock_guard'];caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    "plane_shape",
    (
        "regular-missing-file",
        "regular-missing-origin",
        "package-missing-module-path",
        "package-missing-spec-search",
        "namespace-missing-module-path",
        "namespace-missing-spec-search",
    ),
)
def test_loaded_module_plane_requires_complete_shape(
    tmp_path: Path, plane_shape: str
):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"pkg/__init__.py": "\n"}
    )
    good = layout.checkout / "core/good.py"
    package_file = layout.checkout / "pkg/__init__.py"
    package_dir = layout.checkout / "pkg"
    namespace_dir = layout.checkout / "core/ns"
    name, file_value, origin_value, module_path, search_locations = {
        "regular-missing-file": ("core.good", None, good, None, None),
        "regular-missing-origin": ("core.good", good, None, None, None),
        "package-missing-module-path": (
            "pkg",
            package_file,
            package_file,
            None,
            [package_dir],
        ),
        "package-missing-spec-search": (
            "pkg",
            package_file,
            package_file,
            [package_dir],
            None,
        ),
        "namespace-missing-module-path": (
            "core.ns",
            None,
            None,
            None,
            [namespace_dir],
        ),
        "namespace-missing-spec-search": (
            "core.ns",
            None,
            None,
            [namespace_dir],
            None,
        ),
    }[plane_shape]
    code = (
        "import importlib.machinery,sys,types;"
        f"name={name!r};file_value={os.fspath(file_value) if file_value else None!r};"
        f"origin_value={os.fspath(origin_value) if origin_value else None!r};"
        f"module_path={([os.fspath(item) for item in module_path] if module_path else None)!r};"
        f"search_locations={([os.fspath(item) for item in search_locations] if search_locations else None)!r};"
        "m=types.ModuleType(name);m.__file__=file_value;m.__path__=module_path;"
        "m.__spec__=importlib.machinery.ModuleSpec(name,loader=None,origin=origin_value);"
        "m.__spec__.submodule_search_locations=search_locations;sys.modules[name]=m;"
        "g=sys.modules['_maez_worktree_airlock_guard'];caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("malformed_plane", ("module-path", "spec-search"))
def test_malformed_loaded_module_location_plane_gets_typed_refusal(
    tmp_path: Path, malformed_plane: str
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    good = layout.checkout / "core/good.py"
    module_path = "42" if malformed_plane == "module-path" else "None"
    search_locations = "42" if malformed_plane == "spec-search" else "None"
    code = (
        "import importlib.machinery,sys,types;name='core.good';"
        f"m=types.ModuleType(name);m.__file__={os.fspath(good)!r};"
        f"m.__path__={module_path};"
        f"m.__spec__=importlib.machinery.ModuleSpec(name,loader=None,origin={os.fspath(good)!r});"
        f"m.__spec__.submodule_search_locations={search_locations};"
        "sys.modules[name]=m;g=sys.modules['_maez_worktree_airlock_guard'];caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    "escape_kind",
    (
        "symlink-escape",
        "untracked",
        "nested-unregistered",
        "nested-gitfile",
        "nested-registered",
    ),
)
def test_symlink_escape_untracked_and_nested_checkout_refuse(
    tmp_path: Path, escape_kind: str
):
    extra = {"core/candidate.py": "VALUE = 1\n"}
    airlock, layout, inventory, prepared = _task3_prepared(tmp_path, extra_files=extra)
    candidate = layout.checkout / "core/candidate.py"
    if escape_kind == "symlink-escape":
        foreign = tmp_path / "foreign.py"
        foreign.write_text("VALUE = 2\n", encoding="utf-8")
        candidate.unlink()
        candidate.symlink_to(foreign)
    elif escape_kind == "untracked":
        candidate = layout.checkout / "core/untracked.py"
        candidate.write_text("VALUE = 2\n", encoding="utf-8")
    else:
        nested = layout.checkout / "core/nested"
        nested.mkdir()
        if escape_kind == "nested-gitfile":
            (nested / ".git").write_text("gitdir: /foreign/gitdir\n", encoding="utf-8")
        else:
            (nested / ".git").mkdir()
        candidate = nested / "candidate.py"
        candidate.write_text("VALUE = 2\n", encoding="utf-8")
        if escape_kind == "nested-registered":
            inventory = airlock.GitInventory(
                **{
                    **inventory.__dict__,
                    "registered_worktrees": (*inventory.registered_worktrees, nested),
                }
            )
            airlock._remove_disposable(prepared.root)
            prepared = airlock._prepare_disposable(
                layout, inventory, root_parent=tmp_path
            )
    code = (
        "import importlib.machinery,sys,types;"
        "m=types.ModuleType('core.candidate');"
        f"m.__file__={os.fspath(candidate)!r};"
        f"m.__spec__=importlib.machinery.ModuleSpec('core.candidate',loader=None,origin={os.fspath(candidate)!r});"
        "sys.modules['core.candidate']=m;"
        "g=sys.modules['_maez_worktree_airlock_guard'];caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("operation", ("append", "insert", "extend", "slice", "iadd"))
def test_path_mutation_is_atomic_and_sticky_when_caught(
    tmp_path: Path, operation: str
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    statement = {
        "append": "sys.path.append(foreign)",
        "insert": "sys.path.insert(0,foreign)",
        "extend": "sys.path.extend([foreign])",
        "slice": "sys.path[1:1]=[foreign]",
        "iadd": "sys.path.__iadd__([foreign])",
    }[operation]
    code = (
        "import sys;g=sys.modules['_maez_worktree_airlock_guard'];"
        f"foreign={os.fspath(foreign)!r};before=list(sys.path);caught=False;"
        "\ntry:\n " + statement + "\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught;assert list(sys.path)==before"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


def test_path_mutation_direct_reassignment_is_caught_by_pre_pytest_audit(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    code = (
        "import sys;g=sys.modules['_maez_worktree_airlock_guard'];"
        f"sys.path=list(sys.path)+[{os.fspath(foreign)!r}];caught=False;"
        "\ntry:\n g.audit_before_pytest()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("mutation", ("imul", "base-reverse"))
def test_path_audit_rejects_noncanonical_allowed_projection(
    tmp_path: Path, mutation: str
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    statement = {
        "imul": "list.__imul__(sys.path,2)",
        "base-reverse": "list.reverse(sys.path)",
    }[mutation]
    code = (
        "import sys;g=sys.modules['_maez_worktree_airlock_guard'];"
        f"{statement};caught=False;"
        "\ntry:\n g._audit_paths()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_path_audit_rejects_missing_required_baseline_entry(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = (
        "import sys;g=sys.modules['_maez_worktree_airlock_guard'];"
        "sys.path.remove(g._SHARED_PURELIB);caught=False;"
        "\ntry:\n g._audit_paths()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_dispatcher_audits_direct_path_reassignment_before_import(tmp_path: Path):
    sentinel = tmp_path / "direct-reassignment-loader-ran"
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "rogue.py").write_text(
        f"from pathlib import Path;Path({os.fspath(sentinel)!r}).touch()\n",
        encoding="utf-8",
    )
    code = (
        "import sys;"
        f"sys.path=list(sys.path)+[{os.fspath(foreign)!r}];caught=False;"
        "\ntry:\n import rogue\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_allowed_path_mutation_preserves_checkout_before_dependency_collision(
    tmp_path: Path,
):
    sentinel = tmp_path / "dependency-alias-ran"
    dependency_purelib = tmp_path / "dependency-purelib"
    dependency_purelib.mkdir()
    (dependency_purelib / "anchor.py").write_text(
        f"from pathlib import Path;Path({os.fspath(sentinel)!r}).touch();VALUE=99\n",
        encoding="utf-8",
    )
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=dependency_purelib,
        extra_files={"plugins/anchor.py": "VALUE=41\n"},
    )
    code = (
        "import sys;"
        f"sys.path.append({os.fspath(layout.checkout / 'plugins')!r});"
        "import anchor;assert anchor.VALUE==41"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("operation", ("reverse", "sort", "sort-reverse"))
def test_allowed_reordering_mutation_restores_canonical_path_classes(
    tmp_path: Path, operation: str
):
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"plugins/anchor.py": "VALUE=41\n"}
    )
    statement = {
        "reverse": "sys.path.reverse()",
        "sort": "sys.path.sort()",
        "sort-reverse": "sys.path.sort(reverse=True)",
    }[operation]
    code = (
        "import sys;g=sys.modules['_maez_worktree_airlock_guard'];"
        f"sys.path.append({os.fspath(layout.checkout / 'plugins')!r});"
        f"{statement};classes=[g._path_class(p) for p in sys.path];"
        "assert classes==sorted(classes)"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_allowed_relative_path_is_canonical_before_cwd_retarget(tmp_path: Path):
    sentinel = tmp_path / "retargeted-relative-ran"
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"plugins/anchor.py": "VALUE=41\n"}
    )
    foreign_cwd = tmp_path / "foreign-cwd"
    (foreign_cwd / "plugins").mkdir(parents=True)
    (foreign_cwd / "plugins/anchor.py").write_text(
        f"from pathlib import Path;Path({os.fspath(sentinel)!r}).touch();VALUE=99\n",
        encoding="utf-8",
    )
    code = (
        "import os,sys;sys.path.append('plugins');"
        f"assert {os.fspath(layout.checkout / 'plugins')!r} in sys.path;"
        f"os.chdir({os.fspath(foreign_cwd)!r});import anchor;assert anchor.VALUE==41"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_addsitedir_disposable_site_delegates_without_refusal(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = (
        "import site,sys;"
        f"site.addsitedir({os.fspath(prepared.purelib)!r});"
        "g=sys.modules['_maez_worktree_airlock_guard'];"
        "g.audit_before_pytest()"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_arbitrary_stdlib_descendant_is_not_an_admitted_search_root(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = (
        "import os,sys;g=sys.modules['_maez_worktree_airlock_guard'];"
        "root=next(p for p in g._STDLIB_ROOTS if not p.endswith('.zip'));"
        "candidate=os.path.join(root,'dist-packages');caught=False;"
        "\ntry:\n sys.path.append(candidate)\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_path_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_dispatcher_rejects_foreign_spec_before_loader_execution(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    foreign = tmp_path / "foreign.py"
    sentinel = tmp_path / "loader-ran"
    foreign.write_text("VALUE = 7\n", encoding="utf-8")
    code = textwrap.dedent(
        f"""
        import importlib.abc, importlib.machinery, sys
        sentinel = {os.fspath(sentinel)!r}
        class Loader(importlib.abc.Loader):
            def create_module(self, spec): return None
            def exec_module(self, module): open(sentinel, 'w').close()
        class Finder:
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'core.foreign':
                    return importlib.machinery.ModuleSpec(
                        fullname, Loader(), origin={os.fspath(foreign)!r}
                    )
                return None
        guard = sys.modules['_maez_worktree_airlock_guard']
        guard.restore_dispatcher_front()
        sys.meta_path.insert(1, Finder())
        try:
            import core.foreign
        except RuntimeError:
            pass
        else:
            raise AssertionError('foreign spec loaded')
        """
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    "mutation",
    (
        "insert",
        "slice",
        "append",
        "extend",
        "set-front",
        "iadd",
        "pop-front",
        "remove-dispatcher",
        "delete-front",
        "clear",
        "reverse",
        "sort-last",
        "imul",
    ),
)
def test_meta_path_mutation_keeps_dispatcher_front_and_validates_custom_finder(
    tmp_path: Path, mutation: str
):
    sentinel = tmp_path / "meta-path-bypass-loader-ran"
    foreign = tmp_path / "foreign.py"
    foreign.write_text("VALUE=99\n", encoding="utf-8")
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    statement = {
        "insert": "sys.meta_path.insert(0,finder)",
        "slice": "sys.meta_path[0:0]=[finder]",
        "append": "sys.meta_path.append(finder)",
        "extend": "sys.meta_path.extend([finder])",
        "set-front": "sys.meta_path[0]=finder",
        "iadd": "sys.meta_path.__iadd__([finder])",
        "pop-front": "sys.meta_path.pop(0);sys.meta_path.append(finder)",
        "remove-dispatcher": (
            "sys.meta_path.remove(guard.DISPATCHER);sys.meta_path.append(finder)"
        ),
        "delete-front": "sys.meta_path.__delitem__(0);sys.meta_path.append(finder)",
        "clear": "sys.meta_path.clear();sys.meta_path.append(finder)",
        "reverse": "sys.meta_path.append(finder);sys.meta_path.reverse()",
        "sort-last": (
            "sys.meta_path.append(finder);"
            "sys.meta_path.sort(key=lambda item:item is guard.DISPATCHER)"
        ),
        "imul": "sys.meta_path.append(finder);sys.meta_path.__imul__(2)",
    }[mutation]
    code = textwrap.dedent(
        f"""
        import core, importlib.abc, importlib.machinery, sys
        class Loader(importlib.abc.Loader):
            def create_module(self, spec): return None
            def exec_module(self, module): open({os.fspath(sentinel)!r}, 'w').close()
        class Finder:
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'core.foreign':
                    return importlib.machinery.ModuleSpec(
                        fullname, Loader(), origin={os.fspath(foreign)!r}
                    )
                return None
        guard = sys.modules['_maez_worktree_airlock_guard']
        finder = Finder()
        {statement}
        assert sys.meta_path[0] is guard.DISPATCHER
        try:
            import core.foreign
        except RuntimeError:
            pass
        else:
            raise AssertionError('custom finder bypassed dispatcher')
        """
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_dispatcher_reentrant_different_name_import_cannot_bypass_validation(
    tmp_path: Path,
):
    sentinel = tmp_path / "nested-foreign-loader-ran"
    foreign = tmp_path / "foreign.py"
    foreign.write_text("VALUE=99\n", encoding="utf-8")
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"core/outer.py": "VALUE=41\n"}
    )
    code = textwrap.dedent(
        f"""
        import importlib.abc, importlib.machinery, sys
        sentinel = {os.fspath(sentinel)!r}
        class ForeignLoader(importlib.abc.Loader):
            def create_module(self, spec): return None
            def exec_module(self, module): open(sentinel, 'w').close()
        class OuterLoader(importlib.abc.Loader):
            def create_module(self, spec): return None
            def exec_module(self, module): module.VALUE = 41
        class Finder:
            nested_refused = False
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'core.outer':
                    try:
                        import core.foreign
                    except RuntimeError:
                        self.nested_refused = True
                    return importlib.machinery.ModuleSpec(
                        fullname, OuterLoader(),
                        origin={os.fspath(layout.checkout / 'core/outer.py')!r},
                    )
                if fullname == 'core.foreign':
                    return importlib.machinery.ModuleSpec(
                        fullname, ForeignLoader(), origin={os.fspath(foreign)!r}
                    )
                return None
        guard = sys.modules['_maez_worktree_airlock_guard']
        finder = Finder()
        guard.restore_dispatcher_front()
        sys.meta_path.insert(1, finder)
        import core.outer as outer
        assert finder.nested_refused
        assert outer.VALUE == 41
        """
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_git_derived_alias_is_owned_before_foreign_custom_spec_executes(
    tmp_path: Path,
):
    sentinel = tmp_path / "foreign-alias-loader-ran"
    foreign = tmp_path / "foreign-anchor.py"
    foreign.write_text("VALUE=99\n", encoding="utf-8")
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"plugins/anchor.py": "VALUE=41\n"}
    )
    code = textwrap.dedent(
        f"""
        import importlib.abc, importlib.machinery, sys
        class Loader(importlib.abc.Loader):
            def create_module(self, spec): return None
            def exec_module(self, module): open({os.fspath(sentinel)!r}, 'w').close()
        class Finder:
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'anchor':
                    return importlib.machinery.ModuleSpec(
                        fullname, Loader(), origin={os.fspath(foreign)!r}
                    )
                return None
        guard = sys.modules['_maez_worktree_airlock_guard']
        sys.path.append({os.fspath(layout.checkout / 'plugins')!r})
        guard.restore_dispatcher_front()
        sys.meta_path.insert(1, Finder())
        try:
            import anchor
        except RuntimeError:
            pass
        else:
            raise AssertionError('foreign alias loaded')
        """
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_git_derived_alias_preserves_stdlib_precedence(tmp_path: Path):
    sentinel = tmp_path / "checkout-colorsys-ran"
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={
            "colorsys.py": (
                f"from pathlib import Path;Path({os.fspath(sentinel)!r}).touch()\n"
            )
        },
    )
    airlock._remove_disposable(prepared.root)
    inventory = airlock.GitInventory(
        **{**inventory.__dict__, "maez_roots": (*inventory.maez_roots, "colorsys")}
    )
    prepared = airlock._prepare_disposable(layout, inventory, root_parent=tmp_path)
    code = (
        "import importlib,sys;sys.modules.pop('colorsys',None);"
        "colorsys=importlib.import_module('colorsys');"
        f"assert not colorsys.__file__.startswith({os.fspath(layout.checkout)!r})"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_git_root_alias_preserves_lib_dynload_extension_precedence(tmp_path: Path):
    sentinel = tmp_path / "checkout-hashlib-ran"
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={
            "_hashlib.py": (
                f"from pathlib import Path;Path({os.fspath(sentinel)!r}).touch()\n"
            )
        },
    )
    airlock._remove_disposable(prepared.root)
    inventory = airlock.GitInventory(
        **{**inventory.__dict__, "maez_roots": (*inventory.maez_roots, "_hashlib")}
    )
    prepared = airlock._prepare_disposable(layout, inventory, root_parent=tmp_path)
    code = (
        "import importlib,sys;sys.modules.pop('_hashlib',None);"
        "_hashlib=importlib.import_module('_hashlib');"
        "assert '/lib-dynload/' in _hashlib.__file__;"
        f"assert not _hashlib.__file__.startswith({os.fspath(layout.checkout)!r})"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("foreign_plane", ("file", "origin"))
def test_git_root_stdlib_exemption_requires_all_planes(
    tmp_path: Path, foreign_plane: str
):
    foreign = tmp_path / "foreign.py"
    foreign.write_text("VALUE=99\n", encoding="utf-8")
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"colorsys.py": "VALUE=41\n"}
    )
    airlock._remove_disposable(prepared.root)
    inventory = airlock.GitInventory(
        **{**inventory.__dict__, "maez_roots": (*inventory.maez_roots, "colorsys")}
    )
    prepared = airlock._prepare_disposable(layout, inventory, root_parent=tmp_path)
    source_file = Path(sysconfig.get_path("stdlib")) / "colorsys.py"
    file_value, origin_value = (
        (foreign, source_file)
        if foreign_plane == "file"
        else (source_file, foreign)
    )
    code = (
        "import importlib.machinery,sys,types;name='colorsys';"
        f"m=types.ModuleType(name);m.__file__={os.fspath(file_value)!r};"
        f"m.__spec__=importlib.machinery.ModuleSpec(name,loader=None,origin={os.fspath(origin_value)!r});"
        "sys.modules[name]=m;g=sys.modules['_maez_worktree_airlock_guard'];caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_git_root_alias_preserves_builtin_precedence_with_absent_planes(
    tmp_path: Path,
):
    sentinel = tmp_path / "checkout-time-ran"
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={
            "time.py": (
                f"from pathlib import Path;Path({os.fspath(sentinel)!r}).touch()\n"
            )
        },
    )
    airlock._remove_disposable(prepared.root)
    inventory = airlock.GitInventory(
        **{**inventory.__dict__, "maez_roots": (*inventory.maez_roots, "time")}
    )
    prepared = airlock._prepare_disposable(layout, inventory, root_parent=tmp_path)
    code = (
        "import importlib,sys;sys.modules.pop('time',None);"
        "time=importlib.import_module('time');"
        "assert time.__spec__.origin=='built-in';"
        "g=sys.modules['_maez_worktree_airlock_guard'];g.audit_loaded_modules()"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert not sentinel.exists()
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    ("internal_name", "tracked_relative"),
    (
        ("_maez_worktree_airlock_guard", "plugins/_maez_worktree_airlock_guard.py"),
        ("__main__", "plugins/__main__.py"),
    ),
)
def test_internal_airlock_modules_are_never_claimed_by_tracked_aliases(
    tmp_path: Path, internal_name: str, tracked_relative: str
):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={tracked_relative: "VALUE=99\n"}
    )
    bind_main = (
        f"sys.modules['__main__'].__file__={os.fspath(prepared.runner)!r};"
        if internal_name == "__main__"
        else ""
    )
    code = (
        "import sys;"
        f"{bind_main}"
        f"sys.path.append({os.fspath(layout.checkout / 'plugins')!r});"
        f"assert {internal_name!r} in sys.modules;"
        "g=sys.modules['_maez_worktree_airlock_guard'];g.audit_loaded_modules()"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_internal_runner_exemption_rejects_replacement_lookalike(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"plugins/__main__.py": "VALUE=99\n"}
    )
    code = (
        "import sys,types;g=sys.modules['_maez_worktree_airlock_guard'];"
        f"sys.path.append({os.fspath(layout.checkout / 'plugins')!r});"
        "replacement=types.ModuleType('__main__');"
        f"replacement.__file__={os.fspath(prepared.runner)!r};"
        "replacement.__spec__=None;sys.modules['__main__']=replacement;caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_internal_guard_exemption_requires_no_module_spec(tmp_path: Path):
    foreign = tmp_path / "foreign-guard.py"
    foreign.write_text("VALUE=99\n", encoding="utf-8")
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={"plugins/_maez_worktree_airlock_guard.py": "VALUE=99\n"},
    )
    code = (
        "import importlib.machinery,sys;"
        "g=sys.modules['_maez_worktree_airlock_guard'];"
        f"sys.path.append({os.fspath(layout.checkout / 'plugins')!r});"
        "g.__spec__=importlib.machinery.ModuleSpec("
        f"g.__name__,loader=None,origin={os.fspath(foreign)!r});caught=False;"
        "\ntry:\n g.audit_loaded_modules()\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_import_provenance_violation",
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inactive_tracked_basename_does_not_claim_originless_module(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"tools/__main__.py": "VALUE=41\n"}
    )
    try:
        result = _run_guarded(prepared, "assert __name__ == '__main__'", cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_dispatcher_delegates_in_order_and_returns_exact_spec_and_loader(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files={"core/candidate.py": "\n"}
    )
    code = textwrap.dedent(
        f"""
        import importlib.abc, importlib.machinery, sys
        events = []
        class Loader(importlib.abc.Loader):
            def create_module(self, spec): return None
            def exec_module(self, module): module.loaded = True
        loader = Loader()
        expected = importlib.machinery.ModuleSpec(
            'core.candidate', loader,
            origin={os.fspath(layout.checkout / 'core/candidate.py')!r},
        )
        class First:
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'core.candidate': events.append('first')
                return None
        class Second:
            def find_spec(self, fullname, path=None, target=None):
                if fullname == 'core.candidate':
                    events.append('second')
                    return expected
                return None
        guard = sys.modules['_maez_worktree_airlock_guard']
        guard.restore_dispatcher_front()
        sys.meta_path[1:1] = [First(), Second()]
        import core.candidate as candidate
        assert events == ['first', 'second']
        assert candidate.__spec__ is expected
        assert candidate.__loader__ is loader
        assert candidate.loaded is True
        """
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_dispatcher_front_restoration_is_idempotent_and_preserves_followers(
    tmp_path: Path,
):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = (
        "import sys;g=sys.modules['_maez_worktree_airlock_guard'];"
        "d=g.DISPATCHER;f=object();sys.meta_path.insert(0,f);"
        "g.restore_dispatcher_front();first=list(sys.meta_path);"
        "g.restore_dispatcher_front();"
        "assert sys.meta_path[0] is d;assert sys.meta_path.count(d)==1;"
        "assert list(sys.meta_path)==first;assert f in sys.meta_path[1:]"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_dispatcher_preserves_real_pytest_assertion_rewriting_and_diagnostics(
    tmp_path: Path,
):
    extra = {
        "tests/test_rewritten_target.py": "def fail():\n    assert 1 == 2\n",
        "tests/test_rewrite_probe.py": textwrap.dedent(
            """
            import importlib
            import sys
            import pytest

            def test_rewrite_survives():
                guard = sys.modules['_maez_worktree_airlock_guard']
                guard.restore_dispatcher_front()
                target = importlib.import_module('tests.test_rewritten_target')
                assert type(target.__loader__).__name__ == 'AssertionRewritingHook'
                with pytest.raises(AssertionError) as observed:
                    target.fail()
                assert 'assert 1 == 2' in str(observed.value)
            """
        ),
        "tests/__init__.py": "\n",
    }
    dependency_purelib = Path(
        subprocess.run(
            [
                os.fspath(SHARED_PYTHON),
                "-I",
                "-S",
                "-B",
                "-c",
                "import sysconfig;print(sysconfig.get_path('purelib'))",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path, extra_files=extra, dependency_purelib=dependency_purelib
    )
    code = (
        "import pytest;"
        f"raise SystemExit(pytest.main(['-q','-p','no:cacheprovider',{os.fspath(layout.checkout / 'tests/test_rewrite_probe.py')!r}]))"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 passed" in result.stdout
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_sticky_marker_forces_outer_refusal_after_exception_is_caught(
    tmp_path: Path,
):
    airlock, layout, inventory, prepared = _task3_prepared(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    code = (
        "import sys;caught=False;"
        "\ntry:\n"
        f" sys.path.append({os.fspath(foreign)!r})\n"
        "except RuntimeError:\n caught=True\n"
        "assert caught"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 0, result.stderr
        assert airlock._read_marker_state(prepared.violation_dir)

        snapshots = iter(((), ()))
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: next(snapshots))
            monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)
            monkeypatch.setattr(
                airlock,
                "_run_owned_command",
                lambda *_a, **_k: airlock.OwnedRun(status=0, group_empty=True),
            )
            monkeypatch.setattr(airlock, "_remove_disposable", shutil.rmtree)
            terminal = airlock._execute_outer(
                layout, inventory, root_parent=tmp_path
            )
            assert terminal.refusal == "airlock_path_provenance_violation"
            assert terminal.status == 86
            assert terminal.certificate is None
    finally:
        if prepared.root.exists():
            airlock._remove_disposable(prepared.root)


def test_sticky_marker_write_failure_exits_86_directly(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = (
        "import sys,tempfile;"
        "g=sys.modules['_maez_worktree_airlock_guard'];"
        "g._VIOLATION_DIR='/missing/airlock-marker-root';"
        "sys.path.append('/foreign')"
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)
        assert result.returncode == 86
        assert result.stdout == ""
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_marker_short_write_exits_86_and_reader_fails_closed(
    tmp_path: Path,
):
    token = "airlock_path_provenance_violation"
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = textwrap.dedent(
        f"""
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']
        real_write = guard._os.write

        def short_write(descriptor, payload):
            if payload == {f'{token}\n'.encode('ascii')!r}:
                return real_write(descriptor, payload[:-1])
            return real_write(descriptor, payload)

        guard._os.write = short_write
        guard._record_marker({token!r})
        """
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)

        assert result.returncode == 86
        markers = tuple(prepared.violation_dir.iterdir())
        assert len(markers) == 1
        assert markers[0].name == "00000001"
        assert markers[0].read_bytes() == token.encode("ascii")
        with pytest.raises(
            airlock.AirlockRefusal, match="airlock_child_setup_failed"
        ):
            airlock._read_marker_state(prepared.violation_dir)
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_child_marker_close_failure_exits_86_with_sticky_marker(
    tmp_path: Path,
):
    token = "airlock_path_provenance_violation"
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    code = textwrap.dedent(
        f"""
        import sys

        guard = sys.modules['_maez_worktree_airlock_guard']

        def close_failure(_descriptor):
            raise OSError('forced marker close failure')

        guard._os.close = close_failure
        guard._record_marker({token!r})
        """
    )
    try:
        result = _run_guarded(prepared, code, cwd=layout.checkout)

        assert result.returncode == 86
        assert airlock._read_marker_state(prepared.violation_dir) == (token,)
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_grandchild_marker_concurrency_preserves_same_token_writers(
    tmp_path: Path,
):
    token = "airlock_path_provenance_violation"
    airlock, _layout, _inventory, prepared = _task3_prepared(tmp_path)
    try:
        completed = _run_concurrent_marker_writers(
            prepared, (token, token), tmp_path
        )

        assert [result.returncode for result in completed] == [0, 0], [
            result.stderr for result in completed
        ]
        assert sorted(path.name for path in prepared.violation_dir.iterdir()) == [
            "00000001",
            "00000002",
        ]
        assert airlock._read_marker_state(prepared.violation_dir) == (token, token)
        for marker in prepared.violation_dir.iterdir():
            info = marker.stat()
            assert stat.S_IMODE(info.st_mode) == 0o600
            assert info.st_nlink == 1
            assert marker.read_text(encoding="ascii") == f"{token}\n"
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_grandchild_marker_concurrency_preserves_priority_not_timing(
    tmp_path: Path,
):
    path_token = "airlock_path_provenance_violation"
    import_token = "airlock_import_provenance_violation"
    airlock, _layout, _inventory, prepared = _task3_prepared(tmp_path)
    try:
        completed = _run_concurrent_marker_writers(
            prepared, (import_token, path_token), tmp_path
        )

        assert [result.returncode for result in completed] == [0, 0], [
            result.stderr for result in completed
        ]
        marker_tokens = airlock._read_marker_state(prepared.violation_dir)
        assert set(marker_tokens) == {path_token, import_token}
        assert (
            airlock._select_refusal(
                marker_tokens,
                shared_environment_changed=False,
                cleanup_complete=True,
            )
            == path_token
        )
    finally:
        airlock._remove_disposable(prepared.root)


def test_inherited_grandchild_marker_ordinal_overflow_exits_86(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(tmp_path)
    existing = prepared.violation_dir / "00000001"
    existing.write_text("airlock_path_provenance_violation\n", encoding="ascii")
    existing.chmod(0o600)
    code = (
        "import sys;"
        "g=sys.modules['_maez_worktree_airlock_guard'];"
        "g._MAX_MARKER_ORDINAL=1;"
        "g._record_marker('airlock_import_provenance_violation');"
        "print('UNREACHABLE')"
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-I", "-B", "-c", code],
            cwd=layout.checkout,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 86
        assert "UNREACHABLE" not in result.stdout
        assert sorted(path.name for path in prepared.violation_dir.iterdir()) == [
            "00000001"
        ]
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    "token",
    ("airlock_path_provenance_violation", "airlock_import_provenance_violation"),
)
def test_marker_reader_preserves_validated_refusal_token(tmp_path: Path, token: str):
    airlock = _airlock()
    violation_dir = tmp_path / "violations"
    violation_dir.mkdir(mode=0o700)
    marker = violation_dir / "00000001"
    marker.write_text(f"{token}\n", encoding="ascii")
    marker.chmod(0o600)

    assert airlock._read_marker_state(violation_dir) == (token,)


@pytest.mark.parametrize(
    ("name", "payload"),
    (
        ("00000001", "airlock_path_provenance_violation"),
        ("not-a-marker", "airlock_path_provenance_violation\n"),
        ("00000001", "unknown\n"),
        ("00000001", "airlock_dependency_unavailable\n"),
        ("00000002", "airlock_path_provenance_violation\n"),
    ),
)
def test_marker_reader_fails_closed_on_malformed_marker(
    tmp_path: Path, name: str, payload: str
):
    airlock = _airlock()
    violation_dir = tmp_path / "violations"
    violation_dir.mkdir(mode=0o700)
    marker = violation_dir / name
    marker.write_text(payload, encoding="ascii")
    marker.chmod(0o600)

    with pytest.raises(airlock.AirlockRefusal, match="airlock_child_setup_failed"):
        airlock._read_marker_state(violation_dir)


@pytest.mark.parametrize("damage", ("symlink", "hardlink", "mode"))
def test_marker_reader_preserves_no_follow_single_link_private_file_contract(
    tmp_path: Path,
    damage: str,
):
    airlock = _airlock()
    violation_dir = tmp_path / "violations"
    violation_dir.mkdir(mode=0o700)
    target = tmp_path / "target"
    target.write_text("airlock_path_provenance_violation\n", encoding="ascii")
    target.chmod(0o600)
    marker = violation_dir / "00000001"
    if damage == "symlink":
        marker.symlink_to(target)
    elif damage == "hardlink":
        os.link(target, marker)
    else:
        marker.write_text(
            "airlock_path_provenance_violation\n", encoding="ascii"
        )
        marker.chmod(0o644)

    with pytest.raises(airlock.AirlockRefusal, match="airlock_child_setup_failed"):
        airlock._read_marker_state(violation_dir)


@pytest.mark.parametrize(
    "token",
    ("airlock_path_provenance_violation", "airlock_import_provenance_violation"),
)
def test_marker_refusal_precedes_generic_status_86_dependency_token(
    tmp_path: Path, token: str, monkeypatch: pytest.MonkeyPatch
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    root = tmp_path / "prepared"
    violation_dir = root / "violations"
    violation_dir.mkdir(parents=True, mode=0o700)
    marker = violation_dir / "00000001"
    marker.write_text(f"{token}\n", encoding="ascii")
    marker.chmod(0o600)
    prepared = types.SimpleNamespace(
        root=root,
        python=root / "venv/bin/python",
        runner=root / "inner_runner.py",
        pytest_config=root / "pytest.ini",
        environment={},
        violation_dir=violation_dir,
        diagnostic=root / "diagnostic",
    )
    prepared.python.parent.mkdir(parents=True)
    prepared.python.write_bytes(b"interpreter")
    prepared.pytest_config.write_text("", encoding="utf-8")
    prepared.diagnostic.write_bytes(b"")
    prepared.diagnostic.chmod(0o600)
    snapshots = iter(((), ()))
    monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: next(snapshots))
    monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_a, **_k: airlock.OwnedRun(status=86, group_empty=True),
    )
    monkeypatch.setattr(airlock, "_remove_disposable", shutil.rmtree)

    terminal = airlock._execute_outer(layout, inventory, root_parent=tmp_path)
    assert terminal.refusal == token
    assert terminal.status == 86
    assert terminal.certificate is None


def test_malformed_outer_marker_precedes_generic_status_86_dependency_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    root = tmp_path / "prepared"
    violation_dir = root / "violations"
    violation_dir.mkdir(parents=True, mode=0o700)
    marker = violation_dir / "00000001"
    marker.write_text("unknown\n", encoding="ascii")
    marker.chmod(0o600)
    prepared = types.SimpleNamespace(
        root=root,
        python=root / "venv/bin/python",
        runner=root / "inner_runner.py",
        pytest_config=root / "pytest.ini",
        environment={},
        violation_dir=violation_dir,
        diagnostic=root / "diagnostic",
    )
    prepared.python.parent.mkdir(parents=True)
    prepared.python.write_bytes(b"interpreter")
    prepared.pytest_config.write_text("", encoding="utf-8")
    prepared.diagnostic.write_bytes(b"")
    prepared.diagnostic.chmod(0o600)
    snapshots = iter(((), ()))
    monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: next(snapshots))
    monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_a, **_k: airlock.OwnedRun(status=86, group_empty=True),
    )
    monkeypatch.setattr(airlock, "_remove_disposable", shutil.rmtree)

    terminal = airlock._execute_outer(layout, inventory, root_parent=tmp_path)
    assert terminal.refusal == "airlock_child_setup_failed"
    assert terminal.status == 86
    assert terminal.certificate is None


@pytest.mark.parametrize("state", ["wrong-origin", "partial"])
def test_controlled_pth_refuses_preexisting_wrong_or_partial_guard(
    tmp_path: Path, state: str
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    prepared = airlock._prepare_disposable(
        layout, _inventory_for(layout.checkout), root_parent=tmp_path
    )
    seed = (
        "import site,sys,types;"
        "m=types.ModuleType('_maez_worktree_airlock_guard');"
        + (
            "m.__file__='/wrong/origin';m.AIRLOCK_READY=True;"
            if state == "wrong-origin"
            else f"m.__file__={os.fspath(prepared.guard)!r};m.AIRLOCK_READY=False;"
        )
        + "sys.modules[m.__name__]=m;"
        + f"site.addsitedir({os.fspath(prepared.purelib)!r})"
    )
    try:
        result = subprocess.run(
            [os.fspath(prepared.python), "-I", "-S", "-B", "-c", seed],
            cwd=tmp_path,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 86
        assert result.stdout == ""
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("damage", ["missing", "invalid", "unreadable"])
def test_guard_startup_damage_exits_86_before_user_code(tmp_path: Path, damage: str):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    prepared = airlock._prepare_disposable(
        layout, _inventory_for(layout.checkout), root_parent=tmp_path
    )
    if damage == "missing":
        prepared.guard.unlink()
    elif damage == "invalid":
        prepared.guard.write_text("this is not python !\n", encoding="utf-8")
    else:
        prepared.guard.chmod(0)
    try:
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                "-I",
                "-B",
                "-c",
                "print('USER_CODE_RAN')",
            ],
            cwd=tmp_path,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 86
        assert "USER_CODE_RAN" not in result.stdout
    finally:
        prepared.guard.chmod(0o600) if prepared.guard.exists() else None
        airlock._remove_disposable(prepared.root)


def test_hostile_startup_decoys_do_not_intercept_exact_guard(tmp_path: Path):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    prepared = airlock._prepare_disposable(
        layout, _inventory_for(layout.checkout), root_parent=tmp_path
    )
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    sentinel = tmp_path / "decoy-ran"
    (hostile / "sitecustomize.py").write_text(
        f"from pathlib import Path;Path({os.fspath(sentinel)!r}).touch()\n",
        encoding="utf-8",
    )
    (hostile / "os.py").write_text("raise RuntimeError('decoy')\n", encoding="utf-8")
    try:
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                "-I",
                "-B",
                "-c",
                "import sys;print(sys.modules['_maez_worktree_airlock_guard'].AIRLOCK_READY)",
            ],
            cwd=hostile,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "True"
        assert not sentinel.exists()
    finally:
        airlock._remove_disposable(prepared.root)


def test_dependency_pth_is_plain_data_not_executed_but_package_imports(
    tmp_path: Path,
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    sentinel = tmp_path / "nested-pth-ran"
    (layout.shared_purelib / "dependency_probe.py").write_text(
        "VALUE = 23\n", encoding="utf-8"
    )
    (layout.shared_purelib / "nested.pth").write_text(
        f"import pathlib;pathlib.Path({os.fspath(sentinel)!r}).touch()\n",
        encoding="utf-8",
    )
    prepared = airlock._prepare_disposable(
        layout, _inventory_for(layout.checkout), root_parent=tmp_path
    )
    try:
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                "-I",
                "-B",
                "-c",
                "import dependency_probe;print(dependency_probe.VALUE)",
            ],
            cwd=tmp_path,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "23"
        assert not sentinel.exists()
    finally:
        airlock._remove_disposable(prepared.root)


def test_shared_pth_snapshot_binds_type_mode_size_and_content(tmp_path: Path):
    airlock = _airlock()
    purelib = tmp_path / "purelib"
    purelib.mkdir()
    regular = purelib / "alpha.pth"
    regular.write_text("/alpha\n", encoding="utf-8")
    regular.chmod(0o640)
    (purelib / "link.pth").symlink_to(regular)

    before = airlock._snapshot_pth(purelib)
    assert [(item.name, item.is_regular) for item in before] == [
        ("alpha.pth", True),
        ("link.pth", False),
    ]
    assert before[0].mode == 0o640
    assert before[0].size == len("/alpha\n")
    assert before[0].sha256 is not None
    assert before[1].sha256 is None

    regular.write_text("/changed\n", encoding="utf-8")
    after = airlock._snapshot_pth(purelib)
    assert after != before


def test_shared_pth_real_outer_is_identical_and_disposable_root_is_removed():
    airlock = _airlock()
    shared_purelib = Path(
        subprocess.run(
            [
                os.fspath(SHARED_PYTHON),
                "-I",
                "-S",
                "-B",
                "-c",
                "import sysconfig;print(sysconfig.get_path('purelib'))",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    before = airlock._snapshot_pth(shared_purelib)
    process = subprocess.Popen(
        [
            os.fspath(SHARED_PYTHON),
            "-I",
            "-S",
            "-B",
            os.fspath(AIRLOCK_SOURCE),
            "pytest",
            "--",
            "tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes",
            "-q",
        ],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    observed_roots: set[Path] = set()
    try:
        deadline = time.monotonic() + 10
        while process.poll() is None and time.monotonic() < deadline:
            observed_roots.update(_owned_airlock_roots(process.pid))
            time.sleep(0.002)
        stdout, stderr = process.communicate(timeout=2)
        observed_roots.update(_owned_airlock_roots(process.pid))
        after = airlock._snapshot_pth(shared_purelib)

        assert process.returncode == 0
        assert stdout.startswith("MAEZ_AIRLOCK_CERTIFIED ")
        assert stdout.count("\n") == 1
        assert "1 passed" in stderr
        assert observed_roots
        assert all(not root.exists() for root in observed_roots)
        assert not _owned_airlock_roots(process.pid)
        assert before == after
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        _cleanup_owned_outer_test_run(airlock, process.pid)


@pytest.mark.parametrize(
    ("exit_code", "forward_signal"),
    [(0, None), (1, None), (0, signal.SIGINT), (0, signal.SIGTERM)],
    ids=("pass", "red", "sigint", "sigterm"),
)
def test_cleanup_removes_root_and_owned_group_for_every_terminal_path(
    tmp_path: Path, exit_code: int, forward_signal: int | None
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    before = airlock._snapshot_pth(layout.shared_purelib)
    prepared = airlock._prepare_disposable(
        layout, _inventory_for(layout.checkout), root_parent=tmp_path
    )
    code = (
        "import signal,time;"
        "signal.signal(signal.SIGINT,lambda *_:raise_exit(130));"
        "signal.signal(signal.SIGTERM,lambda *_:raise_exit(143));"
        f"raise SystemExit({exit_code})"
    )
    if forward_signal is not None:
        code = "import time;time.sleep(30)"
    result = airlock._run_owned_command(
        [os.fspath(prepared.python), "-I", "-S", "-B", "-c", code],
        cwd=tmp_path,
        environment=prepared.environment,
        forward_signal=forward_signal,
    )
    marker_state = airlock._read_marker_state(prepared.violation_dir)
    airlock._remove_disposable(prepared.root)
    after = airlock._snapshot_pth(layout.shared_purelib)

    assert result.group_empty is True
    assert marker_state == ()
    assert not prepared.root.exists()
    assert before == after


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("123 (ordinary) S 1 456 456 0 0 0", 456),
        ("123 (name with spaces) S 1 457 457 0 0 0", 457),
        ("123 (odd ) name) S 1 458 458 0 0 0", 458),
    ],
)
def test_proc_stat_parser_reads_pgrp_after_final_comm_delimiter(
    payload: str, expected: int
):
    airlock = _airlock()

    assert airlock._parse_proc_stat_pgrp(payload) == expected


def test_group_member_proof_refuses_unreadable_stat_but_skips_raced_exit(
    tmp_path: Path,
):
    airlock = _airlock()
    process = tmp_path / "123"
    process.mkdir()

    def unreadable(_path: Path) -> str:
        raise PermissionError("proof unavailable")

    with pytest.raises(
        airlock.AirlockRefusal, match="airlock_cleanup_incomplete"
    ):
        airlock._group_members(123, proc_root=tmp_path, stat_reader=unreadable)

    def raced_exit(_path: Path) -> str:
        raise FileNotFoundError("process exited")

    assert airlock._group_members(
        123, proc_root=tmp_path, stat_reader=raced_exit
    ) == ()


def test_owned_group_signal_permission_error_is_failed_cleanup_proof():
    airlock = _airlock()

    assert (
        airlock._clear_owned_group(
            123,
            group_reader=lambda _group: (456,),
            signaler=lambda _group, _signal: (_ for _ in ()).throw(
                PermissionError("signal refused")
            ),
            sleeper=lambda _seconds: None,
        )
        is False
    )


def test_group_member_proof_counts_zombie_as_residue(tmp_path: Path):
    airlock = _airlock()
    process = tmp_path / "456"
    process.mkdir()
    (process / "stat").write_text(
        "456 (owned zombie) Z 1 123 123 0 0 0", encoding="utf-8"
    )

    assert airlock._group_members(123, proc_root=tmp_path) == (456,)


def test_owned_group_requires_two_empty_scans_and_catches_fork_replacement():
    airlock = _airlock()
    observations = iter(((), (101,), (101,), (), ()))
    signals: list[int] = []
    sleeps: list[float] = []

    result = airlock._clear_owned_group(
        100,
        group_reader=lambda _group: next(observations),
        signaler=lambda _group, signum: signals.append(signum),
        sleeper=sleeps.append,
    )

    assert result is True
    assert signals == [signal.SIGTERM, signal.SIGKILL]
    assert sleeps.count(0.05) >= 2


def test_normal_exit_never_signals_numeric_group_after_leader_is_reaped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    airlock = _airlock()
    cleanup_signals: list[int] = []
    observed_groups: list[int] = []

    class ReapedProcess:
        pid = 4242
        returncode = 0

        def poll(self):
            return 0

        def wait(self, timeout):
            del timeout
            return 0

        def communicate(self, timeout):
            del timeout
            return b"", b""

    process = ReapedProcess()
    scope = types.SimpleNamespace(
        interrupted=False,
        attach=lambda _process: None,
        detach=lambda _process: None,
    )
    monkeypatch.setattr(airlock.subprocess, "Popen", lambda *_a, **_k: process)
    monkeypatch.setattr(
        airlock,
        "_clear_owned_group",
        lambda group: cleanup_signals.append(group) or True,
    )
    monkeypatch.setattr(
        airlock,
        "_reaped_group_is_quiescent",
        lambda group: observed_groups.append(group) or False,
        raising=False,
    )

    result = airlock._run_owned_command(
        ("/tracked/child",),
        cwd=tmp_path,
        environment={},
        signal_scope=scope,
    )

    assert result.group_empty is False
    assert observed_groups == [process.pid]
    assert cleanup_signals == []


def test_interrupted_cleanup_stops_signalling_after_wait_reaps_leader(
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    signals: list[tuple[int, int]] = []
    observations = iter(((777,), (888,)))

    class ReapedAfterTerm:
        pid = 4242

        def wait(self, timeout):
            del timeout
            return 143

    monkeypatch.setattr(
        airlock, "_group_members", lambda _group: next(observations)
    )
    monkeypatch.setattr(
        airlock.os,
        "killpg",
        lambda group, signum: signals.append((group, signum)),
    )

    assert airlock._clear_interrupted_owned_group(ReapedAfterTerm()) is False
    assert signals == [(4242, signal.SIGTERM)]


def test_signal_handler_during_cleanup_forwards_without_reaping_leader(
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    polls: list[str] = []
    signals: list[tuple[int, int]] = []

    class ExitedButUnreaped:
        pid = 4242
        returncode = None

        def poll(self):
            polls.append("poll")
            self.returncode = 143
            return self.returncode

    process = ExitedButUnreaped()
    scope = airlock._OuterSignalScope()
    scope._process = process
    monkeypatch.setattr(
        airlock.os,
        "killpg",
        lambda group, signum: signals.append((group, signum)),
    )

    scope._handle(signal.SIGTERM, None)

    assert polls == []
    assert process.returncode is None
    assert signals == [(process.pid, signal.SIGTERM)]

    process.returncode = 143
    scope._handle(signal.SIGTERM, None)
    assert polls == []
    assert signals == [(process.pid, signal.SIGTERM)]


def test_signal_attach_replays_pending_signal_without_reaping_leader(
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    polls: list[str] = []
    signals: list[tuple[int, int]] = []

    class ExitedButUnreaped:
        pid = 4242
        returncode = None

        def poll(self):
            polls.append("poll")
            self.returncode = 130
            return self.returncode

    process = ExitedButUnreaped()
    scope = airlock._OuterSignalScope()
    scope.received.append(signal.SIGINT)
    monkeypatch.setattr(
        airlock.os,
        "killpg",
        lambda group, signum: signals.append((group, signum)),
    )

    scope.attach(process)

    assert polls == []
    assert process.returncode is None
    assert signals == [(process.pid, signal.SIGINT)]


def test_normal_exit_observes_same_group_residue_without_signalling(
    tmp_path: Path,
):
    airlock = _airlock()
    libc = ctypes.CDLL(None, use_errno=True)
    prior_subreaper = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(prior_subreaper), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    child_pid_file = tmp_path / "stubborn-child.pid"
    code = textwrap.dedent(
        f"""
        import ctypes, os, pathlib, signal, time
        child = os.fork()
        if child == 0:
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.prctl(15, b'odd ) name', 0, 0, 0) != 0:
                os._exit(91)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            pathlib.Path({os.fspath(child_pid_file)!r}).write_text(
                str(os.getpid()), encoding='utf-8'
            )
            while True:
                time.sleep(1)
        deadline = time.monotonic() + 3
        while not pathlib.Path({os.fspath(child_pid_file)!r}).exists():
            if time.monotonic() >= deadline:
                os._exit(92)
            time.sleep(0.01)
        os._exit(0)
        """
    )
    child_pid: int | None = None
    try:
        result = airlock._run_owned_command(
            [os.fspath(SHARED_PYTHON), "-I", "-S", "-B", "-c", code],
            cwd=tmp_path,
            environment={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"},
        )
        assert child_pid_file.exists()
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        assert result.group_empty is False
        assert Path(f"/proc/{child_pid}").exists()
    finally:
        try:
            if child_pid is None and child_pid_file.exists():
                child_pid = int(child_pid_file.read_text(encoding="utf-8"))
            if child_pid is not None and Path(f"/proc/{child_pid}").exists():
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        waited, _status = os.waitpid(child_pid, os.WNOHANG)
                    except ChildProcessError:
                        break
                    if waited == child_pid:
                        break
                    time.sleep(0.02)
                assert not Path(f"/proc/{child_pid}").exists()
        finally:
            assert libc.prctl(36, prior_subreaper.value, 0, 0, 0) == 0


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
def test_cleanup_outer_signal_is_forwarded_and_owned_group_is_reaped(
    tmp_path: Path, signal_to_send: int
):
    ready = tmp_path / "child-ready"
    done = tmp_path / "child-done"
    child_code = textwrap.dedent(
        f"""
        import pathlib, signal, sys, time
        pathlib.Path({os.fspath(ready)!r}).touch()
        signal.signal(signal.SIGINT, lambda *_: sys.exit(130))
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
        try:
            time.sleep(2)
        finally:
            pathlib.Path({os.fspath(done)!r}).touch()
        """
    )
    wrapper_code = textwrap.dedent(
        f"""
        import importlib.util, json, pathlib, sys
        source = pathlib.Path({os.fspath(AIRLOCK_SOURCE)!r})
        spec = importlib.util.spec_from_file_location('_outer_signal_probe', source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        result = module._run_owned_command(
            [sys.executable, '-I', '-S', '-B', '-c', {child_code!r}],
            cwd=pathlib.Path({os.fspath(tmp_path)!r}),
            environment={{'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent'}},
        )
        print(json.dumps({{'status': result.status, 'empty': result.group_empty}}))
        """
    )
    wrapper = subprocess.Popen(
        [os.fspath(SHARED_PYTHON), "-I", "-S", "-B", "-c", wrapper_code],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 3
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        sent_at = time.monotonic()
        os.kill(wrapper.pid, signal_to_send)
        stdout, stderr = wrapper.communicate(timeout=4)
        assert wrapper.returncode == 0, stderr
        assert json.loads(stdout) == {"status": 128 + signal_to_send, "empty": True}
        assert done.exists()
        assert time.monotonic() - sent_at < 1.5
    finally:
        if wrapper.poll() is None:
            wrapper.kill()
            wrapper.wait(timeout=2)
        deadline = time.monotonic() + 3
        while not done.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert done.exists()


@pytest.mark.parametrize("signal_to_send", [signal.SIGINT, signal.SIGTERM])
def test_cleanup_signal_during_setup_cannot_bypass_outer_finalizers(
    tmp_path: Path, signal_to_send: int
):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    dependency_purelib = tmp_path / "dependency-purelib"
    dependency_purelib.mkdir()
    ready = tmp_path / "setup-ready"
    release = tmp_path / "setup-release"
    snapshots = tmp_path / "snapshots"
    child_called = tmp_path / "child-called"
    outcome = tmp_path / "outcome"
    wrapper_code = textwrap.dedent(
        f"""
        import importlib.util, pathlib, sys, time
        source = pathlib.Path({os.fspath(AIRLOCK_SOURCE)!r})
        spec = importlib.util.spec_from_file_location('_outer_setup_signal_probe', source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        layout = module.AirlockLayout(
            shared_python=pathlib.Path(sys.executable),
            shared_purelib=pathlib.Path({os.fspath(dependency_purelib)!r}),
            checkout=pathlib.Path({os.fspath(checkout)!r}),
        )
        inventory = module.GitInventory(
            head='a' * 40,
            tracked_files=(),
            tracked_python_files=(),
            maez_roots=(),
            registered_worktrees=(layout.checkout,),
        )
        real_prepare = module._prepare_disposable
        real_snapshot = module._snapshot_pth
        def observed_snapshot(path):
            with pathlib.Path({os.fspath(snapshots)!r}).open('a', encoding='utf-8') as stream:
                stream.write('snapshot\\n')
            return real_snapshot(path)
        def blocked_prepare(*args, **kwargs):
            prepared = real_prepare(*args, **kwargs)
            pathlib.Path({os.fspath(ready)!r}).touch()
            deadline = time.monotonic() + 5
            while not pathlib.Path({os.fspath(release)!r}).exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError('bounded setup release expired')
                time.sleep(0.01)
            return prepared
        def forbidden_child(*args, **kwargs):
            pathlib.Path({os.fspath(child_called)!r}).touch()
            return module.OwnedRun(status=86, group_empty=True)
        module._snapshot_pth = observed_snapshot
        module._prepare_disposable = blocked_prepare
        module._run_owned_command = forbidden_child
        terminal = module._execute_outer(
            layout, inventory, root_parent=pathlib.Path({os.fspath(tmp_path)!r})
        )
        pathlib.Path({os.fspath(outcome)!r}).write_text(
            terminal.refusal or '', encoding='utf-8'
        )
        """
    )
    wrapper = subprocess.Popen(
        [os.fspath(SHARED_PYTHON), "-I", "-S", "-B", "-c", wrapper_code],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 4
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        live_roots = tuple(tmp_path.glob("maez-airlock-*"))
        assert len(live_roots) == 1
        os.kill(wrapper.pid, signal_to_send)
        release.touch()
        stdout, stderr = wrapper.communicate(timeout=6)

        assert wrapper.returncode == 0, stderr
        assert stdout == ""
        assert "MAEZ_AIRLOCK_CERTIFIED" not in stdout + stderr
        assert outcome.read_text(encoding="utf-8") == "airlock_child_setup_failed"
        assert snapshots.read_text(encoding="utf-8").splitlines() == [
            "snapshot",
            "snapshot",
        ]
        assert not child_called.exists()
        assert all(not root.exists() for root in live_roots)
    finally:
        release.touch(exist_ok=True)
        if wrapper.poll() is None:
            wrapper.kill()
            wrapper.wait(timeout=2)
        for root in tmp_path.glob("maez-airlock-*"):
            shutil.rmtree(root, ignore_errors=True)


def test_cleanup_failure_is_typed_and_simultaneous_refusals_are_deterministic():
    airlock = _airlock()

    assert airlock._select_refusal(
        ("airlock_child_setup_failed",),
        shared_environment_changed=True,
        cleanup_complete=False,
    ) == "airlock_shared_environment_changed"
    assert airlock._select_refusal(
        ("airlock_child_setup_failed",),
        shared_environment_changed=False,
        cleanup_complete=False,
    ) == "airlock_cleanup_incomplete"
    assert airlock._select_refusal(
        ("airlock_import_provenance_violation", "airlock_child_setup_failed"),
        shared_environment_changed=False,
        cleanup_complete=True,
    ) == "airlock_import_provenance_violation"


FROZEN_REFUSALS = (
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


def test_refusal_vocabulary_is_the_exact_frozen_order():
    airlock = _airlock()

    assert airlock._REFUSAL_VOCABULARY == FROZEN_REFUSALS
    assert "airlock_provenance_violation" not in AIRLOCK_SOURCE.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("earlier", "later"),
    tuple(itertools.combinations(FROZEN_REFUSALS[:-2], 2)),
)
def test_refusal_vocabulary_order_is_stable_for_every_simultaneous_pair(
    earlier: str, later: str
):
    airlock = _airlock()

    assert (
        airlock._select_refusal(
            (later, earlier),
            shared_environment_changed=False,
            cleanup_complete=True,
        )
        == earlier
    )


def test_refusal_selection_unknown_token_cannot_displace_a_frozen_token():
    airlock = _airlock()

    assert (
        airlock._select_refusal(
            ("unknown_refusal", "airlock_collection_escape"),
            shared_environment_changed=False,
            cleanup_complete=True,
        )
        == "airlock_collection_escape"
    )
    assert (
        airlock._select_refusal(
            ("unknown_refusal",),
            shared_environment_changed=False,
            cleanup_complete=True,
        )
        is None
    )


def test_disposable_setup_cleanup_failure_dominates_original_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    original_rmtree = airlock.shutil.rmtree

    def setup_refuses(*_args, **_kwargs):
        raise airlock.AirlockRefusal("airlock_child_setup_failed")

    def cleanup_refuses(*_args, **_kwargs):
        raise OSError("cleanup failed")

    monkeypatch.setattr(airlock, "_private_write", setup_refuses)
    monkeypatch.setattr(airlock.shutil, "rmtree", cleanup_refuses)
    try:
        with pytest.raises(
            airlock.AirlockRefusal, match="airlock_cleanup_incomplete"
        ):
            airlock._prepare_disposable(
                layout, _inventory_for(layout.checkout), root_parent=tmp_path
            )
    finally:
        monkeypatch.setattr(airlock.shutil, "rmtree", original_rmtree)
        for root in tmp_path.glob("maez-airlock-*"):
            original_rmtree(root)


def test_outer_refuses_when_owned_root_is_renamed_and_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    real_prepare = airlock._prepare_disposable
    captured: list[object] = []
    renamed: Path | None = None

    def prepare(*args, **kwargs):
        prepared = real_prepare(*args, **kwargs)
        captured.append(prepared)
        return prepared

    def replace_root(*_args, **_kwargs):
        nonlocal renamed
        prepared = captured[0]
        renamed = prepared.root.with_name(f"{prepared.root.name}-renamed")
        prepared.root.rename(renamed)
        prepared.root.mkdir(mode=0o700)
        prepared.violation_dir.mkdir(mode=0o700)
        prepared.diagnostic.write_bytes(b"")
        prepared.diagnostic.chmod(0o600)
        return airlock.OwnedRun(
            status=0,
            group_empty=True,
            control=(
                b"airlock_inner_noncertifying\n"
                b"airlock_inner_complete:0:call_phase_observed=1\n"
            ),
        )

    monkeypatch.setattr(airlock, "_prepare_disposable", prepare)
    monkeypatch.setattr(airlock, "_run_owned_command", replace_root)
    try:
        terminal = airlock._execute_outer(
            layout,
            inventory,
            caller_args=("scripts/dev/worktree_test_airlock.py", "-q"),
            root_parent=tmp_path,
        )

        assert terminal.status == 86
        assert terminal.refusal == "airlock_cleanup_incomplete"
        assert terminal.certificate is None
        assert renamed is not None and renamed.exists()
    finally:
        for candidate in (renamed, *(item.root for item in captured)):
            if candidate is not None and candidate.exists():
                airlock._remove_disposable(candidate)


def test_outer_malformed_terminal_order_is_fixed_and_cleanup_is_unconditional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    root = tmp_path / "root"
    root.mkdir()
    (root / "python").write_bytes(b"python")
    (root / "pytest.ini").write_text("", encoding="utf-8")
    (root / "diagnostic").write_bytes(b"")
    (root / "diagnostic").chmod(0o600)
    (root / "violations").mkdir()
    prepared = types.SimpleNamespace(
        root=root,
        python=root / "python",
        pytest_config=root / "pytest.ini",
        diagnostic=root / "diagnostic",
        runner=root / "inner_runner.py",
        environment={},
        violation_dir=root / "violations",
    )
    events: list[str] = []
    snapshots = iter(((), ()))

    monkeypatch.setattr(
        airlock,
        "_snapshot_pth",
        lambda _purelib: events.append("snapshot") or next(snapshots),
    )
    monkeypatch.setattr(
        airlock,
        "_prepare_disposable",
        lambda *_args, **_kwargs: events.append("prepare") or prepared,
    )
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_args, **_kwargs: events.append("run")
        or airlock.OwnedRun(status=86, group_empty=True),
    )
    monkeypatch.setattr(
        airlock,
        "_read_marker_state",
        lambda _path: events.append("markers") or (),
    )
    monkeypatch.setattr(
        airlock,
        "_remove_disposable",
        lambda target: events.append("remove") or shutil.rmtree(target),
    )

    terminal = airlock._execute_outer(layout, inventory, root_parent=tmp_path)

    assert terminal.refusal == "airlock_child_setup_failed"
    assert terminal.status == 86
    assert events == ["snapshot", "prepare", "run", "markers", "remove", "snapshot"]


@pytest.mark.parametrize("pytest_status", (0, 1), ids=("green", "red"))
def test_large_valid_diagnostic_is_truncated_without_rewriting_pytest_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pytest_status: int,
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    root = tmp_path / "attempt"
    root.mkdir()
    violations = root / "violations"
    violations.mkdir()
    diagnostic = root / "diagnostic"
    python = root / "python"
    python.write_bytes(b"interpreter")
    pytest_config = root / "pytest.ini"
    pytest_config.write_text("", encoding="utf-8")
    prepared = types.SimpleNamespace(
        root=root,
        python=python,
        runner=root / "runner.py",
        pytest_config=pytest_config,
        environment={},
        violation_dir=violations,
        diagnostic=diagnostic,
    )
    snapshots = iter(((), ()))
    monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: next(snapshots))
    monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)

    def run(*_args, **_kwargs):
        diagnostic.write_bytes(b"x" * (1_048_576 + 1))
        diagnostic.chmod(0o600)
        return airlock.OwnedRun(
            status=pytest_status,
            group_empty=True,
            control=(
                b"airlock_inner_noncertifying\n"
                + f"airlock_inner_complete:{pytest_status}:"
                "call_phase_observed=1\n".encode()
            ),
        )

    monkeypatch.setattr(airlock, "_run_owned_command", run)
    monkeypatch.setattr(airlock, "_prepared_root_processes_absent", lambda _root: True)
    monkeypatch.setattr(airlock, "_read_marker_state", lambda _path: ())
    monkeypatch.setattr(airlock, "_remove_disposable", shutil.rmtree)

    terminal = airlock._execute_outer(
        layout,
        inventory,
        caller_args=("scripts/dev/worktree_test_airlock.py", "-q"),
        root_parent=tmp_path,
    )

    assert terminal.status == pytest_status
    assert terminal.refusal is None
    assert (terminal.certificate is not None) is (pytest_status == 0)
    assert terminal.diagnostic.endswith(b"MAEZ_AIRLOCK_DIAGNOSTIC_TRUNCATED\n")
    assert len(terminal.diagnostic) <= 1_048_576 + 40


@pytest.mark.parametrize("hazard", ("mode", "hardlink", "symlink", "directory"))
def test_private_diagnostic_filesystem_hazards_still_refuse(
    tmp_path: Path,
    hazard: str,
):
    airlock = _airlock()
    diagnostic = tmp_path / "diagnostic"
    if hazard == "directory":
        diagnostic.mkdir(mode=0o700)
    elif hazard == "symlink":
        target = tmp_path / "target"
        target.write_bytes(b"diagnostic")
        target.chmod(0o600)
        diagnostic.symlink_to(target)
    else:
        diagnostic.write_bytes(b"diagnostic")
        diagnostic.chmod(0o600 if hazard == "hardlink" else 0o644)
        if hazard == "hardlink":
            os.link(diagnostic, tmp_path / "second-link")

    with pytest.raises(
        airlock.AirlockRefusal,
        match="airlock_child_setup_failed",
    ):
        airlock._read_private_diagnostic(diagnostic)


def test_outer_terminal_precedence_uses_observed_final_state_not_exception_timing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    prepared = types.SimpleNamespace(
        root=tmp_path / "root",
        python=tmp_path / "python",
        runner=tmp_path / "runner",
        pytest_config=tmp_path / "pytest.ini",
        environment={},
        violation_dir=tmp_path / "violations",
        diagnostic=tmp_path / "diagnostic",
    )
    prepared.python.write_bytes(b"interpreter")
    prepared.pytest_config.write_text("", encoding="utf-8")
    prepared.diagnostic.write_bytes(b"")
    prepared.diagnostic.chmod(0o600)
    before = airlock.PthEntry("before.pth", True, 0o600, 1, "a" * 64)
    after = airlock.PthEntry("after.pth", True, 0o600, 1, "b" * 64)
    snapshots = iter(((before,), (after,)))
    monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: next(snapshots))
    monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_a, **_k: airlock.OwnedRun(status=86, group_empty=False),
    )
    monkeypatch.setattr(airlock, "_read_marker_state", lambda _path: ("marker",))

    def cleanup_fails(_root):
        raise airlock.AirlockRefusal("airlock_cleanup_incomplete")

    monkeypatch.setattr(airlock, "_remove_disposable", cleanup_fails)

    terminal = airlock._execute_outer(layout, inventory, root_parent=tmp_path)
    assert terminal.refusal == "airlock_shared_environment_changed"
    assert terminal.status == 86
    assert terminal.certificate is None


def test_outer_equal_snapshot_with_unproven_group_is_cleanup_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    prepared = types.SimpleNamespace(
        root=tmp_path / "root",
        python=tmp_path / "python",
        runner=tmp_path / "runner",
        pytest_config=tmp_path / "pytest.ini",
        environment={},
        violation_dir=tmp_path / "violations",
        diagnostic=tmp_path / "diagnostic",
    )
    prepared.python.write_bytes(b"interpreter")
    prepared.pytest_config.write_text("", encoding="utf-8")
    prepared.diagnostic.write_bytes(b"")
    prepared.diagnostic.chmod(0o600)
    snapshots = iter(((), ()))
    monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: next(snapshots))
    monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_a, **_k: airlock.OwnedRun(status=86, group_empty=False),
    )
    monkeypatch.setattr(airlock, "_read_marker_state", lambda _path: ())
    monkeypatch.setattr(airlock, "_remove_disposable", lambda _root: None)

    terminal = airlock._execute_outer(layout, inventory, root_parent=tmp_path)
    assert terminal.refusal == "airlock_cleanup_incomplete"
    assert terminal.status == 86
    assert terminal.certificate is None


def test_forbidden_capability_surface_is_structurally_absent():
    source = AIRLOCK_SOURCE.read_text(encoding="utf-8")
    forbidden_literals = (
        "systemctl",
        "llama-server",
        "MAEZ_SCREEN_PERCEPTION",
        "requests.",
        "urllib.request",
        "pip install",
    )
    assert all(literal not in source for literal in forbidden_literals)
    assert "with_pip=False" in source
    assert "system_site_packages=False" in source
    assert "start_new_session=True" in source
    assert "os.O_NOFOLLOW" in source


def test_operator_and_design_docs_state_the_same_narrow_airlock_claim():
    claim = (
        "Every Maez-owned module used by the gate process or an "
        "inherited-contract Python descendant came from tracked code in the "
        "audited checkout; absolute foreign-interpreter children and "
        "project-importing `-S` children are outside this claim."
    )
    boundary = (
        "Same-process frame/FD introspection and deliberate in-process forgery "
        "are outside the airlock's guarantee."
    )
    def normalized_document(path: Path) -> str:
        lines = (
            line.removeprefix("> ")
            for line in path.read_text(encoding="utf-8").splitlines()
        )
        return " ".join("\n".join(lines).split())

    agents = normalized_document(REPO / "AGENTS.md")
    design = normalized_document(
        REPO
        / "docs/superpowers/specs/2026-07-16-clean-checkout-import-airlock-design.md"
    )

    assert claim in agents
    assert claim in design
    assert boundary in agents
    assert boundary in design
    assert "/home/rohit/maez/.venv/bin/python -I -S -B" in agents
    assert "scripts/dev/worktree_test_airlock.py" in agents
    assert "makes no sandbox claim" in agents
    assert "makes no sandbox" in design


# Task 5 REDs: pytest is a closed certification boundary, not a pass-through CLI.


_SIGNAL_COLLECTION_NODE = (
    "tests/test_worktree_airlock_imports.py::test_airlock_signal_collection_probe"
)
_SIGNAL_CALL_NODE = (
    "tests/test_worktree_airlock_imports.py::test_airlock_signal_call_probe"
)
_SIGNAL_IGNORE_NODE = (
    "tests/test_worktree_airlock_imports.py::test_airlock_signal_ignore_probe"
)
_DETACHED_DESCENDANT_NODE = (
    "tests/test_worktree_airlock_imports.py::"
    "test_airlock_detached_descendant_probe"
)


def _block_for_real_airlock_signal(
    phase: str, *, ignore_signals: bool = False
) -> None:
    if ignore_signals:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    root = Path(os.environ["HOME"])
    ready = root / f"signal-{phase}-ready"
    descriptor = os.open(
        ready,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    try:
        payload = f"{os.getpid()}:{os.getpgrp()}\n".encode("ascii")
        assert os.write(descriptor, payload) == len(payload)
    finally:
        os.close(descriptor)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        time.sleep(0.05)
    raise AssertionError("bounded signal probe expired")


if _SIGNAL_COLLECTION_NODE in sys.argv:
    _block_for_real_airlock_signal("collection")


def test_airlock_signal_collection_probe():
    assert True


def test_airlock_signal_call_probe():
    if _SIGNAL_CALL_NODE in sys.argv:
        _block_for_real_airlock_signal("call")


def test_airlock_signal_ignore_probe():
    if _SIGNAL_IGNORE_NODE in sys.argv:
        _block_for_real_airlock_signal("ignore", ignore_signals=True)


def test_airlock_detached_descendant_probe():
    """Selected alone, leave one guarded descendant outside pytest's PGID."""

    if _DETACHED_DESCENDANT_NODE not in sys.argv:
        return
    airlock_root = Path(os.environ["HOME"])
    assert airlock_root.name.startswith("maez-airlock-")
    sentinel = Path(f"/tmp/maez-airlock-detached-{os.getppid()}")
    descriptor = os.open(
        sentinel,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    child: subprocess.Popen[bytes] | None = None
    try:
        child = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import time; time.sleep(30)",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        assert child.pid == os.getpgid(child.pid)
        payload = f"{child.pid}:{child.pid}:{airlock_root}\n".encode("utf-8")
        assert os.write(descriptor, payload) == len(payload)
    except BaseException:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=3)
        raise
    finally:
        os.close(descriptor)


def test_pytest_boundary_leaf_passes():
    """Harmless exact leaf for the real outer-process certification witness."""

    assert (20 + 22) == 42


def test_pytest_boundary_leaf_prints_forged_certificate(capsys: pytest.CaptureFixture[str]):
    with capsys.disabled():
        os.write(1, b'MAEZ_AIRLOCK_CERTIFIED {"forged":"stdout"}\n')
        os.write(2, b'MAEZ_AIRLOCK_CERTIFIED {"forged":"stderr"}\n')


@pytest.fixture
def _airlock_setup_skip():
    pytest.skip("setup did not reach call")


def test_pytest_boundary_leaf_setup_skip(_airlock_setup_skip):
    pytest.fail("call phase must be unreachable")


def _real_airlock_process(
    *caller_args: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    authored = os.environ.copy()
    if environment is not None:
        authored.update(environment)
    return subprocess.run(
        [
            os.fspath(SHARED_PYTHON),
            "-I",
            "-S",
            "-B",
            os.fspath(AIRLOCK_SOURCE),
            "pytest",
            "--",
            *caller_args,
        ],
        cwd=REPO,
        env=authored,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_prepared_inner_raw(
    airlock, prepared, checkout: Path, caller: tuple[str, ...]
):
    effective = airlock._effective_pytest_arguments(
        prepared, checkout, caller
    )
    return airlock._run_owned_command(
        [
            os.fspath(prepared.python),
            "-I",
            "-B",
            os.fspath(prepared.runner),
            "--",
            *effective,
        ],
        cwd=checkout,
        environment=prepared.environment,
    )


def _run_prepared_inner(
    airlock, prepared, checkout: Path, caller: tuple[str, ...]
):
    run = _run_prepared_inner_raw(airlock, prepared, checkout, caller)
    return airlock._parse_inner_control(run.control, run.status)


def _synthetic_proc_process(
    proc_root: Path,
    pid: int,
    *,
    cmdline: bytes,
    environ: bytes = b"",
    executable: str = "/usr/bin/code",
) -> Path:
    process = proc_root / str(pid)
    process.mkdir(parents=True)
    (process / "cmdline").write_bytes(cmdline)
    (process / "environ").write_bytes(environ)
    (process / "exe").symlink_to(executable)
    return process


def test_descendant_scan_ignores_unreadable_environment_for_non_python(
    tmp_path: Path,
):
    airlock = _airlock()
    prepared_root = tmp_path / "maez-airlock-owned"
    prepared_root.mkdir()
    proc_root = tmp_path / "proc"
    process = _synthetic_proc_process(
        proc_root,
        101,
        cmdline=b"/usr/bin/code\0--unity-launch\0",
    )
    reads: list[str] = []

    def read_bytes(path: Path, limit: int) -> bytes:
        reads.append(path.name)
        if path.name == "environ":
            raise PermissionError("ambient environment is unreadable")
        payload = path.read_bytes()
        assert len(payload) <= limit
        return payload

    assert airlock._scan_prepared_root_processes(
        prepared_root,
        proc_root=proc_root,
        byte_reader=read_bytes,
    )
    assert process.exists()
    assert reads == ["cmdline"]


def test_descendant_scan_refuses_unreadable_environment_for_python(
    tmp_path: Path,
):
    airlock = _airlock()
    prepared_root = tmp_path / "maez-airlock-owned"
    prepared_root.mkdir()
    proc_root = tmp_path / "proc"
    _synthetic_proc_process(
        proc_root,
        102,
        cmdline=b"python3\0-c\0pass\0",
        executable="/usr/bin/python3",
    )

    def read_bytes(path: Path, limit: int) -> bytes:
        if path.name == "environ":
            raise PermissionError("relevant environment is unreadable")
        payload = path.read_bytes()
        assert len(payload) <= limit
        return payload

    assert not airlock._scan_prepared_root_processes(
        prepared_root,
        proc_root=proc_root,
        byte_reader=read_bytes,
    )


def test_descendant_scan_finds_bare_python_from_inherited_environment(
    tmp_path: Path,
):
    airlock = _airlock()
    prepared_root = tmp_path / "maez-airlock-owned"
    prepared_root.mkdir()
    proc_root = tmp_path / "proc"
    _synthetic_proc_process(
        proc_root,
        103,
        cmdline=b"python\0-c\0pass\0",
        environ=(
            f"VIRTUAL_ENV={prepared_root / 'venv'}\0"
            f"PATH={prepared_root / 'venv/bin'}:/usr/bin\0"
        ).encode(),
        executable="/usr/bin/python3",
    )

    assert not airlock._scan_prepared_root_processes(
        prepared_root,
        proc_root=proc_root,
    )


@pytest.mark.parametrize("missing_name", ("cmdline", "environ"))
def test_descendant_scan_reproves_relevant_python_vanished_on_missing_proc_file(
    tmp_path: Path,
    missing_name: str,
):
    airlock = _airlock()
    prepared_root = tmp_path / "maez-airlock-owned"
    prepared_root.mkdir()
    proc_root = tmp_path / "proc"
    _synthetic_proc_process(
        proc_root,
        104,
        cmdline=b"python3\0-c\0pass\0",
        executable="/usr/bin/python3",
    )

    def read_bytes(path: Path, limit: int) -> bytes:
        if path.name == missing_name:
            raise FileNotFoundError("process metadata disappeared")
        payload = path.read_bytes()
        assert len(payload) <= limit
        return payload

    assert not airlock._scan_prepared_root_processes(
        prepared_root,
        proc_root=proc_root,
        byte_reader=read_bytes,
    )


def test_descendant_scan_stops_at_the_process_count_bound(tmp_path: Path):
    airlock = _airlock()
    prepared_root = tmp_path / "maez-airlock-owned"
    prepared_root.mkdir()

    class BoundedProcRoot:
        def __init__(self) -> None:
            self.consumed = 0

        def iterdir(self):
            while True:
                self.consumed += 1
                if self.consumed > airlock._PROC_SCAN_MAX_PROCESSES + 1:
                    raise AssertionError("scanner consumed beyond its bound")
                yield tmp_path / str(self.consumed)

    proc_root = BoundedProcRoot()
    assert not airlock._scan_prepared_root_processes(
        prepared_root,
        proc_root=proc_root,
    )
    assert proc_root.consumed == airlock._PROC_SCAN_MAX_PROCESSES + 1


def test_descendant_absence_requires_two_ordered_scans(tmp_path: Path):
    airlock = _airlock()
    prepared_root = tmp_path / "maez-airlock-owned"
    prepared_root.mkdir()
    events: list[object] = []
    answers = iter((True, False))

    def scanner(root: Path) -> bool:
        events.append(("scan", root))
        return next(answers)

    def sleeper(delay: float) -> None:
        events.append(("sleep", delay))

    assert not airlock._prepared_root_processes_absent(
        prepared_root,
        scanner=scanner,
        sleeper=sleeper,
    )
    assert events == [
        ("scan", prepared_root),
        ("sleep", 0.05),
        ("scan", prepared_root),
    ]


@pytest.mark.parametrize(
    "arguments",
    (
        ("@pytest-args.txt",),
        ("-qk", "leaf"),
        ("--quiet",),
        ("--import-mode=importlib",),
        ("--import-mode", "importlib"),
        (os.fspath(REPO / "tests/test_worktree_airlock_imports.py"),),
        ("tests/../tests/test_worktree_airlock_imports.py",),
        ("--", "tests/test_worktree_airlock_imports.py"),
    ),
    ids=(
        "response-file",
        "clustered-short",
        "unknown-alias",
        "import-mode-equals",
        "import-mode-split",
        "absolute",
        "dotdot",
        "nested-separator",
    ),
)
def test_pytest_boundary_rejects_each_unsealed_caller_shape(
    arguments: tuple[str, ...],
):
    airlock = _airlock()

    with pytest.raises(
        airlock.AirlockRefusal, match="airlock_pytest_arguments_invalid"
    ):
        airlock._parse_pytest_invocation(
            ("pytest", "--", *arguments), REPO, environment={}
        )


def test_pytest_boundary_rejects_response_file_hidden_as_k_expression(
    tmp_path: Path,
):
    response_file = tmp_path / "pytest.args"
    response_file.write_text("leaf\n--tb=no\n", encoding="utf-8")

    process = _real_airlock_process(
        "tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes",
        "-k",
        f"@{response_file}",
        "-q",
    )

    assert process.returncode == 86
    assert process.stdout == ""
    assert "MAEZ_AIRLOCK_CERTIFIED" not in process.stdout + process.stderr
    assert process.stderr.rstrip().endswith("airlock_pytest_arguments_invalid")


@pytest.mark.parametrize("expression", ("@args.txt", "--tb=no"))
def test_pytest_boundary_rejects_non_expression_k_operands(expression: str):
    airlock = _airlock()

    with pytest.raises(
        airlock.AirlockRefusal, match="airlock_pytest_arguments_invalid"
    ):
        airlock._parse_pytest_invocation(
            (
                "pytest",
                "--",
                "tests/test_worktree_airlock_imports.py",
                "-k",
                expression,
            ),
            REPO,
            environment={},
        )


@pytest.mark.parametrize(
    "caller_args",
    (
        (
            b"tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes",
            b"-k",
            b"\xff",
            b"-q",
        ),
        (
            b"tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes\xff",
            b"-q",
        ),
    ),
    ids=("k-expression", "node-suffix"),
)
def test_real_outer_rejects_non_utf8_caller_arguments(caller_args: tuple[bytes, ...]):
    process = subprocess.run(
        [
            os.fsencode(SHARED_PYTHON),
            b"-I",
            b"-S",
            b"-B",
            os.fsencode(AIRLOCK_SOURCE),
            b"pytest",
            b"--",
            *caller_args,
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
    )

    assert process.returncode == 86
    assert process.stdout == b""
    assert b"Traceback" not in process.stderr
    assert process.stderr.rstrip().endswith(b"airlock_pytest_arguments_invalid")


def test_pytest_boundary_rejects_selector_symlink_escape(tmp_path: Path):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    outside = tmp_path / "outside"
    checkout.mkdir()
    outside.mkdir()
    (outside / "test_external.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (checkout / "tests").symlink_to(outside, target_is_directory=True)

    with pytest.raises(
        airlock.AirlockRefusal, match="airlock_pytest_arguments_invalid"
    ):
        airlock._parse_pytest_invocation(
            ("pytest", "--", "tests/test_external.py::test_x"),
            checkout,
            environment={},
        )


@pytest.mark.parametrize("variable", ("PYTEST_ADDOPTS", "PYTEST_PLUGINS"))
def test_pytest_boundary_rejects_even_empty_ambient_pytest_variables_before_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    variable: str,
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    monkeypatch.setenv(variable, "")
    monkeypatch.setattr(airlock, "_validate_outer_invocation", lambda: layout)
    monkeypatch.setattr(airlock, "_run_preflight", lambda _layout: inventory)
    monkeypatch.setattr(
        airlock,
        "_prepare_disposable",
        lambda *_args, **_kwargs: pytest.fail("disposable construction was reached"),
    )

    status = airlock.main(
        ("pytest", "--", "scripts/dev/worktree_test_airlock.py")
    )

    captured = capsys.readouterr()
    assert status == 86
    assert captured.out == ""
    assert captured.err == "airlock_pytest_arguments_invalid\n"


def test_pytest_boundary_accepts_only_frozen_small_surface_and_preserves_order():
    airlock = _airlock()
    caller = (
        "tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes",
        "-q",
        "-k",
        "leaf and not forged",
        "--collect-only",
    )

    assert airlock._parse_pytest_invocation(
        ("pytest", "--", *caller), REPO, environment={}
    ) == caller


def test_pytest_boundary_requires_a_selector_and_rejects_empty_k_expression():
    airlock = _airlock()
    for caller in ((), ("-q",), ("-k", ""), ("-k",)):
        with pytest.raises(
            airlock.AirlockRefusal, match="airlock_pytest_arguments_invalid"
        ):
            airlock._parse_pytest_invocation(
                ("pytest", "--", *caller), REPO, environment={}
            )


def test_pytest_boundary_freezes_and_hashes_the_complete_owned_vector(tmp_path: Path):
    caller = ("core/good.py", "-q")
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path, caller_args=caller
    )
    try:
        effective = airlock._effective_pytest_arguments(
            prepared, tmp_path / "checkout", caller
        )
        assert effective == (
            "-c",
            os.fspath(prepared.pytest_config),
            "--rootdir",
            os.fspath(tmp_path / "checkout"),
            "--confcutdir",
            os.fspath(tmp_path / "checkout"),
            "-p",
            "no:cacheprovider",
            "-p",
            "anyio.pytest_plugin",
            *caller,
        )
        expected = hashlib.sha256(
            json.dumps(
                effective,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        assert airlock._hash_effective_pytest_arguments(effective) == expected
        assert airlock._hash_effective_pytest_arguments(effective) != (
            airlock._hash_effective_pytest_arguments(caller)
        )
        assert prepared.environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    finally:
        airlock._remove_disposable(prepared.root)


def test_owned_empty_config_defeats_hostile_checkout_pytest_configuration(
    tmp_path: Path,
):
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "pytest.ini": textwrap.dedent(
                """
                [pytest]
                addopts = --collect-only -p definitely_missing_airlock_plugin
                pythonpath = /foreign-airlock-path
                """
            ),
            "tests/test_config_boundary.py": textwrap.dedent(
                """
                import sys

                def test_owned_config_wins():
                    assert '/foreign-airlock-path' not in sys.path
                """
            ),
        },
    )
    try:
        control = _run_prepared_inner(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_config_boundary.py", "-q"),
        )
        assert control.status == 0
        assert control.call_phase_observed is True
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_pytest_status_five_is_honest_empty_selection(tmp_path: Path):
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    try:
        control = _run_prepared_inner(
            airlock,
            prepared,
            layout.checkout,
            ("tests/test_leaf.py", "-q", "-k", "definitely_no_match"),
        )

        assert control.status == 5
        assert control.call_phase_observed is False
    finally:
        airlock._remove_disposable(prepared.root)


def test_pytest_status_six_is_honest_max_warnings_error(tmp_path: Path):
    conftest = textwrap.dedent(
        """
        def pytest_configure(config):
            config.option.max_warnings = 0
        """
    )
    test_source = textwrap.dedent(
        """
        import warnings

        def test_warns():
            warnings.warn('airlock status six witness', UserWarning)
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_warns.py": test_source,
        },
    )
    try:
        control = _run_prepared_inner(
            airlock,
            prepared,
            layout.checkout,
            ("tests/test_warns.py", "-q"),
        )

        assert control.status == 6
        assert control.call_phase_observed is True
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("status", tuple(range(7)))
def test_pytest_status_closed_standard_set_propagates_exactly(status: int):
    airlock = _airlock()

    assert airlock._normalize_pytest_status(status) == status


@pytest.mark.parametrize("status", (-1, 7, 42, 86, 255))
def test_pytest_status_outside_closed_set_is_child_setup_failure(status: int):
    airlock = _airlock()

    with pytest.raises(airlock.AirlockRefusal, match="airlock_child_setup_failed"):
        airlock._normalize_pytest_status(status)


def test_inner_noncertifying_control_parser_requires_exact_status_and_call_bit():
    airlock = _airlock()
    valid = (
        b"airlock_inner_noncertifying\n"
        b"airlock_inner_complete:0:call_phase_observed=1\n"
    )
    parsed = airlock._parse_inner_control(valid, 0)
    assert parsed.status == 0
    assert parsed.call_phase_observed is True
    malformed = (
        b"",
        b"airlock_inner_noncertifying\n",
        valid + b"airlock_inner_complete:0:call_phase_observed=1\n",
        b"airlock_inner_noncertifying\nairlock_inner_complete:0\n",
        b"airlock_inner_noncertifying\n"
        b"airlock_inner_complete:0:call_phase_observed=1:certificate_eligible=1\n",
        b"airlock_inner_noncertifying\n"
        b"airlock_inner_complete:00:call_phase_observed=1\n",
    )
    for payload in malformed:
        with pytest.raises(airlock.AirlockRefusal, match="airlock_child_setup_failed"):
            airlock._parse_inner_control(payload, 0)


@pytest.mark.parametrize("status", tuple(range(8)))
def test_pytest_status_outer_preserves_closed_set_and_refuses_out_of_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    root = tmp_path / "attempt"
    root.mkdir()
    violation_dir = root / "violations"
    violation_dir.mkdir()
    diagnostic = root / "diagnostic"
    diagnostic.write_bytes(b"pytest diagnostic\n")
    diagnostic.chmod(0o600)
    python = root / "python"
    python.write_bytes(b"interpreter")
    prepared = types.SimpleNamespace(
        root=root,
        python=python,
        runner=root / "runner.py",
        pytest_config=root / "pytest.ini",
        environment={},
        violation_dir=violation_dir,
        diagnostic=diagnostic,
    )
    prepared.pytest_config.write_text("", encoding="utf-8")
    control = (
        "airlock_inner_noncertifying\n"
        f"airlock_inner_complete:{status}:call_phase_observed=1\n"
    ).encode("ascii")
    monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_a, **_k: airlock.OwnedRun(
            status=status, group_empty=True, control=control
        ),
    )
    monkeypatch.setattr(airlock, "_read_marker_state", lambda _path: ())
    monkeypatch.setattr(airlock, "_remove_disposable", shutil.rmtree)
    monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: ())

    terminal = airlock._execute_outer(
        layout,
        inventory,
        caller_args=("scripts/dev/worktree_test_airlock.py",),
        root_parent=tmp_path,
    )

    if status in range(7):
        assert terminal.status == status
        assert terminal.refusal is None
        assert (terminal.certificate is not None) is (status == 0)
    else:
        assert terminal.status == 86
        assert terminal.refusal == "airlock_child_setup_failed"
        assert terminal.certificate is None


def test_pytest_status_malformed_control_is_integrity_refusal_in_outer_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    root = tmp_path / "attempt"
    root.mkdir()
    violation_dir = root / "violations"
    violation_dir.mkdir()
    diagnostic = root / "diagnostic"
    diagnostic.write_bytes(b"private details\n")
    diagnostic.chmod(0o600)
    prepared = types.SimpleNamespace(
        root=root,
        python=root / "python",
        runner=root / "runner.py",
        pytest_config=root / "pytest.ini",
        environment={},
        violation_dir=violation_dir,
        diagnostic=diagnostic,
    )
    monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_a, **_k: airlock.OwnedRun(
            status=0,
            group_empty=True,
            control=b"airlock_inner_noncertifying\nmalformed\n",
        ),
    )
    monkeypatch.setattr(airlock, "_read_marker_state", lambda _path: ())
    monkeypatch.setattr(airlock, "_remove_disposable", shutil.rmtree)
    monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: ())

    terminal = airlock._execute_outer(
        layout,
        inventory,
        caller_args=("scripts/dev/worktree_test_airlock.py",),
        root_parent=tmp_path,
    )

    assert terminal.status == 86
    assert terminal.refusal == "airlock_child_setup_failed"
    assert terminal.certificate is None


def test_inner_noncertifying_runner_and_inner_main_cannot_emit_certificate(tmp_path: Path):
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    try:
        runner_source = prepared.runner.read_text(encoding="utf-8")
        inner_source = inspect.getsource(airlock._inner_main)
        assert "MAEZ_AIRLOCK_CERTIFIED" not in runner_source
        assert "MAEZ_AIRLOCK_CERTIFIED" not in inner_source
        assert "_write_certificate" not in runner_source
        assert "_write_certificate" not in inner_source
        result = subprocess.run(
            [
                os.fspath(prepared.python),
                "-I",
                "-B",
                os.fspath(prepared.runner),
                "--",
                *airlock._effective_pytest_arguments(
                    prepared,
                    tmp_path / "checkout",
                    ("tests/test_leaf.py", "-q"),
                ),
            ],
            cwd=tmp_path / "checkout",
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.splitlines() == [
            "airlock_inner_noncertifying",
            "airlock_inner_complete:0:call_phase_observed=1",
        ]
        assert "MAEZ_AIRLOCK_CERTIFIED" not in result.stdout
    finally:
        airlock._remove_disposable(prepared.root)


def test_certificate_forgery_from_test_stdout_and_stderr_stays_diagnostic_only():
    result = _real_airlock_process(
        "tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_prints_forged_certificate",
        "-q",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("MAEZ_AIRLOCK_CERTIFIED ") == 1
    assert '"forged"' not in result.stdout
    assert '"forged"' in result.stderr


def test_certificate_real_outer_emits_one_content_light_terminal_record():
    caller = (
        "tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes",
        "-q",
    )
    result = _real_airlock_process(*caller)

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("MAEZ_AIRLOCK_CERTIFIED ")
    assert result.stdout.count("\n") == 1
    payload = json.loads(result.stdout.removeprefix("MAEZ_AIRLOCK_CERTIFIED "))
    assert set(payload) == {
        "schema",
        "isolation",
        "git_head",
        "interpreter_version",
        "interpreter_sha256",
        "shared_pth_sha256",
        "pytest_args_sha256",
    }
    assert payload["schema"] == "worktree_test_airlock.certificate.v1"
    assert payload["isolation"] == "inherited_interpreter_contract"
    assert payload["git_head"] == subprocess.run(
        ["/usr/bin/git", "rev-parse", "HEAD"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert payload["interpreter_version"] == (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    assert payload["interpreter_sha256"] == hashlib.sha256(
        SHARED_PYTHON.read_bytes()
    ).hexdigest()
    airlock = _airlock()
    shared_purelib = SHARED_PURELIB
    assert payload["shared_pth_sha256"] == airlock._hash_pth_projection(
        airlock._snapshot_pth(shared_purelib)
    )
    rendered = json.dumps(payload, sort_keys=True)
    assert all(part not in rendered for part in caller)
    assert os.fspath(REPO) not in rendered
    assert "PYTEST_" not in rendered


def test_certificate_builder_binds_actual_inputs_without_asserted_hashes(
    tmp_path: Path,
):
    airlock = _airlock()
    interpreter = tmp_path / "python"
    interpreter.write_bytes(b"pinned-interpreter")
    entries = (
        airlock.PthEntry(
            name="editable.pth",
            is_regular=True,
            mode=0o644,
            size=7,
            sha256="b" * 64,
        ),
    )
    arguments = ("-c", "/private/pytest.ini", "tests/test_leaf.py", "-q")
    inventory = airlock.GitInventory(
        head="a" * 40,
        tracked_files=(),
        tracked_python_files=(),
        maez_roots=(),
        registered_worktrees=(),
    )

    certificate = airlock._build_certificate(
        inventory=inventory,
        interpreter=interpreter,
        shared_pth=entries,
        effective_pytest_args=arguments,
    )

    expected_pth = json.dumps(
        (
            {
                "name": "editable.pth",
                "is_regular": True,
                "mode": 0o644,
                "size": 7,
                "sha256": "b" * 64,
            },
        ),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    expected_arguments = json.dumps(
        arguments, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    assert certificate["git_head"] == "a" * 40
    assert certificate["interpreter_sha256"] == hashlib.sha256(
        b"pinned-interpreter"
    ).hexdigest()
    assert certificate["shared_pth_sha256"] == hashlib.sha256(
        expected_pth
    ).hexdigest()
    assert certificate["pytest_args_sha256"] == hashlib.sha256(
        expected_arguments
    ).hexdigest()


@pytest.mark.parametrize(
    "mode",
    ("--collect-only", "--collectonly", "--co", "--setup-only", "--setup-plan"),
)
def test_certificate_status_zero_without_plugin_observed_call_does_not_certify(
    mode: str,
):
    result = _real_airlock_process(
        "tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_passes",
        mode,
        "-q",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert "MAEZ_AIRLOCK_CERTIFIED" not in result.stderr


def test_certificate_setup_skip_status_zero_without_call_does_not_certify():
    result = _real_airlock_process(
        "tests/test_worktree_airlock_imports.py::test_pytest_boundary_leaf_setup_skip",
        "-q",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert "MAEZ_AIRLOCK_CERTIFIED" not in result.stderr


def test_pytest_status_one_is_honest_red_not_integrity_and_never_certifies(tmp_path: Path):
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/test_failure.py": "def test_failure():\n    assert 2 + 2 == 5\n",
        },
    )
    try:
        control = _run_prepared_inner(
            airlock, prepared, tmp_path / "checkout", ("tests/test_failure.py", "-q")
        )
        assert control.status == 1
        assert control.call_phase_observed is True
        diagnostic = prepared.diagnostic.read_text(encoding="utf-8")
        assert "assert (2 + 2) == 5" in diagnostic or "assert 4 == 5" in diagnostic
        assert "airlock_" not in diagnostic
    finally:
        airlock._remove_disposable(prepared.root)


def test_plugin_origin_dispatcher_precedes_assertion_rewrite_and_diagnostics_survive(
    tmp_path: Path,
):
    events = tmp_path / "rewrite-events"
    conftest = textwrap.dedent(
        f"""
        import sys
        from pathlib import Path

        guard = sys.modules['_maez_worktree_airlock_guard']
        original = guard.validate_spec

        def observed(fullname, spec):
            if fullname == 'tests.test_rewrite':
                with Path({os.fspath(events)!r}).open('a', encoding='utf-8') as stream:
                    stream.write('validate\\n')
            return original(fullname, spec)

        guard.validate_spec = observed
        """
    )
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_rewrite.py": (
                "import sys\n"
                "from pathlib import Path\n"
                f"with Path({os.fspath(events)!r}).open('a', encoding='utf-8') as stream:\n"
                "    stream.write('execute\\n')\n"
                "def test_rewrite():\n"
                "    guard = sys.modules['_maez_worktree_airlock_guard']\n"
                "    assert sys.meta_path[0] is guard.DISPATCHER\n"
                "    assert any(type(f).__module__ == '_pytest.assertion.rewrite' "
                "and type(f).__name__ == 'AssertionRewritingHook' "
                "for f in sys.meta_path[1:])\n"
                "    actual = 2 + 2\n"
                "    expected = 5\n"
                "    assert actual == expected\n"
            ),
        },
    )
    try:
        control = _run_prepared_inner(
            airlock, prepared, tmp_path / "checkout", ("tests/test_rewrite.py", "-q")
        )
        diagnostic = prepared.diagnostic.read_text(encoding="utf-8")
        assert control.status == 1
        assert "assert 4 == 5" in diagnostic
        assert events.read_text(encoding="utf-8").splitlines() == [
            "validate",
            "execute",
        ]
    finally:
        airlock._remove_disposable(prepared.root)


def test_plugin_origin_unpaired_report_cannot_create_failure_or_call_evidence():
    airlock = _airlock()
    guard = types.SimpleNamespace(
        audit_before_pytest=lambda: None,
        restore_dispatcher_front=lambda: None,
        DISPATCHER=object(),
    )
    plugin = airlock._AirlockPytestPlugin(
        guard=guard,
        checkout=REPO,
        shared_purelib=SHARED_PURELIB,
    )
    plugin.pytest_runtest_logreport(
        types.SimpleNamespace(when="call", failed=True)
    )

    assert plugin.call_phase_observed is False
    assert plugin.failure_observed is False
    assert plugin.final_snapshot(0).certificate_eligible is False


@pytest.mark.parametrize(
    ("kind", "expected"),
    (
        ("plugin", "airlock_import_provenance_violation"),
        ("item", "airlock_collection_escape"),
        ("external-conftest", "airlock_collection_escape"),
        ("untracked-conftest", "airlock_collection_escape"),
    ),
)
def test_plugin_origin_and_collection_refusal_mapping_is_pinned(
    tmp_path: Path,
    kind: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    outside = tmp_path / "outside"
    checkout.mkdir()
    shared.mkdir()
    outside.mkdir()
    seen: list[str] = []

    def violate(token: str):
        seen.append(token)
        raise RuntimeError(token)

    guard = types.SimpleNamespace(
        audit_before_pytest=lambda: None,
        restore_dispatcher_front=lambda: None,
        DISPATCHER=object(),
        _violate=violate,
        _TRACKED_FILES=frozenset(),
    )
    plugin = airlock._AirlockPytestPlugin(
        guard=guard,
        checkout=checkout,
        shared_purelib=shared,
    )
    conftest = "conftest" in kind
    foreign = (
        (checkout if kind == "untracked-conftest" else outside) / "conftest.py"
        if conftest
        else outside / "test_x.py"
    )
    foreign.write_text("\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=expected):
        if kind == "plugin":
            module = types.ModuleType("unapproved_plugin")
            module.__file__ = os.fspath(foreign)
            module.__spec__ = importlib.util.spec_from_file_location(
                "unapproved_plugin", foreign
            )
            assert module.__spec__ is not None
            module.__loader__ = module.__spec__.loader
            module.__package__ = module.__spec__.parent
            monkeypatch.setitem(sys.modules, "unapproved_plugin", module)
            plugin.pytest_plugin_registered(module, "unapproved", None)
        elif kind == "item":
            wrapper = plugin.pytest_collection_modifyitems(
                None,
                None,
                [types.SimpleNamespace(path=foreign, nodeid="foreign")],
            )
            next(wrapper)
            wrapper.send(None)
        else:
            module = types.ModuleType("conftest")
            module.__file__ = os.fspath(foreign)
            module.__spec__ = importlib.util.spec_from_file_location(
                "conftest", foreign
            )
            assert module.__spec__ is not None
            module.__loader__ = module.__spec__.loader
            module.__package__ = module.__spec__.parent
            monkeypatch.setitem(sys.modules, "conftest", module)
            plugin.pytest_plugin_registered(module, os.fspath(foreign), None)

    assert seen == [expected]


def test_real_preimport_untracked_conftest_maps_collection_escape(
    tmp_path: Path,
):
    selector = "tests/test_leaf.py::test_leaf"
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        caller_args=(selector, "-q"),
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    airlock._remove_disposable(prepared.root)
    (layout.checkout / "tests/conftest.py").write_text(
        "VALUE = 'untracked'\n", encoding="utf-8"
    )
    runs = tmp_path / "runs"
    runs.mkdir()

    terminal = airlock._execute_outer(
        layout,
        inventory,
        caller_args=(selector, "-q"),
        root_parent=runs,
    )

    assert terminal.status == 86
    assert terminal.refusal == "airlock_collection_escape"
    assert terminal.certificate is None


def test_real_preimport_external_conftest_maps_collection_escape_before_execution(
    tmp_path: Path,
):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = tmp_path / "external-conftest-executed"
    foreign = outside / "conftest.py"
    foreign.write_text(
        "from pathlib import Path\n"
        f"Path({os.fspath(sentinel)!r}).write_text('executed', encoding='utf-8')\n",
        encoding="utf-8",
    )
    probe = textwrap.dedent(
        f"""
        import importlib.util
        import sys

        class ExternalConftestFinder:
            def find_spec(self, fullname, path=None, target=None):
                del path, target
                if fullname == 'foreign_conftest':
                    return importlib.util.spec_from_file_location(
                        fullname, {os.fspath(foreign)!r}
                    )
                return None

        sys.meta_path.append(ExternalConftestFinder())

        def test_external_conftest():
            import foreign_conftest

            assert foreign_conftest is not None
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/test_external_conftest.py": probe,
        },
        dependency_purelib=SHARED_PURELIB,
    )
    try:
        run = _run_prepared_inner_raw(
            airlock,
            prepared,
            layout.checkout,
            ("tests/test_external_conftest.py", "-q"),
        )

        assert not sentinel.exists(), (
            run,
            prepared.diagnostic.read_text(encoding="utf-8", errors="replace"),
        )
        assert airlock._read_marker_state(prepared.violation_dir) == (
            "airlock_collection_escape",
        ), (
            run,
            prepared.diagnostic.read_text(encoding="utf-8", errors="replace"),
        )
        assert run.status != 0
    finally:
        airlock._remove_disposable(prepared.root)


def test_plugin_origin_accepts_only_exact_anyio_plugin_from_shared_purelib():
    airlock = _airlock()
    anyio_plugin = __import__("anyio.pytest_plugin", fromlist=("pytest_plugin",))
    shared = SHARED_PURELIB
    guard = types.SimpleNamespace(
        audit_before_pytest=lambda: None,
        restore_dispatcher_front=lambda: None,
        DISPATCHER=object(),
        _TRACKED_FILES=frozenset(),
        _violate=lambda token: pytest.fail(f"unexpected refusal: {token}"),
    )
    plugin = airlock._AirlockPytestPlugin(
        guard=guard,
        checkout=REPO,
        shared_purelib=shared,
    )

    plugin.pytest_plugin_registered(
        anyio_plugin, "anyio.pytest_plugin", None
    )


def test_plugin_origin_rejects_core_module_under_wrong_registration_name():
    airlock = _airlock()
    core_plugin = __import__("_pytest.main", fromlist=("main",))
    shared = SHARED_PURELIB
    plugin = _airlock_plugin_for_unit_test(airlock, REPO, shared)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        plugin.pytest_plugin_registered(
            core_plugin, "definitely-wrong-registration", None
        )


def test_plugin_origin_rejects_unapproved_module_inside_shared_purelib(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    checkout.mkdir()
    shared.mkdir()
    origin = shared / "rogue.py"
    origin.write_text("\n", encoding="utf-8")
    module = _synthetic_plugin_module("_pytest.rogue", origin)
    monkeypatch.setitem(sys.modules, "_pytest.rogue", module)
    plugin = _airlock_plugin_for_unit_test(airlock, checkout, shared)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        plugin.pytest_plugin_registered(module, "rogue", None)


def test_terminal_order_certificate_is_last_after_every_outer_finalizer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    airlock = _airlock()
    events: list[str] = []
    layout = _synthetic_layout(tmp_path)
    selector = layout.checkout / "test_leaf.py"
    selector.write_text("def test_leaf(): pass\n", encoding="utf-8")
    inventory = _inventory_for(layout.checkout)
    root = tmp_path / "attempt"
    root.mkdir()
    violation_dir = root / "violations"
    violation_dir.mkdir()
    diagnostic = root / "diagnostic"
    diagnostic.write_bytes(b"")
    diagnostic.chmod(0o600)
    python = root / "python"
    python.write_bytes(b"interpreter")
    pytest_config = root / "pytest.ini"
    pytest_config.write_text("", encoding="utf-8")
    prepared = types.SimpleNamespace(
        root=root,
        python=python,
        runner=root / "runner.py",
        pytest_config=pytest_config,
        environment={},
        violation_dir=violation_dir,
        diagnostic=diagnostic,
    )
    monkeypatch.setattr(airlock, "_validate_outer_invocation", lambda: layout)
    monkeypatch.setattr(airlock, "_run_preflight", lambda _layout: inventory)
    monkeypatch.setattr(
        airlock,
        "_snapshot_pth",
        lambda _path: events.append("snapshot") or (),
    )
    monkeypatch.setattr(
        airlock,
        "_prepare_disposable",
        lambda *_a, **_k: events.append("prepare") or prepared,
    )
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_a, **_k: events.append("run")
        or airlock.OwnedRun(
            status=0,
            group_empty=True,
            control=(
                b"airlock_inner_noncertifying\n"
                b"airlock_inner_complete:0:call_phase_observed=1\n"
            ),
        ),
    )
    monkeypatch.setattr(
        airlock,
        "_read_marker_state",
        lambda _path: events.append("marker") or (),
    )
    monkeypatch.setattr(
        airlock,
        "_prepared_root_processes_absent",
        lambda _root: events.append("descendants") or True,
    )

    def remove(path: Path) -> None:
        events.append("remove")
        shutil.rmtree(path)

    monkeypatch.setattr(airlock, "_remove_disposable", remove)
    original_restore = airlock._OuterSignalScope.restore

    def restore(scope) -> bool:
        events.append("signals")
        return original_restore(scope)

    monkeypatch.setattr(airlock._OuterSignalScope, "restore", restore)
    original_write = airlock._write_certificate

    def write(payload, *, stream=sys.stdout) -> None:
        events.append("certificate")
        original_write(payload, stream=stream)

    monkeypatch.setattr(airlock, "_write_certificate", write)

    status = airlock.main(("pytest", "--", "test_leaf.py"))
    captured = capsys.readouterr()

    assert events == [
        "snapshot",
        "prepare",
        "run",
        "descendants",
        "marker",
        "remove",
        "snapshot",
        "signals",
        "certificate",
    ]
    assert status == 0
    assert captured.out.startswith("MAEZ_AIRLOCK_CERTIFIED ")
    payload = json.loads(captured.out.removeprefix("MAEZ_AIRLOCK_CERTIFIED "))
    effective = (
        "-c",
        os.fspath(pytest_config),
        "--rootdir",
        os.fspath(layout.checkout),
        "--confcutdir",
        os.fspath(layout.checkout),
        "-p",
        "no:cacheprovider",
        "-p",
        "anyio.pytest_plugin",
        "test_leaf.py",
    )
    expected_args = hashlib.sha256(
        json.dumps(
            effective, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    expected_pth = hashlib.sha256(
        json.dumps(
            (), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()
    assert payload == {
        "schema": "worktree_test_airlock.certificate.v1",
        "isolation": "inherited_interpreter_contract",
        "git_head": inventory.head,
        "interpreter_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        ),
        "interpreter_sha256": hashlib.sha256(b"interpreter").hexdigest(),
        "shared_pth_sha256": expected_pth,
        "pytest_args_sha256": expected_args,
    }


@pytest.mark.parametrize(
    "mode",
    ("--collect-only", "--collectonly", "--co", "--setup-only", "--setup-plan"),
)
def test_diagnostic_mode_outer_rejects_forged_positive_call_control(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    root = tmp_path / "attempt"
    root.mkdir()
    violation_dir = root / "violations"
    violation_dir.mkdir()
    python = root / "python"
    python.write_bytes(b"interpreter")
    pytest_config = root / "pytest.ini"
    pytest_config.write_text("", encoding="utf-8")
    diagnostic = root / "diagnostic"
    diagnostic.write_bytes(b"")
    diagnostic.chmod(0o600)
    prepared = types.SimpleNamespace(
        root=root,
        python=python,
        runner=root / "runner.py",
        pytest_config=pytest_config,
        environment={},
        violation_dir=violation_dir,
        diagnostic=diagnostic,
    )
    forged = (
        b"airlock_inner_noncertifying\n"
        b"airlock_inner_complete:0:call_phase_observed=1\n"
    )
    monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_a, **_k: airlock.OwnedRun(
            status=0, group_empty=True, control=forged
        ),
    )
    monkeypatch.setattr(airlock, "_read_marker_state", lambda _path: ())
    monkeypatch.setattr(airlock, "_remove_disposable", shutil.rmtree)
    monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: ())

    terminal = airlock._execute_outer(
        layout,
        inventory,
        caller_args=("tests/test_leaf.py", mode),
        root_parent=tmp_path,
    )

    assert terminal.status == 0
    assert terminal.refusal is None
    assert terminal.certificate is None


@pytest.mark.parametrize("raw_status", (False, True, 1.5, "1"))
def test_inner_validates_raw_pytest_status_before_conversion(
    monkeypatch: pytest.MonkeyPatch,
    raw_status: object,
):
    airlock = _airlock()
    import pytest as real_pytest

    guard = types.SimpleNamespace(
        audit_before_pytest=lambda: None,
        restore_dispatcher_front=lambda: None,
        _CHECKOUT=os.fspath(REPO),
        _SHARED_PURELIB=os.fspath(SHARED_PURELIB),
        DISPATCHER=object(),
    )
    monkeypatch.setitem(sys.modules, "_maez_worktree_airlock_guard", guard)
    monkeypatch.setattr(real_pytest, "main", lambda *_a, **_k: raw_status)

    result = airlock._inner_main(("tests/test_leaf.py",))

    assert result.status == 86
    assert result.call_phase_observed is False


def test_inner_rejects_raw_status_without_invoking_conversion_side_effects(
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    import pytest as real_pytest

    conversions: list[str] = []

    class ConversionTrap:
        def __int__(self):
            conversions.append("int")
            return 0

        def __index__(self):
            conversions.append("index")
            return 0

        def __str__(self):
            conversions.append("str")
            return "0"

    guard = types.SimpleNamespace(
        audit_before_pytest=lambda: None,
        restore_dispatcher_front=lambda: None,
        _CHECKOUT=os.fspath(REPO),
        _SHARED_PURELIB=os.fspath(SHARED_PURELIB),
        DISPATCHER=object(),
    )
    monkeypatch.setitem(sys.modules, "_maez_worktree_airlock_guard", guard)
    monkeypatch.setattr(real_pytest, "main", lambda *_a, **_k: ConversionTrap())

    result = airlock._inner_main(("tests/test_leaf.py",))

    assert result.status == 86
    assert result.call_phase_observed is False
    assert conversions == []


@pytest.mark.parametrize("raw_status", (0, 1))
def test_inner_requires_completed_global_observer_lifecycle_for_every_status(
    monkeypatch: pytest.MonkeyPatch,
    raw_status: int,
):
    airlock = _airlock()
    import pytest as real_pytest

    violations: list[str] = []

    def violate(token: str) -> None:
        violations.append(token)
        raise RuntimeError(token)

    guard = types.SimpleNamespace(
        audit_before_pytest=lambda: None,
        restore_dispatcher_front=lambda: None,
        _CHECKOUT=os.fspath(REPO),
        _SHARED_PURELIB=os.fspath(SHARED_PURELIB),
        DISPATCHER=object(),
        _violate=violate,
    )
    monkeypatch.setitem(sys.modules, "_maez_worktree_airlock_guard", guard)
    monkeypatch.setattr(real_pytest, "main", lambda *_a, **_k: raw_status)

    result = airlock._inner_main(("tests/test_leaf.py",))

    assert result.status == 86
    assert result.call_phase_observed is False
    assert violations == ["airlock_import_provenance_violation"]


def test_inner_runner_keeps_control_and_lifecycle_state_out_of_main_module(
    tmp_path: Path,
):
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/test_runner_state.py": textwrap.dedent(
                """
                import __main__

                def test_runner_state_is_not_test_visible():
                    for name in ('control', 'status', 'call_phase_observed'):
                        assert not hasattr(__main__, name)
                """
            ),
        },
    )
    try:
        control = _run_prepared_inner(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_runner_state.py", "-q"),
        )
        assert control.status == 0
        assert control.call_phase_observed is True
    finally:
        airlock._remove_disposable(prepared.root)


def _airlock_plugin_for_unit_test(airlock, checkout: Path, shared: Path):
    def violate(token: str) -> None:
        raise RuntimeError(token)

    guard = types.SimpleNamespace(
        audit_before_pytest=lambda: None,
        restore_dispatcher_front=lambda: None,
        DISPATCHER=object(),
        _TRACKED_FILES=frozenset(),
        _violate=violate,
    )
    return airlock._AirlockPytestPlugin(
        guard=guard,
        checkout=checkout,
        shared_purelib=shared,
    )


def _bound_airlock_plugin_for_report_test(tmp_path: Path):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    checkout.mkdir()
    shared.mkdir()
    item_path = checkout / "test_leaf.py"
    item_path.write_text("def test_leaf():\n    assert True\n", encoding="utf-8")
    item = types.SimpleNamespace(path=item_path, nodeid="test_leaf.py::test_leaf")
    plugin = _airlock_plugin_for_unit_test(airlock, checkout, shared)
    plugin._bind_items((item,))
    return airlock, plugin, item


def _pytest_call_and_report(phase: str, nodeid: str):
    from _pytest.reports import TestReport
    from _pytest.runner import CallInfo

    call = CallInfo.from_call(lambda: None, when=phase)
    report = TestReport(
        nodeid=nodeid,
        location=("test_leaf.py", 0, "test_leaf"),
        keywords={},
        outcome="passed",
        longrepr=None,
        when=phase,
    )
    return call, report


def _finish_report_wrapper(plugin, item, call, report) -> None:
    wrapper = plugin.pytest_runtest_makereport(item, call)
    next(wrapper)
    with pytest.raises(StopIteration) as stopped:
        wrapper.send(report)
    assert stopped.value.value is report


@pytest.mark.parametrize("lookalike", ("call", "report"))
def test_plugin_makereport_rejects_lookalike_lifecycle_objects(
    tmp_path: Path,
    lookalike: str,
):
    _airlock_module, plugin, item = _bound_airlock_plugin_for_report_test(tmp_path)
    call, report = _pytest_call_and_report("setup", item.nodeid)
    if lookalike == "call":
        call = types.SimpleNamespace(when="setup")
    else:
        report = types.SimpleNamespace(when="setup", failed=False)
    wrapper = plugin.pytest_runtest_makereport(item, call)
    if lookalike == "call":
        with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
            next(wrapper)
        return
    next(wrapper)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        wrapper.send(report)


def test_plugin_makereport_rejects_exact_objects_in_out_of_order_phase(
    tmp_path: Path,
):
    _airlock_module, plugin, item = _bound_airlock_plugin_for_report_test(tmp_path)
    call, report = _pytest_call_and_report("call", item.nodeid)
    wrapper = plugin.pytest_runtest_makereport(item, call)
    next(wrapper)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        wrapper.send(report)


def test_plugin_report_lifecycle_accepts_exact_order_and_ignores_replay(
    tmp_path: Path,
):
    _airlock_module, plugin, item = _bound_airlock_plugin_for_report_test(tmp_path)
    for phase in ("setup", "call", "teardown"):
        call, report = _pytest_call_and_report(phase, item.nodeid)
        _finish_report_wrapper(plugin, item, call, report)
        plugin.pytest_runtest_logreport(report)
        plugin.pytest_runtest_logreport(report)

    assert plugin.call_phase_observed is True
    assert plugin.failure_observed is False


@pytest.mark.parametrize(
    ("failing", "expected_status"),
    ((False, 0), (True, 1)),
    ids=("passing-subtests", "failing-subtest"),
)
def test_plugin_real_subtests_complete_without_forging_top_level_lifecycle(
    tmp_path: Path,
    failing: bool,
    expected_status: int,
):
    source = textwrap.dedent(
        f"""
        import unittest

        class TestSubtests(unittest.TestCase):
            def test_values(self):
                for value in (1, 2):
                    with self.subTest(value=value):
                        if {failing!r} and value == 2:
                            self.assertEqual(value, 1)
                        else:
                            self.assertGreater(value, 0)
        """
    )
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/test_subtests.py": source,
        },
    )
    try:
        run = _run_prepared_inner_raw(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_subtests.py", "-q"),
        )
        markers = airlock._read_marker_state(prepared.violation_dir)
        assert run.status == expected_status, (
            run,
            markers,
            prepared.diagnostic.read_text(encoding="utf-8", errors="replace"),
        )
        control = airlock._parse_inner_control(run.control, run.status)

        assert control.status == expected_status
        assert control.call_phase_observed is True
        assert markers == ()
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("abort_shape", ("pytest-exit", "protocol-swallow"))
def test_plugin_partial_status_zero_run_never_certifies(
    tmp_path: Path,
    abort_shape: str,
):
    if abort_shape == "pytest-exit":
        conftest = ""
        middle = "import pytest\n\ndef test_b():\n    pytest.exit('stop', returncode=0)\n"
    else:
        conftest = textwrap.dedent(
            """
            def pytest_runtest_protocol(item):
                if item.name == 'test_b':
                    return True
                return None
            """
        )
        middle = "def test_b():\n    assert False\n"
    suite = "def test_a():\n    assert True\n\n" + middle
    if abort_shape == "pytest-exit":
        suite += "\ndef test_c():\n    assert False\n"
    files = {
        "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
            encoding="utf-8"
        ),
        "tests/test_partial.py": suite,
    }
    if conftest:
        files["tests/conftest.py"] = conftest
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files=files,
    )
    try:
        run = _run_prepared_inner_raw(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_partial.py", "-q"),
        )
        markers = airlock._read_marker_state(prepared.violation_dir)

        assert run.status == 86
        assert "airlock_inner_complete:86" in run.control.decode("ascii")
        assert set(markers) == {"airlock_import_provenance_violation"}
    finally:
        airlock._remove_disposable(prepared.root)


def test_plugin_makereport_refuses_next_phase_before_prior_report_is_logged(
    tmp_path: Path,
):
    _airlock_module, plugin, item = _bound_airlock_plugin_for_report_test(tmp_path)
    setup_call, setup_report = _pytest_call_and_report("setup", item.nodeid)
    _finish_report_wrapper(plugin, item, setup_call, setup_report)
    call, report = _pytest_call_and_report("call", item.nodeid)
    wrapper = plugin.pytest_runtest_makereport(item, call)
    next(wrapper)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        wrapper.send(report)


def _pytest_collect_report():
    from _pytest.reports import CollectReport

    return CollectReport(
        nodeid="tests/test_leaf.py",
        outcome="passed",
        longrepr=None,
        result=[],
    )


def test_plugin_rejects_published_collect_report_without_created_identity(
    tmp_path: Path,
):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    checkout.mkdir()
    shared.mkdir()
    plugin = _airlock_plugin_for_unit_test(airlock, checkout, shared)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        plugin.pytest_collectreport(_pytest_collect_report())


def test_plugin_rejects_replayed_published_collect_report(tmp_path: Path):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    checkout.mkdir()
    shared.mkdir()
    plugin = _airlock_plugin_for_unit_test(airlock, checkout, shared)
    report = _pytest_collect_report()
    wrapper = plugin.pytest_make_collect_report(object())
    next(wrapper)
    with pytest.raises(StopIteration):
        wrapper.send(report)

    plugin.pytest_collectreport(report)
    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        plugin.pytest_collectreport(report)


def test_plugin_call_and_failure_state_is_read_only_and_fake_reports_are_ignored(
    tmp_path: Path,
):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    checkout.mkdir()
    shared.mkdir()
    plugin = _airlock_plugin_for_unit_test(airlock, checkout, shared)

    with pytest.raises(AttributeError):
        plugin.call_phase_observed = True
    with pytest.raises(AttributeError):
        plugin.failure_observed = True
    plugin.pytest_runtest_logreport(
        types.SimpleNamespace(when="call", failed=False)
    )

    assert plugin.call_phase_observed is False
    assert plugin.failure_observed is False


@pytest.mark.parametrize(
    ("mode", "conftest"),
    (
        (
            "--setup-only",
            textwrap.dedent(
                """
                def pytest_configure(config):
                    for plugin in config.pluginmanager.get_plugins():
                        if type(plugin).__name__ == '_AirlockPytestPlugin':
                            try:
                                plugin.call_phase_observed = True
                            except (AttributeError, TypeError):
                                pass
                """
            ),
        ),
        (
            "--collect-only",
            textwrap.dedent(
                """
                import types

                def pytest_collection_modifyitems(config, items):
                    del items
                    for plugin in config.pluginmanager.get_plugins():
                        if type(plugin).__name__ == '_AirlockPytestPlugin':
                            plugin.pytest_runtest_logreport(
                                types.SimpleNamespace(when='call', failed=False)
                            )
                """
            ),
        ),
        (
            "--setup-only",
            textwrap.dedent(
                """
                import pytest

                @pytest.hookimpl(tryfirst=True)
                def pytest_runtest_logreport(report):
                    if report.when == 'setup':
                        report.when = 'call'
                """
            ),
        ),
    ),
    ids=("direct-assignment", "fake-report", "mutated-setup-report"),
)
def test_plugin_diagnostic_modes_reject_test_reported_call_phase(
    tmp_path: Path,
    mode: str,
    conftest: str,
):
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    try:
        control = _run_prepared_inner(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_leaf.py", mode, "-q"),
        )
        assert control.status == 0
        assert control.call_phase_observed is False
    finally:
        airlock._remove_disposable(prepared.root)


def test_plugin_rejects_extra_plugin_object_exported_from_tracked_conftest(
    tmp_path: Path,
):
    conftest = textwrap.dedent(
        """
        class ExtraPlugin:
            pass

        def pytest_configure(config):
            config.pluginmanager.register(
                ExtraPlugin(), 'extra-from-conftest-instance'
            )
        """
    )
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    try:
        run = _run_prepared_inner_raw(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_leaf.py", "-q"),
        )
        markers = airlock._read_marker_state(prepared.violation_dir)

        assert run.status == 86
        assert set(markers) == {"airlock_import_provenance_violation"}
    finally:
        airlock._remove_disposable(prepared.root)


def test_plugin_failure_fact_survives_report_and_exit_status_mutation(
    tmp_path: Path,
):
    conftest = textwrap.dedent(
        """
        import pytest

        @pytest.hookimpl(tryfirst=True)
        def pytest_runtest_logreport(report):
            report.outcome = 'passed'

        @pytest.hookimpl(trylast=True)
        def pytest_sessionfinish(session):
            session.exitstatus = 0
        """
    )
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_failure.py": "def test_failure():\n    assert 2 + 2 == 5\n",
        },
    )
    try:
        control = _run_prepared_inner(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_failure.py", "-q"),
        )
        assert control.status == 1
        assert control.call_phase_observed is True
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize(
    ("source", "expected_status"),
    (
        (
            "import pytest\n\ndef test_skip_in_call():\n    pytest.skip('skip')\n",
            0,
        ),
        (
            "import unittest\n\nclass TestSkip(unittest.TestCase):\n"
            "    def test_skip(self):\n        self.skipTest('skip')\n",
            0,
        ),
        (
            "import unittest\n\ndef test_plain_unittest_skip():\n"
            "    raise unittest.SkipTest('skip')\n",
            0,
        ),
        (
            "import pytest\n\n@pytest.mark.xfail\ndef test_expected_failure():\n"
            "    assert False\n",
            0,
        ),
        (
            "import pytest\n\ndef test_imperative_xfail():\n"
            "    pytest.xfail('expected')\n",
            0,
        ),
        (
            "import pytest\n\n@pytest.mark.xfail\ndef test_non_strict_xpass():\n"
            "    assert True\n",
            0,
        ),
        (
            "import pytest\n\n@pytest.mark.xfail(strict=True)\n"
            "def test_strict_xpass():\n    assert True\n",
            1,
        ),
    ),
    ids=(
        "call-skip",
        "unittest-call-skip",
        "plain-unittest-skip",
        "expected-xfail",
        "imperative-xfail",
        "non-strict-xpass",
        "strict-xpass",
    ),
)
def test_plugin_failure_truth_preserves_skip_and_xfail_semantics(
    tmp_path: Path,
    source: str,
    expected_status: int,
):
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/test_outcome.py": source,
        },
    )
    try:
        control = _run_prepared_inner(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_outcome.py", "-q"),
        )

        assert control.status == expected_status
        assert control.call_phase_observed is True
        assert airlock._read_marker_state(prepared.violation_dir) == ()
    finally:
        airlock._remove_disposable(prepared.root)


def test_plugin_rejects_firstresult_report_that_launders_failing_call(
    tmp_path: Path,
):
    conftest = textwrap.dedent(
        """
        import pytest
        from _pytest.reports import TestReport

        @pytest.hookimpl(tryfirst=True)
        def pytest_runtest_makereport(item, call):
            report = TestReport.from_item_and_call(item, call)
            if call.when == 'call' and call.excinfo is not None:
                report.outcome = 'passed'
                report.longrepr = None
            return report
        """
    )
    airlock, layout, inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_failure.py": "def test_failure():\n    assert 2 + 2 == 5\n",
        },
    )
    try:
        airlock._remove_disposable(prepared.root)
        terminal = airlock._execute_outer(
            layout,
            inventory,
            caller_args=("tests/test_failure.py", "-q"),
            root_parent=tmp_path,
        )

        assert terminal.status == 86
        assert terminal.refusal == "airlock_import_provenance_violation"
        assert terminal.certificate is None
    finally:
        if prepared.root.exists():
            airlock._remove_disposable(prepared.root)


def _synthetic_plugin_module(
    name: str,
    origin: Path,
    *,
    spec_origin: Path | None = None,
) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = os.fspath(origin)
    module.__spec__ = importlib.util.spec_from_file_location(
        name, spec_origin or origin
    )
    assert module.__spec__ is not None
    module.__loader__ = module.__spec__.loader
    module.__package__ = module.__spec__.parent
    return module


@pytest.mark.parametrize(
    "plane",
    (
        "file",
        "spec-origin",
        "module-path",
        "spec-search",
        "module-path-only",
        "spec-search-only",
    ),
)
def test_plugin_origin_rejects_every_disagreeing_origin_plane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    plane: str,
):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    outside = tmp_path / "outside"
    checkout.mkdir()
    shared.mkdir()
    outside.mkdir()
    allowed_file = shared / "pytest_plugin.py"
    foreign_file = outside / "pytest_plugin.py"
    allowed_file.write_text("\n", encoding="utf-8")
    foreign_file.write_text("\n", encoding="utf-8")
    file_origin = foreign_file if plane == "file" else allowed_file
    spec_origin = foreign_file if plane == "spec-origin" else allowed_file
    module = _synthetic_plugin_module(
        "anyio.pytest_plugin", file_origin, spec_origin=spec_origin
    )
    assert module.__spec__ is not None
    if plane in {"module-path", "module-path-only"}:
        module.__path__ = [os.fspath(foreign_file.parent)]
    if plane in {"spec-search", "spec-search-only"}:
        module.__spec__.submodule_search_locations = [
            os.fspath(foreign_file.parent)
        ]
    if plane == "module-path":
        module.__spec__.submodule_search_locations = [
            os.fspath(allowed_file.parent)
        ]
    if plane == "spec-search":
        module.__path__ = [os.fspath(allowed_file.parent)]
    monkeypatch.setitem(sys.modules, "anyio.pytest_plugin", module)
    plugin = _airlock_plugin_for_unit_test(airlock, checkout, shared)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        plugin.pytest_plugin_registered(module, "anyio.pytest_plugin", None)


def test_plugin_origin_requires_exact_loaded_module_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    checkout.mkdir()
    shared.mkdir()
    origin = shared / "pytest_plugin.py"
    origin.write_text("\n", encoding="utf-8")
    loaded = _synthetic_plugin_module("anyio.pytest_plugin", origin)
    impostor = _synthetic_plugin_module("anyio.pytest_plugin", origin)
    monkeypatch.setitem(sys.modules, "anyio.pytest_plugin", loaded)
    plugin = _airlock_plugin_for_unit_test(airlock, checkout, shared)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        plugin.pytest_plugin_registered(impostor, "anyio.pytest_plugin", None)


def test_plugin_origin_requires_object_type_exported_by_loaded_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    checkout.mkdir()
    shared.mkdir()
    origin = shared / "synthetic.py"
    origin.write_text("\n", encoding="utf-8")
    module = _synthetic_plugin_module("_pytest.synthetic", origin)

    class Impostor:
        pass

    Impostor.__module__ = "_pytest.synthetic"
    module.Impostor = object()
    monkeypatch.setitem(sys.modules, "_pytest.synthetic", module)
    plugin = _airlock_plugin_for_unit_test(airlock, checkout, shared)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        plugin.pytest_plugin_registered(Impostor(), "synthetic", None)


def test_registered_plugin_origin_is_revalidated_during_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    airlock = _airlock()
    checkout = tmp_path / "checkout"
    shared = tmp_path / "shared"
    outside = tmp_path / "outside"
    checkout.mkdir()
    shared.mkdir()
    outside.mkdir()
    origin = shared / "pytest_plugin.py"
    foreign = outside / "pytest_plugin.py"
    origin.write_text("\n", encoding="utf-8")
    foreign.write_text("\n", encoding="utf-8")
    module = _synthetic_plugin_module("anyio.pytest_plugin", origin)
    monkeypatch.setitem(sys.modules, "anyio.pytest_plugin", module)
    plugin = _airlock_plugin_for_unit_test(airlock, checkout, shared)
    plugin.pytest_plugin_registered(module, "anyio.pytest_plugin", None)
    assert module.__spec__ is not None
    module.__spec__.origin = os.fspath(foreign)

    with pytest.raises(RuntimeError, match="airlock_import_provenance_violation"):
        plugin.pytest_configure(None)


def test_registered_plugin_module_identity_is_revalidated_in_real_lifecycle(
    tmp_path: Path,
):
    conftest = textwrap.dedent(
        """
        import sys
        import anyio.pytest_plugin as anyio_plugin

        def pytest_collection_finish(session):
            del session
            anyio_plugin.__name__ = '_pytest.rogue'
            anyio_plugin.__spec__.name = '_pytest.rogue'
            anyio_plugin.__package__ = '_pytest'
            sys.modules['_pytest.rogue'] = anyio_plugin
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    try:
        run = _run_prepared_inner_raw(
            airlock,
            prepared,
            layout.checkout,
            ("tests/test_leaf.py", "-q"),
        )
        markers = airlock._read_marker_state(prepared.violation_dir)

        assert run.status in {*range(1, 7), airlock.AIRLOCK_STATUS}
        assert markers
        assert set(markers) == {"airlock_import_provenance_violation"}
    finally:
        airlock._remove_disposable(prepared.root)


def test_late_guarded_path_state_drift_is_rechecked_in_real_lifecycle(
    tmp_path: Path,
):
    conftest = textwrap.dedent(
        """
        import sys

        def pytest_collection_finish(session):
            del session
            list.append(sys.path, '/foreign-airlock-path')
        """
    )
    airlock, layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    try:
        run = _run_prepared_inner_raw(
            airlock,
            prepared,
            layout.checkout,
            ("tests/test_leaf.py", "-q"),
        )
        markers = airlock._read_marker_state(prepared.violation_dir)

        assert run.status in {*range(1, 7), airlock.AIRLOCK_STATUS}
        assert markers
        assert set(markers) == {"airlock_path_provenance_violation"}
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("boundary", ("collection", "teardown"))
def test_collection_item_retarget_is_caught_at_late_and_final_boundaries(
    tmp_path: Path,
    boundary: str,
):
    hook = (
        "pytest_collection_modifyitems"
        if boundary == "collection"
        else "pytest_runtest_teardown"
    )
    conftest = textwrap.dedent(
        f"""
        from pathlib import Path
        import pytest

        @pytest.hookimpl(trylast=True)
        def {hook}({"config, items" if boundary == "collection" else "item"}):
            {"for item in items:" if boundary == "collection" else ""}
                {"item" if boundary == "collection" else "item"}.path = Path('/etc/hosts')
        """
    )
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    try:
        run = _run_prepared_inner_raw(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_leaf.py", "-q"),
        )
        assert run.status in {*range(1, 7), airlock.AIRLOCK_STATUS}
        markers = airlock._read_marker_state(prepared.violation_dir)
        assert markers, (
            run,
            prepared.diagnostic.read_text(encoding="utf-8", errors="replace"),
        )
        assert set(markers) == {"airlock_collection_escape"}
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("mutation", ("remove", "reorder"))
def test_rewrite_hook_identity_and_order_are_reproved_after_conftest_mutation(
    tmp_path: Path,
    mutation: str,
):
    mutation_code = (
        "list.remove(sys.meta_path, hook)"
        if mutation == "remove"
        else "list.__setitem__(sys.meta_path, slice(None), [hook, guard.DISPATCHER, *rest])"
    )
    conftest = textwrap.dedent(
        f"""
        import sys

        def pytest_collection_finish(session):
            del session
            guard = sys.modules['_maez_worktree_airlock_guard']
            hooks = [finder for finder in sys.meta_path
                     if type(finder).__module__ == '_pytest.assertion.rewrite'
                     and type(finder).__name__ == 'AssertionRewritingHook']
            assert len(hooks) == 1
            hook = hooks[0]
            rest = [finder for finder in sys.meta_path
                    if finder is not hook and finder is not guard.DISPATCHER]
            {mutation_code}
        """
    )
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    try:
        run = _run_prepared_inner_raw(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_leaf.py", "-q"),
        )
        assert run.status in {*range(1, 7), airlock.AIRLOCK_STATUS}
        markers = airlock._read_marker_state(prepared.violation_dir)
        assert markers
        assert set(markers) == {"airlock_import_provenance_violation"}
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("boundary", ("unconfigure", "cleanup"))
@pytest.mark.parametrize("mutation", ("remove", "reorder"))
def test_rewrite_hook_identity_and_order_are_reproved_at_final_cleanup(
    tmp_path: Path,
    boundary: str,
    mutation: str,
):
    mutation_code = (
        "list.remove(sys.meta_path, hook)"
        if mutation == "remove"
        else "list.__setitem__(sys.meta_path, slice(None), [hook, guard.DISPATCHER, *rest])"
    )
    registration = (
        "def pytest_unconfigure(config):\n"
        "    del config\n"
        "    _mutate_rewrite_hook()\n"
        if boundary == "unconfigure"
        else "def pytest_configure(config):\n"
        "    config.add_cleanup(_mutate_rewrite_hook)\n"
    )
    conftest = (
        textwrap.dedent(
            f"""
        import sys

        def _mutate_rewrite_hook():
            guard = sys.modules['_maez_worktree_airlock_guard']
            hooks = [finder for finder in sys.meta_path
                     if type(finder).__module__ == '_pytest.assertion.rewrite'
                     and type(finder).__name__ == 'AssertionRewritingHook']
            assert len(hooks) == 1
            hook = hooks[0]
            rest = [finder for finder in sys.meta_path
                    if finder is not hook and finder is not guard.DISPATCHER]
            {mutation_code}
        """
        )
        + "\n"
        + registration
    )
    airlock, _layout, _inventory, prepared = _task3_prepared(
        tmp_path,
        dependency_purelib=SHARED_PURELIB,
        extra_files={
            "scripts/dev/worktree_test_airlock.py": AIRLOCK_SOURCE.read_text(
                encoding="utf-8"
            ),
            "tests/conftest.py": conftest,
            "tests/test_leaf.py": "def test_leaf():\n    assert True\n",
        },
    )
    try:
        run = _run_prepared_inner_raw(
            airlock,
            prepared,
            tmp_path / "checkout",
            ("tests/test_leaf.py", "-q"),
        )
        markers = airlock._read_marker_state(prepared.violation_dir)
        assert run.status in {*range(1, 7), airlock.AIRLOCK_STATUS}
        assert markers, (
            run,
            prepared.diagnostic.read_text(encoding="utf-8", errors="replace"),
        )
        assert set(markers) == {"airlock_import_provenance_violation"}
    finally:
        airlock._remove_disposable(prepared.root)


@pytest.mark.parametrize("phase", ("collection", "call"))
@pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
def test_real_outer_signal_mid_pytest_never_certifies_and_finalizes(
    phase: str,
    signum: int,
):
    airlock = _airlock()
    shared_purelib = Path(
        subprocess.run(
            [
                os.fspath(SHARED_PYTHON),
                "-I",
                "-S",
                "-B",
                "-c",
                "import sysconfig;print(sysconfig.get_path('purelib'))",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    before_pth = airlock._snapshot_pth(shared_purelib)
    selector = (
        _SIGNAL_COLLECTION_NODE if phase == "collection" else _SIGNAL_CALL_NODE
    )
    process = subprocess.Popen(
        [
            os.fspath(SHARED_PYTHON),
            "-I",
            "-S",
            "-B",
            os.fspath(AIRLOCK_SOURCE),
            "pytest",
            "--",
            selector,
            "-q",
        ],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    owned_pattern = f"maez-airlock-{process.pid}-*"
    observed_root: Path | None = None
    inner_pid: int | None = None
    inner_pgid: int | None = None
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            for candidate in Path("/tmp").glob(owned_pattern):
                ready = candidate / f"signal-{phase}-ready"
                if ready.exists():
                    observed_root = candidate
                    inner_pid, inner_pgid = (
                        int(part)
                        for part in ready.read_text(encoding="ascii").strip().split(":")
                    )
                    break
            if observed_root is not None:
                break
            if process.poll() is not None:
                break
            time.sleep(0.02)
        assert observed_root is not None
        assert inner_pid is not None and inner_pgid == inner_pid
        assert process.poll() is None
        os.kill(process.pid, signum)
        stdout, stderr = process.communicate(timeout=10)

        assert process.returncode == 86
        assert stdout == ""
        assert "MAEZ_AIRLOCK_CERTIFIED" not in stdout + stderr
        assert stderr.rstrip().endswith("airlock_child_setup_failed")
        assert airlock._snapshot_pth(shared_purelib) == before_pth
        assert not Path(f"/proc/{inner_pid}").exists()
        assert not observed_root.exists()
        assert not tuple(Path("/tmp").glob(owned_pattern))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        _cleanup_owned_outer_test_run(airlock, process.pid)


def test_real_outer_refuses_when_successful_test_leaves_detached_descendant():
    airlock = _airlock()
    shared_purelib = Path(
        subprocess.run(
            [
                os.fspath(SHARED_PYTHON),
                "-I",
                "-S",
                "-B",
                "-c",
                "import sysconfig;print(sysconfig.get_path('purelib'))",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    before_pth = airlock._snapshot_pth(shared_purelib)
    process = subprocess.Popen(
        [
            os.fspath(SHARED_PYTHON),
            "-I",
            "-S",
            "-B",
            os.fspath(AIRLOCK_SOURCE),
            "pytest",
            "--",
            _DETACHED_DESCENDANT_NODE,
            "-q",
        ],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    sentinel = Path(f"/tmp/maez-airlock-detached-{process.pid}")
    child_pid: int | None = None
    child_pgid: int | None = None
    prepared_root: Path | None = None
    try:
        stdout, stderr = process.communicate(timeout=15)
        assert sentinel.exists()
        raw_pid, raw_pgid, raw_root = sentinel.read_text(
            encoding="utf-8"
        ).strip().split(":", 2)
        child_pid = int(raw_pid)
        child_pgid = int(raw_pgid)
        prepared_root = Path(raw_root)

        assert process.returncode == 86
        assert stdout == ""
        assert "MAEZ_AIRLOCK_CERTIFIED" not in stdout + stderr
        assert "1 passed" in stderr
        assert stderr.rstrip().endswith("airlock_cleanup_incomplete")
        assert Path(f"/proc/{child_pid}").exists()
        assert airlock._snapshot_pth(shared_purelib) == before_pth
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        pidfd: int | None = None
        if child_pid is not None and Path(f"/proc/{child_pid}").exists():
            process_path = Path(f"/proc/{child_pid}")
            pidfd = os.pidfd_open(child_pid)
            arguments = (process_path / "cmdline").read_bytes().split(b"\0")
            assert process_path.stat().st_uid == os.getuid()
            assert child_pgid == child_pid == os.getpgid(child_pid)
            assert prepared_root is not None
            expected_python = os.fsencode(prepared_root / "venv/bin/python")
            assert expected_python in arguments
            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and process_path.exists():
                time.sleep(0.01)
            assert not process_path.exists()
        if pidfd is not None:
            os.close(pidfd)
        if sentinel.exists():
            info = sentinel.lstat()
            assert stat.S_ISREG(info.st_mode)
            assert info.st_uid == os.getuid()
            assert info.st_nlink == 1
            assert stat.S_IMODE(info.st_mode) == 0o600
            sentinel.unlink()
        _cleanup_owned_outer_test_run(airlock, process.pid)
        assert airlock._snapshot_pth(shared_purelib) == before_pth


@pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
def test_real_outer_signal_escalates_when_inner_ignores_signal(signum: int):
    airlock = _airlock()
    shared_purelib = Path(
        subprocess.run(
            [
                os.fspath(SHARED_PYTHON),
                "-I",
                "-S",
                "-B",
                "-c",
                "import sysconfig;print(sysconfig.get_path('purelib'))",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    before_pth = airlock._snapshot_pth(shared_purelib)
    process = subprocess.Popen(
        [
            os.fspath(SHARED_PYTHON),
            "-I",
            "-S",
            "-B",
            os.fspath(AIRLOCK_SOURCE),
            "pytest",
            "--",
            _SIGNAL_IGNORE_NODE,
            "-q",
        ],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    owned_pattern = f"maez-airlock-{process.pid}-*"
    observed_root: Path | None = None
    inner_pid: int | None = None
    inner_pgid: int | None = None
    timed_out = False
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            for candidate in Path("/tmp").glob(owned_pattern):
                ready = candidate / "signal-ignore-ready"
                if ready.exists():
                    observed_root = candidate
                    inner_pid, inner_pgid = (
                        int(part)
                        for part in ready.read_text(encoding="ascii").strip().split(":")
                    )
                    break
            if observed_root is not None or process.poll() is not None:
                break
            time.sleep(0.02)
        assert observed_root is not None
        assert inner_pid is not None and inner_pgid == inner_pid
        started = time.monotonic()
        os.kill(process.pid, signum)
        try:
            stdout, stderr = process.communicate(timeout=2.0)
        except subprocess.TimeoutExpired:
            timed_out = True
            raise AssertionError("airlock outer hung on a signal-ignoring child")

        assert time.monotonic() - started < 1.5
        assert process.returncode == 86
        assert stdout == ""
        assert "MAEZ_AIRLOCK_CERTIFIED" not in stdout + stderr
        assert stderr.rstrip().endswith("airlock_child_setup_failed")
        assert airlock._snapshot_pth(shared_purelib) == before_pth
        assert not Path(f"/proc/{inner_pid}").exists()
        assert not observed_root.exists()
        assert not tuple(Path("/tmp").glob(owned_pattern))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        _cleanup_owned_outer_test_run(airlock, process.pid)
        if timed_out:
            assert airlock._snapshot_pth(shared_purelib) == before_pth


if __name__ == "__main__":
    unittest.main()
