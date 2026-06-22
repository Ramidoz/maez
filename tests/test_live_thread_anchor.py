import unittest

from core.routing.focused_cognition import (
    ContinuityKind,
    DialogueContinuityState,
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


if __name__ == "__main__":
    unittest.main()
