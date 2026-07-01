"""jetson_face_facts.v0 contract: pure per-frame face-geometry validation.

No I/O. The Jetson eye emits perceptual facts (detections + embeddings), never
conclusions. ``faces: []`` means "the detector found zero faces in this frame":
a fact about detections, not "no one is here." Absence is a brain inference
over many facts, never an eye claim.
"""

from __future__ import annotations

import math
import re

SCHEMA_VERSION = "jetson_face_facts.v0"
EMBEDDING_DIM = 512

_SAFE_MODEL_ID = re.compile(r"^[A-Za-z0-9_./+-]{1,128}$")
_SENSOR_STATES = frozenset({"available", "curtained", "error"})
_FRAME_QUALITIES = frozenset({"good", "low", "unknown"})
_ALLOWED_FRAME_KEYS = frozenset(
    {"schema_version", "model_id", "sensor_state", "frame_quality", "ts", "faces"}
)
_ALLOWED_FACE_KEYS = frozenset({"embedding", "det_score", "box", "track_id"})

_Number = (int, float)


def _finite_number(value: object) -> bool:
    return isinstance(value, _Number) and not isinstance(value, bool) and math.isfinite(value)


def _valid_face(face: object) -> bool:
    if not isinstance(face, dict) or set(face.keys()) != _ALLOWED_FACE_KEYS:
        return False

    embedding = face["embedding"]
    if not isinstance(embedding, list) or len(embedding) != EMBEDDING_DIM:
        return False
    if not all(_finite_number(item) for item in embedding):
        return False

    det_score = face["det_score"]
    if not _finite_number(det_score) or not 0.0 <= det_score <= 1.0:
        return False

    box = face["box"]
    if not isinstance(box, list) or len(box) != 4:
        return False
    if not all(_finite_number(item) for item in box):
        return False

    track_id = face["track_id"]
    if track_id is not None and not isinstance(track_id, str):
        return False

    return True


def parse_face_facts(raw: object) -> dict | None:
    """Validate a raw payload into the contract dict, or ``None`` if malformed."""
    if not isinstance(raw, dict) or set(raw.keys()) != _ALLOWED_FRAME_KEYS:
        return None
    if raw.get("schema_version") != SCHEMA_VERSION:
        return None

    model_id = raw.get("model_id")
    if not isinstance(model_id, str) or not _SAFE_MODEL_ID.match(model_id):
        return None
    if raw.get("sensor_state") not in _SENSOR_STATES:
        return None
    if raw.get("frame_quality") not in _FRAME_QUALITIES:
        return None

    ts = raw.get("ts")
    if not isinstance(ts, str) or not ts.strip():
        return None

    faces = raw.get("faces")
    if not isinstance(faces, list):
        return None
    if not all(_valid_face(face) for face in faces):
        return None

    if raw["sensor_state"] != "available" and faces:
        return None

    return raw


def face_count(reading: dict) -> int:
    """Number of detected faces this frame. Not a presence/absence verdict."""
    return len(reading.get("faces", []))


def jetson_face_facts_shadow_enabled() -> bool:
    """Default-off shadow flag. Off means the endpoint is unavailable."""
    from core.infra.env_flags import strict_env_flag

    return strict_env_flag("MAEZ_JETSON_FACE_FACTS_SHADOW")
