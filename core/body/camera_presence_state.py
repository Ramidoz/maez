"""Camera Presence v1 state and health contract.

Decision 24 / ADR 0029 treats camera presence as a timeboxed body sensor. This
module deliberately holds only content-free state: no frames, names, room
descriptions, biometric identifiers, or durable presence history.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
from typing import Mapping


MODE_ENV = "MAEZ_CAMERA_PRESENCE_MODE"
ENABLED_UNTIL_ENV = "MAEZ_CAMERA_PRESENCE_ENABLED_UNTIL"

SCHEMA_VERSION = "camera_presence.v1"
SOURCE_KIND = "body_sensor.camera_presence"
EVENT_KIND = "presence.observed"
SOURCE_ID = "aurora_camera_presence"
SOURCE_INSTANCE_ID = "aurora_camera_presence.primary"
DEFAULT_STALE_AFTER_SECONDS = 180

VALID_MODES = frozenset({"disabled", "observe", "expired_disabled"})
VALID_PRESENCE_STATES = frozenset({"present", "absent", "unknown", "sensor_unavailable"})
VALID_SENSOR_STATES = frozenset({"disabled", "available", "unavailable", "stale", "unknown"})
VALID_CONFIDENCE_BUCKETS = frozenset({"none", "low", "medium", "high", "unavailable"})
VALID_ERROR_CLASSES = frozenset(
    {
        "",
        "dependency_missing",
        "model_missing",
        "camera_unavailable",
        "camera_busy",
        "detector_timeout",
        "detector_error",
        "native_shutdown_timeout",
        "timebox_expired",
        "config_invalid",
        "unknown",
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_enabled_until(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("enabled_until must include timezone")
    return parsed.astimezone(timezone.utc)


def _telemetry_handle(source_instance_id: str = SOURCE_INSTANCE_ID) -> str:
    digest = hashlib.sha256(source_instance_id.encode("utf-8")).hexdigest()
    return f"camera_presence:{digest[:12]}"


def normalize_error_class(error_class: str) -> str:
    """Map raw detector/runtime failures to the closed content-free vocabulary."""

    raw = (error_class or "").strip()
    if raw in VALID_ERROR_CLASSES:
        return raw
    lowered = raw.lower()
    if not lowered:
        return ""
    if "timeout" in lowered or "timed out" in lowered:
        return "detector_timeout"
    if "model" in lowered or "blaze_face" in lowered:
        return "model_missing"
    if "still running" in lowered or "worker unavailable" in lowered:
        return "camera_busy"
    if "cv2 unavailable" in lowered or "mediapipe unavailable" in lowered:
        return "dependency_missing"
    if "dependency" in lowered or "no module named" in lowered or "shared object" in lowered:
        return "dependency_missing"
    if "camera" in lowered and ("busy" in lowered or "in use" in lowered):
        return "camera_busy"
    if "camera" in lowered and ("unavailable" in lowered or "not available" in lowered or "cannot open" in lowered):
        return "camera_unavailable"
    if "shutdown" in lowered:
        return "native_shutdown_timeout"
    if "timebox" in lowered or "enabled_until" in lowered:
        return "timebox_expired"
    if "config" in lowered:
        return "config_invalid"
    if "detector" in lowered or "detection" in lowered:
        return "detector_error"
    return "unknown"


@dataclass(frozen=True)
class CameraPresenceReading:
    presence_state: str
    confidence_bucket: str
    observed_at: datetime
    sensor_state: str = "available"
    last_error_class: str = ""

    def __post_init__(self) -> None:
        if self.presence_state not in VALID_PRESENCE_STATES:
            raise ValueError(f"invalid presence_state: {self.presence_state!r}")
        if self.confidence_bucket not in VALID_CONFIDENCE_BUCKETS:
            raise ValueError(f"invalid confidence_bucket: {self.confidence_bucket!r}")
        if self.last_error_class not in VALID_ERROR_CLASSES:
            raise ValueError(f"invalid last_error_class: {self.last_error_class!r}")
        if self.sensor_state not in VALID_SENSOR_STATES:
            raise ValueError(f"invalid sensor_state: {self.sensor_state!r}")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must include timezone")


@dataclass(frozen=True)
class ObservationToken:
    mode: str
    enabled_until: str
    submitted_at: datetime


@dataclass(frozen=True)
class CameraPresenceState:
    mode: str = "disabled"
    enabled_until: str = ""
    enabled_until_at: datetime | None = None
    sensor_state: str = "disabled"
    presence_state: str = "unknown"
    confidence_bucket: str = "none"
    last_observed_at: datetime | None = None
    received_at: datetime | None = None
    last_error_class: str = ""
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS
    schema_version: str = SCHEMA_VERSION
    source_kind: str = SOURCE_KIND
    event_kind: str = EVENT_KIND
    source_id: str = SOURCE_ID
    source_instance_id: str = SOURCE_INSTANCE_ID
    telemetry_handle: str = _telemetry_handle()

    def __post_init__(self) -> None:
        if self.mode not in VALID_MODES:
            raise ValueError(f"invalid mode: {self.mode!r}")
        if self.sensor_state not in VALID_SENSOR_STATES:
            raise ValueError(f"invalid sensor_state: {self.sensor_state!r}")
        if self.presence_state not in VALID_PRESENCE_STATES:
            raise ValueError(f"invalid presence_state: {self.presence_state!r}")
        if self.confidence_bucket not in VALID_CONFIDENCE_BUCKETS:
            raise ValueError(f"invalid confidence_bucket: {self.confidence_bucket!r}")
        if self.last_error_class not in VALID_ERROR_CLASSES:
            raise ValueError(f"invalid last_error_class: {self.last_error_class!r}")

    @property
    def enabled(self) -> bool:
        return self.mode == "observe"

    def make_observation_token(self, *, submitted_at: datetime | None = None) -> ObservationToken:
        submitted = submitted_at or _utc_now()
        if submitted.tzinfo is None:
            raise ValueError("submitted_at must include timezone")
        return ObservationToken(
            mode=self.mode,
            enabled_until=self.enabled_until,
            submitted_at=submitted.astimezone(timezone.utc),
        )

    def commit_observation(
        self,
        reading: CameraPresenceReading,
        *,
        token: ObservationToken,
        now: datetime | None = None,
        shutdown_started: bool = False,
    ) -> "CameraPresenceState":
        current_time = (now or _utc_now()).astimezone(timezone.utc)
        if not self._token_still_valid(token=token, now=current_time, shutdown_started=shutdown_started):
            return self.with_freshness(now=current_time)
        observed_at = reading.observed_at.astimezone(timezone.utc)
        return replace(
            self,
            sensor_state=reading.sensor_state,
            presence_state=reading.presence_state,
            confidence_bucket=reading.confidence_bucket,
            last_observed_at=observed_at,
            received_at=current_time,
            last_error_class=reading.last_error_class,
        ).with_freshness(now=current_time)

    def commit_unavailable(
        self,
        error_class: str,
        *,
        token: ObservationToken,
        now: datetime | None = None,
        shutdown_started: bool = False,
    ) -> "CameraPresenceState":
        current_time = (now or _utc_now()).astimezone(timezone.utc)
        if not self._token_still_valid(token=token, now=current_time, shutdown_started=shutdown_started):
            return self.with_freshness(now=current_time)
        return self.unavailable(error_class=error_class, now=current_time)

    def _token_still_valid(
        self,
        *,
        token: ObservationToken,
        now: datetime,
        shutdown_started: bool,
    ) -> bool:
        return (
            not shutdown_started
            and self.mode == "observe"
            and token.mode == "observe"
            and token.enabled_until == self.enabled_until
            and self.enabled_until_at is not None
            and now < self.enabled_until_at
        )

    def with_freshness(self, *, now: datetime | None = None) -> "CameraPresenceState":
        current_time = (now or _utc_now()).astimezone(timezone.utc)
        if self.mode == "observe" and self.enabled_until_at is not None and current_time >= self.enabled_until_at:
            return replace(
                self,
                mode="expired_disabled",
                sensor_state="disabled",
                presence_state="unknown",
                confidence_bucket="none",
                last_error_class="timebox_expired",
            )
        if self.mode != "observe":
            return replace(
                self,
                sensor_state="disabled",
                presence_state="unknown",
                confidence_bucket="none",
            )
        if self.last_observed_at is None:
            return replace(
                self,
                sensor_state="unknown",
                presence_state="unknown",
                confidence_bucket="none",
            )
        age_seconds = (current_time - self.last_observed_at.astimezone(timezone.utc)).total_seconds()
        if age_seconds > self.stale_after_seconds:
            return replace(
                self,
                sensor_state="stale",
                presence_state="unknown",
                confidence_bucket="none",
            )
        return self

    def unavailable(self, *, error_class: str, now: datetime | None = None) -> "CameraPresenceState":
        return replace(
            self,
            sensor_state="unavailable",
            presence_state="sensor_unavailable",
            confidence_bucket="unavailable",
            received_at=(now or _utc_now()).astimezone(timezone.utc),
            last_error_class=normalize_error_class(error_class),
        )

    def to_health(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "enabled_until": self.enabled_until,
            "schema_version": self.schema_version,
            "source_kind": self.source_kind,
            "event_kind": self.event_kind,
            "source_id": self.source_id,
            "source_instance_id": self.source_instance_id,
            "telemetry_handle": self.telemetry_handle,
            "sensor_state": self.sensor_state,
            "presence_state": self.presence_state,
            "confidence_bucket": self.confidence_bucket,
            "last_observed_at": self.last_observed_at.isoformat()
            if self.last_observed_at
            else "",
            "received_at": self.received_at.isoformat() if self.received_at else "",
            "last_error_class": self.last_error_class,
            "stale_after_seconds": self.stale_after_seconds,
        }


def resolve_camera_presence_state(
    env: Mapping[str, str],
    *,
    now: datetime | None = None,
) -> CameraPresenceState:
    current_time = (now or _utc_now()).astimezone(timezone.utc)
    raw_mode = (env.get(MODE_ENV) or "disabled").strip().lower()
    if raw_mode in {"", "disabled"}:
        return CameraPresenceState()
    if raw_mode == "developer_legacy":
        return CameraPresenceState(last_error_class="config_invalid")
    if raw_mode != "observe":
        return CameraPresenceState(last_error_class="config_invalid")

    raw_enabled_until = (env.get(ENABLED_UNTIL_ENV) or "").strip()
    if not raw_enabled_until:
        return CameraPresenceState(last_error_class="config_invalid")
    try:
        enabled_until_at = _parse_enabled_until(raw_enabled_until)
    except ValueError:
        return CameraPresenceState(last_error_class="config_invalid")
    if current_time >= enabled_until_at:
        return CameraPresenceState(
            mode="expired_disabled",
            enabled_until=raw_enabled_until,
            enabled_until_at=enabled_until_at,
            last_error_class="timebox_expired",
        )
    return CameraPresenceState(
        mode="observe",
        enabled_until=raw_enabled_until,
        enabled_until_at=enabled_until_at,
        sensor_state="unknown",
        last_error_class="",
    )
