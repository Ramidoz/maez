import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.brain_bench.bench import (
    DEFAULT_DEBUG_DUMP_DIR,
    BenchmarkConfigError,
    ProbeSample,
    debug_dump_metadata,
    derive_screen_result,
    run_benchmark,
    write_debug_dump,
)
from scripts.brain_bench.bench_packet import (
    ApiFamily,
    FailReason,
    GpuContention,
    OpsRubric,
    RestartRecovery,
    ScreenResult,
    StartupHealth,
    Topology,
)
from scripts.brain_bench.variants import load_variants


def _registry():
    return load_variants(
        json.dumps(
            [
                {
                    "label": "variant",
                    "base_url": "http://127.0.0.1:11434",
                    "model": "m",
                }
            ]
        ),
        source="file",
    )


class DebugDumpTests(unittest.TestCase):
    def test_debug_dump_directory_is_gitignored(self):
        gitignore = Path(".gitignore").read_text()
        self.assertIn("logs/brain_bench_debug/", gitignore)

    def test_debug_dump_is_quarantine_tagged_in_written_file(self):
        path = write_debug_dump(
            records=[{"answer": "FABRICATED_SENTINEL", "evidence": "[E1] raw"}],
            fixture_manifest_hash="f" * 64,
            variant_config_hash="c" * 64,
        )
        data = json.loads(path.read_text())
        path.unlink()

        self.assertEqual(data["metadata"]["provenance"], "UNTRUSTED")
        self.assertTrue(data["metadata"]["quarantined"])
        self.assertFalse(data["metadata"]["promotable"])
        self.assertIn("FABRICATED_SENTINEL", json.dumps(data))
        self.assertEqual(debug_dump_metadata()["provenance"], "UNTRUSTED")

    def test_debug_dump_rejects_custom_directory(self):
        with self.assertRaises(BenchmarkConfigError):
            write_debug_dump(
                Path(tempfile.mkdtemp()),
                records=[],
                fixture_manifest_hash="f" * 64,
                variant_config_hash="c" * 64,
            )


class ScreenResultPrecedenceTests(unittest.TestCase):
    def test_screen_result_precedence(self):
        self.assertEqual(
            derive_screen_result([{"hard_pass": True, "over_ceiling": False}]),
            ScreenResult.PASSES_SCREEN,
        )
        self.assertEqual(
            derive_screen_result([{"hard_pass": False, "over_ceiling": True, "honesty_clean": True}]),
            ScreenResult.FAILS_TOO_SLOW,
        )
        self.assertEqual(
            derive_screen_result([{"hard_pass": False, "over_ceiling": False, "honesty_clean": False}]),
            ScreenResult.FAILS_DISHONEST,
        )


