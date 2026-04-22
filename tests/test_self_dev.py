# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.self_dev — JSON parsing, prompt plumbing, CLI.
The tier call is always mocked so we never spend real quota."""
from __future__ import annotations

import json
import unittest
from unittest import mock


class JsonExtraction(unittest.TestCase):
    def test_extract_clean_json(self):
        from core.self_dev import _extract_json_block
        s = '{"a": 1, "b": [2, 3]}'
        self.assertEqual(_extract_json_block(s), s)

    def test_extract_with_prose_before_and_after(self):
        from core.self_dev import _extract_json_block
        s = 'Here you go: {"a": 1}\nand that\'s that.'
        self.assertEqual(_extract_json_block(s), '{"a": 1}')

    def test_extract_handles_braces_in_strings(self):
        from core.self_dev import _extract_json_block
        # The parser must not be fooled by `{` inside a string value.
        s = '{"text": "use { and } carefully", "n": 1}'
        self.assertEqual(_extract_json_block(s), s)

    def test_extract_returns_none_on_no_json(self):
        from core.self_dev import _extract_json_block
        self.assertIsNone(_extract_json_block("no braces here"))
        self.assertIsNone(_extract_json_block(""))


class ResponseParsing(unittest.TestCase):
    def test_clean_response_produces_structured_concerns(self):
        from core.self_dev import _parse_response
        raw = json.dumps({
            "overall": "Diff looks okay overall.",
            "concerns": [
                {"file": "core/a.py", "line": 42, "severity": "major",
                 "text": "off-by-one in loop bound",
                 "suggestion": "use range(len(xs))"},
                {"file": "core/b.py", "line": None, "severity": "minor",
                 "text": "docstring is wrong",
                 "suggestion": "null"},
            ],
        })
        overall, concerns, err = _parse_response(raw)
        self.assertEqual(err, "")
        self.assertEqual(overall, "Diff looks okay overall.")
        self.assertEqual(len(concerns), 2)
        self.assertEqual(concerns[0].severity, "major")
        self.assertEqual(concerns[0].line, 42)
        self.assertEqual(concerns[0].suggestion, "use range(len(xs))")
        # 'null' string suggestion is dropped
        self.assertIsNone(concerns[1].suggestion)

    def test_invalid_severity_falls_back_to_minor(self):
        from core.self_dev import _parse_response
        raw = json.dumps({
            "overall": "x",
            "concerns": [{"file": "a.py", "line": 1,
                          "severity": "DOOMED", "text": "something"}],
        })
        _, concerns, _ = _parse_response(raw)
        self.assertEqual(concerns[0].severity, "minor")

    def test_concerns_without_text_are_dropped(self):
        from core.self_dev import _parse_response
        raw = json.dumps({
            "overall": "ok",
            "concerns": [
                {"file": "a.py", "line": 1, "severity": "major", "text": ""},
                {"file": "b.py", "line": 2, "severity": "minor",
                 "text": "real concern"},
            ],
        })
        _, concerns, _ = _parse_response(raw)
        self.assertEqual(len(concerns), 1)
        self.assertEqual(concerns[0].text, "real concern")

    def test_non_list_concerns_returns_parse_error(self):
        from core.self_dev import _parse_response
        raw = json.dumps({"overall": "x", "concerns": "nope"})
        _, concerns, err = _parse_response(raw)
        self.assertEqual(concerns, [])
        self.assertIn("not a list", err)

    def test_plain_text_response_is_preserved_as_overall(self):
        from core.self_dev import _parse_response
        raw = "Sorry, I cannot review this diff."
        overall, concerns, err = _parse_response(raw)
        self.assertIn("cannot review", overall)
        self.assertEqual(concerns, [])
        self.assertIn("no JSON object", err)

    def test_malformed_json_is_flagged(self):
        from core.self_dev import _parse_response
        raw = '{"overall": "ok", "concerns": [{"file": "a.py"'  # truncated
        _, _, err = _parse_response(raw)
        self.assertNotEqual(err, "")


class ReviewEndToEndMocked(unittest.TestCase):
    def test_empty_diff_skips_claude_call(self):
        from core import self_dev
        with mock.patch.object(self_dev, "_git_diff", return_value=""):
            r = self_dev.review(target_ref="HEAD")
        self.assertEqual(r.diff_size_chars, 0)
        self.assertEqual(r.concerns, [])
        self.assertIn("empty diff", r.overall.lower())

    def test_review_happy_path(self):
        from core import self_dev
        from core.claude_tier import TierReply

        fake_reply = json.dumps({
            "overall": "Looks good but one real concern.",
            "concerns": [{
                "file": "core/x.py", "line": 10,
                "severity": "major",
                "text": "resource not closed on error path",
                "suggestion": "use a context manager",
            }],
        })
        fake = TierReply(reply=fake_reply, model_used="claude-sonnet-4-6",
                          input_tokens=100, output_tokens=50, raw={})

        with mock.patch.object(self_dev, "_git_diff",
                                return_value="diff --git a/x b/x\n+foo\n"), \
             mock.patch("core.self_dev.claude_tier.call",
                         return_value=fake) as m_call:
            r = self_dev.review(target_ref="HEAD~1..HEAD")

        self.assertEqual(len(r.concerns), 1)
        self.assertEqual(r.concerns[0].severity, "major")
        self.assertEqual(r.model_used, "claude-sonnet-4-6")
        self.assertEqual(r.input_tokens, 100)
        # Caller label propagated for trajectory log slicing
        call_kwargs = m_call.call_args.kwargs
        self.assertEqual(call_kwargs["caller"], "self_dev/review")
        # Diff text is embedded in the user prompt
        self.assertIn("HEAD~1..HEAD", call_kwargs["prompt"])
        self.assertIn("diff --git", call_kwargs["prompt"])

    def test_tier_error_raises_runtime(self):
        from core import self_dev
        from core.claude_tier import ClaudeTierUnavailable

        with mock.patch.object(self_dev, "_git_diff",
                                return_value="diff\n+x\n"), \
             mock.patch("core.self_dev.claude_tier.call",
                         side_effect=ClaudeTierUnavailable("proxy down")):
            with self.assertRaises(RuntimeError) as cm:
                self_dev.review(target_ref="HEAD")
            self.assertIn("proxy down", str(cm.exception))

    def test_large_diff_is_truncated_in_prompt(self):
        from core import self_dev
        from core.claude_tier import TierReply
        big = "diff --git\n" + ("+line\n" * 20000)  # ~130k chars
        fake = TierReply(
            reply='{"overall":"ok","concerns":[]}',
            model_used="sonnet", input_tokens=1, output_tokens=1, raw={},
        )
        with mock.patch.object(self_dev, "_git_diff", return_value=big), \
             mock.patch("core.self_dev.claude_tier.call",
                         return_value=fake) as m_call:
            r = self_dev.review(target_ref="HEAD", diff_char_cap=1000)
        sent_prompt = m_call.call_args.kwargs["prompt"]
        # Should have the truncation note and be much shorter than `big`
        self.assertIn("truncated", sent_prompt)
        self.assertLess(len(sent_prompt), 3000)
        # Result records the ORIGINAL diff size, not truncated
        self.assertEqual(r.diff_size_chars, len(big))


class SeverityCounts(unittest.TestCase):
    def test_counts_severity_buckets(self):
        from core.self_dev import ReviewResult, Concern
        r = ReviewResult(target_ref="x", diff_size_chars=0, overall="")
        r.concerns = [
            Concern(file="a", line=1, severity="blocker", text="t"),
            Concern(file="a", line=2, severity="major", text="t"),
            Concern(file="a", line=3, severity="major", text="t"),
            Concern(file="a", line=4, severity="nit", text="t"),
        ]
        self.assertEqual(
            r.severity_counts(),
            {"blocker": 1, "major": 2, "nit": 1},
        )


if __name__ == "__main__":
    unittest.main()
