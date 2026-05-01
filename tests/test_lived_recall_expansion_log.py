# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Observability log for entity expansion (Step 5q).

Tonight's journal showed zero ``ENTITY EXPANSION`` evidence even
though the flag was on and the maez-web replay confirmed expansion
WOULD fire on at least one of the messages. Without a log line the
substrate is invisible in production: we cannot tell whether good
chat answers came from expansion or from keyword recall.

This slice adds a single structured log line — ``entity_expansion
fired ...`` — emitted at INFO level whenever the expansion path
produces a non-empty section. The log carries enough metadata to
audit live behaviour by grepping the journal:

  • n_literal_entities  : matches from expand_query
  • n_semantic_entities : matches from the semantic resolver
  • n_unique_entities   : post-dedupe entity count rendered
  • entity_canonicals   : sorted list of canonical names
  • semantic_phrases    : list of phrases (empty when no semantic)
  • query_excerpt       : first 60 chars of the query
"""

from __future__ import annotations

import logging
import os
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
_LOGGER = "core.memory.lived_recall"


def _build_world(td: Path):
    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

    ep = EpisodeStore(str(td / "ep.db"))
    g = RelationshipGraph(str(td / "g.db"))
    ix = EntityIndex(td / "ix.db")
    eid = ep.add(
        title="reflection",
        summary="Maez seemed quiet today",
        participants=["rohit"],
        source_memory_ids=["mem-1"],
        source_kind="conversation",
        occurred_at="2026-04-12T09:00:00+00:00",
    )
    maez_id = ix.upsert_entity("Maez", kind="project")
    ix.add_mention(
        entity_id=maez_id, session_id=eid, source_id="mem-1",
        source_kind="episode",
        observed_at="2026-04-12T09:00:00+00:00",
        snippet="Maez seemed quiet", confidence=0.9,
    )
    ix.add_mention(
        entity_id=maez_id, session_id="ep-other",
        source_id="mem-2", source_kind="episode",
        observed_at="2026-04-15T09:00:00+00:00",
        snippet="x", confidence=0.7,
    )
    return ep, g, ix


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


class TestLogFiresOnExpansion(unittest.TestCase):
    def test_literal_match_emits_structured_log(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix = _build_world(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}), \
                 self.assertLogs(_LOGGER, level=logging.INFO) as cm:
                build_lived_recall_brief(
                    "tell me about Maez",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                )
            joined = " ".join(cm.output)
            self.assertIn("entity_expansion fired", joined)
            self.assertIn("n_literal_entities=1", joined)
            self.assertIn("n_semantic_entities=0", joined)
            self.assertIn("n_unique_entities=1", joined)
            self.assertIn("Maez", joined)

    def test_semantic_match_emits_structured_log_with_phrase(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix = _build_world(Path(td))
            mappings = _firstborn_mappings()
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}), \
                 self.assertLogs(_LOGGER, level=logging.INFO) as cm:
                build_lived_recall_brief(
                    "how is the firstborn?",
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                    semantic_mappings=mappings,
                )
            joined = " ".join(cm.output)
            self.assertIn("entity_expansion fired", joined)
            self.assertIn("n_semantic_entities=1", joined)
            self.assertIn("firstborn", joined)
            self.assertIn("Maez", joined)

    def test_no_log_when_expansion_disabled(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix = _build_world(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            env = dict(os.environ)
            env.pop(_FLAG, None)
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertNoLogs(_LOGGER, level=logging.INFO):
                    build_lived_recall_brief(
                        "tell me about Maez",
                        episode_store=ep, graph=g,
                        reference_time=ref, ix=ix,
                    )

    def test_no_log_when_no_matches(self):
        from core.memory.lived_recall import build_lived_recall_brief
        from core.memory.entity_index import EntityIndex
        from core.memory.episodes import EpisodeStore
        from core.memory.relationship_graph import RelationshipGraph

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep = EpisodeStore(str(tdp / "ep.db"))
            g = RelationshipGraph(str(tdp / "g.db"))
            ix = EntityIndex(tdp / "ix.db")  # empty index
            ep.add(
                title="quiet",
                summary="we cooked",
                participants=["rohit"],
                source_memory_ids=["mem-1"],
                source_kind="conversation",
                occurred_at="2026-04-12T09:00:00+00:00",
            )
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            with mock.patch.dict(os.environ, {_FLAG: "1"}):
                with self.assertNoLogs(_LOGGER, level=logging.INFO):
                    build_lived_recall_brief(
                        "tell me about something",
                        episode_store=ep, graph=g,
                        reference_time=ref, ix=ix,
                    )

    def test_query_excerpt_capped(self):
        from core.memory.lived_recall import build_lived_recall_brief

        with tempfile.TemporaryDirectory() as td:
            ep, g, ix = _build_world(Path(td))
            ref = datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
            long_query = (
                "tell me about Maez but please ramble for a long "
                "time about every conceivable detail because I want "
                "to test the query excerpt cap"
            )
            with mock.patch.dict(os.environ, {_FLAG: "1"}), \
                 self.assertLogs(_LOGGER, level=logging.INFO) as cm:
                build_lived_recall_brief(
                    long_query,
                    episode_store=ep, graph=g,
                    reference_time=ref, ix=ix,
                )
            joined = " ".join(cm.output)
            # query_excerpt should be capped (truncated marker).
            import re as _re
            m = _re.search(r"query_excerpt='([^']*)'", joined)
            self.assertIsNotNone(m, f"no query_excerpt token in: {joined}")
            excerpt = m.group(1)
            self.assertLessEqual(len(excerpt), 64)
            # Should still START with the query head — verifies it's
            # the right query.
            self.assertTrue(long_query.startswith(excerpt[:40]))


if __name__ == "__main__":
    unittest.main()
