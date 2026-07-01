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


def _lockable_shas(manifest: dict) -> list:
    """Every sha256 that must be pinned before a build: the source pack (if the
    manifest sources models from a zip) plus every model member."""
    shas = []
    pack = manifest.get("source_pack")
    if isinstance(pack, dict):
        shas.append(pack.get("sha256"))
    shas.extend(m.get("sha256") for m in manifest.get("models", []))
    return shas


def hashes_locked(manifest: dict) -> bool:
    """True only when every pinned digest (source pack + each model) is a real-looking
    64-char lowercase hex sha256 — not empty, not the PENDING sentinel, not malformed.
    The setup refuses to build any engine while this is False."""
    shas = _lockable_shas(manifest)
    if not shas:
        return False
    return all(_SHA256_HEX.match((s or "").lower()) for s in shas)


def verify_sha256(file_path: str, expected_hex: str) -> bool:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest() == expected_hex.lower()
