import threading
import time
import unittest

from core.routing.llm_client import BackendError, _LlamaCppSocketStream


def _chunk(body: bytes) -> bytes:
    return f"{len(body):x}\r\n".encode("ascii") + body + b"\r\n"


def _wire(*events: bytes) -> bytes:
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Transfer-Encoding: chunked\r\n\r\n"
        + b"".join(_chunk(event) for event in events)
        + b"0\r\n\r\n"
    )


def _slices(data: bytes, sizes=(3, 1, 8, 2, 13, 5, 89)):
    out = []
    pos = 0
    idx = 0
    while pos < len(data):
        n = sizes[idx % len(sizes)]
        out.append(data[pos : pos + n])
        pos += n
        idx += 1
    return out


class _FakeSocket:
    def __init__(self, script: list[bytes], block_event=None):
        self._script = list(script)
        self._block = block_event
        self.shutdown_calls = 0
        self.closed = False
        self.sent = bytearray()

    def sendall(self, data):
        self.sent.extend(data)

    def recv(self, _n):
        if self.closed:
            raise OSError("socket closed")
        if self._script:
            return self._script.pop(0)
        if self._block is not None:
            self._block.wait(timeout=2.0)
            raise OSError("closed during block")
        return b""

    def shutdown(self, _how):
        self.shutdown_calls += 1

    def close(self):
        self.closed = True
        if self._block is not None:
            self._block.set()


class SocketStreamTest(unittest.TestCase):
    def test_iterates_tokens(self):
        wire = _wire(
            b'data: {"choices":[{"delta":{"content":"O"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"K"}}]}\n\n',
            b"data: [DONE]\n\n",
        )
        stream = _LlamaCppSocketStream(sock=_FakeSocket(_slices(wire)))
        self.assertEqual("".join(chunk.message.content for chunk in stream), "OK")

    def test_close_is_idempotent_and_shuts_down(self):
        fake_socket = _FakeSocket([])
        stream = _LlamaCppSocketStream(sock=fake_socket)

        stream.close()
        stream.close()

        self.assertTrue(fake_socket.closed)
        self.assertEqual(fake_socket.shutdown_calls, 1)

    def test_close_unblocks_iteration_cleanly(self):
        block = threading.Event()
        fake_socket = _FakeSocket(
            [b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"],
            block_event=block,
        )
        stream = _LlamaCppSocketStream(sock=fake_socket)
        out = []
        errors = []

        def run():
            try:
                for chunk in stream:
                    out.append(chunk.message.content)
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=run)
        worker.start()
        time.sleep(0.1)
        stream.close()
        worker.join(timeout=2.0)

        self.assertFalse(worker.is_alive())
        self.assertEqual(out, [])
        self.assertEqual(errors, [])

    def test_uncancelled_truncated_stream_raises(self):
        fake_socket = _FakeSocket(
            [b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"]
        )
        stream = _LlamaCppSocketStream(sock=fake_socket)

        with self.assertRaises(BackendError):
            list(stream)


if __name__ == "__main__":
    unittest.main()
