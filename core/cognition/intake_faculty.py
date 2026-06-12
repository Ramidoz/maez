"""Intake Understanding Faculty v0 — schema and instrument interfaces.

The faculty is an instrument: it proposes a read of owner-turn meaning. It
never grants permission and never executes an action.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any

TURN_KINDS = frozenset({
    "commitment_response",
    "boundary",
    "continuity_reference",
    "recall_request",
    "search_request",
    "topic_shift",
    "ordinary",
    "ambiguous",
})
STANCES = frozenset({"yes", "no", "ambiguous", "n_a"})
BOUNDARY_SIGNALS = frozenset({"none", "soft", "hard"})
NEEDS = frozenset({"search", "recall", "none"})
REFERENT_KINDS = frozenset({"pending_offer", "earlier_topic", "none"})
STATUSES = frozenset({"ok", "judge_busy", "timeout", "parse_error", "backend_error"})


def _bucket(confidence: Any) -> str:
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return "unknown"
    if value >= 0.75:
        return "high"
    if value >= 0.45:
        return "medium"
    if value >= 0.0:
        return "low"
    return "unknown"


@dataclass(frozen=True)
class IntakeRead:
    turn_kind: str
    stance: str
    boundary_signal: str
    needs: str
    referent_kind: str
    confidence: float | None
    rationale: str = ""
    status: str = "ok"

    @property
    def confidence_bucket(self) -> str:
        return _bucket(self.confidence)

    @classmethod
    def ambiguous(cls, *, status: str = "parse_error") -> "IntakeRead":
        safe_status = status if status in STATUSES else "parse_error"
        return cls(
            turn_kind="ambiguous",
            stance="ambiguous",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=None,
            rationale="",
            status=safe_status,
        )

    @classmethod
    def from_model(cls, data: Any) -> "IntakeRead":
        if not isinstance(data, dict):
            return cls.ambiguous(status="parse_error")

        turn_kind = data.get("turn_kind")
        stance = data.get("stance")
        boundary_signal = data.get("boundary_signal")
        needs = data.get("needs")
        referent_kind = data.get("referent_kind")
        if (
            turn_kind not in TURN_KINDS
            or stance not in STANCES
            or boundary_signal not in BOUNDARY_SIGNALS
            or needs not in NEEDS
            or referent_kind not in REFERENT_KINDS
        ):
            return cls.ambiguous(status="parse_error")
        try:
            confidence = float(data.get("confidence"))
        except (TypeError, ValueError):
            confidence = None
        if confidence is not None:
            confidence = max(0.0, min(1.0, confidence))
        rationale = str(data.get("rationale") or "")[:240]
        return cls(
            turn_kind=turn_kind,
            stance=stance,
            boundary_signal=boundary_signal,
            needs=needs,
            referent_kind=referent_kind,
            confidence=confidence,
            rationale=rationale,
            status="ok",
        )

    def to_telemetry(self, *, debug: bool = False) -> dict[str, Any]:
        rec = {
            "turn_kind": self.turn_kind,
            "stance": self.stance,
            "boundary_signal": self.boundary_signal,
            "needs": self.needs,
            "referent_kind": self.referent_kind,
            "confidence_bucket": self.confidence_bucket,
            "status": self.status,
        }
        if debug and self.rationale:
            rec["rationale"] = self.rationale
        return rec


class FakeIntakeBackend:
    """Tests only. Scripted reads; never touches the real judge service."""

    def __init__(self, scripted=None, *, default: IntakeRead | None = None, busy=False, raises=None, sleep_s=0.0):
        self._scripted = dict(scripted or {})
        self._default = default or IntakeRead(
            turn_kind="ordinary",
            stance="n_a",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=0.8,
            rationale="ordinary turn",
        )
        self._busy = busy
        self._raises = raises
        self._sleep_s = sleep_s
        self.calls: list[tuple[str, dict]] = []

    def read(self, message: str, context: dict, timeout_s: float) -> tuple[IntakeRead, float]:
        started = time.monotonic()
        self.calls.append((message, context))
        if self._raises is not None:
            raise self._raises
        if self._sleep_s:
            time.sleep(self._sleep_s)
        if self._busy:
            return IntakeRead.ambiguous(status="judge_busy"), time.monotonic() - started
        return self._scripted.get(message, self._default), time.monotonic() - started


def parse_json_read(text: str) -> IntakeRead:
    try:
        return IntakeRead.from_model(json.loads(text or ""))
    except Exception:
        return IntakeRead.ambiguous(status="parse_error")
