# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Tests for the semantic-mapping suggester + auditor (Step 5p).

Two friction surfaces from Step 5o went unsolved by Step 5l:

  1. Drafting NEW mappings: the operator has to grep
     ``memory/entity_index.db`` to find each entity's LLM-assigned
     ``kind`` before writing the mapping. The suggester prefills
     it.
  2. Validating EXISTING mappings: when the operator writes
     ``kind: hardware`` but the index records ``kind: concept``,
     the resolver silently warns and skips. The auditor surfaces
     the mismatch as a recognizable issue rather than letting it
     hide.
"""

from __future__ import annotations

import io
import socket
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import yaml

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── helpers ────────────────────────────────────────────────────────


def _seed_ix_with_mentions(td: Path):
    """Seed an EntityIndex with entities at varying mention counts /
    distinct-session counts so the suggester's top-N + min-sessions
    filters have something to bite on."""
    from core.memory.entity_index import EntityIndex

    ix = EntityIndex(td / "ix.db")
    # Maez: 11 mentions, 11 sessions (top recurring)
    maez = ix.upsert_entity("Maez", kind="project")
    for i in range(11):
        ix.add_mention(
            entity_id=maez, session_id=f"ep-maez-{i}",
            source_id=f"mem-maez-{i}", source_kind="episode",
            observed_at=f"2026-04-{10 + i:02d}T09:00:00+00:00",
            snippet="x", confidence=0.9,
        )
    # RTX 4090: 2 mentions, 2 sessions (cross-session evidence)
    rtx = ix.upsert_entity("RTX 4090", kind="concept")
    for i in range(2):
        ix.add_mention(
            entity_id=rtx, session_id=f"ep-rtx-{i}",
            source_id=f"mem-rtx-{i}", source_kind="episode",
            observed_at=f"2026-04-{10 + i:02d}T09:00:00+00:00",
            snippet="x", confidence=0.9,
        )
    # Track A: 6 mentions, 6 sessions
    track = ix.upsert_entity("Track A", kind="project")
    for i in range(6):
        ix.add_mention(
            entity_id=track, session_id=f"ep-track-{i}",
            source_id=f"mem-track-{i}", source_kind="episode",
            observed_at=f"2026-04-{10 + i:02d}T09:00:00+00:00",
            snippet="x", confidence=0.9,
        )
    # Singleton: 1 mention, 1 session — should be filtered out
    # by the cross-session rule unless min_sessions=1.
    solo = ix.upsert_entity("Solo Reference", kind="unknown")
    ix.add_mention(
        entity_id=solo, session_id="ep-solo",
        source_id="mem-solo", source_kind="episode",
        observed_at="2026-04-15T09:00:00+00:00",
        snippet="x", confidence=0.5,
    )
    # Orphan entity: no mentions — should never surface.
    ix.upsert_entity("Orphan", kind="concept")
    return ix


# ── suggester ────────────────────────────────────────────────────


class TestSuggestSemanticDrafts(unittest.TestCase):
    def test_drafts_use_ix_assigned_kind(self):
        """The whole point of 5p: the operator should not have to
        grep the index for the LLM-assigned kind. Each surfaced
        draft carries the kind exactly as recorded in the index."""
        from core.memory.entity_semantic_suggester import (
            suggest_semantic_drafts,
        )

        with tempfile.TemporaryDirectory() as td:
            ix = _seed_ix_with_mentions(Path(td))
            drafts = suggest_semantic_drafts(ix=ix, top_n=10)
            by_name = {d.canonical_name: d for d in drafts}
            self.assertEqual(by_name["Maez"].kind, "project")
            self.assertEqual(by_name["RTX 4090"].kind, "concept")
            self.assertEqual(by_name["Track A"].kind, "project")

    def test_default_filter_excludes_singletons(self):
        from core.memory.entity_semantic_suggester import (
            suggest_semantic_drafts,
        )

        with tempfile.TemporaryDirectory() as td:
            ix = _seed_ix_with_mentions(Path(td))
            drafts = suggest_semantic_drafts(ix=ix)  # min_sessions=2 default
            names = {d.canonical_name for d in drafts}
            self.assertNotIn("Solo Reference", names)
            self.assertNotIn("Orphan", names)

    def test_min_sessions_one_includes_singletons(self):
        from core.memory.entity_semantic_suggester import (
            suggest_semantic_drafts,
        )

        with tempfile.TemporaryDirectory() as td:
            ix = _seed_ix_with_mentions(Path(td))
            drafts = suggest_semantic_drafts(ix=ix, min_sessions=1)
            names = {d.canonical_name for d in drafts}
            self.assertIn("Solo Reference", names)
            # Orphan still excluded (zero mentions).
            self.assertNotIn("Orphan", names)

    def test_top_n_caps_results(self):
        from core.memory.entity_semantic_suggester import (
            suggest_semantic_drafts,
        )

        with tempfile.TemporaryDirectory() as td:
            ix = _seed_ix_with_mentions(Path(td))
            drafts = suggest_semantic_drafts(ix=ix, top_n=2)
            self.assertEqual(len(drafts), 2)
            # Ordered by mention count DESC: Maez (11) > Track A (6).
            self.assertEqual(drafts[0].canonical_name, "Maez")
            self.assertEqual(drafts[1].canonical_name, "Track A")

    def test_drafts_carry_evidence_counts(self):
        from core.memory.entity_semantic_suggester import (
            suggest_semantic_drafts,
        )

        with tempfile.TemporaryDirectory() as td:
            ix = _seed_ix_with_mentions(Path(td))
            drafts = suggest_semantic_drafts(ix=ix, top_n=10)
            maez = next(d for d in drafts if d.canonical_name == "Maez")
            self.assertEqual(maez.mention_count, 11)
            self.assertEqual(maez.distinct_sessions, 11)


# ── YAML output round-trips through resolver ────────────────────


class TestYamlRoundTrip(unittest.TestCase):
    def test_emitted_yaml_validates_with_resolver_loader(self):
        """The suggester's YAML output is a draft — phrase fields
        are placeholders meant for the operator to edit. Even with
        placeholder phrases, the YAML must round-trip through
        load_semantic_mappings without raising; otherwise the
        operator can't sanity-check the file before editing."""
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings,
        )
        from core.memory.entity_semantic_suggester import (
            format_yaml, suggest_semantic_drafts,
        )

        with tempfile.TemporaryDirectory() as td:
            ix = _seed_ix_with_mentions(Path(td))
            drafts = suggest_semantic_drafts(ix=ix, top_n=10)
            yaml_text = format_yaml(drafts)

            # Parse as YAML.
            doc = yaml.safe_load(yaml_text)
            self.assertIn("mappings", doc)
            self.assertGreater(len(doc["mappings"]), 0)

            # Round-trip through the resolver loader.
            f = Path(td) / "out.yaml"
            f.write_text(yaml_text)
            mappings = load_semantic_mappings(f)
            self.assertEqual(len(mappings), len(drafts))
            for m in mappings:
                self.assertEqual(len(m.targets), 1)
                self.assertIn("canonical_name", m.targets[0])
                self.assertIn("kind", m.targets[0])

    def test_yaml_includes_evidence_counts_as_comments(self):
        from core.memory.entity_semantic_suggester import (
            format_yaml, suggest_semantic_drafts,
        )

        with tempfile.TemporaryDirectory() as td:
            ix = _seed_ix_with_mentions(Path(td))
            drafts = suggest_semantic_drafts(ix=ix, top_n=10)
            yaml_text = format_yaml(drafts)
            # Mention counts surface in comments / notes for operator
            # review without polluting the loadable schema.
            self.assertIn("11", yaml_text)  # Maez count
            self.assertIn("Maez", yaml_text)


