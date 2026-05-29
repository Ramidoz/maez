from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory

from core.routing.focused_cognition import assemble_working_set


_FRESH = (
    "[fresh evidence] LIVE_REDDIT r/LocalLLaMA:\n"
    "- LiquidAI/LFM2.5-8B-A1B - Hugging Face (67 pts)\n"
    "- Reachy Mini goes fully local! (142 pts)"
)
_SUBSTRATE = (
    "[memory context] Recent Reddit substrate rows:\n"
    "- Zai replaced the network architecture running GLM-5.1 inference (310 pts)"
)


class AssembleWorkingSetTests(unittest.TestCase):
    def test_extracts_atomic_items_with_ids_and_durable_id(self):
        ws = assemble_working_set(
            transcript=_SUBSTRATE,
            web_context="",
            owner_question="what's new on r/LocalLLaMA",
        )
        self.assertIsNotNone(ws)
        self.assertEqual(len(ws.items), 1)
        item = ws.items[0]
        self.assertEqual(item.local_label, "E1")
        self.assertEqual(item.source_type, "memory_context")
        self.assertTrue(item.durable_id)
        self.assertIn("[E1]", ws.ordered_evidence_text)

    def test_excludes_empty_and_background(self):
        ws = assemble_working_set(
            transcript="[no fresh evidence available: LIVE_REDDIT:EMPTY:NONE:FRESH_ATTEMPT_FAILED]",
            web_context="",
            owner_question="search r/x",
        )
        self.assertIsNone(ws)

    def test_source_priority_fresh_before_substrate(self):
        ws = assemble_working_set(
            transcript=f"{_SUBSTRATE}\n{_FRESH}",
            web_context="",
            owner_question="q",
        )
        self.assertEqual(ws.items[0].source_type, "fresh_evidence")
        self.assertEqual(ws.items[-1].source_type, "memory_context")

    def test_parser_boundary_blocks_do_not_bleed(self):
        ws = assemble_working_set(
            transcript=f"{_FRESH}\n{_SUBSTRATE}",
            web_context="",
            owner_question="q",
        )
        fresh_items = [i for i in ws.items if i.source_type == "fresh_evidence"]
        self.assertFalse(any("GLM-5.1" in i.text for i in fresh_items))

    def test_tail_repeat_same_id_no_double_count(self):
        ws = assemble_working_set(
            transcript=f"{_FRESH}\n{_SUBSTRATE}",
            web_context="",
            owner_question="q",
        )
        labels = [i.local_label for i in ws.items]
        self.assertEqual(len(labels), len(set(labels)))
        top = ws.items[0].local_label
        self.assertGreaterEqual(ws.ordered_evidence_text.count(f"[{top}]"), 2)

    def test_web_context_results_vs_no_results(self):
        present = assemble_working_set(
            transcript="",
            web_context="[WEB SEARCH: 'x'] 2 results - 2026\n  1. Post\n     body",
            owner_question="q",
        )
        self.assertIsNotNone(present)
        absent = assemble_working_set(
            transcript="",
            web_context="[WEB SEARCH: 'x'] No results found.",
            owner_question="q",
        )
        self.assertIsNone(absent)

    def test_intra_turn_echo_with_stale_evidence_returns_none(self):
        ws = assemble_working_set(
            transcript="[memory evidence] stale:\n- April 6 journal",
            web_context="",
            owner_question=(
                "For the continuity witness: dialogue anchors now strip stale "
                "prior citations before they become current evidence. Say that "
                "back in one sentence."
            ),
            chat_history=[
                {
                    "content": (
                        "Rohit: previous continuity probe\n"
                        "Maez: previous continuity answer"
                    )
                }
            ],
        )
        self.assertIsNone(ws)


