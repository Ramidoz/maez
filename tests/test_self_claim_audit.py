# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for the v2 judge-powered self_claim_audit.

The regex-era tests were removed with the regex detectors (2026-04-21).
This suite covers the boundary contract of audit() and the rewrite shape
when the judge returns flags. The judge itself is tested in
test_grounding_judge.py — here we stub it to isolate audit's behavior.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.self_claim_audit import (
    audit, AuditResult, Flag, _diag_find_flags,
    _rewrite, _sentence_span,
)


# ── boundary contract ──────────────────────────────────────────────────

class AuditBoundary(unittest.TestCase):
    """audit() skip / noop paths — must never call the judge in these cases."""

    def test_empty_text_is_noop(self):
        for val in ("", "   ", "\n"):
            r = audit(val, surface="test")
            self.assertFalse(r.rewritten)
            self.assertEqual(r.mode, "noop")

    def test_tool_continuation_skips(self):
        r = audit("I ran foo and got bar", surface="cli",
                  in_tool_continuation=True)
        self.assertFalse(r.rewritten)
        self.assertEqual(r.skipped_reason, "tool_continuation")

    def test_env_disabled_skips(self):
        with patch.dict(os.environ, {"MAEZ_SEMANTIC_AUDIT": "0"}):
            r = audit("anything", surface="test")
            self.assertFalse(r.rewritten)
            self.assertEqual(r.skipped_reason, "env_disabled")


# ── judge integration: stub out judge, verify audit wiring ─────────────

class AuditJudgeWiring(unittest.TestCase):

    def test_no_flags_returns_original(self):
        with patch("core.self_claim_audit._find_flags", return_value=[]):
            r = audit("the disk is at 70% and stable", surface="daemon_cycle")
        self.assertFalse(r.rewritten)
        self.assertEqual(r.mode, "noop")
        self.assertEqual(r.text, "the disk is at 70% and stable")

    def test_judge_flag_triggers_sentence_rewrite(self):
        text = "Disk is at 70%. The upward trend suggests a leak. CPU is fine."
        start = text.find("The upward trend")
        claim = "The upward trend suggests a leak."
        flag = Flag(
            kind="judge",
            span=(start, start + len(claim)),
            text=claim,
            reason="snapshot signal has no history",
        )
        with patch("core.self_claim_audit._find_flags", return_value=[flag]):
            r = audit(text, surface="daemon_cycle")
        self.assertTrue(r.rewritten)
        self.assertEqual(r.mode, "sentence")
        self.assertIn("I don't have a grounded answer for that part.", r.text)
        self.assertNotIn("upward trend suggests a leak", r.text)

    def test_judge_failure_fails_open(self):
        """_find_flags must swallow judge exceptions (no flags, no crash)."""
        from core.self_claim_audit import _find_flags
        with patch("core.grounding_judge.judge",
                   side_effect=Exception("boom")):
            flags = _find_flags("some text", signals_present=[],
                                signals_absent=[])
        self.assertEqual(flags, [])

    def test_multiple_flags_in_same_sentence_replace_once(self):
        text = "The upward trend is leaking disk."
        f1 = Flag(kind="judge", span=(0, 16), text="The upward trend",
                  reason="no history")
        f2 = Flag(kind="judge", span=(20, 32), text="leaking disk",
                  reason="no trend")
        with patch("core.self_claim_audit._find_flags", return_value=[f1, f2]):
            r = audit(text, surface="daemon_cycle")
        self.assertTrue(r.rewritten)
        self.assertEqual(
            r.text.count("I don't have a grounded answer"), 1,
        )


# ── rewrite helper ─────────────────────────────────────────────────────

class RewriteSentenceReplace(unittest.TestCase):

    def test_noop_with_no_flags(self):
        t = "Nothing to rewrite."
        new, mode = _rewrite(t, [])
        self.assertEqual(new, t)
        self.assertEqual(mode, "noop")

    def test_single_flag_replaces_containing_sentence(self):
        text = "First sentence. Bad claim here. Third sentence."
        bad_start = text.find("Bad claim here.")
        f = Flag(kind="judge",
                 span=(bad_start, bad_start + len("Bad claim here.")),
                 text="Bad claim here.", reason="r")
        new, mode = _rewrite(text, [f])
        self.assertEqual(mode, "sentence")
        self.assertIn("First sentence.", new)
        self.assertIn("Third sentence.", new)
        self.assertNotIn("Bad claim here.", new)

    def test_version_number_not_treated_as_sentence_end(self):
        text = "I ran v2.0.0 tests. Everything was fine."
        start = text.find("v2.0.0 tests")
        s_start, s_end = _sentence_span(text, start)
        sentence = text[s_start:s_end]
        self.assertIn("v2.0.0", sentence)
        self.assertIn("tests.", sentence)

    def test_path_dotfile_not_treated_as_sentence_end(self):
        text = "I looked in ~/.local/share. Found nothing."
        start = text.find("~/.local")
        s_start, s_end = _sentence_span(text, start)
        sentence = text[s_start:s_end]
        self.assertIn("~/.local/share.", sentence)


# ── _find_flags via judge (stubbed LLM) ────────────────────────────────

class FindFlagsViaJudge(unittest.TestCase):

    def test_maps_judge_output_to_flag_spans(self):
        text = "Disk at 70%. It has been hovering for weeks. OK."
        claim = "It has been hovering for weeks."
        fake_out = [{"text": claim, "reason": "snapshot has no history"}]
        with patch("core.grounding_judge.judge", return_value=fake_out), \
             patch("core.fabrication_memory.few_shots_for", return_value=[]):
            flags = _diag_find_flags(text, signals_present=["system_stats"],
                                     signals_absent=["history"])
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].kind, "judge")
        self.assertEqual(text[flags[0].span[0]:flags[0].span[1]], claim)
        self.assertEqual(flags[0].reason, "snapshot has no history")

    def test_judge_claim_not_in_text_is_dropped(self):
        text = "Everything looks fine."
        fake_out = [{"text": "a paraphrase not in original", "reason": "r"}]
        with patch("core.grounding_judge.judge", return_value=fake_out), \
             patch("core.fabrication_memory.few_shots_for", return_value=[]):
            flags = _diag_find_flags(text, signals_present=[], signals_absent=[])
        self.assertEqual(flags, [])

    def test_empty_judge_text_skipped(self):
        text = "Some text."
        fake_out = [{"text": "", "reason": "r"}, {"text": "   ", "reason": "r"}]
        with patch("core.grounding_judge.judge", return_value=fake_out), \
             patch("core.fabrication_memory.few_shots_for", return_value=[]):
            flags = _diag_find_flags(text, signals_present=[], signals_absent=[])
        self.assertEqual(flags, [])


# ── AuditResult dataclass sanity ───────────────────────────────────────

class AuditResultShape(unittest.TestCase):

    def test_default_fields(self):
        r = AuditResult(text="hi")
        self.assertFalse(r.rewritten)
        self.assertEqual(r.mode, "noop")
        self.assertEqual(r.flags, [])
        self.assertIsNone(r.skipped_reason)


if __name__ == "__main__":
    unittest.main()
