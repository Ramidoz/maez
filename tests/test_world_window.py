from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path


class WorldWindowPureTests(unittest.TestCase):
    def _window(self, td: str):
        from core.cognition.world_window import WorldWindow

        return WorldWindow(Path(td) / "sig.json")

    def test_cold_start_emits_no_deltas_then_real_delta_shows(self):
        with tempfile.TemporaryDirectory() as td:
            window = self._window(td)
            first = window.deltas(
                {
                    "cpu": {"percent": 2.0, "temperature_c": 42.0, "core_count": 16},
                    "ram": {"percent": 31.0},
                }
            )
            self.assertEqual(first.deltas, ())
            self.assertTrue(first.cold_start)

            second = window.deltas(
                {
                    "cpu": {"percent": 82.0, "temperature_c": 81.0, "core_count": 16},
                    "ram": {"percent": 31.0},
                }
            )
            self.assertFalse(second.cold_start)
            self.assertTrue(any(delta.field == "cpu" for delta in second.deltas))

    def test_projection_is_coarse_never_raw_even_for_allowed_fields(self):
        with tempfile.TemporaryDirectory() as td:
            window = self._window(td)
            window.deltas(
                {
                    "gpu": {
                        "utilization_pct": 1.234567,
                        "memory_used_mb": 12345.678,
                        "memory_total_mb": 24576.0,
                        "temperature_c": 44.444,
                    },
                    "disk": {"/": {"percent": 12.345, "used_gb": 111.1, "total_gb": 999.9}},
                }
            )
            out = window.deltas(
                {
                    "gpu": {
                        "utilization_pct": 88.7654321,
                        "memory_used_mb": 22222.222,
                        "memory_total_mb": 24576.0,
                        "temperature_c": 79.999,
                    },
                    "disk": {"/": {"percent": 92.345, "used_gb": 888.8, "total_gb": 999.9}},
                }
            )
            rendered = " ".join(delta.phrase for delta in out.deltas)
            for raw in ("1.234567", "12345", "88.7654321", "22222", "92.345", "888.8"):
                self.assertNotIn(raw, rendered)
            self.assertIn("gpu availability or load band changed", rendered)
            self.assertIn("disk-use band changed", rendered)

    def test_sensitive_process_fields_never_emit_names_or_pids(self):
        with tempfile.TemporaryDirectory() as td:
            window = self._window(td)
            window.deltas(
                {
                    "top_processes_cpu": [
                        {"pid": 111, "name": "SECRET_BROWSER", "cpu_pct": 1.1, "mem_pct": 2.2}
                    ]
                }
            )
            out = window.deltas(
                {
                    "top_processes_cpu": [
                        {"pid": 222, "name": "PRIVATE_EDITOR", "cpu_pct": 9.9, "mem_pct": 3.3}
                    ]
                }
            )
            rendered = " ".join(delta.phrase for delta in out.deltas)
            self.assertIn("active process set changed", rendered)
            self.assertNotIn("SECRET_BROWSER", rendered)
            self.assertNotIn("PRIVATE_EDITOR", rendered)
            self.assertNotIn("222", rendered)

    def test_raw_private_and_unclassified_fields_are_excluded_content_light(self):
        with tempfile.TemporaryDirectory() as td:
            window = self._window(td)
            window.deltas({"screen_text": "SECRET SCREEN A", "future_field": "PRIVATE VALUE A"})
            out = window.deltas({"screen_text": "SECRET SCREEN B", "future_field": "PRIVATE VALUE B"})
            rendered = " ".join(delta.phrase for delta in out.deltas)
            exclusions = {(item.field, item.reason) for item in out.exclusions}
            self.assertNotIn("SECRET", rendered)
            self.assertNotIn("PRIVATE VALUE", rendered)
            self.assertIn(("screen_text", "raw_private"), exclusions)
            self.assertIn(("future_field", "unclassified"), exclusions)

    def test_module_imports_no_command_or_producer_or_downstream_writers(self):
        src = Path("core/cognition/world_window.py").read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        forbidden = {
            "core.evolution.drive_driven_curiosity",
            "core.actions.action_engine",
            "core.evolution.wonderings",
            "core.evolution.wants",
            "core.cognition.salience_ledger",
            "core.cognition.fresh_moment_receipts",
            "core.infra.private_thoughts",
        }
        self.assertTrue(forbidden.isdisjoint(imported), imported)

    def test_default_signature_path_is_runtime_state_not_memory(self):
        from core.cognition.world_window import default_signature_path

        path = default_signature_path()
        self.assertIn(".local/state/maez", str(path))
        self.assertNotIn("/memory/", str(path))

    def test_disabled_helper_does_not_create_cache(self):
        from core.cognition.world_window import maybe_collect_body_state_window

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sig.json"
            result = maybe_collect_body_state_window(
                {"cpu": {"percent": 2.0}},
                enabled=False,
                signature_path=path,
            )
            self.assertIsNone(result)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
