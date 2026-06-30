"""Runtime config for the Jetson edge producer. Read from env; no secrets in source."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeConfig:
    host_url: str
    intake_path: str
    token: str
    curtain_sentinel: str
    device_index: int
    cadence_seconds: float


def load_config() -> EdgeConfig:
    return EdgeConfig(
        host_url=os.environ.get("MAEZ_JETSON_HOST_URL", "http://127.0.0.1:11437"),
        intake_path="/api/v1/presence/jetson/intake",
        token=os.environ.get("MAEZ_JETSON_DEVICE_TOKEN", ""),
        curtain_sentinel=os.environ.get("MAEZ_JETSON_CURTAIN_SENTINEL", "/run/maez/jetson_curtain"),
        device_index=int(os.environ.get("MAEZ_JETSON_DEVICE_INDEX", "0")),
        cadence_seconds=float(os.environ.get("MAEZ_JETSON_CADENCE_SECONDS", "5")),
    )
