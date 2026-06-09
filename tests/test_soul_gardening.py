"""Soul-Gardening v0 — assert the composed soul state after subtractive edits.

These run against the WORKTREE's config (base-only, no local layer), which is
correct: every invariant-protected commitment lives in soul.base.md.
"""
import unittest

import core.evolution.soul_loader as _sl
from core.evolution.soul_loader import current_soul
from core.evolution.soul_invariants import check


def _fresh_soul() -> str:
    # current_soul() caches on file mtimes; clear so each test reads disk.
    with _sl._lock:
        _sl._cache_text = None
        _sl._cache_signature = None
    return current_soul()


class SoulGardening(unittest.TestCase):
    def test_invariants_hold(self):
        r = check(_fresh_soul())
        self.assertTrue(r.ok, r.summary())

    def test_contradiction_reworded(self):
        soul = _fresh_soul()
        self.assertNotIn("extension of the owner's workflow", soul)
        self.assertNotIn("not a separate entity asking for instructions", soul)
        self.assertIn(
            "Act proactively from your own judgment inside the bond", soul
        )

    def test_rules_replaced_with_pointer(self):
        soul = _fresh_soul()
        for header in (
            "## Never fabricate a search",
            "## Never fabricate a command",
            "## Never fabricate administrative",
            "## Never name an internal framework",
            "## Never claim completion",
            "## Never narrate recalled memory",
        ):
            self.assertNotIn(header, soul)
        # Honest pointer (covenant panel fix): names only LIVE rails, does not
        # over-claim "honest by construction", and does not name a sleeping rail.
        self.assertNotIn("honest by construction", soul)
        self.assertNotIn("recall receipts", soul)
        self.assertIn("cite-or-decline", soul)
        self.assertIn("now guarded by substrate rails", soul)
        self.assertIn(
            "they do not replace your responsibility to speak only from evidence", soul
        )
        # Terse anchors kept for the modes still prose-held (rules 3/5/6):
        # Anchor retirement: admin-side-effects + completion are now enforced by
        # the live deterministic completion-rail, so they retire from the soul.
        self.assertNotIn("do not invent administrative side-effects", soul)
        self.assertNotIn("do not claim completion before a real result exists", soul)
        # recalled-as-present stays (still judge-only / prose-held).
        self.assertIn("do not present recalled memory as live observation", soul)

    def test_elderly_phrase_removed(self):
        soul = _fresh_soul()
        self.assertNotIn("elderly care", soul)
        # Option A: purely subtractive — no grandmother-origin authored here.
        self.assertNotIn("grandmother", soul.lower())


if __name__ == "__main__":
    unittest.main()
