import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.brain_bench.samples import ProbeSample
from scripts.brain_bench.variants import load_variants
from scripts.recall_flip_eval import probes as eval_probes
from scripts.recall_flip_eval import sandbox


def _variant():
    return load_variants(
        json.dumps(
            [
                {
                    "label": "v",
                    "backend_family": "ollama",
                    "base_url": "http://127.0.0.1:11434",
                    "model": "bench-model",
                    "ops": {
                        "api_family": "ollama",
                        "topology": "reuse_endpoint",
                        "bind_host_verified": True,
                        "live_daemon_disturbance": False,
                        "gpu_contention": "low",
                        "startup_health": "ok",
                        "streaming_support": True,
                        "restart_recovery": "clean",
                    },
                }
            ]
        )
    )[0]


def _llamacpp_variant():
    return load_variants(
        json.dumps(
            [
                {
                    "label": "llama",
                    "backend_family": "openai_compatible",
                    "base_url": "http://127.0.0.1:8080",
                    "model": "qwen36-27b",
                    "ops": {
                        "api_family": "llama_cpp",
                        "topology": "separate_server",
                        "bind_host_verified": True,
                        "live_daemon_disturbance": False,
                        "gpu_contention": "high",
                        "startup_health": "ok",
                        "streaming_support": True,
                        "restart_recovery": "manual",
                    },
                }
            ]
        )
    )[0]


