import asyncio
import base64
import io
import json
import os
import unittest
from pathlib import Path
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


class CallTests(unittest.TestCase):
    def _img(self, name="vt_big.png", size=(2000, 1500)):
        from PIL import Image

        path = os.path.join(self._cache(), name)
        Image.new("RGB", size, (10, 20, 30)).save(path)
        return path

    def _cache(self):
        from skills.surface.platform_base import get_image_cache_dir

        return get_image_cache_dir()

    def test_success_path_downscales_and_returns_analysis(self):
        from PIL import Image

        sent = {}

        class Resp:
            status_code = 200

            def json(self):
                return {"choices": [{"message": {"content": "a dark rectangle"}}]}

        def fake_post(url, json=None, timeout=None):
            sent["url"] = url
            sent["model"] = json["model"]
            image_url = json["messages"][0]["content"][1]["image_url"]["url"]
            sent["image_url"] = image_url
            raw = base64.b64decode(image_url.split(",", 1)[1])
            sent["size"] = Image.open(io.BytesIO(raw)).size
            return Resp()

        path = self._img()
        try:
            with mock.patch.object(vision_tools, "requests") as rq:
                rq.post.side_effect = fake_post
                out = json.loads(run(vision_tools.vision_analyze_tool(path, "describe")))

            self.assertTrue(out["success"])
            self.assertEqual(out["analysis"], "a dark rectangle")
            self.assertIn("127.0.0.1", sent["url"])
            self.assertEqual(sent["model"], vision_tools.VISION_MODEL)
            self.assertLessEqual(max(sent["size"]), 1024)
            self.assertTrue(sent["image_url"].startswith("data:image/png;base64,"))
        finally:
            os.unlink(path)

    def test_vision_down_is_honest(self):
        path = self._img("vt_down.png")
        try:
            with mock.patch.object(vision_tools, "requests") as rq:
                rq.post.side_effect = Exception("conn refused")
                out = json.loads(run(vision_tools.vision_analyze_tool(path, "describe")))

            self.assertFalse(out["success"])
            self.assertEqual(out["analysis"], "")
            self.assertEqual(out["error"], "vision_call_failed")
        finally:
            os.unlink(path)


class HeadlineRailTests(unittest.TestCase):
    def _cache(self):
        from skills.surface.platform_base import get_image_cache_dir

        return get_image_cache_dir()

    def _img(self):
        from PIL import Image

        path = os.path.join(self._cache(), "vt_rail_unique.png")
        Image.new("RGB", (32, 32), (121, 33, 17)).save(path)
        return path

    def _memory_files_outside_image_cache(self):
        cache = self._cache().resolve()
        root = Path("memory").resolve()
        if not root.exists():
            return set()
        files = set()
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                path.resolve().relative_to(cache)
                continue
            except ValueError:
                files.add(path.resolve())
        return files

    def test_image_payload_posts_only_to_loopback_vision_endpoint(self):
        calls = []

        class Resp:
            status_code = 200

            def json(self):
                return {"choices": [{"message": {"content": "small square"}}]}

        def fake_post(url, json=None, timeout=None):
            calls.append((url, json))
            return Resp()

        path = self._img()
        try:
            with mock.patch.object(vision_tools, "requests") as rq:
                rq.post.side_effect = fake_post
                out = json.loads(run(vision_tools.vision_analyze_tool(path, "describe")))

            self.assertTrue(out["success"])
            self.assertEqual(len(calls), 1)
            self.assertTrue(vision_tools._is_loopback_url(calls[0][0]))
            content = calls[0][1]["messages"][0]["content"]
            self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        finally:
            os.unlink(path)

    def test_analysis_creates_no_durable_image_copy(self):
        before = self._memory_files_outside_image_cache()

        class Resp:
            status_code = 200

            def json(self):
                return {"choices": [{"message": {"content": "small square"}}]}

        path = self._img()
        try:
            with mock.patch.object(vision_tools, "requests") as rq:
                rq.post.return_value = Resp()
                out = json.loads(run(vision_tools.vision_analyze_tool(path, "describe")))

            after = self._memory_files_outside_image_cache()
            self.assertTrue(out["success"])
            self.assertEqual(after, before)
            self.assertTrue(os.path.exists(path))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
