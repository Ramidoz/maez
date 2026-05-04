# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Tests for the D20 capability-acquisition orchestrator.

The audit pass on 2026-05-02 confirmed every stage-2..4 module
exists and is unit-tested, but no runtime caller wires them
together. This orchestrator is the "fires-on-felt-gap" flow:
take a felt-limitation string and walk it through:

    Stage 2  match_gap()              core/infra/capability_gap_matcher.py
    Stage 3  evaluate_matches()       core/infra/capability_evaluator.py
    Stage 4  generate_proposals()     core/infra/capability_proposal.py
    Stage 4b create pending card      core/decision/pending_cards.py

Stage 1 (autonomous gap-sensing from chat / memory / failures) is
out of scope for this slice; the orchestrator takes a string input
and assumes the producer has already detected a felt gap. A future
slice can wire chat-surface analysis or audit-failure signals into
the producer.

Stage 5 (queue → planner → activation) already has its own runtime
path via action_engine._do_capability_acquire — once the card is
created and the user approves, the existing path runs."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class _Base(unittest.TestCase):
    """Shared fixture: real manual (live docs/maez_manual/) + a
    tempfile PendingCardStore so card writes don't touch production.

    The manual fixture is intentionally the live one — we want the
    orchestrator's lexical matcher to operate against the same
    entries the daemon would see at runtime, so test-vs-production
    drift is impossible by construction."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.card_db = Path(self._tmp.name) / "pending.db"
        from core.decision.pending_cards import PendingCardStore
        self.cards = PendingCardStore(self.card_db)

    def tearDown(self):
        self._tmp.cleanup()


class HappyPath(_Base):
    def test_temporal_gap_signal_produces_match(self):
        """A felt limitation containing a temporal-arithmetic gap
        signal (the manual entry `temporal-arithmetic-at-recall`
        names "when did X happen?" as a signal) should produce
        at least one match."""
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        result = orchestrate_from_felt_limitation(
            "when did X happen?",
            pending_card_store=self.cards,
        )
        self.assertGreater(
            len(result.matches), 0,
            "matcher must surface at least one capability for the "
            "temporal-arithmetic gap signal",
        )

    def test_returns_full_pipeline_state(self):
        """OrchestrationResult must surface matches, evaluations,
        proposals, and any card request_ids — so the caller can
        log / display / debug each stage's output."""
        from core.infra.capability_orchestrator import (
            OrchestrationResult, orchestrate_from_felt_limitation,
        )
        query = "I need to compute how long after Y something happened"
        r = orchestrate_from_felt_limitation(
            query,
            pending_card_store=self.cards,
        )
        self.assertIsInstance(r, OrchestrationResult)
        self.assertIsInstance(r.matches, list)
        self.assertIsInstance(r.evaluations, list)
        self.assertIsInstance(r.proposals, list)
        self.assertIsInstance(r.cards_created, list)
        self.assertEqual(r.felt_limitation, query)
        self.assertEqual(r.stage_errors, [])


class CardCreation(_Base):
    """An eligible proposal must produce a real PendingCard whose
    action / params match `proposal.card_action_payload` exactly.
    A defer/reject proposal must NOT produce a card (consent action
    only fires on eligible decisions)."""

    def test_eligible_proposal_creates_card(self):
        """If the orchestrator generates an eligible proposal, a
        card must land in the store."""
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        # All seed manual entries are 'aspirational' so eligible-on-
        # hardware-grounds depends on hardware probe defaulting to
        # generous values when called via core.self_knowledge. To
        # guarantee at least one eligible match for this test, we
        # inject an unconstrained hardware snapshot.
        hardware = {
            "vram_available_mb": 32_000,
            "vram_total_mb": 32_000,
            "current_context_window": 32_000,
        }
        r = orchestrate_from_felt_limitation(
            "when did X happen?",
            pending_card_store=self.cards,
            hardware=hardware,
        )
        eligibles = [p for p in r.proposals if p.evaluation_decision == "eligible"]
        if not eligibles:
            self.skipTest(
                "No eligible proposal under generous hardware — "
                "manual entries may all be deprecated or have "
                "blocking covenant_touch; orchestrator behaviour "
                "still validated by the other tests"
            )
        self.assertGreater(
            len(r.cards_created), 0,
            "eligible proposal must produce a card",
        )

    def test_card_payload_links_back_to_proposal_id(self):
        """The created card's params must carry `proposal_id` so
        the queue (Stage 4b → action_engine._do_capability_acquire)
        can link the queued row back to its originating proposal."""
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        hardware = {
            "vram_available_mb": 32_000,
            "vram_total_mb": 32_000,
            "current_context_window": 32_000,
        }
        r = orchestrate_from_felt_limitation(
            "when did X happen?",
            pending_card_store=self.cards,
            hardware=hardware,
        )
        if not r.cards_created:
            self.skipTest("no card created — see test above")
        # Re-fetch the created card; verify the proposal_id link
        request_id = r.cards_created[0]
        card = self.cards.get(request_id)
        self.assertIsNotNone(card)
        params = card.params if hasattr(card, "params") else card["params"]
        self.assertIn(
            "proposal_id", params,
            "card params must carry proposal_id for queue back-link",
        )

    def test_no_card_when_store_not_provided(self):
        """If pending_card_store is None, the orchestrator returns
        proposals but creates no cards. Useful for dry-run /
        diagnostic invocations."""
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        r = orchestrate_from_felt_limitation(
            "when did X happen?",
            pending_card_store=None,
        )
        self.assertEqual(r.cards_created, [])


