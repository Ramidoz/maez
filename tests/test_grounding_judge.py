# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.grounding_judge — the semantic grounding-check
pass that replaces the regex detectors in self_claim_audit."""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock


class JudgePromptShape(unittest.TestCase):
    """Judge builds a prompt with response text, signal manifest,
    and few-shot examples. Format is stable so the LLM's JSON output
    parser doesn't drift."""

    def test_prompt_contains_response_text(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="The owner is at his desk.",
            signals_present=["system stats"],
            signals_absent=["screen observation", "presence snapshot"],
            few_shots=[],
        )
        self.assertIn("The owner is at his desk.", prompt)

    def test_prompt_contains_signal_manifest(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="ok",
            signals_present=["system stats"],
            signals_absent=["screen observation"],
            few_shots=[],
        )
        self.assertIn("system stats", prompt)
        self.assertIn("screen observation", prompt)

    def test_prompt_includes_fewshots_when_provided(self):
        from core.grounding_judge import _build_judge_prompt
        fs = [{
            "text": "Rohit is working on X",
            "signals_absent": ["screen observation"],
            "reason": "activity claim without screen source",
        }]
        prompt = _build_judge_prompt(
            text="ok", signals_present=[], signals_absent=["screen"],
            few_shots=fs,
        )
        self.assertIn("Rohit is working on X", prompt)

    def test_prompt_requests_json_output(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="x", signals_present=[], signals_absent=[],
            few_shots=[],
        )
        self.assertTrue(
            "JSON" in prompt or "json" in prompt,
            f"prompt must request JSON output; got:\n{prompt[:500]}",
        )


class JudgeOutputParsing(unittest.TestCase):
    def test_parses_valid_json_flags(self):
        from core.grounding_judge import _parse_judge_output
        llm_output = '{"ungrounded": [{"text": "owner at desk", "reason": "no presence signal"}]}'
        flags = _parse_judge_output(llm_output)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["text"], "owner at desk")

    def test_returns_empty_on_no_ungrounded(self):
        from core.grounding_judge import _parse_judge_output
        flags = _parse_judge_output('{"ungrounded": []}')
        self.assertEqual(flags, [])

    def test_fails_open_on_parse_error(self):
        """Unparseable LLM output returns [] — no flags, not a crash.
        Judge must never block a response."""
        from core.grounding_judge import _parse_judge_output
        self.assertEqual(_parse_judge_output("not json"), [])
        self.assertEqual(_parse_judge_output(""), [])
        self.assertEqual(_parse_judge_output(None), [])

    def test_extracts_json_from_preamble(self):
        """Local LLMs often wrap JSON in prose. Parser must find the
        JSON object even with a preamble."""
        from core.grounding_judge import _parse_judge_output
        llm_output = (
            "Here is my analysis:\n\n"
            '{"ungrounded": [{"text": "x", "reason": "y"}]}'
        )
        flags = _parse_judge_output(llm_output)
        self.assertEqual(len(flags), 1)


class JudgePromptCoversChatSurfaceClasses(unittest.TestCase):
    """Expanded 2026-04-21: the judge prompt must cover three classes
    the deleted regex used to handle — framework-name fabrication,
    version fabrication, second-person presence inference — even when
    the signal manifest is empty (chat-surface case)."""

    def test_prompt_includes_builtin_framework_fewshot(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="ok", signals_present=[], signals_absent=[], few_shots=[],
        )
        self.assertIn("Maelstrom", prompt,
            "framework-name anti-pattern must be in built-in few-shots")
        self.assertIn("Orchestrator", prompt,
            "internal-component anti-pattern must be present")

    def test_prompt_includes_builtin_presence_fewshot(self):
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="ok", signals_present=[], signals_absent=[], few_shots=[],
        )
        # One of the built-in shots must illustrate second-person presence
        self.assertTrue(
            "You seem" in prompt or "Rohit's been" in prompt,
            "presence-inference anti-pattern missing from built-in shots",
        )

    def test_prompt_rules_call_out_concrete_target_action(self):
        """The rules section must express the false-action rule in terms
        of a CONCRETE TARGET (path/file/command) — the daemon-specific
        'no shell during _reason()' phrasing was removed 2026-04-21 after
        it caused the judge to over-flag generic presence claims like
        'I'm monitoring the system' on chat surfaces."""
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="ok", signals_present=[], signals_absent=[], few_shots=[],
        )
        low = prompt.lower()
        # Must mention the concept of a concrete/specific target
        self.assertTrue(
            "concrete target" in low or "specific target" in low,
            "prompt must describe the false-action rule via concrete-target shape",
        )
        # Must explicitly carve out generic presence/framing statements
        self.assertIn("i'm here", low)
        self.assertIn("i'm monitoring", low)

    def test_prompt_demands_verbatim_substring(self):
        """Judge output's `text` must be a substring of the response, or
        audit can't locate it to rewrite. Prompt must instruct this."""
        from core.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="ok", signals_present=[], signals_absent=[], few_shots=[],
        )
        self.assertIn("verbatim", prompt.lower())

    def test_retrieval_fewshots_appended_after_builtin(self):
        """Runtime-retrieved shots from fabrication_memory should appear
        alongside built-in ones, not replace them."""
        from core.grounding_judge import _build_judge_prompt
        retrieved = [{
            "text": "custom-flagged-claim-XYZ",
            "signals_absent": ["screen"],
            "reason": "test",
        }]
        prompt = _build_judge_prompt(
            text="ok", signals_present=[], signals_absent=[],
            few_shots=retrieved,
        )
        self.assertIn("Maelstrom", prompt)  # built-in still there
        self.assertIn("custom-flagged-claim-XYZ", prompt)  # retrieved too


class JudgeCallsLLM(unittest.TestCase):
    """End-to-end: judge(text, signals, few_shots) → flags.
    LLM client is stubbed; this test asserts the integration shape."""

    def test_judge_calls_llm_client(self):
        from core import grounding_judge

        def fake_chat(*, model, messages, **kwargs):
            resp = MagicMock()
            resp.message.content = '{"ungrounded": [{"text": "x", "reason": "y"}]}'
            return resp

        with patch("core.grounding_judge._llm_client.chat",
                   side_effect=fake_chat):
            flags = grounding_judge.judge(
                text="owner at desk",
                signals_present=["system stats"],
                signals_absent=["screen observation"],
                few_shots=[],
            )
            self.assertEqual(len(flags), 1)

    def test_judge_returns_empty_on_llm_failure(self):
        """LLM call raises → judge returns [] (fail-open)."""
        from core import grounding_judge

        def fake_chat(**kwargs):
            raise RuntimeError("llama-server down")

        with patch("core.grounding_judge._llm_client.chat",
                   side_effect=fake_chat):
            flags = grounding_judge.judge(
                text="anything",
                signals_present=[],
                signals_absent=[],
                few_shots=[],
            )
            self.assertEqual(flags, [])


if __name__ == "__main__":
    unittest.main()
