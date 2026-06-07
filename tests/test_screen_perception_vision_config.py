import importlib
import os
import unittest
from contextlib import contextmanager


VISION_ENV_KEYS = (
    "MAEZ_VISION_URL",
    "MAEZ_VISION_MODEL",
    "MAEZ_VISION_MAX_DIM",
)
DEFAULT_VISION_URL = "http://127.0.0.1:8082/v1/chat/completions"


def _snapshot_vision_env():
    return {key: os.environ.get(key) for key in VISION_ENV_KEYS}


def _restore_vision_env(snapshot):
    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _apply_vision_env(env):
    for key in VISION_ENV_KEYS:
        os.environ.pop(key, None)
    for key, value in env.items():
        os.environ[key] = value


class VisionConfigTests(unittest.TestCase):
    @contextmanager
    def _load(self, env):
        snapshot = _snapshot_vision_env()
        try:
            _apply_vision_env(env)
            import skills.screen_perception as sp

            yield importlib.reload(sp)
        finally:
            _restore_vision_env(snapshot)
            import skills.screen_perception as sp

            importlib.reload(sp)

    def test_defaults_point_to_dedicated_vision_endpoint_not_judge(self):
        with self._load(
            {
                "MAEZ_VISION_URL": "",
                "MAEZ_VISION_MODEL": "",
            }
        ) as sp:
            self.assertEqual(DEFAULT_VISION_URL, sp.VISION_URL)
            self.assertEqual("maez-vision", sp.VISION_MODEL)
            self.assertEqual("127.0.0.1", sp._VISION_PROBE_HOST)
            self.assertEqual(8082, sp._VISION_PROBE_PORT)

    def test_env_overrides_url_model_and_probe_port(self):
        with self._load(
            {
                "MAEZ_VISION_URL": "http://127.0.0.1:8099/v1/chat/completions",
                "MAEZ_VISION_MODEL": "qwen3vl-4b-test",
            }
        ) as sp:
            self.assertEqual("http://127.0.0.1:8099/v1/chat/completions", sp.VISION_URL)
            self.assertEqual("qwen3vl-4b-test", sp.VISION_MODEL)
            self.assertEqual(8099, sp._VISION_PROBE_PORT)

    def test_invalid_max_dim_falls_back_to_default_and_import_succeeds(self):
        with self._load({"MAEZ_VISION_MAX_DIM": "wide"}) as sp:
            self.assertEqual(640, sp.VISION_MAX_DIM)

    def test_non_positive_max_dim_falls_back_to_default(self):
        for raw in ("0", "-1"):
            with self.subTest(raw=raw), self._load({"MAEZ_VISION_MAX_DIM": raw}) as sp:
                self.assertEqual(640, sp.VISION_MAX_DIM)

    def test_schemeless_url_normalizes_and_probe_uses_port(self):
        with self._load(
            {
                "MAEZ_VISION_URL": "localhost:8082/v1/chat/completions",
            }
        ) as sp:
            self.assertEqual("http://localhost:8082/v1/chat/completions", sp.VISION_URL)
            self.assertEqual("localhost", sp._VISION_PROBE_HOST)
            self.assertEqual(8082, sp._VISION_PROBE_PORT)

    def test_invalid_port_url_falls_back_to_default_without_crashing(self):
        with self._load(
            {
                "MAEZ_VISION_URL": "http://127.0.0.1:bad/v1",
            }
        ) as sp:
            self.assertEqual(DEFAULT_VISION_URL, sp.VISION_URL)
            self.assertEqual("127.0.0.1", sp._VISION_PROBE_HOST)
            self.assertEqual(8082, sp._VISION_PROBE_PORT)

    def test_load_helper_restores_module_after_patched_reload(self):
        snapshot = _snapshot_vision_env()
        try:
            _apply_vision_env({})
            import skills.screen_perception as sp

            importlib.reload(sp)
            with self._load(
                {
                    "MAEZ_VISION_URL": "http://127.0.0.1:8099/v1/chat/completions",
                }
            ) as loaded:
                self.assertEqual(
                    "http://127.0.0.1:8099/v1/chat/completions",
                    loaded.VISION_URL,
                )

            import skills.screen_perception as restored

            self.assertEqual(DEFAULT_VISION_URL, restored.VISION_URL)
            self.assertEqual(8082, restored._VISION_PROBE_PORT)
        finally:
            _restore_vision_env(snapshot)
            import skills.screen_perception as sp

            importlib.reload(sp)

    def test_docstring_no_longer_claims_qwen25_or_port_8081_vision_service(self):
        with self._load({}) as sp:
            doc = sp.__doc__ or ""
            self.assertNotIn("Qwen2.5-VL-3B", doc)
            self.assertNotIn("port 8081", doc)
            self.assertNotIn("llama-server-vision.service on port 8081", doc)


if __name__ == "__main__":
    unittest.main()
