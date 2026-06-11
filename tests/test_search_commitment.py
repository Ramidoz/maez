import unittest

from core.search.search_commitment import (
    OfferReceipt, is_clear_yes, resolve_affirmation,
)


def _r(**kw):
    base = dict(action_type="web_search", stakes="low_read", offered_query="llama.cpp news",
                created_ts=1000.0, ttl_seconds=300.0, ttl_turns=3, requires_confirmation=True,
                confirmation_mode="clear_yes_ok", executor="searxng",
                egress_class="sovereign_local_search")
    base.update(kw)
    return OfferReceipt(**base)


class ReceiptTests(unittest.TestCase):
    def test_fresh_within_window(self):
        self.assertTrue(_r().is_fresh(now_ts=1100.0, turns_since=1))

    def test_stale_by_time(self):
        self.assertFalse(_r().is_fresh(now_ts=1400.0, turns_since=1))

    def test_stale_by_turns(self):
        self.assertFalse(_r().is_fresh(now_ts=1100.0, turns_since=4))


class ClearYesTests(unittest.TestCase):
    def test_clear_yes(self):
        for t in ["yeah sure", "sure", "yes please", "go ahead", "ok do it", "yep", "yes"]:
            self.assertTrue(is_clear_yes(t), t)

    def test_not_clear_yes(self):
        for t in ["hmm", "k maybe", "not sure", "what do you mean", "no", "later", ""]:
            self.assertFalse(is_clear_yes(t), t)


class ResolverTests(unittest.TestCase):
    def _resolve(self, receipt, text, *, health="healthy", card=False):
        return resolve_affirmation(receipt, text, health=health, has_awaiting_card=card,
                                   now_ts=1100.0, turns_since=1)

    def test_happy_path_executes_exact_query(self):
        d = self._resolve(_r(), "yeah sure")
        self.assertTrue(d.execute)
        self.assertEqual(d.query, "llama.cpp news")  # the egress rail: the STORED query

    def test_no_receipt(self):
        self.assertFalse(self._resolve(None, "yeah sure").execute)

    def test_not_clear_yes(self):
        self.assertFalse(self._resolve(_r(), "hmm maybe").execute)

    def test_stale(self):
        d = resolve_affirmation(_r(), "yeah sure", health="healthy", has_awaiting_card=False,
                                now_ts=2000.0, turns_since=1)
        self.assertFalse(d.execute)
        self.assertEqual(d.reason, "stale_offer")

    def test_unhealthy_blocks(self):
        self.assertFalse(self._resolve(_r(), "yeah sure", health="down").execute)

    # --- the three MANDATORY trap-proof tests ---
    def test_high_stakes_blocked_even_with_clear_yes(self):
        d = self._resolve(_r(stakes="write"), "yeah sure")
        self.assertFalse(d.execute)
        self.assertEqual(d.reason, "stakes_too_high")

    def test_keyed_egress_blocked_even_with_clear_yes(self):
        d = self._resolve(_r(egress_class="external_keyed"), "yeah sure")
        self.assertFalse(d.execute)
        self.assertEqual(d.reason, "egress_not_sovereign")

    def test_awaiting_card_wins_over_yes(self):
        d = self._resolve(_r(), "yeah sure", card=True)
        self.assertFalse(d.execute)
        self.assertEqual(d.reason, "card_precedence")


if __name__ == "__main__":
    unittest.main()
