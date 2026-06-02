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


class EpisodeStoreProvenanceColumns(unittest.TestCase):
    """The 2026-04-27 followup-doc ingest landed two provenance columns
    (``authorship`` / ``memory_voice``). Defaults must be NULL so
    pre-existing rows keep their meaning ("Maez-authored, first-person"
    — the only mode that existed before). Explicit values must round-
    trip through ``add`` → ``get``."""

    def setUp(self):
        from core.memory.episodes import EpisodeStore

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.store = EpisodeStore(self._tmp.name)

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_default_authorship_and_voice_are_null(self):
        ep_id = self.store.add(
            title="t",
            summary="s",
            participants=["Maez"],
            source_memory_ids=["raw-1"],
            source_kind="core_memory",
        )
        ep = self.store.get(ep_id)
        self.assertIsNone(ep["authorship"])
        self.assertIsNone(ep["memory_voice"])

    def test_external_provenance_round_trips(self):
        ep_id = self.store.add(
            title="Project open loop: example",
            summary="external doc summary",
            participants=[],
            source_memory_ids=["followup-doc:docs/followups/example.md"],
            source_kind="followup_doc",
            authorship="project_doc",
            memory_voice="external_to_maez",
            open_loop="(project ledger) example",
        )
        ep = self.store.get(ep_id)
        self.assertEqual(ep["authorship"], "project_doc")
        self.assertEqual(ep["memory_voice"], "external_to_maez")
        self.assertEqual(ep["source_kind"], "followup_doc")


class EpisodeStoreSchemaMigrationIdempotent(unittest.TestCase):
    """Opening the store on a DB that already has the provenance
    columns must not error. The migration path uses ALTER TABLE ADD
    COLUMN guarded by a duplicate-column catch — this test pins that
    behavior."""

    def test_re_init_after_provenance_columns_exist(self):
        from core.memory.episodes import EpisodeStore

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            EpisodeStore(tmp.name)
            # Second open must succeed even though authorship /
            # memory_voice already exist from the first open.
            s2 = EpisodeStore(tmp.name)
            ep_id = s2.add(
                title="re-init-ok",
                summary="s",
                participants=["Maez"],
                source_memory_ids=["raw-x"],
                source_kind="core_memory",
            )
            self.assertTrue(ep_id.startswith("ep-"))
        finally:
            Path(tmp.name).unlink(missing_ok=True)


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


class EpisodeStoreSupersede(unittest.TestCase):
    """supersede() is the covenant-grade "retire a memory" operation:
    status flip plus provenance, never delete."""

    def setUp(self):
        from core.memory.episodes import EpisodeStore

        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.store = EpisodeStore(self._tmp.name)
        self.ep_id = self.store.add(
            title="t",
            summary="s",
            participants=["Maez"],
            source_memory_ids=["raw-1"],
            source_kind="reflection",
        )

    def tearDown(self):
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_supersede_unknown_id_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.store.supersede("ep-doesnotexist", reason="x")

    def test_supersede_active_stamps_provenance_and_excludes_from_active(self):
        ok = self.store.supersede(self.ep_id, reason="mislabeled provenance")
        self.assertTrue(ok)
        row = self.store.get(self.ep_id)
        self.assertIsNotNone(row, "superseded episode must NOT be deleted")
        self.assertEqual(row["status"], "superseded")
        self.assertEqual(row["superseded_reason"], "mislabeled provenance")
        self.assertIsNotNone(row["superseded_at"])
        self.assertIsNone(row["superseded_by"])
        active_ids = {e["id"] for e in self.store.list_active()}
        self.assertNotIn(self.ep_id, active_ids)

    def test_supersede_blank_reason_raises_valueerror_no_mutation(self):
        with self.assertRaises(ValueError):
            self.store.supersede(self.ep_id, reason="   ")
        self.assertEqual(self.store.get(self.ep_id)["status"], "active")

    def test_supersede_unknown_successor_raises_valueerror(self):
        with self.assertRaises(ValueError):
            self.store.supersede(self.ep_id, reason="r", superseded_by="ep-nope")
        self.assertEqual(self.store.get(self.ep_id)["status"], "active")

    def test_supersede_self_successor_raises_valueerror(self):
        with self.assertRaises(ValueError):
            self.store.supersede(self.ep_id, reason="r", superseded_by=self.ep_id)
        self.assertEqual(self.store.get(self.ep_id)["status"], "active")

    def test_supersede_with_valid_successor_stores_it(self):
        succ = self.store.add(
            title="t2",
            summary="s2",
            participants=["Maez"],
            source_memory_ids=["raw-2"],
            source_kind="reflection",
        )
        ok = self.store.supersede(self.ep_id, reason="replaced", superseded_by=succ)
        self.assertTrue(ok)
        self.assertEqual(self.store.get(self.ep_id)["superseded_by"], succ)

    def test_resupersede_returns_false_and_preserves_all_three_provenance_fields(self):
        succ = self.store.add(
            title="t2",
            summary="s2",
            participants=["Maez"],
            source_memory_ids=["raw-2"],
            source_kind="reflection",
        )
        self.assertTrue(
            self.store.supersede(self.ep_id, reason="first reason", superseded_by=succ)
        )
        first = self.store.get(self.ep_id)

        # Second call with a different reason/successor must be a no-op.
        self.assertFalse(
            self.store.supersede(self.ep_id, reason="SECOND reason", superseded_by=None)
        )
        second = self.store.get(self.ep_id)

        self.assertEqual(second["status"], "superseded")
        self.assertEqual(second["superseded_reason"], first["superseded_reason"])
        self.assertEqual(second["superseded_at"], first["superseded_at"])
        self.assertEqual(second["superseded_by"], first["superseded_by"])


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
        # Slice 4 audit M1 fix: timestamps are canonicalised to
        # ``+00:00`` form on entry so string comparison is sound.
        # Round-trip preserves the instant, not the source format.
        self.assertEqual(e["valid_from"], "2026-04-01T00:00:00+00:00")
        self.assertEqual(e["valid_to"], "2026-12-31T23:59:59+00:00")


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
