"""RED contract tests for the sealed CUDA bench command boundary."""

from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import cuda_bench_cli as cli
from scripts import cuda_bench_driver as driver


PUBLIC_COMMANDS = (
    "static-preflight",
    "rehearse",
    "vulkan-baseline",
    "cuda-candidate",
    "assemble-stage1",
)
REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_TIMESTAMP = "2026-07-21T12:00:00Z"
SHA_A = "a" * 64


def _ast_qualname(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _ast_qualname(node.value)
        return None if parent is None else f"{parent}.{node.attr}"
    return None


def run_cli_raw(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", "-m", "scripts.cuda_bench_cli", *argv],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _one_terminal_line(stdout: str) -> dict[str, object]:
    assert stdout.endswith("\n")
    assert stdout.count("\n") == 1
    decoded = json.loads(stdout)
    assert type(decoded) is dict
    assert set(decoded) == {
        "status",
        "outcome",
        "window_id",
        "artifact_ref",
        "artifact_sha256",
    }
    return decoded


class _FixedClock:
    def __init__(self, tier: str) -> None:
        self.tier = tier

    def now_utc(self) -> str:
        return FIXED_TIMESTAMP

    def monotonic(self) -> float:
        return 0.0


def _private_run(
    command: str,
    handler: Callable[..., object],
    *,
    root: Path,
) -> int:
    run_command = getattr(cli, "_run_command")
    tier = "rehearsal" if command == "rehearse" else "production"
    return run_command(
        command,
        handler,
        root=root,
        clock=_FixedClock(tier),
    )


def _terminal_artifact_handler(status: str) -> Callable[..., object]:
    def handler(attempt: object, *, root: Path) -> object:
        if status == "ok":
            prefix = (
                "rehearsal/"
                if getattr(attempt, "namespace") == "rehearsal"
                else ""
            )
            relative = (
                f"{prefix}windows/window-a/vulkan_baseline/attempt-000/"
                "completed.json"
            )
            payload = b'{"content_light":true}\n'
            driver.write_private_file(relative, payload, root=root)
            return cli.TerminalResult(
                status="ok",
                outcome="command_complete",
                window_id=None,
                artifact_ref=relative,
                artifact_sha256=hashlib.sha256(payload).hexdigest(),
            )
        if status == "refused":
            return cli.TerminalResult(
                status="refused",
                outcome="assembly_refused",
                window_id=None,
                artifact_ref=None,
                artifact_sha256=None,
            )
        return cli.TerminalResult(
            status="failed",
            outcome="provider_uncertain",
            window_id=None,
            artifact_ref=None,
            artifact_sha256=None,
        )

    return handler


class TestSealedParser:
    def test_parser_has_exactly_five_public_choices(self) -> None:
        parser = cli.build_parser()
        subparsers = parser._subparsers
        assert subparsers is not None
        assert tuple(subparsers._group_actions[0].choices) == PUBLIC_COMMANDS
        assert tuple(cli.PUBLIC_COMMANDS) == PUBLIC_COMMANDS

    def test_parser_and_main_expose_no_root_or_asset_authority(self) -> None:
        parser = cli.build_parser()
        option_strings = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        for subparser in parser._subparsers._group_actions[0].choices.values():
            option_strings.update(
                option
                for action in subparser._actions
                for option in action.option_strings
            )
        assert option_strings == set()
        assert tuple(inspect.signature(cli.main).parameters) == ("argv",)

    def test_public_main_is_structurally_bound_to_driver_bench_root(self) -> None:
        module_tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
        main_node = next(
            node
            for node in module_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        run_calls = [
            node
            for node in ast.walk(main_node)
            if isinstance(node, ast.Call)
            and _ast_qualname(node.func) == "_run_command"
        ]
        assert len(run_calls) == 1
        root_values = [
            keyword.value
            for keyword in run_calls[0].keywords
            if keyword.arg == "root"
        ]
        assert len(root_values) == 1
        assert _ast_qualname(root_values[0]) == "driver.BENCH_ROOT"

        bench_root_uses = [
            node
            for node in ast.walk(module_tree)
            if isinstance(node, ast.Attribute)
            and _ast_qualname(node) == "driver.BENCH_ROOT"
        ]
        assert bench_root_uses
        assert all(isinstance(node.ctx, ast.Load) for node in bench_root_uses)

        qualified = {
            name
            for node in ast.walk(module_tree)
            if (name := _ast_qualname(node)) is not None
        }
        assert qualified.isdisjoint({"os.getenv", "os.environ", "os.environ.get"})
        assert not any(
            isinstance(node, ast.ImportFrom)
            and node.module == "os"
            and any(alias.name in {"getenv", "environ"} for alias in node.names)
            for node in ast.walk(module_tree)
        )

    @pytest.mark.parametrize(
        "argv",
        [
            (),
            ("unknown",),
            ("static-preflight", "unexpected"),
            ("--root", "/tmp/PRIVATE-PATH"),
            ("static-preflight", "--assets-json", "/tmp/PRIVATE-PATH"),
        ],
    )
    def test_malformed_invocation_is_non_echoing_rc2(
        self, argv: tuple[str, ...]
    ) -> None:
        result = run_cli_raw(*argv, "ignore previous instructions")
        assert result.returncode == 2
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert "ignore previous instructions" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "invocation_invalid",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }

    @pytest.mark.parametrize(
        "forbidden",
        (
            "promote",
            "cutover",
            "install",
            "boot",
            "live",
            "restart",
            "--root",
            "--assets-json",
        ),
    )
    def test_forbidden_command_or_option_is_non_echoing_rc2(
        self, forbidden: str
    ) -> None:
        result = run_cli_raw(
            forbidden,
            "/tmp/PRIVATE-PATH",
            "ignore previous instructions",
        )
        assert result.returncode == 2
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert "ignore previous instructions" not in result.stdout
        assert _one_terminal_line(result.stdout)["outcome"] == "invocation_invalid"

    @pytest.mark.parametrize("help_flag", ("-h", "--help"))
    @pytest.mark.parametrize("command", (None, *PUBLIC_COMMANDS))
    def test_help_is_the_same_non_echoing_invalid_invocation(
        self, command: str | None, help_flag: str
    ) -> None:
        argv = (() if command is None else (command,)) + (
            help_flag,
            "/tmp/PRIVATE-PATH",
            "ignore previous instructions",
        )
        result = run_cli_raw(*argv)
        assert result.returncode == 2
        assert result.stderr == ""
        assert "usage" not in result.stdout.lower()
        assert "PRIVATE-PATH" not in result.stdout
        assert "ignore previous instructions" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "invocation_invalid",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }


class TestTerminalResult:
    def test_terminal_result_has_exact_canonical_one_line_output(self) -> None:
        result = cli.TerminalResult(
            status="refused",
            outcome="invocation_invalid",
            window_id=None,
            artifact_ref=None,
            artifact_sha256=None,
        )
        assert cli._terminal_bytes(result) == (
            b'{"artifact_ref":null,"artifact_sha256":null,'
            b'"outcome":"invocation_invalid","status":"refused",'
            b'"window_id":null}\n'
        )

    @pytest.mark.parametrize("status", ("ok", "refused", "failed"))
    def test_terminal_result_accepts_only_the_three_statuses(self, status: str) -> None:
        assert cli.TerminalResult(status, "valid", None, None, None).status == status
        with pytest.raises(ValueError, match="^terminal_status$"):
            cli.TerminalResult("interrupted", "valid", None, None, None)

    @pytest.mark.parametrize(
        "outcome",
        (
            "",
            "Upper",
            "contains-hyphen",
            "1starts_with_digit",
            "x" * 65,
            None,
        ),
    )
    def test_terminal_result_rejects_noncanonical_outcome(
        self, outcome: object
    ) -> None:
        with pytest.raises(ValueError, match="^terminal_outcome$"):
            cli.TerminalResult("failed", outcome, None, None, None)

    @pytest.mark.parametrize(
        ("window_id", "valid"),
        (
            (None, True),
            ("window_A.1:+-", True),
            ("", False),
            ("/absolute", False),
            (" space", False),
            ("x" * 129, False),
        ),
    )
    def test_terminal_result_validates_bounded_window_id(
        self, window_id: str | None, valid: bool
    ) -> None:
        if valid:
            assert cli.TerminalResult(
                "ok", "valid", window_id, "artifact.json", SHA_A
            ).window_id == window_id
        else:
            with pytest.raises(ValueError, match="^terminal_window_id$"):
                cli.TerminalResult("ok", "valid", window_id, "artifact.json", SHA_A)

    @pytest.mark.parametrize(
        ("artifact_ref", "artifact_sha256"),
        (
            ("artifact.json", None),
            (None, SHA_A),
            ("/absolute.json", SHA_A),
            ("../escape.json", SHA_A),
            ("a//b.json", SHA_A),
            ("./artifact.json", SHA_A),
            ("artifact.json", "A" * 64),
            ("artifact.json", "a" * 63),
        ),
    )
    def test_terminal_result_rejects_invalid_artifact_pair(
        self, artifact_ref: str | None, artifact_sha256: str | None
    ) -> None:
        with pytest.raises(ValueError, match="^terminal_artifact_pair$"):
            cli.TerminalResult(
                "failed",
                "provider_uncertain",
                None,
                artifact_ref,
                artifact_sha256,
            )


class TestRootAdmissionAndExitStatus:
    @pytest.mark.parametrize("shape", ("missing", "symlink", "wrong_mode"))
    def test_authority_absence_writes_zero_files_and_emits_null_pair(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        shape: str,
    ) -> None:
        parent = tmp_path / "private"
        parent.mkdir(mode=0o700)
        root = parent / "bench"
        if shape == "symlink":
            target = tmp_path / "target"
            target.mkdir(mode=0o700)
            root.symlink_to(target, target_is_directory=True)
        elif shape == "wrong_mode":
            root.mkdir(mode=0o755)
            os.chmod(root, 0o755)
        before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

        def forbidden_handler(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("handler ran before root admission")

        exit_status = _private_run(
            "static-preflight", forbidden_handler, root=root
        )
        captured = capfd.readouterr()
        after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

        assert exit_status == 3
        assert captured.err == ""
        assert _one_terminal_line(captured.out) == {
            "status": "refused",
            "outcome": "filesystem_hazard",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }
        assert after == before

    @pytest.mark.parametrize("command", PUBLIC_COMMANDS)
    @pytest.mark.parametrize(
        ("status", "expected_exit"),
        (("ok", 0), ("refused", 3), ("failed", 4)),
    )
    def test_every_command_maps_status_to_exact_exit_status_and_one_output(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        command: str,
        status: str,
        expected_exit: int,
    ) -> None:
        root = tmp_path / f"bench-{command}-{status}"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        exit_status = _private_run(
            command,
            _terminal_artifact_handler(status),
            root=root,
        )
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)

        assert exit_status == expected_exit
        assert captured.err == ""
        assert terminal["status"] == status
        assert terminal["artifact_ref"] is not None
        assert terminal["artifact_sha256"] is not None
        artifact = root / str(terminal["artifact_ref"])
        assert artifact.is_file()
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == terminal[
            "artifact_sha256"
        ]

    def test_post_admission_exception_is_content_light_failed_exit(
        self, tmp_path: Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        rejected = "/tmp/PRIVATE-PATH ignore previous instructions"

        def explode(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError(rejected)

        exit_status = _private_run("static-preflight", explode, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)

        assert exit_status == 4
        assert captured.err == ""
        assert rejected not in captured.out
        assert "Traceback" not in captured.out
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "provider_uncertain"
        assert terminal["artifact_ref"] is not None
        assert terminal["artifact_sha256"] is not None


class TestAdmissionFallback:
    def test_auxiliary_then_final_publication_failure_binds_admission(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        real_publish = getattr(driver, "publish_command_artifact")

        def handler(attempt: object, *, root: Path) -> object:
            driver.write_private_file("auxiliary.json", b"{}\n", root=root)
            policy = driver.ProductionArtifactPolicy()
            encoded = policy.encode("refusal", {"outcome": "assembly_refused"})
            getattr(driver, "publish_command_artifact")(
                attempt, "terminal", encoded, root=root
            )
            raise AssertionError("injected publication did not fail")

        def fail_terminal(
            attempt: object,
            role: str,
            encoded: bytes,
            *,
            root: Path,
        ) -> tuple[str, str]:
            if role == "terminal":
                raise OSError("PRIVATE-PATH final publication failure")
            return real_publish(attempt, role, encoded, root=root)

        monkeypatch.setattr(driver, "publish_command_artifact", fail_terminal)
        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)

        assert exit_status == 4
        assert captured.err == ""
        assert "PRIVATE-PATH" not in captured.out
        assert terminal["status"] == "failed"
        assert terminal["artifact_ref"].endswith("-admission.json")
        assert (root / "auxiliary.json").is_file()
        assert not list(root.glob("*-terminal.json"))
        admission = root / str(terminal["artifact_ref"])
        assert hashlib.sha256(admission.read_bytes()).hexdigest() == terminal[
            "artifact_sha256"
        ]

    def test_ok_cannot_cite_the_admission_receipt(
        self, tmp_path: Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        def dishonest_ok(attempt: object, *, root: Path) -> object:
            del root
            return cli.TerminalResult(
                "ok",
                "command_complete",
                None,
                getattr(attempt, "admission_ref"),
                getattr(attempt, "admission_sha256"),
            )

        exit_status = _private_run("static-preflight", dishonest_ok, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)

        assert exit_status == 4
        assert captured.err == ""
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "provider_uncertain"
        assert terminal["artifact_ref"].endswith("-admission.json")

    @pytest.mark.parametrize("cleanup_failure", ("unlink", "parent_fsync"))
    def test_failed_admission_cleanup_is_null_cleanup_incomplete(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        cleanup_failure: str,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        linked = False
        directory_syncs = 0
        real_link = driver.os.link
        real_fsync = driver.os.fsync
        real_unlink = driver.os.unlink

        def tracking_link(*args: object, **kwargs: object) -> None:
            nonlocal linked
            real_link(*args, **kwargs)
            linked = True

        def failing_fsync(fd: int) -> None:
            nonlocal directory_syncs
            if linked and os.path.isdir(f"/proc/self/fd/{fd}"):
                directory_syncs += 1
                if directory_syncs == 1 or cleanup_failure == "parent_fsync":
                    raise OSError("injected directory fsync")
            real_fsync(fd)

        def failing_unlink(*args: object, **kwargs: object) -> None:
            if cleanup_failure == "unlink":
                raise OSError("injected unlink")
            real_unlink(*args, **kwargs)

        monkeypatch.setattr(driver.os, "link", tracking_link)
        monkeypatch.setattr(driver.os, "fsync", failing_fsync)
        monkeypatch.setattr(driver.os, "unlink", failing_unlink)

        exit_status = _private_run(
            "static-preflight",
            lambda *_args, **_kwargs: pytest.fail("handler ran"),
            root=root,
        )
        captured = capfd.readouterr()

        assert exit_status == 4
        assert captured.err == ""
        assert _one_terminal_line(captured.out) == {
            "status": "failed",
            "outcome": "cleanup_incomplete",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }


def _run_admission_boundary_signal_subprocess(
    root: Path,
    *,
    boundary: str,
    signum: int,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, stat, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "boundary = sys.argv[2]",
            "signum = int(sys.argv[3])",
            "state = {'linked': False, 'sent': False}",
            "real_link = driver.os.link",
            "real_fsync = driver.os.fsync",
            "real_open = driver.os.open",
            "real_sha256 = driver.hashlib.sha256",
            "def send_once():",
            "    if not state['sent']:",
            "        state['sent'] = True",
            "        os.kill(os.getpid(), signum)",
            "def injected_link(*args, **kwargs):",
            "    result = real_link(*args, **kwargs)",
            "    state['linked'] = True",
            "    if boundary == 'link': send_once()",
            "    return result",
            "def injected_fsync(fd):",
            "    result = real_fsync(fd)",
            "    if boundary == 'parent_fsync' and state['linked'] and stat.S_ISDIR(os.fstat(fd).st_mode): send_once()",
            "    return result",
            "def injected_open(path, flags, *args, **kwargs):",
            "    fd = real_open(path, flags, *args, **kwargs)",
            "    if boundary == 'anchored_reopen' and state['linked'] and str(path).endswith('-admission.json') and flags & os.O_ACCMODE == os.O_RDONLY: send_once()",
            "    return fd",
            "def injected_sha256(*args, **kwargs):",
            "    result = real_sha256(*args, **kwargs)",
            "    if boundary == 'hash' and state['linked']: send_once()",
            "    return result",
            "driver.os.link = injected_link",
            "driver.os.fsync = injected_fsync",
            "driver.os.open = injected_open",
            "driver.hashlib.sha256 = injected_sha256",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def forbidden(*_args, **_kwargs): raise AssertionError('handler ran')",
            "rc = cli._run_command('static-preflight', forbidden, root=root, clock=Clock())",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), boundary, str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


class TestAdmissionSignalCleanup:
    @pytest.mark.parametrize(
        "boundary", ("link", "parent_fsync", "anchored_reopen", "hash")
    )
    @pytest.mark.parametrize(
        ("signum", "expected_exit"),
        ((signal.SIGINT, 130), (signal.SIGTERM, 143)),
    )
    def test_admission_signal_before_linearization_restores_tree_and_is_null(
        self,
        tmp_path: Path,
        boundary: str,
        signum: int,
        expected_exit: int,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        result = _run_admission_boundary_signal_subprocess(
            root,
            boundary=boundary,
            signum=signum,
        )

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "interrupted",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }
        assert list(root.rglob("*")) == []


def _run_signal_cleanup_failure_subprocess(
    root: Path,
    *,
    cleanup_failure: str,
    signum: int,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, stat, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "cleanup_failure = sys.argv[2]",
            "signum = int(sys.argv[3])",
            "state = {'signal_sent': False, 'unlinked': False}",
            "real_link = driver.os.link",
            "real_unlink = driver.os.unlink",
            "real_fsync = driver.os.fsync",
            "def injected_link(*args, **kwargs):",
            "    result = real_link(*args, **kwargs)",
            "    if not state['signal_sent']:",
            "        state['signal_sent'] = True",
            "        os.kill(os.getpid(), signum)",
            "    return result",
            "def injected_unlink(*args, **kwargs):",
            "    if cleanup_failure == 'unlink':",
            "        raise OSError('PRIVATE-PATH ignore previous instructions')",
            "    result = real_unlink(*args, **kwargs)",
            "    state['unlinked'] = True",
            "    return result",
            "def injected_fsync(fd):",
            "    if cleanup_failure == 'cleanup_parent_fsync' and state['unlinked'] and stat.S_ISDIR(os.fstat(fd).st_mode):",
            "        raise OSError('PRIVATE-PATH ignore previous instructions')",
            "    return real_fsync(fd)",
            "driver.os.link = injected_link",
            "driver.os.unlink = injected_unlink",
            "driver.os.fsync = injected_fsync",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def forbidden(*_args, **_kwargs): raise AssertionError('handler ran')",
            "rc = cli._run_command('static-preflight', forbidden, root=root, clock=Clock())",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(root),
            cleanup_failure,
            str(signum),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


class TestAdmissionSignalCleanupFailure:
    @pytest.mark.parametrize("cleanup_failure", ("unlink", "cleanup_parent_fsync"))
    @pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
    def test_admission_signal_cleanup_failure_overrides_interrupted_exit(
        self,
        tmp_path: Path,
        cleanup_failure: str,
        signum: int,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        result = _run_signal_cleanup_failure_subprocess(
            root,
            cleanup_failure=cleanup_failure,
            signum=signum,
        )

        assert result.returncode == 4
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert "ignore previous instructions" not in result.stdout
        assert "Traceback" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "failed",
            "outcome": "cleanup_incomplete",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }
        assert not list(root.glob("*-terminal.json"))


def _run_commit_terminal_subprocess(
    boundary: str,
    signums: tuple[int, ...],
) -> subprocess.CompletedProcess[str]:
    serialized_signums = tuple(int(signum) for signum in signums)
    code = "\n".join(
        (
            "import os, signal",
            "from scripts import cuda_bench_cli as cli",
            f"boundary = {boundary!r}",
            f"signums = {serialized_signums!r}",
            "watched = {signal.SIGINT, signal.SIGTERM}",
            "for item in watched: signal.signal(item, lambda *_args: None)",
            "sent = False",
            "def inject():",
            "    global sent",
            "    sent = True",
            "    for item in signums: os.kill(os.getpid(), item)",
            "normal = cli.TerminalResult('ok', 'command_complete', None, 'final.json', 'a' * 64)",
            "real_write = cli.os.write",
            "real_mask = cli.signal.pthread_sigmask",
            "if boundary == 'before_write':",
            "    real_mask(signal.SIG_BLOCK, watched)",
            "    inject()",
            "elif boundary == 'while_write':",
            "    def injected_write(fd, data):",
            "        inject()",
            "        return real_write(fd, data)",
            "    cli.os.write = injected_write",
            "elif boundary == 'after_write':",
            "    calls = 0",
            "    def injected_mask(how, mask):",
            "        global calls",
            "        calls += 1",
            "        if calls == 2:",
            "            inject()",
            "        return real_mask(how, mask)",
            "    cli.signal.pthread_sigmask = injected_mask",
            "code = cli._commit_terminal(normal)",
            "if not sent: raise AssertionError('signal injection did not fire')",
            "real_mask(signal.SIG_UNBLOCK, watched)",
            "os._exit(code)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class TestTerminalSignalLinearization:
    @pytest.mark.parametrize(
        ("signums", "expected_exit"),
        (((signal.SIGINT,), 130), ((signal.SIGTERM,), 143), ((signal.SIGINT, signal.SIGTERM), 143)),
    )
    def test_signal_pending_before_terminal_snapshot_selects_one_interrupted_line(
        self, signums: tuple[int, ...], expected_exit: int
    ) -> None:
        result = _run_commit_terminal_subprocess("before_write", signums)
        terminal = _one_terminal_line(result.stdout)
        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert terminal == {
            "status": "refused",
            "outcome": "interrupted",
            "window_id": None,
            "artifact_ref": "final.json",
            "artifact_sha256": SHA_A,
        }

    @pytest.mark.parametrize("boundary", ("while_write", "after_write"))
    @pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
    def test_signal_after_snapshot_cannot_append_or_change_committed_terminal(
        self, boundary: str, signum: int
    ) -> None:
        result = _run_commit_terminal_subprocess(boundary, (signum,))
        terminal = _one_terminal_line(result.stdout)
        assert result.returncode == 0
        assert result.stderr == ""
        assert terminal == {
            "status": "ok",
            "outcome": "command_complete",
            "window_id": None,
            "artifact_ref": "final.json",
            "artifact_sha256": SHA_A,
        }

    @pytest.mark.parametrize(
        ("command", "signum", "expected_exit"),
        (
            ("static-preflight", signal.SIGINT, 130),
            ("rehearse", signal.SIGTERM, 143),
            ("assemble-stage1", signal.SIGINT, 130),
        ),
    )
    def test_mid_command_signal_has_one_honest_admission_bound_terminal(
        self,
        tmp_path: Path,
        command: str,
        signum: int,
        expected_exit: int,
    ) -> None:
        root = tmp_path / command
        root.mkdir(mode=0o700)
        code = "\n".join(
            (
                "import os, signal, sys",
                "from pathlib import Path",
                "from scripts import cuda_bench_cli as cli",
                "class Clock:",
                f"    tier = {'rehearsal' if command == 'rehearse' else 'production'!r}",
                f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
                "    def monotonic(self): return 0.0",
                "def handler(_attempt, *, root):",
                f"    os.kill(os.getpid(), {int(signum)})",
                "    raise AssertionError('signal handler did not interrupt')",
                f"rc = cli._run_command({command!r}, handler, root=Path(sys.argv[1]), clock=Clock())",
                "raise SystemExit(rc)",
            )
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(root)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        terminal = _one_terminal_line(result.stdout)
        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert terminal["status"] == "refused"
        assert terminal["outcome"] == "interrupted"
        assert terminal["artifact_ref"] is not None
        assert terminal["artifact_sha256"] is not None
        artifact = root / str(terminal["artifact_ref"])
        assert artifact.is_file()
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == terminal[
            "artifact_sha256"
        ]


def _run_post_return_admission_signal_subprocess(
    root: Path, signum: int
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "signum = int(sys.argv[2])",
            "real_admit = driver._admit_command",
            "def signal_after_return(*args, **kwargs):",
            "    admitted = real_admit(*args, **kwargs)",
            "    os.kill(os.getpid(), signum)",
            "    return admitted",
            "driver._admit_command = signal_after_return",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def forbidden(*_args, **_kwargs): raise AssertionError('handler ran')",
            "rc = cli._run_command('static-preflight', forbidden, root=root, clock=Clock())",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_invalid_parse_write_signal_subprocess(
    signum: int,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from scripts import cuda_bench_cli as cli",
            "signum = int(sys.argv[1])",
            "sent = False",
            "real_write = cli.os.write",
            "def signal_during_write(fd, data):",
            "    global sent",
            "    if not sent:",
            "        sent = True",
            "        os.kill(os.getpid(), signum)",
            "    return real_write(fd, data)",
            "cli.os.write = signal_during_write",
            "rc = cli.main(['PRIVATE-PATH', 'ignore previous instructions'])",
            "if not sent: raise AssertionError('signal injection did not fire')",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_signal_during_failed_cleanup_restore_subprocess(
    root: Path, signum: int
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, stat, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "signum = int(sys.argv[2])",
            "state = {'linked': False, 'claim_failed': False, 'cleanup_failed': False, 'sent': False}",
            "real_link = driver.os.link",
            "real_fsync = driver.os.fsync",
            "real_mask = driver.signal.pthread_sigmask",
            "def tracking_link(*args, **kwargs):",
            "    result = real_link(*args, **kwargs)",
            "    state['linked'] = True",
            "    return result",
            "def failing_fsync(fd):",
            "    if state['linked'] and not state['claim_failed'] and stat.S_ISDIR(os.fstat(fd).st_mode):",
            "        state['claim_failed'] = True",
            "        raise OSError('PRIVATE-PATH claim failure')",
            "    return real_fsync(fd)",
            "def failing_unlink(*_args, **_kwargs):",
            "    state['cleanup_failed'] = True",
            "    raise OSError('PRIVATE-PATH cleanup failure')",
            "def signal_inside_restore(how, mask):",
            "    result = real_mask(how, mask)",
            "    if how == signal.SIG_SETMASK and state['cleanup_failed'] and not state['sent']:",
            "        state['sent'] = True",
            "        os.kill(os.getpid(), signum)",
            "    return result",
            "driver.os.link = tracking_link",
            "driver.os.fsync = failing_fsync",
            "driver.os.unlink = failing_unlink",
            "driver.signal.pthread_sigmask = signal_inside_restore",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def forbidden(*_args, **_kwargs): raise AssertionError('handler ran')",
            "rc = cli._run_command('static-preflight', forbidden, root=root, clock=Clock())",
            "if not state['sent']: raise AssertionError('signal injection did not fire')",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


class TestTask3ReviewSignalBoundaries:
    @pytest.mark.parametrize(
        ("signum", "expected_exit"),
        ((signal.SIGINT, 130), (signal.SIGTERM, 143)),
    )
    def test_post_return_preassignment_signal_cites_exact_admission(
        self,
        tmp_path: Path,
        signum: int,
        expected_exit: int,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)

        result = _run_post_return_admission_signal_subprocess(root, signum)
        admissions = list(root.glob("*-admission.json"))

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert len(admissions) == 1
        terminal = _one_terminal_line(result.stdout)
        assert terminal == {
            "status": "refused",
            "outcome": "interrupted",
            "window_id": None,
            "artifact_ref": admissions[0].name,
            "artifact_sha256": hashlib.sha256(admissions[0].read_bytes()).hexdigest(),
        }

    @pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
    def test_parse_invalid_signal_during_terminal_write_keeps_normal_rc2_line(
        self, signum: int
    ) -> None:
        result = _run_invalid_parse_write_signal_subprocess(signum)

        assert result.returncode == 2
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert "ignore previous instructions" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "invocation_invalid",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }

    @pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
    def test_signal_inside_restore_cannot_override_failed_cleanup(
        self, tmp_path: Path, signum: int
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)

        result = _run_signal_during_failed_cleanup_restore_subprocess(root, signum)

        assert result.returncode == 4
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert "Traceback" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "failed",
            "outcome": "cleanup_incomplete",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }
        assert not list(root.glob("*-terminal.json"))


def _run_signal_after_final_subprocess(
    root: Path, signum: int
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "signum = int(sys.argv[2])",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def handler(attempt, *, root):",
            "    encoded = driver.ProductionArtifactPolicy().encode('refusal', {'outcome': 'assembly_refused'})",
            "    driver.publish_command_artifact(attempt, 'terminal', encoded, root=root)",
            "    os.kill(os.getpid(), signum)",
            "    raise AssertionError('signal did not interrupt')",
            "rc = cli._run_command('static-preflight', handler, root=root, clock=Clock())",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_pending_signal_after_final_subprocess(
    root: Path, signum: int
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "signum = int(sys.argv[2])",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def handler(attempt, *, root):",
            "    encoded = driver.ProductionArtifactPolicy().encode('refusal', {'outcome': 'assembly_refused'})",
            "    relative, digest = driver.publish_command_artifact(attempt, 'terminal', encoded, root=root)",
            "    signal.pthread_sigmask(signal.SIG_BLOCK, {signum})",
            "    os.kill(os.getpid(), signum)",
            "    return cli.TerminalResult('ok', 'command_complete', None, relative, digest)",
            "rc = cli._run_command('static-preflight', handler, root=root, clock=Clock())",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_terminal_publication_signal_subprocess(
    root: Path, boundary: str, signum: int
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, stat, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "boundary = sys.argv[2]",
            "signum = int(sys.argv[3])",
            "state = {'terminal_linked': False, 'sent': False}",
            "real_link = driver.os.link",
            "real_fsync = driver.os.fsync",
            "def send_once():",
            "    if not state['sent']:",
            "        state['sent'] = True",
            "        os.kill(os.getpid(), signum)",
            "def injected_link(*args, **kwargs):",
            "    result = real_link(*args, **kwargs)",
            "    if str(args[1]).endswith('-terminal.json'):",
            "        state['terminal_linked'] = True",
            "        if boundary == 'after_link': send_once()",
            "    return result",
            "def injected_fsync(fd):",
            "    result = real_fsync(fd)",
            "    if boundary == 'parent_fsync' and state['terminal_linked'] and stat.S_ISDIR(os.fstat(fd).st_mode): send_once()",
            "    return result",
            "driver.os.link = injected_link",
            "driver.os.fsync = injected_fsync",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def handler(attempt, *, root):",
            "    encoded = driver.ProductionArtifactPolicy().encode('refusal', {'outcome': 'assembly_refused'})",
            "    driver.publish_command_artifact(attempt, 'terminal', encoded, root=root)",
            "    raise AssertionError('publication returned')",
            "rc = cli._run_command('static-preflight', handler, root=root, clock=Clock())",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), boundary, str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_fallback_gap_signal_subprocess(
    root: Path, boundary: str, signum: int
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "boundary = sys.argv[2]",
            "signum = int(sys.argv[3])",
            "sent = False",
            "def send_once():",
            "    global sent",
            "    if not sent:",
            "        sent = True",
            "        os.kill(os.getpid(), signum)",
            "if boundary == 'exception_fallback':",
            "    real_exception = cli._exception_result",
            "    def injected_exception(*args, **kwargs):",
            "        send_once()",
            "        return real_exception(*args, **kwargs)",
            "    cli._exception_result = injected_exception",
            "else:",
            "    real_commit = cli._commit_terminal",
            "    def injected_commit(*args, **kwargs):",
            "        send_once()",
            "        return real_commit(*args, **kwargs)",
            "    cli._commit_terminal = injected_commit",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def handler(_attempt, *, root):",
            "    del root",
            "    if boundary == 'exception_fallback': raise RuntimeError('PRIVATE-PATH')",
            "    return cli.TerminalResult('refused', 'assembly_refused', None, None, None)",
            "rc = cli._run_command('static-preflight', handler, root=root, clock=Clock())",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), boundary, str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_post_commit_restore_failure_subprocess(
    root: Path, boundary: str
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import signal, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "boundary = sys.argv[2]",
            "if boundary == 'mask_restore':",
            "    real_mask = cli.signal.pthread_sigmask",
            "    def failing_mask(how, mask):",
            "        if how == signal.SIG_SETMASK: raise OSError('PRIVATE-PATH mask restore')",
            "        return real_mask(how, mask)",
            "    cli.signal.pthread_sigmask = failing_mask",
            "    result = cli.TerminalResult('ok', 'command_complete', None, 'final.json', 'a' * 64)",
            "    raise SystemExit(cli._commit_terminal(result))",
            "real_signal = cli.signal.signal",
            "signal_calls = 0",
            "def failing_signal(signum, handler):",
            "    global signal_calls",
            "    signal_calls += 1",
            "    result = real_signal(signum, handler)",
            "    if signal_calls == 3: raise OSError('PRIVATE-PATH handler restore')",
            "    return result",
            "cli.signal.signal = failing_signal",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def handler(_attempt, *, root):",
            "    del root",
            "    return cli.TerminalResult('refused', 'assembly_refused', None, None, None)",
            "raise SystemExit(cli._run_command('static-preflight', handler, root=root, clock=Clock()))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), boundary],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


class TestTask3ReviewRemainingOutputBoundaries:
    @pytest.mark.parametrize(
        ("command", "relative"),
        (
            (
                "static-preflight",
                "windows/window-a/vulkan_baseline/attempt-000/"
                "vulkan_baseline-completed.json",
            ),
            (
                "rehearse",
                "rehearsal/windows/window-a/vulkan_baseline/attempt-000/"
                "vulkan_baseline-rehearsal.json",
            ),
        ),
    )
    def test_valid_non_command_final_reference_survives_normalization(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        command: str,
        relative: str,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        payload = b'{"content_light":true}\n'

        def handler(_attempt: object, *, root: Path) -> cli.TerminalResult:
            driver.write_private_file(relative, payload, root=root)
            return cli.TerminalResult(
                "ok",
                "command_complete",
                None,
                relative,
                hashlib.sha256(payload).hexdigest(),
            )

        exit_status = _private_run(command, handler, root=root)
        captured = capfd.readouterr()

        assert exit_status == 0
        assert captured.err == ""
        assert _one_terminal_line(captured.out) == {
            "status": "ok",
            "outcome": "command_complete",
            "window_id": None,
            "artifact_ref": relative,
            "artifact_sha256": hashlib.sha256(payload).hexdigest(),
        }
        assert list(root.rglob("*-admission.json"))

    @pytest.mark.parametrize(
        ("signum", "expected_exit"),
        ((signal.SIGINT, 130), (signal.SIGTERM, 143)),
    )
    def test_signal_after_final_still_cites_the_admission(
        self, tmp_path: Path, signum: int, expected_exit: int
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)

        result = _run_signal_after_final_subprocess(root, signum)
        admissions = list(root.glob("*-admission.json"))
        terminals = list(root.glob("*-terminal.json"))

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert len(admissions) == len(terminals) == 1
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "interrupted",
            "window_id": None,
            "artifact_ref": admissions[0].name,
            "artifact_sha256": hashlib.sha256(admissions[0].read_bytes()).hexdigest(),
        }

    @pytest.mark.parametrize(
        ("signum", "expected_exit"),
        ((signal.SIGINT, 130), (signal.SIGTERM, 143)),
    )
    def test_pending_signal_at_terminal_snapshot_cites_the_admission(
        self, tmp_path: Path, signum: int, expected_exit: int
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)

        result = _run_pending_signal_after_final_subprocess(root, signum)
        admissions = list(root.glob("*-admission.json"))
        terminals = list(root.glob("*-terminal.json"))

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert len(admissions) == len(terminals) == 1
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "interrupted",
            "window_id": None,
            "artifact_ref": admissions[0].name,
            "artifact_sha256": hashlib.sha256(admissions[0].read_bytes()).hexdigest(),
        }

    @pytest.mark.parametrize("boundary", ("after_link", "parent_fsync"))
    @pytest.mark.parametrize(
        ("signum", "expected_exit"),
        ((signal.SIGINT, 130), (signal.SIGTERM, 143)),
    )
    def test_signal_before_terminal_publication_linearizes_removes_terminal(
        self,
        tmp_path: Path,
        boundary: str,
        signum: int,
        expected_exit: int,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)

        result = _run_terminal_publication_signal_subprocess(root, boundary, signum)
        admission = next(root.glob("*-admission.json"))

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert not list(root.glob("*-terminal.json"))
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "interrupted",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(admission.read_bytes()).hexdigest(),
        }

    @pytest.mark.parametrize("boundary", ("exception_fallback", "pre_commit"))
    @pytest.mark.parametrize(
        ("signum", "expected_exit"),
        ((signal.SIGINT, 130), (signal.SIGTERM, 143)),
    )
    def test_signal_in_fallback_or_precommit_gap_is_admission_bound(
        self,
        tmp_path: Path,
        boundary: str,
        signum: int,
        expected_exit: int,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)

        result = _run_fallback_gap_signal_subprocess(root, boundary, signum)
        admission = next(root.glob("*-admission.json"))

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "interrupted",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(admission.read_bytes()).hexdigest(),
        }

    def test_post_admission_cleanup_incomplete_is_failed_rc4_with_binding(
        self, tmp_path: Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        def handler(*_args: object, **_kwargs: object) -> object:
            raise driver.BenchRefusal("cleanup_incomplete")

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)

        assert exit_status == 4
        assert captured.err == ""
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "cleanup_incomplete"
        assert terminal["artifact_ref"] is not None
        artifact = root / str(terminal["artifact_ref"])
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == terminal[
            "artifact_sha256"
        ]

    def test_post_admission_invocation_invalid_fails_closed_to_provider_uncertain(
        self, tmp_path: Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        def handler(*_args: object, **_kwargs: object) -> cli.TerminalResult:
            return cli.TerminalResult(
                "refused", "invocation_invalid", None, None, None
            )

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        admission = next(root.glob("*-admission.json"))

        assert exit_status == 4
        assert captured.err == ""
        assert _one_terminal_line(captured.out) == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(admission.read_bytes()).hexdigest(),
        }

    @pytest.mark.parametrize(
        ("boundary", "expected_exit"),
        (("mask_restore", 0), ("handler_restore", 3)),
    )
    def test_post_commit_restore_failure_preserves_line_and_exit_code(
        self, tmp_path: Path, boundary: str, expected_exit: int
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)

        result = _run_post_commit_restore_failure_subprocess(root, boundary)
        terminal = _one_terminal_line(result.stdout)

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        if boundary == "mask_restore":
            assert terminal == {
                "status": "ok",
                "outcome": "command_complete",
                "window_id": None,
                "artifact_ref": "final.json",
                "artifact_sha256": SHA_A,
            }
        else:
            assert terminal["status"] == "refused"
            assert terminal["outcome"] == "assembly_refused"
            assert terminal["artifact_ref"] is not None
            artifact = root / str(terminal["artifact_ref"])
            assert hashlib.sha256(artifact.read_bytes()).hexdigest() == terminal[
                "artifact_sha256"
            ]

    def test_binding_check_propagates_keyboard_interrupt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = cli.TerminalResult("ok", "command_complete", None, "x.json", SHA_A)

        def interrupted(*_args: object, **_kwargs: object) -> bytes:
            raise KeyboardInterrupt

        monkeypatch.setattr(driver, "open_bench_file", interrupted)
        with pytest.raises(KeyboardInterrupt):
            cli._binding_is_current(result, root=tmp_path)

    def test_binding_check_leaves_command_interruption_for_outer_scope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = cli.TerminalResult("ok", "command_complete", None, "x.json", SHA_A)
        interruption = driver._CommandInterrupted(signal.SIGTERM)

        def interrupted(*_args: object, **_kwargs: object) -> bytes:
            raise interruption

        monkeypatch.setattr(driver, "open_bench_file", interrupted)
        with pytest.raises(driver._CommandInterrupted) as exc:
            cli._binding_is_current(result, root=tmp_path)
        assert exc.value is interruption


def _run_outer_signal_gap_subprocess(
    boundary: str, signum: int
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "boundary = sys.argv[1]",
            "signum = int(sys.argv[2])",
            "sent = False",
            "def send_once():",
            "    global sent",
            "    if not sent:",
            "        sent = True",
            "        os.kill(os.getpid(), signum)",
            "if boundary == 'partial_handler_install':",
            "    other = signal.SIGTERM if signum == signal.SIGINT else signal.SIGINT",
            "    cli._WATCHED_SIGNALS = (other, signum)",
            "    real_signal = cli.signal.signal",
            "    install_calls = 0",
            "    def injected_signal(installed_signum, handler):",
            "        global install_calls",
            "        result = real_signal(installed_signum, handler)",
            "        if handler is cli._on_command_signal:",
            "            install_calls += 1",
            "            if install_calls == 1: send_once()",
            "        return result",
            "    cli.signal.signal = injected_signal",
            "elif boundary == 'handler_install':",
            "    real_install = cli._install_command_signal_scope",
            "    def injected_install():",
            "        previous = real_install()",
            "        send_once()",
            "        return previous",
            "    cli._install_command_signal_scope = injected_install",
            "elif boundary == 'post_parse':",
            "    class SignalClock:",
            "        tier = 'production'",
            "        def __init__(self): send_once()",
            f"        def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "        def monotonic(self): return 0.0",
            "    driver.SystemClock = SignalClock",
            "elif boundary == 'terminal_preblock':",
            "    real_mask = cli.signal.pthread_sigmask",
            "    def injected_mask(how, mask):",
            "        if how == signal.SIG_BLOCK: send_once()",
            "        return real_mask(how, mask)",
            "    cli.signal.pthread_sigmask = injected_mask",
            "else:",
            "    raise AssertionError('unknown boundary')",
            "argv = ['unknown'] if boundary == 'terminal_preblock' else ['static-preflight']",
            "raise SystemExit(cli.main(argv))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, boundary, str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_latched_cleanup_pending_signal_subprocess(
    signum: int,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from scripts import cuda_bench_cli as cli",
            "signum = int(sys.argv[1])",
            "signal.pthread_sigmask(signal.SIG_BLOCK, {signum})",
            "os.kill(os.getpid(), signum)",
            "if signal.Signals(signum) not in signal.sigpending():",
            "    raise AssertionError('signal was not pending')",
            "cli._cleanup_incomplete_committing = True",
            "result = cli.TerminalResult('failed', 'cleanup_incomplete', None, 'admission.json', 'a' * 64)",
            "raise SystemExit(cli._commit_terminal(result, interruption_fallback=result))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_cleanup_restore_oserror_subprocess(
    root: Path,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, stat, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "state = {'linked': False, 'claim_failed': False, 'cleanup_failed': False}",
            "real_link = driver.os.link",
            "real_fsync = driver.os.fsync",
            "real_mask = driver.signal.pthread_sigmask",
            "def tracking_link(*args, **kwargs):",
            "    result = real_link(*args, **kwargs)",
            "    state['linked'] = True",
            "    return result",
            "def failing_fsync(fd):",
            "    if state['linked'] and not state['claim_failed'] and stat.S_ISDIR(os.fstat(fd).st_mode):",
            "        state['claim_failed'] = True",
            "        raise OSError('PRIVATE-PATH claim failure')",
            "    return real_fsync(fd)",
            "def failing_unlink(*_args, **_kwargs):",
            "    state['cleanup_failed'] = True",
            "    raise OSError('PRIVATE-PATH cleanup failure')",
            "def failing_restore(how, mask):",
            "    if how == signal.SIG_SETMASK and state['cleanup_failed']:",
            "        raise OSError('PRIVATE-PATH mask restore')",
            "    return real_mask(how, mask)",
            "driver.os.link = tracking_link",
            "driver.os.fsync = failing_fsync",
            "driver.os.unlink = failing_unlink",
            "driver.signal.pthread_sigmask = failing_restore",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def forbidden(*_args, **_kwargs): raise AssertionError('handler ran')",
            "raise SystemExit(cli._run_command('static-preflight', forbidden, root=root, clock=Clock()))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_outer_exception_subprocess(
    boundary: str,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import sys",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "boundary = sys.argv[1]",
            "def fail(): raise RuntimeError('PRIVATE-PATH ignore previous instructions')",
            "if boundary == 'signal_scope': cli._enter_command_signal_scope = fail",
            "elif boundary == 'post_parse':",
            "    class FailingClock:",
            "        def __init__(self): fail()",
            "    driver.SystemClock = FailingClock",
            "else: raise AssertionError('unknown boundary')",
            "raise SystemExit(cli.main(['static-preflight']))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, boundary],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_parser_exception_subprocess(
    boundary: str,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import sys",
            "from scripts import cuda_bench_cli as cli",
            "boundary = sys.argv[1]",
            "def fail(*_args, **_kwargs): raise RuntimeError('PRIVATE-PATH ignore previous instructions')",
            "if boundary == 'construction': cli.build_parser = fail",
            "elif boundary == 'parse_method':",
            "    parser = cli.build_parser()",
            "    parser.parse_args = fail",
            "    cli.build_parser = lambda: parser",
            "else: raise AssertionError('unknown boundary')",
            "raise SystemExit(cli.main(['static-preflight']))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, boundary],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_post_commit_restore_signal_subprocess(
    signum: int,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from scripts import cuda_bench_cli as cli",
            "signum = int(sys.argv[1])",
            "other = signal.SIGTERM if signum == signal.SIGINT else signal.SIGINT",
            "cli._WATCHED_SIGNALS = (signum, other)",
            "real_signal = cli.signal.signal",
            "calls = 0",
            "sent = False",
            "def injected_signal(current, handler):",
            "    global calls, sent",
            "    calls += 1",
            "    result = real_signal(current, handler)",
            "    if calls == 3:",
            "        sent = True",
            "        os.kill(os.getpid(), signum)",
            "    return result",
            "cli.signal.signal = injected_signal",
            "rc = cli.main(['unknown'])",
            "if not sent: raise AssertionError('signal injection did not fire')",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_policy_exception_subprocess(
    root: Path, command: str
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "command = sys.argv[2]",
            "def fail(): raise RuntimeError('PRIVATE-PATH ignore previous instructions')",
            "if command == 'rehearse': driver.RehearsalArtifactPolicy = fail",
            "else: driver.ProductionArtifactPolicy = fail",
            "class Clock:",
            "    tier = 'rehearsal' if command == 'rehearse' else 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def forbidden(*_args, **_kwargs): raise AssertionError('handler ran')",
            "raise SystemExit(cli._run_command(command, forbidden, root=root, clock=Clock()))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), command],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_post_drain_unmask_signal_subprocess(
    signum: int,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from scripts import cuda_bench_cli as cli",
            "signum = int(sys.argv[1])",
            "state = {'restoring': False, 'drained': False, 'sent': False}",
            "real_signal = cli.signal.signal",
            "real_snapshot = cli._snapshot_pending_signal",
            "real_mask = cli._pthread_sigmask",
            "def tracking_signal(current, handler):",
            "    result = real_signal(current, handler)",
            "    if cli._terminal_committed and handler is not cli._on_command_signal: state['restoring'] = True",
            "    return result",
            "def tracking_snapshot(explicit):",
            "    result = real_snapshot(explicit)",
            "    if cli._terminal_committed: state['drained'] = True",
            "    return result",
            "def signal_before_unmask(how, mask):",
            "    if how == signal.SIG_SETMASK and state['restoring'] and state['drained'] and not state['sent']:",
            "        state['sent'] = True",
            "        os.kill(os.getpid(), signum)",
            "    return real_mask(how, mask)",
            "cli.signal.signal = tracking_signal",
            "cli._snapshot_pending_signal = tracking_snapshot",
            "cli._pthread_sigmask = signal_before_unmask",
            "rc = cli.main(['unknown'])",
            "if state['sent']: raise AssertionError('public terminal path attempted unsafe unmask')",
            "raise SystemExit(rc)",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(signum)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_terminal_io_failure_subprocess(
    root: Path, boundary: str
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import signal, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "boundary = sys.argv[2]",
            "def fail(*_args, **_kwargs): raise OSError('PRIVATE-PATH ignore previous instructions')",
            "if boundary == 'stdout':",
            "    cli.os.write = fail",
            "    raise SystemExit(cli.main(['unknown']))",
            "real_mask = cli._pthread_sigmask",
            "def fail_restore_preblock(how, mask):",
            "    if how == signal.SIG_BLOCK and cli._terminal_committed: fail()",
            "    return real_mask(how, mask)",
            "cli._pthread_sigmask = fail_restore_preblock",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def handler(*_args, **_kwargs): return cli.TerminalResult('refused', 'assembly_refused', None, None, None)",
            "raise SystemExit(cli._run_command('static-preflight', handler, root=root, clock=Clock()))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), boundary],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _run_terminal_prewrite_failure_subprocess(
    boundary: str,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import sys",
            "from scripts import cuda_bench_cli as cli",
            "boundary = sys.argv[1]",
            "def fail(*_args, **_kwargs): raise OSError('PRIVATE-PATH ignore previous instructions')",
            "if boundary == 'initial_block': cli.signal.pthread_sigmask = fail",
            "elif boundary == 'pending_snapshot': cli._snapshot_pending_signal = fail",
            "else: raise AssertionError('unknown boundary')",
            "raise SystemExit(cli.main(['unknown']))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, boundary],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


class TestTask3ThirdReviewCliBoundaries:
    @pytest.mark.parametrize(
        "boundary", ("initial_block", "pending_snapshot")
    )
    def test_terminal_prewrite_failure_is_silent_content_light_rc4(
        self, boundary: str
    ) -> None:
        result = _run_terminal_prewrite_failure_subprocess(boundary)

        assert result.returncode == 4
        assert result.stdout == ""
        assert result.stderr == ""

    @pytest.mark.parametrize("command", ("static-preflight", "rehearse"))
    def test_policy_construction_failure_is_null_content_light_failure(
        self, tmp_path: Path, command: str
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        result = _run_policy_exception_subprocess(root, command)

        assert result.returncode == 4
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert "ignore previous instructions" not in result.stdout
        assert "Traceback" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }

    @pytest.mark.parametrize("role", ("admission", "terminal"))
    @pytest.mark.parametrize("quarantined", (False, True))
    def test_ok_rejects_every_command_control_artifact(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        role: str,
        quarantined: bool,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        assert _private_run(
            "static-preflight",
            _terminal_artifact_handler("refused"),
            root=root,
        ) == 3
        first = _one_terminal_line(capfd.readouterr().out)
        source = (
            next(root.glob("*001-admission.json"))
            if role == "admission"
            else root / str(first["artifact_ref"])
        )
        if quarantined:
            target = source.with_name(
                f".command-cleanup-{source.name}-{'a' * 32}"
            )
            source.rename(target)
            source = target

        def cites_control(_attempt: object, *, root: Path) -> cli.TerminalResult:
            del root
            return cli.TerminalResult(
                "ok",
                "command_complete",
                None,
                source.name,
                hashlib.sha256(source.read_bytes()).hexdigest(),
            )

        exit_status = _private_run("static-preflight", cites_control, root=root)
        captured = capfd.readouterr()
        current_admission = next(root.glob("*002-admission.json"))

        assert exit_status == 4
        assert captured.err == ""
        assert _one_terminal_line(captured.out) == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": current_admission.name,
            "artifact_sha256": hashlib.sha256(
                current_admission.read_bytes()
            ).hexdigest(),
        }

    @pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
    def test_public_terminal_path_has_no_post_drain_unmask_boundary(
        self, signum: int
    ) -> None:
        result = _run_post_drain_unmask_signal_subprocess(signum)

        assert result.returncode == 2
        assert result.stderr == ""
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "invocation_invalid",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }

    def test_stdout_failure_is_content_light_rc4_without_false_line(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        result = _run_terminal_io_failure_subprocess(root, "stdout")

        assert result.returncode == 4
        assert result.stdout == ""
        assert result.stderr == ""

    def test_post_commit_restore_preblock_failure_preserves_line_and_code(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        result = _run_terminal_io_failure_subprocess(root, "restore_preblock")

        assert result.returncode == 3
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        terminal = _one_terminal_line(result.stdout)
        assert terminal["status"] == "refused"
        assert terminal["outcome"] == "assembly_refused"
        assert terminal["artifact_ref"] is not None
        artifact = root / str(terminal["artifact_ref"])
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == terminal[
            "artifact_sha256"
        ]

    @pytest.mark.parametrize("boundary", ("construction", "parse_method"))
    def test_ordinary_parser_failure_is_non_echoing_and_content_light(
        self, boundary: str
    ) -> None:
        result = _run_parser_exception_subprocess(boundary)

        assert result.returncode == 4
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert "ignore previous instructions" not in result.stdout
        assert "Traceback" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }

    @pytest.mark.parametrize(
        ("signum", "expected_exit"),
        ((signal.SIGINT, 130), (signal.SIGTERM, 143)),
    )
    def test_signal_during_partial_handler_install_is_caught_by_outer_boundary(
        self, signum: int, expected_exit: int
    ) -> None:
        result = _run_outer_signal_gap_subprocess(
            "partial_handler_install", signum
        )

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert "Traceback" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "interrupted",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }

    @pytest.mark.parametrize(
        "boundary", ("handler_install", "post_parse", "terminal_preblock")
    )
    @pytest.mark.parametrize(
        ("signum", "expected_exit"),
        ((signal.SIGINT, 130), (signal.SIGTERM, 143)),
    )
    def test_outer_signal_gaps_emit_one_null_interrupted_line(
        self, boundary: str, signum: int, expected_exit: int
    ) -> None:
        result = _run_outer_signal_gap_subprocess(boundary, signum)

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert "Traceback" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "interrupted",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }

    @pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
    def test_pending_signal_cannot_override_latched_cleanup_incomplete(
        self, signum: int
    ) -> None:
        result = _run_latched_cleanup_pending_signal_subprocess(signum)

        assert result.returncode == 4
        assert result.stderr == ""
        assert _one_terminal_line(result.stdout) == {
            "status": "failed",
            "outcome": "cleanup_incomplete",
            "window_id": None,
            "artifact_ref": "admission.json",
            "artifact_sha256": SHA_A,
        }

    def test_ok_cannot_cite_an_earlier_command_admission(
        self, tmp_path: Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        assert _private_run(
            "static-preflight",
            _terminal_artifact_handler("refused"),
            root=root,
        ) == 3
        first = _one_terminal_line(capfd.readouterr().out)
        first_admission = next(root.glob("*001-admission.json"))
        assert first["artifact_ref"] != first_admission.name

        def cites_first(_attempt: object, *, root: Path) -> cli.TerminalResult:
            del root
            return cli.TerminalResult(
                "ok",
                "command_complete",
                None,
                first_admission.name,
                hashlib.sha256(first_admission.read_bytes()).hexdigest(),
            )

        exit_status = _private_run("static-preflight", cites_first, root=root)
        captured = capfd.readouterr()
        second_admission = next(root.glob("*002-admission.json"))

        assert exit_status == 4
        assert captured.err == ""
        assert _one_terminal_line(captured.out) == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": second_admission.name,
            "artifact_sha256": hashlib.sha256(
                second_admission.read_bytes()
            ).hexdigest(),
        }

    def test_ok_cannot_cite_a_quarantined_command_admission(
        self, tmp_path: Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        assert _private_run(
            "static-preflight",
            _terminal_artifact_handler("refused"),
            root=root,
        ) == 3
        capfd.readouterr()
        first_admission = next(root.glob("*001-admission.json"))
        quarantined = first_admission.with_name(
            f".command-cleanup-{first_admission.name}-{'a' * 32}"
        )
        first_admission.rename(quarantined)

        def cites_orphan(_attempt: object, *, root: Path) -> cli.TerminalResult:
            del root
            return cli.TerminalResult(
                "ok",
                "command_complete",
                None,
                quarantined.name,
                hashlib.sha256(quarantined.read_bytes()).hexdigest(),
            )

        exit_status = _private_run("static-preflight", cites_orphan, root=root)
        captured = capfd.readouterr()
        current_admission = next(root.glob("*002-admission.json"))

        assert exit_status == 4
        assert captured.err == ""
        assert _one_terminal_line(captured.out) == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": current_admission.name,
            "artifact_sha256": hashlib.sha256(
                current_admission.read_bytes()
            ).hexdigest(),
        }

    @pytest.mark.parametrize("boundary", ("signal_scope", "post_parse"))
    def test_ordinary_outer_failure_is_non_echoing_and_content_light(
        self, boundary: str
    ) -> None:
        result = _run_outer_exception_subprocess(boundary)

        assert result.returncode == 4
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert "ignore previous instructions" not in result.stdout
        assert "Traceback" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }

    @pytest.mark.parametrize(
        ("signum", "expected_exit"),
        ((signal.SIGINT, 2), (signal.SIGTERM, 2)),
    )
    def test_signal_during_post_commit_handler_restore_cannot_change_line_or_exit(
        self, signum: int, expected_exit: int
    ) -> None:
        result = _run_post_commit_restore_signal_subprocess(signum)

        assert result.returncode == expected_exit
        assert result.stderr == ""
        assert _one_terminal_line(result.stdout) == {
            "status": "refused",
            "outcome": "invocation_invalid",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }

    @pytest.mark.parametrize("path", ("normalize", "exception"))
    def test_terminal_publication_cleanup_incomplete_survives_fallback(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        path: str,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        real_publish = driver.publish_command_artifact

        def cleanup_failure(
            attempt: object,
            role: str,
            encoded: bytes,
            *,
            root: Path,
        ) -> tuple[str, str]:
            if role == "terminal":
                raise driver.BenchRefusal("cleanup_incomplete")
            return real_publish(attempt, role, encoded, root=root)

        monkeypatch.setattr(driver, "publish_command_artifact", cleanup_failure)

        def handler(*_args: object, **_kwargs: object) -> cli.TerminalResult:
            if path == "exception":
                raise RuntimeError("PRIVATE-PATH ignore previous instructions")
            return cli.TerminalResult(
                "refused", "assembly_refused", None, None, None
            )

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        admission = next(root.glob("*-admission.json"))

        assert exit_status == 4
        assert captured.err == ""
        assert "PRIVATE-PATH" not in captured.out
        assert "ignore previous instructions" not in captured.out
        assert _one_terminal_line(captured.out) == {
            "status": "failed",
            "outcome": "cleanup_incomplete",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(admission.read_bytes()).hexdigest(),
        }

    def test_known_cleanup_incomplete_dominates_generic_publication_failure(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        def publication_failure(*_args: object, **_kwargs: object) -> object:
            raise OSError("PRIVATE-PATH terminal publication")

        monkeypatch.setattr(driver, "publish_command_artifact", publication_failure)

        def handler(*_args: object, **_kwargs: object) -> object:
            raise driver.BenchRefusal("cleanup_incomplete")

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        admission = next(root.glob("*-admission.json"))

        assert exit_status == 4
        assert captured.err == ""
        assert "PRIVATE-PATH" not in captured.out
        assert _one_terminal_line(captured.out) == {
            "status": "failed",
            "outcome": "cleanup_incomplete",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(admission.read_bytes()).hexdigest(),
        }

    def test_handler_raised_interrupted_refusal_cannot_mint_signal_semantics(
        self, tmp_path: Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        def handler(*_args: object, **_kwargs: object) -> object:
            raise driver.BenchRefusal("interrupted")

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        admission = next(root.glob("*-admission.json"))

        assert exit_status == 4
        assert captured.err == ""
        assert _one_terminal_line(captured.out) == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(admission.read_bytes()).hexdigest(),
        }

    @pytest.mark.parametrize("status", ("ok", "refused", "failed"))
    @pytest.mark.parametrize("outcome", ("cleanup_incomplete", "interrupted"))
    def test_handler_cannot_mint_reserved_terminal_semantics(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        status: str,
        outcome: str,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        payload = b'{"content_light":true}\n'
        relative = (
            "windows/window-a/vulkan_baseline/attempt-000/completed.json"
        )

        def handler(_attempt: object, *, root: Path) -> cli.TerminalResult:
            if status == "ok":
                driver.write_private_file(relative, payload, root=root)
                return cli.TerminalResult(
                    "ok",
                    outcome,
                    None,
                    relative,
                    hashlib.sha256(payload).hexdigest(),
                )
            return cli.TerminalResult(status, outcome, None, None, None)

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        admission = next(root.glob("*-admission.json"))

        assert exit_status == 4
        assert captured.err == ""
        assert _one_terminal_line(captured.out) == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(admission.read_bytes()).hexdigest(),
        }

    def test_cleanup_incomplete_survives_mask_restore_oserror(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)

        result = _run_cleanup_restore_oserror_subprocess(root)

        assert result.returncode == 4
        assert result.stderr == ""
        assert "PRIVATE-PATH" not in result.stdout
        assert "Traceback" not in result.stdout
        assert _one_terminal_line(result.stdout) == {
            "status": "failed",
            "outcome": "cleanup_incomplete",
            "window_id": None,
            "artifact_ref": None,
            "artifact_sha256": None,
        }


class TestOwnerSurfaceAuthorityAbsence:
    @pytest.mark.parametrize(
        "relative",
        (
            "scripts/cuda_bench_cli.py",
            "scripts/cuda_bench_assemble.py",
        ),
    )
    def test_owner_surface_has_no_direct_production_mutation_capability(
        self, relative: str
    ) -> None:
        tree = ast.parse((REPO_ROOT / relative).read_text(encoding="utf-8"))

        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.partition(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.partition(".")[0])
        assert imported_roots.isdisjoint(
            {"subprocess", "socket", "http", "urllib", "shutil", "dbus", "systemd"}
        )

        called = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (name := _ast_qualname(node.func)) is not None
        }
        called_leafs = {name.rpartition(".")[2].lstrip("_") for name in called}
        assert called.isdisjoint(
            {
                "os.system",
                "os.popen",
                "os.execl",
                "os.execle",
                "os.execlp",
                "os.execlpe",
                "os.execv",
                "os.execve",
                "os.execvp",
                "os.execvpe",
                "subprocess.Popen",
                "subprocess.run",
                "subprocess.call",
                "subprocess.check_call",
                "subprocess.check_output",
                "os.remove",
                "os.unlink",
                "os.rename",
                "os.replace",
                "os.symlink",
                "os.link",
                "os.chmod",
                "os.chown",
            }
        )
        assert called_leafs.isdisjoint(
            {
                "stop_service",
                "start_service",
                "restart_service",
                "enable_service",
                "disable_service",
                "install_override",
                "remove_override",
                "write_model_env",
                "set_model_pointer",
                "switch_model_pointer",
                "promote",
                "promote_cuda",
                "cutover",
                "rollback_drill",
            }
        )

        exact_literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and type(node.value) is str
        }
        assert exact_literals.isdisjoint(
            {
                "promote",
                "cutover",
                "install",
                "boot",
                "live",
                "stop",
                "start",
                "restart",
                "enable",
                "disable",
                "kill",
                "mask",
            }
        )


class TestAssemblerAuthorityAbsence:
    def test_assembler_scaffold_ast_is_exactly_inert(self) -> None:
        path = REPO_ROOT / "scripts" / "cuda_bench_assemble.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert len(tree.body) == 2
        assert isinstance(tree.body[0], ast.Expr)
        assert isinstance(tree.body[0].value, ast.Constant)
        assert type(tree.body[0].value.value) is str
        assert isinstance(tree.body[1], ast.ImportFrom)
        assert tree.body[1].module == "__future__"
        assert [(alias.name, alias.asname) for alias in tree.body[1].names] == [
            ("annotations", None)
        ]
        assert not any(
            isinstance(
                node,
                (
                    ast.Call,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Assign,
                    ast.AnnAssign,
                    ast.With,
                ),
            )
            for node in ast.walk(tree)
        )

    def test_assembler_scaffold_import_has_no_api_or_side_effect(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        before = list(tmp_path.iterdir())
        module = importlib.import_module("scripts.cuda_bench_assemble")
        public = {
            name
            for name in vars(module)
            if not name.startswith("__")
        }
        assert public == {"annotations"}
        assert type(module.annotations).__module__ == "__future__"
        assert list(tmp_path.iterdir()) == before
