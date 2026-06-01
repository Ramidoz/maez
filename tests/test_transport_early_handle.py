import threading
import time
import unittest
from unittest import mock

import core.routing.llm_client as llm_client


class _BlockingRecvSocket:
    def __init__(self):
        self.closed = False
        self.shutdown_calls = 0
        self.sent = bytearray()
        self.recv_entered = threading.Event()
        self.release = threading.Event()

    def sendall(self, data):
        self.sent.extend(data)

    def recv(self, _n):
        self.recv_entered.set()
        self.release.wait(timeout=2.0)
        raise OSError("closed")

    def shutdown(self, _how):
        self.shutdown_calls += 1

    def close(self):
        self.closed = True
        self.release.set()


class EarlyHandleTest(unittest.TestCase):
    def test_handle_available_before_first_token_with_socket_transport(self):
        fake_socket = _BlockingRecvSocket()

        with (
            mock.patch.object(
                llm_client,
                "active_backend",
                return_value=llm_client.BACKEND_LLAMACPP,
            ),
            mock.patch.object(
                llm_client._socket,
                "create_connection",
                return_value=fake_socket,
            ),
        ):
            handle_box = {}

            def start():
                handle_box["call"] = llm_client.start_cancellable_chat(
                    model="m",
                    messages=[{"role": "user", "content": "x"}],
                    think=False,
                )

            worker = threading.Thread(target=start)
            worker.start()
            worker.join(timeout=0.5)

            self.assertIn("call", handle_box)
            self.assertTrue(hasattr(handle_box["call"], "cancel"))
            self.assertFalse(fake_socket.recv_entered.is_set())
            self.assertIn(b"POST /v1/chat/completions HTTP/1.1", fake_socket.sent)

            t0 = time.monotonic()
            handle_box["call"].cancel()
            self.assertLess((time.monotonic() - t0) * 1000, 800)
            self.assertTrue(fake_socket.closed)
            self.assertEqual(fake_socket.shutdown_calls, 1)


if __name__ == "__main__":
    unittest.main()
