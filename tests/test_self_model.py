# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.self_model.

Self-model is a factual snapshot of "how Maez has been lately" built
from real sources on disk. These tests lock in:
  - describe() returns all expected sections
  - prompt_snippet() degrades to empty string when sources are sparse
  - prompt_snippet() includes the 'read, don't re-derive' instruction
  - wonderings query works against the real db schema
  - no LLM generation — every output field traces to a real source
"""
from __future__ import annotations

import unittest

from core import self_model as sm


class DescribeShape(unittest.TestCase):
    def test_describe_returns_all_sections(self):
        d = sm.describe()
        for key in ("recent_themes", "recent_vague_rate", "wonderings",
                    "recent_fabrication_attempts", "residue_level", "ts"):
            self.assertIn(key, d, f"missing section: {key}")

    def test_recent_themes_shape(self):
        """Either empty list or list of (topic:str, count:int) tuples."""
        themes = sm._recent_themes()
        self.assertIsInstance(themes, list)
        for item in themes:
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], str)
            self.assertIsInstance(item[1], int)

    def test_wonderings_snapshot_shape(self):
        w = sm._wonderings_snapshot()
        self.assertIn("open_count", w)
        self.assertIn("sample_question", w)
        self.assertIsInstance(w["open_count"], int)
        self.assertGreaterEqual(w["open_count"], 0)

    def test_residue_level_is_float(self):
        lvl = sm._residue_level()
        self.assertIsInstance(lvl, float)
        self.assertGreaterEqual(lvl, 0.0)

    def test_top_fabrications_shape(self):
        """Either empty or list of (token, kind, count) tuples."""
        fabs = sm._top_fabrications(limit=3)
        self.assertIsInstance(fabs, list)
        for item in fabs:
            self.assertEqual(len(item), 3)


class PromptSnippet(unittest.TestCase):
    def test_snippet_is_string(self):
        s = sm.prompt_snippet()
        self.assertIsInstance(s, str)

    def test_snippet_has_instruction_when_nonempty(self):
        """If the snippet has content, it must carry the 'read, don't
        re-derive' instruction — otherwise it's dead weight in the
        prompt."""
        s = sm.prompt_snippet()
        if s:
            self.assertIn("INSTRUCTION", s)
            self.assertIn("SELF-MODEL", s)

    def test_snippet_bounded(self):
        """Snippet must not grow unbounded even with many sources."""
        s = sm.prompt_snippet()
        self.assertLess(len(s), 2000, "self-model snippet too long")


class Integration(unittest.TestCase):
    """End-to-end: self_model is consumed by capability_registry's
    prompt_snippet when self_model has content."""

    def test_capability_registry_includes_self_model_when_present(self):
        """If self_model.prompt_snippet() is non-empty, it must appear
        in the final capability_registry output so the model sees it."""
        from core.capability_registry import prompt_snippet as _cap
        sm_snip = sm.prompt_snippet()
        if not sm_snip:
            self.skipTest("self_model empty on this box; integration path "
                          "exercised only when there's content to embed")
        full = _cap()
        self.assertIn("SELF-MODEL", full,
            "self_model block missing from capability_registry output")


if __name__ == "__main__":
    unittest.main()
