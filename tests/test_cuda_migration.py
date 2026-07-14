"""Adversarial contract tests for the authoring-only CUDA migration helper."""

from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from scripts import cuda_migration as cm


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
SHA_E = "e" * 64
TS = "2026-07-10T12:00:00Z"

MODEL_SHA = "4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095"
CORPUS_SHA = "ba126352982e734ff1e2742aaef329cfcc496371fd53c59d0cf21f4c4a487104"
ORDER_SHA = "cc9cd81c3110bc37d6c9bfd30bce0267b6cbfc3ffef7fb9abdc8615e42d10575"
CUDA_RELEASE = "/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89"
CUDA_TOOLKIT_LIB = "/usr/local/cuda-13.2/targets/x86_64-linux/lib"
CUDA_RUNTIME_LD_PATH = f"{CUDA_RELEASE}:{CUDA_TOOLKIT_LIB}"


def argv(port: str) -> tuple[str, ...]:
    return (
        "-m",
        "/home/rohit/maez/models/llamacpp/mtp/Qwen3.6-27B-UD-Q4_K_XL.gguf",
        "--alias",
        "qwen36-27b-mtp",
        "--host",
        "127.0.0.1",
        "--port",
        port,
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


HELP = """
--alias NAME
--ctx-size N
--parallel N
--n-gpu-layers N
-fa, --flash-attn [on|off]
--cache-type-k TYPE
--cache-type-v TYPE
--spec-type [none|draft-mtp]
--spec-draft-n-max N
--kv-unified
-fit [on|off]
"""


def evidence(phase: str, status: str = "pass", *, digest: str = SHA_D) -> cm.PhaseEvidence:
    if status == "not_attempted":
        return cm.PhaseEvidence(
            phase=phase,
            status=status,
            artifact_sha256=None,
            timestamp=None,
        )
    return cm.PhaseEvidence(
        phase=phase,
        status=status,
        artifact_sha256=digest,
        timestamp=TS,
    )


def make_identity(**overrides: object) -> cm.RuntimeIdentity:
    values: dict[str, object] = {
        "tag": "b9596",
        "commit": "18ef86ecec723361362a332a79b4d913fd724d40",
        "version": 9596,
        "alias": "qwen36-27b-mtp",
        "model_sha256": MODEL_SHA,
        "model_bytes": 17_909_097_600,
        "runtime_sha256": SHA_B,
        "library_hashes": {"libggml-cuda.so": SHA_C},
        "effective_args": argv("18080"),
        "mode": "bench",
        "production_override_sha256": SHA_A,
        "backend_environment": {
            "CUDA_VISIBLE_DEVICES": "0",
            "GGML_VK_VISIBLE_DEVICES": "",
            "LD_LIBRARY_PATH": CUDA_RUNTIME_LD_PATH,
        },
        "runtime_manifest_sha256": SHA_D,
        "rollback_manifest_sha256": SHA_E,
        "cuda_toolkit": "13.2",
        "cuda_compiler": "13.2.78",
        "cmake_version": "3.31.6",
        "driver_version": "595.71.05",
        "gpu_identifier": "NVIDIA GeForce RTX 4090",
        "compute_capability": "8.9",
    }
    values.update(overrides)
    return cm.RuntimeIdentity.from_static_evidence(**values)


def cycles(*, peak: float, topology: str = SHA_A) -> tuple[cm.CycleMetrics, ...]:
    return tuple(
        cm.CycleMetrics(
            cycle=index,
            topology_sha256=topology,
            bar1_before_percent=2.0 + index,
            bar1_after_load_percent=40.0 + index,
            bar1_after_inference_percent=peak - 3 + index,
            bar1_after_unload_percent=2.0 + index,
            vram_before_mib=500 + index,
            vram_after_load_mib=22_000 + index,
            vram_after_inference_mib=22_500 + index,
            vram_after_unload_mib=500 + index,
        )
        for index in (1, 2, 3)
    )


def live_turns() -> tuple[cm.LiveTurnWitness, ...]:
    return tuple(
        cm.LiveTurnWitness(
            ordinal=index,
            latency_ms=10_000.0 + index,
            false_absence_count=0,
            wrong_answered_ungrounded_count=0,
            type_regression_count=0,
            recall_posture="pass",
            mtp_initialized=True,
            mtp_accepted_tokens=1,
            output_length=128 + index,
            artifact_sha256=f"{index}" * 64,
        )
        for index in range(1, 8)
    )


def make_summary(phase: str = "cuda_candidate", **overrides: object) -> cm.BenchSummary:
    values: dict[str, object] = {
        "phase": phase,
        "alias": "qwen36-27b-mtp",
        "model_sha256": MODEL_SHA,
        "corpus_sha256": CORPUS_SHA,
        "order_sha256": ORDER_SHA,
        "sample_n": 7,
        "warmup_count": 3,
        "measured_sample_count": 21,
        "load_cycles": 3,
        "seven_turn_max_ms": 11_000.0,
        "p95_e2e_ms": 900.0 if phase == "cuda_candidate" else 1_000.0,
        "median_decode_tps": 97.0 if phase == "cuda_candidate" else 100.0,
        "median_prefill_tps": 850.0,
        "cycles": cycles(peak=80.0 if phase == "cuda_candidate" else 82.0),
        "mtp_drafted_tokens": 300,
        "mtp_accepted_tokens": 210,
        "mtp_rejected_tokens": 90,
        "mtp_initialized": True,
        "false_absence_count": 0,
        "wrong_answered_ungrounded_count": 0,
        "type_regression_count": 0,
        "recall_posture": "pass",
        "quality_failure_count": 0,
        "owner_voice_evidence": evidence("owner_voice_review"),
        "kernel_counters": cm.KernelCounters.zero(),
        "crash_count": 0,
        "restart_count": 0,
        "hang_count": 0,
        "timeout_count": 0,
        "unload_leak_mib": 0.0,
        "rollback_witness": make_rollback_witness(),
        "cold_boot_witness": None,
        "provisional_live_witness": None,
    }
    values.update(overrides)
    return cm.BenchSummary(**values)


def backend(phase: str) -> cm.RuntimeBackendWitness:
    if phase == "vulkan_baseline":
        path = "/home/rohit/llama.cpp-release/llama-b9596/llama-b9596/libggml-vulkan.so"
        timestamp = "2026-07-10T12:00:10Z"
    elif phase == "cuda_candidate":
        path = "/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/libggml-cuda.so"
        timestamp = "2026-07-10T12:00:30Z"
    elif phase == "cold_boot":
        path = "/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/libggml-cuda.so"
        timestamp = "2026-07-10T12:01:55Z"
    else:
        path = "/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/libggml-cuda.so"
        timestamp = "2026-07-10T12:03:55Z"
    return cm.RuntimeBackendWitness.from_proc_maps(path, phase=phase, timestamp=timestamp)


def containment_snapshot(phase: str, boundary: str, **overrides: object) -> cm.ContainmentSnapshot:
    values: dict[str, object] = {
        "phase": phase,
        "boundary": boundary,
        "timestamp": TS,
        "screen_flag_value": "0",
        "active_state": "inactive",
        "substate": "dead",
        "enabled_state": "disabled",
        "port_closed": True,
        "flag_source_sha256": SHA_D,
        "vision_unit_sha256": SHA_E,
        "artifact_sha256": SHA_A,
    }
    values.update(overrides)
    return cm.ContainmentSnapshot(**values)


def clean_containment(**replacement: object) -> cm.ContainmentWitness:
    phase_times = {
        "vulkan_baseline": (
            "2026-07-10T12:00:00Z",
            "2026-07-10T12:00:20Z",
        ),
        "cuda_candidate": (
            "2026-07-10T12:00:20Z",
            "2026-07-10T12:00:40Z",
        ),
        "vulkan_rollback": (
            "2026-07-10T12:00:20Z",
            "2026-07-10T12:00:40Z",
        ),
    }
    snapshots = [
        containment_snapshot(
            phase,
            boundary,
            timestamp=phase_times[phase][0 if boundary == "before" else 1],
        )
        for phase in ("vulkan_baseline", "cuda_candidate", "vulkan_rollback")
        for boundary in ("before", "after")
    ]
    if replacement:
        snapshots[-1] = replace(snapshots[-1], **replacement)
    return cm.ContainmentWitness(tuple(snapshots))


def make_rollback_witness() -> cm.RollbackWitness:
    containment = clean_containment()
    return cm.RollbackWitness(
        unit_sha256=cm.FROZEN_VULKAN_UNIT_SHA256,
        dropin_sha256=cm.FROZEN_VULKAN_DROPIN_SHA256,
        runtime_sha256=cm.FROZEN_VULKAN_RUNTIME_SHA256,
        model_sha256=MODEL_SHA,
        alias="qwen36-27b-mtp",
        health_state="healthy",
        mtp_initialized=True,
        mtp_accepted_tokens=7,
        restart_count=0,
        kernel_counters=cm.KernelCounters.zero(),
        bar1_percent=20.0,
        vram_mib=22_000.0,
        shared_library_manifest_sha256=cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
        effective_args_sha256=cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
        containment_artifact_sha256=containment.phase_binding("vulkan_rollback"),
        artifact_sha256=SHA_B,
        timestamp="2026-07-10T12:00:30Z",
    )


def evaluate(
    candidate: cm.BenchSummary | None = None,
    *,
    control: cm.BenchSummary | None = None,
    control_maps: cm.RuntimeBackendWitness | None = None,
    candidate_maps: cm.RuntimeBackendWitness | None = None,
    containment: cm.ContainmentWitness | None = None,
    authorization: cm.AuthorizationWitness | None = None,
    live_authorization: cm.AuthorizationWitness | None = None,
    runtime_identity: cm.RuntimeIdentity | None = None,
) -> cm.PromotionVerdict:
    boot = authorization or cm.AuthorizationWitness(
        "boot_authorization", "not_attempted", None, None, None
    )
    return cm.evaluate_promotion(
        control or make_summary("vulkan_baseline"),
        candidate or make_summary(),
        control_maps or backend("vulkan_baseline"),
        candidate_maps or backend("cuda_candidate"),
        containment or clean_containment(),
        boot,
        live_authorization
        or cm.AuthorizationWitness("live_witness_authorization", "not_attempted", None, None, None),
        runtime_identity
        or make_identity(
            mode=("bench" if boot.status == "not_attempted" else "production"),
            effective_args=argv("18080" if boot.status == "not_attempted" else "8080"),
        ),
    )


class IdentityAndArgvTests(unittest.TestCase):
    def test_frozen_identity_uses_authoritative_model_hash(self) -> None:
        self.assertEqual(MODEL_SHA, cm.FROZEN_MODEL_SHA256)
        self.assertEqual("cuda", make_identity().backend)
        with self.assertRaisesRegex(ValueError, "model_identity_mismatch"):
            make_identity(model_sha256=SHA_A)

    def test_paths_are_restricted_to_three_canonical_roots(self) -> None:
        for path in (
            Path("relative/model.gguf"),
            Path("/tmp/model.gguf"),
            Path("/home/rohit/private/model.gguf"),
            Path("/home/rohit/maez/../private/model.gguf"),
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "canonical_asset_path"):
                    cm.validate_asset_path(path)

    def test_static_bundle_and_runtime_maps_are_separate(self) -> None:
        identity = make_identity()
        witness = backend("cuda_candidate")
        self.assertFalse(hasattr(identity, "mapped_libraries"))
        self.assertEqual("cuda", witness.backend)
        self.assertEqual("cuda_candidate", witness.phase)
        self.assertEqual(64, len(witness.maps_sha256))

    def test_runtime_maps_require_expected_backend_and_release_root(self) -> None:
        cases = (
            (
                "/home/rohit/llama.cpp-release/llama-b9596/llama-b9596/libggml-cuda.so",
                "vulkan_baseline",
            ),
            ("/tmp/libggml-cuda.so", "cuda_candidate"),
            (
                "/home/rohit/llama.cpp-release/other/libggml-cuda.so",
                "cuda_candidate",
            ),
        )
        for maps_text, phase in cases:
            with self.subTest(phase=phase, maps_text=maps_text):
                with self.assertRaisesRegex(
                    ValueError, "(?:backend_(?:unproven|release_root)|canonical_asset_path)"
                ):
                    cm.RuntimeBackendWitness.from_proc_maps(maps_text, phase=phase, timestamp=TS)

    def test_closed_mode_specific_argument_vectors(self) -> None:
        cm.validate_exact_features(HELP, argv("18080"), mode="bench")
        cm.validate_exact_features(HELP, argv("8080"), mode="production")

        bad_vectors = (
            ("bench", argv("8080")),
            ("production", argv("18080")),
            ("bench", argv("8081")),
            ("bench", argv("8082")),
            ("bench", argv("18080") + ("--verbose",)),
            ("bench", argv("18080") + ("--ctx-size", "40960")),
            ("bench", tuple("0.0.0.0" if v == "127.0.0.1" else v for v in argv("18080"))),
        )
        for mode, args in bad_vectors:
            with self.subTest(mode=mode, args=args):
                with self.assertRaisesRegex(ValueError, "exact_features_mismatch"):
                    cm.validate_exact_features(HELP, args, mode=mode)

    def test_toolchain_and_gpu_metadata_are_closed_and_bounded(self) -> None:
        cases = {
            "cuda_toolkit": "13.3",
            "cuda_compiler": "13.1; rm -rf",
            "cmake_version": "latest",
            "driver_version": "999999.1.1",
            "gpu_identifier": "prompt: secret",
            "compute_capability": "9.0",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "runtime_identity_mismatch"):
                    make_identity(**{field: value})


class EvidenceAndMeasurementTests(unittest.TestCase):
    def test_phase_evidence_is_hash_bound_and_tri_state(self) -> None:
        self.assertEqual("pass", evidence("owner_voice_review").status)
        self.assertEqual(
            "not_attempted",
            evidence("cold_boot", "not_attempted").status,
        )
        with self.assertRaisesRegex(ValueError, "phase_evidence"):
            cm.PhaseEvidence(
                phase="owner_voice_review",
                status="pass",
                artifact_sha256=None,
                timestamp=None,
            )
        with self.assertRaisesRegex(ValueError, "phase_evidence"):
            cm.PhaseEvidence(
                phase="owner_voice_review",
                status="maybe",
                artifact_sha256=SHA_A,
                timestamp=TS,
            )

    def test_authorization_cannot_be_supplied_as_a_bool(self) -> None:
        with self.assertRaises(TypeError):
            cm.evaluate_promotion(
                make_summary("vulkan_baseline"),
                make_summary(),
                backend("vulkan_baseline"),
                backend("cuda_candidate"),
                clean_containment(),
                owner_authorized=True,
            )

    def test_exact_counts_and_frozen_manifest_identity_are_required(self) -> None:
        cases = (
            {"sample_n": 6},
            {"warmup_count": 2},
            {"measured_sample_count": 20},
            {"load_cycles": 2},
            {"corpus_sha256": SHA_A},
            {"order_sha256": SHA_B},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, "bench_identity_mismatch"):
                    make_summary(**changes)

    def test_mtp_arithmetic_and_nonzero_acceptance_are_required(self) -> None:
        for changes in (
            {"mtp_drafted_tokens": 299},
            {"mtp_accepted_tokens": 0, "mtp_rejected_tokens": 300},
            {"mtp_initialized": False},
        ):
            with self.subTest(changes=changes):
                verdict = evaluate(make_summary(**changes))
                self.assertEqual("keep_vulkan", verdict.decision)

    def test_positive_summary_measurements_reject_zero_as_missing(self) -> None:
        for field in (
            "seven_turn_max_ms",
            "p95_e2e_ms",
            "median_decode_tps",
            "median_prefill_tps",
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "positive_measurement"):
                    make_summary(**{field: 0.0})

    def test_cycle_metrics_accepts_honest_zero_measurements(self) -> None:
        cycle = cm.CycleMetrics(
            cycle=1,
            topology_sha256=SHA_A,
            bar1_before_percent=0.0,
            bar1_after_load_percent=50.0,
            bar1_after_inference_percent=50.0,
            bar1_after_unload_percent=0.0,
            vram_before_mib=0,
            vram_after_load_mib=18_000,
            vram_after_inference_mib=18_100,
            vram_after_unload_mib=0,
        )
        self.assertTrue(cycle.unload_complete)

    def test_cycle_metrics_rejects_float_vram(self) -> None:
        with self.assertRaisesRegex(ValueError, "vram_integer_mib"):
            cm.CycleMetrics(
                cycle=1,
                topology_sha256=SHA_A,
                bar1_before_percent=10.0,
                bar1_after_load_percent=50.0,
                bar1_after_inference_percent=50.0,
                bar1_after_unload_percent=10.0,
                vram_before_mib=1.5,
                vram_after_load_mib=18_000,
                vram_after_inference_mib=18_100,
                vram_after_unload_mib=1_000,
            )

    def test_cycle_metrics_rejects_negative_and_over_100_bar1(self) -> None:
        for field_value in (-0.1, 100.1):
            with self.subTest(value=field_value):
                with self.assertRaisesRegex(ValueError, "positive_measurement"):
                    cm.CycleMetrics(
                        cycle=1,
                        topology_sha256=SHA_A,
                        bar1_before_percent=field_value,
                        bar1_after_load_percent=50.0,
                        bar1_after_inference_percent=50.0,
                        bar1_after_unload_percent=10.0,
                        vram_before_mib=100,
                        vram_after_load_mib=18_000,
                        vram_after_inference_mib=18_100,
                        vram_after_unload_mib=1_000,
                    )

    def test_cycle_metrics_rejects_bool_and_float_cycle_numbers(self) -> None:
        for cycle_number in (True, 1.0):
            with self.subTest(cycle=cycle_number):
                with self.assertRaisesRegex(ValueError, "bench_identity_mismatch"):
                    cm.CycleMetrics(
                        cycle=cycle_number,
                        topology_sha256=SHA_A,
                        bar1_before_percent=10.0,
                        bar1_after_load_percent=50.0,
                        bar1_after_inference_percent=50.0,
                        bar1_after_unload_percent=10.0,
                        vram_before_mib=100,
                        vram_after_load_mib=18_000,
                        vram_after_inference_mib=18_100,
                        vram_after_unload_mib=1_000,
                    )

    def test_cycle_metrics_rejects_huge_integer_bar1_with_typed_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive_measurement"):
            cm.CycleMetrics(
                cycle=1,
                topology_sha256=SHA_A,
                bar1_before_percent=10**1000,
                bar1_after_load_percent=50.0,
                bar1_after_inference_percent=50.0,
                bar1_after_unload_percent=10.0,
                vram_before_mib=100,
                vram_after_load_mib=18_000,
                vram_after_inference_mib=18_100,
                vram_after_unload_mib=1_000,
            )

    def test_cycles_bind_topology_worst_bar1_and_complete_unload(self) -> None:
        summary = make_summary()
        self.assertEqual(80.0, summary.steady_bar1_percent)
        self.assertEqual(SHA_A, summary.topology_sha256)

        mixed = list(cycles(peak=80.0))
        mixed[-1] = replace(mixed[-1], topology_sha256=SHA_B)
        with self.assertRaisesRegex(ValueError, "topology_mismatch"):
            make_summary(cycles=tuple(mixed))

        leaked = list(cycles(peak=80.0))
        leaked[-1] = replace(leaked[-1], vram_after_unload_mib=999)
        verdict = evaluate(make_summary(cycles=tuple(leaked)))
        self.assertEqual("keep_vulkan", verdict.decision)
        self.assertIn("unload_incomplete", verdict.reasons)

    def test_control_and_candidate_must_share_topology(self) -> None:
        verdict = evaluate(make_summary(cycles=cycles(peak=80.0, topology=SHA_B)))
        self.assertEqual("keep_vulkan", verdict.decision)
        self.assertIn("topology_mismatch", verdict.reasons)

    def test_explicit_quality_fields_are_hard_gates(self) -> None:
        cases = (
            ("false_absence", {"false_absence_count": 1}),
            (
                "wrong_answered_ungrounded",
                {"wrong_answered_ungrounded_count": 1},
            ),
            ("type_regression", {"type_regression_count": 1}),
            ("recall_posture_failed", {"recall_posture": "fail"}),
        )
        for reason, changes in cases:
            with self.subTest(reason=reason):
                verdict = evaluate(make_summary(**changes))
                self.assertEqual("keep_vulkan", verdict.decision)
                self.assertIn(reason, verdict.reasons)

    def test_containment_is_phase_timestamp_and_exact_state_bound(self) -> None:
        witness = clean_containment()
        self.assertTrue(witness.clean)
        self.assertEqual(6, len(witness.phase_hashes))

        for changes in (
            {"active_state": "active"},
            {"substate": "running"},
            {"screen_flag_value": "0  # comment"},
        ):
            with self.subTest(changes=changes):
                verdict = evaluate(containment=clean_containment(**changes))
                self.assertEqual("keep_vulkan", verdict.decision)
                self.assertIn("containment_failed", verdict.reasons)
        with self.assertRaisesRegex(ValueError, "invalid_timestamp"):
            clean_containment(timestamp="2026-07-10T12:00:00")


class GateStateTests(unittest.TestCase):
    def test_complete_bench_without_authorization_is_bench_passed(self) -> None:
        verdict = evaluate()
        self.assertEqual("bench_passed", verdict.decision)

    def test_provisional_requires_hash_bound_owner_authorization(self) -> None:
        bench = evaluate()
        authorization = cm.AuthorizationWitness(
            "boot_authorization",
            "pass",
            SHA_A,
            bench.evidence_sha256,
            "2026-07-10T12:01:00Z",
        )
        verdict = evaluate(authorization=authorization)
        self.assertEqual("provisional_cuda_boot", verdict.decision)
        self.assertEqual(("cold_boot_witness_pending",), verdict.reasons)

    def test_failed_authorization_or_phase_evidence_keeps_vulkan(self) -> None:
        bench = evaluate()
        failed_auth = evaluate(
            authorization=cm.AuthorizationWitness(
                "boot_authorization",
                "fail",
                SHA_A,
                bench.evidence_sha256,
                "2026-07-10T12:01:00Z",
            )
        )
        self.assertEqual("keep_vulkan", failed_auth.decision)
        self.assertIn("owner_authorization_failed", failed_auth.reasons)

    def test_promotion_requires_cold_boot_and_provisional_live_artifacts(self) -> None:
        bench = evaluate()
        boot = cm.AuthorizationWitness(
            "boot_authorization",
            "pass",
            SHA_A,
            bench.evidence_sha256,
            "2026-07-10T12:01:00Z",
        )
        verdict = evaluate(authorization=boot)
        self.assertEqual("provisional_cuda_boot", verdict.decision)

    def test_backend_witnesses_are_gate_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "backend_witness_phase"):
            evaluate(control_maps=backend("cuda_candidate"))

    def test_speed_and_stability_boundaries(self) -> None:
        passing = make_summary(
            seven_turn_max_ms=11_999.999,
            p95_e2e_ms=1_000.0,
            median_decode_tps=97.0,
        )
        self.assertEqual("bench_passed", evaluate(passing).decision)

        cases = (
            ("seven_turn_latency_limit", {"seven_turn_max_ms": 12_000.0}),
            ("p95_regression", {"p95_e2e_ms": 1_000.001}),
            ("decode_throughput_regression", {"median_decode_tps": 96.999}),
            ("bar1_ceiling", {"cycles": cycles(peak=85.0)}),
            (
                "bar1_improvement_insufficient",
                {"cycles": cycles(peak=82.0)},
            ),
        )
        for reason, changes in cases:
            with self.subTest(reason=reason):
                verdict = evaluate(make_summary(**changes))
                self.assertEqual("keep_vulkan", verdict.decision)
                self.assertIn(reason, verdict.reasons)


