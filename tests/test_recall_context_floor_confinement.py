from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
MEMORY_MANAGER = ROOT / "memory" / "memory_manager.py"
DECISION_FUNCTIONS = {
    "_candidate_context_floor",
    "_passes_context_recall_floor",
}


def _source_segment(source: str, node: ast.AST) -> str:
    return ast.get_source_segment(source, node) or ""


def _scan_context_floor_kind_decisions(path: Path) -> list[str]:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    offenders: list[str] = []
    required_functions = DECISION_FUNCTIONS | {"_apply_context_floor_to_partitions"}
    seen_functions: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in required_functions:
            seen_functions.add(node.name)

        if isinstance(node, ast.FunctionDef) and node.name in DECISION_FUNCTIONS:
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "_recall_candidate_kind"
                ):
                    offenders.append(f"{node.name}:_recall_candidate_kind")

        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "_apply_context_floor_to_partitions"
        ):
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.IfExp, ast.comprehension)):
                    text = _source_segment(source, child)
                    if '["kind"]' in text or "['kind']" in text:
                        offenders.append(
                            "_apply_context_floor_to_partitions:kind_in_decision"
                        )
                if isinstance(child, ast.Assign):
                    text = _source_segment(source, child)
                    if "non_self" in text or (
                        "self_digest" in text and "fallback" in text
                    ):
                        offenders.append(
                            "_apply_context_floor_to_partitions:kind_fallback"
                        )

    for missing in sorted(required_functions - seen_functions):
        offenders.append(f"{missing}:missing")

    return offenders


class ContextFloorKindDecisionGuardTests(unittest.TestCase):
    def test_context_floor_decisions_do_not_read_kind(self):
        self.assertEqual(_scan_context_floor_kind_decisions(MEMORY_MANAGER), [])

    def test_probe_trips_on_planted_kind_read_in_floor_predicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory_manager.py"
            path.write_text(
                textwrap.dedent(
                    '''
                    def _candidate_context_floor(
                        *,
                        query_is_memory_ask,
                        base_floor,
                        casual_floor,
                        tier,
                        mem=None,
                    ):
                        if _recall_candidate_kind(mem) == "self_digest":
                            return casual_floor
                        return base_floor

                    def _passes_context_recall_floor(
                        mem,
                        *,
                        query_is_memory_ask,
                        base_floor,
                        casual_floor,
                        tier,
                    ):
                        return True

                    def _apply_context_floor_to_partitions(
                        partitions,
                        *,
                        query_is_memory_ask,
                        base_floor,
                        casual_floor,
                        enforce,
                    ):
                        return partitions, {}
                    '''
                )
            )

            offenders = _scan_context_floor_kind_decisions(path)

        self.assertIn("_candidate_context_floor:_recall_candidate_kind", offenders)

    def test_probe_trips_on_planted_kind_read_in_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory_manager.py"
            path.write_text(
                textwrap.dedent(
                    '''
                    def _candidate_context_floor(
                        *,
                        query_is_memory_ask,
                        base_floor,
                        casual_floor,
                        tier,
                    ):
                        return casual_floor

                    def _passes_context_recall_floor(
                        mem,
                        *,
                        query_is_memory_ask,
                        base_floor,
                        casual_floor,
                        tier,
                    ):
                        return True

                    def _apply_context_floor_to_partitions(
                        partitions,
                        *,
                        query_is_memory_ask,
                        base_floor,
                        casual_floor,
                        enforce,
                    ):
                        failed = [{"kind": "self_digest"}]
                        if enforce:
                            non_self = [
                                row for row in failed if row["kind"] != "self_digest"
                            ]
                            return non_self, {}
                        return partitions, {}
                    '''
                )
            )

            offenders = _scan_context_floor_kind_decisions(path)

        self.assertTrue(
            any(
                item.startswith("_apply_context_floor_to_partitions")
                for item in offenders
            )
        )


if __name__ == "__main__":
    unittest.main()
