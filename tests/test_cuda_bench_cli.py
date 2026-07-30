"""RED contract tests for the sealed CUDA bench command boundary."""

from __future__ import annotations

import ast
import argparse
import hashlib
import importlib
import inspect
import json
import os
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
from pathlib import Path
from types import MappingProxyType
from unittest import mock

import pytest

from scripts import cuda_bench_assemble as assemble
from scripts import cuda_bench_cli as cli
from scripts import cuda_bench_driver as driver
from scripts import cuda_migration as cm


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


def _task6_identity_fields() -> dict[str, object]:
    from tests.test_cuda_migration import PersistedDocTests, make_identity

    fields = PersistedDocTests.identity_fields(make_identity())
    fields["effective_args"] = tuple(fields["effective_args"])
    return fields


def _task6_static_preflight(root: Path) -> tuple[str, cm.StaticPreflightDoc]:
    identity = cm.RuntimeIdentity(**_task6_identity_fields())
    stub_sha = hashlib.sha256(
        (REPO_ROOT / "scripts/cuda_bench_stub.py").read_bytes()
    ).hexdigest()
    doc = cm.StaticPreflightDoc(
        gpu_uuid="GPU-12345678-1234-1234-1234-123456789abc",
        driver_package_sha256="e" * 64,
        stub_sha256=stub_sha,
        corpus_verified=True,
        checks={
            "corpus": cm.FROZEN_CORPUS_SHA256,
            "incumbent_unit": cm.FROZEN_VULKAN_UNIT_SHA256,
            "incumbent_dropin": cm.FROZEN_VULKAN_DROPIN_SHA256,
            "incumbent_server": cm.FROZEN_VULKAN_RUNTIME_SHA256,
            "model": cm.FROZEN_MODEL_SHA256,
            "library_manifest": cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
            "effective_args": cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
            "flag_source": "a" * 64,
            "vision_unit": "b" * 64,
            "candidate_manifest": identity.runtime_manifest_sha256,
            "bench_root_mode": "700",
            "stub_pin": stub_sha,
        },
        timestamp=FIXED_TIMESTAMP,
    )
    fields = {
        "binding_sha256": doc.binding_sha256,
        "gpu_uuid": doc.gpu_uuid,
        "driver_package_sha256": doc.driver_package_sha256,
        "stub_sha256": doc.stub_sha256,
        "corpus_verified": doc.corpus_verified,
        "checks": dict(doc.checks),
        "timestamp": doc.timestamp,
    }
    relative = "receipts/static-preflight-task6.json"
    path = root / relative
    path.parent.mkdir(mode=0o700)
    path.write_bytes(driver.ProductionArtifactPolicy().encode("static_preflight", fields))
    os.chmod(path, 0o600)
    return relative, doc


def _task6_memfd_count() -> int:
    count = 0
    for path in (*Path("/proc").glob("[0-9]*/exe"), *Path("/proc").glob("[0-9]*/fd/*")):
        try:
            target = os.readlink(path)
        except OSError:
            continue
        if "memfd:cuda-bench-entry" in target:
            count += 1
    return count


def _assert_module_from_checkout(
    module: object,
    expected_relative: str,
) -> None:
    checkout_root = Path(__file__).resolve().parents[1]
    try:
        relative = Path(expected_relative)
        origin_value = getattr(module, "__file__")
        if (
            type(expected_relative) is not str
            or relative.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
            or type(origin_value) is not str
            or not origin_value
        ):
            raise ValueError("module_origin")
        expected_lexical = checkout_root / relative
        origin_lexical = Path(origin_value)
        if (
            expected_relative != relative.as_posix()
            or not origin_lexical.is_absolute()
            or origin_value != str(origin_lexical)
            or origin_lexical != expected_lexical
        ):
            raise ValueError("module_origin")
        expected = expected_lexical.resolve(strict=True)
        origin = origin_lexical.resolve(strict=True)
        if (
            not stat.S_ISREG(expected.stat().st_mode)
            or not stat.S_ISREG(origin.stat().st_mode)
            or origin != expected
        ):
            raise ValueError("module_origin")
    except (AttributeError, OSError, TypeError, ValueError):
        raise AssertionError("checkout_module_origin") from None


class _FixedClock:
    def __init__(self, tier: str) -> None:
        self.tier = tier

    def now_utc(self) -> str:
        return FIXED_TIMESTAMP

    def monotonic(self) -> float:
        return 0.0


def _static_test_observation() -> cli.StaticObservation:
    stub_sha = "a" * 64
    doc = cm.StaticPreflightDoc(
        gpu_uuid="GPU-01234567-89ab-cdef-0123-456789abcdef",
        driver_package_sha256="b" * 64,
        stub_sha256=stub_sha,
        corpus_verified=True,
        checks={
            "corpus": cm.FROZEN_CORPUS_SHA256,
            "incumbent_unit": cm.FROZEN_VULKAN_UNIT_SHA256,
            "incumbent_dropin": cm.FROZEN_VULKAN_DROPIN_SHA256,
            "incumbent_server": cm.FROZEN_VULKAN_RUNTIME_SHA256,
            "model": cm.FROZEN_MODEL_SHA256,
            "library_manifest": cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
            "effective_args": cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
            "flag_source": "c" * 64,
            "vision_unit": "d" * 64,
            "candidate_manifest": cm.FROZEN_CUDA_RUNTIME_MANIFEST_SHA256,
            "bench_root_mode": "700",
            "stub_pin": stub_sha,
        },
        timestamp=FIXED_TIMESTAMP,
    )
    return cli.StaticObservation(
        doc, object(), cm.frozen_rollback_manifest_preimage()
    )


def _write_candidate_file(path: Path, payload: bytes) -> tuple[str, int]:
    path.write_bytes(payload)
    os.chmod(path, 0o700 if path.name == "llama-server" else 0o600)
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _self_consistent_candidate(root: Path) -> tuple[str, str, str]:
    root.mkdir()
    cuda_sha, cuda_size = _write_candidate_file(
        root / "libggml-cuda.so", b"substitute-cuda"
    )
    server_sha, server_size = _write_candidate_file(
        root / "llama-server", b"substitute-server"
    )
    rows = (
        f"F\t{cuda_sha}\t{cuda_size}\tlibggml-cuda.so\n"
        f"F\t{server_sha}\t{server_size}\tllama-server\n"
    ).encode()
    (root / "runtime-manifest.sha256").write_bytes(rows)
    os.chmod(root / "runtime-manifest.sha256", 0o600)
    return server_sha, cuda_sha, hashlib.sha256(rows).hexdigest()


def _candidate_rows(root: Path) -> tuple[str, str, list[str]]:
    root.mkdir()
    cuda_sha, cuda_size = _write_candidate_file(
        root / "libggml-cuda.so", b"cuda"
    )
    server_sha, server_size = _write_candidate_file(
        root / "llama-server", b"server"
    )
    return (
        server_sha,
        cuda_sha,
        [
            f"F\t{cuda_sha}\t{cuda_size}\tlibggml-cuda.so\n",
            f"F\t{server_sha}\t{server_size}\tllama-server\n",
        ],
    )


def _write_runtime_manifest(root: Path, rows: list[str]) -> bytes:
    payload = "".join(rows).encode()
    path = root / "runtime-manifest.sha256"
    path.write_bytes(payload)
    os.chmod(path, 0o600)
    return payload


def _pin_candidate(
    monkeypatch: pytest.MonkeyPatch,
    *,
    server_sha: str,
    cuda_sha: str,
    manifest: bytes,
) -> None:
    monkeypatch.setattr(cm, "FROZEN_CUDA_SERVER_SHA256", server_sha)
    monkeypatch.setattr(cm, "FROZEN_CUDA_BACKEND_SHA256", cuda_sha)
    monkeypatch.setattr(
        cm,
        "FROZEN_CUDA_RUNTIME_MANIFEST_SHA256",
        hashlib.sha256(manifest).hexdigest(),
    )


