"""Structural guards for recall promotion authority boundaries."""

from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMOTION_MODULES = {"core.memory_scoring", "core.memory.memory_scoring"}
RELATIVE_PROMOTION_MODULES = {"memory_scoring", "memory.memory_scoring"}
PROMOTION_NAMES = {"promotion_score", "mark_consolidated"}
PROMOTION_PARENT_MODULES = {"core", "core.memory"}
PRODUCTION_SCAN_ROOTS = (
    "cli",
    "core",
    "daemon",
    "devices",
    "memory",
    "scripts",
    "skills",
    "tools",
    "ui",
    "web",
)


def _dream_and_soul_paths() -> list[Path]:
    evolution_dir = REPO_ROOT / "core" / "evolution"
    return sorted([evolution_dir / "dream_state.py", *evolution_dir.glob("soul*.py")])


def _production_python_paths(root: Path = REPO_ROOT) -> list[Path]:
    paths: list[Path] = []
    for root_name in PRODUCTION_SCAN_ROOTS:
        scan_root = root / root_name
        if scan_root.exists():
            paths.extend(scan_root.rglob("*.py"))
    return sorted(paths)


def _imports_memory_scoring_promotion(path: Path) -> list[str]:
    """Return import descriptions that expose recall promotion authority."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names = {alias.name for alias in node.names}
            leaked_names: list[str] = []
            if node.module in PROMOTION_MODULES:
                if "*" in imported_names:
                    leaked_names.append("*")
                leaked_names.extend(sorted(imported_names & PROMOTION_NAMES))
            elif node.level > 0 and node.module in RELATIVE_PROMOTION_MODULES:
                if "*" in imported_names:
                    leaked_names.append("*")
                leaked_names.extend(sorted(imported_names & PROMOTION_NAMES))
            elif node.level > 0 and node.module is None and "memory_scoring" in imported_names:
                leaked_names.append("memory_scoring")
            elif node.level > 0 and node.module == "memory" and "memory_scoring" in imported_names:
                leaked_names.append("memory_scoring")
            elif node.module in PROMOTION_PARENT_MODULES and "memory_scoring" in imported_names:
                leaked_names.append("memory_scoring")

            for name in leaked_names:
                offenders.append(f"{path}:{node.lineno} imports {name} from {node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in PROMOTION_MODULES:
                    offenders.append(f"{path}:{node.lineno} imports {alias.name}")

    return offenders


def _promotion_flag_offenders(root: Path = REPO_ROOT) -> list[str]:
    expected_owner = root / "memory" / "memory_manager.py"
    offenders: list[str] = []
    for path in _production_python_paths(root):
        text = path.read_text(encoding="utf-8")
        if "MAEZ_RECALL_PROMOTION_ENABLED" in text and path != expected_owner:
            offenders.append(str(path.relative_to(root)))
    return offenders


class RecallQualityStructuralTests(unittest.TestCase):
    def test_dream_and_soul_paths_do_not_import_promotion_authority(self) -> None:
        offenders: list[str] = []

        for path in _dream_and_soul_paths():
            offenders.extend(_imports_memory_scoring_promotion(path))

        self.assertEqual([], offenders)

    def test_dream_and_soul_path_scan_includes_all_soul_files(self) -> None:
        covered = {path.name for path in _dream_and_soul_paths()}

        self.assertIn("dream_state.py", covered)
        self.assertIn("soul_invariants.py", covered)

    def test_promotion_flag_is_only_owned_by_memory_manager(self) -> None:
        self.assertEqual([], _promotion_flag_offenders())

    def test_promotion_flag_scan_covers_production_surfaces(self) -> None:
        covered = {
            path.parts[0]
            for path in _production_python_paths()
            if path.is_relative_to(REPO_ROOT)
            for path in [path.relative_to(REPO_ROOT)]
        }

        self.assertIn("core", covered)
        self.assertIn("daemon", covered)
        self.assertIn("devices", covered)
        self.assertIn("scripts", covered)

    def test_import_scanner_detects_planted_dream_state_offender(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "dream_state.py"
            path.write_text(
                "from core.memory_scoring import promotion_score\n",
                encoding="utf-8",
            )

            offenders = _imports_memory_scoring_promotion(path)

        self.assertEqual(1, len(offenders))
        self.assertIn("promotion_score", offenders[0])

    def test_import_scanner_detects_indirect_promotion_authority(self) -> None:
        dangerous_imports = (
            "from core.memory_scoring import *\n",
            "from core.memory.memory_scoring import *\n",
            "import core.memory_scoring\n",
            "from core import memory_scoring\n",
            "from core.memory import memory_scoring as ms\n",
            "from core.memory.memory_scoring import mark_consolidated\n",
            "import core.memory.memory_scoring\n",
            "from ..memory_scoring import promotion_score\n",
            "from ..memory.memory_scoring import mark_consolidated\n",
            "from .. import memory_scoring\n",
            "from ..memory import memory_scoring\n",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for index, import_line in enumerate(dangerous_imports):
                path = tmp_path / f"dream_state_{index}.py"
                path.write_text(import_line, encoding="utf-8")

                offenders = _imports_memory_scoring_promotion(path)

                self.assertEqual(1, len(offenders), import_line)


if __name__ == "__main__":
    unittest.main()
