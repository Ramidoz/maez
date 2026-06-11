import ast
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "core" / "evolution" / "gestation_memory.py"

FORBIDDEN_IMPORT_PREFIXES = (
    "core.ledger",
    "core.identity_ledger",
    "core.memory.identity_ledger",
    "core.wants",
    "core.evolution.wants",
)
FORBIDDEN_IMPORT_PARTS = {
    "llm_client",
    "focused_cognition",
    "daemon",
    "maez_daemon",
    "telegram",
    "voice",
    "speak",
    "wants",
    "valence_live",
    "soul_editor",
    "soul_loader",
    "memory_manager",
    "ledger",
    "identity_ledger",
}
FORBIDDEN_SYMBOLS = {
    "IdentityLedger",
    "LedgerWriter",
    "Wants",
    "record_event",
    "try_write_turn",
}


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            for alias in node.names:
                yield f"{module}.{alias.name}" if module else alias.name


class BoundaryTests(unittest.TestCase):
    def test_no_llm_daemon_or_writer_imports(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        offenders = []
        for name in _imports(tree):
            if any(
                name == prefix or name.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ):
                offenders.append((name, ["prefix"]))
                continue
            blocked = sorted(set(name.split(".")) & FORBIDDEN_IMPORT_PARTS)
            if blocked:
                offenders.append((name, blocked))
        self.assertEqual(offenders, [])

    def test_no_ledger_or_wants_writer_symbols(self):
        src = MODULE.read_text(encoding="utf-8")
        offenders = [symbol for symbol in FORBIDDEN_SYMBOLS if symbol in src]
        self.assertEqual(offenders, [])

    def test_boundary_matcher_catches_smuggled_imports(self):
        tree = ast.parse(
            "from core.memory.identity_ledger import IdentityLedger\n"
            "import core.ledger.writer as writer\n"
            "from core.evolution.wants import Wants\n"
        )
        names = list(_imports(tree))
        self.assertIn("core.memory.identity_ledger.IdentityLedger", names)
        self.assertIn("core.ledger.writer", names)
        self.assertIn("core.evolution.wants.Wants", names)
