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
    _rewrite, _sentence_span, _looks_obviously_clean,
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
        with patch("core.self_claim_audit._find_flags", return_value=([], True)):
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
        with patch("core.self_claim_audit._find_flags", return_value=([flag], True)):
            r = audit(text, surface="daemon_cycle")
        self.assertTrue(r.rewritten)
        self.assertEqual(r.mode, "sentence")
        self.assertIn("I don't have a grounded answer for that part.", r.text)
        self.assertNotIn("upward trend suggests a leak", r.text)

    def test_judge_failure_fails_open(self):
        """_find_flags must swallow judge exceptions. Returns ([], False)
        so the caller can emit 'judge_unavailable' telemetry."""
        from core.self_claim_audit import _find_flags
        with patch("core.grounding_judge.judge",
                   side_effect=Exception("boom")):
            flags, available = _find_flags(
                "some text", signals_present=[], signals_absent=[],
            )
        self.assertEqual(flags, [])
        self.assertFalse(available)

    def test_audit_emits_judge_unavailable_when_judge_down(self):
        """When judge raises, audit must still return the original text
        but tag mode=judge_unavailable via the AuditResult."""
        with patch("core.grounding_judge.judge",
                   side_effect=Exception("llama-server down")), \
             patch("core.fabrication_memory.few_shots_for", return_value=[]):
            r = audit(
                "A claim-shaped sentence about some specific state.",
                surface="daemon_cycle",
            )
        self.assertFalse(r.rewritten)
        self.assertEqual(r.skipped_reason, "judge_unavailable")

    def test_multiple_flags_in_same_sentence_replace_once(self):
        text = "The upward trend is leaking disk."
        f1 = Flag(kind="judge", span=(0, 16), text="The upward trend",
                  reason="no history")
        f2 = Flag(kind="judge", span=(20, 32), text="leaking disk",
                  reason="no trend")
        with patch("core.self_claim_audit._find_flags", return_value=([f1, f2], True)):
            r = audit(text, surface="daemon_cycle")
        self.assertTrue(r.rewritten)
        self.assertEqual(
            r.text.count("I don't have a grounded answer"), 1,
        )


# ── rewrite helper ─────────────────────────────────────────────────────

class PreFilter(unittest.TestCase):
    """Pre-filter must skip the judge on obviously-clean replies and
    route everything else through. Fail-safe: only skip when highly
    confident."""

    def test_very_short_texts_are_clean(self):
        self.assertTrue(_looks_obviously_clean(""))
        self.assertTrue(_looks_obviously_clean("ok"))
        self.assertTrue(_looks_obviously_clean("got it"))

    def test_pure_refusals_are_clean(self):
        self.assertTrue(_looks_obviously_clean("I don't have a screen signal."))
        self.assertTrue(_looks_obviously_clean("I cannot see that."))
        self.assertTrue(_looks_obviously_clean("I don't recall."))

    def test_future_intent_is_clean(self):
        self.assertTrue(_looks_obviously_clean("I'll keep monitoring."))
        self.assertTrue(_looks_obviously_clean("I'll check later"))

    def test_sentinel_phrases_are_clean(self):
        self.assertTrue(_looks_obviously_clean("HEARTBEAT_OK"))
        self.assertTrue(_looks_obviously_clean(
            "I don't have a grounded answer for that part."
        ))

    def test_claim_shaped_sentences_NOT_clean(self):
        # These MUST fall through to the judge, not get skipped.
        for risky in [
            "The disk has been trending upward for weeks.",
            "I'm scanning /var/log for growth culprits.",
            "Rohit has been working on the refactor all afternoon.",
            "My Orchestrator v2 handles that.",
            "CPU at 45%, RAM at 30%, disk at 70%.",  # grounded but audit-worthy
        ]:
            self.assertFalse(
                _looks_obviously_clean(risky),
                f"risky claim incorrectly pre-filtered as clean: {risky!r}",
            )

    def test_multi_sentence_never_clean(self):
        # Even if both sentences match no-fab patterns individually, a
        # multi-sentence response is always judge-worthy.
        text = "Okay. I'll keep monitoring."
        self.assertFalse(_looks_obviously_clean(text))

    def test_audit_skips_judge_on_clean_prefilter(self):
        """When pre-filter says clean, audit must not call the judge."""
        from unittest.mock import patch
        with patch("core.self_claim_audit._find_flags") as mock_find:
            r = audit("I'll keep monitoring.", surface="chat")
            mock_find.assert_not_called()
        self.assertFalse(r.rewritten)
        self.assertEqual(r.mode, "noop")

    def test_audit_runs_judge_on_non_clean(self):
        """Claim-shaped text must fall through to the judge."""
        from unittest.mock import patch
        with patch("core.self_claim_audit._find_flags",
                   return_value=([], True)) as mock_find:
            audit("The disk has been trending upward for weeks.",
                      surface="chat")
            mock_find.assert_called_once()


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


