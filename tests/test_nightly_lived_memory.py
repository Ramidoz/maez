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

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


def _followup_memory(mid="followup-doc:docs/followups/example.md"):
    return {
        "id": mid,
        "document": (
            "# Example deferred follow-up\n\n"
            "**Status:** Deferred follow-up. Filed 2026-04-27.\n\n"
            "## What this is\n\n"
            "A placeholder body so the detector has substance to chew on."
        ),
        "metadata": {
            "kind": "followup",
            "source": "docs_followups",
            "authorship": "project_doc",
            "memory_voice": "external_to_maez",
            "file_path": "docs/followups/example.md",
        },
    }


class FollowupIngestProducesProjectDocEpisode(unittest.TestCase):
    """End-to-end through run_reflection: a followup-doc memory must
    land an episode with provenance = project_doc / external_to_maez,
    source_kind = followup_doc, no first-person participants, and the
    open_loop field set so the recall planner surfaces it."""

    def test_followup_round_trip_through_orchestrator(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            run_reflection,
        )

        store, graph, cleanup = _stores()
        try:
            report = run_reflection(
                memories=[_followup_memory()],
                episode_store=store,
                graph=graph,
            )
            self.assertEqual(report.candidates_seen, 1)
            self.assertEqual(report.episodes_added, 1)
            active = store.list_active()
            self.assertEqual(len(active), 1)
            ep = active[0]
            self.assertEqual(ep["source_kind"], "followup_doc")
            self.assertEqual(ep["authorship"], "project_doc")
            self.assertEqual(ep["memory_voice"], "external_to_maez")
            # No first-person attribution on a project doc.
            self.assertEqual(ep["participants"], [])
            # Open loop populated so the recall planner can surface it.
            self.assertTrue(ep["open_loop"])
            self.assertIn("project ledger", (ep["open_loop"] or "").lower())
            # Evidence points back to the file via the synthetic id.
            self.assertEqual(len(ep["source_memory_ids"]), 1)
            self.assertTrue(
                ep["source_memory_ids"][0].startswith("followup-doc:")
            )
        finally:
            cleanup()


