"""Tests for the inert CUDA bench driver's private core."""

from __future__ import annotations

import ast
import errno
import fcntl
import hashlib
import http.client
import inspect
import json
import os
import re
import select
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.request
from contextlib import AbstractContextManager
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Iterator, Mapping
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

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
    "PHASE_PACKET_SCHEMA": "cuda_bench_driver.phase_packet.v2",
    "REFUSAL_SCHEMA": "cuda_bench_driver.refusal.v1",
    "WINDOW_AUTHORIZATION_SCHEMA": "cuda_bench_driver.window_authorization.v1",
    "CONTINUATION_SCHEMA": "cuda_bench_driver.continuation.v1",
    "CONSUMPTION_RECEIPT_SCHEMA": "cuda_bench_driver.consumption_receipt.v1",
    "TURN_MANIFEST_SCHEMA": "cuda_bench_driver.turn_manifest.v1",
    "TURN_ARTIFACT_SCHEMA": "cuda_bench_driver.turn_artifact.v1",
    "CONTAINMENT_SNAPSHOT_SCHEMA": "cuda_bench_driver.containment_snapshot.v2",
    "RUNTIME_IDENTITY_SCHEMA": "cuda_bench_driver.runtime_identity.v1",
    "ASSEMBLE_RECEIPT_SCHEMA": "cuda_bench_assemble.receipt.v1",
    "REHEARSAL_PACKET_SCHEMA": "cuda_bench_rehearsal.packet.v1",
}

STUB_PATH = Path(__file__).resolve().parents[1] / "scripts" / "cuda_bench_stub.py"
STUB_SHA256 = hashlib.sha256(STUB_PATH.read_bytes()).hexdigest()


@dataclass
class _TestProcessLease:
    pid: int
    pidfd: int
    popen: subprocess.Popen[bytes] | subprocess.Popen[str] | None
    isolated_pgid: int | None
    product_pidfds: set[tuple[int, int, int, int]]
    ports: set[int]


def _stub_argv(*extra: str) -> list[str]:
    return [
        sys.executable,
        "-B",
        "-I",
        str(STUB_PATH),
        "--persona",
        "healthy",
        "--alias",
        "qwen36-27b-mtp",
        *extra,
    ]


def _stub_pin(*, digest: str = STUB_SHA256) -> object:
    return driver.SpawnPin(
        kind="python_file",
        pinned_path=STUB_PATH,
        pinned_sha256=digest,
        required_argv_prefix=(sys.executable, "-B", "-I", str(STUB_PATH)),
    )


def _binary_pin(path: Path) -> object:
    return driver.SpawnPin(
        kind="binary",
        pinned_path=path,
        pinned_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        required_argv_prefix=(str(path),),
    )


def _python_file_pin(path: Path, digest: str) -> object:
    return driver.SpawnPin(
        kind="python_file",
        pinned_path=path,
        pinned_sha256=digest,
        required_argv_prefix=(sys.executable, "-B", "-I", str(path)),
    )


def _free_loopback_port() -> int:
    while True:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", 0))
            port = int(probe.getsockname()[1])
        if port != driver.BENCH_PORT:
            return port


def _write_listener_script(path: Path, sentinel: Path, port: int) -> None:
    path.write_text(
        "import os,pathlib,socket,sys,time\n"
        "prefix='/proc/self/fd/'\n"
        "if sys.argv[0].startswith(prefix): os.close(int(sys.argv[0][len(prefix):]))\n"
        f"pathlib.Path({str(sentinel)!r}).touch()\n"
        "server=socket.socket()\n"
        "server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\n"
        f"server.bind(('127.0.0.1',{port}))\n"
        "server.listen()\n"
        f"print('STUB_LISTENING port={port}',flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )


def _stub_env(**extra: str) -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", "/home/rohit"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONUNBUFFERED": "1",
        **extra,
    }


def _health(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=1
        ) as response:
            return response.status == 200
    except OSError:
        return False


