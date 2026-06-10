import ast
import unittest
from pathlib import Path


class ValenceLiveBoundary(unittest.TestCase):
    FORBIDDEN = (
        "maez_daemon",
        "import daemon",
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

    def test_valence_live_imports_only_pure_valence_and_stdlib(self):
        path = Path(__file__).resolve().parents[1] / "core/evolution/valence_live.py"
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        lines = src.splitlines()

        import_lines = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                end_lineno = getattr(node, "end_lineno", node.lineno)
                import_lines.extend(
                    (lineno, lines[lineno - 1])
                    for lineno in range(node.lineno, end_lineno + 1)
                )

        violations = []
        for lineno, line in import_lines:
            normalized = line.strip().lower()
            for forbidden in self.FORBIDDEN:
                if forbidden in normalized:
                    violations.append(f"{lineno}: {line.strip()} -> {forbidden}")

        import_text = "\n".join(line.strip() for _, line in import_lines)
        self.assertEqual([], violations)
        self.assertIn("core.evolution.valence.", import_text)


if __name__ == "__main__":
    unittest.main()
