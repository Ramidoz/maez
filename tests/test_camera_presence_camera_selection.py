import importlib
import json
import os
import sys
import types
import unittest
from unittest.mock import patch


class FakeCapture:
    def __init__(self, index, opened_index):
        self.index = index
        self.opened_index = opened_index
        self.released = False

    def isOpened(self):
        return self.index == self.opened_index

    def read(self):
        return True, object()

    def release(self):
        self.released = True


class FakeDetector:
    def detect(self, _image):
        return types.SimpleNamespace(detections=[])


class CameraPresenceCameraSelectionTests(unittest.TestCase):
    def test_runtime_camera_index_env_selects_nonzero_device(self):
        from skills import presence_perception

        module = importlib.reload(presence_perception)
        opened_indices = []

        class FakeCv2:
            COLOR_BGR2RGB = object()

            @staticmethod
            def setNumThreads(_count):
                return None

            class ocl:
                @staticmethod
                def setUseOpenCL(_enabled):
                    return None

            @staticmethod
            def VideoCapture(index):
                opened_indices.append(index)
                return FakeCapture(index, opened_index=1)

            @staticmethod
            def cvtColor(frame, _mode):
                return frame

        fake_mediapipe = types.SimpleNamespace(
            Image=lambda image_format, data: data,
            ImageFormat=types.SimpleNamespace(SRGB=object()),
        )

        with (
            patch.dict(
                os.environ,
                {"MAEZ_CAMERA_PRESENCE_CAMERA_INDEX": "1"},
                clear=False,
            ),
            patch.dict(
                sys.modules,
                {
                    "cv2": FakeCv2,
                    "mediapipe": fake_mediapipe,
                },
                clear=False,
            ),
            patch.object(module, "_get_detector", return_value=FakeDetector()),
        ):
            snapshot = module.observe()

        self.assertTrue(snapshot.success)
        self.assertEqual([1], opened_indices)

    def test_json_once_cli_emits_content_free_snapshot(self):
        from skills import presence_perception

        module = importlib.reload(presence_perception)
        snapshot = module.PresenceSnapshot(
            presence_detected=False,
            confidence=0.0,
            success=True,
        )

        with patch.object(module, "observe", return_value=snapshot):
            payload = json.loads(module.observe_json_once())

        self.assertEqual(
            {
                "success": True,
                "presence_detected": False,
                "confidence": 0.0,
                "error": "",
            },
            payload,
        )


if __name__ == "__main__":
    unittest.main()
