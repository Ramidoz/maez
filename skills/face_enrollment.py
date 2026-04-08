"""
face_enrollment.py — Teach Maez who Rohit is

Run once (and whenever you want to update).
Captures 20 frames from the OBSBOT, extracts face embeddings,
stores them permanently in a local file and ChromaDB core memory.
"""

import logging
import os
import pickle
import sys
import time

import cv2
import face_recognition
import numpy as np

logger = logging.getLogger(__name__)

CAMERA_INDEX = 0
NUM_ENROLLMENT_FRAMES = 20
ENROLLMENT_PATH = '/home/rohit/maez/models/face/rohit_embeddings.pkl'
CAPTURE_INTERVAL = 0.5


def enroll(name: str = "Rohit") -> bool:
    os.makedirs(os.path.dirname(ENROLLMENT_PATH), exist_ok=True)

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

    with open(ENROLLMENT_PATH, 'wb') as f:
        pickle.dump(enrollment_data, f)

    print(f"\nSUCCESS: {frame_count} frames enrolled for {name}")
    print(f"Saved to: {ENROLLMENT_PATH}")

    try:
        sys.path.insert(0, '/home/rohit/maez')
        from memory.memory_manager import MemoryManager
        mm = MemoryManager()
        mm.store_core(
            f"Face enrollment: Rohit's face enrolled on {time.strftime('%Y-%m-%d')} "
            f"with {frame_count} reference frames. Maez can now recognize Rohit by sight.",
            source="face_enrollment",
        )
        print("Enrollment recorded in core memory")
    except Exception as e:
        print(f"Note: Could not store in ChromaDB: {e}")

    return True


def load_enrollment() -> dict:
    if not os.path.exists(ENROLLMENT_PATH):
        return None
    try:
        with open(ENROLLMENT_PATH, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        logger.error("Failed to load enrollment: %s", e)
        return None


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    name = sys.argv[1] if len(sys.argv) > 1 else "Rohit"
    success = enroll(name)
    sys.exit(0 if success else 1)
