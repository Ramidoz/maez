# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Cockpit lived-memory endpoint tests (ADR 0019 Phase 7).

The cockpit needs to surface the lived-memory layer without giving
the owner a graph-theory dashboard. The contract is:

    What happened (episode title)
    Why it mattered (summary)
    Still open? (open_loop, if any)
    Evidence (episode ID + source memory IDs)

Plus the relationship view:

    Subject → relation → object, with evidence.

This test file covers the API endpoint that powers the panel:
``GET /api/v1/lived-memory``. The HTML panel itself ships in a
separate commit; locking the JSON contract here means the UI can be
revised independently without breaking consumers.

Tests cover:

- Endpoint exists and returns JSON.
- Empty stores yield empty episodes/edges with sensible counts.
- Populated stores surface episode + edge data with evidence intact.
- Episodes ordered most-recent first.
- Open-loop episodes are flagged so the panel can pin them.
- The endpoint never asserts live state — no 'currently'/'right now'
  in any field it returns.
- Endpoint handles missing SQLite files gracefully (returns empty,
  doesn't 500).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _seed_stores(episode_db, graph_db):
    """Populate fresh SQLite stores for the test_client to read."""
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

    store = EpisodeStore(episode_db)
    graph = RelationshipGraph(graph_db)

    ep_a = store.add(
        title="INFRASTRUCTURE GROUND-TRUTH (correction):",
        summary=(
            "A prior reasoning loop invented a systemd service called "
            "llama-server-vision. None of that exists; vision is retired."
        ),
        participants=["Maez"],
        source_memory_ids=["core-vision-real"],
        source_kind="core_memory",
        emotional_tone="corrective",
        importance=4,
    )
    ep_b = store.add(
        title="Open loop: not finished — soul-write bypass",
        summary=(
            "Owner deferred the dream-state soul-write bypass; we have not finished this work."
        ),
        participants=["Rohit", "Maez"],
        source_memory_ids=["raw-loop-1"],
        source_kind="raw_observation",
        open_loop=("We have not finished the dream-state soul-write bypass."),
    )

    subj = graph.upsert_node(label="Maez", kind="being")
    obj = graph.upsert_node(label="vision narrative", kind="concept")
    graph.add_edge(
        subject_id=subj,
        relation="corrected",
        object_id=obj,
        source_episode_ids=[ep_a],
        source_memory_ids=["core-vision-real"],
        confidence=0.9,
    )
    return ep_a, ep_b


class _ClientFixture(unittest.TestCase):
    """Common setUp/tearDown — patches the web_interface module's
    EpisodeStore / RelationshipGraph paths to per-test temp DBs so
    the test_client doesn't read or write owner's real lived-memory
    files."""

    def setUp(self):
        from skills import web_interface as wi

        self._wi = wi
        self._ep_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._ep_tmp.close()
        self._g_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._g_tmp.close()

        # The endpoint reads paths from module-level constants that
        # the implementation will define. Override them per test.
        self._orig_ep = getattr(wi, "_LIVED_EPISODE_DB_PATH", None)
        self._orig_g = getattr(wi, "_LIVED_GRAPH_DB_PATH", None)
        wi._LIVED_EPISODE_DB_PATH = self._ep_tmp.name
        wi._LIVED_GRAPH_DB_PATH = self._g_tmp.name

        wi.app.config["TESTING"] = True
        self.client = wi.app.test_client()

    def tearDown(self):
        if self._orig_ep is not None:
            self._wi._LIVED_EPISODE_DB_PATH = self._orig_ep
        if self._orig_g is not None:
            self._wi._LIVED_GRAPH_DB_PATH = self._orig_g
        Path(self._ep_tmp.name).unlink(missing_ok=True)
        Path(self._g_tmp.name).unlink(missing_ok=True)


class EndpointExistsAndReturnsJSON(_ClientFixture):
    def test_get_returns_200_and_json(self):
        # Empty stores are still valid — endpoint must not 500.
        resp = self.client.get("/api/v1/lived-memory")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIsInstance(body, dict)
        self.assertIn("episodes", body)
        self.assertIn("edges", body)
        self.assertIn("counts", body)


class EmptyStoresEmptyResponse(_ClientFixture):
    def test_empty_stores_yield_empty_lists(self):
        resp = self.client.get("/api/v1/lived-memory")
        body = resp.get_json()
        self.assertEqual(body["episodes"], [])
        self.assertEqual(body["edges"], [])
        self.assertEqual(body["counts"]["episodes"], 0)
        self.assertEqual(body["counts"]["edges"], 0)


class PopulatedStoresSurfaceData(_ClientFixture):
    def test_episodes_and_edges_returned_with_evidence(self):
        _seed_stores(self._ep_tmp.name, self._g_tmp.name)
        resp = self.client.get("/api/v1/lived-memory")
        body = resp.get_json()

        self.assertEqual(len(body["episodes"]), 2)
        self.assertEqual(len(body["edges"]), 1)
        self.assertEqual(body["counts"]["episodes"], 2)
        self.assertEqual(body["counts"]["edges"], 1)

        # Each episode carries the cockpit contract fields.
        for ep in body["episodes"]:
            for field in (
                "id",
                "title",
                "summary",
                "open_loop",
                "source_memory_ids",
                "source_kind",
                "emotional_tone",
                "importance",
                "status",
            ):
                self.assertIn(field, ep, f"episode missing {field}")
            # Source memory IDs are present and non-empty.
            self.assertTrue(ep["source_memory_ids"])

        # Each edge carries subject/relation/object plus evidence.
        edge = body["edges"][0]
        for field in (
            "id",
            "subject_label",
            "subject_kind",
            "relation",
            "object_label",
            "object_kind",
            "confidence",
            "status",
            "source_episode_ids",
            "source_memory_ids",
        ):
            self.assertIn(field, edge, f"edge missing {field}")
        self.assertEqual(edge["relation"], "corrected")
        self.assertEqual(edge["subject_label"], "Maez")


class EpisodesOrderedMostRecentFirst(_ClientFixture):
    def test_episode_order_descending_by_created_at(self):
        ep_a, ep_b = _seed_stores(self._ep_tmp.name, self._g_tmp.name)
        resp = self.client.get("/api/v1/lived-memory")
        body = resp.get_json()
        # ep_b was added second; should come first in the response.
        self.assertEqual(body["episodes"][0]["id"], ep_b)
        self.assertEqual(body["episodes"][1]["id"], ep_a)


class OpenLoopEpisodesFlagged(_ClientFixture):
    def test_open_loop_appears_as_distinct_field(self):
        _seed_stores(self._ep_tmp.name, self._g_tmp.name)
        resp = self.client.get("/api/v1/lived-memory")
        body = resp.get_json()
        loop_eps = [ep for ep in body["episodes"] if ep["open_loop"]]
        self.assertEqual(len(loop_eps), 1)
        self.assertIn("soul-write bypass", loop_eps[0]["open_loop"])


class NeverAssertsLiveState(_ClientFixture):
    def test_no_field_contains_present_tense_assertions(self):
        _seed_stores(self._ep_tmp.name, self._g_tmp.name)
        resp = self.client.get("/api/v1/lived-memory")
        body = resp.get_json()
        # Walk every string value in the response and check the
        # forbidden words. The endpoint must never wrap stale graph
        # data in language that reads as live state.
        import json as _json

        flat = _json.dumps(body).lower()
        for forbidden in (
            "currently",
            "right now",
            "is happening",
        ):
            self.assertNotIn(
                forbidden,
                flat,
                f"endpoint response contained forbidden {forbidden!r}",
            )


class MissingSqliteFilesHandledGracefully(_ClientFixture):
    """If the owner has not yet run the nightly orchestrator, the
    SQLite files don't exist. The endpoint must return an empty
    payload, not a 500."""

    def test_nonexistent_db_paths_return_200_with_empty(self):
        # Point the module at paths that definitely don't exist.
        self._wi._LIVED_EPISODE_DB_PATH = "/nonexistent/episodes.db"
        self._wi._LIVED_GRAPH_DB_PATH = "/nonexistent/graph.db"
        resp = self.client.get("/api/v1/lived-memory")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["episodes"], [])
        self.assertEqual(body["edges"], [])


if __name__ == "__main__":
    unittest.main()
