# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Dormant narrative readers for recall and presence surfaces."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from core.infra.env_flags import strict_env_flag


def thread_neighbor_candidates(
    *,
    recalled_episode_ids: Iterable[str],
    existing_candidate_ids: set[str],
    episode_store: Any,
    narrative_store_factory: Callable[[], Any],
) -> list[dict]:
    """Return same_thread neighbors as ordinary episode candidates.

    The seam is flag-gated and rank-neutral: returned rows are raw episode
    dicts with no score, boost, or ordering instruction attached.
    """

    if not strict_env_flag("MAEZ_NARRATIVE_RECALL"):
        return []
    narrative_store = narrative_store_factory()
    recalled = [str(item) for item in recalled_episode_ids if str(item)]
    existing = {str(item) for item in existing_candidate_ids if str(item)}
    out: list[dict] = []
    seen = set(existing)
    for episode_id in recalled:
        for link in narrative_store.links_for(episode_id):
            if link.get("link_type") != "same_thread":
                continue
            other_id = (
                str(link.get("to_episode_id"))
                if str(link.get("from_episode_id")) == episode_id
                else str(link.get("from_episode_id"))
            )
            if not other_id or other_id in seen:
                continue
            episode = episode_store.get(other_id)
            if episode is None:
                continue
            seen.add(other_id)
            out.append(episode)
    return out


def format_open_threads_block(
    narrative_store_factory: Callable[[], Any],
    *,
    max_threads: int = 3,
) -> str:
    """Return a content-light open-threads block when presence flag is on."""

    if not strict_env_flag("MAEZ_NARRATIVE_PRESENCE"):
        return ""
    narrative_store = narrative_store_factory()
    threads = [thread for thread in narrative_store.threads() if len(thread) >= 2]
    if not threads:
        return ""
    threads.sort(key=lambda thread: (-len(thread), thread))
    lines = ["OPEN NARRATIVE THREADS (content-light)"]
    for thread in threads[:max_threads]:
        lines.append(f"- {len(thread)} linked episodes: {', '.join(sorted(thread))}")
    return "\n".join(lines)