class ReceiptTests(unittest.TestCase):
    def build(
        self,
        candidate: cm.BenchSummary,
        verdict: cm.PromotionVerdict,
    ) -> dict[str, object]:
        control = make_summary("vulkan_baseline")
        control_maps = backend("vulkan_baseline")
        candidate_maps = backend("cuda_candidate")
        containment = clean_containment()
        authorization = cm.AuthorizationWitness(
            "boot_authorization", "not_attempted", None, None, None
        )
        live_authorization = cm.AuthorizationWitness(
            "live_witness_authorization", "not_attempted", None, None, None
        )
        return cm.build_receipt(
            make_identity(),
            control,
            candidate,
            control_maps,
            candidate_maps,
            containment,
            authorization,
            live_authorization,
            verdict,
            timestamp=TS,
        )

    def test_receipt_reruns_gate_and_rejects_mismatched_verdict(self) -> None:
        original = make_summary()
        verdict = evaluate(original)
        altered = make_summary(p95_e2e_ms=1_000.001)
        with self.assertRaisesRegex(ValueError, "verdict_binding_mismatch"):
            self.build(altered, verdict)

    def test_receipt_includes_backend_and_phase_artifact_hashes(self) -> None:
        candidate = make_summary()
        receipt = self.build(candidate, evaluate(candidate))
        self.assertEqual("producer_evidence_not_verdict", receipt["artifact_role"])
        self.assertEqual(
            backend("vulkan_baseline").maps_sha256,
            receipt["backend_witnesses"]["control_maps_sha256"],
        )
        self.assertEqual(
            backend("cuda_candidate").maps_sha256,
            receipt["backend_witnesses"]["candidate_maps_sha256"],
        )
        self.assertEqual(6, len(receipt["containment"]["phase_hashes"]))

    def test_receipt_refuses_content_markers_and_identity_mixing(self) -> None:
        candidate = make_summary()
        verdict = evaluate(candidate)
        with self.assertRaisesRegex(ValueError, "(?:runtime_identity_mismatch|content_marker)"):
            cm.build_receipt(
                replace(make_identity(), gpu_identifier="prompt: secret"),
                make_summary("vulkan_baseline"),
                candidate,
                backend("vulkan_baseline"),
                backend("cuda_candidate"),
                clean_containment(),
                cm.AuthorizationWitness("boot_authorization", "not_attempted", None, None, None),
                cm.AuthorizationWitness(
                    "live_witness_authorization",
                    "not_attempted",
                    None,
                    None,
                    None,
                ),
                verdict,
                timestamp=TS,
            )

    def test_receipt_is_content_light(self) -> None:
        candidate = make_summary()
        serialized = json.dumps(self.build(candidate, evaluate(candidate))).lower()
        for marker in (
            "prompt",
            "response",
            "transcript",
            "title",
            "pixel",
            '"memory"',
            "/home/rohit/",
            '"environment"',
            '"pid"',
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, serialized)


class SecondReviewContractTests(unittest.TestCase):
    def test_kernel_counters_are_exact_and_any_nonzero_fails(self) -> None:
        clean = cm.KernelCounters(
            reusemappingdb_map=0,
            pmap_cb=0,
            mmu_walk_map=0,
            nv_err_no_memory=0,
            xid=0,
            unmatched_nvrm=0,
        )
        self.assertTrue(clean.clean)
        self.assertFalse(replace(clean, unmatched_nvrm=1).clean)

    def test_boot_and_live_authorizations_are_distinct_parent_bound_artifacts(
        self,
    ) -> None:
        boot = cm.AuthorizationWitness(
            phase="boot_authorization",
            status="pass",
            artifact_sha256=SHA_A,
            parent_sha256=SHA_B,
            timestamp="2026-07-10T12:01:00Z",
        )
        live = cm.AuthorizationWitness(
            phase="live_witness_authorization",
            status="pass",
            artifact_sha256=SHA_C,
            parent_sha256=SHA_D,
            timestamp="2026-07-10T12:03:00Z",
        )
        self.assertNotEqual(boot.phase, live.phase)
        self.assertNotEqual(boot.binding_sha256, live.binding_sha256)

    def test_rollback_witness_binds_exact_incumbent_and_health(self) -> None:
        containment_hash = SHA_A
        witness = cm.RollbackWitness(
            unit_sha256=cm.FROZEN_VULKAN_UNIT_SHA256,
            dropin_sha256=cm.FROZEN_VULKAN_DROPIN_SHA256,
            runtime_sha256=cm.FROZEN_VULKAN_RUNTIME_SHA256,
            model_sha256=MODEL_SHA,
            alias="qwen36-27b-mtp",
            health_state="healthy",
            mtp_initialized=True,
            mtp_accepted_tokens=7,
            restart_count=0,
            kernel_counters=cm.KernelCounters.zero(),
            bar1_percent=20.0,
            vram_mib=22_000.0,
            shared_library_manifest_sha256=cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
            effective_args_sha256=cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
            containment_artifact_sha256=containment_hash,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:00:30Z",
        )
        self.assertTrue(witness.passed)
        self.assertFalse(replace(witness, restart_count=1).passed)
        with self.assertRaisesRegex(ValueError, "rollback_identity_mismatch"):
            replace(witness, unit_sha256=SHA_C)

    def test_cold_boot_witness_proves_nonoverlapping_full_topology(self) -> None:
        witness = cm.ColdBootWitness(
            parent_sha256=SHA_A,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:02:00Z",
            topology_sha256=SHA_C,
            load_intervals=(
                cm.LoadInterval(
                    component="primary",
                    started_at="2026-07-10T12:01:10Z",
                    ended_at="2026-07-10T12:01:20Z",
                ),
                cm.LoadInterval(
                    component="judge",
                    started_at="2026-07-10T12:01:21Z",
                    ended_at="2026-07-10T12:01:30Z",
                ),
            ),
            steady_bar1_percent=80.0,
            kernel_counters=cm.KernelCounters.zero(),
            restart_count=0,
            containment_artifact_sha256=SHA_D,
            runtime_sha256=SHA_A,
            runtime_maps_sha256=SHA_B,
            backend="cuda",
            production_override_sha256=SHA_A,
            alias="qwen36-27b-mtp",
            model_sha256=MODEL_SHA,
            model_bytes=17_909_097_600,
            service_health="healthy",
            mtp_initialized=True,
            mtp_accepted_tokens=7,
        )
        self.assertTrue(witness.passed)
        with self.assertRaisesRegex(ValueError, "overlapping_load_intervals"):
            replace(
                witness,
                load_intervals=(
                    witness.load_intervals[0],
                    replace(
                        witness.load_intervals[1],
                        started_at="2026-07-10T12:01:15Z",
                    ),
                ),
            )

    def test_model_size_is_frozen(self) -> None:
        self.assertEqual(17_909_097_600, cm.FROZEN_MODEL_BYTES)
        with self.assertRaisesRegex(ValueError, "model_identity_mismatch"):
            make_identity(model_bytes=17_909_097_599)

    def test_runtime_identity_binds_override_and_exact_backend_environment(self) -> None:
        identity = make_identity(
            production_override_sha256=SHA_A,
            backend_environment={
                "CUDA_VISIBLE_DEVICES": "0",
                "GGML_VK_VISIBLE_DEVICES": "",
                "LD_LIBRARY_PATH": CUDA_RUNTIME_LD_PATH,
            },
        )
        self.assertEqual(64, len(identity.configuration_sha256))
        with self.assertRaisesRegex(ValueError, "backend_environment_mismatch"):
            make_identity(
                production_override_sha256=SHA_A,
                backend_environment={
                    "CUDA_VISIBLE_DEVICES": "0",
                    "GGML_VK_VISIBLE_DEVICES": "0",
                    "LD_LIBRARY_PATH": CUDA_RUNTIME_LD_PATH,
                },
            )

    def test_containment_hashes_are_identical_across_every_reached_phase(self) -> None:
        snapshots = tuple(
            containment_snapshot(phase, boundary)
            for phase in (
                "vulkan_baseline",
                "cuda_candidate",
                "vulkan_rollback",
                "provisional_cuda_boot",
                "cold_boot",
                "provisional_live",
            )
            for boundary in ("before", "after")
        )
        witness = cm.ContainmentWitness(snapshots)
        self.assertTrue(witness.clean)
        self.assertTrue(
            witness.complete_for(
                {
                    "vulkan_baseline",
                    "cuda_candidate",
                    "vulkan_rollback",
                    "provisional_cuda_boot",
                    "cold_boot",
                    "provisional_live",
                }
            )
        )
        changed = list(snapshots)
        changed[-1] = replace(changed[-1], flag_source_sha256=SHA_B)
        self.assertFalse(cm.ContainmentWitness(tuple(changed)).clean)

    def test_full_parent_chain_is_required_for_promotion(self) -> None:
        phase_times = {
            "vulkan_baseline": (
                "2026-07-10T12:00:00Z",
                "2026-07-10T12:00:20Z",
            ),
            "cuda_candidate": (
                "2026-07-10T12:00:20Z",
                "2026-07-10T12:00:40Z",
            ),
            "vulkan_rollback": (
                "2026-07-10T12:00:20Z",
                "2026-07-10T12:00:40Z",
            ),
            "provisional_cuda_boot": (
                "2026-07-10T12:01:05Z",
                "2026-07-10T12:01:40Z",
            ),
            "cold_boot": (
                "2026-07-10T12:01:05Z",
                "2026-07-10T12:02:10Z",
            ),
            "provisional_live": (
                "2026-07-10T12:03:05Z",
                "2026-07-10T12:04:10Z",
            ),
        }
        containment = cm.ContainmentWitness(
            tuple(
                containment_snapshot(
                    phase,
                    boundary,
                    timestamp=phase_times[phase][0 if boundary == "before" else 1],
                )
                for phase in (
                    "vulkan_baseline",
                    "cuda_candidate",
                    "vulkan_rollback",
                    "provisional_cuda_boot",
                    "cold_boot",
                    "provisional_live",
                )
                for boundary in ("before", "after")
            )
        )
        rollback = cm.RollbackWitness(
            unit_sha256=cm.FROZEN_VULKAN_UNIT_SHA256,
            dropin_sha256=cm.FROZEN_VULKAN_DROPIN_SHA256,
            runtime_sha256=cm.FROZEN_VULKAN_RUNTIME_SHA256,
            model_sha256=MODEL_SHA,
            alias="qwen36-27b-mtp",
            health_state="healthy",
            mtp_initialized=True,
            mtp_accepted_tokens=7,
            restart_count=0,
            kernel_counters=cm.KernelCounters.zero(),
            bar1_percent=20.0,
            vram_mib=22_000.0,
            shared_library_manifest_sha256=cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
            effective_args_sha256=cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
            containment_artifact_sha256=containment.phase_binding("vulkan_rollback"),
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:00:30Z",
        )
        candidate = replace(
            make_summary(),
            rollback_witness=rollback,
            kernel_counters=cm.KernelCounters.zero(),
        )
        control = replace(
            make_summary("vulkan_baseline"),
            rollback_witness=rollback,
            kernel_counters=cm.KernelCounters.zero(),
        )
        no_boot = cm.AuthorizationWitness(
            phase="boot_authorization",
            status="not_attempted",
            artifact_sha256=None,
            parent_sha256=None,
            timestamp=None,
        )
        no_live_auth = cm.AuthorizationWitness(
            phase="live_witness_authorization",
            status="not_attempted",
            artifact_sha256=None,
            parent_sha256=None,
            timestamp=None,
        )
        bench = cm.evaluate_promotion(
            control,
            candidate,
            backend("vulkan_baseline"),
            backend("cuda_candidate"),
            containment,
            no_boot,
            no_live_auth,
            make_identity(),
        )
        self.assertEqual("bench_passed", bench.decision)

        boot = cm.AuthorizationWitness(
            phase="boot_authorization",
            status="pass",
            artifact_sha256=SHA_C,
            parent_sha256=bench.evidence_sha256,
            timestamp="2026-07-10T12:01:00Z",
        )
        cold = cm.ColdBootWitness(
            parent_sha256=boot.binding_sha256,
            artifact_sha256=SHA_D,
            timestamp="2026-07-10T12:02:00Z",
            topology_sha256=SHA_E,
            load_intervals=(
                cm.LoadInterval(
                    "primary",
                    "2026-07-10T12:01:10Z",
                    "2026-07-10T12:01:20Z",
                ),
                cm.LoadInterval(
                    "judge",
                    "2026-07-10T12:01:21Z",
                    "2026-07-10T12:01:30Z",
                ),
            ),
            steady_bar1_percent=80.0,
            kernel_counters=cm.KernelCounters.zero(),
            restart_count=0,
            containment_artifact_sha256=containment.phase_binding("cold_boot"),
            runtime_sha256=make_identity().runtime_sha256,
            runtime_maps_sha256=backend("cold_boot").binding_sha256,
            backend="cuda",
            production_override_sha256=SHA_A,
            alias="qwen36-27b-mtp",
            model_sha256=MODEL_SHA,
            model_bytes=17_909_097_600,
            service_health="healthy",
            mtp_initialized=True,
            mtp_accepted_tokens=7,
        )
        live_auth = cm.AuthorizationWitness(
            phase="live_witness_authorization",
            status="pass",
            artifact_sha256=SHA_E,
            parent_sha256=cold.binding_sha256,
            timestamp="2026-07-10T12:03:00Z",
        )
        live = cm.ProvisionalLiveWitness(
            parent_sha256=live_auth.binding_sha256,
            artifact_sha256=SHA_A,
            timestamp="2026-07-10T12:04:00Z",
            containment_artifact_sha256=containment.phase_binding("provisional_live"),
            turns=live_turns(),
            runtime_sha256=make_identity().runtime_sha256,
            runtime_maps_sha256=backend("provisional_live").binding_sha256,
            backend="cuda",
            configuration_sha256=make_identity(
                mode="production", effective_args=argv("8080")
            ).configuration_sha256,
            corpus_sha256=CORPUS_SHA,
            order_sha256=ORDER_SHA,
        )
        candidate = replace(
            candidate,
            cold_boot_witness=cold,
            provisional_live_witness=live,
        )
        verdict = cm.evaluate_promotion(
            control,
            candidate,
            backend("vulkan_baseline"),
            backend("cuda_candidate"),
            containment,
            boot,
            live_auth,
            make_identity(mode="production", effective_args=argv("8080")),
            cold_boot_maps=backend("cold_boot"),
            provisional_live_maps=backend("provisional_live"),
        )
        self.assertEqual("promote_cuda", verdict.decision)

        broken = replace(live_auth, parent_sha256=boot.binding_sha256)
        refused = cm.evaluate_promotion(
            control,
            candidate,
            backend("vulkan_baseline"),
            backend("cuda_candidate"),
            containment,
            boot,
            broken,
            make_identity(mode="production", effective_args=argv("8080")),
            cold_boot_maps=backend("cold_boot"),
            provisional_live_maps=backend("provisional_live"),
        )
        self.assertEqual("keep_vulkan", refused.decision)
        self.assertIn("evidence_chain_invalid", refused.reasons)

    def test_reached_phase_containment_is_required(self) -> None:
        base = clean_containment()
        self.assertFalse(base.complete_for({"cold_boot"}))


