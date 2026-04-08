"""
presence_perception.py — Camera-based presence + face recognition for Maez

Uses OBSBOT Meet 2 (index 0):
- MediaPipe Face Detection for fast presence check
- face_recognition (dlib) to identify WHO is at the desk

Runs observe() on demand — opens camera, captures frames, closes.
Returns PresenceSnapshot with presence state, identity, and duration.
"""

import logging
import os
import pickle
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("maez")

CAMERA_INDEX = 0
MODEL_PATH = '/home/rohit/maez/models/blaze_face.tflite'
MIN_CONFIDENCE = 0.6
FRAMES_TO_CHECK = 5
PRESENCE_THRESHOLD = 2

# Face recognition
ENROLLMENT_PATH = '/home/rohit/maez/models/face/rohit_embeddings.pkl'
RECOGNITION_THRESHOLD = 0.55  # lower = stricter

# Persistent face detector — initialized once, reused forever
_detector = None

def _get_detector():
    """Initialize MediaPipe face detector once and reuse."""
    global _detector
    if _detector is not None:
        return _detector
    try:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
        base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
        options = mp_vision.FaceDetectorOptions(
            base_options=base_options,
            min_detection_confidence=MIN_CONFIDENCE,
        )
        _detector = mp_vision.FaceDetector.create_from_options(options)
        logger.info("Face detector initialized (persistent)")
        return _detector
    except Exception as e:
        logger.error(f"Face detector init failed: {e}")
        return None


# Module-level state
_presence_state = {
    'present': False,
    'session_start': None,
    'absent_since': None,
    'last_seen': None,
    'total_sessions_today': 0,
    'person': 'unknown',
}

_enrollment = None
_enrollment_loaded = False


def _load_enrollment():
    """Load Rohit's face embeddings. Called once lazily."""
    global _enrollment, _enrollment_loaded
    if _enrollment_loaded:
        return _enrollment
    _enrollment_loaded = True
    if not os.path.exists(ENROLLMENT_PATH):
        logger.info("No face enrollment found — detection only, no recognition")
        return None
    try:
        with open(ENROLLMENT_PATH, 'rb') as f:
            _enrollment = pickle.load(f)
        logger.info("Face enrollment loaded: %s, %d reference frames",
                     _enrollment['name'], _enrollment['frame_count'])
        return _enrollment
    except Exception as e:
        logger.error("Failed to load enrollment: %s", e)
        return None


@dataclass
class PresenceSnapshot:
    rohit_present: bool
    confidence: float
    session_minutes: float
    absent_minutes: float
    just_arrived: bool
    just_left: bool
    person_identified: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: Optional[str] = None

    def format_for_context(self) -> str:
        if not self.success:
            return f"[PRESENCE] Camera unavailable: {self.error}"

        if self.person_identified == "stranger" and self.rohit_present:
            return "[PRESENCE] Someone is at the desk — not Rohit."

        if self.just_arrived:
            if self.person_identified == "Rohit":
                return "[PRESENCE] Rohit just sat down at his desk."
            return "[PRESENCE] Someone just sat down at the desk."

        if self.just_left:
            return "[PRESENCE] Rohit just stepped away from his desk."

        if self.rohit_present:
            who = self.person_identified if self.person_identified != "unknown" else "Rohit"
            mins = self.session_minutes
            if mins < 1:
                return f"[PRESENCE] {who} is at his desk."
            elif mins < 60:
                return f"[PRESENCE] {who} at desk — {int(mins)} minutes."
            else:
                return f"[PRESENCE] {who} at desk — {mins/60:.1f} hours."
        else:
            if self.absent_minutes < 2:
                return "[PRESENCE] Rohit stepped away briefly."
            elif self.absent_minutes < 30:
                return f"[PRESENCE] Rohit away — {int(self.absent_minutes)} minutes."
            else:
                return f"[PRESENCE] Rohit has been away {int(self.absent_minutes)} minutes."

    def format_for_memory(self) -> str:
        if not self.success:
            return "Presence: unknown."
        status = "present" if self.rohit_present else "away"
        who = self.person_identified if self.person_identified != "unknown" else "Rohit"
        mins = self.session_minutes if self.rohit_present else self.absent_minutes
        return f"Presence: {who} {status} for {int(mins)} minutes."


