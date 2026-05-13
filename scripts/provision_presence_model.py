#!/usr/bin/env python3
"""Provision the MediaPipe face detector model used by presence_perception."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path
from typing import Callable

from core.infra import paths

MODEL_FILENAME = "blaze_face.tflite"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
MODEL_SHA256 = "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f"


class ModelHashError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def provision_model(
    *,
    model_path: Path | None = None,
    expected_sha256: str = MODEL_SHA256,
    url: str = MODEL_URL,
    urlopen: Callable = urllib.request.urlopen,
) -> Path:
    model_path = model_path or paths.models_dir() / MODEL_FILENAME
    if model_path.exists() and _sha256(model_path.read_bytes()) == expected_sha256:
        return model_path

    model_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=30) as response:
        data = response.read()

    actual_sha256 = _sha256(data)
    if actual_sha256 != expected_sha256:
        raise ModelHashError(
            f"model sha256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )

    tmp_path = model_path.with_suffix(model_path.suffix + ".tmp")
    tmp_path.write_bytes(data)
    tmp_path.replace(model_path)
    return model_path


def main() -> int:
    try:
        model_path = provision_model()
    except Exception as exc:
        print(f"presence model provision failed: {exc}", file=sys.stderr)
        return 1
    print(f"presence model ready: {model_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
