"""Content-free observation sidecar for Maez live gates.

This runner samples safe `/health` fields while implementation work continues.
It does not enable any organ, does not read raw stores, and does not log prompt,
calendar, camera-frame, or memory content.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib.request import urlopen


DEFAULT_HEALTH_URL = "http://127.0.0.1:11435/health"
DEFAULT_INTERVAL_SECONDS = 30.0
DEFAULT_DURATION_SECONDS = 3600.0
_PRESENCE_THREAD_MARKERS = ("presence", "mediapipe", "opencv", "camera")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick(mapping: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: mapping.get(key) for key in keys if key in mapping}


def project_health(
    health: dict[str, Any],
    *,
    service: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project `/health` into a content-free observation sample."""

    camera = health.get("camera_presence") or {}
    calendar = health.get("calendar") or {}
    reasoning_loop = health.get("reasoning_loop") or {}
    lived_episodes = health.get("lived_episodes") or {}
    m1 = lived_episodes.get("m1") or {}
    m1_staleness = lived_episodes.get("staleness") or {}
    credentials = health.get("credentials") or {}
    temporal_spine = health.get("temporal_spine")
    heartbeat = _pick(health, ("cycle_count",))
    heartbeat.update(
        _pick(
            reasoning_loop,
            (
                "cycle_stalled",
                "stage",
                "stage_age_seconds",
                "cycle_age_seconds",
            ),
        )
    )
    m1_sample = _pick(
        m1,
        (
            "enabled",
            "identity_fallback_count",
            "invalid_eligibility_reason_rejected_count",
            "invalid_promotion_trigger_rejected_count",
        ),
    )
    m1_sample.update(
        _pick(
            m1_staleness,
            (
                "staleness_status",
                "newest_age_hours",
                "active_count",
            ),
        )
    )

    return {
        "observed_at": _utc_now(),
        "service": {
            "active": (service or {}).get("active"),
            "nrestarts": (service or {}).get("nrestarts"),
            "main_pid": (service or {}).get("main_pid"),
            "memory_current_bytes": (service or {}).get("memory_current_bytes"),
            "tasks_current": (service or {}).get("tasks_current"),
            "presence_native_thread_count": (service or {}).get("presence_native_thread_count"),
        },
        "heartbeat": heartbeat,
        "camera_presence": _pick(
            camera,
            (
                "mode",
                "enabled",
                "sensor_state",
                "presence_state",
                "confidence_bucket",
                "last_error_class",
                "last_observed_at",
                "received_at",
                "stale_after_seconds",
                "voice_guard_rejected_count",
            ),
        ),
        "calendar": _pick(
            calendar,
            (
                "mode",
                "connector_state",
                "sync_state",
                "last_error_class",
                "cache_age_seconds",
            ),
        ),
        "m1": m1_sample,
        "credentials": _pick(
            credentials,
            (
                "source",
                "required_present",
                "missing_required_count",
                "rollback_enabled",
            ),
        ),
        "temporal_spine": _pick(
            temporal_spine or {},
            (
                "timezone_source",
                "timezone_name",
                "invalid_field_name_rejected_count",
                "malformed_timestamp_rejected_count",
                "naive_timestamp_assumed_utc_count",
                "unsupported_anchor_rejected_count",
                "helper_unavailable_count",
            ),
        ),
        "temporal_spine_present": isinstance(temporal_spine, dict),
    }


def red_gates(
    sample: dict[str, Any],
    *,
    previous_sample: dict[str, Any] | None = None,
) -> list[str]:
    """Return content-free gate names that should interrupt build flow."""

    gates: list[str] = []
    service = sample.get("service") or {}
    heartbeat = sample.get("heartbeat") or {}
    camera = sample.get("camera_presence") or {}
    m1 = sample.get("m1") or {}
    credentials = sample.get("credentials") or {}
    temporal_spine = sample.get("temporal_spine") or {}

    if service.get("active") not in (None, "active"):
        gates.append("maez_service_inactive")
    if service.get("nrestarts") not in (None, 0, "0"):
        gates.append("maez_service_restarted")
    if heartbeat.get("cycle_stalled") is True:
        gates.append("heartbeat_stalled")

    camera_error = camera.get("last_error_class") or ""
    if camera.get("enabled") and camera_error:
        gates.append(f"camera_{camera_error}")
    if _sample_int(camera, "voice_guard_rejected_count") > 0:
        gates.append("camera_presence_voice_guard_rejected")
    if not camera.get("enabled") and (service.get("presence_native_thread_count") or 0) > 0:
        gates.append("camera_presence_threads_stranded")

    if m1.get("enabled") is False:
        gates.append("m1_disabled")
    if m1.get("staleness_status") == "alarm":
        gates.append("m1_staleness_alarm")
    if _sample_int(m1, "identity_fallback_count") > 0:
        gates.append("m1_identity_fallback")
    if _sample_int(m1, "invalid_eligibility_reason_rejected_count") > 0:
        gates.append("m1_invalid_eligibility_reason_rejected")
    if _sample_int(m1, "invalid_promotion_trigger_rejected_count") > 0:
        gates.append("m1_invalid_promotion_trigger_rejected")

    if credentials.get("required_present") is False:
        gates.append("credentials_missing_required")
    if sample.get("temporal_spine_present") is False:
        gates.append("temporal_spine_unavailable")
    if temporal_spine.get("timezone_source") == "invalid_fallback_utc":
        gates.append("temporal_spine_invalid_timezone_fallback")
    if _sample_int(temporal_spine, "malformed_timestamp_rejected_count") > 0:
        gates.append("temporal_spine_malformed_timestamp_rejected")
    if _temporal_spine_counter_reset(sample, previous_sample):
        gates.append("temporal_spine_counter_reset")

    return gates


