# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Working-self goal-driven retrieval tests.

Covers ``core/memory/working_self.py`` — the Conway 2000 + Park 2023
goal-modulated retrieval module. Tests are split into three groups:

1. Dataclass behaviour (``Goal``, ``GoalHierarchy``, ``ScoreWeights``)
2. Per-source goal extraction (cares_about edges, wants log, owner
   messages, open loops, reflections), each via real stores or
   minimal stubs
3. Scoring math — the Park three-term formula extended with Conway's
   goal-alignment fourth term

Stores (``EpisodeStore``, ``RelationshipGraph``) are real SQLite
fixtures matching ``test_lived_recall.py``'s pattern. ``wants`` is
stubbed because its concrete shape is just ``recent(limit) -> list``.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.memory.working_self import (
    GOAL_SOURCE_CARES_ABOUT,
    GOAL_SOURCE_OPEN_LOOP,
    GOAL_SOURCE_OWNER_MSG,
    GOAL_SOURCE_REFLECTION,
    GOAL_SOURCE_WANTS,
    Goal,
    GoalHierarchy,
    ScoreWeights,
    assemble_goals,
    goal_relevance,
    recency_score,
    relevance_score,
    score_memory,
    tier_score,
)


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


class _StubWants:
    """Minimal stand-in for ``core.evolution.wants.Wants`` — exposes
    only ``recent(limit)``, which is the public surface
    ``_goals_from_wants`` uses."""

    def __init__(self, entries: list[dict]):
        self._entries = entries

    def recent(self, limit: int = 20) -> list[dict]:
        return list(self._entries)[:limit]


# ── dataclass behaviour ────────────────────────────────────────────────


class TestGoal(unittest.TestCase):
    def test_goal_is_frozen(self):
        g = Goal(text="x", source=GOAL_SOURCE_WANTS, weight=0.5)
        with self.assertRaises(Exception):
            g.text = "y"  # type: ignore[misc]

    def test_evidence_ids_coerced_to_tuple(self):
        g = Goal(text="x", source=GOAL_SOURCE_WANTS, weight=0.5,
                 evidence_ids=["a", "b"])  # type: ignore[arg-type]
        self.assertIsInstance(g.evidence_ids, tuple)
        self.assertEqual(g.evidence_ids, ("a", "b"))

    def test_evidence_ids_default_empty_tuple(self):
        g = Goal(text="x", source=GOAL_SOURCE_WANTS, weight=0.5)
        self.assertEqual(g.evidence_ids, ())


class TestGoalHierarchy(unittest.TestCase):
    def test_empty_hierarchy(self):
        h = GoalHierarchy()
        self.assertTrue(h.is_empty)
        self.assertEqual(h.goals, ())
        self.assertEqual(h.text_corpus(), "")

    def test_by_source_filters(self):
        a = Goal(text="alpha", source=GOAL_SOURCE_WANTS, weight=0.5)
        b = Goal(text="beta", source=GOAL_SOURCE_OWNER_MSG, weight=0.7)
        c = Goal(text="gamma", source=GOAL_SOURCE_WANTS, weight=0.4)
        h = GoalHierarchy(goals=(a, b, c))
        wants = h.by_source(GOAL_SOURCE_WANTS)
        self.assertEqual(len(wants), 2)
        self.assertEqual({g.text for g in wants}, {"alpha", "gamma"})

    def test_text_corpus_concatenates(self):
        a = Goal(text="alpha", source=GOAL_SOURCE_WANTS, weight=0.5)
        b = Goal(text="beta", source=GOAL_SOURCE_OWNER_MSG, weight=0.7)
        h = GoalHierarchy(goals=(a, b))
        self.assertEqual(h.text_corpus(), "alpha | beta")

    def test_goals_coerced_to_tuple(self):
        a = Goal(text="alpha", source=GOAL_SOURCE_WANTS, weight=0.5)
        h = GoalHierarchy(goals=[a])  # type: ignore[arg-type]
        self.assertIsInstance(h.goals, tuple)


