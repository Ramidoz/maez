"""Heartbeat-safe live adapter for pure valence v0.1 readings."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from core.evolution.valence.reading import Sign, ValenceReading
from core.evolution.valence.setpoints import read_valence
from core.evolution.valence.signals import AuditSignals, ContinuitySignals, WantSignals

_LOG = logging.getLogger(__name__)

# The one truthy set for the whole house (mirrors core/infra/env_flags.TRUTHY).
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def valence_live_enabled() -> bool:
    """Whether the live valence organ may compute + log this cycle.

    DEFAULT-ON: an absent/empty ``MAEZ_VALENCE_LIVE_ENABLED`` returns True so
    the live behaviour is preserved byte-for-byte (covenant: do not silently
    amputate a live organ). An explicit ``1/true/yes/on`` keeps it ON; any
    other value — ``0``/``false``/``no``/``off`` or junk — DISABLES it via the
    strict parser, closing the ``bool(os.environ.get(...))`` footgun where
    ``"0"`` would read as ON.
    """
    raw = (os.environ.get("MAEZ_VALENCE_LIVE_ENABLED", "") or "").strip().lower()
    if raw == "":
        return True
    return raw in _TRUTHY


def _default_log_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / "valence_telemetry.jsonl"


def _retention() -> int:
    raw = os.environ.get("VALENCE_LOG_RETENTION", "1000")
    try:
        value = int(raw)
    except ValueError:
        value = 1000
    return max(1, value)


def _audit_signals(audit_flags) -> AuditSignals:
    flags = tuple(audit_flags or ())
    completion_rail = any(flag == "completion_rail" for flag in flags)
    non_completion = any(flag != "completion_rail" for flag in flags)
    return AuditSignals(
        rail_fired=completion_rail,
        fabrication_flagged=non_completion,
        correction_needed=completion_rail,
    )


def _read_prior_open(log_path) -> int | None:
    path = Path(log_path)
    if not path.exists():
        return None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        last = next((line for line in reversed(lines) if line.strip()), None)
        if last is None:
            return None
        record = json.loads(last)
        value = record["want_snapshot"]["open"]
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def last_pulse_epoch(log_path=None) -> float | None:
    path = Path(log_path) if log_path is not None else _default_log_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        last = next((line for line in reversed(lines) if line.strip()), None)
        if last is None:
            return None
        record = json.loads(last)
        dt = datetime.fromisoformat(record["ts"])
        if dt.tzinfo is None or dt.utcoffset() is None:
            return None
        return dt.timestamp()
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def _want_signals(open_count, prior_open, resolved=0) -> WantSignals:
    return WantSignals(
        backlog=open_count,
        backlog_grew=prior_open is not None and open_count > prior_open,
        resolved=resolved,
        blocked=0,
        stale=0,
    )


def _continuity_signals(continuity_state) -> ContinuitySignals:
    state = continuity_state or {}
    return ContinuitySignals(
        unexpected_gap=False,
        memory_loss=False,
        capsule_expected=bool(state.get("capsule_expected", False)),
        capsule_present=bool(state.get("capsule_present", False)),
    )


def _evidence_count(evidence) -> int:
    count = 0
    for value in evidence.values():
        if isinstance(value, bool):
            count += int(value)
        elif isinstance(value, int):
            count += int(value > 0)
        elif value:
            count += 1
    return count


def _record(reading: ValenceReading, now, wants: WantSignals) -> dict:
    return {
        "ts": now,
        "sign": reading.sign.value,
        "magnitude": reading.magnitude.value,
        "reasons": [
            contribution.reason
            for contribution in reading.contributions
            if contribution.sign is not Sign.NEUTRAL
        ],
        "evidence_counts": {
            contribution.setpoint: _evidence_count(contribution.evidence)
            for contribution in reading.contributions
        },
        "want_snapshot": {
            "open": wants.backlog,
            "resolved": wants.resolved,
            "blocked": wants.blocked,
            "stale": wants.stale,
            "backlog_grew": wants.backlog_grew,
        },
        "want_coverage": {
            "resolved": "satisfied_events_delta",
            "blocked": "not_live_derived",
            "stale": "not_live_derived",
        },
        "telemetry": reading.as_telemetry(),
        "provenance": reading.provenance,
    }


def _append_and_prune(log_path, record, retention) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
        f.write("\n")

    lines = path.read_text(encoding="utf-8").splitlines()
    keep = lines[-retention:]
    if len(keep) != len(lines):
        path.write_text("\n".join(keep) + "\n", encoding="utf-8")


def read_and_log_valence(
    *,
    audit_flags,
    open_want_count,
    continuity_state,
    now,
    resolved=0,
    log_path=None,
) -> ValenceReading | None:
    """Compute and append a valence reading without raising into heartbeat."""

    if not valence_live_enabled():
        # Organ disabled: return None so the daemon keeps (does not clear) its
        # audit_flag_buffer — disabling never silently drops honesty-audit flags.
        return None

    try:
        path = Path(log_path) if log_path is not None else _default_log_path()
        audit = _audit_signals(audit_flags)
        prior_open = _read_prior_open(path)
        wants = _want_signals(open_want_count, prior_open, resolved=resolved)
        cont = _continuity_signals(continuity_state)
        reading = read_valence(audit, wants, cont)
        record = _record(reading, now, wants)
        _append_and_prune(path, record, _retention())
        return reading
    except Exception:
        _LOG.warning("failed to read and log valence", exc_info=True)
        return None
