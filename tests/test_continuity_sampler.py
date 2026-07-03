import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


class FakeEncoder:
    model = "fake-minilm"
    dimension = 3

    def __init__(self):
        self.encoded = []

    def encode(self, text: str) -> list[float]:
        self.encoded.append(text)
        return [1.0, 0.0, 0.0]


class SamplerTests(unittest.TestCase):
    def test_flag_off_is_noop(self):
        from core.continuity_fingerprint import sampler

        store = mock.Mock()
        chat_fn = mock.Mock()
        with mock.patch.dict(os.environ, {"MAEZ_CONTINUITY_FINGERPRINT": "0"}):
            result = sampler.run_probe_battery(
                chat_fn=chat_fn,
                encoder=FakeEncoder(),
                store=store,
            )

        self.assertEqual(result["status"], "disabled")
        chat_fn.assert_not_called()
        store.record_run.assert_not_called()

    def test_run_uses_clean_envelope_question_prompt_and_stores_answers(self):
        from core.continuity_fingerprint import sampler
        from core.continuity_fingerprint.probes import BATTERY
        from core.continuity_fingerprint.store import ContinuityStore

        calls = []

        def chat_fn(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                message=SimpleNamespace(content=f"answer-{len(calls)}")
            )

        encoder = FakeEncoder()
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(
            os.environ, {"MAEZ_CONTINUITY_FINGERPRINT": "1"}
        ):
            store = ContinuityStore(Path(td) / "continuity_fingerprint.db")
            result = sampler.run_probe_battery(
                chat_fn=chat_fn,
                encoder=encoder,
                store=store,
            )
            answers = store.answers_for(result["run_id"])

        self.assertEqual(result["status"], "recorded")
        self.assertGreater(len(calls), 0)
        first_messages = calls[0]["messages"]
        self.assertEqual([m["role"] for m in first_messages], ["system", "user"])
        self.assertNotIn("=== EVIDENCE", first_messages[0]["content"])
        self.assertNotIn("RECENT DIALOGUE", first_messages[0]["content"])
        self.assertEqual(first_messages[1]["content"], BATTERY[0].text)
        self.assertEqual(len(answers), len(calls))
        self.assertIsNone(answers[0]["dist_short"])

    def test_terminal_sink_does_not_call_memory_or_capsule_writers(self):
        from core.continuity_fingerprint import sampler
        from core.continuity_fingerprint.store import ContinuityStore

        def chat_fn(**_kwargs):
            return SimpleNamespace(message=SimpleNamespace(content="quiet answer"))

        with (
            tempfile.TemporaryDirectory() as td,
            mock.patch.dict(os.environ, {"MAEZ_CONTINUITY_FINGERPRINT": "1"}),
            mock.patch("core.memory.episodes.EpisodeStore.add") as episode_add,
            mock.patch("core.memory.continuity.write_capsule") as write_capsule,
            mock.patch("memory.memory_manager.MemoryManager.store") as recall_store,
        ):
            store = ContinuityStore(Path(td) / "continuity_fingerprint.db")
            result = sampler.run_probe_battery(
                chat_fn=chat_fn,
                encoder=FakeEncoder(),
                store=store,
            )

        self.assertEqual(result["status"], "recorded")
        episode_add.assert_not_called()
        write_capsule.assert_not_called()
        recall_store.assert_not_called()


if __name__ == "__main__":
    unittest.main()
