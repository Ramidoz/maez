import dataclasses
import json
import unittest

from scripts.brain_bench.bench_packet import (
    ApiFamily,
    BenchPacket,
    FailReason,
    GpuContention,
    OpsRubric,
    RestartRecovery,
    ScreenResult,
    StartupHealth,
    Topology,
    VariantReport,
)


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


def _report(**overrides):
    data = {
        "label": "variant-a",
        "hard_pass": False,
        "fail_reasons": (FailReason.FALSE_ABSENCE,),
        "p95_ms": 9000,
        "max_ms": 9000,
        "ops": _ops(),
    }
    data.update(overrides)
    return VariantReport(**data)


class ScreenResultTests(unittest.TestCase):
    def test_no_voice_quality_fail_mode(self):
        self.assertEqual(
            {result.value for result in ScreenResult},
            {"passes_screen", "fails_too_slow", "fails_dishonest"},
        )

    def test_packet_rejects_non_enum_screen_result(self):
        with self.assertRaises(ValueError):
            BenchPacket(
                schema_version="bench_packet.v3",
                fixture_manifest_hash="f" * 64,
                variant_config_hash="c" * 64,
                variant_config_source="file",
                variants=(),
                screen_result="free text",
            )

    def test_packet_hashes_must_be_hex(self):
        with self.assertRaises(ValueError):
            BenchPacket(
                schema_version="bench_packet.v3",
                fixture_manifest_hash="z" * 64,
                variant_config_hash="c" * 64,
                variant_config_source="file",
                variants=(),
                screen_result=ScreenResult.FAILS_DISHONEST,
            )

    def test_tail_flags_reject_over_ceiling(self):
        with self.assertRaises(ValueError):
            _report(
                fail_reasons=(FailReason.OVER_ANSWER_CEILING,),
                p95_ms=12001,
                max_ms=12001,
                over_ceiling=True,
                tail_flags=("over_ceiling",),
            )


class RecursiveContentFreeTests(unittest.TestCase):
    def test_rejects_compound_content_field_in_nested_dataclass(self):
        @dataclasses.dataclass(frozen=True)
        class BadNested:
            answer_text: str = "FABRICATED_SENTINEL"

        with self.assertRaises(ValueError):
            VariantReport(
                label="variant-a",
                hard_pass=True,
                fail_reasons=(),
                p95_ms=9000,
                max_ms=9000,
                ops=BadNested(),
            )

    def test_non_vacuous_sentinel_rejected_by_closed_ops_field(self):
        with self.assertRaises(ValueError):
            _ops(api_family="FABRICATED_SENTINEL")

    def test_rejects_sentinel_in_serialized_scalar_fields(self):
        for kwargs in (
            {"label": "FABRICATED_SENTINEL"},
            {"method": "FABRICATED_SENTINEL"},
            {"tail_flags": ("FABRICATED_SENTINEL",)},
        ):
            with self.assertRaises(ValueError, msg=kwargs):
                _report(**kwargs)

    def test_post_init_rejects_non_enum_reason(self):
        with self.assertRaises(ValueError):
            _report(fail_reasons=("free text",))

    def test_serialized_packet_is_content_free(self):
        packet = BenchPacket(
            schema_version="bench_packet.v3",
            fixture_manifest_hash="f" * 64,
            variant_config_hash="c" * 64,
            variant_config_source="file",
            variants=(_report(),),
            screen_result=ScreenResult.FAILS_DISHONEST,
        )
        blob = json.dumps(packet.to_dict())
        self.assertNotIn("FABRICATED_SENTINEL", blob)
        for forbidden in ("answer", "prompt", "snippet", "raw_reply"):
            self.assertNotIn(forbidden, blob)

    def test_latency_serialization_includes_small_k_distribution_fields(self):
        latency = _report(
            p50_ms=3000,
            p90_ms=7000,
            p95_ms=9000,
            max_ms=10000,
            variance_ms=123.5,
            sample_n=7,
        ).to_dict()["latency"]

        for key in ("p50", "p90", "p95", "max", "variance", "sample_n", "method", "tail_flags"):
            self.assertIn(key, latency)


class CovenantFieldTests(unittest.TestCase):
    def test_fields_present(self):
        packet = BenchPacket(
            schema_version="bench_packet.v3",
            fixture_manifest_hash="f" * 64,
            variant_config_hash="c" * 64,
            variant_config_source="file",
            variants=(),
            screen_result=ScreenResult.FAILS_TOO_SLOW,
        ).to_dict()

        self.assertEqual(packet["artifact_role"], "producer_evidence_not_verdict")
        self.assertTrue(packet["owner_verdict_required"])
        self.assertTrue(packet["requires_s5_voice_continuity_gate"])
        self.assertEqual(packet["schema_version"], "bench_packet.v3")
        self.assertEqual(packet["variant_config_hash"], "c" * 64)
        self.assertEqual(packet["variant_config_source"], "file")


if __name__ == "__main__":
    unittest.main()