class OrchestrationTests(unittest.TestCase):
    def test_negative_control_no_text_leak(self):
        def dishonest_probe(_variant):
            return [
                ProbeSample(
                    probe_id="dated_hit",
                    sample_id="sample-0",
                    answer="FABRICATED_SENTINEL",
                    evidence="[E1] FABRICATED_SENTINEL",
                    false_absence=True,
                    grounded_categorical=False,
                    wrong_absence=False,
                    p95_ms=3000,
                    max_ms=3000,
                    ttft_ms=100,
                    tokens_per_sec=20.0,
                    ops_evidence=_ops(),
                )
            ]

        packet = run_benchmark(
            _registry(),
            fixture_manifest_hash="f" * 64,
            probe_run=dishonest_probe,
            write_debug=True,
        )
        packet_blob = json.dumps(packet.to_dict())
        dump_blob = "\n".join(path.read_text() for path in DEFAULT_DEBUG_DUMP_DIR.iterdir())
        for path in DEFAULT_DEBUG_DUMP_DIR.iterdir():
            path.unlink()

        self.assertFalse(packet.variants[0].hard_pass)
        self.assertIn(FailReason.FALSE_ABSENCE, packet.variants[0].fail_reasons)
        self.assertNotIn("FABRICATED_SENTINEL", packet_blob)
        self.assertIn("FABRICATED_SENTINEL", dump_blob)
        self.assertIn('"provenance": "UNTRUSTED"', dump_blob)

    def test_rejects_overlapping_variant_and_judge_ports(self):
        with self.assertRaises(BenchmarkConfigError):
            run_benchmark(
                _registry(),
                fixture_manifest_hash="f" * 64,
                probe_run=lambda _variant: [],
                call_judge=lambda **_kw: "TIE",
                judge_base_url="http://127.0.0.1:11434",
            )

    def test_structured_samples_drive_sample_n_and_inference_fail_reason(self):
        def failed_probe(_variant):
            return [
                ProbeSample(
                    probe_id="dated_hit",
                    sample_id="sample-1",
                    answer="",
                    evidence="",
                    false_absence=False,
                    grounded_categorical=True,
                    wrong_absence=False,
                    p95_ms=3000,
                    max_ms=3000,
                    ttft_ms=None,
                    tokens_per_sec=0.0,
                    inference_failed=True,
                    fail_code="timeout",
                    ops_evidence=_ops(),
                ),
                ProbeSample(
                    probe_id="dated_hit",
                    sample_id="sample-2",
                    answer="Maez answered from dated context with [E1].",
                    evidence="[E1] context",
                    false_absence=False,
                    grounded_categorical=True,
                    wrong_absence=False,
                    p95_ms=3000,
                    max_ms=3000,
                    ttft_ms=100,
                    tokens_per_sec=20.0,
                    ops_evidence=_ops(),
                ),
            ]

        packet = run_benchmark(
            _registry(),
            fixture_manifest_hash="f" * 64,
            probe_run=failed_probe,
        )

        report = packet.variants[0]
        self.assertEqual(report.sample_n, 2)
        self.assertIn(FailReason.INFERENCE_FAILED, report.fail_reasons)

    def test_judge_winrates_are_reported(self):
        def clean_probe(variant):
            return [
                ProbeSample(
                    probe_id="dated_hit",
                    sample_id="sample-0",
                    answer=f"Maez {variant.label} answered from dated context with [E1].",
                    evidence="[E1] context",
                    false_absence=False,
                    grounded_categorical=True,
                    wrong_absence=False,
                    p95_ms=3000,
                    max_ms=3000,
                    ttft_ms=100,
                    tokens_per_sec=20.0,
                    ops_evidence=_ops(),
                )
            ]

        registry = load_variants(
            json.dumps(
                [
                    {"label": "v1", "base_url": "http://127.0.0.1:11434", "model": "m"},
                    {"label": "v2", "base_url": "http://127.0.0.1:11435", "model": "m"},
                ]
            ),
            source="file",
        )
        packet = run_benchmark(
            registry,
            fixture_manifest_hash="f" * 64,
            probe_run=clean_probe,
            call_judge=lambda first, second, **_kw: (
                "A" if "v1" in first.answer else "B" if "v1" in second.answer else "TIE"
            ),
            judge_base_url="http://127.0.0.1:8081",
        )

        self.assertEqual(packet.variants[0].quality_winrate, 1.0)
        self.assertEqual(packet.variants[0].voice_winrate, 1.0)

    def test_judging_phase_opens_only_judge_port(self):
        seen_ports = []

        @contextlib.contextmanager
        def fake_no_egress(*, allow_loopback_ports=()):
            seen_ports.append(tuple(allow_loopback_ports))
            yield

        def clean_probe(_variant):
            return [
                ProbeSample(
                    probe_id="dated_hit",
                    sample_id="sample-0",
                    answer="Maez answered from dated context with [E1].",
                    evidence="[E1] context",
                    false_absence=False,
                    grounded_categorical=True,
                    wrong_absence=False,
                    p95_ms=3000,
                    max_ms=3000,
                    ttft_ms=100,
                    tokens_per_sec=20.0,
                    ops_evidence=_ops(),
                )
            ]

        with mock.patch("scripts.brain_bench.bench.no_egress", fake_no_egress):
            run_benchmark(
                _registry(),
                fixture_manifest_hash="f" * 64,
                probe_run=clean_probe,
                call_judge=lambda **_kw: "TIE",
                judge_base_url="http://127.0.0.1:8081",
            )

        self.assertIn((11434,), seen_ports)
        self.assertIn((8081,), seen_ports)
        self.assertNotIn((11434, 8081), seen_ports)
        self.assertNotIn((8081, 11434), seen_ports)


def _ops(**overrides):
    data = {
        "api_family": ApiFamily.OLLAMA,
        "topology": Topology.REUSE_ENDPOINT,
        "bind_host_verified": True,
        "live_daemon_disturbance": False,
        "gpu_contention": GpuContention.NONE,
        "startup_health": StartupHealth.OK,
        "streaming_support": True,
        "restart_recovery": RestartRecovery.CLEAN,
    }
    data.update(overrides)
    return OpsRubric(**data)


if __name__ == "__main__":
    unittest.main()
