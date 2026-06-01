import json
import unittest

from core.routing.brain_gateway import BrainGateway, BrainPurpose
from core.routing.cancellable_brain_call import CancellableBrainCall


class EquivalenceTest(unittest.TestCase):
    def test_buffered_reply_byte_equivalent_to_stream_chunks(self):
        chunks = [
            {"content": "On April 27 "},
            {"content": "we noted "},
            {"content": "the incident [E1]."},
        ]
        call = CancellableBrainCall(raw_stream=iter(chunks))

        self.assertEqual(
            call.collect(),
            "On April 27 we noted the incident [E1].",
        )

    def test_gateway_telemetry_is_content_free(self):
        gateway = BrainGateway()
        gateway.submit(
            purpose=BrainPurpose.OWNER_RECALL,
            run_streaming_fn=lambda: iter(
                [
                    {"content": "PRIVATE QUESTION"},
                    {"content": " SECRET EVIDENCE"},
                ]
            ),
        )

        event = gateway.events[-1]
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
        serialized = json.dumps(event, sort_keys=True)
        forbidden = (
            "PRIVATE QUESTION",
            "SECRET EVIDENCE",
            "reply",
            "prompt",
            "evidence",
            "message",
        )
        for sentinel in forbidden:
            with self.subTest(sentinel=sentinel):
                self.assertNotIn(sentinel, serialized)


if __name__ == "__main__":
    unittest.main()
