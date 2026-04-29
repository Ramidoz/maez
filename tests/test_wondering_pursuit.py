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


if __name__ == "__main__":
    unittest.main()
