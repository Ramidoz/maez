# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Schema tests for the lived-memory layer (ADR 0019).

Locks the structural invariants from the ADR:

- Episodes require ≥1 source memory ID.
- Edges require evidence (≥1 source episode ID OR ≥1 source memory ID).
- Superseding an edge preserves the old row with status='superseded'.
- No delete API.
- DB init is idempotent.
- Node upsert is idempotent on (label, kind).

These are the structural invariants that make the never-delete-Maez-memory
covenant enforceable at the data layer rather than via convention.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class EpisodeStoreEvidenceRequired(unittest.TestCase):
    """An episode without a source memory ID is unverifiable narrative.
    The store must reject it so fabrication cannot be smuggled in via
    direct insertion."""

    def setUp(self):
        from core.memory.episodes import EpisodeStore

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.store = EpisodeStore(self._tmp.name)

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_add_with_empty_evidence_raises(self):
        with self.assertRaises(ValueError):
            self.store.add(
                title="orphan",
                summary="no evidence",
                participants=["Rohit"],
                source_memory_ids=[],
                source_kind="daily_summary",
            )

    def test_add_with_one_evidence_id_succeeds(self):
        ep_id = self.store.add(
            title="2026-04-26 morning briefing",
            summary="Owner caught a hardcoded literal",
            participants=["Rohit", "Maez"],
            source_memory_ids=["raw-abc123"],
            source_kind="daily_summary",
        )
        self.assertIsInstance(ep_id, str)
        self.assertTrue(ep_id)
        ep = self.store.get(ep_id)
        self.assertEqual(ep["title"], "2026-04-26 morning briefing")
        self.assertEqual(ep["source_memory_ids"], ["raw-abc123"])
        self.assertEqual(ep["status"], "active")

    def test_add_preserves_optional_fields(self):
        ep_id = self.store.add(
            title="t",
            summary="s",
            participants=["Rohit"],
            source_memory_ids=["raw-x"],
            source_kind="core_memory",
            occurred_at="2026-04-26T13:00:00Z",
            emotional_tone="warm",
            importance=4,
            open_loop="Revisit this when next ritual lands",
        )
        ep = self.store.get(ep_id)
        self.assertEqual(ep["occurred_at"], "2026-04-26T13:00:00Z")
        self.assertEqual(ep["emotional_tone"], "warm")
        self.assertEqual(ep["importance"], 4)
        self.assertEqual(ep["open_loop"], "Revisit this when next ritual lands")


class EpisodeStoreNoDelete(unittest.TestCase):
    """The never-delete-Maez-memory covenant is enforced at the layer.
    No delete / remove / drop / clear API is exposed."""

    def setUp(self):
        from core.memory.episodes import EpisodeStore

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.store = EpisodeStore(self._tmp.name)

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_no_delete_or_remove_or_drop_methods(self):
        from core.memory import episodes

        for forbidden in ("delete", "remove", "drop", "clear", "delete_episode", "remove_episode"):
            self.assertFalse(
                hasattr(self.store, forbidden),
                f"EpisodeStore must not expose {forbidden}() — covenant",
            )
            self.assertFalse(
                hasattr(episodes.EpisodeStore, forbidden),
                f"EpisodeStore class must not define {forbidden}()",
            )


