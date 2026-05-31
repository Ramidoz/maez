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
from scripts.brain_bench.inference_backend import openai_compat_stream, ollama_stream
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
        "backend_family": "ollama",
        "base_url": "http://127.0.0.1:11434",
        "model": "bench-model",
        "chat_kwargs": {"temperature": 0.2, "num_predict": 99},
        "ops": _ops_config(),
    }
    data.update(overrides)
    return load_variants(json.dumps([data]))[0]


def _llamacpp_variant(**overrides):
    data = {
        "label": "llama",
        "backend_family": "openai_compatible",
        "base_url": "http://127.0.0.1:8080",
        "model": "qwen36-27b",
        "chat_kwargs": {"temperature": 0.3, "num_predict": 64},
        "ops": _ops_config(api_family="llama_cpp", topology="separate_server"),
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

    def test_adapter_dispatches_llamacpp_variants_to_openai_compat_endpoint(self):
        response = mock.Mock()
        response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"April "}}]}',
            b'data: {"choices":[{"delta":{"content":"27 [E1]"}}]}',
            b"data: [DONE]",
        ]
        response.raise_for_status.return_value = None

        with mock.patch("requests.Session") as session_factory:
            session = session_factory.return_value
            session.post.return_value = response
            chat_fn, measurements = make_benchmark_chat_fn(variant=_llamacpp_variant())
            out = chat_fn(
                model="ignored-by-adapter",
                messages=[{"role": "user", "content": "q"}],
                think=False,
                options={"num_predict": 256},
            )

        self.assertFalse(session.trust_env)
        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.args[0], "http://127.0.0.1:8080/v1/chat/completions")
        sent = session.post.call_args.kwargs["json"]
        self.assertEqual(sent["model"], "qwen36-27b")
        self.assertEqual(sent["messages"], [{"role": "user", "content": "q"}])
        self.assertTrue(sent["stream"])
        self.assertEqual(sent["temperature"], 0.3)
        self.assertEqual(sent["max_tokens"], 256)
        self.assertEqual(out.message.content, "April 27 [E1]")
        self.assertEqual(measurements.last().answer, "April 27 [E1]")

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

        with mock.patch("requests.Session") as session_factory:
            session = session_factory.return_value
            session.post.return_value = response
            chunks = list(ollama_stream(variant=_loopback_variant(), payload={"x": 1}))

        self.assertFalse(session.trust_env)
        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.args[0], "http://127.0.0.1:11434/api/chat")
        self.assertTrue(session.post.call_args.kwargs["stream"])
        self.assertEqual(chunks, [{"content": "A "}, {"content": "B"}])

    def test_openai_compat_stream_posts_to_v1_chat_completions(self):
        response = mock.Mock()
        response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"A "}}]}',
            b'{"choices":[{"delta":{"content":"B"}}]}',
            b"data: [DONE]",
        ]
        response.raise_for_status.return_value = None

        payload = {
            "model": "ignored",
            "messages": [{"role": "user", "content": "q"}],
            "stream": True,
            "think": False,
            "options": {"temperature": 0.2, "num_predict": 77},
        }
        with mock.patch("requests.Session") as session_factory:
            session = session_factory.return_value
            session.post.return_value = response
            chunks = list(openai_compat_stream(variant=_llamacpp_variant(), payload=payload))

        self.assertFalse(session.trust_env)
        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.args[0], "http://127.0.0.1:8080/v1/chat/completions")
        sent = session.post.call_args.kwargs["json"]
        self.assertEqual(sent["model"], "qwen36-27b")
        self.assertEqual(sent["messages"], [{"role": "user", "content": "q"}])
        self.assertTrue(sent["stream"])
        self.assertEqual(sent["temperature"], 0.2)
        self.assertEqual(sent["max_tokens"], 77)
        self.assertNotIn("extra_body", sent)
        self.assertEqual(sent["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(chunks, [{"content": "A "}, {"content": "B"}])

    def test_openai_compat_flattens_openai_client_extra_body_for_raw_http(self):
        response = mock.Mock()
        response.iter_lines.return_value = [b'data: {"choices":[{"delta":{"content":"A"}}]}']
        response.raise_for_status.return_value = None

        payload = {
            "messages": [{"role": "user", "content": "q"}],
            "think": False,
            "options": {
                "extra_body": {
                    "chat_template_kwargs": {"custom": "ok"},
                    "model": "wrong-model",
                    "messages": [{"role": "user", "content": "wrong"}],
                    "stream": False,
                },
            },
        }
        with mock.patch("requests.Session") as session_factory:
            session = session_factory.return_value
            session.post.return_value = response
            list(openai_compat_stream(variant=_llamacpp_variant(), payload=payload))

        sent = session.post.call_args.kwargs["json"]
        self.assertNotIn("extra_body", sent)
        self.assertEqual(sent["model"], "qwen36-27b")
        self.assertEqual(sent["messages"], [{"role": "user", "content": "q"}])
        self.assertTrue(sent["stream"])
        self.assertEqual(sent["chat_template_kwargs"], {"custom": "ok", "enable_thinking": False})


if __name__ == "__main__":
    unittest.main()
