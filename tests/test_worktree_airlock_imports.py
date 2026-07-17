from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import textwrap
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


if __name__ == "__main__":
    unittest.main()
