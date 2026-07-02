import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _RawGet:
    def __init__(self, documents, metadatas=None):
        self.documents = list(documents)
        self.metadatas = list(metadatas or [{} for _ in self.documents])

    def get(self, *, limit=None, include=None):
        docs = self.documents[:limit] if limit is not None else list(self.documents)
        metas = self.metadatas[: len(docs)]
        out = {"documents": docs}
        if include and "metadatas" in include:
            out["metadatas"] = metas
        return out


class DurableOnlyConsumerDietTests(unittest.TestCase):
    def test_dream_skips_when_durable_recent_raw_below_threshold(self):
        from core.evolution.dream_state import DreamState

        memory = mock.Mock()
        memory.recent_raw.return_value = {
            "documents": [f"durable event {i}" for i in range(5)],
            "metadatas": [{} for _ in range(5)],
        }
        with tempfile.TemporaryDirectory() as td:
            dream = DreamState(
                memory=memory,
                telegram=None,
                action_engine=mock.Mock(),
                db_path=str(Path(td) / "dream.db"),
            )
            with mock.patch("core.llm_client.chat") as chat:
                self.assertIsNone(dream.run_dream_cycle())
        chat.assert_not_called()
        memory.recent_raw.assert_called_once()

    def test_proactive_opinion_skips_when_durable_window_below_threshold(self):
        from daemon.maez_daemon import MaezDaemon

        daemon = mock.Mock()
        daemon.memory.raw = _RawGet([f"durable event {i}" for i in range(5)])
        daemon._send_telegram_notice = mock.Mock()
        daemon._build_evidence_envelope = mock.Mock()
        MaezDaemon._check_proactive_opinion(daemon)
        daemon._send_telegram_notice.assert_not_called()
        daemon._build_evidence_envelope.assert_not_called()

    def test_self_analysis_counts_the_durable_rows_it_receives(self):
        from skills.self_analysis import analyze

        memory = mock.Mock()
        memory.raw = _RawGet(
            ["GPU temperature changed", "Rohit present at desk"],
            [{"timestamp": "2026-07-02T01:00:00+00:00"}, {}],
        )
        result = analyze(memory)
        self.assertEqual(result["total_memories_analyzed"], 2)
        self.assertEqual(result["topic_distribution"]["gpu"], 1)
        self.assertEqual(result["topic_distribution"]["presence"], 1)
