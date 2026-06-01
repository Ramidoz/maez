import json
import unittest

from core.routing.brain_gateway import BrainGateway, BrainPurpose
from core.routing.cancellable_brain_call import CancellableBrainCall
from core.routing.llm_client import _LlamaCppSocketStream


def _chunk(body: bytes) -> bytes:
    return f"{len(body):x}\r\n".encode("ascii") + body + b"\r\n"


def _wire(*events: bytes) -> bytes:
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Transfer-Encoding: chunked\r\n\r\n"
        + b"".join(_chunk(event) for event in events)
        + b"0\r\n\r\n"
    )


class _FakeSocket:
    def __init__(self, script: list[bytes]):
        self._script = list(script)
        self.closed = False

    def recv(self, _n):
        if self._script:
            return self._script.pop(0)
        return b""

    def shutdown(self, _how):
        return None

    def close(self):
        self.closed = True


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

    def test_socket_stream_buffered_reply_byte_equivalent(self):
        wire = _wire(
            b'data: {"choices":[{"delta":{"content":"On April 27 "}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"we noted "}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"the incident [E1]."}}]}\n\n',
            b"data: [DONE]\n\n",
        )
        stream = _LlamaCppSocketStream(
            sock=_FakeSocket([wire[:5], wire[5:41], wire[41:80], wire[80:]])
        )
        call = CancellableBrainCall(raw_stream=stream)

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
