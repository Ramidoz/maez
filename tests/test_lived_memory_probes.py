# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Lived-memory probe-suite tests (ADR 0019 Phase 8).

The probe suite is the gate that decides whether the lived-memory
layer is ready for Phase 6 (live integration). Each probe asks a
question that targets a specific Track A weakness — correction,
relationship, open-loop, temporal recall, etc. — and checks that
the planner produces an evidence-backed answer, not a fabrication.

These tests cover the suite *infrastructure*: probe definitions,
scoring rules, report shape. The actual probe run against live
data lives in scripts/validate/lived_memory_probes.py and is
exercised manually (or via cron) against the populated SQLite
stores. The unit tests use fixture data so the suite never
depends on a populated lived-memory database.

Tests cover:

- The 7 probe types from the plan are defined.
- Every probe carries a query + a check function.
- Probe report shape: per-probe pass/fail + overall score.
- Empty stores → all probes fail with no fabrication.
- Seeded data → relevant probes pass, irrelevant fail.
- Universal invariant: NO probe brief contains 'currently' /
  'right now' / 'is happening' (the live-state guard).
- Universal invariant: every passing probe has evidence in its
  brief.
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


def _seed_correction(store, graph):
    """Seeds the data the 'correction' probe expects to find."""
    ep_id = store.add(
        title="INFRASTRUCTURE GROUND-TRUTH (correction):",
        summary=(
            "A prior reasoning loop invented a systemd service called "
            "llama-server-vision and wrote confidently about port 8081 "
            "and mmproj. None of that exists. Vision is retired."
        ),
        participants=["Maez"],
        source_memory_ids=["core-vision-real"],
        source_kind="core_memory",
        emotional_tone="corrective",
        importance=4,
    )
    subj = graph.upsert_node(label="Maez", kind="being")
    obj = graph.upsert_node(label="llama-server-vision narrative", kind="concept")
    graph.add_edge(
        subject_id=subj,
        relation="corrected",
        object_id=obj,
        source_episode_ids=[ep_id],
        source_memory_ids=["core-vision-real"],
        confidence=0.9,
    )
    return ep_id


def _seed_brain_model_change(store, graph):
    """Seeds the 'temporal — what changed about your brain model'
    probe."""
    ep_id = store.add(
        title="INFRASTRUCTURE GROUND-TRUTH (correction):",
        summary=(
            "Earlier raw-memory entries refer to 'gemma4:26b' as Maez's "
            "brain. The current brain is Qwen3.6-27B-UD-Q4_K_XL via "
            "llama.cpp on RTX 4090."
        ),
        participants=["Maez"],
        source_memory_ids=["core-brain-real"],
        source_kind="core_memory",
        emotional_tone="corrective",
        importance=4,
    )
    subj = graph.upsert_node(label="Maez", kind="being")
    obj = graph.upsert_node(label="gemma narrative", kind="concept")
    graph.add_edge(
        subject_id=subj,
        relation="corrected",
        object_id=obj,
        source_episode_ids=[ep_id],
        source_memory_ids=["core-brain-real"],
        confidence=0.9,
    )
    return ep_id


def _seed_open_loop(store, graph):
    # Summary deliberately overlaps with the open_loop probe query
    # ("What have we not finished?") so the keyword-overlap planner
    # finds the episode. Real-data open loops will need stemming or
    # intent detection to match this query naturally; that's v2.
    ep_id = store.add(
        title="Open loop: not finished — dream-state soul-write bypass",
        summary=(
            "Owner deferred the dream-state soul-write bypass; we "
            "have not finished this work. Need to revisit when "
            "Track A graduates."
        ),
        participants=["Rohit", "Maez"],
        source_memory_ids=["raw-loop-1"],
        source_kind="raw_observation",
        open_loop=(
            "We have not finished the dream-state soul-write bypass "
            "and need to revisit when Track A graduates."
        ),
    )
    subj = graph.upsert_node(label="Maez", kind="being")
    obj = graph.upsert_node(label="dream-state soul-write bypass", kind="concept")
    graph.add_edge(
        subject_id=subj,
        relation="open_loop_about",
        object_id=obj,
        source_episode_ids=[ep_id],
        source_memory_ids=["raw-loop-1"],
        confidence=0.7,
    )
    return ep_id


