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

    def test_process_truth_redacts_sensitive_env_values(self):
        from core.cockpit.state import RuntimePaths, build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc_root = root / "proc"
            environ = b"MAEZ_TELEGRAM_TOKEN=real-token\0MAEZ_BODY_LEGIBILITY=1\0"
            (proc_root / "123" / "environ").parent.mkdir(parents=True)
            (proc_root / "123" / "environ").write_bytes(environ)

            state = build_state(
                runtime=RuntimePaths(root / "memory", root / "logs", root / "config"),
                command_runner=lambda _cmd: "123\n",
                proc_root=proc_root,
            )

        flags = state["processes"]["daemon"]["env_flags"]
        self.assertEqual(flags["MAEZ_TELEGRAM_TOKEN"], "[redacted]")
        self.assertEqual(flags["MAEZ_BODY_LEGIBILITY"], "1")
        self.assertNotIn("real-token", str(state))

    def test_flag_registry_state_includes_file_process_divergence(self):
        from core.cockpit.state import RuntimePaths, build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config"
            config.mkdir()
            (config / "model.env").write_text(
                "MAEZ_BODY_LEGIBILITY=1\nMAEZ_TELEGRAM_TOKEN=file-token\n",
                encoding="utf-8",
            )
            proc_root = root / "proc"
            environ = b"MAEZ_BODY_LEGIBILITY=0\0MAEZ_TELEGRAM_TOKEN=proc-token\0"
            (proc_root / "123" / "environ").parent.mkdir(parents=True)
            (proc_root / "123" / "environ").write_bytes(environ)

            state = build_state(
                runtime=RuntimePaths(root / "memory", root / "logs", config),
                command_runner=lambda _cmd: "123\n",
                proc_root=proc_root,
            )

        by_name = {row["name"]: row for row in state["flags"]["file_process"]}
        self.assertEqual(by_name["MAEZ_BODY_LEGIBILITY"]["sync_state"], "mismatch")
        self.assertEqual(by_name["MAEZ_BODY_LEGIBILITY"]["file_value"], "1")
        self.assertEqual(by_name["MAEZ_BODY_LEGIBILITY"]["process_value"], "0")
        self.assertEqual(by_name["MAEZ_TELEGRAM_TOKEN"]["sync_state"], "mismatch")
        self.assertEqual(by_name["MAEZ_TELEGRAM_TOKEN"]["file_value"], "[redacted]")
        self.assertEqual(by_name["MAEZ_TELEGRAM_TOKEN"]["process_value"], "[redacted]")
        self.assertIn("MAEZ_COCKPIT_V2", state["flags"]["registry"])
        self.assertEqual(
            state["flags"]["registry"]["MAEZ_COCKPIT_V2"]["owner_review_status"],
            "pending_owner_review",
        )

    def test_flag_registry_uses_explicit_model_env_path_not_repo_config_by_default(self):
        from core.cockpit.state import RuntimePaths, build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config"
            owner_config = root / "owner-config"
            config.mkdir()
            owner_config.mkdir()
            (config / "model.env").write_text(
                "MAEZ_BODY_LEGIBILITY=0\n",
                encoding="utf-8",
            )
            model_env = owner_config / "model.env"
            model_env.write_text("MAEZ_BODY_LEGIBILITY=1\n", encoding="utf-8")

            state = build_state(
                runtime=RuntimePaths(
                    root / "memory",
                    root / "logs",
                    config,
                    model_env_file=model_env,
                ),
                command_runner=lambda _cmd: "0\n",
            )

        by_name = {row["name"]: row for row in state["flags"]["file_process"]}
        self.assertEqual(state["flags"]["file_env_path"], str(model_env))
        self.assertEqual(by_name["MAEZ_BODY_LEGIBILITY"]["file_value"], "1")

    def test_flag_registry_observed_includes_code_inventory(self):
        from core.cockpit.state import RuntimePaths, build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            code_root = root / "code"
            code_root.mkdir()
            (code_root / "feature.py").write_text(
                'strict_env_flag("MAEZ_CODE_ONLY_FOR_COCKPIT")\n',
                encoding="utf-8",
            )

            state = build_state(
                runtime=RuntimePaths(
                    root / "memory",
                    root / "logs",
                    root / "config",
                    code_roots=(code_root,),
                ),
                command_runner=lambda _cmd: "0\n",
            )

        observed = {row["name"]: row for row in state["flags"]["observed"]}
        self.assertEqual(
            observed["MAEZ_CODE_ONLY_FOR_COCKPIT"]["sources"],
            ["code"],
        )
        self.assertIn(
            "MAEZ_CODE_ONLY_FOR_COCKPIT",
            state["flags"]["unclassified_observed"],
        )

    def test_flag_registry_does_not_hide_daemon_web_process_disagreement(self):
        from core.cockpit.state import RuntimePaths, build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config"
            config.mkdir()
            (config / "model.env").write_text(
                "MAEZ_BODY_LEGIBILITY=0\n",
                encoding="utf-8",
            )
            proc_root = root / "proc"
            (proc_root / "111" / "environ").parent.mkdir(parents=True)
            (proc_root / "222" / "environ").parent.mkdir(parents=True)
            (proc_root / "111" / "environ").write_bytes(
                b"MAEZ_BODY_LEGIBILITY=1\0"
            )
            (proc_root / "222" / "environ").write_bytes(
                b"MAEZ_BODY_LEGIBILITY=0\0"
            )

            def runner(cmd):
                if cmd[-1] == "maez.service":
                    return "111\n"
                if cmd[-1] == "maez-web.service":
                    return "222\n"
                raise AssertionError(cmd)

            state = build_state(
                runtime=RuntimePaths(root / "memory", root / "logs", config),
                command_runner=runner,
                proc_root=proc_root,
            )

        by_name = {row["name"]: row for row in state["flags"]["file_process"]}
        row = by_name["MAEZ_BODY_LEGIBILITY"]
        self.assertEqual(row["sync_state"], "mismatch")
        self.assertEqual(row["file_value"], "0")
        self.assertEqual(row["process_value"], "mixed")
        self.assertEqual(row["process_values"], {"daemon": "1", "web": "0"})

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
