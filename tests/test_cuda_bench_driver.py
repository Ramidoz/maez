"""Tests for the inert CUDA bench driver's private core."""

from __future__ import annotations

import inspect
import json
import os
import stat
from collections.abc import Iterator, Mapping
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
