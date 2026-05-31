import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.brain_bench.bench import ProbeSample
from scripts.brain_bench.variants import load_variants
from scripts.recall_flip_eval import probes as eval_probes
from scripts.recall_flip_eval import sandbox


def _variant():
    return load_variants(
        json.dumps(
            [
                {
                    "label": "v",
                    "base_url": "http://127.0.0.1:11434",
                    "model": "bench-model",
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
