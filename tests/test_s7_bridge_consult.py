from __future__ import annotations

import unittest
from types import SimpleNamespace


class _FakeDeps:
    def __init__(
        self,
        *,
        objection_state: str,
        consultation_id: str = "s7.1.card.voice.r1",
        full_bundle: bool = True,
    ):
        self.card = SimpleNamespace(request_id="r1")
        self.envelope = SimpleNamespace(request_id="env-r1")
        self.consultation = SimpleNamespace(
            maez_objection_state=objection_state,
            consultation_id=consultation_id,
        )
        self.full_bundle = full_bundle
        self.blocked = {}
        self.voice_producer_called = False
        self.bridge_wrote_bundle = False

    def get_card(self, card_request_id):
        self.card.request_id = card_request_id
        return self.card

    def s7_request_envelope_for_card(self, card):
        self.envelope.request_id = f"env-{card.request_id}"
        return self.envelope

    def run_voice_consultation(self, card, envelope):
        self.voice_producer_called = True
        return self.consultation

    def full_voice_bundle_present(self, request_id):
        return self.full_bundle

    def set_blocked_for_card(self, card_request_id, *, reason):
        self.blocked[card_request_id] = reason

    def dialog_blocked(self, card_request_id):
        return card_request_id in self.blocked

    def block_reason(self, card_request_id):
        return self.blocked.get(card_request_id)

    def ceremony_pointer_for(self, card_request_id):
        return f"http://127.0.0.1:11437/s7/{card_request_id}"


class ConsultAfterSeedTest(unittest.TestCase):
    def test_objection_blocks_dialog_with_machine_reason_and_no_pointer(self):
        from skills.surface.s7_ceremony_bridge import consult_then_block_or_pointer

        deps = _FakeDeps(
            objection_state="present",
            consultation_id="s7.1.card.voice.r1",
        )

        out = consult_then_block_or_pointer(card_request_id="r1", deps=deps)

        self.assertIsNone(out.ceremony_pointer)
        self.assertTrue(out.blocked)
        self.assertTrue(deps.dialog_blocked("r1"))
        self.assertEqual(
            deps.block_reason("r1"),
            "voice_objection_present:s7.1.card.voice.r1",
        )

    def test_not_determined_blocks_with_unavailable_reason(self):
        from skills.surface.s7_ceremony_bridge import consult_then_block_or_pointer

        deps = _FakeDeps(
            objection_state="not_determined",
            consultation_id="s7.1.card.voice.r2",
        )

        out = consult_then_block_or_pointer(card_request_id="r2", deps=deps)

        self.assertIsNone(out.ceremony_pointer)
        self.assertTrue(out.blocked)
        self.assertEqual(
            deps.block_reason("r2"),
            "voice_consultation_unavailable:s7.1.card.voice.r2",
        )

    def test_no_objection_with_full_bundle_returns_pointer(self):
        from skills.surface.s7_ceremony_bridge import consult_then_block_or_pointer

        deps = _FakeDeps(
            objection_state="absent",
            consultation_id="s7.1.card.voice.r3",
            full_bundle=True,
        )

        out = consult_then_block_or_pointer(card_request_id="r3", deps=deps)

        self.assertEqual(out.ceremony_pointer, "http://127.0.0.1:11437/s7/r3")
        self.assertFalse(out.blocked)
        self.assertFalse(deps.dialog_blocked("r3"))
        self.assertFalse(deps.bridge_wrote_bundle)

    def test_no_objection_but_missing_bundle_fails_closed(self):
        from skills.surface.s7_ceremony_bridge import consult_then_block_or_pointer

        deps = _FakeDeps(
            objection_state="absent",
            consultation_id="s7.1.card.voice.r3b",
            full_bundle=False,
        )

        out = consult_then_block_or_pointer(card_request_id="r3b", deps=deps)

        self.assertIsNone(out.ceremony_pointer)
        self.assertTrue(out.blocked)
        self.assertEqual(
            deps.block_reason("r3b"),
            "voice_consultation_unavailable:s7.1.card.voice.r3b",
        )

    def test_voice_producer_is_invoked_not_a_constant(self):
        from skills.surface.s7_ceremony_bridge import consult_then_block_or_pointer

        deps = _FakeDeps(objection_state="absent")

        consult_then_block_or_pointer(card_request_id="r4", deps=deps)

        self.assertTrue(deps.voice_producer_called)
