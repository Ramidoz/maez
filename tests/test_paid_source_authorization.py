# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Paid-source authorization — the D1 seam-2 amendment.

Owner-authorized 2026-08-28 on implementation evidence. Three semantics
stay separate: the ACTION (what Maez is doing), the SOURCE (where
knowledge comes from), and AUTHORITY/RESOURCE POLICY (whether that
source may be consumed). Cost is NOT encoded in an action lane, and NOT
in ``egress_origin_class`` (which means provenance of outbound content).

The vocabulary gained exactly two members rather than overloading
``TRUST_SCOPE_RESTRICTED`` (a trust-scope fact) or ``PRIVACY_GATED``
(a content-sensitivity fact).
"""

from __future__ import annotations

import sqlite3
import unittest

from core.dispatcher.inventory import (
    PAID_SOURCES,
    RESERVED_SOURCES,
    InventoryRegistry,
)
from core.dispatcher.frontier_consult import FrontierReply, consult
from core.dispatcher.paid_source_grant import GrantLedger, PaidSourceGrant
from core.dispatcher.spec import (
    AvailabilityLimitation,
    ExternalSource,
    SourceAvailability,
)

_CALLER = "self_dev.propose_tests"
_OP = "d1-witness"


class _FakeReply:
    """Stands in for a TierReply so no real quota is spent."""

    text = "candidate test code"
    adapter = "claude-cli"
    model = "sonnet-x"


def _proxy_call_count() -> int:
    con = sqlite3.connect("file:memory/subscription_proxy.db?mode=ro", uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    finally:
        con.close()


class TheVocabularyAmendment(unittest.TestCase):
    def test_the_two_new_members_exist_and_are_generic(self):
        self.assertIn("AUTHORIZATION_REQUIRED", SourceAvailability.__members__)
        self.assertIn(
            "PAID_SOURCE_AUTHORIZATION_REQUIRED",
            AvailabilityLimitation.__members__,
        )
        # Generic by ruling: the STATE must not name a provider. The
        # LIMITATION carries the paid reason.
        self.assertNotIn("CLAUDE", str(SourceAvailability.AUTHORIZATION_REQUIRED))
        self.assertNotIn("FRONTIER", str(SourceAvailability.AUTHORIZATION_REQUIRED))

    def test_unknown_vocabulary_values_still_refuse(self):
        """The closed vocabulary stayed closed."""
        with self.assertRaises(ValueError):
            SourceAvailability("NOT_A_REAL_STATE")
        with self.assertRaises(ValueError):
            AvailabilityLimitation("NOT_A_REAL_LIMITATION")

    def test_frontier_consult_is_unreserved_but_paid(self):
        self.assertNotIn(
            ExternalSource.FRONTIER_CONSULT, RESERVED_SOURCES,
            "FRONTIER_CONSULT is un-reserved for the explicit caller path",
        )
        self.assertIn(
            ExternalSource.FRONTIER_CONSULT, PAID_SOURCES,
            "un-reserving must not make it free — it stays gated",
        )


class TheStateMachine(unittest.TestCase):
    def _summary(self, inv):
        r = inv.summarize([ExternalSource.FRONTIER_CONSULT])
        return (
            r.source_availability[ExternalSource.FRONTIER_CONSULT],
            list(r.availability_limitations),
        )

    def test_without_a_grant_the_source_reports_authorization_required(self):
        """REPORTING only. Enforcement is pinned in TheSpendGate --
        an availability report is not a gate."""
        inv = InventoryRegistry()
        state, lims = self._summary(inv)
        self.assertEqual(state, SourceAvailability.AUTHORIZATION_REQUIRED)
        self.assertIn(
            AvailabilityLimitation.PAID_SOURCE_AUTHORIZATION_REQUIRED, lims
        )

    def test_authorization_required_is_distinct_from_unavailable(self):
        """A gated source is NOT an absent source."""
        inv = InventoryRegistry()
        state, _ = self._summary(inv)
        for wrong in (
            SourceAvailability.EXECUTABLE_ABSENT,
            SourceAvailability.RESERVED_UNAVAILABLE,
            SourceAvailability.EXECUTABLE_UNKNOWN,
        ):
            self.assertNotEqual(
                state, wrong,
                "a source that exists and is merely ungranted must not be "
                "reported as absent, reserved or unknown",
            )

    def test_authorization_required_is_distinct_from_budget_exhausted(self):
        """Authorization and quota are SEPARATE facts (owner ruling)."""
        inv = InventoryRegistry()
        _, lims = self._summary(inv)
        self.assertNotIn(
            AvailabilityLimitation.FETCH_BUDGET_EXHAUSTED, lims,
            "a MISSING GRANT was reported as budget exhaustion — quota and "
            "authorization must never be conflated in either direction",
        )

    def test_a_valid_grant_permits_exactly_its_bounded_use(self):
        inv = InventoryRegistry()
        ledger = GrantLedger()
        import core.dispatcher.paid_source_grant as psg

        original, psg.GRANTS = psg.GRANTS, ledger
        try:
            ledger.grant(
                source=ExternalSource.FRONTIER_CONSULT,
                caller=_CALLER, operation=_OP, max_calls=1,
            )
            inv.paid_request_context = (_CALLER, _OP)
            state, _ = self._summary(inv)
            self.assertEqual(state, SourceAvailability.EXECUTABLE_PRESENT)

            ledger.consume(
                source=ExternalSource.FRONTIER_CONSULT,
                caller=_CALLER, operation=_OP,
            )
            state, lims = self._summary(inv)
            self.assertEqual(
                state, SourceAvailability.AUTHORIZATION_REQUIRED,
                "a CONSUMED one-shot grant still permitted a second call — "
                "one yes must not become unlimited spend",
            )
            self.assertIn(
                AvailabilityLimitation.PAID_SOURCE_AUTHORIZATION_REQUIRED, lims
            )
            with self.assertRaises(PermissionError):
                ledger.consume(
                    source=ExternalSource.FRONTIER_CONSULT,
                    caller=_CALLER, operation=_OP,
                )
        finally:
            psg.GRANTS = original

    def test_a_grant_is_bound_to_its_caller_and_operation(self):
        """A generic approval must not authorize a different operation."""
        ledger = GrantLedger()
        ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT,
            caller=_CALLER, operation=_OP,
        )
        self.assertFalse(
            ledger.is_authorized(
                source=ExternalSource.FRONTIER_CONSULT,
                caller="some.other.caller", operation=_OP,
            ),
            "a grant leaked to a different caller",
        )
        self.assertFalse(
            ledger.is_authorized(
                source=ExternalSource.FRONTIER_CONSULT,
                caller=_CALLER, operation="some-other-operation",
            ),
            "a grant leaked to a different operation",
        )

    def test_an_unbound_grant_cannot_be_constructed(self):
        for bad in ({"caller": "", "operation": _OP},
                    {"caller": _CALLER, "operation": "  "}):
            with self.assertRaises(ValueError):
                PaidSourceGrant(
                    grant_id="x", source=ExternalSource.FRONTIER_CONSULT,
                    max_calls=1, expires_at=9e9, **bad,
                )
        with self.assertRaises(ValueError):
            PaidSourceGrant(
                grant_id="x", source=ExternalSource.FRONTIER_CONSULT,
                caller=_CALLER, operation=_OP, max_calls=0, expires_at=9e9,
            )


class TheSpendGate(unittest.TestCase):
    """The report says AUTHORIZATION_REQUIRED; this proves it BITES."""

    def setUp(self):
        self.ledger = GrantLedger()
        self.calls = []

        import core.routing.claude_tier as ct

        self._real = ct.call
        ct.call = lambda **kw: self.calls.append(kw) or _FakeReply()
        self.addCleanup(setattr, ct, "call", self._real)

    def test_no_grant_raises_and_issues_no_call(self):
        before = _proxy_call_count()
        with self.assertRaises(PermissionError):
            consult(
                prompt="x", caller=_CALLER, operation=_OP, ledger=self.ledger
            )
        self.assertEqual(
            self.calls, [],
            "the frontier source was contacted WITHOUT a grant — the "
            "authorization report was advisory, not enforced",
        )
        self.assertEqual(before, _proxy_call_count())

    def test_a_grant_permits_exactly_one_call_then_closes(self):
        self.ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT,
            caller=_CALLER, operation=_OP, max_calls=1,
        )
        reply = consult(
            prompt="x", caller=_CALLER, operation=_OP, ledger=self.ledger
        )
        self.assertEqual(len(self.calls), 1)
        with self.assertRaises(PermissionError):
            consult(
                prompt="x", caller=_CALLER, operation=_OP, ledger=self.ledger
            )
        self.assertEqual(
            len(self.calls), 1,
            "a one-shot grant funded a SECOND frontier call",
        )
        self.assertIsInstance(reply, FrontierReply)

    def test_the_gate_is_bound_to_caller_and_operation(self):
        self.ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT,
            caller=_CALLER, operation=_OP,
        )
        for kw in ({"caller": "other.caller", "operation": _OP},
                   {"caller": _CALLER, "operation": "other-op"}):
            with self.assertRaises(PermissionError):
                consult(prompt="x", ledger=self.ledger, **kw)
        self.assertEqual(self.calls, [])

    def test_an_expired_grant_does_not_spend(self):
        clock = [1000.0]
        ledger = GrantLedger(clock=lambda: clock[0])
        ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT,
            caller=_CALLER, operation=_OP, ttl_s=60.0,
        )
        clock[0] += 61.0
        with self.assertRaises(PermissionError):
            consult(prompt="x", caller=_CALLER, operation=_OP, ledger=ledger)
        self.assertEqual(self.calls, [], "an EXPIRED grant funded a call")

    def test_the_reply_retains_adapter_model_caller_provenance(self):
        self.ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT,
            caller=_CALLER, operation=_OP,
        )
        r = consult(
            prompt="x", caller=_CALLER, operation=_OP, ledger=self.ledger
        )
        self.assertEqual(r.source, ExternalSource.FRONTIER_CONSULT)
        self.assertEqual(r.adapter, "claude-cli")
        self.assertEqual(r.model, "sonnet-x")
        self.assertEqual(r.caller, _CALLER)
        self.assertEqual(r.operation, _OP)
        self.assertTrue(r.grant_id, "the reply must name the grant that paid")


class TheZeroQuotaInvariant(unittest.TestCase):
    def test_availability_probing_consumes_no_frontier_quota(self):
        """THE critical invariant: discovering whether a source is
        affordable must never cost a call."""
        before = _proxy_call_count()
        inv = InventoryRegistry()
        for _ in range(5):
            inv.summarize([ExternalSource.FRONTIER_CONSULT])
        inv.paid_request_context = (_CALLER, _OP)
        for _ in range(5):
            inv.summarize([ExternalSource.FRONTIER_CONSULT])
        after = _proxy_call_count()
        self.assertEqual(
            before, after,
            f"availability probing issued {after - before} model "
            "completion(s). Discovering affordability must be free.",
        )


class TheConversationalBranchStaysClosed(unittest.TestCase):
    """Un-reserving the SOURCE must not open the DISPATCHER BRANCH.

    Two components now say different things about FRONTIER_CONSULT, and
    that is deliberate. ``InventoryRegistry`` reports it as a paid source
    an explicit caller may be granted. ``ExternalSourceRunner`` still
    refuses it outright on the conversational path, because a source
    Maez reaches by TALKING is not the same as one an explicit,
    grant-bound self-development operation requests.

    This is a disagreement pin, not a bug: do not "fix" it by opening
    the branch path.
    """

    def test_preflight_still_reserves_frontier_consult(self):
        import inspect

        from core.dispatcher.external_sources import ExternalFanout

        src = inspect.getsource(ExternalFanout._preflight_result)
        # The FIRST thing preflight does with FRONTIER_CONSULT must still
        # be to reserve it -- before any subject/URL branch is reached.
        head = src.split("subject_boundary_predicate")[0]
        self.assertIn("FRONTIER_CONSULT", head)
        self.assertIn(
            "_reserved_result", head,
            "the conversational branch stopped reserving FRONTIER_CONSULT — "
            "the source door was widened into the talking path",
        )

    def test_the_anticipated_refusal_reason_still_exists(self):
        """The vocabulary reserved this name before anything raised it."""
        from core.dispatcher.spec import DispatcherRefusalReason

        self.assertIn(
            "FRONTIER_CONSULT_WITHOUT_CAPABILITY_GRANT",
            DispatcherRefusalReason.__members__,
        )


class NoActionLaneSemanticsChanged(unittest.TestCase):
    def test_the_action_tier_vocabulary_is_untouched(self):
        """Cost stayed OUT of the action lanes (owner ruling)."""
        from core.actions.action_engine import ACTION_TIERS

        for name in ACTION_TIERS:
            self.assertNotIn(
                "frontier", name.lower(),
                "a frontier/paid concept entered the action tier map — "
                "cost belongs at the SOURCE boundary, not in a lane",
            )
        self.assertEqual(
            ACTION_TIERS.get("web_search"), 0,
            "an existing lane assignment changed as a side effect",
        )


if __name__ == "__main__":
    unittest.main()
