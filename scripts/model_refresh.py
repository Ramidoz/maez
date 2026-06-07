#!/usr/bin/env python3
"""Content-free local model refresh helper.

This module prepares evidence packets and service templates for Maez model
refresh candidates. It never starts/stops services and never captures screen
content. Live starts/restarts remain owner breaths.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

DECISIONS = {"reject", "retry_with_config", "candidate", "admitted"}
SECRET_PATTERNS = (
    "restore_token",
    "data:image",
    "screen content",
    "BEGIN PRIVATE",
)


def _ensure_content_free(packet: dict[str, Any]) -> None:
    encoded = json.dumps(packet, sort_keys=True)
    lower = encoded.lower()
    for pattern in SECRET_PATTERNS:
        if pattern.lower() in lower:
            raise ValueError(f"packet contains forbidden content marker: {pattern}")


def build_packet(
    *,
    candidate: str,
    runtime_path: str,
    runtime_version: str,
    model_repo: str,
    model_files: list[str],
    license: str,
    quantization: str,
    service_port: int,
    load_status: str,
    vram_before_mib: int | None,
    vram_after_load_mib: int | None,
    vram_after_image_mib: int | None,
    smoke_status: str,
    benchmark_status: str,
    latency_ms: int | None,
    decision: str,
    rollback: str,
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError(f"invalid decision: {decision}")
    packet = {
        "candidate": candidate,
        "runtime_path": runtime_path,
        "runtime_version": runtime_version,
        "model_repo": model_repo,
        "model_files": model_files,
        "license": license,
        "quantization": quantization,
        "service_port": service_port,
        "load_status": load_status,
        "vram_before_mib": vram_before_mib,
        "vram_after_load_mib": vram_after_load_mib,
        "vram_after_image_mib": vram_after_image_mib,
        "smoke_status": smoke_status,
        "benchmark_status": benchmark_status,
        "latency_ms": latency_ms,
        "decision": decision,
        "rollback": rollback,
    }
    _ensure_content_free(packet)
    return packet


def write_packet(packet: dict[str, Any], *, root: Path, timestamp: str | None = None) -> Path:
    _ensure_content_free(packet)
    ts = timestamp or time.strftime("%Y%m%dT%H%M%S")
    candidate = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(packet["candidate"])).strip("-")
    out_dir = root / "logs" / "model_refresh"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts}-{candidate}.json"
    out_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-empty-packet", action="store_true")
    parser.add_argument("--candidate", default="qwen3vl-4b")
    args = parser.parse_args()
    if args.write_empty_packet:
        packet = build_packet(
            candidate=args.candidate,
            runtime_path="",
            runtime_version="",
            model_repo="",
            model_files=[],
            license="unknown",
            quantization="",
            service_port=8082,
            load_status="not_started",
            vram_before_mib=None,
            vram_after_load_mib=None,
            vram_after_image_mib=None,
            smoke_status="not_run",
            benchmark_status="not_run",
            latency_ms=None,
            decision="candidate",
            rollback="",
        )
        print(write_packet(packet, root=Path.cwd()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
