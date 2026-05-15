# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
presence_perception.py — Camera-based presence detection for Maez

Uses OBSBOT Meet 2 (index 0):
- MediaPipe Face Detection for fast presence check

Runs observe() on demand — opens camera, captures frames, closes.
Returns PresenceSnapshot with anonymous presence state only.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("maez")

CAMERA_INDEX = 0
CAMERA_INDEX_ENV = "MAEZ_CAMERA_PRESENCE_CAMERA_INDEX"
try:
    from core.infra import paths as _paths

    _MODELS_DIR = _paths.models_dir()
except Exception:
    from pathlib import Path as _Path

    _MODELS_DIR = _Path(__file__).resolve().parent.parent / "models"
MODEL_PATH = str(_MODELS_DIR / "blaze_face.tflite")
MIN_CONFIDENCE = 0.6
FRAMES_TO_CHECK = 5
PRESENCE_THRESHOLD = 2

# Persistent face detector — initialized once, reused forever
_detector = None
_native_initialized = False
_detection_error: Optional[str] = None
_missing_dependency_logged: set[str] = set()


def _mark_detection_unavailable(reason: str, dependency: Optional[str] = None) -> tuple:
    """Record a sensor/dependency failure without converting it into absence."""
    global _detection_error
    _detection_error = reason
    if dependency is not None:
        if dependency not in _missing_dependency_logged:
            logger.warning("Presence detection disabled: %s", reason)
            _missing_dependency_logged.add(dependency)
    else:
        logger.warning("Presence detection unavailable: %s", reason)
    return 0, 0.0


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
    "present": False,
}

def _configure_cv2_runtime(cv2_module) -> None:
    """Keep OpenCV's native worker pool bounded for presence checks."""
    try:
        cv2_module.setNumThreads(1)
    except Exception:
        pass
    try:
        if hasattr(cv2_module, "ocl"):
            cv2_module.ocl.setUseOpenCL(False)
    except Exception:
        pass


def _camera_index() -> int:
    """Resolve the local camera index without widening observation surface."""
    raw_index = (os.environ.get(CAMERA_INDEX_ENV) or "").strip()
    if raw_index:
        try:
            return int(raw_index)
        except ValueError:
            logger.warning(
                "Invalid %s=%r; using default camera index",
                CAMERA_INDEX_ENV,
                raw_index,
            )
    return CAMERA_INDEX


@dataclass
class PresenceSnapshot:
    presence_detected: bool
    confidence: float
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: Optional[str] = None


def _detect_presence() -> tuple:
    """
    Open camera and detect anonymous human-shaped presence with MediaPipe.
    Returns (detection_count, max_confidence).
    """
    global _detection_error, _native_initialized
    _detection_error = None
    try:
        try:
            import cv2
        except Exception as e:
            return _mark_detection_unavailable(f"cv2 unavailable: {e}", "cv2")
        _configure_cv2_runtime(cv2)
        try:
            import mediapipe as mp
        except Exception as e:
            return _mark_detection_unavailable(
                f"mediapipe unavailable: {e}",
                "mediapipe",
            )
        _native_initialized = True

        if not os.path.exists(MODEL_PATH):
            return _mark_detection_unavailable(
                f"face detection model unavailable: {MODEL_PATH}",
                "blaze_face_model",
            )

        # Use persistent detector — initialized once at module level
        detector = _get_detector()
        if detector is None:
            return _mark_detection_unavailable("face detector failed to initialize")

        camera_index = _camera_index()
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            return _mark_detection_unavailable(f"camera {camera_index} not available")

        detections = 0
        max_conf = 0.0

        try:
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
        finally:
            cap.release()
        # detector stays open (persistent)

        return detections, max_conf

    except Exception as e:
        return _mark_detection_unavailable(f"face detection error: {e}")


def observe() -> PresenceSnapshot:
    """Main entry point. Detect anonymous presence only."""
    global _presence_state

    try:
        detections, confidence = _detect_presence()
        if _detection_error is not None:
            return PresenceSnapshot(
                presence_detected=False,
                confidence=0.0,
                success=False,
                error=_detection_error,
            )

        present_now = detections >= PRESENCE_THRESHOLD
        _presence_state["present"] = present_now

        return PresenceSnapshot(
            presence_detected=present_now,
            confidence=confidence,
            success=True,
        )

    except Exception as e:
        logger.error("Presence observation error: %s", e)
        return PresenceSnapshot(
            presence_detected=False,
            confidence=0.0,
            success=False,
            error=str(e),
        )


def shutdown() -> None:
    """Release persistent native presence resources during daemon stop."""
    global _detector
    detector = _detector
    _detector = None
    if not _native_initialized and detector is None:
        return
    if detector is not None:
        try:
            detector.close()
        except Exception as e:
            logger.debug("Presence detector close failed: %s", e)
    try:
        import cv2

        _configure_cv2_runtime(cv2)
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
    except Exception as e:
        logger.debug("OpenCV shutdown cleanup skipped: %s", e)


def is_present() -> bool:
    return _presence_state.get("present", False)


def test():
    print("Presence test — 30 seconds\n")
    start = time.time()
    while time.time() - start < 30:
        snap = observe()
        if snap.success:
            status = "PRESENT" if snap.presence_detected else "ABSENT"
            print(f"  {status} | conf={snap.confidence:.2f}")
        else:
            print(f"  ERROR: {snap.error}")
        time.sleep(3)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test()
