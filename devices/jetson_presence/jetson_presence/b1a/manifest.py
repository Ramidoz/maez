"""Load + integrity-verify the tracked model manifest. The .onnx/.engine artifacts
themselves are gitignored, Jetson-local; this code + the JSON are the repo truth."""
from __future__ import annotations

import hashlib
import json
import os
import re

PENDING = "PENDING_LOCK"  # sentinel: no real hash pinned yet -> build must refuse
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

_DEFAULT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "models", "manifest.json")
)


def load_manifest(path: str = _DEFAULT) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def hashes_locked(manifest: dict) -> bool:
    """True only when every model carries a real-looking pinned digest: a 64-char
    lowercase hex sha256 (not empty, not the PENDING sentinel, not a malformed value).
    The two-phase setup refuses to build any engine while this is False."""
    models = manifest.get("models", [])
    if not models:
        return False
    return all(_SHA256_HEX.match((m.get("sha256") or "").lower()) for m in models)


def verify_sha256(file_path: str, expected_hex: str) -> bool:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest() == expected_hex.lower()
