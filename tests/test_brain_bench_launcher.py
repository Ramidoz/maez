import os
import unittest
from unittest import mock

from scripts.brain_bench import launcher


class LauncherEnvTests(unittest.TestCase):
    def test_launcher_rewrites_known_path_bearing_env_before_exec(self):
        with mock.patch.object(launcher.os, "execv", side_effect=RuntimeError("stop")):
            with self.assertRaises(RuntimeError):
                launcher.main(
                    [
                        "/tmp/brain-bench-sandbox",
                        "--x",
                    ]
                )

        self.assertEqual(os.environ["MAEZ_HOME"], "/tmp/brain-bench-sandbox")
        self.assertEqual(os.environ["MAEZ_LEDGER_DB_PATH"], "/tmp/brain-bench-sandbox/memory/ledger.db")
        self.assertEqual(
            os.environ["MAEZ_ROUTING_OBSERVATION_DB_PATH"],
            "/tmp/brain-bench-sandbox/memory/routing_observation.db",
        )
        self.assertEqual(
            os.environ["MAEZ_SELF_AWARENESS_PATH"],
            "/tmp/brain-bench-sandbox/memory/self_awareness.json",
        )


if __name__ == "__main__":
    unittest.main()
