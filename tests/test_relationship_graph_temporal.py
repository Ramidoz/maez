# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Temporal validity tests for RelationshipGraph (Slice 4).

Adapted from Zep / Graphiti's pattern of modelling facts as
``(subject, relation, object, valid_from, valid_to)`` with explicit
``superseded_by`` chains. Maez had the columns from day one but the
public API never exposed temporal queries — ``list_active()`` only
answered "what's true NOW", never "what was true three months ago".

This slice closes the gap:

- ``add_edge`` defaults ``valid_from = created_at`` (the previous
  default of NULL meant brand-new edges had no temporal lower bound,
  so a temporal query couldn't tell them apart from edges with an
  explicit no-start-time semantics).
- Public ``list_active(at_time=None)`` method:
  - ``at_time=None`` → status='active' edges (current behaviour)
  - ``at_time=<iso>`` → edges that were active at that timestamp,
    regardless of their current status
- Idempotent backfill migration: existing rows with NULL
  ``valid_from`` get filled with ``created_at`` on first init,
  preserving the historical record.

Tests cover the temporal query semantics and the migration.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _graph():
    from core.memory.relationship_graph import RelationshipGraph

    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    p = Path(f.name)

    def cleanup():
        p.unlink(missing_ok=True)

    return RelationshipGraph(str(p)), str(p), cleanup


class TestAddEdgeDefaultsValidFrom(unittest.TestCase):
    """A new edge with no explicit ``valid_from`` should default to
    ``created_at`` so every edge has a temporal lower bound."""

    def test_new_edge_valid_from_defaults_to_created_at(self):
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="Rohit", kind="person")
            o = g.upsert_node(label="continuity", kind="value")
            edge_id = g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
            )
            edge = g.get_edge(edge_id)
            self.assertIsNotNone(edge["valid_from"])
            self.assertEqual(edge["valid_from"], edge["created_at"])
        finally:
            cleanup()

    def test_explicit_valid_from_preserved(self):
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="Rohit", kind="person")
            o = g.upsert_node(label="continuity", kind="value")
            edge_id = g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
                valid_from="2026-01-01T00:00:00+00:00",
            )
            edge = g.get_edge(edge_id)
            self.assertEqual(edge["valid_from"], "2026-01-01T00:00:00+00:00")
        finally:
            cleanup()


class TestListActiveCurrent(unittest.TestCase):
    """``list_active()`` (no args) returns edges with
    status='active' — the current snapshot. Mirrors the lived_recall
    direct-SQL access but as a public method."""

    def test_returns_active_edges_only(self):
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="Rohit", kind="person")
            o = g.upsert_node(label="continuity", kind="value")
            o2 = g.upsert_node(label="speed", kind="value")
            active_id = g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-a"], source_memory_ids=[],
            )
            old_id = g.add_edge(
                subject_id=s, relation="cares_about", object_id=o2,
                source_episode_ids=["ep-b"], source_memory_ids=[],
            )
            g.supersede(
                old_id,
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-c"], source_memory_ids=[],
            )
            results = g.list_active()
            ids = {e["id"] for e in results}
            self.assertIn(active_id, ids)
            self.assertNotIn(old_id, ids)
        finally:
            cleanup()

    def test_each_edge_carries_subject_and_object_labels(self):
        """``list_active`` should return edges joined with their
        subject/object node labels — the canonical shape lived_recall
        and working_self need. Avoids every caller re-implementing
        the JOIN."""
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="Rohit", kind="person")
            o = g.upsert_node(label="continuity", kind="value")
            g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
            )
            results = g.list_active()
            self.assertEqual(len(results), 1)
            edge = results[0]
            self.assertEqual(edge["subject_label"], "Rohit")
            self.assertEqual(edge["object_label"], "continuity")
        finally:
            cleanup()


