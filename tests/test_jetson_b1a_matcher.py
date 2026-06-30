import unittest
import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import matcher


class MatcherTests(unittest.TestCase):
    def test_identical_vectors_distance_zero_and_match(self):
        v = [0.0, 1.0, 0.0, 0.0]
        self.assertAlmostEqual(matcher.cosine_distance(v, v), 0.0, places=6)
        self.assertTrue(matcher.is_match(matcher.cosine_distance(v, v), threshold=0.4))

    def test_orthogonal_vectors_distance_one_no_match(self):
        a = [1.0, 0.0]; b = [0.0, 1.0]
        self.assertAlmostEqual(matcher.cosine_distance(a, b), 1.0, places=6)
        self.assertFalse(matcher.is_match(matcher.cosine_distance(a, b), threshold=0.4))

    def test_random_dissimilar_vectors_no_match(self):
        a = [0.9, 0.1, 0.05, 0.0]; b = [-0.8, 0.2, 0.9, 0.3]
        self.assertFalse(matcher.is_match(matcher.cosine_distance(a, b), threshold=0.4))

    def test_threshold_boundary(self):
        self.assertTrue(matcher.is_match(0.39, threshold=0.4))
        self.assertFalse(matcher.is_match(0.40, threshold=0.4))  # strict <

    def test_zero_vector_is_safe_no_match(self):
        d = matcher.cosine_distance([0.0, 0.0], [1.0, 0.0])
        self.assertFalse(matcher.is_match(d, threshold=0.4))


if __name__ == "__main__":
    unittest.main()
