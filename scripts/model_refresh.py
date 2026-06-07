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
import subprocess
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
SAFE_STEM_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_ALIAS_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _ensure_content_free(packet: dict[str, Any]) -> None:
    encoded = json.dumps(packet, sort_keys=True)
    lower = encoded.lower()
    for pattern in SECRET_PATTERNS:
        if pattern.lower() in lower:
            raise ValueError(f"packet contains forbidden content marker: {pattern}")


def _validated_timestamp(timestamp: str | None) -> str:
    if timestamp is None:
        return time.strftime("%Y%m%dT%H%M%S")
    if not timestamp:
        raise ValueError("timestamp must not be empty")
    if "/" in timestamp or "\\" in timestamp or ".." in timestamp:
        raise ValueError(f"unsafe timestamp: {timestamp}")
    if not SAFE_STEM_RE.fullmatch(timestamp):
        raise ValueError(f"unsafe timestamp: {timestamp}")
    return timestamp


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
    ts = _validated_timestamp(timestamp)
    candidate = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(packet["candidate"])).strip("-")
    out_dir = root / "logs" / "model_refresh"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ts}-{candidate}.json"
    out_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    return out_path


def parse_llama_help(help_text: str) -> dict[str, bool]:
    spec_line = ""
    for line in help_text.splitlines():
        if "--spec-type" in line:
            spec_line = line.lower()
            break
    return {
        "mmproj": "--mmproj" in help_text,
        "mmproj_offload": "--mmproj-offload" in help_text,
        "mtp": "mtp" in spec_line,
    }


def parse_nvidia_smi_csv(row: str) -> dict[str, int]:
    parts = [p.strip() for p in row.split(",")]
    if len(parts) != 4:
        raise ValueError(f"expected 4 nvidia-smi csv fields, got {len(parts)}")

    def mib(text: str) -> int:
        match = re.fullmatch(r"(\d+)\s*MiB", text)
        if not match:
            raise ValueError(f"missing MiB value: {text}")
        return int(match.group(1))

    return {
        "total_mib": mib(parts[1]),
        "used_mib": mib(parts[2]),
        "free_mib": mib(parts[3]),
    }


def response_has_model_alias(response: dict[str, Any], alias: str) -> bool:
    for item in response.get("data", []):
        names = {item.get("id"), item.get("model"), item.get("name")}
        names.update(item.get("aliases") or [])
        if alias in names:
            return True
    for item in response.get("models", []):
        names = {item.get("id"), item.get("model"), item.get("name")}
        names.update(item.get("aliases") or [])
        if alias in names:
            return True
    return False


def _contains_control_char(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def _validate_service_path(name: str, value: str) -> None:
    if not value:
        raise ValueError(f"{name} must not be empty")
    if _contains_control_char(value):
        raise ValueError(f"{name} must not contain control characters")
    if any(char.isspace() for char in value):
        raise ValueError(f"{name} must not contain whitespace")


def _validate_service_alias(alias: str) -> None:
    if not alias:
        raise ValueError("alias must not be empty")
    if not SAFE_ALIAS_RE.fullmatch(alias):
        raise ValueError("alias must match [A-Za-z0-9_.-]+")


def render_vision_service(
    *,
    runtime: str,
    model: str,
    mmproj: str,
    alias: str,
    port: int,
    ctx_size: int,
) -> str:
    _validate_service_path("runtime", runtime)
    _validate_service_path("model", model)
    _validate_service_path("mmproj", mmproj)
    _validate_service_alias(alias)
    if not 1 <= port <= 65535:
        raise ValueError("vision service port must be in 1..65535")
    if port == 8081:
        raise ValueError("vision service must not use the judge port 8081")
    if port == 8080:
        raise ValueError("vision service must not use the main brain port 8080")
    return f"""[Unit]
Description=llama.cpp vision server (Maez local multimodal endpoint)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/rohit/maez
ExecStart={runtime} \\
  -m {model} \\
  --mmproj {mmproj} \\
  --alias {alias} \\
  --host 127.0.0.1 \\
  --port {port} \\
  --ctx-size {ctx_size} \\
  --n-gpu-layers 999 \\
  --flash-attn on \\
  --cache-type-k q4_0 \\
  --cache-type-v q4_0 \\
  --image-max-tokens 1024
Restart=on-failure
Environment=GGML_VK_VISIBLE_DEVICES=0

[Install]
WantedBy=default.target
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-empty-packet", action="store_true")
    parser.add_argument("--candidate", default="qwen3vl-4b")
    parser.add_argument("--llama-server", help="Path to llama-server for help/version discovery")
    parser.add_argument("--nvidia-smi-row", help="Parse one nvidia-smi CSV row and print JSON")
    parser.add_argument("--render-vision-service", action="store_true")
    parser.add_argument("--runtime", default="")
    parser.add_argument("--model-path", default="")
    parser.add_argument("--mmproj-path", default="")
    parser.add_argument("--alias", default="maez-vision")
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--ctx-size", type=int, default=4096)
    args = parser.parse_args()
    if args.render_vision_service:
        print(
            render_vision_service(
                runtime=args.runtime,
                model=args.model_path,
                mmproj=args.mmproj_path,
                alias=args.alias,
                port=args.port,
                ctx_size=args.ctx_size,
            )
        )
        return 0
    if args.llama_server:
        proc = subprocess.run(
            [args.llama_server, "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        print(json.dumps(parse_llama_help(proc.stdout), sort_keys=True))
        return 0
    if args.nvidia_smi_row:
        print(json.dumps(parse_nvidia_smi_csv(args.nvidia_smi_row), sort_keys=True))
        return 0
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
