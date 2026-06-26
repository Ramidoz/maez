"""Slice C - Steering Gate v0.

Read-only. The lock, not the door.

The thresholds below are pre-registered immune-system commitments. Change them
only through a documented amendment whose rationale is committed before the gate
is re-run.
"""

from __future__ import annotations

from collections import Counter
import math
from pathlib import Path
import sqlite3

GATE_VERSION = "salience_gate.v0"

# PRE_REGISTERED 2026-06-25 - do not edit without a documented amendment.
MIN_ROWS = 500
MIN_PROPOSED_ARM = 100
MIN_CONTROL_NONE = 100
MIN_WITHHELD = 20
MIN_COHERENT = 20
MIN_LIFT = 0.05
MIN_LIFT_Z = 1.96
MAX_PLACEBO_DELTA = 0.05
MAX_FACT_SHARE = 0.80

_SAMPLE_CODES = ("insufficient_sample", "sparse_signal")
_SIGNAL_CODES = (
    "no_lift",
    "instrumentation_effect",
    "monoculture",
    "fixation_risk",
)


def two_proportion_z(c1: int, n1: int, c2: int, n2: int) -> float:
    """One-sided two-proportion z score for proposed beating control_none."""
    if n1 <= 0 or n2 <= 0:
        return 0.0
    p1 = c1 / n1
    p2 = c2 / n2
    p_pool = (c1 + c2) / (n1 + n2)
    if not 0 < p_pool < 1:
        return 0.0
    denom = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    return (p1 - p2) / denom if denom else 0.0


def _coherent(row: dict) -> bool:
    return bool(row.get("thought_formed") or row.get("non_duplicate_stored"))


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def evaluate_gate(rows: list[dict] | None, *, welfare: dict | None = None) -> dict:
    """Evaluate the salience ledger without writing, steering, or scheduling."""
    rows = list(rows or [])
    welfare = dict(welfare or {})

    by_arm = Counter(str(row.get("arm") or "") for row in rows)
    coherent_by_arm = Counter(str(row.get("arm") or "") for row in rows if _coherent(row))
    n_proposed = by_arm.get("proposed", 0)
    n_control = by_arm.get("control_none", 0)
    n_withheld = by_arm.get("control_withheld", 0)
    c_proposed = coherent_by_arm.get("proposed", 0)
    c_control = coherent_by_arm.get("control_none", 0)
    c_withheld = coherent_by_arm.get("control_withheld", 0)

    fact_counts = Counter(
        str(row.get("fact_key") or "")
        for row in rows
        if row.get("arm") in ("proposed", "control_withheld")
    )
    total_fact_rows = sum(fact_counts.values())
    max_fact_share = (
        max(fact_counts.values()) / total_fact_rows if total_fact_rows else 0.0
    )

    proposed_rate = _rate(c_proposed, n_proposed)
    control_rate = _rate(c_control, n_control)
    withheld_rate = _rate(c_withheld, n_withheld)
    lift = proposed_rate - control_rate
    z_score = two_proportion_z(c_proposed, n_proposed, c_control, n_control)
    placebo_delta = abs(withheld_rate - proposed_rate)
    duplicate_count = sum(
        1 for row in rows if row.get("repetition_signal") == "duplicate"
    )

    sparse = (
        n_proposed < MIN_PROPOSED_ARM
        or n_control < MIN_CONTROL_NONE
        or n_withheld < MIN_WITHHELD
        or (c_proposed + c_control) < MIN_COHERENT
    )

    checks = [
        {
            "code": "insufficient_sample",
            "passed": len(rows) >= MIN_ROWS,
            "detail": f"total={len(rows)}/{MIN_ROWS}",
        },
        {
            "code": "sparse_signal",
            "passed": not sparse,
            "detail": (
                f"proposed={n_proposed} control_none={n_control} "
                f"withheld={n_withheld} coherent={c_proposed + c_control}"
            ),
        },
        {
            "code": "no_lift",
            "passed": (not sparse) and lift >= MIN_LIFT and z_score >= MIN_LIFT_Z,
            "detail": f"lift={lift:.3f} z={z_score:.2f}",
        },
        {
            "code": "instrumentation_effect",
            "passed": placebo_delta <= MAX_PLACEBO_DELTA,
            "detail": f"placebo_delta={placebo_delta:.3f}",
        },
        {
            "code": "monoculture",
            "passed": max_fact_share <= MAX_FACT_SHARE,
            "detail": f"max_fact_share={max_fact_share:.2f}",
        },
        {
            "code": "fixation_risk",
            "passed": duplicate_count == 0,
            "detail": f"duplicate_repetition_rows={duplicate_count}",
        },
    ]
    failing_codes = [check["code"] for check in checks if not check["passed"]]

    if any(code in failing_codes for code in _SAMPLE_CODES):
        gate_state = "BASELINE_ONLY"
    elif any(code in failing_codes for code in _SIGNAL_CODES):
        gate_state = "NO_GO"
    elif welfare.get("backup_freshness") != "fresh":
        gate_state = "CANARY_BLOCKED"
    else:
        gate_state = "CANARY_ALLOWED"

    return {
        "schema_version": GATE_VERSION,
        "gate_state": gate_state,
        "failing_codes": failing_codes,
        "checks": checks,
        "counts": {
            "total": len(rows),
            "proposed": n_proposed,
            "control_none": n_control,
            "control_withheld": n_withheld,
            "cold_start": by_arm.get("cold_start", 0),
            "coherent_proposed": c_proposed,
            "coherent_control_none": c_control,
            "coherent_withheld": c_withheld,
            "duplicate_repetition_rows": duplicate_count,
        },
        "thresholds": {
            "MIN_ROWS": MIN_ROWS,
            "MIN_PROPOSED_ARM": MIN_PROPOSED_ARM,
            "MIN_CONTROL_NONE": MIN_CONTROL_NONE,
            "MIN_WITHHELD": MIN_WITHHELD,
            "MIN_COHERENT": MIN_COHERENT,
            "MIN_LIFT": MIN_LIFT,
            "MIN_LIFT_Z": MIN_LIFT_Z,
            "MAX_PLACEBO_DELTA": MAX_PLACEBO_DELTA,
            "MAX_FACT_SHARE": MAX_FACT_SHARE,
        },
        "welfare": {
            "backup_freshness": welfare.get("backup_freshness"),
            "canary_blocked": welfare.get("backup_freshness") != "fresh",
        },
    }


