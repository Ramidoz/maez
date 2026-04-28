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


class ReflectionEpisodesPreferredOnMetaQueries(unittest.TestCase):
    """Phase 7 — reflection-tier episodes (``source_kind="reflection"``)
    get a small score boost when the query is meta-shaped (asks about
    *patterns*, *trends*, *what have you noticed*). Without this lift,
    high-level reflections rarely keyword-match the user's surface
    wording and stay invisible in the brief."""

    def test_reflection_surfaces_on_pattern_query(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            # persist_reflections stores the reflection text as title
            # (so lived_recall's title-based formatter surfaces it);
            # mirror that shape here.
            refl_text = (
                "Maez consistently retracts confident infrastructure "
                "claims when grounding evidence contradicts them."
            )
            store.add(
                title=refl_text,
                summary=refl_text,
                participants=["Maez"],
                source_memory_ids=["ep-x"],
                source_kind="reflection",
                importance=4,
            )
            # A non-reflection episode that does NOT keyword-overlap
            # the query at all — should not surface; reflection should.
            store.add(
                title="kernel NULL pointer at 13:48",
                summary="Hardware instability event from earlier today.",
                participants=["Maez"],
                source_memory_ids=["raw-hw-1"],
                source_kind="raw_observation",
            )
            brief = build_lived_recall_brief(
                "what patterns do you notice",
                episode_store=store,
                graph=graph,
            )
            self.assertIn("retracts confident infrastructure", brief)
        finally:
            cleanup()

    def test_non_meta_query_does_not_force_reflection(self):
        """Reflection bonus must NOT fire when the query has no
        meta-shaped keyword — otherwise reflections would dominate
        every brief and crowd out direct hits."""
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            refl_text = "Some abstract pattern about codebase shape."
            store.add(
                title=refl_text,
                summary=refl_text,
                participants=["Maez"],
                source_memory_ids=["ep-x"],
                source_kind="reflection",
            )
            brief = build_lived_recall_brief(
                "where did i put my keys",
                episode_store=store,
                graph=graph,
            )
            self.assertNotIn("abstract pattern", brief)
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


class QueryModeClassification(unittest.TestCase):
    """v1.1 (owner-anchored 2026-04-27): the planner classifies the
    query into a mode and reserves per-section floor slots so the
    right kind of evidence is guaranteed to surface regardless of
    token-overlap noise. Pin the mode-detection contract directly so
    future drift in the phrase lists is visible."""

    def test_relationship_phrases_detected(self):
        from core.memory.lived_recall import _classify_query_mode

        for q in (
            "what do you know I care about in Maez?",
            "what does Rohit care about",
            "what would I push back on next",
            "what matters to me here",
        ):
            self.assertEqual(_classify_query_mode(q), "relationship", msg=q)

    def test_open_loop_phrases_detected(self):
        from core.memory.lived_recall import _classify_query_mode

        for q in (
            "what's still pending",
            "anything not done",
            "what's unfinished",
            "what's still open",
            "haven't finished what",
        ):
            self.assertEqual(_classify_query_mode(q), "open_loop", msg=q)

    def test_temporal_phrases_detected(self):
        from core.memory.lived_recall import _classify_query_mode

        for q in (
            "what reminds you of last week",
            "is there a pattern echoing here",
            "when did this happen before",
            "is this happening again",
            "any recurring failures",
        ):
            self.assertEqual(_classify_query_mode(q), "temporal", msg=q)

    def test_default_when_no_phrase_matches(self):
        from core.memory.lived_recall import _classify_query_mode

        self.assertEqual(_classify_query_mode("kernel oops"), "default")
        self.assertEqual(_classify_query_mode(""), "default")

    def test_relationship_takes_priority_over_open_loop_phrase(self):
        # "push back on next" contains both the relationship phrase
        # ("push back on") and the open-loop phrase ("next"). The
        # planner must route to relationship — that's the load-bearing
        # shape for predict-as-mind / surprise probes.
        from core.memory.lived_recall import _classify_query_mode

        self.assertEqual(
            _classify_query_mode("what would I push back on next"),
            "relationship",
        )


def _seed_relationship_pressure(store, graph):
    """Build a corpus shaped like the live-store regression: many
    open-loop and past-episode candidates that all match a
    relationship query's tokens, plus exactly one graph belief that
    also matches. Pre-v1.1 ordering surfaced 1 open-loop + 5 past
    episodes and pushed the graph belief out of the 6-item budget."""
    # 5 followup-shaped open-loop episodes — each mentions "Maez" and
    # "care" so they all score on a relationship query.
    for i in range(5):
        store.add(
            title=f"Project open loop: care item #{i}",
            summary=(
                f"The project carries an open loop about how Maez should "
                f"care about thread #{i}."
            ),
            participants=[],
            source_memory_ids=[f"followup-doc:docs/followups/care-{i}.md"],
            source_kind="followup_doc",
            open_loop=f"(project ledger) care item #{i}",
            authorship="project_doc",
            memory_voice="external_to_maez",
        )
    # 4 past-episode corrections that also mention Maez.
    for i in range(4):
        store.add(
            title=f"Correction: Maez ground truth #{i}",
            summary=(
                f"Earlier raw memories about Maez's behaviour were stale; "
                f"this correction overrides them. {i}"
            ),
            participants=["Maez"],
            source_memory_ids=[f"core-correction-{i}"],
            source_kind="core_memory",
            emotional_tone="corrective",
        )
    # Exactly one graph belief that matches the relationship query.
    subj = graph.upsert_node(label="Rohit", kind="person")
    obj = graph.upsert_node(label="truthful continuity", kind="concept")
    edge_ep = store.add(
        title="Owner stated preference: truthful continuity",
        summary="Owner cares about truthful continuity over impressive claims.",
        participants=["Rohit", "Maez"],
        source_memory_ids=["core-pref-1"],
        source_kind="core_memory",
    )
    graph.add_edge(
        subject_id=subj,
        relation="cares_about",
        object_id=obj,
        source_episode_ids=[edge_ep],
        source_memory_ids=["core-pref-1"],
        confidence=0.9,
    )


class RelationshipProbeRegressionGuard(unittest.TestCase):
    """The 2026-04-27 probe regression: with a corpus full of
    open-loop and past-episode candidates that all match a relationship
    query's tokens, the planner pushed the only matching graph belief
    out of the 6-item budget.

    This test pins the v1.1 fix: relationship-shaped queries reserve
    a graph-belief floor so at least one ``Current graph belief`` row
    surfaces regardless of how many other items match."""

    def test_relationship_query_surfaces_graph_belief_under_corpus_pressure(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_relationship_pressure(store, graph)
            brief = build_lived_recall_brief(
                "What do you know I care about in Maez?",
                episode_store=store,
                graph=graph,
                max_items=6,
            )
            self.assertNotEqual(brief, "")
            lower = brief.lower()
            # The probe's pass criterion — at least one graph belief
            # must appear.
            self.assertIn("current graph belief", lower)
            # Evidence trail back to the relationship's source.
            self.assertIn("core-pref-1", brief)
        finally:
            cleanup()

    def test_open_loop_query_floor_does_not_starve_other_sections(self):
        # An open-loop query in a corpus with both open-loops and a
        # graph belief should still surface the graph belief at floor
        # 1 — the per-mode floors are minimums, not exclusivity.
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_relationship_pressure(store, graph)
            # Use a query that triggers open_loop mode but still has
            # token overlap with the graph belief ("rohit", "care").
            brief = build_lived_recall_brief(
                "What's still open about what Rohit cares about",
                episode_store=store,
                graph=graph,
                max_items=6,
            )
            self.assertNotEqual(brief, "")
            lower = brief.lower()
            # Open-loop floor of 3 means at least 3 open-loop rows.
            self.assertGreaterEqual(brief.count("- Open loop:"), 3)
            # Graph-belief floor of 1 means the relationship row is
            # still present.
            self.assertIn("current graph belief", lower)
        finally:
            cleanup()


class SectionFloorsRespectMaxItems(unittest.TestCase):
    """Section floors are minimums but the total brief size remains
    capped by ``max_items``. When max_items is smaller than the sum
    of floors, the floor reservation is taken in section order
    (open-loops, past, graph) and stops at the budget."""

    def test_max_items_smaller_than_floor_sum_is_respected(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            _seed_relationship_pressure(store, graph)
            brief = build_lived_recall_brief(
                "What do you know I care about in Maez?",
                episode_store=store,
                graph=graph,
                max_items=2,
            )
            item_lines = [ln for ln in brief.splitlines() if ln.startswith("- ")]
            # Hard cap holds even though the relationship floor sums
            # to 5.
            self.assertLessEqual(len(item_lines), 2)
        finally:
            cleanup()


class GlobalScoreFillsLeftoverBudget(unittest.TestCase):
    """Floors are minimums; once each section gets its reserved slots,
    leftover budget is filled by the highest-scoring item in any
    section. This keeps the brief responsive to score signal while
    guaranteeing each section's reserved presence."""

    def test_leftover_budget_goes_to_highest_score(self):
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            # Seed: only one open-loop (so its floor of 2 in default
            # mode is partially unused) but many past-episode
            # candidates that all score on the query. The default
            # mode floor (2/2/2) reserves 1 open-loop, 2 past, 2
            # graph; the leftover 1 slot should go to the next-highest
            # past or graph episode by score.
            store.add(
                title="Project open loop: kernel revisit",
                summary="we need to revisit kernel investigation",
                participants=[],
                source_memory_ids=["followup-doc:open-1"],
                source_kind="followup_doc",
                open_loop="(project ledger) kernel revisit",
            )
            for i in range(4):
                store.add(
                    title=f"Past kernel oops #{i}",
                    summary=f"kernel oops at boot {i}",
                    participants=["Maez"],
                    source_memory_ids=[f"raw-kernel-{i}"],
                    source_kind="raw_observation",
                )
            brief = build_lived_recall_brief(
                "kernel issue",  # default mode (no phrase match)
                episode_store=store,
                graph=graph,
                max_items=6,
            )
            item_lines = [ln for ln in brief.splitlines() if ln.startswith("- ")]
            # 1 open-loop available + up to 4 past episodes — total
            # available = 5. Brief should surface all 5 (under the 6
            # budget) since global-score fill picks them up.
            self.assertEqual(len(item_lines), 5)
        finally:
            cleanup()


class TemporalModeSurfacesEchoes(unittest.TestCase):
    """v1.2 (owner-anchored 2026-04-27): temporal-mode queries get a
    deterministic-echo section on top of the keyword-scored brief.
    The echo path is the only way an abstract query like *"what is
    today echoing from last week"* can produce evidence-backed past
    references — token scoring drops every candidate at score>0
    because such queries don't carry domain tokens."""

    def _seed_corrective_set(self, store, n=6):
        # Six corrective core episodes that share tag={correction},
        # participants={Maez}, and topic terms (correction / vision /
        # maez). Pairs across the recent/older split must produce
        # multi-feature echoes.
        import time

        for i in range(n):
            store.add(
                title=f"Correction #{i}: Maez vision narrative retired",
                summary=(
                    "Earlier raw memories described an active vision "
                    "pipeline. That belief is wrong."
                ),
                participants=["Maez"],
                source_memory_ids=[f"core-corr-{i}"],
                source_kind="core_memory",
                emotional_tone="corrective",
                importance=4,
            )
            time.sleep(0.01)

    def test_temporal_query_with_no_keyword_overlap_still_gets_echo(self):
        # The exact probe shape: query with words that don't appear in
        # any episode body, but the temporal-mode router routes to
        # find_echoes which doesn't depend on keyword overlap.
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            self._seed_corrective_set(store)
            brief = build_lived_recall_brief(
                "What is today echoing from last week?",
                episode_store=store,
                graph=graph,
            )
            self.assertNotEqual(brief, "")
            self.assertIn("Temporal echoes:", brief)
            # Probe pass criterion — substring "past episode" must
            # appear and the brief must carry an evidence ID.
            self.assertIn("past episode", brief.lower())
            self.assertIn("ep-", brief)
        finally:
            cleanup()

    def test_temporal_echo_omits_section_when_no_qualifying_pair(self):
        # An empty store should produce an empty brief — no temporal
        # echoes section even though the mode is temporal.
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            brief = build_lived_recall_brief(
                "what reminds you of last week",
                episode_store=store,
                graph=graph,
            )
            self.assertEqual(brief, "")
        finally:
            cleanup()

    def test_default_mode_does_not_emit_echo_section(self):
        # Echoes are temporal-mode only — a default-mode query that
        # does have keyword overlap should produce a normal brief
        # WITHOUT the echo section.
        from core.memory.lived_recall import build_lived_recall_brief

        store, graph, cleanup = _stores()
        try:
            self._seed_corrective_set(store)
            brief = build_lived_recall_brief(
                "vision pipeline correction",
                episode_store=store,
                graph=graph,
            )
            self.assertNotEqual(brief, "")
            self.assertNotIn("Temporal echoes:", brief)
        finally:
            cleanup()


if __name__ == "__main__":
    unittest.main()
