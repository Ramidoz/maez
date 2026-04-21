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
