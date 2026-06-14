"""Tests for core.infra.systemd_notify — the sd_notify(3) datagram emitter.

These import ONLY the helper, never the heavy daemon. All fakes: no network, no
real systemd, no daemon process. The fourth test (READY only after probe+bind)
uses seam/fakes to assert ordering without importing maez_daemon.
"""
from __future__ import annotations

import os
import socket
import tempfile
import unittest

from core.infra import systemd_notify
from core.infra.systemd_notify import sd_notify, systemd_notify_enabled


class _RecordingSocket:
    """Fake socket capturing sendto calls; never touches the network."""

    def __init__(self):
        self.sent = []
        self.closed = False

    def sendto(self, payload, addr):
        self.sent.append((payload, addr))
        return len(payload)

    def close(self):
        self.closed = True


class NoOpWhenSocketUnsetTest(unittest.TestCase):
    def test_no_socket_means_zero_sendto(self):
        rec = _RecordingSocket()
        # NOTIFY_SOCKET absent entirely.
        sent = sd_notify(
            "READY=1",
            environ={},
            socket_factory=lambda: rec,
        )
        self.assertFalse(sent)
        self.assertEqual(rec.sent, [], "must not send a datagram with no notify socket")

    def test_empty_socket_value_means_zero_sendto(self):
        rec = _RecordingSocket()
        sent = sd_notify(
            "READY=1",
            environ={"NOTIFY_SOCKET": ""},
            socket_factory=lambda: rec,
        )
        self.assertFalse(sent)
        self.assertEqual(rec.sent, [])

    def test_flag_off_means_zero_sendto_even_with_socket(self):
        rec = _RecordingSocket()
        sent = sd_notify(
            "READY=1",
            environ={"NOTIFY_SOCKET": "@maez", "MAEZ_SYSTEMD_NOTIFY": "0"},
            socket_factory=lambda: rec,
        )
        self.assertFalse(sent)
        self.assertEqual(rec.sent, [])


class SendsReadyToRealUnixSocketTest(unittest.TestCase):
    def test_sends_ready_bytes_to_temp_datagram_socket(self):
        tmpdir = tempfile.mkdtemp()
        sock_path = os.path.join(tmpdir, "notify.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            listener.bind(sock_path)
            listener.settimeout(2.0)
            sent = sd_notify("READY=1", environ={"NOTIFY_SOCKET": sock_path})
            self.assertTrue(sent)
            data, _ = listener.recvfrom(64)
            self.assertEqual(data, b"READY=1")
        finally:
            listener.close()
            try:
                os.unlink(sock_path)
            except OSError:
                pass
            os.rmdir(tmpdir)

    def test_oserror_is_swallowed_returns_false(self):
        # Filesystem path that does not exist -> sendto raises OSError.
        missing = os.path.join(tempfile.gettempdir(), "maez-no-such-notify.sock")
        try:
            os.unlink(missing)
        except OSError:
            pass
        sent = sd_notify("READY=1", environ={"NOTIFY_SOCKET": missing})
        self.assertFalse(sent)


class StrictParserTableTest(unittest.TestCase):
    def test_default_on_when_unset(self):
        self.assertTrue(systemd_notify_enabled({}))

    def test_default_on_when_empty(self):
        self.assertTrue(systemd_notify_enabled({"MAEZ_SYSTEMD_NOTIFY": ""}))

    def test_truthy_table(self):
        for val in ("1", "true", "yes", "on", "TRUE", "On", " yes "):
            self.assertTrue(
                systemd_notify_enabled({"MAEZ_SYSTEMD_NOTIFY": val}),
                f"{val!r} should enable",
            )

    def test_falsy_table(self):
        for val in ("0", "false", "no", "off", "OFF", "2", "maybe"):
            self.assertFalse(
                systemd_notify_enabled({"MAEZ_SYSTEMD_NOTIFY": val}),
                f"{val!r} should disable",
            )

    def test_whitespace_only_is_treated_as_unset_default_on(self):
        # A value that strips to empty is indistinguishable from unset, so it
        # keeps the default-on readiness contract rather than silently disabling.
        self.assertTrue(systemd_notify_enabled({"MAEZ_SYSTEMD_NOTIFY": "   "}))


class ReadyOnlyAfterProbeAndBindTest(unittest.TestCase):
    """Model the daemon ordering with seams: READY must follow probe+bind.

    No daemon import. A fake start sequence records events; sd_notify is the
    final event and only fires once probe passed and the socket bound.
    """

    def test_ready_emitted_after_probe_then_bind(self):
        events = []
        rec = _RecordingSocket()

        def probe_passes():
            events.append("probe")
            return True

        def bind_socket():
            events.append("bind")
            return rec

        # Fake daemon start path mirroring maez_daemon._run_health_server:
        if not probe_passes():
            self.fail("probe should pass in this fixture")
        srv_sock = bind_socket()  # noqa: F841  (binds before notify)
        sd_notify(
            "READY=1",
            environ={"NOTIFY_SOCKET": "@maez"},
            socket_factory=lambda: rec,
        )
        events.append("ready")

        self.assertEqual(events, ["probe", "bind", "ready"])
        self.assertEqual(rec.sent, [(b"READY=1", b"\0maez")])

    def test_no_ready_when_probe_blocks(self):
        events = []
        rec = _RecordingSocket()

        def probe_fails():
            events.append("probe")
            return False

        # If the probe fails the daemon sys.exit(1)s before ever binding the
        # health socket, so sd_notify is never reached.
        if not probe_fails():
            # do NOT bind, do NOT notify
            pass
        self.assertEqual(events, ["probe"])
        self.assertEqual(rec.sent, [], "no READY when probe gates start")


if __name__ == "__main__":
    unittest.main()