class TestScoreWeightsDefaults(unittest.TestCase):
    def test_all_ones_baseline(self):
        w = ScoreWeights()
        self.assertEqual((w.recency, w.tier, w.relevance, w.goal),
                         (1.0, 1.0, 1.0, 1.0))


# ── per-source goal extraction ─────────────────────────────────────────


class TestAssembleGoalsEmpty(unittest.TestCase):
    def test_no_sources_returns_empty(self):
        h = assemble_goals()
        self.assertTrue(h.is_empty)


class TestGoalsFromCaresAbout(unittest.TestCase):
    def test_cares_about_edge_becomes_goal(self):
        store, graph, cleanup = _stores()
        try:
            ep_id = store.add(
                title="Stated preference",
                summary="Rohit said: I value truthful continuity.",
                participants=["Rohit"],
                source_memory_ids=["raw-1"],
                source_kind="raw_observation",
                importance=4,
            )
            subj = graph.upsert_node(label="Rohit", kind="person")
            obj = graph.upsert_node(label="truthful continuity", kind="value")
            graph.add_edge(
                subject_id=subj,
                relation="cares_about",
                object_id=obj,
                source_episode_ids=[ep_id],
                source_memory_ids=["raw-1"],
                confidence=0.9,
            )
            h = assemble_goals(graph=graph)
            self.assertFalse(h.is_empty)
            cares = h.by_source(GOAL_SOURCE_CARES_ABOUT)
            self.assertEqual(len(cares), 1)
            self.assertEqual(cares[0].text, "Rohit cares about truthful continuity")
            self.assertEqual(cares[0].evidence_ids, (ep_id, "raw-1"))
        finally:
            cleanup()

    def test_non_cares_about_edges_ignored(self):
        store, graph, cleanup = _stores()
        try:
            ep_id = store.add(
                title="Hardware",
                summary="GPU instability.",
                participants=["Maez"],
                source_memory_ids=["raw-2"],
                source_kind="raw_observation",
                importance=3,
            )
            subj = graph.upsert_node(label="GPU", kind="hardware")
            obj = graph.upsert_node(label="reliability", kind="concept")
            graph.add_edge(
                subject_id=subj,
                relation="threatens",
                object_id=obj,
                source_episode_ids=[ep_id],
                source_memory_ids=["raw-2"],
            )
            h = assemble_goals(graph=graph)
            self.assertEqual(h.by_source(GOAL_SOURCE_CARES_ABOUT), ())
        finally:
            cleanup()

    def test_max_per_source_caps_cares_about(self):
        store, graph, cleanup = _stores()
        try:
            ep_id = store.add(
                title="Multi-pref",
                summary="Multiple preferences expressed.",
                participants=["Rohit"],
                source_memory_ids=["raw-3"],
                source_kind="raw_observation",
            )
            subj = graph.upsert_node(label="Rohit", kind="person")
            for label in [f"value-{i}" for i in range(8)]:
                obj = graph.upsert_node(label=label, kind="value")
                graph.add_edge(
                    subject_id=subj,
                    relation="cares_about",
                    object_id=obj,
                    source_episode_ids=[ep_id],
                    source_memory_ids=["raw-3"],
                )
            h = assemble_goals(graph=graph, max_per_source=3)
            self.assertEqual(len(h.by_source(GOAL_SOURCE_CARES_ABOUT)), 3)
        finally:
            cleanup()


