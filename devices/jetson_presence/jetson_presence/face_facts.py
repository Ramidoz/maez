"""Pure builder for ``jetson_face_facts.v0`` packets.

Geometry only. No identity and no absence verdict. The device run loop captures,
detects, embeds, calls ``build_packet``, posts, and forgets.
"""

from __future__ import annotations

SCHEMA_VERSION = "jetson_face_facts.v0"


def build_packet(*, model_id, sensor_state, frame_quality, ts, faces):
    """Build a per-frame observation packet.

    ``faces`` is an iterable of ``(embedding, det_score, box, track_id)`` tuples.
    When the eye was not looking, the packet carries no face detections.
    """
    if sensor_state != "available":
        face_dicts = []
    else:
        face_dicts = [
            {
                "embedding": [float(value) for value in embedding],
                "det_score": float(det_score),
                "box": [float(value) for value in box],
                "track_id": (str(track_id) if track_id is not None else None),
            }
            for embedding, det_score, box, track_id in faces
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": model_id,
        "sensor_state": sensor_state,
        "frame_quality": frame_quality,
        "ts": ts,
        "faces": face_dicts,
    }