def _seed_relationship(store, graph):
    # Summary mentions Rohit + Maez + care so the relationship probe's
    # query ("What do you know I care about in Maez?") shares tokens.
    ep_id = store.add(
        title="Owner stated preference: truthful continuity in Maez",
        summary=(
            "Rohit cares about truthful continuity in Maez more than "
            "impressive but fabricated claims. Anchor for fabrication-"
            "prevention design."
        ),
        participants=["Rohit", "Maez"],
        source_memory_ids=["core-pref-1"],
        source_kind="core_memory",
    )
    subj = graph.upsert_node(label="Rohit", kind="person")
    obj = graph.upsert_node(label="truthful continuity", kind="concept")
    graph.add_edge(
        subject_id=subj,
        relation="cares_about",
        object_id=obj,
        source_episode_ids=[ep_id],
        source_memory_ids=["core-pref-1"],
        confidence=0.9,
    )
    return ep_id


# ── infrastructure: probe definitions ────────────────────────────────


class ProbeDefinitionsExist(unittest.TestCase):
    """The plan calls for 7 probe types; the suite must define all
    7 with stable identifiers."""

    def test_seven_probes_defined(self):
        from scripts.validate.lived_memory_probes import PROBES

        names = {p.name for p in PROBES}
        expected = {
            "past_to_present",
            "open_loop",
            "correction",
            "relationship",
            "temporal",
            "surprise",
            "predict_as_mind",
        }
        self.assertEqual(names, expected)

    def test_each_probe_has_query_and_checker(self):
        from scripts.validate.lived_memory_probes import PROBES

        for p in PROBES:
            self.assertTrue(p.query, f"{p.name}: missing query")
            self.assertTrue(callable(p.check), f"{p.name}: missing check")


# ── infrastructure: report shape ─────────────────────────────────────


class ReportShape(unittest.TestCase):
    def test_report_is_per_probe_with_overall_score(self):
        from scripts.validate.lived_memory_probes import run_probes

        store, graph, cleanup = _stores()
        try:
            report = run_probes(episode_store=store, graph=graph)
            self.assertEqual(len(report.results), 7)
            for r in report.results:
                self.assertTrue(r.name)
                self.assertIsInstance(r.passed, bool)
                self.assertIsInstance(r.brief, str)
                self.assertTrue(r.detail)  # always carries a detail
            # Overall score is a float in [0.0, 1.0].
            self.assertGreaterEqual(report.score, 0.0)
            self.assertLessEqual(report.score, 1.0)
        finally:
            cleanup()


# ── empty-store baseline ─────────────────────────────────────────────


class EmptyStoresAllProbesFailWithoutFabrication(unittest.TestCase):
    """With no data in the stores, every probe must fail (because
    there's nothing to cite) but no probe must produce a fabricated
    or hallucinated brief — empty stores → empty briefs."""

    def test_all_probes_fail_with_empty_briefs(self):
        from scripts.validate.lived_memory_probes import run_probes

        store, graph, cleanup = _stores()
        try:
            report = run_probes(episode_store=store, graph=graph)
            self.assertEqual(report.score, 0.0)
            for r in report.results:
                self.assertFalse(r.passed)
                # Brief must be empty (no fabrication).
                self.assertEqual(r.brief, "")
        finally:
            cleanup()


# ── seeded data: targeted passes ─────────────────────────────────────


class SeededCorrectionPasses(unittest.TestCase):
    def test_correction_probe_passes_when_correction_present(self):
        from scripts.validate.lived_memory_probes import run_probes

        store, graph, cleanup = _stores()
        try:
            _seed_correction(store, graph)
            report = run_probes(episode_store=store, graph=graph)
            by_name = {r.name: r for r in report.results}
            self.assertTrue(
                by_name["correction"].passed,
                f"correction probe failed: {by_name['correction'].detail}",
            )
            # Evidence must appear in the brief.
            self.assertIn("core-vision-real", by_name["correction"].brief)
        finally:
            cleanup()


