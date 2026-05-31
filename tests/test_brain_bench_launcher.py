import os
from pathlib import Path
import unittest
from unittest import mock

from scripts.brain_bench import launcher


class LauncherEnvTests(unittest.TestCase):
    def test_launcher_rewrites_known_path_bearing_env_before_exec(self):
        prior = os.environ.copy()
        try:
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
            self.assertEqual(os.environ["MAEZ_OWNER_TIMEZONE"], "America/Chicago")
        finally:
            os.environ.clear()
            os.environ.update(prior)

    def test_launcher_rejects_real_home_before_exec(self):
        for root in ("/home/rohit/maez", "/home/rohit", "/home"):
            with self.subTest(root=root):
                with mock.patch.object(launcher.os, "execv") as execv:
                    with self.assertRaises(SystemExit):
                        launcher.main([root, "--x"])
                execv.assert_not_called()

    def test_launcher_rejects_inherited_live_path_override(self):
        prior = os.environ.copy()
        os.environ["MAEZ_TRACE_DB_PATH"] = "/home/rohit/maez/memory/live.db"
        try:
            with mock.patch.object(launcher.os, "execv") as execv:
                with self.assertRaises(SystemExit):
                    launcher.main(["/tmp/brain-bench-sandbox", "--x"])
            execv.assert_not_called()
        finally:
            os.environ.clear()
            os.environ.update(prior)

    def test_launcher_has_no_maez_imports_before_exec(self):
        tree = __import__("ast").parse(Path(launcher.__file__).read_text())
        forbidden = ("core", "memory", "daemon")
        for node in tree.body:
            if isinstance(node, (__import__("ast").Import, __import__("ast").ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", ())]
                module = getattr(node, "module", "") or ""
                joined = " ".join([module, *names])
                self.assertFalse(any(joined.startswith(name) or f" {name}" in joined for name in forbidden), joined)
                self.assertNotIn("scripts.brain_bench.bench", joined)
                self.assertNotIn("scripts.brain_bench.probe_runner", joined)


if __name__ == "__main__":
    unittest.main()
