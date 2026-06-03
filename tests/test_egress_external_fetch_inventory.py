from __future__ import annotations

import ast
import unittest
from pathlib import Path

import yaml


PRODUCTION_ROOT = Path(".")
MIGRATED_HTTP_FILES = {
    "skills/web_search.py",
    "core/actions/action_engine.py",
}
DIRECT_CALLER_INVENTORY = {
    ("gui.py", 195),
    ("cli.py", 224),
    ("cli/maez_chat.py", 854),
    ("daemon/maez_daemon.py", 4864),
    ("daemon/maez_daemon.py", 6617),
    ("daemon/maez_daemon.py", 6807),
    ("daemon/maez_daemon.py", 8584),
    ("skills/telegram_voice.py", 47),
    ("skills/telegram_voice.py", 2728),
    ("skills/telegram_voice.py", 2782),
    ("core/actions/action_engine.py", 1570),
}


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call) and _name(node.func) == "getattr" and len(node.args) >= 2:
        base = _name(node.args[0])
        attr = node.args[1].value if isinstance(node.args[1], ast.Constant) else None
        if base and isinstance(attr, str):
            return f"{base}.{attr}"
    return ""


class _HttpCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.aliases: dict[str, str] = {}
        self.violations: list[tuple[int, str]] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name == "urllib.request":
                self.aliases[alias.asname or "urllib.request"] = "urllib.request"
            elif alias.name in {"httpx", "requests"}:
                self.aliases[alias.asname or alias.name] = alias.name

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module == "urllib.request":
            for alias in node.names:
                if alias.name == "urlopen":
                    self.aliases[alias.asname or alias.name] = "urllib.request.urlopen"
        if node.module in {"httpx", "requests"}:
            for alias in node.names:
                self.aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def visit_Assign(self, node: ast.Assign):
        value_name = self._resolve(_name(node.value))
        for target in node.targets:
            if isinstance(target, ast.Name) and value_name:
                if value_name in {
                    "urllib.request",
                    "urllib.request.urlopen",
                    "httpx",
                    "httpx.Client",
                    "httpx.AsyncClient",
                    "requests",
                    "requests.get",
                }:
                    self.aliases[target.id] = value_name
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        resolved = self._resolve(_name(node.func))
        if resolved in {
            "urllib.request.urlopen",
            "requests.get",
            "httpx.get",
            "httpx.Client.get",
            "httpx.AsyncClient.get",
        }:
            self.violations.append((node.lineno, resolved))
        self.generic_visit(node)

    def _resolve(self, dotted: str) -> str:
        if not dotted:
            return ""
        parts = dotted.split(".")
        if parts[0] in self.aliases:
            return ".".join([self.aliases[parts[0]], *parts[1:]])
        if dotted.startswith("urllib.request.") or dotted.startswith("requests.") or dotted.startswith("httpx."):
            return dotted
        return dotted


class ExternalFetchInventoryTests(unittest.TestCase):
    def test_migrated_roots_have_no_direct_http_client_calls(self):
        violations = []
        for rel in sorted(MIGRATED_HTTP_FILES):
            tree = ast.parse(Path(rel).read_text(encoding="utf-8"), filename=rel)
            visitor = _HttpCallVisitor()
            visitor.visit(tree)
            for lineno, call in visitor.violations:
                violations.append(f"{rel}:{lineno} {call}")

        self.assertEqual(violations, [], "direct HTTP calls bypass external_fetch substrate")

    def test_web_search_direct_caller_inventory_is_stable(self):
        actual = set()
        for rel in {
            "gui.py",
            "cli.py",
            "cli/maez_chat.py",
            "daemon/maez_daemon.py",
            "skills/telegram_voice.py",
            "core/actions/action_engine.py",
        }:
            tree = ast.parse(Path(rel).read_text(encoding="utf-8"), filename=rel)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "skills.web_search":
                    actual.add((rel, node.lineno))
                elif isinstance(node, ast.Call) and _name(node.func) in {
                    "web_search.search",
                    "skills.web_search.search",
                    "actions.web_search",
                }:
                    actual.add((rel, node.lineno))

        self.assertEqual(actual, DIRECT_CALLER_INVENTORY)

    def test_action_fetch_inventory_status_flips_to_substrate_shadow(self):
        payload = yaml.safe_load(
            Path("docs/slices/privacy-egress-gate/network_migration_allowlist.yaml").read_text(encoding="utf-8")
        )
        entries_by_surface = {entry["surface"]: entry for entry in payload["entries"]}
        self.assertEqual(entries_by_surface["action_engine_external_fetch"]["status"], "substrate_shadow")

        import tests.test_privacy_egress_inventory as inventory_tests

        source = Path(inventory_tests.__file__).read_text(encoding="utf-8")
        self.assertIn('"substrate_shadow"', source)


if __name__ == "__main__":
    unittest.main()