class TestGoalsFromWants(unittest.TestCase):
    def test_wants_entries_become_goals(self):
        wants = _StubWants([
            {"want_id": "w-1", "text": "deepen trace coverage", "created_at": "2026-04-28T12:00:00+00:00"},
            {"want_id": "w-2", "text": "fix telegram link previews", "created_at": "2026-04-27T12:00:00+00:00"},
        ])
        h = assemble_goals(wants=wants)
        wants_goals = h.by_source(GOAL_SOURCE_WANTS)
        self.assertEqual(len(wants_goals), 2)
        texts = {g.text for g in wants_goals}
        self.assertIn("deepen trace coverage", texts)
        self.assertIn("fix telegram link previews", texts)

    def test_wants_falls_back_to_description_field(self):
        wants = _StubWants([{"id": "w-3", "description": "ship working_self slice"}])
        h = assemble_goals(wants=wants)
        wants_goals = h.by_source(GOAL_SOURCE_WANTS)
        self.assertEqual(len(wants_goals), 1)
        self.assertEqual(wants_goals[0].text, "ship working_self slice")

    def test_wants_skips_blank_entries(self):
        wants = _StubWants([{"want_id": "w-blank", "text": "   "}])
        h = assemble_goals(wants=wants)
        self.assertEqual(h.by_source(GOAL_SOURCE_WANTS), ())

    def test_wants_failure_falls_through(self):
        class BadWants:
            def recent(self, limit=20):
                raise RuntimeError("db down")
        h = assemble_goals(wants=BadWants())
        self.assertEqual(h.by_source(GOAL_SOURCE_WANTS), ())


class TestGoalsFromOwnerMsg(unittest.TestCase):
    def test_single_string_message(self):
        h = assemble_goals(recent_owner_text="Let us do it now")
        msgs = h.by_source(GOAL_SOURCE_OWNER_MSG)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].text, "Let us do it now")

    def test_sequence_of_messages_decays(self):
        h = assemble_goals(recent_owner_text=["latest", "older", "oldest"])
        msgs = h.by_source(GOAL_SOURCE_OWNER_MSG)
        self.assertEqual(len(msgs), 3)
        # weights strictly decreasing — most recent first
        self.assertGreater(msgs[0].weight, msgs[1].weight)
        self.assertGreater(msgs[1].weight, msgs[2].weight)

    def test_empty_string_skipped(self):
        h = assemble_goals(recent_owner_text="   ")
        self.assertEqual(h.by_source(GOAL_SOURCE_OWNER_MSG), ())

    def test_none_passthrough(self):
        h = assemble_goals(recent_owner_text=None)
        self.assertEqual(h.by_source(GOAL_SOURCE_OWNER_MSG), ())


class TestGoalsFromOpenLoops(unittest.TestCase):
    def test_only_open_loop_episodes_become_goals(self):
        store, _, cleanup = _stores()
        try:
            store.add(
                title="closed thread",
                summary="resolved",
                participants=["Maez"],
                source_memory_ids=["raw-x"],
                source_kind="raw_observation",
            )
            store.add(
                title="open thread",
                summary="needs follow-up",
                participants=["Maez"],
                source_memory_ids=["raw-y"],
                source_kind="raw_observation",
                open_loop="confirm GPU temp regression resolved",
            )
            h = assemble_goals(episode_store=store)
            loops = h.by_source(GOAL_SOURCE_OPEN_LOOP)
            self.assertEqual(len(loops), 1)
            self.assertEqual(loops[0].text, "confirm GPU temp regression resolved")
        finally:
            cleanup()

    def test_max_per_source_caps_open_loops(self):
        store, _, cleanup = _stores()
        try:
            for i in range(8):
                store.add(
                    title=f"loop-{i}",
                    summary="x",
                    participants=["Maez"],
                    source_memory_ids=[f"raw-{i}"],
                    source_kind="raw_observation",
                    open_loop=f"loop-text-{i}",
                )
            h = assemble_goals(episode_store=store, max_per_source=3)
            self.assertEqual(len(h.by_source(GOAL_SOURCE_OPEN_LOOP)), 3)
        finally:
            cleanup()


