# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Unit tests for the MSEL probe brief parser.

The probe runner itself is a one-shot measurement script; the parser
is the only piece worth unit-testing because reports are noise unless
parse classification is correct (a prior version misclassified
``Explanation:`` lines as canonical entity names)."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.probe.probe_msel_natural import _parse_brief


_BRIEF_WITH_EXPANSION = """=== LIVED RECALL — EVIDENCE-BACKED ===
=== ENTITY EXPANSION ===
- Maez [conf 1.0]: ep-d1254ff7a646, ep-322e1d8ed747
- RTX 4090 [conf 0.9]: ep-b63f30c46ef1
Explanation: matched 2 entities.
"""

_BRIEF_NO_EXPANSION = """=== LIVED RECALL — EVIDENCE-BACKED ===
PAST EPISODES
- ep-c8ac383cf4d7: kernel reboot at 03:14
"""

_BRIEF_EMPTY = ""


class TestParseBrief(unittest.TestCase):
    def test_expansion_section_extracts_canonicals_and_episodes(self):
        fired, entities, eps, phrases = _parse_brief(_BRIEF_WITH_EXPANSION)
        self.assertTrue(fired)
        self.assertEqual(entities, ["Maez", "RTX 4090"])
        self.assertEqual(
            eps,
            ["ep-d1254ff7a646", "ep-322e1d8ed747", "ep-b63f30c46ef1"],
        )
        self.assertEqual(phrases, [])

    def test_explanation_line_is_not_classified_as_entity(self):
        _, entities, _, _ = _parse_brief(_BRIEF_WITH_EXPANSION)
        # Regression guard: the prior parser greedily matched
        # "Explanation: matched 2 entities." as a canonical name.
        self.assertNotIn("Explanation: matched 2 entities.", entities)
        self.assertFalse(any("Explanation" in e for e in entities))

    def test_no_expansion_section_returns_no_entities(self):
        fired, entities, eps, _ = _parse_brief(_BRIEF_NO_EXPANSION)
        self.assertFalse(fired)
        self.assertEqual(entities, [])
        self.assertEqual(eps, ["ep-c8ac383cf4d7"])

    def test_empty_brief_returns_empty(self):
        fired, entities, eps, phrases = _parse_brief(_BRIEF_EMPTY)
        self.assertFalse(fired)
        self.assertEqual(entities, [])
        self.assertEqual(eps, [])
        self.assertEqual(phrases, [])


if __name__ == "__main__":
    unittest.main()