class LoadFollowupsReadsRealDirectory(unittest.TestCase):
    """The loader must read a temp followups directory and emit one
    memory-shaped dict per .md file with the provenance metadata
    pre-set so the builder doesn't have to re-derive it."""

    def test_load_followups_emits_provenance_metadata(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            _load_followups,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs" / "followups").mkdir(parents=True)
            (root / "docs" / "followups" / "alpha.md").write_text(
                "# Alpha\n\n**Status:** Deferred follow-up.\n",
                encoding="utf-8",
            )
            (root / "docs" / "followups" / "beta.md").write_text(
                "# Beta\n\nNot a followup header.\n",
                encoding="utf-8",
            )
            out = _load_followups(root)
            # Both files are picked up — the builder, not the loader,
            # is responsible for rejecting docs that lack the status
            # header. Loader is a thin file-system reader.
            self.assertEqual(len(out), 2)
            ids = {m["id"] for m in out}
            self.assertIn("followup-doc:docs/followups/alpha.md", ids)
            self.assertIn("followup-doc:docs/followups/beta.md", ids)
            for m in out:
                meta = m["metadata"]
                self.assertEqual(meta["kind"], "followup")
                self.assertEqual(meta["source"], "docs_followups")
                self.assertEqual(meta["authorship"], "project_doc")
                self.assertEqual(meta["memory_voice"], "external_to_maez")
                self.assertTrue(meta.get("file_path"))

    def test_load_followups_missing_dir_returns_empty(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            _load_followups,
        )

        with tempfile.TemporaryDirectory() as td:
            # No docs/followups subtree at all.
            out = _load_followups(Path(td))
            self.assertEqual(out, [])


class MissingDailyAccessorFailsLoud(unittest.TestCase):
    """Silent ``except AttributeError`` swallowed an entire daily corpus
    for an unknown number of nightly runs — an ingestion bug that
    looked like cognition failure on the lived-memory probes. The
    replacement contract: missing accessor raises RuntimeError with
    a message that names the broken contract, never silently empties
    the corpus."""

    def test_missing_get_recent_daily_raises(self):
        # Simulate a MemoryManager that has lost the accessor.
        from scripts.memory_reflection import nightly_lived_memory as nlm

        class FakeMM:
            def get_all_core(self):
                return []

            # Intentionally no get_recent_daily.

        # Patch the import target the loader uses.
        import memory.memory_manager as mm_mod

        original = mm_mod.MemoryManager
        mm_mod.MemoryManager = FakeMM
        try:
            with self.assertRaises(RuntimeError) as ctx:
                nlm._load_memories_from_chroma()
            self.assertIn("get_recent_daily", str(ctx.exception))
        finally:
            mm_mod.MemoryManager = original


class M1EpisodesExcludedFromReflectionSynthesis(unittest.TestCase):
    def test_synthesis_pass_excludes_telegram_exchange_episodes(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            ReflectionReport,
            run_synthesis_pass,
        )

        store, graph, cleanup = _stores()
        try:
            store.add(
                title="Bonded conversation with Rohit",
                summary=(
                    "Bonded Telegram exchange. 1 audited owner/Maez pair at "
                    "2026-05-14T18:00:00+00:00. Participants: Rohit, Maez."
                ),
                participants=["Rohit", "Maez"],
                source_memory_ids=["raw-m1-1"],
                source_kind="telegram_exchange",
                occurred_at="2026-05-14T18:00:00+00:00",
                authorship="bonded_dialogue",
                memory_voice="mixed_owner_maez",
            )
            report = ReflectionReport()
            calls = []

            def fake_llm(prompt: str) -> str:
                calls.append(prompt)
                return (
                    '[{"reflection": "should not be generated", '
                    '"evidence_ids": ["raw-m1-1"], "confidence": 0.9}]'
                )

            run_synthesis_pass(
                episode_store=store,
                llm_call=fake_llm,
                report=report,
            )

            self.assertEqual(calls, [])
            self.assertEqual(report.reflections_attempted, 0)
            self.assertEqual(report.reflections_added, 0)
            self.assertEqual(len(store.list_active()), 1)
        finally:
            cleanup()


class ReflectionSynthesisTerminalMetadataTests(unittest.TestCase):
    def test_report_derives_truncated_and_valid_witness_from_finish_reason(self):
        from scripts.memory_reflection.nightly_lived_memory import ReflectionReport

        report = ReflectionReport(finish_reason="length")
        self.assertTrue(report.truncated)
        self.assertFalse(report.valid_witness)

        report.finish_reason = "stop"
        self.assertFalse(report.truncated)
        self.assertTrue(report.valid_witness)

        report.finish_reason = "llm_timeout"
        self.assertFalse(report.truncated)
        self.assertFalse(report.valid_witness)

    def test_default_llm_call_records_stop_finish_reason_budget_and_raw_content(self):
        from scripts.memory_reflection import nightly_lived_memory as nlm

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "finish_reason": "stop",
                                "message": {"content": "[{}]"},
                            }
                        ]
                    }
                ).encode("utf-8")

        with mock.patch("urllib.request.urlopen", return_value=_Resp()):
            llm_call = nlm._default_llm_call("qwen36-27b", 240)
            text = llm_call("prompt")

        self.assertEqual(text, "[{}]")
        self.assertEqual(llm_call.last_finish_reason, "stop")
        self.assertEqual(llm_call.max_tokens, 8192)
        self.assertEqual(llm_call.last_raw_content, "[{}]")

    def test_default_llm_call_records_length_finish_reason(self):
        from scripts.memory_reflection import nightly_lived_memory as nlm

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "finish_reason": "length",
                                "message": {"content": ""},
                            }
                        ]
                    }
                ).encode("utf-8")

        with mock.patch("urllib.request.urlopen", return_value=_Resp()):
            llm_call = nlm._default_llm_call("qwen36-27b", 240)
            text = llm_call("prompt")

        self.assertEqual(text, "")
        self.assertEqual(llm_call.last_finish_reason, "length")
        self.assertEqual(llm_call.max_tokens, 8192)
        self.assertEqual(llm_call.last_raw_content, "")

    def test_default_llm_call_records_timeout_as_terminal_reason(self):
        from scripts.memory_reflection import nightly_lived_memory as nlm

        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            llm_call = nlm._default_llm_call("qwen36-27b", 240)
            text = llm_call("prompt")

        self.assertEqual(text, "")
        self.assertEqual(llm_call.last_finish_reason, "llm_timeout")
        self.assertEqual(llm_call.max_tokens, 8192)
        self.assertEqual(llm_call.last_raw_content, "")

    def test_run_synthesis_pass_copies_terminal_metadata_from_llm_call(self):
        from scripts.memory_reflection.nightly_lived_memory import (
            ReflectionReport,
            run_synthesis_pass,
        )

        store, _graph, cleanup = _stores()
        try:
            store.add(
                title="Runtime correction",
                summary="Maez corrected an earlier false claim about its runtime.",
                participants=["Maez", "Rohit"],
                source_memory_ids=["core-runtime-correction"],
                source_kind="core_memory",
                occurred_at="2026-06-02T00:00:00+00:00",
            )

            def fake_llm(_prompt: str) -> str:
                fake_llm.last_finish_reason = "length"
                fake_llm.max_tokens = 8192
                fake_llm.last_raw_content = ""
                return ""

            report = ReflectionReport(dry_run=True)
            run_synthesis_pass(
                episode_store=store,
                llm_call=fake_llm,
                report=report,
                dry_run=True,
            )

            self.assertEqual(report.finish_reason, "length")
            self.assertEqual(report.max_tokens, 8192)
            self.assertEqual(report.raw_model_content, "")
            self.assertTrue(report.truncated)
            self.assertFalse(report.valid_witness)
        finally:
            cleanup()


if __name__ == "__main__":
    unittest.main()
