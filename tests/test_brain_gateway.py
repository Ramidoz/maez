import unittest
from unittest import mock

from core.routing import brain_gateway as brain_gateway_module
from core.routing.cancellable_brain_call import BrainPreempted
from core.routing.brain_gateway import (
    BrainGateway,
    BrainPurpose,
    current_purpose,
    priority_of,
    reset_gateway_state_for_tests,
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

    def test_reset_gateway_state_for_tests_restores_current_purpose(self):
        with with_purpose(BrainPurpose.OWNER_REPLY):
            reset_gateway_state_for_tests()
            self.assertEqual(current_purpose(), BrainPurpose.NEUTRAL)


class BrainGatewayTest(unittest.TestCase):
    def test_retained_events_are_bounded(self):
        gateway = BrainGateway(max_events=3)

        for idx in range(5):
            gateway.submit(
                purpose=BrainPurpose.OWNER_RECALL,
                run_streaming_fn=lambda idx=idx: iter([{"content": str(idx)}]),
            )

        self.assertEqual(len(gateway.events), 3)
        self.assertEqual(
            [event["purpose"] for event in gateway.events],
            ["owner_recall", "owner_recall", "owner_recall"],
        )

    def test_reset_for_tests_clears_retained_singleton_state(self):
        gateway = BrainGateway(max_events=3)
        gateway.submit(
            purpose=BrainPurpose.OWNER_RECALL,
            run_streaming_fn=lambda: iter([{"content": "first"}]),
        )

        gateway.reset_for_tests()

        self.assertEqual(list(gateway.events), [])

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
                "event",
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
        self.assertEqual(event["event"], "brain_gateway_event")
        self.assertEqual(event["purpose"], "owner_recall")
        self.assertFalse(event["preempted"])
        self.assertFalse(event["slot_busy_before"])

    def test_gateway_event_is_logged_content_free(self):
        gateway = BrainGateway()
        canary = "SECRET_REPLY_TEXT_SHOULD_NOT_BE_LOGGED"

        with mock.patch.object(brain_gateway_module.logger, "info") as m_info:
            reply = gateway.submit(
                purpose=BrainPurpose.OWNER_RECALL,
                run_streaming_fn=lambda: iter([{"content": canary}]),
            )

        self.assertEqual(reply, canary)
        self.assertEqual(m_info.call_count, 1)
        rendered_log_call = " ".join(
            str(part)
            for call in m_info.call_args_list
            for part in (*call.args, *call.kwargs.values())
        )
        self.assertIn("brain_gateway_event", rendered_log_call)
        self.assertIn("owner_recall", rendered_log_call)
        self.assertNotIn(canary, rendered_log_call)

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
