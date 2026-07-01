import unittest

import numpy as np

import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import detector


class ScrfdDecodeTests(unittest.TestCase):
    def test_anchor_centers_match_scrfd_stride_layout(self):
        centers = detector.anchor_centers((16, 16), stride=8, num_anchors=2)

        self.assertEqual(centers.shape, (8, 2))
        self.assertEqual(centers[:4].tolist(), [[0.0, 0.0], [0.0, 0.0], [8.0, 0.0], [8.0, 0.0]])

    def test_decode_applies_stride_scaled_distances(self):
        scores = [
            np.array([[0.9], [0.1], [0.1], [0.1], [0.1], [0.1], [0.1], [0.1]], dtype=np.float32),
            np.zeros((0, 1), dtype=np.float32),
            np.zeros((0, 1), dtype=np.float32),
        ]
        bboxes = [
            np.array([[1, 2, 3, 4], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0],
                      [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]], dtype=np.float32),
            np.zeros((0, 4), dtype=np.float32),
            np.zeros((0, 4), dtype=np.float32),
        ]
        kps = [
            np.zeros((8, 10), dtype=np.float32),
            np.zeros((0, 10), dtype=np.float32),
            np.zeros((0, 10), dtype=np.float32),
        ]

        dets = detector.decode_scrfd([*scores, *bboxes, *kps], input_shape=(16, 16), score_threshold=0.5)

        self.assertEqual(len(dets), 1)
        box, score = dets[0]
        self.assertEqual(box, (-8.0, -16.0, 24.0, 32.0))
        self.assertAlmostEqual(score, 0.9, places=6)

    def test_nms_keeps_highest_overlapping_box(self):
        detections = [((0.0, 0.0, 10.0, 10.0), 0.9), ((1.0, 1.0, 11.0, 11.0), 0.8)]

        kept = detector.nms(detections, threshold=0.4)

        self.assertEqual(kept, [((0.0, 0.0, 10.0, 10.0), 0.9)])


if __name__ == "__main__":
    unittest.main()