class DialogueContinuityStateTests(unittest.TestCase):
    def test_direct_continuity_state(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        examples = [
            "What were we talking about earlier?",
            "What did we just discuss?",
            "What was the last thing I said?",
            "What did you say before this?",
        ]
        for text in examples:
            with self.subTest(text=text):
                state = dialogue_continuity_state(text)
                self.assertEqual(state.kind, ContinuityKind.DIRECT)
                self.assertTrue(state.needs_dialogue)
                self.assertFalse(state.fail_safe_legacy)

    def test_anaphoric_continuity_state(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        examples = [
            "Which one matters most?",
            "Try that.",
            "Why does that matter?",
            "What about those?",
        ]
        for text in examples:
            with self.subTest(text=text):
                state = dialogue_continuity_state(text)
                self.assertEqual(state.kind, ContinuityKind.ANAPHORIC)
                self.assertTrue(state.needs_dialogue)
                self.assertFalse(state.fail_safe_legacy)

    def test_conservative_uncertain_continuity_state(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        state = dialogue_continuity_state("Anything since we were talking?")
        self.assertEqual(state.kind, ContinuityKind.NONE)
        self.assertFalse(state.needs_dialogue)
        self.assertTrue(state.fail_safe_legacy)
        self.assertIn("we were", state.matched_reason or "")

    def test_bare_temporal_freshness_queries_are_not_continuity(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        examples = [
            "what are the last 5 posts on r/LocalLLaMA",
            "any news before the launch",
            "Anything since earlier?",
        ]
        for text in examples:
            with self.subTest(text=text):
                state = dialogue_continuity_state(text)
                self.assertEqual(state.kind, ContinuityKind.NONE)
                self.assertFalse(state.needs_dialogue)
                self.assertFalse(state.fail_safe_legacy)
                self.assertIsNone(state.matched_reason)

    def test_recent_freshness_query_is_not_continuity(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        state = dialogue_continuity_state(
            "Search r/LocalLLaMA right now for recent local LLM posts."
        )
        self.assertEqual(state.kind, ContinuityKind.NONE)
        self.assertFalse(state.needs_dialogue)
        self.assertFalse(state.fail_safe_legacy)
        self.assertIsNone(state.matched_reason)

    def test_intra_turn_echo_instruction_is_not_anaphoric_continuity(self):
        from core.routing.focused_cognition import (
            ContinuityKind,
            dialogue_continuity_state,
        )

        state = dialogue_continuity_state(
            "For the continuity witness: dialogue anchors now strip stale prior "
            "citations before they become current evidence. Say that back in "
            "one sentence."
        )
        self.assertEqual(state.kind, ContinuityKind.NONE)
        self.assertFalse(state.needs_dialogue)
        self.assertFalse(state.fail_safe_legacy)
        self.assertIsNone(state.matched_reason)


class DialogueAnchorTests(unittest.TestCase):
    def test_dialogue_anchor_reuses_history_to_messages(self):
        from unittest import mock

        from core.routing import focused_cognition

        with mock.patch(
            "core.brain.conversation_history.history_to_messages",
            return_value=[
                {"role": "user", "content": "Search r/LocalLLaMA"},
                {"role": "assistant", "content": "I found LiquidAI [E1]."},
            ],
        ) as parser:
            items = focused_cognition.dialogue_anchor_items(
                [{"content": "ignored because parser is patched"}],
                limit_pairs=3,
            )

        parser.assert_called_once()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_type, "dialogue_anchor")
        self.assertIn("User: Search r/LocalLLaMA", items[0].text)
        self.assertIn("Maez: I found LiquidAI", items[0].text)
        self.assertTrue(items[0].durable_id.startswith("ch_"))

    def test_dialogue_anchor_limits_to_recent_pairs(self):
        from core.routing.focused_cognition import dialogue_anchor_items

        history = [
            {"content": "Rohit: first\nMaez: one"},
            {"content": "Rohit: second\nMaez: two"},
            {"content": "Rohit: third\nMaez: three"},
            {"content": "Rohit: fourth\nMaez: four"},
        ]
        items = dialogue_anchor_items(history, limit_pairs=2)
        self.assertEqual(len(items), 2)
        joined = "\n".join(item.text for item in items)
        self.assertNotIn("first", joined)
        self.assertNotIn("one", joined)
        self.assertIn("third", joined)
        self.assertIn("fourth", joined)

    def test_dialogue_anchor_orders_newest_pair_first(self):
        from core.routing.focused_cognition import dialogue_anchor_items

        history = [
            {"content": "Rohit: first\nMaez: one"},
            {"content": "Rohit: second\nMaez: two"},
            {"content": "Rohit: third\nMaez: three"},
            {"content": "Rohit: fourth\nMaez: four"},
        ]
        items = dialogue_anchor_items(history, limit_pairs=3)
        self.assertEqual(len(items), 3)
        self.assertIn("fourth", items[0].text)
        self.assertIn("three", items[1].text)
        self.assertIn("second", items[2].text)

    def test_dialogue_anchor_strips_stale_local_citations(self):
        from core.routing.focused_cognition import dialogue_anchor_items

        history = [
            {
                "content": (
                    "Rohit: What were we talking about earlier?\n"
                    "Maez: We were discussing continuity [E1]. "
                    "The old row said the same thing [E3]."
                )
            }
        ]

        items = dialogue_anchor_items(history, limit_pairs=1)

        self.assertEqual(len(items), 1)
        self.assertIn("We were discussing continuity.", items[0].text)
        self.assertIn("The old row said the same thing.", items[0].text)
        self.assertNotIn("[E1]", items[0].text)
        self.assertNotIn("[E3]", items[0].text)


class DialogueAwareAssembleTests(unittest.TestCase):
    def _history(self):
        return [
            {
                "content": (
                    "Rohit: Search r/LocalLLaMA right now\n"
                    "Maez: LiquidAI and Reachy Mini were the active threads."
                )
            }
        ]

    def test_direct_continuity_prioritizes_dialogue_over_stale_memory(self):
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="What were we talking about earlier?",
            chat_history=self._history(),
        )
        self.assertIsNotNone(ws)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")
        self.assertIn("Search r/LocalLLaMA", ws.items[0].text)
        self.assertGreaterEqual(
            ws.ordered_evidence_text.count(f"[{ws.items[0].local_label}]"),
            2,
        )
        self.assertEqual(len(ws.items), 1)

    def test_direct_continuity_keeps_only_newest_dialogue_anchor(self):
        history = [
            {
                "content": (
                    "Rohit: What were we talking about earlier?\n"
                    "Maez: I only have the April 6 journal."
                )
            },
            {
                "content": (
                    "Rohit: For the continuity witness: bare temporal words "
                    "are freshness.\n"
                    "Maez: Bare temporal words are freshness, and newest "
                    "dialogue anchors come first."
                )
            },
        ]
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="What were we talking about earlier?",
            chat_history=history,
        )
        self.assertIsNotNone(ws)
        assert ws is not None
        dialogue_items = [
            item for item in ws.items if item.source_type == "dialogue_anchor"
        ]
        self.assertEqual(len(dialogue_items), 1)
        self.assertIn("bare temporal words are freshness", dialogue_items[0].text)
        self.assertNotIn("I only have the April 6 journal", dialogue_items[0].text)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")
        self.assertEqual(len(ws.items), 1)

    def test_direct_continuity_without_anchor_returns_none(self):
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="What were we talking about earlier?",
            chat_history=[],
        )
        self.assertIsNone(ws)

    def test_uncertain_continuity_without_anchor_returns_none_even_with_stale_evidence(
        self,
    ):
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="Anything since we were talking?",
            chat_history=[],
        )
        self.assertIsNone(ws)

    def test_uncertain_continuity_with_anchor_prioritizes_dialogue(self):
        ws = assemble_working_set(
            transcript="[memory evidence] stale journal:\n- April 6 journaling note",
            web_context="",
            owner_question="Anything since we were talking?",
            chat_history=self._history(),
        )
        self.assertIsNotNone(ws)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")

    def test_anaphoric_uses_only_newest_dialogue_anchor(self):
        history = [
            {
                "content": (
                    "Rohit: For the continuity witness: bare temporal words "
                    "are freshness.\n"
                    "Maez: Bare temporal words are freshness, and newest "
                    "dialogue anchors come first."
                )
            },
            {
                "content": (
                    "Rohit: What were we talking about earlier?\n"
                    "Maez: We were discussing the direct-continuity fix."
                )
            },
        ]
        ws = assemble_working_set(
            transcript=_FRESH,
            web_context="",
            owner_question="Which one matters most?",
            chat_history=history,
        )
        self.assertIsNotNone(ws)
        assert ws is not None
        self.assertEqual(len(ws.items), 1)
        self.assertEqual(ws.items[0].source_type, "dialogue_anchor")
        self.assertIn("direct-continuity fix", ws.items[0].text)
        self.assertNotIn("bare temporal words are freshness", ws.items[0].text)

    def test_normal_evidence_excludes_dialogue_anchor(self):
        ws = assemble_working_set(
            transcript=_FRESH,
            web_context="",
            owner_question="Search r/LocalLLaMA right now for recent local LLM posts.",
            chat_history=self._history(),
        )
        self.assertIsNotNone(ws)
        self.assertFalse(
            any(item.source_type == "dialogue_anchor" for item in ws.items)
        )


