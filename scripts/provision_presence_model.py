#!/usr/bin/env python3
"""Provision the MediaPipe face detector model used by presence_perception."""

from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from core.infra import paths

MODEL_FILENAME = "blaze_face.tflite"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
MODEL_SHA256 = "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f"
MAX_MODEL_BYTES = 10 * 1024 * 1024


class ModelProvisionError(RuntimeError):
    pass


class ModelHashError(ModelProvisionError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def provision_model(
    *,
    model_path: Path | None = None,
    expected_sha256: str = MODEL_SHA256,
    url: str = MODEL_URL,
    max_bytes: int = MAX_MODEL_BYTES,
    urlopen: Callable = urllib.request.urlopen,
) -> Path:
    model_path = model_path or paths.models_dir() / MODEL_FILENAME
    if urlparse(url).scheme != "https":
        raise ModelProvisionError("presence model URL must use https")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if model_path.parent.is_symlink():
        raise ModelProvisionError(f"presence model parent is a symlink: {model_path.parent}")
    if model_path.parent.stat().st_mode & 0o022:
        raise ModelProvisionError(f"presence model parent is group/world-writable: {model_path.parent}")
    if model_path.is_symlink():
        raise ModelProvisionError(f"presence model target is a symlink: {model_path}")
    if model_path.exists() and _sha256(model_path.read_bytes()) == expected_sha256:
        os.chmod(model_path, 0o644)
        return model_path

    with urlopen(url, timeout=30) as response:
        data = response.read()
    if len(data) > max_bytes:
        raise ModelProvisionError(
            f"presence model payload too large: {len(data)} bytes > {max_bytes}"
        )

    actual_sha256 = _sha256(data)
    if actual_sha256 != expected_sha256:
        raise ModelHashError(
            f"model sha256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )

    tmp_path = model_path.with_suffix(model_path.suffix + ".tmp")
    if tmp_path.is_symlink():
        raise ModelProvisionError(f"presence model temp target is a symlink: {tmp_path}")
    tmp_path.write_bytes(data)
    os.chmod(tmp_path, 0o644)
    tmp_path.replace(model_path)
    os.chmod(model_path, 0o644)
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
