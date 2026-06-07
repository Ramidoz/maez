import asyncio
import json
import os
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


class CacheContainmentTests(unittest.TestCase):
    def _cache(self):
        from skills.surface.platform_base import get_image_cache_dir

        return get_image_cache_dir()

    def test_in_cache_ok(self):
        path = os.path.join(self._cache(), "vt_test.png")
        with open(path, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
        try:
            self.assertTrue(vision_tools._valid_cache_image(path))
        finally:
            os.unlink(path)

    def test_rejects_outside_cache_and_schemes(self):
        for bad in (
            "/etc/passwd",
            "http://x/y.png",
            "https://x/y.png",
            "../../etc/passwd",
            "/tmp/elsewhere.png",
            "nonexistent.png",
        ):
            self.assertFalse(vision_tools._valid_cache_image(bad), bad)

    def test_rejects_symlink_escape(self):
        link = os.path.join(self._cache(), "vt_escape.png")
        try:
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink("/etc/passwd", link)
            self.assertFalse(vision_tools._valid_cache_image(link))
        finally:
            if os.path.lexists(link):
                os.unlink(link)

    def test_invalid_cache_path_fails_before_reading(self):
        with mock.patch.object(vision_tools, "open", create=True) as mocked_open:
            out = json.loads(run(vision_tools.vision_analyze_tool("/etc/passwd", "describe")))

        self.assertFalse(out["success"])
        self.assertEqual(out["error"], "image_not_in_cache")
        mocked_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
