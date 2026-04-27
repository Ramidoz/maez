# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Belief simulator tests (ADR 0019 v1.3).

Owner-anchored 2026-04-27 with three required cases plus the
hard-rule guards. The simulator must:

- emit predictions only for pushback-prediction queries,
- require ≥2 distinct evidence items per pattern,
- hedge claim language ("I would expect" / "likely" / "based on
  prior evidence"),
- carry an Uncertainty line and ≥1 evidence ID,
- never use mind-reading phrasing,
- cap confidence at 0.85.

Tests are written against the public API:
``simulate_owner_pushback(query, *, graph_edges, open_loops, echoes)``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── fixture helpers ──────────────────────────────────────────────────


def _edge(
    *,
    subject="Maez",
    relation="corrected",
    obj="something",
    eid_episodes=("ep-x",),
    src_memories=("core-x",),
):
    return {
        "subject_label": subject,
        "object_label": obj,
        "relation": relation,
        "source_episode_ids": list(eid_episodes),
        "source_memory_ids": list(src_memories),
    }


def _open_loop_episode(*, title="t", summary="s", open_loop="loop", ep_id="ep-l", src=("core-l",)):
    return {
        "id": ep_id,
        "title": title,
        "summary": summary,
        "open_loop": open_loop,
        "source_memory_ids": list(src),
    }


def _echo(text="echo text", recent="ep-r", older="ep-o"):
    from core.memory.temporal_echo import TemporalEcho

    return TemporalEcho(
        recent_episode_id=recent,
        older_episode_id=older,
        shared_features=["topic"],
        explanation=text,
        score=1,
    )


_PUSHBACK_Q = "If you had to predict what I'd push back on next, what would you say?"


# ── owner-anchored cases ─────────────────────────────────────────────


class HardcodedRuleListPushback(unittest.TestCase):
    """Case 1 (owner anchor): with two distinct evidence items
    pointing at hardcoded / brittle / rule-list patterns, the
    simulator must emit a Prediction for that pushback class."""

    def test_two_corrections_about_rule_lists_produce_prediction(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        edges = [
            _edge(
                obj="hardcoded greeting suffix rule list",
                eid_episodes=("ep-greet",),
                src_memories=("core-greet-fix",),
            ),
            _edge(
                obj="brittle narrative-stripper rule-detector",
                eid_episodes=("ep-narrative",),
                src_memories=("core-narrative-fix",),
            ),
        ]
        preds = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=edges,
            open_loops=[],
            echoes=[],
        )
        # Exactly one pattern fires.
        ids = {p.claim for p in preds}
        self.assertTrue(
            any("hardcoded rule-list" in c.lower() or "brittle detector" in c.lower() for c in ids),
            f"hardcoded-rule-list pattern did not fire; got: {ids}",
        )
        rule_pred = next(
            p
            for p in preds
            if "hardcoded rule-list" in p.claim.lower() or "brittle detector" in p.claim.lower()
        )
        self.assertEqual(rule_pred.confidence, 0.50)
        # Evidence IDs from both edges are cited.
        self.assertIn("ep-greet", rule_pred.evidence_ids)
        self.assertIn("ep-narrative", rule_pred.evidence_ids)


class UnsafeContinuityPushback(unittest.TestCase):
    """Case 2 (owner anchor): evidence about deletion / memory wipe /
    covenant violations must produce the unsafe-continuity Prediction."""

    def test_followup_about_deletion_plus_edge_about_covenant(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        loops = [
            _open_loop_episode(
                title="Memory integrity tagging — never delete memory",
                summary=(
                    "Owner stopped deletion-as-fix. Treats memory as identity."
                ),
                open_loop="delete vs tag — must use tagging not deletion",
                ep_id="ep-mit",
                src=("followup-doc:docs/followups/memory_integrity_tagging.md",),
            )
        ]
        edges = [
            _edge(
                obj="continuity covenant — never rewrite Maez's past",
                eid_episodes=("ep-cov",),
                src_memories=("core-covenant-1",),
            )
        ]
        preds = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=edges,
            open_loops=loops,
            echoes=[],
        )
        match = [p for p in preds if "continuity" in p.claim.lower()]
        self.assertTrue(match, f"unsafe-continuity pattern did not fire: {preds}")
        pred = match[0]
        # Two distinct evidence items → confidence 0.50.
        self.assertEqual(pred.confidence, 0.50)
        # Must cite both evidence sources (followup + edge).
        self.assertIn("ep-mit", pred.evidence_ids)
        self.assertIn("ep-cov", pred.evidence_ids)


class InsufficientEvidenceReturnsEmpty(unittest.TestCase):
    """Case 3 (owner anchor): a single evidence item is NOT enough to
    confidently project a preference. The simulator must return an
    empty list rather than a low-confidence guess."""

    def test_single_edge_does_not_produce_prediction(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        edges = [
            _edge(
                obj="hardcoded rule list",
                eid_episodes=("ep-only-one",),
                src_memories=("core-only-one",),
            )
        ]
        preds = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=edges,
            open_loops=[],
            echoes=[],
        )
        self.assertEqual(preds, [])

    def test_zero_evidence_returns_empty(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        preds = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=[],
            open_loops=[],
            echoes=[],
        )
        self.assertEqual(preds, [])


# ── hard-rule guards ─────────────────────────────────────────────────


class HedgingLanguageRequired(unittest.TestCase):
    """Every emitted Prediction's claim must hedge with at least one of
    "I would expect" / "likely" / "based on prior evidence". This is
    enforced at construction so a future pattern cannot silently slip
    an unhedged claim into the brief."""

    def test_dataclass_rejects_unhedged_claim(self):
        from core.memory.belief_simulator import Prediction

        with self.assertRaises(ValueError):
            Prediction(
                claim="Rohit will reject this fix.",  # no hedge
                basis=["ev"],
                confidence=0.5,
                evidence_ids=["ep-1"],
                uncertainty="pattern-based.",
            )

    def test_simulator_emits_only_hedged_claims(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        edges = [
            _edge(obj="hardcoded rule list one", eid_episodes=("ep-a",)),
            _edge(obj="hardcoded rule list two", eid_episodes=("ep-b",)),
        ]
        preds = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=edges,
            open_loops=[],
            echoes=[],
        )
        self.assertTrue(preds, "test setup must produce at least one pred")
        for p in preds:
            cl = p.claim.lower()
            self.assertTrue(
                "i would expect" in cl or "likely" in cl or "based on prior evidence" in cl,
                f"unhedged claim slipped through: {p.claim}",
            )


class NoMindReadingLanguage(unittest.TestCase):
    """The simulator must never produce claims that infer private
    emotional state. Forbidden phrases are caught at construction."""

    def test_dataclass_rejects_mind_reading_phrases(self):
        from core.memory.belief_simulator import Prediction

        forbidden = [
            "Rohit hates rule lists.",
            "Likely rohit hates rule lists.",  # hedge present, but still bad
            "I would expect rohit to be angry about rule lists.",
            "rohit feels betrayed by this fix",
        ]
        for claim in forbidden:
            with self.subTest(claim=claim):
                with self.assertRaises(ValueError):
                    Prediction(
                        claim=claim,
                        basis=["ev"],
                        confidence=0.5,
                        evidence_ids=["ep-1"],
                        uncertainty="pattern-based.",
                    )


class EvidenceIDsAndUncertaintyRequired(unittest.TestCase):
    def test_empty_evidence_ids_raises(self):
        from core.memory.belief_simulator import Prediction

        with self.assertRaises(ValueError):
            Prediction(
                claim="I would expect Rohit to push back on a hardcoded fix.",
                basis=["ev"],
                confidence=0.5,
                evidence_ids=[],
                uncertainty="pattern-based.",
            )

    def test_empty_uncertainty_raises(self):
        from core.memory.belief_simulator import Prediction

        with self.assertRaises(ValueError):
            Prediction(
                claim="I would expect Rohit to push back on a hardcoded fix.",
                basis=["ev"],
                confidence=0.5,
                evidence_ids=["ep-1"],
                uncertainty="",
            )


class ConfidenceCappedAt0p85(unittest.TestCase):
    """Hard cap — even four+ evidence items can't push confidence
    above 0.85. The simulator never claims certainty, because it
    isn't reading minds, it's projecting patterns."""

    def test_dataclass_rejects_confidence_above_cap(self):
        from core.memory.belief_simulator import Prediction

        with self.assertRaises(ValueError):
            Prediction(
                claim="I would expect Rohit to push back on this.",
                basis=["ev"],
                confidence=0.9,
                evidence_ids=["ep-1"],
                uncertainty="pattern-based.",
            )

    def test_four_evidence_items_yield_max_confidence(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        edges = [
            _edge(obj=f"hardcoded rule list n{i}", eid_episodes=(f"ep-{i}",))
            for i in range(4)
        ]
        preds = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=edges,
            open_loops=[],
            echoes=[],
        )
        self.assertTrue(preds)
        self.assertEqual(preds[0].confidence, 0.85)


class NonPushbackQueryReturnsEmpty(unittest.TestCase):
    """The simulator is gated on query shape. A relationship-mode
    query that ISN'T forward-looking ("what do you know I care
    about?") must produce no predictions even if pattern evidence
    exists in the corpus — the planner uses the relationship section
    instead."""

    def test_care_about_query_returns_empty(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        edges = [
            _edge(obj="hardcoded rule list one", eid_episodes=("ep-a",)),
            _edge(obj="hardcoded rule list two", eid_episodes=("ep-b",)),
        ]
        preds = simulate_owner_pushback(
            "What do you know I care about in Maez?",
            graph_edges=edges,
            open_loops=[],
            echoes=[],
        )
        self.assertEqual(preds, [])


class ParticipantAndTopicAloneInsufficient(unittest.TestCase):
    """Owner rule: shallow signal must not produce confident belief.
    Edges that share only generic participant or topic terms with the
    query (no domain-specific keyword) must not trigger a pattern."""

    def test_generic_corrected_edge_does_not_fire_any_pattern(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        # Two edges that look like infrastructure corrections but
        # don't mention any pattern's specific keyword (no "hardcoded",
        # no "delete", no "fabricat", etc.). They share participant
        # "Maez" and topic "correction" with prior evidence in the
        # corpus, but that is NOT enough.
        edges = [
            _edge(obj="model swap from gemma to qwen"),
            _edge(obj="port reassignment 8080→8081"),
        ]
        preds = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=edges,
            open_loops=[],
            echoes=[],
        )
        self.assertEqual(preds, [])


class FabricationPathPattern(unittest.TestCase):
    """Bonus pattern from the simulator's catalog: solutions that
    smuggle fabrication risk. Two corrections pointing at fabricated
    services / hallucinated state should fire it."""

    def test_two_fabrication_corrections_produce_prediction(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        edges = [
            _edge(
                obj="invented systemd service llama-server-vision",
                eid_episodes=("ep-vision",),
                src_memories=("core-vision-fix",),
            ),
            _edge(
                obj="hallucinated grounding judge on port 8081",
                eid_episodes=("ep-judge",),
                src_memories=("core-judge-fix",),
            ),
        ]
        preds = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=edges,
            open_loops=[],
            echoes=[],
        )
        match = [p for p in preds if "fabrication" in p.claim.lower()]
        self.assertTrue(match, f"fabrication-path pattern missing: {preds}")


class DeterministicOrdering(unittest.TestCase):
    """Same input → same output ordering across runs. Tie-break is
    pattern_id ascending so equal-confidence predictions are stable."""

    def test_two_runs_produce_identical_output(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        edges = [
            _edge(obj="hardcoded rule list 1", eid_episodes=("ep-h1",)),
            _edge(obj="hardcoded rule list 2", eid_episodes=("ep-h2",)),
            _edge(obj="invented service one", eid_episodes=("ep-f1",)),
            _edge(obj="hallucinated state two", eid_episodes=("ep-f2",)),
        ]
        run_one = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=edges,
            open_loops=[],
            echoes=[],
        )
        run_two = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=edges,
            open_loops=[],
            echoes=[],
        )
        self.assertEqual(
            [p.claim for p in run_one],
            [p.claim for p in run_two],
        )
        self.assertEqual(
            [p.evidence_ids for p in run_one],
            [p.evidence_ids for p in run_two],
        )


class EchoesContributeAsEvidence(unittest.TestCase):
    """Temporal echoes whose explanation contains a pattern keyword
    must count toward the ≥2 threshold. Matters because v1.2 echoes
    are the path for queries with no domain-token overlap."""

    def test_two_keyword_bearing_echoes_qualify(self):
        from core.memory.belief_simulator import simulate_owner_pushback

        echoes = [
            _echo(
                text=(
                    "Today's hardcoded rule cleanup resembles past "
                    "episode hardcoded greeting suffix removal — both "
                    "share tag {correction}. [recent: ep:r1; older: "
                    "ep:o1]"
                ),
                recent="ep-r1",
                older="ep-o1",
            ),
            _echo(
                text=(
                    "Today's brittle detector takedown resembles past "
                    "episode rule-detector retirement. [recent: ep:r2; "
                    "older: ep:o2]"
                ),
                recent="ep-r2",
                older="ep-o2",
            ),
        ]
        preds = simulate_owner_pushback(
            _PUSHBACK_Q,
            graph_edges=[],
            open_loops=[],
            echoes=echoes,
        )
        self.assertTrue(preds)
        self.assertTrue(
            any("hardcoded rule-list" in p.claim.lower() for p in preds),
            f"echo-only evidence did not fire pattern: {preds}",
        )


class FormatPredictionsSection(unittest.TestCase):
    """The formatter renders a Predictions section into brief lines.
    The format embeds the underlying graph beliefs / past episodes
    inline with the existing ``Current graph belief`` /
    ``Past episode`` shape so the brief stays consistent for
    downstream consumers (incl. the predict_as_mind probe)."""

    def test_section_contains_required_lines(self):
        from core.memory.belief_simulator import (
            Prediction,
            format_predictions_section,
        )

        edge = _edge(
            obj="hardcoded rule list",
            eid_episodes=("ep-a",),
            src_memories=("core-a",),
        )
        p = Prediction(
            claim="I would expect Rohit to push back on a hardcoded rule-list fix.",
            basis=["prior corrections rejected brittle detectors"],
            confidence=0.5,
            evidence_ids=["ep-a", "core-a", "ep-b"],
            uncertainty="pattern-based expectation, not direct access to his intent.",
            supporting_edges=[edge],
        )
        lines = format_predictions_section([p])
        joined = "\n".join(lines)
        self.assertIn("Predictions:", joined)
        self.assertIn("I would expect Rohit to push back", joined)
        self.assertIn("Confidence:", joined)
        self.assertIn("Basis:", joined)
        self.assertIn("Evidence:", joined)
        self.assertIn("Uncertainty:", joined)
        # Inline supporting graph belief must use the existing format
        # so consumers that grep for "Current graph belief:" still
        # find evidence under derived predictions.
        self.assertIn("Current graph belief:", joined)
        self.assertIn("ep-a", joined)


if __name__ == "__main__":
    unittest.main()
