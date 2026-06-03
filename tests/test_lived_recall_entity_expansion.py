# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Optional entity-query expansion in lived recall (Step 5i).

Wires Step-5e entity index lookup into ``build_lived_recall_brief``
behind an env-var feature flag. Flag-off behaviour MUST be byte-
identical to pre-feature output. Flag-on behaviour adds an
``ENTITY EXPANSION`` section at the end of the brief, capped tightly,
fail-closed on any error.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


_FLAG_NAME = "MAEZ_ENTITY_EXPANSION"


# ── helpers ────────────────────────────────────────────────────────


def _build_stores(td: Path):
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph
    return (
        EpisodeStore(str(td / "ep.db")),
        RelationshipGraph(str(td / "g.db")),
    )


def _seed_episode_with_maya(ep, occurred_at: str = "2026-04-12T09:00:00+00:00"):
    return ep.add(
        title="Maya Ananthan started school",
        summary="we discussed Maya Ananthan starting at the new school",
        participants=["rohit"],
        source_memory_ids=["mem-1"],
        source_kind="conversation",
        occurred_at=occurred_at,
    )


def _seed_index_with_maya_mentions(eid: str):
    """In-memory entity index with Maya Ananthan + Anjali (ambiguous
    via 'Maya' alias) plus mentions across multiple sessions."""
    from core.memory.entity_index import EntityIndex

    ix = EntityIndex(":memory:")
    a = ix.upsert_entity(
        "Maya Ananthan", kind="person", aliases=["Maya"],
    )
    b = ix.upsert_entity(
        "Maya Anjali", kind="person", aliases=["Maya"],
    )
    # 'Anjali' is a unique alias for Maya Anjali only — used by the
    # top-3 cap test which needs unambiguous full-confidence hits.
    ix.add_alias(b, "Anjali")
    # Multiple sessions for both so the per-entity session cap test
    # has data to limit.
    for i, ts in enumerate([
        "2026-04-12T09:00:00+00:00",
        "2026-04-13T09:00:00+00:00",
        "2026-04-14T09:00:00+00:00",
    ]):
        ix.add_mention(
            entity_id=a, session_id=eid if i == 0 else f"ep-extra-{i}",
            source_id=eid if i == 0 else f"mem-extra-{i}",
            source_kind="episode",
            observed_at=ts, snippet="x", confidence=0.9,
        )
    return ix, a, b


# ── flag parsing ──────────────────────────────────────────────────


class TestFlagParsing(unittest.TestCase):
    def test_truthy_values_enable(self):
        from core.memory.lived_recall import _entity_expansion_enabled

        for v in ("1", "true", "TRUE", "True", "yes", "on", " on ", "Yes"):
            with mock.patch.dict(os.environ, {_FLAG_NAME: v}):
                self.assertTrue(
                    _entity_expansion_enabled(),
                    f"{v!r} should enable expansion",
                )

    def test_falsy_values_disable(self):
        from core.memory.lived_recall import _entity_expansion_enabled

        for v in ("", "0", "false", "no", "off", "maybe", "x"):
            with mock.patch.dict(os.environ, {_FLAG_NAME: v}):
                self.assertFalse(
                    _entity_expansion_enabled(),
                    f"{v!r} should not enable expansion",
                )

    def test_unset_disables(self):
        from core.memory.lived_recall import _entity_expansion_enabled

        env = dict(os.environ)
        env.pop(_FLAG_NAME, None)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(_entity_expansion_enabled())


# ── off-state: byte-identical output ─────────────────────────────


