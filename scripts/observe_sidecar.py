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
    m1 = ((health.get("lived_episodes") or {}).get("m1")) or {}
    credentials = health.get("credentials") or {}

    return {
        "observed_at": _utc_now(),
        "service": {
            "active": (service or {}).get("active"),
            "nrestarts": (service or {}).get("nrestarts"),
        },
        "heartbeat": _pick(
            health,
            (
                "cycle_count",
                "cycle_stalled",
                "stage",
                "stage_age_seconds",
                "cycle_age_seconds",
            ),
        ),
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
        "m1": _pick(
            m1,
            (
                "enabled",
                "staleness_status",
                "newest_age_hours",
                "active_count",
            ),
        ),
        "credentials": _pick(
            credentials,
            (
                "source",
                "required_present",
                "missing_required_count",
                "rollback_enabled",
            ),
        ),
    }


def red_gates(sample: dict[str, Any]) -> list[str]:
    """Return content-free gate names that should interrupt build flow."""

    gates: list[str] = []
    service = sample.get("service") or {}
    heartbeat = sample.get("heartbeat") or {}
    camera = sample.get("camera_presence") or {}
    m1 = sample.get("m1") or {}
    credentials = sample.get("credentials") or {}

    if service.get("active") not in (None, "active"):
        gates.append("maez_service_inactive")
    if service.get("nrestarts") not in (None, 0, "0"):
        gates.append("maez_service_restarted")
    if heartbeat.get("cycle_stalled") is True:
        gates.append("heartbeat_stalled")

    camera_error = camera.get("last_error_class") or ""
    if camera.get("enabled") and camera_error:
        gates.append(f"camera_{camera_error}")

    if m1.get("enabled") is False:
        gates.append("m1_disabled")
    if m1.get("staleness_status") == "alarm":
        gates.append("m1_staleness_alarm")

    if credentials.get("required_present") is False:
        gates.append("credentials_missing_required")

    return gates


def fetch_health(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def service_status() -> dict[str, Any]:
    active = subprocess.run(
        ["systemctl", "--user", "is-active", "maez.service"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    nrestarts_raw = subprocess.run(
        ["systemctl", "--user", "show", "maez.service", "-p", "NRestarts", "--value"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    try:
        nrestarts: int | str | None = int(nrestarts_raw)
    except ValueError:
        nrestarts = nrestarts_raw or None
    return {"active": active or None, "nrestarts": nrestarts}


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

    while True:
        try:
            sample = project_health(fetch_health(health_url), service=service_status())
            sample["red_gates"] = red_gates(sample)
        except Exception as exc:
            sample = {
                "observed_at": _utc_now(),
                "service": {},
                "heartbeat": {},
                "camera_presence": {},
                "calendar": {},
                "m1": {},
                "credentials": {},
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
