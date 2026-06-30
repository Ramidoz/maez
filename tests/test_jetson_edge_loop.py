import unittest

import tests._jetson_edge_path  # noqa: F401
from jetson_presence import presence_loop


class _Cam:
    def __init__(self, open_ok=True, read_ok=True):
        self._open_ok = open_ok
        self._read_ok = read_ok
        self.opened = False
        self.released = False
        self.frames_read = 0

    def open(self):
        self.opened = True
        return self._open_ok

    def read_frame(self):
        self.frames_read += 1
        return (self._read_ok, object() if self._read_ok else None)

    def release(self):
        self.released = True


class LoopStateMapTests(unittest.TestCase):
    def _run(self, cam, curtained):
        emitted = []
        lab = presence_loop.run_once(
            camera=cam,
            emit=lambda label: emitted.append(label),
            is_curtained=lambda: curtained,
            now_ts=lambda: "T",
        )
        return lab, emitted

    def test_curtained_releases_camera_and_emits_curtained(self):
        cam = _Cam()
        lab, emitted = self._run(cam, curtained=True)
        self.assertTrue(cam.released)
        self.assertFalse(cam.opened)
        self.assertEqual(lab["sensor_state"], "curtained")
        self.assertEqual(lab["owner_present"], "unknown")
        self.assertEqual(lab["confidence"], "low")
        self.assertEqual(emitted, [lab])

    def test_open_and_read_ok_is_available_unknown_and_releases(self):
        cam = _Cam(open_ok=True, read_ok=True)
        lab, emitted = self._run(cam, curtained=False)
        self.assertTrue(cam.opened)
        self.assertEqual(cam.frames_read, 1)
        self.assertTrue(cam.released)
        self.assertEqual(lab["sensor_state"], "available")
        self.assertEqual(lab["owner_present"], "unknown")
        self.assertEqual(lab["confidence"], "low")
        self.assertEqual(emitted, [lab])

    def test_open_fail_is_unavailable_unknown_and_releases(self):
        cam = _Cam(open_ok=False)
        lab, _ = self._run(cam, curtained=False)
        self.assertTrue(cam.released)
        self.assertEqual(lab["sensor_state"], "unavailable")
        self.assertEqual(lab["owner_present"], "unknown")
        self.assertEqual(lab["confidence"], "low")

    def test_read_fail_is_error_unknown_and_releases(self):
        cam = _Cam(open_ok=True, read_ok=False)
        lab, _ = self._run(cam, curtained=False)
        self.assertTrue(cam.released)
        self.assertEqual(lab["sensor_state"], "error")
        self.assertEqual(lab["owner_present"], "unknown")
        self.assertEqual(lab["confidence"], "low")

    def test_never_present_or_absent(self):
        for curtained, ook, rok in [
            (True, True, True),
            (False, True, True),
            (False, False, True),
            (False, True, False),
        ]:
            lab, _ = self._run(_Cam(open_ok=ook, read_ok=rok), curtained=curtained)
            self.assertEqual(lab["owner_present"], "unknown")
            self.assertNotIn(lab["owner_present"], {"present", "absent"})