class TestTask4StaticPreflight:
    def test_static_preflight_canonical_asset_paths_are_exact(self) -> None:
        paths = cli.CANONICAL_STATIC_ASSETS
        assert paths == cli.StaticAssetPaths(
            unit=Path("/home/rohit/.config/systemd/user/llama-server.service"),
            dropin=Path(
                "/home/rohit/.config/systemd/user/"
                "llama-server.service.d/mtp.conf"
            ),
            vulkan_root=cm.VULKAN_RELEASE_ROOT,
            candidate_root=cm.CUDA_RELEASE_ROOT,
            model=Path(cm.FROZEN_MODEL_PATH),
            cuda_override=Path(
                "/home/rohit/maez/config/systemd/"
                "llama-server-b9596-cuda.override.conf"
            ),
            nvcc=Path("/usr/local/cuda-13.2/bin/nvcc"),
            cmake=Path("/usr/bin/cmake"),
            nvidia_smi=Path("/usr/bin/nvidia-smi"),
            flag_source=driver.SCREEN_FLAG_SOURCE_PATH,
            vision_unit=driver.VISION_UNIT_PATH,
            stub=Path("/home/rohit/maez/scripts/cuda_bench_stub.py"),
        )

    def test_runtime_manifest_self_consistent_substitute_cannot_inherit_identity(
        self, tmp_path: Path
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, manifest_sha = _self_consistent_candidate(candidate)
        assert server_sha != cm.FROZEN_CUDA_SERVER_SHA256
        assert cuda_sha != cm.FROZEN_CUDA_BACKEND_SHA256
        assert manifest_sha != cm.FROZEN_CUDA_RUNTIME_MANIFEST_SHA256

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._verify_candidate_runtime_manifest(candidate)

    def test_runtime_manifest_symlink_cuda_backend_refuses_even_when_target_verifies(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidate = tmp_path / "candidate"
        candidate.mkdir()
        target_sha, target_size = _write_candidate_file(
            candidate / "libggml-cuda.so.1", b"cuda-backend"
        )
        (candidate / "libggml-cuda.so").symlink_to("libggml-cuda.so.1")
        server_sha, server_size = _write_candidate_file(
            candidate / "llama-server", b"server"
        )
        link_sha = hashlib.sha256(b"libggml-cuda.so.1").hexdigest()
        rows = (
            f"L\t{link_sha}\tlibggml-cuda.so\tlibggml-cuda.so.1\n"
            f"F\t{target_sha}\t{target_size}\tlibggml-cuda.so.1\n"
            f"F\t{server_sha}\t{server_size}\tllama-server\n"
        ).encode()
        (candidate / "runtime-manifest.sha256").write_bytes(rows)
        os.chmod(candidate / "runtime-manifest.sha256", 0o600)
        monkeypatch.setattr(cm, "FROZEN_CUDA_SERVER_SHA256", server_sha)
        monkeypatch.setattr(cm, "FROZEN_CUDA_BACKEND_SHA256", target_sha)
        monkeypatch.setattr(
            cm,
            "FROZEN_CUDA_RUNTIME_MANIFEST_SHA256",
            hashlib.sha256(rows).hexdigest(),
        )

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._verify_candidate_runtime_manifest(candidate)
        assert link_sha != target_sha

    def test_runtime_manifest_library_hashes_include_exact_regular_cuda_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, manifest_sha = _self_consistent_candidate(candidate)
        monkeypatch.setattr(cm, "FROZEN_CUDA_SERVER_SHA256", server_sha)
        monkeypatch.setattr(cm, "FROZEN_CUDA_BACKEND_SHA256", cuda_sha)
        monkeypatch.setattr(
            cm, "FROZEN_CUDA_RUNTIME_MANIFEST_SHA256", manifest_sha
        )

        observed = cli._verify_candidate_runtime_manifest(candidate)

        assert observed.library_hashes["libggml-cuda.so"] == cuda_sha

    @pytest.mark.parametrize("pin", ("server", "backend", "manifest"))
    def test_runtime_manifest_enforces_each_frozen_candidate_pin_independently(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin: str,
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, manifest_sha = _self_consistent_candidate(candidate)
        monkeypatch.setattr(cm, "FROZEN_CUDA_SERVER_SHA256", server_sha)
        monkeypatch.setattr(cm, "FROZEN_CUDA_BACKEND_SHA256", cuda_sha)
        monkeypatch.setattr(
            cm, "FROZEN_CUDA_RUNTIME_MANIFEST_SHA256", manifest_sha
        )
        monkeypatch.setattr(
            cm,
            {
                "server": "FROZEN_CUDA_SERVER_SHA256",
                "backend": "FROZEN_CUDA_BACKEND_SHA256",
                "manifest": "FROZEN_CUDA_RUNTIME_MANIFEST_SHA256",
            }[pin],
            "0" * 64,
        )

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._verify_candidate_runtime_manifest(candidate)

    @pytest.mark.parametrize(
        "hazard",
        (
            "grammar",
            "order",
            "duplicate",
            "control",
            "hash",
            "size",
            "unlisted",
            "vulkan",
        ),
    )
    def test_runtime_manifest_strict_candidate_hazards_refuse(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        hazard: str,
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, rows = _candidate_rows(candidate)
        if hazard == "grammar":
            rows[0] = "X\t" + rows[0][2:]
        elif hazard == "order":
            rows.reverse()
        elif hazard == "duplicate":
            rows.insert(1, rows[0])
        elif hazard == "control":
            rows[0] = rows[0].replace("libggml-cuda.so", "libggml-\x01cuda.so")
        elif hazard == "hash":
            fields = rows[0].split("\t")
            fields[1] = "0" * 64
            rows[0] = "\t".join(fields)
        elif hazard == "size":
            fields = rows[0].split("\t")
            fields[2] = str(int(fields[2]) + 1)
            rows[0] = "\t".join(fields)
        elif hazard == "unlisted":
            _write_candidate_file(candidate / "extra", b"extra")
        elif hazard == "vulkan":
            digest, size = _write_candidate_file(
                candidate / "libggml-vulkan.so", b"vulkan"
            )
            rows.insert(
                1, f"F\t{digest}\t{size}\tlibggml-vulkan.so\n"
            )
        manifest = _write_runtime_manifest(candidate, rows)
        _pin_candidate(
            monkeypatch,
            server_sha=server_sha,
            cuda_sha=cuda_sha,
            manifest=manifest,
        )

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._verify_candidate_runtime_manifest(candidate)

    @pytest.mark.parametrize(
        "hazard", ("external", "cycle", "dangling", "unlisted_target")
    )
    def test_runtime_manifest_symlink_chain_hazards_refuse(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        hazard: str,
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, rows = _candidate_rows(candidate)
        if hazard == "external":
            (candidate / "libalias.so").symlink_to("../outside")
            target = "../outside"
            rows.insert(
                1,
                "L\t"
                + hashlib.sha256(os.fsencode(target)).hexdigest()
                + f"\tlibalias.so\t{target}\n",
            )
        elif hazard == "cycle":
            (candidate / "libalias.so").symlink_to("libalias2.so")
            (candidate / "libalias2.so").symlink_to("libalias.so")
            for name, target in (
                ("libalias.so", "libalias2.so"),
                ("libalias2.so", "libalias.so"),
            ):
                rows.insert(
                    1,
                    "L\t"
                    + hashlib.sha256(os.fsencode(target)).hexdigest()
                    + f"\t{name}\t{target}\n",
                )
        elif hazard == "dangling":
            (candidate / "libalias.so").symlink_to("libmissing.so")
            target = "libmissing.so"
            rows.insert(
                1,
                "L\t"
                + hashlib.sha256(os.fsencode(target)).hexdigest()
                + f"\tlibalias.so\t{target}\n",
            )
        else:
            _write_candidate_file(candidate / "libtarget.so", b"target")
            (candidate / "libalias.so").symlink_to("libtarget.so")
            target = "libtarget.so"
            rows.insert(
                1,
                "L\t"
                + hashlib.sha256(os.fsencode(target)).hexdigest()
                + f"\tlibalias.so\t{target}\n",
            )
        rows.sort(key=lambda row: os.fsencode(row.split("\t")[2 if row.startswith("L") else 3]))
        manifest = _write_runtime_manifest(candidate, rows)
        _pin_candidate(
            monkeypatch,
            server_sha=server_sha,
            cuda_sha=cuda_sha,
            manifest=manifest,
        )

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._verify_candidate_runtime_manifest(candidate)

    @pytest.mark.parametrize("target_hash_kind", ("literal", "referent"))
    def test_runtime_manifest_auxiliary_link_hashes_literal_target_only(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        target_hash_kind: str,
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, rows = _candidate_rows(candidate)
        target_sha, target_size = _write_candidate_file(
            candidate / "libtarget.so", b"target"
        )
        target = "libtarget.so"
        (candidate / "libalias.so").symlink_to(target)
        link_sha = (
            hashlib.sha256(os.fsencode(target)).hexdigest()
            if target_hash_kind == "literal"
            else target_sha
        )
        rows.extend(
            (
                f"L\t{link_sha}\tlibalias.so\t{target}\n",
                f"F\t{target_sha}\t{target_size}\tlibtarget.so\n",
            )
        )
        rows.sort(key=lambda row: os.fsencode(row.split("\t")[2 if row.startswith("L") else 3]))
        manifest = _write_runtime_manifest(candidate, rows)
        _pin_candidate(
            monkeypatch,
            server_sha=server_sha,
            cuda_sha=cuda_sha,
            manifest=manifest,
        )

        if target_hash_kind == "referent":
            with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
                cli._verify_candidate_runtime_manifest(candidate)
        else:
            observed = cli._verify_candidate_runtime_manifest(candidate)
            assert "libalias.so" not in observed.library_hashes
            assert observed.library_hashes["libtarget.so"] == target_sha

    @pytest.mark.parametrize(
        "hazard",
        (
            "f_is_symlink",
            "self_manifest",
            "missing_field",
            "extra_field",
            "missing_newline",
            "crlf",
        ),
    )
    def test_runtime_manifest_row_shape_and_regular_file_contract_refuses(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        hazard: str,
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, rows = _candidate_rows(candidate)
        if hazard == "f_is_symlink":
            backend = candidate / "libggml-cuda.so"
            backend.rename(candidate / "libggml-cuda.so.1")
            backend.symlink_to("libggml-cuda.so.1")
        elif hazard == "self_manifest":
            rows.append(
                f"F\t{'0' * 64}\t0\truntime-manifest.sha256\n"
            )
            rows.sort(key=lambda row: os.fsencode(row.split("\t")[3]))
        elif hazard == "missing_field":
            rows[0] = "\t".join(rows[0].rstrip("\n").split("\t")[:-1]) + "\n"
        elif hazard == "extra_field":
            rows[0] = rows[0].rstrip("\n") + "\textra\n"
        elif hazard == "missing_newline":
            rows[-1] = rows[-1].rstrip("\n")
        elif hazard == "crlf":
            rows[0] = rows[0].rstrip("\n") + "\r\n"
        manifest = _write_runtime_manifest(candidate, rows)
        _pin_candidate(
            monkeypatch,
            server_sha=server_sha,
            cuda_sha=cuda_sha,
            manifest=manifest,
        )

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._verify_candidate_runtime_manifest(candidate)

    @pytest.mark.parametrize("mutation", ("add_unlisted", "replace_verified"))
    def test_runtime_manifest_refuses_bundle_drift_during_verification(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mutation: str,
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, manifest_sha = _self_consistent_candidate(candidate)
        monkeypatch.setattr(cm, "FROZEN_CUDA_SERVER_SHA256", server_sha)
        monkeypatch.setattr(cm, "FROZEN_CUDA_BACKEND_SHA256", cuda_sha)
        monkeypatch.setattr(
            cm, "FROZEN_CUDA_RUNTIME_MANIFEST_SHA256", manifest_sha
        )
        real_stable = cli._stable_regular_record_at
        fired = False

        def mutate_after_first_verified(
            directory_fd: int, name: str
        ) -> cli._StaticRegularRecord:
            nonlocal fired
            observed = real_stable(directory_fd, name)
            if not fired:
                fired = True
                if mutation == "add_unlisted":
                    _write_candidate_file(candidate / "unlisted", b"x")
                else:
                    path = candidate / name
                    path.write_bytes(b"X" * observed.size)
            return observed

        monkeypatch.setattr(
            cli, "_stable_regular_record_at", mutate_after_first_verified
        )

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._verify_candidate_runtime_manifest(candidate)

    def test_runtime_manifest_final_barrier_rebinds_canonical_candidate_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, manifest_sha = _self_consistent_candidate(candidate)
        monkeypatch.setattr(cm, "FROZEN_CUDA_SERVER_SHA256", server_sha)
        monkeypatch.setattr(cm, "FROZEN_CUDA_BACKEND_SHA256", cuda_sha)
        monkeypatch.setattr(
            cm, "FROZEN_CUDA_RUNTIME_MANIFEST_SHA256", manifest_sha
        )
        real_listdir = cli.os.listdir
        calls = 0

        def replace_after_final_listing(path: object) -> list[str]:
            nonlocal calls
            names = real_listdir(path)
            calls += 1
            if calls == 3:
                candidate.rename(tmp_path / "candidate-original")
                candidate.mkdir()
            return names

        monkeypatch.setattr(cli.os, "listdir", replace_after_final_listing)

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._verify_candidate_runtime_manifest(candidate)

        assert calls >= 3

    def test_runtime_manifest_final_barrier_rechecks_earlier_file_identity(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        candidate = tmp_path / "candidate"
        server_sha, cuda_sha, manifest_sha = _self_consistent_candidate(candidate)
        monkeypatch.setattr(cm, "FROZEN_CUDA_SERVER_SHA256", server_sha)
        monkeypatch.setattr(cm, "FROZEN_CUDA_BACKEND_SHA256", cuda_sha)
        monkeypatch.setattr(
            cm, "FROZEN_CUDA_RUNTIME_MANIFEST_SHA256", manifest_sha
        )
        real_stable = cli._stable_regular_record_at
        calls = 0

        def mutate_earlier_before_later_completes(
            directory_fd: int, name: str
        ) -> cli._StaticRegularRecord:
            nonlocal calls
            calls += 1
            if calls == 4:
                backend = candidate / "libggml-cuda.so"
                backend.write_bytes(b"X" * backend.stat().st_size)
            return real_stable(directory_fd, name)

        monkeypatch.setattr(
            cli,
            "_stable_regular_record_at",
            mutate_earlier_before_later_completes,
        )

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._verify_candidate_runtime_manifest(candidate)

        assert calls == 4

    def test_host_observation_enumerates_one_gpu_and_scopes_every_query(
        self, tmp_path: Path
    ) -> None:
        calls: list[tuple[str, ...]] = []
        paths = cli.StaticAssetPaths(
            *(tmp_path / name for name in (
                "unit", "dropin", "vulkan", "candidate", "model",
                "override", "nvcc", "cmake", "nvidia-smi", "flag",
                "vision", "stub",
            ))
        )

        def runner(
            argv: tuple[str, ...], *, timeout_s: int
        ) -> subprocess.CompletedProcess[str]:
            assert timeout_s > 0
            calls.append(argv)
            if argv[0] == str(paths.nvcc):
                out = "Cuda compilation tools, release 13.2, V13.2.78\n"
            elif argv[0] == str(paths.cmake):
                out = "cmake version 4.2.3\n\nCMake suite maintained.\n"
            elif "--query-gpu=uuid" in argv:
                out = "GPU-01234567-89ab-cdef-0123-456789abcdef\n"
            else:
                out = "595.71.05, NVIDIA GeForce RTX 4090, 8.9\n"
            return subprocess.CompletedProcess(argv, 0, out, "")

        observed = cli._collect_host_tool_observations(
            runner=runner, paths=paths
        )

        assert observed.cmake_version == "4.2.3"
        assert observed.cuda_compiler == "13.2.78"
        gpu_calls = [call for call in calls if call[0] == str(paths.nvidia_smi)]
        assert len(gpu_calls) == 2
        assert "-i" not in gpu_calls[0]
        assert gpu_calls[1][gpu_calls[1].index("-i") + 1] == observed.gpu_uuid
        assert all(Path(call[0]).is_absolute() for call in calls)

    @pytest.mark.parametrize(
        "rows",
        (
            "",
            "GPU-01234567-89ab-cdef-0123-456789abcdef\n"
            "GPU-11234567-89ab-cdef-0123-456789abcdef\n",
        ),
    )
    def test_host_observation_refuses_non_single_gpu(
        self, tmp_path: Path, rows: str
    ) -> None:
        paths = cli.StaticAssetPaths(
            *(tmp_path / name for name in (
                "unit", "dropin", "vulkan", "candidate", "model",
                "override", "nvcc", "cmake", "nvidia-smi", "flag",
                "vision", "stub",
            ))
        )

        def runner(
            argv: tuple[str, ...], *, timeout_s: int
        ) -> subprocess.CompletedProcess[str]:
            del timeout_s
            if "--query-gpu=uuid" in argv:
                return subprocess.CompletedProcess(argv, 0, rows, "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        with pytest.raises(driver.BenchRefusal, match="gpu_scope_violation"):
            cli._collect_host_tool_observations(runner=runner, paths=paths)

    def test_host_observation_refuses_malformed_gpu_uuid(
        self, tmp_path: Path
    ) -> None:
        paths = cli.StaticAssetPaths(
            *(tmp_path / name for name in (
                "unit", "dropin", "vulkan", "candidate", "model",
                "override", "nvcc", "cmake", "nvidia-smi", "flag",
                "vision", "stub",
            ))
        )

        def runner(
            argv: tuple[str, ...], *, timeout_s: int
        ) -> subprocess.CompletedProcess[str]:
            del timeout_s
            return subprocess.CompletedProcess(argv, 0, "GPU-not-a-uuid\n", "")

        with pytest.raises(driver.BenchRefusal, match="gpu_scope_violation"):
            cli._collect_host_tool_observations(runner=runner, paths=paths)

    @pytest.mark.parametrize(
        "metadata",
        (
            "",
            "595.71.05, RTX 4090, 8.9\n595.71.05, RTX 4090, 8.9\n",
            "missing,columns\n",
        ),
    )
    def test_host_observation_refuses_malformed_metadata_rows(
        self, tmp_path: Path, metadata: str
    ) -> None:
        paths = cli.StaticAssetPaths(
            *(tmp_path / name for name in (
                "unit", "dropin", "vulkan", "candidate", "model",
                "override", "nvcc", "cmake", "nvidia-smi", "flag",
                "vision", "stub",
            ))
        )

        def runner(
            argv: tuple[str, ...], *, timeout_s: int
        ) -> subprocess.CompletedProcess[str]:
            del timeout_s
            output = (
                "GPU-01234567-89ab-cdef-0123-456789abcdef\n"
                if "--query-gpu=uuid" in argv
                else metadata
            )
            return subprocess.CompletedProcess(argv, 0, output, "")

        with pytest.raises(driver.BenchRefusal, match="provider_uncertain"):
            cli._collect_host_tool_observations(runner=runner, paths=paths)

    @pytest.mark.parametrize(
        "hazard", ("nonzero", "exception", "non_string", "oversized")
    )
    def test_host_runner_refuses_each_untrusted_result_shape(
        self, hazard: str
    ) -> None:
        def runner(
            argv: tuple[str, ...], *, timeout_s: int
        ) -> subprocess.CompletedProcess[str]:
            del timeout_s
            if hazard == "exception":
                raise TimeoutError("private output")
            if hazard == "nonzero":
                return subprocess.CompletedProcess(argv, 1, "private", "private")
            if hazard == "non_string":
                return subprocess.CompletedProcess(argv, 0, b"bytes", b"")
            return subprocess.CompletedProcess(argv, 0, "x" * (64 * 1024 + 1), "")

        with pytest.raises(driver.BenchRefusal, match="provider_uncertain") as exc:
            cli._runner_stdout(runner, ("/absolute/tool",))
        assert "private" not in str(exc.value)

    def test_read_only_runner_uses_exact_sanitized_subprocess_contract(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observed: dict[str, object] = {}

        def fake_run(
            argv: tuple[str, ...], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            observed["argv"] = argv
            observed.update(kwargs)
            return subprocess.CompletedProcess(argv, 0, "ok", "")

        monkeypatch.setattr(cli.subprocess, "run", fake_run)
        result = cli._run_read_only(("/usr/bin/tool", "--version"), timeout_s=7)

        assert result.returncode == 0
        assert observed == {
            "argv": ("/usr/bin/tool", "--version"),
            "env": {
                "HOME": "/home/rohit",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
            "shell": False,
            "timeout": 7,
            "capture_output": True,
            "text": True,
            "check": False,
        }

    @pytest.mark.parametrize(
        "hazard", ("nvcc_release", "nvcc_patch", "cmake_prefix", "cmake_version")
    )
    def test_host_observation_refuses_malformed_nvcc_or_cmake(
        self, tmp_path: Path, hazard: str
    ) -> None:
        paths = cli.StaticAssetPaths(
            *(tmp_path / name for name in (
                "unit", "dropin", "vulkan", "candidate", "model",
                "override", "nvcc", "cmake", "nvidia-smi", "flag",
                "vision", "stub",
            ))
        )

        def runner(
            argv: tuple[str, ...], *, timeout_s: int
        ) -> subprocess.CompletedProcess[str]:
            del timeout_s
            if "--query-gpu=uuid" in argv:
                output = "GPU-01234567-89ab-cdef-0123-456789abcdef\n"
            elif argv[0] == str(paths.nvidia_smi):
                output = "595.71.05, NVIDIA GeForce RTX 4090, 8.9\n"
            elif argv[0] == str(paths.nvcc):
                output = {
                    "nvcc_release": (
                        "Cuda compilation tools, release 13.1, V13.1.1\n"
                    ),
                    "nvcc_patch": (
                        "Cuda compilation tools, release 13.2, V13.2.1234\n"
                    ),
                }.get(
                    hazard,
                    "Cuda compilation tools, release 13.2, V13.2.78\n",
                )
            else:
                output = {
                    "cmake_prefix": "prefix cmake version 4.2.3\n",
                    "cmake_version": "cmake version 5.0.0\n",
                }.get(hazard, "cmake version 4.2.3\n")
            return subprocess.CompletedProcess(argv, 0, output, "")

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._collect_host_tool_observations(runner=runner, paths=paths)

    @pytest.mark.parametrize(
        "hazard", ("size", "hash", "count", "empty")
    )
    def test_static_preflight_corpus_contract_refuses_each_invalid_shape(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        hazard: str,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        values = ["x" * 257, *(["x"] * 6)]
        if hazard == "count":
            values = ["x" * 261, *(["x"] * 5)]
        elif hazard == "empty":
            values = ["x" * 258, "", *(["x"] * 5)]
        payload = json.dumps(values, separators=(",", ":")).encode()
        assert len(payload) == 285
        corpus = root / "corpus.json"
        corpus.write_bytes(payload)
        os.chmod(corpus, 0o600)
        monkeypatch.setattr(
            cm, "FROZEN_CORPUS_SHA256", hashlib.sha256(payload).hexdigest()
        )
        if hazard == "size":
            corpus.write_bytes(payload[:-1])
        elif hazard == "hash":
            corpus.write_bytes(payload[:-1] + b"!")

        with pytest.raises(driver.BenchRefusal, match="corpus_unavailable"):
            cli._validate_frozen_corpus(root=root)

    def test_static_preflight_corpus_contract_accepts_exact_seven_nonempty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        payload = json.dumps(
            ["x" * 257, *(["x"] * 6)], separators=(",", ":")
        ).encode()
        assert len(payload) == 285
        corpus = root / "corpus.json"
        corpus.write_bytes(payload)
        os.chmod(corpus, 0o600)
        expected = hashlib.sha256(payload).hexdigest()
        monkeypatch.setattr(cm, "FROZEN_CORPUS_SHA256", expected)

        assert cli._validate_frozen_corpus(root=root) == tuple(
            json.loads(payload)
        )

    def test_driver_package_identity_is_ordered_five_file_preimage(self) -> None:
        digest, preimage = cli._driver_package_sha256()
        rows = json.loads(preimage)
        assert [row[0] for row in rows] == [
            "scripts/cuda_migration.py",
            "scripts/cuda_bench_driver.py",
            "scripts/cuda_bench_stub.py",
            "scripts/cuda_bench_cli.py",
            "scripts/cuda_bench_assemble.py",
        ]
        assert hashlib.sha256(preimage).hexdigest() == digest

    def test_driver_package_member_order_and_byte_drift_change_identity(
        self, tmp_path: Path
    ) -> None:
        members = tuple(f"scripts/member-{index}.py" for index in range(5))
        for index, relative in enumerate(members):
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"member-{index}".encode())
            os.chmod(path, 0o600)

        baseline, _ = cli._driver_package_sha256(
            repo_root=tmp_path, members=members
        )
        reordered, _ = cli._driver_package_sha256(
            repo_root=tmp_path, members=tuple(reversed(members))
        )
        changed = tmp_path / members[0]
        changed.write_bytes(b"changed")
        byte_drift, _ = cli._driver_package_sha256(
            repo_root=tmp_path, members=members
        )
        substitute = tmp_path / "scripts/substitute.py"
        substitute.write_bytes(b"substitute")
        os.chmod(substitute, 0o600)
        member_drift, _ = cli._driver_package_sha256(
            repo_root=tmp_path,
            members=(*members[:-1], "scripts/substitute.py"),
        )

        assert len({baseline, reordered, byte_drift, member_drift}) == 4

    @pytest.mark.parametrize(
        "field",
        (
            "unit_sha256",
            "dropin_sha256",
            "vulkan_runtime_sha256",
            "vulkan_library_manifest_sha256",
            "model_sha256",
            "model_bytes",
            "alias",
            "effective_args",
        ),
    )
    def test_rollback_preimage_refuses_each_named_input_drift(
        self,
        monkeypatch: pytest.MonkeyPatch,
        field: str,
    ) -> None:
        assets = cli._AssetObservation(
            unit_sha256=cm.FROZEN_VULKAN_UNIT_SHA256,
            dropin_sha256=cm.FROZEN_VULKAN_DROPIN_SHA256,
            vulkan_runtime_sha256=cm.FROZEN_VULKAN_RUNTIME_SHA256,
            vulkan_library_manifest_sha256=(
                cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256
            ),
            model_sha256=cm.FROZEN_MODEL_SHA256,
            model_bytes=cm.FROZEN_MODEL_BYTES,
            override_sha256="a" * 64,
            flag_source_sha256="b" * 64,
            vision_unit_sha256="c" * 64,
            stub_sha256="d" * 64,
        )
        if field == "alias":
            monkeypatch.setattr(cm, "FROZEN_ALIAS", "different")
        elif field == "effective_args":
            monkeypatch.setattr(
                cm, "FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256", "0" * 64
            )
        elif field == "model_bytes":
            assets = replace(assets, model_bytes=assets.model_bytes + 1)
        else:
            assets = replace(assets, **{field: "0" * 64})

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._build_rollback_preimage(assets)

    @pytest.mark.parametrize(
        "hazard", ("symlink", "directory", "inode_swap", "in_place")
    )
    def test_static_external_file_stability_hazards_refuse(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        hazard: str,
    ) -> None:
        path = tmp_path / "asset"
        if hazard == "directory":
            path.mkdir()
        else:
            path.write_bytes(b"original")
            os.chmod(path, 0o600)
        if hazard == "symlink":
            target = tmp_path / "target"
            path.rename(target)
            path.symlink_to(target)
        real_read = cli.os.read
        fired = False

        def mutate_after_read(fd: int, size: int) -> bytes:
            nonlocal fired
            payload = real_read(fd, size)
            if payload and not fired:
                fired = True
                if hazard == "inode_swap":
                    path.rename(tmp_path / "old")
                    path.write_bytes(b"original")
                    os.chmod(path, 0o600)
                elif hazard == "in_place":
                    path.write_bytes(b"changed!")
            return payload

        if hazard in {"inode_swap", "in_place"}:
            monkeypatch.setattr(cli.os, "read", mutate_after_read)

        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._stable_regular_file(path)

    def test_vulkan_manifest_serializes_files_and_literal_links_from_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "vulkan"
        root.mkdir()
        expected_rows: list[dict[str, object]] = []
        for index in range(36):
            name = f"lib{index:02d}.so"
            payload = f"payload-{index}".encode()
            path = root / name
            path.write_bytes(payload)
            os.chmod(path, 0o600)
            expected_rows.append(
                {
                    "path": name,
                    "type": "file",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                }
            )
        for index in range(3):
            name = f"libalias{index}.so"
            target = f"lib{index:02d}.so"
            (root / name).symlink_to(target)
            expected_rows.append(
                {"path": name, "type": "symlink", "target": target}
            )
        expected_rows.sort(key=lambda row: os.fsencode(str(row["path"])))
        preimage = json.dumps(
            expected_rows,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        expected = hashlib.sha256(preimage).hexdigest()
        monkeypatch.setattr(
            cm, "FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256", expected
        )

        assert cli._vulkan_library_manifest(root) == expected

    def test_static_symlink_read_refuses_identity_change(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        (root / "target-a").write_bytes(b"a")
        (root / "target-b").write_bytes(b"b")
        link = root / "libalias.so"
        link.symlink_to("target-a")
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        real_readlink = cli.os.readlink
        fired = False

        def swap_after_read(
            path: object, *, dir_fd: int | None = None
        ) -> str:
            nonlocal fired
            target = real_readlink(path, dir_fd=dir_fd)
            if not fired:
                fired = True
                link.unlink()
                link.symlink_to("target-b")
            return target

        monkeypatch.setattr(cli.os, "readlink", swap_after_read)
        try:
            with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
                cli._stable_symlink_at(directory_fd, "libalias.so")
        finally:
            os.close(directory_fd)

    def test_static_asset_collector_reads_exact_named_assets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vulkan = tmp_path / "vulkan"
        vulkan.mkdir()
        paths = cli.StaticAssetPaths(
            unit=tmp_path / "unit",
            dropin=tmp_path / "dropin",
            vulkan_root=vulkan,
            candidate_root=tmp_path / "candidate",
            model=tmp_path / "model",
            cuda_override=tmp_path / "override",
            nvcc=tmp_path / "nvcc",
            cmake=tmp_path / "cmake",
            nvidia_smi=tmp_path / "nvidia-smi",
            flag_source=tmp_path / "flag",
            vision_unit=tmp_path / "vision",
            stub=tmp_path / "stub",
        )
        assets = {
            paths.unit: b"unit",
            paths.dropin: b"dropin",
            vulkan / "llama-server": b"vulkan-runtime",
            paths.model: b"model",
            paths.cuda_override: b"override",
            paths.flag_source: b"flag",
            paths.vision_unit: b"vision",
            paths.stub: b"stub",
        }
        for path, payload in assets.items():
            path.write_bytes(payload)
            os.chmod(path, 0o600)
        monkeypatch.setattr(
            cm,
            "FROZEN_VULKAN_UNIT_SHA256",
            hashlib.sha256(assets[paths.unit]).hexdigest(),
        )
        monkeypatch.setattr(
            cm,
            "FROZEN_VULKAN_DROPIN_SHA256",
            hashlib.sha256(assets[paths.dropin]).hexdigest(),
        )
        monkeypatch.setattr(
            cm,
            "FROZEN_VULKAN_RUNTIME_SHA256",
            hashlib.sha256(assets[vulkan / "llama-server"]).hexdigest(),
        )
        monkeypatch.setattr(
            cm,
            "FROZEN_MODEL_SHA256",
            hashlib.sha256(assets[paths.model]).hexdigest(),
        )
        monkeypatch.setattr(cm, "FROZEN_MODEL_BYTES", len(assets[paths.model]))
        monkeypatch.setattr(
            cli,
            "_vulkan_library_manifest",
            lambda root: (
                cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256
                if root == vulkan
                else (_ for _ in ()).throw(AssertionError("wrong root"))
            ),
        )

        observed = cli._collect_static_asset_hashes(paths)

        assert observed.override_sha256 == hashlib.sha256(
            assets[paths.cuda_override]
        ).hexdigest()
        assert observed.flag_source_sha256 == hashlib.sha256(
            assets[paths.flag_source]
        ).hexdigest()
        assert observed.vision_unit_sha256 == hashlib.sha256(
            assets[paths.vision_unit]
        ).hexdigest()
        assert observed.stub_sha256 == hashlib.sha256(
            assets[paths.stub]
        ).hexdigest()

    def test_static_preflight_collector_builds_one_shared_truthful_observation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assets = cli._AssetObservation(
            unit_sha256=cm.FROZEN_VULKAN_UNIT_SHA256,
            dropin_sha256=cm.FROZEN_VULKAN_DROPIN_SHA256,
            vulkan_runtime_sha256=cm.FROZEN_VULKAN_RUNTIME_SHA256,
            vulkan_library_manifest_sha256=(
                cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256
            ),
            model_sha256=cm.FROZEN_MODEL_SHA256,
            model_bytes=cm.FROZEN_MODEL_BYTES,
            override_sha256="a" * 64,
            flag_source_sha256="b" * 64,
            vision_unit_sha256="c" * 64,
            stub_sha256="d" * 64,
        )
        candidate = cli._CandidateObservation(
            runtime_sha256=cm.FROZEN_CUDA_SERVER_SHA256,
            runtime_manifest_sha256=cm.FROZEN_CUDA_RUNTIME_MANIFEST_SHA256,
            library_hashes={
                "libggml-cuda.so": cm.FROZEN_CUDA_BACKEND_SHA256
            },
        )
        host = cli._HostObservation(
            gpu_uuid="GPU-01234567-89ab-cdef-0123-456789abcdef",
            driver_version="595.71.05",
            gpu_identifier="NVIDIA GeForce RTX 4090",
            compute_capability="8.9",
            cuda_compiler="13.2.78",
            cmake_version="4.2.3",
        )
        monkeypatch.setattr(
            cli,
            "_validate_frozen_corpus",
            lambda **_kwargs: tuple(f"prompt-{index}" for index in range(7)),
        )
        monkeypatch.setattr(
            cli, "_collect_static_asset_hashes", lambda _paths: assets
        )
        monkeypatch.setattr(
            cli,
            "_verify_candidate_runtime_manifest",
            lambda _root: candidate,
        )
        monkeypatch.setattr(
            cli,
            "_collect_host_tool_observations",
            lambda **_kwargs: host,
        )
        monkeypatch.setattr(
            cli,
            "_driver_package_sha256",
            lambda: ("e" * 64, b"package-preimage"),
        )
        paths = cli.StaticAssetPaths(
            *(tmp_path / name for name in (
                "unit", "dropin", "vulkan", "candidate", "model",
                "override", "nvcc", "cmake", "nvidia-smi", "flag",
                "vision", "stub",
            ))
        )

        observed = cli.collect_static_observation(
            root=tmp_path,
            paths=paths,
            runner=lambda *_args, **_kwargs: None,
            clock=_FixedClock("production"),
        )

        assert observed.rollback_preimage == cm.frozen_rollback_manifest_preimage()
        assert observed.runtime_identity.mode == "bench"
        assert observed.runtime_identity.cmake_version == "4.2.3"
        assert observed.runtime_identity.runtime_sha256 == (
            cm.FROZEN_CUDA_SERVER_SHA256
        )
        assert observed.static_doc.gpu_uuid == host.gpu_uuid
        assert observed.static_doc.checks["candidate_manifest"] == (
            cm.FROZEN_CUDA_RUNTIME_MANIFEST_SHA256
        )

    def test_static_preflight_dispatches_real_handler_not_placeholder(self) -> None:
        source = inspect.getsource(cli.main)
        assert "_static_preflight_handler" in source

    def test_static_preflight_persists_preimage_and_typed_receipt(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        preimage = cm.frozen_rollback_manifest_preimage()
        stub_sha = "a" * 64
        doc = cm.StaticPreflightDoc(
            gpu_uuid="GPU-01234567-89ab-cdef-0123-456789abcdef",
            driver_package_sha256="b" * 64,
            stub_sha256=stub_sha,
            corpus_verified=True,
            checks={
                "corpus": cm.FROZEN_CORPUS_SHA256,
                "incumbent_unit": cm.FROZEN_VULKAN_UNIT_SHA256,
                "incumbent_dropin": cm.FROZEN_VULKAN_DROPIN_SHA256,
                "incumbent_server": cm.FROZEN_VULKAN_RUNTIME_SHA256,
                "model": cm.FROZEN_MODEL_SHA256,
                "library_manifest": cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
                "effective_args": cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
                "flag_source": "c" * 64,
                "vision_unit": "d" * 64,
                "candidate_manifest": cm.FROZEN_CUDA_RUNTIME_MANIFEST_SHA256,
                "bench_root_mode": "700",
                "stub_pin": stub_sha,
            },
            timestamp=FIXED_TIMESTAMP,
        )
        observation = cli.StaticObservation(doc, object(), preimage)
        monkeypatch.setattr(
            cli,
            "collect_static_observation",
            lambda **_kwargs: observation,
        )

        def handler(attempt: driver.CommandAttempt, *, root: Path) -> object:
            return cli._static_preflight_handler(
                attempt,
                root=root,
                clock=_FixedClock("production"),
            )

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()

        assert exit_status == 0
        terminal = _one_terminal_line(captured.out)
        assert captured.err == ""
        assert terminal["outcome"] == "static_preflight_ready"
        assert terminal["artifact_ref"].endswith("-terminal.json")
        completion_path = root / terminal["artifact_ref"]
        assert completion_path.is_file()
        preimage_path = (
            root
            / "preimages"
            / (
                "rollback-manifest-"
                + hashlib.sha256(preimage).hexdigest()
                + ".json"
            )
        )
        assert preimage_path.read_bytes() == preimage
        persisted = cm.PersistedDoc(completion_path.read_bytes())
        assert isinstance(persisted.obj, cm.CommandCompletionDoc)
        completion = persisted.obj
        assert completion.command == "static-preflight"
        assert completion.admission_ref.endswith("-admission.json")
        assert completion.admission_sha256 == hashlib.sha256(
            (root / completion.admission_ref).read_bytes()
        ).hexdigest()
        static_path = root / completion.artifact_ref
        assert static_path.is_file()
        assert completion.artifact_sha256 == hashlib.sha256(
            static_path.read_bytes()
        ).hexdigest()
        static_persisted = cm.PersistedDoc(static_path.read_bytes())
        assert static_persisted.obj == doc

    def test_static_preflight_receipt_failure_keeps_preimage_and_cites_admission(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        preimage = cm.frozen_rollback_manifest_preimage()
        stub_sha = "a" * 64
        doc = cm.StaticPreflightDoc(
            gpu_uuid="GPU-01234567-89ab-cdef-0123-456789abcdef",
            driver_package_sha256="b" * 64,
            stub_sha256=stub_sha,
            corpus_verified=True,
            checks={
                "corpus": cm.FROZEN_CORPUS_SHA256,
                "incumbent_unit": cm.FROZEN_VULKAN_UNIT_SHA256,
                "incumbent_dropin": cm.FROZEN_VULKAN_DROPIN_SHA256,
                "incumbent_server": cm.FROZEN_VULKAN_RUNTIME_SHA256,
                "model": cm.FROZEN_MODEL_SHA256,
                "library_manifest": cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
                "effective_args": cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
                "flag_source": "c" * 64,
                "vision_unit": "d" * 64,
                "candidate_manifest": cm.FROZEN_CUDA_RUNTIME_MANIFEST_SHA256,
                "bench_root_mode": "700",
                "stub_pin": stub_sha,
            },
            timestamp=FIXED_TIMESTAMP,
        )
        monkeypatch.setattr(
            cli,
            "collect_static_observation",
            lambda **_kwargs: cli.StaticObservation(doc, object(), preimage),
        )
        monkeypatch.setattr(
            driver,
            "write_private_file",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                driver.BenchRefusal("filesystem_hazard")
            ),
        )

        def handler(attempt: driver.CommandAttempt, *, root: Path) -> object:
            return cli._static_preflight_handler(
                attempt,
                root=root,
                clock=_FixedClock("production"),
            )

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)
        admission = next(root.glob("*-admission.json"))

        assert exit_status == 3
        assert captured.err == ""
        assert terminal == {
            "status": "refused",
            "outcome": "filesystem_hazard",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(admission.read_bytes()).hexdigest(),
        }
        assert not next(root.glob("*-terminal.json"), None)
        preimage_path = (
            root
            / "preimages"
            / (
                "rollback-manifest-"
                + hashlib.sha256(preimage).hexdigest()
                + ".json"
            )
        )
        assert preimage_path.read_bytes() == preimage

    def test_static_preflight_preimage_failure_cites_admission_and_mints_no_receipt(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        preimage = cm.frozen_rollback_manifest_preimage()
        stub_sha = "a" * 64
        doc = cm.StaticPreflightDoc(
            gpu_uuid="GPU-01234567-89ab-cdef-0123-456789abcdef",
            driver_package_sha256="b" * 64,
            stub_sha256=stub_sha,
            corpus_verified=True,
            checks={
                "corpus": cm.FROZEN_CORPUS_SHA256,
                "incumbent_unit": cm.FROZEN_VULKAN_UNIT_SHA256,
                "incumbent_dropin": cm.FROZEN_VULKAN_DROPIN_SHA256,
                "incumbent_server": cm.FROZEN_VULKAN_RUNTIME_SHA256,
                "model": cm.FROZEN_MODEL_SHA256,
                "library_manifest": cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
                "effective_args": cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
                "flag_source": "c" * 64,
                "vision_unit": "d" * 64,
                "candidate_manifest": cm.FROZEN_CUDA_RUNTIME_MANIFEST_SHA256,
                "bench_root_mode": "700",
                "stub_pin": stub_sha,
            },
            timestamp=FIXED_TIMESTAMP,
        )
        monkeypatch.setattr(
            cli,
            "collect_static_observation",
            lambda **_kwargs: cli.StaticObservation(doc, object(), preimage),
        )
        monkeypatch.setattr(
            driver,
            "publish_or_verify_immutable",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                driver.BenchRefusal("filesystem_hazard")
            ),
        )

        def handler(attempt: driver.CommandAttempt, *, root: Path) -> object:
            return cli._static_preflight_handler(
                attempt,
                root=root,
                clock=_FixedClock("production"),
            )

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)
        admission = next(root.glob("*-admission.json"))

        assert exit_status == 3
        assert captured.err == ""
        assert terminal["outcome"] == "filesystem_hazard"
        assert terminal["artifact_ref"] == admission.name
        assert terminal["artifact_sha256"] == hashlib.sha256(
            admission.read_bytes()
        ).hexdigest()
        assert not next(root.glob("receipts/*"), None)
        assert not next(root.glob("*-terminal.json"), None)

    def test_static_preflight_signal_after_artifact_refuses_without_completion(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        observation = _static_test_observation()
        monkeypatch.setattr(
            cli,
            "collect_static_observation",
            lambda **_kwargs: observation,
        )
        real_write = driver.write_private_file
        signalled = False

        def write_then_signal(
            relative: str, data: bytes, *, root: Path
        ) -> Path:
            nonlocal signalled
            path = real_write(relative, data, root=root)
            if relative.startswith("receipts/static-preflight-"):
                signalled = True
                os.kill(os.getpid(), signal.SIGTERM)
            return path

        monkeypatch.setattr(driver, "write_private_file", write_then_signal)

        def handler(attempt: driver.CommandAttempt, *, root: Path) -> object:
            return cli._static_preflight_handler(
                attempt,
                root=root,
                clock=_FixedClock("production"),
            )

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)

        assert signalled
        assert exit_status == 128 + signal.SIGTERM
        assert captured.err == ""
        assert terminal["status"] == "refused"
        assert terminal["outcome"] == "interrupted"
        admission = next(root.glob("*-admission.json"))
        assert terminal["artifact_ref"] == admission.name
        assert hashlib.sha256(admission.read_bytes()).hexdigest() == (
            terminal["artifact_sha256"]
        )
        orphan = next(root.glob("receipts/static-preflight-*.json"))
        assert isinstance(
            cm.PersistedDoc(orphan.read_bytes()).obj,
            cm.StaticPreflightDoc,
        )
        assert not next(root.glob("*-terminal.json"), None)

    def test_sigkill_before_completion_link_leaves_inadmissible_static_orphan(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)

        result = _run_static_completion_hard_death_subprocess(root)

        assert result.returncode == -signal.SIGKILL
        assert result.stdout == ""
        assert result.stderr == ""
        static_orphan = next(root.glob("receipts/static-preflight-*.json"))
        assert isinstance(
            cm.PersistedDoc(static_orphan.read_bytes()).obj,
            cm.StaticPreflightDoc,
        )
        assert not next(root.glob("*-terminal.json"), None)
        next_attempt = driver._admit_command(
            command="static-preflight",
            window_id=None,
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=root,
        )
        assert next_attempt.ordinal == 2
        assert next_attempt.admission_ref.endswith(
            "attempt-002-admission.json"
        )

    @pytest.mark.parametrize("signum", (signal.SIGINT, signal.SIGTERM))
    def test_static_completion_wins_signal_after_exact_validation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
        signum: signal.Signals,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        monkeypatch.setattr(
            cli,
            "collect_static_observation",
            lambda **_kwargs: _static_test_observation(),
        )
        real_publish = driver.publish_command_artifact
        callback_calls = 0

        def publish_then_signal(
            attempt: driver.CommandAttempt,
            role: str,
            encoded: bytes,
            *,
            root: Path,
            on_committed: Callable[[str, str], None] | None = None,
        ) -> tuple[str, str]:
            nonlocal callback_calls
            assert on_committed is not None

            def latch_then_signal(relative: str, digest: str) -> None:
                nonlocal callback_calls
                on_committed(relative, digest)
                callback_calls += 1
                os.kill(os.getpid(), signum)

            return real_publish(
                attempt,
                role,
                encoded,
                root=root,
                on_committed=latch_then_signal,
            )

        monkeypatch.setattr(
            driver,
            "publish_command_artifact",
            publish_then_signal,
        )

        def handler(attempt: driver.CommandAttempt, *, root: Path) -> object:
            return cli._static_preflight_handler(
                attempt,
                root=root,
                clock=_FixedClock("production"),
            )

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)

        assert exit_status == 0
        assert captured.err == ""
        assert terminal["status"] == "ok"
        assert terminal["outcome"] == "static_preflight_ready"
        assert callback_calls == 1
        completion_path = root / str(terminal["artifact_ref"])
        completion = cm.PersistedDoc(completion_path.read_bytes()).obj
        assert type(completion) is cm.CommandCompletionDoc

    def test_static_preflight_signal_before_receipt_refuses_without_orphan(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        observation = _static_test_observation()
        monkeypatch.setattr(
            cli,
            "collect_static_observation",
            lambda **_kwargs: observation,
        )
        real_publish = driver.publish_or_verify_immutable

        def publish_then_signal(*args: object, **kwargs: object) -> Path:
            path = real_publish(*args, **kwargs)
            os.kill(os.getpid(), signal.SIGTERM)
            return path

        monkeypatch.setattr(
            driver, "publish_or_verify_immutable", publish_then_signal
        )

        def handler(attempt: driver.CommandAttempt, *, root: Path) -> object:
            return cli._static_preflight_handler(
                attempt,
                root=root,
                clock=_FixedClock("production"),
            )

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)
        admission = next(root.glob("*-admission.json"))

        assert exit_status == 128 + signal.SIGTERM
        assert captured.err == ""
        assert terminal["status"] == "refused"
        assert terminal["outcome"] == "interrupted"
        assert terminal["artifact_ref"] == admission.name
        assert terminal["artifact_sha256"] == hashlib.sha256(
            admission.read_bytes()
        ).hexdigest()
        assert not next(root.glob("receipts/*"), None)

    def test_static_preflight_latched_success_reproves_receipt_before_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        observation = _static_test_observation()
        monkeypatch.setattr(
            cli,
            "collect_static_observation",
            lambda **_kwargs: observation,
        )

        def handler(attempt: driver.CommandAttempt, *, root: Path) -> object:
            completed = cli._static_preflight_handler(
                attempt,
                root=root,
                clock=_FixedClock("production"),
            )
            (root / str(completed.artifact_ref)).unlink()
            return completed

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)
        admission = next(root.glob("*-admission.json"))

        assert exit_status == 4
        assert captured.err == ""
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "provider_uncertain"
        assert terminal["artifact_ref"] == admission.name
        assert terminal["artifact_sha256"] == hashlib.sha256(
            admission.read_bytes()
        ).hexdigest()

    @pytest.mark.parametrize(
        "mutation",
        (
            "in_place",
            "delete",
            "replace_inode",
            "mode",
            "hardlink",
            "root_substitution",
        ),
    )
    def test_static_preflight_latch_failure_after_normalize_never_commits_success(
        self,
        mutation: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        monkeypatch.setattr(
            cli,
            "collect_static_observation",
            lambda **_kwargs: _static_test_observation(),
        )
        real_normalize = cli._normalize_handler_result
        real_reprove = cli._durable_success_latch_is_current
        admission_binding: tuple[str, str] | None = None
        observed_masks: list[set[int]] = []

        def normalize_then_mutate(
            attempt: driver.CommandAttempt,
            value: object,
            *,
            root: Path,
        ) -> cli.TerminalResult:
            nonlocal admission_binding
            normalized = real_normalize(attempt, value, root=root)
            assert normalized.status == "ok"
            assert normalized.artifact_ref is not None
            receipt = root / normalized.artifact_ref
            admission_binding = (
                attempt.admission_ref,
                attempt.admission_sha256,
            )
            if mutation == "in_place":
                payload = bytearray(receipt.read_bytes())
                payload[0] ^= 1
                receipt.write_bytes(payload)
                os.chmod(receipt, 0o600)
            elif mutation == "delete":
                receipt.unlink()
            elif mutation == "replace_inode":
                payload = receipt.read_bytes()
                receipt.unlink()
                receipt.write_bytes(payload)
                os.chmod(receipt, 0o600)
            elif mutation == "mode":
                os.chmod(receipt, 0o640)
            elif mutation == "hardlink":
                os.link(receipt, root / "receipt-hardlink")
            elif mutation == "root_substitution":
                displaced = root.with_name("bench-displaced")
                root.rename(displaced)
                root.mkdir(mode=0o700)
                os.chmod(root, 0o700)
            else:  # pragma: no cover - parameter list is closed above.
                raise AssertionError(mutation)
            return normalized

        def observe_reproof_mask(latch: object) -> bool:
            current = signal.pthread_sigmask(signal.SIG_BLOCK, set())
            observed_masks.append({int(item) for item in current})
            return real_reprove(latch)

        monkeypatch.setattr(cli, "_normalize_handler_result", normalize_then_mutate)
        monkeypatch.setattr(
            cli, "_durable_success_latch_is_current", observe_reproof_mask
        )

        def handler(attempt: driver.CommandAttempt, *, root: Path) -> object:
            return cli._static_preflight_handler(
                attempt,
                root=root,
                clock=_FixedClock("production"),
            )

        exit_status = _private_run("static-preflight", handler, root=root)
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)

        assert admission_binding is not None
        assert exit_status == 4
        assert captured.err == ""
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "provider_uncertain"
        assert terminal["artifact_ref"] == admission_binding[0]
        assert terminal["artifact_sha256"] == admission_binding[1]
        assert observed_masks
        assert {int(item) for item in cli._WATCHED_SIGNALS}.issubset(
            observed_masks[0]
        )


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


class TestTask6RehearseCommand:
    def test_direct_witness_rejects_foreign_module_origin(
        self, tmp_path: Path
    ) -> None:
        foreign = tmp_path / "cuda_bench_cli.py"
        foreign.write_text("FOREIGN = True\n", encoding="utf-8")
        fake_module = type(
            "ForeignModule",
            (),
            {"__file__": str(foreign)},
        )

        with pytest.raises(AssertionError, match="checkout_module_origin"):
            _assert_module_from_checkout(
                fake_module,
                "scripts/cuda_bench_cli.py",
            )

    def test_direct_witness_rejects_foreign_module_origin_symlink_alias(
        self, tmp_path: Path
    ) -> None:
        foreign_alias = tmp_path / "cuda_bench_cli.py"
        foreign_alias.symlink_to(REPO_ROOT / "scripts/cuda_bench_cli.py")
        fake_module = type(
            "ForeignAliasModule",
            (),
            {"__file__": str(foreign_alias)},
        )

        with pytest.raises(AssertionError, match="checkout_module_origin"):
            _assert_module_from_checkout(
                fake_module,
                "scripts/cuda_bench_cli.py",
            )

    def test_direct_witness_rejects_relative_module_origin(self) -> None:
        fake_module = type(
            "RelativeModule",
            (),
            {"__file__": "scripts/cuda_bench_cli.py"},
        )

        with pytest.raises(AssertionError, match="checkout_module_origin"):
            _assert_module_from_checkout(
                fake_module,
                "scripts/cuda_bench_cli.py",
            )

    def test_rehearse_parser_is_exact_and_has_no_timeout_or_asset_override(self) -> None:
        parsed = cli.build_parser().parse_args(
            [
                "rehearse",
                "--static-preflight",
                "receipts/static.json",
                "--persona",
                "healthy",
            ]
        )
        assert vars(parsed) == {
            "command": "rehearse",
            "static_preflight": "receipts/static.json",
            "persona": "healthy",
        }
        for forbidden in (
            "--root",
            "--timeout",
            "--port",
            "--model",
            "--corpus",
            "--readiness-timeout",
            "--request-timeout",
        ):
            with pytest.raises(cli.InvocationRefusal):
                cli.build_parser().parse_args(
                    [
                        "rehearse",
                        "--static-preflight",
                        "receipts/static.json",
                        "--persona",
                        "healthy",
                        forbidden,
                        "value",
                    ]
                )

    def test_rehearsal_identity_collector_uses_selected_wrapper_not_corpus_or_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        relative, static = _task6_static_preflight(root)
        identity = cm.RuntimeIdentity(**_task6_identity_fields())
        opened: list[str] = []
        observation_log: list[str] = []
        real_open = driver.open_bench_file

        def tracked_open(path: str, *, root: Path) -> bytes:
            if path != relative:
                raise AssertionError(f"forbidden bench read: {path}")
            opened.append(path)
            return real_open(path, root=root)

        def candidate(root: Path) -> cli._CandidateObservation:
            assert root == cli.CANONICAL_STATIC_ASSETS.candidate_root
            observation_log.append("candidate")
            return cli._CandidateObservation(
                identity.runtime_sha256,
                identity.runtime_manifest_sha256,
                identity.library_hashes,
            )

        def package() -> tuple[str, bytes]:
            observation_log.append("package")
            return static.driver_package_sha256, b"package"

        def host(**kwargs: object) -> cli._HostObservation:
            assert kwargs["paths"] == cli.CANONICAL_STATIC_ASSETS
            observation_log.append("host")
            return cli._HostObservation(
                gpu_uuid=static.gpu_uuid,
                driver_version=identity.driver_version,
                gpu_identifier=identity.gpu_identifier,
                compute_capability=identity.compute_capability,
                cuda_compiler=identity.cuda_compiler,
                cmake_version=identity.cmake_version,
            )

        def stable(path: Path) -> tuple[str, int]:
            assert path == cli.CANONICAL_STATIC_ASSETS.cuda_override
            observation_log.append("override")
            return identity.production_override_sha256, 1

        monkeypatch.setattr(driver, "open_bench_file", tracked_open)
        monkeypatch.setattr(
            cli,
            "_verify_candidate_runtime_manifest",
            candidate,
        )
        monkeypatch.setattr(
            cli,
            "_driver_package_sha256",
            package,
        )
        monkeypatch.setattr(
            cli,
            "_collect_host_tool_observations",
            host,
        )
        monkeypatch.setattr(cli, "_stable_regular_file", stable)

        selected, observed_identity = cli._collect_rehearsal_identity(
            relative,
            root=root,
            paths=cli.CANONICAL_STATIC_ASSETS,
            runner=lambda *_args, **_kwargs: None,
        )

        assert selected == static
        assert observed_identity == identity
        assert opened == [relative]
        assert observation_log == ["candidate", "package", "host", "override"]
        assert "corpus.json" not in opened
        assert str(cli.CANONICAL_STATIC_ASSETS.model) not in opened

    @pytest.mark.parametrize(
        "drift",
        ("candidate_manifest", "package", "gpu", "tool"),
    )
    def test_rehearse_identity_collector_rejects_each_observation_drift(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        drift: str,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        relative, static = _task6_static_preflight(root)
        identity = cm.RuntimeIdentity(**_task6_identity_fields())
        candidate_manifest = (
            "f" * 64
            if drift == "candidate_manifest"
            else identity.runtime_manifest_sha256
        )
        package_sha = (
            "f" * 64
            if drift == "package"
            else static.driver_package_sha256
        )
        gpu_uuid = (
            "GPU-ffffffff-ffff-ffff-ffff-ffffffffffff"
            if drift == "gpu"
            else static.gpu_uuid
        )
        compiler = "0.0.0" if drift == "tool" else identity.cuda_compiler
        monkeypatch.setattr(
            cli,
            "_verify_candidate_runtime_manifest",
            lambda _root: cli._CandidateObservation(
                identity.runtime_sha256,
                candidate_manifest,
                identity.library_hashes,
            ),
        )
        monkeypatch.setattr(
            cli,
            "_driver_package_sha256",
            lambda: (package_sha, b"package"),
        )
        monkeypatch.setattr(
            cli,
            "_collect_host_tool_observations",
            lambda **_kwargs: cli._HostObservation(
                gpu_uuid=gpu_uuid,
                driver_version=identity.driver_version,
                gpu_identifier=identity.gpu_identifier,
                compute_capability=identity.compute_capability,
                cuda_compiler=compiler,
                cmake_version=identity.cmake_version,
            ),
        )
        monkeypatch.setattr(
            cli,
            "_stable_regular_file",
            lambda path: (
                identity.production_override_sha256,
                1,
            ),
        )

        with pytest.raises(driver.BenchRefusal) as exc:
            cli._collect_rehearsal_identity(
                relative,
                root=root,
                paths=cli.CANONICAL_STATIC_ASSETS,
                runner=lambda *_args, **_kwargs: None,
            )

        assert exc.value.code == "identity_mismatch"

    def test_all_personas_run_actual_rehearse_cli_without_residue(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        _assert_module_from_checkout(cli, "scripts/cuda_bench_cli.py")
        _assert_module_from_checkout(driver, "scripts/cuda_bench_driver.py")
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        os.chmod(root, 0o700)
        static_ref, static_doc = _task6_static_preflight(root)
        static_before = (root / static_ref).read_bytes()
        identity = cm.RuntimeIdentity(**_task6_identity_fields())
        monkeypatch.setattr(driver, "BENCH_ROOT", root)
        observation_calls = {
            "candidate": 0,
            "package": 0,
            "host": 0,
            "override": 0,
        }
        selected_opens = 0
        real_open = driver.open_bench_file

        def guarded_open(relative: str, *, root: Path) -> bytes:
            nonlocal selected_opens
            if relative == "corpus.json" or relative == str(
                cli.CANONICAL_STATIC_ASSETS.model
            ):
                raise AssertionError(f"forbidden rehearsal read: {relative}")
            if relative == static_ref:
                selected_opens += 1
            return real_open(relative, root=root)

        def candidate(candidate_root: Path) -> cli._CandidateObservation:
            assert candidate_root == cli.CANONICAL_STATIC_ASSETS.candidate_root
            observation_calls["candidate"] += 1
            return cli._CandidateObservation(
                identity.runtime_sha256,
                identity.runtime_manifest_sha256,
                identity.library_hashes,
            )

        def package() -> tuple[str, bytes]:
            observation_calls["package"] += 1
            return static_doc.driver_package_sha256, b"package"

        def host(**kwargs: object) -> cli._HostObservation:
            assert kwargs["paths"] == cli.CANONICAL_STATIC_ASSETS
            observation_calls["host"] += 1
            return cli._HostObservation(
                gpu_uuid=static_doc.gpu_uuid,
                driver_version=identity.driver_version,
                gpu_identifier=identity.gpu_identifier,
                compute_capability=identity.compute_capability,
                cuda_compiler=identity.cuda_compiler,
                cmake_version=identity.cmake_version,
            )

        def stable(path: Path) -> tuple[str, int]:
            if path != cli.CANONICAL_STATIC_ASSETS.cuda_override:
                raise AssertionError(f"forbidden static read: {path}")
            observation_calls["override"] += 1
            return identity.production_override_sha256, 1

        monkeypatch.setattr(driver, "open_bench_file", guarded_open)
        monkeypatch.setattr(
            cli,
            "_verify_candidate_runtime_manifest",
            candidate,
        )
        monkeypatch.setattr(cli, "_driver_package_sha256", package)
        monkeypatch.setattr(cli, "_collect_host_tool_observations", host)
        monkeypatch.setattr(cli, "_stable_regular_file", stable)
        children: list[driver.OwnedChild] = []
        real_spawn = driver.RehearsalServerLauncher.spawn

        def tracked_spawn(
            launcher: driver.RehearsalServerLauncher,
            argv: list[str],
            env: dict[str, str],
        ) -> driver.OwnedChild:
            child = real_spawn(launcher, argv, env)
            children.append(child)
            return child

        monkeypatch.setattr(driver.RehearsalServerLauncher, "spawn", tracked_spawn)
        expected = (
            ("healthy", "completed"),
            ("readiness_timeout", "readiness_timeout"),
            ("midturn_hang", "http_timeout"),
            ("crash", "crash"),
            ("malformed_response", "malformed_response"),
            ("wrong_identity", "alias_mismatch"),
        )
        production_before = {
            path.relative_to(root)
            for path in root.rglob("*.json")
            if not str(path.relative_to(root)).startswith("rehearsal/")
        }
        marker_before = tuple((root / "markers").glob("*")) if (root / "markers").exists() else ()
        started = time.monotonic()
        healthy_children: list[driver.OwnedChild] = []
        for persona, outcome in expected:
            before = {path.relative_to(root) for path in root.rglob("*")}
            child_start = len(children)
            rc = cli.main(
                [
                    "rehearse",
                    "--static-preflight",
                    static_ref,
                    "--persona",
                    persona,
                ]
            )
            captured = capfd.readouterr()
            terminal = _one_terminal_line(captured.out)
            assert captured.err == ""
            assert rc == (0 if outcome == "completed" else 3), terminal
            assert terminal["outcome"] == outcome
            assert type(terminal["artifact_ref"]) is str
            artifact_ref = terminal["artifact_ref"]
            assert artifact_ref.startswith("rehearsal/")
            artifact = driver.open_bench_file(artifact_ref, root=root)
            assert hashlib.sha256(artifact).hexdigest() == terminal["artifact_sha256"]
            wrapper = json.loads(artifact)
            assert set(wrapper) == {"rehearsal_schema", "tier", "payload"}
            assert wrapper["rehearsal_schema"] == driver.REHEARSAL_PACKET_SCHEMA
            assert wrapper["tier"] == "rehearsal"
            assert wrapper["payload"]["fields"]["outcome"] == outcome
            new_paths = {
                path.relative_to(root)
                for path in root.rglob("*")
                if path.is_file()
            } - before
            assert new_paths
            assert all(str(path).startswith("rehearsal/") for path in new_paths)
            persona_children = children[child_start:]
            assert persona_children
            assert all(child.port != 18080 for child in persona_children)
            assert all(child.popen.poll() is not None for child in persona_children)
            assert all(driver._pgid_members(child.pgid) == [] for child in persona_children)
            assert all(driver.RealPortProbe().is_free(child.port) for child in persona_children)
            if persona == "healthy":
                healthy_children = persona_children
        elapsed = time.monotonic() - started

        assert elapsed < 15
        assert selected_opens == 12
        assert observation_calls == {
            "candidate": 6,
            "package": 6,
            "host": 6,
            "override": 6,
        }
        assert [child.rehearsal_port_lease.generation for child in healthy_children] == [1, 2, 3]
        assert all(
            child.rehearsal_port_lease is not None
            and driver.RealPortProbe().is_free(child.rehearsal_port_lease.port)
            for child in healthy_children
        )
        assert (root / static_ref).read_bytes() == static_before
        assert {
            path.relative_to(root)
            for path in root.rglob("*.json")
            if not str(path.relative_to(root)).startswith("rehearsal/")
        } == production_before
        assert (
            tuple((root / "markers").glob("*"))
            if (root / "markers").exists()
            else ()
        ) == marker_before
        assert _task6_memfd_count() == 0


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
        assert {
            option
            for action in parser._actions
            for option in action.option_strings
        } == set()
        command_options = {}
        for command, subparser in (
            parser._subparsers._group_actions[0].choices.items()
        ):
            command_options[command] = {
                option
                for action in subparser._actions
                for option in action.option_strings
            }
        assert command_options == {
            "static-preflight": set(),
            "rehearse": {"--static-preflight", "--persona"},
            "vulkan-baseline": {
                "--window-authorization",
                "--static-preflight",
                "--static-admission",
                "--static-completion",
            },
            "cuda-candidate": {
                "--continuation",
                "--parent-window",
                "--parent-packet",
                "--parent-admission",
                "--parent-completion",
                "--static-preflight",
                "--static-admission",
                "--static-completion",
            },
            "assemble-stage1": {
                f"--{field.name.replace('_', '-')}"
                for field in fields(assemble.Stage1ArtifactPaths)
            },
        }
        assembly_parser = parser._subparsers._group_actions[0].choices[
            "assemble-stage1"
        ]
        assert tuple(
            action.dest
            for action in assembly_parser._actions
        ) == tuple(field.name for field in fields(assemble.Stage1ArtifactPaths))
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

    @pytest.mark.parametrize("command", ("static-preflight", "rehearse"))
    @pytest.mark.parametrize(
        ("status", "expected_exit"),
        (("refused", 3), ("failed", 4)),
    )
    def test_non_assembly_refusal_maps_to_exact_exit_status_and_one_output(
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


def _run_static_completion_hard_death_subprocess(
    root: Path,
) -> subprocess.CompletedProcess[str]:
    code = "\n".join(
        (
            "import os, signal, sys",
            "from pathlib import Path",
            "from scripts import cuda_bench_cli as cli",
            "from scripts import cuda_bench_driver as driver",
            "from tests.test_cuda_bench_cli import _static_test_observation",
            "root = Path(sys.argv[1])",
            "cli.collect_static_observation = lambda **_kwargs: _static_test_observation()",
            "real_link = driver.os.link",
            "def kill_before_completion_link(*args, **kwargs):",
            "    if str(args[1]).endswith('-terminal.json'):",
            "        os.kill(os.getpid(), signal.SIGKILL)",
            "    return real_link(*args, **kwargs)",
            "driver.os.link = kill_before_completion_link",
            "class Clock:",
            "    tier = 'production'",
            f"    def now_utc(self): return {FIXED_TIMESTAMP!r}",
            "    def monotonic(self): return 0.0",
            "def handler(attempt, *, root):",
            "    return cli._static_preflight_handler(attempt, root=root, clock=Clock())",
            "rc = cli._run_command('static-preflight', handler, root=root, clock=Clock())",
            "raise SystemExit(rc)",
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
    def test_non_matrix_success_reference_fails_closed(
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

        assert exit_status == 4
        assert captured.err == ""
        terminal = _one_terminal_line(captured.out)
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "provider_uncertain"
        assert terminal["artifact_ref"].endswith("-admission.json")
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
    def test_static_preflight_owner_surface_has_no_production_mutation(
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
        forbidden_imports = {
            "socket",
            "http",
            "urllib",
            "shutil",
            "dbus",
            "systemd",
        }
        if relative != "scripts/cuda_bench_cli.py":
            forbidden_imports.add("subprocess")
        assert imported_roots.isdisjoint(forbidden_imports)

        called = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (name := _ast_qualname(node.func)) is not None
        }
        called_leafs = {name.rpartition(".")[2].lstrip("_") for name in called}
        forbidden_calls = {
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
        if relative != "scripts/cuda_bench_cli.py":
            forbidden_calls.add("subprocess.run")
        assert called.isdisjoint(forbidden_calls)
        if relative == "scripts/cuda_bench_cli.py":
            run_calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and _ast_qualname(node.func) == "subprocess.run"
            ]
            assert len(run_calls) == 1
            enclosing = next(
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_run_read_only"
            )
            assert run_calls[0] in set(ast.walk(enclosing))
            keywords = {item.arg: item.value for item in run_calls[0].keywords}
            assert isinstance(keywords["shell"], ast.Constant)
            assert keywords["shell"].value is False
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
    def test_assembler_uses_only_public_scorer_and_no_action_surface(self) -> None:
        path = REPO_ROOT / "scripts" / "cuda_bench_assemble.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        called = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (name := _ast_qualname(node.func)) is not None
        }
        assert "cm.evaluate_promotion_bundle" in called
        assert "_evaluate_promotion_gate" not in source
        assert called.isdisjoint(
            {
                "driver.run_phase",
                "driver.write_private_file",
                "driver.publish_command_artifact",
                "subprocess.run",
                "os.open",
                "os.link",
                "os.unlink",
                "os.rename",
                "os.replace",
            }
        )
        assert {
            name.rpartition(".")[2].lstrip("_")
            for name in called
        }.isdisjoint(
            {
                "stop_service",
                "start_service",
                "restart_service",
                "install_override",
                "set_model_pointer",
                "switch_model_pointer",
                "promote",
                "cutover",
                "rollback_drill",
            }
        )

    def test_assembler_import_exposes_only_inert_selection_and_evaluation_api(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        before = list(tmp_path.iterdir())
        module = importlib.import_module("scripts.cuda_bench_assemble")
        assert tuple(field.name for field in fields(module.Stage1ArtifactPaths))
        assert tuple(field.name for field in fields(module.Stage1Evaluation)) == (
            "bundle",
            "verdict",
            "receipt",
        )
        assert callable(module.build_stage1_bundle)
        assert callable(module.assemble_stage1)
        assert list(tmp_path.iterdir()) == before


def _task9_paths_namespace() -> argparse.Namespace:
    return argparse.Namespace(
        **{
            field.name: f"selected/{field.name}.json"
            for field in fields(assemble.Stage1ArtifactPaths)
        }
    )


def _task9_evaluation(
    decision: str = "bench_passed",
) -> assemble.Stage1Evaluation:
    from tests import test_cuda_migration as migration_tests

    bundle = migration_tests._make_bundle(1)
    verdict = cm.evaluate_promotion_bundle(bundle)
    if decision == "keep_vulkan":
        verdict = replace(
            verdict,
            decision="keep_vulkan",
            reasons=("false_absence",),
        )
    with mock.patch.object(
        cm,
        "evaluate_promotion_bundle",
        return_value=verdict,
    ):
        receipt = cm.build_receipt(bundle, verdict, timestamp=FIXED_TIMESTAMP)
    return assemble.Stage1Evaluation(
        bundle=bundle,
        verdict=verdict,
        receipt=MappingProxyType(receipt),
    )


def _task9_assembly_handler(
    attempt: driver.CommandAttempt,
    *,
    root: Path,
) -> cli.TerminalResult:
    return cli._assembly_handler(
        attempt,
        root=root,
        clock=_FixedClock("production"),
        args=_task9_paths_namespace(),
    )


class TestTask9Stage1AssemblyCommand:
    def test_assemble_stage1_parser_has_exactly_twenty_two_relative_flags(
        self,
    ) -> None:
        parser = cli.build_parser()
        assembly_parser = parser._subparsers._group_actions[0].choices[
            "assemble-stage1"
        ]
        actions = tuple(assembly_parser._actions)
        assert tuple(action.dest for action in actions) == tuple(
            field.name for field in fields(assemble.Stage1ArtifactPaths)
        )
        assert all(action.required for action in actions)
        assert all(action.type is cli._relative_ref for action in actions)

    def test_terminal_matrix_is_closed_and_exhaustive(self) -> None:
        assert cli._TERMINAL_SCHEMA_MATRIX == {
            "static-preflight": cm.COMMAND_COMPLETION_SCHEMA,
            "rehearse": driver.REHEARSAL_PACKET_SCHEMA,
            "vulkan-baseline": cm.COMMAND_COMPLETION_SCHEMA,
            "cuda-candidate": cm.COMMAND_COMPLETION_SCHEMA,
            "assemble-stage1": driver.ASSEMBLE_RECEIPT_SCHEMA,
        }

    def test_assembly_clock_failure_persists_failed_assembly_receipt(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)

        class BrokenClock:
            tier = "production"

            def now_utc(self) -> str:
                raise RuntimeError("PRIVATE clock detail")

        scorer = mock.Mock(side_effect=AssertionError("scorer reached"))
        monkeypatch.setattr(assemble, "assemble_stage1", scorer)

        def handler(
            attempt: driver.CommandAttempt,
            *,
            root: Path,
        ) -> cli.TerminalResult:
            return cli._assembly_handler(
                attempt,
                root=root,
                clock=BrokenClock(),
                args=_task9_paths_namespace(),
            )

        status = cli._run_command(
            "assemble-stage1",
            handler,
            root=root,
            clock=_FixedClock("production"),
        )
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)
        wrapper = json.loads(
            driver.open_bench_file(str(terminal["artifact_ref"]), root=root)
        )

        assert status == 4
        assert captured.err == ""
        assert "PRIVATE" not in captured.out
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "provider_uncertain"
        assert wrapper == {
            "schema": driver.ASSEMBLE_RECEIPT_SCHEMA,
            "binding_sha256": None,
            "fields": {
                "outcome": "provider_uncertain",
                "timestamp": None,
            },
        }
        scorer.assert_not_called()

    @pytest.mark.parametrize("one_shot", (False, True))
    def test_assembly_terminal_publication_failure_never_retries_generic_schema(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        one_shot: bool,
    ) -> None:
        root = tmp_path / f"bench-{one_shot}"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation()
        monkeypatch.setattr(
            assemble,
            "assemble_stage1",
            lambda *_args, **_kwargs: evaluation,
        )
        real_publish = driver.publish_command_artifact
        calls: list[bytes] = []

        def fail_publication(
            attempt: driver.CommandAttempt,
            role: str,
            encoded: bytes,
            *,
            root: Path,
            on_committed: Callable[[str, str], None] | None = None,
        ) -> tuple[str, str]:
            calls.append(encoded)
            if len(calls) == 1 or not one_shot:
                raise OSError("PRIVATE terminal publication")
            return real_publish(
                attempt,
                role,
                encoded,
                root=root,
                on_committed=on_committed,
            )

        monkeypatch.setattr(
            driver,
            "publish_command_artifact",
            fail_publication,
        )

        status = _private_run(
            "assemble-stage1",
            _task9_assembly_handler,
            root=root,
        )
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)
        admission = next(root.glob("*-admission.json"))

        assert status == 4
        assert captured.err == ""
        assert "PRIVATE" not in captured.out
        assert len(calls) == 1
        assert terminal == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(
                admission.read_bytes()
            ).hexdigest(),
        }
        assert not list(root.glob("*-terminal.json"))

    def test_assembly_cleanup_incomplete_is_admission_bound_without_retry(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "bench-cleanup"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation()
        monkeypatch.setattr(
            assemble,
            "assemble_stage1",
            lambda *_args, **_kwargs: evaluation,
        )
        calls: list[bytes] = []

        def fail_cleanup(
            _attempt: driver.CommandAttempt,
            _role: str,
            encoded: bytes,
            *,
            root: Path,
            on_committed: Callable[[str, str], None] | None = None,
        ) -> tuple[str, str]:
            del root, on_committed
            calls.append(encoded)
            raise driver.BenchRefusal("cleanup_incomplete")

        monkeypatch.setattr(
            driver,
            "publish_command_artifact",
            fail_cleanup,
        )

        status = _private_run(
            "assemble-stage1",
            _task9_assembly_handler,
            root=root,
        )
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)
        admission = next(root.glob("*-admission.json"))

        assert status == 4
        assert captured.err == ""
        assert len(calls) == 1
        assert terminal == {
            "status": "failed",
            "outcome": "cleanup_incomplete",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(
                admission.read_bytes()
            ).hexdigest(),
        }
        assert not list(root.glob("*-terminal.json"))

    def test_assembly_receipt_encode_failure_never_publishes_generic_terminal(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "bench-encode"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation()
        monkeypatch.setattr(
            assemble,
            "assemble_stage1",
            lambda *_args, **_kwargs: evaluation,
        )
        real_encode = driver.ProductionArtifactPolicy.encode
        kinds: list[str] = []

        def fail_receipt_once(
            self: driver.ProductionArtifactPolicy,
            kind: str,
            document: dict[str, object],
        ) -> bytes:
            kinds.append(kind)
            if kind == "receipt":
                raise ValueError("PRIVATE receipt encoding")
            return real_encode(self, kind, document)

        monkeypatch.setattr(
            driver.ProductionArtifactPolicy,
            "encode",
            fail_receipt_once,
        )

        status = _private_run(
            "assemble-stage1",
            _task9_assembly_handler,
            root=root,
        )
        captured = capfd.readouterr()
        terminal = _one_terminal_line(captured.out)
        admission = next(root.glob("*-admission.json"))

        assert status == 4
        assert captured.err == ""
        assert "PRIVATE" not in captured.out
        assert kinds.count("command_admission") == 1
        assert kinds.count("receipt") == 1
        assert "refusal" not in kinds
        assert terminal == {
            "status": "failed",
            "outcome": "provider_uncertain",
            "window_id": None,
            "artifact_ref": admission.name,
            "artifact_sha256": hashlib.sha256(
                admission.read_bytes()
            ).hexdigest(),
        }
        assert not list(root.glob("*-terminal.json"))

    @pytest.mark.parametrize(
        "command",
        (
            "static-preflight",
            "rehearse",
            "vulkan-baseline",
            "cuda-candidate",
        ),
    )
    @pytest.mark.parametrize(
        ("status", "outcome"),
        (
            ("ok", "bench_passed"),
            ("refused", "assembly_refused"),
            ("failed", "provider_uncertain"),
        ),
    )
    def test_receipt_in_phase_terminal_role_fails_closed(
        self,
        tmp_path: Path,
        command: str,
        status: str,
        outcome: str,
    ) -> None:
        root = tmp_path / f"bench-{command}-{status}"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation()
        window_id = (
            "window-a"
            if command in {"vulkan-baseline", "cuda-candidate"}
            else None
        )

        def wrong_terminal(
            attempt: driver.CommandAttempt,
            *,
            root: Path,
            authorization: object | None = None,
        ) -> cli.TerminalResult:
            del authorization
            document = dict(evaluation.receipt)
            document["binding_sha256"] = evaluation.bundle.binding_sha256
            encoded = driver.ProductionArtifactPolicy().encode(
                "receipt", document
            )
            relative, digest = driver.publish_command_artifact(
                attempt,
                "terminal",
                encoded,
                root=root,
            )
            return cli.TerminalResult(
                status,
                outcome,
                window_id,
                relative,
                digest,
            )

        attempt = driver._admit_command(
            command=command,
            window_id=window_id,
            policy=(
                driver.RehearsalArtifactPolicy()
                if command == "rehearse"
                else driver.ProductionArtifactPolicy()
            ),
            clock=_FixedClock(
                "rehearsal" if command == "rehearse" else "production"
            ),
            root=root,
        )
        result = wrong_terminal(attempt, root=root)
        terminal = cli._normalize_handler_result(
            attempt,
            result,
            root=root,
        )

        assert terminal.status == "failed"
        assert terminal.outcome == "provider_uncertain"
        assert terminal.artifact_ref == attempt.admission_ref

    @pytest.mark.parametrize(
        ("terminal_status", "outcome"),
        (
            ("ok", "completed"),
            ("refused", "assembly_refused"),
            ("failed", "provider_uncertain"),
        ),
    )
    def test_command_completion_in_assembly_role_fails_closed(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        terminal_status: str,
        outcome: str,
    ) -> None:
        root = tmp_path / f"bench-{terminal_status}"
        root.mkdir(mode=0o700)

        def wrong_terminal(
            attempt: driver.CommandAttempt,
            *,
            root: Path,
        ) -> cli.TerminalResult:
            completion = cm.CommandCompletionDoc(
                command="static-preflight",
                ordinal=attempt.ordinal,
                window_id=None,
                admission_ref=attempt.admission_ref,
                admission_sha256=attempt.admission_sha256,
                artifact_ref="receipts/not-selected.json",
                artifact_sha256=SHA_A,
                artifact_schema=cm.STATIC_PREFLIGHT_SCHEMA,
                status="completed",
                timestamp=FIXED_TIMESTAMP,
            )
            encoded = driver.ProductionArtifactPolicy().encode(
                "command_completion",
                cli._completion_fields(completion),
            )
            relative, digest = driver.publish_command_artifact(
                attempt,
                "terminal",
                encoded,
                root=root,
            )
            return cli.TerminalResult(
                terminal_status,
                outcome,
                None,
                relative,
                digest,
            )

        status = _private_run(
            "assemble-stage1",
            wrong_terminal,
            root=root,
        )
        terminal = _one_terminal_line(capfd.readouterr().out)

        assert status == 4
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "provider_uncertain"
        assert terminal["artifact_ref"].endswith("-admission.json")

    @pytest.mark.parametrize(
        "mutation",
        (
            "extra_top_field",
            "missing_top_field",
            "extra_gate_binding",
            "missing_gate_binding",
            "malformed_timestamp",
            "malformed_value_shape",
        ),
    )
    def test_assembly_success_receipt_requires_exact_canonical_shape(
        self,
        tmp_path: Path,
        mutation: str,
    ) -> None:
        root = tmp_path / f"bench-{mutation}"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation()
        document = json.loads(json.dumps(dict(evaluation.receipt)))
        document["binding_sha256"] = evaluation.bundle.binding_sha256
        if mutation == "extra_top_field":
            document["unexpected"] = True
        elif mutation == "missing_top_field":
            document.pop("runtime")
        elif mutation == "extra_gate_binding":
            document["gate_bindings"]["unexpected_sha256"] = SHA_A
        elif mutation == "missing_gate_binding":
            document["gate_bindings"].pop("control_summary_sha256")
        elif mutation == "malformed_timestamp":
            document["timestamp"] = "not-a-timestamp"
        else:
            document["evaluator_versions"] = ["quality", "owner_voice"]
        attempt = driver._admit_command(
            command="assemble-stage1",
            window_id=None,
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=root,
        )
        encoded = driver.ProductionArtifactPolicy().encode(
            "receipt",
            document,
        )
        relative, digest = driver.publish_command_artifact(
            attempt,
            "terminal",
            encoded,
            root=root,
        )
        result = cli.TerminalResult(
            "ok",
            evaluation.verdict.decision,
            None,
            relative,
            digest,
        )

        assert not cli._valid_assembly_receipt_result(
            attempt,
            result,
            root=root,
        )

    @pytest.mark.parametrize(
        "mutation",
        (
            "extra",
            "missing",
            "bad_hash",
            "bad_cycle",
            "bad_bar",
            "bad_vram",
        ),
    )
    def test_assembly_success_receipt_requires_exact_nested_cycle_shape(
        self,
        tmp_path: Path,
        mutation: str,
    ) -> None:
        root = tmp_path / f"bench-cycle-{mutation}"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation()
        document = json.loads(json.dumps(dict(evaluation.receipt)))
        document["binding_sha256"] = evaluation.bundle.binding_sha256
        cycle = document["measurements"]["cycles"][0]
        if mutation == "extra":
            cycle["unexpected"] = 0
        elif mutation == "missing":
            cycle.pop("topology_sha256")
        elif mutation == "bad_hash":
            cycle["topology_sha256"] = "not-a-hash"
        elif mutation == "bad_cycle":
            cycle["cycle"] = True
        elif mutation == "bad_bar":
            cycle["bar1_before_percent"] = "1.0"
        else:
            cycle["vram_before_mib"] = 1.5
        attempt = driver._admit_command(
            command="assemble-stage1",
            window_id=None,
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=root,
        )
        encoded = driver.ProductionArtifactPolicy().encode(
            "receipt",
            document,
        )
        relative, digest = driver.publish_command_artifact(
            attempt,
            "terminal",
            encoded,
            root=root,
        )
        result = cli.TerminalResult(
            "ok",
            evaluation.verdict.decision,
            None,
            relative,
            digest,
        )

        assert not cli._valid_assembly_receipt_result(
            attempt,
            result,
            root=root,
        )

    @pytest.mark.parametrize(
        "mutation",
        (
            "unknown_reason",
            "bench_passed_with_reason",
            "keep_vulkan_without_reason",
            "missing_required_backend",
            "present_later_backend",
            "backend_gate_mismatch",
            "wrong_runtime_mode",
            "wrong_runtime_backend",
            "wrong_runtime_commit",
            "wrong_frozen_runtime",
            "runtime_gate_mismatch",
            "wrong_frozen_measurement",
            "phase_gate_mismatch",
            "containment_gate_mismatch",
        ),
    )
    def test_assembly_success_receipt_closes_stage1_nested_values(
        self,
        tmp_path: Path,
        mutation: str,
    ) -> None:
        root = tmp_path / f"bench-stage1-{mutation}"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation(
            "keep_vulkan"
            if mutation == "keep_vulkan_without_reason"
            else "bench_passed"
        )
        document = json.loads(json.dumps(dict(evaluation.receipt)))
        document["binding_sha256"] = evaluation.bundle.binding_sha256
        if mutation == "unknown_reason":
            document["reasons"] = ["unknown_reason"]
        elif mutation == "bench_passed_with_reason":
            document["reasons"] = ["false_absence"]
        elif mutation == "keep_vulkan_without_reason":
            document["reasons"] = []
        elif mutation == "missing_required_backend":
            document["backend_witnesses"]["control_maps_sha256"] = None
        elif mutation == "present_later_backend":
            document["backend_witnesses"]["cold_boot_maps_sha256"] = SHA_A
        elif mutation == "backend_gate_mismatch":
            document["backend_witnesses"]["control_binding_sha256"] = SHA_A
        elif mutation == "wrong_runtime_mode":
            document["runtime"]["mode"] = "production"
        elif mutation == "wrong_runtime_backend":
            document["runtime"]["backend"] = "vulkan"
        elif mutation == "wrong_runtime_commit":
            document["runtime"]["commit"] = "not-a-commit"
        elif mutation == "wrong_frozen_runtime":
            document["runtime"]["tag"] = "b9999"
        elif mutation == "runtime_gate_mismatch":
            document["gate_bindings"]["runtime_identity_sha256"] = SHA_A
        elif mutation == "wrong_frozen_measurement":
            document["measurements"]["sample_n"] = cm.FROZEN_SAMPLE_N + 1
        elif mutation == "phase_gate_mismatch":
            document["phase_evidence"]["boot_authorization_sha256"] = SHA_A
        else:
            document["gate_bindings"]["containment_sha256"] = SHA_A
        attempt = driver._admit_command(
            command="assemble-stage1",
            window_id=None,
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=root,
        )
        encoded = driver.ProductionArtifactPolicy().encode(
            "receipt",
            document,
        )
        relative, digest = driver.publish_command_artifact(
            attempt,
            "terminal",
            encoded,
            root=root,
        )
        result = cli.TerminalResult(
            "ok",
            evaluation.verdict.decision,
            None,
            relative,
            digest,
        )

        assert not cli._valid_assembly_receipt_result(
            attempt,
            result,
            root=root,
        )

    @pytest.mark.parametrize(
        ("command", "status"),
        (
            ("static-preflight", "refused"),
            ("static-preflight", "failed"),
            ("vulkan-baseline", "refused"),
            ("cuda-candidate", "failed"),
        ),
    )
    def test_canonical_production_refusal_is_valid_non_ok_terminal_evidence(
        self,
        tmp_path: Path,
        command: str,
        status: str,
    ) -> None:
        root = tmp_path / f"bench-{command}-{status}"
        root.mkdir(mode=0o700)
        window_id = (
            "window-a"
            if command in {"vulkan-baseline", "cuda-candidate"}
            else None
        )
        attempt = driver._admit_command(
            command=command,
            window_id=window_id,
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=root,
        )
        outcome = (
            "assembly_refused"
            if status == "refused"
            else "provider_uncertain"
        )
        normalized = cli._normalize_handler_result(
            attempt,
            cli.TerminalResult(status, outcome, window_id, None, None),
            root=root,
        )

        assert normalized.artifact_ref == cli._expected_terminal_ref(attempt)
        assert cli._valid_terminal_result(
            attempt,
            normalized,
            root=root,
        )

    @pytest.mark.parametrize("status", ("refused", "failed"))
    def test_canonical_rehearsal_refusal_is_valid_non_ok_terminal_evidence(
        self,
        tmp_path: Path,
        status: str,
    ) -> None:
        root = tmp_path / f"bench-{status}"
        root.mkdir(mode=0o700)
        attempt = driver._admit_command(
            command="rehearse",
            window_id=None,
            policy=driver.RehearsalArtifactPolicy(),
            clock=_FixedClock("rehearsal"),
            root=root,
        )
        outcome = (
            "assembly_refused"
            if status == "refused"
            else "provider_uncertain"
        )
        normalized = cli._normalize_handler_result(
            attempt,
            cli.TerminalResult(status, outcome, None, None, None),
            root=root,
        )

        assert normalized.artifact_ref == cli._expected_terminal_ref(attempt)
        assert cli._valid_terminal_result(
            attempt,
            normalized,
            root=root,
        )

    @pytest.mark.parametrize(
        "command",
        (
            "static-preflight",
            "rehearse",
            "vulkan-baseline",
            "cuda-candidate",
        ),
    )
    @pytest.mark.parametrize("status", ("refused", "failed"))
    def test_arbitrary_non_ok_artifact_never_bypasses_terminal_matrix(
        self,
        tmp_path: Path,
        command: str,
        status: str,
    ) -> None:
        root = tmp_path / f"bench-{command}-{status}"
        root.mkdir(mode=0o700)
        window_id = (
            "window-a"
            if command in {"vulkan-baseline", "cuda-candidate"}
            else None
        )
        attempt = driver._admit_command(
            command=command,
            window_id=window_id,
            policy=(
                driver.RehearsalArtifactPolicy()
                if command == "rehearse"
                else driver.ProductionArtifactPolicy()
            ),
            clock=_FixedClock(
                "rehearsal" if command == "rehearse" else "production"
            ),
            root=root,
        )
        relative = (
            "rehearsal/arbitrary.json"
            if command == "rehearse"
            else "arbitrary.json"
        )
        payload = b'{"arbitrary":true}\n'
        driver.write_private_file(relative, payload, root=root)
        normalized = cli._normalize_handler_result(
            attempt,
            cli.TerminalResult(
                status,
                (
                    "assembly_refused"
                    if status == "refused"
                    else "provider_uncertain"
                ),
                window_id,
                relative,
                hashlib.sha256(payload).hexdigest(),
            ),
            root=root,
        )

        assert normalized.status == "failed"
        assert normalized.outcome == "provider_uncertain"
        assert normalized.artifact_ref == attempt.admission_ref

    @pytest.mark.parametrize("decision", ("bench_passed", "keep_vulkan"))
    def test_assembly_handler_publishes_distinct_exit_zero_scorer_decisions(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        decision: str,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation(decision)
        monkeypatch.setattr(
            assemble,
            "assemble_stage1",
            lambda *_args, **_kwargs: evaluation,
        )

        status = _private_run(
            "assemble-stage1",
            _task9_assembly_handler,
            root=root,
        )
        terminal = _one_terminal_line(capfd.readouterr().out)
        wrapper = json.loads(
            driver.open_bench_file(str(terminal["artifact_ref"]), root=root)
        )

        assert status == 0
        assert terminal["status"] == "ok"
        assert terminal["outcome"] == decision
        assert wrapper["schema"] == driver.ASSEMBLE_RECEIPT_SCHEMA
        assert wrapper["binding_sha256"] == evaluation.bundle.binding_sha256
        assert wrapper["fields"]["decision"] == decision
        assert (
            wrapper["fields"]["bench_binding_sha256"]
            == evaluation.bundle.bench_binding_sha256
        )
        assert (
            wrapper["fields"]["bundle_binding_sha256"]
            == evaluation.bundle.binding_sha256
        )
        assert (
            wrapper["fields"]["gate_bindings"]["bench_evidence_sha256"]
            == evaluation.bundle.bench_binding_sha256
        )
        assert "migration_authorized" not in wrapper["fields"]
        assert "cutover_authorized" not in wrapper["fields"]

    def test_structural_owner_input_refusal_is_content_light_and_unscored(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        monkeypatch.setattr(
            assemble,
            "assemble_stage1",
            mock.Mock(side_effect=driver.BenchRefusal("assembly_refused")),
        )

        status = _private_run(
            "assemble-stage1",
            _task9_assembly_handler,
            root=root,
        )
        terminal = _one_terminal_line(capfd.readouterr().out)
        wrapper = json.loads(
            driver.open_bench_file(str(terminal["artifact_ref"]), root=root)
        )

        assert status == 3
        assert terminal["status"] == "refused"
        assert terminal["outcome"] == "assembly_refused"
        assert wrapper["schema"] == driver.ASSEMBLE_RECEIPT_SCHEMA
        assert wrapper["binding_sha256"] is None
        assert set(wrapper["fields"]) == {"outcome", "timestamp"}
        assert "decision" not in wrapper["fields"]
        assert "verdict" not in wrapper["fields"]
        assert "reasons" not in wrapper["fields"]

    @pytest.mark.parametrize("defect", ("scorer", "receipt_builder"))
    def test_scorer_or_receipt_builder_defect_is_failed_not_assembly_refused(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        defect: str,
    ) -> None:
        root = tmp_path / f"bench-{defect}"
        root.mkdir(mode=0o700)
        monkeypatch.setattr(
            assemble,
            "assemble_stage1",
            mock.Mock(side_effect=RuntimeError(defect)),
        )

        status = _private_run(
            "assemble-stage1",
            _task9_assembly_handler,
            root=root,
        )
        terminal = _one_terminal_line(capfd.readouterr().out)
        wrapper = json.loads(
            driver.open_bench_file(str(terminal["artifact_ref"]), root=root)
        )

        assert status == 4
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "provider_uncertain"
        assert wrapper["schema"] == driver.ASSEMBLE_RECEIPT_SCHEMA
        assert wrapper["binding_sha256"] is None
        assert set(wrapper["fields"]) == {"outcome", "timestamp"}
        assert wrapper["fields"]["outcome"] != "assembly_refused"

    def test_handler_reuses_one_admission_and_publishes_one_terminal(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation()
        monkeypatch.setattr(
            assemble,
            "assemble_stage1",
            lambda *_args, **_kwargs: evaluation,
        )
        real_admit = driver._admit_command
        real_publish = driver.publish_command_artifact
        admit = mock.Mock(wraps=real_admit)
        publish = mock.Mock(wraps=real_publish)
        monkeypatch.setattr(driver, "_admit_command", admit)
        monkeypatch.setattr(driver, "publish_command_artifact", publish)

        status = _private_run(
            "assemble-stage1",
            _task9_assembly_handler,
            root=root,
        )
        terminal = _one_terminal_line(capfd.readouterr().out)

        assert status == 0
        assert admit.call_count == 1
        assert publish.call_count == 1
        admitted = admit.call_args.kwargs["_on_latched"]
        assert callable(admitted)
        attempt = publish.call_args.args[0]
        assert publish.call_args.args[1] == "terminal"
        assert terminal["artifact_ref"] == (
            f"command-assemble-stage1-attempt-{attempt.ordinal:03d}-terminal.json"
        )

    def test_assembly_uses_existing_allocator_for_distinct_ordinals(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        clock = _FixedClock("production")
        policy = driver.ProductionArtifactPolicy()

        def admit() -> driver.CommandAttempt:
            return driver._admit_command(
                command="assemble-stage1",
                window_id=None,
                policy=policy,
                clock=clock,
                root=root,
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            attempts = tuple(executor.map(lambda _index: admit(), range(4)))

        assert sorted(attempt.ordinal for attempt in attempts) == [1, 2, 3, 4]
        assert len({attempt.admission_ref for attempt in attempts}) == 4

    def test_bench_passed_has_no_action_or_measurement_authority(
        self,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        evaluation = _task9_evaluation()
        monkeypatch.setattr(
            assemble,
            "assemble_stage1",
            lambda *_args, **_kwargs: evaluation,
        )
        forbidden = mock.Mock(
            side_effect=AssertionError("action surface reached")
        )
        for name in (
            "stop_service",
            "start_service",
            "restart_service",
            "install_override",
            "remove_override",
            "set_model_pointer",
            "switch_model_pointer",
            "promote_cuda",
            "cutover",
            "rollback_drill",
        ):
            monkeypatch.setattr(cli, name, forbidden, raising=False)
        before = set(root.rglob("*"))

        status = _private_run(
            "assemble-stage1",
            _task9_assembly_handler,
            root=root,
        )
        terminal = _one_terminal_line(capfd.readouterr().out)
        created = {
            path.relative_to(root)
            for path in set(root.rglob("*")) - before
            if path.is_file()
        }

        assert status == 0
        assert terminal["outcome"] == "bench_passed"
        assert created == {
            Path("command-assemble-stage1-attempt-001-admission.json"),
            Path("command-assemble-stage1-attempt-001-terminal.json"),
        }
        assert "rollback-drill" not in cli.PUBLIC_COMMANDS
        assert "cutover" not in cli.PUBLIC_COMMANDS
        assert "authorization" not in inspect.signature(
            cli._assembly_handler
        ).parameters
        forbidden.assert_not_called()


class TestTask7ProductionMeasurementCommands:
    VULKAN_ARGS = (
        "--window-authorization",
        "authority/window.json",
        "--static-preflight",
        "receipts/static.json",
        "--static-admission",
        "commands/static-admission.json",
        "--static-completion",
        "commands/static-completion.json",
    )
    CUDA_ARGS = (
        "--continuation",
        "authority/continuation.json",
        "--parent-window",
        "authority/window.json",
        "--parent-packet",
        "packets/vulkan.json",
        "--parent-admission",
        "commands/vulkan-admission.json",
        "--parent-completion",
        "commands/vulkan-completion.json",
        "--static-preflight",
        "receipts/static.json",
        "--static-admission",
        "commands/static-admission.json",
        "--static-completion",
        "commands/static-completion.json",
    )

    @pytest.mark.parametrize(
        ("command", "arguments", "expected_names"),
        (
            (
                "vulkan-baseline",
                VULKAN_ARGS,
                {
                    "window_authorization",
                    "static_preflight",
                    "static_admission",
                    "static_completion",
                },
            ),
            (
                "cuda-candidate",
                CUDA_ARGS,
                {
                    "continuation",
                    "parent_window",
                    "parent_packet",
                    "parent_admission",
                    "parent_completion",
                    "static_preflight",
                    "static_admission",
                    "static_completion",
                },
            ),
        ),
    )
    def test_production_phase_parser_is_exact(
        self,
        command: str,
        arguments: tuple[str, ...],
        expected_names: set[str],
    ) -> None:
        parsed = cli.build_parser().parse_args((command, *arguments))
        assert set(vars(parsed)) == {"command", *expected_names}
        for forbidden in (
            "--root",
            "--port",
            "--timeout",
            "--model",
            "--corpus",
            "--env",
            "--restart",
        ):
            with pytest.raises(cli.InvocationRefusal):
                cli.build_parser().parse_args((command, *arguments, forbidden, "x"))

    def test_frozen_tail_is_exact_and_hash_bound(self) -> None:
        assert cli.FROZEN_BENCH_ARGV_TAIL == (
            "-m",
            cm.FROZEN_MODEL_PATH,
            "--alias",
            cm.FROZEN_ALIAS,
            "--host",
            "127.0.0.1",
            "--port",
            "18080",
            "--ctx-size",
            "40960",
            "--parallel",
            "1",
            "--n-gpu-layers",
            "999",
            "-fa",
            "on",
            "--cache-type-k",
            "q4_0",
            "--cache-type-v",
            "q4_0",
            "--spec-type",
            "draft-mtp",
            "--spec-draft-n-max",
            "3",
            "--kv-unified",
            "-fit",
            "off",
        )
        encoded = json.dumps(
            list(cli.FROZEN_BENCH_ARGV_TAIL),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        assert hashlib.sha256(encoded).hexdigest() == cm.FROZEN_BENCH_ARGS_SHA256

    def test_frozen_prompt_loader_delegates_and_preserves_duplicates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prompts = ("one", "two", "one", "three", "four", "five", "six")
        monkeypatch.setattr(
            cli, "_validate_frozen_corpus", lambda *, root: prompts
        )
        assert cli._load_frozen_prompts(root=tmp_path) == prompts
        source = inspect.getsource(cli._load_frozen_prompts)
        assert source.count("_validate_frozen_corpus") == 1
        assert "json.loads" not in source

    @pytest.mark.parametrize(
        "field",
        (
            "gpu_uuid",
            "driver_package_sha256",
            "stub_sha256",
            "corpus_verified",
            "checks",
        ),
    )
    def test_static_identity_compares_every_non_timestamp_field(
        self, field: str
    ) -> None:
        selected = _static_test_observation().static_doc
        if field == "checks":
            checks = dict(selected.checks)
            checks["vision_unit"] = "f" * 64
            mutated = replace(selected, checks=checks)
        elif field == "corpus_verified":
            mutated = replace(selected)
            object.__setattr__(mutated, "corpus_verified", False)
        elif field == "gpu_uuid":
            mutated = replace(
                selected,
                gpu_uuid="GPU-11111111-2222-3333-4444-555555555555",
            )
        elif field == "stub_sha256":
            checks = dict(selected.checks)
            checks["stub_pin"] = "f" * 64
            mutated = replace(selected, stub_sha256="f" * 64, checks=checks)
        else:
            mutated = replace(selected, **{field: "f" * 64})
        with pytest.raises(driver.BenchRefusal, match="identity_mismatch"):
            cli._require_static_match(selected, mutated)
        cli._require_static_match(
            selected,
            replace(selected, timestamp="2026-07-21T12:00:01Z"),
        )

    def test_phase_window_is_parsed_before_admission_and_bound(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tmp_path.chmod(0o700)
        authorization = driver.WindowAuthorization(
            window_id="window-task7",
            phases=("vulkan_baseline", "cuda_candidate"),
            boot_id="boot-task7",
            nonce="a" * 64,
            issued_at="2026-07-24T10:00:00Z",
            expires_at="2026-07-24T14:00:00Z",
            owner="owner",
        )
        opened: list[str] = []
        admitted: list[str | None] = []
        monkeypatch.setattr(
            driver,
            "open_bench_file",
            lambda relative, *, root: opened.append(relative) or b"authorization",
        )
        monkeypatch.setattr(
            driver, "parse_window_authorization", lambda _data: authorization
        )
        real_admit = driver._admit_command

        def admit(**kwargs: object) -> driver.CommandAttempt:
            admitted.append(kwargs["window_id"])  # type: ignore[arg-type]
            return real_admit(**kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(driver, "_admit_command", admit)
        result = cli._run_command(
            "vulkan-baseline",
            lambda _attempt, *, root, authorization: cli.TerminalResult(
                "refused",
                "preflight_service_active",
                "window-task7",
                None,
                None,
            ),
            root=tmp_path,
            clock=_FixedClock("production"),
            authority_ref="authority/window.json",
        )
        assert result == 3
        assert opened[0] == "authority/window.json"
        assert admitted == ["window-task7"]
        path = next(tmp_path.glob("*admission.json"))
        admission = cm.CommandAdmissionPreimage(
            str(path.relative_to(tmp_path)), path.read_bytes()
        )
        assert admission.window_id == "window-task7"

    def test_nonce_unburned_pre_admission_authority_failure_creates_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tmp_path.chmod(0o700)
        monkeypatch.setattr(
            driver,
            "open_bench_file",
            lambda _relative, *, root: (_ for _ in ()).throw(
                driver.BenchRefusal("filesystem_hazard")
            ),
        )
        assert (
            cli._run_command(
                "vulkan-baseline",
                lambda _attempt, *, root, authorization: (_ for _ in ()).throw(
                    AssertionError("handler called")
                ),
                root=tmp_path,
                clock=_FixedClock("production"),
                authority_ref="authority/window.json",
            )
            == 3
        )
        assert list(tmp_path.iterdir()) == []

    def test_cuda_continuation_window_is_bound_into_admission(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tmp_path.chmod(0o700)
        continuation = driver.Continuation(
            window_id="window-task7",
            phases=("cuda_candidate",),
            boot_id="boot-task7",
            nonce="b" * 64,
            issued_at="2026-07-24T12:00:00Z",
            expires_at="2026-07-24T13:00:00Z",
            owner="owner",
            parent_vulkan_packet_sha256="c" * 64,
        )
        monkeypatch.setattr(
            driver,
            "open_bench_file",
            lambda _relative, *, root: b"continuation",
        )
        monkeypatch.setattr(
            driver, "parse_continuation", lambda _data: continuation
        )
        assert (
            cli._run_command(
                "cuda-candidate",
                lambda _attempt, *, root, authorization: cli.TerminalResult(
                    "refused",
                    "preflight_service_active",
                    authorization.window_id,
                    None,
                    None,
                ),
                root=tmp_path,
                clock=_FixedClock("production"),
                authority_ref="authority/continuation.json",
            )
            == 3
        )
        path = next(tmp_path.glob("*admission.json"))
        admission = cm.CommandAdmissionPreimage(
            str(path.relative_to(tmp_path)), path.read_bytes()
        )
        assert admission.command == "cuda-candidate"
        assert admission.window_id == continuation.window_id

    def test_production_environment_phase_config_is_exact(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observation = replace(
            _static_test_observation(),
            runtime_identity=cm.RuntimeIdentity(**_task6_identity_fields()),
        )
        identity = observation.runtime_identity
        assert isinstance(identity, cm.RuntimeIdentity)
        window = driver.WindowAuthorization(
            window_id="window-task7",
            phases=("vulkan_baseline", "cuda_candidate"),
            boot_id="boot-task7",
            nonce="a" * 64,
            issued_at="2026-07-24T10:00:00Z",
            expires_at="2026-07-24T14:00:00Z",
            owner="owner",
        )
        prompts = tuple(f"prompt-{index}" for index in range(7))
        monkeypatch.setattr(cli, "_load_frozen_prompts", lambda *, root: prompts)
        monkeypatch.setattr(cli, "_read_boot_id", lambda: "boot-task7")
        args = cli.build_parser().parse_args(
            ("vulkan-baseline", *self.VULKAN_ARGS)
        )
        args._root = Path("/tmp/task7-config")
        args._authorization = window
        config = cli._vulkan_config(args, observation)
        identity_fields = driver._runtime_identity_fields(identity)
        identity_fields["effective_args"] = tuple(identity.effective_args)
        assert config.argv == [
            str(cm.VULKAN_RELEASE_ROOT / "llama-server"),
            *cli.FROZEN_BENCH_ARGV_TAIL,
        ]
        assert config.env == dict(
            driver._PHASE_BENCH_ENVIRONMENTS["vulkan_baseline"]
        )
        assert config.expected_port == 18080
        assert config.readiness_timeout_s == driver.READINESS_TIMEOUT_S
        assert config.window_id == window.window_id
        assert config.boot_id == "boot-task7"
        assert config.bench_identity_fields == identity_fields
        assert config.runtime_identity_fields == identity_fields
        assert config.prompts == prompts

    def test_production_environment_cuda_config_parent_paths_and_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observation = replace(
            _static_test_observation(),
            runtime_identity=cm.RuntimeIdentity(**_task6_identity_fields()),
        )
        continuation = driver.Continuation(
            window_id="window-task7",
            phases=("cuda_candidate",),
            boot_id="boot-task7",
            nonce="b" * 64,
            issued_at="2026-07-24T12:00:00Z",
            expires_at="2026-07-24T13:00:00Z",
            owner="owner",
            parent_vulkan_packet_sha256="c" * 64,
        )
        parent = driver.WindowAuthorization(
            window_id="window-task7",
            phases=("vulkan_baseline", "cuda_candidate"),
            boot_id="boot-task7",
            nonce="a" * 64,
            issued_at="2026-07-24T10:00:00Z",
            expires_at="2026-07-24T14:00:00Z",
            owner="owner",
        )
        prompts = tuple(f"prompt-{index}" for index in range(7))
        monkeypatch.setattr(cli, "_load_frozen_prompts", lambda *, root: prompts)
        monkeypatch.setattr(cli, "_read_boot_id", lambda: "boot-task7")
        monkeypatch.setattr(
            driver, "open_bench_file", lambda _relative, *, root: b"window"
        )
        monkeypatch.setattr(
            driver, "parse_window_authorization", lambda _data: parent
        )
        args = cli.build_parser().parse_args(
            ("cuda-candidate", *self.CUDA_ARGS)
        )
        args._root = Path("/tmp/task7-config")
        args._authorization = continuation
        config = cli._cuda_config(args, observation)
        assert config.argv == [
            str(cm.CUDA_RELEASE_ROOT / "llama-server"),
            *cli.FROZEN_BENCH_ARGV_TAIL,
        ]
        assert config.env == dict(
            driver._PHASE_BENCH_ENVIRONMENTS["cuda_candidate"]
        )
        assert config.prompts == prompts
        assert config.window_id == continuation.window_id
        assert config.parent_window is parent
        assert config.parent_packet_path == args.parent_packet
        assert config.parent_admission_path == args.parent_admission
        assert config.parent_completion_path == args.parent_completion

    def test_no_service_mutation_production_provider_factory_is_exact(
        self,
    ) -> None:
        identity = cm.RuntimeIdentity(**_task6_identity_fields())
        assert isinstance(identity, cm.RuntimeIdentity)
        providers = cli._production_providers("vulkan_baseline", identity)
        assert type(providers.service_state) is driver.RealServiceStateProvider
        assert type(providers.port_probe) is driver.RealPortProbe
        assert type(providers.gpu) is driver.RealGpuProvider
        assert type(providers.kernel_log) is driver.RealKernelLogProvider
        assert type(providers.backend_maps) is driver.RealBackendMapProvider
        assert type(providers.server_launcher) is driver.RealServerLauncher
        assert type(providers.authorization_gate) is driver.RealAuthorizationGate
        assert type(providers.containment) is driver.RealContainmentProvider
        source = inspect.getsource(cli._production_providers)
        for forbidden in (
            '"stop"',
            '"start"',
            '"restart"',
            '"enable"',
            '"disable"',
            '"install"',
            '"override"',
        ):
            assert forbidden not in source

    def test_verify_existing_rollback_is_read_only_and_not_repaired(self) -> None:
        source = inspect.getsource(cli._phase_handler)
        assert source.count("verify_existing_immutable") == 1
        assert "publish_or_verify_immutable" not in source
        assert "write_private_file" not in source

    def test_malformed_selected_static_timestamp_refuses_structurally(self) -> None:
        doc = _static_test_observation().static_doc
        fields = cli._static_preflight_fields(doc)
        fields["timestamp"] = "2026-07-24 12:00:00"
        encoded = driver.ProductionArtifactPolicy().encode(
            "static_preflight", fields
        )
        with pytest.raises(ValueError, match="persisted_roundtrip"):
            cm.PersistedDoc(encoded)

    @pytest.mark.parametrize(
        ("phase", "command"),
        (
            ("vulkan_baseline", "vulkan-baseline"),
            ("cuda_candidate", "cuda-candidate"),
        ),
    )
    def test_phase_completion_signal_before_link_never_latches_success(
        self,
        phase: str,
        command: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tmp_path.chmod(0o700)
        attempt = driver._admit_command(
            command=command,
            window_id="window-task7",
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=tmp_path,
        )
        from tests.test_cuda_migration import _phase_packet

        packet = _phase_packet(phase)
        object.__setattr__(packet, "window_id", "window-task7")
        (tmp_path / "packet.json").write_bytes(b"packet")
        (tmp_path / "packet.json").chmod(0o600)
        monkeypatch.setattr(
            driver, "open_bench_file", lambda _relative, *, root: b"packet"
        )
        monkeypatch.setattr(cm, "decode_persisted_packet", lambda _data: packet)
        monkeypatch.setattr(
            driver,
            "publish_command_artifact",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                driver._CommandInterrupted(signal.SIGTERM, attempt)
            ),
        )
        latched: list[cli.TerminalResult] = []
        monkeypatch.setattr(
            cli,
            "_latch_durable_success",
            lambda result, **_kwargs: latched.append(result),
        )
        with pytest.raises(driver._CommandInterrupted):
            cli._publish_phase_completion(
                attempt,
                phase_ref="packet.json",
                expected_phase=phase,
                expected_window_id="window-task7",
                root=tmp_path,
                clock=_FixedClock("production"),
            )
        assert latched == []
        assert not any(
            "terminal" in path.name for path in tmp_path.rglob("*.json")
        )

    @pytest.mark.parametrize(
        ("phase", "command"),
        (
            ("vulkan_baseline", "vulkan-baseline"),
            ("cuda_candidate", "cuda-candidate"),
        ),
    )
    def test_phase_completion_signal_after_durable_validation_latches_success(
        self,
        phase: str,
        command: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tmp_path.chmod(0o700)
        attempt = driver._admit_command(
            command=command,
            window_id="window-task7",
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=tmp_path,
        )
        from tests.test_cuda_migration import _phase_packet

        packet = _phase_packet(phase)
        object.__setattr__(packet, "window_id", "window-task7")
        (tmp_path / "packet.json").write_bytes(b"packet")
        (tmp_path / "packet.json").chmod(0o600)
        monkeypatch.setattr(
            driver, "open_bench_file", lambda _relative, *, root: b"packet"
        )
        monkeypatch.setattr(cm, "decode_persisted_packet", lambda _data: packet)

        def publish(
            _attempt: driver.CommandAttempt,
            _role: str,
            _data: bytes,
            *,
            root: Path,
            on_committed: Callable[[str, str], None],
        ) -> tuple[str, str]:
            del root
            on_committed("command-completion.json", "f" * 64)
            raise driver._CommandInterrupted(signal.SIGTERM, attempt)

        monkeypatch.setattr(driver, "publish_command_artifact", publish)
        latched: list[cli.TerminalResult] = []
        monkeypatch.setattr(
            cli,
            "_latch_durable_success",
            lambda result, **_kwargs: latched.append(result),
        )
        with pytest.raises(driver._CommandInterrupted):
            cli._publish_phase_completion(
                attempt,
                phase_ref="packet.json",
                expected_phase=phase,
                expected_window_id="window-task7",
                root=tmp_path,
                clock=_FixedClock("production"),
            )
        assert latched == [
            cli.TerminalResult(
                "ok",
                "completed",
                "window-task7",
                "command-completion.json",
                "f" * 64,
            )
        ]

    @pytest.mark.parametrize(
        ("spawned", "schema", "expected_status"),
        (
            (False, driver.REFUSAL_SCHEMA, "refused"),
            (True, driver.PHASE_PACKET_SCHEMA, "failed"),
        ),
    )
    def test_reduced_phase_artifact_maps_honestly_without_completion(
        self,
        spawned: bool,
        schema: str,
        expected_status: str,
        tmp_path: Path,
    ) -> None:
        tmp_path.chmod(0o700)
        fields = {
            "phase": "vulkan_baseline",
            "window_id": "window-task7",
            "boot_id": "boot-task7",
            "outcome": "preflight_service_active",
            "spawned": spawned,
            "timestamp": FIXED_TIMESTAMP,
        }
        binding = hashlib.sha256(driver._canonical_json(fields)).hexdigest()
        wrapper = driver._canonical_json(
            {
                "schema": schema,
                "binding_sha256": binding,
                "fields": fields,
            }
        )
        path = tmp_path / "reduced.json"
        path.write_bytes(wrapper)
        path.chmod(0o600)
        result = cli._phase_artifact_result(
            "reduced.json",
            expected_phase="vulkan_baseline",
            expected_window_id="window-task7",
            root=tmp_path,
        )
        assert result.status == expected_status
        assert result.outcome == "preflight_service_active"
        assert result.artifact_ref == "reduced.json"
        assert not any("completion" in item.name for item in tmp_path.iterdir())
        with pytest.raises(ValueError):
            cm.decode_persisted_packet(wrapper)

    def test_binding_invalid_reduced_phase_artifact_fails_closed(
        self, tmp_path: Path
    ) -> None:
        wrapper = driver._canonical_json(
            {
                "schema": driver.REFUSAL_SCHEMA,
                "binding_sha256": "0" * 64,
                "fields": {
                    "phase": "vulkan_baseline",
                    "window_id": "window-task7",
                    "boot_id": "boot-task7",
                    "outcome": "preflight_service_active",
                    "spawned": False,
                    "timestamp": FIXED_TIMESTAMP,
                },
            }
        )
        path = tmp_path / "reduced.json"
        path.write_bytes(wrapper)
        path.chmod(0o600)
        with pytest.raises(driver.BenchRefusal, match="provider_uncertain"):
            cli._phase_artifact_result(
                "reduced.json",
                expected_phase="vulkan_baseline",
                expected_window_id="window-task7",
                root=tmp_path,
            )

    def test_phase_completion_validator_reopens_and_joins_underlying_packet(
        self, tmp_path: Path
    ) -> None:
        tmp_path.chmod(0o700)
        attempt = driver._admit_command(
            command="vulkan-baseline",
            window_id="window-task7",
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=tmp_path,
        )
        completion = cm.CommandCompletionDoc(
            command="vulkan-baseline",
            ordinal=attempt.ordinal,
            window_id="window-task7",
            admission_ref=attempt.admission_ref,
            admission_sha256=attempt.admission_sha256,
            artifact_ref="packets/missing-phase-packet.json",
            artifact_sha256="f" * 64,
            artifact_schema=cm.PHASE_PACKET_SCHEMA,
            status="completed",
            timestamp="2026-07-21T12:00:01Z",
        )
        encoded = driver.ProductionArtifactPolicy().encode(
            "command_completion", cli._completion_fields(completion)
        )
        completion_ref = cli._expected_terminal_ref(attempt)
        driver.write_private_file(completion_ref, encoded, root=tmp_path)
        result = cli.TerminalResult(
            "ok",
            "completed",
            "window-task7",
            completion_ref,
            hashlib.sha256(encoded).hexdigest(),
        )
        assert cli._valid_command_completion_result(
            attempt, result, root=tmp_path
        ) is False

    @pytest.mark.parametrize("mutation", ("delete", "replace"))
    def test_durable_phase_latch_reproves_joined_packet(
        self, mutation: str, tmp_path: Path
    ) -> None:
        from tests.test_cuda_migration import _phase_packet

        tmp_path.chmod(0o700)
        packet = _phase_packet("vulkan_baseline")
        packet_ref = "packets/vulkan.json"
        packet_bytes = driver.ProductionArtifactPolicy().encode(
            "packet",
            {
                "binding_sha256": packet.binding_sha256,
                **driver._phase_packet_fields(packet),
            },
        )
        driver.write_private_file(packet_ref, packet_bytes, root=tmp_path)
        attempt = driver._admit_command(
            command="vulkan-baseline",
            window_id=packet.window_id,
            policy=driver.ProductionArtifactPolicy(),
            clock=driver.FrozenClock("2026-07-14T07:00:00Z"),
            root=tmp_path,
        )
        result = cli._publish_phase_completion(
            attempt,
            phase_ref=packet_ref,
            expected_phase="vulkan_baseline",
            expected_window_id=packet.window_id,
            root=tmp_path,
            clock=driver.FrozenClock("2026-07-21T12:00:01Z"),
        )
        latch = cli._linearized_durable_success
        assert latch is not None
        path = tmp_path / packet_ref
        if mutation == "delete":
            path.unlink()
        else:
            payload = path.read_bytes()
            path.unlink()
            path.write_bytes(payload)
            path.chmod(0o600)
        assert cli._durable_success_latch_is_current(latch) is False
        assert result.status == "ok"

    def test_nonfrozen_order_packet_cannot_mint_completion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tests.test_cuda_migration import _phase_packet

        tmp_path.chmod(0o700)
        packet = _phase_packet("vulkan_baseline")
        object.__setattr__(packet, "order_sha256", "d" * 64)
        attempt = driver._admit_command(
            command="vulkan-baseline",
            window_id=packet.window_id,
            policy=driver.ProductionArtifactPolicy(),
            clock=driver.FrozenClock("2026-07-14T07:00:00Z"),
            root=tmp_path,
        )
        monkeypatch.setattr(
            driver, "open_bench_file", lambda _relative, *, root: b"packet"
        )
        monkeypatch.setattr(cm, "decode_persisted_packet", lambda _data: packet)
        monkeypatch.setattr(
            driver,
            "publish_command_artifact",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("completion published")
            ),
        )
        with pytest.raises(driver.BenchRefusal, match="provider_uncertain"):
            cli._publish_phase_completion(
                attempt,
                phase_ref="packets/vulkan.json",
                expected_phase="vulkan_baseline",
                expected_window_id=packet.window_id,
                root=tmp_path,
                clock=driver.FrozenClock("2026-07-21T12:00:01Z"),
            )

    @pytest.mark.parametrize(
        ("spawned", "outcome", "status"),
        (
            (False, "cleanup_incomplete", "refused"),
            (True, "cleanup_incomplete", "failed"),
            (False, "interrupted", "refused"),
        ),
    )
    def test_trusted_reduced_terminal_preserves_driver_outcome(
        self,
        spawned: bool,
        outcome: str,
        status: str,
        tmp_path: Path,
    ) -> None:
        tmp_path.chmod(0o700)
        attempt = driver._admit_command(
            command="vulkan-baseline",
            window_id="window-task7",
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=tmp_path,
        )
        fields = {
            "phase": "vulkan_baseline",
            "window_id": "window-task7",
            "boot_id": "boot-task7",
            "outcome": outcome,
            "spawned": spawned,
            "timestamp": FIXED_TIMESTAMP,
        }
        wrapper = driver._canonical_json(
            {
                "schema": (
                    driver.PHASE_PACKET_SCHEMA
                    if spawned
                    else driver.REFUSAL_SCHEMA
                ),
                "binding_sha256": hashlib.sha256(
                    driver._canonical_json(fields)
                ).hexdigest(),
                "fields": fields,
            }
        )
        path = tmp_path / "reduced.json"
        path.write_bytes(wrapper)
        path.chmod(0o600)
        phase_result = cli._phase_artifact_result(
            "reduced.json",
            expected_phase="vulkan_baseline",
            expected_window_id="window-task7",
            root=tmp_path,
        )
        normalized = cli._normalize_handler_result(
            attempt,
            phase_result,
            root=tmp_path,
            trust_phase_results=True,
        )
        assert normalized.status == status
        assert normalized.outcome == outcome

    def test_arbitrary_handler_cannot_construct_trusted_phase_result(self) -> None:
        with pytest.raises(ValueError, match="trusted_phase_result"):
            cli._TrustedPhaseResult(
                cli.TerminalResult(
                    "failed",
                    "cleanup_incomplete",
                    "window-task7",
                    "artifact.json",
                    "f" * 64,
                ),
                _guard=object(),
            )

    def test_arbitrary_run_command_handler_cannot_mint_reserved_reduced_outcome(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        tmp_path.chmod(0o700)
        authorization = driver.WindowAuthorization(
            window_id="window-task7",
            phases=("vulkan_baseline", "cuda_candidate"),
            boot_id="boot-task7",
            nonce="a" * 64,
            issued_at="2026-07-24T10:00:00Z",
            expires_at="2026-07-24T14:00:00Z",
            owner="owner",
        )
        monkeypatch.setattr(
            driver, "parse_window_authorization", lambda _data: authorization
        )
        real_open = driver.open_bench_file
        monkeypatch.setattr(
            driver,
            "open_bench_file",
            lambda relative, *, root: (
                b"authorization"
                if relative == "authority.json"
                else real_open(relative, root=root)
            ),
        )
        fields = {
            "phase": "vulkan_baseline",
            "window_id": authorization.window_id,
            "boot_id": authorization.boot_id,
            "outcome": "cleanup_incomplete",
            "spawned": False,
            "timestamp": FIXED_TIMESTAMP,
        }
        reduced = driver._canonical_json(
            {
                "schema": driver.REFUSAL_SCHEMA,
                "binding_sha256": hashlib.sha256(
                    driver._canonical_json(fields)
                ).hexdigest(),
                "fields": fields,
            }
        )
        (tmp_path / "forged-reduced.json").write_bytes(reduced)
        (tmp_path / "forged-reduced.json").chmod(0o600)
        def arbitrary_handler(
            _attempt: driver.CommandAttempt,
            *,
            root: Path,
            authorization: driver.WindowAuthorization,
        ) -> object:
            return cli._phase_artifact_result(
                "forged-reduced.json",
                expected_phase="vulkan_baseline",
                expected_window_id=authorization.window_id,
                root=root,
            )

        rc = cli._run_command(
            "vulkan-baseline",
            arbitrary_handler,
            root=tmp_path,
            clock=_FixedClock("production"),
            authority_ref="authority.json",
        )
        terminal = _one_terminal_line(capfd.readouterr().out)

        assert rc == 4
        assert terminal["status"] == "failed"
        assert terminal["outcome"] == "provider_uncertain"

    @pytest.mark.parametrize(
        ("command", "parser_name"),
        (
            ("vulkan-baseline", "parse_window_authorization"),
            ("cuda-candidate", "parse_continuation"),
        ),
    )
    def test_both_phase_parse_failures_are_null_and_nonce_unburned(
        self,
        command: str,
        parser_name: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tmp_path.chmod(0o700)
        monkeypatch.setattr(
            driver, "open_bench_file", lambda _relative, *, root: b"malformed"
        )
        monkeypatch.setattr(
            driver,
            parser_name,
            lambda _data: (_ for _ in ()).throw(ValueError("malformed")),
        )
        called = False

        def handler(
            _attempt: driver.CommandAttempt,
            *,
            root: Path,
            authorization: object,
        ) -> object:
            nonlocal called
            called = True
            return None

        assert (
            cli._run_command(
                command,
                handler,
                root=tmp_path,
                clock=_FixedClock("production"),
                authority_ref="authority.json",
            )
            == 3
        )
        assert called is False
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize(
        "hazard", ("schema", "phase", "window", "malformed")
    )
    def test_reduced_artifact_complete_refusal_matrix(
        self, hazard: str, tmp_path: Path
    ) -> None:
        fields = {
            "phase": (
                "cuda_candidate" if hazard == "phase" else "vulkan_baseline"
            ),
            "window_id": "wrong-window" if hazard == "window" else "window-task7",
            "boot_id": "boot-task7",
            "outcome": "preflight_service_active",
            "spawned": False,
            "timestamp": FIXED_TIMESTAMP,
        }
        wrapper: bytes
        if hazard == "malformed":
            wrapper = b"{"
        else:
            wrapper = driver._canonical_json(
                {
                    "schema": (
                        driver.PHASE_PACKET_SCHEMA
                        if hazard == "schema"
                        else driver.REFUSAL_SCHEMA
                    ),
                    "binding_sha256": hashlib.sha256(
                        driver._canonical_json(fields)
                    ).hexdigest(),
                    "fields": fields,
                }
            )
        path = tmp_path / "reduced.json"
        path.write_bytes(wrapper)
        path.chmod(0o600)
        with pytest.raises(driver.BenchRefusal, match="provider_uncertain"):
            cli._phase_artifact_result(
                "reduced.json",
                expected_phase="vulkan_baseline",
                expected_window_id="window-task7",
                root=tmp_path,
            )

    @pytest.mark.parametrize(
        ("command", "phase"),
        (
            ("vulkan-baseline", "vulkan_baseline"),
            ("cuda-candidate", "cuda_candidate"),
        ),
    )
    def test_phase_main_calls_collector_verify_and_run_once_without_residue(
        self,
        command: str,
        phase: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        root = tmp_path / command
        root.mkdir(mode=0o700)
        root.chmod(0o700)
        observation = replace(
            _static_test_observation(),
            runtime_identity=cm.RuntimeIdentity(**_task6_identity_fields()),
        )
        policy = driver.ProductionArtifactPolicy()
        window = driver.WindowAuthorization(
            window_id="window-task7",
            phases=("vulkan_baseline", "cuda_candidate"),
            boot_id="boot-task7",
            nonce="a" * 64,
            issued_at="2026-07-24T10:00:00Z",
            expires_at="2026-07-24T14:00:00Z",
            owner="owner",
        )
        continuation = driver.Continuation(
            window_id=window.window_id,
            phases=("cuda_candidate",),
            boot_id=window.boot_id,
            nonce="b" * 64,
            issued_at="2026-07-24T12:00:00Z",
            expires_at="2026-07-24T13:00:00Z",
            owner=window.owner,
            parent_vulkan_packet_sha256="c" * 64,
        )
        authority = window if command == "vulkan-baseline" else continuation
        authority_kind = (
            "window_authorization"
            if command == "vulkan-baseline"
            else "continuation"
        )
        authority_fields = {
            "binding_sha256": authority.preimage_sha256,
            "window_id": authority.window_id,
            "phases": authority.phases,
            "boot_id": authority.boot_id,
            "nonce": authority.nonce,
            "issued_at": authority.issued_at,
            "expires_at": authority.expires_at,
            "owner": authority.owner,
        }
        if type(authority) is driver.Continuation:
            authority_fields["parent_vulkan_packet_sha256"] = (
                authority.parent_vulkan_packet_sha256
            )
        authority_ref = "authority.json"
        driver.write_private_file(
            authority_ref,
            policy.encode(authority_kind, authority_fields),
            root=root,
        )
        static_ref = "static.json"
        driver.write_private_file(
            static_ref,
            policy.encode(
                "static_preflight",
                cli._static_preflight_fields(observation.static_doc),
            ),
            root=root,
        )
        calls = {"collect": 0, "verify": 0, "run": 0}
        monkeypatch.setattr(driver, "BENCH_ROOT", root)

        def collect(**_kwargs: object) -> cli.StaticObservation:
            calls["collect"] += 1
            return observation

        monkeypatch.setattr(cli, "collect_static_observation", collect)

        def verify(*_args: object, **_kwargs: object) -> Path:
            calls["verify"] += 1
            assert not (root / "preimages").exists()
            return root / "preimages" / "verified.json"

        monkeypatch.setattr(driver, "verify_existing_immutable", verify)
        config = type(
            "Config",
            (),
            {"phase": phase, "window_id": window.window_id},
        )()
        monkeypatch.setattr(
            cli,
            "_vulkan_config" if command == "vulkan-baseline" else "_cuda_config",
            lambda _args, _observation: config,
        )
        monkeypatch.setattr(
            cli, "_production_providers", lambda _phase, _identity: object()
        )

        def run(
            _config: object, _providers: object, *, root: Path
        ) -> Path:
            calls["run"] += 1
            assert calls == {"collect": 1, "verify": 1, "run": 1}
            assert not (root / "preimages").exists()
            fields = {
                "phase": phase,
                "window_id": window.window_id,
                "boot_id": window.boot_id,
                "outcome": "preflight_service_active",
                "spawned": False,
                "timestamp": FIXED_TIMESTAMP,
            }
            relative = "refusals/reduced.json"
            driver.write_private_file(
                relative,
                driver._canonical_json(
                    {
                        "schema": driver.REFUSAL_SCHEMA,
                        "binding_sha256": hashlib.sha256(
                            driver._canonical_json(fields)
                        ).hexdigest(),
                        "fields": fields,
                    }
                ),
                root=root,
            )
            return root / relative

        monkeypatch.setattr(driver, "run_phase", run)
        common = (
            "--static-preflight",
            static_ref,
            "--static-admission",
            "static-admission.json",
            "--static-completion",
            "static-completion.json",
        )
        argv = (
            (
                command,
                "--window-authorization",
                authority_ref,
                *common,
            )
            if command == "vulkan-baseline"
            else (
                command,
                "--continuation",
                authority_ref,
                "--parent-window",
                "parent-window.json",
                "--parent-packet",
                "parent-packet.json",
                "--parent-admission",
                "parent-admission.json",
                "--parent-completion",
                "parent-completion.json",
                *common,
            )
        )
        assert cli.main(argv) == 3
        terminal = _one_terminal_line(capfd.readouterr().out)
        assert terminal["status"] == "refused"
        assert terminal["window_id"] == window.window_id
        assert calls == {"collect": 1, "verify": 1, "run": 1}
        assert not (root / "markers").exists()
        assert not (root / "preimages").exists()
        assert not any("completion" in path.name for path in root.rglob("*.json"))

    @pytest.mark.parametrize(
        ("command", "phase"),
        (
            ("vulkan-baseline", "vulkan_baseline"),
            ("cuda-candidate", "cuda_candidate"),
        ),
    )
    def test_verify_existing_refusal_is_pre_run_nonce_unburned_tree_stable(
        self,
        command: str,
        phase: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / command
        root.mkdir(mode=0o700)
        root.chmod(0o700)
        observation = replace(
            _static_test_observation(),
            runtime_identity=cm.RuntimeIdentity(**_task6_identity_fields()),
        )
        static_ref = "static.json"
        driver.write_private_file(
            static_ref,
            driver.ProductionArtifactPolicy().encode(
                "static_preflight",
                cli._static_preflight_fields(observation.static_doc),
            ),
            root=root,
        )
        attempt = driver._admit_command(
            command=command,
            window_id="window-task7",
            policy=driver.ProductionArtifactPolicy(),
            clock=_FixedClock("production"),
            root=root,
        )
        before = {
            str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        authority: driver.WindowAuthorization | driver.Continuation
        if phase == "vulkan_baseline":
            authority = driver.WindowAuthorization(
                window_id="window-task7",
                phases=("vulkan_baseline", "cuda_candidate"),
                boot_id="boot-task7",
                nonce="a" * 64,
                issued_at="2026-07-24T10:00:00Z",
                expires_at="2026-07-24T14:00:00Z",
                owner="owner",
            )
            args = cli.build_parser().parse_args(
                (command, *self.VULKAN_ARGS)
            )
        else:
            authority = driver.Continuation(
                window_id="window-task7",
                phases=("cuda_candidate",),
                boot_id="boot-task7",
                nonce="b" * 64,
                issued_at="2026-07-24T12:00:00Z",
                expires_at="2026-07-24T13:00:00Z",
                owner="owner",
                parent_vulkan_packet_sha256="c" * 64,
            )
            args = cli.build_parser().parse_args((command, *self.CUDA_ARGS))
        args.static_preflight = static_ref
        monkeypatch.setattr(
            cli,
            "collect_static_observation",
            lambda **_kwargs: observation,
        )
        monkeypatch.setattr(
            driver,
            "verify_existing_immutable",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                driver.BenchRefusal("filesystem_hazard")
            ),
        )
        monkeypatch.setattr(
            driver,
            "run_phase",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("run_phase called")
            ),
        )
        with pytest.raises(driver.BenchRefusal, match="filesystem_hazard"):
            cli._phase_handler(
                attempt,
                root=root,
                clock=_FixedClock("production"),
                args=args,
                authorization=authority,
            )
        after = {
            str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        assert after == before
        assert not (root / "markers").exists()
        assert not (root / "preimages").exists()
