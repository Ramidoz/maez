import tempfile
import unittest
from pathlib import Path


class CockpitV2StateTests(unittest.TestCase):
    def test_empty_runtime_tree_stays_empty_and_reports_no_data(self):
        from core.cockpit.state import RuntimePaths, build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = RuntimePaths(
                memory_dir=root / "memory",
                logs_dir=root / "logs",
                config_dir=root / "config",
            )

            state = build_state(
                runtime=runtime,
                command_runner=lambda _cmd: "0\n",
            )

            self.assertEqual(state["processes"]["daemon"]["status"], "unavailable")
            self.assertEqual(state["processes"]["daemon"]["pid"], 0)
            self.assertEqual(state["sources"]["a1_scar_tissue"]["status"], "no_data")
            self.assertEqual(state["sources"]["a2_continuity"]["status"], "no_data")
            self.assertEqual(state["sources"]["narrative"]["status"], "no_data")
            self.assertEqual(
                state["sources"]["interaction_preferences"]["status"], "no_data"
            )
            self.assertFalse(
                any(root.iterdir()), "read model must not create runtime files"
            )

    def test_process_truth_includes_pid_and_process_env_flags(self):
        from core.cockpit.state import RuntimePaths, build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc_root = root / "proc"
            environ = b"MAEZ_BODY_LEGIBILITY=1\0IGNORED=x\0MAEZ_COCKPIT_V2=0\0"
            (proc_root / "123" / "environ").parent.mkdir(parents=True)
            (proc_root / "123" / "environ").write_bytes(environ)

            def runner(cmd):
                if cmd[-1] == "maez.service":
                    return "123\n"
                if cmd[-1] == "maez-web.service":
                    return "0\n"
                raise AssertionError(cmd)

            state = build_state(
                runtime=RuntimePaths(root / "memory", root / "logs", root / "config"),
                command_runner=runner,
                proc_root=proc_root,
            )

            daemon = state["processes"]["daemon"]
            self.assertEqual(daemon["status"], "active")
            self.assertEqual(daemon["pid"], 123)
            self.assertEqual(
                daemon["env_flags"],
                {"MAEZ_BODY_LEGIBILITY": "1", "MAEZ_COCKPIT_V2": "0"},
            )
            self.assertEqual(state["processes"]["web"]["status"], "unavailable")

    def test_active_process_reports_env_unavailable_separately_from_empty_flags(self):
        from core.cockpit.state import RuntimePaths, build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            state = build_state(
                runtime=RuntimePaths(root / "memory", root / "logs", root / "config"),
                command_runner=lambda _cmd: "456\n",
                proc_root=root / "missing-proc",
            )

        daemon = state["processes"]["daemon"]
        self.assertEqual(daemon["status"], "active")
        self.assertEqual(daemon["pid"], 456)
        self.assertEqual(daemon["env_flags"], {})
        self.assertEqual(daemon["env_status"], "unavailable")

    def test_organs_are_grouped_by_room(self):
        from core.cockpit.state import RuntimePaths, build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = build_state(
                runtime=RuntimePaths(root / "memory", root / "logs", root / "config"),
                command_runner=lambda _cmd: "0\n",
            )

        rooms = {room["id"]: room for room in state["rooms"]}
        self.assertIn("memory", rooms)
        self.assertIn("self_knowledge", rooms)
        self.assertIn("honesty", rooms)
        organ_ids = {
            organ["id"] for room in rooms.values() for organ in room["organs"]
        }
        self.assertIn("a1_scar_tissue", organ_ids)
        self.assertIn("a2_continuity_fingerprint", organ_ids)
        self.assertIn("a6_self_evidence", organ_ids)
        self.assertIn("a7_interiority", organ_ids)


if __name__ == "__main__":
    unittest.main()
