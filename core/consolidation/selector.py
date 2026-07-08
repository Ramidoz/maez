# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Mechanical-v0 episode selector for consolidation B1."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from core.consolidation import skeleton

SELECTION_MODE = "mechanical_v0"


@dataclass(frozen=True)
class EpisodeSelection:
    episode_key: str
    start_chain_position: int
    end_chain_position: int
    turn_ids: tuple[str, ...]
    row_count: int
    tool_outcome_count: int
    tool_outcome_density: float
    error_cluster_present: bool
    selection_depth: str


@dataclass(frozen=True)
class SelectionResult:
    selection_mode: str
    episodes: tuple[EpisodeSelection, ...]
    ranked_episode_keys: tuple[str, ...]
    deep_budget: int


def _sorted_rows(rows: list[dict] | tuple[dict, ...]) -> list[dict]:
    return sorted(
        (dict(row) for row in rows),
        key=lambda row: (int(row.get("chain_position", 0)), float(row.get("timestamp", 0.0))),
    )


def _has_audit_outcome(row: Mapping[str, Any]) -> bool:
    raw = row.get("audit_verdict_json")
    if raw is None or raw == "":
        return False
    if isinstance(raw, Mapping):
        return True
    if isinstance(raw, str):
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            return True
        return True
    return True


def _partition_rows(
    rows: list[dict],
    boundaries: tuple[skeleton.SessionBoundary, ...],
) -> list[list[dict]]:
    if not rows:
        return []
    boundary_starts = {
        boundary.after_chain_position
        for boundary in boundaries
    }
    episodes: list[list[dict]] = []
    current: list[dict] = []
    for row in rows:
        position = int(row.get("chain_position", 0))
        if current and position in boundary_starts:
            episodes.append(current)
            current = []
        current.append(row)
    if current:
        episodes.append(current)
    return episodes


def _episode_key(rows: list[dict]) -> str:
    return f"cp{int(rows[0]['chain_position'])}-cp{int(rows[-1]['chain_position'])}"


def _episode_error_present(
    rows: list[dict],
    clusters: tuple[skeleton.ErrorCluster, ...],
) -> bool:
    start = int(rows[0]["chain_position"])
    end = int(rows[-1]["chain_position"])
    return any(
        cluster.start_chain_position <= end and cluster.end_chain_position >= start
        for cluster in clusters
    )


def _rank_key(episode: EpisodeSelection) -> tuple[float, float, int, int]:
    return (
        float(episode.row_count),
        float(episode.tool_outcome_density),
        1 if episode.error_cluster_present else 0,
        -episode.start_chain_position,
    )


def select(
    rows: list[dict] | tuple[dict, ...],
    *,
    deep_budget: int = 3,
    session_gap_seconds: float = skeleton.DEFAULT_SESSION_GAP_SECONDS,
) -> SelectionResult:
    """Partition and rank episodes using bookkeeping-only signals."""
    budget = max(0, int(deep_budget))
    ordered = _sorted_rows(rows)
    skel = skeleton.build(ordered, session_gap_seconds=session_gap_seconds)
    partitions = _partition_rows(ordered, skel.session_boundaries)

    pending: list[EpisodeSelection] = []
    for partition in partitions:
        row_count = len(partition)
        outcome_count = sum(1 for row in partition if _has_audit_outcome(row))
        density = outcome_count / row_count if row_count else 0.0
        pending.append(
            EpisodeSelection(
                episode_key=_episode_key(partition),
                start_chain_position=int(partition[0]["chain_position"]),
                end_chain_position=int(partition[-1]["chain_position"]),
                turn_ids=tuple(str(row.get("turn_id", "")) for row in partition),
                row_count=row_count,
                tool_outcome_count=outcome_count,
                tool_outcome_density=density,
                error_cluster_present=_episode_error_present(
                    partition,
                    skel.error_clusters,
                ),
                selection_depth="shallow",
            )
        )

    ranked = sorted(pending, key=_rank_key, reverse=True)
    deep_keys = {episode.episode_key for episode in ranked[:budget]}
    episodes = tuple(
        EpisodeSelection(
            episode_key=episode.episode_key,
            start_chain_position=episode.start_chain_position,
            end_chain_position=episode.end_chain_position,
            turn_ids=episode.turn_ids,
            row_count=episode.row_count,
            tool_outcome_count=episode.tool_outcome_count,
            tool_outcome_density=episode.tool_outcome_density,
            error_cluster_present=episode.error_cluster_present,
            selection_depth=(
                "deep" if episode.episode_key in deep_keys else "shallow"
            ),
        )
        for episode in pending
    )
    return SelectionResult(
        selection_mode=SELECTION_MODE,
        episodes=episodes,
        ranked_episode_keys=tuple(episode.episode_key for episode in ranked),
        deep_budget=budget,
    )
