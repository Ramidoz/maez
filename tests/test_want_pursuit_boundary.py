import ast
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "core" / "evolution" / "want_pursuit_bridge.py"
BASE = "4714bd1"


class BoundaryTests(unittest.TestCase):
    def test_bridge_never_references_record_event_or_wants_writer(self):
        src = BRIDGE.read_text(encoding="utf-8")
        self.assertNotIn("record_event", src)
        self.assertNotIn("from core.evolution.wants", src)
        self.assertNotIn("import wants", src)

    def test_bridge_imports_no_lifecycle_writer(self):
        tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
            elif isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
        for name in names:
            self.assertNotIn("wants", name.split("."))

    def test_worker_file_untouched(self):
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{BASE}..HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertNotIn("daemon/wondering_cycle.py", out)
