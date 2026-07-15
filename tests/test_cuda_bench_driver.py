"""Tests for the inert CUDA bench driver's private core."""

from __future__ import annotations

import errno
import inspect
import json
import os
import stat
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Iterator, Mapping
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts import cuda_bench_driver as driver


EXPECTED_REFUSALS = frozenset(
    {
        "tier_mismatch",
        "preflight_service_active",
        "preflight_port_open",
        "preflight_gpu_occupied",
        "preflight_bench_port_busy",
        "identity_mismatch",
        "corpus_unavailable",
        "gpu_scope_violation",
        "authorization_missing",
        "authorization_malformed",
        "authorization_not_yet_valid",
        "authorization_expired",
        "authorization_boot_mismatch",
        "authorization_scope_mismatch",
        "authorization_consumed",
        "continuation_missing",
        "continuation_parent_mismatch",
        "containment_violation",
        "readiness_timeout",
        "alias_mismatch",
        "backend_unproven",
        "http_timeout",
        "crash",
        "hang",
        "malformed_response",
        "response_too_large",
        "mtp_unproven",
        "topology_drift",
        "kernel_unmatched",
        "unload_incomplete",
        "filesystem_hazard",
        "pid_reuse_detected",
        "rehearsal_artifact_rejected",
        "provider_uncertain",
        "spawn_failure",
        "journal_failure",
        "interrupted",
        "cleanup_incomplete",
        "assembly_refused",
        "unscorable",
    }
)

EXPECTED_SCHEMAS = {
    "STATIC_PREFLIGHT_SCHEMA": "cuda_bench_driver.static_preflight.v1",
    "PHASE_PACKET_SCHEMA": "cuda_bench_driver.phase_packet.v1",
    "REFUSAL_SCHEMA": "cuda_bench_driver.refusal.v1",
    "WINDOW_AUTHORIZATION_SCHEMA": "cuda_bench_driver.window_authorization.v1",
    "CONTINUATION_SCHEMA": "cuda_bench_driver.continuation.v1",
    "CONSUMPTION_RECEIPT_SCHEMA": "cuda_bench_driver.consumption_receipt.v1",
    "TURN_MANIFEST_SCHEMA": "cuda_bench_driver.turn_manifest.v1",
    "TURN_ARTIFACT_SCHEMA": "cuda_bench_driver.turn_artifact.v1",
    "CONTAINMENT_SNAPSHOT_SCHEMA": "cuda_bench_driver.containment_snapshot.v1",
    "RUNTIME_IDENTITY_SCHEMA": "cuda_bench_driver.runtime_identity.v1",
    "ASSEMBLE_RECEIPT_SCHEMA": "cuda_bench_assemble.receipt.v1",
    "REHEARSAL_PACKET_SCHEMA": "cuda_bench_rehearsal.packet.v1",
}


@pytest.fixture
def private_root(tmp_path: Path) -> Path:
    root = tmp_path / "bench"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return root


def _private_file(path: Path, payload: bytes = b"evidence") -> None:
    path.write_bytes(payload)
    os.chmod(path, 0o600)


def _assert_refusal(exc: pytest.ExceptionInfo[driver.BenchRefusal], code: str) -> None:
    assert exc.value.code == code


