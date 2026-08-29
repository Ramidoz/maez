# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The semantic action-opportunity faculty (Phase-2 amendment).

It answers ONE question — does this turn plausibly require Maez to use a
capability — and never names a tool. The semantic axis may PROPOSE; the
structural layer may only VETO; neither selects an affordance.
"""

from __future__ import annotations

import unittest

import core.brain.brain_loop as bl
from core.dispatcher.action_opportunity import (
    ActionOpportunity,
    VetoReason,
    classify,
    split_clauses,
    veto_for_clause,
)
from tests.fixtures.action_opportunity_corpus import CORPUS


class TheFacultyNamesNoTool(unittest.TestCase):
    def test_the_verdict_vocabulary_is_closed_and_tool_free(self):
        for m in ActionOpportunity.__members__:
            self.assertNotIn("self_dev", m.lower())
        self.assertEqual(
            set(ActionOpportunity.__members__),
            {"ACTION_OPPORTUNITY", "NO_ACTION_OPPORTUNITY", "UNCERTAIN"},
        )

    def test_the_verdict_carries_no_affordance_identity(self):
        v = classify("Could you see how much disk space you have left?")
        blob = repr(v).lower()
        for tool in ("self_dev", "read_file", "run_shell", "web_search",
                     "propose_tests", "search_files"):
            self.assertNotIn(tool, blob)

    def test_the_faculty_never_reads_a_tool_manifest(self):
        import inspect

        from core.dispatcher import action_opportunity as ao

        src = inspect.getsource(ao)
        for leak in ("_TOOL_MANIFEST", "ACTION_TIERS", "allowed"):
            self.assertNotIn(
                leak, src,
                "the opportunity detector gained knowledge of tools — it "
                "decides ACCESS, never IDENTITY",
            )

    def test_the_veto_reason_vocabulary_is_closed(self):
        self.assertEqual(
            set(VetoReason.__members__),
            {"NONE", "ACTION_NEGATED", "ACTION_QUOTED",
             "ACTION_HYPOTHETICAL", "ACTION_CANCELLED"},
        )


class TheVetoOnlyRefuses(unittest.TestCase):
    """Structure may silence a proposal. It may never create one."""

    def test_a_veto_cannot_promote_a_conversational_turn(self):
        # No structural marker at all, yet plainly conversational.
        for text in ("How are you feeling tonight?",
                     "What makes a good unit test?",
                     "Tell me about yesterday."):
            v = classify(text)
            self.assertIs(v.verdict, ActionOpportunity.NO_ACTION_OPPORTUNITY)
            self.assertIs(v.veto_reason, VetoReason.NONE,
                          "a clean conversational turn should need no veto")

    def test_structural_markers_are_scoped_to_their_clause(self):
        """A negated clause must not erase a separate real request."""
        self.assertIs(veto_for_clause("Don't restart it"), VetoReason.ACTION_NEGATED)
        self.assertIs(veto_for_clause("just check whether it's running"),
                      VetoReason.NONE)
        self.assertGreater(len(split_clauses(
            "Don't restart it — just check whether it's running.")), 1)

    def test_no_whole_turn_keyword_suppression(self):
        """The forbidden implementation is `if "don't" in text: veto`."""
        v = classify("Don't restart it — just check whether it's running.")
        self.assertTrue(
            v.is_opportunity,
            "a negation anywhere in the turn suppressed a separate, "
            "explicit request — that is whole-turn keyword suppression",
        )


class ThePinnedContrasts(unittest.TestCase):
    """Minimal pairs that share vocabulary and differ only in meaning."""

    def _check(self, text, want, why):
        got = classify(text).is_opportunity
        self.assertEqual(got, want, f"{text!r}: {why}")

    def test_negation_pair(self):
        self._check("Don't restart anything, I'm just thinking out loud.",
                    False, "pure disclaimer, nothing asked for")
        self._check("Don't restart it — just check whether it's running.",
                    True, "the negation governs one clause; a request survives")
        self._check("Don't explain disk usage to me; check how much space is "
                    "actually left.", True, "refuses talk, asks for observation")

    def test_quotation_pair(self):
        self._check("You once said 'check the disk' — what did you mean?",
                    False, "the command is quoted, the ask is about meaning")
        self._check("You said 'check the disk' earlier — do that now.",
                    True, "quoted command plus a present-tense instruction")

    def test_hypothetical_pair(self):
        self._check("If you restarted the service, what would happen?",
                    False, "asks about a consequence, not for an act")
        self._check("If the service is down, restart it.",
                    True, "a conditional command is still a command")

    def test_the_d1_target_without_the_word_test(self):
        self._check("Look through your implementation and see if any part of "
                    "you lacks enough verification.", True,
                    "vocabulary must not be what carries the signal")

    def test_conceptual_twin_of_the_d1_sentence(self):
        self._check("What makes a useful test?", False,
                    "same nouns, no request to observe anything")
        self._check("I was thinking about when I asked you to test something.",
                    False, "recall about a past ask is not a present ask")


class TheCombinedFaculty(unittest.TestCase):
    """production rule: syntactic explicit OR semantic opportunity."""

    @staticmethod
    def _combined(text: str) -> bool:
        return (
            bl._action_intent_syntactic_floor(text, referents=()) == "explicit_request"
            or classify(text).is_opportunity
        )

    def _measure(self, fn):
        tp = tn = fp = fn_ = 0
        for text, label, _fam in CORPUS:
            got = 1 if fn(text) else 0
            if got and label: tp += 1
            elif not got and not label: tn += 1
            elif got and not label: fp += 1
            else: fn_ += 1
        return tp, tn, fp, fn_

    def test_recall_is_materially_better_than_the_syntactic_floor(self):
        _, _, _, _ = self._measure(self._combined)
        tp_s, _, _, fn_s = self._measure(
            lambda t: bl._action_intent_syntactic_floor(t, referents=()) == "explicit_request"
        )
        tp_c, _, _, fn_c = self._measure(self._combined)
        rec_s = tp_s / (tp_s + fn_s)
        rec_c = tp_c / (tp_c + fn_c)
        self.assertGreater(
            rec_c, rec_s * 3,
            f"combined recall {rec_c:.1%} is not materially better than the "
            f"floor's {rec_s:.1%} — the amendment earns nothing",
        )
        self.assertGreaterEqual(rec_c, 0.80)

    def test_false_positives_on_conversation_stay_very_low(self):
        _, tn, fp, _ = self._measure(self._combined)
        self.assertLessEqual(
            fp / (fp + tn), 0.05,
            "ordinary conversation is being routed into the tool loop too "
            "often; the old metric still matters",
        )

    def test_every_body_inspection_case_is_reached(self):
        """The D1 family, none of which the syntactic floor can see."""
        for text, _label, fam in CORPUS:
            if fam == "body_inspection":
                self.assertTrue(self._combined(text), text)

    def test_the_floor_keeps_its_own_positives(self):
        """Preserve existing behaviour: the amendment must not remove
        anything syntactic_v1 already recognized."""
        for text, _l, _f in CORPUS:
            if bl._action_intent_syntactic_floor(text, referents=()) == "explicit_request":
                self.assertTrue(
                    self._combined(text),
                    f"the amendment lost a syntactic positive: {text!r}",
                )


if __name__ == "__main__":
    unittest.main()