class ThirdReviewContractTests(unittest.TestCase):
    def test_provisional_live_is_seven_ordered_measured_turns_not_a_bool(self) -> None:
        turns = tuple(
            cm.LiveTurnWitness(
                ordinal=index,
                latency_ms=10_000.0 + index,
                false_absence_count=0,
                wrong_answered_ungrounded_count=0,
                type_regression_count=0,
                recall_posture="pass",
                mtp_initialized=True,
                mtp_accepted_tokens=1,
                output_length=128 + index,
                artifact_sha256=f"{index}" * 64,
            )
            for index in range(1, 8)
        )
        witness = cm.ProvisionalLiveWitness(
            parent_sha256=SHA_A,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:04:00Z",
            containment_artifact_sha256=SHA_C,
            turns=turns,
            runtime_sha256=SHA_D,
            runtime_maps_sha256=SHA_E,
            backend="cuda",
            configuration_sha256=SHA_A,
            corpus_sha256=CORPUS_SHA,
            order_sha256=ORDER_SHA,
        )
        self.assertTrue(witness.passed)
        with self.assertRaisesRegex(ValueError, "live_turn_order"):
            replace(witness, turns=tuple(reversed(turns)))
        self.assertFalse(
            replace(
                witness,
                turns=(replace(turns[0], latency_ms=12_000.0),) + turns[1:],
            ).passed
        )
        with self.assertRaises(TypeError):
            cm.ProvisionalLiveWitness(
                parent_sha256=SHA_A,
                artifact_sha256=SHA_B,
                timestamp="2026-07-10T12:04:00Z",
                containment_artifact_sha256=SHA_C,
                passed=True,
            )

    def test_cold_boot_binds_cuda_production_identity_and_mtp_health(self) -> None:
        witness = cm.ColdBootWitness(
            parent_sha256=SHA_A,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:02:00Z",
            topology_sha256=SHA_C,
            load_intervals=(
                cm.LoadInterval(
                    "primary",
                    "2026-07-10T12:01:10Z",
                    "2026-07-10T12:01:20Z",
                ),
                cm.LoadInterval(
                    "judge",
                    "2026-07-10T12:01:21Z",
                    "2026-07-10T12:01:30Z",
                ),
            ),
            steady_bar1_percent=80.0,
            kernel_counters=cm.KernelCounters.zero(),
            restart_count=0,
            containment_artifact_sha256=SHA_D,
            runtime_sha256=SHA_A,
            runtime_maps_sha256=SHA_B,
            backend="cuda",
            production_override_sha256=SHA_C,
            alias="qwen36-27b-mtp",
            model_sha256=MODEL_SHA,
            model_bytes=17_909_097_600,
            service_health="healthy",
            mtp_initialized=True,
            mtp_accepted_tokens=7,
        )
        self.assertTrue(witness.passed)
        self.assertFalse(replace(witness, backend="vulkan").passed)
        self.assertFalse(replace(witness, mtp_accepted_tokens=0).passed)

    def test_containment_brackets_each_phase_witness_timestamp(self) -> None:
        witness = cm.ContainmentWitness(
            (
                containment_snapshot("vulkan_baseline", "before", timestamp="2026-07-10T12:00:00Z"),
                containment_snapshot("vulkan_baseline", "after", timestamp="2026-07-10T12:00:20Z"),
                containment_snapshot("cuda_candidate", "before", timestamp="2026-07-10T12:00:20Z"),
                containment_snapshot("cuda_candidate", "after", timestamp="2026-07-10T12:00:40Z"),
                containment_snapshot("vulkan_rollback", "before", timestamp="2026-07-10T12:00:40Z"),
                containment_snapshot("vulkan_rollback", "after", timestamp="2026-07-10T12:01:00Z"),
            )
        )
        self.assertTrue(witness.brackets("vulkan_baseline", "2026-07-10T12:00:10Z"))
        self.assertFalse(witness.brackets("vulkan_baseline", "2026-07-10T12:00:20Z"))

    def test_rollback_binds_library_args_vram_and_bar1(self) -> None:
        containment = clean_containment()
        witness = cm.RollbackWitness(
            unit_sha256=cm.FROZEN_VULKAN_UNIT_SHA256,
            dropin_sha256=cm.FROZEN_VULKAN_DROPIN_SHA256,
            runtime_sha256=cm.FROZEN_VULKAN_RUNTIME_SHA256,
            model_sha256=MODEL_SHA,
            alias="qwen36-27b-mtp",
            health_state="healthy",
            mtp_initialized=True,
            mtp_accepted_tokens=7,
            restart_count=0,
            kernel_counters=cm.KernelCounters.zero(),
            bar1_percent=20.0,
            vram_mib=22_000.0,
            shared_library_manifest_sha256=cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
            effective_args_sha256=cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
            containment_artifact_sha256=containment.phase_binding("vulkan_rollback"),
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:00:30Z",
        )
        self.assertTrue(witness.passed)
        with self.assertRaisesRegex(ValueError, "positive_measurement"):
            replace(witness, vram_mib=0.0)

    def test_receipt_rejects_bench_identity_for_production_decisions(self) -> None:
        self.assertTrue(cm.receipt_mode_allows(make_identity(), decision="bench_passed"))
        self.assertFalse(cm.receipt_mode_allows(make_identity(), decision="promote_cuda"))
        production = make_identity(mode="production", effective_args=argv("8080"))
        self.assertTrue(cm.receipt_mode_allows(production, decision="promote_cuda"))


class FourthReviewContractTests(unittest.TestCase):
    def test_cold_and_live_maps_are_fresh_phase_bound_cuda_witnesses(self) -> None:
        cold = backend("cold_boot")
        live = backend("provisional_live")
        offline = backend("cuda_candidate")
        self.assertEqual("cuda", cold.backend)
        self.assertEqual("cold_boot", cold.phase)
        self.assertEqual("provisional_live", live.phase)
        self.assertNotEqual(offline.binding_sha256, cold.binding_sha256)
        self.assertNotEqual(cold.binding_sha256, live.binding_sha256)

    def test_live_witness_binds_frozen_corpus_and_order(self) -> None:
        witness = cm.ProvisionalLiveWitness(
            parent_sha256=SHA_A,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:04:00Z",
            containment_artifact_sha256=SHA_C,
            turns=live_turns(),
            runtime_sha256=SHA_D,
            runtime_maps_sha256=SHA_E,
            backend="cuda",
            configuration_sha256=SHA_A,
            corpus_sha256=CORPUS_SHA,
            order_sha256=ORDER_SHA,
        )
        self.assertTrue(witness.passed)
        with self.assertRaisesRegex(ValueError, "live_corpus_identity"):
            replace(witness, order_sha256=SHA_B)

    def test_live_turn_output_length_is_positive_content_light_count(self) -> None:
        turn = cm.LiveTurnWitness(
            ordinal=1,
            latency_ms=10_000.0,
            false_absence_count=0,
            wrong_answered_ungrounded_count=0,
            type_regression_count=0,
            recall_posture="pass",
            mtp_initialized=True,
            mtp_accepted_tokens=1,
            output_length=128,
            artifact_sha256=SHA_A,
        )
        self.assertEqual(128, turn.output_length)
        with self.assertRaisesRegex(ValueError, "positive_output_length"):
            replace(turn, output_length=0)


class CodeQualityInvariantTests(unittest.TestCase):
    def test_backend_witness_replace_cannot_bypass_factory_invariants(self) -> None:
        witness = backend("cuda_candidate")
        with self.assertRaisesRegex(ValueError, "backend_witness_invariant"):
            replace(witness, backend="vulkan")
        with self.assertRaisesRegex(ValueError, "backend_witness_invariant"):
            replace(witness, release_root_sha256=SHA_A)
        with self.assertRaisesRegex(ValueError, "invalid_sha256"):
            replace(witness, maps_sha256="not-a-hash")

    def test_runtime_identity_replace_cannot_bypass_factory_invariants(self) -> None:
        identity = make_identity()
        with self.assertRaisesRegex(ValueError, "runtime_identity_mismatch"):
            replace(identity, alias="qwen36-27b-mtp-cuda")
        with self.assertRaisesRegex(ValueError, "backend_environment_mismatch"):
            replace(
                identity,
                backend_environment={
                    "CUDA_VISIBLE_DEVICES": "0",
                    "GGML_VK_VISIBLE_DEVICES": "0",
                    "LD_LIBRARY_PATH": CUDA_RUNTIME_LD_PATH,
                },
            )
        with self.assertRaisesRegex(ValueError, "backend_unproven"):
            replace(identity, backend="vulkan")

    def test_identity_binding_covers_every_receipt_visible_field(self) -> None:
        identity = make_identity()
        valid_changes = (
            {"runtime_sha256": SHA_C},
            {"runtime_manifest_sha256": SHA_C},
            {"rollback_manifest_sha256": SHA_C},
            {"production_override_sha256": SHA_C},
            {"cuda_compiler": "13.2.79"},
            {"cmake_version": "3.31.7"},
            {"driver_version": "595.71.06"},
        )
        for changes in valid_changes:
            with self.subTest(changes=changes):
                changed = replace(identity, **changes)
                self.assertNotEqual(identity.binding_sha256, changed.binding_sha256)

        rejected_changes = (
            {"tag": "b9597"},
            {"gpu_identifier": "NVIDIA RTX 5090"},
            {"compute_capability": "9.0"},
        )
        for changes in rejected_changes:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    replace(identity, **changes)

    def test_evidence_sequences_reject_mutable_lists(self) -> None:
        cold = cm.ColdBootWitness(
            parent_sha256=SHA_A,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:02:00Z",
            topology_sha256=SHA_C,
            load_intervals=(
                cm.LoadInterval(
                    "primary",
                    "2026-07-10T12:01:10Z",
                    "2026-07-10T12:01:20Z",
                ),
                cm.LoadInterval(
                    "judge",
                    "2026-07-10T12:01:21Z",
                    "2026-07-10T12:01:30Z",
                ),
            ),
            steady_bar1_percent=80.0,
            kernel_counters=cm.KernelCounters.zero(),
            restart_count=0,
            containment_artifact_sha256=SHA_D,
            runtime_sha256=SHA_A,
            runtime_maps_sha256=SHA_B,
            backend="cuda",
            production_override_sha256=SHA_C,
            alias="qwen36-27b-mtp",
            model_sha256=MODEL_SHA,
            model_bytes=17_909_097_600,
            service_health="healthy",
            mtp_initialized=True,
            mtp_accepted_tokens=7,
        )
        live = cm.ProvisionalLiveWitness(
            parent_sha256=SHA_A,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:04:00Z",
            containment_artifact_sha256=SHA_C,
            turns=live_turns(),
            runtime_sha256=SHA_D,
            runtime_maps_sha256=SHA_E,
            backend="cuda",
            configuration_sha256=SHA_A,
            corpus_sha256=CORPUS_SHA,
            order_sha256=ORDER_SHA,
        )
        cases = (
            (cold, {"load_intervals": list(cold.load_intervals)}),
            (live, {"turns": list(live.turns)}),
            (make_summary(), {"cycles": list(make_summary().cycles)}),
            (
                clean_containment(),
                {"snapshots": list(clean_containment().snapshots)},
            ),
        )
        for value, changes in cases:
            with self.subTest(value=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "immutable_sequence_required"):
                    replace(value, **changes)

        with self.assertRaises(FrozenInstanceError):
            live.turns = ()


