# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""End-to-end synthetic proof of the entity-expansion pipeline (Step 5k).

The Step-5j A/B against real lived-memory showed alias seeding +
backfill + expansion adding little new evidence. Two possible reads:
the architecture is sound and current data is sparse, OR the
architecture itself can't surface what keyword recall misses. This
test settles it with a controlled fixture:

  Setup:
    • Maya Ananthan canonical, aliases ["Maya", "Mimi"]
    • Episodes that mention Maya by short-form ("Maya seemed
      nervous") but never by the nickname "Mimi"
    • Query: "how is Mimi doing?"

  Then:
    • Baseline keyword recall MISSES — query has no token overlap
      with the episode text (the nickname Mimi never appears in
      any episode). This is the exact case that exposes whether
      the substrate adds value.
    • Expanded recall, with the same data, MUST surface the
      episodes via the alias resolution Mimi → Maya Ananthan →
      mentions.

If this test passes but the real corpus A/B adds little, the
bottleneck is data/extraction/alias coverage, not architecture.
That's the load-bearing diagnostic the harness is designed to
provide.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


_FLAG = "MAEZ_ENTITY_EXPANSION"


# ── fixture ────────────────────────────────────────────────────────


def _build_synthetic_world(td: Path) -> dict:
    """Construct the controlled scenario: 5 episodes, one curated
    entity with two aliases (one of which — the nickname — is the
    only way the query reaches the data). Returns handles plus
    the seeded episode ids so tests can assert on them."""
    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

    ep_store = EpisodeStore(str(td / "lived_episodes.db"))
    graph = RelationshipGraph(str(td / "lived_graph.db"))
    ix = EntityIndex(td / "entity_index.db")

    # Seed Maya Ananthan with two aliases — "Maya" (short form
    # appearing in episode text) and "Mimi" (nickname appearing
    # only in queries; the load-bearing case).
    maya_id = ix.upsert_entity(
        "Maya Ananthan", kind="person", aliases=["Maya", "Mimi"],
    )

    # Sample School is a second seeded entity to demonstrate the
    # backfill works for multi-token canonical names that the
    # extractor catches naturally (no alias dependency).
    school_id = ix.upsert_entity(
        "Sample School", kind="organization",
    )

    eids: dict[str, str] = {}
    eids["maya_first_day"] = ep_store.add(
        title="Maya started school today",
        summary="big day; she seemed excited and a little anxious",
        participants=["rohit"],
        source_memory_ids=["mem-1"],
        source_kind="conversation",
        occurred_at="2026-04-12T09:00:00+00:00",
    )
    eids["maya_classroom"] = ep_store.add(
        title="classroom dynamics",
        summary="Maya seemed nervous about the new classroom",
        participants=["rohit"],
        source_memory_ids=["mem-2"],
        source_kind="conversation",
        occurred_at="2026-04-15T09:00:00+00:00",
    )
    eids["sample_school_meeting"] = ep_store.add(
        title="Sample School meeting went well",
        summary="met the principal; positive vibes",
        participants=["rohit"],
        source_memory_ids=["mem-3"],
        source_kind="conversation",
        occurred_at="2026-04-18T09:00:00+00:00",
    )
    eids["dinner"] = ep_store.add(
        title="quiet dinner",
        summary="we cooked together and watched a movie",
        participants=["rohit"],
        source_memory_ids=["mem-4"],
        source_kind="conversation",
        occurred_at="2026-04-20T09:00:00+00:00",
    )
    eids["unrelated"] = ep_store.add(
        title="garage cleanup",
        summary="finally finished sorting the boxes",
        participants=["rohit"],
        source_memory_ids=["mem-5"],
        source_kind="conversation",
        occurred_at="2026-04-22T09:00:00+00:00",
    )
    return {
        "ep_store": ep_store,
        "graph": graph,
        "ix": ix,
        "maya_id": maya_id,
        "school_id": school_id,
        "eids": eids,
    }


# ── stage 1: backfill creates mentions ────────────────────────────


class TestBackfillCreatesAliasAndCanonicalMentions(unittest.TestCase):
    def test_alias_maya_creates_mentions_canonical_school_too(self):
        from core.memory.entity_backfill import backfill

        with tempfile.TemporaryDirectory() as td:
            world = _build_synthetic_world(Path(td))
            ix = world["ix"]
            ep = world["ep_store"]
            maya_id = world["maya_id"]
            school_id = world["school_id"]

            backfill(episodes=ep, ix=ix, write=True)

            # Maya Ananthan should have mentions from BOTH episodes
            # that reference "Maya" (short form alias).
            maya_mentions = ix.list_mentions(maya_id)
            maya_session_ids = {m["session_id"] for m in maya_mentions}
            self.assertIn(world["eids"]["maya_first_day"], maya_session_ids)
            self.assertIn(world["eids"]["maya_classroom"], maya_session_ids)

            # Sample School should have a mention from the
            # extractor catching "Sample School" canonical name.
            school_mentions = ix.list_mentions(school_id)
            self.assertGreaterEqual(len(school_mentions), 1)
            school_sids = {m["session_id"] for m in school_mentions}
            self.assertIn(
                world["eids"]["sample_school_meeting"], school_sids,
            )


# ── stage 2: expand_query resolves nickname → entity → sessions ──


class TestExpandQueryResolvesNicknameToSessions(unittest.TestCase):
    def test_mimi_query_returns_maya_sessions(self):
        from core.memory.entity_backfill import backfill
        from core.memory.entity_index import expand_query

        with tempfile.TemporaryDirectory() as td:
            world = _build_synthetic_world(Path(td))
            ix = world["ix"]
            ep = world["ep_store"]
            backfill(episodes=ep, ix=ix, write=True)

            out = expand_query("how is Mimi doing?", ix=ix)
            self.assertGreaterEqual(len(out.matched_entities), 1)
            ids = {m.entity_id for m in out.matched_entities}
            self.assertIn(world["maya_id"], ids)
            self.assertIn(
                world["eids"]["maya_first_day"], out.session_ids,
            )
            self.assertIn(
                world["eids"]["maya_classroom"], out.session_ids,
            )


# ── stage 3: brief — flag off MISSES, flag on RECOVERS ───────────


class TestBriefBaselineMissesAndExpandedRecovers(unittest.TestCase):
    """The load-bearing assertion: with the controlled fixture, the
    baseline keyword pass cannot find episodes that don't share a
    token with the query 'Mimi doing'. Expansion must surface them
    via the alias index. If THIS fails, the architecture has a
    real bug; if it passes but real-data A/B doesn't, the corpus
    is the bottleneck."""

    def test_baseline_misses_then_expanded_recovers(self):
        from core.memory.entity_backfill import backfill
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            world = _build_synthetic_world(Path(td))
            ix = world["ix"]
            ep = world["ep_store"]
            graph = world["graph"]
            backfill(episodes=ep, ix=ix, write=True)

            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            query = "how is Mimi doing?"

            # Flag off — explicitly clear so caller env can't
            # contaminate.
            env = dict(os.environ)
            env.pop(_FLAG, None)
            with mock.patch.dict(os.environ, env, clear=True):
                baseline = build_lived_recall_brief(
                    query, episode_store=ep, graph=graph,
                    reference_time=ref, ix=ix,
                )
            # Baseline must NOT contain the Maya episodes — query
            # has no token overlap with them. (And no ENTITY
            # EXPANSION header, of course.)
            self.assertNotIn("ENTITY EXPANSION", baseline)
            self.assertNotIn(
                world["eids"]["maya_first_day"], baseline,
            )
            self.assertNotIn(
                world["eids"]["maya_classroom"], baseline,
            )

            # Flag on.
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                expanded = build_lived_recall_brief(
                    query, episode_store=ep, graph=graph,
                    reference_time=ref, ix=ix,
                )
            self.assertIn("=== ENTITY EXPANSION ===", expanded)
            self.assertIn("Maya Ananthan", expanded)
            self.assertIn(world["eids"]["maya_first_day"], expanded)
            self.assertIn(world["eids"]["maya_classroom"], expanded)


# ── stage 4: measurement script reports the recovery ─────────────


class TestMeasurementScriptReportsRecovery(unittest.TestCase):
    def test_new_session_ids_positive_on_synthetic_fixture(self):
        from core.memory.entity_backfill import backfill
        from scripts.measure_entity_expansion import measure

        with tempfile.TemporaryDirectory() as td:
            world = _build_synthetic_world(Path(td))
            ix = world["ix"]
            ep = world["ep_store"]
            graph = world["graph"]
            backfill(episodes=ep, ix=ix, write=True)

            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            m = measure(
                "how is Mimi doing?",
                ix=ix, episode_store=ep, graph=graph,
                reference_time=ref,
            )
            self.assertTrue(m["entity_section_present"])
            self.assertGreaterEqual(len(m["new_session_ids"]), 2)
            self.assertIn("Maya Ananthan", m["entities_surfaced"])


# ── safety ───────────────────────────────────────────────────────


class TestNoSubprocessOrNetwork(unittest.TestCase):
    def test_no_subprocess_or_socket_during_full_pipeline(self):
        from core.memory.entity_backfill import backfill
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 socket, "socket",
                 side_effect=AssertionError("no socket"),
             ):
            world = _build_synthetic_world(Path(td))
            backfill(episodes=world["ep_store"], ix=world["ix"], write=True)
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                build_lived_recall_brief(
                    "how is Mimi doing?",
                    episode_store=world["ep_store"],
                    graph=world["graph"],
                    ix=world["ix"],
                    reference_time=datetime(
                        2026, 4, 30, 12, 0, tzinfo=timezone.utc,
                    ),
                )


if __name__ == "__main__":
    unittest.main()
