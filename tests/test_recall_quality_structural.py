"""Structural guards for recall promotion authority boundaries."""

from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMOTION_MODULES = {"core.memory_scoring", "core.memory.memory_scoring"}
PROMOTION_NAMES = {"promotion_score", "mark_consolidated"}
DREAM_SOUL_PATHS = (
    REPO_ROOT / "core" / "evolution" / "dream_state.py",
    REPO_ROOT / "core" / "evolution" / "soul_editor.py",
    REPO_ROOT / "core" / "evolution" / "soul_loader.py",
)


def _imports_memory_scoring_promotion(path: Path) -> list[str]:
    """Return import descriptions that expose recall promotion authority."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in PROMOTION_MODULES:
            imported_names = {alias.name for alias in node.names}
            leaked_names = sorted(imported_names & PROMOTION_NAMES)
            for name in leaked_names:
                offenders.append(f"{path}:{node.lineno} imports {name} from {node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in PROMOTION_MODULES:
                    offenders.append(f"{path}:{node.lineno} imports {alias.name}")

    return offenders


class RecallQualityStructuralTests(unittest.TestCase):
    def test_dream_and_soul_paths_do_not_import_promotion_authority(self) -> None:
        offenders: list[str] = []

        for path in DREAM_SOUL_PATHS:
            offenders.extend(_imports_memory_scoring_promotion(path))

        self.assertEqual([], offenders)

    def test_promotion_flag_is_only_owned_by_memory_manager(self) -> None:
        expected_owner = REPO_ROOT / "memory" / "memory_manager.py"
        offenders: list[str] = []

        for root_name in ("core", "memory"):
            for path in (REPO_ROOT / root_name).rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                if "MAEZ_RECALL_PROMOTION_ENABLED" in text and path != expected_owner:
                    offenders.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual([], offenders)

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


if __name__ == "__main__":
    unittest.main()
