"""Runtime config for the Jetson edge producer. Read from env; no secrets in source."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EdgeConfig:
    host_url: str
    intake_path: str
    face_facts_intake_path: str
    face_facts_frames: int
    face_facts_model_id: str
    detector_engine_path: str
    embedding_engine_path: str
    token: str
    curtain_sentinel: str
    device_index: int
    cadence_seconds: float


def load_config() -> EdgeConfig:
    return EdgeConfig(
        host_url=os.environ.get("MAEZ_JETSON_HOST_URL", "http://127.0.0.1:11437"),
        intake_path="/api/v1/presence/jetson/intake",
        face_facts_intake_path=os.environ.get(
            "MAEZ_JETSON_FACE_FACTS_INTAKE_PATH",
            "/api/v1/perception/jetson/face_facts",
        ),
        face_facts_frames=int(os.environ.get("MAEZ_JETSON_FACE_FACTS_FRAMES", "1")),
        face_facts_model_id=os.environ.get(
            "MAEZ_JETSON_FACE_FACTS_MODEL_ID",
            "buffalo_s/scrfd_500m+w600k_mbf",
        ),
        detector_engine_path=os.environ.get(
            "MAEZ_JETSON_DETECTOR_ENGINE",
            "models/det_500m.fp32.engine",
        ),
        embedding_engine_path=os.environ.get(
            "MAEZ_JETSON_EMBEDDING_ENGINE",
            "models/w600k_mbf.fp32.engine",
        ),
        token=os.environ.get("MAEZ_JETSON_DEVICE_TOKEN", ""),
        curtain_sentinel=os.environ.get("MAEZ_JETSON_CURTAIN_SENTINEL", "/run/maez/jetson_curtain"),
        device_index=int(os.environ.get("MAEZ_JETSON_DEVICE_INDEX", "0")),
        cadence_seconds=float(os.environ.get("MAEZ_JETSON_CADENCE_SECONDS", "5")),
    )
