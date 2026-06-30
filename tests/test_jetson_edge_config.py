import os
import unittest
from unittest import mock

import tests._jetson_edge_path  # noqa: F401
from jetson_presence import config


class ConfigTests(unittest.TestCase):
    def test_defaults_when_env_absent(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = config.load_config()
            self.assertEqual(cfg.host_url, "http://127.0.0.1:11437")
            self.assertEqual(cfg.intake_path, "/api/v1/presence/jetson/intake")
            self.assertEqual(cfg.device_index, 0)
            self.assertEqual(cfg.token, "")
            self.assertEqual(cfg.curtain_sentinel, "/run/maez/jetson_curtain")
            self.assertEqual(cfg.cadence_seconds, 5)

    def test_env_overrides(self):
        env = {
            "MAEZ_JETSON_HOST_URL": "http://10.0.0.5:11437",
            "MAEZ_JETSON_DEVICE_TOKEN": "tok-abc",
            "MAEZ_JETSON_CURTAIN_SENTINEL": "/run/maez/curtain",
            "MAEZ_JETSON_DEVICE_INDEX": "1",
            "MAEZ_JETSON_CADENCE_SECONDS": "0.25",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = config.load_config()
            self.assertEqual(cfg.host_url, "http://10.0.0.5:11437")
            self.assertEqual(cfg.token, "tok-abc")
            self.assertEqual(cfg.curtain_sentinel, "/run/maez/curtain")
            self.assertEqual(cfg.device_index, 1)
            self.assertEqual(cfg.cadence_seconds, 0.25)

    def test_token_is_never_a_literal_in_source(self):
        import inspect

        src = inspect.getsource(config)
        self.assertNotIn("MAEZ_JETSON_DEVICE_TOKEN=", src)


if __name__ == "__main__":
    unittest.main()
