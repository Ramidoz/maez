# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Mechanical-v0 episode selector for consolidation B1."""
from __future__ import annotations

from dataclasses import dataclass

from core.consolidation import skeleton

SELECTION_MODE = "mechanical_v0"
DEFAULT_DEEP_ROW_CAP = 240


@dataclass(frozen=True)
class EpisodeSelection:
    episode_key: str
    start_chain_position: int
    end_chain_position: int
    turn_ids: tuple[str, ...]
    row_count: int
    selection_depth: str


@dataclass(frozen=True)
class SelectionResult:
    selection_mode: str
    episodes: tuple[EpisodeSelection, ...]
    coverage_order_episode_keys: tuple[str, ...]
    deep_row_budget: int
    rotation_offset: int


def _sorted_rows(rows: list[dict] | tuple[dict, ...]) -> list[dict]:
    return sorted(
        (dict(row) for row in rows),
        key=lambda row: (int(row.get("chain_position", 0)), float(row.get("timestamp", 0.0))),
    )


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


def _coverage_order(
    episodes: list[EpisodeSelection],
    *,
    rotation_offset: int,
) -> list[EpisodeSelection]:
    if not episodes:
        return []
    start = int(rotation_offset) % len(episodes)
    return episodes[start:] + episodes[:start]


def _deep_keys_for_budget(
    episodes: list[EpisodeSelection],
    *,
    deep_row_budget: int,
    rotation_offset: int,
) -> set[str]:
    if not episodes or deep_row_budget <= 0:
        return set()
    selected: set[str] = set()
    used = 0
    for episode in _coverage_order(episodes, rotation_offset=rotation_offset):
        rows = max(0, int(episode.row_count))
        if not selected and rows > deep_row_budget:
            selected.add(episode.episode_key)
            break
        if used + rows > deep_row_budget:
            break
        selected.add(episode.episode_key)
        used += rows
    return selected


def select(
    rows: list[dict] | tuple[dict, ...],
    *,
    deep_row_cap: int | None = None,
    rotation_offset: int = 0,
    session_gap_seconds: float = skeleton.DEFAULT_SESSION_GAP_SECONDS,
) -> SelectionResult:
    """Partition episodes and allocate deep coverage mechanically.

    Selection is deliberately content-blind: episode order, span row count,
    a row cap, and a caller-supplied rotation offset are the only inputs to
    depth assignment. Content-class measurements belong in receipts, not in
    selection.
    """
    ordered = _sorted_rows(rows)
    skel = skeleton.build(ordered, session_gap_seconds=session_gap_seconds)
    partitions = _partition_rows(ordered, skel.session_boundaries)

    pending: list[EpisodeSelection] = []
    for partition in partitions:
        row_count = len(partition)
        pending.append(
            EpisodeSelection(
                episode_key=_episode_key(partition),
                start_chain_position=int(partition[0]["chain_position"]),
                end_chain_position=int(partition[-1]["chain_position"]),
                turn_ids=tuple(str(row.get("turn_id", "")) for row in partition),
                row_count=row_count,
                selection_depth="shallow",
            )
        )

    cap = DEFAULT_DEEP_ROW_CAP if deep_row_cap is None else max(0, int(deep_row_cap))
    span_rows = sum(episode.row_count for episode in pending)
    budget = min(span_rows, cap)
    deep_keys = _deep_keys_for_budget(
        pending,
        deep_row_budget=budget,
        rotation_offset=rotation_offset,
    )
    coverage_order = _coverage_order(pending, rotation_offset=rotation_offset)
    episodes = tuple(
        EpisodeSelection(
            episode_key=episode.episode_key,
            start_chain_position=episode.start_chain_position,
            end_chain_position=episode.end_chain_position,
            turn_ids=episode.turn_ids,
            row_count=episode.row_count,
            selection_depth=(
                "deep" if episode.episode_key in deep_keys else "shallow"
            ),
        )
        for episode in pending
    )
    return SelectionResult(
        selection_mode=SELECTION_MODE,
        episodes=episodes,
        coverage_order_episode_keys=tuple(
            episode.episode_key for episode in coverage_order
        ),
        deep_row_budget=budget,
        rotation_offset=int(rotation_offset),
    )
