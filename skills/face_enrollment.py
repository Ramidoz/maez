# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
face_enrollment.py — Teach Maez who the owner is

Run once (and whenever you want to update).
Captures 20 frames from the OBSBOT, extracts face embeddings,
stores them permanently in a local file and ChromaDB core memory.
"""

import logging
import os
import pickle
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

CAMERA_INDEX = 0
NUM_ENROLLMENT_FRAMES = 20
try:
    from core.infra import paths as _paths
    ENROLLMENT_PATH = str(_paths.models_dir() / "face" / "rohit_embeddings.pkl")
except Exception:
    from pathlib import Path as _Path
    ENROLLMENT_PATH = str(
        _Path(__file__).resolve().parent.parent
        / "models" / "face" / "rohit_embeddings.pkl"
    )
CAPTURE_INTERVAL = 0.5


def _ensure_owner_only_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)


def _save_enrollment_data(path: Path, enrollment_data: dict) -> None:
    _ensure_owner_only_parent(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "wb") as f:
        pickle.dump(enrollment_data, f)
    os.chmod(tmp_path, 0o600)
    tmp_path.replace(path)
    os.chmod(path, 0o600)


def _biometric_artifact_owner_only(path: Path) -> bool:
    try:
        return (path.parent.stat().st_mode & 0o077) == 0 and (path.stat().st_mode & 0o077) == 0
    except OSError:
        return False


def enroll(name: str = "the owner") -> bool:
    import cv2
    import face_recognition
    import numpy as np

    enrollment_path = Path(ENROLLMENT_PATH)
    _ensure_owner_only_parent(enrollment_path)

    print(f"\nEnrolling face for: {name}")
    print(f"Camera will capture {NUM_ENROLLMENT_FRAMES} frames.")
    print("Sit naturally in front of the OBSBOT.")
    print("Move your head slightly between captures for variety.\n")
    input("Press Enter when ready...")

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return False

    embeddings = []
    frame_count = 0
    attempts = 0
    max_attempts = NUM_ENROLLMENT_FRAMES * 3

    print(f"\nCapturing {NUM_ENROLLMENT_FRAMES} frames...")

    while frame_count < NUM_ENROLLMENT_FRAMES and attempts < max_attempts:
        ret, frame = cap.read()
        if not ret:
            attempts += 1
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model='hog')

        if len(locations) == 1:
            encoding = face_recognition.face_encodings(rgb, locations)[0]
            embeddings.append(encoding)
            frame_count += 1
            print(f"  Frame {frame_count}/{NUM_ENROLLMENT_FRAMES} captured")
            time.sleep(CAPTURE_INTERVAL)
        elif len(locations) == 0:
            print("  No face detected — adjust position")
            time.sleep(0.3)
        else:
            print("  Multiple faces — ensure only you are visible")
            time.sleep(0.3)

        attempts += 1

    cap.release()

    if frame_count < NUM_ENROLLMENT_FRAMES // 2:
        print(f"\nFAILED: Only {frame_count} frames. Need at least {NUM_ENROLLMENT_FRAMES // 2}.")
        return False

    mean_embedding = np.mean(embeddings, axis=0)

    enrollment_data = {
        'name': name,
        'embeddings': embeddings,
        'mean_embedding': mean_embedding,
        'frame_count': frame_count,
        'enrolled_at': time.time(),
    }

    _save_enrollment_data(enrollment_path, enrollment_data)

    print(f"\nSUCCESS: {frame_count} frames enrolled for {name}")
    print(f"Saved to: {ENROLLMENT_PATH}")

    try:
        from pathlib import Path as _Path
        sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
        from memory.memory_manager import MemoryManager
        mm = MemoryManager()
        _emit_enrollment_core_memory(
            mm=mm, frame_count=frame_count, name=name,
        )
        print("Enrollment recorded in core memory")
    except Exception as e:
        print(f"Note: Could not store in ChromaDB: {e}")

    return True


def _emit_enrollment_core_memory(*, mm, frame_count: int,
                                 name: str = "the owner") -> str:
    """Step 5x.D.D — record the enrollment as a core memory tagged
    as a tool-observation observed-tier event.

    This is a FRESH observed event, not a derivation of any existing
    raw or core memory: the camera frames are sensor data, not
    memory. ``promoted_from`` is therefore intentionally absent —
    inventing a stub ancestor would falsely run through the 5x.D.A
    promotion gate's worst-wins logic on a non-promotion. A future
    agent reading this file: do NOT "fix" the absence by passing
    ``promoted_from=[<something>]``; the design call here is that
    no ancestor exists.

    Tier choice (5x.D.D): ``observed`` (matches the default for
    ``tool_observation`` per ``default_tier_for``). Face enrollment
    is grounded in local sensor + embedding output; it deserves
    trust above legacy/unknown but is NOT covenant law (the
    heartbeat-tier reserved for schema-derived infrastructure
    writes — see ``core/brain/developmental_heartbeat.py``).

    Extracted as a thin helper so 5x.D.D's contract can be unit-
    tested without spinning up the camera + ChromaDB stack."""
    return mm.store_core(
        f"Face enrollment: {name}'s face enrolled on "
        f"{time.strftime('%Y-%m-%d')} with {frame_count} reference "
        "frames. Maez can now recognize the owner by sight.",
        source="face_enrollment",
        # Sensor + embedding pipeline = tool observation. The
        # default tier for tool_observation is `observed`; passing
        # it explicitly here is documentation, not an override.
        provenance_source="tool_observation",
        trust_tier="observed",
    )


def load_enrollment() -> dict:
    path = Path(ENROLLMENT_PATH)
    if not path.exists():
        return None
    if not _biometric_artifact_owner_only(path):
        logger.error("Refusing to load permissive face enrollment artifact")
        return None
    try:
        with open(path, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        logger.error("Failed to load enrollment: %s", e)
        return None


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    name = sys.argv[1] if len(sys.argv) > 1 else "the owner"
    success = enroll(name)
    sys.exit(0 if success else 1)