# ── auditor ──────────────────────────────────────────────────────


class TestAuditSemanticMappings(unittest.TestCase):
    def _audit_with_yaml(self, td: Path, body: str):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings,
        )
        from core.memory.entity_semantic_suggester import (
            audit_semantic_mappings,
        )

        ix = _seed_ix_with_mentions(td)
        path = td / "sem.yaml"
        path.write_text(body)
        mappings = load_semantic_mappings(path)
        return audit_semantic_mappings(mappings=mappings, ix=ix)

    def test_kind_mismatch_reported(self):
        body = textwrap.dedent("""
        mappings:
          - phrase: "the body"
            targets:
              - canonical_name: "RTX 4090"
                kind: "hardware"  # wrong — index has 'concept'
            confidence: 0.9
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            issues = self._audit_with_yaml(Path(td), body)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].code, "kind_mismatch")
            joined = issues[0].message.lower()
            self.assertIn("rtx 4090", joined)
            self.assertIn("hardware", joined)
            self.assertIn("concept", joined)
            # Auditor surfaces the SUGGESTED kind so the operator
            # can fix in seconds.
            self.assertEqual(issues[0].suggested_kind, "concept")

    def test_missing_entity_reported(self):
        body = textwrap.dedent("""
        mappings:
          - phrase: "the unicorn"
            targets:
              - canonical_name: "Sparkle"
                kind: "person"
            confidence: 1.0
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            issues = self._audit_with_yaml(Path(td), body)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].code, "missing_entity")
            self.assertIn("sparkle", issues[0].message.lower())

    def test_clean_mapping_no_issues(self):
        body = textwrap.dedent("""
        mappings:
          - phrase: "firstborn"
            targets:
              - canonical_name: "Maez"
                kind: "project"
            confidence: 1.0
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            issues = self._audit_with_yaml(Path(td), body)
            self.assertEqual(issues, [])

    def test_partial_target_match_reports_only_missing(self):
        """A multi-target mapping where one target resolves and
        one doesn't should yield exactly one issue for the bad
        target."""
        body = textwrap.dedent("""
        mappings:
          - phrase: "the body"
            targets:
              - canonical_name: "RTX 4090"
                kind: "concept"  # correct
              - canonical_name: "llama.cpp"
                kind: "project"  # not in this fixture index
            confidence: 0.9
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            issues = self._audit_with_yaml(Path(td), body)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].code, "missing_entity")
            self.assertIn("llama.cpp", issues[0].message.lower())


