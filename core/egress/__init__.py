"""Privacy / egress gate primitives."""

from core.egress import external_fetch as external_fetch
from core.egress.gate import (
    EgressDecision,
    EgressRequest,
    EgressSegment,
    decide_egress,
    decision_to_telemetry,
)
from core.egress.provenance import ProvenanceSpan, ProvenancedText

__all__ = [
    "EgressDecision",
    "EgressRequest",
    "EgressSegment",
    "ProvenanceSpan",
    "ProvenancedText",
    "decide_egress",
    "decision_to_telemetry",
    "external_fetch",
]
