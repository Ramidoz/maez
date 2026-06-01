import unittest

from core.routing.cancellable_brain_call import BrainPreempted
from core.routing.brain_gateway import (
    BrainGateway,
    BrainPurpose,
    current_purpose,
    priority_of,
    with_purpose,
)


class BrainPurposeTest(unittest.TestCase):
    def test_priority_is_derived_not_passed(self):
        self.assertGreater(
            priority_of(BrainPurpose.OWNER_RECALL),
            priority_of(BrainPurpose.DAEMON_CYCLE_GENERATION),
        )
        self.assertEqual(priority_of(BrainPurpose.NEUTRAL), 0)

    def test_unknown_purpose_defaults_neutral_never_high(self):
        self.assertEqual(priority_of("not_a_real_purpose"), 0)

    def test_current_purpose_defaults_neutral_and_context_restores(self):
        self.assertEqual(current_purpose(), BrainPurpose.NEUTRAL)
        with with_purpose(BrainPurpose.OWNER_REPLY):
            self.assertEqual(current_purpose(), BrainPurpose.OWNER_REPLY)
        self.assertEqual(current_purpose(), BrainPurpose.NEUTRAL)


class BrainGatewayTest(unittest.TestCase):
    def test_submit_buffers_stream_and_records_content_free_event(self):
        gateway = BrainGateway()

        reply = gateway.submit(
            purpose=BrainPurpose.OWNER_RECALL,
            run_streaming_fn=lambda: iter(
                [{"content": "hello "}, {"content": "there"}]
            ),
        )

        self.assertEqual(reply, "hello there")
        self.assertEqual(len(gateway.events), 1)
        event = gateway.events[0]
        self.assertEqual(
            set(event),
            {
                "schema_version",
                "purpose",
                "priority",
                "wait_ms",
                "preempted",
                "preempted_count",
                "slot_busy_before",
                "preempt_timeout",
            },
        )
        self.assertEqual(event["purpose"], "owner_recall")
        self.assertFalse(event["preempted"])
        self.assertFalse(event["slot_busy_before"])

    def test_brain_preempted_is_propagated_not_buffered(self):
        class _PreemptingStream:
            def __iter__(self):
                raise BrainPreempted()

        gateway = BrainGateway()

        with self.assertRaises(BrainPreempted):
            gateway.submit(
                purpose=BrainPurpose.DAEMON_CYCLE_GENERATION,
                run_streaming_fn=lambda: _PreemptingStream(),
            )

        self.assertEqual(gateway.events[0]["purpose"], "daemon_cycle_generation")
        self.assertTrue(gateway.events[0]["preempted"])


if __name__ == "__main__":
    unittest.main()
