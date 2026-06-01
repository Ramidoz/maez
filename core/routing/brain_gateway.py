"""Priority gateway for access to Maez's primary brain backend."""

from __future__ import annotations

import contextlib
import contextvars
import functools
import logging
import threading
import time
from collections import deque
from enum import Enum
from typing import Callable, Iterable

from core.routing.cancellable_brain_call import (
    BrainPreempted,
    CancellableBrainCall,
)

logger = logging.getLogger("brain_gateway")


class BrainPurpose(str, Enum):
    OWNER_REPLY = "owner_reply"
    OWNER_RECALL = "owner_recall"
    VOICE_REPLY = "voice_reply"
    DAEMON_CYCLE_GENERATION = "daemon_cycle_generation"
    DAEMON_CYCLE_AUDIT_JUDGE = "daemon_cycle_audit_judge"
    DAEMON_CYCLE_REWRITE = "daemon_cycle_rewrite"
    DAEMON_CYCLE_RETRY = "daemon_cycle_retry"
    NEUTRAL = "neutral"


_FOREGROUND_PURPOSES = frozenset(
    {
        BrainPurpose.OWNER_REPLY,
        BrainPurpose.OWNER_RECALL,
        BrainPurpose.VOICE_REPLY,
    }
)
_BACKGROUND_PURPOSES = frozenset(
    {
        BrainPurpose.DAEMON_CYCLE_GENERATION,
        BrainPurpose.DAEMON_CYCLE_AUDIT_JUDGE,
        BrainPurpose.DAEMON_CYCLE_REWRITE,
        BrainPurpose.DAEMON_CYCLE_RETRY,
    }
)
_CURRENT_PURPOSE: contextvars.ContextVar[BrainPurpose] = contextvars.ContextVar(
    "maez_brain_purpose",
    default=BrainPurpose.NEUTRAL,
)


def _coerce_purpose(purpose) -> BrainPurpose:
    if isinstance(purpose, BrainPurpose):
        return purpose
    try:
        return BrainPurpose(str(purpose))
    except Exception:
        return BrainPurpose.NEUTRAL


def priority_of(purpose) -> int:
    purpose = _coerce_purpose(purpose)
    if purpose in _FOREGROUND_PURPOSES:
        return 100
    if purpose in _BACKGROUND_PURPOSES:
        return 10
    return 0


def current_purpose() -> BrainPurpose:
    return _CURRENT_PURPOSE.get()


def copy_current_context_callable(fn, /, *args, **kwargs):
    """Return a callable that preserves the current context across executors."""
    ctx = contextvars.copy_context()
    bound = functools.partial(fn, *args, **kwargs)
    return functools.partial(ctx.run, bound)


@contextlib.contextmanager
def with_purpose(purpose):
    token = _CURRENT_PURPOSE.set(_coerce_purpose(purpose))
    try:
        yield
    finally:
        _CURRENT_PURPOSE.reset(token)


class _InFlight:
    def __init__(self, *, purpose: BrainPurpose, priority: int):
        self.purpose = purpose
        self.priority = priority
        self.call: CancellableBrainCall | None = None
        self.cancel_requested = False
        self.preempt_timeout = False


