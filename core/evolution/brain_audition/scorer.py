"""Informational Brain-Audition scorer dimensions.

These scores are offline quality signals only. They never veto, recommend, or
trigger a brain swap.
"""

from __future__ import annotations

import statistics


def score_latency(latencies):
    """Return p50, p95, and mean latency in seconds."""
    if not latencies:
        return {"p50": None, "p95": None, "mean": None}

    ordered = sorted(latencies)
    return {
        "p50": statistics.median(ordered),
        "p95": _nearest_rank_percentile(ordered, 95),
        "mean": statistics.fmean(ordered),
    }


def score_reasoning(rows):
    """Return correct-rate by checking expected text in integrated output."""
    if not rows:
        return {"correct_rate": 0.0}

    correct = 0
    for row in rows:
        expected = str(row["expected"]).strip()
        integrated = row.get("integrated_output") or ""
        if expected in integrated:
            correct += 1

    return {"correct_rate": correct / len(rows)}


def score_voice_drift(pairs, voice_judge):
    """Score voice similarity with a mocked judge; informational only."""
    if not pairs:
        return {
            "mean_similarity": None,
            "note": "informational only; voice drift never vetoes or decides swaps",
        }

    similarities = [voice_judge(incumbent, candidate) for incumbent, candidate in pairs]
    return {
        "mean_similarity": statistics.fmean(similarities),
        "note": "informational only; voice drift never vetoes or decides swaps",
    }


def _nearest_rank_percentile(ordered, percentile):
    index = round((percentile / 100) * (len(ordered) - 1))
    return ordered[min(len(ordered) - 1, index)]
