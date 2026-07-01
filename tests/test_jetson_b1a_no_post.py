# Structural, AST-based: b1a/ is local-only BY CONSTRUCTION. We assert on the parsed
# import graph (not blunt substrings), plus exact host token/url literals.
import ast
import os
import unittest

_B1A = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "devices", "jetson_presence", "jetson_presence", "b1a"))

# Modules b1a must never import: network stacks + B0 live-path modules.
_FORBIDDEN_IMPORTS = {
    "requests", "urllib", "urllib.request", "http", "http.client",
    "jetson_presence.emitter", "jetson_presence.config",
    "emitter", "config",  # relative `from . import emitter/config`
}
# Exact host token/url identifiers that must never appear as literals.
_FORBIDDEN_LITERALS = (
    "X-Maez-Jetson-Token", "/api/v1/presence", "MAEZ_JETSON_DEVICE_TOKEN",
)


def _imported_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name)
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if base:
                names.add(base)
                names.add(base.split(".")[0])
            for a in node.names:  # `from . import config` / `from jetson_presence import emitter`
                names.add(a.name)
                if base:
                    names.add(f"{base}.{a.name}")
    return names


class NoPostStructuralTests(unittest.TestCase):
    def test_b1a_imports_no_network_or_b0_live_modules(self):
        offenders = []
        for name in os.listdir(_B1A):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(_B1A, name), encoding="utf-8") as f:
                src = f.read()
            imported = _imported_names(ast.parse(src, filename=name))
            for bad in _FORBIDDEN_IMPORTS & imported:
                offenders.append(f"{name}: imports {bad}")
        self.assertEqual(offenders, [], f"b1a is local-only by construction; found: {offenders}")

    def test_b1a_names_no_host_token_or_url(self):
        offenders = []
        for name in os.listdir(_B1A):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(_B1A, name), encoding="utf-8") as f:
                src = f.read()
            for lit in _FORBIDDEN_LITERALS:
                if lit in src:
                    offenders.append(f"{name}: {lit}")
        self.assertEqual(offenders, [], f"b1a must not name host token/url: {offenders}")


if __name__ == "__main__":
    unittest.main()
