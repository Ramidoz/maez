import threading
import time
import unittest
from unittest import mock

import core.routing.llm_client as llm_client
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

    def test_https_base_url_rejected(self):
        with self.assertRaises(BackendError):
            llm_client._connect_llamacpp_socket("https://127.0.0.1:8443/v1", b"{}")

    def test_socket_connect_failure_is_backend_error(self):
        with mock.patch.object(
            llm_client._socket,
            "create_connection",
            side_effect=OSError("refused"),
        ):
            with self.assertRaises(BackendError):
                llm_client._connect_llamacpp_socket("http://127.0.0.1:8080/v1", b"{}")

    def test_socket_send_failure_is_backend_error_and_closes(self):
        fake_socket = _FakeSocket([])

        def fail_send(_data):
            raise OSError("broken pipe")

        fake_socket.sendall = fail_send
        with mock.patch.object(
            llm_client._socket,
            "create_connection",
            return_value=fake_socket,
        ):
            with self.assertRaises(BackendError):
                llm_client._connect_llamacpp_socket("http://127.0.0.1:8080/v1", b"{}")
        self.assertTrue(fake_socket.closed)

    def test_endpoint_path_from_base_url(self):
        fake_socket = _FakeSocket([])

        with mock.patch.object(
            llm_client._socket,
            "create_connection",
            return_value=fake_socket,
        ) as create_connection:
            sock = llm_client._connect_llamacpp_socket(
                "http://127.0.0.1:8080/v1",
                b"{}",
            )

        self.assertIs(sock, fake_socket)
        create_connection.assert_called_once_with(("127.0.0.1", 8080), timeout=90)
        self.assertIn(b"POST /v1/chat/completions HTTP/1.1", fake_socket.sent)
        self.assertIn(b"Host: 127.0.0.1:8080\r\n", fake_socket.sent)
        self.assertIn(b"Content-Length: 2\r\n", fake_socket.sent)
        self.assertTrue(fake_socket.sent.endswith(b"\r\n\r\n{}"))


if __name__ == "__main__":
    unittest.main()