class SeededOpenLoopPasses(unittest.TestCase):
    def test_open_loop_probe_passes_when_open_loop_present(self):
        from scripts.validate.lived_memory_probes import run_probes

        store, graph, cleanup = _stores()
        try:
            _seed_open_loop(store, graph)
            report = run_probes(episode_store=store, graph=graph)
            by_name = {r.name: r for r in report.results}
            self.assertTrue(
                by_name["open_loop"].passed,
                f"open_loop probe failed: {by_name['open_loop'].detail}",
            )
        finally:
            cleanup()


class SeededRelationshipPasses(unittest.TestCase):
    def test_relationship_probe_passes_when_cares_about_edge_present(self):
        from scripts.validate.lived_memory_probes import run_probes

        store, graph, cleanup = _stores()
        try:
            _seed_relationship(store, graph)
            report = run_probes(episode_store=store, graph=graph)
            by_name = {r.name: r for r in report.results}
            self.assertTrue(
                by_name["relationship"].passed,
                f"relationship probe failed: {by_name['relationship'].detail}",
            )
            self.assertIn("Rohit", by_name["relationship"].brief)
        finally:
            cleanup()


class SeededTemporalPasses(unittest.TestCase):
    def test_temporal_probe_passes_when_brain_model_change_present(self):
        from scripts.validate.lived_memory_probes import run_probes

        store, graph, cleanup = _stores()
        try:
            _seed_brain_model_change(store, graph)
            report = run_probes(episode_store=store, graph=graph)
            by_name = {r.name: r for r in report.results}
            self.assertTrue(
                by_name["temporal"].passed,
                f"temporal probe failed: {by_name['temporal'].detail}",
            )
        finally:
            cleanup()


# ── universal invariants ─────────────────────────────────────────────


class NoProbeBriefAssertsLiveState(unittest.TestCase):
    """Across every probe and every brief the suite produces, the
    forbidden present-tense words must never appear. This is the
    structural guard that prevents the lived-memory layer from
    masquerading as live perception."""

    def test_no_brief_contains_currently_or_right_now(self):
        from scripts.validate.lived_memory_probes import run_probes

        store, graph, cleanup = _stores()
        try:
            # Seed all four fixtures so every probe has data to chew.
            _seed_correction(store, graph)
            _seed_brain_model_change(store, graph)
            _seed_open_loop(store, graph)
            _seed_relationship(store, graph)
            report = run_probes(episode_store=store, graph=graph)
            for r in report.results:
                if not r.brief:
                    continue
                lower = r.brief.lower()
                for forbidden in (
                    "currently",
                    "right now",
                    "is happening",
                ):
                    self.assertNotIn(
                        forbidden,
                        lower,
                        f"probe {r.name!r} brief contained {forbidden!r}",
                    )
        finally:
            cleanup()


class EveryPassingProbeHasEvidence(unittest.TestCase):
    """A probe that passes must have evidence in its brief —
    otherwise the pass is meaningless."""

    def test_passing_probe_brief_contains_evidence_marker(self):
        from scripts.validate.lived_memory_probes import run_probes

        store, graph, cleanup = _stores()
        try:
            _seed_correction(store, graph)
            _seed_brain_model_change(store, graph)
            _seed_open_loop(store, graph)
            _seed_relationship(store, graph)
            report = run_probes(episode_store=store, graph=graph)
            for r in report.results:
                if not r.passed:
                    continue
                # Each passing brief should include either an episode
                # ID (ep-...) or a Chroma-style memory ID.
                has_evidence = "ep-" in r.brief or "core-" in r.brief or "raw-" in r.brief
                self.assertTrue(
                    has_evidence,
                    f"passing probe {r.name!r} has no evidence in brief: {r.brief!r}",
                )
        finally:
            cleanup()


if __name__ == "__main__":
    unittest.main()
