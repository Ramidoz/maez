# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Semantic entity resolver tests (Step 5n).

The Step 5j A/B showed that "tell me about X" queries don't benefit
from entity expansion because the keyword pass already matches X
literally. The missing layer is owner-language: "the firstborn"
means Maez, "your body" means the hardware/runtime, "birth"
means Track A. None of these phrases appear in episode text, so
no extractor (deterministic or LLM) can produce them as aliases.
This module is the curated semantic bridge — owner writes the
mappings; resolver looks them up and returns ``EntityMatch``
shapes the expansion section already knows how to render.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── helpers ────────────────────────────────────────────────────────


_SAMPLE_YAML = textwrap.dedent(
    """
    mappings:
      - phrase: "firstborn"
        targets:
          - canonical_name: "Maez"
            kind: "project"
        confidence: 1.0
        notes: "Owner-curated"
      - phrase: "body"
        targets:
          - canonical_name: "RTX 4090"
            kind: "hardware"
          - canonical_name: "llama.cpp"
            kind: "software"
        confidence: 0.9
      - phrase: "birth"
        targets:
          - canonical_name: "Track A"
            kind: "project"
        confidence: 0.9
    """
).strip()


def _seed_ix(td: Path):
    from core.memory.entity_index import EntityIndex

    ix = EntityIndex(td / "ix.db")
    ix.upsert_entity("Maez", kind="project")
    ix.upsert_entity("RTX 4090", kind="hardware")
    ix.upsert_entity("llama.cpp", kind="software")
    ix.upsert_entity("Track A", kind="project")
    return ix


def _write_yaml(td: Path, body: str = _SAMPLE_YAML) -> Path:
    p = td / "semantics.yaml"
    p.write_text(body)
    return p


# ── load_semantic_mappings ────────────────────────────────────────


