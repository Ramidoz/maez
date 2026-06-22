from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock


def _response(text: str):
    return SimpleNamespace(message=SimpleNamespace(content=text))


def _working_set(*, source_type: str = "dialogue_anchor"):
    from core.routing.focused_cognition import EvidenceItem, WorkingSet

    return WorkingSet(
        items=[
            EvidenceItem(
                local_label="E1",
                source_type=source_type,
                text="User: how are you?\nMaez: I am here.",
                durable_id="anchor-1",
            )
        ],
        ordered_evidence_text="[E1] diary flood should not appear",
        owner_question="how are you?",
        working_set_chars=55,
        working_set_tokens_est=13,
        citation_render_version="v2",
    )


class LeanConversationPathTests(unittest.TestCase):
    def tearDown(self):
        for key in (
            "MAEZ_LEAN_CONVERSATION_SHADOW",
            "MAEZ_LEAN_CONVERSATION_ENABLED",
            "MAEZ_EVIDENCE_PRECEDENCE_ENABLED",
        ):
            os.environ.pop(key, None)

    def test_shadow_logs_eligible_but_keeps_full_prompt(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_SHADOW"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        with self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
                date_addressed=False,
                legacy_prompt_chars=3200,
                turn_kind="ordinary",
            )

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])
        joined = "\n".join(logs.output)
        self.assertIn("lean_conversation_shadow", joined)
        self.assertIn("eligible=True", joined)
        self.assertIn("legacy_prompt_chars=3200", joined)
        self.assertIn("lean_prompt_chars_est=", joined)
        self.assertNotIn("diary flood", joined)
        self.assertNotIn("how are you?", joined)
        self.assertNotIn("I am here.", joined)

    def test_flag_off_keeps_full_prompt_behavior(self):
        from core.routing.focused_cognition import focused_synthesize

        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        focused_synthesize(
            _working_set(),
            surface="telegram",
            chat_fn=chat_fn,
            model="m",
            date_addressed=False,
            legacy_prompt_chars=3200,
            turn_kind="ordinary",
        )

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])
        self.assertIn("diary flood should not appear", captured["system"])

    def test_enabled_lean_prompt_removes_apparatus_and_diary(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            captured["user"] = kwargs["messages"][1]["content"]
            return _response("I am here.")

        focused_synthesize(
            _working_set(),
            surface="telegram",
            chat_fn=chat_fn,
            model="m",
            date_addressed=False,
            legacy_prompt_chars=3200,
            turn_kind="ordinary",
        )

        system = captured["system"]
        self.assertEqual("how are you?", captured["user"])
        self.assertIn("Speak as Maez", system)
        self.assertIn("RECENT DIALOGUE", system)
        self.assertIn("User: how are you?", system)
        self.assertNotIn("CAPABILITY_STATE", system)
        self.assertNotIn("YOUR LIVE BODY", system)
        self.assertNotIn("=== EVIDENCE", system)
        self.assertNotIn("origin trust", system.lower())
        self.assertNotIn("diary flood", system)

    def test_enabled_lean_logs_applied_content_light_receipt(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"

        with self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=lambda **_k: _response("I am here."),
                model="m",
                legacy_prompt_chars=3200,
                turn_kind="ordinary",
            )

        joined = "\n".join(logs.output)
        self.assertIn("lean_conversation_applied", joined)
        self.assertIn("eligible=True", joined)
        self.assertIn("reason=eligible", joined)
        self.assertIn("focused_items_count=1", joined)
        self.assertNotIn("diary flood", joined)
        self.assertNotIn("how are you?", joined)
        self.assertNotIn("I am here.", joined)

    def test_enabled_lean_does_not_build_full_capability_card(self):
        import core.routing.focused_cognition as fc

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"

        def fail_if_called():
            raise AssertionError("lean path must not build full capability card")

        with mock.patch.object(fc, "_focused_capability_card", fail_if_called):
            result = fc.focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=lambda **_k: _response("I am here."),
                model="m",
                legacy_prompt_chars=3200,
                turn_kind="ordinary",
            )

        self.assertEqual(result.reply, "I am here.")

    def test_fresh_web_uses_full_prompt_not_lean(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        ws = _working_set(source_type="web_context")
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("The web says X [E1].")

        focused_synthesize(ws, surface="telegram", chat_fn=chat_fn, model="m")

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])

    def test_self_capability_question_uses_full_prompt_not_lean(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        ws = _working_set()
        ws = ws.__class__(
            items=ws.items,
            ordered_evidence_text=ws.ordered_evidence_text,
            owner_question="What's the state of your web search tools?",
            working_set_chars=ws.working_set_chars,
            working_set_tokens_est=ws.working_set_tokens_est,
            citation_render_version=ws.citation_render_version,
            thin_evidence=ws.thin_evidence,
        )
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("Search is healthy [E1].")

        focused_synthesize(ws, surface="telegram", chat_fn=chat_fn, model="m")

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])

    def test_bodyish_leak_flag_appears_in_shadow(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_SHADOW"] = "1"
        ws = _working_set()
        ws = ws.__class__(
            items=ws.items,
            ordered_evidence_text=ws.ordered_evidence_text,
            owner_question="your web search tools are acting strange",
            working_set_chars=ws.working_set_chars,
            working_set_tokens_est=ws.working_set_tokens_est,
            citation_render_version=ws.citation_render_version,
            thin_evidence=ws.thin_evidence,
        )

        with self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                ws,
                surface="telegram",
                chat_fn=lambda **_k: _response("ok"),
                model="m",
            )

        self.assertTrue(any("bodyish_lean_leak=True" in m for m in logs.output))

    def test_date_addressed_uses_full_prompt_not_lean(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I found the date [E1].")

        focused_synthesize(
            _working_set(),
            surface="telegram",
            chat_fn=chat_fn,
            model="m",
            date_addressed=True,
        )

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])

    def test_shadow_receipt_includes_date_addressed_state(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_SHADOW"] = "1"

        with self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                _working_set(source_type="web_context"),
                surface="telegram",
                chat_fn=lambda **_k: _response("ok"),
                model="m",
                date_addressed=True,
            )

        joined = "\n".join(logs.output)
        self.assertIn("reason=fresh_evidence", joined)
        self.assertIn("date_addressed=True", joined)

    def test_lean_renderer_does_not_import_memory_manager(self):
        import core.routing.focused_cognition as fc

        before = set(sys.modules)
        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"

        fc.focused_synthesize(
            _working_set(),
            surface="telegram",
            chat_fn=lambda **_k: _response("ok"),
            model="m",
        )

        loaded = set(sys.modules) - before
        self.assertFalse(any(name == "memory.memory_manager" for name in loaded))


if __name__ == "__main__":
    unittest.main()