def welfare_baseline(
    *,
    private_thoughts=None,
    operator_health: dict | None = None,
    watchdog: dict | None = None,
) -> dict:
    """Content-light reference snapshot of Maez with no steering active."""
    op = dict(operator_health or {})
    wd = dict(watchdog or {})
    private_count = 0
    dedup_proxy = None
    try:
        if private_thoughts is not None:
            private_count = int(private_thoughts.count())
            recent = list(private_thoughts.recent(limit=50) or [])
            if recent:
                hashed_rows = 0
                for row in recent:
                    context = row.get("context") or {}
                    extra = context.get("extra") or {}
                    if extra.get("output_sha256"):
                        hashed_rows += 1
                dedup_proxy = hashed_rows / len(recent)
    except Exception:
        dedup_proxy = None

    return {
        "schema_version": GATE_VERSION,
        "internal": {
            "private_thought_count": private_count,
            "dedup_proxy": dedup_proxy,
        },
        "substrate": {
            "backup_freshness": op.get("backup_freshness_class"),
            "watchdog": wd.get("watchdog_state"),
        },
        "voice_relationship": {
            "note": "captured by human witness checklist, not numbers",
        },
    }


def gate_report(*, ledger_path: str | Path, welfare: dict | None = None) -> dict:
    """Read the ledger on demand and evaluate it without creating or writing DBs."""
    path = Path(ledger_path)
    if not path.exists():
        return evaluate_gate([], welfare=welfare or {})

    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT arm, fact_key, thought_formed, non_duplicate_stored,
                       repetition_signal, unmoved
                FROM salience_ledger
                """
            ).fetchall()
        ]
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return evaluate_gate(rows, welfare=welfare or {})