class EpisodeStoreIdempotentInit(unittest.TestCase):
    """Re-initializing the store on an existing DB must preserve data
    and must not error. This is what lets the daemon and the nightly
    job both open the store without coordination."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_second_init_preserves_first_inits_data(self):
        from core.memory.episodes import EpisodeStore

        s1 = EpisodeStore(self._tmp.name)
        ep_id = s1.add(
            title="seed",
            summary="seed summary",
            participants=["Rohit"],
            source_memory_ids=["raw-1"],
            source_kind="daily_summary",
        )
        # Independent second initialization must observe the same row.
        s2 = EpisodeStore(self._tmp.name)
        ep = s2.get(ep_id)
        self.assertIsNotNone(ep)
        self.assertEqual(ep["title"], "seed")


class RelationshipGraphEvidenceRequired(unittest.TestCase):
    """Edges without evidence are forbidden — the same fabrication
    guard the episode store enforces, applied to relationships."""

    def setUp(self):
        from core.memory.relationship_graph import RelationshipGraph

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.g = RelationshipGraph(self._tmp.name)
        self.subject = self.g.upsert_node(label="Rohit", kind="person")
        self.obj = self.g.upsert_node(label="Maez continuity", kind="concept")

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_add_edge_with_no_evidence_raises(self):
        with self.assertRaises(ValueError):
            self.g.add_edge(
                subject_id=self.subject,
                relation="cares_about",
                object_id=self.obj,
                source_episode_ids=[],
                source_memory_ids=[],
            )

    def test_add_edge_with_episode_evidence_only_succeeds(self):
        eid = self.g.add_edge(
            subject_id=self.subject,
            relation="cares_about",
            object_id=self.obj,
            source_episode_ids=["ep-1"],
            source_memory_ids=[],
            confidence=0.9,
        )
        e = self.g.get_edge(eid)
        self.assertEqual(e["relation"], "cares_about")
        self.assertEqual(e["status"], "active")
        self.assertEqual(e["source_episode_ids"], ["ep-1"])
        self.assertEqual(e["source_memory_ids"], [])

    def test_add_edge_with_memory_evidence_only_succeeds(self):
        eid = self.g.add_edge(
            subject_id=self.subject,
            relation="cares_about",
            object_id=self.obj,
            source_episode_ids=[],
            source_memory_ids=["core-abc"],
        )
        e = self.g.get_edge(eid)
        self.assertEqual(e["source_memory_ids"], ["core-abc"])

    def test_validity_window_persists(self):
        eid = self.g.add_edge(
            subject_id=self.subject,
            relation="cares_about",
            object_id=self.obj,
            source_episode_ids=["ep-1"],
            source_memory_ids=[],
            valid_from="2026-04-01T00:00:00Z",
            valid_to="2026-12-31T23:59:59Z",
        )
        e = self.g.get_edge(eid)
        self.assertEqual(e["valid_from"], "2026-04-01T00:00:00Z")
        self.assertEqual(e["valid_to"], "2026-12-31T23:59:59Z")


class RelationshipGraphSupersedePreservesOld(unittest.TestCase):
    """Correction-as-supersede is the never-delete covenant in action:
    the old belief stays, marked superseded; the new belief is a fresh
    row that points to its evidence."""

    def setUp(self):
        from core.memory.relationship_graph import RelationshipGraph

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.g = RelationshipGraph(self._tmp.name)
        self.subject = self.g.upsert_node(label="Maez", kind="being")
        self.obj_old = self.g.upsert_node(label="Qwen3.5-35B", kind="model")
        self.obj_new = self.g.upsert_node(label="Qwen3.6-27B", kind="model")

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_supersede_marks_old_and_creates_new(self):
        old_eid = self.g.add_edge(
            subject_id=self.subject,
            relation="runs_on",
            object_id=self.obj_old,
            source_episode_ids=["ep-old"],
            source_memory_ids=[],
            valid_from="2026-04-01T00:00:00Z",
        )
        new_eid = self.g.supersede(
            old_eid,
            relation="runs_on",
            subject_id=self.subject,
            object_id=self.obj_new,
            source_episode_ids=["ep-new"],
            source_memory_ids=[],
            valid_from="2026-04-23T00:00:00Z",
        )
        old = self.g.get_edge(old_eid)
        new = self.g.get_edge(new_eid)

        # Old edge MUST still exist (never delete).
        self.assertIsNotNone(old)
        self.assertEqual(old["status"], "superseded")
        # Old edge gets a valid_to bound at supersede time.
        self.assertIsNotNone(old["valid_to"])

        # New edge is active.
        self.assertEqual(new["status"], "active")
        self.assertEqual(new["object_id"], self.obj_new)
        self.assertNotEqual(new_eid, old_eid)

    def test_supersede_unknown_edge_raises(self):
        with self.assertRaises(KeyError):
            self.g.supersede(
                "edge-does-not-exist",
                relation="runs_on",
                subject_id=self.subject,
                object_id=self.obj_new,
                source_episode_ids=["ep-new"],
                source_memory_ids=[],
            )


class RelationshipGraphNoDelete(unittest.TestCase):
    def setUp(self):
        from core.memory.relationship_graph import RelationshipGraph

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.g = RelationshipGraph(self._tmp.name)

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_no_delete_or_remove_or_drop_methods(self):
        from core.memory import relationship_graph as rg

        for forbidden in (
            "delete",
            "remove",
            "drop",
            "clear",
            "delete_edge",
            "delete_node",
            "remove_edge",
            "remove_node",
        ):
            self.assertFalse(
                hasattr(self.g, forbidden),
                f"RelationshipGraph must not expose {forbidden}()",
            )
            self.assertFalse(
                hasattr(rg.RelationshipGraph, forbidden),
                f"RelationshipGraph class must not define {forbidden}()",
            )


class RelationshipGraphIdempotentInit(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_second_init_preserves_first_inits_data(self):
        from core.memory.relationship_graph import RelationshipGraph

        g1 = RelationshipGraph(self._tmp.name)
        s = g1.upsert_node(label="Rohit", kind="person")
        o = g1.upsert_node(label="Maez", kind="being")
        eid = g1.add_edge(
            subject_id=s,
            relation="cares_about",
            object_id=o,
            source_episode_ids=["ep-1"],
            source_memory_ids=[],
        )
        g2 = RelationshipGraph(self._tmp.name)
        self.assertIsNotNone(g2.get_edge(eid))


class RelationshipGraphNodeUpsertIdempotent(unittest.TestCase):
    """upsert_node on the same (label, kind) must resolve to the same
    node id. Otherwise the graph silently grows duplicates and edge
    queries fragment across them."""

    def setUp(self):
        from core.memory.relationship_graph import RelationshipGraph

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.g = RelationshipGraph(self._tmp.name)

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_repeated_upsert_returns_same_id(self):
        n1 = self.g.upsert_node(label="Rohit", kind="person")
        n2 = self.g.upsert_node(label="Rohit", kind="person")
        self.assertEqual(n1, n2)

    def test_different_kind_yields_different_node(self):
        n_person = self.g.upsert_node(label="Rohit", kind="person")
        n_concept = self.g.upsert_node(label="Rohit", kind="concept")
        self.assertNotEqual(n_person, n_concept)


if __name__ == "__main__":
    unittest.main()