class MultiSentenceFlagSpan(unittest.TestCase):
    """A single flag whose span covers more than one sentence must
    replace ALL overlapped sentences, not just the first."""

    def test_two_sentence_claim_replaces_both(self):
        # Five sentences total; one flag spans 2 of them. 2/5 = 40% stays
        # under the short-circuit threshold so we exercise multi-sentence
        # replace specifically.
        text = (
            "I'm scanning /var/log now. The trend is upward over 3 cycles. "
            "CPU is fine. RAM looks okay. Disk at 70%."
        )
        claim = "I'm scanning /var/log now. The trend is upward over 3 cycles."
        start = text.find(claim)
        flag = Flag(
            kind="judge",
            span=(start, start + len(claim)),
            text=claim,
            reason="false action + snapshot-as-trend",
        )
        new, mode = _rewrite(text, [flag])
        self.assertEqual(mode, "sentence")
        # Both fabricated sentences gone
        self.assertNotIn("I'm scanning /var/log", new)
        self.assertNotIn("trend is upward", new)
        # Control sentences preserved
        self.assertIn("CPU is fine.", new)
        self.assertIn("RAM looks okay.", new)
        self.assertIn("Disk at 70%.", new)


class ShortCircuitRewrite(unittest.TestCase):
    """When ≥50% of sentences are flagged (and ≥2 flagged), the whole
    response is replaced rather than punctuating fragments with sentinels."""

    def test_short_circuits_when_majority_flagged(self):
        text = "First bad claim. Second bad claim. Third sentence is fine."
        f1 = Flag(kind="judge", span=(0, 16), text="First bad claim.", reason="r")
        f2 = Flag(
            kind="judge",
            span=(text.find("Second"), text.find("Second") + len("Second bad claim.")),
            text="Second bad claim.", reason="r",
        )
        new, mode = _rewrite(text, [f1, f2])
        self.assertEqual(mode, "shortcircuit")
        self.assertEqual(
            new, "I don't have a grounded answer for this right now.",
        )

    def test_single_flag_below_threshold_uses_sentence_mode(self):
        text = "First bad claim. Second is fine. Third is fine. Fourth is fine."
        f1 = Flag(kind="judge", span=(0, 16), text="First bad claim.", reason="r")
        new, mode = _rewrite(text, [f1])
        self.assertEqual(mode, "sentence")
        self.assertIn("Second is fine.", new)

    def test_two_flags_below_ratio_uses_sentence_mode(self):
        # 2 flagged out of 5 sentences = 40% < 50% threshold
        text = ("Bad one. Bad two. Fine three. Fine four. Fine five.")
        f1 = Flag(kind="judge", span=(0, 8), text="Bad one.", reason="r")
        f2 = Flag(
            kind="judge",
            span=(text.find("Bad two."), text.find("Bad two.") + 8),
            text="Bad two.", reason="r",
        )
        new, mode = _rewrite(text, [f1, f2])
        self.assertEqual(mode, "sentence")
        self.assertIn("Fine three.", new)
        self.assertIn("Fine four.", new)
        self.assertIn("Fine five.", new)

    def test_existing_audit_sentinel_never_gets_duplicated(self):
        text = (
            'I was repeating the fallback phrase "I don\'t have a grounded '
            'answer for that part." Everything else is stable.'
        )
        claim = "Everything else is stable."
        start = text.find(claim)
        flag = Flag(
            kind="judge",
            span=(start, start + len(claim)),
            text=claim,
            reason="no live system signal",
        )

        new, mode = _rewrite(text, [flag])

        self.assertEqual(mode, "shortcircuit")
        self.assertEqual(
            new, "I don't have a grounded answer for this right now.",
        )
        self.assertEqual(new.count("I don't have a grounded answer"), 1)


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
