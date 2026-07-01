import unittest

import numpy as np

import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import detector, parity


class RunParityHelpersTests(unittest.TestCase):
    def test_detector_parity_passes_when_both_see_no_face(self):
        result = parity.detector_parity_result([], [])

        self.assertTrue(result["passed"])
        self.assertEqual(result["reason"], "no_detection")

    def test_detector_parity_fails_when_only_one_path_detects(self):
        result = parity.detector_parity_result([((0.0, 0.0, 1.0, 1.0), 0.9)], [])

        self.assertFalse(result["passed"])
        self.assertEqual(result["reason"], "detection_mismatch")

    def test_detector_parity_compares_top_detection(self):
        result = parity.detector_parity_result(
            [((0.0, 0.0, 10.0, 10.0), 0.9)],
            [((0.0, 0.0, 10.0, 10.0), 0.905)],
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["reason"], "top_detection")

    def test_crop_face_clips_to_frame(self):
        frame = np.zeros((10, 20, 3), dtype=np.uint8)

        crop = detector.crop_face(frame, (-5.0, -4.0, 8.0, 6.0))

        self.assertEqual(crop.shape, (6, 8, 3))


if __name__ == "__main__":
    unittest.main()
