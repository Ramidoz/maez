# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.fabrication_memory.

The module persists every audit hit so fabricated tokens can be
surfaced back into tomorrow's system prompt as 'don't reach for these
again'. These tests lock in:
  - record() never raises on any input shape
  - top_tokens grouping is case-insensitive
  - prompt_snippet includes the instruction block when non-empty
  - prompt_snippet is empty when the log is empty
  - end-to-end: an audit call writes a row
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from unittest.mock import patch

from core import fabrication_memory as fm
from core.self_claim_audit import audit


@dataclass
class _FakeFlag:
    kind: str
    ungrounded_token: str


class RecordAndTop(unittest.TestCase):
    def setUp(self):
        fm._diag_clear_for_test()

    def tearDown(self):
        fm._diag_clear_for_test()

    def test_record_writes_rows(self):
        flags = [_FakeFlag("framework", "Maelstrom"),
                 _FakeFlag("path", "src/maelstrom")]
        fm.record(surface="test", flags=flags, mode="sentence")
        self.assertEqual(fm._diag_total_rows(), 2)

    def test_record_empty_flags_is_noop(self):
        fm.record(surface="test", flags=[], mode="noop")
        self.assertEqual(fm._diag_total_rows(), 0)

    def test_top_tokens_case_insensitive_grouping(self):
        # Three different casings of the same fabricated name should
        # group to a single bucket with count=3.
        for tok in ("Maelstrom", "maelstrom", "MAELSTROM"):
            fm.record(surface="test",
                      flags=[_FakeFlag("framework", tok)],
                      mode="sentence")
        top = fm.top_tokens(days=7, limit=10)
        matching = [r for r in top if r[0].lower() == "maelstrom"]
        self.assertEqual(len(matching), 1,
            f"expected single grouped bucket, got: {top}")
        self.assertEqual(matching[0][2], 3)

    def test_top_tokens_respects_days_window(self):
        """Rows older than the window must be excluded. Fake an old row
        by manipulating ts directly through the db."""
        import sqlite3
        fm._ensure_db()
        with fm._db_lock:
            db = sqlite3.connect(fm._DB_PATH)
            # ts 30 days ago
            db.execute(
                "INSERT INTO fabrication_log "
                "(ts, surface, kind, token, token_lower, mode) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (1.0, "test", "framework", "OldFabrication",
                 "oldfabrication", "sentence"),
            )
            db.commit()
        top = fm.top_tokens(days=7, limit=10)
        self.assertFalse(
            any(r[0].lower() == "oldfabrication" for r in top),
            "row outside window leaked into top_tokens")


class PromptSnippet(unittest.TestCase):
    def setUp(self):
        fm._diag_clear_for_test()

    def tearDown(self):
        fm._diag_clear_for_test()

    def test_empty_log_returns_empty_string(self):
        s = fm.prompt_snippet()
        self.assertEqual(s, "",
            "empty log must yield empty prompt so we don't inject a dead block")

    def test_nonempty_log_returns_block_with_instruction(self):
        fm.record(surface="test",
                  flags=[_FakeFlag("framework", "Maelstrom")],
                  mode="sentence")
        s = fm.prompt_snippet()
        self.assertIn("FABRICATION MEMORY", s)
        self.assertIn("INSTRUCTION", s)
        self.assertIn("Maelstrom", s)

    def test_path_tokens_are_not_echoed_raw(self):
        """Paths could reseed a follow-on fabrication if echoed verbatim
        into the prompt. The snippet sanitises slashes."""
        fm.record(surface="test",
                  flags=[_FakeFlag("path", "src/maelstrom")],
                  mode="sentence")
        s = fm.prompt_snippet()
        self.assertNotIn("src/maelstrom", s,
            f"raw path leaked into prompt: {s!r}")


