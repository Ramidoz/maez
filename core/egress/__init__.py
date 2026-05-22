"""Privacy / egress gate primitives."""

from core.egress.gate import (
    EgressDecision,
    EgressRequest,
    EgressSegment,
    decide_egress,
    decision_to_telemetry,
)

__all__ = [
    "EgressDecision",
    "EgressRequest",
    "EgressSegment",
    "decide_egress",
    "decision_to_telemetry",
]
