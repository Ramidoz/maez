"""Write an A11 narrative coverage shadow artifact without mutating memory."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from core.memory.episodes import EpisodeStore
from core.memory.narrative import NarrativeStore, narrative_coverage
from core.paths import memory_dir


def _default_db() -> Path:
    return memory_dir() / "lived_episodes.db"


def write_coverage_shadow_artifact(
    path: Path | str,
    *,
    episode_store: EpisodeStore,
    narrative_store: NarrativeStore,
) -> Path:
    coverage = narrative_coverage(
        episode_store=episode_store,
        narrative_store=narrative_store,
    )
    candidates = []
    for episode_id, item in sorted(coverage.items()):
        for chapter_id in item["covering_chapters"]:
            candidates.append(
                {
                    "episode_id": episode_id,
                    "covering_chapter": chapter_id,
                    "evidence": item["evidence"],
                }
            )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(_default_db()))
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    db = Path(args.db)
    write_coverage_shadow_artifact(
        Path(args.out),
        episode_store=EpisodeStore(str(db)),
        narrative_store=NarrativeStore(db),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