def _detect_and_recognize() -> tuple:
    """
    Open camera, detect faces with MediaPipe, recognize with face_recognition.
    Returns (detection_count, max_confidence, person_identified).
    """
    try:
        import cv2
        import mediapipe as mp

        if not os.path.exists(MODEL_PATH):
            return 0, 0.0, "unknown"

        # Use persistent detector — initialized once at module level
        detector = _get_detector()
        if detector is None:
            return 0, 0.0, "unknown"


        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            logger.warning("Camera %d not available", CAMERA_INDEX)
            return 0, 0.0, "unknown"

        detections = 0
        max_conf = 0.0
        person = "unknown"
        best_rgb = None  # Keep the best frame for recognition

        for _ in range(FRAMES_TO_CHECK):
            ret, frame = cap.read()
            if not ret:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = detector.detect(mp_image)
            if result.detections:
                conf = result.detections[0].categories[0].score
                if conf >= MIN_CONFIDENCE:
                    detections += 1
                    if conf > max_conf:
                        max_conf = conf
                        best_rgb = rgb  # Save highest-confidence frame

        cap.release()
        # detector stays open (persistent)

        # Face recognition on the best frame
        if best_rgb is not None and detections >= PRESENCE_THRESHOLD:
            enrollment = _load_enrollment()
            if enrollment is not None:
                try:
                    import face_recognition as fr
                    locations = fr.face_locations(best_rgb, model='hog')
                    if locations:
                        encodings = fr.face_encodings(best_rgb, locations)
                        if encodings:
                            distances = fr.face_distance(
                                [enrollment['mean_embedding']], encodings[0]
                            )
                            distance = distances[0]
                            if distance < RECOGNITION_THRESHOLD:
                                person = enrollment['name']
                                logger.debug("Recognized: %s (distance=%.3f)",
                                             person, distance)
                            else:
                                person = "stranger"
                                logger.debug("Unrecognized face (distance=%.3f)",
                                             distance)
                except Exception as e:
                    logger.debug("Recognition error: %s", e)

        return detections, max_conf, person

    except Exception as e:
        logger.debug("Face detection error: %s", e)
        return 0, 0.0, "unknown"


def observe() -> PresenceSnapshot:
    """Main entry point. Detect presence + identify person."""
    global _presence_state

    try:
        detections, confidence, person = _detect_and_recognize()
        present_now = detections >= PRESENCE_THRESHOLD
        now = time.time()

        prev_present = _presence_state['present']

        # Only count as "arrived" if it's Rohit or unknown (no enrollment)
        is_rohit = person in ("Rohit", "unknown")
        just_arrived = present_now and not prev_present and is_rohit
        just_left = not present_now and prev_present

        if just_arrived:
            _presence_state['session_start'] = now
            _presence_state['absent_since'] = None
            _presence_state['total_sessions_today'] += 1
            logger.info("Rohit arrived at desk")
        elif present_now and not prev_present and person == "stranger":
            logger.info("Stranger detected at desk")
        elif just_left:
            _presence_state['absent_since'] = now
            _presence_state['session_start'] = None
            logger.info("Rohit left desk")

        if present_now:
            _presence_state['last_seen'] = now
        _presence_state['present'] = present_now
        _presence_state['person'] = person

        session_mins = 0.0
        absent_mins = 0.0
        if present_now and _presence_state['session_start']:
            session_mins = (now - _presence_state['session_start']) / 60
        if not present_now and _presence_state['absent_since']:
            absent_mins = (now - _presence_state['absent_since']) / 60

        return PresenceSnapshot(
            rohit_present=present_now, confidence=confidence,
            session_minutes=session_mins, absent_minutes=absent_mins,
            just_arrived=just_arrived, just_left=just_left,
            person_identified=person, success=True,
        )

    except Exception as e:
        logger.error("Presence observation error: %s", e)
        return PresenceSnapshot(
            rohit_present=False, confidence=0.0,
            session_minutes=0.0, absent_minutes=0.0,
            just_arrived=False, just_left=False,
            person_identified="unknown", success=False, error=str(e),
        )


def is_present() -> bool:
    return _presence_state.get('present', False)


def test():
    print("Presence + recognition test — 30 seconds\n")
    start = time.time()
    while time.time() - start < 30:
        snap = observe()
        if snap.success:
            status = "PRESENT" if snap.rohit_present else "AWAY"
            extra = ""
            if snap.just_arrived:
                extra = " <- ARRIVED"
            elif snap.just_left:
                extra = " <- LEFT"
            print(f"  {status} | person={snap.person_identified} | "
                  f"conf={snap.confidence:.2f}{extra}")
        else:
            print(f"  ERROR: {snap.error}")
        time.sleep(3)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    test()
