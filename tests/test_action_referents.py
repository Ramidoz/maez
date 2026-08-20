"""Phase 2 commit D: the ActionReferent union + anaphora gating.
Gate REDs 9-10 (wrong-user card; stale receipt both forms) + anaphora
referent requirement + DEFERRED inclusion (P3a reversal)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.brain.action_referents import (
    CardReferent,
    CommitmentReferent,
    ProposalReferent,
    assemble_action_referents,
)
from core.brain.brain_loop import _action_intent_syntactic_floor as floor


class _Store:
    def __init__(self, records):
        self._records = records

    def get_open_for_channel(self, channel, chat_id):
        return self._records


class _Controller:
    def __init__(self, receipt):
        self._r = receipt

    def get_search_offer(self, channel, chat_id):
        return self._r


def _receipt(created_ts, ttl_seconds=300.0, ttl_turns=3, created_turn_seq=None):
    from core.search.search_commitment import OfferReceipt

    return OfferReceipt(
        action_type="web_search", stakes="low_read", offered_query="q",
        created_ts=created_ts, ttl_seconds=ttl_seconds, ttl_turns=ttl_turns,
        requires_confirmation=True, confirmation_mode="clear_yes_ok",
        executor="searxng", egress_class="sovereign_local_search",
        created_turn_seq=created_turn_seq,
    )


class CardReferentTests(unittest.TestCase):
    def test_wrong_user_card_yields_no_referent(self):
        store = _Store([SimpleNamespace(
            request_id="r1", action="write_file", status="open",
            user_id="somebody_else",
        )])
        out = assemble_action_referents(
            channel="telegram_surface", chat_id="c1", user_id="rohit",
            card_store=store, now_ts=1000.0,
        )
        self.assertEqual(out, ())

    def test_deferred_card_is_a_valid_referent(self):
        # P3a reversal: deferral postpones re-presentation, never
        # revokes consent-target authority.
        store = _Store([SimpleNamespace(
            request_id="r2", action="write_file", status="deferred",
            user_id="rohit",
        )])
        out = assemble_action_referents(
            channel="telegram_surface", chat_id="c1", user_id="rohit",
            card_store=store, now_ts=1000.0,
        )
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], CardReferent)
        self.assertEqual(out[0].status, "deferred")


class CommitmentReferentTests(unittest.TestCase):
    def test_fresh_receipt_yields_referent(self):
        ctl = _Controller(_receipt(created_ts=990.0))
        out = assemble_action_referents(
            channel="t", chat_id="c1", user_id="rohit",
            controller=ctl, now_ts=1000.0,
        )
        self.assertIsInstance(out[0], CommitmentReferent)

    def test_stale_by_time_excluded(self):
        ctl = _Controller(_receipt(created_ts=100.0, ttl_seconds=300.0))
        out = assemble_action_referents(
            channel="t", chat_id="c1", user_id="rohit",
            controller=ctl, now_ts=1000.0,
        )
        self.assertEqual(out, ())

    def test_stale_by_turns_excluded_with_real_ordinals(self):
        # RED 10: production-derived turn age, not a direct is_fresh call.
        ctl = _Controller(_receipt(
            created_ts=990.0, ttl_turns=3, created_turn_seq=10,
        ))
        out = assemble_action_referents(
            channel="t", chat_id="c1", user_id="rohit",
            controller=ctl, now_ts=1000.0, current_turn_seq=14,
        )
        self.assertEqual(out, ())  # 4 turns since > ttl 3

    def test_turns_conservative_off_without_counter(self):
        # No ordinals -> turns freshness cannot expire the receipt;
        # time alone governs (documented conservative-off).
        ctl = _Controller(_receipt(
            created_ts=990.0, ttl_turns=0, created_turn_seq=None,
        ))
        out = assemble_action_referents(
            channel="t", chat_id="c1", user_id="rohit",
            controller=ctl, now_ts=1000.0, current_turn_seq=None,
        )
        self.assertEqual(len(out), 1)


class ProposalReferentTests(unittest.TestCase):
    def test_fresh_and_stale_windows_real_producer_shape(self):
        # The PRODUCTION shape is {id, source, shown_at} (gate round 2
        # blocker 2) -- the synthetic {kind, ts} dialect stays accepted.
        fresh = assemble_action_referents(
            channel="t", chat_id="c1", user_id="rohit",
            proposal_entry={"id": 7, "source": "dream", "shown_at": 900.0},
            now_ts=1000.0,
        )
        self.assertIsInstance(fresh[0], ProposalReferent)
        self.assertEqual(fresh[0].kind, "dream")
        stale = assemble_action_referents(
            channel="t", chat_id="c1", user_id="rohit",
            proposal_entry={"id": 7, "source": "dream", "shown_at": 100.0},
            now_ts=1000.0,
        )
        self.assertEqual(stale, ())
        legacy = assemble_action_referents(
            channel="t", chat_id="c1", user_id="rohit",
            proposal_entry={"kind": "dream", "ts": 900.0}, now_ts=1000.0,
        )
        self.assertIsInstance(legacy[0], ProposalReferent)


class AnaphoraGatingTests(unittest.TestCase):
    def test_go_ahead_without_referent_is_none(self):
        self.assertEqual(floor("Go ahead."), "none")
        self.assertEqual(floor("Yes, do it"), "none")

    def test_go_ahead_with_referent_is_explicit(self):
        ref = (CardReferent(request_id="r", action="a", status="open"),)
        self.assertEqual(floor("Go ahead.", referents=ref), "explicit_request")
        self.assertEqual(floor("Yes — proceed", referents=ref), "explicit_request")

    def test_history_prose_never_confers_authority(self):
        # F3 restated at the anaphora level: no typed referent, no intent,
        # regardless of what conversation history contains.
        self.assertEqual(floor("do it", referents=()), "none")


if __name__ == "__main__":
    unittest.main()
