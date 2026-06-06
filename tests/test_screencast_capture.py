import json
import os
import stat
import tempfile
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