class TestGoalsFromReflections(unittest.TestCase):
    def test_only_reflection_episodes_become_goals(self):
        store, _, cleanup = _stores()
        try:
            store.add(
                title="raw obs",
                summary="A raw observation, not a reflection.",
                participants=["Maez"],
                source_memory_ids=["raw-1"],
                source_kind="raw_observation",
            )
            store.add(
                title="reflection on truth-bias",
                summary="Maez has noticed it consistently prioritises truth over speed.",
                participants=["Maez"],
                source_memory_ids=["raw-2"],
                source_kind="reflection",
            )
            h = assemble_goals(episode_store=store)
            refls = h.by_source(GOAL_SOURCE_REFLECTION)
            self.assertEqual(len(refls), 1)
            self.assertIn("truth over speed", refls[0].text)
        finally:
            cleanup()


class TestAssembleGoalsCaps(unittest.TestCase):
    def test_max_goals_truncates_overall(self):
        wants = _StubWants([{"want_id": f"w-{i}", "text": f"want-{i}"} for i in range(10)])
        h = assemble_goals(
            wants=wants,
            recent_owner_text=[f"msg-{i}" for i in range(10)],
            max_goals=4,
            max_per_source=10,
        )
        self.assertEqual(len(h.goals), 4)

    def test_sorted_by_weight_descending(self):
        # owner_msg default weight (0.85) outranks wants default (0.65),
        # so all owner_msg goals should appear before any wants goals.
        wants = _StubWants([{"want_id": "w-1", "text": "low-weight goal"}])
        h = assemble_goals(
            wants=wants,
            recent_owner_text="high-weight goal",
            max_goals=5,
            max_per_source=5,
        )
        self.assertGreaterEqual(len(h.goals), 2)
        self.assertEqual(h.goals[0].source, GOAL_SOURCE_OWNER_MSG)


# ── scoring math ───────────────────────────────────────────────────────


