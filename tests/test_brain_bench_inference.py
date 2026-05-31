import json
import unittest
from unittest import mock

import requests

from core.routing.focused_cognition import EvidenceItem, WorkingSet, focused_synthesize
from scripts.brain_bench.inference import (
    FailCode,
    make_benchmark_chat_fn,
    measure_generation,
)
from scripts.brain_bench.inference_backend import ollama_stream
from scripts.brain_bench.variants import load_variants


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


def _loopback_variant(**overrides):
    data = {
        "label": "v",
        "base_url": "http://127.0.0.1:11434",
        "model": "bench-model",
        "chat_kwargs": {"temperature": 0.2, "num_predict": 99},
        "ops": _ops_config(),
    }
    data.update(overrides)
    return load_variants(json.dumps([data]))[0]


class ChatFnAdapterTests(unittest.TestCase):
    def test_adapter_signature_response_shape_and_payload_merge(self):
        seen = {}

        def fake_stream(*, variant, payload):
            seen["variant"] = variant
            seen["payload"] = payload
            return iter([{"content": "April "}, {"content": "27 [E1]"}])

        chat_fn, measurements = make_benchmark_chat_fn(
            variant=_loopback_variant(), stream_factory=fake_stream
        )
        out = chat_fn(
            model="ignored-by-adapter",
            messages=[{"role": "user", "content": "q"}],
            think=False,
            options={"num_predict": 256},
        )

        self.assertEqual(out.message.content, "April 27 [E1]")
        self.assertEqual(measurements.last().answer, "April 27 [E1]")
        self.assertEqual(seen["payload"]["model"], "bench-model")
        self.assertTrue(seen["payload"]["stream"])
        self.assertFalse(seen["payload"]["think"])
        self.assertEqual(seen["payload"]["options"]["temperature"], 0.2)
        self.assertEqual(seen["payload"]["options"]["num_predict"], 256)

    def test_adapter_failure_returns_empty_response_and_closed_code(self):
        def boom_after_one(*, variant, payload):
            def gen():
                yield {"content": "FABRICATED_SENTINEL"}
                raise TimeoutError("raw timeout details")

            return gen()

        chat_fn, measurements = make_benchmark_chat_fn(
            variant=_loopback_variant(), stream_factory=boom_after_one
        )
        out = chat_fn(model="m", messages=[], think=False, options={})

        measurement = measurements.last()
        self.assertEqual(out.message.content, "")
        self.assertTrue(measurement.failed)
        self.assertEqual(measurement.fail_code, FailCode.TIMEOUT.value)
        self.assertEqual(measurement.answer, "")

    def test_real_focused_synthesize_uses_adapter_shape(self):
        chat_fn, measurements = make_benchmark_chat_fn(
            variant=_loopback_variant(),
            stream_factory=lambda **_kw: iter([{"content": "Grounded [E1]"}]),
        )
        working_set = WorkingSet(
            items=(
                EvidenceItem(
                    local_label="E1",
                    source_type="memory_context",
                    text="April 27 infrastructure note.",
                    durable_id="fixture-1",
                ),
            ),
            ordered_evidence_text="[E1] April 27 infrastructure note.",
            owner_question="What did we note around April 27?",
            working_set_chars=72,
            working_set_tokens_est=18,
        )

        result = focused_synthesize(working_set, surface="telegram", chat_fn=chat_fn)

        self.assertEqual(result.reply, "Grounded [E1]")
        self.assertEqual(measurements.last().answer, "Grounded [E1]")


class MeasurementTests(unittest.TestCase):
    def test_ttft_is_first_nonempty_content(self):
        ticks = iter([0.0, 0.3, 0.4, 0.8, 1.2, 2.0])
        m = measure_generation(
            variant=_loopback_variant(),
            payload={},
            clock=lambda: next(ticks),
            stream_factory=lambda **_kw: iter(
                [{"content": ""}, {"content": ""}, {"content": "A "}, {"content": "B"}]
            ),
        )

        self.assertEqual(m.ttft_ms, 800)
        self.assertEqual(m.total_ms, 2000)
        self.assertEqual(m.output_tokens, 2)
        self.assertEqual(m.answer, "A B")

    def test_empty_output_closed_code(self):
        ticks = iter([0.0, 0.5, 1.0])
        m = measure_generation(
            variant=_loopback_variant(),
            payload={},
            clock=lambda: next(ticks),
            stream_factory=lambda **_kw: iter([{"content": ""}]),
        )

        self.assertTrue(m.failed)
        self.assertEqual(m.fail_code, FailCode.EMPTY.value)
        self.assertEqual(m.answer, "")

    def test_requests_failures_are_closed_codes_and_scrub_partial_text(self):
        def gen():
            yield {"content": "FABRICATED_SENTINEL"}
            raise requests.ConnectionError("host detail")

        ticks = iter([0.0, 0.2, 0.5])
        m = measure_generation(
            variant=_loopback_variant(),
            payload={},
            clock=lambda: next(ticks),
            stream_factory=lambda **_kw: gen(),
        )

        self.assertTrue(m.failed)
        self.assertEqual(m.fail_code, FailCode.REFUSED.value)
        self.assertEqual(m.answer, "")


class BackendTests(unittest.TestCase):
    def test_ollama_stream_posts_to_api_chat(self):
        response = mock.Mock()
        response.iter_lines.return_value = [
            b'{"message":{"content":"A "}}',
            b'{"message":{"content":"B"}}',
        ]
        response.raise_for_status.return_value = None

        with mock.patch("requests.post", return_value=response) as post:
            chunks = list(ollama_stream(variant=_loopback_variant(), payload={"x": 1}))

        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "http://127.0.0.1:11434/api/chat")
        self.assertTrue(post.call_args.kwargs["stream"])
        self.assertEqual(chunks, [{"content": "A "}, {"content": "B"}])


if __name__ == "__main__":
    unittest.main()
