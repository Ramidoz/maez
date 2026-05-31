"""One truthful substrate-backed recall progress receipt.

This module owns the content-free receipt state and timing vocabulary. The
daemon observes runtime state; this module only classifies whether the observed
receipt was eligible, emitted, or unavailable.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum

RECEIPT_AFTER_MS = 900
ACK_CEILING_MS = 1500
RECEIPT_SEND_TIMEOUT_MS = 1000

WORKING_RECEIPT_TEXT = "I'm checking my dated memory for that."
FORBIDDEN_COGNITION_VERBS = (
    "think",
    "thinking",
    "ponder",
    "consider",
    "wonder",
    "mull",
    "reflect",
    "feel",
    "sense",
)


class AckStatus(Enum):
    NOT_REQUIRED_FAST_ANSWER = "not_required_fast_answer"
    EMITTED = "emitted"
    SEND_FAILED = "send_failed"
    SEND_TIMEOUT = "send_timeout"
    DISABLED = "disabled"
    NOT_ELIGIBLE = "not_eligible"


@dataclass(frozen=True)
class ReceiptAckSnapshot:
    fired: bool
    send_result: str | None
    ack_emit_ms: int | None
    cancelled: bool


class ReceiptAckBox:
    """Thread-safe turn-local receipt acknowledgement state.

    The timer thread marks that it fired; the surface loop later records the
    first terminal send result. `ack_emit_ms` is completion time, not enqueue
    time.
    """

    def __init__(self, *, turn_started_mono: float) -> None:
        self._turn_started_mono = turn_started_mono
        self._lock = threading.Lock()
        self._cancelled = False
        self._fired = False
        self._send_result: str | None = None
        self._ack_emit_ms: int | None = None

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    def try_mark_fired(self) -> bool:
        with self._lock:
            if self._cancelled or self._fired:
                return False
            self._fired = True
            return True

    def mark_ok(self, *, completed_mono: float) -> None:
        self._mark_terminal("ok", completed_mono=completed_mono)

    def mark_failed(self, *, completed_mono: float) -> None:
        self._mark_terminal("failed", completed_mono=completed_mono)

    def mark_timeout(self, *, completed_mono: float) -> None:
        self._mark_terminal("timeout", completed_mono=completed_mono)

    def _mark_terminal(self, result: str, *, completed_mono: float) -> None:
        with self._lock:
            if self._send_result is not None:
                return
            self._send_result = result
            self._ack_emit_ms = max(
                0,
                int((completed_mono - self._turn_started_mono) * 1000),
            )

    def snapshot(self, *, now_mono: float | None = None) -> ReceiptAckSnapshot:
        del now_mono  # Reserved for future derived timing without changing API.
        with self._lock:
            return ReceiptAckSnapshot(
                fired=self._fired,
                send_result=self._send_result,
                ack_emit_ms=self._ack_emit_ms,
                cancelled=self._cancelled,
            )


def receipt_eligible(
    *,
    flag_on: bool,
    focused_carrier_engaged: bool,
    surface_sink_available: bool = True,
) -> bool:
    """True only when the observed carrier path can honestly emit a receipt."""
    return bool(flag_on and focused_carrier_engaged and surface_sink_available)


def resolve_ack_status(
    *,
    eligible: bool,
    fired: bool,
    send_result,
    disabled: bool = False,
    ack_required: bool = False,
) -> str:
    if disabled:
        return AckStatus.DISABLED.value
    if not eligible:
        return AckStatus.NOT_ELIGIBLE.value
    if not fired:
        if ack_required:
            # The answer crossed the real-wait threshold, but no receipt made it
            # to the timer/surface completion path. Score it as an ack miss.
            return AckStatus.SEND_TIMEOUT.value
        return AckStatus.NOT_REQUIRED_FAST_ANSWER.value
    if send_result is None:
        return AckStatus.SEND_TIMEOUT.value
    return {
        "ok": AckStatus.EMITTED.value,
        "failed": AckStatus.SEND_FAILED.value,
        "timeout": AckStatus.SEND_TIMEOUT.value,
    }.get(send_result, AckStatus.SEND_FAILED.value)
