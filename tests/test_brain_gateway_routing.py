import asyncio
import os
from pathlib import Path
import types
import unittest
from unittest import mock

from core.routing import llm_client
from core.routing.brain_gateway import (
    BrainGateway,
    BrainPurpose,
    copy_current_context_callable,
    current_purpose,
    with_purpose,
)
from core.routing.cancellable_brain_call import CancellableBrainCall


class RoutingTest(unittest.TestCase):
    def test_llm_client_buffered_chat_uses_gateway_and_current_purpose(self):
        gateway = BrainGateway()

        def fake_start(**_kwargs):
            return CancellableBrainCall(raw_stream=iter([{"content": "gateway reply"}]))

        with (
            mock.patch("core.routing.brain_gateway.GATEWAY", gateway),
            mock.patch.object(llm_client, "start_cancellable_chat", side_effect=fake_start),
            with_purpose(BrainPurpose.OWNER_RECALL),
        ):
            response = llm_client.chat(
                model="m",
                messages=[{"role": "user", "content": "hi"}],
                think=False,
                options={"temperature": 0.1},
            )

        self.assertEqual(response.message.content, "gateway reply")
        self.assertIsNone(response.server_prompt_ms)
        self.assertEqual(gateway.events[-1]["purpose"], "owner_recall")

    def test_llm_client_buffered_chat_surfaces_socket_server_prompt_ms(self):
        gateway = BrainGateway()

        class TimedStream:
            server_prompt_ms = 1234

            def __iter__(self):
                yield {"content": "timed reply"}

        def fake_start(**_kwargs):
            return CancellableBrainCall(raw_stream=TimedStream())

        with (
            mock.patch("core.routing.brain_gateway.GATEWAY", gateway),
            mock.patch.object(llm_client, "start_cancellable_chat", side_effect=fake_start),
            with_purpose(BrainPurpose.OWNER_RECALL),
        ):
            response = llm_client.chat(
                model="m",
                messages=[{"role": "user", "content": "hi"}],
                think=False,
                options={"temperature": 0.1},
            )

        self.assertEqual(response.message.content, "timed reply")
        self.assertEqual(response.server_prompt_ms, 1234)

    def test_llm_client_stream_true_preserves_legacy_iterator_shape(self):
        legacy_stream = iter(
            [types.SimpleNamespace(message=types.SimpleNamespace(content="chunk"))]
        )
        gateway = BrainGateway()

        with (
            mock.patch.dict(os.environ, {"MAEZ_LLM_BACKEND": "ollama"}, clear=False),
            mock.patch.object(llm_client, "_chat_ollama", return_value=legacy_stream),
            mock.patch("core.routing.brain_gateway.GATEWAY", gateway),
        ):
            got = llm_client.chat(
                model="m",
                messages=[],
                stream=True,
                think=False,
                options={},
            )

        self.assertIs(got, legacy_stream)
        self.assertEqual(list(gateway.events), [])

    def test_llm_client_explicit_purpose_overrides_neutral_context(self):
        gateway = BrainGateway()

        with (
            mock.patch("core.routing.brain_gateway.GATEWAY", gateway),
            mock.patch.object(
                llm_client,
                "start_cancellable_chat",
                return_value=CancellableBrainCall(raw_stream=iter([{"content": "ok"}])),
            ),
        ):
            response = llm_client.chat(
                model="m",
                messages=[],
                think=False,
                options={},
                purpose=BrainPurpose.DAEMON_CYCLE_RETRY,
            )

        self.assertEqual(response.message.content, "ok")
        self.assertEqual(gateway.events[-1]["purpose"], "daemon_cycle_retry")

    def test_purpose_survives_run_in_executor_with_explicit_carry(self):
        async def driver():
            with with_purpose(BrainPurpose.OWNER_REPLY):
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None,
                    copy_current_context_callable(current_purpose),
                )

        self.assertEqual(asyncio.run(driver()), BrainPurpose.OWNER_REPLY)

    def test_maez_adapter_uses_gateway_context_carry_for_executor_calls(self):
        src = (Path(__file__).resolve().parents[1] / "skills" / "surface" / "maez_adapter.py").read_text()

        self.assertIn("copy_current_context_callable", src)
        self.assertGreaterEqual(src.count("with_purpose(BrainPurpose.OWNER_REPLY)"), 2)

    def test_old_dnd_and_ollama_lock_are_not_brain_lane_mechanisms(self):
        root = Path(__file__).resolve().parents[1]
        daemon_src = (root / "daemon" / "maez_daemon.py").read_text()
        wondering_src = (root / "daemon" / "wondering_cycle.py").read_text()

        self.assertNotIn("self._ollama_lock.acquire", daemon_src)
        self.assertNotIn("ollama_lock.acquire", wondering_src)
        self.assertNotIn("time.time() < self._rohit_active_until", daemon_src)

    def test_voice_stream_has_no_raw_backend_side_door(self):
        root = Path(__file__).resolve().parents[1]
        daemon_src = (root / "daemon" / "maez_daemon.py").read_text()
        voice_src = daemon_src[
            daemon_src.index("    def handle_voice_stream")
            : daemon_src.index("    def _send_morning_briefing")
        ]

        self.assertIn('self.handle_message(text, source="voice")', voice_src)
        self.assertNotIn("_llm_client.chat", voice_src)
        self.assertNotIn('with _brain_purpose("voice_reply")', voice_src)
        self.assertNotIn("_req.post", voice_src)
        self.assertNotIn("requests.post", voice_src)
        self.assertNotIn("_ollama_lock", voice_src)


if __name__ == "__main__":
    unittest.main()
