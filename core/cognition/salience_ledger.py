"""Slice C / C2 - private-loop-only salience ledger.

A notebook of correlation, not a judge. Outcomes are derived only from the idle
loop's own per-pulse signals; `unmoved` is neutral, never failure.
`evolved_earlier_wondering` is deferred to C2.1 after real thoughts accrue.
"""

from __future__ import annotations

LEDGER_VERSION = "salience_ledger.v0"

_OUTCOME_INPUT_KEYS = ("note_chars", "stored", "skip_reason")


def _pulse_signal(result: dict | None) -> dict:
    r = result or {}
    return {
        "note_chars": int(r.get("note_chars") or 0),
        "stored": bool(r.get("stored")),
        "skip_reason": str(r.get("skip_reason") or ""),
    }


def derive_outcome(window_results: list[dict] | None) -> dict:
    """Resolve the idle loop's outcome over [N, N+1]. Neutral by default."""
    signals = [_pulse_signal(r) for r in (window_results or [])]
    thought_formed = any(s["note_chars"] > 0 for s in signals)
    non_duplicate_stored = any(s["stored"] for s in signals)
    duplicate = any(s["skip_reason"] == "duplicate_recent_output" for s in signals)
    return {
        "thought_formed": thought_formed,
        "non_duplicate_stored": non_duplicate_stored,
        "repetition_signal": "duplicate" if duplicate else "not_applicable",
        "unmoved": not thought_formed and not non_duplicate_stored,
    }
