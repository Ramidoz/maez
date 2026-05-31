import ast
import os
import socket
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from scripts.recall_flip_eval import sandbox


class IsolationTest(unittest.TestCase):
    def tearDown(self):
        sandbox.restore_memory_patches()
        os.environ.pop("MAEZ_LEDGER_DB_PATH", None)

    def test_assert_sandbox_aborts_when_paths_are_real_home(self):
        for key in ("MAEZ_HOME", "MAEZ_DATA", "MAEZ_CONFIG", "MAEZ_CACHE"):
            os.environ.pop(key, None)
        with self.assertRaises(sandbox.NotSandboxError):
            sandbox.assert_sandbox()

    def test_assert_sandbox_passes_under_sandbox_root(self):
        with tempfile.TemporaryDirectory() as root:
            with sandbox.sandbox_env(root):
                sandbox.patch_memory_manager_base_db(root)
                sandbox.assert_sandbox()

    def test_rejects_inherited_real_path_overrides(self):
        with tempfile.TemporaryDirectory() as root:
            with sandbox.sandbox_env(root):
                os.environ["MAEZ_LEDGER_DB_PATH"] = "/home/rohit/maez/memory/ledger.db"
                with self.assertRaises(sandbox.NotSandboxError):
                    sandbox.assert_no_real_path_overrides(root)

    def test_memory_manager_base_db_is_sandboxed_before_instantiation(self):
        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            module = sandbox.patch_memory_manager_base_db(root)
            self.assertTrue(str(module.BASE_DB).startswith(root), module.BASE_DB)
            sandbox.assert_sandbox()

    def test_last_consolidation_file_is_sandboxed_and_restored(self):
        import memory.memory_manager as mm_mod

        original = mm_mod.MemoryManager._LAST_CONSOLIDATION_FILE
        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            sandbox.patch_memory_manager_base_db(root)
            patched = mm_mod.MemoryManager._LAST_CONSOLIDATION_FILE
            self.assertTrue(str(patched).startswith(root), patched)
            sandbox.assert_sandbox()
            sandbox.restore_memory_patches()

        self.assertEqual(mm_mod.MemoryManager._LAST_CONSOLIDATION_FILE, original)

    def test_socket_guard_blocks_dns_and_outbound(self):
        with sandbox.no_egress():
            with self.assertRaises(sandbox.EgressBlockedError):
                socket.create_connection(("127.0.0.1", 9), timeout=0.1)
            with self.assertRaises(sandbox.EgressBlockedError):
                socket.getaddrinfo("example.com", 80)

    def test_seeded_dated_memory_is_visible_only_in_sandbox(self):
        before = sandbox.real_substrate_fingerprint()
        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            sandbox.patch_memory_manager_base_db(root)
            fixture_id = sandbox.seed_dated_memory(
                "multi_year",
                "v1",
                date=date(2026, 4, 27),
                content="SANDBOX SYNTHETIC TOKEN",
                tier="core",
                run_id="run-iso",
            )
            self.assertTrue(fixture_id.startswith("eval-multi_year-v1"))

            from memory.memory_manager import MemoryManager

            mm = MemoryManager()
            evidence, context = mm.recall_for_telegram_living(
                "What did we note around April 27?",
                record_recalls=False,
            )
            self.assertEqual(evidence, {"core": [], "daily": [], "raw": []})
            rows = context["core"]
            self.assertTrue(any(row["id"] == fixture_id for row in rows), rows)
            meta = next(row["metadata"] for row in rows if row["id"] == fixture_id)
            self.assertEqual(meta["temporal_match_method"], "exact_date")
            self.assertTrue(meta["date_confirmed"])

            sandbox.teardown(root)
        self.assertEqual(before, sandbox.real_substrate_fingerprint())

    def test_fingerprint_path_detects_same_size_rewrite(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "sentinel.txt"
            path.write_text("alpha")
            before = sandbox._fingerprint_path(path)
            stat = path.stat()
            path.write_text("bravo")
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))

            self.assertNotEqual(before, sandbox._fingerprint_path(path))

    def test_probe_battery_restores_paths_after_each_probe(self):
        import memory.memory_manager as mm_mod
        from scripts.recall_flip_eval import harness, probes

        with tempfile.TemporaryDirectory() as root, sandbox.sandbox_env(root):
            sandbox.patch_memory_manager_base_db(root)
            outer_sandbox_base = mm_mod.BASE_DB
            with mock.patch.object(harness, "run_probe", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    harness._run_probe_battery(
                        sandbox_root=Path(root),
                        probe=probes.get_probe("dated_hit"),
                        run_id="run-probe-restore",
                        variants_per_probe=1,
                        debug_dump_dir=None,
                    )

            self.assertEqual(mm_mod.BASE_DB, outer_sandbox_base)

    def test_launcher_has_no_core_memory_or_daemon_imports_before_exec(self):
        tree = ast.parse(Path("scripts/recall_flip_eval/launcher.py").read_text())
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        forbidden = [
            name
            for name in imported
            if name.split(".")[0] in {"core", "memory", "daemon"}
        ]
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()