class TestFlagOffByteIdentical(unittest.TestCase):
    """Flag-off output must be the same as not passing ix at all,
    AND must never contain the section header tokens."""

    def test_no_ix_passed_no_expansion_tokens(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            eid = _seed_episode_with_maya(ep)
            ix, _, _ = _seed_index_with_maya_mentions(eid)
            self.addCleanup(ix.close)

            env = dict(os.environ)
            env.pop(_FLAG_NAME, None)
            with mock.patch.dict(os.environ, env, clear=True):
                without = build_lived_recall_brief(
                    "tell me about Maya",
                    episode_store=ep, graph=g,
                )
                with_ix = build_lived_recall_brief(
                    "tell me about Maya",
                    episode_store=ep, graph=g, ix=ix,
                )
            self.assertEqual(
                with_ix, without,
                "supplying ix with flag off must not change output",
            )
            for token in (
                "ENTITY EXPANSION",
                "=== ENTITY",
                "[conf",
                "Explanation:",
            ):
                self.assertNotIn(token, with_ix)
                self.assertNotIn(token, without)

    def test_flag_explicitly_off_no_expansion(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            eid = _seed_episode_with_maya(ep)
            ix, _, _ = _seed_index_with_maya_mentions(eid)
            self.addCleanup(ix.close)

            for v in ("0", "false", "", "no"):
                with mock.patch.dict(os.environ, {_FLAG_NAME: v}):
                    out = build_lived_recall_brief(
                        "Maya?", episode_store=ep, graph=g, ix=ix,
                    )
                self.assertNotIn("ENTITY EXPANSION", out)


# ── on-state: section appears with provenance ────────────────────


class TestFlagOnSectionRender(unittest.TestCase):
    def test_matching_entity_produces_expansion_section(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            eid = _seed_episode_with_maya(ep)
            ix, _, _ = _seed_index_with_maya_mentions(eid)
            self.addCleanup(ix.close)

            with mock.patch.dict(os.environ, {_FLAG_NAME: "1"}):
                out = build_lived_recall_brief(
                    "tell me about Maya Ananthan",
                    episode_store=ep, graph=g, ix=ix,
                )
            self.assertIn("=== ENTITY EXPANSION ===", out)
            self.assertIn("Maya Ananthan", out)
            # Confidence and at least one session id should appear.
            self.assertIn("[conf", out)
            self.assertIn("ep-", out)
            # Explanation is present.
            self.assertIn("Explanation:", out)

    def test_empty_index_produces_no_section(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            _seed_episode_with_maya(ep)
            empty_ix = EntityIndex(":memory:")
            self.addCleanup(empty_ix.close)
            with mock.patch.dict(os.environ, {_FLAG_NAME: "1"}):
                out = build_lived_recall_brief(
                    "tell me about Maya",
                    episode_store=ep, graph=g, ix=empty_ix,
                )
            self.assertNotIn("ENTITY EXPANSION", out)

    def test_ambiguous_alias_shows_split_confidence(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            eid = _seed_episode_with_maya(ep)
            ix, _, _ = _seed_index_with_maya_mentions(eid)
            self.addCleanup(ix.close)
            # Add a mention for the second Maya so it's not zero-mention.
            ix.add_mention(
                entity_id=ix.find_entities("Maya Anjali")[0].entity_id,
                session_id="ep-anjali",
                source_id="mem-anjali",
                source_kind="episode",
                observed_at="2026-04-15T09:00:00+00:00",
                snippet="x", confidence=0.9,
            )
            with mock.patch.dict(os.environ, {_FLAG_NAME: "1"}):
                out = build_lived_recall_brief(
                    "Maya?", episode_store=ep, graph=g, ix=ix,
                )
            # Both canonical names listed.
            self.assertIn("Maya Ananthan", out)
            self.assertIn("Maya Anjali", out)
            # Both at confidence 0.5 (ambiguous alias).
            self.assertIn("[conf 0.5", out)


# ── caps ──────────────────────────────────────────────────────────


class TestSectionCaps(unittest.TestCase):
    def test_top_3_entities_max(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            _seed_episode_with_maya(ep)
            ix = EntityIndex(":memory:")
            self.addCleanup(ix.close)
            # Five entities all aliased "X" — all at confidence 0.2.
            ents = []
            for i in range(5):
                eid_e = ix.upsert_entity(
                    f"Entity {chr(65 + i)}", kind="person",
                    aliases=["X"],
                )
                # Different mention counts so tie-break-by-count
                # selects a stable top-3.
                for j in range(i + 1):
                    ix.add_mention(
                        entity_id=eid_e,
                        session_id=f"ep-{i}-{j}",
                        source_id=f"mem-{i}-{j}",
                        source_kind="episode",
                        observed_at=(
                            f"2026-04-{10 + j:02d}T09:00:00+00:00"
                        ),
                        snippet="x", confidence=0.9,
                    )
                ents.append(eid_e)
            with mock.patch.dict(os.environ, {_FLAG_NAME: "1"}):
                out = build_lived_recall_brief(
                    "X", episode_store=ep, graph=g, ix=ix,
                )
            # Only 3 of the 5 canonical names should be present.
            present = sum(
                f"Entity {chr(65 + i)}" in out for i in range(5)
            )
            self.assertEqual(present, 3)

    def test_top_5_sessions_per_entity(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            _seed_episode_with_maya(ep)
            ix = EntityIndex(":memory:")
            self.addCleanup(ix.close)
            eid_e = ix.upsert_entity(
                "Solo Person", kind="person", aliases=["solo"],
            )
            for i in range(8):
                ix.add_mention(
                    entity_id=eid_e,
                    session_id=f"ep-{i:02d}",
                    source_id=f"mem-{i:02d}",
                    source_kind="episode",
                    observed_at=f"2026-04-{10 + i:02d}T09:00:00+00:00",
                    snippet="x", confidence=0.9,
                )
            with mock.patch.dict(os.environ, {_FLAG_NAME: "1"}):
                out = build_lived_recall_brief(
                    "Solo Person", episode_store=ep, graph=g, ix=ix,
                )
            # The Solo Person line should reference at most 5
            # session ids (ep-NN format). Count distinct ep- ids
            # in the line.
            for line in out.splitlines():
                if "Solo Person" in line and "[conf" in line:
                    ep_ids = [
                        tok for tok in line.replace(",", " ").split()
                        if tok.startswith("ep-")
                    ]
                    self.assertLessEqual(len(ep_ids), 5)
                    break
            else:
                self.fail("Solo Person line not found in output")

    def test_section_under_500_chars(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            _seed_episode_with_maya(ep)
            ix = EntityIndex(":memory:")
            self.addCleanup(ix.close)
            for i in range(3):
                eid_e = ix.upsert_entity(
                    f"VeryLongCanonicalNameNumber{i:02d}"
                    "ThatTakesUpManyCharactersToTest"
                    "TheSectionByteCap",
                    kind="person", aliases=["X"],
                )
                for j in range(5):
                    ix.add_mention(
                        entity_id=eid_e,
                        session_id=f"ep-{i}-{j:02d}-with-extra-padding",
                        source_id=f"mem-{i}-{j}",
                        source_kind="episode",
                        observed_at=(
                            f"2026-04-{10 + j:02d}T09:00:00+00:00"
                        ),
                        snippet="x", confidence=0.9,
                    )
            with mock.patch.dict(os.environ, {_FLAG_NAME: "1"}):
                out = build_lived_recall_brief(
                    "X", episode_store=ep, graph=g, ix=ix,
                )
            # Find the section span.
            self.assertIn("=== ENTITY EXPANSION ===", out)
            section_start = out.index("=== ENTITY EXPANSION ===")
            section = out[section_start:]
            self.assertLessEqual(len(section), 500)


# ── fail-closed ──────────────────────────────────────────────────


class TestFailClosed(unittest.TestCase):
    def test_entity_index_construction_failure_returns_unchanged_brief(self):
        """If the lazy default EntityIndex() raises, the brief
        composer must catch and return without an expansion
        section."""
        from core.memory import lived_recall

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            _seed_episode_with_maya(ep)

            # Reset module-cached index so the lazy path runs.
            lived_recall._cached_entity_ix = None

            with mock.patch.dict(os.environ, {_FLAG_NAME: "1"}), \
                 mock.patch(
                     "core.memory.entity_index.EntityIndex",
                     side_effect=RuntimeError("DB unavailable"),
                 ):
                out = lived_recall.build_lived_recall_brief(
                    "tell me about Maya", episode_store=ep, graph=g,
                )
            self.assertNotIn("ENTITY EXPANSION", out)

    def test_expand_query_failure_returns_unchanged_brief(self):
        from core.memory.entity_index import EntityIndex
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g = _build_stores(Path(td))
            _seed_episode_with_maya(ep)
            ix = EntityIndex(":memory:")
            self.addCleanup(ix.close)

            with mock.patch.dict(os.environ, {_FLAG_NAME: "1"}), \
                 mock.patch(
                     "core.memory.entity_index.expand_query",
                     side_effect=RuntimeError("schema corrupt"),
                 ):
                out = build_lived_recall_brief(
                    "tell me about Maya",
                    episode_store=ep, graph=g, ix=ix,
                )
            self.assertNotIn("ENTITY EXPANSION", out)


# ── safety ──────────────────────────────────────────────────────


class TestNoSubprocessOrNetwork(unittest.TestCase):
    def test_expansion_does_not_subprocess_or_network(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 socket, "socket",
                 side_effect=AssertionError("no socket"),
             ):
            ep, g = _build_stores(Path(td))
            eid = _seed_episode_with_maya(ep)
            ix, _, _ = _seed_index_with_maya_mentions(eid)
            self.addCleanup(ix.close)
            with mock.patch.dict(os.environ, {_FLAG_NAME: "1"}):
                build_lived_recall_brief(
                    "Maya", episode_store=ep, graph=g, ix=ix,
                )


if __name__ == "__main__":
    unittest.main()
