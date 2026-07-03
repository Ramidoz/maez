"""Owner inspection surface for A2 Continuity Fingerprint.

The surface renders measurement receipts in third person. It does not feed
results back into Maez's prompt, memory, or continuity ledger.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

from core.continuity_fingerprint.meter import aggregate_drift, verdict_for_swap
from core.continuity_fingerprint.store import ContinuityStore
from core.infra.env_flags import strict_env_flag


def _enabled() -> bool:
    return strict_env_flag("MAEZ_CONTINUITY_FINGERPRINT")


def _brain_swap_timestamps(db_path: Path | str | None = None) -> list[float]:
    from core.memory.identity_ledger import DEFAULT_DB_PATH

    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    if not path.exists():
        return []
    uri = f"file:{path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute(
            """
            SELECT ts FROM identity_ledger
            WHERE event_type = 'brain_swap'
            ORDER BY ts ASC
            """
        ).fetchall()
    finally:
        con.close()
    return [float(row[0]) for row in rows]


def _runs_with_distances(store: ContinuityStore) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for run in store.list_runs():
        answers = store.answers_for(str(run["run_id"]))
        enriched = dict(run)
        enriched["dist_short"] = aggregate_drift(
            answer.get("dist_short") for answer in answers
        )
        enriched["dist_mid"] = aggregate_drift(
            answer.get("dist_mid") for answer in answers
        )
        enriched["dist_long"] = aggregate_drift(
            answer.get("dist_long") for answer in answers
        )
        runs.append(enriched)
    return runs


def _render_show(
    *,
    store: ContinuityStore,
    swap_timestamps: list[float] | tuple[float, ...] | None = None,
) -> str:
    runs = _runs_with_distances(store)
    swaps = list(swap_timestamps) if swap_timestamps is not None else _brain_swap_timestamps()
    lines = ["continuity fingerprint receipt index"]
    lines.append(f"probe_runs={len(runs)} brain_swaps={len(swaps)}")
    eras = sorted({str(run.get("era") or "") for run in runs if run.get("era")})
    embedder_ids = sorted(
        {str(run.get("embedder_id") or "") for run in runs if run.get("embedder_id")}
    )
    for era in eras:
        lines.append(f"era={era}")
    for embedder_id in embedder_ids:
        lines.append(f"embedder_id={embedder_id}")
    if not runs:
        lines.append("status=no_probe_runs")
        return "\n".join(lines)
    if not swaps:
        lines.append("status=no_brain_swaps")
        return "\n".join(lines)
    for idx, swap_ts in enumerate(swaps, start=1):
        verdict = verdict_for_swap(runs, swap_ts)
        detail = " ".join(
            f"{key}={value}"
            for key, value in sorted(verdict.items())
            if key != "status"
        )
        suffix = f" {detail}" if detail else ""
        lines.append(f"swap_{idx}: status={verdict['status']}{suffix}")
    return "\n".join(lines)


def render(
    argv: list[str] | None = None,
    *,
    store: ContinuityStore | None = None,
    swap_timestamps: list[float] | tuple[float, ...] | None = None,
    sampler_fn=None,
) -> str:
    args = list(argv or ["show"])
    command = args[0] if args else "show"
    if command not in {"show", "run"}:
        return "usage: continuity_fingerprint.py [show|run]"
    if not _enabled():
        return (
            "continuity fingerprint surface disabled "
            "(set MAEZ_CONTINUITY_FINGERPRINT=1)"
        )
    if command == "run":
        if sampler_fn is None:
            from core.continuity_fingerprint.sampler import run_probe_battery

            sampler_fn = run_probe_battery
        result = sampler_fn()
        pieces = [f"{key}={value}" for key, value in sorted(result.items())]
        return "continuity fingerprint run " + " ".join(pieces)

    return _render_show(
        store=store or ContinuityStore(),
        swap_timestamps=swap_timestamps,
    )


def main(argv: list[str] | None = None) -> int:
    print(render(sys.argv[1:] if argv is None else argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
