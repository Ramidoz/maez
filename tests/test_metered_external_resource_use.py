# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The `metered_external_resource_use` S7 work class.

Owner-authorized closed-vocabulary amendment, 2026-08-28 (D1 seam 2).

    Non-mutating consumption of a scarce/metered external resource
    controlled by the bonded owner, where use requires explicit bounded
    owner authorization.

THREE THINGS STAY SEPARATE and this file exists to keep them apart:

    ACTION       what Maez is doing              (self_dev.propose_tests)
    SOURCE       where knowledge comes from      (FRONTIER_CONSULT)
    WORK CLASS   what human permission consuming (metered_external_
                 that source requires             resource_use)

The class is NOT S7.3 WebAuthn-guarded. That does not mean unapproved:
the ceremony for this class is an authenticated owner card whose
resolution mints a bounded, durable, atomically consumable grant.
"""

from __future__ import annotations

import multiprocessing as mp
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from core.decision.pending_cards import CardStatus, PendingCardStore
from core.dispatcher import frontier_grant as fg
from core.dispatcher.spec import ExternalSource
from core.governance import operator_user_boundary as s7

CLASS = "metered_external_resource_use"
OPERATION = "self_dev.propose_tests"
PURPOSE = {"question": "propose tests for the recorder seam"}


def _envelope(**over):
    env = {
        "source": "FRONTIER_CONSULT",
        "operation": OPERATION,
        "purpose_hash": fg.purpose_hash(PURPOSE),
        "max_calls": 1,
        "expires_at": time.time() + 900,
        "model": None,
    }
    env.update(over)
    return env


class _StoreCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(dir="/var/tmp", prefix="d1_meter_")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = PendingCardStore(Path(self.dir) / "cards.db")

    def _approved_card(self, **over):
        card = fg.request_authorization(
            source=ExternalSource.FRONTIER_CONSULT,
            operation=OPERATION,
            purpose=PURPOSE,
            plain_english="Consult the frontier model for candidate tests.",
            store=self.store,
            **over,
        )
        self.store.approve(
            card.request_id, user_id="rohit", via="text_reply",
            current_state_fields=card.params,
        )
        return card


# ---- 1. the vocabulary member itself -------------------------------- #

class TheClosedVocabularyMember(unittest.TestCase):
    def test_1_is_a_recognized_closed_vocabulary_member(self):
        self.assertIn(CLASS, s7.WORK_CLASSES)
        self.assertEqual(s7.validate_work_class(CLASS), CLASS)

    def test_the_vocabulary_is_still_closed(self):
        with self.assertRaises(ValueError):
            s7.validate_work_class("metered_external_resource_abuse")

    def test_7_the_class_cannot_enter_the_direct_ungated_allowlist(self):
        """_NON_GUARDED_DIRECT_ACTIONS is routine, unpaid, read-only
        custody. Spending the owner's quota is not routine custody, and
        must never become directly ungated."""
        self.assertNotIn(CLASS, s7._NON_GUARDED_DIRECT_ACTIONS)
        self.assertNotIn(
            s7.METERED_CONSUMPTION_ACTION, s7._NON_GUARDED_DIRECT_ACTIONS,
            "the metered consumption action became directly ungated",
        )
        for op in s7.NON_MUTATING_METERED_OPERATIONS:
            self.assertNotIn(
                op, s7._NON_GUARDED_DIRECT_ACTIONS,
                f"{op} became routine custody by being named non-mutating "
                "— those are different claims",
            )

    def test_8_no_webauthn_ceremony_is_required_for_this_class(self):
        self.assertNotIn(
            CLASS, s7.GUARDED_WORK_CLASSES,
            "consuming a metered resource does not remake Maez and must "
            "not demand the S7.3 hardware ceremony",
        )

    def test_the_self_modification_voice_seat_is_not_widened(self):
        """This consultation does not remake Maez, so it must not convene
        Maez's self-modification voice ceremony."""
        self.assertNotIn(CLASS, s7.VOICE_SEAT_WORK_CLASSES)
        self.assertEqual(
            s7.VOICE_SEAT_WORK_CLASSES,
            frozenset({
                "self_modification", "covenant_touching_change",
                "capability_acquisition",
                "autonomy_lowering_or_protection_reducing",
            }),
        )


# ---- derivation ------------------------------------------------------ #

