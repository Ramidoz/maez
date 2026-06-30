import unittest

import tests._jetson_edge_path  # noqa: F401
from jetson_presence import capture


_EXPECTED_CAMERA_METHODS = {"open", "read_frame", "release"}
_FORBIDDEN_PUBLIC_NAME_PARTS = ("write", "save", "sink", "file")


class _FakeCap:
    def __init__(self, opened=True, read_ok=True):
        self._opened = opened
        self._read_ok = read_ok
        self.released = False

    def isOpened(self):
        return self._opened

    def read(self):
        return (self._read_ok, object() if self._read_ok else None)

    def release(self):
        self.released = True


class _FakeCV2:
    def __init__(self, *caps):
        self._caps = list(caps)
        self.capture_indexes = []

    def VideoCapture(self, index):
        self.capture_indexes.append(index)
        return self._caps.pop(0)

    def __getattr__(self, name):
        if any(part in name.lower() for part in _FORBIDDEN_PUBLIC_NAME_PARTS):
            raise AssertionError(f"unexpected cv2 surface: {name}")
        raise AttributeError(name)


class CaptureTests(unittest.TestCase):
    def test_open_read_release(self):
        cap = _FakeCap(opened=True, read_ok=True)
        cv2 = _FakeCV2(cap)
        cam = capture.Camera(device_index=7, cv2_module=cv2)
        self.assertTrue(cam.open())
        self.assertEqual([7], cv2.capture_indexes)
        ok, frame = cam.read_frame()
        self.assertTrue(ok)
        self.assertIsNotNone(frame)
        cam.release()
        self.assertTrue(cap.released)

    def test_open_failure(self):
        cap = _FakeCap(opened=False)
        cam = capture.Camera(device_index=0, cv2_module=_FakeCV2(cap))
        self.assertFalse(cam.open())

    def test_read_failure(self):
        cap = _FakeCap(opened=True, read_ok=False)
        cam = capture.Camera(device_index=0, cv2_module=_FakeCV2(cap))
        cam.open()
        ok, frame = cam.read_frame()
        self.assertFalse(ok)
        self.assertIsNone(frame)

    def test_open_releases_existing_capture_before_replacing(self):
        first = _FakeCap(opened=True, read_ok=True)
        second = _FakeCap(opened=True, read_ok=True)
        cv2 = _FakeCV2(first, second)
        cam = capture.Camera(device_index=2, cv2_module=cv2)

        self.assertTrue(cam.open())
        self.assertFalse(first.released)
        self.assertTrue(cam.open())

        self.assertTrue(first.released)
        self.assertFalse(second.released)
        self.assertEqual([2, 2], cv2.capture_indexes)

    def test_capture_module_calls_no_write(self):
        cap = _FakeCap(opened=True, read_ok=True)
        cv2 = _FakeCV2(cap)
        cam = capture.Camera(device_index=0, cv2_module=cv2)
        cam.open()
        cam.read_frame()
        cam.release()

        public_methods = {
            name
            for name in dir(capture.Camera)
            if not name.startswith("_") and callable(getattr(capture.Camera, name))
        }
        self.assertEqual(_EXPECTED_CAMERA_METHODS, public_methods)
        self.assertFalse(
            [
                name
                for name in public_methods
                if any(part in name.lower() for part in _FORBIDDEN_PUBLIC_NAME_PARTS)
            ]
        )
        self.assertEqual([0], cv2.capture_indexes)


if __name__ == "__main__":
    unittest.main()