class BrainGateway:
    """Single-slot gateway with foreground-over-background preemption."""

    def __init__(
        self,
        *,
        preempt_timeout_s: float = 1.5,
        telemetry_sink: Callable[[dict], None] | None = None,
        max_events: int = 512,
    ):
        self._preempt_timeout_s = preempt_timeout_s
        self._telemetry_sink = telemetry_sink
        self._condition = threading.Condition(threading.RLock())
        self._in_flight: _InFlight | None = None
        self.events = deque(maxlen=max(1, int(max_events)))

    def reset_for_tests(self) -> None:
        """Clear retained singleton state between hermetic tests."""
        with self._condition:
            self.events.clear()
            self._in_flight = None
            self._condition.notify_all()

    def submit(self, *, purpose, run_streaming_fn: Callable[[], Iterable]) -> str:
        purpose = _coerce_purpose(purpose)
        priority = priority_of(purpose)
        wait_started = time.monotonic()
        slot_busy_before = False
        preempted_count = 0
        preempt_timeout = False
        record: _InFlight | None = None

        try:
            record, slot_busy_before, preempted_count, preempt_timeout = (
                self._reserve_slot(
                    purpose=purpose,
                    priority=priority,
                    slot_busy_before=slot_busy_before,
                    preempted_count=preempted_count,
                    preempt_timeout=preempt_timeout,
                )
            )
            wait_ms = (time.monotonic() - wait_started) * 1000.0
            raw_stream = run_streaming_fn()
            call = (
                raw_stream
                if isinstance(raw_stream, CancellableBrainCall)
                else CancellableBrainCall(
                    raw_stream=raw_stream,
                    preempt_timeout_s=self._preempt_timeout_s,
                )
            )
            with self._condition:
                record.call = call
                cancel_requested = record.cancel_requested
            if cancel_requested:
                if call.cancel():
                    record.preempt_timeout = True
                    preempt_timeout = True
            reply = call.collect()
            self._emit_event(
                purpose=purpose,
                priority=priority,
                wait_ms=wait_ms,
                preempted=False,
                preempted_count=preempted_count,
                slot_busy_before=slot_busy_before,
                preempt_timeout=preempt_timeout or record.preempt_timeout,
            )
            return reply
        except BrainPreempted:
            self._emit_event(
                purpose=purpose,
                priority=priority,
                wait_ms=(time.monotonic() - wait_started) * 1000.0,
                preempted=True,
                preempted_count=preempted_count,
                slot_busy_before=slot_busy_before,
                preempt_timeout=preempt_timeout
                or (record.preempt_timeout if record is not None else False),
            )
            raise
        finally:
            if record is not None:
                self._release_slot(record)

    def _reserve_slot(
        self,
        *,
        purpose: BrainPurpose,
        priority: int,
        slot_busy_before: bool,
        preempted_count: int,
        preempt_timeout: bool,
    ) -> tuple[_InFlight, bool, int, bool]:
        while True:
            call_to_cancel = None
            with self._condition:
                current = self._in_flight
                if current is None:
                    record = _InFlight(purpose=purpose, priority=priority)
                    self._in_flight = record
                    return record, slot_busy_before, preempted_count, preempt_timeout
                slot_busy_before = True
                if priority > current.priority:
                    current.cancel_requested = True
                    call_to_cancel = current.call
                    preempted_count += 1
                else:
                    self._condition.wait(timeout=0.05)
                    continue
            if call_to_cancel is not None and call_to_cancel.cancel():
                preempt_timeout = True
            with self._condition:
                self._condition.wait(timeout=0.05)

    def _release_slot(self, record: _InFlight) -> None:
        with self._condition:
            if self._in_flight is record:
                self._in_flight = None
                self._condition.notify_all()

    def _emit_event(
        self,
        *,
        purpose: BrainPurpose,
        priority: int,
        wait_ms: float,
        preempted: bool,
        preempted_count: int,
        slot_busy_before: bool,
        preempt_timeout: bool,
    ) -> None:
        event = {
            "schema_version": 1,
            "purpose": purpose.value,
            "priority": priority,
            "wait_ms": round(wait_ms, 3),
            "preempted": bool(preempted),
            "preempted_count": int(preempted_count),
            "slot_busy_before": bool(slot_busy_before),
            "preempt_timeout": bool(preempt_timeout),
        }
        self.events.append(event)
        logger.info(
            "brain_gateway_event schema_version=%s purpose=%s priority=%s "
            "wait_ms=%s preempted=%s preempted_count=%s "
            "slot_busy_before=%s preempt_timeout=%s",
            event["schema_version"],
            event["purpose"],
            event["priority"],
            event["wait_ms"],
            event["preempted"],
            event["preempted_count"],
            event["slot_busy_before"],
            event["preempt_timeout"],
        )
        if self._telemetry_sink is not None:
            self._telemetry_sink(dict(event))


GATEWAY = BrainGateway()


def reset_gateway_state_for_tests() -> None:
    """Reset process-local gateway state for order-independent tests."""
    _CURRENT_PURPOSE.set(BrainPurpose.NEUTRAL)
    GATEWAY.reset_for_tests()
