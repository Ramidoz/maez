import unittest

from core.routing.llm_client import BackendError, _LlamaCppStreamParser


def _chunk(body: bytes) -> bytes:
    return f"{len(body):x}\r\n".encode("ascii") + body + b"\r\n"


def _build_wire(*sse_events: bytes) -> bytes:
    head = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/event-stream\r\n"
        b"Transfer-Encoding: chunked\r\n\r\n"
    )
    return head + b"".join(_chunk(event) for event in sse_events) + b"0\r\n\r\n"


WIRE = _build_wire(
    b'data: {"choices":[{"delta":{"role":"assistant","content":null}}]}\n\n',
    b'data: {"choices":[{"delta":{"content":"On April "}}]}\n\n',
    b'data: {"choices":[{"delta":{"content":"27 [E1]"}}]}\n\n',
    b"data: [DONE]\n\n",
)


def _feed_in_slices(parser, data: bytes, n: int) -> str:
    out = []
    for i in range(0, len(data), n):
        out.extend(parser.feed(data[i : i + n]))
    return "".join(out)


class ParserTest(unittest.TestCase):
    def test_parses_whole_buffer(self):
        parser = _LlamaCppStreamParser()
        self.assertEqual(_feed_in_slices(parser, WIRE, len(WIRE)), "On April 27 [E1]")
        self.assertTrue(parser.done)

    def test_fragmentation_1_byte_at_a_time(self):
        parser = _LlamaCppStreamParser()
        self.assertEqual(_feed_in_slices(parser, WIRE, 1), "On April 27 [E1]")

    def test_fragmentation_adversarial_slices(self):
        for n in (2, 3, 5, 7, 13, 17, 64, 100):
            with self.subTest(n=n):
                parser = _LlamaCppStreamParser()
                self.assertEqual(_feed_in_slices(parser, WIRE, n), "On April 27 [E1]")

    def test_non_200_raises(self):
        parser = _LlamaCppStreamParser()
        with self.assertRaises(BackendError):
            parser.feed(b"HTTP/1.1 500 Internal Server Error\r\n\r\n")

    def test_malformed_chunk_size_without_cancel_raises(self):
        parser = _LlamaCppStreamParser()
        parser.feed(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
        with self.assertRaises(BackendError):
            parser.feed(b"nope\r\n")

    def test_malformed_json_without_cancel_raises(self):
        parser = _LlamaCppStreamParser()
        wire = _build_wire(b"data: {not json}\n\n")
        with self.assertRaises(BackendError):
            _feed_in_slices(parser, wire, len(wire))

    def test_empty_stream_without_cancel_raises_on_done(self):
        parser = _LlamaCppStreamParser()
        wire = _build_wire(b"data: [DONE]\n\n")
        with self.assertRaises(BackendError):
            _feed_in_slices(parser, wire, len(wire))

    def test_truncation_when_cancelled_is_silent(self):
        parser = _LlamaCppStreamParser()
        parser.cancelled = True
        partial = (
            b"HTTP/1.1 200 OK\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n"
            b"12\r\n"
            b"data: {trunc"
        )
        self.assertEqual("".join(parser.feed(partial)), "")


if __name__ == "__main__":
    unittest.main()
