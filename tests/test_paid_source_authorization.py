# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Paid-source authorization — the D1 seam-2 amendment.

Owner-authorized 2026-08-28. Three semantics stay separate: the ACTION
(what Maez is doing), the SOURCE (where knowledge comes from), and
AUTHORITY/RESOURCE POLICY (whether that source may be spent). Cost is
NOT encoded in an action lane and NOT in ``egress_origin_class``.

THE INVARIANT THIS FILE EXISTS TO DEFEND:

    No Maez-originated frontier consultation reaches claude_tier unless
    a bounded grant has already been consumed at frontier_consult.

Builder/eval/operator tooling has a different authority class and is
deliberately out of scope -- see TheBuilderPathStaysSeparate.
"""

from __future__ import annotations

import socket
import sqlite3
import threading
import time
import unittest
from pathlib import Path

from core.dispatcher.frontier_consult import FrontierReply, consult
from core.dispatcher.inventory import (
    PAID_SOURCES,
    RESERVED_SOURCES,
    InventoryRegistry,
)
from core.dispatcher.paid_source_grant import GrantLedger, PaidSourceGrant
from core.dispatcher.spec import (
    AvailabilityLimitation,
    ExternalSource,
    SourceAvailability,
)
from core.routing.claude_tier import TierReply

_CALLER = "self_dev.propose_tests"
_OP = "d1-witness"


def _reply() -> TierReply:
    """A REAL TierReply. Binding the test to the production dataclass is
    the point: an earlier version used a hand-written fake that mirrored
    field names the wire never had, so the provenance pin validated an
    invention. If these fields are renamed, this breaks loudly."""
    return TierReply(
        reply="candidate test code",
        model_used="claude-sonnet-x",
        input_tokens=11,
        output_tokens=22,
        raw={},
    )


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
        # The STATE must not name a provider; the LIMITATION carries the
        # paid reason.
        for banned in ("CLAUDE", "FRONTIER", "ANTHROPIC"):
            self.assertNotIn(banned, str(SourceAvailability.AUTHORIZATION_REQUIRED))

    def test_unknown_vocabulary_values_still_refuse(self):
        with self.assertRaises(ValueError):
            SourceAvailability("NOT_A_REAL_STATE")
        with self.assertRaises(ValueError):
            AvailabilityLimitation("NOT_A_REAL_LIMITATION")

    def test_frontier_consult_is_unreserved_but_paid(self):
        self.assertNotIn(ExternalSource.FRONTIER_CONSULT, RESERVED_SOURCES)
        self.assertIn(
            ExternalSource.FRONTIER_CONSULT, PAID_SOURCES,
            "un-reserving must not make it free — it stays gated",
        )


class OrdinaryCognitionIsUnaffected(unittest.TestCase):
    """The regression that mattered most.

    Un-reserving the source made every dispatcher turn probe a socket and
    inherit PAID_SOURCE_AUTHORIZATION_REQUIRED, because the brain
    inventories ALL sources each turn and Layer 0 copies every
    limitation. Without a paid context the source must look exactly as it
    did before paid sources existed.
    """

    def test_a_context_free_summary_reports_reserved(self):
        r = InventoryRegistry().summarize([ExternalSource.FRONTIER_CONSULT])
        self.assertEqual(
            r.source_availability[ExternalSource.FRONTIER_CONSULT],
            SourceAvailability.RESERVED_UNAVAILABLE,
        )

    def test_no_paid_limitation_leaks_into_an_ordinary_turn(self):
        r = InventoryRegistry().summarize([ExternalSource.FRONTIER_CONSULT])
        self.assertNotIn(
            AvailabilityLimitation.PAID_SOURCE_AUTHORIZATION_REQUIRED,
            r.availability_limitations,
            "every ordinary turn inherited a limitation about a source it "
            "never asked for",
        )

    def test_a_context_free_summary_opens_no_socket(self):
        """A hung proxy would otherwise add 1.5s to EVERY turn."""
        calls = []
        real = socket.create_connection
        socket.create_connection = lambda *a, **k: calls.append(a) or real(*a, **k)
        try:
            InventoryRegistry().summarize([ExternalSource.FRONTIER_CONSULT])
        finally:
            socket.create_connection = real
        self.assertEqual(
            calls, [], "an ordinary turn probed the paid proxy over the network"
        )


class TheStateMachine(unittest.TestCase):
    def setUp(self):
        self.ledger = GrantLedger()
        import core.dispatcher.paid_source_grant as psg

        self._orig, psg.GRANTS = psg.GRANTS, self.ledger
        self.addCleanup(setattr, psg, "GRANTS", self._orig)

    def _grant(self):
        self.ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT, caller=_CALLER, operation=_OP
        )

    def _reachable(self):
        real = socket.create_connection

        class _S:
            def __enter__(s): return s
            def __exit__(s, *a): return False

        socket.create_connection = lambda *a, **k: _S()
        self.addCleanup(setattr, socket, "create_connection", real)

    def _with_budget(self, value=None, *, raises=None):
        """Stub claude_tier.budget -- the DEPENDENCY -- so a mutation to
        _paid_source_budget cannot be masked by its own stub."""
        import core.routing.claude_tier as ct

        real = ct.budget

        def fake(*a, **k):
            if raises is not None:
                raise raises
            return value

        ct.budget = fake
        self.addCleanup(setattr, ct, "budget", real)

    def _state(self, inv=None, ctx=(_CALLER, _OP)):
        inv = inv or InventoryRegistry()
        r = inv.summarize([ExternalSource.FRONTIER_CONSULT], paid_context=ctx)
        return (
            r.source_availability[ExternalSource.FRONTIER_CONSULT],
            list(r.availability_limitations),
        )

    def test_named_caller_without_a_grant_gets_authorization_required(self):
        """REPORTING only. Enforcement is pinned in TheSpendGate."""
        state, lims = self._state()
        self.assertEqual(state, SourceAvailability.AUTHORIZATION_REQUIRED)
        self.assertIn(
            AvailabilityLimitation.PAID_SOURCE_AUTHORIZATION_REQUIRED, lims
        )

    def test_authorization_required_is_distinct_from_unavailable(self):
        state, _ = self._state()
        for wrong in (
            SourceAvailability.EXECUTABLE_ABSENT,
            SourceAvailability.RESERVED_UNAVAILABLE,
            SourceAvailability.EXECUTABLE_UNKNOWN,
        ):
            self.assertNotEqual(state, wrong)

    def test_authorization_required_is_distinct_from_budget_exhausted(self):
        _, lims = self._state()
        self.assertNotIn(
            AvailabilityLimitation.FETCH_BUDGET_EXHAUSTED, lims,
            "a MISSING GRANT was reported as budget exhaustion",
        )

    def _with_socket(self, exc):
        """Stub the SOCKET, never _paid_source_reachable itself.

        Stubbing the method under test is how a mutation to that method
        survives its own test: the stub replaces the mutant.
        """
        real = socket.create_connection

        def fake(*a, **k):
            raise exc

        socket.create_connection = fake
        self.addCleanup(setattr, socket, "create_connection", real)

    def test_reachability_is_decided_before_authorization(self):
        """A down proxy is not an authorization problem."""
        self._with_socket(ConnectionRefusedError())
        state, lims = self._state()
        self.assertEqual(state, SourceAvailability.EXECUTABLE_ABSENT)
        self.assertIn(AvailabilityLimitation.FRESH_ATTEMPT_FAILED, lims)
        self.assertNotIn(
            AvailabilityLimitation.PAID_SOURCE_AUTHORIZATION_REQUIRED, lims,
            "an UNREACHABLE proxy was reported as an authorization problem",
        )

    def test_a_hung_proxy_is_timed_out_not_absent(self):
        """Listening-but-not-accepting is the case that costs 1.5s. It is
        a different fact from 'refused' and must not be flattened into
        it."""
        self._with_socket(socket.timeout())
        state, lims = self._state()
        self.assertEqual(
            state, SourceAvailability.TIMED_OUT,
            "a HUNG proxy was reported as ABSENT — a timeout and a "
            "refusal are different facts",
        )
        self.assertIn(AvailabilityLimitation.SOURCE_TIMEOUT, lims)

    def test_unknown_budget_is_not_reported_as_exhausted(self):
        """can_afford() fails closed to False on ANY read error, so using
        it here would report an unreadable proxy as an exhausted budget."""
        self._grant()
        self._reachable()
        self._with_budget(raises=RuntimeError("proxy unreadable"))
        state, lims = self._state()
        self.assertEqual(state, SourceAvailability.EXECUTABLE_UNKNOWN)
        self.assertNotIn(
            AvailabilityLimitation.FETCH_BUDGET_EXHAUSTED, lims,
            "an UNREADABLE budget was reported as an EXHAUSTED one",
        )

    def test_exhausted_budget_is_reported_only_after_authorization(self):
        self._grant()
        self._reachable()
        self._with_budget({"claude": {"hourly_remaining": 0, "daily_remaining": 0}})
        state, lims = self._state()
        self.assertEqual(state, SourceAvailability.EXECUTABLE_ABSENT)
        self.assertIn(AvailabilityLimitation.FETCH_BUDGET_EXHAUSTED, lims)

    def test_a_valid_grant_reports_present(self):
        self._grant()
        self._reachable()
        self._with_budget({"claude": {"hourly_remaining": 9, "daily_remaining": 9}})
        state, _ = self._state()
        self.assertEqual(state, SourceAvailability.EXECUTABLE_PRESENT)

    def test_context_is_per_call_not_registry_state(self):
        """Instance state here was a real race: one request could install
        its context, pause in the probe, and have another request's
        authorized context answer for it."""
        self.assertFalse(
            hasattr(InventoryRegistry(), "paid_request_context"),
            "paid context is back on the registry as mutable shared state",
        )


class TheGrantLedger(unittest.TestCase):
    def test_a_grant_is_bound_to_source_caller_and_operation(self):
        ledger = GrantLedger()
        ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT, caller=_CALLER, operation=_OP
        )
        for kw in (
            {"source": ExternalSource.WEB_SEARCH, "caller": _CALLER, "operation": _OP},
            {"source": ExternalSource.FRONTIER_CONSULT, "caller": "x", "operation": _OP},
            {"source": ExternalSource.FRONTIER_CONSULT, "caller": _CALLER, "operation": "x"},
        ):
            self.assertFalse(
                ledger.is_authorized(**kw), f"a grant leaked across {kw}"
            )

    def test_a_grant_for_another_source_cannot_fund_frontier(self):
        """Drop the source predicate and every same-source test still
        passes -- this is the one that catches it."""
        ledger = GrantLedger()
        ledger.grant(
            source=ExternalSource.WEB_SEARCH, caller=_CALLER, operation=_OP
        )
        self.assertFalse(
            ledger.is_authorized(
                source=ExternalSource.FRONTIER_CONSULT,
                caller=_CALLER, operation=_OP,
            ),
            "a WEB_SEARCH grant funded a FRONTIER_CONSULT consultation",
        )
        with self.assertRaises(PermissionError):
            ledger.consume(
                source=ExternalSource.FRONTIER_CONSULT,
                caller=_CALLER, operation=_OP,
            )

    def test_an_unbound_or_unbounded_grant_cannot_be_constructed(self):
        base = dict(
            grant_id="x", source=ExternalSource.FRONTIER_CONSULT,
            caller=_CALLER, operation=_OP, max_calls=1, expires_at=9e9,
        )
        for bad in ({"caller": ""}, {"operation": "  "}, {"max_calls": 0},
                    {"expires_at": float("inf")}):
            with self.assertRaises(ValueError, msg=f"accepted {bad}"):
                PaidSourceGrant(**{**base, **bad})

    def test_remaining_reports_zero_for_an_expired_grant(self):
        clock = [1000.0]
        ledger = GrantLedger(clock=lambda: clock[0])
        g = ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT, caller=_CALLER,
            operation=_OP, max_calls=3, ttl_s=60.0,
        )
        self.assertEqual(ledger.remaining(g.grant_id), 3)
        clock[0] += 61.0
        self.assertEqual(
            ledger.remaining(g.grant_id), 0,
            "an EXPIRED grant still advertised unused calls — the ledger "
            "disagreed with itself",
        )

    def test_concurrent_consumers_cannot_overspend_one_grant(self):
        ledger = GrantLedger()
        ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT, caller=_CALLER,
            operation=_OP, max_calls=1,
        )
        wins, barrier = [], threading.Barrier(8)

        # Widen the critical section so an unlocked ledger ACTUALLY
        # interleaves. Without this the GIL hides the race and the test
        # passes even with the lock removed.
        real_live = GrantLedger._live_grant

        def slow_live(self, *a, **k):
            out = real_live(self, *a, **k)
            time.sleep(0.02)
            return out

        GrantLedger._live_grant = slow_live
        self.addCleanup(setattr, GrantLedger, "_live_grant", real_live)

        def race():
            barrier.wait()
            try:
                ledger.consume(
                    source=ExternalSource.FRONTIER_CONSULT,
                    caller=_CALLER, operation=_OP,
                )
                wins.append(1)
            except PermissionError:
                pass

        ts = [threading.Thread(target=race) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(
            len(wins), 1, f"{len(wins)} threads each spent a one-shot grant"
        )

    def test_the_process_local_limit_is_documented_not_hidden(self):
        """Grants do not cross processes. A fork after granting lets each
        child consume the same one-shot grant. That is a real limit and
        must stay stated rather than implied."""
        import core.dispatcher.paid_source_grant as psg

        self.assertIn("process-local", (psg.__doc__ or "").lower() + (
            psg.GrantLedger.__doc__ or "").lower())


class TheSpendGate(unittest.TestCase):
    """The report says AUTHORIZATION_REQUIRED; this proves it BITES."""

    def setUp(self):
        self.ledger = GrantLedger()
        self.calls = []
        import core.routing.claude_tier as ct

        real = ct.call
        ct.call = lambda **kw: (self.calls.append(kw), _reply())[1]
        self.addCleanup(setattr, ct, "call", real)

    def test_no_grant_raises_and_issues_no_call(self):
        before = _proxy_call_count()
        with self.assertRaises(PermissionError):
            consult(prompt="x", caller=_CALLER, operation=_OP, ledger=self.ledger)
        self.assertEqual(
            self.calls, [],
            "the frontier source was contacted WITHOUT a grant — the "
            "authorization report was advisory, not enforced",
        )
        self.assertEqual(before, _proxy_call_count())

    def test_a_grant_permits_exactly_one_call_then_closes(self):
        self.ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT, caller=_CALLER,
            operation=_OP, max_calls=1,
        )
        reply = consult(
            prompt="x", caller=_CALLER, operation=_OP, ledger=self.ledger
        )
        self.assertIsInstance(reply, FrontierReply)
        self.assertEqual(len(self.calls), 1)
        with self.assertRaises(PermissionError):
            consult(prompt="x", caller=_CALLER, operation=_OP, ledger=self.ledger)
        self.assertEqual(
            len(self.calls), 1, "a one-shot grant funded a SECOND frontier call"
        )

    def test_the_gate_is_bound_to_caller_and_operation(self):
        self.ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT, caller=_CALLER, operation=_OP
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
            source=ExternalSource.FRONTIER_CONSULT, caller=_CALLER,
            operation=_OP, ttl_s=60.0,
        )
        clock[0] += 61.0
        with self.assertRaises(PermissionError):
            consult(prompt="x", caller=_CALLER, operation=_OP, ledger=ledger)
        self.assertEqual(self.calls, [], "an EXPIRED grant funded a call")

    def test_the_reply_retains_real_model_and_caller_provenance(self):
        self.ledger.grant(
            source=ExternalSource.FRONTIER_CONSULT, caller=_CALLER, operation=_OP
        )
        r = consult(prompt="x", caller=_CALLER, operation=_OP, ledger=self.ledger)
        self.assertEqual(r.source, ExternalSource.FRONTIER_CONSULT)
        self.assertEqual(r.text, "candidate test code")
        self.assertEqual(
            r.model, "claude-sonnet-x",
            "provenance must carry the model the proxy ACTUALLY used",
        )
        self.assertEqual(r.caller, _CALLER)
        self.assertEqual(r.operation, _OP)
        self.assertTrue(r.grant_id, "the reply must name the grant that paid")
        self.assertEqual((r.input_tokens, r.output_tokens), (11, 22))


class TheConversationalBranchStaysClosed(unittest.TestCase):
    """Un-reserving the SOURCE must not open the DISPATCHER BRANCH.

    Two components deliberately answer different questions:
      InventoryRegistry -- "may an explicitly authorized substrate caller
                            consume this source?"
      ExternalFanout    -- "may ordinary cognition generically CHOOSE it?"

    The second answer stays no. This is a disagreement pin, not a bug: do
    not "fix" it until an epistemic-help/source-selection arc
    intentionally activates generic consultation.
    """

    def test_preflight_still_reserves_frontier_consult(self):
        import inspect

        from core.dispatcher.external_sources import ExternalFanout

        src = inspect.getsource(ExternalFanout._preflight_result)
        head = src.split("subject_boundary_predicate")[0]
        self.assertIn("FRONTIER_CONSULT", head)
        self.assertIn(
            "_reserved_result", head,
            "the conversational branch stopped reserving FRONTIER_CONSULT — "
            "the source door was widened into the talking path",
        )

    def test_the_anticipated_refusal_reason_still_exists(self):
        from core.dispatcher.spec import DispatcherRefusalReason

        self.assertIn(
            "FRONTIER_CONSULT_WITHOUT_CAPABILITY_GRANT",
            DispatcherRefusalReason.__members__,
        )


class TheBuilderPathStaysSeparate(unittest.TestCase):
    def test_claude_tier_is_not_globally_gated(self):
        """Builder/eval/operator tooling spends Rohit's quota under a
        DIFFERENT authority class. Gating claude_tier globally would
        break it and would conflate two unrelated semantics."""
        import inspect

        from core.routing import claude_tier

        src = inspect.getsource(claude_tier.call)
        for leak in ("paid_source_grant", "GRANTS", "is_authorized"):
            self.assertNotIn(
                leak, src,
                "claude_tier.call grew a global grant gate — builder "
                "tooling and Maez-originated consultation are separate "
                "authority classes",
            )


class TheZeroQuotaInvariant(unittest.TestCase):
    def test_availability_probing_consumes_no_frontier_quota(self):
        before = _proxy_call_count()
        ledger = GrantLedger()
        import core.dispatcher.paid_source_grant as psg

        orig, psg.GRANTS = psg.GRANTS, ledger
        try:
            ledger.grant(
                source=ExternalSource.FRONTIER_CONSULT, caller=_CALLER,
                operation=_OP, max_calls=99,
            )
            inv = InventoryRegistry()
            for _ in range(5):
                inv.summarize([ExternalSource.FRONTIER_CONSULT])
                inv.summarize(
                    [ExternalSource.FRONTIER_CONSULT],
                    paid_context=(_CALLER, _OP),
                )
        finally:
            psg.GRANTS = orig
        self.assertEqual(
            before, _proxy_call_count(),
            "availability probing issued a model completion — discovering "
            "affordability must be free, granted or not",
        )


class NoActionLaneSemanticsChanged(unittest.TestCase):
    def test_the_action_tier_vocabulary_is_untouched(self):
        from core.actions.action_engine import ACTION_TIERS

        for name in ACTION_TIERS:
            self.assertNotIn("frontier", name.lower())
        self.assertEqual(ACTION_TIERS.get("web_search"), 0)

    def test_cost_did_not_enter_egress_origin_class(self):
        """egress_origin_class is a free-form string, not an enum, so it
        is pinned over the literals the tree actually uses. It means
        PROVENANCE of outbound content — whose context it came from —
        never who pays for it."""
        import ast
        import os

        used = set()
        for root, dirs, files in os.walk("core"):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                rel = os.path.join(root, fn)
                try:
                    tree = ast.parse(Path(rel).read_text(encoding="utf-8"))
                except SyntaxError:
                    continue
                for n in ast.walk(tree):
                    if (
                        isinstance(n, ast.keyword)
                        and n.arg == "egress_origin_class"
                        and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, str)
                    ):
                        used.add(n.value.value)
                    if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant):
                        for tg in n.targets:
                            if (
                                isinstance(tg, ast.Name)
                                and tg.id == "EGRESS_ORIGIN_CLASS"
                                and isinstance(n.value.value, str)
                            ):
                                used.add(n.value.value)

        self.assertTrue(used, "found no egress_origin_class literals to check")
        for value in used:
            for banned in ("paid", "cost", "budget", "frontier", "authoriz", "quota"):
                self.assertNotIn(
                    banned, value.lower(),
                    f"egress_origin_class {value!r} encodes COST — it means "
                    "provenance of outbound content, never who pays",
                )


if __name__ == "__main__":
    unittest.main()
