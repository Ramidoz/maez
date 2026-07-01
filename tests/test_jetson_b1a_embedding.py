import math
import unittest

import numpy as np

import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import embedding


class EmbeddingTests(unittest.TestCase):
    def test_l2_normalize_returns_unit_vector(self):
        vec = embedding.l2_normalize(np.array([3.0, 4.0], dtype=np.float32))

        self.assertAlmostEqual(math.sqrt(float(np.sum(vec * vec))), 1.0, places=6)
        self.assertAlmostEqual(float(vec[0]), 0.6, places=6)
        self.assertAlmostEqual(float(vec[1]), 0.8, places=6)

    def test_l2_normalize_leaves_zero_vector_safe(self):
        vec = embedding.l2_normalize(np.zeros((3,), dtype=np.float32))

        self.assertEqual(vec.tolist(), [0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