class EmptyAndNoMatch(_Base):
    def test_no_match_returns_empty_pipeline(self):
        """A felt limitation that doesn't lexically match any
        manual entry must walk through the pipeline cleanly and
        return empty proposals + cards. No crash."""
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        r = orchestrate_from_felt_limitation(
            "completely unrelated nonsense xyzzy plugh",
            pending_card_store=self.cards,
        )
        self.assertEqual(r.proposals, [])
        self.assertEqual(r.cards_created, [])

    def test_empty_string_safe(self):
        """Defensive: the orchestrator must not raise on empty
        input. Defers to the matcher's own empty-query handling."""
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        r = orchestrate_from_felt_limitation(
            "",
            pending_card_store=self.cards,
        )
        self.assertEqual(r.matches, [])
        self.assertEqual(r.proposals, [])


class HardwareGating(_Base):
    """If the hardware snapshot rules a match ineligible (vram
    too small, context window too narrow), the proposal generator
    will produce a 'defer' decision. Default behaviour: no card
    is created for deferred proposals."""

    def test_defer_decision_creates_no_card(self):
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        # Pinch hardware so anything with a non-trivial vram
        # requirement defers. (Seed entries may not declare vram
        # requirements — in that case eligibility is unaffected.)
        hardware = {
            "vram_available_mb": 100,
            "vram_total_mb": 200,
            "current_context_window": 1024,
        }
        r = orchestrate_from_felt_limitation(
            "when did X happen?",
            pending_card_store=self.cards,
            hardware=hardware,
        )
        # Either way, deferred proposals must NOT have produced a
        # card. Eligible ones (if any survive) may have.
        for p, request_id in zip(r.proposals, r.cards_created, strict=False):
            self.assertEqual(
                p.evaluation_decision, "eligible",
                "card must only be created for eligible decisions",
            )


