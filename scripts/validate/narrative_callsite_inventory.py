"""Production EpisodeStore.add inventory for the narrative hook guard."""

from __future__ import annotations

from pathlib import Path

_SKIP = {
    "tests",
    "docs",
    "backups",
    ".git",
    ".venv",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
}

_EXCLUDED_FILES = {
    "scripts/prove_entity_expansion.py",  # isolated temp-db proof fixture
    "scripts/validate/narrative_callsite_inventory.py",
}

_EPISODE_ADD_MARKERS = (
    "episode_store.add(",
    "self.episode_store.add(",
    "self.lived_episodes.add(",
)


def _production_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for top in ("core", "daemon", "scripts"):
        root = repo_root / top
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel = path.relative_to(repo_root)
            if any(part in _SKIP for part in rel.parts):
                continue
            if str(rel) in _EXCLUDED_FILES:
                continue
            files.append(path)
    return sorted(files)


def production_episode_add_calls(repo_root: str | Path) -> list[str]:
    root = Path(repo_root)
    calls: list[str] = []
    for path in _production_files(root):
        rel = path.relative_to(root)
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(marker in line for marker in _EPISODE_ADD_MARKERS):
                calls.append(f"{rel}:{lineno}")
    return sorted(calls)
