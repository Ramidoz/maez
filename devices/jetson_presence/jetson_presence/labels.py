"""Pure B0 label rule for the Jetson edge producer.

Self-contained (the Jetson deploys only this package), but a host test pins its
constants against core.body.jetson_presence so the edge cannot drift from the
doorway. B0 always emits owner_present=unknown, confidence=low.
"""

from __future__ import annotations

SCHEMA_VERSION = "jetson_presence.v0"
SENSOR_STATES = frozenset({"available", "unavailable", "curtained", "unenrolled", "error"})
FIXED_OWNER_PRESENT = "unknown"  # B0: no recognition; never present/absent
FIXED_CONFIDENCE = "low"  # B0: fixed; never derived (no occupancy leak)


def build_label(sensor_state: str, ts: str) -> dict:
    """Return the five-field jetson_presence.v0 label for B0.

    owner_present and confidence are fixed; only sensor_state and ts vary.
    """
    if sensor_state not in SENSOR_STATES:
        raise ValueError(f"unknown sensor_state: {sensor_state!r}")
    return {
        "owner_present": FIXED_OWNER_PRESENT,
        "confidence": FIXED_CONFIDENCE,
        "sensor_state": sensor_state,
        "ts": ts,
        "schema_version": SCHEMA_VERSION,
    }
