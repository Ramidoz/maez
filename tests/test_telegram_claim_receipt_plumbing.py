import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_PATH = REPO / "skills" / "telegram_voice.py"


def _process_message_node() -> ast.AsyncFunctionDef:
    tree = ast.parse(SRC_PATH.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_process_message":
            return node
    raise AssertionError("_process_message not found")


class TelegramClaimReceiptPlumbing(unittest.TestCase):
    def test_envelope_uses_telegram_tool_results_not_empty_list(self):
        target = _process_message_node()
        build_calls = []
        for node in ast.walk(target):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name) and fn.id == "_build_envelope":
                    build_calls.append(node)
        self.assertTrue(build_calls, "_process_message must build an evidence envelope")

        tool_kw = None
        for call in build_calls:
            for kw in call.keywords:
                if kw.arg == "tool_results":
                    tool_kw = kw.value
                    break
        self.assertIsNotNone(tool_kw, "build_envelope call must pass tool_results")
        self.assertIsInstance(tool_kw, ast.Name)
        self.assertEqual(tool_kw.id, "_telegram_tool_results")

    def test_pipeline_a_search_appends_typed_search_receipt(self):
        target = _process_message_node()
        source = ast.unparse(target)
        self.assertIn("build_search_tool_result", source)
        self.assertIn("_telegram_tool_results.append", source)
        self.assertIn("source='telegram_pipeline_a'", source)


if __name__ == "__main__":
    unittest.main()
