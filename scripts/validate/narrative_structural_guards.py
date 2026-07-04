"""Structural guards for the lived narrative campaign."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.memory.narrative_weave import assert_no_llm_in_weave_source


def assert_no_lived_graph_import_source(source: str) -> None:
    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        module = node.module or "" if isinstance(node, ast.ImportFrom) else ""
        names = [module, *(alias.name for alias in node.names)]
        if any("lived_graph" in name for name in names):
            offenders.append(f"lived_graph:{getattr(node, 'lineno', '?')}")
    if offenders:
        raise AssertionError(f"narrative modules must not import lived_graph: {offenders}")


def assert_no_forbidden_link_writer_source(source: str) -> None:
    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg not in {"link_type", "trust"}:
                continue
            if not isinstance(keyword.value, ast.Constant):
                continue
            value = keyword.value.value
            if keyword.arg == "link_type" and value in {"follows", "same_story"}:
                offenders.append(f"{value}:{getattr(node, 'lineno', '?')}")
            if keyword.arg == "trust" and value == "proposed":
                offenders.append(f"proposed:{getattr(node, 'lineno', '?')}")
    if offenders:
        raise AssertionError(f"forbidden durable narrative writer shape: {offenders}")


def narrative_source_files(repo_root: Path) -> list[Path]:
    roots = [
        repo_root / "core" / "memory",
        repo_root / "scripts",
    ]
    files: list[Path] = []
    for root in roots:
        for path in sorted(root.glob("narrative*.py")):
            files.append(path)
    return files


def run_narrative_structural_guards(repo_root: Path) -> dict[str, int]:
    counts = {"files": 0, "weave_files": 0}
    for path in narrative_source_files(repo_root):
        source = path.read_text(encoding="utf-8")
        counts["files"] += 1
        assert_no_lived_graph_import_source(source)
        assert_no_forbidden_link_writer_source(source)
        if path.name == "narrative_weave.py":
            assert_no_llm_in_weave_source(source)
            counts["weave_files"] += 1
    return counts


def main() -> int:
    counts = run_narrative_structural_guards(_REPO)
    print(f"narrative structural guards OK files={counts['files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
