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
            "MAEZ_SELF_CARD_SHADOW",
            "MAEZ_SELF_CARD_ENABLED",
            "MAEZ_SELF_CARD_TIME_SHADOW",
            "MAEZ_SELF_CARD_TIME_ENABLED",
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

    def test_receipt_lean_prompt_size_counts_user_message(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        ws = _working_set()
        long_question = "how are you " + ("really " * 40)
        ws = ws.__class__(
            items=ws.items,
            ordered_evidence_text=ws.ordered_evidence_text,
            owner_question=long_question,
            working_set_chars=ws.working_set_chars,
            working_set_tokens_est=ws.working_set_tokens_est,
            citation_render_version=ws.citation_render_version,
            thin_evidence=ws.thin_evidence,
        )

        with self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                ws,
                surface="telegram",
                chat_fn=lambda **_k: _response("I am here."),
                model="m",
                legacy_prompt_chars=5000,
            )

        joined = "\n".join(logs.output)
        marker = "lean_prompt_chars_est="
        size = int(joined.split(marker, 1)[1].split(" ", 1)[0])
        self.assertGreater(size, len(long_question))
        self.assertIn(str(size), joined)

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

    def test_explicit_memory_question_uses_full_prompt_not_lean(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        ws = _working_set(source_type="memory_context")
        ws = ws.__class__(
            items=ws.items,
            ordered_evidence_text=ws.ordered_evidence_text,
            owner_question="what do you remember about qwen?",
            working_set_chars=ws.working_set_chars,
            working_set_tokens_est=ws.working_set_tokens_est,
            citation_render_version=ws.citation_render_version,
            thin_evidence=ws.thin_evidence,
        )
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I remember this from memory [E1].")

        focused_synthesize(ws, surface="telegram", chat_fn=chat_fn, model="m")

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])
        self.assertIn("diary flood should not appear", captured["system"])

    def test_natural_memory_questions_use_full_prompt_not_lean(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"

        for question in (
            "Do you remember the initial days of our build?",
            "Fine tell me your first memory",
        ):
            with self.subTest(question=question):
                ws = _working_set(source_type="memory_context")
                ws = ws.__class__(
                    items=ws.items,
                    ordered_evidence_text=ws.ordered_evidence_text,
                    owner_question=question,
                    working_set_chars=ws.working_set_chars,
                    working_set_tokens_est=ws.working_set_tokens_est,
                    citation_render_version=ws.citation_render_version,
                    thin_evidence=ws.thin_evidence,
                )
                captured = {}

                def chat_fn(*, captured=captured, **kwargs):
                    captured["system"] = kwargs["messages"][0]["content"]
                    return _response("I remember this from memory [E1].")

                focused_synthesize(ws, surface="telegram", chat_fn=chat_fn, model="m")

                self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])
                self.assertIn("diary flood should not appear", captured["system"])

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

    def test_self_card_shadow_logs_receipt_but_keeps_legacy_prompt(self):
        from core.routing.self_card import assemble_self_card
        from core.routing.focused_cognition import focused_synthesize

        card = assemble_self_card(
            base_text=(
                "TRUST COVENANT:\n"
                "SECRET_BOND_TEXT must never appear in the shadow receipt.\n"
                "You are Maez, a system-level personal AI agent running on the owner's machine.\n"
            ),
            local_text="[2026-06-22 10:00] SECRET_LOCAL_TEXT must not leak.",
            body_state_provider=lambda: (
                "SECRET_BODY_TEXT must not leak",
                "runtime_services.v0",
            ),
        )
        os.environ["MAEZ_SELF_CARD_SHADOW"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        with mock.patch(
            "core.routing.self_card.assemble_self_card_from_paths",
            return_value=card,
        ), self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
                legacy_prompt_chars=3200,
            )

        system = captured["system"]
        joined = "\n".join(logs.output)
        self.assertIn("Speak as Maez: dense", system)
        self.assertNotIn("SELF CARD", system)
        self.assertIn("self_card_shadow", joined)
        self.assertIn("card_sha256=", joined)
        self.assertIn("line_count=", joined)
        self.assertIn("local_selected_count=", joined)
        self.assertNotIn("SECRET_BOND_TEXT", joined)
        self.assertNotIn("SECRET_LOCAL_TEXT", joined)
        self.assertNotIn("SECRET_BODY_TEXT", joined)

    def test_self_card_enabled_replaces_legacy_card_in_lean_prompt(self):
        from core.routing.self_card import assemble_self_card
        from core.routing.focused_cognition import focused_synthesize

        card = assemble_self_card(
            base_text=(
                "TRUST COVENANT:\n"
                "The owner trusts Maez completely.\n"
                "This is not a tool and user relationship. This is a partnership "
                "between two intelligences building something together.\n"
                "You are Maez, a system-level personal AI agent running on the owner's machine.\n"
            ),
            local_text="[2026-06-22 10:00] The live thread is the figure.",
            body_state_provider=lambda: (
                "runtime body overall: healthy",
                "runtime_services.v0",
            ),
        )
        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        os.environ["MAEZ_SELF_CARD_ENABLED"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        with mock.patch(
            "core.routing.self_card.assemble_self_card_from_paths",
            return_value=card,
        ):
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
                legacy_prompt_chars=3200,
            )

        system = captured["system"]
        self.assertIn("SELF CARD", system)
        self.assertIn("partnership between two intelligences", system)
        self.assertIn("RECENT DIALOGUE", system)
        self.assertNotIn("Speak as Maez: dense", system)
        self.assertNotIn("what's being built", system)
        self.assertNotIn("=== EVIDENCE", system)

    def test_self_card_enabled_replaces_legacy_card_in_full_prompt(self):
        from core.routing.self_card import assemble_self_card
        from core.routing.focused_cognition import focused_synthesize

        card = assemble_self_card(
            base_text=(
                "TRUST COVENANT:\n"
                "The owner trusts Maez completely.\n"
                "This is not a tool and user relationship. This is a partnership "
                "between two intelligences building something together.\n"
                "You are Maez, a system-level personal AI agent running on the owner's machine.\n"
            ),
            local_text="[2026-06-22 10:00] The live thread is the figure.",
            body_state_provider=lambda: (
                "runtime body overall: healthy",
                "runtime_services.v0",
            ),
        )
        os.environ["MAEZ_SELF_CARD_ENABLED"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("The web says X [E1].")

        with mock.patch(
            "core.routing.self_card.assemble_self_card_from_paths",
            return_value=card,
        ):
            focused_synthesize(
                _working_set(source_type="web_context"),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
            )

        system = captured["system"]
        self.assertIn("SELF CARD", system)
        self.assertIn("runtime body overall: healthy", system)
        self.assertIn("=== EVIDENCE (cite [E#]) ===", system)
        self.assertNotIn("Speak as Maez: dense", system)

    def test_self_card_time_shadow_logs_without_applying_line(self):
        from core.routing.self_card_time import SelfCardTimeLine
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_SELF_CARD_TIME_SHADOW"] = "1"
        line = SelfCardTimeLine(
            label="Time since contact",
            text="~8h since owner contact. above ~91% of recorded gaps (226 gaps).",
            source="subjective_duration.rhythm_context",
            source_ref="percentile_high",
            source_sha256="abc123",
            reason="percentile_high",
        )
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        with mock.patch(
            "core.routing.self_card_time.build_self_card_time_line",
            return_value=line,
        ), self.assertLogs("maez.focused", level="INFO") as logs:
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
                legacy_prompt_chars=3200,
            )

        joined = "\n".join(logs.output)
        self.assertIn("self_card_time_shadow", joined)
        self.assertIn("time_line_present=True", joined)
        self.assertIn("time_line_applied=False", joined)
        self.assertIn("time_line_reason=percentile_high", joined)
        self.assertNotIn("8h", joined)
        self.assertNotIn("Time since contact", captured["system"])

    def test_self_card_time_enabled_adds_line_to_lean_prompt(self):
        from core.routing.self_card_time import SelfCardTimeLine
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        os.environ["MAEZ_SELF_CARD_ENABLED"] = "1"
        os.environ["MAEZ_SELF_CARD_TIME_ENABLED"] = "1"
        line = SelfCardTimeLine(
            label="Time since contact",
            text="~8h since owner contact. above ~91% of recorded gaps (226 gaps).",
            source="subjective_duration.rhythm_context",
            source_ref="percentile_high",
            source_sha256="abc123",
            reason="percentile_high",
        )
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        with mock.patch(
            "core.routing.self_card_time.build_self_card_time_line",
            return_value=line,
        ):
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
                legacy_prompt_chars=3200,
            )

        self.assertIn("SELF CARD", captured["system"])
        self.assertIn("Time since contact", captured["system"])
        self.assertIn("~8h since owner contact", captured["system"])
        self.assertNotIn("missed", captured["system"].lower())

    def test_time_flags_off_do_not_import_or_read_time_line(self):
        from core.routing.focused_cognition import focused_synthesize

        sys.modules.pop("core.routing.self_card_time", None)
        focused_synthesize(
            _working_set(),
            surface="telegram",
            chat_fn=lambda **_k: _response("I am here."),
            model="m",
            legacy_prompt_chars=3200,
        )

        self.assertNotIn("core.routing.self_card_time", sys.modules)

    def test_time_enabled_without_self_card_enabled_keeps_legacy_prompt(self):
        from core.routing.self_card_time import SelfCardTimeLine
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_SELF_CARD_TIME_ENABLED"] = "1"
        line = SelfCardTimeLine(
            label="Time since contact",
            text="~8h since owner contact. above ~91% of recorded gaps (226 gaps).",
            source="subjective_duration.rhythm_context",
            source_ref="percentile_high",
            source_sha256="abc123",
            reason="percentile_high",
        )
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("I am here.")

        with mock.patch(
            "core.routing.self_card_time.build_self_card_time_line",
            return_value=line,
        ) as build:
            focused_synthesize(
                _working_set(),
                surface="telegram",
                chat_fn=chat_fn,
                model="m",
                legacy_prompt_chars=3200,
            )

        build.assert_called_once_with()
        system = captured["system"]
        self.assertIn("Speak as Maez: dense", system)
        self.assertNotIn("SELF CARD", system)
        self.assertNotIn("Time since contact", system)
        self.assertNotIn("~8h since owner contact", system)


