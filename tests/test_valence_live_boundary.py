import ast
import unittest
from pathlib import Path


ALLOWED_STDLIB = frozenset(("datetime", "json", "logging", "os", "pathlib"))
PURE_VALENCE_PREFIX = "core.evolution.valence."

FORBIDDEN = (
    "maez_daemon",
    "daemon",
    "core.daemon",
    "telegram",
    "voice",
    "speak",
    "llm_client",
    "focused_cognition",
    "brain_gateway",
    "audit_flag_buffer",
    "core.evolution.wants",
    "core.memory.continuity",
    "core.continuity",
)


def _imported_module_names(src):
    modules = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = "." * node.level + (node.module or "")
            for alias in node.names:
                if alias.name == "*":
                    modules.append(base)
                elif base:
                    modules.append(f"{base}.{alias.name}")
                else:
                    modules.append(alias.name)
    return modules


def _is_allowed_import(module_name):
    if module_name.startswith(PURE_VALENCE_PREFIX):
        return True
    return any(
        module_name == module or module_name.startswith(f"{module}.")
        for module in ALLOWED_STDLIB
    )


def _has_forbidden_import(module_name):
    lowered = module_name.lower()
    return any(
        lowered == forbidden or lowered.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN
    )


def _import_boundary_violations(src):
    return [
        module_name
        for module_name in _imported_module_names(src)
        if _has_forbidden_import(module_name) or not _is_allowed_import(module_name)
    ]


class ValenceLiveBoundary(unittest.TestCase):
    def test_boundary_helper_rejects_from_core_evolution_import_wants(self):
        violations = _import_boundary_violations("from core.evolution import wants\n")

        self.assertEqual(["core.evolution.wants"], violations)

    def test_boundary_helper_rejects_from_core_memory_import_continuity(self):
        violations = _import_boundary_violations("from core.memory import continuity\n")

        self.assertEqual(["core.memory.continuity"], violations)

    def test_boundary_helper_ignores_comments_and_valence_voice_name(self):
        violations = _import_boundary_violations(
            "# voice should not matter in comments\n"
            "from core.evolution.valence.signals import VoiceSignals\n"
        )

        self.assertEqual([], violations)

    def test_valence_live_imports_are_allowed_stdlib_or_pure_valence(self):
        path = Path(__file__).resolve().parents[1] / "core/evolution/valence_live.py"
        src = path.read_text(encoding="utf-8")

        imported_modules = _imported_module_names(src)
        violations = _import_boundary_violations(src)

        self.assertEqual([], violations)
        self.assertTrue(
            any(module.startswith(PURE_VALENCE_PREFIX) for module in imported_modules)
        )


if __name__ == "__main__":
    unittest.main()