class TestListActiveAtTime(unittest.TestCase):
    """``list_active(at_time=<iso>)`` returns edges that were active
    at the given moment, regardless of their current status. Closes
    the audit gap: 'what did Rohit care about three months ago?'"""

    def test_returns_edges_active_at_past_time(self):
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="Rohit", kind="person")
            o_old = g.upsert_node(label="speed", kind="value")
            o_new = g.upsert_node(label="continuity", kind="value")
            old_edge = g.add_edge(
                subject_id=s, relation="cares_about", object_id=o_old,
                source_episode_ids=["ep-old"], source_memory_ids=[],
                valid_from="2026-01-01T00:00:00+00:00",
            )
            # Supersede on 2026-04-01: the old edge becomes inactive,
            # but it WAS active during Jan-Mar.
            g.supersede(
                old_edge,
                subject_id=s, relation="cares_about", object_id=o_new,
                source_episode_ids=["ep-new"], source_memory_ids=[],
                valid_from="2026-04-01T00:00:00+00:00",
            )
            # Query "what was true on 2026-02-15?" — should return
            # the old edge (cares_about speed), not the new one.
            results = g.list_active(at_time="2026-02-15T00:00:00+00:00")
            relations = {(e["subject_label"], e["object_label"])
                         for e in results}
            self.assertIn(("Rohit", "speed"), relations)
            self.assertNotIn(("Rohit", "continuity"), relations)
        finally:
            cleanup()

    def test_returns_edges_active_at_current_time(self):
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="Rohit", kind="person")
            o = g.upsert_node(label="continuity", kind="value")
            g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
                valid_from="2026-01-01T00:00:00+00:00",
            )
            results = g.list_active(at_time="2026-04-30T00:00:00+00:00")
            self.assertEqual(len(results), 1)
        finally:
            cleanup()

    def test_excludes_edges_starting_after_query_time(self):
        """An edge with valid_from in the future of the query time
        was NOT active then — exclude."""
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="Rohit", kind="person")
            o = g.upsert_node(label="continuity", kind="value")
            g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
                valid_from="2026-04-01T00:00:00+00:00",
            )
            results = g.list_active(at_time="2026-02-15T00:00:00+00:00")
            self.assertEqual(len(results), 0)
        finally:
            cleanup()

    def test_includes_open_ended_edges(self):
        """An edge with valid_to=NULL is open-ended — active at any
        time after valid_from."""
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="Rohit", kind="person")
            o = g.upsert_node(label="continuity", kind="value")
            g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
                valid_from="2026-01-01T00:00:00+00:00",
                # valid_to=None implicit
            )
            results = g.list_active(at_time="2050-01-01T00:00:00+00:00")
            self.assertEqual(len(results), 1)
        finally:
            cleanup()


class TestBackfillMigration(unittest.TestCase):
    """Idempotent backfill: existing rows with NULL ``valid_from``
    get filled with ``created_at`` on first init. Preserves the
    historical record (we know the edge existed *at least* from its
    creation time onward)."""

    def test_legacy_edge_with_null_valid_from_gets_backfilled(self):
        from core.memory.relationship_graph import RelationshipGraph

        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        path = Path(f.name)
        try:
            # Simulate a pre-Slice-4 DB: insert an edge directly
            # with NULL valid_from.
            with sqlite3.connect(str(path)) as c:
                c.executescript("""
                    CREATE TABLE nodes (id TEXT PRIMARY KEY, label TEXT,
                        kind TEXT, created_at TEXT, updated_at TEXT,
                        UNIQUE(label, kind));
                    CREATE TABLE edges (id TEXT PRIMARY KEY,
                        subject_id TEXT, relation TEXT, object_id TEXT,
                        valid_from TEXT, valid_to TEXT,
                        confidence REAL, status TEXT,
                        source_episode_ids_json TEXT,
                        source_memory_ids_json TEXT,
                        created_at TEXT, updated_at TEXT);
                """)
                c.execute(
                    "INSERT INTO nodes VALUES ('n-a','Rohit','person',"
                    "'2026-01-01T00:00:00+00:00',"
                    "'2026-01-01T00:00:00+00:00')"
                )
                c.execute(
                    "INSERT INTO nodes VALUES ('n-b','x','value',"
                    "'2026-01-01T00:00:00+00:00',"
                    "'2026-01-01T00:00:00+00:00')"
                )
                c.execute(
                    "INSERT INTO edges VALUES ('e-1','n-a','cares_about',"
                    "'n-b',NULL,NULL,0.9,'active','[]','[\"raw-1\"]',"
                    "'2026-01-01T00:00:00+00:00',"
                    "'2026-01-01T00:00:00+00:00')"
                )
                c.commit()
            # Now construct the graph — migration should backfill
            # the NULL valid_from with created_at.
            g = RelationshipGraph(str(path))
            edge = g.get_edge("e-1")
            self.assertEqual(edge["valid_from"], "2026-01-01T00:00:00+00:00")
        finally:
            path.unlink(missing_ok=True)


