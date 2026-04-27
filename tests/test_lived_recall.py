# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Lived recall planner tests (ADR 0019 Phase 5).

The planner takes a query and the episode + graph stores and produces
a compact, evidence-backed brief. Four section labels distinguish
*past episode*, *current graph belief*, *open loop*, and *live state
unavailable* — the brief never asserts current system state on graph
evidence alone.

Tests cover:

- Empty stores produce empty brief.
- Query unrelated to any stored data produces empty brief.
- Query about a hardware fault returns a past-episode-framed item,
  with no 'currently' assertion.
- Query about owner preference returns an evidence-backed edge.
- Every emitted item carries an evidence marker (episode ID +
  source memory IDs).
- The brief never contains 'currently' / 'right now' / 'is happening'.
- max_items caps the number of brief items.
- Brief starts with the LIVED RECALL header when non-empty.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _stores():
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

    ep_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    ep_tmp.close()
    g_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    g_tmp.close()
    store = EpisodeStore(ep_tmp.name)
    graph = RelationshipGraph(g_tmp.name)

    def cleanup():
        Path(ep_tmp.name).unlink(missing_ok=True)
        Path(g_tmp.name).unlink(missing_ok=True)

    return store, graph, cleanup


def _seed_hardware_instability(store, graph):
    ep_id = store.add(
        title="Hardware instability: kernel NULL pointer at 13:48",
        summary=(
            "Kernel NULL pointer dereference at 13:48; system rebooted. "
            "NVIDIA driver 570.211.01 implicated."
        ),
        participants=["Maez"],
        source_memory_ids=["raw-hw-1"],
        source_kind="raw_observation",
        emotional_tone="alarming",
        importance=4,
    )
    subj = graph.upsert_node(label="Hardware instability", kind="category")
    obj = graph.upsert_node(label="Track A continuity", kind="concept")
    graph.add_edge(
        subject_id=subj,
        relation="threatens",
        object_id=obj,
        source_episode_ids=[ep_id],
        source_memory_ids=["raw-hw-1"],
        confidence=0.7,
    )
    return ep_id


def _seed_owner_preference(store, graph):
    ep_id = store.add(
        title="Owner stated preference: truthful continuity > impressive claims",
        summary=(
            "Owner expressed in 2026-04-26 conversation that truthful "
            "continuity matters more to them than impressive but possibly "
            "fabricated claims. Anchor for future fabrication-prevention "
            "design."
        ),
        participants=["Rohit", "Maez"],
        source_memory_ids=["core-pref-1"],
        source_kind="core_memory",
    )
    subj = graph.upsert_node(label="Rohit", kind="person")
    obj = graph.upsert_node(label="truthful continuity", kind="concept")
    graph.add_edge(
        subject_id=subj,
        relation="cares_about",
        object_id=obj,
        source_episode_ids=[ep_id],
        source_memory_ids=["core-pref-1"],
        confidence=0.9,
    )
    return ep_id


