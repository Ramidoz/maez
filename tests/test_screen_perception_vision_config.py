import importlib
import os
import unittest
from unittest import mock


class VisionConfigTests(unittest.TestCase):
    def _load(self, env):
        with mock.patch.dict(os.environ, env, clear=False):
            import skills.screen_perception as sp
            return importlib.reload(sp)

    def test_defaults_point_to_dedicated_vision_endpoint_not_judge(self):
        sp = self._load({
            "MAEZ_VISION_URL": "",
            "MAEZ_VISION_MODEL": "",
        })
        self.assertEqual("http://127.0.0.1:8082/v1/chat/completions", sp.VISION_URL)
        self.assertEqual("maez-vision", sp.VISION_MODEL)
        self.assertEqual("127.0.0.1", sp._VISION_PROBE_HOST)
        self.assertEqual(8082, sp._VISION_PROBE_PORT)

    def test_env_overrides_url_model_and_probe_port(self):
        sp = self._load({
            "MAEZ_VISION_URL": "http://127.0.0.1:8099/v1/chat/completions",
            "MAEZ_VISION_MODEL": "qwen3vl-4b-test",
        })
        self.assertEqual("http://127.0.0.1:8099/v1/chat/completions", sp.VISION_URL)
        self.assertEqual("qwen3vl-4b-test", sp.VISION_MODEL)
        self.assertEqual(8099, sp._VISION_PROBE_PORT)

    def test_docstring_no_longer_claims_qwen25_or_port_8081_vision_service(self):
        sp = self._load({})
        doc = sp.__doc__ or ""
        self.assertNotIn("Qwen2.5-VL-3B", doc)
        self.assertNotIn("port 8081", doc)
        self.assertNotIn("llama-server-vision.service on port 8081", doc)


if __name__ == "__main__":
    unittest.main()
