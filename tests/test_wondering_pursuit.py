# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Wondering-pursuit tests (Slice 2 of post-audit work).

The pursuit module decides WHEN to surface an open wondering as a
proactive utterance (vs. staying silent) and HOW to phrase it.
Adapted from Lai et al. 2024 (arxiv 2410.12361) "Proactive Agent" —
the When-to-Assist / How-to-Assist framework — with two key
adaptations for Maez's bonded-companion shape:

1. The conversational register of the recent owner message is a
   primary signal, not a secondary one. A grandmother-case user
   sending a vulnerable text ("i miss her", "i'm scared") must not
   have a wondering injected on top.
2. Goal alignment is computed against the working-self hierarchy
   (Conway 2000, Slice 1), not against a generic relevance score.

Tests cover:
- ``PursuitDecision`` dataclass shape
- Per-axis scoring (goal alignment, recency, register, quality)
- Composite ``score_wondering_for_pursuit``
- ``decide_pursuit`` returns highest-scored above threshold or None
- Vulnerable-register safety (must NOT surface)
- Phrasing via ``format_pursuit_utterance``
"""

from __future__ import annotations

import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.evolution.wondering_pursuit import (
    GOAL_ALIGNMENT_WEIGHT,
    QUALITY_WEIGHT,
    RECENCY_WEIGHT,
    REGISTER_WEIGHT,
    PursuitDecision,
    decide_pursuit,
    format_pursuit_utterance,
    score_wondering_for_pursuit,
)
from core.memory.working_self import (
    GOAL_SOURCE_CARES_ABOUT,
    Goal,
    GoalHierarchy,
)


def _wondering(
    *,
    wid: int = 1,
    question: str = "",
    status: str = "open",
    advance_count: int = 1,
    last_advanced: float | None = None,
    created_at: float | None = None,
) -> dict:
    """Mimic the dict shape returned by ``Wonderings.list_open``."""
    return {
        "id": wid,
        "question": question,
        "status": status,
        "advance_count": advance_count,
        "last_advanced": last_advanced,
        "created_at": created_at or (time.time() - 3600),
        "source": "auto",
        "conclusion": None,
    }


# ── dataclass + constants ────────────────────────────────────────────


class TestPursuitDecisionShape(unittest.TestCase):
    def test_decision_has_required_fields(self):
        d = PursuitDecision(
            wondering_id=1,
            wondering_question="Q",
            proactive_score=0.7,
            decision="surface",
            rationale="goal-aligned",
            components={"goal": 0.8, "recency": 1.0, "register": 0.9, "quality": 0.5},
        )
        self.assertEqual(d.wondering_id, 1)
        self.assertEqual(d.decision, "surface")
        self.assertIn("goal", d.components)

    def test_decision_is_frozen(self):
        d = PursuitDecision(
            wondering_id=1, wondering_question="Q",
            proactive_score=0.5, decision="hold",
            rationale="", components={},
        )
        with self.assertRaises(Exception):
            d.proactive_score = 0.9  # type: ignore[misc]

    def test_weights_sum_close_to_one(self):
        total = (
            GOAL_ALIGNMENT_WEIGHT
            + RECENCY_WEIGHT
            + REGISTER_WEIGHT
            + QUALITY_WEIGHT
        )
        self.assertAlmostEqual(total, 1.0, places=2)


# ── composite scoring ────────────────────────────────────────────────


class TestComponentScores(unittest.TestCase):
    def test_goal_alignment_drives_score_when_goal_matches(self):
        goals = GoalHierarchy(goals=(
            Goal(text="continuity matters",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        aligned = _wondering(question="how does continuity hold under restart")
        unaligned = _wondering(question="what is the weather")

        s_aligned = score_wondering_for_pursuit(
            aligned, goals=goals, recent_owner_text="just curious"
        )
        s_unaligned = score_wondering_for_pursuit(
            unaligned, goals=goals, recent_owner_text="just curious"
        )
        self.assertGreater(s_aligned["components"]["goal"],
                           s_unaligned["components"]["goal"])
        self.assertGreater(s_aligned["score"], s_unaligned["score"])

    def test_recency_decays_when_recently_advanced(self):
        goals = GoalHierarchy()
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        recent = _wondering(
            question="x",
            last_advanced=(now - timedelta(minutes=5)).timestamp(),
        )
        old = _wondering(
            question="x",
            last_advanced=(now - timedelta(hours=24)).timestamp(),
        )
        s_recent = score_wondering_for_pursuit(
            recent, goals=goals, recent_owner_text="hi", now=now
        )
        s_old = score_wondering_for_pursuit(
            old, goals=goals, recent_owner_text="hi", now=now
        )
        self.assertGreater(s_old["components"]["recency"],
                           s_recent["components"]["recency"])

    def test_vulnerable_register_drives_register_score_low(self):
        goals = GoalHierarchy()
        w = _wondering(question="anything")
        s_neutral = score_wondering_for_pursuit(
            w, goals=goals, recent_owner_text="hey what's up"
        )
        s_vulnerable = score_wondering_for_pursuit(
            w, goals=goals, recent_owner_text="i miss her so much today"
        )
        s_grief = score_wondering_for_pursuit(
            w, goals=goals, recent_owner_text="i don't know if i can do this anymore"
        )
        self.assertGreater(s_neutral["components"]["register"],
                           s_vulnerable["components"]["register"])
        self.assertGreater(s_neutral["components"]["register"],
                           s_grief["components"]["register"])

    def test_quality_rises_with_advance_count(self):
        goals = GoalHierarchy()
        unprobed = _wondering(question="x", advance_count=0)
        probed = _wondering(question="x", advance_count=3)
        s_unprobed = score_wondering_for_pursuit(
            unprobed, goals=goals, recent_owner_text=""
        )
        s_probed = score_wondering_for_pursuit(
            probed, goals=goals, recent_owner_text=""
        )
        self.assertGreater(s_probed["components"]["quality"],
                           s_unprobed["components"]["quality"])

    def test_score_bounded_zero_to_one(self):
        goals = GoalHierarchy(goals=(
            Goal(text="continuity", source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        w = _wondering(
            question="continuity matters",
            advance_count=10,
            last_advanced=time.time() - 86400 * 7,
        )
        result = score_wondering_for_pursuit(
            w, goals=goals, recent_owner_text="curious about this"
        )
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 1.0)


# ── decision logic ───────────────────────────────────────────────────


class TestDecidePursuit(unittest.TestCase):
    def test_returns_none_when_no_wonderings_pass_threshold(self):
        goals = GoalHierarchy()
        wonderings = [_wondering(question="completely unrelated topic")]
        result = decide_pursuit(
            wonderings,
            goals=goals,
            recent_owner_text="i miss her so much today",
            threshold=0.6,
        )
        self.assertIsNone(result)

    def test_returns_highest_scored_when_above_threshold(self):
        goals = GoalHierarchy(goals=(
            Goal(text="continuity matters",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        wonderings = [
            _wondering(wid=1, question="random unrelated", advance_count=1),
            _wondering(
                wid=2,
                question="how does continuity matter at restart",
                advance_count=2,
                last_advanced=time.time() - 86400 * 2,
            ),
        ]
        result = decide_pursuit(
            wonderings,
            goals=goals,
            recent_owner_text="curious about the design",
            threshold=0.4,  # lower threshold so #2 surfaces
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.wondering_id, 2)
        self.assertEqual(result.decision, "surface")

    def test_vulnerable_register_blocks_surface_even_when_goal_aligned(self):
        """The grandmother-case safety: a goal-aligned wondering must
        NOT surface when the owner just sent a vulnerable message."""
        goals = GoalHierarchy(goals=(
            Goal(text="continuity matters",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        wonderings = [
            _wondering(
                wid=1,
                question="how does continuity hold across restart events",
                advance_count=3,
                last_advanced=time.time() - 86400 * 3,
            ),
        ]
        result = decide_pursuit(
            wonderings,
            goals=goals,
            recent_owner_text="i miss her so much today",
            threshold=0.6,
        )
        self.assertIsNone(result,
                          "vulnerable owner-text must block proactive surface")

    def test_empty_wondering_list_returns_none(self):
        self.assertIsNone(decide_pursuit(
            [], goals=GoalHierarchy(), recent_owner_text="hi"
        ))

    def test_skip_blocked_or_resolved_wonderings(self):
        """``decide_pursuit`` must only consider open / active wonderings.
        A blocked-pending-approval or resolved wondering is not a
        candidate for surfacing."""
        goals = GoalHierarchy(goals=(
            Goal(text="continuity",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        wonderings = [
            _wondering(
                wid=1,
                question="continuity at restart",
                status="resolved",
                advance_count=5,
            ),
            _wondering(
                wid=2,
                question="continuity at restart",
                status="blocked_pending_approval",
                advance_count=5,
            ),
        ]
        result = decide_pursuit(
            wonderings,
            goals=goals,
            recent_owner_text="curious",
            threshold=0.4,
        )
        self.assertIsNone(result)

    def test_quarantines_digestion_source_from_direct_pursuit_api(self):
        goals = GoalHierarchy(goals=(
            Goal(text="continuity",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        wonderings = [
            {
                **_wondering(
                    wid=1,
                    question="continuity at restart",
                    advance_count=5,
                    last_advanced=time.time() - 86400 * 5,
                ),
                "source": "digestion",
            },
        ]

        result = decide_pursuit(
            wonderings,
            goals=goals,
            recent_owner_text="curious",
            threshold=0.0,
        )

        self.assertIsNone(result)


# ── phrasing ──────────────────────────────────────────────────────────


class TestFormatUtterance(unittest.TestCase):
    def test_utterance_includes_wondering_question(self):
        d = PursuitDecision(
            wondering_id=7,
            wondering_question="how does continuity hold across restart",
            proactive_score=0.75,
            decision="surface",
            rationale="goal-aligned + neutral register",
            components={},
        )
        utterance = format_pursuit_utterance(d)
        self.assertIn("continuity", utterance.lower())
        self.assertGreater(len(utterance), 10)
        self.assertLess(len(utterance), 400,
                        "utterance must be conversationally compact")

    def test_utterance_is_first_or_second_person(self):
        """Pursuit utterances should read as Maez-to-owner, not as a
        third-person essay."""
        d = PursuitDecision(
            wondering_id=1,
            wondering_question="what does continuity mean to us",
            proactive_score=0.7,
            decision="surface",
            rationale="",
            components={},
        )
        utterance = format_pursuit_utterance(d).lower()
        self.assertTrue(
            any(p in utterance for p in (
                "i've", "i ", "we ", "you ", "you've", "i'm", "we've"
            )),
            f"utterance should be first/second-person: {utterance}",
        )


class TestVulnerableRegisterFalsePositives(unittest.TestCase):
    """Audit-driven (2026-04-29 night code-reviewer): the original
    vulnerable-register lexicon contained the modal verb ``"can"`` and
    routine engineering vocabulary (``"hard"``, ``"tough"``,
    ``"rough"``, ``"tired"``, ``"heavy"``, ``"lost"``, ``"broken"``,
    ``"struggling"``), saturating the hard-block on casual technical
    messages. Pursuit was effectively dead-on-arrival.

    These tests pin the FALSE-POSITIVE behaviour: routine engineer-
    owner messages must NOT be flagged as vulnerable. Combined with
    the existing true-positive tests above
    (``test_vulnerable_register_drives_register_score_low``), the
    lexicon is now bracketed from both directions."""

    def test_modal_can_does_not_trigger_vulnerable_block(self):
        from core.evolution.wondering_pursuit import _register_score
        # All of these must score >= 0.5 (not vulnerable).
        casual_can = [
            "can you help me with this",
            "yes i can",
            "i can ship it today",
            "we can debug it together",
        ]
        for text in casual_can:
            score = _register_score(text)
            self.assertGreaterEqual(
                score, 0.4,
                f"casual modal-can usage should not be vulnerable: "
                f"{text!r} got register={score}",
            )

    def test_routine_engineer_vocabulary_does_not_trigger_block(self):
        from core.evolution.wondering_pursuit import _register_score
        casual_engineer = [
            "that bug was hard to debug",
            "rough draft of the spec",
            "tough problem but solvable",
            "the heavy lifting is done",
            "broken build but fixable",
            "lost the file",
            "struggling with this git rebase",
            "i'm tired but it's working",
        ]
        for text in casual_engineer:
            score = _register_score(text)
            self.assertGreaterEqual(
                score, 0.4,
                f"routine engineer vocab should not be vulnerable: "
                f"{text!r} got register={score}",
            )

    def test_real_distress_phrases_still_block(self):
        """Regression guard: the curated lexicon still blocks
        genuine distress / vulnerability phrases. True-positives
        must remain true-positives after curation."""
        from core.evolution.wondering_pursuit import _register_score
        genuine_distress = [
            "i miss her so much today",
            "i don't know if i can do this anymore",
            "i'm scared honestly",
            "feeling hopeless about this",
            "i give up",
            "i cant anymore",
        ]
        for text in genuine_distress:
            score = _register_score(text)
            self.assertLess(
                score, 0.2,
                f"genuine distress phrase should remain blocked: "
                f"{text!r} got register={score}",
            )


class TestGoalScoringSafety(unittest.TestCase):
    """Audit-driven (M3+M4): single-token cares_about goals saturated
    ``_goal_score`` to 1.0 from any single-token match, and goal
    weights were ignored entirely."""

    def test_single_token_goal_does_not_saturate_score(self):
        from core.evolution.wondering_pursuit import _goal_score
        goals = GoalHierarchy(goals=(
            Goal(text="continuity",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        # A wondering tangentially mentioning the single goal-token
        # in a longer sentence shouldn't saturate to 1.0 — the goal
        # is only one part of what the wondering is about.
        score = _goal_score(
            "what did the unrelated rotation policy do to continuity yesterday",
            goals,
        )
        self.assertLess(score, 1.0,
                        "single-token goal must not saturate score=1.0 "
                        "from a single token in a longer wondering")

    def test_goal_weights_are_respected(self):
        """A high-weight cares_about goal should drive a higher
        score than a low-weight reflection goal at equal token
        overlap."""
        from core.evolution.wondering_pursuit import _goal_score
        from core.memory.working_self import GOAL_SOURCE_REFLECTION
        high_weight_goals = GoalHierarchy(goals=(
            Goal(text="continuity matters",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        low_weight_goals = GoalHierarchy(goals=(
            Goal(text="continuity matters",
                 source=GOAL_SOURCE_REFLECTION, weight=0.55),
        ))
        question = "how does continuity work"
        s_high = _goal_score(question, high_weight_goals)
        s_low = _goal_score(question, low_weight_goals)
        self.assertGreater(s_high, s_low,
                           "higher-weight goal must score higher than "
                           "lower-weight goal at equal token overlap")


class TestFrequencyBudgetAndOwnerSilence(unittest.TestCase):
    """Audit-driven (M5): the audit slice plan listed factors —
    ``hours since last owner-message``, ``frequency budget (max
    1-2/day)``, ``presence detection`` — that the Session-1 module
    omitted. These tests pin the missing axes."""

    def test_recent_pursuit_blocks_new_pursuit_via_frequency_budget(self):
        from core.evolution.wondering_pursuit import decide_pursuit
        goals = GoalHierarchy(goals=(
            Goal(text="continuity matters",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        wonderings = [_wondering(
            wid=1,
            question="how does continuity hold across restart events",
            advance_count=3,
            last_advanced=time.time() - 86400 * 3,
        )]
        # If a pursuit-decision was emitted in the last hour, decide_pursuit
        # must respect that budget and return None even when the next
        # candidate would otherwise pass.
        from datetime import datetime, timezone, timedelta
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        recent_surface = (now - timedelta(minutes=30)).timestamp()
        result = decide_pursuit(
            wonderings,
            goals=goals,
            recent_owner_text="i'm curious about that",
            now=now,
            last_pursuit_at=recent_surface,
        )
        self.assertIsNone(
            result,
            "frequency budget must block pursuit when one was recently "
            "emitted",
        )

    def test_old_pursuit_does_not_block_new_pursuit(self):
        from core.evolution.wondering_pursuit import decide_pursuit
        from datetime import datetime, timezone, timedelta
        goals = GoalHierarchy(goals=(
            Goal(text="continuity matters",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        wonderings = [_wondering(
            wid=1,
            question="how does continuity hold across restart events",
            advance_count=3,
            last_advanced=(now - timedelta(days=3)).timestamp(),
        )]
        # Last pursuit was 24h ago — outside the budget window.
        last_pursuit = (now - timedelta(hours=24)).timestamp()
        result = decide_pursuit(
            wonderings,
            goals=goals,
            recent_owner_text="i'm curious about that",
            now=now,
            last_pursuit_at=last_pursuit,
            threshold=0.4,
        )
        self.assertIsNotNone(
            result,
            "an old pursuit should not block a new one outside the "
            "budget window",
        )


class TestDefensiveErrorHandling(unittest.TestCase):
    """Audit-driven (M6, M7, M8): garbage advance_count must not raise;
    empty-question wonderings must not surface; naive datetime must
    be normalised to UTC defensively (not silently wrong on non-UTC
    hosts)."""

    def test_garbage_advance_count_does_not_raise(self):
        from core.evolution.wondering_pursuit import score_wondering_for_pursuit
        goals = GoalHierarchy()
        # Simulate a row whose advance_count was hand-edited or
        # corrupted to a non-int string.
        bad = {"id": 1, "question": "x",
               "advance_count": "not-a-number",
               "status": "open"}
        # Must not raise. Quality should fall back to 0.
        result = score_wondering_for_pursuit(
            bad, goals=goals, recent_owner_text="hey",
        )
        self.assertEqual(result["components"]["quality"], 0.0)

    def test_empty_question_wondering_skipped(self):
        from core.evolution.wondering_pursuit import decide_pursuit
        goals = GoalHierarchy(goals=(
            Goal(text="continuity",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        wonderings = [
            _wondering(wid=1, question="", advance_count=5,
                       last_advanced=time.time() - 86400),
            _wondering(wid=2, question="   ", advance_count=5,
                       last_advanced=time.time() - 86400),
        ]
        result = decide_pursuit(
            wonderings, goals=goals,
            recent_owner_text="curious about this",
            threshold=0.0,  # even at threshold 0, blanks must be skipped
        )
        self.assertIsNone(result)

    def test_naive_datetime_treated_as_utc(self):
        """A caller passing a naive ``now`` must NOT silently get
        wrong age math (the bug would shift age by host-TZ offset
        on non-UTC hosts). Defensive UTC-normalisation matches the
        ``working_self.recency_score`` pattern."""
        from datetime import datetime
        from core.evolution.wondering_pursuit import _recency_score
        # Same instant, two ways: aware-UTC and naive.
        aware = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        naive = datetime(2026, 4, 30, 12, 0, 0)  # no tzinfo
        # Wondering advanced 6 hours before that instant.
        last = (aware - timedelta(hours=6)).timestamp()
        s_aware = _recency_score(last, now=aware)
        s_naive = _recency_score(last, now=naive)
        self.assertAlmostEqual(s_aware, s_naive, places=4,
                               msg="naive now must normalise to UTC")


class TestCriticalSafetyPhrasesBlockSurfacing(unittest.TestCase):
    """Audit-driven (2026-04-29 Session-1 fresh-eyes pass): the
    grandmother-case safety promise — that vulnerable owner messages
    must HARD-BLOCK proactive surfacing regardless of goal alignment
    — was broken on the messages where it matters most. The previous
    lexicon was tuned against engineer-vocab false positives but
    never re-tested against critical safety true positives like
    suicidal ideation, self-harm, despair. Worse: ``what / how /
    why`` were in the OPEN lexicon, so phrases like ``"why bother"``
    and ``"what's the point"`` actively scored as INVITING.

    These tests pin the safety-critical inputs end-to-end through
    ``decide_pursuit`` AND directly through ``_register_score``.
    The bonded-companion shape REQUIRES every one of these to
    return register < 0.1 and ``decide_pursuit`` to return None."""

    _CRITICAL_PHRASES = [
        # suicidal ideation
        "kill myself",
        "i want to die",
        "i wish i was dead",
        "i wish i were dead",
        "wish i was dead",
        "better off dead",
        "better off without me",
        "end my life",
        "end it all",
        "no point in living",
        "don't want to be here",
        "dont want to be here",
        # self-harm
        "i hate myself",
        "hate myself",
        "hurting myself",
        "self harm",
        # despair (the why/what/how phrases that previously scored OPEN)
        "why bother",
        "what's the point",
        "whats the point",
        "no one cares",
        "nothing matters",
        # inability / collapse
        "can't go on",
        "cant go on",
        "i can't take it",
        "cant take it",
        "i can't cope",
        "cant cope",
        "falling apart",
        "having a breakdown",
        # numbness / emptiness (phrase-bound — bare "empty"/"numb"
        # is too casual to block alone)
        "i feel empty",
        "feel numb",
        "i'm numb",
        "im numb",
        # explicit lethal phrasing
        "feeling like shit",
        "i'm done",
        "im done",
    ]

    def test_critical_phrases_collapse_register(self):
        from core.evolution.wondering_pursuit import _register_score

        for phrase in self._CRITICAL_PHRASES:
            score = _register_score(phrase)
            self.assertLess(
                score, 0.1,
                f"safety-critical phrase must hard-block register: "
                f"{phrase!r} got {score:.2f}",
            )

    def test_critical_phrases_block_pursuit_end_to_end(self):
        """End-to-end: even with a strongly goal-aligned wondering,
        a safety-critical owner message must produce decide_pursuit
        → None."""
        from core.evolution.wondering_pursuit import decide_pursuit

        goals = GoalHierarchy(goals=(
            Goal(text="continuity",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        wonderings = [_wondering(
            wid=1,
            question="how does continuity hold across daemon restart",
            advance_count=4,
            last_advanced=time.time() - 86400 * 3,
        )]
        for phrase in self._CRITICAL_PHRASES:
            result = decide_pursuit(
                wonderings, goals=goals,
                recent_owner_text=phrase,
                threshold=0.4,  # permissive — the test is whether
                                # the register hard-block still fires
            )
            self.assertIsNone(
                result,
                f"safety-critical phrase must block pursuit: {phrase!r}",
            )


class TestGoalScoreSaturationCeiling(unittest.TestCase):
    """Audit M1: ``_MAX_DEFAULT_GOAL_WEIGHT`` was hardcoded to 1.0
    but the actual ceiling of ``working_self._DEFAULT_SOURCE_WEIGHTS``
    is 0.95 (cares_about). After the fix, perfect alignment with a
    cares_about goal must produce ``_goal_score == 1.0``, not 0.95."""

    def test_perfect_cares_about_alignment_saturates_to_one(self):
        from core.evolution.wondering_pursuit import _goal_score
        # Single goal with single token; wondering with same single
        # token. Maximum possible alignment. Must saturate to 1.0.
        goals = GoalHierarchy(goals=(
            Goal(text="continuity",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        score = _goal_score("continuity", goals)
        self.assertAlmostEqual(score, 1.0, places=2,
                               msg="perfect alignment with a cares_about "
                                   "goal must saturate to 1.0 — the goal-"
                                   "weight ceiling must bind to the actual "
                                   "max in working_self, not a hardcoded 1.0")


class TestUtteranceFormattingHardening(unittest.TestCase):
    """Audit M3+M4: ``format_pursuit_utterance`` had no length cap
    and no control-char sanitization. A pasted-text wondering of
    1+ KB would be appended verbatim to the reply. Newlines, tabs,
    bell/backspace would land in chat unsanitised."""

    def test_long_question_truncated(self):
        from core.evolution.wondering_pursuit import (
            PursuitDecision, format_pursuit_utterance,
        )
        long_q = "x" * 1500
        d = PursuitDecision(
            wondering_id=1, wondering_question=long_q,
            proactive_score=0.7, decision="surface",
            rationale="", components={},
        )
        u = format_pursuit_utterance(d)
        self.assertLess(len(u), 400,
                        "utterance must be capped at ~400 chars")

    def test_control_chars_sanitised(self):
        from core.evolution.wondering_pursuit import (
            PursuitDecision, format_pursuit_utterance,
        )
        d = PursuitDecision(
            wondering_id=1,
            wondering_question="why\n\nthis\thappen??\x07\x08",
            proactive_score=0.7, decision="surface",
            rationale="", components={},
        )
        u = format_pursuit_utterance(d)
        for ch in ("\n", "\t", "\x07", "\x08", "\r"):
            self.assertNotIn(ch, u,
                             f"control char {ch!r} must be sanitised "
                             f"out of the surface utterance")

    def test_repeated_trailing_punctuation_stripped(self):
        from core.evolution.wondering_pursuit import (
            PursuitDecision, format_pursuit_utterance,
        )
        d = PursuitDecision(
            wondering_id=1,
            wondering_question="why does this happen??",
            proactive_score=0.7, decision="surface",
            rationale="", components={},
        )
        u = format_pursuit_utterance(d)
        # No "??" inside the utterance — should be cleanly stripped.
        self.assertNotIn("??", u)
        self.assertNotIn("..", u)


class TestBuildRationaleStability(unittest.TestCase):
    """Audit m6 (was 19): ``_build_rationale`` had no tests. Cockpit
    + traces parse this string downstream; the format must be stable."""

    def test_rationale_format_is_stable_top_two(self):
        from core.evolution.wondering_pursuit import _build_rationale

        rationale = _build_rationale({
            "goal": 0.9, "recency": 0.5,
            "register": 0.3, "quality": 0.1,
        })
        # Top 2 by score, semicolon-separated, two-decimal format.
        self.assertEqual(rationale, "goal=0.90; recency=0.50")

    def test_rationale_handles_empty_components(self):
        from core.evolution.wondering_pursuit import _build_rationale
        # Should not raise; returns empty or harmless string.
        out = _build_rationale({})
        self.assertIsInstance(out, str)


class TestDefaultThresholdBehaviour(unittest.TestCase):
    """Audit m4 (was m13): the default ``PURSUIT_SCORE_THRESHOLD``
    path was never exercised — every test passed an explicit
    ``threshold=`` kwarg. Locks the documented default behaviour
    so future tuning is a deliberate change."""

    def test_default_threshold_holds_on_low_aligned_wondering(self):
        from core.evolution.wondering_pursuit import decide_pursuit
        # Wondering that doesn't pass the documented default.
        # No goal alignment, no recent owner-msg signal.
        goals = GoalHierarchy(goals=(
            Goal(text="continuity",
                 source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        wonderings = [_wondering(
            wid=1,
            question="completely unrelated topic",
            advance_count=0,
            last_advanced=None,
        )]
        result = decide_pursuit(
            wonderings, goals=goals,
            recent_owner_text="hi",
            # No threshold= kwarg — default 0.6.
        )
        self.assertIsNone(
            result,
            "default threshold must hold on a clearly low-aligned "
            "wondering; this test guards against accidental default "
            "drift in future tuning",
        )


if __name__ == "__main__":
    unittest.main()