class EmptyStoresEmptyBrief(unittest.TestCase):
    def test_empty_returns_empty_string(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            brief = build_lived_recall_brief(
                "anything",
                episode_store=store,
                graph=graph,
            )
            self.assertEqual(brief, "")
        finally:
            cleanup()


class NoRelevantMatchesEmptyBrief(unittest.TestCase):
    def test_unrelated_query_returns_empty(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_hardware_instability(store, graph)
            brief = build_lived_recall_brief(
                "what did i eat for breakfast",
                episode_store=store,
                graph=graph,
            )
            self.assertEqual(brief, "")
        finally:
            cleanup()


class QueryAboutHardwareReturnsPastEpisode(unittest.TestCase):
    def test_brief_uses_past_tense_framing_and_evidence(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_hardware_instability(store, graph)
            brief = build_lived_recall_brief(
                "Have we had any kernel reboots?",
                episode_store=store,
                graph=graph,
            )
            self.assertNotEqual(brief, "")
            lower = brief.lower()
            # Must reference the past via the section label.
            self.assertIn("past episode", lower)
            # Must NOT assert that the kernel is currently broken.
            self.assertNotIn("currently", lower)
            self.assertNotIn("right now", lower)
            self.assertNotIn("is happening", lower)
            # Evidence trail must be visible.
            self.assertIn("raw-hw-1", brief)
        finally:
            cleanup()


class QueryAboutOwnerPreferenceReturnsEdge(unittest.TestCase):
    def test_relationship_edge_surfaces_with_evidence(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_owner_preference(store, graph)
            brief = build_lived_recall_brief(
                "what does Rohit care about",
                episode_store=store,
                graph=graph,
            )
            self.assertNotEqual(brief, "")
            self.assertIn("Rohit", brief)
            self.assertIn("truthful continuity", brief)
            # Evidence ID appears.
            self.assertIn("core-pref-1", brief)
        finally:
            cleanup()


class EveryItemCarriesEvidence(unittest.TestCase):
    def test_every_item_line_has_an_evidence_marker(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_hardware_instability(store, graph)
            _seed_owner_preference(store, graph)
            brief = build_lived_recall_brief(
                "Rohit kernel continuity",
                episode_store=store,
                graph=graph,
            )
            self.assertNotEqual(brief, "")
            # Item lines start with "- "; each must reference an
            # episode (ep-...) or a source memory (raw-... / core-...).
            item_lines = [ln for ln in brief.splitlines() if ln.startswith("- ")]
            self.assertGreater(len(item_lines), 0)
            for ln in item_lines:
                has_evidence = "ep-" in ln or "raw-" in ln or "core-" in ln
                self.assertTrue(
                    has_evidence,
                    f"item without evidence marker: {ln!r}",
                )
        finally:
            cleanup()


class BriefNeverSaysCurrently(unittest.TestCase):
    """The graph must never claim live state. Even when the seeded
    edges describe ongoing relationships ('cares_about'), the brief
    must not say *'currently'*, *'right now'*, *'is happening'* —
    those words are reserved for live perception, which the planner
    does not have."""

    def test_no_present_tense_assertion_words(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_hardware_instability(store, graph)
            _seed_owner_preference(store, graph)
            brief = build_lived_recall_brief(
                "Rohit kernel",
                episode_store=store,
                graph=graph,
            )
            for forbidden in (
                "currently",
                "right now",
                "is happening",
                "happening now",
            ):
                self.assertNotIn(
                    forbidden,
                    brief.lower(),
                    f"brief must not contain {forbidden!r}",
                )
        finally:
            cleanup()


class MaxItemsRespected(unittest.TestCase):
    def test_max_items_caps_brief(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            # Seed both fixtures so there are multiple candidates.
            _seed_hardware_instability(store, graph)
            _seed_owner_preference(store, graph)
            brief = build_lived_recall_brief(
                "Rohit kernel continuity",
                episode_store=store,
                graph=graph,
                max_items=1,
            )
            item_lines = [ln for ln in brief.splitlines() if ln.startswith("- ")]
            self.assertLessEqual(len(item_lines), 1)
        finally:
            cleanup()


class BriefHasHeader(unittest.TestCase):
    def test_non_empty_brief_starts_with_header(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_hardware_instability(store, graph)
            brief = build_lived_recall_brief(
                "kernel",
                episode_store=store,
                graph=graph,
            )
            self.assertTrue(brief.startswith("=== LIVED RECALL"))
        finally:
            cleanup()


class LiveStateQueryGetsUnavailableNote(unittest.TestCase):
    """When the query is about *current* system state (CPU / GPU /
    RAM / 'what's running now'), the brief must include an explicit
    *live state unavailable* note rather than answering from graph
    inference."""

    def test_query_with_now_word_notes_live_state_unavailable(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_hardware_instability(store, graph)
            brief = build_lived_recall_brief(
                "is the kernel ok right now?",
                episode_store=store,
                graph=graph,
            )
            # Brief should still be non-empty (matches kernel),
            # AND should include the live-state-unavailable label.
            self.assertNotEqual(brief, "")
            self.assertIn("live state", brief.lower())
            self.assertIn("unavailable", brief.lower())
        finally:
            cleanup()


if __name__ == "__main__":
    unittest.main()
