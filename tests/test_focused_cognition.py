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

        state = dialogue_continuity_state("Anything since earlier?")
        self.assertEqual(state.kind, ContinuityKind.NONE)
        self.assertFalse(state.needs_dialogue)
        self.assertTrue(state.fail_safe_legacy)
        self.assertIn("earlier", state.matched_reason or "")


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


if __name__ == "__main__":
    unittest.main()
