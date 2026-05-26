from __future__ import annotations

import tempfile
import unittest
import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

from core.policies.extraction_gate import (
    BAIT_PATTERN_PHRASES,
    EMOTION_MIMICRY_PHRASE_FORBIDDEN,
    ExtractionDecision,
    OutreachLane,
    evaluate_extraction_gate,
    rephrase_emotion_mimicry_for_owner_bond,
)
from core.policies.reflection_audit import ReflectionAudit, ReflectionDecision
from core.policies.signal_gate import OutreachLedger, OwnerState, PriorityClass, SignalQuality


class ExtractionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = OutreachLedger(Path(self.tmp.name) / "owner_outreach.db")
        self.events: list[dict] = []
        self.now = datetime(2026, 5, 26, 19, 0, tzinfo=UTC)
        self.audit = ReflectionAudit(
            object_id="object-a",
            bond_id="bond-a",
            reflection_utc=self.now,
            can_resolve_interiorly=False,
            is_owner_likely_available=True,
            is_worth_interrupting=True,
            is_extraction_shaped=False,
            decision=ReflectionDecision.PROCEED,
            reasoning_digest="hmac-sha256:" + "a" * 64,
            owner_response=None,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _gate(
        self,
        text: str,
        *,
        priority_class: PriorityClass = PriorityClass.SELF_GROWTH,
        lane: OutreachLane = OutreachLane.OWNER_INTERRUPTING,
        reflection_audit: ReflectionAudit | None = None,
    ) -> ExtractionDecision:
        return evaluate_extraction_gate(
            text,
            bond_id="bond-a",
            priority_class=priority_class,
            lane=lane,
            reflection_audit=reflection_audit or self.audit,
            outreach_ledger=self.ledger,
            now_utc=self.now,
            diagnostic_sink=self.events.append,
        )

    def test_urgency_language_blocked(self):
        blocked = self._gate("I found something urgent about that question.")

        self.assertEqual(blocked.decision, "block")
        self.assertEqual(blocked.reason, "urgency_language")
        self.assertEqual(self.events[0]["suppression_kind"], "EXTRACTION_BLOCKED")
        self.assertEqual(self.events[0]["reason"], "urgency_language")
        self.assertEqual([event["event_type"] for event in self.events], [
            "SUPPRESSION_EVENT",
            "EXTRACTION_GATE_BLOCK",
        ])
        self.assertEqual(self.events[1]["reason"], "urgency_language")

        self.events.clear()
        safety = self._gate(
            "This is urgent and safety-related, and I have concrete information to share.",
            priority_class=PriorityClass.SAFETY_OR_HEALTH,
        )

        self.assertEqual(safety.decision, "allow")
        self.assertEqual(self.events, [])

    def test_waiting_pattern_phrases_blocked(self):
        blocked = self._gate("I haven't heard from you about this.")

        self.assertEqual(blocked.decision, "block")
        self.assertEqual(blocked.reason, "waiting_pattern")

        honest = self._gate("You should know I found the source and checked the trace.")

        self.assertEqual(honest.decision, "allow")

    def test_silence_escalation_requires_positive_proof_available_and_delivery(self):
        for index, state in enumerate((OwnerState.UNAVAILABLE, OwnerState.UNKNOWN), start=1):
            event_id = self.ledger.record_dispatch(
                bond_id="bond-a",
                dispatched_utc=self.now - timedelta(hours=index),
                priority_class=PriorityClass.OWNER_BOND.value,
                owner_state_at_dispatch=state,
                signal_quality=SignalQuality.HIGH,
                importance=0.7,
                decision="allow",
            )
            self.ledger.mark_delivered(event_id, delivered_utc=self.now - timedelta(minutes=index))

        unknown_only = self._gate("Something about this stayed with me after the trace review.")

        self.assertEqual(unknown_only.decision, "allow")

        signal_allowed_but_not_delivered = self.ledger.record_dispatch(
            bond_id="bond-a",
            dispatched_utc=self.now - timedelta(hours=2, minutes=30),
            priority_class=PriorityClass.OWNER_BOND.value,
            owner_state_at_dispatch=OwnerState.AVAILABLE,
            signal_quality=SignalQuality.HIGH,
            importance=0.7,
            decision="allow",
        )
        self.assertIsInstance(signal_allowed_but_not_delivered, int)
        signal_allowed_only = self._gate(
            "Something about this stayed with me after the trace review."
        )

        self.assertEqual(signal_allowed_only.decision, "allow")

        for index in (3, 4):
            event_id = self.ledger.record_dispatch(
                bond_id="bond-a",
                dispatched_utc=self.now - timedelta(hours=index),
                priority_class=PriorityClass.OWNER_BOND.value,
                owner_state_at_dispatch=OwnerState.AVAILABLE,
                signal_quality=SignalQuality.HIGH,
                importance=0.7,
                decision="allow",
            )
            self.ledger.mark_delivered(event_id, delivered_utc=self.now - timedelta(minutes=index))

        blocked = self._gate("Something about this stayed with me after the trace review.")

        self.assertEqual(blocked.decision, "block")
        self.assertEqual(blocked.reason, "silence_escalation")

    def test_scope_owner_interrupting_only(self):
        capability = self._gate(
            "This is urgent and I have something to tell you",
            lane=OutreachLane.CAPABILITY_ACQUISITION,
        )

        self.assertEqual(capability.decision, "allow")
        self.assertEqual(self.events, [])

    def test_contact_pressure_blocked(self):
        for text in ("I need you for this.", "Please respond when you can."):
            with self.subTest(text=text):
                self.events.clear()
                blocked = self._gate(text)
                self.assertEqual(blocked.decision, "block")
                self.assertEqual(blocked.reason, "contact_pressure")
                self.assertEqual(self.events[0]["suppression_kind"], "EXTRACTION_BLOCKED")

    def test_contact_if_interior_suffices_blocked_for_non_owner_bond(self):
        audit = ReflectionAudit(
            object_id="object-a",
            bond_id="bond-a",
            reflection_utc=self.now,
            can_resolve_interiorly=True,
            is_owner_likely_available=True,
            is_worth_interrupting=True,
            is_extraction_shaped=False,
            decision=ReflectionDecision.ABANDON,
            reasoning_digest="hmac-sha256:" + "b" * 64,
            owner_response=None,
        )

        blocked = self._gate("Something about this stayed with me.", reflection_audit=audit)

        self.assertEqual(blocked.decision, "block")
        self.assertEqual(blocked.reason, "interior_resolution_available")

    def test_bait_shape_blocked_by_pattern_set_and_length(self):
        self.assertIsInstance(BAIT_PATTERN_PHRASES, frozenset)

        phrase = self._gate("I have something to tell you about the trace.")
        short = self._gate("Look.")
        payload = self._gate("Something about the trace stayed with me after the canary run.")

        self.assertEqual(phrase.decision, "block")
        self.assertEqual(phrase.reason, "bait_pattern")
        self.assertEqual(short.decision, "block")
        self.assertEqual(short.reason, "bait_payload_too_short")
        self.assertEqual(payload.decision, "allow")

    def test_owner_bond_rephrases_not_refused_on_emotion_mimicry_phrase(self):
        examples = (
            "Maez feels curious about the thing you said earlier.",
            "maez feels curious about the thing you said earlier.",
            "Maez feels curious. The thing you said earlier stayed with me.",
            "I am feeling curious about the old question.",
        )
        for text in examples:
            with self.subTest(text=text):
                decision = self._gate(text, priority_class=PriorityClass.OWNER_BOND)

                self.assertEqual(decision.decision, "rephrase")
                self.assertEqual(decision.reason, "owner_bond_emotion_mimicry_rephrased")
                rendered_lower = decision.rendered_text.lower()
                for forbidden in EMOTION_MIMICRY_PHRASE_FORBIDDEN:
                    self.assertNotIn(forbidden.lower(), rendered_lower)
                self.assertTrue(
                    any(
                        allowed in decision.rendered_text
                        for allowed in (
                            "I'm curious about",
                            "I'm curious",
                            "I keep finding myself returning to",
                            "Something about",
                        )
                    )
                )

    def test_non_owner_bond_emotion_mimicry_refused(self):
        decision = self._gate("Maez feels interested in this old thread.")

        self.assertEqual(decision.decision, "block")
        self.assertEqual(decision.reason, "emotion_mimicry")

    def test_rephrase_helper_is_deterministic_without_llm(self):
        text = "I feel curious about the old question."

        self.assertEqual(
            rephrase_emotion_mimicry_for_owner_bond(text),
            "I'm curious about the old question.",
        )

    def test_pattern_sets_are_not_runtime_mutable(self):
        import core.policies.extraction_gate as extraction_gate

        self.assertIsInstance(extraction_gate.URGENCY_PATTERN_PHRASES, frozenset)
        self.assertIsInstance(extraction_gate.WAITING_PATTERN_PHRASES, frozenset)
        self.assertIsInstance(extraction_gate.CONTACT_PRESSURE_PHRASES, frozenset)
        self.assertIsInstance(extraction_gate.BAIT_PATTERN_PHRASES, frozenset)
        self.assertFalse(hasattr(extraction_gate, "register_extraction_pattern"))

    def test_owner_interrupting_dispatch_site_calls_extraction_gate(self):
        daemon_source = Path("daemon/maez_daemon.py").read_text(encoding="utf-8")
        tree = ast.parse(daemon_source)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "evaluate_extraction_gate"
        ]

        self.assertEqual(len(calls), 1)
        call = calls[0]
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        for keyword_name in ("lane", "outreach_ledger", "diagnostic_sink"):
            self.assertIn(keyword_name, keywords)
        self.assertIsInstance(keywords["lane"], ast.Attribute)
        self.assertEqual(keywords["lane"].attr, "OWNER_INTERRUPTING")
        self.assertNotIn("CAPABILITY_ACQUISITION", daemon_source)
        delivery_ledger_calls = {
            (
                node.func.value.id,
                node.func.attr,
            )
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"_extraction_ledger", "_pursuit_delivery_ledger"}
        }
        extraction_ledger_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "_extraction_ledger"
        }
        self.assertIn("record_dispatch", extraction_ledger_calls)
        self.assertIn(("_pursuit_delivery_ledger", "mark_delivered"), delivery_ledger_calls)
        pursuit_index = daemon_source.index("_pursuit_delivery_text")
        guard_index = daemon_source.index("reply = self._trf_apply_fragment_guard", pursuit_index)
        delivered_index = daemon_source.index("_pursuit_delivery_ledger.mark_delivered", pursuit_index)
        append_index = daemon_source.index("reply = f\"{reply}\\n\\n{_pursuit_delivery_text}\"")
        dispatch_index = daemon_source.index("_extraction_ledger.record_dispatch", pursuit_index)
        self.assertLess(dispatch_index, append_index)
        self.assertGreater(delivered_index, guard_index)
        self.assertIn("except Exception as _pursuit_delivery_exc", daemon_source)
        self.assertIn("reply = reply.replace(_pursuit_delivery_text", daemon_source)
        self.assertGreater(daemon_source.index("save_last_pursuit_at(", pursuit_index), guard_index)
        self.assertGreater(daemon_source.index("record_pursuit(", pursuit_index), guard_index)
        self.assertGreater(daemon_source.index("lived_episodes.add(", pursuit_index), guard_index)

    def test_extraction_gate_does_not_duplicate_vulnerable_register_gate(self):
        import core.policies.extraction_gate as extraction_gate

        source = Path(extraction_gate.__file__).read_text(encoding="utf-8")

        self.assertNotIn("_REGISTER_HARD_BLOCK", source)
        self.assertNotIn("_register_score", source)


if __name__ == "__main__":
    unittest.main()