class FocusedSynthesizeTests(unittest.TestCase):
    def _ws(self):
        return assemble_working_set(
            transcript=_FRESH,
            web_context="",
            owner_question="what's new on r/LocalLLaMA",
        )

    def test_builds_bounded_injectable_messages(self):
        from core.routing.focused_cognition import focused_synthesize

        captured = {}

        def fake_chat(*, model, messages, think, options):
            captured["model"] = model
            captured["messages"] = messages
            captured["think"] = think
            captured["options"] = options

            class _Response:
                class message:
                    content = "Notable: [E1] LiquidAI's tiny MoE."

            return _Response()

        result = focused_synthesize(self._ws(), surface="telegram", chat_fn=fake_chat)

        from core.model_config import PRIMARY_MODEL

        self.assertEqual(captured["model"], PRIMARY_MODEL)
        self.assertFalse(captured["think"])
        self.assertEqual(captured["options"]["temperature"], 0.7)
        roles = [message["role"] for message in captured["messages"]]
        self.assertEqual(roles, ["system", "user"])
        system = captured["messages"][0]["content"]
        self.assertIn("[E1]", system)
        self.assertNotIn("HARD CONSTRAINTS", system)
        for banned in ("DuckDuckGo", "interceptor", "tool loop", "blocked"):
            self.assertNotIn(banned, system)
        self.assertLess(len(system), 2000)
        self.assertIn("E1", result.cited_ids)