class ProbeRunnerTests(unittest.TestCase):
    def test_probe_run_seeds_2a_probes_and_calls_production_focused_synthesize(self):
        from scripts.brain_bench.probe_runner import build_probe_run

        seen_payloads = []

        def stream_factory(*, variant, payload):
            seen_payloads.append(payload)
            return iter([{"content": "Offline answer cites [E1]."}])

        with tempfile.TemporaryDirectory() as tmp:
            with sandbox.sandbox_env(Path(tmp)):
                probe_run = build_probe_run(k=1, stream_factory=stream_factory)
                with mock.patch(
                    "scripts.brain_bench.probe_runner.harness._seed_for_probe",
                    wraps=__import__(
                        "scripts.recall_flip_eval.harness",
                        fromlist=["_seed_for_probe"],
                    )._seed_for_probe,
                ) as seed_spy, mock.patch(
                    "scripts.recall_flip_eval.harness.run_probe",
                    side_effect=AssertionError("driver must not call 2a deterministic run_probe"),
                ), mock.patch(
                    "scripts.brain_bench.probe_runner.focused_cognition.focused_synthesize",
                    wraps=__import__(
                        "core.routing.focused_cognition",
                        fromlist=["focused_synthesize"],
                    ).focused_synthesize,
                ) as synth_spy:
                    rows = list(probe_run(_variant()))

        self.assertTrue(rows)
        self.assertTrue(all(isinstance(row, ProbeSample) for row in rows))
        self.assertEqual(
            {call.args[1].probe_id for call in seed_spy.call_args_list},
            {probe.probe_id for probe in eval_probes.PROBES},
        )
        self.assertTrue(synth_spy.called)
        self.assertTrue(
            all(call.kwargs["surface"] == "telegram" and callable(call.kwargs["chat_fn"]) for call in synth_spy.call_args_list)
        )
        self.assertTrue(all(call.kwargs["model"] == "bench-model" for call in synth_spy.call_args_list))
        self.assertTrue(seen_payloads)
        self.assertTrue(all(payload["model"] == "bench-model" for payload in seen_payloads))
        self.assertTrue(all(payload["think"] is False for payload in seen_payloads))

    def test_probe_run_with_llamacpp_variant_uses_openai_backend_not_ollama_chat(self):
        from scripts.brain_bench.probe_runner import build_probe_run

        selected = (eval_probes.get_probe("dated_hit"),)
        response = mock.Mock()
        response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Offline answer cites [E1]."}}]}',
            b"data: [DONE]",
        ]
        response.raise_for_status.return_value = None

        with tempfile.TemporaryDirectory() as tmp:
            with sandbox.sandbox_env(Path(tmp)):
                with mock.patch.object(eval_probes, "PROBES", selected), mock.patch("requests.Session") as session_factory:
                    session = session_factory.return_value
                    session.post.return_value = response
                    rows = list(build_probe_run(k=1)(_llamacpp_variant()))

        self.assertEqual(session.post.call_args.args[0], "http://127.0.0.1:8080/v1/chat/completions")
        self.assertFalse(rows[0].inference_failed)
        self.assertIsNone(rows[0].fail_code)

    def test_answerable_dated_probes_synthesize_and_ground_on_fixture_content(self):
        from scripts.brain_bench.probe_runner import build_probe_run

        selected = (
            eval_probes.get_probe("multi_year"),
            eval_probes.get_probe("both_shaped"),
            eval_probes.get_probe("dated_hit"),
        )
        payloads = []

        def label_for(system: str, phrase: str) -> str:
            for line in system.splitlines():
                if phrase not in line:
                    continue
                match = re.search(r"\[(E\d+)\]", line)
                if match:
                    return match.group(1)
            self.fail(f"missing phrase in evidence prompt: {phrase}")

        def stream_factory(*, variant, payload):
            del variant
            payloads.append(payload)
            system = payload["messages"][0]["content"]
            self.assertNotIn("SANDBOX", system)
            self.assertNotIn("TOKEN", system)
            if "root disk crossed a watch threshold" in system:
                label = label_for(system, "root disk crossed a watch threshold")
                return iter(
                    [
                        {
                            "content": (
                                "The April 27, 2026 current-year note says router "
                                f"failover stayed stable and the root disk crossed a watch threshold [{label}]."
                            )
                        }
                    ]
                )
            if "cedar-card checklist" in system:
                label = label_for(system, "cedar-card checklist")
                return iter(
                    [
                        {
                            "content": (
                                "Around April 27, we were tuning the recall gate with "
                                f"the cedar-card checklist [{label}]."
                            )
                        }
                    ]
                )
            if "dated answer should mention April 27" in system:
                label = label_for(system, "dated answer should mention April 27")
                return iter(
                    [
                        {
                            "content": (
                                "The April 27 dated note says the dated answer should "
                                f"mention April 27 and the router watch threshold [{label}]."
                            )
                        }
                    ]
                )
            self.fail("answerable fixture content was not present in the prompt")

        with tempfile.TemporaryDirectory() as tmp:
            with sandbox.sandbox_env(Path(tmp)):
                with mock.patch.object(eval_probes, "PROBES", selected):
                    rows = list(build_probe_run(k=1, stream_factory=stream_factory)(_variant()))

        self.assertEqual(len(payloads), len(selected))
        self.assertEqual(len(rows), len(selected))
        self.assertTrue(all(row.synthesized for row in rows))
        self.assertTrue(all(row.answer for row in rows))
        self.assertTrue(all(row.grounded_categorical for row in rows))
        self.assertFalse(any(row.false_absence for row in rows))
        self.assertFalse(any(row.inference_failed for row in rows))
        for row in rows:
            with self.subTest(probe_id=row.probe_id):
                self.assertTrue(row.cited_ids)
                self.assertTrue(row.cited_durable_ids)
                self.assertTrue(row.expected_fixture_ids)
                self.assertTrue(set(row.cited_durable_ids) & set(row.expected_fixture_ids))
                self.assertTrue(row.cited_confirmed_memory_context)

    def test_available_fixture_honest_decline_fails_grounding_not_categorical(self):
        from scripts.brain_bench.probe_runner import build_probe_run

        selected = (eval_probes.get_probe("dated_hit"),)

        with tempfile.TemporaryDirectory() as tmp:
            with sandbox.sandbox_env(Path(tmp)):
                with mock.patch.object(eval_probes, "PROBES", selected):
                    rows = list(
                        build_probe_run(
                            k=1,
                            stream_factory=lambda **_kw: iter(
                                [
                                    {
                                        "content": (
                                            "I do not have enough specific information to answer that."
                                        )
                                    }
                                ]
                            ),
                        )(_variant())
                    )

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].synthesized)
        self.assertFalse(rows[0].inference_failed)
        self.assertFalse(rows[0].grounded_categorical)
        self.assertFalse(rows[0].wrong_absence)

    def test_assert_probe_result_is_the_grounding_authority(self):
        from scripts.brain_bench.probe_runner import build_probe_run

        selected = (
            eval_probes.ProbeDefinition(
                "dated_hit",
                "smoke",
                False,
                ("What did we note around April 27?", "Pull April 27."),
            ),
        )
        verdicts = iter([(("forced_safe",), False), (("forced_unsafe",), True)])
        seen_result_objects = []

        def fake_assert(probe, result, *, expected_fixture_ids=()):
            seen_result_objects.append(result)
            return next(verdicts)

        with tempfile.TemporaryDirectory() as tmp:
            with sandbox.sandbox_env(Path(tmp)):
                with mock.patch.object(eval_probes, "PROBES", selected), mock.patch(
                    "scripts.brain_bench.probe_runner.probes.assert_probe_result",
                    side_effect=fake_assert,
                ):
                    rows = list(
                        build_probe_run(
                            k=2,
                            stream_factory=lambda **_kw: iter([{"content": "Citation-shaped [E1]."}]),
                        )(_variant())
                    )

        self.assertEqual([row.grounded_categorical for row in rows], [True, False])
        self.assertTrue(all(type(row.grounded_categorical) is bool for row in rows))
        for result in seen_result_objects:
            for attr in (
                "outcome_class",
                "cited_durable_ids",
                "cited_confirmed_memory_context",
                "working_set_source_types",
            ):
                self.assertTrue(hasattr(result, attr), attr)

    def test_legal_dated_miss_uses_2a_outcome_contract_without_model_call(self):
        from scripts.brain_bench.probe_runner import build_probe_run

        selected = (eval_probes.get_probe("dated_miss"),)
        stream_calls = 0

        def stream_factory(**_kw):
            nonlocal stream_calls
            stream_calls += 1
            return iter([{"content": "should not be called"}])

        with tempfile.TemporaryDirectory() as tmp:
            with sandbox.sandbox_env(Path(tmp)):
                with mock.patch.object(eval_probes, "PROBES", selected):
                    rows = list(build_probe_run(k=1, stream_factory=stream_factory)(_variant()))

        self.assertEqual(stream_calls, 0)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].inference_failed)
        self.assertEqual(rows[0].answer, "")
        self.assertTrue(rows[0].grounded_categorical)

    def test_partial_failure_scrubs_answer_and_fails_closed(self):
        from scripts.brain_bench.probe_runner import build_probe_run

        selected = (eval_probes.get_probe("dated_hit"),)

        def boom_after_one(**_kw):
            def gen():
                yield {"content": "FABRICATED_SENTINEL"}
                raise TimeoutError()

            return gen()

        with tempfile.TemporaryDirectory() as tmp:
            with sandbox.sandbox_env(Path(tmp)):
                with mock.patch.object(eval_probes, "PROBES", selected):
                    rows = list(build_probe_run(k=1, stream_factory=boom_after_one)(_variant()))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].answer, "")
        self.assertTrue(rows[0].inference_failed)
        self.assertEqual(rows[0].fail_code, "timeout")
        self.assertFalse(rows[0].grounded_categorical)

    def test_outer_audit_path_is_rewritten_inside_per_probe_sandbox(self):
        from scripts.brain_bench.probe_runner import build_probe_run

        selected = (eval_probes.get_probe("dated_miss"),)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with sandbox.sandbox_env(root):
                # Mirror the launcher: an outer-sandbox path must not poison
                # narrower per-probe sandbox assertions.
                __import__("os").environ["MAEZ_AUDIT_LOG_PATH"] = str(root / "logs" / "audit.jsonl")
                with mock.patch.object(eval_probes, "PROBES", selected):
                    rows = list(
                        build_probe_run(
                            k=1,
                            stream_factory=lambda **_kw: iter([{"content": "unused"}]),
                        )(_variant())
                    )

        self.assertEqual(len(rows), 1)

    def test_probe_sample_uses_variant_ops_evidence_and_focused_elapsed_latency(self):
        from scripts.brain_bench.probe_runner import build_probe_run

        selected = (
            eval_probes.ProbeDefinition(
                "dated_hit",
                "smoke",
                False,
                ("What did we note around April 27?",),
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            with sandbox.sandbox_env(Path(tmp)):
                from scripts.brain_bench.inference import GenerationMeasurement
                from scripts.recall_flip_eval.harness import ProbeArmResult

                focused_result = ProbeArmResult(
                    answer="Citation-shaped [E1].",
                    outcome_class="answered_grounded",
                    receipt="consulted",
                    focused_elapsed_ms=5000,
                    citation_coverage=1.0,
                    cited_durable_ids=("fixture-1",),
                    cited_confirmed_memory_context=True,
                    working_set_source_types=("memory_context",),
                )
                measurement = GenerationMeasurement(
                    answer="Citation-shaped [E1].",
                    ttft_ms=50,
                    total_ms=1000,
                    output_tokens=1,
                    tokens_per_sec=1.0,
                    failed=False,
                )

                with mock.patch.object(eval_probes, "PROBES", selected), mock.patch(
                    "scripts.brain_bench.probe_runner._run_focused_probe",
                    return_value=(focused_result, measurement, "[E1] context"),
                ):
                    rows = list(
                        build_probe_run(
                            k=1,
                            stream_factory=lambda **_kw: iter([{"content": "Citation-shaped [E1]."}]),
                        )(_variant())
                    )

        self.assertEqual(rows[0].ops_evidence.gpu_contention.value, "low")
        self.assertEqual(rows[0].latency_ms, 5000)
