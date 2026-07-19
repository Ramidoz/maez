from __future__ import annotations

import ctypes
import importlib.util
import itertools
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import textwrap
import time
import types
import unittest
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
AIRLOCK_SOURCE = REPO / "scripts" / "dev" / "worktree_test_airlock.py"
SHARED_PYTHON = Path("/home/rohit/maez/.venv/bin/python")


def _airlock():
    spec = importlib.util.spec_from_file_location("_airlock_under_test", AIRLOCK_SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
            "tests/test_worktree_airlock_imports.py",
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


def test_checkout_identity_discovers_tracked_inventory_from_absolute_git():
    airlock = _airlock()
    checkout = airlock._resolve_checkout(AIRLOCK_SOURCE, REPO)
    inventory = airlock._discover_inventory(checkout)

    assert checkout == REPO
    assert len(inventory.head) == 40
    assert inventory.tracked_python_files == tuple(
        sorted(inventory.tracked_python_files, key=lambda path: path.as_posix())
    )
    assert Path("scripts/dev/bench_baseline.py") in inventory.tracked_python_files
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


def test_task2_module_description_names_the_landed_airlock():
    airlock = _airlock()

    assert "disposable no-pip interpreter is now built" in airlock.__doc__
    assert "Runtime import provenance remains a subsequent task" in airlock.__doc__
    assert "land in subsequent tasks" not in airlock.__doc__
    assert "this first slice" not in airlock.__doc__


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


def test_disposable_runner_creates_only_one_private_diagnostic(tmp_path: Path):
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
        result = subprocess.run(
            [os.fspath(prepared.python), "-I", "-B", os.fspath(prepared.runner)],
            cwd=REPO,
            env=prepared.environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 86
        assert result.stdout.splitlines() == [
            "airlock_inner_noncertifying",
            "airlock_inner_complete:86",
        ]
        info = prepared.diagnostic.stat()
        assert stat.S_ISREG(info.st_mode)
        assert stat.S_IMODE(info.st_mode) == 0o600
        assert info.st_nlink == 1
        assert "MAEZ_AIRLOCK_CERTIFIED" not in prepared.runner.read_text(
            encoding="utf-8"
        )
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
    code = (
        "import json,site,sys;"
        f"site.addsitedir({os.fspath(prepared.purelib)!r});"
        f"site.addsitedir({os.fspath(prepared.purelib)!r});"
        "m=sys.modules['_maez_worktree_airlock_guard'];"
        "print(json.dumps([m.__file__,m.AIRLOCK_READY,m.AIRLOCK_LOAD_COUNT]))"
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
        assert json.loads(result.stdout) == [os.fspath(prepared.guard), True, 1]
    finally:
        airlock._remove_disposable(prepared.root)


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
    roots_before = set(Path("/tmp").glob("maez-airlock-*"))
    process = subprocess.Popen(
        [
            os.fspath(SHARED_PYTHON),
            "-I",
            "-S",
            "-B",
            os.fspath(AIRLOCK_SOURCE),
            "pytest",
            "--",
            "tests/test_worktree_airlock_imports.py",
        ],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    observed_roots: set[Path] = set()
    while process.poll() is None:
        observed_roots.update(set(Path("/tmp").glob("maez-airlock-*")) - roots_before)
        time.sleep(0.002)
    stdout, stderr = process.communicate(timeout=2)
    after = airlock._snapshot_pth(shared_purelib)

    assert process.returncode == 86
    assert stdout == ""
    assert stderr.strip() == "airlock_dependency_unavailable"
    assert observed_roots
    assert all(not root.exists() for root in observed_roots)
    assert before == after


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


def test_owned_group_cleanup_finds_stubborn_grandchild_with_odd_comm(tmp_path: Path):
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
        assert result.group_empty is True
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
        token = module._execute_outer(
            layout, inventory, root_parent=pathlib.Path({os.fspath(tmp_path)!r})
        )
        pathlib.Path({os.fspath(outcome)!r}).write_text(token, encoding='utf-8')
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


def test_outer_task2_terminal_order_is_fixed_and_cleanup_is_unconditional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    airlock = _airlock()
    layout = _synthetic_layout(tmp_path)
    inventory = _inventory_for(layout.checkout)
    prepared = types.SimpleNamespace(
        root=tmp_path / "root",
        python=tmp_path / "root/venv/bin/python",
        runner=tmp_path / "root/inner_runner.py",
        environment={},
        violation_dir=tmp_path / "root/violations",
    )
    events: list[str] = []
    snapshots = iter((("before",), ("before",)))

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
        lambda _root: events.append("remove"),
    )

    token = airlock._execute_outer(layout, inventory, root_parent=tmp_path)

    assert token == "airlock_dependency_unavailable"
    assert events == ["snapshot", "prepare", "run", "markers", "remove", "snapshot"]


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
        environment={},
        violation_dir=tmp_path / "violations",
    )
    snapshots = iter((("before",), ("after",)))
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

    assert (
        airlock._execute_outer(layout, inventory, root_parent=tmp_path)
        == "airlock_shared_environment_changed"
    )


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
        environment={},
        violation_dir=tmp_path / "violations",
    )
    snapshots = iter((("same",), ("same",)))
    monkeypatch.setattr(airlock, "_snapshot_pth", lambda _path: next(snapshots))
    monkeypatch.setattr(airlock, "_prepare_disposable", lambda *_a, **_k: prepared)
    monkeypatch.setattr(
        airlock,
        "_run_owned_command",
        lambda *_a, **_k: airlock.OwnedRun(status=86, group_empty=False),
    )
    monkeypatch.setattr(airlock, "_read_marker_state", lambda _path: ())
    monkeypatch.setattr(airlock, "_remove_disposable", lambda _root: None)

    assert (
        airlock._execute_outer(layout, inventory, root_parent=tmp_path)
        == "airlock_cleanup_incomplete"
    )


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


if __name__ == "__main__":
    unittest.main()