class GroundednessTests(unittest.TestCase):
    def _ws(self):
        return assemble_working_set(transcript=_FRESH, web_context="", owner_question="q")

    def test_overlap_verdicts(self):
        from core.routing.focused_cognition import (
            FocusedResult,
            check_groundedness,
        )

        ws = self._ws()
        grounded = check_groundedness(
            FocusedResult("uses [E1] and [E2]", ["E1", "E2"], 0),
            ws,
        )
        self.assertEqual(grounded.verdict, "grounded")

        unmatched = check_groundedness(
            FocusedResult("cites [E9]", ["E9"], 0),
            ws,
        )
        self.assertEqual(unmatched.verdict, "unmatched_citation")

        none = check_groundedness(FocusedResult("no tags here", [], 0), ws)
        self.assertEqual(none.verdict, "no_citations")


class FocusedCognitionStoreTests(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self.addCleanup(self._td.cleanup)

    def _store(self):
        from pathlib import Path

        from core.routing.focused_cognition import FocusedCognitionStore

        return FocusedCognitionStore(db_path=Path(self._td.name) / "focused.db")

    def test_schema_and_roundtrip(self):
        from core.routing.focused_cognition import (
            FocusedResult,
            GroundednessVerdict,
        )

        store = self._store()
        ws = assemble_working_set(transcript=_FRESH, web_context="", owner_question="q")
        row_id = store.record(
            surface="telegram",
            chat_id="c1",
            working_set=ws,
            result=FocusedResult("uses [E1]", ["E1"], ws.working_set_chars),
            verdict=GroundednessVerdict("grounded", 0.5, []),
            legacy_prompt_chars=104000,
            fallback_reason=None,
            routing_observation_id=None,
        )
        row = store.get(row_id)
        self.assertEqual(row["groundedness_verdict"], "grounded")
        self.assertEqual(row["legacy_prompt_chars"], 104000)
        self.assertLess(row["working_set_chars"], row["legacy_prompt_chars"])
        self.assertIn("evidence_map_json", row.keys())

    def test_stores_no_raw_evidence_text(self):
        import sqlite3

        from core.routing.focused_cognition import (
            FocusedResult,
            GroundednessVerdict,
        )

        store = self._store()
        secret = "REACHY_SECRET_MARKER_XYZ"
        ws = assemble_working_set(
            transcript=f"[fresh evidence] X:\n- {secret} (1 pts)",
            web_context="",
            owner_question="q",
        )
        store.record(
            surface="telegram",
            chat_id="c1",
            working_set=ws,
            result=FocusedResult("ok [E1]", ["E1"], ws.working_set_chars),
            verdict=GroundednessVerdict("grounded", 1.0, []),
            legacy_prompt_chars=104000,
            fallback_reason=None,
            routing_observation_id=None,
        )
        conn = sqlite3.connect(store.db_path)
        try:
            rows = conn.execute("SELECT * FROM focused_cognition_runs").fetchall()
        finally:
            conn.close()
        stored = " ".join(str(row) for row in rows)
        self.assertNotIn(secret, stored)

    def test_dialogue_anchor_trace_stores_no_raw_dialogue_text(self):
        import sqlite3

        from core.routing.focused_cognition import (
            FocusedResult,
            GroundednessVerdict,
        )

        store = self._store()
        secret = "DIALOGUE_SECRET_MARKER_ABC"
        ws = assemble_working_set(
            transcript="",
            web_context="",
            owner_question="What were we talking about earlier?",
            chat_history=[
                {
                    "content": (
                        f"Rohit: {secret}\n"
                        "Maez: We were discussing local models."
                    )
                }
            ],
        )
        self.assertIsNotNone(ws)
        store.record(
            surface="telegram",
            chat_id="c1",
            working_set=ws,
            result=FocusedResult(
                "We were discussing local models [E1]",
                ["E1"],
                ws.working_set_chars,
            ),
            verdict=GroundednessVerdict("grounded", 1.0, []),
            legacy_prompt_chars=104000,
            fallback_reason=None,
            routing_observation_id=None,
        )
        conn = sqlite3.connect(store.db_path)
        try:
            rows = conn.execute("SELECT * FROM focused_cognition_runs").fetchall()
        finally:
            conn.close()
        stored = " ".join(str(row) for row in rows)
        self.assertNotIn(secret, stored)
        self.assertIn("dialogue_anchor", stored)


if __name__ == "__main__":
    unittest.main()