class TestRecencyScore(unittest.TestCase):
    def test_now_returns_one(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        score = recency_score(now.isoformat(), now=now)
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_one_half_life_returns_half(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        ts = (now - timedelta(hours=24)).isoformat()
        score = recency_score(ts, now=now, half_life_hours=24.0)
        self.assertAlmostEqual(score, 0.5, places=3)

    def test_two_half_lives_returns_quarter(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        ts = (now - timedelta(hours=48)).isoformat()
        score = recency_score(ts, now=now, half_life_hours=24.0)
        self.assertAlmostEqual(score, 0.25, places=3)

    def test_invalid_timestamp_fails_open(self):
        score = recency_score("not-a-timestamp")
        self.assertEqual(score, 1.0)

    def test_empty_string_fails_open(self):
        score = recency_score("")
        self.assertEqual(score, 1.0)

    def test_naive_iso_is_treated_as_utc(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        # naive timestamp same instant — should give ~1.0 not blow up
        naive = "2026-04-28T12:00:00"
        score = recency_score(naive, now=now)
        self.assertAlmostEqual(score, 1.0, places=4)


class TestTierScore(unittest.TestCase):
    def test_known_tiers_in_descending_order(self):
        self.assertGreater(tier_score("core"), tier_score("reflection"))
        self.assertGreater(tier_score("reflection"), tier_score("open_loop"))
        self.assertGreater(tier_score("open_loop"), tier_score("daily"))
        self.assertGreater(tier_score("daily"), tier_score("raw"))

    def test_core_is_one(self):
        self.assertEqual(tier_score("core"), 1.0)

    def test_unknown_tier_falls_back(self):
        self.assertEqual(tier_score("nonsense"), tier_score("raw"))

    def test_empty_tier_falls_back(self):
        self.assertEqual(tier_score(""), tier_score("raw"))

    def test_case_insensitive(self):
        self.assertEqual(tier_score("CORE"), tier_score("core"))


class TestRelevanceScore(unittest.TestCase):
    def test_full_overlap(self):
        score = relevance_score("the alpha beta gamma", "alpha beta gamma")
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_partial_overlap(self):
        score = relevance_score("alpha gamma", "alpha beta gamma delta")
        self.assertAlmostEqual(score, 0.5, places=4)  # 2 of 4 query toks

    def test_no_overlap(self):
        score = relevance_score("alpha beta", "gamma delta")
        self.assertEqual(score, 0.0)

    def test_empty_inputs(self):
        self.assertEqual(relevance_score("", "anything"), 0.0)
        self.assertEqual(relevance_score("anything", ""), 0.0)

    def test_stopwords_filtered(self):
        # only stopwords on either side → 0
        self.assertEqual(relevance_score("the and or", "the and or"), 0.0)

    def test_embedder_used_when_provided(self):
        calls = []

        def fake_embedder(a: str, b: str) -> float:
            calls.append((a, b))
            return 0.42

        score = relevance_score("alpha", "beta", embedder=fake_embedder)
        self.assertEqual(len(calls), 1)
        self.assertAlmostEqual(score, 0.42, places=4)

    def test_embedder_failure_falls_back(self):
        def boom(a: str, b: str) -> float:
            raise RuntimeError("nope")

        score = relevance_score("alpha beta", "alpha", embedder=boom)
        self.assertAlmostEqual(score, 1.0, places=4)


class TestGoalRelevance(unittest.TestCase):
    def test_empty_hierarchy_is_zero(self):
        score = goal_relevance("alpha beta", GoalHierarchy())
        self.assertEqual(score, 0.0)

    def test_aligned_memory_is_high(self):
        goals = GoalHierarchy(goals=(
            Goal(text="continuity of memory", source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        aligned = goal_relevance("continuity of memory matters", goals)
        unaligned = goal_relevance("kitchen sink plumbing", goals)
        self.assertGreater(aligned, unaligned)
        self.assertGreater(aligned, 0.5)
        self.assertEqual(unaligned, 0.0)

    def test_empty_memory_text_is_zero(self):
        goals = GoalHierarchy(goals=(
            Goal(text="continuity", source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        self.assertEqual(goal_relevance("", goals), 0.0)


class TestScoreMemory(unittest.TestCase):
    def test_alpha_goal_zero_reduces_to_park(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        memory = {
            "text": "alpha beta",
            "tier": "core",
            "created_at": now.isoformat(),
        }
        goals = GoalHierarchy(goals=(
            Goal(text="completely unrelated topic", source=GOAL_SOURCE_WANTS, weight=0.5),
        ))
        weights_with = ScoreWeights(recency=1.0, tier=1.0, relevance=1.0, goal=0.0)
        weights_without_goal_term = ScoreWeights(recency=1.0, tier=1.0, relevance=1.0)
        s_zero = score_memory(memory, query_text="alpha", goals=goals, weights=weights_with, now=now)
        # With α_goal=1 and irrelevant goals, the goal term drags score down.
        s_full = score_memory(memory, query_text="alpha", goals=goals, weights=weights_without_goal_term, now=now)
        self.assertGreater(s_zero, s_full)

    def test_aligned_goal_increases_score(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        memory = {
            "text": "continuity is important",
            "tier": "core",
            "created_at": now.isoformat(),
        }
        empty_goals = GoalHierarchy()
        aligned_goals = GoalHierarchy(goals=(
            Goal(text="continuity matters", source=GOAL_SOURCE_CARES_ABOUT, weight=0.95),
        ))
        weights = ScoreWeights()
        s_no_goals = score_memory(memory, query_text="", goals=empty_goals, weights=weights, now=now)
        s_aligned = score_memory(memory, query_text="", goals=aligned_goals, weights=weights, now=now)
        self.assertGreater(s_aligned, s_no_goals)

    def test_score_is_bounded_zero_to_one(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        memory = {
            "text": "alpha beta",
            "tier": "core",
            "created_at": now.isoformat(),
        }
        goals = GoalHierarchy(goals=(
            Goal(text="alpha beta", source=GOAL_SOURCE_CARES_ABOUT, weight=1.0),
        ))
        weights = ScoreWeights()
        score = score_memory(memory, query_text="alpha beta", goals=goals,
                             weights=weights, now=now)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_zero_weights_returns_zero(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        memory = {"text": "x", "tier": "core", "created_at": now.isoformat()}
        weights = ScoreWeights(recency=0.0, tier=0.0, relevance=0.0, goal=0.0)
        score = score_memory(memory, query_text="x", goals=GoalHierarchy(),
                             weights=weights, now=now)
        self.assertEqual(score, 0.0)

    def test_tier_falls_back_to_source_kind(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        # No "tier" key but source_kind=core — tier_score should still pick up
        memory_a = {"text": "x", "source_kind": "core", "created_at": now.isoformat()}
        memory_b = {"text": "x", "tier": "core", "created_at": now.isoformat()}
        s_a = score_memory(memory_a, query_text="x", weights=ScoreWeights(recency=0, relevance=0, goal=0), now=now)
        s_b = score_memory(memory_b, query_text="x", weights=ScoreWeights(recency=0, relevance=0, goal=0), now=now)
        self.assertEqual(s_a, s_b)

    def test_text_falls_back_through_aliases(self):
        now = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
        memory_text = {"text": "alpha", "tier": "raw", "created_at": now.isoformat()}
        memory_summary = {"summary": "alpha", "tier": "raw", "created_at": now.isoformat()}
        memory_title = {"title": "alpha", "tier": "raw", "created_at": now.isoformat()}
        weights = ScoreWeights(recency=0.0, tier=0.0, relevance=1.0, goal=0.0)
        self.assertEqual(
            score_memory(memory_text, query_text="alpha", weights=weights, now=now),
            score_memory(memory_summary, query_text="alpha", weights=weights, now=now),
        )
        self.assertEqual(
            score_memory(memory_text, query_text="alpha", weights=weights, now=now),
            score_memory(memory_title, query_text="alpha", weights=weights, now=now),
        )


class TestGoalRelevanceExcludesEvidence(unittest.TestCase):
    """Gap 2 fix: ``goal_relevance`` accepts ``exclude_evidence_ids``;
    goals whose evidence_ids overlap are filtered out before scoring.
    Prevents the self-referential bonus where an open_loop episode's
    own goal-text inflates its score against itself."""

    def test_exclude_drops_matching_goals(self):
        goals = GoalHierarchy(goals=(
            Goal(
                text="recovery jarvis cards orphan",
                source=GOAL_SOURCE_OPEN_LOOP,
                weight=0.75,
                evidence_ids=("ep-aaa",),
            ),
        ))
        # Without exclusion: full overlap → 1.0
        self.assertGreater(
            goal_relevance("recovery jarvis cards orphan", goals),
            0.5,
        )
        # With exclusion of ep-aaa: only goal is filtered out → 0.0
        self.assertEqual(
            goal_relevance(
                "recovery jarvis cards orphan",
                goals,
                exclude_evidence_ids=("ep-aaa",),
            ),
            0.0,
        )

    def test_exclude_preserves_non_matching_goals(self):
        goals = GoalHierarchy(goals=(
            Goal(text="alpha goal text", source=GOAL_SOURCE_OPEN_LOOP,
                 weight=0.75, evidence_ids=("ep-aaa",)),
            Goal(text="alpha goal text", source=GOAL_SOURCE_CARES_ABOUT,
                 weight=0.95, evidence_ids=("ep-bbb",)),
        ))
        # Excluding ep-aaa drops the open_loop goal but the
        # cares_about goal (ep-bbb) still contributes.
        score = goal_relevance(
            "alpha goal text",
            goals,
            exclude_evidence_ids=("ep-aaa",),
        )
        self.assertGreater(score, 0.5)

    def test_exclude_default_empty_preserves_old_behavior(self):
        # Regression: omitting the param must equal passing ().
        goals = GoalHierarchy(goals=(
            Goal(text="alpha", source=GOAL_SOURCE_WANTS, weight=0.5,
                 evidence_ids=("ep-x",)),
        ))
        a = goal_relevance("alpha", goals)
        b = goal_relevance("alpha", goals, exclude_evidence_ids=())
        self.assertEqual(a, b)


class TestScoreMemoryExcludesEvidence(unittest.TestCase):
    """``score_memory`` plumbs ``exclude_evidence_ids`` through to
    ``goal_relevance``. Same shape as the unit tests above but at
    the composite-score layer."""

    def test_self_referential_goal_does_not_inflate(self):
        from datetime import datetime as _dt, timezone as _tz
        from core.memory.working_self import score_memory, ScoreWeights

        now = _dt(2026, 4, 28, 12, 0, 0, tzinfo=_tz.utc)
        memory = {
            "id": "ep-self",
            "text": "recovery jarvis cards orphan",
            "tier": "raw",
            "created_at": now.isoformat(),
        }
        goals = GoalHierarchy(goals=(
            Goal(text="recovery jarvis cards orphan",
                 source=GOAL_SOURCE_OPEN_LOOP, weight=0.75,
                 evidence_ids=("ep-self",)),
        ))
        weights = ScoreWeights(recency=0.0, tier=0.0, relevance=0.0, goal=1.0)
        # Without exclusion: high goal contribution
        s_with_bonus = score_memory(memory, query_text="", goals=goals,
                                    weights=weights, now=now)
        s_excluded = score_memory(memory, query_text="", goals=goals,
                                  weights=weights, now=now,
                                  exclude_evidence_ids=("ep-self",))
        self.assertGreater(s_with_bonus, 0.5)
        self.assertEqual(s_excluded, 0.0)


class TestGoalRelevanceNoiseTokenFilter(unittest.TestCase):
    """Universal anchor tokens (the owner's name, "maez") appear in
    every memory and every working-self goal-text, so they carry no
    alignment signal — they're noise. Filtering them via the
    ``noise_tokens`` parameter prevents the goal-only path from
    being dominated by name-coincidence (the 2026-04-29 live-spin
    diagnosis explaining why every reflective query surfaced the
    same 5 OWNER PREFERENCE items)."""

    def test_noise_tokens_filtered_from_both_sides(self):
        # Goal text contains noise tokens + one signal token.
        # Memory text contains ONLY the noise tokens.
        # Without filter: would partially overlap (false positive).
        # With filter: noise stripped → no real overlap → 0.
        goals = GoalHierarchy(goals=(
            Goal(
                text="rohit cares maez continuity",
                source=GOAL_SOURCE_CARES_ABOUT,
                weight=0.95,
            ),
        ))
        memory_only_names = "rohit and maez talked together"
        unfiltered = goal_relevance(memory_only_names, goals)
        filtered = goal_relevance(
            memory_only_names,
            goals,
            noise_tokens=("rohit", "maez"),
        )
        self.assertGreater(unfiltered, 0.0,
                           "without filter, names create false alignment")
        self.assertEqual(filtered, 0.0,
                         "with filter, name-only memory has no alignment")

    def test_noise_filter_preserves_real_alignment(self):
        # Memory has both names AND a content token that matches a
        # signal-bearing goal token. After filtering, real alignment
        # via the signal token still scores.
        goals = GoalHierarchy(goals=(
            Goal(
                text="rohit cares maez continuity",
                source=GOAL_SOURCE_CARES_ABOUT,
                weight=0.95,
            ),
        ))
        memory = "the project's continuity must be preserved"
        filtered = goal_relevance(
            memory,
            goals,
            noise_tokens=("rohit", "maez"),
        )
        # With "rohit" and "maez" filtered, goal tokens reduce to
        # {cares, continuity}. Memory has "continuity". Overlap = 1
        # of 2 → ratio 0.5. Single-goal weighted-mean → 0.5.
        self.assertAlmostEqual(filtered, 0.5, places=2)

    def test_noise_filter_default_empty_preserves_old_behavior(self):
        goals = GoalHierarchy(goals=(
            Goal(text="alpha beta", source=GOAL_SOURCE_WANTS, weight=0.5),
        ))
        a = goal_relevance("alpha beta", goals)
        b = goal_relevance("alpha beta", goals, noise_tokens=())
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
