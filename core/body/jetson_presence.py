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

# Only the contract crosses: the wire payload's key set must be EXACTLY these.
# Any extra (visitor/raw-media/spatial) OR missing key rejects the label.
_ALLOWED_KEYS = frozenset({"owner_present", "confidence", "sensor_state", "ts", "schema_version"})


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
    # Strict key-set: only the contract crosses — no visitor/raw-media/spatial fields.
    if set(raw.keys()) != _ALLOWED_KEYS:
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


def effective_state(
    reading: JetsonPresenceReading | None,
    *,
    received_at: float | None,
    now: float,
    stale_after: float,
) -> tuple[str, str]:
    """Return the host-authoritative (owner_present, sensor_state).

    Honesty rules, in precedence order:
      1. No reading / never received -> (unknown, unavailable).
      2. No fresh label within `stale_after` of host `received_at` -> (unknown, stale).
         Sensor silence is NEVER read as `absent`.
      3. A fresh `curtained` label outranks all other fresh states -> (unknown, curtained).
      4. Otherwise pass the fresh label through.
    `now` and `received_at` are host clock seconds; the Jetson's own ts is never used here.
    """
    if reading is None or received_at is None:
        return ("unknown", "unavailable")
    if (now - received_at) > stale_after:
        return ("unknown", "stale")
    if reading.sensor_state == "curtained":
        return ("unknown", "curtained")
    return (reading.owner_present, reading.sensor_state)


def jetson_presence_shadow_enabled() -> bool:
    """Default-off shadow flag. Behaviorally-unavailable-off: callers must skip all work when False."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_JETSON_PRESENCE_SHADOW")
