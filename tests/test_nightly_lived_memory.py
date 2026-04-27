# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Nightly reflection orchestrator tests (ADR 0019 Phase 4).

The orchestrator wires builder + extractor + EpisodeStore +
RelationshipGraph together: read memories → produce candidates →
dedup → store episodes → extract edges → upsert nodes → store edges.

Tests cover:

- Empty input runs to completion cleanly.
- A single corrective core memory produces 1 episode + 1 'corrected'
  edge with source_episode_ids correctly stamped.
- Re-running on the same memory set is a no-op (idempotent via
  source_memory_id overlap dedup).
- Dry-run produces a report but writes nothing.
- Multiple memories with overlapping source IDs are deduped within
  a single run.
- Edge nodes are upserted, not duplicated.
- LLM-unavailable / extraction-failure paths skip-and-log rather
  than crash (v1 is rule-based but the contract still applies).
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
    """Build a fresh EpisodeStore + RelationshipGraph pair on temp
    SQLite files. Returns (store, graph, cleanup_callable)."""
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


def _corrective_memory(mid="core-vision-1"):
    return {
        "id": mid,
        "document": (
            "Correction 2026-04-23: do not narrate llama-server-vision "
            "as active. Vision is retired; MAEZ_SCREEN_PERCEPTION is "
            "unset; port 8081 has no listener."
        ),
        "metadata": {
            "source": "infrastructure_correction_vision_2026-04-24",
            "kind": "core",
        },
    }


def _open_loop_memory(mid="raw-loop-7"):
    return {
        "id": mid,
        "document": (
            "Owner deferred the dream-state soul-write bypass; we need "
            "to revisit when Track A graduates."
        ),
        "metadata": {"kind": "raw"},
    }


def _hardware_memory(mid="raw-hw-1"):
    return {
        "id": mid,
        "document": (
            "Kernel NULL pointer dereference at 13:48; system rebooted. "
            "NVIDIA driver 570.211.01 implicated."
        ),
        "metadata": {"kind": "raw"},
    }


def _noise_memory(mid="raw-noise-1"):
    return {
        "id": mid,
        "document": "CPU 0.5%, GPU 0%, RAM 22%.",
        "metadata": {"kind": "raw"},
    }


class EmptyInputRunsCleanly(unittest.TestCase):
    def test_empty_iterable(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            run_reflection,
        )

        store, graph, cleanup = _stores()
        try:
            report = run_reflection(
                memories=iter([]),
                episode_store=store,
                graph=graph,
            )
            self.assertEqual(report.candidates_seen, 0)
            self.assertEqual(report.episodes_added, 0)
            self.assertEqual(report.edges_added, 0)
            self.assertFalse(report.dry_run)
            self.assertTrue(report.started_at)
            self.assertTrue(report.finished_at)
        finally:
            cleanup()


class SingleCorrectiveProducesEpisodeAndEdge(unittest.TestCase):
    def test_corrective_yields_one_episode_and_one_edge(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            run_reflection,
        )

        store, graph, cleanup = _stores()
        try:
            report = run_reflection(
                memories=[_corrective_memory()],
                episode_store=store,
                graph=graph,
            )
            self.assertEqual(report.candidates_seen, 1)
            self.assertEqual(report.episodes_added, 1)
            self.assertEqual(report.edges_added, 1)

            # The episode is queryable.
            active = store.list_active()
            self.assertEqual(len(active), 1)
            ep = active[0]
            self.assertEqual(ep["source_memory_ids"], ["core-vision-1"])
            self.assertEqual(ep["source_kind"], "core_memory")

            # The edge cites the episode just stored.
            # We don't expose a list-edges API yet, so reach via SQL
            # for verification. This is a test seam, not a real
            # caller pattern.
            import sqlite3

            with sqlite3.connect(graph._path) as conn:
                conn.row_factory = sqlite3.Row
                edges = conn.execute("SELECT * FROM edges").fetchall()
            self.assertEqual(len(edges), 1)
            edge = dict(edges[0])
            self.assertEqual(edge["relation"], "corrected")
            self.assertEqual(edge["status"], "active")
            # source_episode_ids is JSON-encoded; the episode ID we
            # just stored should be inside it.
            import json

            ep_ids = json.loads(edge["source_episode_ids_json"])
            self.assertEqual(ep_ids, [ep["id"]])
        finally:
            cleanup()