class SkipPathCoverage(_Base):
    """REGRESSION GUARD: prove that the cards_skipped path correctly
    tags non-actionable proposals and consent_card_required=False
    proposals — reviewer flagged this as test-gap risk because the
    HardwareGating test could pass vacuously if no proposals were
    generated at all."""

    def _stub_proposal(
        self, capability_id, *, actionable, consent_card_required,
        evaluation_decision="defer",
    ):
        from core.infra.capability_proposal import CapabilityProposal
        return CapabilityProposal(
            proposal_id="prop-test", created_at=0.0,
            felt_limitation="x",
            capability_id=capability_id, title="t", source="manual",
            match_score=0.5, matched_signals=[], matched_terms=[],
            evaluation_decision=evaluation_decision,
            evaluation_reasons=[],
            prerequisites=[], external_prerequisites=[],
            covenant_touch="low",
            consent_card_required=consent_card_required,
            exact_phrase_ratification=False,
            manual_source_path="x", acquisition="self-dev",
            body_excerpt="", card_plain_english="",
            card_action_payload={
                "action": "capability.acquire",
                "params": {"capability_id": capability_id},
                "reason": "test", "plain_english": "test",
            },
            actionable=actionable,
        )

    def test_non_actionable_proposal_skips_with_decision_reason(self):
        from core.infra import capability_orchestrator as orch
        with mock.patch.object(orch, "match_gap", return_value=["m"]), \
             mock.patch.object(orch, "evaluate_matches", return_value=["e"]), \
             mock.patch.object(
                 orch, "generate_proposals",
                 return_value=[self._stub_proposal(
                     "cap-x", actionable=False,
                     consent_card_required=True,
                     evaluation_decision="defer",
                 )],
             ):
            r = orch.orchestrate_from_felt_limitation(
                "any", pending_card_store=self.cards,
            )
        self.assertEqual(r.cards_created, [])
        self.assertEqual(len(r.cards_skipped), 1)
        cap_id, reason = r.cards_skipped[0]
        self.assertEqual(cap_id, "cap-x")
        self.assertIn("non-actionable", reason)
        self.assertIn("defer", reason)

    def test_consent_not_required_skips_with_named_reason(self):
        from core.infra import capability_orchestrator as orch
        with mock.patch.object(orch, "match_gap", return_value=["m"]), \
             mock.patch.object(orch, "evaluate_matches", return_value=["e"]), \
             mock.patch.object(
                 orch, "generate_proposals",
                 return_value=[self._stub_proposal(
                     "cap-y", actionable=True,
                     consent_card_required=False,
                     evaluation_decision="eligible",
                 )],
             ):
            r = orch.orchestrate_from_felt_limitation(
                "any", pending_card_store=self.cards,
            )
        self.assertEqual(r.cards_created, [])
        self.assertEqual(len(r.cards_skipped), 1)
        cap_id, reason = r.cards_skipped[0]
        self.assertEqual(cap_id, "cap-y")
        self.assertEqual(reason, "consent_card_required=False")


class SupersessionDefault(_Base):
    """REGRESSION GUARD for reviewer Major: chat_id=None at the CLI
    layer disables PendingCardStore.create_card's supersession SQL
    (pending_cards.py:354), so two back-to-back operator runs would
    stack two open cards for the same capability. The orchestrator
    pins a synthetic source as effective_chat_id so successive runs
    supersede correctly."""

    def test_two_runs_same_source_supersede(self):
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        hardware = {
            "vram_available_mb": 32_000,
            "vram_total_mb": 32_000,
            "current_context_window": 32_000,
        }
        r1 = orchestrate_from_felt_limitation(
            "when did X happen?",
            pending_card_store=self.cards, hardware=hardware,
        )
        if not r1.cards_created:
            self.skipTest("manual yielded no eligible proposal")
        # Second run is for its supersession side-effect on the cards
        # store; we don't read the result tuple itself.
        orchestrate_from_felt_limitation(
            "when did X happen?",
            pending_card_store=self.cards, hardware=hardware,
        )
        # Both runs should have produced fresh cards but the prior
        # run's cards must now be superseded (status != 'open').
        from core.decision.pending_cards import CardStatus
        for prior_rid in r1.cards_created:
            prior = self.cards.get(prior_rid)
            self.assertNotEqual(
                prior.status, CardStatus.OPEN.value,
                f"prior card {prior_rid} should be superseded after "
                "second orchestrate run with same source",
            )


class IntegrationContract(_Base):
    """The orchestrator's contract with the rest of the system —
    these tests pin the shape so a future refactor doesn't silently
    break the queue / action_engine handoff."""

    def test_card_action_is_capability_acquire(self):
        """The action_engine handler `_do_capability_acquire` is
        the only consumer of these cards. Action must match
        exactly."""
        from core.infra.capability_orchestrator import (
            orchestrate_from_felt_limitation,
        )
        hardware = {
            "vram_available_mb": 32_000,
            "vram_total_mb": 32_000,
            "current_context_window": 32_000,
        }
        r = orchestrate_from_felt_limitation(
            "when did X happen?",
            pending_card_store=self.cards,
            hardware=hardware,
        )
        if not r.cards_created:
            self.skipTest("no card created")
        card = self.cards.get(r.cards_created[0])
        action = card.action if hasattr(card, "action") else card["action"]
        self.assertEqual(action, "capability.acquire")


if __name__ == "__main__":
    unittest.main()
