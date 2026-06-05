# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""TRF Intent Gate Alignment v1.

The TRF temporal-recall intent gate (``_MEMORY_INTENT_RE`` in
``core/memory/temporal_anchor_recall.py``) was too narrow: continuity-shaped
recall asks like "what were we working on last week?" fell through before the
temporal anchor was ever checked — a false-negative witnessed live on the
daemon path (read-only TRF witness, 2026-06-05). This matrix expands the gate to
recognize those stems while keeping the anchor requirement and the negative /
self-memory guards intact, so a *statement* ("I was working on X yesterday")
never becomes a recall ask.

The gate property is ``anchor_kind``: it is non-None only when the negative and
self-memory guards pass AND a temporal anchor matched AND the intent gate
matched — exactly the gate this slice widens.
"""

from __future__ import annotations

import unittest

from core.memory.temporal_anchor_recall import detect_temporal_anchor


class TrfIntentGateAlignmentTests(unittest.TestCase):
    def test_continuity_shaped_temporal_asks_now_fire(self):
        # the witnessed misses — each pairs a continuity-shaped stem with a real anchor
        cases = [
            ("what were we working on last week?", "last_week"),
            ("what were we discussing yesterday?", "yesterday"),
            ("what were we talking about this morning?", "this_morning"),
            ("what were we doing earlier today?", "earlier_today"),
        ]
        for prompt, kind in cases:
            with self.subTest(prompt=prompt):
                self.assertEqual(detect_temporal_anchor(prompt).anchor_kind, kind)

    def test_controls_stay_silent(self):
        # statement (not a recall ask); self-memory; negative-intent; no-anchor
        for prompt in [
            "I was working on X yesterday.",
            "I remember what we did yesterday.",
            "not asking you to remember last week",
            "what were we working on?",  # no temporal anchor -> continuity's lane, not TRF's
        ]:
            with self.subTest(prompt=prompt):
                self.assertIsNone(detect_temporal_anchor(prompt).anchor_kind)

    def test_existing_phrasings_unchanged(self):
        # regression guard: the original recognized phrasings still fire
        for prompt, kind in [
            ("what did we do yesterday?", "yesterday"),
            ("what happened this morning?", "this_morning"),
            ("do you remember earlier today?", "earlier_today"),
        ]:
            with self.subTest(prompt=prompt):
                self.assertEqual(detect_temporal_anchor(prompt).anchor_kind, kind)


if __name__ == "__main__":
    unittest.main()