class TestLoadSemanticMappings(unittest.TestCase):
    def test_loads_well_formed_file(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings,
        )

        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td))
            mappings = load_semantic_mappings(path)
            self.assertEqual(len(mappings), 3)
            phrases = {m.phrase for m in mappings}
            self.assertEqual(
                phrases, {"firstborn", "body", "birth"},
            )
            firstborn = next(m for m in mappings if m.phrase == "firstborn")
            self.assertEqual(firstborn.confidence, 1.0)
            self.assertEqual(len(firstborn.targets), 1)
            self.assertEqual(firstborn.targets[0]["canonical_name"], "Maez")

    def test_missing_phrase_fails(self):
        from core.memory.entity_semantic_resolver import (
            SemanticConfigError, load_semantic_mappings,
        )

        body = textwrap.dedent("""
        mappings:
          - targets:
              - canonical_name: "Maez"
                kind: "project"
            confidence: 1.0
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SemanticConfigError):
                load_semantic_mappings(path)

    def test_missing_targets_fails(self):
        from core.memory.entity_semantic_resolver import (
            SemanticConfigError, load_semantic_mappings,
        )

        body = textwrap.dedent("""
        mappings:
          - phrase: "firstborn"
            confidence: 1.0
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SemanticConfigError):
                load_semantic_mappings(path)

    def test_target_missing_canonical_name_fails(self):
        from core.memory.entity_semantic_resolver import (
            SemanticConfigError, load_semantic_mappings,
        )

        body = textwrap.dedent("""
        mappings:
          - phrase: "firstborn"
            targets:
              - kind: "project"
            confidence: 1.0
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SemanticConfigError):
                load_semantic_mappings(path)

    def test_invalid_yaml_fails_cleanly(self):
        from core.memory.entity_semantic_resolver import (
            SemanticConfigError, load_semantic_mappings,
        )

        body = "mappings: [\n  not: valid:: yaml: ::"
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SemanticConfigError):
                load_semantic_mappings(path)

    def test_confidence_out_of_range_fails(self):
        from core.memory.entity_semantic_resolver import (
            SemanticConfigError, load_semantic_mappings,
        )

        body = textwrap.dedent("""
        mappings:
          - phrase: "firstborn"
            targets:
              - canonical_name: "Maez"
                kind: "project"
            confidence: 1.5
        """).strip()
        with tempfile.TemporaryDirectory() as td:
            path = _write_yaml(Path(td), body)
            with self.assertRaises(SemanticConfigError):
                load_semantic_mappings(path)


# ── resolve: phrase matching ─────────────────────────────────────


class TestResolveHappyPath(unittest.TestCase):
    def test_firstborn_resolves_to_maez(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            ix = _seed_ix(tdp)
            res = resolve_semantic_entities(
                "how is the firstborn?", ix=ix, mappings=mappings,
            )
            self.assertIn("firstborn", res.matched_phrases)
            names = {e.canonical_name for e in res.resolved_entities}
            self.assertIn("Maez", names)
            self.assertEqual(res.confidence, 1.0)

    def test_multi_target_phrase_resolves_all(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            ix = _seed_ix(tdp)
            res = resolve_semantic_entities(
                "what changed about your body?",
                ix=ix, mappings=mappings,
            )
            self.assertIn("body", res.matched_phrases)
            names = {e.canonical_name for e in res.resolved_entities}
            self.assertIn("RTX 4090", names)
            self.assertIn("llama.cpp", names)
            # confidence honoured from mapping
            self.assertAlmostEqual(res.confidence, 0.9, places=4)

    def test_empty_query_returns_empty_resolution(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            ix = _seed_ix(tdp)
            for q in ("", "   ", None):
                res = resolve_semantic_entities(
                    q, ix=ix, mappings=mappings,
                )
                self.assertEqual(res.matched_phrases, [])
                self.assertEqual(res.resolved_entities, [])
                self.assertEqual(res.confidence, 0.0)

    def test_no_phrase_match_returns_empty(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            ix = _seed_ix(tdp)
            res = resolve_semantic_entities(
                "what's the weather like?",
                ix=ix, mappings=mappings,
            )
            self.assertEqual(res.matched_phrases, [])
            self.assertEqual(res.resolved_entities, [])

    def test_word_boundary_prevents_substring_match(self):
        """'birth' should not match 'birthday'."""
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            ix = _seed_ix(tdp)
            res = resolve_semantic_entities(
                "happy birthday everyone", ix=ix, mappings=mappings,
            )
            self.assertNotIn("birth", res.matched_phrases)

    def test_case_insensitive(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            ix = _seed_ix(tdp)
            res = resolve_semantic_entities(
                "HOW IS THE FIRSTBORN?", ix=ix, mappings=mappings,
            )
            self.assertIn("firstborn", res.matched_phrases)


# ── missing target → warn, do not fabricate ──────────────────────


class TestMissingTargetWarns(unittest.TestCase):
    def test_target_not_in_ix_emits_warning_no_entity(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            from core.memory.entity_index import EntityIndex
            ix = EntityIndex(tdp / "ix.db")
            # Only Maez exists — RTX 4090 / llama.cpp / Track A
            # missing.
            ix.upsert_entity("Maez", kind="project")

            res = resolve_semantic_entities(
                "how is the body?", ix=ix, mappings=mappings,
            )
            # Phrase matched, but no entities resolved.
            self.assertIn("body", res.matched_phrases)
            self.assertEqual(res.resolved_entities, [])
            self.assertGreaterEqual(len(res.warnings), 1)
            joined = " ".join(res.warnings).lower()
            self.assertIn("rtx 4090", joined)
            self.assertIn("not found", joined)

    def test_partial_target_match_returns_what_exists(self):
        """If 'body' has 2 targets and only 1 is in ix, return the
        one that exists and warn about the missing one — don't
        suppress the partial answer."""
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            from core.memory.entity_index import EntityIndex
            ix = EntityIndex(tdp / "ix.db")
            ix.upsert_entity("RTX 4090", kind="hardware")
            # llama.cpp intentionally absent
            res = resolve_semantic_entities(
                "how is the body?", ix=ix, mappings=mappings,
            )
            names = {e.canonical_name for e in res.resolved_entities}
            self.assertEqual(names, {"RTX 4090"})
            joined = " ".join(res.warnings).lower()
            self.assertIn("llama.cpp", joined)


# ── ambiguous: multiple mappings can apply ───────────────────────


class TestMultipleMappingsApply(unittest.TestCase):
    def test_multiple_phrases_in_query_resolve_all(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            ix = _seed_ix(tdp)
            res = resolve_semantic_entities(
                "how is the firstborn after the birth?",
                ix=ix, mappings=mappings,
            )
            self.assertIn("firstborn", res.matched_phrases)
            self.assertIn("birth", res.matched_phrases)
            names = {e.canonical_name for e in res.resolved_entities}
            self.assertIn("Maez", names)
            self.assertIn("Track A", names)
            # confidence = max of matched (1.0 from firstborn)
            self.assertEqual(res.confidence, 1.0)


# ── example file is not private ──────────────────────────────────


class TestExampleFileIsNotPrivate(unittest.TestCase):
    EXAMPLE_PATH = _REPO / "docs" / "entity_semantics.example.yaml"
    PRIVATE_TOKENS = (
        "rohit", "ananthan", "ramidoz", "alienware", "aime",
    )

    def test_example_file_exists(self):
        self.assertTrue(self.EXAMPLE_PATH.is_file())

    def test_example_file_loads_clean(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings,
        )

        mappings = load_semantic_mappings(self.EXAMPLE_PATH)
        self.assertGreater(len(mappings), 0)

    def test_example_file_has_no_private_tokens(self):
        text = self.EXAMPLE_PATH.read_text().lower()
        for tok in self.PRIVATE_TOKENS:
            self.assertNotIn(
                tok, text,
                f"example semantics file leaked private token {tok!r}",
            )


# ── gitignore covers local config ────────────────────────────────


class TestGitignoreCoversLocalSemanticsFile(unittest.TestCase):
    def test_local_semantics_path_is_gitignored(self):
        gi = _REPO / ".gitignore"
        self.assertTrue(gi.is_file())
        self.assertIn(
            "config/entity_semantics.local.yaml", gi.read_text(),
        )


# ── safety ──────────────────────────────────────────────────────


class TestNoSubprocessOrNetwork(unittest.TestCase):
    def test_no_subprocess_no_socket(self):
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings, resolve_semantic_entities,
        )

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=AssertionError("no subprocess"),
             ), mock.patch.object(
                 socket, "socket",
                 side_effect=AssertionError("no socket"),
             ):
            tdp = Path(td)
            mappings = load_semantic_mappings(_write_yaml(tdp))
            ix = _seed_ix(tdp)
            resolve_semantic_entities(
                "how is the firstborn?",
                ix=ix, mappings=mappings,
            )


if __name__ == "__main__":
    unittest.main()
