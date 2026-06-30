"""Thin cv2 capture adapter. The ONLY hardware I/O in B0.

cv2 is injected (tests) or imported lazily (device), so host tests need no
OpenCV. There is deliberately no frame-write API here: frames are read into
RAM, returned, and dropped by the caller. No local file output.
"""

from __future__ import annotations


class Camera:
    def __init__(self, *, device_index: int, cv2_module=None):
        self._index = device_index
        self._cv2 = cv2_module
        self._cap = None

    def _cv2_mod(self):
        if self._cv2 is None:
            import cv2  # lazy: device-only dependency

            self._cv2 = cv2
        return self._cv2

    def open(self) -> bool:
        self.release()
        self._cap = self._cv2_mod().VideoCapture(self._index)
        return bool(self._cap.isOpened())

    def read_frame(self):
        """Return (ok, frame). frame lives in RAM; the caller discards it."""
        if self._cap is None:
            return (False, None)
        ok, frame = self._cap.read()
        return (bool(ok), frame if ok else None)

    def release(self) -> None:
        """Real teardown: release the capture device."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
