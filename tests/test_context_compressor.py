# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for core.context_compressor — conversation-thread summarization
on truncation.

Uses the judge endpoint for summarization; all tests stub the HTTP call.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core.context_compressor import (
    compress, _build_summary_message, _serialize_turns, _SUMMARY_PREFIX,
)


def _turn(role: str, content: str) -> dict:
    return {"role": role, "content": content}


class CompressBoundaryContract(unittest.TestCase):
    """compress() no-ops when thread is short and doesn't need compaction."""

    def test_empty_thread_returns_empty(self):
        self.assertEqual(compress([], keep_tail_n=12), [])

    def test_thread_at_tail_limit_unchanged(self):
        thread = [_turn("user", f"msg {i}") for i in range(12)]
        with patch("core.context_compressor._call_summarizer") as mock:
            out = compress(thread, keep_tail_n=12)
            mock.assert_not_called()
        self.assertEqual(out, thread)

    def test_thread_below_tail_limit_unchanged(self):
        thread = [_turn("user", f"msg {i}") for i in range(5)]
        with patch("core.context_compressor._call_summarizer") as mock:
            out = compress(thread, keep_tail_n=12)
            mock.assert_not_called()
        self.assertEqual(out, thread)


class CompressTailPreservation(unittest.TestCase):
    """The most recent keep_tail_n turns must always appear verbatim
    in the output, unmodified."""

    def test_tail_bytes_preserved(self):
        thread = [_turn("user", f"msg {i}") for i in range(20)]
        with patch("core.context_compressor._call_summarizer",
                   return_value="SUMMARY"):
            out = compress(thread, keep_tail_n=5)
        # First element is the summary; rest is tail verbatim.
        self.assertEqual(out[1:], thread[-5:])

    def test_below_min_compress_just_truncates_no_summary_call(self):
        # 3 head turns with min_to_compress=5 → head too small, just truncate.
        thread = [_turn("user", f"msg {i}") for i in range(15)]
        with patch("core.context_compressor._call_summarizer") as mock:
            out = compress(thread, keep_tail_n=12, min_to_compress=5)
            mock.assert_not_called()
        self.assertEqual(len(out), 12)
        self.assertEqual(out, thread[-12:])


class CompressWithSummarizer(unittest.TestCase):

    def test_summary_prepended_when_head_large_enough(self):
        thread = [_turn("user", f"msg {i}") for i in range(20)]
        with patch("core.context_compressor._call_summarizer",
                   return_value="## Active Task\nRohit asked for X"):
            out = compress(thread, keep_tail_n=12)
        self.assertEqual(len(out), 13)  # 1 summary + 12 tail
        self.assertEqual(out[0]["role"], "system")
        self.assertIn(_SUMMARY_PREFIX, out[0]["content"])
        self.assertIn("Rohit asked for X", out[0]["content"])

    def test_summary_has_handoff_prefix(self):
        thread = [_turn("user", f"msg {i}") for i in range(20)]
        with patch("core.context_compressor._call_summarizer",
                   return_value="body"):
            out = compress(thread, keep_tail_n=5)
        self.assertTrue(out[0]["content"].startswith(_SUMMARY_PREFIX))

    def test_summarizer_passed_head_slice_only(self):
        thread = [_turn("user", f"HEAD {i}") for i in range(5)] + \
                 [_turn("user", f"TAIL {i}") for i in range(5)]
        captured = {}

        def fake(prompt: str) -> str:
            captured["prompt"] = prompt
            return "fake summary"

        with patch("core.context_compressor._call_summarizer",
                   side_effect=fake):
            compress(thread, keep_tail_n=5)

        prompt = captured["prompt"]
        # Head turns should all be in the serialized input
        for i in range(5):
            self.assertIn(f"HEAD {i}", prompt)
        # Tail turns should NOT be — they're preserved verbatim, not summarized
        for i in range(5):
            self.assertNotIn(f"TAIL {i}", prompt)


class CompressFailsSafe(unittest.TestCase):
    """When the summarizer returns None (endpoint down, timeout, malformed
    response, etc.), compress must fall back to plain tail truncation —
    never raise, never lose the tail."""

    def test_none_summary_falls_back_to_tail_truncation(self):
        thread = [_turn("user", f"msg {i}") for i in range(20)]
        with patch("core.context_compressor._call_summarizer",
                   return_value=None):
            out = compress(thread, keep_tail_n=5)
        # No summary, just last 5 turns.
        self.assertEqual(len(out), 5)
        self.assertEqual(out, thread[-5:])

    def test_empty_string_summary_treated_as_none(self):
        thread = [_turn("user", f"msg {i}") for i in range(20)]
        with patch("core.context_compressor._call_summarizer",
                   return_value=""):
            out = compress(thread, keep_tail_n=5)
        self.assertEqual(len(out), 5)

    def test_summarizer_exception_does_not_propagate(self):
        """_call_summarizer swallows its own exceptions; compress() should
        treat any None result as fail-safe truncation regardless."""
        thread = [_turn("user", f"msg {i}") for i in range(20)]
        with patch("core.context_compressor._call_summarizer",
                   side_effect=None, return_value=None):
            # This test verifies that the public compress() is robust to
            # a summarizer that returns None; the internal _call_summarizer
            # has its own try/except to ensure it does return None on error.
            out = compress(thread, keep_tail_n=5)
        self.assertEqual(len(out), 5)


class SerializeTurns(unittest.TestCase):

    def test_labels_roles(self):
        turns = [_turn("user", "hi"), _turn("assistant", "hello")]
        text = _serialize_turns(turns)
        self.assertIn("[USER]: hi", text)
        self.assertIn("[ASSISTANT]: hello", text)

    def test_long_content_truncated(self):
        long = "x" * 5000
        text = _serialize_turns([_turn("user", long)])
        self.assertIn("...[truncated]...", text)
        self.assertLess(len(text), 3000)

    def test_non_string_content_coerced(self):
        # content that isn't a string (rare — maybe a dict from a broken path)
        # should still serialize, not crash.
        text = _serialize_turns([{"role": "user", "content": ["x", "y"]}])
        self.assertIn("[USER]:", text)


class BuildSummaryMessage(unittest.TestCase):

    def test_role_is_system(self):
        msg = _build_summary_message("body")
        self.assertEqual(msg["role"], "system")

    def test_prefix_present(self):
        msg = _build_summary_message("body text here")
        self.assertIn(_SUMMARY_PREFIX, msg["content"])
        self.assertIn("body text here", msg["content"])


if __name__ == "__main__":
    unittest.main()
