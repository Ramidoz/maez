import ast
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "core" / "evolution" / "novelty_harbor.py"
)

FORBIDDEN_IMPORT_PARTS = {
    "daemon",
    "maez_daemon",
    "telegram",
    "voice",
    "speak",
    "llm_client",
    "focused_cognition",
    "valence_live",
    "soul_loader",
    "soul_editor",
    "memory_manager",
    "wants",
}

FORBIDDEN_ENTRYPOINT_STRINGS = ("MaezDaemon", "systemctl", "MAEZ_")


def _import_names(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            for alias in node.names:
                yield f"{module}.{alias.name}" if module else alias.name


class NoveltyHarborBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.source = MODULE_PATH.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_imports_do_not_touch_live_body_speech_or_writer_organs(self):
        offenders = []
        for name in _import_names(self.tree):
            parts = set(name.split("."))
            blocked = sorted(parts & FORBIDDEN_IMPORT_PARTS)
            if blocked:
                offenders.append((name, blocked))

        self.assertEqual(offenders, [])

    def test_module_keeps_soul_invariants_as_intentional_boundary_dependency(self):
        imported_names = set(_import_names(self.tree))

        self.assertIn("core.evolution", imported_names)
        self.assertIn("core.evolution.soul_invariants", imported_names)

    def test_module_has_no_daemon_entrypoint_strings(self):
        for marker in FORBIDDEN_ENTRYPOINT_STRINGS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.source)


if __name__ == "__main__":
    unittest.main()