class TestTimestampCanonicalisation(unittest.TestCase):
    """Audit M1+M2 (2026-04-29 Slice-4 review): the original
    implementation used naive string comparison on ISO-8601
    timestamps. ``"Z"`` (0x5A) > ``"+"`` (0x2B) means
    ``"2026-01-01T00:00:00Z" > "2026-01-01T00:00:00+00:00"`` even
    though they represent the same instant. Plus, malformed input
    (``"not-a-timestamp"``) was silently accepted and produced
    nonsensical results.

    Fix: canonicalise via ``datetime.fromisoformat`` at function
    entry; raise ``ValueError`` on malformed input."""

    def test_z_suffix_normalises_to_plus_zero(self):
        """Same instant in Z and +00:00 form must produce the same
        active-set result."""
        from core.memory.relationship_graph import RelationshipGraph
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        path = Path(f.name)
        try:
            g = RelationshipGraph(str(path))
            s = g.upsert_node(label="Rohit", kind="person")
            o = g.upsert_node(label="continuity", kind="value")
            g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
                valid_from="2026-01-01T00:00:00+00:00",
            )
            # Query with a Z-suffixed timestamp denoting the same
            # instant. Must canonicalise and find the edge.
            results_z = g.list_active(at_time="2026-04-30T00:00:00Z")
            results_plus = g.list_active(at_time="2026-04-30T00:00:00+00:00")
            self.assertEqual(len(results_z), len(results_plus),
                             "Z and +00:00 must denote the same instant")
            self.assertEqual(len(results_z), 1)
        finally:
            path.unlink(missing_ok=True)

    def test_malformed_at_time_raises(self):
        from core.memory.relationship_graph import RelationshipGraph
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        path = Path(f.name)
        try:
            g = RelationshipGraph(str(path))
            with self.assertRaises(ValueError):
                g.list_active(at_time="not-a-timestamp")
        finally:
            path.unlink(missing_ok=True)


class TestHalfOpenIntervalSemantics(unittest.TestCase):
    """Audit N4: the temporal predicate is half-open
    ``[valid_from, valid_to)``. At the supersede boundary, the
    successor edge is the active one (no overlap, no gap). These
    boundary tests lock the semantics so a future refactor can't
    flip strict/non-strict undetected."""

    def test_at_time_equals_valid_from_includes_edge(self):
        from core.memory.relationship_graph import RelationshipGraph
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        path = Path(f.name)
        try:
            g = RelationshipGraph(str(path))
            s = g.upsert_node(label="A", kind="person")
            o = g.upsert_node(label="B", kind="value")
            g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
                valid_from="2026-04-15T12:00:00+00:00",
            )
            # at_time exactly = valid_from → edge IS active.
            results = g.list_active(at_time="2026-04-15T12:00:00+00:00")
            self.assertEqual(len(results), 1)
        finally:
            path.unlink(missing_ok=True)

    def test_at_time_equals_valid_to_excludes_edge(self):
        from core.memory.relationship_graph import RelationshipGraph
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        path = Path(f.name)
        try:
            g = RelationshipGraph(str(path))
            s = g.upsert_node(label="A", kind="person")
            o = g.upsert_node(label="B", kind="value")
            edge = g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
                valid_from="2026-04-15T00:00:00+00:00",
            )
            # Manually set valid_to via supersede.
            o2 = g.upsert_node(label="C", kind="value")
            g.supersede(
                edge,
                subject_id=s, relation="cares_about", object_id=o2,
                source_episode_ids=["ep-2"], source_memory_ids=[],
                valid_from="2026-04-20T12:00:00+00:00",
            )
            # at_time exactly = valid_to of old edge → old edge is
            # NOT active (half-open interval); new edge IS active.
            results = g.list_active(at_time="2026-04-20T12:00:00+00:00")
            objs = {e["object_label"] for e in results}
            self.assertNotIn("B", objs,
                             "old edge with valid_to=T must not be "
                             "active at exactly T (half-open)")
            self.assertIn("C", objs,
                          "successor edge with valid_from=T must be "
                          "active at exactly T (half-open)")
        finally:
            path.unlink(missing_ok=True)


