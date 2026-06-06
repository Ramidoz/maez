import json
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
