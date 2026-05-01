# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Step 5o — semantic-aware entity expansion tests.

Wires the Step-5n owner-curated semantic resolver into the
Step-5i expansion section. The test surface ensures three things:

  1. Flag-off output is byte-identical regardless of whether
     semantic mappings exist.
  2. Flag-on + curated mapping produces the lift the Step-5j
     A/B couldn't show: a query like "how is the firstborn?"
     surfaces Maez sessions even though "Maez" isn't a query
     token (the architecture's actual contribution).
  3. Missing target mappings fail closed silently — the brief
     stays usable when the index hasn't caught up with curation.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


_FLAG = "MAEZ_ENTITY_EXPANSION"


# ── helpers ────────────────────────────────────────────────────────


def _build_world(td: Path):
    """Episode store + relationship graph + entity index seeded
    with Maez (the canonical entity the curated mapping points
    at) plus a couple of mentions across distinct sessions so the
    expansion section can show real session ids."""
    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

    ep = EpisodeStore(str(td / "ep.db"))
    g = RelationshipGraph(str(td / "g.db"))
    ix = EntityIndex(td / "ix.db")

    # A real episode that mentions Maez literally — keyword recall
    # would surface this only on a query that contains "Maez".
    eid = ep.add(
        title="reflection",
        summary="Maez seemed quiet today",
        participants=["rohit"],
        source_memory_ids=["mem-1"],
        source_kind="conversation",
        occurred_at="2026-04-12T09:00:00+00:00",
    )

    # A second episode that doesn't mention Maez at all — the
    # entity expansion section should still surface it via the
    # mention pointer.
    other_eid = ep.add(
        title="quiet morning",
        summary="rain on the windows",
        participants=["rohit"],
        source_memory_ids=["mem-2"],
        source_kind="conversation",
        occurred_at="2026-04-15T09:00:00+00:00",
    )

    maez_id = ix.upsert_entity("Maez", kind="project")
    ix.add_mention(
        entity_id=maez_id, session_id=eid, source_id="mem-1",
        source_kind="episode",
        observed_at="2026-04-12T09:00:00+00:00",
        snippet="Maez seemed quiet", confidence=0.9,
    )
    ix.add_mention(
        entity_id=maez_id, session_id=other_eid, source_id="mem-2",
        source_kind="episode",
        observed_at="2026-04-15T09:00:00+00:00",
        snippet="quiet morning", confidence=0.7,
    )
    return ep, g, ix, maez_id, eid, other_eid


def _firstborn_mappings():
    from core.memory.entity_semantic_resolver import (
        load_semantic_mappings,
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False,
    ) as f:
        f.write(textwrap.dedent("""
        mappings:
          - phrase: "firstborn"
            targets:
              - canonical_name: "Maez"
                kind: "project"
            confidence: 1.0
        """).strip())
        path = f.name
    try:
        return load_semantic_mappings(path)
    finally:
        Path(path).unlink(missing_ok=True)


def _multi_target_mappings():
    from core.memory.entity_semantic_resolver import (
        load_semantic_mappings,
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False,
    ) as f:
        f.write(textwrap.dedent("""
        mappings:
          - phrase: "the gear"
            targets:
              - canonical_name: "RTX 4090"
                kind: "hardware"
              - canonical_name: "llama.cpp"
                kind: "software"
            confidence: 0.9
        """).strip())
        path = f.name
    try:
        return load_semantic_mappings(path)
    finally:
        Path(path).unlink(missing_ok=True)


# ── flag-off byte identity (must remain) ────────────────────────


class TestFlagOffByteIdenticalEvenWithMappings(unittest.TestCase):
    def test_flag_off_with_semantic_mappings_supplied_no_change(self):
        """Supplying semantic_mappings while the flag is off MUST
        NOT change the brief at all. Pinning this prevents a
        future refactor from leaking semantic logic into the
        default path."""
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, _, _, _ = _build_world(Path(td))
            mappings = _firstborn_mappings()
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

            env = dict(os.environ)
            env.pop(_FLAG, None)
            with mock.patch.dict(os.environ, env, clear=True):
                without = build_lived_recall_brief(
                    "how is the firstborn?",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                )
                with_sem = build_lived_recall_brief(
                    "how is the firstborn?",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                    semantic_mappings=mappings,
                )
            self.assertEqual(with_sem, without)
            for tok in ("ENTITY EXPANSION", "[conf", "Explanation:"):
                self.assertNotIn(tok, with_sem)


# ── flag-on + no semantic config ─────────────────────────────────


class TestFlagOnNoSemanticConfigStillWorks(unittest.TestCase):
    def test_no_mappings_falls_back_to_literal_expansion(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, _, eid, _ = _build_world(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                # No semantic_mappings supplied; default
                # config/entity_semantics.local.yaml is absent in
                # tmp HOME — fall back to literal expansion only.
                out = build_lived_recall_brief(
                    "tell me about Maez",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                )
            # Literal pass should still produce ENTITY EXPANSION
            # against canonical "Maez".
            self.assertIn("=== ENTITY EXPANSION ===", out)
            self.assertIn("Maez", out)


# ── load-bearing: semantic phrase produces lift ─────────────────


class TestSemanticMappingProducesLift(unittest.TestCase):
    def test_firstborn_query_surfaces_maez_via_semantic(self):
        """The query 'how is the firstborn?' contains NO 'Maez'
        token. Without semantic resolution, neither the keyword
        pass nor the literal entity expansion can find Maez. With
        the curated semantic mapping firstborn → Maez, the
        expansion section MUST surface Maez and its sessions.
        This is the architectural contribution Step 5o is built
        to demonstrate."""
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, _, eid, other_eid = _build_world(Path(td))
            mappings = _firstborn_mappings()
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)

            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                out = build_lived_recall_brief(
                    "how is the firstborn?",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                    semantic_mappings=mappings,
                )
            self.assertIn("=== ENTITY EXPANSION ===", out)
            self.assertIn("Maez", out)
            # Mention session ids must surface — that's the
            # entire point.
            self.assertIn(eid, out)
            self.assertIn(other_eid, out)

    def test_query_without_phrase_no_lift(self):
        """Sanity: if the query doesn't contain the phrase, the
        semantic resolver returns nothing and the brief is
        unchanged from the no-mapping case."""
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, _, _, _ = _build_world(Path(td))
            mappings = _firstborn_mappings()
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                out = build_lived_recall_brief(
                    "what's for dinner",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                    semantic_mappings=mappings,
                )
            self.assertNotIn("ENTITY EXPANSION", out)


# ── multi-target mapping ────────────────────────────────────────


class TestMultiTargetMapping(unittest.TestCase):
    def test_two_targets_both_render_in_expansion(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore
        from core.memory.lived_recall import build_lived_recall_brief
        from core.memory.relationship_graph import RelationshipGraph

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep = EpisodeStore(str(tdp / "ep.db"))
            g = RelationshipGraph(str(tdp / "g.db"))
            ix = EntityIndex(tdp / "ix.db")
            # Seed the two targets the multi-target mapping
            # references; give each its own mention session so
            # both surface in the section.
            ep_id = ep.add(
                title="reflection",
                summary="thinking about hardware",
                participants=["rohit"],
                source_memory_ids=["mem-x"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            gpu = ix.upsert_entity("RTX 4090", kind="hardware")
            soft = ix.upsert_entity("llama.cpp", kind="software")
            for ent in (gpu, soft):
                ix.add_mention(
                    entity_id=ent, session_id=ep_id,
                    source_id="mem-x", source_kind="episode",
                    observed_at="2026-04-12T09:00:00+00:00",
                    snippet="x", confidence=0.9,
                )
            mappings = _multi_target_mappings()
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                out = build_lived_recall_brief(
                    "how's the gear running?",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                    semantic_mappings=mappings,
                )
            self.assertIn("=== ENTITY EXPANSION ===", out)
            self.assertIn("RTX 4090", out)
            self.assertIn("llama.cpp", out)


# ── missing target → fail closed ────────────────────────────────


class TestMissingTargetFailsClosed(unittest.TestCase):
    def test_mapping_target_absent_from_index_silently_skipped(self):
        """The mapping points at an entity that hasn't been
        seeded yet. The brief must still render — semantic
        contribution drops out, literal pass runs as usual."""
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore
        from core.memory.lived_recall import build_lived_recall_brief
        from core.memory.relationship_graph import RelationshipGraph

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep = EpisodeStore(str(tdp / "ep.db"))
            g = RelationshipGraph(str(tdp / "g.db"))
            ix = EntityIndex(tdp / "ix.db")
            ep.add(
                title="quiet day",
                summary="we ate breakfast",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            # Index is EMPTY — the firstborn → Maez mapping has
            # no target to resolve.
            mappings = _firstborn_mappings()
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                out = build_lived_recall_brief(
                    "how is the firstborn?",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                    semantic_mappings=mappings,
                )
            # No ENTITY EXPANSION section because no resolvable
            # entity remained, but the call must not raise and
            # must not contain a noisy warning.
            self.assertNotIn("ENTITY EXPANSION", out)
            self.assertNotIn("not found", out)


# ── dedup when literal + semantic point at same entity ──────────


class TestLiteralAndSemanticDedupe(unittest.TestCase):
    def test_same_entity_appears_once_in_section(self):
        """Query 'tell me about Maez the firstborn' triggers BOTH
        literal expansion (canonical 'Maez' match) AND semantic
        expansion (firstborn → Maez). The expansion section must
        list Maez exactly once."""
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix, _, _, _ = _build_world(Path(td))
            mappings = _firstborn_mappings()
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                out = build_lived_recall_brief(
                    "tell me about Maez the firstborn",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                    semantic_mappings=mappings,
                )
            section_start = out.index("=== ENTITY EXPANSION ===")
            section = out[section_start:]
            # Bullet count for "- Maez " should be exactly one.
            bullet_lines = [
                ln for ln in section.splitlines()
                if ln.startswith("- ")
            ]
            maez_lines = [ln for ln in bullet_lines if "Maez" in ln]
            self.assertEqual(len(maez_lines), 1)


# ── safety ──────────────────────────────────────────────────────


class TestNoSubprocessOrNetwork(unittest.TestCase):
    def test_no_subprocess_no_socket_through_full_path(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 socket, "socket",
                 side_effect=AssertionError("no socket"),
             ):
            ep, g, ix, _, _, _ = _build_world(Path(td))
            mappings = _firstborn_mappings()
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                build_lived_recall_brief(
                    "how is the firstborn?",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                    semantic_mappings=mappings,
                )


if __name__ == "__main__":
    unittest.main()