class TestEmptyGraphTemporalQuery(unittest.TestCase):
    def test_empty_graph_at_time_returns_empty(self):
        g, _, cleanup = _graph()
        try:
            results = g.list_active(at_time="2026-04-15T00:00:00+00:00")
            self.assertEqual(results, [])
        finally:
            cleanup()


class TestTemporalBoundsValidation(unittest.TestCase):
    """Audit Explore #8 (essential): nothing prevents
    ``valid_to <= valid_from``. The temporal model must reject
    logical contradictions at write time, not silently store them."""

    def test_add_edge_rejects_inverted_bounds(self):
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="A", kind="person")
            o = g.upsert_node(label="B", kind="value")
            with self.assertRaises(ValueError):
                g.add_edge(
                    subject_id=s, relation="cares_about", object_id=o,
                    source_episode_ids=["ep-1"], source_memory_ids=[],
                    valid_from="2026-04-20T00:00:00+00:00",
                    valid_to="2026-04-15T00:00:00+00:00",
                )
        finally:
            cleanup()

    def test_add_edge_rejects_equal_bounds(self):
        """Half-open interval: valid_to must be strictly after
        valid_from, otherwise the edge is never active."""
        g, _, cleanup = _graph()
        try:
            s = g.upsert_node(label="A", kind="person")
            o = g.upsert_node(label="B", kind="value")
            with self.assertRaises(ValueError):
                g.add_edge(
                    subject_id=s, relation="cares_about", object_id=o,
                    source_episode_ids=["ep-1"], source_memory_ids=[],
                    valid_from="2026-04-20T00:00:00+00:00",
                    valid_to="2026-04-20T00:00:00+00:00",
                )
        finally:
            cleanup()


class TestCorruptJsonResilience(unittest.TestCase):
    """Audit N1: one corrupt JSON cell shouldn't break all
    list_active() callers. Defensive per-row JSON decoding."""

    def test_corrupt_row_does_not_break_full_query(self):
        from core.memory.relationship_graph import RelationshipGraph
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        f.close()
        path = Path(f.name)
        try:
            g = RelationshipGraph(str(path))
            s = g.upsert_node(label="A", kind="person")
            o = g.upsert_node(label="B", kind="value")
            o2 = g.upsert_node(label="C", kind="value")
            good = g.add_edge(
                subject_id=s, relation="cares_about", object_id=o,
                source_episode_ids=["ep-1"], source_memory_ids=[],
            )
            bad = g.add_edge(
                subject_id=s, relation="cares_about", object_id=o2,
                source_episode_ids=["ep-2"], source_memory_ids=[],
            )
            # Corrupt one row's JSON.
            with sqlite3.connect(str(path)) as c:
                c.execute(
                    "UPDATE edges SET source_episode_ids_json = ? "
                    "WHERE id = ?",
                    ("not valid json {{{", bad),
                )
                c.commit()
            results = g.list_active()
            # The good edge must still come through.
            ids = {e["id"] for e in results}
            self.assertIn(good, ids,
                          "good edge must survive a corrupt sibling")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
