# core/body/jetson_presence.py
"""jetson_presence.v0 contract: pure label validation + the freshness honesty rule.

No I/O. The Jetson emits content-light owner-presence labels; this module is the
single place that decides what a label means — including the load-bearing rule that
a stale/missing label is `unknown`, never `absent`.
"""
from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = "jetson_presence.v0"

# Wire-valid enums (what the Jetson may emit). `stale` is NOT wire-valid — it is
# host-derived only (see effective_state).
_OWNER_PRESENT = frozenset({"present", "absent", "unknown"})
_CONFIDENCE = frozenset({"low", "medium", "high"})
_SENSOR_STATE_WIRE = frozenset({"available", "unavailable", "curtained", "unenrolled", "error"})


@dataclass(frozen=True)
class JetsonPresenceReading:
    owner_present: str
    confidence: str
    sensor_state: str
    observed_at: str  # the Jetson's self-reported ts — diagnostic only, never the duration authority


def parse_label(raw: object) -> JetsonPresenceReading | None:
    """Validate a raw payload into a reading, or return None if malformed."""
    if not isinstance(raw, dict):
        return None
    if raw.get("schema_version") != SCHEMA_VERSION:
        return None
    owner_present = raw.get("owner_present")
    confidence = raw.get("confidence")
    sensor_state = raw.get("sensor_state")
    observed_at = raw.get("ts")
    if owner_present not in _OWNER_PRESENT:
        return None
    if confidence not in _CONFIDENCE:
        return None
    if sensor_state not in _SENSOR_STATE_WIRE:
        return None
    if not isinstance(observed_at, str) or not observed_at.strip():
        return None
    # Cross-field consistency: a coherent reading can only claim present/absent
    # when the sensor is actually available. Any non-available sensor_state
    # (curtained/unenrolled/unavailable/error) MUST report owner_present=unknown,
    # or the label is incoherent and rejected.
    if sensor_state != "available" and owner_present != "unknown":
        return None
    return JetsonPresenceReading(
        owner_present=owner_present,
        confidence=confidence,
        sensor_state=sensor_state,
        observed_at=observed_at,
    )
