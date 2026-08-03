from __future__ import annotations

import hashlib
import inspect
import os
import shutil
import signal
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import cuda_bench_driver as driver


def _compile_loader_fixture(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True)
    sidecar_source = root / "sidecar.c"
    loader_source = root / "loader.c"
    sidecar = root / "libbench-sidecar.so"
    loader = root / "loader"
    sidecar_source.write_text(
        "#include <fcntl.h>\n"
        "#include <unistd.h>\n"
        "int bench_loaded(const char *path) {\n"
        "  int fd = open(path, O_WRONLY|O_CREAT|O_EXCL, 0600);\n"
        "  if (fd < 0) return 2;\n"
        "  close(fd);\n"
        "  return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    loader_source.write_text(
        "#include <dlfcn.h>\n"
        "#include <limits.h>\n"
        "#include <stdio.h>\n"
        "#include <string.h>\n"
        "#include <unistd.h>\n"
        "typedef int (*loaded_fn)(const char *);\n"
        "static void *load_from(const char *root) {\n"
        "  char path[PATH_MAX];\n"
        "  if (snprintf(path, sizeof(path), \"%s/libbench-sidecar.so\", root)"
        " >= (int)sizeof(path)) return NULL;\n"
        "  return dlopen(path, RTLD_NOW|RTLD_LOCAL);\n"
        "}\n"
        "int main(int argc, char **argv) {\n"
        "  char exe[PATH_MAX], cwd[PATH_MAX];\n"
        "  ssize_t n = readlink(\"/proc/self/exe\", exe, sizeof(exe)-1);\n"
        "  void *handle = NULL;\n"
        "  if (n > 0) {\n"
        "    exe[n] = 0;\n"
        "    char *slash = strrchr(exe, '/');\n"
        "    if (slash) { *slash = 0; handle = load_from(exe); }\n"
        "  }\n"
        "  if (!handle && getcwd(cwd, sizeof(cwd))) handle = load_from(cwd);\n"
        "  if (!handle || argc < 2) return 41;\n"
        "  loaded_fn loaded = (loaded_fn)dlsym(handle, \"bench_loaded\");\n"
        "  if (!loaded || loaded(argv[1]) != 0) return 42;\n"
        "  for (;;) pause();\n"
        "}\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "/usr/bin/gcc",
            "-shared",
            "-fPIC",
            "-o",
            str(sidecar),
            str(sidecar_source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "/usr/bin/gcc",
            "-o",
            str(loader),
            str(loader_source),
            "-ldl",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    sidecar_source.unlink()
    loader_source.unlink()
    return loader, sidecar


def _pin(path: Path) -> driver.SpawnPin:
    return driver.SpawnPin(
        kind="binary",
        pinned_path=path,
        pinned_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        required_argv_prefix=(str(path),),
    )


def _proof(root: Path, manifest_sha256: str = "a" * 64) -> driver.ReleaseDirectoryProof:
    fd = driver._open_release_directory(root)
    try:
        return driver._release_directory_proof(
            fd,
            manifest_sha256=manifest_sha256,
        )
    finally:
        os.close(fd)


def _env() -> dict[str, str]:
    return {
        "HOME": "/tmp",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    }


def _cleanup(child: driver.OwnedChild) -> None:
    try:
        signal.pidfd_send_signal(child.pidfd, signal.SIGKILL)
    except OSError:
        pass
    try:
        child.popen.wait(timeout=3)
    except subprocess.TimeoutExpired:
        child.popen.kill()
        child.popen.wait(timeout=3)
    try:
        os.close(child.pidfd)
    except OSError:
        pass


class TestManifestBoundBackendCwdElf:
    def test_sealed_memfd_with_inherited_wrong_cwd_cannot_load_sidecar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        release = tmp_path / "release"
        wrong = tmp_path / "wrong"
        wrong.mkdir()
        loader, _sidecar = _compile_loader_fixture(release)
        sentinel = tmp_path / "wrong-cwd-target-ran"
        monkeypatch.chdir(wrong)
        pin = _pin(loader)
        directory_fd = driver._open_release_directory(wrong)
        capability = driver._LauncherReleaseDirectory(
            directory_fd,
            pin,
            driver._release_directory_proof(
                directory_fd,
                manifest_sha256="a" * 64,
            ),
            _guard=driver._RELEASE_DIRECTORY_HANDLE_GUARD,
        )
        child: driver.OwnedChild | None = None
        try:
            child = driver.spawn_pinned(
                [str(loader), str(sentinel)],
                pin=pin,
                env=_env(),
                _release_directory=capability,
            )
            assert child.popen.wait(timeout=3) == 41
            assert not sentinel.exists()
        finally:
            os.close(directory_fd)
            if child is not None:
                _cleanup(child)

    def test_sealed_memfd_with_manifest_bound_pin_parent_loads_sidecar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        release = tmp_path / "release"
        wrong = tmp_path / "wrong"
        wrong.mkdir()
        loader, _sidecar = _compile_loader_fixture(release)
        sentinel = tmp_path / "manifest-bound-target-ran"
        monkeypatch.chdir(wrong)
        proof = _proof(release)
        launcher = driver.RealServerLauncher(_pin(loader), proof)

        child = launcher.spawn(
            [
                str(loader),
                str(sentinel),
                "--port",
                str(driver.BENCH_PORT),
            ],
            _env(),
        )
        try:
            deadline = time.monotonic() + 3
            while not sentinel.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert sentinel.exists()
            assert child.popen.poll() is None
            assert os.readlink(f"/proc/{child.pid}/cwd") == str(release)
        finally:
            _cleanup(child)
        assert _proof(release).snapshot_sha256 == proof.snapshot_sha256

    def test_manifest_bound_cwd_follows_changed_pin_parent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original_release = tmp_path / "original-release"
        wrong = tmp_path / "wrong"
        wrong.mkdir()
        original_loader, _sidecar = _compile_loader_fixture(original_release)
        original_pin = _pin(original_loader)
        changed_release = tmp_path / "changed-release"
        original_release.rename(changed_release)
        changed_loader = changed_release / original_loader.name
        changed_pin = replace(
            original_pin,
            pinned_path=changed_loader,
            required_argv_prefix=(str(changed_loader),),
        )
        sentinel = tmp_path / "changed-parent-target-ran"
        monkeypatch.chdir(wrong)
        launcher = driver.RealServerLauncher(
            changed_pin,
            _proof(changed_release),
        )

        child = launcher.spawn(
            [
                str(changed_loader),
                str(sentinel),
                "--port",
                str(driver.BENCH_PORT),
            ],
            _env(),
        )
        try:
            deadline = time.monotonic() + 3
            while not sentinel.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert sentinel.exists()
            assert child.popen.poll() is None
            assert os.readlink(f"/proc/{child.pid}/cwd") == str(changed_release)
        finally:
            _cleanup(child)


class TestReleaseDirectoryProofRefusals:
    def test_snapshot_canon_fixed_vector_covers_file_bytes_and_link_target(
        self, tmp_path: Path
    ) -> None:
        release = tmp_path / "release"
        release.mkdir()
        (release / "alpha").write_bytes(b"A")
        (release / "z").symlink_to("alpha")

        assert _proof(release).snapshot_sha256 == (
            "476dab19d6ab89d3f1c99980e14f6bff"
            "bd0ff55b138f8cc45ed4a82f7894bbc3"
        )

    def test_binary_cwd_has_no_second_path_authority(self) -> None:
        assert "cwd" not in inspect.signature(driver.spawn_pinned).parameters
        assert (
            "_release_directory_fd"
            not in inspect.signature(driver.spawn_pinned).parameters
        )
        assert "cwd" not in inspect.signature(driver.RealServerLauncher).parameters
        assert set(driver.ReleaseDirectoryProof.__dataclass_fields__) == {
            "manifest_sha256",
            "directory_dev",
            "directory_ino",
            "snapshot_sha256",
        }

    def test_binary_spawn_requires_launcher_owned_release_capability(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        monkeypatch.setattr(
            driver,
            "_sealed_executable_snapshot",
            lambda _pin: (_ for _ in ()).throw(
                AssertionError("binary snapshot reached without launcher authority")
            ),
        )

        with pytest.raises(driver.BenchRefusal) as caught:
            driver.spawn_pinned(
                [str(loader)],
                pin=_pin(loader),
                env=_env(),
            )

        assert caught.value.code == "spawn_failure"

    def test_release_capability_cannot_be_constructed_without_launcher_guard(
        self, tmp_path: Path
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        pin = _pin(loader)
        proof = _proof(release)
        directory_fd = driver._open_release_directory(release)
        try:
            with pytest.raises(TypeError):
                driver._LauncherReleaseDirectory(directory_fd, pin, proof)
        finally:
            os.close(directory_fd)

    def test_release_capability_is_bound_to_exact_launcher_pin(
        self, tmp_path: Path
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        launcher_pin = _pin(loader)
        equal_but_distinct_pin = replace(launcher_pin)
        proof = _proof(release)
        directory_fd = driver._open_release_directory(release)
        capability = driver._LauncherReleaseDirectory(
            directory_fd,
            launcher_pin,
            proof,
            _guard=driver._RELEASE_DIRECTORY_HANDLE_GUARD,
        )
        try:
            with pytest.raises(driver.BenchRefusal) as caught:
                driver.spawn_pinned(
                    [str(loader)],
                    pin=equal_but_distinct_pin,
                    env=_env(),
                    _release_directory=capability,
                )
        finally:
            os.close(directory_fd)

        assert caught.value.code == "spawn_failure"

    def test_direct_spawn_cannot_select_directory_b_for_pin_in_a(
        self, tmp_path: Path
    ) -> None:
        release_a = tmp_path / "release-a"
        release_b = tmp_path / "release-b"
        loader, _sidecar = _compile_loader_fixture(release_a)
        release_b.mkdir()
        sentinel = tmp_path / "wrong-authority-target-ran"
        directory_b_fd = driver._open_release_directory(release_b)
        child: driver.OwnedChild | None = None
        try:
            with pytest.raises(TypeError):
                child = driver.spawn_pinned(
                    [str(loader), str(sentinel)],
                    pin=_pin(loader),
                    env=_env(),
                    _release_directory_fd=directory_b_fd,
                )
        finally:
            os.close(directory_b_fd)
            if child is not None:
                _cleanup(child)
        assert child is None
        assert not sentinel.exists()

    @pytest.mark.parametrize("drift", ["inode", "snapshot"])
    def test_detached_or_drifted_proof_refuses_before_target(
        self, tmp_path: Path, drift: str
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        sentinel = tmp_path / f"{drift}-target-ran"
        proof = _proof(release)
        if drift == "inode":
            old = tmp_path / "old-release"
            release.rename(old)
            shutil.copytree(old, release, symlinks=True)
        else:
            (release / "unmanifested.log").write_bytes(b"new")
        launcher = driver.RealServerLauncher(_pin(loader), proof)

        with pytest.raises(driver.BenchRefusal, match="spawn_failure"):
            launcher.spawn(
                [
                    str(loader),
                    str(sentinel),
                    "--port",
                    str(driver.BENCH_PORT),
                ],
                _env(),
            )

        assert not sentinel.exists()

    @pytest.mark.parametrize("mutation", ["new", "changed", "deleted"])
    def test_top_level_release_mutation_refuses_tail_reproof(
        self, tmp_path: Path, mutation: str
    ) -> None:
        release = tmp_path / "release"
        loader, sidecar = _compile_loader_fixture(release)
        proof = _proof(release)
        launcher = driver.RealServerLauncher(_pin(loader), proof)
        if mutation == "new":
            (release / "relative.log").write_bytes(b"log")
        elif mutation == "changed":
            sidecar.write_bytes(sidecar.read_bytes() + b"drift")
        else:
            sidecar.unlink()

        with pytest.raises(driver.BenchRefusal, match="spawn_failure"):
            launcher.verify_release_directory()

    def test_wrong_manifest_proof_refuses_production_contract(
        self, tmp_path: Path
    ) -> None:
        from tests.test_cuda_bench_driver import _b7_production_contract_case

        config, pin, static, identity = _b7_production_contract_case(
            tmp_path,
            "vulkan_baseline",
        )
        proof = driver.ReleaseDirectoryProof(
            manifest_sha256="f" * 64,
            directory_dev=1,
            directory_ino=1,
            snapshot_sha256="e" * 64,
        )
        launcher = driver.RealServerLauncher(pin, proof)

        with pytest.raises(driver.BenchRefusal, match="spawn_failure"):
            driver._validate_production_execution_contract(
                config,
                launcher=launcher,
                static=static,
                runtime_identity=identity,
            )

    @pytest.mark.parametrize("link_kind", ["component", "final"])
    def test_symlinked_pin_parent_refuses_before_target(
        self, tmp_path: Path, link_kind: str
    ) -> None:
        actual_parent = tmp_path / "actual-parent"
        release = actual_parent / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        sentinel = tmp_path / f"{link_kind}-target-ran"
        proof = _proof(release)
        if link_kind == "component":
            linked_parent = tmp_path / "linked-parent"
            linked_parent.symlink_to(actual_parent, target_is_directory=True)
            linked_loader = linked_parent / "release" / loader.name
        else:
            linked_release = tmp_path / "linked-release"
            linked_release.symlink_to(release, target_is_directory=True)
            linked_loader = linked_release / loader.name
        launcher = driver.RealServerLauncher(
            replace(_pin(loader), pinned_path=linked_loader,
                    required_argv_prefix=(str(linked_loader),)),
            proof,
        )

        with pytest.raises(driver.BenchRefusal, match="spawn_failure"):
            launcher.spawn(
                [
                    str(linked_loader),
                    str(sentinel),
                    "--port",
                    str(driver.BENCH_PORT),
                ],
                _env(),
            )

        assert not sentinel.exists()

    def test_directory_open_failure_refuses_before_spawn(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        sentinel = tmp_path / "open-failure-target-ran"
        launcher = driver.RealServerLauncher(_pin(loader), _proof(release))
        monkeypatch.setattr(
            driver,
            "_open_release_directory",
            lambda _path: (_ for _ in ()).throw(OSError("open failed")),
        )
        monkeypatch.setattr(
            driver,
            "spawn_pinned",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("target spawn reached")
            ),
        )

        with pytest.raises(driver.BenchRefusal, match="spawn_failure"):
            launcher.spawn(
                [
                    str(loader),
                    str(sentinel),
                    "--port",
                    str(driver.BENCH_PORT),
                ],
                _env(),
            )
        assert not sentinel.exists()

    def test_actual_guard_fchdir_failure_refuses_before_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        sentinel = tmp_path / "fchdir-failure-target-ran"
        launcher = driver.RealServerLauncher(_pin(loader), _proof(release))
        real_guarded = driver._guarded_popen
        wrong_fd = os.open(loader, os.O_RDONLY)

        def pass_regular_file_to_guard(*args: object, **kwargs: object) -> object:
            kwargs["release_directory_fd"] = wrong_fd
            return real_guarded(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(driver, "_guarded_popen", pass_regular_file_to_guard)
        try:
            with pytest.raises(driver.BenchRefusal, match="spawn_failure"):
                launcher.spawn(
                    [
                        str(loader),
                        str(sentinel),
                        "--port",
                        str(driver.BENCH_PORT),
                    ],
                    _env(),
                )
        finally:
            os.close(wrong_fd)
        assert not sentinel.exists()

    @pytest.mark.parametrize(
        ("original_code", "expected_code"),
        [
            ("spawn_failure", "spawn_failure"),
            ("cleanup_incomplete", "cleanup_incomplete"),
            ("pid_reuse_detected", "pid_reuse_detected"),
        ],
    )
    def test_pre_admission_failure_rechecks_and_closes_held_directory_fd(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        original_code: str,
        expected_code: str,
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        launcher = driver.RealServerLauncher(_pin(loader), _proof(release))
        captured: list[int] = []

        def fail_after_mutation(
            *_args: object,
            _release_directory: object | None = None,
            **_kwargs: object,
        ) -> object:
            assert type(_release_directory) is driver._LauncherReleaseDirectory
            captured.append(_release_directory.fd)
            (release / "failure.log").write_bytes(b"drift")
            raise driver.BenchRefusal(original_code)

        monkeypatch.setattr(driver, "spawn_pinned", fail_after_mutation)
        with pytest.raises(driver.BenchRefusal) as exc:
            launcher.spawn(
                [str(loader), "--port", str(driver.BENCH_PORT)],
                _env(),
            )
        assert exc.value.code == expected_code
        assert len(captured) == 1
        with pytest.raises(OSError):
            os.fstat(captured[0])

    @pytest.mark.parametrize(
        "interruption",
        [KeyboardInterrupt(), SystemExit(73)],
        ids=["keyboard-interrupt", "system-exit"],
    )
    def test_release_drift_cannot_replace_interrupt_dominance(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        interruption: BaseException,
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        launcher = driver.RealServerLauncher(_pin(loader), _proof(release))

        def interrupt_after_mutation(
            *_args: object, **_kwargs: object
        ) -> object:
            (release / "failure.log").write_bytes(b"drift")
            raise interruption

        monkeypatch.setattr(driver, "spawn_pinned", interrupt_after_mutation)
        with pytest.raises(type(interruption)) as caught:
            launcher.spawn(
                [str(loader), "--port", str(driver.BENCH_PORT)],
                _env(),
            )
        assert caught.value is interruption

    def test_release_drift_carrier_reaches_handoff_and_capture_is_retired(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tmp_path.chmod(0o700)
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        launcher = driver.RealServerLauncher(_pin(loader), _proof(release))
        capture, stderr_write = driver._start_binary_stderr_capture()
        carrier = driver._BinarySpawnFailure(
            "spawn_failure",
            bootstrap_cleanup=driver._BootstrapCleanupResult(
                outcome="clean",
                observed_returncode=1,
                exited_before_cleanup_signal=True,
            ),
            stderr_capture=capture,
        )

        def fail_after_mutation(*_args: object, **_kwargs: object) -> object:
            (release / "failure.log").write_bytes(b"drift")
            raise carrier

        monkeypatch.setattr(driver, "spawn_pinned", fail_after_mutation)
        observed_carriers: list[driver._BinarySpawnFailure] = []
        real_dispose = driver._dispose_binary_spawn_failure

        def record_then_dispose(
            failure: driver._BinarySpawnFailure,
            **kwargs: object,
        ) -> object:
            observed_carriers.append(failure)
            return real_dispose(failure, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(
            driver,
            "_dispose_binary_spawn_failure",
            record_then_dispose,
        )
        journal = driver.PhaseJournal(
            "vulkan_baseline",
            journal_dir="journal",
            timestamp="release-drift",
            root=tmp_path,
        )
        os.close(stderr_write)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver._spawn_with_interrupt_handoff(
                    launcher,
                    [str(loader), "--port", str(driver.BENCH_PORT)],
                    _env(),
                    admit=lambda _child: (_ for _ in ()).throw(
                        AssertionError("drifted child admitted")
                    ),
                    journal=journal,
                    clock=driver.SystemClock(),
                    cycle=1,
                    attempt_root=tmp_path,
                )
            assert exc.value.code == "spawn_failure"
            assert observed_carriers == [carrier]
            assert capture.consumed is True
            assert capture.thread_alive is False
            assert capture._control_write is None
            with pytest.raises(OSError):
                os.fstat(capture._stderr_read)
            with pytest.raises(OSError):
                os.fstat(capture._control_read)
        finally:
            journal.close()

    def test_common_phase_tail_reproof_blocks_release_mutation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        launcher = driver.RealServerLauncher(_pin(loader), _proof(release))
        (release / "late-core").write_bytes(b"new residue")
        before = driver.cm.ContainmentSnapshot(
            phase="vulkan_baseline",
            boundary="before",
            timestamp="2026-08-01T12:00:00Z",
            screen_flag_value="0",
            active_state="inactive",
            substate="dead",
            enabled_state="disabled",
            maez_active_state="inactive",
            maez_process_screen_flag_value=None,
            port_closed=True,
            flag_source_sha256="a" * 64,
            vision_unit_sha256="b" * 64,
        )
        after = replace(before, boundary="after")
        monkeypatch.setattr(
            driver,
            "_try_append_phase_transition",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            driver,
            "_persist_containment",
            lambda *_args, **_kwargs: (tmp_path / "after.json", "c" * 64),
        )
        providers = SimpleNamespace(
            tier="production",
            server_launcher=launcher,
            kernel_log=SimpleNamespace(
                cursor=lambda: "cursor-after",
                count_signatures=lambda _start, _end: dict.fromkeys(
                    driver.KERNEL_COUNTER_KEYS, 0
                ),
            ),
            containment=SimpleNamespace(capture=lambda _phase, _boundary: after),
            clock=SimpleNamespace(now_utc=lambda: "2026-08-01T12:00:01Z"),
        )
        static = SimpleNamespace(
            checks={"flag_source": "a" * 64, "vision_unit": "b" * 64}
        )

        tail = driver._collect_phase_tail(
            config=SimpleNamespace(phase="vulkan_baseline"),
            providers=providers,
            attempt_root=tmp_path,
            static=static,
            containment_before=before,
            kernel_cursor_before="cursor-before",
            journal=object(),
        )

        assert tail.refusal is not None
        assert tail.refusal.code == "spawn_failure"

    def test_release_drift_cannot_replace_containment_refusal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        launcher = driver.RealServerLauncher(_pin(loader), _proof(release))
        (release / "late-core").write_bytes(b"new residue")
        before = driver.cm.ContainmentSnapshot(
            phase="vulkan_baseline",
            boundary="before",
            timestamp="2026-08-01T12:00:00Z",
            screen_flag_value="0",
            active_state="inactive",
            substate="dead",
            enabled_state="disabled",
            maez_active_state="inactive",
            maez_process_screen_flag_value=None,
            port_closed=True,
            flag_source_sha256="a" * 64,
            vision_unit_sha256="b" * 64,
        )
        after = replace(before, boundary="after", screen_flag_value="1")
        monkeypatch.setattr(
            driver,
            "_try_append_phase_transition",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            driver,
            "_persist_containment",
            lambda *_args, **_kwargs: (tmp_path / "after.json", "c" * 64),
        )
        providers = SimpleNamespace(
            tier="production",
            server_launcher=launcher,
            kernel_log=SimpleNamespace(
                cursor=lambda: "cursor-after",
                count_signatures=lambda _start, _end: dict.fromkeys(
                    driver.KERNEL_COUNTER_KEYS, 0
                ),
            ),
            containment=SimpleNamespace(capture=lambda _phase, _boundary: after),
            clock=SimpleNamespace(now_utc=lambda: "2026-08-01T12:00:01Z"),
        )
        static = SimpleNamespace(
            checks={"flag_source": "a" * 64, "vision_unit": "b" * 64}
        )

        tail = driver._collect_phase_tail(
            config=SimpleNamespace(phase="vulkan_baseline"),
            providers=providers,
            attempt_root=tmp_path,
            static=static,
            containment_before=before,
            kernel_cursor_before="cursor-before",
            journal=object(),
        )

        assert tail.refusal is not None
        assert tail.refusal.code == "containment_violation"

    @pytest.mark.parametrize("prior_code", ["journal_failure", "kernel_unmatched"])
    def test_release_drift_preserves_prior_tail_refusal(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        prior_code: str,
    ) -> None:
        release = tmp_path / "release"
        loader, _sidecar = _compile_loader_fixture(release)
        launcher = driver.RealServerLauncher(_pin(loader), _proof(release))
        (release / "late-core").write_bytes(b"new residue")
        before = driver.cm.ContainmentSnapshot(
            phase="vulkan_baseline",
            boundary="before",
            timestamp="2026-08-01T12:00:00Z",
            screen_flag_value="0",
            active_state="inactive",
            substate="dead",
            enabled_state="disabled",
            maez_active_state="inactive",
            maez_process_screen_flag_value=None,
            port_closed=True,
            flag_source_sha256="a" * 64,
            vision_unit_sha256="b" * 64,
        )
        after = replace(before, boundary="after")
        monkeypatch.setattr(
            driver,
            "_try_append_phase_transition",
            lambda *_args, **_kwargs: (
                driver.BenchRefusal("journal_failure")
                if prior_code == "journal_failure"
                else None
            ),
        )
        monkeypatch.setattr(
            driver,
            "_persist_containment",
            lambda *_args, **_kwargs: (tmp_path / "after.json", "c" * 64),
        )
        counters = dict.fromkeys(driver.KERNEL_COUNTER_KEYS, 0)
        if prior_code == "kernel_unmatched":
            counters["Xid"] = 1
        providers = SimpleNamespace(
            tier="production",
            server_launcher=launcher,
            kernel_log=SimpleNamespace(
                cursor=lambda: "cursor-after",
                count_signatures=lambda _start, _end: counters,
            ),
            containment=SimpleNamespace(capture=lambda _phase, _boundary: after),
            clock=SimpleNamespace(now_utc=lambda: "2026-08-01T12:00:01Z"),
        )
        static = SimpleNamespace(
            checks={"flag_source": "a" * 64, "vision_unit": "b" * 64}
        )

        tail = driver._collect_phase_tail(
            config=SimpleNamespace(phase="vulkan_baseline"),
            providers=providers,
            attempt_root=tmp_path,
            static=static,
            containment_before=before,
            kernel_cursor_before="cursor-before",
            journal=object(),
        )

        assert tail.refusal is not None
        assert tail.refusal.code == prior_code

    @pytest.mark.parametrize("mutation", ["new", "changed", "deleted"])
    def test_phase_publication_cannot_complete_after_release_mutation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mutation: str,
    ) -> None:
        from tests.test_cuda_bench_driver import _b7_harness, _b7_wrapper

        tmp_path.chmod(0o700)
        release = tmp_path / "release"
        loader, sidecar = _compile_loader_fixture(release)
        launcher = driver.RealServerLauncher(_pin(loader), _proof(release))
        harness = _b7_harness(
            tmp_path,
            nonce=hashlib.sha256(mutation.encode()).hexdigest(),
        )
        real_collect_tail = driver._collect_phase_tail
        mutated = False

        def mutate_then_collect_tail(**kwargs: object) -> object:
            nonlocal mutated
            assert mutated is False
            mutated = True
            if mutation == "new":
                (release / "relative.log").write_bytes(b"new")
            elif mutation == "changed":
                sidecar.write_bytes(sidecar.read_bytes() + b"changed")
            else:
                sidecar.unlink()
            providers = harness.providers
            previous_tier = providers.tier
            previous_launcher = providers.server_launcher
            object.__setattr__(providers, "tier", "production")
            object.__setattr__(providers, "server_launcher", launcher)
            try:
                return real_collect_tail(**kwargs)  # type: ignore[arg-type]
            finally:
                object.__setattr__(providers, "server_launcher", previous_launcher)
                object.__setattr__(providers, "tier", previous_tier)

        monkeypatch.setattr(
            driver,
            "_collect_phase_tail",
            mutate_then_collect_tail,
        )

        path = driver.run_phase(
            harness.config,
            harness.providers,
            root=tmp_path,
        )
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert mutated is True
        assert fields["outcome"] == "spawn_failure"
        assert not list(tmp_path.rglob("vulkan_baseline-completed.json"))
        assert not list(tmp_path.rglob("*command-completion*.json"))
