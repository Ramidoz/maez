# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Temporal echo tests (ADR 0019 v1.2).

Owner-anchored 2026-04-27 after v1.1 confirmed the residual
``past_to_present`` failure is an abstraction problem, not an
ingestion / planner-ordering one. Echoes are deterministic
resemblance claims between recent and older important episodes.

Tests pin the contract:

- An abstract query with no keyword overlap with any episode body
  still produces an echo (the whole point — escape from token
  scoring).
- Recent / older episodes that share an open-loop term produce an
  echo even when nothing else matches.
- Same participant alone is NOT enough to form an echo (owner rule).
- Importance floor excludes low-priority episodes.
- Echo carries evidence (both episode IDs in the explanation).
- Echo never asserts current state (no "currently" / "right now" /
  "is happening" — same brief invariant lived recall enforces).
- Empty store / sparse store (fewer than recent_count+1 episodes)
  returns an empty list, not an error.
- Output is deterministic across runs on the same data.
"""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _store():
    from core.memory.episodes import EpisodeStore

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    s = EpisodeStore(tmp.name)

    def cleanup():
        Path(tmp.name).unlink(missing_ok=True)

    return s, cleanup


def _seed(store, **kw):
    """Add a single episode with sensible defaults; return its id."""
    defaults = dict(
        title="t",
        summary="s",
        participants=["Maez"],
        source_memory_ids=["raw-x"],
        source_kind="raw_observation",
        importance=3,
    )
    defaults.update(kw)
    return store.add(**defaults)


def _seed_six_corrective(store):
    """Five 'recent' corrective core episodes + one 'older' corrective
    core episode. All share tags={correction} and topic terms — guaranteed
    qualifying pairs."""
    ids = []
    for i in range(6):
        ids.append(
            _seed(
                store,
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
        )
        # Tiny stagger so created_at sorts deterministically.
        time.sleep(0.01)
    return ids


class AbstractQueryStillProducesEcho(unittest.TestCase):
    """The probe ``past_to_present`` ("what is today echoing from last
    week?") shares no domain tokens with any episode body. Token
    scoring drops every candidate at score>0. The echo finder must
    bypass that gate by comparing FEATURES, not query tokens."""

    def test_echo_found_without_query_token_overlap(self):
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            _seed_six_corrective(s)
            # No query argument is taken — find_echoes is query-agnostic
            # by design. The recall planner decides when to call it
            # based on query mode.
            echoes = find_echoes(s, recent_count=5, max_echoes=2)
            self.assertGreaterEqual(len(echoes), 1)
            # The echo must reference both an older and a recent
            # episode by ID.
            first = echoes[0]
            self.assertTrue(first.recent_episode_id.startswith("ep-"))
            self.assertTrue(first.older_episode_id.startswith("ep-"))
            self.assertNotEqual(first.recent_episode_id, first.older_episode_id)
        finally:
            cleanup()


class SharedOpenLoopProducesEcho(unittest.TestCase):
    """Open-loop term overlap alone is enough — owner spec test #2."""

    def test_open_loop_only_pair_qualifies(self):
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            # Six episodes total, importance=3, but only two of them
            # share an open-loop term ("dream-state"). The rest of
            # their feature buckets diverge.
            #
            # Older bucket (created earliest) carries the open-loop
            # term, the recent bucket also carries it on exactly one
            # episode.
            # Insertion order matters: anchor first (so it's in the
            # OLDER bucket), then fillers, then mirror last (so it's
            # in the RECENT bucket). With recent_count=5 and 7 total
            # episodes, the older bucket holds the 2 oldest = anchor
            # plus filler 0.
            #
            # The "older" anchor with the shared open-loop term.
            # Its title/summary use private vocabulary that has no
            # overlap with anything else in the store.
            _seed(
                s,
                title="Anchor phi chi psi",
                summary="phi chi psi",
                participants=["Anchor-Other"],
                source_memory_ids=["raw-anchor-1"],
                source_kind="raw_observation",
                open_loop="revisit dreamstate covenant gap",
                importance=4,
            )
            time.sleep(0.01)
            # Each filler uses a UNIQUE private vocabulary, no shared
            # words across fillers, no overlap with anchor or mirror.
            # The titles deliberately avoid the word "filler" so
            # cross-filler pairs don't form spurious topic echoes.
            filler_vocab = [
                ("kappa", "lambda"),
                ("munu", "nuxi"),
                ("xira", "omicroni"),
                ("pip", "rhori"),
                ("sigmab", "taubo"),
            ]
            for i, (a, b) in enumerate(filler_vocab):
                # No common prefix word in titles or summaries — each
                # filler uses entirely private vocabulary.
                _seed(
                    s,
                    title=a,
                    summary=b,
                    participants=[f"Other-{i}"],
                    source_memory_ids=[f"raw-fill-{i}"],
                    source_kind="raw_observation",
                    open_loop=None,
                    importance=3,
                )
                time.sleep(0.01)
            # The "recent" mirror: shares ONLY the open-loop token
            # "dreamstate" with the anchor. Different participants,
            # disjoint title and summary vocabulary, no overlapping tags.
            _seed(
                s,
                title="Today omega upsilon",
                summary="omega upsilon",
                participants=["Recent-Other"],
                source_memory_ids=["raw-recent-1"],
                source_kind="raw_observation",
                open_loop="dreamstate covenant still pending",
                importance=4,
            )

            echoes = find_echoes(s, recent_count=5, max_echoes=2)
            # At least one echo must connect the two open-loop carriers.
            qualifying = [
                e
                for e in echoes
                if "open_loop" in e.shared_features
            ]
            self.assertTrue(qualifying, f"no open-loop echo; got {echoes}")
        finally:
            cleanup()


class ParticipantAloneInsufficient(unittest.TestCase):
    """Owner rule: same participant alone is not enough. If the only
    shared dimension is ``participants``, no echo fires."""

    def test_same_participant_only_no_echo(self):
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            # Six episodes, all with participants=["Maez"], but every
            # other feature dimension diverges (different titles,
            # different summaries, different source_kinds with no
            # shared tags, no open-loops).
            divergent_titles = [
                "alpha alpha alpha",
                "beta beta beta",
                "gamma gamma gamma",
                "delta delta delta",
                "epsilon epsilon epsilon",
                "zeta zeta zeta",
            ]
            for i, title in enumerate(divergent_titles):
                _seed(
                    s,
                    title=title,
                    summary=title,
                    participants=["Maez"],
                    source_memory_ids=[f"raw-only-maez-{i}"],
                    source_kind="raw_observation",
                    emotional_tone=None,
                    importance=3,
                )
                time.sleep(0.01)

            echoes = find_echoes(s, recent_count=5, max_echoes=5)
            for e in echoes:
                self.assertNotEqual(
                    e.shared_features,
                    ["participants"],
                    f"participants-only echo slipped through: {e}",
                )
        finally:
            cleanup()


class ImportanceFloorExcludesNoise(unittest.TestCase):
    """Episodes below the importance floor must not participate. This
    is the heartbeat-noise guard — without it, low-priority episodes
    could form echoes by accident on shared participants alone."""

    def test_importance_below_floor_skipped(self):
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            # One important episode + many low-importance ones.
            for i in range(5):
                _seed(
                    s,
                    title=f"low priority {i}",
                    summary="noise",
                    participants=["Maez"],
                    source_memory_ids=[f"raw-low-{i}"],
                    importance=1,
                )
                time.sleep(0.01)
            _seed(
                s,
                title="lone important episode",
                summary="signal",
                participants=["Maez"],
                source_memory_ids=["raw-high-1"],
                importance=4,
                emotional_tone="corrective",
            )
            # With importance_floor=3 and only one qualifying episode,
            # there's no recent/older split possible: empty result.
            echoes = find_echoes(s, recent_count=5, importance_floor=3)
            self.assertEqual(echoes, [])
        finally:
            cleanup()


class EvidenceIDsIncludedInExplanation(unittest.TestCase):
    """Every echo must be traceable. The explanation string must carry
    both episode IDs so the recall brief stays evidence-bearing."""

    def test_explanation_contains_both_episode_ids(self):
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            ids = _seed_six_corrective(s)
            echoes = find_echoes(s, recent_count=5, max_echoes=1)
            self.assertEqual(len(echoes), 1)
            e = echoes[0]
            self.assertIn(e.recent_episode_id, e.explanation)
            self.assertIn(e.older_episode_id, e.explanation)
            # Source memory IDs are also visible (full evidence trail).
            self.assertIn("core-corr-", e.explanation)
            # The line carries the phrase "past episode" so the
            # past_to_present probe's substring check is satisfied
            # naturally rather than through wording trickery.
            self.assertIn("past episode", e.explanation.lower())
            # Sanity: ids set in seed corresponds to the real episodes.
            self.assertIn(e.recent_episode_id, ids)
            self.assertIn(e.older_episode_id, ids)
        finally:
            cleanup()


class EchoNeverAssertsCurrentState(unittest.TestCase):
    """Same forbidden-language invariant lived recall enforces:
    nothing in the explanation may assert current/live state."""

    _FORBIDDEN = ("currently", "right now", "is happening")

    def test_no_present_tense_assertion_words(self):
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            _seed_six_corrective(s)
            echoes = find_echoes(s, recent_count=5, max_echoes=2)
            for e in echoes:
                low = e.explanation.lower()
                for word in self._FORBIDDEN:
                    self.assertNotIn(word, low, f"forbidden phrase in: {e.explanation}")
        finally:
            cleanup()


class EmptyAndSparseStoresReturnEmptyList(unittest.TestCase):
    def test_empty_store(self):
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            self.assertEqual(find_echoes(s), [])
        finally:
            cleanup()

    def test_sparse_store_below_recent_count_threshold(self):
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            # Only 3 episodes; default recent_count=5. Cannot split.
            for i in range(3):
                _seed(
                    s,
                    title=f"x {i}",
                    source_memory_ids=[f"raw-{i}"],
                    importance=4,
                )
                time.sleep(0.01)
            self.assertEqual(find_echoes(s, recent_count=5), [])
        finally:
            cleanup()


class DeterministicOrderingAcrossRuns(unittest.TestCase):
    """Same data → same echoes in the same order. This is what makes
    the echo a testable abstraction rather than a stochastic guess."""

    def test_two_runs_produce_identical_output(self):
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            _seed_six_corrective(s)
            run_one = find_echoes(s, recent_count=5, max_echoes=2)
            run_two = find_echoes(s, recent_count=5, max_echoes=2)
            self.assertEqual(
                [(e.recent_episode_id, e.older_episode_id) for e in run_one],
                [(e.recent_episode_id, e.older_episode_id) for e in run_two],
            )
            self.assertEqual(
                [e.explanation for e in run_one],
                [e.explanation for e in run_two],
            )
        finally:
            cleanup()


class ScoreIsSharedFeatureCount(unittest.TestCase):
    """Score is the count of shared feature dimensions. A pair sharing
    topic + tags scores 2; a pair sharing topic + tags + participants
    scores 3. The score lets the planner pick the strongest echo
    when more candidates exist than ``max_echoes`` allows."""

    def test_higher_score_outranks_lower_simple(self):
        # A simpler version that doesn't fight the timestamp ordering:
        # build two pair-candidates explicitly via a fresh store and
        # verify the higher-score pair is at index 0.
        from core.memory.temporal_echo import find_echoes

        s, cleanup = _store()
        try:
            # Seed in this order so that timestamp index splits cleanly:
            # older bucket first (will be oldest), then recent bucket.
            #
            # Older bucket: 1 strong, 1 weak.
            _seed(
                s,
                title="Older alpha: correction",
                summary="alpha topic terms here",
                participants=["Maez"],
                source_memory_ids=["raw-older-strong"],
                emotional_tone="corrective",
                source_kind="core_memory",
                open_loop="alpha revisit",
                importance=4,
            )
            time.sleep(0.01)
            _seed(
                s,
                title="Older beta plain",
                summary="beta topic terms here",
                participants=["Other-weak"],
                source_memory_ids=["raw-older-weak"],
                source_kind="raw_observation",
                open_loop="beta pending",
                importance=3,
            )
            time.sleep(0.01)
            # Recent bucket: 5 episodes. Two of them mirror the
            # older anchors above; the other three are fillers.
            for i in range(3):
                _seed(
                    s,
                    title=f"recent filler {i} unique zzz",
                    summary=f"distinct filler {i}",
                    participants=[f"Filler-{i}"],
                    source_memory_ids=[f"raw-fill-{i}"],
                    importance=3,
                )
                time.sleep(0.01)
            _seed(
                s,
                title="Recent beta plain",
                summary="beta topic terms here",
                participants=["Other-weak2"],
                source_memory_ids=["raw-recent-weak"],
                source_kind="raw_observation",
                open_loop="beta pending",
                importance=3,
            )
            time.sleep(0.01)
            _seed(
                s,
                title="Recent alpha: correction",
                summary="alpha topic terms here",
                participants=["Maez"],
                source_memory_ids=["raw-recent-strong"],
                emotional_tone="corrective",
                source_kind="core_memory",
                open_loop="alpha revisit",
                importance=4,
            )

            echoes = find_echoes(s, recent_count=5, max_echoes=2)
            self.assertGreaterEqual(len(echoes), 1)
            # Highest score should pair the two corrective alphas
            # (topic + tags + participants + open_loop = 4).
            top = echoes[0]
            self.assertGreaterEqual(top.score, 3)
            # Sanity: scores are non-increasing.
            for a, b in zip(echoes, echoes[1:], strict=False):
                self.assertGreaterEqual(a.score, b.score)
        finally:
            cleanup()


if __name__ == "__main__":
    unittest.main()