class Task3BuildAndOverrideContractTests(unittest.TestCase):
    BUILD_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_llama_b9596_cuda.sh"
    OVERRIDE = (
        Path(__file__).resolve().parents[1] / "config/systemd/llama-server-b9596-cuda.override.conf"
    )

    def read_required(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"missing Task 3 artifact: {path}")
        return path.read_text(encoding="utf-8")

    def run_shell_function(self, function: str, argument: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; "$2" "$3"',
                "task3-fixture",
                str(self.BUILD_SCRIPT),
                function,
                argument,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_build_script_pins_source_toolchain_and_complete_cmake_shape(self) -> None:
        script = self.read_required(self.BUILD_SCRIPT)
        required = (
            'TAG="b9596"',
            'COMMIT="18ef86ecec723361362a332a79b4d913fd724d40"',
            'NVCC="/usr/local/cuda-13.2/bin/nvcc"',
            'CUDA_LIBRARY_ROOT="/usr/local/cuda-13.2/targets/x86_64-linux/lib"',
            'OFFICIAL_ORIGIN_HTTPS="https://github.com/ggml-org/llama.cpp.git"',
            'OFFICIAL_ORIGIN_SSH="git@github.com:ggml-org/llama.cpp.git"',
            '"-DCMAKE_CUDA_COMPILER=${NVCC}"',
            "-DGGML_CUDA=ON",
            "-DGGML_VULKAN=OFF",
            "-DGGML_CUDA_NCCL=OFF",
            "-DBUILD_SHARED_LIBS=ON",
            "-DGGML_BACKEND_DL=ON",
            "-DGGML_NATIVE=OFF",
            "-DGGML_CPU_ALL_VARIANTS=ON",
            "-DCMAKE_CUDA_ARCHITECTURES=89",
            "'-DCMAKE_INSTALL_RPATH=$ORIGIN'",
            "-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON",
            "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
            "-DLLAMA_BUILD_UI=OFF",
            "-DLLAMA_USE_PREBUILT_UI=OFF",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, script)

    def test_build_script_proves_provenance_and_refuses_path_collisions(self) -> None:
        script = self.read_required(self.BUILD_SCRIPT)
        required = (
            "--source-dir",
            "--output-dir",
            'EXPECTED_OUTPUT_DIR="/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89"',
            'SOURCE_ROOT="/home/rohit/llama.cpp-release/source"',
            'INCUMBENT_DIR="/home/rohit/llama.cpp-release/llama-b9596/llama-b9596"',
            "canonical_existing_dir",
            "canonical_future_path",
            "refuse_existing_path",
            "require_pairwise_disjoint",
            'require_pairwise_disjoint "$SOURCE_DIR" "$BUILD_DIR" "$STAGE_DIR" "$OUTPUT_DIR" "$INCUMBENT_DIR"',
            'git -C "$SOURCE_DIR" remote get-url origin',
            'git -C "$SOURCE_DIR" rev-parse --verify HEAD',
            'git -C "$SOURCE_DIR" rev-parse --verify "refs/tags/${TAG}^{commit}"',
            'git -C "$SOURCE_DIR" rev-parse --short HEAD',
            'git -C "$SOURCE_DIR" describe --exact-match --tags HEAD',
            'git -C "$SOURCE_DIR" status --porcelain=v1 --untracked-files=all',
            "source_generated_residue",
            "tools/ui/node_modules",
            "tools/ui/.svelte-kit",
            "tools/ui/dist",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, script)
        self.assertNotIn("--checksum", script)
        self.assertNotIn("git checkout master", script)
        self.assertNotIn("${COMMIT:0:9}", script)

    def test_build_script_stages_flat_manifest_atomically_on_one_filesystem(self) -> None:
        script = self.read_required(self.BUILD_SCRIPT)
        required = (
            'BUILD_BIN_DIR="${BUILD_DIR}/bin"',
            'cp -a -- "${BUILD_BIN_DIR}/." "$STAGE_DIR/"',
            "stat -c '%d'",
            'MANIFEST_NAME="runtime-manifest.sha256"',
            'MANIFEST_TMP="${STAGE_DIR}/${MANIFEST_NAME}.tmp"',
            "LC_ALL=C",
            "find . -mindepth 1 -maxdepth 1",
            "sort -z",
            "readlink -n --",
            "validate_staged_symlinks",
            "validate_manifest_inputs",
            'mv -T --no-clobber -- "$STAGE_DIR" "$OUTPUT_DIR"',
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, script)

        copy_at = script.find('cp -a -- "${BUILD_BIN_DIR}/." "$STAGE_DIR/"')
        symlink_gate_at = script.find('validate_staged_symlinks "$STAGE_DIR"')
        manifest_input_gate_at = script.find('validate_manifest_inputs "$STAGE_DIR"')
        manifest_at = script.find('MANIFEST_TMP="${STAGE_DIR}/${MANIFEST_NAME}.tmp"')
        publish_at = script.find('mv -T --no-clobber -- "$STAGE_DIR" "$OUTPUT_DIR"')
        self.assertGreaterEqual(min(copy_at, symlink_gate_at, manifest_input_gate_at), 0)
        self.assertLess(copy_at, symlink_gate_at)
        self.assertLess(symlink_gate_at, manifest_input_gate_at)
        self.assertLess(manifest_input_gate_at, manifest_at)
        self.assertLess(manifest_at, publish_at)

    def test_build_script_verifies_candidate_with_a_sanitized_environment(self) -> None:
        script = self.read_required(self.BUILD_SCRIPT)
        required = (
            "env -i",
            'LD_LIBRARY_PATH="$STAGE_DIR:$CUDA_LIBRARY_ROOT"',
            'FLOATING_CUDA_ROOT="/usr/local/cuda"',
            'GGML_VK_VISIBLE_DEVICES=""',
            '"$STAGE_DIR/llama-server" --version',
            '"$STAGE_DIR/llama-server" --help',
            "readelf -d",
            "ldd",
            "not found",
            "require_exact_origin_runpath",
            "libggml-cuda.so",
            "libggml-vulkan.so",
            'grep -F -- "$INCUMBENT_DIR"',
            'grep -F -- "$FLOATING_CUDA_ROOT/"',
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, script)
        self.assertNotIn('LD_LIBRARY_PATH="$STAGE_DIR"', script)

    def test_build_script_has_no_install_network_or_live_service_authority(self) -> None:
        script = self.read_required(self.BUILD_SCRIPT)
        forbidden = (
            "sudo",
            "systemctl",
            "apt-get",
            "apt ",
            "dnf ",
            "yum ",
            "curl ",
            "wget ",
            "git clone",
            "git fetch",
            "npm ",
            "8080",
            "8081",
            "8082",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, script)

    def test_stage_symlinks_are_flat_internal_and_resolve_to_regular_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stage = Path(temp_dir) / "stage"
            stage.mkdir()
            (stage / "libreal.so.1").write_bytes(b"binary")
            (stage / "libreal.so.0").symlink_to("libreal.so.1")
            (stage / "libreal.so").symlink_to("libreal.so.0")
            valid = self.run_shell_function("validate_staged_symlinks", str(stage))
            self.assertEqual(0, valid.returncode, valid.stderr)

        cases = ("absolute", "parent", "broken", "chained_escape")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                stage = root / "stage"
                stage.mkdir()
                outside = root / "outside.so"
                outside.write_bytes(b"outside")
                link = stage / "libbad.so"
                if case == "absolute":
                    link.symlink_to(outside)
                elif case == "parent":
                    link.symlink_to("../outside.so")
                elif case == "broken":
                    link.symlink_to("missing.so")
                else:
                    link.symlink_to("libhop.so")
                    (stage / "libhop.so").symlink_to("../outside.so")
                result = self.run_shell_function("validate_staged_symlinks", str(stage))
                self.assertNotEqual(0, result.returncode)
                self.assertIn("staged_symlink_invalid", result.stderr)

    def test_dynamic_path_gate_requires_one_exact_origin_runpath(self) -> None:
        valid = "0x000000000000001d (RUNPATH) Library runpath: [$ORIGIN]"
        result = self.run_shell_function("require_exact_origin_runpath", valid)
        self.assertEqual(0, result.returncode, result.stderr)

        invalid = (
            "0x0 (RPATH) Library rpath: [$ORIGIN]",
            "0x0 (RUNPATH) Library runpath: [$ORIGIN:/usr/lib]",
            "0x0 (RUNPATH) Library runpath: [/usr/lib:$ORIGIN]",
            "0x0 (RUNPATH) Library runpath: [$ORIGIN]\n0x1 (RUNPATH) Library runpath: [$ORIGIN]",
            "0x0 (RPATH) Library rpath: [/usr/lib]\n0x1 (RUNPATH) Library runpath: [$ORIGIN]",
            "0x0 (NEEDED) Shared library: [libc.so.6]",
        )
        for fixture in invalid:
            with self.subTest(fixture=fixture):
                result = self.run_shell_function("require_exact_origin_runpath", fixture)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("origin_runpath_invalid", result.stderr)

    def test_manifest_inputs_reject_c0_c1_in_names_and_symlink_targets(self) -> None:
        controls = ("\t", "\n", "\x1f", "\x7f", "\x80")
        for control in controls:
            for surface in ("name", "target"):
                with (
                    self.subTest(control=repr(control), surface=surface),
                    tempfile.TemporaryDirectory() as temp_dir,
                ):
                    stage = Path(temp_dir) / "stage"
                    stage.mkdir()
                    if surface == "name":
                        (stage / f"libbad{control}.so").write_bytes(b"binary")
                    else:
                        (stage / "libbad.so").symlink_to(f"libtarget{control}.so")
                    result = self.run_shell_function("validate_manifest_inputs", str(stage))
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("manifest_control_character", result.stderr)

    def test_override_exactly_preserves_the_production_argument_packet(self) -> None:
        override = self.read_required(self.OVERRIDE)
        exec_lines = [line for line in override.splitlines() if line.startswith("ExecStart=")]
        self.assertEqual(2, len(exec_lines))
        self.assertEqual("ExecStart=", exec_lines[0])
        command = shlex.split(exec_lines[1].split("=", 1)[1])
        self.assertEqual(
            "/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/llama-server",
            command[0],
        )
        self.assertEqual(argv("8080"), tuple(command[1:]))

    def test_override_is_cuda_only_and_contains_no_fallback(self) -> None:
        override = self.read_required(self.OVERRIDE)
        environment = {
            line.removeprefix('Environment="').removesuffix('"')
            for line in override.splitlines()
            if line.startswith('Environment="')
        }
        self.assertEqual(
            {
                "CUDA_VISIBLE_DEVICES=0",
                "GGML_VK_VISIBLE_DEVICES=",
                f"LD_LIBRARY_PATH={CUDA_RUNTIME_LD_PATH}",
            },
            environment,
        )
        for forbidden in (
            "/home/rohit/llama.cpp-release/llama-b9596/llama-b9596",
            "/cuda-b9596-migration/",
            "18080",
            "8081",
            "8082",
            "ExecStartPre=",
            "ExecStartPost=",
            "OnFailure=",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, override)


class Task4TruthAndRunbookContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]
    MODEL_STATE = ROOT / "config/model_state.json"
    RUNBOOK = ROOT / "docs/runbooks/llama-b9596-cuda-migration.md"
    GITIGNORE = ROOT / ".gitignore"

    def read_required(self, path: Path) -> str:
        self.assertTrue(path.is_file(), f"missing Task 4 artifact: {path}")
        return path.read_text(encoding="utf-8")

    def test_model_state_reports_vulkan_and_the_live_judge_snapshot(self) -> None:
        state = json.loads(self.read_required(self.MODEL_STATE))
        self.assertEqual("Qwen3.6-27B", state["base"])
        self.assertEqual("UD-Q4_K_XL", state["quant"])
        self.assertEqual("llama.cpp (Vulkan)", state["runtime"])
        self.assertEqual(24.0, state["vram_total_gb"])
        self.assertNotIn("vram_used_gb", state)
        self.assertNotIn("vram_free_gb", state)
        self.assertEqual(17.9, state["disk_gb"])
        self.assertIsNone(state["vision_model"])
        self.assertIsNone(state["vision_port"])
        self.assertEqual("Qwen3.5-4B-Q4_K_M", state["judge_model"])
        self.assertEqual(8081, state["judge_port"])
        self.assertEqual("2026-07-10", state["_updated"])
        self.assertIn("snapshot", state["_note"].lower())
        self.assertIn("live unit/model endpoint", state["_note"].lower())
        self.assertNotIn("judge retired", state["_note"].lower())
        self.assertNotIn("cuda promoted", state["_note"].lower())

    def test_private_cuda_bench_directory_is_gitignored(self) -> None:
        lines = self.read_required(self.GITIGNORE).splitlines()
        self.assertIn("/local/cuda_migration_bench/", lines)

    def test_runbook_names_every_frozen_phase_and_typed_decision(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        required = (
            "Static preflight",
            "Toolkit and sibling build",
            "Static candidate proof",
            "Offline Vulkan baseline",
            "Offline CUDA candidate",
            "Quality and MTP witness",
            "Exact Vulkan rollback drill",
            "Proposed cutover",
            "Cold-boot witness",
            "Provisional-live witness",
            "Keep Vulkan",
            "keep_vulkan",
            "bench_passed",
            "provisional_cuda_boot",
            "promote_cuda",
        )
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, runbook)

    def test_runbook_has_a_hard_owner_authorization_boundary(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        marker = "OWNER AUTHORIZATION STOP"
        self.assertEqual(1, runbook.count(marker))
        before_stop, after_stop = runbook.split(marker)
        for forbidden_before_authorization in (
            "systemctl",
            "--port 18080",
            "curl ",
            "kill ",
            "pkill ",
        ):
            with self.subTest(token=forbidden_before_authorization):
                self.assertNotIn(forbidden_before_authorization, before_stop)
        self.assertIn("Rohit", after_stop)
        self.assertIn("explicit", after_stop.lower())
        self.assertNotIn("automatic cutover", runbook.lower())

    def test_runbook_uses_only_canonical_runtime_paths(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        required_paths = (
            "/home/rohit/maez/",
            "/home/rohit/llama.cpp-release/source/llama.cpp-b9596/",
            "/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89/",
            "/home/rohit/llama.cpp-release/llama-b9596/llama-b9596/",
            "/home/rohit/.config/systemd/user/llama-server.service",
            "/home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf",
            "/home/rohit/maez/local/cuda_migration_bench/",
        )
        for path in required_paths:
            with self.subTest(path=path):
                self.assertIn(path, runbook)
        for forbidden in (
            "/home/rohit/.config/superpowers/worktrees/",
            "./scripts/",
            "./config/",
            "~/",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, runbook)

    def test_runbook_freezes_bench_and_production_ports_without_collision(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        self.assertIn("BENCH_PORT=18080", runbook)
        self.assertIn("PRODUCTION_PORT=8080", runbook)
        self.assertIn("--port 18080", runbook)
        for forbidden_bench_port in ("--port 8080", "--port 8081", "--port 8082"):
            with self.subTest(port=forbidden_bench_port):
                self.assertNotIn(forbidden_bench_port, runbook)

    def test_runbook_preserves_exact_vulkan_rollback_and_never_removes_mtp(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        for digest in (
            cm.FROZEN_VULKAN_UNIT_SHA256,
            cm.FROZEN_VULKAN_DROPIN_SHA256,
            cm.FROZEN_VULKAN_RUNTIME_SHA256,
            cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
            cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
        ):
            with self.subTest(digest=digest):
                self.assertIn(digest, runbook)
        self.assertIn(
            "rm -- /home/rohit/.config/systemd/user/llama-server.service.d/99-b9596-cuda.conf",
            runbook,
        )
        for forbidden in (
            "rm /home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf",
            "rm -- /home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf",
            "disable mtp.conf",
            "remove mtp.conf",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, runbook.lower())

    def test_runbook_keeps_literals_private_and_freezes_kernel_signatures(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        self.assertIn(
            "install -d -m 0700 /home/rohit/maez/local/cuda_migration_bench/",
            runbook,
        )
        self.assertIn("literal prompts and responses", runbook.lower())
        self.assertIn("corpus/order/artifact hashes", runbook.lower())
        self.assertIn("content-light", runbook.lower())
        for signature in (
            "reusemappingdbMap",
            "pMapCb",
            "mmuWalkMap",
            "NV_ERR_NO_MEMORY",
            "NVRM: Xid",
        ):
            with self.subTest(signature=signature):
                self.assertIn(signature, runbook)

    def test_runbook_scopes_cross_release_repo_to_one_install_invocation(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        for required in (
            "Dir::Etc::sourcelist=/tmp/cuda132-apt-sim/cuda.list",
            "Dir::Etc::sourceparts=-",
            "84c883e0e0c6016a351a60d8329d9091cb7cfea69b716a730ed8390b95d455c5",
            "rm -rf -- /tmp/cuda132-apt-sim/",
            "system_repo_config_count=0",
        ):
            with self.subTest(required=required):
                self.assertIn(required, runbook)
        for forbidden in (
            "add-apt-repository",
            "/etc/apt/sources.list.d/cuda",
            "/etc/apt/preferences.d/cuda",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, runbook)

    def test_runbook_records_and_bounds_the_cuda_alternatives_delta(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        for required in (
            "cuda-toolkit-13-2-config-common.postinst",
            "priority 132",
            "leave auto mode at 13.2",
            "readlink -f /usr/local/cuda",
            "/usr/local/cuda-13.2/bin/nvcc",
        ):
            with self.subTest(required=required):
                self.assertIn(required, runbook)
        self.assertNotIn('NVCC="/usr/local/cuda/bin/nvcc"', runbook)

    def test_runbook_rehearses_installed_pointer_and_preserves_offline_recovery(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        required = (
            "install -d -m 0700 /home/rohit/maez/local/cuda_migration_bench/recovery/",
            "install -m 0600 /home/rohit/.config/systemd/user/llama-server.service /home/rohit/maez/local/cuda_migration_bench/recovery/llama-server.service",
            "install -m 0600 /home/rohit/.config/systemd/user/llama-server.service.d/mtp.conf /home/rohit/maez/local/cuda_migration_bench/recovery/mtp.conf",
            "install -m 0600 /home/rohit/maez/config/systemd/llama-server-b9596-cuda.override.conf /home/rohit/.config/systemd/user/llama-server.service.d/99-b9596-cuda.conf",
            "rm -- /home/rohit/.config/systemd/user/llama-server.service.d/99-b9596-cuda.conf",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, runbook)
        install_at = runbook.index(required[3])
        remove_at = runbook.index(required[4])
        self.assertLess(install_at, remove_at)
        self.assertGreaterEqual(runbook[install_at:remove_at].count("systemctl --user"), 2)
        self.assertGreaterEqual(runbook[remove_at:].count("systemctl --user"), 2)

    def test_static_candidate_proof_forbids_ambient_runtime_execution(self) -> None:
        runbook = self.read_required(self.RUNBOOK)
        static_section = runbook.split("## OWNER AUTHORIZATION STOP", 1)[0]
        self.assertIn(
            "/home/rohit/maez/scripts/build_llama_b9596_cuda.sh",
            static_section,
        )
        self.assertIn("sanitized `env -i`", static_section)
        self.assertIn("never invoke `llama-server --version` directly", static_section)


class CycleBackendWitnessTests(unittest.TestCase):
    def _witness(self) -> cm.RuntimeBackendWitness:
        return cm.RuntimeBackendWitness(
            "vulkan",
            SHA_A,
            "vulkan_baseline",
            "2026-07-13T12:00:05Z",
            cm._packet_hash(str(cm.VULKAN_RELEASE_ROOT)),
        )

    def test_witness_timestamp_must_sit_strictly_inside_interval(self) -> None:
        wrapped = cm.CycleBackendWitness(
            witness=self._witness(),
            cycle=1,
            load_started="2026-07-13T12:00:00Z",
            unload_proven="2026-07-13T12:05:00Z",
        )
        self.assertEqual(1, wrapped.cycle)
        cm._validate_sha256(wrapped.binding_sha256)

        for bad_start, bad_end in (
            ("2026-07-13T12:00:05Z", "2026-07-13T12:05:00Z"),
            ("2026-07-13T12:00:06Z", "2026-07-13T12:05:00Z"),
            ("2026-07-13T12:00:00Z", "2026-07-13T12:00:05Z"),
        ):
            with self.subTest(start=bad_start, end=bad_end):
                with self.assertRaisesRegex(ValueError, "witness_outside_interval"):
                    cm.CycleBackendWitness(
                        witness=self._witness(),
                        cycle=1,
                        load_started=bad_start,
                        unload_proven=bad_end,
                    )

    def test_cycle_must_be_non_bool_1_2_or_3(self) -> None:
        for cycle in (True, 0, 4, 1.0):
            with self.subTest(cycle=cycle):
                with self.assertRaisesRegex(ValueError, "bench_identity_mismatch"):
                    cm.CycleBackendWitness(
                        witness=self._witness(),
                        cycle=cycle,
                        load_started="2026-07-13T12:00:00Z",
                        unload_proven="2026-07-13T12:05:00Z",
                    )


class UtcTimestampContractTests(unittest.TestCase):
    def test_utc_z_timestamp_has_one_canonical_rfc3339_lexical_shape(self) -> None:
        for valid in (
            "2026-07-13T12:00:00Z",
            "2026-07-13T12:00:00.123456Z",
        ):
            with self.subTest(valid=valid):
                cm._validate_utc_z_timestamp(valid)

        for invalid in (
            "2026-07-13 12:00:00Z",
            "2026-W29-1T12:00:00Z",
            "20260713T120000Z",
            "2026-07-13T12:00Z",
            "2026-07-13T12:00:00,5Z",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "invalid_timestamp"):
                    cm._validate_utc_z_timestamp(invalid)


class QualityAndOwnerEvidenceTests(unittest.TestCase):
    def _quality(self, **overrides: object) -> cm.QualityEvidence:
        values: dict[str, object] = {
            "evaluator_version": "grounding_judge.v3",
            "control_manifest_sha256": SHA_A,
            "candidate_manifest_sha256": SHA_B,
            "false_absence_count": 0,
            "wrong_answered_ungrounded_count": 0,
            "type_regression_count": 0,
            "recall_posture": "pass",
            "quality_failure_count": 0,
            "covered_turn_count": 21,
            "timestamp": "2026-07-13T12:00:00Z",
        }
        values.update(overrides)
        return cm.QualityEvidence(**values)

    def _owner(self, **overrides: object) -> cm.OwnerVoiceReview:
        values: dict[str, object] = {
            "producer": "owner_human",
            "status": "pass",
            "evaluator_version": "owner_voice.v1",
            "control_manifest_sha256": SHA_A,
            "candidate_manifest_sha256": SHA_B,
            "artifact_sha256": SHA_C,
            "timestamp": "2026-07-13T12:00:00Z",
        }
        values.update(overrides)
        return cm.OwnerVoiceReview(**values)

    def test_quality_covered_turn_count_must_be_non_bool_21(self) -> None:
        for count in (20, True, 21.0):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "quality_coverage"):
                    self._quality(covered_turn_count=count)

    def test_quality_counts_reject_booleans(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_false_absence_count"):
            self._quality(false_absence_count=True)

    def test_quality_and_owner_documents_bind_every_field(self) -> None:
        quality = self._quality()
        owner = self._owner()
        cm._validate_sha256(quality.binding_sha256)
        cm._validate_sha256(owner.binding_sha256)
        self.assertNotEqual(
            quality.binding_sha256,
            replace(quality, evaluator_version="grounding_judge.v4").binding_sha256,
        )
        self.assertNotEqual(
            owner.binding_sha256,
            replace(owner, evaluator_version="owner_voice.v2").binding_sha256,
        )

    def test_owner_document_has_closed_producer_status_and_evaluator(self) -> None:
        cases = (
            ({"producer": "model"}, "owner_voice_producer"),
            ({"status": ["pass"]}, "phase_evidence"),
            ({"evaluator_version": ""}, "owner_voice_evaluator_version"),
        )
        for changes, reason in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, reason):
                    self._owner(**changes)


class ConsumptionAndAuthorizationDocTests(unittest.TestCase):
    def _window(self, **overrides: object) -> cm.WindowAuthorizationDoc:
        values: dict[str, object] = {
            "window_id": "window-1",
            "phases": ("vulkan_baseline", "cuda_candidate"),
            "boot_id": "boot-1",
            "nonce": "a" * 64,
            "issued_at": "2026-07-13T12:00:00Z",
            "expires_at": "2026-07-13T16:00:00Z",
            "owner": "rohit",
        }
        values.update(overrides)
        return cm.WindowAuthorizationDoc(**values)

    def _continuation(self, **overrides: object) -> cm.ContinuationDoc:
        values: dict[str, object] = {
            "window_id": "window-1",
            "phases": ("cuda_candidate",),
            "boot_id": "boot-1",
            "nonce": "b" * 64,
            "issued_at": "2026-07-13T13:00:00Z",
            "expires_at": "2026-07-13T14:00:00Z",
            "owner": "rohit",
            "parent_vulkan_packet_sha256": SHA_A,
        }
        values.update(overrides)
        return cm.ContinuationDoc(**values)

    def test_consumption_receipt_validates_and_binds(self) -> None:
        receipt = cm.ConsumptionReceipt(
            "a" * 64,
            "vulkan_baseline",
            "boot-1",
            "2026-07-13T12:00:00Z",
        )
        cm._validate_sha256(receipt.binding_sha256)
        for changes, reason in (
            ({"nonce": "ABC"}, "nonce_syntax"),
            ({"nonce": ["a" * 64]}, "nonce_syntax"),
            ({"phase": ["vulkan_baseline"]}, "closed_phase"),
            ({"boot_id": ""}, "boot_id_required"),
            ({"timestamp": "2026-07-13T12:00:00+00:00"}, "invalid_timestamp"),
        ):
            values: dict[str, object] = {
                "nonce": "a" * 64,
                "phase": "vulkan_baseline",
                "boot_id": "boot-1",
                "timestamp": "2026-07-13T12:00:00Z",
            }
            values.update(changes)
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, reason):
                    cm.ConsumptionReceipt(**values)

    def test_window_and_continuation_bind_recomputable_preimages(self) -> None:
        window = self._window()
        continuation = self._continuation()
        cm._validate_sha256(window.preimage_sha256)
        cm._validate_sha256(continuation.preimage_sha256)
        self.assertNotEqual(window.preimage_sha256, continuation.preimage_sha256)

    def test_authorization_ttls_are_exact(self) -> None:
        with self.assertRaisesRegex(ValueError, "authorization_ttl"):
            self._window(expires_at="2026-07-13T15:59:59Z")
        with self.assertRaisesRegex(ValueError, "authorization_ttl"):
            self._continuation(expires_at="2026-07-13T15:00:00Z")

    def test_authorization_ttl_preserves_arbitrary_rfc3339_fraction_precision(self) -> None:
        exact = self._window(
            issued_at="2026-07-13T12:00:00.0000001Z",
            expires_at="2026-07-13T16:00:00.0000001Z",
        )
        cm._validate_sha256(exact.preimage_sha256)

        with self.assertRaisesRegex(ValueError, "authorization_ttl"):
            self._window(
                issued_at="2026-07-13T12:00:00.0000001Z",
                expires_at="2026-07-13T16:00:00.0000002Z",
            )

    def test_authorization_phases_must_be_immutable_and_closed(self) -> None:
        for make, phases, reason in (
            (self._window, ["vulkan_baseline"], "immutable_sequence_required"),
            (self._continuation, ["cuda_candidate"], "immutable_sequence_required"),
            (self._window, (["vulkan_baseline"],), "closed_phase"),
            (self._window, ("unknown",), "closed_phase"),
        ):
            with self.subTest(phases=phases):
                with self.assertRaisesRegex(ValueError, reason):
                    make(phases=phases)

    def test_authorization_regex_fields_are_type_checked_first(self) -> None:
        for changes, reason in (
            ({"window_id": ["window-1"]}, "window_id_syntax"),
            ({"nonce": ["a" * 64]}, "nonce_syntax"),
            ({"boot_id": []}, "boot_id_required"),
            ({"owner": []}, "authorization_owner"),
            ({"issued_at": "2026-07-13T12:00:00+00:00"}, "invalid_timestamp"),
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, reason):
                    self._window(**changes)


class StaticPreflightDocTests(unittest.TestCase):
    @staticmethod
    def checks() -> dict[str, str]:
        return {
            "corpus": cm.FROZEN_CORPUS_SHA256,
            "incumbent_unit": cm.FROZEN_VULKAN_UNIT_SHA256,
            "incumbent_dropin": cm.FROZEN_VULKAN_DROPIN_SHA256,
            "incumbent_server": cm.FROZEN_VULKAN_RUNTIME_SHA256,
            "model": cm.FROZEN_MODEL_SHA256,
            "library_manifest": cm.FROZEN_VULKAN_LIBRARY_MANIFEST_SHA256,
            "effective_args": cm.FROZEN_VULKAN_EFFECTIVE_ARGS_SHA256,
            "flag_source": SHA_A,
            "vision_unit": SHA_B,
            "candidate_manifest": SHA_C,
            "bench_root_mode": "700",
            "stub_pin": SHA_D,
        }

    def make_doc(self, **overrides: object) -> cm.StaticPreflightDoc:
        values: dict[str, object] = {
            "gpu_uuid": "GPU-12345678-1234-1234-1234-123456789abc",
            "driver_package_sha256": SHA_E,
            "stub_sha256": SHA_D,
            "corpus_verified": True,
            "checks": self.checks(),
            "timestamp": "2026-07-13T12:00:00Z",
        }
        values.update(overrides)
        return cm.StaticPreflightDoc(**values)

    def test_valid_document_binds_and_freezes_checks(self) -> None:
        source = self.checks()
        doc = self.make_doc(checks=source)
        cm._validate_sha256(doc.binding_sha256)
        source["flag_source"] = SHA_E
        self.assertEqual(SHA_A, doc.checks["flag_source"])
        with self.assertRaises(TypeError):
            doc.checks["flag_source"] = SHA_E

    def test_all_seven_frozen_checks_require_exact_values(self) -> None:
        for name in (
            "corpus",
            "incumbent_unit",
            "incumbent_dropin",
            "incumbent_server",
            "model",
            "library_manifest",
            "effective_args",
        ):
            checks = self.checks()
            checks[name] = SHA_E
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "static_preflight_invalid"):
                    self.make_doc(checks=checks)

    def test_shape_clearance_and_dynamic_hashes_fail_closed(self) -> None:
        missing = self.checks()
        del missing["vision_unit"]
        cases = (
            ({"checks": missing}, "missing key"),
            ({"corpus_verified": False}, "corpus false"),
            ({"gpu_uuid": "GPU-" + "a" * 36}, "bad gpu shape"),
            ({"timestamp": "2026-07-13T12:00:00+00:00"}, "non-Z timestamp"),
        )
        for changes, label in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(
                    ValueError,
                    "(?:static_preflight_invalid|invalid_timestamp)",
                ):
                    self.make_doc(**changes)

        for name in ("flag_source", "vision_unit", "candidate_manifest"):
            checks = self.checks()
            checks[name] = ""
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "static_preflight_invalid"):
                    self.make_doc(checks=checks)


class PersistedDocTests(unittest.TestCase):
    @staticmethod
    def wrapper(
        schema: str,
        obj: object,
        fields: dict[str, object],
        *,
        binding: str | None = None,
    ) -> bytes:
        document = {
            "schema": schema,
            "binding_sha256": binding or obj.binding_sha256,
            "fields": fields,
        }
        return (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            + b"\n"
        )

    @staticmethod
    def identity_fields(identity: cm.RuntimeIdentity) -> dict[str, object]:
        return {
            "tag": identity.tag,
            "commit": identity.commit,
            "version": identity.version,
            "alias": identity.alias,
            "model_sha256": identity.model_sha256,
            "model_bytes": identity.model_bytes,
            "runtime_sha256": identity.runtime_sha256,
            "library_hashes": dict(identity.library_hashes),
            "effective_args": list(identity.effective_args),
            "mode": identity.mode,
            "production_override_sha256": identity.production_override_sha256,
            "backend_environment": dict(identity.backend_environment),
            "runtime_manifest_sha256": identity.runtime_manifest_sha256,
            "rollback_manifest_sha256": identity.rollback_manifest_sha256,
            "cuda_toolkit": identity.cuda_toolkit,
            "cuda_compiler": identity.cuda_compiler,
            "cmake_version": identity.cmake_version,
            "driver_version": identity.driver_version,
            "gpu_identifier": identity.gpu_identifier,
            "compute_capability": identity.compute_capability,
            "backend": identity.backend,
        }

    @staticmethod
    def containment_fields(snapshot: cm.ContainmentSnapshot) -> dict[str, object]:
        return {
            "phase": snapshot.phase,
            "boundary": snapshot.boundary,
            "timestamp": snapshot.timestamp,
            "screen_flag_value": snapshot.screen_flag_value,
            "active_state": snapshot.active_state,
            "substate": snapshot.substate,
            "enabled_state": snapshot.enabled_state,
            "port_closed": snapshot.port_closed,
            "flag_source_sha256": snapshot.flag_source_sha256,
            "vision_unit_sha256": snapshot.vision_unit_sha256,
            "artifact_sha256": snapshot.artifact_sha256,
        }

    @staticmethod
    def cold_witness() -> cm.ColdBootWitness:
        return cm.ColdBootWitness(
            parent_sha256=SHA_A,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:02:00Z",
            topology_sha256=SHA_C,
            load_intervals=(
                cm.LoadInterval(
                    "primary",
                    "2026-07-10T12:01:10Z",
                    "2026-07-10T12:01:20Z",
                ),
                cm.LoadInterval(
                    "judge",
                    "2026-07-10T12:01:21Z",
                    "2026-07-10T12:01:30Z",
                ),
            ),
            steady_bar1_percent=80.0,
            kernel_counters=cm.KernelCounters.zero(),
            restart_count=0,
            containment_artifact_sha256=SHA_D,
            runtime_sha256=SHA_A,
            runtime_maps_sha256=SHA_B,
            backend="cuda",
            production_override_sha256=SHA_C,
            alias=cm.FROZEN_ALIAS,
            model_sha256=cm.FROZEN_MODEL_SHA256,
            model_bytes=cm.FROZEN_MODEL_BYTES,
            service_health="healthy",
            mtp_initialized=True,
            mtp_accepted_tokens=7,
        )

    @staticmethod
    def cold_fields(witness: cm.ColdBootWitness) -> dict[str, object]:
        return {
            "parent_sha256": witness.parent_sha256,
            "artifact_sha256": witness.artifact_sha256,
            "timestamp": witness.timestamp,
            "topology_sha256": witness.topology_sha256,
            "load_intervals": [
                {
                    "component": item.component,
                    "started_at": item.started_at,
                    "ended_at": item.ended_at,
                }
                for item in witness.load_intervals
            ],
            "steady_bar1_percent": witness.steady_bar1_percent,
            "kernel_counters": {
                "reusemappingdb_map": witness.kernel_counters.reusemappingdb_map,
                "pmap_cb": witness.kernel_counters.pmap_cb,
                "mmu_walk_map": witness.kernel_counters.mmu_walk_map,
                "nv_err_no_memory": witness.kernel_counters.nv_err_no_memory,
                "xid": witness.kernel_counters.xid,
                "unmatched_nvrm": witness.kernel_counters.unmatched_nvrm,
            },
            "restart_count": witness.restart_count,
            "containment_artifact_sha256": witness.containment_artifact_sha256,
            "runtime_sha256": witness.runtime_sha256,
            "runtime_maps_sha256": witness.runtime_maps_sha256,
            "backend": witness.backend,
            "production_override_sha256": witness.production_override_sha256,
            "alias": witness.alias,
            "model_sha256": witness.model_sha256,
            "model_bytes": witness.model_bytes,
            "service_health": witness.service_health,
            "mtp_initialized": witness.mtp_initialized,
            "mtp_accepted_tokens": witness.mtp_accepted_tokens,
        }

    @staticmethod
    def live_fields(witness: cm.ProvisionalLiveWitness) -> dict[str, object]:
        return {
            "parent_sha256": witness.parent_sha256,
            "artifact_sha256": witness.artifact_sha256,
            "timestamp": witness.timestamp,
            "containment_artifact_sha256": witness.containment_artifact_sha256,
            "turns": [turn.packet() for turn in witness.turns],
            "runtime_sha256": witness.runtime_sha256,
            "runtime_maps_sha256": witness.runtime_maps_sha256,
            "backend": witness.backend,
            "configuration_sha256": witness.configuration_sha256,
            "corpus_sha256": witness.corpus_sha256,
            "order_sha256": witness.order_sha256,
        }

    def test_runtime_identity_round_trip_restores_tuple_and_frozen_mappings(self) -> None:
        identity = make_identity()
        persisted = cm.PersistedDoc(
            self.wrapper(
                cm.RUNTIME_IDENTITY_SCHEMA,
                identity,
                self.identity_fields(identity),
            )
        )
        self.assertIsInstance(persisted.obj, cm.RuntimeIdentity)
        self.assertIsInstance(persisted.obj.effective_args, tuple)
        self.assertEqual(identity.binding_sha256, persisted.obj.binding_sha256)
        cm._validate_sha256(persisted.file_sha256)
        with self.assertRaises(TypeError):
            persisted.obj.library_hashes["libggml-cuda.so"] = SHA_A

    def test_containment_static_cold_and_live_families_round_trip(self) -> None:
        snapshot = containment_snapshot("cuda_candidate", "before")
        static = StaticPreflightDocTests().make_doc()
        cold = self.cold_witness()
        live = cm.ProvisionalLiveWitness(
            parent_sha256=SHA_A,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:04:00Z",
            containment_artifact_sha256=SHA_C,
            turns=live_turns(),
            runtime_sha256=SHA_D,
            runtime_maps_sha256=SHA_E,
            backend="cuda",
            configuration_sha256=SHA_A,
            corpus_sha256=CORPUS_SHA,
            order_sha256=ORDER_SHA,
        )
        static_fields = {
            "gpu_uuid": static.gpu_uuid,
            "driver_package_sha256": static.driver_package_sha256,
            "stub_sha256": static.stub_sha256,
            "corpus_verified": static.corpus_verified,
            "checks": dict(static.checks),
            "timestamp": static.timestamp,
        }
        cases = (
            (
                cm.CONTAINMENT_SNAPSHOT_SCHEMA,
                snapshot,
                self.containment_fields(snapshot),
                cm.ContainmentSnapshot,
            ),
            (cm.STATIC_PREFLIGHT_SCHEMA, static, static_fields, cm.StaticPreflightDoc),
            (cm.COLD_BOOT_WITNESS_SCHEMA, cold, self.cold_fields(cold), cm.ColdBootWitness),
            (
                cm.PROVISIONAL_LIVE_WITNESS_SCHEMA,
                live,
                self.live_fields(live),
                cm.ProvisionalLiveWitness,
            ),
        )
        for schema, obj, fields, expected_type in cases:
            with self.subTest(schema=schema):
                rebuilt = cm.PersistedDoc(self.wrapper(schema, obj, fields)).obj
                self.assertIsInstance(rebuilt, expected_type)
                self.assertEqual(obj.binding_sha256, rebuilt.binding_sha256)

    def test_inv3_authorization_and_backend_map_wrappers_round_trip(self) -> None:
        authorization = cm.AuthorizationWitness(
            "boot_authorization",
            "pass",
            SHA_A,
            SHA_B,
            "2026-07-13T12:00:00Z",
        )
        maps = backend("cold_boot")
        authorization_fields = {
            "phase": authorization.phase,
            "status": authorization.status,
            "artifact_sha256": authorization.artifact_sha256,
            "parent_sha256": authorization.parent_sha256,
            "timestamp": authorization.timestamp,
        }
        maps_fields = {
            "backend": maps.backend,
            "maps_sha256": maps.maps_sha256,
            "phase": maps.phase,
            "timestamp": maps.timestamp,
            "release_root_sha256": maps.release_root_sha256,
        }
        cases = (
            (
                cm.AUTHORIZATION_WITNESS_SCHEMA,
                authorization,
                authorization_fields,
                cm.AuthorizationWitness,
            ),
            (
                cm.BACKEND_MAP_WITNESS_SCHEMA,
                maps,
                maps_fields,
                cm.RuntimeBackendWitness,
            ),
        )
        for schema, obj, fields, expected_type in cases:
            with self.subTest(schema=schema):
                rebuilt = cm.PersistedDoc(self.wrapper(schema, obj, fields)).obj
                self.assertIsInstance(rebuilt, expected_type)
                self.assertEqual(obj.binding_sha256, rebuilt.binding_sha256)

    def test_live_turn_ordinal_rejects_bool_and_float_impostors(self) -> None:
        turn = live_turns()[0]
        for ordinal in (True, 1.0):
            values = turn.packet()
            values["ordinal"] = ordinal
            with self.subTest(ordinal=ordinal):
                with self.assertRaisesRegex(ValueError, "live_turn_order"):
                    cm.LiveTurnWitness(**values)

    def test_persisted_live_ordinal_impostors_refuse_round_trip(self) -> None:
        live = cm.ProvisionalLiveWitness(
            parent_sha256=SHA_A,
            artifact_sha256=SHA_B,
            timestamp="2026-07-10T12:04:00Z",
            containment_artifact_sha256=SHA_C,
            turns=live_turns(),
            runtime_sha256=SHA_D,
            runtime_maps_sha256=SHA_E,
            backend="cuda",
            configuration_sha256=SHA_A,
            corpus_sha256=CORPUS_SHA,
            order_sha256=ORDER_SHA,
        )
        for ordinal in (True, 1.0):
            fields = self.live_fields(live)
            fields["turns"][0]["ordinal"] = ordinal
            forged_binding = cm._packet_hash(fields)
            with self.subTest(ordinal=ordinal):
                with self.assertRaisesRegex(ValueError, "persisted_roundtrip"):
                    cm.PersistedDoc(
                        self.wrapper(
                            cm.PROVISIONAL_LIVE_WITNESS_SCHEMA,
                            live,
                            fields,
                            binding=forged_binding,
                        )
                    )

    def test_persisted_registry_is_immutable(self) -> None:
        with self.assertRaises(TypeError):
            cm._PERSISTED_REGISTRY["forged.v1"] = lambda fields: fields

    def test_tampered_fields_and_embedded_binding_fail_round_trip(self) -> None:
        snapshot = containment_snapshot("cuda_candidate", "before")
        fields = self.containment_fields(snapshot)
        fields["artifact_sha256"] = SHA_B
        with self.assertRaisesRegex(ValueError, "persisted_roundtrip"):
            cm.PersistedDoc(
                self.wrapper(cm.CONTAINMENT_SNAPSHOT_SCHEMA, snapshot, fields)
            )
        with self.assertRaisesRegex(ValueError, "persisted_roundtrip"):
            cm.PersistedDoc(
                self.wrapper(
                    cm.CONTAINMENT_SNAPSHOT_SCHEMA,
                    snapshot,
                    self.containment_fields(snapshot),
                    binding=SHA_E,
                )
            )

    def test_noncanonical_and_unknown_wrappers_refuse_typed(self) -> None:
        snapshot = containment_snapshot("cuda_candidate", "before")
        canonical = self.wrapper(
            cm.CONTAINMENT_SNAPSHOT_SCHEMA,
            snapshot,
            self.containment_fields(snapshot),
        )
        with self.assertRaisesRegex(ValueError, "noncanonical_wrapper"):
            cm.PersistedDoc(canonical[:-1] + b" \n")

        unknown = self.wrapper(
            "unknown.v1",
            snapshot,
            self.containment_fields(snapshot),
        )
        with self.assertRaisesRegex(ValueError, "persisted_schema_unknown"):
            cm.PersistedDoc(unknown)

    def test_wrapper_bytes_pin_newline_and_utf8_canon(self) -> None:
        snapshot = containment_snapshot("cuda_candidate", "before")
        canonical = self.wrapper(
            cm.CONTAINMENT_SNAPSHOT_SCHEMA,
            snapshot,
            self.containment_fields(snapshot),
        )
        for malformed in (
            canonical[:-1],
            canonical + b"\n",
            canonical[:-1] + b"\r\n",
        ):
            with self.subTest(malformed=malformed[-2:]):
                with self.assertRaisesRegex(ValueError, "noncanonical_wrapper"):
                    cm.PersistedDoc(malformed)

        unicode_snapshot = containment_snapshot(
            "cuda_candidate",
            "before",
            active_state="inactivé",
        )
        encoded = self.wrapper(
            cm.CONTAINMENT_SNAPSHOT_SCHEMA,
            unicode_snapshot,
            self.containment_fields(unicode_snapshot),
        )
        persisted = cm.PersistedDoc(encoded)
        self.assertEqual("inactivé", persisted.obj.active_state)
        self.assertIn("inactivé".encode(), encoded)
        self.assertNotIn(b"inactiv\\u00e9", encoded)
        self.assertTrue(encoded.endswith(b"\n"))


def _turn_manifest(phase: str = "vulkan_baseline") -> cm.TurnManifest:
    entries = []
    for cycle in (1, 2, 3):
        entries.append(cm.TurnManifestEntry(cycle, 0, True, SHA_A))
        for ordinal in range(1, 8):
            entries.append(cm.TurnManifestEntry(cycle, ordinal, False, SHA_B))
    return cm.TurnManifest(phase=phase, entries=tuple(entries))


def _turn_records() -> tuple[cm.TurnRecord, ...]:
    records = []
    for cycle in (1, 2, 3):
        records.append(
            cm.TurnRecord(
                cycle=cycle,
                ordinal=0,
                warmup=True,
                artifact_sha256=SHA_A,
                outcome="completed",
                e2e_ms=99_999.0,
                ttft_ms=99_999.0,
                prompt_per_second=1.0,
                predicted_per_second=1.0,
                draft_n=None,
                draft_n_accepted=None,
            )
        )
        for ordinal in range(1, 8):
            sample = (cycle - 1) * 7 + ordinal
            records.append(
                cm.TurnRecord(
                    cycle=cycle,
                    ordinal=ordinal,
                    warmup=False,
                    artifact_sha256=SHA_B,
                    outcome="completed",
                    e2e_ms=float(sample),
                    ttft_ms=100.0 + sample,
                    prompt_per_second=200.0 + sample,
                    predicted_per_second=100.0 + sample,
                    draft_n=10,
                    draft_n_accepted=7,
                )
            )
    return tuple(records)


def _phase_cycle_metrics() -> tuple[cm.CycleMetrics, ...]:
    return tuple(
        cm.CycleMetrics(
            cycle=cycle,
            topology_sha256=SHA_C,
            bar1_before_percent=10.0,
            bar1_after_load_percent=70.0 + cycle,
            bar1_after_inference_percent=75.0 + cycle,
            bar1_after_unload_percent=10.0,
            vram_before_mib=100,
            vram_after_load_mib=20_000 + cycle,
            vram_after_inference_mib=21_000 + cycle,
            vram_after_unload_mib=100,
        )
        for cycle in (1, 2, 3)
    )


def _cycle_backend_witnesses(
    phase: str = "vulkan_baseline",
) -> tuple[cm.CycleBackendWitness, ...]:
    backend_name = "vulkan" if phase == "vulkan_baseline" else "cuda"
    release_root = cm.VULKAN_RELEASE_ROOT if backend_name == "vulkan" else cm.CUDA_RELEASE_ROOT
    return tuple(
        cm.CycleBackendWitness(
            witness=cm.RuntimeBackendWitness(
                backend=backend_name,
                maps_sha256=f"{cycle}" * 64,
                phase=phase,
                timestamp=f"2026-07-13T12:0{cycle}:10Z",
                release_root_sha256=cm._packet_hash(str(release_root)),
            ),
            cycle=cycle,
            load_started=f"2026-07-13T12:0{cycle}:00Z",
            unload_proven=f"2026-07-13T12:0{cycle}:20Z",
        )
        for cycle in (1, 2, 3)
    )


def _projection_json(
    phase: str,
    records: tuple[cm.TurnRecord, ...],
    metrics: tuple[cm.CycleMetrics, ...],
) -> str:
    statistics = cm.recompute_phase_statistics(records)
    unload_leak = sum(
        max(0, cycle.vram_after_unload_mib - cycle.vram_before_mib)
        for cycle in metrics
    )
    summary = make_summary(
        phase,
        cycles=metrics,
        seven_turn_max_ms=statistics["seven_turn_max_ms"],
        p95_e2e_ms=statistics["p95_e2e_ms"],
        median_decode_tps=statistics["median_decode_tps"],
        median_prefill_tps=statistics["median_prefill_tps"],
        mtp_drafted_tokens=statistics["mtp_drafted_tokens"],
        mtp_accepted_tokens=statistics["mtp_accepted_tokens"],
        mtp_rejected_tokens=statistics["mtp_rejected_tokens"],
        mtp_initialized=statistics["mtp_initialized"],
        crash_count=statistics["crash_count"],
        restart_count=statistics["restart_count"],
        hang_count=statistics["hang_count"],
        timeout_count=statistics["timeout_count"],
        unload_leak_mib=float(unload_leak),
        kernel_counters=cm.KernelCounters.zero(),
    )
    return json.dumps(
        cm.phase_summary_projection(summary),
        sort_keys=True,
        separators=(",", ":"),
    )


def _phase_packet(phase: str = "vulkan_baseline") -> cm.PhasePacket:
    records = _turn_records()
    metrics = _phase_cycle_metrics()
    return cm.PhasePacket(
        phase=phase,
        outcome="completed",
        window_id="window-1",
        boot_id="boot-1",
        gpu_uuid="GPU-12345678-1234-1234-1234-123456789abc",
        topology_sha256=SHA_C,
        model_sha256=MODEL_SHA,
        corpus_sha256=CORPUS_SHA,
        order_sha256=ORDER_SHA,
        effective_args_sha256=SHA_D,
        driver_package_sha256=SHA_E,
        authorization_preimage_sha256=SHA_A,
        consumption_receipt_sha256=SHA_B,
        static_preflight_sha256=SHA_C,
        runtime_identity_sha256=SHA_D,
        turn_manifest=_turn_manifest(phase),
        turn_records=records,
        cycle_metrics=metrics,
        cycle_witnesses=_cycle_backend_witnesses(phase),
        containment_before_sha256=SHA_A,
        containment_after_sha256=SHA_B,
        kernel_cursor_before="cursor-a",
        kernel_cursor_after="cursor-b",
        kernel_counters=cm.KernelCounters.zero(),
        summary_projection_json=_projection_json(phase, records, metrics),
        cycle_one_before_snapshot_at="2026-07-13T12:00:00Z",
        timestamp="2026-07-13T12:10:00Z",
    )


def _phase_packet_fields(packet: cm.PhasePacket) -> dict[str, object]:
    return {
        "phase": packet.phase,
        "outcome": packet.outcome,
        "window_id": packet.window_id,
        "boot_id": packet.boot_id,
        "gpu_uuid": packet.gpu_uuid,
        "topology_sha256": packet.topology_sha256,
        "model_sha256": packet.model_sha256,
        "corpus_sha256": packet.corpus_sha256,
        "order_sha256": packet.order_sha256,
        "effective_args_sha256": packet.effective_args_sha256,
        "driver_package_sha256": packet.driver_package_sha256,
        "authorization_preimage_sha256": packet.authorization_preimage_sha256,
        "consumption_receipt_sha256": packet.consumption_receipt_sha256,
        "static_preflight_sha256": packet.static_preflight_sha256,
        "runtime_identity_sha256": packet.runtime_identity_sha256,
        "turn_manifest": {
            "phase": packet.turn_manifest.phase,
            "entries": [
                [entry.cycle, entry.ordinal, entry.warmup, entry.artifact_sha256]
                for entry in packet.turn_manifest.entries
            ],
        },
        "turn_records": [
            {
                "cycle": record.cycle,
                "ordinal": record.ordinal,
                "warmup": record.warmup,
                "artifact_sha256": record.artifact_sha256,
                "outcome": record.outcome,
                "e2e_ms": record.e2e_ms,
                "ttft_ms": record.ttft_ms,
                "prompt_per_second": record.prompt_per_second,
                "predicted_per_second": record.predicted_per_second,
                "draft_n": record.draft_n,
                "draft_n_accepted": record.draft_n_accepted,
            }
            for record in packet.turn_records
        ],
        "cycle_metrics": [cm._cycle_packet(metric) for metric in packet.cycle_metrics],
        "cycle_witnesses": [
            {
                "witness": {
                    "backend": item.witness.backend,
                    "maps_sha256": item.witness.maps_sha256,
                    "phase": item.witness.phase,
                    "timestamp": item.witness.timestamp,
                    "release_root_sha256": item.witness.release_root_sha256,
                },
                "cycle": item.cycle,
                "load_started": item.load_started,
                "unload_proven": item.unload_proven,
            }
            for item in packet.cycle_witnesses
        ],
        "containment_before_sha256": packet.containment_before_sha256,
        "containment_after_sha256": packet.containment_after_sha256,
        "kernel_cursor_before": packet.kernel_cursor_before,
        "kernel_cursor_after": packet.kernel_cursor_after,
        "kernel_counters": {
            "reusemappingdb_map": packet.kernel_counters.reusemappingdb_map,
            "pmap_cb": packet.kernel_counters.pmap_cb,
            "mmu_walk_map": packet.kernel_counters.mmu_walk_map,
            "nv_err_no_memory": packet.kernel_counters.nv_err_no_memory,
            "xid": packet.kernel_counters.xid,
            "unmatched_nvrm": packet.kernel_counters.unmatched_nvrm,
        },
        "summary_projection_json": packet.summary_projection_json,
        "cycle_one_before_snapshot_at": packet.cycle_one_before_snapshot_at,
        "timestamp": packet.timestamp,
    }


class TurnManifestTests(unittest.TestCase):
    def test_valid_manifest_has_24_entries_and_binds(self) -> None:
        manifest = _turn_manifest()
        self.assertEqual(24, len(manifest.entries))
        cm._validate_sha256(manifest.binding_sha256)

    def test_missing_measured_turn_is_rejected(self) -> None:
        entries = list(_turn_manifest().entries)[:-1]
        with self.assertRaisesRegex(ValueError, "manifest_shape"):
            cm.TurnManifest(phase="vulkan_baseline", entries=tuple(entries))

    def test_warmup_flag_must_match_ordinal_zero(self) -> None:
        entries = list(_turn_manifest().entries)
        entries[0] = cm.TurnManifestEntry(1, 0, False, SHA_A)
        with self.assertRaisesRegex(ValueError, "manifest_shape"):
            cm.TurnManifest(phase="vulkan_baseline", entries=tuple(entries))

    def test_manifest_requires_tuple_exact_order_and_typed_entries(self) -> None:
        manifest = _turn_manifest()
        for entries in (
            list(manifest.entries),
            (manifest.entries[1], manifest.entries[0], *manifest.entries[2:]),
            ("not-an-entry", *manifest.entries[1:]),
        ):
            with self.subTest(kind=type(entries).__name__):
                with self.assertRaisesRegex(ValueError, "manifest_shape"):
                    cm.TurnManifest(phase="vulkan_baseline", entries=entries)

    def test_entry_cycle_ordinal_and_warmup_types_are_exact(self) -> None:
        for values in (
            (True, 0, True),
            (1.0, 0, True),
            (1, True, True),
            (1, 0.0, True),
            (1, 0, 1),
        ):
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, "manifest_shape"):
                    cm.TurnManifestEntry(*values, SHA_A)

    def test_manifest_phase_refuses_non_string_without_type_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "closed_phase"):
            cm.TurnManifest(phase=["vulkan_baseline"], entries=_turn_manifest().entries)


class TurnRecordTests(unittest.TestCase):
    def test_unknown_outcome_is_rejected_by_closed_vocabulary(self) -> None:
        for outcome in ("weird_outcome", ["completed"]):
            with self.subTest(outcome=outcome):
                with self.assertRaisesRegex(ValueError, "turn_outcome_closed"):
                    replace(_turn_records()[1], outcome=outcome)

    def test_warmup_discards_mtp_and_measured_requires_typed_counters(self) -> None:
        with self.assertRaisesRegex(ValueError, "mtp_unproven"):
            replace(_turn_records()[0], draft_n=1, draft_n_accepted=1)
        for drafted, accepted in (
            (None, None),
            (1, None),
            (None, 1),
            (True, 1),
            (1, 2),
            (1.0, 1),
        ):
            with self.subTest(drafted=drafted, accepted=accepted):
                with self.assertRaisesRegex(ValueError, "mtp_unproven"):
                    replace(
                        _turn_records()[1],
                        draft_n=drafted,
                        draft_n_accepted=accepted,
                    )

    def test_measurements_are_nonnegative_finite_floats(self) -> None:
        for field, value in (
            ("e2e_ms", -1.0),
            ("ttft_ms", float("nan")),
            ("prompt_per_second", True),
            ("predicted_per_second", 1),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, "turn_measurement"):
                    replace(_turn_records()[1], **{field: value})

    def test_record_shape_ties_warmup_to_ordinal(self) -> None:
        for changes in (
            {"cycle": True},
            {"ordinal": 1.0},
            {"warmup": 1},
            {"warmup": True},
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, "turn_record_shape"):
                    replace(_turn_records()[1], **changes)

    def test_ttft_is_hash_bound_even_though_not_an_aggregate(self) -> None:
        record = _turn_records()[1]
        changed = replace(record, ttft_ms=record.ttft_ms + 1.0)
        self.assertNotEqual(record.binding_sha256, changed.binding_sha256)

    def test_mtp_integer_must_be_json_serializable(self) -> None:
        with self.assertRaisesRegex(ValueError, "mtp_unproven"):
            replace(
                _turn_records()[1],
                draft_n=10**5_000,
                draft_n_accepted=1,
            )


class PhaseStatisticsTests(unittest.TestCase):
    def test_frozen_statistics_use_only_the_21_measured_rows(self) -> None:
        statistics = cm.recompute_phase_statistics(_turn_records())
        self.assertEqual(20.0, statistics["p95_e2e_ms"])
        self.assertEqual(21.0, statistics["seven_turn_max_ms"])
        self.assertEqual(211.0, statistics["median_prefill_tps"])
        self.assertEqual(111.0, statistics["median_decode_tps"])
        self.assertEqual(210, statistics["mtp_drafted_tokens"])
        self.assertEqual(147, statistics["mtp_accepted_tokens"])
        self.assertEqual(63, statistics["mtp_rejected_tokens"])
        self.assertTrue(statistics["mtp_initialized"])
        self.assertEqual(0, statistics["restart_count"])

    def test_mtp_totals_are_seven_per_cycle_then_three_cycle_sums(self) -> None:
        records = _turn_records()
        for cycle in (1, 2, 3):
            measured = [
                record for record in records if record.cycle == cycle and not record.warmup
            ]
            self.assertEqual(7, len(measured))
            self.assertEqual(70, sum(record.draft_n for record in measured))
            self.assertEqual(49, sum(record.draft_n_accepted for record in measured))
        statistics = cm.recompute_phase_statistics(records)
        self.assertEqual(
            statistics["mtp_drafted_tokens"] - statistics["mtp_accepted_tokens"],
            statistics["mtp_rejected_tokens"],
        )

    def test_phase_projection_has_exact_phase_produced_fields(self) -> None:
        packet = _phase_packet()
        projection = json.loads(packet.summary_projection_json)
        self.assertEqual(
            {
                "phase",
                "alias",
                "model_sha256",
                "corpus_sha256",
                "order_sha256",
                "sample_n",
                "warmup_count",
                "measured_sample_count",
                "load_cycles",
                "seven_turn_max_ms",
                "p95_e2e_ms",
                "median_decode_tps",
                "median_prefill_tps",
                "cycles",
                "mtp_drafted_tokens",
                "mtp_accepted_tokens",
                "mtp_rejected_tokens",
                "mtp_initialized",
                "crash_count",
                "restart_count",
                "hang_count",
                "timeout_count",
                "unload_leak_mib",
                "kernel_counters",
            },
            set(projection),
        )
        for forbidden in (
            "quality_failure_count",
            "recall_posture",
            "owner_voice_evidence_sha256",
            "rollback_witness_sha256",
            "cold_boot_witness_sha256",
            "provisional_live_witness_sha256",
        ):
            self.assertNotIn(forbidden, projection)


class PhasePacketTests(unittest.TestCase):
    def test_valid_packet_binds_all_preimages(self) -> None:
        packet = _phase_packet()
        cm._validate_sha256(packet.binding_sha256)
        self.assertEqual((1, 2, 3), tuple(item.cycle for item in packet.cycle_metrics))

    def test_cross_phase_witness_is_rejected(self) -> None:
        packet = _phase_packet()
        with self.assertRaisesRegex(ValueError, "backend_witness_phase"):
            replace(packet, cycle_witnesses=_cycle_backend_witnesses("cuda_candidate"))

    def test_duplicate_witness_cycle_is_rejected(self) -> None:
        packet = _phase_packet()
        witnesses = list(packet.cycle_witnesses)
        witnesses[1] = replace(witnesses[1], cycle=1)
        with self.assertRaisesRegex(ValueError, "bench_identity_mismatch"):
            replace(packet, cycle_witnesses=tuple(witnesses))

    def test_bad_window_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "window_id_syntax"):
            replace(_phase_packet(), window_id="a b")

    def test_manifest_and_record_join_is_exact(self) -> None:
        packet = _phase_packet()
        records = list(packet.turn_records)
        records[1] = replace(records[1], artifact_sha256=SHA_E)
        with self.assertRaisesRegex(ValueError, "turn_record_join"):
            replace(packet, turn_records=tuple(records))

    def test_tampered_turn_measurement_cannot_preserve_projection(self) -> None:
        packet = _phase_packet()
        records = list(packet.turn_records)
        records[1] = replace(records[1], e2e_ms=9_999.0)
        with self.assertRaisesRegex(ValueError, "projection_not_recomputable"):
            replace(packet, turn_records=tuple(records))

    def test_inconsistent_cycle_metric_is_rejected(self) -> None:
        packet = _phase_packet()
        metrics = list(packet.cycle_metrics)
        metrics[0] = replace(metrics[0], vram_after_unload_mib=101)
        with self.assertRaisesRegex(ValueError, "projection_not_recomputable"):
            replace(packet, cycle_metrics=tuple(metrics))

    def test_consistently_rebuilt_cycle_metric_changes_binding(self) -> None:
        packet = _phase_packet()
        metrics = list(packet.cycle_metrics)
        metrics[0] = replace(metrics[0], vram_after_unload_mib=101)
        metrics_tuple = tuple(metrics)
        rebuilt = replace(
            packet,
            cycle_metrics=metrics_tuple,
            summary_projection_json=_projection_json(
                packet.phase,
                packet.turn_records,
                metrics_tuple,
            ),
        )
        self.assertNotEqual(packet.binding_sha256, rebuilt.binding_sha256)

    def test_cycle_metrics_require_exact_tuple_shape_order_and_type(self) -> None:
        packet = _phase_packet()
        for metrics in (
            packet.cycle_metrics[:2],
            tuple(reversed(packet.cycle_metrics)),
            (packet.cycle_metrics[0], "wrong", packet.cycle_metrics[2]),
            list(packet.cycle_metrics),
        ):
            with self.subTest(metrics=metrics):
                with self.assertRaisesRegex(ValueError, "cycle_metrics_shape"):
                    replace(packet, cycle_metrics=metrics)

    def test_records_and_witnesses_are_tuple_only_and_witness_ordered(self) -> None:
        packet = _phase_packet()
        cases = (
            ({"turn_records": list(packet.turn_records)}, "turn_record_join"),
            ({"cycle_witnesses": list(packet.cycle_witnesses)}, "bench_identity_mismatch"),
            (
                {"cycle_witnesses": tuple(reversed(packet.cycle_witnesses))},
                "bench_identity_mismatch",
            ),
        )
        for changes, reason in cases:
            with self.subTest(changes=tuple(changes)):
                with self.assertRaisesRegex(ValueError, reason):
                    replace(packet, **changes)

    def test_completed_packet_rejects_every_noncompleted_turn_outcome(self) -> None:
        packet = _phase_packet()
        for outcome in ("http_timeout", "crash", "hang", "malformed_response"):
            records = list(packet.turn_records)
            records[1] = replace(records[1], outcome=outcome)
            with self.subTest(outcome=outcome):
                with self.assertRaisesRegex(ValueError, "turn_outcome_incomplete"):
                    replace(packet, turn_records=tuple(records))

    def test_packet_outcome_vocabulary_is_closed(self) -> None:
        for outcome in ("weird_outcome", ["completed"]):
            with self.subTest(outcome=outcome):
                with self.assertRaisesRegex(ValueError, "turn_outcome_closed"):
                    replace(_phase_packet(), outcome=outcome)

    def test_packet_phase_refuses_non_string_without_type_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "closed_phase"):
            replace(_phase_packet(), phase=["vulkan_baseline"])

    def test_kernel_window_must_be_nonempty_and_distinct(self) -> None:
        packet = _phase_packet()
        for before, after in (("", "cursor-b"), ("cursor-a", ""), ("same", "same")):
            with self.subTest(before=before, after=after):
                with self.assertRaisesRegex(ValueError, "kernel_window_invalid"):
                    replace(
                        packet,
                        kernel_cursor_before=before,
                        kernel_cursor_after=after,
                    )

    def test_projection_unload_leak_and_failure_counts_are_recomputed(self) -> None:
        packet = _phase_packet()
        for field, value in (
            ("unload_leak_mib", 1.0),
            ("crash_count", 1),
            ("restart_count", 1),
            ("mtp_drafted_tokens", 211),
            ("mtp_accepted_tokens", 148),
            ("mtp_rejected_tokens", 64),
            ("mtp_initialized", False),
        ):
            projection = json.loads(packet.summary_projection_json)
            projection[field] = value
            forged = json.dumps(projection, sort_keys=True, separators=(",", ":"))
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "projection_not_recomputable"):
                    replace(packet, summary_projection_json=forged)

        projection = json.loads(packet.summary_projection_json)
        projection["kernel_counters"]["Xid"] = 1
        with self.assertRaisesRegex(ValueError, "projection_not_recomputable"):
            replace(
                packet,
                summary_projection_json=json.dumps(
                    projection,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )

    def test_projection_must_be_canonical_json(self) -> None:
        packet = _phase_packet()
        projection = json.loads(packet.summary_projection_json)
        variants = []
        variants.append(packet.summary_projection_json + " ")
        variants.append(json.dumps(dict(reversed(tuple(projection.items())))))
        extra = dict(projection)
        extra["extra"] = 1
        variants.append(json.dumps(extra, sort_keys=True, separators=(",", ":")))
        missing = dict(projection)
        del missing["sample_n"]
        variants.append(json.dumps(missing, sort_keys=True, separators=(",", ":")))
        for field, value in (
            ("p95_e2e_ms", float("nan")),
            ("p95_e2e_ms", 20),
            ("sample_n", 7.0),
            ("warmup_count", True),
            ("unload_leak_mib", 0),
        ):
            typed = dict(projection)
            typed[field] = value
            variants.append(json.dumps(typed, sort_keys=True, separators=(",", ":")))
        for variant in variants:
            with self.subTest(variant=variant[-20:]):
                with self.assertRaisesRegex(ValueError, "projection_not_recomputable"):
                    replace(packet, summary_projection_json=variant)

    def test_nonzero_float_unload_leak_is_recomputable(self) -> None:
        packet = _phase_packet()
        metrics = list(packet.cycle_metrics)
        metrics[0] = replace(metrics[0], vram_after_unload_mib=105)
        metrics_tuple = tuple(metrics)
        rebuilt = replace(
            packet,
            cycle_metrics=metrics_tuple,
            summary_projection_json=_projection_json(
                packet.phase,
                packet.turn_records,
                metrics_tuple,
            ),
        )
        self.assertEqual(5.0, json.loads(rebuilt.summary_projection_json)["unload_leak_mib"])

    def test_fully_populated_noncompleted_packet_can_bind_honest_counts(self) -> None:
        packet = _phase_packet()
        records = list(packet.turn_records)
        records[1] = replace(records[1], outcome="crash")
        record_tuple = tuple(records)
        failed = replace(
            packet,
            outcome="crash",
            turn_records=record_tuple,
            summary_projection_json=_projection_json(
                packet.phase,
                record_tuple,
                packet.cycle_metrics,
            ),
        )
        self.assertEqual(1, json.loads(failed.summary_projection_json)["crash_count"])
        cm._validate_sha256(failed.binding_sha256)

    def test_row_derived_packet_outcomes_require_a_matching_row(self) -> None:
        packet = _phase_packet()
        for outcome in ("crash", "hang", "http_timeout", "malformed_response"):
            with self.subTest(outcome=outcome):
                with self.assertRaisesRegex(ValueError, "turn_outcome_incomplete"):
                    replace(packet, outcome=outcome)

    def test_huge_but_json_serializable_vram_refuses_at_projection_boundary(self) -> None:
        packet = _phase_packet()
        metric = replace(packet.cycle_metrics[0], vram_after_unload_mib=10**400)
        with self.assertRaisesRegex(ValueError, "projection_not_recomputable"):
            replace(packet, cycle_metrics=(metric, *packet.cycle_metrics[1:]))

    def test_numeric_contract_rejects_non_json_serializable_integers(self) -> None:
        huge = 10**5_000
        with self.assertRaisesRegex(ValueError, "vram_integer_mib"):
            replace(_phase_cycle_metrics()[0], vram_after_unload_mib=huge)
        with self.assertRaisesRegex(ValueError, "invalid_xid"):
            replace(cm.KernelCounters.zero(), xid=huge)
        with self.assertRaisesRegex(ValueError, "invalid_unload_leak_mib"):
            replace(make_summary(), unload_leak_mib=huge)

    def test_summary_numbers_must_be_finitely_float_representable(self) -> None:
        large = 10**400
        with self.assertRaisesRegex(ValueError, "invalid_unload_leak_mib"):
            replace(make_summary(), unload_leak_mib=large)
        with self.assertRaisesRegex(ValueError, "positive_measurement"):
            replace(make_summary(), median_decode_tps=large)

    def test_huge_integer_in_projection_is_a_typed_refusal(self) -> None:
        packet = _phase_packet()
        huge_json = '{"sample_n":' + ("9" * 5_000) + "}"
        with self.assertRaisesRegex(ValueError, "projection_not_recomputable"):
            replace(packet, summary_projection_json=huge_json)


class PhasePacketPersistenceTests(unittest.TestCase):
    def test_phase_packet_round_trips_through_the_single_decoder(self) -> None:
        packet = _phase_packet()
        encoded = PersistedDocTests.wrapper(
            cm.PHASE_PACKET_SCHEMA,
            packet,
            _phase_packet_fields(packet),
        )
        persisted = cm.PersistedDoc(encoded)
        self.assertIsInstance(persisted.obj, cm.PhasePacket)
        self.assertIsInstance(persisted.obj.turn_manifest.entries, tuple)
        self.assertIsInstance(persisted.obj.turn_records, tuple)
        self.assertIsInstance(persisted.obj.cycle_metrics, tuple)
        self.assertIsInstance(persisted.obj.cycle_metrics[0], cm.CycleMetrics)
        self.assertIsInstance(persisted.obj.cycle_witnesses[0], cm.CycleBackendWitness)
        self.assertIsInstance(
            persisted.obj.cycle_witnesses[0].witness,
            cm.RuntimeBackendWitness,
        )
        self.assertEqual(packet.binding_sha256, persisted.obj.binding_sha256)
        self.assertEqual(packet.binding_sha256, cm.decode_persisted_packet(encoded).binding_sha256)

    def test_nested_packet_tamper_refuses_round_trip(self) -> None:
        packet = _phase_packet()
        fields = _phase_packet_fields(packet)
        fields["turn_records"][1]["e2e_ms"] = 9_999.0
        with self.assertRaisesRegex(ValueError, "persisted_roundtrip"):
            cm.PersistedDoc(
                PersistedDocTests.wrapper(cm.PHASE_PACKET_SCHEMA, packet, fields)
            )

    def test_packet_decoder_rejects_other_persisted_schema(self) -> None:
        snapshot = containment_snapshot("cuda_candidate", "before")
        encoded = PersistedDocTests.wrapper(
            cm.CONTAINMENT_SNAPSHOT_SCHEMA,
            snapshot,
            PersistedDocTests.containment_fields(snapshot),
        )
        with self.assertRaisesRegex(ValueError, "persisted_packet_schema"):
            cm.decode_persisted_packet(encoded)

    def test_reduced_failed_document_is_not_a_typed_phase_packet(self) -> None:
        packet = _phase_packet()
        fields = _phase_packet_fields(packet)
        fields["outcome"] = "crash"
        del fields["turn_manifest"]
        reduced = PersistedDocTests.wrapper(cm.PHASE_PACKET_SCHEMA, packet, fields)
        with self.assertRaisesRegex(ValueError, "persisted_roundtrip"):
            cm.decode_persisted_packet(reduced)

    def test_huge_metric_in_persisted_packet_is_a_typed_roundtrip_refusal(self) -> None:
        packet = _phase_packet()
        fields = _phase_packet_fields(packet)
        fields["cycle_metrics"][0]["vram_after_unload_mib"] = 10**400
        encoded = PersistedDocTests.wrapper(cm.PHASE_PACKET_SCHEMA, packet, fields)
        with self.assertRaisesRegex(ValueError, "persisted_roundtrip"):
            cm.decode_persisted_packet(encoded)

    def test_huge_integer_json_parser_failure_is_typed(self) -> None:
        encoded = b"[" + (b"9" * 5_000) + b"]"
        with self.assertRaisesRegex(ValueError, "persisted_wrapper_shape"):
            cm.PersistedDoc(encoded)


class RollbackEvidenceBundleTests(unittest.TestCase):
    @staticmethod
    def maps_witness() -> cm.RuntimeBackendWitness:
        return cm.RuntimeBackendWitness(
            backend="vulkan",
            maps_sha256=SHA_A,
            phase="vulkan_rollback",
            timestamp="2026-07-13T13:00:00Z",
            release_root_sha256=cm._packet_hash(str(cm.VULKAN_RELEASE_ROOT)),
        )

    @staticmethod
    def kernel_fields(counters: cm.KernelCounters) -> dict[str, object]:
        return {
            "reusemappingdb_map": counters.reusemappingdb_map,
            "pmap_cb": counters.pmap_cb,
            "mmu_walk_map": counters.mmu_walk_map,
            "nv_err_no_memory": counters.nv_err_no_memory,
            "xid": counters.xid,
            "unmatched_nvrm": counters.unmatched_nvrm,
        }

    @classmethod
    def bundle(cls, **overrides: object) -> cm.RollbackEvidenceBundle:
        values: dict[str, object] = {
            "witness": make_rollback_witness(),
            "maps_witness": cls.maps_witness(),
            "kernel_cursor_before": "cursor-a",
            "kernel_cursor_after": "cursor-b",
            "kernel_counters": cm.KernelCounters.zero(),
            "containment_before": containment_snapshot("vulkan_rollback", "before"),
            "containment_after": containment_snapshot("vulkan_rollback", "after"),
            "producer": "owner_human",
            "window_id": "window-1",
            "parent_control_packet_sha256": SHA_A,
            "parent_candidate_packet_sha256": SHA_B,
            "timestamp": "2026-07-13T13:05:00Z",
        }
        values.update(overrides)
        return cm.RollbackEvidenceBundle(**values)

    @staticmethod
    def witness_fields(witness: cm.RollbackWitness) -> dict[str, object]:
        return {
            "unit_sha256": witness.unit_sha256,
            "dropin_sha256": witness.dropin_sha256,
            "runtime_sha256": witness.runtime_sha256,
            "model_sha256": witness.model_sha256,
            "alias": witness.alias,
            "health_state": witness.health_state,
            "mtp_initialized": witness.mtp_initialized,
            "mtp_accepted_tokens": witness.mtp_accepted_tokens,
            "restart_count": witness.restart_count,
            "kernel_counters": RollbackEvidenceBundleTests.kernel_fields(
                witness.kernel_counters
            ),
            "bar1_percent": witness.bar1_percent,
            "vram_mib": witness.vram_mib,
            "shared_library_manifest_sha256": (
                witness.shared_library_manifest_sha256
            ),
            "effective_args_sha256": witness.effective_args_sha256,
            "containment_artifact_sha256": witness.containment_artifact_sha256,
            "artifact_sha256": witness.artifact_sha256,
            "timestamp": witness.timestamp,
        }

    @staticmethod
    def witness_values(witness: cm.RollbackWitness) -> dict[str, object]:
        return {
            "unit_sha256": witness.unit_sha256,
            "dropin_sha256": witness.dropin_sha256,
            "runtime_sha256": witness.runtime_sha256,
            "model_sha256": witness.model_sha256,
            "alias": witness.alias,
            "health_state": witness.health_state,
            "mtp_initialized": witness.mtp_initialized,
            "mtp_accepted_tokens": witness.mtp_accepted_tokens,
            "restart_count": witness.restart_count,
            "kernel_counters": witness.kernel_counters,
            "bar1_percent": witness.bar1_percent,
            "vram_mib": witness.vram_mib,
            "shared_library_manifest_sha256": (
                witness.shared_library_manifest_sha256
            ),
            "effective_args_sha256": witness.effective_args_sha256,
            "containment_artifact_sha256": witness.containment_artifact_sha256,
            "artifact_sha256": witness.artifact_sha256,
            "timestamp": witness.timestamp,
        }

    @classmethod
    def bundle_fields(cls, bundle: cm.RollbackEvidenceBundle) -> dict[str, object]:
        return {
            "witness": cls.witness_fields(bundle.witness),
            "maps_witness": {
                "backend": bundle.maps_witness.backend,
                "maps_sha256": bundle.maps_witness.maps_sha256,
                "phase": bundle.maps_witness.phase,
                "timestamp": bundle.maps_witness.timestamp,
                "release_root_sha256": bundle.maps_witness.release_root_sha256,
            },
            "kernel_cursor_before": bundle.kernel_cursor_before,
            "kernel_cursor_after": bundle.kernel_cursor_after,
            "kernel_counters": cls.kernel_fields(bundle.kernel_counters),
            "containment_before": PersistedDocTests.containment_fields(
                bundle.containment_before
            ),
            "containment_after": PersistedDocTests.containment_fields(
                bundle.containment_after
            ),
            "producer": bundle.producer,
            "window_id": bundle.window_id,
            "parent_control_packet_sha256": bundle.parent_control_packet_sha256,
            "parent_candidate_packet_sha256": (
                bundle.parent_candidate_packet_sha256
            ),
            "timestamp": bundle.timestamp,
        }

    def test_vulkan_rollback_phase_is_valid_direct_and_from_proc_maps(self) -> None:
        direct = self.maps_witness()
        path = cm.VULKAN_RELEASE_ROOT / "libggml-vulkan.so"
        parsed = cm.RuntimeBackendWitness.from_proc_maps(
            str(path),
            phase="vulkan_rollback",
            timestamp="2026-07-13T13:00:01Z",
        )
        self.assertEqual("vulkan_rollback", direct.phase)
        self.assertEqual("vulkan", direct.backend)
        self.assertEqual("vulkan_rollback", parsed.phase)
        self.assertEqual("vulkan", parsed.backend)

    def test_backend_witness_rejects_untyped_phase_and_maps_inputs(self) -> None:
        for phase in ([], {}):
            with self.subTest(surface="direct", phase=phase):
                with self.assertRaisesRegex(ValueError, "backend_witness_invariant"):
                    cm.RuntimeBackendWitness(
                        "vulkan",
                        SHA_A,
                        phase,
                        TS,
                        cm._packet_hash(str(cm.VULKAN_RELEASE_ROOT)),
                    )
            with self.subTest(surface="factory", phase=phase):
                with self.assertRaisesRegex(ValueError, "backend_witness_phase"):
                    cm.RuntimeBackendWitness.from_proc_maps(
                        str(cm.VULKAN_RELEASE_ROOT / "libggml-vulkan.so"),
                        phase=phase,
                        timestamp=TS,
                    )
        for maps_text in (None, [], {}):
            with self.subTest(maps_text=maps_text):
                with self.assertRaisesRegex(ValueError, "backend_unproven"):
                    cm.RuntimeBackendWitness.from_proc_maps(
                        maps_text,
                        phase="vulkan_rollback",
                        timestamp=TS,
                    )

    def test_bundle_binding_covers_every_carried_fact(self) -> None:
        bundle = self.bundle()
        expected = cm._packet_hash(
            {
                "schema": cm.ROLLBACK_EVIDENCE_BUNDLE_SCHEMA,
                "witness_sha256": bundle.witness.binding_sha256,
                "maps_witness_sha256": bundle.maps_witness.binding_sha256,
                "kernel_cursor_before": bundle.kernel_cursor_before,
                "kernel_cursor_after": bundle.kernel_cursor_after,
                "kernel_counters": bundle.kernel_counters.packet(),
                "containment_before_sha256": (
                    bundle.containment_before.binding_sha256
                ),
                "containment_after_sha256": bundle.containment_after.binding_sha256,
                "producer": bundle.producer,
                "window_id": bundle.window_id,
                "parent_control_packet_sha256": (
                    bundle.parent_control_packet_sha256
                ),
                "parent_candidate_packet_sha256": (
                    bundle.parent_candidate_packet_sha256
                ),
                "timestamp": bundle.timestamp,
            }
        )
        self.assertEqual(expected, bundle.binding_sha256)

    def test_component_types_refuse_before_attribute_access(self) -> None:
        cases = {
            "witness": object(),
            "maps_witness": object(),
            "kernel_counters": object(),
            "containment_before": object(),
            "containment_after": object(),
        }
        for field_name, value in cases.items():
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, "rollback_evidence_type"):
                    self.bundle(**{field_name: value})

    def test_component_subclasses_cannot_override_canonical_bindings(self) -> None:
        class ForgedRollbackWitness(cm.RollbackWitness):
            @property
            def binding_sha256(self) -> str:
                return SHA_E

        class ForgedKernelCounters(cm.KernelCounters):
            def packet(self) -> dict[str, int]:
                return {"Xid": 0}

        class ForgedBackendWitness(cm.RuntimeBackendWitness):
            pass

        class ForgedContainmentSnapshot(cm.ContainmentSnapshot):
            pass

        base_witness = make_rollback_witness()
        maps = self.maps_witness()
        snapshot = containment_snapshot("vulkan_rollback", "before")
        forged_witness = ForgedRollbackWitness(**self.witness_values(base_witness))
        forged_maps = ForgedBackendWitness(
            maps.backend,
            maps.maps_sha256,
            maps.phase,
            maps.timestamp,
            maps.release_root_sha256,
        )
        forged_snapshot = ForgedContainmentSnapshot(
            **PersistedDocTests.containment_fields(snapshot)
        )
        cases = {
            "witness": forged_witness,
            "maps_witness": forged_maps,
            "kernel_counters": ForgedKernelCounters.zero(),
            "containment_before": forged_snapshot,
        }
        for field_name, value in cases.items():
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, "rollback_evidence_type"):
                    self.bundle(**{field_name: value})

    def test_bundle_scalars_require_exact_plain_strings(self) -> None:
        class MasqueradingOwner(str):
            def __eq__(self, other: object) -> bool:
                return True

            def __ne__(self, other: object) -> bool:
                return False

        class DishonestCursor(str):
            def __eq__(self, other: object) -> bool:
                return False

            def __ne__(self, other: object) -> bool:
                return True

        cases = (
            ({"producer": MasqueradingOwner("not-owner")}, "rollback_producer"),
            (
                {
                    "kernel_cursor_before": DishonestCursor("same"),
                    "kernel_cursor_after": DishonestCursor("same"),
                },
                "kernel_window_invalid",
            ),
            ({"window_id": str.__new__(MasqueradingOwner, "window-1")}, "window_id_syntax"),
            ({"parent_control_packet_sha256": MasqueradingOwner(SHA_A)}, "invalid_sha256"),
            ({"parent_candidate_packet_sha256": MasqueradingOwner(SHA_B)}, "invalid_sha256"),
            ({"timestamp": MasqueradingOwner(TS)}, "invalid_timestamp"),
        )
        for changes, reason in cases:
            with self.subTest(changes=tuple(changes)):
                with self.assertRaisesRegex(ValueError, reason):
                    self.bundle(**changes)

    def test_maps_and_containment_require_exact_rollback_roles(self) -> None:
        with self.assertRaisesRegex(ValueError, "backend_witness_phase"):
            self.bundle(maps_witness=backend("vulkan_baseline"))

        cases = (
            {
                "containment_before": containment_snapshot(
                    "vulkan_baseline", "before"
                )
            },
            {
                "containment_after": containment_snapshot(
                    "vulkan_baseline", "after"
                )
            },
            {
                "containment_before": containment_snapshot(
                    "vulkan_rollback", "after"
                )
            },
            {
                "containment_after": containment_snapshot(
                    "vulkan_rollback", "before"
                )
            },
        )
        for changes in cases:
            with self.subTest(changes=tuple(changes)):
                with self.assertRaisesRegex(ValueError, "containment_phase"):
                    self.bundle(**changes)

    def test_containment_snapshot_requires_plain_typed_state(self) -> None:
        class TaggedString(str):
            pass

        cases = (
            ({"phase": TaggedString("vulkan_rollback")}, "containment_phase"),
            ({"boundary": TaggedString("before")}, "containment_phase"),
            ({"timestamp": TaggedString(TS)}, "invalid_timestamp"),
            ({"screen_flag_value": ["0"]}, "containment_state"),
            ({"active_state": {"state": "inactive"}}, "containment_state"),
            ({"substate": ["dead"]}, "containment_state"),
            ({"enabled_state": {"state": "disabled"}}, "containment_state"),
        )
        for changes, reason in cases:
            with self.subTest(changes=tuple(changes)):
                values = PersistedDocTests.containment_fields(
                    containment_snapshot("vulkan_rollback", "before")
                )
                values.update(changes)
                with self.assertRaisesRegex(ValueError, reason):
                    cm.ContainmentSnapshot(**values)

    def test_bundle_revalidates_bypassed_containment_shape(self) -> None:
        class TaggedString(str):
            pass

        malformed_state = containment_snapshot("vulkan_rollback", "before")
        object.__setattr__(malformed_state, "active_state", {"state": "inactive"})
        forged_phase = containment_snapshot("vulkan_rollback", "before")
        object.__setattr__(forged_phase, "phase", TaggedString("vulkan_rollback"))
        forged_boundary = containment_snapshot("vulkan_rollback", "before")
        object.__setattr__(forged_boundary, "boundary", TaggedString("before"))
        for snapshot in (malformed_state, forged_phase, forged_boundary):
            with self.subTest(snapshot=snapshot):
                with self.assertRaisesRegex(ValueError, "rollback_evidence_type"):
                    self.bundle(containment_before=snapshot)

    def test_vulkan_rollback_rejects_cuda_maps(self) -> None:
        cuda_path = cm.CUDA_RELEASE_ROOT / "libggml-cuda.so"
        with self.assertRaisesRegex(ValueError, "backend_unproven"):
            cm.RuntimeBackendWitness.from_proc_maps(
                str(cuda_path),
                phase="vulkan_rollback",
                timestamp="2026-07-13T13:00:01Z",
            )

    def test_kernel_window_requires_nonempty_distinct_string_cursors(self) -> None:
        cases = (
            {"kernel_cursor_before": ""},
            {"kernel_cursor_after": ""},
            {"kernel_cursor_before": "cursor-b"},
            {"kernel_cursor_before": 1},
            {"kernel_cursor_after": None},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, "kernel_window_invalid"):
                    self.bundle(**changes)

    def test_window_parents_timestamp_and_producer_validate_typed(self) -> None:
        cases = (
            ({"window_id": ""}, "window_id_syntax"),
            ({"window_id": "window space"}, "window_id_syntax"),
            ({"window_id": None}, "window_id_syntax"),
            ({"parent_control_packet_sha256": "x" * 64}, "invalid_sha256"),
            ({"parent_candidate_packet_sha256": None}, "invalid_sha256"),
            ({"timestamp": "not-a-timestamp"}, "invalid_timestamp"),
            ({"timestamp": None}, "invalid_timestamp"),
            ({"producer": "assembler"}, "rollback_producer"),
            ({"producer": None}, "rollback_producer"),
        )
        for changes, reason in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, reason):
                    self.bundle(**changes)

    def test_failed_or_unclean_evidence_remains_representable(self) -> None:
        failed_witness = replace(make_rollback_witness(), restart_count=1)
        dirty_counters = replace(cm.KernelCounters.zero(), xid=1)
        dirty_before = containment_snapshot(
            "vulkan_rollback", "before", screen_flag_value="1"
        )
        bundle = self.bundle(
            witness=failed_witness,
            kernel_counters=dirty_counters,
            containment_before=dirty_before,
        )
        self.assertFalse(bundle.witness.passed)
        self.assertFalse(bundle.kernel_counters.clean)
        self.assertFalse(bundle.containment_before.clean)
        cm._validate_sha256(bundle.binding_sha256)

    def test_rollback_witness_requires_canonical_nested_types(self) -> None:
        witness = make_rollback_witness()
        cases = (
            {"kernel_counters": object()},
            {"health_state": ["healthy"]},
        )
        for changes in cases:
            with self.subTest(changes=tuple(changes)):
                with self.assertRaisesRegex(ValueError, "rollback_evidence_type"):
                    replace(witness, **changes)

    def test_nested_and_top_level_counters_revalidate_exact_values(self) -> None:
        for value in ([], {}, -1):
            nested_witness = make_rollback_witness()
            object.__setattr__(nested_witness.kernel_counters, "xid", value)
            with self.subTest(surface="nested", value=value):
                with self.assertRaisesRegex(ValueError, "rollback_evidence_type"):
                    self.bundle(witness=nested_witness)

            top_level = cm.KernelCounters.zero()
            object.__setattr__(top_level, "xid", value)
            with self.subTest(surface="top_level", value=value):
                with self.assertRaisesRegex(ValueError, "rollback_evidence_type"):
                    self.bundle(kernel_counters=top_level)

    def test_rollback_values_reject_builtin_subclass_masquerades(self) -> None:
        class MasqueradingString(str):
            def __eq__(self, other: object) -> bool:
                return True

            def __ne__(self, other: object) -> bool:
                return False

        class EvilInt(int):
            pass

        class EvilFloat(float):
            pass

        witness = make_rollback_witness()
        cases = (
            (
                {"unit_sha256": MasqueradingString(witness.unit_sha256)},
                "invalid_sha256",
            ),
            (
                {"alias": MasqueradingString(witness.alias)},
                "rollback_identity_mismatch",
            ),
            ({"restart_count": EvilInt(0)}, "invalid_restart_count"),
            ({"bar1_percent": EvilFloat(20.0)}, "positive_measurement"),
        )
        for changes, reason in cases:
            with self.subTest(changes=tuple(changes)):
                with self.assertRaisesRegex(ValueError, reason):
                    replace(witness, **changes)

        with self.assertRaisesRegex(ValueError, "invalid_xid"):
            replace(cm.KernelCounters.zero(), xid=EvilInt(0))

    def test_bundle_revalidation_rejects_mutated_schema_versions(self) -> None:
        component_cases = []
        witness = make_rollback_witness()
        object.__setattr__(witness, "schema_version", "forged.v1")
        component_cases.append({"witness": witness})
        maps = self.maps_witness()
        object.__setattr__(maps, "schema_version", "forged.v1")
        component_cases.append({"maps_witness": maps})
        counters = cm.KernelCounters.zero()
        object.__setattr__(counters, "schema_version", "forged.v1")
        component_cases.append({"kernel_counters": counters})
        containment = containment_snapshot("vulkan_rollback", "before")
        object.__setattr__(containment, "schema_version", "forged.v1")
        component_cases.append({"containment_before": containment})

        for changes in component_cases:
            with self.subTest(changes=tuple(changes)):
                with self.assertRaisesRegex(ValueError, "rollback_evidence_type"):
                    self.bundle(**changes)

        bundle = self.bundle()
        object.__setattr__(bundle, "schema_version", "forged.v1")
        with self.assertRaisesRegex(ValueError, "rollback_evidence_type"):
            bundle.__post_init__()

    def test_bundle_forces_component_bindings_during_construction(self) -> None:
        malformed_witness = make_rollback_witness()
        object.__setattr__(malformed_witness, "kernel_counters", object())
        malformed_maps = self.maps_witness()
        object.__setattr__(malformed_maps, "maps_sha256", object())
        malformed_counters = cm.KernelCounters.zero()
        object.__setattr__(malformed_counters, "xid", [])
        malformed_snapshot = containment_snapshot("vulkan_rollback", "before")
        object.__setattr__(malformed_snapshot, "artifact_sha256", object())
        cases = (
            {"witness": malformed_witness},
            {"maps_witness": malformed_maps},
            {"kernel_counters": malformed_counters},
            {"containment_before": malformed_snapshot},
        )
        for changes in cases:
            with self.subTest(changes=tuple(changes)):
                with self.assertRaisesRegex(ValueError, "rollback_evidence_type"):
                    self.bundle(**changes)

    def test_persisted_bundle_round_trip_rebuilds_every_nested_type(self) -> None:
        bundle = self.bundle()
        encoded = PersistedDocTests.wrapper(
            cm.ROLLBACK_EVIDENCE_BUNDLE_SCHEMA,
            bundle,
            self.bundle_fields(bundle),
        )
        rebuilt = cm.PersistedDoc(encoded).obj
        self.assertIsInstance(rebuilt, cm.RollbackEvidenceBundle)
        self.assertIsInstance(rebuilt.witness, cm.RollbackWitness)
        self.assertIsInstance(rebuilt.maps_witness, cm.RuntimeBackendWitness)
        self.assertIsInstance(rebuilt.kernel_counters, cm.KernelCounters)
        self.assertIsInstance(rebuilt.containment_before, cm.ContainmentSnapshot)
        self.assertEqual(bundle.binding_sha256, rebuilt.binding_sha256)

    def test_persisted_bundle_nested_tamper_refuses_round_trip(self) -> None:
        bundle = self.bundle()
        fields = self.bundle_fields(bundle)
        fields["witness"]["restart_count"] = 9
        with self.assertRaisesRegex(ValueError, "persisted_roundtrip"):
            cm.PersistedDoc(
                PersistedDocTests.wrapper(
                    cm.ROLLBACK_EVIDENCE_BUNDLE_SCHEMA,
                    bundle,
                    fields,
                )
            )

    def test_persisted_bundle_refuses_noncanonical_witness_health_type(self) -> None:
        bundle = self.bundle()
        malformed_witness = make_rollback_witness()
        object.__setattr__(malformed_witness, "health_state", ["healthy"])
        fields = self.bundle_fields(bundle)
        fields["witness"]["health_state"] = ["healthy"]
        forged_binding = cm._packet_hash(
            {
                "schema": cm.ROLLBACK_EVIDENCE_BUNDLE_SCHEMA,
                "witness_sha256": malformed_witness.binding_sha256,
                "maps_witness_sha256": bundle.maps_witness.binding_sha256,
                "kernel_cursor_before": bundle.kernel_cursor_before,
                "kernel_cursor_after": bundle.kernel_cursor_after,
                "kernel_counters": bundle.kernel_counters.packet(),
                "containment_before_sha256": (
                    bundle.containment_before.binding_sha256
                ),
                "containment_after_sha256": bundle.containment_after.binding_sha256,
                "producer": bundle.producer,
                "window_id": bundle.window_id,
                "parent_control_packet_sha256": (
                    bundle.parent_control_packet_sha256
                ),
                "parent_candidate_packet_sha256": (
                    bundle.parent_candidate_packet_sha256
                ),
                "timestamp": bundle.timestamp,
            }
        )
        with self.assertRaisesRegex(ValueError, "persisted_roundtrip"):
            cm.PersistedDoc(
                PersistedDocTests.wrapper(
                    cm.ROLLBACK_EVIDENCE_BUNDLE_SCHEMA,
                    bundle,
                    fields,
                    binding=forged_binding,
                )
            )

    def test_persisted_containment_refuses_json_native_state_values(self) -> None:
        snapshot = containment_snapshot("vulkan_rollback", "before")
        object.__setattr__(snapshot, "active_state", ["inactive"])
        fields = PersistedDocTests.containment_fields(snapshot)
        encoded = PersistedDocTests.wrapper(
            cm.CONTAINMENT_SNAPSHOT_SCHEMA,
            snapshot,
            fields,
            binding=snapshot.binding_sha256,
        )
        with self.assertRaisesRegex(ValueError, "persisted_roundtrip"):
            cm.PersistedDoc(encoded)


if __name__ == "__main__":
    unittest.main()
