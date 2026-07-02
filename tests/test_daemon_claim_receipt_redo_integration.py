import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_PATH = REPO / "daemon" / "maez_daemon.py"


def _handle_message_source() -> str:
    tree = ast.parse(SRC_PATH.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "handle_message":
            return ast.unparse(node)
    raise AssertionError("handle_message not found")


class DaemonClaimReceiptRedoIntegration(unittest.TestCase):
    def test_claim_receipt_redo_runs_before_normal_audit_and_does_not_launder(self):
        source = _handle_message_source()
        self.assertIn("_audit_daemon_reply_for_claim_receipts", source)
        self.assertIn("_claim_receipt_redo_messages", source)
        self.assertIn("_claim_receipt_floor_notice", source)

        claim_audit = source.index("_audit_daemon_reply_for_claim_receipts")
        normal_audit = source.index("reply = audit_assistant_text(")
        self.assertLess(claim_audit, normal_audit)

        redo_start = source.index("_claim_receipt_redo_messages")
        normal_audit_start = source.index("reply = audit_assistant_text(")
        redo_segment = source[redo_start:normal_audit_start]
        self.assertNotIn("web_search(", redo_segment)
        self.assertNotIn("search_rss(", redo_segment)


if __name__ == "__main__":
    unittest.main()
