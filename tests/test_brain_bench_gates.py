import inspect
import unittest

from scripts.brain_bench.bench_packet import (
    ApiFamily,
    FailReason,
    GpuContention,
    OpsRubric,
    RestartRecovery,
    StartupHealth,
    Topology,
)
from scripts.brain_bench.gates import (
    ANSWER_CEILING_MS,
    EXCELLENT_BAND_MS,
    FINALIST_K,
    SCREEN_K,
    STRONG_MS,
    GroundingTypeError,
    VariantScore,
    hard_gate_fail_reasons,
    latency_fail,
    ops_cost,
    rank_variants,
    voice_lint,
)
from core.routing.recall_receipt import FORBIDDEN_COGNITION_VERBS


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


class ConstTests(unittest.TestCase):
    def test_frozen(self):
        self.assertEqual(
            (ANSWER_CEILING_MS, STRONG_MS, EXCELLENT_BAND_MS, SCREEN_K, FINALIST_K),
            (12000, 8000, (4000, 6000), 3, 7),
        )


class VoiceLintTests(unittest.TestCase):
    def test_accepts_normal_genderless_answer(self):
        result = voice_lint(
            "Maez found the dated memory and answered from April 27 context with [E1]."
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.reasons, ())

    def test_closed_reasons_for_length_cognition_and_gender(self):
        self.assertIn("too_short", voice_lint("ok").reasons)
        self.assertIn("too_long", voice_lint("word " * 500).reasons)
        self.assertIn("cognition_verb", voice_lint("I think the note was April.").reasons)
        self.assertIn("gendered", voice_lint("Maez said she found it.").reasons)

    def test_canonical_cognition_verbs_are_forbidden(self):
        for verb in FORBIDDEN_COGNITION_VERBS:
            with self.subTest(verb=verb):
                result = voice_lint(f"Maez might {verb} about the dated memory before answering from context.")
                self.assertFalse(result.ok)
                self.assertEqual(result.reasons, ("cognition_verb",))


class GroundingStrictBoolTests(unittest.TestCase):
    def test_rejects_float_drift(self):
        with self.assertRaises(GroundingTypeError):
            hard_gate_fail_reasons(
                false_absence=False,
                grounded_categorical=0.99,
                wrong_absence=False,
                voice_lint_result=voice_lint("Maez answered from context with [E1]."),
            )

    def test_accepts_bool_and_maps_voice_lint(self):
        reasons = hard_gate_fail_reasons(
            false_absence=False,
            grounded_categorical=False,
            wrong_absence=False,
            voice_lint_result=voice_lint("I think she answered."),
        )
        self.assertIn(FailReason.GROUNDING_NOT_CATEGORICAL, reasons)
        self.assertIn(FailReason.VOICE_LINT, reasons)

    def test_hard_gate_signature_has_no_judge_inputs(self):
        params = set(inspect.signature(hard_gate_fail_reasons).parameters)
        for forbidden in ("quality_winrate", "voice_winrate", "judge", "score"):
            self.assertNotIn(forbidden, params)
        self.assertNotIn("voice_lint_ok", params)


class LatencyTests(unittest.TestCase):
    def test_p95_or_max_over_ceiling_fails(self):
        self.assertTrue(latency_fail(p95_ms=11000, max_ms=12001))
        self.assertTrue(latency_fail(p95_ms=12001, max_ms=12001))
        self.assertFalse(latency_fail(p95_ms=9000, max_ms=11000))


class OpsFromEvidenceTests(unittest.TestCase):
    def test_cost_derived_from_closed_evidence(self):
        light = ops_cost(_ops())
        heavy = ops_cost(
            _ops(
                topology=Topology.SEPARATE_SERVER,
                live_daemon_disturbance=True,
                gpu_contention=GpuContention.HIGH,
                restart_recovery=RestartRecovery.WEDGES,
            )
        )
        self.assertLess(light, heavy)

    def test_variant_score_has_no_caller_ops_score(self):
        fields = set(VariantScore.__dataclass_fields__)
        self.assertNotIn("ops", fields)
        self.assertNotIn("ops_cost_value", fields)
        self.assertIn("ops_evidence", fields)


class RankingTests(unittest.TestCase):
    def test_honesty_first(self):
        ranked = rank_variants(
            [
                VariantScore("fast", False, 3000, 0.9, 0.9, 50, _ops()),
                VariantScore("slow", True, 11000, 0.6, 0.6, 10, _ops()),
            ]
        )
        self.assertEqual(ranked[0].label, "slow")

    def test_voice_not_masked_by_quality(self):
        ranked = rank_variants(
            [
                VariantScore("a", True, 8000, 0.95, 0.30, 20, _ops()),
                VariantScore("b", True, 8000, 0.70, 0.70, 20, _ops()),
            ]
        )
        self.assertEqual(ranked[0].label, "b")

    def test_ops_beats_raw_speed_within_same_band(self):
        ranked = rank_variants(
            [
                VariantScore(
                    "fast-heavy",
                    True,
                    8000,
                    0.8,
                    0.8,
                    200,
                    _ops(topology=Topology.SEPARATE_SERVER),
                ),
                VariantScore("slow-light", True, 8000, 0.8, 0.8, 20, _ops()),
            ]
        )
        self.assertEqual(ranked[0].label, "slow-light")


if __name__ == "__main__":
    unittest.main()
