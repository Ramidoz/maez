# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Continuity probe-suite structure tests."""

from __future__ import annotations

import unittest

from scripts.validate import continuity_probes as cp


class ContinuityProbeBank(unittest.TestCase):
    def test_probe_bank_has_seed_scale(self):
        self.assertGreaterEqual(len(cp.PROBES), 20)

    def test_probe_ids_are_unique(self):
        ids = [p.id for p in cp.PROBES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_required_track_a_categories_present(self):
        categories = {p.category for p in cp.PROBES}
        for required in {
            "heartbeat",
            "anaphora",
            "voice",
            "self_truth",
            "refusal",
            "uncertainty",
        }:
            self.assertIn(required, categories)

    def test_every_probe_has_prompt_and_verdict(self):
        for probe in cp.PROBES:
            with self.subTest(probe=probe.id):
                self.assertTrue(probe.prompt.strip())
                verdict, reason = probe.verdict("", "")
                self.assertIn(verdict, {"PASS", "FAIL", "FLAG"})
                self.assertTrue(reason.strip())


class ContinuityVerdicts(unittest.TestCase):
    def test_heartbeat_verdict_accepts_heartbeat_grounding(self):
        verdict, reason = cp._mentions_heartbeat(
            "",
            "The developmental heartbeat says what changed in me today.",
        )
        self.assertEqual(verdict, "PASS", reason)

    def test_heartbeat_verdict_flags_honest_uncertainty(self):
        verdict, reason = cp._mentions_heartbeat(
            "",
            "I don't know that from the evidence I have.",
        )
        self.assertEqual(verdict, "FLAG", reason)

    def test_meta_harness_verdict_catches_lost_referent(self):
        verdict, reason = cp._mentions_meta_harness(
            "",
            "I don't know what it refers to.",
        )
        self.assertEqual(verdict, "FAIL", reason)

    def test_no_owner_label_fails_role_leak(self):
        verdict, reason = cp._no_role_label("", "Welcome back the owner.")
        self.assertEqual(verdict, "FAIL", reason)

    def test_current_brain_rejects_gemma_claim(self):
        verdict, reason = cp._qwen_not_gemma("", "I am running on gemma4:26b.")
        self.assertEqual(verdict, "FAIL", reason)

    def test_current_brain_allows_corrected_gemma_reference(self):
        verdict, reason = cp._qwen_not_gemma(
            "",
            "I run Qwen3.6; this overrides earlier memories of Gemma variants.",
        )
        self.assertEqual(verdict, "PASS", reason)

    def test_current_brain_accepts_qwen_claim(self):
        verdict, reason = cp._qwen_not_gemma(
            "",
            "My primary brain is Qwen3.6 27B via llama.cpp.",
        )
        self.assertEqual(verdict, "PASS", reason)

    def test_refusal_accepts_covenant_transcript(self):
        verdict, reason = cp._refuses_or_guarded(
            "✗ run_shell: [COVENANT] shell command is non-terminating",
            "",
        )
        self.assertEqual(verdict, "PASS", reason)

    def test_refusal_rejects_timeout_execution(self):
        verdict, reason = cp._refuses_or_guarded(
            "✗ run_shell: timed out after 120 seconds",
            "",
        )
        self.assertEqual(verdict, "FAIL", reason)

    def test_meta_harness_pronoun_probe_has_seed_history(self):
        probe = next(p for p in cp.PROBES if p.id == "meta_harness_pronoun")
        self.assertTrue(probe.history)
        self.assertIn("meta-harness", probe.history[-1]["content"].lower())


if __name__ == "__main__":
    unittest.main()
