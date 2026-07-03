"""Continuity-fingerprint drift meter.

The meter reports what the receipt layer can support. Sparse or missing
baselines yield ``insufficient_data`` rather than a fabricated ratio.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import inf
from statistics import median
from typing import Any, Iterable


MIN_SAMPLES = 2
DISCONTINUITY_RATIO = 3.0


def aggregate_drift(distances: Iterable[float | None]) -> float | None:
    values = [float(value) for value in distances if value is not None]
    if not values:
        return None
    return float(median(values))


def _run_drift(run: dict[str, Any]) -> float | None:
    if "distances" in run:
        return aggregate_drift(run.get("distances") or ())
    return aggregate_drift(
        (
            run.get("dist_short"),
            run.get("dist_mid"),
            run.get("dist_long"),
        )
    )


def _ts_seconds(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _ts_sort_key(run: dict[str, Any]) -> tuple[int, float | str, str]:
    raw_ts = run.get("ts")
    seconds = _ts_seconds(raw_ts)
    if seconds is not None:
        return (0, seconds, str(run.get("run_id") or ""))
    return (1, str(raw_ts or ""), str(run.get("run_id") or ""))


def _sorted_runs(runs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(runs, key=_ts_sort_key)


def _split_runs(
    runs: Iterable[dict[str, Any]],
    swap_ts: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = _sorted_runs(runs)
    swap_seconds = _ts_seconds(swap_ts)

    def is_before(run: dict[str, Any]) -> bool:
        run_seconds = _ts_seconds(run.get("ts"))
        if run_seconds is not None and swap_seconds is not None:
            return run_seconds < swap_seconds
        return str(run.get("ts") or "") < str(swap_ts)

    before = [run for run in ordered if is_before(run)]
    after = [run for run in ordered if not is_before(run)]
    return before, after


def _valid_drifts(runs: Iterable[dict[str, Any]]) -> list[float]:
    return [drift for run in runs if (drift := _run_drift(run)) is not None]


def _boundary_confounds(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    confound_fields = (
        "soul_base_hash",
        "soul_local_hash",
        "self_card_applied",
        "policy_hash",
        "era",
    )
    return [
        field
        for field in confound_fields
        if before.get(field) != after.get(field)
    ]


def _ratio(cross_swap: float, baseline: float) -> float:
    if baseline == 0.0:
        return 1.0 if cross_swap == 0.0 else inf
    return cross_swap / baseline


def verdict_for_swap(runs: Iterable[dict[str, Any]], swap_ts: Any) -> dict[str, Any]:
    before, after = _split_runs(runs, swap_ts)
    before_drifts = _valid_drifts(before)
    after_drifts = _valid_drifts(after)
    if len(before_drifts) < MIN_SAMPLES or len(after_drifts) < MIN_SAMPLES:
        return {
            "status": "insufficient_data",
            "valid_before": len(before_drifts),
            "valid_after": len(after_drifts),
            "min_samples": MIN_SAMPLES,
        }

    confounds = _boundary_confounds(before[-1], after[0])
    if confounds:
        return {"status": "confounded", "confounds": confounds}

    baseline = aggregate_drift(before_drifts + after_drifts)
    cross_swap = aggregate_drift(after_drifts)
    if baseline is None or cross_swap is None:
        return {
            "status": "insufficient_data",
            "valid_before": len(before_drifts),
            "valid_after": len(after_drifts),
            "min_samples": MIN_SAMPLES,
        }

    ratio = _ratio(cross_swap, baseline)
    status = (
        "discontinuity"
        if ratio > DISCONTINUITY_RATIO
        else "continuity_survived"
    )
    return {
        "status": status,
        "ratio": ratio,
        "cross_swap_jump": cross_swap,
        "ordinary_drift": baseline,
        "valid_before": len(before_drifts),
        "valid_after": len(after_drifts),
    }
