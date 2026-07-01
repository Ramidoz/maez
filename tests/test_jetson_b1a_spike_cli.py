import unittest

import tests._jetson_edge_path  # noqa: F401
from jetson_presence.b1a import spike


class SpikeCliTests(unittest.TestCase):
    def test_parser_defaults_are_bounded_and_local_only(self):
        args = spike.build_parser().parse_args([])

        self.assertEqual(args.frames, 30)
        self.assertEqual(args.device_index, 0)
        self.assertEqual(args.detector_engine, "models/det_500m.fp32.engine")
        self.assertEqual(args.embedding_engine, "models/w600k_mbf.fp32.engine")


if __name__ == "__main__":
    unittest.main()
