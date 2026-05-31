import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.brain_bench.bench import (
    DEFAULT_DEBUG_DUMP_DIR,
    BenchmarkConfigError,
    debug_dump_metadata,
    derive_screen_result,
    run_full_battery,
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
from scripts.brain_bench.gates import FINALIST_K, SCREEN_K
from scripts.brain_bench.samples import ProbeSample
from scripts.brain_bench.variants import load_variants


def _registry():
    return load_variants(
        json.dumps(
            [
                {
                    "label": "variant",
                    "backend_family": "ollama",
                    "base_url": "http://127.0.0.1:11434",
                    "model": "m",
                    "ops": _ops_config(),
                }
            ]
        ),
        source="file",
    )


def _registry_many(labels):
    return load_variants(
        json.dumps(
            [
                {
                    "label": label,
                    "backend_family": "ollama",
                    "base_url": f"http://127.0.0.1:{11434 + index}",
                    "model": "m",
                    "ops": _ops_config(),
                }
                for index, label in enumerate(labels)
            ]
        ),
        source="file",
    )


def _report(label="variant", **overrides):
    data = {
        "label": label,
        "hard_pass": True,
        "fail_reasons": (),
        "p95_ms": 3000,
        "max_ms": 3000,
        "ops": _ops(),
        "sample_n": 3,
        "synthesized_sample_n": 3,
    }
    data.update(overrides)
    from scripts.brain_bench.bench_packet import VariantReport

    return VariantReport(**data)


def _packet(registry, reports):
    from scripts.brain_bench.bench_packet import BenchPacket

    return BenchPacket(
        schema_version="bench_packet.v3",
        fixture_manifest_hash="f" * 64,
        variant_config_hash=registry.variant_config_hash,
        variant_config_source=registry.variant_config_source.value,
        variants=tuple(reports),
        screen_result=derive_screen_result(
            [
                {
                    "hard_pass": report.hard_pass,
                    "over_ceiling": report.over_ceiling,
                    "honesty_clean": not any(reason is not FailReason.OVER_ANSWER_CEILING for reason in report.fail_reasons),
                }
                for report in reports
            ]
        ),
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

    def test_debug_dump_stays_repo_quarantined_from_other_cwd(self):
        prior = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                path = write_debug_dump(
                    records=[],
                    fixture_manifest_hash="f" * 64,
                    variant_config_hash="c" * 64,
                )
            finally:
                os.chdir(prior)
        path.unlink()

        self.assertTrue(path.resolve().is_relative_to(DEFAULT_DEBUG_DUMP_DIR.resolve()))

    def test_debug_dump_names_do_not_collide_in_same_millisecond(self):
        with mock.patch("scripts.brain_bench.bench.time.time", return_value=1.234):
            first = write_debug_dump(
                records=[{"answer": "first"}],
                fixture_manifest_hash="f" * 64,
                variant_config_hash="c" * 64,
            )
            second = write_debug_dump(
                records=[{"answer": "second"}],
                fixture_manifest_hash="f" * 64,
                variant_config_hash="c" * 64,
            )
        try:
            self.assertNotEqual(first, second)
            self.assertIn("first", first.read_text())
            self.assertIn("second", second.read_text())
        finally:
            first.unlink(missing_ok=True)
            second.unlink(missing_ok=True)


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

    def test_unjudged_run_marks_soft_scores_unmeasured(self):
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

        packet = run_benchmark(
            _registry(),
            fixture_manifest_hash="f" * 64,
            probe_run=clean_probe,
        )

        self.assertFalse(packet.judge_evaluated)
        self.assertIsNone(packet.variants[0].quality_winrate)
        self.assertIsNone(packet.variants[0].voice_winrate)
        self.assertIsNone(packet.variants[0].quality_per_second)
        data = packet.to_dict()
        self.assertFalse(data["judge_evaluated"])
        self.assertIsNone(data["variants"][0]["quality_winrate"])

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
                    {
                        "label": "v1",
                        "backend_family": "ollama",
                        "base_url": "http://127.0.0.1:11434",
                        "model": "m",
                        "ops": _ops_config(),
                    },
                    {
                        "label": "v2",
                        "backend_family": "ollama",
                        "base_url": "http://127.0.0.1:11435",
                        "model": "m",
                        "ops": _ops_config(),
                    },
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

        self.assertTrue(packet.judge_evaluated)
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

    def test_run_full_battery_uses_screen_k_then_finalist_k_and_excludes_failures(self):
        registry = _registry_many(("clean-a", "dishonest", "slow", "clean-b"))
        build_ks = []
        stage_registries = []

        def build_probe_run_fn(*, k):
            build_ks.append(k)
            return lambda _variant: []

        def fake_run_benchmark(stage_registry, **kwargs):
            stage_registries.append((tuple(variant.label for variant in stage_registry), kwargs.get("call_judge")))
            if len(stage_registries) == 1:
                return _packet(
                    stage_registry,
                    (
                        _report("clean-a", p95_ms=3000, max_ms=3000, sample_n=3),
                        _report(
                            "dishonest",
                            hard_pass=False,
                            fail_reasons=(FailReason.FALSE_ABSENCE,),
                            sample_n=3,
                        ),
                        _report(
                            "slow",
                            hard_pass=False,
                            fail_reasons=(FailReason.OVER_ANSWER_CEILING,),
                            p95_ms=12001,
                            max_ms=12001,
                            over_ceiling=True,
                            sample_n=3,
                        ),
                        _report("clean-b", p95_ms=5000, max_ms=5000, sample_n=3),
                    ),
                )
            return _packet(
                stage_registry,
                (
                    _report("clean-a", p95_ms=2900, max_ms=3000, sample_n=7),
                    _report("clean-b", p95_ms=4900, max_ms=5000, sample_n=7),
                ),
            )

        with mock.patch("scripts.brain_bench.bench.run_benchmark", side_effect=fake_run_benchmark):
            packet = run_full_battery(
                registry,
                fixture_manifest_hash="f" * 64,
                build_probe_run_fn=build_probe_run_fn,
                call_judge=lambda **_kw: "TIE",
            )

        self.assertEqual(build_ks, [SCREEN_K, FINALIST_K])
        self.assertEqual(stage_registries[0][0], ("clean-a", "dishonest", "slow", "clean-b"))
        self.assertIsNone(stage_registries[0][1])
        self.assertEqual(stage_registries[1][0], ("clean-b", "clean-a"))
        self.assertIsNotNone(stage_registries[1][1])
        reports = {report.label: report for report in packet.variants}
        self.assertEqual(reports["dishonest"].sample_n, 3)
        self.assertEqual(reports["slow"].sample_n, 3)
        self.assertEqual(reports["clean-a"].sample_n, 7)
        self.assertIn(FailReason.FALSE_ABSENCE, reports["dishonest"].fail_reasons)
        self.assertIn(FailReason.OVER_ANSWER_CEILING, reports["slow"].fail_reasons)

    def test_run_full_battery_preserves_ranked_finalist_order(self):
        registry = _registry_many(("config-first", "best", "middle", "screenout"))
        stage_registries = []

        def build_probe_run_fn(*, k):
            return lambda _variant: []

        def fake_run_benchmark(stage_registry, **_kwargs):
            stage_registries.append(tuple(variant.label for variant in stage_registry))
            if len(stage_registries) == 1:
                return _packet(
                    stage_registry,
                    (
                        _report("config-first", p95_ms=7000, max_ms=7000, tokens_per_sec=20),
                        _report("best", p95_ms=5000, max_ms=5000, tokens_per_sec=90),
                        _report("middle", p95_ms=5000, max_ms=5000, tokens_per_sec=50),
                        _report(
                            "screenout",
                            hard_pass=False,
                            fail_reasons=(FailReason.FALSE_ABSENCE,),
                        ),
                    ),
                )
            return _packet(
                stage_registry,
                tuple(_report(label, sample_n=7) for label in stage_registries[-1]),
            )

        with mock.patch("scripts.brain_bench.bench.run_benchmark", side_effect=fake_run_benchmark):
            packet = run_full_battery(
                registry,
                fixture_manifest_hash="f" * 64,
                build_probe_run_fn=build_probe_run_fn,
            )

        self.assertEqual(stage_registries[1], ("best", "middle", "config-first"))
        self.assertEqual(
            tuple(report.label for report in packet.variants),
            ("best", "middle", "config-first", "screenout"),
        )

    def test_tail_risk_uses_sample_distribution_not_average(self):
        def probe(_variant):
            return [
                _sample(latency_ms=2000),
                _sample(latency_ms=3000),
                _sample(latency_ms=10000),
            ]

        report = run_benchmark(
            _registry(),
            fixture_manifest_hash="f" * 64,
            probe_run=probe,
        ).variants[0]

        self.assertEqual(report.tail_flags, ("tail_risk",))
        self.assertFalse(report.over_ceiling)
        self.assertNotIn(FailReason.OVER_ANSWER_CEILING, report.fail_reasons)

    def test_over_ceiling_is_hard_fail_not_tail_risk_only(self):
        def probe(_variant):
            return [
                _sample(latency_ms=2000),
                _sample(latency_ms=3000),
                _sample(latency_ms=12001),
            ]

        report = run_benchmark(
            _registry(),
            fixture_manifest_hash="f" * 64,
            probe_run=probe,
        ).variants[0]

        self.assertEqual(report.tail_flags, ())
        self.assertTrue(report.over_ceiling)
        self.assertIn(FailReason.OVER_ANSWER_CEILING, report.fail_reasons)

    def test_legal_decline_empty_answer_is_not_voice_linted(self):
        def probe(_variant):
            return [
                _sample(
                    answer="",
                    evidence="",
                    probe_id="dated_miss",
                    sample_id="dated-miss-s1",
                    grounded_categorical=True,
                    latency_ms=1000,
                    p95_ms=1000,
                    max_ms=1000,
                    ttft_ms=None,
                    tokens_per_sec=0.0,
                    synthesized=False,
                )
            ]

        report = run_benchmark(
            _registry(),
            fixture_manifest_hash="f" * 64,
            probe_run=probe,
        ).variants[0]

        self.assertTrue(report.hard_pass)
        self.assertEqual(report.fail_reasons, ())

    def test_latency_discloses_synthesized_answer_denominator(self):
        def probe(_variant):
            return [
                _sample(
                    answer="",
                    evidence="",
                    probe_id="dated_miss",
                    sample_id="dated-miss-s1",
                    grounded_categorical=True,
                    latency_ms=100,
                    p95_ms=100,
                    max_ms=100,
                    ttft_ms=None,
                    tokens_per_sec=0.0,
                    synthesized=False,
                ),
                _sample(
                    probe_id="dated_hit",
                    sample_id="dated-hit-s1",
                    latency_ms=7000,
                    p95_ms=7000,
                    max_ms=7000,
                    synthesized=True,
                ),
            ]

        report = run_benchmark(
            _registry(),
            fixture_manifest_hash="f" * 64,
            probe_run=probe,
        ).variants[0]

        self.assertEqual(report.sample_n, 2)
        self.assertEqual(report.synthesized_sample_n, 1)
        latency = report.to_dict()["latency"]
        self.assertEqual(latency["sample_n"], 2)
        self.assertEqual(latency["synthesized_sample_n"], 1)


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


def _ops_config(**overrides):
    data = {
        "api_family": "ollama",
        "topology": "reuse_endpoint",
        "bind_host_verified": True,
        "live_daemon_disturbance": False,
        "gpu_contention": "none",
        "startup_health": "ok",
        "streaming_support": True,
        "restart_recovery": "clean",
    }
    data.update(overrides)
    return data


def _sample(**overrides):
    latency_ms = overrides.pop("latency_ms", 3000)
    data = {
        "probe_id": "dated_hit",
        "sample_id": f"s-{latency_ms}",
        "answer": "Maez answered from dated context with [E1].",
        "evidence": "[E1] context",
        "false_absence": False,
        "grounded_categorical": True,
        "wrong_absence": False,
        "p95_ms": latency_ms,
        "max_ms": latency_ms,
        "latency_ms": latency_ms,
        "ttft_ms": 100,
        "tokens_per_sec": 20.0,
        "ops_evidence": _ops(),
        "synthesized": True,
    }
    data.update(overrides)
    return ProbeSample(**data)


if __name__ == "__main__":
    unittest.main()
