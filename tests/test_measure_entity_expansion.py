# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Lightweight A/B measurement tests (Step 5j).

The script measures whether ``MAEZ_ENTITY_EXPANSION`` changes the
lived-recall brief — NOT whether the added context is relevant. The
test surface accordingly: behavior change is asserted; relevance is
the operator's call from the diff excerpt.
"""

from __future__ import annotations

import io
import json
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


# ── helpers ────────────────────────────────────────────────────────


def _build(td: Path, *, with_mentions: bool = True):
    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

    ep = EpisodeStore(str(td / "ep.db"))
    g = RelationshipGraph(str(td / "g.db"))
    ix = EntityIndex(td / "ix.db")
    eid = ep.add(
        title="Maya Ananthan started school",
        summary="we discussed Maya Ananthan starting at the new school",
        participants=["rohit"],
        source_memory_ids=["mem-1"],
        source_kind="conversation",
        occurred_at="2026-04-12T09:00:00+00:00",
    )
    if with_mentions:
        ent = ix.upsert_entity(
            "Maya Ananthan", kind="person", aliases=["Maya"],
        )
        ix.add_mention(
            entity_id=ent, session_id=eid, source_id="mem-1",
            source_kind="episode",
            observed_at="2026-04-12T09:00:00+00:00",
            snippet="x", confidence=0.9,
        )
        ix.add_mention(
            entity_id=ent, session_id="ep-other", source_id="mem-2",
            source_kind="episode",
            observed_at="2026-04-15T09:00:00+00:00",
            snippet="x", confidence=0.9,
        )
    return ep, g, ix, eid


# ── env control ───────────────────────────────────────────────────


class TestEnvIsExplicitlyControlled(unittest.TestCase):
    def test_baseline_is_baseline_even_when_env_already_set(self):
        """If the operator runs the script with MAEZ_ENTITY_EXPANSION
        already exported, the baseline pass MUST still produce a
        baseline brief (no expansion section)."""
        from scripts.measure_entity_expansion import measure

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, _ = _build(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                m = measure(
                    "tell me about Maya Ananthan",
                    ix=ix, episode_store=ep, graph=g,
                    reference_time=ref,
                )
            # Baseline must NOT contain the expansion section.
            self.assertNotIn("ENTITY EXPANSION", m["baseline_brief"])
            # Expanded MUST contain it.
            self.assertIn("ENTITY EXPANSION", m["expanded_brief"])

    def test_prior_env_state_restored(self):
        from scripts.measure_entity_expansion import measure

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, _ = _build(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "yes"}):
                measure(
                    "Maya Ananthan",
                    ix=ix, episode_store=ep, graph=g,
                    reference_time=ref,
                )
                self.assertEqual(os.environ.get(_FLAG), "yes")

    def test_prior_env_unset_remains_unset(self):
        from scripts.measure_entity_expansion import measure

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, _ = _build(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            env = dict(os.environ)
            env.pop(_FLAG, None)
            with mock.patch.dict(os.environ, env, clear=True):
                measure(
                    "Maya Ananthan",
                    ix=ix, episode_store=ep, graph=g,
                    reference_time=ref,
                )
                self.assertNotIn(_FLAG, os.environ)


# ── metric shape ──────────────────────────────────────────────────


class TestMeasurementMetrics(unittest.TestCase):
    def test_metrics_present(self):
        from scripts.measure_entity_expansion import measure

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, eid = _build(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            m = measure(
                "tell me about Maya Ananthan",
                ix=ix, episode_store=ep, graph=g,
                reference_time=ref,
            )
            for k in (
                "query", "baseline_chars", "expanded_chars",
                "entity_section_present", "entities_surfaced",
                "new_entities", "baseline_session_ids",
                "expanded_session_ids", "new_session_ids",
                "brief_diff_excerpt",
            ):
                self.assertIn(k, m, f"missing metric: {k}")

    def test_new_session_ids_is_set_diff(self):
        from scripts.measure_entity_expansion import measure

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, eid = _build(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            m = measure(
                "tell me about Maya Ananthan",
                ix=ix, episode_store=ep, graph=g,
                reference_time=ref,
            )
            self.assertEqual(
                set(m["new_session_ids"]),
                set(m["expanded_session_ids"])
                - set(m["baseline_session_ids"]),
            )

    def test_entities_surfaced_picks_up_canonical_name(self):
        from scripts.measure_entity_expansion import measure

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, _ = _build(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            m = measure(
                "tell me about Maya Ananthan",
                ix=ix, episode_store=ep, graph=g,
                reference_time=ref,
            )
            self.assertTrue(m["entity_section_present"])
            self.assertIn("Maya Ananthan", m["entities_surfaced"])
            self.assertGreaterEqual(m["new_entities"], 1)


# ── empty index ──────────────────────────────────────────────────


class TestEmptyIndexHandling(unittest.TestCase):
    def test_main_warns_and_exits_zero_on_empty_index(self):
        from scripts.measure_entity_expansion import main

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, g, ix, _ = _build(tdp, with_mentions=False)
            err = io.StringIO()
            with mock.patch("sys.stderr", err):
                rc = main([
                    "--index-db", str(tdp / "ix.db"),
                    "--episodes-db", str(tdp / "ep.db"),
                    "--graph-db", str(tdp / "g.db"),
                ])
            self.assertEqual(rc, 0)
            err_text = err.getvalue().lower()
            self.assertIn("entity index", err_text)
            self.assertTrue(
                "empty" in err_text or "no entities" in err_text
                or "no mentions" in err_text,
                f"expected an empty-index hint in stderr, got: {err_text!r}",
            )


# ── default queries derived from index ───────────────────────────


class TestDefaultQueries(unittest.TestCase):
    def test_default_queries_pull_top_entities_by_mention_count(self):
        from scripts.measure_entity_expansion import (
            default_queries_from_index,
        )
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ix = EntityIndex(Path(td) / "ix.db")
            for i in range(7):
                ent = ix.upsert_entity(
                    f"Entity {i:02d}", kind="person",
                )
                # Higher i → more mentions, so top-by-count is
                # deterministic for the assertion.
                for j in range(i + 1):
                    ix.add_mention(
                        entity_id=ent,
                        session_id=f"ep-{i}-{j}",
                        source_id=f"mem-{i}-{j}",
                        source_kind="episode",
                        observed_at=(
                            f"2026-04-{10 + j:02d}T09:00:00+00:00"
                        ),
                        snippet="x", confidence=0.9,
                    )
            queries = default_queries_from_index(ix, top_n=5)
            self.assertEqual(len(queries), 5)
            # Top-5 are the highest mention counts: 06, 05, 04, 03, 02.
            for q in queries:
                self.assertTrue(
                    q.startswith("tell me about "), q,
                )
            self.assertIn("tell me about Entity 06", queries)
            self.assertIn("tell me about Entity 02", queries)
            self.assertNotIn("tell me about Entity 00", queries)


# ── queries file ─────────────────────────────────────────────────


class TestQueriesFile(unittest.TestCase):
    def test_queries_file_one_per_line(self):
        from scripts.measure_entity_expansion import _load_queries_file

        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "qs.txt"
            f.write_text(
                "what about Maya?\n"
                "# this is a comment, ignored\n"
                "\n"
                "tell me about Track A\n",
            )
            queries = _load_queries_file(f)
            self.assertEqual(
                queries, ["what about Maya?", "tell me about Track A"],
            )


# ── disclaimer ───────────────────────────────────────────────────


class TestHonestyBanner(unittest.TestCase):
    def test_main_prints_disclaimer_to_stderr(self):
        from scripts.measure_entity_expansion import main

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, g, ix, eid = _build(tdp)
            err = io.StringIO()
            out = io.StringIO()
            with mock.patch("sys.stderr", err), \
                 mock.patch("sys.stdout", out):
                main([
                    "--index-db", str(tdp / "ix.db"),
                    "--episodes-db", str(tdp / "ep.db"),
                    "--graph-db", str(tdp / "g.db"),
                    "--query", "tell me about Maya Ananthan",
                    "--reference-time", "2026-04-30T12:00:00+00:00",
                ])
            # Disclaimer must mention behavior-change vs relevance,
            # and must point to diff_excerpt.
            err_text = err.getvalue()
            self.assertIn("not", err_text.lower())
            self.assertIn("relevant", err_text.lower())
            self.assertIn("diff_excerpt", err_text)


# ── JSON output shape ────────────────────────────────────────────


class TestJsonOutput(unittest.TestCase):
    def test_json_contains_disclaimer_and_results(self):
        from scripts.measure_entity_expansion import main

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, g, ix, _ = _build(tdp)
            out = io.StringIO()
            with mock.patch("sys.stdout", out):
                rc = main([
                    "--index-db", str(tdp / "ix.db"),
                    "--episodes-db", str(tdp / "ep.db"),
                    "--graph-db", str(tdp / "g.db"),
                    "--query", "tell me about Maya Ananthan",
                    "--json",
                    "--reference-time", "2026-04-30T12:00:00+00:00",
                ])
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertIn("disclaimer", payload)
            self.assertIn("relevant", payload["disclaimer"].lower())
            self.assertEqual(len(payload["results"]), 1)
            r = payload["results"][0]
            self.assertEqual(r["query"], "tell me about Maya Ananthan")
            self.assertIn("brief_diff_excerpt", r)


# ── safety ──────────────────────────────────────────────────────


class TestNoSubprocessNoNetwork(unittest.TestCase):
    def test_no_subprocess(self):
        from scripts.measure_entity_expansion import measure

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 socket, "socket",
                 side_effect=AssertionError("no socket"),
             ):
            ep, g, ix, _ = _build(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            measure(
                "tell me about Maya Ananthan",
                ix=ix, episode_store=ep, graph=g,
                reference_time=ref,
            )


if __name__ == "__main__":
    unittest.main()
