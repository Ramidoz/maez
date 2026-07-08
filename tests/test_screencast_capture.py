import json
import os
import stat
import sys
import tempfile
import types
from unittest import mock
import unittest

import scripts.screencast_capture as sc


class OutputContractTests(unittest.TestCase):
    def test_module_imports_without_gi(self):
        import sys

        self.assertNotIn("gi", [m for m in sys.modules if m == "gi"])

    def test_emit_shape(self):
        out = sc._result(
            status="ok",
            temp_path="/tmp/maez-screencast-x.png",
            bytes_=123,
            duration_ms=42,
        )
        self.assertEqual(
            set(out.keys()),
            {"status", "temp_path", "bytes", "duration_ms", "error_class"},
        )
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["bytes"], 123)
        self.assertEqual(out["error_class"], "")

    def test_emit_is_json_serializable_and_tokenless(self):
        out = sc._result(
            status="ok",
            temp_path="/tmp/maez-screencast-x.png",
            bytes_=1,
            duration_ms=1,
        )
        s = json.dumps(out)
        self.assertNotIn("token", s.lower())


class CurtainTests(unittest.TestCase):
    def test_curtain_drawn_short_circuits(self):
        with mock.patch.object(
            sc.os.path,
            "exists",
            lambda p: p == sc.CURTAIN_PATH,
        ):
            out = sc.capture()
        self.assertEqual(out["status"], "curtain_drawn")
        self.assertIsNone(out["temp_path"])

    def test_no_gi_import_when_curtain_drawn(self):
        import sys

        sys.modules.pop("gi", None)
        with mock.patch.object(
            sc.os.path,
            "exists",
            lambda p: p == sc.CURTAIN_PATH,
        ):
            sc.capture()
        self.assertNotIn("gi", sys.modules)


class TokenTests(unittest.TestCase):
    def test_save_token_is_0600(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "tok")
        with mock.patch.object(sc, "TOKEN_PATH", path):
            sc._save_token("SECRET-RESTORE-TOKEN")
            mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o600)

    def test_load_token_roundtrip_and_absent(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "tok")
        with mock.patch.object(sc, "TOKEN_PATH", path):
            self.assertIsNone(sc._load_token())
            sc._save_token("T")
            self.assertEqual(sc._load_token(), "T")


class RevokeTests(unittest.TestCase):
    def test_revoke_deletes_token_and_draws_curtain(self):
        d = tempfile.mkdtemp()
        tok = os.path.join(d, "tok")
        cur = os.path.join(d, "curtain")
        with mock.patch.object(sc, "TOKEN_PATH", tok), mock.patch.object(
            sc,
            "CURTAIN_PATH",
            cur,
        ):
            sc._save_token("T")
            out = sc.revoke()
            self.assertFalse(os.path.exists(tok))
            self.assertTrue(os.path.exists(cur))
        self.assertEqual(out["status"], "curtain_drawn")


class NoLeakTests(unittest.TestCase):
    def test_live_exception_maps_to_stage_no_traceback(self):
        secret = "RAW-PORTAL-HANDLE-9d2f"
        with mock.patch.object(
            sc,
            "_capture_live",
            side_effect=RuntimeError(secret),
        ), mock.patch.object(sc, "_curtain_drawn", return_value=False):
            out = sc.safe_capture()
        self.assertEqual(out["status"], "capture_failed")
        self.assertIn(
            out["error_class"],
            {"portal", "pipewire", "gst", "timeout", "permission_denied"},
        )
        self.assertNotIn(secret, json.dumps(out))


class LiveFailureRecoveryTests(unittest.TestCase):
    def test_restore_token_gst_failure_retries_once_without_token(self):
        d = tempfile.mkdtemp()
        token_path = os.path.join(d, "tok")
        tmp_path = os.path.join(d, "frame.png")
        session_calls = []
        grab_calls = []

        def fake_session(token):
            session_calls.append(token)
            if len(session_calls) == 1:
                return 41, 8, None
            return 42, 9, "fresh-token"

        def fake_grab(fd, node_id, tmp):
            grab_calls.append((fd, node_id))
            if len(grab_calls) == 1:
                raise sc._StageError("gst")
            with open(tmp, "wb") as f:
                f.write(b"PNGDATA")

        with mock.patch.object(sc, "TOKEN_PATH", token_path), mock.patch.object(
            sc,
            "_curtain_drawn",
            return_value=False,
        ), mock.patch.object(sc.tempfile, "mktemp", return_value=tmp_path), mock.patch.object(
            sc,
            "_portal_screencast_session",
            side_effect=fake_session,
        ), mock.patch.object(sc, "_grab_one_frame_pipewire", side_effect=fake_grab):
            sc._save_token("stale-token")
            out = sc.capture()

        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["bytes"], 7)
        self.assertEqual(session_calls, ["stale-token", None])
        self.assertEqual(grab_calls, [(8, 41), (9, 42)])
        with open(token_path, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "fresh-token")

    def test_portal_setup_exception_classifies_as_portal_not_gst(self):
        with mock.patch.object(sc, "_curtain_drawn", return_value=False), mock.patch.object(
            sc,
            "_portal_screencast_session",
            side_effect=RuntimeError("Could not connect: Operation not permitted"),
        ):
            out = sc.capture()

        self.assertEqual(out["status"], "capture_failed")
        self.assertEqual(out["error_class"], "portal")


