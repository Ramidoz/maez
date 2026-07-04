#!/usr/bin/env python3
"""Owner-gated backfill for deterministic lived narrative links."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Sequence

from core.learning.scar_tissue import ScarSidecar
from core.memory.episodes import EpisodeStore
from core.memory.narrative import (
    DETECTOR_VERSION,
    LinkCandidate,
    NarrativeStore,
    detect_links,
    link_key_for,
)
from core.paths import memory_dir


def _default_episode_db() -> Path:
    return memory_dir() / "lived_episodes.db"


def _default_sidecar_db(episode_db: Path) -> Path:
    return episode_db.parent / "scar_tissue.db"


def _active_episodes(episode_db: Path) -> list[dict]:
    return EpisodeStore(str(episode_db)).list_active()


def _sidecar_rows(episode_db: Path, sidecar_db: Path | None = None) -> list[dict]:
    return ScarSidecar.list_all_at(sidecar_db or _default_sidecar_db(episode_db))


def _candidate_key(candidate: LinkCandidate) -> str:
    return link_key_for(
        candidate.link_type,
        candidate.from_id,
        candidate.to_id,
        hook_class=candidate.hook_class,
    )


def _planned_candidates(
    episode_db: Path,
    *,
    sidecar_db: Path | None = None,
) -> list[LinkCandidate]:
    episodes = _active_episodes(episode_db)
    sidecar_rows = _sidecar_rows(episode_db, sidecar_db)
    by_key: dict[str, LinkCandidate] = {}
    for episode in episodes:
        existing = [ep for ep in episodes if ep.get("id") != episode.get("id")]
        for candidate in detect_links(
            episode,
            existing,
            scar_sidecar_rows=sidecar_rows,
        ):
            by_key.setdefault(_candidate_key(candidate), candidate)
    return [by_key[key] for key in sorted(by_key)]


def _report(candidates: Sequence[LinkCandidate]) -> dict:
    counts = Counter(candidate.link_type for candidate in candidates)
    return {
        "counts": {
            "same_thread": int(counts.get("same_thread", 0)),
            "strings": int(counts.get("strings", 0)),
            "because_of": int(counts.get("because_of", 0)),
        },
        "total": len(candidates),
    }


def list_backfill(
    episode_db: str | Path | None = None,
    *,
    sidecar_db: str | Path | None = None,
) -> dict:
    db = Path(episode_db) if episode_db is not None else _default_episode_db()
    sidecar = Path(sidecar_db) if sidecar_db is not None else None
    return _report(_planned_candidates(db, sidecar_db=sidecar))


def apply_backfill(
    episode_db: str | Path | None = None,
    *,
    sidecar_db: str | Path | None = None,
    owner_approved: bool,
) -> dict:
    if not owner_approved:
        raise PermissionError("narrative backfill requires --owner-approved")
    db = Path(episode_db) if episode_db is not None else _default_episode_db()
    sidecar = Path(sidecar_db) if sidecar_db is not None else None
    candidates = _planned_candidates(db, sidecar_db=sidecar)
    store = NarrativeStore(db)
    for candidate in candidates:
        store.upsert_link(
            link_type=candidate.link_type,
            from_episode_id=candidate.from_id,
            to_episode_id=candidate.to_id,
            trust=candidate.trust,
            evidence_ids=candidate.evidence_ids,
            detector_version=DETECTOR_VERSION,
            hook_class=candidate.hook_class,
        )
    report = _report(candidates)
    report["written"] = len(candidates)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "apply"))
    parser.add_argument("--episode-db", type=Path, default=_default_episode_db())
    parser.add_argument("--sidecar-db", type=Path, default=None)
    parser.add_argument("--owner-approved", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "list":
        result = list_backfill(args.episode_db, sidecar_db=args.sidecar_db)
    else:
        result = apply_backfill(
            args.episode_db,
            sidecar_db=args.sidecar_db,
            owner_approved=args.owner_approved,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
