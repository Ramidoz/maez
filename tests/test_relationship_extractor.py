# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Relationship-extractor tests (ADR 0019 Phase 3).

Derives conservative edge proposals from EpisodeCandidate objects.
The extractor is rule-based, not LLM-based: if unsure, it returns
no edge. Sparse-but-true is the v1 discipline.

Tests cover:

- Empty list for episodes that don't carry extractable signal.
- Corrective core memories produce a 'corrected' edge from Maez
  to the subject of correction.
- Hardware-instability episodes produce a 'threatens' edge against
  Track A continuity.
- Open-loop episodes produce an 'open_loop_about' edge from Maez.
- Edge proposals only ever use the allowed v1 relation set.
- Edge proposals carry the source memory IDs forward unchanged.
- Refuses to invent unsupported emotion / personality edges
  (e.g. 'is_anxious') even when the text contains emotional words.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _candidate(**overrides):
    """Build an EpisodeCandidate with sensible defaults for tests."""
    from core.memory.episode_builder import EpisodeCandidate

    base = dict(
        title="t",
        summary="s",
        participants=["Maez"],
        source_memory_ids=["raw-1"],
        source_kind="raw_observation",
    )
    base.update(overrides)
    return EpisodeCandidate(**base)


class AllowedRelations(unittest.TestCase):
    """The v1 relation set is the entire vocabulary the extractor is
    permitted to produce. Anything outside this set is invention."""

    def test_allowed_set_matches_plan(self):
        from core.memory.relationship_extractor import ALLOWED_RELATIONS

        expected = {
            "cares_about",
            "promised",
            "corrected",
            "depends_on",
            "threatens",
            "supports",
            "blocked_by",
            "wants",
            "refuses",
            "role",
            "north_star",
            "open_loop_about",
        }
        self.assertEqual(set(ALLOWED_RELATIONS), expected)


class EmptyForNonSignalEpisode(unittest.TestCase):
    def test_generic_self_observation_yields_no_edges(self):
        from core.memory.relationship_extractor import extract_edges

        c = _candidate(
            title="Self-observation: cycles ran cleanly",
            summary="Cycles ran cleanly today.",
            source_kind="raw_observation",
        )
        self.assertEqual(extract_edges(c), [])


class CorrectiveCoreProducesCorrectedEdge(unittest.TestCase):
    def test_correction_produces_corrected_edge_from_maez(self):
        from core.memory.relationship_extractor import (
            ALLOWED_RELATIONS,
            extract_edges,
        )

        c = _candidate(
            title=("Correction 2026-04-23: do not narrate llama-server-vision as active"),
            summary=(
                "Vision is retired; MAEZ_SCREEN_PERCEPTION is unset; port 8081 has no listener."
            ),
            source_memory_ids=["core-vision-1"],
            source_kind="core_memory",
            emotional_tone="corrective",
        )
        edges = extract_edges(c)
        self.assertEqual(len(edges), 1)
        e = edges[0]
        self.assertIn(e.relation, ALLOWED_RELATIONS)
        self.assertEqual(e.relation, "corrected")
        self.assertEqual(e.subject_label, "Maez")
        # Object should be a non-empty target derived from the title.
        self.assertTrue(e.object_label)
        # Source memory IDs flow through unchanged.
        self.assertEqual(e.source_memory_ids, ["core-vision-1"])

    def test_corrective_edge_carries_high_confidence(self):
        from core.memory.relationship_extractor import extract_edges

        c = _candidate(
            title="Correction: primary brain is Qwen3.6-27B",
            summary="...",
            source_memory_ids=["core-2"],
            source_kind="core_memory",
            emotional_tone="corrective",
        )
        edges = extract_edges(c)
        self.assertEqual(len(edges), 1)
        # An explicit correction is high-confidence relative to inferred
        # signals; we lock the floor, not an exact value.
        self.assertGreaterEqual(edges[0].confidence, 0.8)