class EndToEndAuditIntegration(unittest.TestCase):
    """A real audit call must write to the fabrication log."""

    def setUp(self):
        fm._diag_clear_for_test()
        fm._diag_clear_events_for_test()

    def tearDown(self):
        fm._diag_clear_for_test()
        fm._diag_clear_events_for_test()

    def test_audit_rewrite_populates_events(self):
        # v2: audit is judge-powered. Stub the judge so this test is
        # deterministic. A judge-flagged rewrite must write a row to
        # fabrication_events (not the legacy fabrication_log).
        text = "The disk has been hovering around 70% for weeks."
        fake_flag = [{"text": text, "reason": "snapshot has no history"}]
        with patch("core.grounding_judge.judge", return_value=fake_flag), \
             patch("core.fabrication_memory.few_shots_for", return_value=[]):
            r = audit(text, surface="test_e2e")
        self.assertTrue(r.rewritten, "stubbed judge flag must trigger rewrite")
        # Event row lands via _emit → record_event
        import sqlite3
        conn = sqlite3.connect(fm._DB_PATH)
        try:
            n = conn.execute("SELECT COUNT(*) FROM fabrication_events").fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(n, 0, "judge-flagged audit must leave a fabrication_event")

    def test_audit_noop_does_not_populate_events(self):
        # Stub the judge to return empty → no rewrite, no event row.
        text = "Some benign text."
        with patch("core.grounding_judge.judge", return_value=[]), \
             patch("core.fabrication_memory.few_shots_for", return_value=[]):
            r = audit(text, surface="test_e2e")
        self.assertFalse(r.rewritten)
        import sqlite3
        conn = sqlite3.connect(fm._DB_PATH)
        try:
            n = conn.execute("SELECT COUNT(*) FROM fabrication_events").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 0, "clean reply must not leave an event")


class FewShotsForSignalShape(unittest.TestCase):
    def setUp(self):
        fm._diag_clear_for_test()
        fm._diag_clear_events_for_test()

    def tearDown(self):
        fm._diag_clear_for_test()
        fm._diag_clear_events_for_test()

    def test_returns_empty_when_log_empty(self):
        result = fm.few_shots_for(signals_absent=["screen observation"], k=3)
        self.assertEqual(result, [])

    def test_prefers_matching_signal_shape(self):
        # Three events with different signal-absent shapes.
        # Query for screen+presence — expect the matching one first.
        fm.record_event(
            surface="test", text="Rohit is typing code",
            signals_absent=["screen observation", "presence snapshot"],
            reason="activity claim without screen/presence", mode="dual",
        )
        fm.record_event(
            surface="test", text="disk usage is at 91%",
            signals_absent=["calendar"],
            reason="calendar claim without calendar signal", mode="dual",
        )
        fm.record_event(
            surface="test", text="he seems focused on the project",
            signals_absent=["presence snapshot"],
            reason="presence claim without presence signal", mode="dual",
        )
        result = fm.few_shots_for(
            signals_absent=["screen observation", "presence snapshot"], k=3
        )
        self.assertGreater(len(result), 0)
        # The event with both matching signals should be first
        self.assertIn("Rohit is typing code", result[0]["text"])

    def test_limits_to_k(self):
        for i in range(5):
            fm.record_event(
                surface="test", text=f"fabricated claim {i}",
                signals_absent=["screen observation"],
                reason="activity without screen", mode="dual",
            )
        result = fm.few_shots_for(signals_absent=["screen observation"], k=2)
        self.assertLessEqual(len(result), 2)

    def test_fallback_to_recent_when_no_shape_match(self):
        fm.record_event(
            surface="test", text="something happened",
            signals_absent=["calendar"],
            reason="calendar claim", mode="dual",
        )
        # Query for a completely different signal shape — should still
        # return the event as fallback (recency)
        result = fm.few_shots_for(signals_absent=["presence snapshot"], k=3)
        self.assertEqual(len(result), 1)
        self.assertIn("something happened", result[0]["text"])

    def test_result_dicts_have_required_keys(self):
        fm.record_event(
            surface="test", text="owner is at his desk",
            signals_absent=["presence snapshot"],
            reason="presence claim", mode="dual",
        )
        result = fm.few_shots_for(signals_absent=["presence snapshot"], k=1)
        self.assertEqual(len(result), 1)
        for key in ("text", "signals_absent", "reason"):
            self.assertIn(key, result[0], f"missing key {key!r} in result")


if __name__ == "__main__":
    unittest.main()