class _ExplodingMapping(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        raise RuntimeError(f"unexpected lookup: {key}")

    def __iter__(self) -> Iterator[str]:
        raise RuntimeError("mapping projection failed")

    def __len__(self) -> int:
        return 1


class _StringSubclass(str):
    pass


@dataclass
class _TieredFake:
    tier: str

    def is_active(self, _unit: str) -> str:
        raise AssertionError("factory invoked provider")

    def is_free(self, _port: int) -> bool:
        raise AssertionError("factory invoked provider")

    def enumerate_uuids(self) -> list[str]:
        raise AssertionError("factory invoked provider")

    def inventory(self, _uuid: str) -> list[tuple[int, str]]:
        raise AssertionError("factory invoked provider")

    def memory(self, _uuid: str) -> tuple[float, int]:
        raise AssertionError("factory invoked provider")

    def cursor(self) -> str:
        raise AssertionError("factory invoked provider")

    def count_signatures(self, _start: str, _end: str) -> dict[str, int]:
        raise AssertionError("factory invoked provider")

    def read_maps(self, _pid: int) -> str:
        raise AssertionError("factory invoked provider")

    def spawn(self, _argv: list[str], _env: dict[str, str]) -> object:
        raise AssertionError("factory invoked provider")

    def health(self, _port: int) -> bool:
        raise AssertionError("factory invoked provider")

    def models(self, _port: int) -> list[str]:
        raise AssertionError("factory invoked provider")

    def stream(self, _port: int, _prompt: str) -> object:
        raise AssertionError("factory invoked provider")

    def consume(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("factory invoked provider")

    def encode(self, _kind: str, _document: dict[str, object]) -> bytes:
        raise AssertionError("factory invoked provider")

    def artifact_dir(self, _kind: str) -> str:
        raise AssertionError("factory invoked provider")

    def now_utc(self) -> str:
        raise AssertionError("factory invoked provider")

    def monotonic(self) -> float:
        raise AssertionError("factory invoked provider")

    def create(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("factory invoked provider")


class _ForgedTier:
    def __eq__(self, _other: object) -> bool:
        return True


class _FakeSocket:
    def __init__(
        self,
        *,
        bind_error: OSError | None = None,
        close_error: OSError | None = None,
    ) -> None:
        self.bind_error = bind_error
        self.close_error = close_error
        self.closed = False

    def bind(self, _address: tuple[str, int]) -> None:
        if self.bind_error is not None:
            raise self.bind_error

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def _provider_components(tier: str) -> dict[str, object]:
    """Protocol-shaped inert values for testing the sealed B3 assembly path."""

    zero_counts = {
        "reusemappingdbMap": 0,
        "pMapCb": 0,
        "mmuWalkMap": 0,
        "NV_ERR_NO_MEMORY": 0,
        "Xid": 0,
        "unmatched_nvrm": 0,
    }
    if tier == "production":
        service_state: object = driver.RealServiceStateProvider(
            runner=lambda _argv: (_ for _ in ()).throw(AssertionError("live call"))
        )
        port_probe: object = driver.RealPortProbe()
        gpu: object = driver.RealGpuProvider(
            runner=lambda _argv: (_ for _ in ()).throw(AssertionError("live call"))
        )
        kernel: object = driver.RealKernelLogProvider(
            runner=lambda _argv: (_ for _ in ()).throw(AssertionError("live call"))
        )
        maps: object = driver.RealBackendMapProvider()
        clock: object = driver.SystemClock()
        journal_factory: object = driver.ProductionJournalFactory()
        artifact_policy: object = driver.ProductionArtifactPolicy()
        authorization_gate: object = driver.RealAuthorizationGate(artifact_policy)
    else:
        service_state = driver.SyntheticServiceState({})
        port_probe = driver.SyntheticPortProbe(set())
        gpu = driver.SyntheticGpu([], [], [])
        kernel = driver.SyntheticKernelLog(zero_counts)
        maps = driver.SyntheticBackendMap({})
        clock = driver.FrozenClock("2026-07-14T12:00:00Z")
        journal_factory = driver.RehearsalJournalFactory()
        artifact_policy = driver.RehearsalArtifactPolicy()
        authorization_gate = driver.RehearsalAuthorizationGate(artifact_policy)
    return {
        "service_state": service_state,
        "port_probe": port_probe,
        "gpu": gpu,
        "kernel_log": kernel,
        "backend_maps": maps,
        "server_launcher": _TieredFake(tier),
        "server_client": _TieredFake(tier),
        "authorization_gate": authorization_gate,
        "artifact_policy": artifact_policy,
        "clock": clock,
        "journal_factory": journal_factory,
    }


class TestFrozenContract:
    def test_constants_are_frozen(self) -> None:
        assert driver.BENCH_ROOT == Path("/home/rohit/maez/local/cuda_migration_bench")
        assert driver.BENCH_PORT == 18080
        assert driver.PRODUCTION_PORTS == (8080, 8081, 8082)
        assert driver.READINESS_TIMEOUT_S == 300
        assert driver.REQUEST_TIMEOUT_MS == 30_000
        assert driver.SIGTERM_GRACE_S == 10
        assert driver.RESPONSE_BYTE_CAP == 4 * 1024 * 1024
        assert driver.TURN_ARTIFACT_BYTE_CAP == 8 * 1024 * 1024
        assert driver.WINDOW_TTL_S == 14_400
        assert driver.CONTINUATION_TTL_S == 3_600
        assert driver.KILL_WAIT_S == 15
        assert driver.LISTENER_WAIT_S == 10
        assert driver.UNLOAD_WAIT_S == 60
        assert driver.FROZEN_BENCH_ARGS_SHA256 == (
            "7fd627e1132ff30fb7f45df2cbf83d166002b0a0c56bcd07e169eca2180bd413"
        )

    def test_schema_names_are_frozen(self) -> None:
        assert {name: getattr(driver, name) for name in EXPECTED_SCHEMAS} == EXPECTED_SCHEMAS

    def test_refusal_vocabulary_is_the_exact_forty_entry_canon(self) -> None:
        assert driver.REFUSAL_VOCABULARY == EXPECTED_REFUSALS
        assert len(driver.REFUSAL_VOCABULARY) == 40

    def test_bench_refusal_accepts_only_the_closed_vocabulary(self) -> None:
        refusal = driver.BenchRefusal("filesystem_hazard")
        assert refusal.code == "filesystem_hazard"
        assert str(refusal) == "filesystem_hazard"
        with pytest.raises(ValueError, match="closed_refusal"):
            driver.BenchRefusal("not_a_code")


class TestPrivateReads:
    def test_good_private_file_roundtrips(self, private_root: Path) -> None:
        evidence = private_root / "evidence.bin"
        _private_file(evidence, b"bound evidence")

        assert driver.open_bench_file("evidence.bin", root=private_root) == (b"bound evidence")

    def test_symlinked_intermediate_component_refuses(
        self, private_root: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o700)
        _private_file(outside / "evidence.bin")
        (private_root / "link").symlink_to(outside, target_is_directory=True)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file("link/evidence.bin", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")

    def test_symlinked_final_file_refuses(self, private_root: Path, tmp_path: Path) -> None:
        outside = tmp_path / "outside.bin"
        _private_file(outside)
        (private_root / "evidence.bin").symlink_to(outside)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file("evidence.bin", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")

    def test_hardlinked_file_refuses(self, private_root: Path) -> None:
        source = private_root / "source.bin"
        _private_file(source)
        os.link(source, private_root / "evidence.bin")

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file("evidence.bin", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")

    def test_read_revalidates_final_inode_after_bytes_are_read(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        evidence = private_root / "evidence.bin"
        _private_file(evidence)
        real_read = driver.os.read
        linked = False

        def link_during_read(fd: int, size: int) -> bytes:
            nonlocal linked
            data = real_read(fd, size)
            if data and not linked:
                linked = True
                os.link(evidence, private_root / "unexpected-hardlink.bin")
            return data

        monkeypatch.setattr(driver.os, "read", link_during_read)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file("evidence.bin", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")

    def test_same_size_second_half_rewrite_during_multichunk_read_refuses(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = b"a" * (1024 * 1024 + 4096)
        evidence = private_root / "evidence.bin"
        _private_file(evidence, payload)
        real_read = driver.os.read
        rewritten = False

        def rewrite_after_first_chunk(fd: int, size: int) -> bytes:
            nonlocal rewritten
            chunk = real_read(fd, size)
            if chunk and not rewritten:
                rewritten = True
                rewrite_fd = os.open(evidence, os.O_WRONLY | os.O_NOFOLLOW)
                try:
                    os.pwrite(rewrite_fd, b"b" * 4096, len(payload) - 4096)
                    os.fsync(rewrite_fd)
                finally:
                    os.close(rewrite_fd)
            return chunk

        monkeypatch.setattr(driver.os, "read", rewrite_after_first_chunk)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file("evidence.bin", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert rewritten is True

    def test_non_private_mode_refuses(self, private_root: Path) -> None:
        evidence = private_root / "evidence.bin"
        _private_file(evidence)
        os.chmod(evidence, 0o644)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file("evidence.bin", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")

    def test_oversized_file_refuses(self, private_root: Path) -> None:
        evidence = private_root / "evidence.bin"
        with evidence.open("wb") as handle:
            handle.truncate(driver.TURN_ARTIFACT_BYTE_CAP + 1)
        os.chmod(evidence, 0o600)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file("evidence.bin", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")

    def test_same_size_rewrite_during_multichunk_read_refuses(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chunk_size = 1024 * 1024
        evidence = private_root / "evidence.bin"
        _private_file(evidence, b"A" * chunk_size + b"B" * chunk_size)
        real_read = driver.os.read
        read_count = 0

        def rewrite_after_first_chunk(fd: int, size: int) -> bytes:
            nonlocal read_count
            data = real_read(fd, size)
            read_count += 1
            if read_count == 1:
                with evidence.open("r+b") as handle:
                    handle.seek(chunk_size)
                    handle.write(b"C" * chunk_size)
                    handle.flush()
                    os.fsync(handle.fileno())
            return data

        monkeypatch.setattr(driver.os, "read", rewrite_after_first_chunk)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file("evidence.bin", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")

    @pytest.mark.parametrize("ancestor", ["root", "intermediate"])
    def test_ancestor_privacy_drift_during_read_refuses(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        ancestor: str,
    ) -> None:
        outer = private_root / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True, mode=0o700)
        os.chmod(outer, 0o700)
        os.chmod(inner, 0o700)
        _private_file(inner / "evidence.bin", b"evidence")
        drift_target = private_root if ancestor == "root" else outer
        real_read = driver.os.read
        drifted = False

        def drift_after_read(fd: int, size: int) -> bytes:
            nonlocal drifted
            data = real_read(fd, size)
            if data and not drifted:
                drifted = True
                os.chmod(drift_target, 0o755)
            return data

        monkeypatch.setattr(driver.os, "read", drift_after_read)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver.open_bench_file("outer/inner/evidence.bin", root=private_root)
            _assert_refusal(exc, "filesystem_hazard")
        finally:
            os.chmod(drift_target, 0o700)
        assert drifted is True

    def test_root_replacement_during_read_refuses(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        evidence = private_root / "evidence.bin"
        _private_file(evidence, b"evidence")
        moved_root = private_root.with_name(f"{private_root.name}-moved")
        real_read = driver.os.read
        replaced = False

        def replace_root_after_read(fd: int, size: int) -> bytes:
            nonlocal replaced
            data = real_read(fd, size)
            if data and not replaced:
                replaced = True
                os.rename(private_root, moved_root)
                private_root.mkdir(mode=0o700)
            return data

        monkeypatch.setattr(driver.os, "read", replace_root_after_read)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file("evidence.bin", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert replaced is True
        assert (moved_root / "evidence.bin").read_bytes() == b"evidence"
        assert not (private_root / "evidence.bin").exists()

    @pytest.mark.parametrize("relative", ["../escape.bin", "/tmp/escape.bin"])
    def test_escape_paths_refuse(self, private_root: Path, relative: str) -> None:
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.open_bench_file(relative, root=private_root)
        _assert_refusal(exc, "filesystem_hazard")


class TestPrivateWrites:
    def test_write_roundtrips_and_creates_private_components(self, private_root: Path) -> None:
        written = driver.write_private_file(
            "receipts/nested/evidence.json", b"{}\n", root=private_root
        )

        assert written == private_root / "receipts/nested/evidence.json"
        assert driver.open_bench_file("receipts/nested/evidence.json", root=private_root) == b"{}\n"
        assert (private_root / "receipts").stat().st_mode & 0o777 == 0o700
        assert (private_root / "receipts/nested").stat().st_mode & 0o777 == 0o700
        assert written.stat().st_mode & 0o777 == 0o600

    def test_created_components_are_0700_under_owner_private_umask(
        self, private_root: Path
    ) -> None:
        previous_umask = os.umask(0o077)
        try:
            written = driver.write_private_file(
                "receipts/nested/evidence.json", b"{}\n", root=private_root
            )
        finally:
            os.umask(previous_umask)

        assert (private_root / "receipts").stat().st_mode & 0o777 == 0o700
        assert (private_root / "receipts/nested").stat().st_mode & 0o777 == 0o700
        assert written.stat().st_mode & 0o777 == 0o600

    def test_pathological_umask_refuses_instead_of_repairing_by_name(
        self, private_root: Path
    ) -> None:
        created = private_root / "receipts"
        previous_umask = os.umask(0o777)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver.write_private_file("receipts/evidence.json", b"{}\n", root=private_root)
            _assert_refusal(exc, "filesystem_hazard")
        finally:
            os.umask(previous_umask)
            if created.exists() and not created.is_symlink():
                os.chmod(created, 0o700)

        assert not (private_root / "receipts/evidence.json").exists()

    def test_mkdir_swap_to_symlink_refuses_without_chmodding_outside(
        self,
        private_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o711)
        os.chmod(outside, 0o711)
        original_mode = outside.stat().st_mode & 0o777
        real_mkdir = driver.os.mkdir

        def swap_created_directory(
            path: str, mode: int = 0o777, *, dir_fd: int | None = None
        ) -> None:
            real_mkdir(path, mode=mode, dir_fd=dir_fd)
            os.rmdir(path, dir_fd=dir_fd)
            os.symlink(outside, path, target_is_directory=True, dir_fd=dir_fd)

        monkeypatch.setattr(driver.os, "mkdir", swap_created_directory)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.write_private_file("receipts/evidence.json", b"{}\n", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert outside.stat().st_mode & 0o777 == original_mode
        assert not (outside / "evidence.json").exists()

    def test_second_write_refuses_instead_of_overwriting(self, private_root: Path) -> None:
        driver.write_private_file("evidence.json", b"first", root=private_root)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.write_private_file("evidence.json", b"second", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert (private_root / "evidence.json").read_bytes() == b"first"

    def test_anonymous_publish_is_noninheritable_and_moves_nlink_zero_to_one(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_link = driver.os.link
        observations: list[tuple[bool, int, int]] = []

        def observe_link(
            source: str,
            target: str,
            *,
            dst_dir_fd: int,
            follow_symlinks: bool,
        ) -> None:
            fd = int(source.rsplit("/", 1)[1])
            before = os.fstat(fd)
            real_link(
                source,
                target,
                dst_dir_fd=dst_dir_fd,
                follow_symlinks=follow_symlinks,
            )
            observations.append((os.get_inheritable(fd), before.st_nlink, os.fstat(fd).st_nlink))

        monkeypatch.setattr(driver.os, "link", observe_link)
        driver.write_private_file("evidence.json", b"complete", root=private_root)

        assert observations == [(False, 0, 1)]
        assert (private_root / "evidence.json").read_bytes() == b"complete"

    def test_prelink_fsync_failure_leaves_no_final_name(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_fsync = driver.os.fsync

        def fail_anonymous_file_fsync(fd: int) -> None:
            if stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("injected prelink fsync failure")
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", fail_anonymous_file_fsync)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.write_private_file("evidence.json", b"complete", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert not (private_root / "evidence.json").exists()

    def test_postlink_parent_fsync_failure_keeps_complete_published_file(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_fsync = driver.os.fsync

        def fail_parent_fsync(fd: int) -> None:
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("injected postlink parent fsync failure")
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", fail_parent_fsync)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.write_private_file("evidence.json", b"complete", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert (private_root / "evidence.json").read_bytes() == b"complete"

    @pytest.mark.parametrize("drift_point", ["link", "fsync"])
    def test_parent_drift_after_publication_refuses_but_keeps_complete_file(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        drift_point: str,
    ) -> None:
        real_link = driver.os.link
        real_fsync = driver.os.fsync

        def drift_after_link(
            source: str,
            target: str,
            *,
            dst_dir_fd: int,
            follow_symlinks: bool,
        ) -> None:
            real_link(
                source,
                target,
                dst_dir_fd=dst_dir_fd,
                follow_symlinks=follow_symlinks,
            )
            os.fchmod(dst_dir_fd, 0o755)

        def drift_after_fsync(fd: int) -> None:
            real_fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                os.fchmod(fd, 0o755)

        if drift_point == "link":
            monkeypatch.setattr(driver.os, "link", drift_after_link)
        else:
            monkeypatch.setattr(driver.os, "fsync", drift_after_fsync)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver.write_private_file("evidence.json", b"complete", root=private_root)
            _assert_refusal(exc, "filesystem_hazard")
        finally:
            os.chmod(private_root, 0o700)
        assert (private_root / "evidence.json").read_bytes() == b"complete"

    @pytest.mark.parametrize("ancestor", ["root", "intermediate"])
    def test_ancestor_privacy_drift_after_publication_refuses(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        ancestor: str,
    ) -> None:
        outer = private_root / "outer"
        inner = outer / "inner"
        inner.mkdir(parents=True, mode=0o700)
        os.chmod(outer, 0o700)
        os.chmod(inner, 0o700)
        drift_target = private_root if ancestor == "root" else outer
        real_fsync = driver.os.fsync
        drifted = False

        def drift_during_parent_fsync(fd: int) -> None:
            nonlocal drifted
            real_fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not drifted:
                drifted = True
                os.chmod(drift_target, 0o755)

        monkeypatch.setattr(driver.os, "fsync", drift_during_parent_fsync)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver.write_private_file(
                    "outer/inner/evidence.json",
                    b"complete",
                    root=private_root,
                )
            _assert_refusal(exc, "filesystem_hazard")
        finally:
            os.chmod(drift_target, 0o700)
        assert drifted is True
        assert (inner / "evidence.json").read_bytes() == b"complete"

    def test_root_replacement_after_publication_refuses_false_return_path(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        moved_root = private_root.with_name(f"{private_root.name}-moved")
        real_fsync = driver.os.fsync
        replaced = False

        def replace_root_during_parent_fsync(fd: int) -> None:
            nonlocal replaced
            real_fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not replaced:
                replaced = True
                os.rename(private_root, moved_root)
                private_root.mkdir(mode=0o700)

        monkeypatch.setattr(driver.os, "fsync", replace_root_during_parent_fsync)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.write_private_file("evidence.json", b"complete", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert replaced is True
        assert (moved_root / "evidence.json").read_bytes() == b"complete"
        assert not (private_root / "evidence.json").exists()

    @pytest.mark.parametrize("drift", ["mode", "hardlink"])
    def test_published_inode_drift_during_parent_fsync_refuses(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        drift: str,
    ) -> None:
        evidence = private_root / "evidence.json"
        hardlink = private_root / "evidence-hardlink.json"
        real_fsync = driver.os.fsync
        drifted = False

        def drift_during_parent_fsync(fd: int) -> None:
            nonlocal drifted
            real_fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not drifted:
                drifted = True
                if drift == "mode":
                    os.chmod(evidence, 0o644)
                else:
                    os.link(evidence, hardlink)

        monkeypatch.setattr(driver.os, "fsync", drift_during_parent_fsync)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver.write_private_file("evidence.json", b"complete", root=private_root)
            _assert_refusal(exc, "filesystem_hazard")
        finally:
            if evidence.exists():
                os.chmod(evidence, 0o600)
        assert drifted is True
        assert evidence.read_bytes() == b"complete"

    def test_failed_publication_never_uses_name_based_unlink(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_write = driver.os.write
        real_unlink = driver.os.unlink
        unlink_calls: list[tuple[object, dict[str, object]]] = []
        writes = 0

        def partial_then_error(fd: int, data: object) -> int:
            nonlocal writes
            writes += 1
            if writes == 1:
                return real_write(fd, memoryview(data)[:1])
            raise OSError("injected partial write")

        def record_unlink(path: object, **kwargs: object) -> None:
            unlink_calls.append((path, kwargs))
            real_unlink(path, **kwargs)

        monkeypatch.setattr(driver.os, "write", partial_then_error)
        monkeypatch.setattr(driver.os, "unlink", record_unlink)
        with pytest.raises(driver.BenchRefusal):
            driver.write_private_file("evidence.json", b"partial", root=private_root)
        assert unlink_calls == []
        assert not (private_root / "evidence.json").exists()

    def test_partial_write_failure_leaves_no_final_entry(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_write = driver.os.write
        calls = 0

        def partial_then_error(fd: int, data: object) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, memoryview(data)[:1])
            raise OSError("injected partial write")

        monkeypatch.setattr(driver.os, "write", partial_then_error)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.write_private_file("evidence.json", b"partial", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert not (private_root / "evidence.json").exists()

    @pytest.mark.parametrize("relative", ["../escape.json", "/tmp/escape.json"])
    def test_escape_paths_refuse_without_writing(
        self, private_root: Path, tmp_path: Path, relative: str
    ) -> None:
        outside = tmp_path / "escape.json"

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.write_private_file(relative, b"no", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert not outside.exists()

    def test_symlinked_intermediate_refuses_without_escape(
        self, private_root: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o700)
        (private_root / "link").symlink_to(outside, target_is_directory=True)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.write_private_file("link/evidence.json", b"no", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")
        assert not (outside / "evidence.json").exists()

    @pytest.mark.parametrize("operation", ["read", "write"])
    def test_nul_component_is_typed_filesystem_hazard(
        self, private_root: Path, operation: str
    ) -> None:
        with pytest.raises(driver.BenchRefusal) as exc:
            if operation == "read":
                driver.open_bench_file("bad\0name", root=private_root)
            else:
                driver.write_private_file("bad\0name", b"evidence", root=private_root)
        _assert_refusal(exc, "filesystem_hazard")


class TestPhaseJournal:
    _TIMESTAMP = "2026-07-14T12:34:56Z"

    def _journal(self, root: Path) -> driver.PhaseJournal:
        return driver.PhaseJournal(
            "vulkan_baseline",
            journal_dir="journals",
            timestamp=self._TIMESTAMP,
            root=root,
        )

    def test_directory_and_timestamp_are_required_keyword_only_inputs(self) -> None:
        signature = inspect.signature(driver.PhaseJournal)
        for name in ("journal_dir", "timestamp"):
            parameter = signature.parameters[name]
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
            assert parameter.default is inspect.Parameter.empty

    def test_birth_uses_all_frozen_fd_flags(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_open = driver.os.open
        journal_flags: list[int] = []

        def recording_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
            if (flags & os.O_TMPFILE) == os.O_TMPFILE:
                journal_flags.append(flags)
            return real_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(driver.os, "open", recording_open)
        journal = self._journal(private_root)
        journal.close()

        assert len(journal_flags) == 1
        required = os.O_WRONLY | os.O_TMPFILE | os.O_APPEND
        assert journal_flags[0] & required == required
        assert journal_flags[0] & os.O_EXCL == 0

    def test_birth_prelink_fsync_failure_leaves_no_ghost_name(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_fsync = driver.os.fsync

        def fail_anonymous_file_fsync(fd: int) -> None:
            if stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("injected journal prelink fsync failure")
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", fail_anonymous_file_fsync)
        with pytest.raises(driver.BenchRefusal) as exc:
            self._journal(private_root)
        _assert_refusal(exc, "journal_failure")
        assert list((private_root / "journals").glob("*-journal.jsonl")) == []

    def test_birth_postlink_parent_fsync_failure_keeps_published_journal(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_fsync = driver.os.fsync

        def fail_parent_fsync(fd: int) -> None:
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("injected journal postlink fsync failure")
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", fail_parent_fsync)
        with pytest.raises(driver.BenchRefusal) as exc:
            self._journal(private_root)
        _assert_refusal(exc, "journal_failure")
        paths = list((private_root / "journals").glob("*-journal.jsonl"))
        assert len(paths) == 1
        assert paths[0].read_bytes() == b""

    @pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
    def test_birth_prelink_baseexception_closes_fd_and_preserves_original(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        exc_type: type[BaseException],
    ) -> None:
        real_fsync = driver.os.fsync
        injected = exc_type("injected prelink abort")
        before_fds = len(os.listdir("/proc/self/fd"))

        def abort_file_fsync(fd: int) -> None:
            if stat.S_ISREG(os.fstat(fd).st_mode):
                raise injected
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", abort_file_fsync)
        with pytest.raises(exc_type) as raised:
            self._journal(private_root)
        assert raised.value is injected
        assert len(os.listdir("/proc/self/fd")) == before_fds
        assert list((private_root / "journals").glob("*-journal.jsonl")) == []

    @pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
    def test_birth_postlink_baseexception_closes_fd_and_keeps_artifact(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        exc_type: type[BaseException],
    ) -> None:
        real_fsync = driver.os.fsync
        injected = exc_type("injected postlink abort")
        before_fds = len(os.listdir("/proc/self/fd"))

        def abort_parent_fsync(fd: int) -> None:
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise injected
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", abort_parent_fsync)
        with pytest.raises(exc_type) as raised:
            self._journal(private_root)
        assert raised.value is injected
        assert len(os.listdir("/proc/self/fd")) == before_fds
        paths = list((private_root / "journals").glob("*-journal.jsonl"))
        assert len(paths) == 1
        assert paths[0].read_bytes() == b""

    @pytest.mark.parametrize("drift_point", ["link", "fsync"])
    def test_birth_parent_drift_refuses_but_keeps_published_journal(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        drift_point: str,
    ) -> None:
        real_link = driver.os.link
        real_fsync = driver.os.fsync
        journal: driver.PhaseJournal | None = None

        def drift_after_link(
            source: str,
            target: str,
            *,
            dst_dir_fd: int,
            follow_symlinks: bool,
        ) -> None:
            real_link(
                source,
                target,
                dst_dir_fd=dst_dir_fd,
                follow_symlinks=follow_symlinks,
            )
            os.fchmod(dst_dir_fd, 0o755)

        def drift_after_fsync(fd: int) -> None:
            real_fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                os.fchmod(fd, 0o755)

        if drift_point == "link":
            monkeypatch.setattr(driver.os, "link", drift_after_link)
        else:
            monkeypatch.setattr(driver.os, "fsync", drift_after_fsync)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                journal = self._journal(private_root)
            _assert_refusal(exc, "journal_failure")
        finally:
            if journal is not None:
                journal.close()
            journal_dir = private_root / "journals"
            if journal_dir.exists():
                os.chmod(journal_dir, 0o700)
        paths = list((private_root / "journals").glob("*-journal.jsonl"))
        assert len(paths) == 1
        assert paths[0].read_bytes() == b""

    @pytest.mark.parametrize("ancestor", ["root", "intermediate"])
    def test_birth_ancestor_privacy_drift_refuses(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        ancestor: str,
    ) -> None:
        outer = private_root / "outer"
        outer.mkdir(mode=0o700)
        drift_target = private_root if ancestor == "root" else outer
        real_fsync = driver.os.fsync
        drifted = False

        def drift_during_parent_fsync(fd: int) -> None:
            nonlocal drifted
            real_fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not drifted:
                drifted = True
                os.chmod(drift_target, 0o755)

        monkeypatch.setattr(driver.os, "fsync", drift_during_parent_fsync)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver.PhaseJournal(
                    "vulkan_baseline",
                    journal_dir="outer/journals",
                    timestamp=self._TIMESTAMP,
                    root=private_root,
                )
            _assert_refusal(exc, "journal_failure")
        finally:
            os.chmod(drift_target, 0o700)
        assert drifted is True
        paths = list((outer / "journals").glob("*-journal.jsonl"))
        assert len(paths) == 1
        assert paths[0].read_bytes() == b""

    def test_birth_root_replacement_refuses_false_journal_path(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        moved_root = private_root.with_name(f"{private_root.name}-moved")
        real_fsync = driver.os.fsync
        replaced = False

        def replace_root_during_parent_fsync(fd: int) -> None:
            nonlocal replaced
            real_fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not replaced:
                replaced = True
                os.rename(private_root, moved_root)
                private_root.mkdir(mode=0o700)

        monkeypatch.setattr(driver.os, "fsync", replace_root_during_parent_fsync)
        with pytest.raises(driver.BenchRefusal) as exc:
            self._journal(private_root)
        _assert_refusal(exc, "journal_failure")
        assert replaced is True
        moved_paths = list((moved_root / "journals").glob("*-journal.jsonl"))
        assert len(moved_paths) == 1
        assert moved_paths[0].read_bytes() == b""
        assert not (private_root / "journals").exists()

    @pytest.mark.parametrize("drift", ["mode", "hardlink"])
    def test_birth_published_inode_drift_during_parent_fsync_refuses(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        drift: str,
    ) -> None:
        real_fsync = driver.os.fsync
        drifted = False

        def drift_during_parent_fsync(fd: int) -> None:
            nonlocal drifted
            real_fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not drifted:
                drifted = True
                journal_path = next((private_root / "journals").glob("*-journal.jsonl"))
                if drift == "mode":
                    os.chmod(journal_path, 0o644)
                else:
                    os.link(
                        journal_path,
                        private_root / "journal-hardlink.jsonl",
                    )

        monkeypatch.setattr(driver.os, "fsync", drift_during_parent_fsync)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                self._journal(private_root)
            _assert_refusal(exc, "journal_failure")
        finally:
            paths = list((private_root / "journals").glob("*-journal.jsonl"))
            for path in paths:
                os.chmod(path, 0o600)
        assert drifted is True
        assert len(paths) == 1
        assert paths[0].read_bytes() == b""

    def test_retained_fd_accepts_three_appends_without_reopening(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        journal = self._journal(private_root)

        def forbidden_open(*_args: object, **_kwargs: object) -> int:
            raise AssertionError("journal append reopened its path")

        monkeypatch.setattr(driver.os, "open", forbidden_open)
        for ordinal in range(3):
            journal.append(
                ts=f"2026-07-14T12:35:0{ordinal}Z",
                transition=f"stage_{ordinal}",
                detail={"ordinal": ordinal},
            )
        journal.close()

        paths = list((private_root / "journals").glob("*-journal.jsonl"))
        assert len(paths) == 1
        lines = paths[0].read_text().splitlines()
        assert len(lines) == 3
        assert [json.loads(line)["detail"]["ordinal"] for line in lines] == [
            0,
            1,
            2,
        ]

    def test_same_phase_and_timestamp_journals_coexist(self, private_root: Path) -> None:
        first = self._journal(private_root)
        second = self._journal(private_root)
        first.close()
        second.close()

        paths = list((private_root / "journals").glob("*-journal.jsonl"))
        assert len(paths) == 2
        assert paths[0].name != paths[1].name

    def test_content_marker_refuses_before_append(self, private_root: Path) -> None:
        journal = self._journal(private_root)
        try:
            with pytest.raises(ValueError, match="content_light_violation"):
                journal.append(
                    ts="2026-07-14T12:35:00Z",
                    transition="measured",
                    detail={"PROMPT": "literal"},
                )
            journal.append(
                ts="2026-07-14T12:35:01Z",
                transition="measured",
                detail={"turn_count": 1},
            )
        finally:
            journal.close()

        path = next((private_root / "journals").glob("*-journal.jsonl"))
        lines = path.read_text().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["detail"] == {"turn_count": 1}

    def test_detail_projection_failure_happens_before_fd_is_touched(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        journal = self._journal(private_root)

        def forbidden_fstat(_fd: int) -> os.stat_result:
            raise AssertionError("journal fd touched before serialization")

        monkeypatch.setattr(driver.os, "fstat", forbidden_fstat)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                journal.append(
                    ts="2026-07-14T12:35:00Z",
                    transition="measured",
                    detail=_ExplodingMapping(),
                )
            _assert_refusal(exc, "journal_failure")
        finally:
            journal.close()
        assert journal.path.read_bytes() == b""

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("ts", ""),
            ("ts", "t" * 129),
            ("ts", 1),
            ("ts", _StringSubclass("timestamp")),
            ("transition", ""),
            ("transition", "t" * 129),
            ("transition", 1),
            ("transition", _StringSubclass("transition")),
            ("detail", [("count", 1)]),
            ("detail", {"": 1}),
            ("detail", {"k" * 129: 1}),
            ("detail", {1: 1}),
            ("detail", {_StringSubclass("count"): 1}),
        ],
    )
    def test_malformed_append_shape_refuses_before_fd_is_touched(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        field: str,
        value: object,
    ) -> None:
        journal = self._journal(private_root)
        arguments: dict[str, object] = {
            "ts": "2026-07-14T12:35:00Z",
            "transition": "measured",
            "detail": {"turn_count": 1},
        }
        arguments[field] = value

        def forbidden_fstat(_fd: int) -> os.stat_result:
            raise AssertionError("journal fd touched before shape validation")

        monkeypatch.setattr(driver.os, "fstat", forbidden_fstat)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                journal.append(**arguments)  # type: ignore[arg-type]
            _assert_refusal(exc, "journal_failure")
        finally:
            journal.close()
        assert journal.path.read_bytes() == b""

    def test_partial_append_failure_restores_exact_checkpoint_and_stays_usable(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        journal = self._journal(private_root)
        journal.append(
            ts="2026-07-14T12:35:00Z",
            transition="first",
            detail={"turn_count": 1},
        )
        checkpoint = journal.path.read_bytes()
        real_write = driver.os.write
        calls = 0

        def partial_then_error(fd: int, data: object) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, memoryview(data)[:3])
            raise OSError("injected append failure")

        monkeypatch.setattr(driver.os, "write", partial_then_error)
        with pytest.raises(driver.BenchRefusal) as exc:
            journal.append(
                ts="2026-07-14T12:35:01Z",
                transition="second",
                detail={"turn_count": 2},
            )
        _assert_refusal(exc, "journal_failure")
        assert journal.path.read_bytes() == checkpoint

        monkeypatch.setattr(driver.os, "write", real_write)
        journal.append(
            ts="2026-07-14T12:35:02Z",
            transition="third",
            detail={"turn_count": 3},
        )
        journal.close()
        assert len(journal.path.read_text().splitlines()) == 2

    @pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
    def test_partial_append_baseexception_rolls_back_and_preserves_original(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        exc_type: type[BaseException],
    ) -> None:
        journal = self._journal(private_root)
        journal.append(
            ts="2026-07-14T12:35:00Z",
            transition="first",
            detail={"turn_count": 1},
        )
        checkpoint = journal.path.read_bytes()
        fd = journal._fd
        before_fds = len(os.listdir("/proc/self/fd"))
        real_write = driver.os.write
        injected = exc_type("injected append abort")
        calls = 0

        def partial_then_abort(write_fd: int, data: object) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(write_fd, memoryview(data)[:2])
            raise injected

        monkeypatch.setattr(driver.os, "write", partial_then_abort)
        with pytest.raises(exc_type) as raised:
            journal.append(
                ts="2026-07-14T12:35:01Z",
                transition="second",
                detail={"turn_count": 2},
            )
        assert raised.value is injected
        assert journal.path.read_bytes() == checkpoint
        assert journal._fd == fd
        assert len(os.listdir("/proc/self/fd")) == before_fds

        monkeypatch.setattr(driver.os, "write", real_write)
        journal.append(
            ts="2026-07-14T12:35:02Z",
            transition="third",
            detail={"turn_count": 3},
        )
        journal.close()
        assert len(journal.path.read_text().splitlines()) == 2

    @pytest.mark.parametrize("exc_type", [KeyboardInterrupt, SystemExit])
    def test_rollback_baseexception_poisons_but_original_abort_wins(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        exc_type: type[BaseException],
    ) -> None:
        journal = self._journal(private_root)
        fd = journal._fd
        real_write = driver.os.write
        injected = exc_type("original append abort")
        rollback_abort = (
            SystemExit("rollback abort")
            if exc_type is KeyboardInterrupt
            else KeyboardInterrupt("rollback abort")
        )
        calls = 0

        def partial_then_abort(write_fd: int, data: object) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(write_fd, memoryview(data)[:2])
            raise injected

        def abort_rollback(_fd: int, _size: int) -> None:
            raise rollback_abort

        monkeypatch.setattr(driver.os, "write", partial_then_abort)
        monkeypatch.setattr(driver.os, "ftruncate", abort_rollback)
        with pytest.raises(exc_type) as raised:
            journal.append(
                ts="2026-07-14T12:35:00Z",
                transition="measured",
                detail={"turn_count": 1},
            )
        assert raised.value is injected
        assert journal._fd is None
        assert fd is not None
        with pytest.raises(OSError):
            os.fstat(fd)

        monkeypatch.setattr(driver.os, "write", real_write)
        with pytest.raises(driver.BenchRefusal) as poisoned:
            journal.append(
                ts="2026-07-14T12:35:01Z",
                transition="later",
                detail={"turn_count": 2},
            )
        _assert_refusal(poisoned, "journal_failure")

    def test_concurrent_append_survives_failed_rollback_and_poisons_journal(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        journal = self._journal(private_root)
        real_write = driver.os.write
        calls = 0
        concurrent = b"CONCURRENT-BYTES"

        def partial_concurrent_then_error(fd: int, data: object) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, memoryview(data)[:2])
            other_fd = os.open(
                journal.path,
                os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW,
            )
            try:
                real_write(other_fd, concurrent)
                os.fsync(other_fd)
            finally:
                os.close(other_fd)
            raise OSError("injected append failure after concurrent write")

        monkeypatch.setattr(driver.os, "write", partial_concurrent_then_error)
        with pytest.raises(driver.BenchRefusal) as exc:
            journal.append(
                ts="2026-07-14T12:35:00Z",
                transition="measured",
                detail={"turn_count": 1},
            )
        _assert_refusal(exc, "journal_failure")
        assert concurrent in journal.path.read_bytes()

        monkeypatch.setattr(driver.os, "write", real_write)
        with pytest.raises(driver.BenchRefusal) as poisoned:
            journal.append(
                ts="2026-07-14T12:35:01Z",
                transition="later",
                detail={"turn_count": 2},
            )
        _assert_refusal(poisoned, "journal_failure")
        journal.close()

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_nonfinite_detail_is_journal_failure_without_a_line(
        self, private_root: Path, value: float
    ) -> None:
        journal = self._journal(private_root)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                journal.append(
                    ts="2026-07-14T12:35:00Z",
                    transition="measured",
                    detail={"metric": value},
                )
            _assert_refusal(exc, "journal_failure")
        finally:
            journal.close()
        assert journal.path.read_bytes() == b""

    @pytest.mark.parametrize("drift", ["mode", "hardlink"])
    def test_retained_inode_drift_before_append_refuses_without_a_line(
        self, private_root: Path, drift: str
    ) -> None:
        journal = self._journal(private_root)
        try:
            if drift == "mode":
                os.chmod(journal.path, 0o644)
            else:
                os.link(journal.path, private_root / "journal-hardlink.jsonl")
            with pytest.raises(driver.BenchRefusal) as exc:
                journal.append(
                    ts="2026-07-14T12:35:00Z",
                    transition="measured",
                    detail={"turn_count": 1},
                )
            _assert_refusal(exc, "filesystem_hazard")
        finally:
            journal.close()
        assert journal.path.read_bytes() == b""

    def test_retained_inode_drift_during_append_is_caught_post_write(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        journal = self._journal(private_root)
        real_write = driver.os.write

        def link_during_write(fd: int, data: object) -> int:
            written = real_write(fd, data)
            os.link(journal.path, private_root / "journal-hardlink.jsonl")
            return written

        monkeypatch.setattr(driver.os, "write", link_during_write)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                journal.append(
                    ts="2026-07-14T12:35:00Z",
                    transition="measured",
                    detail={"turn_count": 1},
                )
            _assert_refusal(exc, "filesystem_hazard")
        finally:
            journal.close()

    def test_append_io_error_becomes_typed_journal_failure(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        journal = self._journal(private_root)
        monkeypatch.setattr(driver.os, "write", lambda *_args: (_ for _ in ()).throw(OSError()))
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                journal.append(
                    ts="2026-07-14T12:35:00Z",
                    transition="measured",
                    detail={"turn_count": 1},
                )
            _assert_refusal(exc, "journal_failure")
        finally:
            journal.close()


class TestProviderSeams:
    def test_systemctl_builder_is_read_only_and_exact(self) -> None:
        assert driver.SYSTEMCTL_WHITELIST == frozenset({"show", "is-active"})
        assert driver.systemctl_command("show", "llama-server.service") == [
            "systemctl",
            "--user",
            "show",
            "llama-server.service",
        ]
        for verb in ("stop", "start", "restart", "enable", "disable", "kill", "mask"):
            with pytest.raises(ValueError, match="mutating_systemctl_forbidden"):
                driver.systemctl_command(verb, "x.service")

    def test_exact_systemctl_literal_appears_exactly_once(self) -> None:
        import ast

        source = Path("scripts/cuda_bench_driver.py").read_text()
        exact = [
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and node.value == "systemctl"
        ]
        assert exact == ["systemctl"]

    def test_authorization_protocol_uses_the_inv_2_annotation(self) -> None:
        annotation = inspect.signature(driver.AuthorizationGate.consume).parameters[
            "parent_packet"
        ].annotation
        assert annotation == "cm.PhasePacket | None"
        assert (
            driver.AuthorizationGate.consume.__annotations__["parent_packet"]
            == "cm.PhasePacket | None"
        )

    def test_artifact_policy_encoding_is_canonical_and_tier_incompatible(self) -> None:
        document = {"binding_sha256": "a" * 64, "value": 7}
        production = driver.ProductionArtifactPolicy()
        rehearsal = driver.RehearsalArtifactPolicy()

        assert production.encode("packet", document) == (
            b'{"binding_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
            b'"fields":{"value":7},"schema":"cuda_bench_driver.phase_packet.v1"}\n'
        )
        assert rehearsal.encode("packet", document) == (
            b'{"payload":{"binding_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
            b'"fields":{"value":7},"schema":"cuda_bench_driver.phase_packet.v1"},'
            b'"rehearsal_schema":"cuda_bench_rehearsal.packet.v1","tier":"rehearsal"}\n'
        )
        assert production.artifact_dir("journal") == "journals"
        assert rehearsal.artifact_dir("journal") == "rehearsal/journals"

    def test_turn_artifact_uses_its_own_schema_and_null_binding(self) -> None:
        encoded = json.loads(
            driver.ProductionArtifactPolicy().encode(
                "turn_artifact",
                {"binding_sha256": "a" * 64, "literal": "private"},
            )
        )
        assert encoded == {
            "schema": driver.TURN_ARTIFACT_SCHEMA,
            "binding_sha256": None,
            "fields": {"literal": "private"},
        }

    def test_rehearsal_turn_artifact_is_incompatible_with_schema_22_payload(self) -> None:
        encoded = json.loads(
            driver.RehearsalArtifactPolicy().encode(
                "turn_artifact", {"literal": "private"}
            )
        )
        assert set(encoded) == {"rehearsal_schema", "tier", "payload"}
        assert encoded["payload"]["schema"] == driver.TURN_ARTIFACT_SCHEMA
        assert encoded["payload"]["binding_sha256"] is None

    def test_individual_turn_never_emits_turn_manifest_schema(self) -> None:
        for policy in (
            driver.ProductionArtifactPolicy(),
            driver.RehearsalArtifactPolicy(),
        ):
            assert driver.TURN_MANIFEST_SCHEMA.encode() not in policy.encode(
                "turn_artifact", {"literal": "private"}
            )

    @pytest.mark.parametrize("kind", ["unknown", "journal"])
    def test_artifact_encoder_refuses_non_document_kinds(self, kind: str) -> None:
        with pytest.raises(ValueError, match="artifact_kind_invalid"):
            driver.ProductionArtifactPolicy().encode(kind, {"value": 1})

    @pytest.mark.parametrize(
        "document",
        [
            {1: "non-string-key"},
            {"nested": {1: "non-string-key"}},
            {"metric": float("nan")},
            {"metric": float("inf")},
        ],
    )
    def test_artifact_encoder_rejects_noncanonical_documents(
        self, document: dict[object, object]
    ) -> None:
        with pytest.raises(ValueError, match="artifact_document_invalid"):
            driver.ProductionArtifactPolicy().encode("packet", document)  # type: ignore[arg-type]

    def test_direct_provider_construction_is_sealed(self) -> None:
        with pytest.raises(TypeError, match="sealed_provider_factory_required"):
            driver.Providers(**_provider_components("production"))

    def test_dataclass_replace_cannot_bypass_provider_seal(self) -> None:
        providers = driver.production_tier(**_provider_components("production"))
        with pytest.raises(TypeError, match="sealed_provider_factory_required"):
            replace(providers, clock=driver.SystemClock())

    def test_both_sealed_factories_assemble_all_eleven_seams(self) -> None:
        production = driver.production_tier(**_provider_components("production"))
        rehearsal = driver.rehearsal_tier(**_provider_components("rehearsal"))

        assert production.tier == "production"
        assert rehearsal.tier == "rehearsal"
        assert len(driver.Providers.__dataclass_fields__) == 12  # tier + eleven seams
        assert production.artifact_policy.tier == "production"
        assert rehearsal.artifact_policy.tier == "rehearsal"

    @pytest.mark.parametrize(
        "field",
        [
            "service_state",
            "port_probe",
            "gpu",
            "kernel_log",
            "backend_maps",
            "server_launcher",
            "server_client",
            "authorization_gate",
            "artifact_policy",
            "clock",
            "journal_factory",
        ],
    )
    def test_factory_rejects_each_injected_tier_mixture_before_exposure(
        self, field: str
    ) -> None:
        components = _provider_components("production")
        components[field] = _TieredFake("rehearsal")

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.production_tier(**components)
        _assert_refusal(exc, "tier_mismatch")

    @pytest.mark.parametrize(
        "field",
        [
            "service_state",
            "port_probe",
            "gpu",
            "kernel_log",
            "backend_maps",
            "server_launcher",
            "server_client",
            "authorization_gate",
            "artifact_policy",
            "clock",
            "journal_factory",
        ],
    )
    def test_factory_rejects_missing_tier_on_every_seam(self, field: str) -> None:
        components = _provider_components("production")
        untiered = _TieredFake("production")
        del untiered.tier
        components[field] = untiered
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.production_tier(**components)
        _assert_refusal(exc, "tier_mismatch")

    def test_factory_rejects_forged_tier_equality(self) -> None:
        components = _provider_components("production")
        forged = _TieredFake("production")
        forged.tier = _ForgedTier()  # type: ignore[assignment]
        components["gpu"] = forged
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.production_tier(**components)
        _assert_refusal(exc, "tier_mismatch")

    @pytest.mark.parametrize(
        ("factory", "wrong_dir"),
        [
            (driver.ProductionJournalFactory(), "rehearsal/journals"),
            (driver.RehearsalJournalFactory(), "journals"),
        ],
    )
    def test_journal_factory_refuses_non_policy_directory_before_write(
        self,
        private_root: Path,
        factory: object,
        wrong_dir: str,
    ) -> None:
        with pytest.raises(driver.BenchRefusal) as exc:
            factory.create(  # type: ignore[attr-defined]
                "vulkan_baseline",
                journal_dir=wrong_dir,
                timestamp="2026-07-14T12:00:00Z",
                root=private_root,
            )
        _assert_refusal(exc, "tier_mismatch")
        assert list(private_root.rglob("*")) == []

    @pytest.mark.parametrize(
        ("policy_type", "factory", "derived_dir"),
        [
            (driver.ProductionArtifactPolicy, driver.ProductionJournalFactory(), "journals-v2"),
            (
                driver.RehearsalArtifactPolicy,
                driver.RehearsalJournalFactory(),
                "rehearsal/journals-v2",
            ),
        ],
    )
    def test_journal_factory_derives_directory_from_its_policy(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        policy_type: type,
        factory: object,
        derived_dir: str,
    ) -> None:
        monkeypatch.setattr(
            policy_type,
            "artifact_dir",
            lambda _self, kind: derived_dir if kind == "journal" else "wrong",
        )
        journal = factory.create(  # type: ignore[attr-defined]
            "vulkan_baseline",
            journal_dir=derived_dir,
            timestamp="2026-07-14T12:00:00Z",
            root=private_root,
        )
        journal.close()
        assert journal.path.relative_to(private_root).as_posix().startswith(derived_dir)

    def test_rehearsal_journal_factory_writes_only_under_rehearsal(
        self, private_root: Path
    ) -> None:
        journal = driver.RehearsalJournalFactory().create(
            "vulkan_baseline",
            journal_dir="rehearsal/journals",
            timestamp="2026-07-14T12:00:00Z",
            root=private_root,
        )
        journal.close()
        files = [path.relative_to(private_root).as_posix() for path in private_root.rglob("*") if path.is_file()]
        assert len(files) == 1
        assert files[0].startswith("rehearsal/journals/")

    def test_ambient_topology_hash_is_order_insensitive_and_excludes_owned(self) -> None:
        first = [(22, "/usr/bin/code"), (11, "/usr/lib/Xwayland"), (99, "owned")]
        second = [(99, "different-owned-name"), (11, "Xwayland"), (22, "code")]
        assert driver.ambient_topology_hash(first, {99}) == driver.ambient_topology_hash(
            second, {99}
        )

    def test_synthetic_providers_never_claim_real_contact(self) -> None:
        providers = _provider_components("rehearsal")
        for value in providers.values():
            witness = getattr(value, "witness", None)
            if witness is not None:
                assert witness == driver.ProviderWitness(synthetic=True, real_calls=0)

    @pytest.mark.parametrize(
        ("synthetic", "real_calls"),
        [(True, True), (True, -1), (True, 1), (False, False)],
    )
    def test_provider_witness_rejects_malformed_or_false_synthetic_claims(
        self, synthetic: bool, real_calls: object
    ) -> None:
        with pytest.raises(ValueError, match="provider_witness_invalid"):
            driver.ProviderWitness(synthetic=synthetic, real_calls=real_calls)  # type: ignore[arg-type]

    def test_missing_synthetic_service_state_is_provider_uncertain(self) -> None:
        service = driver.SyntheticServiceState({})
        with pytest.raises(driver.BenchRefusal) as exc:
            service.is_active("missing.service")
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize(
        ("states", "unit"),
        [({"x.service": 7}, "x.service"), ({"x.service": "inactive"}, True), ({}, "")],
    )
    def test_synthetic_service_rejects_nonstring_state_or_invalid_unit(
        self, states: dict[object, object], unit: object
    ) -> None:
        service = driver.SyntheticServiceState(states)  # type: ignore[arg-type]
        with pytest.raises(driver.BenchRefusal) as exc:
            service.is_active(unit)  # type: ignore[arg-type]
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize("port", [True, 0, -1, 65_536, "18080"])
    def test_synthetic_port_probe_rejects_invalid_port(self, port: object) -> None:
        probe = driver.SyntheticPortProbe({18080})
        with pytest.raises(driver.BenchRefusal) as exc:
            probe.is_free(port)  # type: ignore[arg-type]
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize("free", [{True}, {0}, {65_536}, {"18080"}])
    def test_synthetic_port_probe_rejects_malformed_free_set(
        self, free: set[object]
    ) -> None:
        probe = driver.SyntheticPortProbe(free)  # type: ignore[arg-type]
        with pytest.raises(driver.BenchRefusal) as exc:
            probe.is_free(18080)
        _assert_refusal(exc, "provider_uncertain")

    def test_synthetic_gpu_failed_source_refuses_instead_of_claiming_empty(self) -> None:
        gpu = driver.SyntheticGpu(
            ["GPU-12345678-1234-1234-1234-123456789abc"], None, [(0.0, 0)]
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            gpu.inventory("GPU-12345678-1234-1234-1234-123456789abc")
        _assert_refusal(exc, "provider_uncertain")

    def test_synthetic_gpu_deep_freezes_inputs_and_returns_copies(self) -> None:
        uuids = ["GPU-12345678-1234-1234-1234-123456789abc"]
        inventories = [[(7, "/usr/bin/code")], [(7, "/usr/bin/code")]]
        memories = [(1.0, 2), (1.0, 2)]
        gpu = driver.SyntheticGpu(uuids, inventories, memories)

        uuids[0] = "GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        inventories[0][0] = (99, "/tmp/forged")
        memories[0] = (99.0, 99)

        assert gpu.enumerate_uuids() == [
            "GPU-12345678-1234-1234-1234-123456789abc"
        ]
        first = gpu.inventory("GPU-12345678-1234-1234-1234-123456789abc")
        assert first == [(7, "code")]
        first.append((88, "mutated"))
        assert gpu.inventory("GPU-12345678-1234-1234-1234-123456789abc") == [
            (7, "code")
        ]
        assert gpu.memory("GPU-12345678-1234-1234-1234-123456789abc") == (
            1.0,
            2,
        )

    def test_synthetic_gpu_snapshots_mutable_rows_but_requires_tuple_shape(self) -> None:
        mutable_row = [7, "/usr/bin/code"]
        inventories = [[mutable_row]]
        gpu = driver.SyntheticGpu(
            ["GPU-12345678-1234-1234-1234-123456789abc"],
            inventories,  # type: ignore[arg-type]
            [(1.0, 2)],
        )
        mutable_row[:] = [99, "/tmp/forged"]
        with pytest.raises(driver.BenchRefusal) as exc:
            gpu.inventory("GPU-12345678-1234-1234-1234-123456789abc")
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize(
        "uuids",
        [["not-a-gpu"], [True], ["GPU-12345678"]],
    )
    def test_synthetic_gpu_enumeration_requires_exact_uuid_strings(
        self, uuids: list[object]
    ) -> None:
        gpu = driver.SyntheticGpu(uuids, [], [])  # type: ignore[arg-type]
        with pytest.raises(driver.BenchRefusal) as exc:
            gpu.enumerate_uuids()
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize("maps_text", [b"bytes", 7, None])
    def test_synthetic_backend_map_requires_string_evidence(
        self, maps_text: object
    ) -> None:
        provider = driver.SyntheticBackendMap({1: maps_text})  # type: ignore[dict-item]
        with pytest.raises(driver.BenchRefusal) as exc:
            provider.read_maps(1)
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize(
        ("mapping", "pid"),
        [({True: "forged"}, 1), ({1: "maps"}, True), ({1: "maps"}, 0)],
    )
    def test_synthetic_backend_map_requires_exact_positive_int_identity(
        self, mapping: dict[object, str], pid: object
    ) -> None:
        provider = driver.SyntheticBackendMap(mapping)  # type: ignore[arg-type]
        with pytest.raises(driver.BenchRefusal) as exc:
            provider.read_maps(pid)  # type: ignore[arg-type]
        _assert_refusal(exc, "provider_uncertain")

    def test_synthetic_kernel_requires_the_exact_counter_shape(self) -> None:
        with pytest.raises(ValueError, match="synthetic_kernel_invalid"):
            driver.SyntheticKernelLog({})

    def test_frozen_clock_advances_without_wall_clock_contact(self) -> None:
        clock = driver.FrozenClock("2026-07-14T12:00:00Z", monotonic_start=7.0)
        clock.advance(2.5)
        assert clock.now_utc() == "2026-07-14T12:00:02.500000Z"
        assert clock.monotonic() == 9.5

    @pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
    def test_frozen_clock_rejects_invalid_monotonic_start(self, value: object) -> None:
        with pytest.raises(ValueError, match="frozen_clock_invalid"):
            driver.FrozenClock(
                "2026-07-14T12:00:00Z", monotonic_start=value  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
    def test_frozen_clock_rejects_invalid_advance(self, value: object) -> None:
        clock = driver.FrozenClock("2026-07-14T12:00:00Z")
        with pytest.raises(ValueError, match="frozen_clock_invalid"):
            clock.advance(value)  # type: ignore[arg-type]

    def test_frozen_clock_catches_numeric_and_datetime_overflow(self) -> None:
        with pytest.raises(ValueError, match="frozen_clock_invalid"):
            driver.FrozenClock(
                "2026-07-14T12:00:00Z", monotonic_start=10**1000
            )

        for clock, amount in (
            (driver.FrozenClock("2026-07-14T12:00:00Z"), 10**1000),
            (driver.FrozenClock("9999-12-31T23:59:59Z"), 2),
            (driver.FrozenClock("2026-07-14T12:00:00Z", monotonic_start=1e308), 1e308),
        ):
            with pytest.raises(ValueError, match="frozen_clock_invalid"):
                clock.advance(amount)

    def test_synthetic_kernel_cursors_are_distinct_and_equal_window_is_zero(self) -> None:
        counts = {
            "reusemappingdbMap": 1,
            "pMapCb": 2,
            "mmuWalkMap": 3,
            "NV_ERR_NO_MEMORY": 4,
            "Xid": 5,
            "unmatched_nvrm": 6,
        }
        kernel = driver.SyntheticKernelLog(counts)
        before = kernel.cursor()
        after = kernel.cursor()
        assert before != after
        assert kernel.count_signatures(before, after) == counts
        assert kernel.count_signatures(before, before) == dict.fromkeys(counts, 0)

    @pytest.mark.parametrize(
        ("start", "end"),
        [("", "end"), ("start", ""), (True, "end"), ("start", None)],
    )
    def test_synthetic_kernel_requires_exact_nonempty_cursor_strings(
        self, start: object, end: object
    ) -> None:
        counts = dict.fromkeys(driver.KERNEL_COUNTER_KEYS, 0)
        kernel = driver.SyntheticKernelLog(counts)
        with pytest.raises(driver.BenchRefusal) as exc:
            kernel.count_signatures(start, end)  # type: ignore[arg-type]
        _assert_refusal(exc, "provider_uncertain")

    def test_real_service_provider_uses_only_the_whitelisted_builder(self) -> None:
        calls: list[list[str]] = []

        def runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 3, "inactive\n", "")

        provider = driver.RealServiceStateProvider(runner=runner)
        assert provider.is_active("llama-server.service") == "inactive"
        assert calls == [driver.systemctl_command("is-active", "llama-server.service")]

    def test_real_service_provider_rejects_malformed_state(self) -> None:
        result = subprocess.CompletedProcess([], 0, "banana\n", "")
        provider = driver.RealServiceStateProvider(runner=lambda _argv: result)
        with pytest.raises(driver.BenchRefusal) as exc:
            provider.is_active("llama-server.service")
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize(
        ("returncode", "state"),
        [
            (0, "active"),
            (0, "reloading"),
            (3, "inactive"),
            (3, "failed"),
            (3, "activating"),
            (3, "deactivating"),
            (3, "maintenance"),
        ],
    )
    def test_real_service_provider_joins_returncode_to_state(
        self, returncode: int, state: str
    ) -> None:
        result = subprocess.CompletedProcess([], returncode, state + "\n", "")
        provider = driver.RealServiceStateProvider(runner=lambda _argv: result)
        assert provider.is_active("llama-server.service") == state

    @pytest.mark.parametrize(
        ("returncode", "state"),
        [(0, "inactive"), (0, "failed"), (3, "active"), (3, "reloading")],
    )
    def test_real_service_provider_refuses_contradictory_status_pair(
        self, returncode: int, state: str
    ) -> None:
        result = subprocess.CompletedProcess([], returncode, state + "\n", "")
        provider = driver.RealServiceStateProvider(runner=lambda _argv: result)
        with pytest.raises(driver.BenchRefusal) as exc:
            provider.is_active("llama-server.service")
        _assert_refusal(exc, "provider_uncertain")

    def test_port_probe_constructor_failure_is_typed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            driver.socket,
            "socket",
            lambda *_args: (_ for _ in ()).throw(OSError("constructor failed")),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.RealPortProbe().is_free(18080)
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize(
        ("bind_error", "close_error"),
        [
            (OSError("bind failed"), None),
            (None, OSError("close failed")),
            (OSError(errno.EADDRINUSE, "occupied"), OSError("close failed")),
        ],
    )
    def test_port_probe_failures_are_typed_and_socket_is_closed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        bind_error: OSError | None,
        close_error: OSError | None,
    ) -> None:
        fake = _FakeSocket(bind_error=bind_error, close_error=close_error)
        monkeypatch.setattr(driver.socket, "socket", lambda *_args: fake)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.RealPortProbe().is_free(18080)
        _assert_refusal(exc, "provider_uncertain")
        assert fake.closed

    def test_real_gpu_provider_scopes_and_unions_both_inventory_sources(self) -> None:
        calls: list[list[str]] = []
        outputs = iter(
            [
                "GPU-12345678-1234-1234-1234-123456789abc\n",
                "42, /opt/bin/llama-server\n7, /usr/bin/code\n",
                "Processes\n    Process ID : 7\n        Name : /snap/code\n"
                "    Process ID : 9\n        Name : /usr/lib/Xwayland\n",
                "FB Memory Usage\n    Total : 24564 MiB\n    Used : 1024 MiB\n"
                "BAR1 Memory Usage\n    Total : 32768 MiB\n    Used : 28850 MiB\n",
            ]
        )

        def runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, next(outputs), "")

        gpu = driver.RealGpuProvider(runner=runner)
        assert gpu.enumerate_uuids() == [
            "GPU-12345678-1234-1234-1234-123456789abc"
        ]
        assert gpu.inventory("GPU-12345678-1234-1234-1234-123456789abc") == [
            (7, "code"),
            (9, "Xwayland"),
            (42, "llama-server"),
        ]
        assert gpu.memory("GPU-12345678-1234-1234-1234-123456789abc") == (
            88.04,
            1024,
        )
        assert calls == [
            ["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader"],
            [
                "nvidia-smi",
                "-i",
                "GPU-12345678-1234-1234-1234-123456789abc",
                "--query-compute-apps=pid,process_name",
                "--format=csv,noheader",
            ],
            [
                "nvidia-smi",
                "-i",
                "GPU-12345678-1234-1234-1234-123456789abc",
                "-q",
                "-d",
                "PIDS",
            ],
            [
                "nvidia-smi",
                "-i",
                "GPU-12345678-1234-1234-1234-123456789abc",
                "-q",
                "-d",
                "MEMORY",
            ],
        ]

    @pytest.mark.parametrize(
        "uuid", ["GPU-x;touch /tmp/no", "GPU-", "GPU-12345678", "not-a-gpu"]
    )
    def test_real_gpu_provider_rejects_malformed_uuid_before_runner(
        self, uuid: str
    ) -> None:
        called = False

        def runner(_argv: list[str]) -> subprocess.CompletedProcess[str]:
            nonlocal called
            called = True
            return subprocess.CompletedProcess([], 0, "", "")

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.RealGpuProvider(runner=runner).inventory(uuid)
        _assert_refusal(exc, "provider_uncertain")
        assert not called

    @pytest.mark.parametrize(
        "memory",
        [
            "FB Memory Usage\n Total : 10 MiB\n Used : 1 MiB\n",
            "FB Memory Usage\n Total : 10 MiB\n Used : 1 MiB\n"
            "BAR1 Memory Usage\n Total : 0 MiB\n Used : 0 MiB\n",
            "FB Memory Usage\n Total : 10 MiB\n Used : 1 MiB\n"
            "BAR1 Memory Usage\n Total : 10 MiB\n Used : 11 MiB\n",
            "FB Memory Usage\n Total : 10 MiB\n Used : 1 MiB\n"
            "FB Memory Usage\n Total : 10 MiB\n Used : 2 MiB\n"
            "BAR1 Memory Usage\n Total : 10 MiB\n Used : 1 MiB\n",
        ],
    )
    def test_real_gpu_memory_parser_fails_closed(self, memory: str) -> None:
        result = subprocess.CompletedProcess([], 0, memory, "")
        gpu = driver.RealGpuProvider(runner=lambda _argv: result)
        with pytest.raises(driver.BenchRefusal) as exc:
            gpu.memory("GPU-12345678-1234-1234-1234-123456789abc")
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize(
        ("used", "expected"),
        [(1, 3.12), (3, 9.38)],
    )
    def test_real_gpu_memory_delimits_trailing_sections_and_rounds_half_even(
        self, used: int, expected: float
    ) -> None:
        output = (
            "FB Memory Usage\n    Total : 64 MiB\n    Used : 4 MiB\n"
            f"BAR1 Memory Usage\n    Total : 32 MiB\n    Used : {used} MiB\n"
            "Confidential Compute Memory Usage\n"
            "    Total : 2048 MiB\n    Used : 1024 MiB\n"
        )
        result = subprocess.CompletedProcess([], 0, output, "")
        gpu = driver.RealGpuProvider(runner=lambda _argv: result)
        assert gpu.memory("GPU-12345678-1234-1234-1234-123456789abc") == (
            expected,
            4,
        )

    def test_real_gpu_inventory_source_failure_is_provider_uncertain(self) -> None:
        responses = iter(
            [
                subprocess.CompletedProcess([], 0, "", ""),
                subprocess.CompletedProcess([], 1, "", "failed"),
            ]
        )
        gpu = driver.RealGpuProvider(runner=lambda _argv: next(responses))
        with pytest.raises(driver.BenchRefusal) as exc:
            gpu.inventory("GPU-12345678-1234-1234-1234-123456789abc")
        _assert_refusal(exc, "provider_uncertain")

    def test_pids_parser_accepts_explicit_empty_processes_envelope(self) -> None:
        assert driver._parse_pids_inventory(  # noqa: SLF001
            "GPU 0000:01:00.0\nProcesses\n    No running processes found\n"
        ) == set()

    @pytest.mark.parametrize(
        "line",
        [
            "    Processes : None",
            "Processes                       : None",
            "Processes\t: None",
        ],
    )
    def test_pids_parser_accepts_official_padded_processes_none(
        self, line: str
    ) -> None:
        assert driver._parse_pids_inventory(  # noqa: SLF001
            f"GPU 0000:01:00.0\n{line}\n"
        ) == set()

    @pytest.mark.parametrize(
        "payload",
        [
            "garbage\n",
            "Processes : N/A\n",
            "Processes : None\nProcesses : None\n",
            "Processes : None\n    Process ID : 7\n    Name : /usr/bin/code\n",
            "Processes\n    Process ID : N/A\n",
            "Processes\n    Name : /usr/bin/orphan\n",
            "Processes\n    maybe No running processes found later\n",
            "Processes\n    Process ID : 7\n    Name : N/A\n",
            "Processes\n    Process ID : 7\n    Process ID : 8\n"
            "    Name : /usr/bin/code\n",
            "Processes\n    Process ID : 7\n    Name : /usr/bin/code\n"
            "    Name : /usr/bin/duplicate\n",
            "Processes\n    No running processes found\n"
            "    Process ID : 7\n    Name : /usr/bin/code\n",
            "Processes\n    Process ID : 7\n",
        ],
    )
    def test_pids_parser_refuses_unproven_or_contradictory_envelopes(
        self, payload: str
    ) -> None:
        with pytest.raises(driver.BenchRefusal) as exc:
            driver._parse_pids_inventory(payload)  # noqa: SLF001
        _assert_refusal(exc, "provider_uncertain")

    def test_real_kernel_provider_closes_signature_vocabulary_and_cursor(self) -> None:
        outputs = iter(
            [
                "-- cursor: s=before\n",
                "kernel: NVRM: reusemappingdbMap\n"
                "kernel: NVRM: Xid 31\n"
                "kernel: NVRM: mystery fault\n"
                "-- cursor: s=after\n",
            ]
        )
        calls: list[list[str]] = []

        def runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, next(outputs), "")

        kernel = driver.RealKernelLogProvider(runner=runner)
        assert kernel.cursor() == "s=before"
        assert kernel.count_signatures("s=before", "s=after") == {
            "reusemappingdbMap": 1,
            "pMapCb": 0,
            "mmuWalkMap": 0,
            "NV_ERR_NO_MEMORY": 0,
            "Xid": 1,
            "unmatched_nvrm": 1,
        }
        assert calls[1] == [
            "journalctl",
            "-k",
            "--after-cursor=s=before",
            "--show-cursor",
            "--no-pager",
        ]

    def test_equal_kernel_cursors_return_exact_zeros_without_query(self) -> None:
        kernel = driver.RealKernelLogProvider(
            runner=lambda _argv: (_ for _ in ()).throw(AssertionError("queried"))
        )
        assert kernel.count_signatures("same", "same") == {
            "reusemappingdbMap": 0,
            "pMapCb": 0,
            "mmuWalkMap": 0,
            "NV_ERR_NO_MEMORY": 0,
            "Xid": 0,
            "unmatched_nvrm": 0,
        }

    def test_kernel_counts_repeated_occurrences_and_xid_boundary(self) -> None:
        output = (
            "kernel: NVRM: reusemappingdbMap reusemappingdbMap\n"
            "kernel: NVRM: Xid 31; NVRM: Xid 32\n"
            "kernel: NVRM: XidExtra 99\n"
            "-- cursor: s=after\n"
        )
        result = subprocess.CompletedProcess([], 0, output, "")
        kernel = driver.RealKernelLogProvider(runner=lambda _argv: result)
        assert kernel.count_signatures("s=before", "s=after") == {
            "reusemappingdbMap": 2,
            "pMapCb": 0,
            "mmuWalkMap": 0,
            "NV_ERR_NO_MEMORY": 0,
            "Xid": 2,
            "unmatched_nvrm": 1,
        }

    def test_kernel_signature_boundaries_cover_all_five_known_shapes(self) -> None:
        output = (
            "kernel: NVRM: reusemappingdbMap reusemappingdbMap\n"
            "kernel: NVRM: pMapCb pMapCb\n"
            "kernel: NVRM: mmuWalkMap mmuWalkMap\n"
            "kernel: NVRM: NV_ERR_NO_MEMORY NV_ERR_NO_MEMORY\n"
            "kernel: NVRM: Xid 1; NVRM: Xid 2\n"
            "kernel: NVRM: reusemappingdbMapExtra\n"
            "kernel: NVRM: prepMapCb\n"
            "kernel: NVRM: mmuWalkMapSuffix\n"
            "kernel: NVRM: NV_ERR_NO_MEMORY_MORE\n"
            "kernel: NVRM: XidExtra 9\n"
            "-- cursor: s=after\n"
        )
        result = subprocess.CompletedProcess([], 0, output, "")
        kernel = driver.RealKernelLogProvider(runner=lambda _argv: result)
        assert kernel.count_signatures("s=before", "s=after") == {
            "reusemappingdbMap": 2,
            "pMapCb": 2,
            "mmuWalkMap": 2,
            "NV_ERR_NO_MEMORY": 2,
            "Xid": 2,
            "unmatched_nvrm": 5,
        }

    @pytest.mark.parametrize(
        ("inventory", "owned"),
        [
            ([(True, "name")], set()),
            ([(0, "name")], set()),
            ([(1, "")], set()),
            ([(1, "name")], {True}),
            ([[1, "name"]], set()),
            ([(1, "name", "extra")], set()),
        ],
    )
    def test_ambient_topology_rejects_malformed_evidence(
        self, inventory: list[tuple[object, object]], owned: set[object]
    ) -> None:
        with pytest.raises(BenchRefusal := driver.BenchRefusal) as exc:
            driver.ambient_topology_hash(inventory, owned)  # type: ignore[arg-type]
        assert isinstance(exc.value, BenchRefusal)
        _assert_refusal(exc, "provider_uncertain")

    def test_system_clock_is_utc_z_and_monotonic(self) -> None:
        clock = driver.SystemClock()
        assert clock.now_utc().endswith("Z")
        datetime.fromisoformat(clock.now_utc().replace("Z", "+00:00")).astimezone(UTC)
        assert isinstance(clock.monotonic(), float)


_AUTH_NONCE_A = "a" * 64
_AUTH_NONCE_B = "b" * 64


def _window_fields(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "window_id": "window-1",
        "phases": ["vulkan_baseline", "cuda_candidate"],
        "boot_id": "boot-1",
        "nonce": _AUTH_NONCE_A,
        "issued_at": "2026-07-14T08:00:00Z",
        "expires_at": "2026-07-14T12:00:00Z",
        "owner": "owner-label-is-hash-bound-only",
    }
    fields.update(overrides)
    return fields


def _continuation_fields(**overrides: object) -> dict[str, object]:
    fields = _window_fields(
        phases=["cuda_candidate"],
        nonce=_AUTH_NONCE_B,
        issued_at="2026-07-14T11:00:00Z",
        expires_at="2026-07-14T12:00:00Z",
        parent_vulkan_packet_sha256="c" * 64,
    )
    fields.update(overrides)
    return fields


def _authorization_wrapper(kind: str, fields: dict[str, object]) -> bytes:
    normalized = {**fields, "phases": tuple(fields["phases"])}  # type: ignore[arg-type]
    doc = (
        driver.cm.WindowAuthorizationDoc(**normalized)  # type: ignore[arg-type]
        if kind == "window_authorization"
        else driver.cm.ContinuationDoc(**normalized)  # type: ignore[arg-type]
    )
    return driver.ProductionArtifactPolicy().encode(
        kind,
        {
            "schema": doc.schema_version,
            "binding_sha256": doc.preimage_sha256,
            **fields,
        },
    )


def _mutated_wrapper(
    data: bytes,
    *,
    outer: dict[str, object] | None = None,
    fields: dict[str, object] | None = None,
) -> bytes:
    document = json.loads(data)
    if outer is not None:
        document.update(outer)
    if fields is not None:
        document["fields"].update(fields)
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def _scorer_phase_packet(phase: str = "vulkan_baseline") -> driver.cm.PhasePacket:
    from tests.test_cuda_migration import _phase_packet

    return _phase_packet(phase)


def _cuda_authorities(
    *,
    packet: driver.cm.PhasePacket | None = None,
    owner: str = "owner-label-is-hash-bound-only",
) -> tuple[driver.WindowAuthorization, driver.Continuation, driver.cm.PhasePacket]:
    parent = packet if packet is not None else _scorer_phase_packet()
    window = driver.WindowAuthorization(
        window_id="window-1",
        phases=("vulkan_baseline", "cuda_candidate"),
        boot_id="boot-1",
        nonce=_AUTH_NONCE_A,
        issued_at="2026-07-14T08:00:00Z",
        expires_at="2026-07-14T12:00:00Z",
        owner=owner,
    )
    object.__setattr__(
        parent,
        "authorization_preimage_sha256",
        window.preimage_sha256,
    )
    continuation = driver.Continuation(
        window_id="window-1",
        phases=("cuda_candidate",),
        boot_id="boot-1",
        nonce=_AUTH_NONCE_B,
        issued_at="2026-07-14T11:00:00Z",
        expires_at="2026-07-14T12:00:00Z",
        owner=owner,
        parent_vulkan_packet_sha256=parent.binding_sha256,
    )
    return window, continuation, parent


class TestAuthorizationArtifacts:
    def test_canonical_private_wrappers_parse_to_frozen_local_types(
        self, private_root: Path
    ) -> None:
        window_data = _authorization_wrapper("window_authorization", _window_fields())
        continuation_data = _authorization_wrapper("continuation", _continuation_fields())
        _private_file(private_root / "window.json", window_data)
        _private_file(private_root / "continuation.json", continuation_data)

        window = driver.parse_window_authorization(
            driver.open_bench_file("window.json", root=private_root)
        )
        continuation = driver.parse_continuation(
            driver.open_bench_file("continuation.json", root=private_root)
        )

        assert isinstance(window, driver.WindowAuthorization)
        assert isinstance(continuation, driver.Continuation)
        assert window.phases == ("vulkan_baseline", "cuda_candidate")
        assert continuation.phases == ("cuda_candidate",)
        with pytest.raises(FrozenInstanceError):
            window.owner = "mutated"  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            continuation.owner = "mutated"  # type: ignore[misc]

    def test_parsed_preimages_equal_the_scorer_document_canon(self) -> None:
        window_fields = _window_fields(owner="a-different-owner-label")
        continuation_fields = _continuation_fields(owner="a-different-owner-label")
        window = driver.parse_window_authorization(
            _authorization_wrapper("window_authorization", window_fields)
        )
        continuation = driver.parse_continuation(
            _authorization_wrapper("continuation", continuation_fields)
        )
        scorer_window = driver.cm.WindowAuthorizationDoc(
            **{**window_fields, "phases": tuple(window_fields["phases"])}  # type: ignore[arg-type]
        )
        scorer_continuation = driver.cm.ContinuationDoc(
            **{
                **continuation_fields,
                "phases": tuple(continuation_fields["phases"]),  # type: ignore[arg-type]
            }
        )

        assert window.preimage_sha256 == scorer_window.preimage_sha256
        assert continuation.preimage_sha256 == scorer_continuation.preimage_sha256

    @pytest.mark.parametrize(
        "data",
        [b"not-json", b"null", b"[]", b"{}", bytearray(b"{}"), "{}"],
    )
    def test_parsers_reject_bad_json_and_input_types(self, data: object) -> None:
        for parser in (driver.parse_window_authorization, driver.parse_continuation):
            with pytest.raises(driver.BenchRefusal) as exc:
                parser(data)  # type: ignore[arg-type]
            _assert_refusal(exc, "authorization_malformed")

    @pytest.mark.parametrize("kind", ["window_authorization", "continuation"])
    def test_parsers_accept_only_the_closed_bound_b3_wrapper(self, kind: str) -> None:
        fields = _window_fields() if kind == "window_authorization" else _continuation_fields()
        parser = (
            driver.parse_window_authorization
            if kind == "window_authorization"
            else driver.parse_continuation
        )
        valid = _authorization_wrapper(kind, fields)
        wrapper = json.loads(valid)
        malformed: list[bytes] = [
            (json.dumps({"schema": wrapper["schema"], **fields}) + "\n").encode()
        ]
        for key in ("schema", "binding_sha256", "fields"):
            missing = dict(wrapper)
            missing.pop(key)
            malformed.append((json.dumps(missing) + "\n").encode())
        malformed.append(_mutated_wrapper(valid, outer={"extra": True}))
        malformed.append(_mutated_wrapper(valid, outer={"schema": "wrong.schema.v1"}))
        malformed.append(_mutated_wrapper(valid, outer={"binding_sha256": "f" * 64}))
        missing_field = json.loads(valid)
        missing_field["fields"].pop("owner")
        malformed.append((json.dumps(missing_field) + "\n").encode())
        malformed.append(_mutated_wrapper(valid, fields={"extra": True}))

        for data in malformed:
            with pytest.raises(driver.BenchRefusal) as exc:
                parser(data)
            _assert_refusal(exc, "authorization_malformed")

    @pytest.mark.parametrize(
        ("field", "bad_value"),
        [
            ("window_id", ""),
            ("window_id", "bad/window"),
            ("window_id", "w" * 65),
            ("window_id", 7),
            ("nonce", "A" * 64),
            ("nonce", "a" * 63),
            ("nonce", 7),
            ("phases", []),
            ("phases", "vulkan_baseline"),
            ("phases", ["not-a-phase"]),
            ("phases", [7]),
            ("boot_id", ""),
            ("boot_id", 7),
            ("owner", ""),
            ("owner", 7),
            ("issued_at", "2026-07-14T08:00:00+00:00"),
            ("issued_at", "not-a-time"),
            ("expires_at", "2026-07-14T12:00:00+00:00"),
            ("expires_at", "2026-02-30T12:00:00Z"),
            ("expires_at", "2026-07-14T12:00:01Z"),
        ],
    )
    def test_window_parser_rejects_bad_fields_and_nonexact_ttl(
        self, field: str, bad_value: object
    ) -> None:
        data = _mutated_wrapper(
            _authorization_wrapper("window_authorization", _window_fields()),
            fields={field: bad_value},
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.parse_window_authorization(data)
        _assert_refusal(exc, "authorization_malformed")

    @pytest.mark.parametrize(
        ("field", "bad_value"),
        [
            ("parent_vulkan_packet_sha256", "A" * 64),
            ("parent_vulkan_packet_sha256", "a" * 63),
            ("parent_vulkan_packet_sha256", 7),
            ("expires_at", "2026-07-14T12:00:01Z"),
        ],
    )
    def test_continuation_parser_rejects_bad_parent_hash_and_nonexact_ttl(
        self, field: str, bad_value: object
    ) -> None:
        data = _mutated_wrapper(
            _authorization_wrapper("continuation", _continuation_fields()),
            fields={field: bad_value},
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.parse_continuation(data)
        _assert_refusal(exc, "authorization_malformed")

    def test_different_owner_label_is_not_an_authorization_gate(
        self, private_root: Path
    ) -> None:
        fields = _window_fields(owner="not-the-fixture-owner")
        authorization = driver.parse_window_authorization(
            _authorization_wrapper("window_authorization", fields)
        )
        policy = driver.ProductionArtifactPolicy()
        result = driver.RealAuthorizationGate(policy).consume(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-1",
            parent_window=None,
            parent_packet=None,
            root=private_root,
            clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
        )

        assert authorization.owner == "not-the-fixture-owner"
        assert result.preimage_sha256 == authorization.preimage_sha256

    def test_real_gate_consumes_once_with_bound_private_artifacts(
        self, private_root: Path
    ) -> None:
        authorization = driver.parse_window_authorization(
            _authorization_wrapper("window_authorization", _window_fields())
        )
        policy = driver.ProductionArtifactPolicy()
        result = driver.RealAuthorizationGate(policy).consume(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-1",
            parent_window=None,
            parent_packet=None,
            root=private_root,
            clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
        )

        marker = private_root / "markers" / authorization.nonce
        receipts = list((private_root / "receipts").glob("*.json"))
        assert marker.read_bytes() == b""
        assert stat.S_IMODE(marker.stat().st_mode) == 0o600
        assert len(receipts) == 1
        assert stat.S_IMODE(receipts[0].stat().st_mode) == 0o600
        wrapper = json.loads(receipts[0].read_bytes())
        assert set(wrapper) == {"schema", "binding_sha256", "fields"}
        assert wrapper["schema"] == driver.CONSUMPTION_RECEIPT_SCHEMA
        assert wrapper["fields"] == {
            "nonce": authorization.nonce,
            "phase": "vulkan_baseline",
            "boot_id": "boot-1",
            "timestamp": "2026-07-14T11:30:00.000000Z",
        }
        scorer_receipt = driver.cm.ConsumptionReceipt(**wrapper["fields"])
        assert result.preimage_sha256 == authorization.preimage_sha256
        assert result.consumption_receipt_sha256 == scorer_receipt.binding_sha256
        assert result.consumption_receipt_sha256 == wrapper["binding_sha256"]
        assert result.receipt == {
            "schema": driver.CONSUMPTION_RECEIPT_SCHEMA,
            "binding_sha256": scorer_receipt.binding_sha256,
            **wrapper["fields"],
        }

    def test_consumption_compares_full_timestamp_precision_and_samples_clock_once(
        self, private_root: Path
    ) -> None:
        class ExactClock:
            tier = "production"

            def __init__(self) -> None:
                self.calls = 0

            def now_utc(self) -> str:
                self.calls += 1
                return "2026-07-14T08:00:00.0000000Z"

            def monotonic(self) -> float:
                return 0.0

        clock = ExactClock()
        authorization = driver.WindowAuthorization(
            window_id="window-1",
            phases=("vulkan_baseline",),
            boot_id="boot-1",
            nonce=_AUTH_NONCE_A,
            issued_at="2026-07-14T08:00:00.0000001Z",
            expires_at="2026-07-14T12:00:00.0000001Z",
            owner="any-owner-label",
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-1",
                clock=clock,
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        _assert_refusal(exc, "authorization_not_yet_valid")
        assert clock.calls == 1
        assert list(private_root.rglob("*")) == []

    @pytest.mark.parametrize(
        "case",
        ["wrong_type", "wrong_phase_scope", "wrong_boot", "not_yet", "expired_equal"],
    )
    def test_baseline_prevalidation_refusals_never_publish_a_marker(
        self, private_root: Path, case: str
    ) -> None:
        authorization: object = driver.WindowAuthorization(
            window_id="window-1",
            phases=("vulkan_baseline",),
            boot_id="boot-1",
            nonce=_AUTH_NONCE_A,
            issued_at="2026-07-14T08:00:00Z",
            expires_at="2026-07-14T12:00:00Z",
            owner="any-owner-label",
        )
        boot_id = "boot-1"
        now = "2026-07-14T11:30:00Z"
        expected = "authorization_scope_mismatch"
        if case == "wrong_type":
            authorization = driver.Continuation(
                **{
                    **_continuation_fields(),
                    "phases": ("cuda_candidate",),
                }  # type: ignore[arg-type]
            )
        elif case == "wrong_phase_scope":
            authorization = replace(authorization, phases=("cuda_candidate",))
        elif case == "wrong_boot":
            boot_id = "other-boot"
            expected = "authorization_boot_mismatch"
        elif case == "not_yet":
            now = "2026-07-14T07:59:59Z"
            expected = "authorization_not_yet_valid"
        else:
            now = "2026-07-14T12:00:00Z"
            expected = "authorization_expired"

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id=boot_id,
                clock=driver.FrozenClock(now),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        _assert_refusal(exc, expected)
        assert list(private_root.rglob("*")) == []

    @pytest.mark.parametrize(
        ("case", "expected"),
        [
            ("missing_window", "continuation_missing"),
            ("missing_packet", "continuation_missing"),
            ("non_vulkan", "continuation_parent_mismatch"),
            ("non_completed", "continuation_parent_mismatch"),
            ("tampered", "continuation_parent_mismatch"),
            ("packet_window", "authorization_scope_mismatch"),
            ("packet_boot", "authorization_scope_mismatch"),
        ],
    )
    def test_cuda_parent_refusals_are_typed_and_precede_marker_publication(
        self, private_root: Path, case: str, expected: str
    ) -> None:
        window, continuation, packet = _cuda_authorities()
        parent_window: object | None = window
        parent_packet: driver.cm.PhasePacket | None = packet
        if case == "missing_window":
            parent_window = None
        elif case == "missing_packet":
            parent_packet = None
        elif case == "non_vulkan":
            parent_packet = _scorer_phase_packet("cuda_candidate")
            continuation = replace(
                continuation,
                parent_vulkan_packet_sha256=parent_packet.binding_sha256,
            )
        elif case == "non_completed":
            object.__setattr__(packet, "outcome", "crash")
        elif case == "tampered":
            object.__setattr__(packet, "timestamp", "2026-07-13T12:11:00Z")
        elif case == "packet_window":
            object.__setattr__(packet, "window_id", "other-window")
            continuation = replace(
                continuation,
                parent_vulkan_packet_sha256=packet.binding_sha256,
            )
        elif case == "packet_boot":
            object.__setattr__(packet, "boot_id", "other-boot")
            continuation = replace(
                continuation,
                parent_vulkan_packet_sha256=packet.binding_sha256,
            )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                continuation,
                phase="cuda_candidate",
                boot_id="boot-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=parent_window,  # type: ignore[arg-type]
                parent_packet=parent_packet,
            )
        _assert_refusal(exc, expected)
        assert list(private_root.rglob("*")) == []

    @pytest.mark.parametrize("field", ["owner", "window_id", "boot_id"])
    def test_continuation_must_match_every_parent_window_scope_field(
        self, private_root: Path, field: str
    ) -> None:
        window, continuation, packet = _cuda_authorities()
        window = replace(window, **{field: f"different-{field}"})

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                continuation,
                phase="cuda_candidate",
                boot_id="boot-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=window,
                parent_packet=packet,
            )
        _assert_refusal(exc, "authorization_scope_mismatch")
        assert list(private_root.rglob("*")) == []

    def test_different_same_label_parent_window_cannot_extend_cuda_authority(
        self, private_root: Path
    ) -> None:
        window, continuation, packet = _cuda_authorities()
        later_window = replace(
            window,
            issued_at="2026-07-14T09:00:00Z",
            expires_at="2026-07-14T13:00:00Z",
        )
        continuation = replace(
            continuation,
            issued_at="2026-07-14T12:00:00Z",
            expires_at="2026-07-14T13:00:00Z",
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                continuation,
                phase="cuda_candidate",
                boot_id="boot-1",
                clock=driver.FrozenClock("2026-07-14T12:30:00Z"),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=later_window,
                parent_packet=packet,
            )
        _assert_refusal(exc, "continuation_parent_mismatch")
        assert list(private_root.rglob("*")) == []

    def test_continuation_cannot_outlive_parent_window(self, private_root: Path) -> None:
        window, continuation, packet = _cuda_authorities()
        continuation = replace(
            continuation,
            issued_at="2026-07-14T11:30:00Z",
            expires_at="2026-07-14T12:30:00Z",
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                continuation,
                phase="cuda_candidate",
                boot_id="boot-1",
                clock=driver.FrozenClock("2026-07-14T12:00:00Z"),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=window,
                parent_packet=packet,
            )
        _assert_refusal(exc, "authorization_expired")
        assert list(private_root.rglob("*")) == []

    def test_second_and_concurrent_consumers_observe_the_atomic_marker(
        self, private_root: Path
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{**_window_fields(), "phases": ("vulkan_baseline",)}  # type: ignore[arg-type]
        )
        policy = driver.ProductionArtifactPolicy()
        gate = driver.RealAuthorizationGate(policy)
        kwargs = {
            "phase": "vulkan_baseline",
            "boot_id": "boot-1",
            "parent_window": None,
            "parent_packet": None,
            "root": private_root,
            "clock": driver.FrozenClock("2026-07-14T11:30:00Z"),
        }

        first = gate.consume(authorization, **kwargs)
        with pytest.raises(driver.BenchRefusal) as exc:
            gate.consume(authorization, **kwargs)
        _assert_refusal(exc, "authorization_consumed")
        assert first.preimage_sha256 == authorization.preimage_sha256

        other_root = private_root.parent / "concurrent"
        other_root.mkdir(mode=0o700)
        other_auth = replace(authorization, nonce="d" * 64)
        concurrent_kwargs = {**kwargs, "root": other_root}

        def consume() -> object:
            try:
                return gate.consume(other_auth, **concurrent_kwargs)
            except driver.BenchRefusal as refusal:
                return refusal.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _index: consume(), range(2)))
        assert sum(isinstance(outcome, driver.ConsumedAuthority) for outcome in outcomes) == 1
        assert outcomes.count("authorization_consumed") == 1

    def test_loser_at_marker_publication_boundary_never_observes_filesystem_hazard(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{**_window_fields(), "phases": ("vulkan_baseline",)}  # type: ignore[arg-type]
        )
        marker = private_root / "markers" / authorization.nonce
        published = threading.Event()
        loser_snapshotted = threading.Event()
        winner_crossed_boundary = threading.Event()
        real_fchmod = driver.os.fchmod
        real_link = driver.os.link
        real_verify_path_binding = driver._verify_path_binding

        def controlled_fchmod(fd: int, mode: int) -> None:
            if (
                threading.current_thread().name == "marker-winner"
                and os.path.lexists(marker)
            ):
                published.set()
                if not loser_snapshotted.wait(timeout=5):
                    raise AssertionError("loser did not snapshot published marker")
                real_fchmod(fd, mode)
                winner_crossed_boundary.set()
                return
            real_fchmod(fd, mode)

        def controlled_link(
            src: object, dst: object, *args: object, **kwargs: object
        ) -> None:
            real_link(src, dst, *args, **kwargs)  # type: ignore[arg-type]
            if (
                threading.current_thread().name == "marker-winner"
                and dst == authorization.nonce
            ):
                published.set()
                if not loser_snapshotted.wait(timeout=5):
                    raise AssertionError("loser did not snapshot linked marker")
                winner_crossed_boundary.set()

        def controlled_verify_path_binding(
            *args: object, **kwargs: object
        ) -> None:
            if threading.current_thread().name == "marker-loser":
                loser_snapshotted.set()
                if not winner_crossed_boundary.wait(timeout=5):
                    raise AssertionError("winner did not cross publication boundary")
            real_verify_path_binding(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(driver.os, "fchmod", controlled_fchmod)
        monkeypatch.setattr(driver.os, "link", controlled_link)
        monkeypatch.setattr(
            driver,
            "_verify_path_binding",
            controlled_verify_path_binding,
        )
        gate = driver.RealAuthorizationGate(driver.ProductionArtifactPolicy())
        kwargs = {
            "phase": "vulkan_baseline",
            "boot_id": "boot-1",
            "parent_window": None,
            "parent_packet": None,
            "root": private_root,
            "clock": driver.FrozenClock("2026-07-14T11:30:00Z"),
        }
        outcomes: dict[str, str] = {}

        def consume(label: str) -> None:
            if label == "loser" and not published.wait(timeout=5):
                outcomes[label] = "publication_timeout"
                return
            try:
                gate.consume(authorization, **kwargs)
                outcomes[label] = "created"
            except driver.BenchRefusal as refusal:
                outcomes[label] = refusal.code
            except BaseException as exc:  # test captures thread failures deterministically
                outcomes[label] = type(exc).__name__

        winner = threading.Thread(
            target=consume,
            args=("winner",),
            name="marker-winner",
        )
        loser = threading.Thread(
            target=consume,
            args=("loser",),
            name="marker-loser",
        )
        winner.start()
        loser.start()
        winner.join(timeout=10)
        loser.join(timeout=10)

        assert not winner.is_alive()
        assert not loser.is_alive()
        assert sorted(outcomes.values()) == ["authorization_consumed", "created"]

    def test_receipt_write_failure_leaves_the_published_marker_burned(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{**_window_fields(), "phases": ("vulkan_baseline",)}  # type: ignore[arg-type]
        )
        monkeypatch.setattr(
            driver,
            "write_private_file",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                driver.BenchRefusal("filesystem_hazard")
            ),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        _assert_refusal(exc, "filesystem_hazard")
        assert driver.open_bench_file(
            f"markers/{authorization.nonce}", root=private_root
        ) == b""

    def test_anchored_marker_eexist_is_consumed_without_path_exists_probe(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{**_window_fields(), "phases": ("vulkan_baseline",)}  # type: ignore[arg-type]
        )
        marker_dir = private_root / "markers"
        marker_dir.mkdir(mode=0o700)
        _private_file(marker_dir / authorization.nonce, b"")
        monkeypatch.setattr(
            Path,
            "exists",
            lambda *_args: (_ for _ in ()).throw(AssertionError("TOCTOU exists probe")),
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        _assert_refusal(exc, "authorization_consumed")

    @pytest.mark.parametrize(
        "case",
        ["symlink", "directory", "wrong_mode", "nonzero_size", "hardlink"],
    )
    def test_eexist_marker_requires_verified_private_empty_regular_file(
        self, private_root: Path, case: str
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{**_window_fields(), "phases": ("vulkan_baseline",)}  # type: ignore[arg-type]
        )
        marker_dir = private_root / "markers"
        marker_dir.mkdir(mode=0o700)
        marker = marker_dir / authorization.nonce
        if case == "symlink":
            target = private_root / "symlink-target"
            _private_file(target, b"")
            marker.symlink_to(target)
        elif case == "directory":
            marker.mkdir(mode=0o700)
        elif case == "wrong_mode":
            _private_file(marker, b"")
            os.chmod(marker, 0o640)
        elif case == "nonzero_size":
            _private_file(marker, b"not-an-empty-consumption-marker")
        else:
            source = private_root / "hardlink-source"
            _private_file(source, b"")
            os.link(source, marker)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        _assert_refusal(exc, "filesystem_hazard")
        assert list((private_root / "receipts").glob("*.json")) == []

    def test_eexist_marker_path_substitution_is_filesystem_hazard(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{**_window_fields(), "phases": ("vulkan_baseline",)}  # type: ignore[arg-type]
        )
        marker_dir = private_root / "markers"
        marker_dir.mkdir(mode=0o700)
        marker = marker_dir / authorization.nonce
        _private_file(marker, b"")
        verify_path_binding = driver._verify_path_binding

        def substitute_marker_before_binding_check(*args: object, **kwargs: object) -> None:
            marker.unlink()
            _private_file(marker, b"")
            verify_path_binding(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(
            driver,
            "_verify_path_binding",
            substitute_marker_before_binding_check,
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        _assert_refusal(exc, "filesystem_hazard")
        assert list((private_root / "receipts").glob("*.json")) == []

    def test_receipt_encoding_happens_before_marker_publication(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{**_window_fields(), "phases": ("vulkan_baseline",)}  # type: ignore[arg-type]
        )
        monkeypatch.setattr(
            driver.ProductionArtifactPolicy,
            "encode",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("encode failed")),
        )
        with pytest.raises(ValueError, match="encode failed"):
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                root=private_root,
                policy=driver.ProductionArtifactPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        assert list(private_root.rglob("*")) == []

    def test_rehearsal_gate_is_incompatible_confined_and_does_not_burn_nonce(
        self, private_root: Path
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{**_window_fields(), "phases": ("vulkan_baseline",)}  # type: ignore[arg-type]
        )
        canonical_input = private_root / "authorizations" / "window.json"
        canonical_input.parent.mkdir(mode=0o700)
        _private_file(
            canonical_input,
            _authorization_wrapper("window_authorization", _window_fields()),
        )
        before = {
            path.relative_to(private_root).as_posix(): path.read_bytes()
            for path in private_root.rglob("*")
            if path.is_file()
        }
        policy = driver.RehearsalArtifactPolicy()
        result = driver.RehearsalAuthorizationGate(policy).consume(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-1",
            parent_window=None,
            parent_packet=None,
            root=private_root,
            clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
        )
        after_outside = {
            path.relative_to(private_root).as_posix(): path.read_bytes()
            for path in private_root.rglob("*")
            if path.is_file() and "rehearsal" not in path.relative_to(private_root).parts
        }
        rehearsal_files = [
            path
            for path in (private_root / "rehearsal").rglob("*")
            if path.is_file()
        ]

        assert after_outside == before
        assert len(rehearsal_files) == 1
        wrapper = json.loads(rehearsal_files[0].read_bytes())
        assert set(wrapper) == {"rehearsal_schema", "tier", "payload"}
        assert wrapper["rehearsal_schema"] == driver.REHEARSAL_PACKET_SCHEMA
        assert wrapper["payload"]["schema"] == driver.CONSUMPTION_RECEIPT_SCHEMA
        assert wrapper["payload"]["fields"]["timestamp"] == (
            "2026-07-14T11:30:00.000000Z"
        )
        assert result.consumption_receipt_sha256 == wrapper["payload"]["binding_sha256"]
        assert not (private_root / "markers").exists()

        real_policy = driver.ProductionArtifactPolicy()
        real = driver.RealAuthorizationGate(real_policy).consume(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-1",
            parent_window=None,
            parent_packet=None,
            root=private_root,
            clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
        )
        assert real.preimage_sha256 == result.preimage_sha256

    def test_rehearsal_receipt_name_survives_process_local_sequence_reset(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{**_window_fields(), "phases": ("vulkan_baseline",)}  # type: ignore[arg-type]
        )
        policy = driver.RehearsalArtifactPolicy()
        gate = driver.RehearsalAuthorizationGate(policy)
        kwargs = {
            "phase": "vulkan_baseline",
            "boot_id": "boot-1",
            "parent_window": None,
            "parent_packet": None,
            "root": private_root,
            "clock": driver.FrozenClock("2026-07-14T11:30:00Z"),
        }

        monkeypatch.setattr(driver, "_AUTHORIZATION_RECEIPT_SEQUENCE", iter([0]))
        gate.consume(authorization, **kwargs)
        monkeypatch.setattr(driver, "_AUTHORIZATION_RECEIPT_SEQUENCE", iter([0]))
        gate.consume(authorization, **kwargs)

        receipts = list((private_root / "rehearsal" / "receipts").glob("*.json"))
        assert len(receipts) == 2
        assert not (private_root / "markers").exists()

    def test_all_inv_2_surfaces_keep_the_identical_postponed_annotation(self) -> None:
        surfaces = (
            driver.AuthorizationGate.consume,
            driver.RealAuthorizationGate.consume,
            driver.RehearsalAuthorizationGate.consume,
            driver.consume_authorization,
        )
        for surface in surfaces:
            assert inspect.signature(surface).parameters["parent_packet"].annotation == (
                "cm.PhasePacket | None"
            )
            assert surface.__annotations__["parent_packet"] == "cm.PhasePacket | None"

    @pytest.mark.parametrize("tier", ["production", "rehearsal"])
    def test_factory_returns_concrete_gate_with_the_identical_policy_object(
        self, tier: str
    ) -> None:
        components = _provider_components(tier)
        factory = driver.production_tier if tier == "production" else driver.rehearsal_tier
        providers = factory(**components)
        expected_type = (
            driver.RealAuthorizationGate
            if tier == "production"
            else driver.RehearsalAuthorizationGate
        )
        assert type(providers.authorization_gate) is expected_type
        assert providers.authorization_gate.policy is providers.artifact_policy

    def test_factory_refuses_equal_but_distinct_gate_policy_before_any_write(
        self, private_root: Path
    ) -> None:
        components = _provider_components("production")
        components["artifact_policy"] = driver.ProductionArtifactPolicy()

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.production_tier(**components)
        _assert_refusal(exc, "tier_mismatch")
        assert list(private_root.rglob("*")) == []
