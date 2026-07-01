from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
MEMORY_MANAGER = ROOT / "memory" / "memory_manager.py"
FORBIDDEN_MODULE_PREFIXES = (
    "core.dream",
    "core.dream_state",
    "core.soul",
    "daemon.dream",
    "dream_state",
    "soul",
)
FORBIDDEN_NAMES = {
    "write_soul_note",
    "apply_dream",
    "MAEZ_RECALL_PROMOTION_ENABLED = \"1\"",
}


def _scan_recall_floor_confinement(path: Path) -> list[str]:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(FORBIDDEN_MODULE_PREFIXES):
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_MODULE_PREFIXES):
                offenders.append(module)
    for name in FORBIDDEN_NAMES:
        if name in source:
            offenders.append(name)
    return offenders


class RecallTypeFloorConfinementTests(unittest.TestCase):
    def test_memory_manager_does_not_import_dream_soul_or_force_promotion(self):
        self.assertEqual(_scan_recall_floor_confinement(MEMORY_MANAGER), [])

    def test_probe_trips_on_planted_forbidden_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory_manager.py"
            path.write_text(
                textwrap.dedent(
                    """
                    from core.dream_state import apply_dream

                    def harmless():
                        return None
                    """
                )
            )

            offenders = _scan_recall_floor_confinement(path)

        self.assertIn("core.dream_state", offenders)


if __name__ == "__main__":
    unittest.main()
