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
import shutil
import tempfile
import unittest
from pathlib import Path

from core.decision.pending_cards import PendingCardStore
from core.dispatcher import frontier_grant as fg
from core.dispatcher.inventory import (
    PAID_SOURCES,
    RESERVED_SOURCES,
    InventoryRegistry,
)
from core.dispatcher.spec import (
    AvailabilityLimitation,
    ExternalSource,
    SourceAvailability,
)

_CALLER = "self_dev.propose_tests"
_OP = "d1-witness"




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
    """paid_context is an authorization CARD ID.

    Authority comes from an owner-resolved card, never from a caller
    naming itself, so these exercise the real card store.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(dir="/var/tmp", prefix="d1_state_")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = PendingCardStore(Path(self.dir) / "cards.db")
        import core.decision.pending_cards as pc

        real = pc.PendingCardStore
        pc.PendingCardStore = lambda *a, **k: (
            self.store if not a and not k else real(*a, **k)
        )
        self.addCleanup(setattr, pc, "PendingCardStore", real)
        self.card_id = "no-such-card"

    def _grant(self):
        card = fg.request_authorization(
            source=ExternalSource.FRONTIER_CONSULT,
            operation="self_dev.propose_tests", purpose={"q": 1},
            plain_english="Consult the frontier model.", store=self.store,
        )
        self.store.approve(card.request_id, user_id="rohit", via="text_reply",
                           current_state_fields=card.params)
        self.card_id = card.request_id

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

    def _state(self, inv=None, ctx=None):
        inv = inv or InventoryRegistry()
        r = inv.summarize([ExternalSource.FRONTIER_CONSULT],
                          paid_context=ctx or self.card_id)
        return (
            r.source_availability[ExternalSource.FRONTIER_CONSULT],
            list(r.availability_limitations),
        )

    def test_a_request_without_an_approved_card_needs_authorization(self):
        """REPORTING only. Enforcement is pinned in
        tests/test_metered_external_resource_use.py — a report is not a
        gate."""
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

    def test_the_authorization_read_never_consumes_the_card(self):
        """Availability inspection must not spend the authorization it is
        inspecting."""
        self._grant()
        self._reachable()
        self._with_budget({"claude": {"hourly_remaining": 9, "daily_remaining": 9}})
        for _ in range(5):
            self._state()
        self.assertEqual(
            self.store.get(self.card_id).status, "approved",
            "inspecting availability transitioned the card",
        )

    def test_context_is_per_call_not_registry_state(self):
        """Instance state here was a real race: one request could install
        its context, pause in the probe, and have another request's
        authorized context answer for it."""
        self.assertFalse(
            hasattr(InventoryRegistry(), "paid_request_context"),
            "paid context is back on the registry as mutable shared state",
        )


class TheBudgetReadIsThreeValued(unittest.TestCase):
    """Exhausted, affordable, and UNKNOWN are three different answers.

    An incomplete budget record is not evidence of exhaustion. Defaulting
    a missing window to 0 turned "the proxy did not say" into "there is
    none left".
    """

    def _budget(self, payload):
        import core.routing.claude_tier as ct

        real = ct.budget
        ct.budget = lambda *a, **k: payload
        self.addCleanup(setattr, ct, "budget", real)
        return InventoryRegistry()._paid_source_budget(
            ExternalSource.FRONTIER_CONSULT
        )

    def test_both_windows_must_be_present_to_conclude_anything(self):
        for partial in (
            {"daily_remaining": 3},
            {"hourly_remaining": 2},
            {"hourly_cap": 120},
            {},
        ):
            self.assertIsNone(
                self._budget({"claude": partial}),
                f"an INCOMPLETE record {partial} was read as proven "
                "exhaustion",
            )

    def test_a_malformed_record_is_unknown_not_an_exception(self):
        for junk in ("malformed", 7, [1, 2], None):
            self.assertIsNone(
                self._budget({"claude": junk}),
                f"a malformed record {junk!r} was not reported unknown",
            )

    def test_either_window_at_zero_is_exhausted(self):
        """ASYMMETRIC controls. Symmetric 0/0 and 9/9 alone cannot tell
        `and` from `or` -- both pass either way."""
        self.assertIs(
            self._budget({"claude": {"hourly_remaining": 9, "daily_remaining": 0}}),
            False,
            "a spent DAILY window was reported affordable — both windows "
            "must have room, not either",
        )
        self.assertIs(
            self._budget({"claude": {"hourly_remaining": 0, "daily_remaining": 9}}),
            False,
            "a spent HOURLY window was reported affordable",
        )

    def test_both_windows_with_room_is_affordable(self):
        self.assertIs(
            self._budget({"claude": {"hourly_remaining": 9, "daily_remaining": 9}}),
            True,
        )

    def test_a_scheme_default_port_is_used_when_none_is_explicit(self):
        """https://proxy.example is :443, not the bundled proxy's port."""
        import core.routing.claude_tier as ct

        seen = []
        real_sock = socket.create_connection
        socket.create_connection = lambda addr, **k: seen.append(addr) or (_ for _ in ()).throw(ConnectionRefusedError())
        real_url = ct.PROXY_URL
        self.addCleanup(setattr, socket, "create_connection", real_sock)
        self.addCleanup(setattr, ct, "PROXY_URL", real_url)

        for url, expected in (
            ("http://127.0.0.1:11438", 11438),
            ("https://proxy.example", 443),
            ("http://proxy.example", 80),
        ):
            ct.PROXY_URL = url
            seen.clear()
            InventoryRegistry()._paid_source_reachable(
                ExternalSource.FRONTIER_CONSULT
            )
            self.assertEqual(
                seen[0][1], expected,
                f"{url} probed port {seen[0][1]}, not {expected}",
            )


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
        inv = InventoryRegistry()
        for _ in range(5):
            inv.summarize([ExternalSource.FRONTIER_CONSULT])
            inv.summarize([ExternalSource.FRONTIER_CONSULT],
                          paid_context="no-such-card")
        self.assertEqual(
            before, _proxy_call_count(),
            "availability probing issued a model completion — discovering "
            "affordability must be free",
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
