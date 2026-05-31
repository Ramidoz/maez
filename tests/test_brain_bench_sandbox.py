import socket
import unittest
from unittest import mock

from scripts.recall_flip_eval.sandbox import EgressBlockedError, no_egress


class EmptyAllowlistBlocksAllFiveAPIs(unittest.TestCase):
    def test_all_five_blocked_under_empty_allowlist(self):
        with no_egress():
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("127.0.0.1", 11434), timeout=0.01)

            stream = socket.socket()
            try:
                with self.assertRaises(EgressBlockedError):
                    stream.connect(("127.0.0.1", 11434))
                with self.assertRaises(EgressBlockedError):
                    stream.connect_ex(("127.0.0.1", 11434))
            finally:
                stream.close()

            datagram = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                with self.assertRaises(EgressBlockedError):
                    datagram.sendto(b"x", ("127.0.0.1", 11434))
            finally:
                datagram.close()

            with self.assertRaises(EgressBlockedError):
                socket.getaddrinfo("127.0.0.1", 11434)


class LoopbackAllowlistTests(unittest.TestCase):
    def test_allowed_loopback_covers_connect_and_connect_ex(self):
        with no_egress(allow_loopback_ports=(11434,)):
            for fn in ("create_connection", "connect", "connect_ex"):
                stream = socket.socket()
                try:
                    if fn == "create_connection":
                        socket.create_connection(("127.0.0.1", 11434), timeout=0.01)
                    elif fn == "connect":
                        stream.settimeout(0.01)
                        stream.connect(("127.0.0.1", 11434))
                    else:
                        stream.settimeout(0.01)
                        stream.connect_ex(("127.0.0.1", 11434))
                except EgressBlockedError:
                    self.fail(f"{fn} blocked on allowed loopback port")
                except OSError:
                    pass
                finally:
                    stream.close()

    def test_ipv6_tuple_allowed_only_for_allowed_loopback_port(self):
        with no_egress(allow_loopback_ports=(11434,)):
            stream = socket.socket(socket.AF_INET6)
            try:
                stream.settimeout(0.01)
                stream.connect(("::1", 11434, 0, 0))
            except EgressBlockedError:
                self.fail("IPv6 loopback tuple blocked on allowed port")
            except OSError:
                pass
            finally:
                stream.close()

            stream = socket.socket(socket.AF_INET6)
            try:
                with self.assertRaises(EgressBlockedError):
                    stream.connect(("2001:db8::1", 11434, 0, 0))
            finally:
                stream.close()

    def test_external_and_wrong_port_still_blocked(self):
        with no_egress(allow_loopback_ports=(11434,)):
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("8.8.8.8", 53), timeout=0.01)
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("127.0.0.1", 22), timeout=0.01)

    def test_phase_scoped_ports_are_never_open_together(self):
        variant_port = 11434
        judge_port = 8081
        with no_egress(allow_loopback_ports=(variant_port,)):
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("127.0.0.1", judge_port), timeout=0.01)
        with no_egress(allow_loopback_ports=(judge_port,)):
            with self.assertRaises(EgressBlockedError):
                socket.create_connection(("127.0.0.1", variant_port), timeout=0.01)

    def test_sendto_always_blocked_even_allowed_port(self):
        with no_egress(allow_loopback_ports=(11434,)):
            datagram = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                with self.assertRaises(EgressBlockedError):
                    datagram.sendto(b"x", ("127.0.0.1", 11434))
            finally:
                datagram.close()


class GetAddrInfoFilteringTests(unittest.TestCase):
    def test_getaddrinfo_filters_to_loopback_sockaddrs(self):
        mixed = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 11434)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 11434)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 11434, 0, 0)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 11434, 0, 0)),
        ]

        with mock.patch("socket.getaddrinfo", return_value=mixed):
            with no_egress(allow_loopback_ports=(11434,)):
                rows = socket.getaddrinfo("localhost", 11434)

        self.assertEqual([row[-1][0] for row in rows], ["127.0.0.1", "::1"])

    def test_getaddrinfo_raises_when_no_loopback_rows_remain(self):
        mixed = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 11434)),
        ]

        with mock.patch("socket.getaddrinfo", return_value=mixed):
            with no_egress(allow_loopback_ports=(11434,)):
                with self.assertRaises(EgressBlockedError):
                    socket.getaddrinfo("localhost", 11434)

    def test_getaddrinfo_blocks_external_and_wrong_port(self):
        with no_egress(allow_loopback_ports=(11434,)):
            with self.assertRaises(EgressBlockedError):
                socket.getaddrinfo("example.com", 11434)
            with self.assertRaises(EgressBlockedError):
                socket.getaddrinfo("localhost", 22)


class SocketGuardRestorationTests(unittest.TestCase):
    def test_all_socket_apis_restored_after_exception(self):
        originals = (
            socket.create_connection,
            socket.socket.connect,
            socket.socket.connect_ex,
            socket.socket.sendto,
            socket.getaddrinfo,
        )

        with self.assertRaises(RuntimeError):
            with no_egress(allow_loopback_ports=(11434,)):
                raise RuntimeError("boom")

        self.assertEqual(
            originals,
            (
                socket.create_connection,
                socket.socket.connect,
                socket.socket.connect_ex,
                socket.socket.sendto,
                socket.getaddrinfo,
            ),
        )


if __name__ == "__main__":
    unittest.main()
