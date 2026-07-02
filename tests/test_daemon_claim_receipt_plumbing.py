import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_PATH = REPO / "daemon" / "maez_daemon.py"


def _handle_message_node() -> ast.FunctionDef:
    tree = ast.parse(SRC_PATH.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "handle_message":
            return node
    raise AssertionError("handle_message not found")


def _first_lineno_containing(text: str, needle: str) -> int:
    for idx, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return idx
    raise AssertionError(f"{needle!r} not found")


class DaemonClaimReceiptPlumbing(unittest.TestCase):
    def test_live_daemon_search_builds_typed_receipts_before_rendering_envelope(self):
        source = ast.unparse(_handle_message_node())
        self.assertIn("build_search_tool_result", source)
        self.assertIn("_daemon_tool_results.append", source)
        self.assertIn("source='daemon_web_search'", source)
        self.assertIn("source='daemon_photo_freshness_web_search'", source)
        self.assertIn("tool_results=_daemon_tool_results", source)

        first_receipt = _first_lineno_containing(source, "_daemon_tool_results.append")
        render = _first_lineno_containing(source, "_render_envelope(_evidence_envelope)")
        self.assertLess(first_receipt, render)


if __name__ == "__main__":
    unittest.main()