def _wait_for(predicate: Callable[[], bool], *, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


def _test_process_identity(pid: int) -> tuple[int, int, str]:
    rendered = Path(f"/proc/{pid}/stat").read_text()
    suffix = rendered[rendered.rfind(")") + 2 :].split()
    pgid = int(suffix[2])
    start_time_ticks = int(suffix[19])
    exe_sha256 = hashlib.sha256(Path(f"/proc/{pid}/exe").read_bytes()).hexdigest()
    return pgid, start_time_ticks, exe_sha256


@pytest.fixture
def private_root(tmp_path: Path) -> Path:
    root = tmp_path / "bench"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return root


def _private_file(path: Path, payload: bytes = b"evidence") -> None:
    path.write_bytes(payload)
    os.chmod(path, 0o600)


class TestTask4ImmutablePreimage:
    def test_publish_or_verify_immutable_creates_preimages_only_for_static(
        self, private_root: Path
    ) -> None:
        attempt = _command_admit(private_root)
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(b"rollback").hexdigest()
            + ".json"
        )

        path = driver.publish_or_verify_immutable(
            relative, b"rollback", attempt=attempt, root=private_root
        )

        assert path == private_root / relative
        assert path.read_bytes() == b"rollback"
        assert stat.S_IMODE((private_root / "preimages").stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_publish_or_verify_immutable_accepts_exact_existing_bytes(
        self, private_root: Path
    ) -> None:
        attempt = _command_admit(private_root)
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(b"rollback").hexdigest()
            + ".json"
        )
        first = driver.publish_or_verify_immutable(
            relative, b"rollback", attempt=attempt, root=private_root
        )

        second = driver.publish_or_verify_immutable(
            relative, b"rollback", attempt=attempt, root=private_root
        )

        assert first == second

    def test_publish_or_verify_immutable_rejects_mismatched_existing_bytes(
        self, private_root: Path
    ) -> None:
        attempt = _command_admit(private_root)
        expected = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(expected).hexdigest()
            + ".json"
        )
        preimages = private_root / "preimages"
        preimages.mkdir(mode=0o700)
        os.chmod(preimages, 0o700)
        _private_file(private_root / relative, b"different")

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, expected, attempt=attempt, root=private_root
            )

    def test_publish_or_verify_immutable_requires_content_addressed_name(
        self, private_root: Path
    ) -> None:
        attempt = _command_admit(private_root)
        relative = "preimages/rollback-manifest-" + ("a" * 64) + ".json"

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, b"rollback", attempt=attempt, root=private_root
            )

        assert not (private_root / "preimages").exists()

    def test_verify_existing_immutable_never_creates_missing_preimages(
        self, private_root: Path
    ) -> None:
        attempt = _command_admit(
            private_root, command="vulkan-baseline", window_id="window-a"
        )
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(b"rollback").hexdigest()
            + ".json"
        )

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.verify_existing_immutable(
                relative, b"rollback", attempt=attempt, root=private_root
            )

        assert not (private_root / "preimages").exists()

    def test_publish_or_verify_immutable_reopens_admission_under_exact_root(
        self, tmp_path: Path
    ) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        for root in (root_a, root_b):
            root.mkdir(mode=0o700)
            os.chmod(root, 0o700)
        attempt = _command_admit(root_a)
        copied_admission = root_b / attempt.admission_ref
        _private_file(
            copied_admission,
            (root_a / attempt.admission_ref).read_bytes(),
        )
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(b"rollback").hexdigest()
            + ".json"
        )

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, b"rollback", attempt=attempt, root=root_b
            )
        assert not (root_b / "preimages").exists()

    def test_publish_or_verify_immutable_refuses_same_inode_admission_corruption(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempt = _command_admit(private_root)
        admission = private_root / attempt.admission_ref
        original = admission.read_bytes()
        corrupted = bytes([original[0] ^ 1]) + original[1:]
        assert len(corrupted) == len(original)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        real_write_all = driver._write_all
        fired = False

        def corrupt_after_authority_read(fd: int, payload: bytes) -> None:
            nonlocal fired
            if payload == data and not fired:
                fired = True
                admission.write_bytes(corrupted)
                os.chmod(admission, 0o600)
            real_write_all(fd, payload)

        monkeypatch.setattr(driver, "_write_all", corrupt_after_authority_read)

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, data, attempt=attempt, root=private_root
            )

        assert fired

    @pytest.mark.parametrize("mutation", ("delete", "replace"))
    def test_publish_or_verify_immutable_refuses_deleted_or_replaced_admission(
        self, private_root: Path, mutation: str
    ) -> None:
        attempt = _command_admit(private_root)
        admission = private_root / attempt.admission_ref
        admission.unlink()
        if mutation == "replace":
            _private_file(admission, b"replacement")
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(b"rollback").hexdigest()
            + ".json"
        )

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, b"rollback", attempt=attempt, root=private_root
            )
        assert not (private_root / "preimages").exists()

    def test_publish_or_verify_immutable_refuses_exact_bytes_replacement(
        self, private_root: Path
    ) -> None:
        attempt = _command_admit(private_root)
        admission = private_root / attempt.admission_ref
        original = admission.read_bytes()
        admission.unlink()
        _private_file(admission, original)
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(b"rollback").hexdigest()
            + ".json"
        )

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, b"rollback", attempt=attempt, root=private_root
            )

        assert not (private_root / "preimages").exists()

    def test_verify_existing_immutable_rejects_static_attempt_namespace(
        self, private_root: Path
    ) -> None:
        static_attempt = _command_admit(private_root)
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(b"rollback").hexdigest()
            + ".json"
        )
        driver.publish_or_verify_immutable(
            relative, b"rollback", attempt=static_attempt, root=private_root
        )

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.verify_existing_immutable(
                relative, b"rollback", attempt=static_attempt, root=private_root
            )

    @pytest.mark.parametrize(
        "command", ("vulkan-baseline", "cuda-candidate")
    )
    def test_verify_existing_immutable_accepts_each_phase_namespace(
        self, private_root: Path, command: str
    ) -> None:
        static_attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        driver.publish_or_verify_immutable(
            relative, data, attempt=static_attempt, root=private_root
        )
        phase_attempt = _command_admit(
            private_root, command=command, window_id="window-a"
        )

        assert driver.verify_existing_immutable(
            relative, data, attempt=phase_attempt, root=private_root
        ) == private_root / relative

    @pytest.mark.parametrize("hazard", ("symlink_dir", "wrong_mode_dir"))
    def test_publish_or_verify_immutable_refuses_preimages_directory_hazard(
        self, private_root: Path, tmp_path: Path, hazard: str
    ) -> None:
        attempt = _command_admit(private_root)
        preimages = private_root / "preimages"
        if hazard == "symlink_dir":
            outside = tmp_path / "outside"
            outside.mkdir(mode=0o700)
            preimages.symlink_to(outside, target_is_directory=True)
        else:
            preimages.mkdir(mode=0o755)
            os.chmod(preimages, 0o755)
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(b"rollback").hexdigest()
            + ".json"
        )

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, b"rollback", attempt=attempt, root=private_root
            )

    @pytest.mark.parametrize("hazard", ("hardlink", "wrong_mode"))
    def test_verify_existing_immutable_refuses_file_hazard(
        self, private_root: Path, hazard: str
    ) -> None:
        static_attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        path = driver.publish_or_verify_immutable(
            relative, data, attempt=static_attempt, root=private_root
        )
        if hazard == "hardlink":
            os.link(path, private_root / "second-link")
        else:
            os.chmod(path, 0o640)
        phase_attempt = _command_admit(
            private_root, command="vulkan-baseline", window_id="window-a"
        )

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.verify_existing_immutable(
                relative, data, attempt=phase_attempt, root=private_root
            )

    def test_publish_or_verify_immutable_post_link_parent_fsync_failure_refuses(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        static_attempt = _command_admit(private_root)
        preimages = private_root / "preimages"
        preimages.mkdir(mode=0o700)
        os.chmod(preimages, 0o700)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        real_fsync = driver.os.fsync
        failed = False

        def fail_parent_once(fd: int) -> None:
            nonlocal failed
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not failed:
                failed = True
                raise OSError(errno.EIO, "parent fsync")
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", fail_parent_once)
        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, data, attempt=static_attempt, root=private_root
            )
        assert failed
        assert (private_root / relative).read_bytes() == data

        monkeypatch.setattr(driver.os, "fsync", real_fsync)
        assert driver.publish_or_verify_immutable(
            relative, data, attempt=static_attempt, root=private_root
        ) == private_root / relative

    def test_publish_or_verify_immutable_refuses_post_link_content_laundering(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempt = _command_admit(private_root)
        preimages = private_root / "preimages"
        preimages.mkdir(mode=0o700)
        os.chmod(preimages, 0o700)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        path = private_root / relative
        real_fsync = driver.os.fsync
        fired = False

        def mutate_before_parent_sync_returns(fd: int) -> None:
            nonlocal fired
            if stat.S_ISDIR(os.fstat(fd).st_mode) and not fired:
                fired = True
                path.write_bytes(b"X" * len(data))
                os.chmod(path, 0o600)
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", mutate_before_parent_sync_returns)

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, data, attempt=attempt, root=private_root
            )

        assert fired
        assert path.read_bytes() != data

    def test_publish_or_verify_immutable_rebinds_parent_after_final_read(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempt = _command_admit(private_root)
        preimages = private_root / "preimages"
        preimages.mkdir(mode=0o700)
        os.chmod(preimages, 0o700)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        real_read_exact = driver._read_exact_immutable
        calls = 0

        def substitute_after_final_read(
            parent_fd: int, name: str, expected: bytes
        ) -> os.stat_result:
            nonlocal calls
            observed = real_read_exact(parent_fd, name, expected)
            calls += 1
            if calls == 1:
                preimages.rename(private_root / "preimages-original")
                preimages.mkdir(mode=0o700)
                os.chmod(preimages, 0o700)
                _private_file(preimages / name, expected)
            return observed

        monkeypatch.setattr(
            driver, "_read_exact_immutable", substitute_after_final_read
        )

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, data, attempt=attempt, root=private_root
            )

        assert calls == 1

    @pytest.mark.parametrize("target", ("file", "parent"))
    def test_publish_or_verify_immutable_existing_durability_failure_refuses(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        target: str,
    ) -> None:
        static_attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        driver.publish_or_verify_immutable(
            relative, data, attempt=static_attempt, root=private_root
        )
        real_fsync = driver.os.fsync
        failed = False
        regular_syncs = 0

        def fail_selected_once(fd: int) -> None:
            nonlocal failed, regular_syncs
            is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            if not is_directory:
                regular_syncs += 1
            selected = (
                is_directory
                if target == "parent"
                else (not is_directory and regular_syncs == 2)
            )
            if not failed and selected:
                failed = True
                raise OSError(errno.EIO, "durability")
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", fail_selected_once)
        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, data, attempt=static_attempt, root=private_root
            )
        assert failed

    def test_publish_or_verify_immutable_orders_file_fsync_link_parent_fsync(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempt = _command_admit(private_root)
        preimages = private_root / "preimages"
        preimages.mkdir(mode=0o700)
        os.chmod(preimages, 0o700)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        events: list[str] = []
        real_fsync = driver.os.fsync
        real_link = driver.os.link

        def observed_fsync(fd: int) -> None:
            events.append(
                "parent_fsync"
                if stat.S_ISDIR(os.fstat(fd).st_mode)
                else "file_fsync"
            )
            real_fsync(fd)

        def observed_link(*args: object, **kwargs: object) -> None:
            events.append("link")
            real_link(*args, **kwargs)

        monkeypatch.setattr(driver.os, "fsync", observed_fsync)
        monkeypatch.setattr(driver.os, "link", observed_link)

        driver.publish_or_verify_immutable(
            relative, data, attempt=attempt, root=private_root
        )

        assert events.index("file_fsync") < events.index("link")
        assert events.index("link") < events.index("parent_fsync")

    def test_publish_or_verify_immutable_file_fsync_failure_leaves_no_final_name(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        real_fsync = driver.os.fsync

        def fail_regular(fd: int) -> None:
            if stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError(errno.EIO, "file fsync")
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", fail_regular)

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, data, attempt=attempt, root=private_root
            )

        assert not (private_root / relative).exists()

    def test_publish_or_verify_immutable_exact_eexist_syncs_file_and_parent(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        driver.publish_or_verify_immutable(
            relative, data, attempt=attempt, root=private_root
        )
        syncs: list[str] = []
        real_fsync = driver.os.fsync

        def observed(fd: int) -> None:
            syncs.append(
                "parent"
                if stat.S_ISDIR(os.fstat(fd).st_mode)
                else "file"
            )
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", observed)

        driver.publish_or_verify_immutable(
            relative, data, attempt=attempt, root=private_root
        )

        assert "file" in syncs
        assert "parent" in syncs

    def test_publish_or_verify_immutable_non_eexist_link_failure_never_reopens(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        preimages = private_root / "preimages"
        preimages.mkdir(mode=0o700)
        os.chmod(preimages, 0o700)
        _private_file(private_root / relative, data)

        def fail_link(*_args: object, **_kwargs: object) -> None:
            raise OSError(errno.EIO, "not EEXIST")

        monkeypatch.setattr(driver.os, "link", fail_link)

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, data, attempt=attempt, root=private_root
            )

    def test_publish_or_verify_immutable_has_no_broad_link_error_branch(
        self,
    ) -> None:
        source = inspect.getsource(driver.publish_or_verify_immutable)
        tree = ast.parse(source)
        handlers = [
            handler
            for node in ast.walk(tree)
            if isinstance(node, ast.Try)
            for handler in node.handlers
        ]
        names = {
            ast.unparse(handler.type)
            for handler in handlers
            if handler.type is not None
        }

        assert "FileExistsError" in names
        assert not any(
            "BenchRefusal" in name or "Exception" in name
            for name in names
        )

    @pytest.mark.parametrize(
        "hazard",
        (
            "wrong_owner_dir",
            "mkdir_failure",
            "root_fsync_failure",
            "identity_substitution",
        ),
    )
    def test_publish_or_verify_immutable_refuses_each_directory_creation_hazard(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        hazard: str,
    ) -> None:
        attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        real_fstat = driver.os.fstat
        real_fsync = driver.os.fsync
        real_mkdir = driver.os.mkdir
        real_open = driver.os.open
        preimages_open_count = 0

        def wrong_owner_fstat(fd: int) -> os.stat_result:
            info = real_fstat(fd)
            try:
                rendered = os.readlink(f"/proc/self/fd/{fd}")
            except OSError:
                return info
            if rendered == str(private_root / "preimages"):
                return SimpleNamespace(
                    **{
                        name: getattr(info, name)
                        for name in (
                            "st_mode",
                            "st_dev",
                            "st_ino",
                            "st_nlink",
                            "st_size",
                            "st_mtime_ns",
                            "st_ctime_ns",
                        )
                    },
                    st_uid=os.geteuid() + 1,
                )
            return info

        def fail_mkdir(
            path: str,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> None:
            if path == "preimages":
                raise OSError(errno.EIO, "mkdir")
            real_mkdir(path, mode=mode, dir_fd=dir_fd)

        def fail_root_fsync(fd: int) -> None:
            try:
                rendered = os.readlink(f"/proc/self/fd/{fd}")
            except OSError:
                rendered = ""
            if rendered == str(private_root):
                raise OSError(errno.EIO, "root fsync")
            real_fsync(fd)

        def substitute_open(
            path: object,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            nonlocal preimages_open_count
            if path == "preimages":
                preimages_open_count += 1
                if preimages_open_count == 2:
                    (private_root / "preimages").rename(
                        private_root / "preimages-original"
                    )
                    (private_root / "preimages").mkdir(mode=0o700)
                    os.chmod(private_root / "preimages", 0o700)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        if hazard == "wrong_owner_dir":
            monkeypatch.setattr(driver.os, "fstat", wrong_owner_fstat)
        elif hazard == "mkdir_failure":
            monkeypatch.setattr(driver.os, "mkdir", fail_mkdir)
        elif hazard == "root_fsync_failure":
            monkeypatch.setattr(driver.os, "fsync", fail_root_fsync)
        else:
            monkeypatch.setattr(driver.os, "open", substitute_open)

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.publish_or_verify_immutable(
                relative, data, attempt=attempt, root=private_root
            )

    def test_publish_or_verify_immutable_accepts_exact_directory_creation_race(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        real_mkdir = driver.os.mkdir
        raced = False

        def race_mkdir(
            path: str,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> None:
            nonlocal raced
            if path == "preimages" and not raced:
                raced = True
                real_mkdir(path, mode=mode, dir_fd=dir_fd)
                raise FileExistsError(errno.EEXIST, "raced")
            real_mkdir(path, mode=mode, dir_fd=dir_fd)

        monkeypatch.setattr(driver.os, "mkdir", race_mkdir)

        assert driver.publish_or_verify_immutable(
            relative, data, attempt=attempt, root=private_root
        ) == private_root / relative
        assert raced

    def test_verify_existing_immutable_never_repairs_invalid_directory(
        self, private_root: Path
    ) -> None:
        static_attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        path = driver.publish_or_verify_immutable(
            relative, data, attempt=static_attempt, root=private_root
        )
        phase_attempt = _command_admit(
            private_root, command="vulkan-baseline", window_id="window-a"
        )
        preimages = path.parent
        os.chmod(preimages, 0o755)

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.verify_existing_immutable(
                relative, data, attempt=phase_attempt, root=private_root
            )

        assert stat.S_IMODE(preimages.stat().st_mode) == 0o755
        assert path.read_bytes() == data

    @pytest.mark.parametrize(
        "hazard", ("symlink", "wrong_owner", "inode_substitution")
    )
    def test_verify_existing_immutable_refuses_each_final_file_hazard(
        self,
        private_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        hazard: str,
    ) -> None:
        static_attempt = _command_admit(private_root)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        path = driver.publish_or_verify_immutable(
            relative, data, attempt=static_attempt, root=private_root
        )
        phase_attempt = _command_admit(
            private_root, command="cuda-candidate", window_id="window-a"
        )
        real_fstat = driver.os.fstat
        real_fsync = driver.os.fsync
        if hazard == "symlink":
            target = tmp_path / "target"
            _private_file(target, data)
            path.unlink()
            path.symlink_to(target)
        elif hazard == "wrong_owner":
            def wrong_owner(fd: int) -> os.stat_result:
                info = real_fstat(fd)
                try:
                    rendered = os.readlink(f"/proc/self/fd/{fd}")
                except OSError:
                    return info
                if rendered == str(path):
                    return SimpleNamespace(
                        **{
                            name: getattr(info, name)
                            for name in (
                                "st_mode",
                                "st_dev",
                                "st_ino",
                                "st_nlink",
                                "st_size",
                                "st_mtime_ns",
                                "st_ctime_ns",
                            )
                        },
                        st_uid=os.geteuid() + 1,
                    )
                return info

            monkeypatch.setattr(driver.os, "fstat", wrong_owner)
        else:
            fired = False

            def substitute_after_file_sync(fd: int) -> None:
                nonlocal fired
                if stat.S_ISREG(real_fstat(fd).st_mode) and not fired:
                    fired = True
                    path.rename(private_root / "preimages/original")
                    _private_file(path, data)
                real_fsync(fd)

            monkeypatch.setattr(driver.os, "fsync", substitute_after_file_sync)

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.verify_existing_immutable(
                relative, data, attempt=phase_attempt, root=private_root
            )

    @pytest.mark.parametrize(
        "mutation", ("root_b", "delete", "replace", "exact_replace")
    )
    def test_verify_existing_immutable_reopens_admission_and_root(
        self, tmp_path: Path, mutation: str
    ) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        for root in (root_a, root_b):
            root.mkdir(mode=0o700)
            os.chmod(root, 0o700)
        static_attempt = _command_admit(root_a)
        data = b"rollback"
        relative = (
            "preimages/rollback-manifest-"
            + hashlib.sha256(data).hexdigest()
            + ".json"
        )
        driver.publish_or_verify_immutable(
            relative, data, attempt=static_attempt, root=root_a
        )
        phase_attempt = _command_admit(
            root_a, command="vulkan-baseline", window_id="window-a"
        )
        root = root_a
        admission = root_a / phase_attempt.admission_ref
        original = admission.read_bytes()
        if mutation == "root_b":
            root = root_b
            (root_b / "preimages").mkdir(mode=0o700)
            os.chmod(root_b / "preimages", 0o700)
            _private_file(root_b / relative, data)
            _private_file(root_b / phase_attempt.admission_ref, original)
        else:
            admission.unlink()
            if mutation == "replace":
                _private_file(admission, b"replacement")
            elif mutation == "exact_replace":
                _private_file(admission, original)

        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            driver.verify_existing_immutable(
                relative, data, attempt=phase_attempt, root=root
            )


def _assert_refusal(exc: pytest.ExceptionInfo[driver.BenchRefusal], code: str) -> None:
    assert exc.value.code == code


def _assert_no_provider_witness_counter_conflation(
    source: str,
    *,
    label: str,
) -> None:
    field_names = {"real_calls", "loopback_kernel_calls"}
    tree = ast.parse(source)
    aliases: set[str] = set()
    assignments: list[tuple[list[ast.expr], ast.expr, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            assignments.append((list(node.targets), node.value, node.lineno))
        elif isinstance(node, ast.AnnAssign):
            assignments.append(([node.target], node.value, node.lineno))

    def simple_origin(value: ast.expr) -> bool:
        return (
            isinstance(value, ast.Attribute) and value.attr in field_names
        ) or (isinstance(value, ast.Name) and value.id in aliases)

    changed = True
    while changed:
        changed = False
        for targets, value, _lineno in assignments:
            if not simple_origin(value):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    changed = True
    if aliases:
        raise AssertionError(f"counter alias in {label}: {sorted(aliases)!r}")

    def referenced_counters(node: ast.AST) -> set[str]:
        return {
            child.attr
            for child in ast.walk(node)
            if isinstance(child, ast.Attribute) and child.attr in field_names
        }

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and referenced_counters(node):
            raise AssertionError(f"counter conflation in {label}:{node.lineno}")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"sum", "min", "max"}
            and referenced_counters(node)
        ):
            raise AssertionError(f"counter conflation in {label}:{node.lineno}")
        if (
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Attribute)
            and node.target.attr in field_names
            and referenced_counters(node.value)
        ):
            raise AssertionError(f"counter conflation in {label}:{node.lineno}")


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

    def is_free(
        self,
        _port: int,
        *,
        lease: driver.RehearsalPortLease | None = None,
    ) -> bool:
        if lease is not None:
            raise driver.BenchRefusal("provider_uncertain")
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

    def validate(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("factory invoked provider")

    def capture(self, *_args: object, **_kwargs: object) -> object:
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

    def setsockopt(self, _level: int, _option: int, _value: int) -> None:
        return

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
        server_launcher: object = driver.RealServerLauncher(
            _binary_pin(Path(sys.executable))
        )
        containment: object = driver.RealContainmentProvider(
            clock=clock,
            port_probe=port_probe,
            command_reader=lambda _argv: (_ for _ in ()).throw(
                AssertionError("live call")
            ),
            file_reader=lambda _path: (_ for _ in ()).throw(
                AssertionError("live call")
            ),
            environ_reader=lambda _pid: (_ for _ in ()).throw(
                AssertionError("live call")
            ),
        )
    else:
        rehearsal_ports = driver.RehearsalPortRegistry()
        service_state = driver.SyntheticServiceState({})
        port_probe = driver.SyntheticPortProbe(
            set(), rehearsal_ports=rehearsal_ports
        )
        gpu = driver.SyntheticGpu([], [], [])
        kernel = driver.SyntheticKernelLog(zero_counts)
        maps = driver.SyntheticBackendMap({})
        clock = driver.RehearsalClock()
        journal_factory = driver.RehearsalJournalFactory()
        artifact_policy = driver.RehearsalArtifactPolicy()
        authorization_gate = driver.RehearsalAuthorizationGate(artifact_policy)
        server_launcher = driver.RehearsalServerLauncher(
            _stub_pin(), rehearsal_ports=rehearsal_ports
        )
        containment = driver.SyntheticContainmentProvider(
            clock=clock,
            port_probe=port_probe,
            flag_source_sha256="a" * 64,
            vision_unit_sha256="b" * 64,
        )
    server_client = (
        driver.LoopbackServerClient.production(clock)
        if tier == "production"
        else driver.LoopbackServerClient.rehearsal(clock)
    )
    return {
        "service_state": service_state,
        "port_probe": port_probe,
        "gpu": gpu,
        "kernel_log": kernel,
        "backend_maps": maps,
        "server_launcher": server_launcher,
        "server_client": server_client,
        "authorization_gate": authorization_gate,
        "containment": containment,
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
            b'"fields":{"value":7},"schema":"cuda_bench_driver.phase_packet.v2"}\n'
        )
        assert rehearsal.encode("packet", document) == (
            b'{"payload":{"binding_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
            b'"fields":{"value":7},"kind":"packet"},'
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

    def test_rehearsal_turn_artifact_is_incompatible_with_production_schema(self) -> None:
        encoded = json.loads(
            driver.RehearsalArtifactPolicy().encode(
                "turn_artifact", {"literal": "private"}
            )
        )
        assert set(encoded) == {"rehearsal_schema", "tier", "payload"}
        assert encoded["payload"]["kind"] == "turn_artifact"
        assert "schema" not in encoded["payload"]
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

    def test_both_sealed_factories_assemble_all_twelve_seams(self) -> None:
        production = driver.production_tier(**_provider_components("production"))
        rehearsal = driver.rehearsal_tier(**_provider_components("rehearsal"))

        assert production.tier == "production"
        assert rehearsal.tier == "rehearsal"
        assert len(driver.Providers.__dataclass_fields__) == 13  # tier + twelve seams
        assert production.artifact_policy.tier == "production"
        assert rehearsal.artifact_policy.tier == "rehearsal"

    def test_factories_require_concrete_tier_gates_and_containment(self) -> None:
        for tier, factory in (
            ("production", driver.production_tier),
            ("rehearsal", driver.rehearsal_tier),
        ):
            components = _provider_components(tier)
            fake_gate = _TieredFake(tier)
            fake_gate.policy = components["artifact_policy"]  # type: ignore[attr-defined]
            components["authorization_gate"] = fake_gate
            with pytest.raises(driver.BenchRefusal) as gate_exc:
                factory(**components)
            _assert_refusal(gate_exc, "tier_mismatch")

            components = _provider_components(tier)
            components["containment"] = _TieredFake(tier)
            with pytest.raises(driver.BenchRefusal) as containment_exc:
                factory(**components)
            _assert_refusal(containment_exc, "tier_mismatch")

    @pytest.mark.parametrize("tier", ["production", "rehearsal"])
    def test_containment_clock_and_port_probe_are_identity_sealed(
        self, tier: str
    ) -> None:
        components = _provider_components(tier)
        containment = components["containment"]
        assert containment.clock is components["clock"]
        assert containment.port_probe is components["port_probe"]

        other = _provider_components(tier)
        components["containment"] = other["containment"]
        factory = driver.production_tier if tier == "production" else driver.rehearsal_tier
        with pytest.raises(driver.BenchRefusal) as exc:
            factory(**components)
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
            "containment",
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
            "containment",
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
                assert witness == driver.ProviderWitness(
                    synthetic=True,
                    real_calls=0,
                    loopback_kernel_calls=0,
                )

    @pytest.mark.parametrize(
        ("synthetic", "real_calls"),
        [(True, True), (True, -1), (True, 1), (False, False)],
    )
    def test_provider_witness_rejects_malformed_or_false_synthetic_claims(
        self, synthetic: bool, real_calls: object
    ) -> None:
        with pytest.raises(ValueError, match="provider_witness_invalid"):
            driver.ProviderWitness(synthetic=synthetic, real_calls=real_calls)  # type: ignore[arg-type]

    @pytest.mark.parametrize("loopback_kernel_calls", [True, -1, 1.0])
    def test_provider_witness_rejects_malformed_loopback_kernel_count(
        self, loopback_kernel_calls: object
    ) -> None:
        with pytest.raises(ValueError, match="provider_witness_invalid"):
            driver.ProviderWitness(
                synthetic=True,
                real_calls=0,
                loopback_kernel_calls=loopback_kernel_calls,  # type: ignore[arg-type]
            )

    def test_provider_witness_assertion_distinguishes_contact_dimensions(
        self,
    ) -> None:
        sanctioned = driver.ProviderWitness(
            synthetic=True,
            real_calls=0,
            loopback_kernel_calls=3,
        )
        sanctioned.assert_no_real_calls()
        with pytest.raises(
            AssertionError,
            match="synthetic_provider_contacted_real_surface",
        ):
            driver.ProviderWitness(
                synthetic=False,
                real_calls=0,
                loopback_kernel_calls=3,
            ).assert_no_real_calls()
        with pytest.raises(ValueError, match="provider_witness_invalid"):
            driver.ProviderWitness(
                synthetic=True,
                real_calls=1,
                loopback_kernel_calls=0,
            )

    def test_provider_witness_snapshot_is_frozen_and_cannot_mint_invalid_state(
        self,
    ) -> None:
        witness = driver.ProviderWitness(
            synthetic=True,
            real_calls=0,
            loopback_kernel_calls=2,
        )
        before_bytes = witness.canonical_bytes()
        before_hash = witness.binding_sha256
        for field, value in (
            ("real_calls", 1),
            ("real_calls", -1),
            ("loopback_kernel_calls", True),
            ("loopback_kernel_calls", -1),
        ):
            with pytest.raises(FrozenInstanceError):
                setattr(witness, field, value)
        assert witness.canonical_bytes() == before_bytes
        assert witness.binding_sha256 == before_hash

    def test_provider_exposes_read_only_stable_witness_snapshots(
        self,
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=registry,
        )
        port = _free_loopback_port()
        lease = registry.activate_from_launcher(registry.reserve_launch(), port)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen()
        before = probe.witness
        before_bytes = before.canonical_bytes()
        before_hash = before.binding_sha256
        try:
            assert probe.is_free(port, lease=lease) is False
        finally:
            listener.close()
        after = probe.witness

        assert before is not after
        assert before.canonical_bytes() == before_bytes
        assert before.binding_sha256 == before_hash
        assert before.loopback_kernel_calls == 0
        assert after.loopback_kernel_calls == 1
        assert before.real_calls == after.real_calls == 0
        after.assert_no_real_calls()
        with pytest.raises(AttributeError):
            probe.witness = before  # type: ignore[misc]

    def test_real_provider_advances_only_real_contact_dimension(self) -> None:
        probe = driver.RealPortProbe()
        before = probe.witness
        port = _free_loopback_port()

        assert probe.is_free(port) is True
        after = probe.witness

        assert before.real_calls == 0
        assert after.real_calls == 1
        assert before.loopback_kernel_calls == after.loopback_kernel_calls == 0
        assert before.binding_sha256 != after.binding_sha256

    def test_provider_witness_canonical_round_trip_binds_both_counters(
        self,
    ) -> None:
        witness = driver.ProviderWitness(
            synthetic=True,
            real_calls=0,
            loopback_kernel_calls=3,
        )
        expected = (
            b'{"loopback_kernel_calls":3,"real_calls":0,"synthetic":true}\n'
        )

        assert witness.canonical_bytes() == expected
        assert witness.binding_sha256 == hashlib.sha256(expected).hexdigest()
        assert (
            driver.ProviderWitness.from_canonical_bytes(
                expected,
                expected_binding_sha256=witness.binding_sha256,
            )
            == witness
        )

    def test_provider_witness_loopback_tamper_changes_binding_or_refuses(
        self,
    ) -> None:
        witness = driver.ProviderWitness(
            synthetic=True,
            real_calls=0,
            loopback_kernel_calls=3,
        )
        tampered = (
            b'{"loopback_kernel_calls":4,"real_calls":0,"synthetic":true}\n'
        )
        changed = driver.ProviderWitness.from_canonical_bytes(tampered)
        assert changed.binding_sha256 != witness.binding_sha256
        with pytest.raises(ValueError, match="provider_witness_binding_mismatch"):
            driver.ProviderWitness.from_canonical_bytes(
                tampered,
                expected_binding_sha256=witness.binding_sha256,
            )

    @pytest.mark.parametrize(
        "payload",
        [
            b'{"loopback_kernel_calls":3,"real_calls":0,"synthetic":true}',
            b'{"real_calls":0,"loopback_kernel_calls":3,"synthetic":true}\n',
            b'{"extra":0,"loopback_kernel_calls":3,"real_calls":0,"synthetic":true}\n',
            b'{"loopback_kernel_calls":3,"loopback_kernel_calls":4,"real_calls":0,"synthetic":true}\n',
        ],
    )
    def test_provider_witness_refuses_noncanonical_or_ambiguous_bytes(
        self, payload: bytes
    ) -> None:
        with pytest.raises(ValueError, match="provider_witness_serialization_invalid"):
            driver.ProviderWitness.from_canonical_bytes(payload)

    def test_provider_witness_structural_guard_rejects_aliased_conflation(
        self,
    ) -> None:
        violating_source = """
def collapse(witness):
    real = witness.real_calls
    inherited = real
    loopback = witness.loopback_kernel_calls
    return inherited + loopback
"""
        with pytest.raises(AssertionError, match="counter alias|counter conflation"):
            _assert_no_provider_witness_counter_conflation(
                violating_source,
                label="synthetic_alias_fixture",
            )

    def test_provider_witness_dimensions_are_never_summed_or_aliased(
        self,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        for path in (
            repo_root / "scripts" / "cuda_bench_driver.py",
            repo_root / "scripts" / "cuda_migration.py",
        ):
            _assert_no_provider_witness_counter_conflation(
                path.read_text(encoding="utf-8"),
                label=path.name,
            )
        assertion_source = inspect.getsource(driver.ProviderWitness.assert_no_real_calls)
        assert "loopback_kernel_calls" not in assertion_source

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

    def test_dynamic_pid_uses_validated_default_backend_map(self) -> None:
        maps_text = str(driver.cm.VULKAN_RELEASE_ROOT / "libggml-vulkan.so")
        provider = driver.SyntheticBackendMap(
            {}, default_maps_text=maps_text
        )

        assert provider.read_maps(123_456) == maps_text
        with pytest.raises(driver.BenchRefusal) as invalid_pid:
            provider.read_maps(True)  # type: ignore[arg-type]
        _assert_refusal(invalid_pid, "provider_uncertain")

    @pytest.mark.parametrize(
        "maps_text",
        ["no backend here", "libggml-vulkan.so libggml-cuda.so", b"bytes"],
    )
    def test_dynamic_pid_rejects_invalid_default_backend_map(
        self, maps_text: object
    ) -> None:
        provider = driver.SyntheticBackendMap(
            {}, default_maps_text=maps_text  # type: ignore[arg-type]
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            provider.read_maps(123_456)
        _assert_refusal(exc, "provider_uncertain")

    def test_ephemeral_port_lease_is_exact_and_fixed_ports_never_touch_socket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=registry,
        )
        socket_calls = 0

        def forbidden_socket(*_args: object, **_kwargs: object) -> object:
            nonlocal socket_calls
            socket_calls += 1
            raise AssertionError("fixed port attempted socket contact")

        monkeypatch.setattr(driver.socket, "socket", forbidden_socket)
        assert all(probe.is_free(port) is True for port in (8080, 8081, 8082, 18080))
        assert socket_calls == 0

        generation = registry.reserve_launch()
        lease = registry.activate_from_launcher(generation, 32_123)
        assert lease == driver.RehearsalPortLease(generation, 32_123)
        assert registry.current == lease

    def test_ephemeral_port_probe_retires_only_the_exact_current_lease(self) -> None:
        registry = driver.RehearsalPortRegistry()
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=registry,
        )
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = int(listener.getsockname()[1])
        generation = registry.reserve_launch()
        lease = registry.activate_from_launcher(generation, port)
        try:
            assert probe.is_free(port, lease=lease) is False
            assert registry.current == lease
        finally:
            listener.close()

        assert probe.is_free(port, lease=lease) is True
        assert registry.current is None
        assert probe.witness == driver.ProviderWitness(
            synthetic=True,
            real_calls=0,
            loopback_kernel_calls=2,
        )
        probe.witness.assert_no_real_calls()

    def test_ephemeral_port_finalizer_without_port_uses_exact_child_lease(
        self,
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=registry,
        )
        port = _free_loopback_port()
        lease = registry.activate_from_launcher(registry.reserve_launch(), port)
        proc = subprocess.Popen(
            [sys.executable, "-B", "-c", "pass"],
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pidfd = os.pidfd_open(proc.pid)
        pgid, start_time_ticks, exe_sha256 = _test_process_identity(proc.pid)
        assert proc.wait(timeout=3) == 0
        child = driver.OwnedChild(
            pid=proc.pid,
            pgid=pgid,
            pidfd=pidfd,
            start_time_ticks=start_time_ticks,
            pinned_path=str(Path(sys.executable).resolve()),
            pinned_sha256=exe_sha256,
            exe_sha256=exe_sha256,
            port=port,
            popen=proc,
            rehearsal_port_lease=lease,
        )

        result = driver.finalize(
            child,
            clock=driver.SystemClock(),
            port_probe=probe,
            port=None,
        )

        assert result.outcome == "clean"
        assert result.listener_free is True
        assert registry.current is None
        assert probe.witness.loopback_kernel_calls == 1

    def test_ephemeral_port_finalizer_mismatch_cannot_retire_current_lease(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=registry,
        )
        port = _free_loopback_port()
        lease = registry.activate_from_launcher(registry.reserve_launch(), port)
        proc = subprocess.Popen(
            [sys.executable, "-B", "-c", "pass"],
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pidfd = os.pidfd_open(proc.pid)
        pgid, start_time_ticks, exe_sha256 = _test_process_identity(proc.pid)
        assert proc.wait(timeout=3) == 0
        child = driver.OwnedChild(
            pid=proc.pid,
            pgid=pgid,
            pidfd=pidfd,
            start_time_ticks=start_time_ticks,
            pinned_path=str(Path(sys.executable).resolve()),
            pinned_sha256=exe_sha256,
            exe_sha256=exe_sha256,
            port=port,
            popen=proc,
            rehearsal_port_lease=lease,
        )
        monkeypatch.setattr(
            driver.socket,
            "socket",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("mismatched finalizer attempted socket contact")
            ),
        )

        result = driver.finalize(
            child,
            clock=driver.SystemClock(),
            port_probe=probe,
            port=port + 1,
        )

        assert result.outcome == "cleanup_incomplete"
        assert result.listener_free is None
        assert registry.current == lease
        assert probe.witness.loopback_kernel_calls == 0

    def test_ephemeral_port_same_number_stale_lease_refuses_before_socket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=registry,
        )
        port = _free_loopback_port()
        first = registry.activate_from_launcher(registry.reserve_launch(), port)
        assert probe.is_free(port, lease=first) is True
        second = registry.activate_from_launcher(registry.reserve_launch(), port)
        assert second.generation > first.generation

        def forbidden_socket(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("stale lease attempted socket contact")

        monkeypatch.setattr(driver.socket, "socket", forbidden_socket)
        with pytest.raises(driver.BenchRefusal) as stale:
            probe.is_free(port, lease=first)
        _assert_refusal(stale, "provider_uncertain")
        assert registry.current == second

    def test_ephemeral_port_value_equal_clone_is_not_the_exact_lease(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=registry,
        )
        port = _free_loopback_port()
        current = registry.activate_from_launcher(registry.reserve_launch(), port)
        clone = driver.RehearsalPortLease(current.generation, current.port)
        assert clone == current
        assert clone is not current
        monkeypatch.setattr(
            driver.socket,
            "socket",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("cloned lease attempted socket contact")
            ),
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            probe.is_free(port, lease=clone)

        _assert_refusal(exc, "provider_uncertain")
        assert registry.current is current

    def test_ephemeral_port_cross_registry_equal_lease_cannot_retire_current(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first_registry = driver.RehearsalPortRegistry()
        second_registry = driver.RehearsalPortRegistry()
        port = _free_loopback_port()
        stale = first_registry.activate_from_launcher(
            first_registry.reserve_launch(), port
        )
        current = second_registry.activate_from_launcher(
            second_registry.reserve_launch(), port
        )
        assert stale == current
        assert stale is not current
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=second_registry,
        )
        monkeypatch.setattr(
            driver.socket,
            "socket",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("cross-registry lease attempted socket contact")
            ),
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            probe.is_free(port, lease=stale)

        _assert_refusal(exc, "provider_uncertain")
        assert second_registry.current is current

    def test_ephemeral_port_unregistered_dynamic_refuses_before_socket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=driver.RehearsalPortRegistry(),
        )
        monkeypatch.setattr(
            driver.socket,
            "socket",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("unregistered port attempted socket contact")
            ),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            probe.is_free(32_123)
        _assert_refusal(exc, "provider_uncertain")

    def test_stock_rehearsal_real_port_probe_rejects_lease(self) -> None:
        lease = driver.RehearsalPortLease(1, 32_123)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.RealPortProbe().is_free(32_123, lease=lease)
        _assert_refusal(exc, "provider_uncertain")

    @pytest.mark.parametrize("free", [{8080, 8081, 8082, 18080, 32_123}])
    def test_ephemeral_port_fixed_configuration_is_exact(
        self, free: set[int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        probe = driver.SyntheticPortProbe(free, rehearsal_ports=registry)
        monkeypatch.setattr(
            driver.socket,
            "socket",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("invalid configuration attempted socket contact")
            ),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            probe.is_free(8080)
        _assert_refusal(exc, "provider_uncertain")

    def test_ephemeral_port_contested_reservation_refuses_before_spawn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        launcher = driver.RehearsalServerLauncher(
            _stub_pin(), rehearsal_ports=registry
        )
        registry.reserve_launch()
        spawned = False

        def forbidden_spawn(*_args: object, **_kwargs: object) -> object:
            nonlocal spawned
            spawned = True
            raise AssertionError("contested reservation reached spawn")

        monkeypatch.setattr(driver, "spawn_pinned", forbidden_spawn)
        with pytest.raises(driver.BenchRefusal) as exc:
            launcher.spawn(_stub_argv(), _stub_env())
        _assert_refusal(exc, "provider_uncertain")
        assert spawned is False

    def test_ephemeral_port_launcher_and_probe_registry_identity_is_sealed(
        self,
    ) -> None:
        components = _provider_components("rehearsal")
        components["server_launcher"] = driver.RehearsalServerLauncher(
            _stub_pin(), rehearsal_ports=driver.RehearsalPortRegistry()
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.rehearsal_tier(**components)
        _assert_refusal(exc, "tier_mismatch")

    def test_stock_rehearsal_production_callback_refuses_before_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            driver,
            "_sealed_executable_snapshot",
            lambda _pin: (_ for _ in ()).throw(
                AssertionError("production callback reached snapshot")
            ),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.spawn_pinned(
                [str(Path(sys.executable).resolve())],
                pin=_binary_pin(Path(sys.executable).resolve()),
                env=_stub_env(),
                _post_identity=lambda _port: None,
            )
        _assert_refusal(exc, "spawn_failure")

    @pytest.mark.parametrize("forbidden_port", [8080, 8081, 8082, 18080])
    def test_stock_rehearsal_fixed_port_announcement_refuses_before_real_probe(
        self, forbidden_port: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        read_fd, write_fd = os.pipe()
        os.write(
            write_fd,
            f"STUB_LISTENING port={forbidden_port}\n".encode("ascii"),
        )
        os.close(write_fd)
        stdout = os.fdopen(read_fd, "rb", buffering=0)

        class AnnouncingProcess:
            def __init__(self) -> None:
                self.stdout = stdout

            @staticmethod
            def poll() -> None:
                return None

        contacted = False

        def forbidden_probe(
            _probe: object,
            _port: int,
            *,
            lease: object = None,
        ) -> bool:
            del lease
            nonlocal contacted
            contacted = True
            raise AssertionError("fixed announcement reached real port probe")

        monkeypatch.setattr(driver.RealPortProbe, "is_free", forbidden_probe)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver._read_stub_announcement(AnnouncingProcess())  # type: ignore[arg-type]
            _assert_refusal(exc, "spawn_failure")
            assert contacted is False
        finally:
            stdout.close()

    def test_ephemeral_port_activation_failure_aborts_child_and_cancels_reservation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        launcher = driver.RehearsalServerLauncher(
            _stub_pin(), rehearsal_ports=registry
        )
        observed_ports: list[int] = []

        def fail_activation(
            _registry: object, _generation: int, port: int
        ) -> object:
            observed_ports.append(port)
            raise driver.BenchRefusal("provider_uncertain")

        monkeypatch.setattr(
            driver.RehearsalPortRegistry,
            "activate_from_launcher",
            fail_activation,
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            launcher.spawn(_stub_argv(), _stub_env())
        _assert_refusal(exc, "provider_uncertain")
        assert registry.current is None
        assert len(observed_ports) == 1
        assert _wait_for(
            lambda: driver.RealPortProbe().is_free(observed_ports[0]),
            timeout=3.0,
        )

    def test_ephemeral_port_stale_lease_finalizer_cannot_retire_reused_port(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = driver.RehearsalPortRegistry()
        probe = driver.SyntheticPortProbe(
            {8080, 8081, 8082, 18080},
            rehearsal_ports=registry,
        )
        port = _free_loopback_port()
        stale = registry.activate_from_launcher(registry.reserve_launch(), port)
        assert probe.is_free(port, lease=stale) is True
        current = registry.activate_from_launcher(registry.reserve_launch(), port)

        proc = subprocess.Popen(
            [sys.executable, "-B", "-c", "pass"],
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pidfd = os.pidfd_open(proc.pid)
        pgid, start_time_ticks, exe_sha256 = _test_process_identity(proc.pid)
        assert proc.wait(timeout=3) == 0
        child = driver.OwnedChild(
            pid=proc.pid,
            pgid=pgid,
            pidfd=pidfd,
            start_time_ticks=start_time_ticks,
            pinned_path=str(Path(sys.executable).resolve()),
            pinned_sha256=exe_sha256,
            exe_sha256=exe_sha256,
            port=port,
            popen=proc,
            rehearsal_port_lease=stale,
        )
        monkeypatch.setattr(
            driver.socket,
            "socket",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("stale finalizer attempted socket contact")
            ),
        )

        result = driver.finalize(
            child,
            clock=driver.SystemClock(),
            port_probe=probe,
            port=port,
        )

        assert result.outcome == "cleanup_incomplete"
        assert result.listener_free is None
        assert registry.current == current

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


def _parent_completion_evidence(
    packet: driver.cm.PhasePacket,
) -> driver.ParentCompletionEvidence:
    policy = driver.ProductionArtifactPolicy()
    packet_ref = (
        "windows/window-1/vulkan-baseline/attempt-001/"
        "packets/phase-packet.json"
    )
    packet_bytes = policy.encode(
        "packet",
        {
            "binding_sha256": packet.binding_sha256,
            **driver._phase_packet_fields(packet),
        },
    )
    packet_doc = driver.cm.PersistedDoc(packet_bytes)
    admission_ref = "command-vulkan-baseline-attempt-001-admission.json"
    admission_bytes = policy.encode(
        "command_admission",
        {
            "command": "vulkan-baseline",
            "ordinal": 1,
            "window_id": packet.window_id,
            "status": "admitted",
            "timestamp": "2026-07-14T08:00:00Z",
        },
    )
    admission = driver.cm.CommandAdmissionPreimage(
        admission_ref,
        admission_bytes,
    )
    completion = driver.cm.CommandCompletionDoc(
        command="vulkan-baseline",
        ordinal=1,
        window_id=packet.window_id,
        admission_ref=admission.selected_ref,
        admission_sha256=admission.file_sha256,
        artifact_ref=packet_ref,
        artifact_sha256=packet_doc.file_sha256,
        artifact_schema=driver.cm.PHASE_PACKET_SCHEMA,
        status="completed",
        timestamp="2026-07-14T10:59:59Z",
    )
    completion_doc = driver.cm.PersistedDoc(
        policy.encode(
            "command_completion",
            {
                "binding_sha256": completion.binding_sha256,
                "command": completion.command,
                "ordinal": completion.ordinal,
                "window_id": completion.window_id,
                "admission_ref": completion.admission_ref,
                "admission_sha256": completion.admission_sha256,
                "artifact_ref": completion.artifact_ref,
                "artifact_sha256": completion.artifact_sha256,
                "artifact_schema": completion.artifact_schema,
                "status": completion.status,
                "timestamp": completion.timestamp,
            },
        )
    )
    return driver.ParentCompletionEvidence(
        packet=packet,
        packet_ref=packet_ref,
        packet_doc=packet_doc,
        admission=admission,
        completion_doc=completion_doc,
    )


def _completion_doc_with_timestamp(
    evidence: driver.ParentCompletionEvidence,
    timestamp: str,
) -> driver.cm.PersistedDoc:
    completion = evidence.completion_doc.obj
    assert type(completion) is driver.cm.CommandCompletionDoc
    changed = replace(completion, timestamp=timestamp)
    return driver.cm.PersistedDoc(
        driver.ProductionArtifactPolicy().encode(
            "command_completion",
            {
                "binding_sha256": changed.binding_sha256,
                "command": changed.command,
                "ordinal": changed.ordinal,
                "window_id": changed.window_id,
                "admission_ref": changed.admission_ref,
                "admission_sha256": changed.admission_sha256,
                "artifact_ref": changed.artifact_ref,
                "artifact_sha256": changed.artifact_sha256,
                "artifact_schema": changed.artifact_schema,
                "status": changed.status,
                "timestamp": changed.timestamp,
            },
        )
    )


class TestServerLauncherFinalizer:
    @pytest.fixture(autouse=True)
    def _owned_process_registry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Iterator[None]:
        """Retain independent pidfds so a failed assertion cannot leak a child."""

        leases: list[_TestProcessLease] = []
        real_popen = subprocess.Popen
        real_guarded_popen = driver._guarded_popen
        real_pidfd_open = os.pidfd_open
        real_pidfd_signal = signal.pidfd_send_signal

        def register_pid(
            pid: int,
            *,
            popen: subprocess.Popen[bytes] | subprocess.Popen[str] | None,
        ) -> _TestProcessLease:
            if popen is not None:
                existing = next(
                    (lease for lease in leases if lease.popen is popen), None
                )
                if existing is not None:
                    return existing
            try:
                pidfd = real_pidfd_open(pid)
            except BaseException:
                if popen is not None and popen.poll() is None:
                    popen.kill()
                    popen.wait(timeout=2)
                raise
            try:
                pgid = os.getpgid(pid)
            except OSError:
                pgid = None
            lease = _TestProcessLease(
                pid=pid,
                pidfd=pidfd,
                popen=popen,
                isolated_pgid=pgid if pgid == pid else None,
                product_pidfds=set(),
                ports=set(),
            )
            leases.append(lease)
            return lease

        def tracked_popen(*args: object, **kwargs: object) -> subprocess.Popen[object]:
            proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
            register_pid(proc.pid, popen=proc)  # type: ignore[arg-type]
            return proc  # type: ignore[return-value]

        def tracked_guarded_popen(
            *args: object, **kwargs: object
        ) -> tuple[object, ...]:
            result = real_guarded_popen(*args, **kwargs)  # type: ignore[arg-type]
            register_pid(result[0].pid, popen=result[0])
            return result  # type: ignore[return-value]

        self._test_process_leases = leases
        self._register_test_pid = lambda pid: register_pid(pid, popen=None)
        self._test_pidfd_signal = real_pidfd_signal
        self._test_popen = tracked_popen
        monkeypatch.setattr(driver, "_guarded_popen", tracked_guarded_popen)
        cleanup_errors: list[str] = []
        try:
            yield
        finally:
            for lease in reversed(leases):
                try:
                    real_pidfd_signal(lease.pidfd, signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    pass
            for lease in reversed(leases):
                proc = lease.popen
                if proc is not None:
                    try:
                        proc.wait(timeout=2)
                    except (ChildProcessError, subprocess.TimeoutExpired):
                        cleanup_errors.append(f"unreaped:{lease.pid}")
                    for stream_name in ("stdin", "stdout", "stderr"):
                        stream = getattr(proc, stream_name, None)
                        if stream is not None and not stream.closed:
                            stream.close()
            for lease in reversed(leases):
                poller = select.poll()
                try:
                    poller.register(lease.pidfd, select.POLLIN | select.POLLHUP)
                    if not poller.poll(2000):
                        cleanup_errors.append(f"pidfd_alive:{lease.pid}")
                except OSError:
                    pass
                for record in lease.product_pidfds:
                    self._close_product_pidfd_if_owned(*record)
                try:
                    os.close(lease.pidfd)
                except OSError:
                    pass
            for pgid in {
                lease.isolated_pgid
                for lease in leases
                if lease.isolated_pgid is not None
            }:
                try:
                    if not _wait_for(lambda pgid=pgid: not driver._pgid_members(pgid)):
                        cleanup_errors.append(f"pgid_alive:{pgid}")
                except driver.BenchRefusal:
                    cleanup_errors.append(f"pgid_unproven:{pgid}")
            for port in {port for lease in leases for port in lease.ports}:
                if not _wait_for(lambda port=port: driver.RealPortProbe().is_free(port)):
                    cleanup_errors.append(f"listener_alive:{port}")
            assert not cleanup_errors, cleanup_errors

    def _lease_for_popen(self, popen: subprocess.Popen[object]) -> _TestProcessLease:
        return next(
            lease for lease in self._test_process_leases if lease.popen is popen
        )

    def _register_owned_fd(
        self, popen: subprocess.Popen[object], fd: int
    ) -> None:
        descriptor = os.fstat(fd)
        self._lease_for_popen(popen).product_pidfds.add(
            (fd, popen.pid, descriptor.st_dev, descriptor.st_ino)
        )

    def _close_product_pidfd_if_owned(
        self,
        fd: int,
        expected_pid: int,
        expected_device: int,
        expected_inode: int,
    ) -> bool:
        try:
            descriptor = os.fstat(fd)
        except OSError:
            return False
        if (
            descriptor.st_dev != expected_device
            or descriptor.st_ino != expected_inode
        ):
            return False
        state, bound_pid = driver._pidfd_bound_pid(fd)
        if state == "bound" and bound_pid != expected_pid:
            return False
        if state not in {"bound", "gone"}:
            return False
        try:
            os.close(fd)
        except OSError:
            return False
        return True

    def _register_child_evidence(self, child: object) -> object:
        popen = child.popen  # type: ignore[attr-defined]
        lease = self._lease_for_popen(popen)
        descriptor = os.fstat(child.pidfd)  # type: ignore[attr-defined]
        lease.product_pidfds.add(
            (
                child.pidfd,  # type: ignore[attr-defined]
                child.pid,  # type: ignore[attr-defined]
                descriptor.st_dev,
                descriptor.st_ino,
            )
        )
        port = child.port  # type: ignore[attr-defined]
        if type(port) is int:
            lease.ports.add(port)
        return child

    def _launcher(self) -> object:
        return driver.RehearsalServerLauncher(_stub_pin())

    def _spawn_stub(self) -> object:
        child = self._launcher().spawn(  # type: ignore[attr-defined]
            _stub_argv(), _stub_env()
        )
        return self._register_child_evidence(child)

    def _test_cleanup(self, child: object) -> None:
        popen = child.popen  # type: ignore[attr-defined]
        if popen.poll() is None:
            popen.terminate()
            try:
                popen.wait(timeout=2)
            except subprocess.TimeoutExpired:
                popen.kill()
                popen.wait(timeout=2)
        for stream_name in ("stdin", "stdout", "stderr"):
            stream = getattr(popen, stream_name, None)
            if stream is not None and not stream.closed:
                stream.close()
        pidfd = child.pidfd  # type: ignore[attr-defined]
        lease = self._lease_for_popen(popen)
        record = next(
            (record for record in lease.product_pidfds if record[0] == pidfd),
            None,
        )
        if record is not None:
            self._close_product_pidfd_if_owned(*record)

    def _spawn_stubborn_binary(self, tmp_path: Path) -> object:
        ready = tmp_path / "sigterm-handler-ready"
        executable = Path(sys.executable)
        child = driver.RealServerLauncher(_binary_pin(executable)).spawn(
            [
                sys.executable,
                "-B",
                "-c",
                (
                    "import pathlib,signal,sys,time; "
                    "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                    "pathlib.Path(sys.argv[1]).touch(); time.sleep(30)"
                ),
                str(ready),
                "--port",
                str(driver.BENCH_PORT),
            ],
            _stub_env(),
        )
        self._register_child_evidence(child)
        try:
            assert _wait_for(ready.exists)
        except BaseException:
            self._test_cleanup(child)
            raise
        return child

    def test_rehearsal_launcher_refuses_noncanonical_python_target(
        self, tmp_path: Path
    ) -> None:
        impostor = tmp_path / "impostor.py"
        sentinel = tmp_path / "impostor-ran"
        impostor.write_text(
            "from pathlib import Path\n"
            f"Path({str(sentinel)!r}).touch()\n"
            "print('STUB_LISTENING port=12345', flush=True)\n",
            encoding="utf-8",
        )
        pin = _python_file_pin(
            impostor,
            hashlib.sha256(impostor.read_bytes()).hexdigest(),
        )
        with pytest.raises(ValueError, match="spawn_pin_invalid"):
            driver.RehearsalServerLauncher(pin)  # type: ignore[arg-type]
        assert not sentinel.exists()

    @pytest.mark.parametrize(
        ("pin", "argv"),
        [
            (
                lambda: _stub_pin(),
                lambda: [
                    sys.executable,
                    "-B",
                    "-I",
                    str(STUB_PATH.with_name("not-the-pinned-stub.py")),
                ],
            ),
            (
                lambda: _stub_pin(digest="0" * 64),
                lambda: _stub_argv(),
            ),
            (
                lambda: _binary_pin(Path(sys.executable)),
                lambda: ["/bin/false"],
            ),
        ],
    )
    def test_spawn_pinned_refuses_wrong_prefix_hash_or_binary(
        self,
        monkeypatch: pytest.MonkeyPatch,
        pin: object,
        argv: object,
    ) -> None:
        monkeypatch.setattr(
            driver.subprocess,
            "Popen",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("refusal must precede spawn")
            ),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.spawn_pinned(argv(), pin=pin(), env=_stub_env())  # type: ignore[operator]
        _assert_refusal(exc, "spawn_failure")

    @pytest.mark.parametrize("mutation", ["replace_inode", "overwrite_in_place"])
    def test_python_file_executes_sealed_verified_bytes_after_path_mutation(
        self,
        mutation: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "pinned-target.py"
        replacement = tmp_path / "replacement.py"
        original_ran = tmp_path / "original-ran"
        impostor_ran = tmp_path / "impostor-ran"
        port = _free_loopback_port()
        _write_listener_script(target, original_ran, port)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        _write_listener_script(replacement, impostor_ran, port)
        real_guarded_popen = driver._guarded_popen
        spawned: list[object] = []

        def swap_path_after_verified_open(
            *args: object, **kwargs: object
        ) -> object:
            if mutation == "replace_inode":
                os.replace(replacement, target)
            else:
                target.write_bytes(replacement.read_bytes())
            return real_guarded_popen(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(driver, "_guarded_popen", swap_path_after_verified_open)
        try:
            child = driver.spawn_pinned(
                [sys.executable, "-B", "-I", str(target)],
                pin=_python_file_pin(target, digest),  # type: ignore[arg-type]
                env=_stub_env(),
            )
            self._register_child_evidence(child)
            spawned.append(child)

            assert original_ran.exists()
            assert not impostor_ran.exists()
            assert child.pinned_path == str(target)  # type: ignore[attr-defined]
            assert child.pinned_sha256 == digest  # type: ignore[attr-defined]
            cmdline = Path(f"/proc/{child.pid}/cmdline").read_bytes().split(b"\0")  # type: ignore[attr-defined]
            fd_argv = [
                value
                for value in cmdline
                if value.startswith(b"/proc/self/fd/")
            ]
            assert len(fd_argv) == 1
            executed_fd = int(fd_argv[0].rsplit(b"/", 1)[1])
            assert not Path(f"/proc/{child.pid}/fd/{executed_fd}").exists()  # type: ignore[attr-defined]
            assert os.fsencode(target) not in cmdline
        finally:
            for child in spawned:
                self._test_cleanup(child)
            assert _wait_for(lambda: driver.RealPortProbe().is_free(port))

    def test_snapshot_is_fully_sealed_before_the_authoritative_hash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "entry.py"
        target.write_text("print('sealed')\n", encoding="utf-8")
        pin = _python_file_pin(target, hashlib.sha256(target.read_bytes()).hexdigest())
        events: list[str] = []
        real_fcntl = fcntl.fcntl
        real_hash_fd = driver._hash_fd

        def recording_fcntl(fd: int, command: int, argument: int = 0) -> int:
            if command == fcntl.F_ADD_SEALS:
                events.append("seal")
            return real_fcntl(fd, command, argument)

        def recording_hash(fd: int) -> str:
            events.append("hash")
            return real_hash_fd(fd)

        monkeypatch.setattr(driver.fcntl, "fcntl", recording_fcntl)
        monkeypatch.setattr(driver, "_hash_fd", recording_hash)
        snapshot = driver._sealed_executable_snapshot(pin)
        try:
            required = (
                fcntl.F_SEAL_WRITE
                | fcntl.F_SEAL_GROW
                | fcntl.F_SEAL_SHRINK
                | fcntl.F_SEAL_SEAL
            )
            assert fcntl.fcntl(snapshot.fd, fcntl.F_GET_SEALS) & required == required
            assert events == ["seal", "hash"]
            with pytest.raises(OSError):
                os.write(snapshot.fd, b"x")
            with pytest.raises(OSError):
                os.ftruncate(snapshot.fd, 0)
            with pytest.raises(OSError):
                fcntl.fcntl(snapshot.fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_FUTURE_WRITE)
        finally:
            os.close(snapshot.fd)

    def test_memfd_creation_requests_host_executability_and_fails_typed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "entry.py"
        target.write_text("print('sealed')\n", encoding="utf-8")
        pin = _python_file_pin(target, hashlib.sha256(target.read_bytes()).hexdigest())
        real_memfd_create = os.memfd_create
        observed_flags: list[int] = []

        def recording_create(name: str, flags: int = 0) -> int:
            observed_flags.append(flags)
            return real_memfd_create(name, flags)

        monkeypatch.setattr(driver.os, "memfd_create", recording_create)
        snapshot = driver._sealed_executable_snapshot(pin)
        os.close(snapshot.fd)
        assert observed_flags
        assert observed_flags[0] & driver.MFD_EXEC

        monkeypatch.setattr(
            driver.os,
            "memfd_create",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                PermissionError(errno.EACCES, "memfd execution forbidden")
            ),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.spawn_pinned(
                [sys.executable, "-B", "-I", str(target)],
                pin=pin,
                env=_stub_env(),
            )
        _assert_refusal(exc, "spawn_failure")

    def test_binary_entry_executes_from_sealed_memfd_on_this_host(self) -> None:
        executable = Path(sys.executable).resolve()
        child = driver.spawn_pinned(
            [str(executable), "-B", "-c", "import time; time.sleep(30)"],
            pin=_binary_pin(executable),  # type: ignore[arg-type]
            env=_stub_env(),
        )
        self._register_child_evidence(child)
        try:
            assert child.pinned_path == str(executable)
            assert child.pinned_sha256 == hashlib.sha256(executable.read_bytes()).hexdigest()
            assert os.readlink(f"/proc/{child.pid}/exe").startswith("/memfd:cuda-bench-entry")
        finally:
            self._test_cleanup(child)

    def test_closed_verified_fd_refuses_without_executing_or_listening(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "pinned-target.py"
        sentinel = tmp_path / "target-ran"
        port = _free_loopback_port()
        _write_listener_script(target, sentinel, port)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        real_guarded_popen = driver._guarded_popen
        spawned: list[object] = []

        def close_verified_fd(*args: object, **kwargs: object) -> object:
            pinned_fd = kwargs.get("pinned_fd")
            if type(pinned_fd) is int:
                os.close(pinned_fd)
            return real_guarded_popen(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(driver, "_guarded_popen", close_verified_fd)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                child = driver.spawn_pinned(
                    [sys.executable, "-B", "-I", str(target)],
                    pin=_python_file_pin(target, digest),  # type: ignore[arg-type]
                    env=_stub_env(),
                )
                self._register_child_evidence(child)
                spawned.append(child)
            _assert_refusal(exc, "spawn_failure")
            assert not sentinel.exists()
            assert driver.RealPortProbe().is_free(port)
        finally:
            for child in spawned:
                self._test_cleanup(child)
            assert _wait_for(lambda: driver.RealPortProbe().is_free(port))

    def test_pidfd_open_failure_closes_gate_without_executing_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sentinel = tmp_path / "target-executed"
        shell = Path("/bin/sh")
        captured: list[subprocess.Popen[bytes]] = []
        real_popen = self._test_popen

        def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
            captured.append(proc)
            return proc

        monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
        monkeypatch.setattr(
            driver.os,
            "pidfd_open",
            lambda _pid: (_ for _ in ()).throw(OSError(errno.EMFILE, "fd limit")),
        )

        argv = [str(shell), "-c", f"touch {sentinel}"]
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.spawn_pinned(argv, pin=_binary_pin(shell), env=_stub_env())
        _assert_refusal(exc, "spawn_failure")

        assert len(captured) == 1
        guard = captured[0]
        assert guard.wait(timeout=2) == 0
        assert not sentinel.exists()
        assert not Path(f"/proc/{guard.pid}").exists()

    def test_pidfd_open_decoy_is_rejected_before_target_execution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sentinel = tmp_path / "target-executed"
        shell = Path("/bin/sh")
        decoy = self._test_popen(
            [sys.executable, "-B", "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        captured: list[subprocess.Popen[bytes]] = []
        real_popen = self._test_popen
        real_pidfd_open = os.pidfd_open

        def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
            captured.append(proc)
            return proc

        monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
        monkeypatch.setattr(
            driver.os,
            "pidfd_open",
            lambda _pid: real_pidfd_open(decoy.pid),
        )
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver.spawn_pinned(
                    [str(shell), "-c", f"touch {sentinel}"],
                    pin=_binary_pin(shell),  # type: ignore[arg-type]
                    env=_stub_env(),
                )
            _assert_refusal(exc, "spawn_failure")
            assert len(captured) == 1
            assert captured[0].wait(timeout=2) == 0
            assert decoy.poll() is None
            assert not sentinel.exists()
        finally:
            if decoy.poll() is None:
                decoy.kill()
                decoy.wait(timeout=2)

    def test_second_pipe_failure_closes_first_pipe_pair(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_pipe2 = os.pipe2
        opened: list[int] = []
        calls = 0

        def fail_second_pipe(flags: int) -> tuple[int, int]:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError(errno.EMFILE, "fd limit")
            pair = real_pipe2(flags)
            opened.extend(pair)
            return pair

        monkeypatch.setattr(driver.os, "pipe2", fail_second_pipe)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver.spawn_pinned(
                    ["/bin/true"],
                    pin=_binary_pin(Path("/bin/true")),  # type: ignore[arg-type]
                    env=_stub_env(),
                )
            _assert_refusal(exc, "spawn_failure")
            assert len(opened) == 2
            for fd in opened:
                with pytest.raises(OSError):
                    os.fstat(fd)
        finally:
            for fd in opened:
                try:
                    os.close(fd)
                except OSError:
                    pass

    @pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
    def test_interrupt_between_guard_spawn_and_pidfd_keeps_guard_inert(
        self,
        signum: int,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sentinel = tmp_path / "target-executed"
        shell = Path("/bin/sh")
        captured: list[subprocess.Popen[bytes]] = []
        real_popen = self._test_popen
        real_pidfd_open = os.pidfd_open
        old_handler = signal.getsignal(signum)

        def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
            captured.append(proc)
            return proc

        def interrupt_before_pidfd(pid: int) -> int:
            signal.raise_signal(signum)
            return real_pidfd_open(pid)

        signal.signal(signum, signal.default_int_handler)
        monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
        monkeypatch.setattr(driver.os, "pidfd_open", interrupt_before_pidfd)
        try:
            with pytest.raises(KeyboardInterrupt):
                driver.spawn_pinned(
                    [str(shell), "-c", f"touch {sentinel}"],
                    pin=_binary_pin(shell),  # type: ignore[arg-type]
                    env=_stub_env(),
                )
            assert len(captured) == 1
            assert _wait_for(lambda: captured[0].poll() is not None, timeout=0.25)
            assert captured[0].returncode == 0
            assert not sentinel.exists()
        finally:
            signal.signal(signum, old_handler)
            for guard in captured:
                if guard.poll() is None:
                    guard.kill()
                    guard.wait(timeout=2)
                for stream_name in ("stdin", "stdout", "stderr"):
                    stream = getattr(guard, stream_name, None)
                    if stream is not None and not stream.closed:
                        stream.close()

    @pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
    def test_interrupt_after_guard_helper_return_is_still_cleanup_owned(
        self,
        signum: int,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sentinel = tmp_path / "target-executed"
        shell = Path("/bin/sh")
        captured: list[subprocess.Popen[bytes]] = []
        real_popen = self._test_popen
        real_guarded_popen = driver._guarded_popen
        old_handler = signal.getsignal(signum)

        def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
            captured.append(proc)
            return proc

        def interrupt_after_return(*args: object, **kwargs: object) -> object:
            result = real_guarded_popen(*args, **kwargs)  # type: ignore[arg-type]
            signal.raise_signal(signum)
            return result

        signal.signal(signum, signal.default_int_handler)
        monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
        monkeypatch.setattr(driver, "_guarded_popen", interrupt_after_return)
        try:
            with pytest.raises(KeyboardInterrupt):
                driver.spawn_pinned(
                    [str(shell), "-c", f"touch {sentinel}"],
                    pin=_binary_pin(shell),  # type: ignore[arg-type]
                    env=_stub_env(),
                )
            assert len(captured) == 1
            assert _wait_for(lambda: captured[0].poll() is not None, timeout=0.25)
            assert captured[0].returncode == 0
            assert not sentinel.exists()
        finally:
            signal.signal(signum, old_handler)
            for guard in captured:
                if guard.poll() is None:
                    guard.kill()
                    guard.wait(timeout=2)
                for stream_name in ("stdin", "stdout", "stderr"):
                    stream = getattr(guard, stream_name, None)
                    if stream is not None and not stream.closed:
                        stream.close()

    def test_post_pidfd_identity_failure_uses_only_pidfd_and_leaves_no_listener(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[subprocess.Popen[bytes]] = []
        announced: list[int] = []
        sent: list[int] = []
        real_popen = self._test_popen
        real_announcement = driver._read_stub_announcement
        real_pidfd_signal = signal.pidfd_send_signal

        def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
            captured.append(proc)
            return proc

        def recording_announcement(proc: subprocess.Popen[bytes]) -> int:
            port = real_announcement(proc)
            announced.append(port)
            return port

        def recording_signal(
            pidfd: int,
            signum: int,
            siginfo: object = None,
            flags: int = 0,
        ) -> None:
            sent.append(signum)
            real_pidfd_signal(pidfd, signum, siginfo, flags)

        monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
        monkeypatch.setattr(driver, "_read_stub_announcement", recording_announcement)
        monkeypatch.setattr(
            driver,
            "_capture_target_identity",
            lambda _pid: (_ for _ in ()).throw(OSError("identity unavailable")),
        )
        monkeypatch.setattr(driver.signal, "pidfd_send_signal", recording_signal)

        with pytest.raises(driver.BenchRefusal) as exc:
            self._launcher().spawn(_stub_argv(), _stub_env())  # type: ignore[attr-defined]
        _assert_refusal(exc, "spawn_failure")

        assert announced and len(captured) == 1
        assert sent == [signal.SIGKILL]
        assert captured[0].wait(timeout=2) == -signal.SIGKILL
        assert _wait_for(lambda: driver.RealPortProbe().is_free(announced[0]))
        assert not Path(f"/proc/{captured[0].pid}").exists()

    def test_bootstrap_signal_failure_reports_cleanup_incomplete_not_spawn_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[subprocess.Popen[bytes]] = []
        announced: list[int] = []
        real_popen = self._test_popen
        real_announcement = driver._read_stub_announcement

        def recording_popen(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
            proc = real_popen(*args, **kwargs)  # type: ignore[arg-type]
            captured.append(proc)
            return proc

        def recording_announcement(proc: subprocess.Popen[bytes]) -> int:
            port = real_announcement(proc)
            announced.append(port)
            return port

        monkeypatch.setattr(driver.subprocess, "Popen", recording_popen)
        monkeypatch.setattr(driver, "_read_stub_announcement", recording_announcement)
        monkeypatch.setattr(
            driver,
            "_capture_target_identity",
            lambda _pid: (_ for _ in ()).throw(OSError("identity unavailable")),
        )
        monkeypatch.setattr(
            driver.signal,
            "pidfd_send_signal",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("signal failed")),
        )
        monkeypatch.setattr(driver, "KILL_WAIT_S", 0.05)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                self._launcher().spawn(_stub_argv(), _stub_env())  # type: ignore[attr-defined]
            _assert_refusal(exc, "cleanup_incomplete")
            assert len(captured) == 1 and announced
            assert captured[0].poll() is None
            assert _health(announced[0])
        finally:
            for proc in captured:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2)
                for stream_name in ("stdin", "stdout", "stderr"):
                    stream = getattr(proc, stream_name, None)
                    if stream is not None and not stream.closed:
                        stream.close()
            if announced:
                assert _wait_for(lambda: driver.RealPortProbe().is_free(announced[0]))

    def test_identity_capture_follows_exec_proof_and_uses_target_executable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        order: list[str] = []
        real_announcement = driver._read_stub_announcement
        real_capture = driver._capture_target_identity

        def announcement(proc: subprocess.Popen[bytes]) -> int:
            port = real_announcement(proc)
            order.append("target-announced")
            return port

        def capture(pid: int) -> tuple[int, int, str]:
            order.append("identity-captured")
            return real_capture(pid)

        monkeypatch.setattr(driver, "_read_stub_announcement", announcement)
        monkeypatch.setattr(driver, "_capture_target_identity", capture)
        child = self._spawn_stub()
        try:
            assert order == ["target-announced", "identity-captured"]
            assert child.pinned_sha256 == STUB_SHA256
            assert child.exe_sha256 == hashlib.sha256(
                Path(sys.executable).resolve().read_bytes()
            ).hexdigest()
        finally:
            self._test_cleanup(child)

    @pytest.mark.parametrize(
        "payload",
        [
            b"not-the-announcement\n",
            b"STUB_LISTENING port=" + b"9" * 200 + b"\n",
        ],
    )
    def test_stub_announcement_is_exact_and_bounded(self, payload: bytes) -> None:
        proc = self._test_popen(
            [sys.executable, "-B", "-c", f"import os; os.write(1, {payload!r})"],
            stdout=subprocess.PIPE,
        )
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver._read_stub_announcement(proc)
            _assert_refusal(exc, "spawn_failure")
        finally:
            proc.wait(timeout=2)
            assert proc.stdout is not None
            proc.stdout.close()

    def test_stub_announcement_timeout_is_bounded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proc = self._test_popen(
            [sys.executable, "-B", "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
        )
        monkeypatch.setattr(driver, "READINESS_TIMEOUT_S", 0.05)
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                driver._read_stub_announcement(proc)
            _assert_refusal(exc, "spawn_failure")
        finally:
            proc.kill()
            proc.wait(timeout=2)
            assert proc.stdout is not None
            proc.stdout.close()

    def test_hardened_absolute_stub_ignores_hostile_cwd_and_pythonpath(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decoy_root = tmp_path / "decoy"
        decoy_module = decoy_root / "scripts" / "cuda_bench_stub.py"
        decoy_module.parent.mkdir(parents=True)
        sentinel = tmp_path / "decoy-ran"
        decoy_module.write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n")
        monkeypatch.chdir(decoy_root)

        child = self._launcher().spawn(  # type: ignore[attr-defined]
            _stub_argv(), _stub_env(PYTHONPATH=str(decoy_root))
        )
        self._register_child_evidence(child)
        try:
            assert child.port != driver.BENCH_PORT
            assert _health(child.port)
            assert not sentinel.exists()
        finally:
            try:
                result = driver.finalize(
                    child,
                    clock=driver.SystemClock(),
                    port_probe=driver.RealPortProbe(),
                    port=child.port,
                )
                assert result.outcome == "clean"
            finally:
                self._test_cleanup(child)

    def test_same_pid_pidfd_survives_exec_and_terminates_ready_stub(self) -> None:
        child = self._spawn_stub()
        try:
            pidfd_poll = select.poll()
            pidfd_poll.register(
                child.pidfd, select.POLLIN | select.POLLHUP | select.POLLERR
            )
            assert child.pid == child.pgid
            assert driver._pgid_members(child.pgid) == [child.pid]
            assert pidfd_poll.poll(0) == []
            assert _health(child.port)

            result = driver.finalize(
                child,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=child.port,
            )

            assert result.outcome == "clean"
            assert result.signals_sent == ("SIGTERM",)
            assert result.quadruple_reproofs == 1
            assert result.surviving_pgid_members == ()
            assert result.listener_free is True
            assert _wait_for(lambda: not _health(child.port))
        finally:
            self._test_cleanup(child)

    def test_clock_failure_cannot_prevent_process_and_listener_cleanup(self) -> None:
        class BrokenClock:
            tier = "rehearsal"

            def now_utc(self) -> str:
                raise OSError("clock unavailable")

            def monotonic(self) -> float:
                return time.monotonic()

        child = self._spawn_stub()
        try:
            result = driver.finalize(
                child,
                clock=BrokenClock(),  # type: ignore[arg-type]
                port_probe=driver.RealPortProbe(),
                port=child.port,
            )
            assert result.outcome == "cleanup_incomplete"
            assert result.signals_sent == ("SIGTERM",)
            assert result.surviving_pgid_members == ()
            assert result.listener_free is True
            assert child.popen.poll() is not None
            assert _wait_for(lambda: not _health(child.port))
        finally:
            self._test_cleanup(child)

    def test_test_cleanup_never_closes_reused_child_pidfd_number(self) -> None:
        child = self._spawn_stub()
        original_record = next(
            record
            for record in self._lease_for_popen(child.popen).product_pidfds
            if record[0] == child.pidfd
        )
        result = driver.finalize(
            child,
            clock=driver.SystemClock(),
            port_probe=driver.RealPortProbe(),
            port=child.port,
        )
        assert result.outcome == "clean"

        sentinel = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
        if sentinel != child.pidfd:
            os.dup2(sentinel, child.pidfd)
            os.close(sentinel)
            sentinel = child.pidfd
        try:
            assert self._close_product_pidfd_if_owned(*original_record) is False
            os.fstat(sentinel)
        finally:
            os.close(sentinel)

    def test_test_cleanup_never_closes_reused_gone_pidfd(self) -> None:
        child = self._spawn_stub()
        original_record = next(
            record
            for record in self._lease_for_popen(child.popen).product_pidfds
            if record[0] == child.pidfd
        )
        result = driver.finalize(
            child,
            clock=driver.SystemClock(),
            port_probe=driver.RealPortProbe(),
            port=child.port,
        )
        assert result.outcome == "clean"

        unrelated = self._test_popen([sys.executable, "-B", "-c", "pass"])
        unrelated_pidfd = os.pidfd_open(unrelated.pid)
        os.dup2(unrelated_pidfd, child.pidfd)
        if unrelated_pidfd != child.pidfd:
            os.close(unrelated_pidfd)
        assert unrelated.wait(timeout=2) == 0
        try:
            assert driver._pidfd_bound_pid(child.pidfd) == ("gone", None)
            assert self._close_product_pidfd_if_owned(*original_record) is False
            os.fstat(child.pidfd)
        finally:
            try:
                os.close(child.pidfd)
            except OSError:
                pass

    def test_stubborn_child_is_reproved_before_pidfd_sigkill(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        child = self._spawn_stubborn_binary(tmp_path)
        monkeypatch.setattr(driver, "SIGTERM_GRACE_S", 0.05)
        try:
            result = driver.finalize(
                child,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=None,
            )

            assert result.outcome == "clean"
            assert result.signals_sent == ("SIGTERM", "SIGKILL")
            assert result.quadruple_reproofs == 2
            assert result.surviving_pgid_members == ()
            assert child.popen.returncode == -signal.SIGKILL
        finally:
            self._test_cleanup(child)

    def test_identity_drift_after_sigterm_withholds_pidfd_sigkill(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        child = self._spawn_stubborn_binary(tmp_path)
        real_identity_proof = driver._identity_proof
        reproof_calls = 0

        def identity_drifts_after_term(observed: object) -> str:
            nonlocal reproof_calls
            reproof_calls += 1
            if reproof_calls == 1:
                return real_identity_proof(observed)  # type: ignore[arg-type]
            return "mismatch"

        monkeypatch.setattr(driver, "SIGTERM_GRACE_S", 0.05)
        monkeypatch.setattr(driver, "_identity_proof", identity_drifts_after_term)
        try:
            result = driver.finalize(
                child,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=None,
            )

            assert result.outcome == "pid_reuse_detected"
            assert result.signals_sent == ("SIGTERM",)
            assert result.quadruple_reproofs == 2
            assert result.surviving_pgid_members == (child.pid,)
            assert child.popen.poll() is None
        finally:
            if child.popen.poll() is None:
                child.popen.kill()
                child.popen.wait(timeout=2)
            self._test_cleanup(child)

    def test_pidfd_swap_after_sigterm_cannot_redirect_sigkill(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        child = self._spawn_stubborn_binary(tmp_path)
        decoy = self._test_popen(
            [sys.executable, "-B", "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        decoy_pidfd = os.pidfd_open(decoy.pid)
        self._register_owned_fd(decoy, decoy_pidfd)
        real_signal = signal.pidfd_send_signal

        def swap_after_term(
            pidfd: int,
            signum: int,
            siginfo: object = None,
            flags: int = 0,
        ) -> None:
            real_signal(pidfd, signum, siginfo, flags)
            if signum == signal.SIGTERM:
                os.dup2(decoy_pidfd, child.pidfd)

        monkeypatch.setattr(driver, "SIGTERM_GRACE_S", 0.05)
        monkeypatch.setattr(driver.signal, "pidfd_send_signal", swap_after_term)
        try:
            result = driver.finalize(
                child,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=None,
            )
            assert result.outcome == "pid_reuse_detected"
            assert result.signals_sent == ("SIGTERM",)
            assert result.quadruple_reproofs == 2
            assert child.popen.poll() is None
            assert decoy.poll() is None
        finally:
            if child.popen.poll() is None:
                child.popen.kill()
                child.popen.wait(timeout=2)
            if decoy.poll() is None:
                decoy.kill()
                decoy.wait(timeout=2)
            self._test_cleanup(child)

    @pytest.mark.parametrize("tamper", ["start_time_ticks", "exe_sha256"])
    def test_live_identity_tamper_sends_nothing_and_leaves_stub_healthy(
        self, tamper: str
    ) -> None:
        child = self._spawn_stub()
        bad = replace(
            child,
            **(
                {"start_time_ticks": child.start_time_ticks + 1}
                if tamper == "start_time_ticks"
                else {"exe_sha256": "0" * 64}
            ),
        )
        try:
            result = driver.finalize(
                bad,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=child.port,
            )
            assert result.outcome == "pid_reuse_detected"
            assert result.signals_sent == ()
            assert result.quadruple_reproofs == 1
            assert _health(child.port)
        finally:
            self._test_cleanup(child)

    def test_pidfd_must_name_same_pid_as_reproved_quadruple(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = self._test_popen(
            [sys.executable, "-B", "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        second = self._test_popen(
            [sys.executable, "-B", "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        second_pidfd = os.pidfd_open(second.pid)
        self._register_owned_fd(second, second_pidfd)
        pgid, start_time_ticks, exe_sha256 = _test_process_identity(first.pid)
        mixed = driver.OwnedChild(
            pid=first.pid,
            pgid=pgid,
            pidfd=second_pidfd,
            start_time_ticks=start_time_ticks,
            pinned_path=str(Path(sys.executable).resolve()),
            pinned_sha256=exe_sha256,
            exe_sha256=exe_sha256,
            port=None,
            popen=first,
        )
        monkeypatch.setattr(driver, "KILL_WAIT_S", 0.05)
        try:
            result = driver.finalize(
                mixed,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=None,
            )

            assert result.outcome == "pid_reuse_detected"
            assert result.signals_sent == ()
            assert result.quadruple_reproofs == 1
            assert first.poll() is None
            assert second.poll() is None
        finally:
            for proc in (first, second):
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=2)

    def test_unavailable_identity_proof_is_cleanup_incomplete_not_pid_reuse(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        child = self._spawn_stub()
        monkeypatch.setattr(
            driver,
            "_capture_target_identity",
            lambda _pid: (_ for _ in ()).throw(OSError("proc unavailable")),
        )
        try:
            result = driver.finalize(
                child,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=child.port,
            )
            assert result.outcome == "cleanup_incomplete"
            assert result.signals_sent == ()
            assert result.quadruple_reproofs == 1
            assert _health(child.port)
        finally:
            self._test_cleanup(child)

    def test_vanished_leader_is_clean_without_signal(self) -> None:
        proc = self._test_popen(
            [sys.executable, "-B", "-c", "import sys; sys.stdin.read(1)"],
            stdin=subprocess.PIPE,
            start_new_session=True,
        )
        pidfd = os.pidfd_open(proc.pid)
        self._register_owned_fd(proc, pidfd)
        pgid, start_time_ticks, exe_sha256 = _test_process_identity(proc.pid)
        child = driver.OwnedChild(
            pid=proc.pid,
            pgid=pgid,
            pidfd=pidfd,
            start_time_ticks=start_time_ticks,
            pinned_path=str(Path(sys.executable).resolve()),
            pinned_sha256=exe_sha256,
            exe_sha256=exe_sha256,
            port=None,
            popen=proc,
        )
        assert proc.stdin is not None
        proc.stdin.write(b"x")
        proc.stdin.close()
        assert proc.wait(timeout=2) == 0

        result = driver.finalize(
            child,
            clock=driver.SystemClock(),
            port_probe=driver.RealPortProbe(),
            port=None,
        )
        assert result.outcome == "clean"
        assert result.signals_sent == ()
        assert result.quadruple_reproofs == 0

    def test_leader_gone_group_remains_is_observed_never_signalled(self) -> None:
        code = (
            "import subprocess,sys; "
            "p=subprocess.Popen([sys.executable,'-B','-c',"
            "'import time; time.sleep(30)']); "
            "print(p.pid, flush=True); sys.stdin.read(1)"
        )
        proc = self._test_popen(
            [sys.executable, "-B", "-c", code],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        pidfd = os.pidfd_open(proc.pid)
        self._register_owned_fd(proc, pidfd)
        pgid, start_time_ticks, exe_sha256 = _test_process_identity(proc.pid)
        assert proc.stdout is not None
        grandchild = int(proc.stdout.readline().strip())
        grandchild_lease = self._register_test_pid(grandchild)
        child = driver.OwnedChild(
            pid=proc.pid,
            pgid=pgid,
            pidfd=pidfd,
            start_time_ticks=start_time_ticks,
            pinned_path=str(Path(sys.executable).resolve()),
            pinned_sha256=exe_sha256,
            exe_sha256=exe_sha256,
            port=None,
            popen=proc,
        )
        try:
            assert proc.stdin is not None
            proc.stdin.write("x")
            proc.stdin.close()
            assert proc.wait(timeout=2) == 0
            assert Path(f"/proc/{grandchild}").exists()

            result = driver.finalize(
                child,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=None,
            )
            assert result.outcome == "cleanup_incomplete"
            assert result.signals_sent == ()
            assert grandchild in result.surviving_pgid_members
            assert Path(f"/proc/{grandchild}").exists()
        finally:
            try:
                self._test_pidfd_signal(grandchild_lease.pidfd, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
            _wait_for(lambda: not Path(f"/proc/{grandchild}").exists())
            if proc.stdout is not None:
                proc.stdout.close()

    def test_live_leader_with_unexpected_group_member_is_never_signalled(self) -> None:
        code = (
            "import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-B','-c',"
            "'import time; time.sleep(30)']); "
            "print(p.pid, flush=True); time.sleep(30)"
        )
        proc = self._test_popen(
            [sys.executable, "-B", "-c", code],
            stdout=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        pidfd = os.pidfd_open(proc.pid)
        self._register_owned_fd(proc, pidfd)
        pgid, start_time_ticks, exe_sha256 = _test_process_identity(proc.pid)
        assert proc.stdout is not None
        grandchild = int(proc.stdout.readline().strip())
        grandchild_lease = self._register_test_pid(grandchild)
        child = driver.OwnedChild(
            pid=proc.pid,
            pgid=pgid,
            pidfd=pidfd,
            start_time_ticks=start_time_ticks,
            pinned_path=str(Path(sys.executable).resolve()),
            pinned_sha256=exe_sha256,
            exe_sha256=exe_sha256,
            port=None,
            popen=proc,
        )
        try:
            assert proc.poll() is None
            assert Path(f"/proc/{grandchild}").exists()

            result = driver.finalize(
                child,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=None,
            )

            assert result.outcome == "cleanup_incomplete"
            assert result.signals_sent == ()
            assert result.quadruple_reproofs == 0
            assert result.surviving_pgid_members == (proc.pid, grandchild)
            assert proc.poll() is None
            assert Path(f"/proc/{grandchild}").exists()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)
            try:
                self._test_pidfd_signal(grandchild_lease.pidfd, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
            _wait_for(lambda: not Path(f"/proc/{grandchild}").exists())
            if proc.stdout is not None and not proc.stdout.closed:
                proc.stdout.close()

    def test_real_launcher_refuses_port_evidence_not_equal_to_18080(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        launcher = driver.RealServerLauncher(_binary_pin(Path(sys.executable)))
        monkeypatch.setattr(
            driver,
            "spawn_pinned",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("port validation must precede spawn")
            ),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            launcher.spawn(
                [sys.executable, "-B", "-c", "pass", "--port", "18081"],
                _stub_env(),
            )
        _assert_refusal(exc, "spawn_failure")

    def test_real_launcher_binds_post_exec_binary_and_exact_port(self) -> None:
        executable = Path(sys.executable)
        launcher = driver.RealServerLauncher(_binary_pin(executable))
        child = launcher.spawn(
            [
                sys.executable,
                "-B",
                "-c",
                "import time; time.sleep(30)",
                "--port",
                str(driver.BENCH_PORT),
            ],
            _stub_env(),
        )
        self._register_child_evidence(child)
        try:
            assert child.port == driver.BENCH_PORT
            assert child.exe_sha256 == child.pinned_sha256
            result = driver.finalize(
                child,
                clock=driver.SystemClock(),
                port_probe=driver.RealPortProbe(),
                port=None,
            )
            assert result.outcome == "clean"
            assert result.signals_sent == ("SIGTERM",)
        finally:
            self._test_cleanup(child)

    @pytest.mark.parametrize(
        ("tier", "expected_type"),
        [
            ("production", "RealServerLauncher"),
            ("rehearsal", "RehearsalServerLauncher"),
        ],
    )
    def test_factory_returns_concrete_launcher(
        self, tier: str, expected_type: str
    ) -> None:
        components = _provider_components(tier)
        factory = driver.production_tier if tier == "production" else driver.rehearsal_tier
        providers = factory(**components)
        assert type(providers.server_launcher).__name__ == expected_type

    @pytest.mark.parametrize("tier", ["production", "rehearsal"])
    def test_factory_rejects_same_tier_launcher_impostor(self, tier: str) -> None:
        class UnsafeLauncher:
            def __init__(self, claimed_tier: str) -> None:
                self.tier = claimed_tier

            def spawn(self, argv: list[str], env: dict[str, str]) -> object:
                raise AssertionError("unsafe launcher must never enter provider set")

        components = _provider_components(tier)
        components["server_launcher"] = UnsafeLauncher(tier)
        factory = driver.production_tier if tier == "production" else driver.rehearsal_tier
        with pytest.raises(driver.BenchRefusal) as exc:
            factory(**components)
        _assert_refusal(exc, "tier_mismatch")

    def test_b6_client_integrates_with_native_framed_pinned_stub(self) -> None:
        child = self._spawn_stub()
        clock = driver.RehearsalClock()
        client = driver.LoopbackServerClient.rehearsal(clock)
        try:
            assert client.health(child.port) is True
            assert client.models(child.port) == ["qwen36-27b-mtp"]
            measurement = client.stream(child.port, "private prompt sentinel")
            assert measurement.content == "stub response"
            assert measurement.terminal["content"] == ""
            assert measurement.terminal["stop"] is True
            assert measurement.terminal["prompt"] == "private prompt sentinel"
            assert 0 < measurement.ttft_ms <= measurement.e2e_ms
        finally:
            result = driver.finalize(
                child,
                clock=clock,
                port_probe=driver.RealPortProbe(),
                port=child.port,
            )
        assert result.outcome == "clean"
        assert result.listener_free is True

    def test_b6_midturn_hang_times_out_and_finalizer_clears_listener(self) -> None:
        argv = _stub_argv()
        argv[argv.index("healthy")] = "midturn_hang"
        child = self._launcher().spawn(argv, _stub_env())  # type: ignore[attr-defined]
        self._register_child_evidence(child)
        clock = driver.RehearsalClock()
        client = driver.LoopbackServerClient.rehearsal(
            clock,
            request_timeout_ms=200,
        )
        try:
            with pytest.raises(driver.BenchRefusal) as exc:
                client.stream(child.port, "private timeout prompt sentinel")
            _assert_refusal(exc, "http_timeout")
            assert "private timeout prompt sentinel" not in str(exc.value)
        finally:
            result = driver.finalize(
                child,
                clock=clock,
                port_probe=driver.RealPortProbe(),
                port=child.port,
            )
        assert result.outcome == "clean"
        assert result.listener_free is True

    def test_production_finalizer_never_constructs_group_signal(self) -> None:
        source = Path("scripts/cuda_bench_driver.py").read_text()
        assert "killpg" not in source
        assert "os.kill(" not in source


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
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)
        result = driver.RealAuthorizationGate(policy).consume(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-1",
            expected_window_id="window-1",
            parent_window=None,
            parent_packet=None,
            authority_root=private_root,
            receipt_root=receipt_root,
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
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)
        result = driver.RealAuthorizationGate(policy).consume(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-1",
            expected_window_id="window-1",
            parent_window=None,
            parent_packet=None,
            authority_root=private_root,
            receipt_root=receipt_root,
            clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
        )

        marker = private_root / "markers" / authorization.nonce
        receipts = list((receipt_root / "receipts").glob("*.json"))
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
                expected_window_id="window-1",
                clock=clock,
                authority_root=private_root,
                receipt_root=private_root / "attempt",
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
                expected_window_id="window-1",
                clock=driver.FrozenClock(now),
                authority_root=private_root,
                receipt_root=private_root / "attempt",
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
                expected_window_id="window-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                authority_root=private_root,
                receipt_root=private_root / "attempt",
                policy=driver.ProductionArtifactPolicy(),
                parent_window=parent_window,  # type: ignore[arg-type]
                parent_packet=parent_packet,
            )
        _assert_refusal(exc, expected)
        assert list(private_root.rglob("*")) == []

    def test_cuda_gate_rejects_bare_parent_packet_before_nonce_burn(
        self, private_root: Path
    ) -> None:
        window, continuation, packet = _cuda_authorities()
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.RealAuthorizationGate(
                driver.ProductionArtifactPolicy()
            ).consume(
                continuation,
                phase="cuda_candidate",
                boot_id="boot-1",
                expected_window_id="window-1",
                parent_window=window,
                parent_packet=packet,
                parent_completion=None,
                authority_root=private_root,
                receipt_root=receipt_root,
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
            )

        _assert_refusal(exc, "continuation_parent_mismatch")
        assert not (private_root / "markers").exists()
        assert list(receipt_root.rglob("*")) == []

    def test_cuda_gate_revalidates_parent_completion_before_nonce_burn(
        self, private_root: Path
    ) -> None:
        window, continuation, packet = _cuda_authorities()
        evidence = _parent_completion_evidence(packet)
        object.__setattr__(evidence, "packet_ref", "packets/other.json")
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.RealAuthorizationGate(
                driver.ProductionArtifactPolicy()
            ).consume(
                continuation,
                phase="cuda_candidate",
                boot_id="boot-1",
                expected_window_id="window-1",
                parent_window=window,
                parent_packet=packet,
                parent_completion=evidence,
                authority_root=private_root,
                receipt_root=receipt_root,
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
            )

        _assert_refusal(exc, "continuation_parent_mismatch")
        assert not (private_root / "markers").exists()
        assert list(receipt_root.rglob("*")) == []

    @pytest.mark.parametrize("case", ("forged_doc", "mutated_obj"))
    def test_cuda_gate_requires_canonical_parent_completion_preimages(
        self, private_root: Path, case: str
    ) -> None:
        window, continuation, packet = _cuda_authorities()
        evidence = _parent_completion_evidence(packet)
        if case == "forged_doc":
            forged_doc = SimpleNamespace(
                obj=evidence.completion_doc.obj,
                file_sha256=evidence.completion_doc.file_sha256,
            )
            object.__setattr__(evidence, "completion_doc", forged_doc)
        else:
            completion = evidence.completion_doc.obj
            assert type(completion) is driver.cm.CommandCompletionDoc
            forged_ref = "packets/forged.json"
            object.__setattr__(
                evidence.completion_doc,
                "_obj",
                replace(completion, artifact_ref=forged_ref),
            )
            object.__setattr__(evidence, "packet_ref", forged_ref)
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.RealAuthorizationGate(
                driver.ProductionArtifactPolicy()
            ).consume(
                continuation,
                phase="cuda_candidate",
                boot_id="boot-1",
                expected_window_id="window-1",
                parent_window=window,
                parent_packet=packet,
                parent_completion=evidence,
                authority_root=private_root,
                receipt_root=receipt_root,
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
            )

        _assert_refusal(exc, "continuation_parent_mismatch")
        assert not (private_root / "markers").exists()
        assert list(receipt_root.rglob("*")) == []

    def test_cuda_gate_rejects_completion_before_parent_packet_without_burn(
        self, private_root: Path
    ) -> None:
        packet = replace(
            _scorer_phase_packet(),
            timestamp="2026-07-14T10:59:58Z",
        )
        window, continuation, packet = _cuda_authorities(packet=packet)
        evidence = _parent_completion_evidence(packet)
        object.__setattr__(
            evidence,
            "completion_doc",
            _completion_doc_with_timestamp(
                evidence,
                "2026-07-14T10:59:57Z",
            ),
        )
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.RealAuthorizationGate(
                driver.ProductionArtifactPolicy()
            ).consume(
                continuation,
                phase="cuda_candidate",
                boot_id="boot-1",
                expected_window_id="window-1",
                parent_window=window,
                parent_packet=packet,
                parent_completion=evidence,
                authority_root=private_root,
                receipt_root=receipt_root,
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
            )

        _assert_refusal(exc, "continuation_parent_mismatch")
        assert not (private_root / "markers").exists()
        assert list(receipt_root.rglob("*")) == []

    @pytest.mark.parametrize(
        "completion_timestamp",
        (
            "2026-07-14T11:00:01Z",
            "2026-07-14T11:30:01Z",
        ),
    )
    def test_cuda_gate_rejects_parent_completion_after_authority_or_consumption(
        self,
        private_root: Path,
        completion_timestamp: str,
    ) -> None:
        window, continuation, packet = _cuda_authorities()
        evidence = _parent_completion_evidence(packet)
        object.__setattr__(
            evidence,
            "completion_doc",
            _completion_doc_with_timestamp(
                evidence,
                completion_timestamp,
            ),
        )
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.RealAuthorizationGate(
                driver.ProductionArtifactPolicy()
            ).consume(
                continuation,
                phase="cuda_candidate",
                boot_id="boot-1",
                expected_window_id="window-1",
                parent_window=window,
                parent_packet=packet,
                parent_completion=evidence,
                authority_root=private_root,
                receipt_root=receipt_root,
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
            )

        _assert_refusal(exc, "continuation_parent_mismatch")
        assert not (private_root / "markers").exists()
        assert list(receipt_root.rglob("*")) == []

    def test_verified_pair_rejects_swapped_admission_command(
        self, private_root: Path
    ) -> None:
        _window, _continuation, packet = _cuda_authorities()
        evidence = _parent_completion_evidence(packet)
        policy = driver.ProductionArtifactPolicy()
        swapped_ref = "command-cuda-candidate-attempt-001-admission.json"
        swapped_bytes = policy.encode(
            "command_admission",
            {
                "command": "cuda-candidate",
                "ordinal": evidence.admission.ordinal,
                "window_id": packet.window_id,
                "status": "admitted",
                "timestamp": evidence.admission.timestamp,
            },
        )
        swapped_admission = driver.cm.CommandAdmissionPreimage(
            swapped_ref,
            swapped_bytes,
        )
        completion = evidence.completion_doc.obj
        assert type(completion) is driver.cm.CommandCompletionDoc
        swapped_completion = replace(
            completion,
            admission_ref=swapped_admission.selected_ref,
            admission_sha256=swapped_admission.file_sha256,
        )
        completion_ref = (
            "command-vulkan-baseline-attempt-001-completion.json"
        )
        completion_bytes = policy.encode(
            "command_completion",
            {
                "binding_sha256": swapped_completion.binding_sha256,
                "command": swapped_completion.command,
                "ordinal": swapped_completion.ordinal,
                "window_id": swapped_completion.window_id,
                "admission_ref": swapped_completion.admission_ref,
                "admission_sha256": swapped_completion.admission_sha256,
                "artifact_ref": swapped_completion.artifact_ref,
                "artifact_sha256": swapped_completion.artifact_sha256,
                "artifact_schema": swapped_completion.artifact_schema,
                "status": swapped_completion.status,
                "timestamp": swapped_completion.timestamp,
            },
        )
        _private_file(private_root / swapped_ref, swapped_bytes)
        _private_file(private_root / completion_ref, completion_bytes)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver._load_verified_completion_pair(
                admission_ref=swapped_ref,
                completion_ref=completion_ref,
                artifact_ref=evidence.packet_ref,
                artifact_bytes=evidence.packet_doc.wrapper_bytes,
                expected_command="vulkan-baseline",
                expected_window_id=packet.window_id,
                expected_type=driver.cm.PhasePacket,
                root=private_root,
            )

        _assert_refusal(exc, "continuation_parent_mismatch")

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
                expected_window_id="window-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                authority_root=private_root,
                receipt_root=private_root / "attempt",
                policy=driver.ProductionArtifactPolicy(),
                parent_window=window,
                parent_packet=packet,
                parent_completion=_parent_completion_evidence(packet),
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
                expected_window_id="window-1",
                clock=driver.FrozenClock("2026-07-14T12:30:00Z"),
                authority_root=private_root,
                receipt_root=private_root / "attempt",
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
                expected_window_id="window-1",
                clock=driver.FrozenClock("2026-07-14T12:00:00Z"),
                authority_root=private_root,
                receipt_root=private_root / "attempt",
                policy=driver.ProductionArtifactPolicy(),
                parent_window=window,
                parent_packet=packet,
                parent_completion=_parent_completion_evidence(packet),
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
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)
        kwargs = {
            "phase": "vulkan_baseline",
            "boot_id": "boot-1",
            "expected_window_id": "window-1",
            "parent_window": None,
            "parent_packet": None,
            "authority_root": private_root,
            "receipt_root": receipt_root,
            "clock": driver.FrozenClock("2026-07-14T11:30:00Z"),
        }

        first = gate.consume(authorization, **kwargs)
        with pytest.raises(driver.BenchRefusal) as exc:
            gate.consume(authorization, **kwargs)
        _assert_refusal(exc, "authorization_consumed")
        assert first.preimage_sha256 == authorization.preimage_sha256

        other_root = private_root.parent / "concurrent"
        other_root.mkdir(mode=0o700)
        other_receipt_root = other_root / "attempt"
        other_receipt_root.mkdir(mode=0o700)
        other_auth = replace(authorization, nonce="d" * 64)
        concurrent_kwargs = {
            **kwargs,
            "authority_root": other_root,
            "receipt_root": other_receipt_root,
        }

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
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)
        kwargs = {
            "phase": "vulkan_baseline",
            "boot_id": "boot-1",
            "expected_window_id": "window-1",
            "parent_window": None,
            "parent_packet": None,
            "authority_root": private_root,
            "receipt_root": receipt_root,
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
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-1",
                expected_window_id="window-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                authority_root=private_root,
                receipt_root=receipt_root,
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
        marker = marker_dir / authorization.nonce
        real_exists = Path.exists

        def reject_marker_exists_probe(path: Path) -> bool:
            if path == marker:
                raise AssertionError("TOCTOU exists probe")
            return real_exists(path)

        monkeypatch.setattr(
            Path,
            "exists",
            reject_marker_exists_probe,
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-1",
                expected_window_id="window-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                authority_root=private_root,
                receipt_root=private_root / "attempt",
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
                expected_window_id="window-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                authority_root=private_root,
                receipt_root=private_root / "attempt",
                policy=driver.ProductionArtifactPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        _assert_refusal(exc, "filesystem_hazard")
        assert list((private_root / "attempt" / "receipts").glob("*.json")) == []

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
                expected_window_id="window-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                authority_root=private_root,
                receipt_root=private_root / "attempt",
                policy=driver.ProductionArtifactPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        _assert_refusal(exc, "filesystem_hazard")
        assert list((private_root / "attempt" / "receipts").glob("*.json")) == []

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
                expected_window_id="window-1",
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
                authority_root=private_root,
                receipt_root=private_root / "attempt",
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
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)
        result = driver.RehearsalAuthorizationGate(policy).consume(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-1",
            expected_window_id="window-1",
            parent_window=None,
            parent_packet=None,
            authority_root=private_root,
            receipt_root=receipt_root,
            clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
        )
        after_outside = {
            path.relative_to(private_root).as_posix(): path.read_bytes()
            for path in private_root.rglob("*")
            if path.is_file() and "rehearsal" not in path.relative_to(private_root).parts
        }
        rehearsal_files = [
            path
            for path in (receipt_root / "rehearsal").rglob("*")
            if path.is_file()
        ]

        assert after_outside == before
        assert len(rehearsal_files) == 1
        wrapper = json.loads(rehearsal_files[0].read_bytes())
        assert set(wrapper) == {"rehearsal_schema", "tier", "payload"}
        assert wrapper["rehearsal_schema"] == driver.REHEARSAL_PACKET_SCHEMA
        assert wrapper["payload"]["kind"] == "consumption_receipt"
        assert "schema" not in wrapper["payload"]
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
            expected_window_id="window-1",
            parent_window=None,
            parent_packet=None,
            authority_root=private_root,
            receipt_root=receipt_root,
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
        receipt_root = private_root / "attempt"
        receipt_root.mkdir(mode=0o700)
        kwargs = {
            "phase": "vulkan_baseline",
            "boot_id": "boot-1",
            "expected_window_id": "window-1",
            "parent_window": None,
            "parent_packet": None,
            "authority_root": private_root,
            "receipt_root": receipt_root,
            "clock": driver.FrozenClock("2026-07-14T11:30:00Z"),
        }

        monkeypatch.setattr(driver, "_AUTHORIZATION_RECEIPT_SEQUENCE", iter([0]))
        gate.consume(authorization, **kwargs)
        monkeypatch.setattr(driver, "_AUTHORIZATION_RECEIPT_SEQUENCE", iter([0]))
        gate.consume(authorization, **kwargs)

        receipts = list((receipt_root / "rehearsal" / "receipts").glob("*.json"))
        assert len(receipts) == 2
        assert not (private_root / "markers").exists()

    def test_all_inv_2_surfaces_keep_the_identical_postponed_annotation(self) -> None:
        surfaces = (
            driver.AuthorizationGate.validate,
            driver.AuthorizationGate.consume,
            driver.RealAuthorizationGate.validate,
            driver.RealAuthorizationGate.consume,
            driver.RehearsalAuthorizationGate.validate,
            driver.RehearsalAuthorizationGate.consume,
            driver.validate_authorization,
            driver.consume_authorization,
        )
        for surface in surfaces:
            assert inspect.signature(surface).parameters["parent_packet"].annotation == (
                "cm.PhasePacket | None"
            )
            assert surface.__annotations__["parent_packet"] == "cm.PhasePacket | None"
            assert (
                inspect.signature(surface)
                .parameters["parent_completion"]
                .annotation
                == "ParentCompletionEvidence | None"
            )
            assert surface.__annotations__["parent_completion"] == (
                "ParentCompletionEvidence | None"
            )


# Task 3 command-admission REDs intentionally resolve new APIs at test runtime.
# This keeps the pre-implementation focused witness at pytest rc=1 rather than
# turning the existing driver module import into a collection error.
_COMMAND_TIMESTAMP = "2026-07-21T12:00:00Z"
_COMMAND_SCHEMA = "cuda_bench_driver.command_admission.v1"
_COMMANDS = (
    "static-preflight",
    "rehearse",
    "vulkan-baseline",
    "cuda-candidate",
    "assemble-stage1",
)


class _CommandClock:
    def __init__(self, tier: str) -> None:
        self.tier = tier

    def now_utc(self) -> str:
        return _COMMAND_TIMESTAMP

    def monotonic(self) -> float:
        return 0.0


def _task3_api(name: str) -> object:
    return getattr(driver, name)


def _command_admit(
    root: Path,
    *,
    command: str = "static-preflight",
    rehearsal: bool = False,
    window_id: str | None = None,
) -> object:
    try:
        admit = getattr(driver, "_admit_command")
    except AttributeError:
        admit = getattr(driver, "admit_command")
    policy = (
        driver.RehearsalArtifactPolicy()
        if rehearsal
        else driver.ProductionArtifactPolicy()
    )
    return admit(
        command=command,
        window_id=window_id,
        policy=policy,
        clock=_CommandClock(policy.tier),
        root=root,
    )


def _command_tree(root: Path) -> dict[str, tuple[str, int, bytes]]:
    observed: dict[str, tuple[str, int, bytes]] = {}
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        info = path.lstat()
        kind = "directory" if path.is_dir() else "file"
        data = b"" if path.is_dir() else path.read_bytes()
        observed[relative] = (kind, stat.S_IMODE(info.st_mode), data)
    return observed


def _command_admission_fields(
    *, command: str = "static-preflight", ordinal: int = 1
) -> dict[str, object]:
    return {
        "command": command,
        "ordinal": ordinal,
        "window_id": None,
        "status": "admitted",
        "timestamp": _COMMAND_TIMESTAMP,
    }


class TestTask3CommandAdmissionCanon:
    def test_command_admission_exact_schema_23_canon(self) -> None:
        command_schema = _task3_api("COMMAND_ADMISSION_SCHEMA")
        actual = (
            driver.STATIC_PREFLIGHT_SCHEMA,
            driver.cm.SCHEMA_VERSION,
            driver.PHASE_PACKET_SCHEMA,
            driver.REFUSAL_SCHEMA,
            command_schema,
            driver.WINDOW_AUTHORIZATION_SCHEMA,
            driver.CONTINUATION_SCHEMA,
            driver.CONSUMPTION_RECEIPT_SCHEMA,
            driver.TURN_MANIFEST_SCHEMA,
            driver.TURN_ARTIFACT_SCHEMA,
            driver.CONTAINMENT_SNAPSHOT_SCHEMA,
            driver.RUNTIME_IDENTITY_SCHEMA,
            driver.ASSEMBLE_RECEIPT_SCHEMA,
            driver.REHEARSAL_PACKET_SCHEMA,
            driver.cm.BENCH_EVIDENCE_BUNDLE_SCHEMA,
            driver.cm.CYCLE_BACKEND_WITNESS_SCHEMA,
            driver.cm.QUALITY_EVIDENCE_SCHEMA,
            driver.cm.OWNER_VOICE_REVIEW_SCHEMA,
            driver.cm.ROLLBACK_EVIDENCE_BUNDLE_SCHEMA,
            driver.cm.COLD_BOOT_WITNESS_SCHEMA,
            driver.cm.PROVISIONAL_LIVE_WITNESS_SCHEMA,
            driver.cm.AUTHORIZATION_WITNESS_SCHEMA,
            driver.cm.BACKEND_MAP_WITNESS_SCHEMA,
        )
        expected = (
            "cuda_bench_driver.static_preflight.v1",
            "cuda_migration_runtime.v1",
            "cuda_bench_driver.phase_packet.v2",
            "cuda_bench_driver.refusal.v1",
            _COMMAND_SCHEMA,
            "cuda_bench_driver.window_authorization.v1",
            "cuda_bench_driver.continuation.v1",
            "cuda_bench_driver.consumption_receipt.v1",
            "cuda_bench_driver.turn_manifest.v1",
            "cuda_bench_driver.turn_artifact.v1",
            "cuda_bench_driver.containment_snapshot.v2",
            "cuda_bench_driver.runtime_identity.v1",
            "cuda_bench_assemble.receipt.v1",
            "cuda_bench_rehearsal.packet.v1",
            "cuda_migration.bench_evidence_bundle.v1",
            "cuda_migration.cycle_backend_witness.v1",
            "cuda_migration.quality_evidence.v1",
            "cuda_migration.owner_voice_review.v1",
            "cuda_migration.rollback_evidence_bundle.v1",
            "cuda_migration.cold_boot_witness.v1",
            "cuda_migration.provisional_live_witness.v1",
            "cuda_migration.authorization_witness.v1",
            "cuda_migration.backend_map_witness.v1",
        )
        assert actual == expected
        assert len(actual) == len(set(actual)) == 23
        assert actual.count(_COMMAND_SCHEMA) == 1
        assert "cuda_bench_assemble.selection.v1" not in actual

    def test_command_admission_production_shape_is_exact_and_null_bound(self) -> None:
        encoded = driver.ProductionArtifactPolicy().encode(
            "command_admission", _command_admission_fields()
        )
        wrapper = json.loads(encoded)
        assert encoded == (
            json.dumps(wrapper, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        assert wrapper == {
            "schema": _COMMAND_SCHEMA,
            "binding_sha256": None,
            "fields": _command_admission_fields(),
        }

    def test_command_admission_rehearsal_shape_is_incompatible(self) -> None:
        encoded = driver.RehearsalArtifactPolicy().encode(
            "command_admission", _command_admission_fields(command="rehearse")
        )
        wrapper = json.loads(encoded)
        assert "schema" not in wrapper
        assert wrapper == {
            "rehearsal_schema": driver.REHEARSAL_PACKET_SCHEMA,
            "tier": "rehearsal",
            "payload": {
                "kind": "command_admission",
                "binding_sha256": None,
                "fields": _command_admission_fields(command="rehearse"),
            },
        }

    def test_complete_command_admission_bytes_have_no_persisted_decoder(self) -> None:
        encoded = driver.ProductionArtifactPolicy().encode(
            "command_admission", _command_admission_fields()
        )
        assert _COMMAND_SCHEMA not in driver.cm._PERSISTED_REGISTRY
        with pytest.raises(ValueError, match="^persisted_schema_unknown$"):
            driver.cm.PersistedDoc(encoded)

        finalized = json.loads(encoded)
        finalized["fields"]["finalized"] = True
        finalized_bytes = (
            json.dumps(finalized, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        with pytest.raises(ValueError, match="^persisted_schema_unknown$"):
            driver.cm.PersistedDoc(finalized_bytes)


class TestTask3CommandArtifactAllocation:
    def test_command_admission_allocator_mints_immutable_attempt(
        self, private_root: Path
    ) -> None:
        attempt = _command_admit(private_root, window_id="window-1")
        attempt_type = _task3_api("CommandAttempt")
        assert type(attempt) is attempt_type
        assert (
            attempt.command,
            attempt.ordinal,
            attempt.namespace,
            attempt.admission_ref,
        ) == (
            "static-preflight",
            1,
            "",
            "command-static-preflight-attempt-001-admission.json",
        )
        assert re.fullmatch(r"[0-9a-f]{64}", attempt.admission_sha256)
        admission = private_root / attempt.admission_ref
        assert admission.is_file()
        assert stat.S_IMODE(admission.stat().st_mode) == 0o600
        assert hashlib.sha256(admission.read_bytes()).hexdigest() == (
            attempt.admission_sha256
        )
        with pytest.raises((AttributeError, FrozenInstanceError, TypeError)):
            attempt.ordinal = 2

    def test_command_artifact_names_share_admission_ordinal_and_namespace(
        self, private_root: Path
    ) -> None:
        publish = _task3_api("publish_command_artifact")
        production = _command_admit(private_root)
        encoded = driver.ProductionArtifactPolicy().encode(
            "refusal", {"outcome": "assembly_refused"}
        )
        terminal_ref, digest = publish(
            production, "terminal", encoded, root=private_root
        )
        assert terminal_ref == "command-static-preflight-attempt-001-terminal.json"
        assert hashlib.sha256((private_root / terminal_ref).read_bytes()).hexdigest() == digest

        rehearsal = _command_admit(
            private_root, command="rehearse", rehearsal=True
        )
        rehearsal_bytes = driver.RehearsalArtifactPolicy().encode(
            "refusal", {"outcome": "assembly_refused"}
        )
        rehearsal_ref, _ = publish(
            rehearsal, "terminal", rehearsal_bytes, root=private_root
        )
        assert rehearsal.admission_ref == (
            "rehearsal/command-rehearse-attempt-002-admission.json"
        )
        assert rehearsal_ref == (
            "rehearsal/command-rehearse-attempt-002-terminal.json"
        )

    def test_command_artifact_role_is_closed_and_direct_forge_cannot_publish(
        self, private_root: Path
    ) -> None:
        publish = _task3_api("publish_command_artifact")
        attempt = _command_admit(private_root)
        encoded = driver.ProductionArtifactPolicy().encode(
            "refusal", {"outcome": "assembly_refused"}
        )
        with pytest.raises((ValueError, driver.BenchRefusal)):
            publish(attempt, "receipt", encoded, root=private_root)

        with pytest.raises((TypeError, ValueError)):
            replace(attempt, ordinal=attempt.ordinal + 1)

        attempt_type = _task3_api("CommandAttempt")
        try:
            forged = attempt_type(
                command=attempt.command,
                ordinal=attempt.ordinal + 1,
                admission_ref=attempt.admission_ref,
                admission_sha256=attempt.admission_sha256,
                namespace=attempt.namespace,
            )
        except (TypeError, ValueError):
            return
        with pytest.raises((ValueError, driver.BenchRefusal)):
            publish(forged, "terminal", encoded, root=private_root)

    def test_command_admission_disk_scan_uses_max_plus_one_for_both_roles(
        self, private_root: Path
    ) -> None:
        for name in (
            "command-static-preflight-attempt-003-admission.json",
            "command-static-preflight-attempt-009-terminal.json",
            "command-other-attempt-012-admission.json",
            "unrelated-attempt-999.json",
        ):
            _private_file(private_root / name, b"{}\n")
        attempt = _command_admit(private_root)
        assert attempt.ordinal == 13
        assert attempt.admission_ref.endswith("attempt-013-admission.json")

    def test_phase_and_command_call_the_same_shared_disk_allocator(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        shared = _task3_api("_allocate_disk_ordinal")
        observed: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def spy(*args: object, **kwargs: object) -> object:
            observed.append((args, dict(kwargs)))
            return shared(*args, **kwargs)

        monkeypatch.setattr(driver, "_allocate_disk_ordinal", spy)
        phase_attempt = driver._allocate_attempt(
            window_id="window-shared-allocator",
            phase="vulkan_baseline",
            policy=driver.ProductionArtifactPolicy(),
            root=private_root,
        )
        command_attempt = _command_admit(private_root)

        assert phase_attempt.name == "attempt-000"
        assert command_attempt.ordinal == 1
        assert len(observed) == 2

    def test_command_admission_retries_only_true_eexist(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_link = driver.os.link
        calls = 0

        def racing_link(*args: object, **kwargs: object) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                real_link(*args, **kwargs)
                raise FileExistsError(errno.EEXIST, "simulated race")
            real_link(*args, **kwargs)

        monkeypatch.setattr(driver.os, "link", racing_link)
        attempt = _command_admit(private_root)
        assert attempt.ordinal == 2
        assert calls == 2
        assert sorted(path.name for path in private_root.glob("*-admission.json")) == [
            "command-static-preflight-attempt-001-admission.json",
            "command-static-preflight-attempt-002-admission.json",
        ]

    def test_command_admission_never_retries_non_eexist(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = 0

        def failing_link(*_args: object, **_kwargs: object) -> None:
            nonlocal calls
            calls += 1
            raise OSError(errno.EIO, "injected I/O failure")

        monkeypatch.setattr(driver.os, "link", failing_link)
        with pytest.raises(driver.BenchRefusal):
            _command_admit(private_root)
        assert calls == 1
        assert _command_tree(private_root) == {}

    def test_command_artifact_sequential_same_clock_invocations_are_unique(
        self, private_root: Path
    ) -> None:
        publish = _task3_api("publish_command_artifact")
        encoded = driver.ProductionArtifactPolicy().encode(
            "refusal", {"outcome": "assembly_refused"}
        )
        observed: list[tuple[str, str]] = []
        for _ in range(8):
            attempt = _command_admit(private_root)
            terminal_ref, _ = publish(
                attempt, "terminal", encoded, root=private_root
            )
            observed.append((attempt.admission_ref, terminal_ref))
        assert len({item for pair in observed for item in pair}) == 16
        assert [
            int(re.search(r"attempt-([0-9]+)", pair[0]).group(1))
            for pair in observed
        ] == list(range(1, 9))

    def test_command_artifact_concurrent_same_clock_invocations_are_unique(
        self, private_root: Path
    ) -> None:
        publish = _task3_api("publish_command_artifact")
        encoded = driver.ProductionArtifactPolicy().encode(
            "refusal", {"outcome": "assembly_refused"}
        )

        def invoke(_index: int) -> tuple[str, str]:
            attempt = _command_admit(private_root)
            terminal_ref, _ = publish(
                attempt, "terminal", encoded, root=private_root
            )
            return attempt.admission_ref, terminal_ref

        with ThreadPoolExecutor(max_workers=8) as pool:
            observed = list(pool.map(invoke, range(16)))
        refs = [item for pair in observed for item in pair]
        assert len(refs) == len(set(refs)) == 32
        assert sorted(
            int(re.search(r"attempt-([0-9]+)", pair[0]).group(1))
            for pair in observed
        ) == list(range(1, 17))

    @staticmethod
    def _admit_after_synchronized_empty_scan(
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        commands: tuple[str, str],
    ) -> list[object]:
        real_listdir = driver.os.listdir
        barrier = threading.Barrier(2)
        scan_lock = threading.Lock()
        synchronized_scans = 0

        def synchronized_listdir(fd: int) -> list[str]:
            nonlocal synchronized_scans
            names = real_listdir(fd)
            with scan_lock:
                should_wait = synchronized_scans < 2
                if should_wait:
                    synchronized_scans += 1
            if should_wait:
                assert names == []
                barrier.wait(timeout=5)
            return names

        monkeypatch.setattr(driver.os, "listdir", synchronized_listdir)
        with ThreadPoolExecutor(max_workers=2) as pool:
            attempts = list(
                pool.map(
                    lambda command: _command_admit(
                        private_root,
                        command=command,
                    ),
                    commands,
                )
            )
        assert synchronized_scans == 2
        return attempts

    def test_same_command_atomic_claim_resolves_synchronized_scan_collision(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempts = self._admit_after_synchronized_empty_scan(
            private_root,
            monkeypatch,
            ("static-preflight", "static-preflight"),
        )
        assert sorted(attempt.ordinal for attempt in attempts) == [1, 2]

    def test_command_ordinals_are_global_across_different_commands(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempts = self._admit_after_synchronized_empty_scan(
            private_root,
            monkeypatch,
            ("static-preflight", "vulkan-baseline"),
        )
        assert sorted(attempt.ordinal for attempt in attempts) == [1, 2]

    def test_command_ordinals_are_global_across_processes(
        self, private_root: Path
    ) -> None:
        coordination = private_root / "coordination"
        coordination.mkdir(mode=0o700)
        code = "\n".join(
            (
                "import json, os, sys, time",
                "from pathlib import Path",
                "from scripts import cuda_bench_driver as driver",
                "root, command = Path(sys.argv[1]), sys.argv[2]",
                "coordination = root / 'coordination'",
                "real_listdir = driver.os.listdir",
                "first_scan = [True]",
                "def synchronized_listdir(fd):",
                "    names = real_listdir(fd)",
                "    if first_scan[0]:",
                "        first_scan[0] = False",
                "        marker = coordination / command",
                "        marker.write_text('ready', encoding='utf-8')",
                "        os.chmod(marker, 0o600)",
                "        other = coordination / ('vulkan-baseline' if command == 'static-preflight' else 'static-preflight')",
                "        deadline = time.monotonic() + 5",
                "        while not other.is_file():",
                "            if time.monotonic() >= deadline: raise RuntimeError('sync timeout')",
                "            time.sleep(0.005)",
                "    return names",
                "driver.os.listdir = synchronized_listdir",
                "attempt = driver._admit_command(command, None, driver.ProductionArtifactPolicy(), driver.FrozenClock('2026-07-16T12:00:00Z'), root)",
                "print(json.dumps({'ordinal': attempt.ordinal}))",
            )
        )
        processes = [
            subprocess.Popen(
                [sys.executable, "-B", "-c", code, str(private_root), command],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for command in ("static-preflight", "vulkan-baseline")
        ]
        results: list[subprocess.CompletedProcess[str]] = []
        try:
            for process in processes:
                stdout, stderr = process.communicate(timeout=10)
                results.append(
                    subprocess.CompletedProcess(
                        process.args,
                        process.returncode,
                        stdout,
                        stderr,
                    )
                )
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=3)

        assert [result.returncode for result in results] == [0, 0], [
            result.stderr for result in results
        ]
        assert sorted(json.loads(result.stdout)["ordinal"] for result in results) == [
            1,
            2,
        ]

    def test_global_ordinal_unlock_failure_cleans_the_linked_claim(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_flock = driver.fcntl.flock
        failed = False

        def failing_unlock(fd: int, operation: int) -> None:
            nonlocal failed
            real_flock(fd, operation)
            if operation == driver.fcntl.LOCK_UN and not failed:
                failed = True
                raise OSError(errno.EIO, "ordinal unlock failed")

        monkeypatch.setattr(driver.fcntl, "flock", failing_unlock)
        with pytest.raises(driver.BenchRefusal, match="^filesystem_hazard$"):
            _command_admit(private_root)

        assert failed is True
        assert _command_tree(private_root) == {}

    def test_invalid_quarantine_validation_closes_its_directory_fd(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        quarantine_name = f".command-cleanup-rehearsal-{'a' * 32}"
        quarantine = private_root / quarantine_name
        quarantine.mkdir(mode=0o700)
        quarantine.chmod(0o755)
        real_open = driver.os.open
        opened: list[int] = []

        def capture_open(path: object, *args: object, **kwargs: object) -> int:
            fd = real_open(path, *args, **kwargs)
            if path == quarantine_name:
                opened.append(fd)
            return fd

        monkeypatch.setattr(driver.os, "open", capture_open)
        with pytest.raises(driver.BenchRefusal, match="^filesystem_hazard$"):
            _command_admit(private_root)

        assert len(opened) == 1
        try:
            os.fstat(opened[0])
        except OSError as exc:
            assert exc.errno == errno.EBADF
        else:
            os.close(opened[0])
            pytest.fail("invalid quarantine descriptor escaped validation")


class TestTask3CommandAdmissionTransaction:
    @pytest.mark.parametrize("boundary", ("link", "parent_fsync", "reopen", "hash"))
    def test_command_admission_prelinearization_failures_cleanup_tree(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        boundary: str,
    ) -> None:
        before = _command_tree(private_root)
        linked = False
        failed = False
        real_link = driver.os.link
        real_fsync = driver.os.fsync
        real_open = driver.os.open
        real_sha256 = driver.hashlib.sha256

        def injected_link(*args: object, **kwargs: object) -> None:
            nonlocal linked
            if boundary == "link":
                raise OSError(errno.EIO, "link")
            real_link(*args, **kwargs)
            linked = True

        def injected_fsync(fd: int) -> None:
            nonlocal failed
            if (
                boundary == "parent_fsync"
                and linked
                and not failed
                and stat.S_ISDIR(os.fstat(fd).st_mode)
            ):
                failed = True
                raise OSError(errno.EIO, "parent fsync")
            real_fsync(fd)

        def injected_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
            nonlocal failed
            if (
                boundary == "reopen"
                and linked
                and not failed
                and str(path).endswith("-admission.json")
                and flags & os.O_ACCMODE == os.O_RDONLY
            ):
                failed = True
                raise OSError(errno.EIO, "reopen")
            return real_open(path, flags, *args, **kwargs)

        def injected_sha256(*args: object, **kwargs: object) -> object:
            nonlocal failed
            if boundary == "hash" and linked and not failed:
                failed = True
                raise OSError(errno.EIO, "hash")
            return real_sha256(*args, **kwargs)

        monkeypatch.setattr(driver.os, "link", injected_link)
        monkeypatch.setattr(driver.os, "fsync", injected_fsync)
        monkeypatch.setattr(driver.os, "open", injected_open)
        monkeypatch.setattr(driver.hashlib, "sha256", injected_sha256)
        with pytest.raises((driver.BenchRefusal, OSError)):
            _command_admit(private_root)
        assert _command_tree(private_root) == before

    def test_command_admission_catchable_post_link_failure_cleans_up(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_link = driver.os.link

        def interrupted_link(*args: object, **kwargs: object) -> None:
            real_link(*args, **kwargs)
            raise KeyboardInterrupt

        monkeypatch.setattr(driver.os, "link", interrupted_link)
        with pytest.raises((KeyboardInterrupt, driver.BenchRefusal)):
            _command_admit(private_root)
        assert _command_tree(private_root) == {}

    @pytest.mark.parametrize("cleanup_failure", ("unlink", "parent_fsync"))
    def test_command_admission_cleanup_failure_is_typed_cleanup_incomplete(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        cleanup_failure: str,
    ) -> None:
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
            if linked and stat.S_ISDIR(os.fstat(fd).st_mode):
                directory_syncs += 1
                if directory_syncs == 1 or cleanup_failure == "parent_fsync":
                    raise OSError(errno.EIO, "directory fsync")
            real_fsync(fd)

        def failing_unlink(*args: object, **kwargs: object) -> None:
            if cleanup_failure == "unlink":
                raise OSError(errno.EIO, "unlink")
            real_unlink(*args, **kwargs)

        monkeypatch.setattr(driver.os, "link", tracking_link)
        monkeypatch.setattr(driver.os, "fsync", failing_fsync)
        monkeypatch.setattr(driver.os, "unlink", failing_unlink)
        with pytest.raises(driver.BenchRefusal) as exc:
            _command_admit(private_root)
        _assert_refusal(exc, "cleanup_incomplete")

    def test_command_admission_held_root_detects_replacement_and_cleans_original(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        displaced = private_root.with_name("displaced")
        real_link = driver.os.link

        def replacing_link(*args: object, **kwargs: object) -> None:
            real_link(*args, **kwargs)
            private_root.rename(displaced)
            private_root.mkdir(mode=0o700)
            os.chmod(private_root, 0o700)

        monkeypatch.setattr(driver.os, "link", replacing_link)
        with pytest.raises(driver.BenchRefusal):
            _command_admit(private_root)
        assert _command_tree(private_root) == {}
        assert _command_tree(displaced) == {}

    def test_command_admission_holds_one_root_fd_without_path_reopen(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_open_root = driver._open_root_fd
        open_root_calls = 0

        def observed_open_root(root: Path) -> int:
            nonlocal open_root_calls
            open_root_calls += 1
            return real_open_root(root)

        def forbidden_path_reopen(*_args: object, **_kwargs: object) -> bytes:
            raise AssertionError("admission reopened through root path")

        monkeypatch.setattr(driver, "_open_root_fd", observed_open_root)
        monkeypatch.setattr(driver, "open_bench_file", forbidden_path_reopen)
        attempt = _command_admit(private_root)

        assert open_root_calls == 1
        assert (private_root / attempt.admission_ref).is_file()

    def test_command_admission_rehearsal_directory_cleanup_is_identity_scoped(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_link = driver.os.link

        def failing_link(*_args: object, **_kwargs: object) -> None:
            raise OSError(errno.EIO, "link")

        monkeypatch.setattr(driver.os, "link", failing_link)
        with pytest.raises(driver.BenchRefusal):
            _command_admit(private_root, command="rehearse", rehearsal=True)
        assert _command_tree(private_root) == {}

        rehearsal = private_root / "rehearsal"
        rehearsal.mkdir(mode=0o700)
        os.chmod(rehearsal, 0o700)
        sentinel = rehearsal / "sentinel"
        _private_file(sentinel, b"owner-existing")
        with pytest.raises(driver.BenchRefusal):
            _command_admit(private_root, command="rehearse", rehearsal=True)
        assert _command_tree(private_root) == {
            "rehearsal": ("directory", 0o700, b""),
            "rehearsal/sentinel": ("file", 0o600, b"owner-existing"),
        }
        monkeypatch.setattr(driver.os, "link", real_link)

    def test_command_artifact_publication_requires_exact_latched_binding(
        self, private_root: Path
    ) -> None:
        publish = _task3_api("publish_command_artifact")
        attempt = _command_admit(private_root)
        encoded = driver.ProductionArtifactPolicy().encode(
            "refusal", {"outcome": "assembly_refused"}
        )
        admission = private_root / attempt.admission_ref
        admission.unlink()
        _private_file(admission, b"{}\n")
        with pytest.raises(driver.BenchRefusal):
            publish(attempt, "terminal", encoded, root=private_root)
        assert not list(private_root.glob("*-terminal.json"))


class TestTask3CommandAdmissionCrashHonesty:
    def test_full_linked_sigkill_orphan_has_no_terminal_or_attempt_recovery(
        self, private_root: Path, tmp_path: Path
    ) -> None:
        ready = tmp_path / "linked-ready"
        code = "\n".join(
            (
                "import os, sys, time",
                "from pathlib import Path",
                "from scripts import cuda_bench_driver as driver",
                "root, ready = Path(sys.argv[1]), Path(sys.argv[2])",
                "real_link = driver.os.link",
                "def linked(*args, **kwargs):",
                "    real_link(*args, **kwargs)",
                "    ready.write_text('linked', encoding='utf-8')",
                "    while True: time.sleep(0.05)",
                "driver.os.link = linked",
                "try: admit = getattr(driver, '_admit_command')",
                "except AttributeError: admit = getattr(driver, 'admit_command')",
                "class Clock:",
                "    tier = 'production'",
                f"    def now_utc(self): return {_COMMAND_TIMESTAMP!r}",
                "    def monotonic(self): return 0.0",
                "attempt = admit(command='static-preflight', window_id=None, policy=driver.ProductionArtifactPolicy(), clock=Clock(), root=root)",
                "print(attempt, flush=True)",
            )
        )
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", code, str(private_root), str(ready)],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            assert _wait_for(ready.is_file, timeout=8.0)
            process.kill()
            stdout, stderr = process.communicate(timeout=5.0)
        except BaseException:
            process.kill()
            process.wait(timeout=3.0)
            raise

        assert process.returncode == -signal.SIGKILL
        assert stdout == ""
        assert stderr == ""
        assert not list(private_root.glob("*-terminal.json"))
        orphan = next(private_root.glob("*-admission.json"))
        wrapper = json.loads(orphan.read_bytes())
        assert wrapper == {
            "schema": _COMMAND_SCHEMA,
            "binding_sha256": None,
            "fields": _command_admission_fields(),
        }
        with pytest.raises(ValueError, match="^persisted_schema_unknown$"):
            driver.cm.PersistedDoc(orphan.read_bytes())
        attempt_type = _task3_api("CommandAttempt")
        assert not hasattr(attempt_type, "from_admission")
        assert not hasattr(driver, "recover_command_attempt")

        restarted = _command_admit(private_root)
        assert restarted.ordinal == 2
        assert restarted.admission_ref.endswith("attempt-002-admission.json")

    @pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
    def test_command_admission_latches_exact_binding_before_unmask(
        self, private_root: Path, signum: int
    ) -> None:
        code = "\n".join(
            (
                "import json, os, signal, sys",
                "from pathlib import Path",
                "from scripts import cuda_bench_cli as cli",
                "from scripts import cuda_bench_driver as driver",
                "root = Path(sys.argv[1])",
                "real_mask = signal.pthread_sigmask",
                "restore_calls = 0",
                "def injected_mask(how, mask):",
                "    global restore_calls",
                "    if how == signal.SIG_SETMASK:",
                "        restore_calls += 1",
                "        if restore_calls == 1: os.kill(os.getpid(), int(sys.argv[2]))",
                "    return real_mask(how, mask)",
                "driver.signal.pthread_sigmask = injected_mask",
                "class Clock:",
                "    tier = 'production'",
                f"    def now_utc(self): return {_COMMAND_TIMESTAMP!r}",
                "    def monotonic(self): return 0.0",
                "def forbidden(*_args, **_kwargs): raise AssertionError('handler ran')",
                "raise SystemExit(cli._run_command('static-preflight', forbidden, root=root, clock=Clock()))",
            )
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(private_root), str(signum)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == (130 if signum == signal.SIGINT else 143)
        assert result.stderr == ""
        assert result.stdout.count("\n") == 1
        terminal = json.loads(result.stdout)
        assert terminal["outcome"] == "interrupted"
        assert terminal["artifact_ref"].endswith("-admission.json")
        admission = private_root / terminal["artifact_ref"]
        assert hashlib.sha256(admission.read_bytes()).hexdigest() == terminal[
            "artifact_sha256"
        ]

    def test_command_artifact_adds_no_process_local_counter_authority(self) -> None:
        import ast

        tree = ast.parse(Path(driver.__file__).read_text(encoding="utf-8"))
        process_counter_names: set[str] = set()
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name)
                and value.func.value.id == "itertools"
                and value.func.attr == "count"
            ):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            process_counter_names.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )

        command_nodes = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and "command" in node.name.lower()
        ]
        assert command_nodes
        for command_node in command_nodes:
            for nested in ast.walk(command_node):
                assert not (
                    isinstance(nested, ast.Call)
                    and isinstance(nested.func, ast.Attribute)
                    and isinstance(nested.func.value, ast.Name)
                    and nested.func.value.id == "itertools"
                    and nested.func.attr == "count"
                )
                assert not (
                    isinstance(nested, ast.Name)
                    and isinstance(nested.ctx, ast.Load)
                    and nested.id in process_counter_names
                )


class TestTask3ReviewAdmissionFailureBoundaries:
    @pytest.mark.parametrize(
        "boundary", ("file_fsync", "parent_fsync", "reopen", "hash")
    )
    def test_only_link_eexist_advances_the_disk_ordinal(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        boundary: str,
    ) -> None:
        real_fsync = driver.os.fsync
        real_open = driver.os.open
        real_sha256 = driver.hashlib.sha256
        real_link = driver.os.link
        state = {"failed": False, "linked": False, "link_calls": 0}

        def injected_link(*args: object, **kwargs: object) -> None:
            state["link_calls"] += 1
            real_link(*args, **kwargs)
            state["linked"] = True

        def injected_fsync(fd: int) -> None:
            is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            should_fail = (
                boundary == "file_fsync" and not state["linked"] and not is_directory
            ) or (
                boundary == "parent_fsync" and state["linked"] and is_directory
            )
            if should_fail and not state["failed"]:
                state["failed"] = True
                raise FileExistsError(errno.EEXIST, "non-link durability failure")
            real_fsync(fd)

        def injected_open(
            path: object, flags: int, *args: object, **kwargs: object
        ) -> int:
            if (
                boundary == "reopen"
                and state["linked"]
                and not state["failed"]
                and str(path).endswith("-admission.json")
                and flags & os.O_ACCMODE == os.O_RDONLY
            ):
                state["failed"] = True
                raise FileExistsError(errno.EEXIST, "non-link reopen failure")
            return real_open(path, flags, *args, **kwargs)

        def injected_sha256(*args: object, **kwargs: object) -> object:
            if boundary == "hash" and state["linked"] and not state["failed"]:
                state["failed"] = True
                raise FileExistsError(errno.EEXIST, "non-link hash failure")
            return real_sha256(*args, **kwargs)

        monkeypatch.setattr(driver.os, "link", injected_link)
        monkeypatch.setattr(driver.os, "fsync", injected_fsync)
        monkeypatch.setattr(driver.os, "open", injected_open)
        monkeypatch.setattr(driver.hashlib, "sha256", injected_sha256)

        with pytest.raises(driver.BenchRefusal) as exc:
            _command_admit(private_root)

        _assert_refusal(exc, "filesystem_hazard")
        assert state["failed"] is True
        assert state["link_calls"] <= 1
        assert not list(private_root.glob("*attempt-002*"))
        assert _command_tree(private_root) == {}

    @pytest.mark.parametrize("boundary", ("second_open", "validation"))
    def test_rehearsal_namespace_setup_failure_restores_tree_and_signal_mask(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        boundary: str,
    ) -> None:
        real_open = driver.os.open
        real_check = driver._check_directory_fd
        namespace_opens = 0
        directory_checks = 0
        injected = False
        original_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())

        def injected_open(
            path: object, flags: int, *args: object, **kwargs: object
        ) -> int:
            nonlocal injected, namespace_opens
            if path == "rehearsal" and kwargs.get("dir_fd") is not None:
                namespace_opens += 1
                if boundary == "second_open" and namespace_opens == 2:
                    injected = True
                    raise OSError(errno.EIO, "namespace reopen failure")
            return real_open(path, flags, *args, **kwargs)

        def injected_check(fd: int) -> os.stat_result:
            nonlocal directory_checks, injected
            directory_checks += 1
            if boundary == "validation" and directory_checks == 2:
                injected = True
                raise driver.BenchRefusal("filesystem_hazard")
            return real_check(fd)

        monkeypatch.setattr(driver.os, "open", injected_open)
        monkeypatch.setattr(driver, "_check_directory_fd", injected_check)

        caught: BaseException | None = None
        observed_mask: set[signal.Signals] | None = None
        try:
            try:
                _command_admit(private_root, command="rehearse", rehearsal=True)
            except BaseException as exc:
                caught = exc
            observed_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, original_mask)

        assert injected is True
        assert isinstance(caught, driver.BenchRefusal)
        assert caught.code == "filesystem_hazard"
        assert observed_mask == original_mask
        assert _command_tree(private_root) == {}


def _replacement_inode_survives(
    root: Path, identity: tuple[int, int], *, directory: bool
) -> bool:
    for path in root.rglob("*"):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if (info.st_dev, info.st_ino) != identity:
            continue
        return stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    return False


class TestTask3ReviewAdmissionIdentityProofs:
    @pytest.mark.parametrize("target", ("linked_file", "created_namespace"))
    def test_cleanup_never_deletes_a_post_observation_replacement(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        target: str,
    ) -> None:
        replacement_identity: tuple[int, int] | None = None
        swapped = False
        real_fsync = driver.os.fsync
        real_link = driver.os.link
        real_named_match = driver._named_inode_matches
        real_stat = driver.os.stat
        linked = False
        failed = False
        namespace_stats = 0

        def injected_link(*args: object, **kwargs: object) -> None:
            nonlocal linked
            if target == "created_namespace":
                raise OSError(errno.EIO, "trigger namespace cleanup")
            real_link(*args, **kwargs)
            linked = True

        def injected_fsync(fd: int) -> None:
            nonlocal failed
            if (
                target == "linked_file"
                and linked
                and not failed
                and stat.S_ISDIR(os.fstat(fd).st_mode)
            ):
                failed = True
                raise OSError(errno.EIO, "trigger linked-file cleanup")
            real_fsync(fd)

        def swap_after_named_observation(
            parent_fd: int, name: str, expected: os.stat_result
        ) -> bool:
            nonlocal replacement_identity, swapped
            matched = real_named_match(parent_fd, name, expected)
            if target == "linked_file" and matched and not swapped:
                swapped = True
                os.rename(
                    name,
                    f"observed-{name}",
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent_fd,
                )
                try:
                    os.write(fd, b"replacement-must-survive\n")
                    info = os.fstat(fd)
                    replacement_identity = (info.st_dev, info.st_ino)
                finally:
                    os.close(fd)
            return matched

        def swap_after_namespace_observation(
            path: object, *args: object, **kwargs: object
        ) -> os.stat_result:
            nonlocal namespace_stats, replacement_identity, swapped
            info = real_stat(path, *args, **kwargs)
            if (
                target == "created_namespace"
                and path == "rehearsal"
                and kwargs.get("dir_fd") is not None
            ):
                namespace_stats += 1
                if namespace_stats == 2 and not swapped:
                    swapped = True
                    root_fd = int(kwargs["dir_fd"])
                    os.rename(
                        "rehearsal",
                        "observed-rehearsal",
                        src_dir_fd=root_fd,
                        dst_dir_fd=root_fd,
                    )
                    os.mkdir("rehearsal", mode=0o700, dir_fd=root_fd)
                    replacement = real_stat(
                        "rehearsal", dir_fd=root_fd, follow_symlinks=False
                    )
                    replacement_identity = (replacement.st_dev, replacement.st_ino)
            return info

        monkeypatch.setattr(driver.os, "link", injected_link)
        monkeypatch.setattr(driver.os, "fsync", injected_fsync)
        monkeypatch.setattr(driver, "_named_inode_matches", swap_after_named_observation)
        monkeypatch.setattr(driver.os, "stat", swap_after_namespace_observation)

        caught: BaseException | None = None
        try:
            _command_admit(
                private_root,
                command="rehearse" if target == "created_namespace" else "static-preflight",
                rehearsal=target == "created_namespace",
            )
        except BaseException as exc:
            caught = exc

        assert swapped is True
        assert isinstance(caught, driver.BenchRefusal)
        assert caught.code == "cleanup_incomplete"
        assert replacement_identity is not None
        assert _replacement_inode_survives(
            private_root,
            replacement_identity,
            directory=target == "created_namespace",
        )

    def test_created_rehearsal_identity_cannot_be_swapped_before_open(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_stat = driver.os.stat
        replacement_identity: tuple[int, int] | None = None
        swapped = False

        def swap_after_post_mkdir_stat(
            path: object, *args: object, **kwargs: object
        ) -> os.stat_result:
            nonlocal replacement_identity, swapped
            info = real_stat(path, *args, **kwargs)
            if (
                not swapped
                and path == "rehearsal"
                and kwargs.get("dir_fd") is not None
            ):
                swapped = True
                root_fd = int(kwargs["dir_fd"])
                os.rename(
                    "rehearsal",
                    "created-rehearsal",
                    src_dir_fd=root_fd,
                    dst_dir_fd=root_fd,
                )
                os.mkdir("rehearsal", mode=0o700, dir_fd=root_fd)
                replacement = real_stat(
                    "rehearsal", dir_fd=root_fd, follow_symlinks=False
                )
                replacement_identity = (replacement.st_dev, replacement.st_ino)
            return info

        monkeypatch.setattr(driver.os, "stat", swap_after_post_mkdir_stat)

        attempt: object | None = None
        caught: BaseException | None = None
        try:
            attempt = _command_admit(
                private_root, command="rehearse", rehearsal=True
            )
        except BaseException as exc:
            caught = exc

        assert swapped is True
        assert attempt is None
        assert isinstance(caught, driver.BenchRefusal)
        assert caught.code in {"filesystem_hazard", "cleanup_incomplete"}
        assert replacement_identity is not None
        assert _replacement_inode_survives(
            private_root, replacement_identity, directory=True
        )


def _run_dual_signal_publication_cleanup(
    root: Path,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import json, os, signal, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "root = Path(sys.argv[1])",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {_COMMAND_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "attempt = driver._admit_command('static-preflight', None, driver.ProductionArtifactPolicy(), Clock(), root)",
            "real_link = driver.os.link",
            "real_rename = driver.os.rename",
            "fired = {'sigint': False, 'sigterm': False}",
            "def injected_link(*args, **kwargs):",
            "    result = real_link(*args, **kwargs)",
            "    if str(args[1]).endswith('-terminal.json'):",
            "        fired['sigint'] = True",
            "        os.kill(os.getpid(), signal.SIGINT)",
            "    return result",
            "def injected_rename(*args, **kwargs):",
            "    result = real_rename(*args, **kwargs)",
            "    if str(args[0]).endswith('-terminal.json'):",
            "        fired['sigterm'] = True",
            "        os.kill(os.getpid(), signal.SIGTERM)",
            "    return result",
            "driver.os.link = injected_link",
            "driver.os.rename = injected_rename",
            "previous = cli._install_command_signal_scope()",
            "observed = {}",
            "try:",
            "    encoded = driver.ProductionArtifactPolicy().encode('refusal', {'outcome': 'assembly_refused'})",
            "    driver.publish_command_artifact(attempt, 'terminal', encoded, root=root)",
            "    observed = {'kind': 'returned'}",
            "except driver._CommandInterrupted as exc:",
            "    observed = {'kind': 'interrupted', 'signum': exc.signum}",
            "except driver.BenchRefusal as exc:",
            "    observed = {'kind': 'refused', 'code': exc.code}",
            "finally:",
            "    cli._restore_command_signal_scope(previous)",
            "observed['injected'] = fired",
            "print(json.dumps(observed, sort_keys=True, separators=(',', ':')))",
        )
    )
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(root)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


class TestTask3ReviewConsolidatedBindingBoundaries:
    @pytest.mark.parametrize("operation", ("admit", "publish"))
    def test_command_root_fd_is_signal_owned_from_acquisition(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        operation: str,
    ) -> None:
        attempt = _command_admit(private_root) if operation == "publish" else None
        encoded = driver.ProductionArtifactPolicy().encode(
            "refusal", {"outcome": "assembly_refused"}
        )
        real_open_root = driver._open_root_fd
        opened: list[int] = []

        def interrupt_after_open(root: Path) -> int:
            fd = real_open_root(root)
            opened.append(fd)
            os.kill(os.getpid(), signal.SIGTERM)
            return fd

        def interrupt_handler(signum: int, _frame: object) -> None:
            raise driver._CommandInterrupted(signum)

        previous_handler = signal.signal(signal.SIGTERM, interrupt_handler)
        monkeypatch.setattr(driver, "_open_root_fd", interrupt_after_open)
        try:
            with pytest.raises(driver._CommandInterrupted):
                if operation == "admit":
                    _command_admit(private_root)
                else:
                    assert attempt is not None
                    driver.publish_command_artifact(
                        attempt, "terminal", encoded, root=private_root
                    )
        finally:
            signal.signal(signal.SIGTERM, previous_handler)

        assert len(opened) == 1
        try:
            os.fstat(opened[0])
        except OSError as exc:
            assert exc.errno == errno.EBADF
        else:
            os.close(opened[0])
            pytest.fail("root descriptor escaped its signal-ownership region")

    @pytest.mark.parametrize(
        ("command", "rehearsal"),
        (("static-preflight", False), ("rehearse", True)),
    )
    def test_quarantined_orphan_advances_the_next_disk_ordinal(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        command: str,
        rehearsal: bool,
    ) -> None:
        real_fsync = driver.os.fsync
        real_link = driver.os.link
        real_unlink = driver.os.unlink
        linked = False
        failed_parent_fsync = False
        failed_unlink = False

        def injected_link(*args: object, **kwargs: object) -> None:
            nonlocal linked
            real_link(*args, **kwargs)
            if str(args[1]).endswith("-admission.json"):
                linked = True

        def injected_fsync(fd: int) -> None:
            nonlocal failed_parent_fsync
            if linked and not failed_parent_fsync and stat.S_ISDIR(os.fstat(fd).st_mode):
                failed_parent_fsync = True
                raise OSError(errno.EIO, "trigger cleanup")
            real_fsync(fd)

        def injected_unlink(path: object, *args: object, **kwargs: object) -> None:
            nonlocal failed_unlink
            if str(path).startswith(".command-cleanup-") and not failed_unlink:
                failed_unlink = True
                raise OSError(errno.EIO, "leave quarantine")
            real_unlink(path, *args, **kwargs)

        monkeypatch.setattr(driver.os, "link", injected_link)
        monkeypatch.setattr(driver.os, "fsync", injected_fsync)
        monkeypatch.setattr(driver.os, "unlink", injected_unlink)

        with pytest.raises(driver.BenchRefusal, match="cleanup_incomplete"):
            _command_admit(
                private_root,
                command=command,
                rehearsal=rehearsal,
            )
        orphans = list(private_root.rglob(".command-cleanup-*"))
        assert len(orphans) == 1
        with pytest.raises(ValueError):
            driver.cm.PersistedDoc(orphans[0].read_bytes())

        monkeypatch.undo()
        policy_name = (
            "RehearsalArtifactPolicy" if rehearsal else "ProductionArtifactPolicy"
        )
        code = "\n".join(
            (
                "import json, sys",
                "from pathlib import Path",
                "from scripts import cuda_bench_driver as driver",
                "class Clock:",
                f"    tier = {('rehearsal' if rehearsal else 'production')!r}",
                f"    def now_utc(self): return {_COMMAND_TIMESTAMP!r}",
                "    def monotonic(self): return 0.0",
                f"policy = driver.{policy_name}()",
                f"attempt = driver._admit_command({command!r}, None, policy, Clock(), Path(sys.argv[1]))",
                "print(json.dumps({'ordinal': attempt.ordinal}))",
            )
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(private_root)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        assert result.returncode == 0
        assert result.stderr == ""
        assert json.loads(result.stdout) == {"ordinal": 2}

    def test_source_fd_close_failure_cannot_erase_a_constructed_binding(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_open_anonymous = driver._open_anonymous_file
        real_close = driver.os.close
        real_attempt_type = driver.CommandAttempt
        source_fd: int | None = None
        failed = False
        constructed: list[object] = []
        latched: list[object] = []

        def capture_source(*args: object, **kwargs: object) -> int:
            nonlocal source_fd
            source_fd = real_open_anonymous(*args, **kwargs)
            return source_fd

        def recording_attempt(*args: object, **kwargs: object) -> object:
            value = real_attempt_type(*args, **kwargs)
            constructed.append(value)
            return value

        def failing_close(fd: int) -> None:
            nonlocal failed
            if fd == source_fd and not failed:
                failed = True
                raise OSError(errno.EIO, "source close")
            real_close(fd)

        monkeypatch.setattr(driver, "_open_anonymous_file", capture_source)
        monkeypatch.setattr(driver, "CommandAttempt", recording_attempt)
        monkeypatch.setattr(driver.os, "close", failing_close)
        caught: BaseException | None = None
        try:
            driver._admit_command(
                "static-preflight",
                None,
                driver.ProductionArtifactPolicy(),
                _CommandClock("production"),
                private_root,
                _on_latched=latched.append,
            )
        except BaseException as exc:
            caught = exc
        finally:
            if source_fd is not None:
                try:
                    real_close(source_fd)
                except OSError:
                    pass

        assert failed is True
        assert caught is not None
        if constructed:
            assert latched == constructed
            attempt = constructed[0]
            admission = private_root / attempt.admission_ref
            assert admission.is_file()
            assert hashlib.sha256(admission.read_bytes()).hexdigest() == (
                attempt.admission_sha256
            )
        else:
            assert latched == []
            assert not list(private_root.glob("*-admission.json"))

    def test_cleanup_is_signal_protected_and_term_wins_priority(
        self, private_root: Path
    ) -> None:
        result = _run_dual_signal_publication_cleanup(private_root)
        assert result.returncode == 0
        assert result.stderr == ""
        assert json.loads(result.stdout) == {
            "injected": {"sigint": True, "sigterm": True},
            "kind": "interrupted",
            "signum": 15,
        }
        assert not list(private_root.rglob("*-terminal.json"))
        assert not list(private_root.rglob(".command-cleanup-*"))

    def test_terminal_cleanup_failure_dominates_mask_restore_failure(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempt = _command_admit(private_root)
        encoded = driver.ProductionArtifactPolicy().encode(
            "refusal", {"outcome": "assembly_refused"}
        )
        real_link = driver.os.link
        real_fsync = driver.os.fsync
        real_unlink = driver.os.unlink
        real_pthread_sigmask = driver.signal.pthread_sigmask
        terminal_linked = False
        durability_failed = False
        restore_failed = False

        def tracking_link(*args: object, **kwargs: object) -> None:
            nonlocal terminal_linked
            real_link(*args, **kwargs)
            if str(args[1]).endswith("-terminal.json"):
                terminal_linked = True

        def failing_fsync(fd: int) -> None:
            nonlocal durability_failed
            if (
                terminal_linked
                and not durability_failed
                and stat.S_ISDIR(os.fstat(fd).st_mode)
            ):
                durability_failed = True
                raise OSError(errno.EIO, "terminal durability")
            real_fsync(fd)

        def failing_unlink(path: object, *args: object, **kwargs: object) -> None:
            if str(path).startswith(".command-cleanup-"):
                raise OSError(errno.EIO, "identity cleanup")
            real_unlink(path, *args, **kwargs)

        def failing_restore(how: int, mask: object) -> object:
            nonlocal restore_failed
            if how == signal.SIG_SETMASK and not restore_failed:
                restore_failed = True
                raise OSError(errno.EIO, "mask restore")
            return real_pthread_sigmask(how, mask)

        monkeypatch.setattr(driver.os, "link", tracking_link)
        monkeypatch.setattr(driver.os, "fsync", failing_fsync)
        monkeypatch.setattr(driver.os, "unlink", failing_unlink)
        monkeypatch.setattr(driver.signal, "pthread_sigmask", failing_restore)

        with pytest.raises(driver.BenchRefusal, match="^cleanup_incomplete$"):
            driver.publish_command_artifact(
                attempt, "terminal", encoded, root=private_root
            )
        assert terminal_linked is True
        assert durability_failed is True
        assert restore_failed is True

    def test_concurrent_rehearsal_population_is_not_renamed_by_creator_cleanup(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_link = driver.os.link
        observed_identity: tuple[int, int] | None = None

        def failing_link(*args: object, **kwargs: object) -> None:
            nonlocal observed_identity
            if str(args[1]).endswith("-admission.json"):
                namespace = private_root / "rehearsal"
                info = namespace.stat()
                observed_identity = (info.st_dev, info.st_ino)

                def populate() -> None:
                    _private_file(namespace / "concurrent-artifact.json", b"peer\n")

                worker = threading.Thread(target=populate)
                worker.start()
                worker.join(timeout=5)
                assert not worker.is_alive()
                raise OSError(errno.EIO, "creator fails")
            real_link(*args, **kwargs)

        monkeypatch.setattr(driver.os, "link", failing_link)
        with pytest.raises(driver.BenchRefusal, match="cleanup_incomplete"):
            _command_admit(private_root, command="rehearse", rehearsal=True)

        namespace = private_root / "rehearsal"
        assert observed_identity is not None
        current = namespace.stat()
        assert (current.st_dev, current.st_ino) == observed_identity
        assert (namespace / "concurrent-artifact.json").read_bytes() == b"peer\n"
        assert not list(private_root.glob(".command-cleanup-*"))

    def test_peer_write_after_namespace_quarantine_stays_canonical(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_link = driver.os.link
        real_rename = driver.os.rename
        held_namespace_fd: int | None = None
        held_replacement_fd: int | None = None
        original_identity: tuple[int, int] | None = None
        replacement_identity: tuple[int, int] | None = None
        injected = False

        def failing_link(*args: object, **kwargs: object) -> None:
            nonlocal held_namespace_fd, original_identity
            if str(args[1]).endswith("-admission.json"):
                held_namespace_fd = os.open(
                    private_root / "rehearsal",
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                )
                observed = os.fstat(held_namespace_fd)
                original_identity = (observed.st_dev, observed.st_ino)
                assert os.listdir(held_namespace_fd) == []
                raise OSError(errno.EIO, "creator fails after empty precheck")
            real_link(*args, **kwargs)

        def populate_after_quarantine(
            source: object,
            target: object,
            *args: object,
            **kwargs: object,
        ) -> None:
            nonlocal held_replacement_fd, injected, replacement_identity
            real_rename(source, target, *args, **kwargs)
            if source != "rehearsal" or not str(target).startswith(
                ".command-cleanup-rehearsal-"
            ):
                return
            if injected:
                return
            assert held_namespace_fd is not None
            injected = True
            peer_fd = os.open(
                "peer.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=held_namespace_fd,
            )
            try:
                os.write(peer_fd, b"peer-evidence\n")
                os.fsync(peer_fd)
            finally:
                os.close(peer_fd)
            root_fd = int(kwargs["dst_dir_fd"])
            os.mkdir("rehearsal", mode=0o700, dir_fd=root_fd)
            held_replacement_fd = os.open(
                "rehearsal",
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root_fd,
            )
            replacement = os.fstat(held_replacement_fd)
            replacement_identity = (replacement.st_dev, replacement.st_ino)

        monkeypatch.setattr(driver.os, "link", failing_link)
        monkeypatch.setattr(driver.os, "rename", populate_after_quarantine)
        try:
            with pytest.raises(driver.BenchRefusal, match="^cleanup_incomplete$"):
                _command_admit(private_root, command="rehearse", rehearsal=True)
            assert held_replacement_fd is not None
            late_peer_fd = os.open(
                "late-peer.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=held_replacement_fd,
            )
            try:
                os.write(late_peer_fd, b"late-peer-evidence\n")
                os.fsync(late_peer_fd)
            finally:
                os.close(late_peer_fd)
            hidden_admission = driver.RehearsalArtifactPolicy().encode(
                "command_admission",
                {
                    "command": "rehearse",
                    "ordinal": 1,
                    "window_id": None,
                    "status": "admitted",
                    "timestamp": _COMMAND_TIMESTAMP,
                },
            )
            hidden_fd = os.open(
                "command-rehearse-attempt-001-admission.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=held_replacement_fd,
            )
            try:
                os.write(hidden_fd, hidden_admission)
                os.fsync(hidden_fd)
            finally:
                os.close(hidden_fd)
        finally:
            if held_namespace_fd is not None:
                os.close(held_namespace_fd)
            if held_replacement_fd is not None:
                os.close(held_replacement_fd)

        namespace = private_root / "rehearsal"
        current = namespace.stat()
        assert injected is True
        assert original_identity is not None
        assert replacement_identity is not None
        assert original_identity != replacement_identity
        assert (current.st_dev, current.st_ino) == original_identity
        assert (namespace / "peer.json").read_bytes() == b"peer-evidence\n"
        quarantines = list(private_root.glob(".command-cleanup-rehearsal-*"))
        assert len(quarantines) == 1
        quarantine = quarantines[0]
        quarantined = quarantine.stat()
        assert (quarantined.st_dev, quarantined.st_ino) == replacement_identity
        assert (quarantine / "late-peer.json").read_bytes() == b"late-peer-evidence\n"
        assert (
            quarantine / "command-rehearse-attempt-001-admission.json"
        ).read_bytes() == hidden_admission

        monkeypatch.setattr(driver.os, "link", real_link)
        monkeypatch.setattr(driver.os, "rename", real_rename)
        next_attempt = _command_admit(private_root)
        assert next_attempt.ordinal == 2

    def test_same_inode_same_length_mutation_never_returns_a_stale_attempt(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_checkpoint = driver._command_signal_checkpoint
        checkpoints = 0
        mutated = False
        before_identity: tuple[int, int, int] | None = None

        def mutate_after_first_hash() -> None:
            nonlocal before_identity, checkpoints, mutated
            real_checkpoint()
            checkpoints += 1
            if checkpoints != 4:
                return
            admission = next(private_root.glob("*-admission.json"))
            original = admission.read_bytes()
            changed = bytearray(original)
            changed[0] ^= 1
            info = admission.stat()
            before_identity = (info.st_dev, info.st_ino, info.st_size)
            fd = os.open(admission, os.O_WRONLY | os.O_NOFOLLOW)
            try:
                assert os.write(fd, changed) == len(changed)
                os.fsync(fd)
            finally:
                os.close(fd)
            mutated = True

        monkeypatch.setattr(driver, "_command_signal_checkpoint", mutate_after_first_hash)
        attempt: object | None = None
        caught: BaseException | None = None
        try:
            attempt = _command_admit(private_root)
        except BaseException as exc:
            caught = exc

        assert mutated is True
        assert before_identity is not None
        admission = next(private_root.rglob("*-admission.json"), None)
        if admission is not None:
            info = admission.stat()
            assert (info.st_dev, info.st_ino, info.st_size) == before_identity
        assert attempt is None
        assert isinstance(caught, driver.BenchRefusal)


class TestTask3ReviewAdmissionReplacementProofs:
    @pytest.mark.parametrize("target", ("root", "namespace", "admission"))
    def test_final_admission_revalidation_rejects_post_hash_replacement(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        target: str,
    ) -> None:
        real_checkpoint = driver._command_signal_checkpoint
        checkpoints = 0
        replaced = False
        displaced_root = private_root.with_name(f"{private_root.name}-observed")

        def replace_after_hash() -> None:
            nonlocal checkpoints, replaced
            real_checkpoint()
            checkpoints += 1
            if checkpoints != 4:
                return
            replaced = True
            if target == "root":
                private_root.rename(displaced_root)
                private_root.mkdir(mode=0o700)
                os.chmod(private_root, 0o700)
                return
            if target == "namespace":
                namespace = private_root / "rehearsal"
                namespace.rename(private_root / "observed-rehearsal")
                namespace.mkdir(mode=0o700)
                os.chmod(namespace, 0o700)
                return
            admission = next(private_root.glob("*-admission.json"))
            admission.rename(admission.with_name(f"observed-{admission.name}"))
            _private_file(admission, b"replacement-must-not-bind\n")

        monkeypatch.setattr(driver, "_command_signal_checkpoint", replace_after_hash)

        attempt: object | None = None
        caught: BaseException | None = None
        try:
            attempt = _command_admit(
                private_root,
                command="rehearse" if target == "namespace" else "static-preflight",
                rehearsal=target == "namespace",
            )
        except BaseException as exc:
            caught = exc

        assert replaced is True
        assert attempt is None
        assert isinstance(caught, driver.BenchRefusal)
        assert caught.code in {"filesystem_hazard", "cleanup_incomplete"}


_B7_SANITIZED_PATH = (
    "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
)


def _b7_production_environment(phase: str) -> dict[str, str]:
    common = {"HOME": "/home/rohit", "PATH": _B7_SANITIZED_PATH}
    if phase == "vulkan_baseline":
        return {
            **common,
            "LD_LIBRARY_PATH": str(driver.cm.VULKAN_RELEASE_ROOT),
            "GGML_VK_VISIBLE_DEVICES": "0",
            "CUDA_VISIBLE_DEVICES": "",
        }
    return {
        **common,
        "CUDA_VISIBLE_DEVICES": "0",
        "GGML_VK_VISIBLE_DEVICES": "",
        "LD_LIBRARY_PATH": (
            f"{driver.cm.CUDA_RELEASE_ROOT}:"
            f"{driver.cm.CUDA_TOOLKIT_LIBRARY_ROOT}"
        ),
    }


def _b7_production_contract_case(
    root: Path, phase: str
) -> tuple[
    driver.PhaseConfig,
    driver.SpawnPin,
    driver.cm.StaticPreflightDoc,
    driver.cm.RuntimeIdentity,
]:
    harness = _b7_harness(root)
    static_bytes = driver.open_bench_file(
        harness.config.static_preflight_path,
        root=root,
    )
    static = driver.cm.PersistedDoc(static_bytes).obj
    assert type(static) is driver.cm.StaticPreflightDoc
    identity = driver.cm.RuntimeIdentity(**harness.config.bench_identity_fields)
    executable = (
        driver.cm.VULKAN_RELEASE_ROOT / "llama-server"
        if phase == "vulkan_baseline"
        else driver.cm.CUDA_RELEASE_ROOT / "llama-server"
    )
    pin_sha256 = (
        static.checks["incumbent_server"]
        if phase == "vulkan_baseline"
        else identity.runtime_sha256
    )
    pin = driver.SpawnPin(
        kind="binary",
        pinned_path=executable,
        pinned_sha256=pin_sha256,
        required_argv_prefix=(str(executable),),
    )
    config = replace(
        harness.config,
        argv=[str(executable), *identity.effective_args],
        env=_b7_production_environment(phase),
        expected_port=driver.BENCH_PORT,
        readiness_timeout_s=driver.READINESS_TIMEOUT_S,
    )
    if phase == "cuda_candidate":
        window = _b7_authorization()
        continuation = driver.Continuation(
            window_id=window.window_id,
            phases=("cuda_candidate",),
            boot_id=window.boot_id,
            nonce="8" * 64,
            issued_at=window.issued_at,
            expires_at=(
                datetime.fromisoformat(window.issued_at.replace("Z", "+00:00"))
                + driver.timedelta(seconds=driver.CONTINUATION_TTL_S)
            ).isoformat().replace("+00:00", "Z"),
            owner=window.owner,
            parent_vulkan_packet_sha256="7" * 64,
        )
        config = replace(
            config,
            phase=phase,
            authorization=continuation,
            parent_window=window,
            parent_packet_path="packets/vulkan-parent.json",
        )
    return config, pin, static, identity


class TestB7SpecGateExecutionAuthority:
    @pytest.mark.parametrize("phase", ["vulkan_baseline", "cuda_candidate"])
    def test_true_stub_hash_and_exact_real_pin_reach_production_contract_without_spawn(
        self, private_root: Path, phase: str
    ) -> None:
        config, pin, static, identity = _b7_production_contract_case(
            private_root, phase
        )
        assert static.stub_sha256 == STUB_SHA256

        admitted = driver._validate_production_execution_contract(
            config,
            launcher_pin=pin,
            static=static,
            runtime_identity=identity,
        )

        assert admitted.pinned_path == str(pin.pinned_path)
        assert admitted.pinned_sha256 == pin.pinned_sha256
        assert admitted.effective_args_sha256 == driver.FROZEN_BENCH_ARGS_SHA256
        assert dict(admitted.environment) == config.env

    @pytest.mark.parametrize(
        "mutation",
        ["argv", "env", "port", "pin_path", "pin_sha256"],
    )
    def test_production_execution_mutation_refuses_before_authority_or_spawn(
        self, private_root: Path, mutation: str
    ) -> None:
        config, pin, static, identity = _b7_production_contract_case(
            private_root, "vulkan_baseline"
        )
        if mutation == "argv":
            argv = list(config.argv)
            argv[-1] = "on"
            config = replace(config, argv=argv)
        elif mutation == "env":
            config = replace(config, env={**config.env, "UNFROZEN": "1"})
        elif mutation == "port":
            config = replace(config, expected_port=18_081)
        elif mutation == "pin_path":
            pin = driver.SpawnPin(
                kind="binary",
                pinned_path=Path("/tmp/not-the-vulkan-binary"),
                pinned_sha256=pin.pinned_sha256,
                required_argv_prefix=("/tmp/not-the-vulkan-binary",),
            )
        else:
            pin = driver.SpawnPin(
                kind="binary",
                pinned_path=pin.pinned_path,
                pinned_sha256="f" * 64,
                required_argv_prefix=pin.required_argv_prefix,
            )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver._validate_production_execution_contract(
                config,
                launcher_pin=pin,
                static=static,
                runtime_identity=identity,
            )
        _assert_refusal(exc, "identity_mismatch")


class TestB7SpecGateContainmentAndFactories:
    def test_known_dirty_maez_states_are_representable_but_never_clean(self) -> None:
        active_flag_one = driver.cm.ContainmentSnapshot(
            phase="vulkan_baseline",
            boundary="before",
            timestamp="2026-07-16T12:00:00Z",
            screen_flag_value="0",
            active_state="inactive",
            substate="dead",
            enabled_state="disabled",
            maez_active_state="active",
            maez_process_screen_flag_value="1",
            port_closed=True,
            flag_source_sha256="a" * 64,
            vision_unit_sha256="b" * 64,
        )
        failed = replace(
            active_flag_one,
            maez_active_state="failed",
            maez_process_screen_flag_value=None,
        )

        assert active_flag_one.clean is False
        assert failed.clean is False

    def test_real_containment_returns_dirty_observation_for_persistence(self) -> None:
        vision = (
            "ActiveState=inactive\nSubState=dead\n"
            "UnitFileState=disabled\nMainPID=0\n"
        )
        maez = (
            "ActiveState=active\nSubState=running\n"
            "UnitFileState=enabled\nMainPID=7\n"
        )
        provider = driver.RealContainmentProvider(
            clock=driver.SystemClock(),
            port_probe=driver.SyntheticPortProbe({8082}),
            command_reader=lambda argv: maez if "maez.service" in argv else vision,
            file_reader=lambda path: (
                b"MAEZ_SCREEN_PERCEPTION=0\n"
                if path == driver.SCREEN_FLAG_SOURCE_PATH
                else b"unit"
            ),
            environ_reader=lambda _pid: b"MAEZ_SCREEN_PERCEPTION=1\0",
        )

        snapshot = provider.capture("vulkan_baseline", "before")

        assert snapshot.maez_process_screen_flag_value == "1"
        assert snapshot.clean is False

    def test_dirty_before_is_persisted_then_refused_before_consumption(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="3" * 64)
        real_capture = harness.containment.capture

        def dirty_capture(phase: str, boundary: str) -> object:
            snapshot = real_capture(phase, boundary)
            return (
                replace(snapshot, screen_flag_value="1")
                if boundary == "before"
                else snapshot
            )

        monkeypatch.setattr(harness.containment, "capture", dirty_capture)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)

        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == "containment_violation"
        assert fields["spawned"] is False
        attempt = path.parents[2]
        before_path = attempt / "rehearsal" / "containment" / "containment-before.json"
        assert before_path.is_file()
        persisted = json.loads(before_path.read_bytes())
        assert persisted["payload"]["fields"]["screen_flag_value"] == "1"
        assert not list(attempt.rglob("consumption-*.json"))

    def test_containment_before_hashes_join_static_before_consumption(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="2" * 64)
        real_capture = harness.containment.capture

        def drifted_capture(phase: str, boundary: str) -> object:
            snapshot = real_capture(phase, boundary)
            return (
                replace(snapshot, flag_source_sha256="f" * 64)
                if boundary == "before"
                else snapshot
            )

        monkeypatch.setattr(harness.containment, "capture", drifted_capture)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)

        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == "containment_violation"
        assert fields["spawned"] is False
        assert not list(path.parents[2].rglob("consumption-*.json"))

    def test_containment_after_hash_drift_writes_failed_packet(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="1" * 64)
        real_capture = harness.containment.capture

        def drifted_capture(phase: str, boundary: str) -> object:
            snapshot = real_capture(phase, boundary)
            return (
                replace(snapshot, vision_unit_sha256="f" * 64)
                if boundary == "after"
                else snapshot
            )

        monkeypatch.setattr(harness.containment, "capture", drifted_capture)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)

        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == "containment_violation"
        assert fields["spawned"] is True
        after_path = (
            path.parents[2]
            / "rehearsal"
            / "containment"
            / "containment-after.json"
        )
        assert after_path.is_file()

    def test_cycle_one_anchor_is_after_completed_gpu_sample(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="0" * 64)
        base = datetime.now(UTC).replace(microsecond=0)
        clock_calls = 0
        last_clock_before_first_memory: str | None = None
        real_memory = harness.gpu.memory

        def advancing_now(_clock: object) -> str:
            nonlocal clock_calls
            rendered = (base + driver.timedelta(microseconds=clock_calls)).isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z")
            clock_calls += 1
            return rendered

        def observed_memory(uuid: str) -> tuple[float, int]:
            nonlocal last_clock_before_first_memory
            if last_clock_before_first_memory is None:
                last_clock_before_first_memory = (
                    base + driver.timedelta(microseconds=clock_calls - 1)
                ).isoformat(timespec="microseconds").replace("+00:00", "Z")
            return real_memory(uuid)

        monkeypatch.setattr(driver.RehearsalClock, "now_utc", advancing_now)
        monkeypatch.setattr(harness.gpu, "memory", observed_memory)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)

        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == "completed"
        assert last_clock_before_first_memory is not None
        assert (
            driver.cm._compare_utc_z(
                fields["cycle_one_before_snapshot_at"],
                last_clock_before_first_memory,
            )
            > 0
        )

    @pytest.mark.parametrize("tier", ["production", "rehearsal"])
    @pytest.mark.parametrize(
        "field",
        [
            "service_state",
            "port_probe",
            "gpu",
            "kernel_log",
            "backend_maps",
            "artifact_policy",
            "clock",
            "journal_factory",
        ],
    )
    def test_factories_reject_same_tier_protocol_fakes(
        self, tier: str, field: str
    ) -> None:
        components = _provider_components(tier)
        components[field] = _TieredFake(tier)
        factory = driver.production_tier if tier == "production" else driver.rehearsal_tier

        with pytest.raises(driver.BenchRefusal) as exc:
            factory(**components)
        _assert_refusal(exc, "tier_mismatch")

    def test_production_factory_rejects_retagged_synthetic(self) -> None:
        class RetaggedSyntheticGpu(driver.SyntheticGpu):
            tier = "production"

        components = _provider_components("production")
        components["gpu"] = RetaggedSyntheticGpu([], [], [])

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.production_tier(**components)
        _assert_refusal(exc, "tier_mismatch")

    def test_rehearsal_expected_port_refuses_before_consume_or_spawn(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="6" * 64)
        config = replace(harness.config, expected_port=driver.BENCH_PORT)
        consume_calls = 0
        spawn_calls = 0
        real_consume = driver.RehearsalAuthorizationGate.consume
        real_spawn = driver.RehearsalServerLauncher.spawn

        def counted_consume(
            gate: object, *args: object, **kwargs: object
        ) -> object:
            nonlocal consume_calls
            consume_calls += 1
            return real_consume(gate, *args, **kwargs)

        def counted_spawn(
            launcher: driver.RehearsalServerLauncher,
            *args: object,
            **kwargs: object,
        ) -> object:
            nonlocal spawn_calls
            spawn_calls += 1
            return real_spawn(launcher, *args, **kwargs)

        monkeypatch.setattr(driver.RehearsalAuthorizationGate, "consume", counted_consume)
        monkeypatch.setattr(driver.RehearsalServerLauncher, "spawn", counted_spawn)
        path = driver.run_phase(config, harness.providers, root=private_root)

        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == "identity_mismatch"
        assert consume_calls == 0
        assert spawn_calls == 0
        assert not list(private_root.rglob("consumption-*.json"))

    @pytest.mark.parametrize("phase", ["vulkan_baseline", "cuda_candidate"])
    def test_authorization_window_must_join_config_window(
        self, phase: str
    ) -> None:
        window, continuation, parent = _cuda_authorities()
        authority: object = window if phase == "vulkan_baseline" else continuation
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.validate_authorization(
                authority,
                phase=phase,
                boot_id="boot-1",
                expected_window_id="foreign-window",
                parent_window=window if phase == "cuda_candidate" else None,
                parent_packet=parent if phase == "cuda_candidate" else None,
                clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
            )
        _assert_refusal(exc, "authorization_scope_mismatch")

    def test_authorization_window_defines_attempt_scope_before_any_write(
        self, private_root: Path
    ) -> None:
        harness = _b7_harness(private_root, nonce="5" * 64)
        config = replace(harness.config, window_id="foreign-window")

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.run_phase(config, harness.providers, root=private_root)

        _assert_refusal(exc, "authorization_scope_mismatch")
        assert not (private_root / "windows").exists()

    def test_authorization_boot_mismatch_refuses_before_any_write(
        self, private_root: Path
    ) -> None:
        harness = _b7_harness(private_root, nonce="4" * 64)
        config = replace(harness.config, boot_id="foreign-boot")

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.run_phase(config, harness.providers, root=private_root)

        _assert_refusal(exc, "authorization_boot_mismatch")
        assert not (private_root / "windows").exists()

    def test_expiry_during_receipt_encode_is_revalidated_before_marker(
        self, private_root: Path
    ) -> None:
        class MutableClock:
            tier = "production"

            def __init__(self) -> None:
                self.now = "2026-07-14T11:30:00Z"

            def now_utc(self) -> str:
                return self.now

            def monotonic(self) -> float:
                return 0.0

        class ExpiringPolicy:
            tier = "production"

            def encode(self, kind: str, document: dict[str, object]) -> bytes:
                encoded = driver.ProductionArtifactPolicy().encode(kind, document)
                clock.now = authorization.expires_at
                return encoded

            def artifact_dir(self, kind: str) -> str:
                return driver.ProductionArtifactPolicy().artifact_dir(kind)

        authorization = driver.WindowAuthorization(
            **{
                **_window_fields(),
                "phases": ("vulkan_baseline",),
            }  # type: ignore[arg-type]
        )
        clock = MutableClock()
        attempt_root = private_root / "attempt"
        attempt_root.mkdir(mode=0o700)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.consume_authorization(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-1",
                expected_window_id="window-1",
                clock=clock,
                authority_root=private_root,
                receipt_root=attempt_root,
                policy=ExpiringPolicy(),
                parent_window=None,
                parent_packet=None,
            )
        _assert_refusal(exc, "authorization_expired")
        assert not (private_root / "markers").exists()
        assert not (attempt_root / "receipts").exists()

    def test_consumption_wrapper_round_trips_object_binding_and_tamper_refuses(
        self, private_root: Path
    ) -> None:
        authorization = driver.WindowAuthorization(
            **{
                **_window_fields(),
                "phases": ("vulkan_baseline",),
            }  # type: ignore[arg-type]
        )
        attempt_root = private_root / "attempt"
        attempt_root.mkdir(mode=0o700)
        consumed = driver.consume_authorization(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-1",
            expected_window_id="window-1",
            clock=driver.FrozenClock("2026-07-14T11:30:00Z"),
            authority_root=private_root,
            receipt_root=attempt_root,
            policy=driver.ProductionArtifactPolicy(),
            parent_window=None,
            parent_packet=None,
        )
        receipt_path = next((attempt_root / "receipts").glob("*.json"))
        persisted = driver.cm.PersistedDoc(receipt_path.read_bytes())
        assert type(persisted.obj) is driver.cm.ConsumptionReceipt
        assert persisted.obj.binding_sha256 == consumed.consumption_receipt_sha256

        wrapper = json.loads(receipt_path.read_bytes())
        wrapper["fields"]["timestamp"] = "2026-07-14T11:31:00Z"
        tampered = (
            json.dumps(wrapper, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        with pytest.raises(ValueError, match="persisted_roundtrip"):
            driver.cm.PersistedDoc(tampered)

    def test_driver_permits_stage_mode_difference_and_cites_bench_identity_file(
        self, private_root: Path
    ) -> None:
        from tests.test_cuda_migration import PersistedDocTests, argv, make_identity

        harness = _b7_harness(private_root)
        current = make_identity(mode="production", effective_args=argv("8080"))
        current_fields = PersistedDocTests.identity_fields(current)
        current_fields["effective_args"] = tuple(current_fields["effective_args"])
        config = replace(harness.config, runtime_identity_fields=current_fields)
        attempt_root = private_root / "identity-attempt"
        attempt_root.mkdir(mode=0o700)

        loaded = driver._load_phase_preimages(
            config,
            harness.providers,
            root=private_root,
            attempt_root=attempt_root,
        )

        bench_path = (
            attempt_root
            / "rehearsal"
            / "identity"
            / "bench_runtime_identity.json"
        )
        runtime_path = attempt_root / "rehearsal" / "identity" / "runtime_identity.json"
        assert loaded[-1] == hashlib.sha256(bench_path.read_bytes()).hexdigest()
        assert runtime_path.is_file()
        assert bench_path.read_bytes() != runtime_path.read_bytes()

    def test_driver_rejects_stable_identity_field_drift(self, private_root: Path) -> None:
        from tests.test_cuda_migration import PersistedDocTests, make_identity

        harness = _b7_harness(private_root)
        drifted = make_identity(library_hashes={"libggml-cuda.so": "f" * 64})
        drifted_fields = PersistedDocTests.identity_fields(drifted)
        drifted_fields["effective_args"] = tuple(drifted_fields["effective_args"])
        config = replace(harness.config, runtime_identity_fields=drifted_fields)
        attempt_root = private_root / "identity-attempt"
        attempt_root.mkdir(mode=0o700)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver._load_phase_preimages(
                config,
                harness.providers,
                root=private_root,
                attempt_root=attempt_root,
            )
        _assert_refusal(exc, "identity_mismatch")

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


class _ScriptedHttpSocket:
    def __init__(self) -> None:
        self.timeouts: list[float] = []

    def settimeout(self, timeout: float) -> None:
        self.timeouts.append(timeout)


class _ScriptedHttpResponse:
    def __init__(
        self,
        clock: driver.FrozenClock,
        reads: list[tuple[float, bytes]],
        *,
        status: int = 200,
        content_type: str = "text/event-stream",
        close_when_reads_exhausted: bool = False,
        headers: list[tuple[str, str]] | None = None,
    ) -> None:
        self._clock = clock
        self._reads = list(reads)
        self.status = status
        self._content_type = content_type
        self._headers = list(
            headers
            if headers is not None
            else [("Content-Type", content_type)]
        )
        self.will_close = True
        self._close_when_reads_exhausted = close_when_reads_exhausted
        self.closed = False

    def getheader(self, name: str, default: str | None = None) -> str | None:
        values = [value for key, value in self._headers if key.lower() == name.lower()]
        if values:
            return ", ".join(values)
        return default

    def getheaders(self) -> list[tuple[str, str]]:
        return list(self._headers)

    def read1(self, _amount: int) -> bytes:
        if not self._reads:
            return b""
        delay, payload = self._reads.pop(0)
        self._clock.advance(delay)
        return payload

    def close(self) -> None:
        self.closed = True

    def isclosed(self) -> bool:
        return self._close_when_reads_exhausted and not self._reads


class _ScriptedHttpConnection:
    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
        *,
        clock: driver.FrozenClock,
        response: _ScriptedHttpResponse,
        endheaders_delay: float = 0.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.clock = clock
        self.response = response
        self.endheaders_delay = endheaders_delay
        self.sock = _ScriptedHttpSocket()
        self.request: tuple[str, str] | None = None
        self.headers: list[tuple[str, str]] = []
        self.body: bytes | None = None
        self.closed = False

    def connect(self) -> None:
        return

    def putrequest(self, method: str, path: str, **_kwargs: object) -> None:
        self.request = (method, path)

    def putheader(self, name: str, value: str) -> None:
        self.headers.append((name, value))

    def endheaders(self, body: bytes | None = None) -> None:
        self.clock.advance(self.endheaders_delay)
        self.body = body

    def getresponse(self) -> _ScriptedHttpResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


def _scripted_connection_factory(
    clock: driver.FrozenClock,
    reads: list[tuple[float, bytes]],
    *,
    endheaders_delay: float = 0.0,
    close_when_reads_exhausted: bool = False,
) -> tuple[Callable[..., _ScriptedHttpConnection], list[_ScriptedHttpConnection]]:
    connections: list[_ScriptedHttpConnection] = []
    response = _ScriptedHttpResponse(
        clock,
        reads,
        close_when_reads_exhausted=close_when_reads_exhausted,
    )

    def factory(host: str, port: int, timeout: float) -> _ScriptedHttpConnection:
        connection = _ScriptedHttpConnection(
            host,
            port,
            timeout,
            clock=clock,
            response=response,
            endheaders_delay=endheaders_delay,
        )
        connections.append(connection)
        return connection

    return factory, connections


class _LocalHttpScript:
    def __init__(
        self,
        *,
        health_status: int = 200,
        health_body: bytes = b'{"status":"ok"}',
        models_status: int = 200,
        models_body: bytes = b'{"data":[{"id":"qwen36-27b-mtp"}]}',
        completion_status: int = 200,
        completion_body: bytes = (
            b'data: {"content":"stub response","stop":false}\n\n'
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":true,"timings":{}}\n\n'
        ),
        completion_chunks: list[tuple[float, bytes]] | None = None,
        completion_headers: list[tuple[str, str]] | None = None,
        health_content_length: int | None = None,
        completion_content_length: int | None = None,
        redirect_to: str | None = None,
    ) -> None:
        self.health_status = health_status
        self.health_body = health_body
        self.models_status = models_status
        self.models_body = models_body
        self.completion_status = completion_status
        self.completion_body = completion_body
        self.completion_chunks = completion_chunks
        self.completion_headers = list(completion_headers or [])
        self.health_content_length = health_content_length
        self.completion_content_length = completion_content_length
        self.redirect_to = redirect_to
        self.hits: list[tuple[str, str]] = []


class _LocalHttpServer(ThreadingHTTPServer):
    script: _LocalHttpScript


class _LocalHttpHandler(BaseHTTPRequestHandler):
    server: _LocalHttpServer

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        content_length: int | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header(
            "Content-Length",
            str(len(body) if content_length is None else content_length),
        )
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_GET(self) -> None:  # noqa: N802
        self.server.script.hits.append(("GET", self.path))
        if self.path == "/health":
            self._send(
                self.server.script.health_status,
                self.server.script.health_body,
                "application/json",
                content_length=self.server.script.health_content_length,
            )
            return
        if self.path == "/v1/models":
            self._send(
                self.server.script.models_status,
                self.server.script.models_body,
                "application/json",
            )
            return
        self._send(404, b"{}", "application/json")

    def do_POST(self) -> None:  # noqa: N802
        self.server.script.hits.append(("POST", self.path))
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.server.script.redirect_to is not None:
            self.send_response(302)
            self.send_header("Location", self.server.script.redirect_to)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.server.script.completion_chunks is not None:
            chunks = self.server.script.completion_chunks
            self.send_response(self.server.script.completion_status)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header(
                "Content-Length",
                str(sum(len(payload) for _delay, payload in chunks)),
            )
            for name, value in self.server.script.completion_headers:
                self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
            for delay, payload in chunks:
                time.sleep(delay)
                try:
                    self.wfile.write(payload)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
            return
        self._send(
            self.server.script.completion_status,
            self.server.script.completion_body,
            "text/event-stream",
            content_length=self.server.script.completion_content_length,
        )


class _ServingLocalHttp(AbstractContextManager[tuple[_LocalHttpScript, int]]):
    def __init__(self, script: _LocalHttpScript) -> None:
        self.script = script
        self.server = _LocalHttpServer(("127.0.0.1", 0), _LocalHttpHandler)
        self.server.script = script
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> tuple[_LocalHttpScript, int]:
        self.thread.start()
        return self.script, int(self.server.server_address[1])

    def __exit__(self, *exc_info: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        assert not self.thread.is_alive()


class TestB6StreamingTiming:
    def test_owner_interrupt_from_clock_is_never_retyped(self) -> None:
        class InterruptClock:
            tier = "rehearsal"

            def now_utc(self) -> str:
                return "2026-07-15T12:00:00Z"

            def monotonic(self) -> float:
                raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=InterruptClock(),
            )

    def test_cleanup_closes_every_resource_then_reraises_base_exception(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")

        class InterruptingResponse(_ScriptedHttpResponse):
            def close(self) -> None:
                self.closed = True
                raise KeyboardInterrupt

        response = InterruptingResponse(
            clock,
            [(0.010, b"data: private malformed sentinel\n\n")],
        )
        connections: list[_ScriptedHttpConnection] = []

        def factory(host: str, port: int, timeout: float) -> _ScriptedHttpConnection:
            connection = _ScriptedHttpConnection(
                host,
                port,
                timeout,
                clock=clock,
                response=response,
            )
            connections.append(connection)
            return connection

        with pytest.raises(KeyboardInterrupt):
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                connection_factory=factory,
            )

        assert response.closed
        assert connections[0].closed

    def test_post_connect_setup_failure_closes_acquired_connection(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")

        class FailingSocket:
            def settimeout(self, _timeout: float) -> None:
                raise OSError("PRIVATE-TIMEOUT-SETUP-SENTINEL")

        class Connection:
            def __init__(self, _host: str, _port: int, _timeout: float) -> None:
                self.sock = FailingSocket()
                self.connected = False
                self.closed = False

            def connect(self) -> None:
                self.connected = True

            def close(self) -> None:
                self.closed = True

        connections: list[Connection] = []

        def factory(host: str, port: int, timeout: float) -> Connection:
            connection = Connection(host, port, timeout)
            connections.append(connection)
            return connection

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                connection_factory=factory,
            )

        _assert_refusal(exc, "malformed_response")
        assert connections[0].connected
        assert connections[0].closed
        assert "PRIVATE-TIMEOUT-SETUP-SENTINEL" not in str(exc.value)

    def test_post_connect_owner_interrupt_closes_before_propagating(self) -> None:
        class InterruptingClock:
            tier = "rehearsal"

            def __init__(self) -> None:
                self.calls = 0

            def monotonic(self) -> float:
                self.calls += 1
                if self.calls == 3:
                    raise KeyboardInterrupt
                return 0.0

            def now_utc(self) -> str:
                return "2026-07-15T12:00:00Z"

        class Connection:
            def __init__(self, _host: str, _port: int, _timeout: float) -> None:
                self.sock = _ScriptedHttpSocket()
                self.connected = False
                self.closed = False

            def connect(self) -> None:
                self.connected = True

            def close(self) -> None:
                self.closed = True

        connections: list[Connection] = []

        def factory(host: str, port: int, timeout: float) -> Connection:
            connection = Connection(host, port, timeout)
            connections.append(connection)
            return connection

        with pytest.raises(KeyboardInterrupt):
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=InterruptingClock(),
                connection_factory=factory,
            )

        assert connections[0].connected
        assert connections[0].closed

    def test_oversized_clock_number_is_provider_uncertain(self) -> None:
        class OversizedClock:
            tier = "rehearsal"

            def monotonic(self) -> int:
                return 10**1_000

            def now_utc(self) -> str:
                return "2026-07-15T12:00:00Z"

        with pytest.raises(driver.BenchRefusal) as exc:
            driver._monotonic(OversizedClock())  # noqa: SLF001 - provider seam

        _assert_refusal(exc, "provider_uncertain")

    def test_completion_header_arrival_after_deadline_is_http_timeout(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        response = _ScriptedHttpResponse(
            clock,
            [],
            status=500,
        )

        class DelayedHeadersConnection(_ScriptedHttpConnection):
            def getresponse(self) -> _ScriptedHttpResponse:
                clock.advance(0.200)
                return super().getresponse()

        def factory(host: str, port: int, timeout: float) -> _ScriptedHttpConnection:
            return DelayedHeadersConnection(
                host,
                port,
                timeout,
                clock=clock,
                response=response,
            )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                request_timeout_ms=100,
                connection_factory=factory,
            )

        _assert_refusal(exc, "http_timeout")

    @pytest.mark.parametrize(
        "extra_header",
        [
            ("Content-Length", "999"),
            ("Transfer-Encoding", "identity"),
            ("Transfer-Encoding", "chunked"),
        ],
    )
    def test_raw_loopback_rejects_ambiguous_response_framing(
        self, extra_header: tuple[str, str]
    ) -> None:
        script = _LocalHttpScript(
            completion_chunks=[
                (
                    0.0,
                    b'data: {"content":"stub response","stop":false}\n\n'
                    b'data: {"content":"","prompt":"private prompt sentinel",'
                    b'"stop":true,"timings":{}}\n\n',
                )
            ],
            completion_headers=[extra_header],
        )
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(script) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.stream(port, "private prompt sentinel")

        _assert_refusal(exc, "malformed_response")
        assert "private prompt sentinel" not in str(exc.value)

    def test_raw_loopback_rejects_short_declared_completion_body(self) -> None:
        body = (
            b'data: {"content":"private generated sentinel","stop":false}\n\n'
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":true,"timings":{}}\n\n'
        )
        script = _LocalHttpScript(
            completion_body=body,
            completion_content_length=len(body) + 8,
        )
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(script) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.stream(port, "private prompt sentinel")

        _assert_refusal(exc, "malformed_response")
        assert "private" not in str(exc.value)

    def test_completion_rejects_duplicate_json_keys(self) -> None:
        body = (
            b'data: {"content":"private generated sentinel","stop":false}\n\n'
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":false,"stop":true,"timings":{}}\n\n'
        )
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(
            _LocalHttpScript(completion_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.stream(port, "private prompt sentinel")

        _assert_refusal(exc, "malformed_response")
        assert "private" not in str(exc.value)

    @pytest.mark.parametrize("nonfinite", [b"NaN", b"1e9999"])
    def test_completion_rejects_nonfinite_json_numbers(
        self, nonfinite: bytes
    ) -> None:
        body = (
            b'data: {"content":"private generated sentinel","stop":false}\n\n'
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":true,"timings":{},"ignored":'
            + nonfinite
            + b"}\n\n"
        )
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(
            _LocalHttpScript(completion_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.stream(port, "private prompt sentinel")

        _assert_refusal(exc, "malformed_response")
        assert "private" not in str(exc.value)

    def test_completion_maps_recursive_json_failure_to_typed_refusal(self) -> None:
        nested = b"[" * 100_000 + b"0" + b"]" * 100_000
        body = (
            b'data: {"content":"private generated sentinel","stop":false}\n\n'
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":true,"timings":{},"ignored":'
            + nested
            + b"}\n\n"
        )
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(
            _LocalHttpScript(completion_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.stream(port, "private prompt sentinel")

        _assert_refusal(exc, "malformed_response")

    def test_event_after_terminal_is_rejected_without_moving_e2e_to_eof(
        self,
    ) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        content = b'data: {"content":"private generated sentinel","stop":false}\n\n'
        terminal = (
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":true,"timings":{}}\n\n'
        )
        trailing_comment = b": post-terminal comment\n\n"
        factory, _connections = _scripted_connection_factory(
            clock,
            [
                (0.100, content),
                (0.100, terminal),
                (0.500, trailing_comment),
                (0.100, b""),
            ],
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                connection_factory=factory,
            )

        _assert_refusal(exc, "malformed_response")

    def test_completion_rejects_lone_surrogate_json_string(self) -> None:
        body = (
            b'data: {"content":"\\ud800","stop":false}\n\n'
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":true,"timings":{}}\n\n'
        )
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(
            _LocalHttpScript(completion_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.stream(port, "private prompt sentinel")

        _assert_refusal(exc, "malformed_response")

    def test_byte_arrivals_define_ttft_and_e2e_and_post_shape_is_exact(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        prompt = "private prompt sentinel"
        generated = "private generated sentinel"
        metadata = b'data: {"content":"","stop":false}\n\n'
        content = (
            b'data: {"content":"private generated sentinel","stop":false}\n\n'
        )
        # b9596 native final framing is pinned by:
        # server-context.cpp:4329-4338,3894-3908; server-task.cpp:752-774.
        terminal = (
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":true,"timings":{"draft_n":12,"draft_n_accepted":9}}\n\n'
        )
        factory, connections = _scripted_connection_factory(
            clock,
            [
                (0.050, metadata),
                (0.150, content),
                (0.200, terminal),
                (0.900, b""),
            ],
            endheaders_delay=0.100,
        )

        result = driver.stream_completion(
            43210,
            prompt,
            clock=clock,
            connection_factory=factory,
        )

        assert result.ttft_ms == pytest.approx(200.0)
        assert result.e2e_ms == pytest.approx(400.0)
        assert result.content == generated
        assert result.timings == {"draft_n": 12, "draft_n_accepted": 9}
        assert result.terminal["prompt"] == prompt
        assert len(connections) == 1
        connection = connections[0]
        assert connection.host == "127.0.0.1"
        assert connection.port == 43210
        assert connection.request == ("POST", "/completion")
        assert connection.body == b'{"prompt":"private prompt sentinel","stream":true}'
        assert dict(connection.headers) == {
            "Accept": "text/event-stream",
            "Content-Length": str(len(connection.body)),
            "Content-Type": "application/json",
        }
        assert connection.response.closed
        assert connection.closed

    def test_json_parsing_delay_does_not_move_stored_content_arrival(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        factory, _connections = _scripted_connection_factory(
            clock,
            [
                (0.050, b'data: {"content":"","stop":false}\n\n'),
                (
                    0.150,
                    b'data: {"content":"private generated sentinel",'
                    b'"stop":false}\n\n',
                ),
                (
                    0.200,
                    b'data: {"content":"","prompt":"private prompt sentinel",'
                    b'"stop":true,"timings":{}}\n\n',
                ),
                (0.800, b""),
            ],
            endheaders_delay=0.100,
        )
        real_loads = json.loads

        def slow_loads(payload: object, *args: object, **kwargs: object) -> object:
            clock.advance(1.0)
            return real_loads(payload, *args, **kwargs)

        monkeypatch.setattr(driver.json, "loads", slow_loads)

        result = driver.stream_completion(
            43210,
            "private prompt sentinel",
            clock=clock,
            request_timeout_ms=10_000,
            connection_factory=factory,
        )

        assert result.ttft_ms == pytest.approx(1_200.0)
        assert result.e2e_ms == pytest.approx(2_400.0)

    def test_fast_close_cannot_bypass_deadline_after_hostile_parsing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        one_chunk = (
            b'data: {"content":"private generated sentinel","stop":false}\n\n'
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":true,"timings":{}}\n\n'
        )
        factory, _connections = _scripted_connection_factory(
            clock,
            [(0.020, one_chunk)],
            close_when_reads_exhausted=True,
        )
        real_loads = json.loads

        def slow_loads(payload: object, *args: object, **kwargs: object) -> object:
            clock.advance(0.060)
            return real_loads(payload, *args, **kwargs)

        monkeypatch.setattr(driver.json, "loads", slow_loads)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                request_timeout_ms=100,
                connection_factory=factory,
            )

        _assert_refusal(exc, "http_timeout")
        assert "private prompt sentinel" not in str(exc.value)

    def test_same_chunk_content_and_terminal_allows_equal_timings(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        one_chunk = (
            b'data: {"content":"private generated sentinel","stop":false}\n\n'
            b'data: {"content":"","prompt":"private prompt sentinel",'
            b'"stop":true,"timings":{}}\n\n'
        )
        factory, _connections = _scripted_connection_factory(
            clock,
            [(0.250, one_chunk), (0.500, b"")],
        )

        result = driver.stream_completion(
            43210,
            "private prompt sentinel",
            clock=clock,
            connection_factory=factory,
        )

        assert result.ttft_ms == pytest.approx(250.0)
        assert result.e2e_ms == pytest.approx(250.0)
        assert result.ttft_ms <= result.e2e_ms

    def test_absolute_deadline_rejects_continuous_trickle(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        factory, connections = _scripted_connection_factory(
            clock,
            [
                (0.040, b"data: {"),
                (0.040, b'"slot_id":0'),
                (0.040, b"}\n\n"),
            ],
        )
        secret = "private timeout prompt sentinel"

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                secret,
                clock=clock,
                request_timeout_ms=100,
                connection_factory=factory,
            )

        _assert_refusal(exc, "http_timeout")
        assert secret not in str(exc.value)
        assert connections[0].response.closed
        assert connections[0].closed
        assert len(connections[0].sock.timeouts) >= 2

    def test_done_is_a_wrong_endpoint_signal_even_after_a_terminal_event(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        secret = "private response sentinel"
        factory, _connections = _scripted_connection_factory(
            clock,
            [
                (
                    0.010,
                    (
                        f'data: {{"content":"{secret}","stop":false}}\n\n'
                        'data: {"content":"","prompt":"private prompt sentinel",'
                        '"stop":true,"timings":{}}\n\n'
                        "data: [DONE]\n\n"
                    ).encode(),
                )
            ],
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                connection_factory=factory,
            )

        _assert_refusal(exc, "malformed_response")
        assert secret not in str(exc.value)
        assert "private prompt sentinel" not in str(exc.value)

    def test_clean_eof_without_stop_true_is_a_truncated_stream(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        factory, _connections = _scripted_connection_factory(
            clock,
            [
                (
                    0.010,
                    b'data: {"content":"private partial sentinel",'
                    b'"stop":false}\n\n',
                ),
                (0.010, b""),
            ],
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                connection_factory=factory,
            )

        _assert_refusal(exc, "malformed_response")
        assert "private partial sentinel" not in str(exc.value)

    def test_stop_false_timings_cannot_anchor_e2e(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        factory, _connections = _scripted_connection_factory(
            clock,
            [
                (
                    0.100,
                    b'data: {"content":"private generated sentinel",'
                    b'"stop":false,"timings":{"prompt_n":1}}\n\n',
                ),
                (
                    0.300,
                    b'data: {"content":"","prompt":"private prompt sentinel",'
                    b'"stop":true,"timings":{"draft_n":12,'
                    b'"draft_n_accepted":9}}\n\n',
                ),
                (0.900, b""),
            ],
        )

        result = driver.stream_completion(
            43210,
            "private prompt sentinel",
            clock=clock,
            connection_factory=factory,
        )

        assert result.ttft_ms == pytest.approx(100.0)
        assert result.e2e_ms == pytest.approx(400.0)
        assert result.timings == {"draft_n": 12, "draft_n_accepted": 9}

    def test_detokenized_terminal_prompt_is_not_false_compared_to_request(self) -> None:
        # b9596's own test_completion.py:430 witnesses a BOS-prefixed terminal
        # prompt; server-context.cpp:1838 builds it by detokenizing tokens.
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        factory, _connections = _scripted_connection_factory(
            clock,
            [
                (
                    0.100,
                    b'data: {"content":"private generated sentinel",'
                    b'"stop":false}\n\n',
                ),
                (
                    0.100,
                    b'data: {"content":"","prompt":"<s> private prompt sentinel",'
                    b'"stop":true,"timings":{}}\n\n',
                ),
                (0.100, b""),
            ],
        )

        result = driver.stream_completion(
            43210,
            "private prompt sentinel",
            clock=clock,
            connection_factory=factory,
        )

        assert result.terminal["prompt"] == "<s> private prompt sentinel"

    def test_malformed_sse_never_appears_in_refusal(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        secret = b"private malformed body sentinel"
        factory, _connections = _scripted_connection_factory(
            clock,
            [(0.010, b"data: " + secret + b"\n\n")],
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                connection_factory=factory,
            )

        _assert_refusal(exc, "malformed_response")
        assert secret.decode() not in str(exc.value)

    def test_stub_style_terminal_then_eof_is_valid(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        factory, _connections = _scripted_connection_factory(
            clock,
            [
                (
                    0.020,
                    b'data: {"content":"stub response","stop":false}\n\n'
                    b'data: {"content":"","prompt":"private prompt sentinel",'
                    b'"stop":true,"timings":'
                    b'{"draft_n":12,"draft_n_accepted":9}}\n\n',
                ),
                (0.010, b""),
            ],
        )

        result = driver.stream_completion(
            43210,
            "private prompt sentinel",
            clock=clock,
            connection_factory=factory,
        )

        assert result.content == "stub response"
        assert result.ttft_ms == pytest.approx(20.0)
        assert result.e2e_ms == pytest.approx(20.0)

    def test_completion_response_cap_is_typed_and_body_is_private(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        factory, _connections = _scripted_connection_factory(
            clock,
            [(0.010, b"S" * (driver.RESPONSE_BYTE_CAP + 1))],
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                connection_factory=factory,
            )

        _assert_refusal(exc, "response_too_large")
        assert "SSSS" not in str(exc.value)

    def test_redirect_status_is_refused_without_second_connection(self) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        factory, connections = _scripted_connection_factory(clock, [],)
        connections_response = _ScriptedHttpResponse(
            clock,
            [],
            status=302,
            content_type="text/plain",
        )

        def redirect_factory(
            host: str, port: int, timeout: float
        ) -> _ScriptedHttpConnection:
            connection = _ScriptedHttpConnection(
                host,
                port,
                timeout,
                clock=clock,
                response=connections_response,
            )
            connections.append(connection)
            return connection

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.stream_completion(
                43210,
                "private prompt sentinel",
                clock=clock,
                connection_factory=redirect_factory,
            )

        _assert_refusal(exc, "malformed_response")
        assert len(connections) == 1


class TestB6LoopbackEndpoints:
    def test_rehearsal_transport_clock_advances_with_real_time(self) -> None:
        clock = driver.RehearsalClock()
        before = clock.monotonic()
        time.sleep(0.010)
        assert clock.monotonic() > before

    def test_real_trickle_cannot_refresh_the_absolute_deadline(self) -> None:
        script = _LocalHttpScript(
            completion_chunks=[
                (0.020, b"data: {"),
                (0.020, b'"content":"private'),
                (0.020, b' sentinel","stop":false}\n\n'),
                (
                    0.020,
                    b'data: {"content":"","prompt":"private prompt sentinel",'
                    b'"stop":true,"timings":{}}\n\n',
                ),
            ]
        )
        clock = driver.RehearsalClock()
        client = driver.LoopbackServerClient.rehearsal(
            clock,
            request_timeout_ms=50,
        )
        with _ServingLocalHttp(script) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.stream(port, "private prompt sentinel")
        _assert_refusal(exc, "http_timeout")
    def test_health_and_models_use_literal_loopback_without_dns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = driver.RehearsalClock()
        client = driver.LoopbackServerClient.rehearsal(clock)
        script = _LocalHttpScript()

        with _ServingLocalHttp(script) as (observed, port):
            monkeypatch.setattr(
                socket,
                "getaddrinfo",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("DNS must be structurally unreachable")
                ),
            )
            assert client.health(port) is True
            assert client.models(port) == ["qwen36-27b-mtp"]

        assert observed.hits == [("GET", "/health"), ("GET", "/v1/models")]

    def test_models_accepts_the_b9596_outer_document_shape(self) -> None:
        # b9596 tools/server/server-context.cpp:4503-4532 adds models/object
        # alongside the authoritative OpenAI-compatible data rows.
        body = json.dumps(
            {
                "models": [{"name": "qwen36-27b-mtp"}],
                "object": "list",
                "data": [
                    {
                        "id": "qwen36-27b-mtp",
                        "object": "model",
                        "owned_by": "llamacpp",
                    }
                ],
            },
            separators=(",", ":"),
        ).encode()
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())
        with _ServingLocalHttp(
            _LocalHttpScript(models_body=body)
        ) as (_script, port):
            assert client.models(port) == ["qwen36-27b-mtp"]

    def test_ordinary_unready_health_is_false_not_a_typed_refusal(self) -> None:
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())
        with _ServingLocalHttp(
            _LocalHttpScript(
                health_status=503,
                health_body=(
                    b'{"error":{"code":503,"message":"Loading model",'
                    b'"type":"unavailable_error"}}'
                ),
            )
        ) as (_script, port):
            assert client.health(port) is False

    @pytest.mark.parametrize(
        "body",
        [
            b"[]",
            b'{"status":"loading"}',
            b'{"error":{"code":"503","message":"Loading model",'
            b'"type":"unavailable_error"}}',
            b'{"error":{"code":503.0,"message":"Loading model",'
            b'"type":"unavailable_error"}}',
        ],
        ids=["array", "obsolete-shape", "string-code", "float-code"],
    )
    def test_unready_health_rejects_valid_json_with_wrong_shape(
        self, body: bytes
    ) -> None:
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())
        with _ServingLocalHttp(
            _LocalHttpScript(health_status=503, health_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.health(port)

        _assert_refusal(exc, "malformed_response")

    @pytest.mark.parametrize(
        ("body", "reason"),
        [
            pytest.param(b"not-json", "malformed_response", id="malformed"),
            pytest.param(
                b"x" * (driver.RESPONSE_BYTE_CAP + 1),
                "response_too_large",
                id="over-cap",
            ),
        ],
    )
    def test_unready_health_still_validates_the_full_response(
        self, body: bytes, reason: str
    ) -> None:
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())
        with _ServingLocalHttp(
            _LocalHttpScript(health_status=503, health_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.health(port)

        _assert_refusal(exc, reason)

    def test_health_header_arrival_after_deadline_is_http_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        response = _ScriptedHttpResponse(
            clock,
            [(0.0, b'{"status":"loading"}')],
            status=503,
            content_type="application/json",
            close_when_reads_exhausted=True,
        )

        class DelayedHeadersConnection(_ScriptedHttpConnection):
            def getresponse(self) -> _ScriptedHttpResponse:
                clock.advance(0.200)
                return super().getresponse()

        def factory(host: str, port: int, timeout: float) -> _ScriptedHttpConnection:
            return DelayedHeadersConnection(
                host,
                port,
                timeout,
                clock=clock,
                response=response,
            )

        monkeypatch.setattr(driver, "_LiteralLoopbackHTTPConnection", factory)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver._health_request(  # noqa: SLF001 - deterministic transport seam
                43210,
                clock=clock,
                request_timeout_ms=100,
            )

        _assert_refusal(exc, "http_timeout")

    def test_health_redirect_is_protocol_malformed_not_ordinary_unready(self) -> None:
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())
        with _ServingLocalHttp(
            _LocalHttpScript(health_status=302, health_body=b"")
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.health(port)
        _assert_refusal(exc, "malformed_response")

    def test_malformed_http_status_is_typed_and_content_light(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        response = _ScriptedHttpResponse(
            clock,
            [],
            content_type="application/json",
        )

        class MalformedStatusConnection(_ScriptedHttpConnection):
            def getresponse(self) -> _ScriptedHttpResponse:
                raise http.client.BadStatusLine("PRIVATE-STATUS-SENTINEL")

        def factory(host: str, port: int, timeout: float) -> _ScriptedHttpConnection:
            return MalformedStatusConnection(
                host,
                port,
                timeout,
                clock=clock,
                response=response,
            )

        monkeypatch.setattr(driver, "_LiteralLoopbackHTTPConnection", factory)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver._health_request(  # noqa: SLF001 - deterministic transport seam
                43210,
                clock=clock,
                request_timeout_ms=driver.REQUEST_TIMEOUT_MS,
            )

        _assert_refusal(exc, "malformed_response")
        assert "PRIVATE-STATUS-SENTINEL" not in str(exc.value)

    def test_json_parse_cannot_finish_after_the_absolute_deadline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        response = _ScriptedHttpResponse(
            clock,
            [(0.020, b'{"status":"ok"}')],
            content_type="application/json",
            close_when_reads_exhausted=True,
        )

        def factory(host: str, port: int, timeout: float) -> _ScriptedHttpConnection:
            return _ScriptedHttpConnection(
                host,
                port,
                timeout,
                clock=clock,
                response=response,
            )

        real_loads = json.loads

        def slow_loads(payload: object, *args: object, **kwargs: object) -> object:
            clock.advance(0.100)
            return real_loads(payload, *args, **kwargs)

        monkeypatch.setattr(driver, "_LiteralLoopbackHTTPConnection", factory)
        monkeypatch.setattr(driver.json, "loads", slow_loads)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver._health_request(  # noqa: SLF001 - deterministic transport seam
                43210,
                clock=clock,
                request_timeout_ms=100,
            )
        _assert_refusal(exc, "http_timeout")

    def test_json_endpoint_rejects_duplicate_content_length(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        body = b'{"status":"ok"}'
        response = _ScriptedHttpResponse(
            clock,
            [(0.010, body)],
            content_type="application/json",
            close_when_reads_exhausted=True,
            headers=[
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Content-Length", str(len(body))),
            ],
        )

        def factory(host: str, port: int, timeout: float) -> _ScriptedHttpConnection:
            return _ScriptedHttpConnection(
                host,
                port,
                timeout,
                clock=clock,
                response=response,
            )

        monkeypatch.setattr(driver, "_LiteralLoopbackHTTPConnection", factory)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver._health_request(  # noqa: SLF001 - deterministic transport seam
                43210,
                clock=clock,
                request_timeout_ms=driver.REQUEST_TIMEOUT_MS,
            )
        _assert_refusal(exc, "malformed_response")

    def test_raw_health_rejects_short_declared_json_body(self) -> None:
        body = b'{"status":"ok"}'
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())
        script = _LocalHttpScript(
            health_body=body,
            health_content_length=len(body) + 8,
        )

        with _ServingLocalHttp(script) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.health(port)

        _assert_refusal(exc, "malformed_response")

    def test_health_rejects_duplicate_json_keys(self) -> None:
        body = b'{"status":"bad","status":"ok"}'
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(
            _LocalHttpScript(health_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.health(port)

        _assert_refusal(exc, "malformed_response")

    @pytest.mark.parametrize("nonfinite", [b"NaN", b"1e9999"])
    def test_models_reject_nonfinite_json_numbers(self, nonfinite: bytes) -> None:
        body = b'{"data":[{"id":"alias","ignored":' + nonfinite + b"}]}"
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(
            _LocalHttpScript(models_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.models(port)

        _assert_refusal(exc, "malformed_response")

    def test_models_maps_recursive_json_failure_to_typed_refusal(self) -> None:
        nested = b"[" * 100_000 + b"0" + b"]" * 100_000
        body = b'{"data":[{"id":"alias","ignored":' + nested + b"}]}"
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(
            _LocalHttpScript(models_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.models(port)

        _assert_refusal(exc, "malformed_response")

    def test_models_reject_lone_surrogate_json_string(self) -> None:
        body = b'{"data":[{"id":"\\ud800"}]}'
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())

        with _ServingLocalHttp(
            _LocalHttpScript(models_body=body)
        ) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                client.models(port)

        _assert_refusal(exc, "malformed_response")

    def test_pathological_content_length_is_typed_without_integer_conversion(
        self,
    ) -> None:
        clock = driver.FrozenClock("2026-07-15T12:00:00Z")
        response = _ScriptedHttpResponse(
            clock,
            [],
            content_type="application/json",
            headers=[
                ("Content-Type", "application/json"),
                ("Content-Length", "9" * 5_000),
            ],
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver._validate_response_framing(  # noqa: SLF001 - protocol seam
                response,
                expected_content_type="application/json",
            )

        _assert_refusal(exc, "response_too_large")

    def test_connection_refused_health_is_an_ordinary_false_state(self) -> None:
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
            blocker.bind(("127.0.0.1", 0))
            port = int(blocker.getsockname()[1])
            assert client.health(port) is False

    @pytest.mark.parametrize("endpoint", ["health", "models"])
    def test_every_json_endpoint_enforces_the_response_cap(
        self, endpoint: str
    ) -> None:
        secret = b"PRIVATE-ENDPOINT-BODY-" + b"x" * driver.RESPONSE_BYTE_CAP
        kwargs = (
            {"health_body": secret}
            if endpoint == "health"
            else {"models_body": secret}
        )
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())
        with _ServingLocalHttp(_LocalHttpScript(**kwargs)) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                getattr(client, endpoint)(port)

        _assert_refusal(exc, "response_too_large")
        assert secret[:20].decode() not in str(exc.value)

    @pytest.mark.parametrize(
        ("endpoint", "body"),
        [
            ("health", b'{"status":"PRIVATE-HEALTH-SENTINEL"}'),
            ("models", b'{"data":"PRIVATE-MODELS-SENTINEL"}'),
        ],
    )
    def test_malformed_json_endpoint_bodies_never_enter_refusals(
        self, endpoint: str, body: bytes
    ) -> None:
        kwargs = {f"{endpoint}_body": body}
        client = driver.LoopbackServerClient.rehearsal(driver.RehearsalClock())
        with _ServingLocalHttp(_LocalHttpScript(**kwargs)) as (_script, port):
            with pytest.raises(driver.BenchRefusal) as exc:
                getattr(client, endpoint)(port)

        _assert_refusal(exc, "malformed_response")
        assert "PRIVATE" not in str(exc.value)

    def test_real_redirect_is_refused_without_contacting_its_target(self) -> None:
        sink_script = _LocalHttpScript()
        clock = driver.RehearsalClock()
        client = driver.LoopbackServerClient.rehearsal(clock)
        with _ServingLocalHttp(sink_script) as (sink, sink_port):
            redirect = _LocalHttpScript(
                redirect_to=f"http://127.0.0.1:{sink_port}/completion"
            )
            with _ServingLocalHttp(redirect) as (source, source_port):
                with pytest.raises(driver.BenchRefusal) as exc:
                    client.stream(source_port, "PRIVATE-REDIRECT-PROMPT")

        _assert_refusal(exc, "malformed_response")
        assert source.hits == [("POST", "/completion")]
        assert sink.hits == []
        assert "PRIVATE-REDIRECT-PROMPT" not in str(exc.value)


class TestB6ClientSeal:
    def test_production_request_timeout_is_sealed_before_provider_admission(
        self,
    ) -> None:
        clock = driver.SystemClock()
        assert (
            driver.LoopbackServerClient.production(clock).request_timeout_ms
            == driver.REQUEST_TIMEOUT_MS
            == 30_000
        )
        components = _provider_components("production")
        components["server_client"] = driver.LoopbackServerClient.production(
            components["clock"],
            request_timeout_ms=1,
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.production_tier(**components)

        _assert_refusal(exc, "tier_mismatch")

    def test_rehearsal_client_rejects_nonadvancing_transport_clock(self) -> None:
        with pytest.raises(ValueError, match="^transport_clock_required$"):
            driver.LoopbackServerClient.rehearsal(
                driver.FrozenClock("2026-07-15T12:00:00Z")
            )

    @pytest.mark.parametrize("clock", [driver.SystemClock(), driver.RehearsalClock()])
    def test_transport_clock_behavior_is_immutable_after_admission(
        self, clock: object
    ) -> None:
        with pytest.raises(AttributeError):
            clock.monotonic = lambda: 0.0  # type: ignore[attr-defined,method-assign]
        with pytest.raises(AttributeError):
            clock.tier = "rehearsal"  # type: ignore[attr-defined]

    @pytest.mark.parametrize("host", ["localhost", "::1", "127.0.0.2"])
    def test_nonliteral_loopback_host_is_rejected(self, host: str) -> None:
        with pytest.raises(ValueError, match="^loopback_literal_required$"):
            driver.LoopbackServerClient.production(driver.SystemClock(), host=host)

    @pytest.mark.parametrize("tier", ["production", "rehearsal"])
    def test_factory_returns_exact_client_with_identical_clock(self, tier: str) -> None:
        components = _provider_components(tier)
        clock = components["clock"]
        client = (
            driver.LoopbackServerClient.production(clock)
            if tier == "production"
            else driver.LoopbackServerClient.rehearsal(clock)
        )
        components["server_client"] = client
        factory = driver.production_tier if tier == "production" else driver.rehearsal_tier

        providers = factory(**components)

        assert type(providers.server_client) is driver.LoopbackServerClient
        assert providers.server_client.clock is providers.clock

    def test_factory_rejects_equal_but_distinct_client_clock(self) -> None:
        components = _provider_components("rehearsal")
        client_clock = driver.RehearsalClock()
        components["server_client"] = driver.LoopbackServerClient.rehearsal(
            client_clock
        )
        assert client_clock is not components["clock"]

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.rehearsal_tier(**components)

        _assert_refusal(exc, "tier_mismatch")

    def test_factory_rejects_same_tier_fake_client(self) -> None:
        components = _provider_components("production")
        components["server_client"] = _TieredFake("production")
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.production_tier(**components)
        _assert_refusal(exc, "tier_mismatch")

    def test_factory_rejects_client_subclass(self) -> None:
        class UnsafeClient(driver.LoopbackServerClient):
            pass

        components = _provider_components("rehearsal")
        components["server_client"] = UnsafeClient.rehearsal(components["clock"])
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.rehearsal_tier(**components)
        _assert_refusal(exc, "tier_mismatch")

    def test_client_for_one_tier_cannot_enter_the_other(self) -> None:
        components = _provider_components("production")
        components["server_client"] = driver.LoopbackServerClient.rehearsal(
            driver.RehearsalClock()
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.production_tier(**components)
        _assert_refusal(exc, "tier_mismatch")

    def test_sealed_provider_client_cannot_mutate_its_clock_after_admission(
        self,
    ) -> None:
        components = _provider_components("rehearsal")
        providers = driver.rehearsal_tier(**components)

        with pytest.raises(FrozenInstanceError):
            providers.server_client.clock = driver.FrozenClock(  # type: ignore[misc]
                "2026-07-14T12:00:00Z"
            )


class TestB6Mtp:
    def test_missing_wire_keys_are_unproven(self) -> None:
        for timings in ({}, {"draft_n": 12}, {"draft_n_accepted": 9}):
            with pytest.raises(driver.BenchRefusal) as exc:
                driver.parse_mtp(timings)
            _assert_refusal(exc, "mtp_unproven")

    def test_valid_wire_pair_derives_rejected_and_ignores_forged_key(self) -> None:
        assert driver.parse_mtp(
            {
                "draft_n": 12,
                "draft_n_accepted": 9,
                "draft_n_rejected": 999,
            }
        ) == (12, 9, 3)

    @pytest.mark.parametrize(
        "timings",
        [
            {"draft_n": 5, "draft_n_accepted": 9},
            {"draft_n": 0, "draft_n_accepted": 0},
            {"draft_n": True, "draft_n_accepted": 1},
            {"draft_n": 1, "draft_n_accepted": False},
            {"draft_n": 1.0, "draft_n_accepted": 1},
            {"draft_n": 1, "draft_n_accepted": -1},
        ],
    )
    def test_invalid_present_wire_pair_is_malformed(
        self, timings: dict[str, object]
    ) -> None:
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.parse_mtp(timings)
        _assert_refusal(exc, "malformed_response")

    def test_aggregate_requires_exact_three_by_seven_shape(self) -> None:
        valid = [(12, 9, 3)] * 7
        for cycles in ([valid] * 2, [valid, valid, valid[:6]]):
            with pytest.raises(ValueError, match="^sample_count$"):
                driver.aggregate_mtp(cycles)

    @pytest.mark.parametrize(
        "bad_entry",
        [
            (12, 9),
            (12, 9, 999),
            (0, 0, 0),
            (12, 13, -1),
            (True, 1, 0),
        ],
    )
    def test_aggregate_rejects_malformed_or_inconsistent_tuple(
        self, bad_entry: tuple[object, ...]
    ) -> None:
        cycles: list[list[tuple[object, ...]]] = [
            [(12, 9, 3)] * 7,
            [(12, 9, 3)] * 7,
            [(12, 9, 3)] * 7,
        ]
        cycles[1][3] = bad_entry
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.aggregate_mtp(cycles)
        _assert_refusal(exc, "malformed_response")

    def test_aggregate_sums_three_cycles_and_rederives_rejected(self) -> None:
        cycles = [
            [(12, 9, 3)] * 7,
            [(8, 2, 6)] * 7,
            [(3, 0, 3)] * 7,
        ]
        assert driver.aggregate_mtp(cycles) == (161, 77, 84)


def _b6_measurement(index: int) -> object:
    return driver.TurnMeasurement(
        ttft_ms=0.5,
        e2e_ms=float(index),
        content="private generated sentinel",
        timings={
            "prompt_per_second": float(100 + index),
            "predicted_per_second": float(50 + index),
        },
        terminal={"prompt": "private prompt sentinel"},
    )


class TestB6Statistics:
    def test_nearest_rank_medians_and_max_are_recomputed(self) -> None:
        result = driver.phase_statistics(
            [_b6_measurement(index) for index in range(1, 22)]
        )
        assert result == {
            "seven_turn_max_ms": 21.0,
            "p95_e2e_ms": 20.0,
            "median_decode_tps": 61.0,
            "median_prefill_tps": 111.0,
        }

    def test_wrong_sample_count_is_explicit(self) -> None:
        with pytest.raises(ValueError, match="^sample_count$"):
            driver.phase_statistics(
                [_b6_measurement(index) for index in range(1, 21)]
            )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("e2e_ms", float("nan")),
            ("ttft_ms", float("inf")),
            ("e2e_ms", True),
        ],
    )
    def test_invalid_wall_measurement_is_malformed(
        self, field: str, value: object
    ) -> None:
        turns = [_b6_measurement(index) for index in range(1, 22)]
        turns[0] = replace(turns[0], **{field: value})
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.phase_statistics(turns)
        _assert_refusal(exc, "malformed_response")

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("prompt_per_second", float("nan")),
            ("predicted_per_second", float("inf")),
            ("prompt_per_second", False),
        ],
    )
    def test_invalid_server_rate_is_malformed(self, key: str, value: object) -> None:
        turns = [_b6_measurement(index) for index in range(1, 22)]
        timings = dict(turns[0].timings)
        timings[key] = value
        turns[0] = replace(turns[0], timings=timings)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.phase_statistics(turns)
        _assert_refusal(exc, "malformed_response")

    def test_oversized_integer_server_rate_is_malformed(self) -> None:
        turns = [_b6_measurement(index) for index in range(1, 22)]
        timings = dict(turns[0].timings)
        timings["prompt_per_second"] = 10**1_000
        turns[0] = replace(turns[0], timings=timings)

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.phase_statistics(turns)

        _assert_refusal(exc, "malformed_response")

    def test_ttft_after_e2e_is_malformed(self) -> None:
        turns = [_b6_measurement(index) for index in range(1, 22)]
        turns[0] = replace(turns[0], ttft_ms=2.0, e2e_ms=1.0)
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.phase_statistics(turns)
        _assert_refusal(exc, "malformed_response")

    def test_measurement_repr_is_content_light(self) -> None:
        measurement = _b6_measurement(1)
        rendered = repr(measurement)
        assert "private prompt sentinel" not in rendered
        assert "private generated sentinel" not in rendered
        assert "prompt" not in rendered
        assert "content" not in rendered


class _SafeProductionPortProbe:
    tier = "production"

    def __init__(self, *, free: bool = True) -> None:
        self.free = free
        self.calls: list[int] = []

    def is_free(
        self,
        port: int,
        *,
        lease: driver.RehearsalPortLease | None = None,
    ) -> bool:
        if lease is not None:
            raise driver.BenchRefusal("provider_uncertain")
        self.calls.append(port)
        return self.free


class TestB7ContainmentV2:
    @staticmethod
    def _capture(*, maez_active: bool) -> tuple[object, list[tuple[str, object]]]:
        calls: list[tuple[str, object]] = []
        flag_bytes = b"HOME=/home/rohit\nMAEZ_SCREEN_PERCEPTION=0\n"
        unit_bytes = b"[Service]\nExecStart=/frozen/vision\n"

        def command_reader(argv: list[str]) -> str:
            calls.append(("command", tuple(argv)))
            unit = argv[-1]
            if unit == "llama-vision.service":
                return (
                    "ActiveState=inactive\nSubState=dead\n"
                    "UnitFileState=disabled\nMainPID=0\n"
                )
            if unit == "maez.service":
                return (
                    "ActiveState=active\nSubState=running\n"
                    "UnitFileState=enabled\nMainPID=4321\n"
                    if maez_active
                    else "ActiveState=inactive\nSubState=dead\nUnitFileState=enabled\nMainPID=0\n"
                )
            raise AssertionError(unit)

        def file_reader(path: Path) -> bytes:
            calls.append(("file", path))
            if path == driver.SCREEN_FLAG_SOURCE_PATH:
                return flag_bytes
            if path == driver.VISION_UNIT_PATH:
                return unit_bytes
            raise AssertionError(path)

        def environ_reader(pid: int) -> bytes:
            calls.append(("environ", pid))
            return b"HOME=/home/rohit\0MAEZ_SCREEN_PERCEPTION=0\0"

        port_probe = _SafeProductionPortProbe()
        provider = driver.RealContainmentProvider(
            clock=driver.SystemClock(),
            port_probe=port_probe,
            command_reader=command_reader,
            file_reader=file_reader,
            environ_reader=environ_reader,
        )
        snapshot = provider.capture("vulkan_baseline", "before")
        return snapshot, calls

    def test_real_capture_uses_fresh_injected_sensors_and_current_hashes(self) -> None:
        first, first_calls = self._capture(maez_active=True)
        second, second_calls = self._capture(maez_active=True)

        assert first.screen_flag_value == "0"
        assert first.active_state == "inactive"
        assert first.substate == "dead"
        assert first.enabled_state == "disabled"
        assert first.port_closed is True
        assert first.flag_source_sha256 == hashlib.sha256(
            b"HOME=/home/rohit\nMAEZ_SCREEN_PERCEPTION=0\n"
        ).hexdigest()
        assert first.vision_unit_sha256 == hashlib.sha256(
            b"[Service]\nExecStart=/frozen/vision\n"
        ).hexdigest()
        assert first.maez_active_state == "active"
        assert first.maez_process_screen_flag_value == "0"
        assert first.clean is True
        contextual = replace(
            first,
            phase="cuda_candidate",
            boundary="after",
            timestamp="2026-07-15T23:59:59Z",
        )
        changed_observation = replace(first, screen_flag_value="1")
        assert first.artifact_sha256 == contextual.artifact_sha256
        assert first.binding_sha256 != contextual.binding_sha256
        assert first.artifact_sha256 != changed_observation.artifact_sha256
        assert first.artifact_sha256 != first.binding_sha256
        first_commands = [value for kind, value in first_calls if kind == "command"]
        assert first_commands.count(
            ("systemctl", "--user", "show", "llama-vision.service")
        ) == 1
        assert first_commands.count(
            ("systemctl", "--user", "show", "maez.service")
        ) == 2
        assert first_calls and second_calls
        assert first is not second

    def test_wrong_scope_not_found_cannot_vacuously_replace_live_user_unit(
        self,
    ) -> None:
        calls: list[tuple[str, object]] = []

        def command_reader(argv: list[str]) -> str:
            calls.append(("command", tuple(argv)))
            if argv == ["systemctl", "--user", "show", "llama-vision.service"]:
                return (
                    "ActiveState=inactive\nSubState=dead\n"
                    "UnitFileState=disabled\nMainPID=0\n"
                )
            if argv == ["systemctl", "--user", "show", "maez.service"]:
                return (
                    "ActiveState=active\nSubState=running\n"
                    "UnitFileState=enabled\nMainPID=4321\n"
                )
            if argv == ["systemctl", "show", "maez.service"]:
                return (
                    "ActiveState=inactive\nSubState=dead\n"
                    "UnitFileState=\nMainPID=0\n"
                )
            raise AssertionError(argv)

        def file_reader(path: Path) -> bytes:
            if path == driver.SCREEN_FLAG_SOURCE_PATH:
                return b"MAEZ_SCREEN_PERCEPTION=0\n"
            if path == driver.VISION_UNIT_PATH:
                return b"unit"
            raise AssertionError(path)

        def environ_reader(pid: int) -> bytes:
            calls.append(("environ", pid))
            assert pid == 4321
            return b"MAEZ_SCREEN_PERCEPTION=0\0"

        provider = driver.RealContainmentProvider(
            clock=driver.SystemClock(),
            port_probe=_SafeProductionPortProbe(),
            command_reader=command_reader,
            file_reader=file_reader,
            environ_reader=environ_reader,
        )

        snapshot = provider.capture("vulkan_baseline", "before")

        assert snapshot.maez_active_state == "active"
        assert snapshot.maez_process_screen_flag_value == "0"
        assert calls == [
            (
                "command",
                ("systemctl", "--user", "show", "llama-vision.service"),
            ),
            ("command", ("systemctl", "--user", "show", "maez.service")),
            ("environ", 4321),
            ("command", ("systemctl", "--user", "show", "maez.service")),
        ]

    def test_stopped_maez_does_not_fabricate_or_read_a_process_flag(self) -> None:
        snapshot, calls = self._capture(maez_active=False)
        assert snapshot.maez_active_state == "inactive"
        assert snapshot.maez_process_screen_flag_value is None
        assert snapshot.clean is True
        assert not any(kind == "environ" for kind, _value in calls)
        commands = [value for kind, value in calls if kind == "command"]
        assert commands.count(
            ("systemctl", "--user", "show", "maez.service")
        ) == 1
        assert ("systemctl", "show", "maez.service") not in commands

    def test_active_maez_without_exact_process_flag_is_observed_as_dirty(self) -> None:
        provider = driver.RealContainmentProvider(
            clock=driver.SystemClock(),
            port_probe=_SafeProductionPortProbe(),
            command_reader=lambda argv: (
                "ActiveState=inactive\nSubState=dead\nUnitFileState=disabled\nMainPID=0\n"
                if argv[-1] == "llama-vision.service"
                else "ActiveState=active\nSubState=running\nUnitFileState=enabled\nMainPID=7\n"
            ),
            file_reader=lambda path: (
                b"MAEZ_SCREEN_PERCEPTION=0\n"
                if path == driver.SCREEN_FLAG_SOURCE_PATH
                else b"unit"
            ),
            environ_reader=lambda _pid: b"MAEZ_SCREEN_PERCEPTION=1\0",
        )
        snapshot = provider.capture("vulkan_baseline", "before")

        assert snapshot.maez_active_state == "active"
        assert snapshot.maez_process_screen_flag_value == "1"
        assert snapshot.clean is False

    @pytest.mark.parametrize(
        "flag_bytes",
        [
            b"HOME=/home/rohit\n",
            b"MAEZ_SCREEN_PERCEPTION=0\nMAEZ_SCREEN_PERCEPTION=0\n",
            b"MAEZ_SCREEN_PERCEPTION=0\nMAEZ_SCREEN_PERCEPTION=1\n",
        ],
    )
    def test_flag_source_requires_one_unambiguous_assignment_from_hashed_bytes(
        self, flag_bytes: bytes
    ) -> None:
        provider = driver.RealContainmentProvider(
            clock=driver.SystemClock(),
            port_probe=_SafeProductionPortProbe(),
            command_reader=lambda argv: (
                "ActiveState=inactive\nSubState=dead\nUnitFileState=disabled\nMainPID=0\n"
                if argv[-1] == "llama-vision.service"
                else "ActiveState=inactive\nSubState=dead\nUnitFileState=enabled\nMainPID=0\n"
            ),
            file_reader=lambda path: (
                flag_bytes if path == driver.SCREEN_FLAG_SOURCE_PATH else b"unit"
            ),
            environ_reader=lambda _pid: (_ for _ in ()).throw(
                AssertionError("inactive Maez has no process environment")
            ),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            provider.capture("vulkan_baseline", "before")
        _assert_refusal(exc, "containment_violation")

    @pytest.mark.parametrize(
        "second_show",
        [
            "ActiveState=inactive\nSubState=dead\nUnitFileState=enabled\nMainPID=0\n",
            "ActiveState=active\nSubState=running\nUnitFileState=enabled\nMainPID=8\n",
        ],
    )
    def test_active_maez_environment_read_is_bracketed_by_same_pid_active_shows(
        self, second_show: str
    ) -> None:
        maez_shows = iter(
            [
                "ActiveState=active\nSubState=running\nUnitFileState=enabled\nMainPID=7\n",
                second_show,
            ]
        )

        def command_reader(argv: list[str]) -> str:
            if argv[-1] == "llama-vision.service":
                return (
                    "ActiveState=inactive\nSubState=dead\n"
                    "UnitFileState=disabled\nMainPID=0\n"
                )
            return next(maez_shows)

        provider = driver.RealContainmentProvider(
            clock=driver.SystemClock(),
            port_probe=_SafeProductionPortProbe(),
            command_reader=command_reader,
            file_reader=lambda path: (
                b"MAEZ_SCREEN_PERCEPTION=0\n"
                if path == driver.SCREEN_FLAG_SOURCE_PATH
                else b"unit"
            ),
            environ_reader=lambda pid: (
                b"MAEZ_SCREEN_PERCEPTION=0\0"
                if pid == 7
                else (_ for _ in ()).throw(AssertionError("wrong pid read"))
            ),
        )
        with pytest.raises(driver.BenchRefusal) as exc:
            provider.capture("vulkan_baseline", "before")
        _assert_refusal(exc, "provider_uncertain")


@dataclass
class _B7Harness:
    config: object
    providers: object
    port_probe: object
    rehearsal_ports: object
    gpu: object
    containment: object
    authorization_gate: object


def _b7_authorization(*, nonce: str = "9" * 64) -> driver.WindowAuthorization:
    issued = datetime.now(UTC).replace(microsecond=0) - driver.timedelta(minutes=30)
    expires = issued + driver.timedelta(seconds=driver.WINDOW_TTL_S)
    return driver.WindowAuthorization(
        window_id="window-b7",
        phases=("vulkan_baseline", "cuda_candidate"),
        boot_id="boot-b7",
        nonce=nonce,
        issued_at=issued.isoformat().replace("+00:00", "Z"),
        expires_at=expires.isoformat().replace("+00:00", "Z"),
        owner="owner",
    )


def _b7_identity_fields() -> dict[str, object]:
    from tests.test_cuda_migration import PersistedDocTests, make_identity

    identity = make_identity()
    fields = PersistedDocTests.identity_fields(identity)
    fields["effective_args"] = tuple(fields["effective_args"])
    return fields


def _b7_write_static_preflight(root: Path) -> str:
    from tests.test_cuda_migration import PersistedDocTests, StaticPreflightDocTests

    identity = driver.cm.RuntimeIdentity(**_b7_identity_fields())
    checks = StaticPreflightDocTests.checks()
    checks.update(
        {
            "flag_source": "a" * 64,
            "vision_unit": "b" * 64,
            "candidate_manifest": identity.runtime_manifest_sha256,
            "stub_pin": STUB_SHA256,
        }
    )
    doc = driver.cm.StaticPreflightDoc(
        gpu_uuid="GPU-12345678-1234-1234-1234-123456789abc",
        driver_package_sha256="e" * 64,
        stub_sha256=STUB_SHA256,
        corpus_verified=True,
        checks=checks,
        timestamp="2026-07-15T12:00:00Z",
    )
    fields = {
        "gpu_uuid": doc.gpu_uuid,
        "driver_package_sha256": doc.driver_package_sha256,
        "stub_sha256": doc.stub_sha256,
        "corpus_verified": doc.corpus_verified,
        "checks": dict(doc.checks),
        "timestamp": doc.timestamp,
    }
    payload = PersistedDocTests.wrapper(
        driver.STATIC_PREFLIGHT_SCHEMA,
        doc,
        fields,
    )
    relative = "receipts/static-preflight.json"
    path = root / relative
    path.parent.mkdir(mode=0o700)
    _private_file(path, payload)
    return relative


def _b7_harness(
    root: Path,
    *,
    persona: str = "healthy",
    service_active: bool = False,
    fail_containment: str | None = None,
    fail_first_memory: bool = False,
    topology_drift: bool = False,
    nonce: str = "9" * 64,
    request_timeout_ms: int = 250,
) -> _B7Harness:
    static_path = _b7_write_static_preflight(root)
    clock = driver.RehearsalClock()
    services = {
        "llama-server.service": "active" if service_active else "inactive",
        "llama-judge.service": "inactive",
        "llama-vision.service": "inactive",
    }
    service_state = driver.SyntheticServiceState(services)
    rehearsal_ports = driver.RehearsalPortRegistry()
    port_probe = driver.SyntheticPortProbe(
        {driver.BENCH_PORT, *driver.PRODUCTION_PORTS},
        rehearsal_ports=rehearsal_ports,
    )
    inventories = [[] for _index in range(16)]
    if topology_drift:
        inventories[5] = [(999_999, "other-gpu-process")]
    memories = (
        None
        if fail_first_memory
        else [
            *[
                value
                for _cycle in range(3)
                for value in ((1.0, 100), (2.0, 200), (3.0, 250), (1.0, 100))
            ],
            (1.0, 100),
            (1.0, 100),
            (1.0, 100),
        ]
    )
    gpu = driver.SyntheticGpu(
        ["GPU-12345678-1234-1234-1234-123456789abc"],
        inventories,
        memories,
    )
    kernel = driver.SyntheticKernelLog(dict.fromkeys(driver.KERNEL_COUNTER_KEYS, 0))
    maps = driver.SyntheticBackendMap(
        {},
        default_maps_text=str(
            driver.cm.VULKAN_RELEASE_ROOT / "libggml-vulkan.so"
        ),
    )
    policy = driver.RehearsalArtifactPolicy()
    authorization_gate = driver.RehearsalAuthorizationGate(policy)
    containment = driver.SyntheticContainmentProvider(
        clock=clock,
        port_probe=port_probe,
        flag_source_sha256="a" * 64,
        vision_unit_sha256="b" * 64,
        fail_boundary=fail_containment,
    )
    launcher = driver.RehearsalServerLauncher(
        _stub_pin(), rehearsal_ports=rehearsal_ports
    )
    client = driver.LoopbackServerClient.rehearsal(
        clock,
        request_timeout_ms=request_timeout_ms,
    )
    providers = driver.rehearsal_tier(
        service_state=service_state,
        port_probe=port_probe,
        gpu=gpu,
        kernel_log=kernel,
        backend_maps=maps,
        server_launcher=launcher,
        server_client=client,
        authorization_gate=authorization_gate,
        containment=containment,
        artifact_policy=policy,
        clock=clock,
        journal_factory=driver.RehearsalJournalFactory(),
    )
    argv = _stub_argv()
    argv[argv.index("healthy")] = persona
    config = driver.PhaseConfig(
        phase="vulkan_baseline",
        argv=argv,
        env=_stub_env(),
        alias="qwen36-27b-mtp",
        prompts=tuple(f"sentinel-{index}" for index in range(1, 8)),
        authorization=_b7_authorization(nonce=nonce),
        parent_window=None,
        parent_packet_path=None,
        bench_identity_fields=_b7_identity_fields(),
        runtime_identity_fields=_b7_identity_fields(),
        static_preflight_path=static_path,
        gpu_uuid="GPU-12345678-1234-1234-1234-123456789abc",
        boot_id="boot-b7",
        window_id="window-b7",
        expected_port=None,
        readiness_timeout_s=request_timeout_ms / 1_000,
    )
    return _B7Harness(
        config=config,
        providers=providers,
        port_probe=port_probe,
        rehearsal_ports=rehearsal_ports,
        gpu=gpu,
        containment=containment,
        authorization_gate=authorization_gate,
    )


def _b7_wrapper(path: Path) -> dict[str, object]:
    wrapper = json.loads(path.read_bytes())
    assert set(wrapper) == {"rehearsal_schema", "tier", "payload"}
    assert wrapper["rehearsal_schema"] == driver.REHEARSAL_PACKET_SCHEMA
    assert wrapper["tier"] == "rehearsal"
    assert "schema" not in wrapper
    return wrapper


class TestTask6TierTimeoutBounds:
    @pytest.mark.parametrize("readiness_timeout_s", (299.0, 1.0))
    def test_production_readiness_timeout_bound_refuses_before_artifacts(
        self, private_root: Path, readiness_timeout_s: float
    ) -> None:
        config, _pin, _static, _identity = _b7_production_contract_case(
            private_root,
            "vulkan_baseline",
        )
        config = replace(config, readiness_timeout_s=readiness_timeout_s)
        before = sorted(path.relative_to(private_root) for path in private_root.rglob("*"))

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.run_phase(
                config,
                driver.production_tier(**_provider_components("production")),
                root=private_root,
            )

        _assert_refusal(exc, "tier_mismatch")
        assert sorted(path.relative_to(private_root) for path in private_root.rglob("*")) == before

    @pytest.mark.parametrize(
        "readiness_timeout_s",
        (5.000001, 0.0, -1.0, True, float("inf"), float("nan")),
    )
    def test_rehearsal_readiness_timeout_bound_refuses_before_artifacts(
        self, private_root: Path, readiness_timeout_s: object
    ) -> None:
        harness = _b7_harness(private_root)
        config = replace(
            harness.config,
            readiness_timeout_s=readiness_timeout_s,
        )
        before = sorted(path.relative_to(private_root) for path in private_root.rglob("*"))

        with pytest.raises(driver.BenchRefusal) as exc:
            driver.run_phase(config, harness.providers, root=private_root)

        _assert_refusal(exc, "tier_mismatch")
        assert sorted(path.relative_to(private_root) for path in private_root.rglob("*")) == before


class TestB7PhaseStateMachine:
    @pytest.fixture(autouse=True)
    def _short_phase_bounds(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
        monkeypatch.setattr(driver, "READINESS_TIMEOUT_S", 0.25)
        monkeypatch.setattr(driver, "UNLOAD_WAIT_S", 0.25)
        spawned: list[driver.OwnedChild] = []
        real_spawn = driver.RehearsalServerLauncher.spawn

        def tracked_spawn(
            launcher: driver.RehearsalServerLauncher,
            argv: list[str],
            env: dict[str, str],
        ) -> driver.OwnedChild:
            child = real_spawn(launcher, argv, env)
            spawned.append(child)
            return child

        monkeypatch.setattr(driver.RehearsalServerLauncher, "spawn", tracked_spawn)
        yield
        for child in spawned:
            if child.popen.poll() is None:
                child.popen.kill()
                child.popen.wait(timeout=3)
            try:
                os.close(child.pidfd)
            except OSError:
                pass

    def test_production_phase_rejects_static_completion_before_admission(
        self, private_root: Path
    ) -> None:
        config, _pin, _static, _identity = _b7_production_contract_case(
            private_root,
            "vulkan_baseline",
        )
        policy = driver.ProductionArtifactPolicy()
        admission_ref = "command-static-preflight-attempt-001-admission.json"
        admission_bytes = policy.encode(
            "command_admission",
            {
                "command": "static-preflight",
                "ordinal": 1,
                "window_id": None,
                "status": "admitted",
                "timestamp": "2026-07-15T12:00:02Z",
            },
        )
        admission = driver.cm.CommandAdmissionPreimage(
            admission_ref,
            admission_bytes,
        )
        static_bytes = driver.open_bench_file(
            config.static_preflight_path,
            root=private_root,
        )
        static_doc = driver.cm.PersistedDoc(static_bytes)
        completion = driver.cm.CommandCompletionDoc(
            command="static-preflight",
            ordinal=admission.ordinal,
            window_id=None,
            admission_ref=admission.selected_ref,
            admission_sha256=admission.file_sha256,
            artifact_ref=config.static_preflight_path,
            artifact_sha256=static_doc.file_sha256,
            artifact_schema=driver.cm.STATIC_PREFLIGHT_SCHEMA,
            status="completed",
            timestamp="2026-07-15T12:00:01Z",
        )
        completion_ref = (
            "command-static-preflight-attempt-001-completion.json"
        )
        completion_bytes = policy.encode(
            "command_completion",
            {
                "binding_sha256": completion.binding_sha256,
                "command": completion.command,
                "ordinal": completion.ordinal,
                "window_id": completion.window_id,
                "admission_ref": completion.admission_ref,
                "admission_sha256": completion.admission_sha256,
                "artifact_ref": completion.artifact_ref,
                "artifact_sha256": completion.artifact_sha256,
                "artifact_schema": completion.artifact_schema,
                "status": completion.status,
                "timestamp": completion.timestamp,
            },
        )
        _private_file(private_root / admission_ref, admission_bytes)
        _private_file(private_root / completion_ref, completion_bytes)
        attempt_root = private_root / "attempt"
        attempt_root.mkdir(mode=0o700)
        config = replace(
            config,
            static_admission_path=admission_ref,
            static_completion_path=completion_ref,
        )
        providers = driver.production_tier(
            **_provider_components("production")
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            driver._load_phase_preimages(
                config,
                providers,
                root=private_root,
                attempt_root=attempt_root,
            )

        _assert_refusal(exc, "identity_mismatch")
        assert not (private_root / "markers").exists()
        assert list(attempt_root.iterdir()) == []

    def test_stock_rehearsal_runs_three_cycles_and_writes_incompatible_evidence(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root)
        observed_leases: list[object] = []
        tracked_spawn = driver.RehearsalServerLauncher.spawn

        def observe_lease(
            launcher: driver.RehearsalServerLauncher,
            argv: list[str],
            env: dict[str, str],
        ) -> driver.OwnedChild:
            child = tracked_spawn(launcher, argv, env)
            observed_leases.append(child.rehearsal_port_lease)
            return child

        monkeypatch.setattr(driver.RehearsalServerLauncher, "spawn", observe_lease)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        wrapper = _b7_wrapper(path)
        payload = wrapper["payload"]
        assert payload["kind"] == "packet"
        assert "schema" not in payload
        fields = payload["fields"]
        assert fields["outcome"] == "completed"
        assert len(fields["turn_manifest"]["entries"]) == 24
        assert len(fields["turn_records"]) == 24
        assert len(fields["cycle_metrics"]) == 3
        assert len(fields["cycle_witnesses"]) == 3
        assert all(len(metric["topology_hashes"]) == 4 for metric in fields["cycle_metrics"])
        assert len(
            {
                topology
                for metric in fields["cycle_metrics"]
                for topology in metric["topology_hashes"]
            }
        ) == 1
        assert fields["pinned_path"] == str(STUB_PATH)
        assert fields["pinned_sha256"] == STUB_SHA256
        assert [lease.generation for lease in observed_leases] == [1, 2, 3]
        assert all(type(lease) is driver.RehearsalPortLease for lease in observed_leases)
        assert harness.rehearsal_ports.current is None
        assert all(driver.RealPortProbe().is_free(lease.port) for lease in observed_leases)
        assert harness.port_probe.witness == driver.ProviderWitness(
            synthetic=True,
            real_calls=0,
            loopback_kernel_calls=3,
        )
        harness.port_probe.witness.assert_no_real_calls()
        harness_source = inspect.getsource(_b7_harness)
        assert ".is_free =" not in harness_source
        assert ".read_maps =" not in harness_source
        assert "/proc/self/fd/" not in path.read_text()
        assert path.is_relative_to(
            private_root / "rehearsal" / "windows" / "window-b7" / "vulkan_baseline"
        )
        with pytest.raises(ValueError):
            driver.cm.PersistedDoc(path.read_bytes())
        from tests.test_cuda_migration import _make_bundle

        with pytest.raises(ValueError):
            replace(_make_bundle(), control_packet=wrapper)

    def test_validate_precedes_containment_and_consume_follows_cycle_one_before(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="8" * 64)
        events: list[str] = []
        containment = harness.containment
        gpu = harness.gpu
        real_validate = driver.RehearsalAuthorizationGate.validate
        real_consume = driver.RehearsalAuthorizationGate.consume
        real_capture = containment.capture
        real_memory = gpu.memory

        def counted_validate(
            gate_self: object, *args: object, **kwargs: object
        ) -> None:
            events.append("validate")
            real_validate(gate_self, *args, **kwargs)

        def counted_consume(
            gate_self: object, *args: object, **kwargs: object
        ) -> object:
            events.append("consume")
            return real_consume(gate_self, *args, **kwargs)

        monkeypatch.setattr(driver.RehearsalAuthorizationGate, "validate", counted_validate)
        monkeypatch.setattr(driver.RehearsalAuthorizationGate, "consume", counted_consume)
        containment.capture = lambda *args, **kwargs: (
            events.append(f"containment-{args[1]}"),
            real_capture(*args, **kwargs),
        )[1]
        gpu.memory = lambda *args, **kwargs: (
            events.append("memory"),
            real_memory(*args, **kwargs),
        )[1]

        driver.run_phase(harness.config, harness.providers, root=private_root)

        assert events.index("validate") < events.index("containment-before")
        assert events.index("containment-before") < events.index("memory")
        assert events.index("memory") < events.index("consume")
        assert events.count("validate") >= 2  # consume re-validates
        assert harness.containment.capture_count == 2

    @pytest.mark.parametrize(
        ("failure", "expected"),
        [
            ("service", "preflight_service_active"),
            ("containment", "containment_violation"),
            ("gpu", "provider_uncertain"),
            ("port", "preflight_bench_port_busy"),
        ],
    )
    def test_all_pre_spawn_failures_refuse_without_calling_consume(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        failure: str,
        expected: str,
    ) -> None:
        harness = _b7_harness(
            private_root,
            service_active=failure == "service",
            fail_containment="before" if failure == "containment" else None,
            fail_first_memory=failure == "gpu",
            nonce=hashlib.sha256(failure.encode()).hexdigest(),
        )
        if failure == "port":
            harness.port_probe._free.discard(driver.BENCH_PORT)
        consumed = False

        def forbidden_consume(*_args: object, **_kwargs: object) -> object:
            nonlocal consumed
            consumed = True
            raise AssertionError("consume reached")

        monkeypatch.setattr(
            driver.RehearsalAuthorizationGate,
            "consume",
            lambda _self, *_args, **_kwargs: forbidden_consume(),
        )
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == expected
        assert fields["spawned"] is False
        assert consumed is False
        assert not (private_root / "markers").exists()

    @pytest.mark.parametrize(
        "unit",
        ["llama-server.service", "llama-judge.service", driver.VISION_UNIT],
    )
    @pytest.mark.parametrize(
        "state",
        [
            "active",
            "reloading",
            "failed",
            "activating",
            "deactivating",
            "maintenance",
            "unknown",
        ],
    )
    def test_every_noninactive_service_state_refuses_before_nonce_or_spawn(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        unit: str,
        state: str,
    ) -> None:
        nonce = hashlib.sha256(f"{unit}:{state}".encode()).hexdigest()
        harness = _b7_harness(private_root, nonce=nonce)
        harness.providers.service_state._states[unit] = state
        consumed = False
        spawned = False

        def forbidden_consume(*_args: object, **_kwargs: object) -> object:
            nonlocal consumed
            consumed = True
            raise AssertionError("consume reached")

        def forbidden_spawn(*_args: object, **_kwargs: object) -> object:
            nonlocal spawned
            spawned = True
            raise AssertionError("spawn reached")

        monkeypatch.setattr(
            driver.RehearsalAuthorizationGate,
            "consume",
            lambda _self, *_args, **_kwargs: forbidden_consume(),
        )
        monkeypatch.setattr(
            driver.RehearsalServerLauncher,
            "spawn",
            lambda _self, *_args, **_kwargs: forbidden_spawn(),
        )

        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == "preflight_service_active"
        assert fields["spawned"] is False
        assert consumed is False
        assert spawned is False
        assert not (private_root / "markers").exists()

    def test_tampered_parent_wrapper_refuses_before_consume_or_spawn(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="a" * 64)
        parent_relative = "receipts/tampered-parent.json"
        _private_file(private_root / parent_relative, b'{"schema":"tampered"}\n')
        config = replace(harness.config, parent_packet_path=parent_relative)
        consumed = False

        def forbidden_consume(*_args: object, **_kwargs: object) -> object:
            nonlocal consumed
            consumed = True
            raise AssertionError("consume reached")

        monkeypatch.setattr(
            driver.RehearsalAuthorizationGate,
            "consume",
            lambda _self, *_args, **_kwargs: forbidden_consume(),
        )
        path = driver.run_phase(config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == "continuation_parent_mismatch"
        assert fields["spawned"] is False
        assert consumed is False
        assert not (private_root / "markers").exists()

    def test_runtime_identity_drift_refuses_before_consume_or_spawn(
        self, private_root: Path
    ) -> None:
        harness = _b7_harness(private_root, nonce="b" * 64)
        runtime_fields = dict(harness.config.runtime_identity_fields)
        runtime_fields["model_sha256"] = "f" * 64
        config = replace(harness.config, runtime_identity_fields=runtime_fields)
        path = driver.run_phase(config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == "identity_mismatch"
        assert fields["spawned"] is False
        assert not (private_root / "markers").exists()

    def test_unexpected_pre_spawn_exception_becomes_reduced_provider_refusal(
        self, private_root: Path
    ) -> None:
        harness = _b7_harness(private_root, nonce="c" * 64)
        harness.containment.capture = lambda *_args: (_ for _ in ()).throw(
            RuntimeError("unexpected sensor failure")
        )
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == "provider_uncertain"
        assert fields["spawned"] is False
        assert not (private_root / "markers").exists()

    @pytest.mark.parametrize(
        ("persona", "expected"),
        [
            ("readiness_timeout", "readiness_timeout"),
            ("midturn_hang", "http_timeout"),
            ("crash", "crash"),
            ("malformed_response", "malformed_response"),
            ("wrong_identity", "alias_mismatch"),
        ],
    )
    def test_failure_personas_write_reduced_packet_and_real_residue_proof(
        self, private_root: Path, persona: str, expected: str
    ) -> None:
        harness = _b7_harness(
            private_root,
            persona=persona,
            nonce=hashlib.sha256(persona.encode()).hexdigest(),
            request_timeout_ms=120,
        )
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == expected
        assert fields["spawned"] is True
        assert "turn_manifest" not in fields
        assert fields["finalizer"]["listener_free"] is True
        assert fields["finalizer"]["surviving_pgid_members"] == []
        assert driver.RealPortProbe().is_free(fields["observed_port"])
        assert driver._pgid_members(fields["observed_pgid"]) == []

    @pytest.mark.parametrize("field", ["pinned_path", "pinned_sha256"])
    def test_cycle_child_pin_drift_is_identity_mismatch(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch, field: str
    ) -> None:
        harness = _b7_harness(private_root, nonce=("6" if field == "pinned_path" else "7") * 64)
        real_spawn = driver.RehearsalServerLauncher.spawn
        calls = 0

        def drifting_spawn(
            launcher: driver.RehearsalServerLauncher,
            argv: list[str],
            env: dict[str, str],
        ) -> driver.OwnedChild:
            nonlocal calls
            calls += 1
            child = real_spawn(launcher, argv, env)
            if calls == 2:
                replacement = (
                    {"pinned_path": "/home/rohit/maez/scripts/not-the-stub.py"}
                    if field == "pinned_path"
                    else {"pinned_sha256": "f" * 64}
                )
                return replace(child, **replacement)
            return child

        monkeypatch.setattr(driver.RehearsalServerLauncher, "spawn", drifting_spawn)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fields["outcome"] == "identity_mismatch"
        assert "turn_manifest" not in fields

    def test_topology_drift_fails_closed(self, private_root: Path) -> None:
        harness = _b7_harness(private_root, topology_drift=True, nonce="5" * 64)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        assert _b7_wrapper(path)["payload"]["fields"]["outcome"] == "topology_drift"

    @pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
    def test_both_driver_signals_finalize_and_write_interrupted_evidence(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        signum: int,
    ) -> None:
        harness = _b7_harness(private_root, nonce=("3" if signum == signal.SIGINT else "4") * 64)
        handlers: dict[int, object] = {}
        monkeypatch.setattr(
            driver.signal,
            "signal",
            lambda number, handler: handlers.setdefault(number, handler),
        )
        client = harness.providers.server_client
        real_stream = client.stream
        fired = False

        def interrupted_stream(
            _client: driver.LoopbackServerClient,
            port: int,
            prompt: str,
        ) -> object:
            nonlocal fired
            if not fired:
                fired = True
                handlers[signum](signum, None)
            return real_stream(port, prompt)

        monkeypatch.setattr(
            driver.LoopbackServerClient,
            "stream",
            interrupted_stream,
        )
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]
        assert fired is True
        assert fields["outcome"] == "interrupted"
        assert fields["finalizer"]["listener_free"] is True
        assert driver._pgid_members(fields["observed_pgid"]) == []


class TestB7RemainingSpecGate:
    @pytest.fixture(autouse=True)
    def _short_phase_bounds(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
        monkeypatch.setattr(driver, "READINESS_TIMEOUT_S", 0.25)
        monkeypatch.setattr(driver, "UNLOAD_WAIT_S", 0.15)
        monkeypatch.setattr(driver, "SIGTERM_GRACE_S", 0.15)
        monkeypatch.setattr(driver, "KILL_WAIT_S", 0.15)
        monkeypatch.setattr(driver, "LISTENER_WAIT_S", 0.15)
        spawned: list[driver.OwnedChild] = []
        real_spawn = driver.RehearsalServerLauncher.spawn

        def tracked_spawn(
            launcher: driver.RehearsalServerLauncher,
            argv: list[str],
            env: dict[str, str],
        ) -> driver.OwnedChild:
            child = real_spawn(launcher, argv, env)
            spawned.append(child)
            return child

        monkeypatch.setattr(driver.RehearsalServerLauncher, "spawn", tracked_spawn)
        yield
        for child in spawned:
            if child.popen.poll() is None:
                child.popen.kill()
                child.popen.wait(timeout=3)
            try:
                os.close(child.pidfd)
            except OSError:
                pass

    def test_real_launcher_returns_admitted_child_without_post_admission_work(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pin = driver.SpawnPin(
            kind="binary",
            pinned_path=driver.cm.VULKAN_RELEASE_ROOT / "llama-server",
            pinned_sha256="a" * 64,
            required_argv_prefix=(
                str(driver.cm.VULKAN_RELEASE_ROOT / "llama-server"),
            ),
        )
        launcher = driver.RealServerLauncher(pin)
        sentinel = object()
        admitted_ports: list[int | None] = []

        def fake_spawn(
            argv: list[str],
            *,
            pin: object,
            env: dict[str, str],
            admitted_port: int | None = None,
        ) -> object:
            assert argv[-2:] == ["--port", str(driver.BENCH_PORT)]
            admitted_ports.append(admitted_port)
            return sentinel

        monkeypatch.setattr(driver, "spawn_pinned", fake_spawn)
        result = launcher.spawn(
            [str(pin.pinned_path), "--port", str(driver.BENCH_PORT)],
            {},
        )

        assert result is sentinel
        assert admitted_ports == [driver.BENCH_PORT]

    def test_signal_during_launcher_handoff_still_finalizes_owned_child(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="e" * 64)
        real_spawn = driver.RehearsalServerLauncher.spawn

        def signal_before_return(
            launcher: driver.RehearsalServerLauncher,
            argv: list[str],
            env: dict[str, str],
        ) -> driver.OwnedChild:
            child = real_spawn(launcher, argv, env)
            os.kill(os.getpid(), signal.SIGTERM)
            return child

        monkeypatch.setattr(
            driver.RehearsalServerLauncher,
            "spawn",
            signal_before_return,
        )
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == "interrupted"
        assert fields["spawned"] is True
        assert fields["finalizer"]["listener_free"] is True
        assert driver._pgid_members(fields["observed_pgid"]) == []

    @pytest.mark.parametrize(
        "cleanup_outcome", ["cleanup_incomplete", "pid_reuse_detected"]
    )
    def test_cleanup_failure_dominates_request_failure(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        cleanup_outcome: str,
    ) -> None:
        harness = _b7_harness(
            private_root,
            persona="midturn_hang",
            nonce=("f" if cleanup_outcome == "cleanup_incomplete" else "0") * 64,
            request_timeout_ms=100,
        )
        real_finalize = driver.finalize

        def degraded_finalize(*args: object, **kwargs: object) -> object:
            result = real_finalize(*args, **kwargs)
            return replace(result, outcome=cleanup_outcome)

        monkeypatch.setattr(driver, "finalize", degraded_finalize)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == cleanup_outcome
        assert fields["finalizer"]["outcome"] == cleanup_outcome

    def test_forced_sigkill_classifies_live_timeout_as_hang(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(
            private_root,
            persona="midturn_hang",
            nonce="1" * 64,
            request_timeout_ms=100,
        )
        real_finalize = driver.finalize

        def forced_finalize(*args: object, **kwargs: object) -> object:
            result = real_finalize(*args, **kwargs)
            return replace(result, signals_sent=("SIGTERM", "SIGKILL"))

        monkeypatch.setattr(driver, "finalize", forced_finalize)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == "hang"
        assert fields["finalizer"]["signals_sent"] == ["SIGTERM", "SIGKILL"]

    def test_crash_stays_distinct_from_timeout_and_hang(self, private_root: Path) -> None:
        harness = _b7_harness(
            private_root,
            persona="crash",
            nonce="2" * 64,
            request_timeout_ms=100,
        )
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == "crash"
        assert "SIGKILL" not in fields["finalizer"]["signals_sent"]

    def test_unload_waits_until_memory_returns_within_bound(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="3" * 64)
        values = iter(
            [
                (1.0, 100),
                (2.0, 200),
                (3.0, 250),
                (2.0, 150),
                (1.0, 100),
                (1.0, 100),
                (2.0, 200),
                (3.0, 250),
                (1.0, 100),
                (1.0, 100),
                (2.0, 200),
                (3.0, 250),
                (1.0, 100),
            ]
        )
        samples: list[tuple[float, int]] = []

        def constant_inventory(_uuid: str) -> list[tuple[int, str]]:
            return []

        def delayed_memory(_uuid: str) -> tuple[float, int]:
            value = next(values)
            samples.append(value)
            return value

        monkeypatch.setattr(harness.gpu, "inventory", constant_inventory)
        monkeypatch.setattr(harness.gpu, "memory", delayed_memory)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == "completed"
        assert samples[:5] == [
            (1.0, 100),
            (2.0, 200),
            (3.0, 250),
            (2.0, 150),
            (1.0, 100),
        ]

    def test_unload_timeout_retries_then_refuses(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="4" * 64)
        calls = 0

        def constant_inventory(_uuid: str) -> list[tuple[int, str]]:
            return []

        def never_unloaded(_uuid: str) -> tuple[float, int]:
            nonlocal calls
            calls += 1
            if calls == 1:
                return (1.0, 100)
            if calls in {2, 3}:
                return (3.0, 250)
            return (2.0, 150)

        monkeypatch.setattr(harness.gpu, "inventory", constant_inventory)
        monkeypatch.setattr(harness.gpu, "memory", never_unloaded)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == "unload_incomplete"
        assert calls > 4

    def test_kernel_refusal_still_captures_containment_after(
        self, private_root: Path
    ) -> None:
        harness = _b7_harness(private_root, nonce="5" * 64)
        harness.providers.kernel_log._counts["Xid"] = 1
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == "kernel_unmatched"
        assert harness.containment.capture_count == 2
        after = (
            path.parents[2]
            / "rehearsal"
            / "containment"
            / "containment-after.json"
        )
        assert after.is_file()

    def test_backend_unproven_is_a_distinct_failed_packet(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="6" * 64)
        monkeypatch.setattr(
            harness.providers.backend_maps,
            "read_maps",
            lambda _pid: (
                f"{driver.cm.VULKAN_RELEASE_ROOT}/libggml-vulkan.so\n"
                f"{driver.cm.CUDA_RELEASE_ROOT}/libggml-cuda.so"
            ),
        )
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == "backend_unproven"
        assert fields["finalizer"]["outcome"] == "clean"

    def test_reduced_packet_binds_every_observed_tail_preimage(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="d" * 64)
        monkeypatch.setattr(
            harness.providers.backend_maps,
            "read_maps",
            lambda _pid: "no backend mapping",
        )

        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]
        attempt_root = path.parents[2]
        before = attempt_root / "rehearsal/containment/containment-before.json"
        after = attempt_root / "rehearsal/containment/containment-after.json"
        bench_identity = (
            attempt_root / "rehearsal/identity/bench_runtime_identity.json"
        )

        assert fields["authorization_preimage_sha256"] == (
            harness.config.authorization.preimage_sha256
        )
        assert re.fullmatch(r"[0-9a-f]{64}", fields["consumption_receipt_sha256"])
        assert fields["containment_before_sha256"] == hashlib.sha256(
            before.read_bytes()
        ).hexdigest()
        assert fields["containment_after_sha256"] == hashlib.sha256(
            after.read_bytes()
        ).hexdigest()
        assert fields["static_preflight_sha256"] == hashlib.sha256(
            (private_root / harness.config.static_preflight_path).read_bytes()
        ).hexdigest()
        assert fields["runtime_identity_sha256"] == hashlib.sha256(
            bench_identity.read_bytes()
        ).hexdigest()
        assert fields["kernel_cursor_before"] != fields["kernel_cursor_after"]
        assert fields["kernel_counters"] == {
            "reusemappingdb_map": 0,
            "pmap_cb": 0,
            "mmu_walk_map": 0,
            "nv_err_no_memory": 0,
            "xid": 0,
            "unmatched_nvrm": 0,
        }

    def test_finalize_to_unload_boundary_cannot_skip_unload(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="c" * 64)
        real_append = driver._append_phase_transition
        real_wait = driver._wait_for_unload
        unload_calls = 0

        def failed_finalize_journal(
            journal: object,
            clock: object,
            transition: str,
            **kwargs: object,
        ) -> None:
            if transition == "cycle_1_finalize":
                raise driver.BenchRefusal("journal_failure")
            real_append(journal, clock, transition, **kwargs)

        def observed_unload(*args: object, **kwargs: object) -> object:
            nonlocal unload_calls
            unload_calls += 1
            return real_wait(*args, **kwargs)

        monkeypatch.setattr(driver, "_append_phase_transition", failed_finalize_journal)
        monkeypatch.setattr(driver, "_wait_for_unload", observed_unload)

        path = driver.run_phase(harness.config, harness.providers, root=private_root)

        assert _b7_wrapper(path)["payload"]["fields"]["outcome"] == (
            "journal_failure"
        )
        assert unload_calls == 1

    def test_any_forced_sigkill_after_healthy_turns_is_a_hang(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="b" * 64)
        real_finalize = driver.finalize

        def forced_finalize(*args: object, **kwargs: object) -> object:
            result = real_finalize(*args, **kwargs)
            return replace(result, signals_sent=("SIGTERM", "SIGKILL"))

        monkeypatch.setattr(driver, "finalize", forced_finalize)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        fields = _b7_wrapper(path)["payload"]["fields"]

        assert fields["outcome"] == "hang"
        assert fields["finalizer"]["signals_sent"] == ["SIGTERM", "SIGKILL"]

    def test_finalize_journal_detail_carries_the_complete_witness(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="a" * 64)
        real_finalize = driver.finalize

        def forced_finalize(*args: object, **kwargs: object) -> object:
            result = real_finalize(*args, **kwargs)
            return replace(result, signals_sent=("SIGTERM", "SIGKILL"))

        monkeypatch.setattr(driver, "finalize", forced_finalize)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        journal_path = next(path.parents[2].rglob("*-journal.jsonl"))
        event = next(
            json.loads(line)
            for line in journal_path.read_text().splitlines()
            if json.loads(line)["transition"] == "cycle_1_finalize"
        )

        assert event["detail"] == _b7_wrapper(path)["payload"]["fields"]["finalizer"]
        assert event["detail"]["signals_sent"] == ["SIGTERM", "SIGKILL"]

    def test_completed_packet_publication_is_the_only_terminal_artifact(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="e" * 64)
        real_append = driver.PhaseJournal.append

        def forbid_post_publication_append(
            journal: driver.PhaseJournal, *args: object, **kwargs: object
        ) -> None:
            if list(private_root.rglob("vulkan_baseline-completed.json")):
                raise driver.BenchRefusal("journal_failure")
            real_append(journal, *args, **kwargs)

        monkeypatch.setattr(driver.PhaseJournal, "append", forbid_post_publication_append)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        terminals = list(private_root.rglob("vulkan_baseline-*.json"))

        assert _b7_wrapper(path)["payload"]["fields"]["outcome"] == "completed"
        assert terminals == [path]

    def test_journal_close_failure_converts_success_to_one_journal_failure_artifact(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="f" * 64)
        real_close = driver.PhaseJournal.close
        close_calls = 0

        def fail_first_close(journal: driver.PhaseJournal) -> None:
            nonlocal close_calls
            close_calls += 1
            real_close(journal)
            if close_calls == 1:
                raise driver.BenchRefusal("journal_failure")

        monkeypatch.setattr(driver.PhaseJournal, "close", fail_first_close)

        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        terminals = list(private_root.rglob("vulkan_baseline-*.json"))

        assert _b7_wrapper(path)["payload"]["fields"]["outcome"] == "journal_failure"
        assert terminals == [path]
        assert not list(private_root.rglob("vulkan_baseline-completed.json"))

    def test_post_terminal_signal_handler_restore_failure_returns_committed_path(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="1" * 64)
        real_signal = driver.signal.signal
        raised = False

        def fail_after_committed_terminal(signum: int, handler: object) -> object:
            nonlocal raised
            previous = real_signal(signum, handler)
            if (
                not raised
                and list(private_root.rglob("vulkan_baseline-completed.json"))
            ):
                raised = True
                raise OSError("handler restore failed")
            return previous

        monkeypatch.setattr(driver.signal, "signal", fail_after_committed_terminal)

        with pytest.raises(driver.BenchRefusal, match="^cleanup_incomplete$"):
            driver.run_phase(harness.config, harness.providers, root=private_root)

        assert raised is True
        assert not list(private_root.rglob("*command-completion*.json"))

    def test_post_terminal_signal_mask_restore_failure_returns_committed_path(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="2" * 64)
        real_sigmask = driver.signal.pthread_sigmask
        raised = False

        def fail_after_committed_terminal(how: int, mask: object) -> object:
            nonlocal raised
            previous = real_sigmask(how, mask)
            if (
                not raised
                and how == signal.SIG_SETMASK
                and list(private_root.rglob("vulkan_baseline-completed.json"))
            ):
                raised = True
                raise OSError("mask restore failed")
            return previous

        monkeypatch.setattr(driver.signal, "pthread_sigmask", fail_after_committed_terminal)

        with pytest.raises(driver.BenchRefusal, match="^cleanup_incomplete$"):
            driver.run_phase(harness.config, harness.providers, root=private_root)

        assert raised is True
        assert not list(private_root.rglob("*command-completion*.json"))

    def test_sigterm_at_completed_link_returns_only_the_committed_terminal(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="3" * 64)
        real_check_directory = driver._check_directory_fd
        raised = False

        def interrupt_first_postlink_check(fd: int) -> object:
            nonlocal raised
            if (
                not raised
                and list(private_root.rglob("vulkan_baseline-completed.json"))
            ):
                raised = True
                signal.raise_signal(signal.SIGTERM)
            return real_check_directory(fd)

        monkeypatch.setattr(driver, "_check_directory_fd", interrupt_first_postlink_check)

        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        terminals = list(private_root.rglob("vulkan_baseline-*.json"))

        assert raised is True
        assert path.name != "vulkan_baseline-completed.json"
        assert _b7_wrapper(path)["payload"]["fields"]["outcome"] != "completed"
        assert not list(private_root.rglob("*command-completion*.json"))
        assert path in terminals

    @pytest.mark.parametrize(
        ("terminal_kind", "expected_outcome"),
        [
            ("completed", "completed"),
        ],
    )
    def test_postlink_fsync_failure_returns_only_the_committed_terminal(
        self,
        private_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        terminal_kind: str,
        expected_outcome: str,
    ) -> None:
        harness = _b7_harness(private_root, nonce=hashlib.sha256(terminal_kind.encode()).hexdigest())
        real_fsync = driver.os.fsync
        failed = False

        def fail_first_terminal_parent_fsync(fd: int) -> None:
            nonlocal failed
            if (
                not failed
                and stat.S_ISDIR(os.fstat(fd).st_mode)
                and list(private_root.rglob("vulkan_baseline-*.json"))
            ):
                failed = True
                raise OSError("post-link terminal fsync failure")
            real_fsync(fd)

        monkeypatch.setattr(driver.os, "fsync", fail_first_terminal_parent_fsync)

        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        terminals = list(private_root.rglob("vulkan_baseline-*.json"))

        assert failed is True
        observed = _b7_wrapper(path)["payload"]["fields"]["outcome"]
        if terminal_kind == "completed":
            assert observed in {"filesystem_hazard", "journal_failure"}
            assert not list(
                private_root.rglob("*command-completion*.json")
            )
            orphan = next(
                private_root.rglob("vulkan_baseline-completed.json")
            )
            assert orphan != path
            assert _b7_wrapper(orphan)["payload"]["fields"]["outcome"] == (
                "completed"
            )
        else:
            assert observed == expected_outcome
        assert path in terminals

    def test_failed_after_spawn_journal_closes_the_full_evidence_tail(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="9" * 64)
        monkeypatch.setattr(
            harness.providers.backend_maps,
            "read_maps",
            lambda _pid: "no backend mapping",
        )
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        journal_path = next(path.parents[2].rglob("*-journal.jsonl"))
        transitions = [
            json.loads(line)["transition"]
            for line in journal_path.read_text().splitlines()
        ]
        required_tail = [
            "cycle_1_backend_witness",
            "cycle_1_finalize",
            "cycle_1_after_unload",
            "kernel_delta",
            "containment_after",
            "failed_packet_write",
            "failed",
        ]
        positions = [transitions.index(name) for name in required_tail]

        assert _b7_wrapper(path)["payload"]["fields"]["outcome"] == (
            "backend_unproven"
        )
        assert positions == sorted(positions)

    def test_completed_journal_has_the_canonical_transition_sequence(
        self, private_root: Path
    ) -> None:
        harness = _b7_harness(private_root, nonce="7" * 64)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)
        journal_path = next(path.parents[2].rglob("*-journal.jsonl"))
        observed = [
            json.loads(line)["transition"]
            for line in journal_path.read_text().splitlines()
        ]
        expected = [
            "phase_preflight",
            "containment_before",
            "cycle_one_before_snapshot",
            "consume_authorization",
        ]
        for cycle in (1, 2, 3):
            expected.extend(
                [
                    f"cycle_{cycle}_before",
                    f"cycle_{cycle}_load",
                    f"cycle_{cycle}_readiness",
                    f"cycle_{cycle}_alias",
                    f"cycle_{cycle}_backend_witness",
                    f"cycle_{cycle}_after_load",
                    f"cycle_{cycle}_warmup",
                    *[f"cycle_{cycle}_measured_{ordinal}" for ordinal in range(1, 8)],
                    f"cycle_{cycle}_after_inference",
                    f"cycle_{cycle}_finalize",
                    f"cycle_{cycle}_after_unload",
                ]
            )
        expected.extend(
            [
                "kernel_delta",
                "containment_after",
                "packet_write",
                "completed",
            ]
        )
        assert observed == expected

    def test_completed_state_machine_is_single_use_under_private_test_factory(
        self, private_root: Path
    ) -> None:
        harness = _b7_harness(private_root, nonce="8" * 64)
        components = {
            name: getattr(harness.providers, name)
            for name in (
                "service_state",
                "port_probe",
                "gpu",
                "kernel_log",
                "backend_maps",
                "server_launcher",
                "server_client",
                "containment",
                "artifact_policy",
                "clock",
                "journal_factory",
            )
        }
        gate = driver._TestOnlySingleUseAuthorizationGate(
            harness.providers.artifact_policy
        )
        components["authorization_gate"] = gate
        providers = driver._test_rehearsal_tier(**components)

        first = driver.run_phase(harness.config, providers, root=private_root)
        second = driver.run_phase(harness.config, providers, root=private_root)

        assert _b7_wrapper(first)["payload"]["fields"]["outcome"] == "completed"
        retry = _b7_wrapper(second)["payload"]["fields"]
        assert retry["outcome"] == "authorization_consumed"
        assert retry["spawned"] is False
        assert not (private_root / "markers").exists()

        with pytest.raises(driver.BenchRefusal) as real_factory:
            driver.rehearsal_tier(**components)
        _assert_refusal(real_factory, "tier_mismatch")

    def test_protocol_complete_test_gate_cannot_enter_real_factory(self) -> None:
        class TestOnlyGate:
            tier = "rehearsal"

            def validate(self, *_args: object, **_kwargs: object) -> None:
                return None

            def consume(self, *_args: object, **_kwargs: object) -> object:
                raise AssertionError("test only")

        components = _provider_components("rehearsal")
        components["authorization_gate"] = TestOnlyGate()
        with pytest.raises(driver.BenchRefusal) as exc:
            driver.rehearsal_tier(**components)
        _assert_refusal(exc, "tier_mismatch")

    @pytest.mark.parametrize("phase", ["vulkan_baseline", "cuda_candidate"])
    def test_typed_phase_packet_builder_is_reachable_without_a_model(
        self, private_root: Path, phase: str
    ) -> None:
        from tests.test_cuda_migration import _phase_packet

        config, pin, static, identity = _b7_production_contract_case(
            private_root, phase
        )
        execution = driver._validate_production_execution_contract(
            config,
            launcher_pin=pin,
            static=static,
            runtime_identity=identity,
        )
        measured = _phase_packet(phase)
        evidence = driver.CompletedPhaseEvidence(
            admitted_pinned_path=measured.pinned_path,
            admitted_pinned_sha256=measured.pinned_sha256,
            topology_sha256=measured.topology_sha256,
            consumed=driver.ConsumedAuthority(
                measured.authorization_preimage_sha256,
                measured.consumption_receipt_sha256,
                {"nonce": config.authorization.nonce},
            ),
            static_preflight_sha256=measured.static_preflight_sha256,
            bench_runtime_identity_sha256=measured.runtime_identity_sha256,
            turn_manifest=measured.turn_manifest,
            turn_records=measured.turn_records,
            cycle_metrics=measured.cycle_metrics,
            cycle_witnesses=measured.cycle_witnesses,
            containment_before_sha256=measured.containment_before_sha256,
            containment_after_sha256=measured.containment_after_sha256,
            kernel_cursor_before=measured.kernel_cursor_before,
            kernel_cursor_after=measured.kernel_cursor_after,
            kernel_counters=measured.kernel_counters,
            cycle_one_before_snapshot_at=measured.cycle_one_before_snapshot_at,
            timestamp=measured.timestamp,
        )
        rebuilt = driver._build_completed_phase_packet(
            config=config,
            execution_contract=execution,
            runtime_identity=identity,
            static=static,
            evidence=evidence,
        )
        fields = driver._phase_packet_fields(rebuilt)
        encoded = driver.ProductionArtifactPolicy().encode(
            "packet",
            {"binding_sha256": rebuilt.binding_sha256, **fields},
        )
        persisted = driver.cm.PersistedDoc(encoded)

        assert type(rebuilt) is driver.cm.PhasePacket
        assert persisted.obj.binding_sha256 == rebuilt.binding_sha256
        assert rebuilt.pinned_path == execution.pinned_path
        assert rebuilt.pinned_sha256 == execution.pinned_sha256
        assert rebuilt.effective_args_sha256 == execution.effective_args_sha256

        with pytest.raises(driver.BenchRefusal) as tampered:
            driver._build_completed_phase_packet(
                config=config,
                execution_contract=replace(
                    execution,
                    pinned_sha256=("f" if execution.pinned_sha256[0] != "f" else "e")
                    * 64,
                ),
                runtime_identity=identity,
                static=static,
                evidence=evidence,
            )
        _assert_refusal(tampered, "identity_mismatch")

        with pytest.raises(driver.BenchRefusal) as mismatched_admission:
            driver._build_completed_phase_packet(
                config=config,
                execution_contract=execution,
                runtime_identity=identity,
                static=static,
                evidence=replace(
                    evidence,
                    admitted_pinned_sha256=(
                        "f" if evidence.admitted_pinned_sha256[0] != "f" else "e"
                    )
                    * 64,
                ),
            )
        _assert_refusal(mismatched_admission, "identity_mismatch")

    @pytest.mark.parametrize("gate_type", [
        driver.RealAuthorizationGate,
        driver.RehearsalAuthorizationGate,
    ])
    def test_authorization_gate_is_mutation_resistant_after_admission(
        self, gate_type: type[object]
    ) -> None:
        policy: object = (
            driver.ProductionArtifactPolicy()
            if gate_type is driver.RealAuthorizationGate
            else driver.RehearsalArtifactPolicy()
        )
        gate = gate_type(policy)
        with pytest.raises((AttributeError, FrozenInstanceError, TypeError)):
            gate.consume = lambda *_args, **_kwargs: None

    @pytest.mark.parametrize(
        "launcher",
        [
            driver.RealServerLauncher(_binary_pin(Path(sys.executable))),
            driver.RehearsalServerLauncher(_stub_pin()),
        ],
    )
    def test_launcher_pin_is_mutation_resistant_after_admission(
        self, launcher: object
    ) -> None:
        forged = replace(launcher.pin, pinned_sha256="f" * 64)
        with pytest.raises((AttributeError, FrozenInstanceError, TypeError)):
            launcher.pin = forged

    def test_config_mutation_during_consume_cannot_change_spawned_argv_or_env(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _b7_harness(private_root, nonce="f" * 64)
        admitted_argv = list(harness.config.argv)
        admitted_env = dict(harness.config.env)
        real_consume = driver.RehearsalAuthorizationGate.consume
        tracked_spawn = driver.RehearsalServerLauncher.spawn
        observed: list[tuple[list[str], dict[str, str]]] = []

        def mutating_consume(
            gate: driver.RehearsalAuthorizationGate,
            authorization: object,
            **kwargs: object,
        ) -> object:
            result = real_consume(gate, authorization, **kwargs)
            harness.config.argv.append("--forged-after-consume")
            harness.config.env["FORGED_AFTER_CONSUME"] = "1"
            return result

        def observed_spawn(
            launcher: driver.RehearsalServerLauncher,
            argv: list[str],
            env: dict[str, str],
        ) -> driver.OwnedChild:
            observed.append((list(argv), dict(env)))
            return tracked_spawn(launcher, argv, env)

        monkeypatch.setattr(driver.RehearsalAuthorizationGate, "consume", mutating_consume)
        monkeypatch.setattr(driver.RehearsalServerLauncher, "spawn", observed_spawn)
        path = driver.run_phase(harness.config, harness.providers, root=private_root)

        assert _b7_wrapper(path)["payload"]["fields"]["outcome"] == "completed"
        assert len(observed) == 3
        assert all(argv == admitted_argv for argv, _env in observed)
        assert all(env == admitted_env for _argv, env in observed)

    @pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
    def test_real_driver_signal_in_subprocess_finalizes_without_residue(
        self, private_root: Path, signum: int
    ) -> None:
        ready = private_root / "signal-ready.json"
        code = "\n".join(
            [
                "import json, os, sys, time",
                "from pathlib import Path",
                "from scripts import cuda_bench_driver as driver",
                "from tests.test_cuda_bench_driver import _b7_harness",
                "root = Path(sys.argv[1])",
                "driver.READINESS_TIMEOUT_S = 0.25",
                "driver.UNLOAD_WAIT_S = 0.15",
                "driver.SIGTERM_GRACE_S = 0.15",
                "driver.KILL_WAIT_S = 0.15",
                "driver.LISTENER_WAIT_S = 0.15",
                "harness = _b7_harness(root, nonce=sys.argv[2])",
                "def blocked(self, port, prompt):",
                "    path = root / 'signal-ready.json'",
                "    path.write_text(json.dumps({'port': port}), encoding='utf-8')",
                "    os.chmod(path, 0o600)",
                "    while True:",
                "        time.sleep(0.05)",
                "driver.LoopbackServerClient.stream = blocked",
                "result = driver.run_phase(harness.config, harness.providers, root=root)",
                "print('RESULT=' + str(result), flush=True)",
            ]
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                code,
                str(private_root),
                ("a" if signum == signal.SIGINT else "b") * 64,
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            assert _wait_for(ready.is_file, timeout=8.0)
            observed_port = json.loads(ready.read_text())["port"]
            process.send_signal(signum)
            stdout, stderr = process.communicate(timeout=8.0)
        except BaseException:
            process.kill()
            process.wait(timeout=3)
            raise

        assert process.returncode == 0, stderr[-2_000:]
        result_line = next(
            line for line in stdout.splitlines() if line.startswith("RESULT=")
        )
        fields = _b7_wrapper(Path(result_line.removeprefix("RESULT=")))["payload"][
            "fields"
        ]
        assert fields["outcome"] == "interrupted"
        assert fields["finalizer"]["listener_free"] is True
        assert driver.RealPortProbe().is_free(observed_port)
        assert driver._pgid_members(fields["observed_pgid"]) == []

    @pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
    def test_signal_during_entry_setup_becomes_typed_interrupted_outcome(
        self, private_root: Path, signum: int
    ) -> None:
        ready = private_root / "entry-ready"
        code = "\n".join(
            [
                "import json, os, signal, sys, time",
                "from pathlib import Path",
                "from scripts import cuda_bench_driver as driver",
                "from tests.test_cuda_bench_driver import _b7_harness",
                "root = Path(sys.argv[1])",
                "driver.READINESS_TIMEOUT_S = 0.25",
                "driver.UNLOAD_WAIT_S = 0.15",
                "driver.SIGTERM_GRACE_S = 0.15",
                "driver.KILL_WAIT_S = 0.15",
                "driver.LISTENER_WAIT_S = 0.15",
                "harness = _b7_harness(root, nonce=sys.argv[2])",
                "allocate = driver._allocate_attempt",
                "def delayed_allocate(**kwargs):",
                "    path = root / 'entry-ready'",
                "    path.write_text('ready', encoding='utf-8')",
                "    os.chmod(path, 0o600)",
                "    time.sleep(0.25)",
                "    return allocate(**kwargs)",
                "driver._allocate_attempt = delayed_allocate",
                "result = driver.run_phase(harness.config, harness.providers, root=root)",
                "print('RESULT=' + str(result), flush=True)",
            ]
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                code,
                str(private_root),
                ("c" if signum == signal.SIGINT else "d") * 64,
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            assert _wait_for(ready.is_file, timeout=8.0)
            process.send_signal(signum)
            stdout, stderr = process.communicate(timeout=8.0)
        except BaseException:
            process.kill()
            process.wait(timeout=3)
            raise

        assert process.returncode == 0, stderr[-2_000:]
        result_line = next(
            line for line in stdout.splitlines() if line.startswith("RESULT=")
        )
        fields = _b7_wrapper(Path(result_line.removeprefix("RESULT=")))["payload"][
            "fields"
        ]
        assert fields["outcome"] == "interrupted"
        assert fields["spawned"] is False


class TestB7AttemptAllocation:
    def test_disk_allocator_skips_existing_attempt(self, private_root: Path) -> None:
        parent = private_root / "rehearsal" / "windows" / "window-b7" / "vulkan_baseline"
        (parent / "attempt-000").mkdir(parents=True, mode=0o700)
        for directory in (parent / "attempt-000", parent, *parent.parents[:3]):
            os.chmod(directory, 0o700)
        claimed = driver._allocate_attempt(
            window_id="window-b7",
            phase="vulkan_baseline",
            policy=driver.RehearsalArtifactPolicy(),
            root=private_root,
        )
        assert claimed.name == "attempt-001"

    def test_allocator_retries_mkdirat_eexist_race(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = 0
        real_claim = driver._claim_attempt_directory

        def racing_claim(parent_fd: int, name: str) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                os.mkdir(name, mode=0o700, dir_fd=parent_fd)
                raise FileExistsError(errno.EEXIST, "simulated race", name)
            real_claim(parent_fd, name)

        monkeypatch.setattr(driver, "_claim_attempt_directory", racing_claim)
        claimed = driver._allocate_attempt(
            window_id="window-b7",
            phase="vulkan_baseline",
            policy=driver.RehearsalArtifactPolicy(),
            root=private_root,
        )
        assert claimed.name == "attempt-001"
        assert calls == 2


class TestCompletionArtifactPolicy:
    def test_command_completion_schema_is_the_twenty_fourth_closed_family(
        self,
    ) -> None:
        assert len(driver.cm.ACTIVE_SCHEMA_FAMILIES) == 24
        assert len(set(driver.cm.ACTIVE_SCHEMA_FAMILIES)) == 24
        assert (
            "cuda_bench_driver.command_completion.v1"
            in driver.cm.ACTIVE_SCHEMA_FAMILIES
        )
        assert driver._ARTIFACT_SCHEMAS["command_completion"] == (
            "cuda_bench_driver.command_completion.v1"
        )
        fields = {
            "binding_sha256": "a" * 64,
            "command": "static-preflight",
            "ordinal": 1,
            "window_id": None,
            "admission_ref": "command-static-preflight-attempt-001-admission.json",
            "admission_sha256": "b" * 64,
            "artifact_ref": "receipts/static-preflight-attempt-001.json",
            "artifact_sha256": "c" * 64,
            "artifact_schema": driver.STATIC_PREFLIGHT_SCHEMA,
            "status": "completed",
            "timestamp": "2026-07-15T11:59:00Z",
        }
        production = json.loads(
            driver.ProductionArtifactPolicy().encode(
                "command_completion", fields
            )
        )
        rehearsal = json.loads(
            driver.RehearsalArtifactPolicy().encode(
                "command_completion", fields
            )
        )
        assert production["schema"] == (
            "cuda_bench_driver.command_completion.v1"
        )
        assert rehearsal["rehearsal_schema"] == driver.REHEARSAL_PACKET_SCHEMA
        assert "schema" not in rehearsal


class TestB7AuthorizationSplit:
    def test_validate_is_write_free_and_consume_revalidates_into_separate_roots(
        self, private_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        authorization = _b7_authorization(nonce="2" * 64)
        gate = driver.RealAuthorizationGate(driver.ProductionArtifactPolicy())
        clock = driver.FrozenClock(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        attempt_root = private_root / "attempt"
        attempt_root.mkdir(mode=0o700)
        gate.validate(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-b7",
            expected_window_id="window-b7",
            parent_window=None,
            parent_packet=None,
            clock=clock,
        )
        assert list(private_root.rglob("*")) == [attempt_root]

        validations = 0
        real_validate_authorization = driver.validate_authorization

        def counted_validate(*args: object, **kwargs: object) -> None:
            nonlocal validations
            validations += 1
            real_validate_authorization(*args, **kwargs)

        monkeypatch.setattr(driver, "validate_authorization", counted_validate)
        gate.consume(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-b7",
            expected_window_id="window-b7",
            parent_window=None,
            parent_packet=None,
            authority_root=private_root,
            receipt_root=attempt_root,
            clock=clock,
        )
        assert validations == 1
        assert (private_root / "markers" / authorization.nonce).is_file()
        assert len(list((attempt_root / "receipts").glob("*.json"))) == 1
        assert not (private_root / "receipts").exists()
        with pytest.raises(driver.BenchRefusal) as retry:
            gate.consume(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-b7",
                expected_window_id="window-b7",
                parent_window=None,
                parent_packet=None,
                authority_root=private_root,
                receipt_root=attempt_root,
                clock=clock,
            )
        _assert_refusal(retry, "authorization_consumed")

    def test_expiry_between_validate_and_consume_publishes_no_marker(
        self, private_root: Path
    ) -> None:
        class MutableClock:
            tier = "production"

            def __init__(self) -> None:
                self.now = "2026-07-15T11:30:00Z"

            def now_utc(self) -> str:
                return self.now

            def monotonic(self) -> float:
                return 0.0

        authorization = driver.WindowAuthorization(
            window_id="window-b7",
            phases=("vulkan_baseline",),
            boot_id="boot-b7",
            nonce="1" * 64,
            issued_at="2026-07-15T08:00:00Z",
            expires_at="2026-07-15T12:00:00Z",
            owner="owner",
        )
        gate = driver.RealAuthorizationGate(driver.ProductionArtifactPolicy())
        clock = MutableClock()
        gate.validate(
            authorization,
            phase="vulkan_baseline",
            boot_id="boot-b7",
            expected_window_id="window-b7",
            parent_window=None,
            parent_packet=None,
            clock=clock,
        )
        clock.now = authorization.expires_at
        attempt_root = private_root / "attempt"
        attempt_root.mkdir(mode=0o700)
        with pytest.raises(driver.BenchRefusal) as exc:
            gate.consume(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-b7",
                expected_window_id="window-b7",
                parent_window=None,
                parent_packet=None,
                authority_root=private_root,
                receipt_root=attempt_root,
                clock=clock,
            )
        _assert_refusal(exc, "authorization_expired")
        assert not (private_root / "markers").exists()
        assert not (attempt_root / "receipts").exists()

    def test_marker_authority_and_receipt_roots_must_be_distinct(
        self, private_root: Path
    ) -> None:
        authorization = _b7_authorization(nonce="d" * 64)
        gate = driver.RealAuthorizationGate(driver.ProductionArtifactPolicy())
        clock = driver.FrozenClock(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        with pytest.raises(driver.BenchRefusal) as exc:
            gate.consume(
                authorization,
                phase="vulkan_baseline",
                boot_id="boot-b7",
                expected_window_id="window-b7",
                parent_window=None,
                parent_packet=None,
                authority_root=private_root,
                receipt_root=private_root,
                clock=clock,
            )
        _assert_refusal(exc, "filesystem_hazard")
        assert not (private_root / "markers").exists()

    def test_inv2_annotation_is_identical_on_validate_and_consume_surfaces(self) -> None:
        surfaces = (
            driver.AuthorizationGate.validate,
            driver.AuthorizationGate.consume,
            driver.RealAuthorizationGate.validate,
            driver.RealAuthorizationGate.consume,
            driver.RehearsalAuthorizationGate.validate,
            driver.RehearsalAuthorizationGate.consume,
            driver.validate_authorization,
            driver.consume_authorization,
        )
        for surface in surfaces:
            assert inspect.signature(surface).parameters["parent_packet"].annotation == (
                "cm.PhasePacket | None"
            )
            assert surface.__annotations__["parent_packet"] == "cm.PhasePacket | None"
            assert (
                inspect.signature(surface)
                .parameters["parent_completion"]
                .annotation
                == "ParentCompletionEvidence | None"
            )
            assert surface.__annotations__["parent_completion"] == (
                "ParentCompletionEvidence | None"
            )
