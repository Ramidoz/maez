# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Mechanical span bookkeeping for consolidation B1."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

DEFAULT_SESSION_GAP_SECONDS = 30 * 60

_ERROR_OUTCOMES = frozenset(
    (
        "error",
        "failed",
        "failure",
        "refused",
        "denied",
        "blocked",
        "exception",
    )
)


@dataclass(frozen=True)
class SessionBoundary:
    before_chain_position: int
    after_chain_position: int
    gap_seconds: float


@dataclass(frozen=True)
class ErrorCluster:
    start_chain_position: int
    end_chain_position: int
    row_count: int
    turn_ids: tuple[str, ...]


@dataclass(frozen=True)
class SpanSkeleton:
    row_count: int
    turn_kind_counts: dict[str, int]
    tool_proposal_count: int
    tool_outcome_counts: dict[str, int]
    error_clusters: tuple[ErrorCluster, ...]
    session_boundaries: tuple[SessionBoundary, ...]
    surface_counts: dict[str, int]
    hour_counts: dict[int, int]


def _sorted_rows(rows: list[dict] | tuple[dict, ...]) -> list[dict]:
    return sorted(
        (dict(row) for row in rows),
        key=lambda row: (int(row.get("chain_position", 0)), float(row.get("timestamp", 0.0))),
    )


def _loads(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"_raw": value}
    return value


def _outcome_from_audit(audit: Any) -> str | None:
    parsed = _loads(audit)
    if parsed is None:
        return None
    if isinstance(parsed, Mapping):
        for key in ("outcome", "status", "verdict", "decision", "result"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return "present"
    return "present"


def _is_error_outcome(outcome: str | None) -> bool:
    if not outcome:
        return False
    lowered = outcome.lower()
    return lowered in _ERROR_OUTCOMES or any(
        token in lowered for token in ("error", "fail", "refus", "denied", "blocked")
    )


def _session_boundaries(
    rows: list[dict],
    *,
    session_gap_seconds: float,
) -> tuple[SessionBoundary, ...]:
    boundaries: list[SessionBoundary] = []
    previous: dict | None = None
    for row in rows:
        if previous is not None:
            gap = float(row.get("timestamp", 0.0)) - float(previous.get("timestamp", 0.0))
            if gap > session_gap_seconds:
                boundaries.append(
                    SessionBoundary(
                        before_chain_position=int(previous.get("chain_position", 0)),
                        after_chain_position=int(row.get("chain_position", 0)),
                        gap_seconds=gap,
                    )
                )
        previous = row
    return tuple(boundaries)


def _error_clusters(rows: list[dict]) -> tuple[ErrorCluster, ...]:
    clusters: list[ErrorCluster] = []
    current: list[dict] = []

    def flush() -> None:
        nonlocal current
        if current:
            clusters.append(
                ErrorCluster(
                    start_chain_position=int(current[0].get("chain_position", 0)),
                    end_chain_position=int(current[-1].get("chain_position", 0)),
                    row_count=len(current),
                    turn_ids=tuple(str(row.get("turn_id", "")) for row in current),
                )
            )
            current = []

    for row in rows:
        if _is_error_outcome(_outcome_from_audit(row.get("audit_verdict_json"))):
            current.append(row)
        else:
            flush()
    flush()
    return tuple(clusters)


def build(
    rows: list[dict] | tuple[dict, ...],
    *,
    session_gap_seconds: float = DEFAULT_SESSION_GAP_SECONDS,
) -> SpanSkeleton:
    """Return content-light bookkeeping counts for a span."""
    ordered = _sorted_rows(rows)
    turn_kinds: Counter[str] = Counter()
    surfaces: Counter[str] = Counter()
    hours: Counter[int] = Counter()
    outcomes: Counter[str] = Counter()
    proposal_count = 0

    for row in ordered:
        turn_kinds[str(row.get("turn_kind") or "unknown")] += 1
        surfaces[str(row.get("surface") or row.get("raw_surface") or "unknown")] += 1
        timestamp = float(row.get("timestamp", 0.0) or 0.0)
        hour = datetime.fromtimestamp(timestamp, tz=timezone.utc).hour
        hours[hour] += 1
        if _loads(row.get("action_proposal_json")) is not None:
            proposal_count += 1
        outcome = _outcome_from_audit(row.get("audit_verdict_json"))
        if outcome is not None:
            outcomes[outcome] += 1

    return SpanSkeleton(
        row_count=len(ordered),
        turn_kind_counts=dict(sorted(turn_kinds.items())),
        tool_proposal_count=proposal_count,
        tool_outcome_counts=dict(sorted(outcomes.items())),
        error_clusters=_error_clusters(ordered),
        session_boundaries=_session_boundaries(
            ordered,
            session_gap_seconds=session_gap_seconds,
        ),
        surface_counts=dict(sorted(surfaces.items())),
        hour_counts=dict(sorted(hours.items())),
    )