class TheDerivation(unittest.TestCase):
    def _derive(self, action, params=None, claimed=None):
        return s7.derive_work_class(
            action=action, params=params or {}, claimed_work_class=claimed
        )

    def test_3_a_qualifying_request_derives_the_class_mechanically(self):
        self.assertEqual(
            self._derive(s7.METERED_CONSUMPTION_ACTION, _envelope()), CLASS
        )

    def test_2_a_caller_cannot_claim_the_class_to_obtain_authority(self):
        """derive_work_class reads action material, never the caller's
        word about what it is doing."""
        for action, params in (
            ("edit_soul_section", {}),
            ("capability.acquire", {}),
            ("some_unknown_action", {}),
        ):
            got = self._derive(action, params, claimed=CLASS)
            self.assertNotEqual(
                got, CLASS,
                f"{action} obtained {CLASS} merely by claiming it",
            )

    def test_the_source_policy_decides_what_is_metered(self):
        """A caller cannot make a free source paid, nor a paid one free,
        by naming it differently."""
        self.assertNotEqual(
            self._derive(s7.METERED_CONSUMPTION_ACTION,
                         _envelope(source="WEB_SEARCH")), CLASS,
            "a FREE source derived the metered class",
        )
        self.assertNotEqual(
            self._derive(s7.METERED_CONSUMPTION_ACTION,
                         _envelope(source="NOT_A_SOURCE")), CLASS,
        )

    def test_only_registered_non_mutating_operations_qualify(self):
        for op in ("run_shell", "edit_soul_section", "", None):
            self.assertNotEqual(
                self._derive(s7.METERED_CONSUMPTION_ACTION,
                             _envelope(operation=op)), CLASS,
                f"unregistered operation {op!r} derived the class",
            )

    def test_unproven_requests_fail_closed(self):
        self.assertEqual(
            self._derive(s7.METERED_CONSUMPTION_ACTION, {}),
            "undeterminable_work_class",
        )

    def test_4_an_unrelated_non_mutating_local_action_does_not_derive_it(self):
        for action in ("read_file", "search_files", "web_search",
                       "quote_stock", OPERATION):
            self.assertNotEqual(
                self._derive(action, {}), CLASS,
                f"{action} derived a metered-consumption class without "
                "requesting a metered source",
            )

    def test_5_capability_acquisition_is_unchanged(self):
        """Installing or enabling a NEW provider is not using one."""
        self.assertEqual(self._derive("capability.acquire", {}),
                         "capability_acquisition")
        self.assertEqual(
            self._derive("capability.acquire", _envelope()),
            "capability_acquisition",
            "a consumption envelope weakened a capability acquisition",
        )

    def test_6_substrate_mutation_still_derives_self_modification(self):
        for action in ("write_soul_note", "edit_soul_section"):
            self.assertEqual(self._derive(action, {}), "self_modification")

    def test_12_a_mutation_cannot_inherit_consultation_authority(self):
        """Each subsequent act is reclassified independently. Carrying the
        consultation envelope into a mutating action must not launder the
        mutation into the weaker class."""
        for action, expected in (
            ("edit_soul_section", "self_modification"),
            ("write_soul_note", "self_modification"),
            ("capability.acquire", "capability_acquisition"),
        ):
            self.assertEqual(
                self._derive(action, _envelope()), expected,
                f"{action} inherited the weaker consultation class",
            )

    def test_stronger_substrate_classes_win_inside_the_envelope(self):
        """If a consumption envelope somehow carries covenant or self-mod
        material, the stronger class must win."""
        env = _envelope(purpose_hash="core/soul/covenant.md")
        got = self._derive(s7.METERED_CONSUMPTION_ACTION, env)
        if got != CLASS:
            self.assertIn(got, s7.GUARDED_WORK_CLASSES)


# ---- the card-backed grant ------------------------------------------ #

def _child_consume(db, card_id, q):
    from core.decision.pending_cards import PendingCardStore as PCS
    from core.dispatcher import frontier_grant as g
    from core.dispatcher.spec import ExternalSource as ES

    try:
        g.consume(card_id=card_id, source=ES.FRONTIER_CONSULT,
                  operation=OPERATION, purpose=PURPOSE, model=None,
                  store=PCS(db))
        q.put("WON")
    except Exception:
        q.put("refused")