# ── CLI ─────────────────────────────────────────────────────────


class TestCli(unittest.TestCase):
    def test_default_suggest_mode_prints_yaml_no_writes(self):
        from core.memory.entity_semantic_suggester import main

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix_path = tdp / "ix.db"
            _seed_ix_with_mentions(tdp)
            local = tdp / "config" / "entity_semantics.local.yaml"
            self.assertFalse(local.exists())

            out = io.StringIO()
            err = io.StringIO()
            with mock.patch("sys.stdout", out), \
                 mock.patch("sys.stderr", err):
                rc = main(["--index-db", str(ix_path)])
            self.assertEqual(rc, 0)
            self.assertIn("mappings:", out.getvalue())
            self.assertIn("Maez", out.getvalue())
            self.assertFalse(local.exists())

    def test_audit_mode_emits_findings_to_stderr_returns_2(self):
        from core.memory.entity_semantic_suggester import main

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix_path = tdp / "ix.db"
            _seed_ix_with_mentions(tdp)
            sem_path = tdp / "sem.yaml"
            sem_path.write_text(textwrap.dedent("""
            mappings:
              - phrase: "the body"
                targets:
                  - canonical_name: "RTX 4090"
                    kind: "hardware"
                confidence: 0.9
            """).strip())
            out = io.StringIO()
            err = io.StringIO()
            with mock.patch("sys.stdout", out), \
                 mock.patch("sys.stderr", err):
                rc = main([
                    "--audit", str(sem_path),
                    "--index-db", str(ix_path),
                ])
            self.assertEqual(rc, 2)  # nonzero on findings
            combined = out.getvalue() + err.getvalue()
            self.assertIn("kind_mismatch", combined)
            self.assertIn("RTX 4090", combined)

    def test_audit_mode_clean_mappings_returns_zero(self):
        from core.memory.entity_semantic_suggester import main

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ix_path = tdp / "ix.db"
            _seed_ix_with_mentions(tdp)
            sem_path = tdp / "sem.yaml"
            sem_path.write_text(textwrap.dedent("""
            mappings:
              - phrase: "firstborn"
                targets:
                  - canonical_name: "Maez"
                    kind: "project"
                confidence: 1.0
            """).strip())
            out = io.StringIO()
            err = io.StringIO()
            with mock.patch("sys.stdout", out), \
                 mock.patch("sys.stderr", err):
                rc = main([
                    "--audit", str(sem_path),
                    "--index-db", str(ix_path),
                ])
            self.assertEqual(rc, 0)


# ── safety ──────────────────────────────────────────────────────


class TestNoSubprocessOrNetwork(unittest.TestCase):
    def test_no_subprocess_no_socket(self):
        from core.memory.entity_semantic_suggester import (
            suggest_semantic_drafts,
        )

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 socket, "socket",
                 side_effect=AssertionError("no socket"),
             ):
            ix = _seed_ix_with_mentions(Path(td))
            suggest_semantic_drafts(ix=ix, top_n=5)


if __name__ == "__main__":
    unittest.main()
