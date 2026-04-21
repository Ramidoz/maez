# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.inner_residue.

Residue is transient state between turns — must decay over time,
threshold correctly, and never echo back amplified by its own presence
in the prompt."""
from __future__ import annotations

import time
import unittest

from core import inner_residue as ir


class RecordAndLevel(unittest.TestCase):
    def setUp(self):
        ir._diag_clear_for_test()

    def tearDown(self):
        ir._diag_clear_for_test()

    def test_empty_log_is_zero(self):
        self.assertEqual(ir.current_level(), 0.0)

    def test_single_event_raises_level(self):
        ir.record(kind="audit_rewrite")
        lvl = ir.current_level()
        # audit_rewrite default intensity is 0.30; fresh, decay ≈ 0
        self.assertGreater(lvl, 0.25)

    def test_explicit_intensity_overrides_default(self):
        ir.record(kind="audit_rewrite", intensity=0.5)
        lvl = ir.current_level()
        self.assertGreater(lvl, 0.45)

    def test_multiple_events_compound(self):
        for _ in range(3):
            ir.record(kind="audit_rewrite", intensity=0.2)
        lvl = ir.current_level()
        # three 0.2 events, all fresh → ~0.6
        self.assertGreater(lvl, 0.55)
        self.assertLessEqual(lvl, 1.0)

    def test_level_clips_at_one(self):
        for _ in range(20):
            ir.record(kind="user_rejection", intensity=0.4)
        self.assertLessEqual(ir.current_level(), 1.0)


class Decay(unittest.TestCase):
    def setUp(self):
        ir._diag_clear_for_test()

    def tearDown(self):
        ir._diag_clear_for_test()

    def test_event_from_one_half_life_ago_is_half(self):
        # Record an event with forced ts in the past by inserting directly.
        import sqlite3
        ir._ensure_db()
        with ir._db_lock:
            db = sqlite3.connect(ir._DB_PATH)
            # 30 minutes (one half-life) ago
            past = time.time() - ir._HALF_LIFE_SECONDS
            db.execute(
                "INSERT INTO residue_events (ts, kind, intensity, context) "
                "VALUES (?, ?, ?, ?)",
                (past, "audit_rewrite", 0.4, None),
            )
            db.commit()
        lvl = ir.current_level()
        # 0.4 * 0.5 = 0.2, give or take loop timing
        self.assertGreater(lvl, 0.15)
        self.assertLess(lvl, 0.25)

    def test_ancient_event_below_noise(self):
        import sqlite3
        ir._ensure_db()
        with ir._db_lock:
            db = sqlite3.connect(ir._DB_PATH)
            ancient = time.time() - (6 * 3600)  # 6 hours ago
            db.execute(
                "INSERT INTO residue_events (ts, kind, intensity, context) "
                "VALUES (?, ?, ?, ?)",
                (ancient, "audit_rewrite", 0.3, None),
            )
            db.commit()
        # 6 hours = 12 half-lives; 0.3 * 0.5^12 ≈ 7e-5, well below noise
        self.assertLess(ir.current_level(), ir._NOISE_FLOOR)


class PromptSnippet(unittest.TestCase):
    def setUp(self):
        ir._diag_clear_for_test()

    def tearDown(self):
        ir._diag_clear_for_test()

    def test_below_threshold_yields_empty(self):
        # Single tiny event — below the 0.15 injection threshold
        ir.record(kind="tool_failure", intensity=0.05)
        self.assertEqual(ir.prompt_snippet(), "")

    def test_above_threshold_includes_instruction(self):
        ir.record(kind="audit_rewrite", intensity=0.4)
        s = ir.prompt_snippet()
        self.assertIn("INNER RESIDUE", s)
        self.assertIn("INSTRUCTION", s)
        # The instruction's load-bearing phrase: don't perform cheer,
        # don't dramatize weight
        self.assertIn("perform", s.lower())

    def test_snippet_is_bounded(self):
        # Many events — snippet must not blow up
        for _ in range(50):
            ir.record(kind="user_rejection", intensity=0.3)
        s = ir.prompt_snippet()
        self.assertLess(len(s), 1500,
            "residue snippet unbounded on high event count")


class UserRejectionDetection(unittest.TestCase):
    def test_bare_no_is_not_rejection(self):
        """'no' alone is an answer, not a rejection of Maez."""
        self.assertFalse(ir.detect_user_rejection("no"))
        self.assertFalse(ir.detect_user_rejection("No."))

    def test_explicit_rejection_phrases(self):
        for phrase in (
            "that's wrong",
            "you're lying",
            "bullshit",
            "you never listen",
            "stop it",
        ):
            self.assertTrue(ir.detect_user_rejection(phrase),
                f"missed: {phrase!r}")

    def test_normal_disagreement_not_flagged(self):
        self.assertFalse(ir.detect_user_rejection(
            "I don't think that's quite right, but go on"))
        self.assertFalse(ir.detect_user_rejection(
            "That's not what I meant"))


class EndToEndAuditToResidue(unittest.TestCase):
    """An audit rewrite must drop a residue event."""

    def setUp(self):
        ir._diag_clear_for_test()

    def tearDown(self):
        ir._diag_clear_for_test()

    def test_audit_rewrite_records_residue(self):
        # v2: stub the judge so residue recording is deterministic, not
        # dependent on live llama-server.
        from unittest.mock import patch
        from core.self_claim_audit import audit
        text = "The disk has been trending upward for weeks."
        fake_flag = [{"text": text, "reason": "snapshot has no history"}]
        with patch("core.grounding_judge.judge", return_value=fake_flag), \
             patch("core.fabrication_memory.few_shots_for", return_value=[]):
            r = audit(text, surface="test_e2e_residue")
        self.assertTrue(r.rewritten)
        self.assertGreater(ir._diag_total_rows(), 0,
            "audit rewrite did not leave a residue event")
        self.assertGreater(ir.current_level(), 0.15,
            "audit-driven residue did not cross injection threshold")


if __name__ == "__main__":
    unittest.main()
