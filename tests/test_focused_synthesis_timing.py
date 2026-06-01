import time
import unittest
from types import SimpleNamespace

from core.routing.focused_cognition import focused_synthesize


class _WS:
    def __init__(self, question, evidence_text, chars, render_version):
        self.owner_question = question
        self.ordered_evidence_text = evidence_text
        self.working_set_chars = chars
        self.citation_render_version = render_version
        self.items = (SimpleNamespace(local_label="E1", source_type="memory_context"),)


class FocusedSynthesisTimingTest(unittest.TestCase):
    def _ws(self):
        return _WS(
            "what did we note on April 27?",
            "[E1] April 27 note",
            4242,
            "v1",
        )

    def _chat_fn(self, reply_text):
        def fn(*, model, messages, think=False, options=None):
            return SimpleNamespace(message=SimpleNamespace(content=reply_text))

        return fn

    def test_reply_and_cited_ids_byte_stable(self):
        reply = "\n On April 27 we noted the incident [E1].  "
        res = focused_synthesize(
            self._ws(),
            surface="telegram",
            chat_fn=self._chat_fn(reply),
        )
        self.assertEqual(res.reply, reply.strip())
        self.assertEqual(res.cited_ids, ["E1"])

    def test_timing_fields_populated(self):
        res = focused_synthesize(
            self._ws(),
            surface="telegram",
            chat_fn=self._chat_fn("reply [E1]"),
        )
        self.assertIsInstance(res.prompt_build_ms, int)
        self.assertIsInstance(res.chat_total_ms, int)
        self.assertIsInstance(res.reply_token_est, int)
        self.assertGreaterEqual(res.prompt_build_ms, 0)
        self.assertGreaterEqual(res.chat_total_ms, 0)

    def test_chat_total_dominates_on_slow_chat_fn(self):
        def slow_fn(*, model, messages, think=False, options=None):
            time.sleep(0.05)
            return SimpleNamespace(message=SimpleNamespace(content="reply [E1]"))

        res = focused_synthesize(self._ws(), surface="telegram", chat_fn=slow_fn)
        self.assertGreater(res.chat_total_ms, res.prompt_build_ms)
