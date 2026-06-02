from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReasonCode(str, Enum):
    WAKE_PERCEPTION_CHANGED = "wake_perception_changed"
    WAKE_NEW_FAILURE = "wake_new_failure"
    WAKE_OPEN_WANT = "wake_open_want"
    WAKE_MEMORY_DELTA = "wake_memory_delta"
    WAKE_SIGNAL_AVAILABILITY_CHANGED = "wake_signal_availability_changed"
    WAKE_SCHEDULED = "wake_scheduled"
    WAKE_MIN_FLOOR = "wake_min_floor"
    WAKE_FAIL_OPEN = "wake_fail_open"
    SKIP_NOTHING_SALIENT = "skip_nothing_salient"
    SKIP_UNCHANGED = "skip_unchanged"


@dataclass
class DoormanSignals:
    perception_changed: bool
    new_failures: int
    open_wants: int
    memory_delta: bool
    signal_availability_changed: bool
    scheduled_due: bool
    quiet_skips: int
    min_floor: int
    # Carried for telemetry only. The deterministic wake path must not read it.
    presence: str = "unknown"


@dataclass(frozen=True)
class DoormanVerdict:
    wake: bool
    reason_code: ReasonCode
    signals_present: tuple[str, ...] = ()


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("expected nonnegative int")
    if value < 0:
        raise ValueError("expected nonnegative int")
    return value


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError("expected bool")
    return value


def _fail_open() -> DoormanVerdict:
    return DoormanVerdict(True, ReasonCode.WAKE_FAIL_OPEN, ())


def decide(signals: object) -> DoormanVerdict:
    """Decide whether the cycle should wake the deep brain.

    The decider is deliberately conservative: malformed or uncertain inputs
    wake instead of skip. Missing a real moment is worse than wasting a cycle.
    """
    if not isinstance(signals, DoormanSignals):
        return _fail_open()

    try:
        new_failures = _nonnegative_int(signals.new_failures)
        open_wants = _nonnegative_int(signals.open_wants)
        quiet_skips = _nonnegative_int(signals.quiet_skips)
        min_floor = _nonnegative_int(signals.min_floor)
        perception_changed = _bool(signals.perception_changed)
        memory_delta = _bool(signals.memory_delta)
        signal_availability_changed = _bool(signals.signal_availability_changed)
        scheduled_due = _bool(signals.scheduled_due)

        present: list[str] = []
        if new_failures > 0:
            present.append("new_failure")
        if open_wants > 0:
            present.append("open_want")
        if memory_delta:
            present.append("memory_delta")
        if signal_availability_changed:
            present.append("signal_availability_changed")
        if perception_changed:
            present.append("perception_changed")
        if scheduled_due:
            present.append("scheduled_due")
        if quiet_skips >= min_floor:
            present.append("min_floor_due")

        signals_present = tuple(present)
        if new_failures > 0:
            return DoormanVerdict(True, ReasonCode.WAKE_NEW_FAILURE, signals_present)
        if open_wants > 0:
            return DoormanVerdict(True, ReasonCode.WAKE_OPEN_WANT, signals_present)
        if memory_delta:
            return DoormanVerdict(True, ReasonCode.WAKE_MEMORY_DELTA, signals_present)
        if signal_availability_changed:
            return DoormanVerdict(
                True,
                ReasonCode.WAKE_SIGNAL_AVAILABILITY_CHANGED,
                signals_present,
            )
        if perception_changed:
            return DoormanVerdict(
                True,
                ReasonCode.WAKE_PERCEPTION_CHANGED,
                signals_present,
            )
        if scheduled_due:
            return DoormanVerdict(True, ReasonCode.WAKE_SCHEDULED, signals_present)
        if quiet_skips >= min_floor:
            return DoormanVerdict(True, ReasonCode.WAKE_MIN_FLOOR, signals_present)
        return DoormanVerdict(False, ReasonCode.SKIP_NOTHING_SALIENT, signals_present)
    except Exception:
        return _fail_open()
