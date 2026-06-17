from types import SimpleNamespace
import unittest
from unittest import mock


class VoiceSharedSpineTests(unittest.TestCase):
    def test_voice_stream_uses_shared_handle_message_spine_for_synthesis(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = MaezDaemon.__new__(MaezDaemon)
        daemon.system_prompt = "system"
        daemon.memory = SimpleNamespace(
            store_telegram=lambda *args, **kwargs: None,
        )
        daemon._ws_broadcast = lambda *_args, **_kwargs: None

        calls = []

        def fake_handle_message(text, source="unknown", **kwargs):
            calls.append((text, source, kwargs))
            return "shared audited reply."

        daemon.handle_message = fake_handle_message

        spoken = []
        direct_llm_response = SimpleNamespace(
            message=SimpleNamespace(content="direct private voice reply.")
        )

        with (
            mock.patch("skills.voice_output.feed_sentence", side_effect=spoken.append),
            mock.patch("core.llm_client.chat", return_value=direct_llm_response),
        ):
            reply = daemon.handle_voice_stream("hello")

        self.assertEqual(reply, "shared audited reply.")
        self.assertEqual(calls[0][0], "hello")
        self.assertEqual(calls[0][1], "voice")
        self.assertEqual(spoken, ["shared audited reply."])


if __name__ == "__main__":
    unittest.main()
