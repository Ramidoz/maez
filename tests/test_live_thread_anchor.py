import unittest
import os
from unittest import mock

from core.routing.focused_cognition import (
    ContinuityKind,
    DialogueContinuityState,
    assemble_working_set,
    live_thread_anchor_enabled,
    _ranked_items_for_state,
)


def _item(source_type):
    return (source_type, f"text-{source_type}", None, None, None, None)


def _ordinary():
    return DialogueContinuityState(
        kind=ContinuityKind.NONE,
        needs_dialogue=False,
        fail_safe_legacy=False,
    )


def _ranked_types(items, state):
    return [item[0] for item in _ranked_items_for_state(items, state)]


class TestAnchorRankingOrdinary(unittest.TestCase):
    def test_anchor_is_figure_when_no_fresh(self):
        order = _ranked_types(
            [_item("memory_evidence"), _item("dialogue_anchor")],
            _ordinary(),
        )
        self.assertEqual(order[0], "dialogue_anchor")

    def test_fresh_evidence_outranks_anchor(self):
        order = _ranked_types(
            [_item("dialogue_anchor"), _item("fresh_evidence")],
            _ordinary(),
        )
        self.assertEqual(order[0], "fresh_evidence")

    def test_web_context_outranks_anchor(self):
        order = _ranked_types(
            [_item("dialogue_anchor"), _item("web_context")],
            _ordinary(),
        )
        self.assertEqual(order[0], "web_context")

    def test_anchor_above_memory(self):
        order = _ranked_types(
            [_item("memory_context"), _item("dialogue_anchor")],
            _ordinary(),
        )
        self.assertLess(
            order.index("dialogue_anchor"),
            order.index("memory_context"),
        )


class TestAnchorRankingDirect(unittest.TestCase):
    def _direct(self):
        return DialogueContinuityState(
            kind=ContinuityKind.DIRECT,
            needs_dialogue=True,
            fail_safe_legacy=False,
        )

    def test_direct_fresh_still_outranks_anchor(self):
        order = _ranked_types(
            [_item("dialogue_anchor"), _item("fresh_evidence")],
            self._direct(),
        )
        self.assertEqual(order[0], "fresh_evidence")

    def test_direct_web_still_outranks_anchor(self):
        order = _ranked_types(
            [_item("dialogue_anchor"), _item("web_context")],
            self._direct(),
        )
        self.assertEqual(order[0], "web_context")

class TestAnchorFlag(unittest.TestCase):
    def test_flag_off_by_default(self):
        self.assertFalse(live_thread_anchor_enabled(env={}))

    def test_flag_on(self):
        self.assertTrue(
            live_thread_anchor_enabled(env={"MAEZ_LIVE_THREAD_ANCHOR": "1"})
        )


class TestAnchorUngate(unittest.TestCase):
    _history = [
        {
            "content": (
                "Rohit: I'll search Fable 5\n"
                "Maez: Say the word and I'll search it."
            )
        }
    ]

    def test_flag_off_ordinary_turn_has_no_anchor(self):
        with mock.patch.dict(os.environ, {"MAEZ_LIVE_THREAD_ANCHOR": "0"}):
            ws = assemble_working_set(
                transcript="[memory evidence] old note",
                web_context="",
                owner_question="sure",
                chat_history=self._history,
            )
        labels = [it.source_type for it in (ws.items if ws else [])]
        self.assertNotIn("dialogue_anchor", labels)

    def test_flag_on_ordinary_turn_has_anchor_as_figure(self):
        with mock.patch.dict(os.environ, {"MAEZ_LIVE_THREAD_ANCHOR": "1"}):
            ws = assemble_working_set(
                transcript="[memory evidence] old note",
                web_context="",
                owner_question="sure",
                chat_history=self._history,
            )
        self.assertIsNotNone(ws)
        assert ws is not None
        labels = [it.source_type for it in ws.items]
        self.assertIn("dialogue_anchor", labels)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")

    def test_direct_turn_with_web_keeps_web_as_figure(self):
        with mock.patch.dict(os.environ, {"MAEZ_LIVE_THREAD_ANCHOR": "1"}):
            ws = assemble_working_set(
                transcript="[memory evidence] old note",
                web_context="- current web result",
                owner_question="what were we talking about earlier?",
                chat_history=self._history,
            )
        self.assertIsNotNone(ws)
        assert ws is not None
        labels = [it.source_type for it in ws.items]
        self.assertIn("web_context", labels)
        self.assertIn("dialogue_anchor", labels)
        self.assertEqual(ws.items[0].source_type, "web_context")

    def test_direct_turn_with_fresh_keeps_fresh_as_figure(self):
        with mock.patch.dict(os.environ, {"MAEZ_LIVE_THREAD_ANCHOR": "1"}):
            ws = assemble_working_set(
                transcript="[fresh evidence]\n- current sensor result",
                web_context="",
                owner_question="what were we talking about earlier?",
                chat_history=self._history,
            )
        self.assertIsNotNone(ws)
        assert ws is not None
        labels = [it.source_type for it in ws.items]
        self.assertIn("fresh_evidence", labels)
        self.assertIn("dialogue_anchor", labels)
        self.assertEqual(ws.items[0].source_type, "fresh_evidence")


if __name__ == "__main__":
    unittest.main()