def _temporal_spine_counter_reset(
    sample: dict[str, Any],
    previous_sample: dict[str, Any] | None,
) -> bool:
    if not previous_sample:
        return False
    service = sample.get("service") or {}
    previous_service = previous_sample.get("service") or {}
    if not service.get("main_pid") or service.get("main_pid") != previous_service.get("main_pid"):
        return False
    if (
        sample.get("temporal_spine_present") is not True
        or previous_sample.get("temporal_spine_present") is not True
    ):
        return False
    temporal_spine = sample.get("temporal_spine") or {}
    previous_temporal_spine = previous_sample.get("temporal_spine") or {}
    for key in (
        "invalid_field_name_rejected_count",
        "malformed_timestamp_rejected_count",
        "naive_timestamp_assumed_utc_count",
        "unsupported_anchor_rejected_count",
        "helper_unavailable_count",
    ):
        if _sample_int(temporal_spine, key) < _sample_int(previous_temporal_spine, key):
            return True
    return False


def fetch_health(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_int(raw: str) -> int | None:
    try:
        return int((raw or "").strip())
    except (TypeError, ValueError):
        return None


def _sample_int(mapping: dict[str, Any], key: str) -> int:
    raw = mapping.get(key)
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    parsed = _parse_int(str(raw)) if raw is not None else None
    return parsed if parsed is not None else 0


def _systemctl_show_value(prop: str) -> str:
    return subprocess.run(
        ["systemctl", "--user", "show", "maez.service", "-p", prop, "--value"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def presence_native_thread_count(
    pid: int | None,
    *,
    proc_root: Path = Path("/proc"),
) -> int:
    """Count camera/native-looking daemon threads without recording names."""

    if not pid or pid <= 0:
        return 0
    task_dir = proc_root / str(pid) / "task"
    if not task_dir.exists():
        return 0
    count = 0
    for comm_path in task_dir.glob("*/comm"):
        try:
            name = comm_path.read_text(encoding="utf-8", errors="replace").strip().lower()
        except OSError:
            continue
        if any(marker in name for marker in _PRESENCE_THREAD_MARKERS):
            count += 1
    return count


def service_status() -> dict[str, Any]:
    active = subprocess.run(
        ["systemctl", "--user", "is-active", "maez.service"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    nrestarts_raw = _systemctl_show_value("NRestarts")
    nrestarts = _parse_int(nrestarts_raw)
    main_pid = _parse_int(_systemctl_show_value("MainPID"))
    memory_current = _parse_int(_systemctl_show_value("MemoryCurrent"))
    tasks_current = _parse_int(_systemctl_show_value("TasksCurrent"))
    return {
        "active": active or None,
        "nrestarts": nrestarts if nrestarts is not None else nrestarts_raw or None,
        "main_pid": main_pid,
        "memory_current_bytes": memory_current,
        "tasks_current": tasks_current,
        "presence_native_thread_count": presence_native_thread_count(main_pid),
    }


def default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("logs") / "observations" / f"maez_observation_{stamp}.jsonl"


def write_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def run(
    *,
    health_url: str,
    output_path: Path,
    duration_seconds: float,
    interval_seconds: float,
    fail_fast: bool,
) -> int:
    deadline = time.monotonic() + duration_seconds
    samples = 0
    red: list[str] = []
    previous_sample: dict[str, Any] | None = None

    while True:
        try:
            sample = project_health(fetch_health(health_url), service=service_status())
            sample["red_gates"] = red_gates(sample, previous_sample=previous_sample)
        except Exception as exc:
            sample = {
                "observed_at": _utc_now(),
                "service": {},
                "heartbeat": {},
                "camera_presence": {},
                "calendar": {},
                "m1": {},
                "credentials": {},
                "temporal_spine": {},
                "temporal_spine_present": False,
                "red_gates": ["observation_fetch_failed"],
                "error_class": exc.__class__.__name__,
            }

        write_jsonl(output_path, sample)
        samples += 1
        red.extend(str(gate) for gate in sample.get("red_gates") or [])
        if fail_fast and sample.get("red_gates"):
            break
        if time.monotonic() >= deadline:
            break
        previous_sample = sample
        time.sleep(interval_seconds)

    summary = {
        "observed_at": _utc_now(),
        "event": "observation_summary",
        "samples": samples,
        "red_gates": sorted(set(red)),
        "output_path": str(output_path),
    }
    write_jsonl(output_path, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if red else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument("--out", type=Path, default=default_output_path())
    parser.add_argument("--duration-seconds", type=float, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--interval-seconds", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args(argv)

    return run(
        health_url=args.health_url,
        output_path=args.out,
        duration_seconds=max(0.0, args.duration_seconds),
        interval_seconds=max(1.0, args.interval_seconds),
        fail_fast=bool(args.fail_fast),
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