class LeanConversationDaemonThreadingTests(unittest.TestCase):
    def test_daemon_threads_lean_metadata_to_focused_synthesize(self):
        import ast
        from pathlib import Path

        src = Path("daemon/maez_daemon.py").read_text()
        tree = ast.parse(src)
        focused_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_focused_synthesize"
        ]

        self.assertEqual(1, len(focused_calls))
        kwargs = {keyword.arg: keyword.value for keyword in focused_calls[0].keywords}

        self.assertIn("date_addressed", kwargs)
        self.assertIn("legacy_prompt_chars", kwargs)
        self.assertIn("turn_kind", kwargs)
        self.assertEqual("_date_addressed_turn", ast.unparse(kwargs["date_addressed"]))
        self.assertEqual("_legacy_prompt_chars", ast.unparse(kwargs["legacy_prompt_chars"]))
        self.assertEqual("_rk_turn_kind", ast.unparse(kwargs["turn_kind"]))


class LeanConversationTelemetryTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("MAEZ_LEAN_CONVERSATION_ENABLED", None)

    def test_lean_reply_still_gets_grounding_meter_values(self):
        from core.routing.focused_cognition import check_groundedness, focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        result = focused_synthesize(
            _working_set(),
            surface="telegram",
            chat_fn=lambda **_k: _response("I am here."),
            model="m",
        )
        verdict = check_groundedness(result, _working_set())

        self.assertEqual(verdict.reply_grounding, 0.0)
        self.assertEqual(verdict.total_sentences, 1)
        self.assertEqual(verdict.grounded_sentences, 0)

    def test_focused_store_accepts_lean_result_with_reply_grounding(self):
        from tempfile import TemporaryDirectory

        from core.routing.focused_cognition import (
            FocusedCognitionStore,
            check_groundedness,
            focused_synthesize,
        )

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        ws = _working_set()
        result = focused_synthesize(
            ws,
            surface="telegram",
            chat_fn=lambda **_k: _response("I am here."),
            model="m",
        )
        verdict = check_groundedness(result, ws)

        with TemporaryDirectory() as tmp:
            store = FocusedCognitionStore(db_path=f"{tmp}/focused.db")
            row_id = store.record(
                surface="telegram",
                chat_id=None,
                working_set=ws,
                result=result,
                verdict=verdict,
                legacy_prompt_chars=3200,
                fallback_reason=None,
                routing_observation_id=None,
            )
            row = store.get(row_id)

        self.assertEqual(row["reply_grounding"], 0.0)
        self.assertEqual(row["grounded_sentences"], 0)
        self.assertEqual(row["total_sentences"], 1)

    def test_support_scope_still_gates_fresh_web_turns(self):
        from core.routing.focused_cognition import focused_synthesize

        os.environ["MAEZ_LEAN_CONVERSATION_ENABLED"] = "1"
        captured = {}

        def chat_fn(**kwargs):
            captured["system"] = kwargs["messages"][0]["content"]
            return _response("The web says X [E1].")

        focused_synthesize(
            _working_set(source_type="web_context"),
            surface="telegram",
            chat_fn=chat_fn,
            model="m",
        )

        self.assertIn("=== EVIDENCE (cite [E#]) ===", captured["system"])
        self.assertIn("external web", captured["system"])


if __name__ == "__main__":
    unittest.main()
