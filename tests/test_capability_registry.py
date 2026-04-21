# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.capability_registry.

The registry answers "what do I actually have?" for Maez. These tests
lock in the shape of the answer so the self-description surface stays
truthful across refactors.
"""
from __future__ import annotations

import unittest

from core.capability_registry import (
    describe, prompt_snippet, grounded_vocab,
)


class DescribeShape(unittest.TestCase):
    def test_describe_returns_expected_sections(self):
        d = describe()
        for key in ("modules", "services", "schedules",
                    "disabled_features", "recent_activity", "home"):
            self.assertIn(key, d, f"missing section: {key}")

    def test_modules_contains_core_and_daemon(self):
        d = describe()
        self.assertIn("core", d["modules"])
        self.assertIn("daemon", d["modules"])

    def test_schedules_include_load_bearing_cadences(self):
        s = describe()["schedules"]
        self.assertEqual(s["reasoning_cycle_seconds"], 30)
        self.assertEqual(s["daily_consolidation_hour_local"], 3)
        self.assertEqual(s["nightly_journal_hour_local"], 23)

    def test_disabled_features_lists_vision(self):
        """llama-server-vision was explicitly paused by the user. The
        registry must carry this so the model doesn't re-assert
        vision capability."""
        d = describe()
        self.assertIn("llama-server-vision", d["disabled_features"])


class PromptSnippet(unittest.TestCase):
    def test_snippet_is_nonempty_and_bounded(self):
        # Upper bound covers the capability block + fabrication memory
        # + residue + self-model blocks, all of which may be appended.
        # Raised from 2500 as organism blocks (residue, self-model)
        # were added 2026-04-20 — still under 4000 chars total so it
        # won't dominate the context window.
        s = prompt_snippet()
        self.assertGreater(len(s), 200, "snippet too sparse")
        self.assertLess(len(s), 4000,
            "snippet too long — would bloat every turn's context")

    def test_snippet_mentions_instruction_block(self):
        """The load-bearing part of the snippet is the INSTRUCTION that
        tells the model to default to uncertainty. If that's missing,
        the registry is decorative, not load-bearing."""
        s = prompt_snippet()
        self.assertIn("INSTRUCTION", s)
        self.assertTrue(
            "uncertainty" in s.lower() or "don't have that recorded" in s.lower(),
            "snippet missing the default-to-uncertainty instruction"
        )

    def test_snippet_mentions_disabled_features(self):
        """The model must see that vision is paused — otherwise it may
        still claim to process images."""
        s = prompt_snippet()
        self.assertIn("llama-server-vision", s)

    def test_snippet_mentions_30_second_cycle(self):
        """The 30s cycle is the one schedule fact most often fabricated
        away from (as '3AM cycles', 'nightly' etc.). Lock it in."""
        s = prompt_snippet()
        self.assertIn("30-second", s)


class GroundedVocab(unittest.TestCase):
    def test_vocab_is_frozenset(self):
        v = grounded_vocab()
        self.assertIsInstance(v, frozenset)

    def test_vocab_contains_live_services(self):
        v = grounded_vocab()
        # At least one maez* service is live on this box at all times.
        self.assertTrue(
            any(t.startswith("maez") for t in v),
            f"no maez-prefixed token in registry vocab: {sorted(v)}"
        )

    def test_vocab_has_split_service_parts(self):
        """Services like 'maez-web' are split into 'maez' + 'web' so the
        audit detector grounds bare-token references without needing the
        full hyphenated form."""
        v = grounded_vocab()
        self.assertIn("maez", v)
        # web service is always present
        self.assertIn("web", v)


# RegistryFeedsAudit removed 2026-04-21 with the regex detectors.
# The v2 judge doesn't consume the capability registry as a vocabulary;
# grounding is semantic per-response. Registry is still populated and
# surfaced elsewhere — this test just asserted a coupling that no longer
# exists.


if __name__ == "__main__":
    unittest.main()
