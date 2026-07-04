"""Inspect lived narrative links without mutating memory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.paths import memory_dir
from core.memory.episodes import EpisodeStore
from core.memory.narrative import NarrativeStore


def _default_db() -> Path:
    return memory_dir() / "lived_episodes.db"


def render_threads(narrative_store: NarrativeStore) -> str:
    threads = narrative_store.threads()
    if not threads:
        return "No narrative threads."
    lines = ["Narrative threads:"]
    for index, thread in enumerate(sorted(threads, key=lambda t: (-len(t), t)), 1):
        lines.append(f"{index}. size={len(thread)} episodes={', '.join(thread)}")
    return "\n".join(lines)


def render_show(
    narrative_store: NarrativeStore,
    episode_id: str,
    *,
    trust_filter: str | None = None,
) -> str:
    links = narrative_store.links_for(episode_id, trust_filter=trust_filter)
    if not links:
        return f"No narrative links for {episode_id}."
    lines = [f"Narrative links for {episode_id}:"]
    for link in links:
        evidence = []
        for entry in link.get("evidence", []):
            evidence.extend(entry.get("ids") or [])
        lines.append(
            "- "
            f"{link['link_type']} trust={link['trust']} "
            f"{link['from_episode_id']} -> {link['to_episode_id']} "
            f"evidence={', '.join(evidence)}"
        )
    return "\n".join(lines)


def render_timeline(episode_store: EpisodeStore, member_ids: Sequence[str]) -> str:
    rows = []
    for episode_id in member_ids:
        episode = episode_store.get(str(episode_id))
        if episode is None:
            continue
        rows.append(episode)
    rows.sort(key=lambda ep: (ep.get("occurred_at") or ep.get("created_at") or "", ep.get("id") or ""))
    if not rows:
        return "No timeline episodes."
    lines = ["Narrative timeline (derived order; no stored follows):"]
    for episode in rows:
        ts = episode.get("occurred_at") or episode.get("created_at") or "unknown-time"
        lines.append(f"- {ts} {episode.get('id')}: {episode.get('title')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(_default_db()))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("threads")
    show = sub.add_parser("show")
    show.add_argument("episode_id")
    show.add_argument("--trust")
    timeline = sub.add_parser("timeline")
    timeline.add_argument("episode_ids", nargs="+")
    args = parser.parse_args(argv)

    db = Path(args.db)
    narrative_store = NarrativeStore(db)
    episode_store = EpisodeStore(str(db))
    if args.cmd == "threads":
        print(render_threads(narrative_store))
    elif args.cmd == "show":
        print(render_show(narrative_store, args.episode_id, trust_filter=args.trust))
    elif args.cmd == "timeline":
        print(render_timeline(episode_store, args.episode_ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
