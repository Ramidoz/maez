import asyncio
import json
import unittest
from unittest import mock

from tools import vision_tools


def run(coro):
    return asyncio.run(coro)


class ContractTests(unittest.TestCase):
    def test_result_shape(self):
        out = vision_tools._result(success=True, analysis="a cat on a desk")

        self.assertEqual(set(out), {"success", "analysis", "error"})
        self.assertTrue(out["success"])
        self.assertEqual(out["analysis"], "a cat on a desk")
        self.assertEqual(out["error"], "")

    def test_emit_is_json_string(self):
        s = vision_tools._emit(vision_tools._result(success=False, error="x"))

        d = json.loads(s)
        self.assertFalse(d["success"])
        self.assertEqual(d["analysis"], "")
        self.assertEqual(d["error"], "x")


class LoopbackGateTests(unittest.TestCase):
    def test_remote_url_refused_zero_bytes(self):
        with mock.patch.object(
            vision_tools,
            "VISION_URL",
            "http://10.0.0.5:8082/v1/chat/completions",
            create=True,
        ), mock.patch.object(vision_tools, "requests", create=True) as rq:
            out = json.loads(run(vision_tools.vision_analyze_tool("/tmp/x.png", "describe")))

        self.assertFalse(out["success"])
        self.assertEqual(out["error"], "non_local_vision_endpoint")
        rq.post.assert_not_called()

    def test_loopback_allowed(self):
        for url in (
            "http://127.0.0.1:8082/v1/chat/completions",
            "http://localhost:8082/v1/chat/completions",
            "http://[::1]:8082/v1/chat/completions",
        ):
            self.assertTrue(vision_tools._is_loopback_url(url), url)
        self.assertFalse(vision_tools._is_loopback_url("http://example.com/x"))


if __name__ == "__main__":
    unittest.main()
