import unittest
import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import parity


class IoUTests(unittest.TestCase):
    def test_identical_boxes_iou_one(self):
        self.assertAlmostEqual(parity.iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0, places=6)

    def test_disjoint_boxes_iou_zero(self):
        self.assertEqual(parity.iou((0, 0, 10, 10), (100, 100, 110, 110)), 0.0)

    def test_half_overlap(self):
        # boxes (0,0,10,10) and (5,0,15,10): inter=50, union=150 -> 1/3
        self.assertAlmostEqual(parity.iou((0, 0, 10, 10), (5, 0, 15, 10)), 1 / 3, places=4)


class BoxParityTests(unittest.TestCase):
    def test_pass_same_box_same_score(self):
        self.assertTrue(parity.box_parity((0, 0, 10, 10), 0.95, (0, 0, 10, 10), 0.951))

    def test_fail_low_iou(self):
        self.assertFalse(parity.box_parity((0, 0, 10, 10), 0.95, (5, 0, 15, 10), 0.95))

    def test_fail_score_drift(self):
        self.assertFalse(parity.box_parity((0, 0, 10, 10), 0.95, (0, 0, 10, 10), 0.90))


class EmbeddingParityTests(unittest.TestCase):
    def test_pass_identical_vectors(self):
        v = [0.1, 0.2, 0.3, 0.9]
        self.assertTrue(parity.embedding_parity(v, v))

    def test_fail_dissimilar_vectors(self):
        self.assertFalse(parity.embedding_parity([1.0, 0.0], [0.0, 1.0]))

    def test_pass_tiny_fp_jitter(self):
        a = [0.1, 0.2, 0.3, 0.9]
        b = [0.1000001, 0.2, 0.3, 0.8999999]
        self.assertTrue(parity.embedding_parity(a, b))  # FP32 jitter still > 0.999 cosine


if __name__ == "__main__":
    unittest.main()
