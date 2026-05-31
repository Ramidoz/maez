import unittest

from core.routing.recall_receipt import (
    ACK_CEILING_MS,
    RECEIPT_AFTER_MS,
    RECEIPT_SEND_TIMEOUT_MS,
    AckStatus,
    FORBIDDEN_COGNITION_VERBS,
    ReceiptAckBox,
    WORKING_RECEIPT_TEXT,
    receipt_eligible,
    resolve_ack_status,
)


class ReceiptWordingTest(unittest.TestCase):
    def test_working_receipt_is_body_state_not_thought(self):
        low = WORKING_RECEIPT_TEXT.lower()
        for verb in FORBIDDEN_COGNITION_VERBS:
            self.assertNotIn(verb, low, f"cognition-verb leaked: {verb}")
        self.assertIn("checking", low)

    def test_genderless(self):
        low = f" {WORKING_RECEIPT_TEXT.lower()} "
        for bad in (" she ", " he ", " her ", " his ", " him "):
            self.assertNotIn(bad, low)

    def test_constants_match_a7_gate(self):
        self.assertEqual(RECEIPT_AFTER_MS, 900)
        self.assertEqual(ACK_CEILING_MS, 1500)
        self.assertEqual(RECEIPT_SEND_TIMEOUT_MS, 1000)


class EligibilityTest(unittest.TestCase):
    def test_eligible_only_when_focused_carrier_engaged(self):
        self.assertTrue(
            receipt_eligible(
                flag_on=True,
                focused_carrier_engaged=True,
                surface_sink_available=True,
            )
        )
        self.assertFalse(
            receipt_eligible(
                flag_on=True,
                focused_carrier_engaged=False,
                surface_sink_available=True,
            )
        )
        self.assertFalse(
            receipt_eligible(
                flag_on=False,
                focused_carrier_engaged=True,
                surface_sink_available=True,
            )
        )
        self.assertFalse(
            receipt_eligible(
                flag_on=True,
                focused_carrier_engaged=True,
                surface_sink_available=False,
            )
        )


class AckStatusTest(unittest.TestCase):
    def test_fast_answer_no_receipt(self):
        self.assertEqual(
            resolve_ack_status(eligible=True, fired=False, send_result=None),
            AckStatus.NOT_REQUIRED_FAST_ANSWER.value,
        )

    def test_missed_slow_receipt_deadline_is_timeout(self):
        self.assertEqual(
            resolve_ack_status(
                eligible=True,
                fired=False,
                send_result=None,
                ack_required=True,
            ),
            AckStatus.SEND_TIMEOUT.value,
        )

    def test_emitted_on_successful_send(self):
        self.assertEqual(
            resolve_ack_status(eligible=True, fired=True, send_result="ok"),
            AckStatus.EMITTED.value,
        )

    def test_send_failed_and_timeout_are_distinct(self):
        self.assertEqual(
            resolve_ack_status(eligible=True, fired=True, send_result="failed"),
            AckStatus.SEND_FAILED.value,
        )
        self.assertEqual(
            resolve_ack_status(eligible=True, fired=True, send_result="timeout"),
            AckStatus.SEND_TIMEOUT.value,
        )

    def test_disabled_and_not_eligible(self):
        self.assertEqual(
            resolve_ack_status(
                eligible=False,
                fired=False,
                send_result=None,
                disabled=True,
            ),
            AckStatus.DISABLED.value,
        )
        self.assertEqual(
            resolve_ack_status(eligible=False, fired=False, send_result=None),
            AckStatus.NOT_ELIGIBLE.value,
        )


class ReceiptAckBoxTest(unittest.TestCase):
    def test_cancel_prevents_late_fire(self):
        box = ReceiptAckBox(turn_started_mono=10.0)
        box.cancel()
        self.assertFalse(box.try_mark_fired())
        snap = box.snapshot(now_mono=11.0)
        self.assertFalse(snap.fired)
        self.assertIsNone(snap.send_result)

    def test_records_successful_completion_time_not_enqueue(self):
        box = ReceiptAckBox(turn_started_mono=10.0)
        self.assertTrue(box.try_mark_fired())
        box.mark_ok(completed_mono=10.42)
        snap = box.snapshot(now_mono=10.5)
        self.assertTrue(snap.fired)
        self.assertEqual(snap.send_result, "ok")
        self.assertEqual(snap.ack_emit_ms, 419)

    def test_first_terminal_result_wins(self):
        box = ReceiptAckBox(turn_started_mono=10.0)
        self.assertTrue(box.try_mark_fired())
        box.mark_timeout(completed_mono=10.9)
        box.mark_ok(completed_mono=10.95)
        box.mark_failed(completed_mono=11.0)
        snap = box.snapshot(now_mono=11.0)
        self.assertEqual(snap.send_result, "timeout")
        self.assertEqual(snap.ack_emit_ms, 900)

    def test_cancel_after_fire_does_not_erase_completion(self):
        box = ReceiptAckBox(turn_started_mono=10.0)
        self.assertTrue(box.try_mark_fired())
        box.cancel()
        box.mark_ok(completed_mono=10.3)
        snap = box.snapshot(now_mono=10.4)
        self.assertTrue(snap.fired)
        self.assertEqual(snap.send_result, "ok")
        self.assertEqual(snap.ack_emit_ms, 300)


if __name__ == "__main__":
    unittest.main()