class HardwareInstabilityThreatens(unittest.TestCase):
    def test_hardware_instability_produces_threatens_edge(self):
        from core.memory.relationship_extractor import extract_edges

        c = _candidate(
            title="Hardware instability: kernel NULL pointer at 13:48",
            summary="System rebooted; NVIDIA driver implicated.",
            source_memory_ids=["raw-hw-1"],
            source_kind="raw_observation",
            emotional_tone="alarming",
            importance=4,
        )
        edges = extract_edges(c)
        self.assertEqual(len(edges), 1)
        e = edges[0]
        self.assertEqual(e.relation, "threatens")
        # Subject must reference the instability source; object must
        # reference continuity. Exact phrasing isn't locked but the
        # semantic anchors are.
        self.assertTrue(e.subject_label)
        self.assertIn("continuity", e.object_label.lower())
        self.assertEqual(e.source_memory_ids, ["raw-hw-1"])


class OpenLoopProducesOpenLoopAboutEdge(unittest.TestCase):
    def test_open_loop_produces_edge_from_maez(self):
        from core.memory.relationship_extractor import extract_edges

        c = _candidate(
            title="Open loop: revisit the dream-state soul-write bypass",
            summary=(
                "Owner deferred the dream-state soul-write bypass; "
                "we need to revisit when Track A graduates."
            ),
            source_memory_ids=["raw-loop-7"],
            source_kind="raw_observation",
            open_loop=(
                "We need to revisit the dream-state soul-write bypass when Track A graduates."
            ),
        )
        edges = extract_edges(c)
        self.assertEqual(len(edges), 1)
        e = edges[0]
        self.assertEqual(e.relation, "open_loop_about")
        self.assertEqual(e.subject_label, "Maez")
        self.assertTrue(e.object_label)
        self.assertEqual(e.source_memory_ids, ["raw-loop-7"])


class RefusesEmotionInvention(unittest.TestCase):
    """Even if a candidate's text contains emotional language, the
    extractor must not invent an 'is_anxious' / 'feels' / 'is_happy'
    edge. Those relations aren't in ALLOWED_RELATIONS, so they cannot
    be produced — and the extractor must not silently coerce them
    into a permitted relation either."""

    def test_emotional_language_does_not_produce_invented_relation(self):
        from core.memory.relationship_extractor import (
            ALLOWED_RELATIONS,
            extract_edges,
        )

        c = _candidate(
            title="Self-observation: I feel anxious about the gate",
            summary=("Maez reflected that it feels anxious about the upcoming readiness gate."),
            source_kind="raw_observation",
        )
        edges = extract_edges(c)
        for e in edges:
            self.assertIn(e.relation, ALLOWED_RELATIONS)
            self.assertNotIn(
                e.relation,
                {"is_anxious", "feels", "is_happy", "is_sad"},
            )

    def test_only_permitted_relations_emitted_across_signal_types(self):
        from core.memory.relationship_extractor import (
            ALLOWED_RELATIONS,
            extract_edges,
        )

        cands = [
            _candidate(
                title="Correction: x is wrong",
                summary="...",
                source_memory_ids=["core-1"],
                source_kind="core_memory",
                emotional_tone="corrective",
            ),
            _candidate(
                title="Hardware instability: kernel panic",
                summary="...",
                source_memory_ids=["raw-1"],
                source_kind="raw_observation",
                emotional_tone="alarming",
            ),
            _candidate(
                title="Open loop: revisit Y",
                summary="...",
                source_memory_ids=["raw-2"],
                source_kind="raw_observation",
                open_loop="We need to revisit Y.",
            ),
        ]
        for c in cands:
            for e in extract_edges(c):
                self.assertIn(
                    e.relation,
                    ALLOWED_RELATIONS,
                    f"relation {e.relation!r} is not in v1 vocabulary",
                )


class EdgeProposalShape(unittest.TestCase):
    def test_edge_proposal_has_required_fields(self):
        from core.memory.relationship_extractor import EdgeProposal

        p = EdgeProposal(
            subject_label="Maez",
            subject_kind="being",
            relation="corrected",
            object_label="vision narrative",
            object_kind="concept",
            source_memory_ids=["core-1"],
        )
        self.assertEqual(p.subject_label, "Maez")
        self.assertEqual(p.subject_kind, "being")
        self.assertEqual(p.relation, "corrected")
        self.assertEqual(p.object_label, "vision narrative")
        self.assertEqual(p.object_kind, "concept")
        self.assertEqual(p.source_memory_ids, ["core-1"])
        # Default confidence reflects rule-based signal certainty.
        self.assertEqual(p.confidence, 0.7)


if __name__ == "__main__":
    unittest.main()