class TheAuthorityBearingGrant(_StoreCase):
    def test_10_owner_approval_creates_an_authority_bearing_grant(self):
        card = self._approved_card()
        grant = fg.consume(
            card_id=card.request_id, source=ExternalSource.FRONTIER_CONSULT,
            operation=OPERATION, purpose=PURPOSE, store=self.store,
        )
        self.assertEqual(grant.owner_user_id, "rohit")
        self.assertEqual(grant.owner_decision_via, "text_reply")
        self.assertTrue(grant.owner_decision_at)
        self.assertEqual(grant.card_id, card.request_id)
        self.assertEqual(grant.purpose_hash, fg.purpose_hash(PURPOSE))

    def test_an_unapproved_card_authorizes_nothing(self):
        card = fg.request_authorization(
            source=ExternalSource.FRONTIER_CONSULT, operation=OPERATION,
            purpose=PURPOSE, plain_english="x", store=self.store,
        )
        self.assertEqual(card.status, CardStatus.OPEN.value)
        with self.assertRaises(fg.GrantRefused):
            fg.consume(card_id=card.request_id,
                       source=ExternalSource.FRONTIER_CONSULT,
                       operation=OPERATION, purpose=PURPOSE, store=self.store)

    def test_changing_any_binding_invalidates_use(self):
        card = self._approved_card()
        for over in (
            {"operation": "run_shell"},
            {"purpose": {"question": "a different question"}},
            {"model": "opus"},
        ):
            kw = dict(card_id=card.request_id,
                      source=ExternalSource.FRONTIER_CONSULT,
                      operation=OPERATION, purpose=PURPOSE, store=self.store)
            kw.update(over)
            with self.assertRaises(
                (fg.GrantRefused, PermissionError), msg=f"accepted {over}"
            ):
                fg.consume(**kw)
        # and the card is still unspent
        self.assertEqual(
            self.store.get(card.request_id).status, CardStatus.APPROVED.value
        )

    def test_an_expired_card_cannot_consume(self):
        card = self._approved_card(ttl_s=1.0)
        with self.assertRaises(fg.GrantRefused):
            fg.consume(card_id=card.request_id,
                       source=ExternalSource.FRONTIER_CONSULT,
                       operation=OPERATION, purpose=PURPOSE,
                       store=self.store, now=time.time() + 3600)

    def test_a_caller_cannot_mint_a_grant_directly(self):
        """There is no mint-your-own path: authority only comes from an
        owner-resolved card."""
        self.assertFalse(
            [n for n in dir(fg) if n in ("grant", "mint", "authorize")],
            "frontier_grant grew a direct grant-minting entry point",
        )
        with self.assertRaises(fg.GrantRefused):
            fg.request_authorization(
                source=ExternalSource.FRONTIER_CONSULT, operation="run_shell",
                purpose=PURPOSE, plain_english="x", store=self.store,
            )

    def test_11_cross_process_one_shot_consumes_exactly_once(self):
        card = self._approved_card()
        db = str(self.store.db_path)
        ctx = mp.get_context("fork")
        q = ctx.Queue()
        ps = [ctx.Process(target=_child_consume, args=(db, card.request_id, q))
              for _ in range(12)]
        [p.start() for p in ps]
        [p.join() for p in ps]
        out = [q.get() for _ in range(12)]
        self.assertEqual(
            out.count("WON"), 1,
            f"{out.count('WON')} of 12 REAL PROCESSES each spent the same "
            "one-shot authorization",
        )

    def test_a_failed_attempt_is_not_refunded(self):
        card = self._approved_card()
        fg.consume(card_id=card.request_id,
                   source=ExternalSource.FRONTIER_CONSULT,
                   operation=OPERATION, purpose=PURPOSE, store=self.store)
        fg.settle(card_id=card.request_id, ok=False,
                  detail="frontier timed out", store=self.store)
        with self.assertRaises(fg.GrantRefused):
            fg.consume(card_id=card.request_id,
                       source=ExternalSource.FRONTIER_CONSULT,
                       operation=OPERATION, purpose=PURPOSE, store=self.store)

    def test_d1_grants_are_one_shot_not_standing(self):
        self.assertEqual(
            fg.MAX_CALLS, 1,
            "standing allowances are not authorized for D1",
        )


# ---- the spend gate, end to end ------------------------------------- #

class TheSpendGateUnderRealAuthority(_StoreCase):
    def setUp(self):
        super().setUp()
        self.calls = []
        import core.routing.claude_tier as ct
        from core.routing.claude_tier import TierReply

        real = ct.call
        ct.call = lambda **kw: (
            self.calls.append(kw),
            TierReply(reply="candidate tests", model_used="claude-sonnet-x",
                      input_tokens=5, output_tokens=7, raw={}),
        )[1]
        self.addCleanup(setattr, ct, "call", real)

    def test_9_no_valid_card_means_zero_frontier_completion_calls(self):
        from core.dispatcher.frontier_consult import consult

        card = fg.request_authorization(       # created, NEVER approved
            source=ExternalSource.FRONTIER_CONSULT, operation=OPERATION,
            purpose=PURPOSE, plain_english="x", store=self.store,
        )
        for card_id in (card.request_id, "no-such-card"):
            with self.assertRaises(fg.GrantRefused):
                consult(prompt="x", card_id=card_id, operation=OPERATION,
                        purpose=PURPOSE, store=self.store)
        self.assertEqual(
            self.calls, [],
            "the frontier was contacted without an owner-approved card",
        )

    def test_an_approved_card_permits_exactly_one_consultation(self):
        from core.dispatcher.frontier_consult import consult

        card = self._approved_card()
        reply = consult(prompt="x", card_id=card.request_id,
                        operation=OPERATION, purpose=PURPOSE, store=self.store)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(reply.text, "candidate tests")
        self.assertEqual(reply.model, "claude-sonnet-x")
        self.assertEqual(reply.owner_user_id, "rohit")
        self.assertEqual(reply.source, ExternalSource.FRONTIER_CONSULT)
        with self.assertRaises(fg.GrantRefused):
            consult(prompt="x", card_id=card.request_id,
                    operation=OPERATION, purpose=PURPOSE, store=self.store)
        self.assertEqual(
            len(self.calls), 1, "one owner decision funded a SECOND call"
        )

    def test_the_obsolete_injectable_ledger_seam_is_gone(self):
        """A forged in-process ledger once satisfied the gate."""
        import inspect

        from core.dispatcher.frontier_consult import consult

        self.assertNotIn(
            "ledger", inspect.signature(consult).parameters,
            "the injectable ledger seam came back — a forged object could "
            "satisfy the gate without any owner decision",
        )


if __name__ == "__main__":
    unittest.main()
