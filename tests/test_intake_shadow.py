from __future__ import annotations

import json
import unittest

from core.cognition.intake_faculty import IntakeRead
from core.cognition import intake_shadow as shadow
from core.search.search_commitment import OfferReceipt


class _Controller:
    def __init__(self, offer=None, awaiting_card=False):
        self.offer = offer
        self.awaiting_card = awaiting_card
        self.mutated = False

    def get_search_offer(self, channel, chat_id):
        return self.offer

    def has_awaiting_card(self, channel, chat_id):
        return self.awaiting_card

    def consume_offer_approval(self, *args, **kwargs):
        self.mutated = True
        raise AssertionError("shadow must not consume offers")


class TelemetryTests(unittest.TestCase):
    def test_content_light_default_excludes_owner_text(self):
        read = IntakeRead(
            turn_kind="commitment_response",
            stance="yes",
            boundary_signal="none",
            needs="search",
            referent_kind="pending_offer",
            confidence=0.9,
            rationale="Owner said proceed to the search.",
        )

        rec = shadow.build_telemetry(
            message="Proceed with the llama.cpp search",
            context_turns=["Rohit: private prior text", "Maez: private reply"],
            pending_offer={
                "action_type": "web_search",
                "stakes": "low_read",
                "egress_class": "sovereign_local_search",
                "offered_query": "llama.cpp release",
            },
            faculty_read=read,
            gate_verdicts={"is_clear_yes": "false"},
            status="ok",
            latency_s=0.012,
            debug=False,
        )

        blob = json.dumps(rec)
        self.assertIn("turn_hash", rec)
        self.assertIn("context_hash", rec)
        self.assertNotIn("Proceed", blob)
        self.assertNotIn("private prior text", blob)
        self.assertNotIn("llama.cpp release", blob)
        self.assertNotIn("Owner said", blob)

    def test_debug_can_include_bounded_snippets(self):
        read = IntakeRead(
            turn_kind="ordinary",
            stance="n_a",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=0.8,
            rationale="debug rationale",
        )

        rec = shadow.build_telemetry(
            message="hello there",
            context_turns=[],
            pending_offer=None,
            faculty_read=read,
            gate_verdicts={},
            status="ok",
            latency_s=0.0,
            debug=True,
        )

        self.assertEqual(rec["turn_excerpt"], "hello there")
        self.assertEqual(rec["faculty_read"]["rationale"], "debug rationale")

    def test_gate_snapshot_is_read_only(self):
        offer = OfferReceipt(
            action_type="web_search",
            stakes="low_read",
            offered_query="x",
            created_ts=1.0,
            ttl_seconds=300.0,
            ttl_turns=3,
            requires_confirmation=True,
            confirmation_mode="clear_yes_ok",
            executor="searxng",
            egress_class="sovereign_local_search",
        )
        ctrl = _Controller(offer=offer)

        verdicts = shadow.gate_verdicts(
            "proceed",
            controller=ctrl,
            channel="telegram_text",
            chat_id="c",
        )

        self.assertEqual(verdicts["is_clear_yes"], "false")
        self.assertIn(verdicts["hard_want"], {"true", "false"})
        self.assertIn(verdicts["continuity"], {"true", "false", "unavailable"})
        self.assertIn("continuity_kind", verdicts)
        self.assertFalse(ctrl.mutated)
        self.assertIs(ctrl.get_search_offer("telegram_text", "c"), offer)

    def test_pending_offer_snapshot_hashes_query(self):
        offer = OfferReceipt(
            action_type="web_search",
            stakes="low_read",
            offered_query="private query text",
            created_ts=1.0,
            ttl_seconds=300.0,
            ttl_turns=3,
            requires_confirmation=True,
            confirmation_mode="clear_yes_ok",
            executor="searxng",
            egress_class="sovereign_local_search",
        )

        snap = shadow.offer_snapshot(offer)

        self.assertEqual(snap["action_type"], "web_search")
        self.assertEqual(snap["stakes"], "low_read")
        self.assertEqual(snap["egress_class"], "sovereign_local_search")
        self.assertIn("offered_query_hash", snap)
        self.assertNotIn("private query text", json.dumps(snap))

    def test_build_telemetry_sanitizes_raw_pending_offer_dict(self):
        read = IntakeRead(
            turn_kind="ordinary",
            stance="n_a",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=0.8,
        )

        rec = shadow.build_telemetry(
            message="hello",
            context_turns=[],
            pending_offer={
                "action_type": "web_search",
                "stakes": "low_read",
                "executor": "searxng",
                "egress_class": "sovereign_local_search",
                "offered_query": "private raw query",
            },
            faculty_read=read,
            gate_verdicts={},
            status="ok",
            latency_s=0.0,
            debug=False,
        )

        blob = json.dumps(rec)
        self.assertIn("offered_query_hash", blob)
        self.assertNotIn("private raw query", blob)