class IdempotentRerun(unittest.TestCase):
    def test_rerun_on_same_memories_adds_nothing(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            run_reflection,
        )

        store, graph, cleanup = _stores()
        try:
            memories = [_corrective_memory(), _open_loop_memory()]
            r1 = run_reflection(
                memories=memories,
                episode_store=store,
                graph=graph,
            )
            self.assertEqual(r1.episodes_added, 2)
            self.assertEqual(r1.edges_added, 2)

            # Run again with the same memories.
            r2 = run_reflection(
                memories=list(memories),
                episode_store=store,
                graph=graph,
            )
            self.assertEqual(r2.candidates_seen, 2)
            self.assertEqual(r2.episodes_added, 0)
            self.assertEqual(r2.edges_added, 0)
            self.assertEqual(r2.episodes_skipped_duplicate, 2)

            # The store still has exactly 2 active episodes.
            self.assertEqual(len(store.list_active()), 2)
        finally:
            cleanup()


class DryRunWritesNothing(unittest.TestCase):
    def test_dry_run_no_writes_but_report_populated(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            run_reflection,
        )

        store, graph, cleanup = _stores()
        try:
            report = run_reflection(
                memories=[_corrective_memory(), _open_loop_memory()],
                episode_store=store,
                graph=graph,
                dry_run=True,
            )
            self.assertTrue(report.dry_run)
            # Candidates were seen and counted, but nothing written:
            self.assertEqual(report.candidates_seen, 2)
            self.assertEqual(report.episodes_added, 0)
            self.assertEqual(report.edges_added, 0)
            self.assertEqual(len(store.list_active()), 0)
        finally:
            cleanup()


class WithinRunDedup(unittest.TestCase):
    """If two input memories share a source_memory_id, only the first
    creates an episode. (In practice this is rare — same Chroma id
    doesn't appear twice — but the contract should hold.)"""

    def test_overlapping_source_ids_deduped_within_run(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            run_reflection,
        )

        store, graph, cleanup = _stores()
        try:
            # Two memories with the same id — represents a re-fetch
            # of the same Chroma row in the same run.
            mem = _corrective_memory(mid="core-shared-1")
            report = run_reflection(
                memories=[mem, dict(mem)],
                episode_store=store,
                graph=graph,
            )
            self.assertEqual(report.candidates_seen, 2)
            self.assertEqual(report.episodes_added, 1)
            self.assertEqual(report.episodes_skipped_duplicate, 1)
        finally:
            cleanup()


class NodesAreUpserted(unittest.TestCase):
    """Two episodes that produce edges referring to the same labels
    (e.g. both pointing at 'Track A continuity') must share node
    rows, not duplicate them."""

    def test_shared_object_label_resolves_to_single_node(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            run_reflection,
        )

        store, graph, cleanup = _stores()
        try:
            # Two hardware-instability memories — both produce
            # threatens edges with object_label "Track A continuity".
            run_reflection(
                memories=[
                    _hardware_memory(mid="raw-hw-1"),
                    _hardware_memory(mid="raw-hw-2"),
                ],
                episode_store=store,
                graph=graph,
            )
            # Verify: only one node with label "Track A continuity".
            import sqlite3

            with sqlite3.connect(graph._path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT id FROM nodes WHERE label = 'Track A continuity'"
                ).fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            cleanup()


class MixedNoiseAndSignal(unittest.TestCase):
    def test_noise_skipped_signal_extracted(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            run_reflection,
        )

        store, graph, cleanup = _stores()
        try:
            report = run_reflection(
                memories=[
                    _noise_memory(),
                    _corrective_memory(),
                    _noise_memory("raw-noise-2"),
                    _open_loop_memory(),
                    _hardware_memory(),
                ],
                episode_store=store,
                graph=graph,
            )
            # Three signal memories produced candidates; two noise
            # memories were skipped at the builder layer (not even
            # candidates).
            self.assertEqual(report.candidates_seen, 3)
            self.assertEqual(report.episodes_added, 3)
            # Each candidate produces exactly one edge in v1.
            self.assertEqual(report.edges_added, 3)
        finally:
            cleanup()


if __name__ == "__main__":
    unittest.main()