class PortalWaitTests(unittest.TestCase):
    def test_portal_request_subscribes_before_calling_fast_method(self):
        events = []
        response_callback = None

        class FakeParams:
            def unpack(self):
                return (0, {"session_handle": "SESSION"})

        class FakeConnection:
            def get_unique_name(self):
                return ":1.234"

            def signal_subscribe(self, *args):
                nonlocal response_callback
                events.append(("subscribe", args[3]))
                response_callback = args[6]
                return 7

            def signal_unsubscribe(self, sub_id):
                events.append(("unsubscribe", sub_id))

        class FakeProxy:
            def __init__(self):
                self.connection = FakeConnection()

            def get_connection(self):
                return self.connection

            def call_sync(self, *args):
                events.append(("call", args[0]))
                response_callback(None, None, None, None, None, FakeParams(), None)

                class Handle:
                    def unpack(self):
                        return (
                            "/org/freedesktop/portal/desktop/request/1_234/maez_create_TOKEN",
                        )

                return Handle()

        class FakeLoop:
            def run(self):
                events.append(("run", None))

            def quit(self):
                events.append(("quit", None))

        class FakeGio:
            class DBusCallFlags:
                NONE = object()

            class DBusSignalFlags:
                NONE = object()

        class FakeGLib:
            @staticmethod
            def MainLoop():
                return FakeLoop()

            @staticmethod
            def timeout_add(_ms, _callback):
                return 99

            @staticmethod
            def source_remove(source_id):
                events.append(("remove", source_id))

        gi = types.ModuleType("gi")
        repository = types.ModuleType("gi.repository")
        repository.Gio = FakeGio
        repository.GLib = FakeGLib
        with mock.patch.dict(sys.modules, {"gi": gi, "gi.repository": repository}):
            results = sc._portal_request(
                FakeProxy(),
                "CreateSession",
                object(),
                handle_token="maez_create_TOKEN",
            )

        self.assertEqual(results, {"session_handle": "SESSION"})
        self.assertLess(events.index(("subscribe", "/org/freedesktop/portal/desktop/request/1_234/maez_create_TOKEN")), events.index(("call", "CreateSession")))

    def test_timeout_does_not_remove_expired_source(self):
        class FakeConnection:
            def signal_subscribe(self, *args):
                return 44

            def signal_unsubscribe(self, sub_id):
                self.unsubscribed = sub_id

        class FakeLoop:
            def run(self):
                timeout_callback()

            def quit(self):
                self.quit_called = True

        timeout_callback = None
        removed_sources = []

        class FakeGio:
            class BusType:
                SESSION = object()

            class DBusSignalFlags:
                NONE = object()

            @staticmethod
            def bus_get_sync(_bus_type, _cancellable):
                return FakeConnection()

        class FakeGLib:
            @staticmethod
            def MainLoop():
                return FakeLoop()

            @staticmethod
            def timeout_add(_ms, callback):
                nonlocal timeout_callback
                timeout_callback = callback
                return 99

            @staticmethod
            def source_remove(source_id):
                removed_sources.append(source_id)

        gi = types.ModuleType("gi")
        repository = types.ModuleType("gi.repository")
        repository.Gio = FakeGio
        repository.GLib = FakeGLib
        with mock.patch.dict(sys.modules, {"gi": gi, "gi.repository": repository}):
            with self.assertRaises(sc._StageError) as cm:
                sc._wait_request_response(
                    FakeConnection(),
                    "/org/freedesktop/portal/desktop/request/x/y",
                    lambda: None,
                )

        self.assertEqual(cm.exception.stage, "timeout")
        self.assertEqual(removed_sources, [])
