# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Alias-candidate suggester tests (Step 5l).

Reads existing lived-memory episodes and proposes alias candidates
the operator can paste into ``config/entity_aliases.local.yaml``.
Pure heuristic; no LLM; no writes by default.
"""

from __future__ import annotations

import io
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── helpers ────────────────────────────────────────────────────────


def _make_episodes(td: Path, items: list[tuple[str, str]]):
    """Create an EpisodeStore with rows of (title, summary)."""
    from core.memory.episodes import EpisodeStore

    ep = EpisodeStore(str(td / "lived.db"))
    ids: list[str] = []
    for i, (title, summary) in enumerate(items):
        ids.append(ep.add(
            title=title, summary=summary,
            participants=["rohit"],
            source_memory_ids=[f"mem-{i}"],
            source_kind="conversation",
            occurred_at=f"2026-04-{10 + i:02d}T09:00:00+00:00",
        ))
    return ep, ids


# ── core suggestion: co-occurrence ───────────────────────────────


class TestCoOccurrenceShortForm(unittest.TestCase):
    def test_maya_short_form_suggested_as_alias_of_maya_ananthan(self):
        from core.memory.entity_alias_suggester import suggest_aliases

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _make_episodes(Path(td), [
                ("Maya Ananthan started school", "first day"),
                ("classroom dynamics", "Maya seemed nervous"),
                ("dinner", "we cooked together"),
            ])
            suggestions = suggest_aliases(episodes=ep)
            cans = {s.canonical_name: s for s in suggestions}
            self.assertIn("Maya Ananthan", cans)
            self.assertIn("Maya", cans["Maya Ananthan"].aliases)

    def test_no_alias_suggested_when_short_form_absent(self):
        from core.memory.entity_alias_suggester import suggest_aliases

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _make_episodes(Path(td), [
                ("Maya Ananthan started school", "first day"),
                ("dinner", "we cooked together"),
            ])
            suggestions = suggest_aliases(episodes=ep)
            cans = {s.canonical_name: s for s in suggestions}
            # 'Maya Ananthan' still surfaces as a candidate entity,
            # but there should be no 'Maya' alias because the short
            # form never appears standalone.
            if "Maya Ananthan" in cans:
                self.assertEqual(cans["Maya Ananthan"].aliases, [])


# ── sentence-start junk filter ───────────────────────────────────


class TestSentenceStartFilter(unittest.TestCase):
    def test_the_hospital_not_suggested_as_entity(self):
        from core.memory.entity_alias_suggester import suggest_aliases

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _make_episodes(Path(td), [
                ("The Hospital was busy", "lots of people"),
                ("The Hospital had visitors", "again busy"),
            ])
            suggestions = suggest_aliases(episodes=ep)
            cans = {s.canonical_name for s in suggestions}
            self.assertNotIn("The Hospital", cans)

    def test_tomorrow_short_form_not_suggested_as_alias(self):
        from core.memory.entity_alias_suggester import suggest_aliases

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _make_episodes(Path(td), [
                ("Tomorrow Maya Ananthan will arrive", "long trip"),
                ("ride to airport", "Tomorrow is the day"),
            ])
            suggestions = suggest_aliases(episodes=ep)
            for s in suggestions:
                self.assertNotIn("Tomorrow", s.aliases)


# ── ix integration: existing canonical with 0 aliases ────────────


class TestIxIntegration(unittest.TestCase):
    def test_existing_entity_no_aliases_gets_short_form_suggestion(self):
        from core.memory.entity_alias_suggester import suggest_aliases
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _make_episodes(Path(td), [
                ("classroom dynamics", "Maya seemed nervous"),
                ("dinner", "we cooked together"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            ix.upsert_entity(
                "Maya Ananthan", kind="person",
            )  # no aliases
            suggestions = suggest_aliases(episodes=ep, ix=ix)
            cans = {s.canonical_name: s for s in suggestions}
            self.assertIn("Maya Ananthan", cans)
            self.assertIn("Maya", cans["Maya Ananthan"].aliases)
            # Kind preserved from ix.
            self.assertEqual(cans["Maya Ananthan"].kind, "person")

    def test_existing_entity_with_alias_skipped(self):
        """An entity already aliased by the operator shouldn't be
        re-surfaced — that would just make noise. The suggester is
        for filling gaps, not duplicating curated work."""
        from core.memory.entity_alias_suggester import suggest_aliases
        from core.memory.entity_index import EntityIndex

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _make_episodes(Path(td), [
                ("classroom dynamics", "Maya seemed nervous"),
            ])
            ix = EntityIndex(Path(td) / "ix.db")
            ix.upsert_entity(
                "Maya Ananthan", kind="person", aliases=["Maya"],
            )
            suggestions = suggest_aliases(episodes=ep, ix=ix)
            # Already-aliased entity should not appear.
            cans = {s.canonical_name for s in suggestions}
            self.assertNotIn("Maya Ananthan", cans)


# ── frequency + evidence ─────────────────────────────────────────


class TestEvidenceShape(unittest.TestCase):
    def test_each_suggestion_carries_episode_evidence(self):
        from core.memory.entity_alias_suggester import suggest_aliases

        with tempfile.TemporaryDirectory() as td:
            ep, ids = _make_episodes(Path(td), [
                ("Maya Ananthan started school", "first day"),
                ("classroom dynamics", "Maya seemed nervous"),
            ])
            suggestions = suggest_aliases(episodes=ep)
            cans = {s.canonical_name: s for s in suggestions}
            self.assertIn("Maya Ananthan", cans)
            s = cans["Maya Ananthan"]
            self.assertGreater(s.canonical_episode_count, 0)
            self.assertTrue(s.canonical_evidence_episode_ids)
            self.assertGreater(len(s.notes), 0)


# ── YAML round-trip with alias_seed loader ───────────────────────


class TestYamlRoundTripWithLoader(unittest.TestCase):
    def test_emitted_yaml_validates_with_alias_seed_loader(self):
        from core.memory.entity_alias_seed import load_seed_file
        from core.memory.entity_alias_suggester import (
            format_yaml, suggest_aliases,
        )

        with tempfile.TemporaryDirectory() as td:
            ep, _ = _make_episodes(Path(td), [
                ("Maya Ananthan started school", "first day"),
                ("classroom dynamics", "Maya seemed nervous"),
                ("Sample School meeting went well",
                 "met the principal"),
            ])
            suggestions = suggest_aliases(episodes=ep)
            yaml_text = format_yaml(suggestions)

            # Must parse as YAML.
            doc = yaml.safe_load(yaml_text)
            self.assertIn("entities", doc)
            self.assertIsInstance(doc["entities"], list)

            # Must round-trip through the alias_seed loader without
            # raising.
            f = Path(td) / "out.yaml"
            f.write_text(yaml_text)
            entries = load_seed_file(f)
            self.assertGreater(len(entries), 0)


# ── CLI: dry-run prints YAML to stdout, no writes ────────────────


class TestCliPrintsYamlNoWrites(unittest.TestCase):
    def test_main_prints_yaml_no_file_written(self):
        from core.memory.entity_alias_suggester import main

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            ep, _ = _make_episodes(tdp, [
                ("Maya Ananthan started school", "first day"),
                ("classroom dynamics", "Maya seemed nervous"),
            ])
            local_path = tdp / "config" / "entity_aliases.local.yaml"
            # Sanity: file does not exist before run.
            self.assertFalse(local_path.exists())

            out = io.StringIO()
            err = io.StringIO()
            with mock.patch("sys.stdout", out), \
                 mock.patch("sys.stderr", err):
                rc = main([
                    "--episodes-db", str(tdp / "lived.db"),
                ])
            self.assertEqual(rc, 0)
            self.assertIn("entities:", out.getvalue())
            self.assertIn("Maya Ananthan", out.getvalue())
            # No local-config write.
            self.assertFalse(local_path.exists())


# ── empty episode store → graceful exit ─────────────────────────


class TestEmptyEpisodeStore(unittest.TestCase):
    def test_no_episodes_emits_empty_doc_with_note(self):
        from core.memory.entity_alias_suggester import main

        with tempfile.TemporaryDirectory() as td:
            from core.memory.episodes import EpisodeStore

            EpisodeStore(str(Path(td) / "lived.db"))
            out = io.StringIO()
            err = io.StringIO()
            with mock.patch("sys.stdout", out), \
                 mock.patch("sys.stderr", err):
                rc = main([
                    "--episodes-db", str(Path(td) / "lived.db"),
                ])
            self.assertEqual(rc, 0)
            text = out.getvalue() + err.getvalue()
            self.assertTrue(
                "no" in text.lower() or "empty" in text.lower(),
                f"expected empty-corpus hint, got: {text!r}",
            )


# ── safety: no subprocess, no network ───────────────────────────


class TestNoSubprocessOrNetwork(unittest.TestCase):
    def test_no_subprocess_no_socket(self):
        from core.memory.entity_alias_suggester import suggest_aliases

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 socket, "socket",
                 side_effect=AssertionError("no socket"),
             ):
            ep, _ = _make_episodes(Path(td), [
                ("Maya Ananthan started school", "first day"),
                ("classroom dynamics", "Maya seemed nervous"),
            ])
            suggest_aliases(episodes=ep)


if __name__ == "__main__":
    unittest.main()
